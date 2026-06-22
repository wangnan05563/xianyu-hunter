"""采集器辅助工具函数

从 collector.py 提取的纯函数，无浏览器/采集器依赖，便于测试和复用。
"""
from __future__ import annotations

import re
from typing import Any

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


def extract_item_id(href: str) -> str:
    """从 URL 中提取商品 ID

    支持格式：
    - /item?id=123456
    - /item/123456
    - ?itemId=123456
    """
    if not href:
        return ""
    m = re.search(r"(?:itemId|id)=(\d+)", href)
    if m:
        return m.group(1)
    m = re.search(r"/item/(\d+)", href)
    if m:
        return m.group(1)
    return ""


def check_item_sold(raw: dict) -> bool:
    """从 API 响应中检测商品是否已售出

    闲鱼搜索 API 返回的数据中可能包含以下已售标识：
    - status: "sold" 或 "offline"
    - soldOut: true
    - itemStatus: 2 (已售)
    """
    if not raw:
        return False
    status = str(raw.get("status", "")).lower()
    if status in ("sold", "offline", "已售", "下架"):
        return True
    if raw.get("soldOut") or raw.get("sold_out") or raw.get("isSold"):
        return True
    item_status = raw.get("itemStatus", raw.get("item_status"))
    if item_status is not None and int(item_status) == 2:
        return True
    return False


def parse_price_from_text(text: str) -> float:
    """从文本中提取价格数字"""
    m = re.search(r"\d+\.?\d*", text.replace(",", ""))
    return float(m.group()) if m else 0.0


# 中国地名正则：用于判断 region 字段是否为真实地名
# 闲鱼 API 的 region 通常是"浙江"、"浙江杭州"格式
_REGION_PATTERN = re.compile(
    # 含行政区划后缀（省/市/区/县等）
    r'.*(?:省|市|自治区|特别行政区|盟|地区|县|旗|区|镇)$|'
    # 以省份/直辖市/特别行政区名开头
    r'^(?:北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆|香港|澳门|台湾|内蒙古)'
)


def is_region_like(text: str) -> bool:
    """判断文本是否像中国地名（省份/直辖市开头或含行政区划后缀）"""
    if not text:
        return False
    return bool(_REGION_PATTERN.match(text))


def extract_seller_nick(raw: dict) -> tuple[str, str]:
    """从搜索 API 响应中提取卖家昵称和地区

    闲鱼搜索 API 在不同商品上的字段语义并不稳定，至少观察到两种异常：

    1. region 字段实际是用户昵称（如"芯***鱼"），无独立 nick 字段
       → 表现为"地区"列显示脱敏昵称，"卖家"列空
    2. userNick/sellerNick 字段实际是发布时间描述（如"一周内发布"），
       region 字段才是真实昵称
       → 表现为"卖家"列显示"一周内发布"，"地区"列显示脱敏昵称

    这两种情况都会导致 seller/region/publish_time 三列整体错位。
    这里做两层校验：先按候选字段顺序取 nick；再对结果做语义校验，
    若 nick 看起来像时间描述/价格/标签而 region 看起来像昵称，则交换。
    """
    nick = ""
    for nk in ("userNick", "sellerNick", "nick", "userNickname", "sellerNickName"):
        v = raw.get(nk)
        if v and isinstance(v, str) and v.strip():
            nick = v.strip()
            break

    raw_region = raw.get("region", "")

    # 场景 1：nick 为空且 region 不像地名 → 把 region 当 nick
    if not nick and raw_region:
        if not is_region_like(raw_region):
            nick = raw_region.strip()
            raw_region = ""

    # 场景 2：nick 不为空但看起来不像昵称（时间描述/价格/标签），
    # 且 region 看起来像昵称 → 交换两者
    # 不依赖 _looks_like_nick 的绝对判断，而是双向校验：
    # - nick 命中"非昵称"关键词 + region 不像地名 + 长度看起来像昵称 → 交换
    if nick and raw_region:
        if _looks_like_publish_label(nick) and not is_region_like(raw_region) and _looks_like_nick(raw_region):
            nick, raw_region = raw_region, nick

    return nick, raw_region


