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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from xianyu_hunter.web.middleware.auth import setup_auth_middleware
from xianyu_hunter.web.middleware.exception_handler import register_exception_handlers
from xianyu_hunter.web.middleware.request_id import setup_request_id_middleware
from xianyu_hunter.web.startup import setup_startup_hooks
from xianyu_hunter.web.routes import (
    api_about,  # 关于菜单：版本信息 + 检查更新
    api_accounts,  # 多账号管理：列表/切换/退出/会话事件（/api/auth/accounts）
    api_ai,
    api_anticrawl,
    api_auth,
    api_config,
    api_cron,
    api_db_admin,
    api_error_logs,
    api_vector_admin,
    api_evaluations,
    api_export,
    api_ai_deep,
    api_accounts_proxies,
    api_batch_refresh,
    # 智能客服模块路由：会话/消息/SSE/反馈 + 知识库 + 配置
    # 为什么集中放在此处：三路由共用 /api/chatbot 前缀，tags 区分功能域
    api_chatbot,
    api_chatbot_config,
    api_items,
    api_kb,
    api_logs,
    api_maintenance,
    api_menu,  # 菜单配置：用户级菜单可见性/排序（/api/menu）
    api_notifications,
    api_notifier,
    api_orders,
    api_prompts,
    api_stats,
    api_task_deps,
    api_task_links,
    api_tasks,
    api_templates,
    api_tunnel,
    price_dashboard,
)


def _check_db(container: Any) -> tuple[str, bool]:
    """检查数据库连通性，返回 (status_text, is_ok)

    为什么独立：healthz 中 5 个嵌套 try/except 使认知复杂度逼近阈值，
    拆分后主函数只负责组装响应，单项检查异常不会波及其他检查。
    """
    from sqlalchemy import text as sql_text
    try:
        with container.repo.engine.connect() as conn:
            conn.execute(sql_text("SELECT 1"))
        return "ok", True
    except Exception as e:
        return f"error: {e}", False


def _check_login_valid() -> bool:
    """检查闲鱼登录态（信息性：未登录不影响服务本身）"""
    try:
        from xianyu_hunter.web.services.cookie_store import CookieStore
        return CookieStore().has_valid_cookies()
    except Exception:
        return False


def _check_tasks_running(container: Any) -> int:
    """检查运行中任务数"""
    try:
        return len(container.repo.list_tasks(status="running"))
    except Exception:
        return 0


def _check_notifier(container: Any) -> str:
    """检查通知渠道配置"""
    try:
        hub = container.notifier_hub
        channels = getattr(hub, "channels", []) or []
        return "configured" if channels else "not_configured"
    except Exception:
        return "unknown"


# 常见 MIME 类型映射（确保浏览器正确解析 JS/CSS/WOFF2 等资源）
# 提取为模块级常量，避免 create_app 内嵌套局部函数访问时拉高认知复杂度（S3776）
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
    # O-12-26 PWA：manifest 必须用 application/manifest+json 才能被浏览器识别
    ".webmanifest": "application/manifest+json",
}


