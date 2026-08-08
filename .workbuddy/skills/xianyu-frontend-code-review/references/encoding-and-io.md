# 前端编码与 I/O 审查（Encoding & I/O）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)
> **重点**：HTTP 请求 / 响应编码 / 文件下载 / 外部脚本调用 API 的前端审查要点
> **复盘来源**：FAQ 乱码问题（PowerShell 调用 API 默认 cp936 编码 body）

---

## 1. 审查维度（ENC-*）

### 1.1 HTTP 请求编码（ENC-01）

| 规则 | 严重度 |
|---|---|
| **`axios` / `fetch` 默认按 UTF-8 编码 body，禁止手动 `JSON.stringify` + `data:` 传参** | Critical |
| **自定义请求头必须包含 `Content-Type: application/json; charset=utf-8`** | Suggestion |
| **`URLSearchParams` 编码 query 参数默认 UTF-8，禁止混用 `encodeURIComponent` 与 `encodeURI`** | Suggestion |

```typescript
// ❌ Critical 违反 ENC-01：手动 stringify 可能被默认编码
import axios from 'axios'
const body = JSON.stringify({ question: '如何退款' })
axios.post('/api/xxx', body)  // ❌ 未指定 Content-Type，可能 latin-1

// ✅ 正确：用 json= 让 axios 自动 UTF-8 编码
axios.post('/api/xxx', { question: '如何退款' })

// ✅ 正确：手动 stringify 时显式 Content-Type
axios.post('/api/xxx', JSON.stringify({ question: '如何退款' }), {
  headers: { 'Content-Type': 'application/json; charset=utf-8' }
})
```

### 1.2 HTTP 响应解码（ENC-02）

| 规则 | 严重度 |
|---|---|
| **`fetch` 默认 UTF-8 解码 `resp.text()`，禁止覆盖 `TextDecoder` 为非 UTF-8** | Critical |
| **处理后端返回的字符串前不进行额外编码转换** | Critical |
| **二进制响应（文件下载）用 `arrayBuffer()` + `TextDecoder('utf-8')`** | Suggestion |

```typescript
// ❌ Critical 违反 ENC-02：覆盖默认 UTF-8 解码
const text = new TextDecoder('gbk').decode(await resp.arrayBuffer())

// ✅ 正确：默认 UTF-8
const text = await resp.text()

// ✅ 正确：二进制响应显式 UTF-8
const buf = await resp.arrayBuffer()
const text = new TextDecoder('utf-8').decode(buf)
```

### 1.3 用户输入处理（ENC-03）

| 规则 | 严重度 |
|---|---|
| **表单输入的中文字符直接透传，禁止 `encodeURIComponent` 后再传给 API** | Critical |
| **校验用户输入非 ASCII 字符不为 `?`（0x3f），防止编码损坏** | Suggestion |
| **`<input>` / `<textarea>` 的 value 始终是 UTF-16 字符串，无需转换** | Suggestion |

```typescript
// ❌ Critical 违反 ENC-03：编码后传给 API
const question = encodeURIComponent(inputValue)
await axios.post('/api/xxx', { question })  // 后端收到 %E5%A6%82%E4%BD%95 而非中文

// ✅ 正确：直接透传 UTF-16 字符串（axios 会自动 UTF-8 编码）
await axios.post('/api/xxx', { question: inputValue })

// ✅ 推荐：写入前校验非 ASCII 字符不为 ?
function validateNoMojibake(value: string): void {
  if (value.includes('?') && /[^\x00-\x7F]/.test(value)) {
    throw new Error('输入包含乱码字符 "?"，请检查输入法或编码')
  }
}
```

### 1.4 文件上传 / 下载（ENC-04）

| 规则 | 严重度 |
|---|---|
| **上传文件用 `FormData`，浏览器自动处理编码** | Suggestion |
| **下载文件名含中文必须 `encodeURIComponent` 处理 `Content-Disposition`** | Critical |
| **导出 JSON / CSV 文件必须显式 UTF-8 BOM（防 Excel 乱码）** | Critical |

