

## v4.68.0 (2026-07-26) - 健康状态展示与后端实际状态一致性（experimental）

**类型**：experimental 版（Sequential Thinking 四维度复盘沉淀）
**触发来源**：2026-07-26 健康检查 cookie 显示无效但实时搜索正常，前端展示与用户实际体验矛盾。

**新增检查点**：
- F-REVIEW-245 健康状态展示与后端实际状态一致性（HEALTH-DISPLAY-CONSISTENCY）

**配置驱动**：新增 `config.yaml: health_display_consistency` 节点，包含 `enabled` / `distinguishRealFailureFromCheckError` / `disableFeatureOnInvalid` / `refreshAfterRelogin` 等子节点。

**关联规范**：[xianyu-hunter-dev/references/dual-data-source-consistency.md](../xianyu-hunter-dev/references/dual-data-source-consistency.md)
**关联复盘**：[xianyu-hunter-dev/references/retrospective-2026-07-26-r3.md](../xianyu-hunter-dev/references/retrospective-2026-07-26-r3.md)
**关联后端检查点**：B-REVIEW-332 双数据源兜底复核

**experimental 升正条件**：1 季度内（截至 2026-10-26）同类根因再发 ≥ 2 次

---

## v4.63.0 (2026-07-25) — 资源创建幂等性与前端状态闭环（第八轮复盘落地）

### 复盘背景

基于 2026-07-25 第八轮复盘（反爬登录会话启动矛盾修复），将"前端 async handler 三分支完整性"+"API 函数返回类型契约"+"UI 与后端状态一致性强制刷新"三类前端高风险场景沉淀为 3 个 F-REVIEW 检查点。核心目标是"防止 UI 状态与后端响应不一致的矛盾现象"，所有审查要点来自反爬登录会话启动矛盾修复的真实失败案例：

| 失败案例 | 根因 | 对应检查点 |
|----------|------|------------|
| `handleStartSession` else 分支显示固定文案"启动会话失败"且不调用 `loadSession()` | async handler 三分支不完整，else/catch 缺失状态刷新 | F-REVIEW-233 ASYNC-HANDLER-THREE-BRANCH |
| `startSession` API 函数返回类型为 `Promise<any>`，`OperationResult` 缺少 `already_active` 字段 | API 返回类型契约缺失，无法读取后端幂等标志 | F-REVIEW-234 API-RETURN-TYPE-CONTRACT |
| `handleStartSession` 仅 success 分支调用 `loadSession()`，后端 fire-and-forget 已自动启动会话导致 UI 矛盾 | UI 与后端状态不一致，未强制刷新业务状态 | F-REVIEW-235 UI-BACKEND-STATE-CONSISTENCY |

### 新增检查点详情

#### F-REVIEW-233 ASYNC-HANDLER-THREE-BRANCH
- **维度**：47 资源创建幂等性与前端状态闭环
- **严重等级**：CRITICAL（P0）
- **检查点**：前端 `async` 事件 handler 的 try/else/catch 三分支必须同时满足：
  1. success 分支：必须显式调用 `loadXxx()` 刷新所有相关 UI 状态
  2. else 分支：必须显示后端返回的具体错误字段（`error`/`detail`/`message`），禁止固定失败文案；同时必须调用 `loadXxx()` 刷新状态
  3. catch 分支：必须用 `extractApiError(e)` 显示网络/解析错误，同时必须调用 `loadXxx()` 刷新状态
- **配置参数**：`config.yaml#idempotent_resource_creation_frontend.async_handler_three_branch` 节点（含 `require_load_in_all_branches`、`require_specific_error_in_else`、`require_extract_api_error_in_catch`、`handler_patterns`、`refresh_function_patterns` 等）

#### F-REVIEW-234 API-RETURN-TYPE-CONTRACT
- **维度**：47 资源创建幂等性与前端状态闭环
- **严重等级**：HIGH（P1）
- **检查点**：前端 API 函数返回类型必须与后端响应模型 1:1 对齐：
  1. 资源创建类 API（`startXxx`/`createXxx`/`registerXxx`/`launchXxx`）返回类型必须用 `OperationResult` 接口
  2. 必填字段：`ok: boolean`
  3. 幂等标志字段：`already_active?: boolean` / `already_exists?: boolean`（至少一个）
  4. 错误字段：`error?` / `error_code?` / `detail?`
  5. 禁止用 `any` / `unknown` / `Promise<any>` 兜底返回类型
  6. 禁止在调用点用 `as` 强制断言
- **配置参数**：`config.yaml#idempotent_resource_creation_frontend.api_return_type_contract` 节点（含 `required_return_type`、`api_function_patterns`、`required_idempotent_fields`、`forbidden_return_types`、`operation_result_interface_path` 等）

#### F-REVIEW-235 UI-BACKEND-STATE-CONSISTENCY
- **维度**：47 资源创建幂等性与前端状态闭环
- **严重等级**：CRITICAL（P0）
- **检查点**：前端 UI 状态显示必须始终与后端实际状态一致：
  1. 强制刷新：写操作完成后，无论 success/else/catch 都必须调用 `loadXxx()` 重新拉取后端最新状态
  2. 不信任前端缓存：业务状态必须来自 `GET /xxx/status` 响应，禁止前端 `useState` 独立维护
  3. 错误后强制刷新：写操作失败时后端可能已实际生效（fire-and-forget / 网络重试），必须刷新状态避免矛盾
  4. 加载状态独立：`loading` 状态必须独立于业务状态
- **配置参数**：`config.yaml#idempotent_resource_creation_frontend.ui_backend_state_consistency` 节点（含 `require_refresh_after_write`、`require_refresh_in_all_branches`、`require_api_source_for_business_state`、`require_independent_loading_state`、`write_operation_patterns`、`refresh_function_patterns` 等）

### 跨技能一致性验证

| 验证项 | 验证方式 | 结果 |
|---|---|---|
| 编码规范版本号一致 | `xianyu-hunter-dev` 规范 31-32 被本技能 F-REVIEW-233~235 引用 | ✅ |
| 检查点 ID 不冲突 | F-REVIEW-233~235（前端）/ B-REVIEW-313~315（后端）编号独立 | ✅ |
| 配置节点命名一致 | `idempotent_resource_creation_frontend.async_handler_three_branch` / `api_return_type_contract` / `ui_backend_state_consistency` | ✅ |
| 配套测试模式引用闭环 | SKILL.md 引用 auto-testing 模式 AA；auto-testing 引用 F-REVIEW-233~235 | ✅ |
| 无硬编码 | 所有 handler 模式/正则/函数名通过 config.yaml 管理 | ✅ |
| YAML 语法正确 | config.yaml 修改通过 yaml.safe_load 校验 | 待验证 |

### 下游技能同步清单

| 文件 | 本次新增内容 |
|---|---|
| `.trae/skills/xianyu-frontend-code-review/SKILL.md` | 版本 v4.62.0 → v4.63.0，新增维度 47 资源创建幂等性与前端状态闭环 Review |
| `.trae/skills/xianyu-frontend-code-review/references/idempotent-resource-creation-checks.md` | 新建，F-REVIEW-233~235 详细描述 |
| `.trae/skills/xianyu-frontend-code-review/references/checkpoints-index.md` | 新增 F-REVIEW-233~235 索引行，统计 133→136 项 |
| `.trae/skills/xianyu-frontend-code-review/config.yaml` | 新增 `idempotent_resource_creation_frontend` 配置节点（含 3 个子节点） |
| `.trae/skills/xianyu-frontend-code-review/references/version-changelog.md` | 新增 v4.63.0 章节（本节） |

---

## v4.36.0 注册式资源三件套契约复盘（从 SKILL.md 内嵌段落外移）

> **v4.36.0 注册式资源三件套契约 + 修复协议 + 前后端字段契约复盘（meta-rules #33-35 前端落地、*：基、通知中心菜单点击无反、等历史问题复盘（用户报告"通知中心"菜单点击，URL 不变、内容不变；根因、`config/menu_registry.yaml` 已注、`path=/notifications`，但 `frontend/src/App.tsx` 无对、`<Route>`、`pages/Notifications/index.tsx` 不存在、`api/notifications.ts` 不存在，路由 fallback `<Route path="*" element={<Navigate to="/" replace />} />` 静默重定向到首页），使用 Sequential Thinking 4 维度复盘法——成功步、不确定性与失败、可抽象的固定流程与判断逻辑/适用场景与不适用场景，新，3 项维度（31-33 3 F-REVIEW 检查点、*F-REVIEW-117 REGISTRATION-COMPLETENESS 注册式资源三件套契约**（meta-rule #33 落地— 层契约：L1 menu_registry/L2 router/L3 page/L4 api_wrapper/L5 backend_endpoint 缺一即视，CRITICAL，自动化校验 `python scripts/check_registration.py` 退出码 0 才算通过，参数在 `frontend_registration_completeness` 节点管理）*F-REVIEW-118 ROOT-CAUSE-MIN-COUNT 修复前根因扫描协、*（meta-rule #34 落地——修复非平凡 bug 前必须先、 个根因覆盖用户层/接口、数据、配置、历史层；PR 描述必须、 根因列表"段；git diff 涉及  个无关文件视为违反最小修改原则；新增逻辑，unit test 视为 WARNING；参数在 `root_cause_protocol` 节点管理）*F-REVIEW-119 CONTRACT-SINGLE-SOURCE 前后端字段契约单一可信、*（meta-rule #35 落地——后，Pydantic/DB Row 字段 = 权威源；前端 `types.ts` 必须显式标注"派生来源"+ "Pydantic 字段"+ "变更日期"+ "约束" 4 段注释；snake_case 严格透传禁止，camelCase；后，Pydantic 字段 `xxx_yyy` + 前端 types.ts 字段 `xxxYyy` = CRITICAL 命名漂移；参数在 `contract_single_source` 节点管理）。所有新检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.32.0 meta-rules #33-35 step 181-183。后端对应规范为 `xianyu-backend-code-review` v4.31.0 B-REVIEW-159/160/161
---



## v4.38.0 列表聚合与状态联动复盘（从 SKILL.md 内嵌段落外移）

> **v4.38.0 列表聚合与状态联动复盘（meta-rules #38-42 前端落地、*：基于本轮对话解决的"捡漏价格参、等列表聚合类问题复盘（全局聚合未按任务，price_range/market_ratio 过滤导致越界数据 / 列表交叉数据 N+1 查询 / 多字段联动开关逻辑错误 / 状态恢，precheck 抛异、/ 配置缺失即崩溃），使，Sequential Thinking 4 维度复盘法——成功步、不确定性与失败、可抽象的固定流程与判断逻辑/适用场景与不适用场景，在维度 34（规范治理）下追，5 F-REVIEW 检查点（F-REVIEW-122~126），自动化扫描从 121 项扩展到 126 项。新增检查点、*F-REVIEW-122 GLOBAL-AGGREGATE-TASK-FILTER 全局聚合任务级过、*（meta-rule #38 前端侧——前端聚合统计（Dashboard 价格区间分布、市场价比率分布）必须按当前任务、`price_range`/`market_ratio` 配置过滤，禁止展示越界数据；前端展示聚合数据前必须确认后端已调用 `_filter_by_per_task_range` 过滤；参数在 `meta_rules_38_42_frontend.global_aggregate_filter` 节点管理）*F-REVIEW-123 LIST-CROSS-DOMAIN-INJECT 列表交叉数据批量注入**（meta-rule #39 前端侧——列表渲染交叉数据（如商品列表注入最新评估价/订单状态）必须用批，API 一次性获取，禁止循环中逐项 fetch；前端必须支持批量响应的 `id value` 映射结构；参数在 `meta_rules_38_42_frontend.cross_domain_inject` 节点管理）*F-REVIEW-124 MULTI-FIELD-LINKED-SWITCH 多字段联动开关范、*（meta-rule #40 前端侧——多字段联动开关（mode + bargain_only）必须遵、主开关决定副开关可见、范式，副开关值在主开关关闭时必须清零而非保留；前，UI 必须根据主开关状态动态显、隐藏副开关；参数、`meta_rules_38_42_frontend.linked_switch_priority` 节点管理）*F-REVIEW-125 RESUME-PRECHECK-STRUCTURED 状态恢复前置校验结构化响应**（meta-rule #41 前端侧——前端调，resume/start 接口必须处理结构，precheck 响应（`{resume_blocked, reason_code, user_hint, retry_after, task_registered}`），禁止假设接口直接成功；precheck 失败时必须展、`user_hint` `retry_after` 倒计时；参数、`meta_rules_38_42_frontend.precheck_structured_fields` 节点管理）*F-REVIEW-126 CONFIG-DRIVEN-THRESHOLD-FALLBACK 配置化阈值兜底范、*（meta-rule #42 前端侧——前端使用的阈值参数（p10 百分位、market_ratio_threshold、price_range_tolerance）必须从后端配置 API 获取，禁止前端硬编码；配，API 失败时必须用兜底默认值并 `console.warn`，禁止抛异常导致页面崩溃；参数在 `meta_rules_38_42_frontend.config_fallback_defaults` 节点管理）。所有新检查点强调配置驱动（参数在 `config.yaml` `meta_rules_38_42_frontend` 节点管理，不硬编码业务参数）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.34.0 meta-rules #38-42 step 184-188。后端对应规范为 `xianyu-backend-code-review` v4.34.0 B-REVIEW-164~168
---



## v4.44~v4.51 维度 37-45 版本复盘段落（从 SKILL.md 外移）

## 37. Provider  v4.46

- WARNING、P1、Provider UI 
- meta-rules #71 / step 210
- **F-REVIEW-162、PROVIDER-UI-STATE **
  -  Provider  provider 
  -  Provider  cpolar authtoken、Cloudflare cert_file、Tailscale 
  - grep "formProvider.*===" frontend/src/  provider 
  - Z、step 210

- **F-REVIEW-163、WIZARD-STEPS **
  - Named Tunnel  Steps //
  - currentStep config.yaml 
  -  cert_file/tunnel_id/hostname 
  - Z、step 210

- **F-REVIEW-164、ASYNC-LOADER-ISOLATION **
  - login create、route-dns loading 
  -  loading 
  - loginLoading  createLoading  loading 
  - Z、step 210

- **F-REVIEW-165、POLL-TIMER-CLEANUP **
  - setInterval useEffect cleanup 
  -  setState
  - setInterval  useEffect  clearInterval
  - Z、step 210

- **F-REVIEW-166、ERROR-RESET **
  -  loading  polling 
  - 
  - catch  setLoginPolling(false)  setCreateLoading(false)
  - Z、step 210

- ****provider_ui.wizard_steps、provider_ui.poll_interval_ms 2500、provider_ui.async_timeout_ms 30000 config.yaml  provider_ui 
- **** Provider  UI Tunnel.tsx、tunnelProviders.ts、tunnel.ts API 
- **** Provider 

## 38. Per-Preset Credential Management v4.47

