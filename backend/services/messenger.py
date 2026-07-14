"""
Playwright 自动发送 BOSS 消息。参考 geekgeekrun:
- 不使用 persistent context，每次 launch + add_cookies 注入
- Cookie 存为 JSON 文件（与 EditThisCookie 兼容）
"""
import asyncio
import json
import logging
import os
import random
from pathlib import Path
from playwright.async_api import async_playwright, Page

logger = logging.getLogger("messenger")

GEEK_CHAT_URL = "https://www.zhipin.com/web/geek/chat?ka=header-message"
COOKIE_FILE = os.path.join(Path(__file__).parent.parent.parent, "cookies.json")
STORAGE_FILE = os.path.join(Path(__file__).parent.parent.parent, "boss-local-storage.json")

# 反检测脚本（对抗 BOSS 的 disable-devtool）
ANTI_DETECT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
window.chrome = { runtime: {} };
const __noop = () => {};
const __methods = ['log','info','debug','warn','error','table','clear','time','timeEnd','timeLog','group'];
__methods.forEach(m => {
    const __orig = console[m];
    console[m] = function(...args) {
        const short = args.map(a => {
            if (a === null || a === undefined) return String(a);
            if (typeof a === 'string') return a.length > 200 ? a.slice(0,200) : a;
            return '[' + (a.constructor?.name || typeof a) + ']';
        });
        return __orig.apply(console, short);
    };
});
const __origToString = Function.prototype.toString;
Function.prototype.toString = function() {
    if (__methods.includes(this.name)) return 'function ' + (this.name || '') + '() { [native code] }';
    return __origToString.call(this);
};
const __origBack = history.back; history.back = __noop;
const __origForward = history.forward; history.forward = __noop;
history.go = (n) => { if (n >= 0) __origForward.call(history); };
"""

# 延迟（毫秒）
TYPING_GAP = (38, 125)
CLICK_DELAY = (45, 160)
SEND_WAIT = (260, 920)
SCROLL_WAIT = (300, 800)
CHAT_OPEN_WAIT = (800, 2000)
BETWEEN_BOSS_WAIT = (600, 1500)


def _rand(a: int, b: int) -> int:
    return random.randint(a, b)


async def _sleep(a: int, b: int):
    await asyncio.sleep(_rand(a, b) / 1000)


# ── Cookie 管理 ──────────────────────────────────────────────

def _load_cookies() -> list[dict] | None:
    if not os.path.exists(COOKIE_FILE):
        return None
    with open(COOKIE_FILE) as f:
        return json.load(f)


def _save_cookies(cookies: list[dict]):
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)


def _normalize(raw: list[dict]) -> list[dict]:
    """EditThisCookie → Playwright 格式"""
    result = []
    for c in raw:
        expires = -1 if c.get("session", False) or "expirationDate" not in c else int(c["expirationDate"])
        same = str(c.get("sameSite", "")).lower()
        if same in ("no_restriction", "unspecified", ""):
            same = "None"
        elif same == "lax":
            same = "Lax"
        else:
            same = "Strict"
        result.append({
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ".zhipin.com"),
            "path": c.get("path", "/"),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": same,
            "expires": expires,
        })
    return result


def _load_storage() -> str | None:
    if not os.path.exists(STORAGE_FILE):
        return None
    with open(STORAGE_FILE) as f:
        return f.read()


def _save_storage(data: str):
    with open(STORAGE_FILE, "w") as f:
        f.write(data)


# ── 浏览器 ──────────────────────────────────────────────────

async def _launch():
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )
    ctx = await browser.new_context(viewport={"width": 1440, "height": 760})

    # 注入 cookie + localStorage
    cookies = _load_cookies()
    if cookies:
        await ctx.add_cookies(_normalize(cookies))
        logger.info(f"已注入 {len(cookies)} 个 Cookie")
    else:
        logger.warning("未找到 cookies.json，请先登录或导入")

    page = await ctx.new_page()
    await page.add_init_script(ANTI_DETECT_SCRIPT)
    # 注入 localStorage
    storage = _load_storage()
    if storage:
        await page.goto("https://www.zhipin.com", wait_until="domcontentloaded")
        await page.evaluate("(data) => { for (const [k, v] of Object.entries(JSON.parse(data))) { try { window.localStorage.setItem(k, v) } catch(e) {} } }", storage)
        logger.info("已注入 localStorage")
    else:
        await page.goto(GEEK_CHAT_URL, wait_until="domcontentloaded")

    return p, browser, ctx, page


# ── 聊天操作 ─────────────────────────────────────────────────

async def _ensure_list_page(page: Page):
    """确保在聊天列表页，如果不在则导航过去"""
    current = page.url
    if "/web/geek/chat" not in current or "chat/index" in current:
        return  # 已经在列表页
    await page.goto(GEEK_CHAT_URL, wait_until="domcontentloaded")


async def _find_and_click(page: Page, boss_name: str, skip_nav: bool = False) -> bool:
    if not skip_nav:
        await _ensure_list_page(page)
    await page.wait_for_selector(".chat-content", timeout=15000)
    await _sleep(500, 1000)

    stuck_count = 0

    for _ in range(80):
        # 搜索当前视口内所有已渲染的列表项
        found = await page.evaluate("""(name) => {
            const items = document.querySelectorAll(".chat-content .friend-content");
            for (const item of items) {
                const el = item.querySelector(".title-box .name-box .name-text");
                if (el && el.textContent.trim() === name) {
                    item.scrollIntoView({ block: "center" });
                    item.click();
                    return true;
                }
            }
            return false;
        }""", boss_name)
        if found:
            await _sleep(*CHAT_OPEN_WAIT)
            return True

        # 记录滚动前状态
        prev_scroll = await page.evaluate(
            "document.querySelector('.chat-content')?.scrollTop || 0"
        )
        prev_count = await page.evaluate(
            "document.querySelectorAll('.chat-content .friend-content').length"
        )

        # 滚动一屏
        await page.evaluate("document.querySelector('.chat-content')?.scrollBy(0, 600)")
        await _sleep(*SCROLL_WAIT)

        # 等待新节点渲染（最多等 1s）
        for _ in range(5):
            await _sleep(100, 200)
            curr_count = await page.evaluate(
                "document.querySelectorAll('.chat-content .friend-content').length"
            )
            if curr_count > prev_count:
                break

        curr_scroll = await page.evaluate(
            "document.querySelector('.chat-content')?.scrollTop || 0"
        )

        # 滚动位置和节点数都不变 → 到底了
        if curr_scroll == prev_scroll and curr_count == prev_count:
            stuck_count += 1
            if stuck_count >= 2:
                break
        else:
            stuck_count = 0

    return False


async def _back_to_list(page: Page):
    """从聊天详情页返回列表页"""
    await page.evaluate("document.querySelector('.chat-header-back')?.click()")
    await _sleep(300, 600)
    await page.wait_for_selector(".chat-content", timeout=10000)


async def _type_message(page: Page, message: str):
    """逐字输入消息并回车发送"""
    el = await page.query_selector("#chat-input")
    if el:
        await el.click(delay=_rand(*CLICK_DELAY))
    await _sleep(60, 220)
    await page.keyboard.press("Control+a")
    await _sleep(45, 180)
    await page.keyboard.press("Backspace")
    await _sleep(80, 260)
    for i, ch in enumerate(message):
        await page.keyboard.type(ch, delay=0)
        if i < len(message) - 1:
            await asyncio.sleep(_rand(*TYPING_GAP) / 1000)
    await _sleep(120, 420)
    await page.keyboard.press("Enter")


async def _check_send_status(page: Page) -> bool:
    """检测 DOM 中的发送状态。True=发送成功，False=发送失败"""
    try:
        await asyncio.sleep(0.5)

        # 先检查是否有错误标记
        has_error = await page.evaluate("""() => {
            const el = document.querySelector('.friend-content.selected .last-msg');
            if (!el) return false;
            return !!el.querySelector('.status-error');
        }""")
        if has_error:
            logger.warning("检测到 .status-error，发送失败")
            return False

        # 轮询等待 loading 消失（最多 5s）
        for _ in range(17):  # ~17 * 0.3s ≈ 5.1s
            still_loading = await page.evaluate("""() => {
                const el = document.querySelector('.friend-content.selected .last-msg');
                if (!el) return false;
                return !!el.querySelector('.status-loading');
            }""")
            if not still_loading:
                # loading 消失后再检查一次 error
                has_error = await page.evaluate("""() => {
                    const el = document.querySelector('.friend-content.selected .last-msg');
                    if (!el) return false;
                    return !!el.querySelector('.status-error');
                }""")
                if has_error:
                    logger.warning("发送完成后出现 .status-error")
                    return False
                return True
            await asyncio.sleep(0.3)

        # 超过 5s 仍在 loading
        logger.warning("status-loading 超过 5s 未消失，判定发送失败")
        return False
    except Exception as e:
        logger.warning(f"检查发送状态异常: {e}")
        return True  # 无法检测时假定成功，避免重复发送


async def _send_one(page: Page, name: str, message: str) -> dict:
    await page.wait_for_selector("#chat-input", timeout=10000)
    await _sleep(300, 500)

    await _type_message(page, message)

    success = await _check_send_status(page)
    if not success:
        logger.warning(f"消息发送给 {name} 状态异常，重试中...")
        await _sleep(600, 1200)
        await _type_message(page, message)
        success = await _check_send_status(page)
        if success:
            logger.info(f"消息已发送给 {name}（重试成功）")
            return {"name": name, "success": True, "retried": True}
        else:
            logger.error(f"消息发送给 {name} 失败（已重试1次仍失败）")
            return {"name": name, "success": False, "error": "发送状态异常，已重试1次仍失败"}

    logger.info(f"消息已发送给 {name}")
    return {"name": name, "success": True}


# ── 失败记录 ────────────────────────────────────────────────

def _record_failed(boss_name: str, message: str, error: str, encrypt_boss_id: str = None):
    """将发送失败的消息写入数据库队列"""
    try:
        from ..database import get_db
        conn = get_db()
        conn.execute(
            """INSERT INTO message_failed_queue (boss_name, encrypt_boss_id, message, error)
               VALUES (?, ?, ?, ?)""",
            (boss_name, encrypt_boss_id or "", message, error),
        )
        conn.commit()
        conn.close()
        logger.info(f"已记录失败队列: {boss_name} — {error}")
    except Exception as e:
        logger.error(f"记录失败队列异常: {e}")


def _record_results(results: list[dict], items: list[dict]):
    """根据发送结果，将失败的条目写入队列"""
    # 构建 name -> item 的映射（找 encrypt_boss_id）
    item_map = {}
    for item in items:
        item_map[item.get("name", "")] = item

    for r in results:
        if not r.get("success"):
            name = r.get("name", "")
            item = item_map.get(name, {})
            _record_failed(
                boss_name=name,
                message=item.get("message", ""),
                error=r.get("error", "未知错误"),
                encrypt_boss_id=item.get("encrypt_boss_id", ""),
            )


# ── 公开 API ─────────────────────────────────────────────────

async def check_login_status() -> dict:
    p = browser = ctx = None
    try:
        cookies = _load_cookies()
        if not cookies:
            return {"valid": False, "message": "未导入 Cookie 或未登录"}
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        await ctx.add_cookies(_normalize(cookies))
        page = await ctx.new_page()
        resp = await page.goto(
            "https://www.zhipin.com/wapi/zprelation/friend/geekFilterByLabel"
            "?labelId=0&name=全部&encryptSystemId=8cee15b718bda27e0Hx6",
            wait_until="domcontentloaded",
        )
        body = await page.evaluate("document.body.innerText")
        data = json.loads(body) if body else {}
        if data.get("code") == 0:
            return {"valid": True, "message": "Cookie 有效"}
        return {"valid": False, "message": f"API 返回: code={data.get('code')}, msg={data.get('message')}"}
    except Exception as e:
        return {"valid": False, "message": str(e)}
    finally:
        if ctx: await ctx.close()
        if browser: await browser.close()
        if p: await p.stop()


def _sync_cookie_to_db(cookies: list[dict]):
    """将 Playwright cookie 数组转为原始字符串存入 config 表（供 httpx 同步使用）"""
    from ..database import get_db
    parts = []
    for c in cookies:
        parts.append(f"{c['name']}={c['value']}")
    cookie_str = "; ".join(parts)
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('cookie', ?)", (cookie_str,))
    conn.commit()
    conn.close()
    logger.info(f"已将 {len(cookies)} 个 Cookie 同步到数据库")


async def login_and_capture() -> dict:
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )
    ctx = await browser.new_context(viewport={"width": 1440, "height": 860})
    page = await ctx.new_page()
    await page.add_init_script(ANTI_DETECT_SCRIPT)
    await page.goto("https://www.zhipin.com/web/user/", wait_until="domcontentloaded")

    try:
        await asyncio.wait_for(
            page.wait_for_url("**/web/geek/**", timeout=0),
            timeout=300000,
        )
        await asyncio.sleep(2)
        cookies = await ctx.cookies()
        _save_cookies(cookies)
        _sync_cookie_to_db(cookies)
        # 同时保存 localStorage
        storage = await page.evaluate("JSON.stringify(window.localStorage)")
        _save_storage(storage)
        logger.info(f"已保存 {len(cookies)} 个 Cookie + localStorage")
        return {"success": True, "message": f"登录成功，已保存 {len(cookies)} 个 Cookie + localStorage"}
    except asyncio.TimeoutError:
        return {"success": False, "message": "登录超时（5 分钟）"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        await ctx.close()
        await browser.close()
        await p.stop()


async def import_cookies_from_json(raw: list[dict]) -> dict:
    normalized = _normalize(raw)
    _save_cookies(normalized)
    _sync_cookie_to_db(normalized)
    logger.info(f"已导入 {len(normalized)} 个 Cookie")
    return {"ok": True, "count": len(normalized)}


async def send_to_boss(boss_name: str, message: str) -> dict:
    try:
        p, browser, ctx, page = await _launch()
        if not await _find_and_click(page, boss_name):
            result = {"success": False, "error": f"未在聊天列表中找到 {boss_name}"}
            _record_failed(boss_name, message, result["error"])
            return result
        result = await _send_one(page, boss_name, message)
        if not result.get("success"):
            _record_failed(boss_name, message, result.get("error", "发送失败"))
        return result
    except Exception as e:
        _record_failed(boss_name, message, str(e))
        return {"success": False, "error": str(e)}
    # 不关闭浏览器，用户手动关闭


async def send_batch_items(items: list[dict]) -> dict:
    """批量发送，每个 BOSS 独立消息。发送完不关闭浏览器，用户手动关。"""
    results = []
    try:
        p, browser, ctx, page = await _launch()
        await _ensure_list_page(page)
        await _sleep(500, 800)

        for idx, item in enumerate(items):
            name = item["name"]
            msg = item["message"]
            try:
                if not await _find_and_click(page, name, skip_nav=True):
                    results.append({"name": name, "success": False, "error": "未找到"})
                    continue
                result = await _send_one(page, name, msg)
                results.append(result)
                logger.info(f"已发送: {name} ({idx + 1}/{len(items)})")
            except Exception as e:
                results.append({"name": name, "success": False, "error": str(e)})

        return {"results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        _record_results(results, items)
    # 不关闭浏览器，用户手动关闭


async def send_batch(boss_names: list[str], message: str) -> dict:
    """批量发送：左边列表始终存在，依次点击→发送→下一个，无需返回"""
    results = []
    p = browser = ctx = None
    try:
        p, browser, ctx, page = await _launch()
        # 导航到列表页（仅一次）
        await _ensure_list_page(page)
        await _sleep(500, 800)

        for idx, name in enumerate(boss_names):
            try:
                if not await _find_and_click(page, name, skip_nav=True):
                    results.append({"name": name, "success": False, "error": "未找到"})
                    continue
                result = await _send_one(page, name, message)
                results.append(result)
                logger.info(f"已发送: {name} ({idx + 1}/{len(boss_names)})")
                # 不需要返回，左边列表一直可见，直接点下一个
            except Exception as e:
                results.append({"name": name, "success": False, "error": str(e)})

        return {"results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        _items = [{"name": n, "message": message} for n in boss_names]
        _record_results(results, _items)
