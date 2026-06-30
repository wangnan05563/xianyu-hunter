"""集成测试：反爬登录系统模块协同

验证各模块之间的协同工作：
1. FingerprintProfile + AWSCSpoof 脚本协同注入
2. CookieRotator + TokenRenewer 会话管理协同
3. MtopSigner + TokenRenewer 签名续期协同
4. SessionHealthChecker + CaptchaHandler 健康检查与验证码处理协同
5. LoginStrategySelector + FingerprintProfile 登录策略与指纹协同
6. FreqDisguise + 全系统 频率伪装集成
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from xianyu_hunter.modules.awsc_spoof import (
    AWSC_SPOOF_SCRIPT,
    get_awsc_spoof_script,
    is_awsc_spoof_needed,
)
from xianyu_hunter.modules.captcha_handler import (
    CaptchaDetection,
    CaptchaHandler,
    CaptchaSolution,
    CaptchaType,
    detect_captcha_from_response,
)
from xianyu_hunter.modules.cookie_rotator import (
    CookieLayer,
    CookieRotator,
    SessionExpiredError,
)
from xianyu_hunter.modules.fingerprint import (
    FingerprintProfile,
    build_stealth_script,
)
from xianyu_hunter.modules.freq_disguise import (
    ActionType,
    FreqDisguise,
    detect_pattern_regularity,
)
from xianyu_hunter.modules.login_strategy import (
    LoginStrategy,
    LoginStrategySelector,
)
from xianyu_hunter.modules.mtop_signer import (
    MtopAppKey,
    MtopRequest,
    MtopSigner,
    extract_token_from_m5tk,
)
from xianyu_hunter.modules.session_health import (
    HealthAction,
    SessionHealthChecker,
    WAFStatus,
)
from xianyu_hunter.modules.token_renewer import (
    RenewResult,
    RenewerConfig,
    TokenInfo,
    TokenRenewer,
)


# ============== 1. FingerprintProfile + AWSCSpoof 协同 ==============


class TestFingerprintAWSCIntegration:
    """指纹与 AWSC 伪装协同测试"""

    def test_stealth_and_awsc_scripts_compatible(self) -> None:
        """stealth 脚本与 AWSC 伪装脚本可同时注入"""
        profile = FingerprintProfile.random()
        stealth_script = build_stealth_script(profile)
        awsc_script = get_awsc_spoof_script()

        # 两个脚本不应有冲突的变量定义
        # stealth 修复 navigator 属性，AWSC 修复 window.__baxia__ 等
        assert "navigator" in stealth_script
        assert "__baxia__" in awsc_script
        # AWSC 脚本不应覆盖 stealth 修复的 navigator 属性
        assert "navigator, 'webdriver'" not in awsc_script

    def test_awsc_spoof_skipped_in_cdp_mode(self) -> None:
        """CDP 模式下跳过 AWSC 伪装"""
        # CDP 模式使用真实浏览器，AWSC 自然存在
        assert is_awsc_spoof_needed(use_cdp=True) is False
        assert is_awsc_spoof_needed(use_cdp=False) is True

    def test_combined_script_brackets_balanced(self) -> None:
        """组合脚本括号配对"""
        profile = FingerprintProfile.random()
        combined = build_stealth_script(profile) + get_awsc_spoof_script()
        assert combined.count("(") == combined.count(")")
        assert combined.count("{") == combined.count("}")


# ============== 2. CookieRotator + TokenRenewer 协同 ==============


class TestCookieTokenIntegration:
    """Cookie 分层与 Token 续期协同测试"""

    def test_token_renewer_uses_cookie_from_rotator(self) -> None:
        """TokenRenewer 从 CookieRotator 管理的 Cookie 中读取 token"""
        rotator = CookieRotator()
        rotator.set_writer(MagicMock(return_value=1))

        # 模拟登录：写入 identity 层
        rotator.atomic_update({"unb": "123", "cookie2": "abc"})
        # 写入 session 层
        m5tk_value = f"token_{int(time.time() * 1000)}"
        rotator.atomic_update({"_m_h5_tk": m5tk_value, "_m_h5_tk_enc": "enc"})

        # TokenRenewer 从某处获取 _m_h5_tk 值
        # 实际场景中由 cookie_store 提供
        renewer = TokenRenewer()
        renewer.set_cookie_provider(lambda: m5tk_value)

        status = renewer.get_status()
        assert status["token_age_sec"] is not None
        assert status["token_expired"] is False

    def test_session_expiry_cascades_to_token_renewer(self) -> None:
        """identity 层失效时 TokenRenewer 检测到会话失效"""
        rotator = CookieRotator()
        rotator.set_writer(MagicMock(return_value=1))

        rotator.atomic_update({"unb": "123"})
        rotator.atomic_update({"_m_h5_tk": "token_123"})

        # 模拟 identity 失效
        rotator.invalidate_layer(CookieLayer.IDENTITY)

        # session 层也失效了
        assert not rotator.is_layer_valid(CookieLayer.SESSION)

        # TokenRenewer 的 fail_callback 应被触发
        fail_called = MagicMock()
        renewer = TokenRenewer()
        renewer.set_cookie_provider(lambda: None)  # Cookie 已失效
        renewer.set_renew_fail_callback(fail_called)

        result = asyncio.run(renewer.check_and_renew())
        assert result == RenewResult.SESSION_EXPIRED
        fail_called.assert_called_once()

    def test_atomic_update_maintains_token_consistency(self) -> None:
        """原子更新保证 _m_h5_tk 和 _m_h5_tk_enc 同时更新"""
        rotator = CookieRotator()
        writer = MagicMock(return_value=10)
        rotator.set_writer(writer)

        # 先设置 identity
        rotator.atomic_update({"unb": "123"})

        # 原子更新 session 层（两个 Cookie 必须同时写入）
        rotator.atomic_update({
            "_m_h5_tk": "new_token_1700000000000",
            "_m_h5_tk_enc": "new_enc_value",
        })

        # 验证 writer 收到的 cookie 对象包含两个 session Cookie
        last_call = writer.call_args[0][0]
        session_cookies = [c for c in last_call if c["name"] in ("_m_h5_tk", "_m_h5_tk_enc")]
        assert len(session_cookies) >= 2  # 每个域名都有两个


# ============== 3. MtopSigner + TokenRenewer 协同 ==============


class TestMtopTokenIntegration:
    """MTOP 签名与 Token 续期协同测试"""

    def test_signer_uses_token_from_renewer(self) -> None:
        """MtopSigner 使用 TokenRenewer 管理的 token"""
        m5tk_value = "mytoken_1700000000000"

        renewer = TokenRenewer()
        renewer.set_cookie_provider(lambda: m5tk_value)

        signer = MtopSigner()
        # signer 的 token provider 从 renewer 获取
        signer.set_token_provider(lambda: renewer._cookie_provider())

        req = MtopRequest(api="test.api", data={"q": "test"})
        params = signer.sign(req)

        # 验证签名使用了正确的 token
        assert params.appKey == MtopAppKey.SEARCH
        assert len(params.sign) == 32

    def test_sign_fails_when_token_expired(self) -> None:
        """token 过期后签名失败"""
        signer = MtopSigner()
        signer.set_token_provider(lambda: None)  # token 已失效

        req = MtopRequest(api="test.api", data={})
        with pytest.raises(ValueError, match="未获取到"):
            signer.sign(req)

    def test_token_renewal_enables_signing(self) -> None:
        """token 续期后可以签名"""
        # 模拟 token 续期流程
        current_token = [None]  # 初始无 token

        renewer = TokenRenewer()
        renewer.set_cookie_provider(lambda: current_token[0])

        # 续期回调：更新 token
        async def renew_callback():
            current_token[0] = "newtoken_1700000001000"
            return True

        renewer.set_renew_callback(renew_callback)

        # 续期前无法签名
        signer = MtopSigner()
        signer.set_token_provider(lambda: current_token[0])

        with pytest.raises(ValueError):
            signer.sign(MtopRequest(api="test", data={}))

        # 执行续期
        result = asyncio.run(renew_callback())
        assert result is True

        # 续期后可以签名
        params = signer.sign(MtopRequest(api="test", data={}))
        assert len(params.sign) == 32


# ============== 4. SessionHealthChecker + CaptchaHandler 协同 ==============


class TestHealthCaptchaIntegration:
    """健康检查与验证码处理协同测试"""

    @pytest.mark.asyncio
    async def test_captcha_detected_lowers_health_score(self) -> None:
        """检测到验证码时健康评分下降"""
        health_checker = SessionHealthChecker()
        captcha_handler = CaptchaHandler()

        # 设置验证码检测器返回检测到
        captcha_handler.set_detector(AsyncMock(return_value=CaptchaDetection(
            detected=True,
            captcha_type=CaptchaType.SLIDER,
        )))

        # 健康检查的 API 检查器内部调用验证码检测
        async def api_check():
            detection = await captcha_handler.detect()
            return not detection.detected  # 检测到验证码 → API 不可达

        health_checker.set_api_checker(api_check)
        health_checker.set_cookie_checker(lambda: True)
        health_checker.set_page_checker(AsyncMock(return_value=True))
        health_checker.set_waf_status_provider(lambda: WAFStatus.WARNING)

        report = await health_checker.check()

        # API 不可达 + WAF 警告 → score 降低
        assert report.api_reachable is False
        assert report.score < 100

    @pytest.mark.asyncio
    async def test_health_check_triggers_captcha_handling(self) -> None:
        """健康检查发现 API 不可达时触发验证码处理"""
        health_checker = SessionHealthChecker()
        captcha_handler = CaptchaHandler()
        captcha_handler.set_detector(AsyncMock(return_value=CaptchaDetection(
            detected=True, captcha_type=CaptchaType.SLIDER,
        )))
        captcha_handler.set_auto_solver(AsyncMock(return_value=True))

        # 健康检查发现 API 不可达
        async def api_check():
            return False

        health_checker.set_api_checker(api_check)
        health_checker.set_cookie_checker(lambda: True)
        health_checker.set_page_checker(AsyncMock(return_value=True))
        health_checker.set_waf_status_provider(lambda: WAFStatus.CLEAR)

        report = await health_checker.check()
        assert not report.api_reachable

        # 触发验证码处理
        detection = await captcha_handler.detect()
        assert detection.detected

        result = await captcha_handler.solve(detection)
        assert result.success
        assert result.solution == CaptchaSolution.AUTO

    @pytest.mark.asyncio
    async def test_captcha_response_detection_integrates_with_handler(self) -> None:
        """API 响应中的验证码检测集成到处理流程"""
        # 模拟 API 返回验证码
        api_response = {"ret": ["RGV587_ERROR::会话失效"]}

        detection = detect_captcha_from_response(api_response)
        assert detection.detected

        handler = CaptchaHandler()
        handler.set_auto_solver(AsyncMock(return_value=True))

        result = await handler.solve(detection)
        assert result.success


# ============== 5. LoginStrategySelector + FingerprintProfile 协同 ==============


class TestLoginFingerprintIntegration:
    """登录策略与指纹协同测试"""

    def test_cdp_strategy_skips_fingerprint(self) -> None:
        """CDP 策略不需要指纹注入"""
        selector = LoginStrategySelector()

        # 模拟 CDP 可用
        import socket
        from unittest.mock import patch

        mock_socket = MagicMock()
        mock_socket.__enter__ = MagicMock(return_value=mock_socket)
        mock_socket.__exit__ = MagicMock(return_value=False)

        with patch("socket.create_connection", return_value=mock_socket):
            result = selector.evaluate()

        assert result.recommended == LoginStrategy.CDP_CONNECT

        # CDP 模式不需要指纹注入
        assert is_awsc_spoof_needed(use_cdp=True) is False

    def test_qr_strategy_needs_fingerprint(self) -> None:
        """扫码策略需要指纹注入"""
        selector = LoginStrategySelector()

        # 模拟无任何已有登录态
        import os
        from unittest.mock import patch

        with patch.object(selector, "_check_cdp_available", return_value=False), \
             patch.object(selector, "_check_user_data_cookies", return_value=False), \
             patch.object(selector, "_check_browser_importable", return_value=False):
            result = selector.evaluate()

        assert result.recommended == LoginStrategy.QR_SCAN

        # 扫码登录需要指纹注入
        assert is_awsc_spoof_needed(use_cdp=False) is True

        # 可以生成指纹 profile
        profile = FingerprintProfile.random()
        script = build_stealth_script(profile)
        assert len(script) > 100


# ============== 6. FreqDisguise + 全系统 频率伪装集成 ==============


class TestFreqDisguiseIntegration:
    """频率伪装与全系统集成测试"""

    def test_freq_disguise_with_token_renewal(self) -> None:
        """频率伪装应用于 token 续期间隔"""
        disguiser = FreqDisguise()
        renewer = TokenRenewer(RenewerConfig(check_interval_sec=120))

        # 续期检查间隔应受频率伪装影响
        # 实际场景中 check_interval + FreqDisguise 的随机延迟
        base_interval = renewer.config.check_interval_sec
        noise = disguiser.next_interval(ActionType.BROWSE)

        # 总间隔 = 基础间隔 + 噪声
        total_interval = base_interval + noise
        assert total_interval > base_interval

    def test_request_pattern_not_robot_like(self) -> None:
        """完整请求模式不像机器人"""
        disguiser = FreqDisguise()

        # 模拟一轮完整的搜索流程
        intervals = []
        intervals.append(disguiser.next_interval(ActionType.SEARCH))   # 搜索
        for _ in range(5):
            intervals.append(disguiser.next_interval(ActionType.BROWSE))  # 浏览结果
            intervals.append(disguiser.next_interval(ActionType.SCROLL))  # 滚动

        # 检查规律性
        regularity = detect_pattern_regularity(intervals)
        assert regularity < 0.3, f"请求模式太规律: {regularity}"

    def test_noise_requests_inserted(self) -> None:
        """噪声请求被插入"""
        disguiser = FreqDisguise(noise_probability=0.3)

        noise_count = 0
        for _ in range(100):
            if disguiser.should_insert_noise():
                noise_count += 1
                # 噪声请求是浏览类型
                assert disguiser.get_noise_action() == ActionType.BROWSE

        # 30% 概率，100 次约 30 次
        assert 20 <= noise_count <= 40


# ============== 7. 完整登录流程模拟 ==============


class TestFullLoginFlow:
    """完整登录流程集成测试"""

    def test_full_login_flow_qr_strategy(self) -> None:
        """扫码登录完整流程"""
        # 1. 策略选择
        selector = LoginStrategySelector()
        from unittest.mock import patch
        with patch.object(selector, "_check_cdp_available", return_value=False), \
             patch.object(selector, "_check_user_data_cookies", return_value=False), \
             patch.object(selector, "_check_browser_importable", return_value=False):
            evaluation = selector.evaluate()

        assert evaluation.recommended == LoginStrategy.QR_SCAN

        # 2. 生成指纹
        profile = FingerprintProfile.random()
        stealth_script = build_stealth_script(profile)
        awsc_script = get_awsc_spoof_script()
        assert len(stealth_script) > 0
        assert len(awsc_script) > 0

        # 3. 模拟登录成功后 Cookie 管理
        rotator = CookieRotator()
        rotator.set_writer(MagicMock(return_value=10))

        # 写入 identity 层
        rotator.atomic_update({
            "unb": "123456",
            "cookie2": "session_id",
            "sgcookie": "sg_token",
        })
        assert rotator.is_layer_valid(CookieLayer.IDENTITY)

        # 写入 session 层
        m5tk = f"token_{int(time.time() * 1000)}"
        rotator.atomic_update({"_m_h5_tk": m5tk, "_m_h5_tk_enc": "enc"})
        assert rotator.is_layer_valid(CookieLayer.SESSION)

        # 4. 启动 token 续期
        renewer = TokenRenewer()
        renewer.set_cookie_provider(lambda: m5tk)
        assert renewer.get_status()["token_expired"] is False

        # 5. 可以发起 MTOP 签名请求
        signer = MtopSigner()
        signer.set_token_provider(lambda: m5tk)
        params = signer.sign(MtopRequest(api="test.api", data={"q": "test"}))
        assert len(params.sign) == 32

    def test_full_flow_with_health_check(self) -> None:
        """完整流程含健康检查"""
        # 设置完整系统
        rotator = CookieRotator()
        rotator.set_writer(MagicMock(return_value=1))
        rotator.atomic_update({"unb": "123"})
        rotator.atomic_update({"_m_h5_tk": "token_123"})

        health_checker = SessionHealthChecker()
        health_checker.set_cookie_checker(lambda: rotator.is_layer_valid(CookieLayer.IDENTITY))
        health_checker.set_api_checker(AsyncMock(return_value=True))
        health_checker.set_page_checker(AsyncMock(return_value=True))
        health_checker.set_waf_status_provider(lambda: WAFStatus.CLEAR)

        # 执行健康检查
        report = asyncio.run(health_checker.check())

        assert report.is_healthy
        assert report.action == HealthAction.NONE

        # 模拟会话失效
        rotator.invalidate_all()

        report2 = asyncio.run(health_checker.check())
        assert not report2.is_healthy
        assert report2.action != HealthAction.NONE

    def test_full_flow_with_captcha_recovery(self) -> None:
        """完整流程含验证码恢复"""
        captcha_handler = CaptchaHandler()
        captcha_handler.set_detector(AsyncMock(return_value=CaptchaDetection(
            detected=True, captcha_type=CaptchaType.SLIDER,
        )))
        captcha_handler.set_auto_solver(AsyncMock(return_value=True))

        # 检测到验证码
        detection = asyncio.run(captcha_handler.detect())
        assert detection.detected

        # 自动处理
        result = asyncio.run(captcha_handler.solve(detection))
        assert result.success

        # 处理后统计
        stats = captcha_handler.get_stats()
        assert stats["auto_solved"] == 1
