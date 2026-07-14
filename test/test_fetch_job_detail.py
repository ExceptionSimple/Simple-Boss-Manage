"""测试 headless Playwright + 完整反检测 = 抓取岗位详情"""
import asyncio, json, os, sys
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

JOB_ID = "04df8629b2cd4b780nF92dy1ElZW"
COOKIE_FILE = os.path.join(os.path.dirname(__file__), "..", "cookies.json")

# 完整反检测脚本（来自 messenger.py）
ANTI_DETECT = """
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
const __origBack = history.back; history.back = __noop;
const __origForward = history.forward; history.forward = __noop;
history.go = (n) => { if (n >= 0) __origForward.call(history); };
"""


async def main():
    if not os.path.exists(COOKIE_FILE):
        print("错误: cookies.json 不存在，请先导出 Cookie")
        return

    with open(COOKIE_FILE) as f:
        raw = json.load(f)

    # Normalize cookies for Playwright
    normalized = []
    for c in raw:
        expires = -1 if c.get("session", False) or "expirationDate" not in c else int(c["expirationDate"])
        same = str(c.get("sameSite", "")).lower()
        if same in ("no_restriction", "unspecified", ""):
            same = "None"
        elif same == "lax":
            same = "Lax"
        else:
            same = "Strict"
        normalized.append({
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ".zhipin.com"),
            "path": c.get("path", "/"),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": same,
            "expires": expires,
        })

    url = f"https://www.zhipin.com/job_detail/{JOB_ID}.html"
    print(f"正在抓取: {url}\n")

    p = await async_playwright().start()
    try:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = await browser.new_context(viewport={"width": 1440, "height": 760})
        await ctx.add_cookies(normalized)
        page = await ctx.new_page()
        await page.add_init_script(ANTI_DETECT)

        # goto — 等 domcontentloaded 即可
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        print(f"初始 URL: {page.url}")

        # 如果是安全验证页，等它自动跳转（最多 30s），BOSS 验证通常几秒
        if "security" in page.url or "passport" in page.url:
            print("进入安全验证页，等待 JS 验证通过...")
            try:
                await page.wait_for_url("**/job_detail/**", timeout=30000)
                print("已跳回详情页")
            except Exception:
                print(f"30s 后仍未跳回，当前 URL: {page.url}")
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                print("页面标题:", soup.title.string if soup.title else "(无)")
                print("body 前300字:", soup.body.get_text()[:300] if soup.body else "(空)")
                return

        await asyncio.sleep(1)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        print(f"\n最终 URL: {page.url}")
        print(f"页面标题: {soup.title.string if soup.title else '(无)'}")

        # 解析
        print("\n" + "=" * 60)
        print("company_url")
        print("=" * 60)
        el = soup.select_one('a[ka="job-detail-company_custompage"]')
        if el and el.get("href"):
            href = el["href"]
            print(f"https://www.zhipin.com{href}" if href.startswith("/") else href)
        else:
            print("(未找到)")

        print()
        print("=" * 60)
        print("company_name")
        print("=" * 60)
        el = soup.select_one(".level-list-box .company-name")
        if el:
            for span in el.find_all("span"):
                span.decompose()
            print(el.get_text(strip=True))
        else:
            print("(未找到)")

        print()
        print("=" * 60)
        print("detail (前500字)")
        print("=" * 60)
        el = soup.select_one(".job-detail .job-sec-text")
        if el:
            for span in el.find_all("span"):
                span.decompose()
            print(el.get_text(" ", strip=True)[:500])
        else:
            print("(未找到)")
    finally:
        await browser.close()
        await p.stop()


if __name__ == "__main__":
    asyncio.run(main())
