# 前端异步取消与防抖模式（v1.0）

> **版本**：v1.0
> **日期**：2026-07-04
> **来源**：从"闲鱼登录模块"前端问题复盘（多标签页 / 取消登录卡死 / 双击触发 / 轮询终态保护）
> **对应检查点**：`FAC-01 ~ FAC-04`（前端异步操作与状态机维度）
> **适用范围**：`frontend/src/**/*.tsx` + `frontend/src/**/*.ts`
> **配套技能**：`xianyu-frontend-code-review` v4.17.0+、`xianyu-hunter-dev`（编码规范来源）

---

## 一、问题原型

**用户报告**：

| # | 现象 | 根因 |
|---|---|---|
| 1 | 弹出 4 个标签页 | 用户双击启动按钮，未做防抖 |
| 2 | 取消登录卡在"已取消" | in-flight polling resolve 覆盖 setLoginStatus(null) |
| 3 | 取消后状态闪烁 | 轮询无终态保护，已取消后仍在跑 |
| 4 | 重复触发 auth_helper | 启动按钮无 disabled 状态 |

**矛盾本质**：前端异步操作（轮询 + 取消 + 防抖 + 状态机）涉及多个独立维度的时序协调，任一环节处理不当都会导致用户体验异常，且现象（"卡死"）与根因（in-flight polling resolve 覆盖）之间无明显因果关系。

---

## 二、检查清单（自动化扫描）

### 2.1 违规模式（`FAC-01`：取消操作顺序）

#### 违规模式 A：先调 cancel API 再停本地轮询

```typescript
// ❌ 违规：cancel API 返回前，in-flight polling resolve 覆盖 setLoginStatus(null)
const handleCancelLogin = async () => {
  try {
    await authApi.cancelLogin()  // ❌ 远程调用期间轮询仍在跑
    if (pollRef.current) {
      clearInterval(pollRef.current)  // ❌ 太晚：in-flight 请求已 resolve
      setPollTimer(null)
    }
    setLoginStatus(null)
  } catch {
    message.error('取消失败')
  }
}
```

**问题**：
- cancel API 网络往返期间（200-500ms），轮询中的 in-flight 请求可能 resolve
- resolve 后的 setState 覆盖 cancel 路径的 `setLoginStatus(null)`
- 用户看到状态从"已取消"闪回"等待登录中"，卡死

#### 违规模式 B：cancel 路径未清理本地状态

```typescript
// ❌ 违规：cancel 后未清理 pollTimer / loginStatus
const handleCancelLogin = async () => {
  await authApi.cancelLogin()
  // ❌ 缺少 clearInterval(pollRef.current)
  // ❌ 缺少 setLoginStatus(null)
  // ❌ 缺少 setPollTimer(null)
}
```

### 2.2 违规模式（`FAC-02`：启动按钮防抖）

#### 违规模式 A：无防抖状态，直接调 API

```typescript
// ❌ 违规：无防抖，用户双击弹 4 个标签
const handleStartLogin = async () => {
  await authApi.startBrowserLogin()  // ❌ 双击会触发 2 次
  setPollTimer(setInterval(pollLoginStatus, 1000))
}
```

**问题**：
- 用户双击 / 网络慢时重复点击 → 多次调用 startBrowserLogin
- 后端启动多个 Chromium 子进程 → 弹出多个浏览器窗口
- 多次 setInterval 累积 → 内存泄漏 + 状态错乱

#### 违规模式 B：用 disabled 属性但不绑定状态

```typescript
// ❌ 违规：disabled 写死，不响应 API 完成
<Button disabled={false} onClick={handleStartLogin}>启动</Button>
// ❌ API 返回前后按钮都可点击
```

### 2.3 违规模式（`FAC-03`：轮询终态保护）

#### 违规模式 A：轮询 resolve 无条件 setState

```typescript
// ❌ 违规：已取消后轮询 resolve 仍 setState
const pollLoginStatus = async () => {
  const result = await authApi.getLoginStatus()
  // ❌ 缺少 if (loginStatus === 'cancelled') return
  setLoginStatus(result.status)  // 覆盖 cancel 路径的 null
}
```

