# B-REVIEW-313~315：资源创建幂等性与前端状态闭环（v4.64.0）

> 来源：2026-07-25 第八轮复盘（反爬登录会话启动矛盾修复）
> 配套规范：`xianyu-hunter-dev` 规范 31（资源创建接口幂等性设计）
> 配套前端审查：`xianyu-frontend-code-review` F-REVIEW-233~235
> 配套测试模式：`xianyu-auto-testing` 模式 AA
> 配套复盘：`xianyu-hunter-dev/references/retrospective-2026-07-25-r2.md`

---

## B-REVIEW-313 IDEMPOTENT-RESOURCE-CREATION 资源创建接口幂等性强检查

- **维度**：19 API 设计 / 37 资源创建幂等性与前端状态闭环
- **严重等级**：critical（P0）
- **规范引用**：维度 19 第 1842 行 🆕v4.0 幂等性设计描述性条目（本 B-REVIEW 升级为可执行检查清单）+ `xianyu-hunter-dev` 规范 31

### 检查点

资源创建接口（POST `/xxx/start`、`/xxx/create`、`/xxx/register`、`/xxx/launch`）必须满足：

1. **幂等语义**：重复调用返回当前状态 + `already_active`/`already_exists` 标志，不重复创建资源
2. **响应结构**：必须用 `OperationResult` 模型（`ok` + `already_active` + `message` + `error_code`）
3. **禁止失败表达已存在**：禁止用 `ok:False` 表达"资源已存在"语义（这是反爬矛盾修复的根因）
4. **单元测试覆盖**：必须有测试覆盖"首次创建 + 重复创建"两个场景

### 判断信号

- `grep "@router.post.*start|@router.post.*create|@router.post.*register"` 后逐个检查返回结构
- 接口返回 `{"ok": False, "error": "..."}` 表达"已存在" → 视为违规
- 接口无 `already_active` / `already_exists` 字段 → 视为违规
- 单元测试缺少 `test_xxx_already_active` 用例 → 视为违规

### 修复模式（通用伪代码，不绑定具体场景）

```python
@router.post("/xxx/start")
async def start_xxx(...) -> JSONResponse:
    manager = get_manager()
    # 幂等处理：资源已存在时返回 ok:True + already_active 标志
    # 为什么不用 ok:False：自动启动路径（如 fire-and-forget）可能已创建资源，
    # 用户手动点击会命中此分支，标记为失败会让前端误判为出错，但资源功能完全正常
    if manager.is_active:
        return JSONResponse(content={
            "ok": True,
            "already_active": True,
            "message": "资源已处于活跃状态，无需重复启动",
        })
    try:
        await manager.start(...)
        return JSONResponse(content={"ok": True, "message": "资源已启动"})
    except Exception as e:
        logger.error("启动失败: %s", e)
        return JSONResponse(content={"ok": False, "error": f"启动失败: {e}"})
```

### 配置参数

`config.yaml#idempotent_resource_creation` 节点：

```yaml
idempotent_resource_creation:
  enabled: true
  severity: CRITICAL
  route_patterns: ["/start", "/create", "/register", "/launch"]
  required_response_fields: ["ok", "already_active", "message"]
  forbidden_failure_for_existing: true
  required_test_suffixes: ["_already_active", "_already_exists", "_idempotent"]
  applicable_route_keywords: ["session", "task", "connection"]
  applicable_scenarios:
    - "资源创建/启动/注册接口"
    - "网络重试场景"
    - "前端启动/恢复按钮后端"
  inapplicable_scenarios:
    - "纯查询接口（天然幂等）"
    - "计数器递增"
    - "一次性副作用（如发短信验证码，需用 token 防重）"
```

### 适用场景

- 所有资源创建/启动/注册接口（`session/start`、`task/create`、`connection/register`）
- 网络重试场景（重复调用应返回当前状态而非失败）
- 前端"启动/恢复"按钮对应的后端接口

### 不适用场景

- 纯查询接口（天然幂等，无状态变更）
- 计数器递增接口（每次调用都应改变状态）
- 一次性副作用（如发短信验证码，需用 token 防重而非幂等）

### 历史教训

反爬登录管理系统中，`/session/start` 路由在会话已被 `trigger_session_start()` 自动启动后，对再次手动点击返回 `{"ok": False, "error": "会话已处于活跃状态"}`，前端显示"启动会话失败"但 UI 状态却显示"已启动"，造成矛盾。修复后改为 `{"ok": True, "already_active": True, "message": "..."}`，前端根据 `already_active` 显示 `info` 提示。

---

## B-REVIEW-314 OPERATION-RESULT-CONTRACT OperationResult 响应结构契约

- **维度**：11 错误处理 / 37 资源创建幂等性与前端状态闭环
- **严重等级**：error
- **规范引用**：维度 19 第 1838 行响应 DTO 规范（互补）+ `xianyu-hunter-dev` 规范 31

### 检查点

