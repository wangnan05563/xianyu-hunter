# src/xianyu_hunter/web/services/tunnel_providers.py
"""内网穿透 Provider 插件化实现。

设计决策：
- 抽象基类 TunnelProvider 定义统一接口，TunnelService 委托具体实现
- 每个_provider 管理自己的二进制下载与命令构造，隔离差异
- 多镜像源下载：主源失败自动切换备源，全部失败抛出含手动放置指引的异常
- cpolar 需 authtoken，首次启动前自动执行 `cpolar authtoken <TOKEN>` 写入配置
"""
from __future__ import annotations

import logging
import os
import re
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


class BinaryDownloadError(RuntimeError):
    """二进制下载失败，附带手动放置指引"""

    def __init__(self, message: str, manual_path: str, download_urls: list[str]):
        super().__init__(message)
        # 前端读取这两个字段渲染手动放置指引
        self.manual_path = manual_path
        self.download_urls = download_urls


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
        """从子进程输出中解析公网 URL（通用实现）"""
        deadline = time.time() + timeout
        found_url: list[str] = []

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
                logger.debug(f"[{self.binary_name}] {text.strip()}")

        thread = threading.Thread(target=read_output, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if not found_url:
            self.stop()
            raise RuntimeError(f"[{self.binary_name}] 启动超时，未能获取公网 URL")
        return found_url[0]

    def _start_process(self, cmd: list[str], url_pattern: re.Pattern, timeout: int = 15) -> str:
        """启动子进程并解析公网 URL（通用流程）

        使用 CREATE_NO_WINDOW 而非 CREATE_NEW_CONSOLE：
        - cloudflared/cpolar 是命令行工具，无需 GUI 窗口
        - CREATE_NO_WINDOW 静默运行，stdout 仍可重定向到 PIPE 供解析
        - 注意：WebView2/Playwright 仍需 CREATE_NEW_CONSOLE（项目硬约束），但此处不涉及
        """
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        url = self._wait_for_url(url_pattern, timeout=timeout)
        logger.info(f"[{self.binary_name}] 隧道已建立: {url}")
        return url


class CloudflareProvider(TunnelProvider):
    """Cloudflare quick tunnel：无需账号，自动分配 trycloudflare 域名"""

    binary_name = "cloudflared.exe"
    # 多镜像源：GitHub 主源 + jsDelivr CDN 备源（大陆访问更稳定）
    download_urls = [
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
        "https://cdn.jsdelivr.net/gh/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
    ]

    def start(self) -> str:
        if self.status == "running":
            return self._public_url or ""
        self._binary_path = self._ensure_binary()
        cmd = [
            str(self._binary_path),
            "tunnel",
            "--url", f"http://localhost:{self._local_port}",
            "--no-autoupdate",
        ]
        # trycloudflare.com 域名
        url_pattern = re.compile(r"(https://[a-z0-9-]+\.trycloudflare\.com)")
        self._public_url = self._start_process(cmd, url_pattern)
        return self._public_url


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
        """首次启动前配置 authtoken（写入 cpolar 配置文件，只需一次）"""
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

    def start(self) -> str:
        if self.status == "running":
            return self._public_url or ""
        self._binary_path = self._ensure_binary()
        self._configure_authtoken(self._binary_path)
        # cpolar http <port> 启动 HTTP 隧道，输出 Forwarding https://xxx.cpolar.top
        cmd = [str(self._binary_path), "http", str(self._local_port)]
        # cpolar 域名后缀多样：.cpolar.top / .cpolar.io / .cpolar.cn
        url_pattern = re.compile(r"(https://[a-z0-9-]+\.(?:cpolar\.(?:top|io|cn|com)))")
        self._public_url = self._start_process(cmd, url_pattern)
        return self._public_url


# provider 注册表：新增 provider 只需在此注册，无需改动 TunnelService
_PROVIDER_REGISTRY: dict[str, type[TunnelProvider]] = {
    "cloudflare": CloudflareProvider,
    "cpolar": CpolarProvider,
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
