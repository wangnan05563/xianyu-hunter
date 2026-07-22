"""任务 Worker：单任务的「搜索→评估→下单」流水线

设计文档 §3.8 - TaskWorker 是纯编排，业务逻辑全部委托给现有模块：
- Collector（搜索/详情/卖家）
- ItemDedup（去重）
- PriceStrategy（价格过滤）
- Evaluator（卖家评估）
- Buyer（落单）

Worker 不持任何状态，调度由 TaskScheduler 负责。
"""
from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from xianyu_hunter.domain.evaluation import EvalResult, RiskLevel
from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.domain.item import ItemSummary
from xianyu_hunter.domain.order import BuyOutcome, BuyResult
from xianyu_hunter.domain.task import Task, TaskConfig, TaskMode
from xianyu_hunter.config import get_settings
from xianyu_hunter.infra.event_bus import EventBus
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.repo_links import task_keyword_matches_title
from xianyu_hunter.infra.yaml_config import EvalConfig, get_config
from xianyu_hunter.modules.buyer import Buyer
from xianyu_hunter.modules.collector import Collector
from xianyu_hunter.modules.dedup import ItemDedup
from xianyu_hunter.modules.evaluator import Evaluator, PriceRange
from xianyu_hunter.modules.price_strategy import MarketContext, PriceStrategy

logger = get_logger()

# S1192: 评估事件类型字面量在多处重复，提取为常量
_EVAL_SCORED_EVENT = "eval.scored"


@dataclass
class RunStats:
    """一轮 run_once 的统计"""
    found: int = 0           # 搜索结果数
    deduped: int = 0         # 去重过滤掉
    price_filtered: int = 0  # 价格过滤掉
    evaluated: int = 0       # 评估数
    passed: int = 0          # 评估通过数
    bought: int = 0          # 成功落单数
    failed: int = 0          # 落单失败数
    linked: int = 0          # 写入 task_links 数
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    # 自动官方采集统计（P1: 对通过评估的商品做深度验证）
    official_collected: int = 0            # 本轮成功采集数
    official_collect_paused: bool = False  # 连续失败达阈值后暂停本轮剩余采集


@dataclass
class RunResult:
    """run_once 完整结果"""
    stats: RunStats
    evaluations: list[EvalResult] = field(default_factory=list)
    buy_results: list[BuyResult] = field(default_factory=list)
    # RGV587 会话失效时设为 True，Scheduler 检测后自动暂停任务
    # 避免无效搜索持续占用 browser_lock，阻塞 live 端点
    should_pause: bool = False

    @property
    def has_bought(self) -> bool:
        return any(r.outcome == BuyOutcome.SUCCESS for r in self.buy_results)


