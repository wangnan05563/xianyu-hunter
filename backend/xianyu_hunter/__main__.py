"""XianyuHunter CLI 入口

子命令：
  run [task_id]  启动调度器（不指定 task_id 则启动所有 RUNNING 任务）
  add            新增监控任务
  list           列出所有任务
  status [tid]   查看任务运行状态
  pause / resume / stop [tid]  控制单个任务
  web            启动 FastAPI Web 控制台（可选）

使用示例：
  python -m xianyu_hunter add --keyword "iPhone 13" --min 1500 --max 2500
  python -m xianyu_hunter run
  python -m xianyu_hunter list
  python -m xianyu_hunter pause t1
"""
from __future__ import annotations

import asyncio
import signal
import uuid
from contextlib import suppress

import typer

from xianyu_hunter.domain.task import Task, TaskMode
from xianyu_hunter.domain.urls import get_base_url
from xianyu_hunter.container import Container, build_default_container
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.modules.worker import TaskWorker

app = typer.Typer(help="XianyuHunter - 闲鱼自动捡漏与抢单系统")
control_app = typer.Typer(help="任务控制")
app.add_typer(control_app, name="")

# 全局容器引用（run 命令时构造，其他命令 lazy 加载）
_container: Container | None = None


def get_container() -> Container:
    """懒加载容器（子命令在主容器构造之前不会用到）"""
    global _container
    if _container is None:
        _container = build_default_container()
    return _container


async def _load_tasks_from_repo(container: Container) -> list[Task]:
    """从 DB 加载所有 RUNNING 任务并构造 Worker"""
    raw_tasks = container.repo.list_tasks()
    workers: list[TaskWorker] = []
    for raw in raw_tasks:
        # Worker 构造逻辑统一委托给 container.build_worker_from_raw_task
        # 避免与 web/startup.py 的代码重复，保持任务级配置覆盖逻辑一致
        worker = container.build_worker_from_raw_task(raw)
        if worker is None:
            continue
        await container.scheduler.register(worker.task, worker)
        workers.append(worker)
    return [w.task for w in workers]


@app.command()
def add(
    keyword: str = typer.Option(..., help="搜索关键词"),
    name: str = typer.Option("", help="任务名称（默认 = keyword）"),
    min_price: float = typer.Option(None, help="价格下限"),
    max_price: float = typer.Option(None, help="价格上限"),
    mode: str = typer.Option("confirm", help="执行模式: auto/semi_auto/confirm/notify"),
    task_id: str = typer.Option("", help="任务 ID（默认自动生成）"),
) -> None:
    """新增监控任务"""
    container = get_container()
    tid = task_id or f"t{uuid.uuid4().hex[:8]}"
    task = Task(
        id=tid,
        name=name or keyword,
        keyword=keyword,
        min_price=min_price,
        max_price=max_price,
        mode=TaskMode(mode),
    )
    container.repo.upsert_task({
        "id": task.id,
        "name": task.name,
        "keyword": task.keyword,
        "min_price": task.min_price,
        "max_price": task.max_price,
        "mode": task.mode.value,
        "status": "running",
    })
    typer.echo(f"✓ 已新增任务 [{task.id}] {task.name}（{task.keyword}）")
    typer.echo(f"  模式: {task.mode.value}  价格: {min_price} ~ {max_price}")


@app.command(name="list")
def list_tasks() -> None:
    """列出所有任务"""
    container = get_container()
    tasks = container.repo.list_tasks()
    if not tasks:
        typer.echo("(无任务，请用 `xianyu add` 新增)")
        return
    typer.echo(f"{'ID':<14} {'状态':<10} {'关键词':<20} {'价格':<14} {'模式':<10}")
    typer.echo("-" * 70)
    for t in tasks:
        price_str = f"{t.get('min_price') or '?'} ~ {t.get('max_price') or '?'}"
        typer.echo(
            f"{t['id']:<14} {t.get('status', '?'):<10} {t.get('keyword', '?'):<20} "
            f"{price_str:<14} {t.get('mode', '?'):<10}"
        )


