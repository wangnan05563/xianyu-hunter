# backend/xianyu_hunter/web/services/tunnel_providers.py
"""内网穿透 Provider 插件化实现。

设计决策：
- 抽象基类 TunnelProvider 定义统一接口，TunnelService 委托具体实现
- 每个_provider 管理自己的二进制下载与命令构造，隔离差异
- 多镜像源下载：主源失败自动切换备源，全部失败抛出含手动放置指引的异常
- cpolar 需 authtoken，首次启动前自动执行 `cpolar authtoken <TOKEN>` 写入配置
"""
from __future__ import annotations

import logging
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from xianyu_hunter.paths import get_data_dir

logger = logging.getLogger(__name__)

# S1192: 重复字面量提取为常量
# cloudflared 配置目录名（多平台一致）
_CLOUDFLARED_DIR = ".cloudflared"
# cloudflared 证书文件名
_CERT_PEM_FILE = "cert.pem"


class BinaryDownloadError(RuntimeError):
    """二进制下载失败，附带手动放置指引"""

    def __init__(self, message: str, manual_path: str, download_urls: list[str]):
        super().__init__(message)
        # 前端读取这两个字段渲染手动放置指引
        self.manual_path = manual_path
        self.download_urls = download_urls


class TailscaleFunnelAuthError(RuntimeError):
    """Tailscale Funnel 首次启用需要用户在浏览器完成授权

    携带授权链接和操作指引，让前端能渲染可点击的超链接引导用户完成授权。
    auth_url 优先使用命令输出的一次性链接（含 node 参数，直接授权当前节点），
    无链接时回退到管理后台 Funnel 配置页
    """

    # 回退链接：Tailscale 管理后台 Funnel 配置页
    FALLBACK_AUTH_URL = "https://login.tailscale.com/admin/dns/funnel"

    def __init__(self, message: str, auth_url: str | None = None):
        super().__init__(message)
        self.auth_url = auth_url or self.FALLBACK_AUTH_URL


