"""P3 async 化改造回归测试

覆盖 4 个 stats 接口的 async def + asyncio.gather/to_thread 改造：
- GET /api/stats              (stats_overview.py) 4 查询并发
- GET /api/stats/business-kpi (business_kpi.py)   4 KPI 并发
- GET /api/stats/today        (stats_today.py)    5 查询并发
- GET /api/stats/trend        (trend.py)          DB 卸载到线程池

测试目标：
1. async 改造后接口仍返回正确数据（无回归）
2. asyncio.gather 并发查询结果与串行一致
3. 60s TTL 缓存命中/失效行为正常
4. SQLite WAL 多 connection 并发读不报错

设计参考：tests/test_auto_collect_stats_endpoint.py（tempfile + TestClient + dependency_overrides）
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
from xianyu_hunter.web.cache import invalidate_stats_cache
from xianyu_hunter.web.deps import get_container

_TEST_TOKEN = "test-token-stats-async-p3"


@pytest.fixture
def tmp_repo() -> Repository:
    """使用临时数据库，避免污染真实数据"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
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
            # business_kpi 的 _warn_if_no_notify_events 会访问 notifier_hub.notifiers
            class _EmptyNotifierHub:
                notifiers = []
            self.notifier_hub = _EmptyNotifierHub()
            # stats_today 的 _get_browser_dir 会访问 collector.browser
            class _EmptyCollector:
                browser = None
            self.collector = _EmptyCollector()

    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    # 每个测试前清空缓存，避免上一轮缓存污染断言
    invalidate_stats_cache()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    invalidate_stats_cache()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


# ============== 数据写入辅助函数 ==============


def _seed_task(repo: Repository, task_id: str, status: str = "running") -> None:
    repo.upsert_task({
        "id": task_id,
        "name": f"任务-{task_id}",
        "keyword": "测试关键词",
        "cron": "*/1 * * * *",
        "use_cron": 0,
        "interval_seconds": 60.0,
        "mode": "confirm",
        "status": status,
    })


def _seed_order(repo: Repository, order_id: str, status: str, *, created_at=None) -> None:
    order = {
        "id": order_id,
        "task_id": "t1",
        "item_id": f"item_{order_id}",
        "price": 100.0,
        "status": status,
    }
    if created_at is not None:
        order["created_at"] = created_at
    repo.upsert_order(order)


def _seed_eval(repo: Repository, item_id: str, *, score: int = 80, risk_level: str = "low", created_at=None) -> None:
    """写入 eval.scored 事件到 events 表（用于 stats_today 的低分过滤和 trend 的 eval_score 指标）

    注意：此方法只写 events 表，不写 evaluations 表。
    - stats_overview 的 evaluation_count 来自 evaluations 表，需另调 _seed_evaluation
    - business_kpi 的 KPI2 来自 evaluations 表，需另调 _seed_evaluation
    """
    event = {
        "type": "eval.scored",
        "task_id": "t1",
        "item_id": item_id,
        "stage": "eval",
        "level": "info",
        "message": f"商品 {item_id} 评估分 {score}",
        "payload": json.dumps({"score": score, "risk_level": risk_level}, ensure_ascii=False),
    }
    if created_at is not None:
        event["created_at"] = created_at
    repo.upsert_eval_event(event)


def _seed_evaluation(repo: Repository, item_id: str, *, score: int = 80, risk_level: str = "low", created_at=None) -> None:
    """写入评估记录到 evaluations 表（用于 stats_overview 的 evaluation_count 和 business_kpi 的 KPI2）

    与 _seed_eval 区别：_seed_eval 写 events 表，_seed_evaluation 写 evaluations 表。
    生产环境中 evaluator 会同时写两张表，测试中按需分别调用。
    """
    eval_data = {
        "item_id": item_id,
        "score": score,
        "risk_level": risk_level,
    }
    if created_at is not None:
        eval_data["created_at"] = created_at
    repo.save_evaluation(eval_data)


def _seed_event(repo: Repository, *, stage: str = "search", level: str = "info", created_at=None) -> None:
    event = {
        "type": "system.info",
        "task_id": "t1",
        "item_id": None,
        "stage": stage,
        "level": level,
        "message": f"{stage} 事件",
        "payload": "{}",
    }
    if created_at is not None:
        event["created_at"] = created_at
    repo.save_event(event)


# ============== 1. GET /api/stats (overview) 测试 ==============


