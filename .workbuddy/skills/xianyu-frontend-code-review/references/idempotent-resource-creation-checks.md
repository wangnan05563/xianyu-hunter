# 资源创建幂等性与前端状态闭环检查点详情

> **版本**：v4.63.0（2026-07-25 第八轮复盘落地）
> **维度**：47 资源创建幂等性与前端状态闭环
> **关联复盘**：`xianyu-hunter-dev/references/retrospective-2026-07-25-r2.md`（第八轮复盘）
> **关联规范**：`xianyu-hunter-dev` 规范 31（资源创建接口幂等性设计）+ 规范 32（前端 async handler 三分支完整性）
> **后端联动**：`xianyu-backend-code-review` v4.64.0 B-REVIEW-313~315（资源创建幂等性 / OperationResult 契约 / 前端状态刷新闭环后端侧）
> **auto-testing 联动**：`xianyu-auto-testing` 模式 AA（资源创建幂等性与状态闭环回归测试）

---

## F-REVIEW-233 ASYNC-HANDLER-THREE-BRANCH 前端 async handler 三分支完整性

- **维度**：47 资源创建幂等性与前端状态闭环
- **严重等级**：CRITICAL（P0）
- **规范引用**：`xianyu-hunter-dev` 规范 32（前端 async handler 三分支完整性）
- **后端联动**：B-REVIEW-313 IDEMPOTENT-RESOURCE-CREATION（互补）

### 检查点

前端 `async` 事件 handler（`onClick` / `onSubmit` / `onFinish` 等触发网络请求的函数）的 `try/catch/else` 三分支必须同时满足：

1. **success 分支**（`try` 内 `await` 后）：必须显式调用 `loadXxx()` / `refreshXxx()` / `mutateXxx()` 刷新与该操作相关的所有 UI 状态，避免 UI 与后端状态不一致
2. **else 分支**（`if (!resp.ok)` / `if (resp.ok === false)`）：必须显示具体错误（来自后端 `error` / `detail` / `message` 字段），禁止显示固定失败文案；同时必须调用 `loadXxx()` 刷新状态（因为后端可能已实际生效，仅响应标志误报失败）
3. **catch 分支**（`catch (e)`）：必须显示网络/解析错误（用 `extractApiError(e)` 或 `e.message`），同时必须调用 `loadXxx()` 刷新状态

### 判断信号

```bash
# 1. 定位所有 async handler
grep -rn "const handle.* = async\|async (e) =>\|async (values)" frontend/src/ --include="*.tsx" --include="*.ts"

# 2. 检查 success 分支是否调用 loadXxx
grep -rn "await.*api\.\|await.*axios\." frontend/src/ --include="*.tsx" --include="*.ts"
# 后接 loadXxx() 调用 → 通过；缺失 → 违规

# 3. 检查 else 分支是否显示固定失败文案
grep -rn "message\.error('启动失败')\|message\.error('操作失败')\|notification\.error({ message: '失败'" frontend/src/ --include="*.tsx"
# 固定文案无 resp.error 字段 → 违规

# 4. 检查 catch 分支是否调用 loadXxx
grep -rn "catch.*\b(e\|err\|error)\b" frontend/src/ --include="*.tsx" --include="*.ts" -A 5
# catch 块只有 message.error 无 loadXxx → 违规
```

### 反模式

```typescript
// ❌ 反模式：else 分支显示固定文案且不刷新状态
const handleStartSession = async () => {
  try {
    const resp = await startSession();
    if (resp.ok) {
      message.success('启动成功');
      loadSession();  // 只有 success 才刷新
    } else {
      message.error('启动会话失败');  // ❌ 固定文案 + 不刷新状态
    }
  } catch (e) {
    message.error('启动失败');  // ❌ 无具体错误 + 不刷新状态
  }
};
```

### 正确模式

```typescript
// ✅ 正确模式：三分支都显示具体错误 + 都调用 loadSession()
const handleStartSession = async () => {
  try {
    const resp = await startSession();
    if (resp.ok) {
      // success：已启动 / already_active 两种情况都视为成功
      message.success(resp.already_active ? '会话已处于活跃状态' : '启动成功');
    } else {
      // else：显示后端返回的具体 error 字段
      message.error(resp.error || '启动失败，请查看日志');
    }
  } catch (e) {
    // catch：显示网络/解析错误的原始 message
    message.error(extractApiError(e));
  } finally {
    // 三分支统一刷新状态（即使响应标志失败，后端可能已实际生效）
    await loadSession();
  }
};
```

