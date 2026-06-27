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

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from xianyu_hunter.domain.item import ItemDetail, ItemSummary
from xianyu_hunter.domain.seller import SellerProfile
from xianyu_hunter.domain.urls import build_item_url, build_seller_url
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.modules.collector_utils import extract_brand, parse_price_from_text

logger = get_logger()

# P2 调试：每个 seller_id 只 dump 一次 innerText，避免日志/文件爆炸
_DUMPED_SELLER_IDS: set[str] = set()
# P2 调试：每个 item_id 只 dump 一次详情页卖家链接候选，避免日志/文件爆炸
_DUMPED_ITEM_IDS: set[str] = set()
# 首页标题特征：cookie 失效后 SPA 在当前 URL 渲染首页内容，URL 不变但标题是首页标题
# 此时 URL 校验无法检测，需要通过标题内容判断
_HOME_PAGE_TITLE_MARKERS = ("闲鱼 - 闲不住", "闲鱼-闲不住", "闲不住？上闲鱼")


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
            _t0 = time.perf_counter()
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            _t_goto = time.perf_counter() - _t0
            logger.debug(f"详情页 {item_id} page.goto 耗时 {_t_goto:.2f}s")

            # 检查 HTTP 状态码：404/403/302 等异常状态提前返回 None
            if response is not None:
                http_status = response.status
                if http_status >= 400:
                    logger.warning(
                        f"详情页 {item_id} HTTP {http_status}（页面可能已下架/被限制），主动返回 None"
                    )
                    return None
                if http_status >= 300:
                    redirect_url = response.headers.get("location", "")
                    logger.warning(
                        f"详情页 {item_id} 被重定向 HTTP {http_status} → {redirect_url}，主动返回 None"
                    )
                    return None

            # 等待标题（新版闲鱼详情页已移除 h1，主选择器可能失效，
            # 用价格元素作为页面已渲染的信号更可靠）
            _t1 = time.perf_counter()
            try:
                await page.wait_for_selector(
                    self.selectors.DETAIL_TITLE_MAIN, timeout=10000
                )
            except PlaywrightTimeout:
                # 标题选择器未命中不代表页面没加载，继续尝试其他提取方式
                logger.warning(f"详情页 {item_id} 标题选择器未出现，尝试备用提取")
            _t_wait_title = time.perf_counter() - _t1
            logger.debug(f"详情页 {item_id} wait_for_selector(title) 耗时 {_t_wait_title:.2f}s")

            # 解析标题
            # 优先用 DOM 选择器，失败时依次从 og:title meta、document.title 兜底
            # og:title 是 SPA 框架（React/Vue）通用注入的 meta，不依赖业务 className
            # 当闲鱼改版导致 h1/[class*='title'] 失效时，og:title 仍可作可靠中间层
            title = ""
            for sel in [self.selectors.DETAIL_TITLE_MAIN, self.selectors.DETAIL_TITLE_ALT]:
                el = await page.query_selector(sel)
                if el:
                    title = (await el.inner_text()).strip()
                    if title:
                        break
            # 兜底1：og:title meta（SPA 通常会注入，比 document.title 更纯粹的商品标题）
            if not title:
                try:
                    og_el = await page.query_selector("meta[property='og:title']")
                    if og_el:
                        og_title = await og_el.get_attribute("content") or ""
                        og_title = og_title.strip()
                        if og_title:
                            title = og_title
                            logger.debug(f"详情页 {item_id} 标题从 og:title 兜底提取: {title}")
                except Exception as e:
                    logger.debug(f"详情页 {item_id} og:title 提取失败: {e}")
            # 兜底2：document.title（格式 "商品标题_闲鱼"，需去掉后缀）
            if not title:
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
                except Exception as e:
                    logger.warning(f"详情页 {item_id} document.title 提取失败: {e}")

            # 价格
            price = 0.0
            for sel in [self.selectors.DETAIL_PRICE_MAIN, self.selectors.DETAIL_PRICE_ALT]:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    price = parse_price_from_text(text)
                    if price > 0:
                        break

            # 描述（已用排除运费/服务条款的精细选择器）
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

            # 缩略图/主图（thumb_url）：取主图区的第一张图 src
            # 与 image_urls 区别：thumb_url 必须是详情页顶部主图，避免被推荐/广告图污染
            thumb_url = ""
            for sel in [self.selectors.DETAIL_THUMB_MAIN, self.selectors.DETAIL_THUMB_ALT]:
                thumb_el = await page.query_selector(sel)
                if thumb_el:
                    src = await thumb_el.get_attribute("src")
                    if src:
                        thumb_url = src.strip()
                        break
            # 兜底：若主图选择器都失败，从 images 列表取首张
            if not thumb_url and images:
                thumb_url = images[0]

            # 地区：选择器匹配后的 inner_text 通常是省份/城市名（如"浙江 杭州"）
            region = ""
            for sel in [self.selectors.DETAIL_REGION_MAIN, self.selectors.DETAIL_REGION_ALT]:
                region_el = await page.query_selector(sel)
                if region_el:
                    region = (await region_el.inner_text()).strip()
                    if region:
                        # 清洗：去除换行/多余空白
                        region = re.sub(r"\s+", " ", region)
                        break

            # 想要数 + 浏览数：闲鱼详情页两者共享父元素 [class*='want--']
            # DOM 结构：<div class="want--XXX"><div>45人想要</div><div>1472浏览</div></div>
            # 子元素无 class，无法单独选中，需从父元素 inner_text 中用正则分别提取
            want_cnt = 0
            view_cnt = 0
            try:
                want_parent = await page.query_selector("[class*='want--']")
                if want_parent:
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

            # 兜底：父元素提取失败时用原有选择器尝试
            if want_cnt == 0:
                for sel in [self.selectors.DETAIL_WANT_MAIN, self.selectors.DETAIL_WANT_ALT]:
                    want_cnt = await self._extract_count(page, sel)
                    if want_cnt > 0:
                        break
            if view_cnt == 0:
                for sel in [self.selectors.DETAIL_VIEW_MAIN, self.selectors.DETAIL_VIEW_ALT]:
                    view_cnt = await self._extract_count(page, sel)
                    if view_cnt > 0:
                        break

            # 发布时间：通常文本为"3天前发布"或"2024-01-01 发布"
            publish_time: datetime | None = None
            publish_time_text = ""
            for sel in [self.selectors.DETAIL_PUBLISH_TIME_MAIN, self.selectors.DETAIL_PUBLISH_TIME_ALT]:
                time_el = await page.query_selector(sel)
                if time_el:
                    text = (await time_el.inner_text()).strip()
                    if text:
                        publish_time_text = text
                        publish_time = self._parse_publish_time(text)
                        if publish_time is not None:
                            break
            # 时间解析失败的兜底：用当前时间（保证字段非空，避免评估/展示出现 None）
            if publish_time is None:
                publish_time = datetime.now(timezone.utc)

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

            # P2 调试：详情页 seller_id 提取失败时 dump 页面所有 a[href] 含 user/seller 的元素
            # 辅助人工定位新版闲鱼详情页的卖家链接真实 className/属性
            if not seller_id and item_id not in _DUMPED_ITEM_IDS:
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
                    dump_path.write_text(
                        _json.dumps(hrefs, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    _DUMPED_ITEM_IDS.add(item_id)
                    logger.warning(
                        "[P2 调试] 详情页 {} 卖家ID未提取，已 dump {} 个候选链接到 {}",
                        item_id, len(hrefs), dump_path,
                    )
                except Exception as e:
                    # 不再静默吞异常，输出错误原因便于诊断
                    logger.error("[P2 调试] 详情页 {} dump 失败: {}", item_id, e)

            # 从详情页DOM提取卖家信息（用于降级评估，避免必须访问卖家主页）
            detail_seller_nick = ""
            detail_credit_score: int | None = None
            detail_on_sale_count = 0
            detail_sold_count = 0
            detail_register_days = 0

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

            # 从详情页的卖家信息标签提取结构化数据
            # 新版闲鱼详情页在 item-user-info-label 中显示：
            # 地区 / 活跃时间 / 注册时间("来闲鱼X天"/"来闲鱼X年") / 已售数("卖出X件宝贝") / 好评率("好评率X%")
            # 关键：SPA 页面异步渲染，标题出现后这些元素可能还未渲染，需显式等待
            try:
                # 等待卖家信息标签出现（5s 超时，足够 SPA hydration 完成）
                # 不阻塞太久，超时后仍尝试提取（可能部分元素已渲染）
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
                    # 解析已售数："卖出11件宝贝"
                    m = re.search(r"卖出(\d+)件", text)
                    if m:
                        detail_sold_count = int(m.group(1))
                        continue
                    # 解析在售数："在售11件" 或 "在售11"
                    m = re.search(r"在售(\d+)", text)
                    if m:
                        detail_on_sale_count = int(m.group(1))
                        continue
                    # 解析注册天数："来闲鱼179天" / "来闲鱼3年" / "来闲鱼2个月"
                    m = re.search(r"来闲鱼(\d+)\s*天", text)
                    if m:
                        detail_register_days = int(m.group(1))
                        continue
                    m = re.search(r"来闲鱼(\d+)\s*年", text)
                    if m:
                        detail_register_days = int(m.group(1)) * 365
                        continue
                    m = re.search(r"来闲鱼(\d+)\s*个月", text)
                    if m:
                        detail_register_days = int(m.group(1)) * 30
                        continue
                    # 解析好评率："好评率100%" → 作为信用分参考（百分比数值）
                    m = re.search(r"好评率(\d+)%?", text)
                    if m:
                        detail_credit_score = int(m.group(1))
                        continue
                # 提取结果汇总日志（便于诊断字段缺失问题）
                logger.info(
                    f"详情页 {item_id} 卖家信息提取: register_days={detail_register_days}, "
                    f"sold_count={detail_sold_count}, on_sale_count={detail_on_sale_count}, "
                    f"credit_score={detail_credit_score}, nick={detail_seller_nick}"
                )
            except Exception as e:
                # 不再静默吞异常，记录错误原因便于诊断
                logger.warning(f"详情页 {item_id} 卖家信息标签提取异常: {e}")

            # P0 修复：如果核心字段（标题）未提取成功，主动返回 None 让上游感知失败
            # 避免超时后仍返回默认值，导致半残数据污染 items 表与评估结果
            if not title:
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
                return None
            # 首页标题检测：cookie 失效后闲鱼 SPA 可能在当前 URL 渲染首页内容
            # URL 校验无法检测（URL 未改变），通过标题内容判断是否为首页
            if any(marker in title for marker in _HOME_PAGE_TITLE_MARKERS):
                logger.warning(
                    f"详情页 {item_id} 提取到首页标题（title={title}），cookie 可能失效被重定向到首页，主动返回 None"
                )
                return None
            if price <= 0:
                # 价格未命中通常意味着详情页未正常加载（404/SPA 未渲染）
                logger.warning(f"详情页 {item_id} 价格提取失败（title={title}, price={price}），主动返回 None")
                return None

            # P0 增强：校验当前 URL 仍是商品页，否则视为采集失败
            # 场景：cookie 失效后 page.goto(goofish.com/item?id=...) 被闲鱼重定向到首页
            # 此时 page.url 变为 goofish.com（不带 /item），但 title 仍能取到 document.title="闲鱼 - 闲不住？上闲鱼！"
            # 之前会误把首页装饰数据当商品数据返回，污染 items 表
            try:
                current_url = page.url
                if "/item" not in current_url or f"id={item_id}" not in current_url:
                    logger.warning(
                        f"详情页 {item_id} 被重定向到非商品页（current_url={current_url}），主动返回 None"
                    )
                    return None
            except Exception:
                pass

            # 已售检测：采集页面文字，判断商品是否已售出
            # 为什么在采集侧也检测：官方采集和刷新接口复用此方法，
            # 在此检测可统一覆盖三个入口（链接刷新/官方采集/抢单前的 detail 调用）
            # 关键词覆盖"已售"两字作为兜底：与搜索 DOM 检测（text.includes('已售')）保持一致，
            # 避免闲鱼文案变体（如"该商品已售"、"宝贝已下架"等）漏检
            is_sold = False
            try:
                body_text = await page.text_content("body") or ""
                is_sold = "已售" in body_text or any(kw in body_text for kw in (
                    "已售出", "已售完", "已售罄", "宝贝已售", "商品已售",
                    "已下架", "已卖出",
                ))
            except Exception as e:  # noqa: BLE001
                # 静默失败会导致 is_sold 默认 False，已售商品被误判为在售
                # 记录 warning 便于排查页面崩溃/Playwright 异常导致的检测失败
                logger.warning("详情页 {} is_sold 检测失败: {}", item_id, e)

            # 品牌字段：详情页 DOM 通常无独立 brand 元素，复用 extract_brand 兜底链路
            # 优先级：搜索 API brand > 卖家昵称匹配标题 > 标题关键词推断
            # 为什么不在 DOM 中查找 brand 元素：闲鱼详情页 className 是哈希值，
            # 无稳定选择器；从标题/卖家昵称推断已是搜索链路的成熟兜底，复用最稳
            brand = extract_brand(None, title, seller_candidate=detail_seller_nick)

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
                detail_seller_nick=detail_seller_nick,
                detail_credit_score=detail_credit_score,
                detail_on_sale_count=detail_on_sale_count,
                detail_sold_count=detail_sold_count,
                detail_register_days=detail_register_days,
                is_sold=is_sold,
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
            # 昵称兜底：从 document.title 提取（格式："昵称_闲鱼"）
            # 新版卖家主页可能因选择器改版导致昵称为空，但 document.title 始终可用
            if not nick:
                try:
                    doc_title = await page.title()
                    if doc_title:
                        for suffix in ("_闲鱼", " - 闲鱼", " | 闲鱼"):
                            if doc_title.endswith(suffix):
                                nick = doc_title[: -len(suffix)].strip()
                                break
                except Exception:
                    pass

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
            # 新版闲鱼卖家主页用 tabItem 类，3 个 tab 文本分别为 "全部351"/"在售9"/"已售出342"
            # 旧版用 onSale/sold + count 子元素
            # 由于新版 className 是哈希化的 tabItem--HiFOTMcp，无法用 CSS 选择器区分，
            # 直接遍历 tabItem 按文本前缀匹配
            on_sale = 0
            sold = 0
            try:
                tab_texts = await page.evaluate(
                    """() => {
                        const tabs = document.querySelectorAll('[class*="tabItem"]');
                        return Array.from(tabs).map(t => (t.innerText || '').trim());
                    }"""
                )
                for text in tab_texts or []:
                    if text.startswith("在售"):
                        m = re.search(r"(\d+)", text)
                        if m:
                            on_sale = int(m.group(1))
                    elif text.startswith("已售出") or text.startswith("已售"):
                        m = re.search(r"(\d+)", text)
                        if m:
                            sold = int(m.group(1))
            except Exception as e:
                logger.debug(f"tabItem 文本提取失败: {e}")

            # 旧版兜底：新版未命中时尝试旧版选择器
            if on_sale == 0:
                on_sale = await self._extract_count(page, self.selectors.SELLER_ON_SALE_ALT)
            if sold == 0:
                sold = await self._extract_count(page, self.selectors.SELLER_SOLD_ALT)

            # P2 调试：每个 seller_id 只 dump 一次 innerText 到 logs/seller_dom_<id>.txt
            # 当 on_sale 或 sold 选择器失效时（如新版闲鱼改 className），
            # 文本含"在售 X 件"或"卖出 X 件"模式可辅助人工更新 selectors.py
            if (on_sale == 0 or sold == 0) and seller_id not in _DUMPED_SELLER_IDS:
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

        # register_days 优先取详情页的"来闲鱼X天"（新版闲鱼卖家主页已无此字段）
        # 卖家主页未访问到且详情页也无时保持 0（真实未知）
        fallback_register_days = 0
        if detail and detail.detail_register_days > 0:
            fallback_register_days = detail.detail_register_days

        result = SellerProfile(
            id=seller_id or "unknown",
            nick=nick,
            credit_score=credit_score,
            register_days=fallback_register_days,
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
        """
        from datetime import datetime as _dt, timedelta

        if not text:
            return None
        s = text.strip()
        if not s:
            return None

        now = _dt.now(timezone.utc)

        # 1. 相对时间
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

        # 2. 绝对时间：YYYY-MM-DD HH:MM[:SS] 或 YYYY/MM/DD HH:MM
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
        # 3. 纯日期：YYYY-MM-DD 或 YYYY/MM/DD
        m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
            except ValueError:
                pass

        # 解析失败
        return None
