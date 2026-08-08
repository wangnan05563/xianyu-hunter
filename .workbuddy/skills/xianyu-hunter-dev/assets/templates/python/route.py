"""FastAPI 路由模板

复制后替换以下占位符：
- {ModuleName}：模块名（如 items、orders）
- {ModuleTitle}：模块中文名（如 商品、订单）
- {RepoVar}：Repository 变量名（如 items_repo）
- {ItemRow}：ORM 模型类名

设计要点：
- 路由层只做参数校验 + 调用 Repository + 返回响应，禁止业务逻辑
- 所有响应使用 Pydantic Schema 序列化，避免泄露内部字段
- 错误统一通过 HTTPException 抛出，由全局异常处理器转为 JSON
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from xianyu_hunter.infra.repository_base import get_repository
from xianyu_hunter.web.deps import auth_required
from xianyu_hunter.web.request_context import get_request_id


router = APIRouter(prefix="/api/{ModuleName}", tags=["{ModuleTitle}"])


# ==================== Schemas ====================

class {ModuleTitle}Item(BaseModel):
    """{ModuleTitle}响应 Schema"""
    id: str
    name: str
    # TODO: 按业务补充字段
    created_at: str


class {ModuleTitle}ListResponse(BaseModel):
    """{ModuleTitle}列表响应"""
    items: list[{ModuleTitle}Item]
    total: int
    page: int
    page_size: int


class Create{ModuleTitle}Request(BaseModel):
    """创建{ModuleTitle}请求"""
    name: str = Field(..., min_length=1, max_length=100, description="名称")
    # TODO: 按业务补充字段


class Update{ModuleTitle}Request(BaseModel):
    """更新{ModuleTitle}请求"""
    name: str | None = Field(None, min_length=1, max_length=100)


# ==================== 路由 ====================

@router.get("", response_model={ModuleTitle}ListResponse)
async def list_{ModuleName}(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(None, description="搜索关键词"),
    _auth: None = auth_required,
) -> {ModuleTitle}ListResponse:
    """分页查询{ModuleTitle}列表
    
    为什么用 auth_required 依赖：统一鉴权入口，便于维护认证白名单
    """
    repo = get_repository()
    result = repo.list_{ModuleName}(page=page, page_size=page_size, keyword=keyword)
    return {ModuleTitle}ListResponse(
        items=[{ModuleTitle}Item(**item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/{item_id}", response_model={ModuleTitle}Item)
async def get_{ModuleName}(
    item_id: str,
    _auth: None = auth_required,
) -> {ModuleTitle}Item:
    """查询单个{ModuleTitle}"""
    repo = get_repository()
    item = repo.get_{ModuleName}(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="{ModuleTitle}不存在")
    return {ModuleTitle}Item(**item)


@router.post("", response_model={ModuleTitle}Item, status_code=201)
async def create_{ModuleName}(
    data: Create{ModuleTitle}Request,
    request: Request,
    _auth: None = auth_required,
) -> {ModuleTitle}Item:
    """创建{ModuleTitle}
    
    为什么记录 INFO 日志：创建操作是关键状态变更，需保留审计轨迹
    """
    request_id = get_request_id(request)
    repo = get_repository()
    
    item_data = data.model_dump()
    item_data["id"] = repo.generate_id()
    item = repo.create_{ModuleName}(item_data)
    
    logger.info(
        f"创建{ModuleTitle}成功 id={item['id']} request_id={request_id}"
    )
    return {ModuleTitle}Item(**item)


@router.patch("/{item_id}", response_model={ModuleTitle}Item)
async def update_{ModuleName}(
    item_id: str,
    data: Update{ModuleTitle}Request,
    _auth: None = auth_required,
) -> {ModuleTitle}Item:
    """更新{ModuleTitle}（部分更新）"""
    repo = get_repository()
    
    existing = repo.get_{ModuleName}(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="{ModuleTitle}不存在")
    
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="无更新字段")
    
    item = repo.update_{ModuleName}(item_id, update_data)
    return {ModuleTitle}Item(**item)


@router.delete("/{item_id}", status_code=204)
async def delete_{ModuleName}(
    item_id: str,
    _auth: None = auth_required,
) -> None:
    """删除{ModuleTitle}"""
    repo = get_repository()
    
    existing = repo.get_{ModuleName}(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="{ModuleTitle}不存在")
    
    repo.delete_{ModuleName}(item_id)
    logger.info(f"删除{ModuleTitle}成功 id={item_id}")
