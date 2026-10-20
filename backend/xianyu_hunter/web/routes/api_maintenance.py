"""系统维护 API - 缓存/数据库/日志清理"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from xianyu_hunter.container import Container
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.paths import (
    get_browser_data_dir,
    get_data_dir,
    get_log_dir,
    get_project_root,
)
from xianyu_hunter.web.cache import cached_ttl, invalidate_stats_cache
from xianyu_hunter.web.deps import get_container

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


class CleanupRequest(BaseModel):
    """清理请求通用模型"""
    target: str = ""  # 清理目标标识
    days: int = 30  # 保留天数（日志/数据库按时间清理时使用）
    dry_run: bool = False  # 仅预览不执行


def _data_dir() -> Path:
    """获取数据目录"""
    return get_data_dir()


def _log_dir() -> Path:
    """获取日志目录（实际位于 data/logs/）"""
    return get_log_dir()


# 扫描 __pycache__ 时排除的目录：这些目录下的缓存不应被统计/清理
# .venv: 第三方依赖缓存，清理后首次导入变慢且无意义
# node_modules / dist / build: 前端依赖与构建产物
# .git: 版本控制元数据
# data: 运行时数据（chromadb 向量库等）
_EXCLUDE_SCAN_DIRS = frozenset({
    ".venv", "node_modules", ".git", "data",
    "dist", "build", "target", ".cache", "release",
})
# 命中 __pycache__ 后不再往下走（里面只有 .pyc，没有第二层缓存目录）
_NO_DESCEND_DIRS = _EXCLUDE_SCAN_DIRS | {"__pycache__"}


def _iter_pycache_dirs(root: Path | None = None) -> list[Path]:
    """遍历项目源码目录下的 __pycache__，排除第三方依赖目录

    根目录取 `get_project_root()` 而不是 `Path('.')`（T02575）：打包版由
    快捷方式/服务拉起时 cwd 可能是任意目录（甚至 System32），以 cwd 为根
    等于「扫了一个跟本应用无关的目录」，统计与清理都会空转。绝对路径也让
    预览/确认框里显示的目录真正可核对。

    用 os.walk 而非 Path.rglob：os.walk 可在遍历时剪枝（修改 dirs[:]），
    避免 .venv（含数千个子目录）的无效遍历，将扫描时间从 30s+ 降至 <0.1s

    ⚠ 剪枝必须放在「登记命中」之后（T02575 实测修复）：旧实现先用含
    `__pycache__` 的集合过滤 dirnames，再判断 `if "__pycache__" in dirnames`——
    被过滤掉的名字不可能再命中，函数恒返回空列表，于是「Python 编译缓存」
    统计恒 0、清理恒空转，却又一次典型的「界面上有按钮、后端无动作」。
    现在拆成两个集合：_EXCLUDE_SCAN_DIRS 决定哪些目录不参与统计/清理，
    _NO_DESCEND_DIRS 决定不再递归进入哪里。
    """
    if root is None:
        root = get_project_root()
    result: list[Path] = []
    for dirpath, dirnames, _ in os.walk(str(root)):
        if "__pycache__" in dirnames:
            result.append(Path(dirpath) / "__pycache__")
        # 原地剪枝：跳过排除目录，避免递归进入 .venv / __pycache__ 等
        dirnames[:] = [d for d in dirnames if d not in _NO_DESCEND_DIRS]
    return result


# ============== 浏览器用户数据目录（FR-A-5 / T02575）==============
def _browser_data_dir() -> Path | None:
    """解析真实浏览器用户数据目录（闲鱼登录态所在）

    为什么不再用 `data/webview_data_*`：全仓没有任何写入方创建过该目录（磁盘实测
    仓库 data/ 与 %APPDATA%/XianyuHunter/data/ 均无 webview_data_*），旧实现 glob
    一个不存在的目标，统计恒 0、删除永远空转，却对用户显示「浏览器数据已清理」——
    属典型假回执。真实目录由配置项 browser.user_data_dir 决定，与 BrowserManager
    （container.py:432）、cookie_store.py:583、login_strategy.py:170 同一解析函数，
    保证「清理的目标」＝「写入的目标」。

    解析失败（配置异常/无权限建目录）返回 None，调用方按「未能定位」处理，
    不猜路径、不删任何目录。
    """
    try:
        bd = get_browser_data_dir(get_config().browser.user_data_dir)
        # 相对路径要落成绝对路径再回带给统计/预览/确认框（T02575 真机验收发现）：
        # 开发模式下 get_app_dir() 是 "."，于是界面显示「将删除 browser-data」这种
        # 相对名字——用户既核对不了、也不知道自己登录态到底在哪个盘。配置本来就是
        # 绝对路径时不动它，避免 resolve() 在短路径（8.3）环境下改写既有语义。
        return bd if bd.is_absolute() else bd.resolve()
    except Exception as e:  # noqa: BLE001 - 状态查询不能因配置读取失败而 500
        logger.warning("解析浏览器数据目录失败: %s", e)
        return None


def _walk_dir(path: Path) -> tuple[int, int]:
    """单次遍历目录，返回 (总字节数, 文件数)；目录不存在或不可读返回 (0, 0)

    用 os.scandir 手工栈遍历，而不是 `rglob("*")` 后再逐个 `is_file()`+`stat()`：
    后者对每个条目要两次系统调用，而真实浏览器 profile（实测 2073 个文件 /
    426 MB）在磁盘争用期间会让单个预览请求跑到 449s。这里每个条目只遍历一次、
    只 stat 一次，且单个子目录不可读时跳过而不是让整个统计炸掉。
    符号链接既不计入数量也不计入大小（避免跟着链接重复统计或被锁的文件拖住）。
    """
    total = 0
    count = 0
    stack = [str(path)]
    while stack:
        try:
            with os.scandir(stack.pop()) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            count += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return total, count


def _dir_stats(path: Path) -> tuple[float, int]:
    """返回目录的 (MB, 文件数)；目录不存在返回 (0.0, 0)"""
    size, count = _walk_dir(path)
    return round(size / 1024 / 1024, 2), count


def _browser_profile_busy(profile: Path) -> str | None:
    """检测浏览器用户数据目录是否正被浏览器进程占用

    删除正在使用的 Chromium/Edge  profile 会让浏览器会话与登录态损坏（Windows
    上多数文件被锁，rmtree 只能删掉一半，留下半坏目录），因此真实删除前必须拦截。

    判定依据：任一进程 cmdline 含 `--user-data-dir=<本目录>`。
    psutil 不可用时退回探测 Chromium 自己的 SingletonLock——真占用时该文件必在，
    宁可漏判（后续由 _remove_tree 把锁定文件如实报错）也不谎报占用把功能锁死。
    """
    try:
        import psutil
    except ImportError:
        psutil = None
    if psutil is not None:
        target = str(profile).rstrip("\\/").lower()
        for proc in psutil.process_iter(["cmdline"]):
            try:
                for part in (proc.info.get("cmdline") or []):
                    p = str(part).lower()
                    if p.startswith("--user-data-dir=") and \
                            p.split("=", 1)[1].rstrip("\\/").lower() == target:
                        return f"PID {proc.info.get('pid')}"
            except Exception:  # noqa: BLE001 - 单个进程不可读不影响整体扫描
                continue
        return None
    # 无 psutil 的退化判定：Chromium 单实例锁
    return "SingletonLock 存在" if (profile / "SingletonLock").exists() else None


def _remove_tree(path: Path) -> list[str]:
    """删除目录树，返回失败明细（空列表＝确实删净）

    为什么不用 shutil.rmtree(ignore_errors=True)：它会吞掉「文件被占用」这类失败，
    调用方随后仍报告「已删除」——目录其实还在。这里收集 onerror 明细，让回执与磁盘
    真实状态一致。
    """
    failures: list[str] = []

    def _on_error(func, err_path, exc) -> None:  # noqa: ANN001 - shutil onerror 签名
        failures.append(f"{err_path}（{exc[0].__name__}）")

    try:
        shutil.rmtree(path, onerror=_on_error)
    except Exception as e:  # noqa: BLE001
        failures.append(f"{path}（{type(e).__name__}: {e}）")
    if failures and path.exists():
        # 目录仍在＝删除未成功；rmtree 会尽力删掉可删部分，这里补一条总体说明
        failures.append(f"目录未完全删除，仍有残留：{path}")
    return failures


# ============== 清理前状态查询 ==============
@router.get("/status")
@cached_ttl(60, key_fn=lambda container: "maintenance_status", stale_while_revalidate=True)
def maintenance_status(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """获取系统当前存储状态，供清理前评估"""
    # 数据库表统计
    from sqlalchemy import text
    db_stats = {}
    try:
        with container.repo.engine.connect() as conn:
            for table in ("tasks", "items", "task_links", "events", "orders", "notifications"):
                try:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    db_stats[table] = count
                except Exception:
                    db_stats[table] = 0
            # 数据库文件大小
            db_path = _data_dir() / "xianyu.db"
            db_stats["db_size_mb"] = round(db_path.stat().st_size / 1024 / 1024, 2) if db_path.exists() else 0
    except Exception as e:
        logger.warning("获取数据库状态失败: %s", e)

    # 日志文件统计
    log_stats = {"file_count": 0, "total_size_mb": 0, "oldest": None}
    try:
        log_dir = _log_dir()
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log*"))
            log_stats["file_count"] = len(log_files)
            total_size = sum(f.stat().st_size for f in log_files if f.is_file())
            log_stats["total_size_mb"] = round(total_size / 1024 / 1024, 2)
            if log_files:
                oldest = min(f.stat().st_mtime for f in log_files if f.is_file())
                log_stats["oldest"] = datetime.fromtimestamp(oldest).strftime("%Y-%m-%d")
    except Exception:
        pass

    # 缓存统计（浏览器用户数据目录 + Python 字节码缓存）
    # 统计范围需与 cleanup_cache 实际清理范围保持一致，避免"显示0MB但清理271项"的不一致
    # FR-A-5（T02575）：browser_data 改统真实目录（原 webview_data_* 全仓无写入方，
    # 恒为 0）；temp_files 原取 /tmp/xianyu_*，Windows 上路径不存在、恒为 0，且没有
    # 任何清理分支会删它——"看起来可清理却永远清不掉"，一并移除
    cache_stats: dict[str, Any] = {
        "browser_data_mb": 0,
        "browser_data_files": 0,
        "browser_data_exists": False,
        "browser_data_path": None,
        "pycache_mb": 0,
        "pycache_count": 0,
    }
    try:
        # 浏览器数据目录（登录态所在，路径回带给前端如实展示）
        bd = _browser_data_dir()
        if bd is not None:
            cache_stats["browser_data_path"] = str(bd)
            cache_stats["browser_data_exists"] = bd.exists() and any(bd.iterdir())
            cache_stats["browser_data_mb"], cache_stats["browser_data_files"] = _dir_stats(bd)
        # Python __pycache__ 目录（与 cleanup_cache 的清理范围同一函数、同一根目录）
        # 口径：pycache_count 是「缓存目录数」——前端概览与确认框都按「__pycache__ 目录 N 个」
        # 措辞，清理动作也是整目录删除，因此按目录计数才对得上（T02575）
        pycache_total = 0
        pycache_count = 0
        for p in _iter_pycache_dirs():
            size, _files = _walk_dir(p)
            pycache_count += 1
            pycache_total += size
        cache_stats["pycache_mb"] = round(pycache_total / 1024 / 1024, 2)
        cache_stats["pycache_count"] = pycache_count
    except Exception:
        pass

    return {"db": db_stats, "logs": log_stats, "cache": cache_stats}


# ============== 缓存清理 ==============
def _cleanup_browser_data(dry_run: bool, cleaned: list, errors: list) -> None:
    """清理真实浏览器用户数据目录（配置 browser.user_data_dir）

    该目录存的是闲鱼登录 Cookie 与反检测指纹，删除后必须重新扫码登录——
    因此预览与执行两态都要把这一后果写进回执（FR-A-5 / T02575）。
    dry_run 只统计不删除；目录不存在时不追加任何"已清理"条目，避免空转报成功。
    """
    profile = _browser_data_dir()
    if profile is None:
        errors.append("未能定位浏览器用户数据目录（browser.user_data_dir 解析失败），本次未删除任何文件")
        return
    mb, nfiles = _dir_stats(profile)
    if not profile.exists() or nfiles == 0:
        return

    if dry_run:
        cleaned.append(
            f"[预览] 将删除 {profile}（{nfiles} 个文件 / {mb} MB）"
            "——闲鱼登录 Cookie 与浏览器指纹就在该目录，删除后需重新扫码登录"
        )
        return

    busy = _browser_profile_busy(profile)
    if busy:
        errors.append(
            f"浏览器数据目录正被占用（{busy}），已跳过删除；"
            "请先关闭使用该目录的浏览器窗口或停止采集/登录任务后重试"
        )
        return

    failures = _remove_tree(profile)
    if failures:
        errors.extend(f"浏览器数据删除失败: {f}" for f in failures[:5])
        return
    cleaned.append(
        f"已删除 {profile.name}（{nfiles} 个文件 / {mb} MB）；"
        "闲鱼登录态已清除，下次采集前需重新扫码登录"
    )


def _cleanup_pycache(dry_run: bool, cleaned: list, errors: list) -> None:
    """清理 Python __pycache__ 缓存（仅项目源码目录）

    排除 .venv 等第三方依赖目录（由 _iter_pycache_dirs 处理），
    清理后首次导入会重新编译 .pyc，不影响功能。

    旧实现用 `shutil.rmtree(p, ignore_errors=True)` 后无条件追加「已删除 {p}」：
    被占用/无权限的目录删不掉，回执却说删掉了。现在走 _remove_tree，
    失败明细进 errors，只有确实删净的目录才计入 cleaned（T02575）。
    """
    try:
        for p in _iter_pycache_dirs():
            if dry_run:
                cleaned.append(f"[预览] 将删除 {p}")
                continue
            if not p.exists():
                continue  # 扫描与删除之间目录消失（并发清理），不算失败也不算成功删除
            failures = _remove_tree(p)
            if failures:
                errors.extend(failures)
            else:
                cleaned.append(f"已删除 {p}")
    except Exception as e:
        errors.append(f"Python 字节码缓存清理失败: {e}")


# 缓存清理的合法 target（4.1-3 / T02575：temp 是历史误名，实删 __pycache__）
_CACHE_TARGETS = ("browser_data", "pycache", "all")
# 旧客户端仍可能发 temp：映射到语义正确的 pycache，而不是让请求静默落空
_CACHE_TARGET_ALIASES = {"temp": "pycache"}


@router.post("/cache")
def cleanup_cache(
    req: CleanupRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """清理缓存数据（浏览器用户数据目录、Python 字节码缓存）

    target 可选值：
    - browser_data: 清理真实浏览器用户数据目录（会清除闲鱼登录态）
    - pycache: 清理 Python 字节码缓存（__pycache__；旧名 temp 自动映射到本分支）
    - all: 全部清理
    """
    raw_target = req.target or "all"
    target = _CACHE_TARGET_ALIASES.get(raw_target, raw_target)
    cleaned = []
    errors = []

    if target not in _CACHE_TARGETS:
        # 未知 target 旧实现是"什么都不删、返回 count=0 的成功回执"，用户看到
        # 「清理完成 0 项」却以为功能正常——这里改为显式失败
        errors.append(
            f"未知的清理范围：{raw_target}（可选 {' / '.join(_CACHE_TARGETS)}），本次未删除任何文件"
        )
    else:
        if target in ("browser_data", "all"):
            _cleanup_browser_data(req.dry_run, cleaned, errors)
        if target in ("pycache", "all"):
            _cleanup_pycache(req.dry_run, cleaned, errors)

    # 记录操作日志
    _log_cleanup_action("cache", target, cleaned, errors, container)

    if not req.dry_run and not errors:
        # 状态接口有 60s TTL（stale-while-revalidate 更会让旧值一直回吐），
        # 清理后必须让概览缓存失效，否则用户看到"释放 271MB"而数字不变（4.1-4）
        invalidate_stats_cache()

    return {
        "target": target,
        "requested_target": raw_target,
        "dry_run": req.dry_run,
        "cleaned": cleaned,
        "errors": errors,
        "count": len(cleaned),
    }


# ============== 数据库清理 ==============
def _cleanup_old_events(conn, dry_run: bool, days: int, cutoff: datetime, cleaned: list) -> int:
    """处理 events 表中 N 天前的记录

    dry_run 只统计不删除，返回**预计**删除行数；非 dry_run 返回实际删除行数。
    两态都返回条数（4.1-2 / T02575）：旧实现预览返回 0，接口把 total_deleted
    报成 0，前端却按"删除 0 条"渲染绿色成功态——预览语义与回执互相矛盾。
    cleaned 列表通过引用修改，追加预览/删除消息。
    """
    from sqlalchemy import text
    if dry_run:
        count = conn.execute(
            text("SELECT COUNT(*) FROM events WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        ).scalar() or 0
        cleaned.append(f"[预览] 将删除 {count} 条 {days} 天前的事件")
        return int(count)
    result = conn.execute(
        text("DELETE FROM events WHERE created_at < :cutoff"),
        {"cutoff": cutoff},
    )
    deleted = result.rowcount or 0
    cleaned.append(f"已删除 {deleted} 条 {days} 天前的事件")
    return deleted


def _cleanup_old_items(conn, dry_run: bool, days: int, cutoff: datetime, cleaned: list) -> int:
    """处理 items 表中 N 天前且未关联 task_links 的记录

    排除已关联商品避免删掉用户仍在监控的数据；
    dry_run 只统计不删除，同样返回预计条数（口径见 _cleanup_old_events）。
    """
    from sqlalchemy import text
    # 关联检查子查询：排除仍在 task_links 中的商品
    not_linked = "AND id NOT IN (SELECT link_key FROM task_links WHERE link_type='item')"
    if dry_run:
        count = conn.execute(
            text(f"SELECT COUNT(*) FROM items WHERE first_seen < :cutoff {not_linked}"),
            {"cutoff": cutoff},
        ).scalar() or 0
        cleaned.append(f"[预览] 将删除 {count} 条 {days} 天前的未关联商品")
        return int(count)
    result = conn.execute(
        text(f"DELETE FROM items WHERE first_seen < :cutoff {not_linked}"),
        {"cutoff": cutoff},
    )
    deleted = result.rowcount or 0
    cleaned.append(f"已删除 {deleted} 条 {days} 天前的未关联商品")
    return deleted


def _cleanup_sold_items(conn, dry_run: bool, cleaned: list) -> int:
    """处理 task_links 中已售商品关联（display JSON 含 is_sold=true）

    注意：LIKE 模式中的冒号会被 SQLAlchemy 误判为绑定参数，必须用参数化查询。
    dry_run 返回预计条数。
    """
    from sqlalchemy import text
    # display 字段是 JSON 字符串，匹配 "is_sold":true
    sold_pattern = '%"is_sold":true%'
    if dry_run:
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM task_links WHERE link_type='item' "
                "AND display LIKE :pattern"
            ),
            {"pattern": sold_pattern},
        ).scalar() or 0
        cleaned.append(f"[预览] 将删除 {count} 条已售商品关联")
        return int(count)
    result = conn.execute(
        text(
            "DELETE FROM task_links WHERE link_type='item' "
            "AND display LIKE :pattern"
        ),
        {"pattern": sold_pattern},
    )
    deleted = result.rowcount or 0
    cleaned.append(f"已删除 {deleted} 条已售商品关联")
    return deleted


def _vacuum_database(engine, dry_run: bool, cleaned: list, errors: list) -> None:
    """执行 VACUUM 压缩数据库

    VACUUM 不能在事务中执行，需通过 execution_options(isolation_level="AUTOCOMMIT")
    显式关闭 SQLAlchemy 2.0 的隐式事务。
    """
    from sqlalchemy import text
    if dry_run:
        cleaned.append("[预览] 将执行 VACUUM 压缩数据库")
        return
    try:
        with engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.execute(text("VACUUM"))
            cleaned.append("已执行 VACUUM 压缩数据库")
    except Exception as e:
        errors.append(f"VACUUM 失败: {e}")


_DB_TARGETS = ("old_events", "old_items", "sold_items", "vacuum", "all")


@router.post("/database")
def cleanup_database(
    req: CleanupRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """清理数据库冗余数据

    target 可选值：
    - old_events: 清理 N 天前的事件记录
    - old_items: 清理 N 天前未关联的商品记录
    - sold_items: 清理已售商品记录
    - vacuum: VACUUM 压缩数据库
    - all: 以上全部

    `total_deleted` 的口径随 `dry_run` 变化，前端据此选词渲染（4.1-2）：
    dry_run=True 时是**预计**删除条数（由各 SELECT COUNT 汇总，不写库），
    dry_run=False 时是**实际**删除条数。
    """
    target = req.target or "all"
    days = max(1, req.days)
    cutoff = datetime.now() - timedelta(days=days)
    cleaned = []
    errors = []
    total_deleted = 0

    if target not in _DB_TARGETS:
        errors.append(
            f"未知的清理范围：{target}（可选 {' / '.join(_DB_TARGETS)}），本次未删除任何记录"
        )
        _log_cleanup_action("database", target, cleaned, errors, container)
        return {
            "target": target, "days": days, "dry_run": req.dry_run,
            "cleaned": cleaned, "errors": errors, "total_deleted": 0,
        }

    try:
        with container.repo.engine.begin() as conn:
            if target in ("old_events", "all"):
                total_deleted += _cleanup_old_events(conn, req.dry_run, days, cutoff, cleaned)

            if target in ("old_items", "all"):
                total_deleted += _cleanup_old_items(conn, req.dry_run, days, cutoff, cleaned)

            if target in ("sold_items", "all"):
                total_deleted += _cleanup_sold_items(conn, req.dry_run, cleaned)

            if target in ("vacuum", "all"):
                if req.dry_run:
                    cleaned.append("[预览] 将执行 VACUUM 压缩数据库")
                else:
                    # VACUUM 不能在事务中执行
                    pass

        # VACUUM 必须在 AUTOCOMMIT 模式下执行（不能在事务中）
        # SQLAlchemy 2.0 的 engine.connect() 默认开启隐式事务，
        # 需通过 execution_options(isolation_level="AUTOCOMMIT") 显式关闭事务
        if target in ("vacuum", "all") and not req.dry_run:
            _vacuum_database(container.repo.engine, False, cleaned, errors)

    except Exception as e:
        errors.append(f"数据库清理失败: {e}")
        logger.exception("数据库清理失败")

    _log_cleanup_action("database", target, cleaned, errors, container)

    if not req.dry_run and not errors:
        # 真实写库后概览统计（任务/商品/事件行数、库体积）必须立刻反映新值（4.1-4）
        invalidate_stats_cache()

    return {
        "target": target,
        "days": days,
        "dry_run": req.dry_run,
        "cleaned": cleaned,
        "errors": errors,
        "total_deleted": total_deleted,
    }


# ============== 日志清理 ==============
_LOG_TARGETS = ("old_logs", "large_logs", "all")


@router.post("/logs")
def cleanup_logs(
    req: CleanupRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """清理日志文件

    target 可选值：
    - old_logs: 清理 N 天前的日志文件
    - large_logs: 清理超过 10MB 的日志文件
    - all: 全部清理

    `total_freed_mb` 口径同 `total_deleted`：dry_run 时是**预计**可释放量。
    """
    target = req.target or "old_logs"
    days = max(1, req.days)
    cutoff = datetime.now() - timedelta(days=days)
    cleaned = []
    errors = []
    total_freed_mb = 0.0

    if target not in _LOG_TARGETS:
        errors.append(
            f"未知的清理规则：{target}（可选 {' / '.join(_LOG_TARGETS)}），本次未删除任何文件"
        )
        return {
            "target": target, "days": days, "dry_run": req.dry_run,
            "cleaned": cleaned, "errors": errors, "total_freed_mb": 0,
        }

    log_dir = _log_dir()
    if not log_dir.exists():
        return {
            "target": target,
            "days": days,
            "dry_run": req.dry_run,
            "cleaned": [],
            "errors": [f"日志目录不存在：{log_dir}"],
            "total_freed_mb": 0,
        }

    try:
        for f in log_dir.glob("*.log*"):
            if not f.is_file():
                continue
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            size_mb = f.stat().st_size / 1024 / 1024

            # S1871: 两个分支都设置 should_delete=True，合并条件简化逻辑
            should_delete = (
                (target in ("old_logs", "all") and mtime < cutoff)
                or (target in ("large_logs", "all") and size_mb > 10)
            )

            if should_delete:
                if req.dry_run:
                    # 预览也要汇总预计释放量，否则前端只能显示"释放 0 MB"（4.1-2）
                    total_freed_mb += size_mb
                    cleaned.append(f"[预览] 将删除 {f.name} ({round(size_mb, 2)}MB, {mtime.strftime('%Y-%m-%d')})")
                else:
                    try:
                        f.unlink()
                    except OSError as e:
                        # 正在写入的日志在 Windows 上会被句柄占用；删除失败必须显式
                        # 报错，不能既不算 cleaned 也不告诉用户为什么"清理了却没释放"
                        errors.append(f"删除 {f.name} 失败: {type(e).__name__}: {e}")
                        continue
                    total_freed_mb += size_mb
                    cleaned.append(f"已删除 {f.name} ({round(size_mb, 2)}MB)")
    except Exception as e:
        errors.append(f"日志清理失败: {e}")

    _log_cleanup_action("logs", target, cleaned, errors, container)

    if not req.dry_run and not errors:
        invalidate_stats_cache()

    return {
        "target": target,
        "days": days,
        "dry_run": req.dry_run,
        "cleaned": cleaned,
        "errors": errors,
        "total_freed_mb": round(total_freed_mb, 2),
    }


def _log_cleanup_action(category: str, target: str, cleaned: list, errors: list, container: Container) -> None:
    """将清理操作记录到 events 表，供审计追踪"""
    try:
        container.repo.save_event({
            "type": f"maintenance.{category}",
            "task_id": None,
            "stage": "cleanup",
            "level": "err" if errors else "info",
            "message": f"清理{category}({target}): {len(cleaned)} 项完成" + (f", {len(errors)} 错误" if errors else ""),
            "payload": json.dumps({
                "category": category,
                "target": target,
                "cleaned_count": len(cleaned),
                "error_count": len(errors),
                "cleaned_items": cleaned[:20],
                "errors": errors[:5],
            }, ensure_ascii=False),
        })
    except Exception:
        pass