- Severity: CRITICAL (P0, credential not following preset switch causes service call failures)
- Reference: meta-rules #70 / step 211
- **F-REVIEW-167: PRESET-APIKEY-INDIVIDUAL per-preset storage slot**
  - When form fields store credentials associated with a specific preset/vendor (e.g., API Key, Token), each preset must have its own storage slot.
  - Switching presets must atomically: (a) save current credential to its slot, (b) restore credential from target preset slot, (c) update active config.
  - Signal: form still uses global credential after preset switch, or credential lost after switch.
  - Config param: credential_storage.per_preset_slots in config.yaml credential_storage node

- **F-REVIEW-168: CONFIG-SAVE-INDEPENDENCE independent save**
  - Form config fields (model name, endpoint URL, API Key, etc.) must have an independent save mechanism, cannot rely on secondary actions (e.g., "test connection") to persist.
  - Signal: only persistence entry after form modification is test/verify button, no independent save button or debounced auto-save.
  - Config param: config_save.independent_button_required in config.yaml config_save node

- **F-REVIEW-169: BACKEND-RETURN-ON-UPDATE update echo**
  - PUT/PATCH config endpoints must return full updated state (including derived fields like preset_id, masked API Key) after modification, frontend stays in sync without extra GET call.
  - Signal: mutation response only returns {ok: true}, frontend needs extra GET request to get updated state.
  - Config param: api.mutation_response_echo in config.yaml api node

- **Applicable**: All form configs involving preset/vendor switching (AI service config, notification channel config, proxy config, etc.)
- **Not applicable**: Pure display forms without credential fields, one-time operation forms


## 39. Per-Preset Credential Frontend Contract v4.44

- Severity: CRITICAL (P0, frontend preset switch does not properly sync with backend credential slots)
- Reference: meta-rules #71 / step 211 / step 212
- **F-REVIEW-170: PRESET-APPLY-NO-KEY-FORWARD applyPreset omits api_key field**
  - When pplyPreset switches presets, it must NOT send the current pi_key value in the PUT request body.
  - The api_key field should only be sent when the user explicitly types/changes it, not during preset switching.
  - Sending api_key during preset switch can overwrite the target preset's slot with the wrong key.
  - Signal: pplyPreset function includes pi_key: config.api_key in the patch object.
  - Config param: credential_storage.frontend_contract.accept_missing_api_key_on_preset_switch in config.yaml

- **F-REVIEW-171: MASKED-KEY-UI-HANDLING masked key display after preset switch**
  - After preset switch, the returned masked api_key (****xxxx) must NOT be written to the password input value.
  - The api_key input should remain empty after preset switch (user must re-enter if needed).
  - Other fields (base_url, model, vision_model, preset_id) should be updated from the response.
  - Signal: setConfig after preset switch includes pi_key: saved.api_key where saved.api_key is a masked value.
  - Config param: ui.masked_key_handling in config.yaml

- **F-REVIEW-172: EMBEDDING-PRESET-KEY-FOLLOW embedding preset also handles key independently**
  - Embedding preset switch must follow the same pattern: do NOT send embedding_api_key during preset switch.
  - The embedding API key slot restoration must also be backend-managed.
  - Signal: pplyEmbeddingPreset includes embedding_api_key in the patch.
  - Config param: credential_storage.embedding_independent_slots in config.yaml

- **Applicable**: All frontend forms involving preset/vendor credential switching
- **Not applicable**: Non-credential form fields, one-time credential operations
## 40. Model Name Case-Sensitivity Review v4.48

- Severity: CRITICAL (P0, model name case mismatch causes API 400 errors)
- Reference: meta-rules #72 / step 214

- **F-REVIEW-173: MODEL-NAME-CASE-ACCURACY preset model name matches official docs**
  - All preset model names in constants.ts (PRESETS / EMBEDDING_PRESETS) must match vendor official API documentation character-for-character including case.
  - DeepSeek: deepseek-v4-flash (all lowercase), not DeepSeek-V4-Flash or deepseek-v4-flash.
  - Baidu: ERNIE-Speed-8K (mixed case), not ernie-speed-8k.
  - Signal: preset model name differs from official docs in case.
  - Config param: model_names.case_sensitive_check in config.yaml model_names node

- **F-REVIEW-174: MODEL-NAME-SHARED-CHECK-LOWER case-insensitive capability check**
  - Model capability check functions (e.g., _is_vision_capable) must use .lower() for case-insensitive matching, since different vendors use different case strategies.
  - Signal: capability check uses exact string match without .lower().
  - Config param: llm_capability_keywords.case_insensitive (default True) in config.yaml

- **Applicable**: All preset model name definitions in frontend constants files
- **Not applicable**: User-custom-input model names (format validation only)


## 41. Config Persistence and Reflection Review v4.48

- Severity: CRITICAL (P0, config values lost after refresh or incorrectly masked)
- Reference: meta-rules #73 / step 215

- **F-REVIEW-175: CONFIG-PERSIST-ON-CHANGE no secondary-action-required save**
  - Every config input field must have an independent persistence entry point (debounced auto-save or dedicated save button), not dependent on secondary actions like "test connection".
  - Signal: the only persistence trigger for form changes is a test/verify button.
  - Config param: config_persistence.persist_on_change (default True) in config.yaml

- **F-REVIEW-176: CONFIG-REFLECT-ORIGINAL non-secret fields reflect raw values**
  - Backend GET endpoint must return original (non-masked) values for all non-secret config fields (base_url, model, vision_model, embedding_*).
  - Signal: GET response contains masked value for a non-secret field.
  - Config param: config_persistence.mask_non_secret_fields (default False) in config.yaml

- **F-REVIEW-177: MASKED-KEY-PUT-SKIP unchanged key detection on PUT**
  - Frontend PUT must detect masked key prefix (****) and omit api_key from the patch when user hasn't changed it.
  - Signal: PUT request body contains api_key starting with ****.
  - Config param: credential_storage.mask_key_prefix (default "****") in config.yaml

- **Applicable**: All config forms with persistent settings
- **Not applicable**: One-time operation forms
## 42. Multi-User Cookie Isolation Frontend Review v4.45

- Severity: CRITICAL (P0, frontend cookie state display breaks after multi-user migration)
- Reference: meta-rules #72-#78 / steps 216-222

- **F-REVIEW-178: COOKIE-USERID-CONTEXT user_id available in frontend cookie operations**
  - Frontend components that display or manipulate cookie state must receive user_id from the authentication context (request.state.user_id passed from backend).
  - Cookie layer status display (/cookies/layers) must show per-user state, not just default user.
  - Signal: cookie status component does not receive or display user_id.
  - Config param: cookie_management.multi_user_isolation.frontend_user_id_required in config.yaml

- **F-REVIEW-179: COOKIE-STATE-SYNC-REFRESH real-time cookie state reflects current user**
  - When user switches accounts or presets, cookie state display must refresh to show the new user's cookies_{user_id}.json state.
  - Auto-refresh polling must include user_id in the request to get correct per-user cookie status.
  - Signal: cookie state display does not refresh after user/preset switch.
  - Config param: cookie_management.multi_user_isolation.state_refresh_on_switch in config.yaml

- **F-REVIEW-180: LOGIN-SUCCESS-COOKIE-INJECT-VERIFY verify injection after login**
  - After successful login, frontend must verify that cookie injection succeeded by checking the response from the login endpoint.
  - The response should include injected cookie count and user_id.
  - Signal: login success handler does not verify injection result.
  - Config param: ui.login_injection_verification in config.yaml

- **F-REVIEW-181: MULTI-USER-COOKIE-DISPLAY per-user cookie count display**
  - Cookie status dashboard must show cookie count per user, not just total.
  - When multiple users exist, switching user view must reload the correct cookies_{user_id}.json state.
  - Signal: cookie count display aggregates across all users instead of per-user.
  - Config param: ui.cookie_display.per_user_mode in config.yaml

- **Applicable**: All frontend components displaying or manipulating cookie state after multi-user migration
- **Not applicable**: Non-cookie UI components, one-time login flows without state display


## 43. Backend Logic Visibility Sync Frontend Review v4.49

- Severity: HIGH (P1, backend logic changes must be reflected in frontend rule documentation)
- Reference: meta-rules #70-#71 / step 223

- **F-REVIEW-182: BACKEND-LOGIC-VISIBILITY-SYNC backend logic changes must have frontend documentation**
  - When backend evaluation logic changes (e.g., new price range scoring, new threshold rules), the EvalRules page must include a corresponding documentation card explaining the new rule.
  - Signal: backend adds new evaluation dimension but EvalRules.tsx has no card explaining it.
  - Config param: eval.rules_visibility.sync_backend_changes (implicit, always True)

- **F-REVIEW-183: RULE-DOCUMENTATION-USABLE-EXAMPLES rule cards must include concrete examples**
  - Rule documentation cards must include concrete numerical examples (e.g., 600-800 yuan gradient) to help users understand abstract rules.
  - Signal: rule card describes logic abstractly without any numerical example.
  - Config param: eval.rules_visibility.include_examples (default True)

- **F-REVIEW-184: RULE-CONFIG-SOURCE-ANNOTATION rule cards must annotate configuration source**
  - Rule documentation must clearly state whether the rule comes from task-level config (per-task min_price/max_price) or global config (AppConfig.eval).*
  - Signal: rule card does not indicate configuration source.
  - Config param: eval.rules_visibility.annotate_config_source (default True)

- **Applicable**: All pages that display evaluation rules, thresholds, or scoring logic
- **Not applicable**: Pages that only consume evaluation results without displaying rules

## 44. Static Build Artifact Awareness Frontend Review v4.49

- Severity: MEDIUM (P2, build artifact management prevents confusion)
- Reference: meta-rules #72-#73 / step 224

- **F-REVIEW-185: STATIC-BUILD-ARTIFACT-NOT-GIT tracked files must not include build artifacts**
  - Files in src/xianyu_hunter/web/static/spa/ must NOT be committed to Git. Only source files (frontend/src/) should be tracked.
  - Signal: git status shows modified files in web/static/spa/ that are staged for commit.
  - Config param: git.ignore_patterns includes src/xianyu_hunter/web/static/spa/

- **F-REVIEW-186: BUILD-VERIFICATION-BEFORE-SUBMIT frontend changes must pass tsc + vite build**
  - Any frontend source change must be verified with both npx tsc --noEmit AND npx vite build before considering the change complete.
  - Signal: frontend PR includes source changes but no build verification evidence.
  - Config param: build.verify_before_submit (default True)

- **F-REVIEW-187: PWA-CACHE-REFRESH-HINT user notified of PWA cache after frontend changes**
  - After making frontend page changes, developers must inform users to Ctrl+F5 or unregister Service Worker.
  - Signal: frontend page changes deployed but users report seeing old content.
  - Config param: pwa.refresh_hints.enabled (default True)

- **Applicable**: All frontend source changes
- **Not applicable**: Pure backend changes without frontend impact

## 45.  v4.51.0

**F-REVIEW-191: POLLING-TIMEOUT-DISPLAY **

- **Z** config ""
- ****`grep "setInterval.*status|useEffect.*poll"` 
- ****`config.yaml#async_polling_pattern.timeout_display`
- ****
  - /browser-login/status
  - Cookie 
  - 
  -  setInterval + status 
- ****
  -  fetch 
  - SSE/WebSocket 
  - 
- **** Cookie  IPC  90s  60s 
---

##  A、2026-07-22 

> / 3 

### A.1  width  ellipsis

****
```bash
grep -rn "title:.*'" frontend/src/pages/ --include="*.tsx" | grep -v "key:" | grep "dataIndex\|key:" | head -20
```

****
-  `ellipsis: true`  `width`
- SCROLL_X  width  50-60px 
-  width   0 

**** SCROLL_X=1610 1590 width

### A.2 / key 

****
```bash
grep -rn "translate\|i18n\|labels\[" frontend/src/ --include="*.tsx" --include="*.ts" | head -20
```

****
- Tag / Tooltip / Statistic  `title`  key
-  key 
- `*.labels.ts` i18n 

****
```tsx
<Tag title={reason}>{translateRejectReason(reason)}</Tag>
<Statistic title={`${translateDimension(dim)} (${dim})`} value={score} />
```

### A.3  hook

****
```bash
grep -rn "localStorage\|sessionStorage\|usePersistentState" frontend/src/ --include="*.tsx" --include="*.ts"
```

****
-  `usePersistentState` hook
- localStorage key  namespace  `xh.evals.columns.order`
-  schema  `validator` 
-  1  /  1 

****
```tsx
const [order, setOrder] = usePersistentState<string[]>('xh.evals.columns.order', DEFAULT_ORDER, {
  validator: (v): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string')
})
```

### A.4 / state

****
```bash
grep -rn "onDragEnd\|onSortEnd\|DndContext\|SortableContext" frontend/src/ --include="*.tsx"
```

****
- `onDragEnd`  `setState(newOrder)`  onChange
- " setState"React 
-  re-render、key 
- locked: true

****
```tsx
//  state
const onDragEnd = (e) => console.log(e.active.id, e.over?.id)
```

### A.5 

****
```python
#  Python  minify  chunk/
import glob, os
files = glob.glob('src/xianyu_hunter/web/static/spa/assets/*.js')
for f in files:
    content = open(f, encoding='utf-8', errors='ignore').read()
    if 'translateDimension' in content or '' in content:
        print(f'HIT: {os.path.basename(f)}')
```

****
- Vite minify translateDimension  Ls grep 
-  token
-  chunk mtime 

****dimensionLabels.ts ""

---

##  B

### B.1 

```
1. PR/
   -  grep 
   -  TypeScript tsc --noEmit
   -  ESLint

2. 
   - npm run build 
   - Python  chunk 
   -  1 

3. 
   - vitest
   - Playwright、
```

### B.2 l

```markdown
## l - {}

### Blocker
- [ ]  width   
- [ ]  key  

### Critical
- [ ]  key  namespace  
- [ ]  state  

### Major
- 
-  `disabled` 

### 
- [ ] tsc --noEmit 
- [ ] npm run build 
- [ ] Python  chunk 
- [ ]  OK
```

---

##  C

- 2026-07-22
- xianyu-hunter-dev A.5、xianyu-auto-testing
- `docs/00-/-Z-2026-07-22.md`

---

> **v4.53.0 F-REVIEW-199 COMPONENT-REUSE-STATE-RESET meta-rule #85 2026-07-22 ThumbCell errored  Bug **" URL " `ThumbCell`  `rowKey={`${r.item_id}-${r.created_at}`}`  React `useState(false)`  `errored`  Sequential Thinking 4  rowKey  useState  useEffect // useState +  +  prop   useEffect / 1  F-REVIEW **F-REVIEW-199 COMPONENT-REUSE-STATE-RESET** 3/19、React  `rowKey` `useState` errored/loading/selected prop  `useEffect` `grep "useState" frontend/src/`    `<Table>` render / `expandedRowRender` / Tab `destroyInactiveTabPane={false}`   prop  `useEffect` `rowKey`  `created_at`+  `useState`   `errored`/`loading`/`failed`  `useEffect`   `useEffect(() => { setErrored(false) }, [url])` `config.yaml`  `component_reuse_state_reset` `enabled`/`components`/`reset_value_defaults`/`reuse_contexts`Tab `rowKey` key useEffect  F-REVIEW-159Z `xianyu-hunter-dev` v4.52.0  step 249Z

