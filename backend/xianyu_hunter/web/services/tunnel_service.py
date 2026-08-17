# backend/xianyu_hunter/web/services/tunnel_service.py
"""内网穿透服务：委托给具体 provider 实现。

设计决策：
- TunnelService 作为薄封装，持有当前 provider 实例并委托生命周期管理
- provider 选择由配置驱动（yaml_config.TunnelConfig.provider）
- 切换 provider 时需先 stop 当前隧道再创建新 provider
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Optional

from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.web.services.tunnel_providers import (
    TunnelProvider,
    create_provider,
)

logger = logging.getLogger(__name__)


class TunnelService:
    """隧道生命周期管理（委托给 provider）"""

    def __init__(
        self,
        local_port: int = 8000,
        on_started: Callable[[str, str, int], None] | None = None,
    ):
        self._local_port = local_port
        self._provider: Optional[TunnelProvider] = None
        self._provider_name: str = ""
        self._on_started = on_started

    def _resolve_port(self) -> int:
        """解析实际本地端口：环境变量 > yaml tunnel.local_port > yaml server.port"""
        # 环境变量优先：__main__.py web 命令 --port 启动时设置
        env_port = os.environ.get("XH_WEB_PORT")
        if env_port:
            try:
                return int(env_port)
            except ValueError:
                logger.warning(f"XH_WEB_PORT 非法值: {env_port}，忽略")

        cfg = get_config().tunnel
        if cfg.local_port > 0:
            return cfg.local_port
        # 回退到 server.port
        return get_config().server.port

    def _ensure_provider(self) -> TunnelProvider:
        """按当前配置创建/复用 provider 实例"""
        cfg = get_config().tunnel
        provider_name = cfg.provider

        # 配置未变且 provider 已存在：复用
        if self._provider is not None and self._provider_name == provider_name:
            return self._provider

        # 切换 provider：先停止旧实例
        if self._provider is not None:
            self._provider.stop()
            self._provider = None

        port = self._resolve_port()
        # 按 provider 类型传递专属参数
        kwargs: dict = {"binary_path": cfg.binary_path}
        if provider_name == "cpolar":
            kwargs["authtoken"] = cfg.cpolar_authtoken
        elif provider_name == "tailscale":
            # 路径区分模式：path_prefix 非空时启用多应用路径前缀
            kwargs["path_prefix"] = cfg.path_prefix
        elif provider_name == "cloudflare":
            # Named Tunnel 参数：quick 模式下这些值被忽略
            kwargs.update(
                tunnel_mode=cfg.tunnel_mode,
                tunnel_name=cfg.tunnel_name,
                tunnel_id=cfg.tunnel_id,
                credentials_file=cfg.credentials_file,
                hostname=cfg.hostname,
                cert_file=cfg.cert_file,
            )

        self._provider = create_provider(provider_name, port, **kwargs)
        self._provider_name = provider_name
        return self._provider

    @property
    def status(self) -> str:
        """返回隧道状态：running / stopped"""
        if self._provider is None:
            return "stopped"
        return self._provider.status

    @property
    def public_url(self) -> Optional[str]:
        if self._provider is None:
            return None
        return self._provider.public_url

    @property
    def provider_name(self) -> str:
        """当前 provider 名称（供 API 返回）"""
        return self._provider_name

    def start(self) -> str:
        """启动隧道，返回公网 HTTPS URL"""
        provider = self._ensure_provider()
        public_url = provider.start()
        if self._on_started:
            try:
                self._on_started(self._provider_name, public_url, self._resolve_port())
            except Exception as exc:
                logger.warning(f"隧道已启动，但启动通知调度失败: {exc}")
        return public_url

    def stop(self) -> None:
        """停止隧道"""
        if self._provider:
            self._provider.stop()
