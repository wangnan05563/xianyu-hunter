"""认证信息 API - 路由注册入口（聚合子模块）

本模块仅负责从子模块导入 router 并统一 re-export，
不再包含任何业务逻辑实现。

子模块分工：
- auth_query.py      → 用户信息查询（/me, /me/refresh, /verify-session）
- unified_login.py   → 统一登录 API（/login, /login/status, /login/cancel）【推荐】
- browser_login.py   → Playwright 浏览器登录（/browser-login/*）【保留兼容旧版前端】
- cookie_inject.py   → 手动 Cookie 注入（/cookie/*）
- browser_import.py  → 从系统浏览器导入 Cookie（/import-from-browser/*）

共享工具：
- auth_helpers.py    → make_auth_response() 等
"""
from __future__ import annotations

from fastapi import APIRouter

from xianyu_hunter.web.routes.auth_query import router as auth_query_router
from xianyu_hunter.web.routes.unified_login import router as unified_login_router
from xianyu_hunter.web.routes.browser_login import router as browser_login_router
from xianyu_hunter.web.routes.cookie_inject import router as cookie_inject_router
from xianyu_hunter.web.routes.browser_import import router as browser_import_router

# 聚合所有子模块路由（保持原有 URL 路径不变）
router = APIRouter(prefix="/api/auth", tags=["auth"])
router.include_router(auth_query_router)
router.include_router(unified_login_router)
router.include_router(browser_login_router)
router.include_router(cookie_inject_router)
router.include_router(browser_import_router)