---

## v4.55.0 F-REVIEW-200~204 Z、2026-07-22 

>  xianyu-hunter-dev meta-rules #84-#88 Sequential Thinking 
> xianyu-auto-testing  L/  M

### F-REVIEW-200 DERIVED-SOURCE-ANNOTATION  11/15

****#88  5  / #35

****
1.  `ResponseModel` / DB Row  `types.ts` 
2.  `types.ts` `// derived from backend ResponseModel.xxx`
3. /grep  types.ts 

****
-  `ResponseModel`  `types.ts`   CRITICAL
-  `types.ts`   WARNING
-  types.ts   CRITICAL undefined

****
```powershell
#  ResponseModel 
Select-String -Path "src/xianyu_hunter/web/routes/api_*.py" -Pattern "class.*ResponseModel" 
#  types.ts
Select-String -Path "frontend/src/types.ts" -Pattern "derived from"
```

**** ResponseModel/DB Row //
****

---

### F-REVIEW-201 CONFIG-FIELD-UI-COVERAGE  11/15

****#87  5  Config.tsx 

****
1. DB schema  `Config.tsx` 
2. string、Input/textarea、bool、Switch、enum、Select、list、Transfer/Select multiple
3. `types.ts` 

****
- DB schema  `Config.tsx`   CRITICAL 5 
-  text  Input  textarea WARNING
- `types.ts`   CRITICAL 4 

****
```powershell
#  Config.tsx 
Select-String -Path "frontend/src/pages/Config.tsx" -Pattern "<(Input|TextArea|Switch|Select|Slider|InputNumber)"
#  types.ts 
Select-String -Path "frontend/src/types.ts" -Pattern "Config"
```

****
****/ DB 

---

### F-REVIEW-202 CONFIG-RESTORE-DEFAULT  11/15

****#87  3 

****
1. ""//
2. "" `delete_config` DB 
3. "" disabled、disabled-when-default
4.  UI 

****
- ""  WARNING
- ""  CRITICAL
- "" disabled-when-default  NIT

****
```powershell
Select-String -Path "frontend/src/pages/Config.tsx" -Pattern "delete|restore||reset"
```

****DB 
****

---

### F-REVIEW-203 TIMEOUT-STAGE-DISPLAY  UI  13/15

****#85  2 

****
1. //UI """"
2.  +  + 
3.  toast/message """"

****
- ""  CRITICAL
-   WARNING
-   WARNING

****
```powershell
Select-String -Path "frontend/src/pages/**/*.tsx" -Pattern "|unknown error|timeout|"
```

****//
****

---

### F-REVIEW-204 OVERWRITE-SET-FRONTEND-AWARENESS  11/15

****#88  4  

****
1.  `_coalesce` 
2. """"""""
3. /

****
-  `_coalesce`  WARNING
- """"  NIT
-   WARNING

****
```powershell
# ""
Select-String -Path "frontend/src/pages/**/*.tsx" -Pattern "refresh|reload|fetch.*after|.*"
```

****--/
****

---

> **v4.55.0 F-REVIEW-200~204 Z** xianyu-hunter-dev v4.55.0 meta-rules #84-#88 xianyu-auto-testing  L/M

---

## v4.56.0 F-REVIEW-205 Z

### F-REVIEW-205: SIDE-EFFECT-FALLBACK-ALERT  13/15

** meta-rule**#89 LOGIN-SIDE-EFFECT-AUTOMATION
**Z**xianyu-hunter-dev/assets/guides/coding-rules/concurrency.md step 253
****config.yaml#side_effect_fallback_alert

**** fire-and-forget  logger.debug""

****
1. ****Alert/Message
2. **** `session.active === false`  `session.status !== 'running'`
3. **Alert Z** `type="warning"` error
4. ****"" `/api/session/start` 
5. **** `/api/session/status` 
6. **** config.yaml 

**grep **
```bash
#  1
grep -rn "login.*success\|" frontend/src/pages/AntiCrawl/ | grep -v "Alert\|Message\|notification"

#  2
grep -rn "session.active\|session.status" frontend/src/pages/AntiCrawl/ | grep -v "=== false\|!== 'running'"

#  3
grep -rn "Alert.*type=\"warning\"" frontend/src/pages/AntiCrawl/ | grep -v "Button\|onClick.*start"
```

****
```bash
# 
grep -c "Alert.*warning" frontend/src/pages/AntiCrawl/*.tsx
# 
grep -c "\|manual.*start\|startSession" frontend/src/pages/AntiCrawl/*.tsx
```

****
-  Alert 
-  `session.active === false`
- Alert  warning
-  config 
-  config 

****
- 
- 

****
-  error 
- 
-  error 

---

> **v4.56.0 F-REVIEW-205 Z** xianyu-hunter-dev v4.56.0 meta-rule #89 xianyu-auto-testing  N、config.yaml  side_effect_fallback_alert 

---

## v4.57.0 F-REVIEW-206 Z

### F-REVIEW-206: FALLBACK-PRESERVE-KEY-FRONTEND  11/15

** meta-rule**#90 FALLBACK-PRESERVE-KEY
****B-REVIEW-251
****config.yaml#fallback_preserve_key_frontend
****error

**/**2026-07-22 price_range  Bug  item  payload  task_id  Sequential Thinking 4 // +   / 1  F-REVIEW 

**** payload  task_id、user_id、item_id

****
1. ****/ payload  task_id、user_id、item_id
2. **** `undefined`/`null`/`''`  payload/response 
3. **** task_id  user_id 
4. ****b config.yaml 

**grep **
```bash
#  1
grep -rn "payload.get" frontend/src/

#  2 task_id/user_id/item_id
grep -rn "payload.get" frontend/src/ | grep -v "task_id\|user_id\|item_id"
```

****
```bash
# 
grep -rc "payload.get" frontend/src/
# 
grep -rn "payload.get" frontend/src/ | grep -E "task_id|user_id|item_id"
```

**** payload/response 
```typescript
// ?  item  task_id
const item = {
  id: payload.get('id'),
  price_range: payload.get('price_range'),
  // task_id    task_id 
}

// ? 
const item = {
  id: payload.get('id'),
  price_range: payload.get('price_range'),
  task_id: payload.get('task_id'),  // 
  user_id: payload.get('user_id'),  // 
}
```

**** `config.yaml`  `fallback_preserve_key` `enabled`/`required_keys`/`entity_types`/`fallback_sources`

****
-  `fallback_preserve_key.required_keys` 
-  payload/response 
-  config.yaml 

****
-  + 
-  payload 
- SSE/WebSocket 

****
-  API 
- 

---

> **v4.57.0 F-REVIEW-206 Z** xianyu-hunter-dev v4.57.0 meta-rule #90、config.yaml  fallback_preserve_key_frontend  B-REVIEW-251

---

## v4.60.0 F-REVIEW-214~216 Z、2026-07-22 

>  xianyu-hunter-dev v4.60.0 meta-rules #101-#102 "Cookie  +  + CDP "`config/tech-stack.json#hardConstraints.uiPersistence`  `hardConstraints.multiWritePathCheck`

### F-REVIEW-214: MULTI-WRITE-PATH-STATE-CHECK meta-rule #101 v4.60

**** CookieRotator._layer_states.valid
****`config/tech-stack.json#hardConstraints.multiWritePathCheck`
- `intermediateStatePatterns``_layer_states``.valid``.active``_cache_time`
- `writeEntryPatterns``on_login_success``atomic_update``sync_state`
- `validateActualDataPreferred`true
- `autoSyncEnabled`true

****
1. ****Grep 
2. ****Grep 
3. ****/1   P0 
4. **** Cookie DB   P1 
5. ****  P1 

**Grep **
```bash
# 
grep -rn "_layer_states\|\.valid\|\.active\|_cache_time" frontend/src/ --include="*.ts" --include="*.tsx"
# 
grep -rn "on_login_success\|atomic_update\|sync_state\|set_layer_state" frontend/src/ --include="*.ts" --include="*.tsx"
# 
grep -rn "on_login_success\|atomic_update" frontend/src/ --include="*.ts" --include="*.tsx" | grep -v "sync_state\|init_state"
```

****Cookie 
**** loading 
**** F-REVIEW-113 F-REVIEW-197

---

### F-REVIEW-215: UI-PREFERENCE-PERSISTENCE-CHECK UImeta-rule #102 v4.60

**** `useState`  UI  UI 
****`config/tech-stack.json#hardConstraints.uiPersistence`
- `persistablePreferences`pageSize/viewMode/filter/Enabled/Mode/sortBy/sortOrder
- `nonPersistableStates`loading/error/modalVisible/dropdownOpen
- `storageKeyPrefix`localStorage key `xh.`
- `defaultDebounceMs`300ms
- `draftDebounceMs`500ms

****
1. ** useState **Grep  `useState` 
2. **** `persistablePreferences` 
3. **** `usePersistentState`  `useState` `useState`  P1 
4. ** storage key** `usePersistentState`  key  `storageKeyPrefix``xh.`
5. **** `validator`  localStorage 
6. **** `nonPersistableStates`  `usePersistentState`

**Grep **
```bash
#  useState 
grep -rn "useState" frontend/src/pages/ --include="*.tsx" | grep -iE "pageSize|viewMode|filter|Enabled|Mode|sortBy|sortOrder|useCdp|autoRefresh"
#  usePersistentState
grep -rn "usePersistentState" frontend/src/pages/ --include="*.tsx"
#  storage key 
grep -rn "usePersistentState.*'" frontend/src/pages/ --include="*.tsx" | grep -v "'xh\."
```

**** UI 
**** UI loading/error/modalVisible/dropdownOpen/hoveredRow
**** F-REVIEW-175、CONFIG-PERSIST-ON-CHANGE F-REVIEW-199、COMPONENT-REUSE-STATE-RESET

---

### F-REVIEW-216: STORAGE-ERROR-HANDLING-CHECK storage meta-rule #102 v4.60

**** localStorage/sessionStorage  Hook
****`config/tech-stack.json#hardConstraints.uiPersistence`
- `storageVersionField``__v`
- `defaultDebounceMs`

****
1. ** try-catch ** localStorage  try-catch  `QuotaExceededError``SecurityError` 
2. ****localStorage / `Map`
3. ****`__v`
4. **** `validator` 
5. **** 300ms localStorage 
6. ** isPersistent **`usePersistentState`  `isPersistent` 

**Grep **
```bash
#  try-catch  localStorage 
grep -rn "localStorage\.\(getItem\|setItem\|removeItem\)" frontend/src/ --include="*.ts" --include="*.tsx" | grep -v "try"
# 
grep -rn "Map()\|new Map" frontend/src/utils/storage.ts
# 
grep -rn "__v" frontend/src/utils/storage.ts
# 
grep -rn "debounce\|setTimeout" frontend/src/hooks/usePersistentState.ts
```

**** localStorage/sessionStorage  Hook、PWA 
****Cookie Z、IndexedDB 
**** F-REVIEW-138、HOOK-CLEANUP-COMPLETENESS F-REVIEW-165、POLL-TIMER-CLEANUP Hook 

---

> **v4.60.0 F-REVIEW-UI-PREVIEW-GATE / STATE-SELECTION / DEFENSIVE-RENDER / COMPONENT-REUSE-RESET 规范已补全**：对应 xianyu-hunter-dev v4.60.0 12项历史问题复盘提炼，前端侧。config.yaml 已补全 `ui_preview_gate`、`state_selection`、`spa_render_resilience`、`component_reuse_state_reset` 配置节点。auto-testing 对应模式 V/W/X。

---

## v4.60.0 F-REVIEW-UI-PREVIEW-GATE / STATE-SELECTION / DEFENSIVE-RENDER / COMPONENT-REUSE-RESET（2026-07-23 12项历史问题复盘提炼）

### F-REVIEW-UI-PREVIEW-GATE: UI视觉变更预确认门控（维度 3/7）

**配置节点**：config.yaml#ui_preview_gate
**风险等级**：warning

**背景/历史教训**：基于历史问题复盘——icon/theme/color/layout 大面积替换时，未经过用户预览确认直接全量替换，导致UI一致性被破坏且难以回滚。使用 Sequential Thinking 4 维度复盘法提炼：成功步骤（识别出大面积替换属于高风险操作）/ 不确定性与失败（未设置预确认门控导致全量替换后无法回退）/ 可抽象的固定流程（单模块先行→用户确认→全量替换）/ 适用场景与不适用场景。

**检查要点**：
1. **大面积替换检测**：icon/theme/color/layout 的替换行数超过 `ui_preview_gate.changeLineThreshold`（默认10行）→ 要求预览确认
2. **替换策略**：先替换单模块→用户确认视觉一致性→全量替换，禁止直接全量替换
3. **回滚清单**：全量替换前必须记录回滚清单（变更文件列表+变更前内容），确保可回退
4. **豁免场景**：Bug修复、文案修正等非视觉变更不受门控约束（匹配 `ui_preview_gate.exemptPatterns`）

**判断信号（grep 命令）**：
```bash
# 信号 1：检测 icon 的大面积替换
git diff --stat | grep -E "import.*Icon" | wc -l

# 信号 2：检测 theme/color 大面积替换
git diff --stat | grep -E "colorPrimary|borderRadius|token\." | wc -l

# 信号 3：变更行数统计
git diff --shortstat
```

**修复模式**：单模块先行+用户确认+全量替换
```typescript
// ❌ 违规：直接全量替换所有 icon
- <OldIcon />
+ <NewIcon />
// 涉及 15+ 文件，超过 changeLineThreshold

// ✅ 合规：先替换单模块，用户确认后全量
// Step 1: 单模块替换（如 Dashboard 页面）
// Step 2: 用户预览确认
// Step 3: 全量替换 + 记录回滚清单
```

**结果呈现**：⚠️ UI变更门控未通过——需用户预览确认后再全量替换

**通过标准**：
- 大面积替换前已执行单模块先行策略
- 用户已确认视觉效果一致性
- 回滚清单已记录
- 豁免场景需在 commit message 中标注

**适用场景**：icon 全量替换、主题色调整、borderRadius 统一修改、布局结构大面积调整
**不适用场景**：Bug修复、文案修正、单文件小范围修改（变更行数 < changeLineThreshold）

---

### F-REVIEW-STATE-SELECTION: React状态管理选型正确性（维度 10/3）

**配置节点**：config.yaml#state_selection
**风险等级**：warning

**背景/历史教训**：基于历史问题复盘——页面刷新后用户偏好设置（如自动刷新、视图模式、列配置、密度、折叠状态等）丢失，因为使用了 useState 而非 usePersistentState。用户重新进入页面时所有个性化配置被重置为默认值，体验极差。使用 Sequential Thinking 4 维度复盘法提炼：成功步骤（识别出需持久化的状态应使用 usePersistentState）/ 不确定性与失败（开发者习惯性使用 useState 导致刷新丢失）/ 可抽象的固定流程（检查关键词→判断持久化需求→替换 Hook）/ 适用场景与不适用场景。

