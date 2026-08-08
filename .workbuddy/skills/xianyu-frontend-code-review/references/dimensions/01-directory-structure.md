# 1. 目录结构 🆕v2.0

- 【强制】所有代码在 `frontend/src/` 下开发
- 【强制】业务页面位于 `frontend/src/pages/<业务名>/`（如 `Dashboard/`、`Tasks/`、`Items/`、`Orders/`、`Evaluations/`、`Chatbot/`、`Config/`、`Logs/`、`Timeline/`、`Maintenance/`、`About/`、`Onboarding/`、`Login/`）
- 【强制】公共组件位于 `frontend/src/components/`（如 `SheetWorkspace/`、`layout/`、`charts/`、`editors/`、`icons/`、`ErrorBoundary.tsx`）
- 【强制】API 模块位于 `frontend/src/api/`，新增 API 归入子模块而非扩展 `index.ts`
- 【强制】自定义 Hook 位于 `frontend/src/hooks/`
- 【强制】状态管理位于 `frontend/src/stores/`
- 【强制】常量位于 `frontend/src/constants/`
- 【强制】类型定义位于 `frontend/src/api/types.ts`（统一出口）
- 【强制】工具函数位于 `frontend/src/utils/`
