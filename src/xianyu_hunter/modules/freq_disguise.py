"""频率伪装器（设计文档 §4.7）

核心问题：现有 QPS 限流是固定阈值（6/s），人类行为不可能如此规律。

解决方案：基于对数正态分布的请求间隔模拟，让请求模式呈现人类特征。

不同操作类型的间隔分布：
- browse（浏览商品）：对数正态分布，中位数 2.5s
- search（搜索操作）：对数正态分布，中位数 4.0s
- scroll（滚动加载）：指数分布，平均 2s

额外策略：
- 15% 概率插入"噪声请求"（访问 /personal 等），让整体模式更像真实用户
- 请求间隔有较大方差，避免被统计检测识别
"""
from __future__ import annotations

import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


class ActionType(str, Enum):
    """操作类型"""
    BROWSE = "browse"     # 浏览商品
    SEARCH = "search"     # 搜索操作
    SCROLL = "scroll"     # 滚动加载
    DETAIL = "detail"     # 查看详情
    LOGIN = "login"       # 登录操作


@dataclass
class IntervalProfile:
    """间隔分布参数"""
    distribution: str         # 分布类型：lognormal / exponential
    mu: float = 0.0           # 对数正态分布的 μ
    sigma: float = 1.0        # 对数正态分布的 σ
    lam: float = 1.0          # 指数分布的 λ
    min_sec: float = 1.0      # 最小间隔（秒）
    max_sec: float = 30.0     # 最大间隔（秒）


# 不同操作类型的间隔分布参数
# 参数基于真实用户行为统计分析
INTERVAL_PROFILES: dict[ActionType, IntervalProfile] = {
    ActionType.BROWSE: IntervalProfile(
        distribution="lognormal",
        mu=math.log(2.5),    # 中位数 2.5 秒
        sigma=0.8,           # 较大方差，模拟人类不规律性
        min_sec=1.2,
        max_sec=15.0,
    ),
    ActionType.SEARCH: IntervalProfile(
        distribution="lognormal",
        mu=math.log(4.0),    # 中位数 4.0 秒
        sigma=1.0,           # 更大方差，搜索行为更不规律
        min_sec=2.0,
        max_sec=30.0,
    ),
    ActionType.SCROLL: IntervalProfile(
        distribution="exponential",
        lam=0.5,             # 平均 2 秒（1/λ）
        min_sec=0.8,
        max_sec=8.0,
    ),
    ActionType.DETAIL: IntervalProfile(
        distribution="lognormal",
        mu=math.log(3.0),    # 中位数 3.0 秒
        sigma=0.9,
        min_sec=1.5,
        max_sec=20.0,
    ),
    ActionType.LOGIN: IntervalProfile(
        distribution="lognormal",
        mu=math.log(10.0),   # 登录操作间隔较长
        sigma=1.2,
        min_sec=5.0,
        max_sec=60.0,
    ),
}


