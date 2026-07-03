"""反检测核心（设计文档 §3.3）

四大职责：
1. 行为模拟 - Beta 分布延迟、贝塞尔曲线鼠标轨迹
2. 指纹修复 - navigator.webdriver / languages / plugins / chrome.runtime
3. QPS 限流 - 全局每秒请求 ≤ 1
4. 异常统计 - 提供 WAFGuard 接口
"""
from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from xianyu_hunter.domain.urls import get_base_url
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


# ============== Stealth 脚本 ==============
# 在每个新 BrowserContext 创建时通过 add_init_script 注入
# 修复 Playwright/Chromium 在自动化场景下被识别的特征

STEALTH_SCRIPT = """
// 1. 隐藏 webdriver 标志
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. 修复 languages（真实用户一般至少 2 个语言）
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en-US', 'en']
});

// 3. 修复 plugins（Chromium 自动化下 plugins 长度为 0）
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const arr = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' }
        ];
        arr.length = 3;
        return arr;
    }
});

// 4. 修复 mimeTypes
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => {
        const arr = [
            { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' }
        ];
        arr.length = 1;
        return arr;
    }
});

// 5. 注入 chrome.runtime
window.chrome = {
    runtime: {
        PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
        PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
        RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' },
        OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
        connect: () => {},
        sendMessage: () => {}
    },
    loadTimes: () => ({}),
    csi: () => ({}),
    app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } }
};

// 6. 修复 permissions.query（防止被检测到自动通知被屏蔽）
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);

// 7. 修复 WebGL 渲染器（防止被识别为 SwiftShader）
const getParameterProxy = new Proxy(WebGLRenderingContext.prototype.getParameter, {
    apply(target, thisArg, args) {
        const param = args[0];
        // UNMASKED_VENDOR_WEBGL = 37445
        // UNMASKED_RENDERER_WEBGL = 37446
        if (param === 37445) return 'Intel Inc.';
        if (param === 37446) return 'Intel Iris OpenGL Engine';
        return Reflect.apply(target, thisArg, args);
    }
});
WebGLRenderingContext.prototype.getParameter = getParameterProxy;

// 8. 修复 iframe contentWindow（自动化下行为异常）
const elementDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', { ...elementDescriptor, get: function() { return elementDescriptor.get.apply(this); } });

// 9. 防止自动化被 Notification API 检测
const OriginalNotification = window.Notification;
window.Notification = function(...args) { return new OriginalNotification(...args); };
Object.defineProperty(window.Notification, 'permission', { get: () => 'default' });
Object.defineProperty(window.Notification, 'requestPermission', { value: () => Promise.resolve('default') });
"""


# ============== _m_h5_tk 自动刷新脚本 ==============
# 闲鱼 mtop API 的 _m_h5_tk token TTL=1 小时，过期后搜索返回 RGV587_ERROR。
# 此脚本在页面内每 50 分钟自动 fetch 一次 goofish.com 页面，
# 触发服务端 Set-Cookie 续期，避免手动刷新。

M5TK_AUTO_REFRESH_SCRIPT = """
(function() {
    if (window.__m5tk_refresh) return;
    window.__m5tk_refresh = true;

    async function refreshM5tk() {
        try {
            // 访问任意 goofish 页面即可触发 Set-Cookie 续期
            await fetch('__BASE_URL__/personal', {
                credentials: 'include',
                cache: 'no-store',
            });
            console.log('[m5tk] auto-refreshed at', new Date().toISOString());
        } catch (e) {
            console.warn('[m5tk] auto-refresh failed', e);
        }
    }

    // 每 50 分钟刷新一次（TTL=1h，提前 10 分钟续期）
    setInterval(refreshM5tk, 50 * 60 * 1000);
    // 页面加载后 5 秒首次刷新（缩短延迟，尽快续期避免搜索时 token 已过期）
    setTimeout(refreshM5tk, 5000);
})();
""".replace("__BASE_URL__", get_base_url())


# ============== 增强版 Stealth 脚本（v2） ==============
# 在原 STEALTH_SCRIPT 基础上增加 Canvas / AudioContext / Font 指纹修复，
# 应对 2025-2026 年闲鱼升级的反爬检测。