# OpenAPI tag 元信息：与 src/xianyu_hunter/web/routes/*.py 中 APIRouter(tags=[...]) 保持一一对应
# Swagger UI 顶部按顺序展示分组；description 支持 Markdown，可写多行
# 维护原则：新增 tag 必须在此登记，否则 Swagger UI 顶部不展示
_OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "meta",
        "description": (
            "**系统元信息**\n\n"
            "- 版本号、发布日期、Git SHA\n"
            "- 健康检查 `/healthz`（数据库/登录态/任务/浏览器/通知）\n"
            "- 检查 GitHub 新版本"
        ),
    },
    {
        "name": "auth",
        "description": (
            "**认证与登录**\n\n"
            "Token 校验、Cookie 颁发、扫码登录、浏览器 Cookie 注入。"
        ),
    },
    {
        "name": "accounts",
        "description": (
            "**多账号管理**\n\n"
            "列出所有已登录闲鱼账号、一键切换、退出登录、查询会话事件。"
        ),
    },
    {
        "name": "accounts-proxies",
        "description": (
            "**多账号 + 代理池**\n\n"
            "账号与代理的 CRUD、健康检查、轮换获取、success/fail 上报（用于权重调整）。"
        ),
    },
    {
        "name": "tasks",
        "description": (
            "**任务 CRUD 与调度**\n\n"
            "创建/编辑/删除/启停任务，配置关键词、价格区间、执行模式、调度间隔、Cron、闲鱼筛选标签，"
            "支持任务级 AI 评估阈值与价格/搜索/反检测覆盖。"
        ),
    },
    {
        "name": "task-deps",
        "description": "**任务依赖**\n\n任务间的 DAG 依赖关系（A 跑完才能跑 B）。",
    },
    {
        "name": "task-links",
        "description": "**任务链接/关联**\n\n任务间的双向关联查询与反查。",
    },
    {
        "name": "items",
        "description": "**商品数据**\n\n商品 summary 批量查询、任务商品列表、商品详情与状态变更。",
    },
    {
        "name": "evaluations",
        "description": (
            "**卖家评估**\n\n"
            "4 维评分（职业度/信用/纠纷/价格异动）、AI 多模态鉴伪、评估反馈。"
        ),
    },
    {
        "name": "orders",
        "description": "**抢单记录**\n\n订单状态（成功/失败/超时/已接管）、利润计算、人工接管标记。",
    },
    {
        "name": "stats",
        "description": "**统计聚合根**\n\n通用统计查询入口。",
    },
    {
        "name": "stats-overview",
        "description": "**总览统计**\n\n仪表盘 KPI 卡片聚合数据。",
    },
    {
        "name": "stats-today",
        "description": "**今日数据**\n\n今日抢单/评估/通知等关键指标。",
    },
    {
        "name": "stats-trend",
        "description": "**趋势统计**\n\n按时间维度的历史趋势查询。",
    },
    {
        "name": "eval-funnel",
        "description": "**评估漏斗**\n\n搜索→评估→通过的转化漏斗。",
    },
    {
        "name": "business-kpi",
        "description": "**业务 KPI**\n\n业务核心指标（GMV、成功率、平均捡漏金额等）。",
    },
    {
        "name": "price-dashboard",
        "description": "**价格看板**\n\n按类目横向对比中位价/最低价/最高价。",
    },
    {
        "name": "price-trend",
        "description": "**价格趋势**\n\n商品价格历史走势。",
    },
    {
        "name": "prices",
        "description": "**价格直方图**\n\n仪表盘价格分布。",
    },
    {
        "name": "seller-trend",
        "description": "**卖家趋势**\n\n卖家评分/上架量的时间变化。",
    },
    {
        "name": "timeline",
        "description": "**事件时间线**\n\n21 种系统事件类型，跨模块统一时间线。",
    },
    {
        "name": "logs",
        "description": "**实时日志**\n\nSSE 推送的实时日志（按级别过滤）。",
    },
    {
        "name": "error-logs",
        "description": "**错误日志**\n\n未处理异常捕获与 AI 诊断上下文导出。",
    },
    {
        "name": "notifications",
        "description": "**通知中心**\n\n系统通知列表/已读管理/批量操作（订单/登录/系统/配置/任务 5 大类）。",
    },
    {
        "name": "notifier",
        "description": (
            "**通知渠道**\n\n"
            "7+ 渠道 CRUD 与启用：Server酱 / PushPlus / Bark / 钉钉 / 企业微信 / Telegram / ntfy / 通用 Webhook。"
        ),
    },
    {
        "name": "config",
        "description": "**配置管理**\n\n全局配置 CRUD、YAML 预览/保存/备份/恢复/分享。",
    },
    {
        "name": "preferences",
        "description": "**用户偏好**\n\n按用户隔离的偏好持久化（侧边栏状态、列设置等）。",
    },
    {
        "name": "prompts",
        "description": "**Prompt 编辑器**\n\nAI 提示词在线编辑与版本管理。",
    },
    {
        "name": "cron",
        "description": "**Cron 表达式**\n\nCron 校验与示例。",
    },
    {
        "name": "templates",
        "description": "**模板市场**\n\n预置任务模板与用户私有模板。",
    },
    {
        "name": "export",
        "description": "**数据导出**\n\n商品/评估/订单/事件 4 类数据集 CSV 导出。",
    },
    {
        "name": "maintenance",
        "description": "**系统清理**\n\n缓存/数据库/日志清理，SQLite VACUUM。",
    },
    {
        "name": "db-admin",
        "description": "**数据库维护**\n\n11 张业务表在线 CRUD + 自定义 SQL 查询。",
    },
    {
        "name": "vector-admin",
        "description": "**向量数据库维护**\n\nChromaDB 快照、清理、重建监控。",
    },
    {
        "name": "tunnel",
        "description": "**内网穿透**\n\n一键远程访问（cpolar/frp）。",
    },
    {
        "name": "menu",
        "description": "**菜单配置**\n\n用户级菜单可见性/排序，重置默认。",
    },
    {
        "name": "ai",
        "description": (
            "**AI 服务**\n\n"
            "OpenAI 兼容 API：自然语言建任务（`/parse-task`）、条件评估（`/evaluate-condition`）、"
            "模型配置、用量统计、预算控制、连接测试、Embedding 测试。"
        ),
    },
    {
        "name": "ai-deep",
        "description": (
            "**AI 深度多模态**\n\n"
            "商品深度分析（图片+文本）、卖家模板检测。"
        ),
    },
    {
        "name": "chatbot",
        "description": (
            "**智能客服**\n\n"
            "会话管理（增删改查/收藏/结束）、消息收发（SSE 流式）、消息反馈、撤销、转人工、会话导出。"
        ),
    },
    {
        "name": "chatbot-config",
        "description": (
            "**客服配置**\n\n"
            "RAG/Agent 配置 CRUD、FAQ 问答库、欢迎语、配置审计日志。"
        ),
    },
    {
        "name": "chatbot-kb",
        "description": (
            "**智能客服知识库**\n\n"
            "KB 重建、状态查询、版本列表与回滚。"
        ),
    },
    {
        "name": "anticrawl",
        "description": (
            "**反爬登录管理**\n\n"
            "反爬策略配置、扫码/二维码/浏览器 Cookie 注入、会话启停与健康检查、"
            "指纹伪装、QPS 控制、Cookie 分层管理。"
        ),
    },
    {
        "name": "batch-refresh",
        "description": (
            "**批量采集**\n\n"
            "定时批量刷新在售商品最新详情，支持手动触发、暂停/继续/停止、失败熔断、执行历史与统计。"
        ),
    },
    {
        "name": "qr-login",
        "description": "**二维码登录**\n\n闲鱼 App 扫码登录流程。",
    },
    {
        "name": "sse-stream",
        "description": "**SSE 流**\n\n服务端事件流（通知、事件、日志等）。",
    },
]


