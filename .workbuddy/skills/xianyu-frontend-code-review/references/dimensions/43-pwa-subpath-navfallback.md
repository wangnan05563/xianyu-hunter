# 维度 43：PWA 子路径导航回退绝对化 🆕v4.71.0 · F-REVIEW-237

> **编码规范引用**：xianyu-hunter-dev `references/coding-standards.md` §3.16.2 / meta-rule #117
> **配置节点**：config.yaml#checklist.pwa_subpath_navfallback + config.yaml#pwa_subpath_navfallback
> **测试关联**：xianyu-auto-testing 模式 AL（子路径部署一致性）/ 模式 U（SPA 白屏）

## 触发条件
- `frontend/vite.config.ts` 中 PWA 配置（`navigateFallback` / `cleanupOutdatedCaches` / `registerType`）的新增或修改
- 项目以非根路径部署（`base` 非 `/`，如 `/xianyu/`）时的任何 PWA 改动
- `frontend/index.html` 的 `#root` 加载占位的新增或修改

## 检查规则

### 强制（P0 阻塞）
- 当 `base` 非 `/` 时，`navigateFallback` 必须是**绝对路径** `base + 'index.html'`（config.yaml#pwa_subpath_navfallback.expected_navigate_fallback，如 `/xianyu/index.html`），**禁止**相对路径 `'index.html'`。
- workbox 必须 `cleanupOutdatedCaches: true`（config.yaml#pwa_subpath_navfallback.require_cleanup_outdated_caches=true）。

### 推荐（P1 严重）
- `index.html` 的 `#root` 内必须有加载占位（选择器见 config.yaml#pwa_subpath_navfallback.loading_splash_selector，如 `#xh-loading-splash`），JS 挂载后替换，避免纯白白屏。
- `registerType` 应为 `autoUpdate`（prompt 模式在旧 SW 缓存旧 chunk 时会永久卡白屏）。

### 推荐（P2 改进）
- 构建产物 `sw.js` 的 `createHandlerBoundToURL` 必须指向绝对路径；验证时用正则子串上下文提取，勿依赖精确引号比对（易误判）。

## Grep 扫描命令
```bash
# 检测 navigateFallback 是否为相对路径
grep -n "navigateFallback" frontend/vite.config.ts

# 检测是否开启 cleanupOutdatedCaches
grep -n "cleanupOutdatedCaches" frontend/vite.config.ts

# 检测 index.html 加载占位
grep -n "xh-loading-splash\|loading-splash" frontend/index.html

# 检测 base 是否非根
grep -n "base:" frontend/vite.config.ts
```

## 判断标准
- `base` 非 `/` 且 `navigateFallback` 为 `'index.html'` 或相对路径 → P0 阻塞
- `cleanupOutdatedCaches` 缺失 → P0 阻塞
- `index.html` 无加载占位 → P1 严重
- `registerType` 为 `prompt` 且无更新提示机制 → P1 严重

## 适用场景
- 以非根路径（`base` 非 `/`）部署的 PWA
- Service Worker 含 `navigateFallback` 的 SPA
- 含子路由（如 `/xianyu/m/`）的 SPA

## 不适用场景
- 根路径部署（`base: '/'`）且反向代理 strip 模式：可跳过绝对化，但 `cleanupOutdatedCaches` 仍建议开启
- 非 PWA（无 Service Worker）
- SSR / 多页应用（SW 机制不同）
- 第三方库内部 PWA 配置（不在本仓库源码控制范围）
