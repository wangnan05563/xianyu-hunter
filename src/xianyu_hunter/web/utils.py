"""Web 层公共工具函数

消除 routes/ 各模块间的重复代码（datetime 解析、payload 序列化等）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


# 常见的 ISO 时间格式（按优先级尝试）
_ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def parse_iso_datetime(s: str | None) -> datetime | None:
    """将 ISO 格式时间字符串解析为 datetime 对象

    支持格式：2026-06-08T00:00:00 / 2026-06-08T00:00:00.123456 /
              2026-06-08 00:00:00 / 2026-06-08
    解析失败返回 None（不抛异常，让过滤静默跳过）

    之前各路由模块各自实现 _parse_iso_datetime / _to_dt / _parse_dt，
    逻辑完全相同，统一收敛到此函数。
    """
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    # 按长度降序排列，优先匹配精度更高的格式
    for fmt in _ISO_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # 带时区后缀的 ISO 字符串（如 +08:00），截掉后缀再尝试
    if "+" in s or (s.count("-") > 2 and s[-6] in "+-"):
        for fmt in _ISO_FORMATS:
            try:
                # 找到最后一个 + 或 - 作为时区分隔符
                tz_pos = max(s.rfind("+"), s.rfind("-"))
                return datetime.strptime(s[:tz_pos], fmt)
            except ValueError:
                continue
    return None


def to_datetime(v: Any) -> datetime | None:
    """统一把 datetime / str / None 转 aware datetime（UTC）

    ORM Row → dict 后，created_at 可能是 datetime 对象（直接查）
    也可能是 str（JSON 序列化后还原）。此函数统一收敛到带 UTC 时区的 datetime，
    避免与 _utcnow() 比较时抛 TypeError: can't compare offset-naive and offset-aware。
    """
    if v is None:
        return None
    if isinstance(v, datetime):
        # 数据库存储的是 UTC 时间，但 SQLite 不保留时区信息
        # 统一添加 UTC 时区，避免与 _utcnow() 比较时报错
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    if isinstance(v, str):
        d = parse_iso_datetime(v)
        if d is not None and d.tzinfo is None:
            return d.replace(tzinfo=timezone.utc)
        return d
    return None


def payload_text(payload: Any) -> str:
    """把 payload 序列化成可搜索的文本

    - dict/list → json
    - str → 原样
    - None/其他 → 空串
    """
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        return str(payload)
