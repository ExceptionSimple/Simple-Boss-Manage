import json
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from ..services.messenger import (
    send_to_boss, send_batch, login_and_capture,
    import_cookies_from_json, check_login_status,
)
from ..services.msg_generator import generate_message

logger = logging.getLogger("messenger")
router = APIRouter()


class SendSingleBody(BaseModel):
    boss_name: str
    message: str


class SendBatchBody(BaseModel):
    boss_names: list[str]
    message: str


class ImportCookiesBody(BaseModel):
    data: str  # JSON 字符串


@router.post("/messenger/login")
async def api_login():
    """打开浏览器登录页，等用户扫码登录，自动保存 cookie"""
    return await login_and_capture()


@router.get("/messenger/check-login")
async def api_check_login():
    """用 Playwright 验证 cookie 是否有效"""
    return await check_login_status()


@router.post("/messenger/import-cookies")
async def api_import_cookies(body: ImportCookiesBody):
    """粘贴 cookies JSON（EditThisCookie / Puppeteer 格式）"""
    cookies = json.loads(body.data)
    await import_cookies_from_json(cookies)
    return {"ok": True, "count": len(cookies)}


@router.post("/messenger/generate-message")
async def api_generate_message(body: dict):
    """根据配置生成消息（固定模板或 AI）"""
    name = body.get("name", "")
    boss_title = body.get("boss_title", "")
    message = await generate_message(name, boss_title)
    return {"message": message}


@router.post("/messenger/send")
async def api_send_single(body: SendSingleBody):
    return await send_to_boss(body.boss_name, body.message)


@router.post("/messenger/send-batch")
async def api_send_batch(body: SendBatchBody):
    return await send_batch(body.boss_names, body.message)
