"""订单状态字面值同源（T02585 / 3.7，T02693 收口残余裸串并加静态守卫）

钉住「后端写 pending_pay、其余各处读 pending/paid/submitting/paying」这一类静默失效：
错的字面值不会报错，只会永远命中 0 行，所以过去没有任何测试能发现它。

覆盖的都是订单主链路上真实读取状态的地方：
1. 启动迁移把旧库 pending 归一为 pending_pay（归一后仓储层不再做别名合并）；
2. 仪表盘总览 / 今日超时告警 / 趋势曲线的状态字面值；
3. 业务通知规则 OrderTimeoutRule（原先三个从未被写入的字面值 → 告警永不触发）；
4. 接管生命周期落库的每个状态都在 OrderStatus 里；
5. /api/orders 的 status 白名单：非法历史值 422，而不是静默空列表。

T02693 在此基础上补了两节：
- 静态守卫（AST）：订单状态字面值只能来自 OrderStatus，堵住「裸串长回来」这条路；
- 行为回归：trend / stats_today / business_kpi / buyer / repo_orders 五处收口后确实还在计数。

按前端实际调用的端点与真实查询函数打真实 FastAPI 应用 / 真实 SQLite，不使用 Mock 替身。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


class _ContainerShim:
    """只提供被测代码实际用到的 `.repo` / `.engine`"""

    def __init__(self, repo):
        self.repo = repo


def _repo(tmp_path):
    from xianyu_hunter.infra.repository import Repository

    return Repository(db_path=str(tmp_path / "ux585.db"))


def _api(tmp_path):
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    repo = _repo(tmp_path)
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)
    client = TestClient(app)
    # /api/* 全量需鉴权：与 tests/test_order_stats_and_notif_batch.py 同一口径
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo


def _mk_order(repo, oid: str, status: str, *, age_min: int = 0) -> None:
    repo.upsert_order({
        "id": oid,
        "task_id": "t1",
        "item_id": f"i_{oid}",
        "price": 100.0,
        "status": status,
    })
    if age_min:
        # 直接改 created_at：upsert 只会写 now，超时判定必须用「过去的」订单
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=age_min)
        from sqlalchemy import text as sa_text

        with repo.engine.begin() as conn:
            conn.execute(
                sa_text("UPDATE orders SET created_at=:c WHERE id=:i"),
                {"c": cutoff, "i": oid},
            )


# ---------------- 1. 启动迁移：旧值归一 ----------------

def test_legacy_pending_row_is_normalized_on_init(tmp_path) -> None:
    from sqlalchemy import text as sa_text

    from xianyu_hunter.infra.db_models import init_db

    repo = _repo(tmp_path)
    db_path = str(tmp_path / "ux585.db")
    # 模拟旧库：直接写入历史字面值 pending
    with repo.engine.begin() as conn:
        conn.execute(sa_text(
            "INSERT INTO orders (id, task_id, item_id, order_no, price, status, created_at) "
            "VALUES ('legacy1','t1','i1','no1',1.0,'pending','2026-01-01 00:00:00')"
        ))
    init_db(db_path)  # 重跑一次启动迁移

    rows = repo.list_orders(limit=10)
    legacy = [o for o in rows if o["id"] == "legacy1"]
    assert legacy and legacy[0]["status"] == "pending_pay"


# ---------------- 2. 读取侧：统计与告警用规范字面值 ----------------

def test_overview_pending_counts_pending_pay(tmp_path) -> None:
    """仪表盘「待处理」卡：原先 SQL 写 IN ('pending','submitting','paying')，恒 0"""
    from xianyu_hunter.web.routes.stats_overview import _query_order_stats

    repo = _repo(tmp_path)
    _mk_order(repo, "o1", "pending_pay")
    _mk_order(repo, "o2", "takeover_pending")
    _mk_order(repo, "o3", "succeeded")
    _mk_order(repo, "o4", "failed")

    total, succeeded, failed, pending = _query_order_stats(repo.engine)
    assert (total, succeeded, failed) == (4, 1, 1)
    assert pending == 1  # 只有 pending_pay 计入「待支付」


def test_timeout_query_and_alert_fire_for_pending_pay(tmp_path) -> None:
    """今日超时 + 业务通知：两个过去恒为空的地方必须一起恢复"""
    from xianyu_hunter.infra.db_models import _utcnow
    from xianyu_hunter.web.routes.stats_today import _query_timeout_pending
    from xianyu_hunter.web.services.notification_engine import scan_order_timeouts

    repo = _repo(tmp_path)
    _mk_order(repo, "old", "pending_pay", age_min=10)
    _mk_order(repo, "fresh", "pending_pay")

    now = _utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    items, total = _query_timeout_pending(
        repo.engine, _ContainerShim(repo), today_start, now - timedelta(minutes=5), now
    )
    assert total == 1 and [o["id"] for o in items] == ["old"]

    triggered = scan_order_timeouts(_ContainerShim(repo))
    assert triggered >= 1
    notes = repo.list_notifications(limit=20) or []
    assert any("已等待支付" in (n.get("title") or "") for n in notes)


def test_trend_metric_uses_canonical_pending_literal() -> None:
    """趋势曲线指标名 → 状态字面值的映射必须来自 OrderStatus（否则「待支付」曲线恒 0）"""
    from xianyu_hunter.domain.order import OrderStatus
    from xianyu_hunter.web.routes.trend import _ORDER_STATUS_METRICS

    assert _ORDER_STATUS_METRICS["orders_pending"] == OrderStatus.PENDING_PAY.value
    assert _ORDER_STATUS_METRICS["orders_succeeded"] == OrderStatus.SUCCEEDED.value
    assert set(_ORDER_STATUS_METRICS.values()) <= set(
        s.value for s in OrderStatus
    )


# ---------------- 3. 接管生命周期：每个落库状态都在枚举里 ----------------

def test_takeover_lifecycle_round_trip(tmp_path) -> None:
    from xianyu_hunter.domain.order import ORDER_STATUS_VALUES

    client, repo = _api(tmp_path)
    _mk_order(repo, "o1", "pending_pay")

    r = client.post("/api/orders/o1/takeover").json()
    assert r["status"] == "takeover_pending"
    assert client.post("/api/orders/o1/takeover/confirm").json()["status"] == "succeeded"

    stored = client.get("/api/orders/o1").json()["status"]
    assert stored in ORDER_STATUS_VALUES

    stats = client.get("/api/orders").json()["stats"]
    assert stats["pending"] == 0 and stats["takeover"] == 0 and stats["succeeded"] == 1


def test_orders_status_filter_whitelist(tmp_path) -> None:
    """历史 pending / 乱值不再静默返回空列表，而是 422 —— 口径问题要响，不要哑"""
    client, repo = _api(tmp_path)
    _mk_order(repo, "o1", "pending_pay")

    assert client.get("/api/orders", params={"status": "pending_pay"}).json()["total"] == 1
    assert client.get("/api/orders", params={"status": "pending"}).status_code == 422
    assert client.get("/api/orders", params={"status": "paid"}).status_code == 422


# ---------------- 4. 静态守卫：状态字面值只能来自 OrderStatus（T02693） ----------------
#
# 为什么必须用 AST 扫描而不是人工审查：T02585 那一轮之后，同一批错误字面值的写法在
# 8 个文件里又长回来了一次（trend / stats_today / business_kpi / buyer / repo_orders
# 各自裸写 'succeeded' / 'failed' / 'dry_run'）。裸串不报错，只是永远命中 0 行，
# 单元测试只要用同一个裸串造数据就会「一起错、一起绿」。
#
# 为什么不能只按「文件里出现 failed 就算违规」：status 是跨领域字段名，隧道、
# 登录会话、chatbot 知识库都各有自己的一套 status 取值，把它们算进来是噪音。
# 所以守卫分两条腿：
#   - 血缘明确（OrderRow.status 比较、SQL 里点到 orders 表）→ 全仓扫描；
#   - 语境含糊（dict 键、形参、下标赋值）→ 只在订单域文件清单内扫描。
# 订单域清单之外新增的订单读写点，只要碰到 OrderRow.status 或 orders 表就仍在网里。

from pathlib import Path as _Path  # noqa: E402  放在守卫段内，避免干扰上面用例的阅读顺序

_BACKEND_ROOT = _Path(__file__).resolve().parents[1] / "backend" / "xianyu_hunter"
# 订单域文件：语境含糊的字面值只在这些文件里算违规
ORDER_DOMAIN_FILES = frozenset({
    "web/routes/api_orders.py",
    "web/routes/stats_today.py",
    "web/routes/stats_overview.py",
    "web/routes/trend.py",
    "web/routes/business_kpi.py",
    "infra/repo_orders.py",
    "modules/buyer.py",
    "web/services/notification_engine.py",
})
# 枚举定义本身允许出现字面值
GUARD_EXEMPT = frozenset({"domain/order.py"})


def _scan_order_status_literals(root: _Path = _BACKEND_ROOT) -> list[str]:
    """返回「裸写订单状态字面值」的违规位置列表（file:line rule snippet）"""
    import ast
    import re

    from xianyu_hunter.domain.order import ORDER_STATUS_VALUES

    literals = set(ORDER_STATUS_VALUES)
    status_sql_re = re.compile(r"""status\s*(?:=|==|<>)\s*['"]([a-zA-Z_]+)['"]""")
    violations: list[str] = []

    def add(path: _Path, lineno: int, rule: str, snippet: str) -> None:
        violations.append(
            f"{path.relative_to(root).as_posix()}:{lineno} [{rule}] {snippet[:90]}"
        )

    for py in sorted(root.rglob("*.py")):
        rel = py.relative_to(root).as_posix()
        if rel in GUARD_EXEMPT:
            continue
        src = py.read_text(encoding="utf-8-sig")
        try:
            tree = ast.parse(src, filename=str(py))
        except SyntaxError:  # pragma: no cover - 坏文件由导入/收集阶段暴露
            continue
        in_order_domain = rel in ORDER_DOMAIN_FILES

        for node in ast.walk(tree):
            # R-CMP：与裸字面值比较，且比较对象明确指向订单状态
            if isinstance(node, ast.Compare):
                rendered = ast.unparse(node)
                squash = rendered.lower().replace(" ", "")
                lineage = "orderrrow.status" in squash
                looks_like_status = "status" in rendered.lower()
                for comp in [node.left, *node.comparators]:
                    if isinstance(comp, ast.Constant) and comp.value in literals:
                        if lineage or (in_order_domain and looks_like_status):
                            add(py, node.lineno, "CMP", rendered)
                for comp in node.comparators:
                    if isinstance(comp, (ast.List, ast.Tuple)) and any(
                        isinstance(e, ast.Constant) and e.value in literals for e in comp.elts
                    ):
                        if lineage or (in_order_domain and looks_like_status):
                            add(py, node.lineno, "LIST", rendered)

            # R-SQL：字符串常量里的裸 SQL 点到 orders 表又写了状态字面值（全仓）
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for m in status_sql_re.finditer(node.value):
                    if m.group(1).lower() in literals and "order" in node.value.lower():
                        add(py, getattr(node, "lineno", 0), "SQL", m.group(0))

            if not in_order_domain:
                continue

            # R-DICT：{"status": "succeeded"}
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if (
                        isinstance(k, ast.Constant) and k.value == "status"
                        and isinstance(v, ast.Constant) and v.value in literals
                    ):
                        add(py, node.lineno, "DICT", 'status="{}"'.format(v.value))

            # R-KWARG：update(...).values(status="failed")
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if (
                        kw.arg == "status"
                        and isinstance(kw.value, ast.Constant) and kw.value.value in literals
                    ):
                        add(py, node.lineno, "KWARG", ast.unparse(node.func))

            # R-ASSIGN：o["status"] = "failed"
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if (
                        isinstance(t, ast.Subscript)
                        and isinstance(t.slice, ast.Constant) and t.slice.value == "status"
                        and isinstance(node.value, ast.Constant) and node.value.value in literals
                    ):
                        add(py, node.lineno, "ASSIGN", ast.unparse(t))
    return violations


