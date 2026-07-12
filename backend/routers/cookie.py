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
