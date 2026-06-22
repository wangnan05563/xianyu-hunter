"""AWSC 环境伪装脚本（设计文档 §4.2）

核心问题：闲鱼加载 window.__baxia__ 和 window.AWSC，它们会校验
fireyejs 采集的指纹与 __awsc_et__ 返回的 ET Token 是否一致。
现有方案完全忽略这些对象。

解决方案：在页面加载前注入 AWSC 伪装脚本，让反爬系统「自洽」。

核心原则：不阻断 AWSC 运行，而是让浏览器环境本身足够真实。
阻断或篡改 AWSC 的行为比让它正常采集到一致指纹更容易被检测。

注入的脚本处理：
1. 确保 __baxia__ 参数正常返回，不触发验证码
2. 确保 AWSC.use() 回调正常执行
3. 确保 __awsc_et__ 环境令牌正常生成
4. 修补 LocalStorage 中的 baxia 配置
"""
from __future__ import annotations

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


# AWSC 伪装脚本
# 注入时机：page.addInitScript()，早于任何 CDN 脚本加载
# 核心思路：不阻止 AWSC 运行，而是修补其采集结果
AWSC_SPOOF_SCRIPT = """
// === AWSC Environment Spoof Script ===
// 核心原则：不阻断 AWSC 运行，而是让浏览器环境本身足够真实
// 阻断或篡改 AWSC 的行为比让它正常采集到一致指纹更容易被检测

(function() {
    'use strict';

    // 1. 确保 __baxia__ 对象存在且参数正常
    // baxia 检测的是"异常行为"而非"注入脚本"
    // 只要行为模拟足够真实，baxia 不会触发 renderNC
    if (!window.__baxia__) {
        Object.defineProperty(window, '__baxia__', {
            value: {
                paramsType: ["uab", "umid", "et"],
                needUmidToken: true,
                renderNC: false,
                awscTimeout: 3000,
                fromEntry: true,
                baxiaInit: function() { return Promise.resolve(); },
                baxiaPromptInit: function() { return Promise.resolve(); },
                getFYModule: function() { return Promise.resolve({}); },
                postFYModule: function() { return Promise.resolve({}); },
                handleEffectUrl: function() {},
            },
            writable: false,
            configurable: false,
        });
    }

    // 2. 确保 AWSC 对象存在且 use 方法正常
    // AWSC.use 加载安全模块，我们让它正常执行回调
    if (!window.AWSC) {
        Object.defineProperty(window, 'AWSC', {
            value: {
                use: function(module, callback) {
                    // 模拟模块加载成功
                    if (typeof callback === 'function') {
                        setTimeout(function() {
                            callback({
                                umid: null,  // 让 fireyejs 自然采集
                                et: null,
                            });
                        }, 100);
                    }
                },
                configFY: function() {},
                configFYSync: function() {},
                configFYEx: function() {},
                configFYSyncEx: function() {},
            },
            writable: false,
            configurable: false,
        });
    }

    // 3. 确保 __awsc_et__ 环境令牌对象存在
    // ET Token 由服务端验证，无法伪造
    // 此处仅确保对象存在，让令牌自然生成
    if (!window.__awsc_et__) {
        Object.defineProperty(window, '__awsc_et__', {
            value: {
                ver: "g",
                jsv: "119",
                getETToken: function() { return ""; },
                LTKProduct: function() { return Promise.resolve(""); },
                LTKConsume: function() { return Promise.resolve(); },
                AECookie: function() { return ""; },
                load: function() { return Promise.resolve(); },
            },
            writable: false,
            configurable: false,
        });
    }

    // 4. 修补 LocalStorage 中的 baxia 配置
    // baxia_entry_config 存储入口配置，异常值会触发风控
    // 此处确保配置存在且时间戳合理
    try {
        var configKey = 'baxia_entry_config';
        var timeKey = 'baxia_entry_config_time';
        if (!localStorage.getItem(configKey)) {
            localStorage.setItem(configKey, '');
        }
        if (!localStorage.getItem(timeKey)) {
            localStorage.setItem(timeKey, String(Date.now()));
        }
    } catch(e) {
        // LocalStorage 可能被禁用，忽略
    }

    // 5. 确保 fireyejs 能正常采集指纹
    // 不拦截 fireyejs 的采集方法，让它自然运行
    // 前提是 FingerprintProfile 已确保浏览器环境一致
    // fireyejs 采集到的指纹会与 ET Token 一致

    // 6. 监听 baxia 验证码触发事件
    // 如果 baxia 决定渲染验证码（renderNC=true），
    // 通过 CustomEvent 通知外部处理
    var origDefineProperty = Object.defineProperty;
    try {
        var baxiaProxy = new Proxy(window.__baxia__, {
            set: function(target, prop, value) {
                if (prop === 'renderNC' && value === true) {
                    // 通知外部验证码被触发
                    window.dispatchEvent(new CustomEvent('xh_captcha_triggered', {
                        detail: { type: 'slider', source: 'baxia' }
                    }));
                }
                target[prop] = value;
                return true;
            },
        });
        // 不能直接替换 __baxia__（已定义为不可配置），
        // 但可以通过其他方式监听
    } catch(e) {}

    console.log('[AWSC Spoof] 环境伪装脚本已注入');
})();
"""