#### 违规模式 B：无最大轮询次数限制

```typescript
// ❌ 违规：无上限轮询，超时后仍继续
const pollTimer = setInterval(async () => {
  const result = await authApi.getLoginStatus()
  if (result.status === 'success') {
    clearInterval(pollTimer)
  }
  // ❌ 缺少超时 / 最大次数保护
}, 1000)
```

### 2.4 违规模式（`FAC-04`：配置化要求）

#### 违规模式 A：轮询间隔硬编码

```typescript
// ❌ 违规：1000ms 硬编码
setInterval(pollLoginStatus, 1000)
```

#### 违规模式 B：超时时间硬编码

```typescript
// ❌ 违规：200s 超时硬编码
const MAX_WAIT = 200
if (elapsed > MAX_WAIT) {
  clearInterval(pollTimer)
}
```

---

## 三、修复模式（参考实现）

### 3.1 修复：取消操作先停本地再调远程

```typescript
// ✅ 修复：先停本地轮询，再调远程 cancel API
const handleCancelLogin = async () => {
  // 1. 先停本地轮询（避免 in-flight resolve 覆盖）
  if (pollRef.current) {
    clearInterval(pollRef.current)
    setPollTimer(null)
  }
  // 2. 清理本地状态（即使远程 cancel 失败也保持已取消）
  setLoginStatus(null)
  // 3. 再调远程 cancel API
  try {
    await authApi.cancelLogin()
    message.info('已取消登录')
  } catch {
    message.error('取消失败')
  }
  // 4. 远程返回后不再 setState（避免覆盖本地 null）
}
```

### 3.2 修复：启动按钮防抖状态

```typescript
// ✅ 修复：startingBrowser 状态防抖
const [startingBrowser, setStartingBrowser] = useState(false)

const handleStartLogin = async () => {
  // 防抖：API 返回前禁用按钮
  if (startingBrowser) return
  setStartingBrowser(true)
  try {
    await authApi.startBrowserLogin()
    setPollTimer(setInterval(pollLoginStatus, pollIntervalMs))
  } catch (e) {
    message.error(extractApiError(e), 5)
  } finally {
    setStartingBrowser(false)
  }
}

return (
  <Button disabled={startingBrowser} onClick={handleStartLogin}>
    {startingBrowser ? '启动中...' : '启动浏览器登录'}
  </Button>
)
```

### 3.3 修复：轮询终态保护

```typescript
// ✅ 修复：轮询前检查终态 + 最大次数限制
const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
const pollCountRef = useRef(0)
const maxPollCount = Math.ceil(timeoutSec * 1000 / pollIntervalMs)

const pollLoginStatus = async () => {
  // 终态保护：已取消 / 已成功 / 已超时 → 不再 setState
  if (loginStatus === null || loginStatus === 'success' || loginStatus === 'cancelled') {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      setPollTimer(null)
    }
    return
  }
  // 最大次数保护
  pollCountRef.current += 1
  if (pollCountRef.current > maxPollCount) {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      setPollTimer(null)
    }
    setLoginStatus('timeout')
    return
  }
  // 正常轮询
  try {
    const result = await authApi.getLoginStatus()
    // 二次终态检查（请求期间状态可能已变）
    if (loginStatus === null || loginStatus === 'cancelled') return
    setLoginStatus(result.status)
    if (result.status === 'success' || result.status === 'timeout' || result.status === 'error') {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        setPollTimer(null)
      }
    }
  } catch {
    // 网络错误不停止轮询，让用户看到友好提示
  }
}
```

### 3.4 修复：配置化要求

```typescript
// ✅ 修复：从配置读取轮询参数
import { useConfigStore } from '@/stores/config'

const Login: React.FC = () => {
  const pollIntervalMs = useConfigStore(s => s.config?.auth?.poll_interval_ms) ?? 1000
  const timeoutSec = useConfigStore(s => s.config?.auth?.qr_timeout_sec) ?? 200

  // ...
}
```

---

## 四、检测模式（自动扫描正则）

### 4.1 前端扫描模式（`config.yaml` 的 `async_cancel_debounce.detect_patterns`）

