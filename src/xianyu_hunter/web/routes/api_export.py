"""P1-5 数据导出 API

支持将商品/评估/订单/事件数据导出为 CSV 格式。
按时间/任务筛选，Excel/Numbers 友好。

设计要点：
- 复用 Repository 现有查询方法，避免新增 DAO
- CSV 流式输出，避免大结果集占用内存
- 统一导出端点 /api/export/{dataset}，dataset ∈ {items, evaluations, orders, events}
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Iterable

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.utils import to_datetime

router = APIRouter(prefix="/api/export", tags=["export"])

# 每种数据集对应的列定义（顺序即 CSV 列顺序）
_DATASET_COLUMNS: dict[str, list[str]] = {
    "items": [
        "id", "task_id", "title", "price", "publish_time", "region",
        "seller_id", "want_cnt", "view_cnt", "first_seen", "last_seen",
    ],
    "evaluations": [
        "id", "item_id", "seller_id", "score", "risk_level",
        "dimension_scores", "reject_reasons", "created_at",
    ],
    "orders": [
        "id", "task_id", "item_id", "seller_id", "order_no",
        "price", "status", "confirmed_at", "paid_at", "created_at",
    ],
    "events": [
        "id", "type", "task_id", "item_id", "stage",
        "level", "message", "created_at",
    ],
}


def _row_value(row: dict[str, Any], col: str) -> Any:
    """安全提取行字段，缺失返回空字符串"""
    v = row.get(col)
    return "" if v is None else v


def _filter_by_time(
    rows: Iterable[dict[str, Any]],
    time_col: str,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> list[dict[str, Any]]:
    """按时间范围过滤行（Python 侧过滤，避免新增 DAO 方法）"""
    if not start_dt and not end_dt:
        return list(rows)
    out: list[dict[str, Any]] = []
    for r in rows:
        t = to_datetime(r.get(time_col))
        if t is None:
            continue
        if start_dt and t < start_dt:
            continue
        if end_dt and t > end_dt:
            continue
        out.append(r)
    return out


def _build_csv_response(
    rows: list[dict[str, Any]],
    columns: list[str],
    dataset: str,
) -> StreamingResponse:
    """构造 CSV 流式响应（含 BOM 头，确保 Excel 正确识别 UTF-8）"""
    buf = io.StringIO()
    # UTF-8 BOM：让 Excel/Numbers 正确识别编码
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(columns)
    for r in rows:
        writer.writerow([_row_value(r, c) for c in columns])
    fname = f"xh-{dataset}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/{dataset}")
def export_dataset(
    dataset: str,
    task_id: str | None = Query(None, description="按任务 ID 过滤"),
    start: str | None = Query(None, description="起始时间 ISO 格式（如 2026-06-01T00:00:00）"),
    end: str | None = Query(None, description="截止时间 ISO 格式"),
    status: str | None = Query(None, description="订单状态过滤（仅 orders 数据集）"),
    level: str | None = Query(None, description="事件等级过滤（仅 events 数据集）"),
    limit: int = Query(5000, ge=1, le=50000, description="最大导出行数"),
    container: Container = Depends(get_container),
) -> StreamingResponse:
    """导出数据集为 CSV

    支持的数据集：
    - items: 商品列表（按 first_seen 倒序）
    - evaluations: 评估记录（按 created_at 倒序）
    - orders: 订单记录（按 created_at 倒序）
    - events: 事件日志（按 created_at 倒序）

    通用筛选：
    - task_id: 按任务过滤（items/orders/events 支持）
    - start/end: 时间范围过滤

    特定筛选：
    - status: 仅 orders，按订单状态过滤
    - level: 仅 events，按事件等级过滤
    """
    if dataset not in _DATASET_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"未知数据集 {dataset}，可用: {list(_DATASET_COLUMNS.keys())}",
        )

    columns = _DATASET_COLUMNS[dataset]
    # 用 to_datetime 而非 parse_iso_datetime：确保返回 aware datetime，
    # 与 _filter_by_time 中 to_datetime(row[time_col]) 的结果类型一致，
    # 避免 naive vs aware 比较抛 TypeError
    start_dt = to_datetime(start)
    end_dt = to_datetime(end)

    if dataset == "items":
        rows = container.repo.list_items(task_id=task_id, limit=limit)
        rows = _filter_by_time(rows, "first_seen", start_dt, end_dt)

    elif dataset == "evaluations":
        # evaluations 表无 task_id 列，需通过 items 表间接过滤
        if task_id:
            item_ids = {r["id"] for r in container.repo.list_items(task_id=task_id, limit=limit)}
            # evaluations 无 list 方法，通过 events 表反查或直接查 DB
            rows = _list_evaluations_by_items(container, item_ids, limit)
        else:
            rows = _list_all_evaluations(container, limit)
        rows = _filter_by_time(rows, "created_at", start_dt, end_dt)

    elif dataset == "orders":
        rows = container.repo.list_orders(status=status, limit=limit)
        if task_id:
            rows = [r for r in rows if r.get("task_id") == task_id]
        rows = _filter_by_time(rows, "created_at", start_dt, end_dt)

    else:  # events
        rows = container.repo.list_events(level=level, task_id=task_id, limit=limit) or []
        rows = _filter_by_time(rows, "created_at", start_dt, end_dt)

    return _build_csv_response(rows, columns, dataset)


def _list_all_evaluations(container: Container, limit: int) -> list[dict[str, Any]]:
    """列出所有评估记录（直接查表，避免新增 DAO 方法）"""
    from sqlalchemy import select
    from xianyu_hunter.infra.db_models import EvaluationRow

    with container.repo.engine.connect() as conn:
        stmt = (
            select(EvaluationRow)
            .order_by(EvaluationRow.created_at.desc())
            .limit(limit)
        )
        return [container.repo._row_to_dict(r) for r in conn.execute(stmt).all()]


def _list_evaluations_by_items(
    container: Container,
    item_ids: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    """按 item_id 集合查评估记录"""
    if not item_ids:
        return []
    from sqlalchemy import select
    from xianyu_hunter.infra.db_models import EvaluationRow

    out: list[dict[str, Any]] = []
    # 分批查询避免 SQLite IN 子句参数上限
    batch_size = 500
    item_list = list(item_ids)
    with container.repo.engine.connect() as conn:
        for i in range(0, len(item_list), batch_size):
            batch = item_list[i:i + batch_size]
            stmt = (
                select(EvaluationRow)
                .where(EvaluationRow.item_id.in_(batch))
                .order_by(EvaluationRow.created_at.desc())
                .limit(limit)
            )
            out.extend(container.repo._row_to_dict(r) for r in conn.execute(stmt).all())
            if len(out) >= limit:
                out = out[:limit]
                break
    return out


@router.get("")
def list_export_datasets() -> dict[str, Any]:
    """列出可导出的数据集及说明（前端导出按钮调用）"""
    return {
        "datasets": [
            {
                "key": k,
                "columns": v,
                "description": _DATASET_DESCRIPTIONS.get(k, ""),
            }
            for k, v in _DATASET_COLUMNS.items()
        ]
    }


_DATASET_DESCRIPTIONS = {
    "items": "商品列表（含价格、卖家、发布时间）",
    "evaluations": "评估记录（含评分、风险等级、拒绝原因）",
    "orders": "订单记录（含订单号、价格、状态、时间）",
    "events": "事件日志（含类型、等级、消息）",
}
