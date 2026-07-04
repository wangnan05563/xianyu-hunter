---
name: xianyu-frontend-code-review
description: "对闲鱼猎人项目前端代码（React/TypeScript/Ant Design/Zustand）进行全面评审及逻辑审查，涵盖类型安全、业务逻辑、Zustand 状态管理、API 契约、Hooks 设计、性能优化、可访问性、可测试性、认证规范。调用时机：用户要求评审前端代码、审查 .tsx/.ts 文件修改、迭代发布前前端代码走查，或提到 '前端评审'、'frontend review'、'React 代码审查' 等关键词时。"
---

# xianyu-frontend-code-review

> **范围**：`frontend/src/**/*.tsx` + `frontend/src/**/*.ts`
> **技术栈**：React 18 + TypeScript 5 + Vite 5 + Ant Design 5 + Zustand 4 + Axios
> **审查模式**：pending-change（审查未提交改动）/ file-focused（审查指定文件）
> **配套技能**：[xianyu-hunter-dev](../xianyu-hunter-dev/SKILL.md) 提供编码规范来源

---

## When to use this skill

✅ 触发时机：
- 用户要求"评审前端代码" / "前端代码走查" / "code review 前端"
- 修改了 `frontend/src/**` 下任何文件后做发布前审查
- 涉及 Ant Design 组件、Zustand store、Axios 调用的修改
- 跨页面 / 跨 store 的联动改动

❌ 不适用：
- 纯样式 / 视觉调整（用 `xianyu-hunter-dev` + `docs/standards/michelin-design-system.md`）
- 后端代码（用 `xianyu-backend-code-review`）
- 配置文件 / 文档（不在代码审查范围）

---

## How to use this skill

按以下步骤执行审查：

