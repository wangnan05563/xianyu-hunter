"""搜索主流程 Mixin：关键词搜索 + API 拦截 + 实时搜索

将搜索的核心编排逻辑（含 RGV587 重试、DOM 回退、token 刷新）集中于此。
搜索流程紧密耦合 API 拦截与 DOM 解析，故保留在同一模块避免跨文件跳转。
"""
from __future__ import annotations

import asyncio
from http.cookies import CookieError, SimpleCookie
import re
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
from xianyu_hunter.modules.collector_utils import check_item_sold, extract_brand, extract_seller_nick

logger = get_logger()

_ITEM_ID_KEYS = ("itemId", "item_id", "auctionId", "auction_id", "itemID", "id")
_TITLE_KEYS = ("title", "itemTitle", "item_title", "name", "subject")
# 优先取当前挂牌价 price（与官网展示一致），促销价作为兜底
# 为什么调整：promoPrice 是促销价（可能临时降价），官网展示的是 price（挂牌价），
# 两者不一致会导致用户点击跳转后看到不同金额
_PRICE_KEYS = ("price", "promoPrice", "promotionPrice", "soldPrice", "originalPrice")
_THUMB_KEYS = ("picUrl", "mainPicUrl", "pic", "imageUrl", "mainPic", "cover", "pic_url")
_SELLER_ID_KEYS = (
    "sellerId", "userId", "sellerIdNum", "sellerOpenId", "openId", "openUid",
    "sellerOpenUid", "userIdStr", "sellerUserId", "shopId",
)
_SELLER_NICK_KEYS = ("userNick", "sellerNick", "nick", "userNickname", "sellerNickName")
_REGION_KEYS = ("region", "location", "area", "city", "province", "areaName")
_PUBLISH_TIME_KEYS = ("publishTime", "gmtCreate", "publishTimeStr", "publish_time")
_WANT_KEYS = ("wantCnt", "wantCount", "want_cnt", "want")
_VIEW_KEYS = ("viewCnt", "viewCount", "view_cnt", "browseCnt")
_CREDIT_KEYS = ("sellerCredit", "seller_credit", "credit", "creditText")
_PREFERRED_NESTED_KEYS = (
    "item", "itemInfo", "itemDO", "auction", "auctionInfo", "main", "data",
    "sellerInfo", "userInfo", "ownerInfo",
)


def _normalize_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and value not in ("", None)


def _find_value_by_key(obj: Any, key: str, depth: int = 0, max_depth: int = 6) -> Any:
    if depth > max_depth:
        return None
    target = _normalize_key(key)
    if isinstance(obj, dict):
        for raw_key, value in obj.items():
            if _normalize_key(raw_key) == target and _is_scalar(value):
                return value

        preferred_values = [
            obj[k] for k in _PREFERRED_NESTED_KEYS
            if k in obj and isinstance(obj[k], (dict, list))
        ]
        other_values = [
            v for k, v in obj.items()
            if k not in _PREFERRED_NESTED_KEYS and isinstance(v, (dict, list))
        ]
        for value in preferred_values + other_values:
            found = _find_value_by_key(value, key, depth + 1, max_depth)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj[:40]:
            found = _find_value_by_key(value, key, depth + 1, max_depth)
            if found is not None:
                return found
    return None


def _first_value(obj: Any, keys: tuple[str, ...]) -> Any:
    for key in keys:
        found = _find_value_by_key(obj, key)
        if found is not None:
            return found
    return None


def _first_text(obj: Any, keys: tuple[str, ...]) -> str:
    value = _first_value(obj, keys)
    if value is None:
        return ""
    return str(value).strip()


def _coerce_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).replace(",", "").strip()
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 0


