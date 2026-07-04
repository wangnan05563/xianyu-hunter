"""用户偏好 API - 替代 localStorage，按 user_id 隔离

设计文档 §3.5.3 用户偏好 API 蓝图实现。

仅提供批量 GET / PUT 端点：前端 useColumnConfig 等 hook 一次拉取全部偏好，
单次更新也以 dict 形式批量提交，减少请求次数。

pref_value 在库中存储为 JSON 序列化字符串，路由层负责序列化 / 反序列化。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import text as sa_text

from xianyu_hunter.web.services.user_manager import get_user_manager

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("")
def get_preferences(request: Request) -> dict[str, Any]:
    """获取当前用户所有偏好，合并为 {key: value, ...} 格式返回

    pref_value 在库中存储为 JSON 序列化字符串，此处反序列化为原始值。
    解析失败降级为原始字符串，避免单条脏数据导致整体 500。
    """
    user_id = getattr(request.state, "user_id", "default")
    user_manager = get_user_manager()
    engine = user_manager._engine

    with engine.connect() as conn:
        rows = conn.execute(
            sa_text(
                "SELECT pref_key, pref_value FROM user_preferences WHERE user_id=:uid"
            ),
            {"uid": user_id},
        ).fetchall()

    result: dict[str, Any] = {}
    for r in rows:
        try:
            result[r[0]] = json.loads(r[1])
        except (json.JSONDecodeError, TypeError):
            # 历史脏数据降级为字符串，不阻断整体读取
            result[r[0]] = r[1]
    return result


@router.put("")
def update_preferences(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """更新当前用户偏好，逐条 UPSERT

    接收 {key: value, ...} 格式，value 会被 JSON 序列化后存储到 pref_value 字段。
    SQLite UPSERT 依赖 user_preferences 表的 UNIQUE(user_id, pref_key) 约束。
    """
    user_id = getattr(request.state, "user_id", "default")
    user_manager = get_user_manager()
    engine = user_manager._engine

    # onupdate=_utcnow 是 ORM 特性，raw SQL 不会触发，需显式提供 updated_at
    now = datetime.now(timezone.utc).isoformat()
    with engine.connect() as conn:
        for key, value in body.items():
            # JSON 序列化保留类型信息（list/dict/number/bool 都可还原）
            value_str = json.dumps(value, ensure_ascii=False)
            conn.execute(
                sa_text(
                    "INSERT INTO user_preferences (user_id, pref_key, pref_value, updated_at) "
                    "VALUES (:uid, :k, :v, :now) "
                    "ON CONFLICT(user_id, pref_key) DO UPDATE SET "
                    "pref_value=:v, updated_at=:now"
                ),
                {"uid": user_id, "k": key, "v": value_str, "now": now},
            )
        conn.commit()

    return {"ok": True, "count": len(body)}
