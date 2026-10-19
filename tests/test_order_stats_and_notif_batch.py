"""订单状态卡全量口径 + 通知批量删除（T02568 / REQ-036、2.9-5）

钉住三件过去没有任何测试能发现的问题：

1. 抢单记录页四张状态卡原先由前端按「当前页 items」filter，翻到第 2 页数字全变，
   用户当作全局数读；且 pending 桶漏掉了后端实际写入的 pending_pay，「待处理」恒显示 0。
   现在统计来自 list 响应里的 stats/by_status（与列表同 user/task/item 范围的一次 GROUP BY）。
2. 筛选「待处理」传的是 status=pending，而库里写的是 pending_pay → 命中 0 条，
   与卡片数字自相矛盾。T02585 已把字面值统一到 OrderStatus，本文件的断言随之更新。
3. 通知中心勾选批量删除：只删勾中的、只删自己的；deleted<requested 要如实回传。

按前端实际调用的端点打真实 FastAPI 应用（请求序列化、白名单校验、Repository
UPSERT、回读全链路为真），只把数据库换成临时 SQLite，不使用 Mock 替身。
"""
from __future__ import annotations

import pytest


class _ContainerShim:
    """只提供路由实际用到的 `.repo`，其余容器资源与本测试无关"""

    def __init__(self, repo):
        self.repo = repo


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.infra.repository import Repository
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    repo = Repository(db_path=str(tmp_path / "ux568.db"))
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)

    client = TestClient(app)
    # /api/* 全量需鉴权：与 tests/test_notifications_contract.py 同一口径，用管理令牌 Cookie 直通
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo


def _mk_order(repo, oid: str, status: str, *, task_id: str = "t1", item_id: str | None = None) -> None:
    repo.upsert_order({
        "id": oid,
        "task_id": task_id,
        "item_id": item_id or f"i_{oid}",
        "price": 100.0,
        "status": status,
    })


# ---------------- 1. 状态卡：全量口径、翻页不变 ----------------

def test_stats_are_full_scope_and_stable_across_pages(api) -> None:
    client, repo = api
    _mk_order(repo, "o1", "pending_pay")
    _mk_order(repo, "o2", "pending_pay")
    _mk_order(repo, "o3", "takeover_pending")  # 接管中：与 pending_pay 分桶（T02585 归一后不再合并）
    _mk_order(repo, "o4", "succeeded")
    _mk_order(repo, "o5", "failed")

    p1 = client.get("/api/orders", params={"page_num": 1, "page_size": 2}).json()
    p2 = client.get("/api/orders", params={"page_num": 2, "page_size": 2}).json()

    assert len(p1["items"]) == 2 and len(p2["items"]) == 2
    assert p1["total"] == 5 and p2["total"] == 5
    # 关键：两页的 stats 完全相同，且不等于「本页条数」
    assert p1["stats"] == p2["stats"]
    assert p1["stats"]["pending"] == 2
    assert p1["stats"]["succeeded"] == 1
    assert p1["stats"]["failed"] == 1
    assert p1["stats"]["takeover"] == 1
    assert p1["stats"]["total"] == 5
    # by_status 是原始字面值；T02585 起 stats 的桶直接按 OrderStatus 取值，不再做别名合并
    assert p1["by_status"]["pending_pay"] == 2 and p1["by_status"]["takeover_pending"] == 1


def test_stats_scoped_same_as_list_filters(api) -> None:
    """分子分母同源：带 task_id 的列表，stats 也必须只算该任务"""
    client, repo = api
    _mk_order(repo, "o1", "succeeded", task_id="tA")
    _mk_order(repo, "o2", "succeeded", task_id="tA")
    _mk_order(repo, "o3", "failed", task_id="tB")

    scoped = client.get("/api/orders", params={"task_id": "tA"}).json()
    assert scoped["total"] == 2
    assert scoped["stats"]["succeeded"] == 2
    assert scoped["stats"]["failed"] == 0
    assert scoped["stats"]["total"] == 2


def test_canonical_status_filter_hits_pending_pay_rows(api) -> None:
    """筛选「待支付」(status=pending_pay) 必须命中实际写入的行，
    否则顶部卡片显示 N 条、列表却空着 —— 同一份口径不能自相矛盾。

    T02585 起 status 走 OrderStatus 派生的白名单：历史 pending 直接 422，
    而不是静默返回空列表（旧行为靠 _PENDING_LITERALS 别名合并撑着）。"""
    client, repo = api
    _mk_order(repo, "o1", "pending_pay")
    _mk_order(repo, "o2", "pending_pay")
    _mk_order(repo, "o3", "succeeded")

    res = client.get("/api/orders", params={"status": "pending_pay"}).json()
    assert res["total"] == 2
    assert sorted(o["id"] for o in res["items"]) == ["o1", "o2"]
    # 卡片待处理数与筛选命中数一致
    assert res["stats"]["pending"] == res["total"]

    assert client.get("/api/orders", params={"status": "pending"}).status_code == 422


# ---------------- 2. 通知：勾选批量删除 ----------------

def _mk_notif(repo, key: str, **kw) -> int:
    body = {
        "level": "warn", "category": "order", "title": "订单超时",
        "message": "有订单待支付超过 5 分钟", "dedup_key": key, "link": "/orders",
        **kw,
    }
    return int(repo.add_notification(**body)["id"])


def test_batch_delete_removes_only_selected(api) -> None:
    client, repo = api
    ids = [_mk_notif(repo, f"ux568-a{i}") for i in range(4)]

    res = client.post("/api/notifications/batch-delete", json={"ids": ids[:2]})
    assert res.status_code == 200, res.text
    assert res.json() == {"ok": True, "deleted": 2, "requested": 2}

    left = client.get("/api/notifications", params={"limit": 100}).json()
    assert sorted(i["id"] for i in left["items"]) == sorted(ids[2:])


def test_batch_delete_reports_missing_ids_honestly(api) -> None:
    """勾中的通知可能已在别的标签页删掉：deleted < requested 如实回传，不假装全成功"""
    client, repo = api
    keep = _mk_notif(repo, "ux568-b-keep")

    res = client.post("/api/notifications/batch-delete", json={"ids": [keep, 999_999]})
    assert res.json() == {"ok": True, "deleted": 1, "requested": 2}
    assert client.get("/api/notifications", params={"limit": 100}).json()["total"] == 0


def test_batch_delete_is_user_scoped(api) -> None:
    client, repo = api
    mine = _mk_notif(repo, "ux568-c-mine")
    theirs = _mk_notif(repo, "ux568-c-theirs", user_id="other")

    res = client.post("/api/notifications/batch-delete", json={"ids": [mine, theirs]})
    assert res.json() == {"ok": True, "deleted": 1, "requested": 2}
    # 他人通知必须还在（用仓储层直读，绕开本请求的 user 过滤）
    assert repo.get_notification(theirs, user_id="other") is not None


@pytest.mark.parametrize(
    "payload,reason",
    [
        ({"ids": []}, "空数组没有可删对象"),
        ({"ids": "1"}, "非数组"),
        ({"ids": ["abc"]}, "非数字 id"),
        ({"ids": list(range(1, 202))}, "超过单次上限"),
    ],
)
def test_batch_delete_rejects_bad_payload(api, payload, reason) -> None:
    client, _ = api
    res = client.post("/api/notifications/batch-delete", json=payload)
    assert res.status_code == 400, f"{reason}：应 400，实际 {res.status_code} {res.text}"
