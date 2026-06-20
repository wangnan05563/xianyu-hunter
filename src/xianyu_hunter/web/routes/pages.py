"""页面路由 - 服务端渲染 Jinja 模板"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container

router = APIRouter()

# 直接用 jinja2 原生 Environment，绕开 starlette TemplateResponse 的 LRUCache 兼容问题
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
    enable_async=False,
)


def _render(name: str, **ctx: Any) -> HTMLResponse:
    """同步渲染模板并返回 HTML 响应"""
    template = _env.get_template(name)
    return HTMLResponse(template.render(**ctx))


def _ctx(request: Request, container: Container, **extra: Any) -> dict[str, Any]:
    """构造所有页面共享的渲染上下文"""
    return {
        "request": request,
        "container": container,
        "title": extra.pop("title", "XianyuHunter"),
        "active_nav": extra.pop("active_nav", ""),
        **extra,
    }


def _page(name: str, request: Request, container: Container, **extra: Any) -> HTMLResponse:
    """统一页面渲染入口：构造 ctx + 渲染模板"""
    return _render(name, **_ctx(request, container, **extra))


# ============== 根路径 ==============
@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    onboard: str | None = Query(None),
    container: Container = Depends(get_container),
) -> Any:
    """首页：未登录/无任务 → 引导页；否则 → dashboard"""
    tasks = container.repo.list_tasks()
    has_login = _has_login_cookie(container)
    needs_onboarding = onboard == "1" or not has_login or not tasks
    if needs_onboarding:
        return _page(
            "onboarding.html",
            request,
            container,
            title="欢迎使用 XianyuHunter",
            active_nav="onboarding",
            has_login=has_login,
            task_count=len(tasks),
            step_index=4 if (has_login and tasks) else (2 if has_login else 1),
        )
    return RedirectResponse(url="/dashboard", status_code=302)


def _has_login_cookie(container: Container) -> bool:
    """检查持久化浏览器目录中是否存在登录态 Cookie"""
    from xianyu_hunter.infra.yaml_config import get_config
    import sqlite3
    import os

    cfg = get_config()
    cookie_path = Path(cfg.browser.user_data_dir) / "Default" / "Network" / "Cookies"
    if not cookie_path.exists():
        return False
    try:
        with sqlite3.connect(cookie_path) as conn:
            rows = conn.execute(
                "SELECT name FROM cookies WHERE host_key LIKE '%goofish%' OR host_key LIKE '%taobao%'"
            ).fetchall()
        names = {n for (n,) in rows}
        return bool({"_m_h5_tk", "unb", "sgcookie", "cookie2"} & names)
    except Exception:
        return False


# ============== Dashboard ==============
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    container: Container = Depends(get_container),
) -> Any:
    return _page("dashboard.html", request, container, active_nav="dashboard")


# ============== Tasks ==============
@router.get("/tasks", response_class=HTMLResponse)
def tasks_list(
    request: Request,
    container: Container = Depends(get_container),
) -> Any:
    return _page("tasks/list.html", request, container, active_nav="tasks")


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
def task_detail(
    task_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> Any:
    task = container.repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _page(
        "tasks/detail.html",
        request,
        container,
        task=task,
        active_nav="tasks",
        sub_title=f"{task_id} · {(task.get('name') or task.get('keyword') or '')[:30]}",
    )


# ============== Evaluations ==============
@router.get("/evaluations", response_class=HTMLResponse)
def evaluations(
    request: Request,
    container: Container = Depends(get_container),
) -> Any:
    return _page("evaluations.html", request, container, active_nav="evaluations")


# ============== Orders ==============
@router.get("/orders", response_class=HTMLResponse)
def orders(
    request: Request,
    container: Container = Depends(get_container),
) -> Any:
    return _page("orders.html", request, container, active_nav="orders")


# ============== Config ==============
@router.get("/config", response_class=RedirectResponse)
def config_root() -> RedirectResponse:
    return RedirectResponse(url="/config/eval", status_code=302)


_CONFIG_TABS = {
    "search": "config/search.html",
    "price": "config/price.html",
    "eval": "config/eval.html",
    "notifier": "config/notifier.html",
    "buyer": "config/buyer.html",
    "ai": "config/ai.html",
}


@router.get("/config/{tab}", response_class=HTMLResponse)
def config_tab(
    tab: str,
    request: Request,
    container: Container = Depends(get_container),
) -> Any:
    if tab not in _CONFIG_TABS:
        raise HTTPException(status_code=404, detail="未知配置 Tab")
    return _page(
        "config/base.html",
        request,
        container,
        active_nav="config",
        current_tab=tab,
        tabs=[{"key": k, "label": _tab_label(k)} for k in _CONFIG_TABS.keys()],
    )


def _tab_label(key: str) -> str:
    return {
        "search": "搜索参数",
        "price": "价格过滤",
        "eval": "评估权重",
        "notifier": "通知通道",
        "buyer": "抢单策略",
        "ai": "AI 服务",
    }.get(key, key)


# ============== Logs ==============
@router.get("/logs", response_class=HTMLResponse)
def logs(
    request: Request,
    container: Container = Depends(get_container),
) -> Any:
    return _page("logs.html", request, container, active_nav="logs")


# ============== 统一时间线 ==============
@router.get("/timeline", response_class=HTMLResponse)
def timeline(
    request: Request,
    container: Container = Depends(get_container),
) -> Any:
    """聚合订单 + 事件的统一时间线（P0-3 客户体验优化）"""
    return _page("timeline.html", request, container, active_nav="timeline")


# ============== 系统维护 ==============
@router.get("/maintenance", response_class=HTMLResponse)
def maintenance(
    request: Request,
    container: Container = Depends(get_container),
) -> Any:
    """系统维护：缓存/数据库/日志清理"""
    return _page("maintenance.html", request, container, active_nav="maintenance")

