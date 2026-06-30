from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from xianyu_hunter.domain.order import BuyOutcome, BuyResult, OrderSnapshot, OrderStatus
from xianyu_hunter.web.routes import api_orders


class _FakeCookieStore:
    def invalidate_cache(self) -> None:
        return None

    def has_valid_cookies(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_manual_takeover_uses_browser_lock(monkeypatch) -> None:
    events: list[str] = []

    async def _sync_cookie(*args, **kwargs) -> None:
        events.append("cookie_sync")

    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_store.get_cookie_store",
        lambda: _FakeCookieStore(),
    )
    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_runtime_sync.inject_cookie_store_to_worker_browser",
        _sync_cookie,
    )

    container = SimpleNamespace()
    container.repo = MagicMock()
    container.repo.get_item.return_value = {"id": "i1", "price": 100.0, "task_id": "t1"}
    container.repo.find_order_by_task_item.return_value = None
    container.browser_lock = MagicMock()

    async def _acquire(priority: str = "low") -> None:
        events.append(f"acquire:{priority}")

    def _release() -> None:
        events.append("release")

    container.browser_lock.acquire = AsyncMock(side_effect=_acquire)
    container.browser_lock.release = MagicMock(side_effect=_release)
    container.buyer = MagicMock()

    async def _buy(**kwargs) -> BuyResult:
        events.append("buy")
        return BuyResult(
            outcome=BuyOutcome.SUCCESS,
            order=OrderSnapshot(
                item_id="i1",
                order_no="o1",
                price=100.0,
                status=OrderStatus.PENDING_PAY,
            ),
        )

    container.buyer.buy = AsyncMock(side_effect=_buy)

    result = await api_orders.manual_takeover(
        {"item_id": "i1", "task_id": "t1"},
        container=container,
    )

    assert result["ok"] is True
    container.browser_lock.acquire.assert_awaited_once_with(priority="high")
    container.browser_lock.release.assert_called_once()
    assert events == ["acquire:high", "cookie_sync", "buy", "release"]
    container.buyer.buy.assert_awaited_once_with(
        task_id="t1",
        item_id="i1",
        expected_price=100.0,
    )
