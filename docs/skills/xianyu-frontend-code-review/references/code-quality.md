# 前端代码质量审查（Code Quality）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)
> **范围**：TypeScript 类型 / 命名 / 注释 / 导入 / 测试覆盖

---

## 1. TypeScript 类型系统

### 1.1 严禁 `any`（TS-01）

```typescript
// ❌ 反例
const handleChange = (e: any) => {
  console.log(e.target.value)
}

// ✅ 正例：用 unknown + 类型守卫
const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  console.log(e.target.value)
}

// 或 Record<string, unknown>
const data: Record<string, unknown> = await response.json()
```

### 1.2 显式函数签名（TS-02）

```typescript
// ❌ 依赖推断
export const calcScore = (item) => item.price * 0.8 + 10

// ✅ 显式
export const calcScore = (item: Item): number => item.price * 0.8 + 10
```

### 1.3 API 响应必须有类型（TS-04）

```typescript
// ❌ 在页面内联类型
const [config, setConfig] = useState<any>(null)

// ✅ 引用 types.ts 统一类型
import type { AppConfig } from '@/api/types'
const [config, setConfig] = useState<AppConfig | null>(null)
```

### 1.4 Optional 字段统一 `?:` 风格（TS-05）

```typescript
// ❌ 混用
interface User {
  name: string
  age: number | null
  email?: string
}

// ✅ 统一 ?
interface User {
  name: string
  age?: number
  email?: string
}
```

---

## 2. 命名规范

| 类型 | 规范 | 示例 |
|---|---|---|
| 组件 | `PascalCase.tsx` | `BuyerStrategy.tsx` |
| 工具 | `camelCase.ts` | `apiError.ts` |
| 类型 / 接口 | `PascalCase` | `AppConfig`, `DiffChange` |
| 枚举 | `PascalCase` + 成员 `UPPER_SNAKE` | `TaskMode.AUTO_BUY` |
| 函数 | `camelCase` | `loadConfig` |
| 变量 | `camelCase` | `autoBuyScore` |
| 常量 | `UPPER_SNAKE` | `MAX_RETRY_COUNT` |
| CSS class | `kebab-case` | `.diff-preview-modal` |
| 私有属性 | `_` 前缀 | `_loadAll`, `_REDACT_KEYS` |

**与后端交互的字段必须 snake_case**（详见 `../api-contract.md`）。

---

## 3. 注释规范

### 3.1 注释解释 why，不解释 what

```typescript
// ❌ 反例：解释 what
// 加载配置
const config = await configApi.get()

// ✅ 正例：解释 why
// 必须先加载再渲染，否则 InputNumber 拿不到 initialValue
const config = await configApi.get()
```

### 3.2 复杂业务逻辑必须有注释

```typescript
// ✅ 颠倒加载顺序：避免 eval.yaml 整体覆盖 config.yaml 的 eval 子字段
//   旧实现用 data.update() 浅合并且 config.yaml 先加载 → 用户在 /app/config/buyer
//   修改的 pass_score 会被 eval.yaml 默认值覆盖
const data = { ...evalYaml, ...configYaml }
```

### 3.3 TODO 标记

```typescript
// TODO(username): 待 [issue#123] 解决后重构
//   触发条件：[特定错误]
//   临时方案：[当前实现]
```

### 3.4 JSDoc 公开 API

```typescript
/**
 * 从 axios 错误中提取后端返回的可读错误信息。
 *
 * 后端错误响应格式（由 exception_handler.py 统一）：
 * - 400 校验失败：{ detail: { message, errors } }
 * - 401 未授权：{ detail: "Unauthorized" }
 *
 * @param e axios 抛出的错误
 * @returns 用户可读的错误描述
 */
export function extractApiError(e: unknown): string { ... }
```

---

## 4. 导入规范

### 4.1 导入顺序

```typescript
// 1. 第三方库
import { useState, useEffect } from 'react'
import { Button, Form } from 'antd'

// 2. 内部别名
import { useConfigStore } from '@/stores/configStore'
import { configApi } from '@/api/config'

// 3. 相对路径
import { DiffPreviewModal } from '../../components/DiffPreviewModal'

// 4. 类型导入
import type { AppConfig, DiffChange } from '@/api/types'
```

### 4.2 路径别名

`tsconfig.json` 配置：
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

**新代码统一用 `@/`，旧代码逐步迁移**。

### 4.3 避免循环依赖

- `pages/` → `stores/` → `api/` 单向依赖
- 兄弟模块之间通过 `components/` 共享
- 不在 `api/` 内引用 `stores/`

---

## 5. 函数设计

### 5.1 单一职责

