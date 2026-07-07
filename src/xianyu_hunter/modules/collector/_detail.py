"""详情与卖家画像 Mixin：商品详情、卖家主页、降级策略

将详情采集与卖家画像逻辑归为一类，因为 seller_profile_fallback 依赖 ItemDetail。
_extract_count / _parse_register_days 为卖家主页解析的辅助方法，一并归入此模块。
"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from xianyu_hunter.domain.item import ItemDetail, ItemSummary
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.domain.urls import build_item_url, build_seller_url
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.modules.collector_utils import check_text_delisted, check_text_sold, extract_brand, infer_brand_from_title, parse_price_from_text

logger = get_logger()

# P2 调试：每个 seller_id 只 dump 一次 innerText，避免日志/文件爆炸
_DUMPED_SELLER_IDS: set[str] = set()
# P2 调试：每个 item_id 只 dump 一次详情页卖家链接候选，避免日志/文件爆炸
_DUMPED_ITEM_IDS: set[str] = set()
# 首页标题特征：cookie 失效后 SPA 在当前 URL 渲染首页内容，URL 不变但标题是首页标题
# 此时 URL 校验无法检测，需要通过标题内容判断
_HOME_PAGE_TITLE_MARKERS = ("闲鱼 - 闲不住", "闲鱼-闲不住", "闲不住？上闲鱼")
_DATA_PREFIX = "data:"
_DIGITS_PATTERN = r"(\d+)"
# 闲鱼详情页图片可能使用懒加载：src 为占位符（data: URL），真实 URL 在 data-src/data-original/data-lazy-src 属性中
_LAZY_SRC_ATTRS = ("data-src", "data-original", "data-lazy-src", "data-img")
# 占位图标记：搜索 API 返回的 1x1 透明 PNG，详情页也可能出现
_PLACEHOLDER_MARKS = ("tps-2-2", "2-2.png", "1x1.png")


def _is_valid_image_src(src: str) -> bool:
    """判断图片 URL 是否有效：非空、非 data: 占位符、非 1x1 透明 PNG

    提取为模块级函数避免在循环内堆叠多个 if 导致认知复杂度超标（S3776）。
    """
    if not src or src.startswith(_DATA_PREFIX):
        return False
    return not any(mark in src for mark in _PLACEHOLDER_MARKS)


# 卖家信息标签解析规则：(字段名, 正则, 值转换函数)
# 为什么提取为模块级常量：原 _extract_detail_seller_info 内联 6 个 m = re.search + if m: continue
# 分支，单一方法认知复杂度堆积。提取为表驱动后解析逻辑集中且可单测。
# 年/月换算为天数（按 365/30 天近似，与闲鱼显示口径一致）
_SELLER_LABEL_PATTERNS: tuple[tuple[str, re.Pattern, Any], ...] = (
    # converter 收到的是 re.Match 对象而非字符串，必须显式取 group(1) 再 int
    # 否则 int(m) 报 "int() argument must be a string ... not 're.Match'"
    ("sold_count", re.compile(r"卖出(\d+)件"), lambda m: int(m.group(1))),
    ("on_sale_count", re.compile(r"在售(\d+)"), lambda m: int(m.group(1))),
    ("register_days", re.compile(r"来闲鱼(\d+)\s*天"), lambda m: int(m.group(1))),
    ("register_days", re.compile(r"来闲鱼(\d+)\s*年"), lambda m: int(m.group(1)) * 365),
    ("register_days", re.compile(r"来闲鱼(\d+)\s*个月"), lambda m: int(m.group(1)) * 30),
    ("credit_score", re.compile(r"好评率(\d+)%?"), lambda m: int(m.group(1))),
)


def _parse_seller_label_text(text: str) -> tuple[str, Any] | None:
    """解析单个卖家信息标签文本，返回 (字段名, 值) 或 None

    为什么提取为模块级函数：原 _extract_detail_seller_info 的 for 循环内嵌 6 个
    m = re.search + if m: continue 分支，elif 链贡献了主要认知复杂度。
    提取后 _extract_detail_seller_info 的 for 循环仅保留遍历骨架，解析职责分离。
    按顺序匹配第一条命中规则即返回（与原 continue 语义一致）。
    """
    for field, pattern, converter in _SELLER_LABEL_PATTERNS:
        m = pattern.search(text)
        if m:
            return field, converter(m)
    return None


def _parse_single_tab_count(text: str, prefix: str, current: int) -> int:
    """从 tab 文本中按前缀解析数字；未命中或已存在值时保持原值

    为什么未命中也返回 current：tab 遍历会逐个处理三种 tab（全部/在售/已售），
    大多数 tab 不匹配当前 prefix，应保持原值不变。
    """
    if not text.startswith(prefix):
        return current
    m = re.search(_DIGITS_PATTERN, text)
    return int(m.group(1)) if m else current


def _parse_sold_tab_count(text: str, current: int) -> int:
    """从已售 tab 文本中解析数字（兼容"已售出"/"已售"两种前缀）

    为什么单独函数：原代码用 `elif text.startswith("已售出") or text.startswith("已售")`
    复合条件，提取为函数后主循环只剩单行调用，认知复杂度下降。
    """
    if not (text.startswith("已售出") or text.startswith("已售")):
        return current
    m = re.search(_DIGITS_PATTERN, text)
    return int(m.group(1)) if m else current


def _parse_relative_publish_time(s: str, now: datetime) -> datetime | None:
    """解析相对时间描述为 datetime：刚刚 / X秒/分钟/小时前 / 今天/昨天 HH:MM / X天/周/月/年前

    按优先级顺序尝试，命中即返回；都不命中返回 None 由调用方继续尝试绝对时间解析。
    """
    from datetime import timedelta

    # 刚刚 / X秒前
    m = re.search(r"(\d+)\s*秒前", s)
    if m or s == "刚刚":
        return now - timedelta(seconds=int(m.group(1)) if m else 0)
    # X分钟前
    m = re.search(r"(\d+)\s*分钟前", s)
    if m:
        return now - timedelta(minutes=int(m.group(1)))
    # X小时前
    m = re.search(r"(\d+)\s*小时前", s)
    if m:
        return now - timedelta(hours=int(m.group(1)))
    # 今天 HH:MM
    m = re.search(r"今天\s*(\d{1,2}):(\d{1,2})", s)
    if m:
        return now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    # 昨天 HH:MM
    m = re.search(r"昨天\s*(\d{1,2}):(\d{1,2})", s)
    if m:
        t = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        return t - timedelta(days=1)
    # X天前
    m = re.search(r"(\d+)\s*天前", s)
    if m:
        return now - timedelta(days=int(m.group(1)))
    # X周前
    m = re.search(r"(\d+)\s*周前", s)
    if m:
        return now - timedelta(weeks=int(m.group(1)))
    # X个月前
    m = re.search(r"(\d+)\s*个?月前", s)
    if m:
        return now - timedelta(days=int(m.group(1)) * 30)
    # X年前
    m = re.search(r"(\d+)\s*年前", s)
    if m:
        return now - timedelta(days=int(m.group(1)) * 365)
    return None


def _parse_absolute_publish_time(s: str) -> datetime | None:
    """解析绝对时间格式：YYYY-MM-DD HH:MM[:SS] 或纯日期 YYYY-MM-DD / YYYY/MM/DD

    两种格式分别尝试，解析失败（如月份越界）静默返回 None 由调用方兜底。
    """
    # 1. 完整日期时间：YYYY-MM-DD HH:MM[:SS] 或 YYYY/MM/DD HH:MM
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", s)
    if m:
        try:
            y, mo, d, h, mi, se = m.groups()
            return datetime(
                int(y), int(mo), int(d), int(h), int(mi), int(se or 0),
                tzinfo=timezone.utc,
            )
        except ValueError:
            pass
    # 2. 纯日期：YYYY-MM-DD 或 YYYY/MM/DD
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


class DetailMixin:
    """详情与卖家画像 Mixin

    依赖 CollectorBase 的状态（browser/ad/selectors/_seller_profile_cache 等）。
    """

    def _mark_detail_session_invalid(self, item_id: str, reason: str) -> None:
        """标记详情采集发现的会话失效，让 Worker/Scheduler 立即短路暂停。"""
        if not getattr(self, "last_session_invalid", False):
            logger.warning("详情页 {} 检测到会话失效：{}，后续任务将暂停", item_id, reason)
        else:
            logger.debug("详情页 {} 再次检测到会话失效：{}", item_id, reason)
        self.last_session_invalid = True

    async def _wait_for_detail_render_signal(self, page: Page, timeout_ms: int = 2500) -> str:
        """等待详情页出现任一可用渲染信号，避免标题选择器固定等满 10s。"""
        signal = await page.wait_for_function(
            """(selectors) => {
                const hasText = (selector) => {
                    const el = document.querySelector(selector);
                    return !!(el && (el.textContent || '').trim());
                };
                if (hasText(selectors.titleMain)) return 'title';
                if (hasText(selectors.priceMain) || hasText(selectors.priceAlt)) return 'price';
                const og = document.querySelector("meta[property='og:title']");
                if (og && (og.getAttribute('content') || '').trim()) return 'og:title';
                if ((document.title || '').trim()) return 'document.title';
                return false;
            }""",
            arg={
                "titleMain": self.selectors.DETAIL_TITLE_MAIN,
                "priceMain": self.selectors.DETAIL_PRICE_MAIN,
                "priceAlt": self.selectors.DETAIL_PRICE_ALT,
            },
            timeout=timeout_ms,
        )
        return str(await signal.json_value())

    def _check_detail_http_status(self, item_id: str, response: Any) -> bool:
        """检查 HTTP 状态码；返回 True 表示需要提前终止（4xx/3xx 异常状态）。"""
        if response is None:
            return False
        http_status = response.status
        if http_status >= 400:
            self.last_detail_failure_reason = "http_status_error"
            logger.warning(
                f"详情页 {item_id} HTTP {http_status}（页面可能已下架/被限制），主动返回 None"
            )
            return True
        if http_status >= 300:
            self.last_detail_failure_reason = "http_status_error"
            redirect_url = response.headers.get("location", "")
            logger.warning(
                f"详情页 {item_id} 被重定向 HTTP {http_status} → {redirect_url}，主动返回 None"
            )
            return True
        return False

    async def _wait_render_signal_with_timeout(self, page: Page, item_id: str) -> str:
        """等待详情页渲染信号，超时降级到 'timeout' 并继续尝试备用提取。"""
        try:
            return await self._wait_for_detail_render_signal(page)
        except PlaywrightTimeout:
            render_signal = "timeout"
            logger.debug(f"详情页 {item_id} 渲染信号未出现，尝试备用提取")
            return render_signal

    async def _extract_detail_title(self, page: Page, item_id: str) -> str:
        """提取商品标题：DOM 选择器 → og:title meta → document.title。"""
        # 优先用 DOM 选择器，失败时依次从 og:title meta、document.title 兜底
        # og:title 是 SPA 框架（React/Vue）通用注入的 meta，不依赖业务 className
        # 当闲鱼改版导致 h1/[class*='title'] 失效时，og:title 仍可作可靠中间层
        for sel in [self.selectors.DETAIL_TITLE_MAIN, self.selectors.DETAIL_TITLE_ALT]:
            el = await page.query_selector(sel)
            if el:
                title = (await el.inner_text()).strip()
                if title:
                    return title
        # 兜底1：og:title meta（SPA 通常会注入，比 document.title 更纯粹的商品标题）
        title = await self._extract_title_from_og(page, item_id)
        if title:
            return title
        # 兜底2：document.title（格式 "商品标题_闲鱼"，需去掉后缀）
        return await self._extract_title_from_doc_title(page, item_id)

    async def _extract_title_from_og(self, page: Page, item_id: str) -> str:
        """从 og:title meta 提取标题（SPA 注入，比 document.title 更纯粹）。"""
        try:
            og_el = await page.query_selector("meta[property='og:title']")
            if og_el:
                og_title = (await og_el.get_attribute("content") or "").strip()
                if og_title:
                    logger.debug(f"详情页 {item_id} 标题从 og:title 兜底提取: {og_title}")
                    return og_title
        except Exception as e:
            logger.debug(f"详情页 {item_id} og:title 提取失败: {e}")
        return ""

    async def _extract_title_from_doc_title(self, page: Page, item_id: str) -> str:
        """从 document.title 提取标题（格式 "商品标题_闲鱼"，需去掉后缀）。"""
        try:
            doc_title = await page.title()
            if doc_title:
                # 兼容 "_闲鱼" 和 " - 闲鱼" 两种后缀格式
                for suffix in ("_闲鱼", " - 闲鱼", " | 闲鱼"):
                    if doc_title.endswith(suffix):
                        doc_title = doc_title[: -len(suffix)]
                        break
                title = doc_title.strip()
                if title:
                    logger.debug(f"详情页 {item_id} 标题从 document.title 兜底提取: {title}")
                    return title
        except Exception as e:
            logger.warning(f"详情页 {item_id} document.title 提取失败: {e}")
        return ""

    async def _early_detect_delisted(self, page: Page, item_id: str) -> ItemDetail | None:
        """早期下架检测：返回 ItemDetail 表示已下架需立即返回，None 表示继续。"""
        try:
            early_body_text = await page.text_content("body") or ""
        except Exception:
            early_body_text = ""
        if check_text_delisted(early_body_text):
            logger.info(
                f"详情页 {item_id} 检测到下架/被删除文案，标记 is_sold=True 并返回"
            )
            return ItemDetail(
                id=item_id,
                title="",
                price=0.0,
                is_sold=True,
            )
        return None

    def _is_home_page_title_early(self, item_id: str, title: str) -> bool:
        """首页标题检测（标题非空时）：cookie 失效标志。返回 True 表示需提前返回。"""
        # 首页标题检测必须早于卖家 ID dump 和卖家标签等待。
        # 登录态失效时闲鱼会在 item URL 渲染首页内容，继续提取只会产生无意义诊断文件。
        if not title:
            return False
        if not any(marker in title for marker in _HOME_PAGE_TITLE_MARKERS):
            return False
        self.last_detail_failure_reason = "home_title_redirect"
        self._mark_detail_session_invalid(item_id, f"首页标题 title={title}")
        logger.warning(
            f"详情页 {item_id} 提取到首页标题（title={title}），cookie 可能失效被重定向到首页，主动返回 None"
        )
        return True

    def _is_login_or_verify_redirect(self, page: Page, item_id: str) -> bool:
        """检测 URL 是否被重定向到登录/验证页。返回 True 表示需提前返回。"""
        try:
            current_url = page.url
            current_url_lower = current_url.lower()
            if "login" in current_url_lower or "passport" in current_url_lower:
                # 区分 login_redirect vs verify_redirect：login 是 cookie 失效（401），
                # verify 是反爬拦截（429），用户行动指引不同
                self.last_detail_failure_reason = "login_redirect"
                self._mark_detail_session_invalid(item_id, f"跳转登录页 url={current_url[:120]}")
                logger.warning(f"详情页 {item_id} 被重定向到登录页，请重新登录闲鱼")
                return True
            if "verify" in current_url_lower or "captcha" in current_url_lower:
                self.last_detail_failure_reason = "verify_redirect"
                self._mark_detail_session_invalid(item_id, f"触发验证页 url={current_url[:120]}")
                logger.warning(f"详情页 {item_id} 触发验证码，请手动完成验证后重试")
                return True
        except Exception:
            pass
        return False

    async def _extract_detail_price(self, page: Page, item_id: str) -> float:
        """提取价格，尝试主/备两个选择器。"""
        # 为什么添加详细日志：排查"本地价格与官网不一致"问题，
        # 需要确认 DOM 选择器取到的元素文本和解析后的价格
        price = 0.0
        for sel_idx, sel in enumerate([self.selectors.DETAIL_PRICE_MAIN, self.selectors.DETAIL_PRICE_ALT]):
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                price = parse_price_from_text(text)
                logger.debug(f"详情页 {item_id} 价格选择器[{sel_idx}] sel={sel!r} text={text!r} price={price}")
                if price > 0:
                    break
            else:
                logger.debug(f"详情页 {item_id} 价格选择器[{sel_idx}] sel={sel!r} 未匹配到元素")
        logger.info(f"详情页 {item_id} 最终采用价格: {price}")
        return price

    async def _extract_detail_description(self, page: Page) -> str:
        """提取描述（已用排除运费/服务条款的精细选择器）。"""
        for sel in [self.selectors.DETAIL_DESC_MAIN, self.selectors.DETAIL_DESC_ALT]:
            el = await page.query_selector(sel)
            if el:
                desc = (await el.inner_text()).strip()
                if desc:
                    return desc
        return ""

    @staticmethod
    async def _resolve_img_src(el: Any) -> str:
        """从 img 元素解析真实图片 URL，处理懒加载和占位符。"""
        src = await el.get_attribute("src")
        # src 为空或 data: URL（base64 占位符）时，尝试懒加载属性
        if not src or src.startswith(_DATA_PREFIX):
            for attr in _LAZY_SRC_ATTRS:
                src = await el.get_attribute(attr)
                if src and not src.startswith(_DATA_PREFIX):
                    return src
            return ""
        return src

    async def _extract_detail_images(self, page: Page) -> list[str]:
        """提取图片列表，最多取 10 张，跳过占位符。

        主函数只负责选择器遍历与去重收集，单张图片过滤下沉到辅助函数
        以降低认知复杂度（S3776）。
        """
        images: list[str] = []
        for sel in [self.selectors.DETAIL_IMAGES_MAIN, self.selectors.DETAIL_IMAGES_ALT]:
            img_els = await page.query_selector_all(sel)
            for img in img_els[:10]:  # 最多取 10 张
                src = await self._resolve_img_src(img)
                if _is_valid_image_src(src) and src not in images:
                    images.append(src)
            if images:
                break
        return images

    async def _extract_detail_thumb_url(self, page: Page, images: list[str]) -> str:
        """提取缩略图/主图 URL；与 image_urls 区别：必须是详情页顶部主图，避免被推荐/广告图污染。"""
        for sel in [self.selectors.DETAIL_THUMB_MAIN, self.selectors.DETAIL_THUMB_ALT]:
            thumb_el = await page.query_selector(sel)
            if thumb_el:
                src = await self._resolve_img_src(thumb_el)
                if src and not src.startswith(_DATA_PREFIX) and not any(mark in src for mark in _PLACEHOLDER_MARKS):
                    return src.strip()
        # 兜底：若主图选择器都失败，从 images 列表取首张
        if images:
            return images[0]
        return ""

    async def _extract_detail_region(self, page: Page) -> str:
        """提取地区，清洗换行/多余空白。"""
        for sel in [self.selectors.DETAIL_REGION_MAIN, self.selectors.DETAIL_REGION_ALT]:
            region_el = await page.query_selector(sel)
            if region_el:
                region = (await region_el.inner_text()).strip()
                if region:
                    return re.sub(r"\s+", " ", region)
        return ""

    async def _extract_detail_want_view_counts(self, page: Page, item_id: str) -> tuple[int, int]:
        """提取想要数和浏览数：先从 want-- 父元素提取，失败时用单独选择器兜底。

        主函数只负责编排（父元素解析 → 单字段兜底），
        两个子流程下沉到辅助函数以降低认知复杂度（S3776）。
        """
        want_cnt, view_cnt = await self._extract_want_view_from_parent(page, item_id)
        # 兜底：父元素提取失败时用原有选择器尝试
        if want_cnt == 0:
            want_cnt = await self._fallback_extract_count(
                page, [self.selectors.DETAIL_WANT_MAIN, self.selectors.DETAIL_WANT_ALT]
            )
        if view_cnt == 0:
            view_cnt = await self._fallback_extract_count(
                page, [self.selectors.DETAIL_VIEW_MAIN, self.selectors.DETAIL_VIEW_ALT]
            )
        return want_cnt, view_cnt

    async def _extract_want_view_from_parent(
        self, page: Page, item_id: str
    ) -> tuple[int, int]:
        """从 want-- 父元素 inner_text 中解析想要数与浏览数

        DOM 结构：<div class="want--XXX"><div>45人想要</div><div>1472浏览</div></div>
        子元素无 class，无法单独选中，需从父元素 inner_text 中用正则分别提取。
        """
        want_cnt = 0
        view_cnt = 0
        try:
            want_parent = await page.query_selector("[class*='want--']")
            if not want_parent:
                return 0, 0
            want_text = await want_parent.inner_text()
            # 想要数："45人想要"
            m_want = re.search(r"(\d+)\s*人想要", want_text)
            if m_want:
                want_cnt = int(m_want.group(1))
            # 浏览数："1472浏览"
            m_view = re.search(r"(\d+)\s*浏览", want_text)
            if m_view:
                view_cnt = int(m_view.group(1))
        except Exception as e:
            logger.debug(f"详情页 {item_id} 想要数/浏览数从 want-- 父元素提取失败: {e}")
        return want_cnt, view_cnt

    async def _fallback_extract_count(
        self, page: Page, selectors: list[str]
    ) -> int:
        """按选择器顺序尝试提取数字，命中即返回"""
        for sel in selectors:
            cnt = await self._extract_count(page, sel)
            if cnt > 0:
                return cnt
        return 0

    async def _extract_detail_publish_time(self, page: Page) -> datetime:
        """提取发布时间；解析失败时兜底为 now()，保证字段非空，避免评估/展示出现 None。"""
        for sel in [self.selectors.DETAIL_PUBLISH_TIME_MAIN, self.selectors.DETAIL_PUBLISH_TIME_ALT]:
            time_el = await page.query_selector(sel)
            if time_el:
                text = (await time_el.inner_text()).strip()
                if text:
                    publish_time = self._parse_publish_time(text)
                    if publish_time is not None:
                        return publish_time
        return datetime.now(timezone.utc)

    async def _extract_detail_seller_id(self, page: Page, item_id: str, url: str) -> str:
        """提取卖家 ID；失败时 dump 候选链接辅助人工定位新版闲鱼详情页结构。"""
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

        # P2 调试：详情页 seller_id 提取失败时 dump 页面诊断信息
        # 辅助人工定位新版闲鱼详情页的卖家链接真实 className/属性
        if not seller_id and item_id not in _DUMPED_ITEM_IDS:
            await self._dump_seller_id_candidates(page, item_id, url)

        return seller_id

    async def _dump_seller_id_candidates(self, page: Page, item_id: str, url: str) -> None:
        """P2 调试：dump 详情页卖家链接候选到 logs/，辅助人工更新选择器。"""
        try:
            hrefs = await page.evaluate(
                """() => {
                    const out = [];
                    const links = document.querySelectorAll('a[href]');
                    for (const a of links) {
                        const h = a.getAttribute('href') || '';
                        if (h.includes('user') || h.includes('seller') || h.includes('shop')) {
                            out.push({href: h, cls: a.className || '', text: (a.innerText || '').slice(0, 50)});
                        }
                    }
                    return out.slice(0, 30);
                }"""
            )
            dump_path = Path("logs") / f"detail_dom_{item_id}.json"
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            import json as _json
            # hrefs 为空时补充页面上下文，避免 dump 文件仅 "[]" 无法诊断
            # 场景：SPA 未渲染完成、页面被反爬拦截、详情页结构改版
            dump_payload = {
                "item_id": item_id,
                "url": url,
                "page_title": await page.title(),
                "candidate_links": hrefs,
            }
            if not hrefs:
                # 无候选链接时 dump body innerText 片段，辅助判断页面状态
                try:
                    body_text = await page.evaluate(
                        "() => (document.body && document.body.innerText || '').slice(0, 500)"
                    )
                    dump_payload["body_text_preview"] = body_text
                except Exception:
                    pass
            dump_path.write_text(
                _json.dumps(dump_payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _DUMPED_ITEM_IDS.add(item_id)
            logger.warning(
                "[P2 调试] 详情页 {} 卖家ID未提取，已 dump {} 个候选链接到 {}",
                item_id, len(hrefs), dump_path,
            )
        except Exception as e:
            # 不再静默吞异常，输出错误原因便于诊断
            logger.error("[P2 调试] 详情页 {} dump 失败: {}", item_id, e)

    async def _extract_detail_seller_info(self, page: Page, item_id: str) -> dict[str, Any]:
        """提取详情页卖家信息（昵称、信用分、在售数、已售数、注册天数）。

        新版闲鱼详情页在 item-user-info-label 中显示：
        地区 / 活跃时间 / 注册时间("来闲鱼X天"/"来闲鱼X年") / 已售数("卖出X件宝贝") / 好评率("好评率X%")
        SPA 页面异步渲染，标题出现后这些元素可能还未渲染，需显式等待。

        主函数只负责初始化与编排，昵称提取和标签解析下沉到辅助函数
        以降低认知复杂度（S3776）。
        """
        info: dict[str, Any] = {
            "nick": "",
            "credit_score": None,
            "on_sale_count": 0,
            "sold_count": 0,
            "register_days": 0,
        }
        info["nick"] = await self._extract_detail_seller_name(page)
        await self._populate_seller_info_labels(page, item_id, info)
        return info

    async def _extract_detail_seller_name(self, page: Page) -> str:
        """从详情页 DOM 提取卖家昵称

        为什么用 for 循环单元素：保留扩展为多候选选择器的能力，
        未来选择器改版时只需在列表中追加新选择器。
        """
        for nick_sel in [self.selectors.DETAIL_SELLER_NAME]:
            try:
                nick_el = await page.query_selector(nick_sel)
                if nick_el:
                    nick = (await nick_el.inner_text()).strip()
                    if nick:
                        return nick
            except Exception:
                continue
        return ""

    async def _populate_seller_info_labels(
        self, page: Page, item_id: str, info: dict[str, Any]
    ) -> None:
        """从详情页卖家信息标签提取结构化数据并写回 info

        标签解析逻辑统一在模块级函数 _parse_seller_label_text 中（表驱动）。
        SPA 异步渲染需显式等待选择器（5s 超时后仍尝试，可能部分元素已渲染）。
        """
        try:
            # 等待卖家信息标签出现（5s 超时，足够 SPA hydration 完成）
            try:
                await page.wait_for_selector(
                    self.selectors.DETAIL_REGION_MAIN, timeout=5000
                )
            except PlaywrightTimeout:
                logger.warning(f"详情页 {item_id} 卖家信息标签未出现（5s 超时），尝试继续提取")

            info_labels = await page.query_selector_all(self.selectors.DETAIL_REGION_MAIN)
            logger.debug(f"详情页 {item_id} 提取到 {len(info_labels)} 个 item-user-info-label 元素")
            for label_el in info_labels:
                text = (await label_el.inner_text()).strip()
                if not text:
                    continue
                # 解析单个标签文本并写回 info（6 种格式的识别逻辑统一在模块级函数中）
                parsed = _parse_seller_label_text(text)
                if parsed is not None:
                    field, value = parsed
                    info[field] = value
            # 提取结果汇总日志（便于诊断字段缺失问题）
            logger.info(
                f"详情页 {item_id} 卖家信息提取: register_days={info['register_days']}, "
                f"sold_count={info['sold_count']}, on_sale_count={info['on_sale_count']}, "
                f"credit_score={info['credit_score']}, nick={info['nick']}"
            )
        except Exception as e:
            # 不再静默吞异常，记录错误原因便于诊断
            logger.warning(f"详情页 {item_id} 卖家信息标签提取异常: {e}")

    async def _handle_title_extraction_failure(self, page: Page, item_id: str) -> None:
        """标题提取失败时记录日志并 dump HTML，便于事后分析选择器失效根因。

        P0 修复：避免超时后仍返回默认值，导致半残数据污染 items 表与评估结果。
        """
        # 检查页面是否被重定向到登录/验证页（通过 URL 判断）
        try:
            current_url = page.url
            if "login" in current_url.lower() or "passport" in current_url.lower():
                logger.warning(f"详情页 {item_id} 被重定向到登录页，请重新登录闲鱼")
            elif "verify" in current_url.lower() or "captcha" in current_url.lower():
                logger.warning(f"详情页 {item_id} 触发验证码，请手动完成验证后重试")
            else:
                logger.warning(f"详情页 {item_id} 标题提取失败（页面可能未加载/已下架/选择器失效），current_url={current_url}")
        except Exception:
            logger.warning(f"详情页 {item_id} 标题提取失败（页面可能未加载/已下架/选择器失效），主动返回 None")
        # P2 增强：dump 页面 HTML 便于事后分析选择器失效根因
        # 每个 item_id 仅 dump 一次，避免日志爆炸；与 _DUMPED_ITEM_IDS 复用集合
        if item_id not in _DUMPED_ITEM_IDS:
            try:
                html_content = await page.content()
                dump_path = Path("logs") / f"detail_html_{item_id}.html"
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                dump_path.write_text(html_content, encoding="utf-8")
                _DUMPED_ITEM_IDS.add(item_id)
                logger.warning(
                    "[P2 调试] 详情页 {} 标题提取失败已 dump HTML 到 {}（{} 字符）",
                    item_id, dump_path, len(html_content),
                )
            except Exception as dump_err:
                logger.error("[P2 调试] 详情页 {} dump HTML 失败: {}", item_id, dump_err)

    async def _second_detect_delisted(self, page: Page, item_id: str) -> ItemDetail | None:
        """二次下架检测（标题校验后）；返回 ItemDetail 表示已下架需立即返回。

        场景：商品被卖家删除时，闲鱼返回 HTTP 200 + URL 不变 + body 显示"糟糕！宝贝被删掉了"
        此时 document.title="闲鱼 - 闲不住？上闲鱼！"（与首页标题相同），
        若不提前拦截会被首页标题检测误判为 cookie 失效，导致 is_sold 无法更新
        用 check_text_delisted 而非 check_text_sold：已售商品详情页仍能提取 title/price，
        不应早期返回；仅"商品被删除/不存在"的错误页才早期返回
        """
        try:
            body_text = await page.text_content("body") or ""
        except Exception:
            body_text = ""
        if check_text_delisted(body_text):
            logger.info(
                f"详情页 {item_id} 检测到下架/被删除文案，标记 is_sold=True 并返回（其他字段保持默认空值，由 refresh_item 决定是否覆盖）"
            )
            return ItemDetail(
                id=item_id,
                title="",
                price=0.0,
                is_sold=True,
            )
        return None

    def _is_home_page_title_late(self, item_id: str, title: str) -> bool:
        """二次首页标题检测（标题校验后）。返回 True 表示需提前返回。

        cookie 失效后闲鱼 SPA 可能在当前 URL 渲染首页内容
        URL 校验无法检测（URL 未改变），通过标题内容判断是否为首页
        """
        if not any(marker in title for marker in _HOME_PAGE_TITLE_MARKERS):
            return False
        # 修复：早期检测 _is_home_page_title_early 调用了 _mark_detail_session_invalid
        # 但晚期检测漏调用，导致 Worker 无法感知此类失效继续调度任务
        self.last_detail_failure_reason = "home_title_redirect"
        self._mark_detail_session_invalid(item_id, f"二次首页标题 title={title}")
        logger.warning(
            f"详情页 {item_id} 提取到首页标题（title={title}），cookie 可能失效被重定向到首页，主动返回 None"
        )
        return True

    def _is_redirected_away_from_item(self, page: Page, item_id: str) -> bool:
        """校验当前 URL 仍是商品页；返回 True 表示需提前返回。

        场景：cookie 失效后 page.goto(goofish.com/item?id=...) 被闲鱼重定向到首页
        此时 page.url 变为 goofish.com（不带 /item），但 title 仍能取到 document.title="闲鱼 - 闲不住？上闲鱼！"
        之前会误把首页装饰数据当商品数据返回，污染 items 表
        """
        try:
            current_url = page.url
            if "/item" not in current_url or f"id={item_id}" not in current_url:
                self.last_detail_failure_reason = "redirected_away_from_item"
                logger.warning(
                    f"详情页 {item_id} 被重定向到非商品页（current_url={current_url}），主动返回 None"
                )
                return True
        except Exception:
            pass
        return False

    async def _detect_detail_is_sold(self, page: Page, item_id: str) -> bool:
        """已售检测：从 body 文本判断商品是否已售出/被删除。

        为什么复用 check_text_sold：闲鱼前端文案多次变更（如"已售"→"卖掉了"），
        分散维护会导致漏检。统一函数确保任一处发现新文案后全局生效
        """
        try:
            body_text = await page.text_content("body") or ""
            return check_text_sold(body_text)
        except Exception as e:  # noqa: BLE001
            # 静默失败会导致 is_sold 默认 False，已售商品被误判为在售
            # 记录 warning 便于排查页面崩溃/Playwright 异常导致的检测失败
            logger.warning("详情页 {} is_sold 检测失败: {}", item_id, e)
            return False

    def _extract_detail_brand(self, title: str, desc: str, seller_nick: str) -> str:
        """提取品牌：搜索 API brand > 卖家昵称匹配标题 > 标题关键词推断 > 描述推断。

        为什么不在 DOM 中查找 brand 元素：闲鱼详情页 className 是哈希值，
        无稳定选择器；从标题/卖家昵称推断已是搜索链路的成熟兜底，复用最稳
        """
        brand = extract_brand(None, title, seller_candidate=seller_nick)
        # 兜底：标题未命中品牌别名表时，从描述中继续推断
        # 闲鱼卖家常在描述开头写"品牌：联想"或"联想 ThinkPad X1"等关键词，
        # 描述长度比标题更长，品牌命中率更高；但只取首个命中，避免长描述误命中
        if not brand and desc:
            brand = infer_brand_from_title(desc[:200])
        return brand

    async def detail(self, item_id: str, page: Page | None = None) -> ItemDetail | None:
        """商品详情

        主函数只负责页面生命周期与 try/except 包装，
        字段采集主流程下沉到 _collect_detail 以降低认知复杂度（S3776）。
        """
        # 入口重置 reason：避免上次失败 reason 残留导致本次成功后上游误判
        # 仅在 detail() 返回 None 时 reason 才有意义
        self.last_detail_failure_reason = ""
        # 会话失效前置检查：上次检测到 Cookie 失效（首页标题）后立即返回，避免重复采集
        # 利用 _mark_detail_session_invalid 设置的 last_session_invalid 标志，减少无效日志噪声
        if getattr(self, "last_session_invalid", False):
            self.last_detail_failure_reason = "home_title_redirect"
            logger.debug("详情页 {} 跳过采集（会话已失效，last_session_invalid=True）", item_id)
            return None
        own_page = page is None
        if own_page:
            page = await self.browser.new_page()
            # 注册为外部 page，防止 scheduler.close_all_pages 误关
            # 场景：BatchRefreshScheduler 并发调用 detail() 时，主任务 run_once 结束清理会误关此 page
            self.browser.register_external_page(page)
        if page is None:
            raise RuntimeError("new_page 返回 None，浏览器可能已关闭")
        try:
            return await self._collect_detail(item_id, page)
        except Exception as e:
            return self._handle_detail_exception(item_id, e)
        finally:
            if own_page:
                self.browser.unregister_external_page(page)
                # page 可能已被并发关闭，close() 需异常保护避免 finally 抛错掩盖原异常
                try:
                    await page.close()
                except Exception:
                    pass

    async def _collect_detail(self, item_id: str, page: Page) -> ItemDetail | None:
        """详情页字段采集主流程（不含 try/except 包装）

        包含：page 防御性检查、HTTP 状态校验、标题/价格/图片/卖家等字段提取、
        下架/首页标题/重定向校验、最终组装 ItemDetail。
        """
        # 防御性检查：page 可能在 new_page() 的 await 返回前被 close_all_pages 并发关闭
        # 时序：new_page await 期间事件循环切换到 TaskScheduler.run_once 结束清理，
        # close_all_pages 遍历 context.pages 看到新 page（还未 register）将其关闭
        if page.is_closed():
            self.last_detail_failure_reason = "page_closed"
            logger.warning(f"详情页 {item_id} page 已关闭（并发清理或浏览器崩溃），跳过采集")
            return None
        # 延迟导入避免循环依赖
        from xianyu_hunter.modules.login_orchestrator import get_orchestrator
        from xianyu_hunter.modules.freq_disguise import ActionType
        await get_orchestrator().apply_freq_delay(ActionType.DETAIL)
        await self.ad.throttle()
        url = build_item_url(item_id)
        logger.debug(f"详情: {url}")
        _t0 = time.perf_counter()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        _t_goto = time.perf_counter() - _t0
        logger.debug(f"详情页 {item_id} page.goto 耗时 {_t_goto:.2f}s")

        # 检查 HTTP 状态码：404/403/302 等异常状态提前返回 None
        if self._check_detail_http_status(item_id, response):
            return None

        # 等待任一详情页渲染信号。新版闲鱼详情页经常没有 h1，固定等标题会让
        # 每个详情页白白耗满 10s；后续仍会做标题、价格、URL、首页标题校验。
        _t1 = time.perf_counter()
        render_signal = await self._wait_render_signal_with_timeout(page, item_id)
        _t_wait_title = time.perf_counter() - _t1
        logger.debug(f"详情页 {item_id} wait_for_render_signal({render_signal}) 耗时 {_t_wait_title:.2f}s")

        # 解析标题（DOM 选择器 → og:title → document.title 兜底）
        title = await self._extract_detail_title(page, item_id)

        # 下架/已删除页可能复用首页标题，需优先识别，避免误判为 cookie 失效。
        early_return = await self._early_detect_delisted(page, item_id)
        if early_return is not None:
            return early_return

        # 首页标题检测必须早于卖家 ID dump 和卖家标签等待。
        if self._is_home_page_title_early(item_id, title):
            return None

        if self._is_login_or_verify_redirect(page, item_id):
            return None

        # 提取各字段（价格/描述/图片/缩略图/地区/想要数/浏览数/发布时间/卖家ID/卖家信息）
        price = await self._extract_detail_price(page, item_id)
        desc = await self._extract_detail_description(page)
        images = await self._extract_detail_images(page)
        thumb_url = await self._extract_detail_thumb_url(page, images)
        region = await self._extract_detail_region(page)
        want_cnt, view_cnt = await self._extract_detail_want_view_counts(page, item_id)
        publish_time = await self._extract_detail_publish_time(page)
        seller_id = await self._extract_detail_seller_id(page, item_id, url)
        seller_info = await self._extract_detail_seller_info(page, item_id)

        # P0 修复：如果核心字段（标题）未提取成功，主动返回 None 让上游感知失败
        # 避免超时后仍返回默认值，导致半残数据污染 items 表与评估结果
        if not title:
            self.last_detail_failure_reason = "title_extraction_failed"
            await self._handle_title_extraction_failure(page, item_id)
            return None
        # 下架/已删除早期检测：在首页标题检测之前优先识别下架文案
        early_return = await self._second_detect_delisted(page, item_id)
        if early_return is not None:
            return early_return
        # 首页标题检测：cookie 失效后闲鱼 SPA 可能在当前 URL 渲染首页内容
        # URL 校验无法检测（URL 未改变），通过标题内容判断是否为首页
        if self._is_home_page_title_late(item_id, title):
            return None
        if price <= 0:
            # 价格未命中通常意味着详情页未正常加载（404/SPA 未渲染）
            self.last_detail_failure_reason = "price_extraction_failed"
            logger.warning(f"详情页 {item_id} 价格提取失败（title={title}, price={price}），主动返回 None")
            return None

        # P0 增强：校验当前 URL 仍是商品页，否则视为采集失败
        if self._is_redirected_away_from_item(page, item_id):
            return None

        # 已售/已删除检测
        is_sold = await self._detect_detail_is_sold(page, item_id)

        # 品牌字段
        brand = self._extract_detail_brand(title, desc, seller_info["nick"])

        # P3 埋点：成功路径总耗时（DEBUG 级别，便于诊断慢节点）
        _t_total = time.perf_counter() - _t0
        logger.debug(
            f"详情页 {item_id} 采集完成总耗时 {_t_total:.2f}s "
            f"(goto={_t_goto:.2f}s, wait_title={_t_wait_title:.2f}s)"
        )
        return ItemDetail(
            id=item_id,
            title=title,
            price=price,
            description=desc,
            image_urls=images,
            # P1 字段补齐：从详情页提取的结构化字段
            thumb_url=thumb_url,
            region=region,
            want_cnt=want_cnt,
            view_cnt=view_cnt,
            seller_id=seller_id,
            brand=brand,
            publish_time=publish_time,  # 已从详情页解析，无则兜底为 now()
            # 填充从详情页提取的卖家信息
            detail_seller_nick=seller_info["nick"],
            detail_credit_score=seller_info["credit_score"],
            detail_on_sale_count=seller_info["on_sale_count"],
            detail_sold_count=seller_info["sold_count"],
            detail_register_days=seller_info["register_days"],
            is_sold=is_sold,
        )

    def _handle_detail_exception(self, item_id: str, e: Exception) -> None:
        """处理 detail() 采集异常：TargetClosedError 降级为 WARNING，其他为 ERROR

        TargetClosedError 是已知并发场景（BatchRefreshScheduler 与 TaskScheduler.run_once
        并发清理），降级避免污染 ERROR 日志；page 已不可用，统一返回 None。
        """
        err_msg = str(e)
        if "Target" in err_msg and "closed" in err_msg:
            self.last_detail_failure_reason = "target_closed_exception"
            logger.warning(f"详情页 {item_id} 采集失败（页面被并发关闭）: {e}")
        else:
            self.last_detail_failure_reason = "unknown_exception"
            logger.exception(f"采集详情失败 {item_id}")
        return None

    async def seller_profile(
        self, seller_id: str, page: Page | None = None
    ) -> SellerProfile | None:
        """卖家主页 → 画像

        注：访问卖家主页通常需要登录态，否则只能拿到公开信息。

        重构说明：将各字段提取拆分为独立私有方法，主方法只负责页面生命周期与编排，
        降低圈复杂度（S3776）并便于单字段选择器失效时独立排查。
        """
        own_page = page is None
        if own_page:
            page = await self.browser.new_page()
            # 同 detail()：注册外部 page 防止并发清理误关
            self.browser.register_external_page(page)
        if page is None:
            raise RuntimeError("new_page 返回 None，浏览器可能已关闭")
        try:
            # 防御性检查：同 detail()，page 可能在 new_page await 期间被并发关闭
            if page.is_closed():
                logger.warning(f"卖家主页 {seller_id} page 已关闭（并发清理或浏览器崩溃），跳过采集")
                return None
            await self.ad.throttle()
            url = build_seller_url(seller_id)
            logger.debug(f"卖家主页: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # 等待懒加载

            # 各字段独立提取，互不影响
            nick = await self._extract_seller_nick(page)
            credit_score = await self._extract_seller_credit_score(page)
            on_sale, sold = await self._extract_seller_sale_counts(page, seller_id)
            register_days = await self._extract_seller_register_days(page)
            bad_review_count = await self._extract_seller_bad_review(page)

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
            err_msg = str(e)
            # 同 detail()：TargetClosedError 降级为 WARNING
            if "Target" in err_msg and "closed" in err_msg:
                logger.warning(f"卖家主页 {seller_id} 采集失败（页面被并发关闭）: {e}")
            else:
                logger.exception(f"采集卖家主页失败 {seller_id}")
            return None
        finally:
            if own_page:
                self.browser.unregister_external_page(page)
                try:
                    await page.close()
                except Exception:
                    pass

    async def _extract_seller_nick(self, page: Page) -> str:
        """提取卖家昵称：多候选选择器 + document.title 兜底

        为什么需要 title 兜底：新版卖家主页可能因选择器改版导致昵称为空，
        但 document.title 始终可用（格式"昵称_闲鱼"），是最后防线。

        title 兜底逻辑下沉到辅助函数以降低认知复杂度（S3776）。
        """
        nick = ""
        for sel in [self.selectors.SELLER_NICK_MAIN, self.selectors.SELLER_NICK_ALT]:
            el = await page.query_selector(sel)
            if el:
                nick = (await el.inner_text()).strip()
                if nick:
                    break
        # 昵称兜底：从 document.title 提取
        if not nick:
            nick = await self._extract_nick_from_doc_title(page)
        return nick

    async def _extract_nick_from_doc_title(self, page: Page) -> str:
        """从 document.title 提取卖家昵称（格式"昵称_闲鱼"，需去掉后缀）

        兼容三种后缀："_闲鱼" / " - 闲鱼" / " | 闲鱼"。
        """
        try:
            doc_title = await page.title()
            if not doc_title:
                return ""
            for suffix in ("_闲鱼", " - 闲鱼", " | 闲鱼"):
                if doc_title.endswith(suffix):
                    return doc_title[: -len(suffix)].strip()
        except Exception:
            pass
        return ""

    async def _extract_seller_credit_score(self, page: Page) -> int | None:
        """提取信用分：多候选选择器 + 3-4 位数字正则"""
        credit_score: int | None = None
        for sel in [self.selectors.SELLER_CREDIT_MAIN, self.selectors.SELLER_CREDIT_ALT]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                m = re.search(r"\d{3,4}", text)
                if m:
                    credit_score = int(m.group())
                    break
        return credit_score

    async def _extract_seller_sale_counts(
        self, page: Page, seller_id: str
    ) -> tuple[int, int]:
        """提取在售数、已售数：新版 tabItem 遍历 + 旧版选择器兜底

        新版闲鱼卖家主页用 tabItem 类，3 个 tab 文本分别为 "全部351"/"在售9"/"已售出342"。
        旧版用 onSale/sold + count 子元素。
        由于新版 className 是哈希化的 tabItem--HiFOTMcp，无法用 CSS 选择器区分，
        直接遍历 tabItem 按文本前缀匹配。

        主函数只负责编排（新版解析 → 旧版兜底 → 调试 dump），
        tabItem 文本解析下沉到辅助函数以降低认知复杂度（S3776）。
        """
        on_sale, sold = await self._parse_sale_counts_from_tabs(page)

        # 旧版兜底：新版未命中时尝试旧版选择器
        if on_sale == 0:
            on_sale = await self._extract_count(page, self.selectors.SELLER_ON_SALE_ALT)
        if sold == 0:
            sold = await self._extract_count(page, self.selectors.SELLER_SOLD_ALT)

        # P2 调试：每个 seller_id 只 dump 一次 innerText 到 logs/seller_dom_<id>.txt
        # 为什么只在 on_sale=0 时 dump：新版闲鱼已移除"已售出"tab，sold=0 是预期行为；
        # on_sale=0 才是真正的选择器失效（如 className 再次改版），需要 dump 辅助排查
        if on_sale == 0 and seller_id not in _DUMPED_SELLER_IDS:
            await self._dump_seller_dom_for_debug(page, seller_id, on_sale, sold)

        return on_sale, sold

    async def _parse_sale_counts_from_tabs(self, page: Page) -> tuple[int, int]:
        """从卖家主页 tab 元素文本中解析在售数/已售数

        旧版三个 tab 文本分别为 "全部N"/"在售N"/"已售出N"。
        新版（2026-07 改版）改为 "宝贝N"/"信用及评价N"，"在售/已售"tab 已移除。

        className 是哈希化的（如 tabItem--XXX），每次改版可能变化，
        因此用多组选择器兜底 + 文本前缀匹配，而非依赖固定 className。

        近似映射"宝贝"→on_sale（商品总数，含已售）；
        "信用及评价"是评价数≠已售数，不映射，sold 保持 0。
        """
        on_sale = 0
        sold = 0
        try:
            tab_texts = await page.evaluate(
                """() => {
                    // 多组选择器兜底：tabItem（旧版）/ tab-（新版可能的命名）
                    // 为什么不只用 [class*="tabItem"]：2026-07 改版后该选择器可能失效
                    let tabs = document.querySelectorAll('[class*="tabItem"]');
                    if (tabs.length === 0) {
                        tabs = document.querySelectorAll('[class*="tab"][role="tab"], [class*="Tab"][role="tab"]');
                    }
                    if (tabs.length === 0) {
                        // 最终兜底：扫描所有可点击元素，按已知文本前缀过滤
                        tabs = Array.from(document.querySelectorAll('div, span, a'))
                            .filter(el => {
                                const t = (el.innerText || '').trim();
                                return t.startsWith('在售') || t.startsWith('已售')
                                    || t.startsWith('宝贝') || t.startsWith('全部');
                            });
                    }
                    return Array.from(tabs).map(t => (t.innerText || '').trim());
                }"""
            )
            for text in tab_texts or []:
                on_sale = _parse_single_tab_count(text, "在售", on_sale)
                sold = _parse_sold_tab_count(text, sold)
                # 新版改版兜底：旧版"在售"tab 不存在时，用"宝贝"tab 近似映射
                # 为什么放在循环内而非循环后：tabItem 顺序不固定，逐个尝试最稳妥
                if on_sale == 0:
                    on_sale = _parse_single_tab_count(text, "宝贝", on_sale)
        except Exception as e:
            logger.debug(f"tabItem 文本提取失败: {e}")
        return on_sale, sold

    async def _dump_seller_dom_for_debug(
        self, page: Page, seller_id: str, on_sale: int, sold: int
    ) -> None:
        """P2 调试：将卖家主页 body innerText dump 到日志文件

        每个 seller_id 只 dump 一次，避免同一卖家反复失败时产生大量日志。
        选择器失效时人工查看 dump 文件可快速定位新的 className。
        """
        try:
            body_text = await page.evaluate(
                "() => document.body ? document.body.innerText : ''"
            )
            dump_path = Path("logs") / f"seller_dom_{seller_id}.txt"
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(body_text, encoding="utf-8")
            _DUMPED_SELLER_IDS.add(seller_id)
            logger.warning(
                "[P2 调试] 卖家 {} 提取异常（on_sale={}, sold={}）已 dump 到 {}",
                seller_id, on_sale, sold, dump_path,
            )
        except Exception:
            pass

    async def _extract_seller_register_days(self, page: Page) -> int:
        """提取注册天数：从注册时间文本解析（如"2020-01-01注册"或"3年前注册"）"""
        register_days = 0
        try:
            el = await page.query_selector(self.selectors.SELLER_REGISTER_MAIN)
            if el:
                reg_text = (await el.inner_text()).strip()
                register_days = self._parse_register_days(reg_text)
        except Exception:
            pass
        return register_days

    async def _extract_seller_bad_review(self, page: Page) -> int:
        """提取差评数"""
        bad_review_count = 0
        try:
            el = await page.query_selector(self.selectors.SELLER_BAD_REVIEW_MAIN)
            if el:
                bad_review_count = await self._extract_count(page, self.selectors.SELLER_BAD_REVIEW_MAIN)
        except Exception:
            pass
        return bad_review_count

    def seller_profile_fallback(
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

        重构说明：将缓存 key 解析、信息合并、数据质量判断拆分为独立方法，
        降低圈复杂度（S3776）。
        """
        from xianyu_hunter.domain.seller import SellerProfile

        # 确定缓存 key（优先用详情页的 seller_id，其次用搜索结果的）
        cache_key = self._resolve_fallback_cache_key(detail, summary)

        # 检查缓存（同一卖家不重复计算）
        if cache_key and cache_key in self._seller_profile_cache:
            logger.debug("[SellerProfile降级] 命中缓存: seller_id=%s", cache_key)
            return self._seller_profile_cache[cache_key]

        # 合并 summary + detail 中的卖家信息（detail 优先级高于 summary）
        seller_id, nick, credit_score, on_sale_count, sold_count = (
            self._merge_seller_info_from_sources(summary, detail)
        )

        # 判断数据质量
        has_basic_info = self._has_basic_seller_info(
            credit_score, on_sale_count, sold_count, nick
        )

        # register_days 优先取详情页的"来闲鱼X天"（新版闲鱼卖家主页已无此字段）
        # 卖家主页未访问到且详情页也无时保持 0（真实未知）
        fallback_register_days = self._get_fallback_register_days(detail)

        result = SellerProfile(
            id=seller_id or "unknown",
            nick=nick,
            credit_score=credit_score,
            register_days=fallback_register_days,
            on_sale_count=on_sale_count,
            sold_count=sold_count,
        )

        # 写入缓存（仅对有明确 seller_id 的记录缓存）
        self._cache_fallback_profile(result, seller_id, cache_key)

        logger.info(
            "[SellerProfile降级] seller_id=%s nick=%s credit=%s on_sale=%s sold=%s 数据质量=%s",
            seller_id, nick, credit_score, on_sale_count, sold_count,
            "partial" if has_basic_info else "insufficient"
        )

        return result

    def _resolve_fallback_cache_key(
        self, detail: ItemDetail | None, summary: ItemSummary | None
    ) -> str:
        """确定缓存 key：优先用详情页的 seller_id，其次用搜索结果的

        为什么 detail 优先：详情页的 seller_id 经过详情页 DOM 校验，
        比搜索 API 返回的 seller_id 更可靠。
        """
        if detail and detail.seller_id:
            return detail.seller_id
        if summary and summary.seller_id:
            return summary.seller_id
        return ""

    def _merge_seller_info_from_sources(
        self, summary: ItemSummary | None, detail: ItemDetail | None
    ) -> tuple[str, str, int | None, int, int]:
        """合并 summary 和 detail 中的卖家信息

        优先级：detail > summary > 默认值。
        on_sale_count/sold_count 用 max 合并而非覆盖，因为两个来源可能各有部分数据。
        """
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

        return seller_id, nick, credit_score, on_sale_count, sold_count

    def _has_basic_seller_info(
        self,
        credit_score: int | None,
        on_sale_count: int,
        sold_count: int,
        nick: str,
    ) -> bool:
        """判断是否有基本卖家信息（用于日志中的数据质量标记）

        任一字段有值即视为 partial，否则为 insufficient。
        """
        return any([
            credit_score is not None and credit_score > 0,
            on_sale_count > 0,
            sold_count > 0,
            bool(nick),
        ])

    def _get_fallback_register_days(self, detail: ItemDetail | None) -> int:
        """获取 register_days：优先取详情页的"来闲鱼X天"

        新版闲鱼卖家主页已无此字段，详情页是唯一来源。
        卖家主页未访问到且详情页也无时保持 0（真实未知）。
        """
        if detail and detail.detail_register_days > 0:
            return detail.detail_register_days
        return 0

    def _cache_fallback_profile(
        self, result: "SellerProfile", seller_id: str, cache_key: str
    ) -> None:
        """写入缓存（仅对有明确 seller_id 的记录缓存）

        为什么排除 "unknown"：unknown 是无 seller_id 时的占位值，
        缓存它会导致不同无 ID 卖家共享同一缓存条目。
        """
        final_cache_key = seller_id if seller_id else cache_key
        if final_cache_key and final_cache_key != "unknown":
            self._seller_profile_cache[final_cache_key] = result

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
        m = re.search(_DIGITS_PATTERN, text)
        if m:
            return int(m.group(1))
        return 0

    @staticmethod
    def _parse_publish_time(text: str) -> datetime | None:
        """从发布时间文本解析为 datetime

        支持闲鱼详情页常见格式：
        - "刚刚" / "X秒前" / "X分钟前" / "X小时前" → 减去对应时间
        - "今天 HH:MM" / "昨天 HH:MM" → 当天/前一天 + 时间
        - "X天前" → 当前时间 - X 天
        - "YYYY-MM-DD HH:MM" / "YYYY-MM-DD" / "YYYY/MM/DD"
        - "X周前" / "X月前" / "X年前" → 估算时间

        返回带 timezone.utc 的 datetime（统一时区便于排序/比较）。
        解析失败返回 None。

        主函数只负责编排（相对时间 → 绝对时间），
        两类格式解析下沉到模块级辅助函数以降低认知复杂度（S3776）。
        """
        from datetime import datetime as _dt

        if not text:
            return None
        s = text.strip()
        if not s:
            return None

        now = _dt.now(timezone.utc)

        # 1. 相对时间（X秒前 / X分钟前 / 今天 HH:MM 等）
        relative = _parse_relative_publish_time(s, now)
        if relative is not None:
            return relative

        # 2. 绝对时间（YYYY-MM-DD HH:MM[:SS] 或纯日期）
        return _parse_absolute_publish_time(s)