```typescript
// ✅ 文件下载：中文文件名编码
const filename = '配置导出.json'
const encoded = encodeURIComponent(filename)
const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
const url = URL.createObjectURL(blob)
const a = document.createElement('a')
a.href = url
a.download = filename  // 现代浏览器支持直接中文
// 或：a.setAttribute('download', filename)

// ✅ CSV 导出：加 UTF-8 BOM 防 Excel 乱码
const csvContent = '\ufeff' + csvRows.join('\n')  // \ufeff 是 UTF-8 BOM
const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' })

// ✅ 文件上传：FormData
const formData = new FormData()
formData.append('file', fileInput.files?.[0] ?? '')
await axios.post('/api/upload', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
})
```

### 1.5 控制台输出（ENC-05）

| 规则 | 严重度 |
|---|---|
| **`console.log` 输出中文无需特殊处理（浏览器 DevTools 默认 UTF-8）** | Nit |
| **生产环境禁止保留 `console.log` 调试代码** | Suggestion |
| **日志服务（如 Sentry）传输前确认支持 UTF-8** | Suggestion |

### 1.6 外部脚本调用 API 模板（ENC-06）

| 规则 | 严重度 |
|---|---|
| **项目提供的调用模板必须显式 UTF-8 编码 body** | Critical |
| **PowerShell 模板必须用 `[Encoding]::UTF8.GetBytes()`** | Critical |
| **curl 模板必须用 `--data-binary @file.json`** | Critical |

```typescript
// 前端调用 API 标准模式（axios 自动 UTF-8）
import axios from 'axios'

export const apiClient = {
  async create(payload: { question: string; answer: string }): Promise<void> {
    // axios 默认 UTF-8 编码 body
    await axios.post('/api/xxx', payload, {
      headers: { 'Content-Type': 'application/json; charset=utf-8' }
    })
  }
}
```

---

## 2. 字符乱码诊断流程（前端视角）

### 2.1 前端排查步骤

```
Step 1: 浏览器 DevTools Network 查看响应 body
  - 真实字符是 ? 还是 \uXXXX 转义？
  - Response Headers 的 Content-Type 是否带 charset=utf-8？

Step 2: 检查请求 body
  - Request Payload 是否为真实中文？
  - Content-Type 是否带 charset=utf-8？

Step 3: 检查 axios / fetch 配置
  - 是否手动 stringify 后用 data: 传参？（可能导致默认编码）
  - 是否覆盖了 TextDecoder？

Step 4: 检查用户输入
  - 输入法是否正常？输入值是否包含 ? ？
  - 是否有 encodeURIComponent 干扰？

Step 5: 联合后端排查
  - 后端 API 接收到的 body 是否为真实中文？
  - 数据库存储是否为 0x3f（用 conn.text_factory = bytes 验证）？
```

### 2.2 审查 checklist

| 类别 | 检查项 |
|---|---|
| HTTP 请求 | 用 `json=` 参数而非手动 `data: JSON.stringify(...)`？ |
| HTTP 请求头 | 自定义请求包含 `Content-Type: application/json; charset=utf-8`？ |
| HTTP 响应 | 不覆盖 `TextDecoder` 为非 UTF-8？ |
| 用户输入 | 中文字符直接透传？未 `encodeURIComponent` 后传给 API？ |
| 输入校验 | 校验非 ASCII 字符不为 `?` 防止编码损坏？ |
| 文件下载 | 中文文件名用 `encodeURIComponent` 或现代浏览器原生支持？ |
| CSV 导出 | 加 UTF-8 BOM 防 Excel 乱码？ |
| 控制台 | 生产环境无 `console.log` 残留？ |
| 调用模板 | 项目提供的脚本模板显式 UTF-8 编码 body？ |

---

## 3. 复盘反模式（从对话中提炼）

### 3.1 反模式 4：手动 stringify + data 传参

**复盘案例**：FAQ 乱码问题中，PowerShell 默认 cp936 编码 body

**前端虽然用 axios 默认 UTF-8，但仍需警惕手动 stringify 的反模式**：

```typescript
// ❌ 反模式：手动 stringify 后用 data 传参
import axios from 'axios'
const body = JSON.stringify({ question: '如何退款' })
await axios.post('/api/xxx', body)  // ❌ 未指定 Content-Type

// ✅ 正确模式：用 json= 让 axios 自动 UTF-8 编码
await axios.post('/api/xxx', { question: '如何退款' })
```

**预防机制**：审查时 grep `axios.post.*JSON.stringify`，强制用 `json=`参数。

### 3.2 反模式 5：用户输入编码后传给 API

