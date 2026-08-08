# G. 清缓存指导

> 对应决策节点：DT-06（用户浏览器残留旧 SW 缓存）

## 何时需要清缓存

以下场景需要让用户清缓存：
1. 修改了 `registerType` 从 `prompt` 改为 `autoUpdate` 后
2. 修改了 useMobileDetect 逻辑后
3. 修改了 App.tsx 跳转条件后
4. 任何前端代码变更并重新构建后

**为什么需要清缓存**：
- PWA service worker 会缓存旧版本 index.html 和 JS chunks
- 旧 SW 卡在 waiting 状态时，新 SW 无法激活
- 即使改为 `autoUpdate`，旧 SW 仍然需要先被注销一次
- 浏览器缓存（Cache-Control）也可能导致旧版本被加载

## 推荐策略

读取 `config.yaml` 的 `cache_cleanup.primary_strategy`：

**优先推荐：无痕模式**（最彻底，一次性）

无痕模式不会加载任何已注册的 service worker，相当于干净环境。用户在无痕模式下访问一次，确认新版本正常后，再关闭无痕模式，正常访问时新 SW 会自动注册并激活。

## 按浏览器类型的清缓存步骤

读取 `config.yaml` 的 `cache_cleanup.browser_guides`，按用户实际浏览器类型给出步骤。每个浏览器类型在 config 中包含：
- `label`：显示名称
- `steps`：常规清缓存步骤列表
- `incognito_steps`：无痕模式步骤列表

遍历 `browser_guides` 的每个 key（如 `iphone_safari` / `android_chrome` / `desktop_chrome`），按用户实际浏览器匹配 `label`，输出对应的 `steps` 或 `incognito_steps`。

**优先策略**：先推荐 `<cache_cleanup.primary_strategy>`（无痕模式），用户无法使用无痕模式时再给出 `steps`（常规清缓存）。

## 验证清缓存成功

让用户清缓存后再次访问 tunnel URL，确认：
1. 页面能正常加载（不是白屏）
2. 浏览器 console 中出现 `<diagnostic.console_prefix>` 日志（如果加了诊断日志）
3. 诊断浮层能显示（如果带了 `?<diagnostic.query_param_name>=<diagnostic.query_param_value>`）

## 重要提示

- 清缓存后第一次访问可能较慢（重新下载所有静态资源）
- 如果用户清缓存后仍异常，可能是 Cloudflare Tunnel CDN 缓存（默认 tunnel 不缓存 HTML，但需确认）
- 一次清缓存后，`autoUpdate` 模式下后续更新会自动激活，不再需要手动清

## 输出报告

1. 用户使用的浏览器类型
2. 给出的清缓存步骤
3. 用户清缓存后的访问结果
4. 命中的决策节点 ID
