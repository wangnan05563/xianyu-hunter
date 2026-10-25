"""系统清理页真实目标与预览语义（T02575 / PRD FR-A-5 + 评审 4.1-2~4.1-4）

三条"假能力/假回执"红线：

- FR-A-5：清理目标必须是配置 `browser.user_data_dir` 指向的真实浏览器资料目录。
  旧实现 glob `data/webview_data_*`——全仓无任何写入方、磁盘上不存在，统计恒 0、
  删除永远空转，却仍回执「已删除」，是本页最严重的假能力。
- 4.1-2：dry_run 的预计条数/预计释放量必须如实回带。旧实现预览恒返回
  `total_deleted=0`/`total_freed_mb=0`，前端按成功态渲染绿色「删除 0 条」。
- 4.1-4：真实删除后必须让带 60s TTL 的状态概览失效，否则"提示释放了 271MB
  而概览数字不变"。`?bypass_cache=1` 是无效方案（bypass_cache 是装饰器 kwargs），
  本文件断言走 `invalidate_stats_cache()`。
"""
from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from xianyu_hunter.web import cache as web_cache
from xianyu_hunter.web.routes import api_maintenance
from xianyu_hunter.web.routes.api_maintenance import CleanupRequest


class _StubRepo:
    def __init__(self, engine=None) -> None:
        self.engine = engine

    def save_event(self, _payload):  # 审计写库不影响被测逻辑
        return None


class _StubContainer:
    def __init__(self, engine=None) -> None:
        self.repo = _StubRepo(engine)


def _request(user_id: str = "default"):
    """直调端点时顶替 FastAPI 注入的 Request（真实请求里由鉴权中间件写 state.user_id）"""
    return SimpleNamespace(state=SimpleNamespace(user_id=user_id))


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    """把浏览器资料目录指到临时目录，并造出可统计的内容（体积需能让 MB 保留 2 位不为 0）"""
    profile = tmp_path / "browser-data"
    (profile / "Default" / "Network").mkdir(parents=True)
    (profile / "Default" / "Network" / "Cookies").write_bytes(b"x" * 1_572_864)
    (profile / "Local State").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(api_maintenance, "_browser_data_dir", lambda: profile)
    return profile


# ============== FR-A-5：清理目标＝配置里的真实目录 ==============
def test_browser_data_dir_follows_config(tmp_path, monkeypatch):
    """目录解析必须来自 browser.user_data_dir，而不是硬编码的 webview_data_*"""
    target = tmp_path / "my-profile"
    monkeypatch.setattr(
        api_maintenance, "get_config",
        lambda: SimpleNamespace(browser=SimpleNamespace(user_data_dir="my-profile")),
    )
    monkeypatch.setattr(api_maintenance, "get_browser_data_dir", lambda p: tmp_path / p)
    assert api_maintenance._browser_data_dir() == target


def test_browser_data_dir_relative_config_is_displayed_absolute(tmp_path, monkeypatch):
    """配置解析出相对路径时（开发模式 app_dir="."），回带给界面的必须是绝对路径

    真机验收发现确认框只写「将删除 browser-data」，用户无法核对登录态究竟在哪个盘；
    「回显实际路径」这句话本身就成了空话。"""
    monkeypatch.setattr(
        api_maintenance, "get_config",
        lambda: SimpleNamespace(browser=SimpleNamespace(user_data_dir="browser-data")),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        api_maintenance, "get_browser_data_dir",
        lambda _p: Path("browser-data"),  # 模拟 get_app_dir() == Path(".")
    )
    bd = api_maintenance._browser_data_dir()
    assert bd is not None and bd.is_absolute()
    assert str(bd).replace("\\", "/").endswith("browser-data")


def test_browser_data_dir_failure_returns_none(monkeypatch):
    """配置异常时不猜路径：返回 None，调用方据此拒绝删除任何目录"""
    def _boom():
        raise RuntimeError("配置损坏")

    monkeypatch.setattr(api_maintenance, "get_config", _boom)
    assert api_maintenance._browser_data_dir() is None