**复盘案例**：用户输入中文字符被 `encodeURIComponent` 转义后传给 API

```typescript
// ❌ 反模式：编码后传给 API
const question = encodeURIComponent(inputValue)
await axios.post('/api/xxx', { question })  // 后端收到 %E5%A6%82%E4%BD%95

// ✅ 正确模式：直接透传
await axios.post('/api/xxx', { question: inputValue })
```

**预防机制**：审查时检查 API 调用处，确认用户输入直接透传。

### 3.3 反模式 6：CSV 导出无 BOM 导致 Excel 乱码

**复盘案例**：导出 CSV 文件在 Excel 中打开显示乱码

```typescript
// ❌ 反模式：无 BOM
const csv = '问题,答案\n如何退款,请联系客服'
const blob = new Blob([csv], { type: 'text/csv' })

// ✅ 正确模式：加 UTF-8 BOM
const csv = '问题,答案\n如何退款,请联系客服'
const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
```

**预防机制**：所有 CSV 导出代码必须包含 `\ufeff` BOM。

### 3.4 反模式 7：覆盖 TextDecoder 为非 UTF-8

```typescript
// ❌ 反模式：覆盖默认 UTF-8 解码
const text = new TextDecoder('gbk').decode(await resp.arrayBuffer())

// ✅ 正确模式：默认 UTF-8
const text = await resp.text()
```

**预防机制**：审查时 grep `new TextDecoder`，确认参数为 `'utf-8'` 或无参数（默认 UTF-8）。

---

## 4. 测试用例

### 4.1 前端编码回归测试

```typescript
// tests/encoding.test.ts
import { describe, it, expect } from 'vitest'
import axios from 'axios'

describe('编码回归测试', () => {
  it('axios 请求 body 应为 UTF-8 编码', async () => {
    const payload = { question: '如何退款' }
    const response = await axios.post('/api/xxx', payload)
    expect(response.status).toBe(200)

    // 验证存储内容（联合后端测试）
    const stored = await axios.get('/api/xxx')
    expect(stored.data.question).toBe('如何退款')
    expect(stored.data.question).not.toContain('?')
  })

  it('用户输入直接透传，不 encodeURIComponent', () => {
    const input = '如何退款'
    const payload = { question: input }
    expect(payload.question).toBe(input)
    expect(payload.question).not.toMatch(/%[0-9A-F]{2}/)
  })

  it('CSV 导出包含 UTF-8 BOM', () => {
    const csv = '问题,答案\n如何退款,请联系客服'
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
    // 验证 BOM 存在
    expect(blob.type).toBe('text/csv;charset=utf-8')
  })
})
```

### 4.2 E2E 测试

```typescript
// tests/e2e/encoding.spec.ts
import { test, expect } from '@playwright/test'

test('FAQ 创建中文内容不乱码', async ({ page }) => {
  await page.goto('/app/chatbot/config')
  await page.fill('[placeholder="请输入问题"]', '如何退款')
  await page.fill('[placeholder="请输入答案"]', '请联系客服')
  await page.click('button:has-text("保存")')

  // 刷新页面验证
  await page.reload()
  await expect(page.locator('text=如何退款')).toBeVisible()
  await expect(page.locator('text=请联系客服')).toBeVisible()
})
```

---

## 5. 常用检查脚本

```bash
# grep 检查 axios.post 是否手动 stringify
rg "axios\.(post|put|patch)\(.*JSON\.stringify" frontend/src/

# grep 检查 TextDecoder 是否覆盖为非 UTF-8
rg "new TextDecoder\(['\"](?!utf-8)" frontend/src/

# grep 检查 encodeURIComponent 后传给 API
rg "encodeURIComponent.*axios" frontend/src/

# grep 检查 CSV 导出是否有 BOM
rg "Blob\(\['\\\\ufeff'" frontend/src/
rg "text/csv" frontend/src/

# grep 检查 console.log 残留
rg "console\.(log|debug)" frontend/src/ --type ts --type tsx
```

---

## 6. 参考

- [Axios 文档](https://axios-http.com/docs/intro)
- [Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
- [TextDecoder](https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/encoding-and-io.md)
- [项目编码规范](../../xianyu-hunter-dev/references/coding-standards.md)
- [前端 API 契约审查](api-contract.md)
- [前端代码质量审查](code-quality.md)
