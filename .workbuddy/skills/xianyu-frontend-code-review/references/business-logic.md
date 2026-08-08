# 前端业务逻辑审查（Business Logic）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)

---

## 1. 业务逻辑正确性（最高优先级）

业务逻辑 Bug 优先于类型 / 性能问题。审查时先看业务流是否正确。

### 1.1 数据流完整性

每个保存 / 提交操作必须验证完整流：

```
用户输入 → 本地 state → 客户端校验 → API 调用 → 后端校验 → 状态更新 → UI 反馈
   ✓          ✓            ✓           ✓          ✓          ✓          ✓
```

任何一环缺失都是 finding。

### 1.2 提交后刷新本地 state

```tsx
// ❌ 反例：只更新 UI，不刷新 store
const handleSave = async () => {
  await configApi.save(payload)
  message.success('保存成功')  // 但 store 里的数据没更新
}

// ✅ 正例：保存后 reload
const handleSave = async () => {
  await configApi.save(payload)
  await loadConfig()  // 重新加载确保一致性
  message.success('保存成功')
}
```

### 1.3 关键业务流必须有 E2E 测试覆盖

| 业务流 | 必须覆盖 |
|---|---|
| 配置修改-保存-刷新 | 修改 → 刷新后值不变 |
| 任务创建-启动-执行 | 任务状态机流转 |
| 抢单决策链 | 不同分数下行为正确 |
| 评估规则权重 | 修改后立即生效 |

---

## 2. 客户端校验

### 2.1 必填校验

```tsx
<Form.Item
  name="auto_buy_score"
  label="自动抢单最低分数"
  rules={[
    { required: true, message: '请输入自动抢单分数' },
    { type: 'number', min: 0, max: 100, message: '范围 0-100' }
  ]}
>
  <InputNumber />
</Form.Item>
```

### 2.2 跨字段约束

```tsx
<Form.Item
  shouldUpdate={(prev, curr) =>
    prev.pass_score !== curr.pass_score ||
    prev.auto_buy_score !== curr.auto_buy_score
  }
>
  {({ getFieldValue }) => {
    const passScore = getFieldValue('pass_score')
    const autoBuyScore = getFieldValue('auto_buy_score')
    if (passScore > autoBuyScore) {
      return <Alert type="error" message="通过分数不能大于自动抢单分数" />
    }
    return null
  }}
</Form.Item>
```

### 2.3 边界条件

```tsx
// 边界检查清单
- 空数组（空列表渲染）
- 0 值（数值边界）
- undefined / null（可选字段）
- 极大值（数值溢出）
- 特殊字符（用户输入）
- 国际化（中文 / 英文 / 表情）
- 时区（前端时间 vs 后端时间）
```

---

## 3. 状态正确性

### 3.1 状态机

任务状态 / 订单状态等有明确状态机，UI 必须严格按状态机显示：

```
任务：pending → running → completed
                    ↓
                  failed → retrying
```

```tsx
// ✅ 状态机明确
const TASK_STATUS = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  RETRYING: 'retrying'
} as const

const renderStatus = (status: TaskStatus) => {
  switch (status) {
    case TASK_STATUS.RUNNING: return <Badge status="processing" text="运行中" />
    case TASK_STATUS.COMPLETED: return <Badge status="success" text="完成" />
    case TASK_STATUS.FAILED: return <Badge status="error" text="失败" />
    // ...
  }
}
```

### 3.2 并发控制

防止用户重复提交 / 重复点击：

```tsx
const [submitting, setSubmitting] = useState(false)

const handleSubmit = async () => {
  if (submitting) return
  setSubmitting(true)
  try {
    await api.submit()
  } finally {
    setSubmitting(false)
  }
}

// UI 禁用
<Button onClick={handleSubmit} loading={submitting} disabled={submitting}>
  提交
</Button>
```

### 3.3 竞态条件

