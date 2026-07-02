"""评估明细菜单价格范围过滤测试

修复前：list_evaluations 完全不支持价格范围过滤，导致评估明细菜单显示
大量超出任务价格范围区间的商品。
修复后：
1. 显式 min_price/max_price 参数过滤
2. 传 task_id 但未传价格参数时，自动从 task 表读取 min_price/max_price
3. include_out_of_range=True 时跳过价格过滤（审计历史超范围商品）
4. recompute / batch_evaluate / collection_service 三条写入路径增加
   PriceStrategy.check 门禁，超范围商品不写入 eval.scored 事件
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import Settings
from xianyu_hunter.container import Container
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.modules.price_strategy import PriceConfig, PriceStrategy
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-evaluations-price-filter"


@pytest.fixture
def tmp_repo() -> Repository:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
        repo.engine.dispose()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    test_settings = Settings(web_token=_TEST_TOKEN)

    def _fake_settings():
        return test_settings

    monkeypatch.setattr("xianyu_hunter.config.get_settings", _fake_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", _fake_settings, raising=False)

    # 构造 fake container：注入任务级 price_strategy 构造方法
    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo
            self.evaluator = SimpleNamespace(evaluate=lambda detail, seller: SimpleNamespace(
                score=75,
                risk_level=SimpleNamespace(value="medium"),
                dimension_scores={},
                reject_reasons=[],
                is_passed=True,
                data_quality="ok",
            ))
            # 全局 price_strategy：无规则（task 未配置价格范围时用）
            self.price_strategy = PriceStrategy(PriceConfig())

        def build_task_price_strategy(self, raw: dict) -> PriceStrategy:
            """复用 Container 的真实方法逻辑，确保测试与生产行为一致"""
            return Container.build_task_price_strategy(self, raw)

    fake = _FakeContainer(tmp_repo)
    # build_task_price_strategy 是 Container 的实例方法，需要绑定到 fake
    fake.build_task_price_strategy = lambda raw: Container.build_task_price_strategy(fake, raw)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


def _seed_task(repo: Repository, task_id: str, *, min_price: float | None = None, max_price: float | None = None) -> None:
    repo.upsert_task({
        "id": task_id,
        "name": f"任务-{task_id}",
        "keyword": "测试关键词",
        "min_price": min_price,
        "max_price": max_price,
        "status": "running",
    })


def _seed_eval_event(repo: Repository, item_id: str, price: float, *, task_id: str = "t1", score: int = 75) -> None:
    """写入 eval.scored 事件，模拟评估时写入的历史快照"""
    repo.upsert_eval_event({
        "type": "eval.scored",
        "task_id": task_id,
        "item_id": item_id,
        "stage": "eval",
        "level": "info",
        "message": f"商品 {item_id} 评估分 {score}",
        "payload": json.dumps({
            "task_id": task_id,
            "item_id": item_id,
            "item_title": f"商品-{item_id}",
            "item_price": price,
            "score": score,
            "is_passed": True,
        }, ensure_ascii=False),
    })


# ============== list_evaluations 价格范围过滤 ==============


def test_explicit_min_price_filters_out_low_price_items(client: TestClient, tmp_repo: Repository) -> None:
    """显式 min_price 参数应过滤掉低于下限的商品"""
    _seed_task(tmp_repo, "t1")
    _seed_eval_event(tmp_repo, "item_cheap", 50.0)
    _seed_eval_event(tmp_repo, "item_ok", 200.0)

    resp = client.get(
        "/api/evaluations",
        params={"min_price": 100},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    assert item_ids == {"item_ok"}, f"min_price=100 应过滤掉 50 元商品，但得到 {item_ids}"


def test_explicit_max_price_filters_out_high_price_items(client: TestClient, tmp_repo: Repository) -> None:
    """显式 max_price 参数应过滤掉高于上限的商品"""
    _seed_task(tmp_repo, "t1")
    _seed_eval_event(tmp_repo, "item_ok", 200.0)
    _seed_eval_event(tmp_repo, "item_expensive", 5000.0)

    resp = client.get(
        "/api/evaluations",
        params={"max_price": 1000},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    assert item_ids == {"item_ok"}, f"max_price=1000 应过滤掉 5000 元商品，但得到 {item_ids}"


def test_task_id_auto_reads_price_range_from_task_config(client: TestClient, tmp_repo: Repository) -> None:
    """传 task_id 但未传 min_price/max_price 时，自动从 task 表读取价格范围"""
    _seed_task(tmp_repo, "t1", min_price=100, max_price=1000)
    _seed_eval_event(tmp_repo, "item_cheap", 50.0, task_id="t1")     # 低于下限
    _seed_eval_event(tmp_repo, "item_ok", 500.0, task_id="t1")       # 在范围内
    _seed_eval_event(tmp_repo, "item_expensive", 5000.0, task_id="t1")  # 高于上限

    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    assert item_ids == {"item_ok"}, \
        f"task_id=t1（min=100,max=1000）应只返回 500 元商品，但得到 {item_ids}"


def test_explicit_price_overrides_task_config(client: TestClient, tmp_repo: Repository) -> None:
    """用户显式传入的 min_price/max_price 优先于 task 配置"""
    _seed_task(tmp_repo, "t1", min_price=100, max_price=1000)
    _seed_eval_event(tmp_repo, "item_low", 150.0, task_id="t1")   # 在 task 范围内但低于用户指定下限
    _seed_eval_event(tmp_repo, "item_ok", 500.0, task_id="t1")

    # 用户显式传 min_price=300，覆盖 task 的 min_price=100
    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1", "min_price": 300},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    assert item_ids == {"item_ok"}, \
        f"用户显式 min_price=300 应覆盖 task 的 100，但得到 {item_ids}"


def test_include_out_of_range_disables_price_filter(client: TestClient, tmp_repo: Repository) -> None:
    """include_out_of_range=True 时跳过价格过滤，显示所有商品（审计用）"""
    _seed_task(tmp_repo, "t1", min_price=100, max_price=1000)
    _seed_eval_event(tmp_repo, "item_cheap", 50.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_ok", 500.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_expensive", 5000.0, task_id="t1")

    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1", "include_out_of_range": True},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    assert item_ids == {"item_cheap", "item_ok", "item_expensive"}, \
        f"include_out_of_range=True 应显示所有商品，但得到 {item_ids}"


def test_no_task_id_no_price_filter(client: TestClient, tmp_repo: Repository) -> None:
    """未传 task_id 且未传 min_price/max_price 时，不应用价格过滤"""
    _seed_task(tmp_repo, "t1")
    _seed_eval_event(tmp_repo, "item_cheap", 50.0)
    _seed_eval_event(tmp_repo, "item_expensive", 5000.0)

    resp = client.get("/api/evaluations", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    assert item_ids == {"item_cheap", "item_expensive"}, \
        f"无 task_id 无价格参数时应显示所有商品，但得到 {item_ids}"


def test_task_without_price_config_no_filter(client: TestClient, tmp_repo: Repository) -> None:
    """task 未配置 min_price/max_price 时，传 task_id 也不应用价格过滤"""
    _seed_task(tmp_repo, "t1", min_price=None, max_price=None)
    _seed_eval_event(tmp_repo, "item_cheap", 50.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_expensive", 5000.0, task_id="t1")

    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    assert item_ids == {"item_cheap", "item_expensive"}, \
        f"task 无价格配置时不应过滤，但得到 {item_ids}"


def test_price_none_not_filtered(client: TestClient, tmp_repo: Repository) -> None:
    """payload.item_price 为 None 时不应被价格过滤（评估时可能未采集到价格）"""
    _seed_task(tmp_repo, "t1", min_price=100, max_price=1000)
    # 手动写入一个 price=None 的评估事件
    tmp_repo.upsert_eval_event({
        "type": "eval.scored",
        "task_id": "t1",
        "item_id": "item_no_price",
        "stage": "eval",
        "level": "info",
        "message": "商品 item_no_price 评估分 75",
        "payload": json.dumps({
            "task_id": "t1",
            "item_id": "item_no_price",
            "item_price": None,
            "score": 75,
            "is_passed": True,
        }, ensure_ascii=False),
    })
    _seed_eval_event(tmp_repo, "item_ok", 500.0, task_id="t1")

    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    # price=None 的商品应保留（避免误删）
    assert "item_no_price" in item_ids, \
        f"price=None 的商品不应被过滤，但得到 {item_ids}"
    assert "item_ok" in item_ids


# ============== build_task_price_strategy 公共方法 ==============


def test_build_task_price_strategy_uses_task_min_max():
    """task.min_price/max_price 列优先"""
    from xianyu_hunter.infra.yaml_config import AppConfig, PriceStrategyConfig

    cfg = AppConfig(price_strategy=PriceStrategyConfig())
    container = Container.__new__(Container)
    container.config = cfg
    container.price_strategy = PriceStrategy(PriceConfig())

    raw = {"min_price": 100.0, "max_price": 1000.0, "price_config": None}
    ps = container.build_task_price_strategy(raw)
    assert ps.config.min_price == 100.0
    assert ps.config.max_price == 1000.0


def test_build_task_price_strategy_falls_back_to_price_config_json():
    """task.min_price/max_price 为 None 时，从 price_config JSON 中取"""
    from xianyu_hunter.infra.yaml_config import AppConfig, PriceStrategyConfig

    cfg = AppConfig(price_strategy=PriceStrategyConfig())
    container = Container.__new__(Container)
    container.config = cfg
    container.price_strategy = PriceStrategy(PriceConfig())

    raw = {
        "min_price": None,
        "max_price": None,
        "price_config": json.dumps({"min_price": 200, "max_price": 800}),
    }
    ps = container.build_task_price_strategy(raw)
    assert ps.config.min_price == 200
    assert ps.config.max_price == 800


def test_build_task_price_strategy_returns_global_when_no_config():
    """task 无任何价格配置时，返回全局 price_strategy"""
    from xianyu_hunter.infra.yaml_config import AppConfig, PriceStrategyConfig

    global_ps = PriceStrategy(PriceConfig(market_ratio=0.8))
    cfg = AppConfig(price_strategy=PriceStrategyConfig())
    container = Container.__new__(Container)
    container.config = cfg
    container.price_strategy = global_ps

    raw = {"min_price": None, "max_price": None, "price_config": None}
    ps = container.build_task_price_strategy(raw)
    assert ps is global_ps
