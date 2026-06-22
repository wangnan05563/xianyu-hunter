"""搜索主流程 Mixin：关键词搜索 + API 拦截 + 实时搜索

将搜索的核心编排逻辑（含 RGV587 重试、DOM 回退、token 刷新）集中于此。
搜索流程紧密耦合 API 拦截与 DOM 解析，故保留在同一模块避免跨文件跳转。
"""
from __future__ import annotations

import asyncio
from http.cookies import CookieError, SimpleCookie
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Page

from xianyu_hunter.domain.item import ItemDetail, ItemSummary
from xianyu_hunter.domain.task import XIANYU_FILTER_MAP
from xianyu_hunter.domain.urls import (
    build_item_url,
    build_search_url,
    build_seller_url,
    get_base_url,
)
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.repo_links import task_keyword_matches_title
from xianyu_hunter.modules.collector_utils import check_item_sold, extract_seller_nick

logger = get_logger()


def _set_cookie_headers_from_response(response: Any) -> list[str]:
    """Extract Set-Cookie headers from a Playwright APIResponse."""
    headers: list[str] = []
    try:
        raw_headers = getattr(response, "headers_array", None)
        if callable(raw_headers):
            raw_headers = raw_headers()
        for h in raw_headers or []:
            if str(h.get("name", "")).lower() == "set-cookie" and h.get("value"):
                headers.append(str(h["value"]))
    except Exception:
        pass

    if headers:
        return headers

    try:
        header_map = getattr(response, "headers", None)
        if callable(header_map):
            header_map = header_map()
        for name, value in (header_map or {}).items():
            if str(name).lower() == "set-cookie" and value:
                headers.append(str(value))
    except Exception:
        pass
    return headers


def _cookies_from_set_cookie_headers(headers: list[str], response_url: str) -> list[dict[str, Any]]:
    """Convert Set-Cookie headers to Playwright add_cookies() payloads."""
    parsed = urlparse(response_url or "")
    origin = f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else ""
    cookies: list[dict[str, Any]] = []

    for header in headers:
        jar = SimpleCookie()
        try:
            jar.load(header)
        except CookieError:
            continue
        for morsel in jar.values():
            cookie: dict[str, Any] = {
                "name": morsel.key,
                "value": morsel.value,
                "path": morsel["path"] or "/",
            }
            domain = morsel["domain"]
            if domain:
                cookie["domain"] = domain
            elif origin:
                cookie["url"] = origin
            else:
                continue

            if morsel["secure"]:
                cookie["secure"] = True
            if morsel["httponly"]:
                cookie["httpOnly"] = True
            same_site = (morsel["samesite"] or "").lower()
            if same_site in {"lax", "strict", "none"}:
                cookie["sameSite"] = {"lax": "Lax", "strict": "Strict", "none": "None"}[same_site]
            cookies.append(cookie)
    return cookies


async def _sync_response_cookies_to_context(page: Page, response: Any) -> int:
    """Persist MTOP Set-Cookie headers seen via route.fetch() into the browser context."""
    headers = _set_cookie_headers_from_response(response)
    if not headers:
        return 0
    cookies = _cookies_from_set_cookie_headers(headers, getattr(response, "url", ""))
    if not cookies:
        return 0
    await page.context.add_cookies(cookies)
    logger.info(
        "已同步 MTOP Set-Cookie 到浏览器上下文: %s",
        sorted({c["name"] for c in cookies}),
    )
    return len(cookies)

