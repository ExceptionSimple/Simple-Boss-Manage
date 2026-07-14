"""消息提醒模块"""
import logging
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from ..database import get_db
from ..services.msg_generator import generate_message

logger = logging.getLogger("reminders")
router = APIRouter()


@router.get("/reminders")
def list_reminders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """列出待提醒的 BOSS：最近一条消息是我方发送"""
    conn = get_db()
    offset = (page - 1) * size

    # 子查询：每个 boss 的最后一条消息
    total_row = conn.execute("""
        SELECT COUNT(DISTINCT b.encrypt_boss_id) as cnt
        FROM bosses b
        INNER JOIN chat_messages cm ON cm.id = (
            SELECT id FROM chat_messages
            WHERE encrypt_boss_id = b.encrypt_boss_id
            ORDER BY time DESC LIMIT 1
        )
        WHERE cm.side = 'right'
    """).fetchone()
    total = total_row["cnt"] if total_row else 0

    rows = conn.execute("""
        SELECT b.*,
            j.name as job_name, j.city as job_city, j.salary_desc,
            j.position_name, j.job_type_desc,
            cm.push_text AS last_msg_text,
            cm.status AS last_msg_status,
            cm.time AS last_msg_time,
            (SELECT COUNT(*) FROM chat_messages
             WHERE encrypt_boss_id = b.encrypt_boss_id AND side = 'right'
               AND time > COALESCE(
                 (SELECT MAX(time) FROM chat_messages WHERE encrypt_boss_id = b.encrypt_boss_id AND side = 'left'), 0)
            ) AS unanswered_count
        FROM bosses b
        LEFT JOIN job_info j ON b.job_id = j.id
        INNER JOIN chat_messages cm ON cm.id = (
            SELECT id FROM chat_messages
            WHERE encrypt_boss_id = b.encrypt_boss_id
            ORDER BY time DESC LIMIT 1
        )
        WHERE cm.side = 'right'
        ORDER BY unanswered_count DESC, cm.time DESC
        LIMIT ? OFFSET ?
    """, (size, offset)).fetchall()
    conn.close()

    items = []
    for r in rows:
        d = dict(r)
        d["last_msg_preview"] = (r["last_msg_text"] or "")[:50]
        items.append(d)

    return {"total": total, "page": page, "size": size, "items": items}


class PreviewBody(BaseModel):
    encrypt_boss_ids: list[str]


@router.post("/reminders/preview")
async def preview_messages(body: PreviewBody):
    """为选中的 BOSS 生成消息预览"""
    conn = get_db()
    results = []
    for eid in body.encrypt_boss_ids:
        boss = conn.execute(
            "SELECT name, boss_title FROM bosses WHERE encrypt_boss_id = ?", (eid,)
        ).fetchone()
        if not boss:
            continue
        msg = await generate_message(name=boss["name"] or "", boss_title=boss["boss_title"] or "")
        results.append({
            "encrypt_boss_id": eid,
            "name": boss["name"],
            "boss_title": boss["boss_title"],
            "message": msg,
        })
    conn.close()
    return {"items": results}


class SendBody(BaseModel):
    encrypt_boss_ids: list[str]


class SendMessagesBody(BaseModel):
    items: list[dict]  # [{name, message}, ...]


@router.post("/reminders/send")
async def send_reminders(body: SendBody):
    """发送提醒消息（后端生成内容）"""
    conn = get_db()
    names = []
    for eid in body.encrypt_boss_ids:
        boss = conn.execute("SELECT name, boss_title FROM bosses WHERE encrypt_boss_id = ?", (eid,)).fetchone()
        if boss:
            msg = await generate_message(name=boss["name"] or "", boss_title=boss["boss_title"] or "")
            names.append({"name": boss["name"], "message": msg})
    conn.close()

    from ..services.messenger import send_batch_items
    results = await send_batch_items(names)
    return results


@router.post("/reminders/send-messages")
async def send_reminders_with_messages(body: SendMessagesBody):
    """发送提醒消息（发送完浏览器保持打开，用户手动关闭）"""
    from ..services.messenger import send_batch_items
    results = await send_batch_items(body.items)
    return results


# ── 失败队列 ──────────────────────────────────────────────────


@router.get("/reminders/failed-queue")
def list_failed_queue():
    """获取发送失败队列"""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM message_failed_queue
           ORDER BY created_at DESC"""
    ).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}


class FailedQueueRetryBody(BaseModel):
    ids: list[int]  # 要重试的队列记录 ID（空列表=全部）


@router.post("/reminders/failed-queue/retry")
async def retry_failed_queue(body: FailedQueueRetryBody):
    """重试失败队列中的消息"""
    conn = get_db()
    if body.ids:
        placeholders = ",".join("?" for _ in body.ids)
        rows = conn.execute(
            f"SELECT * FROM message_failed_queue WHERE id IN ({placeholders}) ORDER BY created_at",
            body.ids,
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM message_failed_queue ORDER BY created_at"
        ).fetchall()
    conn.close()

    if not rows:
        return {"ok": True, "results": [], "message": "队列为空"}

    items = [{"name": r["boss_name"], "message": r["message"]} for r in rows]
    retry_ids = [r["id"] for r in rows]

    from ..services.messenger import send_batch_items
    results = await send_batch_items(items)

    # 删除重试成功的记录
    succeeded_names = {r["name"] for r in results.get("results", []) if r.get("success")}
    if succeeded_names:
        conn2 = get_db()
        for row in rows:
            if row["boss_name"] in succeeded_names:
                conn2.execute("DELETE FROM message_failed_queue WHERE id = ?", (row["id"],))
                logger.info(f"失败队列重试成功，已移除: {row['boss_name']}")
            else:
                # 更新重试次数
                conn2.execute(
                    "UPDATE message_failed_queue SET retry_count = retry_count + 1 WHERE id = ?",
                    (row["id"],),
                )
        conn2.commit()
        conn2.close()

    return results


class FailedQueueDeleteBody(BaseModel):
    ids: list[int]


@router.delete("/reminders/failed-queue")
def delete_failed_queue(body: Optional[FailedQueueDeleteBody] = None):
    """删除失败队列记录（空 body 或空 ids = 清空全部）"""
    conn = get_db()
    if body and body.ids:
        placeholders = ",".join("?" for _ in body.ids)
        conn.execute(
            f"DELETE FROM message_failed_queue WHERE id IN ({placeholders})",
            body.ids,
        )
    else:
        conn.execute("DELETE FROM message_failed_queue")
    deleted = conn.total_changes
    conn.commit()
    conn.close()
    return {"ok": True, "deleted": deleted}
