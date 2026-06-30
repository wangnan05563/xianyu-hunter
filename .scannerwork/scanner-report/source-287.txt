"""P1-2 多账号轮换 + 代理池 API 单元测试"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings
from xianyu_hunter.infra.db_models import Base, AccountRow, ProxyRow, _utcnow
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-for-accounts-proxies"


@pytest.fixture
def tmp_repo() -> Repository:
    """使用临时数据库"""
    import tempfile
    from pathlib import Path
    get_settings.cache_clear()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        # 显式创建 accounts 和 proxies 表
        Base.metadata.create_all(repo.engine)
        yield repo
        repo.engine.dispose()
        get_settings.cache_clear()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    """构造 TestClient"""
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
            self._account_rotator = None
            self._proxy_pool = None
    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


# ============== 账号管理测试 ==============
def test_create_account(client: TestClient) -> None:
    """创建账号"""
    resp = client.post(
        "/api/accounts",
        json={"name": "account1", "nickname": "测试账号1", "note": "测试"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "account1"
    assert data["nickname"] == "测试账号1"
    assert data["status"] == "active"
    assert data["use_count"] == 0
    assert data["fail_count"] == 0
    # cookies 不应返回明文
    assert "cookies" not in data
    assert data["has_cookies"] is False


def test_create_account_with_cookies(client: TestClient) -> None:
    """创建带 cookies 的账号"""
    cookies = [{"name": "token", "value": "abc123"}]
    resp = client.post(
        "/api/accounts",
        json={"name": "account2", "cookies": cookies},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_cookies"] is True
    assert "cookies" not in data  # 明文不返回


def test_create_account_duplicate(client: TestClient) -> None:
    """重复账号名返回 409"""
    client.post(
        "/api/accounts",
        json={"name": "dup"},
        headers=_auth_headers(),
    )
    resp = client.post(
        "/api/accounts",
        json={"name": "dup"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 409


def test_list_accounts(client: TestClient) -> None:
    """列出账号"""
    for i in range(3):
        client.post(
            "/api/accounts",
            json={"name": f"acc_{i}"},
            headers=_auth_headers(),
        )
    resp = client.get("/api/accounts", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert len(data["accounts"]) == 3


def test_list_accounts_filter_status(client: TestClient) -> None:
    """按状态过滤账号"""
    client.post("/api/accounts", json={"name": "active1"}, headers=_auth_headers())
    client.post("/api/accounts", json={"name": "disabled1"}, headers=_auth_headers())
    # 手动禁用第二个
    resp = client.post("/api/accounts", json={"name": "active1"}, headers=_auth_headers())
    # 获取 ID 后禁用
    accounts = client.get("/api/accounts", headers=_auth_headers()).json()["accounts"]
    disabled_id = [a["id"] for a in accounts if a["name"] == "disabled1"][0]
    client.put(
        f"/api/accounts/{disabled_id}",
        json={"status": "disabled"},
        headers=_auth_headers(),
    )
    # 查询 active
    resp = client.get("/api/accounts?status=active", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert all(a["status"] == "active" for a in data["accounts"])


def test_get_account(client: TestClient) -> None:
    """获取单个账号"""
    create_resp = client.post(
        "/api/accounts", json={"name": "get_test"}, headers=_auth_headers()
    )
    account_id = create_resp.json()["id"]
    resp = client.get(f"/api/accounts/{account_id}", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json()["name"] == "get_test"


def test_get_account_not_found(client: TestClient) -> None:
    """获取不存在的账号"""
    resp = client.get("/api/accounts/9999", headers=_auth_headers())
    assert resp.status_code == 404


def test_update_account(client: TestClient) -> None:
    """更新账号"""
    create_resp = client.post(
        "/api/accounts", json={"name": "update_test"}, headers=_auth_headers()
    )
    account_id = create_resp.json()["id"]
    resp = client.put(
        f"/api/accounts/{account_id}",
        json={"nickname": "新昵称", "note": "更新备注"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["nickname"] == "新昵称"
    assert data["note"] == "更新备注"


def test_delete_account(client: TestClient) -> None:
    """删除账号"""
    create_resp = client.post(
        "/api/accounts", json={"name": "del_test"}, headers=_auth_headers()
    )
    account_id = create_resp.json()["id"]
    resp = client.delete(f"/api/accounts/{account_id}", headers=_auth_headers())
    assert resp.status_code == 200
    # 确认已删除
    resp = client.get(f"/api/accounts/{account_id}", headers=_auth_headers())
    assert resp.status_code == 404


def test_acquire_account_round_robin(client: TestClient) -> None:
    """轮换获取账号：按 last_used_at 升序"""
    # 创建 3 个账号
    ids = []
    for i in range(3):
        resp = client.post(
            "/api/accounts", json={"name": f"rr_{i}"}, headers=_auth_headers()
        )
        ids.append(resp.json()["id"])

    # 第一次获取：应该是最早创建的（last_used_at 为 NULL）
    resp = client.post(
        "/api/accounts/acquire", json={}, headers=_auth_headers()
    )
    assert resp.status_code == 200
    first_id = resp.json()["id"]
    assert first_id == ids[0]

    # 第二次获取：应该是第二个（第一个刚用过）
    resp = client.post(
        "/api/accounts/acquire", json={}, headers=_auth_headers()
    )
    assert resp.status_code == 200
    second_id = resp.json()["id"]
    assert second_id == ids[1]

    # 第三次获取：应该是第三个
    resp = client.post(
        "/api/accounts/acquire", json={}, headers=_auth_headers()
    )
    assert resp.status_code == 200
    third_id = resp.json()["id"]
    assert third_id == ids[2]

    # 第四次获取：应该回到第一个（轮询循环）
    resp = client.post(
        "/api/accounts/acquire", json={}, headers=_auth_headers()
    )
    assert resp.status_code == 200
    fourth_id = resp.json()["id"]
    assert fourth_id == ids[0]


def test_acquire_account_preferred(client: TestClient) -> None:
    """优先使用指定账号"""
    for i in range(3):
        client.post(
            "/api/accounts", json={"name": f"pref_{i}"}, headers=_auth_headers()
        )
    resp = client.post(
        "/api/accounts/acquire",
        json={"preferred_name": "pref_2"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "pref_2"


def test_acquire_account_no_available(client: TestClient) -> None:
    """无可用账号返回 404"""
    # 创建一个禁用账号
    create_resp = client.post(
        "/api/accounts", json={"name": "disabled_acc"}, headers=_auth_headers()
    )
    account_id = create_resp.json()["id"]
    client.put(
        f"/api/accounts/{account_id}",
        json={"status": "disabled"},
        headers=_auth_headers(),
    )
    resp = client.post(
        "/api/accounts/acquire", json={}, headers=_auth_headers()
    )
    assert resp.status_code == 404


def test_report_success(client: TestClient) -> None:
    """报告成功：重置失败计数"""
    create_resp = client.post(
        "/api/accounts", json={"name": "success_test"}, headers=_auth_headers()
    )
    account_id = create_resp.json()["id"]
    resp = client.post(
        f"/api/accounts/{account_id}/report-success", headers=_auth_headers()
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_report_fail_cooldown(client: TestClient) -> None:
    """报告失败：进入冷却"""
    create_resp = client.post(
        "/api/accounts", json={"name": "fail_test"}, headers=_auth_headers()
    )
    account_id = create_resp.json()["id"]
    resp = client.post(
        f"/api/accounts/{account_id}/report-fail",
        json={"cooldown_sec": 60},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "cooldown"
    assert data["fail_count"] == 1
    assert data["cooldown_until"] is not None


def test_report_fail_auto_disable(client: TestClient, tmp_repo: Repository) -> None:
    """连续失败超过阈值自动禁用"""
    # 直接操作数据库设置 fail_count 接近阈值
    create_resp = client.post(
        "/api/accounts", json={"name": "auto_disable"}, headers=_auth_headers()
    )
    account_id = create_resp.json()["id"]
    # 手动设置 fail_count = 4（阈值 5，再失败一次就禁用）
    with tmp_repo.engine.begin() as conn:
        conn.execute(
            AccountRow.__table__.update()
            .where(AccountRow.id == account_id)
            .values(fail_count=4)
        )
    resp = client.post(
        f"/api/accounts/{account_id}/report-fail",
        json={"cooldown_sec": 60},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "disabled"
    assert data["fail_count"] == 5


def test_account_stats(client: TestClient) -> None:
    """账号池统计"""
    client.post("/api/accounts", json={"name": "s1"}, headers=_auth_headers())
    client.post("/api/accounts", json={"name": "s2"}, headers=_auth_headers())
    resp = client.get("/api/accounts/stats", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["active"] == 2
    assert data["cooldown"] == 0
    assert data["disabled"] == 0


# ============== 代理管理测试 ==============
def test_create_proxy(client: TestClient) -> None:
    """创建代理"""
    resp = client.post(
        "/api/proxies",
        json={"url": "http://user:pass@127.0.0.1:8080", "note": "测试代理"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"] == "http://user:pass@127.0.0.1:8080"
    assert data["status"] == "active"
    assert data["use_count"] == 0


def test_create_proxy_invalid_url(client: TestClient) -> None:
    """无效代理 URL 返回 400"""
    resp = client.post(
        "/api/proxies",
        json={"url": "not-a-url"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_create_proxy_duplicate(client: TestClient) -> None:
    """重复代理 URL 返回 400"""
    client.post(
        "/api/proxies",
        json={"url": "http://127.0.0.1:8080"},
        headers=_auth_headers(),
    )
    resp = client.post(
        "/api/proxies",
        json={"url": "http://127.0.0.1:8080"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_list_proxies(client: TestClient) -> None:
    """列出代理"""
    for i in range(3):
        client.post(
            "/api/proxies",
            json={"url": f"http://127.0.0.1:{8080 + i}"},
            headers=_auth_headers(),
        )
    resp = client.get("/api/proxies", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3


def test_get_proxy(client: TestClient) -> None:
    """获取单个代理"""
    create_resp = client.post(
        "/api/proxies",
        json={"url": "http://127.0.0.1:9090"},
        headers=_auth_headers(),
    )
    proxy_id = create_resp.json()["id"]
    resp = client.get(f"/api/proxies/{proxy_id}", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json()["url"] == "http://127.0.0.1:9090"


def test_update_proxy(client: TestClient) -> None:
    """更新代理"""
    create_resp = client.post(
        "/api/proxies",
        json={"url": "http://127.0.0.1:7070"},
        headers=_auth_headers(),
    )
    proxy_id = create_resp.json()["id"]
    resp = client.put(
        f"/api/proxies/{proxy_id}",
        json={"note": "更新备注"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["note"] == "更新备注"


def test_delete_proxy(client: TestClient) -> None:
    """删除代理"""
    create_resp = client.post(
        "/api/proxies",
        json={"url": "http://127.0.0.1:6060"},
        headers=_auth_headers(),
    )
    proxy_id = create_resp.json()["id"]
    resp = client.delete(f"/api/proxies/{proxy_id}", headers=_auth_headers())
    assert resp.status_code == 200
    resp = client.get(f"/api/proxies/{proxy_id}", headers=_auth_headers())
    assert resp.status_code == 404


def test_acquire_proxy_round_robin(client: TestClient) -> None:
    """轮换获取代理"""
    ids = []
    for i in range(3):
        resp = client.post(
            "/api/proxies",
            json={"url": f"http://127.0.0.1:{1000 + i}"},
            headers=_auth_headers(),
        )
        ids.append(resp.json()["id"])

    # 依次获取
    first = client.post("/api/proxies/acquire", headers=_auth_headers()).json()
    second = client.post("/api/proxies/acquire", headers=_auth_headers()).json()
    third = client.post("/api/proxies/acquire", headers=_auth_headers()).json()

    assert first["id"] == ids[0]
    assert second["id"] == ids[1]
    assert third["id"] == ids[2]


def test_acquire_proxy_no_available(client: TestClient) -> None:
    """无可用代理返回 404"""
    resp = client.post("/api/proxies/acquire", headers=_auth_headers())
    assert resp.status_code == 404


def test_report_proxy_success(client: TestClient) -> None:
    """报告代理成功"""
    create_resp = client.post(
        "/api/proxies",
        json={"url": "http://127.0.0.1:5000"},
        headers=_auth_headers(),
    )
    proxy_id = create_resp.json()["id"]
    resp = client.post(
        f"/api/proxies/{proxy_id}/report-success", headers=_auth_headers()
    )
    assert resp.status_code == 200


def test_report_proxy_fail(client: TestClient) -> None:
    """报告代理失败"""
    create_resp = client.post(
        "/api/proxies",
        json={"url": "http://127.0.0.1:4000"},
        headers=_auth_headers(),
    )
    proxy_id = create_resp.json()["id"]
    resp = client.post(
        f"/api/proxies/{proxy_id}/report-fail", headers=_auth_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fail_count"] == 1


def test_proxy_stats(client: TestClient) -> None:
    """代理池统计"""
    client.post(
        "/api/proxies", json={"url": "http://127.0.0.1:3000"}, headers=_auth_headers()
    )
    resp = client.get("/api/proxies/stats", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["active"] == 1


def test_unauthorized_request(client: TestClient) -> None:
    """未认证请求返回 401"""
    resp = client.get("/api/accounts")
    assert resp.status_code == 401
    resp = client.get("/api/proxies")
    assert resp.status_code == 401
