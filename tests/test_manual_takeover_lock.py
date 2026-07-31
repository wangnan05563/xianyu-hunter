from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from xianyu_hunter.domain.order import BuyOutcome, BuyResult, OrderSnapshot, OrderStatus
from xianyu_hunter.web.routes import api_orders


class _FakeCookieStore:
    """Mock CookieStore

    为什么同时 mock has_valid_cookies 和 validate_cookies_with_expiry：
    修复后 _ensure_takeover_prerequisites 改用 validate_cookies_with_expiry
    （含过期检查），保留 has_valid_cookies 兼容其他调用点。
    """

    def __init__(self, is_valid: bool = True, reason: str = "ok") -> None:
        self._is_valid = is_valid
        self._reason = reason

    def invalidate_cache(self, user_id: str | None = None) -> None:
        return None

    def has_valid_cookies(self, user_id: str = "default") -> bool:
        return self._is_valid

    def validate_cookies_with_expiry(self, user_id: str = "default") -> tuple[bool, str]:
        return self._is_valid, self._reason

    def update_cookie_values(self, updates: dict[str, str], user_id: str = "default") -> bool:
        return True


@pytest.mark.asyncio
async def test_manual_takeover_uses_browser_lock(monkeypatch) -> None:
    events: list[str] = []

    async def _sync_cookie(*args, **kwargs) -> None:
        events.append("cookie_sync")

    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_store.get_cookie_store",
        lambda: _FakeCookieStore(is_valid=True),
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

    # manual_takeover 接口需要 request 参数读取 request.state.user_id 做多用户隔离
    # 测试环境用 mock request，user_id="default" 兜底
    mock_request = MagicMock()
    mock_request.state.user_id = "default"

    result = await api_orders.manual_takeover(
        {"item_id": "i1", "task_id": "t1"},
        mock_request,
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


# ==== 多用户场景：Cookie 校验 user_id 传递 ====
class _UserIdTrackingCookieStore(_FakeCookieStore):
    """记录 validate_cookies_with_expiry 被调用时传入的 user_id"""

    def __init__(self, is_valid: bool = True) -> None:
        super().__init__(is_valid=is_valid)
        self.last_user_id: str | None = None

    def validate_cookies_with_expiry(self, user_id: str = "default") -> tuple[bool, str]:
        self.last_user_id = user_id
        return self._is_valid, self._reason


@pytest.mark.asyncio
async def test_manual_takeover_passes_user_id_to_cookie_check(monkeypatch) -> None:
    """多用户场景：抢单时应把 request.state.user_id 传给 Cookie 校验

    修复前：_ensure_takeover_prerequisites 调用 has_valid_cookies() 不传 user_id，
    默认 "default"，多用户场景下读取错误的 cookie 文件，导致"右上角显示有效但抢单报过期"
    修复后：从 request.state 读取 user_id 并传给 validate_cookies_with_expiry
    """
    tracking_store = _UserIdTrackingCookieStore(is_valid=True)
    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_store.get_cookie_store",
        lambda: tracking_store,
    )

    async def _sync_cookie(*args, **kwargs) -> None:
        pass

    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_runtime_sync.inject_cookie_store_to_worker_browser",
        _sync_cookie,
    )

    container = SimpleNamespace()
    container.repo = MagicMock()
    container.repo.get_item.return_value = {"id": "i1", "price": 100.0, "task_id": "t1"}
    container.repo.find_order_by_task_item.return_value = None
    container.browser_lock = MagicMock()
    container.browser_lock.acquire = AsyncMock()
    container.browser_lock.release = MagicMock()
    container.buyer = MagicMock()
    container.buyer.buy = AsyncMock(return_value=BuyResult(
        outcome=BuyOutcome.SUCCESS,
        order=OrderSnapshot(item_id="i1", order_no="o1", price=100.0, status=OrderStatus.PENDING_PAY),
    ))

    # 模拟多用户场景：当前会话用户是 "user_a" 而非 "default"
    mock_request = MagicMock()
    mock_request.state.user_id = "user_a"

    await api_orders.manual_takeover(
        {"item_id": "i1", "task_id": "t1"},
        mock_request,
        container=container,
    )

    # 关键断言：Cookie 校验收到了正确的 user_id
    assert tracking_store.last_user_id == "user_a", (
        f"多用户场景下 Cookie 校验未收到正确 user_id，期望 'user_a'，实际 '{tracking_store.last_user_id}'"
    )


