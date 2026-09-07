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
from xianyu_hunter.paths import get_browser_data_dir

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
        proxy_server: str = "",
    ):
        self.user_data_dir = get_browser_data_dir(user_data_dir)
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.user_agent = user_agent
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        # CDP 模式：连接已启动的系统 Edge，指纹最真实
        self.use_cdp = use_cdp
        # 代理服务器配置：
        # - 空字符串：强制禁用系统代理（--no-proxy-server），避免 Clash 等代理软件
        #   未运行时 ERR_PROXY_CONNECTION_FAILED（闲鱼国内站点无需代理）
        # - 非空：通过 --proxy-server=<url> 显式指定代理（海外部署场景）
        self.proxy_server = (proxy_server or "").strip()
        self._cdp_process: sp.Popen | None = None  # 跟踪 CDP 启动的 Edge 进程
        # 外部组件（如 BatchRefreshScheduler）正在使用的 page 集合
        # close_all_pages 跳过这些 page，避免误关并发任务正在用的页面
        # 修复场景：scheduler.run_once 结束清理时，BatchRefreshScheduler.detail() 仍在用 page
        self._external_pages: set = set()
        # 重启锁：ensure_alive 串行化浏览器重启，避免并发调用方同时重启
        # 导致 browser-data 目录锁冲突或 Playwright 多实例竞争
        self._restart_lock = asyncio.Lock()

    async def start(self) -> None:
        """启动浏览器（持久化），含自动重试和清理逻辑

        CDP 模式下启动系统 Edge 并通过 connect_over_cdp 连接，
        指纹完全真实（navigator.webdriver=undefined，无 CDP 注入痕迹）。
        launch 模式下用 Playwright 启动 Chromium + stealth 脚本。
        """
        if self._browser is not None:
            return

        _MAX_RETRIES = 2

        for attempt in range(_MAX_RETRIES + 1):
            try:
                logger.info(
                    "Starting browser: mode={}, headless={}, data={} (attempt {}/{})",
                    "cdp" if self.use_cdp else "launch", self.headless,
                    self.user_data_dir, attempt + 1, _MAX_RETRIES + 1,
                )
                self._playwright = await async_playwright().start()
                break
            except Exception as e:
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "Browser start failed (attempt {}/{}): {}, cleaning up...",
                        attempt + 1, _MAX_RETRIES + 1, e,
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
            # 代理参数：与 launch 模式保持一致，避免系统代理干扰闲鱼访问
            f"--proxy-server={self.proxy_server}" if self.proxy_server else "--no-proxy-server",
            "about:blank",
        ]
        logger.info("启动系统 Edge (CDP): {}", " ".join(cmd[:4]))
        # CDP Edge 使用 STARTUPINFO 隐藏控制台窗口（不需要像 WebView2 那样用 CREATE_NEW_CONSOLE）
        _si = sp.STARTUPINFO()
        _si.dwFlags |= sp.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0  # SW_HIDE
        # S7487：async 函数中禁止同步 subprocess 调用；sp.Popen 在事件循环中可能阻塞线程
        # 用 asyncio.to_thread 将进程启动移到工作线程，避免阻塞事件循环
        self._cdp_process = await asyncio.to_thread(
            sp.Popen,
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
        # 注意：--disable-features 只能出现一次，多个 feature 用逗号分隔
        # 为什么禁用 QUIC：国内网络环境下 QUIC 经常被防火墙拦截，
        # 触发 ERR_DNS_NO_MATCHING_SUPPORTED_ALPN 错误，强制 HTTP/2 over TCP 更稳定
        launch_args = [
            "--headless=new",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=IsolateOrigins,site-per-process,VizDisplayCompositor,Http3",
            "--disable-quic",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox",
            "--no-sandbox",
            "--disable-web-security",
            "--ignore-certificate-errors",
            "--enable-features=NetworkService,NetworkServiceInProcess",
            "--force-color-profile=srgb",
            "--metrics-recording-only",
            "--password-store=basic",
            "--use-mock-keychain",
            "--export-tagged-pdf",
            "--disable-gpu",
        ]
        # 代理参数：必须显式指定，否则 Chromium 默认读取系统代理
        # 当系统代理软件（Clash/V2Ray）未运行时会触发 ERR_PROXY_CONNECTION_FAILED
        if self.proxy_server:
            launch_args.append(f"--proxy-server={self.proxy_server}")
            logger.info("浏览器使用代理: {}", self.proxy_server)
        else:
            # 闲鱼为国内站点，默认禁用系统代理以确保连接稳定
            launch_args.append("--no-proxy-server")
            logger.info("浏览器禁用系统代理（闲鱼国内站点无需代理）")

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
        """查找系统 Edge 可执行文件路径

        检测顺序：
        1. 注册表 App Paths（识别非默认安装路径，最准确）
        2. 固定路径回退（默认安装位置）

        仅 Windows 平台执行注册表查询，其他平台直接走固定路径回退。
        """
        # 注册表查询：识别用户自定义安装路径（如 D:\Program Files\Edge\）
        if os.name == "nt":
            try:
                import winreg

                # HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe
                # 注册表值是 Edge 安装目录路径，含 msedge.exe 文件名
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
                ) as key:
                    path, _ = winreg.QueryValueEx(key, "")
                    if path and Path(path).exists():
                        return path
            # S5713: FileNotFoundError/PermissionError 都是 OSError 子类，移除冗余子类
            except OSError:
                # 注册表查询失败（非 Windows / Edge 未注册 / 权限不足）时静默回退
                pass

        # 固定路径回退：覆盖默认安装位置
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
            if self._context is None:
                raise RuntimeError("浏览器启动后 context 仍为空")
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
            if self._context is None:
                raise RuntimeError("浏览器重启后 context 仍为空")
            return await self._context.new_page()

    def register_external_page(self, page) -> None:
        """注册外部组件持有的 page，close_all_pages 不会关闭它

        用于 detail()/seller_profile() 等 own_page=True 的场景，
        防止 scheduler 在 run_once 结束清理时误关并发任务正在使用的 page。
        """
        self._external_pages.add(page)

    def unregister_external_page(self, page) -> None:
        """取消注册（page 关闭后调用，避免集合泄漏引用）"""
        self._external_pages.discard(page)

    async def close_all_pages(self) -> int:
        """关闭所有打开的页面（保留 context）

        在 scheduler 每轮 run_once 结束后调用，防止因异常未关闭的页面堆积。
        跳过 _external_pages 中外部组件（如 BatchRefreshScheduler）正在使用的 page，
        避免 TargetClosedError。
        返回关闭的页面数。
        """
        if self._context is None:
            return 0
        closed = 0
        try:
            pages = self._context.pages
            # 保留 about:blank 页面（CDP Edge 启动页），关闭其他所有页面
            for p in pages:
                # 跳过外部组件正在使用的 page（修复并发任务被误关导致的 TargetClosedError）
                if p in self._external_pages:
                    continue
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
            cookie_urls: list[str] = []
            for domain in domains or []:
                value = str(domain).strip()
                if not value:
                    continue
                if "://" in value:
                    cookie_urls.append(value)
                else:
                    cookie_urls.append(f"https://{value.lstrip('.')}")
            return await self._context.cookies(cookie_urls)
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
            injected = await self._context.cookies()
            names = {c['name'] for c in injected}
            requested = {str(c.get('name') or '') for c in cookies if c.get('name')}
            found = _KEY_COOKIES & names
            logger.info(
                'add_cookies: 注入 {} 个 Cookie，目标 Cookie 验证: {}，关键身份 Cookie: {}',
                len(cookies),
                f'✓ {requested & names}' if requested & names else '✗ 未找到目标 Cookie',
                f'✓ {found}' if found else '✗ 未找到关键身份 Cookie',
            )
            names = await _retry_missing_cookies(self._context, cookies, requested, names)
            return bool(requested & names)
        except Exception as e:
            logger.error("add_cookies 失败: {}", e)
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
        """检查浏览器是否还活着

        通过执行轻量 CDP 调用（cookies）验证底层连接可用性。
        不要求 cookies 非空：刚重启的浏览器可能没有 Cookie，但连接仍可用。

        为什么不用 context.pages：pages 是同步 property，返回内部缓存的页面对象列表，
        不会触发 CDP 请求。连接已断开时 pages 仍可访问并返回缓存列表，
        导致 is_alive 错误返回 True，ensure_alive 不触发重启，后续 add_cookies/get_cookies
        反复抛 "Connection closed while reading from the driver"（线上实测 bug）。
        """
        if self._context is None:
            return False
        try:
            # cookies() 是 async CDP 调用（Network.getAllCookies），
            # 连接已断开时会抛异常（Connection closed while reading from the driver）
            await self._context.cookies()
            return True
        except Exception:
            return False

    async def ensure_alive(self) -> bool:
        """确保浏览器连接可用，不可用时自动重启

        场景：浏览器进程崩溃/连接意外断开后，_context 仍非 None 但已失效，
        后续 add_cookies/get_cookies 会反复抛 "Connection closed while reading
        from the driver"。本方法检测到此情况后自动 close + start 重启浏览器。

        并发安全：用 asyncio.Lock 串行化重启，避免多个调用方同时重启
        导致 browser-data 目录锁冲突。

        Returns:
            True 表示浏览器存活（原本就存活或重启成功）；
            False 表示重启失败（已记日志，调用方应降级处理）。
        """
        # 快速路径：大多数情况下浏览器存活，避免 Lock 竞争
        if await self.is_alive():
            return True

        # 慢路径：需要重启，加锁串行化
        async with self._restart_lock:
            # double-check：可能在等锁期间已被其他任务重启成功
            if await self.is_alive():
                return True

            logger.warning("浏览器连接已断开，尝试重启...")
            try:
                await self.close()
            except Exception as e:
                logger.warning("ensure_alive: close 旧浏览器失败（继续启动新实例）: {}", e)

            try:
                await self.start()
                # start 不创建初始页面，验证 context 可达即可
                alive = await self.is_alive()
                if alive:
                    logger.info("浏览器重启成功")
                else:
                    logger.error("浏览器重启后 is_alive 仍为 False")
                return alive
            except Exception as e:
                logger.error("浏览器重启失败: {}", e, exc_info=True)
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



