# 闲鱼猎人前端代码审查报告

## 基本信息

- **审查版本**：v2.0.0
- **审查模式**：[全量审查 / 增量审查 / 指定文件审查 / 片段评审]
- **审查范围**：`frontend/src/**/*.{tsx,ts,js}`
- **审查文件数**：X 个
- **审查时间**：YYYY-MM-DD HH:MM:SS
- **审查人**：xianyu-frontend-code-review Skill
- **上次审查**：[有/无]

## 相对于上次审查的变化

| 状态 | 数量 | 说明 |
|------|------|------|
| 🆕 新增 | X | 本次新发现的问题 |
| ✅ 已修复 | X | 上次存在的问题已修复 |
| ⚠️ 仍存在 | X | 上次存在的问题仍未修复 |

## 审查结果摘要

- 🔴 阻塞问题：X 个（必须修复）
- 🟠 严重问题：X 个（强烈建议修复）
- 🟡 警告问题：X 个（建议修复）
- 🟢 优化建议：X 个（可选）

### 按 severity 分布

| Severity | 数量 |
|----------|------|
| CRITICAL | X |
| HIGH | X |
| MEDIUM | X |
| LOW | X |
| INFO | X |

### 按 category 分布（18 维度）

| Category | 数量 |
|----------|------|
| directory_structure | X |
| naming | X |
| react_component | X |
| typescript_strict | X |
| antd_theme | X |
| zustand | X |
| api_call | X |
| routing_lazy | X |
| sheet_workspace | X |
| hooks_design | X |
| type_safety | X |
| sonarqube | X |
| pwa | X |
| three_mappings | X |
| sse_reconnect | X |
| performance | X |
| accessibility | X |
| project_specific | X |

## 硬约束合规性检查结果

| 硬约束规则 | 状态 | 违规位置 |
|------------|------|----------|
| `fetch_credentials_include` | ✅ 通过 / ❌ 违规 | - |
| `axios_with_credentials` | ✅ 通过 / ❌ 违规 | - |
| `no_token_in_localstorage` | ✅ 通过 / ❌ 违规 | - |
| `no_dangerously_set_inner_html` | ✅ 通过 / ❌ 违规 | - |
| `no_any_type` | ✅ 通过 / ❌ 违规 | - |
| `no_bare_async_catch` | ✅ 通过 / ❌ 违规 | - |
| `icon_button_needs_aria_label` | ✅ 通过 / ❌ 违规 | - |
| `no_enum_use_union` | ✅ 通过 / ❌ 违规 | - |
| `no_index_as_key` | ✅ 通过 / ❌ 违规 | - |
| `no_json_parse_stringify_deep_copy` | ✅ 通过 / ❌ 违规 | - |
| `no_arrow_function_component` | ✅ 通过 / ❌ 违规 | - |
| `zustand_persist_partialize` | ✅ 通过 / ❌ 违规 | - |

**合并结论**：[允许合并 / 阻止合并（存在 CRITICAL 违规）]

## 抽象建议触发情况

基于 `abstraction_thresholds` 阈值检查：

| 抽象维度 | 阈值 | 触发位置 | 建议方案 |
|----------|------|----------|----------|
| 内联样式重复 | ≥3 处 | - | 抽取样式常量或共享组件 |
| 文案字面量重复 | ≥2 处 | - | 抽取共享文案常量 |
| 函数行数 | >50 行 | - | 拆分为子函数 |
| 组件行数 | >300 行 | - | 拆分子组件 |
| 嵌套深度 | >4 层 | - | 提取模块级函数（S2004） |
| 认知复杂度 | >15 | - | 拆分函数（S3776） |

## 详细问题列表

### 🔴 阻塞问题（必须修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```tsx
     // 问题代码示例
     ```
   - **修复建议**：
     ```tsx
     // 修复后的代码示例
     ```
   - **参考规范**：[对应 SKILL.md 维度章节]

### 🟠 严重问题（强烈建议修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **修复建议**：[具体建议]

### 🟡 警告问题（建议修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **修复建议**：[具体建议]

### 🟢 优化建议（可选）

1. **建议描述**：[具体建议]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **优化方案**：[具体方案]

## ✅ 好的实践

- [正面反馈：列出本次审查中发现的好实践]
  - 例如：axios.create 正确配置 `withCredentials: true`
  - 例如：ConfigProvider 正确放置在 BrowserRouter 外层
  - 例如：使用字符串字面量联合替代 enum
  - 例如：useRef 持有最新闭包避免 setInterval 陷阱
  - 例如：抽取纯函数便于单元测试（如 resolveActionDisplay）

## 测试运行结果

- **测试命令**：`npm --prefix frontend test ; npm --prefix frontend run typecheck`
- **测试结果**：[通过 / 失败]
- **类型检查**：[通过 / 失败]

## 审查结论

- [ ] 通过（无阻塞问题）
- [ ] 有条件通过（仅警告和提示级别问题）
- [ ] 不通过（存在阻塞或严重问题）

## 修复验证

修复完成后，请重新运行审查确认问题已解决：

```powershell
# 1. 重新运行快速自检
pwsh .trae/skills/xianyu-frontend-code-review/scripts/auto-scan.ps1

