"""T02684 回归：日志路由的多用户隔离（list / search / export / tag / 链路聚合）

背景（缺陷原文）：`api_logs.py` 全文零处 user_id——`_fetch_log_candidates` 调
`list_events` / `list_events_by_request` 均未传 user_id，`/api/logs`、`/api/logs/search`、
`/api/logs/export` 因此跨用户返回全部日志。两个仓储方法本身早已支持隔离，
鉴权链路也已把身份放进 `request.state.user_id`——能力齐备，只差接线。

为什么断言直接调用路由函数而不是走 HTTP：
- 身份来自鉴权中间件写入的 `request.state.user_id`，走 HTTP 需要签发真实 session
  token（`user_manager.issue_session` 要碰引擎与缓存），那部分已有专测
  （tests/test_auth_middleware_mu2.py）；本单要锁的是「路由有没有把身份透传到仓储」，
  用 SimpleNamespace 造 request.state 最直接，也不会因为鉴权细节变动而假红。
- 额外补一条静态守卫（test_no_unfiltered_event_query_left_in_api_logs），
  防止以后新增端点又走回「不传 user_id」的老路——这是本缺陷唯一的复发形态。

运行：
    .venv/Scripts/python.exe -m pytest tests/test_regress_logs_user_isolation.py -o addopts="" -p no:cacheprovider -q
"""
from __future__ import annotations

import asyncio
import csv
import io
from types import SimpleNamespace

import pytest

from xianyu_hunter.infra import repo_events
from xianyu_hunter.web.routes import api_logs

R_ID = "req-20260701120000537-a3b2c1"  # 合法 request_id：req-<17 位数字>-<6 位 hex>


class _ContainerShim:
    """只提供路由实际用到的 `.repo`"""

    def __init__(self, repo):
        self.repo = repo


def _request(user_id: str | None):
    """模拟鉴权中间件注入的身份；传 NoState 表示中间件根本没写这个属性"""
    if user_id is _NO_STATE:
        return SimpleNamespace(state=SimpleNamespace())
    return SimpleNamespace(state=SimpleNamespace(user_id=user_id))


_NO_STATE = object()


@pytest.fixture
def repo(tmp_path):
    from xianyu_hunter.infra.repository import Repository

    return Repository(db_path=str(tmp_path / "logs_iso.db"))


@pytest.fixture
def shim(repo):
    return _ContainerShim(repo)


def _mk_event(repo, user_id: str, message: str, *, request_id: str | None = None,
              level: str = "info", task_id: str | None = "t1") -> int:
    """写入一条明确归属的事件（显式传 user_id，绕开后台兜底口径，保证断言只测读侧接线）"""
    row: dict = {
        "type": "task.search_done",
        "task_id": task_id,
        "stage": "search",
        "level": level,
        "message": message,
        "payload": None,
        "user_id": user_id,
    }
    if request_id:
        row["request_id"] = request_id
    return repo.save_event(row)


def _msgs(items) -> list[str]:
    return [i.get("message") or "" for i in items]


# ==================== 1. /api/logs（source=db） ====================
def test_list_logs_db_only_returns_session_user_rows(shim, repo) -> None:
    _mk_event(repo, "alice", "alice-1")
    _mk_event(repo, "alice", "alice-2")
    _mk_event(repo, "bob", "bob-1")
    _mk_event(repo, "default", "default-1")

    res = api_logs.list_logs(request=_request("alice"), source="db", limit=100, container=shim)
    assert sorted(_msgs(res["items"])) == ["alice-1", "alice-2"]
    assert res["count"] == 2


def test_list_logs_db_management_token_sees_all(shim, repo) -> None:
    """WEB_TOKEN 直通（user_id=default）＝单用户/运维视角，保持看全量（见 _reader_user_id 口径）"""
    _mk_event(repo, "alice", "alice-1")
    _mk_event(repo, "default", "default-1")

    as_default = api_logs.list_logs(request=_request("default"), source="db", limit=100, container=shim)
    assert sorted(_msgs(as_default["items"])) == ["alice-1", "default-1"]
    # 中间件没写身份（内部调用/未鉴权路径）同样不过滤，行为与历史一致
    as_none = api_logs.list_logs(request=_request(_NO_STATE), source="db", limit=100, container=shim)
    assert sorted(_msgs(as_none["items"])) == ["alice-1", "default-1"]


