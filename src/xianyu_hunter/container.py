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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xianyu_hunter.domain.events import EventType
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

logger = get_logger()


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
        ch_cfg = self.config.notifier.channels
        enabled: list[str] = []
        if ch_cfg.serverchan:
            enabled.append("serverchan")
        if ch_cfg.pushplus:
            enabled.append("pushplus")
        if ch_cfg.bark:
            enabled.append("bark")
        if not enabled:
            enabled = list(self.config.notifier.default_channels)
        # 重新构造 hub 以应用 enabled
        # P3-F-10：注入 quiet_hours；send() 时自动判定静默
        self.notifier_hub = NotifierHub(
            channels=enabled,
            quiet_hours=self.config.notifier.quiet_hours,
            repo=self.repo,
        )
        # 从用户配置解析订阅事件集合
        # 仅匹配已知 EventType，跳过未知事件名（如 chatbot.* 不通过 NotifierHub 推送）
        db_only_events = {
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
        }
        subscribed_events: set[EventType] = set()
        for name in self.config.notifier.subscribed_events or []:
            if name in db_only_events:
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
        # 用户配置为空时传 None，让 hub.attach() 回退到 DEFAULT_NOTIFY_EVENTS
        # 避免 None vs 空 set 语义差异导致 NotifierHub 不订阅任何事件
        self.notifier_hub.attach(
            self.event_bus,
            events=subscribed_events or None,
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
            logger.exception(f"智能客服子容器初始化失败: {e}")
        return None