# ==== 浏览器内存兜底场景 ====
@pytest.mark.asyncio
async def test_manual_takeover_fallback_to_browser_cookies_when_json_invalid(monkeypatch) -> None:
    """JSON 判定无效但浏览器内存 Cookie 有效时，抢单应通过浏览器内存兜底通过

    场景：JSON 与浏览器内存不同步（MTOP Set-Cookie 回写 JSON 失败），
    右上角 /cookie/health 有浏览器内存兜底显示有效，修复前抢单无兜底报过期。
    """
    from xianyu_hunter.modules.cookie_rotator import LAYER_DEFINITIONS, CookieLayer

    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_store.get_cookie_store",
        lambda: _FakeCookieStore(is_valid=False, reason="no_cookie_data"),
    )

    async def _sync_cookie(*args, **kwargs) -> None:
        pass

    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_runtime_sync.inject_cookie_store_to_worker_browser",
        _sync_cookie,
    )

    # 构造浏览器内存 Cookie：m5tk 有效 + identity cookie 存在 + 未过期
    identity_cookie_name = next(iter(LAYER_DEFINITIONS[CookieLayer.IDENTITY].cookies))
    future_expires = 9999999999  # 远未来时间戳
    mock_cookies = [
        {"name": "_m_h5_tk", "value": "1234567890_abc", "expires": -1},
        {"name": identity_cookie_name, "value": "valid_value", "expires": future_expires},
    ]

    container = SimpleNamespace()
    container.browser = MagicMock()
    container.browser.get_cookies = AsyncMock(return_value=mock_cookies)
    container.repo = MagicMock()
    container.repo.get_item.return_value = {"id": "i1", "price": 100.0, "task_id": "t1"}
    container.repo.find_order_by_task_item.return_value = None
    container.browser_lock = MagicMock()
    container.browser_lock.acquire = AsyncMock()
    container.browser_lock.release = MagicMock()
    container.buyer = MagicMock()
    container.buyer.buy = AsyncMock(return_value=BuyResult(
        outcome=BuyOutcome.SUCCESS,
        order=OrderSnapshot(item_id="i1", order_no="o1", price=100.0, status=OrderStatus.PENDING_PAY),
    ))

    mock_request = MagicMock()
    mock_request.state.user_id = "default"

    result = await api_orders.manual_takeover(
        {"item_id": "i1", "task_id": "t1"},
        mock_request,
        container=container,
    )

    # 关键断言：JSON 无效但浏览器内存兜底通过，抢单成功
    assert result["ok"] is True, "JSON 无效但浏览器内存有效时，抢单应通过兜底成功"


@pytest.mark.asyncio
async def test_manual_takeover_raises_when_both_json_and_browser_invalid(monkeypatch) -> None:
    """JSON 无效且浏览器内存也无效时，抢单应报 403 过期错误"""
    from fastapi import HTTPException

    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_store.get_cookie_store",
        lambda: _FakeCookieStore(is_valid=False, reason="no_cookie_data"),
    )

    container = SimpleNamespace()
    container.browser = MagicMock()
    container.browser.get_cookies = AsyncMock(return_value=[])  # 浏览器内存也空
    container.buyer = MagicMock()  # buyer 已注入，跳过 503
    container.repo = MagicMock()

    mock_request = MagicMock()
    mock_request.state.user_id = "default"

    with pytest.raises(HTTPException) as exc_info:
        await api_orders.manual_takeover(
            {"item_id": "i1", "task_id": "t1"},
            mock_request,
            container=container,
        )

    assert exc_info.value.status_code == 403
    assert "闲鱼登录已过期" in exc_info.value.detail


@pytest.mark.asyncio
async def test_manual_takeover_raises_503_when_buyer_not_injected(monkeypatch) -> None:
    """buyer 未注入（with_browser=False）时返回 503，不进行 Cookie 校验"""
    from fastapi import HTTPException

    monkeypatch.setattr(
        "xianyu_hunter.web.services.cookie_store.get_cookie_store",
        lambda: _FakeCookieStore(is_valid=True),
    )

    container = SimpleNamespace()
    container.buyer = None  # buyer 未注入
    container.repo = MagicMock()

    mock_request = MagicMock()
    mock_request.state.user_id = "default"

    with pytest.raises(HTTPException) as exc_info:
        await api_orders.manual_takeover(
            {"item_id": "i1", "task_id": "t1"},
            mock_request,
            container=container,
        )

    assert exc_info.value.status_code == 503
    assert "XH_WITH_SCHEDULER=1" in exc_info.value.detail