class TunnelProvider(ABC):
    """穿透 provider 抽象基类"""

    # 子类覆盖：二进制文件名
    binary_name: str = ""
    # 子类覆盖：下载源列表（按优先级排序，主源 → 备源）
    download_urls: list[str] = []

    def __init__(self, local_port: int, binary_path: str = ""):
        self._local_port = local_port
        # 用户手动放置的二进制路径（可选，优先于自动下载）
        self._manual_binary_path = binary_path or ""
        self._process: Optional[subprocess.Popen] = None
        self._public_url: Optional[str] = None
        self._binary_path: Optional[Path] = None

    @property
    def status(self) -> str:
        """返回隧道状态：running / stopped"""
        if self._process is None:
            # _public_url 存在表示 start() 已成功（含 mock 测试场景），视为运行中
            return "running" if self._public_url else "stopped"
        if self._process.poll() is None:
            return "running"
        # 进程已退出，清理状态
        self._process = None
        self._public_url = None
        return "stopped"

    @property
    def public_url(self) -> Optional[str]:
        return self._public_url

    @abstractmethod
    def start(self) -> str:
        """启动隧道，返回公网 HTTPS URL"""

    def stop(self) -> None:
        """停止隧道（通用实现：terminate → wait → kill）"""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._public_url = None
        logger.info(f"[{self.binary_name}] 隧道已关闭")

    # ---------- 通用工具方法 ----------

    def _ensure_binary(self) -> Path:
        """确保二进制存在：优先用户手动放置路径，其次自动下载"""
        # 用户手动放置优先：允许离线环境预先放好二进制
        if self._manual_binary_path:
            manual = Path(self._manual_binary_path)
            if manual.exists():
                logger.info(f"[{self.binary_name}] 使用手动放置的二进制: {manual}")
                return manual
            logger.warning(
                f"[{self.binary_name}] 配置的 binary_path 不存在: {manual}，回退到自动下载"
            )

        data_dir = get_data_dir()
        data_dir.mkdir(exist_ok=True)
        binary_path = data_dir / self.binary_name

        if not binary_path.exists():
            logger.info(f"[{self.binary_name}] 二进制不存在，开始下载...")
            self._download_binary(binary_path)
        return binary_path

    def _download_binary(self, target: Path) -> None:
        """多镜像源下载：按 download_urls 顺序尝试，全部失败抛 BinaryDownloadError"""
        last_error: Exception | None = None
        for url in self.download_urls:
            try:
                logger.info(f"[{self.binary_name}] 尝试下载源: {url}")
                self._do_download(url, target)
                logger.info(f"[{self.binary_name}] 下载完成: {target}")
                return
            except Exception as e:
                logger.warning(f"[{self.binary_name}] 下载源失败 {url}: {e}")
                last_error = e

        # 全部失败：抛出含指引的异常，前端可渲染手动放置步骤
        raise BinaryDownloadError(
            f"{self.binary_name} 所有下载源均失败: {last_error}",
            manual_path=str(get_data_dir() / self.binary_name),
            download_urls=self.download_urls,
        )

    def _do_download(self, url: str, target: Path) -> None:
        """实际下载逻辑（子类可覆盖以处理 zip 解压等）"""
        urllib.request.urlretrieve(url, str(target))

    def _wait_for_url(self, url_pattern: re.Pattern, timeout: int = 15) -> str:
        """从子进程输出中解析公网 URL（通用实现）

        超时时收集最近 20 行 stdout 输出和进程状态包含在异常消息中，
        让调用方和前端能看到 CLI 实际输出了什么、进程是否存活
        """
        deadline = time.time() + timeout
        found_url: list[str] = []
        # 收集最近输出：超时诊断的关键信息，否则用户无法定位原因
        recent_lines: list[str] = []

        def read_output():
            if self._process is None or self._process.stdout is None:
                return
            while time.time() < deadline and not found_url:
                line = self._process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="ignore")
                match = url_pattern.search(text)
                if match:
                    found_url.append(match.group(1))
                    return
                self._collect_recent_output_line(text, recent_lines)

        thread = threading.Thread(target=read_output, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if not found_url:
            self._raise_url_timeout_error(timeout, recent_lines)
        return found_url[0]

    def _collect_recent_output_line(self, text: str, recent_lines: list[str]) -> None:
        """收集子进程输出最近 20 行用于超时诊断，超长时丢弃旧行避免内存增长"""
        stripped = text.strip()
        if not stripped:
            return
        recent_lines.append(stripped)
        if len(recent_lines) > 20:
            recent_lines.pop(0)
        logger.info(f"[{self.binary_name}] {stripped}")

    def _describe_process_status(self) -> str:
        """生成子进程状态描述用于错误诊断：无输出时判断是已退出还是卡住"""
        if self._process is None:
            return "未知"
        poll_result = self._process.poll()
        if poll_result is None:
            return "仍在运行（可能卡住等待输入或网络连接）"
        return f"已退出（exit code={poll_result}）"

    def _raise_url_timeout_error(self, timeout: int, recent_lines: list[str]) -> None:
        """超时后收集诊断信息并抛出异常：先停进程再拼装输出"""
        process_status = self._describe_process_status()
        self.stop()
        recent_output = "\n".join(recent_lines[-20:]) if recent_lines else "（无输出）"
        raise RuntimeError(
            f"[{self.binary_name}] 启动超时（{timeout}s），未能获取公网 URL。\n"
            f"进程状态: {process_status}\n"
            f"最近输出:\n{recent_output}"
        )

    def _start_process(self, cmd: list[str], url_pattern: re.Pattern, timeout: int = 15) -> str:
        """启动子进程并解析公网 URL（通用流程）

        使用 CREATE_NO_WINDOW 而非 CREATE_NEW_CONSOLE：
        - cloudflared/cpolar 是命令行工具，无需 GUI 窗口
        - CREATE_NO_WINDOW 静默运行，stdout 仍可重定向到 PIPE 供解析
        - 注意：WebView2/Playwright 仍需 CREATE_NEW_CONSOLE（项目硬约束），但此处不涉及

        stdin=DEVNULL：防止子进程卡在等待用户输入（cpolar 首次运行可能提示确认）
        """
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        url = self._wait_for_url(url_pattern, timeout=timeout)
        logger.info(f"[{self.binary_name}] 隧道已建立: {url}")
        return url


class CloudflareProvider(TunnelProvider):
    """Cloudflare 隧道：支持 quick（临时域名）和 named（固定域名）两种模式

    - quick 模式：无需账号，自动分配 trycloudflare 域名，每次重启变化
    - named 模式：需 Cloudflare 账号 + 托管域名，通过 login/create/route-dns 一次性配置后域名永久固定
    """

    binary_name = "cloudflared.exe"
    # 多镜像源：GitHub 主源 + jsDelivr CDN 备源（大陆访问更稳定）
    download_urls = [
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
        "https://cdn.jsdelivr.net/gh/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
    ]

    def __init__(
        self,
        local_port: int,
        binary_path: str = "",
        tunnel_mode: str = "quick",
        tunnel_name: str = "",
        tunnel_id: str = "",
        credentials_file: str = "",
        hostname: str = "",
        cert_file: str = "",
    ):
        super().__init__(local_port, binary_path)
        self._tunnel_mode = tunnel_mode
        self._tunnel_name = tunnel_name
        self._tunnel_id = tunnel_id
        self._credentials_file = credentials_file
        self._hostname = hostname
        self._cert_file = cert_file
        # login 异步状态：start_login 启动子进程后，check_login_status 轮询
        self._login_process: Optional[subprocess.Popen] = None
        self._login_auth_url: Optional[str] = None
        self._login_output: list[str] = []

    def start(self) -> str:
        if self.status == "running":
            return self._public_url or ""
        self._binary_path = self._ensure_binary()
        if self._tunnel_mode == "named":
            return self._start_named_tunnel()
        return self._start_quick_tunnel()

    def _start_quick_tunnel(self) -> str:
        """Quick Tunnel：临时域名，每次启动随机分配"""
        # --no-autoupdate 是全局标志，必须在子命令 tunnel 之前
        cmd = [
            str(self._binary_path),
            "--no-autoupdate",
            "tunnel",
            "--url", f"http://localhost:{self._local_port}",
        ]
        url_pattern = re.compile(r"(https://[a-z0-9-]+\.trycloudflare\.com)")
        self._public_url = self._start_process(cmd, url_pattern)
        return self._public_url

    def _start_named_tunnel(self) -> str:
        """Named Tunnel：固定域名，使用 config.yml + cloudflared tunnel run

        前置条件：用户已通过 setup 向导完成 login/create/route-dns，配置了 tunnel_id、
        credentials_file 和 hostname。此处仅负责生成 config.yml 并启动 run 命令。
        """
        if not self._tunnel_id:
            raise RuntimeError("Named Tunnel 模式需要配置 tunnel_id（请先执行创建隧道步骤）")
        if not self._credentials_file:
            raise RuntimeError("Named Tunnel 模式需要配置 credentials_file 路径")
        if not self._hostname:
            raise RuntimeError("Named Tunnel 模式需要配置 hostname（固定域名）")

        cred_path = Path(self._credentials_file)
        if not cred_path.exists():
            raise RuntimeError(f"凭证文件不存在: {cred_path}，请重新执行创建隧道步骤")

        # 动态生成 config.yml：ingress 规则将 hostname 流量路由到本地端口
        config_path = self._generate_config_yml()
        cmd = [
            str(self._binary_path),
            "--config", str(config_path),
            "--no-autoupdate",
            "tunnel", "run",
        ]
        # named tunnel 启动成功标志：多版本兼容（Registered tunnel connection / Registered tunnel connector）
        ready_pattern = re.compile(r"(Registered tunnel (?:connection|connector))")
        self._start_process(cmd, ready_pattern, timeout=60)
        # 域名是固定的，直接用配置的 hostname
        self._public_url = f"https://{self._hostname}"
        logger.info(f"[cloudflared] Named Tunnel 已建立: {self._public_url}")
        return self._public_url

    def _generate_config_yml(self) -> Path:
        """生成 cloudflared config.yml（ingress 规则将 hostname → localhost:port）

        每次启动都重新生成：local_port 可能从配置继承不同值，确保 ingress 指向正确端口
        """
        import yaml

        config_dir = get_data_dir() / "cloudflared"
        config_dir.mkdir(exist_ok=True)
        config_path = config_dir / "config.yml"

        config_data = {
            "tunnel": self._tunnel_id,
            "credentials-file": str(Path(self._credentials_file).resolve()),
            "ingress": [
                {"hostname": self._hostname, "service": f"http://localhost:{self._local_port}"},
                {"service": "http_status:404"},
            ],
        }
        config_path.write_text(
            yaml.safe_dump(config_data, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        logger.debug(f"[cloudflared] 生成 config.yml: {config_path}")
        return config_path

    # ---------- Named Tunnel 一次性配置辅助方法 ----------

    def _find_cert_pem_paths(self) -> list[Path]:
        """查找所有可能的 cert.pem 位置

        cloudflared 在不同平台/版本可能使用不同的配置目录：
        - Windows 默认: %USERPROFILE%\\.cloudflared\\cert.pem
        - 部分 Windows 版本: %LOCALAPPDATA%\\.cloudflared\\cert.pem
        - 从 login 输出中提取的路径（兜底）
        """
        paths: list[Path] = [Path.home() / _CLOUDFLARED_DIR / _CERT_PEM_FILE]
        # Windows 上部分版本使用 LOCALAPPDATA
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            paths.append(Path(local_app_data) / _CLOUDFLARED_DIR / _CERT_PEM_FILE)
        # APPDATA 兜底
        app_data = os.environ.get("APPDATA")
        if app_data:
            paths.append(Path(app_data) / _CLOUDFLARED_DIR / _CERT_PEM_FILE)
        # 从 login 输出中正则提取路径（cloudflared 可能输出 cert.pem 的绝对路径）
        output = "".join(self._login_output)
        # 匹配 Windows 路径 (C:\...\cert.pem) 和 Unix 路径 (/.../cert.pem)
        m = re.search(r"([A-Za-z]:[\\\/][^\s]*cert\.pem|/[^\s]*cert\.pem)", output)
        if m:
            paths.append(Path(m.group(1)))
        return paths

    def start_login(self) -> dict:
        """启动 cloudflared tunnel login（非阻塞），返回授权 URL 和状态

        login 是交互式命令：cloudflared 会打开浏览器让用户授权。
        此方法用 Popen 启动子进程，后台线程读取 stdout 提取授权 URL，
        然后立即返回，不等待用户完成浏览器操作。
        前端通过 check_login_status() 轮询 cert.pem 是否生成。

        返回:
            {"status": "waiting", "auth_url": "...", "message": "..."}
            或 {"status": "failed", "message": "...", "output": "..."}
        """
        # 如果已有 login 在进行中，直接返回当前状态
        if self._login_process is not None and self._login_process.poll() is None:
            return {
                "status": "waiting",
                "auth_url": self._login_auth_url,
                "message": "login 已在进行中，请在浏览器中完成授权",
            }

        binary = self._ensure_binary()
        # --no-autoupdate 是全局标志，必须在子命令 tunnel 之前
        cmd = [str(binary), "--no-autoupdate", "tunnel", "login"]

        # 不用 capture_output（会阻塞到命令完成），改用 Popen + 后台线程实时读取
        self._login_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self._login_auth_url = None
        self._login_output = []

        # 后台线程实时读取 stdout，提取授权 URL
        thread = threading.Thread(target=self._read_login_output, daemon=True)
        thread.start()
        # 等待最多 10 秒，看能否提取到授权 URL 或进程退出
        self._wait_for_login_url_or_exit(timeout=10)
        return self._build_login_result()

    def _read_login_output(self) -> None:
        """后台线程：实时读取 login 子进程 stdout，匹配到授权 URL 即记录

        cloudflared login 输出的授权 URL 格式：https://dash.cloudflare.com/argotunnel?...
        """
        if self._login_process is None or self._login_process.stdout is None:
            return
        # 仅编译一次：线程内反复编译无意义且影响可读性
        url_pattern = re.compile(r"(https://[^\s]+)")
        for line in self._login_process.stdout:
            self._login_output.append(line)
            self._try_capture_login_url(line, url_pattern)
            logger.debug(f"[cloudflared login] {line.strip()}")

    def _try_capture_login_url(self, line: str, url_pattern: re.Pattern) -> None:
        """从输出行中提取授权 URL，仅首次匹配成功后记录

        多次输出相同 URL 时不覆盖，避免后续 unrelated 日志把 auth_url 清掉
        """
        line_stripped = line.strip()
        if not line_stripped or self._login_auth_url is not None:
            return
        match = url_pattern.search(line_stripped)
        # 必须包含 cloudflare，避免匹配到无关 URL（如文档链接）
        if match and "cloudflare" in match.group(1):
            self._login_auth_url = match.group(1)
            logger.info(f"[cloudflared] login 授权 URL: {self._login_auth_url}")

    def _wait_for_login_url_or_exit(self, timeout: int) -> None:
        """等待授权 URL 出现或进程退出，最多 timeout 秒

        超过 timeout 仍未提取到 URL 也返回，由 _build_login_result 决定如何回复前端
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._login_auth_url or self._login_process.poll() is not None:
                return
            time.sleep(0.5)

    def _build_login_result(self) -> dict:
        """根据 login 进程当前状态构造返回结果：URL 优先 / 进程退出 / 仍在运行"""
        if self._login_auth_url:
            return {
                "status": "waiting",
                "auth_url": self._login_auth_url,
                "message": "请在浏览器中完成 Cloudflare 授权",
            }

        # 进程已退出但未提取到 URL
        if self._login_process.poll() is not None:
            output = "".join(self._login_output)
            exit_code = self._login_process.returncode
            self._login_process = None
            return {
                "status": "failed",
                "message": f"cloudflared login 进程已退出（exit code={exit_code}）",
                "output": output,
            }

        # 进程仍在运行但未输出 URL：浏览器可能已自动打开
        return {
            "status": "waiting",
            "auth_url": None,
            "message": "cloudflared login 已启动，浏览器应该已自动打开。如果未打开，请稍等...",
        }

    def check_login_status(self) -> dict:
        """检查 login 状态：检查 cert.pem 是否已生成

        前端轮询此方法，直到 status 变为 success 或 failed。

        返回:
            {"status": "success", "cert_file": "...", "message": "..."}
            {"status": "waiting", "auth_url": "...", "message": "..."}
            {"status": "failed", "message": "...", "output": "...", "checked_paths": [...]}
            {"status": "idle", "message": "login 未启动"}
        """
        if self._login_process is None:
            return {"status": "idle", "message": "login 未启动"}

        # 检查所有可能的 cert.pem 位置
        cert_paths = self._find_cert_pem_paths()
        for path in cert_paths:
            if path.exists():
                # login 成功：清理子进程引用
                self._cleanup_login_process()
                return {
                    "status": "success",
                    "cert_file": str(path),
                    "message": "授权成功，cert.pem 已生成",
                }

        # 检查进程是否已退出
        if self._login_process.poll() is not None:
            output = "".join(self._login_output)
            exit_code = self._login_process.returncode
            self._login_process = None
            if exit_code == 0:
                # 进程退出码 0 但没找到 cert.pem
                return {
                    "status": "failed",
                    "message": "login 进程已退出但未找到 cert.pem",
                    "output": output,
                    "checked_paths": [str(p) for p in cert_paths],
                }
            return {
                "status": "failed",
                "message": f"login 失败（exit code={exit_code}）",
                "output": output,
            }

        # 仍在等待用户在浏览器中完成授权
        return {
            "status": "waiting",
            "auth_url": self._login_auth_url,
            "message": "等待用户在浏览器中完成授权...",
        }

    def _cleanup_login_process(self) -> None:
        """清理 login 子进程：terminate → wait → kill"""
        if self._login_process is None:
            return
        try:
            self._login_process.terminate()
            self._login_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._login_process.kill()
        except Exception as e:
            logger.warning(f"[cloudflared] 清理 login 子进程异常: {e}")
        finally:
            self._login_process = None

    def setup_create(self, tunnel_name: str, cert_file: str = "", timeout: int = 60) -> dict:
        """执行 cloudflared tunnel create <name>，返回 tunnel_id 和 credentials_file

        需要 cert.pem（login 生成）。如果 cert_file 未指定，使用 provider 配置的 cert_file。
        """
        binary = self._ensure_binary()
        # --no-autoupdate 是全局标志，必须在子命令 tunnel 之前
        cmd = [str(binary), "--no-autoupdate", "tunnel"]
        if cert_file:
            cmd.extend(["--origincert", cert_file])
        elif self._cert_file:
            cmd.extend(["--origincert", self._cert_file])
        cmd.extend(["create", tunnel_name])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout + "\n" + result.stderr
        if result.returncode != 0:
            raise RuntimeError(
                f"cloudflared tunnel create 失败 (exit={result.returncode}): {output.strip()}"
            )
        # 从输出解析 tunnel_id（UUID 格式）和 credentials_file 路径
        # 典型输出：Created tunnel <UUID> with credentials file /path/to/<UUID>.json
        id_match = re.search(
            r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", output, re.I
        )
        # 兼容新旧 cloudflared 输出：
        # - Created tunnel ... with credentials file <path>
        # - Tunnel credentials written to <path>
        # 路径可能被引号包裹，也可能包含空格。
        cred_match = re.search(
            r"(?:credentials file|tunnel credentials written to)\s+\"?(.+?\.json)\"?",
            output, re.I,
        )
        if not id_match or not cred_match:
            raise RuntimeError(f"无法从 create 输出中解析 tunnel_id 或 credentials_file: {output.strip()}")
        cred_path = cred_match.group(1).strip()
        return {
            "tunnel_id": id_match.group(1),
            "credentials_file": cred_path,
            "tunnel_name": tunnel_name,
        }

    def setup_route_dns(
        self, tunnel_name_or_id: str, hostname: str, cert_file: str = "", timeout: int = 60
    ) -> str:
        """执行 cloudflared tunnel route dns <name> <hostname>，创建 CNAME 记录

        需要 cert.pem。hostname 必须是已托管在 Cloudflare DNS 的域名子域。
        """
        binary = self._ensure_binary()
        # --no-autoupdate 是全局标志，必须在子命令 tunnel 之前
        cmd = [str(binary), "--no-autoupdate", "tunnel"]
        if cert_file:
            cmd.extend(["--origincert", cert_file])
        elif self._cert_file:
            cmd.extend(["--origincert", self._cert_file])
        cmd.extend(["route", "dns", tunnel_name_or_id, hostname])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout + "\n" + result.stderr
        if result.returncode != 0:
            raise RuntimeError(
                f"cloudflared route dns 失败 (exit={result.returncode}): {output.strip()}"
            )
        return f"https://{hostname}"


class CpolarProvider(TunnelProvider):
    """cpolar 内网穿透：国内服务器稳定，需 authtoken 配置"""

    binary_name = "cpolar.exe"
    # 下载源说明：
    # - 旧源 cdn.cpolar.com 已废弃（DNS 不可解析，触发 SSL EOF 错误）
    # - 现采用官网真实下载路径 www.cpolar.com/static/downloads/releases/
    # - 主源用 latest 自动跟随最新版；备源固定 3.3.18 版本，防 latest 重定向异常
    # - 两源均为纯 zip（内含 cpolar.exe 单文件），匹配 _do_download 的解压逻辑
    download_urls = [
        "https://www.cpolar.com/static/downloads/releases/latest/cpolar-stable-windows-amd64.zip",
        "https://www.cpolar.com/static/downloads/releases/3.3.18/cpolar-stable-windows-amd64.zip",
    ]

    def __init__(self, local_port: int, authtoken: str = "", binary_path: str = ""):
        super().__init__(local_port, binary_path)
        # authtoken 从配置注入，首次启动时写入 cpolar 配置文件
        self._authtoken = authtoken

    def _do_download(self, url: str, target: Path) -> None:
        """cpolar 下载的是 zip，需解压后提取 exe"""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            urllib.request.urlretrieve(url, str(tmp_path))
            with zipfile.ZipFile(tmp_path, "r") as zf:
                # zip 内可能嵌套目录，查找 cpolar.exe
                exe_names = [n for n in zf.namelist() if n.endswith("cpolar.exe")]
                if not exe_names:
                    raise RuntimeError("cpolar zip 内未找到 cpolar.exe")
                # 解压到临时目录再移动到 target
                extract_dir = tmp_path.parent / f"cpolar_extract_{int(time.time())}"
                zf.extractall(extract_dir)
                src_exe = extract_dir / exe_names[0]
                os.replace(src_exe, target)
        finally:
            # 清理临时文件
            if tmp_path.exists():
                tmp_path.unlink()

    def _configure_authtoken(self, binary: Path) -> None:
        """首次启动前配置 authtoken（写入 cpolar 配置文件，只需一次）

        返回 authtoken 命令的完整输出，供 start 失败时诊断
        """
        if not self._authtoken:
            raise RuntimeError(
                "cpolar 需要配置 authtoken，请在设置页填写或访问 https://dashboard.cpolar.com/signup 获取"
            )
        # cpolar authtoken 命令会将 token 写入用户目录配置文件，幂等操作
        result = subprocess.run(
            [str(binary), "authtoken", self._authtoken],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            raise RuntimeError(f"cpolar authtoken 配置失败: {result.stderr or result.stdout}")
        logger.info(f"[cpolar] authtoken 配置成功: {(result.stdout or '').strip()}")

    def start(self) -> str:
        if self.status == "running":
            return self._public_url or ""
        self._binary_path = self._ensure_binary()
        self._configure_authtoken(self._binary_path)
        # cpolar http <port> 启动 HTTP 隧道，输出 Tunnel established at https://xxx.cpolar.top
        # --log stdout 确保日志输出到 stdout 而非文件，否则 _wait_for_url 读不到任何输出
        cmd = [str(self._binary_path), "http", str(self._local_port), "--log", "stdout"]
        # 域名格式：xxx.cpolar.top / xxx.r5.cpolar.top（含区域中间层）
        # 正则必须匹配多级子域名，否则 URL 已输出但正则不匹配导致超时
        url_pattern = re.compile(r"(https://[a-z0-9-]+(?:\.[a-z0-9]+)*\.cpolar\.[a-z]+)")
        # 超时 40s：cpolar 免费版首次连接服务器分配域名需 ~22s
        self._public_url = self._start_process(cmd, url_pattern, timeout=40)
        return self._public_url


class TailscaleProvider(TunnelProvider):
    """Tailscale Funnel：使用已安装并登录的 Tailscale 提供固定 ts.net 地址。

    Tailscale CLI 只负责配置系统后台服务，因此运行状态不能用子进程存活判断，
    必须通过 ``tailscale funnel status --json`` 查询。

    多应用路径区分模式：通过 path_prefix 在同一节点的 443 端口下分配独立路径，
    Funnel 自动剥离前缀转发给后端，实现单节点多应用共存。
    """

    binary_name = "tailscale.exe"
    download_urls: list[str] = []

    def __init__(self, local_port: int, binary_path: str = "", path_prefix: str = ""):
        """初始化 Tailscale provider。

        path_prefix 非空时启用多应用路径区分模式：
        - start 用 --set-path 注册路径，URL 为 https://{host}{path_prefix}
        - stop 不调用 funnel off，避免关闭其他应用的 Funnel 路径
        """
        super().__init__(local_port, binary_path)
        # 规范化路径前缀：确保以 / 开头、以 / 结尾，空字符串表示根路径模式（旧行为）
        self._path_prefix = self._normalize_path_prefix(path_prefix)

    @staticmethod
    def _normalize_path_prefix(prefix: str) -> str:
        """规范化路径前缀为 /xxx/ 形式，空字符串表示根路径模式。"""
        if not prefix:
            return ""
        p = prefix.strip()
        if not p.startswith("/"):
            p = "/" + p
        if not p.endswith("/"):
            p = p + "/"
        return p

    def _ensure_binary(self) -> Path:
        if self._manual_binary_path:
            manual = Path(self._manual_binary_path)
            if manual.exists():
                return manual
            raise RuntimeError(f"配置的 Tailscale 路径不存在: {manual}")

        discovered = shutil.which("tailscale")
        if discovered:
            return Path(discovered)

        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        standard_path = Path(program_files) / "Tailscale" / "tailscale.exe"
        if standard_path.exists():
            return standard_path

        raise RuntimeError(
            "未检测到 Tailscale。请先安装并登录 Tailscale："
            "https://tailscale.com/download/windows"
        )

    def _run_cli(self, *args: str, timeout: int = 20) -> subprocess.CompletedProcess:
        if self._binary_path is None:
            self._binary_path = self._ensure_binary()
        # 显式指定 UTF-8 解码：tailscale CLI 输出固定为 UTF-8，
        # 中文 Windows 默认用 GBK 解码会导致含非 ASCII 字符的 JSON 解析失败
        result = subprocess.run(
            [str(self._binary_path), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            output = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"Tailscale 命令执行失败: {output or result.returncode}")
        return result

    @staticmethod
    def _parse_json_output(output: str, command: str) -> dict:
        try:
            data = json.loads(output)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"无法解析 {command} 输出，请确认 Tailscale 版本为最新版") from exc
        if not isinstance(data, dict):
            raise RuntimeError(f"{command} 返回了无效的 JSON 对象")
        return data

    def _funnel_url_from_status(self, data: dict) -> str | None:
        """从 funnel status --json 提取当前应用的公网 URL。

        多应用路径模式下，URL 包含 path_prefix（如 https://host/xianyu/）；
        根路径模式下，URL 为 https://host（旧行为）。
        通过匹配 Handlers 中的路径前缀确认当前应用的 Funnel 配置是否存在。
        """
        host = self._extract_funnel_host(data)
        if not host:
            return None
        if self._path_prefix:
            return self._check_funnel_path_prefix(data, host)
        return f"https://{host}"

    @staticmethod
    def _extract_funnel_host(data: dict) -> str | None:
        """从 AllowFunnel 中提取第一个启用 Funnel 的 ts.net 主机名"""
        allow_funnel = data.get("AllowFunnel")
        if not isinstance(allow_funnel, dict):
            return None
        for endpoint, enabled in allow_funnel.items():
            if not enabled:
                continue
            h = str(endpoint).rsplit(":", 1)[0].rstrip(".")
            if h.lower().endswith(".ts.net"):
                return h
        return None

    def _check_funnel_path_prefix(self, data: dict, host: str) -> str | None:
        """路径区分模式：检查 Handlers 中是否存在自己的路径前缀"""
        web = data.get("Web", {})
        handlers = {}
        if isinstance(web, dict):
            for _endpoint, cfg in web.items():
                if isinstance(cfg, dict) and "Handlers" in cfg:
                    handlers = cfg["Handlers"]
                    break
        if not isinstance(handlers, dict) or self._path_prefix not in handlers:
            return None
        return f"https://{host}{self._path_prefix}"

    @property
    def status(self) -> str:
        if self._binary_path is None:
            return "stopped"
        try:
            result = self._run_cli("funnel", "status", "--json")
            data = self._parse_json_output(result.stdout, "tailscale funnel status")
            self._public_url = self._funnel_url_from_status(data)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            logger.warning(f"[tailscale] 查询 Funnel 状态失败: {exc}")
            self._public_url = None
        return "running" if self._public_url else "stopped"

    def start(self) -> str:
        self._binary_path = self._ensure_binary()
        dns_name = self._get_tailscale_dns_name()
        # 用 Popen 非阻塞读取输出，而非 subprocess.run 阻塞等待。
        # 原因：tailscale funnel --bg --yes 在首次启用时会输出授权链接后不退出，
        # 等待用户在浏览器完成授权。用 subprocess.run 会阻塞 60s，
        # 而前端 axios 30s 就超时了，用户看不到授权指引。
        # 改为 Popen + 读取输出，检测到授权链接立即提取并返回错误
        process = self._start_funnel_process()

        auth_url_match: list[str] = []
        recent_lines: list[str] = []
        if self._read_funnel_output(process, dns_name, auth_url_match, recent_lines):
            return self._public_url or ""

        self._terminate_funnel_process(process)
        self._raise_funnel_failure(process, auth_url_match, recent_lines)

    def _get_tailscale_dns_name(self) -> str:
        """校验 Tailscale 已登录并启用 MagicDNS，返回可用的 ts.net DNS 名"""
        status_result = self._run_cli("status", "--json")
        status_data = self._parse_json_output(status_result.stdout, "tailscale status")
        if status_data.get("BackendState") != "Running":
            raise RuntimeError("请先打开并登录 Tailscale，然后重新启动隧道")

        self_info = status_data.get("Self")
        dns_name = self_info.get("DNSName", "") if isinstance(self_info, dict) else ""
        dns_name = str(dns_name).strip().rstrip(".")
        if not dns_name.lower().endswith(".ts.net"):
            raise RuntimeError("Tailscale 尚未启用 MagicDNS，无法生成固定 ts.net 地址")
        return dns_name

    def _start_funnel_process(self) -> subprocess.Popen:
        """启动 funnel 子进程：--bg 后台运行，--yes 跳过交互确认

        路径区分模式用 --set-path 注册路径前缀，Funnel 自动剥离前缀转发给后端。
        """
        funnel_args = ["funnel", "--bg", "--yes"]
        if self._path_prefix:
            funnel_args += ["--set-path", self._path_prefix]
        funnel_args.append(f"http://127.0.0.1:{self._local_port}")
        return subprocess.Popen(
            [str(self._binary_path), *funnel_args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def _read_funnel_output(
        self,
        process: subprocess.Popen,
        dns_name: str,
        auth_url_match: list[str],
        recent_lines: list[str],
    ) -> bool:
        """读取 funnel 进程输出，成功返回 True

        三种退出条件：检测到成功标志（返回 True）、授权链接 break、进程退出或超时（返回 False）
        """
        deadline = time.time() + 30
        while time.time() < deadline:
            line = process.stdout.readline() if process.stdout else ""
            if not line:
                if process.poll() is not None:
                    return False
                time.sleep(0.2)
                continue
            stripped = line.strip()
            if stripped:
                recent_lines.append(stripped)
                logger.info(f"[tailscale] {stripped}")
            # 检测一次性授权链接：tailscale 输出格式为 https://login.tailscale.com/f/funnel?node=xxx
            url_match = re.search(r"(https://login\.tailscale\.com/f/funnel\?node=\S+)", stripped)
            if url_match:
                auth_url_match.append(url_match.group(1))
                return False
            # 检测成功标志：funnel 已建立
            if "Funnel started" in stripped or "listening on" in stripped.lower():
                self._public_url = f"https://{dns_name}{self._path_prefix}"
                logger.info(f"[tailscale] Funnel 已建立: {self._public_url}")
                return True
        return False

    def _terminate_funnel_process(self, process: subprocess.Popen) -> None:
        """终止 funnel 子进程：terminate → wait → kill"""
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    def _raise_funnel_failure(
        self,
        process: subprocess.Popen,
        auth_url_match: list[str],
        recent_lines: list[str],
    ) -> None:
        """根据 funnel 进程退出状态抛出对应异常：授权链接优先 / 失败 / 超时"""
        if auth_url_match:
            raise TailscaleFunnelAuthError(
                "首次启用 Funnel 需要在浏览器完成授权，请点击下方链接完成授权后重新启动隧道",
                auth_url=auth_url_match[0],
            )

        # 检查进程是否已退出
        exit_code = process.returncode
        recent_output = "\n".join(recent_lines[-20:]) if recent_lines else "（无输出）"
        if exit_code is not None and exit_code != 0:
            raise RuntimeError(
                f"Tailscale Funnel 启动失败（exit code={exit_code}）。\n输出:\n{recent_output}"
            )
        raise RuntimeError(
            f"Tailscale Funnel 启动超时（30s），未能确认 Funnel 状态。\n"
            f"进程状态: {'已退出' if exit_code is not None else '仍在运行'}\n"
            f"输出:\n{recent_output}"
        )

    def stop(self) -> None:
        # 路径区分模式：不调用 funnel off，避免关闭其他应用的 Funnel 路径
        # Tailscale 无移除单个路径的命令，停止后路径配置保留（访问会连接失败），
        # 重新启动应用后 --set-path 幂等更新配置自动恢复
        #
        # 同时清除 _binary_path：让 status 属性走短路返回 "stopped"，
        # 避免查询 tailscale funnel status --json 时因 Funnel 仍活跃而返回 "running"。
        if self._path_prefix:
            self._public_url = None
            self._binary_path = None
            logger.info(f"[tailscale] 路径区分模式：保留 Funnel 配置 {self._path_prefix}")
            return

        # 根路径模式（旧行为）：关闭整个 Funnel
        # 捕获异常不抛出：stop 失败不应阻塞配置保存或服务关闭等调用方操作
        # timeout=10s：funnel off 是本地命令应很快返回，
        # Tailscale 服务未运行时命令会卡住等待连接，10s 足够判断
        if self._binary_path is not None:
            try:
                self._run_cli("funnel", "off", timeout=10)
            except Exception as e:
                logger.warning(f"[tailscale] 关闭 Funnel 失败（忽略）: {e}")
        self._public_url = None
        logger.info("[tailscale] Funnel 已关闭")


# provider 注册表：新增 provider 只需在此注册，无需改动 TunnelService
_PROVIDER_REGISTRY: dict[str, type[TunnelProvider]] = {
    "cloudflare": CloudflareProvider,
    "cpolar": CpolarProvider,
    "tailscale": TailscaleProvider,
}


def create_provider(
    provider_name: str, local_port: int, **kwargs
) -> TunnelProvider:
    """工厂函数：按名称创建 provider 实例

    未知 provider 抛 ValueError，避免静默回退到默认值导致用户困惑
    """
    cls = _PROVIDER_REGISTRY.get(provider_name)
    if cls is None:
        raise ValueError(
            f"未知的 tunnel provider: {provider_name}，可选: {list(_PROVIDER_REGISTRY.keys())}"
        )
    return cls(local_port=local_port, **kwargs)
