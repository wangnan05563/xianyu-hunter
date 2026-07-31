"""评估列表 API — 列表查询 + 数据丰富 + 过滤 + 成色标签

从 api_evaluations.py 拆分，包含：
- list_evaluations 路由及其辅助函数（过滤、丰富、分页）
- latest_for_item 路由
- 成色标签分析（_enrich_condition_tags 及辅助函数）
- 脏数据清洗委托给 evaluations_data_cleaner
"""
from __future__ import annotations

import json
import time
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
# 复用 price_dashboard 的 _compute_sold_range 避免口径漂移
# 为什么导入：评估列表的 bargain_price 必须与价格行情页同源，否则前端展示会矛盾
from xianyu_hunter.web.routes.price_dashboard import _compute_sold_range
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])

# 市场价格统计缓存：(task_id, range_days) -> (stats_dict, timestamp)
# 为什么用模块级缓存：评估列表频繁刷新时避免 N+1 查询 task_links/items 表
# TTL 5 分钟：bargain_price/mean_price 基于历史已售数据，短期不会剧烈变化
_MARKET_STATS_CACHE: dict[tuple[str | None, int], tuple[dict[str, float | None], float]] = {}
_MARKET_STATS_CACHE_TTL = 300.0  # 秒


def compute_market_stats_batch(
    container: Container, task_ids: list[str | None], range_days: int = 30
) -> dict[str | None, dict[str, float | None]]:
    """批量查询多个任务的市场价格统计（bargain_price + mean_price），带 TTL 缓存

    返回 {task_id: {"bargain_price": ..., "mean_price": ...}} 映射，
    task_id 为 None 时表示全局统计。
    缓存未命中时逐任务调用 _compute_sold_range，与价格行情页同源保证口径一致。

    为什么同时返回 bargain_price 和 mean_price：
    - bargain_price (P10)：捡漏参考价，用于前端"捡漏价格"展示
    - mean_price (算术平均价)：市场均价，用于"预估盈利 = 均价 - 当前价"计算
    两者同源（_compute_sold_range 一次查询），避免两次 DB 调用。
    """
    now = time.monotonic()
    result: dict[str | None, dict[str, float | None]] = {}
    missing: list[str | None] = []

    for tid in task_ids:
        cache_key = (tid, range_days)
        cached = _MARKET_STATS_CACHE.get(cache_key)
        if cached and (now - cached[1]) < _MARKET_STATS_CACHE_TTL:
            result[tid] = cached[0]
        else:
            missing.append(tid)

    if missing:
        engine = container.repo.engine
        with engine.connect() as conn:
            for tid in missing:
                try:
                    stats = _compute_sold_range(conn, tid, range_days)
                    market_stats = {
                        "bargain_price": stats.get("bargain_price"),
                        "mean_price": stats.get("mean_price"),
                    }
                    _MARKET_STATS_CACHE[(tid, range_days)] = (market_stats, now)
                    result[tid] = market_stats
                except Exception as e:
                    # 市场价格查询失败不应阻断评估列表渲染
                    logger.warning("查询任务 {} 的市场价格统计失败: {}", tid, e)
                    result[tid] = {"bargain_price": None, "mean_price": None}

    return result


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

    为什么 0 不覆盖：选择器未命中时采集器可能返回 0，不应覆盖历史有效数据。

    item_price 快照：覆盖前把评估时的原始价格保存到 _eval_snapshot_price，
    供 _filter_price_range 使用。为什么需要快照：官方采集会更新 items 表价格，
    enrich 用最新价格覆盖 payload.item_price 后，按任务价格范围的过滤会误判
    旧 eval 事件超范围而隐藏（用户报告"官方采集后商品消失"的根因）。
    过滤应基于评估时的价格（评估通过即说明当时价格在范围内），展示用最新价格。
    """
    for src_key, dst_key in _POSITIVE_FIELD_MAP.items():
        value = candidates.get(src_key)
        if value is not None and value > 0:
            if src_key == "price" and "_eval_snapshot_price" not in payload:
                # 首次覆盖前保存评估时价格快照（仅一次，后续 enrich 不刷新），
                # 保留评估入库时的价格供 _filter_price_range 使用，避免官方采集
                # 更新 items 表价格后旧 eval 事件被按最新价格误过滤
                payload["_eval_snapshot_price"] = payload.get(dst_key)
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

    为什么用 _eval_snapshot_price 优先：评估时价格是评估入库时的快照，
    评估通过即说明当时价格在任务范围内。enrich 后的 item_price 是 items 表
    最新值（可能被官方采集更新），用它过滤会误判旧 eval 事件超范围而隐藏。
    展示仍用 item_price（最新值），过滤用评估时价格，二者职责分离。
    为什么 include_out_of_range 跳过：用户审计历史超范围商品时需要能查看
    为什么 price=None 时不过滤：评估时可能未采集到价格，保留避免误删"""
    if include_out_of_range or (min_price is None and max_price is None):
        return False
    # 评估时价格快照优先：_eval_snapshot_price 存在（含 None）说明已 enrich，
    # 用评估时价格过滤；不存在则回退到 item_price（兼容未 enrich 的旧事件）
    if "_eval_snapshot_price" in payload:
        price_val = payload.get("_eval_snapshot_price")
    else:
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


