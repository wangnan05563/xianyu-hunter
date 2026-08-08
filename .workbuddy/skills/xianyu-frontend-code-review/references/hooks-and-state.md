# 前端 Hooks 与状态审查（Hooks & State）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)
> **范围**：React Hooks + Zustand 4 状态管理

---

## 1. React Hooks 规范

### 1.1 Hooks 规则（必须遵守）

| 规则 | 说明 | 严重度 |
|---|---|---|
| 只在顶层调用 | 不能在条件 / 循环 / 嵌套函数中调用 | Critical |
| 只在 React 函数中调用 | 不能在普通 JS 函数中调用 | Critical |
| 命名 `useXxx` | 自定义 hook 必须 `use` 前缀 | Suggestion |

```tsx
// ❌ 反例：条件调用 hook
if (isAdmin) {
  const [data, setData] = useState(null)  // ❌ 违反 Hooks 规则
}

// ✅ 正例：始终调用，用条件渲染
const [data, setData] = useState(null)
if (isAdmin) {
  return <AdminView data={data} />
}
return <NormalView />
```

### 1.2 useState

```tsx
// ✅ 类型显式
const [config, setConfig] = useState<AppConfig | null>(null)
const [loading, setLoading] = useState(false)

// ✅ 懒初始化（首次计算昂贵时）
const [items, setItems] = useState(() => loadInitialItems())

// ✅ 函数式更新（依赖前值时）
setCount(prev => prev + 1)
```

### 1.3 useEffect

```tsx
useEffect(() => {
  loadData()
  return () => {
    // 清理
  }
}, [deps])  // 依赖完整
```

**依赖数组完整性**（HK-01）：

```tsx
// ❌ 漏依赖
useEffect(() => {
  fetchData(query)
}, [])  // query 变了不重新请求

// ✅ 补全
useEffect(() => {
  fetchData(query)
}, [query])
```

**清理函数**（HK-02）：

```tsx
useEffect(() => {
  const timer = setInterval(tick, 1000)
  return () => clearInterval(timer)  // 清理
}, [])
```

### 1.4 useMemo

```tsx
// ✅ 用于重计算
const sorted = useMemo(
  () => items.sort((a, b) => b.score - a.score),
  [items]
)

// ✅ 用于稳定引用
const options = useMemo(() => [...], [])

// ❌ 不必要的 memo
const doubled = useMemo(() => count * 2, [count])  // 直接 count * 2 即可
```

### 1.5 useCallback

```tsx
// ✅ 透传给 memo 包装的子组件
const handleClick = useCallback((id: string) => {
  onItemClick(id)
}, [onItemClick])

// ❌ 不必要的 callback
const handleClick = useCallback(() => setCount(c => c + 1), [])  // 简单 setter 不用
```

### 1.6 自定义 Hooks

```typescript
// hooks/useDebouncedValue.ts
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}

// 使用
const debouncedSearch = useDebouncedValue(searchInput, 300)
```

### 1.7 复杂状态提取

```typescript
// hooks/useConfigForm.ts
export function useConfigForm(initialConfig: AppConfig) {
  const [config, setConfig] = useState(initialConfig)
  const [dirty, setDirty] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const updateField = useCallback((path: string, value: unknown) => {
    setConfig(prev => setByPath(prev, path, value))
    setDirty(true)
  }, [])

  const validate = useCallback(() => {
    // 校验逻辑
  }, [config])

  return { config, dirty, errors, updateField, validate }
}
```

---

## 2. Zustand 状态管理

### 2.1 Store 拆分

按业务模块切分，**禁止**全局大 store：

```
stores/
├── configStore.ts    # 配置管理
├── taskStore.ts      # 任务管理
├── userStore.ts      # 用户登录态
├── dashboardStore.ts # 仪表盘
├── logStore.ts       # 日志
└── notifyStore.ts    # 通知
```

### 2.2 Store 定义