def test_no_bare_order_status_literal_in_backend() -> None:
    assert _scan_order_status_literals() == []


@pytest.mark.parametrize(
    "source,expected_rules",
    [
        # 每条都是本轮真实修掉的写法，规则必须逐条抓得住（否则守卫是自欺欺人）
        ('o.get("status") == "succeeded"', {"CMP"}),
        ("OrderRow.status == 'failed'", {"CMP"}),
        ('conn.execute(sa_text("SELECT 1 FROM orders WHERE status = \'dry_run\'"))', {"SQL"}),
        ('repo.upsert_order({"id": "1", "status": "pending_pay"})', {"DICT"}),
        ('conn.execute(update(OrderRow).values(status="failed"))', {"KWARG"}),
        ('expired[0]["status"] = "succeeded"', {"ASSIGN"}),
        ('ok if status in ("succeeded", "failed") else 0', {"LIST"}),
    ],
)
def test_guard_rules_catch_the_patterns_being_removed(source, expected_rules) -> None:
    """把守卫打在合成源码上：每条被移除的写法都要能复现告警"""
    import tempfile

    # 合成文件放进订单域清单（用清单里的真实文件名），语境含糊规则才会生效
    with tempfile.TemporaryDirectory() as td:
        root = _Path(td) / "infra"
        root.mkdir(parents=True)
        (root / "repo_orders.py").write_text(source, encoding="utf-8")
        found = _scan_order_status_literals(_Path(td))
    assert found, f"规则未命中：{source}"
    assert {r.split("]")[0].split("[")[1] for r in found} & expected_rules


