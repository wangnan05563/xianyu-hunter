# 前后端字段契约单一可信源（meta-rule #35）

> **元规范编号**：#35（v4.32.0 新增）
> **适用场景**：前后端分离架构中，任何跨网络边界传输的数据结构（HTTP body / query / path）
> **不适用**：纯前端单页、纯后端模板渲染、monorepo 共享 types（已有 typegen 工具）

---

## 一、问题背景

### 1.1 经典症状

> 前端 `NotificationItem` 接口字段 `read_at` 拼成 `readAt`（驼峰）→ 后端返回 `read_at`（snake_case）→ 前端永远读到 `undefined` → "标记已读"按钮点击无效。

**根因链条**：
1. 后端 `NotificationRow` 定义 `read_at: Mapped[str | None]`
2. 后端 Pydantic 响应模型 `NotificationItem(read_at: str | None)`
3. 前端 `types.ts` 手工复制 Pydantic 字段时**自己转成了驼峰** `readAt: string | null`
4. 前端 fetch 拿到 `read_at` 字段，前端代码读 `readAt` 永远是 `undefined`
5. 表现为"功能失效"，但代码不报错，测试通过

### 1.2 5 类典型漂移

| 漂移类型 | 现象 | 危害 |
|---|---|---|
| **命名风格漂移** | snake_case → camelCase | 字段读不到 |
| **大小写漂移** | `_session` vs `_Session` | Python `AttributeError` |
| **类型漂移** | 后端 `int` → 前端 `string` | 类型断言失败 |
| **可选性漂移** | 后端 `required` → 前端 `optional?` | 漏字段时无告警 |
| **枚举值漂移** | 后端 `succeeded` → 前端 `success` | 状态判断失效 |

---

## 二、单一可信源原则（Single Source of Truth, SSoT）

### 2.1 原则陈述

> **后端 Pydantic 模型 + DB Row 字段定义 = 权威源（Authoritative Source）**
>
> **前端 `types.ts` 必须显式标注派生来源，禁止无标注手工复制**

### 2.2 三种实现路径

| 路径 | 工具 | 适用 | 优缺点 |
|---|---|---|---|
| A. **后端生成前端 types** | `datamodel-code-generator` / `openapi-typescript` | 强类型优先、大团队 | ✅ 零漂移；❌ 需要 build 步骤 |
| B. **手工对齐 + 注释标注** | 人工 + 注释 | 快速迭代、小团队 | ✅ 灵活；❌ 易遗漏 |
| C. **共享 zod schema** | `zod` + 类型导出 | 前后端 TS/Node 栈 | ✅ 强校验；❌ 异构栈不适用 |

**本项目当前选 B（手工对齐 + 注释标注）**，但预留 A 路径的迁移接口。

### 2.3 字段声明模板（手工对齐）

```typescript
// frontend/src/api/types.ts

/**
 * 通知项
 *
 * 派生来源：src/xianyu_hunter/infra/db_models.py:NotificationRow
 *          + src/xianyu_hunter/web/routes/api_notifications.py:NotificationItem
 * Pydantic 字段：id / level / category / title / message / link /
 *                dedup_key / read_at / created_at
 * 变更日期：2026-07-06（初版）/ 待变更时同步更新
 *
 * 约束：
 * - snake_case 严格保留，禁止转 camelCase
 * - 后端返回 ISO 8601 字符串，前端用 new Date() 解析
 * - read_at 为 null 表示未读，非空表示已读时间
 */
export interface NotificationItem {
  id: number
  level: 'info' | 'warn' | 'err'
  category: 'order' | 'auth' | 'system' | 'config' | 'task'
  title: string
  message: string
  link?: string | null
  dedup_key: string
  read_at: string | null
  created_at: string
}
```

---

## 三、5 点追踪清单（字段变更时）

> 字段定义变更（新增/重命名/类型调整）必须按以下 5 点逐项检查：

| # | 追踪点 | 检查方式 | 责任人 |
|---|---|---|---|
| 1 | **DB Row 定义** | `db_models.py` 的 `Mapped[T]` 字段 | 后端 |
| 2 | **Pydantic 模型** | `web/routes/api_*.py` 的 `BaseModel` 字段 | 后端 |
| 3 | **后端返回路径** | `RepositoryBase._row_to_dict` 白名单 + 仓储 `_row_to_dto` | 后端 |
| 4 | **前端 types.ts** | `frontend/src/api/types.ts` 接口定义 | 前端 |
| 5 | **前端消费点** | `frontend/src/api/<域>.ts` 方法 + `pages/<域>/` 渲染 | 前端 |

> **强制要求**：任一字段变更必须 5 点全部更新；缺一即视为"契约未对齐"CRITICAL。

---

## 四、自动化校验脚本（v4.32.0 预留）

```python
# .trae/skills/xianyu-hunter-dev/scripts/check_contract.py (预留接口)
# 行为：对比后端 Pydantic 字段 vs 前端 types.ts 字段，输出 diff
# 当前未实现：因 Pydantic model 在运行时才构造，AST 解析复杂度高
# 推荐路径：迁移到路径 A（datamodel-code-generator）
```

---

## 五、配置节点

