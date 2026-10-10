# -*- coding: utf-8 -*-
"""T01724 全路由 UI 一致性采集（整页加载方案，绕开 SPA 内导航冻结问题）"""
import json, sys, io
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8010"
ROUTES = [
    "/", "/tasks", "/tasks/new", "/items", "/orders", "/evaluations",
    "/timeline", "/logs", "/logs/errors", "/notifications", "/price-dashboard",
    "/config/price", "/config/eval", "/config/buyer", "/config/search",
    "/config/notifier", "/config/ai", "/config/chatbot", "/config/version",
    "/maintenance", "/maintenance/db", "/maintenance/vector", "/maintenance/tunnel",
    "/batch-refresh", "/anticrawl", "/chatbot", "/export", "/menu-admin",
]

METRICS_JS = """
() => {
  const vis = (el) => el && el.offsetParent !== null;
  const txt = (sel) => [...document.querySelectorAll(sel)].filter(vis).map(e => (e.textContent||'').trim()).filter(Boolean);
  const inlineStyled = [...document.querySelectorAll('[style]')].filter(vis);
  const btns = [...document.querySelectorAll('button')].filter(vis);
  const headings = [...document.querySelectorAll('h1,h2,h3,h4')].filter(vis)
      .map(h => ({tag: h.tagName, text: (h.textContent||'').trim().slice(0, 40)}));
  // 硬编码样式探测（内联 fontSize / 颜色字面量）
  const hardcoded = inlineStyled.filter(el => {
    const s = el.getAttribute('style') || '';
    return /fontSize\\s*:/.test(s) || /#[0-9a-fA-F]{3,8}\\b/.test(s) || /rgb\\(/.test(s);
  }).length;
  const inputs = [...document.querySelectorAll('input,textarea')].filter(vis).length;
  const cards = [...document.querySelectorAll('.ant-card')].filter(vis).length;
  return {
    url: location.pathname,
    ready: document.readyState,
    bodyChars: (document.body.innerText||'').length,
    contentH: (document.querySelector('.ant-layout-content, main')||{}).clientHeight || 0,
    headings,
    h1h2: headings.filter(h => ['H1','H2'].includes(h.tag)).map(h => h.tag + ':' + h.text),
    cards, tables: [...document.querySelectorAll('.ant-table')].filter(vis).length,
    forms: [...document.querySelectorAll('form,.ant-form')].filter(vis).length,
    inputs, buttons: btns.length,
    primaryBtns: btns.filter(b => b.querySelector('.ant-btn-primary') || b.className.includes('ant-btn-primary')).length,
    empty: [...document.querySelectorAll('.ant-empty')].filter(vis).length,
    spin: [...document.querySelectorAll('.ant-spin-spinning')].filter(vis).length,
    alerts: [...document.querySelectorAll('.ant-alert')].filter(vis).length,
    modals: [...document.querySelectorAll('.ant-modal-wrap')].filter(vis).length,
    inlineStyled: inlineStyled.length,
    hardcodedStyle: hardcoded,
    errorBoundary: document.body.innerText.includes('页面出错了') || document.body.innerText.includes('Something went wrong'),
    blank: (document.body.innerText||'').trim().length < 20,
  };
}
"""

def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=r"C:\Users\hspcadmin\AppData\Local\ms-playwright\chromium-1243\chrome-win64\chrome.exe",
        )
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        console_errors, page_errors, failed_reqs = [], [], []
        page.on("console", lambda m: console_errors.append(m.text[:200]) if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)[:200]))
        page.on("response", lambda r: failed_reqs.append(f"{r.status} {r.url[-80:]}") if r.status >= 400 else None)

        # 首次进入，观察是否被重定向到登录
        page.goto(BASE + "/xianyu/", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        login_state = page.url
        results.append({"route": "(boot)", "url_after": login_state})

        for r in ROUTES:
            console_errors.clear(); page_errors.clear(); failed_reqs.clear()
            entry = {"route": r}
            try:
                target = "/xianyu" + r
                retries = 0
                for attempt in range(4):
                    page.goto(BASE + target, wait_until="domcontentloaded")
                    page.wait_for_timeout(1800)
                    cur = page.evaluate("() => location.pathname")
                    if cur == target or (r == "/" and cur == "/xianyu"):
                        break
                    retries += 1
                m = page.evaluate(METRICS_JS)
                m["retries"] = retries
                m["landedOn"] = page.evaluate("() => location.pathname")
                m["pageErrors"] = page_errors.copy()
                m["consoleErrCount"] = len(console_errors)
                m["consoleErrSample"] = console_errors[:3]
                m["failed4xx5xx"] = failed_reqs[:5]
                entry["metrics"] = m
            except Exception as e:
                entry["error"] = str(e)[:200]
            results.append(entry)
            print(json.dumps(entry, ensure_ascii=False)[:500], flush=True)
        browser.close()

    with open("ui_sweep_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("DONE, saved ui_sweep_result.json")

if __name__ == "__main__":
    main()
