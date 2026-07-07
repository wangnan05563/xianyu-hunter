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


def _seed_task(
    repo: Repository, task_id: str, *,
    min_price: float | None = None,
    max_price: float | None = None,
    price_config: dict | None = None,
) -> None:
    task_data: dict = {
        "id": task_id,
        "name": f"任务-{task_id}",
        "keyword": "测试关键词",
        "min_price": min_price,
        "max_price": max_price,
        "status": "running",
    }
    if price_config is not None:
        task_data["price_config"] = json.dumps(price_config)
    repo.upsert_task(task_data)


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


# ============== distribution 与评估列表过滤口径一致 ==============


def test_distribution_filters_by_task_id_and_task_price_range(
    client: TestClient, tmp_repo: Repository
) -> None:
    """distribution 统计应与当前任务评估列表一致，排除其他任务和任务价格范围外样本"""
    _seed_task(tmp_repo, "t1", min_price=100, max_price=1000)
    _seed_task(tmp_repo, "t2", min_price=100, max_price=10000)
    _seed_eval_event(tmp_repo, "item_t1_low", 50.0, task_id="t1", score=70)
    _seed_eval_event(tmp_repo, "item_t1_ok_200", 200.0, task_id="t1", score=75)
    _seed_eval_event(tmp_repo, "item_t1_ok_800", 800.0, task_id="t1", score=85)
    _seed_eval_event(tmp_repo, "item_t1_high", 5000.0, task_id="t1", score=90)
    _seed_eval_event(tmp_repo, "item_t2_other", 3000.0, task_id="t2", score=95)

    resp = client.get(
        "/api/evaluations/distribution",
        params={"task_id": "t1", "range_hours": 168},
        headers=_auth_headers(),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["price_range"] == [200.0, 800.0]
    assert data["marginals"]["result"]["fail"] == 0
    assert data["marginals"]["result"]["pass"] == 1
    assert data["marginals"]["result"]["auto"] == 1


def test_distribution_include_out_of_range_disables_task_price_filter(
    client: TestClient, tmp_repo: Repository
) -> None:
    """include_out_of_range=True 时 distribution 仍限定任务，但保留任务价格范围外样本"""
    _seed_task(tmp_repo, "t1", min_price=100, max_price=1000)
    _seed_task(tmp_repo, "t2", min_price=100, max_price=10000)
    _seed_eval_event(tmp_repo, "item_t1_low", 50.0, task_id="t1", score=70)
    _seed_eval_event(tmp_repo, "item_t1_ok", 500.0, task_id="t1", score=75)
    _seed_eval_event(tmp_repo, "item_t1_high", 5000.0, task_id="t1", score=90)
    _seed_eval_event(tmp_repo, "item_t2_other", 3000.0, task_id="t2", score=95)

    resp = client.get(
        "/api/evaluations/distribution",
        params={"task_id": "t1", "range_hours": 168, "include_out_of_range": True},
        headers=_auth_headers(),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["price_range"] == [50.0, 5000.0]


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


# ============== list_evaluations 低于市场参考价（market_ratio）过滤 ==============


def test_market_ratio_filters_items_above_median_times_ratio(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """market_ratio=0.85 时，价格 > 中位数 × 0.85 的商品被过滤

    场景：5 个商品价格 [100, 200, 300, 400, 1000]
    中位数 = 300，阈值 = 300 × 0.85 = 255
    应保留 100/200，过滤 300/400/1000
    """
    _seed_task(tmp_repo, "t1", price_config={"market_ratio": 0.85})
    _seed_eval_event(tmp_repo, "item_100", 100.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_200", 200.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_300", 300.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_400", 400.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_1000", 1000.0, task_id="t1")

    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    assert item_ids == {"item_100", "item_200"}, \
        f"market_ratio=0.85 应只保留 ≤255 的商品，但得到 {item_ids}"


def test_market_ratio_skipped_when_sample_size_less_than_three(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """样本数 < 3 时跳过 market_ratio 过滤（中位数不稳定）"""
    _seed_task(tmp_repo, "t1", price_config={"market_ratio": 0.85})
    _seed_eval_event(tmp_repo, "item_100", 100.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_1000", 1000.0, task_id="t1")

    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    # 样本不足，不应过滤任何商品
    assert item_ids == {"item_100", "item_1000"}


def test_market_ratio_skipped_when_no_task_id(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """未传 task_id 时不应用 market_ratio 过滤（无市场参考上下文）"""
    _seed_task(tmp_repo, "t1", price_config={"market_ratio": 0.85})
    _seed_eval_event(tmp_repo, "item_100", 100.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_1000", 1000.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_2000", 2000.0, task_id="t1")

    # 不传 task_id
    resp = client.get(
        "/api/evaluations",
        params={},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    # 无 task_id 不应用 market_ratio，应全部返回
    assert item_ids == {"item_100", "item_1000", "item_2000"}


def test_market_ratio_skipped_when_include_out_of_range_true(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """include_out_of_range=True 时跳过 market_ratio 过滤（审计场景需要完整历史）"""
    _seed_task(tmp_repo, "t1", price_config={"market_ratio": 0.85})
    _seed_eval_event(tmp_repo, "item_100", 100.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_200", 200.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_300", 300.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_400", 400.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_1000", 1000.0, task_id="t1")

    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1", "include_out_of_range": True},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    # 审计场景：不过滤任何商品
    assert item_ids == {"item_100", "item_200", "item_300", "item_400", "item_1000"}


def test_market_ratio_skipped_when_task_not_configured(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """任务未配置 market_ratio 且全局默认 None 时，不应用过滤"""
    # _FakeContainer.price_strategy = PriceStrategy(PriceConfig())  # market_ratio=None
    _seed_task(tmp_repo, "t1")  # 不传 price_config
    _seed_eval_event(tmp_repo, "item_100", 100.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_1000", 1000.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_2000", 2000.0, task_id="t1")

    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    # 未配置 market_ratio，应全部返回
    assert item_ids == {"item_100", "item_1000", "item_2000"}


def test_market_ratio_combined_with_explicit_max_price(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """market_ratio 与显式 max_price 共存时，两个过滤叠加生效

    场景：market_ratio=0.85，max_price=500
    商品价格 [100, 200, 300, 400, 1000]
    中位数 = 300，market_ratio 阈值 = 255
    max_price 阈值 = 500
    应保留 100/200，过滤 300/400/1000
    """
    _seed_task(tmp_repo, "t1", price_config={"market_ratio": 0.85})
    _seed_eval_event(tmp_repo, "item_100", 100.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_200", 200.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_300", 300.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_400", 400.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_1000", 1000.0, task_id="t1")

    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1", "max_price": 500},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    # max_price=500 不过滤 400，但 market_ratio 过滤 300/400
    assert item_ids == {"item_100", "item_200"}


def test_market_ratio_above_one_skipped(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """market_ratio >= 1.0 时不应用过滤（与 PriceStrategy.check 一致）"""
    _seed_task(tmp_repo, "t1", price_config={"market_ratio": 1.0})
    _seed_eval_event(tmp_repo, "item_100", 100.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_1000", 1000.0, task_id="t1")
    _seed_eval_event(tmp_repo, "item_2000", 2000.0, task_id="t1")

    resp = client.get(
        "/api/evaluations",
        params={"task_id": "t1"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    item_ids = {item["payload"]["item_id"] for item in data["items"]}
    # market_ratio=1.0 不应用过滤
    assert item_ids == {"item_100", "item_1000", "item_2000"}