# 2. 重新运行人工评审
# 调用 xianyu-frontend-code-review 技能
```

## 报告归档

报告保存路径：`.trae/skills/xianyu-frontend-code-review/reports/YYYY-MM-DD_HHmmss_[full|incremental]_report.md`

---

## 🆕 v4.28.0 四维度复盘

> 基于 [`docs/standards/四维度复盘方法论与历史教训集成.md`](../../../../docs/standards/四维度复盘方法论与历史教训集成.md) 的四维度框架，对本次审查的发现进行结构化复盘，沉淀可复用的工作流模板。

### 维度 1：成功执行任务的完整步骤

- 本次审查在 `XXX` 类目下识别出 `N` 个问题，其中 `M` 个被成功闭环
- 关键成功路径（按时间顺序）：
  1. `step 1`: ...
  2. `step 2`: ...
- 复用已有方法/工具：xxx

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 关键路径异常被吞 | 外层 except 用 `logger.warning(f"...{e}")` | 启动失败无法定位 | 异常堆栈丢失 | 改用 `logger.exception()` |
| 批处理熔断后无 `save_progress()` | `consecutive failure >= 3` 后 `break` | 剩余商品永久 skipped | 熔断分支未持久化 cursor | 熔断时调用 `_save_progress()` |
| Proxy/Observer 被 GC 回收 | `const x = new Proxy()` 局部变量 | DOM 变化不再触发回调 | 局部变量无生命周期 | 赋值给实例属性 `this._proxy` |
| 前端 TTL 缓存兜底跨进程状态 | `setTimeout(refresh, 30000)` | 状态刷新延迟 30s | 跨进程状态未 SSE 推送 | `single_source_of_truth` + `refetch()` |

### 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 对应工作流元规范 | 核心判断信号 | 落地配置节点 |
|------|------------------|--------------|--------------|
| 错误处理决策树 | meta-rule #21 | `grep "except" <file>` 关键路径缺 `logger.exception()` | `workflow_meta_rules_frontend.error_handling_decision_tree` |
| 批处理熔断模板 | meta-rule #22 | `grep "consecutive failure" <file>` 无 `save_progress()` | `workflow_meta_rules_frontend.batch_circuit_breaker_frontend.failure_threshold` |
| 资源生命周期 | meta-rule #23 | `grep "new (Proxy\|MutationObserver\|IntersectionObserver\|ResizeObserver)"` 局部变量 | `workflow_meta_rules_frontend.resource_lifecycle_frontend.required_holder_patterns` |
| 跨组件状态同步 | meta-rule #24 | `grep "usePersistentState" <file>` 但后端有 `GET /api/xxx` | `workflow_meta_rules_frontend.state_sync_workflow_frontend.single_source_of_truth` |

### 维度 4：适用场景与不适用场景

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 错误处理决策树 | 启动钩子 / 迁移 / 初始化 / API 路由 try-catch / 前端 `.catch` | 性能 hot path（结构化异常）/ 测试代码（`pytest.raises`） |
| 批处理熔断模板 | 批量采集 / 批量导入 / 长任务 / 断点续传 / 用户主动取消 | 实时单次请求 / 幂等小批量（≤3 个）/ 性能 hot path |
| 资源生命周期 | Playwright/Selenium / SSE/EventSource / WebSocket / Proxy/Observer / 长生命周期 Timer | 短生命周期局部计算 / 一次性 useEffect / 测试 mock 资源 |
| 跨组件状态同步 | 复杂前端应用（多组件共享同一份数据）/ 多 Tab / 多路由 / 配置变更实时生效 | 简单组件树（1-2 层 props drilling）/ SSR / 纯 UI 偏好（主题色/视图模式） |

## 🆕 v4.28.0 工作流元规范触发

> 本次审查触发的元规范编号（与 xianyu-hunter-dev/references/meta-rules.md #21-24 对应）。每条触发需指明：触发规则名、对应 config.yaml 配置节点、违规位置、修复方式。

| 触发编号 | 元规范名称 | 触发规则 | 配置节点 | 违规位置 | 修复方式 |
|----------|------------|----------|----------|----------|----------|
| #21 | 错误处理决策树 | F-REVIEW-WF-ERROR-HANDLING | `workflow_meta_rules_frontend.error_handling_decision_tree.forbidden_catch_patterns` | `frontend/src/xxx/yyy.tsx:L123` | 改用 switch on `err.error_code` |
| #22 | 批处理熔断模板 | F-REVIEW-WF-BATCH-CIRCUIT-BREAKER | `workflow_meta_rules_frontend.batch_circuit_breaker_frontend.failure_threshold` | `frontend/src/xxx/zzz.ts:L456` | 熔断时调用 `saveProgress()` |
| #23 | 资源生命周期 | F-REVIEW-WF-RESOURCE-LIFECYCLE | `workflow_meta_rules_frontend.resource_lifecycle_frontend.forbid_local_var_creation` | `frontend/src/aaa.tsx:L78` | 改为 `this._observer = new ...` |
| #24 | 跨组件状态同步 | F-REVIEW-WF-STATE-SYNC | `workflow_meta_rules_frontend.state_sync_workflow_frontend.forbid_persistent_state_for` | `frontend/src/bbb.tsx:L234` | 改为 `useXxxStore().setXxx()` + `refetch()` |

## 🆕 v4.28.0 配置变更点

> 本次审查触发的 `config.yaml` 节点变更建议。所有变更遵循"无硬编码"原则，仅调整阈值/白名单/关键字等参数化配置，不引入新的硬编码业务值。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 阈值调整 | `error_handling_decision_tree.max_retry_count` | `3` | `5` | 现有 3 次重试不足以应对网络抖动 | 错误处理决策树（meta-rule #21） |
| 白名单新增 | `batch_circuit_breaker_frontend.required_state_display` | `[running, paused]` | `[running, paused, failed, stopped, completed]` | 状态机需覆盖全部 5 个状态 | 批处理熔断（meta-rule #22） |
| 模式新增 | `resource_lifecycle_frontend.forbid_local_var_creation` | `[Proxy, MutationObserver]` | `[Proxy, MutationObserver, IntersectionObserver, ResizeObserver, EventSource, WebSocket]` | 补齐其他可注册资源 | 资源生命周期（meta-rule #23） |
| 黑名单新增 | `state_sync_workflow_frontend.forbid_persistent_state_for` | `[task_status, cookie_status]` | `[task_status, cookie_status, scheduler_status, model_config]` | 补齐其他跨进程字段 | 跨组件状态同步（meta-rule #24） |

**变更后自检清单**：
- [ ] 无硬编码新增（所有数值/列表/关键字均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] SKILL.md 附录 C 的 26 维度与本变更一致
- [ ] references/version-changelog.md 已追加 v4.28.0 变更说明

## 🆕 v4.30 跨边界访问契约

> 跨边界访问必须明确契约，不能依赖隐式约定。与 xianyu-hunter-dev/references/coding-standards.md §2.11-2.14 配套。

### 跨边界契约检查（前端侧）

| 边界类型 | 契约内容 | 配置节点 | 检查工具 |
|----------|----------|----------|----------|
| DB → 前端 | 后端 ISO datetime 字符串渲染必须 `new Date(isoStr).toLocaleString()` | `cross_boundary_contract_frontend.datetime_render_contract.backend_datetime_field_suffixes` | F-REVIEW-DATETIME-RENDER-CONTRACT |
| 前端 → 后端 | 传递时间用 `Date.toISOString()` 保留时区 | `cross_boundary_contract_frontend.datetime_render_contract.required_isoformat_patterns` | F-REVIEW-DATETIME-RENDER-CONTRACT |
| 跨组件 store | 禁止直接访问 `useXxxStore(s => s._private)` | `cross_boundary_contract_frontend.private_hook_encapsulation.forbid_private_prefix_access` | F-REVIEW-PRIVATE-HOOK-ENCAPSULATION |
| 父 → 子 ref | 父组件通过 ref 访问子组件 `_` 内部 state 禁止 | `cross_boundary_contract_frontend.private_hook_encapsulation.require_imperative_handle` | F-REVIEW-PRIVATE-HOOK-ENCAPSULATION |
| 命名一致性 | Zustand store 字段 camelCase（与前端规范） | `cross_boundary_contract_frontend.naming_consistency.store_field_case` | F-REVIEW-NAMING-CONSISTENCY-FRONTEND |

## 🆕 v4.41.0 编码规范防御性复盘

> 基于 `xianyu-hunter-dev` v4.38.0 meta-rules #57-63 前端落地，新增 4 项 F-REVIEW 检查点（F-REVIEW-148~151），自动化扫描从 121 项扩展到 125 项。与 `xianyu-hunter-dev` step 189-195 对应。

### F-REVIEW-148~151 检查结果汇总

| 检查点 | 名称 | 维度 | severity | 配置节点 | 违规数 | 状态 |
|--------|------|------|----------|----------|--------|------|
| F-REVIEW-148 | ASYNC-AWAIT-SYNC-CHECK-FRONTEND | 10 Hooks 设计模式 | CRITICAL | `meta_rules_57_63_frontend.frontend_async_await_check` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-149 | HTTP-ERROR-LOCALIZATION | 7 API 契约 | WARNING | `meta_rules_57_63_frontend.frontend_http_error_localization` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-150 | ERROR-CHAIN-TRANSPARENT | 7 API 契约 / 4 业务逻辑 | WARNING | `meta_rules_57_63_frontend.frontend_error_chain_transparent` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-151 | EXTERNAL-RESOURCE-CLEANUP-FRONTEND | 10 Hooks 设计模式 / 6 Zustand 状态管理 | CRITICAL | `meta_rules_57_63_frontend.frontend_external_resource_cleanup` | X | ✅ 通过 / ❌ 违规 |

### F-REVIEW-148 ASYNC-AWAIT-SYNC-CHECK-FRONTEND 违规详情

> React `useEffect` 内 async 函数必须用 IIFE 包裹 + cancelled 标志，禁止 `useEffect(async () => {})` 直接传入。

1. **问题描述**：[useEffect 直接接收 async 函数 / cleanup 返回 Promise 而非函数 / 缺少 cancelled 标志]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 问题代码示例
     useEffect(async () => {
       const data = await fetchData();
       setData(data);
     }, []);
     ```
   - **修复建议**：
     ```typescript
     // ✅ 用 IIFE 包裹，cleanup 返回函数
     useEffect(() => {
       let cancelled = false;
       (async () => {
         const data = await fetchData();
         if (!cancelled) setData(data);
       })();
       return () => { cancelled = true; };
     }, []);
     ```
   - **配置节点**：`meta_rules_57_63_frontend.frontend_async_await_check`（severity: CRITICAL, forbidden_patterns: ["useEffect(async", "useEffect.*async.*=>"]）
   - **对应规范**：`xianyu-hunter-dev` v4.38.0 meta-rule #57 + step 189

### F-REVIEW-149 HTTP-ERROR-LOCALIZATION 违规详情

> 已知状态码优先用前端中文 `statusMessages[status]`，后端 `detail` 仅作 fallback。

