"""FastAPI 应用入口

用法：
    uvicorn xianyu_hunter.web.app:app --reload --port 8000
    或：
    python -m xianyu_hunter web --port 8000
    一键启动（Web + 调度器）：
    python -m xianyu_hunter web --with-scheduler
"""
from __future__ import annotations

import hmac
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from xianyu_hunter.web.middleware.auth import setup_auth_middleware
from xianyu_hunter.web.middleware.exception_handler import register_exception_handlers
from xianyu_hunter.web.startup import setup_startup_hooks
from xianyu_hunter.web.routes import (
    api_ai,
    api_auth,
    api_config,
    api_cron,
    api_evaluations,
    api_export,
    api_ai_deep,
    api_accounts_proxies,
    api_items,
    api_logs,
    api_maintenance,
    api_notifications,
    api_notifier,
    api_orders,
    api_prompts,
    api_stats,
    api_task_deps,
    api_task_links,
    api_tasks,
    api_templates,
    pages,
    price_dashboard,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="XianyuHunter Web",
        description="闲鱼自动捡漏与抢单系统 - Web 控制台",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    # Token 认证中间件（C-01：所有 API 端点鉴权）
    setup_auth_middleware(app)

    # 全局异常处理器（兜底未捕获异常 + 统一 422/HTTPException 响应格式）
    register_exception_handlers(app)

    # 启动/关闭钩子（DB 迁移 + 调度器生命周期）
    setup_startup_hooks(app)

    # 静态资源
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # SPA 可视化配置控制台（React 构建产物）
    # 访问 /app/* 时服务 SPA，支持客户端路由
    # vite base='/app/'，构建产物资源路径为 /app/assets/*
    # 注意：不使用 StaticFiles mount，因为 Windows 上 MIME 类型识别不准确
    #       统一由 spa_index catch-all 处理，确保 JS/CSS 等资源有正确的 Content-Type
    spa_dir = static_dir / "spa"
    if spa_dir.exists():
        # 常见 MIME 类型映射（确保浏览器正确解析 JS/CSS/WOFF2 等资源）
        _SPA_MEDIA_TYPES = {
            ".js": "application/javascript",
            ".css": "text/css",
            ".html": "text/html; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".json": "application/json",
            ".map": "application/json",
        }

        @app.get("/app/{full_path:path}")
        async def spa_index(full_path: str) -> Response:
            """SPA catch-all：所有 /app/* 路径，静态文件直接返回，其余返回 index.html

            未登录时在 index.html 中注入登录引导浮层（SPA 本身无登录功能），
            引导用户跳转到 /dashboard 完成登录后返回 /app。
            """
            if full_path:
                file_path = spa_dir / full_path
                if file_path.is_file():
                    ext = file_path.suffix.lower()
                    media_type = _SPA_MEDIA_TYPES.get(ext, "application/octet-stream")
                    headers = {"Cache-Control": "public, max-age=31536000, immutable"} if full_path.startswith("assets/") else {"Cache-Control": "no-cache"}
                    return Response(content=file_path.read_bytes(), media_type=media_type, headers=headers)
            index_path = spa_dir / "index.html"
            if index_path.exists():
                html = index_path.read_text(encoding="utf-8")
                # 注入登录引导浮层（在 </body> 前插入）
                login_overlay = _SPA_LOGIN_OVERLAY
                html = html.replace("</body>", login_overlay + "\n</body>")
                return Response(
                    content=html,
                    media_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "no-cache"},
                )
            return JSONResponse({"detail": "SPA 未构建，请运行 cd frontend && npm run build"}, status_code=404)

    # 路由
    app.include_router(pages.router)
    app.include_router(api_tasks.router)
    app.include_router(api_task_deps.router)  # F-16：任务依赖关系
    app.include_router(api_task_links.router)
    # api_task_links 暴露两个 APIRouter：主路由挂在 /api/tasks，反查路由挂在 /api/tasks/links
    app.include_router(api_task_links._links_lookup)
    app.include_router(api_config.router)
    app.include_router(api_stats.router)
    app.include_router(api_logs.router)
    app.include_router(api_orders.router)
    app.include_router(api_evaluations.router)
    app.include_router(api_auth.router)
    app.include_router(api_notifications.router)
    app.include_router(api_items.router)  # P3-UX-02：商品 summary 批量接口（抢单记录列表）
    app.include_router(api_ai.router)  # F-01：AI 自然语言建任务（OpenAI 兼容 + 规则 fallback）
    app.include_router(api_ai_deep.router)  # P1-4：AI 深度多模态分析增强
    app.include_router(api_accounts_proxies.router)  # P1-2：多账号轮换 + 代理池
    app.include_router(api_notifier.router)  # P3-F-10：免打扰时段配置 API
    app.include_router(api_templates.router)  # F-11：模板市场（预置 + 私有模板）
    app.include_router(api_export.router)  # P1-5：数据导出（CSV）
    app.include_router(api_prompts.router)  # P1-8：Prompt 在线编辑器
    app.include_router(api_cron.router)  # P1-7：Cron 表达式校验
    app.include_router(price_dashboard.router)  # P1-6：价格行情看板增强
    app.include_router(api_maintenance.router)  # 系统维护：缓存/数据库/日志清理

    @app.get("/healthz", tags=["meta"])
    def healthz() -> JSONResponse:
        """健康检查：检查数据库、登录态、任务、浏览器、通知渠道

        仅数据库故障时返回 503（Docker HEALTHCHECK 据此判定不健康）；
        其他检查项为信息性指标，不影响 HTTP 状态码。
        """
        from sqlalchemy import text as sql_text

        checks: dict[str, Any] = {}
        db_ok = False

        try:
            from xianyu_hunter.web.deps import get_container
            container = get_container()

            # 1. 数据库连通性（关键检查项）
            try:
                with container.repo.engine.connect() as conn:
                    conn.execute(sql_text("SELECT 1"))
                checks["db"] = "ok"
                db_ok = True
            except Exception as e:
                checks["db"] = f"error: {e}"

            # 2. 闲鱼登录态（信息性：未登录不影响服务本身）
            try:
                from xianyu_hunter.web.services.cookie_store import CookieStore
                checks["login_valid"] = CookieStore().has_valid_cookies()
            except Exception:
                checks["login_valid"] = False

            # 3. 运行中任务数
            try:
                checks["tasks_running"] = len(container.repo.list_tasks(status="running"))
            except Exception:
                checks["tasks_running"] = 0

            # 4. 浏览器实例（Web 进程 with_browser=False 时为 None，属正常）
            checks["browser"] = "running" if container.browser is not None else "not_started"

            # 5. 通知渠道配置
            try:
                hub = container.notifier_hub
                channels = getattr(hub, "channels", []) or []
                checks["notifier"] = "configured" if channels else "not_configured"
            except Exception:
                checks["notifier"] = "unknown"

        except Exception as e:
            checks["error"] = str(e)

        checks["status"] = "ok" if db_ok else "unhealthy"
        return JSONResponse(
            status_code=200 if db_ok else 503,
            content=checks,
        )

    @app.post("/api/auth/verify", tags=["auth"])
    def verify_token(token: str):
        """验证 Bearer Token 并设置 cookie

        前端首次访问时调用此端点，成功后浏览器自动携带 cookie。
        """
        from xianyu_hunter.config import get_settings

        expected = get_settings().web_token
        # 使用恒定时间比较防止时序攻击，与中间件保持一致
        if not hmac.compare_digest(token.encode(), expected.encode()):
            # 401 响应格式与中间件统一为 {"detail": ...}，便于前端解析
            return JSONResponse(status_code=401, content={"detail": "invalid token"})
        resp = JSONResponse(content={"ok": True})
        resp.set_cookie(
            key="xh_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30,  # 30 天
        )
        return resp

    return app


