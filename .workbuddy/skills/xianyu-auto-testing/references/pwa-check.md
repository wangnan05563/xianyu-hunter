# D. PWA 配置核查

> 对应决策节点：DT-05（PWA registerType 'prompt' 导致 SW 死锁）

## 检查项

### D1. vite.config.ts 的 PWA 配置

读取 `config.yaml` 的 `key_files.vite_config` 和 `pwa` 段，检查：

1. **registerType**：
   - 期望值：`<recommended_register_type>`（即 `autoUpdate`）
   - 若为 `'prompt'` → **DT-05 命中**

2. **manifest 配置**：
   - `start_url` 应指向 SPA basename（如 `/app/`）
   - `scope` 应与 basename 一致
   - `theme_color` 等品牌色

3. **workbox 配置**：
   - `globPatterns`：预缓存文件类型
   - `navigateFallback`：SPA 路由回退（通常 `index.html`）
   - `navigateFallbackDenylist`：API 路径排除（如 `/^\/api\//`）
   - `runtimeCaching`：运行时缓存策略

### D2. sw.js 预缓存清单

读取 `build_output_dir/<sw_filename>`，检查：

1. **precacheAndRoute 数组长度**：应在 `expected_precache_count_range` 范围内
2. **index.html revision**：每次构建后 revision 哈希应变化
3. **是否引用了已删除的旧 chunk**：旧 SW 缓存旧 index.html，引用已删除的旧 JS chunk 是 SW 死锁的典型症状

**判断**：
- precache 数量 < `expected_precache_count_range.min` → 构建不完整
- precache 数量 > `expected_precache_count_range.max` → 可能有多余文件
- index.html revision 与最新构建不一致 → SW 未更新

### D3. ReloadPrompt 组件

读取 `config.yaml` 的 `key_files.reload_prompt`，检查：

1. **registerSW 调用**：
   ```tsx
   const update = registerSW({
     onNeedRefresh() { setNeedRefresh(true) },
     onOfflineReady() { setOfflineReady(true) },
   })
   ```
2. **通知显示**：使用 antd `App.useApp()` 的 notification
3. **update 函数**：调用 `update(true)` 触发 skipWaiting + 重载

**关键陷阱**：在 `registerType: 'prompt'` 模式下，如果旧 SW 缓存的旧 index.html 引用已删除的旧 JS chunk：
- SPA 启动失败 → React 应用无法 mount
- ReloadPrompt 不会被注册 → 通知显示不出来
- 用户永远点不到"立即刷新" → 旧 SW 永远卡在 waiting → 死锁

## 命中后动作

- DT-05 命中：
  1. 修改 `vite.config.ts` 的 `registerType` 为 `<recommended_register_type>`（`autoUpdate`）
  2. 同步更新 `ReloadPrompt.tsx` 的注释
  3. 重新构建（执行 `build.command`）
  4. 进入 DT-06（清缓存指导）

## 输出报告

1. 当前 registerType 值
2. sw.js precache 数量
3. index.html revision 哈希
4. ReloadPrompt 组件状态
5. 命中的决策节点 ID
