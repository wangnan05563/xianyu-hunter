"""Task 11: 自动官方采集统计端点 GET /api/evaluations/auto-collect-stats 测试

覆盖：
- 空数据：total=0, success_rate=0
- 正常聚合：3 成功 + 1 失败 → total=4, success_rate=0.75
- top_failures 聚合：相同 error 合并、按计数降序、最多 3 条
- range_hours 过滤：跨时间段事件被正确包含/排除

测试设计：
- 用 tempfile + 真实 SQLite 建临时 DB（参考 test_items_data_source_migration.py）
- 用 TestClient + app.dependency_overrides 注入 fake container
  （参考 test_evaluations_sold_filter.py）
- upsert_eval_event 写入事件，与生产路径一致

为什么不用 mock repo：端点直接走 SQLAlchemy 查询 EventRow，
mock repo 无法验证 SQL 层的 LIKE 过滤和时间窗过滤逻辑。
"""
from __future__ import annotations

import json
import tempfile
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import Settings
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-auto-collect-stats"


@pytest.fixture
def tmp_repo() -> Repository:
    """使用临时数据库，避免污染真实数据"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
        # 释放 SQLAlchemy 持有的文件句柄（Windows 上必须）
        repo.engine.dispose()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    """构造 TestClient，注入临时 repository 和测试 token"""
    test_settings = Settings(web_token=_TEST_TOKEN)

    def _fake_settings():
        return test_settings

    monkeypatch.setattr("xianyu_hunter.config.get_settings", _fake_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", _fake_settings, raising=False)

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo

    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


def _seed_success(repo: Repository, item_id: str, *, created_at=None) -> None:
    """写入 eval.scored 事件，payload 标记 data_source=official

    为什么用 upsert_eval_event：与 worker 自动采集成功路径一致，
    端点 SQL 用 LIKE '%"data_source":"official"%' 粗筛 + Python 精确解析。
    """
    event = {
        "type": "eval.scored",
        "task_id": "t1",
        "item_id": item_id,
        "stage": "eval",
        "level": "info",
        "message": f"商品 {item_id} 官方采集评估分 80",
        "payload": json.dumps({
            "task_id": "t1",
            "item_id": item_id,
            "score": 80,
            "data_source": "official",
        }, ensure_ascii=False),
    }
    if created_at is not None:
        event["created_at"] = created_at
    repo.upsert_eval_event(event)


def _seed_failure(repo: Repository, item_id: str, error: str, *, created_at=None) -> None:
    """写入 collect.official.failed 事件，payload 含 error 字段

    与 worker.py 自动采集 except 分支写入路径一致，
    端点解析 payload.error 并截断前 100 字符作为 reason 聚合。
    """
    event = {
        "type": "collect.official.failed",
        "task_id": "t1",
        "item_id": item_id,
        "stage": "collect",
        "level": "warn",
        "message": f"自动官方采集失败 {item_id}: {error[:200]}",
        "payload": json.dumps({
            "task_id": "t1",
            "item_id": item_id,
            "error": error,
            "consecutive_failures": 1,
        }, ensure_ascii=False),
    }
    if created_at is not None:
        event["created_at"] = created_at
    repo.upsert_eval_event(event)


# ============== SubTask 11.3 测试用例 ==============


def test_auto_collect_stats_empty(client: TestClient, tmp_repo: Repository) -> None:
    """空数据：返回 total=0, success_rate=0

    验证端点在无事件时不报错且返回合理的默认值。
    """
    resp = client.get(
        "/api/evaluations/auto-collect-stats",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 0
    assert data["success"] == 0
    assert data["failed"] == 0
    assert data["success_rate"] == 0
    assert data["top_failures"] == []
    assert data["range_hours"] == 24


def test_auto_collect_stats_normal(client: TestClient, tmp_repo: Repository) -> None:
    """正常聚合：3 成功 + 1 失败 → total=4, success=3, failed=1, success_rate=0.75

    验证 SQL 层 LIKE 粗筛 + Python 层精确解析 data_source=official 能正确识别成功事件，
    失败事件 type=collect.official.failed 单独计数。
    """
    _seed_success(tmp_repo, "item_1")
    _seed_success(tmp_repo, "item_2")
    _seed_success(tmp_repo, "item_3")
    _seed_failure(tmp_repo, "item_4", "Cookie 过期")

    resp = client.get(
        "/api/evaluations/auto-collect-stats",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 4
    assert data["success"] == 3
    assert data["failed"] == 1
    assert data["success_rate"] == 0.75
    # 1 条失败事件也应出现在 top_failures
    assert len(data["top_failures"]) == 1
    assert data["top_failures"][0]["reason"] == "Cookie 过期"
    assert data["top_failures"][0]["count"] == 1


def test_auto_collect_stats_top_failures(client: TestClient, tmp_repo: Repository) -> None:
    """top_failures 聚合：相同 error 合并、按计数降序、最多 3 条

    场景：3 条失败事件（2 条相同 error + 1 条不同）
    期望：top_failures 第一项是出现 2 次的 error，第二项是出现 1 次的 error，
    总条数 ≤ 3。
    """
    _seed_failure(tmp_repo, "item_1", "Cookie 过期")
    _seed_failure(tmp_repo, "item_2", "Cookie 过期")
    _seed_failure(tmp_repo, "item_3", "网络超时")

    resp = client.get(
        "/api/evaluations/auto-collect-stats",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["failed"] == 3
    assert data["success"] == 0
    assert data["total"] == 3
    top = data["top_failures"]
    # 按计数降序：Cookie 过期(2) 应在 网络超时(1) 之前
    assert len(top) == 2
    assert top[0]["reason"] == "Cookie 过期"
    assert top[0]["count"] == 2
    assert top[1]["reason"] == "网络超时"
    assert top[1]["count"] == 1


def test_auto_collect_stats_top_failures_max_three(client: TestClient, tmp_repo: Repository) -> None:
    """top_failures 最多返回 3 条（即使有 4+ 种不同的 error）

    场景：4 条失败事件，4 种不同 error
    期望：top_failures 长度 ≤ 3（most_common(3) 截断）
    """
    _seed_failure(tmp_repo, "item_1", "错误A")
    _seed_failure(tmp_repo, "item_2", "错误B")
    _seed_failure(tmp_repo, "item_3", "错误C")
    _seed_failure(tmp_repo, "item_4", "错误D")

    resp = client.get(
        "/api/evaluations/auto-collect-stats",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["failed"] == 4
    assert len(data["top_failures"]) <= 3


def test_auto_collect_stats_range_filter(client: TestClient, tmp_repo: Repository) -> None:
    """range_hours 过滤：跨时间段事件被正确包含/排除

    场景：
    - 1 条成功事件 created_at=now（1h 内、6h 内、24h 内都在范围）
    - 1 条失败事件 created_at=now-2h（1h 外、6h 内、24h 内）
    - 1 条失败事件 created_at=now-50h（24h 外、168h 内）

    期望：
    - range_hours=1: total=1, success=1, failed=0
    - range_hours=6: total=2, success=1, failed=1
    - range_hours=24: total=2, success=1, failed=1（50h 失败事件被排除）
    - range_hours=168: total=3, success=1, failed=2
    """
    now = _utcnow()
    _seed_success(tmp_repo, "item_recent", created_at=now)
    _seed_failure(tmp_repo, "item_2h", "中等时长错误", created_at=now - timedelta(hours=2))
    _seed_failure(tmp_repo, "item_50h", "长期错误", created_at=now - timedelta(hours=50))

    # range_hours=1：仅 now 那条成功事件
    resp = client.get(
        "/api/evaluations/auto-collect-stats",
        params={"range_hours": 1},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["range_hours"] == 1
    assert data["total"] == 1
    assert data["success"] == 1
    assert data["failed"] == 0

    # range_hours=6：包含 2h 前的失败事件
    resp = client.get(
        "/api/evaluations/auto-collect-stats",
        params={"range_hours": 6},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["range_hours"] == 6
    assert data["total"] == 2
    assert data["success"] == 1
    assert data["failed"] == 1

    # range_hours=24：仍排除 50h 前的失败事件
    resp = client.get(
        "/api/evaluations/auto-collect-stats",
        params={"range_hours": 24},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["range_hours"] == 24
    assert data["total"] == 2
    assert data["failed"] == 1

    # range_hours=168：包含所有 3 条
    resp = client.get(
        "/api/evaluations/auto-collect-stats",
        params={"range_hours": 168},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["range_hours"] == 168
    assert data["total"] == 3
    assert data["success"] == 1
    assert data["failed"] == 2


def test_auto_collect_stats_invalid_range_hours_falls_back_to_24(
    client: TestClient, tmp_repo: Repository
) -> None:
    """非法 range_hours 回退到默认 24（与 /distribution 风格一致）

    白名单 {1, 6, 24, 168} 之外的值不应报错，应回退到 24。
    """
    resp = client.get(
        "/api/evaluations/auto-collect-stats",
        params={"range_hours": 48},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["range_hours"] == 24


def test_auto_collect_stats_excludes_non_official_success(client: TestClient, tmp_repo: Repository) -> None:
    """非 official 数据源的 eval.scored 不计入成功数

    场景：1 条 eval.scored 事件 payload.data_source='search'（非 official）
    期望：不计入 success（端点应只统计官方采集的成功），
    也不计入 failed（type 不是 collect.official.failed）。
    """
    repo = tmp_repo
    repo.upsert_eval_event({
        "type": "eval.scored",
        "task_id": "t1",
        "item_id": "item_search",
        "stage": "eval",
        "level": "info",
        "message": "商品 item_search 搜索结果评估分 80",
        "payload": json.dumps({
            "task_id": "t1",
            "item_id": "item_search",
            "score": 80,
            "data_source": "search",
        }, ensure_ascii=False),
    })

    resp = client.get(
        "/api/evaluations/auto-collect-stats",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 0
    assert data["success"] == 0
    assert data["failed"] == 0