def test_guard_rules_ignore_foreign_status_vocabularies() -> None:
    """隧道 / 会话 / 知识库的 status 取值不该被误伤（否则守卫会变成噪音源）"""
    import tempfile

    noisy = "\n".join([
        'if result.get("status") == "failed":',
        "    pass",
        '_session["status"] = "failed"',                 # 登录会话
        'kb = {"status": "failed"}',                     # 知识库构建结果
        'y = OrderRow.id == "failed"',                   # 不是状态列
    ])
    with tempfile.TemporaryDirectory() as td:
        root = _Path(td)
        (root / "web" / "routes").mkdir(parents=True)
        (root / "web" / "routes" / "api_tunnel.py").write_text(noisy, encoding="utf-8")
        assert _scan_order_status_literals(root) == []


# ---------------- 5. 行为回归：五处收口后确实还在计数 ----------------
# 静态守卫只保证「写法统一」，本节保证「改了没改坏」——两边都要，
# 因为把裸串换成 OrderStatus.SUCCEEDED.value 本身就可能拼错成员名。

def test_trend_success_rate_rows_follow_order_status(tmp_path) -> None:
    from xianyu_hunter.web.routes.trend import _build_success_rate_rows

    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    orders = [
        {"created_at": datetime.now(timezone.utc), "status": "succeeded"},
        {"created_at": datetime.now(timezone.utc), "status": "pending_pay"},
        {"created_at": datetime.now(timezone.utc), "status": "failed"},
    ]
    values = [v for _, v in _build_success_rate_rows(orders, cutoff)]
    assert values == [1.0, 0.0, 0.0]