1. **问题描述**：[优先用后端英文 detail / 已知状态码无前端中文消息映射 / 状态码映射表散落在组件内]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 优先用后端英文 detail，对中文用户不友好
     catch (err) {
       const status = err?.response?.status;
       const detail = err?.response?.data?.detail;
       message.error(detail || statusMessages[status]);
     }
     ```
   - **修复建议**：
     ```typescript
     // ✅ 已知状态码优先用前端中文消息，后端 detail 仅作 fallback
     const COLLECT_OFFICIAL_ERROR_MESSAGES: Record<number, string> = {
       503: '官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动',
       403: '闲鱼登录已过期，请重新登录闲鱼',
       440: '闲鱼登录已过期，请重新登录闲鱼',
       441: '触发闲鱼反爬限制，请稍后重试或手动完成验证',
       410: '商品详情页加载失败或已下架，请稍后重试',
       502: '浏览器连接异常，请重启服务后重试',
     };
     catch (err) {
       const status = err?.response?.status;
       if (status != null && statusMessages[status]) {
         message.error(statusMessages[status]);
       } else {
         message.error(detail || fallbackMessage);
       }
     }
     ```
   - **配置节点**：`meta_rules_57_63_frontend.frontend_http_error_localization`（severity: WARNING, prefer_frontend_message: true, fallback_to_detail: true）
   - **对应规范**：`xianyu-hunter-dev` v4.38.0 meta-rule #59 + step 191

### F-REVIEW-150 ERROR-CHAIN-TRANSPARENT 违规详情

> 错误链路需透明展示 reason/failure_reason；用户可见错误必须含可操作建议。

1. **问题描述**：[仅展示模糊错误无 reason / 错误消息无可操作建议 / 多阶段降级链未合并展示 / 缺少 retryable 标志]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 仅展示模糊错误，无 reason 无建议
     message.error('采集失败');
     ```
   - **修复建议**：
     ```typescript
     // ✅ 含 reason 与可操作建议
     message.error({
       content: `采集失败：${reason}。建议：${actionHint}`,
       duration: 8,
     });
     // 或结构化展示
     const errorDisplay = {
       title: '官方采集失败',
       reason: failure_reason,
       suggestion: getSuggestionByReason(failure_reason),
       retryable: isRetryable(failure_reason),
     };
     ```
   - **配置节点**：`meta_rules_57_63_frontend.frontend_error_chain_transparent`（severity: WARNING, require_reason: true, require_suggestion: true, require_retryable_flag: true, multi_stage_merge: true）
   - **对应规范**：`xianyu-hunter-dev` v4.38.0 meta-rule #61 + step 193

### F-REVIEW-151 EXTERNAL-RESOURCE-CLEANUP-FRONTEND 违规详情

> `useEffect` 内创建的 WebSocket/EventSource/setInterval/setTimeout/addEventListener/AbortController 必须在 cleanup 中释放。

1. **问题描述**：[useEffect 创建资源但无 cleanup return / cleanup 未调用对应释放方法 / 事件监听器未 removeEventListener / WebSocket 未 close]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ useEffect 创建订阅但无 cleanup
     useEffect(() => {
       const ws = new WebSocket('ws://localhost:8080');
       ws.onmessage = (e) => setMessage(e.data);
       // 缺少 return () => ws.close();
     }, []);
     ```
   - **修复建议**：
     ```typescript
     // ✅ 创建与 cleanup 配对
     useEffect(() => {
       const controller = new AbortController();
       const ws = new WebSocket('ws://localhost:8080');
       ws.onmessage = (e) => setMessage(e.data);
       return () => {
         controller.abort();
         ws.close();
       };
     }, []);
     ```
   - **配置节点**：`meta_rules_57_63_frontend.frontend_external_resource_cleanup`（severity: CRITICAL, resource_types: ["WebSocket", "EventSource", "setInterval", "setTimeout", "addEventListener", "AbortController"], require_cleanup_return: true, pair_required: true）
   - **对应规范**：`xianyu-hunter-dev` v4.38.0 meta-rule #62 + step 194

### v4.43.0 配置变更点

> 本次审查触发的 `config.yaml` 节点变更建议。所有变更遵循"无硬编码"原则。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 状态码映射新增 | `meta_rules_57_63_frontend.frontend_http_error_localization.status_message_examples` | `[503, 403, 440, 441, 410, 502]` | `[503, 403, 440, 441, 410, 502, <新状态码>]` | 业务域扩展新增状态码 | F-REVIEW-149（meta-rule #59） |
| 资源类型新增 | `meta_rules_57_63_frontend.frontend_external_resource_cleanup.resource_types` | `[WebSocket, EventSource, setInterval, setTimeout, addEventListener, AbortController]` | `[...现有, <新资源类型>]` | 新增长生命周期资源 | F-REVIEW-151（meta-rule #62） |
| 检测模式新增 | `meta_rules_57_63_frontend.frontend_external_resource_cleanup.detection_patterns` | `[WebSocket, setInterval, addEventListener]` | `[...现有, <新资源 pattern]` | 补齐其他资源的 cleanup 检测 | F-REVIEW-151（meta-rule #62） |

**变更后自检清单**：
- [ ] 无硬编码新增（所有数值/列表/关键字均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] SKILL.md 维度 34 章节与本变更一致
- [ ] references/version-changelog.md 已追加 v4.41.0 变更说明

## 🆕 v4.45.0 全局拦截器状态码区分检查报告条目（F-REVIEW-154）

> 本节为 v4.45.0 新增 F-REVIEW-154 检查点（meta-rule #66 前端落地）的报告条目模板。每条违规按以下格式记录，参数在 `config.yaml#interceptor_audit` 节点管理。

### F-REVIEW-154 检查结果汇总

| 检查点 | 名称 | 维度 | severity | 配置节点 | 违规数 | 状态 |
|--------|------|------|----------|----------|--------|------|
| F-REVIEW-154 | INTERCEPTOR-STATUS-CODE-DISCRIMINATION | 7 API 契约 | CRITICAL | `interceptor_audit.auth_redirect` | X | ✅ 通过 / ❌ 违规 |

### F-REVIEW-154 INTERCEPTOR-STATUS-CODE-DISCRIMINATION 违规详情

> axios/fetch 全局响应拦截器跳转登录页必须基于 status + detail 双重校验，禁止仅凭 status 跳转，避免业务 401 被误判为认证失效。

