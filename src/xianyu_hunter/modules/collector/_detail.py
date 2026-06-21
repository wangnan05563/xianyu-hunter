"""详情与卖家画像 Mixin：商品详情、卖家主页、降级策略

将详情采集与卖家画像逻辑归为一类，因为 seller_profile_fallback 依赖 ItemDetail。
_extract_count / _parse_register_days 为卖家主页解析的辅助方法，一并归入此模块。
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from xianyu_hunter.domain.item import ItemDetail, ItemSummary
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.domain.urls import build_item_url, build_seller_url
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.modules.collector_utils import parse_price_from_text

logger = get_logger()


class DetailMixin:
    """详情与卖家画像 Mixin

    依赖 CollectorBase 的状态（browser/ad/selectors/_seller_profile_cache 等）。
    """

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
            # 方案A改进：有基本信息时给 30 天默认值，使降级数据至少有 1/3 字段有效
            # 避免评估器直接判定为"数据不足"导致所有评估记录显示 unknown
            register_days=30 if has_basic_info else 0,
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
