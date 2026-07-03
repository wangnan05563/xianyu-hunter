"""P1-7 Cron 定时调度 API

提供 cron 表达式校验和下次触发时间预览，
让前端在创建/编辑任务时验证 cron 表达式。

设计要点：
- 复用 modules/cron_utils.py 的解析逻辑
- 返回未来 5 次触发时间，方便用户预览
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from xianyu_hunter.modules.cron_utils import (
    next_run_time,
    validate_cron,
)

router = APIRouter(prefix="/api/cron", tags=["cron"])


class CronValidateBody(BaseModel):
    """cron 表达式校验请求"""
    cron: str = Field(..., min_length=1, max_length=100, description="5 字段 cron 表达式")


@router.post("/validate")
def validate_cron_expr(body: CronValidateBody) -> dict[str, Any]:
    """校验 cron 表达式并返回未来 5 次触发时间

    返回：
    - valid: 是否合法
    - next_runs: 未来 5 次触发时间（UTC ISO 格式）
    - error: 非法时的错误信息
    """
    if not validate_cron(body.cron):
        return {
            "valid": False,
            "cron": body.cron,
            "next_runs": [],
            "error": "表达式格式错误，需 5 字段：minute hour day month day_of_week",
        }

    # 计算未来 5 次触发时间
    now = datetime.now(timezone.utc)
    next_runs: list[str] = []
    current = now
    for _ in range(5):
        try:
            nxt = next_run_time(body.cron, current)
            next_runs.append(nxt.isoformat())
            current = nxt + timedelta(seconds=1)
        except ValueError:
            break

    return {
        "valid": True,
        "cron": body.cron,
        "next_runs": next_runs,
        "error": None,
    }


@router.get("/examples")
def cron_examples() -> dict[str, Any]:
    """返回常用 cron 表达式示例（前端下拉选择用）"""
    return {
        "examples": [
            {"cron": "*/1 * * * *", "label": "每分钟"},
            {"cron": "*/5 * * * *", "label": "每 5 分钟"},
            {"cron": "*/10 * * * *", "label": "每 10 分钟"},
            {"cron": "*/30 * * * *", "label": "每 30 分钟"},
            {"cron": "0 * * * *", "label": "每小时整点"},
            {"cron": "0 9-22 * * *", "label": "每天 9:00-22:00 整点"},
            {"cron": "*/30 9-22 * * *", "label": "每天 9:00-22:00 每 30 分钟"},
            {"cron": "*/10 9-22 * * 1-5", "label": "工作日 9:00-22:00 每 10 分钟"},
            {"cron": "0 9 * * 1", "label": "每周一 9:00"},
            {"cron": "0 0,12 * * *", "label": "每天 0:00 和 12:00"},
        ]
    }