### 配置参数

`config.yaml#idempotent_resource_creation_frontend.async_handler_three_branch` 节点：

- `enabled`（默认 true）
- `severity`（默认 CRITICAL）
- `require_load_in_all_branches`（默认 true，三分支都必须调用 loadXxx）
- `require_specific_error_in_else`（默认 true，else 分支禁止固定文案）
- `require_extract_api_error_in_catch`（默认 true，catch 分支必须用 extractApiError）
- `handler_patterns`（默认 `["handleStart", "handleStop", "handleCreate", "handleUpdate", "handleDelete", "handleResume", "handlePause"]`）
- `refresh_function_patterns`（默认 `["load", "refresh", "mutate", "refetch"]`）

### 适用场景

- 所有触发网络请求的前端 `async` 事件 handler（`onClick` / `onSubmit` / `onFinish` / `onChange` 触发写操作）
- 资源创建/启动/停止/恢复类按钮的 onClick handler
- 表单提交的 onFinish handler

### 不适用场景

- 纯查询的 `loadXxx` 函数（本身就是刷新函数，不需要再刷新）
- 不发起网络请求的本地状态变更（如切换 Modal 显示）
- 防抖/节流的中间函数（最终调用方仍需满足三分支要求）

### 历史教训

反爬登录管理系统 `handleStartSession` 的 else 分支显示固定文案 "启动会话失败" 且不调用 `loadSession()`，而后端 `trigger_session_start()` 已通过 fire-and-forget 自动启动会话，导致用户看到"失败"提示但 UI 状态显示"已启动"的矛盾现象（详见 `xianyu-hunter-dev/references/retrospective-2026-07-25-r2.md` 第八轮复盘 F37）。

---

## F-REVIEW-234 API-RETURN-TYPE-CONTRACT API 函数返回类型契约

- **维度**：47 资源创建幂等性与前端状态闭环
- **严重等级**：HIGH（P1）
- **规范引用**：`xianyu-hunter-dev` 规范 31（资源创建接口幂等性设计）+ 维度 11 类型契约对齐
- **后端联动**：B-REVIEW-314 OPERATION-RESULT-CONTRACT（互补）

### 检查点

前端 API 函数（`frontend/src/api/*.ts` 中的请求封装）返回类型必须与后端响应模型 1:1 对齐，并满足：

1. **资源创建类 API**（`startSession` / `createXxx` / `registerXxx` / `launchXxx`）的返回类型必须使用 `OperationResult` 接口，包含：
   - 必填字段：`ok: boolean`
   - 幂等标志字段：`already_active?: boolean` / `already_exists?: boolean`
   - 错误字段：`error?: string` / `error_code?: string` / `detail?: string`
   - 消息字段：`message?: string`
2. **类型字段必须显式声明**，禁止用 `any` / `unknown` / `Promise<any>` 兜底
3. **新增字段同步**：后端响应新增字段时，前端类型定义必须同步声明（与 B-REVIEW-315 联动）
4. **废弃字段同步**：后端字段废弃时，前端必须同步移除消费逻辑

### 判断信号

```bash
# 1. 查找资源创建类 API
grep -rn "export async function start\|export async function create\|export async function register\|export async function launch" frontend/src/api/

# 2. 检查返回类型
grep -rn "Promise<any>\|Promise<unknown>" frontend/src/api/
# 资源创建类 API 返回 any → 违规

# 3. 检查 OperationResult 接口是否包含 already_active
grep -rn "interface OperationResult\|type OperationResult" frontend/src/api/types.ts
# 缺少 already_active 字段 → 违规

# 4. 检查 API 调用点的类型断言
grep -rn "as any\|as unknown as" frontend/src/api/
# API 函数返回类型断言 → 违规
```

### 反模式