1. **问题描述**：[拦截器仅凭 status === 401 即跳转 / 未检查 detail 字段 / 业务错误（440/422/429）被全局拦截器拦截跳转]
   - **位置**：`frontend/src/api/client.ts` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 仅凭 status === 401 即跳转，未检查 detail 字段
     client.interceptors.response.use(
       (response) => response,
       (error) => {
         if (error.response?.status === 401) {
           // 业务 401（闲鱼 cookie 过期，detail 为业务消息）也会被误判为认证失效
           localStorage.removeItem('xh_token')
           window.location.href = '/app/login'
         }
         return Promise.reject(error)
       },
     )
     ```
   - **修复建议**：
     ```typescript
     // ✅ 同时校验 status + detail，业务 401 由调用方 catch 处理
     client.interceptors.response.use(
       (response) => response,
       (error) => {
         const isAuthUnauthorized =
           error.response?.status === 401 &&
           error.response?.data?.detail === 'Unauthorized'
         if (isAuthUnauthorized) {
           localStorage.removeItem('xh_token')
           const currentPath = globalThis.location.pathname + globalThis.location.search
           const isLoginPage = currentPath.startsWith('/app/login')
           if (!isLoginPage && !isRedirecting) {
             isRedirecting = true
             const redirect = encodeURIComponent(currentPath)
             globalThis.location.replace(`/app/login?redirect=${redirect}`)
           }
         }
         return Promise.reject(error)
       },
     )
     ```
   - **配置节点**：`interceptor_audit.auth_redirect.conditions[0]`（status: 401, detail_equals: 'Unauthorized'）
   - **规范引用**：meta-rule #66 / xianyu-hunter-dev v4.40.0
   - **适用**：axios/fetch 全局响应拦截器；带 Bearer/JWT 认证的前端应用；SPA 应用
   - **不适用**：无认证应用；纯 SSR 应用；测试 mock
   - **与已有规则的关系**：
     - 与 `auth_token_cookie_handling.forbidden_error_handling_patterns` 互补（前者关注拦截器层面，后者关注业务代码 catch 块）
     - 与 `frontend_error_contract.status_message_map` 配合（业务错误用前端中文消息）
     - 与 v4.27 F-REVIEW-ERROR-CODE-BRANCH 配合（按 error_code 分支处理）

### F-REVIEW-154 业务错误被全局拦截器拦截

### 🟠 [HIGH] F-REVIEW-154：业务错误（440/422/429）被全局拦截器拦截跳转

- **位置**：`frontend/src/api/client.ts` 第 X 行
- **当前代码**：
  ```typescript
  // ❌ 拦截器拦截所有 4xx 错误跳转，业务错误无法被调用方 catch
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status >= 400 && error.response?.status < 500) {
        window.location.href = '/app/login'
      }
      return Promise.reject(error)
    },
  )
  ```
- **问题**：拦截器拦截所有 4xx 错误跳转登录页，业务错误（440/422/429/410）无法被调用方 catch 处理。业务错误应由调用方 catch 后展示 detail 或对应中文消息，不应被全局拦截器统一处理
- **修复建议**：
  ```typescript
  // ✅ 拦截器只处理认证 401（detail='Unauthorized'），其他错误 reject 给调用方
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      const isAuthUnauthorized =
        error.response?.status === 401 &&
        error.response?.data?.detail === 'Unauthorized'
      if (isAuthUnauthorized) {
        // 跳转登录页
      }
      // 业务错误（440/422/429/410）由调用方 catch 处理
      return Promise.reject(error)
    },
  )
  ```
- **配置节点**：`interceptor_audit.business_error_handling`
- **规范引用**：meta-rule #66 / xianyu-hunter-dev v4.40.0
- **适用**：所有带全局响应拦截器的前端应用
- **不适用**：无拦截器的应用；纯 SSR 应用

### F-REVIEW-154 拦截器未 reject 错误

### 🟡 [WARNING] F-REVIEW-154：拦截器处理后未 return Promise.reject(error)，调用方无法 catch

- **位置**：`frontend/src/api/client.ts` 第 X 行
- **当前代码**：
  ```typescript
  // ❌ 拦截器处理后未 reject，调用方 catch 拿不到错误
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        // 跳转登录页
      }
      // 缺少 return Promise.reject(error)
    },
  )
  ```
- **问题**：拦截器处理后未 return Promise.reject(error)，业务错误（440/422/429）的调用方 catch 拿不到错误，无法展示 detail 或对应中文消息
- **修复建议**：
  ```typescript
  // ✅ 拦截器处理后必须 reject，让调用方 catch 继续处理业务错误
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      // 处理认证 401...
      return Promise.reject(error)  // 必须返回
    },
  )
  ```
- **配置节点**：`interceptor_audit.require_reject_after_intercept`
- **规范引用**：meta-rule #66 / xianyu-hunter-dev v4.40.0
- **适用**：所有 axios/fetch 全局响应拦截器
- **不适用**：无拦截器的应用

## 🆕 v4.51.1 前端工具链与代码质量审查报告条目（F-REVIEW-192~196）

> 本节为 v4.51.1 新增 5 项检查点（基于 SonarQube 扫描与前端工具链检查）的报告条目模板。每条违规按以下格式记录，参数在 `config.yaml` 对应节点管理。所有检查点按代码模式匹配，不绑定特定文件名。

### F-REVIEW-192~196 检查结果汇总

| 检查点 | 名称 | 维度 | severity | 配置节点 | 违规数 | 状态 |
|--------|------|------|----------|----------|--------|------|
| F-REVIEW-192 | ESLINT-CONFIG-FORMAT-MATCH | 12 SonarQube 合规 | HIGH | `eslint_config_compatibility` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-193 | PACKAGE-SCRIPTS-COMPLETENESS | 12 工程化规范 | MEDIUM | `package_json_scripts_completeness` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-194 | TS-STRICT-CHECK | 4/11 TypeScript 严格/类型安全 | HIGH | `typescript_strict_check` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-195 | PWA-REGISTER-TYPE | 13 PWA 配置 | HIGH | `pwa_register_type_check` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-196 | MOBILE-DETECT-CLEANLINESS | 10/11 Hooks 设计/代码质量 | MEDIUM | `mobile_detect_cleanliness` | X | ✅ 通过 / ❌ 违规 |

### F-REVIEW-192 ESLINT-CONFIG-FORMAT-MATCH 违规详情

> ESLint v9+ 必须使用 eslint.config.js（flat config），禁止 .eslintrc.*（legacy config）。

1. **问题描述**：[package.json 安装了 eslint@^9+ 但项目根目录只有 .eslintrc.* / ESLint 启动报错 couldn't find an eslint.config file]
   - **位置**：`package.json` 第 X 行 + 项目根目录配置文件
   - **当前代码**：
     ```json
     // ❌ package.json 安装了 eslint v9+，但根目录只有 .eslintrc.js
     {
       "devDependencies": {
         "eslint": "^9.0.0"
       }
     }
     // 根目录存在 .eslintrc.js（legacy config）
     ```
   - **修复建议**：
     ```javascript
     // ✅ 按官方迁移指南转为 eslint.config.js（flat config）
     // eslint.config.js
     import js from '@eslint/js'
     export default [
       js.configs.recommended,
       // 其他配置...
     ]
     ```
   - **配置节点**：`eslint_config_compatibility`（version_threshold: 9, required_config_file: "eslint.config.js", legacy_config_patterns: [".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml"]）
   - **规范引用**：SKILL.md 维度12 / SonarQube 工具链
   - **适用**：使用 ESLint v9+ 的前端项目；CI/CD 流水线中 ESLint 启动失败的场景
   - **不适用**：使用 ESLint v8 及以下版本的项目；不使用 ESLint 的项目

### F-REVIEW-193 PACKAGE-SCRIPTS-COMPLETENESS 违规详情

> package.json 的 scripts 必须包含 test 脚本（即使为占位），支持 CI/CD 流水线调用。

1. **问题描述**：[package.json scripts 缺少 test 脚本 / npm test 报错 missing script: test]
   - **位置**：`package.json` 第 X 行
   - **当前代码**：
     ```json
     // ❌ scripts 只有 dev/build/preview/lint，缺少 test
     {
       "scripts": {
         "dev": "vite",
         "build": "tsc -b && vite build",
         "preview": "vite preview",
         "lint": "eslint src"
       }
     }
     ```
   - **修复建议**：
     ```json
     // ✅ 添加 test 脚本（项目已配置 vitest 时）
     {
       "scripts": {
         "dev": "vite",
         "build": "tsc -b && vite build",
         "preview": "vite preview",
         "lint": "eslint src",
         "test": "vitest run"
       }
     }
     // 或占位命令（无测试用例时）
     // "test": "echo \"no tests specified\" && exit 0"
     ```
   - **配置节点**：`package_json_scripts_completeness`（required_scripts: ["test", "build", "lint"], test_placeholder: "echo \"no tests specified\" && exit 0"）
   - **规范引用**：SKILL.md 维度12 / 工程化规范
   - **适用**：所有前端项目（尤其接入 CI/CD 流水线的项目）
   - **不适用**：纯静态资源项目；monorepo 中不直接运行测试的子包

### F-REVIEW-194 TS-STRICT-CHECK 违规详情

> tsc --noEmit 必须通过，禁止 @ts-ignore / @ts-nocheck 绕过类型检查。

1. **问题描述**：[tsc --noEmit 报错 / 代码中存在 @ts-ignore 或 @ts-nocheck 指令]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 使用 @ts-ignore 绕过类型检查
     // @ts-ignore
     const data = response.data as Item
     ```
   - **修复建议**：
     ```typescript
     // ✅ 修复类型错误，或用 @ts-expect-error 带原因注释
     // @ts-expect-error 后端类型定义待补齐，临时绕过
     const data = response.data as Item
     ```
   - **配置节点**：`typescript_strict_check`（strict_check: true, forbidden_directives: ["@ts-ignore", "@ts-nocheck"], allowed_directives: ["@ts-expect-error"], require_reason_comment: true）
   - **规范引用**：SKILL.md 维度4/11
   - **适用**：所有 TypeScript 前端项目；CI/CD 类型检查门禁
   - **不适用**：纯 JavaScript 项目；迁移中的 JS 文件

