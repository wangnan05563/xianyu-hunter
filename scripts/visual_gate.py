# -*- coding: utf-8 -*-
"""T02796 视觉基线门禁：为关键页建立入库的像素基线与逐张 SHA256 判等。

零新依赖：复用仓内已有的 playwright + 系统 Chrome（`chromium.launch(channel="chrome")`）。

为什么需要它：6.2 的 UI 核对此前只能「代码 + 文档 + 人眼」三方对齐，
改了一个样式没人能机器地回答「别的页有没有被带歪」。这套门禁把答案变成
一条命令：像素和基线不等就 FAIL。

三种模式：
  update  采集并写入基线（`--record` 同时把 `**/api/**` 响应录成 fixtures.json）
  check   重采一遍，与基线逐张 SHA256 判等；缺图/多图/环境不符/基线文件被篡改都算 FAIL
  两者都跑同一批身份断言，避免「基线其实是一张登录页」这种沉默失败

固定环境（写进 manifest，check 时逐项比对）：视口、DPR=1、locale zh-CN、
Asia/Shanghai、浅色、reduced_motion、`screenshot(animations="disabled")`、
以及冻结的 Date（页面里任何「刚刚 / x 秒前 / 今日」都按同一个时刻渲染）。

数据确定性靠 fixtures 回放：update 时录制接口响应，check 时用同一份 fixtures 回放，
所以基线既不受用户真实数据变化影响，也不需要每次跑都联网。

用法（沙箱实例见 frontend/tests/visual/README.md）：
  ./.venv/Scripts/python.exe scripts/visual_gate.py update --url http://127.0.0.1:8123 --record
  ./.venv/Scripts/python.exe scripts/visual_gate.py check  --url http://127.0.0.1:8123
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PAGES = REPO / "frontend" / "tests" / "visual" / "pages.json"
DEFAULT_BASELINE = REPO / "frontend" / "tests" / "visual" / "baseline"

VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "mobile", "width": 390, "height": 844},
    # tall：1440×2000。桌面 900px 那张只覆盖首屏——实测把「策略 4」的标签改掉，
    # 视口截图与 .page-container 元素截图都判不出差异（内容在内层滚动容器里，
    # full_page 拼接在这个布局上还不稳定）。长表单页的回归需要一张能装下整页的基线。
    {"name": "tall", "width": 1440, "height": 2000},
]

# 冻结时刻：2026-01-01 08:00 +08:00。选在整点后是为了让「今日」窗口两侧都有余量，
# 任何页面里的相对时间都会稳定渲染成同一个串。改这个值会让所有基线失效（manifest 会拦）。
FROZEN_TIME = "2026-01-01T08:00:00+08:00"

# 沙箱没有闲鱼账号态：/api/auth/me 必须合成一份「已登录」响应，否则前端守卫
# （MainLayout 的 authChecked/loggedIn）会把整页停在登录界面，基线就成了登录页。
AUTH_ME = {
    "logged_in": True,
    "user_id": "visual_gate_sandbox",
    "nick": "视觉基线沙箱",
    "local_username": "visual_gate_sandbox",
    "custom_alias": "",
    "avatar": "",
}

# 疑似明文密钥/令牌：命中任一即拒绝入库（截图与 fixtures 都可能把它们带进仓库）
FORBIDDEN = [
    r"X-Access-Token",
    r"(?i)access[_-]?token\s*[:=]\s*\S{8,}",
    r"(?i)bearer\s+[A-Za-z0-9._-]{16,}",
    r"https://oapi\.dingtalk\.com/robot/send\?access_token=",
]

# SSE 长连接不能被路由拦截：route.fetch() 会等一个永不结束的流。
# 直接给一个立刻结束的空流，页面拿不到事件也就不会有懒加载 DOM 抖动。
SSE_PATHS = ("/api/events/stream", "/api/logs/stream")

# 每次请求都不同的缓存位参数，回放时按归一化后的 URL 命中
VOLATILE_QUERY = {"t", "_", "ts", "timestamp", "cachebust"}

# 录制时统一掩码的字段：接口里的凭据字段即使已经打了码（`****wqvx` 这种尾 4 位），
# 也是「跟这台机器的配置绑定」的串——既不该进仓库，也不该成为基线像素的一部分。
# 只认带下划线前后缀的字段名，`"key": "dashboard"`（菜单项 id）这类不能被误伤。
MASK_VALUE = "GATE-REDACTED"
SECRET_FIELD_RE = re.compile(
    r'"([A-Za-z0-9_]*(?:api_key|_key|_token|_secret|webhook|password|cookie|authtoken)'
    r'[A-Za-z0-9_]*)"\s*:\s*"((?:[^"\\]|\\.)*)"'
)


def _redact_secrets(body: bytes, content_type: str) -> bytes:
    if "json" not in (content_type or ""):
        return body
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body

    def sub(match: re.Match) -> str:
        field, value = match.group(1), match.group(2)
        if not value.strip():
            return match.group(0)
        return f'"{field}": "{MASK_VALUE}"'

    return SECRET_FIELD_RE.sub(sub, text).encode("utf-8")

# 身份断言轮询预算与到位后的静置时长（毫秒）
IDENTITY_TIMEOUT_MS = 20000
SETTLE_MS = 600
QUIESCE_TIMEOUT_MS = 5000
MICRO_SETTLE_MS = 150

# 出图自稳判据：最多连拍这么多次，相邻两次相等才认
SHOT_STABLE_ATTEMPTS = 3
SHOT_STABLE_GAP_MS = 400


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def app_version() -> str:
    """基线目录名默认取 pyproject 的 version（与发版号同源，逐版本各留一套基线）"""
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit("pyproject.toml 里找不到 version，请显式传 --version")
    return m.group(1)


def norm_url(url: str) -> str:
    """归一化成 fixtures 的键：丢掉缓存位参数并排序，否则每次 URL 都不同、回放必 miss"""
    s = urlsplit(url)
    query = [
        (k, v)
        for k, v in parse_qsl(s.query, keep_blank_values=True)
        if k.lower() not in VOLATILE_QUERY
    ]
    return s.path + (("?" + urlencode(sorted(query))) if query else "")


def _frozen_clock_script() -> str:
    # 只冻结 Date；performance.now / requestAnimationFrame 保持真实推进，
    # 否则 antd 的挂载过渡会停在第一帧。
    return (
        f"(() => {{ const FIXED = Date.parse('{FROZEN_TIME}');"
        " const Orig = Date;"
        " class Frozen extends Orig {"
        "   constructor(...a) { if (a.length === 0) super(FIXED); else super(...a); }"
        " }"
        " Frozen.now = () => FIXED;"
        " window.Date = Frozen;"
        "})();"
    )


def _service_worker_block_script() -> str:
    """把 `navigator.serviceWorker` 摘掉，让 SW 根本没机会注册。

    两个必须拦的理由：
    1. 这个 PWA 的 SW 会缓存「近期 API 响应」（见 ReloadPrompt 文案），一旦命中旧缓存，
       fixtures 回放就被劫持——门禁以为自己控制了数据，其实控制的是缓存；
    2. 注册成功会弹「应用已可离线使用」通知（ReloadPrompt.tsx，duration=4s），
       那是一张会在两次截图之间自己出现又消失的浮层。
    `delete` 掉 Navigator.prototype 上的访问器（WebIDL 属性是 configurable），
    workbox 的 `"serviceWorker" in navigator` 前置判断才会为假、直接早退；
    只把 register 换成 reject 不够，registerSW 仍会继续走完注册流程。
    """
    return "try { delete Object.getPrototypeOf(navigator).serviceWorker; } catch (e) {}"


def _guide_suppress_script(pages: list[dict]) -> str:
    """种「首访引导已完成」标记，让 antd Tour 不弹。

    GuideController 对每个路由首次访问自动弹出引导浮层（src/guides/GuideController.tsx
    的 `isGuideDone(location.pathname)` 门）。那是一层遮住整页的浮层，且每次新建上下文
    都会重弹——基线要的是页面本身，不是浮层。
    值必须是 utils/storage.ts 的封装格式 `{__v:1,data:'1'}`；直接写 `'1'` 会被
    get() 判成脏数据回退成默认值，门照样打开。
    """
    routes = sorted({x["route"] for x in pages if isinstance(x.get("route"), str)})
    wrapped = json.dumps(json.dumps({"__v": 1, "data": "1"}))
    return "".join(
        f"localStorage.setItem({json.dumps('xh.guide.done.' + r)}, {wrapped});"
        for r in routes
    )


def make_handler(store: dict | None, replay: bool):
    """返回 (store, handler)：handler 记录或回放 `**/api/**`，并合成 /api/auth/me"""

    def handler(route):
        url = route.request.url
        if "/api/auth/me" in url:
            # 合成响应绝不写进 fixtures：基线的登录态与沙箱账号数据必须解耦
            route.fulfill(
                status=200,
                headers={"content-type": "application/json"},
                body=json.dumps(AUTH_ME, ensure_ascii=False).encode("utf-8"),
            )
            return
        if any(p in url for p in SSE_PATHS):
            route.fulfill(status=200, headers={"content-type": "text/event-stream"}, body=b"")
            return
        key = norm_url(url)
        if replay:
            item = store.get(key) if store else None
            if item is None:
                route.fulfill(
                    status=599,
                    headers={"content-type": "text/plain"},
                    body=b"NO FIXTURE: " + key.encode("utf-8"),
                )
                return
            route.fulfill(
                status=item["status"],
                headers={"content-type": item["content_type"]},
                body=base64.b64decode(item["body_b64"]),
            )
            return
        resp = route.fetch()
        content_type = resp.headers.get("content-type", "")
        if store is None:
            route.fulfill(response=resp)
            return
        # 先洗再喂给浏览器：这样「屏幕上的」和「fixtures 里的」是同一份内容。
        # 只洗落盘的话，录制那一次渲染的是真值、回放那一次渲染的是掩码，
        # 基线就成了机器相关的像素——check 会在换机器时莫名其妙地红。
        body = _redact_secrets(resp.body(), content_type)
        store[key] = {
            "status": resp.status,
            "content_type": content_type,
            "body_b64": base64.b64encode(body).decode(),
        }
        route.fulfill(
            status=resp.status, headers={"content-type": content_type}, body=body
        )

    return handler


def env_fingerprint(browser) -> dict:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "browser": browser.version,
        "channel": "chrome",
        "device_scale_factor": 1,
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "color_scheme": "light",
        "reduced_motion": "reduce",
        "animations": "disabled",
        "frozen_time": FROZEN_TIME,
        # 视口尺寸写进指纹：改了 VIEWPORTS（哪怕只改高度）就等于换了一套基线，
        # 必须在 check 里炸出来，而不是让人对着 15 张「像素不等」猜为什么全红
        "viewports": VIEWPORTS,
    }


def capture_all(
    url: str,
    pages: list[dict],
    token: str | None,
    store: dict | None,
    replay: bool,
    shoot: bool = True,
) -> tuple[dict[str, bytes], dict]:
    """走一遍页集。`shoot=False` 只做导航+身份断言，用来把接口喂进 store。

    为什么 update 要分两趟（本机实测过才这么写）：一趟「边录边拍」录出来的基线，
    和 `check` 回放 fixtures 得到的截图对不上——`tasks__desktop` 稳定地差一个哈希。
    隔离探针证明回放路径本身两种上下文策略都 100% 可复现，抖动只来自
    live（真接口，带瞬时轮询响应）vs replay（固定响应）这条数据通路。
    所以基线必须由**回放**产出：录制方和校验方吃同一份字节，才有「不等 = 代码变了」。
    """
    from playwright.sync_api import sync_playwright

    shots: dict[str, bytes] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        try:
            fingerprint = env_fingerprint(browser)
            for vp in VIEWPORTS:
                scoped = [x for x in pages if x.get("viewport", "both") in ("both", vp["name"])]
                if not scoped:
                    continue
                ctx = browser.new_context(
                    viewport={"width": vp["width"], "height": vp["height"]},
                    device_scale_factor=1,
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                    color_scheme="light",
                    reduced_motion="reduce",
                )
                init = [_frozen_clock_script(), _service_worker_block_script()]
                suppress = _guide_suppress_script(scoped)
                if suppress:
                    init.append(suppress)
                if token:
                    # 只注入浏览器上下文，不落盘、不打印
                    init.append(
                        "localStorage.setItem('xh_token', " + json.dumps(token) + ");"
                        "document.cookie='xh_token=" + token + "; path=/';"
                    )
                for script in init:
                    ctx.add_init_script(script)
                handler = make_handler(store, replay)
                # auth/me 与 SSE 的分流都在 handler 内，所以只需注册这一条
                ctx.route("**/api/**", handler)
                page = ctx.new_page()
                # 在途请求计数：截图必须落在「没有响应还没落地」的时刻。
                # 页面每 30s 轮询调度器状态，只要截图撞上一次请求的往返，
                # 加载态（Spin/骨架）在不在帧里就变成掷骰子——基线会自己变红。
                pending: set[str] = set()
                page.on("request", lambda r: pending.add(r.url))
                page.on("requestfinished", lambda r: pending.discard(r.url))
                page.on("requestfailed", lambda r: pending.discard(r.url))
                for item in scoped:
                    _shoot(page, url, item, vp["name"], shots, pending, shoot=shoot)
                ctx.close()
        finally:
            browser.close()
    return shots, fingerprint


def _identity_state(page, anchor: str | None, expect_text: str | None, expect_url: str | None):
    """返回 (是否通过, 未通过原因)。整体轮询而不是逐项硬断言：

    页面是 SPA，`load` 只代表骨架到手；身份文本、表格头、卡片标题往往在随后的
    接口回来之后才渲染。单次断言会把「还没渲染完」误判成「渲染错了」，
    于是每条基线都得靠加大 sleep 来碰运气——那是噪声，不是门禁。
    """
    if "/login" in page.url:
        return False, f"被重定向到登录页 → {page.url}"
    if anchor and page.query_selector(anchor) is None:
        return False, f"锚点未出现：{anchor}"
    if expect_url and expect_url not in page.url:
        return False, f"最终 URL 不含 {expect_url!r}（URL={page.url}）"
    if expect_text:
        text = page.evaluate("() => document.documentElement.innerText || ''")
        if expect_text not in text:
            return False, f"缺少文本 {expect_text!r}（URL={page.url}）"
    return True, ""


def _drain(page, pending: set[str]) -> None:
    """等在途请求清空；超时不报错——有些连接本就不会结束。"""
    deadline = time.monotonic() + QUIESCE_TIMEOUT_MS / 1000
    while pending and time.monotonic() < deadline:
        page.wait_for_timeout(100)


def _shot_stable(capture, name: str) -> bytes:
    """连拍两次取稳态：两次字节相等才认，不相等就重试，始终不稳则拒绝出图。

    为什么不能只靠 drain：canvas 图表（ECharts 的价格直方图）的动画是 JS 驱动的 rAF，
    `animations="disabled"` 只管 CSS/Web Animations，`requestAnimationFrame` 又故意没冻结
    （冻了 antd 的挂载过渡会停在第一帧）。本机实测：1440×2000 那张价格页在
    两次采集之间差 3 字节——正是「图表还在画」的签名。
    判据直接落在**我们要断言的那个东西**上：这张图自己稳不稳。
    """
    previous: bytes | None = None
    for attempt in range(SHOT_STABLE_ATTEMPTS):
        current = capture()
        if previous is not None and current == previous:
            return current
        previous = current
        if attempt < SHOT_STABLE_ATTEMPTS - 1:
            time.sleep(SHOT_STABLE_GAP_MS / 1000)
    raise SystemExit(
        f"截图不自稳：{name} 连续 {SHOT_STABLE_ATTEMPTS} 次采集都在变，"
        "页面仍在自我渲染（动画/轮播/未完成图表），不能当基线"
    )


def _shoot(
    page,
    base_url: str,
    item: dict,
    vp_name: str,
    shots: dict[str, bytes],
    pending: set[str],
    shoot: bool = True,
) -> None:
    name = item["name"]
    page.goto(f"{base_url}{item['path']}", wait_until="load", timeout=60000)
    anchor = item.get("anchor")
    expect_text = item.get("expect_text")
    expect_url = item.get("expect_url")
    if not anchor and not expect_text and not expect_url:
        raise SystemExit(f"页集缺身份断言：{name}（anchor/expect_text/expect_url 至少给一个）")
    deadline = time.monotonic() + IDENTITY_TIMEOUT_MS / 1000
    reason = ""
    while True:
        ok, reason = _identity_state(page, anchor, expect_text, expect_url)
        if ok:
            break
        if time.monotonic() >= deadline:
            root_html = page.evaluate(
                "() => (document.getElementById('root') || {innerHTML:''}).innerHTML.length"
            )
            hint = ""
            if not root_html:
                # #root 全空 = App 这一层返回了 null。已知会造成这种状态的一种情形：
                # 窄视口进桌面路由时 App 渲染 <Navigate to="/m/">，而 App 自己没订阅
                # location，重定向之后不会再次渲染 → 白屏（见 frontend/src/App.tsx 的守卫）
                hint = "；#root 为空：App 层返回了 null（疑似窄视口重定向后未再渲染）"
            raise SystemExit(
                f"页面身份不符：{name} 在 {IDENTITY_TIMEOUT_MS}ms 内没到位（{reason}{hint}）"
            )
        page.wait_for_timeout(200)
    # 静置 → 排空在途 → 再静置 → 再排空：Toast、二次跳转、轮询响应都可能恰好在
    # 身份到位之后才落下。单次定长等待既慢又不可靠——tasks__desktop 就这样漂走过一次
    # （同一份构建、同一份 fixtures，两次采集的图不等）。
    for _ in range(2):
        page.wait_for_timeout(SETTLE_MS)
        _drain(page, pending)
    ok, reason = _identity_state(page, anchor, expect_text, expect_url)
    if not ok:
        raise SystemExit(f"页面身份在静置后变质：{name}（{reason}）")
    page.wait_for_timeout(MICRO_SETTLE_MS)
    # 轮询页 load 之后仍可能有字体与懒加载图落位，等齐再截
    page.evaluate("() => (document.fonts ? document.fonts.ready.then(() => true) : true)")
    page.evaluate(
        "() => Promise.all(Array.from(document.images).map((i) => i.complete"
        " ? true : new Promise((r) => { i.addEventListener('load', r);"
        " i.addEventListener('error', r); })))"
    )
    # 瞬态浮层护栏：Tour 遮罩与 notification 吐司都会自己出现/消失。
    # 一旦进了基线，下一次跑没弹出来就是「像素不等」，而根因不是样式改动。
    # 首访引导已在上下文里标成完成、SW 已禁用，所以这里命中即为真异常。
    transients = page.evaluate(
        "() => document.querySelectorAll('.ant-tour, .ant-notification-notice').length"
    )
    if transients:
        raise SystemExit(
            f"瞬态浮层未清：{name} 上还有 {transients} 个 Tour/通知，拒绝把它截进基线"
        )
    html = page.content()
    text = page.evaluate("() => document.documentElement.innerText || ''")
    for pattern in FORBIDDEN:
        if re.search(pattern, text) or re.search(pattern, html):
            raise SystemExit(f"脱敏护栏拦截：{item['path']} 命中 {pattern}，拒绝入库")
    if not shoot:
        # 录制趟：这一趟的全部意义是把这一页会发的接口喂进 store，
        # 流程和校验趟逐行相同（连静置、排空、断言都一样），才能保证喂进去的请求集合一致。
        return
    selector = item.get("selector")
    # full_page 只有 Page.screenshot 认；Locator.screenshot 会 TypeError。
    # 两者同时给出时按元素截图（元素级本来就能超出视口，Playwright 自己滚动拼接）。
    if selector:
        element = page.locator(selector).first

        def capture() -> bytes:
            return element.screenshot(animations="disabled", caret="hide")
    else:
        full = bool(item.get("full_page"))

        def capture() -> bytes:
            return page.screenshot(animations="disabled", caret="hide", full_page=full)
    shots[f"{name}__{vp_name}.png"] = _shot_stable(capture, name)


def _token(args) -> str | None:
    name = getattr(args, "token_env", None)
    if not name:
        return None
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"环境变量 {name} 为空：后端开了鉴权时需要 WEB_TOKEN 才能取到数据")
    return value


def _load(args) -> tuple[list[dict], Path]:
    pages = json.loads(Path(args.pages).read_text(encoding="utf-8"))
    version = args.version or app_version()
    return pages, Path(args.baseline) / version


def _redaction_gate(store: dict) -> None:
    """落盘前的两道闸：
    1) 掩码后不该再有「密钥字段 = 非空且非掩码」的残留；
    2) FORBIDDEN 形态（真令牌串、钉钉 webhook）一个都不许出现。
    同时打印被掩掉的字段数：这是正对照——0 次掩码意味着闸其实没在拦东西，
    而不是「这次恰好干净」。
    """
    residue: list[str] = []
    masked = 0
    for fixture_key, item in store.items():
        text = base64.b64decode(item["body_b64"]).decode("utf-8", errors="ignore")
        masked += text.count(f'"{MASK_VALUE}"')
        for m in SECRET_FIELD_RE.finditer(text):
            if m.group(2).strip() and m.group(2) != MASK_VALUE:
                residue.append(f"{fixture_key} -> {m.group(1)}")
        for pattern in FORBIDDEN:
            if re.search(pattern, text):
                residue.append(f"{fixture_key} -> 命中 {pattern}")
    if residue:
        raise SystemExit(f"fixtures 未通过脱敏闸，拒绝入库：{residue[:8]}")
    print(f"fixtures masked fields: {masked}")


def do_update(args) -> int:
    pages, base = _load(args)
    base.mkdir(parents=True, exist_ok=True)
    store = {} if args.record else None
    fingerprint: dict = {}
    if store is None:
        shots, fingerprint = capture_all(args.url, pages, _token(args), None, replay=False)
    else:
        # 第一趟：只走页面、只录接口，不出图。
        _, _ = capture_all(args.url, pages, _token(args), store, replay=False, shoot=False)
        _redaction_gate(store)
        (base / "fixtures.json").write_text(
            json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"fixtures recorded: {base / 'fixtures.json'}（{len(store)} 个接口）")
        # 第二趟：回放刚录的 fixtures 出图——和 check 用的是同一条数据通路。
        # 出图前先把基线目录里的旧 PNG 清掉：两趟之间页面里可能多了「NO FIXTURE」
        # 之类的分支，残留旧图会被 check 当成「多出的基线图」，噪声盖过真信号。
        for old in base.glob("*.png"):
            old.unlink()
        shots, fingerprint = capture_all(args.url, pages, _token(args), store, replay=True)
    manifest = {
        "version": base.name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "env": fingerprint,
        "fixtures": store is not None,
        "url": args.url,
        "shots": {},
    }
    for png_name, png in shots.items():
        (base / png_name).write_bytes(png)
        manifest["shots"][png_name] = {"sha256": sha256(png), "bytes": len(png)}
    (base / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"baseline written: {base}（{len(shots)} 张）")
    for png_name, meta in manifest["shots"].items():
        print(f"  {png_name} {meta['sha256'][:16]} {meta['bytes']}B")
    return 0


def do_check(args) -> int:
    pages, base = _load(args)
    manifest_path = base / "manifest.json"
    if not manifest_path.exists():
        print(f"FAIL 基线不存在：{manifest_path}（先跑 update）")
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixture_path = Path(args.fixtures) if args.fixtures else base / "fixtures.json"
    store = None
    if manifest.get("fixtures"):
        if not fixture_path.exists():
            print(f"FAIL 基线声明了 fixtures，但找不到 {fixture_path}")
            return 2
        store = json.loads(fixture_path.read_text(encoding="utf-8"))
    shots, fingerprint = capture_all(
        args.url or manifest.get("url", ""), pages, _token(args), store, replay=store is not None
    )

    failures: list[str] = []
    if not args.allow_env_mismatch:
        for key, want in manifest["env"].items():
            got = fingerprint.get(key)
            if got != want:
                failures.append(f"环境不符 {key}: 基线={want!r} 当前={got!r}")
    expected = manifest["shots"]
    for png_name, meta in expected.items():
        path = base / png_name
        if not path.exists():
            failures.append(f"缺少基线图 {png_name}")
            continue
        # 基线文件自身的完整性：不查的话，被篡改/截断的基线照样能 PASS
        disk = sha256(path.read_bytes())
        if disk != meta["sha256"]:
            failures.append(
                f"基线文件与 manifest 不一致 {png_name}: "
                f"manifest={meta['sha256'][:16]} 磁盘={disk[:16]}"
            )
        if png_name not in shots:
            failures.append(f"缺少截图 {png_name}")
            continue
        got = sha256(shots[png_name])
        if got != meta["sha256"]:
            failures.append(f"像素不等 {png_name}: 基线={meta['sha256'][:16]} 当前={got[:16]}")
    for png_path in sorted(base.glob("*.png")):
        if png_path.name not in expected:
            failures.append(f"多出基线图 {png_path.name}（manifest 未登记）")
    for png_name in shots:
        if png_name not in expected:
            failures.append(f"多出截图 {png_name}（基线未登记）")
    if store is not None and not shots:
        failures.append("回放模式没有产出任何截图（页面未加载？）")

    if failures:
        print(f"FAIL {len(failures)} 项")
        for one in failures:
            print(f"  - {one}")
        print("确认是预期内的视觉变化后，重跑 update --record 覆盖基线并在 MR 里说明。")
        return 1
    print(f"PASS {len(expected)} shots 全部字节相等（env={manifest['env']['platform'][:40]}）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["update", "check"])
    ap.add_argument("--url", help="实例地址；check 时省略则取 manifest 里记录的 url")
    ap.add_argument("--pages", default=str(DEFAULT_PAGES))
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    ap.add_argument("--version", help="基线目录名，默认取 pyproject.toml 的 version")
    ap.add_argument("--record", action="store_true", help="录制 **/api/** 到 <baseline>/<version>/fixtures.json")
    ap.add_argument("--fixtures", help="回放用的 fixtures.json，默认取基线目录里的那份")
    ap.add_argument("--token-env", help="从该环境变量读 WEB_TOKEN 注入前端（不打印、不落盘）")
    ap.add_argument("--allow-env-mismatch", action="store_true", help="跳过环境指纹比对（仅排障用）")
    args = ap.parse_args()
    if args.mode == "update" and not args.url:
        ap.error("update 需要 --url")
    return do_update(args) if args.mode == "update" else do_check(args)


if __name__ == "__main__":
    sys.exit(main())
