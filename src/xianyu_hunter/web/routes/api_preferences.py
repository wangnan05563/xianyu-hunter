"""用户偏好 API - 替代 localStorage，按 user_id 隔离

设计文档 §3.5.3 用户偏好 API 蓝图实现。

仅提供批量 GET / PUT 端点：前端 useColumnConfig 等 hook 一次拉取全部偏好，
单次更新也以 dict 形式批量提交，减少请求次数。

pref_value 在库中存储为 JSON 序列化字符串，路由层负责序列化 / 反序列化。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text as sa_text

from xianyu_hunter.web.services.user_manager import UserManager, get_user_manager

router = APIRouter(prefix="/api/preferences", tags=["preferences"])

# 防御 DoS：单次 PUT 的 key 数量与单值序列化后字节数都设上限
# 为什么不依赖框架默认限制：FastAPI/Starlette 对 JSON body 的默认限制是字符串数量级，
# 无法阻止"key 数量巨大但单 value 很小"或"单 value 巨大"两类滥用
_MAX_PREF_KEYS = 100
_MAX_PREF_VALUE_SIZE = 64 * 1024  # 64KB

# 偏好 key 格式校验：字母/下划线开头，后接字母数字下划线点号，长度 1-64
# 为什么限制字符集：pref_key 直接拼入 raw SQL（参数化绑定避免注入），
# 限制字符集是纵深防御，避免控制字符 / SQL 关键字通过校验进入数据库
# 为什么允许点号：前端 hook（如 useColumnConfig）用 "items.columns" 这种命名空间格式
_PREF_KEY_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]{0,63}$")

# 复用 UserManager 的 default 用户常量，避免"魔法字符串"散落多处导致语义漂移
_DEFAULT_USER_ID = UserManager.DEFAULT_USER_ID


@router.get("")
def get_preferences(request: Request) -> dict[str, Any]:
    """获取当前用户所有偏好，合并为 {key: value, ...} 格式返回

    pref_value 在库中存储为 JSON 序列化字符串，此处反序列化为原始值。
    解析失败降级为原始字符串，避免单条脏数据导致整体 500。
    """
    user_id = getattr(request.state, "user_id", _DEFAULT_USER_ID)
    user_manager = get_user_manager()
    # 通过只读 property 访问 engine，避免直接穿透 _engine 私有属性
    engine = user_manager.engine

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

    # key 格式校验：在写库前拦截非法 key，避免脏数据进入 user_preferences
    # 为什么在循环外先校验：保证任一 key 非法时整体回滚，不会有部分写入
    for key in body:
        if not isinstance(key, str) or not _PREF_KEY_RE.match(key):
            raise HTTPException(400, f"非法偏好 key: {key}")

    user_id = getattr(request.state, "user_id", _DEFAULT_USER_ID)
    user_manager = get_user_manager()
    engine = user_manager.engine

    # onupdate=_utcnow 是 ORM 特性，raw SQL 不会触发，需显式提供 updated_at
    # 为什么传 datetime 对象而非 ISO 字符串：ORM 的 default=_utcnow 返回 datetime，
    # raw SQL 也传 datetime 才能保证存储格式一致（避免混合存储导致后续排序/比较异常）
    now = datetime.now(timezone.utc)
    # 使用 engine.begin() 而非 engine.connect() + 手动 commit：
    # begin() 在异常时自动回滚，避免循环中途失败留下部分写入的脏数据
    with engine.begin() as conn:
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

    return {"ok": True, "count": len(body)}


@router.delete("/{key}")
def delete_preference(key: str, request: Request) -> dict[str, Any]:
    """删除当前用户的单个偏好项

    与 PUT 配合：PUT 用于 UPSERT，DELETE 用于显式清除某项，
    前端重置某列配置为默认值时调用（PUT 空值会被当作有效值存储，语义不等价于删除）。
    """
    user_id = getattr(request.state, "user_id", _DEFAULT_USER_ID)
    user_manager = get_user_manager()
    engine = user_manager.engine

    with engine.begin() as conn:
        conn.execute(
            sa_text(
                "DELETE FROM user_preferences WHERE user_id=:uid AND pref_key=:k"
            ),
            {"uid": user_id, "k": key},
        )

    return {"ok": True}
