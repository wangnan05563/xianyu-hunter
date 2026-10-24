"""通知中心勾选批量已读（T02621 / 2.9-5）

钉住四个口径：
1. 只标记勾中的那几条，且只把"未读"变"已读"；
2. updated 只数本次真正变化的行——重复调用第二次必须是 0，不虚报；
3. 只改自己的：勾中他人通知的 id 不生效（与单条 mark_read / batch-delete 同口径）；
4. 入参与 batch-delete 同一套校验（空数组/非数组/非数字/超上限）。

按前端实际调用的 POST /api/notifications/batch-read 打真实 FastAPI 应用，
只把数据库换成临时 SQLite，不使用 Mock 替身。
"""
from __future__ import annotations

import pytest


class _ContainerShim:
    def __init__(self, repo):
        self.repo = repo


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.infra.repository import Repository
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    repo = Repository(db_path=str(tmp_path / "notif_batch_read.db"))
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)

    client = TestClient(app)
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo


def _mk_notif(repo, key: str, **kw) -> int:
    body = {
        "level": "warn", "category": "order", "title": "订单超时",
        "message": "有订单待支付超过 5 分钟", "dedup_key": key, "link": "/orders",
        **kw,
    }
    return int(repo.add_notification(**body)["id"])


def test_batch_read_marks_only_selected(api) -> None:
    client, repo = api
    ids = [_mk_notif(repo, f"batch-read-a{i}") for i in range(3)]

    res = client.post("/api/notifications/batch-read", json={"ids": ids[:2]})
    assert res.status_code == 200, res.text
    assert res.json() == {"ok": True, "updated": 2, "requested": 2}

    unread = client.get("/api/notifications", params={"status": "unread", "limit": 100}).json()
    assert [i["id"] for i in unread["items"]] == [ids[2]]
    assert unread["total"] == 1


def test_batch_read_second_call_reports_zero_newly_read(api) -> None:
    """幂等：已读行不再更新，updated 必须如实为 0"""
    client, repo = api
    nid = _mk_notif(repo, "batch-read-idem")

    first = client.post("/api/notifications/batch-read", json={"ids": [nid, 999_999]})
    assert first.json() == {"ok": True, "updated": 1, "requested": 2}

    second = client.post("/api/notifications/batch-read", json={"ids": [nid]})
    assert second.json() == {"ok": True, "updated": 0, "requested": 1}


def test_batch_read_is_user_scoped(api) -> None:
    client, repo = api
    mine = _mk_notif(repo, "batch-read-mine")
    theirs = _mk_notif(repo, "batch-read-theirs", user_id="other")

    res = client.post("/api/notifications/batch-read", json={"ids": [mine, theirs]})
    assert res.json() == {"ok": True, "updated": 1, "requested": 2}

    theirs_row = repo.get_notification(theirs, user_id="other")
    assert theirs_row is not None and theirs_row["read_at"] is None


@pytest.mark.parametrize(
    "payload,reason",
    [
        ({"ids": []}, "空数组没有可标记对象"),
        ({"ids": "1"}, "非数组"),
        ({"ids": ["abc"]}, "非数字 id"),
        ({"ids": list(range(1, 202))}, "超过单次上限"),
    ],
)
def test_batch_read_rejects_bad_payload(api, payload, reason) -> None:
    client, _ = api
    res = client.post("/api/notifications/batch-read", json=payload)
    assert res.status_code == 400, f"{reason}：应 400，实际 {res.status_code} {res.text}"