def _coerce_price(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return 0.0
    price = float(match.group())
    if "万" in text:
        price *= 10000
    return price


def _normalize_image_url(value: Any) -> str:
    if not value:
        return ""
    url = str(value).strip()
    if not url or url.startswith("data:"):
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https:" + url if url.startswith("//") else "https://" + url
    return url


def _parse_api_publish_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 10_000_000_000:
                ts /= 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        text = str(value).strip()
        if text.isdigit():
            ts = int(text)
            if ts > 10_000_000_000:
                ts /= 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if re.match(r"^\d{4}-\d{2}-\d{2}", text):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    return None


def _extract_api_item_fields(raw: dict) -> dict[str, Any]:
    """Extract item fields from current and nested Goofish search API shapes."""
    source: Any = raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), dict) else raw
    item_id = _first_text(source, _ITEM_ID_KEYS)
    title = _first_text(source, _TITLE_KEYS)

    semantic_raw = {
        "itemId": item_id,
        "title": title,
        "price": _first_value(source, _PRICE_KEYS),
        "userNick": _first_text(source, _SELLER_NICK_KEYS),
        "region": _first_text(source, _REGION_KEYS),
        "sellerId": _first_text(source, _SELLER_ID_KEYS),
        "sellerCredit": _first_text(source, _CREDIT_KEYS),
        "wantCnt": _first_value(source, _WANT_KEYS),
        "viewCnt": _first_value(source, _VIEW_KEYS),
        "publishTime": _first_value(source, _PUBLISH_TIME_KEYS),
    }
    if isinstance(source, dict):
        for key, value in source.items():
            semantic_raw.setdefault(key, value)

    # 占位图标记：闲鱼搜索 API 经常返回 1x1 透明 PNG 占位图，
    # 必须跳过否则前端显示为空白图片
    _PLACEHOLDER_MARKS = ("tps-2-2", "2-2.png", "1x1.png")
    thumb_url = ""
    for key in _THUMB_KEYS:
        candidate = _normalize_image_url(_find_value_by_key(source, key))
        # 仅当候选 URL 非空且非占位图时才赋值，避免最后一个 key 的占位图覆盖之前的空值
        if candidate and not any(mark in candidate for mark in _PLACEHOLDER_MARKS):
            thumb_url = candidate
            break

    return {
        "item_id": item_id,
        "title": title,
        "price": _coerce_price(semantic_raw["price"]),
        "thumb_url": thumb_url,
        "seller_id": semantic_raw["sellerId"],
        "want_cnt": _coerce_int(semantic_raw["wantCnt"]),
        "view_cnt": _coerce_int(semantic_raw["viewCnt"]),
        "publish_time": _parse_api_publish_time(semantic_raw["publishTime"]),
        "seller_credit": semantic_raw["sellerCredit"],
        "semantic_raw": semantic_raw,
    }


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
    """Persist MTOP Set-Cookie headers seen via route.fetch() into the browser context.

    同时将关键 cookie（_m_h5_tk / _m_h5_tk_enc 等 session 层 token）回写到 JSON，
    避免重启后浏览器从 JSON 加载旧 token 导致 session 层状态失效。
    """
    headers = _set_cookie_headers_from_response(response)
    if not headers:
        return 0
    cookies = _cookies_from_set_cookie_headers(headers, getattr(response, "url", ""))
    if not cookies:
        return 0
    await page.context.add_cookies(cookies)
    logger.info(
        "已同步 MTOP Set-Cookie 到浏览器上下文: {}",
        sorted({c["name"] for c in cookies}),
    )

    # 回写关键 cookie 到 JSON：MTOP 返回的 _m_h5_tk 等 token 会定期刷新，
    # 若不回写，重启后浏览器从 JSON 加载旧 token，导致 session 层失效、签名错误
    # 为什么只回写关键 cookie：避免全量覆盖丢失其他 cookie，且减少 JSON 写入开销
    key_cookie_names = {"_m_h5_tk", "_m_h5_tk_enc", "unb", "sgcookie", "cookie2", "lg2"}
    updates = {
        c["name"]: c["value"]
        for c in cookies
        if c.get("name") in key_cookie_names and c.get("value")
    }
    if updates:
        try:
            from xianyu_hunter.web.services.cookie_store import get_cookie_store
            get_cookie_store().update_cookie_values(updates)
        except Exception as e:
            # 为什么 warning：回写失败会导致 JSON 中 token 陈旧，下次健康检查误判 cookie 无效。
            # 此前 debug 级别导致该问题不可观测，排查困难
            logger.warning("MTOP Set-Cookie 回写 JSON 失败: {}", e)

    return len(cookies)