def _resolve_market_ratio(container: Container, task_id: str | None) -> float | None:
    """解析任务的 market_ratio 配置（任务级 price_config 优先，回退全局）

    为什么不直接复用 container.build_task_price_strategy：该方法只有在
    task 配置了 min_price 或 max_price 时才会构造任务级 PriceStrategy，
    否则直接返回全局 strategy，导致任务级 price_config.market_ratio 被忽略。
    此处独立解析，让 market_ratio 在仅有 price_config 覆盖时也能生效。

    为什么从 container.price_strategy 读全局而非 get_config()：让测试可通过
    覆盖 container.price_strategy 控制全局 market_ratio，避免依赖全局单例。"""
    if not task_id:
        return None
    try:
        task_raw = container.repo.get_task(task_id)
    except Exception as e:
        logger.warning(f"读取任务 {task_id} market_ratio 配置失败，跳过市场参考价过滤: {e}")
        return None
    if not task_raw:
        return None
    # 任务级 price_config 覆盖
    task_price_config = task_raw.get("price_config")
    if isinstance(task_price_config, str):
        try:
            task_price_config = json.loads(task_price_config)
        except (TypeError, ValueError):
            task_price_config = None
    if isinstance(task_price_config, dict) and "market_ratio" in task_price_config:
        return task_price_config["market_ratio"]
    # 回退全局：优先用 container.price_strategy（全局策略实例），避免依赖 get_config()
    global_strategy = getattr(container, "price_strategy", None)
    if global_strategy is not None:
        return global_strategy.config.market_ratio
    return get_config().price_strategy.market_ratio


