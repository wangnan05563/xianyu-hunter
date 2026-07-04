# 前端 API 契约审查（API Contract）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)

---

## 1. API 客户端架构

### 1.1 集中管理

```
frontend/src/api/
├── client.ts       # Axios 实例 + 拦截器
├── config.ts       # 配置 API
├── tasks.ts        # 任务 API
├── auth.ts         # 认证 API
├── ai.ts           # AI 服务 API
├── items.ts        # 商品 API
└── types.ts        # 统一类型定义
```

### 1.2 Axios 实例

```typescript
// client.ts
import axios from 'axios'

export const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true  // Cookie 认证
})

// 请求拦截：注入 token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('web_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：401 跳转登录
http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
```

### 1.3 API 方法

```typescript
// config.ts
import { http } from './client'
import type { AppConfig, SaveResponse } from './types'

export const configApi = {
  get: () =>
    http.get<AppConfig>('/config').then(r => r.data),

  save: (payload: AppConfig, dryRun = false) =>
    http.post<SaveResponse>('/config/save', {
      payload,
      dry_run: dryRun
    }).then(r => r.data),

  reset: () =>
    http.post('/config/reset'),
}
```

---

## 2. 类型契约

### 2.1 API 响应必须有类型

```typescript
// types.ts
export interface AppConfig {
  server: ServerConfig
  eval: EvalConfig
  buyer: BuyerConfig
  notifier: NotifierConfig
  // ...
}

export interface SaveResponse {
  ok: boolean
  dry_run: boolean
  diffs: DiffChange[]
}

export interface DiffChange {
  path: string
  op: 'add' | 'modify' | 'delete'
  old: string | null
  new: string | null
}
```

### 2.2 snake_case 透传

```typescript
// ❌ 反例：前端转 camelCase（导致后端校验失败）
const camelPayload = {
  autoBuyScore: 75,  // 后端期望 auto_buy_score
  passScore: 60
}

// ✅ 正例：snake_case 透传
const payload = {
  eval: {
    auto_buy_score: 75,
    pass_score: 60
  }
}
```

### 2.3 严格匹配后端

**禁止**前后端字段命名不一致。如需修改后端字段名，必须：
1. 后端先改 + 部署
2. 前端同步修改类型定义
3. 同时修改 API 调用处

---

## 3. 错误处理（核心规范）

### 3.1 统一错误提取工具

```typescript
// utils/apiError.ts
export function extractApiError(e: unknown): string {
  if (typeof e === 'object' && e !== null) {
    const resp = (e as { response?: { data?: unknown; status?: number } }).response
    if (resp) {
      const detail = (resp.data as Record<string, unknown>)?.detail
      if (typeof detail === 'string') return detail
      if (typeof detail === 'object' && detail !== null) {
        const msg = (detail as Record<string, unknown>).message
        const errors = (detail as Record<string, unknown>).errors
        if (typeof msg === 'string') {
          if (Array.isArray(errors) && errors.length > 0) {
            return `${msg}：${errors.join('; ')}`
          }
          return msg
        }
      }
      if (resp.status === 401) return '认证已过期，请重新登录'
      if (resp.status === 500) return '服务器内部错误，请稍后重试'
    }
  }
  return e instanceof Error ? e.message : '操作失败'
}
```

### 3.2 catch 块使用规范

```tsx
// ❌ 反例 1：笼统提示
try {
  await api.save()
} catch {
  message.error('保存失败')
}

// ❌ 反例 2：直接展示 axios 错误（不友好）
try {
  await api.save()
} catch (e: any) {
  message.error(e.message)
}

// ✅ 正例
import { extractApiError } from '@/utils/apiError'

try {
  await api.save()
  message.success('保存成功')
} catch (e) {
  message.error(extractApiError(e), 5)  // 5 秒持续时间
}
```

### 3.3 错误持续时间

| 类型 | 持续时间 | 原因 |
|---|---|---|
| 成功 | 3 秒（默认） | 简单信息 |
| 失败 | **5 秒** | 含校验细节，需阅读 |
| 警告 | 4 秒 | 中等信息量 |

### 3.4 必须覆盖的 HTTP 状态码

| 状态码 | 用户提示 |
|---|---|
| 200 | success |
| 400 校验失败 | `配置校验失败：xxx` |
| 401 | `认证已过期，请重新登录` |
| 403 | `权限不足` |
| 404 | `资源不存在` |
| 500 | `服务器内部错误，请稍后重试` |
| 网络断开 | `网络连接失败` |

---

## 4. 请求 / 响应

### 4.1 请求体格式

```typescript
// ✅ Content-Type 明确
http.post('/api/config/save', {
  payload: config,
  dry_run: true
}, {
  headers: { 'Content-Type': 'application/json' }
})
```

### 4.2 超时设置

```typescript
// 默认 30 秒
// 长时间操作（采集、评估）显式 60 秒
http.post('/api/collect/run', null, { timeout: 60_000 })
```

### 4.3 取消请求

