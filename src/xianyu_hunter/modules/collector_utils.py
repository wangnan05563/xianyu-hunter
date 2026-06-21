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

    闲鱼 API 对部分商品不返回独立的 userNick/sellerNick 字段，
    而是将卖家昵称放在 region 字段中（非地理地区）。

    Returns:
        (nick, region): 提取到的昵称和清洗后的地区
        如果所有 nick 候选字段为空且 region 不像地名，则将 region 视为 nick
    """
    nick = ""
    for nk in ("userNick", "sellerNick", "nick", "userNickname", "sellerNickName"):
        v = raw.get(nk)
        if v and isinstance(v, str) and v.strip():
            nick = v.strip()
            break

    raw_region = raw.get("region", "")
    if not nick and raw_region:
        if not is_region_like(raw_region):
            nick = raw_region.strip()
            raw_region = ""

    return nick, raw_region


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
