"""Collector 基类：共享状态字段与初始化

将 Collector 的状态字段集中在此处，便于各 Mixin 通过 self 访问。
拆分目的：降低单文件复杂度，状态定义与业务方法分离便于维护。
"""
from __future__ import annotations

import asyncio

from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.infra.browser import BrowserManager
from xianyu_hunter.infra.selectors import SelectorRepo
from xianyu_hunter.modules.anti_detect import AntiDetect


class CollectorBase:
    """Collector 共享状态基类

    所有 Mixin 通过继承此类获得 self.browser / self.ad / self.selectors 等状态。
    不包含业务方法，仅负责状态初始化。
    """

    def __init__(
        self,
        browser: BrowserManager,
        antidetect: AntiDetect,
        selectors: type[SelectorRepo] = SelectorRepo,
        browser_lock: asyncio.Lock | None = None,
    ):
        self.browser = browser
        self.ad = antidetect
        self.selectors = selectors
        # 浏览器互斥锁：防止 Worker 搜索与 live 端点并发操作浏览器
        # 由 container 注入，Worker 和 live 端点共享同一把锁
        self._browser_lock = browser_lock
        # 卖家昵称缓存：seller_id -> nick
        # 搜索 API 响应中可能包含昵称，但 ItemSummary 领域模型不存储此字段，
        # 这里暂存供 live_search 组装 seller 数据时使用
        self._seller_nicks: dict[str, str] = {}
        # 卖家画像降级缓存：seller_id -> SellerProfile
        # 避免同一卖家的多个商品重复计算降级结果（提升性能）
        self._seller_profile_cache: dict[str, SellerProfile] = {}
        # _m_h5_tk 上次刷新时间戳（monotonic），避免每次搜索都刷新
        # token TTL=1h，45 分钟刷新一次留 15 分钟安全余量
        self._last_m5tk_refresh: float = 0.0
        # 上次搜索是否会话失效（RGV587_ERROR）
        # Worker 检测到此标志后自动暂停，避免无效搜索持续占用 browser_lock
        self.last_session_invalid: bool = False
        # 上次搜索是否捕获到 API 响应但解析为 0 个商品（可能是登录墙/会话过期）
        # 供 live_links 端点判断是否需要提示用户重新登录
        self._last_api_captured: bool = False