**检查要点**：
1. **useState 滥用检测**：扫描所有 useState 是否用于需跨刷新持久化的状态（匹配 `state_selection.preferenceKeywords` 列表）
2. **持久化 Hook 替换**：需持久化的状态应使用 `usePersistentState`（由 `state_selection.persistenceHookName` 配置），而非 `useState`
3. **key 命名规范**：usePersistentState 的 key 必须遵循 `xh.<page>.<field>` 命名模式（由 `state_selection.keyNamingPattern` 配置）
4. **validator 校验**：usePersistentState 必须提供 validator 函数，防止 localStorage 中被篡改的数据导致类型错误

**判断信号（grep 命令）**：
```bash
# 信号 1：检测 useState 用于偏好类状态
grep -rn "useState" frontend/src/pages/ --include="*.tsx" | grep -iE "autoRefresh|viewMode|columnConfig|density|collapsed|expandedKeys|themePreference|recentItems|useCdp"

# 信号 2：检测已使用 usePersistentState 的状态
grep -rn "usePersistentState" frontend/src/ --include="*.tsx"

# 信号 3：检测 key 命名不符合规范
grep -rn "usePersistentState" frontend/src/ --include="*.tsx" | grep -v "'xh\."
```

**修复模式**：useState→usePersistentState 替换
```typescript
// ❌ 违规：用 useState 存储需持久化的偏好
const [autoRefresh, setAutoRefresh] = useState(true)
const [viewMode, setViewMode] = useState('table')

// ✅ 合规：用 usePersistentState 持久化偏好，遵循 xh.<page>.<field> 命名 + validator
const [autoRefresh, setAutoRefresh] = usePersistentState('xh.tasks.autoRefresh', true, {
  validator: (v) => typeof v === 'boolean'
})
const [viewMode, setViewMode] = usePersistentState('xh.tasks.viewMode', 'table', {
  validator: (v) => ['table', 'card'].includes(v)
})
```

**结果呈现**：🔧 useState→usePersistentState 建议替换——刷新后状态丢失

**通过标准**：
- 所有 preferenceKeywords 列表中的状态均使用 usePersistentState
- key 命名遵循 `xh.<page>.<field>` 模式
- 每个 usePersistentState 均提供 validator 函数
- 非持久化状态（loading/error/modalVisible 等）仍使用 useState

**适用场景**：用户偏好设置（自动刷新、视图模式、列配置、密度、折叠状态、展开键、主题偏好、最近项、CDP模式）
**不适用场景**：临时 UI 状态（loading/error/modalVisible/dropdownOpen/hoveredRow）、组件内部非持久化计算状态

---

### F-REVIEW-DEFENSIVE-RENDER: SPA防御性渲染完整性（维度 7/10）

**配置节点**：config.yaml#spa_render_resilience
**风险等级**：error

**背景/历史教训**：基于历史问题复盘——SPA 白屏/崩溃问题频发，根因是缺乏防御性渲染机制：无 ErrorBoundary 导致组件异常时整页白屏；无 lazyRetry 导致 chunk 加载失败无法恢复；无防御性访问导致 API 数据为 null 时渲染崩溃；无 401 拦截防抖导致并发请求时多次跳转登录页。使用 Sequential Thinking 4 维度复盘法提炼：成功步骤（识别出 SPA 渲染层需要四件套防护）/ 不确定性与失败（四件套缺失导致用户体验断崖式下降）/ 可抽象的固定流程（逐一检查四件套→缺失则标记→修复补充）/ 适用场景与不适用场景。

**检查要点**：
1. **全局 ErrorBoundary**：SPA 入口（App.tsx）必须包含全局 ErrorBoundary 包裹，组件异常时展示降级 UI 而非白屏（`spa_render_resilience.requireGlobalErrorBoundary`）
2. **lazyRetry 包装**：所有 React.lazy 动态导入必须用 lazyRetry 包装，chunk 加载失败时自动重试（`spa_render_resilience.requireLazyRetry`）
3. **防御性访问**：API 返回数据的嵌套字段必须使用可选链 `?.` 访问，防止 null/undefined 导致渲染崩溃（`spa_render_resilience.requireDefensiveAccess`）
4. **401 拦截防抖**：全局 401 拦截器必须实现防抖，避免并发请求失败时多次重定向登录页（`spa_render_resilience.require401Debounce`）

**判断信号（grep 命令）**：
```bash
# 信号 1：检测全局 ErrorBoundary
grep -rn "ErrorBoundary" frontend/src/App.tsx

# 信号 2：检测 lazy 是否被 lazyRetry 包装
grep -rn "React.lazy\b" frontend/src/ --include="*.tsx" --include="*.ts" | grep -v "lazyRetry"

# 信号 3：检测 API 数据未使用可选链
grep -rn "data\.\(items\|list\|records\)" frontend/src/ --include="*.tsx" | grep -v "\?\."

# 信号 4：检测 401 拦截是否有防抖
grep -rn "401" frontend/src/api/client.ts | grep -v "debounce\|isRedirecting\|throttle"
```

**修复模式**：添加 ErrorBoundary + lazyRetry + 可选链 + 401 防抖
```typescript
// ❌ 违规：缺少全局 ErrorBoundary
function App() {
  return <Router><Routes>...</Routes></Router>
}

// ✅ 合规：全局 ErrorBoundary 包裹
function App() {
  return (
    <ErrorBoundary fallback={<Result status="error" title="页面异常" />}>
      <Router><Routes>...</Routes></Router>
    </ErrorBoundary>
  )
}

// ❌ 违规：React.lazy 无 lazyRetry
const Dashboard = React.lazy(() => import('./pages/Dashboard'))

// ✅ 合规：lazyRetry 包装
const Dashboard = React.lazy(() => lazyRetry(() => import('./pages/Dashboard'), 'Dashboard'))

// ❌ 违规：直接访问嵌套字段
const items = data.items.map(...)

// ✅ 合规：可选链 + 兜底
const items = data?.items  []

// ❌ 违规：401 拦截无防抖
if (status === 401) { navigate('/login') }

// ✅ 合规：401 防抖
if (status === 401 && !isRedirecting) {
  isRedirecting = true
  navigate('/login', { replace: true })
}
```

**结果呈现**：🛡️ 防御性渲染检查清单——缺少[具体项]

**通过标准**：
- App.tsx 包含全局 ErrorBoundary（`spa_render_resilience.checkItems` 第1项）
- 所有 React.lazy 使用 lazyRetry 包装（第2项）
- API 数据访问使用可选链 `?.`（第3项）
- 401 拦截器实现防抖机制（第4项）

**适用场景**：SPA 路由入口、动态加载页面、API 数据渲染、全局 HTTP 拦截器
**不适用场景**：SSR 应用（错误由服务端处理）、非 SPA 的传统多页应用

---

### F-REVIEW-COMPONENT-REUSE-RESET: 组件复用状态重置（维度 3/10）

**配置节点**：config.yaml#component_reuse_state_reset
**风险等级**：warning

**背景/历史教训**：基于历史问题复盘——列表项组件（如 ThumbCell）有内部 useState（如 errored/loading/selected），但在 Table render/expandedRowRender/Tab 面板中复用时，prop 变化但内部状态未重置，导致旧状态残留。例如 ThumbCell 的 errored 状态在切换 item 后仍保持 true，显示错误图标。使用 Sequential Thinking 4 维度复盘法提炼：成功步骤（识别出组件复用时内部状态需随 prop 变化重置）/ 不确定性与失败（开发者未考虑组件复用场景导致状态残留）/ 可抽象的固定流程（检测复用上下文+内部状态→添加 useEffect 重置）/ 适用场景与不适用场景。

**检查要点**：
1. **复用上下文检测**：组件在 Table render/expandedRowRender/Tab 面板中使用（匹配 `component_reuse_state_reset.reuseContexts` 列表）→需检查状态重置
2. **内部状态识别**：组件有 useState 但无 useEffect 监听 prop 变化重置内部状态→标记为问题
3. **重置默认值**：重置时使用 `resetValueDefaults` 配置的默认值（如 errored=false, loading=false, selected=false, expanded=false）
4. **rowKey 静态字段检测**：rowKey 包含静态字段时（如固定 ID），组件实例不会因 key 变化而重新挂载，更需显式重置

**判断信号（grep 命令）**：
```bash
# 信号 1：检测列表项组件中的 useState
grep -rn "useState" frontend/src/components/ --include="*.tsx" | grep -iE "errored|loading|selected|expanded"

# 信号 2：检测在 Table render 中复用的组件
grep -rn "render.*=\|expandedRowRender" frontend/src/pages/ --include="*.tsx"

# 信号 3：检测是否有 useEffect 重置
grep -rn "useEffect" frontend/src/components/ --include="*.tsx" | grep -iE "props\.\|itemId\|taskId"
```

**修复模式**：添加 useEffect 监听 prop 变化重置内部状态
```typescript
// ❌ 违规：ThumbCell 有 errored 状态但切换 item 时未重置
function ThumbCell({ item, src }: ThumbCellProps) {
  const [errored, setErrored] = useState(false)
  // 当 item 变化时，errored 仍为上一项的值
  return errored ? <ErrorIcon /> : <img src={src} onError={() => setErrored(true)} />
}

// ✅ 合规：添加 useEffect 监听 prop 变化重置内部状态
function ThumbCell({ item, src }: ThumbCellProps) {
  const [errored, setErrored] = useState(false)
  // item 变化时重置 errored 为默认值
  useEffect(() => {
    setErrored(false)
  }, [item?.id])
  return errored ? <ErrorIcon /> : <img src={src} onError={() => setErrored(true)} />
}
```

**结果呈现**：🔄 组件复用状态残留——[组件名]的[state名]未随[prop名]变化重置

**通过标准**：
- 列表项组件有 useState + 复用上下文 → 必须有 useEffect 重置
- 重置默认值从 `resetValueDefaults` 配置获取
- rowKey 含静态字段的 Table 更需显式重置检查

**适用场景**：Table render 列表项组件、expandedRowRender 展开行组件、Tab 面板组件、rowKey 含静态字段的列表
**不适用场景**：独立路由页面组件（每次挂载都是新实例）、组件的 prop 不变（无复用场景）

---

> **v4.60.0 F-REVIEW-UI-PREVIEW-GATE / STATE-SELECTION / DEFENSIVE-RENDER / COMPONENT-REUSE-RESET 规范已补全**：对应 xianyu-hunter-dev v4.60.0 12项历史问题复盘提炼，前端侧。config.yaml 已补全 `ui_preview_gate`、`state_selection`、`spa_render_resilience`、`component_reuse_state_reset` 配置节点。auto-testing 对应模式 V/W/X。

---

> **v4.60.0 F-REVIEW-214~216 Z** xianyu-hunter-dev v4.60.0 meta-rules #101-#102、config/tech-stack.json  `hardConstraints.uiPersistence`  `hardConstraints.multiWritePathCheck`  B-REVIEW-267/268、auto-testing  S/T

---



## v4.59.0（2026-07-22）React SPA 间歇性白屏修复复盘

**复盘方法**：Sequential Thinking 4 维度复盘法（成功步骤 / 不确定性与失败点 / 可抽象的固定流程与判断逻辑 / 适用场景与不适用场景）
**复盘范围**：2026-07-22 完成的 React SPA 间歇性白屏修复（5 类根因 + 3 类测试踩坑）
**问题归纳**：2 大类（A 渲染容错缺失 / B 测试环境与断言兼容性）

**变更来源**：`docs/00-待完成/迭代提示词.md#L31-53`

**5 类根因**：
1. 缺少全局 ErrorBoundary——React 组件树抛错后整页白屏，无降级 UI
2. 懒加载 chunk 失效无重试——CDN/部署抖动触发 `Failed to fetch dynamically imported module` 后无法恢复
3. 未保护的数据访问——API 返回 `items` 为 `null`/`undefined` 时 `items[0]` 抛 TypeError 引发白屏
4. 401 拦截器硬跳转——多个并发 401 触发多次 `window.location.href` 跳转，竞态下产生白屏闪烁
5. 路由级错误无隔离——子路由抛错冒泡到全局，导致整个 Layout 白屏而非仅当前 Tab 降级

**测试踩坑 3 类**：
1. vitest 未安装——直接 `npx vitest run` 触发交互式安装提示，CI 卡死
2. antd 中文按钮加空格——antd v5 `Space.Compact` 自动在中文字符间插入空格，`screen.getByText('重试')` 找不到元素
3. tsconfig 未排除测试文件——`__tests__/*.test.tsx` 被 `tsc --noEmit` 校验，类型错误

**治禅门橙**：经 meta-rule #36 精简，原 9 条合并为 6 条（R3 合并到 F-REVIEW-154 扩展、R4 合并到 F-REVIEW-216 子细则、R5 合并到 F-REVIEW-215 子细则），自动化扫描从 119 项扩展到 125 项。

**关联技能**：
- `xianyu-hunter-dev` step 254-261 / meta-rule #95（SPA 白屏修复与测试约定）
- `xianyu-auto-testing` 模式 U（vitest 环境搭建与 antd 中文断言兼容）

**新增审查要点**：6 个 F-REVIEW 检查点（F-REVIEW-214 ~ F-REVIEW-219）

- **F-REVIEW-214 GLOBAL-ERROR-BOUNDARY**（维度 3 React 组件规范，CRITICAL）：App.tsx 必须用 `<ErrorBoundary>` 包裹整个 Routes，类组件实现 `getDerivedStateFromError` + `componentDidCatch` + `resetKeys` 自动重置 + `onError` 回调；扫描命令 `grep -c "<ErrorBoundary" frontend/src/App.tsx` === 0 → CRITICAL
- **F-REVIEW-215 LAZY-RETRY-WRAPPER**（维度 10 路由与懒加载，CRITICAL）：禁止裸用 `lazy()`，必须用 `lazyRetry()` 包装；ChunkLoadError 识别后用 sessionStorage 持久化重试计数（避免 reload 后丢失）；maxRetries 从 config 读取（默认 3）；子细则（原 R5 合并）：ChunkLoadError 识别模式从 config 的 `chunkErrorPatterns` 读取；扫描命令 `grep "\blazy(" frontend/src/ | grep -v lazyRetry` 命中 → CRITICAL
- **F-REVIEW-216 ROUTE-ERROR-BOUNDARY-RESET-KEYS**（维度 10 路由与懒加载，CRITICAL）：MainLayout Content 必须用 `<ErrorBoundary resetKeys={[location.pathname]}>` 包裹 Outlet；子细则（原 R4 合并）：resetKeys 必须是基本类型数组（string/number），禁止对象/数组引用；扫描命令 `grep "resetKeys" frontend/src/components/layout/MainLayout.tsx` 未命中 → CRITICAL，含对象/数组引用 → WARNING
- **F-REVIEW-217 API-ARRAY-DEFENSE-FALLBACK**（维度 7 业务逻辑，MAJOR）：所有 API 返回的数组字段使用前必须 `|| []` 兜底；对象字段必须 `?.` 可选链；扫描命令 `grep -E "\b(res|data|response)\.(items|tables|list|records|data|results)\." frontend/src/` 命中且无 `|| []` → MAJOR
- **F-REVIEW-218 VITEST-ENV-CHECKLIST**（维度 12 可测试性，MAJOR）：运行测试前验证 vitest 可执行文件存在；vitest.config.ts 存在；test-setup.ts 存在；tsconfig.json 排除测试文件；扫描命令 `Test-Path node_modules/.bin/vitest` === False → MAJOR；`grep "__tests__" frontend/tsconfig.json` 未命中 → MAJOR；禁止未验证 vitest 存在时直接 `npx vitest run`（交互式卡死）
- **F-REVIEW-219 ANTD-CHINESE-BUTTON-TEST-REGEX**（维度 12 可测试性，MINOR）：antd Button 中文文案测试断言必须用 `getByRole('button', { name: /文\s*案/ })` 正则兼容空格；原因：antd v5 Space compact 自动在中文间插入空格，渲染为 "文 案"；扫描命令 `grep "getByText.*[\u4e00-\u9fa5]" frontend/src/**/__tests__/` 命中 antd Button 相关 → MINOR

