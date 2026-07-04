"""解析相关 Mixin：DOM 卡片解析与 API 响应解析

将搜索结果的解析逻辑从主流程中分离，便于独立测试与维护。
解析方法依赖 self.selectors（选择器仓库）和 collector_utils 中的纯函数。
"""
from __future__ import annotations

import re
from typing import Any

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from xianyu_hunter.domain.item import ItemSummary
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.modules.collector_utils import (
    check_item_sold,
    check_text_sold,
    extract_item_id,
    parse_price_from_text,
    parse_search_api_result,
)

logger = get_logger()


class ParserMixin:
    """解析相关方法 Mixin

    提供 DOM 卡片解析、API 响应解析、已售检测等能力。
    依赖 CollectorBase 提供的 self.selectors 状态。
    """

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

        重构说明：将各字段提取拆分为独立私有方法，主方法只负责编排，
        降低圈复杂度（S3776）并便于单字段解析失败时定位问题。
        """
        try:
            # 1. 链接 + item_id：card 本身可能就是 <a>，否则向内找
            item_id = await self._extract_card_item_id(card)
            if not item_id:
                return None

            # 各字段独立提取，互不影响
            title = await self._extract_card_title(card)
            price = await self._extract_card_price(card)
            thumb = await self._extract_card_thumbnail(card)
            region = await self._extract_card_region(card)
            want_cnt = await self._extract_card_want_count(card)

            return ItemSummary(
                id=item_id,
                title=title,
                price=price,
                thumb_url=thumb,
                region=region,
                is_sold=await self._check_card_sold(card),
                want_cnt=want_cnt,
                publish_time=None,
            )
        except Exception as e:
            logger.warning(f"解析卡片失败: {e}")
            return None

    async def _extract_card_item_id(self, card: Any) -> str:
        """从卡片提取商品 ID：card 本身是 <a> 时直接用，否则向内找第一个 <a>

        为什么需要 tagName 判断：闲鱼卡片本身就是 <a> 标签，
        若再用 query_selector 找 <a> 会返回 None，必须分两路处理。
        """
        tag = (await card.evaluate("el => el.tagName")).upper() if hasattr(card, "evaluate") else ""
        link = card if tag == "A" else await card.query_selector(self.selectors.CARD_LINK_MAIN)
        if not link:
            return ""
        href = await link.get_attribute("href") or ""
        return self._extract_item_id(href)

    async def _extract_card_title(self, card: Any) -> str:
        """提取标题：按候选选择器顺序匹配，命中即返回

        多候选选择器应对闲鱼前端不同版本 DOM 结构差异。
        """
        for sel in self.selectors.title_candidates():
            el = await card.query_selector(sel)
            if el:
                title = (await el.inner_text()).strip()
                if title:
                    return title
        return ""

    async def _extract_card_price(self, card: Any) -> float:
        """提取价格：按候选选择器顺序匹配，命中即解析

        返回 0.0 表示未解析到有效价格。
        """
        for sel in self.selectors.price_candidates():
            el = await card.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                price = parse_price_from_text(text)
                if price > 0:
                    return price
        return 0.0

    async def _extract_card_thumbnail(self, card: Any) -> str:
        """提取缩略图 URL：优先 src，回退 data-* 懒加载属性

        闲鱼使用懒加载，真实 URL 通常在 data-src/data-original 中。
        跳过 data: URI（占位图），并对协议相对 URL（//开头）补全 https:。
        """
        img = await card.query_selector(self.selectors.CARD_THUMB_MAIN)
        if not img:
            return ""
        thumb = ""
        for attr in ("src", "data-src", "data-original", "data-lazy-src"):
            thumb = (await img.get_attribute(attr)) or ""
            if thumb and not thumb.startswith("data:"):
                break
        # 协议相对 URL 补全（//img.alicdn.com → https://img.alicdn.com）
        if thumb and thumb.startswith("//"):
            thumb = "https:" + thumb
        return thumb

    async def _extract_card_region(self, card: Any) -> str:
        """提取卖家所在地（搜索结果卡片中仅有所在地文本，无卖家ID/链接）

        卖家ID需访问详情页才能获取，搜索卡片不包含。
        """
        seller_loc = await card.query_selector(self.selectors.CARD_SELLER_LOCATION)
        if not seller_loc:
            return ""
        return (await seller_loc.inner_text()).strip()

    async def _extract_card_want_count(self, card: Any) -> int:
        """从卡片文本中提取想要数（DOM 回退模式下的降级提取）

        匹配 "X人想要" 格式；发布时间在搜索卡片中无法可靠提取，固定返回 None。
        为什么用正则而非选择器：闲鱼前端将"X人想要"渲染为纯文本节点，
        无独立 class，只能从卡片整体文本中匹配。
        """
        try:
            card_text = await card.inner_text()
            want_match = re.search(r"(\d+)\s*人想要", card_text)
            if want_match:
                return int(want_match.group(1))
        except Exception:
            pass
        return 0

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
        - "已售"/"卖掉了" 文字标记（详情页文案变更后新增"卖掉了"）
        - 特殊 CSS 类名（如 sold, sold-out）
        - 灰色价格或"已售"标签
        """
        try:
            # 方法1：检查卡片文本是否包含已售关键词（复用统一列表）
            text = (await card.inner_text()) if hasattr(card, 'inner_text') else ""
            if check_text_sold(text):
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

    def _parse_search_api_result(self, result: dict) -> list[dict]:
        """解析搜索 API 返回的商品列表（委托到 collector_utils）"""
        return parse_search_api_result(result)
