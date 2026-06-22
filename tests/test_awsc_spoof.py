"""AWSCSpoof 单元测试"""
from __future__ import annotations

import pytest

from xianyu_hunter.modules.awsc_spoof import (
    AWSC_SPOOF_SCRIPT,
    BAXIA_CAPTCHA_DETECT_SCRIPT,
    BAXIA_LOCALSTORAGE_CHECK_SCRIPT,
    get_awsc_spoof_script,
    get_baxia_detect_script,
    get_baxia_localstorage_check_script,
    is_awsc_spoof_needed,
)


# ============== 脚本内容测试 ==============


def test_awsc_spoof_script_not_empty() -> None:
    """AWSC 伪装脚本非空"""
    assert len(AWSC_SPOOF_SCRIPT) > 100


def test_awsc_spoof_script_contains_baxia() -> None:
    """脚本包含 __baxia__ 处理"""
    assert "__baxia__" in AWSC_SPOOF_SCRIPT
    assert "baxiaInit" in AWSC_SPOOF_SCRIPT
    assert "renderNC" in AWSC_SPOOF_SCRIPT


def test_awsc_spoof_script_contains_awsc() -> None:
    """脚本包含 AWSC 处理"""
    assert "window.AWSC" in AWSC_SPOOF_SCRIPT
    assert "AWSC.use" in AWSC_SPOOF_SCRIPT


def test_awsc_spoof_script_contains_et() -> None:
    """脚本包含 __awsc_et__ 处理"""
    assert "__awsc_et__" in AWSC_SPOOF_SCRIPT
    assert "getETToken" in AWSC_SPOOF_SCRIPT


def test_awsc_spoof_script_contains_localstorage() -> None:
    """脚本包含 LocalStorage 修补"""
    assert "localStorage" in AWSC_SPOOF_SCRIPT
    assert "baxia_entry_config" in AWSC_SPOOF_SCRIPT


def test_awsc_spoof_script_contains_captcha_event() -> None:
    """脚本包含验证码触发事件通知"""
    assert "xh_captcha_triggered" in AWSC_SPOOF_SCRIPT
    assert "CustomEvent" in AWSC_SPOOF_SCRIPT


def test_awsc_spoof_script_iife() -> None:
    """脚本使用 IIFE（立即执行函数表达式）"""
    # 脚本开头有注释，IIFE 在注释之后
    assert "(function()" in AWSC_SPOOF_SCRIPT
    assert ")();" in AWSC_SPOOF_SCRIPT


def test_awsc_spoof_script_strict_mode() -> None:
    """脚本使用严格模式"""
    assert "'use strict'" in AWSC_SPOOF_SCRIPT


def test_awsc_spoof_script_brackets_balanced() -> None:
    """脚本括号配对"""
    assert AWSC_SPOOF_SCRIPT.count("(") == AWSC_SPOOF_SCRIPT.count(")")
    assert AWSC_SPOOF_SCRIPT.count("{") == AWSC_SPOOF_SCRIPT.count("}")
    assert AWSC_SPOOF_SCRIPT.count("[") == AWSC_SPOOF_SCRIPT.count("]")


# ============== 检测脚本测试 ==============


def test_baxia_detect_script_not_empty() -> None:
    """验证码检测脚本非空"""
    assert len(BAXIA_CAPTCHA_DETECT_SCRIPT) > 50


def test_baxia_detect_script_is_arrow_function() -> None:
    """检测脚本是箭头函数（供 page.evaluate 调用）"""
    assert BAXIA_CAPTCHA_DETECT_SCRIPT.strip().startswith("() => {")


def test_baxia_detect_script_checks_renderNC() -> None:
    """检测脚本检查 renderNC 标志"""
    assert "renderNC" in BAXIA_CAPTCHA_DETECT_SCRIPT


def test_baxia_detect_script_checks_dom() -> None:
    """检测脚本检查 DOM 元素"""
    assert "querySelector" in BAXIA_CAPTCHA_DETECT_SCRIPT
    assert "baxia" in BAXIA_CAPTCHA_DETECT_SCRIPT.lower()


def test_baxia_localstorage_check_script_not_empty() -> None:
    """LocalStorage 检查脚本非空"""
    assert len(BAXIA_LOCALSTORAGE_CHECK_SCRIPT) > 50


def test_baxia_localstorage_check_script_checks_keys() -> None:
    """LocalStorage 检查脚本检查关键 key"""
    assert "baxia_entry_config" in BAXIA_LOCALSTORAGE_CHECK_SCRIPT
    assert "auyst" in BAXIA_LOCALSTORAGE_CHECK_SCRIPT
    assert "syfhs" in BAXIA_LOCALSTORAGE_CHECK_SCRIPT


# ============== getter 函数测试 ==============


def test_get_awsc_spoof_script_returns_content() -> None:
    """get_awsc_spoof_script 返回脚本内容"""
    script = get_awsc_spoof_script()
    assert script == AWSC_SPOOF_SCRIPT
    assert "__baxia__" in script


def test_get_baxia_detect_script_returns_content() -> None:
    """get_baxia_detect_script 返回脚本内容"""
    script = get_baxia_detect_script()
    assert script == BAXIA_CAPTCHA_DETECT_SCRIPT


def test_get_baxia_localstorage_check_script_returns_content() -> None:
    """get_baxia_localstorage_check_script 返回脚本内容"""
    script = get_baxia_localstorage_check_script()
    assert script == BAXIA_LOCALSTORAGE_CHECK_SCRIPT


# ============== is_awsc_spoof_needed 测试 ==============


def test_is_awsc_spoof_needed_launch_mode() -> None:
    """launch 模式需要注入"""
    assert is_awsc_spoof_needed(use_cdp=False) is True


def test_is_awsc_spoof_needed_cdp_mode() -> None:
    """CDP 模式不需要注入"""
    assert is_awsc_spoof_needed(use_cdp=True) is False


def test_is_awsc_spoof_needed_default() -> None:
    """默认（无参数）需要注入"""
    assert is_awsc_spoof_needed() is True
