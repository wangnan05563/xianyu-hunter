"""评估明细 API"""
from __future__ import annotations

import json
import math
import re
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from xianyu_hunter.container import Container
from xianyu_hunter.domain.evaluation import RiskLevel
from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.modules.collector_utils import normalize_display_fields
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


# S1192: 提取重复字符串字面量为常量，避免散落维护
_BROKEN_LABEL = "有故障/维修"
_USED_TRACE_LABEL = "有使用痕迹"
_EVAL_TYPE_PREFIX = "eval."
_EVAL_SCORED_TYPE = "eval.scored"
# 已知污染模式：早期 DOM 解析脚本错误写入的字段值
_REGION_PATTERNS = re.compile(r"^[\u4e00-\u9fa5]{2,4}$")  # 纯 2-4 字中文（省/市）
_CREDIT_PATTERNS = re.compile(r"^.*(信用|极好|良好|优秀|信誉).*$")
# match() 不要求匹配到字符串结尾，移除尾部 .* 降低正则复杂度（S5843）
_PUBLISH_TIME_PATTERNS = re.compile(
    r".*(周内|天内|小时前|分钟前|月前|刚刚|今天|昨天|前天|秒前|\d+\s*(分钟|小时|天|周|月)前)"
)
# 卖家昵称脏数据识别用的关键词集合
# 必须包含所有可能的污染值（如"几乎全新"、"全新"等成色关键词）
_POLLUTED_NICK_KEYWORDS = {
    "全新", "未拆封", "未使用", "未拆", "99新", "95新", "9成新", "几乎全新",
    "近全新", "近新", "9.5新", "9.9新", "8成新", "8.5新", "85新", "7成新",
    "正常使用", "使用过", _USED_TRACE_LABEL, "明显使用", "外观磨损", "有划痕", "磕碰",
    "维修", "维修过", "拆修", "故障", "损坏", "已坏", "屏幕破损", "进水", "摔过",
    "原装", "原厂", "正品", "原盒", "原包装", "带发票", "带保修", "在保",
    "裸机", "无包装", "无配件",
    "全新未拆", "未拆封未使用", "未激活", "国行未激活",
    "轻微使用", "保养好", "使用痕迹少", "成色新",
    "成色一般", "使用痕迹明显", "老化", "非全新", "不能用", "进水机",
    "全套", "配件齐全", "带原盒", "保修中", "保修卡", "原装盒", "全套包装",
    "无充电器", "无原盒", "无发票", "无保修卡", "配件不全", "缺包装",
}


def _is_polluted_seller_nick(value: str) -> tuple[bool, str]:
    """检测 seller_nick 是否为脏数据

    返回 (is_polluted, pollution_type)：
    - pollution_type: "region" | "credit" | "publish_time" | "condition" | "combined" | ""
    """
    if not value or not isinstance(value, str):
        return False, ""
    s = value.strip()
    if not s:
        return False, ""

    # 1. 复合污染：包含 \n 分隔的多个字段（地区+信用度）
    if "\n" in s or "\\n" in s:
        return True, "combined"

    # 2. 地区污染：纯 2-4 字中文
    if _REGION_PATTERNS.match(s) and s in {"河北", "山西", "山东", "河南", "江苏", "浙江",
                                              "安徽", "福建", "江西", "湖北", "湖南", "广东",
                                              "广西", "海南", "四川", "贵州", "云南", "陕西",
                                              "甘肃", "青海", "台湾", "北京", "天津", "上海",
                                              "重庆", "唐山", "石家庄", "保定", "邯郸", "秦皇岛",
                                              "广州", "深圳", "杭州", "南京", "苏州", "成都",
                                              "武汉", "西安", "郑州", "济南", "青岛", "厦门",
                                              "福州", "合肥", "南昌", "长沙", "太原"}:
        return True, "region"

    # 3. 信用度污染
    if _CREDIT_PATTERNS.match(s) and len(s) <= 20:
        return True, "credit"

    # 4. 发布时间污染（"一周内发布"、"x小时前"等）
    if _PUBLISH_TIME_PATTERNS.match(s) and len(s) <= 20:
        return True, "publish_time"

    # 5. 成色关键词污染（"几乎全新"等）
    if s in _POLLUTED_NICK_KEYWORDS:
        return True, "condition"

    return False, ""


# ==== _clean_dirty_seller_nick 辅助函数 ====
def _handle_combined_pollution(payload: dict, nick: str) -> None:
    """复合污染处理：分离"地区\n信用度"格式，剩余部分作为 seller_nick"""
    parts = [s.strip() for s in nick.replace("\\n", "\n").split("\n") if s.strip()]
    region = ""
    credit = ""
    for p in parts:
        _, sub_type = _is_polluted_seller_nick(p)
        if sub_type == "region" and not region:
            region = p
        elif sub_type == "credit" and not credit:
            credit = p
    if region and not payload.get("region"):
        payload["region"] = region
    if credit and not payload.get("seller_credit"):
        payload["seller_credit"] = credit
    # 剩余部分作为 seller_nick
    real_nick = " ".join(p for p in parts if p != region and p != credit).strip()
    payload["seller_nick"] = real_nick


def _handle_region_pollution(payload: dict, nick: str) -> None:
    """地区污染处理：移到 region 字段，清空 seller_nick"""
    if not payload.get("region"):
        payload["region"] = nick.strip()
    payload["seller_nick"] = ""


def _handle_credit_pollution(payload: dict, nick: str) -> None:
    """信用度污染处理：移到 seller_credit 字段，清空 seller_nick"""
    if not payload.get("seller_credit"):
        payload["seller_credit"] = nick.strip()
    payload["seller_nick"] = ""


def _handle_publish_time_pollution(payload: dict, nick: str) -> None:
    """发布时间污染处理：保存为 publish_time_text，清空 seller_nick

    为什么存到 publish_time_text：前端发布时间为空时兜底显示"""
    if not payload.get("publish_time_text"):
        payload["publish_time_text"] = nick.strip()
    payload["seller_nick"] = ""


def _handle_condition_pollution(payload: dict, nick: str) -> None:
    """成色关键词污染处理：保存为 condition_label_override，清空 seller_nick

    为什么存到 condition_label_override：覆盖自动计算结果，保证脏数据恢复后展示正确"""
    if not payload.get("condition_label_override"):
        payload["condition_label_override"] = nick.strip()
    payload["seller_nick"] = ""


def _clean_dirty_seller_nick(payload: dict) -> None:
    """清洗历史评估数据中 seller_nick 字段被污染的问题

    历史 bug 总结（多种污染模式）：
    1. 早期 DOM 解析脚本用宽泛的 [class*="seller"] 选择器，导致 seller_nick 字段
       被写入了"地区\\n\\n卖家信用度"格式的脏数据
    2. 部分历史代码从商品标题/描述中错误地提取了"几乎全新"、"一周内发布"等
       成色/时间关键词作为 seller_nick
    3. 部分记录 seller_nick 字段是纯地区名（"河北"、"唐山"等）

    本函数通过白名单+模式识别检测污染，并尝试将脏数据分离到正确的字段：
    - 地区 → region
    - 信用度 → seller_credit
    - 发布时间短语 → publish_time_text（前端兜底展示）
    - 成色关键词 → condition_label（覆盖自动计算结果）
    """
    nick = payload.get("seller_nick", "")
    is_polluted, pollution_type = _is_polluted_seller_nick(nick)

    if not is_polluted:
        return

    if pollution_type == "combined":
        _handle_combined_pollution(payload, nick)
    elif pollution_type == "region":
        _handle_region_pollution(payload, nick)
    elif pollution_type == "credit":
        _handle_credit_pollution(payload, nick)
    elif pollution_type == "publish_time":
        _handle_publish_time_pollution(payload, nick)
    elif pollution_type == "condition":
        _handle_condition_pollution(payload, nick)
    else:
        # 兜底：未识别的污染模式，清空 seller_nick
        payload["seller_nick"] = ""

    # 调试日志：记录脏数据清洗情况（生产环境可通过日志级别控制）
    logger.info(
        "Cleaned dirty seller_nick: type=%s, original=%r, new_nick=%r, region=%r, credit=%r, publish_text=%r, override=%r",
        pollution_type, nick, payload.get("seller_nick"),
        payload.get("region"), payload.get("seller_credit"),
        payload.get("publish_time_text"), payload.get("condition_label_override"),
    )


def _coerce_price(v: object) -> float | None:
    """兼容 task_links.display 的 price 字符串转 float

    None/空字符串视为缺失，返回 None；转换失败也返回 None"""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _coerce_int(v: object) -> int | None:
    """兼容 task_links.display 的 want_cnt/view_cnt 字符串转 int

    None 视为缺失；转换失败返回 None，避免脏数据中断 enrich 流程"""
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _collect_enrich_candidates(item: dict, link: dict) -> dict:
    """收集 items 表和 task_links 表的字段候选值

    数据源优先级：items 表 > task_links.display"""
    return {
        "title": item.get("title") or link.get("title") or link.get("item_title") or "",
        "price": item.get("price") if item.get("price") is not None else _coerce_price(link.get("price")),
        "thumb_url": item.get("thumb_url") or link.get("thumb_url"),
        "region": item.get("region") or link.get("region"),
        "brand": item.get("brand") or link.get("brand"),
        "want_cnt": item.get("want_cnt") if item.get("want_cnt") is not None else _coerce_int(link.get("want_cnt")),
        "view_cnt": item.get("view_cnt") if item.get("view_cnt") is not None else _coerce_int(link.get("view_cnt")),
        "publish_time": item.get("publish_time") or link.get("publish_time"),
        "seller_id": item.get("seller_id") or link.get("seller_id"),
    }


def _apply_enrich_fields(
    payload: dict, candidates: dict, item: dict, link: dict,
) -> None:
    """补充/覆盖 payload 字段

    items 表和 task_links.display 反映采集最新值，
    eval 事件 payload 中的对应字段是评估时的历史快照。
    用户点击标题刷新后，期望评估明细页显示最新商品信息，而非评估时的旧快照。
    因此对"会变动的商品基础信息"字段，有最新值则覆盖；无最新值时保留 payload 旧快照。
    例外：seller_nick 有脏数据清洗特殊逻辑，保持"仅缺失时填充"。"""
    if candidates["title"]:
        payload["item_title"] = candidates["title"]
    # price=0 可能是采集失败（选择器未命中），不应覆盖有效旧值
    if candidates["price"] is not None and candidates["price"] > 0:
        payload["item_price"] = candidates["price"]
    # seller_id：有最新值则覆盖
    if candidates["seller_id"]:
        payload["seller_id"] = str(candidates["seller_id"])
    # 关键修复：脏数据清洗后 seller_nick 为空字符串（falsy），
    # 不能用 `not payload.get("seller_nick")` 判定缺失，否则会被 items 表回填错误数据
    if payload.get("seller_nick") is None:
        nick = link.get("seller_nick") or item.get("seller_nick")
        if nick:
            payload["seller_nick"] = nick
    if candidates["thumb_url"]:
        payload["thumb_url"] = candidates["thumb_url"]
    if candidates["region"]:
        payload["region"] = candidates["region"]
    if candidates["brand"]:
        payload["brand"] = candidates["brand"]
    # want_cnt/view_cnt=0 可能是采集失败，不应覆盖有效旧值
    if candidates["want_cnt"] is not None and candidates["want_cnt"] > 0:
        payload["want_cnt"] = candidates["want_cnt"]
    if candidates["view_cnt"] is not None and candidates["view_cnt"] > 0:
        payload["view_cnt"] = candidates["view_cnt"]
    if candidates["publish_time"]:
        payload["publish_time"] = str(candidates["publish_time"])
    # is_sold：items 表（int 0/1）> task_links.display（bool）> 保留 payload 旧值
    # 为什么总是覆盖：已售状态会变化（在售→已售），用户期望看到最新状态
    raw_sold = item.get("is_sold")
    if raw_sold is not None:
        payload["is_sold"] = bool(raw_sold)
    elif "is_sold" in link:
        payload["is_sold"] = bool(link["is_sold"])


def _inject_order_status(
    payload: dict, order_map: dict[str, dict] | None, item_id: str,
) -> None:
    """注入订单状态：让评估明细页面能直接展示商品是否已被抢单

    为什么不写入 payload 原始事件：order_status 是实时查询的派生字段，不应污染 events 表"""
    if order_map is None or not item_id:
        return
    order = order_map.get(item_id)
    if order:
        payload["order_status"] = order.get("status")
        payload["order_id"] = order.get("id")
    else:
        payload["order_status"] = None
        payload["order_id"] = None


def _enrich_eval_with_item(
    payload: dict, item_map: dict[str, dict], link_map: dict[str, dict] | None = None,
    order_map: dict[str, dict] | None = None,
) -> dict:
    """用 items 表或 task_links 表数据丰富评估记录（补充标题、价格、地区、图片等缺失字段）

    数据源优先级：
    1. items 表（结构化字段最完整，包含 publish_time 等）
    2. task_links.display（任务关联冗余字段，弥补评估事件未入 items 表的常见场景）

    字段名与前端 EvalItem 接口对齐：
    - item_title / item_price / seller_id / seller_nick / thumb_url
    - region / publish_time / want_cnt / view_cnt
    - order_status（来自 order_map，标记商品是否已被抢单）
    """
    item_id = str(payload.get("item_id") or "")
    item = item_map.get(item_id, {}) if item_id else {}
    link = (link_map or {}).get(item_id, {}) if item_id else {}
    if link:
        link, _ = normalize_display_fields(link)

    candidates = _collect_enrich_candidates(item, link)

    # 脏数据清洗：seller_nick 字段可能包含"地区+信用度"组合
    if item or link:
        _clean_dirty_seller_nick(payload)

    _apply_enrich_fields(payload, candidates, item, link)
    _inject_order_status(payload, order_map, item_id)
    return payload


# ==== list_evaluations 辅助函数 ====
def _parse_eval_time_range(
    start_time: str | None, end_time: str | None,
) -> tuple[Any, Any]:
    """解析评估时间过滤边界，end_time 当天结束（23:59:59）覆盖整天

    预解析避免在循环内反复解析同一时间字符串"""
    start_dt = to_datetime(start_time) if start_time else None
    end_dt = to_datetime(end_time) if end_time else None
    if end_dt:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
    return start_dt, end_dt


