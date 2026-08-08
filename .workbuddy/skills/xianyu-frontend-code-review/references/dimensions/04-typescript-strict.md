# 4. TypeScript 严格规范 🆕v2.0

- 【强制】`tsconfig.json` 严格配置（`strict: true`、`noFallthroughCasesInSwitch: true`、`isolatedModules: true`）
- 【强制】`moduleResolution: bundler`（Vite 兼容）
- 【强制】路径别名 `@/* → src/*`
- 【强制】`target: ES2020`，`jsx: react-jsx`（React 18 自动 runtime）
- 【强制】优先 `type` 而非 `interface`（项目规范）
- 【强制】字符串字面量联合而非 enum（如 `type TaskStatus = 'active' | 'paused' | 'stopped'`）
- 【强制】可选字段用 `?` 而非 `| undefined`
- 【禁止】使用 `any` 类型（SonarQube S4325），必要时用 `unknown` + 类型守卫
- 【强制】前后端字段类型对齐：`interface Task` 与后端 `TaskRow` 字段一致
- 【推荐】复杂类型用 `TypeAlias` 提升可读性

```typescript
// ✅ 推荐：字符串字面量联合 + type
type TaskStatus = 'active' | 'paused' | 'stopped'

// 禁止：enum（改用字符串字面量联合 + type）
```

- 🆕v4.11【强制】**F-REVIEW-STATE-ENUM-ALIGN：前后端状态枚举值对齐**
  - 业务对象有状态字段（如 `task.status` / `session.state` / `order.status`）时，前端 `types.ts` 必须导出与后端严格对齐的状态联合类型，**禁止**前端硬编码状态字符串
  - **核心机制**（审查时必须理解）：
    - 后端 Python `Enum` 或字符串常量定义的状态值，前端必须 1:1 对齐（包括大小写、下划线、空格）
    - 状态值变更（如后端 `paused` 改为 `suspended`）必须同步 grep 前端所有消费点（`types.ts` + 组件 + Hook + Store）并更新
    - 前端禁止用 `as TaskStatus` 强制类型转换绕过 TS 检查（会掩盖类型不匹配 bug）
  - **判断信号**：
    - `grep "status ===" frontend/src/` 发现硬编码字符串字面量（如 `status === 'running'`）而非引用常量 → 视为可疑
    - `types.ts` 中状态联合类型与后端 `domain/<名>.py` 的 `Enum` 成员不一致 → 视为违规
    - 后端新增状态值但前端 `types.ts` 未同步更新 → 视为违规
    - 前端代码含 `as TaskStatus` 强制类型转换 → 视为违规
  - **修复模式**（集中定义 + 引用常量 + 同步更新）：
    ```typescript
    // ✅ types.ts 集中导出，与后端 domain/task.py 的 TaskStatus 严格对齐
    export type TaskStatus = 'active' | 'paused' | 'stopped' | 'completed' | 'failed'
    export const TASK_STATUS_VALUES = ['active', 'paused', 'stopped', 'completed', 'failed'] as const
    // 消费方引用常量，禁止硬编码字符串
    if (task.status === 'completed') { ... }  // ✅ 字面量受联合类型保护
    ```
  - **配置参数**：`status_fields`（需要状态对齐的字段列表，如 `['task.status', 'session.state', 'order.status']`）、`forbid_as_cast`（默认 `true`，禁止 `as TaskStatus` 强制转换）、`sync_check_dirs`（同步检查目录，默认 `['frontend/src/', 'src/xianyu_hunter/domain/']`）在 `config.yaml` 的 `state_enum_align` 节点管理
  - **适用**：所有有状态字段的业务对象（任务/会话/订单/评估）；后端用 Enum 或常量定义状态值的场景
  - **不适用**：纯前端 UI 状态（如 `loading` / `open` / `active`）；无状态机的 CRUD 实体（如配置项）
  - **历史教训**：后端 `task.status` 新增 `suspended` 状态但前端 `types.ts` 仍为 `'active' | 'paused' | 'stopped'`，导致前端收到 `suspended` 状态时 TypeScript 不报错（因为用了 `as TaskStatus` 转换），UI 显示为默认的"未知状态"。修复后 `types.ts` 同步新增 `suspended` + 移除所有 `as TaskStatus` 转换 + grep 所有消费点确认