```tsx
// ❌ 竞态：旧请求后返回覆盖新数据
useEffect(() => {
  fetch('/api/data').then(setData)
}, [query])

// ✅ 用 cleanup 或 AbortController
useEffect(() => {
  const controller = new AbortController()
  fetch(`/api/data?q=${query}`, { signal: controller.signal })
    .then(r => r.json())
    .then(setData)
  return () => controller.abort()
}, [query])
```

---

## 4. 用户体验

### 4.1 Loading 状态

所有异步操作必须显示 loading：

```tsx
<Button loading={saving} onClick={handleSave}>保存</Button>
<Spin spinning={loading}><Table {...} /></Spin>
```

### 4.2 错误反馈

见 [`api-contract.md`](api-contract.md)。所有 catch 用 `extractApiError`。

### 4.3 成功反馈

```tsx
message.success('操作成功')

// ✅ 包含操作对象
message.success(`已保存配置：${changedFields.join(', ')}`)
```

### 4.4 不可逆操作二次确认

```tsx
import { Modal } from 'antd'

const handleDelete = (id: string) => {
  Modal.confirm({
    title: '确认删除？',
    content: '删除后无法恢复',
    okText: '确认',
    cancelText: '取消',
    okButtonProps: { danger: true },
    onOk: () => api.delete(id)
  })
}
```

### 4.5 表单离开提示

```tsx
useEffect(() => {
  const handler = (e: BeforeUnloadEvent) => {
    if (isDirty) {
      e.preventDefault()
      e.returnValue = '有未保存的修改，确定离开？'
    }
  }
  window.addEventListener('beforeunload', handler)
  return () => window.removeEventListener('beforeunload', handler)
}, [isDirty])
```

---

## 5. 业务约束 UI 体现

| 业务约束 | UI 体现 |
|---|---|
| `pass_score <= auto_buy_score` | 输入时实时校验 + 错误提示 |
| `qps` 必须为正数 | `InputNumber min={1}` |
| 任务模式需配合分数 | 显示推荐模式提示 |
| 评估权重之和 = 100 | 实时显示总和 + 警告 |
| Cookie 过期 | 提示重新登录 |
| 浏览器未登录 | 跳转登录页 |

---

## 6. 安全业务逻辑

### 6.1 权限校验

```tsx
// ✅ 前端根据用户角色显示不同操作
{user.role === 'admin' && (
  <Button onClick={handleDelete}>删除</Button>
)}

// ⚠️ 注意：前端权限仅用于 UI 体验，后端必须有二次校验
```

### 6.2 敏感操作

- 资金相关：自动抢单、转账 → 二次确认 + 金额显示
- 不可逆：删除、清空 → 二次确认
- 影响范围大：批量操作 → 预览 + 数量提示

### 6.3 输入验证

- 用户输入不直接拼接到 URL（防 SSRF）
- 用户输入不直接当 SQL（防注入，由后端把关）
- 用户输入不直接渲染 HTML（防 XSS）

---

## 7. 业务流程常见问题

### 7.1 抢单策略保存流程

**正确流程**：
1. 用户修改 `auto_buy_score`
2. 点击"保存"
3. 客户端校验（如 `pass_score <= auto_buy_score`）
4. 校验通过 → 调用 `previewSave()` → 显示 diff 预览
5. 用户确认 → 调用 `confirmSave()` → 实际写盘 + reload
6. 关闭 modal，显示成功提示
7. 用户刷新页面 → 看到新值

**易错点**：
- ❌ 跳过 diff 预览直接保存
- ❌ 保存失败不显示具体错误
- ❌ 保存后不 reload 导致 store 与后端不一致
- ❌ 校验失败 modal 不关闭

### 7.2 任务创建流程

```
1. 填写任务基本信息
2. 选择商品搜索条件
3. 选择评估规则
4. 选择任务模式（notify / confirm / auto）
5. 显示风险提示（auto 模式）
6. 用户确认 → 创建
7. 跳转任务列表
```

### 7.3 配置导入导出

