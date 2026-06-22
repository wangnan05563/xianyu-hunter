"""CaptchaHandler 单元测试"""
from __future__ import annotations

import random
from unittest.mock import AsyncMock

import pytest

from xianyu_hunter.modules.captcha_handler import (
    CaptchaDetection,
    CaptchaHandler,
    CaptchaSolution,
    CaptchaType,
    DragTrack,
    SolveResult,
    detect_captcha_from_response,
    generate_drag_track,
)


# ============== 枚举测试 ==============


def test_captcha_type_values() -> None:
    """验证码类型枚举值正确"""
    assert CaptchaType.SLIDER.value == "slider"
    assert CaptchaType.CLICK.value == "click"
    assert CaptchaType.SMS.value == "sms"
    assert CaptchaType.UNKNOWN.value == "unknown"


def test_captcha_solution_values() -> None:
    """处理方式枚举值正确"""
    assert CaptchaSolution.AUTO.value == "auto"
    assert CaptchaSolution.MANUAL.value == "manual"
    assert CaptchaSolution.SKIP.value == "skip"


# ============== DragTrack 测试 ==============


def test_drag_track_total_distance() -> None:
    """总拖动距离计算正确"""
    track = DragTrack(points=[(0.0, 0.0, 10), (50.0, 1.0, 20), (100.0, 0.0, 30)])
    assert track.total_distance == 100.0


def test_drag_track_total_duration() -> None:
    """总时长计算正确"""
    track = DragTrack(points=[(0.0, 0.0, 10), (50.0, 1.0, 20), (100.0, 0.0, 30)])
    assert track.total_duration_ms == 60


def test_drag_track_empty() -> None:
    """空轨迹距离和时长为 0"""
    track = DragTrack(points=[])
    assert track.total_distance == 0.0
    assert track.total_duration_ms == 0


def test_drag_track_to_dict() -> None:
    """to_dict 序列化正确"""
    track = DragTrack(points=[(0.0, 0.0, 10), (100.0, 0.0, 20)])
    d = track.to_dict()
    assert d["point_count"] == 2
    assert d["total_distance"] == 100.0
    assert d["total_duration_ms"] == 30


# ============== generate_drag_track 测试 ==============


def test_generate_drag_track_basic() -> None:
    """基本轨迹生成"""
    random.seed(42)
    track = generate_drag_track(distance=100.0)
    assert len(track.points) > 10
    assert track.total_distance > 0


def test_generate_drag_track_starts_near_zero() -> None:
    """轨迹起点接近 0"""
    random.seed(42)
    track = generate_drag_track(distance=100.0)
    assert abs(track.points[0][0]) < 5  # 起点接近 0


def test_generate_drag_track_ends_near_distance() -> None:
    """轨迹终点接近目标距离"""
    random.seed(42)
    track = generate_drag_track(distance=100.0)
    # 最后一个点应接近 100（可能有过冲）
    last_x = track.points[-1][0]
    assert 95 <= last_x <= 110


def test_generate_drag_track_zero_distance() -> None:
    """距离为 0 时返回单点"""
    track = generate_drag_track(distance=0)
    assert len(track.points) == 1
    assert track.total_distance == 0


def test_generate_drag_track_negative_distance() -> None:
    """负距离返回单点"""
    track = generate_drag_track(distance=-10)
    assert len(track.points) == 1


def test_generate_drag_track_has_y_jitter() -> None:
    """轨迹有 Y 轴抖动（人类特征）"""
    random.seed(42)
    track = generate_drag_track(distance=100.0)
    y_values = [p[1] for p in track.points]
    # 不应所有 Y 都为 0
    assert any(y != 0 for y in y_values)


def test_generate_drag_track_non_uniform_speed() -> None:
    """轨迹速度非匀速（人类特征）"""
    random.seed(42)
    track = generate_drag_track(distance=100.0)
    # 检查延迟不是全部相同
    delays = [p[2] for p in track.points]
    assert len(set(delays)) > 3, "延迟应有多样性"


