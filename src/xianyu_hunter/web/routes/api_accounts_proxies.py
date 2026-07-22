"""P1-2 多账号轮换 + 代理池 API

端点：
- 账号管理：
  - GET    /api/accounts           列出所有账号
  - POST   /api/accounts           添加账号
  - GET    /api/accounts/{id}      获取账号详情
  - PUT    /api/accounts/{id}      更新账号
  - DELETE /api/accounts/{id}      删除账号
  - POST   /api/accounts/acquire   获取可用账号（轮换调度）
  - POST   /api/accounts/{id}/report-success  报告成功
  - POST   /api/accounts/{id}/report-fail     报告失败
  - GET    /api/accounts/stats     账号池统计

- 代理管理：
  - GET    /api/proxies            列出所有代理
  - POST   /api/proxies            添加代理
  - GET    /api/proxies/{id}       获取代理详情
  - PUT    /api/proxies/{id}       更新代理
  - DELETE /api/proxies/{id}       删除代理
  - POST   /api/proxies/acquire    获取可用代理（轮换调度）
  - POST   /api/proxies/{id}/report-success  报告成功
  - POST   /api/proxies/{id}/report-fail     报告失败
  - POST   /api/proxies/{id}/check 健康检查
  - POST   /api/proxies/check-all  批量健康检查
  - GET    /api/proxies/stats      代理池统计
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from xianyu_hunter.container import Container
from xianyu_hunter.modules.account_rotator import AccountRotator
from xianyu_hunter.modules.proxy_pool import ProxyPool
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api", tags=["accounts-proxies"])


# ============== 请求模型 ==============
class AccountCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="账号别名（唯一）")
    nickname: str | None = Field(None, max_length=50, description="闲鱼昵称")
    cookies: list[dict] | None = Field(None, description="Cookie 列表")
    note: str | None = Field(None, max_length=200)


class AccountUpdateBody(BaseModel):
    nickname: str | None = None
    cookies: list[dict] | None = None
    status: str | None = Field(None, description="active/cooldown/disabled")
    note: str | None = None


class AccountAcquireBody(BaseModel):
    preferred_name: str | None = Field(None, description="优先使用的账号名")


class AccountReportFailBody(BaseModel):
    cooldown_sec: int | None = Field(None, ge=1, le=86400, description="冷却时间（秒）")


class ProxyCreateBody(BaseModel):
    url: str = Field(..., description="代理 URL，如 http://user:pass@host:port")
    note: str | None = Field(None, max_length=200)


class ProxyUpdateBody(BaseModel):
    url: str | None = None
    status: str | None = Field(None, description="active/disabled")
    note: str | None = None


# ============== 工具函数 ==============
def _get_rotator(container: Container) -> AccountRotator:
    """获取 AccountRotator 实例（惰性创建 + 热更新）

    从 YAML 配置 account_rotator 节点读取冷却时间与失败阈值，
    替代原 AccountRotator 默认参数（DEFAULT_COOLDOWN_SEC / DEFAULT_FAIL_THRESHOLD）。

    热更新策略：已缓存实例每次调用时同步最新 YAML 配置到 _cooldown_sec / _fail_threshold，
    让用户在前端修改后立即生效（report_fail 调用时读取最新值），无需重启服务。
    """
    from xianyu_hunter.infra.yaml_config import get_config
    cfg = get_config().account_rotator
    if not hasattr(container, "_account_rotator") or container._account_rotator is None:
        container._account_rotator = AccountRotator(
            container.repo.engine,
            cooldown_sec=cfg.cooldown_sec,
            fail_threshold=cfg.fail_threshold,
        )
    else:
        # 热更新：同步最新 YAML 配置到已缓存实例
        container._account_rotator._cooldown_sec = cfg.cooldown_sec
        container._account_rotator._fail_threshold = cfg.fail_threshold
    return container._account_rotator


def _get_proxy_pool(container: Container) -> ProxyPool:
    """获取 ProxyPool 实例（惰性创建）"""
    if not hasattr(container, "_proxy_pool") or container._proxy_pool is None:
        container._proxy_pool = ProxyPool(container.repo.engine)
    return container._proxy_pool


# ============== 账号管理端点 ==============
@router.get("/accounts")
def list_accounts(
    status: str | None = None,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出所有账号"""
    rotator = _get_rotator(container)
    accounts = rotator.list_accounts(status=status)
    # 隐藏 cookies 字段（敏感信息）
    for a in accounts:
        has_cookies = bool(a.get("cookies"))
        a.pop("cookies", None)
        a["has_cookies"] = has_cookies
    return {"accounts": accounts, "count": len(accounts)}