# SPA 登录引导浮层（未登录时注入到 index.html）
# 独立为模块级常量，避免每次请求都重新构造字符串
_SPA_LOGIN_OVERLAY = """<style>
#xh-login-overlay{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px)}
#xh-login-overlay .xh-login-card{background:#fff;border-radius:12px;padding:32px 40px;max-width:380px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.2)}
#xh-login-overlay .xh-login-icon{font-size:48px;margin-bottom:12px}
#xh-login-overlay .xh-login-title{font-size:18px;font-weight:600;margin-bottom:8px;color:#1a1a1a}
#xh-login-overlay .xh-login-desc{font-size:13px;color:#666;margin-bottom:20px;line-height:1.6}
#xh-login-overlay .xh-login-btn{display:inline-block;padding:10px 28px;background:#1677ff;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer;text-decoration:none;transition:background 0.2s}
#xh-login-overlay .xh-login-btn:hover{background:#0958d9}
#xh-login-overlay .xh-login-checking{color:#999;font-size:13px}
</style>
<div id="xh-login-overlay" style="display:none"><div class="xh-login-card"><div class="xh-login-icon">🔑</div><div class="xh-login-title">需要登录闲鱼账号</div><div class="xh-login-desc">SPA 控制台需要登录后才能使用<br>点击下方按钮前往登录页面</div><a class="xh-login-btn" href="/dashboard?redirect=/app/">前往登录</a></div></div>
<script>
(function(){
  var overlay=document.getElementById('xh-login-overlay');
  if(!overlay)return;
  // 检查登录状态：/api/auth/me 在白名单中，无需 token 即可调用
  fetch('/api/auth/me',{credentials:'include'}).then(function(r){return r.json()}).then(function(data){
    if(!data||!data.logged_in){
      overlay.style.display='flex';
      document.body.style.overflow='hidden';
    }
  }).catch(function(){
    // 请求失败（如 401）也显示登录引导
    overlay.style.display='flex';
    document.body.style.overflow='hidden';
  });
})();
</script>"""


# uvicorn 直接调用入口
app = create_app()