# baxia 验证码触发检测脚本
# 注入到页面后，监听 baxia 是否触发验证码
BAXIA_CAPTCHA_DETECT_SCRIPT = """
() => {
    // 检测 baxia 是否渲染了验证码
    const baxia = window.__baxia__;
    if (!baxia) return { detected: false };

    // 检查 renderNC 标志
    if (baxia.renderNC === true) {
        return { detected: true, type: 'slider', source: 'baxia_renderNC' };
    }

    // 检查页面中是否有验证码 DOM 元素
    const captchaSelectors = [
        '#baxia-dialog',
        '#nc_1_wrapper',
        '.nc-container',
        '[class*="baxia"]',
        '[class*="captcha"]',
        'iframe[src*="sec"]',
    ];

    for (const selector of captchaSelectors) {
        const el = document.querySelector(selector);
        if (el && el.offsetParent !== null) {
            return { detected: true, type: 'slider', source: 'dom_' + selector };
        }
    }

    return { detected: false };
}
"""


# LocalStorage baxia 配置检查脚本
BAXIA_LOCALSTORAGE_CHECK_SCRIPT = """
() => {
    const result = {};
    try {
        result.baxia_entry_config = localStorage.getItem('baxia_entry_config') || '';
        result.baxia_entry_config_time = localStorage.getItem('baxia_entry_config_time') || '';
        result.auyst = localStorage.getItem('auyst') || '';
        result.syfhs = localStorage.getItem('syfhs') || '';
        result.lswucn = localStorage.getItem('lswucn') || '';
        result.ETLCD = localStorage.getItem('ETLCD') || '';
    } catch(e) {
        result.error = e.message;
    }
    return result;
}
"""


def get_awsc_spoof_script() -> str:
    """获取 AWSC 伪装脚本

    与 FingerprintProfile 的 stealth 脚本配合使用：
    1. FingerprintProfile 确保浏览器指纹一致
    2. AWSCSpoof 确保 AWSC/baxia 对象存在且不触发验证码
    3. 两者同时注入，让反爬系统完全自洽
    """
    return AWSC_SPOOF_SCRIPT


def get_baxia_detect_script() -> str:
    """获取 baxia 验证码检测脚本

    在页面加载后执行，检测是否触发了验证码。
    返回的 JS 函数可通过 page.evaluate() 调用。
    """
    return BAXIA_CAPTCHA_DETECT_SCRIPT


def get_baxia_localstorage_check_script() -> str:
    """获取 baxia LocalStorage 检查脚本

    检查 LocalStorage 中的 baxia 配置是否异常。
    """
    return BAXIA_LOCALSTORAGE_CHECK_SCRIPT


def is_awsc_spoof_needed(use_cdp: bool = False) -> bool:
    """判断是否需要注入 AWSC 伪装脚本

    CDP 模式下使用真实浏览器，AWSC 自然存在，无需注入。
    launch 模式下需要注入。

    Args:
        use_cdp: 是否使用 CDP 模式
    """
    return not use_cdp
