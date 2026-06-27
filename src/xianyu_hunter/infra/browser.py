"""Playwright 浏览器封装（持久化 User Data Dir）

设计文档 §3.3 - 首次扫码登录后复用 Cookie。

支持两种启动模式：
1. launch 模式（默认）：Playwright 直接启动 Chromium，注入 stealth 脚本
2. CDP 模式：连接已启动的系统 Edge（--remote-debugging-port），指纹最真实
"""
from __future__ import annotations

import asyncio
import os
import subprocess as sp
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Playwright,
    async_playwright,
)

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()

# 系统 Edge 路径（Windows）
_EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
# CDP 调试端口
_CDP_PORT = 9222


class BrowserManager:
    """浏览器生命周期管理

    职责：
    - 启动 Chromium（持久化 User Data Dir，Cookie 长期保留）
    - 注入 stealth 脚本
    - 提供 context 创建
    - 健康检查
    """

    def __init__(
        self,
        user_data_dir: str | Path = "./browser-data",
        headless: bool = True,
        user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport: dict[str, int] | None = None,
        use_cdp: bool = False,
    ):
        self.user_data_dir = Path(user_data_dir)
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.user_agent = user_agent
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        # CDP 模式：连接已启动的系统 Edge，指纹最真实
        self.use_cdp = use_cdp
        self._cdp_process: sp.Popen | None = None  # 跟踪 CDP 启动的 Edge 进程

    async def start(self) -> None:
        """启动浏览器（持久化），含自动重试和清理逻辑

        CDP 模式下启动系统 Edge 并通过 connect_over_cdp 连接，
        指纹完全真实（navigator.webdriver=undefined，无 CDP 注入痕迹）。
        launch 模式下用 Playwright 启动 Chromium + stealth 脚本。
        """
        if self._browser is not None:
            return

        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                logger.info(
                    "Starting browser: mode={}, headless={}, data={} (attempt {}/{})",
                    "cdp" if self.use_cdp else "launch", self.headless,
                    self.user_data_dir, attempt + 1, max_retries + 1,
                )
                self._playwright = await async_playwright().start()
                break
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(
                        "Browser start failed (attempt {}/{}): {}, cleaning up...",
                        attempt + 1, max_retries + 1, e,
                    )
                    self._cleanup_orphan_processes()
                    self._cleanup_lock_files()
                    await asyncio.sleep(2)
                else:
                    raise

        if self.use_cdp:
            await self._start_cdp()
        else:
            await self._start_launch()

    async def _start_cdp(self) -> None:
        """CDP 模式：启动系统 Edge 并通过 connect_over_cdp 连接

        优势：Edge 是用户手动安装的真实浏览器，指纹完全自然，
        不会暴露 navigator.webdriver=true 或 CDP 注入痕迹。
        """
        edge_path = self._find_edge()
        if not edge_path:
            logger.warning("未找到系统 Edge，回退到 launch 模式")
            self.use_cdp = False
            await self._start_launch()
            return

        # 启动 Edge 并开启远程调试端口
        self._cleanup_lock_files()
        cmd = [
            edge_path,
            f"--remote-debugging-port={_CDP_PORT}",
            f"--user-data-dir={self.user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-minimized",  # 最小化启动，避免 new_page() 时弹出可见窗口
            "about:blank",
        ]
        logger.info("启动系统 Edge (CDP): {}", " ".join(cmd[:4]))
        # CDP Edge 使用 STARTUPINFO 隐藏控制台窗口（不需要像 WebView2 那样用 CREATE_NEW_CONSOLE）
        _si = sp.STARTUPINFO()
        _si.dwFlags |= sp.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0  # SW_HIDE
        self._cdp_process = sp.Popen(
            cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL,
            startupinfo=_si if os.name == "nt" else None,
        )

        # 等待 CDP 端口就绪（最多 10 秒）
        import socket
        cdp_ready = False
        for _ in range(20):
            try:
                with socket.create_connection(("127.0.0.1", _CDP_PORT), timeout=0.5):
                    cdp_ready = True
                    break
            except (ConnectionRefusedError, socket.timeout):
                await asyncio.sleep(0.5)

        if not cdp_ready:
            logger.error("Edge CDP 端口 {} 未就绪，回退到 launch 模式", _CDP_PORT)
            self._kill_cdp_process()
            self.use_cdp = False
            await self._start_launch()
            return

        # 通过 CDP 连接到已启动的 Edge
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{_CDP_PORT}"
            )
            # 获取已有的 BrowserContext（Edge 启动时自动创建的）
            if self._browser.contexts:
                self._context = self._browser.contexts[0]
            else:
                self._context = await self._browser.new_context()
            logger.info("CDP 连接成功，使用系统 Edge 浏览器（指纹真实）")
        except Exception as e:
            logger.error("CDP 连接失败: {}，回退到 launch 模式", e)
            self._kill_cdp_process()
            self.use_cdp = False
            await self._start_launch()

    async def _start_launch(self) -> None:
        """launch 模式：Playwright 直接启动 Chromium + stealth 脚本

        集成 LoginOrchestrator 的 FingerprintProfile：
        - 若 orchestrator 已初始化（launch 模式），使用 profile 生成的一致指纹脚本
          和 profile 的 UA/viewport，保证指纹内部一致（UA ↔ GPU ↔ 屏幕）
        - 若 orchestrator 未初始化，回退到原有 STEALTH_SCRIPT_V2，保持向后兼容
        """
        # 反爬启动参数：--headless=new（Chromium ≥128）比旧 headless 更难检测
        launch_args = [
            "--headless=new",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox",
            "--no-sandbox",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--ignore-certificate-errors",
            "--enable-features=NetworkService,NetworkServiceInProcess",
            "--force-color-profile=srgb",
            "--metrics-recording-only",
            "--password-store=basic",
            "--use-mock-keychain",
            "--export-tagged-pdf",
            "--disable-gpu",
        ]

        # 尝试从 LoginOrchestrator 获取指纹 profile
        # 若 orchestrator 已初始化且为 launch 模式，使用 profile 的 UA 和 viewport
        # 保证 UA ↔ GPU ↔ 屏幕分辨率三者一致，避免被 AWSC fireyejs 识破
        effective_ua = self.user_agent
        effective_viewport = self.viewport
        stealth_scripts: list[str] = []

        try:
            from xianyu_hunter.modules.login_orchestrator import get_orchestrator
            orch = get_orchestrator()
            profile = orch.get_fingerprint_profile()
            if profile is not None:
                # 使用 profile 的 UA 和 viewport，保证一致性
                effective_ua = profile.ua
                effective_viewport = {
                    "width": profile.screen_width,
                    "height": profile.screen_height,
                }
                stealth_scripts = orch.get_stealth_scripts()
                logger.info(
                    "使用 FingerprintProfile: name={}, ua={}, viewport={}",
                    profile.name, profile.ua[:50], effective_viewport,
                )
        except Exception as e:
            logger.debug("未使用 LoginOrchestrator 指纹（回退到默认）: {}", e)

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            user_agent=effective_ua,
            viewport=effective_viewport,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=launch_args,
        )

        # 注入 stealth 脚本
        # 优先使用 orchestrator 提供的脚本（基于 FingerprintProfile），
        # 否则回退到原有 STEALTH_SCRIPT_V2 + M5TK_AUTO_REFRESH_SCRIPT
        from xianyu_hunter.modules.anti_detect import STEALTH_SCRIPT_V2, M5TK_AUTO_REFRESH_SCRIPT

        if stealth_scripts:
            for script in stealth_scripts:
                await self._context.add_init_script(script)
            # M5TK 自动刷新脚本与指纹无关，始终注入
            await self._context.add_init_script(M5TK_AUTO_REFRESH_SCRIPT)
            logger.info(
                "浏览器启动完成，已注入 {} 个指纹脚本 + m5tk 自动刷新脚本",
                len(stealth_scripts),
            )
        else:
            await self._context.add_init_script(STEALTH_SCRIPT_V2)
            await self._context.add_init_script(M5TK_AUTO_REFRESH_SCRIPT)
            logger.info("浏览器启动完成，stealth + m5tk 自动刷新脚本已注入（默认）")

        self._browser = self._context.browser

    @staticmethod
    def _find_edge() -> str | None:
        """查找系统 Edge 可执行文件路径"""
        for p in _EDGE_PATHS:
            if Path(p).exists():
                return p
        return None

    def _kill_cdp_process(self) -> None:
        """关闭 CDP 启动的 Edge 进程"""
        if self._cdp_process:
            try:
                self._cdp_process.terminate()
                self._cdp_process.wait(timeout=5)
            except Exception:
                try:
                    self._cdp_process.kill()
                except Exception:
                    pass
            self._cdp_process = None

    async def new_page(self):
        """创建新标签页

        若浏览器 context 已关闭（用户手动关 Edge / CDP 崩溃），
        自动重启浏览器后重试一次，避免抛出 TargetClosedError 导致整轮搜索失败。
        """
        if self._context is None:
            await self.start()
            assert self._context is not None
            return await self._context.new_page()
        try:
            return await self._context.new_page()
        except Exception as e:
            # TargetClosedError / 任何浏览器已关闭的异常：重启后重试一次
            logger.warning("new_page 失败 ({})，重启浏览器后重试...", type(e).__name__)
            try:
                await self.close()
            except Exception:
                pass
            await self.start()
            assert self._context is not None
            return await self._context.new_page()

    async def close_all_pages(self) -> int:
        """关闭所有打开的页面（保留 context）

        在 scheduler 每轮 run_once 结束后调用，防止因异常未关闭的页面堆积。
        返回关闭的页面数。
        """
        if self._context is None:
            return 0
        closed = 0
        try:
            pages = self._context.pages
            # 保留 about:blank 页面（CDP Edge 启动页），关闭其他所有页面
            for p in pages:
                try:
                    if p.url not in ("about:blank", "chrome://newtab/"):
                        await p.close()
                        closed += 1
                except Exception:
                    pass
        except Exception:
            pass
        return closed

    async def get_cookies(self, domains: list[str] | None = None) -> list[dict]:
        """从浏览器 context 实时读取 cookies

        CDP 模式下直接读取系统 Edge 的实时 cookie，比读 SQLite 更准确、无需复制文件。

        Args:
            domains: 可选域名过滤，如 ["goofish.com", "taobao.com"]；为空则返回全部

        Returns:
            cookie 列表，每项含 name/value/domain/path/expires/httpOnly/secure 等字段
        """
        if self._context is None:
            return []
        try:
            return await self._context.cookies(domains or [])
        except Exception as e:
            logger.warning("get_cookies 失败: {}", e)
            return []

    async def add_cookies(self, cookies: list[dict]) -> bool:
        """向浏览器 context 注入 cookies（登录成功后同步到 Worker 实例）

        解决 browser_login.py 子进程写入 browser-data SQLite 后，
        Worker 已运行的浏览器实例内存中缺少登录 Cookie 的问题。

        Args:
            cookies: Playwright cookie 对象列表

        Returns:
            True 表示注入成功
        """
        if self._context is None:
            logger.warning("add_cookies: 浏览器 context 未初始化，跳过注入")
            return False
        if not cookies:
            return False
        try:
            await self._context.add_cookies(cookies)
            # 验证关键 Cookie 是否已注入
            injected = await self._context.cookies()
            names = {c["name"] for c in injected}
            key_cookies = {"cookie2", "sgcookie", "unb"}
            found = key_cookies & names
            logger.info(
                "add_cookies: 注入 {} 个 Cookie，关键 Cookie 验证: {}",
                len(cookies),
                f"✓ {found}" if found else "✗ 未找到关键 Cookie",
            )
            return bool(found)
        except Exception as e:
            logger.error("add_cookies 失败: {}", e)
            return False

    async def is_alive(self) -> bool:
        """检查浏览器是否还活着

        通过访问 context.pages 属性验证底层连接是否可用。
        不创建新页面（避免弹窗），仅读取已有页面列表。
        """
        if self._context is None:
            return False
        try:
            # 访问 pages 属性会触发底层 CDP 请求，
            # 若连接已断开会抛出异常
            _ = self._context.pages
            return True
        except Exception:
            return False

    def _cleanup_orphan_processes(self) -> None:
        """杀掉残留的 msedge/chromium 进程（非当前浏览器实例）

        WebView2 登录后可能留下孤儿 msedge 进程，
        这些进程锁住 browser-data 目录导致新 Playwright 实例无法启动。
        """
        if os.name != "nt":
            return
        try:
            import subprocess as sp
            # 只杀没有窗口标题的 msedge（Playwright headless 模式的残留进程）
            sp.run(
                ["taskkill", "/F", "/IM", "msedge.exe", "/FI", "WINDOWTITLE eq "],
                capture_output=True, timeout=10,
            )
            logger.info("Cleaned orphan msedge processes")
        except Exception as e:
            logger.warning("Failed to clean orphan processes: {}", e)

    def _cleanup_lock_files(self) -> None:
        """清理 browser-data 中的残留锁文件

        Chromium 的 SingletonLock、CDP socket 等文件在非正常退出后可能残留，
        导致新实例无法获取独占访问。
        """
        import glob as g

        patterns = [
            str(self.user_data_dir / "SingletonLock"),
            str(self.user_data_dir / "SingletonCookie"),
            str(self.user_data_dir / "SingletonSocket"),
            str(self.user_data_dir / "*lock*"),
        ]
        cleaned = 0
        for pattern in patterns:
            for f in g.glob(pattern):
                try:
                    Path(f).unlink(missing_ok=True)
                    cleaned += 1
                except OSError:
                    pass
        if cleaned:
            logger.info("Removed {} stale lock files from {}", cleaned, self.user_data_dir)

    async def is_alive(self) -> bool:
        """检查浏览器是否还活着"""
        if self._context is None:
            return False
        try:
            # 尝试执行简单JS来验证浏览器是否真正存活
            pages = self._context.pages
            if not pages:
                return False
            await pages[0].evaluate("1+1")
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """关闭浏览器（保留 Cookie）"""
        if self._context is not None:
            try:
                # CDP 模式下不关闭 context（会关闭用户的 Edge），
                # 只断开 Playwright 连接
                if self.use_cdp:
                    # connect_over_cdp 的 context 不需要 close，
                    # 断开 browser 连接即可
                    pass
                else:
                    await self._context.close()
            except Exception as e:
                logger.warning(f"关闭 context 失败: {e}")
            self._context = None
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning(f"关闭 browser 失败: {e}")
            self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"关闭 playwright 失败: {e}")
            self._playwright = None
        # CDP 模式下关闭启动的 Edge 进程
        self._kill_cdp_process()
        logger.info("浏览器已关闭")

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