# ============== detect_captcha_from_response 测试 ==============


def test_detect_captcha_rgv587() -> None:
    """检测 RGV587_ERROR"""
    response = {"ret": ["RGV587_ERROR::会话失效"]}
    detection = detect_captcha_from_response(response)
    assert detection.detected is True
    assert detection.captcha_type == CaptchaType.SLIDER


def test_detect_captcha_x5sec() -> None:
    """检测 x5sec"""
    response = {"ret": ["FAIL_SYS_ILLEGAL_ACCESS:x5sec"]}
    detection = detect_captcha_from_response(response)
    assert detection.detected is True


def test_detect_captcha_sec_url() -> None:
    """检测验证码 URL"""
    response = {"data": {"url": "https://sec.taobao.com/captcha"}}
    detection = detect_captcha_from_response(response)
    assert detection.detected is True


def test_detect_captcha_normal_response() -> None:
    """正常响应不检测到验证码"""
    response = {"ret": ["SUCCESS"], "data": {"items": []}}
    detection = detect_captcha_from_response(response)
    assert detection.detected is False


def test_detect_captcha_empty_response() -> None:
    """空响应不检测到验证码"""
    detection = detect_captcha_from_response({})
    assert detection.detected is False


def test_detect_captcha_string_ret() -> None:
    """ret 为字符串时也能检测"""
    response = {"ret": "RGV587_ERROR"}
    detection = detect_captcha_from_response(response)
    assert detection.detected is True


# ============== CaptchaHandler.detect 测试 ==============


@pytest.mark.asyncio
async def test_detect_no_detector() -> None:
    """未设置检测器时返回未检测到"""
    handler = CaptchaHandler()
    detection = await handler.detect()
    assert detection.detected is False


@pytest.mark.asyncio
async def test_detect_with_detector() -> None:
    """设置检测器后正确检测"""
    handler = CaptchaHandler()
    handler.set_detector(AsyncMock(return_value=CaptchaDetection(
        detected=True,
        captcha_type=CaptchaType.SLIDER,
        page_url="https://example.com/captcha",
    )))

    detection = await handler.detect()
    assert detection.detected is True
    assert detection.captcha_type == CaptchaType.SLIDER


@pytest.mark.asyncio
async def test_detect_exception_returns_not_detected() -> None:
    """检测器抛异常时返回未检测到"""
    handler = CaptchaHandler()
    handler.set_detector(AsyncMock(side_effect=Exception("error")))

    detection = await handler.detect()
    assert detection.detected is False


@pytest.mark.asyncio
async def test_detect_increments_stats() -> None:
    """检测到验证码时增加计数"""
    handler = CaptchaHandler()
    handler.set_detector(AsyncMock(return_value=CaptchaDetection(
        detected=True, captcha_type=CaptchaType.SLIDER,
    )))

    await handler.detect()
    await handler.detect()

    assert handler.get_stats()["total_detected"] == 2


# ============== CaptchaHandler.solve 测试 ==============


@pytest.mark.asyncio
async def test_solve_not_detected_returns_skip() -> None:
    """未检测到验证码时返回跳过"""
    handler = CaptchaHandler()
    detection = CaptchaDetection(detected=False)
    result = await handler.solve(detection)
    assert result.success is True
    assert result.solution == CaptchaSolution.SKIP


@pytest.mark.asyncio
async def test_solve_auto_success() -> None:
    """自动处理成功"""
    handler = CaptchaHandler()
    handler.set_auto_solver(AsyncMock(return_value=True))

    detection = CaptchaDetection(detected=True, captcha_type=CaptchaType.SLIDER)
    result = await handler.solve(detection)

    assert result.success is True
    assert result.solution == CaptchaSolution.AUTO
    assert result.attempts == 1
    assert handler.get_stats()["auto_solved"] == 1


