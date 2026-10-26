"""抢单记录日期区间筛选（T02829 ①）

告警深链要能表达「今天」，前提是订单列表 API 有日期参数（此前只有
status / task_id / item_id，评估列表反而早有 start_time/end_time）。
本单只落**口径中立**的那一半：参数收「调用方算好的时间点」，
全应用「今日」按本地日还是 UTC 日属 T02734 未裁决的产品口径，
裁决完只改前端发哪一天，后端语义不动。

钉住：
1. 区间收窄列表与 total，两端边界同源；
2. 裸日期当终点覆盖当天整天（否则 23:30 的记录会被 00:00 边界切掉）；
3. 带时区的 ISO 串按其自身时区换算到 UTC，而不是丢掉偏移当本地时间读；
4. 无法解析 422 而非静默降级（与 status / type / sort_by 同一口径）；
5. 四张状态卡保持全量口径（与 T02673 的 type 同一文档化语义）。

按前端实际调用的端点打真实 FastAPI 应用，与 test_orders_type_filter.py 同口径。
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

import pytest

ORDERS_ROUTE = (
    Path(__file__).resolve().parents[1]
    / "backend" / "xianyu_hunter" / "web" / "routes" / "api_orders.py"
)


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

    repo = Repository(db_path=str(tmp_path / "t02829.db"))
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)

    client = TestClient(app)
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo


def _mk(repo, oid: str, created_at: datetime, status: str = "succeeded") -> None:
    repo.upsert_order({
        "id": oid,
        "task_id": "t1",
        "item_id": f"i_{oid}",
        "price": 100.0,
        "status": status,
        "created_at": created_at,
    })


def test_date_range_narrows_list_and_total(api) -> None:
    client, repo = api
    _mk(repo, "d3", datetime(2026, 10, 3, 12))
    _mk(repo, "d4", datetime(2026, 10, 4, 12))
    _mk(repo, "d5", datetime(2026, 10, 5, 12))

    res = client.get("/api/orders", params={
        "start_time": "2026-10-04", "end_time": "2026-10-04"}).json()
    assert [o["id"] for o in res["items"]] == ["d4"]
    assert res["total"] == 1

    # 只给下界：当天 00:00 起全部
    res = client.get("/api/orders", params={"start_time": "2026-10-04"}).json()
    assert sorted(o["id"] for o in res["items"]) == ["d4", "d5"]


def test_bare_end_date_covers_whole_day(api) -> None:
    """裸日期当终点必须覆盖到 23:59:59，否则「选一天」只剩 00:00 那一刻"""
    client, repo = api
    _mk(repo, "early", datetime(2026, 10, 4, 0, 0, 1))
    _mk(repo, "late", datetime(2026, 10, 4, 23, 30))
    _mk(repo, "next", datetime(2026, 10, 5, 0, 0, 1))

    res = client.get("/api/orders", params={
        "start_time": "2026-10-04", "end_time": "2026-10-04"}).json()
    assert sorted(o["id"] for o in res["items"]) == ["early", "late"]
    assert res["total"] == 2


def test_offset_iso_is_converted_to_utc_not_read_as_wall_time(api) -> None:
    """时区边界用例：+08:00 的早上 9 点＝UTC 01:00，按自身时区换算而非丢掉偏移"""
    client, repo = api
    _mk(repo, "before", datetime(2026, 10, 5, 0, 30))   # UTC 00:30 → 早于边界
    _mk(repo, "after", datetime(2026, 10, 5, 1, 30))    # UTC 01:30 → 晚于边界

    res = client.get("/api/orders", params={
        "start_time": "2026-10-05T09:00:00+08:00"}).json()
    assert [o["id"] for o in res["items"]] == ["after"]


def test_unparsable_date_returns_422(api) -> None:
    client, repo = api
    _mk(repo, "d4", datetime(2026, 10, 4, 12))
    for bad in ("abc", "2026-13-45", "2026/10/04 99:00:00"):
        res = client.get("/api/orders", params={"start_time": bad})
        assert res.status_code == 422, bad
        res = client.get("/api/orders", params={"end_time": bad})
        assert res.status_code == 422, bad
    # 非法参数打完，默认查询照常
    assert client.get("/api/orders").json()["total"] == 1


def test_date_combines_with_status_filter(api) -> None:
    client, repo = api
    _mk(repo, "ok", datetime(2026, 10, 4, 12))
    _mk(repo, "bad", datetime(2026, 10, 4, 13), status="failed")
    _mk(repo, "old", datetime(2026, 10, 1, 12), status="failed")

    res = client.get("/api/orders", params={
        "start_time": "2026-10-04", "end_time": "2026-10-04", "status": "failed"}).json()
    assert [o["id"] for o in res["items"]] == ["bad"]
    assert res["total"] == 1


def test_stats_cards_stay_full_scope_under_date_filter(api) -> None:
    """状态卡是全量口径：日期筛选只收窄列表与 total，不重算卡片（与 type 同语义）"""
    client, repo = api
    _mk(repo, "old", datetime(2026, 10, 1, 12))
    _mk(repo, "new", datetime(2026, 10, 4, 12))

    res = client.get("/api/orders", params={"start_time": "2026-10-04"}).json()
    assert res["total"] == 1
    assert res["stats"]["total"] == 2


# ==== 静态守卫：筛选参数必须透传到 list 与 count 两侧 ====
# 「路由收到参数但没往下传」在运行时是静默失效——列表照旧全量、total 照旧全量，
# 断言只挑一个具体值才能撞见，加参数时很容易漏。本项目同类缺陷（user_id 透传丢失）
# 只能靠 ast 守卫发现，所以每加一个筛选参数都要在这里登记它去了哪个 repo 形参。
_ROUTE_PARAM_RENAMES = {
    # 路由形参 → repo 形参（不同名的那几个）
    "type": "order_type",
    "start_time": "created_after",
    "end_time": "created_before",
}
# 分页两参在路由内折算成 limit/offset，本身不同名透传
_PAGINATION_DERIVED = {"page_num", "page_size"}
# count 只要条数：每页条数与排序不进 count
_COUNT_SKIP = {"limit", "sort_by", "sort_dir"}


def _is_query_node(node) -> bool:
    """默认值是不是 Query(...)（其余形参是 request / container 依赖注入）"""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "Query")


def _query_param_names(route) -> set[str]:
    """ast 把默认值放在 args.defaults 里与形参尾部对齐，不能直接从 arg 上取"""
    defaults = route.args.defaults
    offset = len(route.args.args) - len(defaults)
    return {
        arg.arg for i, arg in enumerate(route.args.args)
        if i >= offset and _is_query_node(defaults[i - offset])
    }


def test_every_list_orders_query_param_is_forwarded_to_repo() -> None:
    source = ORDERS_ROUTE.read_text(encoding="utf-8")
    route = next(
        node for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name == "list_orders"
    )
    query_params = _query_param_names(route)
    assert {"start_time", "end_time"} <= query_params

    forwarded = {
        call.func.attr: {kw.arg for kw in call.keywords if kw.arg}
        for call in ast.walk(route)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
        and call.func.attr in ("list_orders", "count_orders")
    }
    assert set(forwarded) == {"list_orders", "count_orders"}
    for repo_call, kwargs in forwarded.items():
        for param in sorted(query_params):
            if param in _PAGINATION_DERIVED:
                continue
            if repo_call == "count_orders" and param in _COUNT_SKIP:
                continue
            target = _ROUTE_PARAM_RENAMES.get(param, param)
            assert target in kwargs, f"{repo_call} 漏传筛选参数 {param}（应为 {target}）"
