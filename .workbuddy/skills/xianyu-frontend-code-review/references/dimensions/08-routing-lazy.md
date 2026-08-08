# 8. 路由与懒加载 🆕v2.0

- 【强制】使用 `react-router-dom` 6.26+ + `BrowserRouter basename="/app"`
- 【强制】约 26 条业务路由（`App.tsx`）
- 【强制】所有业务页面用 `lazy(() => lazyRetry(() => import('./pages/<名>')))` 懒加载
- 【强制】`lazyRetry` 包装 chunk 失败重试：`MAX_RETRIES=3`，1s/2s/4s 指数退避
- 【强制】独立路由（不进 MainLayout）：`/login`、`/onboarding`、`/help`、`/about`
- 【强制】双层 ErrorBoundary：`LazyErrorBoundary`（路由级）+ 顶层 ErrorBoundary
- 【强制】路由切换用 `requestAnimationFrame` 重置滚动位置
