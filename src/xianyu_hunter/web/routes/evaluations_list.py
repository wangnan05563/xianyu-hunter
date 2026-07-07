"""评估列表 API — 列表查询 + 数据丰富 + 过滤 + 成色标签

从 api_evaluations.py 拆分，包含：
- list_evaluations 路由及其辅助函数（过滤、丰富、分页）
- latest_for_item 路由
- 成色标签分析（_enrich_condition_tags 及辅助函数）
- 脏数据清洗委托给 evaluations_data_cleaner
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from xianyu_hunter.container import Container
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.modules.collector_utils import normalize_display_fields
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.routes.evaluations_common import (
    _BROKEN_LABEL,
    _EVAL_SCORED_TYPE,
    _EVAL_TYPE_PREFIX,
    _USED_TRACE_LABEL,
)
from xianyu_hunter.web.routes.evaluations_data_cleaner import clean_dirty_seller_nick
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


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


_SIMPLE_FIELD_MAP = {
    "title": "item_title",
    "thumb_url": "thumb_url",
    "region": "region",
    "brand": "brand",
    "seller_id": "seller_id",
}

_POSITIVE_FIELD_MAP = {
    "price": "item_price",
    "want_cnt": "want_cnt",
    "view_cnt": "view_cnt",
}


def _apply_simple_fields(payload: dict, candidates: dict) -> None:
    """应用简单字段映射：有值则覆盖

    拆分自 _apply_enrich_fields：将 title/thumb_url/region/brand/seller_id
    等"有值即覆盖"的字段用查表法统一处理，替代多个平铺 if（S3776）。"""
    for src_key, dst_key in _SIMPLE_FIELD_MAP.items():
        value = candidates.get(src_key)
        if not value:
            continue
        if src_key == "seller_id":
            payload[dst_key] = str(value)
        else:
            payload[dst_key] = value


def _apply_positive_fields(payload: dict, candidates: dict) -> None:
    """应用数值型字段映射：值为正才覆盖（0 可能是采集失败）

    拆分自 _apply_enrich_fields：将 price/want_cnt/view_cnt 等
    "需 >0 才覆盖"的字段用查表法统一处理，替代多个平铺 if（S3776）。

    为什么 0 不覆盖：选择器未命中时采集器可能返回 0，不应覆盖历史有效数据。"""
    for src_key, dst_key in _POSITIVE_FIELD_MAP.items():
        value = candidates.get(src_key)
        if value is not None and value > 0:
            payload[dst_key] = value


def _apply_seller_nick(payload: dict, item: dict, link: dict) -> None:
    """填充 seller_nick：仅在 payload 中完全缺失时才从 item/link 回填

    拆分自 _apply_enrich_fields：将 seller_nick 的特殊判断（None vs 空字符串）
    收敛到单一函数，避免脏数据清洗后的空字符串被误覆盖（S3776）。

    关键细节：用 is None 判断而非 not，因为脏数据清洗后 seller_nick 可能是
    空字符串（falsy），此时不应被 items 表的旧数据回填。"""
    if payload.get("seller_nick") is not None:
        return
    nick = link.get("seller_nick") or item.get("seller_nick")
    if nick:
        payload["seller_nick"] = nick


def _apply_is_sold(payload: dict, item: dict, link: dict) -> None:
    """填充 is_sold：items 表（int 0/1）> task_links.display（bool）> 保留旧值

    拆分自 _apply_enrich_fields：将 is_sold 的多数据源优先级判断
    收敛到单一函数，降低主函数的分支数（S3776）。

    为什么总是覆盖：已售状态会变化（在售→已售），用户期望看到最新状态。"""
    raw_sold = item.get("is_sold")
    if raw_sold is not None:
        payload["is_sold"] = bool(raw_sold)
    elif "is_sold" in link:
        payload["is_sold"] = bool(link["is_sold"])


def _apply_enrich_fields(
    payload: dict, candidates: dict, item: dict, link: dict,
) -> None:
    """补充/覆盖 payload 字段

    items 表和 task_links.display 反映采集最新值，
    eval 事件 payload 中的对应字段是评估时的历史快照。
    用户点击标题刷新后，期望评估明细页显示最新商品信息，而非评估时的旧快照。
    因此对"会变动的商品基础信息"字段，有最新值则覆盖；无最新值时保留 payload 旧快照。
    例外：seller_nick 有脏数据清洗特殊逻辑，保持"仅缺失时填充"。

    重构说明：按字段类型拆分到 4 个独立函数（S3776），
    简单字段和数值字段用查表法替代平铺 if，主函数只做流程编排。"""
    _apply_simple_fields(payload, candidates)
    _apply_positive_fields(payload, candidates)
    _apply_seller_nick(payload, item, link)
    if candidates["publish_time"]:
        payload["publish_time"] = str(candidates["publish_time"])
    _apply_is_sold(payload, item, link)


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
        clean_dirty_seller_nick(payload)

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
    r: dict, payload: dict,  # NOSONAR
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
    request: Request,  # NOSONAR
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
