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


async def _cmd_login(status_file: Path, timeout: int) -> int:
    """启动有头浏览器，等待用户登录"""
    from playwright.async_api import async_playwright

    cfg = _get_browser_cfg()
    _set_status(status_file, status="starting", message="正在启动浏览器...")

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
            }
            if edge_path:
                # 系统 Edge：干净启动，最不容易被风控检测
                launch_kwargs["executable_path"] = edge_path
                launch_kwargs["channel"] = "msedge"
            else:
                # Playwright 内置 Chromium：需要反检测参数
                launch_kwargs["args"] = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-infobars",
                ]

            # 统一使用指定 user_data_dir，确保 Cookie 写入正确位置
            launch_kwargs["user_data_dir"] = str(user_data_dir)
            bc = await pw.chromium.launch_persistent_context(**launch_kwargs)

            try:
                _set_status(status_file, status="opening", message="正在打开闲鱼...")
                page = await bc.new_page()

                # 导航到闲鱼首页
                await page.goto(
                    "https://www.goofish.com",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await page.wait_for_timeout(3000)

                # 检查是否已登录（通过 cookie 检测，比 DOM 选择器更可靠）
                cookies = await bc.cookies()
                cookie_names = {c["name"] for c in cookies}
                login_indicators = {"_m_h5_tk", "unb", "sgcookie"}
                already_logged = bool(login_indicators & cookie_names)

                if already_logged:
                    # 进一步验证：尝试访问 personal 页面确认登录态有效
                    try:
                        personal_page = await bc.new_page()
                        await personal_page.goto(
                            "https://www.goofish.com/personal",
                            wait_until="domcontentloaded",
                            timeout=15000,
                        )
                        await personal_page.wait_for_timeout(2000)
                        cur_url = personal_page.url.lower()
                        # 如果没被重定向到登录页，说明登录态有效
                        is_login_page = any(k in cur_url for k in ("/login", "passport", "mini_login"))
                        if not is_login_page:
                            _set_status(status_file, status="already_logged", message="检测到已登录状态")
                            _set_status(status_file, status="success", message="已处于登录状态")
                            await personal_page.close()
                            return 0
                        await personal_page.close()
                    except Exception:
                        pass

                _set_status(
                    status_file,
                    status="waiting",
                    message=f"请在浏览器窗口中登录闲鱼（{timeout}s 超时）",
                )

                # 轮询检测 Cookie（检查关键闲鱼 Cookie 是否出现）
                start = time.monotonic()
                prev_cookie_names: set[str] = set(cookie_names)

                while time.monotonic() - start < timeout:
                    await asyncio.sleep(2)
                    cookies = await bc.cookies()
                    names = {c["name"] for c in cookies}

                    if login_indicators & names:
                        # 登录成功：显式等待确保 Cookie 刷入磁盘
                        await page.wait_for_timeout(3000)
                        # 强制保存浏览器存储状态，确保 Cookie 写入 SQLite
                        try:
                            await bc.storage_state()
                        except Exception:
                            pass
                        # 再次读取 Cookie 并导出到 JSON（主验证数据源）
                        final_cookies = await bc.cookies()
                        final_count = len(final_cookies)
                        _export_cookies_to_json(final_cookies, "browser")
                        _set_status(
                            status_file,
                            status="success",
                            message="检测到登录成功，Cookie 已保存",
                            cookie_count=final_count,
                        )
                        # 等待足够时间确保 Cookie 写入 SQLite 数据库
                        await asyncio.sleep(3)
                        return 0

                    # 更新已知 Cookie 集合（避免重复提醒）
                    prev_cookie_names = names

                    # 每10秒更新一次状态消息
                    elapsed = int(time.monotonic() - start)
                    if elapsed % 10 < 2:
                        _set_status(
                            status_file,
                            status="waiting",
                            message=f"等待登录中... 剩余 {timeout - elapsed}s",
                            elapsed=elapsed,
                        )

                _set_status(status_file, status="timeout", message=f"登录超时（{timeout}s）")
                return 2

            finally:
                await bc.close()
    except Exception as e:
        _set_status(status_file, status="error", message=f"浏览器启动失败: {e}")
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