def test_status_reports_real_profile_and_drops_dead_temp_stat(profile_dir, monkeypatch):
    """状态统计与被清对象同源；恒 0 的 temp_files（/tmp/xianyu_*）统计已移除"""
    monkeypatch.setattr(api_maintenance, "_iter_pycache_dirs", lambda *a, **k: [])
    status = api_maintenance.maintenance_status.__wrapped__(container=_StubContainer())
    cache_stats = status["cache"]
    assert "temp_files" not in cache_stats, "Windows 上恒为 0 的临时文件统计不该再回给前端"
    assert cache_stats["browser_data_path"] == str(profile_dir)
    assert cache_stats["browser_data_exists"] is True
    assert cache_stats["browser_data_files"] == 2
    assert cache_stats["browser_data_mb"] > 0


def test_cleanup_cache_real_run_removes_configured_profile(profile_dir):
    """执行态真的删掉登录目录，且回执写清「删除后需重新扫码登录」"""
    result = api_maintenance.cleanup_cache(
        CleanupRequest(target="browser_data", dry_run=False), request=_request(), container=_StubContainer(),
    )
    assert result["errors"] == []
    assert not profile_dir.exists()
    assert "重新扫码登录" in result["cleaned"][0]


def test_cleanup_cache_preview_keeps_profile(profile_dir):
    """预览态一条都不能少删"""
    result = api_maintenance.cleanup_cache(
        CleanupRequest(target="browser_data", dry_run=True), request=_request(), container=_StubContainer(),
    )
    assert profile_dir.exists() and (profile_dir / "Local State").exists()
    assert result["dry_run"] is True
    assert result["cleaned"][0].startswith("[预览]")


def test_missing_profile_is_not_reported_as_cleaned(tmp_path, monkeypatch):
    """目录不存在时不能追加"已删除"条目——空转报成功就是假回执"""
    monkeypatch.setattr(api_maintenance, "_browser_data_dir", lambda: tmp_path / "never-existed")
    result = api_maintenance.cleanup_cache(
        CleanupRequest(target="browser_data", dry_run=False), request=_request(), container=_StubContainer(),
    )
    assert result["cleaned"] == [] and result["count"] == 0


def test_busy_profile_is_skipped_with_error(profile_dir, monkeypatch):
    """浏览器占用资料目录时拒绝删除（否则会留下半坏的 profile）并显式报错"""
    monkeypatch.setattr(api_maintenance, "_browser_profile_busy", lambda _p: "PID 4321")
    result = api_maintenance.cleanup_cache(
        CleanupRequest(target="browser_data", dry_run=False), request=_request(), container=_StubContainer(),
    )
    assert profile_dir.exists(), "占用中却删了一半＝登录态损坏"
    assert result["cleaned"] == []
    assert "占用" in result["errors"][0]


# ============== 4.1-3：temp 名实对齐 ==============
def test_temp_alias_maps_to_pycache(monkeypatch):
    """历史 target=temp 仍可用，但语义（实删 __pycache__）必须被如实回带"""
    calls: list[str] = []
    monkeypatch.setattr(api_maintenance, "_iter_pycache_dirs", lambda *a, **k: calls.append("pycache") or [])
    result = api_maintenance.cleanup_cache(
        CleanupRequest(target="temp", dry_run=True), request=_request(), container=_StubContainer(),
    )
    assert result["target"] == "pycache" and result["requested_target"] == "temp"
    assert result["errors"] == [] and calls == ["pycache"]


def test_unknown_target_fails_loudly(profile_dir):
    """未知 target 旧实现"什么都不删、返回成功"，现在必须点名报错"""
    result = api_maintenance.cleanup_cache(
        CleanupRequest(target="webview_data", dry_run=False), request=_request(), container=_StubContainer(),
    )
    assert result["count"] == 0 and profile_dir.exists()
    assert "未知的清理范围" in result["errors"][0]


def test_no_webview_data_left_in_cleanup_sources():
    """FR-A-5 验收：幻影目录不得再出现在"可执行的清理目标"或"用户可见文案"里

    口径说明：注释与 docstring 里允许保留一次历史说明（解释当初为什么错），
    所以这里不粗暴地全文 grep，而是分别钉住两类真实载体——
    - 后端：不得再有 `glob("webview_data...` 这类扫描目标（目标只能来自配置解析）；
    - 前端（桌面 + 移动）：剥掉注释后不得残留该字面值（选项名、文案、请求参数都在字符串里）。
    """
    root = Path(__file__).resolve().parents[1]
    backend_src = (root / "backend/xianyu_hunter/web/routes/api_maintenance.py").read_text(encoding="utf-8")
    assert 'glob("webview_data' not in backend_src
    assert "glob('webview_data" not in backend_src
    for rel in (
        "frontend/src/pages/Maintenance/Cleanup.tsx",
        "frontend/src/mobile/pages/Cleanup/index.tsx",
    ):
        src = (root / rel).read_text(encoding="utf-8")
        code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        code = "\n".join(
            line for line in code.splitlines() if not line.strip().startswith("//")
        )
        assert "webview_data" not in code, f"{rel} 的界面文案/参数仍引用幻影目录"


