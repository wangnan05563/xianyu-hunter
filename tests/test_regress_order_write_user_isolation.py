"""T02694 回归：订单写路径的 user_id 深度防御（跨用户 / None 边界 / 四条端点冒烟）

背景（缺陷原文见 T02585 收尾）：`api_orders` 的四个订单写端点都调用
`container.repo.upsert_order(o, user_id=user_id)`，但 `OrdersMixin.upsert_order`
当年签名里没有 `user_id` 形参 —— 任一订单状态写入必 TypeError（生产上必 500）。
本轮已补形参，并在 `on_conflict_do_update` 附加 `where=(OrderRow.user_id == user_id)`。
本文件把钉住这条防线的三种复发形态各锁一次：

1. **签名丢失**（本轮真实踩到的）：`user_id` 关键字参数必须存在于 `upsert_order` 签名。
   只跑业务用例也能发现，但失败点在运行期、报错信息是 TypeError 而非「哪个端点丢了隔离」，
   所以额外用 inspect 直接断言签名，失败信息直指根因。
2. **路由侧不再透传**：api_orders 里每个 `upsert_order` 调用点都必须带 `user_id=`，
   用 ast 扫真实调用点。这条只能靠静态守卫——实测（变异检验）把四处 `user_id=user_id`
   全删掉，18 条例题仍全绿：端点先 `get_order(order_id, user_id=...)` 拿整行，
   越权在读侧就 404 了，字典里本来就带着正确归属，WHERE 自然命中。
   也就是说删掉透传不会当场出错，只是把「两道门」悄悄降成一道，所以必须留一条不会沉默的守卫。
3. **WHERE 子句被删**：跨用户 upsert 必须命中 0 行且他人行原封不动，
   同时保留 `user_id=None`（调度器/抢单系统写入）不过滤的语义。

为什么既有测试不够：tests/test_takeover_timeout.py、tests/test_update_order_status.py
全部用 `user_id="default"` 的单身份请求（`_make_request()` 写死），跨用户那条分支
从未被执行；`test_order_stats_and_notif_batch.py` 锁的是通知域的同类防线，订单域空白。

运行：
    .venv/Scripts/python.exe -m pytest tests/test_regress_order_write_user_isolation.py -o addopts="" -p no:cacheprovider -q
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.routes import api_orders

ALICE = "alice"
BOB = "bob"


class _ContainerShim:
    """只提供路由实际用到的 `.repo`（真实 Repository，不走 mock —— mock 证不了 WHERE 生效）"""

    def __init__(self, repo: Repository):
        self.repo = repo


def _request(user_id: str) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(user_id=user_id))


@pytest.fixture
def repo(tmp_path) -> Repository:
    return Repository(db_path=str(tmp_path / "order_write_iso.db"))


def _mk_order(repo: Repository, order_id: str, user_id: str, *, status: str = "pending_pay",
              item_id: str = "i1", task_id: str = "t1") -> dict:
    """预置一条**明确归属**的订单（显式写 user_id，让断言只测写侧接线）"""
    repo.upsert_order(
        {
            "id": order_id,
            "item_id": item_id,
            "task_id": task_id,
            "price": 100.0,
            "status": status,
            "created_at": _utcnow().replace(tzinfo=None),
            "user_id": user_id,
        },
        user_id=user_id,
    )
    return repo.get_order(order_id)


def _raw(repo: Repository, order_id: str) -> dict:
    """不经 user 过滤地读回真实行，用于验证「他人行没被动过」"""
    return repo.get_order(order_id)


# ==================== 1. 仓储层：跨用户 upsert 必须命中 0 行 ====================
def test_cross_user_upsert_leaves_owner_row_untouched(repo) -> None:
    """A 用户凭 id 更新 B 用户的订单行 → WHERE 让 UPDATE 命中 0 行（静默不覆盖）

    这里刻意绕过端点的读侧闸门，直接喂「他人订单的完整字典」：
    读侧 404 只证明闸门在，写侧这道门才是数据被改掉之前的最后一层。
    """
    _mk_order(repo, "o1", BOB, status="pending_pay")
    stolen = repo.get_order("o1")  # 完整行（含 user_id=bob），模拟越权写入
    stolen["status"] = "succeeded"

    repo.upsert_order(stolen, user_id=ALICE)

    after = _raw(repo, "o1")
    assert after["status"] == "pending_pay", "跨用户 upsert 覆盖了他人的订单状态"
    assert after["user_id"] == BOB, "跨用户 upsert 改掉了订单归属"


def test_cross_user_upsert_without_user_id_key_does_not_retag(repo) -> None:
    """字典未带 user_id 时会被注入调用方身份 —— 注入的是 INSERT 侧，不能顺手改走他人行"""
    _mk_order(repo, "o1", BOB, status="pending_pay")
    partial = {"id": "o1", "item_id": "i1", "status": "succeeded"}

    repo.upsert_order(partial, user_id=ALICE)

    assert _raw(repo, "o1")["status"] == "pending_pay"
    assert repo.count_orders() == 1, "越权 upsert 不该另起一行"


def test_same_user_upsert_still_writes(repo) -> None:
    """阳性对照：防线不能靠「什么都不写」通过测试"""
    _mk_order(repo, "o1", ALICE, status="pending_pay")
    mine = repo.get_order("o1")
    mine["status"] = "takeover_pending"

    repo.upsert_order(mine, user_id=ALICE)

    after = _raw(repo, "o1")
    assert after["status"] == "takeover_pending"
    assert after["user_id"] == ALICE


def test_insert_path_stamps_user_id_when_caller_passes_dict_without_it(repo) -> None:
    """新行 + 调用方只给身份：INSERT 侧自动落列，否则读侧按 user 过滤会永远看不到自己的单"""
    repo.upsert_order(
        {"id": "new1", "item_id": "i9", "status": "pending_pay",
         "created_at": _utcnow().replace(tzinfo=None)},
        user_id=ALICE,
    )
    assert _raw(repo, "new1")["user_id"] == ALICE
    assert repo.get_order("new1", user_id=ALICE) is not None
    assert repo.get_order("new1", user_id=BOB) is None


# ==================== 2. user_id=None：系统写入路径不能被过滤误伤 ====================
def test_none_user_id_updates_any_users_row(repo) -> None:
    """调度器/抢单（modules/buyer.py 三处）调用 `upsert_order(order)` 不带 user_id。

    此时必须**不加** WHERE 过滤：这些写入点不认识「当前请求身份」，
    一旦给它兜个 default，自动抢单对已有订单行的状态回写会静默失效。
    """
    _mk_order(repo, "o1", BOB, status="pending_pay")
    row = repo.get_order("o1")
    row["status"] = "succeeded"

    repo.upsert_order(row)  # 系统路径：无 user_id

    after = _raw(repo, "o1")
    assert after["status"] == "succeeded", "user_id=None 时不该附加过滤（会误伤自动抢单写入）"
    assert after["user_id"] == BOB, "系统回写不该把归属抢到自己名下"


def test_none_user_id_new_row_lands_in_default_namespace(repo) -> None:
    """如实记录系统写入的归属：不带 user_id 建新行 → 落列 default（列的 server_default 兜住）

    这条不是「期望行为」而是现状：自动抢单产生的订单归 default，
    真实 session 用户（alice）在订单列表看不到自己任务抢到的单。
    要不要按任务归属改写，属另一单的口径裁决，本文件先把它钉成可见事实。
    """
    repo.upsert_order({"id": "sys1", "item_id": "i1", "status": "pending_pay"})

    assert _raw(repo, "sys1")["user_id"] == "default"
    assert [o["id"] for o in repo.list_orders(user_id=ALICE)] == []
    assert [o["id"] for o in repo.list_orders(user_id="default")] == ["sys1"]


# ==================== 3. 四条写端点：本人 200 冒烟 + 他人 404 且不落库 ====================
# OWNER_SMOKE 每条 = (调用工厂, 起始状态, 期望终态, 响应里的状态字段名)
def _call_takeover(repo, user_id, order_id):
    return api_orders.takeover_order(order_id, request=_request(user_id),
                                     container=_ContainerShim(repo))


def _call_confirm(repo, user_id, order_id):
    return api_orders.takeover_confirm(order_id, request=_request(user_id),
                                       container=_ContainerShim(repo))


def _call_cancel(repo, user_id, order_id):
    return api_orders.takeover_cancel(order_id, request=_request(user_id),
                                      container=_ContainerShim(repo))


def _call_patch(repo, user_id, order_id):
    return api_orders.update_order_status(order_id, {"status": "succeeded"},
                                          request=_request(user_id),
                                          container=_ContainerShim(repo))


OWNER_SMOKE = [
    pytest.param(_call_takeover, "pending_pay", "takeover_pending", "status", id="takeover"),
    pytest.param(_call_confirm, "takeover_pending", "succeeded", "status", id="takeover_confirm"),
    pytest.param(_call_cancel, "takeover_pending", "pending_pay", "status", id="takeover_cancel"),
    pytest.param(_call_patch, "pending_pay", "succeeded", "new_status", id="patch_status"),
]


@pytest.mark.parametrize("call,start_status,expected,resp_key", OWNER_SMOKE)
def test_write_endpoint_returns_ok_for_owner_and_persists(repo, call, start_status,
                                                          expected, resp_key) -> None:
    """四条写路径各一条真实落库冒烟

    缺陷原文（T02585 收尾）只手工验过 takeover→confirm 一条链路，其余三条未实测。
    resp_key 逐端点不同（PATCH 返回 new_status，三个 takeover 端点返回 status）——
    把它写进参数表，是为了让「响应契约漂移」也落在覆盖范围内。
    """
    _mk_order(repo, "o1", ALICE, status=start_status)
    # confirm 端点要求已接管时间，预置一个非空 confirmed_at 贴近真实链路
    if start_status == "takeover_pending":
        mine = repo.get_order("o1")
        mine["confirmed_at"] = _utcnow()
        repo.upsert_order(mine, user_id=ALICE)

    res = call(repo, ALICE, "o1")

    assert res["ok"] is True and res["id"] == "o1"
    assert _raw(repo, "o1")["status"] == expected
    assert res[resp_key] == expected


@pytest.mark.parametrize("call,start_status",
                         [(p.values[0], p.values[1]) for p in OWNER_SMOKE])
def test_write_endpoint_rejects_other_users_order_without_touching_it(
    repo, call, start_status
) -> None:
    """越权调用：404 之外还必须证明库里那行没被改动（读侧闸门 + 写侧 WHERE 双在）"""
    _mk_order(repo, "o1", BOB, status=start_status)
    before = _raw(repo, "o1")

    with pytest.raises(HTTPException) as exc:
        call(repo, ALICE, "o1")
    assert exc.value.status_code == 404

    after = _raw(repo, "o1")
    assert after["status"] == before["status"] == start_status
    assert after["user_id"] == BOB


def test_takeover_confirm_chain_persists_timestamps(repo) -> None:
    """接管→确认这条真实链路的字段回写（confirmed_at / paid_at）留在归属用户名下"""
    _mk_order(repo, "o1", ALICE, status="pending_pay")

    takeover = _call_takeover(repo, ALICE, "o1")
    assert takeover["takeover_deadline"]
    assert _raw(repo, "o1")["confirmed_at"] is not None

    done = _call_confirm(repo, ALICE, "o1")
    assert done["status"] == "succeeded"
    assert _raw(repo, "o1")["paid_at"] is not None
    assert _raw(repo, "o1")["user_id"] == ALICE


# ==================== 4. 静态守卫：透传不能静默丢失 ====================
def test_every_order_write_in_api_orders_passes_user_id() -> None:
    """复发的正好是本轮踩过的那条路：有人重构签名/调用点，隔离就没了。

    用 ast 扫真实调用点（文本 grep 会被 docstring 里
    「复用 upsert_order 写库，但只写 OrderRow 实际存在的列」这句注释误报）。
    """
    import ast

    tree = ast.parse(open(api_orders.__file__, encoding="utf-8").read())
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(
            node.func, "id", "")
        if fname not in ("upsert_order", "get_order", "delete_order_by_id"):
            continue
        if not any(kw.arg == "user_id" for kw in node.keywords):
            offenders.append(f"{fname}@L{node.lineno}")
    assert offenders == [], f"api_orders 存在未透传 user_id 的订单读写：{offenders}"


def test_upsert_order_signature_accepts_user_id() -> None:
    """直接钉住 T02585 的根因：路由传了 user_id=，仓储签名没有 → 生产必 TypeError。

    断言签名而不是只跑业务用例，失败信息能一眼指回「形参丢了」。
    """
    from xianyu_hunter.infra.repo_orders import OrdersMixin

    param = inspect.signature(OrdersMixin.upsert_order).parameters
    assert "user_id" in param, "OrdersMixin.upsert_order 丢了 user_id 形参"
    assert param["user_id"].default is None, "user_id 必须可省略（系统写入路径不带它）"


def test_upsert_order_emits_ownership_where_clause_only_when_user_id_given(repo) -> None:
    """防线本体在 SQL 里：捕获 upsert_order **真实下发**的语句

    为什么不复用语句构造代码来断言：那只会测一份复刻品，实现里删掉 where= 也照样绿。
    行为测试（上面那组）证明「不覆盖」，但将来有人改成「先查再更」两次写也能过，
    却丢掉原子 UPSERT；这里锁住单条 UPSERT 带归属条件 + None 时不带条件。
    """
    from sqlalchemy import event

    captured: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        captured.append(statement)

    engine = repo.engine
    event.listen(engine, "before_cursor_execute", _capture)
    try:
        repo.upsert_order({"id": "sq1", "item_id": "i1", "status": "succeeded"},
                          user_id=ALICE)
        owned = [s for s in captured if "ON CONFLICT" in s.upper()]
        assert len(owned) == 1, f"带身份的订单写入应是单条 UPSERT，实际：{captured}"
        assert "WHERE orders.user_id" in owned[0], owned[0]

        captured.clear()
        repo.upsert_order({"id": "sq2", "item_id": "i2", "status": "succeeded"})
        system = [s for s in captured if "ON CONFLICT" in s.upper()]
        assert len(system) == 1, f"系统写入同样应是单条 UPSERT，实际：{captured}"
        assert "WHERE orders.user_id" not in system[0], system[0]
    finally:
        event.remove(engine, "before_cursor_execute", _capture)


# ==================== 5. 真路由绑定：走一次真实 HTTP（TypeError 的唯一可靠暴露面）============
def test_routes_bind_and_takeover_chain_serves_over_http(repo) -> None:
    """生产故障是 500（TypeError），直调函数也能复现，但 FastAPI 层才是现场。

    用 TestClient 打真实 4 个端点：既证明路由注册得上，也证明
    WEB_TOKEN 直通（user_id=default）这条真实身份链路的写入没坏。
    """
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    _mk_order(repo, "o1", "default", status="pending_pay")

    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)
    client = TestClient(app)
    client.cookies.set("xh_token", get_settings().web_token)

    r = client.post("/api/orders/o1/takeover")
    assert r.status_code == 200, f"takeover 端点 500（签名/防线回归？）：{r.text}"
    assert r.json()["status"] == "takeover_pending"

    r = client.post("/api/orders/o1/takeover/cancel")
    assert r.status_code == 200, r.text
    assert _raw(repo, "o1")["status"] == "pending_pay"

    r = client.post("/api/orders/o1/takeover")
    assert r.status_code == 200, r.text
    r = client.post("/api/orders/o1/takeover/confirm")
    assert r.status_code == 200, r.text
    assert _raw(repo, "o1")["status"] == "succeeded"

    r = client.patch("/api/orders/o1/status", json={"status": "cancelled"})
    assert r.status_code == 200, r.text
    assert _raw(repo, "o1")["status"] == "cancelled"

    assert client.get("/openapi.json").status_code == 200
