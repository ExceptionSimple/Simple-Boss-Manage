import logging
from fastapi import APIRouter
from pydantic import BaseModel
from ..database import get_db

logger = logging.getLogger("cookie")
router = APIRouter()


class CookieBody(BaseModel):
    cookie: str


class CookieStatus(BaseModel):
    configured: bool
    cookie_preview: str = ""


@router.put("/cookie")
def save_cookie(body: CookieBody):
    cookie = body.cookie.strip()
    logger.info(f"保存 Cookie, 长度={len(cookie)}")
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES ('cookie', ?)",
        (cookie,),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/cookie/status", response_model=CookieStatus)
def cookie_status():
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key='cookie'").fetchone()
    conn.close()
    if not row or not row["value"]:
        logger.info("Cookie 状态: 未配置")
        return {"configured": False, "cookie_preview": ""}
    cookie = row["value"]
    preview = cookie[:30] + "..." if len(cookie) > 30 else cookie
    logger.info(f"Cookie 状态: 已配置 ({preview})")
    return {"configured": True, "cookie_preview": preview}


class ConfigBody(BaseModel):
    sync_days: int = 0  # 0 = 全部


@router.get("/config")
def get_config():
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key='sync_days'").fetchone()
    conn.close()
    return {"sync_days": int(row["value"]) if row else 0}


@router.get("/cookie/verify")
def verify_cookie():
    """发一个真实请求验证 Cookie 是否有效"""
    import httpx
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key='cookie'").fetchone()
    conn.close()
    if not row or not row["value"]:
        return {"valid": False, "message": "未配置 Cookie"}

    cookie = row["value"]
    try:
        resp = httpx.get(
            "https://www.zhipin.com/wapi/zprelation/friend/geekFilterByLabel",
            params={"labelId": 0, "name": "全部", "encryptSystemId": "8cee15b718bda27e0Hx6"},
            headers={
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.zhipin.com/web/chat/",
            },
            timeout=10,
            follow_redirects=False,
        )
        if resp.status_code == 302:
            return {"valid": False, "message": "Cookie 已失效（被重定向到登录页）"}
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                return {"valid": True, "message": "Cookie 有效"}
            return {"valid": False, "message": f"API 返回异常: code={data.get('code')}, message={data.get('message')}"}
        return {"valid": False, "message": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"valid": False, "message": str(e)}


@router.put("/config")
def update_config(body: ConfigBody):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES ('sync_days', ?)",
        (str(body.sync_days),),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "sync_days": body.sync_days}
