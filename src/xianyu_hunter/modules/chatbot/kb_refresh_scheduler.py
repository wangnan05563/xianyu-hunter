"""KBRefreshScheduler — 知识库定时刷新调度器

职责：
- 定时检测文档变更，触发 KBManager.incremental_update
- 使用 BackgroundScheduler（独立线程）+ run_coroutine_threadsafe（提交到主循环）
- 不使用 AsyncIOScheduler，避免与主系统 TaskScheduler 争用事件循环

设计要点（详见 docs/chatbot-详细设计.md §5.12、docs/chatbot-概要设计.md §9.1.4）：
- 参考 batch_refresh_scheduler.py 的成熟模式
- max_instances=1 防止任务堆积，coalesce=True 错过多次触发仅执行一次
- 600 秒超时保护，避免 BackgroundScheduler 线程被永久阻塞
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from xianyu_hunter.domain.events import Event, EventType

if TYPE_CHECKING:
    from xianyu_hunter.infra.yaml_config import ChatbotKBConfig
    from xianyu_hunter.modules.chatbot.kb_manager import KBManager


# 单次刷新任务的超时保护（秒），防止 BackgroundScheduler 线程被永久阻塞
_REFRESH_TIMEOUT_SEC = 600


class KBRefreshScheduler:
    """知识库定时更新调度器

    架构选型（见概要设计 §3.12）：
    - 使用 BackgroundScheduler（独立线程）+ run_coroutine_threadsafe（提交到主循环）
    - 不使用 AsyncIOScheduler，避免与主系统 TaskScheduler 争用事件循环
    - 参考 batch_refresh_scheduler.py 的成熟模式
    """

    def __init__(
        self,
        kb_manager: "KBManager",
        config: "ChatbotKBConfig",
        event_bus=None,
    ) -> None:
        self._kb_manager = kb_manager
        self._config = config
        self._event_bus = event_bus
        self._scheduler: BackgroundScheduler | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """启动定时任务（在 startup.py 中调用，传入主事件循环）

        Args:
            loop: FastAPI 主事件循环，用于 run_coroutine_threadsafe 提交 async 任务
        """
        self._loop = loop
        # auto_update_enabled=False 时仅保存 loop 不启动调度器，
        # 便于运行时通过 restart 启用而无需重新绑定 loop
        if not self._config.auto_update_enabled:
            logger.info("知识库自动更新未启用（kb.auto_update_enabled=false）")
            return

        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduler.add_job(
            self._refresh_job_sync,
            trigger="interval",
            hours=self._config.update_interval_hours,
            id="kb_refresh",
            replace_existing=True,
            max_instances=1,  # 防止任务堆积：上一轮未完成不启动新轮
            coalesce=True,    # 错过多次触发仅执行一次
        )
        self._scheduler.start()
        logger.info(
            f"知识库定时更新已启动，间隔 {self._config.update_interval_hours} 小时"
        )

    def _refresh_job_sync(self) -> None:
        """同步入口（BackgroundScheduler 线程中执行）

        通过 run_coroutine_threadsafe 提交 async 任务到主循环，
        future.result(timeout=600) 阻塞当前线程等待完成。
        为什么不直接 await：BackgroundScheduler 线程无事件循环，
        必须提交到主循环执行 async 逻辑（KBManager.incremental_update 是 async）。
        """
        if self._loop is None or self._loop.is_closed():
            logger.warning("主事件循环已关闭，跳过知识库更新")
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._refresh_job(), self._loop)
            future.result(timeout=_REFRESH_TIMEOUT_SEC)
        except TimeoutError as e:
            # future.result 超时：任务仍在主循环中运行，但调度线程不再等待
            logger.error(f"知识库定时更新超时（>{_REFRESH_TIMEOUT_SEC}s）: {e}")
            self._publish_failure_event(e)
        except Exception as e:
            logger.exception("知识库定时更新失败")
            self._publish_failure_event(e)

    async def _refresh_job(self) -> None:
        """实际刷新逻辑（在主事件循环中执行）

        - 调用 kb_manager.incremental_update()
        - 无变更（返回 None）：记录 info 日志
        - 有变更（返回 KBVersion）：发布 CHATBOT_KB_UPDATED 事件
        - 异常时记录 error 日志（失败事件由 _refresh_job_sync 发布）
        """
        try:
            version = await self._kb_manager.incremental_update()
            if version is None:
                logger.info("知识库无变化或更新失败")
            else:
                logger.info(
                    f"知识库已更新到 {version.version_id}（{version.build_type}）"
                )
                await self._publish_event_async(
                    EventType.CHATBOT_KB_UPDATED,
                    {
                        "version_id": version.version_id,
                        "build_type": version.build_type,
                        "status": version.status,
                        "chunk_count": version.chunk_count,
                    },
                )
        except Exception as e:
            # 异常仅记录日志，失败事件由 _refresh_job_sync 的 except 分支发布
            # 避免 _refresh_job 内异常被 _refresh_job_sync 重复捕获导致双重发布
            logger.exception("知识库定时更新异常")

    def _publish_failure_event(self, error: Exception) -> None:
        """发布 CHATBOT_KB_FAILED 事件（同步方法，用 run_coroutine_threadsafe 提交）

        payload 含 error 与 timestamp，便于审计失败时间与原因。
        event_bus 为 None 或 loop 已关闭时静默跳过。
        """
        if self._event_bus is None or self._loop is None or self._loop.is_closed():
            return
        payload = {
            "error": str(error),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        asyncio.run_coroutine_threadsafe(
            self._publish_event_async(EventType.CHATBOT_KB_FAILED, payload),
            self._loop,
        )

    async def _publish_event_async(self, event_type: EventType, payload: dict) -> None:
        """发布领域事件（event_bus 为 None 时静默跳过）

        事件发布失败不影响业务流程，仅记录告警。
        """
        if self._event_bus is None:
            return
        event = Event(type=event_type, payload=payload)
        try:
            await self._event_bus.publish(event)
        except Exception as e:
            logger.warning(f"事件发布失败 {event_type.value}: {e}")

    def stop(self) -> None:
        """关闭调度器（在应用关闭时调用）

        shutdown(wait=True) 等待当前任务完成，避免知识库构建被中断导致状态不一致。
        """
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.shutdown(wait=True)
            logger.info("知识库定时更新调度器已停止")
