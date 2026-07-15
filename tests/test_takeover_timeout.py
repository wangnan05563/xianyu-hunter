"""接管超时清理与状态机白名单测试

覆盖三个严重问题修复：
1. 接管超时定时清理任务（TakeoverTimeoutScheduler + repo.expire_takeover_pending_orders）
2. takeover_order 禁止 takeover_pending → takeover_pending 重置
3. takeover_order 拒绝 failed/succeeded/cancelled 等终态订单

测试覆盖：
- repo.expire_takeover_pending_orders：超时订单被批量 failed、未超时保留、confirmed_at 清空
- TakeoverTimeoutScheduler：start/stop/任务执行
- takeover_order：仅 pending_pay 起始状态可被接管
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from xianyu_hunter.infra.db_models import OrderRow, _utcnow
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.routes import api_orders


# ============== 测试用 Repository fixture ==============


@pytest.fixture
def make_repo(tmp_path):
    """返回一个工厂函数，每次调用构造一个独立 repo 并预填订单数据

    为什么用工厂模式而非直接 fixture：不同测试需要预填不同订单数据，
    工厂模式让测试可以按需构造，并自动通过 pytest tmp_path 清理
    """
    counter = {"n": 0}

    def _factory(orders: list[dict]) -> Repository:
        counter["n"] += 1
        db_path = str(tmp_path / f"test_{counter['n']}.db")
        repo = Repository(db_path)
        with repo.engine.begin() as conn:
            for o in orders:
                conn.execute(OrderRow.__table__.insert().values(**o))
        return repo

    return _factory


def _make_order(
    order_id: str,
    status: str = "takeover_pending",
    confirmed_at_offset_min: int | None = None,
    item_id: str = "i1",
) -> dict:
    """构造订单 dict

    confirmed_at_offset_min:
    - None: confirmed_at 为 NULL
    - 正数: confirmed_at 在 now - offset_min 之前（已超时 offset_min 分钟）
    - 负数: confirmed_at 在未来（未超时）
    """
    now = _utcnow().replace(tzinfo=None)
    if confirmed_at_offset_min is None:
        confirmed_at = None
    else:
        confirmed_at = now - timedelta(minutes=confirmed_at_offset_min)

    return {
        "id": order_id,
        "item_id": item_id,
        "task_id": "t1",
        "price": 100.0,
        "status": status,
        "confirmed_at": confirmed_at,
        "created_at": now,
    }


def _make_container(repo: Repository | None = None) -> SimpleNamespace:
    """构造测试用 Container mock"""
    container = SimpleNamespace()
    container.repo = repo or MagicMock()
    return container


def _make_request() -> SimpleNamespace:
    """构造测试用 Request mock，提供多用户隔离所需的 state.user_id"""
    return SimpleNamespace(state=SimpleNamespace(user_id="default"))


# ============== repo.expire_takeover_pending_orders 测试 ==============


def test_expire_returns_empty_when_no_takeover_pending_orders(make_repo) -> None:
    """场景：无 takeover_pending 订单 → 返回空列表"""
    repo = make_repo([
        _make_order("o1", status="pending_pay", confirmed_at_offset_min=None),
        _make_order("o2", status="succeeded", confirmed_at_offset_min=60),
    ])

    expired = repo.expire_takeover_pending_orders(timeout_minutes=30)

    assert expired == []


def test_expire_marks_timed_out_orders_as_failed(make_repo) -> None:
    """场景：takeover_pending 订单 confirmed_at 60 分钟前 → 被 failed"""
    repo = make_repo([
        _make_order("o_old", status="takeover_pending", confirmed_at_offset_min=60),
    ])

    expired = repo.expire_takeover_pending_orders(timeout_minutes=30)

    assert len(expired) == 1
    assert expired[0]["id"] == "o_old"
    # 验证 DB 状态已更新
    order = repo.get_order("o_old")
    assert order["status"] == "failed"
    assert order["confirmed_at"] is None
    assert "接管超时未支付" in (order.get("error") or "")


def test_expire_keeps_recent_takeover_pending_orders(make_repo) -> None:
    """场景：takeover_pending 订单 confirmed_at 10 分钟前（未超时）→ 保留"""
    repo = make_repo([
        _make_order("o_recent", status="takeover_pending", confirmed_at_offset_min=10),
    ])

    expired = repo.expire_takeover_pending_orders(timeout_minutes=30)

    assert expired == []
    order = repo.get_order("o_recent")
    assert order["status"] == "takeover_pending"
    assert order["confirmed_at"] is not None


def test_expire_skips_orders_with_null_confirmed_at(make_repo) -> None:
    """场景：takeover_pending 但 confirmed_at 为 NULL（数据不一致）→ 跳过

    防御性处理：confirmed_at 为 NULL 时无法计算超时，留给手动处理
    """
    repo = make_repo([
        _make_order("o_null", status="takeover_pending", confirmed_at_offset_min=None),
    ])

    expired = repo.expire_takeover_pending_orders(timeout_minutes=30)

    assert expired == []
    order = repo.get_order("o_null")
    assert order["status"] == "takeover_pending"  # 未被修改


def test_expire_batch_handles_mixed_orders(make_repo) -> None:
    """场景：混合订单 → 仅超时的 takeover_pending 被 failed"""
    repo = make_repo([
        # 超时 takeover_pending → failed
        _make_order("o1", status="takeover_pending", confirmed_at_offset_min=60),
        # 未超时 takeover_pending → 保留
        _make_order("o2", status="takeover_pending", confirmed_at_offset_min=5),
        # pending_pay → 不影响
        _make_order("o3", status="pending_pay", confirmed_at_offset_min=None),
        # succeeded → 不影响
        _make_order("o4", status="succeeded", confirmed_at_offset_min=120),
    ])

    expired = repo.expire_takeover_pending_orders(timeout_minutes=30)

    assert len(expired) == 1
    assert expired[0]["id"] == "o1"
    assert repo.get_order("o1")["status"] == "failed"
    assert repo.get_order("o2")["status"] == "takeover_pending"
    assert repo.get_order("o3")["status"] == "pending_pay"
    assert repo.get_order("o4")["status"] == "succeeded"


def test_expire_clears_confirmed_at_after_marking_failed(make_repo) -> None:
    """场景：超时清理后 confirmed_at 被清空，与 takeover_cancel 行为一致"""
    repo = make_repo([
        _make_order("o1", status="takeover_pending", confirmed_at_offset_min=60),
    ])

    repo.expire_takeover_pending_orders(timeout_minutes=30)

    order = repo.get_order("o1")
    assert order["confirmed_at"] is None


# ============== TakeoverTimeoutScheduler 测试 ==============


def test_scheduler_start_stop_lifecycle() -> None:
    """场景：start/stop 生命周期管理"""
    from xianyu_hunter.modules.takeover_timeout_scheduler import TakeoverTimeoutScheduler

    container = _make_container()
    scheduler = TakeoverTimeoutScheduler(container, timeout_min=30, scan_interval_min=1)

    scheduler.start()
    assert scheduler._scheduler is not None

    # 重复 start 应幂等
    scheduler.start()

    scheduler.stop()
    assert scheduler._scheduler is None

    # 重复 stop 应幂等
    scheduler.stop()


def test_scheduler_run_cleanup_job_calls_repo() -> None:
    """场景：_run_cleanup_job 正确调用 repo.expire_takeover_pending_orders"""
    from xianyu_hunter.modules.takeover_timeout_scheduler import TakeoverTimeoutScheduler

    container = _make_container()
    container.repo.expire_takeover_pending_orders = MagicMock(return_value=[])
    scheduler = TakeoverTimeoutScheduler(container, timeout_min=30)

    scheduler._run_cleanup_job()

    container.repo.expire_takeover_pending_orders.assert_called_once_with(30)


def test_scheduler_run_cleanup_job_logs_when_orders_expired() -> None:
    """场景：有超时订单时记录 warning 日志"""
    from xianyu_hunter.modules.takeover_timeout_scheduler import TakeoverTimeoutScheduler

    container = _make_container()
    expired_orders = [{"id": "o1", "status": "failed"}, {"id": "o2", "status": "failed"}]
    container.repo.expire_takeover_pending_orders = MagicMock(return_value=expired_orders)
    scheduler = TakeoverTimeoutScheduler(container, timeout_min=30)

    with patch("xianyu_hunter.modules.takeover_timeout_scheduler.logger") as mock_logger:
        scheduler._run_cleanup_job()

    mock_logger.warning.assert_called_once()
    # 验证日志参数包含订单数量 2
    args = mock_logger.warning.call_args[0]
    assert args[1] == 2  # %d 个订单 → len(expired)


def test_scheduler_run_cleanup_job_swallows_exceptions() -> None:
    """场景：repo 抛异常时调度器不崩溃，下次扫描可重试"""
    from xianyu_hunter.modules.takeover_timeout_scheduler import TakeoverTimeoutScheduler

    container = _make_container()
    container.repo.expire_takeover_pending_orders = MagicMock(
        side_effect=RuntimeError("DB locked"),
    )
    scheduler = TakeoverTimeoutScheduler(container, timeout_min=30)

    # 不应抛出异常
    scheduler._run_cleanup_job()

    container.repo.expire_takeover_pending_orders.assert_called_once()


# ============== takeover_order 状态机白名单测试 ==============


def test_takeover_rejects_already_takeover_pending() -> None:
    """场景2：takeover_pending → takeover_pending 被拒绝

    防止用户无限点击「接管」重置 30 分钟倒计时
    """
    container = _make_container()
    container.repo.get_order.return_value = {
        "id": "o1", "status": "takeover_pending", "confirmed_at": _utcnow(),
    }

    with pytest.raises(HTTPException) as exc:
        api_orders.takeover_order("o1", container=container, request=_make_request())

    assert exc.value.status_code == 409
    assert "takeover_pending" in exc.value.detail
    container.repo.upsert_order.assert_not_called()


def test_takeover_rejects_failed_order() -> None:
    """场景3：failed 订单不能被接管（疑似 bug 修复）"""
    container = _make_container()
    container.repo.get_order.return_value = {
        "id": "o1", "status": "failed",
    }

    with pytest.raises(HTTPException) as exc:
        api_orders.takeover_order("o1", container=container, request=_make_request())

    assert exc.value.status_code == 409
    container.repo.upsert_order.assert_not_called()


def test_takeover_rejects_succeeded_order() -> None:
    """场景：succeeded 订单不能被接管"""
    container = _make_container()
    container.repo.get_order.return_value = {
        "id": "o1", "status": "succeeded",
    }

    with pytest.raises(HTTPException) as exc:
        api_orders.takeover_order("o1", container=container, request=_make_request())

    assert exc.value.status_code == 409
    container.repo.upsert_order.assert_not_called()


def test_takeover_rejects_cancelled_order() -> None:
    """场景：cancelled 订单不能直接被接管，需先回退到 pending_pay"""
    container = _make_container()
    container.repo.get_order.return_value = {
        "id": "o1", "status": "cancelled",
    }

    with pytest.raises(HTTPException) as exc:
        api_orders.takeover_order("o1", container=container, request=_make_request())

    assert exc.value.status_code == 409


def test_takeover_accepts_pending_pay() -> None:
    """场景：pending_pay → takeover_pending 正常转换"""
    container = _make_container()
    container.repo.get_order.return_value = {
        "id": "o1", "status": "pending_pay", "price": 100.0,
    }

    result = api_orders.takeover_order("o1", container=container, request=_make_request())

    assert result["ok"] is True
    assert result["status"] == "takeover_pending"
    assert "takeover_deadline" in result
    assert "takeover_at" in result
    container.repo.upsert_order.assert_called_once()
    saved = container.repo.upsert_order.call_args[0][0]
    assert saved["status"] == "takeover_pending"
    assert saved["confirmed_at"] is not None


def test_takeover_returns_404_when_order_not_found() -> None:
    """场景：订单不存在 → 404"""
    container = _make_container()
    container.repo.get_order.return_value = None

    with pytest.raises(HTTPException) as exc:
        api_orders.takeover_order("o_not_exist", container=container, request=_make_request())

    assert exc.value.status_code == 404