**扩展检查点**（不新增编号）：
- **F-REVIEW-154 INTERCEPTOR-STATUS-CODE-DISCRIMINATION 扩展**：补充「防抖标记 + location.replace」检查点——401 拦截器跳转必须用模块级 `isRedirecting` 防抖标记防止并发触发，且必须用 `location.replace` 而非 `location.href` 避免产生历史记录导致后退回到错误态

**4 维度复盘要点**：

1. **成功步骤**：构建 SPA 渲染容错三件套（全局 ErrorBoundary + lazyRetry + 路由级 resetKeys）形成三层降级（页面级 fallback UI → 路由级 reset 自动恢复 → 懒加载重试恢复）；API 数组字段统一 `|| []` 兜底切断 TypeError 引发白屏的入口；401 拦截器引入 `isRedirecting` 防抖标记 + `location.replace` 消除并发跳转竞态
2. **不确定性与失败点**：
   - vitest 未安装时 `npx vitest run` 触发交互式安装提示卡死（必须先 `Test-Path node_modules/.bin/vitest` 验证）
   - antd v5 Space.Compact 在中文字符间插入空格导致 `getByText('重试')` 失败（需用 `getByRole('button', { name: /重\s*试/ })` 正则兼容）
   - tsconfig 未排除 `__tests__` 导致 `tsc --noEmit` 类型检查包含测试文件产生错误（需在 `exclude` 添加 `src/**/__tests__/**` 等模式）
   - resetKeys 误传对象/数组引用导致 ErrorBoundary 永远不重置（必须基本类型数组）
3. **可抽象的固定流程**：
   - SPA 渲染容错三件套部署顺序：① App.tsx 全局 ErrorBoundary → ② MainLayout 路由级 ErrorBoundary（resetKeys=[location.pathname]）→ ③ lazyRetry 包装所有 lazy() 调用
   - API 数组字段防御：消费 API 响应的数组字段必须 `|| []`，对象字段必须 `?.`，禁止裸访问 `res.items[0]`
   - 测试环境前置校验：运行测试前验证 vitest 可执行文件 + 配置文件 + tsconfig exclude 三件套
   - antd 中文断言：所有 antd v5 中文 Button/Tag/Alert 测试必须用 `getByRole + 正则 \s*` 兼容空格
4. **适用场景**：所有 React SPA（Vite/Webpack 代码分割）、antd v5 项目、首次引入 vitest 的项目。**不适用场景**：Next.js SSR（ErrorBoundary 由框架提供）、纯静态 HTML、React Native、无代码分割的单 bundle

**配置节点**：新增 `spa_white_screen_resilience` 节点，包含 8 个子节点（globalErrorBoundary / lazyRetry / routeErrorBoundary / apiArrayDefense / http401Debounce / resetKeysConstraint / vitestEnvChecklist / antdChineseButtonTestRegex）对应 6 个新检查点 + F-REVIEW-154 扩展 + resetKeys 约束。

详细审查规则落地到 `references/hooks-and-state.md §10`（F-REVIEW-214/215/216）和 `references/code-quality.md §12`（F-REVIEW-217/218/219）。

---

## v4.52.0 (2026-07-18) — 前端快照职责分离与多用户上下文传递

### 复盘背景

2026-07-18 卖家评估菜单 Bug 2B：后端 `_apply_positive_fields` 用 items 表最新价格覆盖 payload.item_price，`_filter_price_range` 也用覆盖后的最新价格过滤，导致官方采集更新价格后旧 eval 事件被误判超范围隐藏。

前端侧需要：
1. 区分"评估时价格"和"最新价格"的展示
2. 确保多用户上下文（Cookie/credentials）在所有 API 调用中正确传递
3. 业务 440 不触发全局登出

### 成功执行任务的完整步骤

1. **Phase 1 根因调查**：识别后端 enrich 覆盖导致前端展示与过滤混淆
2. **Phase 2 模式分析**：对比评估时快照 vs 最新值的职责
3. **Phase 3 假设测试**：6 个场景测试验证 _eval_snapshot_price 逻辑
4. **Phase 4 实施修复**：后端保存快照 + 过滤优先用快照

### 可抽象的固定流程

1. **前端快照与最新值职责分离**：过滤组件基于评估时价格，展示组件基于最新价格
2. **多用户上下文传递**：所有 API 调用必须携带认证字段，业务 440 不触发全局登出

### 新增检查点

| 检查点 ID | 名称 | 维度 | 核心规则 |
|-----------|------|------|----------|
| F-REVIEW-197 | SNAPSHOT-FILTER-DISPLAY-SEPARATION | 7 | 前端展示价格时需区分"评估时价格"和"最新价格"；过滤组件基于评估时价格，展示组件基于最新价格 |
| F-REVIEW-198 | MULTI-USER-CONTEXT-PROPAGATION | 28 | 所有 API 调用必须携带认证字段（Cookie/credentials:include）；axios 拦截器仅在 401 且 detail === "Unauthorized" 时重定向；业务 440 走业务逻辑 |

### 配置节点

新增 `data_propagation_frontend` 配置节点，包含 2 个子节点对应 2 个检查点。

### 关联文档

- 编码规范：[data-propagation.md](../../../xianyu-hunter-dev/assets/guides/coding-rules/data-propagation.md)
- 多用户认证：[multi-user-auth.md](../../../xianyu-hunter-dev/assets/guides/coding-rules/multi-user-auth.md)

---

## v4.50.0 (2026-07-17) - Backend Cookie Healing Response & Health Display
**新增检查点**：F-REVIEW-HEALING-RESPONSE-HANDLING / F-REVIEW-COOKIE-HEALTH-DISPLAY
- **F-REVIEW-HEALING-RESPONSE-HANDLING**: 前端正确处理后端 403（cookie 失效）/ 441（反爬拦截）/ 410（商品下架）三种状态码，从后端 reason 字段提取错误消息而非硬编码
- **F-REVIEW-COOKIE-HEALTH-DISPLAY**: 前端 Cookie 健康状态显示与后端自愈状态一致，轮询 /cookies/layers 获取最新状态，登录后健康探测有 UI 反馈

**维度**：7（API 调用规范 / UI 状态与操作按钮分离）
**配置节点**：`healing_response_handling` / `cookie_health_display`
**来源**：后端 Cookie 自愈机制修复（多级自愈：token 刷新 → cookie 强制注入 → 放弃；诊断日志；批次级预检；登录后健康探测）

---

## v4.47.0 (2026-07-13) - Per-Preset Credential Frontend Contract
**新增检查点**：F-REVIEW-170~172
- **F-REVIEW-170: PRESET-APPLY-NO-KEY-FORWARD**：applyPreset 不应发送 api_key 字段
- **F-REVIEW-171: MASKED-KEY-UI-HANDLING**：脱敏值 ****xxxx 不应写入 password input
- **F-REVIEW-172: EMBEDDING-PRESET-KEY-FOLLOW**：Embedding 预设切换同样独立管理 key

**维度**：39（Per-Preset Credential Frontend Contract）
**配置节点**：credential_storage.frontend_contract / credential_storage.embedding_independent_slots / ui.masked_key_handling

---
# 版本演进详细复盘记录（Version Changelog）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)
> **用途**：存放各版本的完整复盘详情（Sequential Thinking 复盘法、根因分析、检查点详情），SKILL.md 顶部仅保留索引表格，需要查阅历史决策与根因时再读取本文件。
> **维护原则**：新增版本复盘时按版本号倒序插入到本文件最上方，SKILL.md 顶部表格仅更新一行索引。

---

## v4.50.0（2026-07-17）后端 Cookie 自愈机制前端协同复盘

**复盘方法**：Sequential Thinking 4 维度复盘法
**复盘范围**：最近 3 次会话的 Cookie 自愈机制修复过程（后端新增多级自愈、诊断日志、批次级预检、登录后健康探测）
**问题归纳**：2 大类（A 后端自愈响应处理 / B Cookie 健康状态显示一致性）

**后端修复概要**：
- 后端 `_refresh_token_and_retry_detail` 实现两级自愈：第一级刷新 _m_h5_tk token，第二级从 cookie_store 强制注入完整 cookie
- 后端 `_log_cookie_diagnostics` 在两级自愈均失败时记录诊断日志
- 后端 `_sync_cookie_before_batch` 批次级预检（注入后调用 ensure_official_cookies）
- 后端 `_post_login_cookie_health_check` 登录后健康探测（检查身份 cookie 完整性）
- 后端在 Cookie 失效时返回 403 状态码，错误消息含 `login session expired (reason: home_title_redirect), please re-login`

**新增审查要点**：2 个 F-REVIEW 检查点（维度 7）

- **F-REVIEW-HEALING-RESPONSE-HANDLING**（维度 7 API 调用规范）：前端必须区分后端 403（cookie 失效需重登录）/ 441（反爬拦截可恢复）/ 410（商品下架）三种状态码并独立分支处理；错误消息必须从后端响应体 `reason` 字段提取（如 `home_title_redirect`），而非硬编码前端文案；403 分支必须引导用户重新登录而非显示模糊错误；441 分支不得跳转登录页（反爬拦截可恢复）；410 分支不得触发重登录流程（商品下架与登录态无关）
- **F-REVIEW-COOKIE-HEALTH-DISPLAY**（维度 7 UI 状态与操作按钮分离）：前端 Cookie 健康状态显示必须与后端自愈状态一致；后端自愈成功（valid=true）时前端不得仍显示"失效"；前端必须轮询 `/cookies/layers` 端点获取最新状态（轮询间隔来自配置，禁止硬编码）；轮询失败时禁止强制设为"失效"（应保持上一次成功状态）；登录后健康探测结果必须有 UI 反馈（如 toast 提示"登录成功，Cookie 已验证"或"登录成功但部分 Cookie 缺失"）

**4 维度复盘要点**：

1. **成功步骤**：后端实现多级自愈机制（token 刷新 → cookie 强制注入 → 放弃），自愈耗尽时返回 403 + reason 字段（含 `home_title_redirect` 等诊断信息）；前端需正确区分 403/441/410 三种状态码并从 reason 字段提取错误消息
2. **不确定性与失败点**：前端可能不区分 403/441/410 三种状态码，导致对 441（反爬可恢复）误跳转登录页或对 410（商品下架）触发重登录；前端可能硬编码错误文案而丢失后端 reason 字段的诊断信息；前端可能不轮询 `/cookies/layers` 导致后端自愈成功后仍显示"失效"（状态不一致）；登录后健康探测结果可能无 UI 反馈
3. **可抽象的固定流程**：① 前端按 HTTP 状态码分支处理（403→重登录 / 441→稍后重试 / 410→商品下架），从后端 reason 字段提取错误消息；② Cookie 健康状态显示轮询 `/cookies/layers`，轮询间隔来自配置，轮询失败保持上次状态；③ 登录后健康探测结果通过 toast/message 反馈给用户
4. **适用场景**：与后端采集 API 交互的前端页面（商品详情、官方采集、实时查询、批量采集等）；显示 Cookie 健康状态的前端组件（Cookie 分层管理卡片、登录页面、反爬登录管理、关于页面）。**不适用场景**：纯前端页面（无后端 API 调用）、公开 API（无需认证）、不显示 Cookie 状态的页面、纯后端内部逻辑（前端不感知）

自动化扫描从 104 项扩展到 106 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `healing_response_handling` + `cookie_health_display` 节点管理）与适用/不适用场景说明。详细审查规则落地到 `references/api-contract.md §11` 和 `references/state-and-consistency-checks.md` 维度 7 章节。后端对应规范为后端 Cookie 自愈机制修复（`_refresh_token_and_retry_detail` / `_log_cookie_diagnostics` / `_sync_cookie_before_batch` / `_post_login_cookie_health_check`）。

---

## v4.33.0（2026-07-05）全量复盘与审查要点同步

**复盘方法**：Sequential Thinking 18 步四维度复盘法
**复盘范围**：2026-07-03 至 2026-07-05 全量问题（80+ topics）
**问题归纳**：7 大类（A 时区 / B 命名 / C 状态持久化 / D Cookie 认证 / E 前端交互 / F 数据传递 / G 鲁棒性）

**新增审查要点**：14 个 F-REVIEW checkpoints（F-REVIEW-96 ~ F-REVIEW-109，对应任务原编号 F-REVIEW-84~97 因冲突调整为 96~109）

- **React 组件规范维度**：2 条
  - F-REVIEW-EFFECT-MINIMIZE（useEffect 副作用最小化，规范引用 EFFECT-01）
  - F-REVIEW-STATE-ATOMICITY（状态切换原子性，规范引用 STATE-01）
- **性能与竞态维度**：2 条
  - F-REVIEW-SSE-CONN-MGMT（SSE 连接管理三要素，规范引用 SSE-01）
  - F-REVIEW-ASYNC-RACE-GUARD（异步竞态防护，规范引用 RACE-01）
- **AntD 主题维度**：2 条
  - F-REVIEW-THEME-DYNAMIC-ADAPT（主题色动态适配，规范引用 THEME-01）
  - F-REVIEW-EMBEDDED-LAYOUT-HEIGHT（嵌入式布局高度，规范引用 LAYOUT-01）
- **组件注册维度**：1 条
  - F-REVIEW-COMPONENT-REGISTRY（组件注册完整性，规范引用 REGISTRY-01）
- **数据展示维度**：3 条
  - F-REVIEW-FILTER-TRANSPARENCY（过滤透明化，规范引用 FILTER-02）
  - F-REVIEW-DATA-SOURCE-VERIFY（数据源正确性验证，规范引用 SOURCE-01）
  - F-REVIEW-STATS-RANGE-CALIBRATE（统计范围校准，规范引用 RANGE-01）
