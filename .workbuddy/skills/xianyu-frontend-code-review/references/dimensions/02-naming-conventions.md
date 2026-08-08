# 2. 命名规范

- 【强制】组件文件：PascalCase（如 `MainLayout.tsx`、`ErrorBoundary.tsx`）
- 【强制】API 模块文件：camelCase（如 `task.ts`、`about.ts`）
- 【强制】Hook 文件：`use<X>.ts`（如 `useAutoRefresh.ts`、`useSheetSync.ts`）
- 【强制】Store 文件：`<名>Store.ts`（如 `sheetStore.ts`、`configStore.ts`）
- 【强制】常量文件：按业务域分文件（`frontend/src/constants/`）
- 【强制】CSS 文件：camelCase + `.css` 后缀，与组件同目录（如 `chatbot.css`、`about.css`）
- 【强制】测试文件：`__tests__/<Component>.test.tsx`，与组件同级
- 【强制】常量：UPPER_SNAKE_CASE（如 `SSE_LAST_EVENT_ID_KEY`、`MIN_INTERVAL`、`MAX_RETRIES`）