- 🆕v4.12【强制】**F-REVIEW-INPUT-NUMBER-BOUNDS：InputNumber 边界约束**
  - `<InputNumber>` 组件必须设置 `min` 和 `max` 属性，禁止无边界输入导致 0/负数传入后端触发 ZeroDivisionError 或负数索引导致越界
  - **核心机制**（审查时必须理解）：
    - AntD InputNumber 默认无 min/max，用户可输入任意数值（包括 0、负数、极大值）
    - 后端配置项通常无边界校验（参考 B-REVIEW-CONFIG-VALIDATION），前端必须兜底
    - 0 值传入 `interval / N` 会触发 ZeroDivisionError；负数传入数组索引会导致 undefined
  - **判断信号**：
    - 代码含 `<InputNumber` 但无 `min=` 属性 → 视为违规
    - 代码含 `<InputNumber min={0}` 但实际语义要求 `min={1}`（如间隔时间、重试次数）→ 视为违规
    - 配置项含 `interval` / `count` / `retry` 等数值字段但前端 InputNumber 无边界 → 视为违规
  - **修复模式**：
    ```typescript
    // ✅ 间隔时间类（必须 min=1，禁止 0/负数）
    <InputNumber min={1} max={3600} addonAfter="秒" value={interval} onChange={setInterval} />

    // ✅ 重试次数类（必须 min=0，允许 0 表示不重试）
    <InputNumber min={0} max={10} value={retryCount} onChange={setRetryCount} />

    // 禁止：无 min 边界，用户可输入 0/负数
    ```
  - **配置参数**：`input_number_bounds.required_min`（默认 `true`，必须有 min）、`input_number_bounds.required_max`（默认 `true`，必须有 max）、`input_number_bounds.scenario_min_values`（场景到 min 值的映射，如 `interval → 1`、`retry_count → 0`、`page_size → 1`）在 `config.yaml` 的 `input_number_bounds` 节点管理
  - **适用**：所有 `<InputNumber>` 组件；配置页面数值字段；表单数值输入
  - **不适用**：纯展示型数值（disabled InputNumber）；无业务语义的数值（如 ID 输入，应用其他校验）
  - **历史教训**：配置页 `<InputNumber>` 无 min 边界，用户输入 `ai_suggestion_interval=0`，后端 `asyncio.sleep(interval / 2)` 触发 ZeroDivisionError，任务循环崩溃

- 🆕v4.12【强制】**F-REVIEW-NULL-SEMANTICS：null/undefined/空字符串语义区分**
  - TypeScript 类型必须明确区分 `null`（显式空值）、`undefined`（未定义）、`""`（空字符串）三种语义。**禁止** `value: string` 实际可能为 null 的类型欺骗，**禁止** `value: string | null` 但代码用 `if (value)` 同时判断三种语义
  - **核心机制**（审查时必须理解）：
    - `null`：显式表示"无"（后端返回 null）
    - `undefined`：变量未初始化或属性不存在
    - `""`：空字符串（用户主动输入空）
    - 后端 JSON 返回 `null` → 前端解析为 `null`（非 undefined）；API 字段缺失 → 前端为 `undefined`
    - `if (value)` 同时判断三种语义会导致逻辑混乱（如 `""` 被视为 falsy 但实际是有效输入）
  - **判断信号**：
    - 类型声明 `value: string` 但后端 API 可能返回 `null` → 视为违规（应为 `value: string | null`）
    - 代码含 `if (value)` 判断 string 类型 → 必须明确区分 `value === null` / `value === undefined` / `value === ""`
    - 代码含 `value ?? defaultValue` 但 `""` 应保留而非替换为默认值 → 视为违规（应用 `value ?? defaultValue` 仅在 null/undefined 时替换，""保留）
  - **修复模式**：
    ```typescript
    // ✅ 类型明确区分三种语义
    type TaskStatus = {
      name: string                    // 必有，非空字符串
      description: string | null      // 可能为 null（后端显式返回 null）
      deletedAt: string | null        // null 表示未删除
      parentTaskId?: string           // 可选属性，未传时为 undefined
    }

    // ✅ 判断时明确区分
    if (description === null) {
      // 后端显式返回 null，表示"无描述"
      return '无描述'
    }
    if (description === '') {
      // 空字符串，用户主动输入空
      return '（空）'
    }
    return description

    // 禁止：if (value) 同时判断三种语义（"" 也被显示为"无描述"，语义错误）
    ```
  - **配置参数**：`null_semantics.strict_mode`（默认 `true`，严格区分三种语义）、`null_semantics.forbidden_union_types`（禁止的联合类型列表，如 `["string | null | undefined"]` 应用 `string | null` + 可选属性）、`null_semantics.if_check_pattern`（检测 `if (value)` 同时判断 string 类型的模式）在 `config.yaml` 的 `null_semantics` 节点管理
  - **适用**：所有 TypeScript 类型声明；后端 API 返回字段的类型定义；表单字段的类型与判断逻辑
  - **不适用**：纯前端计算字段（无 null 语义）；布尔类型（true/false 已明确）
  - **历史教训**：API 返回 `parentTaskId: null` 但前端类型声明为 `parentTaskId?: string`，代码用 `if (task.parentTaskId)` 判断导致 null 被视为 falsy 与 undefined 行为一致，但实际语义不同（null 表示"曾有父任务但已解除" vs undefined 表示"从未有父任务"）

