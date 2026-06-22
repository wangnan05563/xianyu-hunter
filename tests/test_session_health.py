"""SessionHealthChecker 单元测试"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from xianyu_hunter.modules.session_health import (
    HealthAction,
    HealthReport,
    SessionHealthChecker,
    WAFStatus,
)


# ============== 枚举测试 ==============


def test_health_action_values() -> None:
    """动作枚举值正确"""
    assert HealthAction.NONE.value == "none"
    assert HealthAction.RENEW_TOKEN.value == "renew_token"
    assert HealthAction.RELOGIN.value == "relogin"
    assert HealthAction.PAUSE.value == "pause"


def test_waf_status_values() -> None:
    """风控状态枚举值正确"""
    assert WAFStatus.CLEAR.value == "clear"
    assert WAFStatus.WARNING.value == "warning"
    assert WAFStatus.BLOCKED.value == "blocked"


# ============== HealthReport 测试 ==============


def test_health_report_is_healthy() -> None:
    """score >= 80 为健康"""
    report = HealthReport(
        score=85, cookie_valid=True, api_reachable=True,
        page_accessible=True, waf_status=WAFStatus.CLEAR,
        action=HealthAction.NONE,
    )
    assert report.is_healthy is True
    assert report.needs_attention is False


def test_health_report_needs_attention() -> None:
    """score < 60 需要关注"""
    report = HealthReport(
        score=50, cookie_valid=False, api_reachable=False,
        page_accessible=False, waf_status=WAFStatus.WARNING,
        action=HealthAction.RELOGIN,
    )
    assert report.is_healthy is False
    assert report.needs_attention is True


def test_health_report_to_dict() -> None:
    """to_dict 序列化正确"""
    report = HealthReport(
        score=75, cookie_valid=True, api_reachable=True,
        page_accessible=False, waf_status=WAFStatus.WARNING,
        action=HealthAction.RENEW_TOKEN,
    )
    d = report.to_dict()
    assert d["score"] == 75
    assert d["cookie_valid"] is True
    assert d["waf_status"] == "warning"
    assert d["action"] == "renew_token"
    assert d["is_healthy"] is False
    assert d["needs_attention"] is False
    assert "checked_at" in d


# ============== check 测试 ==============


@pytest.mark.asyncio
async def test_check_all_healthy() -> None:
    """所有维度健康时 score=100"""
    checker = SessionHealthChecker()
    checker.set_cookie_checker(lambda: True)
    checker.set_api_checker(AsyncMock(return_value=True))
    checker.set_page_checker(AsyncMock(return_value=True))
    checker.set_waf_status_provider(lambda: WAFStatus.CLEAR)

    report = await checker.check()

    assert report.score == 100
    assert report.cookie_valid is True
    assert report.api_reachable is True
    assert report.page_accessible is True
    assert report.waf_status == WAFStatus.CLEAR
    assert report.action == HealthAction.NONE
    assert report.is_healthy is True


@pytest.mark.asyncio
async def test_check_all_unhealthy() -> None:
    """所有维度不健康时 score=0"""
    checker = SessionHealthChecker()
    checker.set_cookie_checker(lambda: False)
    checker.set_api_checker(AsyncMock(return_value=False))
    checker.set_page_checker(AsyncMock(return_value=False))
    checker.set_waf_status_provider(lambda: WAFStatus.BLOCKED)

    report = await checker.check()

    assert report.score == 0
    assert report.action == HealthAction.PAUSE
    assert report.needs_attention is True


@pytest.mark.asyncio
async def test_check_cookie_invalid_only() -> None:
    """仅 Cookie 无效"""
    checker = SessionHealthChecker()
    checker.set_cookie_checker(lambda: False)
    checker.set_api_checker(AsyncMock(return_value=True))
    checker.set_page_checker(AsyncMock(return_value=True))
    checker.set_waf_status_provider(lambda: WAFStatus.CLEAR)

    report = await checker.check()

    # score = 0 + 30 + 20 + 10 = 60
    # 60 在 [60, 80) 区间，cookie 无效 → RENEW_TOKEN
    assert report.score == 60
    assert report.cookie_valid is False
    assert report.action == HealthAction.RENEW_TOKEN


@pytest.mark.asyncio
async def test_check_api_unreachable_only() -> None:
    """仅 API 不可达"""
    checker = SessionHealthChecker()
    checker.set_cookie_checker(lambda: True)
    checker.set_api_checker(AsyncMock(return_value=False))
    checker.set_page_checker(AsyncMock(return_value=True))
    checker.set_waf_status_provider(lambda: WAFStatus.CLEAR)

    report = await checker.check()

    # score = 40 + 0 + 20 + 10 = 70
    assert report.score == 70
    assert report.api_reachable is False
    assert report.action == HealthAction.NONE  # 70 >= 80? No, 70 < 80
    # 实际 70 < 80, cookie_valid=True, 所以 action=NONE
    # 等等，70 < 80 应该是 RENEW_TOKEN，但 cookie_valid=True 所以 NONE
    # 重新看逻辑：60-80 且 not cookie_valid → RENEW_TOKEN，否则 NONE
    # cookie_valid=True → NONE


@pytest.mark.asyncio
async def test_check_waf_warning() -> None:
    """风控警告状态"""
    checker = SessionHealthChecker()
    checker.set_cookie_checker(lambda: True)
    checker.set_api_checker(AsyncMock(return_value=True))
    checker.set_page_checker(AsyncMock(return_value=True))
    checker.set_waf_status_provider(lambda: WAFStatus.WARNING)

    report = await checker.check()

    # score = 40 + 30 + 20 + 5 = 95
    assert report.score == 95
    assert report.waf_status == WAFStatus.WARNING
    assert report.action == HealthAction.NONE


@pytest.mark.asyncio
async def test_check_waf_blocked() -> None:
    """风控熔断状态"""
    checker = SessionHealthChecker()
    checker.set_cookie_checker(lambda: True)
    checker.set_api_checker(AsyncMock(return_value=True))
    checker.set_page_checker(AsyncMock(return_value=True))
    checker.set_waf_status_provider(lambda: WAFStatus.BLOCKED)

    report = await checker.check()

    # score = 40 + 30 + 20 + 0 = 90
    assert report.score == 90
    assert report.waf_status == WAFStatus.BLOCKED


@pytest.mark.asyncio
async def test_check_no_checkers_defaults_healthy() -> None:
    """未设置检查器时默认健康"""
    checker = SessionHealthChecker()

    report = await checker.check()

    assert report.score == 100
    assert report.action == HealthAction.NONE


@pytest.mark.asyncio
async def test_check_cookie_checker_exception() -> None:
    """Cookie 检查器抛异常时返回 False"""
    checker = SessionHealthChecker()
    checker.set_cookie_checker(MagicMock(side_effect=Exception("error")))

    report = await checker.check()

    assert report.cookie_valid is False


@pytest.mark.asyncio
async def test_check_api_checker_exception() -> None:
    """API 检查器抛异常时返回 False"""
    checker = SessionHealthChecker()
    checker.set_api_checker(AsyncMock(side_effect=Exception("error")))

    report = await checker.check()

    assert report.api_reachable is False


@pytest.mark.asyncio
async def test_check_page_checker_exception() -> None:
    """页面检查器抛异常时返回 False"""
    checker = SessionHealthChecker()
    checker.set_page_checker(AsyncMock(side_effect=Exception("error")))

    report = await checker.check()

    assert report.page_accessible is False


def test_waf_provider_exception_returns_warning() -> None:
    """WAF 提供器抛异常时返回 WARNING"""
    checker = SessionHealthChecker()
    checker.set_waf_status_provider(MagicMock(side_effect=Exception("error")))

    status = checker._get_waf_status()
    assert status == WAFStatus.WARNING


# ============== 评分阈值测试 ==============


@pytest.mark.asyncio
async def test_action_renew_token_when_cookie_invalid_and_score_60_80() -> None:
    """score 60-80 且 Cookie 无效时建议续期"""
    checker = SessionHealthChecker()
    # score = 0 + 30 + 20 + 10 = 60
    checker.set_cookie_checker(lambda: False)
    checker.set_api_checker(AsyncMock(return_value=True))
    checker.set_page_checker(AsyncMock(return_value=True))
    checker.set_waf_status_provider(lambda: WAFStatus.CLEAR)

    report = await checker.check()
    assert 60 <= report.score < 80
    assert report.action == HealthAction.RENEW_TOKEN


@pytest.mark.asyncio
async def test_action_relogin_when_score_40_60() -> None:
    """score 40-60 时建议重新登录"""
    checker = SessionHealthChecker()
    # score = 0 + 0 + 20 + 10 = 30 → 实际 < 40, 应 PAUSE
    # 调整：score = 0 + 30 + 0 + 10 = 40
    checker.set_cookie_checker(lambda: False)
    checker.set_api_checker(AsyncMock(return_value=True))
    checker.set_page_checker(AsyncMock(return_value=False))
    checker.set_waf_status_provider(lambda: WAFStatus.CLEAR)

    report = await checker.check()
    assert report.score == 40
    assert report.action == HealthAction.RELOGIN


@pytest.mark.asyncio
async def test_action_pause_when_score_below_40() -> None:
    """score < 40 时建议暂停"""
    checker = SessionHealthChecker()
    # score = 0 + 0 + 0 + 10 = 10
    checker.set_cookie_checker(lambda: False)
    checker.set_api_checker(AsyncMock(return_value=False))
    checker.set_page_checker(AsyncMock(return_value=False))
    checker.set_waf_status_provider(lambda: WAFStatus.CLEAR)

    report = await checker.check()
    assert report.score < 40
    assert report.action == HealthAction.PAUSE


# ============== 状态查询测试 ==============


@pytest.mark.asyncio
async def test_get_last_report() -> None:
    """获取最近一次报告"""
    checker = SessionHealthChecker()
    assert checker.get_last_report() is None

    await checker.check()
    assert checker.get_last_report() is not None


@pytest.mark.asyncio
async def test_get_check_count() -> None:
    """检查次数计数"""
    checker = SessionHealthChecker()
    assert checker.get_check_count() == 0

    await checker.check()
    await checker.check()
    await checker.check()

    assert checker.get_check_count() == 3


def test_weights() -> None:
    """权重总和为 100"""
    checker = SessionHealthChecker()
    weights = checker.weights
    total = sum(weights.values())
    assert total == 100


# ============== 报告详情测试 ==============


@pytest.mark.asyncio
async def test_report_contains_score_breakdown() -> None:
    """报告包含评分明细"""
    checker = SessionHealthChecker()
    checker.set_cookie_checker(lambda: True)
    checker.set_api_checker(AsyncMock(return_value=False))
    checker.set_page_checker(AsyncMock(return_value=True))
    checker.set_waf_status_provider(lambda: WAFStatus.WARNING)

    report = await checker.check()

    assert "scores" in report.details
    assert report.details["scores"]["cookie"] == 40
    assert report.details["scores"]["api"] == 0
    assert report.details["scores"]["page"] == 20
    assert report.details["scores"]["waf"] == 5  # WARNING = 10 // 2
    assert report.details["scores"]["total"] == 65
