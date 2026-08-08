# 前端状态管理与 API 联动规范

> **范围**：`frontend/src/stores/` + `frontend/src/api/` + 业务页面调用
> **技术栈**：Zustand 4 + Axios + Ant Design 5

---

## 一、Zustand 状态管理

### 1.1 Store 拆分

按业务模块切分，**不要**建一个全局大 store：

```
stores/
├── configStore.ts    # 配置管理（eval / price / search / notifier / AI）
├── taskStore.ts      # 任务管理
├── userStore.ts      # 用户登录态
├── dashboardStore.ts # 仪表盘
└── ...
```

### 1.2 Selector 订阅

```typescript
// ✅ 推荐：只订阅需要的字段
const autoBuyScore = useConfigStore(s => s.config.eval?.auto_buy_score)
const updateConfig = useConfigStore(s => s.updateConfig)

// ❌ 反例：订阅整个 store（任何字段变都重渲染）
const store = useConfigStore()
```

### 1.3 状态结构

```typescript
// configStore.ts
interface ConfigState {
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
```

### 1.4 Action 命名

| 类型 | 命名 | 示例 |
|---|---|---|
| 加载 | `loadXxx` | `loadConfig()` |
| 预览 | `previewXxx` | `previewSave()` |
| 提交 | `confirmXxx` | `confirmSave()` |
| 更新字段 | `updateXxx` | `updateField()` |
| 重置 | `resetXxx` | `resetConfig()` |

---

## 二、API 客户端

### 2.1 文件结构

```
api/
├── client.ts       # Axios 实例 + 拦截器
├── config.ts       # 配置相关 API
├── tasks.ts        # 任务相关 API
├── auth.ts         # 认证相关
├── ai.ts           # AI 服务
└── types.ts        # 统一类型定义
```

### 2.2 Client 拦截器

```typescript
// api/client.ts
import axios from 'axios'

export const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true  // 携带 Cookie 认证
})

// 请求拦截：注入 token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截：401 跳转登录
http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error.response?.status === 401) {
      // 跳登录页
    }
    return Promise.reject(error)
  }
)
```

### 2.3 API 方法

```typescript
// api/config.ts
import { http } from './client'
import type { AppConfig, DiffChange } from './types'

export const configApi = {
  get: () => http.get<AppConfig>('/config').then(r => r.data),

  save: (payload: AppConfig, dryRun = false) =>
    http.post<{ ok: boolean; diffs: DiffChange[] }>('/config/save', {
      payload,
      dry_run: dryRun
    }).then(r => r.data),

  reset: () => http.post('/config/reset'),
}
```

### 2.4 错误传播

API 层**不**处理业务错误，**直接 throw**：

```typescript
// ✅ 推荐：API 层只 throw，错误由调用方处理
export const configApi = {
  save: async (payload, dryRun) => {
    const { data } = await http.post('/config/save', { payload, dry_run: dryRun })
    return data
  }
}

// 调用方
try {
  const result = await configApi.save(payload, true)
  // 业务处理
} catch (e) {
  // 统一用 extractApiError
  message.error(extractApiError(e), 5)
}
```

---

## 三、保存流程（两阶段）

### 3.1 为什么两阶段

1. **预览（dry_run=true）**：显示 diff 让用户确认
2. **确认（dry_run=false）**：真正写盘

### 3.2 实现

```typescript
// configStore.ts
const useConfigStore = create<ConfigState>((set, get) => ({
  config: null,
  diffChanges: [],

  previewSave: async () => {
    const { config } = get()
    if (!config) throw new Error('配置未加载')

    const result = await configApi.save(config, true)  // dry_run
    set({ diffChanges: result.diffs })
    return result.diffs
  },

  confirmSave: async () => {
    const { config } = get()
    if (!config) throw new Error('配置未加载')

    await configApi.save(config, false)  // 实际写盘
    await get().loadConfig()  // 重新加载，确保本地状态与后端一致
  },
}))
```

### 3.3 页面调用