class FreqDisguise:
    """频率伪装器

    使用方式：
        disguiser = FreqDisguise()
        interval = disguiser.next_interval(ActionType.SEARCH)
        await asyncio.sleep(interval)
        # 执行搜索...

        if disguiser.should_insert_noise():
            # 插入噪声请求（如访问 /personal）
            ...

    核心原则：
    - 请求间隔呈现对数正态分布（右偏，有长尾）
    - 不同操作类型有不同的间隔特征
    - 偶尔插入噪声请求，打破规律性
    """

    # 噪声请求概率
    NOISE_PROBABILITY = 0.15

    # 历史记录大小（用于统计检测）
    HISTORY_SIZE = 100

    def __init__(self, noise_probability: float = NOISE_PROBABILITY):
        self._noise_probability = noise_probability
        self._history: deque[float] = deque(maxlen=self.HISTORY_SIZE)
        self._last_action_at: float = 0.0
        self._noise_count = 0
        self._total_count = 0

    def next_interval(self, action: ActionType) -> float:
        """生成下一个请求的等待时间（秒）

        按操作类型的分布参数采样，并截断到 [min, max] 范围。
        """
        profile = INTERVAL_PROFILES.get(action, INTERVAL_PROFILES[ActionType.BROWSE])
        interval = self._sample(profile)
        # 截断到合理范围
        interval = max(profile.min_sec, min(profile.max_sec, interval))

        self._history.append(interval)
        self._total_count += 1
        return interval

    def should_insert_noise(self) -> bool:
        """是否应插入噪声请求

        以 noise_probability 的概率返回 True。
        噪声请求让整体请求模式更像真实用户。
        """
        decision = random.random() < self._noise_probability
        if decision:
            self._noise_count += 1
        return decision

    def record_request(self, action: ActionType) -> None:
        """仅记录请求统计（不实际 sleep）

        用于抢单等时间敏感场景：需要累加统计计数器，但不能引入额外延迟。
        采样间隔仍按分布生成并写入 history，保证统计特征准确。
        """
        # 复用 next_interval 的采样+截断+写入 history+累加计数逻辑，避免重复
        self.next_interval(action)

    def get_noise_action(self) -> ActionType:
        """获取噪声请求的操作类型

        噪声请求通常是浏览类操作（访问 /personal、推荐等）
        """
        return ActionType.BROWSE

    def _sample(self, profile: IntervalProfile) -> float:
        """按分布参数采样"""
        if profile.distribution == "lognormal":
            # 对数正态分布：exp(normal(mu, sigma))
            return random.lognormvariate(profile.mu, profile.sigma)
        elif profile.distribution == "exponential":
            # 指数分布：-ln(U) / lambda
            return random.expovariate(profile.lam)
        else:
            # 默认均匀分布
            return random.uniform(profile.min_sec, profile.max_sec)

    # ============== 统计查询 ==============

    def get_stats(self) -> dict[str, Any]:
        """获取频率统计"""
        # noise_ratio 始终基于实际计数计算，不依赖 history 是否为空
        noise_ratio = self._noise_count / max(self._total_count, 1)

        history_list = list(self._history)
        if not history_list:
            return {
                "total_requests": self._total_count,
                "noise_requests": self._noise_count,
                "noise_ratio": round(noise_ratio, 4),
                "mean_interval": 0.0,
                "median_interval": 0.0,
                "std_interval": 0.0,
            }

        mean_val = sum(history_list) / len(history_list)
        sorted_history = sorted(history_list)
        median_val = sorted_history[len(sorted_history) // 2]
        variance = sum((x - mean_val) ** 2 for x in history_list) / len(history_list)
        std_val = math.sqrt(variance)

        return {
            "total_requests": self._total_count,
            "noise_requests": self._noise_count,
            "noise_ratio": round(noise_ratio, 4),
            "mean_interval": round(mean_val, 3),
            "median_interval": round(median_val, 3),
            "std_interval": round(std_val, 3),
            "history_size": len(history_list),
        }

    def reset(self) -> None:
        """重置统计"""
        self._history.clear()
        self._last_action_at = 0.0
        self._noise_count = 0
        self._total_count = 0


# ============== 辅助函数 ==============


def detect_pattern_regularity(intervals: list[float]) -> float:
    """检测请求间隔的规律性

    计算变异系数（CV = std/mean），CV 越小越规律（越像机器人）。
    人类行为 CV 通常 > 0.5，机器人 CV 通常 < 0.1。

    Returns:
        规律性评分 0-1，0 表示完全随机，1 表示完全规律
    """
    if len(intervals) < 2:
        return 0.0

    mean_val = sum(intervals) / len(intervals)
    if mean_val == 0:
        return 1.0

    variance = sum((x - mean_val) ** 2 for x in intervals) / len(intervals)
    std_val = math.sqrt(variance)
    cv = std_val / mean_val

    # CV < 0.1 → 规律性 1.0（机器人特征）
    # CV > 0.5 → 规律性 0.0（人类特征）
    # 线性插值
    if cv <= 0.1:
        return 1.0
    elif cv >= 0.5:
        return 0.0
    else:
        return 1.0 - (cv - 0.1) / 0.4
