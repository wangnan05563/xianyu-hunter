# F-REVIEW 检查点索引

> 本文件为 `xianyu-frontend-code-review` skill 所有 F-REVIEW 检查点的纯索引表格。
> 详细判定标准、反模式、正确模式见 SKILL.md 对应维度章节。
> 维度编号对应 SKILL.md 36 维度审查框架。

## 检查点总表

| ID | 名称 | 维度 | 版本 | 配置节点（config.yaml） | 规范源 |
|----|------|------|------|-------------------------|--------|
| F-REVIEW-UI-STATE-INDEPENDENCE | UI 状态独立性原则 | 3 | v4.2 | `ui_state_independence` | SKILL.md 维度3 |
| F-REVIEW-STATE-MACHINE-UI | 状态机 UI 视觉标识完整性 | 3 | v4.11 | `state_machine_ui` | SKILL.md 维度3 |
| F-REVIEW-STATE-FUNCTIONAL-ALIGN | 状态显示与功能可用性一致 | 3 | v4.16 | `state_functional_align` | SKILL.md 维度3 |
| F-REVIEW-FILTER-EMPTY-STATE | 过滤空状态区分 | 3 | v4.14 | `filter_empty_state` | SKILL.md 维度3 |
| F-REVIEW-EFFECT-MINIMIZE | useEffect 副作用最小化 | 3 | v4.33 | `effect_minimize` | meta-rule #43 前端侧 |
| F-REVIEW-STATE-ENUM-ALIGN | 前后端状态枚举值对齐 | 4 | v4.11 | `state_enum_align` | SKILL.md 维度4 |
| F-REVIEW-INPUT-NUMBER-BOUNDS | InputNumber 边界约束 | 4 | v4.12 | `input_number_bounds` | SKILL.md 维度4 |
| F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY | 默认值操作符一致性检查 | 4 | v4.25 | `default_operator_consistency` | SKILL.md 维度4 |
| F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE | AntD 主题 token 动态覆盖模式 | 5 | v4.8 | `antd_theme_token_override` | SKILL.md 维度5 |
| F-REVIEW-SSE-CONN-MGMT | SSE 连接管理三要素 | 5 | v4.33 | `sse_conn_mgmt` | meta-rule #43 前端侧 |
| F-REVIEW-THEME-DYNAMIC-ADAPT | 主题色动态适配 | 5 | v4.33 | `theme_dynamic_adapt` | meta-rule #43 前端侧 |
| F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND | 多源状态同步统一入口（前端侧） | 6 | v4.6 | `multi_write_entry_frontend` | SKILL.md 维度6 |
| F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY | 前端缓存与后端状态机一致性 | 6 | v4.11 | `dual_link_cache_consistency` | SKILL.md 维度6 |
| F-REVIEW-CONFIG-LINKAGE | 配置全链路生效验证（前端侧） | 7 | v4.5 | `config_linkage` | SKILL.md 维度7 |
| F-REVIEW-FILTER-SCENARIO-FRONTEND | 过滤逻辑场景区分（前端侧） | 7 | v4.7 | `filter_scenario_frontend` | SKILL.md 维度7 |
| F-REVIEW-FILTER-VISIBILITY | 过滤结果可见性（前端侧） | 7 | v4.10 | `filter_visibility` | SKILL.md 维度7 |
| F-REVIEW-BATCH-OPERATION | 批量操作完整流程 | 7 | v4.12 | `batch_operation` | SKILL.md 维度7 |
| F-REVIEW-VERSION-SOURCE-ALIGN | 元数据源显示对齐规范 | 7 | v4.20 | `version_source_align` | SKILL.md 维度7 |
| F-REVIEW-THREE-STATE-NULL-SEMANTICS | API 更新接口三态语义检查 | 7 | v4.25 | `three_state_null_semantics` | SKILL.md 维度7 |
| F-REVIEW-XSS-ESCAPE | 用户输入字段 HTML 转义 | 7 | v4.12 | `xss_escape` | SKILL.md 维度7 |
| F-REVIEW-ERROR-CONTRACT-TIMEOUT | 前后端错误码契约与超时识别 | 7 | v4.13 | `error_contract_timeout` | SKILL.md 维度7 |
| F-REVIEW-RETRY-BACKOFF | 前端可重试错误集与退避策略 | 7 | v4.13 | `retry_backoff` | SKILL.md 维度7 |
| F-REVIEW-FILTER-BACKEND-ALIGN | 前端过滤与后端分类对齐 | 7 | v4.14 | `filter_backend_align` | SKILL.md 维度7 |
| F-REVIEW-FIELD-NAME-ALIGN | 字段名三层一致性规范 | 7 | v4.21 | `field_name_align` | SKILL.md 维度7 |
| F-REVIEW-CONFIG-PERSIST-VERIFY | 配置持久化端到端验证规范 | 7 | v4.21 | `config_persist_verify` | SKILL.md 维度7 |
| F-REVIEW-ASYNC-FEEDBACK | 异步操作用户反馈三态 | 10 | v4.7 | `async_feedback` | SKILL.md 维度10 |
| F-REVIEW-FREQ-STATS-POLLING | 累计统计类 API 定时刷新 | 10 | v4.9 | `freq_stats_polling` | SKILL.md 维度10 |
| F-REVIEW-ASYNC-CONFIG-LOAD | 异步配置加载与竞态保护 | 10 | v4.12 | `async_config_load` | SKILL.md 维度10 |
| F-REVIEW-ASYNC-RACE-CONDITION | 长耗时异步请求 race condition 防护 | 10 | v4.16 | `async_race_condition` | SKILL.md 维度10 |
| F-REVIEW-UI-PREFERENCE-PERSISTENCE | 用户偏好类 UI 状态持久化复用 usePersistentState | 10 | v4.24 | `ui_preference_persistence` | SKILL.md 维度10 |
| F-REVIEW-FILTER-PAGINATION-ADAPT | 前端过滤后分页参数适配 | 10 | v4.14 | `filter_pagination_adapt` | SKILL.md 维度10 |
| F-REVIEW-ASYNC-RACE-GUARD | 异步竞态防护 | 10 | v4.33 | `async_race_guard` | meta-rule #43 前端侧 |
| F-REVIEW-NULL-SEMANTICS | null/undefined/空字符串语义区分 | 11 | v4.12 | `null_semantics` | SKILL.md 维度11 |
| F-REVIEW-CONFIG-DRIVEN-TOGGLE | 配置驱动功能开关模式 | 11 | v4.4 | `config_driven_toggle` | SKILL.md 维度11 |
| F-REVIEW-ERROR-SEMANTICS | 错误提示语义准确性 | 11 | v4.5 | `error_semantics` | SKILL.md 维度11 |
| F-REVIEW-DATA-FLOW-TRACE-FRONTEND | 字段为空 5 点追踪（前端侧） | 11 | v4.7 | `data_flow_trace_frontend` | SKILL.md 维度11 |
| F-REVIEW-DEBUG-CODE-CLEANUP | 临时 DEBUG 代码清理 | 11 | v4.15 | `debug_code_cleanup` | SKILL.md 维度11 |
| F-REVIEW-FIELD-CONTRACT-ALIGN | 前后端字段契约对齐 | 11 | v4.16 | `field_contract_align` | SKILL.md 维度11 |
| F-REVIEW-ERROR-HANDLER-EXTRACT | 重复错误处理抽取 | 11 | v4.16 | `error_handler_extract` | SKILL.md 维度11 |
| F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION | 模型能力元数据集中展示与降级状态可视化 | 11 | v4.23 | `model_capability_centralization` | SKILL.md 维度11 |
| F-REVIEW-PWA-CACHE-VERIFY | PWA 缓存验证规范 | 13 | v4.22 | `pwa_cache_verify` | SKILL.md 维度13 |
| F-REVIEW-SSE-ERROR-HANDLING | SSE 错误事件状态码分类处理 | 15 | v4.1 | `sse_error_handling` | SKILL.md 维度15 |
| F-REVIEW-STATE-ATOMICITY | 状态切换原子性 | 15 | v4.33 | `state_atomicity` | meta-rule #43 前端侧 |
| F-REVIEW-REUSE-PATTERN-FRONTEND | 复用既有模式原则（前端侧） | 18 | v4.7 | `reuse_pattern_frontend` | SKILL.md 维度18 |
| F-REVIEW-SCHEDULER-STATUS-DISPLAY | 调度器状态展示规范 | 18 | v4.19 | `scheduler_status_display` | SKILL.md 维度18 |
| F-REVIEW-DEAD-CODE | 长期存活对象禁止赋值给局部变量 | 19 | — | `dead_code` | SKILL.md 维度19 |
| F-REVIEW-TRY-FINALLY-INIT | try/finally 变量初始化 | 19 | — | `try_finally_init` | SKILL.md 维度19 |
| F-REVIEW-CROSS-COMPONENT-STATE | 跨组件状态同步 | 19 | — | `cross_component_state` | SKILL.md 维度19 |
| F-REVIEW-ERROR-HINT-ROUTABLE | 错误提示路由可操作性 | 19 | — | `error_hint_routable` | SKILL.md 维度19 |
| F-REVIEW-API-DATA-SOURCE-CONSISTENCY | API 响应消费一致性 | 19 | — | `api_data_source_consistency` | SKILL.md 维度19 |
| F-REVIEW-TYPE-CONTRACT-ALIGN | 前后端类型契约对齐 | 19 | — | `type_contract_align` | SKILL.md 维度19 |
| F-REVIEW-ERROR-CODE-CONSUMPTION | error_code 消费决策 | 19 | — | `error_code_consumption` | SKILL.md 维度19 |
| F-REVIEW-ERROR-HANDLING-CONSISTENCY | 错误处理一致性检查 | 20 | v4.25 | `error_handling_consistency` | SKILL.md 维度20 |
| F-REVIEW-ERROR-CODE-BRANCH | 错误展示按 error_code 字段分支 | 25 | v4.27 | `error_code_branch` | SKILL.md 维度25 |
| F-REVIEW-PRECHECK-API-DELEGATION | 数据完整性预检委托后端 | 25 | v4.27 | `precheck_api_delegation` | SKILL.md 维度25 |
| F-REVIEW-MOCK-FIELD-SET-SYNC | mock 数据完整字段集同步 | 25 | v4.27 | `mock_field_set_sync` | SKILL.md 维度25 |
| F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION | 业务关键字常量集中管理 | 27 | v4.31 | `business_keyword_centralization` | SKILL.md 维度27 |
| F-REVIEW-EVENT-TYPE-EXACT-MATCH | 事件类型过滤精确匹配 | 27 | v4.31 | `event_type_exact_match` | SKILL.md 维度27 |
| F-REVIEW-FIELD-NAME-CASE-SENSITIVE | 前后端字段名大小写敏感检查 | 27 | v4.31 | `field_name_case_sensitive` | SKILL.md 维度27 |
| F-REVIEW-MULTI-USER-CONTEXT-ISOLATION | 多用户上下文隔离 | 28 | v4.32 | `multi_user_context_isolation` | SKILL.md 维度28 |
| F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING | 认证 token cookie 处理 | 28 | v4.32 | `auth_token_cookie_handling` | SKILL.md 维度28 |
| F-REVIEW-EMBEDDED-LAYOUT-HEIGHT | 嵌入式布局高度 | 29 | v4.33 | `embedded_layout_height` | meta-rule #43 前端侧 |
| F-REVIEW-COMPONENT-REGISTRY | 组件注册完整性 | 29 | v4.33 | `component_registry` | meta-rule #43 前端侧 |
| F-REVIEW-FILTER-TRANSPARENCY | 过滤透明化 | 29 | v4.33 | `filter_transparency` | meta-rule #43 前端侧 |
| F-REVIEW-DATA-SOURCE-VERIFY | 数据源正确性验证 | 29 | v4.33 | `data_source_verify` | meta-rule #43 前端侧 |
| F-REVIEW-STATS-RANGE-CALIBRATE | 统计范围校准 | 29 | v4.33 | `stats_range_calibrate` | meta-rule #43 前端侧 |
| F-REVIEW-UI-SEMANTICS-SPLIT | 按钮与状态语义分离 | 29 | v4.33 | `ui_semantics_split` | meta-rule #43 前端侧 |
| F-REVIEW-PERSIST-BUSINESS-SWITCH | 用户可配置开关持久化 | 29 | v4.33 | `persist_business_switch` | meta-rule #43 前端侧 |
| F-REVIEW-ERROR-MESSAGE-PASS | 错误消息透传 | 29 | v4.33 | `error_message_pass` | meta-rule #43 前端侧 |
| F-REVIEW-API-CONTRACT-CONSISTENCY | API 契约一致性 | 29 | v4.33 | `api_contract_consistency` | meta-rule #43 前端侧 |
| F-REVIEW-110 | 批量断路器四要素 UI 反馈 | 29 | v4.34 | `data_contract_temporal` | meta-rule #25-30 前端侧 |
| F-REVIEW-111 | ErrorBoundary 完整 stack 上报 | 29 | v4.34 | `data_contract_temporal` | meta-rule #25-30 前端侧 |
| F-REVIEW-112 | ISO datetime 统一解析与序列化 | 29 | v4.34 | `data_contract_temporal` | meta-rule #25-30 前端侧 |
| F-REVIEW-113 | 跨进程状态同步六步法（前端） | 29 | v4.34 | `data_contract_temporal` | meta-rule #25-30 前端侧 |
| F-REVIEW-114 | 前端错误按 error_code 分支 | 29 | v4.34 | `data_contract_temporal` | meta-rule #25-30 前端侧 |
| F-REVIEW-115 | 业务关键字常量集中管理 | 29 | v4.34 | `data_contract_temporal` | meta-rule #25-30 前端侧 |
| F-REVIEW-116 | RESUME-PRECHECK-FRONTEND 恢复操作前端前置校验 | 30 | v4.35 | `resume_policy_precheck` | meta-rule #31 前端侧 |
| F-REVIEW-117 | REGISTRATION-COMPLETENESS 注册式资源三件套契约 | 31 | v4.36 | `frontend_registration_completeness` | meta-rule #33 前端侧 |
| F-REVIEW-118 | ROOT-CAUSE-MIN-COUNT 修复前根因扫描协议 | 32 | v4.36 | `root_cause_protocol` | meta-rule #34 前端侧 |
| F-REVIEW-119 | CONTRACT-SINGLE-SOURCE 前后端字段契约单一可信源 | 33 | v4.36 | `contract_single_source` | meta-rule #35 前端侧 |
| F-REVIEW-120 | SEDIMENTATION-THRESHOLD 规范立项前置计数 | 34 | v4.37 | `spec_sedimentation` | meta-rule #36 前端侧 |
| F-REVIEW-121 | DEGRADATION-CLEANUP 规范退化清理 | 34 | v4.37 | `spec_degradation` | meta-rule #37 前端侧 |
| F-REVIEW-122 | GLOBAL-AGGREGATE-TASK-FILTER 全局聚合任务级过滤 | 34 | v4.38 | `global_aggregate_task_filter` | meta-rule #38 前端侧 |
| F-REVIEW-123 | LIST-CROSS-DOMAIN-INJECT 列表交叉数据批量注入 | 34 | v4.38 | `list_cross_domain_inject` | meta-rule #39 前端侧 |
| F-REVIEW-124 | MULTI-FIELD-LINKED-SWITCH 多字段联动开关范式 | 34 | v4.38 | `multi_field_linked_switch` | meta-rule #40 前端侧 |
| F-REVIEW-125 | RESUME-PRECHECK-STRUCTURED 状态恢复前置校验结构化响应 | 34 | v4.38 | `resume_precheck_structured` | meta-rule #41 前端侧 |
| F-REVIEW-126 | CONFIG-DRIVEN-THRESHOLD-FALLBACK 配置化阈值兜底范式 | 34 | v4.38 | `config_driven_threshold_fallback` | meta-rule #42 前端侧 |
| F-REVIEW-131 | EVENT-MULTI-EMIT-ALIGN 事件多发布点字段对齐 | 35 | v4.39 | `event_multi_emit_align` | meta-rule #43 前端侧 |
| F-REVIEW-132 | ROUTE-TRIPLE-REGISTRATION 前端路由三重注册同步 | 35 | v4.39 | `cross_layer_contract_test_sync.frontend_route_registration` | meta-rule #44 前端侧 |
| F-REVIEW-133 | QUERY-STRING-RETAIN 外部回链 query string 保留 | 35 | v4.39 | `cross_layer_contract_test_sync.query_string_retain` | meta-rule #45 前端侧 |
| F-REVIEW-134 | TEST-SYNC-RESPONSIBILITY 测试同步责任 | 35 | v4.39 | `cross_layer_contract_test_sync.test_sync_responsibility` | meta-rule #46 前端侧 |
| F-REVIEW-135 | EXTERNAL-DEP-ISOLATION 外部依赖隔离测试可重复性 | 35 | v4.39 | `cross_layer_contract_test_sync.external_dep_isolation` | meta-rule #47 前端侧 |
| F-REVIEW-136 | SCHEDULER-STATUS-SYNC 调度器开关状态前端同步 | 35 | v4.40 | `scheduler_status_sync` | meta-rule #48 前端侧 |
| F-REVIEW-137 | POLLING-INTERVAL-CONFIG 轮询间隔配置化 | 35 | v4.40 | `polling_interval_config` | meta-rule #49 前端侧 |
| F-REVIEW-138 | HOOK-CLEANUP-COMPLETENESS 长生命周期 Hook cleanup 完整性 | 35 | v4.40 | `hook_cleanup_completeness` | meta-rule #50 前端侧 |
| F-REVIEW-139 | CRON-EXPR-FRONTEND-VALIDATE cron 表达式前端校验（experimental） | 35 | v4.40 exp | `cron_expr_frontend_validate` | meta-rule #51 前端侧 |
| F-REVIEW-144 | PARAM-CHAIN-EXEC-FRONTEND 参数链闭环验证 | 35 | v4.42 | `param_chain_exec_frontend` | meta-rule #52 前端侧 |
| F-REVIEW-145 | MODE-VERTICAL-CHAIN-FRONTEND 业务模式纵向链路一致性 | 35 | v4.42 | `mode_vertical_chain_frontend` | meta-rule #53 前端侧 |
| F-REVIEW-146 | MOCK-SYNC-BOUNDARY-FRONTEND mock 同步与边界精确性 | 35 | v4.42 | `mock_sync_boundary_frontend` | meta-rule #55 前端侧 |
| F-REVIEW-147 | FILTER-RESULT-TRANSPARENCY-UI 过滤结果透明化 UI | 35 | v4.42 | `filter_result_transparency_ui` | meta-rule #56 前端侧 |
| F-REVIEW-148 | ASYNC-AWAIT-SYNC-CHECK-FRONTEND async/await 同步性检查 | 35 | v4.43 | `async_await_sync_check_frontend` | meta-rule #57 前端侧 |
| F-REVIEW-149 | HTTP-ERROR-LOCALIZATION HTTP 错误本地化 | 35 | v4.43 | `http_error_localization` | meta-rule #59 前端侧 |
| F-REVIEW-150 | ERROR-CHAIN-TRANSPARENT 错误链透明化 | 35 | v4.43 | `error_chain_transparent` | meta-rule #61 前端侧 |
| F-REVIEW-151 | EXTERNAL-RESOURCE-CLEANUP-FRONTEND 外部资源清理 | 35 | v4.43 | `external_resource_cleanup_frontend` | meta-rule #62 前端侧 |
| F-REVIEW-152 | URL-STATE-SYNC-FALLBACK URL↔状态同步失败回退（experimental） | 35 | v4.44 exp | `url_state_sync_fallback` | meta-rule #64 前端侧 |
| F-REVIEW-153 | SW-CACHE-VERSION-SYNC SW 缓存版本同步（experimental） | 35 | v4.44 exp | `sw_cache_version_sync` | meta-rule #65 前端侧 |
| F-REVIEW-154 | INTERCEPTOR-STATUS-CODE-DISCRIMINATION 全局拦截器状态码区分 | 35 | v4.45 | `interceptor_audit` | meta-rule #66 前端侧 |
| F-REVIEW-HEALING-RESPONSE-HANDLING | 后端自愈响应处理 | 7 | v4.50 | `healing_response_handling` | references/api-contract.md §11 |
| F-REVIEW-COOKIE-HEALTH-DISPLAY | Cookie 健康状态显示一致性 | 7 | v4.50 | `cookie_health_display` | references/state-and-consistency-checks.md 维度7 |
| F-REVIEW-191 | POLLING-TIMEOUT-DISPLAY 前端轮询状态超时展示 | 45 | v4.51.0 | `async_polling_pattern.timeout_display` | references/api-contract.md §12 |
| F-REVIEW-192 | ESLINT-CONFIG-FORMAT-MATCH ESLint 版本与配置格式匹配性 | 12 | v4.51.1 | `eslint_config_compatibility` | SKILL.md 维度12 / SonarQube 工具链 |
| F-REVIEW-193 | PACKAGE-SCRIPTS-COMPLETENESS package.json 脚本完整性 | 12 | v4.51.1 | `package_json_scripts_completeness` | SKILL.md 维度12 / 工程化规范 |
| F-REVIEW-194 | TS-STRICT-CHECK TypeScript 严格编译检查 | 4/11 | v4.51.1 | `typescript_strict_check` | SKILL.md 维度4/11 |
| F-REVIEW-195 | PWA-REGISTER-TYPE PWA Service Worker 配置 | 13 | v4.51.1 | `pwa_register_type_check` | SKILL.md 维度13 |
| F-REVIEW-196 | MOBILE-DETECT-CLEANLINESS 移动端检测代码清洁性 | 10/11 | v4.51.1 | `mobile_detect_cleanliness` | SKILL.md 维度10/11 |
| F-REVIEW-197 | ACTION-BUTTON-TIER-RETAIN 操作项分级保留与横向滚动 fallback | 46 | v4.52.0 | `ui_layout` | SKILL.md 维度46 / step 236+238 |
| F-REVIEW-198 | MULTI-VIEW-MODE-CONSISTENCY 多视图模式一致性 | 46 | v4.52.0 | `ui_layout` | SKILL.md 维度46 / step 237 |
| F-REVIEW-214 | GLOBAL-ERROR-BOUNDARY 全局错误边界强制部署 | 3 | v4.59.0 | `spa_white_screen_resilience.globalErrorBoundary` | meta-rule #95 前端侧 / step 254 |
| F-REVIEW-215 | LAZY-RETRY-WRAPPER 懒加载重试包装器强制 | 10 | v4.59.0 | `spa_white_screen_resilience.lazyRetry` | meta-rule #95 前端侧 / step 255 |
| F-REVIEW-216 | ROUTE-ERROR-BOUNDARY-RESET-KEYS 路由级错误边界与 resetKeys 约束 | 10 | v4.59.0 | `spa_white_screen_resilience.routeErrorBoundary` | meta-rule #95 前端侧 / step 256 |
| F-REVIEW-217 | API-ARRAY-DEFENSE-FALLBACK API 响应数组字段防御性兜底 | 7 | v4.59.0 | `spa_white_screen_resilience.apiArrayDefense` | step 257 |
| F-REVIEW-218 | VITEST-ENV-CHECKLIST Vitest 测试环境搭建检查清单 | 12 | v4.59.0 | `spa_white_screen_resilience.vitestEnvChecklist` | step 259-260 |
| F-REVIEW-219 | ANTD-CHINESE-BUTTON-TEST-REGEX antd 中文按钮测试断言兼容空格 | 12 | v4.59.0 | `spa_white_screen_resilience.antdChineseButtonTestRegex` | step 261 |
| F-REVIEW-220 | CONSTANT-CONFIG-DRIVEN 常量配置化 5 步法 | 11/4 | v4.61.0 | `refactoring_safety_checks.constant_config_driven` | references/refactoring-safety-checks.md §A1 |
| F-REVIEW-221 | REACT-HOOKS-SCOPE-CONTRACT React Hooks 作用域契约 | 3/10 | v4.61.0 | `refactoring_safety_checks.react_hooks_scope_contract` | references/refactoring-safety-checks.md §A2 |
| F-REVIEW-222 | IMPORT-NAME-CHANGE-CHECKLIST 导入名称变更 checklist | 11/2 | v4.61.0 | `refactoring_safety_checks.import_name_change_checklist` | references/refactoring-safety-checks.md §A3 |
| F-REVIEW-223 | LONG-TASK-BUILD-LOG-REDIRECT 长任务前端构建日志输出 | 12 | v4.61.0 | `refactoring_safety_checks.long_task_build_log_redirect` | references/refactoring-safety-checks.md §B1 |
| F-REVIEW-224 | SYSTEM-RESOURCE-OVERLOAD-TOLERANCE 系统资源过载容错 | 12/16 | v4.61.0 | `refactoring_safety_checks.system_resource_overload_tolerance` | references/refactoring-safety-checks.md §B2 |
| F-REVIEW-225 | CROSS-FILE-CONTRACT-SYNC 跨文件引用同步校验 | 11/6 | v4.61.0 | `refactoring_safety_checks.cross_file_contract_sync` | references/refactoring-safety-checks.md §D1 |
| F-REVIEW-226 | STATE-PERSISTENCE-UNIFIED-ENTRY 状态持久化统一入口 | 6/10 | v4.61.0 | `refactoring_safety_checks.state_persistence_unified_entry` | references/refactoring-safety-checks.md §D2 |
| F-REVIEW-227 | MARKDOWN-PREPROCESS-CODEBLOCK-PROTECT Markdown 预处理代码块保护（替换前必须分割代码块和行内代码，仅对非代码段执行替换） | 40 | v4.62.0 | `frontend_resilience.markdown_preprocess_codeblock_protect` | references/frontend-resilience-checks.md §F-REVIEW-227 |
| F-REVIEW-228 | REACT-RENDER-SIDEFFECT-BAN React 组件 render 阶段副作用禁令（render 阶段禁止写 ref，必须在 useEffect 中） | 40 | v4.62.0 | `frontend_resilience.react_render_sideffect_ban` | references/frontend-resilience-checks.md §F-REVIEW-228 |
| F-REVIEW-229 | SSE-EVENT-RUNTIME-TYPE-VALIDATION SSE 事件运行时类型校验（禁止 as 断言，必须用 zod safeParse 校验） | 40 | v4.62.0 | `frontend_resilience.sse_event_runtime_type_validation` | references/frontend-resilience-checks.md §F-REVIEW-229 |
| F-REVIEW-230 | TIMER-CLEANUP-RACE-GUARD 定时器清理与竞态防护（卸载时清理 + 重设前清除旧定时器） | 40 | v4.62.0 | `frontend_resilience.timer_cleanup_race_guard` | references/frontend-resilience-checks.md §F-REVIEW-230 |
| F-REVIEW-231 | INTERACTIVE-ELEMENT-A11Y 交互元素可访问性（非原生交互元素三件套：tabIndex/role/onKeyDown） | 40 | v4.62.0 | `frontend_resilience.interactive_element_a11y` | references/frontend-resilience-checks.md §F-REVIEW-231 |
| F-REVIEW-232 | SSE-ONCOMPLETE-DATA-INTEGRITY 流式响应 onComplete 数据完整性（持久化判断基于任一产出非空） | 40 | v4.62.0 | `frontend_resilience.sse_oncomplete_data_integrity` | references/frontend-resilience-checks.md §F-REVIEW-232 |
| F-REVIEW-233 | ASYNC-HANDLER-THREE-BRANCH 前端 async handler 三分支完整性（success/else/catch 都必须显示具体错误 + 调用 loadXxx 刷新状态） | 47 | v4.63.0 | `idempotent_resource_creation_frontend.async_handler_three_branch` | references/idempotent-resource-creation-checks.md §F-REVIEW-233 |
| F-REVIEW-234 | API-RETURN-TYPE-CONTRACT API 函数返回类型契约（资源创建类 API 必须返回 OperationResult 含 already_active 字段） | 47 | v4.63.0 | `idempotent_resource_creation_frontend.api_return_type_contract` | references/idempotent-resource-creation-checks.md §F-REVIEW-234 |
| F-REVIEW-235 | UI-BACKEND-STATE-CONSISTENCY UI 与后端状态一致性强制刷新（写操作三分支必须刷新 + 业务状态必须来自 API） | 47 | v4.63.0 | `idempotent_resource_creation_frontend.ui_backend_state_consistency` | references/idempotent-resource-creation-checks.md §F-REVIEW-235 |
| F-REVIEW-244 | FRONTEND-TYPE-CONTRACT-REVERSE-VALIDATION 前端 types.ts 反向校验（types.ts 类型声明作为后端返回结构的反向校验源，字段名/字段类型/字段可选性必须与后端实际响应 1:1 对齐；后端无 Pydantic ResponseModel 时 types.ts 升级为权威源） | 19 | v4.67.0 experimental | `type_annotation_contract` | meta-rule #110 前端侧 / step 273 / B-REVIEW-330 配套 |
| F-REVIEW-245 | HEALTH-DISPLAY-CONSISTENCY 健康状态展示与后端实际状态一致性 | 状态与一致性 | v4.68.0 experimental | `health_display_consistency` | references/state-and-consistency-checks.md §F-REVIEW-245 / meta-rule #112 前端侧 / step 275 配套 |
| F-REVIEW-246 | SOURCE-FILE-ENCODING-INTEGRITY 源码文件编码完整性（前端源码本体中文→字面量? / GBK 误读乱码，与运行时 ENC 规范正交互补） | 编码规范 | v4.70.0 | `source_file_encoding_integrity` | references/source-file-encoding-integrity.md §F-REVIEW-246 / step 280 配套 / B-REVIEW-337 配套 |

