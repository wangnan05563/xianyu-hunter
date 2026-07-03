"""验证码处理器（设计文档 §4.8）

核心问题：触发滑块验证后现有方案只能熔断暂停，无主动处理能力。

解决方案：分级验证码处理策略。

验证码触发检测 → 判断类型
├─ 滑块验证码 (baxia NC)
│   ├─ 自动模式：图像识别滑块位置 + 贝塞尔曲线拖动
│   └─ 降级模式：截图推送到前端，用户手动完成
├─ 点选验证码
│   └─ 仅降级模式：截图推送到前端
└─ 短信验证码
    └─ 降级模式：通知用户输入

注意：本模块仅设计框架和接口，实际图像识别/拖动实现
需要根据闲鱼实际验证码页面结构调整。
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


class CaptchaType(str, Enum):
    """验证码类型"""
    SLIDER = "slider"         # 滑块验证码（baxia NC）
    CLICK = "click"           # 点选验证码
    SMS = "sms"               # 短信验证码
    UNKNOWN = "unknown"       # 未知类型


class CaptchaSolution(str, Enum):
    """验证码处理方式"""
    AUTO = "auto"       # 自动识别
    MANUAL = "manual"   # 降级到手动
    SKIP = "skip"       # 跳过（放弃）


@dataclass
class CaptchaDetection:
    """验证码检测结果"""
    detected: bool
    captcha_type: CaptchaType = CaptchaType.UNKNOWN
    page_url: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DragTrack:
    """拖动轨迹点"""
    points: list[tuple[float, float, int]]  # (x_offset, y_offset, delay_ms)

    @property
    def total_distance(self) -> float:
        """总拖动距离"""
        if not self.points:
            return 0.0
        return self.points[-1][0] - self.points[0][0]

    @property
    def total_duration_ms(self) -> int:
        """总时长（毫秒）"""
        return sum(p[2] for p in self.points)

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_count": len(self.points),
            "total_distance": round(self.total_distance, 2),
            "total_duration_ms": self.total_duration_ms,
        }


@dataclass
class SolveResult:
    """验证码处理结果"""
    success: bool
    solution: CaptchaSolution
    attempts: int = 0
    error: str = ""
    duration_sec: float = 0.0


class CaptchaHandler:
    """验证码处理器

    使用方式：
        handler = CaptchaHandler()
        handler.set_detector(my_detector)       # 设置检测器
        handler.set_auto_solver(my_auto_solver)  # 设置自动解决器
        handler.set_manual_handler(my_manual)    # 设置手动处理回调

        detection = await handler.detect(page)
        if detection.detected:
            result = await handler.solve(page, detection)
    """

    # 最大自动重试次数
    MAX_AUTO_ATTEMPTS = 3

    # 自动处理支持的验证码类型
    AUTO_SUPPORTED_TYPES = {CaptchaType.SLIDER}

    def __init__(self, max_attempts: int = MAX_AUTO_ATTEMPTS):
        self._max_attempts = max_attempts
        self._detector: Callable[[], Awaitable[CaptchaDetection]] | None = None
        self._auto_solver: Callable[[CaptchaDetection], Awaitable[bool]] | None = None
        self._manual_handler: Callable[[CaptchaDetection], Awaitable[bool]] | None = None
        self._stats: dict[str, int] = {
            "total_detected": 0,
            "auto_solved": 0,
            "manual_solved": 0,
            "failed": 0,
        }

    # ============== 配置 ==============

    def set_detector(self, detector: Callable[[], Awaitable[CaptchaDetection]]) -> None:
        """设置验证码检测器"""
        self._detector = detector

    def set_auto_solver(self, solver: Callable[[CaptchaDetection], Awaitable[bool]]) -> None:
        """设置自动解决器

        solver 接收 CaptchaDetection，返回是否成功
        """
        self._auto_solver = solver

    def set_manual_handler(self, handler: Callable[[CaptchaDetection], Awaitable[bool]]) -> None:
        """设置手动处理回调

        handler 接收 CaptchaDetection，返回是否成功
        """
        self._manual_handler = handler

    # ============== 核心流程 ==============

    async def detect(self) -> CaptchaDetection:
        """检测当前页面是否有验证码"""
        if not self._detector:
            return CaptchaDetection(detected=False)

        try:
            detection = await self._detector()
            if detection.detected:
                self._stats["total_detected"] += 1
                logger.warning(
                    "检测到验证码: type=%s, url=%s",
                    detection.captcha_type.value, detection.page_url,
                )
            return detection
        except Exception as e:
            logger.error("验证码检测异常: %s", e)
            return CaptchaDetection(detected=False)

    async def solve(self, detection: CaptchaDetection) -> SolveResult:
        """处理验证码

        策略：
        1. 如果验证码类型支持自动处理，先尝试自动
        2. 自动失败后降级到手动
        3. 手动不可用则跳过
        """
        if not detection.detected:
            return SolveResult(success=True, solution=CaptchaSolution.SKIP)

        start_time = time.time()
        captcha_type = detection.captcha_type

        # 尝试自动处理
        if captcha_type in self.AUTO_SUPPORTED_TYPES and self._auto_solver:
            result = await self._try_auto_solve(detection)
            if result.success:
                self._stats["auto_solved"] += 1
                result.duration_sec = time.time() - start_time
                return result

        # 降级到手动处理
        if self._manual_handler:
            result = await self._try_manual_solve(detection)
            if result.success:
                self._stats["manual_solved"] += 1
            else:
                self._stats["failed"] += 1
            result.duration_sec = time.time() - start_time
            return result

        # 无法处理
        self._stats["failed"] += 1
        return SolveResult(
            success=False,
            solution=CaptchaSolution.SKIP,
            error=f"无法处理 {captcha_type.value} 类型验证码",
            duration_sec=time.time() - start_time,
        )

    async def _try_auto_solve(self, detection: CaptchaDetection) -> SolveResult:
        """尝试自动解决验证码"""
        attempts = 0
        last_error = ""

        for attempt in range(1, self._max_attempts + 1):
            attempts = attempt
            logger.info("自动处理验证码 (尝试 %d/%d)", attempt, self._max_attempts)
            try:
                success = await self._auto_solver(detection)  # type: ignore
                if success:
                    return SolveResult(
                        success=True,
                        solution=CaptchaSolution.AUTO,
                        attempts=attempts,
                    )
                last_error = "自动解决器返回 False"
            except Exception as e:
                last_error = str(e)
                logger.warning("自动处理验证码失败 (尝试 %d): %s", attempt, e)

        return SolveResult(
            success=False,
            solution=CaptchaSolution.AUTO,
            attempts=attempts,
            error=last_error,
        )

    async def _try_manual_solve(self, detection: CaptchaDetection) -> SolveResult:
        """降级到手动处理"""
        try:
            success = await self._manual_handler(detection)  # type: ignore
            return SolveResult(
                success=success,
                solution=CaptchaSolution.MANUAL,
                attempts=1,
            )
        except Exception as e:
            return SolveResult(
                success=False,
                solution=CaptchaSolution.MANUAL,
                attempts=1,
                error=str(e),
            )

    # ============== 状态查询 ==============

    def get_stats(self) -> dict[str, int]:
        """获取处理统计"""
        return dict(self._stats)


# ============== 滑块轨迹生成 ==============


def generate_drag_track(
    distance: float,
) -> DragTrack:
    """生成滑块拖动轨迹

    关键：不能匀速拖动，必须模拟人类特征
    - 前 30% 距离：加速阶段（速度递增）
    - 中 50% 距离：匀速阶段（微小波动）
    - 后 20% 距离：减速阶段（速度递减，可能略微过冲再回弹）
    - 总时长：300-600ms

    Args:
        distance: 需要拖动的总距离（像素）

    Returns:
        DragTrack: 拖动轨迹点列表
    """
    if distance <= 0:
        return DragTrack(points=[(0.0, 0.0, 0)])

    points: list[tuple[float, float, int]] = []
    # 阶段划分：加速 0~30%，匀速 30~80%，减速 80~100%
    # 减速阶段到 distance，可能略微过冲

    # 生成轨迹点
    num_points = random.randint(20, 35)
    for i in range(num_points + 1):
        t = i / num_points  # 0.0 → 1.0

        # 计算当前位置（三阶段速度模型）
        if t < 0.3:
            # 加速阶段：二次曲线（位移 = a*t^2）
            progress = (t / 0.3) ** 2 * 0.3
        elif t < 0.8:
            # 匀速阶段：线性
            progress = 0.3 + (t - 0.3) / 0.5 * 0.5
        else:
            # 减速阶段：二次曲线减速
            local_t = (t - 0.8) / 0.2
            progress = 0.8 + (1 - (1 - local_t) ** 2) * 0.2

        x = distance * progress
        # Y 轴微小随机抖动（人类拖动不可能完全水平）
        y = random.uniform(-2, 2)

        # 每个点的延迟（加速阶段间隔短，减速阶段间隔长）
        if t < 0.3:
            delay = random.randint(8, 15)
        elif t < 0.8:
            delay = random.randint(10, 20)
        else:
            delay = random.randint(15, 30)

        points.append((round(x, 2), round(y, 2), delay))

    # 过冲 + 回弹（10% 概率）
    if random.random() < 0.1:
        overshoot = random.uniform(2, 5)
        points.append((
            round(distance + overshoot, 2),
            round(random.uniform(-1, 1), 2),
            random.randint(20, 40),
        ))
        # 回弹
        points.append((
            round(distance, 2),
            round(random.uniform(-1, 1), 2),
            random.randint(30, 50),
        ))

    return DragTrack(points=points)


def detect_captcha_from_response(response_data: dict) -> CaptchaDetection:
    """从 API 响应中检测验证码

    闲鱼 API 返回验证码时的典型特征：
    - ret 字段包含特定错误码
    - data 字段包含验证码 URL
    """
    # 检查 ret 字段中的验证码相关错误码
    ret_codes = response_data.get("ret", [])
    if isinstance(ret_codes, str):
        ret_codes = [ret_codes]

    captcha_indicators = [
        "FAIL_SYS_ILLEGAL_ACCESS",
        "RGV587_ERROR",
        "x5sec",
        "sec_verify",
        "punish",
    ]

    for code in ret_codes:
        for indicator in captcha_indicators:
            if indicator in str(code):
                return CaptchaDetection(
                    detected=True,
                    captcha_type=CaptchaType.SLIDER,  # 闲鱼主要用滑块
                    details={"ret_code": code, "response": response_data},
                )

    # 检查 data 字段中的验证码 URL
    data = response_data.get("data", {})
    # S1066: 合并嵌套 if，条件同维度且无 else 分支，合并后可读性更佳
    if isinstance(data, dict) and data.get("url") and "sec" in str(data.get("url", "")).lower():
        return CaptchaDetection(
            detected=True,
            captcha_type=CaptchaType.SLIDER,
            details={"captcha_url": data.get("url")},
        )

    return CaptchaDetection(detected=False)