- **UI 语义维度**：1 条
  - F-REVIEW-UI-SEMANTICS-SPLIT（按钮与状态语义分离，规范引用 UI-SEMANTICS-01）
- **状态持久化维度**：1 条
  - F-REVIEW-PERSIST-BUSINESS-SWITCH（用户可配置开关持久化，规范引用 PERSIST-01）
- **API 契约维度**：2 条
  - F-REVIEW-ERROR-MESSAGE-PASS（错误消息透传，规范引用 ERROR-01）
  - F-REVIEW-API-CONTRACT-CONSISTENCY（API 契约一致性，规范引用 CONTRACT-01）

**审查流程优化**：4 阶段流水线（上下文加载 → 分层扫描 → 优先级分类 → 结果呈现）
- 原 5 阶段闭环（Phase 0-4）重组为 4 阶段流水线
- 阶段 1 新增 `coding_standards` 节点加载 + `coding-rules/` 主题文件加载 + 任务类型识别
- 阶段 2 保留常规规则匹配 + 配置驱动检查 + 硬约束合规性检查三个子阶段
- 阶段 3 新增 P0/P1/P2/P3 四级优先级分类（P0 阻塞合并，P1 强烈建议修复，P2/P3 记录 backlog）
- 阶段 4 强化结构化报告呈现

**结果呈现优化**：结构化报告模板（审查概览 + 问题详情两段式）
- 审查概览：审查范围/审查维度/问题统计 P0/P1/P2/P3/规范版本/配置版本/审查日期
- 问题详情：每个问题含 8 要素（编号/维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示例）
- 与原 Template A/B 并存，按 `report.format` 选择

**配置化**：新增 `coding_standards` 节点，所有 14 项新检查点的参数通过 `config.yaml` 管理
- `coding_standards.effect.disallow_reset_user_controlled_state` / `merge_strategy`
- `coding_standards.sse.max_reconnect_attempts` / `polling_fallback_interval` / `visibility_reconnect`
- `coding_standards.theme.disallow_hardcoded_colors` / `colors.light` / `colors.dark`
- `coding_standards.layout.disallow_minheight_100vh_in_embedded`
- `coding_standards.registry.check_components`
- `coding_standards.filter.summary_enabled`
- `coding_standards.ui_semantics.button_text_must_be_action` / `status_display_must_be_state`
- `coding_standards.persist.business_switch_must_persist` / `storage_key_prefix`
- `coding_standards.race.check_request_id`
- `coding_standards.error.require_extract_api_error`
- `coding_standards.contract.check_ts_interface_match`
- `coding_standards.source.verify_data_source`

**规范源联动**：每个 checkpoint 引用 `xianyu-hunter-dev/references/coding-rules/` 中的规范编号（如 EFFECT-01/SSE-01/THEME-01 等），审查时加载规范详情，实现"检查点 ↔ 规范源"双向追溯。

**版本号调整说明**：任务原指定版本号 v4.28.0（基于旧版本认知 v4.27.0），但文件实际已演进至 v4.32.0（v4.28.0/v4.30.0/v4.31.0/v4.32.0 已存在），故调整为 v4.33.0。checkpoint 编号原指定 F-REVIEW-84~97，但 84-87 已被占用（F-REVIEW-PRECHECK-API-DELEGATION/MOCK-FIELD-SET-SYNC/MULTI-USER-CONTEXT-ISOLATION/AUTH-TOKEN-COOKIE-HANDLING），故调整为 F-REVIEW-96~109（与版本表 v4.32.0 的 95 衔接）。

------

## v4.47.0（2026-07-13）快捷预设独立 API Key 管理复盘

**复盘方法**：Sequential Thinking 4 维度复盘法
**复盘范围**：2026-07-10 AI 服务快捷预设 API Key 未跟随变化 Bug
**问题归纳**：1 大类（A 凭据切换未隔离）

**修复步骤**：
1. **根因定位**：pi_ai.py 的 save_ai_config() 只更新全局 openai_api_key，切换预设时未保存/恢复对应预设的 Key
2. **最小修改**：
   - 后端 secrets.py 新增 AI_PRESET_KEY_PREFIX 和 i_preset_key_name() 函数，按预设 ID 生成独立密钥槽
   - 后端 pi_ai.py 新增 AI_PRESET_BASE_URLS 字典和 _preset_id_for_base_url() 反向查找函数
   - AIConfigBody 新增 preset_id: Literal[...] 字段，get_ai_config() 返回 preset_id
   - save_ai_config() 新增预设切换逻辑：首次切换时迁移全局 Key 到原预设槽，目标预设 Key 自动恢复
   - 后端 config.py _load_secrets_from_keyring() 将 if api_key: 改为 if api_key is not None:，确保空字符串能覆盖旧 .env 值
   - 前端 AIConfig/index.tsx 新增 preset_id 状态，pplyPreset() 携带 preset_id 并接收后端返回的脱敏 Key
   - 前端 ModelConfigForm.tsx 新增独立"保存配置"按钮，文本解析模型不再依赖"测试连接"落盘
   - 前端 pi/ai.ts PUT 响应类型改为返回 AIConfig 完整对象
3. **验证策略**：
   - 后端：3 条 pytest 用例（预设切换 Key 恢复、独立保存 Key、空值覆盖 .env）全部通过
   - 前端：vitest 单测验证保存按钮存在，tsc --noEmit 类型检查通过
   - 构建：frontend/build 成功，无类型错误

**4 维度复盘要点**：
1. **成功步骤**：基于 TDD Red-Green-Refactor 流程，先写失败测试再实现最小代码；使用 keyring 系统密钥库存储预设 Key 而非 .env 明文；PUT 响应回显完整配置避免额外 GET 调用
2. **不确定性与失败点**：
   - RED 阶段测试因 KeyError 失败（预设密钥槽不存在）- 符合预期
   - 前端 vitest 首次运行因 antd window.matchMedia mock 缺失失败 - 补充 mock 后通过
   - config.py 中 _load_secrets_from_keyring 原有 if api_key: 判断在 keyring 无值时不会覆盖 .env 遗留值 - 这是最隐蔽的根因
3. **可抽象的固定流程**：
   - 凭据切换类功能必须遵循：存储槽设计 -> 迁移逻辑 -> 切换原子性 -> 空值覆盖 -> 更新回显 五步法
   - 表单配置字段必须有独立保存入口，不能与测试/验证等次要操作耦合
   - PUT/PATCH 端点必须返回完整更新状态，前端基于响应更新而非额外请求
4. **适用场景**：任何涉及预设/供应商/配置组切换的凭据管理（AI 服务、通知渠道、代理、隧道等）
**不适用场景**：无凭据字段的纯展示表单、一次性操作表单

**新增审查要点**：F-REVIEW-167/168/169（前端）/ B-REVIEW-195/196/197/198/199（后端）
**配置参数**：credential_storage.per_preset_slots、config_save.independent_button_required、pi.mutation_response_echo、pi.literal_preset_ids
**历史教训**：if api_key: 隐式布尔判断掩盖了空字符串语义，导致 keyring 无值时 .env 遗留 Key 重新激活；修复为 if api_key is not None: 显式判断。

---


## v4.32.0 多用户认证上下文隔离复盘（前端侧同步原则）

基于 2026-07-05 完成的 MU2 Sprint（认证中间件改造 + CookieStore 扩展 user_id 维度）复盘（使用 Sequential Thinking 8 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景），新增 2 项 F-REVIEW 检查点（新增维度 28 多用户认证上下文隔离）：

- **F-REVIEW-MULTI-USER-CONTEXT-ISOLATION**（维度 28）：前端按 user_id 维度隔离状态/缓存/请求路径，禁止全局单例 store 承接多用户数据，用户切换时必须调用 `queryClient.clear()` + `useGlobalStore.getState().reset()` + `usePersistentState.invalidate()` 清空旧用户缓存
- **F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING**（维度 28）：认证 token 必须走 httpOnly cookie（禁止 localStorage），fetch 必须显式 `credentials: 'include'`，axios 必须 `withCredentials: true`，htmx 通过 `<meta name="htmx-config">` 配置 credentials；401/440/441/403 必须按状态码语义分支处理（跳登录页/跳重新登录页/刷新 token/提示无权限），禁止所有认证失败一律跳登录页

**4 维度复盘要点**：

1. **成功步骤**：MU2 Sprint 完成后端 CookieStore 按 `cookies_{uid}.json` 分文件存储 + `_cache: dict[str, tuple[dict, float]]` 分桶缓存 + 中间件三路校验（管理令牌 + 用户会话 + 401）+ `make_auth_response` 通过 set-cookie 写入 httpOnly xh_token cookie
2. **不确定性与失败点**：前端 Zustand store 仍用全局单例承接订单/偏好数据，用户切换时未清空缓存导致跨用户数据泄漏；部分 fetch 请求遗漏 `credentials: 'include'` 导致 cookie 不传递；所有 401 一律跳登录页，用户会话过期（应跳重新登录页）和 Cookie 过期（应刷新 token）被误判为"未登录"
3. **可抽象的固定流程**：① 多用户场景下用户特定状态必须按 user_id 分桶（`Record<UserId, UserState>`）或切换时 `store.reset()`；② 认证 token 走 httpOnly cookie + 前端 `credentials: 'include'`；③ 状态码语义精细化分支（401/440/441/403 各自对应不同前端动作）
4. **适用场景**：多用户系统（用户切换/多账号管理）、多租户 SaaS、所有涉及认证的 API 请求、SSE 事件流认证、多角色权限控制。**不适用场景**：单用户系统（无用户切换需求）、纯内部工具（无登录态）、纯公共 API（无需认证）、第三方 OAuth 回调（按 OAuth 规范处理）

自动化扫描从 93 项扩展到 95 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `multi_user_context_isolation` + `auth_token_cookie_handling` 节点管理）与适用/不适用场景说明。详细编码规范整合到 `xianyu-hunter-dev` v4.30.0 的 step 134-137（多用户资源隔离 + 认证中间件多路校验 + 会话 token 安全管理 + 快照与实时数据覆盖决策）。后端对应规范为 `xianyu-backend-code-review` v4.28.0 的维度 21（5 项 B-REVIEW：B-REVIEW-MULTI-USER-RESOURCE-ISOLATION / B-REVIEW-AUTH-MULTI-PATH-VALIDATION / B-REVIEW-SESSION-TOKEN-SECURITY / B-REVIEW-SNAPSHOT-REALTIME-OVERWRITE / B-REVIEW-USER-IDENTITY-PRIORITY）。

---

## v4.31.0 业务关键字常量集中管理与字段名大小写敏感复盘

基于 2026-07-05 解决的 3 类前端反模式复盘（业务文案硬编码 / 事件类型前缀过滤 / 字段名大小写不一致；使用 Sequential Thinking 4 维度复盘法），新增 3 项 F-REVIEW 检查点（新增维度 27 业务关键字常量集中管理与字段名大小写敏感）：

- **F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION**（维度 27）：前端使用业务关键字文案（"卖掉了"/"已售"/"已下架"等业务状态判定文本）时必须从后端配置端点（`/api/config/text_features`）拉取而非硬编码，前端通过共享 helper 函数（`isItemSoldByText(text)`）调用后端配置
- **F-REVIEW-EVENT-TYPE-EXACT-MATCH**（维度 27）：前端按事件类型过滤必须用 `===` 精确匹配或 `Set.has()`，禁止 `startsWith()` / `indexOf()` 前缀匹配（除非是配置节点 `event_type_exact_match.allowed_prefix_grouping_scenarios` 允许的统计/日志场景）
- **F-REVIEW-FIELD-NAME-CASE-SENSITIVE**（维度 27）：前端访问后端 API 响应字段时字段名大小写必须与后端 Pydantic 模型完全一致（snake_case），禁止用 `as any` 绕过类型检查

**4 维度复盘要点**：

1. **成功步骤**：后端 `collector_utils.py` 集中 `SOLD_TEXT_KEYWORDS` + `check_text_sold()` 统一入口 + 配置节点 `config.yaml#external_platform.text_features`，前端通过 `/api/config/text_features` 拉取关键字列表
2. **不确定性与失败点**：前端硬编码业务关键字与后端规则不一致（后端新增"已售出"文案前端未同步）；`event.type.startsWith('eval.')` 误包含 `eval.passed`/`eval.failed`/`eval.error` 子类型；前端用 `data.totalForType` 访问后端 `total_for_type` 字段（驼峰 vs snake_case）导致显示 0 条；后端 `ChatbotRepository` 用 `this._Session` 访问定义的 `this._session` 私有属性（大小写不一致）
3. **可抽象的固定流程**：① 业务关键字从后端配置拉取 + 共享 helper 函数判断；② 事件类型 `===` 精确匹配或 `Set<string>` 集合判断；③ 前端 `api/types.ts` 字段名与后端 Pydantic 模型一一对应 + grep 双向匹配验证
4. **适用场景**：前端业务状态判定（商品售出/订单状态/用户角色）、SSE 事件处理、API 响应消费、Zustand store 字段读写、测试 mock 数据字段名。**不适用场景**：纯前端 UI 文案、组件内部状态文本、路由参数、纯统计/日志场景的事件前缀匹配

自动化扫描从 90 项扩展到 93 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `business_keyword_and_field_contract` 节点管理）。详细编码规范整合到 `xianyu-hunter-dev` v4.31.0 的 step 129/130/131。后端对应规范为 `xianyu-backend-code-review` v4.31.0 的维度 30（6 项 B-REVIEW）。

---

## v4.30.0 跨边界访问契约前端侧复盘

基于 2026-07-05 解决的 3 类跨边界访问问题复盘（时区感知 datetime 渲染契约 / 私有 Hook 封装 / 命名一致性；使用 Sequential Thinking 4 维度复盘法），新增 3 项 F-REVIEW 检查点（新增维度 26 跨边界访问契约前端侧）：

- **F-REVIEW-DATETIME-RENDER-CONTRACT**（维度 26）：前后端 datetime 交换必须用 ISO 8601 带时区格式（`2026-07-05T10:30:00+08:00`），前端渲染必须用 `dayjs` 等库解析时区后按用户本地时区显示，禁止直接 `new Date(str)` 解析 naive datetime
- **F-REVIEW-PRIVATE-HOOK-ENCAPSULATION**（维度 26）：自定义 Hook 的内部状态（如 `loadingRef` / `requestIdRef` / `cache`）必须封装在 Hook 闭包内，禁止暴露给消费方，Hook 只返回公共 API（如 `{ data, error, loading, refetch }`）
- **F-REVIEW-NAMING-CONSISTENCY-FRONTEND**（维度 26）：前端命名必须与后端契约保持一致（字段名 snake_case / 函数名 lowerCamelCase / 类型名 PascalCase），禁止前端独立命名导致前后端不一致

**4 维度复盘要点**：

