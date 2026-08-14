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
//   旧实现用 data.update() 浅合且 config.yaml 先加载 → 用户在 /xianyu/config/buyer
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

## 9. 跨边界访问契约（前端侧）

> **复盘来源**：后端 `TypeError: can't subtract offset-naive and offset-aware datetimes` 与 `AttributeError: 'XxxRepository' object has no attribute '_Session'` 两个 Bug 的共同根因都是「跨边界契约不明确」。前端虽无 datetime aware/naive 问题（JS Date 统一 aware），但跨边界访问同样需要明确契约。
> **配套规范**：[coding-standards.md §2.14 跨边界访问契约](../../xianyu-hunter-dev/references/coding-standards.md#214-跨边界访问契约核心抽象原则)

### 9.1 后端 datetime 字段渲染契约（F-REVIEW-DATETIME-RENDER-CONTRACT）

| 规则 | 说明 |
|---|---|
| **后端 ISO 字符串必须显式 `new Date()` 解析** | 后端返回 `2026-07-05T10:00:00+00:00`，前端必须 `new Date(isoStr)` 转为 Date 对象，禁止直接字符串拼接 |
| **后端无时区 ISO 字符串按 UTC 解析** | 后端返回 naive ISO（如 `2026-07-05T10:00:00`），前端 `new Date(isoStr + 'Z')` 显式按 UTC 解析 |
| **展示前统一 `toLocaleString` 转本地时区** | 用户看到的展示必须是本地时区，禁止直接展示 UTC 时间 |
| **跨时区传递必须保留 ISO 字符串** | 前端 → 后端传递时间用 `Date.toISOString()`，禁止 `toString()` 丢失时区 |

```typescript
// ✅ 正确：后端 ISO 字符串显式 new Date() 解析 + 本地时区展示
const formatDate = (isoStr: string | null): string => {
  if (!isoStr) return '—'
  const date = new Date(isoStr)
  return date.toLocaleString('zh-CN', { hour12: false })
}

// ✅ 正确：后端 naive ISO 字符串按 UTC 解析（后端约定 naive 存储）
const formatNaiveDate = (naiveIso: string | null): string => {
  if (!naiveIso) return '—'
  // 后端 SQLite DateTime 列读回 naive，应用层按 UTC 处理
  const date = new Date(naiveIso + 'Z')
  return date.toLocaleString('zh-CN', { hour12: false })
}

// ❌ 错误：直接字符串拼接展示，丢失时区信息
const formatDate = (isoStr: string): string => {
  return isoStr.replace('T', ' ').slice(0, 19)  // 无时区转换
}

// ❌ 错误：用 toString() 而非 toISOString() 传递给后端
const sendTime = (date: Date): Promise<void> => {
  return api.save({ time: date.toString() })  // 本地时区格式，后端解析失败
}
```

**适用场景**：
- 渲染后端返回的 datetime 字段（created_at / updated_at / publish_time 等）
- 前端 → 后端传递时间（表单提交 / 查询参数）
- 跨时区展示（用户在不同时区访问同一系统）

**不适用场景**：
- 纯前端生成的 Date 对象（无跨边界）
- 用户输入的日期字符串（前端 Form 已处理）

### 9.2 跨组件访问私有 hooks/state 封装（F-REVIEW-PRIVATE-HOOK-ENCAPSULATION）

| 规则 | 说明 |
|---|---|
| **`_` 前缀 hooks/state 禁止跨组件访问** | 项目约定 `_` 前缀为内部 hooks/state，外部组件应通过导出的公共 hooks 访问 |
| **Hooks 必须导出公共 API** | 跨组件需要的内部状态应通过 `useXxxState()` 等 hooks 封装，暴露 `state` + `setState` |
| **Zustand store 私有字段禁止外部 setState** | store 内部维护的字段（如 `_internalState`）禁止外部组件直接 set，应通过 store action 封装 |
| **ref 内部属性禁止跨组件引用** | `useRef` 内部属性（如 `ref.current._internalCache`）禁止父组件 / 兄弟组件直接访问 |

```typescript
// ✅ 正确：hooks 提供公共 API 封装内部状态
// hooks/usePersistentState.ts
export function usePersistentState<T>(
  key: string,
  initialValue: T,
  validator?: (value: unknown) => value is T
): [T, (value: T | ((prev: T) => T)) => void] {
  const [_internalState, _setInternalState] = useState<T>(initialValue)
  // ✅ 内部用 _ 前缀，外部只访问返回的 state + setState
  // ... 持久化逻辑
  return [state, setState]  // 公共 API
}

// ✅ 正确：Zustand store 通过 action 封装内部状态
interface XxxStore {
  config: XxxConfig
  _internalCache: Map<string, unknown>  // 私有，禁止外部 setState
  updateConfig: (patch: Partial<XxxConfig>) => void  // 公共 action
  _invalidateCache: () => void  // 私有 action，仅 store 内部调用
}

// ❌ 错误：跨组件访问 hooks 内部状态
function SomeParent() {
  const xxxRef = useRef<XxxHandle>(null)
  // ❌ 通过 ref 访问子组件内部 state
  useEffect(() => {
    console.log(xxxRef.current?._internalState)  // 破坏封装
  }, [])
  return <SomeChild ref={xxxRef} />
}

// ❌ 错误：跨组件访问 Zustand store 私有字段
function SomeComponent() {
  const _internalCache = useXxxStore(s => s._internalCache)  // ❌ 访问私有字段
  const setInternalCache = useXxxStore(s => s._setInternalCache)  // ❌ 调用私有 action
}
```

**适用场景**：
- 自定义 Hooks 被多个组件使用
- Zustand store 被多个组件订阅
- 父组件通过 ref 访问子组件内部状态

**不适用场景**：
- 组件内部用 useState 维护的局部状态（无跨组件访问）
- 公共 hooks 返回的 state + setState（公共 API）

### 9.3 命名一致性验证（前端侧）（F-REVIEW-NAMING-CONSISTENCY-FRONTEND）

| 规则 | 说明 |
|---|---|
| **hooks 命名全库一致** | `useXxxState` / `useXxxStore` / `useXxxEffect` 风格全库统一，禁止 `useXxx` 与 `usexxx` 共存 |
| **store 字段命名一致** | Zustand store 字段大小写 / 单复数 / 前缀（`_` / 无前缀）必须全 store 一致 |
| **跨组件引用必须与定义一致** | 跨组件 import 的 hooks / store 字段必须与定义完全一致（含大小写） |
| **camelCase / PascalCase / UPPER_SNAKE 规范** | 变量 / 函数 camelCase，组件 / 类型 PascalCase，常量 UPPER_SNAKE |

```typescript
// ✅ 正确：hooks 命名风格全库一致
// hooks/usePersistentState.ts —— 定义
export function usePersistentState<T>(...) { ... }

// pages/SomePage.tsx —— 引用
import { usePersistentState } from '@/hooks/usePersistentState'  // ✅ 大小写匹配

// ❌ 错误：跨组件引用大小写不一致
// hooks/usePersistentState.ts —— 定义 usePersistentState
// pages/SomePage.tsx —— 引用
import { usepersistentstate } from '@/hooks/usePersistentState'  // ❌ 大小写错误

// ✅ 正确：store 字段命名一致 + 通过公共 action 修改
interface XxxStore {
  config: XxxConfig              // 公共字段
  _internalCache: Map<string, unknown>  // 私有字段（_ 前缀）
  updateConfig: (patch: Partial<XxxConfig>) => void  // 公共 action
  _invalidateCache: () => void   // 私有 action（_ 前缀）
}

// ❌ 错误：store 字段大小写不一致
interface XxxStore {
  config: XxxConfig              // camelCase
  XxxConfig: XxxConfig           // ❌ PascalCase，与 config 不一致
  update_config: (patch: Partial<XxxConfig>) => void  // ❌ snake_case，应 updateConfig
}
```

**审查方法（前端命名变体 Grep 法）**：

```bash
# 步骤 1：提取所有 hooks 定义名
rg "export\\s+function\\s+(use\\w+)" frontend/src/hooks/ -r '$1' | sort -u

# 步骤 2：提取所有 Zustand store 字段名
rg "interface\\s+\\w+Store\\s*\\{[\\s\\S]*?\\}" frontend/src/stores/ -A 30 | rg "^\\s+(\\w+):" -r '$1'

# 步骤 3：Grep 全代码库搜索 hooks 引用变体
rg "use\\w+" frontend/src/pages/ frontend/src/components/ | sort -u | grep -i "usepersistent"

# 步骤 4：检查 store 字段大小写一致性
rg "\\w+Store\\s*<" frontend/src/ -A 5 | rg "[a-z]+_[a-z]+:"  # snake_case 字段
```

**适用场景**：
- 任何有自定义 hooks / store 字段的代码审查
- 跨组件 import hooks / store 的场景
- 重命名 hooks / store 字段后的回归检查

**不适用场景**：
- 组件内部局部变量（无跨组件访问）
- CSS class 命名（遵循 kebab-case 独立规范）

### 9.4 跨边界访问契约总原则（前端侧）

| 边界类型 | 契约要求 | 落地手段 |
|---|---|---|
| **后端 → 前端边界** | 后端 datetime 字段的时区状态（ISO 8601 with/without tz） | 后端返回 ISO 字符串 + 前端 `new Date(isoStr)` 显式解析 |
| **Hooks 边界** | hooks 内部状态的可访问性（public / private） | `_` 前缀私有 + 公共 hooks API 封装 |
| **Store 边界** | store 字段的可访问性（public / private） | `_` 前缀私有字段 + 公共 action 封装修改 |
| **组件 ref 边界** | ref 内部属性的可访问性 | `useImperativeHandle` 显式声明可暴露的方法 |
| **模块边界** | 导出 API 的稳定性（稳定 / 实验） | `export` 显式声明 + 公共 hooks docstring |

**核心原则**：**跨边界访问必须明确契约，不能依赖隐式约定**。

**审查 checklist**：
1. 是否存在渲染后端 datetime 字段？是否显式 `new Date()` 解析？
2. 是否存在跨组件访问 `_` 前缀 hooks/state？是否有公共 API 封装？
3. 是否存在跨组件引用 hooks / store 字段？命名是否与定义一致？
4. 是否存在父组件通过 ref 访问子组件内部状态？是否用 `useImperativeHandle` 显式声明？

---

## 10. 参考

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

---

## 12. API 数组防御与测试环境兼容（F-REVIEW-217 / 218 / 219）

> **复盘来源**：2026-07-22 React SPA 间歇性白屏修复复盘——5 类根因中 1 类与未保护的数据访问相关，3 类测试踩坑归入可测试性维度
> **配套规范**：[version-changelog.md §v4.59.0](./version-changelog.md)、`xianyu-hunter-dev` step 257 / 259-261 / meta-rule #95
> **配置节点**：`spa_white_screen_resilience.apiArrayDefense` / `spa_white_screen_resilience.vitestEnvChecklist` / `spa_white_screen_resilience.antdChineseButtonTestRegex`

### 12.1 API 响应数组字段防御性兜底（F-REVIEW-217）

| 规则 | 说明 |
|---|---|
| **API 数组字段使用前必须 `|| []` 兜底** | 维度 7，MAJOR；后端返回 null/undefined 时 `items[0]` 抛 TypeError 引发白屏 |
| **对象字段必须 `?.` 可选链** | 后端返回结构变更或部分字段缺失时避免 Cannot read property of undefined |
| **禁止裸访问 `res.items[0]` / `res.data.records[0]`** | 必须先 `const items = res.items || []` 再访问 |
| **适用字段名从 config 读取** | `arrayFieldPatterns` 列表：items / tables / list / records / data / results |

**判断信号**：

```bash
# 命中且无 || [] → MAJOR
grep -E "\b(res|data|response)\.(items|tables|list|records|data|results)\." frontend/src/
```

**修复模式**：

```typescript
// ❌ 反例：裸访问数组字段，res.items 为 null 时 TypeError 引发白屏
async function loadItems() {
  const res = await api.getItems()
  if (res.items.length > 0 && !selected) {
    setSelected(res.items[0].id)  // ❌ res.items 为 null/undefined 时崩溃
  }
}

// ✅ 正例：数组字段 || [] 兜底，对象字段 ?. 可选链
async function loadItems() {
  const res = await api.getItems()
  const items = res.items || []  // ✅ 防御性兜底
  if (items.length > 0 && !selected) {
    setSelected(items[0]?.id ?? '')  // ✅ 可选链 + 默认值
  }
}

// ✅ 正例：渲染层也必须兜底
function ItemList({ res }: { res: ApiResponse | null }) {
  const items = res?.items ?? []  // ✅ 可选链 + 空数组兜底
  return items.map(item => <Item key={item.id} {...item} />)
}
```

**适用场景**：所有 API 返回的数组字段、第三方 SDK 数据、`JSON.parse` 后数据。**不适用场景**：前端 useState 管理的数组（已初始化为 []）、常量数组、TypeScript 严格类型保证非 null 的字段。

### 12.2 Vitest 测试环境搭建检查清单（F-REVIEW-218）

| 规则 | 说明 |
|---|---|
| **运行测试前验证 vitest 可执行文件存在** | 维度 12，MAJOR；未安装时 `npx vitest run` 触发交互式安装提示卡死 |
| **vitest.config.ts 必须存在** | 配置 jsdom 环境与 setup 文件引用 |
| **src/test-setup.ts 必须存在** | 引入 `@testing-library/jest-dom` 与 antd 必要 mock（matchMedia 等） |
| **tsconfig.json 必须排除测试文件** | `exclude` 添加 `src/**/__tests__/**` 等模式，避免 `tsc --noEmit` 校验测试文件 |
| **禁止未验证 vitest 存在时直接 `npx vitest run`** | 交互式卡死，CI 必须先验证 |

**判断信号**：

```powershell
# vitest 可执行文件不存在 → MAJOR
Test-Path node_modules/.bin/vitest

# tsconfig 未排除测试文件 → MAJOR
Select-String -Path frontend/tsconfig.json -Pattern "__tests__"
```

**修复模式**：

```powershell
# 1. 安装依赖（一次性）
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom @testing-library/user-event
```

```typescript
// 2. frontend/vitest.config.ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    globals: true,
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
})
```

```typescript
// 3. frontend/src/test-setup.ts
import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// antd v5 依赖 matchMedia，jsdom 不提供，必须 mock
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}
```

```jsonc
// 4. frontend/tsconfig.json（必须排除测试文件，避免 tsc --noEmit 校验）
{
  "compilerOptions": { /* ... */ },
  "include": ["src/**/*"],
  "exclude": [
    "src/**/__tests__/**",
    "src/**/*.test.*",
    "src/**/*.spec.*"
  ]
}
```

**适用场景**：首次引入 vitest 的项目、CI 流水线运行前端测试。**不适用场景**：已稳定使用 jest 的项目、纯后端项目、无测试需求的项目。

### 12.3 antd 中文按钮测试断言兼容空格（F-REVIEW-219）

| 规则 | 说明 |
|---|---|
| **antd Button 中文文案测试断言必须用正则兼容空格** | 维度 12，MINOR；`getByRole('button', { name: /文\s*案/ })` |
| **禁止 `getByText('中文')` 断言 antd 中文 Button** | antd v5 Space.Compact 自动在中文字符间插入空格，渲染为 "文 案" |
| **适用范围含 Tag / Alert 等所有 antd 中文组件** | 任何受 Space.Compact 影响的中文文案组件 |
| **正则 `\s*` 同时匹配 0 个或多个空格** | 兼容 antd 不同版本/配置下空格数量的差异 |

**判断信号**：

```bash
# 命中 antd Button 相关 → MINOR
grep "getByText.*[\u4e00-\u9fa5]" frontend/src/**/__tests__/
```

**修复模式**：

```typescript
// ❌ 反例：getByText 精确匹配中文，antd 插入空格后找不到元素
test('renders retry button', () => {
  render(<RetryPanel />)
  expect(screen.getByText('重试')).toBeInTheDocument()  // ❌ 实际渲染为 "重 试"
})

// ✅ 正例 1：getByRole + 正则 \s* 兼容空格
test('renders retry button', () => {
  render(<RetryPanel />)
  expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument()
})

// ✅ 正例 2：Tag 中文文案同理
test('renders status tag', () => {
  render(<StatusPanel />)
  // Tag 文案 "已售出" 在 antd v5 下可能渲染为 "已 售 出"
  expect(screen.getByText(/已\s*售\s*出/)).toBeInTheDocument()
})
```

**根因说明**：antd v5 `Space.Compact` 与中文字符渲染时，浏览器/antd 会自动在相邻中文字符间插入空格（U+0020）以改善排版。`getByText('重试')` 是精确字符串匹配，无法匹配 "重 试"；`getByRole('button', { name: /重\s*试/ })` 通过正则 `\s*`（0 或多个空白字符）兼容这一行为。

**适用场景**：所有 antd v5 项目的中文按钮/Tag/Alert 测试。**不适用场景**：英文文案测试、非 antd 组件测试、antd v4 及以下版本（无此空格行为）。