@pytest.mark.asyncio
async def test_solve_auto_failure_then_manual() -> None:
    """自动失败后降级到手动"""
    handler = CaptchaHandler(max_attempts=2)
    handler.set_auto_solver(AsyncMock(return_value=False))
    handler.set_manual_handler(AsyncMock(return_value=True))

    detection = CaptchaDetection(detected=True, captcha_type=CaptchaType.SLIDER)
    result = await handler.solve(detection)

    assert result.success is True
    assert result.solution == CaptchaSolution.MANUAL
    assert handler.get_stats()["auto_solved"] == 0
    assert handler.get_stats()["manual_solved"] == 1


@pytest.mark.asyncio
async def test_solve_auto_retries() -> None:
    """自动处理重试"""
    handler = CaptchaHandler(max_attempts=3)
    # 前两次失败，第三次成功
    handler.set_auto_solver(AsyncMock(side_effect=[False, False, True]))

    detection = CaptchaDetection(detected=True, captcha_type=CaptchaType.SLIDER)
    result = await handler.solve(detection)

    assert result.success is True
    assert result.attempts == 3


@pytest.mark.asyncio
async def test_solve_auto_exception_retries() -> None:
    """自动处理异常时重试"""
    handler = CaptchaHandler(max_attempts=2)
    handler.set_auto_solver(AsyncMock(side_effect=[Exception("err"), True]))

    detection = CaptchaDetection(detected=True, captcha_type=CaptchaType.SLIDER)
    result = await handler.solve(detection)

    assert result.success is True
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_solve_no_auto_no_manual() -> None:
    """无自动无手动时失败"""
    handler = CaptchaHandler()
    detection = CaptchaDetection(detected=True, captcha_type=CaptchaType.SLIDER)
    result = await handler.solve(detection)

    assert result.success is False
    assert result.solution == CaptchaSolution.SKIP
    assert handler.get_stats()["failed"] == 1


@pytest.mark.asyncio
async def test_solve_click_type_no_auto() -> None:
    """点选验证码不支持自动处理"""
    handler = CaptchaHandler()
    handler.set_auto_solver(AsyncMock(return_value=True))
    handler.set_manual_handler(AsyncMock(return_value=True))

    detection = CaptchaDetection(detected=True, captcha_type=CaptchaType.CLICK)
    result = await handler.solve(detection)

    # 点选不支持自动，直接走手动
    assert result.solution == CaptchaSolution.MANUAL


@pytest.mark.asyncio
async def test_solve_sms_type_no_auto() -> None:
    """短信验证码不支持自动处理"""
    handler = CaptchaHandler()
    handler.set_auto_solver(AsyncMock(return_value=True))
    handler.set_manual_handler(AsyncMock(return_value=True))

    detection = CaptchaDetection(detected=True, captcha_type=CaptchaType.SMS)
    result = await handler.solve(detection)

    assert result.solution == CaptchaSolution.MANUAL


@pytest.mark.asyncio
async def test_solve_manual_exception() -> None:
    """手动处理异常时失败"""
    handler = CaptchaHandler()
    handler.set_manual_handler(AsyncMock(side_effect=Exception("error")))

    detection = CaptchaDetection(detected=True, captcha_type=CaptchaType.SLIDER)
    result = await handler.solve(detection)

    assert result.success is False
    assert "error" in result.error


# ============== 统计测试 ==============


@pytest.mark.asyncio
async def test_stats_after_multiple_solves() -> None:
    """多次处理后统计正确"""
    handler = CaptchaHandler()
    handler.set_auto_solver(AsyncMock(return_value=True))

    for _ in range(3):
        detection = CaptchaDetection(detected=True, captcha_type=CaptchaType.SLIDER)
        await handler.solve(detection)

    stats = handler.get_stats()
    assert stats["auto_solved"] == 3
    assert stats["total_detected"] == 0  # detect 未调用


def test_get_stats_initial() -> None:
    """初始统计为 0"""
    handler = CaptchaHandler()
    stats = handler.get_stats()
    assert all(v == 0 for v in stats.values())
