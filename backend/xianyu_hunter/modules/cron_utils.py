"""P1-7 Cron 表达式工具

基于 APScheduler 的 CronTrigger 实现 5 字段 cron 表达式解析，
计算下次触发时间。

支持标准 5 字段：minute hour day month day_of_week
示例：
- "*/10 * * * *"       每 10 分钟
- "0 9-22 * * *"        每天 9:00-22:00 整点
- "*/30 9-22 * * 1-5"   工作日 9:00-22:00 每 30 分钟
- "0 9 * * 1"           每周一 9:00
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apscheduler.triggers.cron import CronTrigger

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


def parse_cron(cron_expr: str) -> CronTrigger:
    """解析 cron 表达式为 CronTrigger

    Args:
        cron_expr: 5 字段 cron 表达式（minute hour day month day_of_week）

    Returns:
        CronTrigger 实例

    Raises:
        ValueError: 表达式格式错误
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(
            f"cron 表达式必须是 5 字段（minute hour day month day_of_week），"
            f"收到 {len(parts)} 字段: {cron_expr!r}"
        )
    minute, hour, day, month, day_of_week = parts
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone="UTC",
    )


def next_run_time(cron_expr: str, from_time: datetime | None = None) -> datetime:
    """计算 cron 表达式的下次触发时间

    Args:
        cron_expr: 5 字段 cron 表达式
        from_time: 起始时间（UTC），默认当前时间

    Returns:
        下次触发时间（UTC，timezone-aware）

    Raises:
        ValueError: 表达式格式错误
    """
    if from_time is None:
        from_time = datetime.now(timezone.utc)
    elif from_time.tzinfo is None:
        # 无时区信息视为 UTC
        from_time = from_time.replace(tzinfo=timezone.utc)

    trigger = parse_cron(cron_expr)
    next_time = trigger.get_next_fire_time(None, from_time)
    if next_time is None:
        # 理论上不会发生（cron 总有未来触发时间），但防御性处理
        return from_time + timedelta(days=365)
    return next_time


def seconds_until_next_run(cron_expr: str, from_time: datetime | None = None) -> float:
    """计算距离下次触发的秒数

    Args:
        cron_expr: 5 字段 cron 表达式
        from_time: 起始时间（UTC），默认当前时间

    Returns:
        距离下次触发的秒数（float，最小 1.0 避免立即触发）

    Raises:
        ValueError: 表达式格式错误
    """
    if from_time is None:
        from_time = datetime.now(timezone.utc)
    elif from_time.tzinfo is None:
        from_time = from_time.replace(tzinfo=timezone.utc)

    next_time = next_run_time(cron_expr, from_time)
    delta = (next_time - from_time).total_seconds()
    # 最小 1 秒，避免 0 或负数导致 sleep 立即返回
    return max(1.0, delta)


def validate_cron(cron_expr: str) -> bool:
    """校验 cron 表达式是否合法

    Args:
        cron_expr: 5 字段 cron 表达式

    Returns:
        True 合法，False 非法
    """
    try:
        parse_cron(cron_expr)
        return True
    # S5713: ValueError 是 Exception 的子类，仅保留父类即可覆盖
    except Exception:
        return False
