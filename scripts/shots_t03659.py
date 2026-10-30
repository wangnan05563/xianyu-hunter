# -*- coding: utf-8 -*-
"""T03659 产品介绍文档配图：从隔离实例（127.0.0.1:8010，调度器/隧道已关）截真实界面。

隔离与脱敏：
- 只读访问副本库（%TEMP%/xh-shots/data），不碰用户真实 data/
- 截图前在页面内做 DOM 级脱敏：头像模糊、含订单号/链接/令牌的单元格与输入框模糊、
  长数字串打码；不打印 WEB_TOKEN
"""
import io
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8010"
ENV_PATH = r"C:\Users\hspcadmin\AppData\Local\Temp\xh-shots\.env"
OUT_DIR = r"D:\code\otherProjects\17_xianyu\docs\assets\product-shots"

DESKTOP = (1600, 900)
MOBILE = (390, 844)

# 页面级脱敏：表格列按表头关键词模糊；头像模糊；长数字/URL 文本打码
MASK_JS = r"""
() => {
  const BLUR = 'blur(7px)';
  const maskText = (el) => { el.style.filter = BLUR; };
  // 1) 表头命中敏感列的整列内容模糊
  const SENSITIVE = /(卖家|昵称|买家|用户|订单号|收货|收货人|电话|手机|邮箱|地址|Webhook|Token|令牌|Cookie|UA|会话|IP)/i;
  document.querySelectorAll('table').forEach((t) => {
    const heads = [...t.querySelectorAll('thead th')].map((h) => (h.innerText || '').trim());
    if (!heads.length) return;
    const idx = heads.map((h, i) => (SENSITIVE.test(h) ? i : -1)).filter((i) => i >= 0);
    if (!idx.length) return;
    t.querySelectorAll('tbody tr').forEach((tr) => {
      const tds = tr.querySelectorAll('td');
      idx.forEach((i) => { const td = tds[i]; if (td) maskText(td); });
    });
  });
  // 2) 头像模糊
  document.querySelectorAll('.ant-avatar, img[src*="avatar"], img[class*="avatar"]').forEach(maskText);
  // 3) 文本里出现长数字串（订单号）或 http(s) 链接的节点打码
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const hits = [];
  while (walker.nextNode()) {
    const s = walker.currentNode.nodeValue || '';
    if (/\d{8,}/.test(s) || /https?:\/\//.test(s)) hits.push(walker.currentNode.parentElement);
  }
  hits.forEach((el) => { if (el && el.tagName !== 'SCRIPT' && el.tagName !== 'STYLE') maskText(el); });
  // 4) 输入框里的敏感值（webhook/token/手机号）模糊
  document.querySelectorAll('input,textarea').forEach((el) => {
    const v = el.value || el.getAttribute('value') || '';
    if (/^\d{8,}$/.test(v) || /https?:\/\//.test(v) || /token|cookie|secret/i.test(el.name || '') ||
        /(webhook|token|cookie|密码|手机)/i.test(el.closest('div')?.innerText || '')) {
      el.style.filter = BLUR;
    }
  });
  return true;
}
"""

# 关掉可能遮挡界面的引导/更新提示（仅影响截图观感）
CLEANUP_JS = r"""
() => {
  document.querySelectorAll(
    '.driver-overlay,.driver-popover,.ant-modal-root .ant-modal-wrap,.ant-modal-mask,' +
    '.ant-drawer-mask,.ant-notification,.ant-message,' +
    '.ant-tour,.ant-tour-mask,.ant-tour-target-placeholder'
  ).forEach((el) => el.remove());
  return true;
}
"""

