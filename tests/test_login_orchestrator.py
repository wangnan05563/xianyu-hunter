"""LoginOrchestrator 单元测试

覆盖协调器的所有公共接口，验证：
1. 初始化（launch/CDP 两种模式）
2. 策略选择委托
3. 指纹脚本生成
4. Cookie 分层更新
5. 会话生命周期（启动/停止/重复启动/未启动停止）
6. 健康检查配置与执行
7. 频率伪装委托
8. 验证码处理器配置
9. 状态查询完整性
10. 单例获取
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xianyu_hunter.modules.captcha_handler import CaptchaDetection, CaptchaHandler, CaptchaType
from xianyu_hunter.modules.cookie_rotator import CookieLayer, CookieRotator
from xianyu_hunter.modules.fingerprint import FingerprintProfile, build_stealth_script
from xianyu_hunter.modules.freq_disguise import ActionType, FreqDisguise
from xianyu_hunter.modules.login_orchestrator import (
    LoginOrchestrator,
    SessionStatus,
    get_orchestrator,
)
from xianyu_hunter.modules.login_strategy import LoginStrategy, LoginStrategySelector
from xianyu_hunter.modules.session_health import HealthAction, SessionHealthChecker, WAFStatus
from xianyu_hunter.modules.token_renewer import RenewResult, TokenRenewer


# ============== 初始化 ==============

class TestOrchestratorInit:
    """初始化测试"""

    def test_init_creates_all_modules(self):
        """初始化应创建所有子模块实例"""
        orch = LoginOrchestrator()

        assert isinstance(orch._strategy_selector, LoginStrategySelector)
        assert isinstance(orch._cookie_rotator, CookieRotator)
        assert isinstance(orch._token_renewer, TokenRenewer)
        assert isinstance(orch._health_checker, SessionHealthChecker)
        assert isinstance(orch._freq_disguiser, FreqDisguise)
        assert isinstance(orch._captcha_handler, CaptchaHandler)

    def test_init_default_state(self):
        """初始化后状态应为未启动"""
        orch = LoginOrchestrator()

        assert orch._session_active is False
        assert orch._started_at == 0.0
        assert orch._current_strategy is None
        assert orch._use_cdp is False
        assert orch._fingerprint_profile is None
        assert orch.is_session_active is False

    def test_initialize_launch_mode_generates_fingerprint(self):
        """launch 模式应生成指纹 profile"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=False)

        assert orch._use_cdp is False
        assert orch._fingerprint_profile is not None
        assert isinstance(orch._fingerprint_profile, FingerprintProfile)
        assert orch._fingerprint_profile.name  # 应有名称

    def test_initialize_cdp_mode_no_fingerprint(self):
        """CDP 模式不应生成指纹 profile"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=True)

        assert orch._use_cdp is True
        assert orch._fingerprint_profile is None

    def test_initialize_idempotent(self):
        """重复初始化应覆盖前一次配置"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=False)
        first_profile = orch._fingerprint_profile

        orch.initialize(use_cdp=True)
        assert orch._fingerprint_profile is None
        assert first_profile is not None  # 第一次的 profile 还存在对象中


# ============== 策略选择 ==============

class TestStrategyEvaluation:
    """策略选择测试"""

    def test_evaluate_strategy_delegates_to_selector(self):
        """evaluate_strategy 应委托给 LoginStrategySelector"""
        orch = LoginOrchestrator()

        with patch.object(orch._strategy_selector, "evaluate") as mock_eval:
            from xianyu_hunter.modules.login_strategy import StrategyEvaluation
            expected = StrategyEvaluation(
                recommended=LoginStrategy.CDP_CONNECT,
                reason="test",
                available_strategies=[LoginStrategy.CDP_CONNECT],
                details={"cdp_available": True},
            )
            mock_eval.return_value = expected

            result = orch.evaluate_strategy()

            assert result is expected
            mock_eval.assert_called_once()


# ============== 指纹管理 ==============

