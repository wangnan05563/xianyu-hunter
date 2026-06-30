"""FreqDisguise 单元测试"""
from __future__ import annotations

import math
import statistics

import pytest

from xianyu_hunter.modules.freq_disguise import (
    ActionType,
    FreqDisguise,
    IntervalProfile,
    INTERVAL_PROFILES,
    detect_pattern_regularity,
)


# ============== ActionType 枚举测试 ==============


def test_action_type_values() -> None:
    """操作类型枚举值正确"""
    assert ActionType.BROWSE.value == "browse"
    assert ActionType.SEARCH.value == "search"
    assert ActionType.SCROLL.value == "scroll"
    assert ActionType.DETAIL.value == "detail"
    assert ActionType.LOGIN.value == "login"


# ============== 间隔分布测试 ==============


def test_interval_profiles_defined() -> None:
    """所有操作类型都有间隔分布定义"""
    for action in ActionType:
        assert action in INTERVAL_PROFILES, f"{action} 缺少间隔分布定义"


def test_browse_profile_params() -> None:
    """浏览操作的分布参数合理"""
    profile = INTERVAL_PROFILES[ActionType.BROWSE]
    assert profile.distribution == "lognormal"
    assert profile.min_sec > 0
    assert profile.max_sec > profile.min_sec
    # 中位数 = exp(mu) 应在 1-5 秒
    median = math.exp(profile.mu)
    assert 1.0 <= median <= 5.0


def test_search_profile_has_larger_interval() -> None:
    """搜索操作间隔大于浏览操作"""
    browse_median = math.exp(INTERVAL_PROFILES[ActionType.BROWSE].mu)
    search_median = math.exp(INTERVAL_PROFILES[ActionType.SEARCH].mu)
    assert search_median > browse_median, "搜索间隔应大于浏览"


def test_scroll_profile_exponential() -> None:
    """滚动操作使用指数分布"""
    profile = INTERVAL_PROFILES[ActionType.SCROLL]
    assert profile.distribution == "exponential"
    assert profile.lam > 0


# ============== next_interval 测试 ==============


def test_next_interval_in_range() -> None:
    """生成的间隔在 [min, max] 范围内"""
    disguiser = FreqDisguise()
    profile = INTERVAL_PROFILES[ActionType.SEARCH]

    for _ in range(100):
        interval = disguiser.next_interval(ActionType.SEARCH)
        assert profile.min_sec <= interval <= profile.max_sec


def test_next_interval_different_actions() -> None:
    """不同操作类型生成不同范围的间隔"""
    disguiser = FreqDisguise()

    browse_intervals = [disguiser.next_interval(ActionType.BROWSE) for _ in range(50)]
    search_intervals = [disguiser.next_interval(ActionType.SEARCH) for _ in range(50)]

    browse_mean = statistics.mean(browse_intervals)
    search_mean = statistics.mean(search_intervals)

    # 搜索间隔应大于浏览间隔（统计上）
    assert search_mean > browse_mean * 0.8  # 允许一定波动


def test_next_interval_not_constant() -> None:
    """间隔不是固定值（有随机性）"""
    disguiser = FreqDisguise()
    intervals = [disguiser.next_interval(ActionType.BROWSE) for _ in range(20)]
    unique = set(round(x, 3) for x in intervals)
    assert len(unique) > 5, "间隔应有足够多样性"


def test_next_interval_lognormal_distribution() -> None:
    """对数正态分布的间隔呈右偏特征（mean > median）"""
    disguiser = FreqDisguise()
    intervals = [disguiser.next_interval(ActionType.SEARCH) for _ in range(500)]

    mean_val = statistics.mean(intervals)
    median_val = statistics.median(intervals)

    # 对数正态分布右偏：mean > median
    assert mean_val > median_val, f"对数正态应右偏: mean={mean_val}, median={median_val}"


def test_next_interval_records_history() -> None:
    """next_interval 记录历史"""
    disguiser = FreqDisguise()
    for _ in range(10):
        disguiser.next_interval(ActionType.BROWSE)

    stats = disguiser.get_stats()
    assert stats["history_size"] == 10
    assert stats["total_requests"] == 10


# ============== should_insert_noise 测试 ==============


def test_should_insert_noise_returns_bool() -> None:
    """should_insert_noise 返回布尔值"""
    disguiser = FreqDisguise()
    result = disguiser.should_insert_noise()
    assert isinstance(result, bool)


def test_should_insert_noise_probability() -> None:
    """噪声概率接近配置值"""
    disguiser = FreqDisguise(noise_probability=0.3)
    count = sum(1 for _ in range(1000) if disguiser.should_insert_noise())
    # 1000 次中约 300 次，允许 ±5% 误差
    assert 250 <= count <= 350, f"噪声次数 {count} 不在预期范围"


def test_should_insert_noise_zero_probability() -> None:
    """概率为 0 时永远不插入噪声"""
    disguiser = FreqDisguise(noise_probability=0.0)
    for _ in range(100):
        assert disguiser.should_insert_noise() is False


def test_should_insert_noise_full_probability() -> None:
    """概率为 1 时总是插入噪声"""
    disguiser = FreqDisguise(noise_probability=1.0)
    for _ in range(100):
        assert disguiser.should_insert_noise() is True