# 闲鱼搜索结果中常混入"非昵称"字段的关键词：
# - 时间描述：N分钟/小时/天/周/月前发布
# - 价格标签：含 ¥、元
# - 通用标签：包邮、已售、信用、极好、良好、优秀
# - 商品成色描述：几乎全新 / 全新 / 充新 / 99新 / 9X新 / X成新（这些是描述商品状态的标签，不应作为昵称）
# - 交易描述：急售、秒发、正品、自提、议价、小刀
# - 商品描述片段：功能/完好/无损/维修/拆机/原装/配件/直接拍/不议价等
#   （闲鱼 DOM 提取时，标题或描述文本可能被误截取为 seller_nick 段落，
#    如"功能完好无维修"、"直接拍不议价"等，这些不是昵称）
_NON_NICK_PATTERN = re.compile(
    r"(?:分钟前|小时前|天前|周前|月前|前发布|内发布|包邮|已售|信用|极好|良好|优秀|¥|元"
    r"|几乎全新|^全新$|^充新$|\d{1,2}新|\d成新|\d\.\d成新"
    r"|急售|秒发|正品|自提|议价|小刀|大刀"
    r"|功能完好|无损|无维修|拆机|原装|配件"
    r"|直接拍|不议价|不退|非诚勿扰|喜欢可以"
    r"|需要|想要|感兴趣)"
)

# 闲鱼脱敏昵称的典型模式：1-2个汉字 + 至少2个* + 1-2个汉字
_MASKED_NICK_PATTERN = re.compile(
    r"^[\u4e00-\u9fa5A-Za-z0-9_]{1,3}\*{2,}[\u4e00-\u9fa5A-Za-z0-9_]*$"
)


def _looks_like_publish_label(text: str) -> bool:
    """判断文本是否是发布时间/价格/标签描述（不应该是昵称）"""
    if not text:
        return False
    return bool(_NON_NICK_PATTERN.search(text))


def _looks_like_nick(text: str) -> bool:
    """判断文本是否像昵称（含被脱敏的"x***y"格式）"""
    if not text:
        return False
    # 脱敏昵称：芯***鱼 / 买***家 / 数码***爱好者
    if _MASKED_NICK_PATTERN.match(text):
        return True
    # 短字符串（2-20 字符），无明显时间/价格关键词
    if 2 <= len(text) <= 20 and not _NON_NICK_PATTERN.search(text):
        return True
    return False


# 信用度关键词：闲鱼 API 返回的卖家信用度通常是"极好/良好/优秀/信誉极好"等
_CREDIT_PATTERN = re.compile(r"(?:信用|极好|良好|优秀|信誉)")


def _looks_like_credit(text: str) -> bool:
    """判断文本是否像信用度描述"""
    if not text:
        return False
    return bool(_CREDIT_PATTERN.search(text))


# 发布时间描述：闲鱼 API 可能返回"X天前发布"、"一周内发布"等时间描述
_PUBLISH_LABEL_PATTERN = re.compile(
    r"(?:\d+\s*(?:分钟|小时|天|周|月)前|一周内|\d+\s*天内|刚发|前发布|内发布)"
)


def _looks_like_publish_time(text: str) -> bool:
    """判断文本是否像发布时间描述（相对时间或 ISO 时间戳）"""
    if not text:
        return False
    # ISO 时间戳格式：2024-01-01T12:00:00
    if re.match(r"^\d{4}-\d{2}-\d{2}T", text):
        return True
    # 相对时间描述：X天前发布、一周内发布等
    return bool(_PUBLISH_LABEL_PATTERN.search(text))


# 字段元数据：描述每个字段的显示方式（标签、类型、宽度）
# 前端根据此元数据动态渲染列，当接口字段变化时前端展示自动调整
FIELD_METADATA: dict[str, dict[str, Any]] = {
    "thumb_url": {"label": "图片", "type": "image", "width": 80},
    "title": {"label": "标题", "type": "link", "width": None},
    "price": {"label": "价格", "type": "price", "width": 100},
    "seller_nick": {"label": "卖家", "type": "seller", "width": 140},
    "seller_credit": {"label": "信用", "type": "tag", "color": "green", "width": 80},
    "region": {"label": "地区", "type": "text", "width": 100},
    "want_cnt": {"label": "想要", "type": "number", "width": 70},
    "publish_time": {"label": "发布时间", "type": "datetime", "width": 160},
    "is_sold": {"label": "状态", "type": "status", "width": 80},
}


