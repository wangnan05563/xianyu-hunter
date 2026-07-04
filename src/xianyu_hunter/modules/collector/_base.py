"""Collector 基类：共享状态字段与初始化

将 Collector 的状态字段集中在此处，便于各 Mixin 通过 self 访问。
拆分目的：降低单文件复杂度，状态定义与业务方法分离便于维护。
"""
from __future__ import annotations

import asyncio
import time

from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.infra.browser import BrowserManager
from xianyu_hunter.infra.lru import LRUDict
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
        # LRUDict 防止长跑进程累积过多卖家昵称，未命中时回退到 ItemSummary 字段
        self._seller_nicks: LRUDict[str, str] = LRUDict(maxsize=2000)
        # 卖家画像降级缓存：seller_id -> SellerProfile
        # 避免同一卖家的多个商品重复计算降级结果（提升性能）
        # LRU 驱逐后会重新执行 seller_profile_fallback，性能损失但无正确性问题
        self._seller_profile_cache: LRUDict[str, SellerProfile] = LRUDict(maxsize=2000)
        # _m_h5_tk 上次刷新时间戳（monotonic），避免每次搜索都刷新
        # token TTL=1h，45 分钟刷新一次留 15 分钟安全余量
        self._last_m5tk_refresh: float = 0.0
        # 上次搜索是否会话失效（RGV587_ERROR）
        # Worker 检测到此标志后自动暂停，避免无效搜索持续占用 browser_lock
        self.last_session_invalid: bool = False
        # 上次搜索是否捕获到 API 响应但解析为 0 个商品（可能是登录墙/会话过期）
        # 供 live_links 端点判断是否需要提示用户重新登录
        self._last_api_captured: bool = False
        # 上次 detail() 返回 None 的具体原因（枚举字符串）
        # 为什么需要：collection_service 抛错时根据 reason 区分 401/429/502/503，
        # 避免所有失败都归为 502 让用户无法判断是该重试、该重登录还是该等待
        # 取值：page_closed/http_status_error/home_title_redirect/login_redirect/
        #       verify_redirect/title_extraction_failed/price_extraction_failed/
        #       redirected_away_from_item/target_closed_exception/unknown_exception
        self.last_detail_failure_reason: str = ""

    # ============== _m_h5_tk 刷新时间戳的公共访问接口 ==============
    # 为什么需要封装：_last_m5tk_refresh 是私有属性，但 web 路由层
    # （api_task_links.py）需要读写它来协调"补注入身份 Cookie 后强制刷新 token"。
    # 直接读写私有属性破坏封装性，且若内部重命名会静默失效。封装为公共方法
    # 让 web 层只依赖稳定的接口而非实现细节。

    def force_refresh_m5tk_next(self) -> None:
        """标记下次搜索强制刷新 _m_h5_tk token

        通过将 _last_m5tk_refresh 置为 0.0，使 _ensure_fresh_m5tk 的
        elapsed 判断（time.monotonic() - 0.0 = 巨大值 > 2700s）必然触发刷新。
        """
        self._last_m5tk_refresh = 0.0

    def should_reset_m5tk(self, threshold: float = 300.0) -> bool:
        """判断是否需要重置 token 刷新时间戳

        Args:
            threshold: 距上次刷新超过此秒数则返回 True（默认 5 分钟）

        为什么默认 5 分钟：覆盖 Worker 浏览器启动时的匿名 token 场景
        （启动后 5 分钟内首次实时搜索会触发刷新），同时避免短时间连续
        实时搜索反复刷新（每次约 4s 主页导航）。
        """
        return (time.monotonic() - self._last_m5tk_refresh) > threshold