### F-REVIEW-195 PWA-REGISTER-TYPE 违规详情

> vite-plugin-pwa 的 registerType 必须为 'autoUpdate'，避免 SW 死锁导致旧缓存不更新。

1. **问题描述**：[vite.config 中 VitePWA({ registerType: 'prompt' }) / 移动端访问旧版本不刷新]
   - **位置**：`frontend/vite.config.ts` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ registerType 为 'prompt' 会导致 SW 死锁
     import { VitePWA } from 'vite-plugin-pwa'
     export default defineConfig({
       plugins: [
         VitePWA({
           registerType: 'prompt',  // ❌ 旧缓存不更新
         }),
       ],
     })
     ```
   - **修复建议**：
     ```typescript
     // ✅ 改为 'autoUpdate'，自动更新 SW 缓存
     import { VitePWA } from 'vite-plugin-pwa'
     export default defineConfig({
       plugins: [
         VitePWA({
           registerType: 'autoUpdate',  // ✅ 自动更新
         }),
       ],
     })
     ```
   - **配置节点**：`pwa_register_type_check`（required_register_type: "autoUpdate", forbidden_register_types: ["prompt"]）
   - **规范引用**：SKILL.md 维度13
   - **适用**：使用 vite-plugin-pwa 的 PWA 项目；移动端 PWA 应用
   - **不适用**：非 PWA 项目；使用 Workbox 原生配置的项目

### F-REVIEW-196 MOBILE-DETECT-CLEANLINESS 违规详情

> 移动端检测 Hook（含 useMobileDetect 及同类移动端/UA 检测 hooks）不得包含临时诊断代码（debug 参数、console.log 调试输出）。

1. **问题描述**：[移动端检测 hook 包含 debug 参数或 console.log/console.debug 调试输出]
   - **位置**：`frontend/src/hooks/xxx.ts` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ useMobileDetect hook 包含 debug 参数和 console.log
     export function useMobileDetect(options?: { debug?: boolean }) {
       const isMobile = /Mobi|Android/i.test(navigator.userAgent)
       if (options?.debug) {
         console.log('useMobileDetect:', isMobile)  // ❌ 临时诊断代码
       }
       return isMobile
     }
     ```
   - **修复建议**：
     ```typescript
     // ✅ 移除诊断代码，调试通过 DevTools 移动模拟器
     export function useMobileDetect() {
       const isMobile = /Mobi|Android/i.test(navigator.userAgent)
       return isMobile
     }
     ```
   - **配置节点**：`mobile_detect_cleanliness`（forbidden_patterns: ["debug", "console.log", "console.debug"], allowed_in_dev: false, hook_identify_patterns: ["useMobileDetect", "useMediaQuery", "useBreakpoint", "useDeviceDetect", "useUA", "useIsMobile"]）
   - **规范引用**：SKILL.md 维度10/11
   - **适用**：所有移动端检测/响应式断点/UA 检测相关 hooks
   - **不适用**：开发调试阶段（应通过 DevTools）；非移动端检测相关 hooks（由 F-REVIEW-DEBUG-CODE-CLEANUP 覆盖）

### v4.51.1 配置变更点

> 本次审查触发的 `config.yaml` 节点变更建议。所有变更遵循"无硬编码"原则。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 版本阈值调整 | `eslint_config_compatibility.version_threshold` | `9` | `<新阈值>` | ESLint 版本升级策略变更 | F-REVIEW-192 |
| 脚本列表扩展 | `package_json_scripts_completeness.required_scripts` | `["test", "build", "lint"]` | `[...现有, <新必需脚本>]` | CI/CD 流水线新增必需脚本 | F-REVIEW-193 |
| 禁止指令扩展 | `typescript_strict_check.forbidden_directives` | `["@ts-ignore", "@ts-nocheck"]` | `[...现有, <新禁止指令>]` | TypeScript 版本升级新增禁止指令 | F-REVIEW-194 |
| Hook 识别扩展 | `mobile_detect_cleanliness.hook_identify_patterns` | `["useMobileDetect", ...]` | `[...现有, <新 hook 名>]` | 项目新增移动端检测 hook | F-REVIEW-196 |

**变更后自检清单**：
- [ ] 无硬编码新增（所有数值/列表/关键字均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] references/checkpoints-index.md 已追加 F-REVIEW-192~196 索引
- [ ] references/version-changelog.md 已追加 v4.51.1 变更说明



## 🆕 v4.52.0 前端快照职责分离与多用户上下文传递报告条目（F-REVIEW-197/198）

> 本节为 v4.52.0 新增 2 项检查点（基于 2026-07-18 卖家评估 Bug 复盘）的报告条目模板。每条违规按以下格式记录，参数在 `config.yaml#data_propagation_frontend` 节点管理。

### F-REVIEW-197/198 检查结果汇总

| 检查点 | 名称 | 维度 | severity | 配置节点 | 违规数 | 状态 |
|--------|------|------|----------|----------|--------|------|
| F-REVIEW-197 | SNAPSHOT-FILTER-DISPLAY-SEPARATION | 7 API 调用规范 | HIGH | `data_propagation_frontend.snapshot_display_separation` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-198 | MULTI-USER-CONTEXT-PROPAGATION | 28 多用户认证上下文 | CRITICAL | `data_propagation_frontend.multiuser_context_propagation` | X | ✅ 通过 / ❌ 违规 |

### F-REVIEW-197 SNAPSHOT-FILTER-DISPLAY-SEPARATION 违规详情

> 前端展示价格时需区分"评估时价格"和"最新价格"；过滤组件（Select/Slider）应基于评估时价格（eval_snapshot_price），展示组件应基于最新价格（item_price）。

1. **问题描述**：[过滤组件基于最新价格导致旧 eval 事件被误判超范围隐藏 / 展示组件未区分评估时价格与最新价格 / 价格差异无提示]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 过滤组件基于最新价格 item_price，导致官方采集更新价格后旧 eval 被误判超范围
     <Slider
       min={priceRange[0]}
       max={priceRange[1]}
       value={[item.item_price, item.item_price]}
     />
     // 展示也只用 item_price，未区分评估时价格
     <span>{item.item_price}</span>
     ```
   - **修复建议**：
     ```typescript
     // ✅ 过滤组件基于评估时价格 eval_snapshot_price
     <Slider
       min={priceRange[0]}
       max={priceRange[1]}
       value={[item.eval_snapshot_price, item.eval_snapshot_price]}
     />
     // 展示基于最新价格，差异时给提示
     <span>{item.item_price}</span>
     {item.eval_snapshot_price !== item.item_price && (
       <Tooltip title={`评估时价格：${item.eval_snapshot_price}`}>
         <WarningOutlined />
       </Tooltip>
     )}
     ```
   - **配置节点**：`data_propagation_frontend.snapshot_display_separation`（filter_uses_snapshot: true, display_uses_latest: true, show_price_diff_hint: true, price_display_fields.eval_snapshot: "eval_snapshot_price", price_display_fields.latest: "item_price"）
   - **规范引用**：meta-rules #83 / xianyu-hunter-dev v4.52.0 / [data-propagation.md](../../../xianyu-hunter-dev/assets/guides/coding-rules/data-propagation.md)
   - **适用**：所有展示评估事件价格的前端组件（评估列表、评估明细、卖家评估菜单）；带价格范围过滤的前端页面
   - **不适用**：纯展示最新价格的页面（无评估时价格概念）；不涉及价格过滤的页面

### F-REVIEW-198 MULTI-USER-CONTEXT-PROPAGATION 违规详情

> 所有 API 调用必须携带认证字段（Cookie/credentials:include）；axios 拦截器仅在 401 且 detail === "Unauthorized" 时重定向；业务 440（Cookie 过期）走业务逻辑不触发全局登出。

1. **问题描述**：[fetch 请求遗漏 credentials: 'include' / axios 拦截器对所有 401 一律跳转登录页 / 业务 440 被全局拦截器拦截触发登出 / htmx 请求未配置 credentials meta]
   - **位置**：`frontend/src/api/xxx.ts` 第 X 行 或 `frontend/src/api/client.ts` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ fetch 未携带 credentials，cookie 不传递
     const res = await fetch('/api/evaluations', { method: 'GET' });

     // ❌ axios 拦截器对所有 401 一律跳转，业务 440 也被拦截
     client.interceptors.response.use(
       (response) => response,
       (error) => {
         if (error.response?.status === 401 || error.response?.status === 440) {
           window.location.href = '/app/login';
         }
         return Promise.reject(error);
       },
     );
     ```
   - **修复建议**：
     ```typescript
     // ✅ fetch 显式 credentials: 'include'
     const res = await fetch('/api/evaluations', {
       method: 'GET',
       credentials: 'include',
     });

     // ✅ axios 拦截器仅在 401 且 detail === 'Unauthorized' 时重定向，业务 440 走业务逻辑
     client.interceptors.response.use(
       (response) => response,
       (error) => {
         const isAuthUnauthorized =
           error.response?.status === 401 &&
           error.response?.data?.detail === 'Unauthorized';
         if (isAuthUnauthorized) {
           // 跳转登录页
         }
         // 业务 440（Cookie 过期）由调用方 catch 处理，不触发全局登出
         return Promise.reject(error);
       },
     );

     // ✅ htmx 通过 meta 配置传递凭证
     // <meta name="htmx-config" content='{"withCredentials": true}'>
     ```
   - **配置节点**：`data_propagation_frontend.multiuser_context_propagation`（required_auth_headers: ["Cookie"], fetch_credentials: "include", interceptor_redirect_condition: "status==401 and detail=='Unauthorized'", business_440_no_redirect: true, htmx_credentials_meta: true）
   - **规范引用**：meta-rules #83 / xianyu-hunter-dev v4.52.0 / [multi-user-auth.md](../../../xianyu-hunter-dev/assets/guides/coding-rules/multi-user-auth.md)
   - **适用**：所有调用后端 API 的前端代码（fetch/axios/htmx）；带全局响应拦截器的 SPA 应用；多用户系统
   - **不适用**：无认证的公共 API；纯 SSR 应用；测试 mock
   - **与已有规则的关系**：
     - 与 v4.32.0 F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING 配合（前者关注 credentials 与状态码分支，本规则聚焦业务 440 不触发登出）
     - 与 v4.45.0 F-REVIEW-154 配合（拦截器状态码区分）