```typescript
// ❌ 反模式 1：返回类型用 any
export async function startSession(): Promise<any> {
  const resp = await client.post('/api/anticrawl/session/start');
  return resp.data;
}

// ❌ 反模式 2：OperationResult 缺少 already_active 字段
interface OperationResult {
  ok: boolean;
  error?: string;
  // ❌ 缺少 already_active，导致前端无法区分"已存在"与"首次创建"
}

// ❌ 反模式 3：调用点用 as 强制断言
const result = (await startSession()) as { ok: boolean; already_active: boolean };
```

### 正确模式

```typescript
// ✅ 正确模式：OperationResult 完整定义
export interface OperationResult {
  ok: boolean;
  // 幂等标志：资源已存在/已活跃时后端返回 true + 标志位
  already_active?: boolean;
  already_exists?: boolean;
  // 错误信息
  error?: string;
  error_code?: string;
  detail?: string;
  // 消息
  message?: string;
  // 其他业务字段
  affected_id?: string;
  warnings?: string[];
}

// ✅ 正确模式：API 函数显式标注返回类型
export async function startSession(): Promise<OperationResult> {
  const resp = await client.post<OperationResult>('/api/anticrawl/session/start');
  return resp.data;
}
```

### 配置参数

`config.yaml#idempotent_resource_creation_frontend.api_return_type_contract` 节点：

- `enabled`（默认 true）
- `severity`（默认 HIGH）
- `required_return_type`（默认 `OperationResult`）
- `api_function_patterns`（默认 `["start", "create", "register", "launch", "resume"]`）
- `required_idempotent_fields`（默认 `["already_active", "already_exists"]`，至少包含一个）
- `forbidden_return_types`（默认 `["any", "unknown", "Promise<any>"]`）
- `operation_result_interface_path`（默认 `frontend/src/api/types.ts`）

### 适用场景

- 所有资源创建/启动/注册类前端 API 函数
- 后端响应结构变更时同步检查前端类型定义
- 新增 API 端点时的类型契约对齐

### 不适用场景

- 纯查询接口（用专用 DTO 类型，不强制 OperationResult）
- SSE/WebSocket 流式响应（用专用 schema）
- 第三方 SDK 类型定义（无法控制）

### 历史教训

反爬登录管理系统 `startSession` API 函数返回类型原本是 `Promise<any>`，`OperationResult` 接口也缺少 `already_active` 字段，导致前端 handler 无法读取后端返回的幂等标志，被迫用 `resp.ok` 二值判断（详见第八轮复盘 F37）。

---

## F-REVIEW-235 UI-BACKEND-STATE-CONSISTENCY UI 与后端状态一致性强制刷新

- **维度**：47 资源创建幂等性与前端状态闭环
- **严重等级**：CRITICAL（P0）
- **规范引用**：`xianyu-hunter-dev` 规范 31 + 规范 32 + 维度 6 跨组件状态同步
- **后端联动**：B-REVIEW-315 FRONTEND-STATE-REFRESH-CLOSED-LOOP（互补）

### 检查点

前端 UI 状态显示必须始终与后端实际状态保持一致，通过以下机制保证：

1. **强制刷新**：所有写操作（创建/启动/停止/恢复）完成后，无论响应是 success/else/catch，都必须调用对应的 `loadXxx()` 函数重新从后端拉取最新状态
2. **不信任前端缓存**：UI 状态（如"会话已启动"）必须来自后端 `GET /xxx/status` 响应，禁止用前端 `useState` 独立维护（与 F-REVIEW-136 调度器状态同步一致）
3. **错误后强制刷新**：写操作失败时（else/catch 分支），后端可能已实际生效（fire-and-forget / 网络重试场景），必须刷新状态以避免 UI 显示与后端不一致
4. **加载状态独立**：`loading` 状态必须独立于业务状态，避免 `loading=true` 时业务状态显示为"未启动"

### 判断信号

```bash
# 1. 检查写操作后是否调用 loadXxx
grep -rn "await.*api\.\(start\|create\|update\|delete\|stop\|resume\)" frontend/src/ --include="*.tsx" --include="*.ts" -A 3
# 后接 loadXxx → 通过；缺失 → 违规

# 2. 检查业务状态是否来自 API 响应
grep -rn "useState\(false\|true\|null\)" frontend/src/pages/ --include="*.tsx"
# 业务状态用 useState 独立维护 → 违规（应来自 API 响应）

# 3. 检查错误分支是否刷新状态
grep -rn "message\.error" frontend/src/ --include="*.tsx" -B 2 -A 3
# message.error 后无 loadXxx → 违规

# 4. 检查 loading 状态与业务状态是否独立
grep -rn "const \[loading, setLoading\] = useState" frontend/src/pages/ --include="*.tsx"
# 应同时有独立的业务状态 useState（来自 API）
```