- 🆕v4.25【建议】**F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY：默认值操作符一致性检查**
  - 维度归属：TypeScript 严格规范
  - 严重等级：info
  - **检查点**：默认值场景是否统一使用 `??` 而非 `||`
  - **判定标准**：InputNumber/Select 的 `onChange` 默认值必须用 `??`（nullish coalescing）。`||` 会将 `0`/`''`/`false` 也视为 falsy，可能导致意外行为（如 qps=0 被替换为默认值 1）。只有需要同时过滤 `0`/`''`/`false` 的场景才允许用 `||`
  - **检查范围**：所有 `onChange` 中的默认值表达式、函数参数默认值、变量初始化
  - **核心机制**（审查时必须理解）：
    - `??` 仅在左侧为 `null`/`undefined` 时返回右侧值（语义清晰：缺失时给默认）
    - `||` 在左侧为任意 falsy 值（`null`/`undefined`/`0`/`''`/`false`/`NaN`）时返回右侧值（语义模糊：可能误伤合法的 0/''/false）
    - 数值类字段（qps、interval、timeout、retryCount）的 `0` 是合法值，不能用 `||` 替换为默认值
    - 字符串类字段（label、description）的 `''` 是合法值（用户主动清空），不能用 `||` 替换为默认值
    - 布尔类字段（enabled、silent）的 `false` 是合法值，不能用 `||` 替换为默认值
  - **判断信号**（grep 检测）：
    - `grep -nE "onChange=\{\(v\) => .* \|\| " frontend/src/pages/**/*.tsx` 命中 → 检查是否应改为 `??`
    - `grep -nE "value \|\| [0-9]+" frontend/src/pages/**/*.tsx` 命中 → 数值默认值场景必查
    - `grep -nE "const \w+ = \w+ \|\| '" frontend/src/pages/**/*.tsx` 命中 → 字符串默认值场景必查
    - 用户反馈"qps=0 无法保存，被强制改为 1" → 必查 `||` 误用
  - **修复模式**：
    ```typescript
    // ✅ 正确：数值默认值用 ??，0 是合法值
    <InputNumber onChange={(v) => update({ qps: v ?? 1 })} />

    // 禁止：用 || 会把 0 也视为 falsy，qps=0 被替换为 1

    // ✅ 正确：字符串默认值用 ??，'' 是合法值（用户主动清空）
    const label = formData.label ?? '默认标签'

    // 禁止：用 || 会把 '' 也视为 falsy，用户清空后被强制改回默认值
    // ✅ 例外：需要同时过滤 0/''/false 时允许用 ||
    const displayName = user.nickname || user.username || '匿名'  // 空字符串视为"未设置"
    ```
  - **配置参数**：`default_operator` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `preferred_operator`（默认 `"??"`，推荐使用的默认值操作符）
    - `logical_or_exceptions`（默认 `["displayName = nickname || username", "fallback chain"]`，允许使用 `||` 的场景白名单）
    - `detection_patterns`（默认 `["onChange={(v) => ... || ", "value || 0", "value || ''"]`，触发检查的代码模式）
    - `forbidden_in_numeric_context`（默认 `true`，数值类字段禁止用 `||`）
    - `forbidden_in_string_context`（默认 `true`，字符串类字段禁止用 `||`）
    - `forbidden_in_boolean_context`（默认 `true`，布尔类字段禁止用 `||`）
  - **适用场景**：所有提供默认值的表达式（onChange 默认值、变量初始化、函数参数默认值、对象属性默认值）
  - **不适用场景**：需要同时过滤 `0`/`''`/`false` 的场景（如空字符串转默认值的 fallback 链、用户昵称缺失时回退到用户名）；布尔条件判断（`if (a || b)` 是逻辑或，不是默认值）；React 组件条件渲染（`{a || <Fallback/>}` 是逻辑或渲染）
  - **历史教训**：任务级配置覆盖功能开发时，`InputNumber` 的 `onChange` 用 `v || 1`，导致用户输入 0 时被强制改为 1（qps=0 是合法值，表示"不限制速率"）。修复方式：改为 `v ?? 1`，仅在 v 为 null/undefined（用户未输入）时给默认值 1
  - **对应后端原则**：后端 Python 使用 `or` 时同样存在类似问题（`0`/`''`/`False` 为 falsy），详见 `xianyu-backend-code-review` 的 `B-REVIEW-DEFAULT-OPERATOR`（如有）