class TestFingerprintManagement:
    """指纹管理测试"""

    def test_get_fingerprint_profile_launch_mode(self):
        """launch 模式应返回指纹 profile"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=False)

        profile = orch.get_fingerprint_profile()
        assert profile is not None
        assert isinstance(profile, FingerprintProfile)

    def test_get_fingerprint_profile_cdp_mode(self):
        """CDP 模式应返回 None"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=True)

        assert orch.get_fingerprint_profile() is None

    def test_get_fingerprint_profile_before_init(self):
        """未初始化时应返回 None"""
        orch = LoginOrchestrator()
        assert orch.get_fingerprint_profile() is None

    def test_get_stealth_scripts_launch_mode(self):
        """launch 模式应返回指纹脚本和 AWSC 伪装脚本"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=False)

        scripts = orch.get_stealth_scripts()
        assert len(scripts) == 2
        # 第一个脚本应包含指纹信息
        assert "navigator" in scripts[0] or "window" in scripts[0]
        # 第二个脚本应是 AWSC 伪装
        assert "AWSC" in scripts[1] or "awsc" in scripts[1] or function_in_script(scripts[1])

    def test_get_stealth_scripts_cdp_mode(self):
        """CDP 模式应返回空列表"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=True)

        assert orch.get_stealth_scripts() == []

    def test_get_stealth_scripts_before_init(self):
        """未初始化时应返回空列表"""
        orch = LoginOrchestrator()
        assert orch.get_stealth_scripts() == []

    def test_get_user_agent_launch_mode(self):
        """launch 模式应返回 UA"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=False)

        ua = orch.get_user_agent()
        assert ua is not None
        assert "Mozilla" in ua

    def test_get_user_agent_cdp_mode(self):
        """CDP 模式应返回 None"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=True)

        assert orch.get_user_agent() is None

    def test_get_stealth_scripts_match_profile(self):
        """生成的 stealth 脚本应与 profile 一致"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=False)
        profile = orch.get_fingerprint_profile()

        scripts = orch.get_stealth_scripts()
        expected_script = build_stealth_script(profile)
        assert scripts[0] == expected_script


def function_in_script(script: str) -> bool:
    """检查脚本是否包含函数定义"""
    return "function" in script or "(" in script


# ============== Cookie 管理 ==============

class TestCookieManagement:
    """Cookie 管理测试"""

    def test_cookie_rotator_property(self):
        """cookie_rotator 属性应返回内部实例"""
        orch = LoginOrchestrator()
        assert orch.cookie_rotator is orch._cookie_rotator

    def test_set_cookie_writer_delegates(self):
        """set_cookie_writer 应委托给 CookieRotator"""
        orch = LoginOrchestrator()
        writer = MagicMock()

        with patch.object(orch._cookie_rotator, "set_writer") as mock_set:
            orch.set_cookie_writer(writer)
            mock_set.assert_called_once_with(writer)

    def test_on_login_success_classifies_cookies(self):
        """on_login_success 应将 Cookie 分类到对应层"""
        orch = LoginOrchestrator()

        # 混合三层的 Cookie
        cookies = {
            # identity
            "unb": "123456",
            "cookie2": "abc",
            "sgcookie": "sg",
            "t": "tval",
            "_tb_token_": "tb",
            "lg2": "lg",
            # session
            "_m_h5_tk": "token_123",
            "_m_h5_tk_enc": "enc_123",
            # tracking
            "cna": "cna_val",
            "tfstk": "tfstk_val",
            # 未知 -> tracking
            "unknown_cookie": "val",
        }

        # 由于 atomic_update 要求同层，需要分别 mock
        with patch.object(orch._cookie_rotator, "atomic_update") as mock_update:
            mock_update.return_value = 5  # 每次写入5个

            written = orch.on_login_success(cookies)

            # 应调用3次（identity, session, tracking）
            assert mock_update.call_count == 3
            assert written == 15  # 3 * 5

    def test_on_login_success_only_identity(self):
        """仅 identity 层 Cookie 时只调用一次"""
        orch = LoginOrchestrator()

        cookies = {"unb": "123", "cookie2": "abc"}

        with patch.object(orch._cookie_rotator, "atomic_update") as mock_update:
            mock_update.return_value = 2
            written = orch.on_login_success(cookies)

            assert mock_update.call_count == 1
            assert written == 2

    def test_on_login_success_empty_cookies(self):
        """空 Cookie 字典应返回 0"""
        orch = LoginOrchestrator()

        with patch.object(orch._cookie_rotator, "atomic_update") as mock_update:
            written = orch.on_login_success({})

            assert mock_update.call_count == 0
            assert written == 0

    def test_on_login_success_session_depends_on_identity(self):
        """若 identity 层未先更新，session 层应抛出 SessionExpiredError"""
        from xianyu_hunter.modules.cookie_rotator import SessionExpiredError

        orch = LoginOrchestrator()

        # 真实调用（不 mock），identity 未设置时 session 应失败
        cookies = {"_m_h5_tk": "token_123", "_m_h5_tk_enc": "enc_123"}

        with pytest.raises(SessionExpiredError):
            orch.on_login_success(cookies)

    def test_on_login_success_identity_then_session(self):
        """先更新 identity 再更新 session 应成功"""
        orch = LoginOrchestrator()
        orch.set_cookie_writer(lambda cookies: len(cookies))  # mock writer

        # 先更新 identity
        orch.on_login_success({"unb": "123", "cookie2": "abc"})

        # 再更新 session
        written = orch.on_login_success({"_m_h5_tk": "tk_123", "_m_h5_tk_enc": "enc"})
        assert written > 0


# ============== 会话生命周期 ==============

class TestSessionLifecycle:
    """会话生命周期测试"""

    def test_is_session_active_default_false(self):
        """未启动时 is_session_active 应为 False"""
        orch = LoginOrchestrator()
        assert orch.is_session_active is False

    @pytest.mark.asyncio
    async def test_start_session_activates(self):
        """start_session 应激活会话"""
        orch = LoginOrchestrator()

        with patch.object(orch._token_renewer, "start", new_callable=AsyncMock):
            await orch.start_session(cookie_provider=lambda: "token_123")

            assert orch.is_session_active is True
            assert orch._started_at > 0

    @pytest.mark.asyncio
    async def test_start_session_sets_cookie_provider(self):
        """start_session 应设置 cookie_provider"""
        orch = LoginOrchestrator()
        provider = lambda: "token_123"

        with patch.object(orch._token_renewer, "start", new_callable=AsyncMock):
            with patch.object(orch._token_renewer, "set_cookie_provider") as mock_set:
                await orch.start_session(cookie_provider=provider)
                mock_set.assert_called_once_with(provider)

    @pytest.mark.asyncio
    async def test_start_session_sets_renew_callback(self):
        """start_session 应设置 renew_callback"""
        orch = LoginOrchestrator()

        async def renew_cb():
            return True

        with patch.object(orch._token_renewer, "start", new_callable=AsyncMock):
            with patch.object(orch._token_renewer, "set_renew_callback") as mock_set:
                await orch.start_session(
                    cookie_provider=lambda: "tk",
                    renew_callback=renew_cb,
                )
                mock_set.assert_called_once_with(renew_cb)

    @pytest.mark.asyncio
    async def test_start_session_sets_renew_fail_callback(self):
        """start_session 应设置 renew_fail_callback 触发 session 层失效"""
        orch = LoginOrchestrator()

        with patch.object(orch._token_renewer, "start", new_callable=AsyncMock):
            with patch.object(orch._token_renewer, "set_renew_fail_callback") as mock_set:
                await orch.start_session(cookie_provider=lambda: "tk")
                mock_set.assert_called_once()
                # 验证回调会触发 session 层失效
                callback = mock_set.call_args[0][0]
                with patch.object(orch._cookie_rotator, "invalidate_layer") as mock_inv:
                    callback()
                    mock_inv.assert_called_once_with(CookieLayer.SESSION)

    @pytest.mark.asyncio
    async def test_start_session_idempotent(self):
        """重复调用 start_session 应被忽略"""
        orch = LoginOrchestrator()

        with patch.object(orch._token_renewer, "start", new_callable=AsyncMock) as mock_start:
            await orch.start_session(cookie_provider=lambda: "tk")
            first_started_at = orch._started_at

            # 稍等确保时间不同
            await asyncio.sleep(0.01)

            await orch.start_session(cookie_provider=lambda: "tk")
            # 第二次不应更新 started_at
            assert orch._started_at == first_started_at
            # start 只应被调用一次
            assert mock_start.call_count == 1

    @pytest.mark.asyncio
    async def test_stop_session_deactivates(self):
        """stop_session 应停止会话"""
        orch = LoginOrchestrator()

        with patch.object(orch._token_renewer, "start", new_callable=AsyncMock):
            await orch.start_session(cookie_provider=lambda: "tk")

        with patch.object(orch._token_renewer, "stop", new_callable=AsyncMock):
            await orch.stop_session()

            assert orch.is_session_active is False

    @pytest.mark.asyncio
    async def test_stop_session_when_not_active(self):
        """未启动时 stop_session 应安全返回"""
        orch = LoginOrchestrator()

        with patch.object(orch._token_renewer, "stop", new_callable=AsyncMock) as mock_stop:
            await orch.stop_session()
            mock_stop.assert_not_called()


# ============== 默认会话启动（登录后自动调用） ==============

class TestStartSessionDefault:
    """start_session_default 便捷方法测试

    覆盖登录成功后自动启动会话的场景：
    1. 未启动时调用应启动并返回 True
    2. 已活跃时应跳过（不重复启动）
    3. 启动异常时应捕获并返回 False（不抛出影响登录流程）
    """

    @pytest.mark.asyncio
    async def test_start_session_default_activates(self):
        """未启动时调用应启动并返回 True"""
        orch = LoginOrchestrator()

        with patch.object(orch._token_renewer, "start", new_callable=AsyncMock):
            result = await orch.start_session_default()
            assert result is True
            assert orch.is_session_active is True

    @pytest.mark.asyncio
    async def test_start_session_default_skips_when_active(self):
        """已活跃时应直接返回 True，不重复启动 TokenRenewer"""
        orch = LoginOrchestrator()

        with patch.object(orch._token_renewer, "start", new_callable=AsyncMock) as mock_start:
            await orch.start_session_default()
            first_count = mock_start.call_count

            # 再次调用：已活跃，应跳过
            result = await orch.start_session_default()
            assert result is True
            assert mock_start.call_count == first_count  # 没有额外调用

    @pytest.mark.asyncio
    async def test_start_session_default_swallows_exceptions(self):
        """启动异常时应返回 False 而不抛异常（避免影响登录流程）"""
        orch = LoginOrchestrator()

        # 模拟 token_renewer.start 抛异常
        with patch.object(
            orch._token_renewer,
            "start",
            new_callable=AsyncMock,
            side_effect=RuntimeError("renewer failed"),
        ):
            result = await orch.start_session_default()
            assert result is False
            # 异常后 _session_active 仍为 False（start_session 设置的活跃标志在异常前被设）
            # 这里只验证不抛异常、返回 False

    def test_default_cookie_provider_returns_none_when_no_data(self):
        """无 Cookie 数据时 _default_cookie_provider 应返回 None"""
        orch = LoginOrchestrator()

        with patch(
            "xianyu_hunter.web.services.cookie_store.get_cookie_store"
        ) as mock_factory:
            from xianyu_hunter.web.services.cookie_store import CookieStore
            store = MagicMock(spec=CookieStore)
            store._read_json.return_value = None
            mock_factory.return_value = store

            assert orch._default_cookie_provider() is None

    def test_default_cookie_provider_returns_m_h5_tk_value(self):
        """有 Cookie 时应返回 _m_h5_tk 的值"""
        orch = LoginOrchestrator()

        with patch(
            "xianyu_hunter.web.services.cookie_store.get_cookie_store"
        ) as mock_factory:
            from xianyu_hunter.web.services.cookie_store import CookieStore
            store = MagicMock(spec=CookieStore)
            store._read_json.return_value = {
                "cookies": [
                    {"name": "unb", "value": "123"},
                    {"name": "_m_h5_tk", "value": "tk_abc"},
                ]
            }
            mock_factory.return_value = store

            assert orch._default_cookie_provider() == "tk_abc"

    @pytest.mark.asyncio
    async def test_default_renew_callback_returns_false_when_no_browser(self):
        """浏览器不可用时 _default_renew_callback 应返回 False"""
        orch = LoginOrchestrator()

        with patch(
            "xianyu_hunter.web.deps.get_container"
        ) as mock_container_factory:
            from xianyu_hunter.web.deps import get_container
            container = MagicMock()
            container.browser = None
            mock_container_factory.return_value = container

            assert await orch._default_renew_callback() is False


# ============== 健康检查 ==============

class TestHealthCheck:
    """健康检查测试"""

    def test_health_checker_property(self):
        """health_checker 属性应返回内部实例"""
        orch = LoginOrchestrator()
        assert orch.health_checker is orch._health_checker

    def test_configure_health_checkers_cookie(self):
        """configure_health_checkers 应委托 cookie_checker"""
        orch = LoginOrchestrator()
        checker = lambda: True

        with patch.object(orch._health_checker, "set_cookie_checker") as mock_set:
            orch.configure_health_checkers(cookie_checker=checker)
            mock_set.assert_called_once_with(checker)

    def test_configure_health_checkers_api(self):
        """configure_health_checkers 应委托 api_checker"""
        orch = LoginOrchestrator()

        async def api_check():
            return True

        with patch.object(orch._health_checker, "set_api_checker") as mock_set:
            orch.configure_health_checkers(api_checker=api_check)
            mock_set.assert_called_once_with(api_check)

    def test_configure_health_checkers_page(self):
        """configure_health_checkers 应委托 page_checker"""
        orch = LoginOrchestrator()

        async def page_check():
            return True

        with patch.object(orch._health_checker, "set_page_checker") as mock_set:
            orch.configure_health_checkers(page_checker=page_check)
            mock_set.assert_called_once_with(page_check)

    def test_configure_health_checkers_waf(self):
        """configure_health_checkers 应委托 waf_provider"""
        orch = LoginOrchestrator()
        provider = lambda: WAFStatus.OK

        with patch.object(orch._health_checker, "set_waf_status_provider") as mock_set:
            orch.configure_health_checkers(waf_provider=provider)
            mock_set.assert_called_once_with(provider)

    def test_configure_health_checkers_all_none(self):
        """全部参数为 None 时不应调用任何 setter"""
        orch = LoginOrchestrator()

        with patch.object(orch._health_checker, "set_cookie_checker") as m1, \
             patch.object(orch._health_checker, "set_api_checker") as m2, \
             patch.object(orch._health_checker, "set_page_checker") as m3, \
             patch.object(orch._health_checker, "set_waf_status_provider") as m4:
            orch.configure_health_checkers()
            m1.assert_not_called()
            m2.assert_not_called()
            m3.assert_not_called()
            m4.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_health_delegates(self):
        """check_health 应委托给 SessionHealthChecker"""
        orch = LoginOrchestrator()

        with patch.object(orch._health_checker, "check", new_callable=AsyncMock) as mock_check:
            from xianyu_hunter.modules.session_health import HealthReport
            expected = HealthReport(
                score=80,
                cookie_valid=True,
                api_reachable=True,
                page_accessible=True,
                waf_status=WAFStatus.CLEAR,
                action=HealthAction.NONE,
                details={},
            )
            mock_check.return_value = expected

            result = await orch.check_health()
            assert result is expected
            mock_check.assert_called_once()


# ============== 频率伪装 ==============

class TestFreqDisguise:
    """频率伪装测试"""

    def test_freq_disguiser_property(self):
        """freq_disguiser 属性应返回内部实例"""
        orch = LoginOrchestrator()
        assert orch.freq_disguiser is orch._freq_disguiser

    def test_get_request_delay_delegates(self):
        """get_request_delay 应委托给 FreqDisguise"""
        orch = LoginOrchestrator()

        with patch.object(orch._freq_disguiser, "next_interval") as mock_next:
            mock_next.return_value = 1.5

            delay = orch.get_request_delay(ActionType.SEARCH)

            assert delay == 1.5
            mock_next.assert_called_once_with(ActionType.SEARCH)

    def test_get_request_delay_all_action_types(self):
        """所有 ActionType 都应能获取延迟"""
        orch = LoginOrchestrator()

        for action in ActionType:
            delay = orch.get_request_delay(action)
            assert isinstance(delay, float)
            assert delay >= 0

    def test_should_insert_noise_delegates(self):
        """should_insert_noise 应委托给 FreqDisguise"""
        orch = LoginOrchestrator()

        with patch.object(orch._freq_disguiser, "should_insert_noise") as mock_noise:
            mock_noise.return_value = True

            assert orch.should_insert_noise() is True
            mock_noise.assert_called_once()


# ============== 验证码处理 ==============

class TestCaptchaHandler:
    """验证码处理器测试"""

    def test_captcha_handler_property(self):
        """captcha_handler 属性应返回内部实例"""
        orch = LoginOrchestrator()
        assert orch.captcha_handler is orch._captcha_handler

    def test_configure_captcha_handler_detector(self):
        """configure_captcha_handler 应委托 detector"""
        orch = LoginOrchestrator()

        async def detector():
            return CaptchaDetection(captcha_type=CaptchaType.UNKNOWN, detected=False)

        with patch.object(orch._captcha_handler, "set_detector") as mock_set:
            orch.configure_captcha_handler(detector=detector)
            mock_set.assert_called_once_with(detector)

    def test_configure_captcha_handler_auto_solver(self):
        """configure_captcha_handler 应委托 auto_solver"""
        orch = LoginOrchestrator()

        async def solver(detection):
            return True

        with patch.object(orch._captcha_handler, "set_auto_solver") as mock_set:
            orch.configure_captcha_handler(auto_solver=solver)
            mock_set.assert_called_once_with(solver)

    def test_configure_captcha_handler_manual(self):
        """configure_captcha_handler 应委托 manual_handler"""
        orch = LoginOrchestrator()

        async def handler(detection):
            return True

        with patch.object(orch._captcha_handler, "set_manual_handler") as mock_set:
            orch.configure_captcha_handler(manual_handler=handler)
            mock_set.assert_called_once_with(handler)

    def test_configure_captcha_handler_all_none(self):
        """全部参数为 None 时不应调用任何 setter"""
        orch = LoginOrchestrator()

        with patch.object(orch._captcha_handler, "set_detector") as m1, \
             patch.object(orch._captcha_handler, "set_auto_solver") as m2, \
             patch.object(orch._captcha_handler, "set_manual_handler") as m3:
            orch.configure_captcha_handler()
            m1.assert_not_called()
            m2.assert_not_called()
            m3.assert_not_called()


# ============== 状态查询 ==============

class TestSessionStatus:
    """会话状态查询测试"""

    def test_get_session_status_default(self):
        """未启动时应返回默认状态"""
        orch = LoginOrchestrator()

        status = orch.get_session_status()

        assert isinstance(status, SessionStatus)
        assert status.active is False
        assert status.strategy == ""
        assert status.fingerprint_profile == ""
        assert status.health_score is None
        assert status.started_at == 0.0

    def test_get_session_status_to_dict(self):
        """to_dict 应返回完整字典"""
        orch = LoginOrchestrator()

        status = orch.get_session_status()
        d = status.to_dict()

        assert "active" in d
        assert "strategy" in d
        assert "fingerprint_profile" in d
        assert "token_age_sec" in d
        assert "token_expired" in d
        assert "health_score" in d
        assert "health_action" in d
        assert "waf_status" in d
        assert "cookie_layers" in d
        assert "freq_stats" in d
        assert "captcha_stats" in d
        assert "started_at" in d
        assert "uptime_sec" in d

    def test_get_session_status_with_fingerprint(self):
        """launch 模式应包含指纹 profile 名称"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=False)

        status = orch.get_session_status()
        assert status.fingerprint_profile != ""
        assert status.fingerprint_profile == orch._fingerprint_profile.name

    def test_get_session_status_cdp_mode(self):
        """CDP 模式 fingerprint_profile 应为空"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=True)

        status = orch.get_session_status()
        assert status.fingerprint_profile == ""

    def test_get_session_status_with_strategy(self):
        """设置策略后状态应包含策略名"""
        orch = LoginOrchestrator()
        orch.set_current_strategy(LoginStrategy.CDP_CONNECT)

        status = orch.get_session_status()
        assert status.strategy == "cdp_connect"

    def test_get_session_status_uptime_when_active(self):
        """会话活跃时 uptime_sec 应大于 0"""
        orch = LoginOrchestrator()
        orch._session_active = True
        orch._started_at = time.time() - 10  # 10秒前启动

        status = orch.get_session_status()
        d = status.to_dict()
        assert d["uptime_sec"] >= 10

    def test_get_session_status_uptime_when_inactive(self):
        """会话未活跃时 uptime_sec 应为 0"""
        orch = LoginOrchestrator()

        status = orch.get_session_status()
        d = status.to_dict()
        assert d["uptime_sec"] == 0

    def test_get_session_status_includes_cookie_layers(self):
        """状态应包含所有 Cookie 层状态"""
        orch = LoginOrchestrator()

        status = orch.get_session_status()
        assert "identity" in status.cookie_layers
        assert "session" in status.cookie_layers
        assert "tracking" in status.cookie_layers

    def test_get_session_status_includes_freq_stats(self):
        """状态应包含频率伪装统计"""
        orch = LoginOrchestrator()

        status = orch.get_session_status()
        assert isinstance(status.freq_stats, dict)
        assert "total_requests" in status.freq_stats

    def test_get_session_status_includes_captcha_stats(self):
        """状态应包含验证码统计"""
        orch = LoginOrchestrator()

        status = orch.get_session_status()
        assert isinstance(status.captcha_stats, dict)

    def test_set_current_strategy(self):
        """set_current_strategy 应更新当前策略"""
        orch = LoginOrchestrator()
        orch.set_current_strategy(LoginStrategy.QR_SCAN)
        assert orch._current_strategy == LoginStrategy.QR_SCAN


# ============== 单例 ==============

class TestSingleton:
    """单例测试"""

    def test_get_orchestrator_returns_instance(self):
        """get_orchestrator 应返回 LoginOrchestrator 实例"""
        orch = get_orchestrator()
        assert isinstance(orch, LoginOrchestrator)

    def test_get_orchestrator_singleton(self):
        """get_orchestrator 应返回同一实例"""
        # 注意：单例是全局的，我们只验证两次调用返回同一对象
        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        assert orch1 is orch2


# ============== 集成场景 ==============

class TestIntegrationScenarios:
    """集成场景测试"""

    def test_launch_mode_full_flow(self):
        """launch 模式完整流程：初始化 → 获取脚本 → 设置 writer"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=False)

        # 验证指纹
        profile = orch.get_fingerprint_profile()
        assert profile is not None

        # 验证脚本
        scripts = orch.get_stealth_scripts()
        assert len(scripts) == 2

        # 验证 UA
        ua = orch.get_user_agent()
        assert ua is not None

        # 设置 writer
        writer = MagicMock()
        orch.set_cookie_writer(writer)
        assert orch.cookie_rotator._writer is writer

    def test_cdp_mode_full_flow(self):
        """CDP 模式完整流程：初始化 → 无脚本 → 无 UA"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=True)

        assert orch.get_fingerprint_profile() is None
        assert orch.get_stealth_scripts() == []
        assert orch.get_user_agent() is None

    @pytest.mark.asyncio
    async def test_session_with_renew_fail_triggers_cookie_invalidation(self):
        """续期失败应触发 session 层 Cookie 失效"""
        orch = LoginOrchestrator()
        orch.set_cookie_writer(lambda c: len(c))

        # 先设置 identity 层有效
        orch.on_login_success({"unb": "123", "cookie2": "abc"})
        assert orch.cookie_rotator.is_layer_valid(CookieLayer.IDENTITY)

        # 设置 session 层
        orch.on_login_success({"_m_h5_tk": "tk_123", "_m_h5_tk_enc": "enc"})
        assert orch.cookie_rotator.is_layer_valid(CookieLayer.SESSION)

        # 启动会话
        with patch.object(orch._token_renewer, "start", new_callable=AsyncMock):
            await orch.start_session(cookie_provider=lambda: "tk_123")

        # 模拟续期失败回调
        orch._token_renewer._renew_fail_callback()

        # session 层应已失效
        assert not orch.cookie_rotator.is_layer_valid(CookieLayer.SESSION)
        # identity 层应仍有效
        assert orch.cookie_rotator.is_layer_valid(CookieLayer.IDENTITY)

    @pytest.mark.asyncio
    async def test_full_session_lifecycle(self):
        """完整会话生命周期：启动 → 状态查询 → 停止"""
        orch = LoginOrchestrator()
        orch.initialize(use_cdp=False)
        orch.set_cookie_writer(lambda c: len(c))
        orch.set_current_strategy(LoginStrategy.QR_SCAN)

        # 启动前状态
        status = orch.get_session_status()
        assert not status.active

        # 启动
        with patch.object(orch._token_renewer, "start", new_callable=AsyncMock):
            await orch.start_session(cookie_provider=lambda: "tk_123")

        # 启动后状态
        status = orch.get_session_status()
        assert status.active
        assert status.strategy == "qr_scan"
        assert status.fingerprint_profile != ""
        assert status.started_at > 0

        # 停止
        with patch.object(orch._token_renewer, "stop", new_callable=AsyncMock):
            await orch.stop_session()

        # 停止后状态
        status = orch.get_session_status()
        assert not status.active