所有写操作（create/update/delete/start/stop）响应必须用统一 `OperationResult` 模型，字段集固定：

- **必填字段**：`ok: bool`
- **可选字段**：`already_active: bool`、`already_exists: bool`、`error: str`、`error_code: str`、`detail: str`、`message: str`、`affected_id: str`、`warnings: list[str]`
- **禁止字段**：非预定义的字段（避免前端类型漂移）

### 判断信号

- `grep "JSONResponse"` 后检查每个写操作响应是否符合字段集
- 响应包含未声明的字段 → 视为违规
- 缺少 `ok` 字段 → 视为违规（critical）

### 配置参数

`config.yaml#operation_result_contract` 节点：

```yaml
operation_result_contract:
  enabled: true
  severity: ERROR
  required_fields: ["ok"]
  optional_fields:
    - "already_active"
    - "already_exists"
    - "error"
    - "error_code"
    - "detail"
    - "message"
    - "affected_id"
    - "warnings"
  forbidden_extra_fields: false  # 是否禁止未声明字段
  model_definition_path: "src/xianyu_hunter/web/schemas/operation_result.py"
  applicable_scenarios:
    - "所有写操作（create/update/delete/start/stop）响应"
    - "后端响应结构变更同步检查"
  inapplicable_scenarios:
    - "纯查询接口（用专用 DTO）"
    - "流式响应（SSE/WebSocket，用专用 schema）"
```

### 适用场景

- 所有写操作（create/update/delete/start/stop）响应
- 后端响应结构变更同步检查

### 不适用场景

- 纯查询接口（应用专用 DTO 如 `SessionStatus`）
- 流式响应（SSE/WebSocket，应用专用 schema）

### 对应前端

`xianyu-frontend-code-review` F-REVIEW-234 API-RETURN-TYPE-CONTRACT

---

## B-REVIEW-315 FRONTEND-STATE-REFRESH-CLOSED-LOOP 前端状态刷新闭环（后端侧）

- **维度**：33 修复前全链路根因扫描 / 37 资源创建幂等性与前端状态闭环
- **严重等级**：error
- **规范引用**：维度 34 前后端字段契约单一可信源（互补）+ `xianyu-hunter-dev` 规范 31

### 检查点

后端响应字段变更时，必须检查前端 types.ts 是否同步消费：

1. 后端响应新增标志位（如 `already_active`）时，前端 `types.ts` 必须同步声明
2. 后端 API 函数返回类型必须与后端响应模型 1:1 对齐
3. 后端字段重命名时，前端必须同步更新
4. 后端字段废弃时，前端必须同步移除消费逻辑

### 判断信号

- `grep "JSONResponse"` 后端响应字段 vs `grep "interface.*Result" frontend/src/api/*.ts` 前端类型定义
- 后端响应有 `already_active` 但前端 types.ts 无此字段 → 视为违规
- API 函数返回类型与后端响应模型不匹配 → 视为违规
- 后端字段重命名但前端未同步 → 视为违规

### 配置参数

`config.yaml#frontend_state_refresh_closed_loop` 节点：

```yaml
frontend_state_refresh_closed_loop:
  enabled: true
  severity: ERROR
  frontend_types_file: "frontend/src/api/*.ts"
  required_sync_check: true
  grep_frontend_usage_patterns:
    - "interface.*Result"
    - "client\\.(get|post|put|delete)<.*>"
  backend_response_grep_patterns:
    - "JSONResponse"
    - "content=\\{"
  applicable_scenarios:
    - "后端响应字段变更同步"
    - "新增 API 端点"
    - "字段重命名/废弃"
  inapplicable_scenarios:
    - "前端内部状态类型（无后端对应）"
    - "第三方 SDK 类型"
```

### 适用场景

- 后端响应字段变更同步检查
- 新增 API 端点时验证前端类型对齐
- 字段重命名/废弃时的全链路同步

### 不适用场景

- 前端内部状态类型（无后端对应）
- 第三方 SDK 类型（按 SDK 文档）

### 对应前端

`xianyu-frontend-code-review` F-REVIEW-235 UI-BACKEND-STATE-CONSISTENCY

---

## 跨技能引用关系

| B-REVIEW | 对应前端 F-REVIEW | 对应测试模式 AA 步骤 | 对应开发规范 |
|---|---|---|---|
| B-REVIEW-313 IDEMPOTENT-RESOURCE-CREATION | F-REVIEW-233 ASYNC-HANDLER-THREE-BRANCH | 步骤 1（幂等性验证） | 规范 31 |
| B-REVIEW-314 OPERATION-RESULT-CONTRACT | F-REVIEW-234 API-RETURN-TYPE-CONTRACT | 步骤 3（类型契约对齐） | 规范 31 |
| B-REVIEW-315 FRONTEND-STATE-REFRESH-CLOSED-LOOP | F-REVIEW-235 UI-BACKEND-STATE-CONSISTENCY | 步骤 4（UI 状态一致性） | 规范 32 |
