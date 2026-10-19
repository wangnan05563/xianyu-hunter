"""订单状态字面值同源（T02585 / 3.7）

钉住「后端写 pending_pay、其余各处读 pending/paid/submitting/paying」这一类静默失效：
错的字面值不会报错，只会永远命中 0 行，所以过去没有任何测试能发现它。

覆盖的都是订单主链路上真实读取状态的地方：
1. 启动迁移把旧库 pending 归一为 pending_pay（归一后仓储层不再做别名合并）；
2. 仪表盘总览 / 今日超时告警 / 趋势曲线的状态字面值；
3. 业务通知规则 OrderTimeoutRule（原先三个从未被写入的字面值 → 告警永不触发）；
4. 接管生命周期落库的每个状态都在 OrderStatus 里；
5. /api/orders 的 status 白名单：非法历史值 422，而不是静默空列表。

按前端实际调用的端点与真实查询函数打真实 FastAPI 应用 / 真实 SQLite，不使用 Mock 替身。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


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
