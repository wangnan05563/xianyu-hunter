"""任务调度器：管理多个 TaskWorker 的生命周期

设计文档 §3.8 - 调度器职责：
1. 启动/暂停/恢复/停止单个任务
2. 启动/停止全部任务
3. 维护 task_id → 后台 Task 的映射
4. 优雅退出（stop_all 等待所有 worker 结束当前轮）
5. F-16：依赖触发——上游任务成功后自动激活下游 paused 任务

不提供 HTTP 接口（按用户选择），仅 Python API。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from xianyu_hunter.domain.task import Task, TaskStatus
from xianyu_hunter.infra.logger import get_logger

if TYPE_CHECKING:
    from xianyu_hunter.modules.worker import TaskWorker
    from xianyu_hunter.infra.repository import Repository

logger = get_logger()


# 会话失效后任务恢复的冷却期（秒）：避免用户在 Cookie 失效后反复点恢复
# 触发 RGV587 反爬检测，冷却期内 resume/start 会被拒绝并提示前端重新登录
_RESUME_COOLDOWN_SECONDS = 300

# 单轮 run_once 异常后等待重试的默认秒数
# 实际值从 task_scheduler.error_retry_wait_seconds 读取，这里仅作兜底
_DEFAULT_ERROR_RETRY_WAIT_SECONDS = 300


class ResumeBlockedError(Exception):
    """任务恢复被阻止：Cookie 失效或处于会话失效冷却期内

    为什么需要自定义异常而非直接 raise HTTPException：
    scheduler 是纯 Python 调度层，不应感知 HTTP 语义。api_tasks.py 捕获此异常
    后转换为 400 响应，保持分层清晰。消息体会透传给前端作为 detail 提示。
    """


class _ImmediateAwaitable:
    def __await__(self):
        # 返回空迭代器让 await 立即完成：原 if False: yield 是为了让 __await__ 被识别为 generator，
        # 但属于恒定条件（S5797）。改用 iter(()) 直接得到空迭代器，语义等价且无死代码。
        return iter(())


@dataclass
class _WorkerHandle:
    """单个任务的运行时句柄"""
    task: Task
    worker: "TaskWorker"
    loop_task: asyncio.Task | None = None
    stop_event: asyncio.Event = None  # type: ignore[assignment]
    pause_event: asyncio.Event = None  # type: ignore[assignment]
    # 连续失败计数：超阈值后自动暂停任务，由 scheduler._run_loop 维护
    consecutive_errors: int = 0

    def __post_init__(self):
        if self.stop_event is None:
            self.stop_event = asyncio.Event()
        if self.pause_event is None:
            self.pause_event = asyncio.Event()
            self.pause_event.set()  # 默认不暂停


class TaskScheduler:
    """多任务调度器

    使用方式：
        scheduler = TaskScheduler()
        scheduler.register(task, worker)
        scheduler.start("t1")
        scheduler.start_all()  # 同步 API：内部已通过 asyncio.create_task 启动后台循环
        # ...
        await scheduler.stop_all()
    """

    def __init__(self) -> None:
        self._workers: dict[str, _WorkerHandle] = {}
        # F-16：Repository 引用，用于依赖触发时查询/更新任务状态
        self._repo: "Repository | None" = None
        # 全局并发锁：同一时间只允许一个 task 执行 run_once，
        # 避免多任务并发打开多个浏览器页面导致窗口不停弹出
        self._run_lock = asyncio.Lock()
        # _workers 字典并发保护锁：register/unregister/trigger_dependent_tasks
        # 等方法可能在不同协程中并发修改 _workers，需加锁防止 await 间隙的竞态
        self._workers_lock = asyncio.Lock()
        # 会话失效冷却期记录：task_id → 冷却期结束时间戳（time.monotonic）
        # 为什么用 monotonic 而非 time.time：monotonic 不受系统时钟调整影响，
        # 适合测量相对时间间隔，避免 NTP 校时导致冷却期异常缩短或延长
        self._resume_cooldown: dict[str, float] = {}

    # ============== 注册 ==============

    async def register(self, task: Task, worker: "TaskWorker") -> None:
        """注册任务（不启动）"""
        async with self._workers_lock:
            if task.id in self._workers:
                raise ValueError(f"任务 {task.id} 已注册")
            self._workers[task.id] = _WorkerHandle(task=task, worker=worker)
        logger.info(f"Scheduler 注册任务 {task.id} ({task.name})")

    async def unregister(self, task_id: str) -> None:
        """注销（需先 stop）"""
        async with self._workers_lock:
            if task_id not in self._workers:
                raise KeyError(f"任务 {task_id} 未注册")
            h = self._workers[task_id]
            if h.loop_task and not h.loop_task.done():
                raise RuntimeError(f"任务 {task_id} 仍在运行，请先 stop")
            del self._workers[task_id]
            # 清理冷却期记录，避免已注销任务的残留记录占用内存
            self._resume_cooldown.pop(task_id, None)
        # 锁外执行清理，避免长耗时 IO 阻塞 _workers_lock
        cleanup = getattr(h.worker, "cleanup", None)
        if cleanup:
            try:
                cleanup()
            except Exception as e:
                logger.warning(f"[Task {task_id}] Worker cleanup 失败: {e}")

    def drop_task_state(self, task_id: str) -> None:
        """同步清理任务的内存残留状态（供 delete API 调用）

        为什么需要独立方法而非复用 unregister：
        - unregister 是 async 且要求先 stop，delete API 是同步端点且任务可能仍在运行
        - 本方法仅清理 _resume_cooldown，不动 _workers（_workers 清理需先 stop loop_task）
        - _workers 中已停止任务的残留条目占用极小，服务重启后自动清空，
          重点清理 _resume_cooldown 避免长期运行后字典无限增长
        """
        self._resume_cooldown.pop(task_id, None)

    # ============== 启停控制 ==============

    def _check_resume_allowed(self, task_id: str) -> None:
        """恢复前校验：Cookie 有效性 + 会话失效冷却期

        为什么在 scheduler 层而非 api_tasks 层做校验：
        scheduler 是任务生命周期的唯一入口（start/resume 都经过这里），
        在此校验可覆盖所有恢复路径，避免 api_tasks 遗漏某个分支导致绕过。
        失败时抛出 ResumeBlockedError，由 api_tasks 转换为 400 响应。

        校验顺序：先冷却期再 Cookie——冷却期内的拒绝是确定性的，
        Cookie 校验涉及文件 I/O，放后面可避免冷却期内无谓的磁盘读取。
        """
        # 1. 冷却期检查：会话失效后 5 分钟内拒绝恢复
        cooldown_until = self._resume_cooldown.get(task_id)
        if cooldown_until is not None:
            remaining = cooldown_until - time.monotonic()
            if remaining > 0:
                raise ResumeBlockedError(
                    f"任务会话失效冷却期内，请 {int(remaining)} 秒后重试，"
                    f"或重新登录后再恢复"
                )
            # 冷却期已过，清除记录避免字典无限增长
            self._resume_cooldown.pop(task_id, None)

        # 2. Cookie 有效性检查：延迟导入避免循环依赖
        # 为什么延迟导入：cookie_store 属于 web 层，scheduler 属于 modules 层，
        # 编译期直接导入会引入分层违规；运行时延迟导入在测试中可被 mock 替换
        # 为什么需要 active user_id：多用户场景下 cookies_{user_id}.json 按用户隔离，
        # 默认 "default" 在多用户环境下永远找不到 cookie，导致任务被误判为未登录
        try:
            from xianyu_hunter.web.services.cookie_store import get_cookie_store
            from xianyu_hunter.web.services.user_manager import get_user_manager

            user_id = get_user_manager().get_active_user_id()
            if not get_cookie_store().has_valid_cookies(user_id):
                raise ResumeBlockedError("Cookie 已失效，请重新登录后再恢复任务")
        except ImportError:
            # 测试环境或 cookie_store 不可用时跳过 Cookie 校验，仅依赖冷却期
            logger.debug(f"[Task {task_id}] cookie_store 不可用，跳过 Cookie 校验")
        except ResumeBlockedError:
            # ResumeBlockedError 必须重新抛出，否则 Cookie 失效时任务仍会启动
            # （原 except Exception 会误吞 ResumeBlockedError，导致校验形同虚设）
            raise
        except Exception as e:
            # cookie_store 内部异常（如 RuntimeError/IOError）不应导致 500，
            # 降级为跳过 Cookie 校验，仅依赖冷却期
            logger.warning(f"[Task {task_id}] Cookie 校验异常，跳过: {e}")

    def precheck_resume(self, task_id: str) -> dict[str, Any]:
        """恢复前置校验：返回结构化结果，不抛异常

        与 _check_resume_allowed 的关系：
        - _check_resume_allowed 抛 ResumeBlockedError，用于真正执行 resume/start 时阻断
        - precheck_resume 返回结构化 dict，用于前端"恢复"按钮点击前的预检
        - 两者复用同一套校验逻辑（冷却期 + Cookie），确保前后端判断一致

        返回结构（meta-rule #31 resume_policy.require_structured_response）：
        - resume_blocked: bool — 是否阻止恢复
        - reason_code: str — 阻止原因码（cooldown / cookie_invalid / not_registered / ok）
        - user_hint: str — 用户可读提示
        - retry_after: int | None — 冷却期剩余秒数（仅 cooldown 时有值）
        - task_registered: bool — 任务是否已注册到调度器（未注册需重启服务）
        """
        result: dict[str, Any] = {
            "resume_blocked": False,
            "reason_code": "ok",
            "user_hint": "",
            "retry_after": None,
            "task_registered": task_id in self._workers,
        }
        # 未注册任务：不阻断（DB 状态仍可改），但提示需重启服务
        if task_id not in self._workers:
            result["user_hint"] = "任务未注册到调度器，DB 状态将更新但需重启服务才生效"
            return result

        # 1. 冷却期检查
        cooldown_until = self._resume_cooldown.get(task_id)
        if cooldown_until is not None:
            remaining = cooldown_until - time.monotonic()
            if remaining > 0:
                result.update(
                    resume_blocked=True,
                    reason_code="cooldown",
                    user_hint=f"会话失效冷却期内，请 {int(remaining)} 秒后重试，或重新登录后再恢复",
                    retry_after=int(remaining),
                )
                return result
            # 冷却期已过，清除记录避免字典无限增长
            self._resume_cooldown.pop(task_id, None)

        # 2. Cookie 有效性检查
        try:
            from xianyu_hunter.web.services.cookie_store import get_cookie_store
            from xianyu_hunter.web.services.user_manager import get_user_manager

            user_id = get_user_manager().get_active_user_id()
            if not get_cookie_store().has_valid_cookies(user_id):
                result.update(
                    resume_blocked=True,
                    reason_code="cookie_invalid",
                    user_hint="Cookie 已失效，请重新登录后再恢复任务",
                )
                return result
        except ImportError:
            logger.debug(f"[Task {task_id}] cookie_store 不可用，跳过 Cookie 校验")
        except Exception as e:
            logger.warning(f"[Task {task_id}] Cookie 校验异常，跳过: {e}")

        result["user_hint"] = "可恢复"
        return result

    def start(self, task_id: str) -> None:
        """启动单个任务的后台循环"""
        h = self._require(task_id)
        if h.loop_task and not h.loop_task.done():
            logger.warning(f"任务 {task_id} 已在运行")
            return
        # 启动前同样校验 Cookie + 冷却期：restart 流程会先 stop 再 start，
        # 若不校验 start，冷却期校验会被 restart 绕过
        self._check_resume_allowed(task_id)
        h.stop_event.clear()
        h.pause_event.set()
        h.loop_task = asyncio.create_task(self._run_loop(task_id), name=f"task-{task_id}")
        h.task.status = TaskStatus.RUNNING
        logger.info(f"Scheduler 启动任务 {task_id}")

    async def stop(self, task_id: str, timeout: float = 30.0) -> None:  # NOSONAR
        """停止任务（等待当前轮结束）"""
        h = self._require(task_id)
        if not h.loop_task or h.loop_task.done():
            return
        h.stop_event.set()
        h.pause_event.set()  # 若正在暂停，让它能继续到下一轮 stop 检查
        try:
            await asyncio.wait_for(h.loop_task, timeout=timeout)  # noqa: S7483
        except asyncio.TimeoutError:
            logger.warning(f"任务 {task_id} 30s 内未退出，强制取消")
            h.loop_task.cancel()
        h.task.status = TaskStatus.STOPPED
        logger.info(f"Scheduler 停止任务 {task_id}")

    def pause(self, task_id: str) -> None:
        """暂停任务（当前轮会跑完，下一轮不再开始）"""
        h = self._require(task_id)
        h.pause_event.clear()
        h.task.status = TaskStatus.PAUSED
        logger.info(f"Scheduler 暂停任务 {task_id}")

    def resume(self, task_id: str) -> None:
        """恢复任务"""
        # 恢复前校验 Cookie + 冷却期：会话失效时自动暂停的任务，
        # 若不校验直接恢复会立即再次触发 RGV587 反爬检测
        self._check_resume_allowed(task_id)
        h = self._require(task_id)
        h.pause_event.set()
        h.task.status = TaskStatus.RUNNING
        logger.info(f"Scheduler 恢复任务 {task_id}")

    def start_all(self) -> _ImmediateAwaitable:
        """同步启动所有已注册任务。

        注意：保持非 async。原因：
        - `start` 本身是同步方法（内部通过 `asyncio.create_task` 启动后台循环），
          返回 None，若包成 async + await 会导致调用方得到空 await，徒增复杂度。
        - 公共 API 上保留 `start_all()` 同步签名，调用方用 `container.scheduler.start_all()` 即可。
        - 若需要等待首个轮次结束，请改用 `await scheduler.start_and_wait_all()` 之类显式方法。
        """
        # 提前快照 worker ids：self.start() 内部可能修改 self._workers，
        # 直接对 keys() 迭代会触发 RuntimeError: dictionary changed size during iteration
        worker_tids = list(self._workers.keys())  # noqa: S7504 - list() 必要：防止迭代中修改字典
        for tid in worker_tids:
            self.start(tid)
        return _ImmediateAwaitable()

    async def stop_all(self) -> None:
        # 并发等待所有 stop
        # list() 必要：self.stop() 内部 del self._workers[tid]，并发执行时会修改字典
        await asyncio.gather(
            *(self.stop(tid) for tid in list(self._workers.keys())),  # noqa: S7504
            return_exceptions=True,
        )

    # ============== 状态查询 ==============

    def list_tasks(self) -> list[Task]:
        return [h.task for h in self._workers.values()]

    def get_status(self, task_id: str) -> TaskStatus:
        return self._require(task_id).task.status

    def is_running(self, task_id: str) -> bool:
        h = self._require(task_id)
        return h.loop_task is not None and not h.loop_task.done()

    # ============== F-16 依赖触发 ==============

    def set_repo(self, repo: "Repository") -> None:
        """注入 Repository（用于依赖触发时查询/更新任务状态）

        为什么不放在 __init__：Scheduler 在 Container 中通过 field(default_factory) 构造，
        此时 repo 尚未就绪；需要构造后手动注入。
        """
        self._repo = repo

    async def trigger_dependent_tasks(self, upstream_task_id: str) -> list[str]:
        """F-16：上游任务成功后，自动激活依赖它的下游 paused 任务

        返回被激活的任务 ID 列表。
        仅改 DB 状态 + 写事件；内存中的 WorkerHandle 在下次 _run_loop 时自动读取新状态。
        """
        if not self._repo:
            logger.warning("[F-16] repo 未注入，无法触发依赖任务")
            return []

        dependents = self._repo.list_dependent_tasks(upstream_task_id)
        activated: list[str] = []

        for dep in dependents:
            downstream_id = dep["task_id"]
            downstream = self._repo.get_task(downstream_id)
            if not downstream:
                continue
            # 仅 paused 状态的下游任务需要激活
            if downstream.get("status") != "paused":
                logger.info(
                    f"[F-16] 下游任务 {downstream_id} 状态为 {downstream.get('status')}，跳过激活"
                )
                continue

            self._repo.update_task_status(downstream_id, "running")
            self._repo.save_event({
                "task_id": downstream_id,
                "stage": "dep_triggered",
                "level": "info",
                "message": f"上游任务 {upstream_task_id} 成功，自动激活下游任务",
                "payload": f'{{"upstream_task": "{upstream_task_id}", "triggered_by": "dep_chain"}}',
            })
            activated.append(downstream_id)
            logger.info(
                f"[F-16] 上游任务 {upstream_task_id} 成功 → 自动激活下游任务 {downstream_id}"
            )

            # 如果下游任务已在调度器中注册，同步内存状态（加锁防止并发 unregister）
            async with self._workers_lock:
                if downstream_id in self._workers:
                    handle = self._workers[downstream_id]
                    handle.task.status = TaskStatus.RUNNING
                    handle.pause_event.set()  # 唤醒可能阻塞在 pause_event.wait() 的 _run_loop

        return activated

    # ============== 内部 ==============

    def _require(self, task_id: str) -> _WorkerHandle:
        if task_id not in self._workers:
            raise KeyError(f"任务 {task_id} 未注册")
        return self._workers[task_id]

    async def _run_loop(self, task_id: str) -> None:
        """单任务后台循环

        使用全局 _run_lock 确保同一时间只有一个 task 在执行 run_once，
        避免多任务并发打开多个浏览器页面（每个 run_once 会创建多个详情页/卖家页）。

        P1-7：支持 cron 模式。当 TaskConfig.use_cron=True 时，
        按 Task.cron 表达式计算下次运行时间，sleep 到该时间点再执行。

        重构说明：主循环只保留调度骨架，单轮执行与等待下沉到独立私有方法（S3776）。
        """
        h = self._require(task_id)
        interval = h.worker.config.interval_seconds
        # P1-7：判断是否使用 cron 调度
        use_cron = getattr(h.worker.config, "use_cron", False)
        cron_expr = h.task.cron if use_cron else None

        while not h.stop_event.is_set():
            # 检查暂停
            await h.pause_event.wait()
            if h.stop_event.is_set():
                break
            # 为本轮 run_once 设置独立 request_id
            current_rid = self._init_request_id()
            # 单轮执行：返回 True 表示应跳出主循环
            if await self._run_one_iteration(h, task_id, current_rid):
                break
            # 等待下一轮（可被 stop 提前唤醒）
            await self._wait_for_next_round(h, cron_expr, interval, task_id)
        logger.info(f"任务 {task_id} 循环退出")

    @staticmethod
    def _init_request_id() -> str:
        """为本轮 run_once 生成独立 request_id

        周期触发的任务与原 HTTP 请求已脱钩，每轮生成新流水号，
        让本轮所有 events / error_logs / loguru 日志都关联到同一 request_id。
        协程结束时 ContextVar 自动回收，无需显式清理。
        """
        from xianyu_hunter.infra.request_context import generate_request_id, set_request_id
        current_rid = generate_request_id()
        set_request_id(current_rid)
        return current_rid

    async def _run_one_iteration(
        self, h: "_WorkerHandle", task_id: str, current_rid: str
    ) -> bool:
        """执行一轮 run_once，返回是否应跳出主循环

        返回 True：会话失效已自动暂停，或已达失败阈值，调用方应 break。
        返回 False：本轮正常完成或异常后将继续下一轮，调用方应进入等待。
        """
        try:
            # should_break=True 表示会话失效或 stop 信号，需跳出主循环
            should_break = await self._execute_run_once_locked(h, task_id)
            if should_break:
                return True
            h.consecutive_errors = 0  # 成功后重置连续失败计数
            return False
        except Exception as e:  # noqa: BLE001
            # should_continue=True 表示未达阈值等待重试，False 表示已达阈值已暂停
            should_continue = await self._handle_run_once_exception(
                e, h, task_id, current_rid
            )
            # should_continue=True → 不 break（返回 False）；False → break（返回 True）
            return not should_continue

    async def _wait_for_next_round(
        self, h: "_WorkerHandle", cron_expr: str | None, interval: int, task_id: str
    ) -> None:
        """等待下一轮执行：cron 模式按表达式，interval 模式用固定间隔

        可被 stop_event 提前唤醒，避免 stop 时还要等到下一轮。
        """
        wait_seconds = self._compute_next_wait_seconds(cron_expr, interval, task_id)
        try:
            await asyncio.wait_for(h.stop_event.wait(), timeout=wait_seconds)
        except asyncio.TimeoutError:
            pass

    async def _execute_run_once_locked(
        self, h: "_WorkerHandle", task_id: str
    ) -> bool:
        """在全局锁内执行一轮 run_once，返回是否应跳出主循环

        为什么需要返回 bool 而非 raise：should_pause 是业务预期内的暂停（会话失效），
        不是异常；用返回值语义化地表达"应跳出循环"，避免与下方 except 混淆。

        返回 True：会话失效已自动暂停，或 stop 信号到达，调用方应 break。
        返回 False：本轮正常完成，调用方应重置 consecutive_errors 并进入下一轮等待。
        """
        # 全局锁：串行化所有任务的 run_once，避免并发弹出多个浏览器窗口
        async with self._run_lock:
            if h.stop_event.is_set():
                return True
            result = await h.worker.run_once()
            # RGV587 会话失效或搜索超时时自动暂停任务，避免无效搜索持续占用 browser_lock
            if result.should_pause:
                logger.info(f"[Task {task_id}] 会话失效，自动暂停任务")
                h.pause_event.clear()
                h.task.status = TaskStatus.PAUSED
                # 记录冷却期结束时间：会话失效后 5 分钟内拒绝恢复，
                # 避免用户反复点恢复触发更严厉的反爬封禁
                self._resume_cooldown[task_id] = (
                    time.monotonic() + _RESUME_COOLDOWN_SECONDS
                )
                # 同步数据库状态，确保 API 读取到正确的 paused 状态
                if self._repo:
                    self._repo.update_task_status(task_id, "paused")
                return True
            # 每轮结束后清理残留页面，避免异常未关闭的页面堆积  # NOSONAR
            # 堆积会导致内存压力和窗口不停弹出
            await self._cleanup_browser_pages(h, task_id)
        return False

    async def _cleanup_browser_pages(
        self, h: "_WorkerHandle", task_id: str
    ) -> None:
        """每轮结束后清理浏览器残留页面

        单独提取：close_all_pages 失败不应影响主流程，异常在此吞掉仅记日志。
        """
        browser = getattr(h.worker.collector, 'browser', None)
        if browser is None:
            return
        try:
            await browser.close_all_pages()
        except Exception as e:
            logger.warning(f"[Task {task_id}] 清理残留页面失败: {e}")

    async def _handle_run_once_exception(
        self,
        e: Exception,
        h: "_WorkerHandle",
        task_id: str,
        current_rid: str,
    ) -> bool:
        """处理 run_once 抛出异常的分支，返回是否应 continue 下一轮

        返回 True：未达失败阈值，等待重试间隔后 continue 下一轮。
        返回 False：已达失败阈值，任务已暂停，应 break 主循环。

        之所以放在 scheduler 层而非 worker 层：这里是后台任务异常的统一兜底点，
        能覆盖 worker.run_once 中所有未被内部 try-except 消化的异常。
        """
        logger.exception(f"[Task {task_id}] run_once 异常")
        # 捕获到 error_logs 表，供错误日志页面展示和 AI 诊断
        # context 中携带本次执行的 request_id，便于关联到本轮所有日志
        self._capture_background_error(e, task_id, current_rid)
        h.task.status = TaskStatus.ERROR
        # 连续失败计数：超过阈值自动暂停（阈值由 antidetect.fail_pause_threshold 配置）
        h.consecutive_errors += 1
        if self._pause_if_exceeded_fail_threshold(h, task_id):
            return False
        # 出错后等待再试：从 task_scheduler.error_retry_wait_seconds 读取，避免刷错误日志
        # 与 resume_policy.cooldown_seconds 语义不同：本字段控制未触发暂停时的重试退避
        retry_wait = self._get_error_retry_wait_seconds()
        try:
            await asyncio.wait_for(h.stop_event.wait(), timeout=retry_wait)
        except asyncio.TimeoutError:
            pass
        h.task.status = TaskStatus.RUNNING
        return True

    @staticmethod
    def _get_error_retry_wait_seconds() -> int:
        """读取异常重试等待秒数，配置读取失败时回退到默认值 300 秒"""
        try:
            from xianyu_hunter.infra.yaml_config import get_config
            return get_config().task_scheduler.error_retry_wait_seconds
        except Exception:
            return _DEFAULT_ERROR_RETRY_WAIT_SECONDS

    def _capture_background_error(
        self, e: Exception, task_id: str, current_rid: str
    ) -> None:
        """将异常写入 error_logs 表，供错误日志页面展示和 AI 诊断

        延迟导入避免分层违规：error_capture 属于 web 层，scheduler 属于 modules 层。
        捕获本身失败时仅记日志，不应让错误处理流程再次抛出异常。
        """
        try:
            from xianyu_hunter.web.middleware.error_capture import capture_background_error
            capture_background_error(
                e,
                context={
                    "source": "scheduler.run_once",
                    "task_id": task_id,
                    "request_id": current_rid,
                },
            )
        except Exception:
            logger.warning("error_logs 捕获失败，跳过")

    def _pause_if_exceeded_fail_threshold(
        self, h: "_WorkerHandle", task_id: str
    ) -> bool:
        """连续失败超阈值时自动暂停任务，返回是否已触发暂停

        阈值由 antidetect.fail_pause_threshold 配置控制（默认 3），
        避免硬编码导致不同部署环境无法调整。
        """
        # 读取用户配置的失败暂停阈值（默认 3），而非硬编码 10
        try:
            from xianyu_hunter.infra.yaml_config import get_config
            max_errors = get_config().antidetect.fail_pause_threshold
        except Exception:
            max_errors = 3
        if h.consecutive_errors < max_errors:
            return False
        logger.error(
            f"[Task {task_id}] 连续失败 {h.consecutive_errors} 次，"
            f"达到阈值 {max_errors}，自动暂停任务"
        )
        h.pause_event.clear()
        h.task.status = TaskStatus.PAUSED
        # 同步数据库状态，确保 API 读取到正确的 paused 状态
        # 与 should_pause 分支保持一致
        if self._repo:
            try:
                self._repo.update_task_status(task_id, "paused")
            except Exception as db_err:
                logger.warning(f"[Task {task_id}] 暂停状态同步 DB 失败: {db_err}")
        return True

    def _compute_next_wait_seconds(
        self, cron_expr: str | None, interval: int, task_id: str
    ) -> float:
        """计算下一轮的等待秒数：cron 模式按表达式，interval 模式用固定间隔

        P1-7：cron 模式按表达式计算下次运行时间，interval 模式用固定间隔。
        cron 表达式无效时回退到 interval，保证调度不中断。

        P2-3：cron 模式下最小等待秒数不低于 antidetect.min_delay_ms / 1000，
        避免用户设置激进 cron（如 * * * * * 每分钟）导致请求频率超过反爬最小间隔
        """
        if not cron_expr:
            return interval
        try:
            from xianyu_hunter.modules.cron_utils import seconds_until_next_run
            wait_seconds = seconds_until_next_run(cron_expr)
            # 最小间隔保护：cron 计算出的等待秒数不得低于反爬最小延迟
            # 为什么读 min_delay_ms 而非硬编码：antidetect.min_delay_ms 是反爬基线，
            # 请求频率低于此值会触发 RGV587 检测，cron 间隔应与之对齐
            min_wait = self._get_min_cron_interval_seconds()
            if wait_seconds < min_wait:
                logger.warning(
                    f"[Task {task_id}] cron={cron_expr!r} 计算间隔 {wait_seconds:.0f}s "
                    f"低于反爬最小间隔 {min_wait}s，已自动上调"
                )
                return min_wait
            logger.debug(
                f"[Task {task_id}] cron={cron_expr!r} 下次运行在 {wait_seconds:.0f}s 后"
            )
            return wait_seconds
        except ValueError as e:
            logger.warning(
                f"[Task {task_id}] cron 表达式 {cron_expr!r} 无效，回退到 interval={interval}s: {e}"
            )
            return interval

    @staticmethod
    def _get_min_cron_interval_seconds() -> float:
        """读取反爬最小延迟作为 cron 模式最小间隔（秒），配置读取失败时回退到 10 秒"""
        try:
            from xianyu_hunter.infra.yaml_config import get_config
            return get_config().antidetect.min_delay_ms / 1000.0
        except Exception:
            return 10.0
