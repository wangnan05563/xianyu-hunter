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


def test_category_stats_excludes_deleted_task(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """已删除任务不应出现在价格行情统计

    修复前：_build_task_select 未过滤 status != 'deleted'，
    导致用户删除任务后价格行情仍显示该品类（样本数为 0 的空品类）。
    """
    _seed_multi_category_data(tmp_repo)
    # 删除任务 t3（手机壳）
    tmp_repo.update_task_status("t3", "deleted")
    resp = client.get("/api/prices/category-stats", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    # 应只剩 2 个品类（iPhone + 键盘），不是 3 个
    assert len(data["categories"]) == 2
    task_ids = {c["task_id"] for c in data["categories"]}
    assert "t3" not in task_ids


def test_category_comparison_excludes_deleted_task(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """已删除任务不应出现在品类横向对比"""
    _seed_multi_category_data(tmp_repo)
    tmp_repo.update_task_status("t2", "deleted")
    resp = client.get(
        "/api/prices/category-comparison", headers=_auth_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["categories"]) == 2
    task_ids = {c["task_id"] for c in data["categories"]}
    assert "t2" not in task_ids


def test_category_stats_deleted_single_task_returns_empty(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """查询已删除的单个任务时返回空品类列表"""
    _seed_multi_category_data(tmp_repo)
    tmp_repo.update_task_status("t1", "deleted")
    resp = client.get(
        "/api/prices/category-stats?task_id=t1", headers=_auth_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["categories"] == []
    assert data["total_count"] == 0


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


# ============== sold-range 任务价格区间过滤与 bargain_eval 评估 ==============


def _seed_sold_range_data(repo: Repository) -> None:
    """填充 sold-range 测试数据：1 个带价格区间的任务 + 多个已售商品

    任务 t1 配置 min_price=3000, max_price=6000，已售商品价格含：
    - 1 元引流（应被过滤）
    - 200 元配件（应被过滤）
    - 3500/3800/4200/4800/5500（在范围内，应保留）
    - 9999 元超范围高价（应被过滤）
    """
    repo.upsert_task({
        "id": "t1", "name": "iPhone 任务", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
        "min_price": 3000.0, "max_price": 6000.0,
    })
    # 通过 task_links 注入已售商品（is_sold=1, price 在 display 中）
    sold_prices = [1.0, 200.0, 3500.0, 3800.0, 4200.0, 4800.0, 5500.0, 9999.0]
    for i, price in enumerate(sold_prices):
        repo.upsert_task_link(
            task_id="t1",
            link_type="item",
            link_key=f"item_{i}",
            display={"price": price, "is_sold": 1, "title": f"item {i}"},
        )


def test_sold_range_filters_by_task_price_range(client: TestClient, tmp_repo: Repository) -> None:
    """sold-range 应按任务价格区间过滤异常样本（1 元引流/配件/超范围高价被剔除）"""
    _seed_sold_range_data(tmp_repo)
    resp = client.get("/api/prices/sold-range?task_id=t1&range_days=0", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    # 过滤后应保留 3500/3800/4200/4800/5500 共 5 个样本
    assert data["sample_size"] == 5
    assert data["min_price"] == 3500.0
    assert data["max_price"] == 5500.0
    # task_price_range 字段应回传任务配置
    assert data["task_price_range"]["min_price"] == 3000.0
    assert data["task_price_range"]["max_price"] == 6000.0
    # 分位数字段应存在
    for field in ("p10", "p25", "p75", "p90"):
        assert field in data
        assert data[field] is not None


def test_sold_range_bargain_price_uses_p10_not_min(client: TestClient, tmp_repo: Repository) -> None:
    """bargain_price 应使用 P10 分位数而非历史最低价，避免单点异常污染"""
    _seed_sold_range_data(tmp_repo)
    resp = client.get("/api/prices/sold-range?task_id=t1&range_days=0", headers=_auth_headers())
    data = resp.json()
    # 过滤后样本排序：[3500, 3800, 4200, 4800, 5500]
    # P10 = 0.10 * 4 = 0.4 → 3500*0.6 + 3800*0.4 = 2100 + 1520 = 3620.0
    assert data["bargain_price"] == 3620.0
    # min_price 仍保留为真实最低价
    assert data["min_price"] == 3500.0


def test_sold_range_no_task_range_keeps_all(client: TestClient, tmp_repo: Repository) -> None:
    """任务未配置价格区间时不过滤，保留原有行为"""
    repo = tmp_repo
    repo.upsert_task({
        "id": "t_no_range", "name": "无价格区间任务", "keyword": "test",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    for i, price in enumerate([1.0, 100.0, 500.0]):
        repo.upsert_task_link(
            task_id="t_no_range",
            link_type="item",
            link_key=f"item_{i}",
            display={"price": price, "is_sold": 1, "title": f"item {i}"},
        )
    resp = client.get("/api/prices/sold-range?task_id=t_no_range&range_days=0", headers=_auth_headers())
    data = resp.json()
    # 未配置区间，1 元商品应保留
    assert data["sample_size"] == 3
    assert data["min_price"] == 1.0
    assert data["task_price_range"]["min_price"] is None
    assert data["task_price_range"]["max_price"] is None


def test_bargain_eval_excellent_level(client: TestClient, tmp_repo: Repository) -> None:
    """bargain-eval：当前价格低于 P10 评定为 excellent"""
    _seed_sold_range_data(tmp_repo)
    # 过滤后样本 [3500, 3800, 4200, 4800, 5500]，P10=3620
    resp = client.get(
        "/api/prices/bargain-eval?task_id=t1&current_price=3000&range_days=0",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["bargain_level"] == "excellent"
    assert data["bargain_score"] == 95
    assert "极好的捡漏机会" in data["suggestion"]
    assert data["sold_price_stats"] is not None
    assert data["sold_price_stats"]["count"] == 5


def test_bargain_eval_poor_level(client: TestClient, tmp_repo: Repository) -> None:
    """bargain-eval：当前价格高于中位数评定为 poor"""
    _seed_sold_range_data(tmp_repo)
    # 中位数 = 4200，传入 5000 高于中位数
    resp = client.get(
        "/api/prices/bargain-eval?task_id=t1&current_price=5000&range_days=0",
        headers=_auth_headers(),
    )
    data = resp.json()
    assert data["bargain_level"] == "poor"
    assert data["bargain_score"] == 30
    assert "价格偏高" in data["suggestion"]


def test_bargain_eval_below_task_min_warns_risk(client: TestClient, tmp_repo: Repository) -> None:
    """bargain-eval：低于任务配置下限优先提示假货/骗子风险"""
    _seed_sold_range_data(tmp_repo)
    # task_min=3000，传入 100 低于下限
    resp = client.get(
        "/api/prices/bargain-eval?task_id=t1&current_price=100&range_days=0",
        headers=_auth_headers(),
    )
    data = resp.json()
    # 即使 100 < P10，任务区间校验优先，应提示风险而非 excellent
    assert "低于任务配置下限" in data["suggestion"]
    assert "假货/骗子风险" in data["suggestion"]


def test_bargain_eval_above_task_max_warns_out_of_range(client: TestClient, tmp_repo: Repository) -> None:
    """bargain-eval：高于任务配置上限提示超出监控目标范围"""
    _seed_sold_range_data(tmp_repo)
    # task_max=6000，传入 8000 高于上限
    resp = client.get(
        "/api/prices/bargain-eval?task_id=t1&current_price=8000&range_days=0",
        headers=_auth_headers(),
    )
    data = resp.json()
    assert "高于任务配置上限" in data["suggestion"]
    assert "超出监控目标范围" in data["suggestion"]


def test_bargain_eval_below_task_min_returns_out_of_range_level(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """bargain-eval：低于 task_min 应返回 out_of_range 等级而非 excellent

    修复前：低于 task_min 时分位数评定为 excellent，但 suggestion 提示假货风险，
    造成 level 与 suggestion 语义冲突。新逻辑统一返回 out_of_range 等级。
    """
    _seed_sold_range_data(tmp_repo)
    # task_min=3000，传入 100 低于下限（同时也低于 P10=3620）
    resp = client.get(
        "/api/prices/bargain-eval?task_id=t1&current_price=100&range_days=0",
        headers=_auth_headers(),
    )
    data = resp.json()
    assert data["bargain_level"] == "out_of_range"
    assert data["bargain_score"] == 0
    assert "低于任务配置下限" in data["suggestion"]


def test_bargain_eval_above_task_max_returns_out_of_range_level(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """bargain-eval：高于 task_max 应返回 out_of_range 等级而非 poor"""
    _seed_sold_range_data(tmp_repo)
    # task_max=6000，传入 8000 高于上限（同时也高于中位数 4200）
    resp = client.get(
        "/api/prices/bargain-eval?task_id=t1&current_price=8000&range_days=0",
        headers=_auth_headers(),
    )
    data = resp.json()
    assert data["bargain_level"] == "out_of_range"
    assert data["bargain_score"] == 0
    assert "高于任务配置上限" in data["suggestion"]


def test_category_stats_filters_by_task_price_range(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """category-stats 应按任务价格区间过滤异常样本

    验证 _load_category_prices 的 apply_task_range_filter 逻辑。
    """
    repo = tmp_repo
    repo.upsert_task({
        "id": "t_range", "name": "范围任务", "keyword": "range",
        "mode": "confirm", "cron": "*/5 * * * *",
        "min_price": 100.0, "max_price": 500.0,
    })
    now = datetime.now(timezone.utc)
    # 同时往 task_links（sold_range 用）和 items（category-stats 用）写数据
    items = []
    for i, price in enumerate([1.0, 50.0, 100.0, 200.0, 350.0, 500.0, 999.0]):
        repo.upsert_task_link(
            task_id="t_range",
            link_type="item",
            link_key=f"item_{i}",
            display={"price": price, "is_sold": 0, "title": f"item {i}"},
        )
        items.append({
            "id": f"item_{i}", "task_id": "t_range", "title": f"item {i}",
            "price": price, "seller_id": f"s_{i}",
            "first_seen": now, "publish_time": now,
        })
    repo.batch_upsert_items(items)

    resp = client.get(
        "/api/prices/category-stats?task_id=t_range", headers=_auth_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    cat = data["categories"][0]
    # 1元/50元/999元 都被过滤，保留 100/200/350/500 共 4 个
    assert cat["count"] == 4
    assert cat["min"] == 100.0
    assert cat["max"] == 500.0
    assert cat["task_price_range"]["min_price"] == 100.0
    assert cat["task_price_range"]["max_price"] == 500.0


def test_category_comparison_overall_mean_uses_weighted_average(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """category-comparison overall_mean 应使用样本数加权平均

    修复前用"每个品类重复 min(count, 100) 次均值"近似加权，
    count>100 的品类权重被截断。修复后用 sum(mean*count)/sum(count)
    精确加权。
    """
    _seed_multi_category_data(tmp_repo)
    resp = client.get(
        "/api/prices/category-comparison", headers=_auth_headers()
    )
    data = resp.json()
    # 验证：精确加权 = sum(mean*count) / sum(count)
    cats = data["categories"]
    expected = sum(c["mean"] * c["count"] for c in cats) / sum(c["count"] for c in cats)
    expected = round(expected, 2)
    assert data["overall_mean"] == expected


def test_histogram_endpoint_not_crash_with_task_id(
    client: TestClient, tmp_repo: Repository,
) -> None:
    """histogram 端点不应因 _load_histogram_samples 参数不匹配崩溃

    修复前：_load_histogram_samples 函数定义只接受 3 个参数，
    调用方传 4 个参数，导致 TypeError。
    """
    repo = tmp_repo
    repo.upsert_task({
        "id": "t_hist", "name": "直方图任务", "keyword": "hist",
        "mode": "confirm", "cron": "*/5 * * * *",
        "min_price": 100.0, "max_price": 500.0,
    })
    now = datetime.now(timezone.utc)
    items = [
        {"id": f"h_{i}", "task_id": "t_hist", "title": f"h_{i}",
         "price": price, "seller_id": f"sh_{i}",
         "first_seen": now, "publish_time": now}
        for i, price in enumerate([1.0, 100.0, 250.0, 500.0, 9999.0])
    ]
    repo.batch_upsert_items(items)

    resp = client.get(
        "/api/prices/histogram?task_id=t_hist&bins=20", headers=_auth_headers()
    )
    assert resp.status_code == 200
    summary = resp.json()["summary"]
    # 1元/9999元被过滤，保留 100/250/500 共 3 个
    assert summary["count"] == 3
    assert summary["min"] == 100.0
    assert summary["max"] == 500.0


def test_bargain_eval_empty_data_returns_unknown(client: TestClient, tmp_repo: Repository) -> None:
    """bargain-eval：无已售数据时返回 unknown 等级"""
    repo = tmp_repo
    repo.upsert_task({
        "id": "t_empty", "name": "空任务", "keyword": "empty",
        "mode": "confirm", "cron": "*/5 * * * *",
        "min_price": 100.0, "max_price": 500.0,
    })
    resp = client.get(
        "/api/prices/bargain-eval?task_id=t_empty&current_price=200&range_days=0",
        headers=_auth_headers(),
    )
    data = resp.json()
    assert data["bargain_level"] == "unknown"
    assert data["bargain_score"] == 0
    assert data["sold_price_stats"] is None
    assert "暂无" in data["suggestion"]


def test_bargain_eval_requires_task_id(client: TestClient) -> None:
    """bargain-eval：task_id 必填，缺失返回 422"""
    resp = client.get(
        "/api/prices/bargain-eval?current_price=100",
        headers=_auth_headers(),
    )
    assert resp.status_code == 422


def test_bargain_eval_requires_current_price(client: TestClient) -> None:
    """bargain-eval：current_price 必填，缺失返回 422"""
    resp = client.get(
        "/api/prices/bargain-eval?task_id=t1",
        headers=_auth_headers(),
    )
    assert resp.status_code == 422
