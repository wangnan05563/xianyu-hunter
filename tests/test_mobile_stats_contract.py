"""移动端 KPI 口径契约测试（T02588 / FR-G-1 + FR-G-2）

覆盖两条此前只在桌面侧成立的口径：

1. GET /api/stats 的 `metrics` 块：真实「发现商品数 / 评估通过数 / 通知失败数」。
   移动端 KPI 卡此前只能拿 tasks.total 冒充商品数、拿 evaluation_count 冒充「评估通过」、
   拿 orders.failed 冒充「通知失败」——本测试把三者的真实定义钉住，
   并显式断言「metrics ≠ 那几个被冒充的字段」，防止有人再把前端绑回去。
2. GET /api/orders/{id} 对 takeover_pending 订单附加 takeover_deadline / takeover_remaining_sec
   （此前只有列表端点附加，移动端详情页拿不到倒计时，只能显示一个静态「人工接管」标签）。
"""
from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import Settings
from xianyu_hunter.infra.db_models import TaskLinkRow, _utcnow
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.cache import invalidate_stats_cache
from xianyu_hunter.web.deps import get_container

_TEST_TOKEN = "test-token-mobile-stats"


@pytest.fixture
def tmp_repo() -> Repository:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        repo = Repository(str(Path(d) / "test.db"))
        yield repo
        repo.engine.dispose()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    test_settings = Settings(web_token=_TEST_TOKEN)

    def _fake_settings():
        return test_settings

    monkeypatch.setattr("xianyu_hunter.config.get_settings", _fake_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", _fake_settings, raising=False)

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo

            class _EmptyNotifierHub:
                notifiers = []

            self.notifier_hub = _EmptyNotifierHub()

            class _EmptyCollector:
                browser = None

            self.collector = _EmptyCollector()

    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    invalidate_stats_cache()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    invalidate_stats_cache()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


def _seed_task(repo: Repository, task_id: str) -> None:
    repo.upsert_task({
        "id": task_id, "name": f"任务-{task_id}", "keyword": "k", "cron": "*/1 * * * *",
        "use_cron": 0, "interval_seconds": 60.0, "mode": "confirm", "status": "running",
    })


def _seed_item_links(repo: Repository, task_id: str, keys: list[str]) -> None:
    """写 task_links（link_type='item'）——真实「发现商品数」的唯一来源"""
    with repo.engine.begin() as conn:
        for key in keys:
            conn.execute(TaskLinkRow.__table__.insert().values(
                task_id=task_id, link_type="item", link_key=key, source="auto",
            ))


# ============== 1. /api/stats metrics 块 ==============


def test_stats_metrics_are_real_counts_not_proxies(client: TestClient, tmp_repo: Repository) -> None:
    """metrics 三个字段取真实口径，且不等于此前被冒充的那几个字段"""
    _seed_task(tmp_repo, "t1")
    _seed_task(tmp_repo, "t2")
    # 2 个任务，但发现商品 3 个（含 1 个重复 link_key 去重 + 1 个 seller 关联不计入）
    _seed_item_links(tmp_repo, "t1", ["i1", "i2"])
    _seed_item_links(tmp_repo, "t2", ["i2", "i3"])
    with tmp_repo.engine.begin() as conn:
        conn.execute(TaskLinkRow.__table__.insert().values(
            task_id="t1", link_type="seller", link_key="s1", source="auto",
        ))
    # 4 条评估：2 条 low（通过）、1 条 mid、1 条 high
    tmp_repo.save_evaluation({"item_id": "i1", "score": 88, "risk_level": "low"})
    tmp_repo.save_evaluation({"item_id": "i2", "score": 70, "risk_level": "low"})
    tmp_repo.save_evaluation({"item_id": "i3", "score": 50, "risk_level": "mid"})
    tmp_repo.save_evaluation({"item_id": "i1", "score": 30, "risk_level": "high"})
    # 通知事件：2 成功 1 失败；另有 1 条非 notify 阶段的 error 不该算进通知失败
    tmp_repo.save_event({"type": "notify.sent", "task_id": "t1", "item_id": "i1",
                         "stage": "notify", "level": "info", "message": "ok", "payload": "{}"})
    tmp_repo.save_event({"type": "notify.sent", "task_id": "t1", "item_id": "i2",
                         "stage": "notify", "level": "info", "message": "ok", "payload": "{}"})
    tmp_repo.save_event({"type": "notify.failed", "task_id": "t1", "item_id": "i3",
                         "stage": "notify", "level": "err", "message": "推送失败", "payload": "{}"})
    tmp_repo.save_event({"type": "eval.failed", "task_id": "t1", "item_id": "i3",
                         "stage": "eval", "level": "err", "message": "评估异常", "payload": "{}"})
    # 订单失败 1 条：用来证明「通知失败」不再拿 orders.failed 冒充
    tmp_repo.upsert_order({"id": "o1", "task_id": "t1", "item_id": "i1",
                           "price": 10.0, "status": "failed"})

    data = client.get("/api/stats", headers=_auth_headers()).json()
    m = data["metrics"]
    assert m["items_discovered"] == 3, "发现商品数应为 DISTINCT item 关联数（3），不是任务数（2）"
    assert m["eval_pass"] == 2, "评估通过数应为 risk_level='low' 的条数（2），不是评估总数（4）"
    assert m["notify_failed"] == 1, "通知失败数应为 stage=notify 且 level=err（1），不是订单失败数（1 巧合）"
    # 显式钉住「不等于被冒充字段」——orders.failed 恰好也是 1，改用不等式会误判，
    # 因此这里断言字段存在且与 tasks.total / evaluation_count 不同源
    assert m["items_discovered"] != data["tasks"]["total"]
    assert m["eval_pass"] != data["evaluation_count"]
    assert "notify_failed" in m


def test_stats_metrics_empty_repo(client: TestClient) -> None:
    """空库：metrics 三个字段为 0（真的没有，而不是缺字段）"""
    data = client.get("/api/stats", headers=_auth_headers()).json()
    assert data["metrics"] == {"items_discovered": 0, "eval_pass": 0, "notify_failed": 0}


# ============== 2. 订单详情端点的接管倒计时字段 ==============


def _seed_takeover_order(repo: Repository, order_id: str, *, status: str = "takeover_pending") -> None:
    now = _utcnow()
    # confirmed_at 必须是 datetime：SQLite DateTime 列不接受 ISO 字符串
    # （_parse_takeover_ts 之所以还兼容字符串，是因为历史库里存在文本形态的旧数据）
    repo.upsert_order({
        "id": order_id, "task_id": "t1", "item_id": "i1", "price": 99.0,
        "status": status,
        "confirmed_at": now - timedelta(minutes=5),
    })


def test_order_detail_attaches_takeover_deadline(client: TestClient, tmp_repo: Repository) -> None:
    """详情端点补齐倒计时字段（FR-G-2）：takeover_pending 订单返回 deadline + 剩余秒"""
    _seed_takeover_order(tmp_repo, "ot1")
    data = client.get("/api/orders/ot1", headers=_auth_headers()).json()
    assert data["takeover_deadline"], "takeover_pending 详情应带 takeover_deadline"
    # confirmed_at 5 分钟前，默认 30 分钟窗口 → 剩约 25 分钟
    assert 1000 < data["takeover_remaining_sec"] <= 1500, data["takeover_remaining_sec"]


def test_order_detail_other_status_has_no_deadline(client: TestClient, tmp_repo: Repository) -> None:
    """非 takeover_pending 订单不应被塞倒计时（前端按 status 判定显示，避免幽灵字段）"""
    _seed_takeover_order(tmp_repo, "ok1", status="succeeded")
    data = client.get("/api/orders/ok1", headers=_auth_headers()).json()
    assert "takeover_deadline" not in data
    assert "takeover_remaining_sec" not in data