# 离线环境下闲鱼 CDN 缩略图必然取不到：页面自带的兜底是 🖼️ emoji（在文档里很像碎图标）。
# 统一给商品图容器换成中性占位块，加载失败的 <img> 也一并换掉
PLACEHOLDER_CSS = (
    'width:100%;height:100%;display:flex;align-items:center;justify-content:center;'
    'background:#fafafa;color:#c9c9c9;font-size:12px;border:1px dashed #e4e4e4;border-radius:6px'
)
FIX_IMGS_JS = r"""
() => {
  let n = 0;
  const CSS = 'CSS_HERE';
  const fill = (el) => {
    el.innerHTML = `<div style="${CSS}">商品图</div>`;
    n += 1;
  };
  document.querySelectorAll('[class*="item-card-image"],[class*="item-image"],[class*="cover-image"]')
    .forEach(fill);
  document.querySelectorAll('img').forEach((img) => {
    if (img.complete && img.naturalWidth > 0) return;
    if (img.src && !/^https?:/.test(img.src)) return;
    const box = document.createElement('div');
    const w = img.clientWidth || img.parentElement?.clientWidth || 80;
    const h = img.clientHeight || img.parentElement?.clientHeight || 80;
    box.style.cssText = `width:${w}px;height:${h}px;` + CSS;
    box.textContent = '商品图';
    img.replaceWith(box);
    n += 1;
  });
  // 兜底 emoji 单独成节点时直接去掉
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    if (/^\s*🖼️?\s*$/.test(w.currentNode.nodeValue || '')) w.currentNode.nodeValue = '';
  }
  return n;
}
""".replace("CSS_HERE", PLACEHOLDER_CSS)

# 价格策略页右侧「策略命中预览」默认不取数，点一次预览按钮把直方图与命中数跑出来
CLICK_REFRESH_PREVIEW_JS = r"""
() => {
  const btn = [...document.querySelectorAll('button')]
    .find((b) => (b.innerText || '').includes('刷新预览数据'));
  if (btn) btn.click();
  return !!btn;
}
"""

ROUTES = [
    # (文件名, 路径, 移动端?, 额外等待 ms, 额外 prep JS)
    ("01-tasks", "/tasks", False, 2500, None),
    ("02-items", "/items", False, 2500, None),
    ("03-evaluations", "/evaluations", False, 3000, None),
    ("04-price-strategy", "/config/price", False, 2500, CLICK_REFRESH_PREVIEW_JS),
    ("05-orders", "/orders", False, 2500, None),
    (
        "05b-confirm-buy",
        "/confirm-buy?task_id=t68bc149b&item_id=1064817948549",
        False,
        3000,
        None,
    ),
    ("06-notifier", "/config/notifier", False, 2500, None),
    ("06b-notifications", "/notifications", False, 2500, None),
    ("07-mobile-dashboard", "/m/", True, 6000, None),
    ("08-chatbot", "/chatbot", False, 2500, None),
    ("09-anticrawl", "/anticrawl", False, 2500, None),
    ("10-maintenance", "/maintenance", False, 2500, None),
    ("10b-db-admin", "/maintenance/db", False, 3000, None),
    ("00-dashboard", "/", False, 3000, None),
]

# 隔离实例里没有闲鱼 Cookie，/api/auth/me 会回 logged_in=false 把 SPA 打回登录页。
# 为了拿到真实界面截图但不复制用户 Cookie，仅在浏览器侧把该探针结果置为已登录
# （页面展示的昵称固定为「示例用户」，其余接口仍走真实后端与副本库）。
AUTH_ME = {
    "logged_in": True,
    "user_id": "default",
    "nick": "示例用户",
    "avatar_url": "",
    "fetched_at": 0,
    "display_name_source": "custom_alias",
    "nick_sync_state": "ok",
}

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

# 1×1 浅灰 PNG：离线环境里所有外链缩略图（闲鱼 CDN/头像）统一回这个色块，
# 避免文档里出现浏览器裂图图标；本地静态资源不受影响
GRAY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63f8ffff3f0005fe02fea735c8d00000000049454e44ae426082"
)


def _route_image(route):
    url = route.request.url
    if route.request.resource_type == "image" and not url.startswith(BASE):
        route.fulfill(status=200, content_type="image/png", body=GRAY_PNG)
    else:
        route.continue_()


