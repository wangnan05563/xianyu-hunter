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

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text as sa_text

from xianyu_hunter.web.services.user_manager import get_user_manager

router = APIRouter(prefix="/api/preferences", tags=["preferences"])

# 防御 DoS：单次 PUT 的 key 数量与单值序列化后字节数都设上限
# 为什么不依赖框架默认限制：FastAPI/Starlette 对 JSON body 的默认限制是字符串数量级，
# 无法阻止"key 数量巨大但单 value 很小"或"单 value 巨大"两类滥用
_MAX_PREF_KEYS = 100
_MAX_PREF_VALUE_SIZE = 64 * 1024  # 64KB


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
    # 入参大小校验：阻止恶意大 body 撑爆 SQLite 与内存
    if len(body) > _MAX_PREF_KEYS:
        raise HTTPException(400, f"偏好项数量超过上限 {_MAX_PREF_KEYS}")

    user_id = getattr(request.state, "user_id", "default")
    user_manager = get_user_manager()
    engine = user_manager._engine

    # onupdate=_utcnow 是 ORM 特性，raw SQL 不会触发，需显式提供 updated_at
    now = datetime.now(timezone.utc).isoformat()
    with engine.connect() as conn:
        for key, value in body.items():
            # JSON 序列化保留类型信息（list/dict/number/bool 都可还原）
            value_str = json.dumps(value, ensure_ascii=False)
            # 单值大小校验：64KB 足以覆盖列配置/筛选器等正常场景，
            # 同时阻止单条超大 value 写入 Text 字段造成的 IO 放大
            if len(value_str) > _MAX_PREF_VALUE_SIZE:
                raise HTTPException(400, f"偏好值 {key} 超过 {_MAX_PREF_VALUE_SIZE} 字节")
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


@router.delete("/{key}")
def delete_preference(key: str, request: Request) -> dict[str, Any]:
    """删除当前用户的单个偏好项

    与 PUT 配合：PUT 用于 UPSERT，DELETE 用于显式清除某项，
    前端重置某列配置为默认值时调用（PUT 空值会被当作有效值存储，语义不等价于删除）。
    """
    user_id = getattr(request.state, "user_id", "default")
    user_manager = get_user_manager()
    engine = user_manager._engine

    with engine.begin() as conn:
        conn.execute(
            sa_text(
                "DELETE FROM user_preferences WHERE user_id=:uid AND pref_key=:k"
            ),
            {"uid": user_id, "k": key},
        )

    return {"ok": True}
