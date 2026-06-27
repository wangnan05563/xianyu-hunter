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
                "args": [
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-default-apps",
                    "--disable-extensions",
                ],
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
            launch_start = time.monotonic()
            bc = await pw.chromium.launch_persistent_context(**launch_kwargs)
            timings["launch_context_sec"] = _elapsed_sec(launch_start)

            try:
                set_status(status="opening", message="正在打开闲鱼...")
                page_start = time.monotonic()
                page = await bc.new_page()
                timings["new_page_sec"] = _elapsed_sec(page_start)

                # 导航到闲鱼首页
                goto_start = time.monotonic()
                await page.goto(
                    "https://www.goofish.com",
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                timings["goto_home_sec"] = _elapsed_sec(goto_start)

                # 检查是否已登录（严格验证 Cookie 值，而非仅检测名称存在）
                # _m_h5_tk 访问首页就会自动设置，不能作为登录判据
                cookie_start = time.monotonic()
                cookies = await bc.cookies()
                timings["initial_cookie_read_sec"] = _elapsed_sec(cookie_start)
                cookie_names = {c["name"] for c in cookies}

                if _validate_login_cookies(cookies):
                    # Cookie 值验证通过，进一步访问 personal 页面确认登录态有效
                    try:
                        verify_start = time.monotonic()
                        personal_page = await bc.new_page()
                        await personal_page.goto(
                            "https://www.goofish.com/personal",
                            wait_until="domcontentloaded",
                            timeout=8000,
                        )
                        timings["verify_personal_sec"] = _elapsed_sec(verify_start)
                        cur_url = personal_page.url.lower()
                        # 如果没被重定向到登录页，说明登录态有效
                        is_login_page = any(k in cur_url for k in ("/login", "passport", "mini_login"))
                        if not is_login_page:
                            set_status(status="already_logged", message="检测到已登录状态")
                            # 导出 Cookie 到 JSON 供后端验证
                            export_start = time.monotonic()
                            final_cookies = await bc.cookies()
                            _export_cookies_to_json(final_cookies, "browser")
                            # 保存 Playwright 格式 Cookie 供 Worker 注入
                            _save_playwright_cookies(final_cookies)
                            timings["export_cookies_sec"] = _elapsed_sec(export_start)
                            set_status(
                                status="success",
                                message="已处于登录状态",
                                cookie_count=len(final_cookies),
                            )
                            await personal_page.close()
                            return 0
                        else:
                            print("[browser_login] Cookie 存在但 personal 页面重定向到登录页，Cookie 可能已过期", file=sys.stderr)
                        await personal_page.close()
                    except Exception as e:
                        print(f"[browser_login] 验证登录态失败: {e}", file=sys.stderr)

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
                        # 强制保存浏览器存储状态，确保 Cookie 写入 SQLite
                        storage_start = time.monotonic()
                        try:
                            await bc.storage_state()
                        except Exception:
                            pass
                        timings["storage_state_sec"] = _elapsed_sec(storage_start)
                        # 再次读取 Cookie 并导出到 JSON（主验证数据源）
                        export_start = time.monotonic()
                        final_cookies = await bc.cookies()
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
