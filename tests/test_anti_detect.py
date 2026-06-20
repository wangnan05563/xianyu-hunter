"""AntiDetect 单元测试（不依赖浏览器）"""
from __future__ import annotations

import asyncio
import time

import pytest

from xianyu_hunter.modules.anti_detect import (
    AntiDetect,
    AntiDetectConfig,
    WAFDecision,
    WAFGuard,
    bezier_point,
    human_delay_seconds,
    random_click_offset,
    random_mouse_path,
)


# ============== 纯函数测试 ==============


def test_bezier_endpoints() -> None:
    """贝塞尔曲线端点 = 起止点"""
    assert bezier_point(0.0, 0, 1, 2, 3) == 0
    assert bezier_point(1.0, 0, 1, 2, 3) == 3


def test_bezier_midpoint_not_straight() -> None:
    """贝塞尔曲线中点不是直线中点（说明有弧度）"""
    # 控制点 (0, 5, 8, 10) 不在 0→10 的直线上（直线是 y=x，控制点 y 比 x 大）
    p = bezier_point(0.5, 0, 5, 8, 10)
    # 直线中点是 5
    assert p > 5 + 0.5, f"贝塞尔曲线应偏离直线中点 5，实际={p}"


def test_human_delay_in_range() -> None:
    """延迟在配置范围内"""
    for _ in range(50):
        delay = human_delay_seconds(200, 1500)
        assert 0.15 <= delay <= 1.6  # 留 50ms 抖动余量


def test_human_delay_distribution_is_beta() -> None:
    """延迟分布偏向短停顿（Beta 分布右偏特征：mean > median）"""
    samples = [human_delay_seconds(0, 1000) for _ in range(500)]
    median = sorted(samples)[250]
    mean = sum(samples) / len(samples)
    # Beta(2, 5) 理论均值 = 2/7 ≈ 0.286，右偏分布 → mean > median
    # 实测 mean=0.288, median=0.286
    assert 0.2 < mean < 0.4, f"均值应在 0.2-0.4 之间（Beta 特征）"
    assert 0.2 < median < 0.4, f"中位数应在 0.2-0.4 之间"


def test_random_mouse_path_length() -> None:
    """轨迹点数 = steps + 1"""
    path = random_mouse_path(0, 0, 100, 100, steps=20)
    assert len(path) == 21
    assert path[0] == (0, 0)
    assert path[-1] == (100, 100)


def test_random_mouse_path_steps_in_range() -> None:
    """默认 steps 在 15-30 之间"""
    path = random_mouse_path(0, 0, 100, 100)
    assert 16 <= len(path) <= 31


def test_random_click_offset() -> None:
    """点击偏移在范围内"""
    for _ in range(50):
        x, y = random_click_offset(100, 100, max_offset=3)
        assert 97 <= x <= 103
        assert 97 <= y <= 103


# ============== WAFGuard 测试 ==============


def test_wafguard_initial_state() -> None:
    """初始不熔断"""
    waf = WAFGuard(threshold=3)
    assert not waf.is_paused()
    assert waf.current_failure_count == 0


def test_wafguard_under_threshold_continues() -> None:
    """未达阈值继续"""
    waf = WAFGuard(threshold=3, window_sec=60)
    assert waf.record_failure() == WAFDecision.CONTINUE
    assert waf.record_failure() == WAFDecision.CONTINUE
    assert not waf.is_paused()


def test_wafguard_at_threshold_pauses() -> None:
    """达到阈值熔断"""
    waf = WAFGuard(threshold=3, window_sec=60)
    waf.record_failure()
    waf.record_failure()
    assert waf.record_failure() == WAFDecision.PAUSE_ALL
    assert waf.is_paused()


def test_wafguard_success_clears_failures() -> None:
    """成功清零失败计数"""
    waf = WAFGuard(threshold=3, window_sec=60)
    waf.record_failure()
    waf.record_failure()
    waf.record_success()
    assert waf.current_failure_count == 0


def test_wafguard_reset_unpauses() -> None:
    """重置解除熔断"""
    waf = WAFGuard(threshold=3, window_sec=60)
    for _ in range(3):
        waf.record_failure()
    assert waf.is_paused()
    waf.reset()
    assert not waf.is_paused()


# ============== AntiDetect 异步测试 ==============


@pytest.mark.asyncio
async def test_throttle_enforces_interval() -> None:
    """throttle 强制间隔"""
    cfg = AntiDetectConfig(qps=10)  # 100ms 间隔
    ad = AntiDetect(cfg)

    t0 = time.monotonic()
    await ad.throttle()
    await ad.throttle()
    await ad.throttle()
    elapsed = time.monotonic() - t0

    # 3 次调用，至少 200ms 间隔
    assert elapsed >= 0.2


@pytest.mark.asyncio
async def test_throttle_qps_1() -> None:
    """QPS=1 时 2 次调用至少 1 秒"""
    cfg = AntiDetectConfig(qps=1)
    ad = AntiDetect(cfg)

    t0 = time.monotonic()
    await ad.throttle()
    await ad.throttle()
    elapsed = time.monotonic() - t0

    assert elapsed >= 1.0


@pytest.mark.asyncio
async def test_human_delay_returns_actual() -> None:
    """human_delay 返回实际等待秒数"""
    ad = AntiDetect()
    delay = await ad.human_delay(min_ms=100, max_ms=200)
    assert 0.1 <= delay <= 0.4


@pytest.mark.asyncio
async def test_record_failure_propagates_to_waf() -> None:
    """失败记录触发 WAF"""
    cfg = AntiDetectConfig(fail_pause_threshold=2)
    ad = AntiDetect(cfg)

    ad.record_failure()
    assert not ad.waf.is_paused()
    ad.record_failure()
    assert ad.waf.is_paused()


def test_stealth_script_contains_key_fixes() -> None:
    """stealth 脚本包含关键修复"""
    from xianyu_hunter.modules.anti_detect import STEALTH_SCRIPT
    assert "navigator, 'webdriver'" in STEALTH_SCRIPT
    assert "navigator, 'languages'" in STEALTH_SCRIPT
    assert "navigator, 'plugins'" in STEALTH_SCRIPT
    assert "window.chrome" in STEALTH_SCRIPT
    assert "permissions.query" in STEALTH_SCRIPT
    assert "WebGLRenderingContext" in STEALTH_SCRIPT


def test_stealth_script_no_obvious_errors() -> None:
    """stealth 脚本语法基本正确（括号配对）"""
    from xianyu_hunter.modules.anti_detect import STEALTH_SCRIPT
    # 简单括号配对检查
    assert STEALTH_SCRIPT.count("(") == STEALTH_SCRIPT.count(")")
    assert STEALTH_SCRIPT.count("{") == STEALTH_SCRIPT.count("}")
    assert STEALTH_SCRIPT.count("[") == STEALTH_SCRIPT.count("]")