```typescript
// ❌ 函数做太多事
const handleSave = async () => {
  const cfg = await configApi.get()
  cfg.eval.auto_buy_score = 75
  const result = await configApi.save(cfg, true)
  if (result.diffs.length > 0) {
    setDiff(result.diffs)
    setOpen(true)
  }
  // 还做了加载、修改、预览、状态更新
}

// ✅ 拆分
const handleSave = async () => {
  const changes = await previewSave()  // 单一职责：预览
  if (changes.length === 0) {
    message.info('配置未变更')
    return
  }
  setDiffChanges(changes)
  setDiffModalOpen(true)
}
```

### 5.2 参数不超过 3 个

```typescript
// ❌ 参数太多
createUser(name, age, email, phone, address, role)

// ✅ 用对象
createUser({ name, age, email, phone, address, role })
```

### 5.3 避免副作用

```typescript
// ❌ 纯函数中修改外部
let counter = 0
const increment = () => ++counter

// ✅ 纯函数
const increment = (n: number) => n + 1
```

---

## 6. 错误处理

详见 [`api-contract.md`](api-contract.md)。**核心**：所有 catch 块用 `extractApiError`。

---

## 7. 测试覆盖

### 7.1 业务函数必须可测

```typescript
// ✅ 提取纯函数
export const calcEvalScore = (weights: Weights, metrics: ItemMetrics): number => {
  return (
    weights.professional * metrics.professionalScore +
    weights.credit * metrics.creditScore +
    ...
  )
}

// 测试
test('calcEvalScore 应按权重计算总分', () => {
  const score = calcEvalScore(
    { professional: 0.3, credit: 0.3, ... },
    { professionalScore: 100, creditScore: 80, ... }
  )
  expect(score).toBeCloseTo(78.5)
})
```

### 7.2 关键组件有快照测试

```typescript
import { render } from '@testing-library/react'
import { BuyerStrategy } from './BuyerStrategy'

test('BuyerStrategy 渲染默认状态', () => {
  const { container } = render(<BuyerStrategy />)
  expect(container).toMatchSnapshot()
})
```

### 7.3 关键交互有 E2E 测试

用 Playwright 覆盖：保存 / 取消 / 校验失败 / 网络错误。

---

## 8. 常见审查 finding

| Finding | 修复 |
|---|---|
| `useEffect` 依赖数组不完整 | 补全依赖或用 `useMemo` 派生 |
| `useState` 初始值用 `any` | 补全类型 |
| API 错误未捕获 | 加 try-catch + extractApiError |
| magic number 散落 | 提取常量 |
| 重复组件逻辑 | 提取公共组件 |
| 嵌套三元表达式 | 用 switch / if-else |
| `console.log` 留在代码 | 改为 `logger` 或删除 |
| 类型断言 `as` 滥用 | 用类型守卫 |

---

## 9. 参考

- [TypeScript 官方手册](https://www.typescriptlang.org/docs/handbook/intro.html)
- [React 类型检查](https://react-typescript-cheatsheet.netlify.app/)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)

---

## 十一、antd 组件使用模式

### 11.1 Modal 动态状态

| 审查项 | 要求 | 常见问题 |
|---|---|---|
| Modal.confirm 按钮状态 | 用 `modal.update()` 动态更新 | 用 `querySelector` 操作 DOM（不可靠） |
| 初始 disabled | `okButtonProps: { disabled: true }` | 初始未禁用，用户可跳过确认 |
| 输入验证 | onChange 中调 `modal.update()` 切换 disabled | onChange 只更新变量，不触发按钮状态更新 |

### 11.2 Menu 路径守卫

| 审查项 | 要求 | 常见问题 |
|---|---|---|
| onClick 路径校验 | `if (key.startsWith('/')) navigate(key)` | 所有 key 都 navigate（SubMenu 父项也会触发） |
| SubMenu key 命名 | 以 `sub-` 前缀标识 | 与路由 key 混淆 |

### 11.3 表格列中文标注

| 审查项 | 要求 | 常见问题 |
|---|---|---|
| 列标题 | 用中文简称 + Tooltip 显示完整标注 | 只显示英文字段名 |
| 表结构展示 | 独立"中文标注"列 | 缺少标注列 |
| 编辑表单 label | 中文简称 + 类型标签 + Tooltip | 只显示英文字段名 |

### 11.4 路由同步

| 审查项 | 要求 | 常见问题 |
|---|---|---|
| 新增页面 | App.tsx Route + MainLayout Menu + 页面组件三同步 | 只加组件和菜单，忘记路由 |
| 菜单 key | 以 `/` 开头的完整路径 | 使用非路径 key |
| 路由 fallback | `path="*"` 兜底到首页 | 缺少 fallback 导致白屏 |
