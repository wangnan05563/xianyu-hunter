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

    def _parse_search_api_result(self, result: dict) -> list[dict]:
        """解析搜索 API 返回的商品列表（委托到 collector_utils）"""
        return parse_search_api_result(result)
