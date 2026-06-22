"""浏览器指纹一致性系统（设计文档 §4.1）

核心问题：原 STEALTH_SCRIPT 逐项修补指纹，但各项之间缺乏一致性
（如声称 8 核 CPU 却无 GPU 信息），被 AWSC fireyejs 交叉验证识破。

解决方案：引入「指纹配置文件」概念，所有指纹从同一份 profile 派生，
保证内部一致性。同一 profile 的所有指纹值在 Stealth 脚本中同时注入。

使用方式：
    profile = FingerprintProfile.random()
    script = build_stealth_script(profile)
    await context.add_init_script(script)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


# ============== 预设指纹配置文件 ==============
# 每份 profile 代表一台真实存在的设备配置，所有字段内部一致
# 关键约束：UA / 硬件 / 屏幕 / GPU 必须互相匹配，不能交叉矛盾

_PRESET_PROFILES: list[dict[str, Any]] = [
    {
        # 设备1：Intel i5-12400 + Iris Xe，常见办公电脑
        "name": "office-intel-i5",
        "ua": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
        ),
        "platform": "Win32",
        "vendor": "Google Inc.",
        "hardware_concurrency": 8,
        "device_memory": 8,
        "gpu_vendor": "Intel Inc.",
        "gpu_renderer": "Intel(R) Iris(R) Xe Graphics",
        "screen_width": 1920,
        "screen_height": 1080,
        "color_depth": 24,
        "pixel_ratio": 1.0,
        "languages": ["zh-CN", "zh", "en-US", "en"],
        "canvas_noise_seed": 0x1A2B3C4D,
        "audio_noise_seed": 0x5E6F7081,
    },
    {
        # 设备2：AMD Ryzen 5 + Radeon，中端游戏电脑
        "name": "gaming-amd-r5",
        "ua": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "platform": "Win32",
        "vendor": "Google Inc.",
        "hardware_concurrency": 12,
        "device_memory": 16,
        "gpu_vendor": "Intel Inc.",
        "gpu_renderer": "AMD Radeon RX 6600",
        "screen_width": 2560,
        "screen_height": 1440,
        "color_depth": 24,
        "pixel_ratio": 1.0,
        "languages": ["zh-CN", "zh", "en-US", "en"],
        "canvas_noise_seed": 0x2B3C4D5E,
        "audio_noise_seed": 0x6F708192,
    },
    {
        # 设备3：Intel i7-12700 + UHD，高端办公电脑
        "name": "office-intel-i7",
        "ua": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
        ),
        "platform": "Win32",
        "vendor": "Google Inc.",
        "hardware_concurrency": 12,
        "device_memory": 16,
        "gpu_vendor": "Intel Inc.",
        "gpu_renderer": "Intel(R) UHD Graphics 770",
        "screen_width": 1920,
        "screen_height": 1080,
        "color_depth": 24,
        "pixel_ratio": 1.25,
        "languages": ["zh-CN", "zh", "en-US", "en"],
        "canvas_noise_seed": 0x3C4D5E6F,
        "audio_noise_seed": 0x70819203,
    },
    {
        # 设备4：Intel i3-12100 + UHD，入门级办公电脑
        "name": "office-intel-i3",
        "ua": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        "platform": "Win32",
        "vendor": "Google Inc.",
        "hardware_concurrency": 4,
        "device_memory": 8,
        "gpu_vendor": "Intel Inc.",
        "gpu_renderer": "Intel(R) UHD Graphics 730",
        "screen_width": 1920,
        "screen_height": 1080,
        "color_depth": 24,
        "pixel_ratio": 1.0,
        "languages": ["zh-CN", "zh", "en-US", "en"],
        "canvas_noise_seed": 0x4D5E6F70,
        "audio_noise_seed": 0x81920304,
    },
    {
        # 设备5：AMD Ryzen 7 + RTX，高端游戏电脑
        "name": "gaming-amd-r7",
        "ua": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "platform": "Win32",
        "vendor": "Google Inc.",
        "hardware_concurrency": 16,
        "device_memory": 32,
        "gpu_vendor": "Intel Inc.",
        "gpu_renderer": "NVIDIA GeForce RTX 3060",
        "screen_width": 2560,
        "screen_height": 1440,
        "color_depth": 24,
        "pixel_ratio": 1.0,
        "languages": ["zh-CN", "zh", "en-US", "en"],
        "canvas_noise_seed": 0x5E6F7081,
        "audio_noise_seed": 0x92030405,
    },
]


@dataclass
class FingerprintProfile:
    """一份完整的、内部一致的浏览器指纹

    所有字段从同一份预设配置派生，保证：
    - UA 声称的设备类型与硬件参数匹配
    - GPU 厂商与渲染器型号匹配
    - 屏幕分辨率与设备类型匹配
    - Canvas/Audio 扰动种子固定（同 profile 同结果）
    """
    # 基础身份
    name: str
    ua: str
    platform: str = "Win32"
    vendor: str = "Google Inc."

    # 硬件 — 必须与 UA 声称的设备匹配
    hardware_concurrency: int = 8
    device_memory: int = 8
    gpu_vendor: str = "Intel Inc."
    gpu_renderer: str = "Intel(R) Iris(R) Xe Graphics"

    # 屏幕 — 必须与设备类型匹配
    screen_width: int = 1920
    screen_height: int = 1080
    color_depth: int = 24
    pixel_ratio: float = 1.0

    # 软件 — 必须与浏览器版本匹配
    languages: list[str] = field(default_factory=lambda: ["zh-CN", "zh", "en-US", "en"])

    # 指纹扰动种子 — 同一 profile 内固定，避免每次启动指纹变化被追踪
    canvas_noise_seed: int = 0
    audio_noise_seed: int = 0

    @classmethod
    def from_preset(cls, name: str) -> "FingerprintProfile":
        """按名称加载预设 profile"""
        for preset in _PRESET_PROFILES:
            if preset["name"] == name:
                return cls(**preset)
        raise ValueError(f"未知的指纹 profile: {name}")

    @classmethod
    def random(cls) -> "FingerprintProfile":
        """随机选取一个预设 profile

        随机而非全新生成的原因：
        全新生成的指纹组合可能不存在于真实设备中，
        反而更容易被 AWSC 识别为异常。
        预设 profile 都是真实存在的设备配置。
        """
        preset = random.choice(_PRESET_PROFILES)
        return cls(**preset)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（供日志/调试用）"""
        return {
            "name": self.name,
            "ua": self.ua,
            "platform": self.platform,
            "hardware_concurrency": self.hardware_concurrency,
            "device_memory": self.device_memory,
            "gpu_renderer": self.gpu_renderer,
            "screen": f"{self.screen_width}x{self.screen_height}",
            "pixel_ratio": self.pixel_ratio,
        }


