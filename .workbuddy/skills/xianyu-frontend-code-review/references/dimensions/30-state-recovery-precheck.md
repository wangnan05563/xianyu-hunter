# 30. 状态恢复前置校验前端侧 🆕v4.35

> 本维度对应 `xianyu-hunter-dev` v4.31.0 meta-rules #31 与后端 `xianyu-backend-code-review` v4.30.0 的 B-REVIEW-157（状态恢复前置校验）。前端侧新增 1 个 F-REVIEW 检查点（F-REVIEW-116），强调恢复/启动按钮点击时必须先调用后端 precheck 接口校验前置条件。前端无降级链日志场景，不新增 LOG-MERGE 对应检查点（meta-rules #32 仅后端适用）。

- 🆕v4.35【强制】**F-REVIEW-116：RESUME-PRECHECK-FRONTEND 恢复操作前端前置校验**
  - 维度归属：30 状态恢复前置校验前端侧
  - 严重等级：error（P0）
  - 规范引用：meta-rule #31 状态恢复前置校验（前端侧）+ 后端 B-REVIEW-157
  - **检查点**：前端"恢复/启动/继续"按钮点击时，必须先调用后端 precheck 接口校验前置条件（如 Cookie 是否 valid、会话是否 active、连接是否可达），校验失败时禁用按钮 + 提示用户先解决根因（如重新登录），禁止绕过前端校验直接调 resume API
  - **检查项**：
    1. resume/启动按钮 `onClick` 必须调用 precheck API（如 `POST /api/<resource>/precheck`），获取 `{resume_blocked, reason_code, user_hint, retry_after}` 结构化响应
    2. precheck 失败时（`resume_blocked: true`）按钮 `disabled` + 提示 `user_hint`（如"请先重新登录闲鱼"），禁止直接调 resume API
    3. 冷却期内（`retry_after > 0`）按钮 `disabled` + 倒计时显示，倒计时结束后允许重新点击 precheck
    4. 禁止绕过前端校验直接调 resume API（如点击按钮立即 `fetch('/api/resume')` 无 precheck 调用）
  - **判断信号**：
    - `grep "onClick.*(resume|start|continue|恢复|启动|继续)" frontend/src/**/*.{ts,tsx}` 无 precheck 调用 → 视为违规
    - resume/启动按钮无 `disabled` 状态绑定（`disabled={precheckBlocked}`）→ 视为违规
    - 直接调 resume API（`fetch('/api/<resource>/resume')`）无前置 precheck 调用 → 视为违规
    - 冷却期内按钮可点击（无倒计时逻辑）→ 视为违规
  - **配置参数**：`resume_precheck_frontend.precheck_endpoint_pattern`（precheck 端点模式，如 `/api/<resource>/precheck`）、`resume_precheck_frontend.required_response_fields`（响应必须字段，如 `["resume_blocked", "reason_code", "user_hint", "retry_after"]`）、`resume_precheck_frontend.cooldown_countdown_required`（冷却期倒计时是否必须，默认 true）、`resume_precheck_frontend.applicable_buttons`（适用按钮清单，如 `["task_resume", "session_recover", "connection_reconnect"]`）在 `config.yaml` 的 `resume_precheck_frontend` 节点管理
  - **对应编码规范**：详见 `xianyu-hunter-dev` v4.31.0 meta-rules #31 + 后端 `xianyu-backend-code-review` v4.30.0 B-REVIEW-157
  - **适用**：任务恢复按钮（如搜索任务暂停后恢复）、登录会话恢复（Cookie 失效后重新登录）、连接重连按钮（连接池断连后重连）
  - **不适用**：无前置依赖的普通启动按钮（如新建任务）、用户主动 pause 后的恢复（非异常触发，无 root_cause）、一次性表单提交按钮
  - **历史教训**：搜索任务 `t68bc149b` 因闲鱼会话失效被自动暂停后，用户在前端连续点击「恢复」按钮 4 次，但前端未调用 precheck 校验 Cookie 层状态，每次恢复在 13~22 秒内再次触发会话失效检测并暂停，形成"恢复→失效→暂停"无效循环。修复：前端「恢复」按钮 onClick 先调 `POST /api/tasks/precheck`，校验 `cookie_rotator` 的 identity/session 是否 valid 状态，失效时按钮 disabled + 提示"请先重新登录闲鱼"，冷却期内显示倒计时，彻底消除无效循环

---