def _apply_task_price_fallback(
    container: Container,
    task_id: str | None,
    min_price: float | None,
    max_price: float | None,
    include_out_of_range: bool,
) -> tuple[float | None, float | None]:
    """任务级价格回退：用户未显式传 min/max_price 但传了 task_id 时，
    自动从 task 表读取，解决"评估明细显示超范围商品"问题

    为什么放在 rows 加载之后：task 配置查询独立于 events，提前查会浪费未命中的 IO"""
    if include_out_of_range or (min_price is not None and max_price is not None) or not task_id:
        return min_price, max_price
    try:
        # task_id 在评估明细页是 Select 选择的精确值，但 API 层支持模糊匹配，
        # 此处用 get_task 精确查询；若任务不存在则不应用价格过滤（避免误伤）
        task_raw = container.repo.get_task(task_id)
        if task_raw:
            if min_price is None and task_raw.get("min_price") is not None:
                min_price = float(task_raw["min_price"])
            if max_price is None and task_raw.get("max_price") is not None:
                max_price = float(task_raw["max_price"])
    except Exception as e:
        logger.warning(f"读取任务 {task_id} 价格配置失败，跳过价格过滤: {e}")
    return min_price, max_price


def _collect_eval_event_item_ids(rows: list[dict]) -> set[str]:
    """收集本批评估事件涉及的所有 item_id，用于批量查询 items / task_links"""
    event_item_ids: set[str] = set()
    for r in rows:
        payload = r.get("payload") or {}
        iid = str(payload.get("item_id") or r.get("item_id") or "")
        if iid:
            event_item_ids.add(iid)
    return event_item_ids


def _load_eval_item_map(container: Container, item_ids: set[str]) -> dict[str, dict]:
    """预加载 items 表数据，用于丰富评估记录

    为什么按 item_id 批量查询：之前用 list_items(limit=5000) 全量加载，超过 5000 行会遗漏"""
    if not item_ids:
        return {}
    item_rows = container.repo.list_items_by_ids(list(item_ids))
    item_map: dict[str, dict] = {}
    for it in item_rows:
        iid = str(it.get("item_id") or it.get("id") or "")
        if iid:
            item_map[iid] = it
    return item_map


def _build_item_sold_map(item_map: dict[str, dict], sold_filter: str) -> dict[str, bool]:
    """预构建 item_id -> is_sold 映射，供 sold_filter 在 Python 端过滤使用

    为什么不在 SQL 端下推：events 表需 JOIN items 表按 item_id 关联再分页，
    events 表数据量级大且已按 task_id+item_id 去重，Python 端过滤足够高效"""
    if sold_filter == "all":
        return {}
    item_sold_map: dict[str, bool] = {}
    for iid, it in item_map.items():
        # items.is_sold 是 int(0/1)，转 bool 便于过滤判断
        item_sold_map[iid] = bool(it.get("is_sold"))
    return item_sold_map


def _load_seller_nick_map(container: Container, item_map: dict[str, dict]) -> dict[str, str]:
    """预加载 sellers 表数据（items 表无 seller_nick，需从 sellers 表补充）

    为什么按 seller_id 批量查询：之前直接访问 engine 查询所有 sellers"""
    seller_ids_from_items = {
        str(it.get("seller_id") or "")
        for it in item_map.values()
        if it.get("seller_id")
    }
    if not seller_ids_from_items:
        return {}
    seller_map: dict[str, str] = {}  # seller_id -> nick
    seller_rows = container.repo.list_sellers_by_ids(list(seller_ids_from_items))
    for s in seller_rows:
        sid = str(s.get("id") or "")
        nick = s.get("nick")
        if sid and nick:
            seller_map[sid] = nick
    return seller_map


def _match_item_id_filter(payload: dict, r: dict, item_id: str | None) -> bool:
    """商品 ID 模糊匹配：返回 True 表示应跳过该记录"""
    if not item_id:
        return False
    eid = str(payload.get("item_id") or r.get("item_id") or "")
    return item_id.lower() not in eid.lower()


def _match_task_id_filter(payload: dict, r: dict, task_id: str | None) -> bool:
    """任务 ID 模糊匹配：返回 True 表示应跳过该记录"""
    if not task_id:
        return False
    tid = str(payload.get("task_id") or r.get("task_id") or "")
    return task_id.lower() not in tid.lower()


def _match_brand_filter(payload: dict, brand: str | None) -> bool:
    """品牌精确匹配：brand 字段已由 _enrich_eval_with_item 从 task_links.display 补充

    为什么放在 enrich 之后：评估事件本身不存 brand，必须先补全再过滤"""
    if not brand:
        return False
    return str(payload.get("brand") or "") != brand


def _filter_sold_status(
    payload: dict, r: dict, sold_filter: str, item_sold_map: dict[str, bool],
) -> bool:
    """销售状态过滤：返回 True 表示应跳过

    为什么 items 表无记录时按"在售"处理：评估事件可能引用了未入库的商品，
    这种情况按"在售"保留，避免 onsale 过滤时误删有效评估"""
    if sold_filter == "all":
        return False
    iid = str(payload.get("item_id") or r.get("item_id") or "")
    is_sold = item_sold_map.get(iid, False)
    if sold_filter == "onsale" and is_sold:
        return True
    if sold_filter == "sold" and not is_sold:
        return True
    return False


def _filter_price_range(
    payload: dict,
    min_price: float | None,
    max_price: float | None,
    include_out_of_range: bool,
) -> bool:
    """价格范围过滤：返回 True 表示应跳过

    为什么放在 enrich 之后：item_price 已由 _enrich_eval_with_item 用 items 表最新值覆盖
    为什么 include_out_of_range 跳过：用户审计历史超范围商品时需要能查看
    为什么 price=None 时不过滤：评估时可能未采集到价格，保留避免误删"""
    if include_out_of_range or (min_price is None and max_price is None):
        return False
    price_val = payload.get("item_price")
    if price_val is None:
        return False
    try:
        price_float = float(price_val)
    except (TypeError, ValueError):
        return False
    if min_price is not None and price_float < min_price:
        return True
    if max_price is not None and price_float > max_price:
        return True
    return False


def _parse_eval_score(payload: dict) -> float | None:
    """解析 payload 中的 score，失败或缺失返回 None"""
    score = payload.get("score")
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def _filter_score_range(
    score: float | None, min_score: int | None, max_score: int | None,
) -> bool:
    """评分范围过滤：返回 True 表示应跳过"""
    if min_score is not None and (score is None or score < min_score):
        return True
    if max_score is not None and (score is None or score > max_score):
        return True
    return False


def _filter_result_category(
    score: float | None, result_category: str | None,
) -> bool:
    """结果分类过滤：按配置阈值精确分类，与统计卡片展示逻辑一致

    为什么不用 min_score/max_score：score 可能是浮点数（如 75.5），
    max_score 是闭区间无法表达 [pass, auto) 半开区间；
    insufficient 需要 score=null，min/max_score 会把 null 排除"""
    if not result_category:
        return False
    eval_cfg = get_config().eval
    pass_threshold = eval_cfg.pass_score
    auto_threshold = eval_cfg.auto_buy_score
    if result_category == "auto":
        return score is None or score < auto_threshold
    if result_category == "pass":
        return score is None or score < pass_threshold or score >= auto_threshold
    if result_category == "fail":
        return score is None or score >= pass_threshold
    if result_category == "insufficient":
        return score is not None
    return False


def _filter_time_range(r: dict, start_dt: Any, end_dt: Any) -> bool:
    """时间范围过滤：返回 True 表示应跳过"""
    if not start_dt and not end_dt:
        return False
    ts = r.get("created_at", "")
    d = to_datetime(ts) if ts else None
    if d is None:
        return True
    if start_dt and d < start_dt:
        return True
    if end_dt and d > end_dt:
        return True
    return False


def _enrich_eval_record(
    r: dict, item_map: dict[str, dict], link_map: dict[str, dict],
    order_map: dict[str, dict], seller_map: dict[str, str],
) -> None:
    """丰富单条评估记录的 payload 字段（标题/价格/卖家/订单状态等）

    拆分自主循环：降低 list_evaluations 嵌套层级，避免 11 个 if 平铺时认知负担过重"""
    # 关键修复：必须把兜底空字典写回 r["payload"]，否则数据库中 payload 为 NULL 的记录
    # 会在 _enrich_eval_with_item 修改后仍以 None 返回前端，导致 r.payload.score 报错
    r["payload"] = r.get("payload") or {}
    payload = r["payload"]

    _enrich_eval_with_item(payload, item_map, link_map, order_map)

    # 用 sellers 表补充卖家昵称（items 表无 seller_nick 字段）
    # 关键修复：脏数据清洗后 seller_nick 为空字符串，不能用 `not` 判定缺失
    sid = payload.get("seller_id") or r.get("seller_id")
    if sid and payload.get("seller_nick") is None and str(sid) in seller_map:
        payload["seller_nick"] = seller_map[str(sid)]

    # 确保顶层 item_id 有值（兼容旧事件：EventRow.item_id 列可能为空）
    if not r.get("item_id") and payload.get("item_id"):
        r["item_id"] = str(payload["item_id"])


def _should_skip_eval_record(
    r: dict, payload: dict,
    item_id: str | None, task_id: str | None, brand: str | None,
    sold_filter: str, item_sold_map: dict[str, bool],
    min_price: float | None, max_price: float | None,
    include_out_of_range: bool,
    min_score: int | None, max_score: int | None,
    result_category: str | None,
    start_dt: Any, end_dt: Any,
) -> bool:
    """判断评估记录是否应被跳过（不满足任一过滤条件返回 True）

    拆分自主循环：把 8 个独立 if 过滤条件收敛到一个函数，
    主循环只看到一个判定结果，降低嵌套层级与认知复杂度"""
    if _match_item_id_filter(payload, r, item_id):
        return True
    if _match_task_id_filter(payload, r, task_id):
        return True
    if _match_brand_filter(payload, brand):
        return True
    if _filter_sold_status(payload, r, sold_filter, item_sold_map):
        return True
    if _filter_price_range(payload, min_price, max_price, include_out_of_range):
        return True
    score = _parse_eval_score(payload)
    if _filter_score_range(score, min_score, max_score):
        return True
    if _filter_result_category(score, result_category):
        return True
    if _filter_time_range(r, start_dt, end_dt):
        return True
    return False