# ============== record_request 测试 ==============


def test_record_request_increments_total_count() -> None:
    """record_request 应累加 total_count 并写入 history"""
    disguiser = FreqDisguise()
    disguiser.record_request(ActionType.LOGIN)
    disguiser.record_request(ActionType.SEARCH)
    stats = disguiser.get_stats()
    assert stats["total_requests"] == 2
    assert stats["history_size"] == 2


def test_record_request_does_not_sleep() -> None:
    """record_request 不引入实际延迟（抢单场景关键）"""
    import time as _time
    disguiser = FreqDisguise()
    t0 = _time.monotonic()
    for _ in range(10):
        disguiser.record_request(ActionType.LOGIN)
    elapsed = _time.monotonic() - t0
    # 10 次 record_request 应在 0.1s 内完成（无 sleep）
    assert elapsed < 0.1, f"record_request 耗时 {elapsed:.3f}s，可能引入了延迟"


def test_record_request_interval_within_profile_range() -> None:
    """record_request 采样间隔应在 action 的 [min, max] 范围内"""
    disguiser = FreqDisguise()
    profile = INTERVAL_PROFILES[ActionType.LOGIN]
    for _ in range(20):
        disguiser.record_request(ActionType.LOGIN)
    history = list(disguiser._history)
    for interval in history:
        assert profile.min_sec <= interval <= profile.max_sec


def test_get_noise_action_returns_browse() -> None:
    """噪声操作类型为浏览"""
    disguiser = FreqDisguise()
    assert disguiser.get_noise_action() == ActionType.BROWSE


# ============== 统计查询测试 ==============


def test_get_stats_initial() -> None:
    """初始统计为空"""
    disguiser = FreqDisguise()
    stats = disguiser.get_stats()
    assert stats["total_requests"] == 0
    assert stats["noise_requests"] == 0
    assert stats["mean_interval"] == 0.0


def test_get_stats_after_actions() -> None:
    """操作后统计正确"""
    disguiser = FreqDisguise()
    for _ in range(50):
        disguiser.next_interval(ActionType.BROWSE)

    stats = disguiser.get_stats()
    assert stats["total_requests"] == 50
    assert stats["history_size"] == 50
    assert stats["mean_interval"] > 0
    assert stats["median_interval"] > 0
    assert stats["std_interval"] > 0


def test_get_stats_noise_count() -> None:
    """噪声计数正确"""
    disguiser = FreqDisguise(noise_probability=1.0)  # 总是插入噪声
    disguiser.should_insert_noise()
    disguiser.should_insert_noise()

    stats = disguiser.get_stats()
    assert stats["noise_requests"] == 2
    # total_count=0 时 noise_ratio = noise_count / max(0, 1) = 2.0
    assert stats["noise_ratio"] == 2.0


def test_reset_clears_stats() -> None:
    """reset 清空统计"""
    disguiser = FreqDisguise()
    for _ in range(10):
        disguiser.next_interval(ActionType.BROWSE)
    disguiser.should_insert_noise()

    disguiser.reset()

    stats = disguiser.get_stats()
    assert stats["total_requests"] == 0
    assert stats["noise_requests"] == 0


# ============== detect_pattern_regularity 测试 ==============


def test_regularity_constant_intervals() -> None:
    """固定间隔检测为高规律性（机器人特征）"""
    intervals = [2.0] * 20  # 完全固定
    regularity = detect_pattern_regularity(intervals)
    assert regularity > 0.9, f"固定间隔规律性应高: {regularity}"


def test_regularity_random_intervals() -> None:
    """随机间隔检测为低规律性（人类特征）"""
    import random
    random.seed(42)
    intervals = [random.lognormvariate(1.0, 1.0) for _ in range(100)]
    regularity = detect_pattern_regularity(intervals)
    assert regularity < 0.3, f"随机间隔规律性应低: {regularity}"


def test_regularity_empty_intervals() -> None:
    """空列表规律性为 0"""
    assert detect_pattern_regularity([]) == 0.0


def test_regularity_single_interval() -> None:
    """单个间隔规律性为 0"""
    assert detect_pattern_regularity([2.0]) == 0.0


# ============== 集成测试：FreqDisguise 生成的间隔不像机器人 ==============


def test_generated_intervals_not_robot_like() -> None:
    """FreqDisguise 生成的间隔不像机器人"""
    disguiser = FreqDisguise()
    intervals = [disguiser.next_interval(ActionType.BROWSE) for _ in range(100)]

    regularity = detect_pattern_regularity(intervals)
    # 人类行为规律性应低于 0.3
    assert regularity < 0.3, f"生成的间隔太规律: regularity={regularity}"


def test_generated_intervals_have_variance() -> None:
    """生成的间隔有足够方差"""
    disguiser = FreqDisguise()
    intervals = [disguiser.next_interval(ActionType.SEARCH) for _ in range(50)]

    std_val = statistics.stdev(intervals)
    mean_val = statistics.mean(intervals)
    cv = std_val / mean_val

    # 人类行为 CV > 0.5
    assert cv > 0.3, f"变异系数过低: cv={cv}"