# 提取关键身份 Cookie 常量（用于验证注入结果）
_KEY_COOKIES = {"cookie2", "sgcookie", "unb"}
# 已知无害 Cookie：缺失不影响登录态，无需告警（避免注入时高频刷屏）
_BENIGN_COOKIES = {"xlly_s"}


async def _retry_missing_cookies(
    context: BrowserContext,
    cookies: list[dict],
    requested: set[str],
    current_names: set[str],
) -> set[str]:
    """对未注入成功的 Cookie 尝试显式属性重试（secure/sameSite 约束修复）

    部分真实 Edge/CDP 环境会静默丢弃 secure/sameSite 属性不匹配的 Cookie，
    这里对缺失项用标准 Lax/True 重试一次，修复大多数静默丢弃问题。
    """
    missing = requested - current_names
    if not missing:
        return current_names

    retry_items: list[dict] = []
    for c in cookies:
        if str(c.get("name") or "") in missing:
            item = dict(c)
            item["secure"] = True
            item["sameSite"] = "Lax"
            retry_items.append(item)
    try:
        await context.add_cookies(retry_items)
        re_injected = await context.cookies()
        re_names = {c["name"] for c in re_injected}
        still = missing - re_names
        # 合并原“尝试重试”+“仍缺失”两条日志为一条，避免同一次注入成对刷屏；
        # 已知无害 Cookie（如 xlly_s）缺失时降级为 DEBUG
        benign_missing = still & _BENIGN_COOKIES
        real_missing = still - _BENIGN_COOKIES
        if real_missing:
            logger.warning("add_cookies: 关键 Cookie 注入后仍缺失（已显式重试）: {}", sorted(real_missing))
        if benign_missing:
            logger.debug("add_cookies: 非关键 Cookie 未落地（已忽略）: {}", sorted(benign_missing))
        if not still:
            logger.info("add_cookies: 缺失 Cookie 已补齐: {}", sorted(missing))
        return current_names | re_names
    except Exception as e:
        logger.warning("add_cookies: 显式属性重试失败: {}", e)
        return current_names

