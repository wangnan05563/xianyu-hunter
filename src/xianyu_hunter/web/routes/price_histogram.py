"""价格直方图 API - 商品价格分档统计

端点：
- GET /api/prices/histogram     价格分档直方图（含分位数 + 时间对比）
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from xianyu_hunter.container import Container
from xianyu_hunter.infra.db_models import ItemRow, TaskRow, _utcnow
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api", tags=["prices"])

# 固定的"价格刻度"，方便不同次请求的桶边界一致
_PRICE_TICKS = [0, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]


def _percentile(sorted_prices: list[float], p: float) -> float:
    """线性插值分位数（per NumPy 默认算法）"""
    if not sorted_prices:
        return 0.0
    n = len(sorted_prices)
    if n == 1:
        return float(sorted_prices[0])
    rank = p * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_prices[lo])
    frac = rank - lo
    return sorted_prices[lo] * (1 - frac) + sorted_prices[hi] * frac


def _build_compare_means(
    prices: list[float],
    all_rows_with_ts: list[tuple[str, float]],
) -> dict[str, float]:
    """计算"昨日 / 7 日 / 30 日"均价对比

    O-09-26 扩展：新增 last30d 字段，用于价格趋势对比基线
    """
    if not all_rows_with_ts:
        return {"yesterday": 0.0, "last7d": 0.0, "last30d": 0.0, "diff_pct": 0.0}

    now = _utcnow()
    yesterday_start = now - timedelta(days=1)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    ys_prices: list[float] = []
    wk_prices: list[float] = []
    m_prices: list[float] = []
    for ts, p in all_rows_with_ts:
        d = to_datetime(ts)
        if d is None:
            continue
        if d >= yesterday_start:
            ys_prices.append(p)
        if d >= week_start:
            wk_prices.append(p)
        if d >= month_start:
            m_prices.append(p)

    y_mean = round(sum(ys_prices) / len(ys_prices), 2) if ys_prices else 0.0
    w_mean = round(sum(wk_prices) / len(wk_prices), 2) if wk_prices else 0.0
    m_mean = round(sum(m_prices) / len(m_prices), 2) if m_prices else 0.0
    diff = 0.0
    if w_mean > 0 and y_mean > 0:
        diff = round((y_mean - w_mean) / w_mean * 100, 1)
    return {"yesterday": y_mean, "last7d": w_mean, "last30d": m_mean, "diff_pct": diff}


def _build_buckets(prices: list[float]) -> list[dict[str, Any]]:
    """根据价格样本落入预定义刻度区间，返回 [{min, max, count}, ...]"""
    if not prices:
        return []
    ticks = list(_PRICE_TICKS)
    upper = ticks + [math.inf]
    buckets = []
    for i in range(len(ticks)):
        lo, hi = ticks[i], upper[i + 1]
        cnt = sum(1 for p in prices if lo <= p < hi) if hi != math.inf else sum(
            1 for p in prices if p >= lo
        )
        buckets.append({"min": lo, "max": hi if hi != math.inf else None, "count": cnt})
    return buckets


@router.get("/prices/histogram")
def prices_histogram(
    bins: int = 0,
    task_id: str | None = None,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """商品价格分档直方图（含 P3-UX-03 分位数 + 时间对比）

    P-09-30 修正：
    1. ts_rows 必须与 prices 同源——按 task_id 过滤，否则时间对比基线
       (yesterday/last7d/last30d) 会混入其它任务的价格，导致"较7日变化"
       等表格指标完全失真。
    2. bins=20 分桶范围引入任务定价范围 (min_price/max_price) 并使用
       百分位 (P5/P95) 裁剪极端值，避免单个异常高价把范围拉到 5000+
       而任务实际定价范围只有 100~1000。
    """
    engine = container.repo.engine
    with engine.connect() as conn:
        scope: dict[str, Any] = {"mode": "all", "task_id": None, "task_name": None, "keyword": None, "label": "全部任务"}
        # 任务定价范围（min_price/max_price），用于校准分桶范围与前端标线展示
        task_price_range: dict[str, float | None] = {"min_price": None, "max_price": None}
        if task_id and task_id != "all":
            row = conn.execute(
                select(TaskRow.name, TaskRow.keyword, TaskRow.min_price, TaskRow.max_price)
                .where(TaskRow.id == task_id)
                .limit(1)
            ).first()
            if row:
                name, kw, t_min, t_max = row[0], row[1], row[2], row[3]
                scope = {
                    "mode": "task",
                    "task_id": task_id,
                    "task_name": name,
                    "keyword": kw,
                    "label": f"{name or kw or task_id}（{task_id}）" if (name or kw) else task_id,
                }
                task_price_range = {
                    "min_price": float(t_min) if t_min is not None else None,
                    "max_price": float(t_max) if t_max is not None else None,
                }
            else:
                return {
                    "bins": [],
                    "summary": {
                        "count": 0, "min": 0, "max": 0, "mean": 0, "median": 0,
                        "p25": 0, "p75": 0,
                        "compare": {"yesterday": 0, "last7d": 0, "last30d": 0, "diff_pct": 0},
                        "task_price_range": task_price_range,
                    },
                    "scope": {**scope, "task_id": task_id, "label": f"任务 {task_id}（不存在）"},
                    "mode": "fixed",
                }

        if scope["mode"] == "task":
            # task_id 有 ix_items_task_first_seen 索引，查询高效，但仍加 LIMIT 防止极端数据量
            rows = conn.execute(
                select(ItemRow.price).where(ItemRow.task_id == task_id).limit(10000)
            ).all()
        else:
            # 全表查询必须有 LIMIT，防止大表撑爆内存
            rows = conn.execute(select(ItemRow.price).limit(10000)).all()
        prices = [float(r[0]) for r in rows if r and r[0] is not None]

        # P-09-30 关键修复：ts_rows 必须与 prices 同源，按 task_id 过滤
        # 修复前为全表查询，导致选定任务时 yesterday/last7d/last30d 基线混入其它任务价格
        ts_query = select(ItemRow.price, ItemRow.publish_time)
        if scope["mode"] == "task":
            ts_query = ts_query.where(ItemRow.task_id == task_id)
        ts_rows = conn.execute(
            ts_query.order_by(ItemRow.publish_time.desc()).limit(2000)
        ).all()
        all_with_ts = [(r[1], float(r[0])) for r in ts_rows if r and r[0] is not None and r[1]]

    if not prices:
        return {
            "bins": [],
            "summary": {
                "count": 0, "min": 0, "max": 0, "mean": 0, "median": 0,
                "p25": 0, "p75": 0,
                "compare": {"yesterday": 0, "last7d": 0, "last30d": 0, "diff_pct": 0},
                "task_price_range": task_price_range,
            },
            "scope": scope,
            "mode": "fixed",
        }

    sorted_p = sorted(prices)
    p25 = round(_percentile(sorted_p, 0.25), 2)
    p75 = round(_percentile(sorted_p, 0.75), 2)
    mean_val = round(sum(prices) / len(prices), 2)
    median_val = round(sorted_p[len(sorted_p) // 2], 2)
    compare = _build_compare_means(prices, all_with_ts)

    if bins == 20:
        # P-09-30: 分桶范围校准——百分位裁剪 + 任务定价范围融合
        # 旧逻辑用 min(prices)/max(prices)，单个异常高价（如 5000）会把范围拉到 5000，
        # 而任务实际定价范围可能只有 100~1000，导致前 2 个桶装着大部分商品、其余全为 0。
        # 新逻辑：
        #   1. 用 P5/P95 裁剪极端值，分桶范围聚焦主要分布；
        #   2. 融合任务定价范围 (min_price/max_price)，确保分桶范围覆盖定价区间；
        #   3. 首尾桶吸收范围外的极端值，保证商品计数不丢失。
        p5 = _percentile(sorted_p, 0.05)
        p95 = _percentile(sorted_p, 0.95)
        t_min = task_price_range["min_price"]
        t_max = task_price_range["max_price"]
        # 下界取 P5 与任务定价下界的较小值，确保覆盖任务定价范围
        lo = min(p5, t_min) if t_min is not None else p5
        # 上界取 P95 与任务定价上界的较大值，确保覆盖任务定价范围
        hi = max(p95, t_max) if t_max is not None else p95
        lo = max(0.0, lo)
        if hi <= lo:
            hi = lo + 1
        step = (hi - lo) / 20
        result = []
        for i in range(20):
            b_lo = lo + i * step
            b_hi = b_lo + step if i < 19 else hi + 1
            # 首桶吸收所有低于 b_lo 的极端低价；尾桶吸收所有 >= b_lo 的极端高价
            if i == 0:
                cnt = sum(1 for p in prices if p < b_hi)
            elif i == 19:
                cnt = sum(1 for p in prices if b_lo <= p)
            else:
                cnt = sum(1 for p in prices if b_lo <= p < b_hi)
            result.append({"min": round(b_lo, 2), "max": round(b_hi, 2) if i < 19 else round(hi, 2), "count": cnt})
        return {
            "bins": result,
            "summary": {
                "count": len(prices),
                # 真实最小/最大值（不是分桶下/上界），让前端能显示真实价格范围
                "min": round(sorted_p[0], 2),
                "max": round(sorted_p[-1], 2),
                "mean": mean_val,
                "median": median_val,
                "p25": p25,
                "p75": p75,
                "compare": compare,
                "task_price_range": task_price_range,
            },
            "scope": scope,
            "mode": "auto",
        }

    bins_data = _build_buckets(prices)
    return {
        "bins": bins_data,
        "summary": {
            "count": len(prices),
            "min": round(sorted_p[0], 2),
            "max": round(sorted_p[-1], 2),
            "mean": mean_val,
            "median": median_val,
            "p25": p25,
            "p75": p75,
            "compare": compare,
            "task_price_range": task_price_range,
        },
        "scope": scope,
        "mode": "fixed",
    }


@router.post("/prices/analyze")
def prices_analyze(
    task_id: str | None = None,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """基于直方图数据调用 LLM 生成价格分析建议

    将价格分布统计信息（分位数、均价、时间对比等）组装为 prompt，
    调用已配置的 LLM 生成面向用户的参考意见。
    """
    from xianyu_hunter.config import get_settings
    from xianyu_hunter.infra.ai_usage import check_budget, record_usage
    import httpx

    settings = get_settings()
    if not settings.openai_api_key:
        return {"analysis": "未配置 AI 服务密钥，无法生成分析。请在「AI 服务」配置页面设置 API Key。", "source": "error"}

    allowed, reason = check_budget()
    if not allowed:
        return {"analysis": f"AI 调用受限：{reason}", "source": "error"}

    # 复用 histogram 端点获取统计数据
    hist = prices_histogram(bins=20, task_id=task_id, container=container)
    summary = hist.get("summary", {})
    scope = hist.get("scope", {})

    if not summary.get("count"):
        return {"analysis": "当前无商品数据，无法生成分析。", "source": "empty"}

    # 组装分析 prompt
    compare = summary.get("compare", {})
    scope_label = scope.get("label", "全部任务")
    prompt = f"""你是一位闲鱼商品价格分析专家。请根据以下价格分布统计数据，给出简洁实用的分析建议。

