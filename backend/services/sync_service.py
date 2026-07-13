import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from ..database import get_db
from . import boss_api

AVATAR_DIR = os.path.join(Path(__file__).parent.parent.parent, "frontend", "public", "avatar")

logger = logging.getLogger("sync")

# 只保存这些类型的消息
ALLOWED_BODY_TYPES = {1, 3, 7, 12, 14, 20}


def _event(event_type: str, **data) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


async def sync_all():
    """全量同步生成器，逐条 yield SSE 事件"""
    conn = get_db()

    # 读取同步天数配置
    row = conn.execute("SELECT value FROM config WHERE key='sync_days'").fetchone()
    sync_days = int(row["value"]) if row else 0
    cutoff = 0
    if sync_days > 0:
        cutoff = int(time.time() * 1000) - sync_days * 86400 * 1000
        logger.info(f"仅同步最近 {sync_days} 天的消息")

    # Step 1: 获取联系人列表
    yield _event("start", phase="friends", message="正在获取联系人列表...")
    try:
        friends = await boss_api.fetch_friend_list()
    except Exception as e:
        logger.error(f"获取联系人列表失败: {e}")
        yield _event("error", phase="friends", message=str(e))
        yield _event("done", friends=0, new_messages=0, errors=[str(e)])
        conn.close()
        return

    # 预筛选：根据 updateTime 过滤联系人数
    skipped_pre = 0
    if sync_days > 0:
        active = [f for f in friends if f.get("updateTime", 0) >= cutoff]
        skipped_pre = len(friends) - len(active)
        logger.info(f"预筛选: {len(friends)} 个联系人 → {len(active)} 个在 {sync_days} 天内有活动")
        yield _event("progress", phase="friends",
                     message=f"获取到 {len(friends)} 个联系人，{len(active)} 个在 {sync_days} 天内有活动",
                     total=len(active), current=0)
        friends = active
    else:
        yield _event("progress", phase="friends",
                     message=f"获取到 {len(friends)} 个联系人",
                     total=len(friends), current=0)

    stats = {"friends": 0, "new_messages": 0, "skipped_bosses": skipped_pre if sync_days > 0 else 0, "errors": []}

    # Step 2: 遍历筛选后的联系人
    for idx, f in enumerate(friends):
        name = f.get("name", "?")
        brand = f.get("brandName", "")
        job = f.get("jobName", "")
        encrypt_id = f["encryptFriendId"]
        current = idx + 1
        label = f"{name} · {brand} · {job}" if brand and job else name
        yield _event("progress", phase="boss", message=f"[{current}/{len(friends)}] 正在同步: {label}", total=len(friends), current=current, boss_name=label)

        try:
            # 2a. Insert or update boss (不覆盖手动字段)
            conn.execute(
                """
                INSERT OR IGNORE INTO bosses (encrypt_boss_id, boss_id, name, update_time)
                VALUES (?, ?, ?, ?)
                """,
                (encrypt_id, f["friendId"], name, f.get("updateTime", 0)),
            )
            conn.execute(
                """
                UPDATE bosses SET
                    brand_name = ?, job_name = ?, position_name = ?, job_city = ?,
                    location_name = ?, job_type_desc = ?, update_time = MAX(update_time, ?),
                    updated_at = datetime('now', 'localtime')
                WHERE encrypt_boss_id = ?
                """,
                (
                    f.get("brandName", ""),
                    f.get("jobName", ""),
                    f.get("positionName", ""),
                    f.get("jobCity", ""),
                    "",
                    f.get("jobTypeDesc", ""),
                    f.get("updateTime", 0),
                    encrypt_id,
                ),
            )

            # 2b. 获取岗位信息 + 下载头像（顺便拿 securityId，避免重复请求）
            friend_id = f["friendId"]
            security_id = ""
            try:
                result = await boss_api.fetch_job_data(encrypt_id)
                job = result["job"]
                tiny_url = result["tinyUrl"]
                security_id = result.get("securityId", "")
                if not security_id:
                    logger.warning(f"未获取到 {name} 的 securityId，无法拉取聊天记录")
                conn.execute(
                    """
                    UPDATE bosses SET
                        boss_title = ?, location_name = ?, salary_desc = ?,
                        has_interview = CASE WHEN ? = 1 THEN 1 ELSE has_interview END,
                        updated_at = datetime('now', 'localtime')
                    WHERE encrypt_boss_id = ?
                    """,
                    (
                        result.get("title", ""),
                        job.get("locationName", ""),
                        job.get("salaryDesc", ""),
                        1 if job.get("hasInterview") else 0,
                        encrypt_id,
                    ),
                )
                # 下载头像
                if tiny_url:
                    avatar_filename = await boss_api.download_avatar(tiny_url, friend_id, AVATAR_DIR)
                    conn.execute(
                        "UPDATE bosses SET avatar_url = ? WHERE encrypt_boss_id = ?",
                        (avatar_filename, encrypt_id),
                    )
            except Exception as e:
                logger.warning(f"岗位信息获取失败 ({name}): {e}")
                stats["errors"].append(f"岗位信息({name}): {e}")

            # 2c. 获取聊天记录（分页）
            new_count = 0
            total_msgs = 0
            page_num = 0
            try:
                if not security_id:
                    raise ValueError("无 securityId")
                max_msg_id = 0
                while True:
                    page_num += 1
                    result = await boss_api.fetch_messages(encrypt_id, security_id, max_msg_id)
                    page_msgs = result["messages"]
                    total_msgs += len(page_msgs)

                    has_new = False
                    for msg in page_msgs:
                        # 跳过超出天数范围的消息
                        msg_time = msg.get("time", 0)
                        if cutoff and msg_time < cutoff:
                            continue
                        has_new = True

                        body = msg.get("body", {}) or {}
                        body_type = body.get("type", 0)
                        if body_type not in ALLOWED_BODY_TYPES:
                            continue

                        try:
                            body_content = ""

                            # 标记简历相关的判断
                            mark_resume = False

                            if body_type == 1:
                                body_content = body.get("text", "")
                                if body_content == "对方已查看了您的附件简历":
                                    mark_resume = True
                            elif body_type in (3, 14):
                                interview = body.get("interview", {}) or {}
                                body_content = interview.get("text", "")
                            elif body_type == 7:
                                dialog = body.get("dialog", {}) or {}
                                body_content = dialog.get("input", "")
                            elif body_type == 12:
                                hyperlink = body.get("hyperLink", {}) or {}
                                body_content = hyperlink.get("text", "")
                                if re.match(r"^您的附件简历", body_content) and re.search(r"已发送给Boss点击查看附件$", body_content):
                                    mark_resume = True

                            # 统一标记简历已发送
                            if mark_resume:
                                conn.execute(
                                    "UPDATE bosses SET is_resume_sent = 1, send_resume_datetime = COALESCE(send_resume_datetime, ?) WHERE encrypt_boss_id = ?",
                                    (msg_time, encrypt_id),
                                )
                            elif body_type == 20:
                                sticker = body.get("sticker", {}) or {}
                                img = sticker.get("image", {}) or {}
                                origin = img.get("originImage", {}) or {}
                                img_url = origin.get("url", "")
                                if img_url:
                                    body_content = await boss_api.download_image_as_base64(img_url)
                                else:
                                    body_content = json.dumps(sticker, ensure_ascii=False)

                            from_info = msg.get("from", {}) or {}
                            to_info = msg.get("to", {}) or {}
                            side = "left" if from_info.get("uid") == friend_id else "right"

                            mid = msg.get("mid", 0)
                            if not mid:
                                continue
                            conn.execute(
                                """
                                INSERT OR IGNORE INTO chat_messages
                                    (id, encrypt_boss_id, received, body_type, body_content,
                                     push_text, side, status, time, from_name, to_name)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    mid,
                                    encrypt_id,
                                    1 if msg.get("received") else 0,
                                    body_type,
                                    body_content,
                                    msg.get("pushText", ""),
                                    side,
                                    msg.get("status", 0),
                                    msg_time,
                                    from_info.get("name", ""),
                                    to_info.get("name", ""),
                                ),
                            )
                            changed = conn.execute("SELECT changes()").fetchone()[0]
                            if changed:
                                new_count += 1
                        except Exception:
                            pass

                    # 若当前页全部超出范围，停止分页
                    if cutoff and not has_new:
                        break
                    if not result["hasMore"]:
                        break
                    max_msg_id = result["minMsgId"]
                    await asyncio.sleep(0.2)

                stats["new_messages"] += new_count
                # 更新首次/末次聊天时间
                if total_msgs > 0:
                    conn.execute(
                        """
                        UPDATE bosses SET
                            first_msg_time = (SELECT MIN(time) FROM chat_messages WHERE encrypt_boss_id = ?),
                            last_msg_time  = (SELECT MAX(time) FROM chat_messages WHERE encrypt_boss_id = ?)
                        WHERE encrypt_boss_id = ?
                        """,
                        (encrypt_id, encrypt_id, encrypt_id),
                    )
                if cutoff and total_msgs > 0 and new_count == 0:
                    stats["skipped_bosses"] += 1
                if page_num > 1:
                    logger.info(f"  └─ 分 {page_num} 页获取, 共 {total_msgs} 条, 新增 {new_count} 条")
                else:
                    logger.info(f"  └─ 共 {total_msgs} 条, 新增 {new_count} 条")
            except Exception as e:
                logger.warning(f"聊天记录获取失败 ({name}): {e}")
                stats["errors"].append(f"聊天记录({name}): {e}")

            stats["friends"] += 1
            yield _event("boss_done", boss_name=label, new_messages=new_count)

            await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"同步 {name} 失败: {e}")
            stats["errors"].append(f"联系人 {name}: {e}")

    conn.commit()

    # 写同步日志
    conn.execute(
        """INSERT INTO sync_logs (sync_days, friends, new_messages, skipped, errors)
           VALUES (?, ?, ?, ?, ?)""",
        (sync_days, stats["friends"], stats["new_messages"], stats["skipped_bosses"],
         "; ".join(stats["errors"]) if stats["errors"] else ""),
    )
    conn.commit()
    conn.close()

    logger.info(f"同步完成 — 联系人: {stats['friends']}, 新消息: {stats['new_messages']}, 跳过: {stats['skipped_bosses']}, 错误: {len(stats['errors'])}")
    yield _event("done", **stats)