1. **成功步骤**：基于 `repo_chatbot.py` 的 `TypeError: can't subtract offset-naive and offset-aware datetimes` 修复经验，确立 datetime 跨边界传递必须带时区的契约
2. **不确定性与失败点**：后端 `_utcnow().replace(tzinfo=None) - row.created_at` 混用 naive/aware datetime 触发异常；前端自定义 Hook 暴露内部 `loadingRef` 导致消费方误修改；前端用驼峰命名而后端用 snake_case 导致字段对不上
3. **可抽象的固定流程**：① 跨边界 datetime 必须 ISO 8601 + 时区；② Hook 内部状态闭包封装；③ 命名风格前后端一致（snake_case 字段 / lowerCamelCase 函数 / PascalCase 类型）
4. **适用场景**：前后端数据交换、自定义 Hook 设计、跨模块命名约定。**不适用场景**：纯前端内部状态（无后端契约）、第三方库内部实现、CSS 类名（前端独立命名）

自动化扫描从 87 项扩展到 90 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `cross_boundary_contract_frontend` 节点管理）。详细编码规范整合到 `xianyu-hunter-dev` v4.30.0 的 step 132/133。后端对应规范为 `xianyu-backend-code-review` v4.30.0 的 B-REVIEW-DATETIME-TIMEZONE-AWARE / B-REVIEW-PRIVATE-ATTR-ENCAPSULATION / B-REVIEW-NAMING-CONSISTENCY。

---

## v4.28.0 工作流元规范硬约束复盘（前端侧同步原则）

基于 xianyu-hunter-dev meta-rules #21-24（错误处理决策树 / 批处理熔断 / 资源生命周期 / 跨组件状态同步）的前端侧同步复盘（使用 Sequential Thinking 4 维度复盘法），新增 4 项 F-REVIEW 检查点（维度 19/6/10/11）：

- **F-REVIEW-WF-ERROR-HANDLING**（维度 19）：前端关键路径（认证/支付/会话初始化）的 `.catch` 禁止空实现或仅 `console.error`，必须分级处理（warning→`message.warning` / error→`message.error`），与 v4.7 异步三态反馈配合
- **F-REVIEW-WF-BATCH-CIRCUIT-BREAKER**（维度 6）：前端调用批量接口时必须展示熔断状态（running/paused/failed/completed），熔断后必须展示"已成功 X 项 + 剩余 Y 项 + 失败原因 Z + 恢复入口"
- **F-REVIEW-WF-RESOURCE-LIFECYCLE**（维度 10）：`new Proxy()` / `new MutationObserver()` / `new IntersectionObserver()` / `new EventSource()` / `new WebSocket()` 等长生命周期资源必须赋值给实例属性或 ref，禁止赋值给局部变量后被 GC 回收；必须在 `useEffect` cleanup 中调用 `close()`
- **F-REVIEW-WF-STATE-SYNC**（维度 11）：跨组件状态同步必须用单一可信源（`useCookieLayersStore` / `useAuthStore` / `useBatchRefreshConfigStore`）+ 统一 refetch 入口 + SSE 推送，禁止前端用 30/60 秒 TTL `setInterval` 同步跨进程状态，禁止 `usePersistentState` 重复持久化后端已有 GET API 的字段

**4 维度复盘要点**：

1. **成功步骤**：抽取 xianyu-hunter-dev meta-rules #21-24 对应的前端检查点，确保前后端工作流元规范一致
2. **不确定性与失败点**：meta-rule 在前端场景的适用边界（如批处理熔断前端如何展示、资源生命周期前端 GC 风险、跨组件状态同步前端 TTL 兜底禁止）
3. **可抽象的固定流程**：4 项 meta-rule 在前端的检查模式（决策树/状态展示/资源持有/单一可信源），所有规则配置驱动
4. **适用场景**：所有 useEffect / fetch / axios / EventSource 代码路径、批量操作 UI、跨组件状态同步。**不适用场景**：测试 mock / 一次性脚本 / 短生命周期对象

自动化扫描从 83 项扩展到 87 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的 `workflow_meta_rules_frontend` 节点管理）。详细编码规范整合到 `xianyu-hunter-dev` v4.28.0 的 meta-rules #21-24。后端对应规范为 `xianyu-backend-code-review` v4.28.0 的工作流元规范检查点。

---

## v4.27.0 端到端失败原因链与数据完整性闭环复盘（前端侧同步原则）

基于本轮对话解决的 `Failed to collect item detail: page unavailable or login expired` 问题复盘（根因：代码被回退 + 服务未重启双重原因导致修复未生效；使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景），新增 3 项 F-REVIEW 检查点（维度 25 端到端失败原因链前端侧同步原则）：

- **F-REVIEW-ERROR-CODE-BRANCH**：前端错误展示必须按后端返回的 `error_code` 字段分支而非按文案子串判断，禁止 `if (msg.includes('expired'))` 等子串匹配模式，应改为 `switch (err.error_code) { case 'token_invalid': ... }`，与后端 `failure_reason_propagation.reason_enum` 一一对应（命名风格以后端为准，统一 lower_snake_case）
- **F-REVIEW-PRECHECK-API-DELEGATION**：前端调用后端 API 前若需预检数据完整性，必须调用后端预检端点（如 `/api/cookies/precheck`）而非前端自行判断 cookie 数量/字段完整性，前端不具备后端业务规则的完整上下文
- **F-REVIEW-MOCK-FIELD-SET-SYNC**：前端 mock 数据必须覆盖完整字段集与后端 Pydantic 模型保持一致，新增后端字段后前端 mock 必须同步补齐，避免测试通过但生产环境类型不一致

自动化扫描从 80 项扩展到 83 项；所有新检查点强调配置驱动（参数在 `config.yaml` 的 `failure_reason_chain_frontend` 节点管理）与适用/不适用场景说明。详细编码规范整合到 `xianyu-hunter-dev` v4.27.0 的 step 123-128。后端对应规范为 `xianyu-backend-code-review` v4.27.0 的维度 29（6 项 B-REVIEW）。

---

## v4.26.0 API三态语义/错误处理/默认值操作符复盘（前端侧）

基于本轮对话解决的「任务级配置覆盖功能开发 + 代码审查」复盘（使用 Sequential Thinking 8 步复盘法），新增 3 项 F-REVIEW 检查点：

- **F-REVIEW-THREE-STATE-NULL-SEMANTICS**（维度 7）：PATCH/PUT 请求清除覆盖字段必须显式传 null，禁止用省略字段代替传 null
- **F-REVIEW-ERROR-HANDLING-CONSISTENCY**（维度 20）：API 调用的 catch 块必须用 extractApiError 提取具体错误信息，禁止 `message.error('保存失败')` 等无信息提示
- **F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY**（维度 4）：默认值场景统一用 `??` 而非 `||`，只有需要同时过滤 0/''/false 时才用 `||`

自动化扫描从 77 项扩展到 80 项。详细编码规范整合到 xianyu-hunter-dev v4.26.0 的 step 117/121/122。后端对应规范为 xianyu-backend-code-review v4.26.0 的 B-REVIEW-EXCLUDE-UNSET-CHECK / B-REVIEW-NOT-NULL-NONE-DEFENSE。

---

## v4.25.0 数据库迁移块独立容错与关键路径异常可见性复盘（前端侧同步原则）

基于本轮对话解决的 `sqlite3.OperationalError: no such column: notifications.read_at` 问题复盘（使用 Sequential Thinking 6 步复盘法），**不新增 F-REVIEW 检查点**（自动化扫描项保持 77 项不变）。原因：本次问题为纯后端数据库迁移问题，前端不直接处理数据库迁移，业务场景过于狭窄。

仅在前端层面同步以下原则：

1. 前端若涉及"启动时初始化"逻辑（如 `useEffect` 中的初始化请求、Zustand store 的 `hydrate` 操作），错误处理必须用 `console.error` 输出完整错误对象而非 `console.warn(String(e))` 丢失堆栈
2. 前端初始化逻辑中有多个独立初始化步骤时（如并行 fetch 多个 API），每个步骤应独立 catch 而非统一 try/catch 吞掉异常导致后续步骤跳过
3. 前端若展示后端迁移状态或数据库 schema 信息（如"关于"页面展示数据库版本），应从后端 `/api/about` 等端点获取而非前端硬编码

本次复盘的详细编码规范整合到 `xianyu-hunter-dev` v4.25.0 的 step 116（仅后端规范），后端审查规则落地到 `xianyu-backend-code-review` v4.25.0 的 B-REVIEW-MIGRATION-BLOCK-ISOLATION（第 110 项）/ B-REVIEW-CRITICAL-PATH-NO-SWALLOW（第 111 项）。

---

## v4.24.0 用户偏好类 UI 状态持久化复盘（前端侧）

基于本轮对话解决的「批量采集菜单相关参数开关应支持持久化」需求复盘（使用 Sequential Thinking 7 步复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-UI-PREFERENCE-PERSISTENCE**（维度 10）：用户偏好类 UI 状态（自动刷新/视图模式/列显隐/折叠/展开/主题偏好/最近使用列表/记住上次选中项）必须使用项目既有 `frontend/src/hooks/usePersistentState.ts` 持久化，禁止裸 useState、禁止自行实现 localStorage 读写、禁止引入第三方持久化库

自动化扫描从 76 项扩展到 77 项。核心机制：项目已有统一封装的 usePersistentState hook（含防抖写入、数据验证、localStorage 不可用回退到内存 Map）。详细编码规范整合到 `xianyu-hunter-dev` v4.24.0 的 step 115。后端对应规范为 `xianyu-backend-code-review` v4.24.0 的复盘记录同步原则（不新增 B-REVIEW 检查点，纯前端问题）。

---

## v4.23.0 模型能力元数据集中展示与降级状态可视化复盘（前端侧）

基于本轮对话解决的"LLM 深度分析因 vision 模型不支持 image_url 触发 400"问题复盘（使用 Sequential Thinking 4 维度复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION**（维度 11）：前端展示 LLM 模型能力时必须集中展示（从 `/api/config` 或 `/api/about` 统一获取，禁止每页独立 fetch/内联判断），用户上传图片/启用 tool 时前端必须根据能力位给出降级状态可视化，关键字列表仅在后端 `api_ai._VISION_CAPABLE_KEYWORDS` 一处维护，前端抽 `isVisionCapable()` + `getCapabilityDisplay()` 共享函数到 `frontend/src/utils/modelCapability.ts`

自动化扫描从 75 项扩展到 76 项。详细编码规范整合到 `xianyu-hunter-dev` v4.21.0 的 step 112-114。后端对应规范为 `xianyu-backend-code-review` v4.23.0 的 B-REVIEW-LLM-CAPABILITY-DISPATCH / B-REVIEW-SHARED-UTIL-CENTRALIZATION / B-REVIEW-SILENT-DOWNGRADE-PRECHECK。

---

## v4.22.0 PWA 缓存验证复盘（前端侧）

基于本轮对话解决的「批量采集执行历史 Tab2 前端不可见」问题复盘（使用 Sequential Thinking 6 步复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-PWA-CACHE-VERIFY**（维度 13）：前端功能不可见时必须从源码→构建产物→sw.js 预缓存清单三层验证，vite-plugin-pwa 的 registerType: 'prompt' 模式检测到新版本仅弹通知不自动刷新，必须实现 ReloadPrompt 组件提示用户刷新，或改用 registerType: 'autoUpdate' 自动激活新版本

自动化扫描从 74 项扩展到 75 项。详细编码规范整合到 xianyu-hunter-dev v4.20.0 的 step 107-111。后端对应规范为 xianyu-backend-code-review v4.22.0 的 B-REVIEW-STARTUP-HOOK-COMPLETENESS / B-REVIEW-TASK-HISTORY-THREE-LAYER-PROTECTION / B-REVIEW-COUNTER-DB-MAX-INIT / B-REVIEW-APSCHEDULER-INTERVAL-FIRST-RUN。

---

## v4.20.0 版本号源管理复盘（前端侧）

基于本轮解决的"版本管理菜单持续显示 V10"问题复盘（使用 Sequential Thinking 6 步复盘法），落地 v4.19.0 遗留待办，新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-VERSION-SOURCE-ALIGN**（维度 7）：前端显示元数据必须调用语义对齐的 API 端点，禁止将返回 `len(backups)` / `count` / `size` / `length` 的端点当作版本号使用；新增 aboutApi 调用必须通过 `Promise.all` 与既有 configApi 并行化避免瀑布请求；修复时同步清理只 set 不 read 的死代码 state

自动化扫描从 73 项扩展到 74 项。详细编码规范整合到 `xianyu-hunter-dev` v4.18.0 的 step 98。后端对应规范为 `xianyu-backend-code-review` v4.20.0 的 B-REVIEW-VERSION-SOURCE-SINGLE。

---

## v4.19.0 调度器状态展示复盘（前端侧）

基于本次对话解决的 3 个后端问题中"关键调度器启动状态可见性"对应的前端需求复盘（使用 Sequential Thinking 12 步复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-SCHEDULER-STATUS-DISPLAY**（维度 18）：前端"关于"页面必须展示关键调度器启动状态，调用 `/api/about` 端点获取 `schedulers` 数组并渲染为状态卡片，未启动的调度器必须显示红色"未启动"标签 + 启动命令提示

自动化扫描从 72 项扩展到 73 项。详细编码规范整合到 `xianyu-hunter-dev` v4.19.0 的 step 101。后端对应规范为 `xianyu-backend-code-review` v4.19.0 的 B-REVIEW-SCHEDULER-STARTUP-VISIBILITY。遗留待办：v4.17.0/v4.18.0 的 VERSION-SOURCE 规范尚未在本 skill 落地，需后续补充。

---

## v4.16.0 Cookie 层状态管理复盘（前端侧）

基于本轮解决的"功能正常但状态显示失效"问题（用户反馈：实时查询、官方采集等功能均能正常运行，但 identity、session、tracking 状态持续显示失效）复盘（使用 Sequential Thinking 4 维度复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-STATE-FUNCTIONAL-ALIGN**（维度 3）：前端 UI 显示的"功能/会话/服务状态"必须与"功能实际可用性"保持一致；禁止仅依据后端返回的"初始值"或"短期缓存"判定 UI 状态显示为"失效/异常"，必须配合"已发生过真实调用"标记（首次成功时间戳、计数器、最近一次成功时间）才更新 UI 状态为"有效/正常"

自动化扫描从 68 项扩展到 69 项。详细编码规范整合到 `xianyu-hunter-dev` v4.16.0 的 step 91-93。后端对应规范为 `xianyu-backend-code-review` v4.15.0 的 B-REVIEW-CACHE-INVALIDATION / B-REVIEW-STATE-DETECTION-BOOTSTRAP / B-REVIEW-MIGRATION-TRANSACTION。

### v4.16.0 同时补充 3 项 F-REVIEW 检查点

基于「前端接入 api_ai_deep 端点」代码审查复盘（使用 Sequential Thinking 4 维度复盘法）：