# ==================== 2. /api/logs/search ====================
def test_search_logs_filters_by_user(shim, repo) -> None:
    _mk_event(repo, "alice", "订单支付成功", level="err")
    _mk_event(repo, "alice", "搜索完成", level="info")
    _mk_event(repo, "bob", "订单支付成功", level="err")

    # 带等级过滤：DB 侧按 level 粗筛 + 按 user 过滤，两条条件都不能少
    res = api_logs.search_logs(request=_request("alice"), q=None, level="ERR", tag=None,
                               task_id=None, stage=None, request_id=None, start=None,
                               end=None, since_id=None, limit=50, offset=0, container=shim)
    assert _msgs(res["items"]) == ["订单支付成功"]
    assert res["matched_levels"] == {"err": 1}

    # 不带等级过滤：bob 的同名行仍然不能出现
    res_all = api_logs.search_logs(request=_request("alice"), q=None, level=None, tag=None,
                                   task_id=None, stage=None, request_id=None, start=None,
                                   end=None, since_id=None, limit=50, offset=0, container=shim)
    assert sorted(_msgs(res_all["items"])) == ["搜索完成", "订单支付成功"]
    assert res_all["matched_levels"] == {"err": 1, "info": 1}


def test_search_logs_keyword_does_not_leak_other_users(shim, repo) -> None:
    _mk_event(repo, "alice", "alice 的隐私路径 /data/alice/token.json")
    _mk_event(repo, "bob", "bob 的隐私路径 /data/bob/token.json")

    res = api_logs.search_logs(request=_request("alice"), q="隐私路径", level=None, tag=None,
                               task_id=None, stage=None, request_id=None, start=None,
                               end=None, since_id=None, limit=50, offset=0, container=shim)
    assert _msgs(res["items"]) == ["alice 的隐私路径 /data/alice/token.json"]


def test_search_logs_request_id_branch_is_filtered(shim, repo) -> None:
    """request_id 走的是另一条仓储方法（list_events_by_request）——历史上正是这条分支漏传"""
    _mk_event(repo, "alice", "alice-link", request_id=R_ID)
    _mk_event(repo, "bob", "bob-link", request_id=R_ID)

    res = api_logs.search_logs(request=_request("alice"), q=None, level=None, tag=None,
                               task_id=None, stage=None, request_id=R_ID, start=None,
                               end=None, since_id=None, limit=50, offset=0, container=shim)
    assert _msgs(res["items"]) == ["alice-link"]
    # bob 的 request_id 查别人的链路 → 空（不是「返回对方的行」）
    _mk_event(repo, "carol", "carol-link", request_id="req-20260701120000537-cccccc")
    res2 = api_logs.search_logs(request=_request("carol"), q=None, level=None, tag=None,
                                task_id=None, stage=None, request_id=R_ID, start=None,
                                end=None, since_id=None, limit=50, offset=0, container=shim)
    assert res2["items"] == []


# ==================== 3. /api/logs/export ====================
async def _collect_body(resp) -> str:
    chunks = [part async for part in resp.body_iterator]
    return "".join(c.decode("utf-8") if isinstance(c, bytes) else c for c in chunks)


def test_export_logs_csv_contains_only_session_user_rows(shim, repo) -> None:
    _mk_event(repo, "alice", "A1")
    _mk_event(repo, "alice", "A2")
    _mk_event(repo, "bob", "B1")

    resp = api_logs.export_logs(request=_request("alice"), format="csv", q=None, level=None,
                                tag=None, task_id=None, stage=None, start=None, end=None,
                                limit=1000, container=shim)
    text = asyncio.run(_collect_body(resp))
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][:2] == ["id", "created_at"]
    messages = sorted(r[6] for r in rows[1:] if r)
    assert messages == ["A1", "A2"], f"导出 CSV 混入了他人日志：{messages}"


