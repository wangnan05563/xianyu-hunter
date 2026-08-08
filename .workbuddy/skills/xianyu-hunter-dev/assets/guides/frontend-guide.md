# 前端开发指南

> 本文档整合了闲鱼猎人前端开发规范与代码模板，是 React + TypeScript + AntD + Zustand 个性化前端开发的完整参考。

## 目录导航

- [一、开发规范](#一开发规范)
  - [1. 概述](#1-概述)
  - [2. 环境要求](#2-环境要求)
  - [3. 命名约定](#3-命名约定)
  - [4. 目录结构与文件组织](#4-目录结构与文件组织)
  - [5. TypeScript 严格规范](#5-typescript-严格规范)
  - [6. React 18 组件规范](#6-react-18-组件规范)
  - [7. AntD 5 主题规范](#7-antd-5-主题规范)
  - [8. Hooks 设计模式](#8-hooks-设计模式)
  - [9. Zustand 状态管理](#9-zustand-状态管理)
  - [10. API 调用规范](#10-api-调用规范)
  - [11. 路由与懒加载](#11-路由与懒加载)
  - [12. SheetWorkspace 多页签系统](#12-sheetworkspace-多页签系统)
  - [13. PWA 配置](#13-pwa-配置)
  - [14. SonarQube 规则遵守](#14-sonarqube-规则遵守)
  - [15. 性能优化](#15-性能优化)
  - [16. 测试规范](#16-测试规范)
- [二、代码模板](#二代码模板)
  - [模板1：API 模块](#模板1api-模块)
  - [模板2：自定义 Hook](#模板2自定义-hook)
  - [模板3：Zustand Store](#模板3zustand-store)

---

## 一、开发规范

## 1. 概述

### 1.1 文档目的

本文档规范闲鱼猎人前端开发流程，确保代码质量、可维护性与 SonarQube 合规。

### 1.2 适用范围

- 闲鱼猎人前端所有功能开发（`frontend/src/`）
- 组件开发、Hook 提取、Store 设计、API 接入
- 路由注册、菜单维护、Sheet 映射

### 1.3 核心原则

- **配置驱动**：所有参数通过 config 文件管理，无硬编码
- **单一职责**：组件/Hook/Store 各司其职，避免胖组件
- **模块级函数提取**：嵌套层级 ≤ 4，超限提取模块级函数（S2004）
- **类型严格**：`strict: true`，禁用 `any`（除非泛型边界场景）
- **错误兜底**：`LazyErrorBoundary` + `Suspense` 双层容错
- **解释"为什么"**：注释说明设计权衡与历史教训，而非复述代码

### 1.4 技术栈

- **React** 18.3.1（Concurrent Mode）
- **TypeScript** 5.5（strict: true）
- **Ant Design** 5.21（ConfigProvider 主题化）
- **Zustand** 4.5（轻量状态管理）
- **react-router-dom** 6.26（SPA 路由）
- **axios** 1.7（HTTP 客户端）
- **echarts** 5.5（数据可视化，按需导入）
- **@dnd-kit** 6.1（拖拽排序）
- **Vite** 5.4（构建工具）
- **vite-plugin-pwa** 1.3（PWA 离线访问）
- **Vitest** 4.1（单元测试）

---

## 2. 环境要求

### 2.1 开发工具

| 工具 | 版本 | 说明 |
|---|---|---|
| Node.js | >=18（Docker 20-alpine，开发环境 24） | 使用 nvm 管理多版本 |
| VS Code | 最新 | 推荐 TypeScript Vue Plugin / ESLint |
| Chrome | 90+ | PWA Service Worker 支持 |

### 2.2 VS Code 推荐插件

1. **ESLint**：TypeScript/React 代码检查
2. **Prettier**：CSS/Less/JS 格式化
3. **EditorConfig**：固定尾部换行符 LF

### 2.3 启动命令

```bash
cd frontend
npm install          # 安装依赖
npm run dev          # 开发模式（HMR，端口 5173）
npm run build        # 生产构建（tsc -b && vite build）
npm run lint         # ESLint 检查
npx tsc -b           # 类型检查（构建前强制）
npx vitest run       # 单元测试
```

---

## 3. 命名约定

### 3.1 文件命名

| 类型 | 规范 | 示例 |
|---|---|---|
| 组件文件 | PascalCase | `MainLayout.tsx`、`SheetTabs.tsx` |
| Hook 文件 | camelCase + use 前缀 | `useAutoLiveSearch.ts`、`useSheetSync.ts` |
| Store 文件 | camelCase + Store 后缀 | `sheetStore.ts`、`configStore.ts` |
| API 模块 | camelCase | `task.ts`、`chatbot.ts` |
| 类型定义 | camelCase | `types.ts` |
| 常量文件 | camelCase 或 kebab-case | `eventTypes.ts`、`statusColors.ts` |
| 测试文件 | `<被测名>.test.tsx` | `SheetWorkspace.test.tsx`、`useAutoLiveSearch.test.ts` |
| 样式文件 | camelCase + .css | `chatbot.css`、`about.css` |

### 3.2 标识符命名

| 类型 | 规范 | 示例 |
|---|---|---|
| 组件 | PascalCase | `SheetWorkspace`、`ErrorBoundary` |
| Hook | use + PascalCase | `useAutoLiveSearch`、`usePersistentState` |
| Store hook | use + PascalCase + Store | `useSheetStore`、`useConfigStore` |
| 函数/方法 | camelCase | `openSheet`、`handleTabClick` |
| 常量 | UPPER_SNAKE_CASE | `PERSIST_DEBOUNCE_MS`、`MAX_RETRIES`、`REPLACED_HISTORY_MAX` |
| 类型 | PascalCase | `SheetItem`、`SheetPreferences`、`TaskCreateBody` |
| Props 类型 | PascalCase + Props 后缀 | `StreamRefs`、`SendErrorDeps` |
| 枚举值 | PascalCase | `'active' \| 'paused' \| 'stopped'`（字符串字面量联合） |

### 3.3 模块导出规范

- **API 模块**：导出 `<域>Api` 对象，禁止默认导出
  ```ts
  export const taskApi = { list: () => client.get('/tasks'), ... }
  ```
- **Hook**：导出同名 hook 函数
  ```ts
  export function useAutoLiveSearch(opts: Options) { ... }
  ```
- **Store**：导出 `use<Feature>Store` hook
  ```ts
  export const useSheetStore = create<SheetState>()(persist(...))
  ```

---

## 4. 目录结构与文件组织

### 4.1 前端目录结构

```
frontend/src/
├── api/                      # API 层
│   ├── client.ts             # axios 单例 + 拦截器
│   ├── index.ts              # re-export 各业务域
│   ├── types.ts              # 共享类型定义
│   ├── task.ts               # 任务 API
│   ├── chatbot.ts            # 客服 API
│   └── ...                   # 约 18 个业务域
├── components/               # 公共组件
│   ├── SheetWorkspace/       # 多页签工作台（6 文件）
│   ├── TidalForagers/        # IP 形象背景
│   ├── charts/               # 图表组件
│   ├── editors/              # 编辑器组件
│   ├── icons/                # 图标库
│   ├── layout/               # 布局组件
│   ├── ErrorBoundary.tsx
│   ├── ExportButton.tsx
│   ├── LazyImage.tsx
│   └── ReloadPrompt.tsx
├── constants/                # 常量（按业务域分文件）
│   ├── eventTypes.ts
│   ├── statusColors.ts
│   ├── orderStatus.ts
│   ├── riskLevels.ts
│   └── logLevels.ts
├── contexts/                 # React Context
│   └── ThemeContext.tsx
├── hooks/                    # 自定义 Hook
│   ├── useAutoLiveSearch.ts
│   ├── useAutoRefresh.ts
│   ├── useColumnConfig.ts
│   ├── useIsMobile.ts
│   ├── usePersistentState.ts
│   ├── useSearch.ts
│   ├── useSearchHistory.ts
│   └── useSheetSync.ts
├── pages/                    # 页面（按业务域分组）
│   ├── About/
│   ├── Chatbot/
│   ├── Config/
│   ├── Dashboard/
│   ├── Evaluations/
│   ├── Items/
│   ├── Login/
│   ├── Logs/
│   ├── Maintenance/
│   ├── Onboarding/
│   ├── Orders/
│   ├── Tasks/
│   └── Timeline/
├── stores/                   # Zustand Store
│   ├── configStore.ts
│   └── sheetStore.ts
├── utils/                    # 工具函数
│   ├── apiError.ts
│   ├── lazyRetry.tsx
│   └── storage.ts
├── App.tsx                   # 路由声明
├── main.tsx                  # 应用入口
├── test-setup.ts             # 测试 setup
└── vite-env.d.ts
```

### 4.2 页面目录组织

每个页面目录遵循：
```
pages/<域>/
├── index.tsx                 # 主页面
├── <域>.css                  # 页面样式（如有）
├── i18n.ts                   # 国际化（如有）
├── api.ts                    # 页面专用 API（如有，通用 API 在 src/api/）
├── types.ts                  # 页面专用类型（如有，通用类型在 src/api/types.ts）
├── utils.ts                  # 页面专用工具
├── components/               # 页面专用组件
└── __tests__/                # 单元测试
    └── <Component>.test.tsx
```

---

## 5. TypeScript 严格规范

### 5.1 tsconfig.json 关键配置

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2021", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,                          // 启用所有严格检查
    "noFallthroughCasesInSwitch": true,      // switch 必须有 break/return
    "isolatedModules": true,                  // 隔离模块（Vite 兼容）
    "moduleDetection": "force",
    "useDefineForClassFields": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "allowImportingTsExtensions": true,
    "jsx": "react-jsx",                       // React 18 自动 runtime
    "noEmit": true,                           // 仅类型检查，构建交 Vite
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }             // 路径别名
  },
  "include": ["src"],
  "exclude": ["src/**/__tests__/**", "src/**/*.test.*", "src/**/*.spec.*"]
}
```

### 5.2 类型定义规范

- **优先 `type` 而非 `interface`**（除非需要 declaration merging）
  ```ts
  // 推荐
  type SheetItem = { id: string; path: string; ... }
  // 不推荐
  interface SheetItem { id: string; path: string; ... }
  ```
- **复杂 Props 拆分为子类型组合**
  ```ts
  type StreamRefs = { ... }
  type StreamSetters = { ... }
  type StreamContext = StreamRefs & StreamSetters
  ```
- **工厂函数依赖参数用 `Deps` 后缀**
  ```ts
  type SendErrorDeps = { publish: (e: Error) => void; logger: Logger }
  function createSendError(deps: SendErrorDeps) { ... }
  ```
- **使用字符串字面量联合而非 enum**（便于序列化）
  ```ts
  type TaskStatus = 'running' | 'paused' | 'stopped' | 'error' | 'deleted'
  ```

### 5.3 类型断言限制

- **禁止不必要类型断言**（S4325）
  ```ts
  // 错误：val 已经是 string
  const val: string = 'foo' as string
  // 正确
  const val = 'foo'
  ```
- **必要时使用 `as unknown as T`** 并附注释说明原因
  ```ts
  // ChromaDB 返回类型与官方声明不一致，需要强制断言
  const result = response.data as unknown as ChromaDBResult
  ```

---

## 6. React 18 组件规范

### 6.1 函数式组件

- **统一使用函数式组件**（SFC），禁用 class 组件
- **SFC 内禁用 `this`**（S6757），需要状态用 Hook
- **组件声明用 `function` 关键字**，便于堆栈追踪
  ```tsx
  // 推荐
  function SheetTabs(props: SheetTabsProps) { ... }
  // 不推荐
  const SheetTabs = (props: SheetTabsProps) => { ... }
  ```

### 6.2 Props 类型设计

- **Props 类型用 `type` 关键字**，定义在组件文件内（除非复用）
  ```tsx
  type SheetTabsProps = {
    sheets: SheetItem[]
    activeSheetId: string | null
    onSelect: (id: string) => void
    onClose: (id: string) => void
  }
  ```
- **回调函数用 `on` 前缀**
  ```tsx
  type Props = { onSelect: (id: string) => void; onClose: (id: string) => void }
  ```
- **可选 props 用 `?` 标记，不要用 `| undefined`**
  ```tsx
  type Props = { title?: string }  // 不要 { title: string | undefined }
  ```

### 6.3 useEffect 依赖管理

- **ref 持有最新闭包避免 `setInterval` 陷阱**
  ```tsx
  const latestCallbackRef = useRef(callback)
  useEffect(() => { latestCallbackRef.current = callback }, [callback])
  useEffect(() => {
    const id = setInterval(() => latestCallbackRef.current(), 1000)
    return () => clearInterval(id)
  }, [])
  ```
- **对象依赖用 `JSON.stringify` 稳定化**（EChart 主题）
  ```tsx
  useEffect(() => { ... }, [JSON.stringify(theme), JSON.stringify(opts)])
  ```
- **`scheduleNextRef` 打破循环依赖**（useAutoRefresh）
- **组件卸载递增 `requestId` 让所有未完成回调失效**（useSearch）

### 6.4 错误边界

- **`LazyErrorBoundary` 包裹 `Suspense`**：Suspense 只能捕获异步 fallback，无法捕获同步 chunk 错误
  ```tsx
  function LazyRoute({ children }: { children: React.ReactNode }) {
    return (
      <LazyErrorBoundary>
        <Suspense fallback={<PageLoading />}>{children}</Suspense>
      </LazyErrorBoundary>
    )
  }
  ```
- **`ErrorBoundary` 的 `resetKeys` 变化自动重置**
  ```tsx
  <ErrorBoundary resetKeys={[path]}>
    <SheetContent path={path} />
  </ErrorBoundary>
  ```

### 6.5 事件处理

- **可点击元素必须配键盘事件**（S6848）
  ```tsx
  // 错误：div + onClick 不可键盘访问
  <div onClick={handleClick}>...</div>
  // 正确：工厂函数配键盘事件
  function clickableProps(onClick: () => void) {
    return {
      onClick,
      onKeyDown: (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick() }
      },
      tabIndex: 0,
      role: 'button',
    }
  }
  <div {...clickableProps(handleClick)}>...</div>
  ```

---

## 7. AntD 5 主题规范

### 7.1 ConfigProvider 配置

**关键设计**：`ConfigProvider` 必须放在 `BrowserRouter` 外层（`main.tsx`），让独立路由（如 `/login`）也能感知主题切换。

```tsx
// main.tsx 关键片段
<ConfigProvider
  theme={{
    algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: '#FF6200',          // 品牌橙
      borderRadius: 8,
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', ...",
    },
    components: {
      Table: {
        // darkAlgorithm 不会重算显式 token，需要动态覆盖
        // 否则亮色 rowHoverBg '#fff7f0' 与暗色文字对比度过低
        rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : '#fff7f0',
      },
    },
  }}
>
  <BrowserRouter basename="/app">
    <App />
  </BrowserRouter>
</ConfigProvider>
```

### 7.2 踩坑记录

- **顶层 ConfigProvider 缺 `algorithm`** → Login 页永远浅色
- **`darkAlgorithm` 不会重算已显式设置的 token** → `rowHoverBg` 需手动随主题切换
- **`message` v5 不支持 `btn` 字段** → 用 `notification` 承载撤销按钮
- **`App.useApp()` 获取主题化实例** → 在 ConfigProvider 内部消费 `theme.useToken()`

### 7.3 颜色规范

| 用途 | 颜色 |
|---|---|
| 品牌主色 | `#FF6200`（橙） |
| Table rowHoverBg（亮色） | `#fff7f0` |
| Table rowHoverBg（暗色） | `rgba(255, 98, 0, 0.08)` |
| BotAvatar 眼睛 | `#6ECDB4`（青） |
| BotAvatar 腮红 | `#FFB3CC`（粉） |
| 空状态背景圆 | `#FFD6E8`（粉）/ `#C8F1E2`（青） |

### 7.4 CSS 变量

- `--xh-bg-layout`：布局背景
- `--xh-bg-code`：代码块背景

---

## 8. Hooks 设计模式

### 8.1 现有 Hooks 清单

| Hook | 文件 | 用途 |
|---|---|---|
| `useAutoLiveSearch` | `hooks/useAutoLiveSearch.ts` | 任务列表自动实时搜索（SSE 串行队列） |
| `useAutoRefresh` | `hooks/useAutoRefresh.ts` | 触发式实时刷新（SSE 事件驱动 + 定时兜底） |
| `useColumnConfig` | `hooks/useColumnConfig.ts` | 表格列配置（order + hidden 双状态） |
| `useIsMobile` | `hooks/useIsMobile.ts` | 移动端断点检测（matchMedia + 767px） |
| `usePersistentState` | `hooks/usePersistentState.ts` | 持久化 useState（防抖 300ms + validator） |
| `useSearch` | `hooks/useSearch.ts` | 统一搜索（防抖 400ms + requestId 竞态保护） |
| `useSearchHistory` | `hooks/useSearchHistory.ts` | 搜索历史（namespace 隔离 + 容量 20） |
| `useSheetSync` | `hooks/useSheetSync.ts` | URL ↔ sheet 栈双向同步 |

### 8.2 Hook 设计要点

- **常量提取到模块级**：避免组件内多层闭包嵌套（S2004）
  ```ts
  // 模块级
  const MAX_RETRIES = 3
  const RETRY_BASE_MS = 1000
  function decrementRemainMap(map: Record<string, number>, id: string) { ... }
  
  // Hook 内
  function useAutoRefresh() {
    const [state, setState] = useState(...)
    // 调用模块级函数
    decrementRemainMap(remainMap, id)
  }
  ```
- **ref 持有最新闭包**：避免 `setInterval` 陷阱
- **页面不可见降频**：`visibilitychange` 监听，`BACKGROUND_SLOWDOWN × 3`
- **防抖/节流**：`DEBOUNCE_MS = 300`（持久化）、`400ms`（搜索）、`500ms`（刷新）
- **竞态保护**：`cancelled` 标记（CronEditor）、`requestId` 丢弃过时响应（useSearch）

### 8.3 useAutoLiveSearch 关键修复

**问题**：`pauseAll` 清空 `searchingIds` 导致已发起 SSE 中断、悬挂请求。

**修复**：`pauseAll` 不清空 `searchingIds`，已发起的 SSE 不中断，完成后自然移除。

```ts
// 错误：pauseAll 清空 searchingIds
const pauseAll = () => { setSearchingIds(new Set()) }
// 正确：pauseAll 只停止 tick，不清空 searchingIds
const pauseAll = () => { 
  shouldPauseRef.current = true
  // searchingIds 不动，已发起的 SSE 完成后自然移除
}
```

### 8.4 SSE 断线重连三要素与 visibilitychange 标准模板 🆕

**问题背景**：SSE 连接在页面切换到后台后断开，恢复可见时不自动重建；断线重连不传递 `last_event_id`，导致断线期间事件丢失；error 事件无限重连浪费资源。

**强制规则**：使用 `EventSource` 的组件必须实现三个要素：

| 要素 | 作用 | 实现方式 |
|------|------|----------|
| 1. lastEventId 记录 | 断线重连时启用回放 | `app_event` 回调中 `e.lastEventId` 保存到变量 |
| 2. 重连传递 last_event_id | 后端回放断线期间事件 | URL 拼接 `?last_event_id=${lastEventId}` |
| 3. visibilitychange 监听 | 页面恢复可见时重建连接 | `document.addEventListener('visibilitychange', ...)` |

**重连次数限制**：必须有 `MAX_RECONNECT` 上限（通过配置管理，默认 10），超限后放弃 SSE 退化为轮询。

**标准模板**：

```typescript
useEffect(() => {
  if (!enabled || !taskId) return

  const MAX_RECONNECT = 10  // 通过配置管理
  let reconnectAttempts = 0
  let lastEventId = 0

  const connect = () => {
    if (sseRef.current) sseRef.current.close()
    if (document.visibilityState !== 'visible') return
    if (reconnectAttempts >= MAX_RECONNECT) return

    // 要素 2：传递 last_event_id 启用回放
    const url = lastEventId > 0
      ? `/api/events/stream?last_event_id=${lastEventId}`
      : '/api/events/stream'
    const es = new EventSource(url)
    sseRef.current = es

    // 要素 1：记录 lastEventId
    es.addEventListener('app_event', (e: MessageEvent) => {
      lastEventId = parseInt(e.lastEventId) || lastEventId
      // ... 事件处理 ...
    })

    es.addEventListener('error', () => {
      try { es.close() } catch { /* */ }
      sseRef.current = null
      reconnectAttempts++
      if (reconnectAttempts < MAX_RECONNECT && document.visibilityState === 'visible') {
        setTimeout(connect, 3000)
      }
    })
  }

  // 要素 3：页面恢复可见时重建连接
  const onVisibilityChange = () => {
    if (document.visibilityState === 'visible' && !sseRef.current) {
      reconnectAttempts = 0
      connect()
    }
  }
  document.addEventListener('visibilitychange', onVisibilityChange)

  connect()
  return () => {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    if (sseRef.current) {
      sseRef.current.close()
      sseRef.current = null
    }
  }
}, [enabled, taskId])
```

**常见陷阱**：
- `lastEventId` 是 `MessageEvent` 的属性（`e.lastEventId`），不是 `EventSource` 的属性
- 页面不可见时 `selectedTask` 变化会触发 useEffect 重执行，`connect()` 检测不可见直接 return，恢复可见后无机制重建 → 必须有 visibilitychange 监听
- 浏览器原生 EventSource 自动重连会携带 `Last-Event-ID` header，但手动 `close() + new EventSource()` 不会 → 必须显式传递

**适用场景**：所有使用 `EventSource` 的前端组件
**不适用场景**：使用 `fetch + ReadableStream` 手动实现 SSE 的场景（已有 `AbortController` 管理）

---

## 9. Zustand 状态管理

### 9.1 设计原则

- **store 是纯逻辑层**：不感知路由库，`navigate` 由组件注入
  ```ts
  // sheetStore.ts
  let _navigator: ((path: string) => void) | null = null
  export function setNavigator(n: (path: string) => void) { _navigator = n }
  
  // SheetWorkspace.tsx 注入
  const navigate = useNavigate()
  useEffect(() => setNavigator(navigate), [navigate])
  ```
- **双状态支持 diff 预览**（configStore）
  ```ts
  interface ConfigState {
    original: AppConfig   // 原始配置
    config: AppConfig     // 当前编辑配置
    previewSave: () => Promise<DiffPreview>  // dry_run
    confirmSave: () => Promise<void>        // 实际保存
    revertField: (path: string) => void      // 字段级回滚
  }
  ```
- **持久化只存必要字段**：过滤 `icon/title/element` 等 ReactNode
  ```ts
  persist(
    (set, get) => ({ ... }),
    {
      name: 'xh-sheets',
      partialize: (s) => ({ 
        sheets: s.sheets.map(({ id, path, minimized, openedAt }) => 
          ({ id, path, minimized, openedAt }))
      }),
      debounce: 300,  // PERSIST_DEBOUNCE_MS
    }
  )
  ```

### 9.2 sheetStore 四分支 openSheet

```ts
const openSheet = (path: string) => {
  // 1. 已存在则激活
  if (existing) return activateExistingSheet(existing)
  // 2. 循环替换（达 maxSheets 时替换最旧）
  if (circularReplaceEnabled && sheets.length >= maxSheets) return performCircularReplace(path)
  // 3. 移动端替换激活 sheet
  if (isMobile && activeSheet) return replaceMobileActiveSheet(path)
  // 4. 新建 sheet
  return createNewSheet(path)
}
```

### 9.3 回收栈设计

- `replacedHistory` 最多 5 条（FIFO，`REPLACED_HISTORY_MAX = 5`）
- `restoreReplaced` 不检查 `maxSheets`（用户主动撤销应始终成功，可能临时超限，下次 `openSheet` 再平衡）
- `replacedSheet` 独立于 `SheetItem`（不携带 ReactNode，序列化轻便）
- `replacedHistory` 不持久化恢复（`replacedAt` 时间戳过期，恢复无意义）

---

## 10. API 调用规范

### 10.1 axios 单例（client.ts）

```ts
const client = axios.create({
  baseURL: '/api',
  withCredentials: true,   // 携带 cookie，与项目硬约束一致
  timeout: 30000,
})

// 请求拦截：附加 Bearer Token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('xh.token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截：401 防抖跳转
let isRedirecting = false   // 防止并发 401 触发多次跳转白屏
client.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401 && !isRedirecting) {
      isRedirecting = true
      const redirect = encodeURIComponent(globalThis.location.pathname)
      globalThis.location.replace(`/app/login?redirect=${redirect}`)
    }
    return Promise.reject(error)
  },
)
```

### 10.2 业务 API 组织

- **按业务域 re-export**：新增 API 归入子模块而非扩展 `index.ts`
  ```ts
  // api/index.ts
  export * from './task'
  export * from './chatbot'
  export * from './auth'
  // ...约 18 个业务域
  ```
- **API 模块导出 `<域>Api` 对象**
  ```ts
  // api/task.ts
  export const taskApi = {
    list: () => client.get('/tasks').then(r => r.data),
    create: (body: TaskCreateBody) => client.post('/tasks', body).then(r => r.data),
    live: (keyword: string) => fetch('/api/tasks/live', { ... }),  // SSE 用 fetch
  }
  ```

### 10.3 SSE 流式 API

- **使用 `fetch + ReadableStream`**（不支持 axios）
- **错误按 axios 兼容格式抛出**：让上层 `apiError` 解析逻辑可以无差别处理
  ```ts
  throw Object.assign(new Error(message), {
    response: { status, data: { detail } }
  })
  ```
- **lastEventId 持久化重连**：localStorage 存储 → 重连时作为 `?last_event_id=` 参数

### 10.4 错误处理（utils/apiError.ts）

```ts
export function extractApiError(err: unknown): string {
  // 1. FastAPI 校验错误：{ detail: { message, errors } }
  // 2. 401 Unauthorized：跳登录
  // 3. 500 Internal Server Error：显示通用错误
  // 4. 网络错误：显示"网络异常"
}
```

---

## 11. 路由与懒加载

### 11.1 路由声明（App.tsx）

```tsx
import { lazyRetry } from '@/utils/lazyRetry'

// 路由懒加载 + chunk 失败重试（MAX_RETRIES=3）
const Dashboard = lazyRetry(() => import('./pages/Dashboard'))
const Tasks = lazyRetry(() => import('./pages/Tasks'))
// ...

function LazyRoute({ children }: { children: React.ReactNode }) {
  return (
    <LazyErrorBoundary>
      <Suspense fallback={<PageLoading />}>{children}</Suspense>
    </LazyErrorBoundary>
  )
}

function App() {
  return (
    <Routes>
      {/* 独立路由（不进 MainLayout） */}
      <Route path="/login" element={<LazyRoute><Login /></LazyRoute>} />
      <Route path="/onboarding" element={<LazyRoute><Onboarding /></LazyRoute>} />
      <Route path="/help" element={<LazyRoute><Help /></LazyRoute>} />
      <Route path="/about" element={<LazyRoute><About /></LazyRoute>} />
      {/* 嵌套路由（MainLayout 内） */}
      <Route element={<MainLayout />}>
        <Route path="/" element={<LazyRoute><Dashboard /></LazyRoute>} />
        <Route path="/tasks" element={<LazyRoute><Tasks /></LazyRoute>} />
        {/* ...约 26 条业务路由 */}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
```

### 11.2 lazyRetry 设计

- **MAX_RETRIES = 3**：chunk 加载失败自动重试 3 次
- **重试间隔**：1s / 2s / 4s 指数退避
- **失败后抛错**：被 `LazyErrorBoundary` 捕获显示重试按钮

### 11.3 三处映射维护

新增页面必须同步维护：
1. `App.tsx`：路由声明
2. `MainLayout.tsx`：菜单项 `menuItems`
3. `sheetRegistry.tsx`：path → component + title + icon 映射

---

## 12. SheetWorkspace 多页签系统

### 12.1 文件组织

```
components/SheetWorkspace/
├── index.tsx                  # 容器组件，注入 navigate 到 store
├── SheetTabs.tsx              # 标签栏（ThumbnailTab/StandardTab）
├── SheetContent.tsx           # 内容渲染区（双层 ErrorBoundary）
├── sheetRegistry.tsx          # path → component + title + icon 映射
├── SheetPreferences.tsx       # 偏好设置 Drawer
├── sheetNotifications.tsx     # 循环替换触发时发 Notification + 5s 撤销
└── sheet.css
```

### 12.2 SheetPreferences 字段

| 字段 | 类型 | 范围 | 默认值 |
|---|---|---|---|
| `maxSheets` | number | [1, 10] | 5 |
| `enableAnimation` | boolean | - | true |
| `minimizeInsteadOfClose` | boolean | - | false |
| `doubleClickCloseEnabled` | boolean | - | true |
| `doubleClickInterval` | number | [200, 800] | 350 |
| `thumbnailMode` | boolean | - | false |
| `thumbnailTooltipEnabled` | boolean | - | true |
| `circularReplaceEnabled` | boolean | - | true |

### 12.3 关键设计

- **store 是纯逻辑层不感知路由库**，`_navigator` 由 `SheetWorkspace` 通过 `useNavigate` 注入
- **用 `notification` 而非 `message`**：v5 `message` 不支持 `btn` 字段，无法承载"撤销"按钮
- **缩略图模式激活态显示微型关闭按钮**：双击关闭禁用时原本无关闭途径，可用性阻塞
- **两层 ErrorBoundary**：外层 `resetKeys=[path]`（路径变化重置），内层 `LazyErrorBoundary`（捕获 chunk 错误）

---

## 13. PWA 配置

### 13.1 vite.config.ts PWA 关键配置

```ts
VitePWA({
  registerType: 'prompt',  // 提示用户刷新，避免静默刷新打断操作
  manifest: {
    name: '闲鱼猎人 XianyuHunter',
    theme_color: '#FF6200',
    background_color: '#FFFFFF',
    display: 'standalone',
    lang: 'zh-CN',
    start_url: '/app/',
    scope: '/app/',
  },
  workbox: {
    maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,  // 4MB，容纳 echarts/antd 大 chunk
    navigateFallback: 'index.html',
    navigateFallbackDenylist: [/^\/api\//],
    runtimeCaching: [
      {
        // 静态图片 CacheFirst，30 天，100 条
        urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
        handler: 'CacheFirst',
        options: { cacheName: 'xh-images', expiration: { maxEntries: 100, maxAgeSeconds: 30 * 24 * 3600 } },
      },
      {
        // API GET NetworkFirst，5 秒超时，5 分钟，200 条
        urlPattern: /^https?:\/\/[^/]+\/api\/.*$/,
        handler: 'NetworkFirst',
        options: {
          cacheName: 'xh-api',
          networkTimeoutSeconds: 5,
          expiration: { maxEntries: 200, maxAgeSeconds: 5 * 60 },
          // 关键排除：SSE、鉴权、流式响应
          denylist: [/\/api\/events\/stream/, /\/api\/auth\//, /\/api\/export\//],
        },
      },
    ],
  },
  devOptions: { enabled: false },  // 开发模式不启用 SW
})
```

### 13.2 ReloadPrompt 组件

- `App.useApp()` 获取主题化 notification
- `import('virtual:pwa-register')` 动态导入（开发模式静默失败）
- 更新通知 `duration: 0` 不自动关闭

---

## 14. SonarQube 规则遵守

### 14.1 必须遵守的规则

| 规则 | 说明 | 解决方案 |
|---|---|---|
| **S2004** | 嵌套层级 ≤ 4 | 提取模块级函数（典型：setState updater） |
| **S3358** | 嵌套三元拆为变量 | 拆为 `const a = cond ? x : y` 再用 |
| **S6757** | SFC 内不用 `this` | 工厂函数替代 class（TidalForagers `createFish`） |
| **S7784** | 使用 `structuredClone` | 替代 `JSON.parse(JSON.stringify())` |
| **S6848** | 可点击元素配键盘事件 | `clickableProps` 工厂函数 |
| **S1128** | 删除未使用 import | 定期清理 |
| **S4325** | 移除不必要类型断言 | 让 TS 推断 |
| **S3776** | 认知复杂度 | 拆 case 为模块级 handler |

### 14.2 S2004 修复示例

```tsx
// 错误：嵌套超过 4 层
function Chatbot({ sessionId }: Props) {
  const [messages, setMessages] = useState([])
  useEffect(() => {
    sse.on('message', (msg) => {
      if (msg.type === 'recalled') {
        setMessages(prev => prev.map(m => {
          if (m.id === msg.id) {
            return { ...m, isRecalled: true }  // 嵌套 5 层
          }
          return m
        })
      }
    })
  }, [])
}

// 正确：提取模块级 updater
function createRecalledMessageUpdater(msgId: string) {
  return (prev: Message[]) => prev.map(m => m.id === msgId ? { ...m, isRecalled: true } : m)
}

function Chatbot({ sessionId }: Props) {
  const [messages, setMessages] = useState([])
  useEffect(() => {
    sse.on('message', (msg) => {
      if (msg.type === 'recalled') {
        setMessages(createRecalledMessageUpdater(msg.id))  // 嵌套 2 层
      }
    })
  }, [])
}
```

### 14.3 S6848 clickableProps 工厂函数

```tsx
function clickableProps(onClick: () => void) {
  return {
    onClick,
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        onClick()
      }
    },
    tabIndex: 0,
    role: 'button',
  }
}

// 使用
<div {...clickableProps(() => handleOpen(id))}>...</div>
```

---

## 15. 性能优化

### 15.1 路由懒加载 + chunk 重试

- `lazyRetry`：MAX_RETRIES=3，1s/2s/4s 指数退避
- `LazyErrorBoundary` + `Suspense` 双层容错

### 15.2 ECharts 按需导入

```ts
// 按需导入，bundle 从 ~1000kB 降至 ~300kB
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart, ... } from 'echarts/charts'
import { TitleComponent, TooltipComponent, ... } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, LineChart, PieChart, TitleComponent, ..., CanvasRenderer])
```

### 15.3 TidalForagers 空间分区

- Boids 群体智能 + Perlin 噪声流场（220 条鱼 + 6 个光点）
- **空间分区网格优化**（gridSize=80）：邻居查找从 O(n²) 降至 O(n)
- **工厂函数替代 class**（S6757）：SFC 内不能用 `this`

### 15.4 localStorage 封装

- `{ __v: 1, data }` 包装 + 内存回退（`memoryStore Map`）
- `isAvailable` 只检测一次缓存
- 防抖写入 300ms 默认

### 15.5 CSS 断点单一来源

- `matchMedia` 与 antd `sm/md` 对齐 767px
- 路由切换 `rAF` 重置滚动

### 15.6 LazyImage

- `IntersectionObserver`（rootMargin: 100px 提前加载）
- 阿里云 2x2 占位图检测（`PLACEHOLDER_MARKS`）直接显示 🖼️
- src 变化重置 loaded/error

---

## 16. 测试规范

### 16.1 测试栈

- **Vitest** 4.1 + **@testing-library/react** 16.3 + **jsdom** 29.1
- `environment: 'jsdom'`、`globals: true`、`setupFiles: ['./src/test-setup.ts']`、`css: false`

### 16.2 test-setup.ts

```ts
import '@testing-library/jest-dom/vitest'
```

### 16.3 测试文件组织

- 测试文件位于组件/hook 同级目录的 `__tests__/` 下
- 命名：`<Component>.test.tsx` 或 `<hook>.test.ts`
- 示例：
  ```
  components/SheetWorkspace/__tests__/SheetWorkspace.test.tsx
  hooks/__tests__/useAutoLiveSearch.test.ts
  stores/__tests__/sheetStore.test.ts
  pages/Evaluations/__tests__/resolveActionDisplay.test.ts  # 19 单测
  ```

### 16.4 测试用例规范

- **纯函数优先**：业务逻辑提取为纯函数（如 `resolveActionDisplay`）便于测试
- **mock 外部依赖**：`vi.mock('axios')`、`vi.mock('@/api/client')`
- **act() 包裹状态更新**：`act(() => { result.current.openSheet('/tasks') })`
- **断言用 jest-dom 匹配器**：`toBeVisible()`、`toHaveTextContent()`、`toBeInTheDocument()`

---

## 二、代码模板

## 模板1：API 模块

**文件位置**：`frontend/src/api/<域>.ts`

```ts
import { client } from './client'
import type { <域>Entity, <域>CreateBody, <域>UpdateBody } from './types'

// <域> API 模块
// 所有方法返回 Promise，错误统一抛 axios 兼容格式（含 response.status/data.detail）
export const <域>Api = {
  // 列表查询（GET，支持分页/过滤）
  list: (params?: { page?: number; pageSize?: number; keyword?: string }) =>
    client.get<<域>Entity[]>('/<域>', { params }).then(r => r.data),

  // 详情查询（GET，路径参数）
  get: (id: string) =>
    client.get<<域>Entity>(`/<域>/${id}`).then(r => r.data),

  // 创建（POST，请求体校验由后端 Pydantic 处理）
  create: (body: <域>CreateBody) =>
    client.post<<域>Entity>('/<域>', body).then(r => r.data),

  // 更新（PATCH，部分字段更新）
  update: (id: string, body: <域>UpdateBody) =>
    client.patch<<域>Entity>(`/<域>/${id}`, body).then(r => r.data),

  // 删除（DELETE，幂等）
  remove: (id: string) =>
    client.delete<{ success: boolean }>(`/<域>/${id}`).then(r => r.data),

  // SSE 流式接口（用 fetch + ReadableStream，错误抛 axios 兼容格式）
  live: (keyword: string, onEvent: (data: <域>StreamEvent) => void) => {
    const controller = new AbortController()
    const promise = fetch(`/api/<域>/live?keyword=${encodeURIComponent(keyword)}`, {
      method: 'GET',
      credentials: 'include',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('xh.token') ?? ''}`,
        'Accept': 'text/event-stream',
      },
      signal: controller.signal,
    }).then(async (res) => {
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: '未知错误' }))
        throw Object.assign(new Error(detail.detail), {
          response: { status: res.status, data: detail },
        })
      }
      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try { onEvent(JSON.parse(line.slice(6))) } catch { /* 忽略解析错误 */ }
          }
        }
      }
    })
    return { promise, cancel: () => controller.abort() }
  },
}
```

## 模板2：自定义 Hook

**文件位置**：`frontend/src/hooks/use<Feature>.ts`

```ts
import { useCallback, useEffect, useRef, useState } from 'react'

// 常量提取到模块级（S2004 修复：避免组件内多层闭包嵌套）
const DEFAULT_DEBOUNCE_MS = 400
const MAX_RETRIES = 3

type Status = 'idle' | 'loading' | 'success' | 'error'

// Hook 参数类型
type Use<Feature>Options = {
  debounceMs?: number
  enabled?: boolean
  onError?: (err: Error) => void
}

// Hook 返回值类型
type Use<Feature>Result = {
  status: Status
  data: <Result> | null
  error: Error | null
  retry: () => void
}

// Hook 实现
export function use<Feature>(opts: Use<Feature>Options = {}): Use<Feature>Result {
  const { debounceMs = DEFAULT_DEBOUNCE_MS, enabled = true, onError } = opts
  const [status, setStatus] = useState<Status>('idle')
  const [data, setData] = useState<<Result> | null>(null)
  const [error, setError] = useState<Error | null>(null)

  // ref 持有最新闭包避免 setInterval 陷阱
  const onErrorRef = useRef(onError)
  useEffect(() => { onErrorRef.current = onError }, [onError])

  // requestId 丢弃过时响应（useSearch 模式）
  const requestIdRef = useRef(0)

  // cancelled 标记防竞态（CronEditor 模式）
  const cancelledRef = useRef(false)

  const execute = useCallback(async () => {
    if (!enabled) return
    const currentRequestId = ++requestIdRef.current
    cancelledRef.current = false
    setStatus('loading')

    let lastError: Error | null = null
    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      if (cancelledRef.current) return
      try {
        const result = await fetch<Result>()  // 替换为实际 API 调用
        // 竞态保护：丢弃过时响应
        if (currentRequestId !== requestIdRef.current) return
        setData(result)
        setStatus('success')
        return
      } catch (err) {
        lastError = err as Error
        // 指数退避
        await new Promise(r => setTimeout(r, 1000 * Math.pow(2, attempt)))
      }
    }
    if (cancelledRef.current) return
    setError(lastError)
    setStatus('error')
    onErrorRef.current?.(lastError!)
  }, [enabled])

  // 触发执行（防抖）
  useEffect(() => {
    const id = setTimeout(execute, debounceMs)
    return () => clearTimeout(id)
  }, [execute, debounceMs])

  // 卸载时取消所有未完成回调
  useEffect(() => {
    return () => {
      cancelledRef.current = true
      requestIdRef.current++  // 让所有未完成回调失效
    }
  }, [])

  return {
    status,
    data,
    error,
    retry: execute,
  }
}
```

## 模板3：Zustand Store

**文件位置**：`frontend/src/stores/<feature>Store.ts`

```ts
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

// 常量提取到模块级
const PERSIST_DEBOUNCE_MS = 300
const MAX_ITEMS = 10

// State 类型
type <Feature>State = {
  items: Item[]
  activeItemId: string | null
  // 偏好
  maxItems: number
  // actions
  addItem: (item: Omit<Item, 'id'>) => void
  removeItem: (id: string) => void
  setActiveItem: (id: string | null) => void
  clearAll: () => void
}

// 模块级纯函数（S2004 修复）
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

// Store 实现（持久化只存必要字段）
export const use<Feature>Store = create<<Feature>State>()(
  persist(
    (set, get) => ({
      items: [],
      activeItemId: null,
      maxItems: MAX_ITEMS,

      addItem: (item) => set((state) => {
        // 循环替换：达 maxItems 时替换最旧
        if (state.items.length >= state.maxItems) {
          const [oldest, ...rest] = state.items
          const newItem = { ...item, id: generateId() }
          return {
            items: [...rest, newItem],
            activeItemId: newItem.id,
          }
        }
        const newItem = { ...item, id: generateId() }
        return {
          items: [...state.items, newItem],
          activeItemId: newItem.id,
        }
      }),

      removeItem: (id) => set((state) => {
        const items = state.items.filter(i => i.id !== id)
        const activeItemId = state.activeItemId === id
          ? items[0]?.id ?? null
          : state.activeItemId
        return { items, activeItemId }
      }),

      setActiveItem: (id) => set({ activeItemId: id }),

      clearAll: () => set({ items: [], activeItemId: null }),
    }),
    {
      name: 'xh-<feature>',
      storage: createJSONStorage(() => localStorage),
      // 持久化只存必要字段，过滤函数/ReactNode
      partialize: (state) => ({
        items: state.items.map(({ id, ...rest }) => ({ id, ...rest })),
        activeItemId: state.activeItemId,
        maxItems: state.maxItems,
      }),
      // 防抖写入
      debounce: PERSIST_DEBOUNCE_MS,
      // hydrate 时丢弃失效数据
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.items = state.items.filter(i => i.id && isValidItem(i))
        }
      },
    },
  ),
)

function isValidItem(item: unknown): item is Item {
  return typeof item === 'object' && item !== null && 'id' in item
}
```