STEALTH_SCRIPT_V2 = STEALTH_SCRIPT + """
// 10. 修复 Canvas 指纹（只修改少量随机像素，避免全量遍历的性能开销）
(function() {
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {
            // 只修改 3 个随机像素，足以改变 Canvas 指纹哈希
            // 原实现遍历全部像素（1920x1080 = 2M 像素），性能极差
            try {
                const imageData = ctx.getImageData(0, 0, Math.min(this.width, 10), Math.min(this.height, 10));
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] = imageData.data[i] ^ 1;
                }
                ctx.putImageData(imageData, 0, 0);
            } catch(e) {}  // CORS 跨域画布会抛异常，忽略即可
        }
        return origToDataURL.apply(this, args);
    };
})();

// 11. 修复 AudioContext 指纹（只修改少量样本点，避免全量遍历）
(function() {
    const origGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function(...args) {
        const data = origGetChannelData.apply(this, args);
        // 只修改前 10 个样本点（步长 100），足以改变指纹
        // 原实现遍历全部样本，大缓冲区性能差
        const maxModify = Math.min(data.length, 1000);
        for (let i = 0; i < maxModify; i += 100) {
            data[i] = data[i] + 1e-7;
        }
        return data;
    };
})();

// 12. 修复 hardwareConcurrency（headless 下常返回 1 或 2）
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8
});

// 13. 修复 deviceMemory（headless 下常返回 0 或 1）
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8
});

// 14. 修复 connection（headless 下不存在）
if (!navigator.connection) {
    Object.defineProperty(navigator, 'connection', {
        get: () => ({
            effectiveType: '4g',
            rtt: 50,
            downlink: 10,
            saveData: false
        })
    });
}

// 15. 移除 CDP 痕迹（window.cdc_* 变量）
for (const key of Object.keys(window)) {
    if (key.startsWith('cdc_') || key.startsWith('$cdc_')) {
        try { delete window[key]; } catch(e) {}
    }
}

// 16. 修复 iframe detection
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get: function() {
        return window;
    }
});

// 17. 修复 toString 检测（部分反爬通过 Function.toString 检测注入）
const origToString = Function.prototype.toString;
Function.prototype.toString = function() {
    if (this === Function.prototype.toString) return 'function toString() { [native code] }';
    return origToString.call(this);
};
"""


# ============== 行为模拟工具 ==============


