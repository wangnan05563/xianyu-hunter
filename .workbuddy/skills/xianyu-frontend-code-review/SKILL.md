---
name: "xianyu-frontend-code-review"
description: "对闲鱼猎人项目前端代码（frontend/src/ �?React/TypeScript/Ant Design/Zustand 文件）进行全面评审与逻辑审查，覆盖类型安全、业务逻辑、Zustand 状态管理、API 契约、Hooks 设计、路由懒加载、AntD 主题、性能、可访问性、可测试性、认证规范、SonarQube 合规、注册式资源三件套契约等 36 个维度。当用户要求'审查/检�?走查/把关/review/评估/看看对不�?规范不规�?前端 React/TS 代码�?.tsx/.ts 文件修改'�?迭代发布前前端走�?，或提到'前端评审/frontend review/React 代码审查/TypeScript 评审/组件代码走查'时调用。仅审查前端 .tsx/.ts 文件；纯后端 .py 文件审查请改�?xianyu-backend-code-review�?
whenToUse: "需要审查闲鱼猎人前端代码（frontend/src/ �?.tsx/.ts 文件，含 pages/页面、components/组件、hooks/、stores/Zustand、api/、routes/路由、App.tsx、main.tsx）是否符合项目规�?
triggers: "前端代码 走查/审查/审核/把关/review/检�?评估 | 前端评审/frontend review/React 代码审查/TypeScript 评审/组件代码走查/AntD 评审/Zustand 评审 | .tsx/.ts 文件 修改/变更/迭代 走查 | 迭代发布�?前端 代码 走查 | 这段前端代码/组件/Hook 写得对不�?规范不规�?| 闲鱼 前端 代码 review | 页面/组件/Hook/Store/路由 代码 审查"
version: "4.69.0"
updated: "2026-08-11"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# 闲鱼猎人前端代码审查

对闲鱼猎人项目前端代码（`frontend/src/` 下的 React/TypeScript/Ant Design/Zustand 文件）进行全面的代码评审及逻辑审查。评审涵�?*36 个维�?*，包括类型安全、业务逻辑、Zustand 状态管理、API 契约、Hooks 设计、路由与懒加载、AntD 主题、性能、可访问性、可测试性、认证规范、SonarQube 合规、模型能力集中展示、端到端失败原因链前端侧同步原则、跨边界访问契约前端侧、业务关键字常量集中管理与字段名大小写敏感、多用户认证上下文隔离、数据契约与时序（meta-rules #25-30 落地）、状态恢复前置校验前端侧（meta-rules #31 落地）、注册式资源三件套契约（meta-rules #33 落地）、修复前全链路根因扫描协议（meta-rules #34 落地）、前后端字段契约单一可信源（meta-rules #35 落地）、规范治理（meta-rules #36-37 落地）、列表聚合与状态联动（meta-rules #38-42 落地）、跨层契约与测试同步（meta-rules #43-47 落地）、调度器运行时治理前端侧（meta-rules #48-51 落地）�?
## 版本演进索引

> 各版本的完整复盘详情（Sequential Thinking 复盘法、根因分析、检查点详情、对应后端规范）已外部化�?[references/version-changelog.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/version-changelog.md)。本表仅作索引，需查阅历史决策与根因时再读取该文件�?
| 版本 | 新增检查点 | 维度 | 扫描�?| 核心变化 |
|---|---|---|---|---|
| v2.0.0 | �?| 1,3,4,5,6,7,8,9,10,12,13,14,15,17,18 | 0�?2 | 知识点整�?|
| v3.0.0 | �?| 12 | 14�?6 | SonarQube 8�?6 规则 |
| v4.0.0 | �?| 3,10,11,17,18 | 26�?6 | Tab重构/实时搜索/通用规范 |
| v4.1.0 | F-REVIEW-SSE-ERROR-HANDLING | 15 | 36�?8 | SSE错误码分�?|
| v4.2.0 | F-REVIEW-UI-STATE-INDEPENDENCE | 3 | 38�?9 | UI状态不联动路由 |
| v4.3.0 | 维度 19（跨组件状态同步与死代码检测） | 19 | 39�?3 | 反爬复盘 |
| v4.4.0 | F-REVIEW-CONFIG-DRIVEN-TOGGLE | 11 | 43�?4 | 配置驱动高风�?|
| v4.5.0 | F-REVIEW-ERROR-SEMANTICS / F-REVIEW-CONFIG-LINKAGE | 11,7 | 44�?6 | 错误语义/配置链路 |
| v4.6.0 | F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND | 6 | 46�?7 | 多入口统一updateState |
| v4.7.0 | F-REVIEW-ASYNC-FEEDBACK / DATA-FLOW-TRACE / FILTER-SCENARIO / REUSE-PATTERN | 10,11,7,18 | 47�?1 | 异步三�?数据追踪/场景标志/复用 |
| v4.8.0 | F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE | 5 | 51�?2 | 暗色token动态覆�?|
| v4.9.0 | F-REVIEW-FREQ-STATS-POLLING | 10 | 52�?3 | 累计统计定时刷新 |
| v4.10.0 | F-REVIEW-FILTER-VISIBILITY | 7 | 53�?4 | filter_summary三�?|
| v4.11.0 | F-REVIEW-STATE-ENUM-ALIGN / STATE-MACHINE-UI / DUAL-LINK-CACHE-CONSISTENCY | 4,3,6 | 54�?7 | 状态机/双链�?缓存 |
| v4.12.0 | F-REVIEW-ASYNC-CONFIG-LOAD / INPUT-NUMBER-BOUNDS / NULL-SEMANTICS / XSS-ESCAPE / BATCH-OPERATION | 10,4,11,7 | 57�?2 | 配置/输入/null/XSS/批量 |
| v4.13.0 | F-REVIEW-ERROR-CONTRACT-TIMEOUT / RETRY-BACKOFF | 7,7 | 62�?4 | 错误契约/退避重�?|
| v4.14.0 | F-REVIEW-FILTER-BACKEND-ALIGN / FILTER-PAGINATION-ADAPT / FILTER-EMPTY-STATE | 7,10,3 | 64�?7 | 过滤/分页/空状�?|
| v4.15.0 | F-REVIEW-DEBUG-CODE-CLEANUP | 11 | 67�?8 | DEBUG代码移除 |
| v4.16.0 | F-REVIEW-STATE-FUNCTIONAL-ALIGN / FIELD-CONTRACT-ALIGN / ASYNC-RACE-CONDITION / ERROR-HANDLER-EXTRACT | 3,11,10,11 | 68�?2 | Cookie状�?api_ai_deep复盘 |
| v4.19.0 | F-REVIEW-SCHEDULER-STATUS-DISPLAY | 18 | 72�?3 | 关于页调度器状�?|
| v4.20.0 | F-REVIEW-VERSION-SOURCE-ALIGN | 7 | 73�?4 | 版本源语义对�?|
| v4.22.0 | F-REVIEW-PWA-CACHE-VERIFY | 13 | 74�?5 | PWA三层缓存 |
| v4.23.0 | F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION | 11 | 75�?6 | 模型能力集中/降级可视�?|
| v4.24.0 | F-REVIEW-UI-PREFERENCE-PERSISTENCE | 10 | 76�?7 | 偏好用usePersistentState |
| v4.25.0 | 无新增（仅同步原则） | �?| 77 | DB迁移容错(同步原则) |
| v4.26.0 | F-REVIEW-THREE-STATE-NULL-SEMANTICS / ERROR-HANDLING-CONSISTENCY / DEFAULT-OPERATOR-CONSISTENCY | 7,20,4 | 77�?0 | API三�?错误处理/默认�?|
| v4.27.0 | F-REVIEW-ERROR-CODE-BRANCH / PRECHECK-API-DELEGATION / MOCK-FIELD-SET-SYNC | 25 | 80�?3 | 端到端失败链(维度25) |
| v4.28.0 | F-REVIEW-WF-ERROR-HANDLING / WF-BATCH-CIRCUIT-BREAKER / WF-RESOURCE-LIFECYCLE / WF-STATE-SYNC | 19,6,10,11 | 83�?7 | 工作流硬约束(#21-24) |
| v4.30.0 | F-REVIEW-DATETIME-RENDER-CONTRACT / PRIVATE-HOOK-ENCAPSULATION / NAMING-CONSISTENCY-FRONTEND | 26 | 87�?0 | 跨边界契�?维度26) |
| v4.31.0 | F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION / EVENT-TYPE-EXACT-MATCH / FIELD-NAME-CASE-SENSITIVE | 27 | 90�?3 | 关键字集�?事件精确/大小写敏�?维度27) |
| v4.32.0 | F-REVIEW-MULTI-USER-CONTEXT-ISOLATION / AUTH-TOKEN-COOKIE-HANDLING | 28 | 93�?5 | 多用户隔�?维度28) |
| v4.33.0 | F-REVIEW-EFFECT-MINIMIZE / STATE-ATOMICITY / SSE-CONN-MGMT / ASYNC-RACE-GUARD / THEME-DYNAMIC-ADAPT / EMBEDDED-LAYOUT-HEIGHT / COMPONENT-REGISTRY / FILTER-TRANSPARENCY / DATA-SOURCE-VERIFY / STATS-RANGE-CALIBRATE / UI-SEMANTICS-SPLIT / PERSIST-BUSINESS-SWITCH / ERROR-MESSAGE-PASS / API-CONTRACT-CONSISTENCY | 3,15,5,10,7 | 95�?09 | 全量复盘+14项F-REVIEW/4阶段流水�?|
| v4.34.0 | F-REVIEW-110~115（meta-rules #25-30 落地�?| 29 | 109�?15 | 数据契约时序(维度29) |
| v4.35.0 | F-REVIEW-116 RESUME-PRECHECK-FRONTEND | 30 | 115�?16 | 状态恢复前置校�?维度30) |
| v4.36.0 | F-REVIEW-117 REGISTRATION-COMPLETENESS / F-REVIEW-118 ROOT-CAUSE-MIN-COUNT / F-REVIEW-119 CONTRACT-SINGLE-SOURCE | 31,32,33 | 116�?19 | 注册三件�?根因扫描/契约单一�?维度31-33) |
| v4.37.0 | F-REVIEW-120 SEDIMENTATION-THRESHOLD / F-REVIEW-121 DEGRADATION-CLEANUP | 34 | 119�?21 | 沉淀门槛/退化机�?维度34) |
| v4.38.0 | F-REVIEW-122 GLOBAL-AGGREGATE-TASK-FILTER / F-REVIEW-123 LIST-CROSS-DOMAIN-INJECT / F-REVIEW-124 MULTI-FIELD-LINKED-SWITCH / F-REVIEW-125 RESUME-PRECHECK-STRUCTURED / F-REVIEW-126 CONFIG-DRIVEN-THRESHOLD-FALLBACK | 34 | 121�?26 | 列表聚合/状态联�?维度34扩展) |
| v4.39.0 | F-REVIEW-131 EVENT-MULTI-EMIT-ALIGN / F-REVIEW-132 ROUTE-TRIPLE-REGISTRATION / F-REVIEW-133 QUERY-STRING-RETAIN / F-REVIEW-134 TEST-SYNC-RESPONSIBILITY / F-REVIEW-135 EXTERNAL-DEP-ISOLATION | 35 | 126�?31 | 跨层契约/测试同步(维度35) |
| v4.42.0 | F-REVIEW-144 PARAM-CHAIN-EXEC-FRONTEND / F-REVIEW-145 MODE-VERTICAL-CHAIN-FRONTEND / F-REVIEW-146 MOCK-SYNC-BOUNDARY-FRONTEND / F-REVIEW-147 FILTER-RESULT-TRANSPARENCY-UI | 7,4,12,7 | 131�?35 | 参数�?纵向链路/mock边界/过滤透明�?|
| v4.43.0 | F-REVIEW-148 ASYNC-AWAIT-SYNC-CHECK-FRONTEND / F-REVIEW-149 HTTP-ERROR-LOCALIZATION / F-REVIEW-150 ERROR-CHAIN-TRANSPARENT / F-REVIEW-151 EXTERNAL-RESOURCE-CLEANUP-FRONTEND | 10,7,7,10 | 135�?39 | async同步/HTTP本地�?错误�?资源清理 |
| v4.44.0 experimental | F-REVIEW-152 URL-STATE-SYNC-FALLBACK / F-REVIEW-153 SW-CACHE-VERSION-SYNC | 3,13 | 139�?41 experimental | URL同步回退/SW缓存版本(experimental) |
| v4.45.0 | F-REVIEW-154 INTERCEPTOR-STATUS-CODE-DISCRIMINATION | 7 | 141�?42 | 全局拦截器状态码区分(认证401 vs 业务401) |
| v4.47.0 | F-REVIEW-167 PRESET-APIKEY-INDIVIDUAL / F-REVIEW-168 CONFIG-SAVE-INDEPENDENCE / F-REVIEW-169 BACKEND-RETURN-ON-UPDATE | 10,11,10 | 142->145 | Preset API Key per preset / independent config save / update echo (dims 10-11) |
| v4.48.0 | F-REVIEW-173 MODEL-NAME-CASE-ACCURACY / F-REVIEW-174 MODEL-NAME-SHARED-CHECK-LOWER / F-REVIEW-175 CONFIG-PERSIST-ON-CHANGE / F-REVIEW-176 CONFIG-REFLECT-ORIGINAL / F-REVIEW-177 MASKED-KEY-PUT-SKIP | 11,11,10,10,10 | 145->150 | Model name case accuracy / shared check lower / persist on change / reflect original / masked key skip (dims 10-11) |
| v4.49.0 | F-REVIEW-182 BACKEND-LOGIC-VISIBILITY-SYNC / F-REVIEW-183 RULE-DOCUMENTATION-USABLE-EXAMPLES / F-REVIEW-184 RULE-CONFIG-SOURCE-ANNOTATION / F-REVIEW-185 STATIC-BUILD-ARTIFACT-NOT-GIT / F-REVIEW-186 BUILD-VERIFICATION-BEFORE-SUBMIT / F-REVIEW-187 PWA-CACHE-REFRESH-HINT | 10,10,10,10,10,10 | 150->156 | Backend logic UI sync / concrete examples / config source annotation / static artifact management / build verification / PWA cache hint (dims 10) |
| v4.50.0 | F-REVIEW-HEALING-RESPONSE-HANDLING / F-REVIEW-COOKIE-HEALTH-DISPLAY | 7,7 | 104->106 | Backend cookie healing response / cookie health display consistency (dims 7) |
| v4.51.0 | F-REVIEW-191 POLLING-TIMEOUT-DISPLAY | 45 | 106->107 | Polling status timeout display (dim 45) |
| v4.51.1 | F-REVIEW-192 ESLINT-CONFIG-FORMAT-MATCH / F-REVIEW-193 PACKAGE-SCRIPTS-COMPLETENESS / F-REVIEW-194 TS-STRICT-CHECK / F-REVIEW-195 PWA-REGISTER-TYPE / F-REVIEW-196 MOBILE-DETECT-CLEANLINESS | 12,12,4,11,13,10 | 107->112 | ESLint配置格式/package脚本完整�?TS严格检�?PWA SW类型/移动端检测清�?|
| v4.52.0 | F-REVIEW-197 SNAPSHOT-FILTER-DISPLAY-SEPARATION / F-REVIEW-198 MULTI-USER-CONTEXT-PROPAGATION | 7,28 | 112->114 | ǰ�˿��չ���չʾ���� / ���û������Ĵ��ݣ�meta-rules #83 ��أ�2026-07-18 ������� Bug ���̣� |
| v4.53.0 | F-REVIEW-199 COMPONENT-REUSE-STATE-RESET | 3 | 114->115 | �������״̬ͬ�����ã�meta-rule #85 ��أ�2026-07-22 ThumbCell errored ״̬���� Bug ���̣� |
| v4.57.0 | F-REVIEW-206 FALLBACK-PRESERVE-KEY-FRONTEND | 11 | 115->116 | ���˹��������ǰ����飨meta-rule #90 ��أ�2026-07-22 price_range ע�� Bug ���̣� |
| v4.59.0 | F-REVIEW-214 GLOBAL-ERROR-BOUNDARY / F-REVIEW-215 LAZY-RETRY-WRAPPER / F-REVIEW-216 ROUTE-ERROR-BOUNDARY-RESET-KEYS / F-REVIEW-217 API-ARRAY-DEFENSE-FALLBACK / F-REVIEW-218 VITEST-ENV-CHECKLIST / F-REVIEW-219 ANTD-CHINESE-BUTTON-TEST-REGEX | 3,10,10,7,12,12 | 119->125 | SPA��Ⱦ�ݴ�������(ȫ��ErrorBoundary/lazyRetry/·�ɼ�resetKeys) / API��������Զ��� / Vitest��������嵥 / antd���İ�ť��������meta-rule #95 ��أ�2026-07-22 �����޸����̣� |
| v4.60.0 | F-REVIEW-UI-PREVIEW-GATE / F-REVIEW-STATE-SELECTION / F-REVIEW-DEFENSIVE-RENDER / F-REVIEW-COMPONENT-REUSE-RESET | 3,10,7,3 | 125->129 | UI变更门控/状态选型/防御性渲染/组件复用重置（2026-07-23 12项历史问题复盘提炼） |
| v4.70.0 | F-REVIEW-227 BUILD-ARTIFACT-ICON-BRAND-CONSISTENCY / F-REVIEW-228 DEPLOY-CACHE-INVALIDATION | 2 | 227->228 | 构建产物图标品牌一致性 / 部署缓存失效一致性（meta-rule #112，2026-08 构建产物图标 + 部署缓存复盘） |
| v4.71.0 | F-REVIEW-236 SOURCE-FILE-PROTECTION / F-REVIEW-237 PWA-SUBPATH-NAVFALLBACK / F-REVIEW-238 DESIGN-TOKENS-NO-HARDCODE / F-REVIEW-239 SPA-BASENAME-CONSISTENCY | 42,43,44,45 | 42->45 | 前端部署韧性 4 维度（meta-rules #116-#119，2026-08-13 复盘 retrospective-2026-08-13）：清理脚本禁删 tracked 源 / PWA 子路径导航回退绝对化 / 设计令牌集中化禁硬编码色 / SPA 基路径三处对齐；全部参数经 config.yaml 节点管理，禁硬编码 |
| v4.72.0 | F-REVIEW-247 PROXY-REDIRECT-SAFETY | 1 | 247->247 | 重定向/中间件不得破坏反代（Funnel 回环安全，meta-rule #120，retrospective-2026-08-13-login-cookie）：根路径白板靠统一入口指向子路径，禁止加重定向（避免反代前缀剥离无限回环）；参数经 config.yaml#proxy_redirect_safety 管理，无硬编码 |
| v4.61.0 | F-REVIEW-220~226 重构安全性检查（7项） | 11/4,3/10,11/2,12,12/16,11/6,6/10 | 125->132 | 常量配置化5步法/Hooks作用域契约/导入名变更checklist/长任务日志输出/资源过载容错/跨文件契约同步/状态持久化统一入口（复盘规范集A/B/D三类前端落地） |
| v4.58.0 | F-REVIEW-211 SSE-PRECHECK-HTTP-ERROR-CODE / F-REVIEW-212 LIST-DERIVED-USEMEMO / F-REVIEW-213 SSE-FETCH-READABLESTREAM | 15,10,10 | 116->119 | SSEǰ�ü��HTTP������/useMemo/fetch+ReadableStream��meta-rule #93 ��أ�2026-07-22 �����Ż�8�������̣� |

## 配置驱动

**核心原则**：所有评审规则、硬约束、项目规范均通过 `config.yaml` 管理，技能本身不含任何业务参数或硬编码值。新增规则只需修改配置文件，无需改动技能本身�?
配置文件位置：`.trae/skills/xianyu-frontend-code-review/config.yaml`

首次使用时，从同目录�?`config.example.yaml` 复制并按项目实际情况修改。配置项分为 9 大类�?
| 配置�?| 职责 | 关键参数 |
|--------|------|----------|
| `scope` | 评审范围 | include_paths, exclude_paths, file_extensions, max_files_per_run |
| `priority` | 优先级排�?| severity_order, category_order, report_threshold |
| `hard_constraints` | 硬约束规�?| rules（可扩展列表，每条含 name/pattern/message/severity/auto_fix�?|
| `checklist` | 评审检查清�?| 19 大类开�?|
| `abstraction_thresholds` | 抽象建议阈�?| inline_style_repeat, text_literal_repeat, function_max_lines �?|
| `report` | 报告生成 | output_dir, format, include_good_practices, max_suggestions |
| `verify` | 验证配置 | run_tests_after_review, test_command, fail_on_critical |
| `project_conventions` | 项目专属规范参�?| ui_library, visual_style, auth_requirements, test_framework �?|
| `meta_rules_38_42_frontend` | 列表聚合与状态联动（meta-rules #38-42 前端侧，🆕v4.38�?| global_aggregate_filter, cross_domain_inject, linked_switch_priority, precheck_structured_fields, config_fallback_defaults |
| `cross_layer_contract_test_sync` | 跨层契约与测试同步（meta-rules #43-47 前端侧，🆕v4.39�?| event_multi_emit_alignment, frontend_route_registration, external_callback_query_retention, test_synchronization, external_dependency_isolation |
| `scheduler_runtime_governance_frontend` | 调度器运行时治理前端侧（meta-rules #48-51 前端侧，🆕v4.40�?| scheduler_status_sync, polling_interval_config, hook_cleanup_completeness, cron_expr_frontend_validate |
| `ui_preview_gate` | UI视觉变更预确认门控（🆕v4.60） | enabled, changeLineThreshold, previewStrategy, triggerPatterns, exemptPatterns |
| `state_selection` | React状态选型检查（🆕v4.60） | enabled, preferenceKeywords, persistenceHookName, keyNamingPattern |
| `spa_render_resilience` | SPA防御性渲染检查（🆕v4.60） | enabled, requireGlobalErrorBoundary, requireLazyRetry, requireDefensiveAccess, require401Debounce, checkItems |
| `component_reuse_state_reset` | 组件复用状态重置检查（🆕v4.60） | enabled, reuseContexts, resetValueDefaults |
| `refactoring_safety_checks` | 重构安全性检查（🆕v4.61） | constant_config_driven, react_hooks_scope_contract, import_name_change_checklist, long_task_build_log_redirect, system_resource_overload_tolerance, cross_file_contract_sync, state_persistence_unified_entry |
| `fallback_preserve_key` | ���˹�������������meta-rule #90 ǰ�˲࣬??v4.57�� | enabled, required_keys, entity_types, fallback_sources |

## 审查模式

| 模式 | 扫描范围 | 触发 |
|------|---------|------|
| 快速自检 | 仅阻塞级 | `pwsh .trae/skills/xianyu-frontend-code-review/scripts/auto-scan.ps1` |
| 增量审查 | `git diff --name-only` 变更文件 | 粘贴变更文件列表 |
| 指定文件审查 | 用户明确列出的文�?| 用户指定路径 |
| 片段评审 | 用户粘贴代码片段 | 无文件路径时仅输出建�?|
| 全量审查 | `frontend/src/**/*.{tsx,ts,js}` | 默认 |

---

> **v4.36.0 注册式资源三件套契约 + 修复协议 + 前后端字段契约复盘（meta-rules #33-35 前端落地�?*：基�?通知中心菜单点击无反�?等历史问题复盘（用户报告"通知中心"菜单点击�?URL 不变、内容不变；根因�?`config/menu_registry.yaml` 已注�?`path=/notifications`，但 `frontend/src/App.tsx` 无对�?`<Route>`、`pages/Notifications/index.tsx` 不存在、`api/notifications.ts` 不存在，路由 fallback `<Route path="*" element={<Navigate to="/" replace />} />` 静默重定向到首页），使用 Sequential Thinking 4 维度复盘法——成功步�?不确定性与失败�?可抽象的固定流程与判断逻辑/适用场景与不适用场景，新�?3 项维度（31-33�? 3 �?F-REVIEW 检查点�?*F-REVIEW-117 REGISTRATION-COMPLETENESS 注册式资源三件套契约**（meta-rule #33 落地—�? 层契约：L1 menu_registry/L2 router/L3 page/L4 api_wrapper/L5 backend_endpoint 缺一即视�?CRITICAL，自动化校验 `python scripts/check_registration.py` 退出码 0 才算通过，参数在 `frontend_registration_completeness` 节点管理）�?*F-REVIEW-118 ROOT-CAUSE-MIN-COUNT 修复前根因扫描协�?*（meta-rule #34 落地——修复非平凡 bug 前必须先�?�? 个根因覆盖用户层/接口�?数据�?配置�?历史层；PR 描述必须�?�? 根因列表"段；git diff 涉及 �? 个无关文件视为违反最小修改原则；新增逻辑�?unit test 视为 WARNING；参数在 `root_cause_protocol` 节点管理）�?*F-REVIEW-119 CONTRACT-SINGLE-SOURCE 前后端字段契约单一可信�?*（meta-rule #35 落地——后�?Pydantic/DB Row 字段 = 权威源；前端 `types.ts` 必须显式标注"派生来源"+ "Pydantic 字段"+ "变更日期"+ "约束" 4 段注释；snake_case 严格透传禁止�?camelCase；后�?Pydantic 字段 `xxx_yyy` + 前端 types.ts 字段 `xxxYyy` = CRITICAL 命名漂移；参数在 `contract_single_source` 节点管理）。所有新检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.32.0 �?meta-rules #33-35 �?step 181-183。后端对应规范为 `xianyu-backend-code-review` v4.31.0 �?B-REVIEW-159/160/161�?
---

> **v4.38.0 列表聚合与状态联动复盘（meta-rules #38-42 前端落地�?*：基于本轮对话解决的"捡漏价格参�?等列表聚合类问题复盘（全局聚合未按任务�?price_range/market_ratio 过滤导致越界数据 / 列表交叉数据 N+1 查询 / 多字段联动开关逻辑错误 / 状态恢�?precheck 抛异�?/ 配置缺失即崩溃），使�?Sequential Thinking 4 维度复盘法——成功步�?不确定性与失败�?可抽象的固定流程与判断逻辑/适用场景与不适用场景，在维度 34（规范治理）下追�?5 �?F-REVIEW 检查点（F-REVIEW-122~126），自动化扫描从 121 项扩展到 126 项。新增检查点�?*F-REVIEW-122 GLOBAL-AGGREGATE-TASK-FILTER 全局聚合任务级过�?*（meta-rule #38 前端侧——前端聚合统计（�?Dashboard 价格区间分布、市场价比率分布）必须按当前任务�?`price_range`/`market_ratio` 配置过滤，禁止展示越界数据；前端展示聚合数据前必须确认后端已调用 `_filter_by_per_task_range` 过滤；参数在 `meta_rules_38_42_frontend.global_aggregate_filter` 节点管理）�?*F-REVIEW-123 LIST-CROSS-DOMAIN-INJECT 列表交叉数据批量注入**（meta-rule #39 前端侧——列表渲染交叉数据（如商品列表注入最新评估价/订单状态）必须用批�?API 一次性获取，禁止循环中逐项 fetch；前端必须支持批量响应的 `id �?value` 映射结构；参数在 `meta_rules_38_42_frontend.cross_domain_inject` 节点管理）�?*F-REVIEW-124 MULTI-FIELD-LINKED-SWITCH 多字段联动开关范�?*（meta-rule #40 前端侧——多字段联动开关（�?mode + bargain_only）必须遵�?主开关决定副开关可见�?范式，副开关值在主开关关闭时必须清零而非保留；前�?UI 必须根据主开关状态动态显�?隐藏副开关；参数�?`meta_rules_38_42_frontend.linked_switch_priority` 节点管理）�?*F-REVIEW-125 RESUME-PRECHECK-STRUCTURED 状态恢复前置校验结构化响应**（meta-rule #41 前端侧——前端调�?resume/start 接口必须处理结构�?precheck 响应（`{resume_blocked, reason_code, user_hint, retry_after, task_registered}`），禁止假设接口直接成功；precheck 失败时必须展�?`user_hint` �?`retry_after` 倒计时；参数�?`meta_rules_38_42_frontend.precheck_structured_fields` 节点管理）�?*F-REVIEW-126 CONFIG-DRIVEN-THRESHOLD-FALLBACK 配置化阈值兜底范�?*（meta-rule #42 前端侧——前端使用的阈值参数（�?p10 百分位、market_ratio_threshold、price_range_tolerance）必须从后端配置 API 获取，禁止前端硬编码；配�?API 失败时必须用兜底默认值并 `console.warn`，禁止抛异常导致页面崩溃；参数在 `meta_rules_38_42_frontend.config_fallback_defaults` 节点管理）。所有新检查点强调配置驱动（参数在 `config.yaml` �?`meta_rules_38_42_frontend` 节点管理，不硬编码业务参数）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.34.0 �?meta-rules #38-42 �?step 184-188。后端对应规范为 `xianyu-backend-code-review` v4.34.0 �?B-REVIEW-164~168�?
---

## 审查规则�?9 项维度）

### 1. 目录结构 🆕v2.0

- 【强制】所有代码在 `frontend/src/` 下开�?- 【强制】业务页面位�?`frontend/src/pages/<业务�?/`（如 `Dashboard/`、`Tasks/`、`Items/`、`Orders/`、`Evaluations/`、`Chatbot/`、`Config/`、`Logs/`、`Timeline/`、`Maintenance/`、`About/`、`Onboarding/`、`Login/`�?- 【强制】公共组件位�?`frontend/src/components/`（如 `SheetWorkspace/`、`layout/`、`charts/`、`editors/`、`icons/`、`ErrorBoundary.tsx`�?- 【强制】API 模块位于 `frontend/src/api/`，新�?API 归入子模块而非扩展 `index.ts`
- 【强制】自定义 Hook 位于 `frontend/src/hooks/`
- 【强制】状态管理位�?`frontend/src/stores/`
- 【强制】常量位�?`frontend/src/constants/`
- 【强制】类型定义位�?`frontend/src/api/types.ts`（统一出口�?- 【强制】工具函数位�?`frontend/src/utils/`

### 2. 命名规范

- 【强制】组件文件：PascalCase（如 `MainLayout.tsx`、`ErrorBoundary.tsx`�?- 【强制】API 模块文件：camelCase（如 `task.ts`、`about.ts`�?- 【强制】Hook 文件：`use<X>.ts`（如 `useAutoRefresh.ts`、`useSheetSync.ts`�?- 【强制】Store 文件：`<�?Store.ts`（如 `sheetStore.ts`、`configStore.ts`�?- 【强制】常量文件：按业务域分文件（`frontend/src/constants/`�?- 【强制】CSS 文件：camelCase + `.css` 后缀，与组件同目录（�?`chatbot.css`、`about.css`�?- 【强制】测试文件：`__tests__/<Component>.test.tsx`，与组件同级
- 【强制】常量：UPPER_SNAKE_CASE（如 `SSE_LAST_EVENT_ID_KEY`、`MIN_INTERVAL`、`MAX_RETRIES`�?
### 3. React 组件规范 🆕v2.0

- 【强制】使�?`function` 关键字定义组件（**�?*箭头函数�?- 【强制】Props �?`type` 关键字定义（**�?* `interface`，项目规范）
- 【强制】Hooks 调用顺序：所�?hooks 必须在条件�?return 之前调用（避�?React Hooks 规则违规�?- 【强制】双�?ErrorBoundary 容错：`LazyErrorBoundary` + `Suspense`
- 【强制】路由切换用 `requestAnimationFrame` 重置滚动位置
- 【强制�?*容器适配**：被嵌入�?SheetWorkspace/MainLayout 等固定高度容器的页面组件，用 `height: 100%` 适应父容�?- 【禁止】在嵌入场景使用 `minHeight: 100vh` �?`height: 100vh`（溢出容器导致全屏显示）
- 【强制】flex 布局�?Header �?`flex: '0 0 auto'`，Content �?`flex: 1` + `overflow: auto`
- 【推荐】独立路由页面（未进 MainLayout，如 `/login`）可�?`100vh`
- 🆕v4.0【强制�?*多视�?state 提升**：Tab/Accordion/Collapse/Drawer 多视图共享同一数据源时，state 必须提升至最近共同父组件
- 🆕v4.0【强制】`destroyInactiveTabPane={false}` 保留 DOM（表单类避免输入焦点丢失�?- 🆕v4.0【强制】标题职责归容器（如 Tab label），子组件只保留功能说明文字，禁止标题重�?  - **判断信号**：两个子组件�?props 来自同一 config/state �?应提�?- 🆕v4.2【强制�?*F-REVIEW-UI-STATE-INDEPENDENCE：UI 状态独立性原�?*
  - 受控 UI 状态（`openKeys`/`expandedKeys`/`activeKey`/`Drawer open` 等）不应通过 `useEffect` 联动路由变化（`location.pathname`/`useNavigate`�?  - 路由变化只应更新**派生状�?*：`selectedKeys`（高亮当前项）、breadcrumb（面包屑）、页面标�?  - **判断信号**：代码含 `useEffect(() => setOpenKeys(...), [autoOpenKeys])` �?`useEffect(() => setExpandedKeys(...), [location.pathname])` �?视为违规
  - **修复模式**：`openKeys` 仅在首次挂载时按当前路由初始化（`useState(() => autoOpenKeys)`），之后完全由用户通过 `onOpenChange` 控制，移�?`useEffect` 联动
  - **适用**：Menu `openKeys`、Tree `expandedKeys`、Collapse `activeKey`、Tabs `activeKey`、Drawer `open` 等用户手动控制的 UI 状�?  - **不适用**：`selectedKeys`（应联动路由高亮）、breadcrumb（应联动路由）、页面标题（应联动路由）
  - **历史教训**：MainLayout �?`openKeys` 通过 `useEffect` 联动 `autoOpenKeys`，sheet 切换触发 `navigate` �?URL 变化 �?`autoOpenKeys` 重算 �?`setOpenKeys` 重置 �?SubMenu 展开/折叠动画遮挡内容。第一次修复用"合并"策略仍会展开�?SubMenu，最终改为完全移�?`useEffect` 联动才彻底解�?
```typescript
// �?推荐：function 关键�?+ type Props
type MainLayoutProps = {
  children: React.ReactNode
}

function MainLayout({ children }: MainLayoutProps) {
  return (
    <ConfigProvider>
      <LayoutContent />
    </ConfigProvider>
  )
}
```

```typescript
// �?推荐：双�?ErrorBoundary + Suspense
const LazyRoute = ({ children }) => (
  <LazyErrorBoundary>
    <Suspense fallback={<Spin />}>
      {children}
    </Suspense>
  </LazyErrorBoundary>
)
```

- 🆕v4.11【强制�?*F-REVIEW-STATE-MACHINE-UI：状态机 UI 视觉标识完整�?*
  - 业务对象有状态字段（�?`task.status` / `session.state` / `order.status`）时，每个状态值必须有对应�?UI 视觉标识：颜�?Tag / 图标 / 文案 / 操作按钮�?*禁止**终态显�?进行�?类动画，中间态必须有 loading 反馈
  - **核心机制**（审查时必须理解）：
    - 后端状态机有白名单转换规则（B-REVIEW-STATE-MACHINE-WHITELIST），前端 UI 必须为每个状态值提供明确的视觉标识
    - 终态（`completed` / `failed` / `cancelled`）禁止显�?loading 动画�?进行�?文案，应显示最终结果的静态标识（成功/失败/已取消）
    - 中间态（`pending` / `running` / `processing`）必须有 loading 反馈（Spin / 进度�?/ 动画图标），让用户感知任务正在进�?    - 状态对应的操作按钮必须与状态机白名单转换一致（�?`running` 状态显�?暂停"按钮，`paused` 状态显�?恢复"按钮，`completed` 状态不显示任何操作按钮�?  - **判断信号**�?    - `grep "status" frontend/src/` 发现状态值但无对�?Tag/图标/文案映射 �?视为违规
    - 终态状态（`completed`/`failed`/`cancelled`）仍显示 loading 动画 �?视为违规
    - 中间态状态（`pending`/`running`）无 loading 反馈 �?视为违规
    - 操作按钮与状态机白名单不一致（�?`completed` 状态仍显示"暂停"按钮）→ 视为违规
    - 后端新增状态值但前端 UI 无对应视觉标�?�?视为违规
  - **修复模式**（状�?�?视觉标识映射�?+ 操作按钮白名单）�?    ```typescript
    // �?状态视觉标识映射表（集中管理）
    const TASK_STATUS_UI: Record<TaskStatus, { color: string; text: string; icon: ReactNode; loading: boolean }> = {
      pending: { color: 'default', text: '待开�?, icon: <ClockCircleOutlined />, loading: false },
      running: { color: 'processing', text: '运行�?, icon: <LoadingOutlined />, loading: true },
      paused: { color: 'warning', text: '已暂�?, icon: <PauseCircleOutlined />, loading: false },
      completed: { color: 'success', text: '已完�?, icon: <CheckCircleOutlined />, loading: false },
      failed: { color: 'error', text: '已失�?, icon: <CloseCircleOutlined />, loading: false },
    }
    // �?操作按钮白名单（与后端状态机 TRANSITIONS 一致）
    const TASK_ACTIONS: Partial<Record<TaskStatus, Action[]>> = {
      pending: [{ key: 'start', label: '开�? }],
      running: [{ key: 'pause', label: '暂停' }],
      paused: [{ key: 'resume', label: '恢复' }, { key: 'stop', label: '停止' }],
      // completed / failed 无操作按钮（终态不可复活）
    }
    // 消费�?    const ui = TASK_STATUS_UI[task.status]
    <Tag color={ui.color} icon={ui.icon}>{ui.text}</Tag>
    {ui.loading && <Spin size="small" />}
    {TASK_ACTIONS[task.status]?.map(a => <Button key={a.key} onClick={() => handleAction(a.key)}>{a.label}</Button>)}
    ```
  - **配置参数**：`status_ui_mapping`（状�?�?视觉标识映射表，�?color/text/icon/loading 字段）、`terminal_states`（终态列表，默认 `['completed', 'failed', 'cancelled']`，禁�?loading 动画）、`intermediate_states`（中间态列表，默认 `['pending', 'running', 'processing']`，必�?loading 反馈）、`action_whitelist`（状�?�?允许的操作按钮白名单，与后端 TRANSITIONS 一致）�?`config.yaml` �?`state_machine_ui` 节点管理
  - **适用**：所有有状态字段的业务对象（任�?会话/订单/评估）；后端有状态机白名单转换的场景
  - **不适用**：纯前端 UI 状态（�?`loading` / `open` / `active`）；无状态机�?CRUD 实体；状态值不展示给用户的内部状�?  - **历史教训**：任务状�?`completed` 仍显�?loading 动画（因为前�?`TASK_STATUS_UI` 映射表未区分终态与中间态），用户以为任务还在运行反复刷新页面。且 `failed` 状态仍显示"暂停"按钮（操作按钮未与后端状态机白名单一致），用户点击后后端返回 400 错误。修复后映射表区分终�?中间�?+ 操作按钮按白名单显示

- 🆕v4.16【强制�?*F-REVIEW-STATE-FUNCTIONAL-ALIGN：状态显示与功能可用性一�?*
  - 前端 UI 显示�?功能/会话/服务状�?（如 Cookie 层状态：`identity` / `session` / `tracking` 是否失效；服务可用性：SSE 连接、API 健康度、采集器运行状态）必须�?功能实际可用�?保持一致；**禁止**仅依据后端返回的"初始�?�?短期缓存"判定 UI 状态显示为"失效/异常"
  - **核心机制**（审查时必须理解）：
    - 后端"功能信号"字段（如 `last_session_invalid` / `is_healthy` / `is_connected`）的初始值（默认 `False`）表�?未检�?�?*不能**被解读为"功能正常"
    - 后端"功能信号"必须配合"已发生过检�?标记（首次成功时间戳 `_last_check_at > 0`、计数器 `use_count > 0`、首次成功标�?`_has_run`）才�?已检�?语义
    - 前端 UI 状态显�?有效/正常"前必须先确认"已发生过真实调用且成�?�?*禁止**仅看后端初始 `False` �?误判�?正常"�?显示绿色有效标识
    - 跨进�?跨模块场景下，子进程已检测成功的状态变更必须通过 SSE / 状态广播实时同步到前端�?*禁止**前端�?30 �?TTL 缓存兜底（子进程状态变更后 30 秒内前端仍显示旧状态）
  - **判断信号**�?    - `grep "state === 'valid'\\|state === 'normal'\\|state === 'healthy'" frontend/src/` 出现不配�?已检�?标记的硬编码布尔判定 �?视为违规
    - `grep "sessionInvalid\\|isInvalid\\|isExpired" frontend/src/` 仅依据后端单次返回值更�?UI 状态（无首次成功时间戳、计数器辅助）→ 视为违规
    - UI 状态显示组件（�?`<StatusTag>` / `<LayerStatusBadge>`）的 props 来自未校验的布尔字段（如 `valid` 默认 `false`）→ 视为可疑
    - 跨进程状态同步依�?`setInterval` 轮询�?0s/60s TTL）而未使用 SSE 推�?�?视为可疑（同步不及时�?  - **修复模式**�?    ```typescript
    // �?后端 types.ts 显式区分"未检�? / "已检测有�? / "已检测无�?
    // 与后�?xianyu-backend-code-review v4.15.0 �?B-REVIEW-STATE-DETECTION-BOOTSTRAP 对齐
    export type LayerStatus =
      | 'unknown'      // 初始未检测（前端必须显示灰色/未检测，不显�?失效"�?      | 'valid'        // 已检测且有效
      | 'invalid'      // 已检测且失效
      | 'stale'        // 已检测但超时�?last_check_threshold_seconds�?
    // �?接收后端"已检�?标记
    interface LayerState {
      status: LayerStatus
      lastCheckedAt: number    // 0 = 未检�?      useCount: number         // 0 = 未检�?      lastError?: string
    }

    // �?UI 渲染：仅�?lastCheckedAt > 0 时才显示"已检�?状�?    function LayerStatusBadge({ state }: { state: LayerState }) {
      if (state.lastCheckedAt === 0 && state.useCount === 0) {
        return <Tag color="default">未检�?/Tag>   // 必须明确区分"未检�?�?已失�?
      }
      if (state.status === 'valid') {
        return <Tag color="success">有效</Tag>
      }
      if (state.status === 'invalid') {
        return <Tag color="error">失效</Tag>
      }
      if (state.status === 'stale') {
        return <Tag color="warning">检测超�?/Tag>
      }
      return <Tag color="default">未知</Tag>
    }

    // 禁止：仅依据布尔 initial=false 判定"有效"（刚启动�?valid=false 被解读为"失效"，但实际语义�?未检�?�?    ```
  - **配置参数**�?    - `state_functional_align.required_check_marker`：默�?`true`，必须有"已检�?标记（`lastCheckedAt > 0` / `useCount > 0` / `hasRun` 至少一个）
    - `state_functional_align.unknown_status_display`：默�?`'未检�?`，未检测状态的 UI 文案
    - `state_functional_align.sse_push_required`：默�?`true`，跨进程状态变更必�?SSE 推送（禁止 TTL 兜底�?    - `state_functional_align.ttl_grace_seconds`：默�?`0`，跨进程同步�?TTL 兜底秒数�? 即不依赖 TTL�?    - `state_functional_align.stale_threshold_seconds`：默�?`3600`，已检测状态超过该秒数视为 `stale`（检测超时）
    - `state_functional_align.status_field_mapping`：状态字段到判定逻辑的映射（�?`cookie_layer �?{required: ['lastCheckedAt', 'useCount'], initialValue: 'unknown'}`�?    - `state_functional_align.status_color_mapping`：状态值到 UI 颜色/文案的映射（�?`{valid: 'success', invalid: 'error', unknown: 'default', stale: 'warning'}`�?    �?`config.yaml` �?`state_functional_align` 节点管理
  - **适用**：所�?功能/会话/服务状�?显示（Cookie 层有效�?/ SSE 连接状�?/ API 健康�?/ 采集器运行状�?/ 第三方服务可达�?/ 任务调度器状态）；跨进程/跨模块状态同步（子进程→主进程→前端）；状态自愈（容器健康检查、服务可用性兜底）
  - **不适用**：纯前端 UI 状态（�?`loading` / `open` / `active` 开关）；单次函数返回值（无状态延续语义）；无初始歧义的纯布尔开关（�?`enableNotification: boolean`）；后端已用布尔 `True/False` 明确表达"有效/失效"且前端仅做展示映射的场景
  - **历史教训**：用户反�?实时查询、官方采集均能正常运行，但反爬登录管理页�?`identity` / `session` / `tracking` 状态持续显示为失效（红 X 标签�?，根因：后端 `CookieStore` �?30 �?TTL 兜底缓存子进程状态，浏览器子进程登录后只更新子进程自己的内存缓存，主进程读时仍取�?TTL 内的�?失效"状态（30 秒后才自动恢复），同时前�?`LayerStatusBadge` 仅依�?`valid: boolean` 显示（无"未检�?区分），导致用户看到"功能可用但状态持续失�?长达 30 秒，体感"明明能跑却一直报�?。修复后三层：①后端 `sync_cookie_layers_from_json()` 显式调用 `invalidate_cache()`（B-REVIEW-CACHE-INVALIDATION）②后端 `collector.last_session_invalid=False` 仅在 `_last_m5tk_refresh > 0` 时才恢复所有层（B-REVIEW-STATE-DETECTION-BOOTSTRAP）③前端 `LayerStatusBadge` 区分 `unknown` / `valid` / `invalid` / `stale` 四态，�?已检�?标记时显示灰�?未检�?而非"失效"

### 4. TypeScript 严格规范 🆕v2.0

- 【强制】`tsconfig.json` 严格配置（`strict: true`、`noFallthroughCasesInSwitch: true`、`isolatedModules: true`�?- 【强制】`moduleResolution: bundler`（Vite 兼容�?- 【强制】路径别�?`@/* �?src/*`
- 【强制】`target: ES2020`，`jsx: react-jsx`（React 18 自动 runtime�?- 【强制】优�?`type` 而非 `interface`（项目规范）
- 【强制】字符串字面量联合而非 enum（如 `type TaskStatus = 'active' | 'paused' | 'stopped'`�?- 【强制】可选字段用 `?` 而非 `| undefined`
- 【禁止】使�?`any` 类型（SonarQube S4325），必要时用 `unknown` + 类型守卫
- 【强制】前后端字段类型对齐：`interface Task` 与后�?`TaskRow` 字段一�?- 【推荐】复杂类型用 `TypeAlias` 提升可读�?
```typescript
// �?推荐：字符串字面量联�?+ type
type TaskStatus = 'active' | 'paused' | 'stopped'

// 禁止：enum（改用字符串字面量联�?+ type�?```

- 🆕v4.11【强制�?*F-REVIEW-STATE-ENUM-ALIGN：前后端状态枚举值对�?*
  - 业务对象有状态字段（�?`task.status` / `session.state` / `order.status`）时，前�?`types.ts` 必须导出与后端严格对齐的状态联合类型，**禁止**前端硬编码状态字符串
  - **核心机制**（审查时必须理解）：
    - 后端 Python `Enum` 或字符串常量定义的状态值，前端必须 1:1 对齐（包括大小写、下划线、空格）
    - 状态值变更（如后�?`paused` 改为 `suspended`）必须同�?grep 前端所有消费点（`types.ts` + 组件 + Hook + Store）并更新
    - 前端禁止�?`as TaskStatus` 强制类型转换绕过 TS 检查（会掩盖类型不匹配 bug�?  - **判断信号**�?    - `grep "status ===" frontend/src/` 发现硬编码字符串字面量（�?`status === 'running'`）而非引用常量 �?视为可疑
    - `types.ts` 中状态联合类型与后端 `domain/<�?.py` �?`Enum` 成员不一�?�?视为违规
    - 后端新增状态值但前端 `types.ts` 未同步更�?�?视为违规
    - 前端代码�?`as TaskStatus` 强制类型转换 �?视为违规
  - **修复模式**（集中定�?+ 引用常量 + 同步更新）：
    ```typescript
    // �?types.ts 集中导出，与后端 domain/task.py �?TaskStatus 严格对齐
    export type TaskStatus = 'active' | 'paused' | 'stopped' | 'completed' | 'failed'
    export const TASK_STATUS_VALUES = ['active', 'paused', 'stopped', 'completed', 'failed'] as const
    // 消费方引用常量，禁止硬编码字符串
    if (task.status === 'completed') { ... }  // �?字面量受联合类型保护
    ```
  - **配置参数**：`status_fields`（需要状态对齐的字段列表，如 `['task.status', 'session.state', 'order.status']`）、`forbid_as_cast`（默�?`true`，禁�?`as TaskStatus` 强制转换）、`sync_check_dirs`（同步检查目录，默认 `['frontend/src/', 'src/xianyu_hunter/domain/']`）在 `config.yaml` �?`state_enum_align` 节点管理
  - **适用**：所有有状态字段的业务对象（任�?会话/订单/评估）；后端�?Enum 或常量定义状态值的场景
  - **不适用**：纯前端 UI 状态（�?`loading` / `open` / `active`）；无状态机�?CRUD 实体（如配置项）
  - **历史教训**：后�?`task.status` 新增 `suspended` 状态但前端 `types.ts` 仍为 `'active' | 'paused' | 'stopped'`，导致前端收�?`suspended` 状态时 TypeScript 不报错（因为用了 `as TaskStatus` 转换），UI 显示为默认的"未知状�?。修复后 `types.ts` 同步新增 `suspended` + 移除所�?`as TaskStatus` 转换 + grep 所有消费点确认

- 🆕v4.12【强制�?*F-REVIEW-INPUT-NUMBER-BOUNDS：InputNumber 边界约束**
  - `<InputNumber>` 组件必须设置 `min` �?`max` 属性，禁止无边界输入导�?0/负数传入后端触发 ZeroDivisionError 或负数索引导致越�?  - **核心机制**（审查时必须理解）：
    - AntD InputNumber 默认�?min/max，用户可输入任意数值（包括 0、负数、极大值）
    - 后端配置项通常无边界校验（参�?B-REVIEW-CONFIG-VALIDATION），前端必须兜底
    - 0 值传�?`interval / N` 会触�?ZeroDivisionError；负数传入数组索引会导致 undefined
  - **判断信号**�?    - 代码�?`<InputNumber` 但无 `min=` 属�?�?视为违规
    - 代码�?`<InputNumber min={0}` 但实际语义要�?`min={1}`（如间隔时间、重试次数）�?视为违规
    - 配置项含 `interval` / `count` / `retry` 等数值字段但前端 InputNumber 无边�?�?视为违规
  - **修复模式**�?    ```typescript
    // �?间隔时间类（必须 min=1，禁�?0/负数�?    <InputNumber min={1} max={3600} addonAfter="�? value={interval} onChange={setInterval} />

    // �?重试次数类（必须 min=0，允�?0 表示不重试）
    <InputNumber min={0} max={10} value={retryCount} onChange={setRetryCount} />

    // 禁止：无 min 边界，用户可输入 0/负数
    ```
  - **配置参数**：`input_number_bounds.required_min`（默�?`true`，必须有 min）、`input_number_bounds.required_max`（默�?`true`，必须有 max）、`input_number_bounds.scenario_min_values`（场景到 min 值的映射，如 `interval �?1`、`retry_count �?0`、`page_size �?1`）在 `config.yaml` �?`input_number_bounds` 节点管理
  - **适用**：所�?`<InputNumber>` 组件；配置页面数值字段；表单数值输�?  - **不适用**：纯展示型数值（disabled InputNumber）；无业务语义的数值（�?ID 输入，应用其他校验）
  - **历史教训**：配置页 `<InputNumber>` �?min 边界，用户输�?`ai_suggestion_interval=0`，后�?`asyncio.sleep(interval / 2)` 触发 ZeroDivisionError，任务循环崩�?
- 🆕v4.12【强制�?*F-REVIEW-NULL-SEMANTICS：null/undefined/空字符串语义区分**
  - TypeScript 类型必须明确区分 `null`（显式空值）、`undefined`（未定义）、`""`（空字符串）三种语义�?*禁止** `value: string` 实际可能�?null 的类型欺骗，**禁止** `value: string | null` 但代码用 `if (value)` 同时判断三种语义
  - **核心机制**（审查时必须理解）：
    - `null`：显式表�?无�?（后端返�?null�?    - `undefined`：变量未初始化或属性不存在
    - `""`：空字符串（用户主动输入空）
    - 后端 JSON 返回 `null` �?前端解析�?`null`（非 undefined）；API 字段缺失 �?前端�?`undefined`
    - `if (value)` 同时判断三种语义会导致逻辑混乱（如 `""` 被视�?falsy 但实际是有效输入�?  - **判断信号**�?    - 类型声明 `value: string` 但后�?API 可能返回 `null` �?视为违规（应�?`value: string | null`�?    - 代码�?`if (value)` 判断 string 类型 �?必须明确区分 `value === null` / `value === undefined` / `value === ""`
    - 代码�?`value ?? defaultValue` �?`""` 应保留而非替换为默认�?�?视为违规（应�?`value ?? defaultValue` 仅在 null/undefined 时替换，""保留�?  - **修复模式**�?    ```typescript
    // �?类型明确区分三种语义
    type TaskStatus = {
      name: string                    // 必有，非空字符串
      description: string | null      // 可能�?null（后端显式返�?null�?      deletedAt: string | null        // null 表示未删�?      parentTaskId?: string           // 可选属性，未传时为 undefined
    }

    // �?判断时明确区�?    if (description === null) {
      // 后端显式返回 null，表�?无描�?
      return '无描�?
    }
    if (description === '') {
      // 空字符串，用户主动输入空
      return '（空�?
    }
    return description

    // 禁止：if (value) 同时判断三种语义�?" 也被显示�?无描�?，语义错误）
    ```
  - **配置参数**：`null_semantics.strict_mode`（默�?`true`，严格区分三种语义）、`null_semantics.forbidden_union_types`（禁止的联合类型列表，如 `["string | null | undefined"]` 应用 `string | null` + 可选属性）、`null_semantics.if_check_pattern`（检�?`if (value)` 同时判断 string 类型的模式）�?`config.yaml` �?`null_semantics` 节点管理
  - **适用**：所�?TypeScript 类型声明；后�?API 返回字段的类型定义；表单字段的类型与判断逻辑
  - **不适用**：纯前端计算字段（无 null 语义）；布尔类型（true/false 已明确）
  - **历史教训**：API 返回 `parentTaskId: null` 但前端类型声明为 `parentTaskId?: string`，代码用 `if (task.parentTaskId)` 判断导致 null 被视�?falsy �?undefined 行为一致，但实际语义不同（null 表示"曾有父任务但已解�? vs undefined 表示"从未有父任务"�?
- 🆕v4.25【建议�?*F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY：默认值操作符一致性检�?*
  - 维度�? TypeScript 严格规范
  - 严重等级：info
  - **检查点**：默认值场景是否统一使用 `??` 而非 `||`
  - **判定标准**：InputNumber/Select �?`onChange` 默认值必须用 `??`（nullish coalescing）。`||` 会将 `0`/`''`/`false` 也视�?falsy，可能导致意外行为（�?qps=0 被替换为默认�?1）。只有需要同时过�?`0`/`''`/`false` 的场景才允许�?`||`
  - **检查范�?*：所�?`onChange` 中的默认值表达式、函数参数默认值、变量初始化
  - **核心机制**（审查时必须理解）：
    - `??` 仅在左侧�?`null`/`undefined` 时返回右侧值（语义清晰：缺失时给默认）
    - `||` 在左侧为任意 falsy 值（`null`/`undefined`/`0`/`''`/`false`/`NaN`）时返回右侧值（语义模糊：可能误伤合法的 0/''/false�?    - 数值类字段（qps、interval、timeout、retryCount）的 `0` 是合法值，不能�?`||` 替换为默认�?    - 字符串类字段（label、description）的 `''` 是合法值（用户主动清空），不能�?`||` 替换为默认�?    - 布尔类字段（enabled、silent）的 `false` 是合法值，不能�?`||` 替换为默认�?  - **判断信号**（grep 检测）�?    - `grep -nE "onChange=\{\(v\) => .* \|\| " frontend/src/pages/**/*.tsx` 命中 �?检查是否应改为 `??`
    - `grep -nE "value \|\| [0-9]+" frontend/src/pages/**/*.tsx` 命中 �?数值默认值场景必�?    - `grep -nE "const \w+ = \w+ \|\| '" frontend/src/pages/**/*.tsx` 命中 �?字符串默认值场景必�?    - 用户反馈"qps=0 无法保存，被强制改为 1" �?必查 `||` 误用
  - **修复模式**�?    ```typescript
    // �?正确：数值默认值用 ??�? 是合法�?    <InputNumber onChange={(v) => update({ qps: v ?? 1 })} />

    // 禁止：用 || 会把 0 也视�?falsy，qps=0 被替换为 1

    // �?正确：字符串默认值用 ??�?' 是合法值（用户主动清空�?    const label = formData.label ?? '默认标签'

    // 禁止：用 || 会把 '' 也视�?falsy，用户清空后被强制改回默认�?
    // �?例外：需要同时过�?0/''/false 时允许用 ||
    const displayName = user.nickname || user.username || '匿名'  // 空字符串视为"未设�?
    ```
  - **配置参数**：`default_operator` 节点（在 `config.yaml` 管理，不硬编码）�?    - `enabled`（默�?`true`，开关本检查）
    - `preferred_operator`（默�?`"??"`，推荐使用的默认值操作符�?    - `logical_or_exceptions`（默�?`["displayName = nickname || username", "fallback chain"]`，允许使�?`||` 的场景白名单�?    - `detection_patterns`（默�?`["onChange={(v) => ... || ", "value || 0", "value || ''"]`，触发检查的代码模式�?    - `forbidden_in_numeric_context`（默�?`true`，数值类字段禁止�?`||`�?    - `forbidden_in_string_context`（默�?`true`，字符串类字段禁止用 `||`�?    - `forbidden_in_boolean_context`（默�?`true`，布尔类字段禁止�?`||`�?  - **适用场景**：所有提供默认值的表达式（onChange 默认值、变量初始化、函数参数默认值、对象属性默认值）
  - **不适用场景**：需要同时过�?`0`/`''`/`false` 的场景（如空字符串转默认值的 fallback 链、用户昵称缺失时回退到用户名）；布尔条件判断（`if (a || b)` 是逻辑或，不是默认值）；React 组件条件渲染（`{a || <Fallback/>}` 是逻辑或渲染）
  - **历史教训**：任务级配置覆盖功能开发时，`InputNumber` �?`onChange` �?`v || 1`，导致用户输�?0 时被强制改为 1（qps=0 是合法值，表示"不限制速率"）。修复方式：改为 `v ?? 1`，仅�?v �?null/undefined（用户未输入）时给默认�?1
  - **对应后端原则**：后�?Python 使用 `or` 时同样存在类似问题（`0`/`''`/`False` �?falsy），详见 `xianyu-backend-code-review` �?`B-REVIEW-DEFAULT-OPERATOR`（如有）

### 5. AntD 5 主题规范 🆕v2.0

- 【强制】使�?Ant Design 5.21+ + `ConfigProvider` 主题�?- 【强制】基础 token 包含 `colorPrimary: '#FF6200'`（闲鱼品牌橙）、`borderRadius: 8`
- 【强制】暗色主题用 `theme.darkAlgorithm`，亮色用 `theme.defaultAlgorithm`
- 【强制】`ConfigProvider` 必须�?`BrowserRouter` 外层（让独立路由�?`/login` 也能切换主题�?- 【强制】`theme.useToken()` �?ConfigProvider 内部消费
- 【强制】组件级主题覆盖（如 `Table.rowHoverBg`）需响应 `isDark` 状�?- 【强制�?*交互元素颜色对比�?*：可点击的文字、图标、提示用 `colorPrimary`（即 `activeColor`），确保对比�?- 【禁止】交互元素文字用 `colorBorder`（对比度不足，浅�?深色主题下均难辨识）
- 【推荐】装饰性元素（边框、背景、分隔线）可�?`colorBorder`，交互元素不�?- 🆕v4.8【强制�?*F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE：AntD 主题 token 动态覆盖模�?*
  - 项目支持暗色主题（`theme.darkAlgorithm`）时，`baseTheme.components.<Component>.<token>` �?*显式指定**的主题相�?token（token 名含 `Color` / `Bg` / `Border` / `Hover` / `Active` / `Focus` 后缀）必须根�?`isDark` 状态在能读�?`useTheme()` 的组件（通常�?`ThemedRoot`）内**动态覆�?*�?*禁止**依赖 `darkAlgorithm` 自动重算�?`index.css` 中的 `--ant-*` CSS 变量
  - **核心机制**（审查时必须理解）：
    - antd v5 �?`darkAlgorithm` **仅重算未指定�?token**，显式指定的 token 会被原样继承 �?这是 `baseTheme` 中显式指定的亮色值在暗色主题下失效的根因
    - antd v5 �?`cssVar` 模式**默认未启�?*，手动在 `index.css` 中写�?`--ant-*` CSS 变量不被组件引用，是死代�?�?不能依赖 CSS 变量覆盖 token，必须改 `ConfigProvider`
  - **判断信号**�?    - `grep "components\\." main.tsx` 发现 `baseTheme.components.<Component>.<token>: '<value>'` 显式指定了主题相�?token（token 名含 `Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus` 后缀�?    - 项目使用 `algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm`（支持暗色主题）
    - �?token �?`ThemedRoot` �?*未根�?`isDark` 动态覆�?*（直�?spread `baseTheme` 后未覆盖 `components.<Component>.<token>`）→ 视为违规
    - `index.css` 中存�?`--ant-*` CSS 变量定义（`grep "\\-\\-ant-" index.css`）→ 视为可疑死代码，需确认是否启用 `cssVar` 模式，未启用则清�?  - **修复模式**（在 `ThemedRoot` �?spread `baseTheme` 后动态覆盖）�?    ```typescript
    function ThemedRoot() {
      const { isDark } = useTheme()
      return (
        <ConfigProvider
          theme={{
            ...baseTheme,
            algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
            components: {
              ...baseTheme.components,
              Table: {
                ...baseTheme.components.Table,
                // darkAlgorithm 不会重算显式指定�?token，故必须在此处动态覆�?                // 暗色用品牌色淡橙透明叠加，与卡片背景 #1f1f1f 形成明显对比且与亮色 #fff7f0 调性一�?                rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : '#fff7f0',
              },
            },
          }}
        >
          <BrowserRouter basename="/xianyu">
            <App />
          </BrowserRouter>
        </ConfigProvider>
      )
    }
    ```
  - **暗色值选择原则**（与品牌�?`#FF6200` 保持视觉一致性，参数�?`config.yaml` �?`antd_theme_override` 节点管理）：
    - `Hover` / `Active` 状态色：优先用「品牌色 + 低透明度」叠加（�?`rgba(255, 98, 0, 0.08)`），避免硬编码纯色或过深�?    - 背景色（`Bg` 后缀）：用暗色阶梯色（如 `#1f1f1f` / `#141414`�?    - 文字色（`Color` 后缀）：�?`rgba(255, 255, 255, 0.88)` �?`#e0e0e0`
    - 边框色（`Border` 后缀）：�?`rgba(255, 255, 255, 0.15)` 等半透明�?  - **注释要求**（注释必须解释「为什么」而非「做什么」，参考用户编程原则）�?    1. 说明 `darkAlgorithm` 不会重算显式 token（避免后续维护者误以为会自动适配�?    2. 说明 WCAG 对比度计算（暗色文字�?hover 背景的对比度需满足 AA �?�?4.5:1�?    3. 说明品牌色一致性（暗色值与亮色值在视觉调性上保持一致，如都是淡橙调�?  - **配置参数**：`theme_token_whitelist`（主题相�?token 名称后缀白名单：`Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus`）、`dark_value_strategy`（暗色值生成策略：`hover_active=brand_overlay` / `background=dark_step` / `text=white_alpha`）、`brand_color`（默�?`#FF6200`）、`brand_overlay_alpha`（默�?`0.08`）、`wcag_level`（默�?`AA`）、`cssvar_enabled`（默�?`false`，用于判�?`--ant-*` 变量是否为死代码）在 `config.yaml` �?`antd_theme_override` 节点管理
  - **诊断流程**（出现「暗色主题下文字看不�?对比度低」类问题时执行）�?    1. `grep "components\\." main.tsx` 扫描所有显式指定的 token
    2. 逐个检�?token 名是否含主题相关后缀（`Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus`�?    3. 对每个主题相�?token，验证是否响应了 `isDark` 动态切�?    4. 若未响应 �?判定为违规，按修复模式动态覆�?    5. 顺手 `grep "\\-\\-ant-" index.css` 检查是否有死代�?CSS 变量，确认后清理
  - **适用**：AntD 5.x 项目 + 多主题支持（`darkAlgorithm` / `defaultAlgorithm` 切换�? `baseTheme.components.<Component>.<token>` 显式指定主题相关 token 的场景；WCAG 可访问性合规场�?  - **不适用**：未启用多主题的项目（仅默认亮色）；antd v4 及以下（主题机制不同）；启用�?antd v5 `cssVar: true` 的项目（CSS 变量会生效，可优先用 CSS 变量方案）；�?antd UI 库；与主题无关的 token（`borderRadius`/`fontSize`/`lineHeight` �?`darkAlgorithm` 会自动适配�?  - **历史教训**：`baseTheme.components.Table.rowHoverBg` 显式指定�?`#fff7f0`（接近白色的淡橙），暗色主题下被原样继承，与暗色文字 `rgba(255, 255, 255, 0.88)�?e0e0e0`（也接近白色）对比度近乎为零，hover 时文字几乎看不见。同�?`index.css` 中残留的 `--ant-table-row-hover-bg: #262626` 是死代码（未启用 cssVar 模式，不被组件引用）误导了初版诊断。修复后�?`ThemedRoot` 内根�?`isDark` 动态覆盖为 `rgba(255, 98, 0, 0.08)`

```typescript
// �?推荐：ConfigProvider �?BrowserRouter 外层
// 注意：baseTheme 中显式指定的主题相关 token（含 Color/Bg/Border/Hover/Active/Focus 后缀�?// 必须�?ThemedRoot 内根�?isDark 动态覆盖（darkAlgorithm 不会重算显式 token�?const baseTheme = {
  token: { colorPrimary: '#FF6200', borderRadius: 8 },
  components: {
    Table: { rowHoverBg: '#fff7f0' },  // 亮色值，暗色需�?ThemedRoot 动态覆�?  },
}

function ThemedRoot() {
  const { isDark } = useTheme()
  return (
    <ConfigProvider
      theme={{
        ...baseTheme,
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        components: {
          ...baseTheme.components,
          Table: {
            ...baseTheme.components.Table,
            rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : baseTheme.components.Table.rowHoverBg,
          },
        },
      }}
    >
      <BrowserRouter basename="/xianyu">
        <App />
      </BrowserRouter>
    </ConfigProvider>
  )
}
```

### 6. Zustand 状态管�?🆕v2.0

- 【强制】使�?Zustand 4.5（轻量状态管理）
- 【强制】`persist` 中间�?+ `partialize` 只存必要字段（过�?ReactNode 等不可序列化字段�?- 【强制】store 是纯逻辑层（不感知路由库�?- 【强制】`_navigator` 由组件通过 `useNavigate` 注入，不直接依赖 `react-router-dom`
- 【强制】防抖持久化�?00ms�?- 【强制】`hydrate()` 恢复时丢弃失�?path
- 【推荐】`replacedHistory` 回收栈最�?5 �?FIFO
- 【强制】`openSheet()` 四分支决策：
  1. `activateExistingSheet`：已存在则激�?  2. `performCircularReplace`：达�?maxSheets 上限时循环替�?  3. `replaceMobileActiveSheet`：移动端替换当前活动
  4. `createNewSheet`：创建新页签
- 【强制�?*状态变更操作一致�?*：每个状态变更函数必须同步更新所有相关字�?  - `activateSheet` 激活最小化 sheet 时必须同时设 `minimized: false`
  - `closeSheet` 关闭激活项时必须同步切�?`activeId` 到相邻项
  - `minimizeSheet` 最小化激活项时必须同步切�?`activeId` 到下一个非最小化�?  - 检查方法：列出操作影响的所有字段，确认全部同步更新
- 🆕v4.6【强制�?*F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND：多源状态同步统一入口（前端侧�?*
  - 前端调用同一后端写入接口的不同代码路径时，状态更新必须统一通过单一 `updateState` / `refetchState` 函数而非各路径独立更�?  - **判断信号**�?    - 多个组件 / Hook 各自调用后端 GET 接口获取同一份状态（�?`/cookies/layers` / `/api/auth/me` / `/api/about`�?    - 各组件独�?setState 但缺少统一 refetch 入口
    - 一个组件更新状态后，其他依赖同一状态的组件不会自动刷新（需要手动刷新页面）
  - **修复模式**�?    - 抽取 `useXxxState()` Hook + 内部 `refetch()` 方法 + 写入路径统一调用 `refetch()`
    - 复杂场景�?Zustand 集中管理（`setXxxState(newData)`），写入路径统一 `setXxxState`
    - **禁止**每个组件独立 `useEffect(() => fetch(...), [])` 重复拉取
  - **关键约束**：写入路径调�?refetch 后，**禁止**再独�?setState 旧值（避免回退）；refetch 失败应保留旧状态并 `message.warning`
  - **配置参数**：`unified_state_hooks`（统一状�?Hook 列表）、`write_entry_paths`（需要触�?refetch 的写入路径）�?`config.yaml` �?`state_sync_frontend` 节点管理
  - **适用**：后端有"主数据源"概念 + 多入口更新同一份状�?+ 前端需要展示最新状�?  - **不适用**：纯客户端状态（localStorage 独占）、只读状态（一次性拉取）
  - **历史教训**：后�?`/cookies/layers` 端点修复统一同步入口后，前端若仍�?`useEffect` 在各组件独立调用 + 不同�?refetch，会出现"某些页面显示失效、另一些页面显示有�?的不一致现象。统一通过 `useCookieLayersStore` 集中管理 + 各写入路�?refetch 后彻底一�?- 🆕v4.11【强制�?*F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY：前端缓存与后端状态机一致�?*
  - 同一业务目标（如"刷新会话" / "更新任务状�?）有 �?2 条链路（API 路由 + WebSocket 推�?+ 定时任务 + 手动操作）触发同一状态变更时，前端必须通过**统一 refetch 入口**刷新缓存�?*禁止**各链路独�?`setState` 导致缓存不一�?  - **核心机制**（审查时必须理解）：
    - 后端状态机有白名单转换规则（B-REVIEW-STATE-MACHINE-WHITELIST），前端缓存必须与后端状态机保持一�?    - 多链路触发同一状态变更时（如 API 调用 + SSE 推�?+ 定时轮询），若各链路独立 `setState`，会出现"页面 A 显示新状态、页�?B 显示旧状�?的不一�?    - 前端缓存（Zustand store / useState / useRef）必须通过统一 `refetch()` 入口从后端拉取最新状态，而非各链路独立推�?  - **判断信号**�?    - 多个组件 / Hook 各自调用后端 GET 接口获取同一份状�?+ 各自 `setState` �?视为违规
    - API 调用成功后前�?`setState(newStatus)` 但未触发其他依赖同一状态的组件刷新 �?视为违规
    - SSE 推送状态变更但前端只更新当前组�?`setState` 未刷新全局缓存 �?视为违规
    - 定时轮询拉取状态后前端 `setState` �?API 调用路径�?`setState` 逻辑不一�?�?视为违规
  - **修复模式**（统一 refetch 入口 + 集中状态管理）�?    ```typescript
    // �?抽取 useXxxState() Hook + 内部 refetch() + 多链路统一调用 refetch()
    function useTaskState() {
      const [task, setTask] = useState<Task | null>(null)
      const refetch = useCallback(async (taskId: number) => {
        const data = await taskApi.get(taskId)
        setTask(data)  // 统一 setState 入口
      }, [])
      return { task, refetch, setTask }
    }
    // API 调用路径
    const handleControl = async (action) => {
      await taskApi.control(taskId, action)
      await refetch(taskId)  // �?统一 refetch
    }
    // SSE 推送路�?    useEffect(() => {
      const es = new EventSource(...)
      es.onmessage = (e) => {
        const data = JSON.parse(e.data)
        if (data.task_id === taskId) refetch(taskId)  // �?统一 refetch，禁止独�?setState
      }
    }, [taskId, refetch])
    ```
  - **关键约束**�?    - 多链路触发同一状态变更时�?*必须**调用统一 `refetch()` 从后端拉取最新状态，**禁止**各链路独�?`setState` 推断新状�?    - `refetch()` 失败应保留旧状态并 `message.warning`�?*禁止**清空缓存
    - SSE 推�?+ 定时轮询 + API 调用三链路必须共享同一 `refetch()` 入口
  - **配置参数**：`unified_refetch_hooks`（统一 refetch Hook 列表）、`multi_link_state_fields`（多链路状态字段列表，�?`['task.status', 'session.state']`）、`forbid_independent_setstate`（默�?`true`，多链路场景禁止独立 setState）在 `config.yaml` �?`dual_link_cache_consistency` 节点管理
  - **适用**：同一业务目标�?�?2 条链路触发状态变更的场景（API + SSE + 轮询）；后端有状态机白名单转换的场景
  - **不适用**：单链路状态变更（只有 API 调用，无 SSE/轮询）；纯前�?UI 状态（不依赖后端）；只读状态（无写入操作）
  - **历史教训**：任务详情页通过 API 调用 `taskApi.control(taskId, 'pause')` �?`setTask({ ...task, status: 'paused' })` 独立推断状态，但任务列表页通过定时轮询拉取最新状态显�?`running`（后端实际状态已�?`paused`，但列表页缓存未刷新），导致"详情页显示已暂停、列表页显示运行�?的不一致。修复后两页统一通过 `useTaskState().refetch(taskId)` 刷新缓存

```typescript
// �?推荐：persist + partialize
export const useSheetStore = create<SheetState>()(
  persist(
    (set, get) => ({
      sheets: [],
      openSheet: (path, title, icon) => { ... },
    }),
    {
      name: 'sheet-storage',
      partialize: (state) => ({ /* 只存必要字段，过�?ReactNode */ }),
    }
  )
)
```

### 7. API 调用规范 🆕v2.0

- 【强制】使�?axios 单例 + 拦截器（`frontend/src/api/client.ts`�?- 【强制】`baseURL: '/api'` + `withCredentials: true`�?*硬约�?*：所有请求携�?cookie 通过后端认证�?- 【强制】请求拦截器附加 `Authorization: Bearer <token>`
- 【强制】响应拦截器 401 防抖跳转（`isRedirecting` 标志位防重复跳转�?- 【强制】业�?API 模块导出 `<�?Api` 对象�?*禁止**默认导出�?- 【强制】API 统一出口 `frontend/src/api/index.ts`，新�?API 归入子模�?- 【强制】SSE 流式请求�?`fetch + ReadableStream`（axios 不支持流式）
- 【强制】SSE 请求必须包含 `credentials: 'include'`
- 【强制】错误抛 axios 兼容格式：`Object.assign(new Error(msg), { response: { status, data } })`

```typescript
// �?推荐：业�?API 模块导出对象
export const taskApi = {
  list: () => client.get('/tasks'),
  get: (id: number) => client.get(`/tasks/${id}`),
  create: (data: TaskCreate) => client.post('/tasks', data),
  control: (id: number, action: string) => client.post(`/tasks/${id}/control`, { action }),
}

// �?推荐：SSE �?fetch + ReadableStream
live: async () => {
  const response = await fetch('/api/tasks/live', {
    credentials: 'include',  // 【硬约束�?  })
  const reader = response.body!.getReader()
  // ... 解析 SSE 事件
}
```

- 🆕v4.5【强制�?*F-REVIEW-CONFIG-LINKAGE：配置全链路生效验证（前端侧�?*
  - 前端配置项（如搜索间隔、防抖间隔、排序方式）从定义到消费必须全链路追踪，**禁止**只在配置页设置但不传递给后端 API
  - **判断信号**：前端配置页有某配置�?�?但对应的 API 请求参数中不包含该字�?�?配置无效
  - **检查方�?*：从前端配置页表�?�?提交 API �?后端 config.yaml �?后端 Config �?�?后端方法参数 �?最�?URL/SQL，确认每层都读取并传�?  - **适用**：所有前端可配置的参数（搜索参数、间隔、阈值），尤其是新增配置项后
  - **不适用**：前端纯 UI 配置（如主题色、页签数量）
  - **历史教训**：前端配置页显示"排序方式：默认综�?，用户可以设置排序方式，但后�?`build_search_url` 不支�?sort_type 参数，搜�?URL 中从不包�?`&sortType=...`。前�?搜索间隔"文案也混淆了"操作延迟"�?任务循环间隔"两个概念
- 🆕v4.7【强制�?*F-REVIEW-FILTER-SCENARIO-FRONTEND：过滤逻辑场景区分（前端侧�?*
  - 前端调用后端查询接口时，必须按使用场景显式传递场景标志（�?`include_failed` / `include_deleted`），**禁止**所有调用点使用默认值导致展示页看不到完整数�?  - **判断信号**：前端调�?`list_orders` / `list_tasks` 等查询接口时 �?检查是否传�?`include_failed` 参数 �?展示历史场景（评估明细页、历史记录页）必须传 `True` �?操作判断场景（抢单按钮、状态判断）�?`False` 或默认�?  - **修复模式**：识别接口的所有前端调用点 �?按场景分类（展示历史 vs 操作判断）→ 展示历史场景显式�?`include_failed: true` �?操作判断场景显式�?`include_failed: false` �?添加注释说明为何该场景需�?不需要失败数�?  - **配置参数**：`scenario_flag_field`（默�?`include_failed`）、`display_history_routes`（展示历史场景路由列表）、`operation_judge_routes`（操作判断场景路由列表）�?`config.yaml` �?`filter_scenario_frontend` 节点管理
  - **关键约束**�?    - 展示历史场景**必须显式�?`True`**，不依赖后端默认值（后端默认安全�?`False`�?    - 前端调用点必须有注释说明为何该场景需�?不需要失败数�?    - 新增查询接口调用点时，必须评估属于哪种场�?  - **适用**：调用后�?`list_*` / `get_*` 查询接口的所有前端代码路径，尤其是订�?任务/日志类查�?  - **不适用**：纯前端筛选（�?Table 组件�?filter）、单一场景的查询（如报表统计只看成功）
  - **历史教训**：评估明细页调用 `list_orders_by_item_ids` 时未�?`include_failed`，后端默认跳�?failed 订单，导致用户点击抢单失败后刷新页面看到 "�?，误以为没下过单而反复触发抢单。修复后评估明细页显式传 `include_failed: true`
- 🆕v4.10【强制�?*F-REVIEW-FILTER-VISIBILITY：过滤结果可见性（前端侧）**
  - 后端返回 `filter_summary` 时前端必须实现三态提示策�?+ "查看被过滤结�?入口�?*禁止**只显�?查询完成"不暴露过滤过�?  - **核心机制**（审查时必须理解）：
    - 后端过滤链（keyword/price/publish_days/自定义）会输�?`filter_summary` �?`raw`/各阶�?`*_skipped`/`final_total`/`filtered_out` 详情
    - 前端若只�?`final_total` 不展示过滤过程，用户无法判断"无结�?是搜索无果还是被过滤掉，反复调整搜索词无�?    - TypeScript 类型必须显式声明 `filter_summary?: LiveFilterSummary`�?*禁止**�?`as { filter_summary?: ... }` 强制类型转换绕过 TS 检查（会掩盖类型不匹配 bug�?  - **判断信号**�?    - 前端代码�?`(res as { filter_summary?: ... })` 强制类型转换 �?视为违规
    - 实时搜索/列表查询结果 `final_total == 0` 但前端只显示"查询完成"无任何过滤提�?�?视为违规
    - 后端返回 `filtered_out` 非空但前端无"查看被过滤结�?入口 �?视为违规
    - `grep "filter_summary" frontend/src/` 发现类型定义或消费逻辑缺失 �?视为违规
  - **修复模式**（三态提�?+ 按钮入口 + Modal 详情）：
    ```typescript
    // �?API 类型显式声明
    export interface LiveFilterSummary {
      raw: number; formatted: number;
      keyword_skipped: number; price_skipped: number; publish_days_skipped: number;
      final_total: number; final_items: number; final_sellers: number;
      filtered_out: LiveFilteredItem[];
    }
    export interface LiveFilteredItem {
      link_type: string; link_key: string;
      display?: Partial<TaskLink['display']> & Record<string, any>;
      filter_reason: 'keyword' | 'price' | 'publish_days';
      filter_detail: string;
    }
    // live() 返回类型显式声明 filter_summary
    async function live(): Promise<{ items: TaskLink[]; filter_summary?: LiveFilterSummary; ... }>

    // �?三态提示策�?    const fs = res.filter_summary  // 类型已在 live() 声明，无需 as 转换
    setLiveFilterSummary(fs || null)
    const itemCount = res.items?.length || 0
    if (itemCount > 0) {
      message.success(`实时查询完成，获�?${itemCount} 条`)
    } else if (fs && fs.raw > 0) {
      // warning 必须列出各过滤原因计�?      const reasons: string[] = []
      if (fs.keyword_skipped) reasons.push(`关键�?${fs.keyword_skipped}`)
      if (fs.price_skipped) reasons.push(`价格 ${fs.price_skipped}`)
      if (fs.publish_days_skipped) reasons.push(`发布时间 ${fs.publish_days_skipped}`)
      message.warning(`搜索�?${fs.raw} 条，但全部被过滤条件筛掉�?{reasons.join('�?) || '未知原因'}），请调整任务过滤配置`)
    } else {
      message.info('实时查询完成，未找到匹配商品')
    }

    // �?"查看被过滤结�?按钮 + Modal（仅 filtered_out 非空时显示）
    {liveFilterSummary && liveFilterSummary.filtered_out.length > 0 && (
      <Button onClick={() => setFilteredModalOpen(true)}>
        查看被过滤的 {liveFilterSummary.filtered_out.length} 条结�?      </Button>
    )}
    <Modal open={filteredModalOpen} onCancel={() => setFilteredModalOpen(false)}>
      <Alert message={`过滤链路：原�?${fs.raw} �?关键�?${fs.keyword_skipped} �?价格 ${fs.price_skipped} �?发布时间 ${fs.publish_days_skipped} �?最�?${fs.final_total}`} />
      <Table dataSource={fs.filtered_out} columns={[
        { title: '商品', dataIndex: 'display' },
        { title: '过滤原因', dataIndex: 'filter_reason', render: (v) => <Tag>{v}</Tag> },
        { title: '详情', dataIndex: 'filter_detail' },
      ]} />
    </Modal>
    ```
  - **三态判定阈�?*（参数在 `config.yaml` �?`filter_visibility` 节点管理）：
    - `success`：`raw >= success_raw_min`（默�?1）且 `final_total >= success_final_min`（默�?1�?    - `warning`：`raw >= warning_raw_min`（默�?1）且 `final_total <= warning_final_max`（默�?0�?    - `info`：`raw <= info_raw_max`（默�?0�?  - **配置参数**：`filter_visibility.three_state_thresholds`（三态判定阈值，如上）、`filter_visibility.modal_required_min_items`（默�?1，filtered_out 长度 �?此值时必须提供 Modal 入口）、`filter_visibility.filter_reason_labels`（过滤原因中文标签映射，�?`{ keyword: "关键�?, price: "价格", publish_days: "发布时间" }`）、`filter_visibility.forbid_as_cast`（默�?`true`，禁�?`as { filter_summary?: ... }` 强制类型转换）在 `config.yaml` �?`filter_visibility` 节点管理
  - **诊断流程**（出�?实时搜索无结果但不知原因"类问题时执行）：
    1. `grep "filter_summary" frontend/src/` 扫描类型定义与消费逻辑
    2. 检�?API 返回类型是否显式声明 `filter_summary?` 字段
    3. 检查消费代码是否含 `as { filter_summary?: ... }` 强制转换（违规信号）
    4. 检�?`final_total == 0` 分支是否实现三态提�?    5. 检�?`filtered_out` 非空时是否提�?查看被过滤结�?按钮+Modal
  - **适用**：所有调用后端含过滤链路查询接口（实时搜�?历史查询/列表过滤）的前端代码；后端返�?`filter_summary` 结构的场�?  - **不适用**：无过滤的纯 CRUD 接口；前端纯前端过滤（如 Table 自带筛选）；过滤结果不影响用户体验的场景（如后台日志查询）
  - **历史教训**：实时搜索接�?`final_total=0`（keyword 过滤 32 + price 过滤 27 = 0 最终）但前端只显示"实时查询完成"，用户无法判断是搜索无结果还是被过滤掉，反复调整搜索词无果。且 `task.ts` �?`live()` 返回类型未声�?`filter_summary`，前端用 `(res as { filter_summary?: LiveFilterSummary })` 强制转换绕过 TS 检查。修复后 `live()` 显式声明返回类型 + 三态提�?+ "查看被过滤结�?Modal + api/index.ts re-export 新类�?
- 🆕v4.12【强制�?*F-REVIEW-BATCH-OPERATION：批量操作完整流�?*
  - 批量操作（一键启�?停止/删除所有任务等）必须实现完整流程：`Modal.confirm` 确认 + loading 状�?+ success/error message 反馈 + 异常处理 + 状态刷新，**禁止**只调 API 不反馈或只反馈不刷新
  - **核心机制**（审查时必须理解）：
    - 批量操作影响多个资源，必须用户显式确认（Modal.confirm）防止误�?    - 操作期间必须显示 loading 状态防止重复点�?    - 操作成功/失败必须明确反馈（message.success/error�?    - 部分失败时必须告知用户跳过数量和失败原因
    - 操作完成后必须刷新状态（loadTasks）确�?UI 与后端一�?  - **判断信号**�?    - 代码�?`taskApi.batchControl` / `Promise.all(ids.map(...))` 等批量调�?�?必须有完整流�?    - 代码�?`<Button onClick={() => taskApi.batchControl(...)}>` �?Modal.confirm �?视为违规
    - 代码含批�?API 调用但无 loading 状�?�?视为违规
    - 代码含批�?API 调用但无 try/catch �?视为违规
  - **修复模式**�?    ```typescript
    const [startAllLoading, setStartAllLoading] = useState(false)

    const handleStartAll = useCallback(() => {
      // 过滤出需要启动的任务（跳过已运行�?      const toStart = tasks.filter((t) => t.status !== 'running')
      const skipped = tasks.length - toStart.length
      if (toStart.length === 0) {
        message.info(skipped > 0 ? `所�?${skipped} 个任务已在运行中` : '暂无任务可启�?)
        return
      }
      // 确认对话�?      const taskNames = toStart.map((t) => t.name || t.keyword).slice(0, 5).join('�?)
      const more = toStart.length > 5 ? ` �?${toStart.length} 个任务` : ''
      Modal.confirm({
        title: '确认启动所有任务？',
        content: `将启�?${toStart.length} 个任务（${taskNames}${more}）` +
          (skipped > 0 ? `，跳�?${skipped} 个已运行任务` : ''),
        okText: '启动',
        cancelText: '取消',
        onOk: async () => {
          setStartAllLoading(true)
          try {
            await taskApi.batchControl(toStart.map((t) => t.id), 'restart')
            message.success(`已启�?${toStart.length} 个任务` + (skipped > 0 ? `，跳�?${skipped} 个` : ''))
            await loadTasks()  // 刷新状�?          } catch (err: unknown) {
            const detail = err instanceof Error ? err.message : String(err)
            message.error(`启动失败: ${detail.slice(0, 100)}`)
          } finally {
            setStartAllLoading(false)
          }
        },
      })
    }, [tasks, loadTasks])

    // 禁止：无确认 + �?loading + 无反�?    ```
  - **配置参数**：`batch_operation.required_steps`（默�?`["confirm", "loading", "feedback", "refresh"]`，必须的步骤）、`batch_operation.confirm_component`（默�?`Modal.confirm`）、`batch_operation.max_preview_items`（默�?`5`，确认框中预览的任务名数量上限）、`batch_operation.error_message_max_length`（默�?`100`，错误消息截断长度）�?`config.yaml` �?`batch_operation` 节点管理
  - **适用**：所有批量操作（一键启�?停止/删除/导出所有任务）；影响多个资源的操作；不可逆操作（删除/归档�?  - **不适用**：单个资源操作（如启动单个任务）；纯查询操作（无副作用）；用户已通过其他方式确认的操作（如表单提交）
  - **历史教训**：`TaskContentMenu` 一键启动按钮直接调 `taskApi.batchControl` 无确认无 loading 无反馈，用户点击后无任何反应以为没生效重复点击，导致同一任务被启动多�?
- 🆕v4.20【强制�?*F-REVIEW-VERSION-SOURCE-ALIGN：元数据源显示对齐规�?*
  - 前端显示构建期元数据（版本号/构建时间/git_sha 等）必须调用**语义对齐**�?API 端点（如 `aboutApi.get()` �?`/api/about`），**禁止**将返�?`len(backups)` / `count` / `size` / `length` 等业务计数端点当作版本号使用；新增元数据 API 调用必须通过 `Promise.all` 与既�?API 并行化避免瀑布请求；修复时必须同步清理�?`set` �?`read` 的死代码 state
  - **核心机制**（审查时必须理解）：
    - 构建期元数据必须有唯一源头（Single Source of Truth），前端只是消费方，不能从同名但语义不同的端点推�?    - 端点命名相似不等于语义对齐：`/api/config/version` 名称�?"version" 但实际返�?`len(backups)`，受 `BACKUP_KEEP` 上限影响会卡在上限�?    - 显示元数据的组件（`<Statistic>` / `<Tag>` / `<Descriptions.Item>`）必�?grep `value=` 字段来源，确认来自语义对�?API
    - 新增独立 API 调用必须 `Promise.all` 并行化（与既�?configApi 调用同时发起），避免串行瀑布请求导致加载时间翻�?    - 修复 bug 时发现只 `set` �?`read` �?state（如 `const [, setXxx] = useState(0)`）必须同步清理，避免遗留死代�?  - **判断信号**�?    - `grep "getVersion\\(\\)" frontend/src/` 用于版本号显�?�?视为违规（应改用 `aboutApi.get()`�?    - `grep "Statistic.*title=.*version" frontend/src/` �?`value=` 字段来自 `length` / `count` / `size` �?视为违规
    - `grep "Tag.*color=.*version" frontend/src/` �?`children` 字段来自计数端点 �?视为违规
    - `grep "configApi\\.getVersion" frontend/src/` 同时 grep 不到 `aboutApi.get` �?视为违规
    - `const [, setXxx] = useState` 解构�?setter 但无 getter 使用 �?死代码信�?    - 新增 `aboutApi.get()` 调用未与既有 `configApi.getXxx()` `Promise.all` 并行 �?性能违规
  - **修复模式**�?    ```typescript
    // 禁止：getVersion() 实际返回 len(backups)，受 BACKUP_KEEP=10 上限永远卡在 10（永远显�?V10�?
    // �?正确：调用语义对齐的 /api/about 端点 + Promise.all 并行�?    const [buildInfo, setBuildInfo] = useState<BuildInfo | null>(null)
    const [backups, setBackups] = useState<BackupItem[]>([])

    useEffect(() => {
      // 并行化：aboutApi 提供版本�?+ configApi 提供备份数（语义分离�?      Promise.all([aboutApi.get(), configApi.listBackups()])
        .then(([info, bks]) => {
          setBuildInfo(info)
          setBackups(bks)
        })
        .catch(err => message.error(`加载失败: ${err.message}`))
    }, [])

    return (
      <>
        <Statistic title="version" value={`v${buildInfo?.version ?? 'unknown'}`} />
        <Statistic title="backups" value={backups.length} />
      </>
    )

    // �?死代码清理：发现 const [, setConfigVersion] = useState(0) �?set �?read �?删除
    ```
  - **配置参数**：`version_source_management` 节点（在 `config.yaml` 管理，不硬编码）�?    - `enabled`（默�?`true`，开关本检查）
    - `forbidden_version_endpoints`（默�?`["/api/config/version"]`，禁止当作版本号使用的端点列表）
    - `forbidden_placeholders`（默�?`["1.0", "0.0.0", "unknown version"]`，禁止作为版本号回退值的占位符）
    - `required_semantic_api`（默�?`"/api/about"`，版本号必须来自的语义对�?API�?    - `parallel_fetch_required`（默�?`true`，新增元数据 API 调用必须 Promise.all 并行化）
    - `dead_code_cleanup_required`（默�?`true`，修复时必须同步清理�?set �?read �?state�?  - **适用**：构建期元数据（版本�?构建时间/git_sha/构建主机）的前端显示；多端点读取同一元数据的场景；前�?版本管理"/"关于"/"系统信息"页面
  - **不适用**：业务数据计数（如备份数/任务�?商品数）；临时调试变量；跨服务边界元数据（应通过专门 API 同步）；核心依赖版本（如 React/AntD 版本，由 package.json 管理）；Pydantic 模型字段（由后端类型系统管理�?  - **历史教训**：版本管理菜单持续显�?"V10"。根因链路：前端 `VersionManager.tsx` 调用 `configApi.getVersion()` 拉取 `/api/config/version`，但该端点实际返�?`len(backups)`，受 `BACKUP_KEEP=10` 上限影响永远卡在 10；同时后�?`export_config` 中残留占位符 `"version": "1.0"`。修复：前端改用 `aboutApi.get()` �?`/api/about` 拿真�?`__version__`，`Promise.all` 并行化避免瀑布；后�?`_safe_app_version()` 辅助函数替代占位符；同步清理 Dashboard �?`const [, setConfigVersion] = useState(0)` 死代�?
- 🆕v4.22【强制�?*F-REVIEW-PWA-CACHE-VERIFY：PWA 缓存验证规范**
  - 维度�?3 PWA 配置
  - 检查项：前端功能不可见时必须从源码→构建产物→sw.js 预缓存清单三层验�?  - 强制要求�?    1. `vite-plugin-pwa` �?`registerType: 'prompt'` 模式检测到新版本仅弹通知不自动刷新，必须实现 `ReloadPrompt` 组件提示用户刷新
    2. 或改�?`registerType: 'autoUpdate'` 自动激活新版本（无需用户确认�?    3. 部署后必须验�?`sw.js` 预缓存清单包含新 chunk 文件名（�?`BatchRefresh-xxx.js`�?    4. 构建产物必须包含新功能标识（如中文文案「执行历史」），用 `Select-String` �?`grep` 验证
    5. 构建时间必须晚于源码修改时间，确保构建是最新的
    6. 用户反馈「看不到新功能」时，排查顺序：源码 �?构建产物 �?sw.js 预缓存清�?�?Service Worker 缓存 �?浏览器缓�?  - 配置节点：`pwa_cache_verify`（verify_layers / register_type / prompt_fallback_required / reload_prompt_component / build_time_check�?  - 适用场景：PWA 项目（vite-plugin-pwa/Workbox）部署后用户反馈「看不到新功能�?  - 不适用场景：无 PWA 的传统部署；htmx 服务端渲染；CSR �?Service Worker
  - 实战案例：批量采集执行历�?Tab2 已在源码和构建产物中正确实现，但用户看不到，原因�?PWA Service Worker 缓存了旧版本 JS 资源，registerType: 'prompt' 模式只弹通知不自动刷新，用户需手动 Ctrl+Shift+R 硬刷�?
- 🆕v4.25【强制�?*F-REVIEW-THREE-STATE-NULL-SEMANTICS：API 更新接口三态语义检�?*
  - 维度�? API 调用规范
  - 严重等级：warning
  - **检查点**：PATCH/PUT 请求是否正确处理 null 语义
  - **判定标准**：前端发送更新请求时�?*清除覆盖字段必须显式�?null（不能省略字段）**，更新字段必须传具体值�?*禁止**�?省略字段"代替"�?null"——后�?`exclude_unset=True` 会把省略字段视为"未提�?（保持原值），�?`null` 才是"显式清除覆盖"的语�?  - **检查范�?*：所�?`taskApi.update` / `configApi.update` �?PATCH/PUT 调用
  - **核心机制**（审查时必须理解）：
    - 后端 Pydantic + `exclude_unset=True` 模式下，请求体省略字�?= "未提�? = 保持原值；显式�?`null` = "显式清除覆盖"
    - 前端 `FormData`/payload 构造时，已勾�?恢复默认"�?清除覆盖"的字段必须显式赋 `null`，不能依赖字段省�?    - 后端配合使用 `Optional[T] = None` 但区�?未传"（保持原值）�?�?null"（清除），需�?`model_dump(exclude_unset=True)` 而非 `exclude_none=True`
  - **判断信号**（grep 检测）�?    - `grep -nE "delete formData\[" frontend/src/pages/**/*.tsx` 命中 �?检查是否应改为 `formData[x] = null`
    - `grep -nE "if \(value\) \{ formData\[` frontend/src/pages/**/*.tsx` 命中 �?检�?else 分支是否�?`formData[x] = null`
    - 用户反馈"清除覆盖不生效，覆盖值仍存在" �?必查前端是否省略字段而非�?null
  - **修复模式**�?    ```typescript
    // �?正确：清除覆盖字段显式传 null
    const payload: Partial<TaskConfig> = { search_config: null }  // 显式 null 清除覆盖
    await taskApi.update(taskId, payload)

    // 禁止：省略字段，后端 exclude_unset=True 视为"未提�?，覆盖不会被清除

    // 禁止：用 undefined 也会�?exclude_unset 过滤�?    ```
  - **配置参数**：`api_update_semantics` 节点（在 `config.yaml` 管理，不硬编码）�?    - `enabled`（默�?`true`，开关本检查）
    - `three_state_fields`（默�?`["search_config", "filter_config", "score_override", "notify_config"]`，必须显式传 null 才能清除覆盖的字段列表）
    - `clear_override_fields`（默�?`["search_config"]`�?清除覆盖"语义的字段列表）
    - `detection_signals`（默�?`["delete formData[", "omit field in PATCH", "undefined in PATCH payload"]`，触发检查的代码模式�?    - `forbidden_omit_fields`（默认同 `three_state_fields`，禁止在 PATCH 中省略的字段列表�?  - **适用场景**：所�?PATCH/PUT 接口的可选字段（任务级配置覆盖、用户偏好覆盖、商品级配置覆盖、批量配置覆盖）
  - **不适用场景**：POST 创建接口（所有字段都显式传，不存�?省略 = 保持原�?语义）；GET 查询接口（无写入语义）；DELETE 接口（无字段语义�?  - **历史教训**：任务级配置覆盖功能开发时，前�?FormData �?清除 search_config 覆盖"操作通过 `delete formData.search_config` 实现，导致后�?`exclude_unset=True` 把该字段视为"未提�?，覆盖未被清除，用户反馈"清除不生�?。修复方式：改为 `formData.search_config = null` 显式�?null，后端识�?null 后调�?`clear_override()` 清除覆盖
  - **对应后端原则**：后�?PATCH/PUT 接口必须�?`model_dump(exclude_unset=True)` 区分"未提�?�?显式 null"，禁止用 `exclude_none=True`（会吞掉 null 语义），详见 `xianyu-backend-code-review` v4.26.0 �?`B-REVIEW-EXCLUDE-UNSET-CHECK` / `B-REVIEW-NOT-NULL-NONE-DEFENSE`

### 8. 路由与懒加载 🆕v2.0

- 【强制】使�?`react-router-dom` 6.26+ + `BrowserRouter basename="/xianyu"`
- 【强制】约 26 条业务路由（`App.tsx`�?- 【强制】所有业务页面用 `lazy(() => lazyRetry(() => import('./pages/<�?')))` 懒加�?- 【强制】`lazyRetry` 包装 chunk 失败重试：`MAX_RETRIES=3`�?s/2s/4s 指数退�?- 【强制】独立路由（不进 MainLayout）：`/login`、`/onboarding`、`/help`、`/about`
- 【强制】双�?ErrorBoundary：`LazyErrorBoundary`（路由级�? 顶层 ErrorBoundary
- 【强制】路由切换用 `requestAnimationFrame` 重置滚动位置

### 9. SheetWorkspace 多页签系�?🆕v2.0

- 【强制】多页签系统位于 `frontend/src/components/SheetWorkspace/`�? 文件组织
- 【强制】`SheetPreferences` 字段�?  - `maxSheets`: [1, 10]
  - `enableAnimation`: boolean
  - `minimizeInsteadOfClose`: boolean
  - `doubleClickCloseEnabled`: boolean
  - `doubleClickInterval`: [200, 800]
  - `thumbnailMode`: boolean
  - `circularReplaceEnabled`: boolean
- 【强制】`activateSheet` 激活最小化 sheet 时必须同时恢复（`minimized: false`），否则 SheetContent 显示空状�?- 【强制】最小化标识�?恢复"提示文字�?`colorPrimary`（`activeColor`），禁止�?`colorBorder`
- 【强制】页面组件嵌�?SheetContent 时用 `height: 100%`，禁�?`minHeight: 100vh`

### 10. Hooks 设计模式 🆕v2.0

- 【强制】常量提取到模块级（SonarQube S2004）：`MIN_INTERVAL`、`MAX_INTERVAL`、`DEFAULT_INTERVAL`、`MAX_RETRIES`、`RETRY_BASE_MS`、`DEBOUNCE_MS`、`BACKGROUND_SLOWDOWN`
- 【强制】`ref` 持有最新闭包（避免 setInterval 陷阱）：`refreshRef`、`enabledRef`、`pausedRef`、`intervalRef`、`scheduleNextRef`
- 【强制】页面不可见降频：�?（`BACKGROUND_SLOWDOWN`�?- 【强制】防抖：300/400/500ms（按场景�?- 【强制】`requestId` 竞态保护：每次请求生成 requestId，丢弃过期响�?- 🆕v4.0【强制�?*搜索场景防抖间隔统一 400ms**（通过配置管理，非硬编码）
- 🆕v4.0【强制�?*搜索响应结构统一**：`{ items, total, page, page_size }`，参数命�?`keyword/q, page/offset, page_size/limit`
- 【强制】`mountedRef` 防止卸载�?setState
- 【强制】`refreshingRef` 并发保护
- 【强制】`async/await` �?`.then().catch()` 错误处理；禁止遗�?`this` 上下文绑�?- 【强制】每个异步请求有错误处理分支
- 【强制】提交按钮异步期间设 `loading`/`disabled` 防重复提�?- 【强制�?*测试环境准备**：antd 组件（Drawer/Grid/Skeleton）测试必�?mock `window.matchMedia`
- 【强制】vitest 测试命令必须�?`--no-isolate`（Node v24 + vitest 4.x worker 启动兼容性）
- 【强制】测试文件扩展名跟随被测文件：组件测试用 `.test.tsx`，Hook/纯逻辑�?`.test.ts`
- 【强制】全局事件监听（`visibilitychange`、`resize`、`scroll` 等）必须�?useEffect 中注册，并在 cleanup 中移�?- 【强制】`visibilitychange` 监听用于：页面不可见时暂停网络连接（SSE/WebSocket），恢复可见时自动重�?- 【推荐】useEffect 中同时管�?SSE 连接�?visibilitychange 监听，确保两者生命周期一�?- 🆕v4.7【强制�?*F-REVIEW-ASYNC-FEEDBACK：异步操作用户反馈三�?*
  - 前端异步操作（API 请求、文件上传、批量操作）必须实现 loading �?success �?error 三态用户反馈，**禁止** `.catch(() => {})` 静默吞错�?  - **判断信号**：`await fetch(...)` / `await axios(...)` / `useEffect` 中的异步操作 �?检查是否有 `message.loading` / `setLoading(true)` �?检查成功分支是否有 `message.success` �?检�?catch 分支是否�?`message.error` �?`notification.error`
  - **修复模式**（三态反馈标准模式）�?    ```typescript
    // �?标准三态反馈模�?    const hide = message.loading('正在采集评估明细...', 0)
    try {
      const result = await fetchEvaluationDetail(itemIds)
      hide()
      message.success(`采集完成，共 ${result.length} 条`)
      setData(result)
    } catch (err) {
      hide()
      message.error(err instanceof Error ? err.message : '采集失败，请稍后重试')
      // 错误状态必须显式设置，不能只靠 catch 不做�?      setError(err instanceof Error ? err.message : '未知错误')
    }
    ```
  - **禁止模式**�?    ```typescript
    // 禁止：静默吞错误

    // 禁止：只�?loading 没有 success/error 反馈
    ```
  - **配置参数**：`loading_duration`（loading 提示展示时长，默�?0 表示持续到手动关闭）、`success_auto_hide_ms`（成功提示自动关闭时长，默认 3000）、`error_auto_hide_ms`（错误提示自动关闭时长，默认 5000）、`feedback_components`（反馈组件映射，默认 `message`）在 `config.yaml` �?`async_feedback` 节点管理
  - **关键约束**�?    - loading 提示必须�?await 之前触发，在 finally �?success/error 分支中关�?    - 错误信息必须面向用户友好（避免堆栈跟踪、错误码直接展示�?    - 批量操作必须显示进度（如"3/10 完成"�?    - 网络错误与业务错误区分显示（网络错误提示"网络异常"，业务错误显示后端返回的 detail�?  - **适用**：所有前端异步操作（API 请求、文件上传、批量操作、长时间计算�?  - **不适用**：后台同步任务（�?SSE 心跳、定时轮询）、纯展示组件的初始数据加载（可用 Skeleton 占位�?  - **历史教训**：评估明细采集按钮点击后无任何反馈，用户不知道是否在执行；采集失败后页面无变化，用户反复点击导致多次请求。修复后改为 `message.loading` �?`message.success/error` 三态反�?- 🆕v4.9【强制�?*F-REVIEW-FREQ-STATS-POLLING：累计统计类 API 定时刷新**
  - 累计统计�?API（频率伪装统�?/ 采样�?/ 计数�?/ 令牌�?/ 健康评分 �?内部状态持续累�?的接口）必须在前端页面通过 `setInterval` **定时刷新**�?*禁止**只依�?页面加载时拉一�?。定时器间隔、清理策略、失败兜底必须在 `config.yaml` �?`freq_stats_polling` 节点管理，不硬编�?  - **核心机制**（审查时必须理解）：
    - 业务模块（collector / buyer / notifier 等）持续调用后端核心模块（如 `FreqDisguise.record_request`）累加统�?    - 前端 `useEffect` 初始化时�?`fetch` 一�?�?拿到的是某个时刻的快�?    - 用户停留在页面期间，后端统计持续累加�?UI 永远停留在初始值（甚至永远�?0�?    - 表现：用户反�?统计数据持续�?0 且无变化"，但后端 API 与业务调用方均正�?  - **判断信号**�?    - `grep "loadFreqStats\|loadStats\|fetchStats" <page>.tsx` 发现页面有加载函�?    - `grep "setInterval" <page>.tsx` **没有**对应�?`setInterval` 定时�?    - 累计统计�?API 名称�?`stats` / `metrics` / `count` / `health_score` / `token_bucket` 等关键词
    - 后端核心模块（如 `FreqDisguise` / `MetricsCollector` / `Sampler`）有 `_total_count` / `_history` 等内部状�?  - **修复模式**（在页面 useEffect 中加 `setInterval` + 清理）：
    ```typescript
    useEffect(() => {
      loadAll()
      // 频率伪装统计定时刷新：业务模块持续调�?apply_freq_delay/record_freq_request�?      // 前端需定时拉取才能反映最新请求节�?      const freqInterval = setInterval(() => {
        loadFreqStats()
      }, POLL_INTERVALS.freqStats)  // 10000ms 来自 config.yaml
      return () => {
        clearInterval(freqInterval)  // 卸载时必须清�?      }
    }, [loadAll])
    ```
  - **关键约束**�?    - **必须清理定时�?*：`useEffect` cleanup �?`clearInterval`，避免组件卸载后定时器仍触发 `setState`（内存泄�?+ 警告�?    - **间隔配置�?*：`10000` / `30000` 等间隔值必须来�?`config.yaml` �?`freq_stats_polling.interval_ms` �?`POLL_INTERVALS` 常量，禁止在组件内硬编码数字
    - **轮询失败静默**：累计统计轮询失败应 `console.error` 而非 `message.error`（避免用户被频繁弹窗骚扰�?    - **可独立刷�?*：每个累计统�?API 可独立设�?`setInterval`，无需等待 `loadAll()`
  - **配置参数**：`enabled`（默�?`true`）、`interval_ms`（默�?`10000`）、`slow_interval_ms`（变化缓慢的统计�?Cookie 层，默认 `30000`）、`fail_silent`（轮询失败是否仅 console 不弹错，默认 `true`）、`applicable_pages`（适用页面列表�?`AntiCrawl` / `Dashboard`）、`exempt_apis`（豁免的 API 列表如已�?SSE 推送的接口）在 `config.yaml` �?`freq_stats_polling` 节点管理
  - **诊断流程**（用户反�?统计数据持续�?0 且无变化"时执行）�?    1. 定位页面对应�?`loadXxx` 函数 �?检查页�?useEffect 是否调用�?`loadAll()` 初始�?    2. `grep "setInterval" <page>.tsx` 检查是否有定时刷新
    3. 若无 �?判定为孤岛（前端未轮询）�?按修复模式增�?`setInterval`
    4. 验证后端 API 端点是否被业务模块持续调用（`grep "apply_freq_delay\|record_request"` 后端�?    5. 三层验证：API 端点存在 �?+ 业务模块调用 �?+ 前端轮询 �?�?数据应开始累�?  - **适用**�?    - 反爬登录管理页面的频率伪装统计（业务模块持续调用 `apply_freq_delay` / `record_request`�?    - Dashboard 的实时统计（任务�?/ 评估�?/ 订单数等持续累加指标�?    - 健康检查页面的健康评分（持续变化）
    - 任何后端�?内部状态持续累�?特征�?API
  - **不适用**�?    - 纯客户端状态（localStorage 独占，无后端状态）
    - 只读快照类统计（后端一次性生成数据，无需轮询，如日报表）
    - Chart 库内置轮询（echarts / recharts 已有 setInterval 机制�?    - 已有 SSE 推送的实时数据流（避免�?SSE 重复�?  - **历史教训**：`AntiCrawl` 页面�?`loadFreqStats` 仅在 `useEffect` 初始化时调用一次，**没有 `setInterval` 定时刷新**。后�?`FreqDisguise.record_request` �?collector/buyer 持续调用累加统计正确，但前端 UI 永远显示初始值（0）。用户反�?频率伪装统计持续�?0 且无变化"持续数天。修复后�?`useEffect` 中加 `setInterval(loadFreqStats, 10000)` + cleanup `clearInterval`，数据立即开始正常累�?
- 🆕v4.12【强制�?*F-REVIEW-ASYNC-CONFIG-LOAD：异步配置加载与竞态保�?*
  - 使用 `usePersistentState` �?localStorage 持久�?hook 时，若初始值需从异�?API（如 `configApi.get()`）加载，必须实现双重检查防止竞态：第一次检�?localStorage 是否已有用户偏好，第二次检查在 API 返回后再次确�?localStorage 未被 usePersistentState 防抖写入抢先
  - **核心机制**（审查时必须理解）：
    - `usePersistentState` 同步初始化无法等待异�?API
    - 用户偏好优先�?> 全局配置默认值，不能直接覆盖已有用户偏好
    - 组件卸载�?API 返回仍调 setState 会触�?React 警告（Can't perform a React state update on an unmounted component�?  - **判断信号**�?    - 代码�?`configApi.get().then(cfg => setXxx(cfg.xxx))` 模式 �?必须�?cancelled 标志和双重检�?    - `useEffect` 依赖数组�?`[]` 但调用了异步 API + setState �?必须实现清理函数 `return () => { cancelled = true }`
    - 代码�?`if (localStorage.getItem(KEY) !== null) return` 短路 �?必须�?API then 回调中再次检�?  - **修复模式**�?    ```typescript
    // �?双重检�?+ cancelled 标志
    const [autoSearchEnabled, setAutoSearchEnabled] = usePersistentState<boolean>(
      'xh.tasks.autoSearchEnabled',
      false,
    )

    useEffect(() => {
      // 第一次检查：localStorage 已有值（用户偏好优先），不覆�?      if (localStorage.getItem('xh.tasks.autoSearchEnabled') !== null) return
      let cancelled = false
      configApi.get()
        .then(cfg => {
          if (cancelled) return
          // 第二次检查：防止 usePersistentState 防抖写入抢先
          if (localStorage.getItem('xh.tasks.autoSearchEnabled') !== null) return
          setAutoSearchEnabled(cfg.task_scheduler?.auto_search_enabled ?? false)
        })
        .catch(() => { /* config 加载失败保持默认 false */ })
      return () => { cancelled = true }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
    ```
  - **配置参数**：`async_config_load.required_double_check`（默�?`true`，必须双重检�?localStorage）、`async_config_load.required_cancelled_flag`（默�?`true`，必须有 cancelled 标志）、`async_config_load.user_preference_priority`（默�?`true`，用户偏好优先于全局配置）、`async_config_load.fallback_default_value`（默�?`false`，config 加载失败时的兜底值）�?`config.yaml` �?`async_config_load` 节点管理
  - **适用**：所有从异步 API 加载初始值的 usePersistentState/useState 场景；用户偏好与全局配置合并的场�?  - **不适用**：纯同步初始值（直接 useState(initialValue)）；非持久化�?useState；无异步 API 调用的场�?  - **历史教训**：`usePersistentState('xh.tasks.autoSearchEnabled', false)` 直接�?false 初始化，然后 useEffect 异步加载 configApi.get() 设置默认值，但用户已手动关闭开关（localStorage �?false 值）时被 API 返回�?true 覆盖，导致用户偏好丢�?
- 🆕v4.16【强制�?*F-REVIEW-ASYNC-RACE-CONDITION：长耗时异步请求 race condition 防护**
  - **判断信号**：`client.post` / `client.get` 调用�?`timeout >= 3000` 参数；或调用方为 LLM/批量类（`aiApi.deepAnalyze` / `aiApi.evaluateCondition` / `evalApi.batchEvaluate`）；用户可触发多次切换商�?任务/对象�?Modal 内异步或列表行按钮异�?  - **强制规则**：任�?> 3s 的异步请求必须用 `useRef` 跟踪最新请�?ID；旧请求�?result/error/loading 三态在 setState 前必须校�?`ref.current === itemId`，不匹配则丢弃；finally 块同样校验，避免提前关闭新请求的 loading
  - **代码模板**�?    ```typescript
    const itemIdRef = useRef('')
    const onXxx = async (itemId: string) => {
      itemIdRef.current = itemId
      setLoading(true); setResult(null)
      try {
        const result = await api.fetch(itemId)
        if (itemIdRef.current !== itemId) return  // 丢弃过期结果
        setResult(result)
      } catch (err) {
        if (itemIdRef.current !== itemId) return  // 丢弃过期错误
        handleError(err)
      } finally {
        if (itemIdRef.current === itemId) setLoading(false)  // 仅最新请求结�?loading
      }
    }
    ```
  - **配置参数**：`async_race_condition` 节点（enabled / threshold_ms / detect_patterns / abort_controller_preferred�?  - **适用场景**：timeout >= 3s 的异步请�?+ 用户可触发多次切换商�?任务/对象
  - **不适用场景**：同步请求（< 1s）；一次性请求（页面加载）；用户无法重复触发（如表单提交后禁用按钮）；请求顺序由用户显式控制（如分页加载�?  - 注：`AbortController` 是更优解但需后端支持取消；`useRef` 方案是通用轻量�?- 🆕v4.24【强制�?*F-REVIEW-UI-PREFERENCE-PERSISTENCE：用户偏好类 UI 状态持久化强制复用 usePersistentState**
  - 用户偏好�?UI 状态（自动刷新开关、视图模式、列显隐、折�?展开状态、主题偏好、最近使用列表、记住上次选中项等）必须使用项目既�?`frontend/src/hooks/usePersistentState.ts` 持久化，**禁止**�?`useState` 存储（判别信号：刷新页面/路由切换后状态丢失即违规）�?*禁止**各组件自行实�?`localStorage.getItem/setItem` 逻辑�?*禁止**引入第三方持久化�?  - **核心机制**（审查时必须理解）：
    - 项目已有统一封装�?`usePersistentState` hook（位�?`frontend/src/hooks/usePersistentState.ts`），内置防抖写入、数据验证、localStorage 不可用回退到内�?Map
    - 业务方未使用既有 hook 而裸 `useState` 会导致用户偏好类状态在页面刷新/路由切换后丢�?    - 各组件自行实�?localStorage 读写会导致错误处理不一致、key 命名混乱、无防抖、无内存回退
    - 已通过后端 API 持久化的字段（如批量采集�?`enabled` / `interval_minutes`）不得再�?`usePersistentState` 重复持久化，否则前后端不一�?  - **判断信号**（grep 检测）�?    - `grep -E "const\s+\[\s*(autoRefresh|viewMode|columnConfig|density|collapsed|expandedKeys|themePreference|recentItems|rememberLast)\s*,\s*\w+\]\s*=\s*useState" frontend/src/pages/**/*.tsx` 命中 �?违规
    - `grep "localStorage.getItem\|localStorage.setItem" frontend/src/pages/**/*.tsx` 命中 �?检查是否应改用 `usePersistentState`
    - 用户反馈"刷新页面后开�?设置丢失"�?每次进入页面都需要重新设�? �?必查
  - **修复模式**（用 usePersistentState 替换 useState）：
    ```typescript
    // �?正确：使�?usePersistentState + key 命名规范 + validator
    import { usePersistentState } from '../../hooks/usePersistentState'
    
    const [autoRefresh, setAutoRefresh] = usePersistentState<boolean>(
      'xh.batchRefresh.autoRefresh',  // key 遵循 xh.<page>.<field> 命名
      false,
      { validator: (v): v is boolean => typeof v === 'boolean' },  // validator 必填防脏数据
    )
    
    // 禁止：裸 useState，刷新页面后状态丢�?
    // 禁止：自行实�?localStorage 读写
    ```
  - **状态分类识�?*（新�?state 时必须先识别归属类别）：
    | 类别 | 持久化方�?| 示例 |
    |---|---|---|
    | 用户偏好�?| `usePersistentState` | 自动刷新、视图模式、列显隐、折�?展开、主题偏好、最近使用列�?|
    | 业务数据�?| 后端 API | 任务列表、订单状态、配置项（已通过后端持久化） |
    | 会话状态类 | Zustand store | 登录态、当前选中项、跨页共享状�?|
    | 临时状态类 | `useState` | loading、modal open、按�?submitting、表�?dirty |
    | 敏感数据�?| secure storage / httpOnly cookie | token、密码、API key |
  - **配置参数**：`ui_preference_persistence` 节点（enabled / preference_keywords / required_hook / prefer_state_storage_patterns / skip_scenarios / require_validator / require_key_naming / require_memory_fallback / detection_signals�?  - **关键约束**�?    - localStorage key 必须遵循 `xh.<page>.<field>` 命名模式
    - validator 必填，防�?localStorage 脏数据（旧版本数�?用户手动修改/其他项目同名 key）导�?UI 异常
    - 不重复持久化后端已通过 PATCH /config 持久化的字段（避免前后端不一致）
    - localStorage 不可用（隐私模式/存储已满/被禁用）时依�?hook 内置的内存回退机制，业务代码不�?try-catch
  - **适用**：用户偏好类 UI 状态（开关类、视图模式、列显隐、折�?展开、主题偏好、最近使用列表、记住上次选中项）；跨会话需要保留的 UI 偏好
  - **不适用**：业务数据（必须走后�?API）；会话状态（必须�?Zustand store）；临时状态如 loading/modal open（必须用 useState）；敏感数据（必须走 secure storage）；已通过后端持久化的字段（不重复持久化）
  - **历史教训**：`Maintenance/BatchRefresh.tsx` 的「自动刷新」开关使�?`useState(false)`，每次刷新页面或重新进入页面开关重置为关闭，用户需要反复手动开启。修复方式：替换�?`usePersistentState<boolean>('xh.batchRefresh.autoRefresh', false, { validator: ... })`，复用项目既�?`hooks/usePersistentState.ts`（含防抖写入、数据验证、localStorage 不可用回退到内�?Map）。本次同时验证「启用批量采集」与「触发间隔」字段已通过后端 `PATCH /api/batch-refresh/config` 持久化，无需重复持久化�?  - **对应后端原则**：若后端提供用户偏好 API（如 `/api/user/preferences`），同样必须复用同一持久化策略与配置驱动，不硬编码（详见 `xianyu-backend-code-review` v4.24.0 复盘记录同步原则�?
### 11. 类型安全评审

- 【强制】前后端字段类型一致性（�?`is_sold?: boolean` 与后�?`bool(raw_sold)` 匹配�?- 【强制】可选链使用（`?.`）处理可能缺失的字段
- 【强制】联合类型和 `Exclude`/`Omit` 等高级类型的使用
- 【强制】避�?`any` 类型（必要时�?`unknown` + 类型守卫�?- 【强制】`as` 断言的合理性（是否有更安全的类型收窄方式）
- 【强制】TypeScript 严格模式合规（`strictNullChecks` 等）
- 🆕v4.0【强制�?*IIFE 反模式禁�?*：JSX 内禁�?`{(() => { ... })()}`，提取为组件顶部变量
  - �?`const apiKeyUrl = getApiKeyUrl(config.base_url)` �?JSX: `{apiKeyUrl ? <Link/> : null}`
  - �?`{(() => { const url = getApiKeyUrl(config.base_url); return url ? <Link/> : null })()}`
- 🆕v4.0【强制�?*动态资源映射分�?*：映射表（`Record<string, string>`）与推断函数分离，不混合
  - 推断函数返回 `null` 表示无匹配，调用方条件渲�?  - 业务参数（URL、阈值）通过配置文件管理，不硬编�?- 🆕v4.4【强制�?*F-REVIEW-CONFIG-DRIVEN-TOGGLE：配置驱动功能开关模�?*
  - 高风�?高资源消耗的前端功能（如自动同步开关、CDP 调试触发按钮、批量操作）必须配置驱动，参数集中在 `constants.ts` �?config 文件管理（不硬编码），默认关闭需用户显式启用
  - **判断信号**：功能需用户主动选择 + 可能耗资源（CPU/内存/网络�?+ 多环境部署需�?+ 涉及浏览�?系统资源调用
  - **修复模式**：`constants.ts` 定义 `FEATURE_TOGGLES` 映射�?+ 默认�?`false` �?组件通过 `useFeatureToggle(name)` Hook 读取 �?设置页提�?Switch 开�?+ 资源消耗提示文�?  - **配置参数**：`enable_flag` 默认 `false`，详细参数（interval/threshold/port）集中在 `constants.ts` �?`FEATURE_CONFIGS` 节点
  - **适用**：CDP 在线导入触发、Cookie 自动同步开关、向量库重建触发、批量导出等高风�?高资源消耗功�?  - **不适用**：核心功能（必须默认启用）、性能敏感场景（配置加载延迟不可接受）、简单展示组�?  - **历史教训**：`auto_sync` 默认关闭避免用户不知情下启用自动同步导致浏览器资源被占用；前端触�?CDP 导入的按钮应明确提示"需启动 Edge 调试模式"并默�?disabled，需用户先勾�?我已了解"再启�?- 🆕v4.5【强制�?*F-REVIEW-ERROR-SEMANTICS：错误提示语义准确�?*
  - 前端错误提示文案必须与后端错误根因语义匹配，**禁止**将特定错误（�?token 过期）显示为不相关的语义（如"登录已过�?�?  - **判断信号**：前�?catch 块中根据 HTTP 状态码或错误消息关键词显示提示文案时，文案语义必须与后端错误根因一�?  - **修复模式**：后端错误码根因分析 �?前端按语义分类显示提示（"稍后重试" vs "重新登录"）→ Alert 类型匹配严重性（warning 而非 error）→ 按钮紧迫性匹配操作出�?  - **通过示例**�?    ```typescript
    // RGV587 = mtop API 临时 token 过期，不是登录态失�?    if (detail.includes('令牌临时过期')) {
      setSessionExpired(true)  // 显示"稍后重试"提示，非"重新登录"
    }
    ```
  - **不通过示例**�?    ```typescript
    // RGV587 被映射为 401，前端显�?登录已过�?
    if (status === 401 || detail.includes('登录已过�?)) {
      setSessionExpired(true)  // 误导用户重新登录
    }
    ```
  - **适用**：所有前端错误提示（Alert、message、notification�?  - **不适用**：开发环境调试信�?  - **历史教训**：后端将 RGV587（mtop API 临时 token 过期，TTL 1 小时）映射为 HTTP 401("闲鱼登录已过�?)，前端捕�?401 后显示红�?Alert"Cookie 失效或会话过�?。但用户多查几次能成功——说明不是登录态失效。修复后改为橙色 warning"搜索令牌临时过期，请稍后重试"
- 🆕v4.7【强制�?*F-REVIEW-DATA-FLOW-TRACE-FRONTEND：字段为�?5 点追踪（前端侧）**
  - 前端"字段为空/显示异常"类问题必须配合后端按 5 点逐层追踪，前端侧负责验证 types 声明 + render 取值两点，**禁止**仅查前端单层就下结论"前端 bug"
  - **判断信号**：用户反�?字段显示�?'�?/undefined" �?前端 grep 字段名在 `types.ts` 是否声明 �?grep �?`render` 是否正确取�?�?若前端正常则定位为后端问题（配合后端 B-REVIEW-DATA-FLOW-TRACE 追踪 DB/Repo/API 三点�?  - **修复模式**（前端侧 5 点追踪流程）�?    ```typescript
    // 1. types.ts 中字段声�?    interface Order {
      order_id: string          // �?字段已声�?      status: string
      price: number | null      // �?可空字段�?| null
    }
    // 2. render 中取�?    const order = orders.find(o => o.item_id === itemId)
    // 禁止：orders 为空数组时显�?"�?
    // �?正确：先检�?orders 是否加载完成
    {orders.length === 0 ? <Empty /> : <Table data={orders} />}
    // 禁止：order.status �?Repo 层过滤掉（前端无法发现，需配合后端追踪�?    ```
  - **配置参数**：`trace_nodes_frontend`（前端负责的追踪节点：`frontend_types` + `render`）、`required_fields`（必查字段列表）、`null_value_patterns`（空值渲染模式，�?`field || '�?` / `field ?? '暂无'`）在 `config.yaml` �?`data_flow_trace_frontend` 节点管理
  - **关键约束**�?    - 前端发现字段为空时，必须先确认前�?types + render 两点正常，再定位为后端问�?    - 可空字段必须�?`| null` 显式声明，禁止用 `any` 或省略类�?    - 渲染时必须区�?数据加载�?�?数据为空"�?字段缺失"三种状�?    - 前端 grep 字段名在 `types.ts` �?`render` 都正�?�?必须反馈后端排查 DB/Repo/API 三点
  - **适用**：用户反�?字段为空/显示异常/数据丢失"的所有场�?  - **不适用**：前端布局问题（非数据问题）、样式渲染问题、权限问题（用户看不到数据）
  - **历史教训**：评估明细页订单字段显示 "�?，前端排�?types 声明正常、render 取值正常，最终定位为后端 Repo �?`list_orders_by_item_ids` 一刀切过�?`if status == 'failed': continue`。前端侧已正常，根因在后�?
- 🆕v4.12【强制�?*F-REVIEW-XSS-ESCAPE：用户输入字�?HTML 转义**
  - 后端返回的用户输入字段（�?task.source、item.title、user.nickname）在展示时必须经�?HTML 转义�?*禁止**直接渲染�?DOM（即�?JSX 默认转义，仍需双重保护防止 dangerouslySetInnerHTML 误用�?  - **核心机制**（审查时必须理解）：
    - React JSX 默认�?`{value}` 进行 HTML 转义，但以下场景不转义：`dangerouslySetInnerHTML`、`<a href={value}>`（javascript: 协议）、`<iframe src={value}>`、动态属性名
    - 后端字段可能�?`<script>` / `<img onerror=>` / `javascript:` �?XSS 载荷
    - 双重保护：escapeHtml 函数（转�?< > & " '�? React JSX 默认转义，确保任意一层失效仍有保�?  - **判断信号**�?    - 后端返回字段直接渲染�?`dangerouslySetInnerHTML` �?视为违规
    - 后端返回字段直接渲染�?`<a href={value}>` 且未校验协议 �?视为违规
    - 后端返回字段�?source/title/nickname/name 等用户可编辑字段 �?必须经过 escapeHtml
    - 代码�?`dangerouslySetInnerHTML={{ __html: backendField }}` �?CRITICAL 违规
  - **修复模式**�?    ```typescript
    // �?escapeHtml 函数 + SafeSourceTag 组件双重保护
    function escapeHtml(str: string): string {
      return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
    }

    function SafeSourceTag({ source }: { source: string }) {
      // 第一层保护：escapeHtml 转义特殊字符
      const safeSource = escapeHtml(source)
      // 第二层保护：JSX 默认转义（即�?escapeHtml 失效，JSX 仍会转义�?      return <Tag>{safeSource}</Tag>
    }

    // 禁止：后端字段直接渲染到 dangerouslySetInnerHTML

    // 禁止：后端字段直接渲染到 a href 未校验协议（item.url 可能�?javascript:alert(1)�?
    // �?a href 必须校验协议
    function isSafeUrl(url: string): boolean {
      return /^https?:\/\//i.test(url)
    }
    {isSafeUrl(item.url) && <a href={item.url}>链接</a>}
    ```
  - **配置参数**：`xss_escape.required_for_fields`（必须转义的字段名列表，�?`["source", "title", "nickname", "description", "name"]`）、`xss_escape.forbidden_directives`（禁止的指令列表，如 `["dangerouslySetInnerHTML"]`）、`xss_escape.url_protocol_whitelist`（URL 协议白名单，�?`["http:", "https:"]`）、`xss_escape.double_protection`（默�?`true`，必须双重保护）�?`config.yaml` �?`xss_escape` 节点管理
  - **适用**：所有后端返回字段的渲染；用户可编辑字段（source/title/nickname/description）；URL 字段（href/src�?  - **不适用**：纯前端硬编码字符串（如 'Hello World'）；数字/布尔类型字段（无 XSS 风险）；React 组件内部状态字�?  - **历史教训**：`TaskContentMenu` 直接渲染后端返回�?`task.source` 字段�?`<Tag>{source}</Tag>`，虽�?JSX 默认转义，但若用户切换到 `dangerouslySetInnerHTML` 渲染模式则会�?XSS 攻击。修复后增加 `escapeHtml` 函数 + `SafeSourceTag` 组件双重保护
- 🆕v4.13【强制�?*F-REVIEW-ERROR-CONTRACT-TIMEOUT：前后端错误码契约与超时识别**
  - 前端调用后端含重�?异步逻辑的接口时，必须用模块�?`statusMessages: Record<number, string>` 映射�?+ 独立 `isAxiosTimeout()` 函数双路识别错误，axios 超时�?`response.status` 必须�?`error.code === 'ECONNABORTED'` �?`/timeout/i.test(error.message)` 识别�?*禁止**所有错误走同一通用文案导致用户无法区分"网络超时"�?商品下架"
  - **核心机制**（审查时必须理解）：
    - axios 超时�?`response.status`（请求未到达后端或后端未响应），必须通过 `error.code` �?`error.message` 识别
    - 后端按语义区分的状态码�?01/403/410/440/441/502/503）必须在前端映射表中有对应文�?    - 超时识别优先�?status 映射（因超时�?status�?  - **判断信号**�?    - 前端 catch 块含 `err.response?.status` 但无超时识别逻辑 �?视为违规
    - 前端 `message.error('xxx 失败，请稍后重试')` 出现在多�?catch �?�?必须按状态码差异化文�?    - 模块内无独立 `isAxiosTimeout` 函数 �?视为违规
    - 错误消息映射表硬编码�?catch 块内 �?必须提取为模块级常量
  - **修复模式**�?    ```typescript
    // �?模块级常�?+ 模块级函�?+ 统一错误提示
    const COLLECT_OFFICIAL_ERROR_MESSAGES: Record<number, string> = {
      503: '官方采集需要浏览器实例，请�?XH_WITH_SCHEDULER=1 模式启动',
      403: '闲鱼登录已过期，请重新登录闲�?,
      440: '闲鱼登录已过期，请重新登录闲�?,
      441: '触发闲鱼反爬限制，请稍后重试或手动完成验�?,
      410: '商品详情页加载失败或已下架，请稍后重�?,
      502: '浏览器连接异常，请重启服务后重试',
    }
    const COLLECT_OFFICIAL_TIMEOUT_MESSAGE = '官方采集超时（详情页+卖家主页加载缓慢），请稍后重试或检查网�?
    const COLLECT_OFFICIAL_FALLBACK_MESSAGE = '官方采集失败，请稍后重试'

    const isAxiosTimeout = (error: { code?: string; message?: string }): boolean =>
      error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')

    function showStatusError(err: unknown, statusMessages: Record<number, string>,
                             timeoutMessage: string, fallbackMessage: string): void {
      const error = err as { response?: { status?: number; data?: { detail?: string } }; code?: string; message?: string }
      if (isAxiosTimeout(error)) {
        message.error(timeoutMessage)  // 超时优先
      } else if (error?.response?.status != null && statusMessages[error.response.status]) {
        message.error(error?.response?.data?.detail || statusMessages[error.response.status])
      } else {
        message.error(error?.response?.data?.detail || fallbackMessage)
      }
    }

    // 禁止：所有错误走同一通用文案

    // 禁止：无超时识别（axios 超时�?response.status�?    ```
  - **配置参数**：`frontend_error_contract.timeout_codes`（默�?`['ECONNABORTED']`，axios 超时 code 列表）、`frontend_error_contract.timeout_patterns`（默�?`['/timeout/i']`，超�?message 正则模式列表）、`frontend_error_contract.status_message_map`（场景到消息映射，按业务接口分组，如 `collect_official: { 410: '...', 441: '...' }`）、`frontend_error_contract.timeout_priority`（默�?`true`，超时识别优先于 status 映射）在 `config.yaml` �?`frontend_error_contract` 节点管理
  - **适用**：含重试逻辑�?SSE/HTTP 接口、依赖多�?Cookie 的接口、含状态机的业务接口、浏览器自动化接�?  - **不适用**：一次性请求无重试逻辑、纯 token 认证（JWT 无超时概念）、内�?API（无业务文案需求）
  - **历史教训**：用户反�?官方采集失败，请稍后重试"，理论推断为 axios 30s 超时，实际日志显示采集只�?12s，根因是后端选择器失效返�?502，前端无超时识别导致无法区分"超时"�?502"
- 🆕v4.13【强制�?*F-REVIEW-RETRY-BACKOFF：前端可重试错误集与退避策�?*
  - 前端调用后端接口必须区分「可重试错误」（410/441/502/timeout）与「需用户介入错误」（403/440/503），可重试错误用指数/固定退避重�?N 次（默认 N=1），重试时不弹消息避免打扰用户，**禁止**对所有错误一刀切重试导致需用户介入的错误被无意义重�?  - **核心机制**（审查时必须理解）：
    - 可重试错误：临时性故障（410 页面未加�?441 反爬触发/502 连接异常/timeout 超时�?    - 需用户介入错误�?03 权限不足/440 Cookie 过期/503 服务未启动，重试无意�?    - 重试时不弹消息：避免偶发失败打扰用户，仅在最终失败时展示错误
    - 退避时间按错误类型差异化：441 反爬需 3s 冷却�?10/502 快速重�?1s
  - **判断信号**�?    - 前端 catch 块直�?`throw` 或直�?`message.error` �?必须评估错误是否可重�?    - 前端 `retry_count` �?`MAX_RETRIES` 硬编码数�?�?必须移到配置或模块级常量
    - 前端对所有错误都重试 �?必须区分可重试与不可重试
    - 前端重试时弹消息 �?应改为静默重试（仅在最终失败时展示�?  - **修复模式**�?    ```typescript
    // �?可重试错误集 + 退避时间映�?+ 重试不弹消息
    const RETRYABLE_STATUSES = new Set([410, 441, 502])
    const RETRY_DELAYS: Record<string, number> = {
      '410': 1000,   // 页面未加载，快速重�?      '441': 3000,   // 反爬触发，需 3s 冷却
      '502': 1000,   // 连接异常，快速重�?      'timeout': 2000,  // 超时�?s 后重�?    }

    async function collectOfficialWithRetry(itemId: string, taskId?: string): Promise<OfficialCollectResult> {
      const MAX_RETRIES = 1
      let lastErr: unknown
      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
          return await evalApi.collectOfficial(itemId, taskId)
        } catch (err: unknown) {
          lastErr = err
          if (attempt >= MAX_RETRIES) break
          const e = err as { response?: { status?: number }; code?: string; message?: string }
          const status = e?.response?.status
          const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(e?.message || '')
          const retryable = isTimeout || (status !== undefined && RETRYABLE_STATUSES.has(status))
          if (!retryable) break  // 不可重试错误直接抛出
          const delayKey = isTimeout ? 'timeout' : String(status)
          const delay = RETRY_DELAYS[delayKey] ?? 2000
          await new Promise(resolve => setTimeout(resolve, delay))
          // 重试时不弹消息，避免打扰用户（仅在最终失败时展示错误�?        }
      }
      throw lastErr
    }

    // 禁止：对所有错误一刀切重�?
    // 禁止：重试时弹消息打扰用�?    ```
  - **配置参数**：`frontend_retry_strategy.retryable_statuses`（默�?`[410, 441, 502]`，可重试状态码列表）、`frontend_retry_strategy.retry_delays_ms`（默�?`{410: 1000, 441: 3000, 502: 1000, timeout: 2000}`，状态码到退避时间映射）、`frontend_retry_strategy.max_retries`（默�?`1`，最大重试次数）、`frontend_retry_strategy.non_retryable_statuses`（默�?`[403, 440, 503]`，需用户介入的错误列表）、`frontend_retry_strategy.silent_on_retry`（默�?`true`，重试时不弹消息）在 `config.yaml` �?`frontend_retry_strategy` 节点管理
  - **适用**：网络请求（axios/fetch）、临时性错误（410/441/502/timeout）、浏览器自动化接�?  - **不适用**：需用户介入的错误（403 权限不足/440 Cookie 过期/503 服务未启动）、不可重试业务错误（404 资源不存在）、事务性操作（POST/PUT/DELETE 需幂等性保证）
  - **历史教训**：前端对所有错误直�?`message.error`，用户被偶发�?441 反爬�?502 连接异常打扰，需用户手动重试；改为仅对可重试错误自动重试 1 次后�?5% 的偶发失败用户无感知
- 🆕v4.14【强制�?*F-REVIEW-FILTER-BACKEND-ALIGN：前端过滤与后端分类对齐**
  - 实现前端过滤功能前必须先 grep 后端 `insufficient_count`/`marginals`/`result` 确认分类互斥性，前端过滤条件必须与后端分类逻辑对齐，过滤后各分类数量之和等于总数�?*禁止**前端自定义分类逻辑导致与后端统计不一�?  - **维度**�? API 调用规范
  - **核心机制**（审查时必须理解）：
    - 后端分类是互斥的（每条记录只属于一个分类），前端过滤条件必须与后端分类逻辑 1:1 对齐
    - 过滤后各分类数量之和必须等于总数（互斥性验证），否则说明前端过滤逻辑有误
    - 阈值参数（autoBuyScore/passScore）必须从 config 读取，禁止硬编码
  - **判断信号**�?    - 前端�?filterStatus 状态但�?grep 后端分类逻辑 �?视为违规
    - 前端过滤后各分类数量之和 �?总数 �?视为违规（分类不互斥或过滤逻辑错误�?    - 前端硬编码阈值数字（�?80/60�?�?必须移到配置
  - **示例**：评估明细统计卡片过滤，前端 filterStatus 过滤逻辑必须与后�?`api_evaluations.py` �?`dist.marginals.result` 分类一致（`score==null→insufficient`，`score>=autoBuyScore→auto`，`passScore<=score<autoBuyScore→pass`，`score<passScore→fail`�?  - **适用**：统计卡片过滤、Tab 分类过滤、状态分组过�?  - **不适用**：纯前端搜索过滤（无后端分类对应）、非互斥分类
  - **配置驱动**：阈值参数从 config 读取，分类映射表�?`config.yaml` �?`filter_backend_align` 节点管理
  - **历史教训**：评估明细页统计卡片点击过滤后，前端 filterStatus 分类逻辑与后�?`dist.marginals.result` 不一致，导致过滤后数量与统计卡片显示数量不匹�?- 🆕v4.14【强制�?*F-REVIEW-FILTER-PAGINATION-ADAPT：前端过滤后分页参数适配**
  - 添加 filterStatus 状态后必须同步调整 pagination �?total/current/pageSize 三参数，**禁止**过滤后仍用原 total/items 导致分页错乱或数据截�?  - **维度**�?0 Hooks 设计模式
  - **核心机制**（审查时必须理解）：
    - `total=filteredItems.length`：分页总数基于过滤后的数据�?    - `current=1`：切换过滤条件时重置到第一页，不触发后�?reload（前端过滤已加载数据�?    - `pageSize=filteredItems.length||1`：全量显示避免截断（过滤后数据量通常较少�?  - **判断信号**�?    - 前端�?filterStatus �?pagination 仍用�?items.length �?视为违规
    - 切换 filterStatus �?current 不重�?�?视为违规（可能指向不存在的页�?    - 过滤�?pageSize 仍用原值导致数据截�?�?视为违规
  - **示例**：`filterStatus !== 'all'` �?`total=filteredItems.length`、`current=1`、`pageSize=filteredItems.length||1`
  - **适用**：前端过滤已加载的分页数�?  - **不适用**：后端分页过滤（filter 参数传给后端�?  - **配置驱动**：分页参数策略在 `config.yaml` �?`filter_pagination_adapt` 节点管理
  - **历史教训**：评估明细页添加 filterStatus 后未调整 pagination 参数，导致过滤后分页错乱、数据被截断
- 🆕v4.14【强制�?*F-REVIEW-FILTER-EMPTY-STATE：过滤空状态区�?*
  - 空状态判断必须用 `filteredItems.length` 而非原始 `items.length`，区分「无数据」与「过滤后无匹配」两种文案，**禁止**用同一个空状态文案导致用户无法区�?  - **维度**�? React 组件规范
  - **核心机制**（审查时必须理解）：
    - `items.length === 0`：数据源为空（后端无数据），应显示「暂无数据�?    - `filteredItems.length === 0` �?`items.length > 0`：有数据但过滤后无匹配，应显示「当前过滤条件下无匹配记录�?    - 两种空状态文案必须不同，帮助用户判断是数据问题还是过滤问�?  - **判断信号**�?    - 前端�?`items.length === 0` 判断空状态但�?filterStatus �?视为违规
    - 过滤后无匹配数据显示「暂无数据�?�?视为违规（应显示「当前过滤条件下无匹配记录」）
    - 两种空状态用同一文案 �?视为违规
  - **示例**：`filteredItems.length === 0 ? (items.length === 0 ? '暂无数据' : '当前过滤条件下无匹配记录') : <Table>`
  - **适用**：所有带过滤功能的列表页
  - **不适用**：无过滤功能的纯展示列表
  - **配置驱动**：空状态文案在 `config.yaml` �?`filter_empty_state` 节点管理
  - **历史教训**：评估明细页过滤后无匹配数据时显示「暂无数据」，用户误以为后端无数据，实际是过滤条件不匹�?- 🆕v4.15【强制�?*F-REVIEW-DEBUG-CODE-CLEANUP：临�?DEBUG 代码清理**
  - 临时 DEBUG 代码在问题修复后必须移除�?*禁止**留在生产代码中。DEBUG 代码包括：临�?import（如 `import * as _fs from 'fs'`）、临时环境变量检查（�?`process.env.DEBUG`）、临时日志文件写入（�?`_fs.writeFileSync('debug.log', ...)`）、临�?console.log（如 `console.log('DEBUG: ...')`）。问题修复后必须 grep 所�?DEBUG 代码并移除，避免污染生产环境
  - **判断信号**：代码含 `import * as _fs` / `process.env.DEBUG` / `writeFileSync('debug.log')` / `console.log('DEBUG')` / 异常密集�?console.log �?必须检查是否为临时 DEBUG 代码；问题修复后 grep 仍有 DEBUG 代码 �?必须移除
  - **修复模式**�?    ```typescript
    // 禁止：问题修复后仍保�?DEBUG 代码（临�?import / process.env.DEBUG / writeFileSync('debug.log') / console.log('DEBUG')�?
    // �?正确：问题修复后移除所�?DEBUG 代码
    // grep -rn "DEBUG\|debug\.log\|import \* as _fs\|process\.env\.DEBUG" frontend/src/
    // 确认无残�?DEBUG 代码
    ```
  - **配置参数**：`debug.enabled`（默�?`false`，生产环境禁�?DEBUG 代码）、`debug.cleanup_after_fix`（默�?`true`，问题修复后自动清理 DEBUG 代码）、`debug.whitelist`（长期监控指标白名单，如 `["performance_metrics", "health_check"]`）在 `config.yaml` �?`debug` 节点管理
  - **适用**：临时调试代码、排查问题后的清理、开发环境调�?  - **不适用**：日志级别动态降级（需保留配置）、长期监控指标收集（需保留）、性能埋点（需保留�?  - **历史教训**：前端问题排查时添加 `import * as _fs` �?`writeFileSync('debug.log', ...)` 写入调试信息，问题修复后未移除，导致生产环境产生 debug.log 文件污染

- 🆕v4.16【强制�?*F-REVIEW-FIELD-CONTRACT-ALIGN：前后端字段契约对齐**
  - **判断信号**：后端有 `_normalize` / `_unify` / `_merge` / `_flatten` 等归一化函�?+ 前端 types.ts 声明 damages/inconsistencies 等旧字段�?+ 前端通过 `check[signalKey]` 动�?key 取�?  - **强制规则**：后端归一化字段时前端 types.ts 必须注释 `// 后端已归一化，前端消费 X 字段`；保留旧字段名必须标 optional 并注�?`// 仅作兼容保留，后端不返回`；前端禁止通过动�?key 取归一化字段，必须直接用归一化后字段名（�?`check.signals`�?  - **反例**：`const signals = (check[signalKey] as string[] | undefined) ?? []`（后端归一化后 signalKey 永远 undefined�?  - **正例**：`const signals = check.signals ?? []`
  - **配置参数**：`field_contract_align` 节点（enabled / require_doc_comment / detect_dynamic_key_access / fallback_to_legacy_field�?  - **适用场景**：后端有归一化函�?+ 前端通过动�?key 取�?  - **不适用场景**：后端直接返回原始响应无转换；前端类型声明与后端 pydantic 模型一一对应

- 🆕v4.16【强制�?*F-REVIEW-ERROR-HANDLER-EXTRACT：重复错误处理抽�?*
  - **判断信号**：grep `status === 403` / `status === 404` 在同文件内出�?>= 2 处；多个 async 函数调用同一后端端点的错误处�?if-else 完全重复
  - **强制规则**：两处以上相�?if-else 状态码分支必须抽取工具函数 `handleXxxError(err, fallbackMsg, closeModal)`；抽取后原调用处仅保�?`handleXxxError(err, '失败文案', () => setModalOpen(false))` 一�?  - **反例**：onAIEval �?onDeepAnalyze 各自包含 403/404/422 三段 if-else 完全重复
  - **正例**：抽�?`handleAiError(err, fallbackMsg, closeModal)` 工具函数，两处调用各减少 13 �?  - **配置参数**：`error_handler_extract` 节点（enabled / min_duplicate_count / detect_patterns / unified_signature�?  - **适用场景**：多�?async 函数调用同一后端端点；多个函数处理同一类外�?API 错误
  - **不适用场景**：仅一处调用的错误处理；错误处理逻辑有差异（如不同端点状态码集合不同�?
- 🆕v4.21【强制�?*F-REVIEW-FIELD-NAME-ALIGN：字段名三层一致性规�?*
  - 凭据字段名在四层（前�?`types.ts` / 后端 Pydantic 模型 / keyring KEY 常量 / yaml 字段）必�?1:1 对齐；当第三方库构造函数参数名与本项目字段名不一致时，必须在 API 边界层做字段名映射（`_FIELD_NAME_MAP` 映射�?+ `_map_credentials_to_notifier_params()` 转换函数），**禁止** API 端点直接 `**body.credentials` 解包透传
  - **核心机制**（审查时必须理解）：
    - Pydantic v2 + keyring + yaml 三层持久化链路中，字段名不一致会导致同步写错位置�?`model_dump()` 丢弃字段
    - 第三�?Notifier 构造函数参数名（如 `webhook_url`/`send_key`/`token`）通常与项目字段名（如 `dingtalk_webhook`/`serverchan_send_key`/`pushplus_token`）不一�?    - API 端点直接 `**body.credentials` 解包传给 Notifier 构造函数，未识别字段会�?`**kwargs` 吞入，触�?`TypeError`
    - 边界层映射函数必须集中在模块顶部声明，禁止散落在多个函数�?  - **判断信号**�?    - 前端 `types.ts` 凭据字段�?�?后端 Pydantic 字段�?�?视为违规
    - 后端 Pydantic 字段�?�?keyring KEY 常量�?�?视为违规
    - keyring KEY 常量�?�?yaml 字段�?�?视为违规
    - API 端点直接 `**body.credentials` 解包传给 Notifier 构造函�?�?必查字段名映�?    - Notifier 构造函数参数名与前端字段名不一致（�?`dingtalk_webhook` vs `webhook_url`）→ 必须在边界层做字段名映射
  - **修复模式**�?    ```typescript
    // �?前端 types.ts 字段名与后端 Pydantic 字段�?1:1 对齐
    interface NotifierCredentials {
      serverchan_send_key: string
      pushplus_token: string
      bark_server: string
      bark_key: string
      telegram_bot_token: string
      telegram_chat_id: string
      wecom_webhook: string
      dingtalk_webhook: string
      dingtalk_secret: string
      webhook_url: string
    }
    ```

    ```python
    # �?后端边界层字段名映射（集中在模块顶部声明�?    _FIELD_NAME_MAP: dict[str, str] = {
        "serverchan_send_key": "send_key",
        "pushplus_token": "token",
        "bark_server": "server",
        "bark_key": "key",
        "telegram_bot_token": "bot_token",
        "telegram_chat_id": "chat_id",
        "wecom_webhook": "webhook_url",
        "dingtalk_webhook": "webhook_url",
        "dingtalk_secret": "secret",
    }

    def _map_credentials_to_notifier_params(credentials: dict[str, str]) -> dict[str, str]:
        """将前端字段名转换�?Notifier 构造函数参数名"""
        mapped: dict[str, str] = {}
        for key, value in credentials.items():
            mapped[_FIELD_NAME_MAP.get(key, key)] = value
        return mapped

    # 禁止：直�?**body.credentials 解包（TypeError: unexpected keyword argument�?    ```
  - **配置参数**：`field_name_mapping.layers`（必须对齐的层级列表，如 `["frontend_types", "pydantic_model", "keyring_key", "yaml_field"]`）、`field_name_mapping.boundary_map`（边界层字段名映射表，如 `{"serverchan_send_key": "send_key", ...}`）、`field_name_mapping.require_align_check`（默�?`true`，CI 中自动检查字段名对齐）在 `config.yaml` �?`field_name_mapping` 节点管理
  - **适用场景**：凭据字段（webhook/token/secret 类）；前后端持久化链路字段；多层级字段名一致性要�?  - **不适用场景**：第三方 API 返回字段的归一化（参�?F-REVIEW-FIELD-CONTRACT-ALIGN）；前端内部状态字段（无后端对应）；后端计算字段（无前端写入）
  - **历史教训**：前端字段名 `dingtalk_webhook` �?Notifier 构造函数参数名 `webhook_url` 不一致，`/api/notifier/test` 直接 `**body.credentials` 解包导致 `TypeError: BaseNotifier.__init__() got an unexpected keyword argument 'dingtalk_webhook'`。修复后添加 `_FIELD_NAME_MAP` 边界层映�?
- 🆕v4.21【强制�?*F-REVIEW-CONFIG-PERSIST-VERIFY：配置持久化端到端验证规�?*
  - 持久化链路必须端到端验证（前端写�?�?API 接收 �?Pydantic 序列�?�?yaml 存储 �?keyring 同步（如适用�?�?GET 回显），每层必须打印中间值确认传递；修复后必须新增端到端测试覆盖该场景（前端写入 �?刷新页面 �?验证回显）；开关状态字段必须默认安全（�?`enabled: bool = False` 默认关闭，避免意外启用）
  - **核心机制**（审查时必须理解）：
    - 持久化链路任一层断裂都会导�?填写后刷新页面变�?问题
    - Pydantic v2 `extra='ignore'` 会丢弃未声明字段（参�?B-REVIEW-PYDANTIC-FIELD-DECLARE�?    - 前端 `types.ts` 字段缺失会导�?API 响应字段无法被前端消�?    - 开关状态默认值若�?`true`，新增功能默认启用可能造成意外影响
  - **判断信号**�?    - 前端表单填写后刷新页面输入框变空 �?必查持久化链路（types.ts �?API �?Pydantic �?yaml �?回显�?    - 前端开关状态切换后刷新页面还原为初始�?�?必查开关字段是否在 Pydantic 模型中声�?    - API 响应缺失前端写入的字�?�?必查 Pydantic `model_dump()` 是否丢弃未声明字�?    - 前端调用 `PUT /api/config` 成功�?`GET /api/config` 返回旧�?�?必查后端是否实际写入 yaml
  - **修复模式**�?    ```typescript
    // �?前端：写入后立即 GET 验证回显
    const onSave = async (credentials: NotifierCredentials) => {
      await fetch('/api/config', {
        method: 'PUT',
        credentials: 'include',
        body: JSON.stringify(credentials),
      })
      // 端到端验证：立即 GET 确认回显
      const resp = await fetch('/api/config', { credentials: 'include' })
      const data = await resp.json()
      if (data.dingtalk_webhook !== credentials.dingtalk_webhook) {
        message.error('配置未持久化，请检查后�?)
      }
    }
    ```
  - **配置参数**：`config_persist_verify.layers`（必须验证的层级列表，如 `["frontend_write", "api_receive", "pydantic_serialize", "yaml_store", "get_response"]`）、`config_persist_verify.require_e2e_test`（默�?`true`，必须新增端到端测试）、`config_persist_verify.default_safe_value`（默�?`false`，开关字段默认安全值）�?`config.yaml` �?`config_persist_verify` 节点管理
  - **适用场景**：所有用户可编辑的配置项（凭据、开关、阈值）；前端表�?�?后端持久化的链路；刷新页面后状态需保持的场�?  - **不适用场景**：纯前端状态（�?UI 折叠状态）；运行时计算字段（无需持久化）；调试用临时字段
  - **历史教训**：通知渠道菜单填写凭据后刷新页面输入框清空。根因：`AppConfig` Pydantic 模型未声明凭据字段，`extra='ignore'` 导致 `model_dump()` 丢弃，`GET /api/config` 不返回凭据。修复后端到端验证每一层传�?- 🆕v4.23【强制�?*F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION：模型能力元数据集中展示与降级状态可视化**
  - 前端展示 LLM 模型能力（vision_capable / function_call / json_mode）时必须**集中展示**（从后端 `/api/config` �?`/api/about` 统一获取，禁止在每个展示页独�?fetch / 内联判断）；用户上传图片 / 启用 tool 时前端必须根据能力位给出**降级状态可视化**（如 `Tag color="warning"` 显示"纯文本模型不支持图片分析，已降级为文字描�?），禁止静默丢弃用户的可选输�?  - **核心机制**（审查时必须理解）：
    - 后端 `api_ai._is_vision_capable()` 共享函数 + `api_ai_deep.py` 调用是后端服务端�?能力-需�?匹配
    - 前端展示层是"用户-能力"对齐：用户能直观看到当前模型支持什么能�?+ 不支持时降级行为
    - 后端 LLM 调用前预检 + 前端展示能力�?+ 降级状态可视化 = 端到端能力驱动派�?    - 关键字白名单仅在后端 `api_ai._VISION_CAPABLE_KEYWORDS` 一处维护，前端展示�?`settings.openai_vision_model` + 单一 `isVisionCapable()` 共享函数
  - **判断信号**�?    - 前端 `useState` / `useEffect` 内独�?fetch `/api/config` 获取 vision_model + 内联关键字白名单判断（`if (model.includes('vision'))`）→ 视为违规（应统一 fetch + 共享函数�?    - 前端调用图片上传 / function call 时未做能力位预检 + 降级提示 �?视为违规
    - 关键字列表（`['vision', 'gpt-4o', ...]`）出现在前端 `.tsx`/`.ts` 文件中（应仅在后�?`api_ai.py`）→ 视为违规
    - �?�? 前端组件出现相同�?vision_capable 判断逻辑 �?视为违规（应抽到 `frontend/src/utils/modelCapability.ts` 共享�?  - **修复模式**�?    ```typescript
    // �?共享工具函数 + 集中获取 + 降级可视�?    // frontend/src/utils/modelCapability.ts
    const VISION_KEYWORDS = ['vision', 'gpt-4o', 'gpt-4-vision', 'qvq', 'qwen-vl', 'glm-4v', 'claude-3', 'opus', 'sonnet', 'haiku'] as const;
    export function isVisionCapable(modelName: string | null | undefined): boolean {
      if (!modelName) return false;
      return VISION_KEYWORDS.some(kw => modelName.toLowerCase().includes(kw));
    }
    export function getCapabilityDisplay(modelName: string | null | undefined): { vision: boolean; warning?: string } {
      if (!modelName) return { vision: false, warning: '未配置模�? };
      const vision = isVisionCapable(modelName);
      return { vision, warning: vision ? undefined : '当前模型为纯文本模型，已自动降级为文字描�? };
    }

    // AI 配置页（集中展示�?    import { getCapabilityDisplay } from '@/utils/modelCapability';
    const { vision, warning } = getCapabilityDisplay(settings.openai_vision_model);
    return <div>
      <Tag color={vision ? 'success' : 'warning'}>{vision ? '支持 Vision' : '不支�?Vision'}</Tag>
      {warning && <Alert type="warning" message={warning} />}
    </div>;

    // 图片上传组件（消费端�?    const { vision } = getCapabilityDisplay(settings.openai_vision_model);
    const handleUpload = (file: File) => {
      if (!vision) {
        message.warning('当前模型不支持图片分析，将使用文字描�?);
        return uploadAsText(file);
      }
      return uploadAsImage(file);
    };
    ```
    ```typescript
    // 禁止：跨组件内联关键�?+ 独立 fetch（AIConfigPage / ImageUploader 各自 fetch + 内联关键字判断，散落修改风险�?    ```
  - **配置参数**：`model_capability_centralization.shared_util_path`（默�?`frontend/src/utils/modelCapability.ts`）、`model_capability_centralization.capability_source`（默�?`/api/config` + `/api/about`）、`model_capability_centralization.require_centralized_fetch`（默�?`true`，禁止每页独�?fetch）、`model_capability_centralization.require_downgrade_visualization`（默�?`true`，降级状态必须可视化）、`model_capability_centralization.tag_color_mapping`（默�?`{supported: 'success', unsupported: 'warning'}`）、`model_capability_centralization.alert_message`（默�?`当前模型不支�?{capability}，已自动降级�?{fallback}`）在 `config.yaml` �?`model_capability_centralization` 节点管理
  - **适用场景**：前端展�?LLM 模型能力（AI 配置�?/ 设置�?/ 模型选择器）；用户上传图�?/ 启用 tool / 选择 json_mode 的交互组件；监控页展示当前模型能力与降级状态；多页面共享同一能力位信�?  - **不适用场景**：纯后端内部能力判断（无前端展示）；单页面单次性能力判断（不必抽取共享函数）；后端 SDK 已封装能力判断（�?langchain `with_structured_output`�?  - **历史教训**：深度分析无脑拼�?`image_url` content block �?后端 400 �?WARNING 噪音；前端用户上传图片时未做能力预检，图片被静默丢弃；修复时后端�?`_is_vision_capable()` 共享函数 + 前端�?`getCapabilityDisplay()` 共享函数 + 集中展示能力 + 上传时降级提�?
### 12. SonarQube 合规 🆕v2.0 / v3.0 增强

- 【强制�?*S2004**：函数嵌套层�?�?4，超限提取模块级函数（典型：setState updater�?- 【强制�?*S3358**：嵌套三元拆为变量（不超�?2 层）
- 【强制�?*S6757**：SFC 内不�?`this`，工厂函数替�?class
- 【强制�?*S7784**：使�?`structuredClone` 替代 `JSON.parse(JSON.stringify())`
- 【强制�?*S6848**：`clickableProps` 工厂函数配键盘事�?- 【强制�?*S1128**：删除未使用 import
- 【强制�?*S4325**：移除不必要类型断言
- 【强制�?*S3776**：认知复杂度 �?15，拆 case 为模块级 handler
- 🆕【强制�?*S7503**：不必要�?`async` 函数（无 await）——同步函数移�?`async` 关键�?- 🆕【强制�?*S6767**：未使用�?Props/State/参数 ——立即删除，避免接口膨胀
- 🆕【强制�?*S6819**：使�?`<a>` 替代 `<button>`（无 href 时）——改�?`<button type="button">`
- 🆕【强制�?*S6844**：使�?`<div role="button">` 替代 `<button>` ——优先原�?`<button>` + 键盘事件
- 🆕【强制�?*S7744**：不必要的类型转换（`as` 链路过深）——用类型守卫（`type guard`）收窄类�?- 🆕【强制�?*S6582**：可选链冗余调用（`a?.b?.c` �?a 已非空）——移除冗�?`?.`
- 🆕【强制�?*S7735**：useEffect 缺少依赖�?——补全依赖数组（�?`ref` 持有最新闭包避免循环）
- 🆕【强制�?*S6551**：使�?`for...in` 遍历对象 ——改�?`Object.keys/values/entries`
- 🆕【强制�?*S1874**：使�?`@deprecated` 标记替代直接删除�?API ——导出前标注 deprecated

**实战案例参�?*�?- `SheetTabs.tsx` 拆分 `TabItem` �?`ThumbnailTab` + `StandardTab` 修复 S3776 + S6767
- `Chatbot/index.tsx` �?`createSendCompleteHandler` 工厂函数修复 S2004 + S6819
- `ItemList.tsx` `div+onClick` �?`<button>` 修复 S6844
- `Evaluations/index.tsx` 提取 `resolveActionDisplay` 修复 S3776

### 13. PWA 配置 🆕v2.0

- 【强制】`vite.config.ts` 配置 `base: '/xianyu/'`
- 【强制】构建产物输出到 `../src/xianyu_hunter/web/static/spa`
- 【强制】`VitePWA` `registerType: 'prompt'`
- 【强制】`manifest.theme_color: '#FF6200'`
- 【强制】`workbox.maximumFileSizeToCacheOnBytes: 4MB`
- 【强制】`runtimeCaching` 排除以下路径（不缓存）：
  - `/api/events/stream`
  - `/api/auth/`
  - `/api/export/`
  - `/xianyu/api/`
- 【强制】`devOptions.enabled: false`
- 【强制】`workbox-build` / `workbox-window` 必须在 `frontend/package.json` 的 `devDependencies` 中显式声明（vite-plugin-pwa 将其列为 peerDependency；未声明时 `npm ci` 会移除，构建报 `Cannot find module 'workbox-build'`）。Signal: `grep -n "workbox-build\|workbox-window" frontend/package.json`
- 【强制】`vite.config.ts` 必须 `build.emptyOutDir: false`，输出目录清理改由构建脚本用 `rmdir /s /q`（cmd 内建，不经沙箱 safe-delete 劫持）或 .NET 直接删除负责；禁止依赖 vite 构建开始的 emptyOutDir 清空（沙箱 safe-delete 守卫会中断 `fs.rmSync`）。Signal: `grep -n "emptyOutDir" frontend/vite.config.ts`
- 【强制】`vite.config.ts` 使用函数式 `defineConfig(({ command }) => ({...}))` 并在 `optimizeDeps` 设 `force: command === 'build'`（仅 build 强制从零预构建，避免 `node_modules` 重装后陈旧 `.vite/deps` 缓存导致 Rollup `failed to resolve import` 纯 ESM 包）。Signal: `grep -n "optimizeDeps" frontend/vite.config.ts`
- 【强制】`runtimeCaching` 排除规则与 `navigateFallbackDenylist` 必须同时覆盖 `spa.api_prefix`（默认 `/xianyu/api`）与裸 `/api/`（双前缀部署下真实 API 路径为 `/xianyu/api/*`）。Signal: `grep -n "navigateFallbackDenylist\|runtimeCaching" frontend/vite.config.ts`

### 14. 三处映射同步 🆕v2.0

- 【强制】新增页面必须同步维护三处：
  1. `frontend/src/App.tsx`：路由声�?  2. `frontend/src/components/layout/MainLayout.tsx`：`menuItems` 菜单注册
  3. `frontend/src/components/SheetWorkspace/sheetRegistry.tsx`：path �?component 映射
- 【强制】菜单三级分组（Command Palette 支持�?
### 15. SSE 重连 🆕v2.0

- 【强制】SSE lastEventId 持久化重连（`frontend/src/pages/Dashboard/index.tsx`�?- 【强制】`SSE_LAST_EVENT_ID_KEY = 'xh_sse_last_event_id'` 模块级常�?- 【强制】断线重连从 localStorage 读取 lastEventId 作为 `?last_event_id=` 参数
- 【强制】`handleSseAppEvent` 模块级函数（SonarQube S2004�?- 【强制�?*SSE 断线重连三要�?*（缺一不可）：
  1. **lastEventId 记录**：`app_event` 回调�?`e.lastEventId`（MessageEvent 属性，�?EventSource）保存到变量
  2. **重连传�?last_event_id**：URL 拼接 `?last_event_id=${lastEventId}`，启用后端回放断线期间事�?  3. **visibilitychange 监听**：页面恢复可见且 SSE 已断开时自动重建连接（解决页面不可见时 selectedTask 变化导致 SSE 永久断开的问题）
- 【强制】SSE error 重连必须有次数上限（`MAX_RECONNECT`，通过配置管理，默�?10），超限后放�?SSE 退化为轮询
- 【强制】页面恢复可见时重置重连计数（`reconnectAttempts = 0`），给新一轮重连机�?- 【强制】`visibilitychange` 事件监听必须�?useEffect cleanup 中移除（`document.removeEventListener`），避免内存泄漏
- 【常见陷阱】`lastEventId` �?`MessageEvent` 的属性（`e.lastEventId`），不是 `EventSource` 的属性（`es.lastEventId` 不存在）
- 🆕v4.1【强制�?*F-REVIEW-SSE-ERROR-HANDLING：SSE 错误事件状态码分类处理**
  - SSE 流中收到 `stage='error'` 事件时，必须�?`status` 字段分类处理（状态码与文案映射在 `config.yaml` �?`sse_error_status_mapping` 节点管理）：
    - `503/504`：稍后重试提示（�?网络繁忙，请稍后重试"），不阻�?UI
    - `401/403`：需用户介入（如"登录已过期，请前往「反爬登录管理」重新登�?�? 显式"前往登录"跳转按钮（用 `useNavigate` 跳转�?`/login` 或反爬登录页�?    - `502`：需重启服务提示（如"浏览器连接断开，请重启服务"�?  - **禁止**：将 `stage='done'` + 0 条结果与 `stage='error'` 混为一谈（前者是"真的没货"，后者是"业务异常"�?  - **禁止**：吞�?`stage='error'` 事件只展示通用错误（如只显�?预览失败"而无具体指引�?  - **判断信号**：组件消�?SSE 流（�?`useAutoLiveSearch.ts` �?`live` 方法回调）→ 必须显式处理 `stage='error'` 分支
  - **通过示例**�?    ```typescript
    if (data.stage === 'error') {
      const status = data.status ?? 500
      if (status === 401 || status === 403) {
        setErrorMsg(data.detail ?? '登录已过�?)
        setShowReLoginBtn(true)  // 显示"前往登录"按钮
      } else if (status === 502) {
        setErrorMsg(data.detail ?? '服务异常，请重启')
      } else {
        setErrorMsg(data.detail ?? '网络繁忙，请稍后重试')
      }
      return
    }
    ```
  - **不通过示例**�?    ```typescript
    if (data.stage === 'done') { /* 渲染结果 */ }
    // 未处�?stage='error'，导�?SSE 错误事件被忽略或走默认分�?    ```

### 16. 性能评审

- 【强制】复�?props（对象、数组、Map）使�?`useMemo` 保证引用稳定
- 【强制】回调函数使�?`useCallback` 避免子组件不必要渲染
- 【强制】`useEffect` 依赖数组完整性（避免遗漏依赖导致 stale closure�?- 【强制】列表渲染使用稳定的 `key`�?*禁止**�?index�?- 【强制】大列表虚拟化（`react-window`/`react-virtualized`�?- 【禁止】在 render 内创建新对象/数组
- 【强制】React Flow 数据使用 `useNodes`/`useEdges`（不手动拉取�?- 【强制】echarts 5.5 按需导入
- 【强制】网络重连（SSE/WebSocket/API 重试）必须有最大次数限制，超限后退化为降级方案（如轮询�?- 【强制】无限重连循环（`setTimeout(connect, N)` 无计数器）视为资源浪费风�?
### 17. 可访问性评�?
- 【强制】交互元素（特别是图标按钮）必须�?`aria-label`
- 【强制】表单控件必须有 `label` 关联
- 【推荐】颜色对比度达标（WCAG AA�?- 【推荐】键盘导航支持（Tab 顺序、Enter/Space 触发�?- 【推荐】屏幕阅读器友好性（语义化标签、`role` 属性）
- 🆕v4.0【强制�?*外部链接安全**：`target="_blank"` 必须�?`rel="noopener noreferrer"`（防 `window.opener` 钓鱼 + 不泄�?Referer�?
### 18. 闲鱼项目规范 🆕v2.0

- 【强制】UI 组件库：Ant Design 5.21
- 【强制】视觉风格（来自 user_profile.md）：干净明亮的扁平化设计语言，清新治愈的 macaron 配色，浅�?浅青为主，大圆角，轻透磨砂玻璃质�?- 【强制】API 出口统一：`frontend/src/api/index.ts` �?`export *` 聚合
- 【强制】测试框架：Vitest 4.1 + @testing-library/react 16.3 + jsdom 29.1
- 【强制】测试文件位置：组件/hook 同级目录 `__tests__/<Component>.test.tsx`
- 【强制】构建命令：`npm run build`（`tsc -b && vite build`�?- 【强制】类型检查：`npx tsc -b`（构建前强制类型检查）
- 【强制】Dev 命令：`npm run dev`（HMR，端�?5173�?- 【强制】测试命令：`npx vitest run`
- 【推荐】抽象模式：纯函�?+ 组件 + 常量分层（如 `resolveActionDisplay` + `ActionPlaceholder` + `ACTION_PLACEHOLDER_TEXT`�?- 🆕v4.0【强制�?*显式样式优于隐式间距**：图�?文字、按�?文字等内联元素间距用显式 `style={{ marginRight: N }}` �?`Space` 组件�?*禁止**依赖 JSX 空格渲染间距
- 🆕v4.0【强制�?*注释与代码一致�?*：注释必须与代码逻辑严格一致，禁止误导性注释；防御性说明需明确标注�?防御�?而非"必需"
- 🆕v4.7【强制�?*F-REVIEW-REUSE-PATTERN-FRONTEND：复用既有模式原则（前端侧）**
  - 新增前端功能前必�?grep 项目内相似实现，复用既有 Hook/工具函数/模式�?*禁止**重新实现已有功能
  - **判断信号**：新�?Hook/组件/工具函数�?�?grep 项目内是否已有相似实�?�?若有则复用或扩展 �?若无则评估是否可抽取为通用工具
  - **修复模式**（复用检查流程）�?    ```typescript
    // 新增"采集评估明细"功能前，�?grep 项目内相似实�?    // grep "message.loading" �?发现多处使用 message.loading + try/catch + message.success/error 模式
    // 复用既有模式�?    const hide = message.loading('正在采集...', 0)  // �?复用 message.loading 模式
    try {
      // ...
    } catch (err) {
      hide()
      message.error(...)  // �?复用 message.error 模式
    }
    // 新增页面路由前，�?grep "lazyRetry" �?复用既有懒加载模�?    const EvalDetail = lazy(() => lazyRetry(() => import('./pages/EvalDetail')))  // �?复用 lazyRetry
    // 新增深拷贝需求前，先 grep "JSON.parse" �?发现应改�?structuredClone（SonarQube S7784�?    const cloned = structuredClone(data)  // �?复用 structuredClone 模式
    ```
  - **配置参数**：`search_keywords`（搜索关键词列表，如 `message.loading` / `lazyRetry` / `structuredClone` / `useDebounce` / `useEventSource`）、`similarity_threshold`（相似度阈值，默认 0.7）、`reuse_priority`（复用优先级：项目内既有 Hook > 工具函数 > 模式 > 标准�?> 第三方库）在 `config.yaml` �?`reuse_pattern_frontend` 节点管理
  - **关键约束**�?    - 新增 Hook 前必�?grep `use*.ts` 确认无相似实�?    - 新增工具函数前必�?grep `utils/` / `helpers/` 确认无相似实�?    - 强行复用导致耦合 > 重新实现的成本时，允许重新实现但需注释说明
    - 复用 Ant Design 组件时必须确认版本兼容性（项目�?AntD 5.21�?  - **适用**：新增前端功能（Hook/组件/工具函数/模式）前的预检�?  - **不适用**：首次实现的基础设施代码（无既有实现可复用）、业务逻辑差异较大的场景（强行复用会导致耦合�?  - **历史教训**：评估明细采集按钮未复用项目内既有的 `message.loading` + `try/catch` + `message.success/error` 三态反馈模式，导致无用户反馈。修复后复用既有模式实现三态反�?- 🆕v4.19【强制�?*F-REVIEW-SCHEDULER-STATUS-DISPLAY：调度器状态展示规�?*
  - 前端"关于"页面必须展示关键调度器启动状态，调用 `/api/about` 端点获取 `schedulers: [{name, enabled, interval_minutes, last_run_at}]` 数组并渲染为状态卡片，未启动的调度器必须显示红�?未启�?标签 + 启动命令提示，启动的调度器显示绿�?运行�?标签 + 间隔 + 最近运行时间，调度器状态变更必须通过 SSE 实时推送或定时轮询刷新
  - **核心机制**（审查时必须理解）：
    - 后端关键调度器（�?`BatchRefreshScheduler`）影响业务正确性，但用户无法从终端日志感知启动状�?    - 前端"关于"页面是用户感知系统运行状态的唯一入口，必须展示调度器状�?    - 未启动调度器必须用红色标签醒目标�?+ 显示启动命令（如 `python -m xianyu_hunter web --with-scheduler`�?    - 启动的调度器显示绿色"运行�?标签 + 间隔（如"�?30 分钟"�? 最近运行时�?    - 调度器状态可能随启动参数/环境变量变化，必须通过 SSE 推送或定时轮询（间隔在 config.yaml 管理）刷�?  - **判断信号**�?    - `grep "schedulers" frontend/src/` 未发现消�?`/api/about` 返回�?`schedulers` 字段 �?视为违规
    - "关于"页面只有版本�?构建时间，无调度器状态展�?�?视为违规
    - 调度器状态用单一布尔值显示（�?未启�?vs"运行�?区分）→ 视为可疑
    - 未启动调度器无启动命令提�?�?视为可疑
    - 调度器状态无定时刷新（仅页面加载时拉一次）�?视为可疑
  - **修复模式**�?    ```typescript
    // �?types.ts 声明调度器状态类�?    interface SchedulerStatus {
      name: string
      enabled: boolean
      interval_minutes: number
      last_run_at: string | null  // ISO 时间字符串，null 表示从未运行
    }

    // �?About 页面渲染调度器状态卡�?    function SchedulerStatusCard({ scheduler }: { scheduler: SchedulerStatus }) {
      return (
        <Card size="small" title={scheduler.name}>
          <Space>
            <Tag color={scheduler.enabled ? 'success' : 'error'}>
              {scheduler.enabled ? '运行�? : '未启�?}
            </Tag>
            <Text type="secondary">�?{scheduler.interval_minutes} 分钟</Text>
            {scheduler.last_run_at && (
              <Text type="secondary">
                最近运行：{new Date(scheduler.last_run_at).toLocaleString()}
              </Text>
            )}
          </Space>
          {!scheduler.enabled && (
            <Alert
              type="warning"
              showIcon
              message="该调度器未启动，相关功能将不生效"
              description={
                <Text code>python -m xianyu_hunter web --with-scheduler</Text>
              }
            />
          )}
        </Card>
      )
    }

    // �?定时轮询刷新（间隔从 config 读取�?    const POLL_INTERVAL = 30000  // 30s，应�?config.yaml 读取
    useEffect(() => {
      const timer = setInterval(() => aboutApi.get().then(setAboutInfo), POLL_INTERVAL)
      return () => clearInterval(timer)
    }, [])

    // 禁止：未展示调度器状态，用户无法感知启动情况
    ```
  - **配置参数**：`scheduler_status_display.enabled`（默�?`true`）、`scheduler_status_display.require_about_endpoint_consumption`（默�?`true`，前端必须消�?`/api/about` �?`schedulers` 字段）、`scheduler_status_display.require_disabled_hint`（默�?`true`，未启动调度器必须显示启动命令提示）、`scheduler_status_display.require_realtime_refresh`（默�?`true`，必须通过 SSE 或定时轮询刷新）、`scheduler_status_display.refresh_interval_ms`（默�?`30000`，轮询间隔毫秒）、`scheduler_status_display.status_color_mapping`（默�?`{enabled: 'success', disabled: 'error'}`）、`scheduler_status_display.startup_command_hint`（默�?`'python -m xianyu_hunter web --with-scheduler'`，未启动时显示的启动命令）在 `config.yaml` �?`scheduler_status_display` 节点管理
  - **适用**：前�?关于"页面/系统信息页面；展示后端调度器运行状态；用户需要感知后台任务运行情况的场景
  - **不适用**：纯前端调度器（�?`setInterval` 无后端对应）；调试用页面（非用户面向）；无调度器的简单应�?  - **历史教训**：用户启�?web 服务时未�?`--with-scheduler` 参数，`BatchRefreshScheduler` 永远不运行，但前�?关于"页面只显示版本号，用户无法感知调度器未启动。导致商�?1058031608014 实际已售但数据库 `is_sold=0` 长期不刷新，用户看到已售商品仍被推荐。修复后前端"关于"页面展示调度器状态卡片，未启动时显示红色标签 + 启动命令提示

### 19. 跨组件状态同步与死代码检�?🆕v4.3

- 【强制�?*F-REVIEW-DEAD-CODE：长期存活对象禁止赋值给局部变�?*：`new Proxy()` / `new MutationObserver()` / `new IntersectionObserver()` 等需要长期存活的监听�?观察者，必须赋值给实例属性（`this._observer`）或模块级变量，禁止赋值给局部变量后丢弃
  - **判断信号**：`var xxx = new Proxy(...)` / `const xxx = new MutationObserver(...)` �?xxx 是局部变量且未被返回/导出
  - **修复模式**：赋值给实例属性或模块级变量，确保引用保留
  - **历史教训**：`awsc_spoof.py` �?`var baxiaProxy = new Proxy(window.__baxia__, {...})` 赋值给局部变量后从未使用，验证码触发事件永远不会被派�?
- 【强制�?*F-REVIEW-TRY-FINALLY-INIT：try/finally 变量初始�?*：`try/finally` 块中 `finally` 引用的变量必须在 `try` 之前初始化为 `null`/`undefined`，确�?`try` 内赋值前抛异常时 `finally` 不会�?`ReferenceError`
  - **判断信号**：`try { const page = await create() } finally { page.close() }` �?page �?try 内声�?  - **修复模式**：`let page = null; try { page = await create() } finally { if (page) await page.close() }`

- 【强制�?*F-REVIEW-CROSS-COMPONENT-STATE：跨组件状态同�?*：多个组�?模块对同一概念（如"会话有效�?�?登录状�?）做判断时，状态变更必须双向同步——状态变更方通知其他组件、查询方额外检查其他组件的最新状�?  - **判断信号**：两个以上组件各自独立判�?会话有效�?/"登录状�?等同一概念（如健康检查器检�?Cookie 存在�?+ worker 检�?API 响应 RGV587_ERROR�?  - **修复模式**：前�?store 状态变更时通过事件/回调通知其他组件；查询方在判断时额外检查其他来源的状态标�?  - **不适用**：单组件内部状态、无跨组件依赖的独立判断

- 【强制�?*F-REVIEW-ERROR-HINT-ROUTABLE：错误提示路由可操作�?*：面向用户的错误提示中引用的路由路径必须在前端路由表中已注册，引用的 API 端点必须在后端已实现
  - **判断信号**：错误信息中包含 `/api/xxx` �?`/page-path` 引用
  - **修复模式**：提示中只引用已注册的路由和已实现的端点；提供具体的可操作修复指引（�?请点击「反爬登录管理」重新初始化"而非"请调�?/api/xxx/configure"�?
### 20. API 数据源一致性与类型契约对齐 🆕v4.4

- 【强制�?*F-REVIEW-API-DATA-SOURCE-CONSISTENCY：API 响应消费一致�?*：同一 API 响应被多处组件消费时，必须共用同一 fetch 结果（通过 store/context 缓存），禁止各组件独立调用导致数据不一致；后端返回新增字段时所有消费方必须同步更新
  - 检查清单（参数�?`config.yaml` �?`api_data_source_consistency` 节点管理）：
    - `enabled`：默�?`true`
    - `shared_fetch_apis`：默�?`["/api/stats", "/api/prices/histogram", "/api/config"]`，需共享 fetch 的端�?    - `require_type_sync`：默�?`true`，后端新增字段时前端 types.ts 必须同步
  - **判断信号**：两个以上组件各自调用同一 `priceApi.histogram()` �?必须改为共享 fetch；后�?summary 新增 `task_price_range` 字段但前�?`HistogramData` 类型未声�?�?类型契约断裂
  - **修复模式**：将 fetch 结果存入 store/context，各组件�?store 读取；后端新增字段后立即�?`api/types.ts` 同步声明并注释字段语�?  - **适用**：仪表盘多卡片消费同一 API、配置页与业务页共用配置数据、后端响应结构变�?  - **不适用**：独立页面的独立 API 调用、明确需要实时刷新的独立请求
  - **历史教训**：后�?`price_histogram.py` summary 新增 `task_price_range` 字段，若前端 `HistogramData` 类型未同步声明，TS 严格模式下访�?`histogram.summary.task_price_range` 会类型报错；`PriceStrategy.tsx` 独立调用 `priceApi.histogram()` 且检�?`data?.counts`（不存在的字段），导致始终走 catch 降级到模拟数�?
- 【强制�?*F-REVIEW-TYPE-CONTRACT-ALIGN：前后端类型契约对齐**：后�?Pydantic 模型/响应体新增或修改字段时，前端 `api/types.ts` 必须同步更新；可选字段用 `field?: T`，可空字段用 `field: T | null`
  - 检查清单（参数�?`config.yaml` �?`type_contract_align` 节点管理）：
    - `enabled`：默�?`true`
    - `type_file_path`：默�?`"frontend/src/api/types.ts"`
    - `optional_vs_null`：默�?`"optional"`，优先用 `field?: T` 而非 `field: T | null`
  - **判断信号**：后端响应含 `task_price_range: {min_price: float | null, max_price: float | null}` 但前端类型未声明 �?必须补齐；前端用 `as any` 绕过类型检�?�?必须改为精确类型
  - **修复模式**：后端新增字段后，在 `types.ts` 对应接口同步声明，注释字段语义和可空场景；前端消费新增字段时先做 null 检�?  - **适用**：所有后端响应结构变更、新�?API 端点、字段语义变�?  - **不适用**：内部工具函数返回值、纯前端计算字段

- 【建议�?*F-REVIEW-ERROR-CODE-CONSUMPTION：error_code 消费决策**：后端错误响应含 `error_code` 时，前端必须根据 error_code 做重�?降级决策，而非统一展示错误信息
  - 检查清单（参数�?`config.yaml` �?`error_code_consumption` 节点管理）：
    - `enabled`：默�?`true`
    - `retryable_codes`：默�?`["network_error", "timeout", "rate_limited", "service_unavailable"]`
    - `non_retryable_codes`：默�?`["item_not_found", "invalid_params", "auth_failed", "business_rule"]`
  - **判断信号**：catch 块统一 `message.error(extractApiError(e))` 但未检�?`error_code` �?可重试错误未提供重试入口
  - **修复模式**：解析响应体 `error_code`，可重试错误显示"重试"按钮，不可重试错误显示具体原�?  - **适用**：批量操作错误处理、需用户决策重试的场�?  - **不适用**：简单表单提交错误（�?extractApiError 统一处理即可�?
- 🆕v4.25【强制�?*F-REVIEW-ERROR-HANDLING-CONSISTENCY：错误处理一致性检�?*
  - 维度�?0 错误提示语义 + 配置链路
  - 严重等级：error
  - **检查点**：API 调用�?catch 块是否使�?`extractApiError` 提取具体错误信息
  - **判定标准**�?*禁止** `message.error('保存失败')` / `message.error('操作失败')` 等无具体信息的错误提示。必须使�?`extractApiError(e)` 提取状态码 + 详情，显示时长不少于 `error_display_duration_sec`（默�?5 秒）
  - **检查范�?*：所有含 try/catch �?API 调用
  - **核心机制**（审查时必须理解）：
    - `extractApiError(e)` 工具函数位于 `frontend/src/utils/apiError.ts`，能�?axios 错误中提�?`error.response.status` + `error.response.data.detail` + `error.response.data.message` 等字段，组合成可读的错误信息
    - �?`message.error('保存失败')` 让用户无法判断失败原因（网络错误/参数错误/权限不足/服务异常），无法自助排查
    - 显示时长 < 5 秒会导致用户来不及读完错误信息就被吞掉，特别是包含状态码 + 详情的长文本
    - 错误信息应包含：HTTP 状态码�?01/403/404/500/502/503/504�? 后端返回的具�?detail（如"商品不存�?/"评分必须大于 0"/"权限不足"�?  - **判断信号**（grep 检测）�?    - `grep -nE "message\.error\('保存失败'\)|message\.error\('操作失败'\)|message\.error\('加载失败'\)" frontend/src/pages/**/*.tsx` 命中 �?违规
    - `grep -nE "catch \(.*\) \{ message\.error\('" frontend/src/pages/**/*.tsx` 命中 �?检查是否调�?`extractApiError`
    - `grep -nE "message\.error\(.*\)" frontend/src/pages/**/*.tsx | Select-String -NotMatch "extractApiError"` 命中 �?检�?message.error 是否包含具体信息
    - `grep -nE "message\.error\([^,]+\)$" frontend/src/pages/**/*.tsx` 命中 �?检查是否省略了 duration 参数（应 >= 5 秒）
    - 用户反馈"保存失败但不知道原因" �?必查 catch 块是否用 extractApiError
  - **修复模式**�?    ```typescript
    // �?正确：用 extractApiError 提取具体错误，显�?5 �?    import { extractApiError } from '@/utils/apiError'

    try {
      await taskApi.update(taskId, payload)
      message.success('保存成功')
    } catch (e) {
      message.error(extractApiError(e), 5)  // 显示 "400: search_config 字段必须是对�?
    }

    // 禁止：无具体信息的错误提示（'保存失败' 用户不知道为什么失败）

    // 禁止：显示时长过短（默认 3 秒，长文本来不及读）

    // 禁止：直接用 error.message 丢失状态码（只�?"Request failed with status code 400"，没�?detail�?    ```
  - **配置参数**：`frontend_error_handling` 节点（在 `config.yaml` 管理，不硬编码）�?    - `enabled`（默�?`true`，开关本检查）
    - `error_display_duration_sec`（默�?`5`，错误提示最小显示时长，秒）
    - `required_error_extractor`（默�?`"extractApiError"`，强制使用的错误提取工具函数名）
    - `forbidden_error_patterns`（默�?`["保存失败", "操作失败", "加载失败", "提交失败", "请求失败"]`，禁止使用的笼统错误文案列表�?    - `required_fields_in_message`（默�?`["status_code", "detail"]`，错误信息中必须包含的字段）
    - `extractor_function_path`（默�?`"frontend/src/utils/apiError.ts"`，extractApiError 函数所在路径）
    - `detection_signals`（默�?`["message.error('", "catch (e) { message.error", "message.error(e.message)"]`，触发检查的代码模式�?  - **适用场景**：所有含 try/catch �?API 调用（保�?更新/删除/查询/批量操作/SSE 错误处理�?  - **不适用场景**：非 API 错误（如本地计算错误、表单验证错误、本�?storage 读写错误）；开发环境调试信息（`console.error`）；用户主动取消操作（`message.info('已取�?)`）；表单客户端校验错误（`form.setFields([{ errors: [...] }])`�?  - **历史教训**：任务级配置覆盖功能开发时，保存接�?catch 块用 `message.error('保存失败')`，用户反�?清除覆盖不生�?但前端只显示"保存失败"，无法定位是 400（参数错误）还是 500（服务异常）还是 401（登录过期）。修复方式：改为 `message.error(extractApiError(e), 5)`，显示具体状态码 + 后端 detail（如"400: search_config 必须显式�?null 才能清除覆盖"），用户能自助排�?  - **对应后端原则**：后�?API 必须返回结构化错误响应（�?`detail` + `error_code` + `status_code`），禁止只返�?`{"detail": "Internal Server Error"}`，详�?`xianyu-backend-code-review` �?`B-REVIEW-ERROR-RESPONSE-STRUCTURE`（如有）

### 25. 端到端失败原因链前端侧同步原�?🆕v4.27

基于"Failed to collect item detail: page unavailable or login expired"根因复盘（代码被回退 + 服务未重启双重原因导致修复未生效），系统化梳理前端在端到端失败原因链中的同步原则。本维度不直接处理后端失败原因传�?数据完整性预检/合并写入等后端逻辑，但前端作为错误展示方与 API 调用方，必须遵循以下 3 项同步原则，确保前后端错误处理契约一致�?
- 🆕v4.27【强制�?*F-REVIEW-ERROR-CODE-BRANCH：错误展示按 error_code 字段分支**
  - 维度�?5 端到端失败原因链前端侧同步原�?  - 严重等级：error
  - **检查点**：前�?catch 块中处理后端错误响应时，是否�?`error_code` 字段分支决策（重�?降级/提示用户操作）而非按文案子串判�?  - **判定标准**�?*禁止** `if (msg.includes('expired'))` / `if (detail.indexOf('unavailable') !== -1)` / `if (err.message === '页面不可�?)` 等子串匹配模式。必须改�?`switch (err.error_code) { case 'token_invalid': ...; case 'page_unavailable': ...; case 'rate_limited': ... }`，分支逻辑与后�?`failure_reason_propagation.reason_enum` 一一对应（命名风格以后端为准，统一 lower_snake_case�?  - **检查范�?*：所有消费后端错误响应的前端 catch 块（API 调用、SSE 错误事件、批量操作错误处理）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.27.0 �?HTTPException �?detail 改为结构�?`{'error_code': 'XXX', 'message': '...'}`，禁止用字符串子串做日志降级 marker（后�?B-REVIEW-FAILURE-REASON-PROPAGATION�?    - 前端若按文案子串判断，后端调整文案后前端逻辑会失效（如后端把"login expired"改为"会话已过�?，前端的 `includes('expired')` 不再命中�?    - error_code 是稳定的契约接口，文案是可变的人类可读描述，前端必须依赖前者而非后�?    - �?F-REVIEW-ERROR-CODE-CONSUMPTION（维�?20）配合：F-REVIEW-ERROR-CODE-CONSUMPTION 关注"是否决策重试/降级"，F-REVIEW-ERROR-CODE-BRANCH 关注"如何识别错误类型（按 error_code 而非文案子串�?
  - **判断信号**（grep 检测）�?    - `grep -nE "if\s*\(\s*\w+\.(message|detail|msg)\.includes\(" frontend/src/**/*.tsx` 命中 �?检查是否在判断后端错误类型
    - `grep -nE "\.(indexOf|search|match)\(['\"](expired|unavailable|rate limited|page unavailable|login expired)" frontend/src/**/*.tsx` 命中 �?违规（按文案子串判断错误类型�?    - `grep -nE "switch\s*\(\s*\w+\.error_code\s*\)" frontend/src/**/*.tsx` 未命�?�?检查是否有�?error_code 分支的实�?    - 用户反馈"后端改了错误文案后前端行为异�? �?必查前端是否按文案子串判断错误类�?  - **修复模式**�?    ```typescript
    // �?正确：按 error_code 字段分支
    import type { ApiErrorResponse } from '@/api/types'

    try {
      await collectionApi.collectItem(itemId)
    } catch (e) {
      const err = e.response?.data as ApiErrorResponse
      switch (err?.error_code) {
        case 'token_invalid':
          message.warning('令牌已失效，请重新获�?)
          break
        case 'page_unavailable':
          message.error('页面不可用，可能需要重新登�?)
          break
        case 'rate_limited':
          message.warning('操作过于频繁，请稍后重试')
          break
        default:
          message.error(extractApiError(e), 5)
      }
    }

    // 禁止：按文案子串判断（后端改文案后失效）
    ```
  - **配置参数**：`failure_reason_chain_frontend` 节点（在 `config.yaml` 管理，不硬编码）�?    - `enabled`（默�?`true`，开关本检查）
    - `required_error_code_field`（默�?`"error_code"`，后端错误响应中必须包含的错误码字段名）
    - `forbidden_substring_markers`（默�?`["expired", "unavailable", "rate limited", "page unavailable", "login expired"]`，禁止用于判断错误类型的文案子串列表�?    - `required_branch_pattern`（默�?`"switch.*error_code"`，必须使用的分支模式正则�?    - `backend_reason_enum_source`（默�?`"xianyu-backend-code-review.failure_reason_propagation.reason_enum"`，后�?reason 枚举来源，确保前后端契约对齐�?    - `detection_signals`（默�?`[".includes('expired'", ".indexOf('unavailable'", ".match(/rate limited/i)"]`，触发检查的代码模式�?  - **适用场景**：所有消费后端错误响应的前端 catch 块（API 调用/SSE 错误事件/批量操作错误处理）；后端已实现结构化 error_code 字段的接口；需要按错误类型做不�?UI 反馈的场景（重试/降级/引导用户操作�?  - **不适用场景**：纯前端错误（表单校验错误、本地计算错误、本�?storage 读写错误）；后端未实�?error_code 字段的旧接口（应推动后端补齐）；网络层错误（�?axios 超时�?response.body，应�?F-REVIEW-ERROR-CONTRACT-TIMEOUT �?`isAxiosTimeout()` 识别�?  - **历史教训**：闲鱼详情采集接口返�?`{"detail": "Failed to collect item detail: page unavailable or login expired"}`，前端按 `detail.includes('expired')` 判断�?登录过期"引导用户重新登录，但实际根因可能是页面不可用（非登录问题）。后端将 detail 改为结构�?`{"error_code": "page_unavailable", "message": "..."}` 后，前端子串判断失效。修复方式：前端改为�?`error_code` 分支，与后端 reason_enum 一一对应
  - **对应后端原则**：后端必须返回结构化错误响应�?`error_code` 字段，禁止用字符串子串做日志降级 marker，详�?`xianyu-backend-code-review` v4.27.0 �?`B-REVIEW-FAILURE-REASON-PROPAGATION` / `B-REVIEW-ERROR-MESSAGE-CONSTANT`

- 🆕v4.27【强制�?*F-REVIEW-PRECHECK-API-DELEGATION：数据完整性预检委托后端**
  - 维度�?5 端到端失败原因链前端侧同步原�?  - 严重等级：warning
  - **检查点**：前端调用后�?API 前若需预检数据完整性（�?cookie 数量是否足够、关键字段是否非空），是否调用后端预检端点而非前端自行判断
  - **判定标准**�?*禁止**前端自行实现数据完整性预检逻辑（如 `if (cookies.length < 10)` / `if (!cookie.token)` / `if (!item.title || !item.price)`）。必须调用后端预检端点（如 `/api/cookies/precheck` / `/api/items/<id>/precheck`）获取预检结果，前端仅根据预检结果�?`passed` 字段决定是否继续调用主接�?  - **检查范�?*：所有调用需预检的后�?API 的前端代码路径（采集前预检 cookie、提交前预检表单完整性、批量操作前预检数据状态）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.27.0 起数据完整性预检方法签名统一�?`async def _check_xxx_completeness(self) -> str | None`，返�?None 表示通过、字符串表示错误描述（后�?B-REVIEW-DATA-COMPLETENESS-PRECHECK�?    - 后端预检使用双阈�?AND 判断（总数 + 关键项命中数），前端不具备后端业务规则的完整上下文（如哪些字段是"关键�?、阈值由业务场景决定�?    - 前端自行判断会与后端预检逻辑不一致，导致前端通过预检但后端拒绝（或反之）
    - 前端预检的职责是"调用预检端点 + 展示预检结果 + 引导用户修复"，不�?实现预检逻辑"
  - **判断信号**（grep 检测）�?    - `grep -nE "if\s+\(?\s*\w+\.length\s*<\s*\d+" frontend/src/**/*.tsx` 命中 �?检查是否在判断后端数据完整�?    - `grep -nE "if\s+\(?\s*!\w+\.(token|cookies|title|price)" frontend/src/**/*.tsx` 命中 �?检查是否在前端判断后端字段完整�?    - `grep -nE "/api/\w+/precheck" frontend/src/api/**/*.ts` 未命�?�?检查是否有调用后端预检端点
    - 用户反馈"前端预检通过但后端拒�? �?必查前端是否自行实现预检逻辑
  - **修复模式**�?    ```typescript
    // �?正确：调用后端预检端点
    try {
      const precheck = await collectionApi.precheckItem(itemId)
      if (!precheck.passed) {
        message.warning(precheck.reason)  // �?"cookie 数量不足�?/22），请重新登�?
        return
      }
      await collectionApi.collectItem(itemId)  // 预检通过才调用主接口
    } catch (e) {
      message.error(extractApiError(e), 5)
    }

    // 禁止：前端自行判断（与后端预检逻辑可能不一致，阈值硬编码�?    ```
  - **配置参数**：`failure_reason_chain_frontend` 节点（在 `config.yaml` 管理，不硬编码）�?    - `precheck_endpoint_pattern`（默�?`"/api/<resource>/precheck"`，后端预检端点�?URL 模式�?    - `precheck_result_field`（默�?`"passed"`，预检结果中是否通过的字段名�?    - `precheck_reason_field`（默�?`"reason"`，预检结果中失败原因的字段名）
    - `forbidden_frontend_precheck_patterns`（默�?`["length < \\d+", "!\\w+\\.token", "!\\w+\\.title"]`，禁止前端自行实现的预检模式�?    - `backend_precheck_method_source`（默�?`"xianyu-backend-code-review.data_completeness_precheck.method_name_pattern"`，后端预检方法来源，确保前后端契约对齐�?  - **适用场景**：调用需预检的后�?API（采集前预检 cookie、提交前预检表单、批量操作前预检数据状态）；后端已提供预检端点的接口；预检逻辑涉及业务规则（如哪些字段是关键项、阈值由业务场景决定�?  - **不适用场景**：纯前端表单校验（必填字段、格式校验、长度限制，�?antd Form rules 即可）；无需预检的简单查询接口（GET /api/items）；前端可独立判断的非业务规则（�?选择的批量操作数量是否超�?100"�?  - **历史教训**：闲鱼详情采集前前端自行判断 cookie 数量（`if (cookies.length < 4)`），但后端预检阈值是 22（关�?cookie 命中数），前端通过预检但后端仍返回 401。修复方式：前端改为调用 `/api/cookies/precheck` 端点，后端返�?`{"passed": false, "reason": "关键 cookie 命中数不足（4/12�?}`，前端展示原因并引导用户重新登录
  - **对应后端原则**：后端必须提供预检端点 + 预检方法签名统一�?`str | None` + 双阈�?AND 判断，详�?`xianyu-backend-code-review` v4.27.0 �?`B-REVIEW-DATA-COMPLETENESS-PRECHECK`

- 🆕v4.27【强制�?*F-REVIEW-MOCK-FIELD-SET-SYNC：mock 数据完整字段集同�?*
  - 维度�?5 端到端失败原因链前端侧同步原�?  - 严重等级：warning
  - **检查点**：前端单元测�?集成测试�?mock 数据是否覆盖后端 Pydantic 模型的完整字段集，新增后端字段后前端 mock 是否同步补齐
  - **判定标准**�?*禁止**前端 mock 数据仅包含测试用例当前需要的字段（如 `mockItem = { id: 1, title: 'test' }` 但后�?`Item` 模型�?12 个字段）。必须从后端 Pydantic 模型导出完整字段集作�?mock 基线，测试用例在基线�?override 需要的字段。新增后端字段后必须同步更新 mock 基线，避�?测试通过但生产环境类型不一�?
  - **检查范�?*：所有前端单元测�?集成测试中的 mock 数据（API 响应 mock、组�?props mock、Zustand store 初始状�?mock�?  - **核心机制**（审查时必须理解）：
    - 后端 v4.27.0 起测�?mock 必须覆盖完整字段集（后端 B-REVIEW-TEST-MOCK-SYNC），前端同样需要同�?    - 前端 mock 数据不完整会导致：测试通过但生产环境访问未 mock 的字段时类型报错；TS 类型检查可能因 mock 类型断言绕过；新增后端字段后前端未同�?mock 会导致测试用例无法覆盖新字段逻辑
    - 后端 Pydantic 模型是字段集的唯一真实来源（single source of truth），前端 mock 必须与之一�?    - 前端可通过 `api/types.ts` 中声明的接口反推字段集，�?`api/types.ts` 必须与后�?Pydantic 模型同步（F-REVIEW-TYPE-CONTRACT-ALIGN�?  - **判断信号**（grep 检测）�?    - `grep -nE "const\s+mock\w+\s*=\s*\{\s*id:" frontend/src/**/*.test.tsx` 命中 �?检�?mock 是否仅包含部分字�?    - `grep -nE "as\s+(Item|Task|Order|Config)\b" frontend/src/**/*.test.tsx` 命中 �?检查是否用 `as` 类型断言绕过字段完整性检�?    - 后端新增字段�?`git diff frontend/src/api/types.ts` 无变�?�?前端类型未同步，mock 必然也不完整
    - 用户反馈"测试通过但生产环境类型报�? �?必查前端 mock 是否覆盖完整字段�?  - **修复模式**�?    ```typescript
    // �?正确：从完整字段集基�?override
    // frontend/src/test/mocks/itemMocks.ts
    import type { Item } from '@/api/types'

    // 完整字段集基线（与后�?Item Pydantic 模型一一对应�?    export const mockItemBaseline: Item = {
      id: 1,
      title: 'test item',
      price: 100,
      description: '',
      seller_id: 'seller_001',
      status: 'active',
      created_at: '2026-07-05T10:00:00Z',
      updated_at: '2026-07-05T10:00:00Z',
      // ... 所有后�?Item 模型字段
    }

    // 测试用例在基线上 override 需要的字段
    const mockItem: Item = { ...mockItemBaseline, status: 'completed' }

    // 禁止：仅包含测试用例当前需要的字段（as 绕过类型检查）
    ```
  - **配置参数**：`failure_reason_chain_frontend` 节点（在 `config.yaml` 管理，不硬编码）�?    - `mock_field_set_source`（默�?`"backend_pydantic_model"`，mock 字段集的真实来源�?    - `require_baseline_file`（默�?`true`，是否要求集中管�?mock 基线文件�?    - `baseline_file_path`（默�?`"frontend/src/test/mocks/"`，mock 基线文件目录�?    - `forbidden_partial_mock_patterns`（默�?`["as\\s+(Item|Task|Order|Config)\\b", "const\\s+mock\\w+\\s*=\\s*\\{\\s*id:"]`，禁止的部分 mock 模式�?    - `backend_mock_sync_source`（默�?`"xianyu-backend-code-review.test_mock_synchronization.scenario_full_field_sets"`，后�?mock 字段集来源，确保前后�?mock 一致）
    - `detection_signals`（默�?`["as Item", "as Task", "const mock.*=.*{id:"]`，触发检查的代码模式�?  - **适用场景**：前端单元测�?集成测试中的 mock 数据；后�?Pydantic 模型新增字段后前�?mock 同步；TS 严格模式下需�?mock 数据类型完整才能通过编译的场�?  - **不适用场景**：纯前端工具函数测试（无后端模型对应）；只测试组件渲染逻辑�?storybook 故事（可仅传必要 props）；快速原型验证阶段的临时 mock（但需�?PR 前补齐）
  - **历史教训**：闲鱼详情采集接口新�?`failure_reason` 字段后，前端测试 mock 未同步补齐，导致前端 catch 块访�?`err.failure_reason` 时在测试环境�?`undefined`，测试通过但生产环境逻辑分支未覆盖。修复方式：建立 `frontend/src/test/mocks/` 目录集中管理 mock 基线，新增后端字段后同步更新基线文件
  - **对应后端原则**：后端测�?mock 必须覆盖完整字段�?+ 集中管理，详�?`xianyu-backend-code-review` v4.27.0 �?`B-REVIEW-TEST-MOCK-SYNC`

### 27. 业务关键字常量集中管理与字段名大小写敏感 🆕v4.31

基于 2026-07-05 解决�?3 类前端反模式复盘（业务文案硬编码 / 事件类型前缀过滤 / 字段名大小写不一致），系统化梳理前端在业务关键字与字段契约层面的同步原则。本维度强调"前端业务关键字常量必须从后端配置拉取 + 事件类型过滤必须 === 精确匹配 + 前后端字段名大小写敏感对�?，确保前后端业务规则一致性�? 项检查点对应 `xianyu-hunter-dev` 编码规范 step 129/130/131�?
- 🆕v4.31【强制�?*F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION：业务关键字常量集中管理**
  - 维度�?7 业务关键字常量集中管理与字段名大小写敏感
  - 严重等级：error
  - **检查点**：前端使用业务关键字文案（如"卖掉�?/"已售"/"已下�?等业务状态判定文本）时，是否从后端配置端点（�?`/api/config/text_features`）拉取而非前端硬编�?  - **判定标准**�?*禁止**前端�?`utils/`、`pages/`、`components/` 中硬编码业务关键字中文字面量（如 `const SOLD_KEYWORDS = ['卖掉�?, '已售']`、`if (text.includes('卖掉�?))`）。必须改为从后端配置端点拉取关键字列表，前端通过共享 helper 函数（如 `isItemSoldByText(text)`）调用后端配�?  - **检查范�?*：所有前端业务关键字文本判断（商品售出状态、订单状态、用户角色判定等业务规则文本�?  - **核心机制**（审查时必须理解）：
    - 后端 v4.31.0 起业务关键字常量集中�?`collector_utils.py` �?`SOLD_TEXT_KEYWORDS` + `check_text_sold()` 函数，配置节点为 `config.yaml#external_platform.text_features`
    - 前端硬编码业务关键字会与后端规则不一致（如后端新�?已售�?文案但前端未同步，导致前端展示状态错误）
    - 业务关键字是"业务规则的可配置化入�?，前端不能假设关键字是固定不变的
    - 前端职责�?调用后端配置 + 通过 helper 函数判断"，不�?实现业务规则"
  - **判断信号**（grep 检测）�?    - `grep -nE "const\s+\w*_KEYWORDS?\s*=\s*\[" frontend/src/**/*.{ts,tsx}` 命中 �?检查是否硬编码业务关键字常�?    - `grep -nE "\.includes\(['\"](卖掉了|已售|已下架|已成�?" frontend/src/**/*.{ts,tsx}` 命中 �?违规（硬编码业务关键字判断）
    - `grep -nE "/api/config/text_features" frontend/src/api/**/*.ts` 未命�?�?检查是否有调用后端配置端点
    - 用户反馈"前端判断状态与后端不一�? �?必查前端是否硬编码业务关键字
  - **修复模式**�?    ```typescript
    // �?正确：从后端配置拉取业务关键�?    import { configApi } from '@/api/config'

    let soldKeywords: string[] = ['卖掉�?]  // 兜底默认�?
    async function loadTextFeatures() {
      const features = await configApi.getTextFeatures()
      soldKeywords = features.sold_keywords ?? soldKeywords
    }

    export function isItemSoldByText(text: string): boolean {
      return soldKeywords.some(kw => text.includes(kw))
    }

    // 禁止：前端硬编码业务关键字（与后端规则可能不一致）
    ```
  - **配置参数**：`business_keyword_centralization` 节点（在 `config.yaml` 管理，不硬编码）�?    - `enabled`（默�?`true`，开关本检查）
    - `config_endpoint_pattern`（默�?`"/api/config/text_features"`，后端业务关键字配置端点 URL�?    - `forbidden_hardcoded_patterns`（默�?`["const \\w*_KEYWORDS?\\s*=\\s*\\[", "\\.includes\\(['\"][^'\"]*(卖掉了|已售|已下�?"]`，禁止前端硬编码业务关键字的代码模式�?    - `required_helper_pattern`（默�?`"is\\w+ByText"`，业务关键字判断必须使用的共�?helper 函数命名模式�?    - `backend_keyword_source`（默�?`"xianyu-backend-code-review.business_keyword_centralization.SOLD_TEXT_KEYWORDS"`，后端业务关键字常量来源，确保前后端契约对齐�?  - **适用场景**：前端业务状态判定（商品售出/订单状�?用户角色）、业务关键字文案判断、需要与后端规则保持一致的业务规则文本
  - **不适用场景**：纯前端 UI 文案（如"保存成功"/"加载�?，不涉及业务规则）；前端组件内部状态文本（�?tab 标签）；固定�?UI 提示文案（不依赖后端规则�?  - **历史教训**：闲�?卖掉�?文案判定，后�?`collector_utils.py` 新增"已售�?文案后前�?`utils/soldDetector.ts` 中硬编码�?`['卖掉�?, '已售']` 未同步，导致前端展示商品状态错误（显示"在售"实际已售）。修复方式：前端改为�?`/api/config/text_features` 拉取 sold_keywords 列表，与后端 `SOLD_TEXT_KEYWORDS` 一一对应
  - **对应后端原则**：后端业务关键字常量必须集中�?`collector_utils.py` + `check_text_sold()` 统一入口 + 配置节点 `config.yaml#external_platform.text_features`，详�?`xianyu-hunter-dev` step 129

- 🆕v4.31【强制�?*F-REVIEW-EVENT-TYPE-EXACT-MATCH：事件类型过滤精确匹�?*
  - 维度�?7 业务关键字常量集中管理与字段名大小写敏感
  - 严重等级：error
  - **检查点**：前端按事件类型（event_type）过滤时是否使用 `===` 精确匹配，禁止使�?`startsWith()` / `indexOf()` 前缀匹配
  - **判定标准**�?*禁止** `if (event.type.startsWith('eval.'))` / `if (event.type.indexOf('task.') === 0)` 等前缀匹配模式（除非该前缀是明确的分组分类场景）。必须改为显式枚�?`if (event.type === 'eval.started' || event.type === 'eval.passed')`，或使用 `Set` 集合判断 `if (EVENT_TYPES_TO_HANDLE.has(event.type))`
  - **检查范�?*：所有前端事件类型过滤逻辑（SSE 事件、WebSocket 事件、自定义事件分发、批量事件处理）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.31.0 起事件类型过滤必�?== 精确匹配（step 130），前端 SSE 事件处理同样需要遵�?    - 前缀匹配会误包含子类型事件（�?`startsWith('eval.')` 会误包含 `eval.passed`/`eval.failed`/`eval.error`），导致前端逻辑分支错误
    - 事件类型�?枚举�?而非"前缀分类"，前端必须按枚举值精确匹�?    - 通知事件（如 `notification.created`）与业务事件（如 `task.created`）必须分离处理，禁止用前缀 `startsWith('task.')` 同时匹配业务事件和通知事件
  - **判断信号**（grep 检测）�?    - `grep -nE "\.startsWith\(['\"]\w+\." frontend/src/**/*.{ts,tsx}` 命中 �?检查是否在事件类型前缀匹配
    - `grep -nE "\.indexOf\(['\"]\w+\.\w" frontend/src/**/*.{ts,tsx}` 命中 �?检查是否在事件类型前缀匹配
    - `grep -nE "switch\s*\(\s*\w+\.(type|eventType)" frontend/src/**/*.{ts,tsx}` 未命�?�?检查是否有按事件类�?switch 的实�?    - 用户反馈"前端 SSE 处理了不该处理的事件" �?必查前端是否用前缀匹配事件类型
  - **修复模式**�?    ```typescript
    // �?正确：精确匹�?+ 显式枚举
    const EVENT_TYPES_TO_HANDLE = new Set([
      'eval.started',
      'eval.passed',
      'eval.failed',
    ])

    if (EVENT_TYPES_TO_HANDLE.has(event.type)) {
      handleEvent(event)
    }

    // �?正确：switch case 精确匹配
    switch (event.type) {
      case 'eval.started':
        handleEvalStarted(event)
        break
      case 'eval.passed':
        handleEvalPassed(event)
        break
      // ...
    }

    // 禁止：前缀匹配（误包含子类型）
    ```
  - **配置参数**：`event_type_exact_match` 节点（在 `config.yaml` 管理，不硬编码）�?    - `enabled`（默�?`true`，开关本检查）
    - `forbidden_prefix_patterns`（默�?`["startsWith\\(['\"]\\w+\\.", "indexOf\\(['\"]\\w+\\.\\w"]`，禁止用于事件类型过滤的前缀匹配模式�?    - `required_match_pattern`（默�?`["===", "Set\\.has\\(", "switch.*case"]`，必须使用的精确匹配模式�?    - `notification_event_separation_required`（默�?`true`，是否强制通知事件与业务事件分离处理）
    - `allowed_prefix_grouping_scenarios`（默�?`["statistics_aggregation", "log_filtering"]`，允许前缀匹配的统�?日志场景�?  - **适用场景**：前�?SSE 事件处理、WebSocket 消息处理、自定义事件分发、批量事件处�?  - **不适用场景**：纯统计场景（如"统计 eval.* 类型事件总数"，允许前缀匹配）；日志过滤场景（如"过滤 task.* 类型事件"，允许前缀匹配）；路由前缀匹配（如 `/tasks/*` 路由，是路径前缀而非事件类型�?  - **历史教训**：评估明细页前端�?`event.type.startsWith('eval.')` 过滤 SSE 事件，导�?`eval.passed`/`eval.failed`/`eval.error` 等子类型事件全部进入同一处理分支，前端展�?227+ 条空记录（实际只�?`eval.started` 应该进入此分支）。修复方式：前端改为 `Set<string>` 精确匹配 `eval.started`，与后端事件类型枚举一一对应
  - **对应后端原则**：后端事件类型过滤必�?== 精确匹配 + 通知事件与业务事件分�?+ 前缀分组仅限统计场景，详�?`xianyu-hunter-dev` step 130

- 🆕v4.31【强制�?*F-REVIEW-FIELD-NAME-CASE-SENSITIVE：前后端字段名大小写敏感检�?*
  - 维度�?7 业务关键字常量集中管理与字段名大小写敏感
  - 严重等级：error
  - **检查点**：前端访问后�?API 响应字段时，字段名大小写是否与后�?Pydantic 模型完全一�?  - **判定标准**�?*禁止**前端�?`data.totalForType` 访问后端 `total_for_type` 字段（驼�?下划线混淆）、用 `repo._Session` 访问后端 `_session` 字段（私有属性大小写不一致）。必须严格对齐后�?Pydantic 模型字段名大小写，前�?`api/types.ts` 中声明的字段名必须与后端模型字段名一一对应；禁止用 `as any` 绕过类型检�?  - **检查范�?*：所有前端访问后�?API 响应字段的代码路径（API 响应消费、组�?props 取值、Zustand store 字段读写、测�?mock 数据字段名）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.31.0 起前后端字段名大小写敏感检查规范化（step 131），前端同样需要遵�?    - 后端 Pydantic 模型字段名是契约（如 `total_for_type` snake_case），前端 `api/types.ts` 必须严格对齐
    - 后端私有属性（�?`_session`）大小写敏感，前端通过类型断言访问时必须完全一�?    - 前端�?`as any` 绕过类型检查会掩盖字段名大小写不一致的 bug，必须改为精确类�?+ grep 双向匹配验证
  - **判断信号**（grep 检测）�?    - `grep -nE "as\s+any\b" frontend/src/**/*.{ts,tsx}` 命中 �?检查是否用 `as any` 绕过字段名检�?    - `grep -nE "\.\w*[A-Z]\w*\b" frontend/src/api/**/*.ts` 命中 �?检查前�?API 类型定义中是否有驼峰字段名（后端应为 snake_case�?    - 后端字段重命名后 `git diff frontend/src/api/types.ts` 无变�?�?前端类型未同�?    - 用户反馈"前端字段显示 undefined / 0 / �? �?必查前端字段名大小写是否与后端一�?  - **修复模式**�?    ```typescript
    // �?正确：前端类型与后端 Pydantic 模型一一对应（snake_case�?    interface EvalDetailResponse {
      total: number
      total_for_type: number  // 与后�?Pydantic 模型一�?      items: EvalItem[]
    }

    const data = await api.getEvalDetail()
    console.log(data.total_for_type)  // �?字段名一�?
    // 禁止：字段名大小写不一致（前端误用驼峰 totalForType，与后端 total_for_type 不一致；as any 绕过类型检查导�?undefined�?    ```
  - **配置参数**：`field_name_case_sensitive` 节点（在 `config.yaml` 管理，不硬编码）�?    - `enabled`（默�?`true`，开关本检查）
    - `backend_field_naming_style`（默�?`"snake_case"`，后端字段命名风格）
    - `forbidden_frontend_naming_styles`（默�?`["camelCase", "PascalCase"]`，禁止前端字段命名风格（除非是前端独立字段）�?    - `require_type_sync`（默�?`true`，后端字段变更时前端 types.ts 必须同步�?    - `forbidden_bypass_patterns`（默�?`["as\\s+any\\b", "as\\s+unknown\\s+as"]`，禁止用类型断言绕过字段名检查的模式�?    - `detection_signals`（默�?`["\\.\\w*[A-Z]\\w*\\b", "as\\s+any\\b"]`，触发检查的代码模式�?    - `backend_model_source`（默�?`"xianyu-backend-code-review.field_name_contract.models"`，后�?Pydantic 模型字段名来源，确保前后端契约对齐）
  - **适用场景**：前端访问后�?API 响应字段、前�?API 类型定义、前�?Zustand store 字段读写、前端测�?mock 数据字段�?  - **不适用场景**：前端独立字段（如组件内�?state，不涉及后端契约）；前端 UI 文案常量（不涉及字段名）；前端路由参数（前端独立命名�?  - **历史教训**：评估明细页前端展示"0 �?，根因是前端�?`data.totalForType` 访问后端 `total_for_type` 字段（驼�?vs snake_case 不一致），导�?`data.totalForType` 始终�?`undefined`，前�?`undefined || 0` 显示�?0。同时后�?`ChatbotRepository` 类用 `this._Session` 访问定义�?`this._session` 私有属性（大小写不一致），导�?`AttributeError: 'ChatbotRepository' object has no attribute '_Session'`。修复方式：前端类型定义严格对齐后端 snake_case，私有属性大小写完全一�?  - **对应后端原则**：后端私有属性大小写一�?+ API 字段名前后端契约对齐 + grep 双向匹配验证，详�?`xianyu-hunter-dev` step 131

### 28. 多用户认证上下文隔离 🆕v4.32

基于 2026-07-05 完成�?MU2 Sprint（认证中间件改�?+ CookieStore 扩展 user_id 维度）复盘（使用 Sequential Thinking 8 步复盘法——成功步�?不确定性与失败�?可抽象的固定流程与判断逻辑/适用场景与不适用场景），系统化梳理前端在多用户认证场景下的上下文隔离原则。本维度强调"前端�?user_id 隔离状�?+ 认证 token 通过 httpOnly cookie 传�?+ 401 降级路径明确分离"，确保多用户场景下不发生跨用户污染、认证失败有可操作的恢复路径�? 项检查点对应 `xianyu-hunter-dev` 编码规范 step 134-137（多用户资源隔离 + 认证中间件多路校�?+ 会话 token 安全管理 + 快照与实时数据覆盖决策）�?
- 🆕v4.32【强制�?*F-REVIEW-MULTI-USER-CONTEXT-ISOLATION：多用户上下文隔�?*
  - 维度�?8 多用户认证上下文隔离
  - 严重等级：error
  - **检查点**：前端是否存在按 user_id 维度隔离的状�?缓存/请求路径，避免跨用户数据污染
  - **判定标准**�?*禁止**前端用全局单例 store/缓存承接多用户会话数据。前端从 `/api/auth/me` 获取当前 `user_id` 后，所有用户特定的 API 请求必须显式携带 `user_id` 上下文（通过请求参数、Header 或后�?session 注入），所有用户特定的 Zustand store 必须�?`user_id` 分桶存储（`Record<UserId, UserState>`），用户切换时必须清空旧用户的全局缓存并触�?`invalidate`
  - **检查范�?*：前端所有持有用户特定状态的代码（Zustand store / React Context / localStorage 缓存 / Service Worker 缓存 / SWR/React Query 缓存键）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.32 �?CookieStore �?`cookies_{uid}.json` 分文件存�?+ `_cache: dict[str, tuple[dict, float]]` 分桶缓存（step 134），前端必须同步�?`user_id` 隔离状�?    - 后端中间件三路校验通过后注�?`request.state.user_id`（step 135），前端�?`/api/auth/me` 拿到 `user_id` 后必须传递给所有用户相�?API
    - 多用户切换时未清空缓存会导致跨用户数据泄漏（A 用户的订单列表显示给 B 用户�?    - 前端"全局单例 store 承接多用户数�?是反模式，必须改�?`Record<UserId, UserState>` 分桶或切换时 `store.reset()`
  - **判断信号**（grep 检测）�?    - `grep -nE "user_id" frontend/src/stores/` 未命�?�?检�?Zustand store 是否考虑�?user_id 维度
    - `grep -nE "localStorage\\.(get|set)Item\\(['\"]user_" frontend/src/**/*.{ts,tsx}` 命中 �?检查是否按 user_id 分键存储
    - `grep -nE "useUserStore|useAuthStore" frontend/src/` 命中 �?检查用户切换时是否调用 `reset()` �?`invalidate`
    - 用户反馈"切换账号后看到上一个账号的数据" �?必查前端是否�?user_id 隔离状�?  - **修复模式**�?    ```typescript
    // �?正确：Zustand store �?user_id 分桶
    interface UserScopedState {
      [userId: string]: {
        orders: Order[]
        preferences: UserPreferences
      }
    }

    const useUserStore = create<UserScopedState>((set, get) => ({
      // 默认空对�?    }))

    // 切换用户时清空旧用户缓存
    function onUserSwitch(newUserId: string) {
      // 1. 清空全局 SWR/React Query 缓存
      queryClient.clear()
      // 2. 重置非用户特�?store
      useGlobalStore.getState().reset()
      // 3. 加载新用户数�?      loadUserData(newUserId)
    }

    // 禁止：全局单例 store 承接多用户数据（多用户切换时未清空，A 用户的订单残留显示给 B 用户�?    ```
  - **配置参数**：`multi_user_context_isolation` 节点（在 `config.yaml` 管理，不硬编码）�?    - `enabled`（默�?`true`，开关本检查）
    - `require_user_id_in_store`（默�?`true`，用户特�?store 必须�?user_id 分桶�?    - `require_invalidate_on_user_switch`（默�?`true`，用户切换时必须清空旧用户缓存）
    - `forbidden_global_singleton_patterns`（默�?`["create<.*>\\(\\)\\s*=>\\s*\\(\\{\\s*orders:"\\]`，禁止全局单例承接多用户数据的模式�?    - `user_id_source`（默�?`"/api/auth/me"`，前端获取当�?user_id 的端点）
    - `backend_isolation_source`（默�?`"xianyu-hunter-dev.multi_user_resource_isolation"`，后端资源隔离规范来源，确保前后端契约对齐）
  - **适用场景**：多用户系统（用户切�?多账号管理）、多租户 SaaS、需要按用户隔离缓存/状�?请求的场�?  - **不适用场景**：单用户系统（无用户切换需求）、纯内部工具（无登录态）、纯只读公共数据展示（无用户特定数据�?  - **历史教训**：MU2 Sprint 中后�?CookieStore 升级为按 `cookies_{uid}.json` 分文件存储，但前�?Zustand store 仍用全局单例承接订单/偏好数据，导致用�?A 切换到用�?B 时短暂显�?A 的订单列表（缓存未清空）。修复方式：前端引入 `onUserSwitch` 钩子，调�?`queryClient.clear()` + `useGlobalStore.getState().reset()` 后再加载新用户数�?  - **对应后端原则**：后�?CookieStore �?user_id 分文�?+ 分桶缓存 + 白名单校�?+ SQLite 兜底隔离，详�?`xianyu-hunter-dev` step 134

- 🆕v4.32【强制�?*F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING：认�?token cookie 处理**
  - 维度�?8 多用户认证上下文隔离
  - 严重等级：error
  - **检查点**：前端是否正确处理认�?token �?cookie 传递、`credentials: 'include'` 配置�?01 降级路径
  - **判定标准**�?*禁止**前端将认�?token 存入 `localStorage`（应通过 httpOnly cookie 由后端写入）�?*禁止**fetch/axios 请求遗漏 `credentials: 'include'`（或 axios �?`withCredentials: true`）；**禁止**所有认证失败一律显�?请重新登�?，必须按后端状态码语义区分�?01（未登录，跳登录页）/ 440（Cookie 过期，跳重新登录页）/ 441（Token 过期，调刷新接口�? 403（权限不足，提示无权限）
  - **检查范�?*：前端所�?API 请求代码（fetch/axios/SSE EventSource）、所�?401/403/440/441 错误处理分支、所�?token 存取代码
  - **核心机制**（审查时必须理解）：
    - 后端 v4.32 起中间件三路校验：管理令牌直通（hmac.compare_digest）→ 用户会话查库（verify_session）→ 401（step 135），前端必须配合 cookie 传�?token
    - 后端 `make_auth_response` 在登录成功后通过 `set-cookie` 写入 `xh_token` cookie（httpOnly + samesite=lax + max_age=86400*30），前端无法读取但会自动携带
    - 前端 fetch 必须显式 `credentials: 'include'` 才会携带 cookie；axios 必须�?`withCredentials: true`
    - 后端 SSE 事件需通过 htmx `<meta name="htmx-config">` 配置 `withCredentials` �?EventSource 显式�?`withCredentials: true`
    - 状态码语义精细化（�?v4.27 F-REVIEW-ERROR-CODE-BRANCH 配合）：前端必须�?`error_code` 字段�?HTTP 状态码区分 401/440/441/403 不同降级路径
    - 拦截器层面精确化（与 v4.45 F-REVIEW-154 配合）：axios/fetch 全局响应拦截器跳转登录页必须基于 status + detail 双重校验（`status === 401 && detail === 'Unauthorized'`），禁止仅凭 status 跳转；业�?401（detail 为业务消息）由调用方 catch 处理；详�?config.yaml `interceptor_audit` 配置�?  - **判断信号**（grep 检测）�?    - `grep -nE "fetch\\(" frontend/src/api/**/*.ts` 命中后检查是否包�?`credentials: 'include'`
    - `grep -nE "axios\\.create" frontend/src/api/**/*.ts` 命中后检查是否包�?`withCredentials: true`
    - `grep -nE "localStorage\\.(get|set)Item\\(['\"]xh_token" frontend/src/**/*.{ts,tsx}` 命中 �?违规（token 不应�?localStorage�?    - `grep -nE "EventSource\\(" frontend/src/**/*.{ts,tsx}` 命中后检查是否包�?`withCredentials: true`
    - `grep -nE "401.*登录|401.*login" frontend/src/**/*.{ts,tsx}` 命中 �?检查是否区�?401/440/441/403
    - 用户反馈"频繁被踢出登�?�?刷新页面后丢失登录�? �?必查前端是否正确处理 cookie + credentials
  - **修复模式**�?    ```typescript
    // �?正确：fetch 显式 credentials + 状态码分支
    async function fetchOrders() {
      const resp = await fetch('/api/orders', {
        credentials: 'include',  // 必须显式声明，否则不携带 cookie
      })
      if (resp.status === 401) {
        redirectTo('/login')  // 未登录，跳登录页
        return
      }
      if (resp.status === 440) {
        redirectTo('/relogin')  // Cookie 过期，跳重新登录�?        return
      }
      if (resp.status === 441) {
        await refreshToken()  // Token 过期，调刷新接口
        return fetchOrders()  // 重试
      }
      if (resp.status === 403) {
        message.error('权限不足')  // 已登录但无权�?        return
      }
      return resp.json()
    }

    // �?正确：axios 全局配置 withCredentials
    const api = axios.create({
      baseURL: '/api',
      withCredentials: true,  // 全局配置，所有请求携�?cookie
    })

    // �?正确：htmx meta 配置 credentials（初始化时机可靠�?    // <meta name="htmx-config" content='{"withCredentials": true}'>

    // 禁止：token �?localStorage（XSS 可读取）

    // 禁止：所有认证失败一律跳登录页（未区分语义，用户反复被踢�?    ```
  - **配置参数**：`auth_token_cookie_handling` 节点（在 `config.yaml` 管理，不硬编码）�?    - `enabled`（默�?`true`，开关本检查）
    - `require_credentials_include`（默�?`true`，fetch 必须显式 `credentials: 'include'`�?    - `require_axios_with_credentials`（默�?`true`，axios 必须�?`withCredentials: true`�?    - `forbidden_token_storage`（默�?`["localStorage", "sessionStorage"]`，禁止存�?token 的位置）
    - `status_code_semantics`（默�?`{"401": "redirect_login", "440": "redirect_relogin", "441": "refresh_token", "403": "show_permission_error"}`，状态码到前端动作的映射�?    - `cookie_name`（默�?`"xh_token"`，后端写入的认证 cookie 名称�?    - `cookie_attributes`（默�?`{"httpOnly": true, "samesite": "lax", "max_age": 2592000}`，后�?cookie 属性契约）
    - `backend_auth_source`（默�?`"xianyu-hunter-dev.auth_multi_path_validation"`，后端认证中间件规范来源，确保前后端契约对齐�?  - **适用场景**：所有涉及认证的 API 请求、登�?会话管理、SSE 事件流认证、多角色权限控制
  - **不适用场景**：纯公共 API（无需认证）、第三方 OAuth 回调（按 OAuth 规范处理）、内部微服务间调用（�?cookie 概念�?  - **历史教训**：MU2 Sprint 中后端中间件实现三路校验（管理令�?+ 用户会话 + 401），但前端仍用旧逻辑：所�?401 一律跳登录页，导致用户会话过期（应跳重新登录页）和 Cookie 过期（应刷新 token）也被误判为"未登�?，用户频繁被踢出。同时部�?fetch 请求遗漏 `credentials: 'include'`，导�?cookie 不传递，后端 401 拒绝。修复方式：前端�?`error_code`/状态码分支处理，全局 axios 实例统一配置 `withCredentials: true`，htmx 通过 `<meta>` 配置 credentials
  - **对应后端原则**：后端中间件三路校验 + `make_auth_response` 写入 httpOnly cookie + 状态码语义精细化，详见 `xianyu-hunter-dev` step 135 + step 71（状态码语义精细化）

- 🆕v4.33【强制�?*F-REVIEW-EFFECT-MINIMIZE：useEffect 副作用最小化**
  - 维度�? React 组件规范
  - 严重等级：HIGH
  - **规范引用**：EFFECT-01 useEffect 副作用最小化原则
  - **检查点**：useEffect 是否用于重置用户交互控制的状态、是否应合并而非替换、是否在依赖数组变化时触发不必要的副作用
  - **判定标准**�?*禁止**�?useEffect 联动重置用户交互控制的状态（�?openKeys/expandedKeys/activeKey/open），此类状态应通过 useState 初始�?+ 用户交互回调更新�?*禁止**�?useEffect 替换本应合并的状态更新；useEffect 仅用于订�?取消订阅、事件监听挂�?卸载、外部系统同步等真正的副作用场景
  - **检查范�?*：所�?useEffect 调用，特别是依赖数组包含路由/location/props �?setState 用户交互控制状态的场景
  - **判断信号**（grep 检测）�?    - `grep -nE "useEffect\\(\\s*\\(\\s*\\)\\s*=>\\s*\\{[^}]*set(OpenKeys|ExpandedKeys|ActiveKey|Open)" frontend/src/**/*.{ts,tsx}` 命中 �?违规
    - useEffect 依赖数组包含 `location.pathname` / `url` �?setState 用户控制状�?�?违规
    - 用户反馈"菜单动画闪烁"/"展开状态被重置" �?必查 useEffect 是否联动重置
  - **反模�?*�?    ```typescript
    // 禁止：useEffect 联动重置用户控制�?openKeys，触�?SubMenu 动画遮挡
    ```
  - **修复模式**�?    ```typescript
    // �?正确：useState 初始�?+ 用户交互控制，移�?useEffect 联动
    const [openKeys, setOpenKeys] = useState<string[]>(() => autoOpenKeys)
    // openKeys 完全�?onOpenChange 用户交互控制，不依赖路由变化
    ```
  - **配置参数**：`coding_standards.effect.disallow_reset_user_controlled_state`（默�?`true`，禁�?useEffect 重置用户控制状态）+ `coding_standards.effect.merge_strategy`（默�?`merge_not_replace`，状态更新应合并而非替换�?  - **适用场景**：所有受�?UI 状态（菜单展开/折叠/选中/Tab 激活）、用户交互后状态需要保留的场景
  - **不适用场景**：订阅外�?store（如 Zustand subscribe）、事件监听挂�?卸载、与外部系统（WebSocket/SSE）同�?  - **历史教训**：MainLayout �?useEffect 联动重置 openKeys 导致 SubMenu 动画遮挡，用户操作时菜单闪烁。修复方式：完全移除 useEffect，openKeys �?useState 初始�?+ onOpenChange 用户控制
  - **对应后端原则**：无（纯前端 React 组件规范），规范�?xianyu-hunter-dev/references/coding-rules.md EFFECT-01

- 🆕v4.33【强制�?*F-REVIEW-STATE-ATOMICITY：状态切换原子�?*
  - 维度�? React 组件规范
  - 严重等级：HIGH
  - **规范引用**：STATE-01 状态切换原子性原则（前端�?  - **检查点**：多字段状态切换是否同步更新，避免部分字段更新导致中间不一致状�?  - **判定标准**：涉及多字段状态切换（�?sheet.active/sheet.minimized/sheet.order 三字段联动）时，**禁止**分散更新单个字段导致中间不一致状态，**必须**封装 transition 方法同步更新所有字段，或使用单一状态枚举（�?sheet.status: 'active' | 'minimized' | 'closed'）替代多字段布尔�?  - **检查范�?*：所有涉及多字段状态切换的代码（sheet/workspace/tab/panel 状态管理、对象状态机切换�?  - **判断信号**（grep 检测）�?    - `grep -nE "set\\w+\\(\\s*\\{[^}]*active:\\s*true" frontend/src/**/*.{ts,tsx}` 命中后检查是否同步更�?minimized/order 等关联字�?    - 多字段状态对象的部分更新（`setState({ active: true })` 而非 `setState({ active: true, minimized: false })`）→ 违规
    - 用户反馈"切换 Tab 时短暂出现两个激活状�? �?必查状态切换原子�?  - **反模�?*�?    ```typescript
    // 禁止：只更新 active 忘了 minimized，导�?sheet 同时处于 active + minimized
    ```
  - **修复模式**�?    ```typescript
    // �?正确：封�?transition 方法，同步更新所有关联字�?    const activateSheet = (id: string) => {
      setSheets(prev => prev.map(s => {
        if (s.id === id) return { ...s, active: true, minimized: false }
        return { ...s, active: false }
      }))
    }
    // 或使用单一状态枚举替代多字段布尔�?    type SheetStatus = 'active' | 'minimized' | 'closed'
    ```
  - **配置参数**：无（纯代码模式检查，配置驱动通过 checklist.react_component 开关）
  - **适用场景**：多字段状态联动切换（sheet/tab/panel/workspace）、状态机转换、需要保持一致性的复合状�?  - **不适用场景**：独立单字段状态、无关联的并行状态更新、性能优化的批量更新（已有 React batching 保证�?  - **历史教训**：SheetWorkspace �?`sheet.active = true` 时忘记同�?`sheet.minimized = false`，导�?sheet 同时显示为激活和最小化状态。修复方式：封装 `activateSheet` transition 方法同步更新所有关联字�?  - **对应后端原则**：无（纯前端状态管理），规范源 xianyu-hunter-dev/references/coding-rules.md STATE-01

- 🆕v4.33【强制�?*F-REVIEW-SSE-CONN-MGMT：SSE 连接管理三要�?*
  - 维度�?5 SSE 重连
  - 严重等级：CRITICAL
  - **规范引用**：SSE-01 SSE 连接管理三要�?  - **检查点**：SSE 连接是否同时具备三要素——visibilitychange 监听（页面恢复可见时重建连接）、last_event_id 回放（断线重连时传递最后事�?ID）、最大重试限制（超限后降级轮询）
  - **判定标准**�?*禁止**SSE 无限重连（必须配�?max_reconnect_attempts，超限后退化为轮询）；**必须**监听 visibilitychange 事件在页面恢复可见时重建连接�?*必须**在重连时通过 `?last_event_id=` 参数传递最后事�?ID 启用服务端回�?  - **检查范�?*：所�?EventSource / useEventSource 调用，SSE 重连逻辑，visibilitychange 事件监听
  - **判断信号**（grep 检测）�?    - `grep -nE "new EventSource\\(" frontend/src/**/*.{ts,tsx}` 命中后检查是否包�?visibilitychange 监听
    - `grep -nE "addEventListener\\('error'[\\s\\S]*setTimeout\\(connect" frontend/src/**/*.{ts,tsx}` 命中后检查是否有 MAX_RECONNECT 限制
    - `grep -nE "EventSource\\([^)]*\\)" frontend/src/**/*.{ts,tsx}` 命中后检查是否包�?`?last_event_id=` 参数
    - 用户反馈"SSE 频繁重连但不恢复" / "页面切回后事件丢�? �?必查三要素完整�?  - **反模�?*�?    ```typescript
    // 禁止：SSE 无限重连，无最大重试限制，�?visibilitychange 监听
    ```
  - **修复模式**�?    ```typescript
    // �?正确：visibilitychange 监听 + last_event_id 回放 + 最大重�?10 �?+ 降级轮询
    const MAX_RECONNECT = 10
    let reconnectCount = 0
    const connect = () => {
      const lastEventId = localStorage.getItem('xh_sse_last_event_id') || ''
      const es = new EventSource(`/api/events/stream?last_event_id=${lastEventId}`)
      es.addEventListener('open', () => { reconnectCount = 0 })
      es.addEventListener('error', () => {
        es.close()
        if (reconnectCount >= MAX_RECONNECT) {
          startPollingFallback()  // 降级轮询
          return
        }
        reconnectCount++
        setTimeout(connect, 3000 * reconnectCount)
      })
    }
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        reconnectCount = 0
        connect()
      }
    })
    ```
  - **配置参数**：`coding_standards.sse.max_reconnect_attempts`（默�?`10`，最大重连次数）+ `coding_standards.sse.polling_fallback_interval`（默�?`30`，降级轮询间隔秒数）+ `coding_standards.sse.visibility_reconnect`（默�?`true`，必须监�?visibilitychange�?  - **适用场景**：所有使�?SSE 的实时数据推送（事件�?通知�?状态变更推送）、长连接场景
  - **不适用场景**：WebSocket（有自己的重连机制）、短连接轮询、一次性事件订�?  - **历史教训**：SSE 连接在网络抖动时无限重连导致服务器压力，且页面切到后台再切回时事件丢失。修复方式：增加最大重�?10 次限�?+ visibilitychange 监听 + last_event_id 回放
  - **对应后端原则**：后�?SSE 端点必须支持 `?last_event_id=` 参数启用事件回放，规范源 xianyu-hunter-dev/references/coding-rules.md SSE-01

- 🆕v4.33【强制�?*F-REVIEW-ASYNC-RACE-GUARD：异步竞态防�?*
  - 维度�?0 Hooks 设计模式
  - 严重等级：HIGH
  - **规范引用**：RACE-01 异步竞态防�?  - **检查点**：异步请求是否用 useRef 维护最新请�?ID，响应回来时对比 ID 决定是否更新状�?  - **判定标准**�?*禁止**异步请求完成直接更新状态（无请�?ID 对比），**必须**�?useRef 维护最新请�?ID，响应回来时对比 ID，若不一致则丢弃响应（避免旧响应覆盖新响应）
  - **检查范�?*：所有异步请求（fetch/axios）触发的状态更新，特别是搜�?筛�?分页等用户可快速连续触发的场景
  - **判断信号**（grep 检测）�?    - `grep -nE "async\\s+function\\s+\\w+[\\s\\S]{0,500}set\\w+\\(.*\\)" frontend/src/**/*.{ts,tsx}` 命中后检查是否有 requestId 对比
    - `grep -nE "useRef\\(.*requestId" frontend/src/**/*.{ts,tsx}` 未命�?�?检查异步请求是否缺少竞态防�?    - 用户反馈"快速切换筛选条件后显示旧数�? / "搜索结果与关键词不匹�? �?必查异步竞态防�?  - **反模�?*�?    ```typescript
    // 禁止：异步请求完成直接更新状态，无请�?ID 对比（旧响应可能覆盖新响应）
    ```
  - **修复模式**�?    ```typescript
    // �?正确：useRef 维护最新请�?ID，响应回来时对比
    const latestRequestId = useRef(0)
    const search = async (keyword: string) => {
      const requestId = ++latestRequestId.current
      const resp = await fetch(`/api/search?keyword=${keyword}`)
      const data = await resp.json()
      if (requestId !== latestRequestId.current) return  // 丢弃过期响应
      setResults(data)
    }
    ```
  - **配置参数**：`coding_standards.race.check_request_id`（默�?`true`，必须用 useRef 维护请求 ID 对比�?  - **适用场景**：用户可快速连续触发的异步请求（搜�?筛�?分页/排序）、并发请求可能返回顺序不一致的场景
  - **不适用场景**：单次提交（如保�?删除，无连续触发）、请求顺序天然保证的场景（如 await 链式调用�?  - **历史教训**：搜索框快速输入时，前一个请求的响应覆盖后一个请求的响应，导致显示与关键词不匹配的结果。修复方式：引入 useRef 维护最新请�?ID
  - **对应后端原则**：无（纯前端竞态防护），规范源 xianyu-hunter-dev/references/coding-rules.md RACE-01

- 🆕v4.33【强制�?*F-REVIEW-THEME-DYNAMIC-ADAPT：主题色动态适配**
  - 维度�? AntD 5 主题规范
  - 严重等级：HIGH
  - **规范引用**：THEME-01 主题色动态适配
  - **检查点**：是否硬编码颜色值、是否根�?isDark 动态设置主题相�?token
  - **判定标准**�?*禁止**硬编码颜色值（特别是主题相�?token �?rowHoverBg/headerBg/headerColor），**必须**根据 isDark 动态设置；显式指定的主�?token 必须�?ThemedRoot 内按 isDark 覆盖（与 v4.8 F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE 配合�?  - **检查范�?*：所�?components.<Component>.<token> 配置、内联样式中的颜色值、CSS 变量定义
  - **判断信号**（grep 检测）�?    - `grep -nE "components\\.[A-Z]\\w+\\.\\w*(?:Color|Bg|Border|Hover|Active|Focus)\\s*:\\s*['\"]#[0-9a-fA-F]+['\"]" frontend/src/**/*.{ts,tsx}` 命中 �?违规（硬编码颜色�?    - `grep -nE "rowHoverBg|headerBg|headerColor" frontend/src/**/*.{ts,tsx}` 命中后检查是否根�?isDark 动态设�?    - 暗色模式下用户反�?文字看不�?/"背景太亮" �?必查主题色动态适配
  - **反模�?*�?    ```typescript
    // 禁止：硬编码 rowHoverBg，暗色模式不可读
    ```
  - **修复模式**�?    ```typescript
    // �?正确：根�?isDark 动态设�?    const themeConfig = {
      components: {
        Table: {
          rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : '#fff7f0'
        }
      }
    }
    ```
  - **配置参数**：`coding_standards.theme.disallow_hardcoded_colors`（默�?`true`，禁止硬编码主题色）+ `coding_standards.theme.colors.light`（浅色主题色映射�? `coding_standards.theme.colors.dark`（暗色主题色映射�?  - **适用场景**：所有支持暗色主题的组件、显式指定的主题 token、内联样式中的颜色�?  - **不适用场景**：纯亮色主题应用（无暗色模式）、第三方组件内部样式（无法控制）、品牌固定色（如 logo 颜色�?  - **历史教训**：Table 组件硬编�?`rowHoverBg: '#fff7f0'`，暗色模式下用户无法看清 hover 行。修复方式：改为 `isDark ? 'rgba(255,98,0,0.08)' : '#fff7f0'`
  - **对应后端原则**：无（纯前端主题规范），规范�?xianyu-hunter-dev/references/coding-rules.md THEME-01

- 🆕v4.33【强制�?*F-REVIEW-EMBEDDED-LAYOUT-HEIGHT：嵌入式布局高度**
  - 维度�? React 组件规范
  - 严重等级：HIGH
  - **规范引用**：LAYOUT-01 嵌入式布局高度
  - **检查点**：嵌入框架页面（�?iframe / Electron / 浏览器扩展弹窗）是否�?`height: 100%` + `flex: 1`，禁�?`minHeight: 100vh`
  - **判定标准**�?*禁止**在嵌入式场景使用 `minHeight: '100vh'`（会撑满整个视口而非容器，导致全屏溢出）�?*必须**使用 `height: '100%'` + `flex: 1` 适配父容器高�?  - **检查范�?*：所有页�?布局组件的样式，特别是嵌�?iframe / Electron / 浏览器扩展弹窗的场景
  - **判断信号**（grep 检测）�?    - `grep -nE "minHeight:\\s*['\"]100vh['\"]|minHeight:\\s*['\"]100vh['\"]" frontend/src/**/*.{ts,tsx}` 命中 �?检查是否为嵌入式场�?    - `grep -nE "height:\\s*['\"]100%['\"]" frontend/src/**/*.{ts,tsx}` 未命�?�?检查嵌入式布局是否缺少 height:100%
    - 用户反馈"页面撑满整个浏览器窗�? / "iframe 内出现滚动条" �?必查嵌入式布局高度
  - **反模�?*�?    ```typescript
    // 禁止：嵌�?iframe 使用 minHeight: '100vh'，撑满视口导致全�?    ```
  - **修复模式**�?    ```typescript
    // �?正确：使�?height: '100%' + flex: 1 适配父容�?    const PageContainer = styled.div`
      height: '100%';
      flex: 1;
      overflow: auto;
    `
    ```
  - **配置参数**：`coding_standards.layout.disallow_minheight_100vh_in_embedded`（默�?`true`，嵌入式场景禁止 minHeight:100vh�?  - **适用场景**：嵌�?iframe / Electron / 浏览器扩展弹�?/ 桌面应用 webview 的页面布局
  - **不适用场景**：独立网页（非嵌入）、需要撑满视口的落地�?营销页、移动端 H5（视口适配�?  - **历史教训**：闲鱼猎人前端嵌�?iframe 时使�?`minHeight: '100vh'`，导致页面撑满整个浏览器窗口而非 iframe 容器，出现全屏溢出。修复方式：改为 `height: '100%'` + `flex: 1`
  - **对应后端原则**：无（纯前端布局规范），规范�?xianyu-hunter-dev/references/coding-rules.md LAYOUT-01

- 🆕v4.33【强制�?*F-REVIEW-COMPONENT-REGISTRY：组件注册完整�?*
  - 维度�? React 组件规范
  - 严重等级：HIGH
  - **规范引用**：REGISTRY-01 组件注册完整�?  - **检查点**：ECharts / antd 等需�?register 的组件是�?import + register，避免使用未注册组件导致静默失败
  - **判定标准**�?*禁止**使用未注册的组件（如 ECharts �?FunnelChart / LineChart / BarChart / PieChart 等）�?*必须**在使用前 `import` + `use()` 注册所有用到的组件；组件注册应集中在入口文件（�?`echarts.setup.ts`�?  - **检查范�?*：所�?ECharts 组件使用（`<FunnelChart />` / `<LineChart />` 等）、antd 按需加载配置、其他需�?register 的库
  - **判断信号**（grep 检测）�?    - `grep -nE "<(FunnelChart|LineChart|BarChart|PieChart|MapChart|HeatmapChart)" frontend/src/**/*.{ts,tsx}` 命中后检查对�?import + use 注册
    - `grep -nE "echarts\\.(register|use)\\(" frontend/src/**/*.{ts,tsx}` 命中后核对注册的组件列表是否覆盖所有使�?    - 用户反馈"图表不显�?/"组件渲染空白无报�? �?必查组件注册完整�?  - **反模�?*�?    ```typescript
    // 禁止：使�?FunnelChart 但未注册，静默失败（图表不显示无报错�?    ```
  - **修复模式**�?    ```typescript
    // �?正确：import + register 所有用到的组件
    import * as echarts from 'echarts/core'
    import { FunnelChart } from 'echarts/charts'
    import { TooltipComponent, GridComponent } from 'echarts/components'
    import { CanvasRenderer } from 'echarts/renderers'
    
    echarts.use([FunnelChart, TooltipComponent, GridComponent, CanvasRenderer])
    ```
  - **配置参数**：`coding_standards.registry.check_components`（默�?`[FunnelChart, LineChart, BarChart, PieChart]`，需要检查注册的组件列表�?  - **适用场景**：所有使�?ECharts / antd / Mobx 等需�?register 的库的组�?  - **不适用场景**：使用全量引入（`import * as echarts from 'echarts'`，自动注册所有组件）、不涉及 register 的库
  - **历史教训**：使�?FunnelChart 但未注册，导致图表静默失败（无报错但不显示），用户反�?图表空白"才定位到问题。修复方式：建立 `echarts.setup.ts` 集中注册所有用到的组件
  - **对应后端原则**：无（纯前端组件注册），规范�?xianyu-hunter-dev/references/coding-rules.md REGISTRY-01

- 🆕v4.33【强制�?*F-REVIEW-FILTER-TRANSPARENCY：过滤透明�?*
  - 维度�? API 调用规范
  - 严重等级：MEDIUM
  - **规范引用**：FILTER-02 过滤透明�?  - **检查点**：数据被过滤时是否展示过滤原因和条数，避免用户误以为数据丢失
  - **判定标准**�?*禁止**仅显�?获取 N �?而隐藏过滤过程（实际搜到 M 条被过滤�?N 条）�?*必须**展示过滤原因和条数（�?搜到 59 条，按规则过滤后显示 12 �?），通过 Modal / Tooltip / Alert 展示 `filter_summary`
  - **检查范�?*：所有调用后端过滤接口的列表�?搜索�?统计页，特别是显示条数的场景
  - **判断信号**（grep 检测）�?    - `grep -nE "获取\\s*\\d+\\s*条|共\\s*\\d+\\s*�? frontend/src/**/*.{ts,tsx}` 命中后检查是否展�?filter_summary
    - `grep -nE "filter_summary" frontend/src/api/types.ts` 命中后检查前端是否消费该字段
    - 用户反馈"显示获取 0 条但实际有数�? �?必查过滤透明�?  - **反模�?*�?    ```typescript
    // 禁止：显�?获取0�?但实际搜�?59 条被过滤，用户误以为数据丢失
    ```
  - **修复模式**�?    ```typescript
    // �?正确：后端返�?filter_summary，前端用 Modal/Tooltip 展示
    const resp = await fetch('/api/items/search?keyword=xxx')
    const data = await resp.json()
    message.success(`显示 ${data.items.length} 条`)
    if (data.filter_summary) {
      Modal.info({
        title: '过滤结果说明',
        content: `搜到 ${data.filter_summary.total_matched} 条，按规则过滤后显示 ${data.items.length} 条。过滤原因：${data.filter_summary.reason}`
      })
    }
    ```
  - **配置参数**：`coding_standards.filter.summary_enabled`（默�?`true`，必须展示过滤摘要）
  - **适用场景**：所有调用后端过滤接口的列表�?搜索�?统计页、用户可能误解数据完整性的场景
  - **不适用场景**：纯前端过滤（无后端 filter_summary）、无需展示过滤过程的内部统计、数据导出场�?  - **历史教训**：搜索接口显�?获取 0 �?但实际后端搜�?59 条被过滤规则过滤，用户误以为数据丢失。修复方式：后端返回 `filter_summary` 字段，前端用 Modal 展示过滤原因和条�?  - **对应后端原则**：后端必须返�?`filter_summary` 字段�?`total_matched` / `total_filtered` / `reason`，规范源 xianyu-hunter-dev/references/coding-rules.md FILTER-02

- 🆕v4.33【强制�?*F-REVIEW-DATA-SOURCE-VERIFY：数据源正确性验�?*
  - 维度�?8 闲鱼项目规范
  - 严重等级：HIGH
  - **规范引用**：SOURCE-01 数据源正确性验�?  - **检查点**：显示数据是否来自正确数据源，避免误用配置备份文件数等错误数据源
  - **判定标准**�?*禁止**误用数据源（如版本管理显示配置备份文件数 V10 而非系统版本），**必须**从语义对齐的 API 获取数据（如系统版本�?`/api/about` 获取，而非 `/api/config/version` 返回�?`len(backups)`�?  - **检查范�?*：所有显示版�?计数/统计数据的组件，特别是从多个 API 获取类似字段的场�?  - **判断信号**（grep 检测）�?    - `grep -nE "version\\s*[:=]" frontend/src/**/*.{ts,tsx}` 命中后检查数据源是否�?`/api/about`
    - `grep -nE "/api/config/version" frontend/src/**/*.{ts,tsx}` 命中 �?检查是否误用（该接口返�?len(backups)�?    - 用户反馈"版本号显示为 V10 而非实际版本" �?必查数据源正确�?  - **反模�?*�?    ```typescript
    // 禁止：版本管理显�?V10（配置备份文件数而非系统版本�?    ```
  - **修复模式**�?    ```typescript
    // �?正确：从 /api/about 获取系统版本
    const resp = await fetch('/api/about')
    const data = await resp.json()
    setVersion(data.version)  // 系统版本�?    ```
  - **配置参数**：`coding_standards.source.verify_data_source`（默�?`true`，必须验证数据源语义正确性）
  - **适用场景**：所有显示版�?计数/统计数据的场景、从多个 API 获取类似字段的场景、数据源语义可能混淆的场�?  - **不适用场景**：单一明确数据源、内部计数（无歧义）、测�?mock 数据
  - **历史教训**：版本管理页显示 V10，用户以为是系统版本，实际是配置备份文件数。修复方式：�?`/api/about` 获取系统版本，废�?`/api/config/version` 误用
  - **对应后端原则**：后�?`/api/about` 必须返回系统版本字段，规范源 xianyu-hunter-dev/references/coding-rules.md SOURCE-01（与 v4.20 F-REVIEW-VERSION-SOURCE-ALIGN 配合�?
- 🆕v4.33【强制�?*F-REVIEW-STATS-RANGE-CALIBRATE：统计范围校�?*
  - 维度�?6 性能评审
  - 严重等级：MEDIUM
  - **规范引用**：RANGE-01 统计范围校准（前端）
  - **检查点**：统计图表范围是否与业务范围匹配，避免统计范围过大导致图表不可读或误�?  - **判定标准**�?*禁止**统计图表范围过大与业务范围不匹配（如价格直方图统�?0-10000 但任务定价范围仅 0-500），**必须**按业务范围过滤（task_id 过滤�? 百分位校准（P5/P95）确保图表聚焦业务实际范�?  - **检查范�?*：所有统计图表（直方�?折线�?散点图），特别是显示价格/数量/频率等业务指标的图表
  - **判断信号**（grep 检测）�?    - `grep -nE "type:\\s*['\"](histogram|line|scatter)" frontend/src/**/*.{ts,tsx}` 命中后检查统计范围是否与业务范围匹配
    - `grep -nE "min:\\s*\\d+.*max:\\s*\\d+" frontend/src/**/*.{ts,tsx}` 命中后检�?min/max 是否经过业务校准
    - 用户反馈"图表大部分是空白"/"数据集中在角�? �?必查统计范围校准
  - **反模�?*�?    ```typescript
    // 禁止：价格直方图统计范围 0-10000，与任务定价范围 0-500 不匹�?    ```
  - **修复模式**�?    ```typescript
    // �?正确：task_id 过滤 + P5/P95 百分位校�?    const taskPrices = prices.filter(p => p.task_id === currentTaskId)
    const sorted = [...taskPrices].sort((a, b) => a.price - b.price)
    const p5 = sorted[Math.floor(sorted.length * 0.05)].price
    const p95 = sorted[Math.floor(sorted.length * 0.95)].price
    const option = {
      xAxis: { min: p5, max: p95 },  // 聚焦业务实际范围
      series: [{ type: 'histogram', data: taskPrices }]
    }
    ```
  - **配置参数**：无（纯业务逻辑校准，配置驱动通过 checklist.performance 开关）
  - **适用场景**：所有统计图表（直方�?折线�?散点图）、显示业务指标的图表、数据范围可能过大误导决策的场景
  - **不适用场景**：全量数据展示（无范围限制需求）、固定范围仪表盘、实时监控图表（范围动态）
  - **历史教训**：价格直方图统计范围 0-10000，但任务定价范围�?0-500，导致图表大部分空白，用户无法看清分布。修复方式：task_id 过滤 + P5/P95 百分位校准聚焦业务范�?  - **对应后端原则**：无（纯前端图表校准），规范�?xianyu-hunter-dev/references/coding-rules.md RANGE-01

- 🆕v4.33【强制�?*F-REVIEW-UI-SEMANTICS-SPLIT：按钮与状态语义分�?*
  - 维度�? React 组件规范
  - 严重等级：MEDIUM
  - **规范引用**：UI-SEMANTICS-01 按钮与状态语义分�?  - **检查点**：按钮文案是否表达动作（动词）、状态显示是否表达状态（名词/形容词），避免用户误�?  - **判定标准**�?*禁止**按钮文案与状态显示混用（如红�?失效"既是按钮文案又是状态显示，用户无法判断是点击失效还是已失效），**必须**按钮文案表达动作（如"主动失效"/"批量失效"），状态显示表达状态（�?有效"/"已失�?�?  - **检查范�?*：所有按钮文案、状态标�?徽章、操作列按钮
  - **判断信号**（grep 检测）�?    - `grep -nE "<Button[^>]*>[^<]*(失效|有效|启用|禁用)" frontend/src/**/*.{ts,tsx}` 命中后检查文案是动作还是状�?    - `grep -nE "<Tag[^>]*>[^<]*(失效|有效|启用|禁用)" frontend/src/**/*.{ts,tsx}` 命中后检查是否与按钮文案混用
    - 用户反馈"误点了失效按钮以为是状态显�? �?必查按钮与状态语义分�?  - **反模�?*�?    ```typescript
    // 禁止：红�?失效"是按钮而非状态显示，用户误判
    ```
  - **修复模式**�?    ```typescript
    // �?正确：按钮文案表达动作（主动失效），状态显示表达状态（有效/已失效）
    <Space>
      {record.status === 'active' 
        ? <Button danger onClick={handleDisable}>主动失效</Button>
        : <Tag color="default">已失�?/Tag>}
    </Space>
    ```
  - **配置参数**：`coding_standards.ui_semantics.button_text_must_be_action`（默�?`true`，按钮文案必须是动作�? `coding_standards.ui_semantics.status_display_must_be_state`（默�?`true`，状态显示必须是状态）
  - **适用场景**：所有按钮文案、状态标�?徽章、操作列按钮、状态切换控�?  - **不适用场景**：图标按钮（无文案）、纯导航按钮（如"返回"）、确认对话框按钮（如"确定"/"取消"�?  - **历史教训**：列表操作列红色"失效"按钮被用户误以为是状态标签，导致误点击。修复方式：按钮文案改为"主动失效"，状态用 Tag 显示"已失�?
  - **对应后端原则**：无（纯前端 UI 语义），规范�?xianyu-hunter-dev/references/coding-rules.md UI-SEMANTICS-01

- 🆕v4.33【强制�?*F-REVIEW-PERSIST-BUSINESS-SWITCH：用户可配置开关持久化**
  - 维度�?0 Hooks 设计模式
  - 严重等级：HIGH
  - **规范引用**：PERSIST-01 用户可配置开关持久化
  - **检查点**：业务开关（如自动刷�?批量启用/调试模式）是否用 `usePersistentState` 持久化，避免刷新丢失
  - **判定标准**�?*禁止**业务开关用 `useState`（刷新后丢失用户配置），**必须**�?`usePersistentState`（localStorage 持久化）；持久化 key 必须遵循 `xh.<page>.<field>` 命名模式（与 v4.24 F-REVIEW-UI-PREFERENCE-PERSISTENCE 配合�?  - **检查范�?*：所有业务开关（自动刷新/批量启用/调试模式/高级筛�?暗色模式等用户可配置的布�?枚举状态）
  - **判断信号**（grep 检测）�?    - `grep -nE "const\\s+\\[\\s*(autoRefresh|batchEnabled|debugMode|advancedFilter|darkMode)\\s*,\\s*\\w+\\]\\s*=\\s*useState" frontend/src/**/*.{ts,tsx}` 命中 �?违规
    - `grep -nE "usePersistentState\\(\\s*['\"]xh\\." frontend/src/**/*.{ts,tsx}` 未命�?�?检查业务开关是否缺少持久化
    - 用户反馈"刷新后开关重置为默认�? �?必查业务开关持久化
  - **反模�?*�?    ```typescript
    // 禁止：业务开关用 useState，刷新丢�?    ```
  - **修复模式**�?    ```typescript
    // �?正确：业务开关用 usePersistentState（localStorage 持久化）
    const [autoRefresh, setAutoRefresh] = usePersistentState<boolean>(
      'xh.dashboard.autoRefresh',
      false,
      { validator: (v) => typeof v === 'boolean' }
    )
    ```
  - **配置参数**：`coding_standards.persist.business_switch_must_persist`（默�?`true`，业务开关必须持久化�? `coding_standards.persist.storage_key_prefix`（默�?`xh.`，持久化 key 前缀�?  - **适用场景**：所有业务开关（自动刷新/批量启用/调试模式/高级筛�?暗色模式等用户可配置状态）
  - **不适用场景**：临时状态（�?loading/visible）、会话状态（�?currentStep）、敏感数据（�?token）、后端已持久化的字段（应从后端获取）
  - **历史教训**：批量刷新的自动刷新开关用 useState，用户刷新页面后开关重置为 false，导致用户需要重新开启。修复方式：改用 usePersistentState 持久化到 localStorage
  - **对应后端原则**：无（纯前端持久化），规范源 xianyu-hunter-dev/references/coding-rules.md PERSIST-01

- 🆕v4.33【强制�?*F-REVIEW-ERROR-MESSAGE-PASS：错误消息透传**
  - 维度�?0 API 数据源一致性与类型契约对齐
  - 严重等级：MEDIUM
  - **规范引用**：ERROR-01 错误消息透传（前端）
  - **检查点**：catch 块是否用 `extractApiError` 提取后端具体错误，避免显示无信息的通用错误
  - **判定标准**�?*禁止**catch 块显示无信息的通用错误（如 `message.error('预览失败')`），**必须**�?`extractApiError` 提取后端具体错误（如 `message.error(extractApiError(err, '预览失败'))`），让用户看到后端根�?  - **检查范�?*：所�?API 调用�?catch 块，特别是显示错误提示的场景
  - **判断信号**（grep 检测）�?    - `grep -nE "catch\\s*\\([^)]*\\)\\s*\\{[^}]*message\\.error\\(['\"][^'\"]*失败['\"]" frontend/src/**/*.{ts,tsx}` 命中 �?违规（无具体错误�?    - `grep -nE "extractApiError" frontend/src/**/*.{ts,tsx}` 未命�?�?检�?catch 块是否缺少错误透传
    - 用户反馈"只显示保存失败，不知道具体原�? �?必查错误消息透传
  - **反模�?*�?    ```typescript
    // 禁止：catch 块显示无具体错误的通用提示
    ```
  - **修复模式**�?    ```typescript
    // �?正确：用 extractApiError 提取后端具体错误
    try {
      await previewFile(id)
    } catch (err) {
      message.error(extractApiError(err, '预览失败'))
      // 显示�?预览失败：文件不存在"�?预览失败：权限不�?
    }
    ```
  - **配置参数**：`coding_standards.error.require_extract_api_error`（默�?`true`，catch 块必须用 extractApiError�?  - **适用场景**：所�?API 调用�?catch 块、显示错误提示的场景、用户需要知道错误根因的操作
  - **不适用场景**：纯前端错误（如表单校验）、网络层错误（无后端响应）、测�?mock
  - **历史教训**：文件预览失败时只显�?预览失败"，用户不知道是文件不存在还是权限不足，无法定位问题。修复方式：�?`extractApiError` 提取后端具体错误透传给用�?  - **对应后端原则**：后端必须返回结构化错误响应�?`error_code` + `message` 字段（与 v4.27 F-REVIEW-ERROR-CODE-BRANCH 配合），规范�?xianyu-hunter-dev/references/coding-rules.md ERROR-01

- 🆕v4.33【强制�?*F-REVIEW-API-CONTRACT-CONSISTENCY：API 契约一致�?*
  - 维度�?1 类型安全评审
  - 严重等级：HIGH
  - **规范引用**：CONTRACT-01 API 契约一致性（前端�?  - **检查点**：TS interface 字段名是否与后端 response_model 一致，避免大小�?命名风格不一致导致数据显示为 0/undefined
  - **判定标准**�?*禁止**TS interface 字段名与后端 response_model 不一致（如后端返�?`total`，前端期�?`total_for_type`），**必须**TS interface 字段名与后端 response_model 完全一致（snake_case �?snake_case）；可选字段用 `field?: T`，可空字段用 `field: T | null`
  - **检查范�?*：所�?`frontend/src/api/types.ts` 中的 interface/type 定义，与后端 Pydantic model 的字段名对比
  - **判断信号**（grep 检测）�?    - `grep -nE "interface\\s+\\w+[\\s\\S]{0,500}?\\s+\\w+:\\s" frontend/src/api/types.ts` 命中后与后端 model 对比字段�?    - `grep -nE "as\\s+any\\b|as\\s+unknown\\s+as" frontend/src/**/*.{ts,tsx}` 命中 �?检查是否绕过类型检查掩盖契约不一�?    - 用户反馈"显示 0 �?/"字段显示 undefined" �?必查 API 契约一致�?  - **反模�?*�?    ```typescript
    // 禁止：后端返�?total，前端期�?total_for_type，导致显�?0 �?    ```
  - **修复模式**�?    ```typescript
    // �?正确：TS interface 字段名与后端 response_model 完全一�?    interface EvaluationResult {
      total: number  // 与后�?Pydantic model 字段名一�?      total_for_type?: number  // 可选字段用 ?，可空字段用 | null
    }
    ```
  - **配置参数**：`coding_standards.contract.check_ts_interface_match`（默�?`true`，必须检�?TS interface 与后�?model 一致性）
  - **适用场景**：所�?API 响应类型定义、前后端字段契约对齐、类型安全检�?  - **不适用场景**：纯前端内部类型（无后端对应）、第三方 API 类型（按第三方文档）、归一化层类型（前后端字段映射�?  - **历史教训**：评估明细页后端返回 `total`，前�?TS interface 期望 `total_for_type`，导致显�?0 条。修复方式：TS interface 字段名与后端 response_model 完全一�?  - **对应后端原则**：后�?Pydantic model 字段名必须稳定，新增字段需同步前端 types.ts（与 v4.16 F-REVIEW-TYPE-CONTRACT-ALIGN 配合），规范�?xianyu-hunter-dev/references/coding-rules.md CONTRACT-01

---

### 29. 数据契约与时序（meta-rules #25-30 落地）🆕v4.34

> 本维度整�?`xianyu-hunter-dev` v4.30.0 �?meta-rules #25-30 前端侧审查要点，新增 6 �?F-REVIEW 检查点（F-REVIEW-110~115）。所有检查点强调配置驱动（参数在 `config.yaml` �?`data_contract_temporal` 节点管理，不硬编码）与适用/不适用场景说明。后端对应规范为 `xianyu-backend-code-review` v4.29.0 维度 31 �?B-REVIEW-151~156�?
- 🆕v4.34【强制�?*F-REVIEW-110: 批量断路器四要素 UI 反馈（batch circuit breaker UI feedback�?*
  - 维度�?9 数据契约与时�?  - 严重等级：error
  - 规范引用：meta-rule #25 批量处理四要�?  - **检查点**：批量操�?UI 必须区分「用户主动停止�?「熔断可恢复�?「异常失败」三态，**禁止**一律显�?操作已取�?�?操作失败"。熔断可恢复态必须展�?`success_count` / `pending_count` / `failure_reason` / `recover_action`（如"重试剩余 12 �?按钮），与后�?`batch_circuit_breaker` 日志文案（`paused/stopped/failed`）一一对应
  - **判断信号**�?    - `grep "message\\.(warning|error)\\(['\"](?:批次已停止|批次失败).*['\"]\\)" frontend/src/**/*.{ts,tsx}` �?视为**必修 P0 缺陷**（缺少可恢复性提示）
    - `grep "Modal\\.confirm.*停止" frontend/src/**/*.{ts,tsx}` �?success_count / pending_count 不展�?�?视为缺恢复信�?  - **配置参数**：`data_contract_temporal.batch_circuit_breaker.failure_threshold`（默�?`3`，与后端 B-REVIEW-151 一致）、`required_state_display`（默�?`[running, paused, failed, completed]`）、`required_pause_info`（默�?`[success_count, pending_count, failure_reason, recover_action]`）在 `config.yaml` 管理
  - **适用**：所有用户可中止的批量操作（批量删除/批量导入/批量上报/批量刷新/批量重试�?  - **不适用**：单�?API 调用、≤3 �?item 的小批量操作、定时后台任务（无用户交互入口）
  - **历史教训**：`batch_refresh_scheduler.py` 熔断后剩余项被标�?`skipped` 但前端仅显示"批次已停�?，用户无法判断是否可恢复，也无法看到"重试剩余 N �?按钮，导致用户以为操作失败后只能重新发起全量

- 🆕v4.34【强制�?*F-REVIEW-111: ErrorBoundary 完整 stack 上报（ErrorBoundary full stack report�?*
  - 维度�?9 数据契约与时�?  - 严重等级：error
  - 规范引用：meta-rule #26 关键路径异常保留完整 traceback
  - **检查点**：React 全局 `ErrorBoundary.componentDidCatch` 必须上报**完整 stack** 到监控服务（�?sentry / 自建 report 端点），**禁止**�?`console.error` 打印�?`return null` 静默吞异常。后端关键路径（`_on_startup` / `run_migrations`）用 `logger.exception()` 完整堆栈，前端全局错误兜底必须用同等的"全量上报"语义
  - **判断信号**�?    - `grep "componentDidCatch\\(error[\\s\\S]{0,200}(?:console\\.(log|error)|return\\s+null)" frontend/src/**/*.{ts,tsx}` �?视为**必修 P0 缺陷**（吞异常�?    - ErrorBoundary 仅有 `return <h1>出错�?/h1>` �?`Sentry.captureException(error)` �?视为违规
  - **配置参数**：`data_contract_temporal.error_boundary.require_full_stack_report`（默�?`true`）、`forbidden_patterns`（默�?`[console.error_only, return_null]`）、`report_service`（默�?`sentry`，可改为自建 report 端点）在 `config.yaml` 管理
  - **适用**：所有路由层 ErrorBoundary、所�?lazy 加载模块的兜�?ErrorBoundary、所有全局错误拦截
  - **不适用**：业务层 try/catch（业务层应处理具体错误后展示 UI，不应被 ErrorBoundary 兜底）、测试代码中�?mock ErrorBoundary
  - **历史教训**：MainLayout 顶层 ErrorBoundary �?`console.error` 打印，生产环境用户报"页面空白"无法定位根因（无 stack、无 userId、无路由信息）。修复：接入 sentry 并补�?`errorInfo.componentStack` 上报

- 🆕v4.34【强制�?*F-REVIEW-112: ISO datetime 统一解析与序列化（ISO datetime parse & serialize�?*
  - 维度�?9 数据契约与时�?  - 严重等级：warning
  - 规范引用：meta-rule #27 datetime 统一时区策略
  - **检查点**：前端展示后�?ISO datetime 必须�?`new Date(isoStr).toLocaleString('zh-CN', { hour12: false })` 解析后转本地时区�?*禁止**直接字符串拼接（`iso + ' 创建'`）或字符串方法（`iso.replace('T', ' ').slice(0, 19)`）；前端→后端传递时间必须用 `Date.toISOString()` 保留时区�?*禁止** `toString()` / `toLocaleString()` 丢失时区信息
  - **判断信号**�?    - `grep "['\"]\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}['\"]\\s*\\+\\s*['\"]" frontend/src/**/*.{ts,tsx}` �?视为违规（直接拼接）
    - `grep "\\w+_(at|seen|time|active)\\.(replace|slice|substring|substr)\\(" frontend/src/**/*.{ts,tsx}` �?视为违规（字符串方法解析�?    - `grep "(time|date|at)\\s*:\\s*\\w+\\.toString\\(\\)" frontend/src/**/*.{ts,tsx}` �?视为违规（toString 丢时区）
  - **配置参数**：`data_contract_temporal.datetime.parse_iso_method`（默�?`new Date(isoStr)`）、`display_method`（默�?`toLocaleString('zh-CN', { hour12: false })`）、`send_to_backend_method`（默�?`Date.toISOString()`）、`forbidden_parse_methods`（默�?`[replace, slice, substring, substr]`）、`forbidden_send_methods`（默�?`[toString, toLocaleString]`）在 `config.yaml` 管理
  - **适用**：所有展示后�?`created_at` / `updated_at` / `expires_at` / `last_seen_at` �?ISO 字符串、所有前端→后端的时间字段提交（搜索/筛�?创建�?  - **不适用**：纯展示�?dayjs/day.js 库已封装解析、纯日期不含时间（年月日）、固定文案中的时间字符串
  - **历史教训**：订单列表后端返�?`created_at: "2026-07-05T10:00:00+00:00"`，前�?`isoStr.slice(0, 10)` 取日期直接显�?�?时区错位（UTC 时间当作本地时间，跨时区用户全部�?8 小时显示）。修复：统一 `new Date(iso).toLocaleString('zh-CN', { timeZone, hour12: false })` 解析

- 🆕v4.34【强制�?*F-REVIEW-113: 跨进程状态同步六步法（前端：SSE 推�?+ 启动 refetch�?*
  - 维度�?9 数据契约与时�?  - 严重等级：warning
  - 规范引用：meta-rule #28 跨进程状态同步六步法
  - **检查点**：跨进程状态变更（�?Cookie 多层同步、批量进度、登录态变化）前端必须采用 **SSE 推�?+ 启动 refetch** 模式�?*禁止**�?`setInterval` 长间隔（�?s）轮询替�?SSE 推送。SSE 推送失败时退化为短间隔（�?s）轮�?+ 启动时强�?refetch，与后端六步法配�?  - **判断信号**�?    - `grep "setInterval\\([^,]+,\\s*\\d{4,}\\)[\\s\\S]{0,300}//.*\\u4ee3\\u66ff.*SSE|//.*\\u4ee3\\u66ff.*SSE[\\s\\S]{0,300}setInterval" frontend/src/**/*.{ts,tsx}` �?视为违规（setInterval 替代 SSE�?    - SSE 错误处理�?`visibilitychange` 重建 / �?`MAX_RECONNECT` 次数限制 �?与已�?F-REVIEW-SSE-ERROR-HANDLING 重复检�?  - **配置参数**：`data_contract_temporal.state_sync.prefer_sse`（默�?`true`）、`sse_substitute_setinterval`（默�?`forbidden`）、`max_setinterval_for_state_sync`（默�?`0`，表示禁止）、`marker_dir_for_frontend`（默�?`data/markers`）在 `config.yaml` 管理
  - **适用**：Cookie 状态变化推送、批量任务进度推送、登录态变化通知、配置变更广�?  - **不适用**：纯 UI 动画（与后端无关）、表单字段同步（父子组件 props）、单�?API 拉取后的本地轮询（≤1s 防抖�?  - **历史教训**：Cookie 状态变更后端写 marker，但前端�?`setInterval(refetch, 5000)` 轮询 �?5s 延迟 + 高频请求浪费。修复：后端通过 SSE `/api/events/stream` 主动推�?`cookie_status_changed` 事件，前端订阅后立即 refetch

- 🆕v4.34【强制�?*F-REVIEW-114: 前端错误�?error_code 分支（error_code switch branch�?*
  - 维度�?9 数据契约与时�?  - 严重等级：error
  - 规范引用：meta-rule #29 前端错误�?error_code 分支
  - **检查点**：前端错误展示必须用 `switch (err.error_code)` 按后�?`reason_enum` 分支�?*禁止**按文案子串判断（`if (err.message.includes('expired'))`）。`reason_enum` 与后�?`error_code_contract.reason_enum` 一一对应（`token_expired/anti_crawler/page_unavailable/rate_limited/login_expired/session_invalid/permission_denied/validation_error/internal_error/service_unavailable`）。前端常量集中在 `frontend/src/constants/errorCode.ts`
  - **判断信号**�?    - `grep "if\\s*\\(\\s*\\w+\\.(message|detail|msg)\\.(includes|indexOf|search|match)\\(['\"](?:expired|unavailable|rate limited|page unavailable|login expired|session invalid)" frontend/src/**/*.{ts,tsx}` �?视为**必修 P0 缺陷**（substring 判断�?    - 前端 import `errorCode` 常量缺失 �?视为违规（应�?`frontend/src/constants/errorCode.ts` 导入�?  - **配置参数**：`data_contract_temporal.error_code_branch.reason_enum_source`（默�?`xianyu-backend-code-review.error_code.reason_enum`，与后端单一可信源）、`recognized_error_codes`（默�?10 �?reason 值）、`forbidden_substring_patterns`（默�?`[expired, unavailable, rate_limited, login_expired, session_invalid]`）、`required_pattern`（默�?`switch\\s*\\(\\s*\\w+\\.error_code\\s*\\)`）、`frontend_constants_file`（默�?`frontend/src/constants/errorCode.ts`）在 `config.yaml` 管理
  - **适用**：所�?API 错误处理分支、所�?toast/notification 文案、所�?4xx/5xx 错误展示
  - **不适用**：本地表单校验（无后端响应）、开发环�?console.error 调试日志、第三方 SDK 错误（按 SDK 文档处理�?  - **历史教训**：前�?8 个组件用 `if (err.message.includes('expired'))` 判断 Cookie 过期 �?后端文案从「登录已过期」改为「会话已失效」后所有页面判断失效，统一显示「未知错误」。修复：建立前后�?`error_code` 契约，前�?`switch (err.error_code)` 分支

- 🆕v4.34【强制�?*F-REVIEW-115: 业务关键字常量集中管理（business keyword centralization�?*
  - 维度�?9 数据契约与时�?  - 严重等级：warning
  - 规范引用：meta-rule #30 业务关键字常量集中管�?  - **检查点**：前端业务关键字（已�?已删�?宝贝不存�?卖掉�?已售罄等需正则匹配/includes 判断的字符串�?*禁止**内联到组件（�?`if (text.includes('已售'))`），**必须**�?`frontend/src/constants/businessKeywords.ts` 导入�?*必须**与后�?`config.yaml#business_keywords` 等价（通过 `tests/test_keyword_consistency.py` 验证�?  - **判断信号**�?    - `grep "['\"](?:已售|已删除|宝贝不存在|卖掉了|已售�?['\"]" frontend/src/**/*.{ts,tsx}` �?视为违规（硬编码�?    - 业务代码 `if (text.includes('xxx'))` �?xxx 不在 `businessKeywords.ts` �?视为违规
  - **配置参数**：`data_contract_temporal.business_keyword.constants_file`（默�?`frontend/src/constants/businessKeywords.ts`）、`backend_source`（默�?`xianyu-backend-code-review.business_keyword`，单一可信源）、`consistency_test`（默�?`tests/test_keyword_consistency.py`）、`categories`（默�?`[sold, deleted, loginExpired, antiCrawler]`）在 `config.yaml` 管理
  - **适用**：商品状态识别（已售/已删/在售）、错误提示文案匹配、风控标签识别、敏感词过滤
  - **不适用**：日�?异常消息中的自由文本、配置文件中的连接信息、测试用例中�?mock 数据
  - **历史教训**：Cookie 自愈系统�?`sold` 关键字集合在 3 处独立维护，新增「宝贝走丢了」时只更新了 2 处，�?3 处漏更新导致「已售商品」被误判为「在售」继续抢单。修复：抽取�?`config.yaml#business_keywords` + `frontend/src/constants/businessKeywords.ts` 集中管理，CI 跑一致性测�?
---

### 30. 状态恢复前置校验前端侧 🆕v4.35

> 本维度对�?`xianyu-hunter-dev` v4.31.0 meta-rules #31 与后�?`xianyu-backend-code-review` v4.30.0 �?B-REVIEW-157（状态恢复前置校验）。前端侧新增 1 �?F-REVIEW 检查点（F-REVIEW-116），强调恢复/启动按钮点击时必须先调用后端 precheck 接口校验前置条件。前端无降级链日志场景，不新�?LOG-MERGE 对应检查点（meta-rules #32 仅后端适用）�?
- 🆕v4.35【强制�?*F-REVIEW-116：RESUME-PRECHECK-FRONTEND 恢复操作前端前置校验**
  - 维度�?0 状态恢复前置校验前端侧
  - 严重等级：error（P0�?  - 规范引用：meta-rule #31 状态恢复前置校验（前端侧）+ 后端 B-REVIEW-157
  - **检查点**：前�?恢复/启动/继续"按钮点击时，必须先调用后�?precheck 接口校验前置条件（如 Cookie �?valid、会�?active、连接可达），校验失败时禁用按钮 + 提示用户先解决根因（如重新登录），禁止绕过前端校验直接调 resume API
  - **检查项**�?    1. resume/启动按钮 `onClick` 必须调用 precheck API（如 `POST /api/<resource>/precheck`），获取 `{resume_blocked, reason_code, user_hint, retry_after}` 结构化响�?    2. precheck 失败时（`resume_blocked: true`）按�?`disabled` + 提示 `user_hint`（如"请先重新登录闲鱼"），禁止直接�?resume API
    3. 冷却期内（`retry_after > 0`）按�?`disabled` + 倒计时显示，倒计时结束后允许重新点击 precheck
    4. 禁止绕过前端校验直接�?resume API（如点击按钮立即 `fetch('/api/resume')` �?precheck 调用�?  - **判断信号**�?    - `grep "onClick.*(resume|start|continue|恢复|启动|继续)" frontend/src/**/*.{ts,tsx}` �?precheck 调用 �?视为违规
    - resume/启动按钮�?`disabled` 状态绑定（`disabled={precheckBlocked}`）→ 视为违规
    - 直接�?resume API（`fetch('/api/<resource>/resume')`）无前置 precheck 调用 �?视为违规
    - 冷却期内按钮可点击（无倒计时逻辑）→ 视为违规
  - **配置参数**：`resume_precheck_frontend.precheck_endpoint_pattern`（precheck 端点模式，如 `/api/<resource>/precheck`）、`resume_precheck_frontend.required_response_fields`（响应必须字段，�?`["resume_blocked", "reason_code", "user_hint", "retry_after"]`）、`resume_precheck_frontend.cooldown_countdown_required`（冷却期倒计时是否必须，默认 true）、`resume_precheck_frontend.applicable_buttons`（适用按钮清单，如 `["task_resume", "session_recover", "connection_reconnect"]`）在 `config.yaml` �?`resume_precheck_frontend` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.31.0 meta-rules #31 + 后端 `xianyu-backend-code-review` v4.30.0 B-REVIEW-157
  - **适用**：任务恢复按钮（如搜索任务暂停后恢复）、登录会话恢复（Cookie 失效后重新登录）、连接重连按钮（连接池断连后重连�?  - **不适用**：无前置依赖的普通启动按钮（如新建任务）、用户主�?pause 后的恢复（非异常触发，无 root_cause）、一次性表单提交按�?  - **历史教训**：搜索任�?`t68bc149b` 因闲鱼会话失效被自动暂停后，用户在前端连续点击「恢复」按�?4 次，但前端未调用 precheck 校验 Cookie 层状态，每次恢复�?13~22 秒内再次触发会话失效检测并暂停，形�?恢复→失效→暂停"无效循环。修复：前端「恢复」按�?onClick 先调 `POST /api/tasks/precheck`，校�?`cookie_rotator` �?identity/session �?valid 状态，失效时按�?disabled + 提示"请先重新登录闲鱼"，冷却期内显示倒计时，彻底消除无效循环

---

### 34. 规范治理（meta-rules #36-37 落地）🆕v4.37

> 本维度对�?`xianyu-hunter-dev` v4.33.0 meta-rules #36（规范沉淀门槛）与 #37（规范退化机制），与后端 `xianyu-backend-code-review` v4.33.0 维度 35 �?B-REVIEW-162/163 联动。前端侧新增 2 �?F-REVIEW 检查点（F-REVIEW-120/121），强调前端编码规范（F-REVIEW）的立项门槛与退化清理，防止过度规范化和规范膨胀�?
#### F-REVIEW-120：SEDIMENTATION-THRESHOLD 规范立项前置计数（meta-rule #36 落地�?
**规则**：新立前端编码规范（meta-rule / F-REVIEW / step）必须满�?�?`meta_rules_governance.sedimentation_threshold`（默�?3）个相似 bug 门槛，单一 bug 立规范需�?`experimental` 标签 + 1 季度观察期�?
**关键约束**�?- 单一 bug 立规范（�?experimental 标签）→ 视为违规（规范膨胀风险�?- experimental 标签�?1 季度未升级为正式 �?视为废弃候�?- 例外豁免立规范但未标注豁免原�?�?视为不规�?- 计数阈值硬编码 �?视为违规（必须从 config 读取�?
**判断信号**�?- `grep "🆕v4\\." SKILL.md` 新增维度标题但无对应的历�?bug 收集记录 �?视为违规
- `grep "experimental" SKILL.md` 标签�?1 季度未升�?�?废弃候�?- 新增 F-REVIEW 检查点�?`docs/standards/编码规范复盘.md` �?�? 个相�?bug 记录 �?视为违规

**配置参数**：`meta_rules_governance.sedimentation_threshold`（相�?bug 计数门槛，默�?3）、`meta_rules_governance.sedimentation_time_window_months`（计数时间窗口，默认 6 月）、`meta_rules_governance.experimental_observation_quarters`（experimental 观察期，默认 1 季度）、`meta_rules_governance.sedimentation_exemption_categories`（例外豁免类别：security_vulnerability / data_loss / payment_damage）在 `config.yaml` �?`meta_rules_governance` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.33.0 meta-rules #36 + 后端 `xianyu-backend-code-review` v4.33.0 B-REVIEW-162

**适用**：新增前端编码规范（F-REVIEW 检查点 / 维度 / step）的立项场景
**不适用**：安全漏洞类规范（XSS/CSRF/token 处理，立即立规范）、数据丢失类规范、付费受损类规范（这三类豁免 �? 次门槛）

**历史教训**：v4.36.0 新增维度 31-33（F-REVIEW-117/118/119）时，仅基于"通知中心菜单点击无反�?单一 bug 立规范，未满�?�? 个相�?bug 门槛，且未标 experimental 标签。虽因属�?注册式资源三件套契约"类问题（影响用户可导航功能入口）可申请豁免，但未在规范中标注豁免原因，导致无法审计。修复：本维度（F-REVIEW-120）作为规范治理元规范，强制要求后续新增规范必须满足门槛或标注豁免原因�?
#### F-REVIEW-121：DEGRADATION-CLEANUP 规范退化清理（meta-rule #37 落地�?
**规则**：利用率 < `meta_rules_governance.degradation_threshold`（默�?3 �?季度）的 F-REVIEW 检查点必须标记"待合�?�?待废�?�? 季度观察期后废弃并移�?`version-history.md` Deprecated 章节�?
**关键约束**�?- 利用�?< 3 �?季度�?F-REVIEW 未标记待合并/待废�?�?视为违规
- 标记"待废�?�?1 季度未处�?�?视为违规（废弃流程卡住）
- 安全类规范被标记退�?�?视为违规（安全类永不退化）
- 退化阈值硬编码 �?视为违规（必须从 config 读取�?
**判断信号**�?- `grep "待废弃|deprecated" SKILL.md` 标记�?1 季度未处�?�?废弃流程卡住
- F-REVIEW 检查点在最�?1 季度审查报告�?0 命中且未标记待废�?�?视为违规
- 安全�?F-REVIEW（如 fetch_credentials_include / no_token_in_localstorage）被标记退�?�?视为违规

**配置参数**：`meta_rules_governance.degradation_threshold`（利用率退化阈值，默认 3 �?季度）、`meta_rules_governance.observation_period_quarters`（待废弃观察期，默认 1 季度）、`meta_rules_governance.degradation_exemption_categories`（永不退化类别：security / config_driven）在 `config.yaml` �?`meta_rules_governance` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.33.0 meta-rules #37 + 后端 `xianyu-backend-code-review` v4.33.0 B-REVIEW-163

**适用**：每季度�?F-REVIEW 检查点利用率统计与退化清�?**不适用**：安全类规范（XSS/CSRF/token 处理/认证白名单等永不退化）、配置驱动类规范（依�?config 存在，config 存在则规范存在）

**历史教训**：v4.33.0 一次性新�?14 �?F-REVIEW（F-REVIEW-96~109），其中部分检查点（如 F-REVIEW-EMBEDDED-LAYOUT-HEIGHT）在后续季度审查�?0 命中，但未触发退化清理流程，导致规范堆积。修复：本维度（F-REVIEW-121）作为规范治理元规范，强制要求每季度统计利用率并清理低命中规范�?
#### F-REVIEW-122：GLOBAL-AGGREGATE-TASK-FILTER 全局聚合任务级过滤（meta-rule #38 前端侧）🆕v4.38

**维度**�? API 契约 / 11 数据展示

**规则**：前端聚合统计（�?Dashboard 价格区间分布、市场价比率分布）必须按当前任务�?`price_range`/`market_ratio` 配置过滤，禁止展示越界数据；前端展示聚合数据前必须确认后端已调用 `_filter_by_per_task_range` 过滤�?
**关键约束**�?- 前端展示全局聚合数据但未确认后端按任务级配置过滤 �?视为违规（CRITICAL�?- 聚合数据中包含超出任�?`price_range` 的数据点 �?视为违规
- 聚合统计 UI 未标�?已按任务配置过滤" �?视为违规（WARNING�?- 前端自行实现过滤而非依赖后端 �?视为违规（应后端过滤，前端仅展示�?
**判断信号**�?- `grep "aggregate\|stats\|distribution" frontend/src/` 后检查是否引用任务级配置过滤
- Dashboard 聚合组件未读取当前任务的 `price_range`/`market_ratio` �?视为违规
- 聚合数据响应中包含超�?`price_range` 的数据点 �?视为违规

**反模�?*�?```typescript
// 禁止：前端展示全局聚合数据但未确认后端按任务级配置过滤
```

**正确模式**：`useEffect` �?`fetch('/api/items/price-distribution?task_id=${taskId}')` 传�?task_id �?后端调用 `_filter_by_per_task_range` 按任务级 price_range/market_ratio 过滤

**配置参数**：`meta_rules_38_42_frontend.global_aggregate_filter.enabled`（开关，默认 true）、`severity`（CRITICAL）、`required_filter_function`（后端必须调用的过滤函数名，默认 `_filter_by_per_task_range`）、`task_config_fields`（任务级配置字段列表，默�?`["price_range", "market_ratio"]`）在 `config.yaml` �?`meta_rules_38_42_frontend.global_aggregate_filter` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.34.0 meta-rule #38 + step 184

**适用**：所有全局聚合统计（Dashboard 价格分布、市场价比率分布、评估统计等�?**不适用**：单任务详情页的数据展示（已天然�?task_id 过滤）、用户级全局配置页面

**历史教训**：Dashboard �?捡漏价格参�?聚合统计未按任务�?`price_range` 过滤，导致展示越界数据（�?price_range 配置�?0-100 元，但聚合分布中包含 200 元的数据点），用户误以为系统配置错误。修复：后端聚合 API 必须调用 `_filter_by_per_task_range` 按任务级配置过滤，前端传�?`task_id` 参数�?
#### F-REVIEW-123：LIST-CROSS-DOMAIN-INJECT 列表交叉数据批量注入（meta-rule #39 前端侧）🆕v4.38

**维度**�? API 契约 / 10 性能

**规则**：列表渲染交叉数据（如商品列表注入最新评估价/订单状态）必须用批�?API 一次性获取，禁止循环中逐项 fetch；前端必须支持批量响应的 `id �?value` 映射结构�?
**关键约束**�?- 列表中逐项 fetch 交叉数据（如 `items.map(item => fetch(`/api/eval/${item.id}`))`）→ 视为违规（CRITICAL�?- 批量 API 响应未用 `id �?value` 映射结构 �?视为违规（WARNING�?- 前端未处理批量响应中缺失�?id �?视为违规（应�?fallback�?- 循环中调�?db query 的模式（`for item in items: db.query(...)`）→ 视为违规

**判断信号**�?- `grep "items.map.*fetch\|for.*of.*fetch" frontend/src/` 命中 �?视为违规
- `grep "\.map\(.*await" frontend/src/` 命中 �?视为违规（循环中 await�?- 列表组件中每�?item 单独发起 API 请求 �?视为违规

**反模�?*�?```typescript
// 禁止：列表中逐项 fetch 交叉数据（N+1 查询�?```

**正确模式**：`fetch('/api/eval/batch', { method: 'POST', body: { ids: itemIds } })` 批量获取 �?`evals` �?`{ id: evalData }` 映射 �?`items.map(item => ({ ...item, eval: evals[item.id] ?? null }))` 缺失�?fallback

**配置参数**：`meta_rules_38_42_frontend.cross_domain_inject.enabled`（开关，默认 true）、`severity`（WARNING）、`cache_ttl_seconds`（前端缓�?TTL，默�?300）、`batch_size_limit`（批量请求最�?id 数，默认 500）、`forbidden_loop_patterns`（禁止的循环模式列表）在 `config.yaml` �?`meta_rules_38_42_frontend.cross_domain_inject` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.34.0 meta-rule #39 + step 185

**适用**：列表渲染交叉数据（商品列表注入评估�?订单状态、任务列表注入最新运行状态等�?**不适用**：单条详情页的数据获取、实�?SSE 推送的数据更新

**历史教训**：商品列表页每个商品单独 fetch 评估价，100 个商品触�?100 �?API 请求，页面加载时间从 200ms 膨胀�?5s+。修复：新增批量 API `/api/eval/batch`，前端一次性获取所有评估价并用 `id �?value` 映射注入�?
#### F-REVIEW-124：MULTI-FIELD-LINKED-SWITCH 多字段联动开关范式（meta-rule #40 前端侧）🆕v4.38

**维度**�? React 组件 / 6 Zustand 状态管�?
**规则**：多字段联动开关（�?mode + bargain_only）必须遵�?主开关决定副开关可见�?范式，副开关值在主开关关闭时必须清零而非保留；前�?UI 必须根据主开关状态动态显�?隐藏副开关�?
**关键约束**�?- 副开关在主开关关闭时仍可�?�?视为违规（MAJOR�?- 副开关值在主开关关闭时未清零（保留旧值）�?视为违规（CRITICAL�?- 主开关切换时未触发副开�?UI 更新 �?视为违规
- 前端 UI 未根据主开关状态动态显�?隐藏副开�?�?视为违规

**判断信号**�?- `grep "mode.*bargain_only\|main_switch.*sub_switch" frontend/src/` 后检查联动逻辑
- 主开关切换时副开关值未清零 �?视为违规
- 副开关组件未根据主开关状态条件渲�?�?视为违规

**反模�?*�?```typescript
// 禁止：副开关值在主开关关闭时未清零，�?UI 未联�?```

**正确模式**：`handleModeChange(newMode)` 切换主开�?�?`newMode === 'notify'` �?`setBargainOnly(false)` 副开关清�?�?`{mode !== 'notify' && <Switch checked={bargainOnly} />}` 副开关条件渲�?
**配置参数**：`meta_rules_38_42_frontend.linked_switch_priority.enabled`（开关，默认 true）、`severity`（MAJOR）、`main_switch_field`（主开关字段名，默�?`mode`）、`filter_suffix`（副开关后缀，默�?`_bargain_only`）、`priority_matrix`（主开关�?�?副开关可见性映射）�?`config.yaml` �?`meta_rules_38_42_frontend.linked_switch_priority` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.34.0 meta-rule #40 + step 186

**适用**：所有多字段联动开关场景（mode + bargain_only、auto_buy + notify_only 等）
**不适用**：独立无依赖的开关字段、单向不可逆的开关（如删除确认）

**历史教训**：任务配置中 `mode` 切换�?`notify` 时，`bargain_only` 字段仍保留旧�?`true`，导致后端在 notify 模式下仍尝试 bargain 逻辑引发异常。修复：前端主开关切换时必须清零副开关值，�?UI 根据 `priority_matrix` 动态显�?隐藏副开关�?
#### F-REVIEW-125：RESUME-PRECHECK-STRUCTURED 状态恢复前置校验结构化响应（meta-rule #41 前端侧）🆕v4.38

**维度**�? API 契约 / 11 错误处理

**规则**：前端调�?resume/start 接口必须处理结构�?precheck 响应（`{resume_blocked, reason_code, user_hint, retry_after, task_registered}`），禁止假设接口直接成功；precheck 失败时必须展�?`user_hint` �?`retry_after` 倒计时�?
**关键约束**�?- 前端调用 resume/start 接口未处�?`resume_blocked: true` 情况 �?视为违规（CRITICAL�?- precheck 失败时仅展示通用错误而非 `user_hint` �?视为违规
- 未展�?`retry_after` 倒计�?�?视为违规（WARNING�?- 前端假设 resume 接口直接返回成功 �?视为违规

**判断信号**�?- `grep "resume\|start\|unpause" frontend/src/` 后检查是否处理结构化响应
- resume 接口响应处理中无 `resume_blocked` 字段判断 �?视为违规
- 错误展示中未引用 `user_hint` �?`retry_after` �?视为违规

**反模�?*�?```typescript
// 禁止：假�?resume 接口直接成功，未处理 precheck 结构化响�?```

**正确模式**：`fetch('/api/tasks/resume', { body: { task_id } })` �?`res.resume_blocked` �?true �?`message.warning(res.user_hint)` + `setRetryCountdown(res.retry_after)` 倒计�?�?否则 `message.success('任务已恢�?)`

**配置参数**：`meta_rules_38_42_frontend.precheck_structured_fields.enabled`（开关，默认 true）、`severity`（CRITICAL）、`required_fields`（结构化响应必须包含的字段列表，默认 `["resume_blocked", "reason_code", "user_hint", "retry_after", "task_registered"]`）、`forbid_raise`（是否禁止后端抛异常，默�?true）、`api_error_status`（precheck 失败时的 HTTP 状态码，默�?400）在 `config.yaml` �?`meta_rules_38_42_frontend.precheck_structured_fields` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.34.0 meta-rule #41 + step 187

**适用**：所�?resume/start/unpause 接口的前端调�?**不适用**：首次创建任务（�?precheck 需求）、纯查询接口（无状态变更）

**历史教训**：前端调�?resume 接口时假设直接成功，但后�?precheck 检测到 cookie 过期返回 `resume_blocked: true`，前端仍展示"任务已恢�?导致用户困惑。修复：前端必须处理结构�?precheck 响应，precheck 失败时展�?`user_hint` �?`retry_after` 倒计时�?
#### F-REVIEW-126：CONFIG-DRIVEN-THRESHOLD-FALLBACK 配置化阈值兜底范式（meta-rule #42 前端侧）🆕v4.38

**维度**�?1 配置驱动 / 11 错误处理

**规则**：前端使用的阈值参数（�?p10 百分位、market_ratio_threshold、price_range_tolerance）必须从后端配置 API 获取，禁止前端硬编码；配�?API 失败时必须用兜底默认值并 `console.warn`，禁止抛异常导致页面崩溃�?
**关键约束**�?- 前端硬编码阈值参数（�?`const P10 = 0.10`）→ 视为违规（MAJOR�?- 配置 API 失败时抛异常导致页面崩溃 �?视为违规（CRITICAL�?- 配置 API 失败时未用兜底默认�?�?视为违规
- 配置 API 失败时未 `console.warn` 记录 �?视为违规（WARNING�?
**判断信号**�?- `grep "const\s+P\d+\s*=\s*0\.\d+\|const\s+THRESHOLD\s*=" frontend/src/` 命中 �?视为违规
- 配置 API 调用�?try/catch �?.catch() �?视为违规
- 配置 API 失败时无兜底默认�?�?视为违规

**反模�?*�?```typescript
// 禁止：前端硬编码阈值，且配�?API 失败时抛异常
```

**正确模式**：`FALLBACK_DEFAULTS = { p10_percentile: 0.10, market_ratio_threshold: 0.85, price_range_tolerance: 0.05 }` 兜底 �?`fetch('/api/config').then(r => r.json()).catch(err => { console.warn('配置 API 失败', err); return FALLBACK_DEFAULTS })`

**配置参数**：`meta_rules_38_42_frontend.config_fallback_defaults.enabled`（开关，默认 true）、`severity`（MAJOR）、`fallback_defaults`（兜底默认值映射，默认 `{p10_percentile: 0.10, market_ratio_threshold: 0.85, price_range_tolerance: 0.05}`）、`require_warning_log`（是否强�?console.warn，默�?true）在 `config.yaml` �?`meta_rules_38_42_frontend.config_fallback_defaults` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.34.0 meta-rule #42 + step 188

**适用**：所有阈值参数（p10 百分位、market_ratio_threshold、price_range_tolerance 等）
**不适用**：纯 UI 展示参数（如颜色、字体大小）、无业务语义的常�?
**历史教训**：前端硬编码 `P10_PERCENTILE = 0.10`，当后端配置调整�?`0.05` 时前端未同步，导�?捡漏价格参�?展示�?低于 P10"判定标准与后端不一致。修复：前端阈值参数必须从后端配置 API 获取，失败时用兜底默认值并 `console.warn`，禁止硬编码�?
### 35. 跨层契约与测试同步（meta-rules #43-47 落地）🆕v4.39

> 本维度对�?`xianyu-hunter-dev` v4.35.0 meta-rules #43-#47（事件多发布点字段对�?/ 路由三重注册同步 / query string 保留 / 测试同步责任 / 外部依赖隔离），与后�?`xianyu-backend-code-review` �?B-REVIEW-169~173 联动。前端侧新增 5 �?F-REVIEW 检查点（F-REVIEW-131~135），基于 2026-07-07 SEMI_AUTO 模式通知未触发确认类问题复盘（EVAL_PASSED 事件三处发布�?task_mode 字段不对�?/ 前端 sheetRegistry 未注册新路由 + findSheetMeta 未剥�?query string / useSheetSync 丢失 query string），使用 Sequential Thinking 4 维度复盘法提炼，强调跨层契约对齐与测试同步，确保事件多发布点字段集一�?/ 路由三处注册同步 / 外部回链 query string 保留 / 接口签名变更同步测试 / 外部依赖显式 mock。所有检查点强调配置驱动（参数在 `config.yaml` �?`cross_layer_contract_test_sync` 节点管理，不硬编码）与适用 / 不适用场景说明�?
#### F-REVIEW-131：EVENT-MULTI-EMIT-ALIGN 事件多发布点字段对齐（meta-rule #43 前端侧）🆕v4.39

**维度**�?5 SSE 重连 / 19 跨组件状态同�?
**【强制�?*前端消费方按事件 payload 字段分支时（�?`payload.task_mode` / `event.task_mode`），必须确认所有事件发布点（成功路�?/ 失败路径 / 超时路径 / 降级路径）发布的字段集一致；任一字段缺失必须显式 fallback，禁止默�?`undefined` 进入分支逻辑导致静默无反馈�?
**关键约束**�?- 同一事件类型在多个发布点（成�?/ 失败 / 超时 / 降级）字段集不一�?�?视为违规（CRITICAL�?- 消费方按某字段分支（�?`task_mode === 'SEMI_AUTO'`）但�?fallback / else 分支 �?视为违规（WARNING�?- 事件字段名在前后�?/ 不同发布点拼写不一致（�?`task_mode` vs `taskMode`）→ 视为违规
- 字段添加至某发布点但未同步到其他发布�?�?视为违规

**判断信号**�?- `grep "payload\.\|event\." frontend/src/` 按字段分支但�?fallback / else 分支 �?视为违规
- `grep -r "emit.*task_mode\|emit.*taskMode" backend/` 多个 emit 点字段集不一�?�?视为违规
- 前端 `switch (payload.xxx)` �?case 列表与后�?emit 字段集不匹配 �?视为违规

**反模�?*�?```typescript
// 禁止：按字段分支但无 fallback，且未确认所有发布点字段一�?```

**正确模式**：`type EvalEvent = { task_mode: 'AUTO' | 'SEMI_AUTO' | 'MANUAL'; status: string }` 事件类型契约 �?`switch (event.task_mode)` 分支处理 �?`default` 分支 `console.warn` + 回退�?AUTO 流程

**配置参数**：`cross_layer_contract_test_sync.event_multi_emit_alignment.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_field_fallback`（是否强制字段缺�?fallback，默�?true）、`event_type_contract_required`（是否强制事件类型契约定义，默认 true）、`emit_point_consistency_check`（是否检查后端多发布点字段一致，默认 true）在 `config.yaml` �?`cross_layer_contract_test_sync.event_multi_emit_alignment` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.35.0 meta-rule #43 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-173

**适用**：消�?SSE / WebSocket / postMessage / 自定义事件的前端组件
**不适用**：纯内部 state 变更（无跨层事件传递）、字段为可选且消费方不依赖分支的场�?
**历史教训**：SEMI_AUTO 模式通知未触发确认弹窗。根因：EVAL_PASSED 事件存在三处发布点（成功路径 / 异常路径 / 超时路径），某发布点 `task_mode` 字段拼写不一致或缺失，前端按 `task_mode === 'SEMI_AUTO'` 分支但无 fallback，导致字段缺失时静默跳过确认流程，用户报�?通知未触�?。修复：统一三处发布点字段集，前端增�?default 分支兜底�?
#### F-REVIEW-132：ROUTE-TRIPLE-REGISTRATION 前端路由三重注册同步（meta-rule #44 前端侧）🆕v4.39

**维度**�? 路由与懒加载 / 14 三处映射同步

**【强制�?*新增 SheetWorkspace 多页签路由必�?L1（路由根组件 `<Route>`�? L2（路由注册表 sheetRegistry�? L3（URL 同步 Hook useSheetSync）三处同步注册；任一处缺失视为路由链路断裂，会导�?URL 与页签状态不同步�?
**关键约束**�?- 新增 `<Route>` 但路由注册表无对应条�?�?视为违规（CRITICAL�?- 路由注册表注册新路由�?URL 同步 Hook 未处理该 path �?视为违规（URL 不联动）
- URL 同步 Hook 处理�?path 但路由根组件无对�?`<Route>` �?视为违规�?04 fallback�?- 路由 path 在三处拼写不一致（�?`/evaluations` vs `/evaluation`）→ 视为违规

**判断信号**�?- `git diff` 新增 `<Route path="...">` 但同 PR 路由注册表无对应条目 �?视为违规
- `grep "sheetRegistry" frontend/src/` 路由表与 `grep "<Route" frontend/src/` 数量不一�?�?视为违规
- `grep "useSheetSync" frontend/src/hooks/` 处理�?path 列表与路由注册表不一�?�?视为违规

**反模�?*�?```typescript
// 禁止：路由根组件新增 Route（如 /evaluations/auto）但路由注册表与 useSheetSync Hook 未同步更�?```

**正确模式**：L1 `<Route path="/evaluations/auto" element={<AutoEvalPage />} />` + L2 `sheetRegistry` 注册 `{ key, path, label }` + L3 `useSheetSync` �?`sheetRegistry.find(s => s.path === location.pathname)` 三处同步

**配置参数**：`cross_layer_contract_test_sync.frontend_route_registration.enabled`（开关，默认 true）、`severity`（CRITICAL）、`registration_layers_required`（必须同步的层列表，默认 `["app_route", "sheet_registry", "use_sheet_sync"]`）、`path_consistency_check`（是否检�?path 拼写一致，默认 true）、`auto_validate_on_diff`（是否在 git diff 时自动校验，默认 true）在 `config.yaml` �?`cross_layer_contract_test_sync.frontend_route_registration` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.35.0 meta-rule #44 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-174

**适用**：SheetWorkspace 多页签应用、依�?URL 同步 sheet 状态的多页签场�?**不适用**：独立路由如 /login / /onboarding（无 sheet 同步需求）、纯内部导航（无 URL 变更�?
**历史教训**：新�?SEMI_AUTO 评估路由，仅在路由根组件添加 `<Route>`，但路由注册表未注册对应条目、URL 同步 Hook 未处理该 path，导致用户从外部链接进入该路由时 sheet 页签状态与 URL 不同步。修复：新增路由必须三处同步，CI 自动校验 path 一致性�?
#### F-REVIEW-133：QUERY-STRING-RETAIN 外部回链 query string 保留（meta-rule #45 前端侧）🆕v4.39

**维度**�? 路由与懒加载 / 19 跨组件状态同�?
**【强制�?*URL 同步 Hook 必须�?`location.pathname + location.search` 完整拼接作为路由标识；路由匹配函数（�?findSheetMeta）必须剥�?query string 后再与路由表 path 比对，禁止把�?query 的完�?URL 直接与路由表 path 比较�?
**关键约束**�?- URL 同步 Hook 仅用 `location.pathname` 拼接 URL（丢�?query string）→ 视为违规（CRITICAL�?- 路由匹配函数直接用完�?URL（含 query）与路由�?path 比较 �?视为违规（永远匹配失败）
- 外部回链�?query string �?sheet 切换后丢�?�?视为违规
- �?`window.location.href` 替代 `location.pathname + location.search` �?视为违规（含 hash / origin 不可控）

**判断信号**�?- `grep "location.pathname" frontend/src/hooks/` 命中但无 `location.search` 配对 �?视为违规
- `grep "findSheetMeta" frontend/src/` 内含 `pathname === path`（未先剥�?query）→ 视为违规
- `grep "window.location.href" frontend/src/hooks/` 命中 �?视为违规（应使用 location 对象拆分字段�?
**反模�?*�?```typescript
// 禁止：useSheetSync 仅取 location.pathname 丢失 ?task_id=xxx �?query；findSheetMeta 直接用含 query �?fullPath �?sheetRegistry.path 比对导致永远匹配失败
```

**正确模式**：`useSheetSync` �?`location.pathname + location.search` 完整保留 query �?`findSheetMeta` �?`fullPath.split('?')[0]` 剥离 query 后再�?`sheetRegistry.path` 比对

**配置参数**：`cross_layer_contract_test_sync.external_callback_query_retention.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_search_retention`（是否强制保�?location.search，默�?true）、`require_query_strip_in_match`（是否强制路由匹配前剥离 query，默�?true）、`forbidden_location_apis`（禁止使用的 location API 列表，默�?`["window.location.href"]`）在 `config.yaml` �?`cross_layer_contract_test_sync.external_callback_query_retention` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.35.0 meta-rule #45 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-175

**适用**：从外部通知 / 邮件 / 二维码回链的路由（含 query string 携带业务参数）、SheetWorkspace URL 同步 Hook
**不适用**：纯内部导航（无 query string）、无需保留 query 的简单路由跳�?
**历史教训**：用户从通知中心点击回链进入 `/evaluations/auto?task_id=xxx`，但 URL 同步 Hook 仅用 pathname 同步 sheet，query string 丢失；同时路由匹配函数用完整 URL（含 query）与路由�?path 比对，永远匹配失败导�?sheet 显示首页。修复：URL 同步 Hook 必须 `pathname + search` 拼接，路由匹配函数必须先 `split('?')[0]` 剥离 query 再匹配�?
#### F-REVIEW-134：TEST-SYNC-RESPONSIBILITY 测试同步责任（meta-rule #46 前端侧）🆕v4.39

**维度**�? 可测试�?/ 20 API 数据源一致性与类型契约对齐

**【强制�?*前端 API 接口签名变更 / Hook 签名变更 / mock 字段集调�?/ 异步同步逻辑重构必须�?PR 同步更新对应 `__tests__/` 测试；测试覆盖率不允许因重构下降�?
**关键约束**�?- API 签名变更（参�?/ 返回类型 / 字段名）但同 PR `__tests__/` 无修�?�?视为违规（WARNING�?- Hook 签名变更�?Hook 测试未更�?�?视为违规
- mock 字段集调整但测试快照未更�?�?视为违规
- 异步同步逻辑重构（如 useEffect 改用 useSyncExternalStore）但测试用例未调�?�?视为违规

**判断信号**�?- `git diff` 生产代码 API 签名变更但同 PR `__tests__/` 无修�?�?视为违规
- `git diff` Hook 文件签名变更但同 PR Hook 测试文件无修�?�?视为违规
- `grep "vi.mock\|jest.mock" frontend/src/__tests__/` mock 字段集与生产代码字段集不一�?�?视为违规
- 测试覆盖率下降超�?5% �?视为违规

**反模�?*�?```typescript
// 禁止：API 签名新增字段（如 task_mode）但测试 vi.mock 仍返回旧字段集，导致测试通过但生产代码按新字段分支失�?```

**正确模式**：`export type EvalItem = { id; status; task_mode: 'AUTO'|'SEMI_AUTO'|'MANUAL' }` 签名变更 �?`vi.mock` 同步更新 mock 字段集含 `task_mode` �?新增 `test('SEMI_AUTO 模式触发确认弹窗')` 分支测试用例

**配置参数**：`cross_layer_contract_test_sync.test_synchronization.enabled`（开关，默认 true）、`severity`（WARNING）、`require_test_update_on_signature_change`（是否强制签名变更同步测试，默认 true）、`mock_field_set_sync_required`（是否强�?mock 字段集与生产代码同步，默�?true）、`coverage_drop_threshold_percent`（覆盖率下降阈值，默认 5）、`test_framework`（测试框架，默认 `vitest`）在 `config.yaml` �?`cross_layer_contract_test_sync.test_synchronization` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.35.0 meta-rule #46 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-172

**适用**：前�?API 层重构、Hook 签名变更、异步同步逻辑（useEffect / useSyncExternalStore）重构、mock 字段集调�?**不适用**：纯样式调整（CSS / Tailwind class）、注�?/ 文档修改、纯类型导入调整（无运行时影响）

**历史教训**：API 新增 `task_mode` 字段后未同步更新测试 mock，测试用例仍用旧字段集（�?task_mode）通过 CI，但生产环境�?task_mode 分支时字段缺失导�?SEMI_AUTO 确认弹窗未触发。修复：API 签名变更必须�?PR 同步测试�?mock 字段集，CI 校验覆盖率下降不超过阈值�?
#### F-REVIEW-135：EXTERNAL-DEP-ISOLATION 外部依赖隔离测试可重复性（meta-rule #47 前端侧）🆕v4.39

**维度**�? 可测试�?
**【强制�?*前端测试中依�?`fetch` / `localStorage` / `sessionStorage` / `window` / `import.meta.env` 等外部依赖必须显�?`vi.mock` / `vi.spyOn` / `vi.stubGlobal` / `vi.stubEnv` 隔离，禁止依赖生�?fallback 或运行时真实环境�?
**关键约束**�?- 测试中调�?`fetch` 但无 `vi.spyOn(global, 'fetch')` �?视为违规（CRITICAL�?- 测试中读�?`localStorage` 但无 mock �?视为违规（CRITICAL�?- 测试依赖 `import.meta.env.VITE_XXX` 但无 `vi.stubEnv` �?视为违规（WARNING�?- 测试依赖 `window.location` 真实�?�?视为违规

**判断信号**�?- `grep "fetch\|localStorage\|sessionStorage" frontend/src/__tests__/` 命中但同文件�?`vi.mock\|vi.spyOn\|vi.stubGlobal` �?视为违规
- `grep "import.meta.env" frontend/src/__tests__/` 命中但无 `vi.stubEnv` �?视为违规
- `grep "window.location" frontend/src/__tests__/` 命中但无 mock �?视为违规
- 测试�?CI 与本地结果不一致（依赖真实环境）→ 视为违规

**反模�?*�?```typescript
// 禁止：测试直接调用真�?fetch / localStorage 而无 vi.spyOn / vi.stubGlobal mock，导�?CI 无网络环境下失败、本地有缓存通过
```

**正确模式**：`vi.spyOn(global, 'fetch').mockResolvedValue(...)` mock fetch + `vi.stubGlobal('localStorage', { getItem, setItem, removeItem })` mock localStorage + `vi.stubEnv('VITE_API_BASE', '/api/v1')` mock env �?测试结束 `vi.restoreAllMocks()`

**配置参数**：`cross_layer_contract_test_sync.external_dependency_isolation.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_mock_for_external_deps`（是否强制外部依�?mock，默�?true）、`external_deps_to_mock`（需 mock 的依赖列表，默认 `["fetch", "localStorage", "sessionStorage", "window", "import.meta.env"]`）、`forbid_real_env_in_test`（是否禁止测试依赖真实环境，默认 true）、`auto_restore_mocks`（是否自�?restoreAllMocks，默�?true）在 `config.yaml` �?`cross_layer_contract_test_sync.external_dependency_isolation` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.35.0 meta-rule #47 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-177

**适用**：所有前端测试（单元测试 / 集成测试 / Hook 测试 / 组件测试�?**不适用**：纯函数测试（无外部依赖）、TypeScript 类型测试（`tsd`）、常量与枚举测试

**历史教训**：异步同�?Hook 测试依赖真实 `fetch` �?`localStorage`，本地有缓存与网络通过，CI 无网络环境下失败；同时测�?mock 未设�?`task_mode` 字段，导�?mock 与生产代码字段集不一致。修复：所有外部依赖必须显�?`vi.spyOn` / `vi.stubGlobal` / `vi.stubEnv` mock，确保测试可重复�?
---

### 36. 调度器运行时治理前端侧（meta-rules #48-51 落地）🆕v4.40

> 本维度对�?`xianyu-hunter-dev` v4.36.0 meta-rules #48（调度器运行时开关对称性）/ #49（时间参数配置化�? #50（长生命周期对象状态清理）/ #51（用户输入时间表达式校验，experimental），与后�?`xianyu-backend-code-review` v4.37.0 维度 36 �?B-REVIEW-178/179/180/181 联动。前端侧新增 4 �?F-REVIEW 检查点（F-REVIEW-136~139），聚焦于：调度器开关状态在前端的可见性与同步、前端轮询间隔的配置化、React Hook �?cleanup 机制、用户输�?cron 表达式的前端校验�?
#### F-REVIEW-136：SCHEDULER-STATUS-SYNC 调度器开关状态前端同步（meta-rule #48 前端侧）🆕v4.40

**检查点**：前端必须实时同步后端调度器的开关状态（enabled/disabled），用户切换开关后必须调用后端 API 持久化，前端状态必须以 `GET /api/scheduler/status` 返回值为唯一可信源，禁止前端独立维护 `enabled` 状态�?
**检查项**�?1. 调度器开�?UI 组件（Switch/Toggle）的 `checked` 状态必须从后端 `GET /api/scheduler/status` 响应读取，禁止前端独�?`useState` 维护
2. 用户切换开关后必须 `POST/PATCH /api/scheduler/config` 持久化到后端，前端状态更新必须在 API 成功响应�?3. API 失败时前端状态必须回滚到切换前值，并显示错误提�?4. 前端必须有定时轮询（�?`setInterval(fetchSchedulerStatus, 10000)`）同步后端状态，避免多端操作不一�?5. 轮询间隔�?`config.yaml` 读取不硬编码

**判断信号**�?- `grep "schedulerStatus\\|scheduler.*enabled" frontend/src/` 后检查状态来源是否为 API 响应 �?前端独立 `useState` 视为违规
- `grep "Switch.*onChange" frontend/src/` 后检�?onChange 是否调用 API �?缺失 API 调用视为违规
- `grep "setInterval.*scheduler" frontend/src/` 检查是否有定时轮询 �?缺失视为违规

**反模�?*�?```typescript
// 前端独立维护 enabled 状态，不调用后�?API
const [enabled, setEnabled] = useState(false);
<Switch checked={enabled} onChange={setEnabled} />  // �?API 调用
```

**正确模式**：`useSchedulerStatus()` 读取状�?�?`api.patch` 持久�?�?乐观更新 + 失败回滚 + `message.error` 提示

**配置参数**：`scheduler_runtime_governance_frontend.scheduler_status_sync.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_api_source`（是否强�?API 为唯一可信源，默认 true）、`require_polling`（是否强制定时轮询，默认 true）、`polling_interval_ms`（轮询间隔，默认 10000）、`require_rollback_on_failure`（是否强制失败回滚，默认 true）在 `config.yaml` �?`scheduler_runtime_governance_frontend.scheduler_status_sync` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #48 + 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-178

**适用**：所有调度器开�?UI（批量采�?Cookie 同步/状态回查）、配置页面中的功能开关组�?**不适用**：纯前端 UI 状态开关（如暗色模�?侧边栏折叠）、无后端持久化需求的临时开�?
**历史教训**：前端批量采集开�?`useState(false)` 独立维护，用户切换后未调用后�?API，刷新页面后状态丢失；且多端操作时前端显示与后端实际状态不一致，用户以为已禁用但后端仍持续执行�?
---

#### F-REVIEW-137：POLLING-INTERVAL-CONFIG 轮询间隔配置化（meta-rule #49 前端侧）🆕v4.40

**检查点**：前端所有定时轮询（`setInterval`/`setTimeout` 递归调用的轮询）的间隔时间必须从配置读取，禁止硬编码字面量数字；配置来源优先级：后端 API 响应 > 前端 config > 默认值�?
**检查项**�?1. `grep "setInterval\\|setTimeout" frontend/src/` 后检查间隔参数来�?�?字面量数字视为违�?2. 轮询间隔必须从配置读取（�?`import { pollingInterval } from '@/config'` 或后�?API 响应�?3. 配置必须提供默认值兜底（�?`pollingInterval ?? 10000`�?4. 页面不可见时（`document.hidden`）必须暂停或降频轮询，使�?`Page Visibility API`
5. 组件卸载时必�?`clearInterval` 清理定时�?
**判断信号**�?- `grep "setInterval\\([^,]*,\\s*\\d+\\)" frontend/src/` 匹配到字面量数字 �?视为违规
- `grep "document.hidden\\|visibilitychange" frontend/src/` 检查是否有页面可见性优�?�?缺失视为 WARNING

**反模�?*�?```typescript
// 硬编码轮询间�?10 �?useEffect(() => {
  const timer = setInterval(fetchData, 10000);  // 字面�?10000
  return () => clearInterval(timer);
}, []);
```

**正确模式**：`config.pollingInterval ?? 10000` 读取间隔 �?`setInterval` 轮询 �?`visibilitychange` 事件暂停/恢复 �?cleanup `clearInterval` + `removeEventListener`

**配置参数**：`scheduler_runtime_governance_frontend.polling_interval_config.enabled`（开关，默认 true）、`severity`（MAJOR）、`forbidden_literals_ms`（禁止的字面量毫秒数，默�?`[5000, 10000, 30000, 60000]`）、`require_default_fallback`（是否强制默认值兜底，默认 true）、`require_visibility_optimization`（是否强制页面可见性优化，默认 true）在 `config.yaml` �?`scheduler_runtime_governance_frontend.polling_interval_config` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #49 + 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-179

**适用**：所有前端定时轮询场景（数据刷新/状态同�?心跳检�?SSE 断线重连�?**不适用**：防�?节流场景（如搜索输入防抖 400ms，属�?UX 参数而非轮询间隔）、动画帧率（`requestAnimationFrame`）、一次性延迟执行（`setTimeout` 非递归�?
**历史教训**：前端状态页 `setInterval(fetchStatus, 10000)` 硬编�?10 秒轮询，用户切到后台标签页后仍持续请求，浪费带宽与服务器资源；且间隔无法根据网络环境调整（弱网环境应降频）�?
---

#### F-REVIEW-138：HOOK-CLEANUP-COMPLETENESS 长生命周�?Hook cleanup 完整性（meta-rule #50 前端侧）🆕v4.40

**检查点**：React Hook 中创建的所有副作用资源（定时器/事件监听�?WebSocket/SSE/订阅/AbortController）必须在 `useEffect` �?cleanup 函数中完整清理，禁止遗漏导致内存泄漏或僵尸更新�?
**检查项**�?1. `useEffect` 中创建的 `setInterval`/`setTimeout` 必须�?cleanup �?`clearInterval`/`clearTimeout`
2. `useEffect` 中添加的 `addEventListener` 必须�?cleanup �?`removeEventListener`
3. `useEffect` 中创建的 `WebSocket`/`EventSource`(SSE) 必须�?cleanup �?`close()`
4. `useEffect` 中创建的 `AbortController` 必须�?cleanup �?`abort()`
5. `useEffect` 中创建的 Zustand `subscribe` 必须�?cleanup 中调用返回的 `unsubscribe` 函数
6. 组件卸载后禁止更�?state（`isMounted` ref �?`AbortController` 防护�?
**判断信号**�?- `grep "useEffect" frontend/src/` 后逐个检查是否有 `return () => { ... }` cleanup �?缺失视为违规
- `grep "setInterval\\|addEventListener\\|new WebSocket\\|new EventSource" frontend/src/` 后检查对�?cleanup �?缺失视为违规
- `grep "subscribe(" frontend/src/` 后检查返回值是否在 cleanup 中调�?�?缺失视为违规

**反模�?*�?```typescript
// useEffect 创建定时器但�?cleanup
useEffect(() => {
  setInterval(fetchData, 10000);  // �?cleanup，组件卸载后仍执�?}, []);

// SSE 连接�?cleanup
useEffect(() => {
  const es = new EventSource('/api/events/stream');
  es.onmessage = (e) => setData(JSON.parse(e.data));
  // �?es.close() cleanup
}, []);

// Zustand subscribe �?unsubscribe
useEffect(() => {
  store.subscribe((state) => setLocalState(state.value));
  // �?unsubscribe cleanup
}, []);
```

**正确模式**：`useEffect` 中创�?`setInterval`/`EventSource`/`subscribe`/`AbortController` �?cleanup `return () => { clearInterval; es.close; unsubscribe; abortController.abort }`；卸载后防护�?`let isMounted = true` + `if (isMounted) setData`

**配置参数**：`scheduler_runtime_governance_frontend.hook_cleanup_completeness.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_cleanup_for`（必�?cleanup 的副作用类型列表，默�?`["setInterval", "setTimeout", "addEventListener", "WebSocket", "EventSource", "subscribe", "AbortController"]`）、`require_unmount_guard`（是否强制卸载后防护，默�?true）在 `config.yaml` �?`scheduler_runtime_governance_frontend.hook_cleanup_completeness` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #50 + 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-180

**适用**：所�?React Hook（`useEffect`/`useLayoutEffect`/自定�?Hook）；创建副作用资源的组件；SSE/WebSocket 实时数据消费组件；Zustand store 订阅组件
**不适用**：纯计算 Hook（无副作用）、只�?Hook（如 `useMemo`/`useCallback`）、SSR 场景（无 DOM 环境�?
**历史教训**：SSE 事件流组�?`useEffect` 中创�?`EventSource` 但无 cleanup，用户切换页面后 SSE 连接未关闭，持续接收事件并尝�?`setState`，导�?组件已卸载仍更新 state"�?React 警告与内存泄漏�?
---

#### F-REVIEW-139：CRON-EXPR-FRONTEND-VALIDATE cron 表达式前端校验（meta-rule #51 前端侧，experimental）🆕v4.40 experimental

**检查点**：前端接受用户输�?cron 表达式的表单组件必须在提交前进行前端校验，解析失败的 cron 表达式必须显示结构化错误提示，最小间隔阈值从配置读取�?
**检查项**�?1. 接受 cron 表达式输入的 `<Input>` / `<Input.TextArea>` 必须有前端校验（`onChange` �?`onBlur` 触发�?2. 校验函数必须使用 `cron-parser` 或等价库解析表达式，解析失败显示结构化错�?3. 校验通过后必须计算最小执行间隔，低于阈值的显示警告（不阻塞提交但提示用户）
4. 最小间隔阈值从 `config.yaml` 读取（默�?60 秒）
5. 表单提交时必须再次校验，禁止提交无效 cron 表达�?
**判断信号**�?- `grep "cron\\|schedule_cron" frontend/src/` 后检查是否有前端校验 �?缺失视为违规
- `grep "cron-parser\\|cronstrue" frontend/src/` 检查是否使用专业库解析 �?内联正则视为 WARNING

**反模�?*�?```typescript
// 接受任意输入，无前端校验
<Input
  value={cronExpr}
  onChange={(e) => setCronExpr(e.target.value)}
  placeholder="* * * * *"
/>
// 提交时直接发送到后端，无前端校验
const handleSubmit = () => {
  api.post('/api/tasks', { schedule_cron: cronExpr });  // 无校�?};
```

**正确模式**：`cron-parser` �?`parseExpression()` 解析 �?计算实际间隔 vs `config.cronMinIntervalSeconds ?? 60` �?`valid/error/warning` 三态返�?�?`Input.onChange` 实时校验 + `status` 属性联�?+ `Alert` 提示 �?`handleSubmit` 提交前再次校�?
**配置参数**：`scheduler_runtime_governance_frontend.cron_expr_frontend_validate.enabled`（开关，默认 true）、`severity`（MAJOR）、`min_interval_seconds`（最小间隔阈值，默认 60）、`require_parser_library`（是否强制使用专业库，默�?true）、`require_submit_revalidate`（是否强制提交时再次校验，默�?true）在 `config.yaml` �?`scheduler_runtime_governance_frontend.cron_expr_frontend_validate` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #51（experimental�? 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-181

**适用**：所有接受用户输�?cron 表达式的表单（任务调度配�?定时采集配置/状态回查配置）
**不适用**：系统内部固�?cron 表达式（非用户输入）、interval 触发器配置（已有 interval 参数）、一次性任务（无重复执行）

**历史教训**：任务调度配置页面接受任�?cron 表达式输入，无前端校验，用户输入 `* * * * *`（每分钟执行）直接提交到后端，后端虽有校验但前端无即时反馈，用户体验差且增加无效请求�?
---

#### F-REVIEW-144：PARAM-CHAIN-EXEC-FRONTEND 参数链闭环验证（meta-rule #52 前端侧）🆕v4.42

**维度**�? API 契约
**严重等级**：critical（P0，过滤参数未消费导致数据泄漏�?
**检查点**：前端定义的 query 参数必须能在后端找到对应的消费逻辑，前端发送的过滤参数必须被后端实际消�?
**检查项**�?1. 前端 API 调用传递的过滤参数（如 market_ratio、price_range）必须对应后端的消费函数
2. 前端 types.ts 中声明的过滤参数字段必须与后�?API 签名一�?3. 前端单元测试应验�?传参 vs 不传�?的请�?URL 差异

**判断信号**�?- `grep "market_ratio\|price_range" frontend/src/api/` 但后端无对应消费逻辑 �?视为违规
- 前端 types.ts 声明过滤参数但后�?API 签名无对应参�?�?契约不一�?
**配置参数**：`param_chain_exec_frontend.metadata_whitelist`（默认同后端）在 `config.yaml` �?`param_chain_exec_frontend` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #52

**适用**：所有有过滤参数的列表查�?API 前端调用
**不适用**：GET 单个资源详情、DELETE 接口、创建类 POST 接口

**历史教训**：前端传�?`market_ratio=0.85` 参数但后�?`evaluations_list.py` 未调�?`PriceStrategy.check`，导致过滤未生效。修复：前后端同步闭�?
---

#### F-REVIEW-145：MODE-VERTICAL-CHAIN-FRONTEND 业务模式纵向链路一致性（meta-rule #53 前端侧）🆕v4.42

**维度**�? 业务逻辑
**严重等级**：critical（P0，模式退化导致业务逻辑失效�?
**检查点**：前端必须为每个 mode 枚举值提供对应路由、页面、组件，mode 字段名前后端严格一�?
**检查项**�?1. 前端枚举值必须与后端一致（�?AUTO/SEMI_AUTO/MANUAL�?2. 每个 mode 值在前端路由/页面/组件中都有引�?3. SEMI_AUTO 模式必须有确认路由（�?/confirm-buy�?4. mode 字段名严�?snake_case 透传，禁�?camelCase 转换

**判断信号**�?- `grep "SEMI_AUTO\|AUTO\|MANUAL" frontend/src/` 在路�?页面中未命中 �?链路断裂
- 前端 types.ts �?`taskMode` 而后端用 `task_mode` �?命名漂移

**配置参数**：`mode_vertical_chain_frontend.required_layers`（默�?`["router","page","component","api_wrapper"]`）、`mode_vertical_chain_frontend.mode_field_names`（默认同后端）在 `config.yaml` �?`mode_vertical_chain_frontend` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #53

**适用**：任务执行模式、通知模式、采集模式的前端实现
**不适用**：纯展示�?mode 字段、内部状态字段、单一布尔开�?
**历史教训**：SEMI_AUTO 模式退化为 CONFIRM/NOTIFY，前端无 /confirm-buy 路由，用户点击通知无反应。修复：新增 ConfirmBuy 页面+路由

---

#### F-REVIEW-146：MOCK-SYNC-BOUNDARY-FRONTEND mock 同步与边界精确性（meta-rule #55 前端侧）🆕v4.42

**维度**�?2 可测试�?**严重等级**：critical（P0，mock 错配导致测试假阳�?假阴性）

**检查点**：前�?vitest mock 类型必须与被 mock 对象的同�?异步特性匹配，mock 数据必须覆盖完整字段�?
**检查项**�?1. 同步函数�?`vi.fn()`，异步函数用 `vi.fn().mockResolvedValue()` �?`vi.mock()` 中用 async
2. mock 数据必须覆盖组件访问的所有字�?3. 测试必须断言副作用未发生（如未发起真�?API 请求�?
**判断信号**�?- `grep "vi.fn\(\)" frontend/src/__tests__/` 但被 mock 函数�?async �?违规
- mock 数据缺字段导致组件渲�?NPE �?不完�?
**配置参数**：`mock_sync_frontend.type_mapping`（默�?`{"sync":"vi.fn()","async":"vi.fn().mockResolvedValue()"}`）、`mock_sync_frontend.required_assertions`（默�?`["no_real_api_request","no_real_router_change"]`）在 `config.yaml` �?`mock_sync_frontend` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #55

**适用**：所�?vitest 单元测试、集成测试中�?mock
**不适用**：E2E 测试、快照测�?
**历史教训**：后�?AsyncMock 用在同步函数导致测试失败，前端类似问题用 vi.fn() mock 异步函数也会导致 await 失败

---

#### F-REVIEW-147：FILTER-RESULT-TRANSPARENCY-UI 过滤结果透明�?UI（meta-rule #56 前端侧）🆕v4.42

**维度**�? API 契约
**严重等级**：warning（P1，用户无法理�?为何查不到数�?�?
**检查点**：列表查�?UI 同时�?�? 个过滤参数时必须透明化展示当前生效的过滤规则组合

**检查项**�?1. 关键过滤参数提供 Tooltip 说明查询规则（用 QuestionCircleOutlined 图标�?2. 空结果时区分"无数�?vs"被过滤排�?vs"全部数据"三态（filter_summary�?3. UI 显式列出当前生效的过滤参数组�?4. 业务参数展示语义化文案（�?低于市场参考价 15%"而非"0.85"�?
**判断信号**�?- `grep "filter.*range\|market.*ratio\|min.*max" frontend/src/pages/` 在列�?UI 但无 `Tooltip`/`filter_summary` �?违规
- `grep "empty.*data\|no.*data"` 但无 `filtered_count`/`total_count` 区分 �?违规

**配置参数**：`filter_transparency_ui.min_filter_params`（默�?2）、`filter_transparency_ui.required_elements`（默�?`["tooltip","filter_summary"]`）、`filter_transparency_ui.filter_summary_states`（默�?`["no_data","filtered_empty","all_data"]`）在 `config.yaml` �?`filter_transparency_ui` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #56

**适用**：所有多参数列表查询 UI（评估明�?商品列表/订单列表/仪表盘过滤）
**不适用**：单一过滤参数、用户主动输入的查询条件、详情页

**历史教训**：用户调�?低于市场参考价"�?0.85 后，评估明细菜单仍能查出价格上限 800 的商品，�?UI 无任何提示当前生效的过滤规则。修复：在价格范�?label 处添�?QuestionCircleOutlined 图标+Tooltip 说明查询规则

---

#### F-REVIEW-148：ASYNC-AWAIT-SYNC-CHECK-FRONTEND async/await 同步性检查（meta-rule #57 前端侧）🆕v4.43

**维度**�?0 Hooks 设计模式
**严重等级**：critical（P0，useEffect 直接�?async 函数导致 React 警告 + 内存泄漏�?**规范引用**：meta-rule #57 async/await 同步性静态检查（前端侧）

**检查点**：React useEffect �?async 函数必须�?`.then()` �?IIFE 包裹，禁�?`async () => {}` 直接传给 useEffect

**检查项**�?1. useEffect 回调函数禁止�?async 函数（`useEffect(async () => {...})` 视为违规�?2. useEffect 内的 async 操作必须�?IIFE 包裹�?`.then()` 链式调用
3. 必须�?`cancelled` 标志防止组件卸载�?setState（内存泄漏防护）
4. 事件回调（onClick/onSubmit）中�?async 函数必须处理 rejection

**判断信号**�?- `grep "useEffect(async" frontend/src/` �?视为违规
- `grep "useEffect.*async.*=>" frontend/src/` �?视为违规

**反模�?*�?```typescript
// useEffect 直接�?async 函数
useEffect(async () => {
  const data = await fetchData();
  setData(data);
}, []);
// React 警告: "Effect callback cannot be async"
// cleanup 返回 Promise 导致取消逻辑失效
```

**正确模式**：`useEffect` 内用 `let cancelled = false` + IIFE `(async () => { await fetchData(); if (!cancelled) setData(data) })()` + cleanup `cancelled = true`

**配置参数**：`meta_rules_57_63_frontend.frontend_async_await_check.enabled`（默�?true）、`meta_rules_57_63_frontend.frontend_async_await_check.severity`（默�?CRITICAL）、`meta_rules_57_63_frontend.frontend_async_await_check.forbidden_patterns`（默�?`["useEffect(async", "useEffect.*async.*=>"]`）、`meta_rules_57_63_frontend.frontend_async_await_check.require_cancellation_flag`（默�?true）在 `config.yaml` �?`meta_rules_57_63_frontend.frontend_async_await_check` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #57

**适用**：React useEffect 副作用、事件回调（onClick/onSubmit 等）中的 async 函数
**不适用**：top-level await（模块顶层）、`await import()` 动态导入、async generator 函数

**历史教训**：useEffect 直接�?async 函数导致 React 警告 "Effect callback cannot be async"，且 cleanup 返回 Promise 导致取消逻辑失效，组件卸载后异步操作�?setState 引发内存泄漏

---

#### F-REVIEW-149：HTTP-ERROR-LOCALIZATION HTTP 错误本地化（meta-rule #59 前端侧）🆕v4.43

**维度**�? API 契约
**严重等级**：warning（P1，优先用后端英文 detail 对中文用户不友好�?**规范引用**：meta-rule #59 HTTP 状态码精细化映射表（前端侧�?
**检查点**：已知状态码优先用前端中�?`statusMessages[status]`，后�?detail 仅作 fallback

**检查项**�?1. 已知状态码优先用前端中文消息（`statusMessages[status]`�?2. 多状态码场景必须建立状态码 �?中文消息映射�?3. 未知状态码可回退到后�?detail，但必须标注 fallback 行为
4. 状态码映射表必须在 `api/<�?.ts` 顶层声明，禁止散落在组件�?
**判断信号**�?- `grep "detail ||" frontend/src/` �?视为违规（优先用 detail 而非 statusMessages�?- `grep "message.error.*detail" frontend/src/` �?视为违规

**反模�?*�?```typescript
catch (err) {
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;
  message.error(detail || statusMessages[status]);  // 优先用后端英�?detail
}
// 用户看到 "Failed to collect item: detail page unavailable or item removed"
// 中文用户无法理解
```

**正确模式**：`COLLECT_ERROR_MESSAGES: Record<number, string>` 状态码→中文消息映射（503/403/440/441/410/502）→ catch �?`status` 查表优先展示中文 �?未知状�?fallback �?`detail || fallbackMessage`

**配置参数**：`meta_rules_57_63_frontend.frontend_http_error_localization.enabled`（默�?true）、`meta_rules_57_63_frontend.frontend_http_error_localization.severity`（默�?WARNING）、`meta_rules_57_63_frontend.frontend_http_error_localization.prefer_frontend_message`（默�?true）、`meta_rules_57_63_frontend.frontend_http_error_localization.status_messages_required`（默�?true）、`meta_rules_57_63_frontend.frontend_http_error_localization.fallback_to_detail`（默�?true）、`meta_rules_57_63_frontend.frontend_http_error_localization.localized_languages`（默�?`["zh-CN"]`）在 `config.yaml` �?`meta_rules_57_63_frontend.frontend_http_error_localization` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #59

**适用**：所�?HTTP 错误响应处理（catch 块中读取 `err.response.status` �?`err.response.data.detail`�?**不适用**：前端无对应状态码映射的未知错误、调试模式需展示原始 detail、纯技术内部错误不向用户展�?
**历史教训**：useEvalCollect.ts 优先用后�?detail 展示 "Failed to collect item 1053036882534: detail page unavailable or item removed"，对中文用户不友好，用户无法理解错误含义。修复：建立 COLLECT_ERROR_MESSAGES 状态码映射表，优先用中文消�?
---

#### F-REVIEW-150：ERROR-CHAIN-TRANSPARENT 错误链透明化（meta-rule #61 前端侧）🆕v4.43

**维度**�? API 契约 / 4 业务逻辑
**严重等级**：warning（P1，仅展示"采集失败"�?reason 用户无法判断�?**规范引用**：meta-rule #61 异常日志语义保留规范（前端侧�?
**检查点**：错误链路需透明展示 reason/failure_reason，用户可见错误必须含可操作建�?
**检查项**�?1. 错误消息必须�?reason 字段（来自后�?failure_reason�?2. 错误消息必须含可操作建议（如"请重新登录闲�?�?3. 错误必须标注 retryable 让用户知道是否可重试
4. 多阶段降级链必须合并展示最终生效路径（�?官方采集失败 �?降级到模拟采�?必须�?UI 体现�?
**判断信号**�?- `grep "message.error\|notification.error" frontend/src/` 后检查错误消息是否含 reason 与建�?- `grep "message.error\('采集失败'\)" frontend/src/` �?视为违规（无 reason�?
**反模�?*�?```typescript
message.error('采集失败');
// 用户无法判断�?cookie 过期还是反爬限制
// 需查看后端日志才能定位
```

**正确模式**：`message.error({ content: \`采集失败�?{reason}。建议：${actionHint}\`, duration: 8 })` 或结构化对象 `{ title, reason: failure_reason, suggestion: getSuggestionByReason(), retryable: isRetryable() }`

**配置参数**：`meta_rules_57_63_frontend.frontend_error_chain_transparent.enabled`（默�?true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.severity`（默�?WARNING）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.require_reason`（默�?true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.require_suggestion`（默�?true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.require_retryable_flag`（默�?true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.multi_stage_merge`（默�?true）在 `config.yaml` �?`meta_rules_57_63_frontend.frontend_error_chain_transparent` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #61

**适用**：所有错误展示组件（message.error / notification.error / Modal.error�?**不适用**：纯成功场景、loading 状态、开发调试日志（console.error�?
**历史教训**：前端仅展示"采集失败"�?reason，用户无法判断是 cookie 过期还是反爬限制，需查看后端日志才能定位。修复：错误消息�?reason + suggestion + retryable 三字�?
---

#### F-REVIEW-151：EXTERNAL-RESOURCE-CLEANUP-FRONTEND 外部资源清理（meta-rule #62 前端侧）🆕v4.43

**维度**�?0 Hooks 设计模式 / 6 Zustand 状态管�?**严重等级**：critical（P0，组件卸载后资源未释放导致内存泄漏与重复消息�?**规范引用**：meta-rule #62 外部资源生命周期配对管理（前端侧�?
**检查点**：useEffect 内创建的订阅/定时�?AbortController 必须�?cleanup 中释�?
**检查项**�?1. useEffect 内创建的 WebSocket 必须�?cleanup 中调�?`ws.close()`
2. useEffect 内创建的 EventSource 必须�?cleanup 中调�?`es.close()`
3. useEffect 内的 `setInterval`/`setTimeout` 必须�?cleanup 中调�?`clearInterval`/`clearTimeout`
4. useEffect 内的 `addEventListener` 必须�?cleanup 中调�?`removeEventListener`
5. useEffect 内的 AbortController 必须�?cleanup 中调�?`controller.abort()`
6. useEffect 必须返回 cleanup 函数（当创建了上述资源时�?
**判断信号**�?- `grep "useEffect" frontend/src/` 后检查是否返�?cleanup 函数
- `grep "setInterval\|setTimeout\|addEventListener\|new WebSocket\|new AbortController" frontend/src/` 检查是否在 cleanup 中释�?
**反模�?*�?```typescript
useEffect(() => {
  const ws = new WebSocket('ws://localhost:8080');
  ws.onmessage = (e) => setMessage(e.data);
  // 缺少 return () => ws.close();
}, []);
// 组件卸载�?WebSocket 仍保持连�?// 导致内存泄漏与重复消�?```

**正确模式**：`useEffect` 内创�?`AbortController` + `WebSocket` �?cleanup `return () => { controller.abort(); ws.close() }`

**配置参数**：`meta_rules_57_63_frontend.frontend_external_resource_cleanup.enabled`（默�?true）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.severity`（默�?CRITICAL）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.resource_types`（默�?`["WebSocket", "EventSource", "setInterval", "setTimeout", "addEventListener", "AbortController"]`）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.require_cleanup_return`（默�?true）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.pair_required`（默�?true）在 `config.yaml` �?`meta_rules_57_63_frontend.frontend_external_resource_cleanup` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #62

**适用**：所�?useEffect 副作用中创建的外部资源（WebSocket/EventSource/定时�?事件监听�?AbortController�?**不适用**：无副作用的纯渲染组件、React 组件卸载时自动清理的资源（如 useState 管理的状态）

**历史教训**：useEffect 创建 WebSocket 但无 cleanup，组件卸载后 WebSocket 仍保持连接，导致内存泄漏与重复消息（每次组件重新挂载都会新建连接�?
---

#### F-REVIEW-152 experimental：URL-STATE-SYNC-FALLBACK URL↔状态同步失败回退（meta-rule #64 前端侧）🆕v4.44 experimental

**维度**�? React 状态管�?/ 19 跨组件状态同�?**严重等级**：critical（P0，URL �?active sheet 不一致导�?useParams 返回错误值，业务逻辑误判�?**规范引用**：meta-rule #64 URL↔状态同步失败回退（experimental�?
**检查点**：SheetWorkspace 多页签应用中，URL 变化触发 openSheet 失败时，必须回退 URL 到当�?active sheet �?path

**检查项**�?1. useSheetSync Hook 监听 URL 变化时，�?openSheet 返回 false（路径未注册/栈满），必须调用 `navigate(activeSheet.path, { replace: true })` 回退 URL
2. 回退必须�?URL 变化事件处理中同步执行，不能延迟到下一帧（防止 useParams 读取到错误的 URL�?3. 回退动作必须记录日志（`logger.debug('URL sync failed, fallback to active sheet')`�?
**判断信号**�?- `grep "openSheet\|findSheetMeta" frontend/src/hooks/useSheetSync.ts` 后检查是否在 openSheet 失败时回退 URL
- `grep "navigate\|location.pathname" frontend/src/hooks/useSheetSync.ts` 检查是否有 fallback 逻辑

**反模�?*�?```typescript
useEffect(() => {
  const sheet = findSheetMeta(location.pathname);
  if (sheet) {
    openSheet(sheet.id);
  }
  // 缺少 else { navigate(activeSheet.path, { replace: true }) }
}, [location.pathname]);
// URL 已改变但 activeId 未变 �?useParams() 返回错误�?�?isEdit 误判�?false
```

**正确模式**：`useEffect` �?`findSheetMeta(pathname)` �?`openSheet(sheet.id)` 失败�?sheet 未找到时 `navigate(activeSheet.path, { replace: true })` 回退 + `logger.debug` 记录

**配置参数**：`url_state_sync_fallback` 节点（在 `config.yaml` 管理，不硬编码）�?- `enabled`（默�?`true`，开关本检查）
- `fallback_strategy`（默�?`replace`，回退策略：replace/push�?- `detection_patterns`（默�?`["navigate", "openSheet", "findSheetMeta"]`，需要检测的函数�?- `applicable_routes`（默�?`["/tasks", "/config/search"]`，适用路由白名单，均为 basename 内相对路由，不含 `/xianyu` 前缀）

**对应编码规范**：详�?`xianyu-hunter-dev` v4.39.0 experimental meta-rule #64

**适用**：SheetWorkspace 多页签应用（useSheetSync Hook）；URL �?sheet 状态双向同步场�?**不适用**：单页应用（�?SheetWorkspace）；静态路由（无动�?sheet 注册�?
**历史教训**：任务修改流程中点击 Step 3「全局搜索配置」按钮，navigate('/app/config/search') 多了 /app 前缀（basename），findSheetMeta 返回 undefined，触�?React Router 重定向到 /。此�?URL 变为 /，但 activeId 仍指�?TaskEditor，useParams().id 返回 undefined，isEdit 误判�?false，提交时创建重复任务�?
**experimental 观察�?*：案例数<3 次，�?meta-rule #36 门槛规则�?experimental，观察期 2026-07-08 �?2026-10-08�? 季度）。观察期内若再出�?�? 个相�?bug 则升级为正式规范，否则废弃�?
---

#### F-REVIEW-153 experimental：SW-CACHE-VERSION-SYNC SW 缓存版本同步（meta-rule #65 前端侧）🆕v4.44 experimental

**维度**�?3 PWA 配置 / 10 Hooks 设计模式
**严重等级**：warning（P1，缓存旧版本导致功能异常，但用户可手动刷新解决）
**规范引用**：meta-rule #65 Service Worker 缓存版本同步（experimental�?
**检查点**：PWA 应用构建时生成的版本哈希必须与前端运行时检测的版本一致，版本不一致时触发 skipWaiting 强制更新

**检查项**�?1. vite-plugin-pwa 配置必须生成版本哈希（`strategies: 'generateSW'`，`manifest: { version: process.env.VITE_BUILD_VERSION }`�?2. 前端必须�?sw.js 注册时监�?`updatefound` 事件，新 SW 进入 waiting 状态时提示用户刷新
3. 用户确认刷新时调�?`registration.waiting.postMessage({ type: 'SKIP_WAITING' })` 触发 skipWaiting
4. 版本检测必须在应用启动时执行（main.tsx �?App.tsx），不能延迟到用户操作后

**判断信号**�?- `grep "vite-plugin-pwa" frontend/vite.config.ts` 检查是否配置版本生�?- `grep "updatefound\|SKIP_WAITING\|registration.waiting" frontend/src/` 检查是否有版本检测逻辑
- `grep "navigator.serviceWorker.register" frontend/src/` 检查是否有版本同步 Hook

**反模�?*�?```typescript
// vite.config.ts 缺少版本配置
VitePWA({
  strategies: 'generateSW',
  // 缺少 manifest.version
});

// main.tsx 注册 SW 但无版本检�?navigator.serviceWorker.register('/sw.js');
// 用户缓存旧版�?�?功能异常（如 PC 端重定向到移动端�?```

**正确模式**：`VitePWA({ strategies: 'generateSW', manifest: { version: process.env.VITE_BUILD_VERSION || Date.now() } })` + `useSWVersion()` Hook 监听 `registration.updatefound` �?`newWorker.statechange` �?`setNeedsRefresh(true)` + `skipWaiting()` 调用 `registration.waiting.postMessage({ type: 'SKIP_WAITING' })`

**配置参数**：`sw_cache_version_sync` 节点（在 `config.yaml` 管理，不硬编码）�?- `enabled`（默�?`true`，开关本检查）
- `version_detection`（默�?`updatefound`，版本检测方式：updatefound/manual�?- `skip_waiting_trigger`（默�?`postMessage`，触发方式：postMessage/reload�?- `hard_refresh_prompt`（默�?`true`，是否提示用户硬刷新�?
**对应编码规范**：详�?`xianyu-hunter-dev` v4.39.0 experimental meta-rule #65

**适用**：PWA 应用（vite-plugin-pwa）；Service Worker 缓存静态资源场�?**不适用**：非 PWA 应用（无 Service Worker）；�?SSR 应用（无客户端缓存）

**历史教训**：PC 端首次登录后重定向到 /app/m/（移动端），根因是浏览器缓存了旧�?sw.js，旧�?SPA �?useMobileDetect.ts �?pointer:coarse 触屏判断导致 PC 端误判为移动端�?
**experimental 观察�?*：案例数<3 次，�?meta-rule #36 门槛规则�?experimental，观察期 2026-07-08 �?2026-10-08�? 季度）。观察期内若再出�?�? 个相�?bug 则升级为正式规范，否则废弃�?
---

#### F-REVIEW-154：INTERCEPTOR-STATUS-CODE-DISCRIMINATION 全局拦截器状态码区分检查（meta-rule #66 前端侧）🆕v4.45

**维度**�? API 契约
**严重等级**：critical（P0，业�?401 被误判为认证失效导致用户被踢出登录页�?**规范引用**：meta-rule #66 全局拦截器状态码区分检�?
**关注�?*：axios/fetch 全局响应拦截器跳转登录页必须基于 status + detail 双重校验

**与已有规则的关系**�?- 已有 `auth_token_cookie_handling.forbidden_error_handling_patterns` 关注「业务代�?catch 块的错误处理模式�?- F-REVIEW-154 关注「axios/fetch 全局响应拦截器层面的精确化跳转条件�?- 两者互补，F-REVIEW-154 补齐了拦截器层面的检查缺�?
**检查规�?*�?1. 拦截器跳转登录页必须同时满足 `status === 401` + `detail === 'Unauthorized'`（或配置的其他认证中间件标识�?2. 禁止仅凭 `status === 401` 即跳转，未检�?`detail` 字段
3. 业务错误�?40/422/429/410）应由调用方 catch 后展�?detail，不应被全局拦截器拦截跳�?4. 拦截器处理后必须 `return Promise.reject(error)`，让调用�?catch 继续处理业务错误

**配置节点**：`config.yaml#interceptor_audit`

**配置结构**�?- `auth_redirect.conditions`：跳转条件数组（status + detail_equals + action），新增认证中间件标识时只需追加
- `auth_redirect.require_all_conditions`：true（必须同时满足所有条件）
- `auth_redirect.forbidden_interceptor_patterns`：禁止的拦截器模式（仅凭 status 跳转�?- `auth_redirect.recommended_pattern`：推荐的拦截器代码示�?- `business_error_handling`：业务错误处理数组（status + action�?- `require_reject_after_intercept`：true（拦截器必须 reject�?
**判断信号**�?- `grep -rn "status === 401" frontend/src/api/` 命中且无 `detail === 'Unauthorized'` 校验 �?拦截器过�?- `grep -rn "case 401:" frontend/src/api/` 命中�?switch 未检�?detail �?拦截器过�?- 拦截�?`if (status >= 400)` 即跳�?�?业务错误被全局拦截

**反模�?*�?```typescript
// 禁止：拦截器仅凭 status === 401 即跳转登录页，业�?401（闲�?cookie 过期）也会被误判为认证失效；应同时校�?detail === 'Unauthorized' 或使�?440 状态码区分
```

**正确模式**：拦截器 `status === 401 && detail === 'Unauthorized'` 双重校验 �?`localStorage.removeItem('xh_token')` + `globalThis.location.replace(import.meta.env.BASE_URL + 'login?redirect=...')`（排�?login �?+ `isRedirecting` 防重复跳转）�?业务 401 由调用方 catch（整页跳转必须用 `import.meta.env.BASE_URL`，禁止硬编码 `/app/` 或 `/xianyu/`）

**配置参数**：`interceptor_audit` 节点（在 `config.yaml` 管理，不硬编码）�?- `auth_redirect.conditions`（默�?`[{status: 401, detail_equals: "Unauthorized", action: "redirect_to_login"}]`，跳转条件数组）
- `auth_redirect.require_all_conditions`（默�?`true`，必须同时满�?status �?detail 才跳转）
- `auth_redirect.forbidden_interceptor_patterns`（禁止的拦截器模式，仅凭 status 跳转�?- `auth_redirect.recommended_pattern`（推荐的拦截器代码示例）
- `business_error_handling`（业务错误处理数组：440/422/429/410 由调用方 catch�?- `require_reject_after_intercept`（默�?`true`，拦截器必须 reject�?
**对应编码规范**：详�?`xianyu-hunter-dev` v4.45.0 meta-rule #66

**适用场景**：axios/fetch 全局响应拦截器；�?Bearer/JWT 认证的前端应用；SPA 应用；与后端 FastAPI BearerAuthMiddleware 配套的前�?**不适用场景**：无认证应用；纯 SSR 应用；测�?mock

**修复建议**�?- 拦截器同时校�?status + detail
- 业务错误 reject 给调用方 catch
- 拦截器必�?return Promise.reject(error)

**复盘来源**：业�?401 与认�?401 状态码冲突 Bug（卖家评估页点击标题链接跳转登录页）

---

#### F-REVIEW-220：CACHE-CONSISTENCY-CHECK 缓存一致性审查（§2.15 缓存策略规范 前端侧）🆕v4.60

**维度**：10 Hooks 设计模式 / 7 API 契约
**严重等级**：major（P1，前端缓存 TTL 超过后端导致脏数据，依赖数组缺失导致闭包陈旧值）
**规范引用**：§2.15 缓存策略规范（前端侧落地）

**检查点**：前端 `useMemo`/`useCallback` 依赖数组必须完整，本地缓存 TTL 必须与后端 `cache.live_search_ttl` 协调（前端不应长于后端 TTL），缓存失效后必须自动重新请求

**定位方法**：`grep -rn "useMemo\|useCallback\|useCache\|cache" frontend/src/` 定位前端缓存使用点

**判断标准**：
1. `useMemo`/`useCallback` 依赖数组是否完整（遗漏依赖会导致闭包捕获陈旧值）
2. 前端本地缓存 TTL 是否与后端协调（后端 `cache.live_search_ttl=5s`，前端不应长于此后端 TTL）
3. 缓存失效后是否自动重新请求（避免用户看到过期数据）

**判断信号**：
- `grep -rn "useMemo\|useCallback" frontend/src/` 后检查第二参数依赖数组 → 缺失或为空数组（且函数体引用外部变量）视为违规
- 前端 TTL 字面量数字 > 5000（5s）→ 视为可疑（超过后端 `cache.live_search_ttl`）
- 缓存失效逻辑（如 `invalidateCache`/`cache.clear`）后无 `refetch`/`fetch` 调用 → 视为违规

**反模式**：
```typescript
// 1. 依赖数组缺失，过滤条件变更后展示旧数据
const value = useMemo(() => filter(items, filterKey), []);  // 缺 filterKey 依赖

// 2. 前端 TTL 超过后端 cache.live_search_ttl
const cache = useRef({ data: null, ts: 0 });
if (Date.now() - cache.current.ts < 30000) return cache.current.data;  // 30s > 后端 5s

// 3. 缓存失效不重新请求，用户看到过期数据
invalidateCache();  // 缺少 refetch() 调用
```

**正确模式**：
1. 依赖数组完整：`useMemo(() => filter(items, filterKey), [items, filterKey])`
2. 前端 TTL 不超过后端 `cache.live_search_ttl`：从配置读取 `const cacheTtl = config.cacheTtl ?? 5000`
3. 缓存失效后自动 refetch：`invalidateCache(); void refetch();`

**配置参数**：`cache_consistency_check` 节点（在 `config.yaml` 管理，不硬编码）：
- `enabled`（默认 `true`，开关本检查）
- `backend_ttl_ms`（默认 `5000`，与后端 `cache.live_search_ttl` 同步值）
- `frontend_ttl_max_ms`（默认 `5000`，前端 TTL 上限，超过则违规）
- `require_full_deps`（默认 `true`，强制 `useMemo`/`useCallback` 依赖完整）
- `require_refetch_on_invalidate`（默认 `true`，缓存失效后必须 refetch）

**修复建议**：前端缓存 TTL 不超过后端 `cache.live_search_ttl`，依赖数组必须完整，缓存失效后必须触发 refetch

**对应编码规范**：详见 `coding-standards.md` §2.15 缓存策略规范

**适用**：所有前端 `useMemo`/`useCallback`/`useCache`/`localStorage` 缓存场景；与后端 `cache.live_search_ttl` 协调的列表查询/搜索结果缓存
**不适用**：纯静态常量缓存（如 enum 映射表、配置常量）；用户偏好持久化（如 `usePersistentState`，与后端无关）；SSR 场景（无客户端缓存）

**历史教训**：前端搜索结果缓存 TTL 设为 30s，但后端 `cache.live_search_ttl=5s` 已更新数据，导致用户看到 25s 前的过期数据；且 `useMemo` 依赖数组为空，过滤条件变更后仍展示旧数据。修复：依赖数组补全 + 前端 TTL 对齐后端 + 失效后 refetch

---

#### F-REVIEW-221：MULTI-FORMAT-INPUT-PARSE 多格式输入解析审查（§2.20 多格式输入解析规范 前端侧）🆕v4.60

**维度**：4 TypeScript 严格规范 / 7 API 契约
**严重等级**：major（P1，输入解析覆盖不全导致部分格式数据丢失，split('=') 截断值中含 = 的数据）
**规范引用**：§2.20 多格式输入解析规范（前端侧落地）

**检查点**：粘贴板解析必须覆盖所有格式（标准头/换行分隔/Header 前缀/尾分号），必须有实时解析反馈（识别 N 项/填充 N 项/无效 N 项），分割点必须用 `indexOf('=')` 而非 `split('=')` 避免值中含 `=` 被截断

**定位方法**：`grep -rn "split\|parse\|clipboard\|paste\|onPaste" frontend/src/` 定位输入解析逻辑

**判断标准**：
1. 粘贴板解析是否覆盖所有格式（标准头/换行分隔/Header 前缀/尾分号）
2. 是否有实时解析反馈（识别 N 项/填充 N 项/无效 N 项）
3. 分割点是否用 `indexOf('=')` 而非 `split('=')` 避免值中含 `=` 被截断

**判断信号**：
- `grep -rn "split('=')" frontend/src/` 命中 → 视为违规（值含 `=` 会被截断，如 `password=a=b` 丢失 `=b`）
- 粘贴板解析逻辑仅处理单一格式（如只处理 `\n` 换行分隔）→ 视为违规
- `onPaste`/`onChange` 处理函数无识别/填充/无效计数反馈 → 视为 WARNING

**反模式**：
```typescript
// 1. 用 split('=') 导致值含 = 被截断
const [key, value] = line.split('=');  // "k=v=1" → value="v"，丢失 "=1"

// 2. 仅处理单一格式（只处理换行分隔）
const lines = text.split('\n');  // 未处理尾分号、Header 前缀等格式

// 3. 无实时反馈，用户不知道识别了多少项
onPaste={(e) => {
  const data = parse(e.clipboardData.getData('text'));
  setForm(data);  // 用户不知道识别/填充/无效各几项
}}
```

**正确模式**：
1. 用 `indexOf('=')` 容错分割：`const idx = line.indexOf('='); const key = line.slice(0, idx); const value = line.slice(idx + 1);`
2. 枚举所有格式：标准头（`key=value\n`）、换行分隔、Header 前缀（`Header: value`）、尾分号（`key=value;`）
3. 实时视觉反馈：`{识别 N 项，填充 N 项，无效 N 项}` + 高亮无效行

**配置参数**：`multi_format_input_parse` 节点（在 `config.yaml` 管理，不硬编码）：
- `enabled`（默认 `true`，开关本检查）
- `supported_formats`（默认 `["standard_header", "newline_delimited", "header_prefix", "trailing_semicolon"]`，必须覆盖的格式列表）
- `forbid_split_on_equals`（默认 `true`，禁止 `split('=')`，必须用 `indexOf('=')`）
- `require_realtime_feedback`（默认 `true`，强制识别/填充/无效计数反馈）

**修复建议**：枚举所有格式 + `indexOf('=')` 容错分割 + 实时视觉反馈，参考 §2.20

**对应编码规范**：详见 `coding-standards.md` §2.20 多格式输入解析规范

**适用**：所有接受粘贴板输入的表单（批量配置/批量导入/多行文本解析）；含 `key=value` 结构的输入场景
**不适用**：单行输入框（无粘贴板解析需求）；纯数字/日期输入；结构化 JSON 输入（用 `JSON.parse` 即可）；文件上传（非文本粘贴）

**历史教训**：批量配置粘贴板解析仅处理换行分隔，用户粘贴带尾分号的格式（`key=value;`）时全部识别失败；且 `split('=')` 截断了含 `=` 的值（如 `password=a=b`），导致配置丢失。修复：枚举 4 种格式 + `indexOf('=')` 分割 + 实时计数反馈

---

#### F-REVIEW-222：STREAMING-RESPONSE-HANDLER 流式响应处理审查（§2.17 性能优化范式 前端侧）🆕v4.60

**维度**：15 SSE 重连 / 10 Hooks 设计模式
**严重等级**：critical（P0，stage=error 未清理连接导致内存泄漏 + 状态卡死，stage=done 未关闭连接导致连接泄漏）
**规范引用**：§2.17 性能优化范式（前端侧落地）

**检查点**：必须正确处理 SSE stage 事件（checking_cache/searching/filtering/done/error），stage=error 时必须清理连接和状态，stage=done 时必须关闭 EventSource 连接，必须有超时兜底处理

**定位方法**：`grep -rn "EventSource\|SSE\|event-stream\|stage" frontend/src/` 定位 SSE 处理逻辑

**判断标准**：
1. 是否正确处理 SSE stage 事件（checking_cache/searching/filtering/done/error）
2. stage=error 时是否正确清理连接和状态
3. stage=done 时是否正确关闭 EventSource 连接
4. 是否有超时兜底处理（避免 SSE 卡住无响应）

**判断信号**：
- `grep -rn "EventSource\|event-stream" frontend/src/` 后检查 stage 事件处理 → 未覆盖 error/done 视为违规
- stage=error 处理分支未调用 `es.close()` 与状态重置 → 视为违规
- stage=done 处理分支未调用 `es.close()` → 视为违规（连接泄漏）
- SSE 处理逻辑无 `setTimeout`/`AbortController` 超时兜底 → 视为 WARNING

**反模式**：
```typescript
// 1. 未处理 stage=error，错误时状态卡死在 searching
es.addEventListener('stage', (e) => {
  const { stage } = JSON.parse(e.data);
  if (stage === 'searching') setSearching(true);
  if (stage === 'done') setSearching(false);
  // 缺少 error 处理 → 错误时状态卡死
});

// 2. stage=done 未关闭连接，每次搜索泄漏一个 EventSource
if (stage === 'done') {
  setData(result);
  // 缺少 es.close() → 连接泄漏
}

// 3. 无超时兜底，SSE 卡住时 UI 永远 loading
const es = new EventSource('/api/search/stream');
// 无 setTimeout 兜底
```

**正确模式**：
1. 按 stage 分发处理：`switch(stage) { case 'checking_cache': ...; case 'searching': ...; case 'filtering': ...; case 'done': ...; case 'error': ...; }`
2. stage=error 时清理：`es.close(); setState(STATE_ERROR); clearTimeout(timer);`
3. stage=done 时关闭连接：`es.close(); setState(STATE_DONE); clearTimeout(timer);`
4. 超时兜底：`const timer = setTimeout(() => { es.close(); setState(STATE_TIMEOUT); }, config.sseTimeoutMs ?? 30000);` 在 done/error/cleanup 中 `clearTimeout(timer)`

**配置参数**：`streaming_response_handler` 节点（在 `config.yaml` 管理，不硬编码）：
- `enabled`（默认 `true`，开关本检查）
- `required_stages`（默认 `["checking_cache", "searching", "filtering", "done", "error"]`，必须覆盖的 stage 列表）
- `require_close_on_done`（默认 `true`，stage=done 时必须 `es.close()`）
- `require_close_on_error`（默认 `true`，stage=error 时必须 `es.close()`）
- `require_cleanup_on_error`（默认 `true`，error 时必须重置状态）
- `require_timeout_fallback`（默认 `true`，必须有超时兜底）
- `default_timeout_ms`（默认 `30000`，超时阈值）

**修复建议**：按 stage 分发处理 + error 时清理 + done 时关闭连接，参考 §2.17

**对应编码规范**：详见 `coding-standards.md` §2.17 性能优化范式

**适用**：所有 `EventSource`/SSE 流式响应处理（搜索/采集/批量任务进度推送）；后端使用 stage 事件协议的实时通信
**不适用**：WebSocket（非 SSE 协议）；一次性 fetch 请求（非流式）；轮询场景（无 stage 事件）；纯 SSR 场景（无客户端 EventSource）

**历史教训**：搜索 SSE 流 stage=error 时未关闭 EventSource 连接，每次搜索失败都泄漏一个连接，长时间运行后浏览器连接数耗尽；且 UI 状态卡在 searching，用户以为还在搜索。修复：按 stage 分发 + error 时清理 + done 时关闭 + 30s 超时兜底

---

## 快速自检

执行 `pwsh .trae/skills/xianyu-frontend-code-review/scripts/auto-scan.ps1` 自动检查以下阻塞项�?
1. `fetch` 请求是否包含 `credentials: 'include'`
2. axios 是否设置 `withCredentials: true`
3. token 是否写入 `localStorage`（应优先 httpOnly cookie�?4. 是否使用 `dangerouslySetInnerHTML`
5. 是否使用 `any` 类型
6. 是否存在�?`.catch()` �?7. 图标按钮是否缺少 `aria-label`
8. `v-for`/`map` 是否使用 index 作为 key
9. 是否使用 `enum`（应用字符串字面量联合）
10. `ConfigProvider` 是否�?`BrowserRouter` 外层
11. 三处映射是否同步（路由、菜单、sheetRegistry�?12. 是否使用 `JSON.parse(JSON.stringify())` 深拷贝（应用 `structuredClone`，S7784�?13. 页面组件是否使用 `minHeight: 100vh`（嵌入场景应�?`height: 100%`�?14. 交互元素文字是否使用 `colorBorder`（应�?`colorPrimary`，确保对比度�?15. 🆕 **S6819/S6844**：是否存�?`<div onClick>` / `<a onClick>` �?href 的可点击元素（应�?`<button>` + 键盘事件�?16. 🆕 **S7503**：是否存在无 `await` �?`async` 函数（应改同步函数）
17. 🆕 **S6767**：函�?组件是否存在未使用的 Props、State、参�?18. 🆕 **S7744**：是否存�?`as unknown as T` 多重断言链（应用类型守卫�?19. 🆕 **S7735**：useEffect 依赖数组是否完整（结�?ESLint react-hooks/exhaustive-deps 提示�?20. 🆕 **S6582**：是否存�?`a?.b` �?a 已确认非空的冗余可选链
21. 🆕 **S1874**：被移除�?API 是否标注 `@deprecated` 而非直接删除
22. 🆕 **S6551**：是否使�?`for...in`（应�?`Object.keys/values/entries`�?23. 🆕 状态管理函数（`activateSheet`、`closeSheet` 等）是否同步更新所有相关字段（`minimized`/`activeId` 等）
24. 🆕 嵌入�?SheetWorkspace/MainLayout 的页面是否用 `height: 100%` 而非 `100vh`
25. 🆕 vitest 测试是否�?`--no-isolate` 参数（Node v24 兼容性）
26. 🆕 antd 组件测试是否 mock `window.matchMedia`（Drawer/Grid/Skeleton�?27. 【强制】EventSource 连接包含 lastEventId 记录（`e.lastEventId`）和重连�?`?last_event_id=` 参数传�?28. 【强制】SSE useEffect 包含 `visibilitychange` 监听器，且在 cleanup �?`removeEventListener`
29. 【强制】SSE error 重连�?`MAX_RECONNECT` 上限，超限后放弃 SSE 退化为轮询
30. 【强制】全局事件监听（`visibilitychange`/`resize`/`scroll`）在 useEffect cleanup 中移�?31. 🆕v4.0 【强制】Tab/Accordion/Collapse 多视图共享数据是�?state 提升至父组件 + `destroyInactiveTabPane={false}`
32. 🆕v4.0 【强制】JSX 内是否存�?IIFE（`{(() => { ... })()}`），应提取为变量
33. 🆕v4.0 【强制】`target="_blank"` 外部链接是否�?`rel="noopener noreferrer"`
34. 🆕v4.0 【强制】图�?文字间距是否用显�?`marginRight`（非 JSX 空格�?35. 🆕v4.0 【强制】注释是否与代码逻辑一致（无误导性顺�?依赖约束说明�?36. 🆕v4.0 【强制】动态资源映射是否映射表+推断函数分离（非混合），业务参数是否通过配置管理
37. 🆕v4.1 【强制】SSE 流消费回调是否显式处�?`stage='error'` 分支（禁止与 `stage='done'`+0 结果混为一谈）
38. 🆕v4.1 【强制】SSE 错误事件是否�?`status` 分类处理�?01/403 显示"前往登录"按钮�?03/504 稍后重试�?02 重启提示�?39. 🆕v4.2 **F-REVIEW-UI-STATE-INDEPENDENCE**（�?）：受控 UI 状态不应通过 useEffect 联动路由
40. 🆕v4.3 `new Proxy()` / `new MutationObserver()` 是否赋值给局部变量后丢弃（应赋值给实例属�?模块级变量）
41. 🆕v4.3 try/finally 块中 finally 引用的变量是否在 try 之前初始化为 null/undefined
42. 🆕v4.3 多个组件对同一概念（会话有效�?登录状态）做判断时，状态变更是否双向同�?43. 🆕v4.3 错误提示中引用的路由路径/API端点是否实际存在（前端路由已注册/后端已实现）
44. 🆕v4.4 **F-REVIEW-CONFIG-DRIVEN-TOGGLE**（�?1）：高风险功能必须配置驱动，默认关闭
45. 🆕v4.5 **F-REVIEW-ERROR-SEMANTICS**（�?1）：错误文案必须与后端根因语义匹�?46. 🆕v4.5 **F-REVIEW-CONFIG-LINKAGE**（�?）：配置项从表单到后端消费全链路可追�?47. 🆕v4.6 **F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND**（�?）：多写入入口统一 updateState
48. 🆕v4.7 **F-REVIEW-FILTER-SCENARIO-FRONTEND**（�?）：按场景显式传�?include_failed 等标�?49. 🆕v4.7 **F-REVIEW-ASYNC-FEEDBACK**（�?0）：异步操作 loading �?success �?error 三态反�?50. 🆕v4.7 **F-REVIEW-DATA-FLOW-TRACE-FRONTEND**（�?1）：字段为空�?5 点逐层追踪
51. 🆕v4.7 **F-REVIEW-REUSE-PATTERN-FRONTEND**（�?8）：新增功能�?grep 复用既有模式
52. 🆕v4.8 **F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE**（�?）：暗色主题 token 动态覆�?53. 🆕v4.9 **F-REVIEW-FREQ-STATS-POLLING**（�?0）：累计统计�?API 前端定时刷新
54. 🆕v4.10 **F-REVIEW-FILTER-VISIBILITY**（�?）：filter_summary 三态提示策�?55. 🆕v4.11 **F-REVIEW-STATE-ENUM-ALIGN**（�?）：前后端状态枚举值严格对�?56. 🆕v4.11 **F-REVIEW-STATE-MACHINE-UI**（�?）：状态机每个状态值有 UI 视觉标识
57. 🆕v4.11 **F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY**（�?）：多链路触发统一 refetch 入口
58. 🆕v4.13 **F-REVIEW-ERROR-CONTRACT-TIMEOUT**（�?）：模块�?statusMessages map + isAxiosTimeout()
59. 🆕v4.13 **F-REVIEW-RETRY-BACKOFF**（�?）：可重试错误按退避序列重�?65. 🆕v4.14 **F-REVIEW-FILTER-BACKEND-ALIGN**（�?）：前端过滤与后端分类逻辑对齐
66. 🆕v4.14 **F-REVIEW-FILTER-PAGINATION-ADAPT**（�?0）：filterStatus 后同步调�?pagination 三参�?67. 🆕v4.14 **F-REVIEW-FILTER-EMPTY-STATE**（�?）：空状态判断用 filteredItems.length
68. 🆕v4.15 **F-REVIEW-DEBUG-CODE-CLEANUP**（�?1）：临时 DEBUG 代码必须移除
69. 🆕v4.16 **F-REVIEW-STATE-FUNCTIONAL-ALIGN**（�?）：UI 状态与功能可用性一�?74. 🆕v4.20 **F-REVIEW-VERSION-SOURCE-ALIGN**（�?）：版本号源语义对齐 API
75. 🆕v4.21 **F-REVIEW-FIELD-NAME-ALIGN**（�?0）：字段名三层一致�?76. 🆕v4.21 **F-REVIEW-CONFIG-PERSIST-VERIFY**（�?0）：配置持久化端到端验证
77. 🆕v4.22 **F-REVIEW-PWA-CACHE-VERIFY**（�?3）：PWA 三层缓存验证
78. 🆕v4.23 **F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION**（�?1）：LLM 模型能力集中展示
79. 🆕v4.24 **F-REVIEW-UI-PREFERENCE-PERSISTENCE**（�?0）：用户偏好�?UI 状态用 usePersistentState
80. 🆕v4.25 **F-REVIEW-THREE-STATE-NULL-SEMANTICS**（�?）：PATCH/PUT 清除覆盖显式�?null
81. 🆕v4.25 **F-REVIEW-ERROR-HANDLING-CONSISTENCY**（�?0）：catch 块用 extractApiError
82. 🆕v4.25 **F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY**（�?）：默认值统一�??? 而非 ||
83. 🆕v4.27 **F-REVIEW-ERROR-CODE-BRANCH**（�?5）：�?error_code 字段分支决策
84. 🆕v4.27 **F-REVIEW-PRECHECK-API-DELEGATION**（�?5）：数据完整性预检委托后端
85. 🆕v4.27 **F-REVIEW-MOCK-FIELD-SET-SYNC**（�?5）：mock 数据覆盖完整字段�?86. 🆕v4.32 **F-REVIEW-MULTI-USER-CONTEXT-ISOLATION**（�?8）：多用户上下文�?user_id 隔离 + 切换时清空缓�?87. 🆕v4.32 **F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING**（�?8）：token �?httpOnly cookie + credentials:include + 401/440/441/403 状态码语义分支
88. 🆕v4.33 **F-REVIEW-EFFECT-MINIMIZE**（�?）：useEffect 禁止重置用户交互控制的状态（openKeys/expandedKeys/activeKey），应用 useState 初始�?89. 🆕v4.33 **F-REVIEW-STATE-ATOMICITY**（�?）：多字段状态切换必须同步更新（封装 transition 方法或单一状态枚举）
90. 🆕v4.33 **F-REVIEW-SSE-CONN-MGMT**（�?5）：SSE 连接管理三要素（visibilitychange 监听 + last_event_id 回放 + 最大重�?10 次降级轮询）
91. 🆕v4.33 **F-REVIEW-ASYNC-RACE-GUARD**（�?0）：异步请求�?useRef 维护最新请�?ID，响应回来时对比丢弃过期响应
92. 🆕v4.33 **F-REVIEW-THEME-DYNAMIC-ADAPT**（�?）：禁止硬编码主题色，必须根�?isDark 动态设置（rowHoverBg/headerBg 等）
93. 🆕v4.33 **F-REVIEW-EMBEDDED-LAYOUT-HEIGHT**（�?）：嵌入式布局�?height:100% + flex:1，禁�?minHeight:100vh
94. 🆕v4.33 **F-REVIEW-COMPONENT-REGISTRY**（�?）：ECharts/antd 组件必须 import + register，避免静默失�?95. 🆕v4.33 **F-REVIEW-FILTER-TRANSPARENCY**（�?）：数据被过滤时展示过滤原因和条数（Modal/Tooltip 展示 filter_summary�?96. 🆕v4.33 **F-REVIEW-DATA-SOURCE-VERIFY**（�?8）：显示数据必须来自正确数据源（系统版本�?/api/about 而非 /api/config/version�?97. 🆕v4.33 **F-REVIEW-STATS-RANGE-CALIBRATE**（�?6）：统计图表范围与业务范围匹配（task_id 过滤 + P5/P95 百分位校准）
98. 🆕v4.33 **F-REVIEW-UI-SEMANTICS-SPLIT**（�?）：按钮文案表达动作（主动失效），状态显示表达状态（已失效），禁止混�?99. 🆕v4.33 **F-REVIEW-PERSIST-BUSINESS-SWITCH**（�?0）：业务开关用 usePersistentState 持久化，禁止 useState 刷新丢失
100. 🆕v4.33 **F-REVIEW-ERROR-MESSAGE-PASS**（�?0）：catch 块用 extractApiError 提取后端具体错误，禁止无信息通用错误
101. 🆕v4.33 **F-REVIEW-API-CONTRACT-CONSISTENCY**（�?1）：TS interface 字段名与后端 response_model 完全一致（snake_case 对齐�?
> **F-REVIEW 检查点详细规则**：以�?50 �?F-REVIEW 检查点的核心机�?/ 判断信号 / 修复模式 / 适用场景 / 不适用场景 / 历史教训详见对应维度章节（�? 维度号）。配置参数在 `config.yaml` 的对应节点管理�?
---

## 审查流程�? 阶段流水线）🆕v4.33

> v4.33 将原 5 阶段闭环（Phase 0-4）优化为 4 阶段流水线，新增 `coding_standards` 节点加载�?`coding-rules/` 主题文件加载，强化优先级分类（P0/P1/P2/P3）与结构化报告呈现�?
### 阶段 1：上下文加载

1. **加载 config.yaml 配置**（含 `coding_standards` 节点，v4.33 新增�?   - 读取 `scope` / `priority` / `hard_constraints` / `checklist` / `coding_standards` 等节�?   - `coding_standards` 节点提供 14 �?F-REVIEW 检查点的阈值参数（effect/sse/theme/layout/registry/filter/ui_semantics/persist/race/error/contract/source 等）
2. **识别任务类型**（前�?后端/全栈�?   - 前端任务：加�?`frontend/src/` 下的 React/TypeScript/Ant Design 文件
   - 后端任务：转�?`xianyu-backend-code-review` 技�?   - 全栈任务：前后端协同审查，识别跨边界契约问题
3. **加载对应 `coding-rules/` 主题文件**（v4.33 新增规范源联动）
   - �?`xianyu-hunter-dev/references/coding-rules/` 加载与本次审查相关的主题文件（如 EFFECT-01/SSE-01/THEME-01 等）
   - 每个 F-REVIEW checkpoint 引用对应规范编号，审查时加载规范详情
4. **确定评审范围**�?   - **待提交变更模�?*：`git diff HEAD` + `git status` 提取改动�?`.tsx/.ts/.js` 文件
   - **指定文件模式**：用户明确指定的文件列表
   - **片段评审模式**：用户粘贴的代码片段（无文件路径时仅输出建议�?5. **应用 `scope.include_paths` / `scope.exclude_paths` 过滤**，截�?`scope.max_files_per_run` 个文�?6. **对每个待评审文件收集上下�?*�?   - 使用 Read 工具读取完整文件内容
   - 使用 Grep 工具查找关键依赖（导入的组件/Hook/工具函数、Ant Design 组件、API 接口�?   - 使用 Grep 查找相关测试文件（`__tests__/*.test.ts(x)`）评估测试覆�?   - 使用 Grep 查找相关类型定义（`types.ts`）评估类型一致�?   - 记录文件的最近修改历史（`git log --oneline -5 -- <file>`�?
**判断逻辑**：范围必须收紧——只评审用户提供的或明确引用的文件，不顺便审查旁边代码�?
### 阶段 2：分层扫�?
�?`checklist` 配置�?28 大类逐层扫描，每个维度引用对�?F-REVIEW checkpoints，对比反模式示例识别问题�?
**优先级排�?*：`severity_order` × `category_order`
- 类型安全（CRITICAL�? 业务逻辑（HIGH�? 性能（MEDIUM�? 规范（LOW�?- 硬约束违规优先级最高，无论 severity 如何

**子阶�?2.1：常规规则匹�?*

�?`checklist` 配置�?28 大类逐项检查（见上�?审查规则"章节），每个维度引用对应 F-REVIEW checkpoints�?
**子阶�?2.2：配置驱动检�?* 🆕v4.31

针对配置驱动�?F-REVIEW 检查点，必须在常规规则匹配后追�?配置驱动检�?子阶段，按以下顺序扫描：

1. **业务关键字硬编码扫描**（对�?F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION�?   - �?Grep 扫描 `frontend/src/**/*.{ts,tsx}` 是否存在 `const \w*_KEYWORDS?\s*=\s*\[` �?`\.includes\(['"](卖掉了|已售|已下�?` 模式
   - 命中后检查是否调�?`/api/config/text_features` 端点拉取后端配置；未调用 �?标记�?配置节点缺失"分类�?CRITICAL 问题
2. **事件类型前缀匹配扫描**（对�?F-REVIEW-EVENT-TYPE-EXACT-MATCH�?   - �?Grep 扫描 `frontend/src/**/*.{ts,tsx}` 是否存在 `\.startsWith\(['"]\w+\.` �?`\.indexOf\(['"]\w+\.\w` 模式
   - 命中后检查是否属于配置节�?`event_type_exact_match.allowed_prefix_grouping_scenarios` 允许的统�?日志场景；不属于 �?标记�?CRITICAL 问题
3. **字段名大小写敏感扫描**（对�?F-REVIEW-FIELD-NAME-CASE-SENSITIVE�?   - �?Grep 扫描 `frontend/src/api/**/*.ts` 是否存在驼峰字段名（后端应为 snake_case），以及 `frontend/src/**/*.{ts,tsx}` 是否存在 `as any` 类型断言绕过
   - 命中后检查前�?`api/types.ts` 字段名是否与后端 Pydantic 模型一一对应；不一�?�?标记�?CRITICAL 问题
4. 🆕v4.32 **多用户上下文隔离扫描**（对�?F-REVIEW-MULTI-USER-CONTEXT-ISOLATION�?   - �?Grep 扫描 `frontend/src/stores/` 是否存在未按 `user_id` 分桶的全局单例 store（如 `create<.*>\(\)\s*=>\s*\(\{\s*orders:` 模式�?   - 命中后检查用户切换路径是否调�?`queryClient.clear()` / `useGlobalStore.getState().reset()`；未调用 �?标记�?CRITICAL 问题（跨用户数据泄漏风险�?5. 🆕v4.32 **认证 token cookie 处理扫描**（对�?F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING�?   - �?Grep 扫描 `frontend/src/api/**/*.ts` �?`fetch(` 调用是否包含 `credentials: 'include'`，`axios.create` 是否包含 `withCredentials: true`
   - �?Grep 扫描 `frontend/src/**/*.{ts,tsx}` 是否存在 `localStorage.(get|set)Item(['"]xh_token` 模式（token 不应�?localStorage�?   - �?Grep 扫描 401 错误处理分支是否区分 401/440/441/403 状态码语义；未区分 �?标记�?CRITICAL 问题（用户频繁被踢出风险�?6. 🆕v4.33 **coding_standards 节点驱动扫描**（对�?F-REVIEW-96~109�?4 项新检查点�?   - �?`coding_standards` 节点配置的阈值参数扫描（effect/sse/theme/layout/registry/filter/ui_semantics/persist/race/error/contract/source�?   - 对比反模式示例识别问题，命中后引用对应规范编号（EFFECT-01/SSE-01/THEME-01 等）

**子阶�?2.3：硬约束合规性检�?*

遍历 `hard_constraints.rules`，对每条规则�?1. 使用 Grep 工具扫描代码库（pattern 字段�?2. 匹配到的违规项记录到报告
3. �?`hard_constraints.block_on_violation=true` 且发�?CRITICAL 违规，在报告中标�?阻止合并"

**判断逻辑**：硬约束违规优先级最高，无论 severity 如何，必须在报告中突出显示。本阶段识别的问题统一归入"配置节点缺失"分类（见 Template A），与常规规则匹配结果合并后进入阶段 3 优先级分类。

**子阶段 2.4：跨层影响范围评估** 🆕v4.60

修改前端 `types.ts` / 字段定义时，自动评估后端 Pydantic / DB 影响：
1. **前端字段变更检测**：Grep 扫描本次变更是否涉及 `frontend/src/api/types.ts` 中的字段定义修改
2. **后端影响映射**：若前端字段变更，对照 `contract_single_source` 配置检查后端 Pydantic 模型对应字段是否同步修改
3. **DB 影响评估**：若后端字段变更涉及 DB 列，标记为 CRITICAL（需数据库迁移）
4. **影响传播图生成**：生成本次变更的跨层传播路径图（types.ts → Pydantic → DB），写入报告的「跨层影响图」部分

**子阶段 2.5：缓存守卫专项检查** 🆕v4.60

所有涉及缓存的代码变更，验证三项守卫：
1. **空结果不缓存**：API 返回空数组/空对象时不应写入缓存，防止脏数据长期驻留
2. **TTL 非硬编码**：缓存过期时间必须从配置获取（如 `config_fallback_defaults` 节点），禁止硬编码魔法数字
3. **守卫独立性**：缓存守卫逻辑（写入前校验/TTL 过期清理/失效重取）应独立于业务逻辑，不与 UI 渲染耦合

**子阶段 2.6：UI变更门控检查** 🆕v4.60

前端视觉变更的预确认检查（对应 F-REVIEW-UI-PREVIEW-GATE）：
1. **变更行数统计**：统计本次变更中 icon/theme/color/layout 相关的替换行数
2. **门控阈值判断**：若变更行数 > `ui_preview_gate.changeLineThreshold`，标记为 WARNING 并要求预览确认
3. **豁免检测**：检查 commit message 是否匹配 `ui_preview_gate.exemptPatterns`（如 Bug修复/文案修正），匹配则跳过门控
4. **回滚清单生成**：门控未通过时，自动生成回滚清单（变更文件列表 + 变更前 git hash）

**子阶段 2.7：重构安全性检查** 🆕v4.61

基于复盘规范集 A/B/D 三类前端版本，审查重构过程的安全性（详见 [references/refactoring-safety-checks.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/refactoring-safety-checks.md)）。**为什么独立成节**：常规代码质量检查关注"代码写得对不对"，重构安全性检查关注"改的过程是否安全"——任何重命名、常量抽取、Hook 改造、构建命令变更都伴随着跨文件契约，必须配套同步验证。所有阈值参数在 `config.yaml#refactoring_safety_checks` 节点管理，不硬编码。

**触发条件**：本次变更为重构类操作（重命名 / 常量迁移 / Hook 改造 / 模块拆分 / 构建脚本变更）时自动触发；纯 Bug 修复或新增功能不触发。

按以下 7 项 F-REVIEW 检查点逐项扫描：

1. **常量配置化 5 步法**（对应 F-REVIEW-220 CONSTANT-CONFIG-DRIVEN）：
   - 检查常量重构是否遵循"grep 全量 → 新增常量 → 源文件改造 → 核对引用 → 文档同步"五步闭环
   - 判断信号：改动常量定义但未执行 grep 全量引用扫描 / 常量已迁移但源文件仍保留旧的内联字面量 / 注释仍引用旧常量名
   - 配置节点：`refactoring_safety_checks.constant_config_driven`

2. **React Hooks 作用域契约**（对应 F-REVIEW-221 REACT-HOOKS-SCOPE-CONTRACT）：
   - 检查 Hook 改造是否破坏组件作用域与模块作用域的边界
   - 判断信号：组件 useState/useRef 被改为模块级 `let` 变量 / Hook 被改为普通函数丢失 `use` 前缀 / 模块级常量被组件修改 / 组件 re-mount 后状态未恢复
   - 配置节点：`refactoring_safety_checks.react_hooks_scope_contract`

3. **导入名称变更 checklist**（对应 F-REVIEW-222 IMPORT-NAME-CHANGE-CHECKLIST）：
   - 检查重命名导出符号时是否按调用类型分类核对（Hook 调用保留 `()`、组件调用改为 JSX、函数调用加 `()`）
   - 判断信号：删除导出名前未 grep / Hook 改名为普通函数后调用方未加 `()` / 函数改名为组件后调用方未改为 JSX
   - 配置节点：`refactoring_safety_checks.import_name_change_checklist`

4. **长任务前端构建日志输出**（对应 F-REVIEW-223 LONG-TASK-BUILD-LOG-REDIRECT）：
   - 检查构建脚本是否使用 PowerShell sink cmdlet（如 `| Select-Object -Last N`）导致缓冲
   - 判断信号：脚本含 `| Select-Object` / `| Out-Host -Paging` / `| more` / 长任务未设置超时
   - 配置节点：`refactoring_safety_checks.long_task_build_log_redirect`

5. **系统资源过载容错**（对应 F-REVIEW-224 SYSTEM-RESOURCE-OVERLOAD-TOLERANCE）：
   - 检查全量 tsc 检查是否提供单文件 fallback / 是否监控 Node 进程内存
   - 判断信号：`tsc --noEmit` 超过 `system_resource_overload_tolerance.long_task_threshold_seconds` 仍无输出 / Node 内存超过 `node_memory_threshold_mb` / 无 fallback 策略
   - 配置节点：`refactoring_safety_checks.system_resource_overload_tolerance`

6. **跨文件引用同步校验**（对应 F-REVIEW-225 CROSS-FILE-CONTRACT-SYNC）：
   - 检查修改导出符号后是否运行 `tsc --noEmit` 验证（catch ImportError / NameError）
   - 判断信号：修改导出符号前未 grep / 重构后未运行 tsc / 未检查动态 `import()` 引用 / 修改函数签名但未同步调用方
   - 配置节点：`refactoring_safety_checks.cross_file_contract_sync`

7. **状态持久化统一入口**（对应 F-REVIEW-226 STATE-PERSISTENCE-UNIFIED-ENTRY）：
   - 检查业务参数（轮询间隔 / timeout / 阈值）是否从 config 读取 / localStorage key 是否有命名空间 / 状态读取是否有类型守卫
   - 判断信号：`setInterval(refresh, 10000)` 硬编码 / `localStorage.setItem('columns', ...)` 无命名空间 / `JSON.parse` 无类型守卫
   - 配置节点：`refactoring_safety_checks.state_persistence_unified_entry`

**判断逻辑**：本阶段识别的问题统一归入"重构安全性"分类，CRITICAL 问题（如 F-REVIEW-225 跨文件契约失败）必须阻塞合并。详细判定标准、反模式示例、修复模式见 [references/refactoring-safety-checks.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/refactoring-safety-checks.md)。

### 阶段 3：优先级分类 🆕v4.33

将阶�?2 识别的所有问题按 P0/P1/P2/P3 四级分类，决定修复优先级与是否阻塞合并�?
| 优先�?| 含义 | 阻塞合并 | 示例 |
|--------|------|----------|------|
| **P0 阻塞�?* | 安全漏洞/数据丢失/崩溃/认证绕过 | �?�?| token �?localStorage（F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING）、SSE 无限重连（F-REVIEW-SSE-CONN-MGMT�?|
| **P1 严重** | 逻辑错误/性能问题/数据不一�?| �?否（强烈建议修复�?| useEffect 重置用户状态（F-REVIEW-EFFECT-MINIMIZE）、异步竞态（F-REVIEW-ASYNC-RACE-GUARD）、API 契约不一致（F-REVIEW-API-CONTRACT-CONSISTENCY�?|
| **P2 改进** | 代码质量/可维护�?规范偏离 | �?�?| 主题色硬编码（F-REVIEW-THEME-DYNAMIC-ADAPT）、统计范围过大（F-REVIEW-STATS-RANGE-CALIBRATE）、错误消息无透传（F-REVIEW-ERROR-MESSAGE-PASS�?|
| **P3 微调** | 风格/注释/命名 | �?�?| 按钮与状态语义混用（F-REVIEW-UI-SEMANTICS-SPLIT）、组件注册集中性（F-REVIEW-COMPONENT-REGISTRY�?|

**判断逻辑**�?- P0 问题必须修复后才能合并，报告中标�?阻止合并"
- P1 问题强烈建议在本次迭代修复，报告中突出显�?- P2/P3 问题记录�?backlog，可在后续迭代修�?- 优先级映射到原有 severity：P0=CRITICAL、P1=HIGH、P2=MEDIUM、P3=LOW

### 阶段 4：结果呈�?
�?`report.format` 生成结构化报告（Markdown），严格遵循**输出模板**（见 `templates/report-template.md` 与下�?结构化报告模�?）�?
**报告结构**�?1. **审查概览**（审查范�?审查维度/问题统计 P0/P1/P2/P3/规范版本�?2. **问题详情**（按 P0→P3 优先级排序，每个问题含编�?维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示例）
3. **与上次审查对�?*（🆕新�?/ ✅已修复 / ⚠️仍存在）
4. **硬约束合规性检查结�?*
5. **好的实践**（正面反馈）
6. **测试运行结果**（若 `verify.run_tests_after_review=true`�?7. **审查结论与修复验证指�?*

**结构化报告模�?*（v4.33 新增，每个问题按以下格式呈现）：

```markdown
#### [P0] F-REVIEW-96 useEffect 副作用最小化
- **规范引用**: EFFECT-01 useEffect 副作用最小化原则
- **维度**: §3 React 组件规范
- **代码位置**: MainLayout.tsx:358-362
- **问题描述**: useEffect 联动重置 openKeys，触�?SubMenu 动画遮挡
- **修复建议**: 完全移除 useEffect，openKeys �?useState 初始�?+ 用户交互控制
- **配置节点**: coding_standards.effect.disallow_reset_user_controlled_state
- **反模式示�?*: useEffect(() => setOpenKeys(autoOpenKeys), [location.pathname])
```

**结果呈现优化** 🆕v4.60：

1. **按风险等级分组**：问题详情按风险等级分组呈现，优先级排序为：
   - CRITICAL（安全/数据丢失）> WARNING（缓存/状态）> INFO（风格/优化）
   - 每个风险等级对应不同的视觉标识：🔴 CRITICAL / 🟡 WARNING / 🔵 INFO

2. **防回归标记**：每个修复点标记对应的测试模式（xianyu-auto-testing 模式），确保修复可被自动测试覆盖：
   ```markdown
   - **防回归标记**: auto-testing 模式 V（UI一致性回归）/ 模式 W（状态持久化回归）/ 模式 X（渲染健壮性回归）
   ```

3. **跨层影响图**：显示变更的跨层传播路径，帮助审查者理解修改的完整影响范围：
   ```markdown
   ### 跨层影响图
   ```
   types.ts:Item.price_range ──→ Pydantic:ItemResponse.price_range ──→ DB:items.price_range
   types.ts:Item.market_ratio ──→ Pydantic:ItemResponse.market_ratio ──→ DB:items.market_ratio
   ```
   影响路径数：2  最大深度：3  涉及DB列：2
   ```

---

## 评审范围判断

- **待提交变更模�?*：`git diff HEAD --name-only` + 过滤 `.tsx/.ts/.js` 文件
- **指定文件模式**：用户明确列出文件路�?- **片段模式**：用户粘贴代码但无文件路径（仅输出建议，不输�?File:Line�?- **范围必须收紧**：不顺便审查旁边代码，不主动扩展到未提及的文�?
## 误报识别判断

- 路径匹配 `scope.exclude_paths`：跳�?- 测试文件中的规范类问题：降级处理
- 生成代码（含 `// @generated` 注释�?`__generated__` 路径）：跳过
- 第三方库代码（`node_modules`）：跳过
- 类型定义文件（`.d.ts`）中的规范类问题：降级处�?
## 修复建议判断

- 必须提供可操作的修复建议（含代码示例�?- 建议必须解释"为什�?而非�?做什�?
- 优先建议抽取纯函数、共享常量、共享组�?- 若问题需要代码修改，在报告末尾询问用户是否应用修�?
## 抽象建议判断（闲鱼项目特色）

- 重复的内联样式（`abstraction_thresholds.inline_style_repeat` 默认 3 处）：建议抽取共享组件或样式常量
- 重复的文案（`abstraction_thresholds.text_literal_repeat` 默认 2 处）：建议抽取共享文案常�?- 复杂的优先级/判定逻辑：建议抽取为纯函数并配套单元测试
- 跨组件共享的状态逻辑：建议抽取为自定�?Hook
- 函数行数超过 `function_max_lines`（默�?50）：建议拆分
- 组件行数超过 `component_max_lines`（默�?300）：建议拆分
- 嵌套深度超过 `max_nesting_depth`（默�?4）：建议重构（SonarQube S2004�?
## 失败恢复机制

1. **文件读取失败**：记录跳过原因，继续评审其他文件
2. **Grep 超时**：缩小搜索范围或跳过该检查项
3. **测试运行失败**：输出测试失败信息，不阻止报告生�?4. **配置文件缺失**：使用内置默认配置并提示用户创建 `config.yaml`
5. **TypeScript 编译错误**：记录但继续评审，不阻止报告生成

---

## 审查判断标准

| 🟠阻塞(必须修复) | 🟠严重(强烈建议) | 🟡警告(建议) |
|-----------------|-----------------|-------------|
| `fetch` 请求未包�?`credentials: 'include'` | 未复用组�?| 缩进不规�?|
| axios 未设 `withCredentials: true` | UI 不一�?| 变量命名不规�?|
| token 写入 `localStorage` | 缺注�?| 冗余代码 |
| 使用 `dangerouslySetInnerHTML` | 验证规则不完�?| 注释不清�?|
| 使用 `any` 类型 | 错误处理不完�?| 缺少类型注解 |
| �?`.catch()` �?| 空指针风险（链式调用未判空） | 缺少测试 |
| `v-for`/`map` 使用 index 作为 key | `useEffect` 依赖数组不完�?| 缺少文档字符�?|
| `ConfigProvider` �?`BrowserRouter` 内层 | `useMemo`/`useCallback` 缺失 | 嵌套层级过深 |
| 三处映射不同步（路由/菜单/sheetRegistry�?| `requestId` 竞态保护缺�?| 注释复述代码 |
| `enum` 替代字符串字面量联合 | `mountedRef` 缺失（卸载后 setState�?| 魔法数字未提�?|
| `JSON.parse(JSON.stringify())` 深拷�?| `refreshingRef` 并发保护缺失 | 魔法字符�?|
| 使用 `interface`（应�?`type`�?| `lazyRetry` 未包�?| 函数过长 |
| `main.tsx` 入口配置错误 | `SSE_LAST_EVENT_ID_KEY` 缺失 | 缺少 `__all__` |
| 函数嵌套 > 4 层（S2004�?| PWA `runtimeCaching` 未排�?`/api/events/stream` | - |
| 认知复杂�?> 15（S3776�?| 路由切换未重置滚动位�?| - |
| `vite.config.ts` `base` 错误 | `partialize` 未过�?ReactNode | - |
| 构建产物未输出到 `web/static/spa` | store 感知路由库（未用 `_navigator` 注入�?| - |
| 使用箭头函数定义组件 | `useEffect` 依赖数组缺失导致 stale closure | - |
| 嵌入页面�?`minHeight: 100vh`（应 `height: 100%`�?| `activateSheet` 未同步恢�?`minimized` | - |
| 交互元素文字�?`colorBorder`（应 `colorPrimary`�?| antd 组件测试�?mock `matchMedia` | - |
| 状态变更操作未同步更新所有相关字�?| vitest 命令缺少 `--no-isolate` | - |
| 🆕 `<div onClick>`/`<a onClick>` �?href（S6819/S6844�?| 🆕 `useEffect` 依赖缺失导致 stale closure（S7735�?| - |
| 🆕 �?`await` �?`async` 函数（S7503�?| 🆕 冗余可选链 `a?.b` �?a 已非空（S6582�?| - |
| 🆕 未使用的 Props/State/参数（S6767�?| 🆕 重复内联样式 `abstraction_thresholds.inline_style_repeat` 次以�?| - |
| 🆕v4.0 Tab 切换数据丢失（state 未提升） | 🆕v4.0 JSX �?IIFE 未提取为变量 | - |
| 🆕v4.0 外部链接�?`rel="noopener noreferrer"` | 🆕v4.0 图标文字间距依赖 JSX 空格 | - |
| 🆕v4.0 注释与代码逻辑不一致（误导性约束说明） | 🆕v4.0 动态资源映射表与推断函数混�?| - |
| 🆕v4.1 SSE 流消费回调未处理 `stage='error'` 分支 | 🆕v4.1 SSE 错误事件未按 `status` 分类�?01/403 应显�?前往登录"按钮�?| - |
| 🆕v4.1 SSE 错误事件�?真的没货"（`stage='done'`+0 结果）混为一�?| - | - |
| 🆕v4.2 受控 UI 状态（`openKeys`/`expandedKeys`）通过 `useEffect` 联动路由变化（产生非用户触发的展开/折叠动画�?| - | - |
| 🆕v4.3 Proxy/Observer 赋值给局部变量后丢弃（死代码�?| 🆕v4.3 跨组件对同一概念判断维度未同�?| - |
| 🆕v4.3 try/finally 变量未初始化�?null/undefined | 🆕v4.3 错误提示引用不存在的路由/端点 | - |
| 🆕v4.4 高风险前端功能默认启用（应默认关�?配置驱动）（F-REVIEW-CONFIG-DRIVEN-TOGGLE�?| 🆕v4.4 功能参数硬编码在组件内（应集中在 `constants.ts` �?`FEATURE_TOGGLES`/`FEATURE_CONFIGS` 节点管理�?| - |
| 🆕v4.5 错误提示文案与后端错误根因语义不匹配（如 token 过期显示"登录已过�?）（F-REVIEW-ERROR-SEMANTICS�?| 🆕v4.5 前端配置项未传递给后端 API（配置无效化）（F-REVIEW-CONFIG-LINKAGE�?| - |
| 🆕v4.9 累计统计�?API（频率伪装统�?/ 健康评分 / 计数器）仅在 useEffect 初始化时拉一次，缺少 setInterval 定时刷新（F-REVIEW-FREQ-STATS-POLLING�?| 🆕v4.9 setInterval 间隔数字�?0000/30000）硬编码在组件内（应来自 `config.yaml` �?`freq_stats_polling.interval_ms` �?`POLL_INTERVALS` 常量�?| - |
| 🆕v4.10 后端返回 `filter_summary` 但前端只显示"查询完成"不暴露过滤过程（F-REVIEW-FILTER-VISIBILITY�?| 🆕v4.10 API 返回类型�?`as { filter_summary?: ... }` 强制转换绕过 TS 检查（应显式声�?`filter_summary?` 字段�?| - |
| 🆕v4.11 前后端状态枚举值不对齐（前�?`types.ts` 联合类型与后�?`Enum` 不一致）（F-REVIEW-STATE-ENUM-ALIGN�?| 🆕v4.11 前端硬编码状态字符串（`status === 'running'`）而非引用 `types.ts` 联合类型 | - |
| 🆕v4.11 终态（`completed`/`failed`）仍显示 loading 动画�?进行�?文案（F-REVIEW-STATE-MACHINE-UI�?| 🆕v4.11 中间态（`pending`/`running`）缺�?loading 反馈 / 操作按钮与后端状态机白名单不一�?| - |
| 🆕v4.11 多链路触发同一状态变更时各链路独�?`setState` 推断新状态（F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY�?| 🆕v4.11 SSE 推送状态变更后只更新当前组�?`setState` 未刷新全局缓存 / `refetch()` 失败清空缓存 | - |
---

## 与现有工具的关系

- **xianyu-hunter-dev**：开发技能，本技能与之配合（开发完成后用本技能审查）
- **frontend-code-review**（全局技能）：本技能参考其检查清单精神，但增加了闲鱼项目专属的硬约束�?19 维度检查清�?- **xianyu-backend-code-review**：前后端协同评审时配合使�?- **xianyu-sonarqube-mcp**：SonarQube 修复后的二次人工评审使用本技�?- **frontend-design**：UI 设计与样式调整使用该技能，不使用本技�?- **systematic-debugging**：纯调试场景使用该技能，不使用本技�?- **skill-creator**：本技能由 skill-creator 创建

---

## 安全注意事项

1. **凭据**：报告中不包含任�?token、密码等敏感信息
2. **XSS 风险**：检�?`dangerouslySetInnerHTML` 的使�?3. **敏感信息存储**：检�?token 是否避免写入 localStorage（优�?httpOnly cookie�?4. **认证一致�?*：检查所�?API 请求是否携带 credentials

---

## 示例用法

### 场景1：迭代发布前评审

用户�?对这次迭代的前端修改进行代码评审"

技能执行：
1. 读取 `config.yaml`
2. `git diff HEAD --name-only` 提取改动�?`.tsx/.ts/.js` 文件
3. 逐文件读取并�?23 大类检�?4. 硬约束合规性扫�?5. 生成评审报告

### 场景2：指定组件评�?
用户�?评审 frontend/src/pages/Evaluations/index.tsx"

技能执行：
1. 读取 `config.yaml`
2. 读取指定文件
3. 收集上下文（类型定义、测试文件、API 契约�?4. 按检查清单评�?5. 生成评审报告

### 场景3：仅评审类型安全和业务逻辑

用户修改 `config.yaml`�?```yaml
checklist:
  directory_structure: false
  naming: false
  react_component: false
  typescript_strict: false
  antd_theme: false
  zustand: false
  api_call: false
  routing_lazy: false
  sheet_workspace: false
  hooks_design: false
  type_safety: true
  sonarqube: false
  pwa: false
  three_mappings: false
  sse_reconnect: false
  business_logic: true
  performance: false
  accessibility: false
  testability: true
  auth: false
  project_specific: false
```

技能执行：只检查类型安全、业务逻辑和可测试性�?
### 场景4：评审新增的纯函数抽�?
用户�?评审我新抽取�?`resolveActionDisplay` 函数"

技能执行：
1. 读取函数定义文件（`utils.ts`�?2. 读取对应测试文件（`__tests__/resolveActionDisplay.test.ts`�?3. 重点检查：
   - 类型安全（返回值联合类型、参数类型）
   - 业务逻辑（优先级顺序、边界场景）
   - 可测试性（纯函数、测试覆盖度�?   - 注释质量（是否解�?为什�?�?4. 生成评审报告

---

## 结构化报告模�?🆕v4.33

> v4.33 新增结构化报告模板，强化"审查概览 + 问题详情"两段式呈现，每个问题含编�?维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示�?8 要素。与下方 Template A/B 并存，按 `report.format` 选择�?
### 完整报告结构

```markdown
# 代码审查报告

## 审查概览
- **审查范围**: [文件列表，如 MainLayout.tsx / SheetWorkspace.tsx / api/types.ts]
- **审查维度**: [命中的维度列表，�?§3 React 组件规范 / §10 Hooks 设计模式 / §15 SSE 重连]
- **问题统计**: P0=[n] P1=[n] P2=[n] P3=[n]（总计 [n] 项）
- **规范版本**: xianyu-frontend-code-review v4.33.0
- **配置版本**: config.yaml（含 coding_standards 节点�?- **审查日期**: [YYYY-MM-DD]

## 问题详情

### 🔴 P0 阻塞性问题（必须修复后才能合并）

#### [P0] F-REVIEW-SSE-CONN-MGMT SSE 连接管理三要�?- **规范引用**: SSE-01 SSE 连接管理三要�?- **维度**: §15 SSE 重连
- **代码位置**: EventSourceProvider.tsx:45-62
- **问题描述**: SSE 连接无限重连，无最大重试限制，�?visibilitychange 监听，页面切回后事件丢失
- **修复建议**: 增加 MAX_RECONNECT=10 限制 + visibilitychange 监听 + last_event_id 回放 + 降级轮询
- **配置节点**: coding_standards.sse.max_reconnect_attempts / coding_standards.sse.visibility_reconnect
- **反模式示�?*:
  ```typescript
  es.addEventListener('error', () => {
    setTimeout(connect, 3000)  // 无限重连，无降级
  })
  ```

#### [P0] F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING 认证 token cookie 处理
- **规范引用**: AUTH-COOKIE-01（与 v4.32 F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING 配合�?- **维度**: §28 多用户认证上下文隔离
- **代码位置**: api/auth.ts:23
- **问题描述**: token 存入 localStorage，XSS 可读�?- **修复建议**: 改为 httpOnly cookie 由后端写入，fetch 显式 credentials: 'include'
- **配置节点**: auth_token_cookie_handling.forbidden_token_storage
- **反模式示�?*: `localStorage.setItem('xh_token', token)`

### 🟠 P1 严重问题（强烈建议本次迭代修复）

#### [P1] F-REVIEW-EFFECT-MINIMIZE useEffect 副作用最小化
- **规范引用**: EFFECT-01 useEffect 副作用最小化原则
- **维度**: §3 React 组件规范
- **代码位置**: MainLayout.tsx:358-362
- **问题描述**: useEffect 联动重置 openKeys，触�?SubMenu 动画遮挡
- **修复建议**: 完全移除 useEffect，openKeys �?useState 初始�?+ 用户交互控制
- **配置节点**: coding_standards.effect.disallow_reset_user_controlled_state
- **反模式示�?*: `useEffect(() => setOpenKeys(autoOpenKeys), [location.pathname])`

#### [P1] F-REVIEW-API-CONTRACT-CONSISTENCY API 契约一致�?- **规范引用**: CONTRACT-01 API 契约一致性（前端�?- **维度**: §11 类型安全评审
- **代码位置**: api/types.ts:128
- **问题描述**: 后端返回 total，前�?TS interface 期望 total_for_type，导致显�?0 �?- **修复建议**: TS interface 字段名与后端 response_model 完全一致（snake_case 对齐�?- **配置节点**: coding_standards.contract.check_ts_interface_match
- **反模式示�?*: `interface EvaluationResult { total_for_type: number }`

### 🟡 P2 改进问题（记录到 backlog，后续迭代修复）

#### [P2] F-REVIEW-THEME-DYNAMIC-ADAPT 主题色动态适配
- **规范引用**: THEME-01 主题色动态适配
- **维度**: §5 AntD 5 主题规范
- **代码位置**: theme.ts:34
- **问题描述**: 硬编�?rowHoverBg: '#fff7f0'，暗色模式不可读
- **修复建议**: 改为 isDark ? 'rgba(255,98,0,0.08)' : '#fff7f0'
- **配置节点**: coding_standards.theme.disallow_hardcoded_colors / coding_standards.theme.colors.light/dark
- **反模式示�?*: `rowHoverBg: '#fff7f0'`

### 🟢 P3 微调问题（风�?注释/命名�?
#### [P3] F-REVIEW-UI-SEMANTICS-SPLIT 按钮与状态语义分�?- **规范引用**: UI-SEMANTICS-01 按钮与状态语义分�?- **维度**: §3 React 组件规范
- **代码位置**: CookieList.tsx:156
- **问题描述**: 红色"失效"是按钮而非状态显示，用户误判
- **修复建议**: 按钮文案改为"主动失效"，状态用 Tag 显示"已失�?
- **配置节点**: coding_standards.ui_semantics.button_text_must_be_action
- **反模式示�?*: `<Button danger>失效</Button>`

### ⚙️ Config Node Missing（v4.31+ 独立分类�?
> Phase 2「配置驱动检查」识别的 3 类问题：业务关键字硬编码 / 事件类型前缀匹配 / 字段名大小写不一致。severity 默认 CRITICAL，可�?`config.yaml` �?`enabled` 字段开关�?*必须独立呈现**，不�?Critical/Suggestions/Nits 混合，便于用户快速定�?配置契约"类问题�?
#### [CRITICAL] F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION 业务关键字未集中管理
- **代码位置**: xxx.tsx:NN
- **问题描述**: [违反�?F-REVIEW 规则 + 缺失�?config 节点 + 前后端契约缺口]
- **修复建议**: [新增 config 节点 + 同步前端类型 + grep 双向验证]
- **配置节点**: business_keyword_centralization

## 与上次审查对�?- 🆕 新增: [n] �?- �?已修�? [n] �?- ⚠️ 仍存�? [n] �?
## 硬约束合规性检查结�?- 检查规则数: [n]
- 违规�? [n]
- 是否阻止合并: [�?否]

## 好的实践（正面反馈）
1. [正面反馈 1]
2. [正面反馈 2]

## 审查结论与修复验证指�?- **结论**: [通过 / 有条件通过 / 阻止合并]
- **修复优先�?*: P0 修复后重新审查，P1 建议本次迭代修复
- **验证方式**: 修复后运�?`npm --prefix frontend test ; npm --prefix frontend run typecheck`
```

**输出规则**�?- 若某分类无问题，省略该分类的整个 section
- 若问题数超过 10 个，概括�?"Found 10+ critical issues/suggestions/optional nits" 并仅输出�?10 �?- 不要压缩 section 之间的空行，保持可读�?- 「Config Node Missing」分类必须独立呈现，不与 Critical/Suggestions/Nits 混合
- 若有任何问题需要代码修改，在结构化输出后追加简短询问，例如�?是否需要我使用 Suggested Fix 来修复这些问题？"
- 无问题时输出简短结论：`## Code Review Summary\n�?No issues found.`

> 完整报告模板（含基本信息、severity/category 分布、四维度复盘、跨边界访问契约、配置变更点等扩展段落）�?[templates/report-template.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/templates/report-template.md)�?
---

## 重要提醒

1. 【强制】所�?`fetch`/axios 请求必须包含 `credentials: 'include'` / `withCredentials: true`
2. 【强制】`ConfigProvider` 必须�?`BrowserRouter` 外层，响�?`useTheme`
3. 【强制】新增页面必须同步三处映射（路由、菜单、sheetRegistry�?4. 【强制】禁�?`any` 类型、`dangerouslySetInnerHTML`、`enum`、`JSON.parse(JSON.stringify())`
5. 【强制】SSE 请求�?`fetch + ReadableStream`，lastEventId 持久化重�?6. 【强制】提交前执行 `auto-scan.ps1`；完成后调用本技能走�?
---

## 快速问题定�?
> 现象导向的问题定位对照表（现�?�?原因 �?方案�?0+ 项）已外部化�?[references/quick-troubleshooting.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/quick-troubleshooting.md)。当用户报告具体现象时，先查该表快速定位原因，再回到对应维度章节查阅详细规则�?

> 本次走查沉淀的端到端案例（跨端失败诊断一致性、移动端 `usage` 初始为 null 的优雅降级、状态语义对齐）见 [references/xianyu-walkthrough-cases.md](references/xianyu-walkthrough-cases.md)，作为「快速问题定位」的补充实证。
> 本次走查与评审技能建设的完整复盘（四维度：成功步骤 / 不确定性与失败点 / 抽象流程 / 适用场景）见 [references/review-process-retrospective.md](file:///d:/code/otherProjects/17_xianyu/.workbuddy/skills/xianyu-backend-code-review/references/review-process-retrospective.md)。
---

## 附录A：硬约束来源

本技能的硬约束规则来源于�?- `c:\Users\hspcadmin\.trae-cn\memory\projects\-d-code-otherProjects-17-xianyu\project_memory.md`
- `.trae/skills/xianyu-hunter-dev/references/project-rules.md`
- `.trae/skills/xianyu-hunter-dev/assets/guides/frontend-guide.md`
- `.trae/skills/xianyu-frontend-code-review/references/encoding-and-io.md` —�?字符编码�?I/O 边界审查要点（FAQ 乱码复盘提炼，ENC-01 ~ ENC-08�?- `.trae/skills/xianyu-frontend-code-review/references/state-and-consistency-checks.md` —�?前端硬编码阈值禁用、状态判断后端一致性、类型对齐、API 字段映射、credentials 传递、错误反馈与重试、事件冒泡控制（代码审查 P1 + 实时搜索复盘提炼�?0 �?F-REVIEW 检查点�?- 历史代码评审记录

## 附录B：项目专属规�?
以下规范�?`config.yaml` �?`project_conventions` 节点维护�?
| 规范 | 说明 |
|------|------|
| `ui_library` | UI 组件库（Ant Design�?|
| `visual_style` | 视觉风格偏好 |
| `auth_requirements` | 认证要求 |
| `test_framework` | 测试框架 |
| `types_location` | 类型定义位置 |
| `abstraction_patterns` | 推荐的抽象模�?|
| `routing` | 路由配置 |
| `pwa` | PWA 配置 |
| `sonarqube_rules` | SonarQube 8 条规�?|

## 附录C�?38 维度对照�?
| # | 维度 | 核心规则 |
|:--|:---|:---|
| 1 | 目录结构 | `frontend/src/<分类>/` 规范路径 |
| 2 | 命名规范 | PascalCase/camelCase/use<X>/<�?Store |
| 3 | React 组件规范 | function 关键�?+ type Props + 双层 ErrorBoundary + 🆕v4.2 F-REVIEW-UI-STATE-INDEPENDENCE（受�?UI 状态不联动路由�?|
| 4 | TypeScript 严格规范 | strict:true、type 优先、字符串字面量联合、🆕v4.25 F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY（默认值统一�??? 而非 \|\|�?|
| 5 | AntD 5 主题 | ConfigProvider �?BrowserRouter 外层、品牌橙 |
| 6 | Zustand 状态管�?| persist + partialize、store 不感知路�?|
| 7 | API 调用规范 | axios + withCredentials、SSE �?fetch、🆕v4.25 F-REVIEW-THREE-STATE-NULL-SEMANTICS（PATCH/PUT 清除覆盖必须显式�?null�?|
| 8 | 路由与懒加载 | lazyRetry、双�?ErrorBoundary |
| 9 | SheetWorkspace 多页�?| 6 文件组织、四分支决策 |
| 10 | Hooks 设计模式 | 常量模块级、ref 持有最新闭包、requestId 竞态保护、🆕v4.24 F-REVIEW-UI-PREFERENCE-PERSISTENCE（用户偏好类 UI 状态强制复�?usePersistentState�?|
| 11 | 类型安全 | 前后端字段对齐、可选链、联合类型、🆕v4.4 配置驱动功能开关（F-REVIEW-CONFIG-DRIVEN-TOGGLE�?|
| 12 | SonarQube 合规 | 8 条规则：S2004/S3358/S6757/S7784/S6848/S1128/S4325/S3776 |
| 13 | PWA 配置 | base:'/xianyu/'、runtimeCaching 排除规则（含 /xianyu/api）、构建依赖与缓存完整性（workbox peer deps / emptyOutDir / optimizeDeps.force） |
| 14 | 三处映射同步 | App.tsx + MainLayout.tsx + sheetRegistry.tsx |
| 15 | SSE 重连 | lastEventId 持久化重连、🆕v4.1 F-REVIEW-SSE-ERROR-HANDLING（stage='error' �?status 分类处理 + "前往登录"跳转引导�?|
| 16 | 性能 | useMemo/useCallback、虚拟化、稳�?key |
| 17 | 可访问�?| aria-label、label 关联、键盘导�?|
| 18 | 闲鱼项目规范 | AntD 5.21、Vitest 4.1、纯函数+组件+常量分层 |
| 19 | 跨组件状态同步与死代码检�?| Proxy/Observer 赋值实例属性、try/finally 变量初始化、跨组件状态双向同步、错误提示路由可操作�?|
| 20 | 错误提示语义 + 配置链路（前端侧�?| 🆕v4.5 错误文案与根因匹配、前端配置全链路追踪、🆕v4.25 F-REVIEW-ERROR-HANDLING-CONSISTENCY（catch 块必须用 extractApiError�?|
| 21 | 异步反馈 + 数据流转 + 过滤场景 + 复用模式（前端侧�?| 🆕v4.7 异步操作三态反馈（loading→success→error）、字段为�?5 点追踪（前端 types+render）、过滤场景标志显式传递（include_failed）、复用既有前端模式（message.loading/lazyRetry/structuredClone�?|
| 22 | 累计统计�?API 定时刷新（前端侧�?| 🆕v4.9 累计统计�?API（频率伪装统�?/ 健康评分 / 计数器）必须在前�?useEffect 中通过 setInterval 定时刷新，禁止只依赖"页面加载时拉一�?；间隔、清理策略、失败兜底均�?`config.yaml` �?`freq_stats_polling` 节点管理，不硬编码（与后�?v4.8.0 `B-REVIEW-ISLAND-MODULE` 配合�?|
| 23 | 前后端错误码契约与超时识�?+ 前端可重试错误集与退避策�?| 🆕v4.13 模块�?`statusMessages` map + `isAxiosTimeout()` 函数（axios 超时�?`response.status` �?`error.code === 'ECONNABORTED'` �?`/timeout/i.test(error.message)` 识别）；可重试错误集�?10/441/502/超时）按 `retry_delays_ms` 退避序列重试，重试过程 `silent_on_retry`；非幂等写入接口禁用自动重试；参数在 `frontend_error_contract` + `frontend_retry_strategy` 节点管理（与后端 v4.12 `B-REVIEW-DOM-FALLBACK-CHAIN` / `B-REVIEW-TIMING-INSTRUMENTATION` / `B-REVIEW-PRECHECK-AND-PARALLEL` 联动�?|
| 24 | 模型能力元数据集中展示与降级状态可视化 | 🆕v4.23 前端展示 LLM 模型能力时必须集中展示（�?`/api/config` �?`/api/about` 统一获取，禁止每页独�?fetch/内联判断），用户上传图片/启用 tool 时前端必须根据能力位给出降级状态可视化（如 `Tag color="warning"` 显示"纯文本模型不支持图片分析，已降级为文字描�?），关键字列表仅在后�?`api_ai._VISION_CAPABLE_KEYWORDS` 一处维护，前端�?`isVisionCapable()` + `getCapabilityDisplay()` 共享函数�?`frontend/src/utils/modelCapability.ts`；参数在 `model_capability_centralization` 节点管理 |
| 25 | 端到端失败原因链前端侧同步原�?| 🆕v4.27 前端在端到端失败原因链中�?3 项同步原则：F-REVIEW-ERROR-CODE-BRANCH（错误展示按 `error_code` 字段分支，禁止按文案子串判断，与后端 `failure_reason_propagation.reason_enum` 一一对应）、F-REVIEW-PRECHECK-API-DELEGATION（数据完整性预检委托后端，禁止前端自行实现预检业务规则，调用后端预检端点 `/api/<resource>/precheck` 获取 `passed` 字段）、F-REVIEW-MOCK-FIELD-SET-SYNC（前�?mock 数据必须覆盖完整字段集与后端 Pydantic 模型一致，禁止�?`as` 类型断言绕过，集中管�?mock 基线文件 `frontend/src/test/mocks/`）；参数�?`failure_reason_chain_frontend` 节点管理（与后端 v4.27.0 维度 29 �?6 �?B-REVIEW 联动�?|
| 26 | 跨边界访问契约前端侧 | 🆕v4.30 后端跨边界契约不明确在前端的对应场景：F-REVIEW-DATETIME-RENDER-CONTRACT（后�?datetime 字段 must use `new Date(isoStr)` 显式解析，naive ISO 字符串追�?`Z` 后缀，禁止字符串方法解析）、F-REVIEW-PRIVATE-HOOK-ENCAPSULATION（跨组件访问私有 hooks/state 必须通过公共 API，禁�?`useXxxStore(s => s._xxx)` 直接访问私有字段，用 `useImperativeHandle` 显式声明可暴露方法）、F-REVIEW-NAMING-CONSISTENCY-FRONTEND（命名一致性验证：变量 camelCase / 组件 PascalCase / 常量 UPPER_SNAKE_CASE / 私有 _ 前缀，跨组件引用必须大小写匹配）；参数在 `cross_boundary_contract_frontend` 节点管理 |
| 27 | 业务关键字常量集中管理与字段名大小写敏感 | 🆕v4.31 前端业务关键字与字段契约层面�?3 项同步原则：F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION（前端业务关键字常量必须从后端配置端�?`/api/config/text_features` 拉取，禁止前端硬编码中文字面量，通过共享 helper `isItemSoldByText()` 调用后端配置）、F-REVIEW-EVENT-TYPE-EXACT-MATCH（前端按事件类型过滤必须 `===` 精确匹配�?`Set.has()`，禁�?`startsWith()`/`indexOf()` 前缀匹配，通知事件与业务事件分离处理）、F-REVIEW-FIELD-NAME-CASE-SENSITIVE（前端访问后端字段时大小写敏感，前端 `api/types.ts` 必须与后�?Pydantic 模型字段名一一对应，禁止用 `as any` 绕过类型检查）�? 项检查点对应 `xianyu-hunter-dev` step 129/130/131；参数在 `business_keyword_centralization` / `event_type_exact_match` / `field_name_case_sensitive` 节点管理（与后端 v4.31.0 维度 30 �?6 �?B-REVIEW 联动�?|
| 28 | 多用户认证上下文隔离 | 🆕v4.32 多用户场景前端隔离原则：F-REVIEW-MULTI-USER-CONTEXT-ISOLATION（前端按 `user_id` 隔离 Zustand store / 缓存 / 请求路径，禁止全局单例承接多用户数据；切换用户时必�?`queryClient.clear()` + `useGlobalStore.getState().reset()` 后再加载新用户数据）、F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING（认�?token 通过 httpOnly cookie 传递，fetch 必须 `credentials: 'include'` / axios 必须 `withCredentials: true`�?01/440/441/403 状态码语义精细化分支）；参数在 `multi_user_context_isolation` / `auth_token_cookie_handling` 节点管理（与 xianyu-hunter-dev step 134-137 + 后端 v4.32 维度 28 联动�?|
| 29 | 数据契约与时序（meta-rules #25-30 落地�?| 🆕v4.34 前端在数据契约与时序维度�?6 项落地检查点：F-REVIEW-110（批量断路器 UI 三态反馈，区分用户主动停止/熔断可恢�?异常失败，必须展�?success_count/pending_count/failure_reason/recover_action）、F-REVIEW-111（ErrorBoundary 完整 stack 上报，禁 console.error_only/return_null）、F-REVIEW-112（ISO datetime 统一解析与序列化，解析用 new Date().toLocaleString，发送用 toISOString）、F-REVIEW-113（跨进程状态同步六步法前端侧，�?setInterval 替代 SSE）、F-REVIEW-114（前端错误按 error_code 分支，禁 substring 判断）、F-REVIEW-115（业务关键字常量集中管理，禁内联字符串，�?@/constants/businessKeywords 导入，与后端一致性测试）�? 项检查点对应 xianyu-hunter-dev v4.30.0 meta-rules #25-30 + 后端 v4.29.0 维度 31 �?B-REVIEW-151~156；参数在 `data_contract_temporal` 节点管理 |
| 30 | 状态恢复前置校验前端侧（meta-rule #31 落地�?| 🆕v4.35 前端在状态恢复前置校验维度的 1 项落地检查点：F-REVIEW-116 RESUME-PRECHECK-FRONTEND（恢�?启动/继续按钮 onClick 必须先调用后�?precheck API 校验前置条件，禁前端自行实现预检；校验失败时展示 user_hint + retry_after 倒计�?+ 恢复动作按钮；与后端 B-REVIEW-157 配套）；1 项检查点对应 xianyu-hunter-dev v4.31.0 meta-rule #31 + 后端 v4.30.0 B-REVIEW-157；参数在 `resume_policy_precheck` 节点管理 |
| 31 | 注册式资源三件套契约前端侧（meta-rule #33 落地�?| 🆕v4.36 前端在注册式资源三件套契约维度的 1 项落地检查点：F-REVIEW-117 REGISTRATION-COMPLETENESS（菜�?路由/页面/API 模块/后端端点 5 层契约，任一层缺�?CRITICAL；自动化校验 `python scripts/check_registration.py` 退出码 0 才算通过）；1 项检查点对应 xianyu-hunter-dev v4.32.0 meta-rule #33 + 后端 B-REVIEW-159；参数在 `frontend_registration_completeness` 节点管理 |
| 32 | 修复前根因扫描协议前端侧（meta-rule #34 落地�?| 🆕v4.36 前端在修复前根因扫描协议维度�?1 项落地检查点：F-REVIEW-118 ROOT-CAUSE-MIN-COUNT（修复非平凡 bug 前必须先�?�? 个根因覆盖用户层/接口�?数据�?配置�?历史层；PR 描述必含"�? 根因列表"段；git diff 涉及 �? 个无关文件视为违反最小修改原则）�? 项检查点对应 xianyu-hunter-dev v4.32.0 meta-rule #34 + 后端 B-REVIEW-160；参数在 `root_cause_protocol` 节点管理 |
| 33 | 前后端字段契约单一可信源前端侧（meta-rule #35 落地�?| 🆕v4.36 前端在前后端字段契约单一可信源维度的 1 项落地检查点：F-REVIEW-119 CONTRACT-SINGLE-SOURCE（后�?Pydantic/DB Row 字段=权威源，前端 types.ts 必须显式标注"派生来源+Pydantic 字段+变更日期+约束"4 段注释；snake_case 严格透传禁止�?camelCase；命名漂�?CRITICAL）；1 项检查点对应 xianyu-hunter-dev v4.32.0 meta-rule #35 + 后端 B-REVIEW-161；参数在 `contract_single_source` 节点管理 |
| 34 | 规范治理（meta-rules #36-37 落地�?| 🆕v4.37 前端在规范治理维度的 2 项落地检查点：F-REVIEW-120 SEDIMENTATION-THRESHOLD（新立编码规范必须满�?�? 个相�?bug 门槛，单一 bug 立规范需�?experimental 标签 + 1 季度观察期，安全/数据丢失/付费受损豁免）、F-REVIEW-121 DEGRADATION-CLEANUP（利用率 < 3 �?季度�?F-REVIEW 必须标记待合�?待废弃，1 季度观察期后废弃并移�?version-history.md Deprecated 章节，安全类永不退化）�? 项检查点对应 xianyu-hunter-dev v4.33.0 meta-rules #36-37 + 后端 B-REVIEW-162/163；参数在 `meta_rules_governance` 节点管理 |
| 42 | 源码受保护（清理禁删 tracked 源）| 🆕v4.71 meta-rule #116 落地：清理脚本 git status 守卫 + 白名单只含 build/node_modules/.cache/__pycache__，禁匹配 src//*.css/*.ts(x)/*.py；参数在 `source_file_protection` 节点管理 |
| 43 | PWA 子路径导航回退绝对化 | 🆕v4.71 meta-rule #117 落地：base 非 `/` 时 navigateFallback 必须绝对路径 base+'index.html'，workbox cleanupOutdatedCaches:true，index.html 有加载占位；参数在 `pwa_subpath_navfallback` 节点管理 |
| 44 | 设计令牌集中化（禁硬编码色）| 🆕v4.71 meta-rule #119 落地：颜色/圆角/间距集中在 CSS 变量/token，组件内禁止硬编码十六进制色，装饰色移除改品牌灰阶，满足 WCAG AA；参数在 `design_tokens` 节点管理 |
| 45 | SPA 基路径三处对齐 | 🆕v4.71 meta-rule #118 落地：vite base ⇄ BrowserRouter basename ⇄ 后端剥离前缀 三处一致，自动打开入口统一 <base> 禁 /app/ 裸 /；参数在 `spa_basename_consistency` 节点管理 |


---

## 37. Provider �����ǰ��״̬���� ??v4.46

- ���صȼ���WARNING��P1��Provider UI ״̬��һ�µ����û������½���
- ���ã�meta-rules #71 / step 210
- **F-REVIEW-162��PROVIDER-UI-STATE ������Ⱦһ����**
  - ÿ�� Provider �����ñ���ֶα������ provider ����������Ⱦ
  - ��ͬ Provider ��ר��������� cpolar authtoken��Cloudflare cert_file��Tailscale ��װָ����������©
  - �ж��źţ�grep "formProvider.*===" frontend/src/ ȱ��ĳ�� provider ���͵�������֧
  - ��Ӧ����淶��step 210

- **F-REVIEW-163��WIZARD-STEPS ���������״̬��**
  - Named Tunnel �򵼱���ʹ�� Steps ����ֲ�������ÿ������ȷ�Ľ���/���/��������
  - ��״̬��currentStep�������� config.yaml �־û�״̬һ��
  - �ж��źţ��򵼲���״̬�������ļ��� cert_file/tunnel_id/hostname ��һ��
  - ��Ӧ����淶��step 210

- **F-REVIEW-164��ASYNC-LOADER-ISOLATION �첽����������**
  - ÿ���첽������login ��ѯ��create��route-dns�������ж����� loading ״̬
  - ��ֹ���� loading ״̬���²����以�����
  - �ж��źţ�loginLoading �� createLoading ����ͬһ�� loading ����
  - ��Ӧ����淶��step 210

- **F-REVIEW-165��POLL-TIMER-CLEANUP ��ѯ��ʱ������**
  - ��ѯ��ʱ����setInterval�����������ж��ʱͨ�� useEffect cleanup ����
  - ��ѯ�ص��б������������״̬����ֹж�غ� setState
  - �ж��źţ�setInterval ���ڵ� useEffect ���غ������� clearInterval
  - ��Ӧ����淶��step 210

- **F-REVIEW-166��ERROR-RESET ����״̬����**
  - �첽����ʧ�ܺ����������� loading �� polling ״̬
  - �û�����ʱ�������֮ǰ�Ĵ���״̬
  - �ж��źţ�catch ������ setLoginPolling(false) �� setCreateLoading(false)
  - ��Ӧ����淶��step 210

- **���ò���**��provider_ui.wizard_steps��provider_ui.poll_interval_ms��Ĭ�� 2500����provider_ui.async_timeout_ms��Ĭ�� 30000���� config.yaml �� provider_ui �ڵ����
- **����**������ Provider ��ص� UI �����Tunnel.tsx��tunnelProviders.ts��tunnel.ts API ģ�飩
- **������**���� Provider ��صı�����첽����

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

## 45. ��ѯ״̬��ʱչʾ v4.51.0

**F-REVIEW-191: POLLING-TIMEOUT-DISPLAY ǰ����ѯ״̬��ʱչʾ**

- **�淶**��ǰ����ѯ���״̬ʱ����ͬһ״̬����������ֵ���� config ��ȡ��������չʾ��ʱ��ʾ���ṩ"����"����
- **�ж��ź�**��`grep "setInterval.*status|useEffect.*poll"` ���޳�ʱ��ʱ��
- **���ýڵ�**��`config.yaml#async_polling_pattern.timeout_display`
- **���ó���**��
  - �������¼״̬��ѯ��/browser-login/status��
  - Cookie ���������ѯ
  - ������ִ�н�����ѯ
  - �κ� setInterval + status ״̬��ģʽ
- **�����ó���**��
  - һ���� fetch ���󣨷���ѯ��
  - SSE/WebSocket ���ͣ�������������ͣ�����ǰ�˳�ʱ��
  - �û��ֶ�ˢ�³���
- **��ʷ��ѵ**���������¼ Cookie �����׶� IPC �������º������ͣ�ͣ�ǰ�����޵ȴ� 90s ��ű����Ӧ��ǰ�� 60s ʱ������ʾ
---

## ��¼ A��2026-07-22 �������㣨���ڽ�һ�ֶԻ����̣�

> ��Դ����������ʧ������ק/�����û���ά�ȱ��ػ� 3 ����ʵ�����ĸ���

### A.1 ����б�����ʽָ�� width �� ellipsis

**�������**��
```bash
grep -rn "title:.*'" frontend/src/pages/ --include="*.tsx" | grep -v "key:" | grep "dataIndex\|key:" | head -20
```

**����׼**��
- �ַ����У����⡢��������ע������� `ellipsis: true` ����ʽ `width`
- SCROLL_X ����������� width �ܺͶ� 50-60px ����
- ���������������м� width���������㱼 �� �����б�ѹ���� 0 ���

**��ʵʧ��**��������ϸ���� SCROLL_X=1610���̶����ܺ� 1590���������� width����ѹ�����ɼ�

### A.2 ����/���ػ����뱣��ԭ key ������

**�������**��
```bash
grep -rn "translate\|i18n\|labels\[" frontend/src/ --include="*.tsx" --include="*.ts" | head -20
```

**����׼**��
- Tag / Tooltip / Statistic ����ʹ�÷��뺯��ʱ�������� `title` ���Ա���ԭ key
- ���뺯��δƥ�䵽 key ʱ�����뷵��ԭ�ַ��������ף�����ֹ���ؿ�
- ������ļ����������`*.labels.ts`�������ں��� i18n ��չ

**����**��
```tsx
<Tag title={reason}>{translateRejectReason(reason)}</Tag>
<Statistic title={`${translateDimension(dim)} (${dim})`} value={score} />
```

### A.3 �û�������״̬�����߳־û� hook

**�������**��
```bash
grep -rn "localStorage\|sessionStorage\|usePersistentState" frontend/src/ --include="*.tsx" --include="*.ts"
```

**����׼**��
- �û�ƫ�ã���˳����������ҳ��С��ˢ�¼��������� `usePersistentState` hook
- localStorage key ����� namespace ǰ׺���� `xh.evals.columns.order`�������ҳ���ͻ
- �־û��� schema ����� `validator` ��������ֹ�ɰ汾���ݷ����л�����
- ���ٱ��� 1 �пɼ� / ���� 1 ��Ĭ�����ã����ױ�����

**����**��
```tsx
const [order, setOrder] = usePersistentState<string[]>('xh.evals.columns.order', DEFAULT_ORDER, {
  validator: (v): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string')
})
```

### A.4 ��ק/������������ͬ�� state����ֹ�첽�ӳ�

**�������**��
```bash
grep -rn "onDragEnd\|onSortEnd\|DndContext\|SortableContext" frontend/src/ --include="*.tsx"
```

**����׼**��
- `onDragEnd` �ص����� `setState(newOrder)` ͬ�����£����ܵ� onChange
- ������"δ�仯ʱ���� setState"�жϣ�React ǳ�Ƚϻ�ʧЧ��
- ��קǰ��Ҫ�������� re-render��key �仯�����ñ仯��
- �����У�locked: true������������ק�¼�����

**����**��
```tsx
// ���󣺽���¼��˳�򣬲����� state
const onDragEnd = (e) => console.log(e.active.id, e.over?.id)
```

### A.5 ����������֤���̣�ǰ�����У�

**�������**���޸������ִ�У���
```python
# �� Python �� minify �� chunk����֤�ؼ�����/������Ƭ��
import glob, os
files = glob.glob('src/xianyu_hunter/web/static/spa/assets/*.js')
for f in files:
    content = open(f, encoding='utf-8', errors='ignore').read()
    if 'translateDimension' in content or 'ְҵ���' in content:
        print(f'HIT: {os.path.basename(f)}')
```

**����׼**��
- Vite minify �������ᱻѹ����translateDimension �� Ls���������� grep ��������֤
- ������ҵ��ؼ��ʣ����ı�ǩ��Ӣ�� token����֤
- ������������������Դ�ļ��޸�ʱ���� chunk mtime ֮ǰ

**��ʵʧ��**��dimensionLabels.ts ���ñ�����ɾ��������"�ɹ�"���������޷���

---

## ��¼ B���������ǿ��

### B.1 ����ʽ��飨������

```
1. ��̬��飨PR/����ύʱ��
   - �� grep �������
   - ��� TypeScript ���루tsc --noEmit��
   - ��� ESLint

2. ������飨�ϲ�ǰ��
   - npm run build �ɹ�
   - Python �ű���֤�ؼ� chunk ���´���
   - ������ֶ���֤���� 1 ����������

3. �ع���飨����ǰ��
   - ȫ������ͨ����vitest��
   - �˵��˹ؼ�·����Playwright��
```

### B.2 ��鱨��ģ�壨������¼��

```markdown
## ��鱨�� - {�������}

### ������Blocker��
- [ ] ����� width ȱʧ �� �б�ѹ�����ɼ�
- [ ] �����δ����ԭ key �� ���Բ��ɶ�λ

### �ؼ���Critical��
- [ ] �־û� key �� namespace �� ��ҳ���ͻ
- [ ] ��ק��δͬ�� state �� �û���������Ч

### ���飨Major��
- �������Ϊ�����ļ�
- ��ק�����м� `disabled` �Ӿ�����

### ����
- [ ] tsc --noEmit ͨ��
- [ ] npm run build �ɹ�
- [ ] Python ��֤ chunk ���´���
- [ ] ������ֶ���֤ OK
```

---

## ��¼ C���汾��ά��

- ���θ��£�2026-07-22
- �������ܣ�xianyu-hunter-dev����¼ A.5����xianyu-auto-testing
- ������Դ��`docs/00-�����/����-����淶�뼼���Ż�-2026-07-22.md`

---

> **v4.53.0 F-REVIEW-199 COMPONENT-REUSE-STATE-RESET �������״̬ͬ��������飨meta-rule #85 ��أ�2026-07-22 ThumbCell errored ״̬���� Bug ���̣�**�����ڱ��ζԻ������"�ٷ��ɼ�����ͼƬ URL ������ͼ����ʾռλͼ"���⸴�̣������� `ThumbCell` ����� `rowKey={`${r.item_id}-${r.created_at}`}` ���䱻 React ���ã�`useState(false)` �� `errored` ״̬���Զ����á�ʹ�� Sequential Thinking 4 ά�ȸ��̷������ɹ����裨ʶ�� rowKey ������Ų� useState ���á���� useEffect ���á�������֤��/��ȷ���ԣ��Ƿ����������ͬ�����⣩/�ɳ������̣������ useState + ������ + �ڲ�״̬���� prop �� ���� useEffect ���ã�/�����벻���ó��������� 1 �� F-REVIEW ���㡣**F-REVIEW-199 COMPONENT-REUSE-STATE-RESET**��ά�� 3/19����React ����� `rowKey` ���䱻����ʱ��`useState` �ڲ�״̬�����Զ����ã��ڲ�״̬��errored/loading/selected�������� prop �仯ʱ�������� `useEffect` ���á��ж��źţ�`grep "useState" frontend/src/` �ҵ����ڲ�״̬����� �� ����Ƿ��� `<Table>` render / `expandedRowRender` / Tab ��壨`destroyInactiveTabPane={false}`����ʹ�� �� ��� prop �仯ʱ�Ƿ��� `useEffect` �����ڲ�״̬��`rowKey` ����̬�ֶΣ��� `created_at`��+ �б�������� `useState` �� ����ᱻ���ã����������ã������ `errored`/`loading`/`failed` ״̬���޶�Ӧ `useEffect` ���� �� ��ΪΥ�档�޸�ģʽ��`useEffect(() => { setErrored(false) }, [url])`�����ò����� `config.yaml` �� `component_reuse_state_reset` �ڵ�����`enabled`/`components`/`reset_value_defaults`/`reuse_contexts`������Ӳ����ҵ����������ã��б��������չ���������Tab ��������`rowKey` ����̬�ֶε��б�������ã�ÿ�ζ�������ʵ���������key Ψһ�������ڲ�״̬�Ĵ�չʾ�����useEffect ����������������� F-REVIEW-159������ϸ����淶���ϵ� `xianyu-hunter-dev` v4.52.0 �� step 249����˶�Ӧ�ޣ���ǰ�˹淶����

---

## v4.55.0 F-REVIEW-200~204 �������淶��2026-07-22 �ڶ��ָ��̣�

> ��Ӧ xianyu-hunter-dev meta-rules #84-#88������ Sequential Thinking ��ά�ȸ��̳����
> ���ײ���ģʽ��xianyu-auto-testing ģʽ L��״̬�������ع飩/ ģʽ M�����������Լһ���ԣ���

### F-REVIEW-200 DERIVED-SOURCE-ANNOTATION ����ֶ�������Դ��ע��飨ά�� 11/15��

**��ӦԪ����**��#88 �� 5 �� / #35��ǰ����ֶ���Լ��һ����Դ��

**���Ҫ��**��
1. ��� `ResponseModel` / DB Row �ֶα��ʱ��ǰ�� `types.ts` �Ƿ�ͬ������
2. ǰ�� `types.ts` �п���ֶ��Ƿ��ע������Դ��`// derived from backend ResponseModel.xxx`��
3. ����ֶ�������/ɾ��ʱ��ǰ���Ƿ�ͬ���޸ģ�grep ����ֶ����� types.ts �еĲ����

**�жϱ�׼**��
- ��� `ResponseModel` �����ֶε�ǰ�� `types.ts` �޶�Ӧ �� CRITICAL����Լ��ͬ����
- ǰ�� `types.ts` �ֶ���������Դע���ҿ������ �� WARNING����׷����ȱʧ��
- ����ֶ�ɾ����ǰ�� types.ts �������� �� CRITICAL���������ͨ��������ʱ undefined��

**�������**��
```powershell
# ��ȡ��� ResponseModel �ֶ�
Select-String -Path "src/xianyu_hunter/web/routes/api_*.py" -Pattern "class.*ResponseModel" 
# �Ա�ǰ�� types.ts
Select-String -Path "frontend/src/types.ts" -Pattern "derived from"
```

**���ó���**����� ResponseModel/DB Row �ֶ�����/ɾ��/��������ǰ�����Լ�������
**�����ó���**����ǰ���ڲ����ͣ��޺����Դ���������������Ͷ���

---

### F-REVIEW-201 CONFIG-FIELD-UI-COVERAGE �����ֶ�ǰ�˱༭�ؼ�������飨ά�� 11/15��

**��ӦԪ����**��#87 �� 5 �㣨ǰ�� Config.tsx �༭�ؼ���

**���Ҫ��**��
1. DB schema ���û��ɱ༭�����ֶ��Ƿ��� `Config.tsx` ���ж�Ӧ�༭�ؼ�
2. �༭�ؼ������Ƿ����ֶ�����ƥ�䣨string��Input/textarea��bool��Switch��enum��Select��list��Transfer/Select multiple��
3. `types.ts` �������ֶ����Ͷ����Ƿ���ȫ

**�жϱ�׼**��
- DB schema ���ֶε� `Config.tsx` �ޱ༭�ؼ� �� CRITICAL���� 5 ��ȱʧ��
- �ֶ�����Ϊ text ��ʹ�� Input ���� textarea�����ı��������� WARNING
- `types.ts` ȱ���ֶ����Ͷ��� �� CRITICAL���� 4 ��ȱʧ��

**�������**��
```powershell
# �г� Config.tsx �еı���ؼ�
Select-String -Path "frontend/src/pages/Config.tsx" -Pattern "<(Input|TextArea|Switch|Select|Slider|InputNumber)"
# �Ա� types.ts �е������ֶ�
Select-String -Path "frontend/src/types.ts" -Pattern "Config"
```

**���ó���**�����������ֶκ��ǰ�˸�����飻����ҳ���ع������������֤
**�����ó���**��ֻ�����ã����û��ɱ༭������������/����������� DB �־û���

---

### F-REVIEW-202 CONFIG-RESTORE-DEFAULT �����ֶλָ�Ĭ�ϻ�����飨ά�� 11/15��

**��ӦԪ����**��#87 �� 3 �㣨�ָ�Ĭ�ϻ��ƣ�

**���Ҫ��**��
1. ÿ���û��ɱ༭�����ֶ��Ƿ���"�ָ�Ĭ��"��ڣ���ť/�˵�/ͼ�꣩
2. "�ָ�Ĭ��"�Ƿ���� `delete_config`��ɾ�� DB ��¼������д��Ĭ��ֵ�ַ���
3. "�ָ�Ĭ��"��ť��ֵ����Ĭ��ֵʱ�Ƿ� disabled��disabled-when-default��
4. �ָ�Ĭ�Ϻ� UI �Ƿ�ˢ��Ϊ������Ĭ��ֵ

**�жϱ�׼**��
- �����ֶ���"�ָ�Ĭ��"��� �� WARNING���ָ�Ĭ�ϻ���ȱʧ��
- "�ָ�Ĭ��"ͨ��д��Ĭ��ֵ�ַ���ʵ�� �� CRITICAL��Ĭ��ֵ�������ʱ��
- "�ָ�Ĭ��"��ťδʵ�� disabled-when-default �� NIT���û��������⣩

**�������**��
```powershell
Select-String -Path "frontend/src/pages/Config.tsx" -Pattern "delete|restore|�ָ�Ĭ��|reset"
```

**���ó���**���û��ɱ༭�����DB �־û������ñ�
**�����ó���**��ֻ�����ã���Ĭ��ֵ�����������

---

### F-REVIEW-203 TIMEOUT-STAGE-DISPLAY ��ʱ�׶��� UI ��ʾ��飨ά�� 13/15��

**��ӦԪ����**��#85 �� 2 �㣨��ʱ�쳣�û��Ѻ����壩

**���Ҫ��**��
1. �ಽ���첽����������/�ɼ�/��¼����ʱʱ��UI �Ƿ���ʾ����׶�������"�ύ������ʱ"������"δ֪�쳣"
2. ��ʱ������Ϣ�Ƿ������ʱ���� + ����ԭ�� + �������
3. ��ʱ toast/message �Ƿ�����"��ʱ"��"�ỰʧЧ"��������

**�жϱ�׼**��
- ��ʱ��ʾ"δ֪�쳣" �� CRITICAL���û��޷��ж��ǳ�ʱ���ǻỰʧЧ��
- ��ʱ��Ϣ�޳�ʱ���� �� WARNING���û��޷��ж��Ƿ������ʱ��
- ��ʱ��ỰʧЧʹ����ͬ�İ� �� WARNING�����������

**�������**��
```powershell
Select-String -Path "frontend/src/pages/**/*.tsx" -Pattern "δ֪�쳣|unknown error|timeout|��ʱ"
```

**���ó���**�������û����첽��ʱ����������/�ɼ�/��¼�����ಽ��ؼ�·��
**�����ó���**���ڲ���ʱ���ԣ���ֱ�������û�������������

---

### F-REVIEW-204 OVERWRITE-SET-FRONTEND-AWARENESS ���ǲ���ǰ�˸�֪��飨ά�� 11/15��

**��ӦԪ����**��#88 �� 4 �������ǲ��Լ��Ϲ������ ǰ�˲�

**���Ҫ��**��
1. ǰ���Ƿ�����˷��ص��ֶ���������ֵ������ `_coalesce` �����¿��ܱ����ֵ�ĳ�����
2. ǰ��չʾ"�ɼ�δȡ��"���ֶ�ʱ�Ƿ�����"������"��"δȡ��"������ʾ"����"���ǿհף�
3. ǰ���Ƿ��ڹٷ��ɼ�/�زɺ󴥷�����ˢ�£�����չʾ�������ݣ�

**�жϱ�׼**��
- ǰ�˼����ֶ���������ֵ������� `_coalesce` �� WARNING������չʾ��ֵ��ǰ�˲�֪�飩
- "δȡ��"�ֶ���ʾ�հ׶���"����" �� NIT���û��������⣩
- �ٷ��ɼ���δ��������ˢ�� �� WARNING��չʾ�������ݣ�

**�������**��
```powershell
# ���ǰ���Ƿ���"�ɼ���ˢ��"�߼�
Select-String -Path "frontend/src/pages/**/*.tsx" -Pattern "refresh|reload|fetch.*after|�ɼ�.*ˢ��"
```

**���ó���**���ɼ�-�洢-չʾ��·���ٷ��ɼ�/�زɴ������ݸ���
**�����ó���**����ǰ���ڲ�״̬���޲ɼ��߼���ҳ��

---

> **v4.55.0 F-REVIEW-200~204 ���淶�������**����Ӧ xianyu-hunter-dev v4.55.0 meta-rules #84-#88������ xianyu-auto-testing ģʽ L/M��

---

## v4.56.0 F-REVIEW-205 �������淶

### F-REVIEW-205: SIDE-EFFECT-FALLBACK-ALERT ǰ�˸����ö�����ʾ��飨ά�� 13/15��

**��Ӧ meta-rule**��#89 LOGIN-SIDE-EFFECT-AUTOMATION��ǰ����أ�
**���׹淶**��xianyu-hunter-dev/assets/guides/coding-rules/concurrency.md step 253
**���ýڵ�**��config.yaml#side_effect_fallback_alert

**����**����˵�¼�����ã���Ự���ڣ����� fire-and-forget ģʽ��ʧ��ʱ�� logger.debug��ǰ�����֪��˸�����״̬����ʧ��ʱ�ṩ������ʾ���ֶ�������ڣ������û�����Ϊ"��¼�ɹ������ܲ�����"��

**���Ҫ��**��
1. **������ʾ������**����˸�����ʧ��ʱ��ǰ�˱����ж�����ʾ��Alert/Message�������ܾ�Ĭ�޷���
2. **����������ȷ��**����������Ӧ��� `session.active === false` �� `session.status !== 'running'`�����Ƿ����Ĵ���״̬
3. **Alert ���͹淶**��������ʾ����ʹ�� `type="warning"`���� error�����¼�������ѳɹ������ṩ�ֶ��������
4. **�ֶ��������**��������ʾ�������"�ֶ�����Ự"��ť�����ӣ����ú�� `/api/session/start` �ӿ�
5. **״̬��ѯ����**����¼�ɹ���ǰ��Ӧ��ѯ `/api/session/status` ȷ�ϸ������Ƿ���Ч����ʱδ��Ч����ʾ������ʾ
6. **���ò���ע��**��������ʾ�İ�����ѯ������ʱ��ֵ�Ȳ�������� config.yaml ��ȡ

**�ж��źţ�grep ���**��
```bash
# �ź� 1����¼�ɹ�ҳ���޶�����ʾ
grep -rn "login.*success\|��¼�ɹ�" frontend/src/pages/AntiCrawl/ | grep -v "Alert\|Message\|notification"

# �ź� 2��������������ȷ
grep -rn "session.active\|session.status" frontend/src/pages/AntiCrawl/ | grep -v "=== false\|!== 'running'"

# �ź� 3��ȱ���ֶ��������
grep -rn "Alert.*type=\"warning\"" frontend/src/pages/AntiCrawl/ | grep -v "Button\|onClick.*start"
```

**�������**��
```bash
# ͳ�ƶ�����ʾ�����
grep -c "Alert.*warning" frontend/src/pages/AntiCrawl/*.tsx
# ͳ���ֶ������ť��
grep -c "�ֶ����\|manual.*start\|startSession" frontend/src/pages/AntiCrawl/*.tsx
```

**ͨ����׼**��
- ��¼�ɹ�ҳ����ڶ��� Alert ���
- ����������ȷ��� `session.active === false`
- Alert ����Ϊ warning�������ֶ������ť
- ״̬��ѯ����볬ʱ��ֵ�� config ��ȡ
- �İ��� config ��ȡ����Ӳ����

**���ó���**��
- ��¼�ɹ���������˸����õ�ҳ�棨�練����¼����ҳ��
- ������ʧ�ܲ�Ӱ�������ܵ�Ӱ������ĳ���

**�����ó���**��
- ��¼������ʧ�ܵĴ�����ʾ��Ӧ�� error ���ͣ�
- �޸����õĴ�չʾҳ��
- ������ʧ�ܻᵼ�����ݶ�ʧ�ĳ�����Ӧ�� error ���Ͳ���ֹ������

---

> **v4.56.0 F-REVIEW-205 ���淶�������**����Ӧ xianyu-hunter-dev v4.56.0 meta-rule #89��ǰ����أ������� xianyu-auto-testing ģʽ N��config.yaml �Ѳ�ȫ side_effect_fallback_alert ���ýڵ㡣

---

## v4.57.0 F-REVIEW-206 �������淶

### F-REVIEW-206: FALLBACK-PRESERVE-KEY-FRONTEND ���˹��������������飨ά�� 11/15��

**��Ӧ meta-rule**��#90 FALLBACK-PRESERVE-KEY��ǰ����أ�
**��Ӧ��˹���**��B-REVIEW-251
**���ýڵ�**��config.yaml#fallback_preserve_key_frontend
**���صȼ�**��error

**����/��ʷ��ѵ**��2026-07-22 price_range ע�� Bug ���̡�ǰ���ڻ��˹��� item ʵ��ʱ������¼� payload ���˹��죩����©�� task_id �ȹ��������������������ù��������߼���������������û�������ʧЧ��ʹ�� Sequential Thinking 4 ά�ȸ��̷������ɹ����裨ʶ����˹�����Ų��������©����ʽ��ȡ��������֤��/��ȷ���ԣ��Ƿ����������˹���ͬ�����⣩/�ɳ������̣�ǰ�˴Ӳ������ݹ���ʵ�� + �������������� �� ������ʽ��ȡ��������/�����벻���ó��������� 1 �� F-REVIEW ���㡣

**���Ĺ���**��ǰ�˴Ӻ�˻������ݣ����¼� payload ���˹����ʵ�壩�������ʱ�����뱣�����������Ĺ��������� task_id��user_id��item_id����

**���Ҫ��**��
1. **���˹��������������**��ǰ�˴Ӳ�������/�¼� payload ���˹���ʵ��ʱ��������ʽ��ȡ�������������������Ĺ��������� task_id��user_id��item_id��
2. **����������Ĭ�Ͽ�**���������ֶβ����� `undefined`/`null`/`''` ��ΪĬ��ֵ���ף������ payload/response ��ʽ��ȡ
3. **��������У��**���������Ѹ�ʵ����߼����簴 task_id ��ѯ���� user_id �ۺϣ��������õ��ǿչ�����
4. **���ò���ע��**���豣��Ĺ������嵥�� config.yaml ��ȡ����Ӳ����

**�ж��źţ�grep ���**��
```bash
# �ź� 1���ҵ����˹���
grep -rn "payload.get" frontend/src/

# �ź� 2�����˹�����©���������������ʱδ��ȡ task_id/user_id/item_id��
grep -rn "payload.get" frontend/src/ | grep -v "task_id\|user_id\|item_id"
```

**�������**��
```bash
# ͳ�ƻ��˹������
grep -rc "payload.get" frontend/src/
# �����˹����Ƿ񺬹�������ȡ
grep -rn "payload.get" frontend/src/ | grep -E "task_id|user_id|item_id"
```

**�޸�ģʽ**�����˹���ʱ�� payload/response ����ʽ��ȡ��������
```typescript
// ? Υ�棺���˹��� item ʱ��© task_id
const item = {
  id: payload.get('id'),
  price_range: payload.get('price_range'),
  // task_id ��© �� ���ΰ� task_id ����ʧЧ
}

// ? �Ϲ棺��ʽ��ȡ������
const item = {
  id: payload.get('id'),
  price_range: payload.get('price_range'),
  task_id: payload.get('task_id'),  // ��ʽ��ȡ���������ι���
  user_id: payload.get('user_id'),  // ��ʽ��ȡ
}
```

**���ò���**���� `config.yaml` �� `fallback_preserve_key` �ڵ�����`enabled`/`required_keys`/`entity_types`/`fallback_sources`������Ӳ����ҵ�������

**ͨ����׼**��
- ���˹����ʵ��������� `fallback_preserve_key.required_keys` �����Ĺ�����
- �������� payload/response ��ʽ��ȡ����Ĭ�Ͽ�ֵ
- �������嵥�� config.yaml ��ȡ����Ӳ����

**���ó���**��
- ǰ�˴Ӳ������ݹ���ʵ�� + ��������������
- �¼� payload ���˹���ʵ��
- SSE/WebSocket �¼����˹���

**�����ó���**��
- ֱ�Ӵ� API ��ȡ����ʵ�壨�޻��ˣ�
- ��ǰ�˹������ʱ�����޺�˹�����

---

> **v4.57.0 F-REVIEW-206 ���淶�������**����Ӧ xianyu-hunter-dev v4.57.0 meta-rule #90��ǰ����أ���config.yaml �Ѳ�ȫ fallback_preserve_key_frontend ���ýڵ㡣��˶�Ӧ B-REVIEW-251��

---

## v4.60.0 F-REVIEW-214~216 �������淶��2026-07-22 �����ָ��̣�

> ���� xianyu-hunter-dev v4.60.0 meta-rules #101-#102 ��أ���Ӧ"Cookie ״̬�쳣 + ҳ�����ó־û� + CDP ģʽ״̬��ʧ"�������⸴�̡����ýڵ㣺`config/tech-stack.json#hardConstraints.uiPersistence` �� `hardConstraints.multiWritePathCheck`��

### F-REVIEW-214: MULTI-WRITE-PATH-STATE-CHECK ��д��·��״̬��飨meta-rule #101 ǰ����أ�??v4.60

**��������**��ǰ����֤���������м��״̬���� CookieRotator._layer_states.valid����ǰ�����������˻�����м�״̬��ǰ���ж��д��·������ͬһ״̬ʱ
**���ýڵ�**��`config/tech-stack.json#hardConstraints.multiWritePathCheck`
- `intermediateStatePatterns`���м��״̬�ֶ�ģʽ�б��`_layer_states`��`.valid`��`.active`��`_cache_time`��
- `writeEntryPatterns`��д�����ģʽ�б��`on_login_success`��`atomic_update`��`sync_state`��
- `validateActualDataPreferred`���Ƿ�������֤ʵ�����ݣ�true��
- `autoSyncEnabled`���Ƿ������Զ�ͬ����true��

**��鲽��**��
1. **ʶ���м��״̬����**��Grep ɨ��ǰ�˴��������õ��м��״̬�ֶ�
2. **ö������д��·��**��Grep ɨ�����п��ܸ��¸�״̬��д�����
3. **��֤д��·��������**����ÿ��д����ڣ�����Ƿ������״̬��ʼ��/ͬ���߼�����1 ��д��·��δ���� �� P0 ȱ��
4. **����ʵ��������֤**����֤�����Ƿ�ֱ�Ӽ��ʵ�����ݣ��� Cookie ���ݡ�DB ��¼�����ǽ������м��״̬�������������Զ�ͬ�� �� P1 ȱ��
5. **�Զ�ͬ������**����֤��������״̬��һ��ʱ�Ƿ��Զ�ͬ�������Զ�ͬ���������м��״̬ �� P1 ȱ��

**Grep ����**��
```bash
# ʶ���м��״̬����
grep -rn "_layer_states\|\.valid\|\.active\|_cache_time" frontend/src/ --include="*.ts" --include="*.tsx"
# ö��д�����
grep -rn "on_login_success\|atomic_update\|sync_state\|set_layer_state" frontend/src/ --include="*.ts" --include="*.tsx"
# ��֤д��·�������ԣ�д�����δ����ͬ����
grep -rn "on_login_success\|atomic_update" frontend/src/ --include="*.ts" --include="*.tsx" | grep -v "sync_state\|init_state"
```

**���ó���**��Cookie ״̬�������¼̬ͬ���������״̬��������״̬�������û�������״̬
**�����ó���**����ǰ����ʱ״̬���� loading ��ǣ����޺�������ı��ؼ���״̬��һ������Ⱦ״̬
**�����й���Ĺ�ϵ**������ F-REVIEW-113�������״̬ͬ������ F-REVIEW-197�����û������Ĵ��ݣ���ǰ�߹�ע�����ͬ�����ƣ��������עд��·��������

---

### F-REVIEW-215: UI-PREFERENCE-PERSISTENCE-CHECK UIƫ�ó־û���飨meta-rule #102 ǰ����أ�??v4.60

**��������**������ҳ������ʱʹ�� `useState` �����û������õ� UI ƫ�ã����ҳ��С����ͼģʽ��ɸѡ����������״̬������ʽ�����������ҳ���Ƿ���δ�־û��� UI ƫ��
**���ýڵ�**��`config/tech-stack.json#hardConstraints.uiPersistence`
- `persistablePreferences`������־û���ƫ���б��pageSize/viewMode/filter/Enabled/Mode/sortBy/sortOrder��
- `nonPersistableStates`����Ӧ�־û���״̬�б��loading/error/modalVisible/dropdownOpen��
- `storageKeyPrefix`��localStorage key ǰ׺��`xh.`��
- `defaultDebounceMs`��Ĭ�Ϸ����ӳ٣�300ms��
- `draftDebounceMs`���ݸ�����ӳ٣�500ms��

**��鲽��**��
1. **ɨ�� useState ʹ��**��Grep ɨ������ҳ������е� `useState` ����
2. **ʶ���û�ƫ�ñ���**�����������Ƿ�ƥ�� `persistablePreferences` �б��е�ģʽ
3. **��֤�־û�**����ÿ��ƥ����û�ƫ�ñ���������Ƿ�ʹ�� `usePersistentState` ���� `useState`��ʹ�� `useState` �� P1 ȱ��
4. **��֤ storage key**����� `usePersistentState` �� key �Ƿ��� `storageKeyPrefix`��`xh.`����ͷ���Ƿ�Ψһ����������
5. **��֤��������**������Ƿ��ṩ `validator` ��������������֤����ֹ localStorage �����ݵ������ʹ���
6. **�ų��ǳ־û�״̬**����� `nonPersistableStates` �б��е�״̬�Ƿ������� `usePersistentState`

**Grep ����**��
```bash
# ɨ�� useState ��ʶ���û�ƫ�ñ���
grep -rn "useState" frontend/src/pages/ --include="*.tsx" | grep -iE "pageSize|viewMode|filter|Enabled|Mode|sortBy|sortOrder|useCdp|autoRefresh"
# ��֤�Ƿ�ʹ�� usePersistentState
grep -rn "usePersistentState" frontend/src/pages/ --include="*.tsx"
# ��֤ storage key ǰ׺
grep -rn "usePersistentState.*'" frontend/src/pages/ --include="*.tsx" | grep -v "'xh\."
```

**���ó���**�������û������õ� UI ƫ�ã���ҳ����ͼģʽ��ɸѡ�����򡢿��ء�����ѡ�񣩡�����ݸ��Զ����桢�򵼲������
**�����ó���**����ʱ UI ״̬��loading/error/modalVisible/dropdownOpen/hoveredRow�����ܿ�����ļ�ʱֵ�����������״̬
**�����й���Ĺ�ϵ**������ F-REVIEW-175��CONFIG-PERSIST-ON-CHANGE���� F-REVIEW-199��COMPONENT-REUSE-STATE-RESET����ǰ�߹�ע���ñ����ʱ���棬�������ע�û�ƫ�ÿ�Ự�־û�

---

### F-REVIEW-216: STORAGE-ERROR-HANDLING-CHECK storage �������飨meta-rule #102 ������??v4.60

**��������**��ʹ�� localStorage/sessionStorage �������ʵ���Զ���洢���߻� Hook�����洢��ش���Ĵ�����ͻ��˻���
**���ýڵ�**��`config/tech-stack.json#hardConstraints.uiPersistence`
- `storageVersionField`���洢��ʽ�汾�ֶ�����`__v`��
- `defaultDebounceMs`�������ӳ٣�������֤����д���Ƿ���ȷʵ��

**��鲽��**��
1. **��֤ try-catch ����**������ localStorage ��д������������� try-catch �У���ֹ `QuotaExceededError`��`SecurityError` �׳�δ�����쳣
2. **��֤���˻���**��localStorage ������ʱ����˽ģʽ/���ã��������ڴ���ˣ��� `Map`��������ֱ�ӱ���
3. **��֤���ݸ�ʽ**���洢��ʽ��������汾�ֶΣ�`__v`��������δ��Ǩ�ơ���ȡʱ������֤�汾���汾��ƥ��ʱ���˵�Ĭ��ֵ
4. **��֤����У��**����ȡ�����ͨ�� `validator` ����У���������ͣ���ֹ�洢�ľ����ݻ򱻴۸ĵ����ݵ������ʹ���
5. **��֤����д��**����Ƶ���µ�״̬����ʹ�÷���д�루Ĭ�� 300ms��������Ƶ��д�� localStorage Ӱ������
6. **��֤ isPersistent ��ʶ**��`usePersistentState` ���뷵�� `isPersistent` ��ʶ�������֪����ǰ�Ƿ������־û�

**Grep ����**��
```bash
# ��֤ try-catch ������δ������ localStorage ������
grep -rn "localStorage\.\(getItem\|setItem\|removeItem\)" frontend/src/ --include="*.ts" --include="*.tsx" | grep -v "try"
# ��֤���˻���
grep -rn "Map()\|new Map" frontend/src/utils/storage.ts
# ��֤�汾�ֶ�
grep -rn "__v" frontend/src/utils/storage.ts
# ��֤����д��
grep -rn "debounce\|setTimeout" frontend/src/hooks/usePersistentState.ts
```

**���ó���**������ʹ�� localStorage/sessionStorage �ĳ������Զ���洢���ߡ��־û� Hook��PWA ���߻���
**�����ó���**��Cookie �������ж����Ĵ�����淶����IndexedDB �������ж�����������ƣ����ڴ�״̬
**�����й���Ĺ�ϵ**������ F-REVIEW-138��HOOK-CLEANUP-COMPLETENESS���� F-REVIEW-165��POLL-TIMER-CLEANUP����ǰ�߹�ע Hook ��������������������ע�洢��Ĵ�����ͻ���

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
const items = data?.items ?? []

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

> **v4.60.0 F-REVIEW-214~216 ���淶�������**����Ӧ xianyu-hunter-dev v4.60.0 meta-rules #101-#102��ǰ����أ���config/tech-stack.json �Ѳ�ȫ `hardConstraints.uiPersistence` �� `hardConstraints.multiWritePathCheck` ���ýڵ㡣��˶�Ӧ B-REVIEW-267/268��auto-testing ��Ӧģʽ S/T��


---

> **v4.69.0 F-REVIEW-SPA-AUTO-OPEN-ENTRY / 维度 13 构建依赖与缓存完整性 规范已补全**：对应 xianyu-hunter-dev S1 步骤8（自动打开浏览器入口 URL 必须 = SPA 基路径）+ S4（前端构建依赖与缓存完整性：workbox peer deps / emptyOutDir+safe-delete / optimizeDeps.force / PWA denylist 覆盖 /xianyu/api）。config.yaml 已补全 `spa` 节点（basename / api_prefix），并修正 stale `/app` → `/xianyu`。auto-testing 对应模式 AL/AM + 构建产物核对。

---

## 46. SPA Subpath / Base-Path Consistency (redirect scope + deploy basepath) v4.69

- Severity: HIGH (P0, white-board / tunnel 404 root cause)
- Reference: xianyu-hunter-dev 规范 23-24 / meta-rules #111-#112

- **F-REVIEW-SPA-REDIRECT-SCOPE: all redirects must use BASE_URL, bare-root `/` banned**
  - Any `location.replace()` / `location.href=` / `<Navigate to>` / `router.push()` target must include `import.meta.env.BASE_URL` (build-time `/xianyu/`) or a basename-relative path. A bare `/` or `''` target is a violation: under `BrowserRouter basename="/xianyu"` it mismatches routes (white screen), and outside the tunnel funnel `/xianyu/*` scope it triggers Tailscale's `404 page not found`.
  - Signal: `grep -rnE "location\.(replace|href)\s*=\s*['\"][^'\"]*['\"]|Navigate to=[\"']/?[\"']|router\.push\(\s*[\"']/?[\"']\s*\)" frontend/src/`
  - Config param: `spa.basename` (default `/xianyu/`) — single source. `apiBase.ts` must be `API_BASE = import.meta.env.BASE_URL`; never hardcode the literal `/xianyu/`.
  - Applicable: AccountSwitcher.tsx, api/client.ts (401 handler), App.tsx route table, any page/interceptor with redirects.
  - Not applicable: backend redirect responses; non-SPA.

- **F-REVIEW-SPA-DEPLOY-BASEPATH: index.html assets & SW scope must match base path**
  - `index.html` script/link URLs, `manifest.webmanifest` `start_url`/`scope`, and `sw.js` scope must all carry the `/xianyu/` prefix consistent with `vite.config.ts base:'/xianyu/'`. Mismatch causes assets 404 / SW scope error under subpath or tunnel deploy.
  - Signal: verify `vite.config.ts` `base` equals `spa.basename`; check `index.html` asset URLs start with `/xianyu/`; confirm `manifest.webmanifest` `start_url`/`scope` are `/xianyu/`.
  - Config param: `spa.basename` / `vite.config.ts base` — single config source, no hardcoded literal.
  - Applicable: vite.config.ts, index.html, manifest.webmanifest, sw.js, app.py SPA serving.
  - Not applicable: dev server (proxy rewrites `/xianyu`).

- **F-REVIEW-SPA-AUTO-OPEN-ENTRY: auto-open browser entry & full-page navigation must target SPA basename**
  - All "auto-open browser" entry points (launcher scripts, server-start logs, tray `on_open`, setup/automation scripts) and any full-page navigation (`location.replace`/`location.href` to app root) MUST target `spa.basename` (default `/xianyu/`), never a bare `/` or stale `/app/`. A bare `/` or `/app/` entry loads `index.html` 200 but `BrowserRouter basename="/xianyu"` fails to match routes → white screen.
  - Signal: `grep -rnE "start \"\" \"?http://[^\"]*/(app/)?\"?|location\.replace\(['\"]/?['\"]\)|webbrowser\.open\(['\"]http://[^'\"]*/(app/)?['\"]\)" scripts/ src/`
  - Config param: `spa.basename` (default `/xianyu/`) — single source, no hardcoded literal. In-app full-page jumps reuse `import.meta.env.BASE_URL`.
  - Applicable: scripts/启动服务.bat, scripts/launcher.py, scripts/automation.ps1, scripts/setup-env.ps1, web command logs, AccountSwitcher.tsx.
  - Not applicable: deep-link to a specific sub-route (must still sit under basename); dev server.

- **Applicable**: all frontend changes touching routing, redirects, build config, or static asset references
- **Not applicable**: pure backend changes; SSR apps; non-PWA apps

---

## 47. 构建产物图标与部署缓存（Build Artifact & Deploy Cache）v4.70 🆕

> 对应 `xianyu-hunter-dev` meta-rule #112（2026-08 构建产物图标复盘）。
> 所有审查参数（品牌图标路径/尺寸/严重级）均在 `config.yaml` 对应节点管理，**禁止硬编码**；判断用 grep 信号，禁止语义判断。

### F-REVIEW-227: BUILD-ARTIFACT-ICON-BRAND-CONSISTENCY 构建产物图标品牌一致性

- All shipped product icons — installer `SetupIconFile` / app exe icon (PyInstaller `.spec` `icon=`) / PWA `manifest.webmanifest` `icons` / favicon — MUST use the brand `.ico` (`assets/xianyu-hunter.ico`), never default builder icons nor bound system resources.
- No `shell32.dll` / `imageres.dll` system-icon binding: system icons are Microsoft copyright; binding them into a distributed product carries trademark/copyright risk. Formal products should use their own brand icon.
- Signal:
  ```powershell
  grep "SetupIconFile" installer.iss                              # 缺失 → 安装包默认图标
  grep "icon=" xianyu-hunter.spec                                # 缺失 → app exe 默认图标
  # 检查 manifest.webmanifest icons 指向品牌资源
  grep "shell32\|imageres" installer.iss scripts/                # 系统图标绑定 → WARNING
  ```
- Config param: `build_artifact_icon.brand_icon_path_default` / `forbid_system_icon_binding` / `recommend_size_px`（默认 256，避免高分屏大图标偏糊）— single source，no hardcoded literal。
- Applicable: 打包配置（installer.iss / .spec）、PWA manifest、favicon。
- Not applicable: dev server；第三方库默认资源且产品允许。

### F-REVIEW-228: DEPLOY-CACHE-INVALIDATION 部署缓存失效一致性

- After redeploying the SPA build to disk (the project deploys SPA from `src/.../static/spa/` to `dist/.../static/spa/` without a full PyInstaller rebuild), the PWA Service Worker MUST be version-bumped / cache invalidated. A stale SW serving an old entry chunk causes white screen or stale behavior; base path + auto-open entry must still match `spa.basename`.
- Signal:
  ```powershell
  grep -rn "sw.js\|serviceWorker\|registration" frontend/src/   # 确认 SW 版本键在部署时递增
  grep -rn "location.replace(['\"]/?['\"])|start \"\".*/(app/)? " scripts/ src/  # 入口仍指向 spa.basename
  ```
- Config param: `deploy_cache_invalidation.require_sw_version_bump` / `spa.basename`（单一可信源，禁止硬编码 `/xianyu/`）。
- Applicable: PWA-enabled deploy；磁盘 SPA 热更新（不整包重建）；隧道/子路径部署。
- Not applicable: dev server；非 PWA 应用。

### 审查流程与结果呈现增强（v4.70）

- **流程**：对打包配置与 PWA 部署，按 F-REVIEW-227~228 执行配置驱动核查——优先用上述 grep 信号定位，禁止"语义判断"；命中后回查 `config.yaml` 对应节点确认参数来源。
- **呈现**：每条 finding 除既有结构外，须标注 **①关联 meta-rule（#112）②配置节点（`config.yaml#...`）③适用/不适用场景**，确保与整体工作流（xianyu-hunter-dev 规范 SOP、xianyu-backend-code-review B-REVIEW-291、xianyu-auto-testing 模式 AN）高度一致、可追溯。