def _compute_eval_market_median(candidates: list[dict]) -> tuple[float | None, int]:
    """从已 enrich 的评估事件列表中计算价格中位数

    为什么基于已 enrich 的 payload.item_price：评估事件写入时的快照可能已过时，
    enrich 已用 items 表最新值覆盖，中位数应基于最新价格计算才贴近市场实情。

    为什么 sample_size < 3 时返回 None：与 PriceStrategy.check 一致，
    样本不足时中位数不稳定，过滤会误伤有效商品。"""
    prices: list[float] = []
    for r in candidates:
        payload = r.get("payload") or {}
        price_val = payload.get("item_price")
        if price_val is None:
            continue
        try:
            prices.append(float(price_val))
        except (TypeError, ValueError):
            continue
    if len(prices) < 3:
        return None, len(prices)
    prices.sort()
    n = len(prices)
    # 与 worker._compute_market_context 保持一致的中位数算法
    median = prices[n // 2] if n % 2 == 1 else (prices[n // 2 - 1] + prices[n // 2]) / 2
    return median, n


def _filter_market_ratio(
    payload: dict,
    market_ratio: float | None,
    median_price: float | None,
    sample_size: int,
) -> bool:
    """低于市场参考价过滤：返回 True 表示应跳过

    沿用 PriceStrategy.check 中 market_ratio 分支的判断逻辑，
    保证卖家评估菜单的过滤与 worker 搜索流水线口径一致：
    - market_ratio 为 None 或 >= 1.0 时禁用
    - 样本数 < 3 时跳过（中位数不稳定）
    - 商品价格 > 中位数 × 比率 时拒绝"""
    if market_ratio is None or market_ratio >= 1.0:
        return False
    if median_price is None or sample_size < 3:
        return False
    price_val = payload.get("item_price")
    if price_val is None:
        return False
    try:
        price_float = float(price_val)
    except (TypeError, ValueError):
        return False
    return price_float > median_price * market_ratio


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
    market_ratio: float | None, median_price: float | None, sample_size: int,
) -> bool:
    """判断评估记录是否应被跳过（不满足任一过滤条件返回 True）

    拆分自主循环：把 9 个独立 if 过滤条件收敛到一个函数，
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
    if not include_out_of_range and _filter_market_ratio(payload, market_ratio, median_price, sample_size):
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

    低于市场参考价过滤（market_ratio）：
    - 解析任务级 price_config.market_ratio（任务级覆盖，回退全局 AppConfig.price_strategy）
    - 实时计算同 task_id 下所有评估事件的价格中位数（sample_size >= 3 才生效）
    - 过滤商品价格 > 中位数 × market_ratio 的记录，与 worker 搜索流水线口径一致
    - include_out_of_range=True 时跳过该过滤（审计场景需要完整历史）
    - 未传 task_id 时不应用此过滤（无市场参考上下文）
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
    # 两段循环：先 enrich 所有候选，再计算市场参考价中位数，最后过滤
    # 为什么不沿用单段循环：market_ratio 过滤需要中位数，中位数基于 enrich 后的
    # payload.item_price 计算，必须先全量 enrich 才能得到正确的中位数样本
    candidates: list[dict] = []
    for r in rows:
        # 只展示 eval.scored 评估事件，排除 eval.passed 等通知事件
        # 为什么不用 startswith("eval.")：NotifierHub 推送钉钉时会写入 type="eval.passed"、
        # payload=None、stage="notify" 的记录（hub.py 第 196-204 行），这些通知事件
        # 没有评分数据，混入列表会导致前端出现大量"无内容记录"且被 distribution API
        # 误算为 insufficient_count
        if str(r.get("type", "")) != _EVAL_SCORED_TYPE:
            continue
        _enrich_eval_record(r, item_map, link_map, order_map, seller_map)
        candidates.append(r)

    # 解析 market_ratio 配置（任务级优先，全局回退），实时计算中位数
    # 为什么 include_out_of_range 时跳过：审计历史超范围商品时不应再叠加市场参考价过滤
    market_ratio = (
        _resolve_market_ratio(container, task_id) if not include_out_of_range else None
    )
    if market_ratio is not None:
        # 中位数计算基于硬性价格范围内的样本，避免被 min_price/max_price 过滤的商品扭曲中位数
        in_range_candidates = [
            r for r in candidates
            if not _filter_price_range(r["payload"], min_price, max_price, include_out_of_range)
        ]
        median_price, sample_size = _compute_eval_market_median(in_range_candidates)
    else:
        median_price, sample_size = None, 0

    for r in candidates:
        payload = r["payload"]
        if _should_skip_eval_record(
            r, payload, item_id, task_id, brand,
            sold_filter, item_sold_map,
            min_price, max_price, include_out_of_range,
            min_score, max_score, result_category,
            start_dt, end_dt,
            market_ratio, median_price, sample_size,
        ):
            continue

        evals.append(r)
    # 计算成色判断标签（基于商品标题和描述文本，帮助用户判断商品新旧程度）
    _enrich_condition_tags(evals)
    # 批量注入捡漏价格（P10）、均价（mean_price）与预估盈利（均价 - 当前价）
    # 为什么在分页前注入：市场价格统计按 task_id 缓存，分页前注入可让同 task_id
    # 的所有商品共享一次缓存查询；分页后只有 20 条会导致同 task_id 多次刷新重复查询
    _enrich_bargain_and_profit(evals, container)
    total = len(evals)
    # 始终使用 page_num/page_size 分页
    actual_offset = (page_num - 1) * page_size
    paged = evals[actual_offset:actual_offset + page_size]
    return {"items": paged, "count": len(paged), "total": total}


def _enrich_bargain_and_profit(evals: list[dict], container: Container) -> None:
    """为评估记录注入 bargain_price、avg_price 和 estimated_profit 字段

    bargain_price：P10 分位数（捡漏参考价，与价格行情页同源）
    avg_price：算术平均价（市场均价，用于预估盈利计算）
    estimated_profit = avg_price - 当前价格(item_price)
    缺失数据时字段均为 None，前端用 null 语义区分显示

    为什么用"均价-当前价"而非"当前价-捡漏价"：
    预估盈利的语义是"买入后以市场均价卖出的预期利润"。
    当前价是买入成本，均价是预期卖出价，盈利 = 卖出 - 买入 = 均价 - 当前价。
    正数（均价 > 当前价）= 当前价低于市场均价，有利润空间（捡漏机会）；
    负数（均价 < 当前价）= 当前价高于市场均价，无利润空间。
    """
    if not evals:
        return
    task_ids = {r.get("task_id") for r in evals if r.get("task_id")}
    # task_id 为空时也查一次全局统计，让无 task_id 的评估记录也能展示盈利预估
    if any(not tid for r in evals for tid in [r.get("task_id")]):
        task_ids.add(None)
    market_map = compute_market_stats_batch(container, list(task_ids))
    for r in evals:
        payload = r["payload"]
        tid = r.get("task_id")
        stats = market_map.get(tid) or {}
        bargain = stats.get("bargain_price")
        avg_price = stats.get("mean_price")
        payload["bargain_price"] = bargain
        payload["avg_price"] = avg_price
        current_price = payload.get("item_price")
        # 三态语义：avg_price 或 current_price 为 None 时 estimated_profit 为 None
        # 前端用 null 表示"无法计算"，区分于 0 或负数
        if avg_price is not None and current_price is not None:
            try:
                payload["estimated_profit"] = round(float(avg_price) - float(current_price), 2)
            except (TypeError, ValueError):
                payload["estimated_profit"] = None
        else:
            payload["estimated_profit"] = None


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


# 否定词前缀：修饰负面关键词时表示该情况不存在（如"无划痕磕碰"中的"无"）
# 为什么需要否定词感知：朴素子串匹配会把"无划痕"中的"划痕"误判为 worn 类别命中
_NEGATION_PREFIXES = ("无", "没有", "不含", "未见", "没")

# 需要否定词感知的类别：仅负面类别做否定检测，避免误伤正面/中性关键词
# 例如 completeness_missing 类别本身就有"无包装"这类关键词，不应再被否定逻辑处理
_NEGATION_AWARE_CATEGORIES = {"used", "worn", "broken"}

# 否定词与关键词之间的断句标点：标点会断开否定关系
# 例如"无划痕、磕碰"中"磕碰"前的"、"断开了"无"的修饰范围
_NEGATION_BREAKING_PUNCTS = "，。；、,.;！？!?"


def _is_negated(text: str, label: str, label_pos: int) -> bool:
    """检查关键词在文本中是否被否定词修饰

    通过检查关键词前 10 个字符窗口内是否包含否定词来判断。
    窗口内若存在断句标点，则只看最后一个断句标点之后的内容，
    因为标点会断开否定关系（如"无划痕、磕碰"中"磕碰"未被否定）。

    为什么窗口取 10 字符：常见否定表达如"没有任何"、"无任何"加上被修饰词
    总长不超过 10 字符，过短会漏判（如"无任何划痕"中"划痕"前 5 字符为"无任何"，
    但"没有划痕和磕碰"中"磕碰"前 5 字符为"划痕和"，需 10 字符窗口才能覆盖"没有"）。
    """
    window_start = max(0, label_pos - 10)
    prefix = text[window_start:label_pos]
    # 找到窗口内最后一个断句标点，只看其之后的内容
    last_punct_idx = -1
    for punct in _NEGATION_BREAKING_PUNCTS:
        idx = prefix.rfind(punct)
        if idx > last_punct_idx:
            last_punct_idx = idx
    if last_punct_idx != -1:
        prefix = prefix[last_punct_idx + 1:]
    # 在剩余前缀中查找否定词
    return any(neg in prefix for neg in _NEGATION_PREFIXES)


def _scan_condition_keywords(text: str) -> tuple[list[dict], int]:
    """扫描文本中的成色关键词，返回 (tags, score)

    每个 category 只算一次（避免同一类别多关键词重复加分）。

    否定词感知：负面类别（used/worn/broken）的关键词若被否定词修饰
    （如"无划痕磕碰"中的"磕碰"），不计为命中，避免误判为明显使用。
    同一关键词在文本中多次出现时，只要有一次未被否定即视为命中。
    """
    tags: list[dict] = []
    score = 0
    for category, info in _CONDITION_KEYWORDS.items():
        for label in info["labels"]:
            pos = text.find(label)
            matched = False
            while pos != -1 and not matched:
                # 负面类别需检查否定词修饰；被否定的出现位置跳过，继续查找下一次出现
                if category in _NEGATION_AWARE_CATEGORIES and _is_negated(text, label, pos):
                    pos = text.find(label, pos + len(label))
                    continue
                tags.append({"category": category, "label": label})
                score += info["score_bonus"]
                matched = True
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
