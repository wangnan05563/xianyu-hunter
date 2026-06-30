"""INotifier 协议 + BaseNotifier 抽象基类

BaseNotifier 内置"3 次指数退避"重试逻辑（F6.3 需求）。
"""
from __future__ import annotations

import asyncio
from typing import Protocol

from aiohttp import ClientError, ClientResponseError, ClientTimeout

from xianyu_hunter.domain.events import Event
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.modules.notifier.models import NotifyResult

logger = get_logger()


class INotifier(Protocol):
    """Notifier 协议

    实现方需提供：
        - name: 渠道唯一标识
        - send(event): 真正发起一次 HTTP 推送（只尝试 1 次，失败抛异常）
    """
    name: str

    async def send(self, event: Event) -> NotifyResult: ...


class BaseNotifier:
    """Notifier 抽象基类

    内置重试 + 超时 + 异常转 NotifyResult。子类只需实现 _do_send()。
    """

    # 默认每次请求超时 10s
    DEFAULT_TIMEOUT = 10.0
    # 默认重试 3 次，间隔指数退避 1s, 2s, 4s
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_BACKOFF = 1.0

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_backoff: float = DEFAULT_BASE_BACKOFF,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.timeout = timeout

    @property
    def name(self) -> str:
        """渠道名（子类须覆盖为类属性）"""
        raise NotImplementedError

    @property
    def is_configured(self) -> bool:
        """渠道是否已配置有效凭证

        子类根据自身密钥字段覆盖。默认 True 保留对无凭证渠道（如 webhook）的兼容。
        NotifierHub 初始化时据此过滤，避免每次事件都触发"未配置"错误。
        """
        return True

    async def send(self, event: Event) -> NotifyResult:
        """对外接口：含重试的推送

        总是返回 NotifyResult，不抛异常。调用方据此判断成功/失败。
        """
        attempts = 0
        last_error = ""
        last_response = ""
        for attempt in range(1, self.max_retries + 1):
            attempts = attempt
            try:
                response = await self._do_send(event)
                return NotifyResult(
                    success=True,
                    channel=self.name,
                    attempts=attempts,
                    response=response,
                )
            except (ClientError, asyncio.TimeoutError) as e:
                # 网络/HTTP 异常：可重试
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(
                    f"[{self.name}] 第 {attempt}/{self.max_retries} 次失败: {last_error}"
                )
            except Exception as e:
                # 未知异常：不重试，直接失败
                last_error = f"{type(e).__name__}: {e}"
                logger.exception(f"[{self.name}] 推送异常（不再重试）: {e}")
                return NotifyResult(
                    success=False,
                    channel=self.name,
                    attempts=attempt,
                    error=last_error,
                )
            # 指数退避（最后一次不等待）
            if attempt < self.max_retries:
                backoff = self.base_backoff * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)
        # 重试全部失败
        return NotifyResult(
            success=False,
            channel=self.name,
            attempts=attempts,
            response=last_response,
            error=last_error or "exhausted retries",
        )

    async def _do_send(self, event: Event) -> str:
        """子类实现：实际发起一次 HTTP 推送

        Returns: 渠道原始响应文本
        Raises: 网络/HTTP 异常（BaseNotifier 会自动重试）
        """
        raise NotImplementedError

    def _client_timeout(self) -> ClientTimeout:
        return ClientTimeout(total=self.timeout)

    def _is_retryable_http_error(self, err: ClientResponseError) -> bool:
        """判断 HTTP 状态码是否可重试（5xx + 429）"""
        return err.status >= 500 or err.status == 429
