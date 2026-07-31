"""P4-3 预聚合调度器：定时刷新 stats 接口快照到 DB

职责：每 5 分钟调用 4 个 stats 核心计算函数，将 JSON 结果写入
stats_snapshots 表。服务重启后 startup.py 从表中读取快照预热
TTL 缓存，避免首个请求 ~300ms 冷启动延迟。

线程模型：BackgroundScheduler 在独立线程触发 _refresh_job_sync，
通过 asyncio.run_coroutine_threadsafe 提交 async 任务到主事件循环
（因为 stats 计算函数都是 async def，必须在事件循环中执行）。

设计要点：
- 异步执行通过 run_coroutine_threadsafe 桥接到主事件循环
- 120s 超时防止 BackgroundScheduler 线程被慢查询永久阻塞
- max_instances=1 + coalesce=True：避免慢计算导致任务堆积
- 每次刷新覆写 snapshot_key 对应的行（UPSERT，非 INSERT）
"""
from __future__ import annotations

import json
import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# 默认扫描间隔（分钟）
_DEFAULT_INTERVAL_MIN = 5
# 异步任务超时（秒）
_REFRESH_TIMEOUT_SEC = 120


class PreAggregationScheduler:
    """预聚合调度器

    参考模式：KBRefreshScheduler（BackgroundScheduler + run_coroutine_threadsafe）
    """

    def __init__(
        self,
        container: Any,
        interval_min: int = _DEFAULT_INTERVAL_MIN,
    ) -> None:
        self._container = container
        self._interval_min = interval_min
        self._scheduler: BackgroundScheduler | None = None
        self._loop: Any = None

    def start(self, loop: Any) -> None:
        """启动定时调度（须传入主事件循环）

        为什么需要 loop：stats 计算函数是 async def，不能直接在
        BackgroundScheduler 线程中调用，必须通过 run_coroutine_threadsafe
        提交到主事件循环。
        """
        if self._scheduler:
            return
        self._loop = loop
        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduler.add_job(
            self._refresh_job_sync,
            "interval",
            minutes=self._interval_min,
            id="pre_aggregation_refresh",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self._scheduler.start()
        logger.info(
            "预聚合调度器已启动，刷新间隔 %d 分钟",
            self._interval_min,
        )

    def stop(self) -> None:
        """停止定时调度"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            self._loop = None
            logger.info("预聚合调度器已停止")

    def _refresh_job_sync(self) -> None:
        """在 BackgroundScheduler 线程中，提交异步刷新到主事件循环

        参考 KBRefreshScheduler 的 run_coroutine_threadsafe 模式：
        异步任务提交到主事件循环后阻塞等待结果，设置超时防止死锁。
        """
        import asyncio

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._refresh_all_snapshots(),
                self._loop,
            )
            future.result(timeout=_REFRESH_TIMEOUT_SEC)
        except TimeoutError:
            logger.error(
                "预聚合刷新超时（%d 秒），跳过本次刷新",
                _REFRESH_TIMEOUT_SEC,
            )
        except Exception:  # noqa: BLE001
            # 刷新失败不影响主业务，下次扫描会重试
            logger.exception("预聚合刷新任务异常")

    async def _refresh_all_snapshots(self) -> None:
        """计算并存储所有 stats 接口的快照

        依次调用 4 个核心计算函数（bypass_cache=True 确保拿到最新数据），
        将结果 JSON 序列化后 UPSERT 到 stats_snapshots 表。
        """
        from xianyu_hunter.infra.db_models import StatsSnapshotRow, _utcnow

        container = self._container
        engine = container.repo.engine
        snapshots: list[tuple[str, str, str]] = []

        # 1. business_kpi (range_days=30)
        try:
            from xianyu_hunter.web.routes.business_kpi import _compute_business_kpi
            kpi_result = await _compute_business_kpi(range_days=30, container=container, bypass_cache=True)
            snapshots.append(("business_kpi:30", json.dumps(kpi_result, ensure_ascii=False), _utcnow().isoformat()))
        except Exception:
            logger.exception("预聚合：business_kpi 计算失败")

        # 2. stats_today
        try:
            from xianyu_hunter.web.routes.stats_today import _compute_stats_today
            today_result = await _compute_stats_today(container=container, bypass_cache=True)
            snapshots.append(("stats_today", json.dumps(today_result, ensure_ascii=False), _utcnow().isoformat()))
        except Exception:
            logger.exception("预聚合：stats_today 计算失败")

        # 3. stats_overview
        try:
            from xianyu_hunter.web.routes.stats_overview import _overview
            overview_result = await _overview(container=container, bypass_cache=True)
            snapshots.append(("stats_overview", json.dumps(overview_result, ensure_ascii=False), _utcnow().isoformat()))
        except Exception:
            logger.exception("预聚合：stats_overview 计算失败")

        # 4. stats_trend (metric=events, range_hours=24)
        try:
            from xianyu_hunter.web.routes.trend import _compute_stats_trend
            trend_result = await _compute_stats_trend(
                metric="events", range_hours=24, task_id=None,
                container=container, bypass_cache=True,
            )
            snapshots.append(("stats_trend:events:24", json.dumps(trend_result, ensure_ascii=False), _utcnow().isoformat()))
        except Exception:
            logger.exception("预聚合：stats_trend 计算失败")

        if not snapshots:
            logger.warning("预聚合：所有 snapshots 计算均失败，跳过写入")
            return

        # UPSERT 到 stats_snapshots 表
        with engine.begin() as conn:
            for key, payload, ts in snapshots:
                conn.execute(
                    StatsSnapshotRow.__table__.insert()
                    .values(snapshot_key=key, payload=payload, computed_at=_utcnow())
                    .prefix_with("OR REPLACE")
                )
        logger.info(
            "预聚合刷新完成：%d 个 snapshot 已写入（keys: %s）",
            len(snapshots),
            [s[0] for s in snapshots],
        )
