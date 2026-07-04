"""Playwright 有头浏览器登录 - 最可靠的闲鱼登录方式

原理：
1. 启动 Chromium 有头浏览器（使用系统已安装的 Edge 或 Chrome）
2. 导航到 goofish.com，用户在浏览器中正常登录（扫码/密码/短信均可）
3. 轮询检测 Cookie 变化，检测到闲鱼登录 Cookie 后标记成功
4. Cookie 自动写入 browser-data，与 Worker 共享同一 user_data_dir
5. 通过状态文件与 web 后端通信

比 WebView2 更可靠的原因：
- 与 Worker 使用同一 Playwright 引擎和 user_data_dir，Cookie 天然兼容
- 不需要跨进程复制 Cookie 文件（WebView2 → Playwright 复制是主要故障点）
- 登录完成后 Worker 立即可用，无需额外的同步步骤
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))


def _get_browser_cfg():
    from xianyu_hunter.infra.yaml_config import get_config
    return get_config().browser


def _set_status(status_file: Path, **kw) -> None:
    """原子写入状态文件"""
    s = {}
    if status_file.exists():
        try:
            s = json.loads(status_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    s.update(kw)
    s["ts"] = time.time()
    status_file.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


def _elapsed_sec(start: float) -> float:
    return round(time.monotonic() - start, 2)


def _export_cookies_to_json(cookies: list[dict], method: str) -> None:
    """登录成功后导出 Cookie 到 JSON 文件（供 Web 后端立即验证）"""
    try:
        # 需要将 scripts 目录加入 sys.path 才能 import cookie_store
        _repo = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(_repo / "src"))
        from xianyu_hunter.web.services.cookie_store import get_cookie_store
        get_cookie_store().export_cookies(cookies, method=method)
    except Exception as e:
        print(f"[browser_login] Cookie JSON 导出失败: {e}", file=sys.stderr)


def _save_playwright_cookies(cookies: list[dict]) -> None:
    """保存 Playwright 格式的 Cookie 到文件，供 Worker 浏览器实例注入

    Worker 的 BrowserManager 在登录前就已启动，内存中没有登录 Cookie。
    登录成功后需要将 Cookie 注入到 Worker 实例中，否则实时搜索会报
    "闲鱼登录 Cookie 不完整"。
    """
    try:
        _repo = Path(__file__).resolve().parents[1]
        cookie_file = _repo / "data" / "last_login_cookies.json"
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        # 只保存 goofish.com / taobao.com 域的 Cookie，减少文件大小
        domain_cookies = [
            c for c in cookies
            if any(d in c.get("domain", "") for d in ("goofish.com", "taobao.com"))
        ]
        cookie_file.write_text(
            json.dumps(domain_cookies, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[browser_login] Playwright Cookie 已保存到 {cookie_file} (count={len(domain_cookies)})", file=sys.stderr)
    except Exception as e:
        print(f"[browser_login] 保存 Playwright Cookie 失败: {e}", file=sys.stderr)


def _get_edge_path() -> str | None:
    """查找系统 Edge 浏览器路径"""
    import shutil
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    # fallback: 用 shutil.which 查找
    edge = shutil.which("msedge")
    if edge:
        return edge
    return None


def _validate_login_cookies(cookies: list[dict]) -> bool:
    """严格验证 Cookie 是否表示真正登录成功

    仅检测 Cookie 名称存在是不够的（_m_h5_tk 访问首页就会设置），
    必须验证关键登录 Cookie 的值有效：
    - unb: 闲鱼用户ID，必须是纯数字且长度 >= 6
    - cookie2: 会话ID，必须存在且非空、非测试值
    """
    cookie_map = {c["name"]: c.get("value", "") for c in cookies}

    unb = cookie_map.get("unb", "")
    cookie2 = cookie_map.get("cookie2", "")

    # unb 必须是纯数字且长度 >= 6（真实用户ID）
    if not unb or not unb.isdigit() or len(unb) < 6:
        return False

    # 过滤已知测试值（unb=123456 等）
    if unb in ("123456", "123"):
        return False

    # cookie2 必须存在且长度 >= 10（真实会话ID）
    if not cookie2 or len(cookie2) < 10:
        return False

    # 过滤测试值
    if cookie2 == "abc":
        return False

    return True


def _build_login_launch_args(cfg) -> list[str]:
    """Build Chromium args for the interactive login window."""
    args = [
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-extensions",
    ]

    proxy_server = str(getattr(cfg, "proxy_server", "") or "").strip()
    if proxy_server:
        args.append(f"--proxy-server={proxy_server}")
    else:
        args.append("--no-proxy-server")
    return args


_LOGIN_RESOURCE_ALLOW_HINTS = (
    "goofish.com",
    "taobao.com",
    "tmall.com",
    "alicdn.com",
    "aliyuncs.com",
    "aliapp.org",
    "alipay.com",
    "mmstat.com",
    "cnzz.com",
)


def _should_abort_login_resource(url: str, resource_type: str) -> bool:
    """Return True when a nonessential login-window resource can be blocked."""
    if resource_type not in ("font", "media", "image", "manifest"):
        return False

    lower_url = url.lower()
    if any(hint in lower_url for hint in _LOGIN_RESOURCE_ALLOW_HINTS):
        return False
    return True


def _cookie_signature(cookies: list[dict]) -> frozenset[tuple[str, str, str]]:
    return frozenset(
        (
            str(c.get("name", "")),
            str(c.get("domain", "")),
            str(c.get("path", "/")),
        )
        for c in cookies
        if c.get("name")
    )


async def _collect_settled_cookies(
    context,
    *,
    min_wait: float = 2.0,
    max_wait: float = 8.0,
    interval: float = 1.0,
    stable_rounds: int = 2,
    min_full_count: int = 60,
) -> list[dict]:
    """Read cookies until post-login async writes have had time to settle."""
    start = time.monotonic()
    deadline = start + max_wait
    best: list[dict] = []
    last_signature: frozenset[tuple[str, str, str]] | None = None
    stable_count = 0

    while True:
        cookies = await context.cookies()
        if len(cookies) >= len(best):
            best = cookies

        signature = _cookie_signature(cookies)
        if signature == last_signature:
            stable_count += 1
        else:
            stable_count = 0
            last_signature = signature

        waited = time.monotonic() - start
        enough_time = waited >= min_wait
        enough_count = len(cookies) >= min_full_count
        stable = stable_count >= stable_rounds
        timed_out = time.monotonic() >= deadline
        if timed_out or (enough_time and enough_count and stable):
            return best

        await asyncio.sleep(interval)


async def _prepare_login_cookie_export(bc, page, route_handler, timings: dict[str, float]) -> list[dict]:
    """Switch from fast login loading to complete post-login cookie collection."""
    try:
        await bc.unroute("**/*", route_handler)
    except Exception:
        pass

    warmup_start = time.monotonic()
    try:
        await page.goto(
            "https://www.goofish.com/personal",
            wait_until="domcontentloaded",
            timeout=15000,
        )
    except Exception:
        pass
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    timings["post_login_warmup_sec"] = _elapsed_sec(warmup_start)

    await asyncio.sleep(3)
    storage_start = time.monotonic()
    try:
        await bc.storage_state()
    except Exception:
        pass
    timings["storage_state_sec"] = _elapsed_sec(storage_start)

    settle_start = time.monotonic()
    final_cookies = await _collect_settled_cookies(bc)
    timings["settle_cookies_sec"] = _elapsed_sec(settle_start)
    return final_cookies


async def _cmd_login(status_file: Path, timeout: int) -> int:
    """启动有头浏览器，等待用户登录"""
    from playwright.async_api import async_playwright

    flow_start = time.monotonic()
    timings: dict[str, float] = {}

    def set_status(**kw) -> None:
        _set_status(
            status_file,
            elapsed=_elapsed_sec(flow_start),
            timings=timings,
            **kw,
        )

    cfg = _get_browser_cfg()
    set_status(status="starting", message="正在启动浏览器...")

    # 检测可用浏览器：优先 Edge（Windows 自带），其次 Chromium
    edge_path = _get_edge_path()
    # 使用已有的 browser-data 目录，登录后 Cookie 与 Worker 共享
    user_data_dir = Path(cfg.user_data_dir)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    if edge_path:
        print(f"[browser_login] 使用系统 Edge: {edge_path}", file=sys.stderr)
    else:
        print("[browser_login] Edge 未找到，使用 Playwright 内置 Chromium", file=sys.stderr)

    try:
        async with async_playwright() as pw:
            launch_kwargs: dict = {
                "headless": False,
                "viewport": {"width": 1280, "height": 800},
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai",
                "args": _build_login_launch_args(cfg),
            }
            if edge_path:
                # 系统 Edge：干净启动，最不容易被风控检测
                launch_kwargs["executable_path"] = edge_path
                launch_kwargs["channel"] = "msedge"
            else:
                # Playwright 内置 Chromium：需要反检测参数
                launch_kwargs["args"].extend([
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ])

            # 统一使用指定 user_data_dir，确保 Cookie 写入正确位置
            launch_kwargs["user_data_dir"] = str(user_data_dir)

            # 清理 user_data_dir 中残留的 SingletonLock 等锁文件 + Sessions 历史
            # 为什么：Worker 与本进程共用 browser-data 目录，Worker 异常退出后
            # SingletonLock/SingletonCookie/SingletonSocket 会残留，导致新 Chromium
            # 启动后无法独占 user_data_dir，表现为 launch 成功但 new_page() 报
            # "Target.createTarget: Failed to open a new tab"
            # 与 Worker 的 _cleanup_lock_files() 保持一致（browser.py#L475）
            #
            # 同时清理 Sessions/ 目录：Chromium 启动时会自动恢复历史标签，
            # 导致登录窗口出现 3 个标签（2 个 Worker 残留 + 1 个登录页）。
            # 删除 Tabs_*/Session_* 文件让 Chromium 干净启动，只打开登录需要的 1 个标签。
            # Cookie 存在 Default/Cookies SQLite，不在 Sessions/ 目录，清理不影响登录态
            import glob as _glob
            for _pattern in (
                str(user_data_dir / "SingletonLock"),
                str(user_data_dir / "SingletonCookie"),
                str(user_data_dir / "SingletonSocket"),
                str(user_data_dir / "*lock*"),
                str(user_data_dir / "Default" / "Sessions" / "Tabs_*"),
                str(user_data_dir / "Default" / "Sessions" / "Session_*"),
            ):
                for _f in _glob.glob(_pattern):
                    try:
                        Path(_f).unlink(missing_ok=True)
                    except OSError:
                        pass

            launch_start = time.monotonic()
            bc = await pw.chromium.launch_persistent_context(**launch_kwargs)
            timings["launch_context_sec"] = _elapsed_sec(launch_start)

            # 拦截非必要资源加速加载：字体、媒体、图片、manifest
            # 不拦截 stylesheet：闲鱼/淘宝登录页 CSS 来自 g.alicdn.com 等阿里 CDN，
            # 白名单难穷尽所有 CDN 域名；CSS 缺失会导致页面布局错乱、按钮不可见、
            # 扫码区域错位，得不偿失（CSS 体积通常仅几百 KB）
            # 通过域名白名单放行登录页（淘宝/支付宝登录页含扫码二维码图），
            # 否则拦截 image 会导致二维码无法显示，用户无法扫码登录
            async def _block_resources(route):
                req = route.request
                if _should_abort_login_resource(req.url, req.resource_type):
                    await route.abort()
                    return
                await route.continue_()
            await bc.route("**/*", _block_resources)

            try:
                set_status(status="opening", message="正在打开闲鱼...")
                page_start = time.monotonic()
                # 复用 launch_persistent_context 自动创建的默认 page，
                # 而非 close + new_page：关闭 context 中唯一的 page 会让
                # Edge/Chromium 某些版本进入不稳定状态，紧接的 new_page()
                # 会报 "Target.createTarget: Failed to open a new tab"
                # 兼容无默认 page 的边缘场景
                page = bc.pages[0] if bc.pages else await bc.new_page()
                timings["new_page_sec"] = _elapsed_sec(page_start)

                # 直接打开个人页：已登录显示个人页，未登录服务端自动 302 跳转到登录页
                # 比先打开首页再判断少一次 SPA 初始化，节省 1-3 秒
                goto_start = time.monotonic()
                await page.goto(
                    "https://www.goofish.com/personal",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                timings["goto_home_sec"] = _elapsed_sec(goto_start)

                # 检查是否已登录（严格验证 Cookie 值）
                # _m_h5_tk 访问首页就会自动设置，不能作为登录判据；
                # 这里严格校验 unb（>=6位数字）+ cookie2（>=10位真实会话ID），
                # 验证通过即视为已登录，无需再访问 personal 页做服务端二次验证
                # （避免开第 2 个标签导致窗口出现 3 个标签）
                cookie_start = time.monotonic()
                cookies = await bc.cookies()
                timings["initial_cookie_read_sec"] = _elapsed_sec(cookie_start)

                if _validate_login_cookies(cookies):
                    set_status(status="already_logged", message="检测到已登录状态")
                    export_start = time.monotonic()
                    final_cookies = await _prepare_login_cookie_export(
                        bc, page, _block_resources, timings
                    )
                    _export_cookies_to_json(final_cookies, "browser")
                    _save_playwright_cookies(final_cookies)
                    timings["export_cookies_sec"] = _elapsed_sec(export_start)
                    set_status(
                        status="success",
                        message="已处于登录状态",
                        cookie_count=len(final_cookies),
                    )
                    return 0

                set_status(
                    status="waiting",
                    message=f"请在浏览器窗口中登录闲鱼（{timeout}s 超时）",
                )

                # 轮询检测 Cookie（严格验证 Cookie 值，而非仅检测名称存在）
                start = time.monotonic()

                while time.monotonic() - start < timeout:
                    await asyncio.sleep(1)
                    cookies = await bc.cookies()

                    if _validate_login_cookies(cookies):
                        # 登录成功后继续预热并等待 cookie jar 稳定，避免只导出半截 cookie。
                        export_start = time.monotonic()
                        final_cookies = await _prepare_login_cookie_export(
                            bc, page, _block_resources, timings
                        )
                        final_count = len(final_cookies)
                        _export_cookies_to_json(final_cookies, "browser")
                        # 保存 Playwright 格式 Cookie 供 Worker 注入
                        _save_playwright_cookies(final_cookies)
                        timings["export_cookies_sec"] = _elapsed_sec(export_start)
                        set_status(
                            status="success",
                            message="检测到登录成功，Cookie 已保存",
                            cookie_count=final_count,
                        )
                        # 再等 2 秒让 Chromium 异步 flush SQLite：
                        # bc.close() 之前 SQLite 写入可能未完成，立即退出
                        # 会导致其他 Chromium 进程（auth_helper / Worker）读到不完整 cookie
                        await asyncio.sleep(2)
                        return 0

                    # 更新状态消息
                    names = {c["name"] for c in cookies}

                    # 每10秒更新一次状态消息
                    elapsed = int(time.monotonic() - start)
                    if elapsed % 10 < 2:
                        set_status(
                            status="waiting",
                            message=f"等待登录中... 剩余 {timeout - elapsed}s",
                            wait_elapsed=elapsed,
                        )

                set_status(status="timeout", message=f"登录超时（{timeout}s）")
                return 2

            finally:
                await bc.close()
    except Exception as e:
        _set_status(
            status_file,
            status="error",
            message=f"浏览器启动失败: {e}",
            elapsed=_elapsed_sec(flow_start),
            timings=timings,
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Playwright 有头浏览器登录")
    parser.add_argument("--status-file", required=True, help="状态文件路径 (JSON)")
    parser.add_argument("--timeout", type=int, default=300, help="登录超时秒数")
    args = parser.parse_args()

    status_file = Path(args.status_file)
    status_file.parent.mkdir(parents=True, exist_ok=True)

    _set_status(status_file, status="pending", message="初始化...")
    return asyncio.run(_cmd_login(status_file, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())
