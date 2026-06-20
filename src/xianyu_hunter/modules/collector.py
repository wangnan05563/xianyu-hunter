"""闲鱼数据采集器

设计文档 §3.4 - 三个核心方法：
- search(keyword): 搜索 + 滚动加载
- detail(item_id): 商品详情
- seller_profile(seller_id): 卖家主页

依赖：BrowserManager（提供 page）+ AntiDetect（限流/反检测）+ Repository（去重）
"""
from __future__ import annotations

import asyncio
import random
import re
import time
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from xianyu_hunter.domain.item import ItemDetail, ItemSummary
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.domain.task import XIANYU_FILTER_MAP
from xianyu_hunter.domain.urls import build_item_url, build_search_url, build_seller_url, get_base_url
from xianyu_hunter.infra.browser import BrowserManager
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.repo_links import task_keyword_matches_title
from xianyu_hunter.infra.selectors import SelectorRepo
from xianyu_hunter.modules.anti_detect import AntiDetect
from xianyu_hunter.modules.collector_utils import (
    check_item_sold,
    extract_item_id,
    extract_seller_nick,
    parse_price_from_text,
    parse_search_api_result,
)

logger = get_logger()


class Collector:
    """闲鱼数据采集器

    所有方法接收可选 page 参数用于测试注入（默认从 BrowserManager 获取）。
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

    # ============== 搜索 ==============

    async def _ensure_fresh_m5tk(self, page: Page, force: bool = False) -> bool:
        """导航到闲鱼主页刷新 _m_h5_tk token

        _m_h5_tk 有 1 小时 TTL，过期后搜索 API 返回 RGV587_ERROR。
        访问 goofish.com 主页可触发服务端 Set-Cookie 续期。
        带 45 分钟缓存避免频繁刷新（force=True 时跳过缓存）。

        Returns:
            True 表示执行了刷新，False 表示跳过（缓存未过期）
        """
        if not force:
            elapsed = time.monotonic() - self._last_m5tk_refresh
            if elapsed < 2700:  # 45 分钟
                return False
        try:
            logger.debug("刷新 _m_h5_tk token: 导航到 goofish.com 主页")
            await page.goto(f"{get_base_url()}/", wait_until="domcontentloaded", timeout=15000)
            # 等待 Set-Cookie 响应被浏览器处理
            await asyncio.sleep(1.5)
            self._last_m5tk_refresh = time.monotonic()
            logger.info("_m_h5_tk token 已刷新")
            return True
        except Exception as e:
            logger.warning("刷新 _m_h5_tk token 失败: %s", e)
            return False

    async def search(
        self,
        keyword: str,
        max_pages: int = 3,
        page: Page | None = None,
        search_filters: list[str] | None = None,
        fast: bool = False,
        skip_lock: bool = False,
        skip_rgv587_retry: bool = False,
    ) -> list[ItemSummary]:
        """关键词搜索 + 滚动加载完整列表

        Args:
            keyword: 搜索关键词
            max_pages: 最多翻多少"屏"（每次滚动算一屏）
            page: 可选 page 注入
            search_filters: 闲鱼筛选标签（如 personal_idle, free_shipping），
                           会映射为 URL 查询参数追加到搜索 URL
            fast: 快速模式——跳过 token 刷新（Worker 会处理）、RGV587 时不重试
            skip_lock: 跳过 browser_lock 获取（调用方已持有锁时使用）
            skip_rgv587_retry: 跳过 RGV587 重试（Worker 用，避免 75 秒重试占用锁）

        Returns:
            搜索结果 ItemSummary 列表（已去重）
        """
        own_page = page is None
        if own_page:
            page = await self.browser.new_page()
        assert page is not None
        items: list[ItemSummary] = []
        # Worker 搜索时获取 browser_lock，与 live 端点互斥
        # skip_lock=True 时跳过（live 端点已在外层持有锁）
        release_lock = False
        if self._browser_lock is not None and own_page and not skip_lock:
            await self._browser_lock.acquire()
            release_lock = True
        try:
            # H-06 修复：keyword 需做 URL 编码，避免 & # % % 等特殊字符破坏查询语义
            # 追加筛选标签对应的 URL 参数（映射关系见 domain/task.py XIANYU_FILTER_MAP）
            filter_params: list[str] = []
            if search_filters:
                filter_params = [XIANYU_FILTER_MAP[f] for f in search_filters if f in XIANYU_FILTER_MAP]
                if filter_params:
                    logger.info("搜索筛选参数: {}", ", ".join(search_filters))
            url = build_search_url(keyword, filter_params=filter_params)
            logger.info(f"搜索: {url}")
            await self.ad.throttle()

            # 快速模式跳过 token 刷新——Worker 调度器会定期刷新，无需每次实时搜索都刷新
            if not fast:
                await self._ensure_fresh_m5tk(page)

            # 优先通过 route 拦截捕获 API 响应获取结构化数据
            api_items, session_invalid = await self._call_search_api(page, keyword, max_pages, fast=fast, skip_rgv587_retry=skip_rgv587_retry)
            # 记录会话失效状态，供 Worker 检测后暂停任务
            self.last_session_invalid = session_invalid
            if api_items:
                items = api_items
            else:
                # API 不可用或会话失效时，均尝试 DOM 解析作为兜底
                # RGV587_ERROR 时页面仍可能渲染搜索结果（10:06 验证可行），不应直接放弃
                if session_invalid:
                    logger.warning("搜索 API 会话失效，尝试 DOM 回退: keyword={}", keyword)
                else:
                    logger.info("API 不可用，回退到 DOM 解析: {}", keyword)
                # RGV587 时页面可能未完全渲染，缩短等待时间避免 API 超时
                await self.ad.human_delay(1000, 2000)
                # 检查页面是否被重定向到非搜索页面（RGV587 可能触发验证页面跳转）
                try:
                    current_url = page.url
                    if "goofish.com/search" not in current_url:
                        logger.warning("页面已跳转至非搜索页，跳过 DOM 回退: url={}", current_url[:100])
                        cards = []
                    else:
                        # 先用 evaluate 检查卡片数量（不会卡住），再决定是否执行 query_selector_all
                        card_count = await asyncio.wait_for(
                            page.evaluate(
                                "() => document.querySelectorAll(\"[class*='feeds-item-wrap'], [class*='feeds-item']\").length"
                            ),
                            timeout=5.0,
                        )
                        if card_count == 0:
                            logger.info("DOM 回退: 页面无搜索卡片 (RGV587 可能阻止了渲染)")
                            cards = []
                        else:
                            logger.info("DOM 回退: 检测到 {} 个卡片，开始解析", card_count)
                            cards = await asyncio.wait_for(self._find_cards(page), timeout=8.0)
                except asyncio.TimeoutError:
                    logger.warning("DOM 回退查找卡片超时，放弃: keyword={}", keyword)
                    cards = []
                except Exception as e:
                    logger.warning("DOM 回退异常: {}", str(e)[:80])
                    cards = []
                if cards:
                    logger.info("DOM 解析发现 {} 个卡片", len(cards))
                    filtered_out = []
                    for card in cards:
                        summary = await self._parse_card(card)
                        if summary and summary.id and not any(i.id == summary.id for i in items):
                            # 使用分词匹配替代严格子串匹配，避免限流时默认推荐被全部排除
                            if keyword and summary.title and not task_keyword_matches_title(keyword, summary.title):
                                filtered_out.append(summary.title[:50])
                                continue
                            items.append(summary)
                    if filtered_out:
                        logger.info("DOM 回退过滤掉 {} 个标题 (关键词={}): {}", len(filtered_out), keyword, filtered_out)
                    logger.info("DOM 解析有效结果: {} 个", len(items))
                if not items:
                    logger.info("搜索无结果: {}", keyword)

            logger.info(f"搜索完成: 共 {len(items)} 个商品")
        except Exception as e:
            logger.exception(f"搜索失败 {keyword}: {e}")
        finally:
            if own_page:
                try:
                    await page.close()
                except Exception:
                    pass  # 页面可能已被取消，忽略关闭异常
            if release_lock:
                self._browser_lock.release()
        return items

    # 搜索 API 精确匹配的端点路径（避免误匹配 shade/activate 等子 API）
    _SEARCH_API_PATH = "mtop.taobao.idlemtopsearch.pc.search/1.0"

    async def _call_search_api(self, page: Page, keyword: str, max_pages: int = 3, fast: bool = False, skip_rgv587_retry: bool = False) -> tuple[list[ItemSummary], bool]:
        """通过 Playwright route 拦截捕获搜索 API 响应

        页面加载时会自然发起 mtop API 请求获取搜索结果。
        通过 route 拦截这些请求并捕获响应，绕过 CORS 限制。
        比 JS fetch 方式更可靠，因为使用的是页面自身的请求上下文。

        Args:
            fast: 快速模式——RGV587 时不重试、减少等待时间（8秒 vs 15秒）
            skip_rgv587_retry: 跳过 RGV587 重试（Worker 用，避免 75 秒重试占用 browser_lock）

        Returns:
            (items, session_invalid): items 为搜索结果列表，session_invalid 表示
            会话失效（RGV587_ERROR），此时 DOM 回退也无法获取结果，应停止重试。
        """
        items: list[ItemSummary] = []
        captured_responses: list[dict] = []
        session_invalid: bool = False  # RGV587 表示会话失效，不是普通限流

        async def _handle_route(route):
            """拦截搜索 API 请求，捕获响应体"""
            nonlocal session_invalid
            req_url = route.request.url
            # 精确匹配搜索 API 端点，排除 shade/activate 等子 API
            if self._SEARCH_API_PATH in req_url:
                try:
                    response = await route.fetch()
                    body = await response.json()
                    ret = body.get("ret", [])
                    if ret and isinstance(ret, list):
                        ret_str = str(ret[0]) if ret else ""
                        if "RGV587" in ret_str:
                            # RGV587_ERROR 表示会话失效／反爬检测，非普通限流
                            # 此时闲鱼要求重新登录，DOM 回退也无法获取搜索结果
                            logger.warning(
                                "搜索 API 会话失效 (RGV587_ERROR)，需重新登录闲鱼: keyword={}",
                                keyword,
                            )
                            session_invalid = True
                            await route.fulfill(response=response)
                            return
                        if "ERROR" in ret_str or "FAIL" in ret_str:
                            logger.warning("搜索 API 返回错误 (可能限流/未登录): {}", ret_str[:100])
                            await route.fulfill(response=response)
                            return
                    captured_responses.append(body)
                    body_str = str(body)
                    logger.info("route 拦截捕获搜索 API 响应，大小: {} bytes", len(body_str))
                    logger.info("API 响应前500字符: {}", body_str[:500])
                    await route.fulfill(response=response)
                except Exception as e:
                    logger.warning("route 拦截处理失败: {}", str(e)[:80])
                    try:
                        await route.continue_()
                    except Exception:
                        pass
            else:
                try:
                    await route.continue_()
                except Exception:
                    pass  # 某些内部路由（如 service worker）可能已被处理

        await page.route("**/*", _handle_route)

        try:
            # 导航到搜索页（页面会自然发起 API 请求）
            url = build_search_url(keyword)
            # 快速模式使用 15 秒超时（vs 默认 30 秒），减少卡死风险
            goto_timeout = 15000 if fast else 30000
            await page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout)

            # 等待 API 响应：快速模式最多 8 秒，正常模式最多 15 秒
            wait_rounds = 8 if fast else 15
            for _ in range(wait_rounds):
                if captured_responses or session_invalid:
                    break
                await asyncio.sleep(1)

            # 会话失效时尝试刷新 token 后重试一次
            # fast 模式或 skip_rgv587_retry 时跳过重试，直接返回（避免 75 秒重试占用 browser_lock）
            if session_invalid and not fast and not skip_rgv587_retry:
                logger.warning("搜索 API 会话失效，尝试强制刷新 _m_h5_tk 后重试: keyword={}", keyword)
                # 强制刷新 token（跳过缓存）
                refreshed = await self._ensure_fresh_m5tk(page, force=True)
                if refreshed:
                    # 重置状态，重新尝试搜索
                    session_invalid = False
                    captured_responses.clear()
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        # 等待 API 响应（最多等 15 秒）
                        for _ in range(15):
                            if captured_responses or session_invalid:
                                break
                            await asyncio.sleep(1)
                    except Exception as e:
                        logger.warning("RGV587 重试导航失败: {}", e)
                else:
                    logger.warning("强制刷新 _m_h5_tk 失败，跳过重试: keyword={}", keyword)

            # 会话失效时返回空列表，由 search 方法决定是否尝试 DOM 回退
            if session_invalid:
                logger.warning("搜索 API 会话失效，将尝试 DOM 回退: keyword={}", keyword)

            # 解析捕获到的 API 响应
            for resp in captured_responses:
                raw_items = self._parse_search_api_result(resp)
                if not raw_items:
                    continue
                logger.info("route 拦截获取到 {} 个商品", len(raw_items))
                if raw_items:
                    # 打印第一条原始数据的所有 key，便于排查字段名
                    sample = raw_items[0]
                    logger.info("搜索API原始字段 keys={}", list(sample.keys())[:30])
                for raw in raw_items:
                    try:
                        # 提取卖家昵称和地区（委托到 collector_utils，处理 region 误存为 nick 的情况）
                        nick, _raw_region = extract_seller_nick(raw)
                        # 闲鱼 API 可能用不同字段名返回卖家ID和发布时间
                        seller_id = str(raw.get("sellerId") or raw.get("userId") or raw.get("sellerIdNum") or "")
                        # publishTime 为毫秒时间戳，需转换为 datetime
                        publish_time = None
                        pt_raw = raw.get("publishTime") or raw.get("gmtCreate") or raw.get("publishTimeStr")
                        if pt_raw:
                            try:
                                if isinstance(pt_raw, (int, float)):
                                    publish_time = datetime.fromtimestamp(pt_raw / 1000, tz=timezone.utc)
                                elif isinstance(pt_raw, str) and pt_raw.isdigit():
                                    publish_time = datetime.fromtimestamp(int(pt_raw) / 1000, tz=timezone.utc)
                            except Exception:
                                pass
                        # 缩略图 URL 补全协议头（API 返回 //img.alicdn.com 格式）
                        thumb_url = raw.get("picUrl", "")
                        if thumb_url and not thumb_url.startswith(("http://", "https://")):
                            thumb_url = "https:" + thumb_url
                        # 一次性构造 ItemSummary
                        item = ItemSummary(
                            id=str(raw.get("itemId", "")),
                            title=raw.get("title", ""),
                            price=float(raw.get("price", 0)),
                            region=_raw_region,
                            seller_id=seller_id,
                            seller_nick=nick or "",
                            want_cnt=int(raw.get("wantCnt", 0) or 0),
                            view_cnt=int(raw.get("viewCnt", 0) or 0),
                            thumb_url=thumb_url,
                            is_sold=check_item_sold(raw),
                            publish_time=publish_time,
                            # 尝试从搜索API提取卖家基本信息（用于降级评估）
                            seller_credit_score=self._extract_credit_from_api_raw(raw),
                            seller_on_sale_count=int(raw.get("onSaleCount", raw.get("itemCount", 0)) or 0),
                            seller_sold_count=int(raw.get("soldCount", 0) or 0),
                        )
                        if nick and item.seller_id:
                            self._seller_nicks[item.seller_id] = nick
                        if item.id and not any(i.id == item.id for i in items):
                            items.append(item)
                    except Exception:
                        continue

                # 翻页：滚动以触发更多 API 请求
                if len(raw_items) >= 20 and len(captured_responses) < max_pages:
                    # 清空旧的响应，准备捕获下一页
                    captured_responses.clear()
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await self.ad.human_delay(2000, 4000)
                    # 等待下一页 API 响应
                    for _ in range(10):
                        if captured_responses:
                            break
                        await asyncio.sleep(1)
                else:
                    break

        finally:
            # 页面可能已损坏（TargetClosedError），unroute 需超时+异常保护避免卡住
            # 不传 handler，直接移除所有匹配 url 的路由，避免 handler 匹配导致的卡住
            try:
                await asyncio.wait_for(page.unroute("**/*"), timeout=5.0)
                logger.info("page.unroute 完成")
            except asyncio.TimeoutError:
                logger.warning("page.unroute 超时，可能影响后续 DOM 解析")
            except Exception as e:
                logger.warning("page.unroute 异常: {}", str(e)[:80])

        # 记录是否捕获到 API 响应（供 live_links 判断 Cookie 失效）
        # captured_responses 非空但 items 为空 → 可能是登录墙响应或会话过期
        self._last_api_captured = bool(captured_responses)
        return items, session_invalid

    def _parse_search_api_result(self, result: dict) -> list[dict]:
        """解析搜索 API 返回的商品列表（委托到 collector_utils）"""
        return parse_search_api_result(result)

    async def _wait_for_cards(self, page: Page, timeout: int = 15000) -> None:
        """等待首个搜索卡片出现（尝试多个选择器）"""
        for selector in self.selectors.search_card_candidates():
            try:
                await page.wait_for_selector(selector, timeout=timeout // len(self.selectors.search_card_candidates()))
                return
            except PlaywrightTimeout:
                continue
        logger.warning("搜索卡片未找到任何匹配选择器")

    async def _find_cards(self, page: Page) -> list[Any]:
        """查找所有搜索卡片（尝试多个选择器）"""
        for selector in self.selectors.search_card_candidates():
            cards = await page.query_selector_all(selector)
            if cards:
                return cards
        return []

    async def _parse_card(self, card: Any) -> ItemSummary | None:
        """解析单个商品卡片为 ItemSummary

        注意：闲鱼搜索结果卡片本身就是 <a> 标签（class="feeds-item-wrap--*"），
        所以先判断 card.tagName，若为 A 则直接用 card 当链接；
        否则在内部找第一个 <a>。
        """
        try:
            # 1. 链接：card 本身可能就是 <a>，否则向内找
            tag = (await card.evaluate("el => el.tagName")).upper() if hasattr(card, "evaluate") else ""
            link = card if tag == "A" else await card.query_selector(self.selectors.CARD_LINK_MAIN)
            if not link:
                return None
            href = await link.get_attribute("href") or ""
            item_id = self._extract_item_id(href)
            if not item_id:
                return None

            # 标题
            title = ""
            for sel in self.selectors.title_candidates():
                el = await card.query_selector(sel)
                if el:
                    title = (await el.inner_text()).strip()
                    if title:
                        break

            # 价格
            price = 0.0
            for sel in self.selectors.price_candidates():
                el = await card.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    price = parse_price_from_text(text)
                    if price > 0:
                        break

            # 缩略图：优先 src，回退 data-src（懒加载），再回退 data-original
            thumb = ""
            img = await card.query_selector(self.selectors.CARD_THUMB_MAIN)
            if img:
                for attr in ("src", "data-src", "data-original", "data-lazy-src"):
                    thumb = (await img.get_attribute(attr)) or ""
                    if thumb and not thumb.startswith("data:"):
                        break
                # 协议相对 URL 补全（//img.alicdn.com → https://img.alicdn.com）
                if thumb and thumb.startswith("//"):
                    thumb = "https:" + thumb

            # 卖家所在地（搜索结果卡片中仅有所在地文本，无卖家ID/链接）
            # 卖家ID需访问详情页才能获取，搜索卡片不包含
            region = ""
            seller_loc = await card.query_selector(self.selectors.CARD_SELLER_LOCATION)
            if seller_loc:
                region = (await seller_loc.inner_text()).strip()

            # 从卡片文本中提取想要数和发布时间（DOM 回退模式下的降级提取）
            want_cnt = 0
            publish_time = None
            try:
                card_text = await card.inner_text()
                # 想要数：匹配 "X人想要" 或 "想要 X" 格式
                want_match = re.search(r"(\d+)\s*人想要", card_text)
                if want_match:
                    want_cnt = int(want_match.group(1))
            except Exception:
                pass

            return ItemSummary(
                id=item_id,
                title=title,
                price=price,
                thumb_url=thumb,
                region=region,
                is_sold=await self._check_card_sold(card),
                want_cnt=want_cnt,
                publish_time=publish_time,
            )
        except Exception as e:
            logger.warning(f"解析卡片失败: {e}")
            return None

    @staticmethod
    def _extract_item_id(href: str) -> str:
        """从 URL 中提取商品 ID（委托到 collector_utils）"""
        return extract_item_id(href)

    @staticmethod
    def _check_item_sold(raw: dict) -> bool:
        """从 API 响应中检测商品是否已售出（委托到 collector_utils）"""
        return check_item_sold(raw)

    async def _check_card_sold(self, card: Any) -> bool:
        """从 DOM 卡片中检测商品是否已售出

        闲鱼搜索结果中已售商品通常有：
        - "已售" 文字标记
        - 特殊 CSS 类名（如 sold, sold-out）
        - 灰色价格或"已售"标签
        """
        try:
            # 方法1：检查卡片文本是否包含"已售"
            text = (await card.inner_text()) if hasattr(card, 'inner_text') else ""
            if "已售" in text:
                return True

            # 方法2：检查是否有已售相关的 CSS 类
            class_name = (await card.get_attribute("class")) or ""
            if any(kw in class_name for kw in ["sold", "sold-out", "offline", "dealed"]):
                return True

            # 方法3：检查子元素中的已售标签
            sold_selectors = [
                ".sold-tag",
                ".sold-out-tag",
                "[class*='sold']",
                ".item-status-sold",
                ".dealed-text",
            ]
            for sel in sold_selectors:
                el = await card.query_selector(sel)
                if el:
                    return True

            return False
        except Exception:
            return False

    @staticmethod
    def _extract_credit_from_api_raw(raw: dict) -> int | None:
        """从搜索API原始数据中尝试提取卖家信用分

        闲鱼搜索API可能返回以下字段（字段名可能变化）：
        - userCreditScore / creditScore / credit_score
        - zhimaCredit / zhima_score
        """
        credit_fields = [
            "userCreditScore", "creditScore", "credit_score",
            "zhimaCredit", "zhima_score", "credit",
            "userCredit", "sellerCredit",
        ]
        for field in credit_fields:
            val = raw.get(field)
            if val is not None:
                try:
                    score = int(val)
                    # 合理的信用分范围：400-950
                    if 400 <= score <= 950:
                        return score
                except (ValueError, TypeError):
                    continue
        return None

    async def seller_profile_fallback(
        self,
        summary: ItemSummary | None = None,
        detail: ItemDetail | None = None,
    ) -> SellerProfile:
        """降级策略：从搜索结果+详情页构建基本 SellerProfile

        当卖家主页采集失败时，使用此方法合并已采集到的卖家信息，
        构建一个基本的 SellerProfile 用于评估（虽然不完整但比默认值好）。

        优化：同一卖家的多个商品会复用缓存的降级结果（提升性能）。

        优先级：
        1. 搜索API中的卖家信息（summary）
        2. 详情页中提取的卖家信息（detail）
        3. 默认值（标记为数据不足）
        """
        from xianyu_hunter.domain.seller import SellerProfile

        # 确定缓存 key（优先用详情页的 seller_id，其次用搜索结果的）
        cache_key = ""
        if detail and detail.seller_id:
            cache_key = detail.seller_id
        elif summary and summary.seller_id:
            cache_key = summary.seller_id

        # 检查缓存（同一卖家不重复计算）
        if cache_key and cache_key in self._seller_profile_cache:
            logger.debug("[SellerProfile降级] 命中缓存: seller_id=%s", cache_key)
            return self._seller_profile_cache[cache_key]

        seller_id = ""
        nick = ""
        credit_score: int | None = None
        on_sale_count = 0
        sold_count = 0

        # 1. 从 ItemSummary（搜索结果）提取
        if summary:
            seller_id = summary.seller_id or seller_id
            nick = summary.seller_nick or nick
            credit_score = summary.seller_credit_score or credit_score
            on_sale_count = max(on_sale_count, summary.seller_on_sale_count)
            sold_count = max(sold_count, summary.seller_sold_count)

        # 2. 从 ItemDetail（详情页）提取更多信息（优先级高于搜索结果）
        if detail:
            seller_id = detail.seller_id or seller_id
            # 详情页的卖家昵称通常更准确
            if detail.detail_seller_nick and not nick:
                nick = detail.detail_seller_nick
            # 详情页的信用分优先于搜索结果
            if detail.detail_credit_score is not None:
                credit_score = detail.detail_credit_score
            on_sale_count = max(on_sale_count, detail.detail_on_sale_count)
            sold_count = max(sold_count, detail.detail_sold_count)

        # 3. 判断数据质量
        has_basic_info = any([
            credit_score is not None and credit_score > 0,
            on_sale_count > 0,
            sold_count > 0,
            bool(nick),
        ])

        result = SellerProfile(
            id=seller_id or "unknown",
            nick=nick,
            credit_score=credit_score,
            register_days=0,  # 无法从搜索/详情页获取
            on_sale_count=on_sale_count,
            sold_count=sold_count,
        )

        # 写入缓存（仅对有明确 seller_id 的记录缓存）
        final_cache_key = seller_id if seller_id else cache_key
        if final_cache_key and final_cache_key != "unknown":
            self._seller_profile_cache[final_cache_key] = result

        logger.info(
            "[SellerProfile降级] seller_id=%s nick=%s credit=%s on_sale=%s sold=%s 数据质量=%s",
            seller_id, nick, credit_score, on_sale_count, sold_count,
            "partial" if has_basic_info else "insufficient"
        )

        return result

    def clear_seller_profile_cache(self) -> int:
        """清空卖家画像降级缓存（通常在任务结束时调用）

        Returns:
            清除的缓存条目数
        """
        count = len(self._seller_profile_cache)
        self._seller_profile_cache.clear()
        logger.info("已清除 {} 条卖家画像降级缓存", count)
        return count

    async def live_search(
        self,
        keyword: str,
        max_pages: int = 2,
        page: Page | None = None,
        collect_sellers: bool = True,
        max_seller_details: int = 5,
        fast: bool = False,
    ) -> list[dict]:
        """实时搜索并返回前端可直接展示的结果（不经过数据库）

        返回格式与 task_links 列表 API 兼容，前端无需修改渲染逻辑。

        搜索结果卡片不含卖家ID，仅有所在地。因此需要访问详情页获取卖家ID：
        - collect_sellers=True 时，访问前 max_seller_details 个商品的详情页提取卖家ID
        - 此操作会显著增加耗时（每个详情页约 3-5 秒），但能获取真实卖家数据

        Args:
            fast: 快速模式——跳过 token 刷新、RGV587 时不重试、减少等待时间
        """
        items = await self.search(keyword, max_pages=max_pages, page=page, fast=fast, skip_lock=True)
        results: list[dict] = []
        # 优先从搜索结果中收集已有的 seller_id（API 响应中包含此字段）
        sellers_from_search: dict[str, dict] = {}
        for item in items:
            # 闲鱼商品详情页 URL 格式（.htm 已废弃，使用 /item?id=）
            item_url = build_item_url(item.id)
            # 卖家昵称：优先从 _seller_nicks 缓存中读取（搜索 API 已提取）
            seller_nick = self._seller_nicks.get(getattr(item, "seller_id", ""), "")
            base = {
                "item_id": item.id,
                "title": item.title,
                "price": item.price,
                "thumb_url": item.thumb_url,
                "region": item.region,
                "url": item_url,
                "is_sold": item.is_sold,
                "seller_id": getattr(item, "seller_id", ""),
                "seller_nick": seller_nick or getattr(item, "seller_nick", ""),
                "want_cnt": getattr(item, "want_cnt", 0),
                "view_cnt": getattr(item, "view_cnt", 0),
                "publish_time": getattr(item, "publish_time", None).isoformat() if getattr(item, "publish_time", None) else None,
            }
            # item 类型（url 已可由前端从 item_id 自动拼接，无需单独存储）
            results.append({**base, "link_type": "item", "link_key": item.id})
            # 搜索 API 已返回 seller_id 时直接收集，无需访问详情页
            if getattr(item, "seller_id", None) and item.seller_id not in sellers_from_search:
                sellers_from_search[item.seller_id] = {
                    "item_id": item.id,
                    "title": seller_nick or f"卖家 {item.seller_id}",
                    "price": None,
                    "thumb_url": "",
                    "region": item.region,
                    "url": build_seller_url(item.seller_id),
                    "link_type": "seller",
                    "link_key": item.seller_id,
                    "seller_id": item.seller_id,
                    "seller_nick": seller_nick,
                }
                logger.debug(f"live_search 从搜索结果提取卖家: {item.seller_id} (来自商品 {item.id})")

        # 将搜索结果中已获取的卖家加入 results
        for seller_data in sellers_from_search.values():
            results.append(seller_data)

        # 如果搜索结果中没有 seller_id（DOM 回退模式），访问详情页获取
        if collect_sellers and items and not sellers_from_search:
            seen_sellers: set[str] = set()
            own_page = page is None
            detail_page = page
            try:
                if own_page:
                    detail_page = await self.browser.new_page()
                assert detail_page is not None

                for item in items[:max_seller_details]:
                    if not item.id:
                        continue
                    try:
                        detail = await self.detail(item.id, page=detail_page)
                        if detail and detail.seller_id and detail.seller_id not in seen_sellers:
                            seen_sellers.add(detail.seller_id)
                            # DOM 回退模式下 detail() 不返回 nick（需访问卖家主页），
                            # 此处保持空字符串，前端会回退到 seller_id 展示
                            results.append({
                                "item_id": item.id,
                                "title": f"卖家 {detail.seller_id}",
                                "price": None,
                                "thumb_url": "",
                                "region": item.region,
                                "url": build_seller_url(detail.seller_id),
                                "link_type": "seller",
                                "link_key": detail.seller_id,
                                "seller_id": detail.seller_id,
                                "seller_nick": "",
                            })
                            logger.debug(f"live_search 提取卖家: {detail.seller_id} (来自商品 {item.id})")
                    except Exception as e:
                        logger.warning(f"live_search 提取卖家失败 item={item.id}: {e}")
            finally:
                if own_page and detail_page:
                    await detail_page.close()

        seller_count = len([r for r in results if r.get("link_type") == "seller"])
        logger.info(f"live_search 完成: {len(items)} 个商品, {seller_count} 个卖家, {len(results)} 条总结果")
        return results

    # ============== 详情 ==============

    async def detail(self, item_id: str, page: Page | None = None) -> ItemDetail | None:
        """商品详情"""
        own_page = page is None
        if own_page:
            page = await self.browser.new_page()
        assert page is not None
        try:
            await self.ad.throttle()
            url = build_item_url(item_id)
            logger.debug(f"详情: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # 等待标题
            try:
                await page.wait_for_selector(
                    self.selectors.DETAIL_TITLE_MAIN, timeout=10000
                )
            except PlaywrightTimeout:
                logger.warning(f"详情页 {item_id} 标题未出现")

            # 解析标题
            title = ""
            for sel in [self.selectors.DETAIL_TITLE_MAIN, self.selectors.DETAIL_TITLE_ALT]:
                el = await page.query_selector(sel)
                if el:
                    title = (await el.inner_text()).strip()
                    if title:
                        break

            # 价格
            price = 0.0
            for sel in [self.selectors.DETAIL_PRICE_MAIN, self.selectors.DETAIL_PRICE_ALT]:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    price = parse_price_from_text(text)
                    if price > 0:
                        break

            # 描述
            desc = ""
            for sel in [self.selectors.DETAIL_DESC_MAIN, self.selectors.DETAIL_DESC_ALT]:
                el = await page.query_selector(sel)
                if el:
                    desc = (await el.inner_text()).strip()
                    if desc:
                        break

            # 图片
            images: list[str] = []
            for sel in [self.selectors.DETAIL_IMAGES_MAIN, self.selectors.DETAIL_IMAGES_ALT]:
                img_els = await page.query_selector_all(sel)
                for img in img_els[:10]:  # 最多取 10 张
                    src = await img.get_attribute("src")
                    if src and src not in images:
                        images.append(src)
                if images:
                    break

            # 卖家 ID（从卖家链接提取，尝试多个选择器）
            seller_id = ""
            seller_link_selectors = [
                self.selectors.DETAIL_SELLER_LINK,
                self.selectors.DETAIL_SELLER_LINK_ALT1,
                self.selectors.DETAIL_SELLER_LINK_ALT2,
            ]
            for sel in seller_link_selectors:
                seller_link = await page.query_selector(sel)
                if seller_link:
                    href = await seller_link.get_attribute("href") or ""
                    # 支持 userId=xxx 和 /user/xxx 两种格式
                    m = re.search(r"userId=(\d+)", href)
                    if not m:
                        m = re.search(r"/user/(\d+)", href)
                    if m:
                        seller_id = m.group(1)
                        logger.debug("通过选择器 %s 提取卖家ID: %s", sel, seller_id)
                        break

            # 从详情页DOM提取卖家信息（用于降级评估，避免必须访问卖家主页）
            detail_seller_nick = ""
            detail_credit_score: int | None = None
            detail_on_sale_count = 0
            detail_sold_count = 0

            # 提取卖家昵称（详情页通常显示卖家名称）
            for nick_sel in [self.selectors.DETAIL_SELLER_NAME]:
                try:
                    nick_el = await page.query_selector(nick_sel)
                    if nick_el:
                        detail_seller_nick = (await nick_el.inner_text()).strip()
                        if detail_seller_nick:
                            break
                except Exception:
                    continue

            # 提取信用分（如果详情页有显示）
            for credit_sel in [self.selectors.SELLER_CREDIT_MAIN, self.selectors.SELLER_CREDIT_ALT]:
                try:
                    credit_el = await page.query_selector(credit_sel)
                    if credit_el:
                        credit_text = (await credit_el.inner_text()).strip()
                        m = re.search(r"\d{3,4}", credit_text)
                        if m:
                            detail_credit_score = int(m.group())
                            break
                except Exception:
                    continue

            return ItemDetail(
                id=item_id,
                title=title,
                price=price,
                description=desc,
                image_urls=images,
                seller_id=seller_id,
                publish_time=datetime.now(timezone.utc),  # 详情页可补充
                # 填充从详情页提取的卖家信息
                detail_seller_nick=detail_seller_nick,
                detail_credit_score=detail_credit_score,
                detail_on_sale_count=detail_on_sale_count,
                detail_sold_count=detail_sold_count,
            )
        except Exception as e:
            logger.exception(f"采集详情失败 {item_id}: {e}")
            return None
        finally:
            if own_page:
                await page.close()

    # ============== 卖家主页 ==============

    async def seller_profile(
        self, seller_id: str, page: Page | None = None
    ) -> SellerProfile | None:
        """卖家主页 → 画像

        注：访问卖家主页通常需要登录态，否则只能拿到公开信息。
        """
        own_page = page is None
        if own_page:
            page = await self.browser.new_page()
        assert page is not None
        try:
            await self.ad.throttle()
            url = build_seller_url(seller_id)
            logger.debug(f"卖家主页: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # 等待懒加载

            nick = ""
            for sel in [self.selectors.SELLER_NICK_MAIN, self.selectors.SELLER_NICK_ALT]:
                el = await page.query_selector(sel)
                if el:
                    nick = (await el.inner_text()).strip()
                    if nick:
                        break

            # 信用分
            credit_score: int | None = None
            for sel in [self.selectors.SELLER_CREDIT_MAIN, self.selectors.SELLER_CREDIT_ALT]:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    m = re.search(r"\d{3,4}", text)
                    if m:
                        credit_score = int(m.group())
                        break

            # 在售数、已售数
            on_sale = await self._extract_count(page, self.selectors.SELLER_ON_SALE_MAIN)
            sold = await self._extract_count(page, self.selectors.SELLER_SOLD_MAIN)

            # 注册天数：从注册时间文本解析（如"2020-01-01注册"或"3年前注册"）
            register_days = 0
            try:
                el = await page.query_selector(self.selectors.SELLER_REGISTER_MAIN)
                if el:
                    reg_text = (await el.inner_text()).strip()
                    register_days = self._parse_register_days(reg_text)
            except Exception:
                pass

            # 差评数
            bad_review_count = 0
            try:
                el = await page.query_selector(self.selectors.SELLER_BAD_REVIEW_MAIN)
                if el:
                    bad_review_count = await self._extract_count(page, self.selectors.SELLER_BAD_REVIEW_MAIN)
            except Exception:
                pass

            return SellerProfile(
                id=seller_id,
                nick=nick,
                credit_score=credit_score,
                on_sale_count=on_sale,
                sold_count=sold,
                register_days=register_days,
                bad_review_count=bad_review_count,
                last_visited=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.exception(f"采集卖家主页失败 {seller_id}: {e}")
            return None
        finally:
            if own_page:
                await page.close()

    @staticmethod
    async def _extract_count(page: Page, selector: str) -> int:
        """从元素文本中提取数字"""
        try:
            el = await page.query_selector(selector)
            if el:
                text = (await el.inner_text()).strip()
                m = re.search(r"\d+", text.replace(",", ""))
                if m:
                    return int(m.group())
        except Exception:
            pass
        return 0

    @staticmethod
    def _parse_register_days(text: str) -> int:
        """从注册时间文本解析为天数

        支持格式：
        - "2020-01-01注册" / "2020/01/01" → 计算距今天数
        - "3年前注册" / "2个月前" → 估算天数
        - "注册1234天" → 直接取数字
        """
        from datetime import datetime as _dt
        # 格式1：直接包含天数
        m = re.search(r"(\d+)\s*天", text)
        if m:
            return int(m.group(1))
        # 格式2：YYYY-MM-DD 或 YYYY/MM/DD
        m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
        if m:
            try:
                d = _dt(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                return max(0, (_dt.now() - d).days)
            except ValueError:
                pass
        # 格式3：N年前/N个月前
        m = re.search(r"(\d+)\s*年前", text)
        if m:
            return int(m.group(1)) * 365
        m = re.search(r"(\d+)\s*个月前", text)
        if m:
            return int(m.group(1)) * 30
        # 格式4：纯数字（假设是天数）
        m = re.search(r"(\d+)", text)
        if m:
            return int(m.group(1))
        return 0
