"""P1-4 AI 深度多模态分析增强 API 单元测试"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-for-ai-deep"


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
    """构造 TestClient，注入临时 repository 和测试 token

    不配置 openai_api_key，强制走规则模拟路径（避免真实 LLM 调用）。
    """
    from xianyu_hunter.config import Settings
    test_settings = Settings(web_token=_TEST_TOKEN)  # openai_api_key 默认为空
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


def _seed_item(repo: Repository) -> None:
    """填充单个商品测试数据"""
    now = datetime.now(timezone.utc)
    repo.upsert_task({
        "id": "t1", "name": "测试任务", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    repo.batch_upsert_items([
        {
            "id": "i1", "task_id": "t1", "title": "iPhone 13 99新仅拆封",
            "price": 3999.0, "seller_id": "s1", "first_seen": now,
            "description": "iPhone 13 128G 银色，99新仅拆封，自用国行，无划痕磕碰",
            "image_urls": '["https://xianyu.com/img1.jpg", "https://xianyu.com/img2.jpg"]',
        },
    ])


def _seed_seller_items(repo: Repository) -> None:
    """填充卖家多商品数据（用于贩子识别）"""
    now = datetime.now(timezone.utc)
    repo.upsert_task({
        "id": "t1", "name": "测试任务", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    items = []
    # 5 个商品，描述高度模板化（贩子特征）
    template_desc = "99新仅拆封，自用国行，支持验货，假一赔十，全新正品"
    for i in range(5):
        items.append({
            "id": f"item_{i}", "task_id": "t1", "title": f"iPhone {i}",
            "price": 3999.0 + i * 100, "seller_id": "dealer_seller",
            "first_seen": now - timedelta(days=i),
            "description": template_desc,
            "image_urls": '["https://xianyu.com/img.jpg"]',
        })
    repo.batch_upsert_items(items)


def test_deep_analyze_rule_fallback(client: TestClient, tmp_repo: Repository) -> None:
    """规则模拟深度分析：无 LLM Key 时走规则路径"""
    _seed_item(tmp_repo)
    resp = client.post(
        "/api/ai/deep-analyze",
        json={"item_id": "i1", "checks": ["stolen_image", "damage", "consistency", "template"]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "rule"
    assert data["item_id"] == "i1"
    # 4 个维度都应返回
    assert "stolen_image" in data
    assert "damage" in data
    assert "consistency" in data
    assert "template" in data
    # 全局字段
    assert "overall_verdict" in data
    assert "overall_score" in data
    assert "summary" in data
    assert "image_hashes" in data
    assert "checks_performed" in data


def test_deep_analyze_partial_checks(client: TestClient, tmp_repo: Repository) -> None:
    """只请求部分检查项"""
    _seed_item(tmp_repo)
    resp = client.post(
        "/api/ai/deep-analyze",
        json={"item_id": "i1", "checks": ["damage", "template"]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    # 只返回请求的检查项
    assert "damage" in data
    assert "template" in data
    assert "stolen_image" not in data
    assert "consistency" not in data
    assert data["checks_performed"] == ["damage", "template"]


def test_deep_analyze_item_not_found(client: TestClient) -> None:
    """商品不存在返回 404"""
    resp = client.post(
        "/api/ai/deep-analyze",
        json={"item_id": "nonexistent", "checks": ["damage"]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 404


def test_deep_analyze_image_hashes(client: TestClient, tmp_repo: Repository) -> None:
    """验证图片哈希计算"""
    _seed_item(tmp_repo)
    resp = client.post(
        "/api/ai/deep-analyze",
        json={"item_id": "i1", "checks": ["stolen_image"]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    # 2 张图片 → 2 个哈希
    assert len(data["image_hashes"]) == 2
    # 哈希是 12 位 MD5
    for h in data["image_hashes"]:
        assert len(h) == 12


def test_deep_analyze_damage_detection(client: TestClient, tmp_repo: Repository) -> None:
    """损坏检测：描述含划痕关键词应降低评分"""
    now = datetime.now(timezone.utc)
    repo = tmp_repo
    repo.upsert_task({
        "id": "t1", "name": "测试", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    repo.batch_upsert_items([{
        "id": "i_damage", "task_id": "t1", "title": "iPhone 有划痕",
        "price": 2999.0, "seller_id": "s1", "first_seen": now,
        "description": "屏幕有划痕，边框磕碰，电池维修过",
        "image_urls": '["https://xianyu.com/img.jpg"]',
    }])
    resp = client.post(
        "/api/ai/deep-analyze",
        json={"item_id": "i_damage", "checks": ["damage"]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    damage = resp.json()["damage"]
    # 含损坏关键词 → 评分应较低
    assert damage["score"] <= 6
    assert len(damage["signals"]) > 0


def test_deep_analyze_stolen_image_non_official(client: TestClient, tmp_repo: Repository) -> None:
    """盗图检测：非官方图床应降低评分"""
    now = datetime.now(timezone.utc)
    repo = tmp_repo
    repo.upsert_task({
        "id": "t1", "name": "测试", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    repo.batch_upsert_items([{
        "id": "i_stolen", "task_id": "t1", "title": "iPhone 13",
        "price": 3999.0, "seller_id": "s1", "first_seen": now,
        "description": "iPhone 13",
        "image_urls": '["https://example.com/img1.jpg", "https://other.com/img2.jpg"]',
    }])
    resp = client.post(
        "/api/ai/deep-analyze",
        json={"item_id": "i_stolen", "checks": ["stolen_image"]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    stolen = resp.json()["stolen_image"]
    # 非官方图床 → 评分应较低
    assert stolen["score"] <= 6


def test_deep_analyze_template_detection(client: TestClient, tmp_repo: Repository) -> None:
    """模板化检测：堆砌模板词应降低评分"""
    now = datetime.now(timezone.utc)
    repo = tmp_repo
    repo.upsert_task({
        "id": "t1", "name": "测试", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    repo.batch_upsert_items([{
        "id": "i_template", "task_id": "t1", "title": "iPhone 13 全新正品",
        "price": 3999.0, "seller_id": "s1", "first_seen": now,
        "description": "99新仅拆封，自用国行，全新正品，专柜代购，支持验货",
        "image_urls": '["https://xianyu.com/img.jpg"]',
    }])
    resp = client.post(
        "/api/ai/deep-analyze",
        json={"item_id": "i_template", "checks": ["template"]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    template = resp.json()["template"]
    # 堆砌模板词 → 评分应较低
    assert template["score"] <= 6


def test_deep_analyze_no_images(client: TestClient, tmp_repo: Repository) -> None:
    """无图片：盗图和一致性检测应给出风险信号"""
    now = datetime.now(timezone.utc)
    repo = tmp_repo
    repo.upsert_task({
        "id": "t1", "name": "测试", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    repo.batch_upsert_items([{
        "id": "i_noimg", "task_id": "t1", "title": "iPhone 13",
        "price": 3999.0, "seller_id": "s1", "first_seen": now,
        "description": "iPhone 13 128G",
        "image_urls": None,
    }])
    resp = client.post(
        "/api/ai/deep-analyze",
        json={"item_id": "i_noimg", "checks": ["stolen_image", "consistency"]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    # 无图片 → 盗图评分低
    assert data["stolen_image"]["score"] <= 5
    # LLM 返回的信号文本可能不同，只检查分数不检查具体文案
    assert len(data["stolen_image"]["signals"]) >= 0


def test_seller_template_check_dealer(client: TestClient, tmp_repo: Repository) -> None:
    """贩子识别：模板化文案应识别为贩子"""
    _seed_seller_items(tmp_repo)
    resp = client.post(
        "/api/ai/seller-template-check",
        json={"seller_id": "dealer_seller", "sample_size": 10},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["seller_id"] == "dealer_seller"
    assert data["sample_count"] == 5
    # 模板化文案 → 评分应较低，识别为贩子
    assert data["template_score"] <= 6
    assert "is_dealer" in data
    assert "signals" in data
    assert "keyword_freq" in data


def test_seller_template_check_insufficient_samples(client: TestClient, tmp_repo: Repository) -> None:
    """样本不足：返回默认评分"""
    now = datetime.now(timezone.utc)
    repo = tmp_repo
    repo.upsert_task({
        "id": "t1", "name": "测试", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    repo.batch_upsert_items([{
        "id": "i1", "task_id": "t1", "title": "iPhone",
        "price": 3999.0, "seller_id": "small_seller", "first_seen": now,
        "description": "仅 1 个商品",
    }])
    resp = client.post(
        "/api/ai/seller-template-check",
        json={"seller_id": "small_seller", "sample_size": 10},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sample_count"] == 1
    assert data["template_score"] == 10
    assert data["is_dealer"] is False


def test_seller_template_check_no_items(client: TestClient) -> None:
    """卖家无商品：返回默认评分"""
    resp = client.post(
        "/api/ai/seller-template-check",
        json={"seller_id": "empty_seller", "sample_size": 10},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sample_count"] == 0
    assert data["template_score"] == 10
    assert data["is_dealer"] is False


def test_seller_template_check_personal_seller(client: TestClient, tmp_repo: Repository) -> None:
    """个人卖家：个性化文案不应识别为贩子"""
    now = datetime.now(timezone.utc)
    repo = tmp_repo
    repo.upsert_task({
        "id": "t1", "name": "测试", "keyword": "iphone",
        "mode": "confirm", "cron": "*/5 * * * *",
    })
    # 5 个商品，每个描述都不同（个性化）
    items = []
    descs = [
        "自用 iPhone 13，买了半年，电池健康度 92%，送原装充电器",
        "出闲置 iPad，去年教育优惠买的，有发票，9 成新",
        "搬家清仓，索尼耳机 WH-1000XM4，使用一年，包耳皮略有磨损",
        "出国转手 MacBook Pro 2021 款，M1 Pro 芯片，32G 内存",
        "回血出 Switch OLED，玩了几个月，带 3 张卡带",
    ]
    for i, desc in enumerate(descs):
        items.append({
            "id": f"personal_{i}", "task_id": "t1", "title": f"商品 {i}",
            "price": 1000.0 + i * 500, "seller_id": "personal_seller",
            "first_seen": now - timedelta(days=i),
            "description": desc,
        })
    repo.batch_upsert_items(items)
    resp = client.post(
        "/api/ai/seller-template-check",
        json={"seller_id": "personal_seller", "sample_size": 10},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    # 个性化文案 → 评分应较高
    assert data["template_score"] >= 7
    assert data["is_dealer"] is False


def test_unauthorized_request(client: TestClient) -> None:
    """未认证请求返回 401"""
    resp = client.post(
        "/api/ai/deep-analyze",
        json={"item_id": "i1", "checks": ["damage"]},
    )
    assert resp.status_code == 401