### v4.52.0 配置变更点

> 本次审查触发的 `config.yaml` 节点变更建议。所有变更遵循"无硬编码"原则。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 字段名扩展 | `data_propagation_frontend.snapshot_display_separation.price_display_fields` | `{eval_snapshot: "eval_snapshot_price", latest: "item_price"}` | `{...现有, <新字段名>}` | 后端新增价格类字段时同步 | F-REVIEW-197 |
| 认证头扩展 | `data_propagation_frontend.multiuser_context_propagation.required_auth_headers` | `["Cookie"]` | `[...现有, <新认证头>]` | 新增认证方式（如 Authorization） | F-REVIEW-198 |
| 状态码分支扩展 | `data_propagation_frontend.multiuser_context_propagation.interceptor_redirect_condition` | `status==401 and detail=='Unauthorized'` | `<新条件>` | 后端调整认证失败响应体 | F-REVIEW-198 |

**变更后自检清单**：
- [ ] 无硬编码新增（所有数值/列表/关键字均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] references/version-changelog.md 已追加 v4.52.0 变更说明

## 🆕 v4.61.0 重构安全性审查报告条目（F-REVIEW-220~226）

> 本节为 v4.61.0 新增 7 项检查点（基于复盘规范集 A/B/D 三类前端版本）的报告条目模板。每条违规按以下格式记录，参数在 `config.yaml#refactoring_safety_checks` 节点管理。所有阈值参数（执行时长、变更文件数、引用计数等）通过该节点集中管理，不硬编码。详细判定标准与反模式示例见 [references/refactoring-safety-checks.md](../references/refactoring-safety-checks.md)。

**触发条件**：本次变更为重构类操作（重命名 / 常量迁移 / Hook 改造 / 模块拆分 / 构建脚本变更）时本章节必填；纯 Bug 修复或新增功能本章节填"不适用"。

### F-REVIEW-220~226 检查结果汇总

| 检查点 | 名称 | 维度 | severity | 配置节点 | 违规数 | 状态 |
|--------|------|------|----------|----------|--------|------|
| F-REVIEW-220 | CONSTANT-CONFIG-DRIVEN 常量配置化 5 步法 | 11/4 | MAJOR | `refactoring_safety_checks.constant_config_driven` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-221 | REACT-HOOKS-SCOPE-CONTRACT React Hooks 作用域契约 | 3/10 | HIGH | `refactoring_safety_checks.react_hooks_scope_contract` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-222 | IMPORT-NAME-CHANGE-CHECKLIST 导入名称变更 checklist | 11/2 | MAJOR | `refactoring_safety_checks.import_name_change_checklist` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-223 | LONG-TASK-BUILD-LOG-REDIRECT 长任务前端构建日志输出 | 12 | MAJOR | `refactoring_safety_checks.long_task_build_log_redirect` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-224 | SYSTEM-RESOURCE-OVERLOAD-TOLERANCE 系统资源过载容错 | 12/16 | WARNING | `refactoring_safety_checks.system_resource_overload_tolerance` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-225 | CROSS-FILE-CONTRACT-SYNC 跨文件引用同步校验 | 11/6 | CRITICAL | `refactoring_safety_checks.cross_file_contract_sync` | X | ✅ 通过 / ❌ 违规 |
| F-REVIEW-226 | STATE-PERSISTENCE-UNIFIED-ENTRY 状态持久化统一入口 | 6/10 | HIGH | `refactoring_safety_checks.state_persistence_unified_entry` | X | ✅ 通过 / ❌ 违规 |

### F-REVIEW-220 CONSTANT-CONFIG-DRIVEN 违规详情

> 常量重构必须遵循"grep 全量 → 新增常量 → 源文件改造 → 核对引用 → 文档同步"五步闭环。

1. **问题描述**：[常量已迁移到 constants.ts 但源文件仍保留旧的内联字面量 / 改动常量定义但未执行 grep 全量引用扫描 / 注释仍引用旧常量名]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 常量已迁移但源文件仍保留旧的内联字面量
     setInterval(refresh, 10000)  // 应改为 POLL_INTERVAL_MS
     ```
   - **修复建议**：
     ```typescript
     // ✅ 从 constants 读取
     import { POLL_INTERVAL_MS } from '@/config/constants'
     setInterval(refresh, POLL_INTERVAL_MS)
     ```
   - **配置节点**：`refactoring_safety_checks.constant_config_driven`（require_grep_before_refactor: true, require_tsc_verify_after: true, require_doc_sync: true）
   - **规范引用**：references/refactoring-safety-checks.md §A1
   - **适用**：常量迁移 / 重命名 / 值修改需核对引用点
   - **不适用**：单次性临时变量 / 测试 fixture / 已被 ESLint 规则覆盖的简单替换

### F-REVIEW-221 REACT-HOOKS-SCOPE-CONTRACT 违规详情

> 组件作用域与模块作用域的边界不可破坏，useState/useRef 必须在组件函数体内。

1. **问题描述**：[组件 useState/useRef 被改为模块级 `let` 变量 / Hook 被改为普通函数丢失 `use` 前缀 / 模块级常量被组件修改 / 组件 re-mount 后状态未恢复]
   - **位置**：`frontend/src/pages/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ useState 提升为模块级变量，多实例共享状态
     let selectedRowKeys: React.Key[] = []
     function TaskList() {
       // selectedRowKeys 在多个 TaskList 实例间共享
     }
     ```
   - **修复建议**：
     ```typescript
     // ✅ 保持 useState 在组件内
     function TaskList() {
       const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
     }
     ```
   - **配置节点**：`refactoring_safety_checks.react_hooks_scope_contract`（forbid_module_level_mutable_in_component: true, require_use_prefix_for_hooks: true, require_persistent_state_for_cross_mount: true）
   - **规范引用**：references/refactoring-safety-checks.md §A2
   - **适用**：Hook 重构 / 状态管理方式变更 / 提取自定义 Hook
   - **不适用**：纯工具函数 / 模块级不可变常量 / SSR 场景

### F-REVIEW-222 IMPORT-NAME-CHANGE-CHECKLIST 违规详情

> 重命名导出符号必须按调用类型分类核对（Hook 保留 `()` / 组件改 JSX / 函数加 `()`）。

1. **问题描述**：[Hook 改名为普通函数后调用方未加 `()` / 函数改名为组件后调用方未改为 JSX / 删除导出名前未 grep]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ Hook 改名为普通函数，调用方未加 ()
     const tasks = fetchTasks  // 丢失 () 调用，tasks 是函数引用
     ```
   - **修复建议**：
     ```typescript
     // ✅ 调用方加 () 调用
     const tasks = fetchTasks()
     ```
   - **配置节点**：`refactoring_safety_checks.import_name_change_checklist`（require_grep_before_rename: true, require_tsc_verify_after: true, require_lint_verify_after: true）
   - **规范引用**：references/refactoring-safety-checks.md §A3
   - **适用**：重命名导出符号 / 修改导出方式 / 拆分模块
   - **不适用**：仅修改实现细节 / 内部私有变量 / 自动生成代码

