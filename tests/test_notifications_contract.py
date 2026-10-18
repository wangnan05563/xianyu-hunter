# tests/test_notifications_contract.py
"""通知中心前后端契约测试（T02561 / FR-B-1）

两条背景，都是过去没有任何测试能发现的：

1. `mark_read` / `delete` 两个写端点调用 `repo.get_notification(notif_id, user_id=...)`，
   而仓储层签名根本没有 `user_id` 参数 —— 每次标记已读/删除都是 TypeError → 500。
   通知中心页的「标记已读」按钮因此从未真正生效过，badge 也永远清不掉。
2. 前端「已读」数原先是 `列表 total − unread` 现算，而 `total` 跟随 status 筛选变化
   （选「未读」时恒 0、选「已读」时错算）。本测试把「计数端点与筛选无关」这件事钉死，
   前端才能安全地改读后端全量口径。

按前端实际调用的端点打真实 FastAPI 应用（请求序列化、Pydantic/白名单校验、
Repository UPSERT、回读全链路为真），只把数据库换成临时 SQLite，不使用 Mock 替身。
"""
from __future__ import annotations

import pytest


class _ContainerShim:
    """只提供路由实际用到的 `.repo`，其余容器资源与本测试无关"""

    def __init__(self, repo):
        self.repo = repo


@pytest.fixture
def notif_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.infra.repository import Repository
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    repo = Repository(db_path=str(tmp_path / "notif.db"))
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)

    client = TestClient(app)
    # /api/* 全量需鉴权：与 tests/test_menu_contract.py 同一口径，用管理令牌 Cookie 直通
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo


def _mk(client, dedup_key: str, **overrides) -> int:
    body = {
        "level": "warn",
        "category": "order",
        "title": "订单超时",
        "message": "有订单待支付超过 5 分钟",
        "dedup_key": dedup_key,
        **overrides,
    }
    resp = client.post("/api/notifications", json=body)
    assert resp.status_code == 200, resp.text
    return int(resp.json()["item"]["id"])


def test_mark_read_returns_200(notif_client):
    """回归锁：修复前这里是 500（get_notification 不接收 user_id）"""
    client, _ = notif_client
    nid = _mk(client, "t02561-mark-read")
    resp = client.post(f"/api/notifications/{nid}/read")
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    assert resp.json()["newly_read"] is True


def test_delete_returns_200(notif_client):
    client, _ = notif_client
    nid = _mk(client, "t02561-delete")
    resp = client.delete(f"/api/notifications/{nid}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted"] is True
    assert client.get("/api/notifications").json()["total"] == 0


def test_mark_read_is_idempotent_and_moves_bucket(notif_client):
    """重复标记不再计入 newly_read，但已读数只有一份：unread 减、read 加"""
    client, _ = notif_client
    nid = _mk(client, "t02561-idem")
    assert client.get("/api/notifications/unread_count").json() == {"unread": 1, "read": 0, "total": 1}

    assert client.post(f"/api/notifications/{nid}/read").json()["newly_read"] is True
    assert client.post(f"/api/notifications/{nid}/read").json()["newly_read"] is False

    counts = client.get("/api/notifications/unread_count").json()
    assert counts == {"unread": 0, "read": 1, "total": 1}


def test_counts_ignore_list_filter(notif_client):
    """2.9-3 的核心断言：三个计数是全量口径，不随列表 status 筛选变化"""
    client, _ = notif_client
    first = _mk(client, "t02561-c1")
    _mk(client, "t02561-c2")
    _mk(client, "t02561-c3")
    client.post(f"/api/notifications/{first}/read")

    expected = {"unread": 2, "read": 1, "total": 3}
    assert client.get("/api/notifications/unread_count").json() == expected

    # 列表的 total 才是跟随筛选的——前端若拿它反算已读就会错，这里把两者区分钉住
    for status, total in (("unread", 2), ("read", 1), (None, 3)):
        params = {"status": status} if status else {}
        assert client.get("/api/notifications", params=params).json()["total"] == total
    assert client.get("/api/notifications/unread_count").json() == expected


def test_get_notification_scopes_by_user(notif_client):
    """user_id 过滤要与 mark/delete 同一口径，否则跨用户可见即越权"""
    _, repo = notif_client
    nid = _mk_repo_notification(repo, "t02561-scope", user_id="alice")
    assert repo.get_notification(nid, user_id="alice") is not None
    assert repo.get_notification(nid, user_id="bob") is None


def _mk_repo_notification(repo, dedup_key: str, user_id: str) -> int:
    row = repo.add_notification(
        level="info", category="system", title="t", message="m",
        link=None, dedup_key=dedup_key, user_id=user_id,
    )
    return int(row["id"])