### 反模式

```typescript
// ❌ 反模式 1：success 才刷新，else/catch 不刷新
const handleStart = async () => {
  try {
    const resp = await startSession();
    if (resp.ok) {
      setActive(true);  // ❌ 前端独立维护状态
      message.success('启动成功');
      loadSession();
    } else {
      message.error('启动失败');  // ❌ 不刷新状态
    }
  } catch (e) {
    message.error('启动失败');  // ❌ 不刷新状态
  }
};

// ❌ 反模式 2：业务状态用前端 useState 独立维护
const [active, setActive] = useState(false);
// ❌ 应来自 GET /session/status 响应
```

### 正确模式

```typescript
// ✅ 正确模式 1：业务状态来自 API 响应
const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null);
const [loading, setLoading] = useState(false);  // 独立 loading 状态

const loadSession = async () => {
  const status = await getSessionStatus();
  setSessionStatus(status);  // ✅ 业务状态来自后端
};

// ✅ 正确模式 2：三分支统一刷新状态
const handleStartSession = async () => {
  setLoading(true);
  try {
    const resp = await startSession();
    if (resp.ok) {
      message.success(resp.already_active ? '会话已活跃' : '启动成功');
    } else {
      message.error(resp.error || '启动失败');
    }
  } catch (e) {
    message.error(extractApiError(e));
  } finally {
    setLoading(false);
    await loadSession();  // ✅ 三分支统一刷新
  }
};
```

### 配置参数

`config.yaml#idempotent_resource_creation_frontend.ui_backend_state_consistency` 节点：

- `enabled`（默认 true）
- `severity`（默认 CRITICAL）
- `require_refresh_after_write`（默认 true，写操作后必须刷新）
- `require_refresh_in_all_branches`（默认 true，三分支都必须刷新）
- `require_api_source_for_business_state`（默认 true，业务状态必须来自 API）
- `require_independent_loading_state`（默认 true，loading 状态必须独立）
- `write_operation_patterns`（默认 `["start", "create", "update", "delete", "stop", "resume", "pause"]`）
- `refresh_function_patterns`（默认 `["load", "refresh", "mutate", "refetch"]`）

### 适用场景

- 所有涉及后端资源状态的前端 UI（会话状态/任务状态/连接状态）
- 写操作（创建/启动/停止/恢复）的前端 handler
- 网络不稳定或 fire-and-forget 后端调用场景

### 不适用场景

- 纯前端 UI 状态（如 Modal 显示/隐藏、表单输入值）
- 防抖/节流的中间状态
- 加载状态本身（`loading` 不需要从后端拉取）

### 历史教训

反爬登录管理系统 `handleStartSession` 仅在 success 分支调用 `loadSession()`，else/catch 分支不刷新状态，而后端 `trigger_session_start()` 已通过 fire-and-forget 自动启动会话，导致用户看到"启动失败"提示但 UI 状态显示"已启动"的矛盾（详见第八轮复盘 F37）。

---

## 跨技能一致性验证清单

| 验证项 | 验证方式 | 结果 |
|---|---|---|
| 编码规范版本号一致 | `xianyu-hunter-dev` 规范 31-32 被本技能 F-REVIEW-233~235 引用 | ✅ |
| 检查点 ID 不冲突 | F-REVIEW-233~235（前端）/ B-REVIEW-313~315（后端）编号独立 | ✅ |
| 配置节点命名一致 | `idempotent_resource_creation_frontend.async_handler_three_branch` / `api_return_type_contract` / `ui_backend_state_consistency` | ✅ |
| 配套测试模式引用闭环 | SKILL.md 引用 auto-testing 模式 AA；auto-testing 引用 F-REVIEW-233~235 | ✅ |
| 无硬编码 | 所有 handler 模式/正则/函数名通过 config.yaml 管理 | ✅ |
| YAML 语法正确 | config.yaml 修改通过 yaml.safe_load 校验 | 待验证 |
