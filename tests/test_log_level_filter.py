"""日志级别筛选（T02569 读侧 → T02683 归一后）

T02683 裁决「小写全词」：events.level 写侧只写 info / warning / error / debug / trace，
启动时 init_db 把历史 warn/err/大写行幂等改写。别名表已删除，读侧只认规范值，
本文件钉住归一后的真实行为，防止别名以任何形式回流。

按前端实际调用的端点打真实 FastAPI 应用（请求序列化、白名单校验、Repository
写入、回读全链路为真），只把数据库换成临时 SQLite，不使用 Mock 替身。
"""
from __future__ import annotations

import sqlite3

import pytest


class _ContainerShim:
    """只提供路由实际用到的 `.repo`，其余容器资源与本测试无关"""

    def __init__(self, repo):
        self.repo = repo


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.infra.repository import Repository
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    repo = Repository(db_path=str(tmp_path / "ux569.db"))
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)

    client = TestClient(app)
    # /api/* 全量需鉴权：与 tests/test_order_stats_and_notif_batch.py 同一口径
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo


def _mk_event(repo, *, level: str, message: str, task_id: str = "t1") -> int:
    return repo.save_event({
        "type": "system.test",
        "stage": "test",
        "level": level,
        "message": message,
        "task_id": task_id,
    })


# ---------------- 1. 别名表已删除 ----------------

def test_alias_table_is_gone() -> None:
    import xianyu_hunter.domain.events as events

    assert not hasattr(events, "level_literals")
    assert not hasattr(events, "_LEVEL_ALIASES")


# ---------------- 2. 仓储层：只看规范值 ----------------

def test_list_events_filters_by_canonical_level(api) -> None:
    _, repo = api
    _mk_event(repo, level="error", message="错误")
    _mk_event(repo, level="warning", message="警告")
    _mk_event(repo, level="info", message="信息")

    assert {e["message"] for e in repo.list_events(level="error", limit=50)} == {"错误"}
    assert {e["message"] for e in repo.list_events(level="warning", limit=50)} == {"警告"}
    assert {e["message"] for e in repo.list_events(level="info", limit=50)} == {"信息"}
    # 调用方传大写由仓储统一转小写，不算别名
    assert {e["message"] for e in repo.list_events(level="ERROR", limit=50)} == {"错误"}


def test_list_events_unknown_level_stays_exact(api) -> None:
    _, repo = api
    _mk_event(repo, level="critical", message="未知级别")
    assert {e["message"] for e in repo.list_events(level="critical", limit=50)} == {"未知级别"}
    # 未知值不能被放大成「不过滤」
    assert repo.list_events(level="fatal", limit=50) == []


# ---------------- 3. 启动迁移：历史写法归位 ----------------

def test_init_db_normalizes_legacy_level_rows(tmp_path) -> None:
    from xianyu_hunter.infra.db_models import init_db

    db = tmp_path / "legacy_levels.db"
    init_db(str(db))

    con = sqlite3.connect(db)
    for lvl in ("warn", "WARN", "err", "ERR", "ERROR", "WARNING", "INFO", "trace"):
        con.execute(
            "INSERT INTO events (type, stage, level, message, created_at) "
            "VALUES ('system.test', 'test', ?, ?, '2026-01-01 00:00:00')",
            (lvl, lvl),
        )
    con.commit()
    con.close()

    init_db(str(db))

    con = sqlite3.connect(db)
    rows = dict(con.execute("SELECT message, level FROM events").fetchall())
    con.close()

    assert rows == {
        "warn": "warning",
        "WARN": "warning",
        "err": "error",
        "ERR": "error",
        "ERROR": "error",
        "WARNING": "warning",
        "INFO": "info",
        "trace": "trace",
    }


# ---------------- 4. 搜索端点：筛选与分布同源 ----------------

def test_search_endpoint_filters_by_canonical_level(api) -> None:
    client, repo = api
    _mk_event(repo, level="error", message="E1")
    _mk_event(repo, level="warning", message="W1")
    _mk_event(repo, level="info", message="I1")

    res = client.get("/api/logs/search", params={"level": "error", "limit": 50})
    assert res.status_code == 200
    body = res.json()
    assert {i["message"] for i in body["items"]} == {"E1"}
    assert body["matched_levels"] == {"error": 1}

    res = client.get("/api/logs/search", params={"level": "WARNING", "limit": 50})
    assert {i["message"] for i in res.json()["items"]} == {"W1"}


def test_search_rejects_out_of_enum_level(api) -> None:
    client, _ = api
    # 入参白名单不变：归一化不等于放开任意值
    assert client.get("/api/logs/search", params={"level": "fatal"}).status_code == 422
    # 旧缩写不再接受：宁可 422，也不静默返回空结果
    assert client.get("/api/logs/search", params={"level": "err"}).status_code == 422
    assert client.get("/api/logs/search", params={"level": "warn"}).status_code == 422


def test_search_total_estimate_counts_all_matches_before_paging(api) -> None:
    """total_estimate 是命中总数，不是当页条数（T02678）。

    原先先切片再 len()，total_estimate 恒等于 count，前端无法区分「共 N 条」与
    「已展示 M 条」，截断提示也就永远不会出现。
    """
    client, repo = api
    for i in range(5):
        _mk_event(repo, level="info", message=f"I{i}")

    body = client.get("/api/logs/search", params={"limit": 2}).json()
    assert len(body["items"]) == 2
    assert body["count"] == 2
    assert body["total_estimate"] == 5


# ---------------- 5. 导出端点：与页面筛选拼合一致 ----------------

def test_export_csv_honors_filters(api) -> None:
    client, repo = api
    _mk_event(repo, level="error", message="要导出", task_id="tA")
    _mk_event(repo, level="info", message="级别不符", task_id="tA")
    _mk_event(repo, level="error", message="任务不符", task_id="tB")

    res = client.get("/api/logs/export", params={"format": "csv", "level": "error", "task_id": "tA"})
    assert res.status_code == 200
    text = res.text
    assert "要导出" in text
    assert "级别不符" not in text
    assert "任务不符" not in text
    assert res.headers["content-disposition"].startswith("attachment; filename=")


def test_export_csv_keyword_filter_combined_with_level(api) -> None:
    client, repo = api
    _mk_event(repo, level="warning", message="价格偏离")
    _mk_event(repo, level="warning", message="无关内容")

    res = client.get("/api/logs/export", params={"format": "csv", "level": "warning", "q": "价格偏离"})
    text = res.text
    assert "价格偏离" in text
    assert "无关内容" not in text
