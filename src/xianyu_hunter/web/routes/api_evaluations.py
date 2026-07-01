"""评估明细 API"""
from __future__ import annotations

import asyncio
import json
import math
import re
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from xianyu_hunter.container import Container
from xianyu_hunter.domain.evaluation import RiskLevel
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.infra.item_display_sync import sync_item_display_from_detail
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.modules.collector_utils import normalize_display_fields
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


# S1192: 提取重复字符串字面量为常量，避免散落维护
_BROKEN_LABEL = "有故障/维修"
# 已知污染模式：早期 DOM 解析脚本错误写入的字段值
_REGION_PATTERNS = re.compile(r"^[\u4e00-\u9fa5]{2,4}$")  # 纯 2-4 字中文（省/市）
_CREDIT_PATTERNS = re.compile(r"^.*(信用|极好|良好|优秀|信誉).*$")
_PUBLISH_TIME_PATTERNS = re.compile(
    r".*(周内|天内|小时前|分钟前|月前|刚刚|今天|昨天|前天|秒前|\d+\s*(分钟|小时|天|周|月)前).*"
)
# 卖家昵称脏数据识别用的关键词集合
# 必须包含所有可能的污染值（如"几乎全新"、"全新"等成色关键词）
_POLLUTED_NICK_KEYWORDS = {
    "全新", "未拆封", "未使用", "未拆", "99新", "95新", "9成新", "几乎全新",
    "近全新", "近新", "9.5新", "9.9新", "8成新", "8.5新", "85新", "7成新",
    "正常使用", "使用过", "有使用痕迹", "明显使用", "外观磨损", "有划痕", "磕碰",
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
        # 复合污染：分离"地区\n信用度"格式
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

    elif pollution_type == "region":
        if not payload.get("region"):
            payload["region"] = nick.strip()
        payload["seller_nick"] = ""

    elif pollution_type == "credit":
        if not payload.get("seller_credit"):
            payload["seller_credit"] = nick.strip()
        payload["seller_nick"] = ""

    elif pollution_type == "publish_time":
        # 把发布时间短语保存为 publish_time_text，前端发布时间为空时兜底显示
        if not payload.get("publish_time_text"):
            payload["publish_time_text"] = nick.strip()
        payload["seller_nick"] = ""

    elif pollution_type == "condition":
        # 把成色关键词保存为 condition_label_override，覆盖自动计算结果
        if not payload.get("condition_label_override"):
            payload["condition_label_override"] = nick.strip()
        payload["seller_nick"] = ""
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

    # 兼容 task_links.display 的键名：title -> item_title, price 字符串转 float
    def _coerce_price(v: object) -> float | None:
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    # 取 title：items.title > link.title > link.item_title
    title_candidate = (
        item.get("title") or link.get("title") or link.get("item_title") or ""
    )
    # 取 price：items.price > link.price
    price_candidate = item.get("price")
    if price_candidate is None:
        price_candidate = _coerce_price(link.get("price"))
    # 取 thumb_url：items.thumb_url > link.thumb_url
    thumb_candidate = item.get("thumb_url") or link.get("thumb_url")
    # 取 region：items.region > link.region
    region_candidate = item.get("region") or link.get("region")
    # 取 brand：items.brand > link.brand（品牌由 extract_brand 推断，存于 task_links.display）
    brand_candidate = item.get("brand") or link.get("brand")
    # 取 want_cnt：items.want_cnt > link.want_cnt
    want_candidate = item.get("want_cnt")
    if want_candidate is None and link.get("want_cnt") is not None:
        try:
            want_candidate = int(link["want_cnt"])
        except (TypeError, ValueError):
            want_candidate = None
    # 取 view_cnt：items.view_cnt > link.view_cnt（曝光度，用于辅助判断商品热度）
    view_candidate = item.get("view_cnt")
    if view_candidate is None and link.get("view_cnt") is not None:
        try:
            view_candidate = int(link["view_cnt"])
        except (TypeError, ValueError):
            view_candidate = None
    # 取 publish_time：items.publish_time > link.publish_time
    publish_candidate = item.get("publish_time") or link.get("publish_time")

    # 脏数据清洗：seller_nick 字段可能包含"地区+信用度"组合
    if item or link:
        _clean_dirty_seller_nick(payload)

    # 补充/覆盖字段：items 表和 task_links.display 反映采集最新值，
    # eval 事件 payload 中的对应字段是评估时的历史快照。
    # 用户点击标题刷新后，期望评估明细页显示最新商品信息，而非评估时的旧快照。
    # 因此对"会变动的商品基础信息"字段，有最新值则覆盖；无最新值时保留 payload 旧快照。
    # 例外：seller_nick 有脏数据清洗特殊逻辑，保持"仅缺失时填充"。
    if title_candidate:
        payload["item_title"] = title_candidate
    # price=0 可能是采集失败（选择器未命中），不应覆盖有效旧值
    if price_candidate is not None and price_candidate > 0:
        payload["item_price"] = price_candidate
    # seller_id：有最新值则覆盖
    sid = item.get("seller_id") or link.get("seller_id")
    if sid:
        payload["seller_id"] = str(sid)
    # 关键修复：脏数据清洗后 seller_nick 为空字符串（falsy），
    # 不能用 `not payload.get("seller_nick")` 判定缺失，否则会被 items 表回填错误数据
    if payload.get("seller_nick") is None:
        nick = link.get("seller_nick") or item.get("seller_nick")
        if nick:
            payload["seller_nick"] = nick
    if thumb_candidate:
        payload["thumb_url"] = thumb_candidate
    if region_candidate:
        payload["region"] = region_candidate
    if brand_candidate:
        payload["brand"] = brand_candidate
    # want_cnt/view_cnt=0 可能是采集失败，不应覆盖有效旧值
    if want_candidate is not None and want_candidate > 0:
        payload["want_cnt"] = want_candidate
    if view_candidate is not None and view_candidate > 0:
        payload["view_cnt"] = view_candidate
    if publish_candidate:
        payload["publish_time"] = str(publish_candidate)
    # is_sold：items 表（int 0/1）> task_links.display（bool）> 保留 payload 旧值
    # 为什么总是覆盖：已售状态会变化（在售→已售），用户期望看到最新状态
    raw_sold = item.get("is_sold")
    if raw_sold is not None:
        payload["is_sold"] = bool(raw_sold)
    elif "is_sold" in link:
        payload["is_sold"] = bool(link["is_sold"])
    # 注入订单状态：让评估明细页面能直接展示商品是否已被抢单
    # 为什么不写入 payload 原始事件：order_status 是实时查询的派生字段，不应污染 events 表
    if order_map is not None and item_id:
        order = order_map.get(item_id)
        if order:
            payload["order_status"] = order.get("status")
            payload["order_id"] = order.get("id")
        else:
            payload["order_status"] = None
            payload["order_id"] = None
    return payload


@router.get("")
def list_evaluations(
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
    """
    # 预解析时间范围边界（避免在循环内反复解析）
    start_dt = to_datetime(start_time) if start_time else None
    end_dt = to_datetime(end_time) if end_time else None
    # end_time 当天结束（23:59:59），覆盖整天
    if end_dt:
        end_dt = end_dt.replace(hour=23, minute=59, second=59)

    # 修复：之前用 list_events(limit=limit*4) 在 Python 端过滤 eval.*，
    # 当非 eval 事件多时会遗漏数据且 total 不准。改为 SQL 端按 type 前缀过滤。
    # 不传 limit/offset，全量加载 eval.* 事件（评估事件已按 task_id+item_id 去重，量级可控），
    # 后续在 Python 端做 item_id/task_id 模糊匹配、score/time 范围过滤，再分页。
    rows, _ = container.repo.list_events_by_type_prefix(type_prefix="eval.")

    # 收集本批评估事件涉及的所有 item_id，用于批量查询 items / task_links
    event_item_ids: set[str] = set()
    for r in rows:
        payload = r.get("payload") or {}
        iid = str(payload.get("item_id") or r.get("item_id") or "")
        if iid:
            event_item_ids.add(iid)

    # 预加载 items 表数据，用于丰富评估记录
    # 修复：之前用 list_items(limit=5000) 全量加载，超过 5000 行会遗漏。
    # 改为按评估事件涉及的 item_id 批量查询，既省内存又不会遗漏。
    item_rows = container.repo.list_items_by_ids(list(event_item_ids)) if event_item_ids else []
    item_map: dict[str, dict] = {}
    for it in item_rows:
        iid = str(it.get("item_id") or it.get("id") or "")
        if iid:
            item_map[iid] = it

    # 预构建 item_id -> is_sold 映射，供 sold_filter 在 Python 端过滤使用
    # 为什么不在 SQL 端下推：评估事件存于 events 表，需 JOIN items 表按 item_id 关联，
    # 再分页；events 表数据量级大且已按 task_id+item_id 去重，Python 端过滤足够高效
    item_sold_map: dict[str, bool] = {}
    if sold_filter != "all":
        for iid, it in item_map.items():
            # items.is_sold 是 int(0/1)，转 bool 便于过滤判断
            item_sold_map[iid] = bool(it.get("is_sold"))

    # 预加载 task_links.display 数据（弥补 items 表缺失的常见场景：评估事件未入 items 但已关联到任务）
    # 修复：之前直接访问 container.repo.engine 绕过 Repository，改为调用正式方法
    link_map: dict[str, dict] = container.repo.list_link_displays_by_keys(
        list(event_item_ids), link_type="item"
    ) if event_item_ids else {}

    # 预加载 sellers 表数据（items 表无 seller_nick，需从 sellers 表补充）
    # 修复：之前直接访问 engine 查询所有 sellers，改为按 item_map 中的 seller_id 批量查询
    seller_ids_from_items = {
        str(it.get("seller_id") or "")
        for it in item_map.values()
        if it.get("seller_id")
    }
    seller_map: dict[str, str] = {}  # seller_id -> nick
    if seller_ids_from_items:
        seller_rows = container.repo.list_sellers_by_ids(list(seller_ids_from_items))
        for s in seller_rows:
            sid = str(s.get("id") or "")
            nick = s.get("nick")
            if sid and nick:
                seller_map[sid] = nick

    # 批量预加载订单状态：避免 N+1 查询，评估明细列表展示「订单状态」列使用
    # 为什么放在主流程：order_status 是派生字段，不写入 events 表，每次查询时实时关联
    # 为什么 include_failed=True：评估明细需要展示失败订单记录，否则用户
    # 点击抢单失败后刷新页面看到「—」，会误以为没下过单而反复触发抢单
    order_map = (
        container.repo.list_orders_by_item_ids(
            list(event_item_ids), include_failed=True
        )
        if event_item_ids
        else {}
    )

    evals = []
    for r in rows:
        if not str(r.get("type", "")).startswith("eval."):
            continue
        payload = r.get("payload") or {}

        # 用 items 表 / task_links 数据丰富 payload（补充标题、价格、地区、图片、卖家ID等）
        _enrich_eval_with_item(payload, item_map, link_map, order_map)

        # 用 sellers 表补充卖家昵称（items 表无 seller_nick 字段）
        # 关键修复：脏数据清洗后 seller_nick 为空字符串，不能用 `not` 判定缺失
        sid = payload.get("seller_id") or r.get("seller_id")
        if sid and payload.get("seller_nick") is None and str(sid) in seller_map:
            payload["seller_nick"] = seller_map[str(sid)]

        # 确保顶层 item_id 有值（兼容旧事件：EventRow.item_id 列可能为空）
        if not r.get("item_id") and payload.get("item_id"):
            r["item_id"] = str(payload["item_id"])

        # 商品 ID 模糊匹配
        if item_id:
            eid = str(payload.get("item_id") or r.get("item_id") or "")
            if item_id.lower() not in eid.lower():
                continue

        # 任务 ID 模糊匹配
        if task_id:
            tid = str(payload.get("task_id") or r.get("task_id") or "")
            if task_id.lower() not in tid.lower():
                continue

        # 品牌精确匹配：brand 字段已由 _enrich_eval_with_item 从 task_links.display 补充
        # 为什么放在 enrich 之后：评估事件本身不存 brand，必须先补全再过滤
        # S1066: 合并嵌套 if，外层仅做"是否过滤"判断，内层为同一过滤条件的延续
        if brand and str(payload.get("brand") or "") != brand:
            continue

        # 销售状态过滤：根据 items 表 is_sold 字段过滤评估记录
        # 为什么放在 enrich 之后：item_map 已批量加载 is_sold，复用避免重复查询
        # 为什么 items 表无记录时按"在售"处理：评估事件可能引用了未入库的商品，
        # 这种情况按"在售"保留，避免 onsale 过滤时误删有效评估
        if sold_filter != "all":
            iid = str(payload.get("item_id") or r.get("item_id") or "")
            is_sold = item_sold_map.get(iid, False)
            if sold_filter == "onsale" and is_sold:
                continue
            if sold_filter == "sold" and not is_sold:
                continue

        # 评分范围过滤
        score = payload.get("score")
        if score is not None:
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = None
        if min_score is not None and (score is None or score < min_score):
            continue
        if max_score is not None and (score is None or score > max_score):
            continue

        # 结果分类过滤：按配置阈值精确分类，与统计卡片展示逻辑一致
        # 为什么不用 min_score/max_score：score 可能是浮点数（如 75.5），
        # max_score 是闭区间无法表达 [pass, auto) 半开区间；
        # insufficient 需要 score=null，min/max_score 会把 null 排除
        if result_category:
            eval_cfg = get_config().eval
            pass_threshold = eval_cfg.pass_score
            auto_threshold = eval_cfg.auto_buy_score
            if result_category == "auto":
                if score is None or score < auto_threshold:
                    continue
            elif result_category == "pass":
                if score is None or score < pass_threshold or score >= auto_threshold:
                    continue
            elif result_category == "fail":
                if score is None or score >= pass_threshold:
                    continue
            elif result_category == "insufficient":
                if score is not None:
                    continue

        # 时间范围过滤
        if start_dt or end_dt:
            ts = r.get("created_at", "")
            d = to_datetime(ts) if ts else None
            if d is None:
                continue
            if start_dt and d < start_dt:
                continue
            if end_dt and d > end_dt:
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
        "labels": ["8成新", "8.5新", "85新", "9成新以下", "正常使用", "使用过", "有使用痕迹"],
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
    "正常使用": "正常使用", "使用过": "正常使用", "有使用痕迹": "正常使用",
    "明显使用": "明显使用", "外观磨损": "明显使用", "有划痕": "明显使用", "磕碰": "明显使用",
    "维修": _BROKEN_LABEL, "维修过": _BROKEN_LABEL, "拆修": _BROKEN_LABEL,
    "故障": _BROKEN_LABEL, "损坏": _BROKEN_LABEL, "已坏": _BROKEN_LABEL,
    "屏幕破损": _BROKEN_LABEL, "进水": _BROKEN_LABEL, "摔过": _BROKEN_LABEL,
    "原装": "全新", "原厂": "全新", "正品": "全新",  # 单独成色描述时归为全新
    "原盒": "全新", "原包装": "全新", "带发票": "全新", "带保修": "全新", "在保": "全新",
    "裸机": "明显使用", "无包装": "正常使用", "无配件": "正常使用",
}


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
        # 合并标题和描述作为扫描文本
        text_parts = [
            payload.get("item_title", "") or "",
            payload.get("description", "") or "",
            payload.get("item_description", "") or "",
        ]
        text = " ".join(text_parts).strip()
        if not text:
            r["condition_tags"] = []
            r["condition_label"] = "未知"
            r["condition_score"] = 0
            r["is_branded_new"] = False
            r["has_repair"] = False
            continue

        tags = []
        score = 0
        # 扫描各类关键词
        for category, info in _CONDITION_KEYWORDS.items():
            for label in info["labels"]:
                if label in text:
                    tags.append({"category": category, "label": label})
                    score += info["score_bonus"]
                    break  # 每个 category 只算一次（避免重复加分）

        # 计算综合成色描述
        if any(t["category"] == "broken" for t in tags):
            condition_label = _BROKEN_LABEL
        elif any(t["category"] == "worn" for t in tags):
            condition_label = "明显使用"
        elif any(t["category"] == "used" for t in tags):
            condition_label = "正常使用"
        elif any(t["category"] == "newness_worn" for t in tags):
            condition_label = "近全新"
        elif any(t["category"] == "newness" for t in tags):
            condition_label = "全新"
        else:
            condition_label = "未注明"

        # 兜底覆盖：若历史数据清洗后从 seller_nick 提取到了成色关键词
        # 则用其覆盖自动计算结果（保证脏数据恢复后展示正确）
        override = payload.get("condition_label_override")
        if override and override in _CONDITION_KEYWORDS_LABEL_MAP:
            condition_label = _CONDITION_KEYWORDS_LABEL_MAP[override]
            # 根据 override 的成色级别修正 condition_score
            if condition_label == "全新":
                score = max(score, 1)
            elif condition_label == _BROKEN_LABEL:
                score = min(score, -3)  # 之前只修正 label 未修正 score，导致显示不一致
            r["is_branded_new"] = condition_label == "全新"
            r["has_repair"] = condition_label == _BROKEN_LABEL
            # 把 override 关键词也加入 tags（方便用户看到原始信息）
            if not any(t["label"] == override for t in tags):
                tags.append({"category": "newness" if condition_label in ("全新", "近全新") else "used", "label": override})

        r["condition_tags"] = tags
        r["condition_label"] = condition_label
        r["condition_score"] = score
        # is_branded_new：综合判断，override 命中"全新"或自动识别为"全新"时为 True
        r["is_branded_new"] = condition_label == "全新"
        # has_repair：override 命中故障类关键词或自动识别到 broken category 时为 True
        # 之前用 any(t["category"] == "broken") 单独判断会覆盖 override 的正确结果
        r["has_repair"] = condition_label == _BROKEN_LABEL or any(t["category"] == "broken" for t in tags)


@router.get("/latest/{item_id}")
def latest_for_item(
    item_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    e = container.repo.get_latest_evaluation(item_id)
    if not e:
        raise HTTPException(status_code=404, detail="无该商品评估记录")
    return e


# ============== Task 11: 自动官方采集统计 API ==============
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

    from collections import Counter
    from sqlalchemy import select

    from xianyu_hunter.infra.db_models import EventRow
    from xianyu_hunter.infra.yaml_config import get_config

    # 退避阈值来自全局配置（任务级覆盖无法在全局统计端点感知，用全局值近似）
    fail_pause_threshold = get_config().eval.auto_collect_fail_pause_threshold

    success_count = 0
    error_counter: Counter[str] = Counter()
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
            .where(EventRow.type == "eval.scored")
            .where(EventRow.created_at >= cutoff)
            .where(func.json_extract(EventRow.payload, '$.data_source') == 'official')
        ).scalar() or 0

        # 失败事件：collect.official.failed（需加载 payload 聚合 top_failures）
        failed_rows = conn.execute(
            select(EventRow.payload)
            .where(EventRow.type == "collect.official.failed")
            .where(EventRow.created_at >= cutoff)
        ).all()
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

        # 判断当前是否处于退避暂停状态：
        # 取最近一条 collect.official.failed 事件的 consecutive_failures 字段，
        # 若 >= 阈值则视为暂停。为什么用最近一条而非累计：退避语义是"连续失败"，
        # 最近一条的 consecutive_failures 反映了最新连续失败计数
        latest_failed_row = conn.execute(
            select(EventRow.payload)
            .where(EventRow.type == "collect.official.failed")
            .order_by(EventRow.created_at.desc())
            .limit(1)
        ).first()
        if latest_failed_row:
            try:
                latest_payload = json.loads(latest_failed_row.payload) if isinstance(latest_failed_row.payload, str) else latest_failed_row.payload
                if isinstance(latest_payload, dict):
                    latest_consecutive = int(latest_payload.get("consecutive_failures", 0))
                    is_paused = latest_consecutive >= fail_pause_threshold
            # S5713: json.JSONDecodeError 是 ValueError 的子类，移除冗余子类
            except (TypeError, ValueError):
                pass

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


# ============== P3-UX-09 评估分分布 API ==============
@router.get("/distribution")
def evaluations_distribution(
    range_hours: int = 168,
    price_bin_count: int = 10,
    score_bin_count: int = 10,
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
    events, _ = container.repo.list_events_by_type_prefix(type_prefix="eval.")
    # 收集涉及的 item_id 用于批量查询 items
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

    # 收集所有评估事件：score 必须有（非 None），price 可选
    # 分数分布（marginals.score / distribution_5bin）只依赖 score
    # 热力图（buckets）依赖 price × score，price 缺失时跳过热力图但仍计入分数分布
    # 注意：score=None（数据不足）的记录不计入分数分布，但计入总数统计
    eval_records: list[tuple[float, float | None]] = []  # (score, price_or_None)
    insufficient_count = 0  # 数据不足的评估数
    for e in events:
        if not str(e.get("type", "")).startswith("eval."):
            continue
        ts = e.get("created_at", "")
        if not ts:
            continue
        d = to_datetime(ts)
        if d is None or d < cutoff:
            continue
        payload = e.get("payload") or {}
        score = payload.get("score")
        if score is None:
            insufficient_count += 1
            continue
        try:
            score = float(score)
        except (TypeError, ValueError):
            continue
        item_id = payload.get("item_id") or e.get("item_id")
        price = item_price_map.get(str(item_id)) if item_id else None
        # 如果 payload 中已有价格（从 _enrich_eval_with_item 补充的），优先使用
        # 字段名与 worker.py 写入的 payload 对齐：item_price
        if price is None and payload.get("item_price") is not None:
            try:
                price = float(payload["item_price"])
            except (TypeError, ValueError):
                pass
        eval_records.append((score, price))

    # total = 所有有 score 的评估数（不要求有 price）
    total = len(eval_records)

    # 分数边际分布 + 结果分类（只依赖 score，不依赖 price）
    # 阈值从实时配置读取，确保与配置页面一致
    eval_cfg = get_config().eval
    pass_threshold = eval_cfg.pass_score
    auto_threshold = eval_cfg.auto_buy_score

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

    # 二维热力图桶：只统计有 price 的评估
    pairs_with_price: list[tuple[float, float]] = [
        (p, s) for s, p in eval_records if p is not None
    ]

    if not pairs_with_price:
        # 无价格数据时：热力图为空，但分数分布仍有数据
        buckets: list[list[dict[str, int]]] = []
        marginal_price = [0] * price_bin_count
        price_range = [0.0, 0.0]
    else:
        # 价格范围：对数桶（闲鱼商品价格跨 4 个数量级：1元 ~ 1万元）
        prices = [p for p, _ in pairs_with_price]
        pmin = max(1.0, min(prices))
        pmax = max(prices)
        if pmin == pmax:
            pmin = max(1.0, pmin * 0.9)
            pmax = pmax * 1.1
        log_pmin = math.log10(pmin)
        log_pmax = math.log10(pmax)
        if log_pmax == log_pmin:
            log_pmax = log_pmin + 0.1
        price_range = [round(pmin, 2), round(pmax, 2)]

        # 二维桶 [score_idx][price_idx]
        buckets = [
            [{"count": 0, "pass": 0, "auto": 0, "fail": 0} for _ in range(price_bin_count)]
            for _ in range(score_bin_count)
        ]
        for price, score in pairs_with_price:
            # 价格桶（对数刻度）
            if pmin <= price <= pmax:
                log_p = math.log10(price)
                pi = int((log_p - log_pmin) / (log_pmax - log_pmin) * price_bin_count)
                pi = max(0, min(price_bin_count - 1, pi))
            else:
                pi = price_bin_count - 1
            # 分数桶
            si = int((score - smin) / (smax - smin) * score_bin_count)
            si = max(0, min(score_bin_count - 1, si))
            buckets[si][pi]["count"] += 1
            if score >= auto_threshold:
                buckets[si][pi]["auto"] += 1
            elif score >= pass_threshold:
                buckets[si][pi]["pass"] += 1
            else:
                buckets[si][pi]["fail"] += 1

        marginal_price = [sum(buckets[si][pi]["count"] for si in range(score_bin_count))
                          for pi in range(price_bin_count)]

    # F-15：5 档分布之前的准备工作
    # total 已在前面计算（所有有 score 的评估数，不依赖 price）

    # F-15：5 档分布（0-20/20-40/40-60/60-80/80-100），便于前端直方图直接消费
    distribution_5bin: list[dict[str, Any]] = [
        {"range": "0-20", "count": (marginal_score[0] if len(marginal_score) > 0 else 0)
                              + (marginal_score[1] if len(marginal_score) > 1 else 0)},
        {"range": "20-40", "count": (marginal_score[2] if len(marginal_score) > 2 else 0)
                              + (marginal_score[3] if len(marginal_score) > 3 else 0)},
        {"range": "40-60", "count": (marginal_score[4] if len(marginal_score) > 4 else 0)
                              + (marginal_score[5] if len(marginal_score) > 5 else 0)},
        {"range": "60-80", "count": (marginal_score[6] if len(marginal_score) > 6 else 0)
                              + (marginal_score[7] if len(marginal_score) > 7 else 0)},
        {"range": "80-100", "count": (marginal_score[8] if len(marginal_score) > 8 else 0)
                               + (marginal_score[9] if len(marginal_score) > 9 else 0)},
    ]

    # F-15：二分查找建议阈值——找到使通过率最接近 75% 的分数
    # 通过率随阈值单调递减，因此二分查找收敛到目标通过率对应的分数
    target_rate = 0.75
    if total > 0:
        lo, hi = 0.0, 100.0
        for _ in range(30):
            mid = (lo + hi) / 2
            passing = 0
            for i in range(len(marginal_score)):
                bin_low = i * 10
                bin_high = (i + 1) * 10
                if mid <= bin_low:
                    # 整个桶都在阈值之上，全部通过
                    passing += marginal_score[i] or 0
                elif mid < bin_high:
                    # 桶内线性插值：mid 右侧部分通过
                    passing += (marginal_score[i] or 0) * (bin_high - mid) / 10
            rate = passing / total
            if rate > target_rate:
                lo = mid
            else:
                hi = mid
        suggested_score = round((lo + hi) / 2)
        # 计算该阈值下的实际通过率
        passing = 0
        for i in range(len(marginal_score)):
            bin_low = i * 10
            bin_high = (i + 1) * 10
            if suggested_score <= bin_low:
                passing += marginal_score[i] or 0
            elif suggested_score < bin_high:
                passing += (marginal_score[i] or 0) * (bin_high - suggested_score) / 10
        actual_pass_rate = round(passing / total, 2)
    else:
        # 无数据时使用配置的 pass_score，避免硬编码导致与实际配置不一致
        suggested_score = get_config().eval.pass_score
        actual_pass_rate = 0.75

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
@router.get("/seller-price-trend")
def seller_price_trend(
    seller_id: str = Query(..., description="卖家 ID"),
    range_days: int = Query(30, ge=7, le=90, description="统计天数"),
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

    # 查询该卖家的所有商品（SQL 端按 seller_id 过滤，不加载全量 items 再 Python 过滤）
    seller_items = container.repo.list_items_by_seller(seller_id, limit=5000) or []

    if not seller_items:
        # 无数据时返回空结构，前端显示"暂无数据"
        return {
            "seller_id": seller_id,
            "items_count": 0,
            "price_points": [],
            "current_avg": 0,
            "trend": "stable",
        }

    # 按日期分组：优先用 publish_time，缺失时用 first_seen
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

    # 按日期排序并计算统计值
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

    # 当前均价（最近一天或所有商品）
    current_prices = [float(it["price"]) for it in seller_items if it.get("price") is not None]
    current_avg = round(sum(current_prices) / len(current_prices)) if current_prices else 0

    # 趋势判断：比较前 1/3 和后 1/3 的均价
    trend = "stable"
    if len(price_points) >= 3:
        n = len(price_points)
        first_third = price_points[: max(1, n // 3)]
        last_third = price_points[-max(1, n // 3):]
        first_avg = sum(p["avg_price"] for p in first_third) / len(first_third)
        last_avg = sum(p["avg_price"] for p in last_third) / len(last_third)
        # 变化超过 5% 才判定为趋势，避免微小波动误判
        if first_avg > 0 and (last_avg - first_avg) / first_avg > 0.05:
            trend = "up"
        elif first_avg > 0 and (first_avg - last_avg) / first_avg > 0.05:
            trend = "down"

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
@router.get("/threshold-suggestion")
def threshold_suggestion(
    target_pass_rate: float = Query(0.7, ge=0.1, le=0.95, description="目标通过率"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-15：基于评估分布反推建议阈值

    算法：从高分到低分累加，直到达到 target_pass_rate 对应的分数即为建议阈值。
    复用 distribution API 的 marginals.score 数据，不需要新的数据源。
    """
    # 复用 distribution API 获取分数分布（默认 7 天）
    dist_data = evaluations_distribution(
        range_hours=168,
        price_bin_count=10,
        score_bin_count=10,
        container=container,
    )

    total = dist_data.get("total", 0)
    score_marginals = dist_data.get("marginals", {}).get("score", [])

    # 5 档分布（0-20/20-40/40-60/60-80/80-100）
    distribution: dict[str, int] = {
        "0-20": (score_marginals[0] if len(score_marginals) > 0 else 0)
                + (score_marginals[1] if len(score_marginals) > 1 else 0),
        "20-40": (score_marginals[2] if len(score_marginals) > 2 else 0)
                 + (score_marginals[3] if len(score_marginals) > 3 else 0),
        "40-60": (score_marginals[4] if len(score_marginals) > 4 else 0)
                 + (score_marginals[5] if len(score_marginals) > 5 else 0),
        "60-80": (score_marginals[6] if len(score_marginals) > 6 else 0)
                 + (score_marginals[7] if len(score_marginals) > 7 else 0),
        "80-100": (score_marginals[8] if len(score_marginals) > 8 else 0)
                  + (score_marginals[9] if len(score_marginals) > 9 else 0),
    }

    if total == 0:
        return {
            "suggested_threshold": get_config().eval.pass_score,
            "target_pass_rate": target_pass_rate,
            "current_pass_rate": 0.0,
            "distribution": distribution,
            "analysis": "暂无评估数据，使用当前配置阈值",
        }

    # 从高分到低分累加，找到达到 target_pass_rate 的分数
    # score_marginals[i] 对应 [i*10, (i+1)*10) 分数段
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

    # 当前通过率（使用配置的 pass_score 而非硬编码 60）
    current_pass = get_config().eval.pass_score
    pass_bin = current_pass // 10  # score_marginals 索引
    pass_count = sum(score_marginals[i] for i in range(pass_bin, len(score_marginals)) if i < len(score_marginals))
    current_pass_rate = round(pass_count / total, 2)

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
    range_days: int = Query(30, ge=7, le=90, description="统计天数"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-12：通过 item_id 查询卖家价格趋势

    前端在评估明细页点击"卖家价格趋势"时调用，无需用户手动输入 seller_id。
    先通过 item_id 查出 seller_id，再复用本模块的 seller_price_trend。
    优先从 items 表查询，若商品未入库则回退到事件 payload 中提取 seller_id。
    """
    seller_id: str | None = None

    # 策略1：优先从 items 表查询（数据更完整）
    # 修复：之前直接访问 engine，改为调用 Repository 方法
    item = container.repo.get_item(item_id)
    if item and item.get("seller_id"):
        seller_id = str(item["seller_id"])

    # 策略2：items 表无记录时，从事件 payload 回退（评估事件中包含 seller_id）
    if not seller_id:
        payload = container.repo.get_eval_payload_by_item(item_id)
        if payload:
            seller_id = payload.get("seller_id")

    if not seller_id:
        raise HTTPException(status_code=404, detail="未找到该商品的卖家信息（商品未入库且无评估事件）")

    # 复用本模块的 seller_price_trend（同返回格式，避免跨路由耦合）
    return seller_price_trend(
        seller_id=seller_id,
        range_days=range_days,
        container=container,
    )


# ============== 评估反馈（P3: 反馈闭环） ==============

@router.post("/{item_id}/feedback")
def submit_eval_feedback(
    item_id: str,
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

    # 查找该商品最新的评估事件
    event_type = "eval.scored"
    payload_updates: dict[str, Any] = {
        "feedback": feedback,
        "feedback_note": note or "",
        "feedback_at": _utcnow().isoformat(),
    }

    # 如果有 task_id，按 task_id + item_id 精确查找
    if task_id:
        updated = container.repo.update_eval_payload_by_keys(
            task_id, item_id, event_type, payload_updates
        )
    else:
        # 无 task_id 时，查找该 item_id 最新的 eval.scored 事件
        payload = container.repo.get_eval_payload_by_item(item_id)
        if not payload:
            raise HTTPException(status_code=404, detail=f"未找到商品 {item_id} 的评估记录")
        # 获取 task_id 后更新
        task_id_in_payload = payload.get("task_id", "")
        if task_id_in_payload:
            updated = container.repo.update_eval_payload_by_keys(
                task_id_in_payload, item_id, event_type, payload_updates
            )
        else:
            raise HTTPException(status_code=404, detail=f"评估记录缺少 task_id，无法更新")

    if not updated:
        raise HTTPException(status_code=404, detail=f"未找到商品 {item_id} 的评估记录")

    logger.info("评估反馈: item=%s feedback=%s note=%s", item_id, feedback, note or "")

    return {"ok": True, "item_id": item_id, "feedback": feedback}


@router.get("/feedback/stats")
def feedback_stats(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """评估反馈统计

    返回各反馈类型的数量和准确率，用于监控评估系统整体表现。
    """
    rows, _ = container.repo.list_events_by_type_prefix("eval.scored", limit=50000)
    stats: dict[str, int] = {"accurate": 0, "inaccurate": 0, "partial": 0, "no_feedback": 0}
    for r in rows:
        payload = r.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                payload = {}
        fb = (payload or {}).get("feedback", "")
        if fb in stats:
            stats[fb] += 1
        else:
            stats["no_feedback"] += 1

    total_feedback = stats["accurate"] + stats["inaccurate"] + stats["partial"]
    accuracy_rate = stats["accurate"] / total_feedback if total_feedback > 0 else 0

    return {
        "stats": stats,
        "total_feedback": total_feedback,
        "accuracy_rate": round(accuracy_rate, 4),
    }


# ============== 历史评估重新计算 ==============
@router.post("/recompute")
def recompute_evaluations(
    task_id: str | None = Query(None, description="可选：仅重新计算指定任务的评估"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """用当前配置的评估规则重新计算历史评估数据

    读取 events 表中所有 eval.scored 事件，从 items + sellers 表重建
    ItemDetail 和 SellerProfile，用当前配置的 Evaluator 重新评分，
    更新 events 表的 payload。
    """
    import json as _json
    from xianyu_hunter.domain.item import ItemDetail
    from xianyu_hunter.domain.seller import SellerProfile

    evaluator = container.evaluator

    # 拉取所有评估事件
    # 修复：之前用 list_events(limit=10000) 在 Python 端过滤，改为 SQL 端按 type 前缀过滤
    all_eval_events, _ = container.repo.list_events_by_type_prefix(
        type_prefix="eval.", task_id=task_id
    )
    eval_events = all_eval_events

    if not eval_events:
        # 没有 eval.* 事件时，从 task_links 生成评估
        # 覆盖场景：live_search 写入了 task_links 但未触发评估（旧版本）
        link_rows = []
        if task_id:
            link_rows = container.repo.list_task_links(
                task_id=task_id, link_type="item", limit=500
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
            display = link.get("display") or {}
            item_id = link.get("link_key") or ""
            if not item_id:
                continue
            try:
                price_val = display.get("price")
                price_float = float(price_val) if price_val is not None else 0.0
                detail = ItemDetail(
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
                seller = SellerProfile(
                    id=detail.seller_id or "unknown",
                    nick=detail.seller_nick or "",
                    credit_score=None,
                    register_days=0,
                    on_sale_count=0,
                    sold_count=0,
                )
                eval_result = evaluator.evaluate(detail, seller)
                score_display = eval_result.score if eval_result.score is not None else "N/A"
                if eval_result.is_passed:
                    level = "info"
                elif eval_result.risk_level != RiskLevel.EXTREME:
                    level = "warn"
                else:
                    level = "err"
                if eval_result.risk_level == RiskLevel.UNKNOWN:
                    level = "warn"
                # 补写 items 表：recompute 从 task_links 生成评估时同步写入 items 表，
                # 避免 eval.* 事件引用的 item_id 在 items 表中不存在（孤儿数据）
                if item_id not in existing_item_ids:
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
                        })
                        existing_item_ids.add(item_id)
                    except Exception as e:
                        logger.warning(f"补写 items 表失败 item_id={item_id}: {e}")
                # 使用 upsert 按 task_id+item_id 去重，防止重复评估
                container.repo.upsert_eval_event({
                    "type": "eval.scored",
                    "task_id": link.get("task_id") or task_id or "",
                    "item_id": detail.id,
                    "stage": "eval",
                    "level": level,
                    "message": f"商品 {detail.id} 评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
                    "payload": _json.dumps({
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
                })
                generated += 1
            except Exception:
                errors += 1
                continue
        return {
            "ok": True,
            "recomputed": generated,
            "skipped": 0,
            "errors": errors,
            "total": generated,
            "message": f"从 task_links 生成 {generated} 条评估记录（错误 {errors}）",
        }

    # 预加载 items 和 sellers 数据
    # 修复：之前用 list_items(limit=10000) 全量加载，改为按评估事件涉及的 item_id 批量查询
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

    # 预加载 sellers
    # 修复：之前对每个 item 的 seller_id 单独调用 get_seller（N+1 查询），
    # 改为收集所有 seller_id 后批量查询
    seller_ids_set: set[str] = set()
    for it in item_rows:
        sid = str(it.get("seller_id") or "")
        if sid:
            seller_ids_set.add(sid)
    seller_map: dict[str, dict] = {}
    if seller_ids_set:
        seller_rows = container.repo.list_sellers_by_ids(list(seller_ids_set))
        for s in seller_rows:
            sid = str(s.get("id") or "")
            if sid:
                seller_map[sid] = s

    recomputed = 0
    skipped = 0
    errors = 0

    for e in eval_events:
        try:
            payload = e.get("payload") or {}
            if isinstance(payload, str):
                payload = _json.loads(payload)

            item_id = str(payload.get("item_id") or e.get("item_id") or "")
            if not item_id:
                skipped += 1
                continue

            item_data = item_map.get(item_id)
            if not item_data:
                # 修复：之前直接 skip，导致 live 搜索写入 task_links 但未入 items 表的商品无法重算评估
                # 回退到 payload 中的字段（由 _enrich_eval_with_item 从 task_links.display 补充）
                item_data = {
                    "title": payload.get("item_title") or "",
                    "price": payload.get("item_price") or 0,
                    "region": payload.get("region") or "",
                    "seller_id": payload.get("seller_id") or "",
                    "seller_nick": payload.get("seller_nick") or "",
                }

            seller_id = str(item_data.get("seller_id") or payload.get("seller_id") or "")
            seller_data = seller_map.get(seller_id, {})

            # 重建 ItemDetail（仅包含评估所需字段）
            # seller_nick 优先从 sellers 表取（ItemRow 无此字段），回退到 payload
            detail = ItemDetail(
                id=item_id,
                title=str(item_data.get("title") or payload.get("item_title") or ""),
                price=float(item_data.get("price") or 0),
                region=str(item_data.get("region") or ""),
                seller_id=seller_id,
                seller_nick=str(seller_data.get("nick") or payload.get("seller_nick") or ""),
            )

            # 重建 SellerProfile
            seller = SellerProfile(
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

            # 用当前配置重新评估
            eval_result = evaluator.evaluate(detail, seller)

            # 更新 payload（保留原始字段，仅更新评分相关字段）
            payload["score"] = eval_result.score
            payload["risk_level"] = eval_result.risk_level.value
            payload["dimension_scores"] = eval_result.dimension_scores
            payload["reject_reasons"] = eval_result.reject_reasons
            payload["is_passed"] = eval_result.is_passed
            payload["data_quality"] = eval_result.data_quality
            payload["recomputed_at"] = _utcnow().isoformat()

            # 更新 events 表
            event_id = e.get("id")
            if event_id:
                container.repo.update_event_payload(event_id, _json.dumps(payload, ensure_ascii=False, default=str))
                recomputed += 1

        except Exception:
            errors += 1
            continue

    return {
        "ok": True,
        "recomputed": recomputed,
        "skipped": skipped,
        "errors": errors,
        "total": len(eval_events),
        "message": f"已重新计算 {recomputed} 条评估记录（跳过 {skipped}，错误 {errors}）",
    }


@router.post("/batch-evaluate-unevaluated")
def batch_evaluate_unevaluated(
    task_id: str | None = Query(None, description="可选：仅评估指定任务的商品"),
    limit: int = Query(200, ge=1, le=1000, description="单次最大评估数量"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量评估 items 表中未被评估的商品

    解决商品采集与评估是独立流程导致的大量商品未被评估的问题。
    查询 items 表中不在 eval.* 事件中的商品，用当前评估规则批量评估。
    """
    import json as _json
    from xianyu_hunter.domain.item import ItemDetail
    from xianyu_hunter.domain.seller import SellerProfile

    evaluator = container.evaluator

    # 1. 获取所有已评估的 item_id 集合
    eval_events, _ = container.repo.list_events_by_type_prefix(type_prefix="eval.")
    evaluated_ids: set[str] = set()
    for e in eval_events:
        payload = e.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = _json.loads(payload)
            except (ValueError, TypeError):
                payload = {}
        iid = str(payload.get("item_id") or e.get("item_id") or "")
        if iid:
            evaluated_ids.add(iid)

    # 2. 获取 items 表中所有商品（按 task_id 过滤）
    # items 表量级可控（通常 < 1000），一次查询即可
    all_items = container.repo.list_items(task_id=task_id, limit=5000, offset=0)
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

    # 3. 预加载 sellers 数据（批量查询避免 N+1）
    seller_ids_set: set[str] = set()
    for it in to_evaluate:
        sid = str(it.get("seller_id") or "")
        if sid:
            seller_ids_set.add(sid)
    seller_map: dict[str, dict] = {}
    if seller_ids_set:
        seller_rows = container.repo.list_sellers_by_ids(list(seller_ids_set))
        for s in seller_rows:
            sid = str(s.get("id") or "")
            if sid:
                seller_map[sid] = s

    # 4. 遍历评估并写入 eval.* 事件
    evaluated = 0
    errors = 0
    for it in to_evaluate:
        try:
            item_id = str(it.get("id") or "")
            if not item_id:
                continue
            seller_id = str(it.get("seller_id") or "")
            seller_data = seller_map.get(seller_id, {})

            detail = ItemDetail(
                id=item_id,
                title=str(it.get("title") or ""),
                price=float(it.get("price") or 0),
                region=str(it.get("region") or ""),
                seller_id=seller_id,
                seller_nick=str(seller_data.get("nick") or ""),
                thumb_url=str(it.get("thumb_url") or ""),
                want_cnt=int(it.get("want_cnt") or 0),
                view_cnt=int(it.get("view_cnt") or 0),
            )
            seller = SellerProfile(
                id=seller_id or "unknown",
                nick=str(seller_data.get("nick") or ""),
                credit_score=seller_data.get("credit_score"),
                register_days=int(seller_data.get("register_days") or 0),
                on_sale_count=int(seller_data.get("on_sale_count") or 0),
                sold_count=int(seller_data.get("sold_count") or 0),
            )
            eval_result = evaluator.evaluate(detail, seller)
            score_display = eval_result.score if eval_result.score is not None else "N/A"
            if eval_result.is_passed:
                level = "info"
            elif eval_result.risk_level != RiskLevel.EXTREME:
                level = "warn"
            else:
                level = "err"
            if eval_result.risk_level == RiskLevel.UNKNOWN:
                level = "warn"
            effective_task_id = str(it.get("task_id") or task_id or "")
            container.repo.upsert_eval_event({
                "type": "eval.scored",
                "task_id": effective_task_id,
                "item_id": item_id,
                "stage": "eval",
                "level": level,
                "message": f"商品 {item_id} 批量评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
                "payload": _json.dumps({
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
            })
            evaluated += 1
        except Exception as e:
            logger.warning(f"批量评估失败 item_id={it.get('id')}: {e}")
            errors += 1
            continue

    return {
        "ok": True,
        "evaluated": evaluated,
        "skipped": skipped,
        "errors": errors,
        "total": evaluated,
        "message": f"已批量评估 {evaluated} 条未评估商品（跳过 {skipped}，错误 {errors}）",
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

    """检查浏览器是否持有有效的闲鱼登录 Cookie，无效时尝试从 JSON 补注入

    为什么需要 JSON 补注入：服务重启后浏览器实例从 SQLite 加载 cookies，
    但 SQLite 可能被锁或同步失败，导致 cookies 仅存在于 JSON 文件中。
    此时通过 Playwright context.add_cookies() 直接注入到浏览器内存。

    P3 增强：除了检查 cookie 存在性，还检查 expires 字段判断是否过期。
    过期 cookie 会导致 page.goto 被 30s 超时浪费，前置检查可快速失败返回 440。
    """
    if not container.browser:
        return

    async def _get_cookies() -> list[dict]:
        try:
            return await container.browser.get_cookies()
        except Exception as e:
            logger.warning("读取浏览器 Cookie 失败: {}", e)
            return []

    def _cookie_by_name(cookies: list[dict]) -> dict[str, dict]:
        return {
            str(c.get("name") or ""): c
            for c in cookies
            if str(c.get("name") or "")
        }

    def _expired_identity_cookies(cookies_by_name: dict[str, dict]) -> list[str]:
        """检查关键 cookie 的 expires 字段，返回已过期的 cookie 名列表。"""
        import time as _time

        now = _time.time()
        expired = []
        for name in _OFFICIAL_COLLECT_IDENTITY_COOKIES:
            c = cookies_by_name.get(name)
            if not c:
                continue
            expires = c.get("expires", -1)
            # 仅 persistent cookie 且已过期才记录；session cookie（expires<=0）跳过
            if expires > 0 and expires < now:
                expired.append(name)
        return expired

    from xianyu_hunter.web.services.cookie_store import get_cookie_store, is_test_cookie

    def _cookies_from_json() -> tuple[list[dict], dict[str, str]]:
        """读取 CookieStore JSON，返回可注入 cookie 和关键 cookie 最新值。"""
        store = get_cookie_store()
        store.invalidate_cache()
        json_data = store._read_json()
        if not json_data or not json_data.get("cookies"):
            return [], {}

        pw_cookies: list[dict] = []
        identity_values: dict[str, str] = {}
        for c in json_data["cookies"]:
            name = str(c.get("name") or "")
            value = str(c.get("value") or "")
            if not name or not value:
                continue
            # 深度防御：跳过测试数据，防止 JSON 被污染时测试值注入浏览器
            if is_test_cookie(name, value):
                logger.warning("官方采集：跳过测试 Cookie {}={}，不注入浏览器", name, value)
                continue

            item = {
                "name": name,
                "value": value,
                "domain": c.get("domain") or ".goofish.com",
                "path": c.get("path") or "/",
            }
            expires = c.get("expires", -1)
            if expires and expires > 0:
                item["expires"] = expires
            pw_cookies.append(item)
            if name in _OFFICIAL_COLLECT_IDENTITY_COOKIES:
                identity_values[name] = value
        return pw_cookies, identity_values

    async def _cookie_issues(json_identity_values: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
        cookies_by_name = _cookie_by_name(await _get_cookies())
        missing = [n for n in _OFFICIAL_COLLECT_IDENTITY_COOKIES if n not in cookies_by_name]
        expired = _expired_identity_cookies(cookies_by_name)
        stale = [
            n for n, value in json_identity_values.items()
            if n in cookies_by_name and cookies_by_name[n].get("value") != value
        ]
        return missing, expired, stale

    pw_cookies, json_identity_values = _cookies_from_json()
    missing, expired, stale = await _cookie_issues(json_identity_values)
    if not missing and not expired and not stale:
        return

    # 浏览器缺少、过期或仍持有旧关键 cookie 时，尝试从 CookieStore JSON 补/替换注入。
    if pw_cookies:
        logger.info(
            "官方采集：准备从 CookieStore JSON 注入 cookie，missing={}, expired={}, stale={}",
            missing, expired, stale,
        )
        try:
            success = await container.browser.add_cookies(pw_cookies)
            if success:
                logger.info("从 CookieStore JSON 补注入/替换 {} 个 cookie 到浏览器", len(pw_cookies))
                # 同步 CookieRotator 层状态：补注入成功说明 JSON 持有有效 cookie，
                # 若层状态从未初始化（updated_at==0.0），此处补救同步避免 /cookies/layers 误显示失效
                try:
                    from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json
                    sync_cookie_layers_from_json()
                except Exception as e:
                    logger.debug("官方采集补注入后同步层状态失败: {}", e)
            else:
                logger.warning("从 CookieStore JSON 注入 cookie 后关键 Cookie 验证未通过")
        except Exception as e:
            logger.warning("从 JSON 补注入 cookie 失败: {}", e)

    # 重新检查补注入后是否仍缺少/过期/陈旧
    missing, expired, stale = await _cookie_issues(json_identity_values)
    if expired:
        logger.warning("官方采集：关键 Cookie 已过期 {}，需重新登录闲鱼", expired)
        raise HTTPException(
            status_code=440,
            detail=f"闲鱼登录 Cookie 已过期（{', '.join(expired)}），请重新登录闲鱼",
        )
    if stale:
        raise HTTPException(
            status_code=440,
            detail=f"闲鱼登录 Cookie 未刷新到采集浏览器（{', '.join(stale)}），请重新登录闲鱼",
        )
    if missing:
        raise HTTPException(
            status_code=403,
            detail=f"闲鱼登录 Cookie 不完整（缺少 {', '.join(missing)}），请重新登录闲鱼",
        )


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

    """完整官方采集：执行 detail + seller + reviews + 重新评估 + events 写入的端到端流程

    语义：
        完整官方采集，调用方在进入本函数前应先执行
        ``_ensure_official_collect_cookies(container)`` 完成 Cookie 同步，
        随后本函数按以下顺序完成端到端采集与评估：

    流程步骤（按代码顺序）：
        1. (前置, 由调用方完成) ``_ensure_official_collect_cookies`` 采集前 Cookie 同步
        2. ``container.collector.detail(item_id, page=own_page)`` 采集商品详情
           （own_page 复用给后续评价提取，避免二次开页）
        3. 并行执行 ``_extract_reviews_from_page(own_page)`` +
           ``container.collector.seller_profile(detail.seller_id)``，
           两者无依赖关系，并行可节省 1-3s
        4. 卖家主页采集失败时降级：
           ``container.collector.seller_profile_fallback(None, detail)``
           用详情页中提取的卖家信息构建基本画像
        5. 持久化到 ``items`` / ``sellers`` / ``task_links.display``，
           items 字段使用 ``_coalesce`` 旧值保留策略（新值为空时保留旧值，
           避免半残数据覆盖本地搜索已写入的有效数据；``_ALWAYS_OVERWRITE``
           集合中的字段除外）
        6. ``evaluator.evaluate(detail, seller)`` 用完整数据重新评估
        7. 更新 ``events`` 表，写 ``eval.scored`` 事件并标记
           ``data_source=official``

    与 refresh_item 的区别：
        ``api_items.py:refresh_item`` 是轻量刷新，仅采集 detail 并 ``upsert_item``，
        不做卖家主页 / 评价提取 / 重新评估 / events 写入。本函数是 refresh_item 的
        "超集"，适合需要完整画像与最新评估分的场景。

    Args:
        container: 应用容器，提供 ``collector`` / ``repo`` / ``evaluator`` 等依赖。
        item_id: 商品 ID。
        task_id: 关联任务 ID，用于写回 items.task_id / events.task_id。
            为空时尝试从 ``get_eval_payload_by_item`` 或现有 items 行回填。

    Returns:
        dict: 包含 ``ok`` / ``item_id`` / ``collected`` / ``item`` / ``seller``
        / ``reviews`` / ``evaluation`` 字段。其中 ``evaluation.data_source``
        固定为 ``"official"``。
    """
    from xianyu_hunter.domain.item import ItemDetail
    from xianyu_hunter.domain.seller import SellerProfile

    # 1. 采集商品详情（传入 own_page 以便后续提取评价）
    own_page = await container.browser.new_page()
    detail: ItemDetail | None = None
    reviews: list[str] = []
    seller: SellerProfile | None = None
    try:
        detail = await container.collector.detail(item_id, page=own_page)
        if detail is None:
            # 尝试从页面 URL/标题获取更精准的失败原因
            page_url = ""
            page_title = ""
            try:
                page_url = own_page.url
                page_title = await own_page.title()
            except Exception:
                pass
            logger.warning(
                "官方采集失败：detail() 返回 None，item_id={}, page_url={}, page_title={}",
                item_id, page_url, page_title,
            )
            # 根据页面 URL/标题 区分用户可操作的失败原因
            # 差异化状态码：440=cookie失效、441=反爬触发、410=商品下架/未加载
            # 仍保留 502 仅给浏览器断连等系统级故障，避免用户误以为是系统问题
            if "login" in page_url.lower() or "passport" in page_url.lower():
                raise HTTPException(
                    status_code=440,
                    detail="采集商品详情失败：页面被重定向到登录页，请重新登录闲鱼后重试",
                )
            if "verify" in page_url.lower() or "captcha" in page_url.lower():
                raise HTTPException(
                    status_code=441,
                    detail="采集商品详情失败：触发闲鱼验证码，请手动完成验证后重试",
                )
            # 首页标题检测：cookie 失效后闲鱼 SPA 在商品 URL 下渲染首页内容
            if page_title and ("闲不住" in page_title or page_title.strip() == "闲鱼"):
                raise HTTPException(
                    status_code=440,
                    detail="采集商品详情失败：闲鱼登录已过期，页面被重定向到首页，请重新登录闲鱼后重试",
                )
            raise HTTPException(
                status_code=410,
                detail=f"采集商品 {item_id} 详情失败：页面可能未正常加载或商品已下架（标题/价格未提取到），请稍后重试",
            )

        # 2. 并行执行：评价提取（依赖 own_page）+ 卖家主页采集（独立 page）
        # 两者无依赖关系，并行可节省 1-3s（卖家主页 page.goto 与 reviews DOM 提取重叠）
        # 注意：reviews 必须在 own_page 关闭前完成，所以放在同一个 try-finally 内
        async def _safe_seller_profile() -> SellerProfile | None:
            if not detail or not detail.seller_id:
                return None
            try:
                return await container.collector.seller_profile(detail.seller_id)
            except Exception as e:
                logger.warning("采集卖家主页失败 seller={}: {}", detail.seller_id, e)
                return None

        reviews, seller = await asyncio.gather(
            _extract_reviews_from_page(own_page),
            _safe_seller_profile(),
        )
    finally:
        await own_page.close()

    # 卖家主页采集失败时降级：用详情页中提取的卖家信息构建基本画像
    if seller is None:
        seller = await container.collector.seller_profile_fallback(None, detail)
    else:
        # 卖家主页采集成功但部分字段为空时，用详情页数据补充
        # 新版闲鱼卖家主页信用分通过图片显示，无法文本提取；注册天数已从卖家主页移除
        if not seller.nick and detail.detail_seller_nick:
            seller.nick = detail.detail_seller_nick
        if seller.credit_score is None and detail.detail_credit_score is not None:
            seller.credit_score = detail.detail_credit_score
        if not seller.sold_count and detail.detail_sold_count:
            seller.sold_count = detail.detail_sold_count
        # 注册天数：新版闲鱼卖家主页已无此字段，从详情页的"来闲鱼X天"补充
        if not seller.register_days and detail.detail_register_days:
            seller.register_days = detail.detail_register_days

    # 3. 持久化到 items 表
    import json as _json
    existing_item = container.repo.get_item(item_id) or {}
    effective_task_id = task_id or ""
    if not effective_task_id:
        existing_payload = container.repo.get_eval_payload_by_item(item_id)
        if existing_payload:
            effective_task_id = existing_payload.get("task_id", "") or ""
    if not effective_task_id:
        effective_task_id = str(existing_item.get("task_id") or "")

    new_item_row = {
        "id": item_id,
        "task_id": effective_task_id,
        "title": detail.title,
        "price": detail.price,
        "description": detail.description or "",
        "image_urls": _json.dumps(detail.image_urls, ensure_ascii=False) if detail.image_urls else None,
        "seller_id": detail.seller_id or "",
        "region": detail.region or "",
        "want_cnt": detail.want_cnt,
        "view_cnt": detail.view_cnt,
        "thumb_url": detail.thumb_url or "",
        "publish_time": detail.publish_time,
        # 销售状态：来自采集侧 detail() 的页面已售关键词检测
        "is_sold": 1 if detail.is_sold else 0,
    }
    # P0 修复：官方采集不应清空已有非空字段
    # 旧值保留策略：新值为 None/空字符串/0 时保留旧值
    # 仅当新值有有效内容时才覆盖
    def _is_blank(v: object) -> bool:
        if v is None:
            return True
        if isinstance(v, str) and v == "":
            return True
        # 仅当新值为 None 或空字符串时视为 blank；数字 0 是合法值
        # （如新发布商品浏览数 0、卖家在售数 0 等），不能被当成"缺失"
        return False

    def _coalesce(new_val: object, old_val: object) -> object:
        """新值为空时保留旧值，避免官方采集半残数据覆盖本地搜索已写入的有效数据"""
        return old_val if _is_blank(new_val) else new_val

    # 允许覆盖的字段（官方采集应优先更新采集时刻 + 来源信息）
    # 数字 0 是合法值（_is_blank 已修正不再当作 blank），所以这些字段
    # 走 ALWAYS_OVERWRITE 不会因新值为 0 而误判为"缺失"
    # 注意：image_urls 不在此集合中——采集未获取到图片时应保留旧值，
    # 而非用 None 覆盖清空已有图片数据（走 _coalesce 逻辑）
    _ALWAYS_OVERWRITE = {"task_id", "publish_time", "view_cnt", "want_cnt", "region", "seller_id", "is_sold"}

    try:
        old_item = existing_item
        item_row = {
            k: (new_item_row[k] if k in _ALWAYS_OVERWRITE else _coalesce(new_item_row[k], old_item.get(k)))
            for k in new_item_row.keys()
        }
        container.repo.upsert_item(item_row)
        # 标记采集来源为 official，供统计端点（auto-collect-stats）按来源筛选
        # 失败不阻断主流程：update_data_source 失败仅记录日志
        try:
            container.repo.update_data_source(item_id, "official")
        except Exception as ds_err:
            logger.warning("更新 data_source=official 失败 item={}: {}", item_id, ds_err)
        # 已售时同步 task_links.display.is_sold（前端列表读 display）
        if detail.is_sold:
            container.repo.mark_sold(item_id)
    except Exception as e:
        logger.warning("更新 items 表失败 item={}: {}", item_id, e)

    # 官方采集完成后也要同步 task_links.display。brand 为空时代表详情页无法验证旧品牌，
    # 必须写回空值，避免评估明细继续从旧 display 读到错误品牌。
    if effective_task_id:
        try:
            sync_item_display_from_detail(container.repo, effective_task_id, item_id, detail, source="auto")
        except Exception as e:
            logger.warning("同步 task_links.display 失败 item={}: {}", item_id, e)

    # 4. 持久化到 sellers 表
    if seller and seller.id and seller.id != "unknown":
        seller_row = {
            "id": seller.id,
            "nick": seller.nick or "",
            "credit_score": seller.credit_score,
            "register_days": seller.register_days,
            "on_sale_count": seller.on_sale_count,
            "sold_count": seller.sold_count,
            "last_visited": _utcnow(),
        }
        try:
            container.repo.upsert_seller(seller_row)
        except Exception as e:
            logger.warning("更新 sellers 表失败 seller={}: {}", seller.id, e)

    # 5. 用完整数据重新评估
    evaluator = container.evaluator
    eval_result = evaluator.evaluate(detail, seller)

    # 6. 更新评估事件（标记数据来源为官方采集）
    score_display = eval_result.score if eval_result.score is not None else "N/A"
    if eval_result.is_passed:
        level = "info"
    elif eval_result.risk_level != RiskLevel.EXTREME:
        level = "warn"
    else:
        level = "err"
    if eval_result.risk_level == RiskLevel.UNKNOWN:
        level = "warn"

    eval_payload = {
        "task_id": effective_task_id or "",  # 写入 payload 保持与其他路径一致
        "item_id": item_id,
        "item_title": detail.title,
        "item_price": detail.price,
        "item_description": detail.description or "",
        "seller_id": detail.seller_id or "",
        "seller_nick": seller.nick if seller else "",
        "seller_credit_score": seller.credit_score if seller else None,
        "seller_on_sale_count": seller.on_sale_count if seller else 0,
        "seller_sold_count": seller.sold_count if seller else 0,
        "seller_register_days": seller.register_days if seller else 0,
        "score": eval_result.score,
        "risk_level": eval_result.risk_level.value,
        "dimension_scores": eval_result.dimension_scores,
        "reject_reasons": eval_result.reject_reasons,
        "is_passed": eval_result.is_passed,
        "data_quality": eval_result.data_quality,
        "data_source": "official",  # 标记数据来源为官方页面采集
        "collected_at": _utcnow().isoformat(),
        "reviews": reviews,  # 评价信息（可能为空）
        "image_urls": detail.image_urls if detail.image_urls else [],
    }

    if effective_task_id:
        try:
            container.repo.upsert_eval_event({
                "type": "eval.scored",
                "task_id": effective_task_id,
                "item_id": item_id,
                "stage": "eval",
                "level": level,
                "message": f"商品 {item_id} 官方采集评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
                "payload": _json.dumps(eval_payload, ensure_ascii=False, default=str),
            })
        except Exception as e:
            logger.warning("更新评估事件失败 item={}: {}", item_id, e)

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
        "reviews": reviews,
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
            # 根据 HTTP 状态码分类失败原因，方便调用方决定是否重试
            # - 410: 商品已下架/不存在 → 不应重试
            # - 其他业务错误 → 标记为 unknown，由调用方自行判断
            if e.status_code == 410:
                error_code = "item_not_found"
            else:
                error_code = "unknown"
            results.append({
                "ok": False, "item_id": iid, "error": e.detail,
                "error_code": error_code,
            })
            failed += 1
        except Exception as e:
            logger.exception("批量采集失败 item={}: {}", iid, e)
            # 区分网络错误与未知错误：网络错误通常可重试，未知错误不应盲目重试
            err_str = str(e)
            if isinstance(e, (TimeoutError, ConnectionError, OSError)):
                error_code = "network_error"
            elif "Timeout" in err_str or "ConnectError" in err_str or "Connection" in err_str:
                error_code = "network_error"
            else:
                error_code = "unknown"
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
