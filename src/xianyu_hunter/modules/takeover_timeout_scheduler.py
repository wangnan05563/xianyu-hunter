"""接管超时清理调度器

职责：定时扫描 takeover_pending 状态且超过支付截止时间的订单，
批量转为 failed 状态，避免用户误支付已被闲鱼自动关闭的订单。

业务背景：
- 用户点击「接管」后有 30 分钟在闲鱼 App 完成支付
- 闲鱼「待付款」订单默认 30 分钟自动关闭
- 系统若不清理，订单会永久卡在 takeover_pending，用户看到"接管中"状态
  可能去支付已关闭的订单，造成业务事故

设计要点：
1. 复用 APScheduler BackgroundScheduler 模式（同 cookie_sync_scheduler）
2. 同步任务，不依赖 Playwright/事件循环，可在 BackgroundScheduler 线程直接执行
3. 默认 5 分钟扫描一次：平衡时效性与 DB 开销
4. cleanup 逻辑在 repo 层一次 SQL 完成（避免 N+1）
5. 清理后发布日志事件供审计
"""
from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# 默认扫描间隔（分钟）
_DEFAULT_SCAN_INTERVAL_MIN = 5


class TakeoverTimeoutScheduler:
    """接管超时清理调度器

    线程模型：BackgroundScheduler 在独立线程定时触发 _run_cleanup_job，
    直接调用 repo.expire_takeover_pending_orders 完成 DB 操作，
    无需通过 run_coroutine_threadsafe 提交到主事件循环
    （不依赖 Playwright/async 资源）
    """

    def __init__(
        self,
        container: Any,
        timeout_min: int = 30,
        scan_interval_min: int = _DEFAULT_SCAN_INTERVAL_MIN,
    ) -> None:
        self._container = container
        self._timeout_min = timeout_min
        self._scan_interval_min = scan_interval_min
        self._scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        """启动定时调度"""
        if self._scheduler:
            return
        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduler.add_job(
            self._run_cleanup_job,
            "interval",
            minutes=self._scan_interval_min,
            id="takeover_timeout_cleanup",
            replace_existing=True,
            # 错过执行窗口不补跑：超时清理是幂等操作，下次扫描会处理
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.start()
        logger.info(
            "接管超时清理调度器已启动，扫描间隔 %d 分钟，超时阈值 %d 分钟",
            self._scan_interval_min, self._timeout_min,
        )

    def stop(self) -> None:
        """停止定时调度"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("接管超时清理调度器已停止")

    def _run_cleanup_job(self) -> None:
        """定时任务：扫描并清理超时的 takeover_pending 订单"""
        try:
            expired = self._container.repo.expire_takeover_pending_orders(self._timeout_min)
            if expired:
                order_ids = [o.get("id") for o in expired if o.get("id")]
                logger.warning(
                    "接管超时清理：%d 个订单被标记为 failed（超时 %d 分钟未支付）: %s",
                    len(expired), self._timeout_min, order_ids,
                )
        except Exception:  # noqa: BLE001
            # 清理失败不影响主业务，下次扫描会重试
            logger.exception("接管超时清理任务异常")