@app.command()
def status(task_id: str = typer.Argument("", help="任务 ID（不传则显示全部）")) -> None:
    """查看任务状态"""
    container = get_container()
    if task_id:
        s = container.scheduler.get_status(task_id)
        running = container.scheduler.is_running(task_id)
        typer.echo(f"任务 {task_id}: 状态={s.value}  运行中={running}")
    else:
        for t in container.scheduler.list_tasks():
            running = container.scheduler.is_running(t.id)
            typer.echo(f"  [{t.id}] {t.name}  状态={t.status.value}  运行中={running}")


@app.command()
def login(timeout: int = typer.Option(180, help="扫码登录超时秒数")) -> None:
    """打开浏览器扫码登录闲鱼（首次使用必跑）

    流程：
    1. 启动 Chromium（非无头模式，需要 GUI 桌面）
    2. 导航到闲鱼登录页
    3. 等待用户扫码（手机闲鱼 App）
    4. 检测到登录态 Cookie 后视为登录成功
    5. 关闭浏览器，登录态持久化到 data/browser_data/
    """
    from xianyu_hunter.infra.browser import BrowserManager
    cfg = get_config()
    browser = BrowserManager(
        user_data_dir=cfg.browser.user_data_dir,
        headless=False,  # 必须可弹窗
        user_agent=cfg.browser.user_agent,
        use_cdp=True,  # CDP 模式：连接系统 Edge，指纹最真实
        proxy_server=cfg.browser.proxy_server,
    )

    async def _login() -> None:
        await browser.start()
        page = await browser.new_page()
        try:
            typer.echo(f"→ 打开闲鱼登录页（{timeout}s 内扫码）...")
            await page.goto(f"{get_base_url()}/", wait_until="domcontentloaded")
            import time
            start = time.monotonic()
            while time.monotonic() - start < timeout:
                cookies = await browser._context.cookies()  # type: ignore[union-attr]
                cookie_names = {c["name"] for c in cookies}
                if "_m_h5_tk" in cookie_names or "unb" in cookie_names or "sgcookie" in cookie_names:
                    typer.echo("✓ 登录成功（Cookie 已持久化）")
                    return
                await asyncio.sleep(2)
            typer.echo(f"✗ 登录超时（{timeout}s 内未检测到登录态）")
            raise typer.Exit(1)
        finally:
            await browser.close()

    try:
        asyncio.run(_login())
    except KeyboardInterrupt:
        typer.echo("\n已中断")


@app.command()
def run(
    task_id: str = typer.Argument("", help="任务 ID（不传则启动所有 RUNNING 任务）"),
) -> None:
    """启动调度器（前台阻塞，按 Ctrl+C 优雅退出）"""
    container = get_container()

    async def _run() -> None:
        # 从 DB 加载任务并注册到调度器（register 现在是 async）
        await _load_tasks_from_repo(container)

        if task_id:
            target_ids = [task_id]
        else:
            target_ids = [t.id for t in container.scheduler.list_tasks()]

        if not target_ids:
            typer.echo("(无任务可启动，请先 `xianyu add`)")
            return

        # 启动 EventBus 消费循环（Notifer 派发用）
        bus_task = asyncio.create_task(container.event_bus.run_forever())
        # 启动所有目标 worker
        for tid in target_ids:
            container.scheduler.start(tid)
        typer.echo(f"已启动 {len(target_ids)} 个任务: {target_ids}")
        typer.echo("按 Ctrl+C 退出")

        # 等待 stop 信号
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:  # Windows
                pass

        try:
            await stop.wait()
        finally:
            typer.echo("正在停止...")
            await container.scheduler.stop_all()
            container.event_bus.stop()
            bus_task.cancel()
            # shutdown 中 await 已取消的子任务，使用 suppress 避免 CancelledError 中断 cleanup
            with suppress(asyncio.CancelledError):
                await bus_task

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        typer.echo("\n收到退出信号")


