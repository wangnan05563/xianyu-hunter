"""FingerprintProfile 单元测试"""
from __future__ import annotations

import json
import re

import pytest

from xianyu_hunter.modules.fingerprint import (
    FingerprintProfile,
    build_stealth_script,
    list_available_profiles,
)


# ============== Profile 加载测试 ==============


def test_list_available_profiles_not_empty() -> None:
    """预设 profile 列表非空"""
    profiles = list_available_profiles()
    assert len(profiles) >= 3, "至少应有 3 个预设 profile"


def test_from_preset_valid_name() -> None:
    """按名称加载预设 profile"""
    names = list_available_profiles()
    profile = FingerprintProfile.from_preset(names[0])
    assert profile.name == names[0]


def test_from_preset_invalid_name_raises() -> None:
    """未知名称抛出 ValueError"""
    with pytest.raises(ValueError, match="未知的指纹 profile"):
        FingerprintProfile.from_preset("non-existent-profile")


def test_random_returns_valid_profile() -> None:
    """random() 返回有效的 profile"""
    profile = FingerprintProfile.random()
    assert profile.name in list_available_profiles()
    assert profile.ua
    assert profile.hardware_concurrency > 0
    assert profile.device_memory > 0


def test_random_distribution_covers_all() -> None:
    """多次 random() 应覆盖所有预设 profile（验证随机性）"""
    seen = set()
    for _ in range(100):
        seen.add(FingerprintProfile.random().name)
    assert seen == set(list_available_profiles()), "100 次随机应覆盖所有 profile"


# ============== 一致性校验测试 ==============


def test_profile_internal_consistency() -> None:
    """每个预设 profile 内部字段一致"""
    for name in list_available_profiles():
        profile = FingerprintProfile.from_preset(name)

        # UA 与平台一致
        if "Win64; x64" in profile.ua:
            assert profile.platform == "Win32", f"{name}: Win64 UA 应对应 Win32 platform"

        # 硬件参数合理
        assert profile.hardware_concurrency in (4, 6, 8, 12, 16, 20, 24), \
            f"{name}: hardware_concurrency={profile.hardware_concurrency} 不合理"
        assert profile.device_memory in (4, 8, 16, 32), \
            f"{name}: device_memory={profile.device_memory} 不合理"

        # 屏幕分辨率合理
        assert profile.screen_width >= 1366, f"{name}: 屏幕宽度过小"
        assert profile.screen_height >= 768, f"{name}: 屏幕高度过小"
        assert profile.color_depth == 24, f"{name}: color_depth 应为 24"

        # GPU 厂商与渲染器匹配
        if "Intel" in profile.gpu_renderer:
            assert profile.gpu_vendor == "Intel Inc.", \
                f"{name}: Intel GPU 应对应 Intel Inc. vendor"

        # 语言列表非空
        assert len(profile.languages) >= 2, f"{name}: languages 至少 2 个"
        assert "zh-CN" in profile.languages, f"{name}: 应包含 zh-CN"

        # 扰动种子非零（避免无扰动）
        assert profile.canvas_noise_seed != 0, f"{name}: canvas_noise_seed 不应为 0"
        assert profile.audio_noise_seed != 0, f"{name}: audio_noise_seed 不应为 0"


def test_profiles_are_distinct() -> None:
    """不同 profile 的关键字段应不同（保证多样性）"""
    profiles = [FingerprintProfile.from_preset(n) for n in list_available_profiles()]
    uas = {p.ua for p in profiles}
    renderers = {p.gpu_renderer for p in profiles}
    # 至少有 2 种不同的 UA 和 2 种不同的 GPU 渲染器
    assert len(uas) >= 2, "预设 profile 的 UA 应有多样性"
    assert len(renderers) >= 2, "预设 profile 的 GPU 渲染器应有多样性"


# ============== Stealth 脚本生成测试 ==============


def test_build_stealth_script_contains_profile_values() -> None:
    """生成的脚本包含 profile 的指纹值"""
    profile = FingerprintProfile.from_preset("office-intel-i5")
    script = build_stealth_script(profile)

    # UA 出现在注释中
    assert profile.name in script
    # GPU 渲染器出现在脚本中
    assert profile.gpu_renderer in script
    # 硬件参数出现在脚本中
    assert str(profile.hardware_concurrency) in script
    assert str(profile.device_memory) in script
    # 扰动种子出现在脚本中
    assert str(profile.canvas_noise_seed) in script
    assert str(profile.audio_noise_seed) in script


def test_build_stealth_script_contains_key_fixes() -> None:
    """脚本包含关键的反检测修复"""
    profile = FingerprintProfile.random()
    script = build_stealth_script(profile)

    assert "navigator, 'webdriver'" in script
    assert "navigator, 'languages'" in script
    assert "navigator, 'plugins'" in script
    assert "window.chrome" in script
    assert "WebGLRenderingContext" in script
    assert "hardwareConcurrency" in script
    assert "deviceMemory" in script
    # 不应残留 Python f-string 的 {profile.xxx} 占位符
    assert "{profile." not in script


def test_build_stealth_script_brackets_balanced() -> None:
    """脚本括号配对（基本语法检查）"""
    profile = FingerprintProfile.random()
    script = build_stealth_script(profile)

    assert script.count("(") == script.count(")"), "圆括号不配对"
    assert script.count("{") == script.count("}"), "花括号不配对"
    assert script.count("[") == script.count("]"), "方括号不配对"


def test_build_stealth_script_no_template_leaks() -> None:
    """脚本中不应残留未替换的模板占位符"""
    profile = FingerprintProfile.random()
    script = build_stealth_script(profile)

    # 不应有 Python f-string 的 {xxx} 残留（已替换为值）
    # 但 JS 对象语法本身有 {}，所以检查特定的未替换模式
    assert "{profile." not in script, "脚本中残留未替换的 profile 占位符"


def test_different_profiles_produce_different_scripts() -> None:
    """不同 profile 生成不同的脚本"""
    names = list_available_profiles()
    if len(names) < 2:
        pytest.skip("需要至少 2 个 profile")

    scripts = set()
    for name in names:
        profile = FingerprintProfile.from_preset(name)
        script = build_stealth_script(profile)
        scripts.add(script)

    assert len(scripts) == len(names), "不同 profile 应生成不同脚本"


def test_to_dict_contains_key_fields() -> None:
    """to_dict 包含关键字段"""
    profile = FingerprintProfile.random()
    d = profile.to_dict()

    assert "name" in d
    assert "ua" in d
    assert "hardware_concurrency" in d
    assert "device_memory" in d
    assert "gpu_renderer" in d
    assert "screen" in d
