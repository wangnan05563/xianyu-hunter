"""批量采集调度器

职责：定时（默认每 30 分钟）刷新在售（is_sold=0）商品的详情，
检测已售状态、补全字段变更。

设计要点：
1. 参照 cookie_sync_scheduler.py 的 APScheduler BackgroundScheduler 模式。
2. collector.detail() 是 async 且依赖 Playwright（绑定主事件循环），
   不能在 BackgroundScheduler 线程的临时事件循环中调用。
   因此 _run_batch_job 通过 run_coroutine_threadsafe 提交到主事件循环执行。
3. 复用 api_items.py refresh_item 端点的合并写库逻辑：
   - 构造 new_row → upsert_item（items 表）
   - is_sold 时调用 mark_sold（补写 sold_detected_at + 同步 task_links.display）
   - sync_item_display_from_detail（合并 task_links.display）
4. 失败重试：单商品失败记录原因并跳过，连续失败超过阈值时暂停当前批次，
   避免浏览器实例异常时持续无效请求。
5. 变更日志：记录 item_id、变更字段列表、时间戳到内存状态，供 API 查询。
6. 任务控制（pause/resume/stop）：
   - 通过 asyncio.Event 实现暂停/继续，_pause_event.clear() 阻塞，set() 恢复
   - 通过 _stop_flag 实现停止，循环中检查后 break
   - 暂停时持久化待处理 item_id 到 batch_refresh_progress 表，支持断点续传
7. 资源调度优化：每个 item 处理后 await asyncio.sleep(0.3) 让出事件循环，
   确保主业务请求优先处理，避免批量采集独占事件循环。
8. 执行历史持久化（batch_refresh_history 表）：
   - 启动时从 DB MAX(task_id) 初始化自增计数器，跨进程重启不重置
   - 批次开始时插入 running 状态记录，结束时更新为终态（completed/cancelled/failed）
   - 采集中累积错误消息（上限 50 条），结束时一并写入历史记录
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from xianyu_hunter.infra.db_models import BatchRefreshProgressRow
from xianyu_hunter.modules.collection_service import (
    CollectionError,
    CollectionMode,
    ItemCollectionService,
)

logger = logging.getLogger(__name__)

# 变更日志内存上限（避免无限增长导致 OOM）
_MAX_CHANGE_LOG = 1000
# 单次采集超时（秒），与 refresh_item 端点一致
_DETAIL_TIMEOUT = 60.0
# 单次批量任务整体超时（秒），防止 BackgroundScheduler 线程被 future.result 永久阻塞
_BATCH_TIMEOUT = 3600
# 每个 item 处理后让出事件循环的时间（秒）
# 为什么需要：批量采集是低优先级后台任务，sleep 让出控制权给主业务请求，
# 避免在大量商品采集时阻塞 API 响应。
_YIELD_INTERVAL = 0.3
# 单批次累积错误消息上限：避免大量失败时 error_messages JSON 字段无限膨胀
_MAX_ERROR_MESSAGES = 50


@dataclass
class _BatchCounters:
    """批次采集计数器

    为什么用 dataclass 而非局部变量：_run_batch_async 主流程需要将计数器
    传递给 _process_items_loop 子方法，dataclass 提供可变引用避免逐个返回值聚合。
    """
    success: int = 0
    failed: int = 0
    skipped: int = 0
    consecutive_failures: int = 0
    # 标记是否因熔断退出（区别于用户停止）
    circuit_broken: bool = False
    processed: int = 0


class BatchRefreshScheduler:
    """批量采集调度器

    线程模型：BackgroundScheduler 在独立线程触发 _run_batch_job，
    通过 run_coroutine_threadsafe 提交到主事件循环执行 async 采集逻辑。
    为什么这样做：collector.detail 依赖 Playwright，绑定主事件循环，
    不能在 BackgroundScheduler 线程的临时事件循环中调用。

    状态机：
        idle ──trigger──> running ──pause──> paused ──resume──> running
          ↑                │                   │
          │                │                   └──stop──> stopping ──> idle
          └──all done──────┴──stop───────────────────┘
    """

    def __init__(
        self,
        container: Any,
        config: Any,
        fail_pause_threshold: int = 3,
    ) -> None:
        self._container = container
        self._config = config  # BatchRefreshConfig 实例（引用，热更新生效）
        self._fail_pause_threshold = fail_pause_threshold
        self._scheduler: BackgroundScheduler | None = None
        self._main_loop: asyncio.AbstractEventLoop | None = None

        # 运行状态：idle | running | paused | stopping
        # 单值原子性足够，BackgroundScheduler 线程与主循环线程均可读写
        self._status: str = "idle"
        self._last_run_at: str | None = None
        self._last_result: dict[str, int] | None = None
        self._change_log: list[dict] = []
        # task_id 自增计数器：从历史表 MAX(task_id) 初始化，跨进程重启不重置
        # 为什么不用 DB 自增：task_id 是业务字段（progress 表/历史表/日志均引用），
        # 需在调度器内存中维护以便 trigger_now 立即返回给前端
        try:
            self._current_task_id: int = container.repo.get_max_batch_refresh_task_id()
        except Exception as e:  # noqa: BLE001
            # 历史表首次创建或查询失败时回退到 0，不影响启动
            logger.warning(f"初始化 task_id 失败，回退到 0: {e}")
            self._current_task_id = 0

        # 任务控制（仅在 _run_batch_async 执行期间有效）
        # asyncio.Event 必须在事件循环内创建，所以延迟到 _run_batch_async 中初始化
        self._pause_event: asyncio.Event | None = None
        self._stop_flag: bool = False
        # 进度信息（None 表示无批次在运行）
        self._progress: dict | None = None
        # 当前批次对应的历史记录 ID，结束时用于 UPDATE 终态字段
        self._current_history_id: int | None = None
        # 当前批次累积的错误消息（list[dict]，结束时序列化为 JSON 写入历史表）
        self._current_errors: list[dict] = []

    def start(self, main_loop: asyncio.AbstractEventLoop) -> None:
        """启动定时调度

        Args:
            main_loop: FastAPI 主事件循环，用于提交 async 采集任务到 Playwright
        """
        if self._scheduler:
            return
        self._main_loop = main_loop
        self._scheduler = BackgroundScheduler(daemon=True)
        # next_run_time 设为启动后 10 秒：APScheduler interval 触发器默认首次执行时间是
        # start_time + interval（即启动后还要等 30 分钟），用户感知不到调度器在工作。
        # 设 10 秒延迟而非立即执行：给浏览器/collector 初始化留时间，避免首次采集因
        # 浏览器未就绪而连续失败触发熔断。
        next_run = datetime.now() + timedelta(seconds=10)
        self._scheduler.add_job(
            self._run_batch_job,
            "interval",
            minutes=self._config.interval_minutes,
            next_run_time=next_run,
            id="batch_refresh",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(
            "批量采集调度器已启动，间隔 %d 分钟，首次执行于 %s",
            self._config.interval_minutes,
            next_run.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def stop(self) -> None:
        """停止定时调度（关闭 APScheduler，不干预当前批次的运行）"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            self._main_loop = None
            logger.info("批量采集调度器已停止")

    def is_running(self) -> bool:
        """当前是否有批次正在执行（含暂停态，因为暂停态下协程仍在阻塞中）"""
        return self._status in ("running", "paused", "stopping")

    def get_status(self) -> dict:
        """返回当前状态（供 API 端点调用）"""
        return {
            "status": self._status,
            "last_run_at": self._last_run_at,
            "last_result": self._last_result,
            # 仅返回最近 50 条变更日志，避免响应体过大
            "change_log": list(self._change_log[-50:]),
            "enabled": self._config.enabled,
            "interval_minutes": self._config.interval_minutes,
            # 进度信息：current/total/current_item_id/started_at/elapsed_ms
            "progress": self._get_progress_snapshot(),
            # 是否允许 pause/resume/stop 操作
            "control_available": self._status in ("running", "paused"),
        }

    def trigger_now(self, source: str = "manual") -> int:
        """手动触发一次批量采集，返回任务 ID

        Args:
            source: 触发来源 manual=用户手动 / scheduler=APScheduler 定时

        Returns:
            任务 ID（正整数）；-1 表示调度器未启动或已有批次在运行
        """
        if self._main_loop is None or self.is_running():
            return -1
        self._current_task_id += 1
        task_id = self._current_task_id
        # 提交到主事件循环异步执行（不等待完成，让 API 立即返回）
        asyncio.run_coroutine_threadsafe(
            self._run_batch_async(task_id, source), self._main_loop
        )
        return task_id

    def pause(self) -> bool:
        """暂停当前批次

        立即更新状态为 paused 并 clear event，但实际暂停在当前 item 处理完成
        后生效（await event.wait() 阻塞）。这样保证当前 item 的数据库写入完整。

        Returns:
            True 表示暂停请求已接受；False 表示当前状态不允许暂停
        """
        if self._status != "running":
            return False
        self._status = "paused"
        if self._pause_event is not None:
            self._pause_event.clear()
        logger.info("[BatchRefresh] 用户请求暂停，将在当前商品采集完成后生效")
        return True

    def resume(self) -> bool:
        """继续执行已暂停的批次

        Returns:
            True 表示继续请求已接受；False 表示当前状态不在暂停态
        """
        if self._status != "paused":
            return False
        self._status = "running"
        if self._pause_event is not None:
            self._pause_event.set()
        logger.info("[BatchRefresh] 用户请求继续执行")
        return True

    def stop_current(self) -> bool:
        """停止当前批次

        立即更新状态为 stopping 并 set event（解除暂停阻塞），让循环继续到
        _stop_flag 检查后 break。未处理的 items 会持久化以便下次续传。

        Returns:
            True 表示停止请求已接受；False 表示当前状态不允许停止
        """
        if self._status not in ("running", "paused"):
            return False
        self._stop_flag = True
        self._status = "stopping"
        # 解除暂停阻塞，让循环继续到 stop_flag 检查
        if self._pause_event is not None:
            self._pause_event.set()
        logger.info("[BatchRefresh] 用户请求停止，将在当前商品采集完成后生效")
        return True

    def update_config(
        self,
        interval_minutes: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        """运行时热更新配置

        修改调度器持有的 config 引用字段，同时 reschedule 已注册的 job。
        enabled=False 时立即暂停定时触发（remove_job），enabled=True 时恢复定时触发。
        """
        if interval_minutes is not None:
            self._config.interval_minutes = interval_minutes
            if self._scheduler and self._config.enabled:
                self._scheduler.reschedule_job(
                    "batch_refresh",
                    trigger="interval",
                    minutes=interval_minutes,
                )
        if enabled is not None:
            self._config.enabled = enabled
            if not enabled:
                # 立即移除定时 job：用户禁用后不应再自动触发
                # 为什么不用 shutdown：shutdown 会关闭整个调度器，后续无法 reschedule，
                # remove_job 保留调度器实例允许用户重新启用
                if self._scheduler:
                    try:
                        self._scheduler.remove_job("batch_refresh")
                        logger.info("批量采集已禁用，定时任务已移除")
                    except Exception:
                        # job 不存在或已移除，忽略
                        pass
            else:
                # 重新启用：恢复定时 job
                if self._scheduler and self._main_loop:
                    next_run = datetime.now() + timedelta(seconds=10)
                    self._scheduler.add_job(
                        self._run_batch_job,
                        "interval",
                        minutes=self._config.interval_minutes,
                        next_run_time=next_run,
                        id="batch_refresh",
                        replace_existing=True,
                    )
                    logger.info(
                        "批量采集已启用，间隔 %d 分钟，首次执行于 %s",
                        self._config.interval_minutes,
                        next_run.strftime("%Y-%m-%d %H:%M:%S"),
                    )

    def _get_progress_snapshot(self) -> dict | None:
        """获取进度快照（计算 elapsed_ms）"""
        if not self._progress:
            return None
        snapshot = dict(self._progress)
        if snapshot.get("started_at"):
            try:
                started = datetime.fromisoformat(snapshot["started_at"])
                elapsed = (datetime.now(timezone.utc) - started).total_seconds() * 1000
                snapshot["elapsed_ms"] = int(elapsed)
            except (ValueError, TypeError):
                pass
        return snapshot

    def _run_batch_job(self) -> None:
        """BackgroundScheduler 定时入口（同步线程）

        通过 run_coroutine_threadsafe 提交到主事件循环执行，并等待结果。
        为什么用 future.result 而非 fire-and-forget：定时任务需要感知执行异常，
        便于日志排查；超时则释放线程，避免堆积。
        """
        # 双重保险：enabled=False 时跳过执行
        # 为什么在 _run_batch_job 也检查而非仅依赖 update_config 移除 job：
        # update_config 与 APScheduler 触发之间存在竞态，job 可能已被调度到线程池
        # 队列，仅 remove_job 不能保证正在排队的回调被取消
        if not self._config.enabled:
            return
        if self._main_loop is None or self.is_running():
            return
        self._current_task_id += 1
        task_id = self._current_task_id
        future = asyncio.run_coroutine_threadsafe(
            self._run_batch_async(task_id, "scheduler"), self._main_loop
        )
        try:
            future.result(timeout=_BATCH_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            logger.error("[BatchRefresh#%d] 任务异常: %s", task_id, e)
            # 异常退出时也要更新历史记录为 failed，避免残留 running 状态
            self._finalize_history_on_exception(task_id, e)

    async def _run_batch_async(self, task_id: int, source: str = "manual") -> None:
        """批量采集主逻辑（在主事件循环中执行）

        步骤：
        1. 检查断点续传：若有 paused 状态的进度记录，从持久化的 pending 列表恢复
        2. 同步 Cookie 到 worker 浏览器（每批次一次，避免每商品都同步）
        3. 逐个采集详情 → 合并写库
        4. 循环中检查 _stop_flag 和 _pause_event，响应用户控制
        5. 每个 item 后 await asyncio.sleep 让出事件循环（资源调度优化）
        6. 批次开始时插入历史记录（running），结束时更新终态（completed/cancelled/failed）

        重构说明：将"准备 items"、"主循环处理"、"终态计算"拆分为独立方法，
        主方法只负责编排，降低圈复杂度（S3776）。计数器通过 _BatchCounters 共享。

        Args:
            task_id: 批次任务 ID（全局自增）
            source: 触发来源 manual=用户手动 / scheduler=定时调度
        """
        if self.is_running():
            logger.warning("[BatchRefresh#%d] 跳过：已有批次在运行", task_id)
            return

        # 初始化运行时控制状态
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始非阻塞
        self._stop_flag = False
        # 重置当前批次错误累积
        self._current_errors = []
        started_at = datetime.now(timezone.utc)
        counters = _BatchCounters()

        # 准备 items（断点续传或新批次）
        items, processed, total = await self._prepare_batch_items(task_id, started_at)
        counters.processed = processed

        # 插入历史记录（running 状态），结束前在 finally 中更新为终态
        self._current_history_id = self._create_history(
            task_id=task_id,
            source=source,
            started_at=started_at,
            total=total,
        )

        # 初始化进度
        self._status = "running"
        self._progress = {
            "task_id": task_id,
            "current": processed,
            "total": total,
            "current_item_id": None,
            "started_at": started_at.isoformat(),
        }

        try:
            # 主循环：逐个采集，期间响应暂停/停止
            await self._process_items_loop(items, task_id, total, started_at, counters)

            # 正常完成：清理进度记录
            if not self._stop_flag:
                self._clear_progress()
            self._last_result = {
                "success": counters.success,
                "failed": counters.failed,
                "skipped": counters.skipped,
                "stopped": self._stop_flag,
            }
            self._last_run_at = started_at.isoformat()
            logger.info(
                f"[BatchRefresh#{task_id}] 完成: success={counters.success} "
                f"failed={counters.failed} skipped={counters.skipped} stopped={self._stop_flag}"
            )

            # 计算终态，熔断对应 failed，用户停止对应 cancelled，正常完成对应 completed
            final_status = self._compute_final_status(counters.circuit_broken)

            # 更新历史记录为终态
            self._finalize_history(
                started_at=started_at,
                status=final_status,
                success=counters.success,
                failed=counters.failed,
                skipped=counters.skipped,
                total=total,
                consecutive_failures=counters.consecutive_failures if counters.circuit_broken else 0,
            )
        finally:
            self._status = "idle"
            self._progress = None
            self._pause_event = None
            self._stop_flag = False
            self._current_history_id = None
            self._current_errors = []

    async def _prepare_batch_items(
        self, task_id: int, started_at: datetime
    ) -> tuple[list[dict], int, int]:
        """准备本批次要处理的 items 列表

        优先尝试断点续传（恢复未完成的 paused/running 批次）；
        无可续传记录时走新批次路径：同步 Cookie + 拉取在售商品。

        Returns:
            (items, processed, total)：items 为待处理列表，processed 为已处理数（续传时非 0），total 为总数。
        """
        resumed = self._load_resumable_progress()
        if resumed:
            # 从持久化的 pending_item_ids 恢复
            pending_ids = resumed["pending_item_ids"]
            items = self._container.repo.list_items_by_ids(pending_ids)
            # 过滤掉已售的（暂停期间可能已被其他流程标记为已售）
            items = [it for it in items if not it.get("is_sold")]
            processed = resumed["processed"]
            total = resumed["total"]
            logger.info(
                f"[BatchRefresh#{task_id}] 从断点续传: 已处理 {processed}/{total}, "
                f"剩余 {len(items)} 个未售商品"
            )
            # 清理旧的进度记录
            self._clear_progress()
            return items, processed, total

        # 新批次：先同步 Cookie，再拉取在售商品
        await self._sync_cookie_before_batch(task_id, started_at)
        items = self._container.repo.list_unsold_items(
            limit=self._config.max_items_per_run
        )
        processed = 0
        total = len(items)
        logger.info(f"[BatchRefresh#{task_id}] 开始采集 {total} 个商品")
        return items, processed, total

    async def _sync_cookie_before_batch(
        self, task_id: int, started_at: datetime
    ) -> None:
        """新批次开始前同步 Cookie 到 worker 浏览器

        为什么每批次只同步一次：Cookie 同步涉及磁盘 I/O 与浏览器 IPC，
        每商品都同步会显著拖慢采集；同批次内 Cookie 通常不会中途失效。
        同步失败仅记日志与错误累积，不阻断批次（后续 _refresh_one 会再次校验）。
        """
        try:
            from xianyu_hunter.web.services.cookie_runtime_sync import (
                inject_cookie_store_to_worker_browser,
            )
            await inject_cookie_store_to_worker_browser(
                "批量采集前 Cookie 同步", force_refresh_m5tk=False
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[BatchRefresh#{task_id}] Cookie 同步失败: {e}")
            self._append_error("cookie_sync", str(e), started_at)

    async def _process_items_loop(
        self,
        items: list[dict],
        task_id: int,
        total: int,
        _started_at: datetime,
        counters: _BatchCounters,
    ) -> None:
        """逐个采集 items，期间响应暂停/停止/熔断

        async 方法：内部需要 await _pause_event.wait()、_refresh_one、asyncio.sleep，
        必须在 async 上下文中调用。提取为独立方法是为降低 _run_batch_async 圈复杂度（S3776）。
        """
        for idx, item in enumerate(items):
            item_id = item.get("id")
            if not item_id:
                counters.skipped += 1
                continue

            # 检查停止标志（在 wait 之前，避免暂停态下无法停止）
            if self._stop_flag:
                # 持久化未处理的 items（含当前 item）
                remaining = [it for it in items[idx:] if it.get("id")]
                self._save_progress(
                    task_id, remaining, counters.processed, total, "stopped"
                )
                logger.info(
                    f"[BatchRefresh#{task_id}] 用户停止，已持久化 "
                    f"{len(remaining)} 个未处理商品"
                )
                break

            # 等待暂停恢复（暂停时 event 被 clear，wait 阻塞）
            await self._pause_event.wait()

            # resume 后再次检查停止标志（用户可能在暂停态下请求停止）
            if self._stop_flag:
                remaining = [it for it in items[idx:] if it.get("id")]
                self._save_progress(
                    task_id, remaining, counters.processed, total, "stopped"
                )
                break

            # 更新当前处理的 item（前端可见）
            self._progress["current_item_id"] = item_id

            # 处理单个 item；返回 True 表示熔断需跳出循环
            should_break = await self._process_single_item(
                item_id, item, task_id, counters, len(items)
            )
            if should_break:
                break

            # 更新进度
            counters.processed += 1
            self._progress["current"] = counters.processed
            self._progress["current_item_id"] = None

            # 资源调度优化：让出事件循环给主业务请求
            # 不在 finally 中，避免暂停阻塞时也 sleep
            await asyncio.sleep(_YIELD_INTERVAL)

    async def _process_single_item(
        self,
        item_id: str,
        item: dict,
        task_id: int,
        counters: _BatchCounters,
        total_items: int,
    ) -> bool:
        """处理单个 item 的采集，返回是否应跳出主循环

        返回 True：熔断触发，应 break 主循环。
        返回 False：正常处理完成或单商品失败但未熔断，应继续下一轮。
        """
        try:
            changed_fields = await self._refresh_one(item_id, item)
            if changed_fields is None:
                counters.skipped += 1
            else:
                counters.success += 1
                if changed_fields:
                    self._record_change(item_id, changed_fields)
            counters.consecutive_failures = 0
            return False
        except Exception as e:  # noqa: BLE001
            return self._handle_item_failure(
                e, task_id, item_id, counters, total_items
            )

    def _handle_item_failure(
        self,
        e: Exception,
        task_id: int,
        item_id: str,
        counters: _BatchCounters,
        total_items: int,
    ) -> bool:
        """处理单个 item 采集失败：累加错误、检查熔断，返回是否应跳出主循环

        返回 True：连续失败达阈值，已标记熔断，应 break。
        返回 False：未达阈值，应继续下一轮。
        """
        counters.failed += 1
        counters.consecutive_failures += 1
        logger.warning(
            f"[BatchRefresh#{task_id}] 采集 {item_id} 失败: {e}"
        )
        # 累积错误消息到历史记录，便于事后排查
        self._append_error(item_id, str(e), datetime.now(timezone.utc))
        if counters.consecutive_failures < self._fail_pause_threshold:
            return False
        logger.error(
            f"[BatchRefresh#{task_id}] 连续失败 {counters.consecutive_failures} 次，"
            f"暂停当前批次（剩余商品记为 skipped）"
        )
        # 标记熔断：与用户停止区分，历史记录 status=failed
        counters.circuit_broken = True
        # 剩余未处理商品记为 skipped，便于统计对账
        processed_count = counters.success + counters.failed + counters.skipped
        remaining_count = total_items - processed_count
        counters.skipped += remaining_count
        return True

    def _compute_final_status(self, circuit_broken: bool) -> str:
        """计算批次终态：熔断→failed / 用户停止→cancelled / 正常→completed"""
        if circuit_broken:
            return "failed"
        if self._stop_flag:
            return "cancelled"
        return "completed"

    def _create_history(
        self,
        task_id: int,
        source: str,
        started_at: datetime,
        total: int,
    ) -> int | None:
        """批次开始时插入一条 running 状态的历史记录

        返回历史记录主键 id；写入失败时返回 None，不阻断批次执行
        （历史记录是辅助功能，不应影响采集主流程）
        """
        try:
            return self._container.repo.save_batch_refresh_history({
                "task_id": task_id,
                "trigger_source": source,
                "started_at": started_at,
                "total": total,
                "status": "running",
            })
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[BatchRefresh#{task_id}] 写入历史记录失败: {e}")
            return None

    def _append_error(self, item_id: str, error: str, timestamp: datetime) -> None:
        """累积错误消息到内存列表，结束时序列化为 JSON 写入历史记录

        上限 _MAX_ERROR_MESSAGES 条，FIFO 丢弃最旧，避免 JSON 字段无限膨胀。
        """
        if len(self._current_errors) >= _MAX_ERROR_MESSAGES:
            # 切片保留尾部，丢弃最旧
            self._current_errors = self._current_errors[-_MAX_ERROR_MESSAGES + 1:]
        self._current_errors.append({
            "item_id": item_id,
            "error": error[:500],  # 截断单条错误，避免超长堆栈
            "timestamp": timestamp.isoformat(),
        })

    def _finalize_history(
        self,
        started_at: datetime,
        status: str,
        success: int,
        failed: int,
        skipped: int,
        total: int,
        consecutive_failures: int = 0,
    ) -> None:
        """批次结束时更新历史记录为终态"""
        if self._current_history_id is None:
            return
        completed_at = datetime.now(timezone.utc)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        # error_messages 仅在有错误时序列化，避免空数组占用空间
        error_json = json.dumps(self._current_errors) if self._current_errors else None
        try:
            self._container.repo.update_batch_refresh_history(
                self._current_history_id,
                {
                    "completed_at": completed_at,
                    "status": status,
                    "success": success,
                    "failed": failed,
                    "skipped": skipped,
                    "total": total,
                    "consecutive_failures": consecutive_failures,
                    "duration_ms": duration_ms,
                    "error_messages": error_json,
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"更新历史记录失败: {e}")

    def _finalize_history_on_exception(self, task_id: int, error: Exception) -> None:
        """future.result 超时或异常时的兜底更新

        为什么单独处理：_run_batch_async 内部异常会被 finally 捕获并更新终态，
        但 future.result(timeout=_BATCH_TIMEOUT) 抛 TimeoutError 时协程还在运行，
        历史记录可能停留在 running 状态。此处兜底更新为 failed。
        """
        if self._current_history_id is None:
            return
        self._append_error("_batch_timeout", str(error), datetime.now(timezone.utc))
        try:
            self._container.repo.update_batch_refresh_history(
                self._current_history_id,
                {
                    "completed_at": datetime.now(timezone.utc),
                    "status": "failed",
                    "error_messages": json.dumps(self._current_errors),
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[BatchRefresh#{task_id}] 兜底更新历史记录失败: {e}")
        finally:
            # 清理状态，避免下次批次创建历史时 _current_history_id 残留
            self._current_history_id = None
            self._current_errors = []

    def _load_resumable_progress(self) -> dict | None:
        """加载可续传的进度记录

        查找 status=paused 的最近一条记录（进程异常退出后可能残留 running 状态，
        一并视为可续传）。
        """
        engine = self._container.repo.engine
        with engine.connect() as conn:
            stmt = (
                select(BatchRefreshProgressRow)
                .where(BatchRefreshProgressRow.status.in_(("paused", "running")))
                .order_by(BatchRefreshProgressRow.created_at.desc())
                .limit(1)
            )
            row = conn.execute(stmt).first()
            if row is None:
                return None
            try:
                pending_ids = json.loads(row.pending_item_ids)
            except (json.JSONDecodeError, TypeError):
                return None
            return {
                "task_id": row.task_id,
                "pending_item_ids": pending_ids,
                "total": row.total,
                "processed": row.processed,
            }

    def _save_progress(
        self,
        task_id: int,
        remaining_items: list[dict],
        processed: int,
        total: int,
        status: str,
    ) -> None:
        """持久化当前进度到数据库（断点续传用）

        Args:
            task_id: 当前批次任务 ID
            remaining_items: 未处理的 item dict 列表
            processed: 已处理数量
            total: 总数量
            status: paused / stopped
        """
        pending_ids = [it.get("id") for it in remaining_items if it.get("id")]
        engine = self._container.repo.engine
        with engine.begin() as conn:
            # 删除同 task_id 的旧记录（避免重复）
            conn.execute(
                BatchRefreshProgressRow.__table__.delete().where(
                    BatchRefreshProgressRow.task_id == task_id
                )
            )
            conn.execute(
                BatchRefreshProgressRow.__table__.insert().values(
                    task_id=task_id,
                    pending_item_ids=json.dumps(pending_ids),
                    total=total,
                    processed=processed,
                    status=status,
                )
            )
            conn.commit()

    def _clear_progress(self) -> None:
        """清理所有进度记录（批次正常完成后调用）"""
        engine = self._container.repo.engine
        with engine.begin() as conn:
            conn.execute(BatchRefreshProgressRow.__table__.delete())
            conn.commit()

    async def _refresh_one(
        self, item_id: str, existing_item: dict
    ) -> list[str] | None:
        try:
            result = await asyncio.wait_for(
                ItemCollectionService(self._container).collect(
                    item_id,
                    task_id=str(existing_item.get("task_id") or ""),
                    mode=CollectionMode.OFFICIAL_FULL,
                    existing_item=existing_item,
                    source="official",
                ),
                timeout=_DETAIL_TIMEOUT,
            )
        except CollectionError as exc:
            if exc.status_code == 410:
                return None
            raise
        if not result.ok:
            return None
        return result.changed_fields

        """采集单个商品详情并合并写库

        Returns:
            变更字段列表（可能为空列表表示无变化）；None 表示采集失败或无数据
        """
        from xianyu_hunter.infra.item_display_sync import sync_item_display_from_detail

        # detail() 内部 page.goto 有 30s 超时，但页面操作可能挂起，
        # 加 60s 整体超时与 refresh_item 端点保持一致
        detail = await asyncio.wait_for(
            self._container.collector.detail(item_id), timeout=_DETAIL_TIMEOUT
        )
        if detail is None:
            return None

        # 构造 new_row（复用 refresh_item 端点的合并写库逻辑）
        # task_id 从 existing_item 读取，避免覆盖原任务归属
        new_row = {
            "id": item_id,
            "task_id": existing_item.get("task_id") or "",
            "title": detail.title,
            "price": detail.price,
            "seller_id": detail.seller_id or "",
            "region": detail.region or "",
            "want_cnt": detail.want_cnt,
            "view_cnt": detail.view_cnt,
            "thumb_url": detail.thumb_url or "",
            "is_sold": 1 if detail.is_sold else 0,
        }

        # 写库前比较字段差异（upsert 后旧值被覆盖，无法再比较）
        changed_fields = self._diff_fields(existing_item, new_row)

        self._container.repo.upsert_item(new_row)
        # 已售时通过 mark_sold 补写 sold_detected_at + 同步 task_links.display.is_sold
        if detail.is_sold:
            self._container.repo.mark_sold(item_id)

        # 同步 task_links.display：评估明细页 brand 等字段从此处读取
        task_id = existing_item.get("task_id") or ""
        if task_id:
            sync_item_display_from_detail(
                self._container.repo, task_id, item_id, detail, source="batch_refresh"
            )

        return changed_fields

    def _diff_fields(self, existing: dict, new_row: dict) -> list[str]:
        """比较现有 item 和新 row 的字段差异

        为什么单独实现而非用 dict 比较：DB 返回的类型可能与 new_row 不一致
        （如 price 可能是 Decimal/float，want_cnt 可能是 int/None），
        需要按字段类型规范化后再比较，避免误报变更。
        """
        # 与 new_row 的 key 对齐（不含 id/task_id，这两个不参与变更日志）
        str_fields = ["title", "seller_id", "region", "thumb_url"]
        int_fields = ["want_cnt", "view_cnt", "is_sold"]
        changed: list[str] = []

        for f in str_fields:
            old_val = existing.get(f)
            new_val = new_row.get(f)
            # None 与 "" 视为等价（DB NULL 与空字符串不区分）
            if (old_val or "") != (new_val or ""):
                changed.append(f)

        for f in int_fields:
            old_val = existing.get(f)
            new_val = new_row.get(f)
            if int(old_val or 0) != int(new_val or 0):
                changed.append(f)

        # price 单独处理：float vs Decimal/str 都能转 float 比较
        old_price = existing.get("price")
        new_price = new_row.get("price")
        try:
            if float(old_price or 0) != float(new_price or 0):
                changed.append("price")
        except (TypeError, ValueError):
            changed.append("price")

        return changed

    def _record_change(self, item_id: str, changed_fields: list[str]) -> None:
        """记录变更到内存日志（带上限，FIFO 丢弃最旧）"""
        if not changed_fields:
            return
        self._change_log.append(
            {
                "item_id": item_id,
                "changed_fields": changed_fields,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        if len(self._change_log) > _MAX_CHANGE_LOG:
            # 切片保留尾部，丢弃最旧的记录
            self._change_log = self._change_log[-_MAX_CHANGE_LOG:]