```typescript
useEffect(() => {
  const controller = new AbortController()

  fetch('/api/items', { signal: controller.signal })
    .then(r => r.json())
    .then(setItems)
    .catch(e => {
      if (e.name === 'AbortError') return  // 忽略取消
      console.error(e)
    })

  return () => controller.abort()
}, [filter])
```

### 4.4 重试

```typescript
// 用 axios-retry 或手写
const fetchWithRetry = async (url: string, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      return await http.get(url)
    } catch (e) {
      if (i === retries - 1) throw e
      await new Promise(r => setTimeout(r, 1000 * (i + 1)))
    }
  }
}
```

---

## 5. 认证

### 5.1 Token 存储

```typescript
// ✅ 推荐：httpOnly cookie（最安全，由后端 Set-Cookie）
// ⚠️ 备选：localStorage（XSS 风险，但实现简单）
localStorage.setItem('web_token', token)
```

### 5.2 Token 注入

```typescript
// 拦截器统一注入（见 1.2）
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('web_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
```

### 5.3 Token 刷新

```typescript
// 401 时尝试刷新，失败再跳转登录
http.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    if (error.response?.status === 401) {
      try {
        const newToken = await authApi.refresh()
        localStorage.setItem('web_token', newToken)
        // 重试原请求
        return http.request(error.config)
      } catch {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)
```

---

## 6. 数据格式

### 6.1 时间格式

```typescript
// 后端 → 前端：ISO 8601 UTC
"2026-07-04T08:30:00.000Z"

// 前端展示：dayjs 格式化
import dayjs from 'dayjs'
dayjs(item.created_at).format('YYYY-MM-DD HH:mm')
```

### 6.2 数值精度

```typescript
// 金额保留 2 位小数
amount.toFixed(2)

// 百分比保留 1 位小数
(rate * 100).toFixed(1) + '%'
```

### 6.3 大数据量

```typescript
// ✅ 分页
http.get('/api/items?page=1&page_size=20')

// ✅ 流式（SSE）
new EventSource('/api/logs/stream')

// ❌ 一次性返回 10w 行
```

---

## 7. 常见 finding

| Finding | 修复 |
|---|---|
| `catch { message.error('失败') }` | 用 `extractApiError(e)` |
| catch 后无业务处理 | 至少 message 提示 |
| `message.error` 持续时间太短 | 失败用 5 秒 |
| API 路径硬编码 | 集中到 `api/` 模块 |
| 类型用 `any` | 补全类型 |
| 前后端字段命名不一致 | 严格 snake_case 透传 |
| 401 未处理 | 拦截器跳登录 |
| 超时未设置 | 显式 timeout |
| 重复请求未去重 | AbortController |

---

## 8. API 测试

### 8.1 MSW 模拟

```typescript
// tests/mocks/handlers.ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/config', () => {
    return HttpResponse.json(mockConfig)
  }),

  http.post('/api/config/save', async ({ request }) => {
    const body = await request.json()
    if (body.payload.eval.pass_score > body.payload.eval.auto_buy_score) {
      return HttpResponse.json(
        { detail: { message: '校验失败', errors: ['pass_score > auto_buy_score'] } },
        { status: 400 }
      )
    }
    return HttpResponse.json({ ok: true, dry_run: true, diffs: [] })
  })
]
```

### 8.2 端到端测试

```typescript
import { test, expect } from '@playwright/test'

test('保存失败应显示具体错误', async ({ page }) => {
  await page.goto('/app/config/buyer')
  await page.fill('.ant-input-number-input', '90')  // pass_score = 90
  await page.fill('.ant-input-number-input >> nth=1', '70')  // auto_buy_score = 70
  await page.click('button.ant-btn-primary')
  await expect(page.locator('.ant-message-error')).toContainText('校验失败')
})
```

---

## 9. 复盘：从对话中提炼

### 9.1 反模式 1：catch 块吞错

```tsx
// ❌ 反模式
try {
  await configApi.save(payload, true)
} catch {
  message.error('预览失败')  // 不知道是校验、网络、还是权限
}
```

**正确做法**：
```tsx
try {
  const diffs = await configApi.save(payload, true)
  setDiffChanges(diffs)
  setDiffModalOpen(true)
} catch (e) {
  message.error(extractApiError(e), 5)
  // 显示类似："配置校验失败，未保存：通过分数 pass_score(90) 不能大于 自动抢单分数 auto_buy_score(70)"
}
```

### 9.2 反模式 2：401 未处理

```typescript
// ❌ 反模式：401 错误无任何处理
export const http = axios.create({ baseURL: '/api' })
// token 过期后用户看到一堆 401 错误
```

**正确做法**：
```typescript
http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
```

### 9.3 反模式 3：API 路径散落

```tsx
// ❌ 散落
fetch('/api/config/save', ...)
fetch('/api/config/reset', ...)
fetch('/api/config/import', ...)

// ✅ 集中
configApi.save(...)
configApi.reset(...)
configApi.import(...)
```

---

## 10. 参考

- [Axios 拦截器](https://axios-http.com/docs/interceptors)
- [MDN AbortController](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)
- [项目错误处理规范总入口](../../xianyu-hunter-dev/references/error-handling.md)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)
