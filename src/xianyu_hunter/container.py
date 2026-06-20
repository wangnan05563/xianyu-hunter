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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xianyu_hunter.infra.event_bus import EventBus
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.infra.yaml_config import AppConfig, get_config
from xianyu_hunter.modules.anti_detect import AntiDetect, AntiDetectConfig
from xianyu_hunter.modules.buyer import Buyer
from xianyu_hunter.modules.buyer_config import BuyerConfig
from xianyu_hunter.modules.collector import Collector
from xianyu_hunter.modules.dedup import ItemDedup
from xianyu_hunter.modules.evaluator import Evaluator, EvaluationThresholds
from xianyu_hunter.modules.notifier import NotifierHub
from xianyu_hunter.modules.price_strategy import PriceConfig, PriceStrategy
from xianyu_hunter.modules.scheduler import TaskScheduler

logger = get_logger()


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
    browser_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

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
        )
        self.notifier_hub.attach(self.event_bus)


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
    _browser_lock = asyncio.Lock()

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
    thresholds = EvaluationThresholds(
        on_sale_count=cfg.eval.thresholds.on_sale_count,
        post_count_30d=cfg.eval.thresholds.post_count_30d,
        top_category_ratio=cfg.eval.thresholds.top_category_ratio,
        credit_score_min=cfg.eval.thresholds.credit_score_min,
        bad_review_max=cfg.eval.thresholds.bad_review_max,
        register_days_min=cfg.eval.thresholds.register_days_min,
    )
    evaluator = Evaluator(
        thresholds=thresholds,
        weights={
            "professional": cfg.eval.weights.professional,
            "credit": cfg.eval.weights.credit,
            "dispute": cfg.eval.weights.dispute,
            "price": cfg.eval.weights.price,
        },
        professional_keywords=cfg.eval.professional_keywords,
    )

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
    logger.info("Container 初始化完成")
    return container
