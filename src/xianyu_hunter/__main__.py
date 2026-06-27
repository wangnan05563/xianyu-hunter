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
import sys
import uuid
from pathlib import Path
from typing import Any

import typer
from loguru import logger

from xianyu_hunter.domain.task import Task, TaskMode
from xianyu_hunter.domain.urls import get_base_url
from xianyu_hunter.container import Container, build_default_container
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.modules.scheduler import TaskScheduler
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
        if raw.get("status") != "running":
            continue
        # 仓库中存的 dict 还原为 Task 领域对象
        task = Task(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            keyword=raw["keyword"],
            min_price=raw.get("min_price"),
            max_price=raw.get("max_price"),
            exclude_words=raw.get("exclude_words") or [],
            region=raw.get("region"),
            mode=TaskMode(raw.get("mode", "confirm")),
            # 调度配置：从 DB 读取，与 web/startup.py 保持一致
            # 用 or 防御 NULL：迁移后的旧行可能为 None，dict.get(key, default) 在 key 存在但值为 None 时返回 None
            cron=raw.get("cron") or "*/1 * * * *",
            use_cron=bool(raw.get("use_cron") or 0),
            interval_seconds=float(raw.get("interval_seconds") or 60.0),
        )
        from xianyu_hunter.domain.task import TaskConfig

        # 装入价格策略的 min/max（来自 Task）
        if task.min_price is not None or task.max_price is not None:
            from xianyu_hunter.modules.price_strategy import PriceConfig

            container.price_strategy = type(container.price_strategy)(  # type: ignore[attr-defined]
                PriceConfig(
                    min_price=task.min_price,
                    max_price=task.max_price,
                    market_ratio=getattr(container.price_strategy, "config", None).market_ratio
                    if getattr(container.price_strategy, "config", None) is not None
                    else 0.8,
                )
            )
        worker = TaskWorker(
            task=task,
            collector=container.collector,
            dedup=container.dedup,
            price_strategy=container.price_strategy,
            evaluator=container.evaluator,
            buyer=container.buyer,
            # 调度参数从 Task 字段读取，避免 use_cron 恒为 False 的断层
            config=TaskConfig(
                use_cron=task.use_cron,
                interval_seconds=task.interval_seconds,
            ),
            repo=container.repo,
        )
        await container.scheduler.register(task, worker)
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
            await container.scheduler.start(tid)
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
            try:
                await bus_task
            except asyncio.CancelledError:
                pass

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
    port: int = typer.Option(8000, help="监听端口"),
    reload: bool = typer.Option(False, help="开发模式（自动重载）"),
    with_scheduler: bool = typer.Option(False, help="同时启动任务调度器（一键启动 Web + 搜索引擎）"),
) -> None:
    """启动 Web 控制台（FastAPI + htmx）

    加 --with-scheduler 可同时启动任务调度器，无需再单独运行 `xianyu run`。
    """
    try:
        import uvicorn
    except ImportError:
        typer.echo("✗ 缺少依赖 uvicorn，请先 pip install uvicorn[standard]", err=True)
        raise typer.Exit(1)
    import os
    if with_scheduler:
        os.environ["XH_WITH_SCHEDULER"] = "1"
        typer.echo("→ 模式: Web + 调度器（一键启动）")
    else:
        os.environ.pop("XH_WITH_SCHEDULER", None)
    from xianyu_hunter.web.app import app as web_app
    typer.echo(f"→ 启动 Web 控制台: http://{host}:{port}")
    typer.echo(f"  API 文档:        http://{host}:{port}/api/docs")
    typer.echo("  按 Ctrl+C 退出")
    uvicorn.run(web_app, host=host, port=port, reload=reload, log_level="info")


if __name__ == "__main__":
    app()
