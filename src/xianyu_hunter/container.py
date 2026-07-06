"""组合根 (Composition Root)

负责把配置 / Repository / Browser / EventBus / Evaluator / Buyer / Scheduler 全部串起来。
测试时可注入 fakes 替换任一依赖。

架构定位：
    本文件位于项目根包 (xianyu_hunter.container)，与 infra / modules / web 平级。
    作为 Composition Root，它合法地依赖所有层，不存在反向依赖问题。
    （原位置在 infra/ 下已迁移，修复 C-01 反向依赖违例）
"""
from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xianyu_hunter.domain.events import EventType
from xianyu_hunter.domain.task import Task, TaskConfig, TaskMode
from xianyu_hunter.infra.event_bus import EventBus
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.infra.yaml_config import AppConfig, get_config
from xianyu_hunter.modules.anti_detect import AntiDetect, AntiDetectConfig
from xianyu_hunter.modules.buyer import Buyer
from xianyu_hunter.modules.buyer_config import BuyerConfig
from xianyu_hunter.modules.collector import Collector
from xianyu_hunter.modules.dedup import ItemDedup
from xianyu_hunter.modules.evaluator import Evaluator
from xianyu_hunter.modules.notifier import NotifierHub
from xianyu_hunter.modules.price_strategy import PriceConfig, PriceStrategy
from xianyu_hunter.modules.scheduler import TaskScheduler
from xianyu_hunter.modules.worker import TaskWorker

logger = get_logger()


def _parse_json_field(raw: Any, field_name: str) -> dict | None:
    """安全解析 DB 中的 JSON 配置覆盖字段

    返回 None 表示无覆盖（沿用全局），dict 表示有效覆盖
    """
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw or None
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if parsed else None
        except json.JSONDecodeError:
            logger.warning(f"任务 {field_name} JSON 解析失败，将沿用全局配置: {raw[:80]}")
            return None
    return None


# 仅用于时间线/DB 持久化的事件类型集合，不通过 NotifierHub 推送
# 为什么定义为模块级常量：避免 wire_notifier 内联大集合推高认知复杂度，
# 同时便于在测试中通过模块级 patch 替换
_DB_ONLY_EVENTS: frozenset[str] = frozenset({
    "TASK_STOPPED",
    "TASK_SEARCH_DONE",
    "ITEM_FOUND",
    "EVAL_SCORED",
    "WAF_BLOCKED",
    "AUTH_EXPIRED",
    "SYSTEM_ERROR",
    "MAINTENANCE_DATABASE",
    "MAINTENANCE_LOGS",
    "MAINTENANCE_CACHE",
})


def _build_yaml_credentials(cfg: Any) -> dict[str, dict[str, str]]:
    """从 AppConfig 顶层字段构建 yaml_credentials 字典

    为什么提取为模块级函数：原 wire_notifier 内联 7 个 if cfg.xxx 分支
    构建各渠道凭据字典，单一方法认知复杂度堆积。提取后 wire_notifier 仅保留
    编排逻辑，凭据构建职责分离。
    yaml_credentials 作为 keyring 的 fallback：用户在前端保存凭据时只写入 yaml，
    但 notifier __init__ 优先从 keyring 读取，需用 yaml 明文兜底避免数据流断裂。
    """
    yaml_credentials: dict[str, dict[str, str]] = {}
    if cfg.serverchan_send_key:
        yaml_credentials["serverchan"] = {"send_key": cfg.serverchan_send_key}
    if cfg.pushplus_token:
        yaml_credentials["pushplus"] = {"token": cfg.pushplus_token}
    if cfg.bark_key:
        yaml_credentials["bark"] = {
            "server": cfg.bark_server or "",
            "key": cfg.bark_key,
        }
    if cfg.telegram_bot_token:
        yaml_credentials["telegram"] = {
            "bot_token": cfg.telegram_bot_token,
            "chat_id": cfg.telegram_chat_id or "",
        }
    if cfg.wecom_webhook:
        yaml_credentials["wecom"] = {"webhook_url": cfg.wecom_webhook}
    if cfg.dingtalk_webhook:
        yaml_credentials["dingtalk"] = {
            "webhook_url": cfg.dingtalk_webhook,
            "secret": cfg.dingtalk_secret or "",
        }
    if cfg.webhook_url:
        yaml_credentials["webhook"] = {"webhook_url": cfg.webhook_url}
    return yaml_credentials