## 统计

- 总计：139 项检查点（v4.70.0 新增 1 项源码文件编码完整性；v4.68.0 experimental 新增 1 项健康状态展示与后端实际状态一致性；v4.67.0 experimental 新增 1 项类型注解契约对齐前端反向校验；v4.63.0 新增 3 项资源创建幂等性检查点）
- 按维度分布：维度 3（7项）、维度 4（4项）、维度 5（3项）、维度 6（3项）、维度 7（14项）、维度 10（10项）、维度 11（13项）、维度 12（6项）、维度 13（2项）、维度 15（2项）、维度 16（1项）、维度 18（2项）、维度 19（9项）、维度 20（1项）、维度 25（3项）、维度 27（3项）、维度 28（2项）、维度 29（10项）、维度 30（1项）、维度 31（1项）、维度 32（1项）、维度 33（1项）、维度 34（7项）、维度 35（18项）、维度 40（6项）、维度 45（1项）、维度 46（2项）、维度 47（3项）
- experimental：F-REVIEW-139、F-REVIEW-152、F-REVIEW-153、F-REVIEW-197、F-REVIEW-198、F-REVIEW-244
- v4.61.0 新增：F-REVIEW-220~226（重构安全性检查，配套 references/refactoring-safety-checks.md）
- v4.62.0 新增：F-REVIEW-227~232（前端韧性 Review，配套 references/frontend-resilience-checks.md）
- v4.63.0 新增：F-REVIEW-233~235（资源创建幂等性与前端状态闭环，配套 references/idempotent-resource-creation-checks.md）
- v4.67.0 experimental 新增：F-REVIEW-244（前端 types.ts 反向校验，配套 meta-rule #110 + step 273 + B-REVIEW-330）
- v4.70.0 新增：F-REVIEW-246（源码文件编码完整性，配套 xianyu-hunter-dev step 280 + 后端 B-REVIEW-337 + 测试模式 AK；覆盖源码本体中文→字面量? / GBK 误读乱码，与运行时 ENC 规范正交互补）

## 新增检查点（v4.72.0 · 2026-08-13 登录/Cookie/测试专项）

| ID | 名称 | 维度 | 版本 | 配置节点 | 规范源 |
|----|------|------|------|----------|--------|
| F-REVIEW-247 | PROXY-REDIRECT-SAFETY 重定向/中间件不得破坏反代（Funnel 回环安全） | 48 | v4.72.0 | `proxy_redirect_safety` | meta-rule #120 / step 登录专项 |