- **F-REVIEW-FIELD-CONTRACT-ALIGN**（维度 11）：后端归一化字段时前端 types.ts 必须注释「后端已归一化，前端消费 X 字段」，禁止通过动态 key 取归一化字段
- **F-REVIEW-ASYNC-RACE-CONDITION**（维度 10）：timeout >= 3s 的异步请求必须用 useRef 跟踪最新请求 ID，旧请求的 result/error/loading 三态在 setState 前校验 `ref.current === itemId` 不匹配则丢弃
- **F-REVIEW-ERROR-HANDLER-EXTRACT**（维度 11）：两处以上相同 if-else 状态码分支必须抽取工具函数 `handleXxxError(err, fallbackMsg, closeModal)`

自动化扫描从 69 项扩展到 72 项。后端对应规范为 `xianyu-backend-code-review` v4.16.0 的 B-REVIEW-FIELD-NORMALIZE-DOC / B-REVIEW-DIVZERO-FALLBACK，详细编码规范整合到 `xianyu-hunter-dev` v4.17.0 的 step 94-97。

---

## v4.15.0 登录流程性能优化/Cookie层同步测试修复/代码变更逻辑审查复盘（前端侧）

基于本次会话解决的 4 个问题复盘（使用 Sequential Thinking 4 维度复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-DEBUG-CODE-CLEANUP**（维度 11）：临时 DEBUG 代码在问题修复后必须移除，禁止留在生产代码中，包括临时 import/临时环境变量检查/临时日志文件写入/临时打印语句

自动化扫描从 67 项扩展到 68 项。详细编码规范整合到 `xianyu-hunter-dev` v4.15.0 的 step 88。后端对应规范为 `xianyu-backend-code-review` v4.14.0 的 B-REVIEW-DEBUG-CODE-CLEANUP。

---

## v4.14.0 评估明细过滤/分页/空状态复盘（前端侧）

基于本轮对话解决的「评估明细页面优化」工作复盘（使用 Sequential Thinking 5 步系统分析），新增 3 项 F-REVIEW 检查点：

- **F-REVIEW-FILTER-BACKEND-ALIGN**（维度 7）：实现前端过滤功能前必须先 grep 后端 insufficient_count/marginals/result 确认分类互斥性，前端过滤条件必须与后端分类逻辑对齐
- **F-REVIEW-FILTER-PAGINATION-ADAPT**（维度 10）：添加 filterStatus 状态后必须同步调整 pagination 三参数：total=filteredItems.length、current=1、pageSize=filteredItems.length||1
- **F-REVIEW-FILTER-EMPTY-STATE**（维度 3）：空状态判断必须用 filteredItems.length 而非原始 items.length，区分两种文案

自动化扫描从 64 项扩展到 67 项。后端对应规范为 xianyu-backend-code-review v4.13.0 的 B-REVIEW-STATS-EXCLUSIVE，详细编码规范整合到 xianyu-hunter-dev v4.14.0 的 step 82-85。

---

## v4.13.0 官方采集失败复盘（前端侧）

基于本轮对话解决的「官方采集失败」P0-P3 优化工作复盘（使用 Sequential Thinking 4 维度复盘法），新增 2 项 F-REVIEW 检查点：

- **F-REVIEW-ERROR-CONTRACT-TIMEOUT**（维度 7）：前端 API 模块必须声明模块级 `statusMessages: Record<number, string>` 映射表，axios 错误处理必须提供独立 `isAxiosTimeout(error)` 工具函数双路识别 `error.code === 'ECONNABORTED'` 或 `/timeout/i.test(error.message)`
- **F-REVIEW-RETRY-BACKOFF**（维度 7）：前端 API 重试逻辑必须区分可重试错误集（410/441/502/超时）与需用户介入错误集（401/403/440/503），可重试错误按 `retry_delays_ms` 退避序列重试默认 [500,1500,3000]ms，重试过程 `silent_on_retry=true` 不弹 message

自动化扫描从 62 项扩展到 64 项。后端对应规范为 `xianyu-backend-code-review` v4.12.0 的 B-REVIEW-DOM-FALLBACK-CHAIN / B-REVIEW-FAILURE-DUMP / B-REVIEW-TIMING-INSTRUMENTATION / B-REVIEW-PRECHECK-AND-PARALLEL，详细编码规范整合到 `xianyu-hunter-dev` v4.13.0 的 step 76-81。

---

## v4.12.0 配置加载/输入边界/null 语义/XSS 转义/批量操作复盘（前端侧）

基于本轮对话解决的 5 类前端问题复盘（使用 Sequential Thinking 4 维度复盘法），新增 5 项 F-REVIEW 检查点：

- **F-REVIEW-ASYNC-CONFIG-LOAD**（维度 10）：异步加载配置后设置 usePersistentState 必须双重检查 localStorage 防止竞态，cancelled 标志防止组件卸载后 setState
- **F-REVIEW-INPUT-NUMBER-BOUNDS**（维度 4）：InputNumber 必须设置 min/max 边界，禁止无边界输入导致 0/负数触发后端 ZeroDivisionError
- **F-REVIEW-NULL-SEMANTICS**（维度 4）：类型必须明确区分 null/undefined/空字符串三种语义
- **F-REVIEW-XSS-ESCAPE**（维度 11）：用户输入字段必须 HTML 转义+JSX 双重保护
- **F-REVIEW-BATCH-OPERATION**（维度 7）：批量操作必须实现 Modal.confirm + loading + success/error message + 异常处理 + 状态刷新完整流程

自动化扫描从 57 项扩展到 62 项。后端对应规范为 `xianyu-backend-code-review` v4.11.0 的 B-REVIEW-CONFIG-VALIDATION / B-REVIEW-STATUS-CODE-SEMANTICS，详细编码规范整合到 `xianyu-hunter-dev` v4.12.0 的 step 69-75。

---

## v4.11.0 状态机/双链路/缓存一致性复盘（前端侧）

基于后端 v4.9.0 的 5 类问题复盘（使用 Sequential Thinking 4 维度复盘法），新增 3 项 F-REVIEW 检查点：

- **F-REVIEW-STATE-ENUM-ALIGN**（维度 4）：前后端状态枚举值必须严格对齐，禁止前端硬编码状态字符串而应从 `types.ts` 导出常量联合类型
- **F-REVIEW-STATE-MACHINE-UI**（维度 3）：状态机每个状态值必须有对应的 UI 视觉标识，终态禁止显示"进行中"类动画，中间态必须有 loading 反馈
- **F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY**（维度 6）：多链路触发同一状态变更时必须通过统一 refetch 入口刷新缓存，禁止各链路独立 setState

自动化扫描从 54 项扩展到 57 项。后端对应规范为 `xianyu-backend-code-review` v4.9.0 的 B-REVIEW-STATE-MACHINE-WHITELIST / B-REVIEW-DUAL-LINK-CONSISTENCY，详细编码规范整合到 `xianyu-hunter-dev` v4.10.0 的 step 60-64。

---

## v4.10.0 过滤结果可见性复盘（前端侧）

基于"实时搜索过滤结果全部被筛掉但前端只显示'查询完成'导致用户不知原因"问题复盘（使用 Sequential Thinking 8 步系统分析），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-FILTER-VISIBILITY**（维度 7）：后端返回 `filter_summary` 时前端必须实现三态提示策略 success/warning/info；`filtered_out` 非空时必须提供"查看被过滤结果"按钮+Modal；API 返回类型必须显式声明 `filter_summary?` 字段，禁止 `as` 强制类型转换绕过 TS 检查

自动化扫描从 53 项扩展到 54 项。后端对应规范为 `xianyu-backend-code-review` v4.10.0 的 B-REVIEW-FILTER-VISIBILITY，详细编码规范整合到 `xianyu-hunter-dev` v4.11.0 的 step 65。

---

## v4.9.0 频率伪装统计孤岛复盘（前端定时刷新）

基于"反爬登录管理菜单的频率伪装统计持续为 0 且无变化"问题复盘（与后端 v4.8.0 配合，使用 Sequential Thinking 4 维度复盘法），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-FREQ-STATS-POLLING**（维度 10）：累计统计类 API（频率伪装统计 / 采样器 / 计数器 / 令牌桶 / 健康评分）必须在前端通过 `setInterval` 定时刷新，不能只依赖"页面加载时拉一次"

自动化扫描从 52 项扩展到 53 项。核心机制：业务模块持续调用后端核心模块累加统计，前端若不轮询，UI 会永远停留在某个时刻的快照。后端对应规范为 `xianyu-backend-code-review` v4.8.0 的 B-REVIEW-ISLAND-MODULE，详细编码规范整合到 `xianyu-hunter-dev` v4.9.0 的 step 56-59。

---

## v4.8.0 AntD 主题 token 动态覆盖复盘

基于"暗色主题下 Table hover 高亮色与文字色一致导致不可见"问题复盘（使用 Sequential Thinking 5 步系统分析），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE**（维度 5）：项目支持暗色主题时，`baseTheme.components.<Component>.<token>` 中显式指定的主题相关 token（含 `Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus` 后缀）必须根据 `isDark` 状态在 `ThemedRoot` 内动态覆盖，禁止依赖 `darkAlgorithm` 自动重算或 `index.css` 的 `--ant-*` CSS 变量

自动化扫描从 51 项扩展到 52 项。核心机制：antd v5 `darkAlgorithm` 仅重算未指定 token + `cssVar` 模式默认未启用。

---

## v4.7.0 异步反馈 + 数据流转 + 过滤场景 + 复用模式复盘

基于"评估明细标题采集超时 + 订单字段为空根因定位 + 一刀切过滤导致展示缺失"三个问题复盘（使用 Sequential Thinking 5 步系统分析），新增 4 项 F-REVIEW 检查点：

- **F-REVIEW-ASYNC-FEEDBACK**（维度 10）：前端异步操作必须实现 loading → success → error 三态反馈，禁止 `.catch(() => {})` 静默吞错误
- **F-REVIEW-DATA-FLOW-TRACE-FRONTEND**（维度 11）：前端"字段为空"类问题必须配合后端按 5 点逐层追踪，前端侧验证 types 声明 + render 取值
- **F-REVIEW-FILTER-SCENARIO-FRONTEND**（维度 7）：前端调用后端查询接口时必须按场景传 `include_failed` 等场景标志，展示历史场景传 True
- **F-REVIEW-REUSE-PATTERN-FRONTEND**（维度 18）：新增前端功能前必须 grep 项目内相似实现，复用既有 Hook/工具函数/模式

自动化扫描从 47 项扩展到 51 项。

---

## v4.6.0 Cookie 分层管理架构前端同步复盘

基于后端 5 个登录路径不更新 CookieRotator 层状态 + cookie_checker 覆盖手动失效问题复盘，新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND**（维度 6）：前端调用同一后端写入接口的不同代码路径时，状态更新必须统一通过单一 `updateState` 函数而非各路径独立更新

自动化扫描从 46 项扩展到 47 项。

---

## v4.5.0 搜索参数链路 + 错误语义复盘

基于"实时搜索错误提示语义偏差 + 搜索参数配置不生效"两个问题复盘（使用 Sequential Thinking 4 维度分析），新增 2 项 F-REVIEW 检查点：

- **F-REVIEW-ERROR-SEMANTICS**（维度 11）：前端错误提示文案必须与后端错误根因语义匹配（如 RGV587=token 过期不应显示"登录已过期"）
- **F-REVIEW-CONFIG-LINKAGE**（维度 7）：前端配置项从定义到消费必须全链路追踪，配置注入≠配置生效

自动化扫描从 44 项扩展到 46 项。

---

## v4.4.0 浏览器 Cookie 导入增强复盘

基于"浏览器 Cookie 导入增强（v20 加密 + 多 Profile + 自动同步）"复盘（使用 Sequential Thinking 4 维度分析），新增 1 项 F-REVIEW 检查点：

- **F-REVIEW-CONFIG-DRIVEN-TOGGLE**（维度 11）：前端高风险功能（如自动同步开关、CDP 调试触发按钮）必须配置驱动，参数集中在 `constants.ts` 或 config 文件管理（不硬编码），默认关闭需用户显式启用

自动化扫描从 43 项扩展到 44 项。

---

## v4.3.0 反爬模块代码审查复盘

基于反爬模块全面评估复盘，新增维度 19（跨组件状态同步与死代码检测），补充检查项：Proxy/Observer 赋值给局部变量（死代码）、try/finally 变量未初始化为 None、跨组件对同一概念判断维度差异、错误提示引用不存在的端点/路由，自动化扫描从 39 项扩展到 43 项。

---

## v4.2.0 UI 状态独立性复盘

基于"菜单树动画遮挡"问题复盘，新增 F-REVIEW-UI-STATE-INDEPENDENCE 检查项到维度 3（React 组件规范），要求受控 UI 状态（`openKeys`/`expandedKeys`/`activeKey`）不应通过 `useEffect` 联动路由变化，仅在用户主动操作时变化；路由变化只应更新派生状态（`selectedKeys`/breadcrumb）。自动化扫描从 38 项扩展到 39 项。

---

## v4.1.0 SSE 错误处理复盘

基于"实时搜索会话失效未推送明确错误提示"问题复盘，新增维度 15（F-REVIEW-SSE-ERROR-HANDLING：SSE 错误事件状态码分类处理 + "前往登录"跳转引导）补充检查项，对应后端 v4.1.0 的错误粒度三类区分（503/504 稍后重试、401/403 需用户介入、502 需重启服务），自动化扫描从 36 项扩展到 38 项。

---

## v4.0.0 布局重构/搜索标准化/代码质量复盘

基于 AI 服务页面 Tab 布局重构 + 实时搜索标准化 + 代码评审通用规范复盘，新增维度 3（多视图 state 提升）、维度 10（requestId 竞态保护 + 统一防抖）、维度 11（IIFE 反模式禁止 + 动态资源映射分离）、维度 17（外部链接 rel 安全）、维度 18（显式样式 + 注释一致性）补充检查项，自动化扫描从 26 项扩展到 36 项。

---

## v3.0.0 SonarQube 规则增强

基于 SonarQube 修复实战复盘，扩展维度 12（SonarQube 合规）从 8 条规则到 16 条，新增 S7503（不必要 async）、S6767（未使用 Props/State）、S6819/S6844（div/anchor 替代 button）、S7744（不必要类型转换）、S6582（冗余可选链）、S7735（useEffect 依赖缺失）、S6551（for...in）、S1874（@deprecated 缺失），自动化扫描从 14 项扩展到 26 项；抽象建议新增"纯函数+组件+常量分层"模式（如 `resolveActionDisplay` + `ActionPlaceholder` + `ACTION_PLACEHOLDER_TEXT`）。

---

## v2.0.0 知识点整合

整合 `xianyu-hunter-dev` 技能的 `frontend-guide.md` 与 `project-rules.md` 硬约束，新增维度 1（目录结构）、3（React 组件规范）、4（TypeScript 严格规范）、5（AntD 5 主题）、6（Zustand 状态管理）、7（API 调用规范）、8（路由与懒加载）、9（SheetWorkspace 多页签）、10（Hooks 设计模式）、12（SonarQube 合规）、13（PWA 配置）、14（三处映射同步）、15（SSE 重连）、17（移动端适配）、18（闲鱼项目规范），扩展抽象建议与硬约束规则，自动化扫描 12 项。
