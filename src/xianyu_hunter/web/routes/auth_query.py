"""用户信息查询 API - 登录态检测 / 用户资料

端点：
- GET  /api/auth/me              当前登录用户信息（缓存）
- GET  /api/auth/me/refresh      强制后台刷新（不等完成）
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.services.auth_manager import get_auth_manager
from xianyu_hunter.web.routes.auth_helpers import make_auth_response
from xianyu_hunter.web.services.notification_engine import scan_and_notify
from xianyu_hunter.web.services.cookie_store import get_cookie_store

router = APIRouter(tags=["auth-query"])


def _check_cookies() -> bool:
    """检查闲鱼 Cookie 是否有效（JSON 优先，SQLite 兜底）

    CookieStore 内部优先读取 JSON 文件（登录子进程立即写入），
    JSON 不可用时回退到 SQLite 检查。
    """
    return get_cookie_store().has_valid_cookies()


@router.get("/me")
def auth_me(container: Container = Depends(get_container)):
    """返回当前登录用户信息（昵称/头像/user_id）

    实现策略：复用现有 cookie 探测 + 后台 Playwright 拉取
    - 同步部分：从持久化 cookies 立即判断 has_login（基于 cookie 存在性）
    - 异步部分：触发后台拉取 userinfo（首次 / 缓存过期时）
    """
    has_cookie = _check_cookies()

    am = get_auth_manager()
    info = am.get_userinfo()

    # 同步探测有 cookie 但缓存里 logged_in=False → 触发后台刷新
    if has_cookie and not info.get("logged_in"):
        am.trigger_refresh_userinfo_async()
    # 缓存过期 → 触发后台刷新
    if has_cookie and info.get("logged_in") and (time.time() - info.get("fetched_at", 0)) > am.USERINFO_TTL:
        am.trigger_refresh_userinfo_async()

    # 构建返回结果
    if has_cookie and not info.get("logged_in"):
        result = {
            "logged_in": True,
            "user_id": info.get("user_id", ""),
            "nick": info.get("nick", ""),
            "avatar_url": info.get("avatar_url", ""),
            "fetched_at": info.get("fetched_at", 0),
            "detecting": True,
        }
    else:
        result = {
            "logged_in": has_cookie and bool(info.get("logged_in")),
            "user_id": info.get("user_id", ""),
            "nick": info.get("nick", ""),
            "avatar_url": info.get("avatar_url", ""),
            "fetched_at": info.get("fetched_at", 0),
        }

    # 检测登录态掉线 → 生成业务通知（失败不影响主路径）
    scan_and_notify(container, auth_state=result)

    # 已登录时确保浏览器持有 xh_token 认证 cookie
    if result.get("logged_in"):
        return make_auth_response(result)

    return result


@router.post("/me/refresh")
def auth_refresh() -> dict:
    """强制后台刷新用户信息（不等完成）"""
    am = get_auth_manager()
    am.trigger_refresh_userinfo_async()
    return {"ok": True, "message": "后台刷新已触发"}


@router.post("/verify-session")
def verify_session() -> dict:
    """验证当前闲鱼登录会话是否有效

    与 /me 不同，本端点会实际访问闲鱼页面验证登录态，
    而不是仅检查 Cookie 文件是否存在。
    适用于登录后验证、登录态掉线检测等场景。
    """
    has_cookie = _check_cookies()

    if not has_cookie:
        return {"ok": False, "logged_in": False, "reason": "no_login_cookies"}

    # 尝试用 auth_helper 拉取用户信息来验证会话有效性
    # 如果 auth_helper 能成功获取用户信息，说明会话有效
    try:
        am = get_auth_manager()
        am.trigger_refresh_userinfo_async()
        return {"ok": True, "logged_in": True, "message": "会话验证已触发，请稍后查看 /api/auth/me"}
    except Exception as e:
        return {"ok": False, "logged_in": False, "reason": f"verify_error: {e}"}
