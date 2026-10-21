"""T02618 回归：通知读写两侧的 user_id 口径必须同源

原缺陷（工单 T02618 / 母单 T02561 2.6 通知模型统一）：
- 读侧（list / unread_count）用 `getattr(request.state, "user_id", None)`，
- 写侧（POST / read / delete / batch-delete / clear）用 `getattr(..., "default")`。

两套兜底值一错开，"能看见的行"和"能改动的行"就不是同一批：前端表现为
「点了标记已读/删除没反应」（404）。另一头，通知引擎与盯盘降价写入从不带
user_id，全部落 default，真实会话用户登录后通知中心是空的。

本文件把四件事钉成断言：
1. `web.utils.reader_user_id` / `owner_user_id` 两个口径函数本身的值域；
2. 通知路由 8 个端点**全部**取同一个身份值（owner_user_id）：
   「看得见 = 改得动」+「直通也删不掉他人的行」两条锁的交集；
3. 后台/引擎写入把归属带给通知（订单超时规则、掉线规则、盯盘降价汇总），
   扫描范围与通知归属同一个值；
4. 静态守卫——防止路由里再出现裸 `getattr(request.state, ...)`，
   也防止通知侧误学日志侧放开为不过滤（日志只有读侧，通知有改侧）。

为什么多数断言直接调用路由函数而不是走 HTTP：身份来自鉴权中间件写入的
`request.state.user_id`，走 HTTP 需要签发真实 session token（那部分已有专测
tests/test_auth_middleware_mu2.py）；这里要锁的是"路由有没有把身份透传到仓储"，
用 SimpleNamespace 造 request.state 最直接，也不会因鉴权细节变动而假红。
直通路径另走一次真实 HTTP（TestClient + WEB_TOKEN cookie）作为端到端补充。
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
API_NOTIFICATIONS = ROOT / "backend" / "xianyu_hunter" / "web" / "routes" / "api_notifications.py"


class _ContainerShim:
    """只提供路由/引擎实际用到的 `.repo`，可选记录 list_orders 的入参"""

    def __init__(self, repo, **extra):
        self.repo = repo
        self.__dict__.update(extra)


def _req(user_id: object = ...) -> SimpleNamespace:
    """造一个只带 state.user_id 的假 Request；不传 = 属性缺失（未过中间件）"""
    state = SimpleNamespace()
    if user_id is not ...:
        state.user_id = user_id
    return SimpleNamespace(state=state)


@pytest.fixture
def repo(tmp_path):
    from xianyu_hunter.infra.repository import Repository

    return Repository(db_path=str(tmp_path / "notif_scope.db"))


def _mk(repo, dedup_key: str, user_id: str | None) -> int:
    """经仓储直接建一条通知，返回 id"""
    row = repo.add_notification(
        level="warn", category="order", title=f"t-{dedup_key}", message="m",
        link=None, dedup_key=dedup_key, user_id=user_id,
    )
    return int(row["id"])


def _list(shim, user_id: object = ...) -> dict:
    """直调 list 路由。

    ⚠ 必须显式传 status/limit/offset：绕过 FastAPI 时函数默认值是 `Query(...)`
    对象而不是 50/None，直接透传给仓储会炸 `int() argument ... not 'Query'`。
    """
    from xianyu_hunter.web.routes import api_notifications as mod

    return mod.list_notifications(
        request=_req(user_id), status=None, limit=50, offset=0, container=shim,
    )


# ==================== 1. 口径函数本体 ====================
def test_reader_user_id_value_range():
    from xianyu_hunter.web.utils import reader_user_id

    assert reader_user_id(_req("alice")) == "alice"      # 真实会话用户 → 严格过滤
    assert reader_user_id(_req("default")) is None       # WEB_TOKEN 直通 → 不过滤
    assert reader_user_id(_req("")) is None              # 空串 → 不过滤
    assert reader_user_id(_req()) is None                # 属性缺失 → 不过滤


def test_owner_user_id_never_returns_none():
    """创建侧必须拿到非空归属：NotificationRow.user_id 是 NOT NULL"""
    from xianyu_hunter.web.utils import owner_user_id

    assert owner_user_id(_req("alice")) == "alice"
    assert owner_user_id(_req("default")) == "default"
    assert owner_user_id(_req("")) == "default"
    assert owner_user_id(_req()) == "default"


def test_add_notification_normalizes_none_user_id(repo):
    """调用方手里的 user_id 完全可能是 None（单用户/后台线程）：
    列 default 只兜"不传参"，显式传 None 会撞 NOT NULL 把整条通知吞掉"""
    nid = _mk(repo, "scope-none", None)
    assert repo.get_notification(nid)["user_id"] == "default"


# ==================== 2. 路由读写同源 ====================
def test_create_stamps_session_user(repo):
    from xianyu_hunter.web.routes import api_notifications as mod

    out = mod.create_notification(
        request=_req("alice"),
        payload={"level": "warn", "category": "order", "title": "A",
                 "message": "M", "dedup_key": "scope:alice"},
        container=_ContainerShim(repo),
    )
    assert out["item"]["user_id"] == "alice"


def test_create_falls_back_to_default_when_state_missing(repo):
    from xianyu_hunter.web.routes import api_notifications as mod

    out = mod.create_notification(
        request=_req(),
        payload={"level": "info", "category": "system", "title": "B",
                 "message": "M", "dedup_key": "scope:nostate"},
        container=_ContainerShim(repo),
    )
    assert out["item"]["user_id"] == "default"


def test_session_user_only_sees_own_notifications(repo):
    from xianyu_hunter.web.routes import api_notifications as mod

    _mk(repo, "scope:alice", "alice")
    _mk(repo, "scope:bob", "bob")
    shim = _ContainerShim(repo)

    mine = _list(shim, "alice")
    assert [i["dedup_key"] for i in mine["items"]] == ["scope:alice"]
    assert mine["total"] == 1
    assert [i["dedup_key"] for i in _list(shim, "bob")["items"]] == ["scope:bob"]
    # 直通身份待在自己的 default 命名空间：既看不到 alice 的，也看不到 bob 的
    # （越权锁，与 test_order_stats_and_notif_batch.py::test_batch_delete_is_user_scoped 同口径）
    assert {i["dedup_key"] for i in _list(shim, "default")["items"]} == set()

    counts = mod.unread_count(request=_req("alice"), container=shim)
    assert counts == {"unread": 1, "read": 0, "total": 1}


def test_cross_user_mutate_is_404_for_session_users(repo):
    """真实会话用户改他人通知 → 404（不是静默成功，也不是假回执）"""
    from fastapi import HTTPException

    from xianyu_hunter.web.routes import api_notifications as mod

    nid = _mk(repo, "scope:alice", "alice")
    with pytest.raises(HTTPException) as exc:
        mod.mark_read(nid, request=_req("bob"), container=_ContainerShim(repo))
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc2:
        mod.delete_notification(nid, request=_req("bob"), container=_ContainerShim(repo))
    assert exc2.value.status_code == 404
    # 归属没被动过
    assert repo.get_notification(nid)["user_id"] == "alice"
    assert repo.get_notification(nid)["read_at"] is None


@pytest.mark.parametrize("action", ["read", "delete", "batch_delete", "read_all"])
def test_same_identity_reads_and_mutates_the_same_rows(repo, action):
    """不变量：同一身份「看得见 = 改得动」（T02618）。

    修复前读侧兜 None（全量）、改侧兜 "default"（过滤），两套值错开时
    别的命名空间的行会「列表里看得见、点标记已读/删除却 404」，
    前端表现即工单描述的「点了没反应」。
    这里用直通身份自建自改，把读写两侧钉在同一个命名空间上。
    """
    from xianyu_hunter.web.routes import api_notifications as mod

    created = mod.create_notification(
        request=_req("default"),
        payload={"level": "warn", "category": "order", "title": "V", "message": "M",
                 "dedup_key": f"scope-vis-{action}"},
        container=_ContainerShim(repo),
    )
    nid = created["item"]["id"]
    shim = _ContainerShim(repo)
    assert nid in [i["id"] for i in _list(shim, "default")["items"]], "读侧应先看到该行"

    if action == "read":
        assert mod.mark_read(nid, request=_req("default"), container=shim)["ok"] is True
    elif action == "delete":
        assert mod.delete_notification(nid, request=_req("default"), container=shim)["deleted"] is True
    elif action == "batch_delete":
        out = mod.batch_delete_notifications(
            request=_req("default"), payload={"ids": [nid]}, container=shim,
        )
        assert out == {"ok": True, "deleted": 1, "requested": 1}
    else:
        assert mod.mark_all_read(request=_req("default"), container=shim)["updated"] == 1


def test_passthrough_cannot_touch_other_namespace(repo):
    """越权锁：WEB_TOKEN 直通也看不到 / 改不动 other 用户的通知。

    通知与日志不同——日志只有读侧可以放开为不过滤（T02684 reader_user_id），
    通知有改侧，放开读侧要么连带放开改侧（越权），要么制造 404。
    """
    from fastapi import HTTPException

    from xianyu_hunter.web.routes import api_notifications as mod

    nid = _mk(repo, "scope:alice", "alice")
    shim = _ContainerShim(repo)
    assert nid not in [i["id"] for i in _list(shim, "default")["items"]]
    with pytest.raises(HTTPException) as exc:
        mod.mark_read(nid, request=_req("default"), container=shim)
    assert exc.value.status_code == 404
    out = mod.batch_delete_notifications(
        request=_req("default"), payload={"ids": [nid]}, container=shim,
    )
    assert out == {"ok": True, "deleted": 0, "requested": 1}


def test_clear_notifications_respects_scope(repo):
    from xianyu_hunter.web.routes import api_notifications as mod

    _mk(repo, "scope:alice", "alice")
    _mk(repo, "scope:bob", "bob")
    out = mod.clear_notifications(request=_req("alice"), status=None, container=_ContainerShim(repo))
    assert out["deleted"] == 1
    # 仓储层直读（不带 user 过滤）确认 bob 的行完好
    assert [i["dedup_key"] for i in repo.list_notifications(user_id=None)] == ["scope:bob"]


# ==================== 3. 引擎/后台写入的归属 ====================
def test_order_timeout_rule_scans_and_stamps_user(repo):
    """订单超时规则以前既不带范围也不带归属：用 A 的请求给全体订单生成归属 default 的通知"""
    from sqlalchemy import insert

    from xianyu_hunter.infra.db_models import OrderRow, _utcnow
    from xianyu_hunter.web.services import notification_engine as eng

    overdue = _utcnow() - timedelta(minutes=40)
    with repo.engine.begin() as conn:
        for oid, uid in (("o-alice", "alice"), ("o-bob", "bob")):
            conn.execute(insert(OrderRow).values(
                id=oid, item_id=f"i-{oid}", price=10.0, status="pending_pay",
                created_at=overdue, user_id=uid,
            ))

    scopes: list = []

    class _RepoSpy:
        """包一层 Repository：引擎走 `container.repo.list_orders(...)`，
        所以记录点必须在 repo 对象上，而不是 container 上"""

        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def list_orders(self, **kwargs):
            scopes.append(kwargs.get("user_id"))
            return self._inner.list_orders(**kwargs)

    triggered = eng.scan_order_timeouts(_ContainerShim(_RepoSpy(repo)), user_id="alice")

    assert triggered == 1, "只应命中 alice 的订单"
    assert scopes == ["alice"], "扫描范围必须按同一 user_id 收缩"
    items = repo.list_notifications(user_id="alice")
    assert [i["dedup_key"] for i in items] == ["order_timeout:o-alice:30min"]
    assert items[0]["user_id"] == "alice"
    assert repo.list_notifications(user_id="bob") == []

    # None（直通/内部调用）→ 全库扫描，通知归属由仓储兜底 default
    scopes.clear()
    triggered_all = eng.scan_order_timeouts(_ContainerShim(_RepoSpy(repo)), user_id=None)
    assert triggered_all == 2
    assert scopes == [None]
    assert {i["user_id"] for i in repo.list_notifications()} == {"alice", "default"}


def test_auth_down_rule_stamps_user(repo, tmp_path, monkeypatch):
    """掉线告警按请求者归属：alice 的账号掉线只通知 alice"""
    import xianyu_hunter.paths as paths
    from xianyu_hunter.web.services import notification_engine as eng

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "userinfo.json").write_text('{"user_id": "alice"}', encoding="utf-8")
    # _scan_auth_down 在函数内 import get_data_dir，因此要打在 paths 模块上
    monkeypatch.setattr(paths, "get_data_dir", lambda: data_dir)

    n = eng._scan_auth_down(_ContainerShim(repo), {"logged_in": False}, user_id="alice")
    assert n == 1
    rows = repo.list_notifications(user_id="alice")
    assert len(rows) == 1
    assert rows[0]["category"] == "auth"
    assert rows[0]["user_id"] == "alice"


def test_scan_and_notify_threads_user_to_both_rules(repo, monkeypatch):
    """聚合入口必须把 user_id 透传给每条规则，漏一条就又是一次同类漂移"""
    from xianyu_hunter.web.services import notification_engine as eng

    seen: list = []

    def _spy_orders(container, user_id=None):
        seen.append(("order", user_id))
        return 0

    def _spy_auth(container, auth_state, user_id=None):
        seen.append(("auth", user_id))
        return 0

    monkeypatch.setattr(eng, "scan_order_timeouts", _spy_orders)
    monkeypatch.setattr(eng, "_scan_auth_down", _spy_auth)

    stats = eng.scan_and_notify(
        _ContainerShim(repo), auth_state={"logged_in": False}, user_id="alice",
    )
    assert stats == {"order_timeout": 0, "auth_down": 0}
    assert seen == [("order", "alice"), ("auth", "alice")]


def test_price_drop_notification_follows_task_user(repo):
    """盯盘降价通知的 user_id 已在参数里，但原先没往下传给 add_notification"""
    from xianyu_hunter.modules.price_watch import _emit_drop_notifications

    info = {
        "item_id": "i-9", "item_title": "某商品", "task_id": "tk-9",
        "prev_min_price": 100.0, "new_price": 80.0, "drop_pct": 0.2,
    }
    _emit_drop_notifications(repo, None, info, user_id="alice")
    rows = repo.list_notifications(user_id="alice")
    assert [r["dedup_key"] for r in rows] == ["price_drop:i-9:80.00"]
    assert rows[0]["category"] == "price"
    # 事件时间线同样按 alice 归属
    assert repo.list_events(limit=10, user_id="alice")


def test_drop_summary_follows_task_user(repo):
    from xianyu_hunter.modules.price_watch import _emit_drop_summary

    drops = [
        {"item_id": "i-1", "item_title": "A", "task_id": "tk-1",
         "new_price": 50.0, "drop_pct": 0.5},
        {"item_id": "i-2", "item_title": "B", "task_id": "tk-1",
         "new_price": 60.0, "drop_pct": 0.3},
    ]
    _emit_drop_summary(repo, None, drops, user_id="bob")
    rows = repo.list_notifications(user_id="bob")
    assert len(rows) == 1
    assert rows[0]["dedup_key"].startswith("price_drop_summary:tk-1:")


# ==================== 4. HTTP 冒烟：直通端到端仍可用 ====================
def test_passthrough_http_flow(repo):
    """端到端：直通（WEB_TOKEN → state.user_id="default"）在自己的命名空间里读写闭环"""
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    alien = _mk(repo, "scope:http-alien", "alice")
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)
    client = TestClient(app)
    client.cookies.set("xh_token", get_settings().web_token)

    listed = client.get("/api/notifications").json()
    assert [i["dedup_key"] for i in listed["items"]] == []
    assert listed["total"] == 0

    created = client.post("/api/notifications", json={
        "level": "warn", "category": "price", "title": "H", "message": "M",
        "dedup_key": "scope:http-created",
    })
    assert created.status_code == 200
    nid = created.json()["item"]["id"]
    assert created.json()["item"]["user_id"] == "default"
    assert alien not in [i["id"] for i in client.get("/api/notifications").json()["items"]]

    assert client.post(f"/api/notifications/{nid}/read").status_code == 200
    assert client.get("/api/notifications/unread_count").json() == {"unread": 0, "read": 1, "total": 1}
    assert client.delete(f"/api/notifications/{nid}").json()["deleted"] is True


# ==================== 5. 静态守卫：口径旁路不得复活 ====================
def test_routes_use_shared_helpers_not_bare_getattr():
    """本缺陷唯一的复发形态 = 路由里再写一次裸 getattr(request.state, "user_id", ...)"""
    src = API_NOTIFICATIONS.read_text(encoding="utf-8")
    assert 'getattr(request.state, "user_id"' not in src
    assert "getattr(request.state" not in src
    assert src.count("user_id = owner_user_id(request)") == 8, "8 个端点各取一次身份"
    assert "reader_user_id(" not in src, "通知侧不得放开为不过滤（有改侧）"


def test_api_logs_reader_delegates_to_shared_helper():
    """日志侧（T02684）与通知侧（T02618）必须是同一个函数，否则又变成两套口径"""
    p = ROOT / "backend" / "xianyu_hunter" / "web" / "routes" / "api_logs.py"
    src = p.read_text(encoding="utf-8")
    assert "return reader_user_id(request)" in src
    assert 'uid = getattr(request.state, "user_id", None)' not in src