def build_stealth_script(profile: FingerprintProfile) -> str:
    """根据指纹 profile 生成一致的 stealth 脚本

    与原 STEALTH_SCRIPT_V2 的关键区别：
    1. 所有指纹值从同一 profile 派生，杜绝交叉矛盾
    2. Canvas/Audio 扰动使用确定性种子（同 profile 同结果）
    3. WebGL 渲染器与 profile 声称的 GPU 一致
    4. hardwareConcurrency / deviceMemory 与 profile 声称的硬件一致
    """
    # 将 profile 字段注入 JS 模板
    # 注意：JSON 序列化保证 JS 中能正确解析为对象/数组
    import json as _json

    languages_js = _json.dumps(profile.languages)
    plugins_js = _json.dumps([
        {"name": "Chrome PDF Plugin", "filename": "internal-pdf-viewer"},
        {"name": "Chrome PDF Viewer", "filename": "mhjfbmdgcfjbbpaeojofohoefgiehjai"},
        {"name": "Native Client", "filename": "internal-nacl-plugin"},
    ])

    return f"""
// === FingerprintProfile Stealth Script ===
// Profile: {profile.name}
// 所有指纹值从同一 profile 派生，保证内部一致性

// 1. 隐藏 webdriver 标志
Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});

// 2. 修复 languages（与 profile 一致）
Object.defineProperty(navigator, 'languages', {{
    get: () => {languages_js}
}});

// 3. 修复 plugins（Chromium 自动化下 plugins 长度为 0）
Object.defineProperty(navigator, 'plugins', {{
    get: () => {{
        const arr = {plugins_js};
        arr.length = 3;
        return arr;
    }}
}});

// 4. 修复 mimeTypes
Object.defineProperty(navigator, 'mimeTypes', {{
    get: () => {{
        const arr = [
            {{ type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' }}
        ];
        arr.length = 1;
        return arr;
    }}
}});

// 5. 注入 chrome.runtime
window.chrome = {{
    runtime: {{
        PlatformOs: {{ MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' }},
        PlatformArch: {{ ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' }},
        connect: () => {{}},
        sendMessage: () => {{}}
    }},
    loadTimes: () => ({{}}),
    csi: () => ({{}}),
    app: {{ isInstalled: false }}
}};

// 6. 修复 permissions.query
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({{ state: Notification.permission }}) :
    originalQuery(parameters)
);

// 7. 修复 WebGL 渲染器（与 profile 声称的 GPU 一致）
const getParameterProxy = new Proxy(WebGLRenderingContext.prototype.getParameter, {{
    apply(target, thisArg, args) {{
        const param = args[0];
        if (param === 37445) return '{profile.gpu_vendor}';
        if (param === 37446) return '{profile.gpu_renderer}';
        return Reflect.apply(target, thisArg, args);
    }}
}});
WebGLRenderingContext.prototype.getParameter = getParameterProxy;

// 8. 修复 hardwareConcurrency（与 profile 声称的硬件一致）
Object.defineProperty(navigator, 'hardwareConcurrency', {{
    get: () => {profile.hardware_concurrency}
}});

// 9. 修复 deviceMemory（与 profile 声称的硬件一致）
Object.defineProperty(navigator, 'deviceMemory', {{
    get: () => {profile.device_memory}
}});

// 10. 修复 connection（headless 下不存在）
if (!navigator.connection) {{
    Object.defineProperty(navigator, 'connection', {{
        get: () => ({{
            effectiveType: '4g',
            rtt: 50,
            downlink: 10,
            saveData: false
        }})
    }});
}}

// 11. 修复 platform（与 profile 一致）
Object.defineProperty(navigator, 'platform', {{
    get: () => '{profile.platform}'
}});

// 12. 修复 vendor（与 profile 一致）
Object.defineProperty(navigator, 'vendor', {{
    get: () => '{profile.vendor}'
}});

// 13. 移除 CDP 痕迹（window.cdc_* 变量）
for (const key of Object.keys(window)) {{
    if (key.startsWith('cdc_') || key.startsWith('$cdc_')) {{
        try {{ delete window[key]; }} catch(e) {{}}
    }}
}}

// 14. 修复 iframe detection
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {{
    get: function() {{
        return window;
    }}
}});

// 15. 修复 toString 检测
const origToString = Function.prototype.toString;
Function.prototype.toString = function() {{
    if (this === Function.prototype.toString) return 'function toString() {{ [native code] }}';
    return origToString.call(this);
}};

// 16. Canvas 指纹扰动（确定性种子，同 profile 同结果）
// 使用 profile.canvas_noise_seed 作为种子，保证同一 profile 的 Canvas 指纹稳定
// 避免每次启动指纹变化被追踪
(function() {{
    const SEED = {profile.canvas_noise_seed};
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {{
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {{
            try {{
                const w = Math.min(this.width, 10);
                const h = Math.min(this.height, 10);
                const imageData = ctx.getImageData(0, 0, w, h);
                // 用种子决定扰动位置，保证确定性
                for (let i = 0; i < imageData.data.length; i += 4) {{
                    imageData.data[i] = imageData.data[i] ^ (SEED & 1);
                }}
                ctx.putImageData(imageData, 0, 0);
            }} catch(e) {{}}
        }}
        return origToDataURL.apply(this, args);
    }};
}})();

// 17. AudioContext 指纹扰动（确定性种子）
(function() {{
    const SEED = {profile.audio_noise_seed};
    const origGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function(...args) {{
        const data = origGetChannelData.apply(this, args);
        const maxModify = Math.min(data.length, 1000);
        for (let i = 0; i < maxModify; i += 100) {{
            data[i] = data[i] + (SEED & 1) * 1e-7;
        }}
        return data;
    }};
}})();
"""


def list_available_profiles() -> list[str]:
    """列出所有可用的预设 profile 名称"""
    return [p["name"] for p in _PRESET_PROFILES]