## 数据概览（{scope_label}）
- 商品总数: {summary.get('count', 0)} 件
- 价格范围: ¥{summary.get('min', 0)} ~ ¥{summary.get('max', 0)}
- 均价: ¥{summary.get('mean', 0)}，中位数: ¥{summary.get('median', 0)}
- P25: ¥{summary.get('p25', 0)}，P75: ¥{summary.get('p75', 0)}
- 7日均价: ¥{compare.get('last7d', 0)}，今日均价: ¥{compare.get('yesterday', 0)}
- 较7日变化: {compare.get('diff_pct', 0)}%

## 价格分档
{chr(10).join(f"- ¥{b['min']:.0f}~¥{b['max']:.0f}: {b['count']}件" if b.get('max') is not None else f"- ¥{b['min']:.0f}~+: {b['count']}件" for b in hist.get('bins', []))}

请从以下维度分析，每点1-2句话：
1. **价格分布特征**：集中度、偏态、是否存在异常高价/低价
2. **性价比区间**：结合 P25-P75 推荐值得关注的价位段
3. **趋势判断**：对比7日均价，价格是涨是跌，是否适合入手
4. **策略建议**：针对监控任务的价格上下限设置给出具体建议

请用中文回答，语气专业但平易近人。"""

    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": "你是一位闲鱼商品价格分析专家，擅长从价格分布数据中提炼洞察并给出实用建议。回答简洁，重点突出。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 800,
    }
    headers = {
        # S3457: 字符串拼接改 f-string
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        return {"analysis": "AI 分析超时，请稍后重试。", "source": "error"}
    except httpx.HTTPError as e:
        return {"analysis": f"AI 服务网络错误: {e}", "source": "error"}

    if r.status_code != 200:
        return {"analysis": f"AI 服务返回错误 ({r.status_code})，请检查 API 配置。", "source": "error"}

    try:
        resp_data = r.json()
        record_usage("price_analyze", settings.openai_model, resp_data)
        content = resp_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError):
        return {"analysis": "AI 返回格式异常，请重试。", "source": "error"}

    return {"analysis": content, "source": "ai", "scope_label": scope_label}