@router.get("/accounts/stats")
def account_stats(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """账号池统计"""
    rotator = _get_rotator(container)
    return rotator.get_stats()


@router.post("/accounts")
def create_account(
    body: AccountCreateBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """添加新账号"""
    rotator = _get_rotator(container)
    try:
        account = rotator.add_account(
            name=body.name, nickname=body.nickname,
            cookies=body.cookies, note=body.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    has_cookies = bool(account.get("cookies"))
    account.pop("cookies", None)
    account["has_cookies"] = has_cookies
    return account


@router.get("/accounts/{account_id}")
def get_account(
    account_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """获取账号详情"""
    rotator = _get_rotator(container)
    account = rotator.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail=f"账号 {account_id} 不存在")
    has_cookies = bool(account.get("cookies"))
    account.pop("cookies", None)
    account["has_cookies"] = has_cookies
    return account


@router.put("/accounts/{account_id}")
def update_account(
    account_id: int,
    body: AccountUpdateBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """更新账号"""
    rotator = _get_rotator(container)
    if not rotator.get_account(account_id):
        raise HTTPException(status_code=404, detail=f"账号 {account_id} 不存在")
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="无更新字段")
    account = rotator.update_account(account_id, **fields)
    has_cookies = bool(account.get("cookies"))
    account.pop("cookies", None)
    account["has_cookies"] = has_cookies
    return account


@router.delete("/accounts/{account_id}")
def delete_account(
    account_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除账号"""
    rotator = _get_rotator(container)
    if not rotator.delete_account(account_id):
        raise HTTPException(status_code=404, detail=f"账号 {account_id} 不存在")
    return {"ok": True, "deleted": account_id}


@router.post("/accounts/acquire")
def acquire_account(
    body: AccountAcquireBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """获取可用账号（轮换调度核心）

    返回一个 active 账号，自动更新 last_used_at 和 use_count。
    无可用账号时返回 404。
    """
    rotator = _get_rotator(container)
    account = rotator.acquire(preferred_name=body.preferred_name)
    if not account:
        raise HTTPException(status_code=404, detail="无可用账号（全部冷却/禁用）")
    has_cookies = bool(account.get("cookies"))
    account.pop("cookies", None)
    account["has_cookies"] = has_cookies
    return account


@router.post("/accounts/{account_id}/report-success")
def report_account_success(
    account_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """报告账号使用成功（重置失败计数）"""
    rotator = _get_rotator(container)
    if not rotator.get_account(account_id):
        raise HTTPException(status_code=404, detail=f"账号 {account_id} 不存在")
    rotator.report_success(account_id)
    return {"ok": True}


@router.post("/accounts/{account_id}/report-fail")
def report_account_fail(
    account_id: int,
    body: AccountReportFailBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """报告账号使用失败（累加失败计数，可能触发冷却/禁用）"""
    rotator = _get_rotator(container)
    if not rotator.get_account(account_id):
        raise HTTPException(status_code=404, detail=f"账号 {account_id} 不存在")
    account = rotator.report_fail(account_id, cooldown_sec=body.cooldown_sec)
    has_cookies = bool(account.get("cookies"))
    account.pop("cookies", None)
    account["has_cookies"] = has_cookies
    return account


# ============== 代理管理端点 ==============
@router.get("/proxies")
def list_proxies(
    status: str | None = None,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出所有代理"""
    pool = _get_proxy_pool(container)
    proxies = pool.list_proxies(status=status)
    return {"proxies": proxies, "count": len(proxies)}


@router.get("/proxies/stats")
def proxy_stats(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """代理池统计"""
    pool = _get_proxy_pool(container)
    return pool.get_stats()


@router.post("/proxies")
def create_proxy(
    body: ProxyCreateBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """添加新代理"""
    pool = _get_proxy_pool(container)
    try:
        proxy = pool.add_proxy(url=body.url, note=body.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return proxy


@router.get("/proxies/{proxy_id}")
def get_proxy(
    proxy_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """获取代理详情"""
    pool = _get_proxy_pool(container)
    proxy = pool.get_proxy(proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail=f"代理 {proxy_id} 不存在")
    return proxy


@router.put("/proxies/{proxy_id}")
def update_proxy(
    proxy_id: int,
    body: ProxyUpdateBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """更新代理"""
    pool = _get_proxy_pool(container)
    if not pool.get_proxy(proxy_id):
        raise HTTPException(status_code=404, detail=f"代理 {proxy_id} 不存在")
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="无更新字段")
    return pool.update_proxy(proxy_id, **fields)


@router.delete("/proxies/{proxy_id}")
def delete_proxy(
    proxy_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除代理"""
    pool = _get_proxy_pool(container)
    if not pool.delete_proxy(proxy_id):
        raise HTTPException(status_code=404, detail=f"代理 {proxy_id} 不存在")
    return {"ok": True, "deleted": proxy_id}


@router.post("/proxies/acquire")
def acquire_proxy(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """获取可用代理（轮换调度核心）

    返回一个 active 代理，自动更新 last_used_at 和 use_count。
    无可用代理时返回 404。
    """
    pool = _get_proxy_pool(container)
    proxy = pool.acquire()
    if not proxy:
        raise HTTPException(status_code=404, detail="无可用代理")
    return proxy


@router.post("/proxies/{proxy_id}/report-success")
def report_proxy_success(
    proxy_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """报告代理使用成功"""
    pool = _get_proxy_pool(container)
    if not pool.get_proxy(proxy_id):
        raise HTTPException(status_code=404, detail=f"代理 {proxy_id} 不存在")
    pool.report_success(proxy_id)
    return {"ok": True}


@router.post("/proxies/{proxy_id}/report-fail")
def report_proxy_fail(
    proxy_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """报告代理使用失败"""
    pool = _get_proxy_pool(container)
    if not pool.get_proxy(proxy_id):
        raise HTTPException(status_code=404, detail=f"代理 {proxy_id} 不存在")
    return pool.report_fail(proxy_id)


@router.post("/proxies/{proxy_id}/check")
def check_proxy(
    proxy_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """健康检查单个代理"""
    pool = _get_proxy_pool(container)
    if not pool.get_proxy(proxy_id):
        raise HTTPException(status_code=404, detail=f"代理 {proxy_id} 不存在")
    try:
        return pool.check_proxy(proxy_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/proxies/check-all")
def check_all_proxies(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量健康检查所有 active 代理"""
    pool = _get_proxy_pool(container)
    results = pool.check_all()
    return {"results": results, "count": len(results)}