def normalize_display_fields(display: dict) -> tuple[dict, dict]:
    """对 display 字段做全面语义校正，并返回字段元数据

    闲鱼搜索 API 在不同商品上字段语义并不稳定，已观察到以下错位场景：
    1. seller_nick 字段实际是发布时间描述（如"一周内发布"），region 才是真实昵称
    2. seller_nick 字段实际是信用度描述（如"信用极好"），region 才是真实昵称
    3. region 字段实际是用户昵称（如"芯***鱼"），无独立 nick 字段
    4. publish_time 字段为空，但 seller_nick 包含时间描述

    本函数对 display 字段做全面语义校正，确保每个字段都符合其语义：
    - seller_nick 必须是昵称（不能是时间描述/价格/标签/信用度）
    - region 必须是地名（不能是昵称）
    - publish_time 必须是时间（不能是昵称或地区）
    - seller_credit 必须是信用度描述（不能是昵称）

    Args:
        display: 原始 display 字典

    Returns:
        (corrected_display, field_map)
        - corrected_display: 校正后的 display 字典
        - field_map: 字段元数据，描述每个字段的显示方式
    """
    if not isinstance(display, dict):
        return {}, {}

    corrected = dict(display)
    seller_nick = str(corrected.get("seller_nick", "") or "").strip()
    region = str(corrected.get("region", "") or "").strip()
    publish_time = str(corrected.get("publish_time", "") or "").strip()
    seller_credit = str(corrected.get("seller_credit", "") or "").strip()

    # 场景 1：seller_nick 像信用度描述，且 seller_credit 为空 → 移动到 seller_credit
    if seller_nick and not seller_credit and _looks_like_credit(seller_nick):
        seller_credit = seller_nick
        seller_nick = ""

    # 场景 2：seller_nick 像发布时间描述，且 publish_time 为空 → 移动到 publish_time
    if seller_nick and not publish_time and _looks_like_publish_time(seller_nick):
        publish_time = seller_nick
        seller_nick = ""

    # 场景 3：seller_nick 不像昵称，且 region 像昵称 → 交换
    if seller_nick and region:
        if not _looks_like_nick(seller_nick) and _looks_like_nick(region):
            # 进一步校验：seller_nick 是否像时间/信用/价格
            if _looks_like_publish_time(seller_nick) or _looks_like_credit(seller_nick) or _NON_NICK_PATTERN.search(seller_nick):
                # 如果 seller_nick 像时间且 publish_time 为空，移到 publish_time
                if _looks_like_publish_time(seller_nick) and not publish_time:
                    publish_time = seller_nick
                # 如果 seller_nick 像信用且 seller_credit 为空，移到 seller_credit
                elif _looks_like_credit(seller_nick) and not seller_credit:
                    seller_credit = seller_nick
                seller_nick = region
                region = ""

    # 场景 4：seller_nick 为空，且 region 是脱敏昵称 → 把 region 当 seller_nick
    # 只在 region 明显是脱敏昵称（如"芯***鱼"）时才交换，避免误伤简短城市名（如"杭州"、"深圳"）
    # 之前用 `not is_region_like(region) and _looks_like_nick(region)` 判断过于宽松：
    # "杭州"/"深圳" 不带行政区划后缀，is_region_like 返回 False，
    # 但 _looks_like_nick 返回 True（2-20 字符且无非昵称关键词），导致 region 被错误清空
    if not seller_nick and region:
        if _MASKED_NICK_PATTERN.match(region):
            seller_nick = region
            region = ""

    # 场景 5：region 不像地名，且 seller_nick 像地名 → 交换
    if region and seller_nick:
        if not is_region_like(region) and is_region_like(seller_nick):
            seller_nick, region = region, seller_nick

    # 场景 6：seller_nick 命中"非昵称"关键词但没有合适的归属字段 → 清空
    # 例如 seller_nick='几乎全新'/'9成新'，既不是时间也不是信用度，
    # 前面场景已尝试纠正但仍然无法识别时应清空，避免前端误显示
    # 触发条件：seller_nick 命中 _NON_NICK_PATTERN 且 region 没有有效值
    if seller_nick and _NON_NICK_PATTERN.search(seller_nick):
        if not region:
            # 无 region 可填补时，清空 seller_nick
            seller_nick = ""

    # 写回校正后的字段
    corrected["seller_nick"] = seller_nick
    corrected["region"] = region
    corrected["publish_time"] = publish_time or None
    corrected["seller_credit"] = seller_credit

    # 构建字段元数据：只包含实际有值的字段
    field_map: dict[str, dict[str, Any]] = {}
    for field, meta in FIELD_METADATA.items():
        # 字段不在 display 中时跳过（如空字典输入时 is_sold 不存在）
        if field not in corrected:
            continue
        value = corrected.get(field)
        # 判断字段是否有值（None/空字符串/空数字视为无值）
        has_value = False
        if meta["type"] == "image":
            has_value = bool(value)
        elif meta["type"] == "price":
            has_value = value is not None and value != 0
        elif meta["type"] == "number":
            has_value = value is not None
        elif meta["type"] == "status":
            # 状态字段：只要字段存在就显示（False 表示"在售"，是有效值）
            has_value = True
        else:
            has_value = bool(value)
        if has_value:
            field_map[field] = meta

    return corrected, field_map


