"""菜单配置 API - 用户菜单的查询 / 更新 / 重置

设计文档：docs/07-权限模块/2026-07-01-登录模块优化概要设计.md §3.5.2 菜单配置 API 蓝图

路由前缀 /api/menu，所有端点需鉴权（中间件注入 request.state.user_id）。
- GET    /api/menu        获取当前用户菜单（已合并 registry 默认值 + 用户级覆盖）
- PUT    /api/menu        更新当前用户菜单配置（UPSERT 用户级覆盖）
- POST   /api/menu/reset  重置当前用户菜单为默认配置
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from xianyu_hunter.web.services.menu_manager import get_menu_manager
from xianyu_hunter.web.services.user_manager import UserManager

router = APIRouter(prefix="/api/menu", tags=["menu"])

# 复用 UserManager 的 default 用户常量，避免"魔法字符串"散落多处
# WEB_TOKEN 管理令牌直通场景下 request.state.user_id 可能缺失，需要兜底
_DEFAULT_USER_ID = UserManager.DEFAULT_USER_ID


class MenuItemUpdate(BaseModel):
    """单个菜单项的用户级覆盖入参"""
    key: str = Field(..., min_length=1, description="对应 registry 的 menu key")
    visible: bool = True
    sort_order: int = Field(0, ge=0, le=10000)


class MenuUpdateBody(BaseModel):
    """PUT /api/menu 请求体"""
    # 限制 menus 长度：registry 总共约 25 项，100 上限足以覆盖未来扩展，
    # 同时阻止恶意提交超大数组撑爆 UPSERT 循环与数据库 IO
    menus: list[MenuItemUpdate] = Field(..., max_length=100)


@router.get("")
def get_menu(request: Request) -> dict[str, Any]:
    """获取当前用户菜单

    返回 {menus: [...]}，已按 sort_order 升序排列，仅包含 visible=True 的项。
    用户无配置时返回 registry 默认值。
    """
    user_id = getattr(request.state, "user_id", _DEFAULT_USER_ID)
    manager = get_menu_manager()
    menus = manager.get_menus(user_id)
    return {"menus": menus}


@router.put("")
def update_menu(body: MenuUpdateBody, request: Request) -> dict[str, Any]:
    """更新当前用户菜单配置（UPSERT）

    入参 {menus: [{key, visible, sort_order}, ...]}，
    仅更新本次显式提交的项，不影响其他项的既有配置。
    """
    user_id = getattr(request.state, "user_id", _DEFAULT_USER_ID)
    manager = get_menu_manager()
    # Pydantic model_dump 转为普通 dict 供 MenuManager 逐条 UPSERT
    items = [m.model_dump() for m in body.menus]
    try:
        manager.update_menu_config(user_id, items)
    except (ValueError, TypeError) as e:
        # 入参类型错误（如 sort_order 非整数）已由 Pydantic 拦截，
        # 此处仅兜底 UPSERT 过程中的类型转换异常
        raise HTTPException(status_code=400, detail=f"菜单配置更新失败: {e}") from e
    except OperationalError as e:
        # SQLite 锁等待超时 / 磁盘故障等可恢复异常：客户端可重试
        # 为什么 503 而非 500：503 Service Unavailable 语义上更准确，提示客户端稍后重试
        raise HTTPException(status_code=503, detail="数据库暂时不可用，请重试") from e
    except SQLAlchemyError as e:
        # 其他 SQLAlchemy 异常（如约束冲突）：视为内部错误，不暴露细节给客户端
        raise HTTPException(status_code=500, detail=f"数据库错误: {e}") from e
    return {"ok": True}


@router.post("/reset")
def reset_menu(request: Request) -> dict[str, Any]:
    """重置当前用户菜单为默认配置

    删除该用户在 user_menu_configs 表中的所有记录，
    下次 GET /api/menu 将返回 registry 默认值。
    """
    user_id = getattr(request.state, "user_id", _DEFAULT_USER_ID)
    manager = get_menu_manager()
    manager.reset_menu_config(user_id)
    return {"ok": True}