class TaskWorker:
    """单任务 Worker

    使用方式：
        worker = TaskWorker(task=task, collector=..., ...)
        result = await worker.run_once()        # 跑一轮
        # 循环由 Scheduler 调用
    """

    def __init__(
        self,
        task: Task,
        collector: Collector,
        dedup: ItemDedup,
        price_strategy: PriceStrategy,
        evaluator: Evaluator,
        buyer: Buyer | None = None,  # 评估通过后是否真拍，模式 AUTO 时必传
        config: TaskConfig | None = None,
        repo: Any | None = None,  # 注入 repo 以写入 task_links
        event_bus: EventBus | None = None,  # 注入后用于触发 EVAL_PASSED 等通知事件
        # P1: 官方采集回调，对通过评估的商品做深度验证（提取评价/留言等爬虫无法获取的数据）
        # None 时跳过自动采集；container 构造时注入 startup._call_official_collect
        official_collect_fn: Any | None = None,
    ):
        self.task = task
        self.collector = collector
        self.dedup = dedup
        self.price = price_strategy
        self.evaluator = evaluator
        self.buyer = buyer
        self.config = config or TaskConfig()
        self.repo = repo
        # EventBus 用于把评估通过等业务事件投递给 NotifierHub
        # 为什么需要：NotifierHub 订阅 EVAL_PASSED 事件，但旧版 worker 不持有 bus，
        # 评估通过后只写数据库 events 表（用于时间线），从未通过 EventBus 触发事件，
        # 导致 NotifierHub 永远收不到 EVAL_PASSED，订阅了也发不出通知
        self.event_bus = event_bus
        self.official_collect_fn = official_collect_fn
        # 上次落单时间（用于冷却）
        self._last_buy_at: float = 0.0
        # 连续采集失败计数器：达到 auto_collect_fail_pause_threshold 后暂停本轮采集
        # 每轮 run_once 开头重置，避免上一轮的失败影响本轮（Cookie 可能已刷新）
        self._consecutive_collect_failures: int = 0
        # 任务级捡漏价格（P10）缓存：notify_bargain_only/auto_buy_bargain_only 开关启用时使用
        # 为什么缓存：避免每个商品都查询 task_links/items 表，单轮 run_once 内 P10 不变
        # None 表示未加载，float | None 表示加载后的值（None=无足够数据计算 P10）
        self._bargain_price_cache: float | None = None
        # 捡漏价格数据来源缓存（sold/all_fallback/all_fallback_insufficient/empty）  # NOSONAR S125:括号内为枚举值说明非注释代码
        # 为什么单独缓存：通知模板需展示来源，让用户事后能对比价格行情页口径
        self._bargain_source_cache: str | None = None
        self._bargain_price_loaded: bool = False

    def _get_task_bargain_price(self) -> float | None:
        """获取当前任务的捡漏价格（P10），单轮 run_once 内缓存

        复用 price_dashboard._compute_sold_range 保证口径与价格行情页一致。
        查询失败或无足够数据时返回 None，调用方按"未启用过滤"处理。
        同时填充 _bargain_source_cache，供通知模板渲染实际数据来源。
        """
        if self._bargain_price_loaded:
            return self._bargain_price_cache
        self._bargain_price_loaded = True
        if not self.repo:
            return None
        try:
            # 延迟导入避免循环依赖
            from xianyu_hunter.web.routes.price_dashboard import _compute_sold_range
            with self.repo.engine.connect() as conn:
                stats = _compute_sold_range(conn, self.task.id, range_days=30)
                self._bargain_price_cache = stats.get("bargain_price")
                self._bargain_source_cache = stats.get("source")
        except Exception as e:
            logger.warning("[Task {}] 查询捡漏价格失败，开关过滤降级为未启用: {}", self.task.id, e)
            self._bargain_price_cache = None
            self._bargain_source_cache = None
        return self._bargain_price_cache

    def cleanup(self) -> None:
        """Worker 资源清理钩子

        供 TaskScheduler.unregister 调用，确保注销任务时释放持有的资源。
        当前实现无后台 task 需取消（同步任务在 run_once 内完成），保留方法
        以兼容 scheduler 清理逻辑并为未来扩展（如 AI 评估后台 task）预留接入点。
        """
        return None

    def _effective_eval_cfg(self) -> EvalConfig:
        """合并任务级 eval_config 覆盖与全局 EvalConfig

        task.eval_config 为 None 或空 dict 时直接返回全局单例（无副本开销）。
        非 None 时过滤掉 None 值和未知字段后用 model_copy 创建副本，避免污染全局单例。
        未知字段需显式过滤：Pydantic v2 的 model_copy(update=...) 会直接 setattr
        未知键，不校验是否为模型字段，导致脏数据残留。
        """
        global_cfg = get_config().eval
        task_override = getattr(self.task, "eval_config", None)
        if not task_override:
            return global_cfg
        # 过滤 None 值：None 表示"不覆盖此字段"，与传 False 显式关闭语义不同
        # 过滤未知字段：前端可能误传 typo 或废弃字段，不应污染 EvalConfig 实例
        known_fields = type(global_cfg).model_fields
        updates = {
            k: v for k, v in task_override.items()
            if v is not None and k in known_fields
        }
        if not updates:
            return global_cfg
        return global_cfg.model_copy(update=updates)

    def _should_buy(self) -> bool:
        """根据模式判断本轮是否执行真拍"""
        if self.task.mode == TaskMode.AUTO:
            return True
        if self.task.mode == TaskMode.NOTIFY_ONLY:
            return False
        # CONFIRM / SEMI_AUTO 都不在 Worker 拍（由用户在 App 内确认）
        return False

    def _in_cooldown(self) -> bool:
        return (time.monotonic() - self._last_buy_at) < self.config.cooldown_after_buy

    def _save_task_links(self, items: list[ItemSummary]) -> None:
        """将搜索到的商品批量写入 task_links，供前端关联面板展示

        按关键词过滤：闲鱼搜索页可能返回默认推荐商品而非真实搜索结果，
        只有标题匹配任务关键词的商品才写入数据库，避免无关数据污染。
        """
        if not self.repo or not items:
            return
        saved = 0
        skipped = 0
        for item in items:
            title = getattr(item, "title", None) or ""
            if not task_keyword_matches_title(self.task.keyword, title):
                skipped += 1
                continue
            try:
                # 方案B改进：空字符串 seller_id 转为 None，避免覆盖详情页阶段已写入的非空值
                raw_seller_id = getattr(item, "seller_id", None)
                seller_id = raw_seller_id if raw_seller_id else None
                self.repo.upsert_item_task_links(
                    task_id=self.task.id,
                    item_id=item.id,
                    title=title,
                    price=getattr(item, "price", None),
                    thumb_url=getattr(item, "thumb_url", None),
                    seller_id=seller_id,
                    source="auto",
                    region=getattr(item, "region", None),
                    publish_time=getattr(item, "publish_time", None),
                    want_cnt=getattr(item, "want_cnt", None),
                    view_cnt=getattr(item, "view_cnt", None),
                    is_sold=getattr(item, "is_sold", False),
                    seller_nick=getattr(item, "seller_nick", None),
                    brand=getattr(item, "brand", None),
                )
                saved += 1
            except Exception as e:
                logger.warning(f"[Task {self.task.id}] 写入 task_links 失败 {getattr(item, 'id', '?')}: {e}")
        if skipped > 0:
            logger.info(f"[Task {self.task.id}] 关键词过滤跳过了 {skipped} 条无关商品")
        if saved > 0:
            logger.info(f"[Task {self.task.id}] 已写入 {saved} 条关联到 task_links")

    async def run_once(self) -> RunResult:
        """执行一轮完整流水线

        流程：搜索 → 去重 → 详情+卖家 → 价格过滤 → 评估 → 落单 → 写 task_links
        本方法只负责阶段编排，单阶段实现细节在对应的私有方法中
        """
        stats = RunStats()
        evaluations: list[EvalResult] = []
        buy_results: list[BuyResult] = []
        # 显式初始化，避免 finally 块中 dir() 反模式检查变量是否存在
        new_items: list[ItemSummary] | None = None
        settings = get_settings()
        eval_cfg = self._effective_eval_cfg()
        # 每轮重置连续失败计数器：新一轮可能已修复问题（Cookie 刷新/网络恢复），
        # 应给重新尝试的机会，不延续上一轮的失败状态
        self._consecutive_collect_failures = 0
        # 每轮重置 P10 缓存：捡漏价格基于历史已售数据，新一轮可能已采集更多样本
        # 为什么不跨轮缓存：避免长期缓存导致 P10 滞后，开关过滤失效
        self._bargain_price_cache = None
        self._bargain_source_cache = None
        self._bargain_price_loaded = False

        try:
            # 1. 搜索阶段：超时/会话失效直接返回，调用方据 stats 决策
            items = await self._search_phase(stats)
            if items is None:
                return RunResult(stats=stats, should_pause=True)

            # 2. 去重 + 限流：返回 None 表示本轮无可处理商品
            new_items = self._dedup_and_limit(items, stats)
            if new_items is None:
                return RunResult(stats=stats)

            # 3. 立即写 task_links + 估算市场价
            self._save_task_links(new_items)
            stats.linked = sum(
                1 for item in new_items
                if task_keyword_matches_title(self.task.keyword, getattr(item, "title", None))
            )
            market_ctx = self._compute_market_context(new_items)

            # 4. 详情/评估/落单：处理循环内部异常通过返回值控制是否提前终止
            early_return = await self._process_items_loop(
                new_items, market_ctx, eval_cfg, settings, stats, evaluations, buy_results
            )
            if early_return is not None:
                return early_return
        finally:
            self._finalize_run(stats, new_items)

        logger.info(
            f"[Task {self.task.id}] 本轮完成: 找到 {stats.found} / "
            f"去重 {stats.deduped} / 价格过滤 {stats.price_filtered} / "
            f"评估 {stats.evaluated} / 通过 {stats.passed} / "
            f"落单 {stats.bought} / 失败 {stats.failed} / 关联 {stats.linked}"
        )
        return RunResult(stats=stats, evaluations=evaluations, buy_results=buy_results)

    async def _search_phase(self, stats: RunStats) -> list[ItemSummary] | None:
        """搜索阶段：返回商品列表，会话失效或超时返回 None

        会话失效检测放在搜索之后：detail 阶段若已会话失效，
        collector 会置 last_session_invalid=True，由调用方统一处理暂停
        """
        logger.info(f"[Task {self.task.id}] 搜索「{self.task.keyword}」")
        await self._sync_cookie_before_search()
        combined_filters = self._build_combined_search_filters()
        items = await self._execute_search_with_timeout(combined_filters, stats)
        if items is None:
            # 搜索超时：持续占用 browser_lock 阻塞 live 端点，因此暂停任务
            return None
        stats.found = len(items)
        logger.info(f"[Task {self.task.id}] 搜索到 {stats.found} 件")

        await self._yield_to_live_queries()

        # RGV587 会话失效时通知 Scheduler 暂停任务
        # 避免无效搜索持续占用 browser_lock，阻塞 live 端点的实时搜索
        if getattr(self.collector, 'last_session_invalid', False):
            logger.warning(f"[Task {self.task.id}] 闲鱼会话失效（RGV587_ERROR），自动暂停任务，请重新登录闲鱼")
            self._invalidate_session_identity()
            stats.finished_at = datetime.now(timezone.utc)
            return None
        return items

    def _dedup_and_limit(self, items: list[ItemSummary], stats: RunStats) -> list[ItemSummary] | None:
        """去重 + 限制每轮条数，无可处理商品返回 None

        ItemDedup.filter_new 是同步方法（基于 repo.items_exist 批量查询），
        无需 await——之前误用 await 会被 async FakeDedup 掩盖，生产环境会抛 TypeError
        """
        new_items = self.dedup.filter_new(items)
        stats.deduped = stats.found - len(new_items)
        if not new_items:
            logger.info(f"[Task {self.task.id}] 全部已看过，本轮跳过")
            stats.finished_at = datetime.now(timezone.utc)
            return None
        # 限制每轮条数：使用用户配置的 page_size（默认 20）
        # 避免处理过多商品导致 OOM 或超时
        max_items = self.config.search_page_size or self.config.max_items_per_run
        return new_items[:max_items]

    async def _process_items_loop(
        self, new_items: list[ItemSummary], market_ctx: MarketContext | None,
        eval_cfg: EvalConfig, settings: Any, stats: RunStats,
        evaluations: list[EvalResult], buy_results: list[BuyResult]
    ) -> RunResult | None:
        """串行拉取详情 + 卖家主页并执行评估/落单

        复用单个详情页和卖家页，避免并发打开多个浏览器窗口
        （原 Semaphore(3)+gather 实现每轮弹出 6 个窗口，干扰用户操作）
        返回 RunResult 表示应提前终止本轮；None 表示正常完成
        """
        shared_pages: dict = {"detail": None, "seller": None}
        # collector.browser 可能为 None（测试环境），此时不创建复用页面
        _has_browser = getattr(self.collector, 'browser', None) is not None
        try:
            for summary in new_items:
                if not summary.id:
                    continue
                # 详情采集前再次检测会话失效，避免无效请求
                if getattr(self.collector, 'last_session_invalid', False):
                    logger.warning(
                        "[Task {}] 详情采集前检测到闲鱼会话失效，停止本轮并暂停任务",
                        self.task.id,
                    )
                    stats.finished_at = datetime.now(timezone.utc)
                    return RunResult(stats=stats, evaluations=evaluations, buy_results=buy_results, should_pause=True)

                detail, seller, should_pause = await self._collect_detail_and_seller(
                    summary, shared_pages, _has_browser
                )
                if should_pause:
                    stats.finished_at = datetime.now(timezone.utc)
                    return RunResult(stats=stats, evaluations=evaluations, buy_results=buy_results, should_pause=True)
                if not detail or not seller:
                    continue

                # 用详情页采集到的 seller_id 更新 task_links
                self._update_seller_in_task_links(detail, summary)

                # 单商品处理（评估/AI/落单）独立方法，异常隔离到单条商品
                stop = await self._process_single_item(
                    detail, seller, summary, market_ctx, eval_cfg,
                    settings, _has_browser, stats, evaluations, buy_results
                )
                if stop:
                    break
        finally:
            # 关闭复用的详情页和卖家页，避免页面泄漏
            await self._close_shared_pages(shared_pages)
        return None

    async def _process_single_item(
        self, detail: Any, seller: Any, summary: ItemSummary,
        market_ctx: MarketContext | None, eval_cfg: EvalConfig, settings: Any,
        _has_browser: bool, stats: RunStats,
        evaluations: list[EvalResult], buy_results: list[BuyResult]
    ) -> bool:
        """处理单个商品：价格过滤 → 评估 → AI 二次确认 → 通知 → 官方采集 → 落单

        返回 True 表示已抢单成功且配置 stop_on_first_buy，调用方应终止循环；
        任何单条商品异常都被捕获并记录，不影响后续商品处理
        """
        try:
            # 4. 价格过滤 + 5. 评估
            eval_result = self._evaluate_item(detail, seller, market_ctx, stats, evaluations)
            if eval_result is None:
                return False

            # 写入 events 表，供评估明细/事件中心展示
            self._save_eval_event(detail, eval_result)

            # 推送门槛：使用配置的 pass_score（默认 60）
            # 通过此门槛的商品会进入 AI 评估和推送通知流程
            # 但不一定会触发抢单（抢单需达到 auto_buy_score，见下方落单判断）
            _pass_score = eval_cfg.pass_score if eval_cfg else 60
            if not eval_result.should_pass(_pass_score):
                return False
            stats.passed += 1

            # 5.5 AI 自动评估（可选，消耗 token）
            ai_eval_result = await self._run_ai_auto_eval(
                detail, eval_result, eval_cfg, settings, _has_browser
            )
            if ai_eval_result is None:
                return False
            eval_result = ai_eval_result

            # 5.6 AI 深度分析（可选，消耗更多 token）
            if not await self._run_ai_deep_analyze(detail, eval_cfg, settings, _has_browser):
                return False

            # 触发 EVAL_PASSED 事件，让 NotifierHub 等订阅者收到通知
            # 为什么放在 AI 评估/深度分析之后：避免 AI reject 后仍发通知造成误报，
            # 确保只有最终通过的商品才触发推送。用 publish_nowait 避免阻塞主流程
            self._publish_eval_passed_event(detail, eval_result, _pass_score)

            # 5.8 自动官方采集（P1: 对通过评估的商品做深度验证）
            # 放在 EVAL_PASSED 之后：采集是深度验证，失败不影响已发出的通知
            await self._run_official_collect(detail, stats, eval_cfg)

            # 6. 落单
            action = await self._attempt_buy(detail, eval_result, eval_cfg, stats, buy_results)
            return action == "break"
        except Exception as e:  # noqa: BLE001
            logger.exception(f"[Task {self.task.id}] 处理 {summary.id} 出错")
            # 捕获到 error_logs 表，供错误日志页面展示
            # 这里是单商品处理异常，记录后由调用方 continue 跳过该商品，不影响整体流程
            try:
                from xianyu_hunter.web.middleware.error_capture import capture_background_error
                capture_background_error(e, context={
                    "source": "worker.run_once.process_item",
                    "task_id": self.task.id,
                    "item_id": getattr(summary, 'id', None),
                })
            except Exception:
                pass
            return False

    def _compute_market_context(self, items: list) -> MarketContext | None:
        """从当前批次的商品中估算市场参考价（中位数 + 全量价格列表）"""
        prices = [
            i.price for i in items
            if getattr(i, "price", None) is not None
        ]
        if len(prices) < 3:
            return None
        prices.sort()
        n = len(prices)
        median = prices[n // 2] if n % 2 == 1 else (prices[n // 2 - 1] + prices[n // 2]) / 2
        # 传入 all_prices 供 TopN 策略逐商品计算 cheaper_seller_count
        return MarketContext(median_price=median, sample_size=n, all_prices=prices)

    # ------------------------------------------------------------------
    # run_once 的子方法：每个方法对应流水线的一个独立职责
    # 提取目的：降低 run_once 认知复杂度（S3776 阈值 15），保持业务行为不变
    # ------------------------------------------------------------------

    async def _sync_cookie_before_search(self) -> None:
        """搜索前同步 Cookie 到浏览器，失败时仅 debug 日志不中断流程

        为什么不中断：Cookie 同步是搜索的增强而非前置条件，
        同步失败时 collector 仍可能用旧 Cookie 完成搜索
        """
        try:
            from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_browser
            from xianyu_hunter.web.services.user_manager import get_user_manager

            # 多用户场景下必须传当前活跃 user_id，否则默认 "default" 找不到 cookies_default.json
            # 导致 CookieStore 为空 → 浏览器无 Cookie → 反爬拦截 → 卖家信息提取失败
            await inject_cookie_store_to_browser(
                getattr(self.collector, "browser", None),
                "后台任务搜索前 Cookie 同步",
                collector=self.collector,
                force_refresh_m5tk=False,
                user_id=get_user_manager().get_active_user_id(),
            )
        except Exception as e:
            logger.debug(f"[Task {self.task.id}] 搜索前 Cookie 同步失败: {e}")

    def _build_combined_search_filters(self) -> list:
        """合并任务级与全局搜索筛选标签

        任务级优先（用户创建任务时指定的筛选），全局配置作为补充
        """
        task_filters = getattr(self.task, 'search_filters', None) or []
        global_filters = self.config.search_filter_tags or []
        return list(set(task_filters + global_filters))

    async def _execute_search_with_timeout(
        self, combined_filters: list, stats: RunStats
    ) -> list[ItemSummary] | None:
        """执行搜索，超时返回 None 由调用方决定暂停策略

        搜索超时通常意味着浏览器卡住或网络异常，继续循环只会再次超时
        """
        search_timeout = self.config.search_timeout
        try:
            items = await asyncio.wait_for(
                self.collector.search(
                    self.task.keyword,
                    search_filters=combined_filters,
                    # Worker 不使用 fast 模式：需要刷新 _m_h5_tk token 避免会话失效
                    skip_rgv587_retry=True,
                    sort_type=self.config.search_sort_type,
                    regions=self.config.search_regions,
                    max_pages=self.config.search_max_pages,
                ),
                timeout=float(search_timeout),
            )
            return items
        except asyncio.TimeoutError:
            logger.warning(f"[Task {self.task.id}] 搜索超时（{search_timeout}秒），自动暂停任务")
            stats.finished_at = datetime.now(timezone.utc)
            return None

    async def _yield_to_live_queries(self) -> None:
        """搜索完成后检测实时查询等待，延迟让出浏览器锁

        优先级锁让出：搜索完成后锁已释放，如果有 live 端点在等待，
        延迟 3 秒让 live 请求优先获取锁（减少实时查询等待时间）
        """
        _lock = getattr(self.collector, '_browser_lock', None)
        if _lock is not None and getattr(_lock, 'has_high_priority_waiting', False):
            logger.info(f"[Task {self.task.id}] 检测到实时查询等待中，延迟 3 秒让出浏览器")
            await asyncio.sleep(3)

    def _invalidate_session_identity(self) -> None:
        """主动失效 orchestrator 的 identity 层，让健康检查反映真实状态

        为什么需要：cookie 本地仍存在但服务端已注销，
        健康检查器需要感知此状态才能给出正确的 RELOGIN 建议
        为什么 manual=False：系统检测到的失效应能被 cookie_checker
        在 cookie 实际恢复有效时自动同步恢复，避免状态永久锁定
        """
        try:
            from xianyu_hunter.modules.login_orchestrator import get_orchestrator
            from xianyu_hunter.modules.cookie_rotator import CookieLayer
            get_orchestrator().cookie_rotator.invalidate_layer(CookieLayer.IDENTITY, manual=False)
        except Exception:
            pass

    async def _collect_detail_and_seller(
        self, summary: ItemSummary, shared_pages: dict, _has_browser: bool
    ) -> tuple[Any, Any, bool]:
        """采集单个商品的详情和卖家信息

        返回 (detail, seller, should_pause)：
        - should_pause=True 表示会话失效，调用方应暂停任务
        - detail/seller 为 None 表示采集失败，调用方应 continue
        """
        detail = None
        # 初始化 seller 避免 except 块中引用未定义变量
        seller = None
        try:
            detail, should_pause = await self._fetch_detail_with_session_check(
                summary, shared_pages, _has_browser
            )
            if should_pause:
                return None, None, True
            if detail is None:
                return None, None, False
            # 复用卖家页（首次创建，后续复用）
            # seller_profile 失败时使用降级策略（搜索页+详情页信息），而非空默认值
            seller = None
            if detail.seller_id:
                if _has_browser and shared_pages["seller"] is None:
                    shared_pages["seller"] = await self.collector.browser.new_page()
                seller = await self.collector.seller_profile(detail.seller_id, page=shared_pages["seller"])
            if not seller:
                logger.info("[Task {}] 卖家主页获取失败，使用降级策略评估 {}", self.task.id, summary.id)
                # 降级策略：合并搜索结果+详情页的卖家信息构建基本画像
                seller = await self._seller_profile_fallback(summary=summary, detail=detail)
            self._merge_detail_seller_fields(seller, detail)
        except Exception as e:
            logger.warning("[Task {}] 采集异常 {}: {}", self.task.id, summary.id, e)
            detail = None
            # 异常时也尝试用搜索结果构建降级 SellerProfile（如果有 summary）
            if not seller and hasattr(self, 'collector'):
                seller = await self._seller_profile_fallback(summary=summary, detail=detail)
        return detail, seller, False

    async def _fetch_detail_with_session_check(
        self, summary: ItemSummary, shared_pages: dict, _has_browser: bool
    ) -> tuple[Any, bool]:
        """获取详情页并检测会话失效

        返回 (detail, should_pause)：
        - should_pause=True 表示会话失效，调用方应暂停任务
        - detail 为 None 表示采集失败（会话失效或详情获取失败）
        """
        # 复用详情页（首次创建，后续复用）
        if _has_browser and shared_pages["detail"] is None:
            shared_pages["detail"] = await self.collector.browser.new_page()
        detail = await self.collector.detail(summary.id, page=shared_pages["detail"])
        if getattr(self.collector, 'last_session_invalid', False):
            logger.warning(
                "[Task {}] 详情页检测到闲鱼会话失效，停止本轮并暂停任务",
                self.task.id,
            )
            return None, True
        if not detail:
            logger.warning("[Task {}] 详情页获取失败，跳过 {}", self.task.id, summary.id)
            return None, False
        return detail, False

    def _merge_detail_seller_fields(self, seller: Any, detail: Any) -> None:
        """用详情页字段补充 seller_profile 缺失的卖家维度

        为什么需要：seller_profile 可能因页面变更/反爬返回部分字段为空的 SellerProfile，
        用 detail 页的 detail_credit_score/detail_register_days/detail_sold_count/detail_seller_nick
        补充缺失字段，避免 evaluator 因维度数据不足触发 _evaluate_insufficient 模式（cap 65 分）。
        与 collection_service._collect_official_full line 720 的 _merge_detail_seller_fields 对齐。
        """
        if not (seller and detail):
            return
        if not getattr(seller, 'nick', None) and getattr(detail, 'detail_seller_nick', None):
            seller.nick = detail.detail_seller_nick
        if getattr(seller, 'credit_score', None) is None and getattr(detail, 'detail_credit_score', None) is not None:
            seller.credit_score = detail.detail_credit_score
        if not getattr(seller, 'sold_count', None) and getattr(detail, 'detail_sold_count', None):
            seller.sold_count = detail.detail_sold_count
        if not getattr(seller, 'register_days', None) and getattr(detail, 'detail_register_days', None):
            seller.register_days = detail.detail_register_days

    async def _seller_profile_fallback(self, summary: ItemSummary | None = None, detail: Any | None = None) -> Any | None:
        fallback = getattr(self.collector, "seller_profile_fallback", None)
        if not callable(fallback):
            return None
        result = fallback(summary=summary, detail=detail)
        if inspect.isawaitable(result):
            return await result
        return result

    def _update_seller_in_task_links(self, detail: Any, summary: ItemSummary) -> None:
        """用详情页采集到的 seller_id 更新 task_links

        详情页阶段也需关键词过滤：_save_task_links 已过滤过一轮，
        但 new_items 中可能包含被 _save_task_links 跳过的 noise 商品，
        此处再次过滤避免写入无关关联
        """
        if not (detail.seller_id and self.repo and task_keyword_matches_title(self.task.keyword, detail.title)):
            return
        try:
            self.repo.upsert_item_task_links(
                task_id=self.task.id,
                item_id=detail.id,
                title=detail.title,
                price=detail.price,
                thumb_url=summary.thumb_url,
                seller_id=detail.seller_id,
                source="auto",
                region=getattr(detail, "region", None),
                publish_time=getattr(detail, "publish_time", None),
                want_cnt=getattr(detail, "want_cnt", None),
                view_cnt=getattr(detail, "view_cnt", None),
                is_sold=getattr(summary, "is_sold", False),
                brand=getattr(detail, "brand", None),
            )
        except Exception as e:
            logger.warning(
                "[Task {}] 更新卖家关联失败 {}: {}",
                self.task.id, detail.id, e,
            )

    def _evaluate_item(
        self, detail: Any, seller: Any, market_ctx: MarketContext | None,
        stats: RunStats, evaluations: list[EvalResult]
    ) -> EvalResult | None:
        """价格过滤 + 评估，未通过价格过滤返回 None"""
        verdict = self.price.check(detail, market_ctx)
        if not verdict.pass_:
            stats.price_filtered += 1
            return None
        price_range = PriceRange.from_price_config(getattr(self.price, "config", None))
        if price_range is None:
            eval_result = self.evaluator.evaluate(detail, seller)
        else:
            eval_result = self.evaluator.evaluate(detail, seller, price_range=price_range)
        stats.evaluated += 1
        evaluations.append(eval_result)
        return eval_result

    def _save_eval_event(self, detail: Any, eval_result: EvalResult) -> None:
        """写入评估事件到 events 表，供评估明细/事件中心展示

        不写入则前端评估明细和事件中心页面永远无数据
        """
        if not self.repo:
            return
        try:
            import json as _json
            score_display = eval_result.score if eval_result.score is not None else "N/A"
            # S3358: 提取嵌套三元为独立变量
            if eval_result.is_passed:
                level = "info"
            elif eval_result.risk_level == RiskLevel.EXTREME:
                level = "err"
            else:
                level = "warn"
            if eval_result.risk_level == RiskLevel.UNKNOWN:
                level = "warn"  # 数据不足用 warn 级别，避免误报为错误
            self.repo.upsert_eval_event({
                "type": _EVAL_SCORED_EVENT,
                "task_id": self.task.id,
                "item_id": detail.id,  # 顶层 item_id 供前端 dataIndex 直接读取
                "stage": "eval",
                "level": level,
                "message": f"商品 {detail.id} 评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
                "payload": _json.dumps({
                    "task_id": self.task.id,  # 写入 payload 供官方采集回查 effective_task_id
                    "item_id": detail.id,
                    "item_title": detail.title,       # 前端期望 item_title
                    "item_price": detail.price,       # 前端期望 item_price
                    "seller_id": detail.seller_id,   # 卖家ID（详情页采集）
                    "seller_nick": detail.detail_seller_nick or "",  # 卖家昵称
                    "score": eval_result.score,  # 可能为 None
                    "risk_level": eval_result.risk_level.value,
                    "dimension_scores": eval_result.dimension_scores,
                    "reject_reasons": eval_result.reject_reasons,
                    "is_passed": eval_result.is_passed,
                    "data_quality": eval_result.data_quality,
                }, ensure_ascii=False, default=str),  # default=str 处理 None 值
            })
        except Exception as e:
            logger.warning(f"[Task {self.task.id}] 写入评估事件失败: {e}")

    async def _run_ai_auto_eval(
        self, detail: Any, eval_result: EvalResult, eval_cfg: EvalConfig,
        settings: Any, _has_browser: bool
    ) -> EvalResult | None:
        """AI 自动评估，返回更新后的 eval_result；AI 拒绝时返回 None 表示跳过

        开启后对通过规则评估的商品自动调用 AI 二次确认
        """
        if not (_has_browser and settings.ai_enabled and eval_cfg.ai_auto_eval and settings.openai_api_key):
            return eval_result
        try:
            from xianyu_hunter.web.routes.api_ai import _call_llm_vision
            ai_result = await _call_llm_vision(
                detail.title, detail.description or "",
                detail.price or 0, detail.image_urls or [],
            )
            ai_verdict = ai_result.get("verdict", "")
            ai_condition_score = ai_result.get("condition_score", 0)

            # P2 优化：AI 评估结果实质性地影响总分
            # 旧逻辑仅追加到 dimension_scores 不影响总分，
            # 新逻辑通过 apply_ai_eval 调整总分和风险等级
            eval_result = self.evaluator.apply_ai_eval(
                eval_result, ai_verdict, ai_condition_score
            )

            if ai_verdict == "reject":
                logger.info("[Task {}] AI 评估拒绝 {} (score={})，跳过", self.task.id, detail.id, ai_condition_score)
                # 更新 events 表中的评估记录
                if self.repo:
                    try:
                        self.repo.update_eval_payload_by_keys(
                            self.task.id, detail.id, _EVAL_SCORED_EVENT,
                            {"score": eval_result.score,
                             "risk_level": eval_result.risk_level.value,
                             "dimension_scores": eval_result.dimension_scores,
                             "reject_reasons": eval_result.reject_reasons,
                             "is_passed": False},
                        )
                    except Exception:
                        pass
                return None

            # 更新 events 表中的评估记录（AI 调整后的分数）
            if self.repo:
                try:
                    self.repo.update_eval_payload_by_keys(
                        self.task.id, detail.id, _EVAL_SCORED_EVENT,
                        {"score": eval_result.score,
                         "risk_level": eval_result.risk_level.value,
                         "dimension_scores": eval_result.dimension_scores,
                         "reject_reasons": eval_result.reject_reasons,
                         "is_passed": eval_result.is_passed},
                    )
                except Exception as e:
                    logger.warning(f"[Task {self.task.id}] 更新 AI 评估事件失败: {e}")
        except Exception as e:
            logger.warning("[Task {}] AI 自动评估失败，继续规则评估: {}", self.task.id, e)
        return eval_result

    async def _run_ai_deep_analyze(
        self, detail: Any, eval_cfg: EvalConfig, settings: Any, _has_browser: bool
    ) -> bool:
        """AI 深度分析，返回 False 表示应跳过该商品"""
        if not (_has_browser and settings.ai_enabled and eval_cfg.ai_auto_deep_analyze and settings.openai_api_key):
            return True
        try:
            from xianyu_hunter.web.routes.api_ai_deep import _call_llm_deep_analyze
            deep_result = await _call_llm_deep_analyze(
                detail.title, detail.description or "",
                detail.price or 0, detail.image_urls or [],
            )
            overall = deep_result.get("overall", {})
            if overall.get("verdict") == "reject":
                logger.info("[Task {}] AI 深度分析拒绝 {}，跳过", self.task.id, detail.id)
                return False
        except Exception as e:
            logger.warning("[Task {}] AI 深度分析失败，继续: {}", self.task.id, e)
        return True

    def _publish_eval_passed_event(
        self, detail: Any, eval_result: EvalResult, pass_score: float
    ) -> None:
        """触发 EVAL_PASSED 事件，让 NotifierHub 等订阅者收到通知

        为什么 payload 用扁平字段而非 item 子对象：
        - notifier/templates.py 的 _eval_passed 模板优先消费扁平字段
        - 与 collection_service / api_evaluations 补发的 EVAL_PASSED 字段对齐
        - 减少嵌套层级，便于日志/调试

        notify_bargain_only 开关优先级矩阵：
        - mode=notify/auto/semi_auto/confirm：开关启用时仅价格≤P10 才发通知
        - 开关关闭：所有通过评估的商品都发通知（向后兼容）
        - P10 查询失败：降级为未启用过滤，避免阻断通知链
        """
        if self.event_bus is None:
            return
        # 通知触发开关过滤：价格 > P10 时跳过通知
        # 同时记录实际使用的捡漏价与来源，供通知模板展示口径一致性信息
        bargain_used: float | None = None
        bargain_source: str | None = None
        if getattr(self.task, "notify_bargain_only", False):
            bargain_used = self._get_task_bargain_price()
            bargain_source = self._bargain_source_cache
            if bargain_used is not None and detail.price is not None and detail.price > bargain_used:
                logger.info(
                    "[Task {}] {} 价格 {} > 捡漏价 {}，notify_bargain_only 开关过滤跳过通知",
                    self.task.id, detail.id, detail.price, bargain_used,
                )
                return
        try:
            self.event_bus.publish_nowait(
                Event(
                    type=EventType.EVAL_PASSED,
                    task_id=self.task.id,
                    item_id=detail.id,
                    payload={
                        "item_id": detail.id,
                        "item_title": detail.title,
                        "item_price": detail.price,
                        "thumb_url": getattr(detail, "thumb_url", ""),
                        "region": getattr(detail, "region", ""),
                        "seller_id": detail.seller_id,
                        "seller_nick": getattr(detail, "seller_nick", ""),
                        "score": eval_result.score,
                        "risk_level": eval_result.risk_level.value,
                        # 不再传 is_passed：此处必为 True，字段冗余
                        "data_quality": eval_result.data_quality,
                        "reject_reasons": eval_result.reject_reasons or [],
                        "pass_score": pass_score,
                        # SEMI_AUTO 模式下通知模板需要渲染"确认抢单"链接，
                        # 让用户点击链接跳转到前端 /confirm-buy 页面触发抢单
                        "task_mode": self.task.mode.value,
                        # 实际过滤使用的捡漏价与数据来源（仅 notify_bargain_only 启用时填充）
                        # 为什么传给通知：让用户从通知内容能反查为何被推送，
                        # 避免价格行情页"全部任务聚合值"与 worker"任务级 P10"口径不一致导致困惑
                        "bargain_price_used": bargain_used,
                        "bargain_source": bargain_source,
                    },
                )
            )
        except Exception as e:
            logger.warning(f"[Task {self.task.id}] 触发 EVAL_PASSED 事件失败: {e}")

    async def _run_official_collect(
        self, detail: Any, stats: RunStats, eval_cfg: EvalConfig
    ) -> None:
        """自动官方采集：对通过评估的商品做深度验证

        四个 AND 条件全满足才触发：配置开启 + 回调已注入 + 未暂停 + 配额未耗尽
        """
        if not (eval_cfg
                and eval_cfg.auto_collect_official
                and self.official_collect_fn is not None
                and not stats.official_collect_paused
                and stats.official_collected < eval_cfg.auto_collect_max_per_run):
            return
        try:
            await self.official_collect_fn(detail.id, self.task.id)
            stats.official_collected += 1
            # 成功时重置计数器：偶发失败不应累积触发暂停
            self._consecutive_collect_failures = 0
        except Exception as collect_err:
            self._consecutive_collect_failures += 1
            logger.warning(
                f"[Task {self.task.id}] 官方采集失败 {detail.id}: {collect_err}"
            )
            # 达到阈值后暂停本轮剩余商品的采集，避免持续失败浪费配额
            if (self._consecutive_collect_failures
                    >= eval_cfg.auto_collect_fail_pause_threshold):
                stats.official_collect_paused = True
                logger.warning(
                    f"[Task {self.task.id}] 连续采集失败 "
                    f"{self._consecutive_collect_failures} 次，暂停本轮自动采集"
                )
                # 通过 EventBus 发送暂停告警，与 EVAL_PASSED 路径一致
                if self.event_bus is not None:
                    try:
                        self.event_bus.publish_nowait(
                            Event(
                                type=EventType.TASK_ERROR,
                                task_id=self.task.id,
                                item_id=detail.id,
                                payload={
                                    "reason": "auto_collect_paused",
                                    "consecutive_failures": self._consecutive_collect_failures,
                                    "threshold": eval_cfg.auto_collect_fail_pause_threshold,
                                },
                            )
                        )
                    except Exception as alert_err:
                        logger.warning(
                            f"[Task {self.task.id}] 触发采集暂停告警失败: {alert_err}"
                        )

    async def _attempt_buy(
        self, detail: Any, eval_result: EvalResult, eval_cfg: EvalConfig,
        stats: RunStats, buy_results: list[BuyResult]
    ) -> str | None:
        """落单决策，返回 "break"（抢到停止本轮）或 None（正常结束/跳过）

        区分推送门槛与抢单门槛：
        - pass_score(60) 用于推送通知（is_passed 已在上方检查）
        - auto_buy_score(75) 用于全自动拍下，避免 60-74 分中等分数商品被误抢单

        auto_buy_bargain_only 开关优先级矩阵：
        - mode=notify：开关无意义（仅通知模式不下单），_should_buy 已返回 False
        - mode=auto/semi_auto/confirm：开关启用时仅价格≤P10 才执行抢单
        - 开关关闭：所有达到 auto_buy_score 的商品都抢单（向后兼容）
        - P10 查询失败：降级为未启用过滤，避免阻断抢单链
        """
        if not self._should_buy():
            # 为什么加日志：非 AUTO 模式跳过抢单是高频原因，
            # 缺少日志时用户无法定位"评分达标却未抢单"的根因
            logger.info(
                f"[Task {self.task.id}] 任务模式 {self.task.mode.value} 非自动抢单(AUTO)，跳过 {detail.id}"
            )
            return None
        _auto_buy_score = eval_cfg.auto_buy_score if eval_cfg else 80
        if not eval_result.should_auto_buy(_auto_buy_score):
            logger.info(
                f"[Task {self.task.id}] {detail.id} 评估分 {eval_result.score} "
                f"未达 auto_buy_score({_auto_buy_score}) 或非低风险({eval_result.risk_level.value})，跳过抢单"
            )
            return None
        # 自动下单触发开关过滤：价格 > P10 时跳过抢单
        if getattr(self.task, "auto_buy_bargain_only", False):
            bargain = self._get_task_bargain_price()
            if bargain is not None and detail.price is not None and detail.price > bargain:
                logger.info(
                    "[Task {}] {} 价格 {} > 捡漏价 {}，auto_buy_bargain_only 开关过滤跳过抢单",
                    self.task.id, detail.id, detail.price, bargain,
                )
                return None
        # buyer 未注入时跳过落单：with_browser=False 模式下 container.buyer 为 None，
        # 或浏览器启动失败后 Buyer 仍可能未就绪。此时不应抛出 AttributeError 中断流程
        if self.buyer is None:
            logger.warning(
                f"[Task {self.task.id}] buyer 未注入（with_browser=False 或初始化失败），跳过落单 {detail.id}"
            )
            return None
        if self._in_cooldown():
            logger.info(
                f"[Task {self.task.id}] 冷却中，跳过 {detail.id}"
            )
            return None

        buy_result = await self.buyer.buy(  # type: ignore[misc]
            task_id=self.task.id,
            item_id=detail.id,
            expected_price=detail.price,
        )
        buy_results.append(buy_result)
        if buy_result.outcome == BuyOutcome.SUCCESS:
            stats.bought += 1
            self._last_buy_at = time.monotonic()
            if self.config.stop_on_first_buy:
                logger.info(
                    f"[Task {self.task.id}] 抢到 1 单，按策略停止本轮"
                )
                return "break"
        else:
            stats.failed += 1
        return None

    async def _close_shared_pages(self, shared_pages: dict) -> None:
        """关闭复用的详情页和卖家页，避免页面泄漏"""
        for key in ("detail", "seller"):
            _p = shared_pages.get(key)
            if _p is not None:
                try:
                    await _p.close()
                except Exception:
                    pass

    def _finalize_run(self, stats: RunStats, new_items: list[ItemSummary] | None) -> None:
        """收尾：设置完成时间 + 持久化 items + 兜底写入 task_links + 写入 search_done 事件"""
        stats.finished_at = datetime.now(timezone.utc)
        # 确保商品持久化到 items 表（去重 + 关联查询依赖此数据）
        if new_items:
            try:
                self.dedup.save(new_items, task_id=self.task.id)
            except Exception as e:
                logger.warning("[Task {}] 持久化 items 失败: {}", self.task.id, e)
        # 兜底：如果 try 块因异常未执行 _save_task_links，在 finally 中补调用
        # 使用 new_items（已去重）而非 items（原始），避免保存无关默认推荐
        if stats.linked == 0 and new_items:
            self._save_task_links(new_items)
        # 写入搜索完成事件，供事件中心/时间线展示
        if self.repo:
            try:
                import json as _json
                self.repo.save_event({
                    "type": "task.search_done",
                    "task_id": self.task.id,
                    "stage": "search",
                    "level": "info",
                    "message": f"搜索完成: 找到{stats.found}/去重{stats.deduped}/评估{stats.evaluated}/通过{stats.passed}",
                    "payload": _json.dumps({
                        "found": stats.found,
                        "deduped": stats.deduped,
                        "price_filtered": stats.price_filtered,
                        "evaluated": stats.evaluated,
                        "passed": stats.passed,
                        "bought": stats.bought,
                        "failed": stats.failed,
                        "linked": stats.linked,
                    }, ensure_ascii=False),
                })
            except Exception as e:
                logger.warning(f"[Task {self.task.id}] 写入搜索事件失败: {e}")
