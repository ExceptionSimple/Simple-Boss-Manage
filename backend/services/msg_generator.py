"""消息生成：支持固定模板和 AI 生成两种模式，每种模式有 3 套预设方案"""
import json
import logging
from openai import AsyncOpenAI
from ..routers.cookie import _cfg

logger = logging.getLogger("msg_generator")

SYSTEM_PROMPT = (
    "你是一个专业的求职助手，帮助用户在BOSS直聘平台上给招聘者发送消息。"
    "生成的消息要简洁、友好、专业，控制在100字以内。"
    "你必须使用中文回答，请勿使用英文。"
    "不需要任何的占位符，你所生成的消息必须可以直接发送给招聘者。而不是带占位符，让用户自己替换。"
    "生成纯文本，不要任何结构化输出。"
)

DEFAULT_FIXED = [
    "您好，{name}，我对贵司的岗位很感兴趣，方便聊聊吗？",
    "你好{name}，看到贵司在招{job_name}，我这边有相关经验，可以沟通一下吗？",
    "您好{name}，我之前做过类似岗位，对这个方向很感兴趣，希望能有机会面试。",
]
DEFAULT_AI = [
    "请为{boss_title or 'HR'}{name or ''}写一段简短的打招呼消息",
    "请为{boss_title or 'HR'}{name or ''}写一段突出技术能力的自荐消息",
    "请为{boss_title or 'HR'}{name or ''}写一段询问岗位详情的消息",
]


def _get_scheme_content(mode: str, index: int = 0) -> str:
    """获取指定模式和索引的方案内容"""
    schemes_raw = _cfg("msg_schemes") or ""
    if schemes_raw:
        try:
            schemes = json.loads(schemes_raw)
            return schemes.get(mode, [])[index] if index < len(schemes.get(mode, [])) else ""
        except (json.JSONDecodeError, KeyError):
            pass
    # 回退到旧版单模板
    if mode == "ai":
        return _cfg("ai_prompt") or DEFAULT_AI[index] if index < len(DEFAULT_AI) else DEFAULT_AI[0]
    return _cfg("msg_template") or DEFAULT_FIXED[index] if index < len(DEFAULT_FIXED) else DEFAULT_FIXED[0]


def render_template(template: str, name: str = "", boss_title: str = "") -> str:
    """替换模板中的变量占位符 {name} {boss_title}"""
    if not template:
        template = DEFAULT_FIXED[0]
    return template.replace("{name}", name or "").replace("{boss_title}", boss_title or "")


async def generate_ai_message(prompt: str, user_name: str, boss_title: str) -> str:
    """调用 DeepSeek API 生成消息（流式收集）"""
    api_key = _cfg("api_key") or ""
    api_base = (_cfg("api_base") or "").rstrip("/") or "https://api.deepseek.com"

    if not api_key:
        raise ValueError("未配置 API_KEY，请在设置中配置")

    rendered = render_template(prompt, user_name, boss_title)

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)
    stream = await client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": rendered},
        ],
        stream=True,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "disabled"}},
    )

    chunks = []
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            chunks.append(delta.content)

    content = "".join(chunks).strip()
    logger.info(f"AI 生成消息成功 ({len(content)} 字)")
    return content


async def generate_ai_message_stream(prompt: str, user_name: str, boss_title: str):
    """调用 DeepSeek API 生成消息（流式 yield）"""
    api_key = _cfg("api_key") or ""
    api_base = (_cfg("api_base") or "").rstrip("/") or "https://api.deepseek.com"

    if not api_key:
        raise ValueError("未配置 API_KEY，请在设置中配置")

    rendered = render_template(prompt, user_name, boss_title)

    client = AsyncOpenAI(api_key=api_key, base_url=api_base)
    stream = await client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": rendered},
        ],
        stream=True,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "disabled"}},
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


async def generate_message(name: str = "", boss_title: str = "", scheme_index: int = 0) -> str:
    """根据配置生成消息（固定模板或 AI），支持 3 套预设方案"""
    mode = _cfg("msg_mode") or "fixed"
    content = _get_scheme_content(mode, scheme_index)

    if mode == "ai":
        logger.info(f"使用 AI 模式（方案{scheme_index + 1}）：{content[:50]}...")
        try:
            return await generate_ai_message(content, name, boss_title)
        except Exception as e:
            logger.warning(f"AI 生成失败，回退到固定模板: {e}")

    return render_template(content, name, boss_title)
