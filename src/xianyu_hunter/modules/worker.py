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
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from xianyu_hunter.domain.evaluation import EvalResult
from xianyu_hunter.domain.item import ItemDetail, ItemSummary
from xianyu_hunter.domain.order import BuyOutcome, BuyResult
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.domain.task import Task, TaskConfig, TaskMode
from xianyu_hunter.config import get_settings
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.repo_links import task_keyword_matches_title
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.modules.buyer import Buyer
from xianyu_hunter.modules.collector import Collector
from xianyu_hunter.modules.dedup import ItemDedup
from xianyu_hunter.modules.evaluator import Evaluator
from xianyu_hunter.modules.price_strategy import MarketContext, PriceStrategy

logger = get_logger()


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
    ):
        self.task = task
        self.collector = collector
        self.dedup = dedup
        self.price = price_strategy
        self.evaluator = evaluator
        self.buyer = buyer
        self.config = config or TaskConfig()
        self.repo = repo
        # 上次落单时间（用于冷却）
        self._last_buy_at: float = 0.0

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
                self.repo.upsert_item_task_links(
                    task_id=self.task.id,
                    item_id=item.id,
                    title=title,
                    price=getattr(item, "price", None),
                    thumb_url=getattr(item, "thumb_url", None),
                    seller_id=getattr(item, "seller_id", None),
                    source="auto",
                    region=getattr(item, "region", None),
                    publish_time=getattr(item, "publish_time", None),
                    want_cnt=getattr(item, "want_cnt", None),
                    view_cnt=getattr(item, "view_cnt", None),
                    is_sold=getattr(item, "is_sold", False),
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

        流程：
        1. 搜索
        2. 去重
        3. 拉详情 + 卖家主页
        4. 价格过滤
        5. 评估
        6. 落单（仅 AUTO 模式）
        7. 写入 task_links
        """
        stats = RunStats()
        evaluations: list[EvalResult] = []
        buy_results: list[BuyResult] = []
        # 显式初始化，避免 finally 块中 dir() 反模式检查变量是否存在
        new_items: list[ItemSummary] | None = None
        settings = get_settings()
        eval_cfg = get_config().eval

        try:
            # 1. 搜索（传递任务配置的筛选标签）
            logger.info(f"[Task {self.task.id}] 搜索「{self.task.keyword}」")
            # 加 60 秒超时保护 + 跳过 RGV587 重试：
            # RGV587 重试需要 75 秒且通常无效（需重新登录），跳过后 Worker 搜索最多 ~30 秒，
            # 避免长时间占用 browser_lock 阻塞 live 端点的实时搜索请求
            try:
                items = await asyncio.wait_for(
                    self.collector.search(
                        self.task.keyword,
                        search_filters=getattr(self.task, 'search_filters', None) or [],
                        skip_rgv587_retry=True,
                    ),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                # 搜索超时通常意味着浏览器卡住或网络异常，继续循环只会再次超时
                # 持续占用 browser_lock 阻塞 live 端点，因此暂停任务
                logger.warning(f"[Task {self.task.id}] 搜索超时（60秒），自动暂停任务")
                stats.finished_at = datetime.now(timezone.utc)
                return RunResult(stats=stats, should_pause=True)
            stats.found = len(items)
            logger.info(f"[Task {self.task.id}] 搜索到 {stats.found} 件")

            # RGV587 会话失效时通知 Scheduler 暂停任务
            # 避免无效搜索持续占用 browser_lock，阻塞 live 端点的实时搜索
            if getattr(self.collector, 'last_session_invalid', False):
                logger.warning(f"[Task {self.task.id}] 闲鱼会话失效（RGV587_ERROR），自动暂停任务，请重新登录闲鱼")
                stats.finished_at = datetime.now(timezone.utc)
                return RunResult(stats=stats, should_pause=True)

            # 2. 去重
            new_items = await self.dedup.filter_new(items)
            stats.deduped = stats.found - len(new_items)
            if not new_items:
                logger.info(f"[Task {self.task.id}] 全部已看过，本轮跳过")
                stats.finished_at = datetime.now(timezone.utc)
                return RunResult(stats=stats)

            # 限制每轮条数
            new_items = new_items[: self.config.max_items_per_run]

            # 立即写入 task_links（搜索完成后直接存储，不等详情爬取）
            # 这样用户可以在"闲鱼内容关联"面板立即看到搜索结果
            self._save_task_links(new_items)
            stats.linked = sum(
                1 for item in new_items
                if task_keyword_matches_title(self.task.keyword, getattr(item, "title", None))
            )

            market_ctx = self._compute_market_context(new_items)

            # 3. 串行拉取详情 + 卖家主页（复用单个页面，避免并发打开多个浏览器窗口）
            # 原实现用 Semaphore(3) + gather 并发，每个 detail/seller_profile 都 new_page，
            # 导致 scheduler 每轮触发时同时弹出 6 个窗口（3 详情 + 3 卖家主页）。
            # 改为串行复用单个详情页 + 单个卖家页，窗口数从 6 降到 2，且不会并发弹出。
            shared_detail_page = None
            shared_seller_page = None
            # collector.browser 可能为 None（测试环境），此时不创建复用页面
            _has_browser = getattr(self.collector, 'browser', None) is not None
            try:
                for summary in new_items:
                    if not summary.id:
                        continue
                    try:
                        # 复用详情页（首次创建，后续复用）
                        if _has_browser and shared_detail_page is None:
                            shared_detail_page = await self.collector.browser.new_page()
                        detail = await self.collector.detail(summary.id, page=shared_detail_page)
                        if not detail:
                            logger.warning("[Task %s] 详情页获取失败，跳过 %s", self.task.id, summary.id)
                            continue
                        # 复用卖家页（首次创建，后续复用）
                        # seller_profile 失败时使用降级策略（搜索页+详情页信息），而非空默认值
                        seller = None
                        if detail.seller_id:
                            if _has_browser and shared_seller_page is None:
                                shared_seller_page = await self.collector.browser.new_page()
                            seller = await self.collector.seller_profile(detail.seller_id, page=shared_seller_page)
                        if not seller:
                            logger.info("[Task %s] 卖家主页获取失败，使用降级策略评估 %s", self.task.id, summary.id)
                            # 降级策略：合并搜索结果+详情页的卖家信息构建基本画像
                            seller = await self.collector.seller_profile_fallback(summary=summary, detail=detail)
                    except Exception as e:
                        logger.warning("[Task %s] 采集异常 %s: %s", self.task.id, summary.id, e)
                        detail = None
                        # 异常时也尝试用搜索结果构建降级 SellerProfile（如果有 summary）
                        if not seller and hasattr(self, 'collector'):
                            seller = await self.collector.seller_profile_fallback(summary=summary, detail=detail)

                    if not detail or not seller:
                        continue

                    # 用详情页采集到的 seller_id 更新 task_links（搜索页卡片通常不含卖家信息）
                    # 详情页阶段也需关键词过滤：_save_task_links 已过滤过一轮，
                    # 但 new_items 中可能包含被 _save_task_links 跳过的 noise 商品，
                    # 此处再次过滤避免写入无关关联
                    if detail.seller_id and self.repo and task_keyword_matches_title(self.task.keyword, detail.title):
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
                            )
                        except Exception as e:
                            logger.warning(
                                "[Task %s] 更新卖家关联失败 %s: %s",
                                self.task.id, detail.id, e,
                            )

                    try:

                        # 4. 价格过滤
                        verdict = self.price.check(detail, market_ctx)
                        if not verdict.pass_:
                            stats.price_filtered += 1
                            continue

                        # 5. 评估
                        eval_result = self.evaluator.evaluate(detail, seller)
                        stats.evaluated += 1
                        evaluations.append(eval_result)

                        # 写入 events 表，供评估明细/事件中心展示
                        # 不写入则前端评估明细和事件中心页面永远无数据
                        if self.repo:
                            try:
                                import json as _json
                                score_display = eval_result.score if eval_result.score is not None else "N/A"
                                level = "info" if eval_result.is_passed else ("warn" if eval_result.risk_level != RiskLevel.EXTREME else "err")
                                if eval_result.risk_level == RiskLevel.UNKNOWN:
                                    level = "warn"  # 数据不足用 warn 级别，避免误报为错误
                                self.repo.save_event({
                                    "type": "eval.scored",
                                    "task_id": self.task.id,
                                    "item_id": detail.id,  # 顶层 item_id 供前端 dataIndex 直接读取
                                    "stage": "eval",
                                    "level": level,
                                    "message": f"商品 {detail.id} 评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
                                    "payload": _json.dumps({
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

                        if not eval_result.is_passed:
                            continue
                        stats.passed += 1

                        # 5.5 AI 自动评估（可选，消耗 token）
                        # 开启后对通过规则评估的商品自动调用 AI 二次确认
                        if _has_browser and settings.ai_enabled and eval_cfg.ai_auto_eval and settings.openai_api_key:
                            try:
                                from xianyu_hunter.web.routes.api_ai import _call_llm_vision, _rule_eval_condition
                                ai_result = await _call_llm_vision(
                                    detail.title, detail.description or "",
                                    detail.price or 0, detail.image_urls or [],
                                )
                                ai_verdict = ai_result.get("verdict", "")
                                if ai_verdict == "reject":
                                    logger.info("[Task %s] AI 评估拒绝 %s，跳过", self.task.id, detail.id)
                                    continue
                                # 将 AI 评估结果追加到 dimension_scores
                                if "detail" in ai_result:
                                    eval_result.dimension_scores["ai_condition"] = ai_result.get("condition_score", 0)
                                    eval_result.dimension_scores["ai_verdict"] = ai_verdict
                            except Exception as e:
                                logger.warning("[Task %s] AI 自动评估失败，继续规则评估: %s", self.task.id, e)

                        # 5.6 AI 深度分析（可选，消耗更多 token）
                        if _has_browser and settings.ai_enabled and eval_cfg.ai_auto_deep_analyze and settings.openai_api_key:
                            try:
                                from xianyu_hunter.web.routes.api_ai_deep import _call_llm_deep_analyze, _fallback_deep_analyze
                                deep_result = await _call_llm_deep_analyze(
                                    detail.title, detail.description or "",
                                    detail.price or 0, detail.image_urls or [],
                                )
                                overall = deep_result.get("overall", {})
                                if overall.get("verdict") == "reject":
                                    logger.info("[Task %s] AI 深度分析拒绝 %s，跳过", self.task.id, detail.id)
                                    continue
                            except Exception as e:
                                logger.warning("[Task %s] AI 深度分析失败，继续: %s", self.task.id, e)

                        # 6. 落单
                        if not self._should_buy():
                            continue
                        if self._in_cooldown():
                            logger.info(
                                f"[Task {self.task.id}] 冷却中，跳过 {detail.id}"
                            )
                            continue

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
                                break
                        else:
                            stats.failed += 1
                    except Exception as e:  # noqa: BLE001
                        logger.exception(f"[Task {self.task.id}] 处理 {summary.id} 出错: {e}")
                        continue
            finally:
                # 关闭复用的详情页和卖家页，避免页面泄漏
                for _p in (shared_detail_page, shared_seller_page):
                    if _p is not None:
                        try:
                            await _p.close()
                        except Exception:
                            pass

        finally:
            stats.finished_at = datetime.now(timezone.utc)
            # 确保商品持久化到 items 表（去重 + 关联查询依赖此数据）
            if new_items:
                try:
                    await self.dedup.save(new_items, task_id=self.task.id)
                except Exception as e:
                    logger.warning("[Task %s] 持久化 items 失败: %s", self.task.id, e)
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

        logger.info(
            f"[Task {self.task.id}] 本轮完成: 找到 {stats.found} / "
            f"去重 {stats.deduped} / 价格过滤 {stats.price_filtered} / "
            f"评估 {stats.evaluated} / 通过 {stats.passed} / "
            f"落单 {stats.bought} / 失败 {stats.failed} / 关联 {stats.linked}"
        )
        return RunResult(stats=stats, evaluations=evaluations, buy_results=buy_results)

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