def test_stats_today_order_counts_and_failed_list(tmp_path) -> None:
    from xianyu_hunter.web.routes.stats_today import _query_failed_orders, _query_order_stats

    repo = _repo(tmp_path)
    _mk_order(repo, "ok1", "succeeded")
    _mk_order(repo, "ok2", "succeeded")
    _mk_order(repo, "bad1", "failed")
    _mk_order(repo, "wait1", "pending_pay")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total, succeeded, failed = _query_order_stats(repo.engine, today_start)
    assert (total, succeeded, failed) == (4, 2, 1)

    detail_ids = sorted(o["id"] for o in _query_failed_orders(
        repo.engine, _ContainerShim(repo), today_start
    ))
    assert detail_ids == ["bad1"]


def test_business_kpi_order_success_rate_counts_succeeded(tmp_path) -> None:
    from xianyu_hunter.web.routes.business_kpi import _kpi_order_success_rate

    repo = _repo(tmp_path)
    _mk_order(repo, "ok1", "succeeded")
    _mk_order(repo, "bad1", "failed")
    _mk_order(repo, "wait1", "pending_pay")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cur_paid, cur_total, prev_paid, prev_total = _kpi_order_success_rate(
        repo.engine, now - timedelta(hours=1), now,
        now - timedelta(days=2), now - timedelta(days=1),
    )
    assert (cur_paid, cur_total) == (1, 3)
    assert (prev_paid, prev_total) == (0, 0)


def test_dry_run_order_lands_dry_run_status(tmp_path) -> None:
    """演练落单：status 必须是 dry_run（前端按它出红色徽标、统计按它排除）"""
    from types import SimpleNamespace

    from xianyu_hunter.domain.order import OrderStatus
    from xianyu_hunter.modules.buyer import Buyer

    repo = _repo(tmp_path)
    Buyer._record_dry_run_order(
        SimpleNamespace(repo=repo), "t1", "i_dry", 9.9, {"total_ms": 1}
    )
    rows = [o for o in repo.list_orders(limit=10) if o["item_id"] == "i_dry"]
    assert len(rows) == 1
    assert rows[0]["status"] == OrderStatus.DRY_RUN.value
    assert rows[0]["type"] == "dry_run"


def test_repo_orders_failed_helpers_stay_canonical(tmp_path) -> None:
    """repo_orders 三处 failed 判定/落库收口后行为不变"""
    from sqlalchemy import text as sa_text

    from xianyu_hunter.domain.order import OrderStatus
    from xianyu_hunter.infra.db_models import _utcnow

    repo = _repo(tmp_path)
    _mk_order(repo, "f1", "failed")
    _mk_order(repo, "p1", "pending_pay")

    # find_order_by_task_item：failed 视为「没有」，允许重抢
    assert repo.find_order_by_task_item("t1", "i_f1") is None
    assert repo.find_order_by_task_item("t1", "i_p1")["id"] == "p1"

    # list_orders_by_item_ids：默认跳过 failed，include_failed 才保留
    assert set(repo.list_orders_by_item_ids(["i_f1", "i_p1"])) == {"i_p1"}
    assert set(repo.list_orders_by_item_ids(["i_f1", "i_p1"], include_failed=True)) == {"i_f1", "i_p1"}

    # expire_takeover_pending_orders：批量 update 落规范值（confirmed_at 需早于 cutoff）
    _mk_order(repo, "to1", "takeover_pending")
    with repo.engine.begin() as conn:
        conn.execute(
            sa_text("UPDATE orders SET confirmed_at=:c WHERE id='to1'"),
            {"c": _utcnow().replace(tzinfo=None) - timedelta(seconds=30)},
        )
    assert [o["id"] for o in repo.expire_takeover_pending_orders(0)] == ["to1"]
    assert repo.get_order("to1")["status"] == OrderStatus.FAILED.value