@router.get("")
def list_evaluations(
    request: Request,
    limit: int = 200,
    offset: int = 0,
    page_num: int = Query(1, ge=1, description="页码（从1开始）"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    item_id: str | None = Query(None, description="商品 ID 模糊匹配"),
    task_id: str | None = Query(None, description="任务 ID 模糊匹配"),
    min_score: int | None = Query(None, ge=0, le=100, description="最低评分"),
    max_score: int | None = Query(None, ge=0, le=100, description="最高评分"),
    start_time: str | None = Query(None, description="开始时间 (YYYY-MM-DD)"),
    end_time: str | None = Query(None, description="结束时间 (YYYY-MM-DD)"),
    brand: str | None = Query(None, description="品牌精确匹配（从 items/task_links.display 补充后过滤）"),
    sold_filter: str = Query("all", pattern="^(all|onsale|sold)$", description="销售状态过滤：all=全部 / onsale=在售 / sold=已售"),
    result_category: str | None = Query(
        None,
        pattern="^(auto|pass|fail|insufficient)$",
        description="结果分类过滤：auto=可抢(≥auto_buy_score) / pass=通过([pass_score,auto_buy_score)) / fail=驳回(<pass_score) / insufficient=数据不足(score=null)",
    ),
    min_price: float | None = Query(None, ge=0, description="价格下限（含）。未传但传了 task_id 时自动从任务配置读取"),
    max_price: float | None = Query(None, ge=0, description="价格上限（含）。未传但传了 task_id 时自动从任务配置读取"),
    include_out_of_range: bool = Query(False, description="是否显示超出任务价格范围的历史商品（默认 False，仅显示合规商品）"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """从 events 表中读 eval.* 事件（与 list_events 共享存储）

    支持按商品 ID、任务 ID 模糊查询，按评分范围、时间范围过滤。
    支持 page_num/page_size 分页（优先于旧版 limit/offset）。
    自动关联 items 表补充标题、价格、卖家等字段。
    brand 过滤在 enrich 之后执行（品牌字段从 task_links.display 补充）。
    sold_filter 在 Python 端过滤：评估事件本身不存 is_sold，需从 items 表批量查询后过滤。
    result_category 按配置阈值精确分类过滤，支持 score=null 的"数据不足"过滤，
    解决前端只过滤当前页导致"点击统计卡片查不到记录"的问题。

    价格范围过滤（min_price/max_price）：
    - 显式参数优先；未传但传了 task_id 时自动从 task.min_price/max_price 读取
    - 解决评估明细菜单显示大量超出任务价格范围商品的问题
    - include_out_of_range=True 时跳过价格过滤，用于审计历史超范围商品
    - 价格取自 enrich 后的 payload.item_price（已是 items 表最新值）
    """
    start_dt, end_dt = _parse_eval_time_range(start_time, end_time)

    # 修复：之前用 list_events(limit=limit*4) 在 Python 端过滤 eval.*，
    # 当非 eval 事件多时会遗漏数据且 total 不准。改为 SQL 端按 type 前缀过滤。
    # 不传 limit/offset，全量加载 eval.* 事件（评估事件已按 task_id+item_id 去重，量级可控），
    # 后续在 Python 端做 item_id/task_id 模糊匹配、score/time 范围过滤，再分页。
    # 多用户隔离：仅查询当前账号的评估事件
    user_id = getattr(request.state, "user_id", None)
    rows, _ = container.repo.list_events_by_type_prefix(
        type_prefix=_EVAL_TYPE_PREFIX, user_id=user_id,
    )

    min_price, max_price = _apply_task_price_fallback(
        container, task_id, min_price, max_price, include_out_of_range
    )

    event_item_ids = _collect_eval_event_item_ids(rows)
    item_map = _load_eval_item_map(container, event_item_ids)
    item_sold_map = _build_item_sold_map(item_map, sold_filter)

    # 预加载 task_links.display 数据（弥补 items 表缺失的常见场景：评估事件未入 items 但已关联到任务）
    # 修复：之前直接访问 container.repo.engine 绕过 Repository，改为调用正式方法
    link_map: dict[str, dict] = container.repo.list_link_displays_by_keys(
        list(event_item_ids), link_type="item", user_id=user_id,
    ) if event_item_ids else {}

    seller_map = _load_seller_nick_map(container, item_map)

    # 批量预加载订单状态：避免 N+1 查询，评估明细列表展示「订单状态」列使用
    # 为什么放在主流程：order_status 是派生字段，不写入 events 表，每次查询时实时关联
    # 为什么 include_failed=True：评估明细需要展示失败订单记录，否则用户
    # 点击抢单失败后刷新页面看到「—」，会误以为没下过单而反复触发抢单
    order_map = (
        container.repo.list_orders_by_item_ids(
            list(event_item_ids), include_failed=True, user_id=user_id,
        )
        if event_item_ids
        else {}
    )

    evals = []
    for r in rows:
        # 只展示 eval.scored 评估事件，排除 eval.passed 等通知事件
        # 为什么不用 startswith("eval.")：NotifierHub 推送钉钉时会写入 type="eval.passed"、
        # payload=None、stage="notify" 的记录（hub.py 第 196-204 行），这些通知事件
        # 没有评分数据，混入列表会导致前端出现大量"无内容记录"且被 distribution API
        # 误算为 insufficient_count
        if str(r.get("type", "")) != _EVAL_SCORED_TYPE:
            continue
        _enrich_eval_record(r, item_map, link_map, order_map, seller_map)
        payload = r["payload"]
        if _should_skip_eval_record(
            r, payload, item_id, task_id, brand,
            sold_filter, item_sold_map,
            min_price, max_price, include_out_of_range,
            min_score, max_score, result_category,
            start_dt, end_dt,
        ):
            continue

        evals.append(r)
    # 计算成色判断标签（基于商品标题和描述文本，帮助用户判断商品新旧程度）
    _enrich_condition_tags(evals)
    total = len(evals)
    # 始终使用 page_num/page_size 分页
    actual_offset = (page_num - 1) * page_size
    paged = evals[actual_offset:actual_offset + page_size]
    return {"items": paged, "count": len(paged), "total": total}


# 商品成色判断关键词库（用户购物时关注的核心维度）
_CONDITION_KEYWORDS = {
    "newness": {  # 成色新
        "labels": ["全新", "未拆封", "未使用", "未拆", "全新未拆", "99新", "95新", "9成新", "几乎全新",
                   "未激活", "国行未激活", "原装", "原厂", "正品", "未拆封未使用"],
        "score_bonus": 1,  # 每命中 1 个 +1 分
    },
    "newness_worn": {  # 轻度使用（与 newness 不重复的关键词，score_bonus=0）
        "labels": ["9.5新", "9.9新", "轻微使用", "保养好", "使用痕迹少", "成色新"],
        "score_bonus": 0,
    },
    "used": {  # 中度使用
        "labels": ["8成新", "8.5新", "85新", "9成新以下", "正常使用", "使用过", _USED_TRACE_LABEL],
        "score_bonus": -1,
    },
    "worn": {  # 明显使用
        "labels": ["7成新", "成色一般", "使用痕迹明显", "外观磨损", "有划痕", "磕碰", "老化"],
        "score_bonus": -2,
    },
    "broken": {  # 故障/维修
        "labels": ["维修", "维修过", "拆修", "非全新", "故障", "损坏", "不能用", "已坏",
                   "屏幕破损", "进水", "摔过", "进水机"],
        "score_bonus": -3,
    },
    "completeness": {  # 配件完整度
        "labels": ["全套", "配件齐全", "原盒", "原包装", "带发票", "带保修", "带原盒",
                   "在保", "保修中", "保修卡", "原装盒", "全套包装"],
        "score_bonus": 1,
    },
    "completeness_missing": {  # 配件缺失
        "labels": ["无包装", "无配件", "无充电器", "无原盒", "裸机", "无发票",
                   "无保修卡", "配件不全", "缺包装"],
        "score_bonus": -1,
    },
}

# 关键词 → 成色描述的映射（用于 condition_label_override 覆盖）
# 与 _CONDITION_KEYWORDS 一起定义在 _enrich_condition_tags 之前，避免使用时还未定义
_CONDITION_KEYWORDS_LABEL_MAP = {
    "全新": "全新", "未拆封": "全新", "未使用": "全新", "未拆": "全新",
    "99新": "近全新", "95新": "近全新", "9成新": "近全新", "几乎全新": "近全新",
    "近全新": "近全新", "近新": "近全新", "9.5新": "近全新", "9.9新": "近全新",
    "8成新": "正常使用", "8.5新": "正常使用", "85新": "正常使用", "7成新": "明显使用",
    "正常使用": "正常使用", "使用过": "正常使用", _USED_TRACE_LABEL: "正常使用",
    "明显使用": "明显使用", "外观磨损": "明显使用", "有划痕": "明显使用", "磕碰": "明显使用",
    "维修": _BROKEN_LABEL, "维修过": _BROKEN_LABEL, "拆修": _BROKEN_LABEL,
    "故障": _BROKEN_LABEL, "损坏": _BROKEN_LABEL, "已坏": _BROKEN_LABEL,
    "屏幕破损": _BROKEN_LABEL, "进水": _BROKEN_LABEL, "摔过": _BROKEN_LABEL,
    "原装": "全新", "原厂": "全新", "正品": "全新",  # 单独成色描述时归为全新
    "原盒": "全新", "原包装": "全新", "带发票": "全新", "带保修": "全新", "在保": "全新",
    "裸机": "明显使用", "无包装": "正常使用", "无配件": "正常使用",
}


# ==== _enrich_condition_tags 辅助函数 ====
def _build_condition_scan_text(payload: dict) -> str:
    """合并标题和描述作为成色关键词扫描文本

    为什么合并多字段：商品成色信息可能出现在标题或描述任一位置，
    单字段扫描会漏判，需拼接后统一匹配"""
    text_parts = [
        payload.get("item_title", "") or "",
        payload.get("description", "") or "",
        payload.get("item_description", "") or "",
    ]
    return " ".join(text_parts).strip()


def _init_empty_condition(r: dict) -> None:
    """无文本可扫描时初始化空成色字段"""
    r["condition_tags"] = []
    r["condition_label"] = "未知"
    r["condition_score"] = 0
    r["is_branded_new"] = False
    r["has_repair"] = False


def _scan_condition_keywords(text: str) -> tuple[list[dict], int]:
    """扫描文本中的成色关键词，返回 (tags, score)

    每个 category 只算一次（避免同一类别多关键词重复加分）"""
    tags: list[dict] = []
    score = 0
    for category, info in _CONDITION_KEYWORDS.items():
        for label in info["labels"]:
            if label in text:
                tags.append({"category": category, "label": label})
                score += info["score_bonus"]
                break
    return tags, score


def _resolve_base_condition_label(tags: list[dict]) -> str:
    """根据扫描到的 tags 综合判断成色描述

    优先级：故障 > 明显使用 > 正常使用 > 近全新 > 全新 > 未注明
    为什么按此优先级：负面成色对购买决策影响更大，应优先展示"""
    if any(t["category"] == "broken" for t in tags):
        return _BROKEN_LABEL
    if any(t["category"] == "worn" for t in tags):
        return "明显使用"
    if any(t["category"] == "used" for t in tags):
        return "正常使用"
    if any(t["category"] == "newness_worn" for t in tags):
        return "近全新"
    if any(t["category"] == "newness" for t in tags):
        return "全新"
    return "未注明"


def _apply_condition_override(
    r: dict, payload: dict, tags: list[dict], score: int, condition_label: str,
) -> tuple[list[dict], int, str]:
    """兜底覆盖：若历史数据清洗后从 seller_nick 提取到了成色关键词，用其覆盖自动计算结果

    为什么需要覆盖：脏数据恢复后的成色关键词比标题/描述扫描更可靠，
    保证脏数据恢复后展示正确。
    返回更新后的 (tags, score, condition_label)；同时设置 r 的临时字段
    （后续 _set_condition_fields 会用最终 condition_label 再次覆盖）"""
    override = payload.get("condition_label_override")
    if not override or override not in _CONDITION_KEYWORDS_LABEL_MAP:
        return tags, score, condition_label
    condition_label = _CONDITION_KEYWORDS_LABEL_MAP[override]
    # 根据 override 的成色级别修正 condition_score
    if condition_label == "全新":
        score = max(score, 1)
    elif condition_label == _BROKEN_LABEL:
        # 之前只修正 label 未修正 score，导致显示不一致
        score = min(score, -3)
    r["is_branded_new"] = condition_label == "全新"
    r["has_repair"] = condition_label == _BROKEN_LABEL
    # 把 override 关键词也加入 tags（方便用户看到原始信息）
    if not any(t["label"] == override for t in tags):
        tags.append({
            "category": "newness" if condition_label in ("全新", "近全新") else "used",
            "label": override,
        })
    return tags, score, condition_label


def _set_condition_fields(
    r: dict, tags: list[dict], score: int, condition_label: str,
) -> None:
    """最终写入成色字段到评估记录"""
    r["condition_tags"] = tags
    r["condition_label"] = condition_label
    r["condition_score"] = score
    # is_branded_new：综合判断，override 命中"全新"或自动识别为"全新"时为 True
    r["is_branded_new"] = condition_label == "全新"
    # has_repair：override 命中故障类关键词或自动识别到 broken category 时为 True
    # 之前用 any(t["category"] == "broken") 单独判断会覆盖 override 的正确结果
    r["has_repair"] = condition_label == _BROKEN_LABEL or any(t["category"] == "broken" for t in tags)


def _enrich_condition_tags(evals: list[dict]) -> None:
    """为每条评估记录添加商品成色判断标签

    基于商品标题/描述文本扫描关键词库，识别成色状态（全新/轻度使用/明显使用/故障/维修等），
    同时给出 condition_score 调整分（叠加到评估分数上），帮助用户判断商品价值。

    新增字段：
    - condition_tags: 成色标签列表（如 ["全新", "配件齐全"]）
    - condition_label: 综合成色描述（全新/近全新/正常使用/明显使用/有故障）
    - condition_score: 成色调整分（-3 ~ +2，叠加到评估分数）
    - is_branded_new: 是否全新（布尔值）
    - has_repair: 是否有维修记录（布尔值）
    """
    for r in evals:
        # 跳过已存在 condition_tags 的记录（避免重复计算）
        if r.get("condition_tags"):
            continue
        payload = r.get("payload") or {}
        text = _build_condition_scan_text(payload)
        if not text:
            _init_empty_condition(r)
            continue

        tags, score = _scan_condition_keywords(text)
        condition_label = _resolve_base_condition_label(tags)
        tags, score, condition_label = _apply_condition_override(r, payload, tags, score, condition_label)
        _set_condition_fields(r, tags, score, condition_label)


@router.get("/latest/{item_id}")
def latest_for_item(
    item_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    # 多用户隔离：仅返回当前账号的评估记录
    user_id = getattr(request.state, "user_id", None)
    e = container.repo.get_latest_evaluation(item_id, user_id=user_id)
    if not e:
        raise HTTPException(status_code=404, detail="无该商品评估记录")
    return e


# ============== Task 11: 自动官方采集统计 API ==============
# ==== auto_collect_stats 辅助函数 ====
def _aggregate_failed_events(failed_rows) -> tuple[int, "Counter[str]"]:
    """聚合失败事件，返回 (failed_count, error_counter)

    error 字段截断前 100 字符作为 reason 分组，
    便于聚合 Top N（原始 error 含堆栈/参数，不截断会导致分组过于分散）"""
    from collections import Counter
    failed_count = 0
    error_counter: Counter[str] = Counter()
    for row in failed_rows:
        failed_count += 1
        try:
            payload = json.loads(row.payload) if isinstance(row.payload, str) else row.payload
            if not isinstance(payload, dict):
                error_counter["解析失败"] += 1
                continue
            # error 字段可能很长，截断前 100 字符作为 reason 分组
            # 为什么截断：原始 error 含堆栈/参数，截断后便于聚合 Top N
            error = str(payload.get("error", "未知错误"))[:100]
            error_counter[error] += 1
        except (json.JSONDecodeError, TypeError):
            error_counter["解析失败"] += 1
    return failed_count, error_counter


def _check_pause_status(conn, fail_pause_threshold: int) -> bool:
    """判断当前是否处于退避暂停状态

    取最近一条 collect.official.failed 事件的 consecutive_failures 字段，
    若 >= 阈值则视为暂停。为什么用最近一条而非累计：退避语义是"连续失败"，
    最近一条的 consecutive_failures 反映了最新连续失败计数"""
    from sqlalchemy import select
    from xianyu_hunter.infra.db_models import EventRow
    latest_failed_row = conn.execute(
        select(EventRow.payload)
        .where(EventRow.type == "collect.official.failed")
        .order_by(EventRow.created_at.desc())
        .limit(1)
    ).first()
    if not latest_failed_row:
        return False
    try:
        latest_payload = json.loads(latest_failed_row.payload) if isinstance(latest_failed_row.payload, str) else latest_failed_row.payload
        if isinstance(latest_payload, dict):
            latest_consecutive = int(latest_payload.get("consecutive_failures", 0))
            return latest_consecutive >= fail_pause_threshold
    # S5713: json.JSONDecodeError 是 ValueError 的子类，移除冗余子类
    except (TypeError, ValueError):
        pass
    return False


@router.get("/auto-collect-stats")
def auto_collect_stats(
    range_hours: int = 24,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """自动官方采集统计（最近 N 小时）

    聚合两类事件：
    - eval.scored AND payload.data_source='official' → 成功采集
    - collect.official.failed → 失败采集

    Returns:
        {
            "range_hours": 24,
            "total": 10,          # 成功 + 失败
            "success": 7,         # 成功采集数
            "failed": 3,          # 失败采集数
            "success_rate": 0.7,  # 成功率（0-1）
            "is_paused": False,   # 当前是否处于退避暂停状态
            "fail_pause_threshold": 3,  # 退避阈值（来自全局配置）
            "top_failures": [     # 失败原因 Top3
                {"reason": "Cookie 过期", "count": 2},
                {"reason": "超时", "count": 1},
            ],
        }
    """
    # range_hours 限定为 {1, 6, 24, 168} 之一（与 /distribution 风格一致）
    # 为什么不用 Query(le/ge)：枚举白名单更严格，避免任意数值输入
    if range_hours not in (1, 6, 24, 168):
        range_hours = 24
    now = _utcnow()
    cutoff = now - timedelta(hours=range_hours)

    from sqlalchemy import select

    from xianyu_hunter.infra.db_models import EventRow
    from xianyu_hunter.infra.yaml_config import get_config

    # 退避阈值来自全局配置（任务级覆盖无法在全局统计端点感知，用全局值近似）
    fail_pause_threshold = get_config().eval.auto_collect_fail_pause_threshold

    success_count = 0
    failed_count = 0
    is_paused = False

    with container.repo.engine.connect() as conn:
        # 成功事件：eval.scored + payload.data_source='official'
        # 用 json_extract 精确查询 JSON 字段 + SQL COUNT，避免 LIKE 全表扫描和 Python 层解析
        # 为什么用 json_extract：LIKE 无法区分 'official' vs 'official_xxx'，
        # 且 json_extract 在 SQLite 3.38+ 有查询优化；COUNT 不加载 payload 到内存
        from sqlalchemy import func
        success_count = conn.execute(
            select(func.count())
            .select_from(EventRow)
            .where(EventRow.type == _EVAL_SCORED_TYPE)
            .where(EventRow.created_at >= cutoff)
            .where(func.json_extract(EventRow.payload, '$.data_source') == 'official')
        ).scalar() or 0

        # 失败事件：collect.official.failed（需加载 payload 聚合 top_failures）
        failed_rows = conn.execute(
            select(EventRow.payload)
            .where(EventRow.type == "collect.official.failed")
            .where(EventRow.created_at >= cutoff)
        ).all()
        failed_count, error_counter = _aggregate_failed_events(failed_rows)

        # 判断当前是否处于退避暂停状态
        is_paused = _check_pause_status(conn, fail_pause_threshold)

    total = success_count + failed_count
    success_rate = (success_count / total) if total > 0 else 0

    return {
        "range_hours": range_hours,
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "success_rate": round(success_rate, 4),
        "is_paused": is_paused,
        "fail_pause_threshold": fail_pause_threshold,
        "top_failures": [
            {"reason": reason, "count": count}
            for reason, count in error_counter.most_common(3)
        ],
    }


# ==== evaluations_distribution 辅助函数 ====
def _load_dist_item_price_map(container: Container, events: list[dict]) -> dict[str, float]:
    """预加载 items 价格映射，用于热力图统计

    为什么按 item_id 批量查询：之前用 list_items(limit=5000) 全量加载"""
    dist_item_ids: set[str] = set()
    for ev in events:
        ev_payload = ev.get("payload") or {}
        iid = str(ev_payload.get("item_id") or ev.get("item_id") or "")
        if iid:
            dist_item_ids.add(iid)
    items = container.repo.list_items_by_ids(list(dist_item_ids)) if dist_item_ids else []
    item_price_map: dict[str, float] = {}
    for it in items:
        iid = it.get("item_id") or it.get("id")
        price = it.get("price")
        if iid and price is not None:
            try:
                item_price_map[str(iid)] = float(price)
            except (TypeError, ValueError):
                pass
    return item_price_map


def _is_within_eval_cutoff(e: dict, cutoff: Any) -> bool:
    """检查事件是否在统计时间窗口内（有合法时间戳且不早于 cutoff）

    拆分自 _collect_dist_eval_records：将时间戳解析 + cutoff 判断收敛到单一函数，
    降低主循环嵌套层级"""
    ts = e.get("created_at", "")
    if not ts:
        return False
    d = to_datetime(ts)
    return d is not None and d >= cutoff


def _resolve_eval_price_from_payload(
    payload: dict, e: dict, item_price_map: dict[str, float],
) -> float | None:
    """从 item_price_map 或 payload.item_price 解析价格

    优先用 item_price_map（items 表结构化数据），其次 payload 中的 item_price
    （_enrich_eval_with_item 补充的历史快照）。转换失败返回 None"""
    item_id = payload.get("item_id") or e.get("item_id")
    price = item_price_map.get(str(item_id)) if item_id else None
    if price is not None:
        return price
    raw_price = payload.get("item_price")
    if raw_price is None:
        return None
    try:
        return float(raw_price)
    except (TypeError, ValueError):
        return None


def _collect_dist_eval_records(
    events: list[dict],
    cutoff: Any,
    item_price_map: dict[str, float],
    task_id: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    include_out_of_range: bool = False,
) -> tuple[list[tuple[float, float | None]], int]:
    """收集评估记录（score, price_or_None），返回 (records, insufficient_count)

    score 必须有（非 None），price 可选。
    分数分布只依赖 score，热力图依赖 price × score。
    score=None（数据不足）的记录不计入分数分布，但计入 insufficient_count

    为什么只统计 eval.scored 而非所有 eval.*：NotifierHub 推送钉钉时会写入
    type="eval.passed"、payload=None、stage="notify" 的记录（hub.py 第 196-204 行），
    这些通知事件没有 score 字段，若用 startswith("eval.") 过滤会被误算为
    insufficient_count，导致前端误报"有 N 条评估记录因卖家信息缺失仅基于价格评估"
    """
    eval_records: list[tuple[float, float | None]] = []
    insufficient_count = 0  # 数据不足的评估数
    for e in events:
        if str(e.get("type", "")) != _EVAL_SCORED_TYPE:
            continue
        if not _is_within_eval_cutoff(e, cutoff):
            continue
        payload = e.get("payload") or {}
        if _match_task_id_filter(payload, e, task_id):
            continue
        price = _resolve_eval_price_from_payload(payload, e, item_price_map)
        price_payload = {**payload, "item_price": price}
        if _filter_price_range(price_payload, min_price, max_price, include_out_of_range):
            continue
        # score=None（数据不足）计入 insufficient_count，区别于转换失败（跳过）
        raw_score = payload.get("score")
        if raw_score is None:
            insufficient_count += 1
            continue
        score = _parse_eval_score(payload)
        if score is None:
            continue
        eval_records.append((score, price))
    return eval_records, insufficient_count


def _calc_marginal_score_and_result(
    eval_records: list[tuple[float, float | None]],
    score_bin_count: int,
    pass_threshold: float,
    auto_threshold: float,
) -> tuple[list[int], dict[str, int]]:
    """计算分数边际分布 + 结果分类（只依赖 score，不依赖 price）

    阈值从实时配置读取，确保与配置页面一致"""
    marginal_score = [0] * score_bin_count
    result_totals: dict[str, int] = {"pass": 0, "auto": 0, "fail": 0}
    smin, smax = 0.0, 100.0
    for score, _ in eval_records:
        si = int((score - smin) / (smax - smin) * score_bin_count)
        si = max(0, min(score_bin_count - 1, si))
        marginal_score[si] += 1
        if score >= auto_threshold:
            result_totals["auto"] += 1
        elif score >= pass_threshold:
            result_totals["pass"] += 1
        else:
            result_totals["fail"] += 1
    return marginal_score, result_totals


def _compute_log_price_bounds(
    prices: list[float],
) -> tuple[float, float, float, float, list[float]]:
    """计算对数价格桶边界，返回 (pmin, pmax, log_pmin, log_pmax, price_range)

    拆分自 _build_2d_buckets：将边界计算（含 pmin==pmax 和 log_pmax==log_pmin
    两个边界情况处理）收敛到独立函数，降低主函数条件分支数"""
    pmin = max(1.0, min(prices))
    pmax = max(prices)
    if pmin == pmax:
        pmin = max(1.0, pmin * 0.9)
        pmax = pmax * 1.1
    log_pmin = math.log10(pmin)
    log_pmax = math.log10(pmax)
    if log_pmax == log_pmin:
        log_pmax = log_pmin + 0.1
    return pmin, pmax, log_pmin, log_pmax, [round(pmin, 2), round(pmax, 2)]


def _init_2d_buckets(
    score_bin_count: int, price_bin_count: int,
) -> list[list[dict[str, int]]]:
    """初始化二维桶，每个桶包含 count/pass/auto/fail 计数

    拆分自 _build_2d_buckets：将嵌套列表推导提取为独立函数，
    避免嵌套推导增加认知复杂度"""
    return [
        [{"count": 0, "pass": 0, "auto": 0, "fail": 0} for _ in range(price_bin_count)]
        for _ in range(score_bin_count)
    ]


def _compute_price_bin_index(
    price: float, pmin: float, pmax: float,
    log_pmin: float, log_pmax: float, price_bin_count: int,
) -> int:
    """计算价格在对数桶中的索引

    拆分自 _build_2d_buckets：将 if/else 分支 + 对数计算提取为独立函数"""
    if pmin <= price <= pmax:
        log_p = math.log10(price)
        pi = int((log_p - log_pmin) / (log_pmax - log_pmin) * price_bin_count)
        return max(0, min(price_bin_count - 1, pi))
    return price_bin_count - 1


def _classify_score_result(
    score: float, pass_threshold: float, auto_threshold: float,
) -> str:
    """按阈值分类评估结果，返回 "auto"/"pass"/"fail"

    拆分自 _build_2d_buckets：将 if/elif/else 链提取为独立函数"""
    if score >= auto_threshold:
        return "auto"
    if score >= pass_threshold:
        return "pass"
    return "fail"


def _sum_price_marginals(
    buckets: list[list[dict[str, int]]],
    score_bin_count: int, price_bin_count: int,
) -> list[int]:
    """按价格桶汇总所有分数桶的 count

    拆分自 _build_2d_buckets：将嵌套推导（list comp + generator in sum）
    提取为独立函数，避免嵌套推导增加认知复杂度"""
    return [
        sum(buckets[si][pi]["count"] for si in range(score_bin_count))
        for pi in range(price_bin_count)
    ]


def _build_2d_buckets(
    eval_records: list[tuple[float, float | None]],
    score_bin_count: int,
    price_bin_count: int,
    pass_threshold: float,
    auto_threshold: float,
) -> tuple[list[list[dict[str, int]]], list[int], list[float]]:
    """构建二维热力图桶，返回 (buckets, marginal_price, price_range)

    价格范围：对数桶（闲鱼商品价格跨 4 个数量级：1元 ~ 1万元）。
    无价格数据时返回空 buckets 和零值 marginal_price。"""
    pairs_with_price: list[tuple[float, float]] = [
        (p, s) for s, p in eval_records if p is not None
    ]
    if not pairs_with_price:
        # 无价格数据时：热力图为空，但分数分布仍有数据
        return [], [0] * price_bin_count, [0.0, 0.0]

    prices = [p for p, _ in pairs_with_price]
    pmin, pmax, log_pmin, log_pmax, price_range = _compute_log_price_bounds(prices)
    buckets = _init_2d_buckets(score_bin_count, price_bin_count)
    smin, smax = 0.0, 100.0
    for price, score in pairs_with_price:
        pi = _compute_price_bin_index(
            price, pmin, pmax, log_pmin, log_pmax, price_bin_count,
        )
        # 分数桶
        si = int((score - smin) / (smax - smin) * score_bin_count)
        si = max(0, min(score_bin_count - 1, si))
        buckets[si][pi]["count"] += 1
        buckets[si][pi][_classify_score_result(score, pass_threshold, auto_threshold)] += 1

    marginal_price = _sum_price_marginals(buckets, score_bin_count, price_bin_count)
    return buckets, marginal_price, price_range


def _build_distribution_5bin(marginal_score: list[int]) -> list[dict[str, Any]]:
    """F-15：5 档分布（0-20/20-40/40-60/60-80/80-100），便于前端直方图直接消费

    使用边界检查避免 marginal_score 长度不足时越界"""
    def _bin_pair_sum(i: int, j: int) -> int:
        return (marginal_score[i] if len(marginal_score) > i else 0) + \
               (marginal_score[j] if len(marginal_score) > j else 0)
    return [
        {"range": "0-20", "count": _bin_pair_sum(0, 1)},
        {"range": "20-40", "count": _bin_pair_sum(2, 3)},
        {"range": "40-60", "count": _bin_pair_sum(4, 5)},
        {"range": "60-80", "count": _bin_pair_sum(6, 7)},
        {"range": "80-100", "count": _bin_pair_sum(8, 9)},
    ]


def _compute_passing_count(marginal_score: list[int], threshold: float) -> float:
    """计算在指定阈值下的通过数量（桶内线性插值）

    threshold 右侧的分数视为通过；桶内 straddle threshold 时按比例计算。
    拆分自 _calc_suggested_threshold：两个循环（二分搜索 + 最终计算）
    复用同一逻辑，消除重复代码并降低嵌套"""
    passing = 0
    for i in range(len(marginal_score)):
        bin_low = i * 10
        bin_high = (i + 1) * 10
        if threshold <= bin_low:
            # 整个桶都在阈值之上，全部通过
            passing += marginal_score[i] or 0
        elif threshold < bin_high:
            # 桶内线性插值：threshold 右侧部分通过
            passing += (marginal_score[i] or 0) * (bin_high - threshold) / 10
    return passing


def _calc_suggested_threshold(
    marginal_score: list[int], total: int,
) -> tuple[int, float]:
    """F-15：二分查找建议阈值——找到使通过率最接近 75% 的分数

    通过率随阈值单调递减，因此二分查找收敛到目标通过率对应的分数。
    无数据时使用配置的 pass_score，避免硬编码导致与实际配置不一致"""
    target_rate = 0.75
    if total == 0:
        return get_config().eval.pass_score, 0.75

    lo, hi = 0.0, 100.0
    for _ in range(30):
        mid = (lo + hi) / 2
        rate = _compute_passing_count(marginal_score, mid) / total
        if rate > target_rate:
            lo = mid
        else:
            hi = mid
    suggested_score = round((lo + hi) / 2)
    # 计算该阈值下的实际通过率
    actual_passing = _compute_passing_count(marginal_score, suggested_score)
    actual_pass_rate = round(actual_passing / total, 2)
    return suggested_score, actual_pass_rate


# ============== P3-UX-09 评估分分布 API ==============
@router.get("/distribution")
def evaluations_distribution(
    request: Request,
    range_hours: int = 168,
    price_bin_count: int = 10,
    score_bin_count: int = 10,
    task_id: str | None = Query(None, description="任务 ID 模糊匹配；用于与评估列表统计口径一致"),
    min_price: float | None = Query(None, ge=0, description="价格下限（含）。未传但传了 task_id 时自动从任务配置读取"),
    max_price: float | None = Query(None, ge=0, description="价格上限（含）。未传但传了 task_id 时自动从任务配置读取"),
    include_out_of_range: bool = Query(False, description="是否显示超出任务价格范围的历史商品"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """P3-UX-09：评估分 × 价格的二维分布

    Args:
        range_hours: 多久内的评估（默认 7 天 = 168h）
        price_bin_count: 价格桶数（X 轴 10 桶）
        score_bin_count: 分数桶数（Y 轴 10 桶，每桶 10 分）

    Returns:
        {
          "range_hours": 168,
          "price_bin_count": 10,
          "score_bin_count": 10,
          "price_range": [0, 5000],     # 价格区间 [min, max]
          "score_range": [0, 100],      # 分数区间
          "buckets": [                  # 10x10 二维桶
            # 桶 [score_idx][price_idx] = {"count": 5, "pass": 2, "auto": 0, "fail": 3}
            [[...], ...],
          ],
          "marginals": {
            "price": [...],   # 10 个价格桶总数
            "score": [...],   # 10 个分数桶总数
            "result": {"pass": N, "auto": N, "fail": N},
          },
          "total": int,
        }
    """
    if range_hours not in (24, 72, 168, 720):
        range_hours = 168
    price_bin_count = max(4, min(price_bin_count, 20))
    score_bin_count = max(5, min(score_bin_count, 20))
    now = _utcnow()
    cutoff = now - timedelta(hours=range_hours)

    # 从 events 拉 eval.*，并 join items 拿价格（item_id 在 payload.item_id）
    # 修复：之前用 list_events(limit=5000) + list_items(limit=5000) 全量加载，
    # 改为按 type 前缀过滤 events，按涉及 item_id 批量查询 items
    # 多用户隔离：仅统计当前账号的评估事件
    user_id = getattr(request.state, "user_id", None)
    events, _ = container.repo.list_events_by_type_prefix(
        type_prefix=_EVAL_TYPE_PREFIX, user_id=user_id,
    )
    min_price, max_price = _apply_task_price_fallback(
        container, task_id, min_price, max_price, include_out_of_range
    )
    item_price_map = _load_dist_item_price_map(container, events)

    eval_records, insufficient_count = _collect_dist_eval_records(
        events,
        cutoff,
        item_price_map,
        task_id=task_id,
        min_price=min_price,
        max_price=max_price,
        include_out_of_range=include_out_of_range,
    )

    # total = 所有有 score 的评估数（不要求有 price）
    total = len(eval_records)

    # 阈值从实时配置读取，确保与配置页面一致
    eval_cfg = get_config().eval
    pass_threshold = eval_cfg.pass_score
    auto_threshold = eval_cfg.auto_buy_score

    marginal_score, result_totals = _calc_marginal_score_and_result(
        eval_records, score_bin_count, pass_threshold, auto_threshold
    )

    buckets, marginal_price, price_range = _build_2d_buckets(
        eval_records, score_bin_count, price_bin_count, pass_threshold, auto_threshold
    )

    distribution_5bin = _build_distribution_5bin(marginal_score)

    suggested_score, actual_pass_rate = _calc_suggested_threshold(marginal_score, total)
    suggested_threshold = {"score": suggested_score, "pass_rate": actual_pass_rate}

    return {
        "range_hours": range_hours,
        "price_bin_count": price_bin_count,
        "score_bin_count": score_bin_count,
        "price_range": price_range,
        "score_range": [0, 100],
        "buckets": buckets,
        "marginals": {
            "price": marginal_price,
            "score": marginal_score,
            "result": result_totals,
        },
        "total": total,
        "insufficient_count": insufficient_count,
        "distribution": distribution_5bin,
        "suggested_threshold": suggested_threshold,
        # 返回当前生效的阈值，前端据此动态显示分类标签
        "thresholds": {"pass_score": pass_threshold, "auto_buy_score": auto_threshold},
    }


# ============== F-12 卖家历史价格趋势 ==============
# ==== seller_price_trend 辅助函数 ====
def _group_prices_by_date(seller_items: list[dict], cutoff) -> dict[str, list[float]]:
    """按发布日期分组商品价格

    优先用 publish_time，缺失时用 first_seen；
    过滤掉无时间/无价格/转换失败/早于 cutoff 的商品"""
    daily: dict[str, list[float]] = {}
    for it in seller_items:
        ts = it.get("publish_time") or it.get("first_seen")
        if not ts:
            continue
        d = to_datetime(ts)
        if d is None or d < cutoff:
            continue
        price = it.get("price")
        if price is None:
            continue
        try:
            p = float(price)
        except (TypeError, ValueError):
            continue
        date_key = d.strftime("%Y-%m-%d")
        daily.setdefault(date_key, []).append(p)
    return daily


def _calc_price_points(daily: dict[str, list[float]]) -> list[dict[str, Any]]:
    """按日期排序并计算每日价格统计值（avg/min/max/count）"""
    price_points: list[dict[str, Any]] = []
    for date_key in sorted(daily.keys()):
        prices = daily[date_key]
        price_points.append({
            "date": date_key,
            "avg_price": round(sum(prices) / len(prices)),
            "min_price": round(min(prices)),
            "max_price": round(max(prices)),
            "count": len(prices),
        })
    return price_points


def _calc_current_avg(seller_items: list[dict]) -> int:
    """计算当前均价（所有有效价格商品的均价，无价格时返回 0）"""
    current_prices = [float(it["price"]) for it in seller_items if it.get("price") is not None]
    return round(sum(current_prices) / len(current_prices)) if current_prices else 0


def _determine_trend(price_points: list[dict[str, Any]]) -> str:
    """比较首尾 1/3 均价判断趋势方向

    变化超过 5% 才判定为趋势，避免微小波动误判"""
    if len(price_points) < 3:
        return "stable"
    n = len(price_points)
    first_third = price_points[: max(1, n // 3)]
    last_third = price_points[-max(1, n // 3):]
    first_avg = sum(p["avg_price"] for p in first_third) / len(first_third)
    last_avg = sum(p["avg_price"] for p in last_third) / len(last_third)
    if first_avg > 0 and (last_avg - first_avg) / first_avg > 0.05:
        return "up"
    if first_avg > 0 and (first_avg - last_avg) / first_avg > 0.05:
        return "down"
    return "stable"


@router.get("/seller-price-trend")
def seller_price_trend(
    seller_id: str = Query(..., description="卖家 ID"),
    range_days: int = Query(30, ge=7, le=90, description="统计天数"),
    request: Request = None,  # noqa: B008  # 兼容 seller_trend_for_item 内部调用（FastAPI 路由会注入非 None 值）
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-12：卖家历史价格趋势

    聚合该卖家所有在售商品的价格分布，按发布日期分组返回价格变化趋势。
    算法：
    1. 从 items 表查询 seller_id 匹配的商品
    2. 按 publish_time（或 first_seen）日期分组
    3. 每组计算 avg/min/max/count
    4. 比较首尾均价判断趋势方向
    """
    now = _utcnow()
    cutoff = now - timedelta(days=range_days)

    # 多用户隔离：仅查询当前账号的商品
    user_id = getattr(request.state, "user_id", None) if request is not None else None
    # 查询该卖家的所有商品（SQL 端按 seller_id 过滤，不加载全量 items 再 Python 过滤）
    seller_items = container.repo.list_items_by_seller(
        seller_id, limit=5000, user_id=user_id,
    ) or []

    if not seller_items:
        # 无数据时返回空结构，前端显示"暂无数据"
        return {
            "seller_id": seller_id,
            "items_count": 0,
            "price_points": [],
            "current_avg": 0,
            "trend": "stable",
        }

    daily = _group_prices_by_date(seller_items, cutoff)
    price_points = _calc_price_points(daily)
    current_avg = _calc_current_avg(seller_items)
    trend = _determine_trend(price_points)

    return {
        "seller_id": seller_id,
        "items_count": len(seller_items),
        "price_points": price_points,
        "current_avg": current_avg,
        "trend": trend,
    }


# ============== F-15 评估分布 + 阈值建议 ==============
# 注意：固定路径路由必须放在动态路径 /{item_id}/ 之前，否则 FastAPI 会把
# "threshold-suggestion" 当作 item_id 匹配到 /{item_id}/seller-trend
# ==== threshold_suggestion 辅助函数 ====
def _build_5bin_distribution(score_marginals: list[int]) -> dict[str, int]:
    """构建 5 档分数分布（0-20/20-40/40-60/60-80/80-100）

    每个 5 档对应 2 个 10 分 score_marginals 桶"""
    labels = ["0-20", "20-40", "40-60", "60-80", "80-100"]
    distribution: dict[str, int] = {}
    for bin_idx in range(5):
        low = score_marginals[bin_idx * 2] if bin_idx * 2 < len(score_marginals) else 0
        high = score_marginals[bin_idx * 2 + 1] if bin_idx * 2 + 1 < len(score_marginals) else 0
        distribution[labels[bin_idx]] = low + high
    return distribution


def _find_suggested_threshold(score_marginals: list[int], total: int, target_pass_rate: float) -> int:
    """从高分到低分累加，找到达到 target_pass_rate 的分数即为建议阈值

    score_marginals[i] 对应 [i*10, (i+1)*10) 分数段；
    在命中桶内线性插值估算精确阈值"""
    target_count = total * target_pass_rate
    accumulated = 0
    suggested_threshold = 100
    for i in range(len(score_marginals) - 1, -1, -1):
        bin_count = score_marginals[i] if i < len(score_marginals) else 0
        accumulated += bin_count
        if accumulated >= target_count:
            # 在该桶内线性插值估算精确阈值
            bin_low = i * 10
            # 桶内还需要多少条才达到目标
            excess = accumulated - target_count
            if bin_count > 0:
                # 从桶底开始，跳过 excess 条对应的分数
                ratio = excess / bin_count
                suggested_threshold = round(bin_low + ratio * 10)
            else:
                suggested_threshold = bin_low
            break
    return suggested_threshold


def _calc_current_pass_rate(score_marginals: list[int], total: int, current_pass: int) -> float:
    """计算当前配置阈值对应的通过率"""
    pass_bin = current_pass // 10  # score_marginals 索引
    pass_count = sum(score_marginals[i] for i in range(pass_bin, len(score_marginals)) if i < len(score_marginals))
    return round(pass_count / total, 2)


@router.get("/threshold-suggestion")
def threshold_suggestion(
    request: Request,
    target_pass_rate: float = Query(0.7, ge=0.1, le=0.95, description="目标通过率"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-15：基于评估分布反推建议阈值

    算法：从高分到低分累加，直到达到 target_pass_rate 对应的分数即为建议阈值。
    复用 distribution API 的 marginals.score 数据，不需要新的数据源。
    """
    # 复用 distribution API 获取分数分布（默认 7 天）
    # 多用户隔离：传递 request 以复用用户过滤逻辑
    dist_data = evaluations_distribution(
        range_hours=168,
        price_bin_count=10,
        score_bin_count=10,
        request=request,
        container=container,
    )

    total = dist_data.get("total", 0)
    score_marginals = dist_data.get("marginals", {}).get("score", [])

    # 5 档分布（0-20/20-40/40-60/60-80/80-100）
    distribution = _build_5bin_distribution(score_marginals)

    if total == 0:
        return {
            "suggested_threshold": get_config().eval.pass_score,
            "target_pass_rate": target_pass_rate,
            "current_pass_rate": 0.0,
            "distribution": distribution,
            "analysis": "暂无评估数据，使用当前配置阈值",
        }

    suggested_threshold = _find_suggested_threshold(score_marginals, total, target_pass_rate)

    # 当前通过率（使用配置的 pass_score 而非硬编码 60）
    current_pass = get_config().eval.pass_score
    current_pass_rate = _calc_current_pass_rate(score_marginals, total, current_pass)

    # 生成分析文本
    analysis = (
        f"当前阈值 {current_pass} 导致 {round(current_pass_rate * 100)}% 通过率，"
        f"建议调至 {suggested_threshold} 分可达到 {round(target_pass_rate * 100)}% 通过率"
    )

    return {
        "suggested_threshold": suggested_threshold,
        "target_pass_rate": target_pass_rate,
        "current_pass_rate": current_pass_rate,
        "distribution": distribution,
        "analysis": analysis,
    }


# ============== F-12 评估明细 → 卖家价格趋势 ==============
@router.get("/{item_id}/seller-trend")
def seller_trend_for_item(
    item_id: str,
    request: Request,
    range_days: int = Query(30, ge=7, le=90, description="统计天数"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-12：通过 item_id 查询卖家价格趋势

    前端在评估明细页点击"卖家价格趋势"时调用，无需用户手动输入 seller_id。
    先通过 item_id 查出 seller_id，再复用本模块的 seller_price_trend。
    优先从 items 表查询，若商品未入库则回退到事件 payload 中提取 seller_id。
    """
    seller_id: str | None = None

    # 多用户隔离：仅查询当前账号的商品和评估事件
    user_id = getattr(request.state, "user_id", None)
    # 策略1：优先从 items 表查询（数据更完整）
    # 修复：之前直接访问 engine，改为调用 Repository 方法
    item = container.repo.get_item(item_id, user_id=user_id)
    if item and item.get("seller_id"):
        seller_id = str(item["seller_id"])

    # 策略2：items 表无记录时，从事件 payload 回退（评估事件中包含 seller_id）
    if not seller_id:
        payload = container.repo.get_eval_payload_by_item(item_id, user_id=user_id)
        if payload:
            seller_id = payload.get("seller_id")

    if not seller_id:
        raise HTTPException(status_code=404, detail="未找到该商品的卖家信息（商品未入库且无评估事件）")

    # 复用本模块的 seller_price_trend（同返回格式，避免跨路由耦合）
    # 传递 request 以复用用户过滤逻辑
    return seller_price_trend(
        seller_id=seller_id,
        range_days=range_days,
        request=request,
        container=container,
    )


# ============== 评估反馈（P3: 反馈闭环） ==============

@router.post("/{item_id}/feedback")
def submit_eval_feedback(
    item_id: str,
    request: Request,
    feedback: str = Query(..., description="反馈类型: accurate / inaccurate / partial"),
    note: str | None = Query(None, description="可选反馈备注"),
    task_id: str | None = Query(None, description="可选：指定任务 ID（多任务同 item_id 时）"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """提交评估准确率反馈

    用户在评估明细页面标记评估结果是否准确，
    反馈数据写入 eval.scored 事件的 payload.feedback 字段，
    供后续分析评估准确率和优化阈值使用。

    反馈类型：
    - accurate：评估准确（评分与实际一致）
    - inaccurate：评估不准确（评分偏差大）
    - partial：部分准确（方向对但幅度偏）
    """
    if feedback not in ("accurate", "inaccurate", "partial"):
        raise HTTPException(status_code=400, detail="feedback 必须为 accurate/inaccurate/partial")

    # 多用户隔离：写入操作用 "default" 兜底
    user_id = getattr(request.state, "user_id", "default")
    # 查找该商品最新的评估事件
    event_type = _EVAL_SCORED_TYPE
    payload_updates: dict[str, Any] = {
        "feedback": feedback,
        "feedback_note": note or "",
        "feedback_at": _utcnow().isoformat(),
    }

    # 如果有 task_id，按 task_id + item_id 精确查找
    if task_id:
        updated = container.repo.update_eval_payload_by_keys(
            task_id, item_id, event_type, payload_updates, user_id=user_id,
        )
    else:
        # 无 task_id 时，查找该 item_id 最新的 eval.scored 事件
        payload = container.repo.get_eval_payload_by_item(item_id, user_id=user_id)
        if not payload:
            raise HTTPException(status_code=404, detail=f"未找到商品 {item_id} 的评估记录")
        # 获取 task_id 后更新
        task_id_in_payload = payload.get("task_id", "")
        if task_id_in_payload:
            updated = container.repo.update_eval_payload_by_keys(
                task_id_in_payload, item_id, event_type, payload_updates, user_id=user_id,
            )
        else:
            raise HTTPException(status_code=404, detail="评估记录缺少 task_id，无法更新")

    if not updated:
        raise HTTPException(status_code=404, detail=f"未找到商品 {item_id} 的评估记录")

    logger.info("评估反馈: item=%s feedback=%s note=%s", item_id, feedback, note or "")

    return {"ok": True, "item_id": item_id, "feedback": feedback}


def _parse_eval_feedback(r: dict) -> str:
    """从评估事件 payload 解析反馈类型，无效 payload 返回空字符串

    payload 可能是 str（旧数据，需 json.loads）或 dict（新数据）或 None。
    拆分自 feedback_stats：把 try/except 嵌套抽离，主循环只剩分支统计"""
    payload = r.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}
    return (payload or {}).get("feedback", "")


def _accumulate_feedback_stats(rows: list[dict]) -> dict[str, int]:
    """聚合评估反馈统计：遍历 eval.scored 事件统计各反馈类型计数

    拆分自 feedback_stats：把 for + try/except + if/else 嵌套收敛到独立函数"""
    stats: dict[str, int] = {"accurate": 0, "inaccurate": 0, "partial": 0, "no_feedback": 0}
    for r in rows:
        fb = _parse_eval_feedback(r)
        if fb in stats:
            stats[fb] += 1
        else:
            stats["no_feedback"] += 1
    return stats


@router.get("/feedback/stats")
def feedback_stats(
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """评估反馈统计

    返回各反馈类型的数量和准确率，用于监控评估系统整体表现。
    """
    # 多用户隔离：仅统计当前账号的评估反馈
    user_id = getattr(request.state, "user_id", None)
    rows, _ = container.repo.list_events_by_type_prefix(_EVAL_SCORED_TYPE, limit=50000, user_id=user_id)
    stats = _accumulate_feedback_stats(rows)

    total_feedback = stats["accurate"] + stats["inaccurate"] + stats["partial"]
    accuracy_rate = stats["accurate"] / total_feedback if total_feedback > 0 else 0

    return {
        "stats": stats,
        "total_feedback": total_feedback,
        "accuracy_rate": round(accuracy_rate, 4),
    }


# ==== recompute_evaluations 辅助函数 ====
def _make_recompute_price_strategy_getter(container: Container):
    """创建任务级 PriceStrategy 缓存查询闭包

    recompute 应与 worker.py 搜索流水线一致，在评估前用 PriceStrategy.check 做价格门禁，
    超范围商品不写入 eval.scored 事件。
    为什么按 task_id 缓存：recompute 可能跨多个任务，避免重复构造 PriceStrategy"""
    _price_strategy_cache: dict[str, "PriceStrategy"] = {}
    _skip_price_check_task_ids: set[str] = set()

    def _get_price_strategy(tid: str | None) -> "PriceStrategy | None":
        """按 task_id 获取任务级 PriceStrategy。task_id 为空或任务不存在时返回 None（跳过门禁）"""
        if not tid:
            return None
        if tid in _skip_price_check_task_ids:
            return None
        if tid in _price_strategy_cache:
            return _price_strategy_cache[tid]
        try:
            task_raw = container.repo.get_task(tid)
            if not task_raw:
                _skip_price_check_task_ids.add(tid)
                return None
            ps = container.build_task_price_strategy(task_raw)
            _price_strategy_cache[tid] = ps
            return ps
        except Exception as e:
            logger.warning(f"recompute 读取任务 {tid} 价格策略失败，跳过门禁: {e}")
            _skip_price_check_task_ids.add(tid)
            return None

    return _get_price_strategy


def _determine_eval_level(eval_result) -> str:
    """根据评估结果确定事件日志级别

    与 worker.py 保持一致：通过=info，极端风险=err，其他=warn；UNKNOWN 兜底为 warn"""
    if eval_result.is_passed:
        level = "info"
    elif eval_result.risk_level != RiskLevel.EXTREME:
        level = "warn"
    else:
        level = "err"
    if eval_result.risk_level == RiskLevel.UNKNOWN:
        level = "warn"
    return level


def _build_item_detail_from_display(item_id: str, display: dict):
    """从 task_links.display 构造 ItemDetail（recompute 从 task_links 生成评估时使用）"""
    from xianyu_hunter.domain.item import ItemDetail
    price_val = display.get("price")
    # price 为 None 时用 0.0 兜底，避免 ItemDetail 构造失败
    price_float = float(price_val) if price_val is not None else 0.0
    return ItemDetail(
        id=str(item_id),
        title=str(display.get("title") or ""),
        price=price_float,
        region=str(display.get("region") or ""),
        seller_id=str(display.get("seller_id") or ""),
        seller_nick=str(display.get("seller_nick") or ""),
        thumb_url=str(display.get("thumb_url") or ""),
        is_sold=bool(display.get("is_sold", False)),
        want_cnt=int(display.get("want_cnt") or 0),
        view_cnt=int(display.get("view_cnt") or 0),
        description="",
    )


def _upsert_item_from_link_display(
    container: Container,
    item_id: str,
    link: dict,
    display: dict,
    price_float: float,
    task_id: str | None,
    user_id: str | None = None,
) -> bool:
    """补写 items 表：recompute 从 task_links 生成评估时同步写入 items 表

    避免 eval.* 事件引用的 item_id 在 items 表中不存在（孤儿数据）。
    返回 True 表示写入成功，False 表示失败（已记录日志）。"""
    try:
        container.repo.upsert_item({
            "id": str(item_id),
            "task_id": link.get("task_id") or task_id or "",
            "title": str(display.get("title") or ""),
            "price": price_float,
            "region": str(display.get("region") or ""),
            "seller_id": str(display.get("seller_id") or ""),
            "want_cnt": int(display.get("want_cnt") or 0),
            "view_cnt": int(display.get("view_cnt") or 0),
            "thumb_url": str(display.get("thumb_url") or ""),
            "image_urls": "[]",
            "description": "",
            "first_seen": _utcnow(),
            "last_seen": _utcnow(),
        }, user_id=user_id or "default")
        return True
    except Exception as e:
        logger.warning(f"补写 items 表失败 item_id={item_id}: {e}")
        return False


def _persist_eval_from_link(
    container: Container, link: dict, display: dict,
    detail, eval_result, task_id: str | None, user_id: str | None,
    item_id: str, existing_item_ids: set[str],
) -> None:
    """写入 eval 事件，并按需补写 items 表

    为什么补写 items：recompute 从 task_links 生成评估时同步写入 items 表，
    避免 eval.* 事件引用的 item_id 在 items 表中不存在（孤儿数据）。
    拆分自 _recompute_from_task_links：把持久化逻辑抽离，主循环只编排"""
    score_display = eval_result.score if eval_result.score is not None else "N/A"
    level = _determine_eval_level(eval_result)
    if item_id not in existing_item_ids:
        if _upsert_item_from_link_display(
            container, item_id, link, display, detail.price, task_id, user_id=user_id,
        ):
            existing_item_ids.add(item_id)
    # 使用 upsert 按 task_id+item_id 去重，防止重复评估
    container.repo.upsert_eval_event({
        "type": _EVAL_SCORED_TYPE,
        "task_id": link.get("task_id") or task_id or "",
        "item_id": detail.id,
        "stage": "eval",
        "level": level,
        "message": f"商品 {detail.id} 评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
        "payload": json.dumps({
            "task_id": link.get("task_id") or task_id or "",  # 写入 payload 供官方采集回查
            "item_id": detail.id,
            "item_title": detail.title,
            "item_price": detail.price,
            "seller_id": detail.seller_id,
            "seller_nick": detail.seller_nick,
            "score": eval_result.score,
            "risk_level": eval_result.risk_level.value,
            "dimension_scores": eval_result.dimension_scores,
            "reject_reasons": eval_result.reject_reasons,
            "is_passed": eval_result.is_passed,
            "data_quality": eval_result.data_quality,
        }, ensure_ascii=False, default=str),
    }, user_id=user_id or "default")


def _process_recompute_link(
    link: dict, container: Container, get_price_strategy, evaluator,
    task_id: str | None, user_id: str | None, existing_item_ids: set[str],
) -> str:
    """处理单条 task_link：构建评估对象 + 价格门禁 + 评估 + 持久化

    返回 generated/error/skip。
    拆分自 _recompute_from_task_links：把 for 循环体提取为独立函数，
    降低 try/except + 嵌套 if 的认知复杂度"""
    from xianyu_hunter.domain.seller import SellerProfile

    display = link.get("display") or {}
    item_id = link.get("link_key") or ""
    if not item_id:
        return "skip"
    try:
        detail = _build_item_detail_from_display(item_id, display)
        seller = SellerProfile(
            id=detail.seller_id or "unknown",
            nick=detail.seller_nick or "",
            credit_score=None,
            register_days=0,
            on_sale_count=0,
            sold_count=0,
        )
        effective_task_id = link.get("task_id") or task_id or ""
        # 复用 _is_recompute_price_skipped：日志前缀一致（都是 "recompute 跳过超范围商品"）
        # 为什么传 market_ctx=None：recompute 无现成市场数据，仅走 min/max 硬性规则
        if _is_recompute_price_skipped(get_price_strategy, effective_task_id, detail, item_id):
            return "skip"
        eval_result = evaluator.evaluate(detail, seller)
        _persist_eval_from_link(
            container, link, display, detail, eval_result,
            task_id, user_id, item_id, existing_item_ids,
        )
        return "generated"
    except Exception:
        return "error"


def _recompute_from_task_links(
    container: Container,
    task_id: str | None,
    get_price_strategy,
    user_id: str | None = None,
) -> dict[str, Any]:
    """无 eval.* 事件时，从 task_links 生成评估

    覆盖场景：live_search 写入了 task_links 但未触发评估（旧版本）"""
    link_rows = []
    if task_id:
        link_rows = container.repo.list_task_links(
            task_id=task_id, link_type="item", limit=500, user_id=user_id,
        )
    if not link_rows:
        return {"ok": True, "recomputed": 0, "message": "无评估记录需要重新计算，且无 task_links 可生成评估"}

    evaluator = container.evaluator
    generated = 0
    errors = 0
    # 批量检查哪些 item_id 还不在 items 表，避免逐条查询
    # recompute 从 task_links 生成评估时，需同步补写 items 表，防止孤儿数据
    all_link_item_ids = [link.get("link_key") for link in link_rows if link.get("link_key")]
    existing_item_ids = container.repo.items_exist(all_link_item_ids) if all_link_item_ids else set()

    for link in link_rows:
        result = _process_recompute_link(
            link, container, get_price_strategy, evaluator,
            task_id, user_id, existing_item_ids,
        )
        if result == "generated":
            generated += 1
        elif result == "error":
            errors += 1
        # "skip"：item_id 为空或价格门禁跳过，不计数

    return {
        "ok": True,
        "recomputed": generated,
        "skipped": 0,
        "errors": errors,
        "total": generated,
        "message": f"从 task_links 生成 {generated} 条评估记录（错误 {errors}）",
    }


def _load_recompute_item_map(
    container: Container, eval_events: list[dict],
) -> tuple[dict[str, dict], list[dict]]:
    """预加载 items 数据

    修复：之前用 list_items(limit=10000) 全量加载，改为按评估事件涉及的 item_id 批量查询"""
    recompute_item_ids = set()
    for e in eval_events:
        payload = e.get("payload") or {}
        iid = str(payload.get("item_id") or e.get("item_id") or "")
        if iid:
            recompute_item_ids.add(iid)
    item_rows = container.repo.list_items_by_ids(list(recompute_item_ids)) if recompute_item_ids else []
    item_map: dict[str, dict] = {}
    for it in item_rows:
        iid = str(it.get("item_id") or it.get("id") or "")
        if iid:
            item_map[iid] = it
    return item_map, item_rows


def _load_recompute_seller_map(
    container: Container, item_rows: list[dict],
) -> dict[str, dict]:
    """预加载 sellers

    修复：之前对每个 item 的 seller_id 单独调用 get_seller（N+1 查询），
    改为收集所有 seller_id 后批量查询"""
    seller_ids_set: set[str] = set()
    for it in item_rows:
        sid = str(it.get("seller_id") or "")
        if sid:
            seller_ids_set.add(sid)
    if not seller_ids_set:
        return {}
    seller_map: dict[str, dict] = {}
    seller_rows = container.repo.list_sellers_by_ids(list(seller_ids_set))
    for s in seller_rows:
        sid = str(s.get("id") or "")
        if sid:
            seller_map[sid] = s
    return seller_map


def _resolve_recompute_item_data(item_id: str, item_map: dict[str, dict], payload: dict) -> dict:
    """获取商品数据，items 表无记录时回退到 payload

    修复：之前直接 skip，导致 live 搜索写入 task_links 但未入 items 表的商品无法重算评估。
    回退字段由 _enrich_eval_with_item 从 task_links.display 补充"""
    item_data = item_map.get(item_id)
    if item_data:
        return item_data
    return {
        "title": payload.get("item_title") or "",
        "price": payload.get("item_price") or 0,
        "region": payload.get("region") or "",
        "seller_id": payload.get("seller_id") or "",
        "seller_nick": payload.get("seller_nick") or "",
    }


def _build_recompute_item_detail(
    item_id: str, item_data: dict, payload: dict, seller_data: dict,
):
    """重建 ItemDetail（仅包含评估所需字段）

    seller_nick 优先从 sellers 表取（ItemRow 无此字段），回退到 payload"""
    from xianyu_hunter.domain.item import ItemDetail
    seller_id = str(item_data.get("seller_id") or payload.get("seller_id") or "")
    return ItemDetail(
        id=item_id,
        title=str(item_data.get("title") or payload.get("item_title") or ""),
        price=float(item_data.get("price") or 0),
        region=str(item_data.get("region") or ""),
        seller_id=seller_id,
        seller_nick=str(seller_data.get("nick") or payload.get("seller_nick") or ""),
    )


def _build_recompute_seller_profile(seller_id: str, seller_data: dict):
    """重建 SellerProfile"""
    from xianyu_hunter.domain.seller import SellerProfile
    return SellerProfile(
        id=seller_id or "unknown",
        nick=str(seller_data.get("nick") or ""),
        credit_score=seller_data.get("credit_score"),
        register_days=int(seller_data.get("register_days") or 0),
        on_sale_count=int(seller_data.get("on_sale_count") or 0),
        sold_count=int(seller_data.get("sold_count") or 0),
        top_category=seller_data.get("top_category"),
        top_category_ratio=float(seller_data.get("top_category_ratio") or 0),
        post_count_30d=int(seller_data.get("post_count_30d") or 0),
        bad_review_count=int(seller_data.get("bad_review_count") or 0),
        in_blacklist=bool(seller_data.get("in_blacklist") or False),
    )


def _is_recompute_price_skipped(
    get_price_strategy, task_id: str, detail, item_id: str,
) -> bool:
    """价格门禁：与 worker.py 搜索流水线一致，超范围商品不重新评估

    为什么 skip 而非删除旧事件：recompute 语义是"重算"而非"清理"，
    保留旧事件供 include_out_of_range=True 审计；list_evaluations 的
    价格过滤会默认隐藏这些超范围商品"""
    price_strategy = get_price_strategy(task_id)
    if price_strategy is None:
        return False
    verdict = price_strategy.check(detail, market=None)
    if verdict.pass_:
        return False
    logger.info(
        "recompute 跳过超范围商品: item_id={}, price={}, reasons={}",
        item_id, detail.price, verdict.reasons,
    )
    return True


def _update_recompute_payload(payload: dict, eval_result) -> None:
    """更新 payload（保留原始字段，仅更新评分相关字段）"""
    payload["score"] = eval_result.score
    payload["risk_level"] = eval_result.risk_level.value
    payload["dimension_scores"] = eval_result.dimension_scores
    payload["reject_reasons"] = eval_result.reject_reasons
    payload["is_passed"] = eval_result.is_passed
    payload["data_quality"] = eval_result.data_quality
    payload["recomputed_at"] = _utcnow().isoformat()


def _persist_recomputed_eval(
    e: dict, container: Container, payload: dict, eval_result,
    detail, seller, effective_task_id: str, item_id: str, notify: bool,
) -> str:
    """更新 events 表，按需触发 EVAL_PASSED 事件

    返回 recomputed/notified/noop。
    为什么 notify 默认 False：recompute 是历史回算，可能批量重算大量历史数据，
    默认关闭避免刷爆群；用户主动回算想验证通知链路时由调用方传 True"""
    event_id = e.get("id")
    if not event_id:
        return "noop"
    container.repo.update_event_payload(event_id, json.dumps(payload, ensure_ascii=False, default=str))
    if notify and eval_result.is_passed:
        _publish_eval_passed_event(
            container, effective_task_id, item_id, detail, seller, eval_result,
            data_source="recompute",
        )
        return "notified"
    return "recomputed"


def _do_recompute_single_eval(
    e: dict,
    container: Container,
    item_map: dict[str, dict],
    seller_map: dict[str, dict],
    get_price_strategy,
    evaluator,
    task_id: str | None,
    notify: bool,
) -> str:
    """实际重算逻辑

    拆分自 _recompute_single_eval：把核心逻辑从 try/except 中拆出，
    降低嵌套层级；原函数仅负责异常兜底"""
    payload = e.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    item_id = str(payload.get("item_id") or e.get("item_id") or "")
    if not item_id:
        return "skipped"

    item_data = _resolve_recompute_item_data(item_id, item_map, payload)
    seller_id = str(item_data.get("seller_id") or payload.get("seller_id") or "")
    seller_data = seller_map.get(seller_id, {})

    detail = _build_recompute_item_detail(item_id, item_data, payload, seller_data)
    seller = _build_recompute_seller_profile(seller_id, seller_data)

    effective_task_id = str(payload.get("task_id") or e.get("task_id") or task_id or "")
    if _is_recompute_price_skipped(get_price_strategy, effective_task_id, detail, item_id):
        return "skipped"

    eval_result = evaluator.evaluate(detail, seller)
    _update_recompute_payload(payload, eval_result)

    return _persist_recomputed_eval(
        e, container, payload, eval_result, detail, seller,
        effective_task_id, item_id, notify,
    )


def _recompute_single_eval(
    e: dict,
    container: Container,
    item_map: dict[str, dict],
    seller_map: dict[str, dict],
    get_price_strategy,
    evaluator,
    task_id: str | None,
    notify: bool = False,
) -> str:
    """重新计算单条评估事件

    返回值：recomputed=已重算 / skipped=跳过 / error=异常 / noop=无 event_id 不计数"""
    try:
        return _do_recompute_single_eval(
            e, container, item_map, seller_map,
            get_price_strategy, evaluator, task_id, notify,
        )
    except Exception:
        return "error"


# ============== 历史评估重新计算 ==============
@router.post("/recompute")
def recompute_evaluations(
    request: Request,
    task_id: str | None = Query(None, description="可选：仅重新计算指定任务的评估"),
    notify: bool = Query(
        False,
        description="评估通过是否触发钉钉等通知。默认 False：recompute 是历史回算，"
        "避免批量重算刷爆通知群；用户主动回算想验证通知链路时传 True",
    ),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """用当前配置的评估规则重新计算历史评估数据

    读取 events 表中所有 eval.scored 事件，从 items + sellers 表重建
    ItemDetail 和 SellerProfile，用当前配置的 Evaluator 重新评分，
    更新 events 表的 payload。
    """
    evaluator = container.evaluator
    get_price_strategy = _make_recompute_price_strategy_getter(container)

    # 多用户隔离：仅重新计算当前账号的评估事件
    user_id = getattr(request.state, "user_id", None)
    # 拉取所有评估事件
    # 修复：之前用 list_events(limit=10000) 在 Python 端过滤，改为 SQL 端按 type 前缀过滤
    all_eval_events, _ = container.repo.list_events_by_type_prefix(
        type_prefix=_EVAL_TYPE_PREFIX, task_id=task_id, user_id=user_id,
    )
    eval_events = all_eval_events

    if not eval_events:
        # 没有 eval.* 事件时，从 task_links 生成评估
        # 覆盖场景：live_search 写入了 task_links 但未触发评估（旧版本）
        return _recompute_from_task_links(container, task_id, get_price_strategy, user_id=user_id)

    item_map, item_rows = _load_recompute_item_map(container, eval_events)
    seller_map = _load_recompute_seller_map(container, item_rows)

    recomputed = 0
    skipped = 0
    errors = 0
    notified = 0

    for e in eval_events:
        result = _recompute_single_eval(
            e, container, item_map, seller_map,
            get_price_strategy, evaluator, task_id,
            notify=notify,
        )
        if result == "recomputed":
            recomputed += 1
        elif result == "notified":
            notified += 1
            recomputed += 1
        elif result == "skipped":
            skipped += 1
        elif result == "error":
            errors += 1
        # "noop"：无 event_id，不增加任何计数

    return {
        "ok": True,
        "recomputed": recomputed,
        "notified": notified,
        "skipped": skipped,
        "errors": errors,
        "total": len(eval_events),
        "message": (
            f"已重新计算 {recomputed} 条评估记录（跳过 {skipped}，错误 {errors}）"
            + (f"，触发通知 {notified} 条" if notify else "")
        ),
    }


# ==== batch_evaluate_unevaluated 辅助函数 ====
def _make_batch_price_strategy_getter(container: Container):
    """创建任务级 PriceStrategy 缓存查询闭包（batch_evaluate 专用）

    batch_evaluate 应与 worker.py 一致做价格门禁，
    超范围商品不写入 eval.scored 事件，避免污染评估明细菜单。
    为什么按 task_id 缓存：可能跨多个任务，避免重复构造 PriceStrategy"""
    _price_strategy_cache: dict[str, "PriceStrategy"] = {}
    _skip_price_check_task_ids: set[str] = set()

    def _get_price_strategy(tid: str | None) -> "PriceStrategy | None":
        if not tid:
            return None
        if tid in _skip_price_check_task_ids:
            return None
        if tid in _price_strategy_cache:
            return _price_strategy_cache[tid]
        try:
            task_raw = container.repo.get_task(tid)
            if not task_raw:
                _skip_price_check_task_ids.add(tid)
                return None
            ps = container.build_task_price_strategy(task_raw)
            _price_strategy_cache[tid] = ps
            return ps
        except Exception as e:
            logger.warning(f"batch_evaluate 读取任务 {tid} 价格策略失败，跳过门禁: {e}")
            _skip_price_check_task_ids.add(tid)
            return None

    return _get_price_strategy


def _collect_evaluated_ids(container: Container, user_id: str | None = None) -> set[str]:
    """获取所有已评估的 item_id 集合"""
    eval_events, _ = container.repo.list_events_by_type_prefix(
        type_prefix=_EVAL_TYPE_PREFIX, user_id=user_id,
    )
    evaluated_ids: set[str] = set()
    for e in eval_events:
        payload = e.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                payload = {}
        iid = str(payload.get("item_id") or e.get("item_id") or "")
        if iid:
            evaluated_ids.add(iid)
    return evaluated_ids


def _load_batch_seller_map(container: Container, to_evaluate: list[dict]) -> dict[str, dict]:
    """预加载 sellers 数据（批量查询避免 N+1）"""
    seller_ids_set: set[str] = set()
    for it in to_evaluate:
        sid = str(it.get("seller_id") or "")
        if sid:
            seller_ids_set.add(sid)
    if not seller_ids_set:
        return {}
    seller_map: dict[str, dict] = {}
    seller_rows = container.repo.list_sellers_by_ids(list(seller_ids_set))
    for s in seller_rows:
        sid = str(s.get("id") or "")
        if sid:
            seller_map[sid] = s
    return seller_map


def _publish_eval_passed_event(
    container: Container,
    task_id: str,
    item_id: str,
    detail: Any,
    seller: Any,
    eval_result: Any,
    data_source: str = "",
) -> None:
    """评估通过 → 触发 EVAL_PASSED 事件，让 NotifierHub 推送钉钉等通知

    为什么独立工具函数而非复用 collection_service._publish_eval_passed_event：
    - 该函数被 batch_evaluate / recompute 两条路径共用，避免 payload 构造重复
    - 字段与 worker._publish_eval_passed_event 对齐，保证模板渲染一致
    - 用 getattr 安全访问 detail/seller 字段，兼容 ItemDetail 与 ItemRow 两种类型

    为什么用 publish_nowait：调用方在同步函数中，EventBus.run_forever 异步消费
    """
    bus = getattr(container, "event_bus", None)
    if bus is None:
        return
    payload: dict[str, Any] = {
        "item_id": item_id,
        "item_title": getattr(detail, "title", "") or "",
        "item_price": getattr(detail, "price", 0) or 0,
        "thumb_url": getattr(detail, "thumb_url", "") or "",
        "region": getattr(detail, "region", "") or "",
        "seller_id": getattr(detail, "seller_id", "") or "",
        "seller_nick": getattr(seller, "nick", "") or "",
        "score": getattr(eval_result, "score", 0),
        "risk_level": getattr(eval_result, "risk_level", RiskLevel.MEDIUM).value
                      if hasattr(getattr(eval_result, "risk_level", None), "value")
                      else str(getattr(eval_result, "risk_level", "medium")),
        "data_quality": getattr(eval_result, "data_quality", ""),
        "reject_reasons": getattr(eval_result, "reject_reasons", []) or [],
    }
    if data_source:
        payload["data_source"] = data_source
    try:
        bus.publish_nowait(
            Event(
                type=EventType.EVAL_PASSED,
                task_id=task_id,
                item_id=item_id,
                payload=payload,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to publish EVAL_PASSED item={}: {}", item_id, exc)


def _build_batch_item_detail(it: dict, seller_data: dict):
    """从 items 表行 + sellers 表数据构建 ItemDetail

    seller_nick 优先从 sellers 表取（ItemRow 无此字段），传入 seller_data 用于查询"""
    from xianyu_hunter.domain.item import ItemDetail
    return ItemDetail(
        id=str(it.get("id") or ""),
        title=str(it.get("title") or ""),
        price=float(it.get("price") or 0),
        region=str(it.get("region") or ""),
        seller_id=str(it.get("seller_id") or ""),
        seller_nick=str(seller_data.get("nick") or ""),
        thumb_url=str(it.get("thumb_url") or ""),
        want_cnt=int(it.get("want_cnt") or 0),
        view_cnt=int(it.get("view_cnt") or 0),
    )


def _build_batch_seller_profile(seller_id: str, seller_data: dict):
    """构建 SellerProfile（批量评估路径专用）"""
    from xianyu_hunter.domain.seller import SellerProfile
    return SellerProfile(
        id=seller_id or "unknown",
        nick=str(seller_data.get("nick") or ""),
        credit_score=seller_data.get("credit_score"),
        register_days=int(seller_data.get("register_days") or 0),
        on_sale_count=int(seller_data.get("on_sale_count") or 0),
        sold_count=int(seller_data.get("sold_count") or 0),
    )


def _is_batch_price_skipped(
    get_price_strategy, task_id: str, detail, item_id: str,
) -> bool:
    """价格门禁：与 worker.py 搜索流水线一致，超范围商品不写入 eval.scored 事件"""
    price_strategy = get_price_strategy(task_id)
    if price_strategy is None:
        return False
    verdict = price_strategy.check(detail, market=None)
    if verdict.pass_:
        return False
    logger.info(
        "batch_evaluate 跳过超范围商品: item_id={}, price={}, reasons={}",
        item_id, detail.price, verdict.reasons,
    )
    return True


def _persist_batch_eval_event(
    container: Container, item_id: str, effective_task_id: str,
    detail, eval_result, user_id: str | None,
) -> None:
    """写入 eval 事件，data_source=batch_unevaluated 标记来源便于追踪

    为什么用 upsert：按 task_id+item_id 去重，防止重复评估"""
    score_display = eval_result.score if eval_result.score is not None else "N/A"
    level = _determine_eval_level(eval_result)
    container.repo.upsert_eval_event({
        "type": _EVAL_SCORED_TYPE,
        "task_id": effective_task_id,
        "item_id": item_id,
        "stage": "eval",
        "level": level,
        "message": f"商品 {item_id} 批量评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
        "payload": json.dumps({
            "task_id": effective_task_id,
            "item_id": item_id,
            "item_title": detail.title,
            "item_price": detail.price,
            "seller_id": detail.seller_id,
            "seller_nick": detail.seller_nick,
            "score": eval_result.score,
            "risk_level": eval_result.risk_level.value,
            "dimension_scores": eval_result.dimension_scores,
            "reject_reasons": eval_result.reject_reasons,
            "is_passed": eval_result.is_passed,
            "data_quality": eval_result.data_quality,
            "data_source": "batch_unevaluated",
        }, ensure_ascii=False, default=str),
    }, user_id=user_id or "default")


def _do_evaluate_single_unevaluated_item(
    it: dict, container: Container, seller_map: dict[str, dict],
    get_price_strategy, evaluator, task_id: str | None,
    notify: bool, user_id: str | None,
) -> str:
    """实际评估逻辑

    拆分自 _evaluate_single_unevaluated_item：把核心逻辑从 try/except 中拆出，
    降低嵌套层级；原函数仅负责异常兜底"""
    item_id = str(it.get("id") or "")
    if not item_id:
        return "noop"
    seller_id = str(it.get("seller_id") or "")
    seller_data = seller_map.get(seller_id, {})
    detail = _build_batch_item_detail(it, seller_data)
    seller = _build_batch_seller_profile(seller_id, seller_data)

    effective_task_id = str(it.get("task_id") or task_id or "")
    if _is_batch_price_skipped(get_price_strategy, effective_task_id, detail, item_id):
        return "skipped"

    eval_result = evaluator.evaluate(detail, seller)
    _persist_batch_eval_event(container, item_id, effective_task_id, detail, eval_result, user_id)

    # 评估通过 → 触发 EVAL_PASSED 事件，让 NotifierHub 推送钉钉等通知
    # 为什么 notify 默认 True：与 collection_service 官方采集语义一致，
    # 用户主动触发的批量评估，通过的商品值得通知
    # 返回 "notified" 而非 "evaluated"：让调用方统计通知数
    if notify and eval_result.is_passed:
        _publish_eval_passed_event(
            container, effective_task_id, item_id, detail, seller, eval_result,
            data_source="batch_unevaluated",
        )
        return "notified"
    return "evaluated"


def _evaluate_single_unevaluated_item(
    it: dict,
    container: Container,
    seller_map: dict[str, dict],
    get_price_strategy,
    evaluator,
    task_id: str | None,
    notify: bool = True,
    user_id: str | None = None,
) -> str:
    """评估单个未评估商品并写入 eval.* 事件

    返回值：evaluated=已评估 / skipped=价格门禁跳过 / error=异常 / noop=item_id 为空

    为什么默认 notify=True：批量评估是用户主动触发的新评估，评估通过应该通知用户
    （与官方采集语义一致）；recompute 是历史回算，默认不通知，由调用方传 False
    """
    try:
        return _do_evaluate_single_unevaluated_item(
            it, container, seller_map, get_price_strategy, evaluator,
            task_id, notify, user_id,
        )
    except Exception as e:
        logger.warning(f"批量评估失败 item_id={it.get('id')}: {e}")
        return "error"


@router.post("/batch-evaluate-unevaluated")
def batch_evaluate_unevaluated(
    request: Request,
    task_id: str | None = Query(None, description="可选：仅评估指定任务的商品"),
    limit: int = Query(200, ge=1, le=1000, description="单次最大评估数量"),
    notify: bool = Query(
        True,
        description="评估通过是否触发钉钉等通知。默认 True：批量评估是用户主动触发的新评估，"
        "通过的商品值得通知；批量评估大量商品时可传 False 关闭避免刷爆群",
    ),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量评估 items 表中未被评估的商品

    解决商品采集与评估是独立流程导致的大量商品未被评估的问题。
    查询 items 表中不在 eval.* 事件中的商品，用当前评估规则批量评估。
    """
    evaluator = container.evaluator
    get_price_strategy = _make_batch_price_strategy_getter(container)

    # 多用户隔离：仅评估当前账号的商品
    user_id = getattr(request.state, "user_id", None)
    # 1. 获取所有已评估的 item_id 集合
    evaluated_ids = _collect_evaluated_ids(container, user_id=user_id)

    # 2. 获取 items 表中所有商品（按 task_id 过滤）
    # items 表量级可控（通常 < 1000），一次查询即可
    all_items = container.repo.list_items(task_id=task_id, limit=5000, offset=0, user_id=user_id)
    unevaluated = [it for it in all_items if str(it.get("id") or "") not in evaluated_ids]

    if not unevaluated:
        return {
            "ok": True,
            "evaluated": 0,
            "skipped": 0,
            "errors": 0,
            "total": 0,
            "message": "所有商品均已评估，无需批量评估",
        }

    # 限制单次评估数量，避免长时间阻塞
    to_evaluate = unevaluated[:limit]
    skipped = len(unevaluated) - len(to_evaluate)

    # 3. 预加载 sellers 数据
    seller_map = _load_batch_seller_map(container, to_evaluate)

    # 4. 遍历评估并写入 eval.* 事件
    evaluated = 0
    errors = 0
    notified = 0
    for it in to_evaluate:
        result = _evaluate_single_unevaluated_item(
            it, container, seller_map, get_price_strategy, evaluator, task_id,
            notify=notify, user_id=user_id,
        )
        if result == "notified":
            notified += 1
            evaluated += 1
        elif result == "evaluated":
            evaluated += 1
        elif result == "skipped":
            skipped += 1
        elif result == "error":
            errors += 1
        # "noop"：item_id 为空，不增加任何计数

    return {
        "ok": True,
        "evaluated": evaluated,
        "notified": notified,
        "skipped": skipped,
        "errors": errors,
        "total": evaluated,
        "message": (
            f"已批量评估 {evaluated} 条未评估商品（跳过 {skipped}，错误 {errors}）"
            + (f"，触发通知 {notified} 条" if notify else "")
        ),
    }


# ============== 官方页面采集 + 重新评估 ==============
# 解决评估明细页依赖本地采集数据信息有限的问题：
# 优先访问闲鱼官方商品详情页+卖家主页，获取完整权威数据后重新评估

# 官方采集所需的身份 Cookie（与 live_search 一致，确保登录态有效）
_OFFICIAL_COLLECT_IDENTITY_COOKIES = ("cookie2", "sgcookie", "unb")


async def _ensure_official_collect_cookies(container: Container) -> None:
    from xianyu_hunter.modules.collection_service import (
        CollectionError,
        ItemCollectionService,
    )

    try:
        await ItemCollectionService(container).ensure_official_cookies()
    except CollectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return


async def _extract_reviews_from_page(page) -> list[str]:
    """从商品详情页 DOM 中尝试提取评价/留言信息

    闲鱼详情页的评价模块结构可能随版本变化，使用宽松选择器 + try-except，
    提取失败时返回空列表，不影响主采集流程。
    """
    reviews: list[str] = []
    # 候选选择器：覆盖闲鱼详情页可能的评价/留言/评论模块命名
    review_selectors = [
        "[class*='review'] [class*='item']",
        "[class*='comment'] [class*='item']",
        "[class*='evaluation'] [class*='item']",
        "[class*='message'] [class*='item']",
    ]
    for sel in review_selectors:
        try:
            els = await page.query_selector_all(sel)
            for el in els[:10]:  # 最多取 10 条，避免过多影响性能
                text = (await el.inner_text()).strip()
                if text and len(text) > 5:  # 过滤过短的无效文本
                    reviews.append(text)
            if reviews:
                break
        except Exception:
            continue
    return reviews


async def _collect_official_and_evaluate(
    container: Container,
    item_id: str,
    task_id: str | None = None,
) -> dict[str, Any]:
    from xianyu_hunter.modules.collection_service import (
        CollectionError,
        CollectionMode,
        ItemCollectionService,
    )

    try:
        result = await ItemCollectionService(container).collect(
            item_id,
            task_id=task_id,
            mode=CollectionMode.OFFICIAL_FULL,
            source="official",
        )
    except CollectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    detail = result.detail
    seller = result.seller
    eval_result = result.evaluation
    if detail is None or eval_result is None:
        raise HTTPException(status_code=502, detail=f"Official collection {item_id} returned incomplete result")

    return {
        "ok": True,
        "item_id": item_id,
        "collected": True,
        "item": {
            "title": detail.title,
            "price": detail.price,
            "description": detail.description or "",
            "image_urls": detail.image_urls or [],
            "thumb_url": detail.thumb_url or "",
            "region": detail.region or "",
            "seller_id": detail.seller_id or "",
            "want_cnt": detail.want_cnt,
            "view_cnt": detail.view_cnt,
        },
        "seller": {
            "id": seller.id if seller else "",
            "nick": seller.nick if seller else "",
            "credit_score": seller.credit_score if seller else None,
            "register_days": seller.register_days if seller else 0,
            "on_sale_count": seller.on_sale_count if seller else 0,
            "sold_count": seller.sold_count if seller else 0,
        },
        "reviews": result.reviews,
        "evaluation": {
            "score": eval_result.score,
            "risk_level": eval_result.risk_level.value,
            "dimension_scores": eval_result.dimension_scores,
            "reject_reasons": eval_result.reject_reasons,
            "is_passed": eval_result.is_passed,
            "data_quality": eval_result.data_quality,
            "data_source": "official",
        },
    }


class BatchCollectRequest(BaseModel):
    """批量官方采集请求体"""
    item_ids: list[str] = Field(..., min_length=1, max_length=50, description="商品 ID 列表，最多 50 个")


# ==== batch_collect_official 辅助函数 ====
def _classify_http_error_code(status_code: int) -> str:
    """根据 HTTP 状态码分类失败原因，方便调用方决定是否重试

    - 410: 商品已下架/不存在 → 不应重试
    - 其他业务错误 → 标记为 unknown，由调用方自行判断"""
    if status_code == 410:
        return "item_not_found"
    return "unknown"


def _classify_exception_error(e: Exception) -> str:
    """区分网络错误与未知错误

    网络错误通常可重试，未知错误不应盲目重试"""
    if isinstance(e, (TimeoutError, ConnectionError, OSError)):
        return "network_error"
    err_str = str(e)
    if "Timeout" in err_str or "ConnectError" in err_str or "Connection" in err_str:
        return "network_error"
    return "unknown"


@router.post("/batch-collect-official")
async def batch_collect_official(
    body: BatchCollectRequest = Body(...),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量官方采集+评估

    串行采集每个商品（避免并发触发反爬虫），逐个返回结果。
    单个失败不中断整体流程，最终汇总成功/失败数。
    """
    item_ids = body.item_ids
    if not container.collector:
        raise HTTPException(
            status_code=503,
            detail="官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动",
        )
    if not container.browser:
        raise HTTPException(
            status_code=503,
            detail="浏览器实例未初始化，请重启服务",
        )

    results: list[dict] = []
    succeeded = 0
    failed = 0

    for iid in item_ids:
        try:
            async with container.browser_lock:
                result = await _collect_official_and_evaluate(container, iid)
            results.append(result)
            succeeded += 1
        except HTTPException as e:
            # Cookie 失效类错误立即中断：后续商品也会逐个失败，浪费时间
            # - 403: Cookie 不完整（_ensure_official_collect_cookies 检测到缺失关键 cookie）
            # - 440: Cookie 过期/未刷新（重定向到登录页/首页）
            # - 441: 触发验证码（RGV587 反爬）
            # 注意：不检查 401——project_memory 要求闲鱼会话失效统一用 403/440/441，
            # 401 会触发前端 axios 全局登出逻辑（误判为系统认证失效）
            if e.status_code in (403, 440, 441):
                raise
            error_code = _classify_http_error_code(e.status_code)
            results.append({
                "ok": False, "item_id": iid, "error": e.detail,
                "error_code": error_code,
            })
            failed += 1
        except Exception as e:
            logger.exception("批量采集失败 item={}: {}", iid, e)
            err_str = str(e)
            error_code = _classify_exception_error(e)
            results.append({
                "ok": False, "item_id": iid, "error": err_str,
                "error_code": error_code,
            })
            failed += 1

    return {
        "ok": True,
        "total": len(item_ids),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
        "message": f"批量采集完成：成功 {succeeded}，失败 {failed}",
    }


@router.post("/{item_id}/collect-official")
async def collect_official(
    item_id: str,
    task_id: str | None = Query(None, description="可选：指定任务 ID"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """单条官方采集+评估

    访问闲鱼官方商品详情页和卖家主页，采集完整数据后重新评估。
    采集结果持久化到 items/sellers/events 表，评估标记 data_source=official。
    """
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id 必填")
    if not container.collector:
        raise HTTPException(
            status_code=503,
            detail="官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动",
        )
    if not container.browser:
        raise HTTPException(
            status_code=503,
            detail="浏览器实例未初始化，请重启服务",
        )

    try:
        async with container.browser_lock:
            result = await _collect_official_and_evaluate(container, item_id, task_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("官方采集失败 item={}: {}", item_id, e)
        err_msg = str(e)
        if "TargetClosed" in err_msg or "Browser has been closed" in err_msg:
            raise HTTPException(status_code=502, detail="浏览器连接已断开，请重启服务后重试")
        if "RGV587" in err_msg:
            # 反爬触发统一用 441，区别于 403（cookie 缺失）和 502（系统故障）
            raise HTTPException(status_code=441, detail="搜索令牌临时过期，请稍后重试；若持续失败请重新登录闲鱼")
        if "Connection closed" in err_msg:
            raise HTTPException(status_code=502, detail="浏览器连接异常，请重启服务后重试")
        raise HTTPException(status_code=502, detail=f"官方采集失败: {err_msg}")