def _build_favicon_response(static_dir: Path) -> Response:
    """构建 favicon 响应，优先 SPA 构建产物，回退到 frontend/public 源文件

    独立为模块级函数：原为 create_app 内的局部路由函数，多重 if 分支拉高了
    create_app 的认知复杂度（S3776）；提取后路由函数仅做一行调用。
    """
    spa_favicon = static_dir / "spa" / "favicon.ico"
    if spa_favicon.is_file():
        return Response(
            content=spa_favicon.read_bytes(),
            media_type="image/x-icon",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    frontend_favicon = Path(__file__).resolve().parents[3] / "frontend" / "public" / "favicon.ico"
    if frontend_favicon.is_file():
        return Response(
            content=frontend_favicon.read_bytes(),
            media_type="image/x-icon",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    return JSONResponse({"detail": "favicon not found"}, status_code=404)


def _serve_spa_request(spa_dir: Path, full_path: str) -> Response:
    """SPA catch-all 请求处理：静态文件直接返回，其余返回注入登录浮层的 index.html

    独立为模块级函数以降低 create_app 认知复杂度（S3776）。
    """
    if full_path:
        file_path = spa_dir / full_path
        if file_path.is_file():
            ext = file_path.suffix.lower()
            media_type = _SPA_MEDIA_TYPES.get(ext, "application/octet-stream")
            # assets/ 下是带 hash 的构建产物，可长期强缓存；其余路径禁缓存以保证 index.html 实时性
            headers = (
                {"Cache-Control": "public, max-age=31536000, immutable"}
                if full_path.startswith("assets/")
                else {"Cache-Control": "no-cache"}
            )
            return Response(content=file_path.read_bytes(), media_type=media_type, headers=headers)
    index_path = spa_dir / "index.html"
    if index_path.exists():
        html = index_path.read_text(encoding="utf-8")
        # 注入登录引导浮层（在 </body> 前插入）
        html = html.replace("</body>", _SPA_LOGIN_OVERLAY + "\n</body>")
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-cache"},
        )
    return JSONResponse({"detail": "SPA 未构建，请运行 cd frontend && npm run build"}, status_code=404)


def _collect_health_checks(container: Any) -> tuple[dict[str, Any], bool]:
    """运行健康检查项，返回 (checks, db_ok)

    try/except 兜底：容器初始化异常不应让 /healthz 直接 500，而应返回带 error 字段的 503。
    """
    checks: dict[str, Any] = {}
    db_ok = False
    try:
        # 1. 数据库连通性（关键检查项，决定 HTTP 状态码）
        checks["db"], db_ok = _check_db(container)
        # 2. 闲鱼登录态（信息性：未登录不影响服务本身）
        checks["login_valid"] = _check_login_valid()
        # 3. 运行中任务数
        checks["tasks_running"] = _check_tasks_running(container)
        # 4. 浏览器实例（Web 进程 with_browser=False 时为 None，属正常）
        checks["browser"] = "running" if container.browser is not None else "not_started"
        # 5. 通知渠道配置
        checks["notifier"] = _check_notifier(container)
    except Exception as e:
        checks["error"] = str(e)
    return checks, db_ok


def create_app() -> FastAPI:
    app = FastAPI(
        title="XianyuHunter Web API",
        description=(
            "## 闲鱼猎人 Web 控制台 API\n\n"
            "闲鱼猎人（XianyuHunter）是面向闲鱼平台的自动捡漏与抢单系统，"
            "提供 Web 控制台 + 移动端 + AI 智能客服的完整能力。本文档为后端 REST API 完整参考，"
            "覆盖 40+ 功能域、300+ 端点。\n\n"
            "### 鉴权\n\n"
            "除白名单端点外，所有 API 需在请求头携带 `Authorization: Bearer <token>`，"
            "或在浏览器请求中携带 `xh_token` Cookie（前端 fetch 默认 `credentials: 'include'`）。\n\n"
            "**认证白名单**（无需鉴权）：`/api/auth/cookie`、`/api/auth/me`、`/api/auth/import-from-browser`、"
            "`/import-from-browser/status`、`/api/events/stream`、`/api/notifications`（SSE 内部白名单）、"
            "`/api/notifier/`、`/api/about`、`/api/about/check-update`、`/healthz`、`/api/docs`、`/openapi.json`、`/app/*` SPA。\n\n"
            "### 端点分组\n\n"
            "- **meta**：版本信息、健康检查、关于\n"
            "- **auth / accounts**：Token 认证、多账号管理、扫码登录\n"
            "- **tasks / task-deps / task-links**：任务 CRUD、依赖关系、链接管理\n"
            "- **items / evaluations / orders**：商品、卖家评估、抢单记录\n"
            "- **stats-\\***：聚合统计（总览/今日/趋势/价格/评估漏斗/卖家趋势）\n"
            "- **timeline / logs / error-logs / notifications**：事件流、日志、错误、通知\n"
            "- **config / preferences / prompts / cron / templates**：配置管理\n"
            "- **ai / ai-deep**：自然语言建任务、深度多模态分析\n"
            "- **chatbot / chatbot-config / chatbot-kb**：智能客服（会话/RAG/Agent/知识库/FAQ）\n"
            "- **notifier**：7+ 渠道通知配置（Server酱/PushPlus/Bark/钉钉/企微/Telegram/ntfy/Webhook）\n"
            "- **anticrawl / batch-refresh / accounts-proxies**：反爬、批量采集、代理池\n"
            "- **maintenance / db-admin / vector-admin / tunnel / export**：系统维护、数据库、向量库、内网穿透、数据导出\n"
            "- **menu**：用户级菜单可见性/排序配置\n"
            "- **sse-stream**：服务端推送（SSE 日志/事件）\n\n"
            "### 错误格式\n\n"
            "所有错误统一返回 `{\"detail\": \"...\"}` JSON 对象；401 未授权；403 越权；404 不存在；422 参数校验失败。\n\n"
            "### 版本\n\n"
            "API 版本随 `_build_info.py` 的 `__version__` 自动更新；破坏性变更会标记 `Deprecation` 标签。\n"
        ),
        version="0.3.0",
        # 禁用默认 docs，使用自定义 Swagger UI（顶部含帮助文档入口按钮）
        docs_url=None,
        redoc_url=None,
        # openapi_tags：为每个 tag 提供 description，Swagger UI 顶部分类展示
        openapi_tags=_OPENAPI_TAGS,
        # 联系信息（GitHub Issues）
        contact={"name": "GitHub Issues", "url": "https://github.com/xianyu-hunter/xianyu-hunter/issues"},
        # 开源协议
        license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        # 术语服务器（占位，便于后续扩展）
        openapi_extra={
            "x-logo": {"url": "/favicon.ico", "altText": "闲鱼猎人 Logo"},
        },
    )

    # Token 认证中间件（C-01：所有 API 端点鉴权）
    setup_auth_middleware(app)

    # 全局流水号中间件：必须在认证之后注册（LIFO 后注册的先执行）
    # 执行顺序：RequestIdMiddleware → BearerAuthMiddleware → 路由
    setup_request_id_middleware(app)

    # 全局异常处理器（兜底未捕获异常 + 统一 422/HTTPException 响应格式）
    register_exception_handlers(app)

    # 启动/关闭钩子（DB 迁移 + 调度器生命周期）
    setup_startup_hooks(app)

    # 静态资源
    # 打包模式：static 外置到 exe 同级目录（与 launcher.py、build-exe.ps1 外置策略一致）
    # 开发模式：源码目录
    from xianyu_hunter.paths import is_frozen, get_app_dir
    if is_frozen():
        static_dir = get_app_dir() / "static"
    else:
        static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 浏览器访问任何页面都会默认请求 /favicon.ico，需显式提供避免 404 噪音
    # 优先从 SPA 构建产物读取，回退到 frontend/public 源文件
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return _build_favicon_response(static_dir)

    # 噪音路径静默处理：浏览器/DevTools 自动探测或缓存残留导致的 404 噪音
    # 返回 204 No Content 即可，无需业务逻辑
    # - /.well-known/appspecific/com.chrome.devtools.json：Chrome DevTools 自动探测
    # - /@vite/client：浏览器缓存 Vite dev server HTML 后误请求生产后端
    @app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
    async def chrome_devtools_probe() -> Response:
        return Response(status_code=204)

    @app.get("/@vite/client", include_in_schema=False)
    async def vite_client() -> Response:
        return Response(status_code=204)

    # /app/docs 重定向到 FastAPI 内置的 API 文档（docs_url=/api/docs）
    # 避免被下方 SPA catch-all 捕获后返回 index.html，导致前端路由跳回首页
    @app.get("/app/docs", include_in_schema=False)
    async def redirect_app_docs() -> RedirectResponse:
        return RedirectResponse(url="/api/docs", status_code=302)

    # 自定义 Swagger UI 页面：在顶部导航栏注入「帮助文档」入口按钮
    # docs_url=None 禁用默认 docs，由本路由提供含帮助入口的增强版 Swagger UI
    @app.get("/api/docs", include_in_schema=False)
    async def custom_docs() -> HTMLResponse:
        return HTMLResponse(_SWAGGER_UI_HTML)

    # SPA 可视化配置控制台（React 构建产物）
    # 访问 /app/* 时服务 SPA，支持客户端路由
    # vite base='/app/'，构建产物资源路径为 /app/assets/*
    # 注意：不使用 StaticFiles mount，因为 Windows 上 MIME 类型识别不准确
    #       统一由 spa_index catch-all 处理，确保 JS/CSS 等资源有正确的 Content-Type
    spa_dir = static_dir / "spa"
    if spa_dir.exists():
        @app.get("/app/{full_path:path}")
        async def spa_index(full_path: str) -> Response:
            """SPA catch-all：所有 /app/* 路径，静态文件直接返回，其余返回 index.html

            未登录时在 index.html 中注入登录引导浮层，
            引导用户跳转到 /app/login 完成登录后返回 /app。
            """
            return _serve_spa_request(spa_dir, full_path)

    # 根路径重定向到新版 SPA：旧版 SSR 已下线，所有用户访问 / 时跳转到 /app/
    @app.get("/", include_in_schema=False)
    async def redirect_to_spa() -> RedirectResponse:
        return RedirectResponse(url="/app/", status_code=302)

    # 路由
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
    app.include_router(api_accounts.router)  # 多账号管理：/api/auth/accounts 列表/切换/退出
    app.include_router(api_about.router)  # 关于菜单：版本信息 + 检查更新
    app.include_router(api_anticrawl.router)  # 反爬登录管理：策略/会话/健康/Cookie 分层
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
    app.include_router(api_db_admin.router)  # 系统维护 → 数据库维护：业务表在线 CRUD
    app.include_router(api_vector_admin.router)  # 系统维护 → 向量数据库维护：ChromaDB 快照/清理/监控
    app.include_router(api_error_logs.router)  # 后台错误日志：异常捕获 + AI 诊断上下文
    app.include_router(api_batch_refresh.router)  # 批量采集调度器：定时刷新在售商品详情
    app.include_router(api_tunnel.router)  # 内网穿透：一键远程访问
    app.include_router(api_menu.router)  # 用户级菜单可见性/排序：/api/menu GET/PUT + /api/menu/reset
    # 智能客服模块路由：api_chatbot（会话/消息/SSE/反馈）、api_kb（知识库版本/重建）、api_chatbot_config（热更新配置）
    # 为什么放在最后：chatbot 为可选模块，容器构造时若依赖缺失返回 None，
    # 路由内通过 get_container().chatbot 判空返回 503，不影响主系统路由注册
    app.include_router(api_chatbot.router)
    app.include_router(api_kb.router)
    app.include_router(api_chatbot_config.router)

    @app.get("/healthz", tags=["meta"])
    def healthz() -> JSONResponse:
        """健康检查：检查数据库、登录态、任务、浏览器、通知渠道

        仅数据库故障时返回 503（Docker HEALTHCHECK 据此判定不健康）；
        其他检查项为信息性指标，不影响 HTTP 状态码。
        """
        from xianyu_hunter.web.deps import get_container
        container = get_container()
        checks, db_ok = _collect_health_checks(container)
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
            samesite="none",  # 改为 none，支持移动端跨域访问
            secure=True,      # SameSite=None 要求 Secure
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
#xh-login-overlay .xh-login-btn{display:inline-block;padding:10px 28px;background:#FF6200;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer;text-decoration:none;transition:background 0.2s}
#xh-login-overlay .xh-login-btn:hover{background:#e55a00}
#xh-login-overlay .xh-login-checking{color:#999;font-size:13px}
</style>
<div id="xh-login-overlay" style="display:none"><div class="xh-login-card"><div class="xh-login-icon">🔑</div><div class="xh-login-title">需要登录闲鱼账号</div><div class="xh-login-desc">控制台需要登录后才能使用<br>点击下方按钮前往登录页面</div><a class="xh-login-btn" href="/app/login">前往登录</a></div></div>
<script>
(function(){
  // 已在登录页时不显示浮层，避免遮挡前端登录界面
  if(window.location.pathname.indexOf('/app/login')!==-1)return;
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


# 自定义 Swagger UI 页面：在标准 Swagger UI 基础上注入顶部导航栏
# 导航栏含「帮助文档」和「返回控制台」入口，使用闲鱼品牌橙配色
_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>XianyuHunter Web - API 文档</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
<link rel="icon" href="/static/icons/icon-dashboard.svg">
<style>
  body { margin: 0; }
  /* 顶部导航栏：固定定位，不随页面滚动 */
  .xh-docs-header {
    position: fixed; top: 0; left: 0; right: 0; height: 56px;
    background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    z-index: 1000; display: flex; align-items: center; justify-content: space-between;
    padding: 0 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .xh-docs-header .xh-title { display: flex; align-items: center; gap: 10px; font-size: 16px; font-weight: 600; color: #262626; }
  .xh-docs-header .xh-logo {
    width: 32px; height: 32px; border-radius: 8px;
    background: linear-gradient(135deg, #FF6200, #FF8533);
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 700; font-size: 16px;
    box-shadow: 0 2px 8px rgba(255,98,0,0.25);
  }
  .xh-docs-header .xh-actions { display: flex; gap: 10px; align-items: center; }
  .xh-docs-header .xh-btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 16px; border-radius: 6px; font-size: 14px;
    text-decoration: none; cursor: pointer; border: none;
    transition: all 0.2s; font-weight: 500;
  }
  .xh-docs-header .xh-btn-primary { background: #FF6200; color: #fff; }
  .xh-docs-header .xh-btn-primary:hover { background: #e55a00; box-shadow: 0 2px 8px rgba(255,98,0,0.3); }
  .xh-docs-header .xh-btn-default { background: transparent; color: #595959; border: 1px solid #d9d9d9; }
  .xh-docs-header .xh-btn-default:hover { color: #FF6200; border-color: #FF6200; }
  /* Swagger UI 偏移，避免被固定导航栏遮挡 */
  .swagger-ui { margin-top: 56px; }
</style>
</head>
<body>
<div class="xh-docs-header">
  <div class="xh-title">
    <div class="xh-logo">闲</div>
    <span>闲鱼猎人 · API 文档</span>
  </div>
  <div class="xh-actions">
    <a class="xh-btn xh-btn-default" href="/app/" target="_blank">控制台</a>
    <a class="xh-btn xh-btn-primary" href="/app/about" target="_blank">📖 关于</a>
  </div>
</div>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  SwaggerUIBundle({
    url: '/openapi.json',
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis],
    layout: 'BaseLayout',
    defaultModelsExpandDepth: 2,
  });
</script>
</body>
</html>"""


# uvicorn 直接调用入口
app = create_app()
