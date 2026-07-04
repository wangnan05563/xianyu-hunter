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

from xianyu_hunter.web.services.menu_manager import get_menu_manager

router = APIRouter(prefix="/api/menu", tags=["menu"])

# default 用户兜底：WEB_TOKEN 管理令牌直通场景下 request.state.user_id 可能缺失
_DEFAULT_USER_ID = "default"


class MenuItemUpdate(BaseModel):
    """单个菜单项的用户级覆盖入参"""
    key: str = Field(..., min_length=1, description="对应 registry 的 menu key")
    visible: bool = True
    sort_order: int = Field(0, ge=0, le=10000)


class MenuUpdateBody(BaseModel):
    """PUT /api/menu 请求体"""
    menus: list[MenuItemUpdate]


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