def test_stats_overview_empty(client: TestClient) -> None:
    """空数据：4 个查询并发返回 0，不报错

    验证 asyncio.gather 在空表场景下能正常完成所有 4 个 to_thread 任务。
    """
    resp = client.get("/api/stats", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tasks"] == {"total": 0, "running": 0, "paused": 0, "stopped": 0}
    assert data["orders"] == {"total": 0, "succeeded": 0, "failed": 0, "pending": 0}
    assert data["events"]["total"] == 0
    assert data["evaluation_count"] == 0


def test_stats_overview_with_data(client: TestClient, tmp_repo: Repository) -> None:
    """有数据：4 个 CASE WHEN 聚合并发执行，状态计数正确

    场景：2 running + 1 paused + 1 stopped 任务；2 succeeded + 1 failed + 1 pending 订单；
    3 事件；2 评估记录。
    验证 asyncio.gather 拿到的 4 个独立 connection 查询结果与串行一致。
    """
    _seed_task(tmp_repo, "t1", "running")
    _seed_task(tmp_repo, "t2", "running")
    _seed_task(tmp_repo, "t3", "paused")
    _seed_task(tmp_repo, "t4", "stopped")
    _seed_order(tmp_repo, "o1", "succeeded")
    _seed_order(tmp_repo, "o2", "succeeded")
    _seed_order(tmp_repo, "o3", "failed")
    _seed_order(tmp_repo, "o4", "pending")
    _seed_event(tmp_repo, stage="search")
    _seed_event(tmp_repo, stage="notify")
    _seed_event(tmp_repo, stage="eval")
    # evaluations 表单独写入（evaluation_count 来自 evaluations 表，非 events 表）
    _seed_evaluation(tmp_repo, "item_1")
    _seed_evaluation(tmp_repo, "item_2")

    resp = client.get("/api/stats", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tasks"] == {"total": 4, "running": 2, "paused": 1, "stopped": 1}
    assert data["orders"] == {"total": 4, "succeeded": 2, "failed": 1, "pending": 1}
    assert data["events"]["total"] == 3
    assert data["evaluation_count"] == 2


def test_stats_overview_excludes_deleted_tasks(client: TestClient, tmp_repo: Repository) -> None:
    """status='deleted' 的软删除任务不计入统计（WHERE status != 'deleted'）"""
    _seed_task(tmp_repo, "t1", "running")
    _seed_task(tmp_repo, "t2", "deleted")

    resp = client.get("/api/stats", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tasks"]["total"] == 1
    assert data["tasks"]["running"] == 1


# ============== 2. GET /api/stats/business-kpi 测试 ==============


def test_business_kpi_empty(client: TestClient) -> None:
    """空数据：4 个 KPI 并发查询返回 0/0%，不报错"""
    resp = client.get("/api/stats/business-kpi", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["range_days"] == 30
    kpis = {k["id"]: k for k in data["kpis"]}
    assert kpis["items_discovered"]["value"] == 0
    assert kpis["eval_pass_rate"]["value"] == 0.0
    assert kpis["order_success_rate"]["value"] == 0.0
    assert kpis["notify_failure_rate"]["value"] == 0.0


def test_business_kpi_with_data(client: TestClient, tmp_repo: Repository) -> None:
    """有数据：4 个 KPI 并发查询，每个独立 connection 计算正确"""
    now = _utcnow()
    # KPI2: 2 评估记录（risk_level=low） → pass_rate = 100%
    # 注意：KPI2 查询 evaluations 表，需用 save_evaluation 写入
    _seed_evaluation(tmp_repo, "item_1", score=80, risk_level="low", created_at=now)
    _seed_evaluation(tmp_repo, "item_2", score=60, risk_level="low", created_at=now)
    # KPI3: 1 succeeded + 1 total → 100%
    _seed_order(tmp_repo, "o1", "succeeded", created_at=now)
    # KPI4: 1 notify 失败 + 1 notify 总数 → 100%
    _seed_event(tmp_repo, stage="notify", level="err", created_at=now)

    resp = client.get("/api/stats/business-kpi", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    kpis = {k["id"]: k for k in data["kpis"]}
    # eval_pass_rate: 2 low / 2 total = 100%
    assert kpis["eval_pass_rate"]["value"] == 100.0
    assert kpis["eval_pass_rate"]["sample_size"] == 2
    # order_success_rate: 1 succeeded / 1 total = 100%
    assert kpis["order_success_rate"]["value"] == 100.0
    # notify_failure_rate: 1 err / 1 notify = 100%
    assert kpis["notify_failure_rate"]["value"] == 100.0


# ============== 3. GET /api/stats/today 测试 ==============


def test_stats_today_empty(client: TestClient) -> None:
    """空数据：5 个查询并发返回 0，不报错"""
    resp = client.get("/api/stats/today", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["today"] == {"orders": 0, "events": 0, "succeeded": 0, "failed": 0}
    assert data["alerts"]["counts"] == {"failed": 0, "timeout": 0, "low_eval": 0}
    assert data["alerts"]["failed_orders"] == []
    assert data["alerts"]["timeout_pending"] == []
    assert data["alerts"]["low_evaluations"] == []


def test_stats_today_with_data(client: TestClient, tmp_repo: Repository) -> None:
    """有数据：5 个查询并发执行，今日统计与异常列表正确"""
    now = _utcnow()
    # 2 succeeded + 1 failed 订单（今日）
    _seed_order(tmp_repo, "o1", "succeeded", created_at=now)
    _seed_order(tmp_repo, "o2", "succeeded", created_at=now)
    _seed_order(tmp_repo, "o3", "failed", created_at=now)
    # 3 事件（今日）+ 1 eval.scored 事件 = 4 事件
    _seed_event(tmp_repo, stage="search", created_at=now)
    _seed_event(tmp_repo, stage="notify", created_at=now)
    _seed_event(tmp_repo, stage="eval", created_at=now)
    # 1 低分评估：score=0 → score_value=0.0 < 0.5，计入 low_eval
    # 注意：_sync_score_value 直接 float(score)，不除以 100
    _seed_eval(tmp_repo, "item_low", score=0, risk_level="high", created_at=now)

    resp = client.get("/api/stats/today", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["today"]["orders"] == 3
    assert data["today"]["succeeded"] == 2
    assert data["today"]["failed"] == 1
    # 3 system events + 1 eval.scored event = 4
    assert data["today"]["events"] == 4
    # 低分评估：score=0 → score_value=0.0 < 0.5，计入 low_eval
    assert data["alerts"]["counts"]["low_eval"] == 1
    assert len(data["alerts"]["failed_orders"]) == 1


# ============== 4. GET /api/stats/trend 测试 ==============


def test_stats_trend_empty(client: TestClient) -> None:
    """空数据：DB 查询卸载到线程池，返回空 series"""
    resp = client.get("/api/stats/trend", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["metric"] == "events"
    assert data["range_hours"] == 24
    assert len(data["series"]) == 24  # 24 个时间桶
    assert all(s["value"] == 0.0 for s in data["series"])
    assert data["summary"]["min"] == 0
    assert data["summary"]["max"] == 0


def test_stats_trend_with_events(client: TestClient, tmp_repo: Repository) -> None:
    """有数据：events metric 返回非零 series"""
    now = _utcnow()
    _seed_event(tmp_repo, stage="search", created_at=now)
    _seed_event(tmp_repo, stage="notify", created_at=now)

    resp = client.get("/api/stats/trend", params={"metric": "events"}, headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 24h 内有 2 个事件，应分布在前几个桶
    total_count = sum(s["count"] for s in data["series"])
    assert total_count == 2


def test_stats_trend_orders_metric(client: TestClient, tmp_repo: Repository) -> None:
    """orders metric：查询 orders 表并返回非零 series"""
    now = _utcnow()
    _seed_order(tmp_repo, "o1", "succeeded", created_at=now)

    resp = client.get("/api/stats/trend", params={"metric": "orders"}, headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["metric"] == "orders"
    total_count = sum(s["count"] for s in data["series"])
    assert total_count == 1


def test_stats_trend_invalid_range_falls_back(client: TestClient) -> None:
    """非法 range_hours 回退到 24"""
    resp = client.get("/api/stats/trend", params={"range_hours": 48}, headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["range_hours"] == 24


# ============== 5. 缓存行为测试 ==============


def test_cache_hit_on_second_request(client: TestClient, tmp_repo: Repository) -> None:
    """60s TTL 缓存：第二次请求命中缓存，返回相同数据

    验证 async cached_ttl 装饰器在 asyncio.gather 场景下正确缓存。
    """
    _seed_task(tmp_repo, "t1", "running")
    _seed_order(tmp_repo, "o1", "succeeded")

    resp1 = client.get("/api/stats", headers=_auth_headers())
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["tasks"]["total"] == 1

    # 在缓存写入后再插入数据，第二次请求应命中缓存返回旧值
    _seed_task(tmp_repo, "t2", "paused")
    resp2 = client.get("/api/stats", headers=_auth_headers())
    assert resp2.status_code == 200
    data2 = resp2.json()
    # 缓存命中：仍是 1 个任务（不含 t2）
    assert data2["tasks"]["total"] == 1
    assert data2["ts"] == data1["ts"]  # ts 相同证明是缓存值


def test_cache_bypass_refreshes(client: TestClient, tmp_repo: Repository) -> None:
    """bypass_cache=True 强制刷新缓存，返回最新数据"""
    _seed_task(tmp_repo, "t1", "running")
    resp1 = client.get("/api/stats", headers=_auth_headers())
    data1 = resp1.json()
    assert data1["tasks"]["total"] == 1

    _seed_task(tmp_repo, "t2", "paused")
    # bypass_cache 通过 query param 不支持，需要直接调用被装饰函数
    # 这里通过 invalidate_stats_cache 清空缓存模拟强制刷新
    invalidate_stats_cache()
    resp2 = client.get("/api/stats", headers=_auth_headers())
    data2 = resp2.json()
    assert data2["tasks"]["total"] == 2
