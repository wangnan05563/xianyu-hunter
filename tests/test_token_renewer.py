"""TokenRenewer 单元测试"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from xianyu_hunter.modules.token_renewer import (
    RenewResult,
    RenewerConfig,
    TokenInfo,
    TokenRenewer,
)


# ============== TokenInfo 测试 ==============


def test_token_info_parse_with_timestamp() -> None:
    """解析带时间戳的 _m_h5_tk"""
    # timestamp 是毫秒级
    value = "abc123_1700000000000"
    info = TokenInfo.from_cookie_value(value)
    assert info.token == "abc123"
    assert info.issued_at == 1700000000.0
    assert info.raw_value == value


def test_token_info_parse_without_timestamp() -> None:
    """解析不带时间戳的值"""
    value = "abc123"
    info = TokenInfo.from_cookie_value(value)
    assert info.token == "abc123"
    assert info.raw_value == value


def test_token_info_parse_invalid_timestamp() -> None:
    """时间戳无效时使用当前时间"""
    value = "abc123_invalid"
    info = TokenInfo.from_cookie_value(value)
    assert info.token == "abc123"
    # issued_at 应接近当前时间
    assert abs(info.issued_at - time.time()) < 5


def test_token_info_age_seconds() -> None:
    """age_seconds 计算正确"""
    # issued_at 设为 100 秒前
    past = time.time() - 100
    info = TokenInfo(
        raw_value="test",
        token="test",
        issued_at=past,
        obtained_at=past,
    )
    age = info.age_seconds()
    assert 95 <= age <= 105


def test_token_info_is_expired() -> None:
    """is_expired 判断正确"""
    now = time.time()
    # 30 分钟前的 token，TTL=20 分钟 → 已过期
    old = TokenInfo("test", "test", now - 1800, now - 1800)
    assert old.is_expired(ttl_sec=1200)

    # 5 分钟前的 token，TTL=20 分钟 → 未过期
    fresh = TokenInfo("test", "test", now - 300, now - 300)
    assert not fresh.is_expired(ttl_sec=1200)


# ============== RenewerConfig 测试 ==============


def test_default_config() -> None:
    """默认配置合理"""
    cfg = RenewerConfig()
    assert cfg.renew_before_expiry_sec == 600   # 过期前 10 分钟
    assert cfg.check_interval_sec == 120        # 2 分钟检查
    assert cfg.token_ttl_sec == 1200            # 20 分钟 TTL
    assert cfg.max_renew_attempts == 3


# ============== check_and_renew 测试 ==============


@pytest.mark.asyncio
async def test_renew_skipped_when_no_provider() -> None:
    """未设置 cookie_provider 时跳过"""
    renewer = TokenRenewer()
    result = await renewer.check_and_renew()
    assert result == RenewResult.SKIPPED
    assert renewer._stats["total_skipped"] == 1


@pytest.mark.asyncio
async def test_renew_expired_when_no_cookie() -> None:
    """cookie_provider 返回 None 时标记会话失效"""
    renewer = TokenRenewer()
    renewer.set_cookie_provider(lambda: None)
    result = await renewer.check_and_renew()
    assert result == RenewResult.SESSION_EXPIRED


@pytest.mark.asyncio
async def test_renew_skipped_when_token_fresh() -> None:
    """token 刚获取不久时跳过续期"""
    renewer = TokenRenewer()
    # 1 分钟前的 token
    fresh_value = f"token_{int((time.time() - 60) * 1000)}"
    renewer.set_cookie_provider(lambda: fresh_value)

    result = await renewer.check_and_renew()
    assert result == RenewResult.SKIPPED


@pytest.mark.asyncio
async def test_renew_success_when_token_aging() -> None:
    """token 接近过期时触发续期"""
    cfg = RenewerConfig(token_ttl_sec=1200, renew_before_expiry_sec=600)
    renewer = TokenRenewer(cfg)

    # 15 分钟前的 token（TTL=20min，10min 时触发）
    aging_value = f"token_{int((time.time() - 900) * 1000)}"
    renewer.set_cookie_provider(lambda: aging_value)

    # 设置续期回调返回成功
    renewer.set_renew_callback(AsyncMock(return_value=True))

    result = await renewer.check_and_renew()
    assert result == RenewResult.SUCCESS
    assert renewer._stats["total_renewed"] == 1
    assert renewer._consecutive_failures == 0


@pytest.mark.asyncio
async def test_renew_failed_when_callback_returns_false() -> None:
    """续期回调返回 False 时标记失败"""
    renewer = TokenRenewer()
    aging_value = f"token_{int((time.time() - 900) * 1000)}"
    renewer.set_cookie_provider(lambda: aging_value)
    renewer.set_renew_callback(AsyncMock(return_value=False))

    result = await renewer.check_and_renew()
    assert result == RenewResult.FAILED
    assert renewer._consecutive_failures == 1


@pytest.mark.asyncio
async def test_renew_failed_when_callback_raises() -> None:
    """续期回调抛异常时标记失败"""
    renewer = TokenRenewer()
    aging_value = f"token_{int((time.time() - 900) * 1000)}"
    renewer.set_cookie_provider(lambda: aging_value)
    renewer.set_renew_callback(AsyncMock(side_effect=Exception("network error")))

    result = await renewer.check_and_renew()
    assert result == RenewResult.FAILED


@pytest.mark.asyncio
async def test_renew_expired_when_token_too_old() -> None:
    """token 已过期时标记会话失效"""
    renewer = TokenRenewer()
    # 30 分钟前的 token（TTL=20min → 已过期）
    expired_value = f"token_{int((time.time() - 1800) * 1000)}"
    renewer.set_cookie_provider(lambda: expired_value)

    result = await renewer.check_and_renew()
    assert result == RenewResult.SESSION_EXPIRED


@pytest.mark.asyncio
async def test_fail_callback_triggered_on_expiry() -> None:
    """会话失效时触发 fail_callback"""
    renewer = TokenRenewer()
    fail_cb = MagicMock()
    renewer.set_renew_fail_callback(fail_cb)

    expired_value = f"token_{int((time.time() - 1800) * 1000)}"
    renewer.set_cookie_provider(lambda: expired_value)

    await renewer.check_and_renew()
    fail_cb.assert_called_once()


@pytest.mark.asyncio
async def test_fail_callback_triggered_on_max_failures() -> None:
    """连续失败达到上限时触发 fail_callback"""
    cfg = RenewerConfig(max_renew_attempts=2)
    renewer = TokenRenewer(cfg)
    fail_cb = MagicMock()
    renewer.set_renew_fail_callback(fail_cb)

    aging_value = f"token_{int((time.time() - 900) * 1000)}"
    renewer.set_cookie_provider(lambda: aging_value)
    renewer.set_renew_callback(AsyncMock(return_value=False))

    # 第一次失败
    await renewer.check_and_renew()
    assert not fail_cb.called

    # 第二次失败 → 触发 fail_callback
    await renewer.check_and_renew()
    fail_cb.assert_called_once()


# ============== 生命周期测试 ==============


@pytest.mark.asyncio
async def test_start_stop_lifecycle() -> None:
    """start/stop 生命周期"""
    renewer = TokenRenewer(RenewerConfig(check_interval_sec=1))
    renewer.set_cookie_provider(lambda: f"token_{int(time.time() * 1000)}")

    assert not renewer.is_running

    # start() 是同步方法：内部通过 asyncio.create_task 启动后台循环
    renewer.start()
    assert renewer.is_running

    await asyncio.sleep(0.1)  # 让循环跑一会

    await renewer.stop()
    assert not renewer.is_running


@pytest.mark.asyncio
async def test_start_idempotent() -> None:
    """重复 start 不会创建多个任务"""
    renewer = TokenRenewer(RenewerConfig(check_interval_sec=10))
    renewer.set_cookie_provider(lambda: None)

    renewer.start()
    task1 = renewer._task

    renewer.start()
    task2 = renewer._task

    assert task1 is task2

    await renewer.stop()


# ============== 状态查询测试 ==============


def test_get_status_initial() -> None:
    """初始状态正确"""
    renewer = TokenRenewer()
    status = renewer.get_status()

    assert status["running"] is False
    assert status["token_age_sec"] is None
    assert status["consecutive_failures"] == 0
    assert status["stats"]["total_checks"] == 0


def test_get_status_with_token() -> None:
    """有 token 时状态正确"""
    renewer = TokenRenewer()
    renewer.set_cookie_provider(lambda: f"token_{int((time.time() - 100) * 1000)}")

    status = renewer.get_status()
    assert status["token_age_sec"] is not None
    assert 95 <= status["token_age_sec"] <= 105
    assert status["token_expired"] is False


@pytest.mark.asyncio
async def test_get_status_after_renew() -> None:
    """续期后状态更新"""
    renewer = TokenRenewer()
    aging_value = f"token_{int((time.time() - 900) * 1000)}"
    renewer.set_cookie_provider(lambda: aging_value)
    renewer.set_renew_callback(AsyncMock(return_value=True))

    await renewer.check_and_renew()

    status = renewer.get_status()
    assert status["stats"]["total_renewed"] == 1
    assert status["last_renew_result"] == "success"
    assert status["last_renew_at"] > 0
