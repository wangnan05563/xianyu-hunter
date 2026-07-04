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