# 批量解析脚本：在浏览器中一次性提取所有搜索卡片的商品数据
# 替代逐个 query_selector 的串行模式，将 150+ 次 DOM 往返压缩为 1 次 evaluate 调用
_BATCH_PARSE_SCRIPT = r"""
() => {
  const cards = document.querySelectorAll(
    "[class*='feeds-item-wrap'], [class*='feeds-item']"
  );
  const results = [];
  cards.forEach(card => {
    try {
      // 链接与商品ID
      const link = card.tagName === 'A' ? card : card.querySelector('a');
      if (!link) return;
      const href = link.getAttribute('href') || '';
      const idMatch = href.match(/id=(\d+)/) || href.match(/\/(\d{6,})/);
      if (!idMatch) return;
      const id = idMatch[1];

      // 标题
      let title = '';
      for (const sel of ['[class*="title"]', '[class*="name"]', '.title', '.name']) {
        const el = card.querySelector(sel);
        if (el) { title = el.innerText.trim(); if (title) break; }
      }

      // 价格
      let price = 0;
      for (const sel of ['[class*="price"]', '.price']) {
        const el = card.querySelector(sel);
        if (el) {
          const m = el.innerText.match(/[\d.]+/);
          if (m) { price = parseFloat(m[0]); if (price > 0) break; }
        }
      }

      // 缩略图：优先 src，回退 data-src（懒加载）
      let thumb = '';
      const img = card.querySelector('img');
      if (img) {
        for (const attr of ['src', 'data-src', 'data-original', 'data-lazy-src']) {
          thumb = img.getAttribute(attr) || '';
          if (thumb && !thumb.startsWith('data:')) break;
        }
      }

      // 卖家ID：从卖家链接 URL 中提取
      let sellerId = '';
      const sellerLinks = card.querySelectorAll('a[href*="userId"], a[href*="personal"], a[href*="shop"]');
      for (const sl of sellerLinks) {
        const slHref = sl.getAttribute('href') || '';
        const sidMatch = slHref.match(/[?&]userId=(\w+)/) || slHref.match(/[?&]sellerId=(\w+)/);
        if (sidMatch) { sellerId = sidMatch[1]; break; }
      }
      // 兜底：从 data 属性提取 sellerId
      if (!sellerId) {
        const sellerEl = card.querySelector('[data-userid], [data-sellerid], [data-seller-id]');
        if (sellerEl) {
          sellerId = sellerEl.getAttribute('data-userid') || sellerEl.getAttribute('data-sellerid') || sellerEl.getAttribute('data-seller-id') || '';
        }
      }

      // 按段落分割卡片文本：闲鱼格式通常为
      // [标题, 价格, x人想要, 地区, 卖家昵称, 卖家信用度, ...]
      const paragraphs = card.innerText.split(/[\n\r]+/).map(s => s.trim()).filter(Boolean);

      // 地区：精确选择器 + 从段落中匹配"2-4字中文"的省份/城市
      let region = '';
      for (const sel of ['[class*="seller-left"]', '[class*="sellerLocation"]', '[class*="areaName"]', '[class*="userArea"]', '[class*="area-name"]', '[class*="region-name"]', '[class*="location"]']) {
        const el = card.querySelector(sel);
        if (el && el.innerText.trim()) { region = el.innerText.trim(); break; }
      }
      // 兜底1：从段落中匹配"xx·xx"格式（如"河北·唐山"）
      if (!region) {
        for (const p of paragraphs) {
          const m = p.match(/([\u4e00-\u9fa5]{2,4})\s*[·•]\s*([\u4e00-\u9fa5]{2,4})/);
          if (m) { region = m[0]; break; }
        }
      }
      // 兜底2：从段落中找 2-4 字中文地区（排除标题、价格等）
      if (!region) {
        // 跳过包含 ¥、数字、英文的段落
        for (const p of paragraphs) {
          if (/[¥\d]|想要|已售|信用|极好|良好/.test(p)) continue;
          if (/^[\u4e00-\u9fa5]{2,4}$/.test(p) && !['万', '千', '全新', '包邮', '急售', '秒发', '正品'].includes(p)) {
            region = p; break;
          }
        }
      }

      // 卖家昵称：精确选择器 + 段落中找非地区非信用的中文文本
      let sellerNick = '';
      for (const sel of ['[class*="sellerName"]', '[class*="userNick"]', '[class*="nickName"]', '[class*="userName"]', '[class*="user-nick"]', '[class*="seller-right"]']) {
        const el = card.querySelector(sel);
        if (el && el.innerText.trim()) { sellerNick = el.innerText.trim(); break; }
      }
      if (!sellerNick) {
        // 兜底：从段落中找非地区、非信用、非价格、非发布时间描述的卖家昵称
        // 闲鱼卡片段落可能包含"一周内发布"、"3天前发布"等时间描述，
        // 这些文本是纯中文且长度 2-12，会被误认为昵称，必须显式排除
        // 同时支持脱敏昵称：闲鱼 API 返回的昵称常是"嘟***子"格式（含 *），
        // 之前的纯中文正则不识别，导致 sellerNick 兜底失败被清空
        const maskedNick = /^[\u4e00-\u9fa5*]+\*{2,}[\u4e00-\u9fa5*]*$/.test;  // 模式：脱敏昵称如"嘟***子"
        for (const p of paragraphs) {
          if (p === region) continue;
          if (/[¥]|想要|已售|信用|极好|良好|\d+\s*人/.test(p)) continue;
          // 排除发布时间描述：含"发布"、"X天前"、"X小时前"、"X分钟前"等
          if (/发布|分钟前|小时前|天前|周前|月前|刚发/.test(p)) continue;
          // 排除商品成色描述（"几乎全新"、"全新"、"9成新"等）
          if (/几乎全新|^全新$|^充新$|\d{1,2}新|\d成新/.test(p)) continue;
          // 排除交易描述（"急售"、"包邮"、"秒发"等）
          if (/急售|包邮|秒发|正品|自提|议价|小刀|大刀/.test(p)) continue;
          // 排除商品描述片段（"功能完好无维修"、"直接拍不议价"等）
          // 闲鱼 DOM 提取时标题/描述文本可能被截取为段落，误当昵称
          if (/功能完好|无损|无维修|拆机|原装|配件|直接拍|不议价|不退|非诚勿扰|喜欢可以|需要|感兴趣/.test(p)) continue;
          if (/^[\u4e00-\u9fa5]+$/.test(p) && p.length >= 2 && p.length <= 12) {
            sellerNick = p; break;
          }
          // 脱敏昵称：以中文开头、含 2+ 个 *、以中文或 * 结尾
          if (maskedNick(p) && p.length >= 3 && p.length <= 20) {
            sellerNick = p; break;
          }
        }
      }

      // 卖家信用度：精确选择器 + 段落中找"极好/良好/优秀"等
      let sellerCredit = '';
      for (const sel of ['[class*="credit"]', '[class*="honor"]', '[class*="user-credit"]', '[class*="reputation"]']) {
        const el = card.querySelector(sel);
        if (el && el.innerText.trim()) { sellerCredit = el.innerText.trim(); break; }
      }
      if (!sellerCredit) {
        for (const p of paragraphs) {
          if (/信用|极好|良好|优秀|信誉/.test(p)) { sellerCredit = p; break; }
        }
      }

      // 发布时间：从卡片文本中提取
      let publishTime = null;
      const text = card.innerText || '';
      const timeMatch = text.match(/(\d+)\s*小时前/) || text.match(/(\d+)\s*天前/) || text.match(/(\d+)\s*分钟前/);
      if (timeMatch) {
        const num = parseInt(timeMatch[1]);
        const unit = timeMatch[0].includes('小时') ? 'hours' : timeMatch[0].includes('天') ? 'days' : 'minutes';
        const dt = new Date(Date.now());
        if (unit === 'hours') dt.setHours(dt.getHours() - num);
        else if (unit === 'days') dt.setDate(dt.getDate() - num);
        else dt.setMinutes(dt.getMinutes() - num);
        publishTime = dt.toISOString();
      }

      // 想要数：扩展匹配格式
      let wantCnt = 0;
      const wantMatch = text.match(/(\d+)\s*人想要/) || text.match(/(\d+)\s*想要/) || text.match(/想要\s*(\d+)/);
      if (wantMatch) wantCnt = parseInt(wantMatch[1]);

      // 已售检测
      const isSold = text.includes('已售') ||
        /sold|sold-out|offline|dealed/i.test(card.className || '');

      results.push({
        id, title, price, thumb, region, want_cnt: wantCnt, is_sold: isSold,
        seller_id: sellerId, seller_nick: sellerNick, seller_credit: sellerCredit,
        publish_time: publishTime,
      });
    } catch(e) { /* 跳过解析失败的卡片 */ }
  });
  return results;
}
"""


