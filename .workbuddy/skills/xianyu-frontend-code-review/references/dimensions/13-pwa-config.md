# 13. PWA 配置 🆕v2.0

- 【强制】`vite.config.ts` 配置 `base: '/app/'`
- 【强制】构建产物输出到 `../src/xianyu_hunter/web/static/spa`
- 【强制】`VitePWA` `registerType: 'prompt'`
- 【强制】`manifest.theme_color: '#FF6200'`
- 【强制】`workbox.maximumFileSizeToCacheOnBytes: 4MB`
- 【强制】`runtimeCaching` 排除以下路径（不缓存）：
  - `/api/events/stream`
  - `/api/auth/`
  - `/api/export/`
- 【强制】`devOptions.enabled: false`