```
导出：序列化整个 config → 下载 .yaml
导入：读取 .yaml → 校验 → 预览 diff → 确认覆盖
```

---

## 8. 时序与时间

### 8.1 时间显示

```tsx
// ❌ 直接显示 ISO
{item.created_at}  // 2024-01-15T08:30:00.000Z

// ✅ 友好格式
import dayjs from 'dayjs'
{dayjs(item.created_at).format('YYYY-MM-DD HH:mm')}  // 2024-01-15 08:30
```

### 8.2 倒计时 / 实时刷新

```tsx
// 实时数据用 SSE 或 WebSocket
useEffect(() => {
  const es = new EventSource('/api/events')
  es.onmessage = (e) => setData(JSON.parse(e.data))
  return () => es.close()
}, [])
```

### 8.3 时区

后端存 UTC，前端根据用户时区显示：

```tsx
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(utc)
dayjs.extend(timezone)

{dayjs.utc(item.created_at).tz(dayjs.tz.guess()).format()}
```

---

## 9. 业务逻辑审查 checklist

| 类别 | 检查项 |
|---|---|
| 数据流 | 提交后刷新本地 state？完整流（输入→UI）？ |
| 客户端校验 | 必填？范围？跨字段约束？边界？ |
| 状态机 | UI 严格按状态机显示？状态切换正确？ |
| 并发 | 防重复提交？竞态处理？ |
| 用户体验 | Loading？错误反馈？成功反馈？二次确认？ |
| 业务约束 | UI 体现？实时校验？ |
| 安全 | 权限？敏感操作？输入验证？ |
| 时序 | 时间格式？实时刷新？时区？ |

---

## 10. 复盘：从对话中提炼

### 10.1 反模式：保存失败不显示具体错误

**问题**：`catch { message.error('预览失败') }`

**修复**：`catch (e) { message.error(extractApiError(e), 5) }`

**影响**：用户看到"保存失败"但不知道是网络问题、权限问题还是参数错误。

### 10.2 反模式：保存成功但 state 没更新

**问题**：保存 API 返回成功，但前端 store 里的 config 还是旧值。

**修复**：`await confirmSave()` 后调用 `await loadConfig()` 强制 reload。

**影响**：用户刷新页面才看到新值，期间 UI 与实际数据不一致。

### 10.3 反模式：跳过 diff 预览直接保存

**问题**：直接 POST save 端点，跳过 dry_run 预览。

**修复**：所有写操作走两阶段（preview → confirm）。

**影响**：用户无法看到具体改了哪些字段，误操作难恢复。

---

## 11. 参考

- [React 状态管理](https://react.dev/learn/managing-state)
- [Ant Design Form 校验](https://ant.design/components/form#form-validation)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)

---

## 十一、级联操作前端表现

### 11.1 审查项

| 审查项 | 要求 | 说明 |
|---|---|---|
| 删除前预览 | 调 `cascadePreview` API 展示影响范围 | 让用户知道会连带删除/修改哪些数据 |
| 级联信息展示 | 列出每张关联表的表名+操作类型+影响行数 | 不能只显示"将删除关联数据" |
| 操作类型区分 | cascade 显示"🗑 删除"，set_null 显示"✂ 置空" | 用户需要知道是删除还是断开引用 |
| 无关联提示 | 显示"✓ 无关联数据，可安全删除" | 避免用户担心 |
| 删除结果展示 | 显示级联影响详情（`cascade` 字段） | 确认操作已完成并告知影响 |

### 11.2 正确模式

```typescript
// 删除前获取级联预览
const preview = await dbAdminApi.cascadePreview(activeTable, [pkValue])
if (preview.relations.length > 0) {
  // 展示每条关联规则的影响
  cascadeHtml = preview.relations.map(r => {
    const icon = r.action === 'cascade' ? '🗑' : '✂'
    return `${icon} ${r.description}`
  }).join('\n')
} else {
  cascadeHtml = '✓ 无关联数据，可安全删除'
}
```