def read_token() -> str:
    # 优先用为副本库数据归属用户签发的 session token：WEB_TOKEN 直通的 user_id="default"
    # 会撞上多用户读侧过滤，items/sellers 等真实行全在真实 uid 下，读出来是空列表
    sess_path = os.path.join(os.path.dirname(ENV_PATH), "session_token.txt")
    if os.path.exists(sess_path):
        tok = io.open(sess_path, encoding="utf-8").read().strip()
        if tok:
            return tok
    text = io.open(ENV_PATH, encoding="utf-8").read()
    m = re.search(r"^WEB_TOKEN=(\S+)\s*$", text, re.M)
    if not m:
        raise SystemExit("WEB_TOKEN missing in isolated .env")
    return m.group(1)


def main(argv):
    want = set(argv[1:]) or None
    token = read_token()
    os.makedirs(OUT_DIR, exist_ok=True)
    # 优先用本机已装的系统 Chrome：Playwright 自带 chromium 版本与当前 wheel 不匹配时 headless shell 会缺失
    exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    launch = {"headless": True}
    if os.path.exists(exe):
        launch["executable_path"] = exe
    else:
        launch["channel"] = "chrome"
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch)
        for name, path, mobile, wait_ms, prep in ROUTES:
            if want and name not in want:
                continue
            w, h = MOBILE if mobile else DESKTOP
            ctx = browser.new_context(
                viewport={"width": w, "height": h},
                device_scale_factor=1,
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                user_agent=MOBILE_UA if mobile else None,
                is_mobile=mobile,
                has_touch=mobile,
                service_workers="block",
            )
            ctx.add_cookies([{"name": "xh_token", "value": token, "domain": "127.0.0.1", "path": "/"}])
            page = ctx.new_page()
            # 引导 Tour / 弹层可能在截屏前一瞬才挂载，用常驻定时器持续清理
            page.add_init_script(
                "setInterval(() => { document.querySelectorAll("
                "'.driver-overlay,.driver-popover,.ant-tour,.ant-tour-mask,"
                ".ant-tour-target-placeholder,.ant-modal-mask,.ant-drawer-mask,"
                ".ant-notification,.ant-message').forEach((el) => el.remove()); }, 200);"
            )
            page.route("**/*", _route_image)
            page.route(
                "**/api/auth/me**",
                lambda route: route.fulfill(
                    status=200, content_type="application/json", body=json.dumps(AUTH_ME)
                ),
            )
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)[:200]))
            target = BASE + "/xianyu" + path
            page.goto(target, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            # SPA 有时首跳落回首页，重试一次直达
            if page.evaluate("() => location.pathname") != "/xianyu" + path and path != "/":
                page.goto(target, wait_until="domcontentloaded")
                page.wait_for_timeout(wait_ms)
            page.evaluate(CLEANUP_JS)
            if prep:
                page.evaluate(prep)
                page.wait_for_timeout(2000)
            page.evaluate(FIX_IMGS_JS)
            # 列表/卡片是异步补齐的，裂图可能在首轮处理后才挂载，补扫一轮
            page.wait_for_timeout(900)
            page.evaluate(FIX_IMGS_JS)
            page.evaluate(MASK_JS)
            page.wait_for_timeout(300)
            # PWA/通知可能在首次清理之后才弹，截屏前再清一次
            page.evaluate(CLEANUP_JS)
            page.wait_for_timeout(150)
            out = os.path.join(OUT_DIR, name + ".png")
            page.screenshot(path=out, full_page=False)
            metrics = page.evaluate(
                "() => ({url: location.pathname, chars: (document.body.innerText||'').length,"
                " cards: document.querySelectorAll('.ant-card').length,"
                " tables: document.querySelectorAll('.ant-table').length,"
                " empty: document.querySelectorAll('.ant-empty').length})"
            )
            print(name, metrics, "errors=", errors[:2], "bytes=", os.path.getsize(out))
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main(sys.argv)