### F-REVIEW-223 LONG-TASK-BUILD-LOG-REDIRECT 违规详情

> PowerShell sink cmdlet 会缓冲整个输出流，长任务执行时终端无反馈。必须改用文件重定向。

1. **问题描述**：[构建脚本使用 `| Select-Object -Last N` / `| Out-Host -Paging` / 长任务未设置超时]
   - **位置**：`scripts/build.ps1` 第 X 行 或 构建脚本中的 PowerShell 命令
   - **当前代码**：
     ```powershell
     # ❌ sink cmdlet 导致缓冲，长任务无输出
     npm --prefix frontend run build | Select-Object -Last 50
     ```
   - **修复建议**：
     ```powershell
     # ✅ 文件重定向 + 实时 tail
     $logFile = "frontend-build-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
     Start-Process -FilePath "npm" -ArgumentList "run","build" `
       -WorkingDirectory "frontend" `
       -RedirectStandardOutput $logFile `
       -NoNewWindow -Wait
     Get-Content $logFile -Wait -Tail 20
     ```
   - **配置节点**：`refactoring_safety_checks.long_task_build_log_redirect`（long_task_threshold_seconds: 30, forbidden_sink_cmdlets: [Select-Object, Out-Host, Out-String, more, less], require_timeout: true, default_timeout_seconds: 300）
   - **规范引用**：references/refactoring-safety-checks.md §B1
   - **适用**：PowerShell 终端执行前端构建 / 类型检查 / 测试 / CI/CD 流水线
   - **不适用**：bash/zsh 环境 / 短任务 / IDE 内置终端交互式命令

### F-REVIEW-224 SYSTEM-RESOURCE-OVERLOAD-TOLERANCE 违规详情

> 全量 tsc 检查卡住时必须提供单文件 fallback + 监控 Node 进程内存。

1. **问题描述**：[全量 tsc 卡住无 fallback / Node 内存超过阈值未告警 / 未设置 NODE_OPTIONS 堆内存上限]
   - **位置**：`scripts/typecheck.ps1` 第 X 行 或 CI/CD 类型检查步骤
   - **当前代码**：
     ```powershell
     # ❌ 全量 tsc 无 fallback，卡住无响应
     tsc --noEmit
     ```
   - **修复建议**：
     ```powershell
     # ✅ 单文件检查 fallback + 监控 Node 内存
     $env:NODE_OPTIONS = "--max-old-space-size=8192"
     # 卡住时 fallback
     tsc --noEmit --skipLibCheck frontend/src/pages/Tasks/TaskList.tsx
     ```
   - **配置节点**：`refactoring_safety_checks.system_resource_overload_tolerance`（node_memory_threshold_mb: 4096, long_task_threshold_seconds: 60, fallback_to_single_file: true, node_options_env: "--max-old-space-size=8192"）
   - **规范引用**：references/refactoring-safety-checks.md §B2
   - **适用**：大型 TypeScript 项目全量类型检查 / CI/CD tsc 卡住 / vitest 大量用例
   - **不适用**：小型项目 / 非构建类任务 / 已使用 SWC/esbuild

### F-REVIEW-225 CROSS-FILE-CONTRACT-SYNC 违规详情

> 修改导出符号后必须运行 `tsc --noEmit` 验证，catch ImportError / NameError。

1. **问题描述**：[修改导出符号前未 grep / 重构后未运行 tsc / 未检查动态 `import()` 引用 / 修改函数签名但未同步调用方]
   - **位置**：`frontend/src/utils/xxx.ts` 第 X 行（导出方）+ `frontend/src/pages/yyy.tsx` 第 X 行（引用方）
   - **当前代码**：
     ```typescript
     // ❌ 删除导出符号但引用方未迁移
     // utils/format.ts 中删除了 formatPrice
     // ItemList.tsx 仍引用
     import { formatPrice } from '@/utils/format'  // 运行时 ImportError
     ```
   - **修复建议**：
     ```typescript
     // ✅ 引用方迁移到新位置 + tsc 验证
     import { formatPrice } from '@/utils/currency'
     // 运行 tsc --noEmit 确认无 ImportError
     ```
   - **配置节点**：`refactoring_safety_checks.cross_file_contract_sync`（require_grep_before_export_change: true, require_tsc_verify_after: true, require_lint_verify_after: true, require_test_verify_after: true, require_build_verify_after: true）
   - **规范引用**：references/refactoring-safety-checks.md §D1
   - **适用**：删除/重命名导出符号 / 修改函数签名 / 修改模块路径 / 拆分合并模块
   - **不适用**：仅修改实现细节 / 测试代码内部重构 / 自动生成代码

### F-REVIEW-226 STATE-PERSISTENCE-UNIFIED-ENTRY 违规详情

> 业务参数必须从 config 读取 / localStorage key 必须有命名空间 / 状态读取必须有类型守卫。

1. **问题描述**：[业务参数硬编码在组件内 / localStorage key 无命名空间 / 状态读取无类型守卫 / 命名风格不一致]
   - **位置**：`frontend/src/pages/xxx.tsx` 第 X 行
   - **当前代码**：
     ```typescript
     // ❌ 业务参数硬编码 + localStorage key 无命名空间 + 无类型守卫
     setInterval(refresh, 10000)  // 10000 硬编码
     localStorage.setItem('columns', JSON.stringify(columns))  // 无命名空间
     const cols = JSON.parse(localStorage.getItem('columns') || '[]')  // 无类型守卫
     ```
   - **修复建议**：
     ```typescript
     // ✅ 从 config 读取 + 命名空间 key + 类型守卫
     import { POLL_INTERVALS } from '@/config/constants'
     setInterval(refresh, POLL_INTERVALS.TASK_LIST)

     const STORAGE_KEY = 'xh.orders.columns'  // 命名空间
     localStorage.setItem(STORAGE_KEY, JSON.stringify(columns))

     function isColumn(value: unknown): value is Column {
       return typeof value === 'object' && value !== null &&
         'key' in value && 'width' in value
     }
     const cols = loadColumns()  // 内部有类型守卫
     ```
   - **配置节点**：`refactoring_safety_checks.state_persistence_unified_entry`（forbid_hardcoded_business_params: true, require_namespace_for_localstorage: true, require_type_guard_for_state_read: true, namespace_prefix: "xh", namespace_pattern: "xh\\.<page>\\.<field>"）
   - **规范引用**：references/refactoring-safety-checks.md §D2
   - **适用**：业务参数 / 用户偏好持久化 / localStorage 状态管理 / 跨页面共享状态
   - **不适用**：一次性临时变量 / 服务端状态 / 临时 UI 状态

### v4.61.0 配置变更点

> 本次审查触发的 `config.yaml#refactoring_safety_checks` 节点变更建议。所有变更遵循"无硬编码"原则。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 阈值调整 | `refactoring_safety_checks.long_task_build_log_redirect.long_task_threshold_seconds` | `30` | `<新阈值>` | 项目规模变化导致长任务判定阈值调整 | F-REVIEW-223 |
| 内存阈值调整 | `refactoring_safety_checks.system_resource_overload_tolerance.node_memory_threshold_mb` | `4096` | `<新阈值>` | Node 版本升级或项目规模变化 | F-REVIEW-224 |
| sink cmdlet 扩展 | `refactoring_safety_checks.long_task_build_log_redirect.forbidden_sink_cmdlets` | `[Select-Object, Out-Host, Out-String, more, less]` | `[...现有, <新 cmdlet>]` | PowerShell 版本升级新增 sink cmdlet | F-REVIEW-223 |
| 命名空间前缀调整 | `refactoring_safety_checks.state_persistence_unified_entry.namespace_prefix` | `xh` | `<新前缀>` | 项目命名规范变更 | F-REVIEW-226 |
| 验证命令扩展 | `refactoring_safety_checks.cross_file_contract_sync.verify_commands` | `[typecheck, lint, test, build]` | `[...现有, <新命令>]` | CI/CD 流水线新增验证步骤 | F-REVIEW-225 |