def bezier_point(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
    """三阶贝塞尔曲线 B(t)"""
    mt = 1 - t
    return (
        mt * mt * mt * p0
        + 3 * mt * mt * t * p1
        + 3 * mt * t * t * p2
        + t * t * t * p3
    )


def human_delay_seconds(min_ms: int = 200, max_ms: int = 1500) -> float:
    """生成模拟人类思考停顿的延迟（秒）

    使用 Beta 分布而非均匀分布：人类停顿有"长尾"特征，
    大量短停顿 + 偶尔长停顿。Beta(2, 5) 偏向于较短停顿。
    """
    if min_ms >= max_ms:
        return min_ms / 1000.0
    delay = random.betavariate(2, 5) * (max_ms - min_ms) + min_ms
    # 加上高斯抖动，更自然
    delay += random.gauss(0, 30)
    return max(min_ms / 1000.0, delay / 1000.0)


def random_mouse_path(
    from_x: float, from_y: float,
    to_x: float, to_y: float,
    steps: int | None = None,
) -> list[tuple[float, float]]:
    """生成贝塞尔曲线鼠标轨迹点列表

    Returns: 包含 (from, ..., to) 的轨迹点列表
    """
    if steps is None:
        steps = random.randint(15, 30)
    # 控制点偏移制造弧线（非直线）
    cp1 = (from_x + (to_x - from_x) * random.uniform(0.2, 0.4), from_y + (to_y - from_y) * random.uniform(0.1, 0.3))
    cp2 = (from_x + (to_x - from_x) * random.uniform(0.6, 0.8), from_y + (to_y - from_y) * random.uniform(0.7, 0.9))
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = bezier_point(t, from_x, cp1[0], cp2[0], to_x)
        y = bezier_point(t, from_y, cp1[1], cp2[1], to_y)
        points.append((x, y))
    return points


def random_click_offset(target_x: float, target_y: float, max_offset: int = 3) -> tuple[float, float]:
    """点击位置随机偏移（不点正中心）"""
    return (
        target_x + random.uniform(-max_offset, max_offset),
        target_y + random.uniform(-max_offset, max_offset),
    )


# ============== AntiDetect 主类 ==============


@dataclass
class AntiDetectConfig:
    qps: int = 1
    min_delay_ms: int = 200
    max_delay_ms: int = 1500
    fail_pause_threshold: int = 3
    fail_window_sec: int = 3600


class AntiDetect:
    """反检测核心

    使用：
        ad = AntiDetect(config)
        await ad.inject_stealth(context)
        await ad.throttle()           # 全局 QPS 限流
        await ad.human_delay()         # 模拟人类思考
        await ad.natural_click(page, button)
    """

    def __init__(self, config: AntiDetectConfig | None = None):
        self.config = config or AntiDetectConfig()
        self._qps_lock = asyncio.Lock()
        self._last_action_at = 0.0
        self.waf = WAFGuard(
            threshold=self.config.fail_pause_threshold,
            window_sec=self.config.fail_window_sec,
        )

    async def inject_stealth(self, context) -> None:
        """向 BrowserContext 注入 stealth 脚本

        必须在每个新 context 创建后立即调用
        """
        await context.add_init_script(STEALTH_SCRIPT)
        logger.debug("stealth 脚本已注入")

    async def throttle(self) -> None:
        """全局 QPS 限流

        两次 throttle 调用之间至少间隔 1/QPS 秒。
        使用 asyncio.Lock 保证串行。
        """
        async with self._qps_lock:
            now = time.monotonic()
            elapsed = now - self._last_action_at
            interval = 1.0 / self.config.qps
            if elapsed < interval:
                sleep_for = interval - elapsed + random.uniform(0, 0.3)
                await asyncio.sleep(sleep_for)
            self._last_action_at = time.monotonic()

    async def human_delay(self, min_ms: int | None = None, max_ms: int | None = None) -> float:
        """模拟人类思考延迟，返回实际等待秒数"""
        lo = min_ms or self.config.min_delay_ms
        hi = max_ms or self.config.max_delay_ms
        delay = human_delay_seconds(lo, hi)
        await asyncio.sleep(delay)
        return delay

    async def natural_mouse_move(
        self,
        page,
        target_x: float, target_y: float,
    ) -> None:
        """贝塞尔曲线鼠标轨迹移动

        Args:
            page: Playwright Page
            target_x, target_y: 目标坐标
        """
        # 获取当前鼠标位置（默认从 0,0 出发）
        current = await page.evaluate("""() => {
            // 尝试从 window 拿上次位置，否则用 0,0
            if (window._lastMouse) return window._lastMouse;
            return [0, 0];
        }""")
        from_x, from_y = current[0], current[1]

        path = random_mouse_path(from_x, from_y, target_x, target_y)
        for x, y in path:
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.005, 0.020))

        # 记录当前位置供下次使用
        await page.evaluate("(x, y) => { window._lastMouse = [x, y]; }", target_x, target_y)

    async def natural_click(self, page, selector: str) -> None:
        """自然点击元素：先移动鼠标过去，再偏移点击"""
        locator = page.locator(selector).first
        box = await locator.bounding_box()
        if not box:
            raise ValueError(f"元素 {selector} 不可见或没有 bounding box")
        # 目标点 = 元素中心 + 随机偏移
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        tx, ty = random_click_offset(cx, cy, max_offset=3)

        await self.throttle()
        await self.natural_mouse_move(page, tx, ty)
        await self.human_delay(min_ms=50, max_ms=200)
        await page.mouse.click(tx, ty)

    def record_success(self) -> None:
        """记录一次成功（清零风控计数）"""
        self.waf.record_success()

    def record_failure(self) -> bool:
        """记录一次失败，返回是否触发熔断"""
        return self.waf.record_failure()


# ============== WAFGuard ==============


class WAFDecision(str, Enum):
    CONTINUE = "continue"
    PAUSE_ALL = "pause_all"


class WAFGuard:
    """风控熔断器

    在滑动窗口内连续失败 N 次触发 PAUSE_ALL 决策。
    用于避免账号因异常被风控。
    """

    def __init__(self, threshold: int = 3, window_sec: int = 3600):
        self.threshold = threshold
        self.window_sec = window_sec
        self._failures: deque[datetime] = deque()
        self._paused = False

    def record_failure(self) -> WAFDecision:
        """记录一次失败，返回是否需要熔断"""
        now = _utcnow()
        self._failures.append(now)
        self._clean(now)
        if len(self._failures) >= self.threshold:
            self._paused = True
            logger.warning(
                f"风控熔断触发：{len(self._failures)} 次失败 / {self.window_sec}s 窗口"
            )
            return WAFDecision.PAUSE_ALL
        return WAFDecision.CONTINUE

    def record_success(self) -> None:
        """成功时清零计数（保守做法：成功也清零）"""
        self._failures.clear()
        if self._paused:
            logger.info("风控熔断解除")
            self._paused = False

    def is_paused(self) -> bool:
        """当前是否处于熔断状态"""
        return self._paused

    def reset(self) -> None:
        """用户主动重置（如人工处理后）"""
        self._failures.clear()
        self._paused = False

    def _clean(self, now: datetime) -> None:
        """清理窗口外的失败记录"""
        cutoff = now - timedelta(seconds=self.window_sec)
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()

    @property
    def current_failure_count(self) -> int:
        """当前窗口内失败次数"""
        self._clean(_utcnow())
        return len(self._failures)
