# 响应式适配专项测试

> 对应 meta-rule #67（移动端检测多重 fallback）、#68（响应式断点统一）、#69（设备仿真验证清单）。
> 本文档描述响应式适配问题的排查、修复验证和多设备测试流程。
> 所有参数从 `config.yaml` 读取，**禁止硬编码**。

## 适用场景

- 用户报告设备仿真模式下页面不切换到移动端布局
- 修复 useMobileDetect/useIsMobile Hook 后验证
- 新增/修改 CSS 媒体查询断点后验证
- iPadOS 13+ 设备兼容性验证
- 重新构建部署后的回归测试

## 不适用场景

- 纯后端 API 变更（无 UI 影响）
- 纯 CSS 视觉调整（无 JS 检测逻辑变更）
- 非 SPA 路由跳转相关变更

---

## 步骤 R1：仿真三要素检查

通过 `playwright_evaluate` 检查当前浏览器环境的仿真三要素：

```javascript
JSON.stringify({
  ua: navigator.userAgent,
  maxTouchPoints: navigator.maxTouchPoints,
  innerWidth: window.innerWidth,
  ontouchend: 'ontouchend' in document,
  href: window.location.href
})
```

**判断逻辑**：

| 场景 | UA | maxTouchPoints | innerWidth | ontouchend | 预期跳转 |
|------|----|----|----|----|----|
| 真实 iPhone | 含 iPhone | 5 | 390 | true | → /app/m/ |
| 真实 iPad Pro | 含 Macintosh | 5 | 834 | true | → /app/m/ |
| 仿真 iPhone 13 | 桌面 UA（不变） | 0（不变） | 390 | false | → /app/m/（视口兜底） |
| 仿真 iPad Pro | 桌面 UA（不变） | 0（不变） | 834 | false | → /app/（仿真失败） |
| JS 覆盖 iPad | Macintosh | 5 | 834 | false | → /app/m/（fallback 生效） |
| 桌面 Chrome | Windows | 0 | 1280 | false | → /app/（保持桌面） |

**注意**：Playwright `playwright_resize` 只调整视口尺寸，不修改 UA 和 maxTouchPoints。
这是已知限制（config.yaml `browser_automation.known_limitations`）。

---

## 步骤 R2：JS 属性覆盖验证

当仿真工具无法修改 UA 时，通过 `Object.defineProperty` 覆盖 navigator 属性来模拟真实设备环境。

**脚本模板**（从 `config.yaml#mobile_detect.ua_override_script_template` 读取）：

```javascript
Object.defineProperty(navigator, 'userAgent', {
  value: '{ua}',
  configurable: true
});
Object.defineProperty(navigator, 'maxTouchPoints', {
  value: {maxTouchPoints},
  configurable: true
});
window.dispatchEvent(new Event('resize'));
```

**参数来源**：
- `{ua}`：从 `config.yaml#browser_automation.playwright_mcp.ipados_simulation.ua` 读取
- `{maxTouchPoints}`：从 `config.yaml#browser_automation.playwright_mcp.ipados_simulation.max_touch_points` 读取

**验证步骤**：
1. 执行属性覆盖脚本
2. 等待 React 状态更新（~100ms）
3. 检查 `window.location.pathname` 是否跳转到 `config.yaml#spa.mobile_home_path`
4. 检查移动端布局元素（`.m-layout`、`.m-tabbar`、`#m-content`）是否存在

---

## 步骤 R3：多设备覆盖测试

遍历 `config.yaml#browser_automation.playwright_mcp.device_presets` 中的每个设备预设：

| 设备类别 | 操作 | 预期结果 |
|---------|------|---------|
| narrow_phone | `playwright_resize` + 导航到根路径 | 跳转到 /app/m/ |
| wide_tablet | `playwright_resize` + JS 属性覆盖 + 导航 | 跳转到 /app/m/（验证 fallback） |
| desktop | `playwright_resize` + 导航到 /app/ | 保持 /app/（防误判） |

---

## 步骤 R4：桌面端防误判验证

**必须步骤**（meta-rule #69）：每次修复移动端检测后，验证桌面端不会被误判为移动端。

1. 调用 `playwright_resize` 设置 `desktop_viewport_width` x 720
2. 导航到 `config.yaml#spa.desktop_home_path`
3. 验证 `window.location.pathname` 保持为 `/app/`（不跳转到 /m/）
4. 验证无 `.m-tabbar` 元素（桌面端不应渲染移动端 TabBar）
5. 验证 `#root` innerHTML 长度 > 0（React 应用已挂载）

---

## 步骤 R5：SW 缓存清理

当遇到 PWA SW 缓存旧 JS 导致白屏或 MIME 类型错误时：

1. 检查 console 是否有 `unsupported MIME type` 错误
2. 检查 `#root` innerHTML 是否为空
3. 若命中，执行 SW 缓存清理：
   - 调用 `playwright_evaluate` 执行 `test_execution.sw_cleanup.unregister_script`
   - 重新导航到目标页面（带 `?_t={timestamp}` 绕过 HTTP 缓存）
4. 等待 React 重新渲染（~2s）
5. 验证页面内容正常

---

## 步骤 R6：断点一致性检查

验证 `config.yaml#mobile_detect` 中的三个阈值关系正确：

- `viewport_max_width`（路由跳转阈值）< `ui_responsive_max_width`（UI 响应式阈值）
- `css_media_breakpoint` = `ui_responsive_max_width` + 1
- 阈值差异原因已在 config.yaml 注释中显式声明

若不一致，输出警告并建议修正。