**变更后自检清单**：
- [ ] 无硬编码新增（所有数值/列表/关键字均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] references/checkpoints-index.md 已追加 F-REVIEW-220~226 索引
- [ ] references/version-changelog.md 已追加 v4.61.0 变更说明
- [ ] references/refactoring-safety-checks.md 已与配置节点一致

## 🆕 v4.70.0 源码文件编码完整性审查报告条目（F-REVIEW-246）

> 本节为 v4.70.0 新增检查点（基于登录页提示信息乱码复盘：源码中文被替换为字面量 `?` 0x3F，及 GBK 误读为 UTF-8 乱码）。配套 xianyu-hunter-dev step 280、后端 B-REVIEW-337、测试模式 AK。判定参数全部来自 `config.yaml#coding_standards.source_file_encoding_integrity`，**禁止硬编码**路径/阈值/严重级。扫描**只读**，仅输出 `file:line` 证据，不自动改写。

### F-REVIEW-246 检查结果汇总

| 检查点 | 名称 | 维度 | severity | 配置节点 | 违规数 | 状态 |
|--------|------|------|----------|----------|--------|------|
| F-REVIEW-246 | SOURCE-FILE-ENCODING-INTEGRITY 源码文件编码完整性 | 编码规范 | HIGH | `coding_standards.source_file_encoding_integrity` | X | ✅ 通过 / ❌ 违规 |

### F-REVIEW-246 SOURCE-FILE-ENCODING-INTEGRITY 违规详情

> 前端源码文件**本体**在磁盘上出现非 ASCII 字符（中文等）被替换为连续 `?`（≥ `min_consecutive` 个）且处于非 ASCII 上下文，或含 U+FFFD 替换字符，或（可选）命中 GBK-as-UTF-8 误读特征（`鑱岃`/`、` 类）。编译/运行通常仍正常，但用户可见文案、注释、日志出现损坏，并污染 Git 历史。

**判定信号（来自配置）**：

| 信号 | 规则 | 配置键 |
|------|------|--------|
| 连续 `?` 且非 ASCII 上下文 | `[\u4e00-\u9fff]\?{N,}\|\?{N,}[\u4e00-\u9fff]`（N=`min_consecutive`） | `min_consecutive` |
| Unicode 替换字符 | 行内含 `\ufffd` | `check_fffd` |
| GBK 误读特征 | （`check_gbk_misdecode=true` 时）`鑱`/`、` 等非预期字符簇 | `check_gbk_misdecode` |

1. **问题描述**：[源码中文被替换为连续 `?` / 源码含 U+FFFD / 源码含 GBK 误读乱码 / HEAD 已提交版本携带损坏字符]
   - **位置**：`frontend/src/xxx.tsx` 第 X 行（扫描输出 `file:line`）
   - **证据（只读扫描命令）**：
     ```bash
     grep -rPn '[\x{4e00}-\x{9fff}]\?{3,}|\?{3,}[\x{4e00}-\x{9fff}]' frontend/src
     grep -rPn '\x{fffd}' frontend/src
     # 修复后全仓复扫确认 0 命中
     grep -rPn '\?{3,}' frontend/src && echo "仍有残留" || echo "OK"
     ```
   - **当前代码**：
     ```typescript
     // ❌ 源码本体损坏：中文被替换为 ?
     message.error('??????，请重新登录');
     ```
   - **修复建议**：
     ```typescript
     // ✅ 还原正确的中文文案；npx tsc --noEmit 校验语法
     message.error('登录已过期，请重新登录');
     ```
   - **配置节点**：`coding_standards.source_file_encoding_integrity`（scan_globs / scan_exclude / min_consecutive / check_fffd / check_gbk_misdecode / severity）
   - **规范引用**：xianyu-hunter-dev step 280（SOURCE-FILE-ENCODING-INTEGRITY-01）/ 后端 B-REVIEW-337 / 测试模式 AK
   - **修复协议**：S1 分类（源码本体 vs 运行时）→ S2 按 `scan_globs` 扫描 → S3 匹配信号 → S4 输出 `file:line` → S5 人工确认排除合法 `?`（`https?://`、正则可选匹配、占位串）→ S6 还原中文 + `tsc --noEmit` 校验 → S7 全仓复扫 0 命中 → S8 pre-commit/CI 门禁
   - **适用**：含中文/非 ASCII 字符的前端源码（`.ts`/`.tsx`/`.js`/`.jsx`/`.json`/`.md`）；跨编辑器/OS 保存后可疑 `?` 或乱码；合并冲突解决后；CI 门禁；历史提交回溯
   - **不适用**：运行时 API 响应乱码（查 Content-Type charset / 后端）；终端 stdout 显示乱码；浏览器字体缺失"方框/豆腐块"；字符串/正则中合法 `?`；纯 ASCII 文件
   - **与已有规则的关系**：
     - 与运行时编码检查（HTTP 响应 charset / `B-REVIEW-WINDOWS-TERMINAL-ENCODING`）**正交**：本规则只管"源码文件本体"，运行时数据损坏由 ENC 系列与测试模式 K 覆盖
     - 与 `v4.41.0` 编码规范防御性复盘（F-REVIEW-148~151）互补：彼为运行时/契约层，本为源码静态完整性

### v4.70.0 配置变更点

> 本次审查触发的 `config.yaml#coding_standards.source_file_encoding_integrity` 节点（新增）。所有参数遵循"无硬编码"原则。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 扫描范围扩展 | `coding_standards.source_file_encoding_integrity.scan_globs` | `[frontend/src/**/*.{ts,tsx,js,jsx,json,md}]` | `[...现有, <新 glob>]` | 项目新增源码目录 | F-REVIEW-246 |
| 阈值调整 | `coding_standards.source_file_encoding_integrity.min_consecutive` | `3` | `<新阈值>` | 误报/漏报调优 | F-REVIEW-246 |
| 开关开启 | `coding_standards.source_file_encoding_integrity.check_gbk_misdecode` | `false` | `true` | 需检测 GBK 误读类乱码 | F-REVIEW-246 |

**变更后自检清单**：
- [ ] 无硬编码新增（扫描路径/阈值/严重级均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] references/checkpoints-index.md 已追加 F-REVIEW-246 索引
- [ ] references/source-file-encoding-integrity.md 已与配置节点一致

### 🟠 [HIGH] F-REVIEW-246：源码中文被替换为字面量 `?`

- **位置**：`frontend/src/xxx.tsx` 第 X 行（扫描证据 `file:line`）
- **证据**：`grep -rPn '[\x{4e00}-\x{9fff}]\?{3,}|\?{3,}[\x{4e00}-\x{9fff}]' frontend/src` 命中
- **问题**：源码文件本体中文被替换为连续 `?`，用户可见文案/注释/日志损坏，且可能已随 `HEAD` 提交污染历史
- **修复建议**：
  ```typescript
  // ✅ 还原正确的中文；tsc --noEmit 校验；全仓复扫 0 命中；必要时修正 HEAD 已提交版本
  message.error('登录已过期，请重新登录');
  ```
- **配置节点**：`coding_standards.source_file_encoding_integrity`
- **规范引用**：xianyu-hunter-dev step 280 / 后端 B-REVIEW-337 / 测试模式 AK
- **适用**：含中文的源码文件；跨工具保存后可疑 `?`
- **不适用**：运行时数据乱码（→ ENC/模式 K）；纯 ASCII 文件；正则中合法 `?`