```yaml
# xianyu-frontend-code-review/config.yaml 的 contract_single_source 节点
# 前后端共用
contract_single_source:
  enabled: true
  # 当前实现路径：A / B / C
  current_path: "B"  # 手工对齐 + 注释标注
  # 路径 B 必备：types.ts 注释模板
  required_annotation_fields:
    - "派生来源"  # 必须标注后端文件路径+行号
    - "Pydantic 字段"
    - "变更日期"
    - "约束"
  # 字段变更 5 点追踪清单
  five_point_trace:
    - "db_models.py"          # DB Row
    - "web/routes/api_*.py"   # Pydantic
    - "infra/repository.py"   # _row_to_dict 白名单
    - "frontend/src/api/types.ts"  # 前端类型
    - "frontend/src/pages/*/"     # 前端消费
  # 命名约定
  naming_convention:
    backend: "snake_case"
    frontend: "snake_case"  # 严格透传，禁止转 camelCase
    url_path: "kebab-case"
    class_name: "PascalCase"
  # 类型映射白名单
  type_mapping:
    "int": "number"
    "str": "string"
    "bool": "boolean"
    "datetime": "string (ISO 8601)"
    "list[T]": "T[]"
    "dict[str, Any]": "Record<string, unknown>"
    "Optional[T]": "T | null"
```

---

## 六、判断信号（grep 优先）

| 信号 | 含义 | 违规判定 |
|---|---|---|
| `frontend/src/api/types.ts` 缺 `派生来源` 注释 | 手工对齐但未标注 | WARNING |
| 后端 Pydantic 字段 `xxx_yyy` + 前端 types.ts 字段 `xxxYyy` | 命名漂移 | CRITICAL |
| 后端新增字段，前端 types.ts 未同步 | 字段缺失 | CRITICAL |
| 前端 types.ts 字段标 `?` 但后端 Pydantic 标 `...` | 可选性漂移 | WARNING |
| 前端直接访问后端返回的 dict 用 `data['xxxYyy']`（驼峰） | 违反 snake_case 透传 | CRITICAL |

---

## 七、典型反模式（避免）

### 7.1 ❌ 反模式 1：手工复制后端模型

```typescript
// ❌ 错误：直接复制，未标注来源，未对齐
export interface Task {
  taskId: number  // 驼峰！
  taskName: string
  publishTime: string
}
```

### 7.2 ❌ 反模式 2：使用 any 绕过类型检查

```typescript
// ❌ 错误：any 抹掉所有约束
const task: any = await taskApi.get(id)
console.log(task.task_id)  // 字段名变更后无告警
```

### 7.3 ❌ 反模式 3：动态 key 取值

```typescript
// ❌ 错误：用字符串 key 取值，无法类型检查
const value = (task as Record<string, any>)['task_id']
```

### 7.4 ✅ 正模式

```typescript
// ✅ 正确：snake_case 透传 + 注释标注派生来源
/** 派生来源：src/xianyu_hunter/domain/task.py:Task */
export interface Task {
  task_id: number
  task_name: string
  publish_time: string  // ISO 8601
}

const task: Task = await taskApi.get(id)
console.log(task.task_id)  // 类型检查保护
```

---

## 八、不适用场景

| 场景 | 不适用原因 | 替代方案 |
|---|---|---|
| 纯前端单页（无后端） | 无契约问题 | 内部 state 用 zustand/yup 自管 |
| SSR（后端直接渲染） | 前后端共享模板 | 模板内嵌类型检查 |
| monorepo + 共享 types | 已 typegen | 信任 typegen 输出 |
| 第三方 API（不可控） | 无单一可信源 | 适配层 + 注释"外部 API 字段名" |
| 性能 hot path（极致优化） | 避免类型检查开销 | 用结构化 schema + 手工断言 |

---

## 九、与元规范 #33 / #34 的关系

- **#33 注册式资源三件套契约**：纵向 5 层齐备性（API wrapper 属于 L4）
- **#34 修复前全链路根因扫描协议**：横向 5 步根因扫描
- **#35 前后端字段契约单一可信源**：跨层字段对齐（本文档）

**完整流程**：
1. **新功能** → 用 #33 校验 5 层齐备性 + 用 #35 校验字段契约
2. **修复 bug** → 用 #34 根因扫描 + 用 #35 检查是否字段名漂移是根因之一
3. **字段重构** → 用 #35 5 点追踪清单逐项更新 + CI 校验

---

## 十、相关引用

- **元规范 #33**：注册式资源三件套契约（`registration-completeness.md`）
- **元规范 #34**：修复前全链路根因扫描协议（`root-cause-protocol.md`）
- **现有约束**：
  - F3 命名规范：snake_case 透传（参见 `编码规范.md` §四 命名一致性）
  - meta-rule #1：配置驱动原则
- **审查要点**：
  - 前端：`F-REVIEW-119 CONTRACT-SINGLE-SOURCE`（xianyu-frontend-code-review v4.36.0）
  - 后端：`B-REVIEW-161 CONTRACT-OWNER-MARKER`（xianyu-backend-code-review v4.31.0）
- **未来迁移**：路径 A（datamodel-code-generator）路线图
