"""P1-6 价格行情看板增强 API 单元测试"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-for-price-dashboard"


@pytest.fixture
def tmp_repo() -> Repository:
    """使用临时数据库"""
    import tempfile
    from pathlib import Path
    get_settings.cache_clear()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
        repo.engine.dispose()
        get_settings.cache_clear()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    """构造 TestClient，注入临时 repository 和测试 token"""
    from xianyu_hunter.config import Settings
    test_settings = Settings(web_token=_TEST_TOKEN)
    monkeypatch.setattr(
        "xianyu_hunter.config.get_settings",
        lambda: test_settings,
    )
    monkeypatch.setattr(
        "xianyu_hunter.web.app.get_settings",
        lambda: test_settings,
        raising=False,
    )

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo
    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


def _seed_multi_category_data(repo: Repository) -> None:
    """填充多品类测试数据：3 个任务 + 多个商品"""
    now = datetime.now(timezone.utc)
    # 任务 1：iPhone（高价品类）
    repo.upsert_task({
        "id": "t1", "name": "iPhone 任务", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    # 任务 2：键盘（中价品类）
    repo.upsert_task({
        "id": "t2", "name": "键盘任务", "keyword": "keyboard",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    # 任务 3：手机壳（低价品类）
    repo.upsert_task({
        "id": "t3", "name": "手机壳任务", "keyword": "case",
        "mode": "confirm", "cron": "*/5 * * * *",
    })

    items = []
    # iPhone 品类：5 个商品
    for i, price in enumerate([3999.0, 4999.0, 4499.0, 5299.0, 3799.0]):
        items.append({
            "id": f"iphone_{i}", "task_id": "t1", "title": f"iPhone {i}",
            "price": price, "seller_id": f"s_iphone_{i}",
            "first_seen": now - timedelta(days=i),
            "publish_time": now - timedelta(days=i),
        })
    # 键盘品类：4 个商品
    for i, price in enumerate([299.0, 399.0, 499.0, 599.0]):
        items.append({
            "id": f"kb_{i}", "task_id": "t2", "title": f"Keyboard {i}",
            "price": price, "seller_id": f"s_kb_{i}",
            "first_seen": now - timedelta(days=i),
            "publish_time": now - timedelta(days=i),
        })
    # 手机壳品类：3 个商品
    for i, price in enumerate([19.9, 29.9, 39.9]):
        items.append({
            "id": f"case_{i}", "task_id": "t3", "title": f"Case {i}",
            "price": price, "seller_id": f"s_case_{i}",
            "first_seen": now - timedelta(days=i),
            "publish_time": now - timedelta(days=i),
        })
    repo.batch_upsert_items(items)


def test_category_stats_all(client: TestClient, tmp_repo: Repository) -> None:
    """全品类价格统计：返回所有品类的统计指标"""
    _seed_multi_category_data(tmp_repo)
    resp = client.get("/api/prices/category-stats", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert "total_count" in data
    # 3 个品类
    assert len(data["categories"]) == 3
    # 总样本数 = 5 + 4 + 3 = 12
    assert data["total_count"] == 12
    # 按样本数降序排列
    counts = [c["count"] for c in data["categories"]]
    assert counts == sorted(counts, reverse=True)


def test_category_stats_single_task(client: TestClient, tmp_repo: Repository) -> None:
    """单品类价格统计：指定 task_id 只返回该品类"""
    _seed_multi_category_data(tmp_repo)
    resp = client.get(
        "/api/prices/category-stats?task_id=t1", headers=_auth_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["categories"]) == 1
    cat = data["categories"][0]
    assert cat["task_id"] == "t1"
    assert cat["name"] == "iPhone 任务"
    assert cat["keyword"] == "iphone"
    assert cat["count"] == 5
    # 验证统计指标
    prices = [3999.0, 4999.0, 4499.0, 5299.0, 3799.0]
    assert cat["min"] == min(prices)
    assert cat["max"] == max(prices)
    assert cat["mean"] == round(sum(prices) / len(prices), 2)
    # 历史最低价 = min
    assert cat["min"] == 3799.0


def test_category_stats_percentiles(client: TestClient, tmp_repo: Repository) -> None:
    """验证分位数计算正确性"""
    _seed_multi_category_data(tmp_repo)
    resp = client.get(
        "/api/prices/category-stats?task_id=t2", headers=_auth_headers()
    )
    assert resp.status_code == 200
    cat = resp.json()["categories"][0]
    # 键盘品类价格：[299, 399, 499, 599]
    # 排序后：[299, 399, 499, 599]
    # P25 = 0.25 * 3 = 0.75 → 299*0.25 + 399*0.75 = 74.75 + 299.25 = 374.0
    # P75 = 0.75 * 3 = 2.25 → 499*0.75 + 599*0.25 = 374.25 + 149.75 = 524.0
    assert cat["p25"] == 374.0
    assert cat["p75"] == 524.0
    # 中位数 = (399 + 499) / 2 = 449.0
    assert cat["median"] == 449.0


def test_category_stats_empty(client: TestClient, tmp_repo: Repository) -> None:
    """空数据库：返回空品类列表"""
    resp = client.get("/api/prices/category-stats", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["categories"] == []
    assert data["total_count"] == 0


def test_category_stats_nonexistent_task(client: TestClient, tmp_repo: Repository) -> None:
    """不存在的 task_id：返回空品类列表"""
    _seed_multi_category_data(tmp_repo)
    resp = client.get(
        "/api/prices/category-stats?task_id=nonexistent", headers=_auth_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["categories"] == []


def test_category_comparison_default(client: TestClient, tmp_repo: Repository) -> None:
    """多品类横向对比：默认按均价升序"""
    _seed_multi_category_data(tmp_repo)
    resp = client.get(
        "/api/prices/category-comparison", headers=_auth_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert "overall_mean" in data
    assert data["sort_by"] == "mean"
    assert data["order"] == "asc"
    # 3 个品类
    assert len(data["categories"]) == 3
    # 按均价升序：手机壳 < 键盘 < iPhone
    means = [c["mean"] for c in data["categories"]]
    assert means == sorted(means)
    # 验证品类名称
    names = [c["name"] for c in data["categories"]]
    assert "手机壳任务" in names
    assert "键盘任务" in names
    assert "iPhone 任务" in names


def test_category_comparison_sort_by_median_desc(client: TestClient, tmp_repo: Repository) -> None:
    """按中位数降序排序"""
    _seed_multi_category_data(tmp_repo)
    resp = client.get(
        "/api/prices/category-comparison?sort_by=median&order=desc",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    medians = [c["median"] for c in data["categories"]]
    assert medians == sorted(medians, reverse=True)


def test_category_comparison_limit(client: TestClient, tmp_repo: Repository) -> None:
    """limit 参数限制返回品类数"""
    _seed_multi_category_data(tmp_repo)
    resp = client.get(
        "/api/prices/category-comparison?limit=2", headers=_auth_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["categories"]) == 2


def test_category_comparison_deviation_pct(client: TestClient, tmp_repo: Repository) -> None:
    """验证偏离度计算"""
    _seed_multi_category_data(tmp_repo)
    resp = client.get(
        "/api/prices/category-comparison?sort_by=mean&order=asc",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    cats = resp.json()["categories"]
    # 所有品类都应有 deviation_pct 字段
    for c in cats:
        assert "deviation_pct" in c
        assert isinstance(c["deviation_pct"], (int, float))


def test_category_comparison_range_days(client: TestClient, tmp_repo: Repository) -> None:
    """range_days 过滤：仅统计最近 N 天的商品"""
    _seed_multi_category_data(tmp_repo)
    # 最近 1 天：只有 publish_time 在 1 天内的商品
    resp = client.get(
        "/api/prices/category-comparison?range_days=1", headers=_auth_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["range_days"] == 1
    # 每个品类最多 1 个商品（因为测试数据每天 1 个）
    for c in data["categories"]:
        assert c["count"] <= 1


def test_category_comparison_invalid_sort_by(client: TestClient, tmp_repo: Repository) -> None:
    """无效排序字段：回退到 mean"""
    _seed_multi_category_data(tmp_repo)
    resp = client.get(
        "/api/prices/category-comparison?sort_by=invalid_field",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sort_by"] == "mean"


def test_category_comparison_empty(client: TestClient, tmp_repo: Repository) -> None:
    """空数据库横向对比"""
    resp = client.get(
        "/api/prices/category-comparison", headers=_auth_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["categories"] == []
    assert data["overall_mean"] == 0.0


def test_category_stats_has_all_required_fields(client: TestClient, tmp_repo: Repository) -> None:
    """验证返回字段完整性：均价/中位数/历史最低价/价格分位数"""
    _seed_multi_category_data(tmp_repo)
    resp = client.get("/api/prices/category-stats", headers=_auth_headers())
    assert resp.status_code == 200
    cat = resp.json()["categories"][0]
    required_fields = {
        "task_id", "name", "keyword", "count",
        "min", "max", "mean", "median",
        "p10", "p25", "p75", "p90",
    }
    assert required_fields.issubset(set(cat.keys()))


def test_unauthorized_request(client: TestClient) -> None:
    """未认证请求返回 401"""
    resp = client.get("/api/prices/category-stats")
    assert resp.status_code == 401