```typescript
// stores/configStore.ts
import { create } from 'zustand'
import { configApi } from '@/api/config'
import type { AppConfig, DiffChange } from '@/api/types'

interface ConfigState {
  // State
  config: AppConfig | null
  loading: boolean
  saving: boolean
  diffChanges: DiffChange[]

  // Actions
  loadConfig: () => Promise<void>
  previewSave: () => Promise<DiffChange[]>
  confirmSave: () => Promise<void>
  updateField: (path: string, value: unknown) => void
  reset: () => void
}

export const useConfigStore = create<ConfigState>((set, get) => ({
  config: null,
  loading: false,
  saving: false,
  diffChanges: [],

  loadConfig: async () => {
    set({ loading: true })
    try {
      const config = await configApi.get()
      set({ config, loading: false })
    } catch (e) {
      set({ loading: false })
      throw e  // ✅ 上抛给调用方处理
    }
  },

  previewSave: async () => {
    const { config } = get()
    if (!config) throw new Error('配置未加载')

    const result = await configApi.save(config, true)
    set({ diffChanges: result.diffs })
    return result.diffs
  },

  confirmSave: async () => {
    const { config } = get()
    if (!config) throw new Error('配置未加载')

    await configApi.save(config, false)
    // ✅ 重新加载确保本地状态与服务端一致
    await get().loadConfig()
  },

  updateField: (path, value) => {
    set(state => {
      if (!state.config) return state
      const newConfig = structuredClone(state.config)
      setByPath(newConfig, path, value)
      return { config: newConfig }
    })
  },

  reset: () => set({ config: null, diffChanges: [] })
}))
```

### 2.3 Selector 订阅（关键）

```tsx
// ❌ 反例：订阅整个 store（任何字段变都重渲染）
const store = useConfigStore()
return <div>{store.config?.eval?.auto_buy_score}</div>

// ✅ 正例：selector 字段订阅
const autoBuyScore = useConfigStore(s => s.config?.eval?.auto_buy_score)
return <div>{autoBuyScore}</div>

// ✅ 多个字段
const { config, saving, updateField } = useConfigStore(
  useShallow(s => ({
    config: s.config,
    saving: s.saving,
    updateField: s.updateField
  }))
)
```

### 2.4 Action 设计

| 命名 | 用途 |
|---|---|
| `loadXxx` | 异步加载 |
| `saveXxx` / `updateXxx` | 异步更新 |
| `previewXxx` / `confirmXxx` | 两阶段操作 |
| `setXxx` | 同步设置 |
| `reset` / `clearXxx` | 重置 / 清理 |

### 2.5 异步 Action

```typescript
// ✅ 抛错给调用方
loadConfig: async () => {
  set({ loading: true })
  try {
    const config = await configApi.get()
    set({ config, loading: false })
  } catch (e) {
    set({ loading: false })
    throw e  // 让 catch 块处理
  }
}

// 调用方
try {
  await loadConfig()
} catch (e) {
  message.error(extractApiError(e), 5)
}
```

### 2.6 派生状态

```typescript
// ❌ 存派生状态
const useStore = create((set) => ({
  items: [],
  itemCount: 0,  // 派生
  hasItems: false,  // 派生
  addItem: (item) => set(s => {
    const items = [...s.items, item]
    return { items, itemCount: items.length, hasItems: items.length > 0 }
  })
}))

// ✅ 派生状态在组件中计算
const items = useStore(s => s.items)
const itemCount = items.length
const hasItems = items.length > 0
```

### 2.7 Store 组合

```typescript
// 跨 store 组合：用 selector
const isReady = useConfigStore(s => s.config != null) &&
                useUserStore(s => s.user != null)

// 提取到自定义 hook
function useAppReady() {
  return useConfigStore(s => s.config != null) &&
         useUserStore(s => s.user != null)
}
```

---

## 3. 状态一致性

### 3.1 单一数据源

```tsx
// ❌ 反例：组件内和 store 双重状态
const BuyerStrategy = () => {
  const config = useConfigStore(s => s.config)
  const [localAutoBuyScore, setLocalAutoBuyScore] = useState(75)  // ❌ 重复
  // ...
}

// ✅ 正例：state 全在 store
const BuyerStrategy = () => {
  const autoBuyScore = useConfigStore(s => s.config?.eval?.auto_buy_score)
  const updateField = useConfigStore(s => s.updateField)
  // ...
}
```

### 3.2 保存后刷新

