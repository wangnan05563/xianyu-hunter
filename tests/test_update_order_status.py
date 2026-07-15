"""update_order_status 端点测试

覆盖场景：
1. 无效状态值 → 422
2. 订单不存在 → 404
3. 状态相同 → changed=False（幂等）
4. pending_pay → succeeded：写入 paid_at + 触发下游任务
5. succeeded → pending_pay：不触发下游任务、不写 paid_at
6. pending_pay → cancelled：不触发下游任务
7. takeover_pending 不在合法集合中（必须走 takeover 端点）
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from xianyu_hunter.web.routes import api_orders


def _make_container(order: dict | None = None) -> SimpleNamespace:
    """构造带 mock repo 的 container

    get_order 返回 order；upsert_order 记录调用；list_dependent_tasks 默认返回空列表
    （不触发下游任务逻辑）。
    """
    container = SimpleNamespace()
    container.repo = MagicMock()
    container.repo.get_order.return_value = order
    container.repo.upsert_order = MagicMock()
    container.repo.get_item.return_value = None
    container.repo.list_dependent_tasks.return_value = []
    return container


def _make_request() -> SimpleNamespace:
    """构造测试用 Request mock，提供多用户隔离所需的 state.user_id"""
    return SimpleNamespace(state=SimpleNamespace(user_id="default"))


def test_invalid_status_returns_422() -> None:
    """非法状态值（含 takeover_pending 中间态）应返回 422"""
    container = _make_container(order={"id": "o1", "status": "pending_pay"})

    for bad in ("takeover_pending", "invalid", "", "PENDING_PAY"):
        with pytest.raises(HTTPException) as exc:
            api_orders.update_order_status(
                "o1", {"status": bad}, container=container, request=_make_request(),
            )
        assert exc.value.status_code == 422
    # 不应发生任何写库
    container.repo.upsert_order.assert_not_called()


def test_order_not_found_returns_404() -> None:
    """订单不存在应返回 404"""
    container = _make_container(order=None)

    with pytest.raises(HTTPException) as exc:
        api_orders.update_order_status(
            "o1", {"status": "succeeded"}, container=container, request=_make_request(),
        )
    assert exc.value.status_code == 404


def test_same_status_is_idempotent() -> None:
    """目标状态与当前状态一致 → changed=False，不写库"""
    container = _make_container(order={"id": "o1", "status": "pending_pay"})

    result = api_orders.update_order_status(
        "o1", {"status": "pending_pay"}, container=container, request=_make_request(),
    )

    assert result == {
        "ok": True,
        "id": "o1",
        "old_status": "pending_pay",
        "new_status": "pending_pay",
        "changed": False,
    }
    container.repo.upsert_order.assert_not_called()


def test_pending_pay_to_succeeded_writes_paid_at_and_triggers_dependents() -> None:
    """pending_pay → succeeded：写 paid_at 并触发下游任务"""
    order = {"id": "o1", "status": "pending_pay", "item_id": "i1"}
    container = _make_container(order=order)
    # 模拟有下游依赖任务
    container.repo.get_item.return_value = {"id": "i1", "task_id": "t_upstream"}
    container.repo.list_dependent_tasks.return_value = [
        {"task_id": "t_downstream"},
    ]
    container.repo.get_task.return_value = {"id": "t_downstream", "status": "paused"}

    with patch("xianyu_hunter.web.routes.api_orders._trigger_dependent_tasks") as mock_trigger:
        result = api_orders.update_order_status(
            "o1", {"status": "succeeded"}, container=container, request=_make_request(),
        )

    assert result["changed"] is True
    assert result["old_status"] == "pending_pay"
    assert result["new_status"] == "succeeded"

    # 验证写库调用包含 paid_at
    container.repo.upsert_order.assert_called_once()
    saved = container.repo.upsert_order.call_args[0][0]
    assert saved["status"] == "succeeded"
    assert "paid_at" in saved

    # 验证下游任务触发
    mock_trigger.assert_called_once_with(container, saved, user_id="default")


def test_succeeded_to_pending_pay_does_not_trigger_dependents() -> None:
    """succeeded → pending_pay：不应触发下游任务"""
    order = {"id": "o1", "status": "succeeded", "item_id": "i1"}
    container = _make_container(order=order)

    with patch("xianyu_hunter.web.routes.api_orders._trigger_dependent_tasks") as mock_trigger:
        result = api_orders.update_order_status(
            "o1", {"status": "pending_pay"}, container=container, request=_make_request(),
        )

    assert result["changed"] is True
    assert result["new_status"] == "pending_pay"
    mock_trigger.assert_not_called()


def test_pending_pay_to_cancelled_does_not_trigger_dependents() -> None:
    """pending_pay → cancelled：不应触发下游任务"""
    order = {"id": "o1", "status": "pending_pay", "item_id": "i1"}
    container = _make_container(order=order)

    with patch("xianyu_hunter.web.routes.api_orders._trigger_dependent_tasks") as mock_trigger:
        result = api_orders.update_order_status(
            "o1", {"status": "cancelled"}, container=container, request=_make_request(),
        )

    assert result["changed"] is True
    assert result["new_status"] == "cancelled"
    mock_trigger.assert_not_called()


def test_takeover_pending_cannot_be_set_manually() -> None:
    """takeover_pending 是流程中间态，不能通过此端点手动设置"""
    order = {"id": "o1", "status": "pending_pay"}
    container = _make_container(order=order)

    with pytest.raises(HTTPException) as exc:
        api_orders.update_order_status(
            "o1", {"status": "takeover_pending"}, container=container, request=_make_request(),
        )
    assert exc.value.status_code == 422


def test_paid_at_only_set_when_target_is_succeeded() -> None:
    """只有目标状态是 succeeded 才写 paid_at"""
    order = {"id": "o1", "status": "pending_pay"}
    container = _make_container(order=order)

    api_orders.update_order_status(
        "o1", {"status": "failed"}, container=container, request=_make_request(),
    )

    saved = container.repo.upsert_order.call_args[0][0]
    assert "paid_at" not in saved