def parse_search_api_result(result: dict) -> list[dict]:
    """解析搜索 API 返回的商品列表

    尝试多种可能的响应结构：
    - data.data.itemsList
    - data.itemsList
    - data.data.items
    以及递归搜索包含 itemId/title 的列表。
    """
    if not result or not isinstance(result, dict):
        return []

    # 尝试已知的字段路径
    data = result.get("data", result)
    if isinstance(data, dict):
        inner = data.get("data", data)
        if isinstance(inner, dict):
            for key in ("itemsList", "itemList", "items", "list", "result", "resultList"):
                items_list = inner.get(key)
                if isinstance(items_list, list) and items_list:
                    # 记录第一个元素的 keys，便于排查字段名不匹配问题
                    if isinstance(items_list[0], dict):
                        logger.info("parse_search_api_result: key='{}', count={}, sample keys={}",
                                    key, len(items_list), list(items_list[0].keys())[:20])
                    return items_list
            # 调试：记录实际响应结构（loguru 使用 {} 格式化，不是 %s）
            logger.info(
                "parse_search_api_result: inner keys={}, data keys={}, top keys={}",
                list(inner.keys())[:15], list(data.keys())[:15], list(result.keys())[:15],
            )
            # 递归搜索：在 inner 中查找包含 itemId 的列表
            found = _find_items_recursive(inner, depth=0)
            if found:
                logger.info("parse_search_api_result: 递归搜索找到 {} 个商品", len(found))
                return found
            return []
        for key in ("itemsList", "itemList", "items", "list", "result", "resultList"):
            items_list = data.get(key)
            if isinstance(items_list, list) and items_list:
                return items_list
        logger.info(
            "parse_search_api_result: data keys={}, top keys={}",
            list(data.keys())[:15] if isinstance(data, dict) else type(data).__name__,
            list(result.keys())[:15],
        )
        # 递归搜索
        found = _find_items_recursive(data, depth=0)
        if found:
            logger.info("parse_search_api_result: 递归搜索找到 {} 个商品", len(found))
            return found
        return []
    return []


def _find_items_recursive(obj: Any, depth: int = 0, max_depth: int = 4) -> list[dict]:
    """递归搜索 dict/list 结构中包含商品特征的列表

    闲鱼 API 可能嵌套在不同层级，此函数做兜底搜索。
    """
    _item_keys = ("itemId", "id", "item_id", "auctionId", "auction_id")
    if depth > max_depth:
        return []
    if isinstance(obj, list):
        # 检查列表元素是否像商品（含 itemId/id/auctionId 等标识字段）
        # 闲鱼 resultList 元素可能将商品字段包裹在 data 子字典中
        if obj and isinstance(obj[0], dict):
            for item in obj[:3]:
                if any(k in item for k in _item_keys):
                    return obj
                # 检查 data 子字典中的商品字段
                sub = item.get("data")
                if isinstance(sub, dict) and any(k in sub for k in _item_keys):
                    return obj
        # 继续搜索子元素
        for item in obj:
            found = _find_items_recursive(item, depth + 1, max_depth)
            if found:
                return found
    elif isinstance(obj, dict):
        for v in obj.values():
            found = _find_items_recursive(v, depth + 1, max_depth)
            if found:
                return found
    return []
