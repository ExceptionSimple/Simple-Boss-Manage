import base64
import logging
import os
import httpx
from ..database import get_db

logger = logging.getLogger("boss_api")

# 绕过系统 SOCKS 代理
for key in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "http_proxy", "https_proxy"):
    os.environ.pop(key, None)

BOSS_BASE = "https://www.zhipin.com"


def _get_cookie() -> str:
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key='cookie'").fetchone()
    conn.close()
    if not row or not row["value"]:
        raise ValueError("Cookie 未配置，请先在设置页面保存 Cookie")
    return row["value"]


def _headers() -> dict:
    return {
        "Cookie": _get_cookie(),
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.zhipin.com/web/chat/",
    }


async def fetch_friend_list() -> list[dict]:
    """获取联系人列表"""
    url = (
        f"{BOSS_BASE}/wapi/zprelation/friend/geekFilterByLabel"
        "?labelId=0&name=全部&encryptSystemId=8cee15b718bda27e0Hx6"
    )
    logger.info("正在获取联系人列表...")
    async with httpx.AsyncClient(timeout=30, proxy=None) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取联系人失败: {data.get('message')}")
        friends = data["zpData"]["friendList"]
        logger.info(f"获取到 {len(friends)} 个联系人")
        return friends


async def fetch_job_data(encrypt_boss_id: str) -> dict:
    """获取岗位信息和头像 URL，返回 {job, tinyUrl}"""
    url = f"{BOSS_BASE}/wapi/zpchat/geek/getBossData"
    params = {"bossId": encrypt_boss_id, "bossSource": 0}
    async with httpx.AsyncClient(timeout=30, proxy=None) as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取岗位信息失败: {data.get('message')}")
        zp = data["zpData"]
        job = zp["job"]
        zp_data = zp.get("data", {}) or {}
        # encryptJobId 可能在 job / zpData 顶层 / zpData.data 中
        encrypt_job_id = (
            job.get("encryptJobId", "") or
            zp.get("encryptJobId", "") or
            zp_data.get("encryptJobId", "")
        )
        if not encrypt_job_id:
            logger.warning(f"未找到 encryptJobId (boss={encrypt_boss_id}), job keys: {list(job.keys())}, zpData keys: {list(zp.keys())}, data keys: {list(zp_data.keys())}")
        return {
            "job": job,
            "encryptJobId": encrypt_job_id,
            "companyName": zp_data.get("companyName", ""),
            "title": zp_data.get("title", ""),
            "tinyUrl": zp_data.get("tinyUrl", ""),
            "securityId": zp_data.get("securityId", ""),
        }


async def fetch_messages(encrypt_boss_id: str, security_id: str, max_msg_id: int = 0) -> dict:
    """获取聊天记录（单页），返回 {messages, hasMore, minMsgId}"""
    url = f"{BOSS_BASE}/wapi/zpchat/geek/historyMsg"
    params = {
        "bossId": encrypt_boss_id,
        "maxMsgId": max_msg_id,
        "c": 20,
        "page": 1,
        "src": 0,
        "securityId": security_id,
    }
    async with httpx.AsyncClient(timeout=30, proxy=None) as client:
        resp = await client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取聊天记录失败: {data.get('message')}")
        zp = data["zpData"]
        return {
            "messages": zp["messages"],
            "hasMore": zp.get("hasMore", False),
            "minMsgId": zp.get("minMsgId", 0),
        }


async def download_image_as_base64(url: str) -> str:
    """下载图片并返回 base64 编码字符串"""
    async with httpx.AsyncClient(timeout=15, proxy=None) as client:
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.zhipin.com/",
        })
        resp.raise_for_status()
        data = base64.b64encode(resp.content).decode()
        content_type = resp.headers.get("content-type", "image/png")
        return f"data:{content_type};base64,{data}"


async def download_avatar(tiny_url: str, friend_id: int, avatar_dir: str) -> str:
    """下载头像到本地，返回文件名 friendId.jpg。已存在则跳过。"""
    import os
    filename = f"{friend_id}.jpg"
    filepath = os.path.join(avatar_dir, filename)
    if os.path.exists(filepath):
        return filename
    os.makedirs(avatar_dir, exist_ok=True)
    async with httpx.AsyncClient(timeout=15, proxy=None) as client:
        resp = await client.get(tiny_url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.zhipin.com/",
        })
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        logger.info(f"头像已保存: {filename}")
        return filename


