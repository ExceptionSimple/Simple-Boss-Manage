"""消息生成：支持固定模板和 AI 生成两种模式"""
import json
import logging
from ..routers.cookie import _cfg

logger = logging.getLogger("msg_generator")


def render_template(template: str, name: str = "", boss_title: str = "") -> str:
    """替换模板中的变量占位符 {name} {boss_title}"""
    return template.replace("{name}", name or "").replace("{boss_title}", boss_title or "")


async def generate_ai_message(prompt: str, user_name: str, boss_title: str) -> str:
    """调用 AI API 生成消息"""
    import httpx
    api_key = _cfg("api_key") or ""
    api_base = (_cfg("api_base") or "").rstrip("/")

    if not api_key:
        raise ValueError("未配置 API_KEY，请在设置中配置")

    rendered = render_template(prompt, user_name, boss_title)

    url = f"{api_base}/chat/completions"
    body = {
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": "你是一个求职助手，帮用户生成给BOSS直聘招聘者的打招呼消息。消息要简洁、友好、专业。"},
            {"role": "user", "content": rendered},
        ],
        "temperature": 0.7,
        "max_tokens": 200,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            logger.error(f"AI API 错误: {resp.status_code} {resp.text}")
            raise RuntimeError(f"AI API 返回错误: {resp.status_code}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        logger.info(f"AI 生成消息成功")
        return content.strip()


async def generate_message(name: str = "", boss_title: str = "") -> str:
    """根据配置生成消息（固定模板或 AI）"""
    mode = _cfg("msg_mode") or "fixed"

    if mode == "ai":
        prompt = _cfg("ai_prompt") or f"请为{boss_title or 'HR'}{name or ''}写一段简短的打招呼消息"
        try:
            return await generate_ai_message(prompt, name, boss_title)
        except Exception as e:
            logger.warning(f"AI 生成失败，回退到固定模板: {e}")
            # AI 失败则回退到固定模板

    template = _cfg("msg_template") or "您好，{name}，我对贵司的岗位很感兴趣，方便聊聊吗？"
    return render_template(template, name, boss_title)