# 任务控制子命令
@control_app.command()
def pause(task_id: str = typer.Argument(...)) -> None:
    """暂停任务"""
    asyncio.run(get_container().scheduler.pause(task_id))
    typer.echo(f"已暂停 {task_id}")


@control_app.command()
def resume(task_id: str = typer.Argument(...)) -> None:
    """恢复任务"""
    asyncio.run(get_container().scheduler.resume(task_id))
    typer.echo(f"已恢复 {task_id}")


@control_app.command()
def stop(task_id: str = typer.Argument(...)) -> None:
    """停止任务"""
    asyncio.run(get_container().scheduler.stop(task_id))
    typer.echo(f"已停止 {task_id}")


@app.command()
def config_show() -> None:
    """显示当前加载的配置（已脱敏）"""
    cfg = get_config()
    import json

    out = {
        "server": cfg.server.model_dump(),
        "browser": {k: v for k, v in cfg.browser.model_dump().items() if k != "user_agent"},
        "antidetect": cfg.antidetect.model_dump(),
        "waf": cfg.waf.model_dump(),
        "notifier": cfg.notifier.model_dump(),
        "eval": cfg.eval.model_dump(),
    }
    typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", help="监听地址"),
    port: int = typer.Option(8001, help="监听端口"),
    reload: bool = typer.Option(False, help="开发模式（自动重载）"),
    # 默认启用调度器：实时搜索/批量采集/自动抢单等核心功能都依赖浏览器实例
    # 使用 --no-with-scheduler 可在纯 Web 模式下启动（仅查看数据，不采集）
    with_scheduler: bool = typer.Option(
        True,
        "--with-scheduler/--no-with-scheduler",
        help="同时启动任务调度器与浏览器实例（默认启用，使用 --no-with-scheduler 关闭）",
    ),
    workers: int = typer.Option(
        1,
        "--workers",
        help="uvicorn worker 进程数（多核部署建议设为 CPU 核数，提升吞吐；与 --reload 互斥）",
    ),
) -> None:
    """启动 Web 控制台（FastAPI + htmx）

    默认以调度器模式启动（Web + 浏览器 + 任务引擎同进程），
    加 --no-with-scheduler 可降级为纯 Web 模式（仅查看数据，不采集）。
    """
    try:
        import uvicorn
    except ImportError:
        typer.echo("✗ 缺少依赖 uvicorn，请先 pip install uvicorn[standard]", err=True)
        raise typer.Exit(1)
    import os
    if with_scheduler:
        os.environ["XH_WITH_SCHEDULER"] = "1"
        typer.echo("→ 模式: Web + 调度器（默认，含浏览器实例与任务引擎）")
    else:
        os.environ.pop("XH_WITH_SCHEDULER", None)
        typer.echo("→ 模式: Web only（纯 Web，实时搜索/批量采集/自动抢单不可用）")
    from xianyu_hunter.web.app import app as web_app
    # 同步端口到环境变量：内网穿透模块通过 XH_WEB_PORT 感知命令行 --port
    os.environ["XH_WEB_PORT"] = str(port)
    typer.echo(f"→ 启动 Web 控制台: http://{host}:{port}/xianyu")
    typer.echo(f"  API 文档:        http://{host}:{port}/api/docs")
    typer.echo("  按 Ctrl+C 退出")
    # P1-4：多 worker 部署提升吞吐（已实测单 worker 51→多 worker 80 req/s）。
    # uvicorn 要求 reload 与 workers 互斥，reload 模式强制单 worker（开发热重载不需要多进程）。
    # 多 worker + 调度器（with_scheduler）会让每个 worker 各起一个浏览器/调度器实例，
    # 生产建议：纯 Web 多 worker（--no-with-scheduler）配合独立调度进程，或仅单 worker 带调度器。
    if reload and workers > 1:
        typer.echo("⚠ --reload 与 --workers 互斥，已强制 workers=1", err=True)
        workers = 1
    uvicorn.run(web_app, host=host, port=port, reload=reload, workers=workers, log_level="info")


if __name__ == "__main__":
    app()