# ============== 4.1-2：dry_run 预计量如实回带 ==============
@pytest.fixture
def db_container():
    """临时 SQLite 库，建出清理分支用到的三张表并塞入跨 cutoff 的样本"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        engine = create_engine(f"sqlite:///{Path(d) / 'm.db'}")
        old, recent = datetime.now() - timedelta(days=120), datetime.now()
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE events (id TEXT PRIMARY KEY, created_at DATETIME)"))
            conn.execute(text("CREATE TABLE items (id TEXT PRIMARY KEY, first_seen DATETIME)"))
            conn.execute(text(
                "CREATE TABLE task_links (link_key TEXT, link_type TEXT, display TEXT)"
            ))
            for i in range(4):
                conn.execute(
                    text("INSERT INTO events (id, created_at) VALUES (:i, :ts)"),
                    {"i": f"e{i}", "ts": old if i < 3 else recent},
                )
            for i in range(2):
                conn.execute(
                    text("INSERT INTO items (id, first_seen) VALUES (:i, :ts)"),
                    {"i": f"i{i}", "ts": old if i == 0 else recent},
                )
            # 已售关联挂在 i9（不存在的商品）上：既让 sold_items 分支有 1 条可算，
            # 又不影响 old_items 分支对 i0 的"未关联"判定；i1 用未售出关联占位，
            # 验证"仍在监控的商品不会被删"这条排除逻辑。
            # display 必须走绑定参数——JSON 里的冒号会被 SQLAlchemy 当成 bind param
            # （正是被测代码 _cleanup_sold_items 注释里记录的同一个坑）
            for key, display in (("i9", '{"is_sold":true}'), ("i1", '{"is_sold":false}')):
                conn.execute(
                    text("INSERT INTO task_links (link_key, link_type, display) "
                         "VALUES (:k, 'item', :d)"),
                    {"k": key, "d": display},
                )
        yield _StubContainer(engine)
        engine.dispose()


def test_database_preview_projects_counts_without_deleting(db_container):
    result = api_maintenance.cleanup_database(
        CleanupRequest(target="all", days=30, dry_run=True), request=_request(), container=db_container,
    )
    assert result["dry_run"] is True
    assert result["total_deleted"] == 5, "预览必须回带预计条数（3 事件 + 1 商品 + 1 已售关联）"
    assert any("将删除 3 条" in c for c in result["cleaned"])
    with db_container.repo.engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM events")).scalar() == 4, "预览不许写库"


def test_database_real_run_deletes_and_reports(db_container):
    result = api_maintenance.cleanup_database(
        CleanupRequest(target="old_events", days=30, dry_run=False), request=_request(), container=db_container,
    )
    assert result["total_deleted"] == 3
    with db_container.repo.engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM events")).scalar() == 1


# ============== 日志：预计释放量 + 真实删除后失效概览缓存 ==============
@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    d = tmp_path / "logs"
    d.mkdir()
    old = d / "app.2020-01-01.log"
    old.write_text("x" * 1_048_576, encoding="utf-8")
    stamp = (datetime.now() - timedelta(days=400)).timestamp()
    os.utime(old, (stamp, stamp))
    monkeypatch.setattr(api_maintenance, "_log_dir", lambda: d)
    return d


def test_logs_preview_projects_freed_mb(log_dir):
    result = api_maintenance.cleanup_logs(
        CleanupRequest(target="old_logs", days=7, dry_run=True), request=_request(), container=_StubContainer(),
    )
    assert result["total_freed_mb"] > 0, "预览态旧实现恒返回 0，前端只能显示「释放 0 MB」"
    assert log_dir / "app.2020-01-01.log" in list(log_dir.iterdir())


def test_real_cleanup_invalidates_status_cache(log_dir):
    """清理后必须让 60s TTL 概览失效，否则用户看到"释放成功"而数字不变（4.1-4）"""
    web_cache._cache_store[("maintenance_status", "maintenance_status")] = (
        web_cache.time.monotonic(), {"stale": True},
    )
    result = api_maintenance.cleanup_logs(
        CleanupRequest(target="old_logs", days=7, dry_run=False), request=_request(), container=_StubContainer(),
    )
    assert result["cleaned"] and not result["errors"]
    assert not list(log_dir.iterdir())
    assert not web_cache._cache_store, "真实删除后概览缓存未被作废"


def test_preview_does_not_invalidate_cache(log_dir):
    """预览没改动磁盘，不该顺手把全站统计缓存清空"""
    web_cache._cache_store[("maintenance_status", "maintenance_status")] = (
        web_cache.time.monotonic(), {"keep": True},
    )
    api_maintenance.cleanup_logs(
        CleanupRequest(target="old_logs", days=7, dry_run=True), request=_request(), container=_StubContainer(),
    )
    assert web_cache._cache_store
    web_cache._cache_store.clear()


# ============== _remove_tree：失败必须可见（不用 ignore_errors 吞异常） ==============
def test_remove_tree_reports_failures(tmp_path, monkeypatch):
    d = tmp_path / "profile"
    (d / "sub").mkdir(parents=True)

    def _boom(_path, **_kw):
        raise PermissionError("另一个程序正在使用此文件")

    monkeypatch.setattr(api_maintenance.shutil, "rmtree", _boom)
    failures = api_maintenance._remove_tree(d)
    assert failures and "PermissionError" in failures[0]
    assert any("仍有残留" in f for f in failures)


def test_remove_tree_success_leaves_nothing(tmp_path):
    d = tmp_path / "profile"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "f").write_text("x", encoding="utf-8")
    assert api_maintenance._remove_tree(d) == []
    assert not d.exists()


# ============== 扫描本身必须命中（T02575 实测发现的第二个假护栏） ==============
@pytest.fixture
def scan_tree(tmp_path, monkeypatch):
    """造一棵带 __pycache__ 的源码树 + 不应被统计/清理的依赖目录

    扫描根目录由 get_project_root() 决定（不再跟着 cwd 走），因此这里把锚点
    指到临时目录；大小取 1.5 MB 级别，保证 MB 保留 2 位后不为 0。
    """
    for rel in ("pkg", "pkg/sub", ".venv/lib", "node_modules/x", "data/chroma"):
        (tmp_path / rel / "__pycache__").mkdir(parents=True)
        (tmp_path / rel / "__pycache__" / "m.pyc").write_bytes(b"\x00" * 1_572_864)
    monkeypatch.setattr(api_maintenance, "get_project_root", lambda: tmp_path)
    return tmp_path


def test_pycache_scan_finds_source_dirs_and_skips_excluded(scan_tree):
    """旧实现在过滤 dirnames 之后才判断 `if "__pycache__" in dirnames`，
    被过滤掉的名字永远不可能再命中 → 恒返回空列表，「Python 编译缓存」
    于是统计恒 0、清理恒空转。此断言锁死这个回归。"""
    found = api_maintenance._iter_pycache_dirs()
    rel = sorted(str(p.relative_to(scan_tree)).replace("\\", "/") for p in found)
    assert rel == ["pkg/__pycache__", "pkg/sub/__pycache__"], (
        f"只应命中源码目录，实际={rel}")
    assert all(p.is_absolute() for p in found), (
        "回带给界面/回执的必须是可核对的绝对路径（打包版 cwd 可能是任意目录）")


def test_pycache_cleanup_preview_and_real_run_hit_real_dirs(scan_tree):
    """清理缓存（pycache）预览要列出目录、执行要真删——不能只给「已清理 0 项」的漂亮回执"""
    preview = api_maintenance.cleanup_cache(
        CleanupRequest(target="pycache", dry_run=True), request=_request(), container=_StubContainer(),
    )
    assert preview["dry_run"] is True and preview["count"] == 2
    assert all(c.startswith("[预览]") for c in preview["cleaned"])
    assert (scan_tree / "pkg" / "__pycache__").exists(), "预览不得删除任何东西"

    run = api_maintenance.cleanup_cache(
        CleanupRequest(target="pycache", dry_run=False), request=_request(), container=_StubContainer(),
    )
    assert run["errors"] == [] and run["count"] == 2
    assert not (scan_tree / "pkg" / "__pycache__").exists()
    assert not (scan_tree / "pkg" / "sub" / "__pycache__").exists()
    assert (scan_tree / ".venv" / "lib" / "__pycache__").exists(), "第三方依赖缓存不该被动"


def test_pycache_real_run_reports_locked_dir_instead_of_fake_success(scan_tree, monkeypatch):
    """删不掉的缓存目录必须进 errors，不能照样回一句「已删除」"""
    def _boom(_path, **_kw):
        raise PermissionError("另一个程序正在使用此文件")

    monkeypatch.setattr(api_maintenance.shutil, "rmtree", _boom)
    run = api_maintenance.cleanup_cache(
        CleanupRequest(target="pycache", dry_run=False), request=_request(), container=_StubContainer(),
    )
    assert run["cleaned"] == [] and run["errors"], "被占用却报已清理＝假回执"
    assert (scan_tree / "pkg" / "__pycache__").exists()


def test_status_pycache_count_is_not_hardcoded_zero(scan_tree, profile_dir):
    """概览里的 Py缓存 数必须来自真实扫描（否则界面上的数字是摆设）"""
    status = api_maintenance.maintenance_status.__wrapped__(container=_StubContainer())
    assert status["cache"]["pycache_count"] == 2
    assert status["cache"]["pycache_mb"] > 0


# ============== 打包版：「Python 编译缓存」不适用（T02739） ==============
def test_dev_build_keeps_pycache_applicable(scan_tree, profile_dir):
    """开发模式必须照常可用，别把「不适用」判定写成一刀切"""
    status = api_maintenance.maintenance_status.__wrapped__(container=_StubContainer())
    assert status["cache"]["pycache_applicable"] is True
    assert status["cache"]["pycache_count"] == 2


def test_frozen_build_marks_pycache_inapplicable_and_skips_scan(scan_tree, profile_dir, monkeypatch):
    """打包版没有源码树：status 回带不适用，且不再白扫一遍

    用 scan_tree 真造出 2 个 __pycache__——若实现仍在打包版扫描，count 会是 2，
    断言立即暴露「只是把界面文案改了、后端还在假装有东西可清」。
    """
    monkeypatch.setattr(api_maintenance, "is_frozen", lambda: True)
    status = api_maintenance.maintenance_status.__wrapped__(container=_StubContainer())
    cache = status["cache"]
    assert cache["pycache_applicable"] is False
    assert cache["pycache_count"] == 0 and cache["pycache_mb"] == 0
    # 不适用只作用于字节码缓存这一档，浏览器数据仍要如实统计
    assert cache["browser_data_path"] == str(profile_dir)


def test_frozen_build_explicit_pycache_cleanup_fails_loudly(scan_tree, monkeypatch):
    """显式请求 pycache 时不能回「已清理 0 项」的成功回执，必须说明不适用"""
    monkeypatch.setattr(api_maintenance, "is_frozen", lambda: True)
    run = api_maintenance.cleanup_cache(
        CleanupRequest(target="pycache", dry_run=False), request=_request(), container=_StubContainer(),
    )
    assert run["count"] == 0 and run["errors"], "打包版这一档没有任何可删对象，不能报成功"
    assert "不适用" in run["errors"][0]
    assert (scan_tree / "pkg" / "__pycache__").exists()


def test_frozen_build_all_still_cleans_browser_data_quietly(profile_dir, monkeypatch):
    """打包版「全部缓存」只剩浏览器数据：该删的要删，且不该为不适用档报错"""
    monkeypatch.setattr(api_maintenance, "is_frozen", lambda: True)
    run = api_maintenance.cleanup_cache(
        CleanupRequest(target="all", dry_run=False), request=_request(), container=_StubContainer(),
    )
    assert run["errors"] == [], "全部缓存里跳过不适用档不算失败"
    assert run["count"] == 1 and "已删除" in run["cleaned"][0]
    assert not profile_dir.exists()


def test_dir_stats_missing_dir_is_zero_and_survives_unreadable(tmp_path):
    """目录不存在 → (0.0, 0)；单个子目录不可读也不能让整次统计炸掉"""
    assert api_maintenance._dir_stats(tmp_path / "nope") == (0.0, 0)
    root = tmp_path / "mix"
    (root / "ok").mkdir(parents=True)
    (root / "ok" / "a.bin").write_bytes(b"y" * 2_000_000)
    mb, count = api_maintenance._dir_stats(root)
    assert count == 1 and mb == round(2_000_000 / 1024 / 1024, 2)