def test_export_logs_csv_for_token_session_still_all(shim, repo) -> None:
    _mk_event(repo, "alice", "A1")
    _mk_event(repo, "default", "D1")

    resp = api_logs.export_logs(request=_request("default"), format="csv", q=None, level=None,
                                tag=None, task_id=None, stage=None, start=None, end=None,
                                limit=1000, container=shim)
    rows = [r for r in csv.reader(io.StringIO(asyncio.run(_collect_body(resp)))) if r][1:]
    assert sorted(r[6] for r in rows) == ["A1", "D1"]


# ==================== 4. tag / untag 深度防御 ====================
def test_tag_other_users_event_is_404_and_payload_untouched(shim, repo) -> None:
    from fastapi import HTTPException

    bob_id = _mk_event(repo, "bob", "bob-row", level="err")

    with pytest.raises(HTTPException) as exc:
        api_logs.tag_event(request=_request("alice"), event_id=bob_id, tag="mine", container=shim)
    assert exc.value.status_code == 404
    # 读侧挡住了还不够：payload 必须真的没被改（update_event_payload 的 WHERE 也带 user_id）
    assert repo.get_event(bob_id, user_id="bob").get("payload") in (None, "")

    ok = api_logs.tag_event(request=_request("bob"), event_id=bob_id, tag="his", container=shim)
    assert ok["tags"] == ["his"]
    with pytest.raises(HTTPException):
        api_logs.untag_event(request=_request("alice"), event_id=bob_id, tag="his", container=shim)
    # 对方删不掉，本人可以（幂等口径不变）
    assert api_logs.untag_event(request=_request("bob"), event_id=bob_id, tag="his",
                                container=shim)["tags"] == []


def test_get_event_user_id_param_is_optional_backcompat(repo) -> None:
    """不传 user_id 时行为与历史一致（其它调用点未接线前不能因为默认过滤而拿不到行）"""
    eid = _mk_event(repo, "alice", "A1")
    assert repo.get_event(eid) is not None
    assert repo.get_event(eid, user_id="alice") is not None
    assert repo.get_event(eid, user_id="bob") is None


# ==================== 5. 全链路聚合 ====================
def test_request_chain_filters_events_and_flags_error_logs(shim, repo) -> None:
    _mk_event(repo, "alice", "alice-chain", request_id=R_ID)
    _mk_event(repo, "bob", "bob-chain", request_id=R_ID)
    repo.save_error_log({
        "error_type": "ValueError",
        "error_message": "bob-error",
        "request_id": R_ID,
        "user_id": "bob",
    })

    res = api_logs.get_request_chain(request=_request("alice"), request_id=R_ID,
                                     limit=100, container=shim)
    evs = [c for c in res["chain"] if c.get("_source") == "event"]
    assert [e["message"] for e in evs] == ["alice-chain"]
    assert res["events_total"] == 1
    # T02800：error_logs 已带 user_id，异常分支也按用户过滤，标志位表示「本次响应确实过滤过」
    assert res["error_logs_isolated"] is True
    assert [c for c in res["chain"] if c.get("_source") == "error_log"] == []

    as_default = api_logs.get_request_chain(request=_request("default"), request_id=R_ID,
                                            limit=100, container=shim)
    assert as_default["error_logs_isolated"] is False
    assert sorted(c["message"] for c in as_default["chain"] if c.get("_source") == "event") == [
        "alice-chain", "bob-chain"]
    assert [c["error_message"] for c in as_default["chain"]
            if c.get("_source") == "error_log"] == ["bob-error"]


def test_request_chain_rejects_invalid_request_id(shim) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        api_logs.get_request_chain(request=_request("alice"), request_id="not-a-rid",
                                   limit=10, container=shim)


# ==================== 6. 写侧归属兜底 ====================
def test_save_event_stamps_active_user_when_caller_silent(repo, monkeypatch) -> None:
    """后台写入点（worker/scheduler/notify hub 等 12 处）都没传 user_id：
    读侧一旦隔离，这些行会永远留在 default 上、真实用户看不到自己的日志。
    save_event 用单一入口补「当前活跃用户」，新写入点默认归属正确。"""
    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "alice")
    eid = repo.save_event({"type": "task.search_done", "stage": "search",
                           "level": "info", "message": "no-owner"})
    assert repo.get_event(eid)["user_id"] == "alice"