1. **确定审查模式**（pending-change / file-focused）
2. **识别审查范围**（用 `git diff` 或用户指定的文件）
3. **按 §2 审查维度逐项检查**
4. **查阅 references/** 对应专题：
   - [references/code-quality.md](references/code-quality.md) —— 类型 / 命名 / 注释
   - [references/performance.md](references/performance.md) —— 重渲染 / memo / 列表
   - [references/business-logic.md](references/business-logic.md) —— 业务逻辑正确性
   - [references/api-contract.md](references/api-contract.md) —— API 契约 / 错误处理
   - [references/hooks-and-state.md](references/hooks-and-state.md) —— Hooks / Zustand 用法
   - [references/security-and-a11y.md](references/security-and-a11y.md) —— 安全 / 可访问性
   - [references/antd-patterns.md](references/antd-patterns.md) —— antd 5 关键模式审查
5. **按 §4 模板输出审查报告**

---

## §1 审查原则

| 原则 | 说明 |
|---|---|
| **代码即文档** | 命名 + 注释必须自解释 |
| **业务正确性优先** | 类型 / 性能问题都让位于业务 Bug |
| **改动局部化** | 评估影响范围，避免引入"未来风险" |
| **审查可执行** | 每个 finding 必须能对应到一个修改动作 |
| **优先级分层** | Critical（必修）> Suggestion（应改）> Nit（可选）|

---

## §2 审查维度（8 个）

### 2.1 类型安全（Code Quality · 类型）

| 编号 | 规则 | 严重度 |
|---|---|---|
| TS-01 | 禁止 `any` 类型（必须用 `Record<string, unknown>` / 泛型） | Critical |
| TS-02 | 函数参数和返回值必须有显式类型（避免依赖推断） | Suggestion |
| TS-03 | `useState` 初始值类型显式 | Suggestion |
| TS-04 | API 响应使用统一类型（`api/types.ts`）禁止内联 | Critical |
| TS-05 | 可选字段用 `?:` 不混用 `\| null` | Nit |
| TS-06 | 枚举值用 `as const` 或 `enum`，禁止 magic string | Suggestion |
| TS-07 | `strictNullChecks` 必须开 | Critical |

### 2.2 业务逻辑（Business Logic）

| 编号 | 规则 | 严重度 |
|---|---|---|
| BL-01 | 字段命名与后端 snake_case 完全一致（不做大小写转换） | Critical |
| BL-02 | 保存前做客户端校验（必填 / 范围 / 依赖关系） | Critical |
| BL-03 | 提交后刷新本地 store（不要只更新 UI） | Critical |
| BL-04 | 错误状态可恢复（用户能重试） | Suggestion |
| BL-05 | 边界条件（空数组 / 0 / undefined）显式处理 | Suggestion |
| BL-06 | 业务约束在 UI 体现（如 `pass_score <= auto_buy_score`） | Suggestion |
| BL-07 | 副作用（alert / confirm）最小化 | Nit |
| BL-08 | 用户输入不直接信任（XSS、SQL 注入） | Critical |

### 2.3 Zustand 状态管理

| 编号 | 规则 | 严重度 |
|---|---|---|
| ZS-01 | **不订阅整个 store**（必须 selector 字段订阅） | Critical |
| ZS-02 | Action 命名规范（loadXxx / saveXxx / updateField / reset） | Suggestion |
| ZS-03 | 不在 store 外修改 state（必须通过 action） | Critical |
| ZS-04 | 异步 action 抛错而非吞错 | Critical |
| ZS-05 | 状态拆分到独立字段（不存整个大对象当 state） | Suggestion |
| ZS-06 | 状态持久化策略明确（哪些用 localStorage 哪些用 session） | Suggestion |
| ZS-07 | 跨 store 数据通过 selector 组合 | Suggestion |

### 2.4 API 契约

| 编号 | 规则 | 严重度 |
|---|---|---|
| API-01 | 所有 catch 块用 `extractApiError(e)` | Critical |
| API-02 | message 失败提示持续时间 ≥ 5 秒 | Critical |
| API-03 | API 路径在 `api/` 模块集中管理 | Suggestion |
| API-04 | 请求 / 响应有 TypeScript 类型 | Critical |
| API-05 | HTTP 方法语义正确（GET 幂等 / POST 写） | Suggestion |
| API-06 | 401 / 403 / 500 统一处理（拦截器） | Critical |
| API-07 | 长时间请求有 loading 状态 | Suggestion |
| API-08 | 重试 / 取消 / 超时有处理 | Suggestion |
| API-09 | 敏感数据（cookie / token）不在前端硬编码 | Critical |

### 2.5 Hooks 设计

| 编号 | 规则 | 严重度 |
|---|---|---|
| HK-01 | `useEffect` 依赖数组完整 | Critical |
| HK-02 | 副作用清理函数（`return () => {...}`） | Suggestion |
| HK-03 | 不用 `useEffect` 同步状态（用派生 state） | Suggestion |
| HK-04 | `useMemo` / `useCallback` 用于重计算或透传 | Suggestion |
| HK-05 | 自定义 hook 命名 `useXxx` | Nit |
| HK-06 | hook 不在条件 / 循环中调用 | Critical |
| HK-07 | 复杂逻辑提取到自定义 hook | Suggestion |

### 2.6 性能（Performance）

| 编号 | 规则 | 严重度 |
|---|---|---|
| PF-01 | 大列表用虚拟滚动（Ant Design `Virtual`） | Suggestion |
| PF-02 | 列表 `key` 用业务 ID（不用 index） | Critical |
| PF-03 | 重组件用 `React.memo` 包装 | Suggestion |
| PF-04 | 事件回调用 `useCallback` 稳定引用 | Suggestion |
| PF-05 | 大数据表格分页 / 懒加载 | Suggestion |
| PF-06 | 路由级代码分割（`React.lazy`） | Suggestion |
| PF-07 | 图片懒加载（`loading="lazy"`） | Nit |
| PF-08 | Debounce / Throttle 频繁触发 | Suggestion |

### 2.7 安全 & 可访问性（Security & A11y）

| 编号 | 规则 | 严重度 |
|---|---|---|
| SC-01 | 用户输入用 dangerouslySetInnerHTML 必须 sanitise | Critical |
| SC-02 | 敏感数据（cookie / API key）不写日志 | Critical |
| SC-03 | URL 参数 / hash 不存敏感信息 | Critical |
| SC-04 | XSS 防护（用户输入展示前 escape） | Critical |
| SC-05 | 所有可点击元素 keyboard 可达 | Suggestion |
| SC-06 | 表单字段有关联 `<label>` | Suggestion |
| SC-07 | ARIA 属性正确（`aria-label` / `aria-describedby`） | Nit |
| SC-08 | 颜色对比度满足 WCAG AA | Suggestion |
| SC-09 | 错误状态有 `role="alert"` | Suggestion |

### 2.8 框架特定模式

| 编号 | 规则 | 严重度 |
|---|---|---|
| FP-01 | antd 5 组件使用模式（Modal.update / Menu路径守卫 / 表格中文标注 / 路由同步）[references/antd-patterns.md](references/antd-patterns.md) | Critical |

---

## §3 项目特定审查要点

### 3.1 配置管理页面（`pages/Config/*.tsx`）

| 编号 | 规则 |
|---|---|
| CFG-01 | 必有"重置"按钮恢复默认 |
| CFG-02 | 保存前显示 diff 预览（`DiffPreviewModal`） |
| CFG-03 | 数值输入有 min / max 限制 |
| CFG-04 | 修改未保存时离开页面有提示 |
| CFG-05 | 业务约束（`pass_score <= auto_buy_score`）UI 提示 |

### 3.2 抢单决策相关页面

| 编号 | 规则 |
|---|---|
| BUY-01 | 显示"auto 模式"风险提示 |
| BUY-02 | 数值变更实时校验（不依赖后端） |
| BUY-03 | 配合"评估规则"页面的联动说明 |
| BUY-04 | 修改后无需重启的明确说明 |

### 3.3 表格 / 列表页

| 编号 | 规则 |
|---|---|
| TBL-01 | 表格列定义集中（`columns.tsx` 或 `getColumns()`） |
| TBL-02 | 分页 / 排序 / 筛选有明确交互 |
| TBL-03 | 批量操作有确认 |
| TBL-04 | 空状态有友好提示 |

---

## §4 输出模板

### 4.1 有问题（Template A）

```markdown
# Frontend Code Review

Found <X> critical issues need to be fixed:

## 🔴 Critical (Must Fix)

### 1. <brief description>

**FilePath**: <path> line <line>
<相关代码片段或指针>

**问题**：
- 具体违反的规则编号（如 TS-01 / API-01 / ZS-01）
- 影响范围（哪些用户 / 哪些场景会触发）

**Suggested Fix**：
1. <具体修改步骤>
2. <代码示例（可选）>

---

... (重复每个 critical issue) ...

Found <Y> suggestions for improvement:

## 🟡 Suggestions (Should Consider)

### 1. <brief description>

**FilePath**: <path> line <line>
<相关代码片段或指针>

**Suggested Fix**：
1. ...

---

Found <Z> optional nits:

## 🟢 Nits (Optional)

### 1. <brief description>

**FilePath**: <path> line <line>

**Suggested Fix**：
- <minor suggestions>

---

## ✅ What's Good

- <值得肯定的实现>
```

### 4.2 无问题（Template B）

```markdown
# Frontend Code Review

✅ No issues found. 当前实现符合本项目前端编码规范。
```

### 4.3 输出规则

- **优先按严重度排序**：Critical → Suggestion → Nit
- **同类问题聚合**：如多页面都有同样 catch 笼统提示，合并为一个 finding 并列文件清单
- **每条 finding 包含**：路径 + 行号 + 规则编号 + 修复建议
- **超过 10 条同类问题**："Found 10+ <category> issues, only showing first 10"
- **末尾必须询问**："需要我直接应用这些修复吗？"

---

## §5 审查流程（详细）

### Step 1: 收集变更

```bash
# pending-change 模式
git diff frontend/src/

# file-focused 模式
# 用户直接指定文件路径
```

### Step 2: 分类标记

按 `§2` 维度分类：
- 类型安全
- 业务逻辑
- Zustand 状态
- API 契约
- Hooks
- 性能
- 安全 / A11y

### Step 3: 逐项检查

每条规则对照代码，按 Critical / Suggestion / Nit 分级。

### Step 4: 聚合输出

按模板输出，**每条 finding 至少包含**：
- 规则编号（便于追溯到 §2 规则表）
- 文件路径 + 行号
- 影响说明
- 修复建议（具体可执行）

### Step 5: 应用修复（可选）

如用户确认修复，按"先 Critical 后 Suggestion"顺序批量修改。

---

## §6 不审查什么

- ❌ 视觉 / 颜色 / 间距（用设计系统规范）
- ❌ 拼写错误（IDE linter 处理）
- ❌ Import 排序（prettier 处理）
- ❌ 测试代码（除非影响主逻辑）
- ❌ 文档 / 注释内容

---

## §7 常用检查脚本

```bash
# TypeScript 类型检查
cd frontend && npx tsc --noEmit

# ESLint
cd frontend && npx eslint src/ --ext .ts,.tsx

# Prettier 检查
cd frontend && npx prettier --check src/

# 单元测试
cd frontend && npm test
```

---

## §8 复盘：从对话中提炼的关键模式

### 8.1 反模式 1：catch 块笼统提示

**复盘案例**：抢单策略页面保存失败时只显示"预览失败"

**反模式代码**：
```tsx
try {
  await previewSave()
  setDiffChanges(changes)
  setDiffModalOpen(true)
} catch {
  message.error('预览失败')  // ❌ 用户不知道哪里错了
}
```

**正确模式**：
```tsx
import { extractApiError } from '@/utils/apiError'

try {
  await previewSave()
  setDiffChanges(changes)
  setDiffModalOpen(true)
} catch (e) {
  message.error(extractApiError(e), 5)  // ✅ 显示具体校验错误
}
```

**预防机制**：所有 catch 块用 lint 规则强制 `extractApiError`（可在 CI 中加 ESLint 规则）。

### 8.2 反模式 2：整个 store 订阅

**反模式代码**：
```tsx
const store = useConfigStore()  // ❌ 任何字段变都重渲染
return <div>{store.config.eval.auto_buy_score}</div>
```

**正确模式**：
```tsx
const autoBuyScore = useConfigStore(s => s.config?.eval?.auto_buy_score)
// ✅ 只有 auto_buy_score 变才重渲染
```

**预防机制**：Code Review 时重点检查 `useStore()` 形式。

### 8.3 反模式 3：snake_case 大小写转换

**反模式代码**：
```tsx
// 前端转 camelCase
const camelPayload = Object.fromEntries(
  Object.entries(payload).map(([k, v]) => [camelCase(k), v])
)
// ❌ 后端校验时找不到字段
```

**正确模式**：
```tsx
// snake_case 透传
const save = await configApi.save(payload)  // payload 用 snake_case
```

**预防机制**：types.ts 集中定义，后端字段名不能改。

---

## §9 与其他技能协同

```
用户请求前端代码评审
    ↓
xianyu-frontend-code-review（本技能）
    │
    ├── 编码规范依据 ──→ docs/skills/xianyu-hunter-dev/references/coding-standards.md
    │
    ├── 类型 / 命名 / 注释 ──→ references/code-quality.md
    │
    ├── 性能 / 重渲染 ──→ references/performance.md
    │
    ├── 业务逻辑 ──→ references/business-logic.md
    │
    ├── API 契约 ──→ references/api-contract.md
    │
    ├── Hooks / Zustand ──→ references/hooks-and-state.md
    │
    └── 安全 / 可访问性 ──→ references/security-and-a11y.md
```

---

## References

- [references/code-quality.md](references/code-quality.md)
- [references/performance.md](references/performance.md)
- [references/business-logic.md](references/business-logic.md)
- [references/api-contract.md](references/api-contract.md)
- [references/hooks-and-state.md](references/hooks-and-state.md)
- [references/security-and-a11y.md](references/security-and-a11y.md)
- [references/antd-patterns.md](references/antd-patterns.md) —— antd 5 关键模式审查