def _resolve_subscribed_events(config_events: list[str] | None) -> set[EventType]:
    """解析用户配置的订阅事件名列表为 EventType 集合

    为什么提取为模块级函数：原 wire_notifier 内联 for + if name in db_only_events
    + if evt is not None + else warning 的嵌套链，提取后 wire_notifier 复杂度显著降低。
    仅匹配已知 EventType，跳过未知事件名（如 chatbot.* 不通过 NotifierHub 推送）。
    """
    subscribed_events: set[EventType] = set()
    for name in config_events or []:
        if name in _DB_ONLY_EVENTS:
            logger.info(
                f"[wire_notifier] 配置中的 subscribed_events 包含仅用于时间线的事件类型 {name!r}，"
                f"通知总线已跳过"
            )
            continue
        evt = getattr(EventType, name, None)
        if evt is not None:
            subscribed_events.add(evt)
        else:
            logger.warning(
                f"[wire_notifier] 忽略未知事件类型 {name!r}（不在 EventType 枚举中），"
                f"请检查 config.yaml 的 notifier.subscribed_events 配置"
            )
    return subscribed_events


class PriorityBrowserLock:
    """优先级浏览器锁

    high 优先级（live 端点）请求优先获取锁。
    low 优先级（Worker）请求通过 has_high_priority_waiting 属性
    检查是否有 live 请求在等待，从而主动延迟下一轮搜索。

    设计权衡：不改变 asyncio.Lock 的 FIFO 语义（避免复杂竞态），
    而是通过 _high_waiting 计数器让 Worker 在搜索完成后主动让出，
    减少 live 端点的锁竞争等待时间（从 5-10s 降至 1-3s）。
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._high_waiting = 0

    @property
    def has_high_priority_waiting(self) -> bool:
        """是否有高优先级请求在等待（Worker 可据此延迟搜索）"""
        return self._high_waiting > 0

    async def acquire(self, priority: str = "low") -> None:
        if priority == "high":
            self._high_waiting += 1
            try:
                await self._lock.acquire()
            finally:
                self._high_waiting -= 1
        else:
            await self._lock.acquire()

    def release(self) -> None:
        self._lock.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        self.release()


@dataclass
class Container:
    """DI 容器：持有全部单例依赖

    设计原则：
    1. 所有重对象（Browser / Repository / Scheduler）只构造一次
    2. 每 Task 共享全局依赖（Evaluator / Buyer / Collector）
    3. 支持测试 override（任何字段可被替换为 fake）
    """
    config: AppConfig
    repo: Repository
    event_bus: EventBus
    # 可选依赖（生产模式必填；测试模式可注入 fake）
    browser: Any = None
    antidetect: AntiDetect = None  # type: ignore[assignment]
    collector: Collector = None  # type: ignore[assignment]
    dedup: ItemDedup = None  # type: ignore[assignment]
    price_strategy: PriceStrategy = None  # type: ignore[assignment]
    evaluator: Evaluator = None  # type: ignore[assignment]
    buyer: Buyer = None  # type: ignore[assignment]
    notifier_hub: NotifierHub = field(default_factory=NotifierHub)
    scheduler: TaskScheduler = field(default_factory=TaskScheduler)
    # 浏览器操作互斥锁：防止 Worker 和 live 端点并发使用同一浏览器实例
    # 并发使用会导致 TargetClosedError / Connection closed 等错误
    # 使用 PriorityBrowserLock 支持 live 端点高优先级获取锁
    browser_lock: PriorityBrowserLock = field(default_factory=PriorityBrowserLock)
    # 智能客服子容器：由 _build_chatbot_container 在主容器就绪后注入
    # 用 Any 而非具体类型：避免顶层 container.py 强依赖 chatbot 模块，
    # chromadb 等可选依赖未安装时仍可正常构造（chatbot=None）
    chatbot: Any = None

    def wire_notifier(self) -> None:
        """把 NotifierHub 接入 EventBus（构造后只调一次）"""
        # 选取已配置为启用的渠道
        # 通过 model_dump() 自动收集所有为 True 的渠道字段，避免新增渠道时遗漏
        # 旧版只判断 serverchan/pushplus/bark 导致 dingtalk 等渠道即使开启也不会被加入
        ch_cfg = self.config.notifier.channels
        enabled: list[str] = [name for name, on in ch_cfg.model_dump().items() if on]
        warn_unconfigured = bool(enabled)
        if not enabled:
            enabled = list(self.config.notifier.default_channels)
            if not enabled:
                logger.warning(
                    "[wire_notifier] 未配置任何通知渠道且 default_channels 为空，"
                    "所有通知将被丢弃。请在 config.yaml 的 notifier.channels 中启用至少一个渠道"
                )
        # 从 yaml 明文读取凭据，作为 keyring 的 fallback
        # 为什么需要 yaml fallback：用户在前端保存凭据时只写入 yaml，
        # 但 notifier __init__ 优先从 keyring 读取；当 keyring 中没有时，
        # 用 yaml 明文兜底，避免"配置已保存但通知不发送"的数据流断裂
        yaml_credentials = _build_yaml_credentials(self.config)
        # 重新构造 hub 以应用 enabled
        # P3-F-10：注入 quiet_hours；send() 时自动判定静默
        self.notifier_hub = NotifierHub(
            channels=enabled,
            quiet_hours=self.config.notifier.quiet_hours,
            repo=self.repo,
            warn_unconfigured=warn_unconfigured,
            yaml_credentials=yaml_credentials,
        )
        # 从用户配置解析订阅事件集合
        # 仅匹配已知 EventType，跳过未知事件名（如 chatbot.* 不通过 NotifierHub 推送）
        subscribed_events = _resolve_subscribed_events(
            self.config.notifier.subscribed_events,
        )
        # 用户配置为空时传 None，让 hub.attach() 回退到 DEFAULT_NOTIFY_EVENTS
        # 避免 None vs 空 set 语义差异导致 NotifierHub 不订阅任何事件
        self.notifier_hub.attach(
            self.event_bus,
            events=subscribed_events or None,
        )

    def build_task_price_strategy(self, raw: dict) -> PriceStrategy:
        """从 DB raw task dict 构造任务级 PriceStrategy

        合并规则（与 build_worker_from_raw_task 内的逻辑保持一致）：
        - task.min_price/max_price 列优先
        - 为 None 时从 task.price_config JSON 中取
        - 都为 None 时沿用全局 self.price_strategy

        为什么提取为公共方法：recompute / batch_evaluate / collection_service
        三条评估写入路径都需要用任务级 PriceStrategy 做价格门禁，
        避免在四处复制合并逻辑导致行为漂移。
        """
        task_price_override = _parse_json_field(raw.get("price_config"), "price_config")
        effective_min = raw.get("min_price")
        effective_max = raw.get("max_price")
        if task_price_override:
            if effective_min is None and "min_price" in task_price_override:
                effective_min = task_price_override["min_price"]
            if effective_max is None and "max_price" in task_price_override:
                effective_max = task_price_override["max_price"]
        if effective_min is not None or effective_max is not None:
            price_cfg = self.config.price_strategy
            return type(self.price_strategy)(
                PriceConfig(
                    min_price=effective_min,
                    max_price=effective_max,
                    market_ratio=task_price_override.get("market_ratio", price_cfg.market_ratio)
                    if task_price_override else price_cfg.market_ratio,
                )
            )
        return self.price_strategy

    def build_worker_from_raw_task(self, raw: dict) -> TaskWorker | None:
        """从 DB 的 raw task dict 构造 TaskWorker

        统一 CLI (__main__.py) 和 Web (startup.py) 的 Worker 构造逻辑，
        避免两处代码不一致导致行为差异。支持任务级 search_config / price_config /
        eval_config 覆盖，None 字段沿用全局配置。

        Args:
            raw: repo.list_tasks() 返回的 dict

        Returns:
            TaskWorker 实例，若 raw 状态非 running 返回 None
        """
        if raw.get("status") != "running":
            return None

        # 解析任务级配置覆盖（JSON 字符串 → dict，None 表示沿用全局）
        task_search_override = _parse_json_field(raw.get("search_config"), "search_config")
        task_price_override = _parse_json_field(raw.get("price_config"), "price_config")
        task_eval_override = _parse_json_field(raw.get("eval_config"), "eval_config")

        task = Task(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            keyword=raw["keyword"],
            min_price=raw.get("min_price"),
            max_price=raw.get("max_price"),
            exclude_words=raw.get("exclude_words") or [],
            region=raw.get("region"),
            mode=TaskMode(raw.get("mode", "confirm")),
            search_filters=raw.get("search_filters") or [],
            # 用 or 防御 NULL：迁移后的旧行可能为 None
            cron=raw.get("cron") or "*/1 * * * *",
            use_cron=bool(raw.get("use_cron") or 0),
            interval_seconds=float(raw.get("interval_seconds") or 60.0),
            eval_threshold=raw.get("eval_threshold"),
            ai_prompt=raw.get("ai_prompt"),
            search_config=task_search_override,
            price_config=task_price_override,
            eval_config=task_eval_override,
        )

        # 复用公共方法构造任务级价格策略，避免逻辑重复
        worker_price_strategy = self.build_task_price_strategy(raw)

        # 合并任务级搜索参数覆盖
        search_cfg = self.config.search
        effective_search = {
            "page_size": search_cfg.page_size,
            "sort_type": search_cfg.sort_type,
            "timeout": search_cfg.timeout,
            "regions": search_cfg.regions,
            "filter_tags": search_cfg.filter_tags,
        }
        if task_search_override:
            for k in effective_search:
                if k in task_search_override:
                    effective_search[k] = task_search_override[k]
        task_config = TaskConfig(
            search_page_size=effective_search["page_size"],
            search_sort_type=effective_search["sort_type"],
            search_timeout=effective_search["timeout"],
            search_regions=effective_search["regions"],
            search_filter_tags=effective_search["filter_tags"],
            use_cron=task.use_cron,
            interval_seconds=task.interval_seconds,
        )

        # P1: 注入官方采集回调，延迟导入避免循环依赖（startup → app → container）
        # partial 绑定 container：worker 调用 fn(item_id, task_id) 时实际执行
        # _call_official_collect(self, item_id, task_id)
        try:
            from functools import partial
            from xianyu_hunter.web.startup import _call_official_collect
            official_collect_fn = partial(_call_official_collect, self)
        except ImportError:
            official_collect_fn = None

        return TaskWorker(
            task=task,
            collector=self.collector,
            dedup=self.dedup,
            price_strategy=worker_price_strategy,
            evaluator=self.evaluator,
            buyer=self.buyer,
            config=task_config,
            repo=self.repo,
            event_bus=self.event_bus,
            official_collect_fn=official_collect_fn,
        )


def build_default_container(
    config: AppConfig | None = None,
    db_path: str | Path = "data/xianyu.db",
    with_browser: bool = True,
) -> Container:
    """构造生产模式容器

    - 加载 YAML 配置
    - 初始化 SQLite + Repository
    - 启动 Browser + 注入 stealth（仅 when with_browser=True）
    - 构造 Collector / Evaluator / Buyer / NotifierHub / Scheduler

    Args:
        with_browser: Web 进程传入 False 以跳过浏览器启动（节省 ~100-200MB 内存）
    """
    cfg = config or get_config()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    repo = Repository(db_path=str(db_path))
    bus = EventBus()

    # H-02 修复：Web 进程不需要浏览器，跳过 BrowserManager/AntiDetect/Collector/Buyer
    browser = None
    antidetect = None
    collector = None
    buyer = None
    # 浏览器互斥锁：Worker 搜索与 live 端点共享，防止并发操作浏览器
    _browser_lock = PriorityBrowserLock()

    if with_browser:
        from xianyu_hunter.infra.browser import BrowserManager

        browser = BrowserManager(
            user_data_dir=cfg.browser.user_data_dir,
            headless=cfg.browser.headless,
            user_agent=cfg.browser.user_agent,
            # CDP 模式禁用：CDP 模式下每次 new_page() 都会弹出可见 Edge 窗口，
            # 即使页面被正确关闭，窗口也会短暂出现，导致任务执行时不停弹窗。
            # headless launch 模式更适合后台任务执行场景。
            use_cdp=False,
            proxy_server=cfg.browser.proxy_server,
        )

        antidetect = AntiDetect(AntiDetectConfig(
            qps=cfg.antidetect.qps,
            min_delay_ms=cfg.antidetect.min_delay_ms,
            max_delay_ms=cfg.antidetect.max_delay_ms,
            fail_pause_threshold=cfg.antidetect.fail_pause_threshold,
            fail_window_sec=cfg.antidetect.fail_window_sec,
        ))

        collector = Collector(browser=browser, antidetect=antidetect, browser_lock=_browser_lock)
        buyer = Buyer(browser=browser, repository=repo, event_bus=bus, config=BuyerConfig())

    dedup = ItemDedup(repo=repo)
    price = PriceStrategy(PriceConfig(
        min_price=None,
        max_price=None,
        market_ratio=0.8,
        top_n=None,
    ))
    # Evaluator 不接收 thresholds/weights/keywords 覆盖参数：
    # 为什么：Evaluator.__init__ 会把传入的参数存为 _override_*，
    # 一旦不为 None，_get_thresholds() 等方法就永远返回覆盖值，
    # 不再从 get_config() 实时读取。这会导致：
    # 1. 用户在配置页面修改 pass_score/auto_buy_score 后不生效
    # 2. evaluator._score_to_risk() 用固定阈值划分 risk_level，
    #    而 worker.should_auto_buy() 用实时配置值，两者不一致
    # 3. 评分达标的商品因 risk_level != LOW 被错误跳过抢单
    # 正确做法：让 Evaluator 每次 evaluate() 时从 get_config() 实时读取
    evaluator = Evaluator()

    container = Container(
        config=cfg,
        repo=repo,
        event_bus=bus,
        browser=browser,
        antidetect=antidetect,
        collector=collector,
        dedup=dedup,
        price_strategy=price,
        evaluator=evaluator,
        buyer=buyer,
        browser_lock=_browser_lock,
    )
    container.wire_notifier()
    # F-16：给 Scheduler 注入 repo，使其能触发依赖任务
    container.scheduler.set_repo(repo)
    # 智能客服子容器构造（在主容器就绪后，复用 repo.engine 和 event_bus）
    # 为什么放在末尾：chatbot 模块依赖 repo/engine/event_bus 等主容器资源，
    # 必须等主容器完全构造后才能注入；可选依赖缺失时返回 None 不影响主系统
    container.chatbot = _build_chatbot_container(container)
    logger.info("Container 初始化完成")
    return container


def _build_chatbot_container(container: Container) -> Any:
    """构造智能客服子容器

    独立函数而非内联在 build_default_container 中：
    1. 隔离可选依赖：chromadb/sentence-transformers 未安装时返回 None，不影响主容器
    2. 便于测试：测试时可单独 mock chatbot 子容器
    3. 关注点分离：主容器构造逻辑不被 chatbot 逻辑污染

    返回 dict 而非 dataclass：chatbot 子容器字段多且可能扩展，
    dict 更灵活；访问方式 container.chatbot["orchestrator"] 直观清晰
    """
    # 深拷贝 chatbot 配置：避免 settings.openai_model 覆盖污染 get_config() 全局单例
    # 若直接修改单例，用户清空 OPENAI_MODEL 后 cfg.llm.model 会保留上次污染值无法重置
    cfg = copy.deepcopy(container.config.chatbot)
    if not cfg.enabled:
        logger.info("智能客服未启用（chatbot.enabled=false）")
        return None

    # 同步 settings.openai_model 到 cfg.llm.model（修改的是副本，不影响全局单例）
    # 原因：用户在 .env 中配置 OPENAI_MODEL 时，只需改一处即可同时影响 LLM 和 chatbot
    from xianyu_hunter.config import get_settings as _get_settings
    _settings = _get_settings()
    if _settings.openai_model:
        cfg.llm.model = _settings.openai_model
        logger.info(f"chatbot LLM model 同步为 settings.openai_model: {_settings.openai_model}")

    try:
        from xianyu_hunter.infra import ai_usage
        from xianyu_hunter.infra.repo_chatbot import ChatbotRepository
        from xianyu_hunter.modules.chatbot.embedding_service import EmbeddingService
        from xianyu_hunter.modules.chatbot.vector_store import VectorStore
        from xianyu_hunter.modules.chatbot.kb_manager import KBManager
        from xianyu_hunter.modules.chatbot.faq_matcher import FAQMatcher
        from xianyu_hunter.modules.chatbot.intent_classifier import IntentClassifier
        from xianyu_hunter.modules.chatbot.rag_engine import RAGEngine
        from xianyu_hunter.modules.chatbot.context_manager import ContextManager
        from xianyu_hunter.modules.chatbot.escalation import Escalation
        from xianyu_hunter.modules.chatbot.tool_registry import ToolRegistry
        from xianyu_hunter.modules.chatbot.agent import Agent
        from xianyu_hunter.modules.chatbot.orchestrator import ChatbotOrchestrator
        from xianyu_hunter.modules.chatbot.kb_refresh_scheduler import KBRefreshScheduler
    except ImportError as e:
        logger.warning(f"智能客服模块依赖缺失，跳过初始化: {e}")
        return None

    try:
        # 1. 仓储层：复用主 repo.engine（避免独立 create_engine 导致 SQLite locked）
        chatbot_repo = ChatbotRepository(container.repo.engine)

        # 2. 基础设施层
        # settings.embedding_* 覆盖 cfg.kb.embedding_*：
        # embedding endpoint 已独立于 LLM（DeepSeek 不支持 /embeddings），
        # 通过 .env 的 EMBEDDING_MODEL/DIMENSIONS 切换后端时，
        # 必须同步覆盖 model 和 dimensions，否则会用错模型名/错误维度
        _emb_model = _settings.embedding_model or cfg.kb.embedding_model
        _emb_dimensions = (
            _settings.embedding_dimensions
            if _settings.embedding_dimensions > 0
            else cfg.kb.embedding_dimensions
        )
        embedding_service = EmbeddingService(
            ai_usage=ai_usage,
            model=_emb_model,
            dimensions=_emb_dimensions,
            concurrency=cfg.kb.embedding_concurrency,
        )
        vector_store = VectorStore(
            persist_path=cfg.kb.persist_path,
            collection_name=cfg.kb.collection_name,
        )

        # 3. 知识库管理器
        kb_manager = KBManager(
            embedding_service=embedding_service,
            vector_store=vector_store,
            repo=chatbot_repo,
            config=cfg.kb,
            project_root=cfg.kb.project_root,
        )

        # 4. 匹配器群
        faq_matcher = FAQMatcher(
            repo=chatbot_repo,
            embedding_service=embedding_service,
            config=cfg.faq,
        )
        intent_classifier = IntentClassifier(
            config=cfg,
            ai_usage=ai_usage,
        )
        rag_engine = RAGEngine(
            embedding_service=embedding_service,
            vector_store=vector_store,
            config=cfg.rag,
            llm_config=cfg.llm,
            ai_usage=ai_usage,
        )

        # 5. 上下文 + 转人工
        context_manager = ContextManager(
            repo=chatbot_repo,
            config=cfg,
        )
        escalation = Escalation(
            repo=chatbot_repo,
            config=cfg.escalation,
            session_timeout_min=cfg.session_timeout_min,
        )

        # 6. Agent + 工具注册表
        tool_registry = ToolRegistry(
            repo=container.repo,
            rag_engine=rag_engine,
            config=cfg.agent,
        )
        agent = Agent(
            tool_registry=tool_registry,
            config=cfg.agent,
            llm_config=cfg.llm,
            ai_usage=ai_usage,
        )

        # 7. 编排器（串联所有模块）
        orchestrator = ChatbotOrchestrator(
            faq_matcher=faq_matcher,
            intent_classifier=intent_classifier,
            rag_engine=rag_engine,
            agent=agent,
            context_manager=context_manager,
            escalation=escalation,
            chatbot_repo=chatbot_repo,
            config=cfg,
            event_bus=container.event_bus,
        )

        # 8. 知识库刷新调度器（不在构造时启动，由 startup.py 在应用启动后启动）
        kb_scheduler = KBRefreshScheduler(
            kb_manager=kb_manager,
            config=cfg.kb,
            event_bus=container.event_bus,
        )

        logger.info("智能客服子容器初始化完成")
        return {
            "repo": chatbot_repo,
            "embedding_service": embedding_service,
            "vector_store": vector_store,
            "kb_manager": kb_manager,
            "faq_matcher": faq_matcher,
            "intent_classifier": intent_classifier,
            "rag_engine": rag_engine,
            "context_manager": context_manager,
            "escalation": escalation,
            "tool_registry": tool_registry,
            "agent": agent,
            "orchestrator": orchestrator,
            "kb_scheduler": kb_scheduler,
            "config": cfg,
        }
    except Exception as e:
        # ImportError：可选依赖（chromadb/sentence-transformers）缺失是合法状态，降级为 info
        # 避免可选依赖缺失被误判为启动失败（logger.exception 会输出 ERROR 级别+堆栈）
        if isinstance(e, ImportError):
            logger.info(f"智能客服可选依赖缺失，跳过初始化: {e}")
        else:
            # chromadb 初始化失败、VectorStore 集合打开失败等异常不阻断主系统
            logger.exception("智能客服子容器初始化失败")
        return None