def test_save_event_keeps_explicit_user_id(repo, monkeypatch) -> None:
    monkeypatch.setattr(repo_events, "_active_user_id_for_background_write", lambda: "alice")
    eid = repo.save_event({"type": "task.search_done", "stage": "search", "level": "info",
                           "message": "explicit", "user_id": "bob"})
    assert repo.get_event(eid)["user_id"] == "bob"


def test_active_user_helper_delegates_to_user_manager(monkeypatch) -> None:
    """口径必须与 worker 读 cookie 用的同源（get_active_user_id），否则「日志归 A、cookie 归 B」"""
    calls: list = []

    class _UM:
        def get_active_user_id(self_inner):
            calls.append(1)
            return "carol"

    import xianyu_hunter.web.services.user_manager as um

    monkeypatch.setattr(um, "get_user_manager", lambda: _UM())
    assert repo_events._active_user_id_for_background_write() == "carol"
    assert calls == [1]


def test_active_user_helper_degrades_to_default_on_error(monkeypatch) -> None:
    """用户体系未就绪时降级 default——日志归属写错可查，写入抛异常会直接吞事件"""
    import xianyu_hunter.web.services.user_manager as um

    def _boom():
        raise RuntimeError("engine not ready")

    monkeypatch.setattr(um, "get_user_manager", _boom)
    assert repo_events._active_user_id_for_background_write() == "default"


# ==================== 7. 静态守卫：隔离旁路不能复活 ====================
def test_no_unfiltered_event_query_left_in_api_logs() -> None:
    """本缺陷的复发形态只有一个：新端点又调 list_events*/get_event 而不传 user_id。

    用 ast 解析真实调用点（而不是文本 grep——模块 docstring 里就有一句
    「复用 list_events(level=) 已有索引」，纯文本断言会被注释误报）。
    """
    import ast

    path = api_logs.__file__
    tree = ast.parse(open(path, encoding="utf-8").read())
    guarded = ("list_events", "list_events_by_request", "get_event")
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(
            node.func, "id", "")
        if fname not in guarded:
            continue
        if not any(kw.arg == "user_id" for kw in node.keywords):
            offenders.append(f"{fname}@L{node.lineno}")
    assert offenders == [], f"api_logs 存在未透传 user_id 的 events 查询：{offenders}"


# ==================== 8. 真路由绑定（直调函数不能证明 FastAPI 能装上）====================
def test_routes_still_bind_and_serve_through_fastapi(tmp_path, repo) -> None:
    """给 5 个端点各加一个 `request: Request` 形参，最大风险是路由根本注册不上
    （Request 位置写错、或 Body/Query 混排导致 FastAPI 启动期报错）。
    这里用 TestClient 走一次真实 HTTP，顺带证明 WEB_TOKEN 直通＝看全量的线上行为没变。
    """
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    _mk_event(repo, "alice", "A1")
    _mk_event(repo, "default", "D1")

    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)
    client = TestClient(app)
    client.cookies.set("xh_token", get_settings().web_token)

    r = client.get("/api/logs", params={"source": "db", "limit": 50})
    assert r.status_code == 200, r.text
    assert sorted(_msgs(r.json()["items"])) == ["A1", "D1"]  # 直通会话不过滤（单用户视角）

    r = client.get("/api/logs/search", params={"limit": 50})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 2

    r = client.get("/api/logs/export", params={"format": "csv", "limit": 50})
    assert r.status_code == 200, r.text
    assert "attachment" in r.headers.get("content-disposition", "")
    assert len([x for x in r.text.splitlines() if x]) == 3  # 表头 + 2 行

    r = client.get("/api/logs/request/not-a-rid")
    assert r.status_code == 400

    # OpenAPI 能生成 = 五个签名的参数排布都合法（启动期校验的真实产物）
    assert client.get("/openapi.json").status_code == 200


def test_reader_user_id_semantics() -> None:
    """_reader_user_id 的三条分支是本次修复的全部决策面，单独锁住避免被「顺手优化」掉"""
    assert api_logs._reader_user_id(_request("alice")) == "alice"
    assert api_logs._reader_user_id(_request("default")) is None
    assert api_logs._reader_user_id(_request(_NO_STATE)) is None
    assert api_logs._reader_user_id(_request("")) is None