```yaml
detect_patterns:
  # cancel 路径先调 API 再停轮询
  - pattern: "await\\s+\\w+\\.cancel\\w*\\([^)]*\\)[\\s\\S]{0,200}clearInterval"
    message: "cancel 路径应先停本地轮询（clearInterval）再调远程 cancel API，避免 in-flight resolve 覆盖"
    severity: HIGH
    scope: "frontend/src/**/*.tsx"

  # 启动按钮无防抖状态
  - pattern: "onClick\\s*=\\s*\\{\\s*async\\s*\\(\\)\\s*=>\\s*\\{\\s*await\\s+\\w+\\.start"
    message: "启动按钮缺少防抖状态（startingXxx），用户双击会重复触发"
    severity: MEDIUM
    scope: "frontend/src/**/*.tsx"

  # 轮询 setInterval 硬编码
  - pattern: "setInterval\\([^,]+,\\s*\\d+\\)"
    message: "setInterval 间隔硬编码，应从配置读取（pollIntervalMs）"
    severity: LOW
    scope: "frontend/src/**/*.tsx"

  # 轮询无最大次数限制
  - pattern: "setInterval\\([^)]*\\)(?!.*maxPollCount)"
    message: "轮询无最大次数限制，可能无限运行导致内存泄漏"
    severity: MEDIUM
    scope: "frontend/src/**/*.tsx"
```

---

## 五、测试用例

### 5.1 前端测试（vitest）

```typescript
// tests/frontend/Login.cancel.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/react'
import { Login } from '@/pages/Login'

describe('Login 取消操作', () => {
  it('应先停本地轮询再调 cancel API', async () => {
    const cancelSpy = vi.fn(async () => {})
    const clearIntervalSpy = vi.spyOn(global, 'clearInterval')

    const { getByText } = render(<Login />)
    fireEvent.click(getByText('启动浏览器登录'))
    await waitFor(() => expect(getByText('取消登录')).toBeInTheDocument())

    fireEvent.click(getByText('取消登录'))

    // ✅ clearInterval 应在 cancelSpy 之前被调用
    expect(clearIntervalSpy).toHaveBeenCalled()
    expect(cancelSpy).toHaveBeenCalled()
    const clearIntervalOrder = clearIntervalSpy.mock.invocationCallOrder[0]
    const cancelOrder = cancelSpy.mock.invocationCallOrder[0]
    expect(clearIntervalOrder).toBeLessThan(cancelOrder)
  })

  it('启动按钮在 API 返回前应禁用', async () => {
    const { getByText } = render(<Login />)
    const button = getByText('启动浏览器登录') as HTMLButtonElement

    fireEvent.click(button)
    // ✅ 防抖：API 返回前 disabled = true
    expect(button.disabled).toBe(true)

    await waitFor(() => expect(button.disabled).toBe(false))
  })

  it('取消后轮询不应再 setState', async () => {
    const { getByText } = render(<Login />)
    fireEvent.click(getByText('启动浏览器登录'))
    await waitFor(() => expect(getByText('取消登录')).toBeInTheDocument())

    fireEvent.click(getByText('取消登录'))
    const statusAfterCancel = getByText('已取消').textContent

    // 等待 1 秒确认轮询 resolve 未覆盖
    await new Promise(r => setTimeout(r, 1100))
    expect(getByText('已取消').textContent).toBe(statusAfterCancel)
  })
})
```

---

## 六、相关文件

| 文件 | 职责 |
|------|------|
| `frontend/src/pages/Login/index.tsx` | 登录页（含防抖 + 取消逻辑） |
| `frontend/src/api/auth.ts` | 认证 API 客户端 |
| `frontend/src/stores/config.ts` | 配置 store（含 auth.poll_interval_ms / auth.qr_timeout_sec） |
| `frontend/src/utils/apiError.ts` | 错误信息提取工具 |
| `tests/frontend/Login.cancel.test.tsx` | 取消操作测试 |

---

## 七、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-04 | 初版：基于登录模块前端问题复盘，新增 `FAC-01 ~ FAC-04` 4 项检查点 |