# 批量解析脚本：在浏览器中一次性提取所有搜索卡片的商品数据
# 替代逐个 query_selector 的串行模式，将 150+ 次 DOM 往返压缩为 1 次 evaluate 调用
_BATCH_PARSE_SCRIPT = r"""
() => {
  // 选择器必须与 _find_cards 的 card_selectors 保持一致
  // 为什么：之前只用 2 种选择器（feeds-item-wrap/feeds-item），
  // 而 _find_cards 用 6 种。闲鱼搜索页大量卡片使用 item-card/search-item/product-card 等其他 class，
  // 批量脚本与 _find_cards 不一致导致 31 个卡片只提取到 1 条
  const cards = document.querySelectorAll(
    "[class*='feeds-item-wrap'], [class*='feeds-item'], " +
    "[class*='item-card'], [class*='search-item'], " +
    "[class*='product-card'], [data-spm*='item']"
  );
  const results = [];
  cards.forEach(card => {
    try {
      // 链接与商品ID：多路径兜底
      // 为什么增加兜底：闲鱼 SPA 部分卡片用 onclick 跳转而非 <a href>，
      // 仅靠 a[href] 会导致大量卡片提取失败
      const link = card.tagName === 'A' ? card : card.querySelector('a[href*="item"], a[href*="goods"], a[href*="product"], a');
      let href = link ? (link.getAttribute('href') || '') : '';
      let id = '';
      // 优先从 URL 提取：id=xxx 或 /item/xxx 或 /数字
      let idMatch = href.match(/id=(\d+)/) || href.match(/\/item\/(\d+)/) || href.match(/\/(\d{6,})/);
      if (idMatch) {
        id = idMatch[1];
      } else {
        // 兜底1：从 data-itemid / data-id / data-spm 等属性提取
        for (const attr of ['data-itemid', 'data-id', 'data-spm', 'data-iid', 'data-aid']) {
          const v = card.getAttribute(attr) || '';
          const m = v.match(/(\d{6,})/);
          if (m) { id = m[1]; break; }
        }
      }
      // 兜底2：从 card 内部任意元素的 data-* 属性中查找商品ID
      if (!id) {
        const idEls = card.querySelectorAll('[data-itemid], [data-id], [data-iid], [data-aid], [data-spm]');
        idEls.forEach(el => {
          if (id) return;
          for (const attr of ['data-itemid', 'data-id', 'data-iid', 'data-aid', 'data-spm']) {
            const v = el.getAttribute(attr) || '';
            const m = v.match(/(\d{6,})/);
            if (m) { id = m[1]; return; }
          }
        });
      }
      // 兜底3：从 card 内部任意 <a> 的 href 中提取 ID（不限制第一个 link）
      if (!id) {
        const allLinks = card.querySelectorAll('a');
        for (let i = 0; i < allLinks.length && !id; i++) {
          const h = allLinks[i].getAttribute('href') || '';
          const m = h.match(/id=(\d+)/) || h.match(/\/item\/(\d+)/) || h.match(/\/(\d{6,})/);
          if (m) { id = m[1]; }
        }
      }
      if (!id) return;

      // 标题
      let title = '';
      for (const sel of ['[class*="title"]', '[class*="name"]', '.title', '.name']) {
        const el = card.querySelector(sel);
        if (el) { title = el.innerText.trim(); if (title) break; }
      }

      // 价格：排除原价/划线价/运费等干扰元素，支持"万"单位
      // 为什么排除：搜索卡片中可能有原价（划线）、当前价、促销价等多个含 price 的元素，
      // querySelector 取第一个匹配可能不是当前价，导致采集金额与官网不一致
      let price = 0;
      const priceSel = '[class*="price"]:not([class*="original"]):not([class*="Original"]):not([class*="postage"]):not([class*="shipping"]):not([class*="line-through"])';
      for (const sel of [priceSel, '[class*="price"]', '.price']) {
        const el = card.querySelector(sel);
        if (el) {
          let txt = el.innerText.replace(/[\s,]+/g, '');
          const m = txt.match(/\d+\.?\d*/);
          if (m) {
            price = parseFloat(m[0]);
            if (/万/.test(txt)) price *= 10000;
            if (price > 0) break;
          }
        }
      }

      // 缩略图：优先 <img> src，回退 data-src（懒加载），最后回退 background-image
      let thumb = '';
      const img = card.querySelector('img');
      if (img) {
        for (const attr of ['src', 'data-src', 'data-original', 'data-lazy-src', 'lazy-src']) {
          thumb = img.getAttribute(attr) || '';
          if (thumb && !thumb.startsWith('data:')) break;
        }
      }
      // 兜底：从 background-image 提取图片 URL（闲鱼部分卡片用 CSS 背景图而非 <img>）
      if (!thumb) {
        const bgEls = card.querySelectorAll('[style*="background-image"], [style*="background"]');
        for (const bgEl of bgEls) {
          const bgStyle = bgEl.getAttribute('style') || '';
          const bgMatch = bgStyle.match(/url\(["']?(\/\/[^"')]+)["']?\)/) || bgStyle.match(/url\(["']?(https?:\/\/[^"')]+)["']?\)/);
          if (bgMatch) { thumb = bgMatch[1]; break; }
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
    # 为什么用 ** 而非 *：Playwright glob 中 * 不跨 / 匹配，
    # 而 URL 是 https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/...
    # mtop 前面有 /h5/，用 * 无法跨 / 匹配导致 route 拦截器从未被触发
    # ** 匹配包括 / 在内的任意字符，能正确匹配跨路径的 API URL
    _SEARCH_API_ROUTE_PATTERN = f"**{_SEARCH_API_PATH}**"

    async def _ensure_fresh_m5tk(self, page: Page, force: bool = False) -> bool:
        """导航到闲鱼主页刷新 _m_h5_tk token

        _m_h5_tk 有 1 小时 TTL，过期后搜索 API 返回 RGV587_ERROR。
        访问 goofish.com 主页可触发服务端 Set-Cookie 续期。
        带 45 分钟缓存避免频繁刷新（force=True 时跳过缓存）。
        force=True 时仍有 5 分钟最小间隔，避免 RGV587 连续触发时反复打开临时页面。

        Returns:
            True 表示执行了刷新，False 表示跳过（缓存未过期）
        """
        elapsed = time.monotonic() - self._last_m5tk_refresh
        if not force:
            if elapsed < 2700:  # 45 分钟
                return False
        else:
            # force 刷新 5 分钟内不重复执行：刚刷新过的 token 不会立即过期，
            # 连续 RGV587 更可能是 Cookie 失效而非 token 过期，反复刷新无益
            if elapsed < 300:  # 5 分钟
                logger.debug("force 刷新被跳过：距上次刷新仅 {:.0f}s".format(elapsed))
                return False
        try:
            logger.debug("刷新 _m_h5_tk token: 导航到 goofish.com 主页")
            # 35 秒超时：闲鱼主页资源多，网络波动时 15-25s 可能不够
            # 为什么 35s：日志显示 36 次 token 刷新都成功（25s 内），
            # 但接近阈值的刷新在网络波动时可能超时；35s 给予足够缓冲避免连锁失效
            await page.goto(f"{get_base_url()}/", wait_until="domcontentloaded", timeout=35000)
            # 等待 Set-Cookie 响应被浏览器处理
            await asyncio.sleep(1.5)
            self._last_m5tk_refresh = time.monotonic()
            logger.info("_m_h5_tk token 已刷新")
            return True
        except Exception as e:
            logger.warning("刷新 _m_h5_tk token 失败: {}", e)
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
            # 注册外部 page，防止与 scheduler.close_all_pages 并发时被误关
            # 场景：live_search 端点调用 search() 时，主任务 run_once 可能同时清理 page
            self.browser.register_external_page(page)
        assert page is not None
        items: list[ItemSummary] = []
        # Worker 搜索时获取 browser_lock，与 live 端点互斥
        # skip_lock=True 时跳过（live 端点已在外层持有锁）
        release_lock = False
        if self._browser_lock is not None and own_page and not skip_lock:
            await self._browser_lock.acquire()
            release_lock = True
        # 性能埋点：记录搜索耗时和搜索方式（api 拦截 / dom 回退），
        # 便于后续日志分析定位性能瓶颈
        search_start = time.monotonic()
        search_via = "unknown"
        self._last_search_error = ""
        try:
            # H-06 修复：keyword 需做 URL 编码，避免 & # % % 等特殊字符破坏查询语义
            # 追加筛选标签对应的 URL 参数（映射关系见 domain/task.py XIANYU_FILTER_MAP）
            filter_params: list[str] = []
            if search_filters:
                filter_params = [XIANYU_FILTER_MAP[f] for f in search_filters if f in XIANYU_FILTER_MAP]
                if filter_params:
                    logger.info("搜索筛选参数: {}", ", ".join(search_filters))
            url = build_search_url(keyword, filter_params=filter_params, sort_type=sort_type, regions=regions)
            logger.info("搜索: {}", url)
            # 频率伪装：搜索前按对数正态分布等待，统计计数器同步累加
            # 延迟导入避免循环依赖；fast 模式仅记录统计保持抢单速度
            from xianyu_hunter.modules.login_orchestrator import get_orchestrator
            from xianyu_hunter.modules.freq_disguise import ActionType
            if not fast:
                await get_orchestrator().apply_freq_delay(ActionType.SEARCH)
            else:
                # 与 buyer.py 保持一致：频率伪装统计失败不应影响搜索主流程
                try:
                    get_orchestrator().record_freq_request(ActionType.SEARCH)
                except Exception:
                    logger.debug("fast 模式 record_freq_request 失败，忽略不影响搜索")
            await self.ad.throttle()

            # 始终检查 token 有效性（由 45 分钟缓存决定是否真正刷新）
            # 之前 fast 模式完全跳过，导致 token 过期后 RGV587 频繁触发
            # _ensure_fresh_m5tk 内部有缓存判断，未过期时直接返回 False，不增加耗时
            await self._ensure_fresh_m5tk(page)

            # 优先通过 route 拦截捕获 API 响应获取结构化数据
            api_items, session_invalid = await self._call_search_api(page, keyword, max_pages, fast=fast, skip_rgv587_retry=skip_rgv587_retry, sort_type=sort_type, regions=regions)
            # 记录会话失效状态，供 Worker 检测后暂停任务
            self.last_session_invalid = session_invalid
            if api_items:
                items = api_items
                search_via = "api"
            else:
                search_via = "dom"
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
                        # 多选择器容错：闲鱼前端可能调整 class 命名，覆盖多种历史与当前结构
                        card_selectors = (
                            "[class*='feeds-item-wrap'], [class*='feeds-item'], "
                            "[class*='item-card'], [class*='search-item'], "
                            "[class*='product-card'], [data-spm*='item']"
                        )
                        card_count = await asyncio.wait_for(
                            page.evaluate(
                                f"() => document.querySelectorAll(\"{card_selectors}\").length"
                            ),
                            timeout=5.0,
                        )
                        # 首次未检测到卡片时，等待 2 秒后重试一次（页面可能仍在异步渲染）
                        if card_count == 0:
                            await asyncio.sleep(2)
                            card_count = await asyncio.wait_for(
                                page.evaluate(
                                    f"() => document.querySelectorAll(\"{card_selectors}\").length"
                                ),
                                timeout=5.0,
                            )
                        if card_count == 0:
                            logger.info("DOM 回退: 页面无搜索卡片 (RGV587 可能阻止了渲染)")
                            cards = []
                        else:
                            logger.info("DOM 回退: 检测到 {} 个卡片，开始解析", card_count)
                            # 注意：此处不重置 session_invalid 标志
                            # 检测到卡片不等于会话有效，可能页面渲染了卡片但 API 令牌仍失效
                            # 重置时机推迟到成功提取商品后（见下方 items 非空时）
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
                            # 通过 extract_seller_nick 校验卖家昵称和地区
                            # DOM 提取的段落匹配可能将昵称和地区搞反，
                            # 复用 API 路径的校验逻辑确保字段一致性
                            dom_nick = d.get("seller_nick", "") or ""
                            dom_region = d.get("region", "") or ""
                            nick, region = extract_seller_nick({
                                "userNick": dom_nick,
                                "region": dom_region,
                            })
                            brand = extract_brand(None, title, seller_candidate=nick)
                            items.append(ItemSummary(
                                id=item_id,
                                title=title,
                                price=float(d.get("price", 0) or 0),
                                thumb_url=thumb,
                                region=region,
                                brand=brand,
                                is_sold=d.get("is_sold", False),
                                want_cnt=int(d.get("want_cnt", 0) or 0),
                                seller_id=d.get("seller_id", "") or "",
                                seller_nick=nick,
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
                    # DOM 回退成功提取到商品才重置会话失效标志：
                    # 此时页面能正常渲染搜索结果且解析有效，说明会话实际可用
                    # 如果解析到 0 个商品（选择器失效/关键词过滤），保持标志为 True，
                    # 让 live_links 触发令牌刷新重试，避免持续走 DOM 回退
                    if session_invalid and items:
                        self.last_session_invalid = False
                        logger.info("DOM 回退成功提取 {} 个商品，重置会话失效标志", len(items))
                # DOM 翻页：首屏解析后，若 max_pages > 1 则滚动加载更多屏
                # 为什么需要：DOM 回退原仅取首屏 26 条，650 元商品可能在第 2 屏
                if items and max_pages > 1:
                    seen_ids = {i.id for i in items}
                    for dom_page in range(1, max_pages):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await self.ad.human_delay(2000, 4000)
                        try:
                            batch_data = await asyncio.wait_for(
                                page.evaluate(_BATCH_PARSE_SCRIPT),
                                timeout=10.0,
                            )
                        except (asyncio.TimeoutError, Exception) as e:
                            logger.warning("DOM 翻页第 {} 屏解析失败: {}", dom_page + 1, str(e)[:80])
                            break
                        new_count = 0
                        for d in (batch_data or []):
                            item_id = d.get("id", "")
                            if not item_id or item_id in seen_ids:
                                continue
                            title = d.get("title", "")
                            if keyword and title and not task_keyword_matches_title(keyword, title):
                                continue
                            thumb = d.get("thumb", "")
                            if thumb and thumb.startswith("//"):
                                thumb = "https:" + thumb
                            pt_str = d.get("publish_time")
                            pt_val = None
                            if pt_str:
                                try:
                                    pt_val = datetime.fromisoformat(pt_str.replace('Z', '+00:00'))
                                except Exception:
                                    pass
                            dom_nick = d.get("seller_nick", "") or ""
                            dom_region = d.get("region", "") or ""
                            nick, region = extract_seller_nick({"userNick": dom_nick, "region": dom_region})
                            brand = extract_brand(None, title, seller_candidate=nick)
                            items.append(ItemSummary(
                                id=item_id,
                                title=title,
                                price=float(d.get("price", 0) or 0),
                                thumb_url=thumb,
                                region=region,
                                brand=brand,
                                is_sold=d.get("is_sold", False),
                                want_cnt=int(d.get("want_cnt", 0) or 0),
                                seller_id=d.get("seller_id", "") or "",
                                seller_nick=nick,
                                seller_credit=d.get("seller_credit", "") or "",
                                publish_time=pt_val,
                            ))
                            seen_ids.add(item_id)
                            new_count += 1
                        logger.info("DOM 翻页第 {} 屏新增 {} 个商品", dom_page + 1, new_count)
                        if new_count == 0:
                            break
                if not items:
                    logger.info("搜索无结果: {}", keyword)

            elapsed = time.monotonic() - search_start
            logger.info("搜索完成: 共 {} 个商品, 耗时 {:.1f}s, 方式={}", len(items), elapsed, search_via)
        except Exception as e:
            elapsed = time.monotonic() - search_start
            self._last_search_error = str(e)
            logger.exception("搜索失败 {}: {}, 耗时 {:.1f}s", keyword, e, elapsed)
        finally:
            if own_page:
                try:
                    self.browser.unregister_external_page(page)
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
                            "搜索 API 会话失效 ({})，需重新登录闲鱼: keyword={}",
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

        route_pattern = self._SEARCH_API_ROUTE_PATTERN
        await page.route(route_pattern, _handle_route)

        try:
            # 导航到搜索页（页面会自然发起 API 请求）
            url = build_search_url(keyword, sort_type=sort_type, regions=regions)
            # 使用 wait_until="commit"：HTTP 响应头到达即返回，不等待 SPA 水合
            # 闲鱼搜索页是 SPA，domcontentloaded 事件需等待水合完成，网络波动时易超时
            # commit 后 route 拦截器仍可捕获后续 API 请求，等待逻辑由下方轮询负责
            goto_timeout = 15000 if fast else 20000
            try:
                await page.goto(url, wait_until="commit", timeout=goto_timeout)
            except Exception as goto_err:
                # goto 超时后主动检测会话失效：闲鱼可能将失效会话重定向到登录/验证页
                # 重定向时 page.url 不再是搜索页，此时 DOM 回退也无法成功
                try:
                    current_url = page.url or ""
                except Exception:
                    current_url = ""
                # 仅当 URL 确实是 goofish.com 的非搜索页时才判定为会话失效：
                # about:blank（导航未开始）或空 URL 更可能是网络/浏览器问题，不误判
                if (
                    current_url
                    and "goofish.com" in current_url
                    and "goofish.com/search" not in current_url
                ):
                    logger.warning(
                        "goto 超时且页面已跳转至非搜索页，判定为会话失效: url={}",
                        current_url[:120],
                    )
                    session_invalid = True
                    self._last_api_captured = False
                    return items, session_invalid
                # 未跳转则重新抛出，由上层处理（可能是单纯网络慢）
                raise goto_err

            # 等待 API 响应：快速模式最多 8 秒，正常模式最多 15 秒
            wait_rounds = 8 if fast else 15
            for _ in range(wait_rounds):
                if captured_responses or session_invalid:
                    break
                await asyncio.sleep(1)
            if not captured_responses and not session_invalid:
                logger.info("搜索 API 未捕获响应，等待 {}s 后回退 DOM: keyword={}", wait_rounds, keyword)

            # 会话失效时尝试刷新 token 后重试一次
            # skip_rgv587_retry 时跳过重试（Worker 专用，避免 75 秒重试占用 browser_lock）
            # fast 模式也重试：_ensure_fresh_m5tk(force=True) 有 5 分钟最小间隔保护，
            # 不会频繁刷新；令牌失效后不重试会导致每次搜索都走 DOM 回退，性能差且易超时
            if session_invalid and not skip_rgv587_retry:
                logger.warning("搜索 API 会话失效，尝试强制刷新 _m_h5_tk 后重试: keyword={}", keyword)
                # 强制刷新 token（跳过缓存）
                refreshed = await self._ensure_fresh_m5tk(page, force=True)
                if refreshed:
                    # 重置状态，重新尝试搜索
                    session_invalid = False
                    captured_responses.clear()
                    try:
                        # 同步使用 wait_until="commit" 加速重试导航
                        await page.goto(url, wait_until="commit", timeout=20000)
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
            # 为什么用 while 而非 for：翻页后新捕获的响应需被继续处理，
            # for 循环基于原始迭代器，遍历完后不会处理新增元素
            api_page_idx = 0
            while captured_responses and api_page_idx < max_pages:
                resp = captured_responses.pop(0)
                raw_items = self._parse_search_api_result(resp)
                if not raw_items:
                    api_page_idx += 1
                    continue
                logger.info("route 拦截获取到 {} 个商品", len(raw_items))
                if raw_items:
                    # 打印第一条原始数据的所有 key，便于排查字段名
                    sample = raw_items[0]
                    logger.info("搜索API原始字段 keys={}", list(sample.keys())[:30])
                for raw in raw_items:
                    try:
                        fields = _extract_api_item_fields(raw)
                        semantic_raw = fields["semantic_raw"]
                        if not fields["item_id"] or not fields["title"]:
                            data = raw.get("data") if isinstance(raw, dict) else None
                            type_info = {k: type(v).__name__ for k, v in data.items()} if isinstance(data, dict) else {}
                            logger.debug(
                                "跳过搜索 API 条目：缺少 item_id/title, raw_keys={}, data_types={}",
                                list(raw.keys())[:20] if isinstance(raw, dict) else type(raw).__name__,
                                type_info,
                            )
                            continue
                        # 提取卖家昵称和地区（委托到 collector_utils，处理 region 误存为 nick 的情况）
                        # 调试日志：记录 API 原始字段值，便于排查字段错位
                        _raw_nick = semantic_raw.get("userNick") or semantic_raw.get("sellerNick") or semantic_raw.get("nick") or ""
                        _raw_region_val = semantic_raw.get("region", "")
                        if _raw_nick or _raw_region_val:
                            logger.debug(
                                "商品 {} 原始字段 userNick={!r} region={!r}",
                                fields["item_id"], _raw_nick, _raw_region_val,
                            )
                        nick, _raw_region = extract_seller_nick(semantic_raw)
                        brand = extract_brand(semantic_raw, fields["title"], seller_candidate=nick)
                        # 一次性构造 ItemSummary
                        item = ItemSummary(
                            id=fields["item_id"],
                            title=fields["title"],
                            price=fields["price"],
                            region=_raw_region,
                            brand=brand,
                            seller_id=fields["seller_id"],
                            seller_nick=nick or "",
                            want_cnt=fields["want_cnt"],
                            view_cnt=fields["view_cnt"],
                            thumb_url=fields["thumb_url"],
                            is_sold=check_item_sold(semantic_raw),
                            publish_time=fields["publish_time"],
                            # 尝试从搜索API提取卖家基本信息（用于降级评估）
                            seller_credit_score=self._extract_credit_from_api_raw(semantic_raw),
                            seller_on_sale_count=_coerce_int(_first_value(semantic_raw, ("onSaleCount", "itemCount"))),
                            seller_sold_count=_coerce_int(_first_value(semantic_raw, ("soldCount",))),
                        )
                        if nick and item.seller_id:
                            self._seller_nicks[item.seller_id] = nick
                        if item.id and not any(i.id == item.id for i in items):
                            items.append(item)
                    except Exception as e:
                        logger.debug("解析搜索 API 条目失败: {}", str(e)[:120])
                        continue

                # 翻页：滚动以触发更多 API 请求
                if len(raw_items) >= 20 and api_page_idx + 1 < max_pages:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await self.ad.human_delay(2000, 4000)
                    # 等待下一页 API 响应（新响应会通过 route 拦截器追加到 captured_responses）
                    for _ in range(10):
                        if captured_responses:
                            break
                        await asyncio.sleep(1)
                api_page_idx += 1

        finally:
            # 页面可能已损坏（TargetClosedError），unroute 需超时+异常保护避免卡住
            # 只解除当前搜索 API handler，避免 page.unroute("**/*") 等待页面所有路由清理。
            try:
                await asyncio.wait_for(page.unroute(route_pattern, _handle_route), timeout=1.0)
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
        search_error = getattr(self, "_last_search_error", "")
        if search_error and not items:
            raise RuntimeError(f"实时搜索采集失败: {search_error}")
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
                "brand": getattr(item, "brand", ""),
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
                    "brand": getattr(item, "brand", ""),
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
                logger.debug("live_search 从搜索结果提取卖家: {} (来自商品 {})", item.seller_id, item.id)

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
                    # 同 search()：注册外部 page 防止并发清理误关
                    self.browser.register_external_page(detail_page)
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
                                "brand": getattr(item, "brand", ""),
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
                            logger.debug("live_search 提取卖家: {} (来自商品 {})", detail.seller_id, item.id)
                    except Exception as e:
                        logger.warning(f"live_search 提取卖家失败 item={item.id}: {e}")
            finally:
                if own_page and detail_page:
                    self.browser.unregister_external_page(detail_page)
                    await detail_page.close()

        seller_count = len([r for r in results if r.get("link_type") == "seller"])
        logger.info("live_search 完成: {} 个商品, {} 个卖家, {} 条总结果", len(items), seller_count, len(results))
        return results
