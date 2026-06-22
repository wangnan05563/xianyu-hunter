"""CookieRotator 单元测试"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from xianyu_hunter.modules.cookie_rotator import (
    CookieLayer,
    CookieRotator,
    LayerState,
    SessionExpiredError,
    get_cookie_layer,
    get_required_cookies_for_layer,
    is_identity_cookie,
    is_session_cookie,
)


# ============== 层定义测试 ==============


def test_identity_layer_cookies() -> None:
    """身份层包含正确的 Cookie"""
    cookies = get_required_cookies_for_layer(CookieLayer.IDENTITY)
    assert "unb" in cookies
    assert "cookie2" in cookies
    assert "sgcookie" in cookies
    assert "t" in cookies
    assert "_tb_token_" in cookies
    assert "lg2" in cookies


def test_session_layer_cookies() -> None:
    """会话层包含正确的 Cookie"""
    cookies = get_required_cookies_for_layer(CookieLayer.SESSION)
    assert "_m_h5_tk" in cookies
    assert "_m_h5_tk_enc" in cookies


def test_session_depends_on_identity() -> None:
    """会话层依赖身份层"""
    from xianyu_hunter.modules.cookie_rotator import LAYER_DEFINITIONS
    assert LAYER_DEFINITIONS[CookieLayer.SESSION].depends_on == CookieLayer.IDENTITY


def test_identity_has_no_dependency() -> None:
    """身份层无依赖"""
    from xianyu_hunter.modules.cookie_rotator import LAYER_DEFINITIONS
    assert LAYER_DEFINITIONS[CookieLayer.IDENTITY].depends_on is None


# ============== 分类函数测试 ==============


def test_get_cookie_layer_identity() -> None:
    """身份层 Cookie 分类正确"""
    assert get_cookie_layer("unb") == CookieLayer.IDENTITY
    assert get_cookie_layer("cookie2") == CookieLayer.IDENTITY
    assert get_cookie_layer("sgcookie") == CookieLayer.IDENTITY


def test_get_cookie_layer_session() -> None:
    """会话层 Cookie 分类正确"""
    assert get_cookie_layer("_m_h5_tk") == CookieLayer.SESSION
    assert get_cookie_layer("_m_h5_tk_enc") == CookieLayer.SESSION


def test_get_cookie_layer_tracking() -> None:
    """追踪层 Cookie 分类正确"""
    assert get_cookie_layer("cna") == CookieLayer.TRACKING
    assert get_cookie_layer("tfstk") == CookieLayer.TRACKING


def test_get_cookie_layer_unknown() -> None:
    """未知 Cookie 返回 None"""
    assert get_cookie_layer("unknown_cookie") is None


def test_is_identity_cookie() -> None:
    """is_identity_cookie 判断正确"""
    assert is_identity_cookie("unb") is True
    assert is_identity_cookie("_m_h5_tk") is False


def test_is_session_cookie() -> None:
    """is_session_cookie 判断正确"""
    assert is_session_cookie("_m_h5_tk") is True
    assert is_session_cookie("unb") is False


# ============== atomic_update 测试 ==============


def test_atomic_update_identity_layer() -> None:
    """原子更新身份层"""
    rotator = CookieRotator()
    writer = MagicMock(return_value=10)
    rotator.set_writer(writer)

    written = rotator.atomic_update({
        "unb": "123456",
        "cookie2": "abc",
    })

    assert written == 10
    assert rotator.is_layer_valid(CookieLayer.IDENTITY)
    writer.assert_called_once()


def test_atomic_update_empty_cookies() -> None:
    """空 Cookie 不更新"""
    rotator = CookieRotator()
    writer = MagicMock()
    rotator.set_writer(writer)

    written = rotator.atomic_update({})
    assert written == 0
    writer.assert_not_called()


def test_atomic_update_cross_layer_raises() -> None:
    """跨层混合更新抛出异常"""
    rotator = CookieRotator()
    rotator.set_writer(MagicMock(return_value=0))

    with pytest.raises(ValueError, match="跨层混合"):
        rotator.atomic_update({
            "unb": "123",           # identity
            "_m_h5_tk": "token",    # session
        })


def test_atomic_update_session_without_identity_raises() -> None:
    """identity 层无效时更新 session 层抛出异常"""
    rotator = CookieRotator()
    rotator.set_writer(MagicMock(return_value=0))

    # identity 层未设置，无效
    with pytest.raises(SessionExpiredError, match="identity.*失效"):
        rotator.atomic_update({
            "_m_h5_tk": "token_123",
            "_m_h5_tk_enc": "enc",
        })


def test_atomic_update_session_after_identity() -> None:
    """先更新 identity 再更新 session 成功"""
    rotator = CookieRotator()
    rotator.set_writer(MagicMock(return_value=5))

    # 先更新 identity
    rotator.atomic_update({"unb": "123", "cookie2": "abc"})

    # 再更新 session
    written = rotator.atomic_update({
        "_m_h5_tk": "token_123",
        "_m_h5_tk_enc": "enc",
    })

    assert written == 5
    assert rotator.is_layer_valid(CookieLayer.SESSION)


def test_atomic_update_tracking_layer() -> None:
    """更新追踪层"""
    rotator = CookieRotator()
    rotator.set_writer(MagicMock(return_value=3))

    written = rotator.atomic_update({"cna": "xyz", "tfstk": "abc"})
    assert written == 3
    assert rotator.is_layer_valid(CookieLayer.TRACKING)


def test_atomic_update_unknown_cookie_goes_to_tracking() -> None:
    """未知 Cookie 归入追踪层"""
    rotator = CookieRotator()
    rotator.set_writer(MagicMock(return_value=1))

    rotator.atomic_update({"unknown_cookie": "value"})
    assert rotator.is_layer_valid(CookieLayer.TRACKING)


def test_atomic_update_no_writer() -> None:
    """未设置 writer 时返回 0"""
    rotator = CookieRotator()
    written = rotator.atomic_update({"unb": "123"})
    assert written == 0


# ============== 级联失效测试 ==============


def test_invalidate_identity_cascades_to_session() -> None:
    """identity 层失效级联到 session 层"""
    rotator = CookieRotator()
    rotator.set_writer(MagicMock(return_value=1))

    # 设置两层有效
    rotator.atomic_update({"unb": "123"})
    rotator.atomic_update({"_m_h5_tk": "token"})
    assert rotator.is_layer_valid(CookieLayer.SESSION)

    # identity 失效
    rotator.invalidate_layer(CookieLayer.IDENTITY)

    assert not rotator.is_layer_valid(CookieLayer.IDENTITY)
    assert not rotator.is_layer_valid(CookieLayer.SESSION)  # 级联失效


def test_invalidate_session_not_cascade_to_identity() -> None:
    """session 层失效不级联到 identity 层"""
    rotator = CookieRotator()
    rotator.set_writer(MagicMock(return_value=1))

    rotator.atomic_update({"unb": "123"})
    rotator.atomic_update({"_m_h5_tk": "token"})

    rotator.invalidate_layer(CookieLayer.SESSION)

    assert not rotator.is_layer_valid(CookieLayer.SESSION)
    assert rotator.is_layer_valid(CookieLayer.IDENTITY)  # 不级联


def test_invalidate_all() -> None:
    """invalidate_all 使所有层失效"""
    rotator = CookieRotator()
    rotator.set_writer(MagicMock(return_value=1))

    rotator.atomic_update({"unb": "123"})
    rotator.atomic_update({"cna": "xyz"})

    rotator.invalidate_all()

    assert not rotator.is_layer_valid(CookieLayer.IDENTITY)
    assert not rotator.is_layer_valid(CookieLayer.SESSION)
    assert not rotator.is_layer_valid(CookieLayer.TRACKING)


# ============== 状态查询测试 ==============


def test_initial_state_all_invalid() -> None:
    """初始状态所有层无效"""
    rotator = CookieRotator()
    for layer in CookieLayer:
        assert not rotator.is_layer_valid(layer)


def test_get_layer_state_after_update() -> None:
    """更新后层状态正确"""
    rotator = CookieRotator()
    rotator.set_writer(MagicMock(return_value=1))

    rotator.atomic_update({"unb": "123", "cookie2": "abc"})
    state = rotator.get_layer_state(CookieLayer.IDENTITY)

    assert state.valid is True
    assert state.cookie_count == 2
    assert state.updated_at > 0


def test_get_all_states() -> None:
    """get_all_states 返回所有层状态"""
    rotator = CookieRotator()
    states = rotator.get_all_states()

    assert len(states) == 3
    assert CookieLayer.IDENTITY in states
    assert CookieLayer.SESSION in states
    assert CookieLayer.TRACKING in states


# ============== 批量写入测试 ==============


def test_batch_write_all_domains() -> None:
    """批量写入覆盖所有域名"""
    rotator = CookieRotator()
    writer = MagicMock(return_value=100)
    rotator.set_writer(writer)

    rotator.atomic_update({"unb": "123"})

    # 验证 writer 被调用，且 cookie 对象包含所有域名
    call_args = writer.call_args[0][0]
    domains_written = {c["domain"] for c in call_args}
    assert ".goofish.com" in domains_written
    assert ".taobao.com" in domains_written
    assert ".alipay.com" in domains_written


def test_batch_write_cookie_object_format() -> None:
    """写入的 cookie 对象格式正确"""
    rotator = CookieRotator()
    writer = MagicMock(return_value=1)
    rotator.set_writer(writer)

    rotator.atomic_update({"unb": "123"})

    call_args = writer.call_args[0][0]
    cookie = call_args[0]
    assert cookie["name"] == "unb"
    assert cookie["value"] == "123"
    assert cookie["path"] == "/"
    assert cookie["secure"] is True
    assert cookie["httpOnly"] is True


# ============== 线程安全测试 ==============


def test_thread_safety() -> None:
    """多线程并发更新安全"""
    rotator = CookieRotator()
    writer = MagicMock(return_value=1)
    rotator.set_writer(writer)

    errors = []

    def update_identity():
        try:
            rotator.atomic_update({"unb": "123"})
        except Exception as e:
            errors.append(e)

    def update_tracking():
        try:
            rotator.atomic_update({"cna": "xyz"})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=update_identity) for _ in range(5)]
    threads += [threading.Thread(target=update_tracking) for _ in range(5)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert rotator.is_layer_valid(CookieLayer.IDENTITY)
    assert rotator.is_layer_valid(CookieLayer.TRACKING)