```typescript
// ✅ confirmSave 后 reload
confirmSave: async () => {
  await configApi.save(config, false)
  await get().loadConfig()  // 关键：重新加载确保一致性
}
```

### 3.3 乐观更新 vs 悲观更新

```typescript
// 悲观：等服务器返回再更新
await api.save(payload)
await get().loadConfig()

// 乐观：立即更新 UI，失败回滚
const oldConfig = get().config
get().updateField('eval.auto_buy_score', newValue)
try {
  await api.save(newConfig)
} catch (e) {
  set({ config: oldConfig })  // 回滚
  throw e
}
```

---

## 4. 持久化

### 4.1 Zustand persist 中间件

```typescript
import { persist, createJSONStorage } from 'zustand/middleware'

export const useUserStore = create(
  persist<UserState>(
    (set) => ({
      user: null,
      setUser: (user) => set({ user }),
      clear: () => set({ user: null })
    }),
    {
      name: 'user-storage',
      storage: createJSONStorage(() => localStorage)
    }
  )
)
```

### 4.2 哪些状态要持久化

| 状态 | 持久化 |
|---|---|
| 用户登录态 | ✅ |
| 主题 / 语言 | ✅ |
| 表格筛选 / 分页 | ✅ |
| 表单草稿 | ✅ |
| 服务端数据（config / items） | ❌（重新加载） |
| 临时 UI 状态（loading / modal） | ❌ |

---

## 5. 常见反模式

| 反模式 | 修复 |
|---|---|
| `useStore()` 订阅整个 store | selector 字段订阅 |
| 组件内 `useState` 存服务端数据 | 用 store |
| `useEffect` 中修改 state 触发循环 | 用派生 state |
| 异步 action 吞错 | `throw e` |
| magic 字符串 | 提取常量 |
| 派生状态存 store | 组件中计算 |
| 重复的状态（组件 + store） | 单一数据源 |
| 保存后不 reload | `await loadConfig()` |
| Zustand 不分模块 | 按业务拆分 |

---

## 6. 审查 checklist

| 类别 | 检查项 |
|---|---|
| Hooks 规则 | 只在顶层调用？只在 React 函数中？命名规范？ |
| 依赖数组 | useEffect 依赖完整？清理函数？ |
| 性能 | useMemo 必要？useCallback 必要？ |
| 自定义 hook | 命名 `useXxx`？单一职责？可复用？ |
| Zustand 拆分 | 按业务模块？不大杂烩？ |
| Selector 订阅 | 不订阅整个 store？ |
| 异步 action | 抛错而非吞？loading 状态？ |
| 数据一致性 | 单一数据源？保存后 reload？ |
| 持久化 | 必要状态才持久？敏感数据不存 localStorage？ |

---

## 7. 复盘：从对话中提炼

### 7.1 反模式 1：订阅整个 store

**复盘案例**：`BuyerStrategy.tsx` 之前可能存在的 `const store = useConfigStore()`

**影响**：任何 config 字段变都触发整个组件树重渲染，性能差。

**修复**：selector 字段订阅：
```tsx
const autoBuyScore = useConfigStore(s => s.config?.eval?.auto_buy_score)
```

### 7.2 反模式 2：保存后不 reload

**复盘案例**：`confirmSave` API 成功但本地 store 还是旧值。

**修复**：
```typescript
confirmSave: async () => {
  await configApi.save(config, false)
  await get().loadConfig()  // 关键
}
```

### 7.3 反模式 3：catch 块吞错

**复盘案例**：loadConfig 失败时只 console.error，用户无感知。

**修复**：
```typescript
loadConfig: async () => {
  set({ loading: true })
  try {
    const config = await configApi.get()
    set({ config, loading: false })
  } catch (e) {
    set({ loading: false })
    throw e  // 上抛
  }
}
```

调用方用 `extractApiError` 提示。

---

## 8. 参考