```typescript
// BuyerStrategy.tsx
const handleSave = async () => {
  try {
    setSaving(true)
    const changes = await previewSave()
    if (changes.length === 0) {
      message.info('配置未变更')
      return
    }
    setDiffChanges(changes)
    setDiffModalOpen(true)  // 弹 diff 预览
  } catch (e) {
    message.error(extractApiError(e), 5)
  } finally {
    setSaving(false)
  }
}

const handleConfirmSave = async () => {
  try {
    setSaving(true)
    await confirmSave()
    setDiffModalOpen(false)
    message.success('抢单策略已保存')
  } catch (e) {
    message.error(extractApiError(e), 5)
  } finally {
    setSaving(false)
  }
}
```

---

## 四、字段命名一致性

**铁律：snake_case 透传，不做大小写转换**

| 层 | 字段名 |
|---|---|
| YAML | `auto_buy_score` |
| Pydantic | `auto_buy_score: int` |
| TS 接口 | `auto_buy_score: number` |
| React 组件 prop | `auto_buy_score` |
| HTTP body | `auto_buy_score` |

**禁止**在中间任何一层做转换（如 `autoBuyScore`），避免后端校验通过但前端字段对不上。

---

## 五、Form 与 store 联动

### 5.1 简单字段

```typescript
// 用受控组件直接绑定 store
<InputNumber
  value={config?.eval?.auto_buy_score}
  onChange={(v) => updateField('eval.auto_buy_score', v)}
/>
```

### 5.2 复杂表单（评估规则多权重）

```typescript
// 用 Form.useForm() 管理本地状态
const [form] = Form.useForm()
const [initialValues, setInitialValues] = useState<Weights | null>(null)

useEffect(() => {
  if (config) {
    const weights = config.eval.weights
    setInitialValues(weights)
    form.setFieldsValue(weights)
  }
}, [config])

// 保存时合并到 config
const handleSave = async () => {
  const newWeights = await form.validateFields()
  updateField('eval.weights', newWeights)
  await previewSave()
  // ...
}
```

### 5.3 嵌套更新

```typescript
// store 中提供通用的 updateField(path, value)
updateField: (path: string, value: unknown) => {
  set((state) => {
    if (!state.config) return state
    const newConfig = structuredClone(state.config)
    setByPath(newConfig, path, value)  // lodash.set 类似
    return { config: newConfig }
  })
}
```

---

## 六、性能优化

| 场景 | 优化手段 |
|---|---|
| 大列表 | `React.memo` + 稳定 `key` |
| 重计算 | `useMemo` |
| 回调透传 | `useCallback` |
| 频繁触发 | `debounce` / `throttle` |
| 大型 Modal | 懒加载（`React.lazy`） |
| 不必要重渲染 | 拆分组件 + selector 订阅 |

---

## 七、测试

### 7.1 Store 单测

```typescript
import { renderHook, act } from '@testing-library/react'
import { useConfigStore } from './configStore'

test('previewSave 应该调用 API 并存储 diffs', async () => {
  const { result } = renderHook(() => useConfigStore())
  await act(async () => {
    await result.current.loadConfig()
    const diffs = await result.current.previewSave()
    expect(diffs).toBeInstanceOf(Array)
  })
})
```

### 7.2 页面 E2E

用 Playwright（已在 MCP 中配置）：

```typescript
// 1. 导航
await playwright_navigate({ url: '/app/config/buyer' })
// 2. 修改字段
await playwright_fill({ selector: '.ant-input-number-input', value: '75' })
// 3. 点击保存
await playwright_click({ selector: 'button.ant-btn-primary' })
// 4. 断言
expect(await getVisibleText()).toContain('配置变更预览')
```

---

## 八、Anti-Pattern

- ❌ 整个 store 订阅（重渲染爆炸）
- ❌ catch 块写 `message.error('失败')` 等笼统提示
- ❌ 在组件内联 `axios.post(...)`，不走 `api/` 模块
- ❌ 表单状态在多个组件各存一份
- ❌ 字段命名做大小写转换
- ❌ API 层吞错误
- ❌ 业务逻辑写在 useEffect 里（应该用 store action）
- ❌ 不写测试就改业务逻辑

---

## 九、相关文件

- `frontend/src/stores/configStore.ts` —— 配置 store 模板
- `frontend/src/api/config.ts` —— 配置 API
- `frontend/src/api/types.ts` —— 统一类型
- `frontend/src/pages/Config/BuyerStrategy.tsx` —— 抢单策略页面（参考实现）
- `frontend/src/utils/apiError.ts` —— 错误提取工具
- `frontend/src/components/DiffPreviewModal.tsx` —— Diff 预览组件