class SearchMixin:
    """搜索主流程 Mixin

    依赖 CollectorBase 的状态（browser/ad/_browser_lock/_seller_nicks 等）
    以及 ParserMixin 的解析方法（_find_cards/_parse_card/_parse_search_api_result 等）。
    """

    # 搜索 API 精确匹配的端点路径（避免误匹配 shade/activate 等子 API）
    _SEARCH_API_PATH = "mtop.taobao.idlemtopsearch.pc.search/1.0"

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
        sort_type: str = "default",
        regions: str = "",
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
            sort_type: 排序方式（default/newest/price_asc/price_desc/want_count）
            regions: 地区过滤（逗号分隔，空字符串表示全国）

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
            url = build_search_url(keyword, filter_params=filter_params, sort_type=sort_type, regions=regions)
            logger.info(f"搜索: {url}")
            await self.ad.throttle()

            # 快速模式跳过 token 刷新——Worker 调度器会定期刷新，无需每次实时搜索都刷新
            if not fast:
                await self._ensure_fresh_m5tk(page)

            # 优先通过 route 拦截捕获 API 响应获取结构化数据
            api_items, session_invalid = await self._call_search_api(page, keyword, max_pages, fast=fast, skip_rgv587_retry=skip_rgv587_retry, sort_type=sort_type, regions=regions)
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
                            # 检测到卡片说明页面正常渲染了搜索结果，会话实际有效
                            # 重置 session_invalid 标志，避免 live_links 误报"令牌过期"
                            # 即使后续解析提取到 0 个商品（DOM 选择器失效或关键词过滤），也不应判定为会话失效
                            if session_invalid:
                                self.last_session_invalid = False
                                logger.info("DOM 回退检测到卡片，重置会话失效标志")
                            cards = await asyncio.wait_for(self._find_cards(page), timeout=8.0)
                except asyncio.TimeoutError:
                    logger.warning("DOM 回退查找卡片超时，放弃: keyword={}", keyword)
                    cards = []
                except Exception as e:
                    logger.warning("DOM 回退异常: {}", str(e)[:80])
                    cards = []
                if cards:
                    logger.info("DOM 解析发现 {} 个卡片", len(cards))
                    # 批量提取：用 page.evaluate 一次性获取所有卡片数据，替代逐个 query_selector
                    # 将 150+ 次 DOM 往返减少到 1 次，性能提升 10 倍以上
                    try:
                        batch_data = await asyncio.wait_for(
                            page.evaluate(_BATCH_PARSE_SCRIPT),
                            timeout=10.0,
                        )
                    except asyncio.TimeoutError:
                        logger.warning("DOM 批量解析超时，回退到逐个解析")
                        batch_data = []
                    except Exception as e:
                        logger.warning("DOM 批量解析异常: {}", str(e)[:80])
                        batch_data = []

                    filtered_out = []
                    if batch_data:
                        logger.info("DOM 批量解析提取到 {} 条数据", len(batch_data))
                        for d in batch_data:
                            item_id = d.get("id", "")
                            if not item_id or any(i.id == item_id for i in items):
                                continue
                            title = d.get("title", "")
                            # 关键词过滤（与逐个解析逻辑一致）
                            if keyword and title and not task_keyword_matches_title(keyword, title):
                                filtered_out.append(title[:50])
                                continue
                            thumb = d.get("thumb", "")
                            if thumb and thumb.startswith("//"):
                                thumb = "https:" + thumb
                            # 发布时间：DOM 脚本返回 ISO 字符串，需转为 datetime
                            pt_str = d.get("publish_time")
                            pt_val = None
                            if pt_str:
                                try:
                                    pt_val = datetime.fromisoformat(pt_str.replace('Z', '+00:00'))
                                except Exception:
                                    pass
                            items.append(ItemSummary(
                                id=item_id,
                                title=title,
                                price=float(d.get("price", 0) or 0),
                                thumb_url=thumb,
                                region=d.get("region", ""),
                                is_sold=d.get("is_sold", False),
                                want_cnt=int(d.get("want_cnt", 0) or 0),
                                seller_id=d.get("seller_id", "") or "",
                                seller_nick=d.get("seller_nick", "") or "",
                                seller_credit=d.get("seller_credit", "") or "",
                                publish_time=pt_val,
                            ))
                    else:
                        # 批量提取失败时回退到逐个解析
                        for card in cards:
                            summary = await self._parse_card(card)
                            if summary and summary.id and not any(i.id == summary.id for i in items):
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

    async def _call_search_api(self, page: Page, keyword: str, max_pages: int = 3, fast: bool = False, skip_rgv587_retry: bool = False, sort_type: str = "default", regions: str = "") -> tuple[list[ItemSummary], bool]:
        """通过 Playwright route 拦截捕获搜索 API 响应

        页面加载时会自然发起 mtop API 请求获取搜索结果。
        通过 route 拦截这些请求并捕获响应，绕过 CORS 限制。
        比 JS fetch 方式更可靠，因为使用的是页面自身的请求上下文。

        Args:
            fast: 快速模式——RGV587 时不重试、减少等待时间（8秒 vs 15秒）
            skip_rgv587_retry: 跳过 RGV587 重试（Worker 用，避免 75 秒重试占用 browser_lock）
            sort_type: 排序方式（default/newest/price_asc/price_desc/want_count）
            regions: 地区过滤（逗号分隔，空字符串表示全国）

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
                    await _sync_response_cookies_to_context(page, response)
                    body = await response.json()
                    ret = body.get("ret", [])
                    if ret and isinstance(ret, list):
                        ret_str = str(ret[0]) if ret else ""
                        # 会话失效判定：RGV587_ERROR 或 token 非法/过期
                        # FAIL_SYS_TOKEN_ILLEGAL 表示 _m_h5_tk 令牌非法，与 RGV587 同属会话过期
                        token_invalid = any(
                            keyword in ret_str
                            for keyword in (
                                "RGV587",
                                "TOKEN_EMPTY",
                                "TOKEN_ILLEGAL",
                                "TOKEN_EXPIRED",
                                "TOKEN_INVALID",
                                "SYS_ILLEGAL_ACCESS",
                            )
                        )
                        if token_invalid:
                            # 会话失效／反爬检测／token 过期，非普通限流
                            # 此时闲鱼要求重新登录，DOM 回退也无法获取搜索结果
                            logger.warning(
                                "搜索 API 会话失效 (%s)，需重新登录闲鱼: keyword=%s",
                                ret_str[:60], keyword,
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
            url = build_search_url(keyword, sort_type=sort_type, regions=regions)
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
                        # 闲鱼 resultList 元素将商品字段包裹在 data 子字典中
                        # 检查 data 子字典是否包含商品标识字段
                        if "data" in raw and isinstance(raw["data"], dict):
                            sub = raw["data"]
                            # 闲鱼 API 结构：resultList 元素 = {data: {item: {...}, template, templateSingle}, style, type}
                            # data.item 可能是 dict（商品字段集合）或字符串（HTML 模板）
                            # 递归查找 data 子字典中包含商品标识字段的 dict
                            found_item = None
                            for _k, _v in sub.items():
                                if isinstance(_v, dict) and any(
                                    k in _v for k in ("itemId", "id", "item_id", "auctionId", "title", "price")
                                ):
                                    found_item = _v
                                    break
                            if found_item:
                                raw = found_item
                            elif not any(k in raw for k in ("itemId", "id", "title", "price")):
                                # raw 本身不含商品字段，使用 data 子字典
                                # 记录 data 子字典中每个 key 的 value 类型，便于排查商品字段位置
                                _type_info = {k: type(v).__name__ for k, v in sub.items()}
                                logger.info("resultList data 子字典 keys={}, value_types={}", list(sub.keys())[:20], _type_info)
                                raw = sub
                        # 提取卖家昵称和地区（委托到 collector_utils，处理 region 误存为 nick 的情况）
                        # 调试日志：记录 API 原始字段值，便于排查字段错位
                        _raw_nick = raw.get("userNick") or raw.get("sellerNick") or raw.get("nick") or ""
                        _raw_region_val = raw.get("region", "")
                        if _raw_nick or _raw_region_val:
                            logger.debug(
                                "商品 {} 原始字段 userNick={!r} region={!r}",
                                raw.get("itemId", "?"), _raw_nick, _raw_region_val,
                            )
                        nick, _raw_region = extract_seller_nick(raw)
                        # 闲鱼 API 可能用不同字段名返回卖家ID和发布时间
                        # 方案B改进：扩展字段路径，覆盖闲鱼API各种命名风格
                        seller_info = raw.get("sellerInfo")
                        seller_id = str(
                            raw.get("sellerId") or raw.get("userId") or raw.get("sellerIdNum")
                            or raw.get("sellerOpenId") or raw.get("openId") or raw.get("openUid")
                            or raw.get("sellerOpenUid") or raw.get("userIdStr")
                            or raw.get("sellerUserId") or raw.get("shopId")
                            or (seller_info.get("sellerId", "") if isinstance(seller_info, dict) else "")
                            or ""
                        )
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
                        # 闲鱼搜索API可能返回多个价格字段，优先取实际售价（promoPrice），
                        # 其次取 price，最后取 originalPrice，确保与详情页一致
                        # 调试日志：记录所有价格相关字段，便于排查价格不一致问题
                        price_fields = {k: raw.get(k) for k in raw if "price" in k.lower() or "Price" in k}
                        if price_fields:
                            logger.debug(f"商品 {raw.get('itemId', '?')} 价格字段: {price_fields}")
                        price_val = (
                            raw.get("promoPrice")
                            or raw.get("promotionPrice")
                            or raw.get("price")
                            or raw.get("originalPrice")
                            or 0
                        )
                        # 价格可能是字符串（如 "693.00"）或数字
                        try:
                            price = float(price_val)
                        except (TypeError, ValueError):
                            price = 0.0
                        item = ItemSummary(
                            id=str(raw.get("itemId", "")),
                            title=raw.get("title", ""),
                            price=price,
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

    async def live_search(
        self,
        keyword: str,
        max_pages: int = 2,
        page: Page | None = None,
        collect_sellers: bool = True,
        max_seller_details: int = 5,
        fast: bool = False,
        search_filters: list[str] | None = None,
        sort_type: str = "default",
        regions: str = "",
    ) -> list[dict]:
        """实时搜索并返回前端可直接展示的结果（不经过数据库）

        返回格式与 task_links 列表 API 兼容，前端无需修改渲染逻辑。

        搜索结果卡片不含卖家ID，仅有所在地。因此需要访问详情页获取卖家ID：
        - collect_sellers=True 时，访问前 max_seller_details 个商品的详情页提取卖家ID
        - 此操作会显著增加耗时（每个详情页约 3-5 秒），但能获取真实卖家数据

        Args:
            fast: 快速模式——跳过 token 刷新、RGV587 时不重试、减少等待时间
            search_filters: 闲鱼筛选标签（如 personal_idle, free_shipping）
            sort_type: 排序方式（default/newest/price_asc/price_desc/want_count）
            regions: 地区过滤（逗号分隔，空字符串表示全国）
        """
        items = await self.search(keyword, max_pages=max_pages, page=page, fast=fast, skip_lock=True, search_filters=search_filters, sort_type=sort_type, regions=regions)
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
                "seller_credit": getattr(item, "seller_credit", ""),
                "want_cnt": getattr(item, "want_cnt", 0),
                "view_cnt": getattr(item, "view_cnt", 0),
                "publish_time": getattr(item, "publish_time", None).isoformat() if getattr(item, "publish_time", None) else None,
            }
            # item 类型（url 已可由前端从 item_id 自动拼接，无需单独存储）
            results.append({**base, "link_type": "item", "link_key": item.id})
            # 搜索 API 已返回 seller_id 时直接收集，无需访问详情页
            # seller 行的字段结构必须与 item 行对称（同一份前端表格渲染），
            # 否则会出现"卖家"列与"发布时间"列错位显示同一 seller_credit 的问题
            if getattr(item, "seller_id", None) and item.seller_id not in sellers_from_search:
                item_seller_credit = getattr(item, "seller_credit", "") or ""
                item_publish_time = getattr(item, "publish_time", None)
                sellers_from_search[item.seller_id] = {
                    "item_id": item.id,
                    "title": seller_nick or f"卖家 {item.seller_id}",
                    "price": None,
                    "thumb_url": "",
                    "region": item.region,
                    "url": build_seller_url(item.seller_id),
                    "is_sold": False,
                    "publish_time": item_publish_time.isoformat() if item_publish_time else None,
                    "seller_id": item.seller_id,
                    "seller_nick": seller_nick,
                    "seller_credit": item_seller_credit,
                    "want_cnt": 0,
                    "view_cnt": 0,
                    "link_type": "seller",
                    "link_key": item.seller_id,
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
                            # seller 行的 display 字段需要与 item 行对称，
                            # 避免前端表格"卖家"列与"发布时间"列错位渲染
                            results.append({
                                "item_id": item.id,
                                "title": f"卖家 {detail.seller_id}",
                                "price": None,
                                "thumb_url": "",
                                "region": item.region,
                                "url": build_seller_url(detail.seller_id),
                                "is_sold": False,
                                "publish_time": None,
                                "seller_id": detail.seller_id,
                                "seller_nick": "",
                                "seller_credit": "",
                                "want_cnt": 0,
                                "view_cnt": 0,
                                "link_type": "seller",
                                "link_key": detail.seller_id,
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