- [React Hooks 官方文档](https://react.dev/reference/react)
- [Zustand 文档](https://github.com/pmndrs/zustand)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)

## 9. 轮询状态超时展示（F-REVIEW-191）

> **复盘来源**：后端浏览器登录心跳超时误判问题修复后，前端轮询应有超时展示规范——避免后端长时间返回 waiting/running 时前端无限等待
> **配置节点**：`async_polling_pattern.timeout_display`（`stale_threshold_sec` / `message_template` / `actions` / `component`）

### 9.1 usePollingWithTimeout Hook 模式

封装"轮询 + 超时检测"复合逻辑，避免每个调用点重复实现。超时检测复用轮询回调，无需独立 setTimeout：

```typescript
function usePollingWithTimeout<T>(
  fetcher: () => Promise<T>,
  options: {
    intervalMs: number
    staleThresholdSec: number
    onStateChange: (state: T) => void
    onTimeout: (staleSeconds: number) => void
  }
) {
  // 定时器引用必须存 useRef（参见 F-REVIEW-190），禁止 useState
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // 状态首次出现时间也存 useRef，避免每次渲染重置
  const stateFirstSeenRef = useRef<{ state: T | null; timestamp: number }>({
    state: null,
    timestamp: 0,
  })

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => {
    timerRef.current = setInterval(async () => {
      const state = await fetcher()
      const prev = stateFirstSeenRef.current
      if (prev.state !== state) {
        // 状态变化：重置首次出现时间
        stateFirstSeenRef.current = { state, timestamp: Date.now() }
        options.onStateChange(state)
      } else {
        // 状态不变：检测是否超过 stale_threshold_sec
        const staleSec = (Date.now() - prev.timestamp) / 1000
        if (staleSec > options.staleThresholdSec) {
          options.onTimeout(staleSec)
          clearTimer() // 超时后必须停止轮询，交由父组件决策
        }
      }
    }, options.intervalMs)
    return clearTimer
  }, [options.intervalMs, options.staleThresholdSec])

  return { clearTimer }
}
```

### 9.2 状态首次出现时间记录

- 使用 `useRef` 存储 `{ state, timestamp }`，避免每次渲染重新创建（useState 会触发重渲染且丢失时间戳）
- 状态变化时重置 `timestamp = Date.now()`，状态不变时累加 `staleSeconds`
- 禁止用 `useState` 存储定时器返回值（参见 F-REVIEW-190）

### 9.3 超时计时器与轮询计时器的协同

- **轮询计时器**：`setInterval` 调用 fetcher，间隔 `intervalMs`（从 `async_polling_pattern.interval_ms` 读取）
- **超时检测**：在轮询回调内同步检测，**无需独立 setTimeout**——复用轮询节奏即可，避免两个定时器竞争
- **触发超时**：调用 `onTimeout` 回调并 `clearInterval`，由父组件决定是否重试（展示 Alert + 重试/取消按钮）

### 9.4 cleanup 逻辑（两个计时器引用的清理）

- **组件卸载**：`useEffect` 的 cleanup 调用 `clearTimer` 清除轮询定时器
- **超时触发**：`onTimeout` 内调用 `clearTimer`，避免继续轮询无响应的状态
- **重试**：由父组件重新挂载 Hook 或调用 reset 方法（重置 `stateFirstSeenRef` 并重新启动 interval）
- **关键约束**：`stateFirstSeenRef` 在重试时必须重置（state=null, timestamp=0），否则会立即再次触发超时

---

## 10. SPA 渲染容错三件套（F-REVIEW-214 / 215 / 216）

> **复盘来源**：2026-07-22 React SPA 间歇性白屏修复复盘——5 类根因中 3 类与渲染容错缺失相关（无全局 ErrorBoundary / lazy 无重试 / 路由级错误无隔离）
> **配套规范**：[version-changelog.md §v4.59.0](./version-changelog.md)、`xianyu-hunter-dev` step 254-256 / meta-rule #95
> **配置节点**：`spa_white_screen_resilience.globalErrorBoundary` / `spa_white_screen_resilience.lazyRetry` / `spa_white_screen_resilience.routeErrorBoundary` / `spa_white_screen_resilience.resetKeysConstraint`

三件套部署顺序：① App.tsx 全局 ErrorBoundary → ② MainLayout 路由级 ErrorBoundary（resetKeys=[location.pathname]）→ ③ lazyRetry 包装所有 lazy() 调用。

### 10.1 全局错误边界强制部署（F-REVIEW-214）

| 规则 | 说明 |
|---|---|
| **App.tsx 必须用 `<ErrorBoundary>` 包裹整个 Routes** | 维度 3，CRITICAL；缺失时组件树抛错整页白屏 |
| **类组件实现完整四件套** | `getDerivedStateFromError` + `componentDidCatch` + `resetKeys` 自动重置 + `onError` 回调 |
| **fallback UI 用 antd Result** | `fallbackType: "antd-result"`（从 config 读取），保证降级 UI 与项目风格一致 |
| **必须导出 onError 钩子** | 允许业务侧接入埋点/告警，禁止静默吞错 |

**判断信号**：

```bash
# 命中 0 → CRITICAL
grep -c "<ErrorBoundary" frontend/src/App.tsx
```

**修复模式**：

```tsx
// frontend/src/components/ErrorBoundary.tsx
interface ErrorBoundaryProps {
  children: React.ReactNode
  resetKeys?: Array<string | number>  // 基本类型数组，禁止对象/数组引用（见 §10.3）
  onError?: (error: Error, info: React.ErrorInfo) => void
  fallback?: React.ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    this.props.onError?.(error, info)
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps): void {
    if (this.state.hasError && prevProps.resetKeys !== this.props.resetKeys) {
      this.setState({ hasError: false, error: null })
    }
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <Result
          status="error"
          title="页面加载失败"
          subTitle={this.state.error?.message}
          extra={<Button type="primary" onClick={() => window.location.reload()}>刷新页面</Button>}
        />
      )
    }
    return this.props.children
  }
}
```

```tsx
// frontend/src/App.tsx
// 必须在 Routes 外层包裹 ErrorBoundary，任何子组件抛错时降级而非白屏
function App() {
  return (
    <ErrorBoundary onError={(e, info) => logger.error('global EB', e, info)}>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Home />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  )
}
```

**适用场景**：所有 React SPA。**不适用场景**：Next.js SSR（框架自带 error.tsx）、纯静态 HTML、React Native。

### 10.2 懒加载重试包装器强制（F-REVIEW-215）

| 规则 | 说明 |
|---|---|
| **禁止裸用 `lazy()`** | 维度 10，CRITICAL；裸 lazy 遇 ChunkLoadError 直接抛错白屏 |
| **必须用 `lazyRetry()` 包装** | 包装 lazy() + isChunkLoadError 识别 + sessionStorage 重试计数 + LazyErrorBoundary 兜底 |
| **重试计数必须用 sessionStorage 持久化** | 避免页面 reload 后计数丢失导致死循环 |
| **maxRetries 从 config 读取** | 默认 3，禁止硬编码 |
| **ChunkLoadError 识别模式从 config 读取** | 子细则（原 R5 合并）：`chunkErrorPatterns` 列表支持多条正则 |

**判断信号**：

```bash
# 命中 → CRITICAL
grep "\blazy(" frontend/src/ | grep -v lazyRetry
```

**修复模式**：

```tsx
// frontend/src/utils/lazyRetry.tsx
const CHUNK_ERROR_PATTERNS = [
  /Failed to fetch dynamically imported module/,
  /Loading chunk \d+ failed/,
  /Loading CSS chunk \d+ failed/,
]  // 实际从 config.spa_white_screen_resilience.lazyRetry.chunkErrorPatterns 编译

function isChunkLoadError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err)
  return CHUNK_ERROR_PATTERNS.some(p => p.test(msg))
}

export function lazyRetry<T extends React.ComponentType<any>>(
  factory: () => Promise<{ default: T }>,
  options: { name: string; maxRetries?: number } = { name: 'unknown' }
): React.LazyExotic<T> {
  const maxRetries = options.maxRetries ?? 3  // 从 config 读取
  const storageKey = `__retry_${options.name}`

  return React.lazy(async () => {
    const retried = Number(sessionStorage.getItem(storageKey) ?? '0')
    try {
      const mod = await factory()
      sessionStorage.removeItem(storageKey)  // 成功后清除计数
      return mod
    } catch (err) {
      if (isChunkLoadError(err) && retried < maxRetries) {
        sessionStorage.setItem(storageKey, String(retried + 1))
        window.location.reload()  // 必须用 reload 重新拉取 chunk
        // 不应到达此处；返回占位避免类型错误
        throw err
      }
      // 超过 maxRetries 或非 ChunkLoadError：交给 LazyErrorBoundary 兜底
      sessionStorage.removeItem(storageKey)
      throw err
    }
  })
}
```

```tsx
// 使用对比
// ❌ 反例：裸 lazy，ChunkLoadError 直接白屏
const Settings = lazy(() => import('./pages/Settings'))

// ✅ 正例：lazyRetry 包装
const Settings = lazyRetry(() => import('./pages/Settings'), { name: 'Settings' })
```

**适用场景**：Vite/Webpack 代码分割的 SPA、PWA、CDN 部署。**不适用场景**：无代码分割的单 bundle、SSR、React Native。

### 10.3 路由级错误边界与 resetKeys 约束（F-REVIEW-216）

| 规则 | 说明 |
|---|---|
| **MainLayout Content 必须用 `<ErrorBoundary resetKeys={[location.pathname]}>` 包裹 Outlet** | 维度 10，CRITICAL；缺失时子路由抛错冒泡到全局导致整个 Layout 白屏 |
| **resetKeys 必须是基本类型数组** | 子细则（原 R4 合并）：仅允许 string / number，禁止对象 / 数组引用 |
| **resetKeys 变化时自动重置 ErrorBoundary** | 路由切换时自动清错，避免上一个路由的错误污染新路由 |
| **禁用对象/数组作为 resetKeys** | 对象/数组引用每次渲染都变化或永不变化，导致要么永远重置要么永不重置 |

**判断信号**：

```bash
# 未命中 → CRITICAL
grep "resetKeys" frontend/src/components/layout/MainLayout.tsx
# 含对象/数组引用（如 resetKeys={[someObj]} / resetKeys={[arr]}) → WARNING
```

**修复模式**：

```tsx
// frontend/src/components/layout/MainLayout.tsx
function MainLayout() {
  const location = useLocation()
  return (
    <Layout>
      <Sider>...</Sider>
      <Layout>
        <Header>...</Header>
        <Content>
          {/* resetKeys 用 location.pathname 基本类型，路由切换时自动重置错误状态 */}
          <ErrorBoundary resetKeys={[location.pathname]}>
            <Outlet />
          </ErrorBoundary>
        </Content>
      </Layout>
    </Layout>
  )
}
```

```tsx
// ❌ 反例 1：未包裹 ErrorBoundary，子路由抛错冒泡整页白屏
<Content>
  <Outlet />
</Content>

// ❌ 反例 2：resetKeys 含对象引用，每次渲染引用变化导致永远重置
const someState = useMemo(() => ({ filter: 'x' }), [filter])
<ErrorBoundary resetKeys={[someState]}>  {/* ❌ 对象引用 */}
  <Outlet />
</ErrorBoundary>

// ❌ 反例 3：resetKeys 含数组引用
const items = useItems()
<ErrorBoundary resetKeys={[items]}>  {/* ❌ 数组引用 */}
  <Outlet />
</ErrorBoundary>
```

**resetKeys 类型约束**（从 `spa_white_screen_resilience.resetKeysConstraint` 读取）：

| 类型 | 允许 |
|---|---|
| string | ✅ |
| number | ✅ |
| object | ❌ WARNING |
| array | ❌ WARNING |

**适用场景**：路由级 ErrorBoundary、Tab 切换、弹窗内 ErrorBoundary。**不适用场景**：全局根 ErrorBoundary（无路由上下文，无 resetKeys 需求）。

### 10.4 三件套协同关系

- **全局 ErrorBoundary（F-REVIEW-214）** 是最后一道防线，捕获所有未被子级 ErrorBoundary 处理的错误
- **路由级 ErrorBoundary（F-REVIEW-216）** 优先捕获子路由错误，配合 resetKeys 实现路由切换自动恢复
- **lazyRetry（F-REVIEW-215）** 在 chunk 加载失败时优先尝试重试，重试耗尽后抛错交给 ErrorBoundary 兜底
- 三者必须同时部署，缺任一项都会留下白屏缺口
