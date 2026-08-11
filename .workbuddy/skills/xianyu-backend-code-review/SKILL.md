---
name: "xianyu-backend-code-review"
description: "对闲鱼猎人项目后端代码（src/xianyu_hunter/ �?Python/FastAPI/SQLAlchemy 文件）进行全面评审与逻辑审查，覆盖分层架构、异步并发、数据库规约、安全、性能、错误处理、日志规范、配置驱动、注册式资源 endpoint 契约、编码规范防御性复盘、跨层契约与测试同步�?36 个维度。当用户要求'审查/检�?走查/把关/review/评估/看看对不�?规范不规�?后端 Python 代码�?.py 文件修改'�?迭代发布前后端走�?，或提到'后端评审/backend review/Python 代码审查/FastAPI 评审/SQLAlchemy 评审'时调用。仅审查后端 .py 文件；纯前端 .tsx/.ts 文件审查请改�?xianyu-frontend-code-review�?
whenToUse: "需要审查闲鱼猎人后端代码（src/xianyu_hunter/ �?.py 文件，含路由 routes/、仓�?infra/repo_*.py、领域模�?domain/、调度器 scheduler、配�?yaml_config、异步并发代码）是否符合项目规范"
triggers: "后端代码 走查/审查/审核/把关/review/检�?评估 | 后端评审/backend review/Python 代码审查/FastAPI 评审/SQLAlchemy 评审 | .py 文件 修改/变更/迭代 走查 | 迭代发布�?后端 代码 走查 | 这段后端代码 写得对不�?规范不规�?| 闲鱼 后端 代码 review | 路由/仓储/领域模型/调度�?代码 审查"
version: "4.71.0"
updated: "2026-08-11"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# 闲鱼猎人后端代码审查

对闲鱼猎人项目后端代码（`src/xianyu_hunter/` 下的 Python/FastAPI/SQLAlchemy 文件）进行全面的代码评审及逻辑审查。评审涵�?*36 个维�?*，包括分层架构、命名规范、异步并发、数据库规约、安全约束、性能优化、错误处理、日志规约、配置管理、智能客服专项、Git 操作规范、跨字段一致性与硬编码属性禁用、LLM 端点能力派发、端到端失败原因链与数据完整性闭环、多用户资源隔离与身份识别、业务关键字常量集中管理与跨端契约对齐、数据契约与时序（meta-rules #25-30 落地）、状态恢复前置校验与降级链日志合并（meta-rules #31-32 落地）、注册式资源 endpoint 契约 + 修复前全链路根因扫描协议 + 前后端字段契约单一可信源（meta-rules #33-35 落地）、规范治理（meta-rules #36-37 落地）、列表聚合与状态联动（meta-rules #38-42 落地）、编码规范防御性复盘（meta-rules #57-63 落地）、跨层契约与测试同步（meta-rules #47-51 落地）等�?

## 版本演进索引

> 各版本的完整复盘详情已外部化�?[references/version-changelog.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/version-changelog.md)。本表仅作索引，需查阅历史决策与根因时再读取该文件�?

| 版本 | 新增检查点 | 维度 | 扫描�?| 核心变化 |
|---|---|---|---|---|
| v4.50.0 | B-REVIEW-238 DATA-PROPAGATION-INTEGRITY / B-REVIEW-239 SNAPSHOT-VS-LATEST-SEPARATION / B-REVIEW-240 FALLBACK-DATA-MERGE-COMPLETENESS / B-REVIEW-241 MULTIUSER-ISOLATION-WRITE-CONSISTENCY | 10,10,10,10 | 236->240 | �������͸�������� / ����������ְֵ����� / fallback ���ݺϲ������� / ���û�����д��һ���ԣ�meta-rules #83 ��أ�2026-07-18 ������� Bug ���̣� |
| v4.60.0 | B-REVIEW-275 CACHE-GUARD-3RULES / B-REVIEW-276 FIELD-STRATEGY / B-REVIEW-277 STATE-MACHINE-RETURN / B-REVIEW-278 CALLBACK-INJECTION / B-REVIEW-279 CROSS-LAYER-CLOSED-LOOP / B-REVIEW-280 WINDOWS-ENCODING | 8,8,8,8,8,8 | 274->280 | 缓存守卫三原则/数据写入策略字段级决策/状态机返回值语义/回调注入默认值/跨层闭环验证/Windows编码规范（meta-rule #102，2026-07-23 四维度复盘） |
| v4.61.0 | B-REVIEW-281 CONFIG-REFACTOR-5STEP / B-REVIEW-282 SCOPE-CONTRACT-CHECK / B-REVIEW-283 IMPORT-NAME-CHECKLIST / B-REVIEW-284 POWERSHELL-LONG-TASK-OUTPUT / B-REVIEW-285 RESOURCE-OVERLOAD-TOLERANCE / B-REVIEW-286 SONARQUBE-PIPELINE-CLOSED-LOOP / B-REVIEW-287 RESILIENCE-RECOVERY / B-REVIEW-288 TEST-VERIFY-TIERS / B-REVIEW-289 CROSS-FILE-REFERENCE-SYNC / B-REVIEW-290 CONFIG-ACCESS-UNIFIED-ENTRY | 42 | 280->290 | 重构安全性审查（配置化重构5步法/作用域契约/导入名称checklist/PowerShell长任务/资源过载容错/SonarQube闭环/弹性恢复/测试三档/跨文件同步/配置统一入口，2026-07-23 复盘规范集后端落地） |
| v4.51.0 | B-REVIEW-242 STEP-PROGRESS-LOG / B-REVIEW-243 TIMEOUT-ERROR-SEMANTICS / B-REVIEW-244 OVERWRITE-SET-SELECTION | 9,9,6 | 240->243 | �ಽ����ȱ����־ / ��ʱ�쳣�û��Ѻ����� / �ֶθ��Ǽ���ѡ��meta-rule #85 ��أ�2026-07-22 ������ʱ+image_urls ��� Bug ���̣� |
| v4.55.0 | B-REVIEW-245 SCHEDULER-STATE-MACHINE-RECOVERY / B-REVIEW-246 COOKIE-TOKEN-SEPARATION / B-REVIEW-247 CONFIG-FIELD-FIVE-LAYER / B-REVIEW-248 CROSS-LAYER-WRITEBACK-PROTECTION / B-REVIEW-249 RENEWAL-LOOP-WRITEBACK | 5,4,5,4,5 | 243->248 | ������״̬���ָ� / Cookie-Token ���� / �����ֶ������·���ǣ�meta-rule #86 ��أ�/ ���д�ر�������ֵ�ָ�Ĭ�ϣ�meta-rule #87 ��أ�/ ���ڱջ���д��2026-07-22 �ڶ��ָ��̣�config.yaml ��ȫ B-REVIEW-247/248 ���ýڵ㣩 |
| v4.57.0 | B-REVIEW-251 FALLBACK-PRESERVE-KEY / B-REVIEW-252 TIME-WINDOW-FULL-FALLBACK / B-REVIEW-253 POWERSHELL-EXPLICIT-SUFFIX | 11,7,12 | 250->253 | ���˹��������/ʱ�䴰�ڻ���/PowerShell �ⲿ���meta-rules #90-92 ��أ�2026-07-22 price_range ע�� Bug ���̣� |
| v4.58.0 | B-REVIEW-262 ASYNC-SYNC-DB-RUN-IN-EXECUTOR / B-REVIEW-263 BATCH-UPSERT-SINGLE-COMMIT / B-REVIEW-264 SQL-FILTER-PUSHDOWN / B-REVIEW-265 LIST-COUNT-MERGED-QUERY / B-REVIEW-266 PRIORITY-LOCK-YIELD / B-REVIEW-267 CACHE-TTL-GT-OPERATION-COST | 15,6,6,6,6,15 | 253->259 | asyncͬ��DB/run_in_executor/����upsert/SQL����/list+count�ϲ�/���ȼ���/����TTL��meta-rules #93-94 ��أ�2026-07-22 �����Ż�8�������̣� |
| v4.49.1 | B-REVIEW-229 MONKEYPATCH-FROM-IMPORT-COVERAGE / B-REVIEW-230 ASYNC-SYNC-TEST-CALL-MATCH / B-REVIEW-231 PROPERTY-RENAME-SERIALIZE-FIELD-SEP / B-REVIEW-232 FASTAPI-ENDPOINT-SIGNATURE-TEST-SYNC / B-REVIEW-233 SOFT-DELETE-CATEGORY-ISOLATION / B-REVIEW-234 ES-RESILIENCE-PRECHECK / B-REVIEW-235 PYTEST-TIMEOUT-CONFIG / B-REVIEW-236 MULTI-USER-ID-PROPAGATION | 37 | 228->236 | ����������ͬ���ԣ�monkeypatch ����/async-sync ����ƥ��/�����ع������л�����/�˵�ǩ��ͬ��/��ɾ������/ES ����Ԥ��/pytest ��ʱ/���û� user_id ͸���� |
| v4.48.0 | B-REVIEW-226 ASYNC-BLOCKING-CALL-TIMEOUT / B-REVIEW-227 SUBPROCESS-HEARTBEAT-STAGE-COORDINATION / B-REVIEW-228 CROSS-BLOCK-CONSISTENCY-CHECK | 35 | 225->228 | async �������ó�ʱ���� / �ӽ���������׶γ�ʱЭͬ / ������һ���Լ�飨meta-rules #80/#81/#82�� |
| v4.40.0 | B-REVIEW-189 | 13 | 188�?89 | 新增 B-REVIEW-189 业务异常状态码冲突检查（meta-rule #66）；关注同一状态码跨层语义冲突，与 B-REVIEW-184「多原因 None �?状态码映射」互补；新增 config.yaml `status_code_audit` 配置块（layers/reserved_for_middleware/forbidden_business_codes/consistency_rules/detection_patterns�?|
| v4.41.0 | B-REVIEW-195 PRESET-APIKEY-SLOT-ISOLATION / B-REVIEW-196 MIGRATION-FIRST-TIME / B-REVIEW-197 EMPTY-OVERRIDES-LEGACY / B-REVIEW-198 MUTATION-RESPONSE-ECHO / B-REVIEW-202 PRESET-ID-LITERAL | 9,9,9,10,9 | 189->199 | Per-preset credential isolation / migration / empty override / mutation echo / literal IDs |
| v4.44.0 | B-REVIEW-203 MODEL-NAME-OFFICIAL-ACCURACY / B-REVIEW-204 CAPABILITY-CHECK-SHARED / B-REVIEW-205 MODEL-LITERAL-TYPE / B-REVIEW-206 CONFIG-PERSIST-ENV-UPDATE / B-REVIEW-207 MASKED-KEY-RETURN / B-REVIEW-208 KEY-RING-INDEPENDENT | 11,11,11,10,10,10 | 199->205 | Model name accuracy / shared check / Literal type / env persist / masked echo / key ring isolation (dims 9-11) |`n| v4.45.0 | B-REVIEW-209 COOKIE-ISOLATION-USERID-PROPAGATION / B-REVIEW-210 LIVE-SEARCH-COOKIE-HEALTHCHECK / B-REVIEW-211 CACHE_INVALIDATION_BEFORE_READ / B-REVIEW-212 COOKIE-INJECTION-VERIFY / B-REVIEW-213 M5TK-REFRESH-ISOLATION / B-REVIEW-214 COOKIE-LAYER-SYNC-INVALIDATE / B-REVIEW-215 TEST-COOKIE-FILTER-BEFORE-INJECT / B-REVIEW-216 USER-ID-VALIDATION-BEFORE-PATH / B-REVIEW-217 BACKWARD-COMPAT-DEFAULT | 10,10,10,10,10,10,10,10,10 | 205->217 | Multi-user cookie isolation / user_id propagation / cache invalidation / injection verification / M5TK isolation / layer sync / test filter / path safety / backward compat (dim 12) |
| v4.46.0 | B-REVIEW-MULTI-LEVEL-HEALING / B-REVIEW-CIRCUIT-BREAKER-RETRY / B-REVIEW-DIAGNOSTIC-LOGGING / B-REVIEW-PRE-CHECK-BATCH | 4 | 221->225 | Cookie self-healing: multi-level healing / circuit breaker retry coordination / diagnostic logging / batch pre-check (dim 15) |
| v4.49.0 | B-REVIEW-218 BACKEND-LOGIC-CHANGE-TRIGGERS-FRONTDOC / B-REVIEW-219 PRICE-RANGE-SCORING-CONFIGURABLE / B-REVIEW-220 FALLBACK-COMPATIBLE-INTERFACE / B-REVIEW-221 CONFLICT-RESOLUTION-HELPER-PRIORITY | 10,10,10,10 | 217->221 | Frontend doc sync / configurable price scoring / backward compat / merge conflict priority (dims 10) |
| v4.39.0 | �?| �?| 188�?88 | meta-rules #64/#65 前端侧同步（后端无新增） |
| v4.38.0 | B-REVIEW-182~188 | 9,11,13,14 | 181�?88 | meta-rules #57-#63（async/await/资源�?HTTP映射/CSS降级/异常日志/外部资源/DB身份�?|
| v4.37.0 | B-REVIEW-178~181 | 9 | 177�?81 | meta-rules #48-#51 调度器运行时治理（toggle/时间参数/资源清理/cron间隔�?|
| v4.35.0 | B-REVIEW-173~177 | 36 | 172�?77 | meta-rules #43-#47 跨层契约与测试同�?|
| v4.34.0 | B-REVIEW-164~168 | �?| 163�?68 | meta-rules #38-42 列表聚合与状态联�?|
| v4.31.0 | B-REVIEW-159~161 | 32,33,34 | 163�?66 | meta-rules #33-35 注册�?endpoint/根因扫描/字段契约 |
| v4.31.0 | 5 项（业务关键字等�?| 30 | 166�?66 | 业务关键字集中管�?事件精确匹配/字段大小�?重启验证/Windows编码 |
| v4.30.0 | B-REVIEW-157~158 | 32 | 161�?63 | meta-rules #31-32 状态恢复前置校�?降级链日志合�?|
| v4.29.0 | B-REVIEW-151~156 | �?| 155�?61 | meta-rules #25-30 数据契约与时序（断路�?traceback/datetime/状态同�?error_code/关键字） |
| v4.28.0 | B-REVIEW-121~150 | 6,7,9,11,13,14,18,19,20 | 125�?55 | 全量复盘 80+ topics�?0 项检查点�? 阶段流水线） |
| v4.28.0 | 5 项（多用户隔离等�?| 21 | 120�?25 | 多用户资源隔�?认证多路校验/会话token/快照覆盖/身份优先�?|
| v4.27.0 | 6 项（失败原因链等�?| 29 | 114�?20 | 端到端失败原因链与数据完整性闭�?|
| v4.26.0 | 3 项（三态语义等�?| 6,9,19 | 111�?14 | API三态语�?NOT NULL防御/共享单例污染 |
| v4.25.0 | 2 项（迁移块等�?| 6,11 | 109�?11 | 数据库迁移块独立容错/关键路径异常可见�?|
| v4.24.0 | �?| �?| 109�?09 | 用户偏好 UI 状态持久化（后端同步原则，无新增） |
| v4.23.0 | 3 项（能力派发等） | 28 | 106�?09 | LLM 能力驱动派发/共享工具函数/静默降级预检 |
| v4.22.0 | 4 项（启动钩子等） | 6,9 | 102�?06 | 启动钩子完整�?任务历史三层保护/计数器DB MAX/interval首次执行 |
| v4.20.0 | 1 项（版本源） | 14 | 101�?02 | 版本号源管理（B-REVIEW-VERSION-SOURCE-SINGLE�?|
| v4.19.0 | 3 项（DOM选择器等�?| 9,11,13 | 98�?01 | DOM 选择器同�?外部文案集中管理/调度器启动可见�?|
| v4.16.0 | 2 项（字段归一化等�?| 13,18 | 96�?8 | 字段归一化文档化/除零兜底禁止凑数 |
| v4.15.0 | 3 项（缓存失效等） | 6,9,14 | 93�?6 | Cookie 层状态管�?状态检�?bootstrap/迁移事务 |
| v4.14.0 | 3 项（路由拦截等） | 9,10,13 | 90�?3 | 路由拦截类型/信号层映�?DEBUG 代码清理 |
| v4.13.0 | 1 项（统计互斥�?| 19 | 89�?0 | 统计分类互斥性（B-REVIEW-STATS-EXCLUSIVE�?|
| v4.12.0 | 4 项（DOM 兜底等） | 8,9,11 | 82�?6 | DOM 兜底�?失败 dump/计时埋点/预检并行 |
| v4.11.0 | 7 项（配置校验等） | 6,7,9,11,13,14 | 75�?2 | 配置校验/迁移失败/状态码语义/LLM解析/调度器DB同步/后台监控/数值提�?|
| v4.10.0 | 4 项（过滤可见性等�?| 12,19,20 | 71�?5 | 过滤可见�?pytest 模块隔离/loguru 占位�?测试 fixture 隔离 |
| v4.9.0 | 5 项（状态机等） | 9,11,18 | 69�?4 | 双链路一致�?状态机/资源生命周期/并发安全/Python 现代�?|
| v4.8.0 | 3 项（状态标志等�?| 9,12,13 | 86�?9 | 状态标志前置检�?日志降级稳定�?修改生效验证 |
| v4.8.0 | 3 项（孤岛模块等） | 11,12,13 | 66�?9 | 频率伪装孤岛模块/时间敏感分离/辅助日志级别 |
| v4.7.0 | �?| �?| 66�?6 | AntD 主题 token（后端同步原则，无新增） |
| v4.6.0 | 4 项（异步超时等） | 6,9,13,18 | 62�?6 | 异步超时/数据流转追踪/过滤场景/复用模式 |
| v4.5.0 | 6 项（多写入入口等�?| 6,10,13,14 | 56�?2 | Cookie 分层管理（多写入/状态区�?浏览器兜�?upsert/写后钩子/死代码） |
| v4.4.0 | 5 项（错误语义等） | 5,7,9,11,14 | 51�?6 | 搜索参数链路/错误语义/快速降�?硬编码阈�?参数透传 |
| v4.3.0 | 9 项（加密降级等） | 6,7,9,11,14,15,16,20 | 42�?1 | 浏览�?Cookie 导入增强（v20 加密/�?Profile/自动同步�?|
| v4.2.0 | �?| 24 | 36�?2 | 反爬模块代码审查（跨字段一致�?硬编码属性禁用） |
| v4.1.0 | �?| 7,11 | 34�?6 | 会话失效处理（错误粒度三类区分） |
| v4.0.0 | �?| 9,13,17,19 | 24�?4 | 事件时机/字段覆盖/幂等�?搜索标准�?|
| v3.0.0 | �?| 9,13 | 14�?4 | SonarQube 规则增强（S7503/S3776/S6767/S1192/S5843�?|
| v2.1.0 | �?| 23 | 12�?4 | Git 操作规范�?git/index.lock/untrack/cherry-pick�?|
| v2.0.0 | �?| 1,4,5,6,9,10,16,17 | 0�?4 | 知识点整合（backend-guide/database-guide/chatbot-guide/project-rules�?|


## 配置驱动

**核心原则**：所有评审规则、硬约束、项目规范均通过 `config.yaml` 管理，技能本身不含任何业务参数或硬编码值。新增规则只需修改配置文件，无需改动技能本身�?

配置文件位置：`.trae/skills/xianyu-backend-code-review/config.yaml`

首次使用时，从同目录�?`config.example.yaml` 复制并按项目实际情况修改。配置项分为 10 大类�?

| 配置�?| 职责 | 关键参数 |
|--------|------|----------|
| `scope` | 评审范围 | include_paths, exclude_paths, file_extensions, max_files_per_run |
| `priority` | 优先级排�?| severity_order, category_order, report_threshold |
| `hard_constraints` | 硬约束规�?| rules（可扩展列表，每条含 name/pattern/message/severity/auto_fix�?|
| `checklist` | 评审检查清�?| 35 大类开�?|
| `report` | 报告生成 | output_dir, format, include_good_practices, max_suggestions |
| `verify` | 验证配置 | run_tests_after_review, test_command, fail_on_critical |
| `project_conventions` | 项目专属规范参�?| auth_whitelist, required_indexes, webview2_config, kb_index, hf_endpoint |
| `meta_rules_33_35` | 🆕v4.31 注册�?根因扫描/字段契约配置节点 | backend_registration_endpoint / root_cause_chain_check / contract_owner_marker |
| `meta_rules_governance` | 🆕v4.33 规范治理配置节点 | sedimentation_threshold / degradation_threshold / observation_period_quarters / sedimentation_exemption_categories / degradation_exemption_categories |
| `meta_rules_38_42` | 🆕v4.34 列表聚合与状态联动配置节�?| global_aggregate_filter / cross_domain_inject / linked_switch_priority / precheck_structured_fields / config_fallback_defaults |
| `refactoring_safety` | 🆕v4.61 重构安全性配置节点 | refactor_5step / scope_contract / import_name_change / long_task_output / resource_overload_tolerance / sonarqube_pipeline / resilience_recovery / test_verify_tiers / cross_file_sync / config_access_unified |

## 审查模式

| 模式 | 扫描范围 | 触发 |
|------|---------|------|
| 快速自检 | 仅阻塞级 | `pwsh .trae/skills/xianyu-backend-code-review/scripts/auto-scan.ps1` |
| 增量审查 | `git diff --name-only` 变更文件 | 粘贴变更文件列表 |
| 指定文件审查 | 用户明确列出的文�?| 用户指定路径 |
| 片段评审 | 用户粘贴代码片段 | 无文件路径时仅输出建�?|
| 全量审查 | `src/xianyu_hunter/**/*.py` | 默认 |

---

## 审查规则�?0 项维度）

### 1. 分层架构 🆕v2.0

- 【强制】依赖单�?`web �?modules �?infra �?domain`，`domain` 不依赖任何层
- 【强制】`container.py` 是唯一 Composition Root，合法依赖所有层
- 【强制】路由层文件命名�?`api_<�?.py`（如 `api_tasks.py`、`api_items.py`�?
- 【强制】仓储层文件命名�?`repo_<�?.py`（Mixin 模式组合�?`repository.py`�?
- 【强制】领域模型用 `@dataclass`，Web 层用 `pydantic.BaseModel`
- 【禁止】跨层调用：路由直接访问 ORM 对象、领域包引入框架注解
- 【禁止】循环依赖：A �?B �?C �?A

**判断规则**�?
- `web/routes/` �?�?HTTP 解析与响应组装，业务逻辑下沉�?`modules/` �?`web/services/`
- `modules/` �?业务编排，可调用 `infra/` �?`domain/`
- `infra/` �?基础设施（DB、浏览器、密钥、日志），不感知业务
- `domain/` �?纯数据结�?+ Enum，无 IO 依赖

### 2. 命名规范

- 【强制】模块：snake_case（如 `price_strategy.py`�?
- 【强制】类：PascalCase（如 `TaskMode`、`Task`、`TaskRow`、`TaskCreate`�?
- 【强制】DB Row 类：`*Row` 后缀（如 `TaskRow`、`ItemRow`、`OrderRow`�?
- 【强制】配置类：`*Config` 后缀（如 `AppConfig`、`BrowserConfig`�?
- 【强制】函�?方法：snake_case（如 `build_default_container`、`list_tasks_with_last_seen`�?
- 【强制】常量：UPPER_SNAKE_CASE（如 `_IDENT_RE`、`_TASK_NOT_FOUND`�?
- 【强制】私有辅助：`_` 前缀（如 `_load_secrets_from_keyring`、`_migrate_add_column`、`_escape_like`、`_utcnow`�?
- 【推荐】文案常量提取到模块级（SonarQube S1192），�?`_TASK_NOT_FOUND = "任务不存�?`

### 3. 类型注解

- 【强制】全面使用类型注解，采用 Python 3.10+ 现代语法（`X | None` 而非 `Optional[X]`�?
- 【强制】函数签名标注参数与返回类型
- 【推荐】复杂类型用 `TypeAlias` 提升可读�?
- 【禁止】滥�?`Any`，必要时�?`Unknown` + 类型守卫
- 【强制】泛型容器标注元素类型（`dict[str, Any]` 而非 `dict`，`list[int]` 而非 `list`�?

```python
# �?推荐：Python 3.10+ 现代语法
@dataclass
class Task:
    search_config: dict[str, Any] | None  # None 表示沿用全局配置
    price_config: dict[str, Any] | None
```

### 4. Pydantic 2.x 模型 🆕v2.0

- 【强制】Web 层请�?响应模型继承 `pydantic.BaseModel`
- 【强制】使�?`Field(..., min_length=N, max_length=N)` 约束
- 【强制】区�?未传"�?�?null"：用 `model_dump(exclude_unset=True)`
- 【强制】Pydantic 2.x 写法（`model_dump` / `model_validate`），禁止 Pydantic 1.x �?`.dict()` / `.json()`
- 【推荐】响应模型显式声�?`response_model`，避免返�?`dict | JSONResponse` 联合类型（兼容性需设为 `None`�?
- 【强制】领域模型用 `@dataclass`�?*�?*�?Pydantic

```python
# �?推荐：Pydantic 2.x 风格
class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    search_config: dict[str, Any] | None = None

data = task_create.model_dump(exclude_unset=True)
```

### 5. SQLAlchemy 2.0 规范 🆕v2.0

- 【强制】使�?DeclarativeBase + `Mapped` + `mapped_column` 风格（禁�?1.x �?`Column(Integer)` 风格�?
- 【强制】所有时间字段统一 UTC，用 `_utcnow = lambda: datetime.now(timezone.utc)`（禁止已弃用�?`datetime.utcnow()`�?
- 【强制】所�?schema 变更必须**幂等**：`_migrate_add_column`、`_migrate_create_index`（`IF NOT EXISTS`）、`_migrate_make_column_nullable`（SQLite 表重建）
- 【强制】SQL 注入防护�?
  - LIKE 查询必须�?`_escape_like()` 转义 `%` �?`_`
  - 表名/列名�?`_IDENT_RE = re.compile(r'^[A-Za-z_]\w*$', re.ASCII)` 白名单校�?
  - 用户 ID �?`_USER_ID_RE`（`^[A-Za-z0-9_-]+$`）校验，防路径遍�?
- 【推荐】UPSERT �?`sqlite_insert(...).on_conflict_do_update(index_elements=[...], set_=...)`
- 【推荐】软删除�?SQL 层过滤（避免 limit/offset 截断�?

```python
# �?推荐：SQLAlchemy 2.0 风格
class Base(DeclarativeBase): ...

class TaskRow(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
```
- 🆕v4.4【强制�?*B-REVIEW-PARAM-PASS-THROUGH：参数透传链路完整�?*
  - 方法签名新增参数时，必须同步更新所有内部调用点传递该参数�?*禁止**只在外层方法签名添加而内部调用点遗漏
  - **判断信号**：`git diff` 显示方法签名新增参数 �?必须 grep 方法名检查所有调用点（包括内�?`_private` 方法的调用）是否传递新参数
  - **检查方�?*：从方法签名 �?内部调用 `_call_xxx(new_param=new_param)` �?内部调用 `build_url(new_param=new_param)` �?最�?URL 查询参数追加，逐层验证
  - **配置参数**：无（纯代码审查检查项�?
  - **适用**：方法签名新增参数后的所有内部调用点，尤其是跨层参数传递（API �?Module �?Domain �?URL Builder�?
  - **不适用**：向后兼容的可选参数（有默认值且不影响现有行为）
  - **历史教训**：`search()` 方法新增 `sort_type`/`regions` 参数后，`_call_search_api()` 内部 `build_search_url(keyword)` 未传这两个参数，导致 RGV587 重试�?URL 中丢失排序和地区参数

### 6. SQLite 优化与索引规�?🆕v2.0

- 【强制】引擎创建必须配置：
  - `poolclass=NullPool`（避免跨线程 cursor 竞争�?*禁止** StaticPool�?
  - `connect_args={"timeout": 10, "check_same_thread": False}`
  - `PRAGMA journal_mode=WAL`
  - `PRAGMA busy_timeout=10000`
  - `PRAGMA cache_size=-20000`
- 【强制】以下字段必须建索引：`task_id`、`seller_id`、`first_seen`、`publish_time`、`created_at`、`request_id`
- 【强制】必须建立复合索引以优化 Dashboard 查询
- 【强制】`_overview()` 中的 COUNT 查询必须�?`CASE WHEN` 聚合合并，减�?DB 调用 67%
- 【强制】函数内冗余导入必须移至模块级别
- 【推荐】批量操作用 `session.bulk_insert_mappings` / `session.bulk_update_mappings`
- 【推荐】大结果集用 `yield_per(N)` 流式加载，禁止全表加载到内存
- 【强制�?*索引一致性双�?*：ORM `__table_args__` 中的 `Index(...)` 必须�?`init_db()` 中的 `_migrate_create_index(...)` 双向同步
  - ORM 有定义但 init_db 无迁移调�?�?已有数据库缺失索引（全表扫描�?
  - init_db 有迁移调用但 ORM 无定�?�?新建数据库缺失索�?
  - 两者索引名必须一�?
- 【强制】复合索引按"过滤�?+ 排序�?顺序设计：`(task_id, link_type, created_at)` 而非 `(created_at, task_id, link_type)`
- 🆕v4.3【强制�?*B-REVIEW-FILE-LOCK-BYPASS：文件锁绕过模式（SQLite immutable�?*
  - 并发访问被锁文件时，使用 SQLite URI `immutable=1` 参数打开只读数据库，绕过 Windows 文件锁机�?
  - **判断信号**：Windows 文件锁报错（`database is locked` / `unable to open database`�? 只读访问需�?+ SQLite 数据�?
  - **修复模式**：构�?URI `file:./Cookies?immutable=1` �?�?`sqlite3.connect(uri=True)` 打开 �?仅执�?SELECT 查询
  - **配置参数**：`immutable_flag` 默认 `true`，`lock_timeout_ms` �?`config.yaml` �?`sqlite_file_lock` 节点管理
  - **适用**：浏览器 cookie 数据库并发访问、Windows 文件锁定机制、需要只读访问的共享资源
  - **不适用**：需要写入的场景、Linux 文件锁（建议�?`flock`）、原子写场景
  - **历史教训**：浏览器运行时持�?`Cookies` 数据库写锁，传统 `sqlite3.connect()` 打开失败，改�?`immutable=1` 后可并发读取
- 🆕v4.5【强制�?*B-REVIEW-UPDATE-VS-UPSERT：Update vs Upsert 语义区分**
  - 持久化层（CookieStore / Repository）必须明确区�?Update"�?Upsert"两类操作�?*禁止**用一个方法兼顾两种语�?
  - **判断信号**：函数命名含 `update` 但实际行为是"更新或新�?，或反之 �?维护者无法从命名判断行为
  - **修复模式**�?
    - **`update_cookie_values(updates)`**：只更新已存在的 cookie（name �?JSON 中存�?�?替换 value；不存在 �?跳过）。用�?token 刷新场景
    - **`upsert_cookie_values(upserts)`**：更新已存在 + 添加不存在（name �?JSON 中存�?�?替换 value；不存在 �?追加新条目）。用于浏览器兜底回写场景
  - **关键约束**：upsert 必须携带完整属性（`value`/`domain`/`path`/`expires`），不能只传 value 因为新条目需要完整字�?
  - **并发安全**：读-�?写必须在 `self._lock`（`RLock`）内完成，避免与并发 `export_cookies` 交错导致数据丢失
  - **元数据保�?*：方法标签（�?`data["method"]`）必须用 `if "mtop_refresh" not in existing_method: data["method"] = existing_method + "+mtop_refresh"` 避免无限追加
  - **配置参数**：`update_methods`（只更新已存在）、`upsert_methods`（更�?添加）方法名列表�?`config.yaml` �?`persistence_semantics` 节点管理
  - **适用**：所有持久化层的数据合并操作（Cookie / 缓存 / 索引�?
  - **不适用**：纯 add-only 日志、纯 replace 全量覆盖
  - **历史教训**：MTOP 刷新 `_m_h5_tk` 时若�?`update_*` �?JSON 中没有该条目 �?静默丢失；反之若�?`upsert_*` �?JSON 中已�?�?字段被覆盖（�?`expires`）→ 下次过滤过期逻辑失效
- 🆕v4.6【强制�?*B-REVIEW-FILTER-SCENARIO：过滤逻辑场景区分**
  - 同一查询函数被多个场景复用时，过滤逻辑必须**参数化场景标�?*（如 `include_failed` / `include_deleted` / `scope`），调用方按使用场景传值，**禁止**一刀切过滤导致展示页看不到完整数�?
  - **判断信号**：函数命名含 `list_*` / `get_*` / `query_*` �?`grep` 多个调用�?�?检查过滤逻辑是否硬编码（�?`if status == 'failed': continue`）→ 必须改为参数�?
  - **修复模式**：增�?`include_failed: bool = False` 参数 �?默认安全（跳过失败数据，不影响现有逻辑）→ 调用方按场景显式传值（操作判断场景 False / 展示历史场景 True）→ 函数 docstring 说明两种场景用�?�?新增回归测试覆盖两种场景
  - **关键约束**�?
    - 场景标志必须**默认安全**（`include_failed=False` 默认跳过失败，避免影响现有逻辑�?
    - 调用方必�?*显式传�?*（如 `include_failed=True`），不依赖默认�?
    - 必须新增**回归测试**覆盖两种场景
  - **配置参数**：`scenario_flag_field`（默�?`include_failed`）、`status_whitelist`（默�?`['succeeded', 'pending']`）、`multi_scene_callsites`（多场景调用点列表）�?`config.yaml` �?`filter_scenario` 节点管理
  - **适用**：同一查询�?操作判断"�?展示历史"两种场景复用，尤其是订单/任务/日志类查�?
  - **不适用**：单一场景的查询（如报表统计只看成功）、有独立 Repo 方法的查询、权限过滤（应单独抽取）
  - **历史教训**：`list_orders_by_item_ids` 无条�?`if status == 'failed': continue`，导致评估明细页看不到失败订单记录，用户点击抢单失败后刷新页面看�?"�?，误以为没下过单而反复触发抢单。修复后增加 `include_failed` 参数，评估明细调用传 `True`
- 🆕v4.11【强制�?*B-REVIEW-MIGRATION-FAILURE-HANDLING：DB 迁移失败处理**
  - `_migrate_*` 函数失败必须明确处理策略：关键迁移（schema 变更/列类型修改）失败 `raise RuntimeError` 中断启动；非关键迁移（索引补�?数据回填）失�?`logger.warning` + 继续启动�?*禁止** `except: pass` 静默吞掉
  - **核心机制**（审查时必须理解）：
    - 关键迁移失败会导致后续代码访问不存在的列/表，应立即中断启动而非带病运行
    - 非关键迁移失败（如索引补建）不影响功能，仅影响性能，应记录日志后继续启�?
    - `except: pass` 会吞掉所有异常（包括 KeyError、AttributeError 等编程错误），导致问题隐�?
    - 幂等性检查（�?"duplicate column" 错误）应识别并跳过，不视为失�?
  - **判断信号**�?
    - 代码�?`def _migrate_*` 函数 + `try/except` �?�?except 块必须明确记录日志或抛出，禁�?`pass`
    - 代码�?`except: pass` �?`except Exception: pass` �?`_migrate_*` 函数�?�?视为违规
    - 代码�?`except Exception as e: logger.debug(...)` �?`_migrate_*` 函数�?�?视为违规（debug 默认不输出）
  - **修复模式**�?
    ```python
    # �?关键迁移：失败必须中�?
    def _migrate_add_column(conn, table: str, column: str, sql_type: str) -> None:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                return  # 幂等，已存在则跳�?
            raise RuntimeError(f"关键迁移失败 {table}.{column}: {e}") from e

    # �?非关键迁移：失败 warning + 继续
    def _migrate_create_index(conn, name: str, table: str, columns: list[str]) -> None:
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({', '.join(columns)})")
        except Exception as e:
            logger.warning("非关键索引迁移失�?{}：{}（不影响启动�?, name, e)

    # 禁止：silent pass 吞掉所有异�?
    ```
  - **配置参数**：`migration_failure_strategy.critical_migrations`（关键迁移函数名列表，如 `["_migrate_add_column", "_migrate_make_column_nullable"]`，失�?raise）、`migration_failure_strategy.non_critical_migrations`（非关键迁移函数名列表，�?`["_migrate_create_index", "_migrate_backfill_data"]`，失�?warn）、`migration_failure_strategy.default_strategy`（默�?`warn`，可�?`raise`）在 `config.yaml` �?`migration_failure_strategy` 节点管理
  - **适用**：所�?`_migrate_*` 函数（_migrate_add_column / _migrate_create_index / _migrate_make_column_nullable / _migrate_backfill_data）；数据�?schema 变更
  - **不适用**：迁移幂等性检查（已通过"duplicate column"等错误识别处理）；测试代码中的迁移；运行时数据修复（非迁移）
  - **历史教训**：`_migrate_create_index` 失败�?`except: pass` 吞掉，生产数据库索引长期缺失导致 Dashboard 查询�?10 倍，但日志无任何记录
- 🆕v4.25【强制�?*B-REVIEW-MIGRATION-BLOCK-ISOLATION：迁移块独立容错**
  - 迁移函数（如 `run_migrations`）内含多个独立迁移块（如 C-01 task_links 重建 / C-02 orders.task_id 添加�?/ C-03/C-04/C-05 等）时，**每个迁移块必须各�?try/except**，禁止外层统一 try/except 吞掉异常导致后续迁移块全部跳�?
  - **核心机制**（审查时必须理解）：
    - 迁移块之间通常�?*逻辑独立**的（C-01 重建 task_links 表与 C-04 添加 notifications.read_at 列无依赖关系），一个块失败不应影响其他�?
    - 外层统一 try/except 会让第一个失败的块中断所有后续迁移，导致数据�?schema �?ORM 不一致，运行�?INSERT/SELECT 才报 "no such column"
    - 外层 try/except 还会**吞掉异常**（仅记录 warning），使问题隐藏在日志中难以发�?
    - **强依赖场�?*允许合并：如 C-01 task_links 表重�?+ 历史数据回填必须在同一事务内完成（回填依赖表存在），此时可合并为一�?try/except
  - **判断信号**�?
    - 代码�?`def run_migrations` / `def _migrate_*` 函数 + 内含多个 `# C-01` / `# C-02` 注释�?�?检查每个块是否各自 try/except
    - 代码含外�?`try: ... except Exception as e: logger.warning(f"启动迁移钩子失败: {e}")` 包裹多个迁移�?�?视为违规
    - 代码�?`auto_migrate_task_links()` 等可能抛异常的调�?+ 后续迁移块在同一 try �?�?视为违规
  - **修复模式**�?
    ```python
    # �?每个迁移块各�?try/except
    def run_migrations(container: Any) -> None:
        insp = sa_inspect(container.repo.engine)
        # C-01: task_links 表重�?+ 历史数据回填（强依赖，合并为一�?try�?
        try:
            _rebuild_task_links_table(insp, container)
            inserted = container.repo.auto_migrate_task_links()
            logger.info(f"task_links auto-migrate: 新增 {inserted} �?)
        except Exception as e:
            logger.warning(f"C-01 task_links 迁移失败（忽略，不影响后续迁移）: {e}")

        # C-02: orders.task_id 列添加（独立�?
        try:
            _ensure_orders_task_id_column(insp, container)
        except Exception as e:
            logger.warning(f"C-02 orders.task_id 迁移失败（忽略）: {e}")

        # C-03/C-04/C-05 同样各自独立 try/except...

    # 禁止：外层统一 try/except 吞掉异常
    ```
  - **关键约束**�?
    - 迁移块边界标识符（如 `C-01`/`C-02` 注释）应�?`config.yaml` �?`migration_block_isolation.block_markers` 管理，便于自动化扫描识别块边�?
    - 强依赖场景（如表重建 + 数据回填）允许合并为一�?try/except，但必须在注释中说明合并原因
    - 每个块的 except 必须�?`logger.warning` �?`logger.exception` 记录（与 B-REVIEW-MIGRATION-FAILURE-HANDLING 一致），禁�?`except: pass`
    - �?B-REVIEW-CRITICAL-PATH-NO-SWALLOW 联动：外层启动钩子的 except 必须�?`logger.exception()` 输出完整 traceback
  - **配置参数**：`migration_block_isolation.function_patterns`（迁移函数名模式，如 `["run_migrations", "_migrate_*"]`）、`migration_block_isolation.block_markers`（块边界标识符，�?`["C-01", "C-02", "C-03", "C-04", "C-05"]`）、`migration_block_isolation.require_independent_try`（是否要求各�?try/except，默�?`true`）、`migration_block_isolation.allow_merge_when_dependent`（强依赖时允许合并，默认 `true`）、`migration_block_isolation.violation_message`（违规提示模板）�?`config.yaml` �?`migration_block_isolation` 节点管理
  - **适用**：含多个独立迁移块的迁移函数（`run_migrations` / `_migrate_all_*`）；数据�?schema 增量迁移；启动时的初始化迁移
  - **不适用**：单一迁移块（无独立性问题）；强依赖的迁移步骤（如表重建 + 数据回填，允许合并）；事务内 DDL（由 B-REVIEW-MIGRATION-TRANSACTION 管控�?
  - **历史教训**：`run_migrations()` �?C-01 步骤 `auto_migrate_task_links()` 抛异常，外层 `_on_startup` �?`try/except` 吞掉异常，导�?C-04（添�?`notifications.read_at` 列）被跳过。运行时 `add_notification` �?UPSERT INSERT �?`sqlite3.OperationalError: no such column: notifications.read_at`。修复后改为每个迁移块各�?try/except，问题彻底解�?
- 🆕v4.25【强制�?*B-REVIEW-111: NOT-NULL-NONE-DEFENSE：NOT NULL 字段 None 防御检�?*
  - NOT NULL 字段收到 null 时必�?*防御�?pop**（从 update_data 中移除）�?*禁止**直接写入 DB 触发 `IntegrityError`；覆盖字段收�?null 表示"清除覆盖"应正常写�?None
  - **核心机制**（审查时必须理解）：
    - NOT NULL 字段（如 `task_id`/`seller_id`/`created_at`）传 null 是非法操作，�?pop 后记�?WARNING 日志
    - 覆盖字段（如 `price_config`/`score_config` �?nullable 字段）传 null 是合法的"清除覆盖"语义，应正常写入 None
    - 必须区分"NOT NULL 约束字段"�?可空覆盖字段"�?*不能**一刀�?pop 所�?None
  - **判断信号**�?
    - 更新逻辑中出�?`await session.execute(update(Task).where(...).values(**update_data))` 但未检�?NOT NULL 字段是否�?None �?视为违规
    - 对所�?None 字段一刀�?`update_data.pop(k)` 导致覆盖字段无法清除 �?视为违规
    - NOT NULL 字段�?null 触发 `sqlite3.IntegrityError: NOT NULL constraint failed` �?视为违规
    - 代码中出�?`try: await session.commit() except IntegrityError: pass` 吞掉 NOT NULL 错误 �?视为违规
  - **修复模式**�?
    ```python
    # �?区分 NOT NULL 字段与覆盖字�?
    _NOT_NULL_FIELDS = {"task_id", "seller_id", "created_at", "updated_at"}  # �?schema 定义读取

    async def update_task(task_id: str, update_data: dict):
        # NOT NULL 字段�?null �?防御�?pop + WARNING
        for field in list(update_data.keys()):
            if field in _NOT_NULL_FIELDS and update_data[field] is None:
                logger.warning(f"NOT NULL 字段 {field} 收到 null，已跳过更新 (task_id={task_id})")
                update_data.pop(field)
        # 覆盖字段（nullable）传 null �?正常写入 None（表示清除覆盖）
        await session.execute(update(Task).where(Task.id == task_id).values(**update_data))
        await session.commit()

    # 禁止：直接写入触�?IntegrityError
    async def update_task(task_id: str, update_data: dict):
        await session.execute(update(Task).where(Task.id == task_id).values(**update_data))
        # �?update_data �?task_id=None �?IntegrityError

    # 禁止：一刀�?pop 所�?None，覆盖字段无法清�?
    async def update_task(task_id: str, update_data: dict):
        for k in list(update_data.keys()):
            if update_data[k] is None:
                update_data.pop(k)  # price_config=None 也被 pop，无法清除覆�?
    ```
  - **关键约束**�?
    - 必须�?ORM 模型 / DB schema 读取 NOT NULL 字段列表�?*禁止**硬编�?
    - NOT NULL 字段�?null �?pop + `logger.warning`（含字段�?+ 主键�?
    - 覆盖字段（nullable）传 null 时正常写�?None
    - **禁止**�?`except IntegrityError: pass` 吞掉 NOT NULL 错误
    - 配合 B-REVIEW-110 EXCLUDE-UNSET-CHECK：先 `model_dump(exclude_unset=True)` �?NOT NULL 防御
  - **配置参数**：`api_update_semantics.not_null_fields`（NOT NULL 字段列表，从 ORM 模型自动读取或显式配置）、`api_update_semantics.nullable_override_fields`（可空覆盖字段列表）、`api_update_semantics.require_warning_on_null_pop`（默�?`true`，NOT NULL 字段�?pop 时必须记�?WARNING）在 `config.yaml` �?`api_update_semantics` 节点管理
  - **适用**：所有含 NOT NULL 约束字段的更新接口；任务级配置覆盖功能；支持"�?null 清除覆盖"语义的接�?
  - **不适用**：POST 创建接口（创建时 NOT NULL 字段缺失应被 Pydantic 校验拦截）；�?NOT NULL 约束的表；纯查询接口
  - **历史教训**：任务级配置覆盖功能中，`update_data = body.model_dump(exclude_unset=True)` 后直�?`session.execute(update(...).values(**update_data))`，但用户�?`{"task_id": null}`（误操作）触�?`IntegrityError: NOT NULL constraint failed: tasks.task_id`，导致整个更新事务回滚，合法�?`price_config=null`（清除覆盖）也未生效。修复后增加 NOT NULL 字段防御�?pop + WARNING 日志

### 7. 安全性评�?

- 【强制】凭据比较必须使�?`hmac.compare_digest()` 防止时序攻击�?*禁止** `==`�?
- 【强制】敏感字段（token 长度、密码）避免写入日志，仅记录布尔匹配结果
- 【强制】Token 写入失败必须触发 `logging.warning()` 告警
- 【强制�?01 响应必须返回 JSON `{"detail": "Unauthorized"}`（禁止纯文本�?
- 【强制】认证白名单端点完整配置（见 `project_conventions.auth_whitelist`�?
- 【强制】禁止硬编码凭据（密码、token、API key、钉钉推�?Key�?
- 【强制】敏感字段（推�?Key 等）写入 keyring（Windows DPAPI），**�?*写入 `.env` �?`config.yaml` 明文
- 【强制】SQL 注入防护（见维度 5�?
- 【强制】智能客服用户输入必须经 `check_user_input_safety()` 检�?Prompt Injection
- 【强制】命令注入防护：`subprocess` 参数用列表形式，禁止 shell=True 拼接用户输入
- 【强制】Chrome Cookie 解密�?`cryptography` AES-256-GCM�?9.0.0+�?
- 【推荐】CORS 配置收紧 origin，禁�?`*`
- 🆕v4.1【强制�?*B-REVIEW-COOKIE-CHECK：Cookie 检查全面�?*：依赖多�?Cookie 的接口前置检查必须覆�?*所�?*关键 token
  - 检查清单：身份 Cookie（如 `cookie2`/`sgcookie`/`unb`�? 会话 token（如 `_m_h5_tk`），清单�?`config.yaml` �?`cookie_check_lists` 节点管理
  - **禁止**只检查身�?Cookie 存在性而忽略会�?token 有效�?
  - 失效处理：抛 `HTTPException(401)` + 明确指引（如"会话 token 已过期，请重新登�?�?
  - **判断信号**：接口含 `_ensure_*_cookies` 或前�?Cookie 检查函�?�?必须覆盖会话 token
  - **历史教训**：`_ensure_live_search_cookies` 只检查身�?Cookie 存在性，`_m_h5_tk` 已过期但检查通过，导致搜索失败但前端无明确提�?
- 🆕v4.3【强制�?*B-REVIEW-ENCRYPTION-DEGRADATION：加密升级退化策略模�?*
  - 依赖外部进程/资源的加密机制（�?Chrome v20 App-Bound Encryption）无法离线解密时，必须选择运行时接管（CDP/IPC）而非等待离线解密方案
  - **判断信号**：加密依赖外部进程状�?+ IElevator/COM 接口 + 本地密钥不可访问 + 文档标注"App-Bound"
  - **修复模式**：检测到 v20 加密 �?探测 CDP 端点可达�?�?`Playwright.connect_over_cdp()` 接管运行中浏览器 �?通过 `Network.getAllCookies` 获取解密�?cookie
  - **配置参数**：加密方案识别标志、CDP 端口、降级方案优先级�?`config.yaml` �?`encryption_solutions` 节点管理（不硬编码）
  - **适用**：依赖外部进程的加密（Chrome v20）、DRM 保护机制、需要在线状态验证的场景
  - **不适用**：可离线解密的加密（v10 AES）、依赖本地密钥的对称加密、静态资源处�?
  - **历史教训**：v20 App-Bound Encryption 无法�?`CryptUnprotectData` 离线解密，调研后选择 CDP 接管方案而非 IElevator COM 或智能降�?
- 🆕v4.4【强制�?*B-REVIEW-ERROR-SEMANTICS：错误提示语义准确�?*
  - 面向用户的错误提示必须与实际错误原因语义匹配�?*禁止**将特定错误码映射为不相关的语�?
  - **判断信号**：后端将特定错误码（�?RGV587）映射为 HTTP 状态码时，状态码语义必须与错误码根因一�?
  - **修复模式**：错误码根因分析 �?选择语义匹配的状态码 �?提示文案与根因一�?�?提供正确的操作出口（"稍后重试" vs "重新登录"�?
  - **配置参数**：错误码到状态码的映射、提示文案模板在 `config.yaml` �?`error_code_mappings` 节点管理（不硬编码）
  - **适用**：所有面向用户的错误提示（API 响应 detail、SSE error 事件�?
  - **不适用**：内部调试日志、堆栈跟�?
  - **历史教训**：RGV587 �?mtop API �?`_m_h5_tk` 临时 token 过期（TTL 1 小时），不是浏览�?Cookie/登录态失效，但后端映射为 HTTP 401("闲鱼登录已过�?)，前端显�?Cookie 失效或会话过�?。实际多查几次能成功——说明不是登录态失�?
- 🆕v4.11【强制�?*B-REVIEW-STATUS-CODE-SEMANTICS：状态码语义精细�?*
  - HTTP 状态码必须按语义精细化区分：`401` 未登�?/ `403` 权限不足 / `440` Cookie 过期（需重新登录�? `441` Token 过期（需刷新�? `504` 网关超时�?*禁止**所有认证失败都映射�?`401` 导致前端无法区分"未登�?�?登录态过�?
  - **核心机制**（审查时必须理解）：
    - `401 Unauthorized`：完全未登录，前端应跳转登录�?
    - `403 Forbidden`：已登录但无权限，前端应提示"权限不足"
    - `440 Login Timeout`（非标准但广泛使用）：Cookie 过期，前端应跳转重新登录页（区别�?401�?
    - `441 Token Expired`（项目自定义）：临时 Token（如 `_m_h5_tk`）过期，前端应静默刷�?Token 后重�?
    - `504 Gateway Timeout`：网关超时，前端应提�?稍后重试"
    - 所有认证失败都映射�?401 会导致前端无法区分应"跳转登录�?还是"刷新 Token"
  - **判断信号**�?
    - 代码�?`raise HTTPException(status_code=401)` 出现�?Cookie 检�?/ Token 刷新 / 登录校验等多�?�?必须按语义区分状态码
    - 代码�?`if is_cookie_expired(): raise HTTPException(401, "Cookie 过期")` �?应改�?`raise HTTPException(440, ...)`
    - 代码�?`if is_m5tk_expired(): raise HTTPException(401, "Token 过期")` �?应改�?`raise HTTPException(441, ...)`
    - 前端代码�?`if (status === 401) redirect("/login")` 但实际可能是 Cookie 过期 �?需按状态码区分跳转
  - **修复模式**�?
    ```python
    # �?按语义区分状态码
    if not identity_cookies:
        raise HTTPException(401, "未登录，请先登录")  # 完全未登�?
    if is_cookie_expired(identity_cookies):
        raise HTTPException(440, "Cookie 已过期，请重新登�?)  # 登录态过�?
    if is_m5tk_expired(session_cookies):
        raise HTTPException(441, "会话 Token 已过期，请刷�?)  # 临时 token 过期
    if not has_permission(user, action):
        raise HTTPException(403, "权限不足")  # 已登录但无权�?

    # 禁止：所有认证失败都映射�?401
    ```
  - **配置参数**：`status_code_semantics.mapping`（错误场景到状态码的映射，�?`cookie_expired �?440`、`token_expired �?441`、`not_logged_in �?401`、`permission_denied �?403`、`gateway_timeout �?504`）、`status_code_semantics.frontend_actions`（状态码到前端动作的映射，如 `401 �?redirect_login`、`440 �?redirect_relogin`、`441 �?refresh_token`、`504 �?retry_later`）在 `config.yaml` �?`status_code_semantics` 节点管理
  - **适用**：所有认证相�?API（登�?Cookie 校验/Token 刷新/权限检查）；SSE error 事件的状态码字段
  - **不适用**：业务错误（�?404 资源不存在�?09 状态冲突�?22 参数校验失败）；纯内�?API；健康检查端�?
  - **历史教训**：Cookie 过期、Token 过期、未登录全部映射�?`401`，前端无法区分应"跳转登录�?还是"刷新 Token"，导致用户反复被踢出登录

### 8. 性能评审

- 【强制】N+1 查询检测（循环内查询数据库�?
- 【强制】批量操作用批量接口（如批量 embedding、`bulk_insert_mappings`�?
- 【强制】异步端点必须用 `asyncio.to_thread` 包装同步阻塞操作（如 SQLite 同步仓储�?async 路由中调用）
- 【禁止】async 代码中调用阻�?IO（如 `requests.get`、`time.sleep`�?
- 【推荐】缓存机会识别（`@lru_cache` 配置加载、`functools.cache` 纯函数）
- 【推荐】大文件边读边处理，禁止一次�?`read()` 全部到内�?
- 【推荐】正则表达式预编译为模块�?`re.compile`，禁止循环内 `re.match`
- 【强制】关键查询方法必须有性能埋点：方法入�?`time.monotonic()`，出口计�?elapsed_ms，超过阈�?`logger.warning`（Repository �?100ms，API �?200ms�?
- 【强制】慢查询告警必须包含关键上下文：task_id、查询参数、行数、耗时
- 【推荐】`list_and_count_*` 类方法（单次查询返回列表+计数）应有埋点，替代分别调用 `list_*` + `count_*` 的模�?

### 9. 异步与调度器 🆕v2.0

- 【强制】FastAPI 路由全部 `async def`，与 ASGI 兼容
- 【强制】SQLite 仓储同步实现（避�?async 开销，单进程足够�?
- 【强制】`asyncio.Task` 必须保留引用�?GC（存�?`set` 或属性）
- 【强制】`asyncio.CancelledError` 必须�?`contextlib.suppress(asyncio.CancelledError)` 包裹 await
- 【强制�? 类调度器（APScheduler）职责清晰：
  1. 主任务调度器
  2. EventBus 后台消费�?
  3. Cookie 同步调度�?
  4. 批量采集调度�?
  5. KB 刷新调度�?
  6. 接管超时调度�?
- 【强制】`@Async`/`asyncio.create_task` 必须有异常处理（`exceptionally`/`add_done_callback`�?
- 🆕【强制�?*S7503**：不必要�?`async` 函数（无 await）——同步函数移�?`async` 关键�?
  - **实战案例**：`scheduler.start_all` �?`async def` 改为同步 `def`，避�?SonarQube 误报
  - **判断**：纯编排方法（只调用其他同步方法）应保持同步
- 【推荐】并发请求用 `asyncio.gather`，限制并发数�?`asyncio.Semaphore`
- 【禁止】在 async 函数中用 `loop.run_until_complete`（会死锁�?
- 🆕v4.0【强制�?*事件触发时机**�?已完�?语义事件（`EVAL_PASSED`/`NOTIFY_SENT`/`TASK_COMPLETED`）必须在业务逻辑**完成�?*触发
  - **禁止**：在业务逻辑前置条件变更时就触发完成事件（如 DingTalk 通知�?AI 评估前触�?EVAL_PASSED�?
  - "开�?语义事件（`TASK_STARTED`/`EVAL_STARTED`）在业务逻辑**开始前**触发
  - **判断信号**：事件名�?PASSED/SENT/COMPLETED �?后置；含 STARTED/BEGIN �?前置
- 🆕v4.3【强制�?*B-REVIEW-SCHEDULER-ISOLATION：独立调度器隔离模式**
  - 生命周期/优先级不同的后台任务必须使用独立 APScheduler `BackgroundScheduler`，避免与项目主调度器耦合
  - **判断信号**：后台任务生命周期与应用主调度器不同 + 共享状态有冲突风险 + 任务优先级不�?
  - **修复模式**：创建独�?`BackgroundScheduler()` �?独立 `add_job()` 注册 �?独立 `start()`/`shutdown()` 钩子 �?不共�?jobstore
  - **配置参数**：`scheduler_name`、`max_instances`、`coalesce`、`misfire_grace_time` �?`config.yaml` �?`isolated_schedulers` 节点管理
  - **适用**：Cookie 同步调度器、健康检查调度器、生命周期不同于主任务调度器的辅助任�?
  - **不适用**：紧耦合任务调度、共享状态访问需求、资源限制环境（内存敏感场景应合并调度器�?
  - **历史教训**：Cookie 同步任务若复用项目主任务调度器，会与采集任务的优先级产生冲突，且 shutdown 时序复杂；独立调度器后生命周期清�?
- 🆕v4.4【强制�?*B-REVIEW-NO-HARDCODED-THRESHOLD：硬编码阈值禁�?*
  - 调度�?任务循环中的阈值参数必须从配置读取�?*禁止**用硬编码常量替代已有配置�?
  - **判断信号**：代码中存在 `MAX_XXX = N` 硬编码常量，�?`config.yaml` 中已有对应的配置�?�?必须改为读取配置
  - **修复模式**：`try: from infra.yaml_config import get_config; threshold = get_config().<section>.<field> except: threshold = <default>`
  - **配置参数**：所有业务阈值的配置字段名在 `config.yaml` �?`hardcoded_threshold_checks` 节点管理
  - **适用**：所有业务阈值（失败重试次数、超时时间、间隔时间、并发数�?
  - **不适用**：语言/框架级常量（�?HTTP 200）、数学常量、协议固定�?
  - **历史教训**：Scheduler 用硬编码 `MAX_CONSECUTIVE_ERRORS = 10` 控制连续失败暂停，但 `config.yaml` �?`antidetect.fail_pause_threshold = 3`。用户设置了失败 3 次后暂停，实际要失败 10 次才暂停
- 🆕v4.6【强制�?*B-REVIEW-ASYNC-TIMEOUT：异步操作整体超时保�?*
  - 所�?`await` 调用外部资源（浏览器自动化、HTTP 客户端、IO 操作、远�?API）的异步操作，必须在**调用�?*�?`asyncio.wait_for(coro, timeout=N)` 包装整体超时，超时后返回语义化状态码（如 504 网关超时），**禁止**依赖被调用方内部 `timeout` 参数作为唯一超时保护
  - **判断信号**：代码含 `await container.<module>.<method>(...)` / `await client.<method>(...)` / `await page.<method>(...)` 调用外部资源 �?必须检查是否被 `asyncio.wait_for` 包裹；被调用方内�?`timeout` 参数不视为整体超时保�?
  - **修复模式**�?
    ```python
    try:
        detail = await asyncio.wait_for(
            container.collector.detail(item_id), timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.warning("[RefreshItem] 采集超时 item=%s�?ss），外部资源可能异常", item_id, timeout_seconds)
        raise HTTPException(status_code=504, detail="采集超时：外部资源异常或被反爬拦截，请稍后重�?)
    except Exception as e:
        logger.warning("[RefreshItem] 采集失败 item=%s: %s", item_id, e)
        raise HTTPException(status_code=502, detail=f"采集失败：{e}")
    ```
  - **关键约束**�?
    - 超时时间必须从配置读取（`config.async_timeout.<operation>_seconds`），**禁止**硬编�?
    - 超时后必须返回明确状态码�?04=超时�?02=失败�?03=稍后重试），便于前端按状态码分类处理
    - 超时日志必须记录操作类型 + 资源 ID + 超时秒数
    - `asyncio.CancelledError` 不应�?`wait_for` �?`TimeoutError` 吞掉，应单独传播
  - **配置参数**：`timeout_seconds`（默�?60）、`max_retries`（默�?0=不重试）、`status_code_mapping`（超时→504、失败→502）在 `config.yaml` �?`async_timeout` 节点管理
  - **适用**：所�?`await` 外部资源的异步操作（浏览器自动化、HTTP 请求、远�?API、IO 操作、子进程调用�?
  - **不适用**：有内建 timeout �?HTTP 客户端（`httpx.Timeout` 已配置）、纯计算函数、`asyncio.CancelledError` 传播路径、有 tenacity 等重试机制包裹的场景
  - **历史教训**：`refresh_item` 调用 `collector.detail(item_id)` 时，`page.query_selector` �?`timeout` 参数，闲鱼反�?RGV587 拦截后浏览器实例异常导致 `query_selector` 无限挂起，前�?90 秒后客户端超时无任何错误提示。修复后 `refresh_item` �?`asyncio.wait_for(..., timeout=60.0)` + 504 响应�?4.4 秒返回明确错�?
- 🆕v4.9【强制�?*B-REVIEW-RESOURCE-CLEANUP-HOOK：资源生命周�?cleanup 钩子完整�?*
  - 所有可注册的组件（Worker/Adapter/Plugin/Handler）必须实�?`cleanup()` 钩子，由调度�?容器�?`unregister` 时统一调用，确保资源释�?
  - **判断信号**：组件类有「注�?注销」生命周期（�?`scheduler.register` / `scheduler.unregister`�? 持有后台任务/连接/�?文件句柄 �?必须实现 cleanup()
  - **修复模式**�?
    - 即使当前实现为空，也必须保留 `async def cleanup(self) -> None: return None` 方法（为未来扩展预留接入点）
    - 后台 `asyncio.Task` 必须保留引用�?GC（`self._task = asyncio.create_task(...)`），禁止�?`create_task` 不持有引�?
    - 取消后台任务必须 `task.cancel()` + `await asyncio.gather(task, return_exceptions=True)`，确保资源清理完�?
    - `try/finally` 块中 `finally` 引用的变量必须在 `try` 之前初始化为 `None`
  - **配置参数**：`cleanup_method_name`（默�?`cleanup`）、`task_cancel_timeout`（默�?5s）、`required_cleanup_components`（必须实�?cleanup 的组件类型列表，�?`["TaskWorker", "Adapter", "Plugin"]`）在 `config.yaml` �?`resource_lifecycle` 节点管理
  - **适用**：可注册组件（Worker/Adapter/Plugin/Handler）、持有后台任务的组件、持有连�?�?文件句柄的组�?
  - **不适用**：纯函数（无状态无副作用）；一次性脚本（进程结束即释放）；纯数据对象（无生命周期�?
  - **历史教训**：`TaskWorker` 缺少 `cleanup()` 方法，`TaskScheduler.unregister` 时无法释�?worker 持有的资源；`_WorkerHandle` 缺少 `loop_task` 字段声明导致 `getattr` 兜底反模式。修复后 `TaskWorker` 实现 cleanup 钩子，`_WorkerHandle` 显式声明所有字�?
- 🆕v4.9【强制�?*B-REVIEW-CONCURRENT-STATE-LOCK：并发共享状态锁保护**
  - 多线�?协程访问同一共享状态（计数�?冷却时间/最后执行时间）时，「检�?更新」必须在同一锁内完成，避免竞�?
  - **判断信号**：代码含 `if self._last_run + interval < now: self._last_run = now()` 模式（检�?更新分离�? 多线�?协程访问 �?必须加锁
  - **修复模式**�?
    ```python
    # �?锁内原子检�?更新
    with self._lock:
        if h.consecutive_errors >= threshold:
            return False
        h.consecutive_errors += 1
        return True
    ```
  - **关键约束**�?
    - 锁仅保护临界区（检�?更新），**禁止**用锁保护 IO（如 `await` 网络请求），避免阻塞其他协程
    - `asyncio.Lock` 内禁�?`await` 长时间操作，必要时先释放锁再�?IO
    - 跨线程用 `threading.RLock`（可重入），跨协程用 `asyncio.Lock`�?*禁止**混用
    - Dataclass 字段必须显式声明默认值（`consecutive_errors: int = 0`），**禁止**�?`getattr(h, 'consecutive_errors', 0)` 兜底（反模式，掩盖字段未初始化的 bug）；仅在处理「外部输入的动态属性」（�?JSON 解析结果）时才允�?getattr
  - **配置参数**：`lock_type`（默�?`RLock`）、`critical_section_max_await`（默�?`0`，禁�?await）、`required_lock_fields`（必须加锁保护的字段名列表，�?`["last_run", "consecutive_errors", "cooldown_until"]`）在 `config.yaml` �?`concurrency_safety` 节点管理
  - **适用**：多线程/协程访问同一共享状态；定时任务�?API 请求并发修改同一数据
  - **不适用**：单线程顺序执行；thread-local 数据；不可变对象
  - **历史教训**：`_WorkerHandle` 缺少 `consecutive_errors` 字段声明，代码用 `getattr(h, 'consecutive_errors', 0) + 1` 兜底，掩盖了字段未初始化�?bug；并发场景下「检�?更新」未在锁内可能导致竞态。修复后显式声明字段 + 锁内原子检�?
- 🆕v4.9【强制�?*B-REVIEW-PYTHON-MODERN-ASYNCIO：Python 现代�?asyncio 用法**
  - Python 3.10+ 项目必须使用现代 asyncio API �?dataclass 语法�?*禁止**使用过时 API
  - **判断信号**：代码含 `asyncio.get_event_loop()` / `getattr(obj, 'field', default)` 兜底 dataclass 字段 / 函数�?`import asyncio` �?视为违规
  - **修复模式**�?
    ```python
    # �?现代 asyncio API
    _scheduler_task = asyncio.create_task(_scheduler_loop())  # �?
    # 禁止：loop = asyncio.get_event_loop(); loop.create_task(...)  # 过时
    # �?dataclass 字段显式声明
    @dataclass
    class _WorkerHandle:
        consecutive_errors: int = 0  # �?
    # 禁止：h.consecutive_errors = getattr(h, 'consecutive_errors', 0) + 1  # 兜底反模�?
    ```
  - **关键约束**�?
    - `asyncio.create_task(coro)` 替代 `asyncio.get_event_loop().create_task(coro)`；在协程内获取事件循环用 `asyncio.get_running_loop()`（明确表示运行中循环），**禁止** `asyncio.get_event_loop()`（Python 3.10+ 已弃用，且在无运行循环时会创建新循环导致行为不可预期�?
    - dataclass 字段必须显式声明默认值，**禁止**�?`getattr(obj, 'field', default)` 兜底未声明字段；仅在处理「外部输入的动态属性」（�?JSON 解析结果）时才允�?getattr
    - 所�?import 必须在模块顶部，**禁止**函数内重�?import（除非解决循环依赖的延迟导入�?
    - `asyncio.CancelledError` 必须�?`contextlib.suppress(asyncio.CancelledError)` 包裹 await 并向上传播，**禁止** `except: pass` 静默吞掉
    - 类型注解现代语法：`X | None` 替代 `Optional[X]`，`list[T]` 替代 `List[T]`，`dict[K, V]` 替代 `Dict[K, V]`
  - **配置参数**：`min_version`（默�?`"3.10"`）、`deprecated_apis`（禁�?API 列表：`get_event_loop`/`utcnow`/`Optional`/`List`/`Dict`）、`required_imports_at_module_level`（强制模块级导入的模块列表，�?`["asyncio", "re", "threading", "logging"]`）在 `config.yaml` �?`python_modern` 节点管理
  - **适用**：Python 3.10+ 项目；使�?asyncio 的代码；使用 dataclass 的领域模�?
  - **不适用**：Python 3.9 及以下（部分语法不支持）；同步代码（�?asyncio）；�?dataclass �?
  - **历史教训**：`startup.py` �?`asyncio.get_event_loop().create_task()` 创建后台任务（过�?API），且函数内重复 `import asyncio`；`_WorkerHandle` �?`getattr` 兜底 `consecutive_errors` 字段。修复后改为 `asyncio.create_task()` + 模块�?import + 显式字段声明
- 🆕v4.11【强制�?*B-REVIEW-SCHEDULER-DB-SYNC：调度器状态与 DB 同步**
  - 调度器内存状态变更（pause/resume/stop/error_pause）必须同步到 DB（`update_task_status`），**禁止**只在内存变更导致 API 返回的状态与实际运行状态不一�?
  - **核心机制**（审查时必须理解）：
    - 调度器内存中维护 `pause_event` / `consecutive_errors` / `_active` 等状�?
    - API 端点�?DB 读取 `task.status` 字段返回给前�?
    - 若内存状态变更不同步 DB，前端显�?运行�?但任务实际已暂停
    - 自动暂停（连续失败触发）必须同步 DB，否则用户无法感知任务已停止
  - **判断信号**�?
    - 调度器代码含 `pause_event.clear()` / `pause_event.set()` / `self._active = False` �?必须同步调用 `self._repo.update_task_status(task_id, "paused"/"running"/"stopped")`
    - 代码�?`if h.consecutive_errors >= threshold: h.pause_event.clear()` �?必须同步 `update_task_status(task_id, "paused")`
    - API 返回 `task.status == "running"` 但调度器�?`pause_event` �?clear �?状态不一�?
  - **修复模式**�?
    ```python
    # �?状态变更后同步 DB
    async def _auto_pause_on_errors(self, task_id: str, h: _WorkerHandle) -> None:
        h.pause_event.clear()
        h.consecutive_errors = 0
        # 同步 DB 状态，确保 API 返回与实际一�?
        try:
            await self._repo.update_task_status(task_id, "paused")
        except Exception as e:
            logger.warning("[Task {}] DB 状态同步失败：{}", task_id, e)

    # 禁止：只在内存变更，DB 仍为 "running"
    ```
  - **配置参数**：`scheduler_db_sync.required_transitions`（必须同�?DB 的状态转换列表，�?`["running→paused", "paused→running", "running→stopped", "running→error_paused"]`）、`scheduler_db_sync.sync_failure_strategy`（默�?`warn`，可�?`raise`）、`scheduler_db_sync.status_field`（默�?`status`）在 `config.yaml` �?`scheduler_db_sync` 节点管理
  - **适用**：所有调度器状态变更（auto_pause / manual_pause / resume / stop / unregister）；任务状态机转换
  - **不适用**：纯计算状态（�?consecutive_errors 计数器）；临时状态（�?pause_event 内部信号）；fire-and-forget 任务
  - **历史教训**：调度器连续失败触发 `pause_event.clear()` 自动暂停，但未调�?`update_task_status("paused")`，API 仍返�?`running`，前端显�?运行�?但任务实际已停止，用户无法察�?
- 🆕v4.11【强制�?*B-REVIEW-BACKGROUND-TASK-MONITOR：后台任务健康监�?*
  - 后台任务（EventBus 消费�?/ 调度器循�?/ 健康检查器）必须用轮询监控（`while not stop_event.is_set(): if task.done(): break; await asyncio.wait_for(stop_event.wait(), timeout=N)`），**禁止** `await asyncio.Event().wait()` 静默等待导致任务异常退出时主循环无感知
  - **核心机制**（审查时必须理解）：
    - `asyncio.Event().wait()` 会阻塞直�?event �?set，期间无法感知其�?task 的退�?
    - 后台 task（如 EventBus）异常退出时，主循环仍阻塞在 `stop_event.wait()`，事件推送静默失�?
    - 轮询模式�?N 秒检查一�?`task.done()`，能�?10 秒内感知子任务退�?
    - `asyncio.wait_for(stop_event.wait(), timeout=N)` 配合 `try/except asyncio.TimeoutError` 是标准轮询模�?
  - **判断信号**�?
    - 代码�?`bus_task = asyncio.create_task(...)` �?`await stop_event.wait()` �?视为违规
    - 代码�?`event_bus_task = asyncio.create_task(event_bus.run())` + `await shutdown_event.wait()` �?必须改为轮询
    - 后台 task 异常退出但主循环未感知 �?典型症状
  - **修复模式**�?
    ```python
    # �?轮询监控后台任务
    stop_event = asyncio.Event()
    while not stop_event.is_set():
        if bus_task.done():
            exc = bus_task.exception()
            if exc:
                logger.error("EventBus 异常退出：{}", exc)
            else:
                logger.warning("EventBus 已退�?)
            break
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            continue  # 超时继续下一轮检�?

    # 禁止：Event.wait 静默等待，bus_task 异常退出无感知
    ```
  - **配置参数**：`background_task_monitor.poll_interval_seconds`（默�?`10`，轮询间隔）、`background_task_monitor.monitored_tasks`（必须监控的后台任务名列表，�?`["event_bus", "scheduler_loop", "health_check", "cookie_sync", "kb_refresh"]`）、`background_task_monitor.on_task_exit`（默�?`log_and_break`，可�?`restart`）、`background_task_monitor.restart_max_attempts`（默�?`3`，restart 策略下的最大重启次数）�?`config.yaml` �?`background_task_monitor` 节点管理
  - **适用**：所有后�?asyncio.Task（EventBus / Scheduler / Health Checker / Cookie Sync / KB Refresh）；需要在主循环中感知子任务退出的场景
  - **不适用**：fire-and-forget 任务（不需感知退出）；一次性任务（如启动初始化）；�?done_callback 处理的任�?
  - **历史教训**：`startup._scheduler_loop` �?`await stop_event.wait()` 等待关闭信号，EventBus 任务异常退出时主循环无感知，事件推送静默失�?30 分钟才被用户发现
- 🆕v4.14【强制�?*B-REVIEW-ROUTE-BLOCK-TYPES：浏览器自动化资源拦截粒�?*
  - 浏览器自动化资源拦截必须考虑业务关键资源（二维码图片、关键数据接口）�?*禁止**盲目拦截 image/font/media。拦截前必须检查页面是否依赖图片渲染关键内容（如二维码图片是登录流程关键资源），若依赖则必须排除或延迟拦截
  - **判断信号**：代码含 `route.abort("image")` �?`route.abort("font")` �?`route.abort("media")` �?必须检查页面是否依赖该类型资源渲染关键业务内容；登录流�?二维码页�?图片采集页面 �?禁止拦截 image
  - **修复模式**�?
    ```python
    # �?按场景精细化拦截
    async def setup_route_blocking(page, scenario: str):
        block_types = config.browser.route_block_scenarios.get(scenario, ["font", "media"])
        if "login" in scenario or "qrcode" in scenario:
            block_types = []  # 登录流程不拦截任何资源，确保二维码图片正常渲�?
        async def route_handler(route):
            if route.request.resource_type in block_types:
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", route_handler)
    ```
  - **配置参数**：`browser.route_block_types`（默�?`["font", "media"]`，不拦截 image）、`browser.route_block_whitelist`（关键资�?URL 白名单，如二维码图片 URL）、`browser.route_block_scenarios`（场景到拦截类型的映射，�?`login �?[]` 不拦截，`search �?["image", "font", "media"]` 可拦截）�?`config.yaml` �?`browser.route_block` 节点管理
  - **适用**：浏览器自动化场景的资源拦截优化（减少带宽、加快加载）
  - **不适用**：纯数据抓取页面（无关键图片渲染）、纯 API 请求场景（无需浏览器）
  - **历史教训**：登录流�?`route.abort("image")` 拦截所有图片，导致二维码图片无法渲染，用户看不到二维码无法扫码登录。修复后改为精细化拦截，排除二维码图�?URL
- 🆕v4.19【强制�?*B-REVIEW-SCHEDULER-STARTUP-VISIBILITY：关键调度器启动状态可见�?*
  - 关键后台调度器（影响业务正确性的，如批量采集/状态回�?数据同步/定时清理）的启动状态必须在启动日志中明确告知用户，未启动时输出 WARNING 级别日志 + 醒目提示（含启动命令样例 + 影响范围），`--help` 输出必须说明启动参数影响范围，`/api/about` 端点必须返回调度器状态，调度器启动参数列表在 config.yaml 集中管理
  - **核心机制**（审查时必须理解）：
    - 关键调度器（�?`BatchRefreshScheduler`）影响业务正确性（已售商品状态回查），未启动时业务表面正常但数据长期不刷�?
    - INFO 级别日志用户在终端滚动中容易错过，未启动时必须用 WARNING 级别 + 多行格式（启动命�?+ 影响范围�?
    - `--help` 输出仅说明参数语法不够，必须说明"启用什么调度器、间隔多少、影响哪些下游功�?
    - `/api/about` 端点返回 `schedulers: [{name, enabled, interval_minutes, last_run_at}]` 供前�?关于"页面展示
  - **判断信号**�?
    - 代码�?`asyncio.create_task(...)` �?`scheduler.start()` 启动调度器但无启动日�?�?视为违规
    - 启动日志仅用 `logger.info("xxx 已启�?)` 但未告知用户如何禁用/启用 �?视为可疑
    - 调度器未启动时仅静默跳过（无 WARNING）→ 视为违规
    - `/api/about` 端点未返回调度器状�?�?视为可疑
    - `--help` 输出中启动参数无影响范围说明 �?视为可疑
  - **修复模式**�?
    ```python
    # �?未启动时 WARNING + 醒目提示 + 启动命令 + 影响范围
    if not os.environ.get("XH_WITH_SCHEDULER"):
        logger.warning(
            "⚠️ 批量采集调度器未启动，已售商品状态将不刷新。\n"
            "  如需启用：python -m xianyu_hunter web --with-scheduler\n"
            "  影响范围：商�?is_sold 状态回查、已售商品检�?
        )
        return
    # 启动�?INFO + 间隔
    logger.info("�?批量采集调度器已启动（间�?30 分钟，每�?100 条）")

    # �?/api/about 返回调度器状�?
    @api_router.get("/about")
    async def about():
        return {
            "version": _safe_app_version(),
            "schedulers": [{
                "name": "BatchRefreshScheduler",
                "enabled": scheduler.is_running,
                "interval_minutes": 30,
                "last_run_at": scheduler.last_run_at,
            }],
        }

    # 禁止：未启动时仅 info 静默跳过
    ```
  - **配置参数**：`scheduler_startup_visibility.critical_schedulers`（关键调度器名单，如 `["BatchRefreshScheduler", "AutoLoginScheduler", "CookieCheckerScheduler"]`）、`scheduler_startup_visibility.require_startup_log`（默�?`true`）、`scheduler_startup_visibility.require_warning_when_disabled`（默�?`true`）、`scheduler_startup_visibility.require_help_doc`（默�?`true`）、`scheduler_startup_visibility.require_about_endpoint`（默�?`true`）、`scheduler_startup_visibility.startup_param_env_mapping`（启动参数与环境变量映射，如 `{"--with-scheduler": "XH_WITH_SCHEDULER"}`）在 `config.yaml` �?`scheduler_startup_visibility` 节点管理
  - **适用**：关键后台调度器（批量采�?状态回�?数据同步/定时清理）；通过启动参数或环境变量控制的功能开关；影响业务正确性的后台任务
  - **不适用**：调试用的可选功能（�?`--debug` 模式）；默认启动且无法关闭的核心功能；一次性任务（如启动时迁移�?
  - **历史教训**：用户启�?web 服务时未�?`--with-scheduler` 参数，`BatchRefreshScheduler`（每 30 分钟回查 `is_sold=0` 商品状态）永远不运行。日志仅输出一�?info"批量采集调度器未启动（需 XH_WITH_SCHEDULER=1�?，用户无感知。导致商�?1058031608014 实际已售但数据库 `is_sold=0` 长期不刷新，用户看到已售商品仍被推荐。修复后调度器未启动时输�?WARNING + 醒目提示 + 启动命令 + 影响范围
- 🆕v4.25【强制�?*B-REVIEW-112: SHARED-SINGLETON-POLLUTION：共享单例污染检�?*
  - 循环中创建任务级覆盖对象必须使用局部变�?`worker_xxx`�?*禁止**直接修改 `container` 单例导致后续任务继承前一任务的覆盖状�?
  - **核心机制**（审查时必须理解）：
    - `container` 单例（如 `Container`）在进程生命周期内共享，多个任务/请求复用同一实例
    - 循环�?`container.chatbot = build_chatbot(task_config)` 会污染单例，下一个任务读到的是上一个任务的 chatbot
    - 必须�?`worker_chatbot = build_chatbot(task_config)` 局部变量，任务结束后随栈帧释放
    - 单例只存�?进程级共享配�?（如数据库连接池、全局默认配置），**禁止**存放"任务级覆盖配�?
  - **判断信号**�?
    - 循环中出�?`container.xxx = ...` / `self.container.xxx = ...` 赋�?�?视为违规
    - `for task in tasks:` 内部修改单例属�?�?视为违规
    - 任务执行后单例属性未还原导致下一任务读到脏数�?�?视为违规
    - 多任务并发时单例属性被竞态覆�?�?视为违规
  - **修复模式**�?
    ```python
    # �?使用局部变�?worker_xxx，不污染单例
    async def run_batch(tasks: list[Task]):
        for task in tasks:
            # 任务级覆盖配置用局部变�?
            worker_chatbot = build_chatbot(task.chatbot_config)
            worker_price_strategy = build_price_strategy(task.price_config)
            await _process_one(task, worker_chatbot, worker_price_strategy)
            # 局部变量随函数栈帧释放，不污染 container

    # 禁止：直接修�?container 单例
    async def run_batch(tasks: list[Task]):
        for task in tasks:
            container.chatbot = build_chatbot(task.chatbot_config)  # 污染单例�?
            await _process_one(task)
            # 下一任务读到的是本任务的 chatbot

    # �?若必须通过单例传递（如深层调用链），�?try/finally 还原
    async def run_batch(tasks: list[Task]):
        original = container.chatbot
        try:
            for task in tasks:
                worker = build_chatbot(task.chatbot_config)
                container.chatbot = worker  # 临时设置
                await _process_one(task)
        finally:
            container.chatbot = original  # 还原，避免污染后续批�?
    ```
  - **关键约束**�?
    - 循环内创建的任务级对象必须用 `worker_xxx` 局部变�?
    - **禁止**在循环内 `container.xxx = ...` 修改单例
    - 若深层调用链必须通过单例传递，�?`try/finally` 还原原始�?
    - 单例只存"进程级共享配�?，任务级配置用局部变量或函数参数传�?
    - 并发场景（`asyncio.gather`）下单例污染会触发竞态，必须用局部变�?
    - 修改后必�?`grep` 验证循环内无 `container.xxx =` 赋�?
  - **配置参数**：`shared_singleton_protection.singleton_attr_pattern`（单例属性命名模式，�?`container`）、`shared_singleton_protection.worker_var_prefix`（局部变量前缀，默�?`worker_`）、`shared_singleton_protection.require_try_finally_restore`（默�?`true`，若必须修改单例则要�?try/finally 还原）、`shared_singleton_protection.forbid_assign_in_loop`（默�?`true`，禁止循环内赋值单例属性）�?`config.yaml` �?`shared_singleton_protection` 节点管理
  - **适用**：循环处理多个任务的批量场景（如 `run_batch`/`asyncio.gather`）；任务级配置覆盖功能；通过 container 单例传递依赖的架构
  - **不适用**：单任务处理（无循环无污染风险）；进程级初始化（�?`lifespan` 启动时设置单例）；只读单例（不修改属性）
  - **历史教训**：任务级配置覆盖功能中，`run_batch` 循环�?`container.chatbot = build_chatbot(task.chatbot_config)` 为每个任务构建专�?chatbot，但下一个任务读到的是上一个任务的 chatbot 配置（污染），导致任�?A 的高价策略被任务 B 继承，任�?B 误以高价抢单。修复后改为 `worker_chatbot` 局部变�?+ 函数参数传�?

### 10. 事件总线 🆕v2.0

- 【强制】EventBus 基于 `asyncio.Queue`
- 【强制】EventType 枚举完整（约 35 种）
- 【强制】EVENT_SEVERITY 三级：INFO / WARN / ERROR
- 【强制】事件消费者必须处�?`asyncio.CancelledError` �?`QueueEmpty`
- 【推荐】SSE 端点�?`EventSourceResponse` 或手�?`StreamingResponse` + `text/event-stream`
- 【强制】SSE lastEventId 持久化重连：客户端断线重连时�?localStorage 读取作为 `?last_event_id=` 参数
- 🆕v4.5【强制�?*B-REVIEW-MULTI-WRITE-ENTRY：多源状态同步统一入口**
  - 同一份状态（�?Cookie 层状态、用户登录态、连接池状态）�?�?2 个写入入口时，必须建�?*统一同步入口函数**（如 `sync_cookie_layers_from_json()`），在所有写入路径写完后主动调用
  - **判断信号**：核心状态依赖外部存储（JSON / SQLite / 浏览器内�?/ 远程 API），但内存层状态只在某个入口被同步 �?出现"实际有数据但显示失效"的脱节现�?
  - **修复模式**：识别所有写入路径（登录 / 注入 / 导入 / 工具刷新）→ 抽取 `sync_xxx_from_<主数据源>()` 公共函数 �?在每个写入路径的成功分支主动调用 �?同步逻辑必须重新读主数据源（而非用调用方传入的列表），避免过滤逻辑不一�?
  - **关键约束**：禁止依赖某个回调（�?`on_login_success`）自动触发而无任何调用方——必须显式调�?
  - **配置参数**：`sync_entry_functions`（同步入口函数名列表）、`write_entry_paths`（需要调用的写入路径列表）在 `config.yaml` �?`state_sync` 节点管理
  - **适用**：状态分布在多个存储介质（JSON / SQLite / 浏览�?/ 内存）且需保持显示一致；多入口写入同一份状�?
  - **不适用**：单一写入入口、状态天然同步（无中间层缓存）、纯计算型状�?
  - **历史教训**：`CookieRotator` �?`on_login_success` 钩子函数被定义后从未被任何调用方触发，导�?5 个登录路径（`browser_login` / `auth_helper` / `cookie_inject` / `browser_import` / `qr_login`）都绕过层状态更新，登录�?`/cookies/layers` 端点始终显示三层失效但功能完全正�?
- 🆕v4.5【强制�?*B-REVIEW-INACTIVE-STATE-PRESERVE：状态条件区�?从未初始�?�?主动失效"**
  - 当状态字段有"从未初始�?/ 已初始化 / 主动失效"三种语义时，**禁止**�?`not state.valid` 笼统判断"该同步了"——必须用 `state.updated_at == 0.0` 区分"从未初始�?�?主动失效�?
  - **判断信号**：状态对象有 `valid` + `updated_at` 两个字段 + 存在"主动失效"语义（如 `invalidate_layer()` 显式�?`valid=False` 但保�?`updated_at`）→ �?`not valid` 会覆盖手动失效状�?
  - **修复模式**�?
    - **从未初始�?*（`updated_at == 0.0`）：可主动补救同步（读主数据源、读浏览器内存兜底）
    - **主动失效**（`updated_at > 0.0 and not valid`）：保留状态不覆盖（用�?系统已显式标记失效）
    - **已初始化有效**（`updated_at > 0.0 and valid`）：正常返回
  - **配置参数**：`inactive_check_field`（用于判断的字段名，�?`updated_at`）在 `config.yaml` �?`state_semantics` 节点管理
  - **适用**：所�?状态机 + 主动失效"语义的场景（Cookie 层状态、用户会话状态、健康检查状态）
  - **不适用**：纯二元状态（有效/无效）、无"主动失效"语义的简单标志位
  - **历史教训**：`cookie_checker` 健康检查器�?`not identity_state.valid` 作为"需要同�?的判断条件，导致 collector 检测到 RGV587 主动失效 identity 层后，cookie_checker 在下�?tick 立即�?JSON 重新同步覆盖失效状态，造成"自动失效永远不生�?的死循环
- 🆕v4.5【强制�?*B-REVIEW-BROWSER-FALLBACK-SYNC：浏览器内存兜底同步模式**
  - 当主数据源（JSON）可能与运行时状态（浏览器内存、内存缓存）脱节时，状态查询端点必须实�?*两步同步**：第一步从主数据源同步；第一步后仍有状态未恢复时，从运行时载体读取作为兜底
  - **判断信号**：主数据�?+ 运行时载体共�?+ 某些字段（如 MTOP token）只在运行时载体更新（被外部进程 `Set-Cookie`�?+ 状态查询可能因�?JSON 过期而误报失�?
  - **修复模式**�?
    1. **第一步（主数据源同步�?*：从 JSON 读取、过滤过期、构�?cookie_map、调�?`sync_state_from_cookies()`
    2. **第二步（兜底同步�?*：检查仍�?`updated_at==0.0` 的层 �?�?`browser.context.cookies()` 读取对应�?�?重新构�?cookie_map �?同步 �?回写主数据源（避免下次再走兜底）
  - **回写策略**：用 `upsert`（更�?+ 添加）而非 `update`（只更新已存在），因 JSON 中可能完全不存在�?cookie 条目
  - **配置参数**：兜底同步开关、读取的 cookie 域列表、回写白名单�?`config.yaml` �?`cookie_fallback` 节点管理
  - **适用**：浏览器 Cookie 多源持久化、CDP/Playwright 抓取场景、外部进程状态回�?
  - **不适用**：无运行时载体的纯文件存储、有强一致要求的场景（应直接报错而非兜底�?
  - **历史教训**：`_m_h5_tk` �?session token �?MTOP 响应中被 `Set-Cookie` 写入浏览器内存，�?`_sync_response_cookies_to_context` 只调 `add_cookies` 不回�?JSON。重启后浏览器从 JSON 加载�?token 失败，但功能靠浏览器内存正常工作。`/cookies/layers` 端点增加浏览器内存兜底同�?+ 回写 JSON 后彻底解�?
- 🆕v4.14【强制�?*B-REVIEW-SIGNAL-LAYER-MAPPING：层依赖关系信号匹配**
  - 层恢复信号必须与层范围匹配，SESSION 层信号不能恢�?IDENTITY 层，IDENTITY 无效�?SESSION 也不能恢复。层定义�?`depends_on` 字段指示依赖关系，信号只能恢复其所属层及以下层�?*禁止**跨层恢复导致状态不一�?
  - **判断信号**：代码含 `sync_cookie_layers_from_json()` �?`_sync_layers_from_signal()` �?必须检查信号与层的匹配关系；层定义�?`depends_on` 字段 �?信号恢复必须遵循依赖�?
  - **修复模式**�?
    ```python
    # �?按依赖链恢复层状�?
    LAYER_DEPENDS_ON: dict[str, str | None] = {
        "session": "identity",  # session 依赖 identity
        "identity": "base",     # identity 依赖 base
        "base": None,           # base 无依�?
    }

    async def sync_layer_from_signal(signal_type: str, layer_name: str) -> bool:
        # 信号只能恢复其所属层及以下层（依赖链�?
        signal_layer_mapping = config.cookie_layers.signal_layer_mapping
        allowed_layer = signal_layer_mapping.get(signal_type)
        if allowed_layer != layer_name:
            logger.warning(f"信号 {signal_type} 不能恢复�?{layer_name}，只能恢�?{allowed_layer} 及其依赖�?)
            return False

        # 检查依赖链上层是否有效
        depends_on = LAYER_DEPENDS_ON.get(layer_name)
        if depends_on and not get_layer_state(depends_on).valid:
            logger.warning(f"�?{layer_name} 的依赖层 {depends_on} 无效，无法恢�?)
            return False

        # 恢复层状�?
        return await _restore_layer_state(layer_name)
    ```
  - **配置参数**：`cookie_layers.signal_layer_mapping`（信号到层的映射表，�?`login_success �?identity`，`session_refresh �?session`）、`cookie_layers.depends_on_chain`（层依赖链，�?`session �?identity �?base`）在 `config.yaml` �?`cookie_layers` 节点管理
  - **适用**：层级依赖的状态恢复、Cookie 层管理、多源状态同�?
  - **不适用**：无层级依赖的状态、独立状态恢复、单层状态管�?
  - **历史教训**：SESSION 层恢复信�?`sync_from_browser()` 被误用于恢复 IDENTITY 层，导致 IDENTITY 层状态与实际不一致（浏览器已失效但层状态显示有效）
- 🆕v4.21【强制�?*B-REVIEW-PYDANTIC-FIELD-DECLARE：Pydantic 模型字段完整性规�?*
  - 所有需持久化或回显的字段必须在 Pydantic 模型中显式声明，**禁止**依赖 `extra='allow'`/`extra='ignore'` 处理 yaml 字段（Pydantic v2 默认 `extra='ignore'`，未声明字段�?`model_dump()` 时会被丢弃，导致 API 响应缺失字段�?
  - **核心机制**（审查时必须理解）：
    - Pydantic v2 `BaseModel` 默认 `extra='ignore'`，未显式声明的字段在 `model_dump()` 时会被丢�?
    - API 响应若直接返�?`model_dump()`，前端永远拿不到未声明字段，导致凭据/配置回显失败
    - 任何需要持久化或回显的字段�?*必须**�?Pydantic 模型中显式声明（哪怕默认空字符串）
  - **判断信号**�?
    - yaml 中有某字段但 Pydantic 模型无对应字段定�?�?视为违规
    - API 返回的字典中缺失 yaml 中已有的字段 �?必须检�?Pydantic 模型是否声明
    - 前端"填写后刷新页面变�?问题 �?必查根因是否�?Pydantic 字段未声�?
    - 代码�?`model_extra` �?`__pydantic_extra__` 访问未声明字�?�?视为可疑（应改为显式声明�?
    - `grep "extra=.allow." src/xianyu_hunter/` 发现配置模型�?`extra='allow'` �?视为可疑
  - **修复模式**�?
    ```python
    # 禁止：依�?extra='allow' 处理 yaml 字段
    class AppConfig(BaseModel):
        model_config = ConfigDict(extra='allow')
        notifier: NotifierConfig = NotifierConfig()
        # 凭据字段未声明，model_dump() 时被丢弃

    # �?正确：所有需持久化的字段显式声明（哪怕默认空字符串）
    class AppConfig(BaseModel):
        notifier: NotifierConfig = NotifierConfig()
        # 通知渠道凭据（明文存�?yaml，前端用 Input.Password 组件隐藏�?
        serverchan_send_key: str = ""
        pushplus_token: str = ""
        bark_server: str = ""
        bark_key: str = ""
        telegram_bot_token: str = ""
        telegram_chat_id: str = ""
        wecom_webhook: str = ""
        dingtalk_webhook: str = ""
        dingtalk_secret: str = ""
        webhook_url: str = ""
    ```
  - **配置参数**：`pydantic_field_integrity.require_explicit_declare`（默�?`true`，所�?yaml 字段必须显式声明）、`pydantic_field_integrity.scan_yaml_keys`（默�?`true`，自动扫�?yaml 字段名与 Pydantic 模型字段对齐）、`pydantic_field_integrity.exceptions`（豁免列表，如运行时计算的临时字段）�?`config.yaml` �?`pydantic_field_integrity` 节点管理
  - **适用**：所有继�?`BaseModel` 的配置模型（AppConfig / NotifierConfig 等）；需持久化到 yaml/json 的字段；通过 API 回显的字�?
  - **不适用**：运行时计算字段（用 `@computed_field`）；显式标注 `exclude=True` 的字段；临时内存对象（无需序列化）
  - **历史教训**：通知渠道凭据字段（`serverchan_send_key` �?10 个）未在 `AppConfig` 中显式声明，前端写入 yaml �?`GET /api/config` 调用 `model_dump()` 丢弃这些字段，导致前�?填写后刷新页面变�?
- 🆕v4.21【强制�?*B-REVIEW-CREDENTIAL-SYNC-BRIDGE：凭据同步桥接规范（yaml→keyring�?*
  - 双存储介质（yaml 写入 + keyring 读取）的凭据必须有显式同步桥接函数，DI 容器初始�?Notifier/Client 之前必须先调用同步函数；keyring KEY 常量名必须与 yaml 字段�?1:1 对齐；同步失败必�?`logging.warning()` 告警
  - **核心机制**（审查时必须理解）：
    - 前端写入 yaml（用户可编辑的明文存储），Notifier �?keyring 读取（运行时凭证存储�?
    - 两个存储介质之间**必须**有显式同步桥接函数，否则 Notifier `is_configured` 永远�?False
    - keyring KEY 常量�?*必须**�?yaml 字段�?1:1 对齐，否则同步逻辑会写错位�?
    - 同步时机：DI 容器初始�?Notifier 之前必须先调�?`_sync_yaml_credentials_to_keyring()`
  - **判断信号**�?
    - 代码�?yaml 字段（`config.dingtalk_webhook`）但无同步到 keyring 的调�?�?视为违规
    - keyring KEY 常量名与 yaml 字段名不一致（�?`KEY_DINGTALK_WEBHOOK = "dingtalk_webhook_url"` �?yaml 字段�?`dingtalk_webhook`）→ 视为违规
    - Notifier `__init__` �?keyring 读取�?`is_configured=False` 且无同步逻辑 �?必查同步桥接
    - 测试�?`wire_notifier()` 后单测失败（keyring 被污染）�?必须在测�?setup/teardown 清理 keyring
    - `grep "secrets.get_secret" src/xianyu_hunter/` 找到读取点但无对应的 `secrets.set_secret()` 同步�?�?视为违规
  - **修复模式**�?
    ```python
    # �?1. keyring KEY 常量名与 yaml 字段�?1:1 对齐
    KEY_DINGTALK_WEBHOOK = "dingtalk_webhook"  # �?旧�?"dingtalk_webhook_url"
    KEY_WECOM_WEBHOOK = "wecom_webhook"        # �?旧�?"wecom_webhook_url"

    # �?2. DI 容器初始�?Notifier 之前先同�?yaml �?keyring
    def wire_notifier(self) -> None:
        self._sync_yaml_credentials_to_keyring()  # 必须先同�?
        self.notifier_hub = NotifierHub(channels=enabled, ...)
        self.notifier_hub.attach(self.event_bus)

    def _sync_yaml_credentials_to_keyring(self) -> None:
        """�?yaml 中的明文凭证同步�?keyring"""
        from xianyu_hunter.infra import secrets
        cred_map = {
            "serverchan_send_key": secrets.KEY_SERVERCHAN,
            "pushplus_token": secrets.KEY_PUSHPLUS,
            "bark_server": secrets.KEY_BARK_SERVER,
            "bark_key": secrets.KEY_BARK_KEY,
            "telegram_bot_token": secrets.KEY_TELEGRAM_TOKEN,
            "telegram_chat_id": secrets.KEY_TELEGRAM_CHAT,
            "wecom_webhook": secrets.KEY_WECOM_WEBHOOK,
            "dingtalk_webhook": secrets.KEY_DINGTALK_WEBHOOK,
            "dingtalk_secret": secrets.KEY_DINGTALK_SECRET,
            "webhook_url": secrets.KEY_WEBHOOK_URL,
        }
        for yaml_attr, keyring_key in cred_map.items():
            yaml_value = getattr(self.config, yaml_attr, "")
            if yaml_value:
                try:
                    secrets.set_secret(keyring_key, yaml_value)
                except Exception as e:
                    logging.warning("同步凭据 %s �?keyring 失败: %s", yaml_attr, e)

    # 禁止：Notifier 直接�?keyring 读取�?yaml 从未同步
    ```
  - **配置参数**：`credential_sync_bridge.yaml_to_keyring_map`（yaml 字段名到 keyring KEY 常量的映射表）、`credential_sync_bridge.sync_timing`（默�?`before_notifier_init`，可�?`on_config_update`）、`credential_sync_bridge.require_key_name_align`（默�?`true`，强�?keyring KEY 常量名与 yaml 字段名对齐）�?`config.yaml` �?`credential_sync_bridge` 节点管理
  - **适用**：双存储介质的凭�?配置同步（yaml �?keyring、yaml �?env、json �?数据库）；Notifier/Client �?keyring 读取的场景；多写入入口的状态同�?
  - **不适用**：单一存储介质（如�?yaml 或纯 keyring）；运行时计算字段（无需同步）；外部系统主动推送的状态（无本地写入）
  - **历史教训**：用户在通知渠道菜单填写钉钉 webhook 后，自动抢单成功却未收到钉钉通知。根因：前端�?yaml，`DingTalkNotifier` �?keyring 读取，但中间无同步桥接，`is_configured=False`，渠道被 `NotifierHub` 静默跳过。同�?`KEY_DINGTALK_WEBHOOK="dingtalk_webhook_url"` �?yaml 字段 `dingtalk_webhook` 不一致，即使有同步也会写错位�?
- 🆕v4.21【强制�?*B-REVIEW-REDACT-SCENARIO：脱敏策略场景区分规�?*
  - 同一字段在不�?API 场景下脱敏策略必须区分：`GET /api/config`（前端回显，**不脱�?*凭据）vs `/share`/`/export`（分享导出，**必须脱敏**凭据）vs 日志输出�?*必须脱敏**凭据）；`_REDACT_KEYS`/`_SHARE_REDACT_PATHS`/`_SENSITIVE_KEYS` 三个集合必须分离；UI 层用 `Input.Password` 组件隐藏敏感内容（前端层防护�?
  - **核心机制**（审查时必须理解）：
    - `_REDACT_KEYS`（全局脱敏字段集）会脱敏所�?API 响应，前端无法回显需展示的字�?
    - 凭据字段需在前端回显（用户已填写的值），不能加�?`_REDACT_KEYS`
    - 凭据字段在分�?导出场景必须脱敏（防止泄露），需加入 `_SHARE_REDACT_PATHS`
    - 凭据字段在日志输出必须脱敏（防止日志泄露），需加入 `_SENSITIVE_KEYS`
    - UI 层用 `Input.Password` 组件隐藏敏感内容（前端层防护），不依赖后端脱�?
  - **判断信号**�?
    - API 返回字段被脱敏但前端需要回显（�?`***` 显示在输入框）→ 必查 `_REDACT_KEYS` 是否包含该字�?
    - 分享/导出场景未脱敏凭据字�?�?必查 `_SHARE_REDACT_PATHS` 是否包含该字�?
    - 日志中打印凭据明�?�?必查 `_SENSITIVE_KEYS` 是否包含该字�?
    - 同一字段在所�?API 场景脱敏策略一致（如所�?API 都脱敏或都不脱敏）→ 视为可疑（未区分场景�?
  - **修复模式**�?
    ```python
    # �?1. 三个脱敏集合分离
    _REDACT_KEYS = frozenset({
        "cookie", "cookies", "session_id",  # 仅前端无需回显的真正敏感字�?
    })
    _SHARE_REDACT_PATHS = [
        ("notifier", "channels"),
        ("serverchan_send_key",),
        ("pushplus_token",),
        ("bark_server",),
        ("bark_key",),
        ("telegram_bot_token",),
        ("telegram_chat_id",),
        ("wecom_webhook",),
        ("dingtalk_webhook",),
        ("dingtalk_secret",),
        ("webhook_url",),
        ("browser", "user_data_dir"),
    ]
    _SENSITIVE_KEYS = frozenset({
        "serverchan_send_key", "pushplus_token", "bark_key", "bark_server",
        "telegram_bot_token", "telegram_chat_id", "wecom_webhook",
        "dingtalk_webhook", "dingtalk_secret", "webhook_url",
        "openai_api_key",
    })

    # �?2. GET /api/config 不脱敏凭据（前端需回显�?
    @app.get("/api/config")
    async def get_config():
        return config.model_dump()  # 凭据字段原样返回

    # �?3. /share 端点�?_SHARE_REDACT_PATHS 脱敏
    @app.post("/share")
    async def share_config():
        data = config.model_dump()
        return _redact_paths(data, _SHARE_REDACT_PATHS)

    # 禁止：所�?API 都用 _REDACT_KEYS 脱敏凭据
    ```
  - **配置参数**：`redact_strategy.scenarios`（场景列表，�?`["config_response", "share_response", "export_response", "log_output"]`）、`redact_strategy.scenario_field_map`（场景到字段集的映射，如 `{config_response: [], share_response: ["serverchan_send_key", ...]}`）、`redact_strategy.ui_protection_components`（默�?`["Input.Password", "MaskedText"]`，前�?UI 层防护组件白名单）在 `config.yaml` �?`redact_strategy` 节点管理
  - **适用**：所有需要脱敏的敏感字段（凭据、Cookie、Token、用户隐私数据）；多场景 API 返回相同字段但脱敏策略不同；前端需回显但分享需脱敏的场�?
  - **不适用**：单一场景的字段（所�?API 都需脱敏或都不需脱敏）；非敏感字段（如配置项的开关状态）；前端纯展示字段（无后端写入需求）
  - **历史教训**：通知渠道凭据字段被加�?`_REDACT_KEYS`，导�?`GET /api/config` 返回 `***`，前端无法回显用户已填写的凭据。修复后将凭据字段从 `_REDACT_KEYS` 移除（前端需回显），同时扩展 `_SHARE_REDACT_PATHS` �?`_SENSITIVE_KEYS`（分享和日志仍脱敏），前端用 `Input.Password` 组件隐藏内容

### 11. 错误处理

- 【禁止】裸 `except:` �?`except Exception:` 静默吞掉（`except: pass`�?
- 【禁止】过�?`except Exception` / `except BaseException`
- 【强制】捕获异常后保留原始堆栈：`raise NewException("msg") from e`
- 【强制】三层兜底错误处理：
  1. 路由层抛业务异常（如 `ResumeBlockedError`�?
  2. `register_exception_handlers` 统一�?JSON 响应
  3. loguru 兜底记录
- 【强制】`asyncio.CancelledError` 是唯一例外，必须向上传播以触发资源清理�?*�?*静默吞掉�?
- 【推荐】重试逻辑�?`tenacity`（退避策略、最大重试次数），禁�?`while True: try`
- 【推荐】资源释放用 `with` �?`try/finally`
- 🆕v4.1【强制�?*B-REVIEW-SESSION-SIGNAL：重试失败后状态信号必须传�?*
  - SSE/HTTP 接口包含重试逻辑时，重试代码块结束后必须检查关键状态标志（�?`last_session_invalid`�?
  - 状态仍异常则推送明确错误事件并 `return`�?*禁止**"重试失败但仍走成功流�?误导用户
  - **判断信号**：代码含 `retry_*` / `raw_results = await retry_*(...)` �?重试后必须检查状态标�?
  - **不通过示例**�?
    ```python
    raw_results = await retry_search(...)
    logger.info("raw_results={}", len(raw_results))  # 0 商品但未检�?session_invalid
    # 继续�?filtering �?前端误以�?真的没货"
    ```
  - **通过示例**�?
    ```python
    raw_results = await retry_search(...)
    if not raw_results and getattr(container.collector, "last_session_invalid", False):
        yield sse({"stage": "error", "detail": "会话已过期，请重新登�?, "status": 403})
        return
    ```
- 🆕v4.1【强制�?*错误粒度三类区分**：面向用户的错误响应必须按粒度区分（状态码与文案映射在 `config.yaml` �?`error_status_mapping` + `error_message_templates` 节点管理�?
  - `503/504`：稍后重试（网络超时/限流/服务繁忙�?
  - `401/403`：需用户介入（登录失�?权限不足�? 明确指引"请前往 X 重新登录"
  - `502`：需重启服务（浏览器断开/TargetClosed�?
  - **判断信号**：错误源�?`_m_h5_tk` 过期/Cookie 失效 �?401/403；`asyncio.TimeoutError` �?503/504；`TargetClosedError` �?502
- 🆕v4.3【强制�?*B-REVIEW-FALLBACK-CHAIN：降级链模式**
  - 多重方案按优先级排序，失败后自动降级�? 次失败加倍间隔，最大间�?2 小时
  - **判断信号**：多方案优先级明�?+ 网络不稳定环�?+ 外部依赖不可�?
  - **修复模式**：方�?A 失败 �?尝试方案 B �?方案 B 失败 N 次后触发 backoff（`interval *= 2`，上�?`max_interval`）→ 记录降级原因到日�?
  - **配置参数**：`max_failures=3`、`backoff_multiplier=2`、`max_interval=7200` �?`config.yaml` �?`fallback_chain` 节点管理（不硬编码）
  - **适用**：Cookie 同步（offline import �?CDP import �?backoff）、网络重试、外�?API 调用
  - **不适用**：单一方案场景、降级后体验差于报错（应直接失败）、关键安全场景（必须 fail-fast�?
  - **历史教训**：Cookie 同步调度器实�?offline import 优先 �?CDP import 次之 �?backoff 兜底的降级链�? 次失败后间隔加倍避免无意义重试
- 🆕v4.4【强制�?*B-REVIEW-FAST-DEGRADATION：快速模式降级重�?*
  - `fast=True` 模式跳过恢复机制（token 刷新、RGV587 重试）时，调用方应在 fast 失败后自动以�?fast 模式重试一�?
  - **判断信号**：方法签名含 `fast=True` 参数�?fast 模式跳过 `_ensure_fresh_*` / `*_retry` 逻辑 �?调用方必须检�?fast 返回结果的状态标志，失败时降级重�?
  - **修复模式**：`fast=True` 返回空结果且状态标志（�?`last_session_invalid=True`）指示可恢复 �?自动�?`fast=False` 重试 �?重试成功则正常返回，失败才报�?�?重试超时应放宽以容纳 token 刷新 + 搜索
  - **配置参数**：降级重试超时（默认 45s）在 `config.yaml` �?`search.fast_degradation_timeout` 节点管理
  - **适用**：所�?fast/quick 模式接口（跳过恢复机制的快速路径）
  - **不适用**：纯查询接口（无副作用）、实时性要求极高的接口（如心跳检测）、重试成本过高的操作
  - **历史教训**：实时搜索用 `fast=True` 完全跳过 `_ensure_fresh_m5tk()` �?RGV587 重试，刚登录后第一次搜索碰�?token 有效成功，后续连续请求时 token 过期全部失败
- 🆕v4.9【强制�?*B-REVIEW-STATE-MACHINE-WHITELIST：状态机白名单转�?*
  - 含「状态」字段且状态会变化的业务对象（订单/任务/会话/工作流）必须�?6 步流程设计状态机：枚举穷�?/ 转换白名�?/ 终态不可复�?/ 中间态超时清�?/ deadline 不可无限重置 / 前后端枚举值统一
  - **判断信号**：业务对象有 `status` / `state` 字段 + 字段会通过 API / 调度�?/ 事件变更 �?必须�?6 步流程设�?
  - **修复模式**�?
    ```python
    # �?白名单模式：仅允�?pending_pay �?takeover_pending
    ALLOWED_TRANSITIONS: dict[str, set[str]] = {
        "pending_pay": {"takeover_pending", "cancelled"},
        "takeover_pending": {"succeeded", "failed"},
        # 终�?succeeded/failed/cancelled 不在 key �?�?任何转换都被拒绝
    }
    def transition(current: str, target: str) -> None:
        if current not in ALLOWED_TRANSITIONS or target not in ALLOWED_TRANSITIONS[current]:
            raise HTTPException(409, detail=f"非法状态转�? {current} �?{target}")

    # �?中间态超时清理：独立调度�?+ 一�?SQL 批量更新
    class TakeoverTimeoutScheduler:
        def _scan_and_expire(self) -> None:
            expired_ids = self._select_expired_ids()  # SELECT 在事务内
            if expired_ids:
                self.repo.expire_takeover_pending_orders(self.timeout_min)  # 一�?UPDATE
    ```
  - **关键约束**�?
    - 状态变更操作必须用**白名�?*（仅允许明确列出的转换）而非黑名单（禁止某些转换）——白名单更安全：新增状态时不会意外允许非法转换
    - `failed`/`succeeded`/`cancelled` 等终态禁止再转换到其他状态，状态变更接口必须前置校�?`if current_status in TERMINAL_STATES: raise HTTPException(409, ...)`
    - `pending_pay`/`takeover_pending` 等中间态必须有超时清理机制——独�?APScheduler `BackgroundScheduler` 定时扫描 + 一�?SQL 批量更新（SELECT + UPDATE 在同一事务），**禁止**逐条更新
    - `takeover_deadline` 等截止时间字段，同一操作（如 `takeover_order`）禁止反复延长，状态机白名单天然保�?
    - 后端 `status: str = "pending_pay"` 与前�?`type Status = 'pending_pay' | ...` 必须字面值完全一致，**禁止**后端 snake_case 前端 camelCase 的映射转�?
  - **配置参数**：`state_machine.<entity>.timeout_scan_interval`（默�?300s）、`state_machine.<entity>.timeout_threshold`（默�?1800s）、`state_machine.<entity>.terminal_states`（终态列表）、`state_machine.<entity>.allowed_transitions`（白名单映射）在 `config.yaml` �?`state_machine` 节点管理
  - **适用**：订�?任务/会话/工作流等有状态生命周期的业务对象
  - **不适用**：纯 CRUD 实体（如配置项，无状态流转）；单状态字段（�?`is_active: bool` 用简�?if 判断即可）；一次性事件（如日志记录）
  - **历史教训**：`takeover_order` 接口未校验起始状态，导致 `failed` 终态订单可被接管（终态复活）；`takeover_pending` 超时无清理机制，订单永久卡死；同一订单可被反复 `takeover_order` 延长 deadline（无限重置）。修复后改为白名�?+ 独立调度器批量清�?+ 终态前置校�?
- 🆕v4.11【强制�?*B-REVIEW-LLM-DEFENSIVE-PARSING：LLM 响应防御性三层级解析**
  - 调用 LLM API（OpenAI 兼容协议、Anthropic、本地模型）的响应必须按三层级防御性解析：`choices �?message �?content`，每层用 `.get()` / `isinstance` / 长度检查，**禁止**直接 `response["choices"][0]["message"]["content"]` 链式访问导致 KeyError / IndexError
  - **核心机制**（审查时必须理解）：
    - LLM 服务异常时返�?`{"error": "..."}` 而非 `{"choices": [...]}`
    - 流式响应�?chunk 可能缺少 message 字段（仅�?delta�?
    - content 可能�?null（如 function_call 场景）或空字符串
    - 链式访问任一层失败都会抛 KeyError/IndexError，导�?AI 建议任务静默失败
  - **判断信号**�?
    - 代码�?`response["choices"]` �?`response['choices'][0]` �?必须�?`.get()` + 边界检�?
    - 代码�?`response["choices"][0]["message"]["content"]` 链式访问 �?视为违规
    - 代码�?`choices = response.get("choices", [])` + `if choices:` �?通过第一层校�?
  - **修复模式**�?
    ```python
    # �?三层级防御性解�?
    def _extract_llm_content(response: dict) -> str | None:
        # 第一层：choices 数组存在且非�?
        choices = response.get("choices") if isinstance(response, dict) else None
        if not choices or not isinstance(choices, list):
            logger.warning("LLM 响应缺少 choices 字段：{}", response)
            return None
        # 第二层：message 对象存在
        first = choices[0] if len(choices) > 0 else {}
        message = first.get("message") if isinstance(first, dict) else None
        if not message or not isinstance(message, dict):
            logger.warning("LLM 响应缺少 message 字段")
            return None
        # 第三层：content 字符串非�?
        content = message.get("content")
        if not content or not isinstance(content, str):
            logger.warning("LLM 响应 content 为空")
            return None
        return content.strip()

    # 禁止：链式访问任一层失败都会抛异常
    ```
  - **配置参数**：`llm_defensive_parsing.required_layers`（默�?`["choices", "message", "content"]`，必须校验的层级）、`llm_defensive_parsing.allow_empty_content`（默�?`false`，空 content 视为失败）、`llm_defensive_parsing.fallback_strategy`（默�?`return_none`，可�?`raise`）、`llm_defensive_parsing.supported_apis`（默�?`["openai_compatible", "anthropic", "ollama"]`）在 `config.yaml` �?`llm_defensive_parsing` 节点管理
  - **适用**：所有调�?LLM API 的代码（OpenAI 兼容协议 / Anthropic / 本地 Ollama / sentence-transformers）；流式响应（每�?chunk 也需校验�?
  - **不适用**：本地模型直接返回对象（�?JSON 解析）；Embedding API 响应（结构不同）；Mock 测试响应
  - **历史教训**：`_call_ai_suggestion` 直接 `response["choices"][0]["message"]["content"]`，LLM 服务异常时返�?`{"error": "..."}` 导致 KeyError 未捕获，AI 建议任务静默失败
- 🆕v4.19【强制�?*B-REVIEW-SELECTOR-REPOSITORY-SYNC：选择器仓库同步与单一数据�?*
  - 同一 DOM 数据源的所有解析路径（主解�?`_find_cards` / 批量解析 `_BATCH_PARSE_SCRIPT` / 降级解析）必须引用同一选择器仓库，JS 脚本必须动态拼接选择器字符串（禁止内�?CSS 选择器），ID 提取必须�?3 层兜底（data-* 属�?�?内部任意 a[href] �?/item/数字 路径），新增选择器候选时自动同步到所有解析路�?
  - **核心机制**（审查时必须理解）：
    - DOM 解析常有多条路径（主流程 `page.query_selector_all` + 批量脚本 `page.evaluate` 嵌入 JS + 降级 og:meta），若各路径独立维护选择器列表，闲鱼前端 DOM 变更时只改主解析器会遗漏批量脚本
    - JS 脚本字符串中硬编�?CSS 选择器无法被 Python 端静态检查，必须通过 f-string �?`.format()` 动态注�?
    - 选择器仓库（selector repository）需提供 `to_js_selector_string()` 方法，将 Python 列表转为 JS `document.querySelectorAll('...')` 可用的字符串
    - ID 提取单层失败即返�?None 会导致大量卡片被丢弃�? 层兜底保证极�?DOM 变更下仍能提�?
  - **判断信号**�?
    - `grep "document\.querySelectorAll" src/xianyu_hunter/modules/` 发现 JS 字符串中硬编码选择�?�?视为违规
    - 主解析器�?`card_selectors` 列表�?`_BATCH_PARSE_SCRIPT` 内的选择器字符串不一�?�?视为违规
    - 修改主解析器选择器后未同步批量脚本（grep 验证）→ 视为违规
    - DOM 解析脚本�?ID 提取只有单层无兜�?�?视为可疑
    - `grep "_BATCH_PARSE_SCRIPT\|_PARSE_SCRIPT" src/` 发现 JS 字符串中�?`'[class*='` 字面�?�?视为可疑
  - **修复模式**�?
    ```python
    # �?选择器仓库提�?Python �?JS 双端消费形式
    class SelectorRepository:
        def search_card_candidates(self) -> list[str]:
            """搜索卡片候选选择器（单一数据源）"""
            return [
                "[class*='feeds-item-wrap']", "[class*='feeds-item']",
                "[class*='item-card']", "[class*='search-item']",
                "[class*='product-card']", "[data-spm*='item']",
            ]
        def to_js_selector_string(self) -> str:
            """转为 JS document.querySelectorAll 可用的字符串"""
            return ", ".join(self.search_card_candidates())

    # �?批量解析脚本动态拼接选择�?
    def _build_batch_parse_script(self) -> str:
        js_selector = self.selectors.to_js_selector_string()
        return f"""
    () => {{
        const cards = document.querySelectorAll({js_selector});
        // ... 3 �?ID 提取兜底
    }}
    """

    # 禁止：JS 脚本硬编�?2 种选择器，与主解析器的 6 种不一�?
    ```
  - **配置参数**：`selector_repository_sync.enabled`（默�?`true`）、`selector_repository_sync.require_js_consumer_method`（默�?`true`，选择器仓库必须提�?`to_js_selector_string()` 方法）、`selector_repository_sync.audit_files`（默�?`["_search.py", "_parser.py", "_detail.py"]`，需稽查选择器一致性的文件）、`selector_repository_sync.batch_script_marker`（默�?`"_BATCH_PARSE_SCRIPT"`，批量解析脚本变量名标识）、`selector_repository_sync.require_id_fallback_layers`（默�?`3`，ID 提取兜底层数）在 `config.yaml` �?`selector_repository_sync` 节点管理
  - **适用**：同一 DOM 数据源有多条解析路径（主解析 + 批量解析 + 降级解析）；DOM 解析脚本嵌入�?Playwright `page.evaluate` 中执行；闲鱼/淘宝/第三方网站前�?DOM 结构频繁变更的场�?
  - **不适用**：API 响应解析（结构固定，�?DOM 选择器概念）；单次单卡片解析（无批量场景）；一次性爬虫脚本（无长期维护需求）
  - **历史教训**：DOM 回退模式检测到 31 个卡片，�?`_BATCH_PARSE_SCRIPT` 仅用 2 种选择器（`feeds-item-wrap`/`feeds-item`），�?`_find_cards` �?6 种选择器（�?`item-card`/`search-item`/`product-card`/`data-spm*='item'`）不一致，导致仅提取到 1 条数据。修复：选择器对齐为 6 �?+ 新增 3 �?ID 提取兜底（data-* 属性、内部任�?a[href]�?item/数字 路径�?
- 🆕v4.25【强制�?*B-REVIEW-CRITICAL-PATH-NO-SWALLOW：关键路径异常可见�?*
  - 启动钩子（`_on_startup`�? 迁移函数（`run_migrations`�? 初始化函数（`_init_*`）等关键路径的外�?except 必须�?`logger.exception()` 输出完整 traceback�?*禁止** `logger.warning(f"...{e}")` 丢失堆栈
  - **核心机制**（审查时必须理解）：
    - 关键路径的异常通常意味着系统无法正常启动或数据库 schema 不一致，必须保留完整堆栈用于事后排查
    - `logger.warning(f"...{e}")` 只输出异常消息字符串（如 "no such column: notifications.read_at"），丢失调用栈（哪一行触发、从哪里调用），难以定位根因
    - `logger.exception()` 自动附加完整 traceback，等同于 `logger.error(..., exc_info=True)`
    - 关键路径的异�?*不应被静默吞�?*——即使选择"忽略并继续启�?，也必须输出 ERROR 级别日志（含 traceback）让运维感知
  - **判断信号**�?
    - 代码�?`@app.on_event("startup")` / `def _on_startup` / `def run_migrations` / `def _init_*` + 外层 `except Exception as e: logger.warning(f"...{e}")` �?视为违规
    - 代码�?`except Exception as e: logger.warning("...: {}", e)` 在启动钩子中 �?视为违规（loguru 占位符也不保�?traceback�?
    - 代码�?`except Exception as e: logger.warning(f"启动迁移钩子失败（忽略）: {e}")` �?视为违规�?忽略"语义 + warning 级别 + �?traceback 三重问题�?
  - **修复模式**�?
    ```python
    # �?关键路径：用 logger.exception() 输出完整 traceback
    @app.on_event("startup")
    async def _on_startup() -> None:
        try:
            run_migrations(container)
            await _init_schedulers(container)
        except Exception:
            logger.exception("启动钩子失败，部分功能可能不可用")
            # 选择"忽略并继续启�?而非 raise，让主服务可�?

    # 禁止：warning + f-string 丢失堆栈
    # 禁止：silent pass 完全吞掉
    ```
  - **关键约束**�?
    - 关键路径函数清单（`_on_startup` / `run_migrations` / `_init_*`）在 `config.yaml` �?`critical_path_no_swallow.critical_functions` 节点管理，便于自动化扫描识别
    - 禁止日志模式（`logger.warning(f"...{e}")` / `logger.warning("...: {}", e)` / `except: pass`）在 `critical_path_no_swallow.forbidden_patterns` 节点管理
    - 允许的简�?warning 场景（非关键路径，如可选缓存失效）�?`critical_path_no_swallow.allowed_simple_warning` 节点管理，避免误�?
    - �?B-REVIEW-MIGRATION-BLOCK-ISOLATION 联动：迁移块各自 try/except 后，外层启动钩子仍需�?`logger.exception()` 兜底
    - �?B-REVIEW-MIGRATION-FAILURE-HANDLING 区别：本节点关注**外层**异常可见性，B-REVIEW-MIGRATION-FAILURE-HANDLING 关注**迁移函数内部**的策略（raise vs warn�?
  - **配置参数**：`critical_path_no_swallow.critical_functions`（关键路径函数名列表，如 `["_on_startup", "run_migrations", "_init_schedulers", "_init_components"]`）、`critical_path_no_swallow.require_exception_logger`（是否要�?`logger.exception()`，默�?`true`）、`critical_path_no_swallow.forbidden_patterns`（禁止的日志模式正则列表，如 `["logger\\.warning\\(f\".*\\{e\\}\"", "except.*pass"]`）、`critical_path_no_swallow.allowed_simple_warning`（允许简�?warning 的非关键路径函数名列表，�?`["_refresh_cache", "_cleanup_temp"]`）在 `config.yaml` �?`critical_path_no_swallow` 节点管理
  - **适用**：启动钩子（`@app.on_event("startup")`）；数据库迁移函数（`run_migrations` / `_migrate_*`）；组件初始化函数（`_init_*`）；任何"失败即影响核心功�?的关键路�?
  - **不适用**：非关键路径（如可选缓存刷新、临时文件清理）；已�?B-REVIEW-MIGRATION-FAILURE-HANDLING 管控的迁移函数内部策略；用户请求处理（应由路由层异常处理器管控）
  - **历史教训**：`_on_startup` 的外�?`try/except Exception as e: logger.warning(f"启动迁移钩子失败（忽略）: {e}")` 吞掉�?`run_migrations` �?C-01 `auto_migrate_task_links()` 的异常，日志仅显�?"启动迁移钩子失败（忽略）: ...",无法定位是哪个迁移块失败。修复后改为 `logger.exception("启动钩子失败...")`，完�?traceback 暴露问题根因

### 12. 日志规约

- 【强制】使�?loguru（非 stdlib `logging`�?
- 【强制】三 sink 配置�?
  - stderr 彩色输出
  - JSON 文件按日滚动（保�?14 天）
  - 纯文本文�?
- 【强制】request_id 全链路追踪：`ContextVar` + loguru patcher 钩子
- 【强制】敏感数据脱敏：`_SENSITIVE_HEADERS` 包含 `authorization/cookie/xh_token/set-cookie`
- 【强制】异常必须包含异常对象：`logger.error("msg", e)`�?*禁止** `logger.error("msg")`�?
- 【强制】token 写入失败必须 `logging.warning()` 告警
- 【禁止】日志记录密�?密钥/Token 明文
- 【推荐】四级日志：ERROR（异�?失败�?/ WARN（潜在问题） / INFO（关键操作） / DEBUG（调试，生产关闭�?
- 【强制】loguru 日志使用 `{}` 占位符，**禁用** `%s`/`%d`/`%f` printf 风格（loguru 不解析，导致参数未替换）
  - �?`logger.info("task={} rows={}", task_id, rows)`
  - �?`logger.info("task=%s rows=%d", task_id, rows)` �?输出原始 `%s`/`%d`
- 【强制】耗时日志使用 `{:.1f}` 格式化毫秒值，保留一位小�?
- 🆕v4.10【强制�?*B-REVIEW-LOGURU-PLACEHOLDER：日志库占位符一致�?*
  - 项目选定单一日志库后（如 loguru），所�?`logger.xxx()` 调用必须使用该库的占位符语法�?*禁止**混用其他日志库的占位符（loguru �?`{}`，标�?logging �?`%s`/`%d`�?
  - **核心机制**（审查时必须理解）：
    - loguru 不识�?`%s`/`%d` 占位符，但混�?*不会抛异�?*，会导致日志输出"%s"字面量而非实际值，极难发现
    - 标准 logging 不识�?`{}` 占位符，混用同样不抛异常但输�?{}"字面�?
    - f-string �?Python 原生字符串拼接，与日志库无关，简单拼接可用，但复杂格式推荐用占位符（性能更好，延迟格式化�?
  - **判断信号**�?
    - 项目�?loguru（`from loguru import logger`）但代码�?`logger.xxx("...%s...", arg)` �?视为违规
    - 项目用标�?logging 但代码含 `logger.xxx("...{}...", arg)` �?视为违规
    - 日志输出�?`%s`/`%d`/`{}` 字面量而非实际�?�?典型症状
    - `grep -nE 'logger\\.(debug|info|warning|error|critical).*%[sdrf]' file.py` 命中 �?loguru 项目混用 `%s` 违规
  - **修复模式**�?
    ```python
    # �?loguru：{} 占位�?
    from loguru import logger
    logger.info("用户 {} 登录，耗时 {:.2f}s", user, elapsed)
    logger.warning("Cookie 刷新失败，原因：{}", reason)

    # 禁止：loguru 项目混用 %s（不抛异常但输出 "%s" 字面量）
    # �?标准 logging�?s 占位�?
    import logging
    logger = logging.getLogger(__name__)
    logger.info("用户 %s 登录", user)

    # �?f-string 例外（简单拼接可用）
    logger.info(f"用户 {user} 登录")
    ```
  - **配置参数**：`log_placeholder.logger_lib`（默�?`loguru`，可�?`logging`/`structlog`）、`log_placeholder.placeholder_pattern`（默�?`\\{\\}` �?loguru，`%[sdrf]` �?logging）、`log_placeholder.forbidden_pattern`（默�?`%[sdrf]` �?loguru 项目）、`log_placeholder.logger_method_names`（默�?`["debug", "info", "warning", "error", "critical"]`）、`log_placeholder.allow_fstring`（默�?`true`，允许简�?f-string 拼接）在 `config.yaml` �?`log_placeholder` 节点管理
  - **诊断流程**（出�?日志输出 %s 字面�?类问题时执行）：
    1. `grep -nE 'logger\\.(debug|info|warning|error|critical).*%[sdrf]' src/` 扫描所�?logger 调用
    2. 确认项目使用的日志库（`grep "from loguru" src/` vs `grep "import logging" src/`�?
    3. 若是 loguru 项目，所�?`%[sdrf]` 占位符均为违规，改为 `{}`
    4. 若是 logging 项目，所�?`{}` 占位符均为违规，改为 `%[sdrf]`
  - **适用**：所有用 loguru/standard logging/structlog 的项目；混用多个日志库的项目（需统一到单一日志库）
  - **不适用**：未使用日志库的项目（如仅用 print）；自定义日志库（需在配置中声明占位符语法）
  - **历史教训**：`cookie_rotator.py` �?197�?45 行用 `logger.warning("...%s...", reason)`（loguru 项目混用 `%s`），loguru 不识�?`%s` 占位符但不抛异常，导致日志输�?Cookie 刷新失败，原因：%s"字面量。修复后改为 `logger.warning("...{}", reason)`

### 13. 代码质量

- 【强制】缺失导入检查（`re`、`threading`、`logging` 等必须在模块级导入，避免函数�?NameError�?
- 【强制】函数内冗余导入移到模块�?
- 【强制】异�?同步混用检查（`await` 是否用于同步方法�?
- 【强制】`ImportError` 检查（异常类、符号是否正确导入）
- 【强制�?*async/await 一致�?*：异步方法调用必须保�?`await`，合并冲突时优先保留异步版本
- 🆕【强制�?*S3776**：认知复杂度 �?15，拆分大函数为多个小函数
  - **实战案例**�?
    - `login_orchestrator.start_session` 拆为 7 个小方法（`_validate_session/_acquire_browser/_navigate_login/_wait_for_qrcode/_poll_session_status/_update_token_store/_emit_started_event`�?
    - `cookie_store.upsert_cookie_values` 拆为 4 个小方法（`_resolve_existing_user/_upsert_user_record/_upsert_cookies/_cleanup_orphans`�?
- 🆕【强制�?*S6767**：未使用的参�?属�?局部变�?——立即删除或�?`_` 前缀
- 🆕【强制�?*S1192**：重复的字符串字面量 ——提取为模块级常量（�?`_TASK_NOT_FOUND = "任务不存�?`�?
- 🆕【强制�?*S5843**：正则表达式复杂度过�?——可拆分为多个简单正则或改用字符串方�?
- 【推荐】代码重复检查（DRY 违规�?
- 【推荐】函数职责单一性（SRP），超长函数拆分
- 【推荐】深层嵌�?�?4 层，复杂条件提取为命名变量或函数
- 【推荐】魔法数�?字符串提取为常量
- 【推荐】注释解�?为什�?而非"做什�?
- 🆕v4.0【强制�?*注释与代码一致�?*：注释必须与代码逻辑严格一致，禁止误导性注�?
  - 防御性说明需明确标注�?防御�?而非"必需"（如"顺序不影响结果，但保留防御性排�?�?
- 🆕v4.5【强制�?*B-REVIEW-DEAD-CODE-CLEANUP：死代码检测与清理**
  - 业务流程�?*未在任何调用点被触发的函�?方法**必须在每次大版本（v4.x �?v4.x+1）时主动检测并清理
  - **判断信号**�?
    - 函数被定义（�?`def on_login_success(self): ...`）但 `grep -rn "on_login_success" src/` 找不到任何调�?
    - 事件订阅被注册但 `grep` 不到发布�?
    - 抽象方法被子类实现但从未被子类外部调�?
  - **检测方�?*�?
    1. `git log -p --all -S "<function_name>"` 查看该函数的所有历史变�?
    2. `grep -rn "<function_name>" src/ tests/` 确认无任何调用方
    3. �?PR/Commit 描述中显式标�?删除死代�?X"
  - **修复模式**�?
    - **找到调用�?*：恢复调用路径（适合误删调用方导致的死代码）
    - **改写为入口函�?*：将死代码改写为"统一同步入口"（如 `on_login_success` 改写�?`sync_cookie_layers_from_json`�?
    - **直接删除**：无任何依赖时直接删�?
  - **配置参数**：`dead_code_check_enabled`（默�?`true`）、`dead_code_ignore_list`（保留作�?API 接口的方法名白名单）�?`config.yaml` �?`dead_code_cleanup` 节点管理
  - **适用**：所�?定义即遗�?的函�?回调/事件订阅/类方�?
  - **不适用**：保留作�?API 接口的方法（即便未被内部调用）、测�?fixture、抽象基�?
  - **历史教训**：`CookieRotator.on_login_success` 方法被定义后从未被任何登录路径调用，"逻辑上应该被触发"但实际是死代码，导致登录后层状态永远不更新
  - 涉及顺序约束、依赖关系的注释需验证是否真实存在该约�?
  - **历史教训**：注释称"必须�?X 之前判断避免误匹�?，但实际不存在误匹配风险
- 🆕v4.6【强制�?*B-REVIEW-REUSE-PATTERN：复用既有模式原�?*
  - 新增功能前必须先 `grep` 项目内相似实现，复用既有 helper / 工具函数 / 模式（如 `_utcnow` / `_escape_like` / `hmac.compare_digest` / `asyncio.wait_for` / `logger.warning`），**禁止**重复造轮子或实现已有模式的变�?
  - **判断信号**：新增函�?+ `grep` 发现已有相似命名/相似参数/相似功能的函�?�?必须复用而非重复实现；新增异步操作未复用 `asyncio.wait_for` 模式 �?视为违规
  - **修复模式**�?
    1. **搜索阶段**：`grep -rn "<相似关键�?" src/` 查找已有实现
    2. **评估阶段**：对比新增函数与已有函数的差异（参数差异 / 返回值差�?/ 副作用差异）
    3. **复用阶段**：直接调用已有函�?/ 抽取公共部分�?helper / 在已有函数上增加参数
    4. **文档阶段**：在新增函数 docstring 中说�?为什么不复用 X"（如适用�?
  - **关键约束**�?
    - 复用优先级：**项目�?helper > 标准�?> 第三方库 > 新实�?*
    - 复用必须**保持一致�?*：调用方式、参数命名、返回值格式与已有函数一�?
    - 若已有函数不完全满足需求，�?*扩展已有函数**而非新建（参�?B-REVIEW-FILTER-SCENARIO 参数化场景标志）
    - 必须复用的常见模式：`asyncio.wait_for`（异步超时）、`hmac.compare_digest`（凭据比较）、`_escape_like`（SQL LIKE 转义）、`_utcnow`（UTC 时间）、`logger.warning`（告警日志）
  - **配置参数**：`search_keywords`（必须搜索的关键词列表）、`similarity_threshold`（默�?0.7，相似度高于此值时强制复用）、`reuse_priority`（复用优先级顺序）在 `config.yaml` �?`reuse_pattern` 节点管理
  - **适用**：所有新增功�?/ 工具函数 / 帮助�?/ 异步操作 / 安全相关代码
  - **不适用**：业务完全独立的全新功能、性能优化重写、技术债清理重�?
  - **历史教训**：`refresh_item` 直接 `await collector.detail()` 而未复用 v4.4 �?fast 模式重试机制（`fast=False` 重试一次），也未加 `asyncio.wait_for` 整体超时（B-REVIEW-ASYNC-TIMEOUT 规范），导致浏览器异常时无限挂起。修复时复用 `asyncio.wait_for` 模式 + 504 状态码（与 v4.1 错误粒度三类区分一致）
- 🆕v4.11【强制�?*B-REVIEW-NUMERIC-EXTRACTION：文本数值提取模�?*
  - 从可能含多个数字的文本中提取数值时，必须用 `re.findall` �?`numbers[-1]`（最后一个数字）�?*禁止** `re.search` 取第一个数字，因实际成交价/当前值通常出现在最后（�?原价 1000 现价 500"应取 500�?
  - **核心机制**（审查时必须理解）：
    - 自由文本中可能含多个数字（原�?现价、最小�?最大值、原数量/现数量）
    - 实际成交�?当前值通常出现在最后（"原价 X 现价 Y"�?�?X 降到 Y"�?
    - `re.search` 只取第一个匹配，会误取原�?最小�?
    - `re.findall` 返回所有匹配，�?`[-1]` 获取最后一个（实际值）
  - **判断信号**�?
    - 代码�?`re.search(r"\d+", text)` �?`re.match(r"\d+", text)` 提取数�?�?必须评估文本是否可能含多数字
    - 代码�?`m = re.search(r"\d+(?:\.\d+)?", text)` �?`float(m.group())` �?多数字场景会误取第一�?
    - 用户反馈"价格提取错误"�?数值字段显示为原价而非现价" �?典型症状
  - **修复模式**�?
    ```python
    # �?取最后一个数字（实际成交价）
    import re
    text = "原价 1000 现价 500"
    numbers = re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))
    if numbers:
        actual_price = float(numbers[-1])  # 500，正�?

    # 禁止：取第一个数字（误取原价�?
    # �?有明确位置的文本用分组提取（例外场景�?
    m = re.search(r"价格:\s*(\d+(?:\.\d+)?)", text)
    if m: price = float(m.group(1))  # 分组提取，明确位�?
    ```
  - **配置参数**：`numeric_extraction_strategy.default_strategy`（默�?`last`，可�?`first`/`max`/`min`）、`numeric_extraction_strategy.scenarios`（场景到策略的映射，�?`price_extraction �?last`、`quantity_extraction �?first`、`max_value_extraction �?max`）、`numeric_extraction_strategy.regex_pattern`（默�?`r"\d+(?:\.\d+)?"`）在 `config.yaml` �?`numeric_extraction_strategy` 节点管理
  - **适用**：从自由文本提取数值（价格/数量/评分/版本号）；多数字场景�?原价 X 现价 Y"�?最�?X 最�?Y"�?
  - **不适用**：单一数字文本（如纯数字字符串 "123"）；结构化数据（JSON 字段直接取值）；有明确位置的文本（�?价格:X"�?`re.search(r"价格:\s*(\d+)", text)` 分组提取�?
  - **历史教训**：`_extract_actual_price` �?`re.search` 取第一个数字，订单页文本为"原价 1000 现价 500"时误�?1000，导致价格校验失败抢单被�?
- 🆕v4.14【强制�?*B-REVIEW-DEBUG-CODE-CLEANUP：临�?DEBUG 代码清理**
  - 临时 DEBUG 代码在问题修复后必须移除�?*禁止**留在生产代码中。DEBUG 代码包括：临�?import（如 `import os as _os`）、临时环境变量检查（�?`environ.get("DEBUG")`）、临时日志文件写入（�?`open("debug.log", "w")`）、临时打印语句（�?`print("DEBUG: ...")`）。问题修复后必须 grep 所�?DEBUG 代码并移除，避免污染生产环境
  - **判断信号**：代码含 `import os as _os` / `environ.get("DEBUG")` / `open("debug.log")` / `print("DEBUG")` / `logger.debug` 异常密集 �?必须检查是否为临时 DEBUG 代码；问题修复后 grep 仍有 DEBUG 代码 �?必须移除
  - **修复模式**�?
    ```python
    # 禁止：问题修复后仍保�?DEBUG 代码
    # �?正确：问题修复后移除所�?DEBUG 代码
    # grep -rn "DEBUG\|debug\.log\|import os as _os\|environ.get(\"DEBUG\")" src/
    # 确认无残�?DEBUG 代码
    ```
  - **配置参数**：`debug.enabled`（默�?`false`，生产环境禁�?DEBUG 代码）、`debug.cleanup_after_fix`（默�?`true`，问题修复后自动清理 DEBUG 代码）、`debug.whitelist`（长期监控指标白名单，如 `["performance_metrics", "health_check"]`）在 `config.yaml` �?`debug` 节点管理
  - **适用**：临时调试代码、排查问题后的清理、开发环境调�?
  - **不适用**：日志级别动态降级（需保留配置）、长期监控指标收集（需保留）、性能埋点（需保留�?
  - **历史教训**：登录流程问题排查时添加 `import os as _os` �?`open("debug.log", "w")` 写入调试信息，问题修复后未移除，导致生产环境产生 debug.log 文件污染日志目录

- 🆕v4.16【强制�?*B-REVIEW-DIVZERO-FALLBACK：除零兜底禁止凑�?*
  - **判断信号**：grep ` / 0\.` �?`/ 0.1` �?`/ max(*, 1)` 等可疑除零兜底；比�?比率/百分比计算中 previous_count/baseline 可能�?0
  - **强制规则**：除�?空值兜底禁止用凑数小数（`x / 0.1`）伪装比值；比�?比率/百分比计算中 previous_count/baseline 可能�?0 时直接置�?`0.0` �?`float('inf')`；写�?reason/log 展示给用户的数值无意义时用字符�?`"N/A"` 而非数字
  - **反例**：`ratio = recent_count / 0.1 if recent_count > 0 else 0.0`（previous=0 �?ratio=100.0 误导用户�?
  - **正例**：`if previous_count > 0: ratio = recent_count / previous_count else: ratio = 0.0` + `ratio_str = f"{ratio}x" if previous_count > 0 else "N/A"`
  - **配置参数**：`divzero_fallback` 节点（enabled / detect_patterns / display_value_for_empty_baseline�?
  - **适用场景**：比�?比率/百分比计算；previous_count/baseline 可能�?0 的对比场景；写入 reason/log 展示给用户的数�?
  - **不适用场景**：内部计算用途的兜底（如 max(prev, 1) 防止除零但结果不展示）；倒计�?计时器场�?
- 🆕v4.19【强制�?*B-REVIEW-EXTERNAL-TEXT-PATTERN-CENTRALIZE：外部系统文本特征集中管�?*
  - 外部系统（闲�?淘宝/第三�?API）的文本特征（已售关键词/错误�?状态文�?反爬识别）必须提取为模块级常量（`tuple[str, ...]` �?`frozenset[str]`），多处消费点必须复用同一纯函数（`check_xxx(text: str) -> bool`），禁止在消费点内联关键词列表（�?`if "已售" in text`），关键词清单变更时只需修改单一常量
  - **核心机制**（审查时必须理解）：
    - 外部系统文案会频繁变更（如闲�?已售" �?"卖掉�?），分散在多个文件的关键词列表必然漏�?
    - 模块级常量（`tuple[str, ...]`）不可变，便于扩展且线程安全
    - 纯函数（`check_xxx(text) -> bool`）无副作用，便于单测，多处消费点 import 同一函数
    - 关键词清单定义处必须注释历史遗漏案例，说明为什么集中维�?
  - **判断信号**�?
    - `grep "已售\|卖掉了\|已下架\|已删�? src/xianyu_hunter/` 发现同一关键词在多个文件重复 �?视为违规
    - 代码�?`if "xxx" in text` 但未调用统一函数 �?视为违规
    - 关键词以列表字面量出现在函数内部而非模块级常�?�?视为可疑
    - `grep "check_text_sold\|check_item_sold"` 调用�?< 定义�?�?视为可疑（有内联替代�?
  - **修复模式**�?
    ```python
    # �?单一常量 + 纯函�?+ 3 处复�?
    # collector_utils.py
    SOLD_TEXT_KEYWORDS: tuple[str, ...] = (
        "已售", "已售�?, "已售�?, "已售�?, "宝贝已售", "商品已售",
        "已下�?, "已卖�?,
        "卖掉�?,  # 闲鱼新版文案�?026-06-29 发现�?
        "宝贝不存�?, "宝贝走丢�?, "该宝贝不存在", "商品不存�?, "已删�?, "已被删除",
    )

    def check_text_sold(text: str) -> bool:
        """检测页面文本是否表示商品已售�?

        为什么集中维护：闲鱼前端文案多次变更，分散在 3 个文件的关键词列表容易漏改�?
        历史遗漏案例�?026-06-29 发现商品 1058031608014 详情页显�?卖掉�?但被误判为在售�?
        """
        if not text:
            return False
        return any(kw in text for kw in SOLD_TEXT_KEYWORDS)

    # _detail.py / _parser.py / buyer.py 统一复用
    from xianyu_hunter.modules.collector_utils import check_text_sold
    is_sold = check_text_sold(body_text)

    # 禁止�? 处独立关键词列表，新增文案时漏改
    ```
  - **配置参数**：`external_text_pattern_centralize.enabled`（默�?`true`）、`external_text_pattern_centralize.require_constant_extraction`（默�?`true`，强制提取为模块级常量）、`external_text_pattern_centralize.require_pure_function`（默�?`true`，强制封装为纯函数）、`external_text_pattern_centralize.audit_keywords`（默�?`["已售", "卖掉�?, "已下�?, "已删�?]`，需要稽查的关键词样例）、`external_text_pattern_centralize.max_inline_occurrences`（默�?`1`，同一关键词在代码中出�?>1 次且未引用常�?�?违规）、`external_text_pattern_centralize.require_version_comment`（默�?`true`，常量定义处必须注释历史遗漏案例）在 `config.yaml` �?`external_text_pattern_centralize` 节点管理
  - **适用**：外部系统文案检测（已售/下架/错误状�?异常提示）；错误码识别（HTTP 状态码/业务错误�?反爬识别）；第三�?API 响应文本特征提取；多处消费同一类文本特征的场景
  - **不适用**：内部状态判断（�?`task.status == 'completed'`，前端可控）；单一消费点的临时字符串比较；配置文件中已管理的关键词（无需再提取为代码常量�?
  - **历史教训**：商�?1058031608014 实际已售（详情页 body 文本�?卖掉�?），�?3 处独立关键词列表（`_detail.py` / `_parser.py` / `buyer.py`）都未包�?卖掉�?，导致系统误判为在售，用户看到已售商品仍被推荐。Chrome DevTools MCP 实际打开页面�?body 文本才发现该关键词。修复后提取 `SOLD_TEXT_KEYWORDS` 常量 + `check_text_sold()` 函数�?`collector_utils.py`�? 处复�?

### 14. 配置管理

- 【强制】使�?`pydantic-settings` + `keyring` + `.env` 三层配置�?
- 【强制】`get_settings()` �?`@lru_cache` 单例
- 【强制】敏感字段（推�?Key 等）写入 keyring，`.env` 仅放占位�?
- 【强制】环境变量优先级：env > .env > 配置文件默认�?
- 【强制】`update_ai_config()` 热更新：写入 `.env` + keyring
- 【强制】Embedding 配置独立�?LLM 配置
- 【强制】HuggingFace 镜像：`local_embedding.py` 模块顶层�?*�?* `import sentence_transformers` 之前）`os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")`
- 【强制】sentence-transformers 5.x 兼容：`getattr(model, "get_sentence_embedding_dimension", getattr(model, "get_embedding_dimension", None))()`
- 【强制】当 `EMBEDDING_BASE_URL` 为空�?"local" 时，使用本地 sentence-transformers 后端（BAAI/bge-small-zh-v1.5，dim=512�?
- 🆕v4.3【强制�?*B-REVIEW-CONFIG-DRIVEN-TOGGLE：配置驱动功能开关模�?*
  - 高风�?高资源消耗功能默认关闭，需用户显式启用；所有功能参数集中在 `Config` 类（�?`BrowserConfig`），不硬编码
  - **判断信号**：功能需用户主动选择 + 可能耗资源（CPU/内存/网络�?+ 多环境部署需�?
  - **修复模式**：`Config` 类新�?`enable_flag: bool = False` + 详细参数字段 �?`config.yaml` 暴露开�?�?文档明确启用条件与资源消�?
  - **配置参数**：`enable_flag` 默认 `false`，详细参数（interval/threshold/port）集中在相应 `Config` 类，`config.yaml` �?`feature_toggles` 节点管理开�?
  - **适用**：CDP 在线导入、Cookie 自动同步、向量库重建等高风险/高资源消耗功�?
  - **不适用**：核心功能（必须默认启用）、性能敏感场景（配置加载延迟不可接受）、简单脚本工�?
  - **历史教训**：`auto_sync` 默认 `false`，避免用户不知情下启用自动同步导致浏览器资源被占用；`cdp_port` 通过 `BrowserConfig` 管理而非硬编�?
- 🆕v4.4【强制�?*B-REVIEW-CONFIG-LINKAGE：配置全链路生效验证**
  - 配置项从定义到消费必须全链路追踪�?*禁止**只注入到中间层就认为生效
  - **判断信号**：`config.yaml` 新增字段 �?Config 类有字段 �?TaskConfig 注入 �?�?Worker/Module/方法参数中从未读�?`self.config.xxx` �?配置无效
  - **检查方�?*：grep 每个配置项的字段名，确认从定义到最终消费点（URL 构建方法、SQL 查询、阈值比较）都有读取代码
  - **配置参数**：配置链路追踪检查清单在 `config.yaml` �?`config_linkage_checks` 节点管理
  - **适用**：所有配置项（搜索参数、阈值、间隔、开关），尤其是新增配置项后
  - **不适用**：编译期常量、安全固定值（�?`path: "/"`�?
  - **历史教训**：`search_sort_type` �?`search_regions` �?`startup.py` 注入�?TaskConfig，但 `worker.py` �?`_search.py` 从未读取，`build_search_url` 也不支持这两个参数。用户在配置页设置了排序方式但搜�?URL 中从不包�?`&sortType=...` 参数
- 🆕v4.5【强制�?*B-REVIEW-POST-WRITE-HOOK：写后钩子（Post-Write Hook）规�?*
  - 所�?写主数据�?+ 同步派生状�?的操作必须实�?*显式写后钩子**——禁止依赖隐式回调、事件总线自动触发、定时器轮询
  - **判断信号**：派生状态（缓存 / 索引 / 内存模型）需要与主数据源保持一致，但代码中只在某个特定入口同步 �?其他写入路径遗漏
  - **修复模式**�?
    - 在每个写入路径的成功分支（`if json_written: ...`）添加显式调�?
    - 钩子函数�?*幂等**：可重复调用而不会产生副作用
    - 钩子失败必须**仅记录日志不抛异�?*：派生状态同步失败不能阻断主写入
    - 钩子逻辑�?*重新读主数据�?*而非用调用方传入的列表（避免过滤逻辑不一致）
  - **典型实现**�?
    ```python
    if json_written:
        try:
            sync_cookie_layers_from_json()
        except Exception as e:
            logger.debug("写后钩子失败（不影响主流程）: %s", e)
    ```
  - **配置参数**：`post_write_hooks`（钩子函数名列表）、`write_entry_paths`（需要触发钩子的写入路径）在 `config.yaml` �?`post_write_hooks` 节点管理
  - **适用**：所�?写后需要同步派生状�?的场景（Cookie 状态机、缓存失效、索引重建、计数器重置�?
  - **不适用**：单写入入口且无派生状态、性能敏感场景（钩子开销不可接受�?
  - **历史教训**：登录路径写 JSON 后没有任何钩子触�?`CookieRotator.sync_state_from_cookies()`，导致层状态永远停留在 `valid=False, updated_at=0.0`，`/cookies/layers` 显示三层全部失效
- 🆕v4.11【强制�?*B-REVIEW-CONFIG-VALIDATION：配置项边界值校�?*
  - 数值型配置项必须有边界值校验（min/max/non_zero/range），加载时主动校验，无效值用默认值并 `logger.warning` 告警�?*禁止**直接使用未校验的数值导致运行时 ZeroDivisionError / ValueError
  - **核心机制**（审查时必须理解）：
    - `config.yaml` 数值字段可能被用户设置�?0、负数、极大值等非法�?
    - 代码�?`interval / N` �?`count * factor` 等算术运算时�? 会触�?ZeroDivisionError，负数会触发 ValueError
    - 配置加载时主动校�?+ 默认值兜底是防御性编程的最佳实�?
  - **判断信号**�?
    - `config.yaml` 新增数值字�?+ 代码用该字段做算术运�?�?必须校验除数非零、乘数有�?
    - 代码�?`interval = config.get("xxx_interval", 60)` 后直�?`await asyncio.sleep(interval / 2)` �?必须校验 interval > 0
    - 代码�?`max_retries = config.get("max_retries", 3)` 后直�?`for _ in range(max_retries)` �?max_retries 应为非负整数
  - **修复模式**�?
    ```python
    # �?加载时校�?+ 默认值兜�?
    interval = config.get("ai_suggestion_interval", 60)
    if not isinstance(interval, (int, float)) or interval <= 0:
        logger.warning("ai_suggestion_interval 配置无效（{}），使用默认�?60", interval)
        interval = 60
    # 使用 interval 做算术运算前已校验非�?
    await asyncio.sleep(interval / 2)

    # 禁止：未校验直接使用
    ```
  - **配置参数**：`config_validation.rules`（每条规则含 `field`/`min`/`max`/`non_zero`/`regex`/`default`）、`config_validation.on_invalid`（默�?`warn_and_fallback`，可�?`raise`）在 `config.yaml` �?`config_validation` 节点管理
  - **适用**：所有数值型配置项（间隔时间/阈�?并发�?超时/重试次数）；字符串枚举值（�?regex 校验�?
  - **不适用**：布尔型配置项（无需校验范围）；纯展示型字符串（如标题）；编译期常量
  - **历史教训**：`ai_suggestion_interval=0` 未校验直接用�?`asyncio.sleep(interval / 2)` 导致 ZeroDivisionError，任务循环崩�?
- 🆕v4.12【强制�?*B-REVIEW-DOM-FALLBACK-CHAIN：DOM 多层兜底链模�?*
  - SPA/动态页面数据提取必须在主路径失败时按序尝试多层兜底（DOM 选择�?�?`meta[property='og:title']` �?`document.title`），**禁止**单一选择器失败即整体失败
  - **核心机制**（审查时必须理解）：
    - SPA 站点 DOM 结构会随版本迭代变化，单一选择器脆弱性高
    - `og:meta` �?`document.title` 由网站框架稳定维护，是可靠的兜底�?
    - 兜底链按"语义忠实�?递减排序，最终兜底必须保证非空（�?`document.title` 兜底但应标注 `title_source: 'fallback'`�?
  - **判断信号**�?
    - 代码�?`page.locator(...).text_content()` / `await page.querySelector(...)` 后直接返回结�?�?检查是否有兜底
    - 选择器失败抛 `TimeoutError`/`ElementNotFound` 但代码未捕获 �?违规
    - 数据提取函数返回值可能为 `None` 但调用方未做空值检�?�?违规
  - **修复模式**�?
    ```python
    # �?多层兜底�?
    title = await page.locator(SELECTORS["title"]).text_content()
    if not title:
        # DOM 主路径失�?�?og:meta 兜底
        title = await page.get_attribute("meta[property='og:title']", "content")
    if not title:
        # og:meta 失败 �?document.title 最终兜底（保证非空�?
        title = await page.title()
        title_source = "fallback"
    else:
        title_source = "primary"
    ```
    ```python
    # 禁止：单一选择器，无兜�?
    ```
  - **配置参数**：`dom_fallback_chain.strategies`（兜底层级列表，�?`["dom", "og_meta", "document_title"]`）、`dom_fallback_chain.dom_selectors`（主路径选择器集合，业务场景�?key）、`dom_fallback_chain.meta_selectors`（og:meta 选择器集合）、`dom_fallback_chain.final_fallback`（最终兜底函数名）、`dom_fallback_chain.dump_on_all_fail`（全部失败时是否触发 dump，与 `failure_dump` 联动）在 `config.yaml` �?`dom_fallback_chain` 节点管理（与 v4.3 B-REVIEW-FALLBACK-CHAIN �?多方案降�?语义不同，本节点专指 DOM 提取兜底�?
  - **适用**：SPA 数据采集（标�?价格/卖家/图片）、动态渲染页面的关键字段提取、可能因站点改版失效�?DOM 选择�?
  - **不适用**：静�?JSON API（结构稳定，单一解析即可）、写入操作（无兜底语义）、用户输入校�?
  - **历史教训**：官方采集仅�?`.item-title` 单一选择器，闲鱼页面改版后选择器失效直接返�?`title=None`，下游字段覆盖逻辑�?None 覆盖历史有效值，最终用户看�?采集失败"
- 🆕v4.12【强制�?*B-REVIEW-FAILURE-DUMP：失败诊�?dump 机制**
  - 关键选择器失败或数据提取异常时必须自�?dump `page.content()` 到本地文件，便于离线复现；dump 操作不得阻塞主流程（异步执行�?fire-and-forget�?
  - **核心机制**（审查时必须理解）：
    - 采集�?bug 在生产环境难以复现（依赖具体页面状�?Cookie/时序�?
    - dump 完整 HTML 后可在本地用 `page.set_content()` 重放调试
    - dump 文件需按场景归档，含时间戳与业�?ID 便于关联日志
  - **判断信号**�?
    - 代码�?`except ElementNotFound`/`except TimeoutError` 但未触发 dump �?违规
    - dump 操作�?`await` 阻塞主流�?�?违规（应 fire-and-forget �?`asyncio.create_task`�?
    - dump 文件名不含时间戳或场景标�?�?排查困难，违�?
    - dump 文件未做大小限制/数量限制 �?可能撑爆磁盘
  - **修复模式**�?
    ```python
    # �?异步 dump，不阻塞主流�?
    async def _dump_html(scenario: str, biz_id: str, page: Page) -> None:
        try:
            content = await page.content()
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = Path("logs") / f"{scenario}_{biz_id}_{ts}.html"
            # 异步写入（任何失败仅 debug 日志，不影响主流程）
            await asyncio.to_thread(path.write_text, content, encoding="utf-8")
        except Exception as e:
            logger.debug("dump 失败（不影响主流程）: {}", e)

    # 主流程：选择器失败时 fire-and-forget dump
    try:
        title = await page.locator(SELECTORS["title"]).text_content()
    except (ElementNotFound, TimeoutError):
        asyncio.create_task(_dump_html("official_collect", task_id, page))
        title = None  # 走兜底链
    ```
    ```python
    # 禁止：阻塞主流程 + 无场景标�?
    ```
  - **配置参数**：`failure_dump.enabled`（总开关）、`failure_dump.dump_dir`（输出目录，默认 `logs/`）、`failure_dump.filename_pattern`（文件名模板，如 `{scenario}_{id}_{timestamp}.html`）、`failure_dump.max_file_size_mb`（单文件大小上限）、`failure_dump.max_files_per_scenario`（每场景保留文件数上限）、`failure_dump.scenarios`（启�?dump 的场景列表）、`failure_dump.sensitive_patterns`（需脱敏的正则列表，�?cookie/token）在 `config.yaml` �?`failure_dump` 节点管理
  - **适用**：所�?Playwright/浏览器自动化采集、DOM 选择器失败时、关键路径异常时
  - **不适用**：纯 API 调用（已有完整请�?响应日志）、本地纯函数（无外部状态）、单�?集成测试场景
  - **历史教训**：官方采集失败时仅日志记�?选择器失�?，无法定位是页面改版还是 Cookie 失效，需用户手动复现；引�?dump 后离线分析即可定�?
- 🆕v4.12【强制�?*B-REVIEW-TIMING-INSTRUMENTATION：关键路径计时埋�?*
  - 关键路径操作（`page.goto`/`wait_for_selector`/HTTP 调用/DB 查询）必须用 `time.perf_counter()` 计时并按阈值告警，**禁止**仅用 `logger.info("开�?)`/`logger.info("结束")` 文本日志（难以聚合分析）
  - **核心机制**（审查时必须理解）：
    - 性能问题排查依赖结构�?timing 数据，文本日志需正则解析不可�?
    - `time.perf_counter()` �?`time.time()` 精度高（纳秒级），不受系统时间回拨影�?
    - 超阈值告警便于运维主动发现性能退化，而非用户报障
  - **判断信号**�?
    - 代码�?`await page.goto(...)` / `await page.wait_for_selector(...)` / `await http_client.get(...)` 但前后无 `perf_counter()` 计时 �?违规
    - �?`time.time()` 计时（精度低）→ 建议改为 `perf_counter()`
    - 计时结果�?`logger.debug` 不做阈值判�?�?超阈值无法告�?
    - 计时埋点�?try/finally 包裹�?finally 内引用变量未前置初始�?�?�?B-REVIEW-TRY-FINALLY-INIT 联动违规
  - **修复模式**�?
    ```python
    # �?perf_counter + 阈值告�?
    t0 = time.perf_counter()
    try:
        await page.goto(url, wait_until="domcontentloaded")
    finally:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        threshold = config.get("timing.goto_threshold_ms", 5000)
        if elapsed_ms > threshold:
            logger.warning("page.goto �? {:.0f}ms > {}ms, url={}", elapsed_ms, threshold, url)
        else:
            logger.debug("page.goto: {:.0f}ms, url={}", elapsed_ms, url)
    ```
    ```python
    # 禁止：无计时 / 文本日志无法聚合
    ```
  - **配置参数**：`timing_instrumentation.thresholds_ms`（按操作类型配置阈值，�?`{goto: 5000, wait_for_selector: 3000, http_request: 2000, db_query: 1000}`）、`timing_instrumentation.log_level_normal`（正常日志级别，默认 `DEBUG`）、`timing_instrumentation.log_level_slow`（超阈值日志级别，默认 `WARNING`）、`timing_instrumentation.enabled_scenarios`（启用计时的场景列表）、`timing_instrumentation.timer_function`（计时函数名，默�?`time.perf_counter`）在 `config.yaml` �?`timing_instrumentation` 节点管理
  - **适用**：所�?`page.goto`/`wait_for_selector` 操作、HTTP 外部调用、DB 查询、关�?async 任务�?
  - **不适用**：单�?集成测试（无需生产级埋点）、纯内存计算（耗时极短）、本地开发调试（临时 print 即可�?
  - **历史教训**：官方采集偶发慢，但�?`logger.info` 无结构化 timing，排查时无法区分�?`page.goto` 慢还�?`wait_for_selector` 慢，需用户多次复现抓包
- 🆕v4.12【强制�?*B-REVIEW-PRECHECK-AND-PARALLEL：凭证前置校验与并行采集**
  - 高开销操作（浏览器启动/网络采集）前必须前置校验 Cookie 凭证有效性（`expires` 字段），过期凭证直接返回明确状态码（如 440），**禁止**启动浏览器后才在采集过程中失败浪费资源；独立 IO 任务必须�?`asyncio.gather(*tasks, return_exceptions=True)` 并行执行
  - **核心机制**（审查时必须理解）：
    - 浏览器启动耗时数秒，Cookie 已过期时启动浏览器纯属资源浪�?
    - `cookie.expires=-1` 表示 session cookie（浏览器关闭即失效，无法预判），跳过预校�?
    - `cookie.expires>0` �?`< now()` 表示持久 Cookie 已过期，可直接返�?440
    - `asyncio.gather` 默认任一异常即全部取消，`return_exceptions=True` 让独立任务互不影�?
  - **判断信号**�?
    - 代码�?`async with async_playwright() as p:` 启动浏览器但前置未校�?Cookie �?违规
    - 代码�?`for task in tasks: await task` 串行执行独立 IO �?应改�?`asyncio.gather`
    - `asyncio.gather` 未传 `return_exceptions=True` 且未做异常隔�?�?任一失败导致全部取消
    - Cookie 校验仅检�?`name in cookies` 不检�?`expires` �?违规
  - **修复模式**�?
    ```python
    # �?凭证前置校验
    def _cookie_expired(cookie: dict) -> bool:
        expires = cookie.get("expires", -1)
        if expires == -1:
            return False  # session cookie，无法预�?
        return expires < time.time()

    identity_cookies = [c for c in cookies if c["name"] in IDENTITY_COOKIE_NAMES]
    expired = [c for c in identity_cookies if _cookie_expired(c)]
    if expired:
        # 前置返回 440，不启动浏览�?
        raise HTTPException(status_code=440, detail="Cookie 已过期，请重新登�?)

    # �?独立 IO 并行采集
    results = await asyncio.gather(
        *[collect_task(item) for item in items],
        return_exceptions=True,  # 任一失败不影响其�?
    )
    for item, result in zip(items, results):
        if isinstance(result, Exception):
            logger.warning("采集失败 item={}: {}", item.id, result)
        else:
            process(result)
    ```
    ```python
    # 禁止：启动浏览器后才发现 Cookie 过期 + 串行采集
    ```
  - **配置参数**：`precheck_parallel.credential_check_enabled`（总开关）、`precheck_parallel.identity_cookies_whitelist`（身�?Cookie 名称列表，如 `["_m_h5_tk", "cookie17", "unb"]`）、`precheck_parallel.skip_session_cookies`（是否跳�?session cookie，默�?`true`）、`precheck_parallel.expiry_status_code`（过期时返回状态码，默�?`440`）、`precheck_parallel.parallel_gather_return_exceptions`（gather 是否�?return_exceptions，默�?`true`）、`precheck_parallel.parallel_gather_max_concurrency`（最大并发数�? 表示不限制）、`precheck_parallel.parallel_scenarios`（启用并行的场景列表，如 `["official_collect", "seller_fetch"]`）在 `config.yaml` �?`precheck_parallel` 节点管理
  - **适用**：所有需�?Cookie 凭证的外部采集、独�?IO 任务并行（多商品采集/多卖家查�?�?API 调用）、浏览器自动化前置校�?
  - **不适用**：有依赖关系的串行任务（B 依赖 A 的结果）、纯本地计算、Cookie 仅用于读操作且无成本（如读本�?JSON�?
  - **历史教训**：官方采集启�?Chromium 后才发现 `_m_h5_tk` 过期，浪�?3-5 秒浏览器启动时间；多个商品串行采�?10 个商品耗时 30 秒，并行后降�?5 �?

- 🆕v4.20【强制�?*B-REVIEW-VERSION-SOURCE-SINGLE：元数据源单源管理规�?*
  - 构建期元数据（版本号/构建时间/git_sha/构建主机）必须有唯一源头文件（如 `__init__.py: __version__ = "x.y.z"`），自动生成文件（如 `_build_info.py`）由专门脚本（如 `scripts/build_info.py`）维护；多端点读取同一元数据必须封�?`_safe_xxx()` 三层 try/except 回退辅助函数（源�?�?生成文件 �?默认�?`'unknown'`）；export_config / about / health 等多端点响应中涉及版本号字段必须调用辅助函数而非硬编码占位符
  - **核心机制**（审查时必须理解）：
    - 构建期元数据必须有唯一源头（Single Source of Truth），自动生成文件是派生产物，多端点响应是消费�?
    - 端点命名相似不等于语义对齐：`/api/config/version` 名称�?"version" 但实际返�?`len(backups)`，应在端点命名或 docstring 中明确语�?
    - 多端点读取同一元数据若各自直接 `from xianyu_hunter import __version__`，遇�?`__version__` 缺失�?`_build_info.py` 未生成时各自兜底，会导致响应不一�?
    - 三层回退保证可用性：源头 import 成功 �?生成文件兜底 �?默认�?`'unknown'` 兜底（禁止使�?`"1.0"` / `"0.0.0"` / `"unknown version"` 等占位符，会误导前端与用户）
    - 占位符必须列为禁止值并通过自动化扫描检查，因为它们看起来像合法版本号，�?`'unknown'` 更具误导�?
  - **判断信号**�?
    - `grep "from xianyu_hunter import __version__" src/` 出现 �?2 �?�?必须封装辅助函数
    - `grep -E "'(1\.0|0\.0\.0|unknown version)'" src/xianyu_hunter/web/routes/` �?必须改为调用辅助函数
    - `grep -E '"version":\s*"[^"]+"' src/xianyu_hunter/web/routes/` 命中硬编码字符串 �?视为违规（应调用 `_safe_app_version()`�?
    - 端点 `/api/config/version` 实际返回 `len(backups)` 而非版本�?�?视为命名误导，应�?docstring 中明�?返回备份�?
    - `grep "_safe_app_version\|_safe_build_info" src/xianyu_hunter/web/routes/` 无匹�?�?视为违规
  - **修复模式**�?
    ```python
    # 禁止：硬编码占位�?+ 多端点各自直�?import
    async def export_config(...):
        return {"version": "1.0", ...}  # 占位符，会误导前�?

    # api_about.py
    @router.get("/api/about")
    async def about(...):
        from xianyu_hunter import __version__  # 直接 import，遇缺失无兜�?
        return {"version": __version__, ...}

    # �?正确：封�?_safe_xxx() 辅助函数 + 多端点复�?
    # api_config.py
    def _safe_app_version() -> str:
        """读取系统真实版本号，失败时回退�?'unknown'�?""
        try:
            from xianyu_hunter import __version__
            if __version__:
                return __version__
        except Exception:
            pass
        try:
            from xianyu_hunter import _build_info
            return getattr(_build_info, "__version__", "unknown") or "unknown"
        except Exception:
            return "unknown"

    @router.get("/api/config/export", response_model=ExportConfigResponse)
    async def export_config(...):
        return {"version": _safe_app_version(), ...}  # 调用辅助函数

    # api_about.py 复用同一辅助函数（或在共享模块中定义�?
    @router.get("/api/about")
    async def about(...):
        return {"version": _safe_app_version(), ...}
    ```
  - **配置参数**：`version_source_management` 节点（在 `config.yaml` 管理，不硬编码）�?
    - `enabled`（默�?`true`，开关本检查）
    - `single_source_file`（默�?`"src/xianyu_hunter/__init__.py"`，元数据唯一源头文件路径�?
    - `source_field_name`（默�?`"__version__"`，源头字段名�?
    - `auto_generated_file`（默�?`"src/xianyu_hunter/_build_info.py"`，自动生成文件路径）
    - `auto_generator_script`（默�?`"scripts/build_info.py"`，自动生成脚本路径）
    - `safe_helper_function`（默�?`"_safe_app_version"`，多端点读取必须封装的辅助函数名�?
    - `fallback_default`（默�?`"unknown"`，三层回退的最终默认值，禁止使用占位符）
    - `forbidden_placeholders`（默�?`["1.0", "0.0.0", "unknown version"]`，禁止作为版本号回退值的占位符列表）
    - `forbidden_version_endpoints`（默�?`["/api/config/version"]`，命名含 "version" 但实际返回业务计数的端点列表，应�?docstring 中明确语义）
    - `helper_threshold`（默�?`2`，grep `from xxx import __version__` 出现 �?N 处时必须封装辅助函数�?
  - **适用**：版本号/构建时间/git_sha/构建主机等构建期元数据的读取与响应；多端点读取同一元数据的场景；`/api/about` / `/api/config/export` / `/api/health` / `/api/version` 等元数据相关端点
  - **不适用**：业务数据计数（如备份数/任务�?商品数）；临时调试变量；跨服务边界元数据（应通过专门 API 同步）；核心依赖版本（如 FastAPI/SQLAlchemy 版本，由 requirements.txt 管理）；Pydantic 模型字段（由后端类型系统管理�?
  - **历史教训**：版本管理菜单持续显�?"V10"。根因链路：①前�?`VersionManager.tsx` 调用 `configApi.getVersion()` 拉取 `/api/config/version`，但该端点实际返�?`len(backups)`，受 `BACKUP_KEEP=10` 上限影响永远卡在 10；②后端 `export_config` 中残留占位符 `"version": "1.0"`，前端拿到虚假版本号。修复：后端 `_safe_app_version()` 辅助函数替代占位符（三层回退：`__version__` �?`_build_info.__version__` �?`'unknown'`），前端改用 `aboutApi.get()` �?`/api/about` 拿真实版本号。教训：端点命名相似不等于语义对齐，多端点读取同一元数据必须封装辅助函数避免占位符

- 🆕v4.22【强制�?*B-REVIEW-STARTUP-HOOK-COMPLETENESS：启动钩子完整性检查规�?*
  - 维度�? 异步与调度器
  - 检查项：所有依�?`container.browser` �?`container.collector` 的组件必须在 `startup.py` �?`_on_startup` 中有对应�?`start_xxx()` 启动钩子
  - 强制要求�?
    1. 启动钩子必须�?`if _should_start_scheduler():` 包裹，避免无浏览器时错误启动
    2. 启动钩子必须放在依赖的调度器之后（确保浏览器/collector 已就绪）
    3. 启动失败必须 try/except 兜底，仅记录 warning 不阻断主服务启动
    4. 验证方法：`grep -rn "container.browser\|container.collector" src/xianyu_hunter/` 找所有依赖点，逐个检�?startup.py 是否有对�?start_xxx 调用
  - 配置节点：`startup_hook_completeness`（required_components / dependency_check_fields / startup_order�?
  - 适用场景：含 BackgroundScheduler/asyncio.Task 后台任务的项目，特别是依赖浏览器/外部资源的组�?
  - 不适用场景：纯 Web 项目无后台任务；单进程无外部依赖项目；纯前端组件
  - 实战案例：反爬会话管理（LoginOrchestrator + TokenRenewer）依�?container.browser 进行 Cookie 续期，但 startup.py 缺失启动钩子，导致服务重启后 TokenRenewer 不自动启动，用户必须手动点击「启动会话」按�?

- 🆕v4.22【强制�?*B-REVIEW-TASK-HISTORY-THREE-LAYER-PROTECTION：任务历史持久化三层状态保护规�?*
  - 维度�? 异步与调度器
  - 检查项：写�?running 状态的代码路径必须有对�?finalize 调用更新为终�?
  - 强制要求�?
    1. 必须覆盖三条路径：正常结束（finally 块）、future.result 超时（except 块调�?_finalize_history_on_exception）、协程异常（except 块）
    2. 错误消息累积必须设上限（FIFO 切片丢弃最旧，默认 50 条），避�?JSON 字段无限膨胀
    3. 状态语义必须区分：circuit_broken（连续失败熔断）�?failed，_stop_flag（用户主动停止）�?cancelled，正常完�?�?completed
    4. 业务自增 task_id 不能依赖内存初始化（�?B-REVIEW-COUNTER-DB-MAX-INIT�?
  - 配置节点：`task_history_protection`（required_states / exception_fallback_required / max_error_messages / counter_init_query�?
  - 适用场景：长时间运行任务的执行历史记录（批量采集/数据同步/批处�?定时任务�?
  - 不适用场景：短时间 HTTP 请求；不需要历史记录的任务；一次性脚本任�?
  - 实战案例：批量采集任�?_run_batch_async 开始时插入 running 状态，�?future.result(timeout=3600) 超时，历史记录会残留 running 状态，需 _finalize_history_on_exception 兜底

- 🆕v4.22【强制�?*B-REVIEW-COUNTER-DB-MAX-INIT：业务自增计数器 DB MAX 初始化规�?*
  - 维度�? SQLite 优化
  - 检查项：业务自�?ID（task_id/batch_id/run_id）必须从 DB MAX 初始化，不能依赖内存初始�?
  - 强制要求�?
    1. 调度�?`__init__` 时必须从 DB `SELECT MAX(id)` 初始化计数器
    2. 查询失败时回退�?0 + `logger.warning`，不阻断启动
    3. `trigger_now()` 调用�?`+= 1` 后立即返回给前端，不等待 DB 写入
    4. 为什么不�?DB 自增主键：业务自�?ID 需在调度器内存中维护以�?trigger_now 立即返回给前�?
  - 配置节点：`counter_db_max_init`（counter_fields / init_query_template / fallback_value / warning_on_failure�?
  - 适用场景：业务自�?ID 跨进程重启不能重置的场景
  - 不适用场景：DB 自增主键（autoincrement）；UUID/GUID；临时计数器（无需跨进程持久化�?
  - 实战案例：批量采�?task_id 是业务字段（progress �?历史�?日志均引用），若进程重启后内存计数器�?0 开始，会与历史记录�?task_id 冲突

- 🆕v4.22【强制�?*B-REVIEW-APSCHEDULER-INTERVAL-FIRST-RUN：APScheduler interval 触发器首次执行控制规�?*
  - 维度�? 异步与调度器
  - 检查项：APScheduler interval 触发器必须明确首次执行时�?
  - 强制要求�?
    1. 使用 interval 触发器时必须明确首次执行时间
    2. 需要启动后快速反馈的场景，必须设�?`next_run_time` 参数
    3. `next_run_time` 不建议设�?`datetime.now()`（立即执行），应�?5-10 秒延迟给初始化依赖就�?
    4. 日志必须输出间隔 + 首次执行时间：`logger.info("调度器已启动，间�?%d 分钟，首次执行于 %s", interval, next_run)`
    5. 为什么不设为立即执行：给浏览�?collector 初始化留时间，避免首次采集因浏览器未就绪而连续失败触发熔�?
  - 配置节点：`apscheduler_interval_first_run`（default_next_run_delay_seconds / needs_immediate_execution / log_format�?
  - 适用场景：APScheduler interval 触发器且需要启动后快速反馈的场景（批量采�?数据同步/定时巡检�?
  - 不适用场景：cron 触发器（有明确时间点）；首次执行依赖外部状态需手动触发的场景；�?Web 请求无定时任�?
  - 实战案例：批量采集调度器 interval=30分钟，默认首次执行在启动�?0分钟，用户感知不到调度器在工作，误以为功能不生效。加 next_run_time=now+10s �?0秒首次执�?

### 15. 进程管理

- 【强制】Web 进程必须 `with_browser=False` 模式（节省内存）
- 【强制】WebView2/Playwright 子进程必须用 `CREATE_NEW_CONSOLE` 标志�?*禁止** `CREATE_NO_WINDOW`，防�?GUI 窗口闪退�?
- 【强制】WebView2 子进�?*�?*重定�?stdout/stderr �?`DEVNULL`（保留调试输出）
- 【强制】WebView2 `webview.start()` 必须设置�?
  - `private_mode=False`
  - 唯一 `storage_path`（格�?`webview_data_{pid}_{timestamp}`，持久化 Cookie 防冲突）
- 🆕v4.3【强制�?*B-REVIEW-CHROME-136-ADAPTATION：Chrome 136+ 限制适配模式**
  - Chrome/Edge 136+ 版本使用 `--remote-debugging-port` 时必须配�?`--user-data-dir` 指向非标准目�?
  - **判断信号**：Chrome/Edge 136+ 版本 + 使用 `--remote-debugging-port` 参数 + 浏览器自动化场景
  - **修复模式**：启动命令同时包�?`--remote-debugging-port=9222` + `--user-data-dir=<unique-path>` �?路径不指向默�?`User Data` 目录
  - **配置参数**：`user_data_dir` 路径模板（`browser_data/debug_{timestamp}`）、`debug_port` �?`config.yaml` �?`chrome_debug` 节点管理（不硬编码）
  - **适用**：Chrome/Edge 浏览器自动化、CDP 调试、Playwright `connect_over_cdp`
  - **不适用**：其他浏览器（Firefox/Safari）、旧�?Chrome�? 136）、不使用 remote-debugging 的场�?
  - **历史教训**：Chrome 136+ 安全限制要求 `--user-data-dir` 指向非标准目录，否则 `--remote-debugging-port` 不生效；使用独立 `Debug` profile 避免污染用户�?profile

### 16. Composition Root 🆕v2.0

- 【强制】`container.py` 持有全部单例依赖�?`@dataclass Container`
- 【强制】`build_default_container()` 是唯一工厂函数
- 【强制】`PriorityBrowserLock` �?high/low 优先级（避免低优先级任务长期阻塞�?
- 【强制】`ChatbotOrchestrator` 子容器用 `_build_chatbot_container()` **深拷�?*配置，避免污染全局单例
- 【强制】`chromadb` 缺失时返�?`None`（不抛异常）
- 【推荐】Evaluator 构�?*�?*接受 `thresholds/weights/keywords` 覆盖参数（避免永久覆盖导致用户配置不生效�?
- 🆕v4.3【强制�?*B-REVIEW-MULTI-PROFILE-DISCOVERY：多配置文件发现模式**
  - 发现多个同名配置/profile 时，优先从结构化元数据（�?`Local State` JSON �?`profile.info_cache`）读取，失败�?fallback 到目录扫�?
  - **判断信号**：需发现多个同名配置/profile + 存在结构化索引文�?+ 用户可能使用非默�?profile
  - **修复模式**：读�?`Local State` �?解析 `profile.info_cache` 字典 �?失败则扫�?`User Data/` 子目录匹�?`Profile *` 模式 �?按优先级排序（有目标 cookie �?Default �?名称�?
  - **配置参数**：主数据源路径、fallback 扫描目录、profile 目录正则模式、优先级排序规则�?`config.yaml` �?`profile_discovery` 节点管理（不硬编码）
  - **适用**：浏览器�?profile 发现、多账户隔离环境、多环境配置加载
  - **不适用**：单一配置场景、严格顺序访问场景、路径已知且唯一的场�?
  - **历史教训**：用户实际使�?`Profile 1` 而非 `Default`，原实现只读�?`Default` 导致 cookie 导入失败

### 17. 智能客服专项 🆕v2.0

- 【强制】`ChatbotOrchestrator` 不持有请求级状态（如当�?`session_id`），保证可被多会话共�?
- 【强制】per-session Lock �?`_locks_guard` 保护 `_session_locks` 字典的并发访�?
- 【强制】异常不向外抛出，统一转为 `SSEEvent(ERROR)` �?`SSEEvent(ESCALATE)`
- 【强制】`asyncio.CancelledError` 向上传播以触发资源清�?
- 【强制】`KBManager._scan_and_chunk` 必须排除�?
  - `web/static/`、`web/templates/`、`__pycache__/`、`node_modules/`、`.git/`、`dist/`、`build/`
- 【强制】仅索引 `.md`、`.py`、`.jsonl`、`.txt` 文件（白名单�?
  - **历史教训**：前端构建产物（packed .js/.css）会产生数千无用 chunk，向量化时间�?5 分钟膨胀�?30+ 分钟
- 【强制】工具注册：`BaseTool` 子类注册�?`tool_registry.py`
- 🆕v4.0【强制�?*字段覆盖策略（数据合并）**：数据采集合并时按字段语义分类覆盖策略，**不能一刀�?*
  - 基本信息字段（title/url/region/brand/seller_id/publish_time）：新值非空则覆盖
  - 数值类字段（price/want_cnt/view_cnt）：新�?> 0 才覆盖（防止 0 覆盖有效值）
  - 状态类字段（is_sold）：始终覆盖（状态时效性最高）
  - 标识类字段（seller_nick）：只填缺失（稳定性高�?
  - **适用**：数据采集合并、缓存更新；**不适用**：审计日�?
  - **历史教训**：`_enrich_eval_with_item` �?只填缺失"策略导致旧价�?905 不被新价�?888 覆盖

### 18. Web 层规�?

- 【强制】FastAPI 应用�?`create_app()` 工厂
- 【强制】中间件 LIFO 注册顺序：RequestId �?BearerAuth �?路由
- 【强制】SPA catch-all 处理 `/app/{full_path:path}`，返�?`index.html`
- 【强制】`APIRouter(prefix="/api/<�?", tags=["<�?"])`
- 【强制】Swagger UI 自定�?`_SWAGGER_UI_HTML` 注入导航�?
- 【推荐】启动钩�?`startup.py` 管理 `startup`/`shutdown` 事件
- 🆕v4.6【强制�?*B-REVIEW-DATA-FLOW-TRACE：字段为�?5 点追�?*
  - 用户反馈"某字段为�?/ 显示异常 / 数据丢失"类问题时，必须按 **DB schema �?Repo 查询过滤 �?API 注入 �?前端 types �?render 取�?* 5 点逐层追踪根因�?*禁止**只看前端代码或只查后端代�?
  - **判断信号**：用户反�?字段为空 / 数据丢失 / 显示异常" �?必须�?DB 原始数据开始逐层验证，每层都打印中间�?
  - **追踪流程**�?
    1. **DB schema**：用 `sqlite3` / DB 客户端查询原始数据，确认数据是否存在
    2. **Repo 查询过滤**：检�?Repo 层查询是否有 `WHERE` / `if status == 'failed': continue` 等过滤逻辑
    3. **API 注入**：检�?API 路由层是否正确调�?Repo 并将数据注入响应（参数是否正确传递，�?`include_failed=True`�?
    4. **前端 types**：检�?`frontend/src/api/types.ts` 中类型定义是否包含该字段
    5. **render 取�?*：检查前端组件是否正确从响应中取值并渲染
  - **关键约束**�?
    - 5 点必�?*逐层验证**，不能跳过任何一�?
    - 每层验证必须**打印中间�?*（如 `print(order_map)` / `console.log(record.order)`），不能凭推�?
    - 找到根因后必�?*修复根因**而非绕过（如 Repo 过滤逻辑错误应修 Repo，而非 API 层重新查询）
    - 修复后必�?*回归测试**覆盖该场�?
  - **配置参数**：`trace_nodes`�? 个节点的标识）、`required_fields`（必检字段列表）、`null_value_check`（是否检�?null 值）�?`config.yaml` �?`data_flow_trace` 节点管理
  - **适用**：所�?字段为空 / 显示异常 / 数据丢失"类根因定位，尤其是涉及前后端多层的字�?
  - **不适用**：UI 样式问题（如颜色/布局错误）、纯前端计算字段（如 `total = price * quantity`）、权限不足导致字段隐�?
  - **历史教训**：评估明细页"订单"列显�?"�?，根因是 `repo_orders.list_orders_by_item_ids` 无条�?`if status == 'failed': continue`，但 API 层评估明细调用未�?`include_failed=True`。数据库中实际有 3 �?failed 订单，但全部�?Repo 层过滤。修复后 API 返回 `order_status=failed`（之前为 `null`�?
- 🆕v4.9【强制�?*B-REVIEW-DUAL-LINK-CONSISTENCY：双链路前置条件一致�?*
  - 同一业务目标�?�? 条执行链路时（如 Worker 调度链路 + Live 实时链路都到达「下单」），共用前置条件必须提取为独立函数，两条链路调用同一函数�?*禁止**各自实现
  - **判断信号**：同一业务目标（如「下单」「采集」「通知」）�?�? 条执行链路（�?Worker 调度 + Live 实时 + API 手动 + CLI 命令）→ 必须提取共用前置条件
  - **修复模式**�?
    ```python
    # �?提取共用前置条件为独立函�?
    def _build_price_strategy(task: Task) -> PriceStrategy:
        """构建价格策略，Worker �?Live 链路共用"""
        return PriceStrategy(
            max_price=task.price_config.get("max_price") or 0,
            min_price=task.price_config.get("min_price") or 0,
        )

    # Worker 链路
    class TaskWorker:
        async def run_once(self):
            strategy = _build_price_strategy(self.task)
            if not strategy.is_acceptable(item): return  # 共用过滤

    # Live 链路
    async def _trigger_live_auto_buy(item, task):
        strategy = _build_price_strategy(task)
        if not strategy.is_acceptable(item): return  # 共用过滤
    ```
  - **关键约束**�?
    - 共用前置条件（价格过�?分数校验/库存检查）提取为独立函数（�?`_build_price_strategy(task) -> PriceStrategy`�?
    - 两条链路必须调用同一函数�?*禁止**各自实现相似逻辑
    - 前置条件过滤仅阻止「执行动作」（如抢单），不阻止「评估写库」（评估结果仍写�?DB 供后续分析）
    - 修改后必�?`grep` 验证两条链路确实调用同一函数，禁止遗�?
    - 必须新增测试覆盖两条链路的前置条件一致�?
  - **配置参数**：`target_entities`（业务目标列表，�?`["buy", "collect", "notify"]`）、`shared_predicate_patterns`（共用前置条件函数命名模式，�?`_build_*_strategy`）、`verify_callers`（是否启�?grep 验证，默�?`true`）在 `config.yaml` �?`dual_link_consistency` 节点管理
  - **适用**：同一业务目标有多个触发入口（�?Worker 调度 + Live 实时 + API 手动 + CLI 命令�?
  - **不适用**：单一入口的业务（如只�?API 触发）；链路间业务逻辑本就不同（如 Worker 是异步批量，Live 是同步单条）——此时应抽取「共同部分」为函数，「差异部分」各自处�?
  - **历史教训**：Worker 链路调用 `PriceStrategy.is_acceptable()` 做价格过滤，Live 链路只看分数达标不做价格过滤，导致两条链路行为不一致——Worker 链路过滤掉的高价商品�?Live 链路被下单。修复后提取 `_build_live_price_strategy` 共用函数，两链路调用同一函数

### 19. API 设计规范

- 【强制】HTTP 动词语义化（GET=查询、POST=创建、PUT=替换、PATCH=局部更新、DELETE=删除�?
- 【禁止】GET 请求引发状态变更（如激活、删除）
- 【强制】集合接口必须支持分页（默认 20 条上限）
- 【强制】URL 使用名词复数（`/tasks` 而非 `/getTasks`�?
- 【强制】响应使�?DTO/Pydantic 模型，禁止直接返�?ORM 对象（避免字段泄漏与懒加�?N+1�?
- 【强制】错误响应：HTTP 状态码区分 4xx（客户端�?5xx（服务端），禁止 200+error �?
- 【推荐】API 版本化：路径包含 `/v1/`、`/v2/`
- 【强制】向后兼容：同版本内禁止删除接口/字段、变更字段类型、增加必填参�?
- 🆕v4.0【强制�?*幂等性设�?*：资源创建接口（�?`session/start`、`task/create`）必须幂�?
  - 重复调用返回当前状�?+ `already_active` 标志，不重复创建资源
  - **适用**：资源创建接口、网络重试；**不适用**：纯查询接口（天然幂等）、计数器递增
- 🆕v4.0【强制�?*搜索接口标准�?*：实时搜索接口统一参数命名与响应结�?
  - 统一参数：`keyword/q, page/offset, page_size/limit`
  - 统一响应：`{ items, total, page, page_size }`
  - **适用**：实时搜索（用户输入 + 防抖 + 流式/分页）；**不适用**：主键精确查�?
- 🆕v4.10【强制�?*B-REVIEW-FILTER-VISIBILITY：过滤结果可见性（后端侧）**
  - 后端过滤链（keyword/price/publish_days/自定义过滤）必须输出完整�?`filter_summary` 结构�?*禁止**只返�?final_total 不暴露过滤过�?
  - **核心机制**（审查时必须理解）：
    - 过滤链每阶段（keyword/price/publish_days）必须记录跳过数量（`*_skipped`）和详情（`filtered_out`�?
    - `filtered_out` 项必须含 `link_type`/`link_key`/`display`/`filter_reason`/`filter_detail`，便于前端按原因分组展示
    - `filtered_out` 数量必须有上限避免响应过大（默认 50，参数在 `config.yaml` �?`filter_summary.max_filtered_out_items` 节点管理�?
    - 前端若只拿到 `final_total` 不展示过滤过程，用户无法判断"无结�?是搜索无果还是被过滤�?
  - **判断信号**�?
    - 后端代码�?`if not match_keyword: continue` / `if price > max: continue` 等过滤逻辑但未记录�?`filter_summary` �?视为违规
    - 接口响应只含 `items`/`total` 不含 `filter_summary` �?视为违规
    - `filter_summary` 缺少 `filtered_out` 详情列表 �?视为违规
    - `filtered_out` 项缺�?`filter_reason`/`filter_detail` �?视为违规
  - **修复模式**�?
    ```python
    # �?filter_summary 完整结构 + 三处过滤记录
    _filter_summary = {
        "raw": 0, "formatted": 0,
        "keyword_skipped": 0, "price_skipped": 0, "publish_days_skipped": 0,
        "final_total": 0, "final_items": 0, "final_sellers": 0,
        "filtered_out": [],  # 限制 max_filtered_out_items �?
    }
    # 读取上限（配置驱动，不硬编码�?
    max_filtered_out_items = config.get("filter_summary", {}).get("max_filtered_out_items", 50)

    # keyword 过滤
    if not _match_keyword(r, kw):
        _filter_summary["keyword_skipped"] += 1
        if len(_filter_summary["filtered_out"]) < max_filtered_out_items:
            _filter_summary["filtered_out"].append({
                "link_type": r.get("link_type"), "link_key": r.get("link_key"),
                "display": r.get("display"),
                "filter_reason": "keyword", "filter_detail": f"未匹配关键词 {kw}",
            })
        continue

    # price 过滤
    if price > max_price:
        _filter_summary["price_skipped"] += 1
        if len(_filter_summary["filtered_out"]) < max_filtered_out_items:
            _filter_summary["filtered_out"].append({
                "link_type": r.get("link_type"), "link_key": r.get("link_key"),
                "display": r.get("display"),
                "filter_reason": "price", "filter_detail": f"价格 {price} 超过上限 {max_price}",
            })
        continue

    # publish_days 过滤
    try:
        pub_dt = _dt.fromisoformat(str(pub).replace("Z", "+00:00"))
        if (_now - pub_dt).days > max_publish_days:
            _filter_summary["publish_days_skipped"] += 1
            if len(_filter_summary["filtered_out"]) < max_filtered_out_items:
                _filter_summary["filtered_out"].append({
                    "link_type": r.get("link_type"), "link_key": r.get("link_key"),
                    "display": r.get("display"),
                    "filter_reason": "publish_days",
                    "filter_detail": f"发布 {(_now - pub_dt).days} 天，超过上限 {max_publish_days} �?,
                })
            continue
    except (ValueError, TypeError):
        pass
    ```
  - **配置参数**：`filter_summary.max_filtered_out_items`（默�?`50`，filtered_out 列表长度上限）、`filter_summary.required_fields`（默�?`["raw", "formatted", "keyword_skipped", "price_skipped", "publish_days_skipped", "final_total", "final_items", "final_sellers", "filtered_out"]`，filter_summary 必须包含的字段）、`filter_summary.filtered_out_required_fields`（默�?`["link_type", "link_key", "display", "filter_reason", "filter_detail"]`，filtered_out 项必须包含的字段）、`filter_summary.filter_reason_values`（默�?`["keyword", "price", "publish_days"]`，filter_reason 允许的值列表）�?`config.yaml` �?`filter_summary` 节点管理
  - **诊断流程**（出�?实时搜索无结果但不知原因"类问题时执行）：
    1. `grep "filter_summary" src/xianyu_hunter/web/routes/` 扫描接口响应组装代码
    2. 检查过滤链每阶段是否记�?`*_skipped` 计数�?`filtered_out` 详情
    3. 验证 `filtered_out` 项是否含完整�?5 个字段（link_type/link_key/display/filter_reason/filter_detail�?
    4. 验证 `max_filtered_out_items` 是否�?config 读取（禁止硬编码 50�?
    5. 验证接口响应是否包含 `filter_summary` 字段
  - **适用**：所有含过滤链路的查询接口（实时搜索/历史查询/列表过滤）；多阶段过滤的场景；前端需要展示过滤详情的场景
  - **不适用**：无过滤的纯 CRUD 接口；单一阶段过滤且过滤原因明显（如权限过滤）；内�?API 不暴露给前端
  - **历史教训**：实时搜索接�?`final_total=0`（keyword 过滤 32 + price 过滤 27 = 0 最终）但响应只�?`items: []`，前端只显示"实时查询完成"，用户无法判断是搜索无结果还是被过滤掉，反复调整搜索词无果。修复后添加 `filtered_out` 跟踪 + `filter_summary` 完整结构
- 🆕v4.25【强制�?*B-REVIEW-110: EXCLUDE-UNSET-CHECK：API 更新接口 exclude_unset 检�?*
  - PATCH/PUT 接口必须使用 Pydantic v2 �?`model_dump(exclude_unset=True)` 区分"未传 / �?null / 传�?三态语义，**禁止**手动循环跳过 None �?
  - **核心机制**（审查时必须理解）：
    - `exclude_unset=True` 只导出客户端**显式传入**的字段（区分"未传"�?�?null"�?
    - `exclude_none=True` 会误�?�?null 表示清除"的语义，**禁止**用于更新接口
    - 手动 `for k, v in data.items(): if v is not None: ...` 会丢�?�?null 清除覆盖"的能力，且无法区�?未传"�?�?null"
  - **判断信号**�?
    - PATCH/PUT 路由中出�?`for k, v in body.dict().items(): if v is not None: setattr(obj, k, v)` �?视为违规
    - 使用 `body.dict(exclude_none=True)` 而非 `model_dump(exclude_unset=True)` �?视为违规
    - 使用 `body.model_dump(exclude_none=True)` 用于更新逻辑 �?视为违规
    - 直接 `body.dict()` 不带任何 exclude 参数用于更新 �?视为违规
  - **修复模式**�?
    ```python
    # �?使用 exclude_unset=True 区分三�?
    @router.patch("/tasks/{task_id}")
    async def update_task(task_id: str, body: TaskUpdate):
        update_data = body.model_dump(exclude_unset=True)  # 只含客户端显式传入的字段
        # 未传的字段不�?update_data �?�?不更�?
        # �?null 的字段在 update_data 中且值为 None �?更新�?None（表示清除）
        # 传值的字段�?update_data 中且有�?�?更新为新�?
        await repo.update_task(task_id, update_data)

    # 禁止：手动循环跳�?None，丢�?�?null 清除"语义
    async def update_task(task_id: str, body: TaskUpdate):
        data = body.dict()
        for k, v in data.items():
            if v is not None:  # 无法区分"未传"�?�?null"
                setattr(obj, k, v)
    ```
  - **关键约束**�?
    - 所�?Pydantic BaseModel �?PATCH/PUT 更新接口必须�?`model_dump(exclude_unset=True)`
    - **禁止**�?`exclude_none=True` 替代 `exclude_unset=True`（前者会误删"�?null 清除"语义�?
    - **禁止**手动循环 `if v is not None` 跳过 None
    - 配合 B-REVIEW-111 NOT-NULL-NONE-DEFENSE：NOT NULL 字段�?null 时需防御�?pop
    - Pydantic v1 �?`.dict(exclude_unset=True)`，v2 �?`.model_dump(exclude_unset=True)`
  - **配置参数**：`api_update_semantics.require_exclude_unset`（默�?`true`，强�?PATCH/PUT �?exclude_unset）、`api_update_semantics.forbid_exclude_none`（默�?`true`，禁止用 exclude_none 替代）、`api_update_semantics.forbid_manual_loop`（默�?`true`，禁止手动循环跳�?None）在 `config.yaml` �?`api_update_semantics` 节点管理
  - **适用**：所�?PATCH/PUT 接口的可选字段更新；任务级配置覆盖功能；支持"�?null 清除覆盖"语义的接�?
  - **不适用**：POST 创建接口（创建时字段未传走默认值）；GET 查询接口（无更新语义）；内部数据转换（非用户输入�?
  - **历史教训**：任务级配置覆盖功能中，前端�?`{"price_config": null}` 表示清除该任务的 price_config 覆盖，但后端�?`for k, v in data.items(): if v is not None: setattr(obj, k, v)` 跳过�?None，导�?清除覆盖"操作无效，用户删除的任务级配置实际仍生效。修复后改用 `model_dump(exclude_unset=True)` + 配合 NOT NULL 字段防御�?pop

### 20. 测试建议

审查时建议对以下场景补充单元测试（`tests/test_*.py`）：

- null 输入 / 空集�?/ 边界值（0�?1、最大值）
- 异常分支（服务调用失败、参数校验不通过�?
- 并发场景（共享缓存、计数器、懒加载初始化）
- 事务边界（跨服务调用、回滚条件）
- SSE 重连（lastEventId 持久化恢复）
- 幂等迁移（重复执行不报错�?
- 🆕v4.3【强制�?*B-REVIEW-WINDOWS-TEST-MOCK：Windows 测试环境 Mock 模式**
  - 测试代码�?Windows 环境变量（`LOCALAPPDATA`/`APPDATA`/`USERPROFILE`）必须用 `tmp_path` 正确 mock，路径结构需与实现一�?
  - **判断信号**：测试涉�?Windows 文件系统路径 + 使用环境变量 + 实现依赖 `Path(LOCALAPPDATA)` 等构造路�?
  - **修复模式**：`monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))` �?测试 fixture 创建 `tmp_path / "Microsoft" / "Edge" / "User Data"` 完整路径结构 �?与实现路径完全对�?
  - **配置参数**：测�?fixture 路径模板、环境变量映射在 `tests/conftest.py` 管理
  - **适用**：Windows 文件系统路径测试、浏览器 profile 发现测试、配置文件加载测�?
  - **不适用**：Linux/Mac 路径测试、不涉及环境变量的路径测试、纯函数测试
  - **历史教训**：测试代码创�?`tmp_path / "Edge" / "User Data"` 但实现用 `Path(LOCALAPPDATA) / "Microsoft" / "Edge" / "User Data"`，路径结构不一致导致测试失�?
- 🆕v4.3【强制�?*B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK：第三方插件依赖预检模式**
  - 使用 pytest 插件（如 `pytest-timeout`）前必须验证项目已安装，避免运行时报错；插件依赖列表需�?`pyproject.toml` 显式声明
  - **判断信号**：使�?pytest 命令行参数（�?`--timeout`�? 依赖第三方插�?+ 未在 `pyproject.toml` 声明
  - **修复模式**：`pyproject.toml` `[tool.pytest.ini_options]` 显式声明 `addopts` + `requirements-dev.txt` 列出插件依赖 �?运行前用 `pytest --version` + 插件检查脚本验�?
  - **配置参数**：插件依赖列表在 `pyproject.toml` 管理，预检脚本�?`scripts/check-deps.ps1`
  - **适用**：所�?pytest 插件依赖（`pytest-timeout`/`pytest-cov`/`pytest-asyncio`）、tox/nox 多环境测�?
  - **不适用**：pytest 内置功能（无需预检）、CI 环境固定镜像（依赖明确）
  - **历史教训**：使�?`pytest --timeout=60` 报错 `unrecognized arguments`，项目未安装 `pytest-timeout` 插件；移�?`--timeout` 标志后通过，但应预检插件依赖
- 🆕v4.10【强制�?*B-REVIEW-PYTEST-MODULE-REIMPORT：pytest 模块重复 import 隔离**
  - pytest �?`sys.modules` 中可能以 `test_xxx`（无包前缀）和 `tests.test_xxx`（带包前缀）两种名字持有同一测试文件的不同模块对象，conftest.py patch 模块属性时**禁止**硬编码模块名列表，必须遍�?`sys.modules` 找所有持目标属性的模块全部 patch
  - **核心机制**（审查时必须理解）：
    - pytest 以两种名�?import 同一测试文件，生成两个不同模块对象在 `sys.modules` �?
    - conftest.py 若只 patch 其中一个模块对象，被测代码读取的是另一个未 patch 的模块对象，导致隔离失败
    - `__import__("a.b")` 返回顶层�?`a` 而非子模�?`a.b`，必须用 `importlib.import_module` 正确返回子模�?
  - **判断信号**�?
    - conftest.py �?`for name in ["xxx", "yyy"]: monkeypatch.setattr(sys.modules[name], ...)` 硬编码模块名列表 �?视为违规
    - conftest.py �?`__import__("a.b")` 且后续操作期望得到子模块 �?视为违规
    - 测试用例 `import tests.test_xxx` 后修改模块属性，但被测代�?`from test_xxx import YYY` 读取的是另一份模块对�?�?典型症状
    - 生产文件含测试数据（�?`data/cookies.json` �?`test_fixture_` 前缀）→ 隔离失败症状
  - **修复模式**�?
    ```python
    # �?正确：遍�?sys.modules 找所有持目标属性的模块
    import sys
    TARGET_ATTR = "_COOKIE_JSON"

    def patch_all_modules_with_cookie(tmp_path):
        patched = []
        for mod in sys.modules.values():
            if mod is None:
                continue
            if hasattr(mod, TARGET_ATTR):
                # patch �?tmp_path 隔离生产数据
                setattr(mod, TARGET_ATTR, str(tmp_path / "cookies.json"))
                patched.append(mod.__name__)
        assert patched, f"未找到持 {TARGET_ATTR} 属性的模块"
        return patched

    # �?正确：importlib.import_module 替代 __import__
    import importlib
    mod = importlib.import_module("xianyu_hunter.modules.cookie_rotator")

    # 禁止：硬编码模块名列�?
    # 禁止：__import__ 返回顶层�?
    ```
  - **配置参数**：`pytest_isolation.target_attr_pattern`（默�?`_COOKIE_JSON`，支持正则）、`pytest_isolation.module_name_prefixes`（默�?`[]` 表示全扫，可选限制如 `["xianyu_hunter", "tests"]`）、`pytest_isolation.use_importlib`（默�?`true`，强制使�?`importlib.import_module`）、`pytest_isolation.forbid_hardcoded_module_list`（默�?`true`，禁止硬编码模块名列表）�?`config.yaml` �?`pytest_isolation` 节点管理
  - **诊断流程**（出�?测试数据污染生产文件"类问题时执行）：
    1. `grep "for name in" tests/conftest.py` 扫描硬编码模块名列表
    2. `grep "__import__" tests/` 扫描 `__import__` 使用
    3. 检�?conftest.py 是否遍历 `sys.modules` 动态识别持目标属性的模块
    4. 验证 patch �?`assert hasattr(mod, TARGET_ATTR)` 确认 patch 生效
    5. 跨模块共享配置路径的测试必须用此模式
  - **适用**：pytest conftest.py 全局 fixture patch 模块属性；多模块共享同一配置文件路径的场景；任何需�?patch 跨模块共享状态的测试
  - **不适用**：单模块测试（直�?monkeypatch 即可）；�?pytest 测试框架；patch 对象属性（非模块属性）
  - **历史教训**：`conftest.py` 硬编�?`[cookie_rotator]` 列表 patch `_COOKIE_JSON`，但 pytest �?`test_cookie_rotator` �?`tests.test_cookie_rotator` 两种名字持有同一文件的两个模块对象，patch 只命中其中一个，导致生产 `data/cookies.json` 被测试数据污染。修复后改为遍历 `sys.modules` 找所有持 `_COOKIE_JSON` 属性的模块全部 patch
- 🆕v4.10【强制�?*B-REVIEW-TEST-FIXTURE-ISOLATION：测�?fixture 生产隔离与数据污染应�?*
  - conftest.py 必须 patch 生产路径（如 `data/cookies.json`、`*.db`）到 `tmp_path`，fixture 数据需带可识别特征（如 `test_fixture_` 前缀），数据污染应急必须按 5 步流程执�?
  - **核心机制**（审查时必须理解）：
    - fixture 若直接读写生产路径，测试数据会污染生产文件，导致服务异常
    - 测试数据带可识别特征（前缀/后缀）便于污染后定位与清�?
    - 数据污染应�?5 步流程确保污染被发现后系统化处理，避免遗�?
  - **判断信号**�?
    - conftest.py �?`open("data/cookies.json", "w")` / `open("data/*.db", "w")` 直接写生产路�?�?视为违规
    - 测试数据无前缀/后缀特征（如 `user_id = "abc123"` 而非 `user_id = "test_fixture_abc123"`）→ 视为违规
    - 生产文件含测试数据（�?`data/cookies.json` �?`test_fixture_` 前缀�?cookie）→ 典型污染症状
    - conftest.py 用模块级全局变量持有测试数据路径 �?视为违规（应�?fixture scope�?
  - **修复模式**�?
    ```python
    # �?正确：tmp_path 隔离 + 可识别特�?+ patch 验证
    @pytest.fixture(scope="session")
    def isolated_cookie_path(tmp_path_factory):
        cookie_path = tmp_path_factory.mktemp("data") / "cookies.json"
        # 写入�?test_fixture_ 前缀的测试数据（便于污染后定位）
        cookie_path.write_text('{"token": "test_fixture_token_xxx"}')
        # patch 所有持 _COOKIE_JSON 属性的模块（参�?B-REVIEW-PYTEST-MODULE-REIMPORT�?
        patched = []
        for mod in sys.modules.values():
            if mod is not None and hasattr(mod, "_COOKIE_JSON"):
                setattr(mod, "_COOKIE_JSON", str(cookie_path))
                patched.append(mod.__name__)
        assert patched, "未找到持 _COOKIE_JSON 属性的模块"
        # 验证生产路径未被写入
        assert not os.path.exists("data/cookies.json"), "生产路径被写入！"
        return cookie_path

    # 数据污染应急流程（�?config.yaml �?test_isolation.pollution_recovery_steps 执行�?
    # 1. 停止服务：xianyu-automation-startserver stop
    # 2. 删除污染文件：rm data/cookies.json
    # 3. 修复 conftest：参�?B-REVIEW-PYTEST-MODULE-REIMPORT 遍历 sys.modules patch
    # 4. 重跑测试：pytest
    # 5. 通知用户：告知污染文件清�?
    ```
  - **配置参数**：`test_isolation.production_path_patterns`（默�?`["data/cookies.json", "data/*.db", "data/*.json"]`，生产路径模式列表）、`test_isolation.test_data_markers`（默�?`["test_fixture_", "__test__"]`，测试数据可识别特征列表）、`test_isolation.pollution_recovery_steps`（默�?5 步流程列表：停止服务/删除污染文件/修复 conftest/重跑测试/通知用户）、`test_isolation.fixture_scope_default`（默�?`function`，fixture 默认作用域）、`test_isolation.assert_no_production_write`（默�?`true`，加�?fixture 后断言生产路径未写入）�?`config.yaml` �?`test_isolation` 节点管理
  - **诊断流程**（出�?生产文件含测试数�?类问题时执行）：
    1. 检查生产文件是否含 `test_data_markers` 中的特征前缀/后缀
    2. `grep "open\\(['\\\"]data/" tests/` 扫描测试代码直接写生产路�?
    3. 检�?conftest.py 是否�?`tmp_path` / `tmp_path_factory` 隔离
    4. 检�?fixture 数据是否带可识别特征
    5. �?`pollution_recovery_steps` 执行应急流�?
  - **适用**：所�?pytest fixture 涉及文件 IO 的场景；conftest.py 全局 fixture；CI/CD 测试环境
  - **不适用**：纯内存测试（无文件 IO）；mock 替代真实文件的测试；一次性脚本测�?
  - **历史教训**：`conftest.py` 未隔�?`data/cookies.json`，测试用例直接写入生产文件，导致生产 cookie 被测试数据污染（�?`test_fixture_` 前缀�?token）。应急流程：停止服务 �?删除 `data/cookies.json` �?修复 conftest 遍历 sys.modules patch �?重跑 pytest 全绿 �?通知用户重新初始�?cookie

### 21. 架构与分�?

- 【强制】包组织策略明确：按功能分模块（`modules/collector/`、`modules/notifier/`、`modules/buyer/` 等）
- 【禁止】跨层调用：路由直接访问 ORM、领域包引入框架注解
- 【强制】领域包不引入框架注解（不依�?SQLAlchemy/FastAPI�?
- 【禁止】循环依�?A �?B �?C �?A
- 【推荐】`util/`、`common/` 包不得无限增长，应归属对应功能模�?
- 【强制】DTO 在边界处转换，领域对象不出边�?
- 【推荐】新增功能应仅影响对应功能包，不应触碰多个包

### 22. 闲鱼项目规范 🆕v2.0

- 【强制】依赖单�?`web �?modules �?infra �?domain`
- 【强制】`container.py` 是唯一 Composition Root
- 【强制】仓储用 Mixin 组合模式（`TasksMixin`、`ItemsMixin` 等），聚合为 `Repository`
- 【强制】Typer CLI 入口（`__main__.py`）支�?`run/add/list/status/pause/resume/stop/login/web/config_show` 命令
- 【强制】Web 进程通过 `os.environ["XH_WITH_SCHEDULER"] = "1"` 控制调度器模�?
- 【强制】目录不可移动：`src/xianyu_hunter/`、`config/`、`data/`、`browser-data/`、`frontend/`、`tests/`（代码硬编码引用�?
- 【强制】根目录严格遵循 14 个核心文件规范（�?`docs/standards/directory-structure.md §7.1`�?
- 【强制】Docker 三阶段构建：`frontend`（node:20-alpine）→ `builder`（python:3.12-slim）→ `runtime`（python:3.12-slim�?
- 【强制】runtime 阶段不包含构建工具，减小镜像体积
- 【推荐】`pyproject.toml` 不使�?`dynamic = ["version"]`（About API 需运行时反射）

### 23. Git 操作规范 🆕v2.1

- 【强制】合并前检�?`.git/index.lock` 是否残留（失�?git 操作可能留下锁文件）
- 【强制】产物文件（`.scannerwork/`、`__pycache__/`、`node_modules/`、`dist/`）不应被 git track
- 【强制】发现产物被 track 时用 `git rm -r --cached <dir>` 清理（不删除工作区文件）
- 【强制】`.git` 目录被安全策略保护时，用 Python `os.remove()` �?git 命令本身操作
- 【强制】冲突解决保留更新版本（�?`await` 异步版本优于同步版本�?
- 【强制】cherry-pick 后的合并冲突：main 已有 cherry-pick 改动，feat 有原始改动，保留 main 版本
- 【推荐】stash 前确认无大目录被 modified，避免权限问题导�?stash 失败
- 【推荐】PowerShell �?`stash@{0}` 必须加引号：`git stash pop 'stash@{0}'`

### 24. 跨字段一致性与硬编码属性禁�?🆕v4.2

- 【强制�?*B-REVIEW-CROSS-FIELD：跨字段一致性校�?*：同一 dataclass/dict 中语义相关联的字段对必须在构造时校验一致性，禁止出现矛盾组合
  - 检查清单（字段对在 `config.yaml` �?`cross_field_consistency_checks` 节点管理）：
    - `gpu_vendor` + `gpu_renderer`：厂商与渲染器型号必须匹配（�?`Google Inc. (AMD)` �?AMD 渲染器）
    - `valid` + `written_count`：层状态标�?valid=True 时写入数量必�?> 0（或 writer 未设置）
    - `layer` + `cookies`：Cookie 分层定义与实际归属必须一致（�?`_m_h5_tk` 属于 session 层而非 identity 层）
  - **判断信号**：同一数据结构中存在语义关联字段对
  - **修复模式**：`__post_init__` / 构造函�?/ 工厂函数中校验，不一致时�?`ValueError`
  - **不适用**：独立无关联字段、运行时动态拼装的临时对象

- 【强制�?*B-REVIEW-NO-HARDCODED-PROPS：硬编码属性禁�?*：写入外部系统（浏览�?Cookie、HTTP 响应头、数据库列）的属性必须根据数据语义动态设置，禁止硬编码固定�?
  - 检查清单（属性映射在 `config.yaml` �?`hardcoded_property_mappings` 节点管理）：
    - Cookie 属性：`httpOnly`/`secure`/`sameSite` 根据 Cookie 名称和层级动态判断（identity �?Cookie �?JS 可读的，不能强制 `httpOnly:True`�?
    - HTTP 响应头：`Content-Type`/`Cache-Control` 根据响应内容类型设置
  - **判断信号**：批量构造对象时所有实例使用相同的属性固定值（如所�?Cookie 都设 `httpOnly:True`�?
  - **修复模式**：属性值从数据语义派生或通过配置文件管理属性映�?
  - **不适用**：项目固定常量（如域名、路径前缀 `path: "/"`）、安全必需的固定�?

- 【强制�?*B-REVIEW-NO-CROSS-THREAD-ASYNC：跨线程异步调用禁用**：禁止在同步函数中用 `asyncio.run_coroutine_threadsafe()` + `future.result()` 等待异步结果（存在死锁风险）
  - **判断信号**：`run_coroutine_threadsafe` + `future.result(timeout=N)` 组合出现
  - **修复模式**：改为纯异步路径（`async def`）或 fire-and-forget（`asyncio.ensure_future` 不等待结果）+ 同步兜底（如 JSON 持久化）
  - **适用**：FastAPI 同步路由调用 Playwright 等异�?API
  - **不适用**：测试代码中的显式事件循环控�?

- 【强制�?*B-REVIEW-TRY-FINALLY-INIT：try/finally 变量初始�?*：`try/finally` 块中 `finally` 引用的变量必须在 `try` 之前初始化为 `None`
  - **判断信号**：`try:` 块内赋值的变量�?`finally:` 中被引用
  - **修复模式**：`page = None; try: page = await ... finally: if page: await page.close()`

- 【强制�?*B-REVIEW-CROSS-COMPONENT-STATE：跨组件状态同�?*：多个组件对同一概念做判断时，状态变更必须双向同�?
  - 检查清单（跨组件状态概念在 `config.yaml` �?`cross_component_state_concepts` 节点管理）：
    - "会话有效�?：health_checker（Cookie 存在性）+ worker（API 响应 RGV587_ERROR�? orchestrator（cookie_rotator 层状态）
  - **判断信号**：两个以上组件各自独立判�?会话有效�?/"登录状�?等同一概念
  - **修复模式**：状态变更方调用 `invalidate_layer()` 通知其他组件；查询方额外检查其他组件的状态标�?

- 【强制�?*B-REVIEW-ERROR-HINT-ROUTABLE：错误提示端点可操作�?*：面向用户的错误提示中引用的 API 端点/方法名必须实际存�?
  - **判断信号**：错误信息中包含 `/api/xxx` 或方法名引用
  - **修复模式**：提示中只引用已实现的端点；改为可操作的 UI 指引（如"请调�?POST /api/anticrawl/initialize 重新初始�?�?

- 🆕v4.16【强制�?*B-REVIEW-FIELD-NORMALIZE-DOC：字段归一化文档化**
  - **判断信号**：后端有 `_normalize` / `_unify` / `_merge` / `_flatten` 等归一化函�?+ 前端 types.ts 声明旧字段名 + 前端通过动�?key 取�?
  - **强制规则**：后端归一化字段时必须在前�?types.ts 对应字段声明中加注释 `// 后端已归一化，前端消费 X 字段`；保留旧字段名必须标 optional 并注�?`// 仅作兼容保留，后端不返回`；前端禁止通过动�?key 取归一化字段必须直接用归一化后字段�?
  - **反例**：后�?`_normalize_deep_result` �?signals/damages/inconsistencies 归并�?signals，但前端 types.ts 仍声�?damages/inconsistencies，前端通过 `check[signalKey]` 取值永�?undefined
  - **正例**：后端归一化后在前�?types.ts 注释 `// 后端已归一化，前端消费 signals 字段`，前端直接用 `check.signals`
  - **配置参数**：`field_normalize_doc` 节点（enabled / require_doc_comment / detect_dynamic_key_access / fallback_to_legacy_field�?
  - **适用场景**：后端有归一化函�?+ 前端通过动�?key 取�?
  - **不适用场景**：后端直接返回原始响应无转换；前端类型声明与后端 pydantic 模型一一对应

### 25. 状态管理与日志治理 🆕v4.8

- 【强制�?*B-REVIEW-STATE-FLAG-PRECHECK：状态标志前置检查完整�?*：检测到异常状态（会话失效/Cookie 过期/服务降级/限流）后是否设置状态标志；后续操作入口是否�?`getattr(self, "flag", False)` 检查标志提前返�?
  - 检查清单（参数�?`config.yaml` �?`state_flag_precheck` 节点管理）：
    - `state_flag_names`：状态标志名列表（如 `last_session_invalid` / `degraded_mode` / `cookie_expired`�?
    - `require_reset_mechanism`：默�?true，要求必须有重置机制（grep `flag = False` 确认重置点）
  - **判断信号**：代码含 `self.last_session_invalid = True` / `self.degraded_mode = True` 等状态标志设�?�?必须检查后续操作入口是否有前置检�?
  - **修复模式**：在操作入口增加 `if getattr(self, "flag", False): return None`；必须有重置机制（grep `flag = False` 确认重置点）；调用方能处�?None 返回�?
  - **适用**：会话失效、Cookie 过期、服务降级、限流、依赖不可用
  - **不适用**：一次性错误（单条请求失败）、无恢复机制的场景、高频变化状�?
  - **历史教训**：`_detail.py` 检测到 Cookie 失效（首页标题）后设�?`last_session_invalid = True`，但 `detail()` 方法未检查标志，导致 300+ WARNING 日志刷屏

- 【强制�?*B-REVIEW-LOG-DOWNGRADE-STABILITY：日志降级判断稳定�?*：已知业务场景的错误日志降级时，判断字符串是否提取为模块级常量；常量是否注释标明文案来源；未知错误是否保�?WARNING/ERROR 级别
  - 检查清单（参数�?`config.yaml` �?`log_downgrade` 节点管理）：
    - `downgrade_rules`：降级规则列表，每条�?`match_pattern` / `target_level` / `detail_marker` / `source_comment`
  - **判断信号**：代码含 `logger.log(log_level, ...)` 动态日志级�?�?必须检查判断条件是否用魔法字符�?
  - **修复模式**：将魔法字符串提取为模块级常量（�?`_COOKIE_EXPIRED_DETAIL_MARKER = "Failed to collect item detail"`），注释标明文案来源
  - **适用**：已知业务异常日志治理（Cookie 失效 502、重试中 WARNING）、外部依赖偶发失�?
  - **不适用**：未知错误、安全相关错误（不应降级）、首次出现的错误、需用户介入的错�?
  - **历史教训**：`exception_handler.py` �?`"Failed to collect item detail" in str(exc.detail)` 判断是否 Cookie 失效，字符串未提取为常量，文案变更时匹配会失�?

- 【强制�?*B-REVIEW-EDIT-VERIFY：修改生效验证（针对 AI 辅助开发）**：使�?Edit 工具修改文件后，是否立即�?Grep �?Read 验证修改是否真正生效
  - **配置参数**：无（纯流程检查项�?
  - **判断信号**：代码评审时发现修复代码引用的变�?函数不存在于文件�?�?修改可能未生�?
  - **修复模式**：Edit 后立�?Grep 搜索新增代码的标志性标识符（变量名/函数�?常量名），无匹配则重新执�?Edit
  - **适用**：所有使�?Edit 工具的修改场景，尤其是批量修改多个文件时
  - **不适用**：Read/Write 工具（这些工具本身有返回验证�?
  - **历史教训**：第一次调�?Edit 修改 `_detail.py` �?`exception_handler.py` 后工具返�?修改成功"，但后续 Grep 检查发现修改未保存，导致评审了未修改的代码

### 26. 缓存/状态判�?Schema 演进规约 🆕v4.15

- 【强制�?*B-REVIEW-CACHE-INVALIDATION：缓存失效传播完整�?*：任何持久化层（JSON 文件 / SQLite / 外部配置）变更后，是�?*显式调用**对应缓存对象�?`invalidate_cache()` 或等价方法；TTL 兜底不替代主动失效；跨进程变更是否主动通知主进�?
  - 检查清单（参数�?`config.yaml` �?`cache_invalidation` 节点管理）：
    - `enabled`：默�?`true`，强制启用显式失�?
    - `ttl_grace_seconds`：默�?`0`，TTL 兜底秒数�? 即不依赖 TTL�?
    - `fail_log_level`：默�?`warning`，同步钩子失败的日志级别
    - `cache_field_patterns`：缓存字段正则列表（�?`["_cache", "_cache_time", "_cached_.*"]`�?
  - **判断信号**：类�?`_cache`/`_cache_time`/`_cached_*` 字段但无 `invalidate_cache()` 方法 �?必须补齐；写入主数据源的方法（`update_*`/`upsert_*`/`write_*`）未在写后调用同步钩�?�?必须补齐
  - **修复模式**�?
    1. 识别共享状态：明确"输入字段"�?派生字段"�?持久化副�?三类
    2. 设计 invalidate 入口：每个缓存对象暴�?`invalidate_cache()` 方法
    3. 写入主路径后必调：所有写主数据源方法在写�?*显式**调用 `invalidate_cache()`
    4. 失败降级：同步钩子失败仅 `logger.warning`，不抛异常阻塞主流程
  - **适用**：JSON 持久化层、跨进程 Cookie/状态同步、内存缓存与文件副本同步、登录态多进程写入
  - **不适用**：纯函数、纯计算缓存（如 LRU math 缓存）、无外部数据源同步的内部状�?
  - **历史教训**：`CookieStore` �?30 �?TTL 兜底缓存，浏览器子进程登录后只更新子进程自己的缓存，主进程仍读到旧缓存，导致 3 �?Cookie 层显示失效（功能实际可用�?

- 【强制�?*B-REVIEW-STATE-DETECTION-BOOTSTRAP：状态判定需区分"未检�?�?已检测未失效"**：任�?功能信号"字段（`last_session_invalid`/`is_healthy`/`is_connected` 等）不能仅用布尔初始值（�?`False`）代�?未检�?——`False` �?已检测无失效"语义混淆，会导致刚启动时误判�?功能正常"
  - 检查清单（参数�?`config.yaml` �?`state_detection_bootstrap` 节点管理）：
    - `required_marker`：前置条件类型（`timestamp`/`counter`/`flag`，默�?`timestamp`�?
    - `signal_layer_mapping`：信号到层范围映射（�?`collector_signal �?[identity, session, tracking]`、`m5tk_signal �?[session]`�?
    - `unknown_signal_strategy`：默�?`set()`，未识别信号组合的处理策�?
    - `boolean_field_default_pattern`：布尔字段默认值正则（默认 `False`�?
  - **判断信号**：布尔字段默认�?`False` + 实际语义�?初始未检�? �?必须增加时间�?计数器区分；强制恢复/兜底逻辑仅依赖布尔字�?�?必须加前置条�?
  - **修复模式**�?
    1. 增加"已检�?标记：`_last_m5tk_refresh > 0` / `use_count > 0` / `_has_run = True`
    2. 信号判定前置条件：`if has_searched and session_ok: signals.add(...)`
    3. 强制恢复需白名单：信号 1/2 只能恢复其能证明有效的层范围
    4. 防御�?else：未识别的信号组合不默认恢复所有层，写 `logger.warning` �?`set()`
  - **适用**：跨进程/跨模块状态判定、Cookie 层状态自愈、容器健康检查、服务可用性兜�?
  - **不适用**：纯客户�?UI 状态、单次函数返回值、无初始歧义的开关字�?
  - **历史教训**：collector 刚启动还没搜索过任何商品时，`last_session_invalid=False` 被解读为"会话有效"，强制恢复所�?Cookie 层（包括实际已失效的 IDENTITY），导致用户看到"状态闪�?（失效→恢复→再失效�?

- 【强制�?*B-REVIEW-MIGRATION-TRANSACTION：SQLite DDL 修改列约束必须用表重�?+ 事务安全**：SQLite 不支�?`ALTER COLUMN`，任何修改列约束的操作（NOT NULL→nullable、类型变更）是否通过 `engine.begin()` 单事�?+ 残留清理 + 数据复制 + 异常恢复模式；禁止分�?commit 或裸 ALTER
  - 检查清单（参数�?`config.yaml` �?`migration_transaction` 节点管理）：
    - `require_single_transaction`：默�?`true`，DDL 必须单事务包�?
    - `cleanup_residual_table`：默�?`true`，迁移前 `DROP TABLE IF EXISTS {table}_old`
    - `recover_from_old`：默�?`true`，失败后�?`{table}_old` 恢复
    - `exception_log_level`：默�?`error`，DDL 失败日志级别
    - `unsafe_patterns`：禁用模式正则（�?`["ALTER TABLE.*MODIFY COLUMN", "ALTER TABLE.*ALTER COLUMN"]`�?
  - **判断信号**：`_migrate_*` 函数含多�?`conn.commit()` �?拆分为单一事务；`ALTER TABLE ... MODIFY COLUMN` / `ALTER TABLE ... ALTER COLUMN` �?SQLite 不支持，需改用表重建；DDL 操作未传 `conn` �?`orm_table.create` �?必须改为�?`conn`
  - **修复模式**�?
    ```python
    with engine.begin() as conn:
        conn.execute(sa_text(f"DROP TABLE IF EXISTS {table}_old"))
        conn.execute(sa_text(f"ALTER TABLE {table} RENAME TO {table}_old"))
        orm_table.create(conn, checkfirst=True)
        old_cols = {c[1] for c in conn.execute(sa_text(f"PRAGMA table_info({table}_old)")).all()}
        common_cols = [c for c in orm_table.columns if c.name in old_cols]
        col_list = ", ".join(f'"{c.name}"' for c in common_cols)
        conn.execute(sa_text(f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM {table}_old"))
        conn.execute(sa_text(f"DROP TABLE {table}_old"))
    ```
  - **适用**：SQLite 修改列约束、表重建、任何不可�?DDL
  - **不适用**：PostgreSQL/MySQL（有原生 DDL 事务）、新增列（直�?`ADD COLUMN`）、纯查询/插入操作
  - **历史教训**：旧�?`_migrate_make_column_nullable` �?3 个独�?commit 拆分布骤 1/2/3/4，步�?2 �?3 失败时旧表已 RENAME 但新表未创建完成，tasks 表变空且 tasks_old 残留，下次启动时 RENAME 因目标已存在永久阻塞；新版改�?`engine.begin()` 单事�?+ 残留清理 + 异常恢复，彻底解决该问题

### 27. 多路径数据源一致性与统计聚合校准 🆕v4.17

- 【强制�?*B-REVIEW-MULTI-PATH-DATA-SOURCE：同 API 多查询数据源一致�?*：同一端点内多�?`select` 查询若服务于同一响应指标，必须共用同一过滤条件；禁止主查询�?`task_id` 过滤、辅助查询全表扫�?
  - 检查清单（参数�?`config.yaml` �?`multi_path_data_source` 节点管理）：
    - `enabled`：默�?`true`
    - `scan_select_count_threshold`：默�?`2`，同一函数�?select 语句�?�?此值时触发检�?
    - `ignore_global_scope_queries`：默�?`true`，scope.mode=="all" 时允许辅助查询不过滤 task_id
  - **判断信号**：同一函数内出�?�? �?`select(...)` 且主查询�?`where(task_id==)` 但辅助查询无此条�?�?必须检查辅助查询是否应同源过滤
  - **修复模式**：辅助查询补�?`where(task_id==task_id)`；或提取公共过滤条件变量；时间对比基线查询必须与价格样本查询同源
  - **适用**：仪表盘统计 API（直方图/趋势/对比）、多查询拼装响应的端�?
  - **不适用**：明确需要跨任务聚合的全局统计（scope.mode=="all"）、不同业务含义的同类字段
  - **历史教训**：`price_histogram.py` �?`prices` �?task_id 过滤，但 `ts_rows`（用于计�?yesterday/last7d/last30d 均价）全表扫描，导致选定任务时时间对比基线混入其它任务价格，"�?日变�?等表格指标完全失�?

- 【强制�?*B-REVIEW-STATISTICAL-INPUT-BOUNDARY：统计聚合输入边界校�?*：统�?分桶/均价逻辑禁止直接�?`min(prices)`/`max(prices)` 作为范围，必须用百分位裁剪（P5/P95�? 业务上下文范围融�?
  - 检查清单（参数�?`config.yaml` �?`statistical_input_boundary` 节点管理）：
    - `enabled`：默�?`true`
    - `lower_percentile`：默�?`0.05`（P5�?
    - `upper_percentile`：默�?`0.95`（P95�?
    - `min_sample_size`：默�?`5`，样本数 < 此值时跳过裁剪（小样本直接�?min/max�?
    - `business_range_fields`：业务范围字段映射（�?`{"task": ["min_price", "max_price"]}`�?
  - **判断信号**：代码含 `lo, hi = min(prices), max(prices)` 后接等宽分桶 �?必须检查是否有极端值防护；分桶范围未融合业务上下文（如任务定价范围）→ 必须补齐
  - **修复模式**�?
    1. 计算 P5/P95 百分位（用线性插值分位数�?
    2. 融合业务范围：`lo = min(P5, task_min_price)`, `hi = max(P95, task_max_price)`
    3. `lo = max(0, lo)`；若 `hi <= lo` �?`hi = lo + 1`
    4. 首桶吸收 `p < lo+step` 的极端低价；尾桶吸收 `p >= lo+(N-1)*step` 的极端高�?
    5. 验证 `sum(counts) == len(prices)`（总数守恒�?
    6. summary �?min/max 返回真实极值（非分桶边界）
  - **适用**：直方图分桶、均价计算、趋势对比、任何受极端值污染的聚合
  - **不适用**：需要精确极值的场景（如"最高价商品"列表）、小样本�?5 个数据点�?
  - **历史教训**：`price_histogram.py` bins=20 模式�?`min(prices)=50, max(prices)=5000` 作为分桶范围，单�?5000 元极端值导致前 2 个桶装着大部分商品、其�?18 个桶全为 0；改�?P5/P95 裁剪 + 任务定价范围融合后，范围缩小 34%，分布可视化才有参考价�?

- 【建议�?*B-REVIEW-CONCURRENT-CHECK-ACT：并�?check-then-act 原子�?*：并发场景下状态检查（冷却�?锁状�?计数器）必须在持锁状态下进行，禁�?check 后释放锁�?act
  - 检查清单（参数�?`config.yaml` �?`concurrent_check_act` 节点管理）：
    - `enabled`：默�?`true`
    - `lock_types`：默�?`["asyncio.Lock", "threading.Lock"]`
    - `check_keywords`：默�?`["cooldown", "last_run", "count", "exists"]`
  - **判断信号**：`if self._xxx_ok():` 后接 `async with self._lock:` �?check 在锁外，必须移入锁内
  - **修复模式**：将 check 移入 `async with lock:` 上下文内；act 后立即更新状态使后续并发 check 失败
  - **适用**：抢单触发、浏览器操作、定时任务并�?
  - **不适用**：纯只读查询、单线程顺序执行
  - **历史教训**：`_trigger_live_auto_buy` 冷却期检查在 `browser_lock` 外，3 个并发协程都通过检查后依次抢锁执行，冷却期失效；修复后�?check 移入锁内

### 28. LLM 端点能力派发与共享工具函�?🆕v4.23

- 🆕v4.23【强制�?*B-REVIEW-LLM-CAPABILITY-DISPATCH：能力驱动派发（capability-driven dispatch�?*
  - 任何 LLM/多模�?function_call/json_mode 调用必须�?*构�?payload �?*预检目标模型能力，禁�?能力-需�?不匹配的无脑发送（典型症状：调用纯文本模型时附�?`image_url` content block �?服务�?400 `unknown variant`�?
  - **核心机制**（审查时必须理解）：
    - LLM endpoint �?schema 由目标模型决定，纯文本模型不支持多模态内容块（image_url/audio_url），调用会被服务端拒�?
    - 能力预检 = 模型名（`settings.openai_vision_model` 等）�?关键字白名单（vision/function_call/json_mode）→ bool
    - 预检失败时降级为"等价文本表达"（prompt 追加"图片 URL + 描述"），而非抛错
    - 关键字白名单与判断函数必�?*共享**（见 B-REVIEW-SHARED-UTIL-CENTRALIZATION），禁止散落
  - **判断信号**�?
    - 代码�?`chat(model="xxx", messages=[{"role": "user", "content": [{"type": "text", ...}, {"type": "image_url", ...}]}])` 但未�?`if is_vision_capable(model)` �?视为违规
    - `messages` 中拼�?`image_url` content block 但调用方未校�?vision_capable �?视为违规
    - payload 构造与模型能力校验解耦（一个函数构�?payload，另一个函数调�?LLM）→ 视为高风�?
    - 关键字列表（`["vision", "gpt-4o", ...]`）直接出现在调用函数内而非 `import` 共享常量 �?视为违规
  - **修复模式**�?
    ```python
    # �?共享判断 + 预检 + 降级
    # api_ai.py（权威源�?
    _VISION_CAPABLE_KEYWORDS: tuple[str, ...] = (
        "vision", "gpt-4o", "gpt-4-vision", "qvq", "qwen-vl",
        "glm-4v", "claude-3", "opus", "sonnet", "haiku",
    )

    def _is_vision_capable(model_name: str | None) -> bool:
        if not model_name:
            return False
        return any(kw in model_name.lower() for kw in _VISION_CAPABLE_KEYWORDS)

    # api_ai_deep.py（消费方�?
    from xianyu_hunter.web.routes.api_ai import _is_vision_capable

    vision_capable = _is_vision_capable(settings.openai_vision_model)
    if not vision_capable:
        logger.warning("mode=downgrade reason=vision_missing model={}", settings.openai_vision_model)
        user_content = text + f"\n图片 URL: {image_url}（请参考文字描述分析）"
    else:
        user_content = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    ```
    ```python
    # 禁止：无脑拼�?image_url + 关键字白名单散落
    ```
  - **配置参数**：`llm_capability_keywords.vision_keywords`（默�?`["vision", "gpt-4o", "gpt-4-vision", "qvq", "qwen-vl", "glm-4v", "claude-3", "opus", "sonnet", "haiku"]`）、`llm_capability_keywords.function_call_keywords`、`llm_capability_keywords.json_mode_keywords`、`llm_capability_keywords.case_insensitive`（默�?`true`）、`llm_capability_keywords.shared_util_location`（默�?`src/xianyu_hunter/web/routes/api_ai.py`）、`llm_capability_keywords.shared_function_name`（默�?`_is_vision_capable`）在 `config.yaml` �?`llm_capability_keywords` 节点管理（与 `xianyu-hunter-dev/config/tech-stack.json` 保持单一来源�?
  - **适用**：调用外�?LLM endpoint（OpenAI/Claude/通义千问/DeepSeek/Ollama）；多模态调用（Vision/Audio）；function call / tool use；structured output / JSON mode
  - **不适用**：调用固定单一能力的稳定服务；本地固定函数（无外部 endpoint）；已由 SDK 强制约束的调�?
  - **历史教训**：深度分析无脑拼�?`image_url` content block，当 `openai_vision_model` 配置�?`qwen-turbo`/`deepseek-chat`（纯文本）时，服务端返回 400 `unknown variant 'image_url'`，触�?WARNING 日志噪音；修复时新增 `_is_vision_capable()` 共享函数 + 预检降级
- 🆕v4.23【强制�?*B-REVIEW-SHARED-UTIL-CENTRALIZATION：共享工具函数规范（避免散落内联判断�?*
  - �?�? 模块复用的判断逻辑/关键字白名单/常量必须抽取�?被依赖方"模块顶层�?*纯函�?*�?*模块级常�?*，导入方只能 `from <source_module> import <shared_name>`�?*禁止**复制粘贴关键字列表或正则字面量到多个调用�?
  - **核心机制**（审查时必须理解）：
    - 模型升级 / 协议变更时，散落在多个文件的关键字白名单必然漏改
    - 共享函数位置选择原则：业务最早引入该逻辑的模块作�?权威�?（避免循环依赖）
    - 共享函数必须满足：纯函数（无副作用）+ 类型注解完整 + 单测覆盖 + docstring 注明"为什么是共享�?
  - **判断信号**�?
    - `grep -rn "_VISION_CAPABLE_KEYWORDS" src/` 发现定义�?�?2 �?视为违规（应统一为单一权威源）
    - �?�? 文件出现相同的关键字字面量（`"vision"`, `"gpt-4o"`, `"claude-3"`）→ 视为违规
    - �?�? 文件出现相同的正则字面量 �?视为违规
    - �?�? 文件出现相同的魔法数�?字符串（`BATCH_SIZE = 100`）→ 视为可疑
  - **修复模式**�?
    ```python
    # �?单一权威源（api_ai.py�?
    _VISION_CAPABLE_KEYWORDS: tuple[str, ...] = (
        "vision", "gpt-4o", "gpt-4-vision", "qvq", "qwen-vl",
        "glm-4v", "claude-3", "opus", "sonnet", "haiku",
    )

    def _is_vision_capable(model_name: str | None) -> bool:
        """判断指定模型是否支持多模态（Vision）输入�?
        为什么共享：api_ai 成色评估 + api_ai_deep 深度分析 共用此判断，
        避免模型升级时散落修改�?
        """
        if not model_name:
            return False
        return any(kw in model_name.lower() for kw in _VISION_CAPABLE_KEYWORDS)

    # api_ai_deep.py（消费方�?
    from xianyu_hunter.web.routes.api_ai import _is_vision_capable  # 复用，不重写
    ```
    ```python
    # 禁止：两处独立关键字列表
    def is_vision_capable(model): return any(kw in model for kw in VISION_KEYWORDS)

    # api_ai_deep.py（散落，漏了 glm-4v�?
    vision_capable = "vision" in model or "gpt-4o" in model or "qwen-vl" in model
    ```
  - **配置参数**：`shared_util_rules.min_call_sites`（默�?`2`，触发抽取的最小调用点数）、`shared_util_rules.min_module_count`（默�?`2`，触发抽取的最小模块数）、`shared_util_rules.pure_function_required`（默�?`true`）、`shared_util_rules.require_type_annotation`（默�?`true`）、`shared_util_rules.require_unit_test`（默�?`true`）、`shared_util_rules.shared_function_docstring_required`（默�?`true`）在 `config.yaml` �?`shared_util_rules` 节点管理
  - **适用**：跨模块复用的关键字白名�?正则/常量；模�?接口/协议的版本判断；权限/角色/能力位判断；业务规则判断（如"是否已售"关键词）
  - **不适用**：仅单模块内部使用的 helper（不必抽取）；逻辑需要复用的同时还要扩展（应抽象为基�?策略模式）；性能敏感�?hot path 抽取会带�?import 开销（需评估�?
  - **历史教训**：本�?vision_capable 修复初版把判断内联到 `api_ai_deep.py`，与 `api_ai.py` 早已存在的关键字白名单重�?�?后续模型升级需同时�?2 �?�?散落修改风险
- 🆕v4.23【强制�?*B-REVIEW-SILENT-DOWNGRADE-PRECHECK：静默降级预检（不支持能力 �?友好降级�?*
  - "可选增�?能力（vision / function_call / json_mode）调用前必须预检，失败时降级�?等价文本表达"（如 prompt 追加"图片 URL + 描述"），**禁止**直接抛错。降级路径必须有可观测性（warning 日志 + 降级标记�? 降级 prompt 模板集中管理
  - **核心机制**（审查时必须理解）：
    - LLM 端点不支持的能力被无脑发�?�?服务�?400 �?调用�?catch + 重试 + 降级 �?链路�?+ 日志噪音
    - 预检失败时降级为等价文本表达（如 vision 缺失 �?prompt 追加"图片请参考以下文字描�?）可保持主流程继�?
    - 核心能力（chat 文本生成）缺失必须报错，不能静默降级
    - 降级 prompt 模板必须集中管理（`config.yaml` �?`llm_downgrade` 节点），禁止在调用点拼接
  - **判断信号**�?
    - 代码构�?payload 时未做能力预检 �?视为违规（与 B-REVIEW-LLM-CAPABILITY-DISPATCH 联动�?
    - 预检失败时直接抛异常（`raise ValueError("vision not supported")`）→ 视为违规（应降级�?
    - 降级路径�?warning 日志（仅静默跳过）→ 视为违规（不可观测）
    - 降级 prompt 模板以字符串字面量出现在调用函数内（`f"图片请参考以下描述：{url}"`）→ 视为违规
  - **修复模式**�?
    ```python
    # �?预检 + 降级 + warning + 集中模板
    # config.yaml
    llm_downgrade:
      prompt_templates:
        vision_missing: "图片请参考以下文字描述：{image_url}"

    # api_ai_deep.py
    vision_capable = _is_vision_capable(settings.openai_vision_model)
    if not vision_capable:
        logger.warning(
            "mode=downgrade reason=vision_missing model={}",
            settings.openai_vision_model,
        )
        downgrade_template = settings.llm_downgrade.prompt_templates["vision_missing"]
        user_content = text + "\n" + downgrade_template.format(image_url=image_url)
    else:
        user_content = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    ```
    ```python
    # 禁止：预检缺失 + 降级模板散落 + 无日�?
    ```
  - **配置参数**：`llm_downgrade.optional_capabilities`（默�?`["vision", "function_call", "json_mode"]`）、`llm_downgrade.downgrade_log_level`（默�?`warning`）、`llm_downgrade.downgrade_marker_format`（默�?`mode=downgrade reason={capability}_missing model={model_name}`）、`llm_downgrade.prompt_templates`（降�?prompt 模板字典，key 为缺失的能力名）、`llm_downgrade.core_capabilities_not_downgradable`（默�?`["chat", "text_generation", "embedding"]`）在 `config.yaml` �?`llm_downgrade` 节点管理
  - **适用**：外�?LLM endpoint + payload 含可选能力字段；多模�?/ function call / structured output 调用；用户上传图片但模型可能不支�?Vision；用户启�?tool 但模型可能不支持 function call
  - **不适用**：核心能力缺失（chat 文本生成失败必须报错）；用户明确要求某能力（如选择 vision-only 模型）；预检与降级开销大于直接调用（极简场景�?
  - **历史教训**：深度分析失败时直接�?400，调用方需�?catch + 重试 + 降级，链路长且日志噪音大；引入预检 + 降级模板后，warning 降级，prompt 文本补全，warning 计数归零

### 29. 端到端失败原因链与数据完整性闭�?🆕v4.27

基于"Failed to collect item detail: page unavailable or login expired"根因复盘（代码被回退 + 服务未重启双重原因导致修复未生效），系统化梳理端到端失败原因链传递与数据完整性预检的闭环规范。本维度涵盖失败原因传递链、数据完整性预检、合并写�?vs 覆盖写入决策、文案常量集中管理、修�?验证-部署闭环、测�?mock 同步 6 个子节点�?

- 🆕v4.27【强制�?*B-REVIEW-FAILURE-REASON-PROPAGATION：失败原因传递链（reason propagation chain�?*
  - 失败原因必须分三层传递：底层（collector/adapter）设�?`last_*_failure_reason` 属性（�?`last_detail_failure_reason`）→ 中层（service/orchestrator）将 reason 映射�?HTTP status_code �?高层（route/middleware）按 status_code 决定日志级别与降级策略�?*禁止**跨层直传字符串�?*禁止**用字符串子串做日志降�?marker
  - **核心机制**（审查时必须理解）：
    - 失败原因若只在底层设置，中层不映�?status_code，高层只能用字符串子串判�?�?文案变更即破坏降级逻辑（脆弱耦合�?
    - reason 值必须是可枚举的有限集（�?`["cookie_incomplete", "session_expired", "rate_limited", "page_unavailable", "network_timeout"]`），集中定义为模块级常量 `FAILURE_REASONS: tuple[str, ...]`
    - 文案�?reason 的映射必须集中在 `REASON_TO_STATUS_CODE: dict[str, int]` / `REASON_TO_MESSAGE: dict[str, str]` 字典，禁止在多处 if/elif 分支散落映射
    - 错误响应必须�?`error_code` 字段（machine-readable�? `detail` 字段（human-readable），前端�?`error_code` 分支而非按文案子�?
  - **判断信号**�?
    - grep `if "expired" in error_message` �?`if "page unavailable" in detail` �?字符串子串判断违�?
    - grep `last_*_failure_reason` 设置�?�?检查是否被中层 status_code 映射消费
    - grep `HTTPException(status_code=` �?检�?status_code 是否根据 reason 映射，而非硬编�?401
    - 错误响应 JSON 不含 `error_code` 字段 �?违规
  - **修复模式**�?
    ```python
    # �?三层传�?+ reason 枚举 + 字典映射 + error_code 字段
    # config.yaml
    failure_reason_propagation:
      reason_enum: ["cookie_incomplete", "session_expired", "rate_limited", "page_unavailable", "network_timeout"]
      reason_to_status_code:
        cookie_incomplete: 401
        session_expired: 440
        rate_limited: 429
        page_unavailable: 503
        network_timeout: 504

    # collector/_detail.py（底层）
    self.last_detail_failure_reason = "cookie_incomplete"

    # collection_service.py（中层）
    reason = collector.last_detail_failure_reason
    status_code = settings.failure_reason_propagation.reason_to_status_code.get(reason, 500)
    raise HTTPException(status_code=status_code, detail={"error_code": reason, "message": "..."})

    # exception_handler.py（高层）
    if exc.status_code in (429, 503, 504):
        logger.warning("...")  # 降级
    elif exc.status_code == 401:
        logger.error("...")   # 需用户介入
    ```
    ```python
    # 禁止：字符串子串判断 + 硬编�?status_code
    ```
  - **配置参数**：`failure_reason_propagation.reason_enum`（reason 可枚举集合）、`failure_reason_propagation.reason_to_status_code`（reason �?HTTP 状态码映射字典）、`failure_reason_propagation.reason_to_message`（reason �?用户可读文案映射）、`failure_reason_propagation.forbidden_substring_markers`（禁止用作降级判断的字符串子串黑名单）、`failure_reason_propagation.require_error_code_field`（默�?`true`，错误响应必须含 `error_code` 字段）在 `config.yaml` �?`failure_reason_propagation` 节点管理
  - **适用**：含多层架构（collector �?service �?route）的失败处理链；多类失败原因需要不�?HTTP 状态码区分的场景；前端需要按 error_code 分支展示不同提示的场�?
  - **不适用**：单层函数内部错误（无传递链）；纯输入校验错误（422 直接返回）；不可恢复的系统级错误�?00 直接抛出�?
  - **历史教训**：v4.27 修复�?`Failed to collect item detail: page unavailable or login expired` 文案同时覆盖"cookie 过期"�?页面不可�?两类语义，前端无法区分需用户重新登录还是稍后重试；reason 链路化后�?01（cookie 不完整）+ 503（页面不可用�? 429（限流）+ 504（超时）四态分�?

- 🆕v4.27【强制�?*B-REVIEW-DATA-COMPLETENESS-PRECHECK：数据完整性预检（pre-call completeness check�?*
  - 调用外部依赖（浏览器、HTTP API、第三方服务）前必须执行数据完整性预检，预检方法签名固定�?`async def _check_xxx_completeness(self) -> str | None`，返�?`None` 表示通过、返回字符串表示错误描述�?*禁止**直接调用外部依赖后再发现数据不完整（已消耗资源）
  - **核心机制**（审查时必须理解）：
    - 单一阈值判断不够（�?cookie 数量 �?10"）——可�?10 个全是身�?cookie 缺会�?cookie，必须用**双阈�?AND 判断**：总数阈�?+ 关键项命中数阈�?
    - 预检必须在调用前 + 调用后各执行一次（调用后二次检查防御外部依赖中途失效）
    - 错误信息必须含具体缺失清单（�?身份 Cookie [cookie2, sgcookie] 存在，会�?Cookie [cna, tracknick, _tb_token_] 不足"），禁止笼统�?数据不完�?
  - **判断信号**�?
    - grep `await page.goto` �?`await client.get` �?检查调用前是否�?`_check_*_completeness` 预检
    - 预检方法签名�?`str | None` 返回类型 �?违规（应统一签名�?
    - 预检只用单一阈值（�?`if len(cookies) < 10`）→ 违规（缺关键项命中数判断�?
    - 预检错误信息�?数据不完�?/"参数错误"等笼统描�?�?违规
    - 调用后无二次检�?�?违规（外部依赖可能中途失效）
  - **修复模式**�?
    ```python
    # �?双阈�?AND 判断 + 调用前预检 + 调用后二次检�?+ 具体缺失清单
    _DETAIL_COOKIE_MIN_COUNT = 10  # config: data_completeness_precheck.min_count
    _DETAIL_SESSION_MIN_HITS = 3   # config: data_completeness_precheck.min_key_hits

    async def _check_detail_cookie_completeness(self) -> str | None:
        cookies = await self._get_browser_cookies()
        cookie_names = {c.get("name", "") for c in cookies}
        identity_found = set(_OFFICIAL_COLLECT_IDENTITY_COOKIES) & cookie_names
        session_found = _DETAIL_SESSION_COOKIES & cookie_names
        # 双阈�?AND 判断
        if len(cookies) >= _DETAIL_COOKIE_MIN_COUNT and len(session_found) >= _DETAIL_SESSION_MIN_HITS:
            return None
        # 具体缺失清单
        return (
            f"闲鱼登录 Cookie 不完整（�?{len(cookies)} 个，"
            f"身份 Cookie {sorted(identity_found)} 存在�?
            f"会话 Cookie {sorted(session_found)} 不足），"
            f"请重新登录或从浏览器导出完整 Cookie 导入"
        )

    async def _collect_detail_only(self, item_id: str):
        # 调用前预检
        if reason := await self._check_detail_cookie_completeness():
            raise HTTPException(status_code=401, detail={"error_code": "cookie_incomplete", "message": reason})
        result = await collector.detail(item_id)
        # 调用后二次检�?
        if not result and collector.last_detail_failure_reason:
            raise HTTPException(status_code=503, detail={"error_code": collector.last_detail_failure_reason})
    ```
    ```python
    # 禁止：单阈�?+ 无签�?+ 笼统错误信息 + 无二次检�?
    async def _check_cookies(self) -> bool:
        if len(await self._get_cookies()) < 10:
            return False
        return True
    ```
  - **配置参数**：`data_completeness_precheck.method_name_pattern`（预检方法名模式，默认 `_check_*_completeness`）、`data_completeness_precheck.return_type`（默�?`str | None`）、`data_completeness_precheck.require_dual_threshold`（默�?`true`，强制双阈�?AND 判断）、`data_completeness_precheck.require_post_call_check`（默�?`true`，强制调用后二次检查）、`data_completeness_precheck.require_missing_list_in_message`（默�?`true`，错误信息必须含具体缺失清单）、`data_completeness_precheck.min_count`（总数阈值，默认 10）、`data_completeness_precheck.min_key_hits`（关键项命中数阈值，默认 3）在 `config.yaml` �?`data_completeness_precheck` 节点管理
  - **适用**：调用浏览器自动化（依赖完整 cookie 集）；调用第三方 API（依赖完整请求头/认证 token）；调用本地服务（依赖完整配置文件）；任�?数据不完整即调用失败"的场�?
  - **不适用**：幂等查询接口（缺数据可返回空集合，无需预检）；纯计算函数（无外部依赖）；用户输入校验（�?Pydantic 模型校验�?
  - **历史教训**：v4.27 修复前仅检�?4 个身�?cookie 存在性，未检�?22 个完�?cookie 集，导致闲鱼详情�?SPA 渲染失败（依赖完整会�?cookie）；双阈�?AND 判断后，38 �?cookie + 5 个关键会�?cookie 命中才放�?

- 🆕v4.27【强制�?*B-REVIEW-MERGE-VS-OVERWRITE-WRITE：合并写�?vs 覆盖写入决策（merge vs overwrite write strategy�?*
  - 持久化层（JSON 文件 / SQLite / 配置文件）写入时必须按数据来源选择策略：新数据�?*完整�?*（如全量导出）→ 覆盖写；新数据是**部分�?*（如增量导入、用户单点更新）�?合并写�?*禁止**对部分集数据使用覆盖写（会丢失旧文件中的其他数据�?
  - **核心机制**（审查时必须理解）：
    - 合并写方法签名固定为 `def merge_xxx(self, new_items: list[dict] | dict) -> bool`，返�?`True` 表示合并成功
    - 合并策略：以唯一 key（如 cookie �?`name` 字段、用户的 `id` 字段）为索引，相�?key 的新值覆盖旧值，旧文件中其他项全部保�?
    - 合并后必须日志输出合并前后数量变化（�?`merge_cookies: 4 �?38 (added 34, updated 4)`�?
    - 覆盖写必须先验证新集完整（调�?`_check_xxx_completeness` 预检），否则禁止覆盖
  - **判断信号**�?
    - grep `json.dump(` �?`write_text(` �?检查写入策略是否匹配数据来�?
    - grep `export_cookies` / `save_config` �?检查是否区�?`merge_*` �?`overwrite_*` 两个方法
    - 部分集数据（如浏览器导入�?4 �?cookie）调用覆盖写方法 �?违规
    - 合并写方法无日志输出合并前后数量 �?违规
    - 覆盖写前未调用预检验证新集完整 �?违规
  - **修复模式**�?
    ```python
    # �?合并写：�?name �?key 合并，旧文件中其�?cookie 全部保留
    def merge_cookies(self, new_cookies: list[dict]) -> bool:
        old_cookies = self._load_json_cookies()  # 38 �?
        old_by_name = {c["name"]: c for c in old_cookies}
        added, updated = 0, 0
        for new_c in new_cookies:  # 4 个新导入
            name = new_c["name"]
            if name in old_by_name:
                old_by_name[name] = new_c
                updated += 1
            else:
                old_by_name[name] = new_c
                added += 1
        merged = list(old_by_name.values())
        self._write_json_cookies(merged)
        logger.info(f"merge_cookies: {len(old_cookies)} �?{len(merged)} (added {added}, updated {updated})")
        return True

    # 禁止：覆盖写丢失旧数�?
    def save_cookies(self, new_cookies: list[dict]):  # 4 个新导入覆盖 38 个旧数据
        self._write_json_cookies(new_cookies)
    ```
  - **配置参数**：`write_strategy_decision.merge_method_pattern`（合并写方法名模式，默认 `merge_*`）、`write_strategy_decision.overwrite_method_pattern`（覆盖写方法名模式，默认 `save_*` / `export_*`）、`write_strategy_decision.require_log_on_merge`（默�?`true`，合并后必须日志输出合并前后数量）、`write_strategy_decision.require_precheck_before_overwrite`（默�?`true`，覆盖写前必须预检新集完整）、`write_strategy_decision.unique_key_field_examples`（唯一 key 字段示例，如 `["name", "id", "key"]`）在 `config.yaml` �?`write_strategy_decision` 节点管理
  - **适用**：浏览器 Cookie 导入（部分集，必须合并写）；用户偏好导入（部分集）；配置文件增量更新（部分集）；全量备份恢复（完整集，可覆盖写）；首次初始化（无旧文件，可覆盖写�?
  - **不适用**：内存缓存更新（无持久化）；日志文件追加（无合并概念）；临时文件写入（无历史数据需要保留）
  - **历史教训**：v4.27 修复前浏览器 Cookie 导入�?`export_cookies`（覆盖写），4 个新 cookie 覆盖�?38 个旧 cookie，导�?cookie 集从 38 �?4，闲鱼详情页 SPA 渲染失败；改�?`merge_cookies` 后，4 个新 cookie 合并�?38 个旧 cookie，cookie 集从 4 �?38 恢复

- 🆕v4.27【强制�?*B-REVIEW-ERROR-MESSAGE-CONSTANT：文案常量集中管理（error message constant centralization�?*
  - 错误文案、日志降�?marker、用户提示信息必须提取为模块级常量（`_ERROR_MSG_*` / `_LOG_MARKER_*`），跨模块引用必�?`from <source> import _MSG_*`�?*禁止**用字符串子串做日志降�?marker（如 `if "expired" in detail:`），**禁止**在多处内联相同文�?
  - **核心机制**（审查时必须理解）：
    - 文案常量集中定义为模块级 `tuple[str, ...]` �?`dict[str, str]`，并注释文案来源（如 `# 来源：闲鱼详情页错误提示，v4.27 修复时提炼`�?
    - 跨模块引用必�?import 常量，禁止重新定义相同字符串
    - 错误响应必须�?`error_code` 字段（machine-readable），前端�?`error_code` 分支而非按文案子�?
    - 日志降级判断必须用常量集合（�?`if reason in DOWNGRADE_REASONS:`），禁止字符串子串判�?
  - **判断信号**�?
    - grep `if "expired" in` / `if "unavailable" in` / `if "rate limited" in` �?字符串子串判断违�?
    - 同一文案字符串在代码中出�?�?2 处未提取为常�?�?违规（与 B-REVIEW-LOG-DOWNGRADE-STABILITY 联动�?
    - 错误响应 JSON 不含 `error_code` 字段 �?违规
    - 跨模�?import 同一文案常量失败（重新定义相同字符串）→ 违规
  - **修复模式**�?
    ```python
    # �?文案常量集中 + error_code 字段 + 常量集合判断
    # collection_service.py
    _ERROR_MSG_COOKIE_INCOMPLETE = "闲鱼登录 Cookie 不完整，请重新登录或从浏览器导出完整 Cookie 导入"
    _ERROR_MSG_PAGE_UNAVAILABLE = "闲鱼详情页暂时不可用，请稍后重试"
    _DOWNGRADE_REASONS = frozenset({"rate_limited", "page_unavailable", "network_timeout"})

    # 跨模块引�?
    from .collection_service import _ERROR_MSG_COOKIE_INCOMPLETE

    # 日志降级判断用常量集�?
    if reason in _DOWNGRADE_REASONS:
        logger.warning("mode=downgrade reason={}", reason)
    ```
    ```python
    # 禁止：字符串子串判断 + 内联文案 + �?error_code
    ```
  - **配置参数**：`error_message_centralization.require_constant_extraction`（默�?`true`，强制提取为模块级常量）、`error_message_centralization.require_version_comment`（默�?`true`，常量定义处必须注释历史来源）、`error_message_centralization.require_error_code_field`（默�?`true`，错误响应必须含 `error_code` 字段）、`error_message_centralization.forbidden_substring_markers`（禁止用作降级判断的字符串子串黑名单，如 `["expired", "unavailable", "rate limited"]`）、`error_message_centralization.max_inline_occurrences`（默�?`1`，同一文案允许内联次数）在 `config.yaml` �?`error_message_centralization` 节点管理
  - **适用**：错误响应文案（401/403/500 等）；日志降�?marker；用户提示信息（前端 toast/message）；跨模块复用的常量文案
  - **不适用**：一次性临时调试日志（无需提取）；动态生成的文案（如 `f"task {task_id} failed"`）；纯内部断言消息（如 `assert x > 0, "x must be positive"`�?
  - **历史教训**：v4.27 修复�?`Failed to collect item detail: page unavailable or login expired` 文案�?collection_service / cookie_inject / exception_handler 三处内联，文案变更需�?3 处；提取为常量后，文案变更只需�?1 处，前端�?`error_code` 分支而非按文案子�?

- 🆕v4.27【强制�?*B-REVIEW-EDIT-VERIFY-DEPLOY-LOOP：修�?验证-部署闭环（edit-verify-deploy closed loop�?*
  - 使用 Edit 工具修改文件后必须立即用 Grep/Read 验证修改是否真正生效（grep 标志性标识符确认�?false positive）；Python 修改后必须重启服务（旧进程仍在运行旧代码）；重启后必须验证端口监�?+ 数据状态；`git stash` 前必须先 `git commit` 保底（避�?stash 丢失）�?*禁止**修改后直接交付用户验�?
  - **核心机制**（审查时必须理解）：
    - Edit 工具可能�?`old_string` 不唯一而失败（返回成功但未修改），必须�?Grep 验证标志性标识符（如新方法名、新常量名）确实存在于文件中
    - 全局 grep 旧文案（�?`Failed to collect item detail`）确认无残留（可能多处内联，必须全部修改�?
    - Python 修改后旧进程仍在运行旧代码，必须 `taskkill /F /T /PID` 终止旧进�?+ 重启服务
    - 重启后必须验证端口监听（`netstat -ano | findstr :8000`�? 数据状态（�?cookie 数量、配置文件内容）
    - `git stash` 会丢失未提交的工作区修改，必须先 `git commit -m "wip"` 保底，再 stash
  - **判断信号**�?
    - AI 助手修改文件后未 grep 验证 �?违规
    - 用户反馈"还是报错"，排查发�?Python 进程启动时间早于代码修改时间 �?服务未重启违�?
    - `git stash` 后工作区修改丢失，无法恢�?�?未先 commit 保底违规
    - 重启后未验证端口监听 �?违规（可能端口被占用，新进程启动失败但未发现�?
  - **修复模式**�?
    ```powershell
    # �?修改-验证-部署闭环
    # 1. Edit 修改 collection_service.py 新增 _check_detail_cookie_completeness 方法
    # 2. Grep 验证标志性标识符
    Grep _check_detail_cookie_completeness collection_service.py  # 应有匹配
    # 3. 全局 grep 旧文�?
    Grep "Failed to collect item detail: page unavailable or login expired"  # 应无匹配
    # 4. 终止旧进�?
    taskkill /F /T /PID 27020
    # 5. 重启服务
    .venv\Scripts\python.exe -m xianyu_hunter web
    # 6. 验证端口监听
    netstat -ano | findstr :8000  # 应有 LISTENING
    # 7. 验证数据状�?
    Read data\cookies_default.json  # 应有 38 �?cookie
    ```
    ```powershell
    # 禁止：修改后未验�?+ 未重启服�?
    ```
  - **配置参数**：`edit_verify_deploy_loop.require_grep_verify_after_edit`（默�?`true`，Edit 后必�?Grep 验证）、`edit_verify_deploy_loop.require_global_grep_old_message`（默�?`true`，全局 grep 旧文案确认无残留）、`edit_verify_deploy_loop.require_restart_python_service`（默�?`true`，Python 修改后必须重启服务）、`edit_verify_deploy_loop.require_port_verify_after_restart`（默�?`true`，重启后必须验证端口监听）、`edit_verify_deploy_loop.require_data_state_verify`（默�?`true`，重启后必须验证数据状态）、`edit_verify_deploy_loop.require_commit_before_stash`（默�?`true`，git stash 前必须先 commit 保底）、`edit_verify_deploy_loop.verify_port`（默�?`8000`）、`edit_verify_deploy_loop.verify_data_file_examples`（验证数据文件示例，�?`["data/cookies_default.json"]`）在 `config.yaml` �?`edit_verify_deploy_loop` 节点管理
  - **适用**：AI 助手使用 Edit 工具修改代码后；Python 服务代码修改后需重启的场景；多文件修改后需全局验证的场景；使用 git stash 的工作流
  - **不适用**：纯前端修改（前�?vite 热更新，无需重启）；纯文档修改（不影响运行时）；纯测试代码修改（pytest 重新执行即生效）；使�?git worktree 的隔离工作流（无需 stash�?
  - **历史教训**：v4.27 修复�?Edit 工具修改 collection_service.py 后未 grep 验证，未重启服务，用户反�?还是报错"，排查发�?Python 进程（PID 27020）启动时�?17:19:25 早于代码修改时间 17:30，旧进程仍在运行旧代码；闭环规范后，Edit �?Grep �?taskkill �?重启 �?端口验证 �?数据验证 6 步走

- 🆕v4.27【强制�?*B-REVIEW-TEST-MOCK-SYNC：测�?mock 同步（test mock synchronization�?*
  - 修改前置条件（如新增 cookie 完整性预检、新增配置项、新增方法参数）时必须同步更新测�?mock 数据，mock 数据必须覆盖完整字段集（�?22 �?cookie 而非 4 个）�?*禁止**修改前置条件后不更新测试 mock（测试会因前置条件不满足而失败，但开发者可能误以为�?mock 不全而非前置条件变更�?
  - **核心机制**（审查时必须理解）：
    - 修改前置条件（如新增 `_check_detail_cookie_completeness` 方法）后，原测试 mock �?4 �?cookie，预检读不到完�?cookie 集抛 401，测试失�?
    - mock 数据必须覆盖完整字段集（�?22 �?cookie�? 个身�?+ 5 个会�?+ 13 个其他），而非最小集
    - 测试失败时必须优先检查前置条件变更（grep 最近修改的方法签名、新增的预检方法），而非盲目调整 mock
    - mock 数据集中管理（如 `tests/conftest.py` �?`MOCK_COOKIES` 常量），禁止在多个测试文件中重复定义
  - **判断信号**�?
    - grep 测试文件中的 mock 数据（如 `MOCK_COOKIES = [...]`）→ 检查是否覆盖完整字段集
    - 测试失败时错误信息为 `AssertionError: expected 401 but got 200` �?`KeyError: 'cna'` �?优先检查前置条件变�?
    - 同一 mock 数据在多个测试文件中重复定义 �?违规（应集中管理�?
    - 修改前置条件后未同步更新测试 mock �?违规
  - **修复模式**�?
    ```python
    # �?mock 数据集中管理 + 完整字段�?+ 同步更新
    # tests/conftest.py
    MOCK_COOKIES = [
        {"name": n, "value": "v"} for n in [
            # 身份 Cookie�? 个）
            "cookie2", "sgcookie", "unb", "_m_h5_tk",
            # 会话 Cookie�? 个）
            "cna", "tracknick", "_tb_token_", "t", "tfstk",
            # 其他 Cookie�?3 个）
            "xlly_s", "_samesite_flag_", "KLNotice", "isg", "tfstk",
            # ... �?22 �?
        ]
    ]

    # tests/test_collection_service.py
    container.browser.get_cookies = AsyncMock(return_value=MOCK_COOKIES)
    ```
    ```python
    # 禁止：mock 数据不完�?+ 修改前置条件后未同步更新
    ```
  - **配置参数**：`test_mock_synchronization.require_full_field_set`（默�?`true`，mock 数据必须覆盖完整字段集）、`test_mock_synchronization.require_centralized_management`（默�?`true`，mock 数据集中管理�?conftest.py）、`test_mock_synchronization.require_sync_on_precondition_change`（默�?`true`，修改前置条件时必须同步更新 mock）、`test_mock_synchronization.priority_check_on_failure`（默�?`precondition_change`，测试失败时优先检查前置条件变更）、`test_mock_synchronization.min_cookie_count_for_detail_test`（默�?`22`，详情采集测�?mock cookie 最小数量）、`test_mock_synchronization.mock_data_location`（默�?`tests/conftest.py`）在 `config.yaml` �?`test_mock_synchronization` 节点管理
  - **适用**：修改前置条件（新增预检方法、新增配置项、新增方法参数）后；测试失败时优先排查方向；mock 数据管理；新增测试用例时参考完整字段集
  - **不适用**：纯 UI 测试（无前置条件依赖）；一次性临时测试（无需集中管理）；纯函数测试（无外部依�?mock�?
  - **历史教训**：v4.27 修复前新�?`_check_detail_cookie_completeness` 方法后，原测�?mock �?4 �?cookie，预检失败�?401，测试用�?`test_collection_service.py` 3/3 失败；同步更�?mock �?12 �?cookie�? 身份 + 5 会话 + 3 其他）后�?/3 通过

- 🆕v4.28【强制�?*B-REVIEW-121: 时区一致性检查（timezone consistency�?*
  - 规范引用：DATETIME-TZ-01 时区一致性三步检查法
  - datetime 减法/比较前必须统一 tzinfo，禁�?aware �?naive 混用导致 `TypeError: can't subtract offset-naive and offset-aware datetimes`�?*核心机制**：项目内统一时区策略（naive �?aware），`_utcnow()` 返回 aware 时所�?DB 字段也必�?aware；DB 字段�?naive 时调用方必须 `.replace(tzinfo=None)` 统一�?*判断信号**：grep `_utcnow() - row\.` / `_utcnow() < row\.` 检查右侧是否同 tzinfo；`TypeError: offset-naive vs aware` 异常即违反�?*修复模式**：`diff = _utcnow().replace(tzinfo=None) - row.created_at`（naive 策略）或 `diff = _utcnow() - row.created_at.replace(tzinfo=timezone.utc)`（aware 策略）�?*配置参数**：`coding_standards.datetime.default_timezone`（默�?`naive`）在 `config.yaml` 管理�?*适用**：所�?datetime 减法/比较场景；定时任务计算下次执行时间；过期判断�?*不适用**：纯日期字段（无时间）；UTC 时间戳数值比较�?*历史教训**：v4.28 修复�?`_utcnow()` 返回 aware，`row.created_at` �?naive，`diff = _utcnow() - row.created_at` �?TypeError 导致任务调度失败

- 🆕v4.28【强制�?*B-REVIEW-122: 原生 SQL 返回值类型防御（raw SQL return type defense�?*
  - 规范引用：DATETIME-TZ-02 原生 SQL 类型强制转换
  - `text()` 查询返回的标量值必须做类型转换，禁止直接调�?`.isoformat()` / `.timestamp()` 等方法（不同 SQLite 驱动返回 `str` / `datetime` / `bytes` 不一致）�?*核心机制**：raw SQL 结果集类型不确定，必须用 `_coerce_datetime(value)` 等强制转换函数包裹；转换函数检�?`isinstance(value, datetime)` 直返、`isinstance(value, str)` 解析、其他类�?fallback�?*判断信号**：grep `text\(.*\).*\.isoformat\(\)` / `result\.scalar\(\)\.isoformat` 检查是否漏类型转换；`AttributeError: 'str' object has no attribute 'isoformat'` 即违反�?*修复模式**：`dt = _coerce_datetime(value); dt.isoformat()`（强制转换）vs `value.isoformat()`（直接调用，违规）�?*配置参数**：`coding_standards.datetime.raw_sql_coerce`（默�?`true`）在 `config.yaml` 管理�?*适用**：所�?`session.execute(text(...))` 标量查询；ORM `column_property` 派生字段；自定义聚合查询�?*不适用**：ORM 模型字段（已有类型声明）；纯数�?字符串查询�?*历史教训**：v4.28 修复�?`text("SELECT MAX(created_at) FROM events")` 返回 str，调�?`.isoformat()` �?AttributeError

- 🆕v4.28【强制�?*B-REVIEW-123: 迁移步骤独立性（migration step independence�?*
  - 规范引用：MIGRATE-01 迁移块独立容�?
  - 多个迁移步骤（C-01/C-02/C-03/C-04/C-05）必须各�?try/except，禁止外层统一 try/except 吞掉异常导致后续步骤跳过�?*核心机制**：每个迁移步骤独�?try/except + warning 日志，单步失败不阻断后续；强依赖场景（C-02 依赖 C-01 的列存在）允许合并；步骤边界用注�?`# C-01: xxx` 标识�?*判断信号**：grep `try:.*C-01.*C-02.*C-03` �?try 多步骤即违规；`except: pass` 包裹多个迁移步骤即违规�?*修复模式**：每个步骤独�?`try: ... except Exception as e: logger.warning(...)`（正确）vs `try: C-01; C-02; C-03; except: pass`（错误，C-01 失败导致 C-02/C-03 跳过）�?*配置参数**：`coding_standards.migration.independent_steps`（默�?`[C-01, C-02, C-03, C-04, C-05]`）、`coding_standards.migration.allow_merge_when`（默�?`strong_dependency`）在 `config.yaml` 管理�?*适用**：所�?`_migrate_*` 函数；多步骤数据迁移；schema 演进�?*不适用**：单步骤迁移；强依赖迁移链（C-02 必须�?C-01 后）�?*历史教训**：v4.28 修复�?5 个迁移步骤被外层 try/except 包裹，C-01 失败导致 C-04 未执行，列缺�?

- 🆕v4.28【强制�?*B-REVIEW-124: NOT NULL 字段防御（NOT NULL field defense�?*
  - 规范引用：NULL-01 NOT NULL 字段 API 层防�?
  - NOT NULL 字段�?API 层必须有 null 防御，禁�?`data.get('field')` 直接赋值（可能返回 None 触发 IntegrityError）�?*核心机制**：API 层校�?`if data.get('field') is None: raise HTTPException(422, detail="field 不能为空")`；与 B-REVIEW-111 NOT-NULL-NONE-DEFENSE 配合（B-REVIEW-111 �?DB 写入�?pop，本检查是 API 层前置校验）�?*判断信号**：grep `task\.\w+ = data\.get\(` 检查字段是否为 NOT NULL；`IntegrityError: NOT NULL constraint failed` 即违反�?*修复模式**：`if data.get('interval_seconds') is None: raise HTTPException(422)`（防御）vs `task.interval_seconds = data.get('interval_seconds')`（直接赋值，可能 None）�?*配置参数**：`coding_standards.null_defense.check_fields`（默�?`[interval_seconds, use_cron]`）在 `config.yaml` 管理�?*适用**：所�?PATCH/PUT 接口；NOT NULL 字段更新；用户输入写�?DB�?*不适用**：可空字段；有默认值字段；系统自动填充字段�?*历史教训**：v4.28 修复�?`task.interval_seconds = data.get('interval_seconds')` 在用户未传字段时写入 None，触�?IntegrityError

- 🆕v4.28【强制�?*B-REVIEW-125: 查询过滤条件精确性（query filter precision�?*
  - 规范引用：QUERY-01 过滤条件精确性检�?
  - 查询过滤条件必须精确匹配业务语义，禁�?`startswith` / `contains` 等模糊匹配引入噪声数据�?*核心机制**：业务需要精确匹配时必须�?`==`，需要前缀匹配时评估是否会引入无关数据；`startswith('eval.')` 会同时匹�?`eval.scored` �?`eval.passed`，若只需 `eval.scored` 必须�?`==`�?*判断信号**：grep `filter\(.*startswith\(` 评估是否应改 `==`；统计结果与预期不符时优先排查过滤条件�?*修复模式**：`filter(events.type == 'eval.scored')`（精确）vs `filter(events.type.startswith('eval.'))`（模糊，引入 `eval.passed` 噪声）�?*配置参数**：`coding_standards.query_filter.precision_check`（默�?`true`）在 `config.yaml` 管理�?*适用**：所�?ORM 查询；统计聚合；分页查询�?*不适用**：模糊搜索场景（用户输入关键词）；日志查询�?*历史教训**：v4.28 修复�?`filter(events.type.startswith('eval.'))` 同时匹配 `eval.scored` �?`eval.passed`，导致评分统计翻�?

- 🆕v4.28【强制�?*B-REVIEW-126: 状态值枚举一致性（enum value consistency�?*
  - 规范引用：ENUM-01 状态值枚举一致�?
  - 业务逻辑中的状态值字符串必须�?DB 存储值一致，禁止硬编码字符串导致前后�?DB 不一致�?*核心机制**：状态值必须集中定义为枚举常量（如 `class OrderStatus(str, Enum): SUCCEEDED = 'succeeded'`），业务代码引用常量而非字面量；DB 存储值、API 响应值、业务判断值三者必须引用同一常量�?*判断信号**：grep `filter\(.*status == ['"]` 检查是否硬编码字符串；状态值与 DB 实际存储不符的查询返回空结果�?*修复模式**：`query.filter(Order.status == OrderStatus.SUCCEEDED)`（常量引用）vs `query.filter(Order.status == 'paid')`（硬编码，DB 实际�?`succeeded`）�?*配置参数**：`coding_standards.enum_consistency.status_fields`（默�?`[order_status, eval_status, notify_status]`）在 `config.yaml` 管理�?*适用**：所有状态字段查询；状态转换逻辑；前后端状态同步�?*不适用**：临时调试查询；一次性数据修复脚本�?*历史教训**：v4.28 修复�?`Order.status == 'paid'` 硬编码，DB 实际�?`succeeded`，查询永远返回空

- 🆕v4.28【强制�?*B-REVIEW-127: 错误归因精细化（error attribution refinement�?*
  - 规范引用：ATTRIB-01 错误归因精细�?
  - 外部调用失败必须根据 failure_reason 映射具体 HTTP 状态码，禁止统一返回 502 无具体原因�?*核心机制**：failure_reason 字段必须可枚举（token_expired/anti_crawler/page_unavailable/other），每个 reason 映射到具体状态码�?01/429/503/502）；�?B-REVIEW-FAILURE-REASON-PROPAGATION 配合（v4.27 失败原因传递链）�?*判断信号**：grep `raise HTTPException\(502` 检查是否无具体原因；前端无法区分错误类型即违反�?*修复模式**：`status_map = {'token_expired': 401, 'anti_crawler': 429, 'page_unavailable': 503, 'other': 502}; raise HTTPException(status_map.get(reason, 502))`（精细化映射）vs `raise HTTPException(502)`（无具体原因）�?*配置参数**：`coding_standards.error_attribution.status_mapping`（默�?`{token_expired: 401, anti_crawler: 429, page_unavailable: 503, other: 502}`）在 `config.yaml` 管理�?*适用**：所有外部调用失败的 HTTP 响应；LLM API 调用；浏览器自动化失败�?*不适用**：内部业务逻辑错误（用 400/422）；认证授权错误（用 401/403）�?*历史教训**：v4.28 修复前所有外部失败统一返回 502，前端无法区�?token 过期（需重新登录）与反爬（需等待重试�?

- 🆕v4.28【强制�?*B-REVIEW-128: 异常传播完整性（exception propagation integrity�?*
  - 规范引用：EXCEPT-01 异常传播完整�?
  - 禁止 `except: return False` 吞掉异常返回默认值，必须检测具体异常类型并重新抛出关键异常�?*核心机制**：except 块必须区�?预期异常"（可降级处理）与"非预期异�?（必须重新抛出）；浏览器自动化场景必须检�?`page.is_closed()` 并重新抛�?`TargetClosedError`�?*判断信号**：grep `except.*:\s*return False` 检查是否吞掉异常；`except Exception: pass` 无日志即违反�?*修复模式**：`try: ... except TargetClosedError: raise  # 重新抛出关键异常 except Exception as e: logger.warning(...); return False  # 降级处理`（正确）vs `try: ... except: return False  # 隐藏问题`（错误）�?*适用**：所�?try/except 块；浏览器自动化异常处理；外�?API 调用�?*不适用**：清理代码（finally 中的异常可降级）；日志记录失败（不应阻断主流程）�?*历史教训**：v4.28 修复前浏览器页面关闭后被 `except: return False` 吞掉，下游误以为采集成功

- 🆕v4.28【强制�?*B-REVIEW-129: 错误消息透传（error message transparency�?*
  - 规范引用：ERROR-01 错误消息透传
  - HTTPException 必须返回具体 detail，禁止用"操作失败"等通用文案掩盖根因�?*核心机制**：detail 字段必须包含具体错误原因（含字段�?�?约束），�?f-string 拼接上下文信息；�?B-REVIEW-ERROR-MESSAGE-CONSTANT 配合（v4.27 文案常量集中管理，本检查关�?detail 透传）�?*判断信号**：grep `HTTPException\(400,\s*['"]操作失败` / `HTTPException\(.*,\s*['"]失败['"]` 检查通用文案；前端无法定位问题即违反�?*修复模式**：`raise HTTPException(400, detail=f"配置校验失败：{e}")`（透传根因）vs `raise HTTPException(400, "操作失败")`（通用文案）�?*适用**：所�?HTTPException 抛出；API 参数校验；业务逻辑错误�?*不适用**：敏感信息错误（需脱敏）；安全相关错误（不应透露内部状态）�?*历史教训**：v4.28 修复前所有配置错误返�?操作失败"，用户无法定位是哪个字段校验失败

- 🆕v4.28【强制�?*B-REVIEW-130: 重试策略配置化（retry strategy configuration�?*
  - 规范引用：RETRY-01 重试策略配置�?
  - 重试次数必须�?config 读取，禁止硬编码 `for i in range(10)`�?*核心机制**：重试次数、间隔、退避策略（固定/指数）必须集中在 config.yaml 管理；与 B-REVIEW-FALLBACK-CHAIN 配合（v4.3 降级链模式，本检查关注重试次数配置化）�?*判断信号**：grep `for i in range\(\d+\)` 在重试场景检测硬编码；grep `retry_count` / `max_retries` 检查是否从 config 读取�?*修复模式**：`for i in range(config.retry_count):`（配置化）vs `for i in range(10):`（硬编码）�?*配置参数**：`coding_standards.retry.default_count`（默�?`3`）、`coding_standards.retry.default_interval`（默�?`1.0`）、`coding_standards.retry.backoff`（默�?`exponential`）在 `config.yaml` 管理�?*适用**：所有重试循环；外部 API 调用重试；网络请求重试�?*不适用**：固定次数的批量处理（非重试）；测试用例中的 mock 循环�?*历史教训**：v4.28 修复前硬编码 `range(10)` 重试 10 次，生产环境反爬触发后请求量暴增被封�?

- 🆕v4.28【强制�?*B-REVIEW-131: 已知场景日志降噪（log noise suppression�?*
  - 规范引用：LOG-NOISE-01 已知场景日志降噪
  - 高频已知错误必须聚合/降级，禁止每次都输出 WARNING 导致日志爆炸�?*核心机制**：首次出现输�?WARNING，后续在冷却期内（如 300s）降级为 DEBUG；降噪模式按 pattern 匹配（如 `cookie_expired`）；�?B-REVIEW-LOGURU-PLACEHOLDER 配合（v4.10 占位符一致性，本检查关注降噪）�?*判断信号**：grep `logger.warning.*cookie.*expired` 检查是否无降噪；同一 WARNING 出现 300+ 次即违反�?*修复模式**：首�?WARNING + 后续 DEBUG + 冷却�?300s（正确）vs `logger.warning(f'Cookie expired: {e}')` 每次�?WARNING（错误）�?*配置参数**：`coding_standards.log_noise.suppress_patterns`（默�?`[{pattern: 'cookie_expired', first_level: WARNING, repeat_level: DEBUG, cooldown_seconds: 300}]`）在 `config.yaml` 管理�?*适用**：高频已知错误（cookie 过期/反爬触发/页面不可用）；定时任务日志；外部 API 失败日志�?*不适用**：未知错误（必须 WARNING+）；首次出现的错误；关键路径错误�?*历史教训**：v4.28 修复�?cookie 过期 WARNING 输出 300+ 次，淹没真正关键日志

- 🆕v4.28【强制�?*B-REVIEW-132: 熔断器持久化对称性（circuit breaker cleanup symmetry�?*
  - 规范引用：CIRCUIT-01 熔断器持久化对称�?
  - 熔断分支与停止分支的清理逻辑必须对称，禁止熔断分�?break 但未调用 `_save_progress()` 导致状态丢失�?*核心机制**：所有退出循环的分支（熔�?停止/正常完成）必须执行相同的持久化流程（save_progress + record_state + notify_downstream）；�?cleanup_checklist 清单核对�?*判断信号**：grep `break` 在循环内检查是否调�?`_save_progress()`；熔断后重启状态丢失即违反�?*修复模式**：熔断分支与停止分支执行相同�?`_save_progress(); _record_state(); _notify_downstream()`（对称）vs 熔断分支�?`break`（不对称，状态丢失）�?*配置参数**：`coding_standards.circuit_breaker.cleanup_checklist`（默�?`[save_progress, record_state, notify_downstream]`）在 `config.yaml` 管理�?*适用**：所有熔断器逻辑；批量采集循环；定时任务循环�?*不适用**：无状态循环（无需持久化）；单次执行任务�?*历史教训**：v4.28 修复前熔断分�?break 但未保存进度，重启后�?0 开始，已采集数据丢�?

- 🆕v4.28【强制�?*B-REVIEW-133: 状态切换原子性（state transition atomicity�?*
  - 规范引用：STATE-01 状态切换原子�?
  - 多字段状态切换必须同步更新，禁止只更新一个字段导致状态不一致�?*核心机制**：语义关联字段（�?active/minimized/enabled）必须封�?transition 方法同步更新；禁止外部直接赋值单个字段�?*判断信号**：grep `\.\w+ = True` / `\.\w+ = False` 检查是否漏更新关联字段；状态字段组合非法（�?active=True + minimized=True）即违反�?*修复模式**：`def activate(self): self.active = True; self.minimized = False; self.enabled = True`（封�?transition）vs `sheet.active = True  # 忘了 sheet.minimized = False`（直接赋值，状态不一致）�?*适用**：所有多字段状态切换；UI 状态管理；业务对象状态机�?*不适用**：独立字段（无关联）；单字段状态�?*历史教训**：v4.28 修复�?`sheet.active = True` �?`sheet.minimized` 仍为 True，UI 显示异常

- 🆕v4.28【强制�?*B-REVIEW-134: 多源失效判定一致性（multi-source failure consistency�?*
  - 规范引用：CONSISTENCY-01 多源失效判定一致�?
  - 多个组件判定同一状态必须使用一致的标准，禁止健康检查器用本地存在性、worker �?RGV587_ERROR 导致判定不一致�?*核心机制**：失效判定函数必须统一（如 `is_cookie_valid(cookie) -> bool`），所有组件引用同一函数；禁止各组件自行实现判定逻辑�?*判断信号**：grep `os.path.exists.*cookie` / `RGV587_ERROR` 检查是否有多个判定标准；同一状态在不同组件返回不同结果即违反�?*修复模式**：统一失效判定函数 `is_cookie_invalid(reason) -> bool`（一致）vs 健康检查器用本地存在性、worker �?RGV587_ERROR（不一致）�?*适用**：所有跨组件状态判定；健康检查；故障检测�?*不适用**：组件内部私有状态；不同语义的状态�?*历史教训**：v4.28 修复前健康检查器认为 cookie 有效（文件存在），worker 认为 cookie 无效（RGV587_ERROR），状态显示矛�?

- 🆕v4.28【强制�?*B-REVIEW-135: 缺失数据回退策略（missing data fallback strategy�?*
  - 规范引用：FALLBACK-01 缺失数据回退策略
  - 主数据源缺失时必须有回退数据源，禁止直接标记无效导致功能不可用�?*核心机制**：主数据源（�?JSON 文件）缺失时从备用数据源（如浏览器内存）回退，并写回主数据源；与 B-REVIEW-BROWSER-FALLBACK-SYNC 配合（v4.5 浏览器内存兜底同步，本检查关注回退策略完整性）�?*判断信号**：grep `if not.*json.*invalid` 检查是否有回退；主数据源缺失直接标记无效即违反�?*修复模式**：JSON 缺失时从浏览器内存回退 + 写回 JSON（正确）vs JSON 缺失 cookie 时直接标记无效（错误，功能不可用）�?*适用**：所有多数据源场景；cookie 管理；配置加载�?*不适用**：单数据源；关键安全数据（缺失即失效）�?*历史教训**：v4.28 修复�?JSON 文件被误删，cookie 直接标记无效，用户需重新登录；回退到浏览器内存 + 写回 JSON 后无需重新登录

- 🆕v4.28【强制�?*B-REVIEW-136: 多源状态同步标记机制（multi-source sync marker�?*
  - 规范引用：SYNC-01 多源状态同步标记机�?
  - 写入�?消费方必须有 marker 机制，禁�?auto_sync=false 时不检�?pending markers 导致状态丢失�?*核心机制**：写入方写入数据后设�?pending marker 文件，消费方启动时必须检�?marker 目录并同步；auto_sync=false 仅控制自动同步，不控制启动时检查�?*判断信号**：grep `auto_sync.*False` 检查是否漏检�?marker；启动后状态未同步即违反�?*修复模式**：启动时检�?pending markers 并同步（正确）vs auto_sync=false 时不检�?pending markers（错误，状态丢失）�?*配置参数**：`coding_standards.state_sync.pending_marker_dir`（默�?`data/markers`）、`coding_standards.state_sync.check_on_startup`（默�?`true`）在 `config.yaml` 管理�?*适用**：所有多进程状态同步；跨组件数据传递；配置变更通知�?*不适用**：单进程应用；实时同步场景（无需 marker）�?*历史教训**：v4.28 修复�?auto_sync=false 时启动不检�?marker，用户配置变更未生效

- 🆕v4.28【强制�?*B-REVIEW-137: 异步竞态防护（async race condition protection�?*
  - 规范引用：RACE-01 异步竞态防�?
  - 异步请求完成时必须对比请�?ID，禁止旧请求响应覆盖新请求状态�?*核心机制**：用 useRef（前端）/ dict[request_id]（后端）维护最新请�?ID，响应回来时对比 ID，ID 不匹配则丢弃响应；与 B-REVIEW-CONCURRENT-STATE-LOCK 配合（v4.9 并发共享状态锁，本检查关注请�?ID 对比）�?*判断信号**：grep `async.*await.*update` 检查是否有请求 ID 对比；快速切换后状态显示旧数据即违反�?*修复模式**：useRef 维护最新请�?ID + 响应回来时对比（正确）vs 异步请求完成直接更新状态（错误，旧响应覆盖新状态）�?*配置参数**：`coding_standards.race.check_request_id`（默�?`true`）在 `config.yaml` 管理�?*适用**：所有异步请求场景；快速切�?UI；搜索建议�?*不适用**：单次请求；同步请求；幂等请求�?*历史教训**：v4.28 修复前用户快速切换任务，旧任务响应后覆盖新任务状态，显示错误数据

- 🆕v4.28【强制�?*B-REVIEW-138: 参数传递链完整性（parameter chain integrity�?*
  - 规范引用：PARAM-CHAIN-01 参数传递链完整�?
  - 配置项必须在每一层都读取并传递，禁止中间层漏传参数导致末端拿不到配置�?*核心机制**：config.yaml �?AppConfig �?API �?业务逻辑 �?外部调用全链路传递；新增配置项时必须同步更新所有中间层签名；与 B-REVIEW-PARAM-PASS-THROUGH 配合（v4.4 参数透传链路完整性，本检查关注全链路完整性）�?*判断信号**：grep 配置项名称检查每一层是否读取；新增配置项后末端拿不到值即违反�?*修复模式**：config.yaml �?AppConfig �?API �?业务逻辑 �?外部调用全链路传递（正确）vs build_search_url 缺少 sort/region 参数（错误，末端拿不到）�?*配置参数**：`coding_standards.param_chain.required_fields`（默�?`[sort_type, region, fail_pause_threshold]`）在 `config.yaml` 管理�?*适用**：所有配置项；新增配置项；多层级架构�?*不适用**：单层应用；动态配置（运行时获取）�?*历史教训**：v4.28 修复�?`build_search_url` 缺少 sort/region 参数，搜索结果排序错�?

- 🆕v4.28【强制�?*B-REVIEW-139: 业务关键词配置化（business keyword configuration�?*
  - 规范引用：KEYWORD-01 业务关键词配置化
  - 业务关键词必须集中定义并配置化，禁止分散硬编码导致维护困难�?*核心机制**：关键词集中定义为模块级常量（如 `SOLD_TEXT_KEYWORDS: tuple[str, ...] = ('卖掉�?, '已售', ...)`)，并�?config.yaml 暴露可配置列表；�?B-REVIEW-EXTERNAL-TEXT-PATTERN-CENTRALIZE 配合（v4.19 外部系统文本特征集中管理，本检查关注配置化）�?*判断信号**：grep `'卖掉�?` / `'宝贝不存�?` 检查是否分散硬编码；同一关键词在多处出现即违反�?*修复模式**：集中定�?`SOLD_TEXT_KEYWORDS` 常量 + config.yaml 配置化列表（正确）vs 分散硬编�?'卖掉�?�?宝贝不存�?（错误，维护困难）�?*配置参数**：`coding_standards.keywords.sold`（默�?`['卖掉�?, '已售', '已售�?, '宝贝不存�?, '宝贝走丢�?, '该宝贝不存在', '商品不存�?, '已删�?, '已被删除']`）、`coding_standards.keywords.deleted`（默�?`['宝贝不存�?, '宝贝走丢�?, '该宝贝不存在', '商品不存�?, '已删�?, '已被删除']`）在 `config.yaml` 管理�?*适用**：所有业务关键词；外部系统文本特征；状态判断关键词�?*不适用**：一次性字符串；调试日志文本�?*历史教训**：v4.28 修复�?'卖掉�? 关键词在 5 个文件硬编码，新增关键词需�?5 �?

- 🆕v4.28【强制�?*B-REVIEW-140: 开关持久化（switch persistence�?*
  - 规范引用：PERSIST-01 开关持久化
  - 业务开关必须持久化�?DB 字段�?localStorage，禁止仅内存 useState 导致刷新后丢失�?*核心机制**：业务开关（如自动采�?通知静默）必须持久化�?DB 字段�?localStorage；与 B-REVIEW-CACHE-INVALIDATION 配合（v4.15 缓存失效，本检查关注开关持久化）�?*判断信号**：grep `useState.*True` 检查业务开关是否持久化；刷新后开关状态丢失即违反�?*修复模式**：业务开关持久化�?DB 字段�?localStorage（正确）vs 业务开关仅内存 useState（错误，刷新后丢失）�?*配置参数**：`coding_standards.persist.business_switch_must_persist`（默�?`true`）在 `config.yaml` 管理�?*适用**：所有业务开关；用户偏好设置；功能开关�?*不适用**：临�?UI 状态（�?loading）；会话级状态（如当前选中项）�?*历史教训**：v4.28 修复前自动采集开关仅内存 useState，刷新后丢失，用户需重新开�?

- 🆕v4.28【强制�?*B-REVIEW-141: 凭证多存储同步（credential multi-store sync�?*
  - 规范引用：CREDENTIAL-01 凭证多存储同�?
  - yaml/keyring 凭证必须同步，禁�?yaml 凭证不同步到 keyring 导致渠道静默跳过�?*核心机制**：启动时 yaml �?keyring 同步，确保两个存储一致；�?B-REVIEW-CREDENTIAL-SYNC-BRIDGE 配合（v4.21 凭证同步桥接规范，本检查关注启动时同步）�?*判断信号**：grep `keyring.*get` 检查是�?fallback �?yaml；凭证缺失导致渠道静默跳过即违反�?*修复模式**：启动时 yaml �?keyring 同步（正确）vs yaml 凭证不同步到 keyring，渠道静默跳过（错误）�?*配置参数**：`coding_standards.credential_stores`（默�?`[yaml, keyring]`）在 `config.yaml` 管理�?*适用**：所有凭证管理；多存储后端；敏感信息同步�?*不适用**：单一存储；明文配置（无敏感信息）�?*历史教训**：v4.28 修复�?yaml 凭证未同步到 keyring，通知渠道静默跳过，用户未收到通知

- 🆕v4.28【强制�?*B-REVIEW-142: 属性调用一致性（property naming consistency�?*
  - 规范引用：NAMING-01 属性调用一致�?
  - 属性大小写必须与定义一致，禁止 `self._Session()` 但实际定义是 `_session` 导致 AttributeError�?*核心机制**：从类定义复制粘贴属性名，禁止手写；IDE 自动补全必须基于定义而非记忆；与 B-REVIEW-NO-HARDCODED-PROPS 配合（v4.2 硬编码属性，本检查关注命名一致性）�?*判断信号**：grep `AttributeError.*has no attribute` 检查命名错误；属性大小写与定义不符即违反�?*修复模式**：从类定义复制粘贴属性名（正确）vs `self._Session()  # 实际定义�?_session`（错误，AttributeError）�?*适用**：所有属性访问；方法调用；类成员引用�?*不适用**：动态属性（getattr/setattr）；第三方库属性�?*历史教训**：v4.28 修复�?`self._Session()` 但实际定义是 `_session`，运行时 AttributeError

- 🆕v4.28【强制�?*B-REVIEW-143: API 契约一致性（API contract consistency�?*
  - 规范引用：CONTRACT-01 API 契约一致�?
  - response_model 字段名必须与前端 TS interface 完全一致，禁止后端返回 `total` 前端期望 `total_for_type` 导致字段未定义�?*核心机制**：response_model 字段名与 TS interface 字段名必须完全一致（含大小写/下划�?驼峰）；新增字段时必须同步更新前后端�?*判断信号**：grep response_model 字段�?+ 前端 TS interface 检查一致性；前端 `undefined` 字段即违反�?*修复模式**：response_model 字段名与 TS interface 完全一致（正确）vs 后端返回 `total`，前端期�?`total_for_type`（错误，前端 undefined）�?*配置参数**：`coding_standards.contract.check_ts_interface_match`（默�?`true`）在 `config.yaml` 管理�?*适用**：所�?API 响应；前后端数据交换；DTO 设计�?*不适用**：内�?API（无前端消费）；遗留 API（无法修改）�?*历史教训**：v4.28 修复前后端返�?`total`，前端期�?`total_for_type`，统计页面显�?undefined

- 🆕v4.28【强制�?*B-REVIEW-144: 命名语义清晰性（naming semantics clarity�?*
  - 规范引用：SEMANTICS-01 命名语义清晰�?
  - 字段名必须准确反映业务语义，禁止 `search_interval` 实际是操作延迟导致理解错误�?*核心机制**：字段名必须与业务语义一致，禁止用相似但不准确的名称；命名应反映"是什�?而非"怎么�?�?*判断信号**：grep 字段�?+ 业务逻辑检查语义一致性；字段名与实际含义不符即违反�?*修复模式**：`operation_delay  # 准确反映语义`（正确）vs `search_interval  # 实际是操作延迟`（错误，理解偏差）�?*适用**：所有字段命名；变量命名；函数命名�?*不适用**：遗留命名（兼容性考虑）；第三方库命名�?*历史教训**：v4.28 修复�?`search_interval` 实际是操作延迟，开发者误以为是搜索间隔，配置错误

- 🆕v4.28【强制�?*B-REVIEW-145: 重复逻辑抽取（duplicate logic extraction�?*
  - 规范引用：DRY-01 重复逻辑抽取
  - 重复代码必须抽取为公共函数，禁止在多个文件中复制粘贴相同逻辑�?*核心机制**：跨 �? 文件出现相同逻辑（≥3 行）必须抽取为公共函数；�?B-REVIEW-SHARED-UTIL-CENTRALIZATION 配合（v4.23 共享工具函数规范，本检查关注重复检测）；与 B-REVIEW-S1192 配合（重复字符串字面量）�?*判断信号**：grep 相同代码片段检查重复；同一逻辑在多处出现即违反�?*修复模式**：抽�?`_is_vision_capable()` 公共函数（正确）vs 视觉能力检测逻辑�?api_ai.py �?api_ai_deep.py 重复（错误）�?*配置参数**：`coding_standards.dry.threshold_lines`（默�?`3`）、`coding_standards.dry.threshold_occurrences`（默�?`2`）在 `config.yaml` 管理�?*适用**：所有重复代码；跨文件相同逻辑；相似业务流程�?*不适用**：一次性代码；测试用例（允许重�?setup）；平台特定代码�?*历史教训**：v4.28 修复前视觉能力检测逻辑�?api_ai.py �?api_ai_deep.py 重复，修改时漏改一处导致行为不一�?

- 🆕v4.28【强制�?*B-REVIEW-146: 跨进程编码一致性（cross-process encoding consistency�?*
  - 规范引用：ENCODING-01 跨进程编码一致�?
  - 跨进程通信必须显式设置 UTF-8，禁�?PowerShell 默认 cp936 导致中文�?`?`�?*核心机制**：跨进程通信（HTTP/管道/文件）必须显式设�?`Content-Type: application/json; charset=utf-8`；PowerShell 脚本必须设置 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`�?*判断信号**：grep `Content-Type.*json` 检查是否含 charset；中文变 `?` 即违反�?*修复模式**：显式设�?`Content-Type: application/json; charset=utf-8`（正确）vs PowerShell 脚本默认 cp936，中文变 ?（错误）�?*配置参数**：`coding_standards.encoding.default`（默�?`utf-8`）在 `config.yaml` 管理�?*适用**：所有跨进程通信；HTTP 响应；子进程调用�?*不适用**：进程内通信；纯 ASCII 内容�?*历史教训**：v4.28 修复�?PowerShell 脚本默认 cp936，中文通知内容�?`?`，用户无法阅�?

- 🆕v4.28【强制�?*B-REVIEW-147: dataclass 字段显式声明（dataclass explicit field declaration�?*
  - 规范引用：DATACLASS-01 dataclass 字段显式声明
  - dataclass 必须显式声明所有字段，禁止 `getattr(self, 'field', default)` 兜底未声明字段�?*核心机制**：dataclass 必须显式声明所有字段（含默认值），未声明字段不能�?getattr 兜底；与 B-REVIEW-CONCURRENT-STATE-LOCK 配合（v4.9 并发共享状态锁，本检查关�?dataclass 字段完整性）�?*判断信号**：grep `getattr\(self,` 检查是否兜底未声明字段；`getattr(self, 'consecutive_errors', 0)` 即违反�?*修复模式**：dataclass 显式声明 `consecutive_errors: int = 0`（正确）vs `getattr(self, 'consecutive_errors', 0)  # 字段未声明`（错误，绕过类型检查）�?*配置参数**：`coding_standards.dataclass.disallow_getattr_fallback`（默�?`true`）在 `config.yaml` 管理�?*适用**：所�?dataclass；typeddict；pydantic 模型�?*不适用**：动态属性（�?ORM 模型）；第三方库类�?*历史教训**：v4.28 修复�?`getattr(self, 'consecutive_errors', 0)` 兜底未声明字段，类型检查器无法检测，运行时字段类型错�?

- 🆕v4.28【强制�?*B-REVIEW-148: 启动钩子完整性（startup hook completeness�?*
  - 规范引用：STARTUP-01 启动钩子完整�?
  - 启动钩子必须覆盖所有必要组件，禁止 `_on_startup` 缺少反爬会话管理启动导致功能不可用�?*核心机制**：启动钩子必须用清单核对（如 `[scheduler, session_manager, migration, cookie_sync, embedding]`）；�?B-REVIEW-STARTUP-HOOK-COMPLETENESS 配合（v4.22 启动钩子完整性，本检查关注清单核对）�?*判断信号**：grep `_on_startup` 检查是否启动所有必要组件；启动后功能不可用即违反�?*修复模式**：清单核�?`[scheduler, session_manager, migration, cookie_sync, embedding]`（正确）vs `_on_startup` 缺少反爬会话管理启动（错误，反爬功能不可用）�?*配置参数**：`coding_standards.startup.components`（默�?`[scheduler, session_manager, migration, cookie_sync, embedding]`）在 `config.yaml` 管理�?*适用**：所有启动钩子；服务初始化；组件依赖管理�?*不适用**：按需启动组件；延迟加载组件�?*历史教训**：v4.28 修复�?`_on_startup` 缺少反爬会话管理启动，反爬功能运行时报错"会话未初始化"

- 🆕v4.28【强制�?*B-REVIEW-149: 测试 Mock 类型匹配（test mock type matching�?*
  - 规范引用：MOCK-01 测试 Mock 类型匹配
  - AsyncMock/MagicMock 必须�?async/sync 函数一致，禁止同步函数�?AsyncMock、`assert_awaited` 用于 sync�?*核心机制**：异步函数用 `AsyncMock` + `assert_awaited`，同步函数用 `MagicMock` + `assert_called`；与 B-REVIEW-TEST-MOCK-SYNC 配合（v4.27 测试 mock 同步，本检查关�?Mock 类型匹配）�?*判断信号**：grep `AsyncMock` 检查对应函数是�?async；`AssertionError: coroutines not awaited` 即违反�?*修复模式**：异步用 `AsyncMock + assert_awaited`，同步用 `MagicMock + assert_called`（正确）vs 同步函数�?AsyncMock，assert_awaited 用于 sync（错误，类型不匹配）�?*配置参数**：`coding_standards.mock.async_check_enabled`（默�?`true`）在 `config.yaml` 管理�?*适用**：所有测�?mock；异步函数测试；同步函数测试�?*不适用**：mock 对象（非函数）；属�?mock�?*历史教训**：v4.28 修复前同步函数用 AsyncMock，`assert_awaited` 失败，测试报错但实际功能正常

- 🆕v4.28【强制�?*B-REVIEW-150: Cookie 完整性管理（cookie integrity management�?*
  - 规范引用：COOKIE-01 Cookie 完整性管�?
  - 登录后必须验证关�?cookie 齐全，禁止登录后未验�?'unb' cookie 导致后续请求失败�?*核心机制**：维护必�?cookie 清单（如 `[unb, _m_h5_tk, cookie2, t, _tb_token_]`），登录后校验清单完整性，缺失则报错；`import_full=true` 时必须导入完�?cookie 集而非子集；与 B-REVIEW-COOKIE-CHECK 配合（v4.1 Cookie 检查全面性，本检查关注登录后校验）�?*判断信号**：grep `login.*success` 后检查是否校�?cookie 清单；登录后请求失败即违反�?*修复模式**：维护必�?cookie 清单 + 登录后校�?+ `import_full=true`（正确）vs 登录后未验证 'unb' cookie，导致后续请求失败（错误）�?*配置参数**：`coding_standards.cookie.required_cookies`（默�?`[unb, _m_h5_tk, cookie2, t, _tb_token_]`）、`coding_standards.cookie.import_full`（默�?`true`）在 `config.yaml` 管理�?*适用**：所有登录流程；cookie 导入；会话管理�?*不适用**：匿名访问；公开 API�?*历史教训**：v4.28 修复前登录后未验�?'unb' cookie，后续请求失败，用户误以为登录成功但功能不可�?

---

### 30. 数据契约与时序（meta-rules #25-30 落地）🆕v4.29

> 本维度整�?`xianyu-hunter-dev` v4.30.0 �?meta-rules #25-30 后端侧审查要点，新增 6 �?B-REVIEW 检查点（B-REVIEW-151~156）。所有检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明。前端对应规范为 `xianyu-frontend-code-review` v4.34.0 �?F-REVIEW-110~115�?

- 🆕v4.29【强制�?*B-REVIEW-151: 批量断路器四要素（batch circuit breaker 4 elements�?*
  - 维度�?1 数据契约与时�?
  - 严重等级：error
  - 规范引用：meta-rule #25 批量处理四要�?
  - **检查点**：批量处理触发熔断时必须满足四要素—�?1) 失败计数 + 滑动窗口双条件（`failure_threshold` + `failure_window_sec`）�?2) 进度持久化（`save_progress()`，cursor/completed_ids/remaining_ids 三键齐全）�?3) 续传入口（启动时检�?pending_marker）�?4) 日志对称（`log_phrasing.paused/stopped/failed` 三套文案与动作一致）
  - **判断信号**�?
    - `grep "consecutive failure" <file>` 出现但同函数内无 `save_progress()` �?视为**必修 P0 缺陷**
    - `grep "break" <file>` 后紧�?`mark.*skipped` 但无 `save_progress` �?视为违规
    - `grep "paused" <file>` 但实�?`return`/`break` 跳出循环 �?视为日志语义不一�?
  - **配置参数**：`coding_standards.batch_circuit_breaker.failure_threshold`（默�?`3`）、`coding_standards.batch_circuit_breaker.failure_window_sec`（默�?`3600`）、`coding_standards.batch_circuit_breaker.log_phrasing`（`{paused/stopped/failed}` 三套文案）、`coding_standards.batch_circuit_breaker.mark_remaining_as`（默�?`pending`）、`coding_standards.batch_circuit_breaker.persist_keys`（默�?`[cursor, completed_ids, remaining_ids]`）在 `config.yaml` 管理
  - **适用**：批量采集、批量导入、批量上报、长任务重试
  - **不适用**：单�?API 调用、≤3 �?item 的小批量操作、性能 hot path（持久化开销不可接受�?
  - **历史教训**：`batch_refresh_scheduler.py` �?BatchRefresh#95 连续失败 3 次后 `break` 跳出循环，将剩余商品标记�?`skipped`，但**未调�?`_save_progress()`**。结果：(1) 下次启动无法加载 `remaining_ids` 触发续传�?2) 剩余商品被永久跳过且日志无任何持久化记录

- 🆕v4.29【强制�?*B-REVIEW-152: 关键路径异常保留完整 traceback（critical path exception log�?*
  - 维度�?1 数据契约与时�?
  - 严重等级：error
  - 规范引用：meta-rule #26 关键路径异常保留完整 traceback
  - **检查点**：`_on_startup` / `run_migrations` / `_init_*` / `_on_close` / `_shutdown` / `_register_signal_handlers` 外层 except **必须**使用 `logger.exception()` 输出完整 traceback�?*禁止** `logger.warning(f"...{e}")` 丢堆�?
  - **判断信号**�?
    - `grep "except Exception" <file>` 关键路径�?`logger.exception()` �?视为违规
    - `grep "logger.warning.*f\".*{e}\"\|logger.error.*f\".*{e}\"" <file>` 在关键路�?�?视为违规
  - **配置参数**：`coding_standards.critical_path.patterns`（关键路径函数名模式列表，如 `["_on_startup", "run_migrations", "_init_db"]`）、`coding_standards.critical_path.require_logger_exception`（默�?`true`）、`coding_standards.critical_path.forbidden_log_patterns`（禁用的丢堆栈日志模式正则）�?`config.yaml` 管理
  - **适用**：启动钩子、迁移函数、初始化函数、关闭钩子、信号处理器注册
  - **不适用**：常规业务函数（�?`logger.error(f"...{e}")` 即可）、测试代码、性能 hot path
  - **历史教训**：`run_migrations()` 用外�?`try/except Exception as e: logger.warning(f"迁移失败: {e}")` �?后续 5 个迁移块 C-01~C-05 全部跳过（异常被吞）�?启动时表缺列触发 `OperationalError: no such column`

- 🆕v4.29【强制�?*B-REVIEW-153: datetime 统一时区策略（datetime timezone strategy�?*
  - 维度�?1 数据契约与时�?
  - 严重等级：warning
  - 规范引用：meta-rule #27 datetime 统一时区策略
  - **检查点**：涉及跨时区/跨进�?跨服务的 `datetime` 算术与序列化必须满足—�?1) 存储一�?UTC（`datetime.now(timezone.utc)`），(2) 算术前显�?unify tzinfo（与 DB naive 算术�?`_utcnow().replace(tzinfo=None)`），(3) 序列化时显式�?tzinfo（ISO 8601 with tz�?
  - **判断信号**�?
    - `grep "datetime.now()" <file>` �?`tzinfo` 参数 �?视为违规
    - `grep "datetime.utcnow()" <file>` �?视为**反模�?*（Python 3.12+ 弃用�?
    - `grep "\.isoformat()\[:19\]" <file>` �?视为序列化不规范
  - **配置参数**：`coding_standards.datetime.storage_timezone`（默�?`UTC`）、`coding_standards.datetime.preferred_now`（默�?`datetime.now(timezone.utc)`）、`coding_standards.datetime.forbidden_now_patterns`（禁用的 now 模式正则）、`coding_standards.datetime.serialization_format`（默�?`iso8601_with_tz`）、`coding_standards.datetime.naive_unify_helper`（默�?`_utcnow().replace(tzinfo=None)`）在 `config.yaml` 管理
  - **适用**：所�?`created_at` / `updated_at` / `expires_at` 字段的算术运算、跨服务时间比较、ISO 序列�?
  - **不适用**：纯展示（前端用 `dayjs` 解析）、同函数内的 local variable 计算、纯日期不含时间
  - **历史教训**：`repo_chatbot.py:478` �?`TypeError: can't subtract offset-naive and offset-aware datetimes`：`datetime.utcnow() - row.created_at`，其�?`row.created_at` �?SQLAlchemy �?SQLite 读出�?naive datetime。修复：�?`_utcnow().replace(tzinfo=None) - row.created_at` 统一�?naive

- 🆕v4.29【强制�?*B-REVIEW-154: 跨进程状态同步六步法（cross-process state sync 6 steps�?*
  - 维度�?1 数据契约与时�?
  - 严重等级：warning
  - 规范引用：meta-rule #28 跨进程状态同步六步法
  - **检查点**：需要多源写入的状态（�?Cookie 多层管理）必须满足六步—�?1) 写端：业务变更后写状�?+ �?`pending_marker`�?2) 同步端：独立调度器扫�?marker�?3) 读端：仅读最新状态�?4) 启动时：检查未处理 marker 强制触发同步�?5) 异常时：保留 marker 不删除�?6) 配置：同步开�?间隔/批次大小均通过配置
  - **判断信号**�?
    - `grep "write_marker" <file>` 但无 `scan_marker` 同步�?�?视为违规（marker 永不被消费）
    - 启动函数（匹�?`critical_path_patterns`）无 `process_pending_markers` 但有 marker 写入�?�?视为违规（重启时积压 marker 丢失�?
    - `grep "os.unlink.*marker" <file>` �?try 块内但无异常分支 �?视为违规（失败时 marker 丢失�?
  - **配置参数**：`coding_standards.state_sync_marker.marker_dir`（默�?`data/markers`）、`coding_standards.state_sync_marker.startup_check_required`（默�?`true`）、`coding_standards.state_sync_marker.scan_interval_sec`（默�?`60`）、`coding_standards.state_sync_marker.max_retry_count`（默�?`5`）、`coding_standards.state_sync_marker.marker_format`（默�?`{category}_{user_id}_{timestamp}.json`）在 `config.yaml` 管理
  - **适用**：Cookie 多层同步、配置变更广播、跨 Tab 状态共享、用户偏好同�?
  - **不适用**：单写单读的临时状态、纯 UI 状态、性能 hot path、无跨进程边界的纯函数计�?
  - **历史教训**：Cookie 自愈系统涉及 3 个写端（`auth_helper.py` / `browser_login.py` / 外部 API 调用）与 1 个同步器（`cookie_sync_scheduler.py`）。修复前：写端无 marker �?同步器无法被触发；启动时不检�?marker �?重启时积�?marker 永久丢失。修复：补全 6 步后，Cookie 自愈成功率从 65% 提升�?92%

- 🆕v4.29【强制�?*B-REVIEW-155: 前后端错误码契约（frontend-backend error code contract�?*
  - 维度�?1 数据契约与时�?
  - 严重等级：warning
  - 规范引用：meta-rule #29 前端错误�?error_code 分支
  - **检查点**：`raise HTTPException` 必须包含 `error_code` 字段（来�?`reason_enum`），错误响应统一结构�?`{ "error_code": "<reason>", "user_message": "<人类可读>", "detail": "<技术细�?" }`。`reason_enum` 包含 `token_expired/anti_crawler/page_unavailable/rate_limited/login_expired/session_invalid/permission_denied/validation_error/internal_error/service_unavailable`
  - **判断信号**�?
    - `grep "raise HTTPException" <file>` �?`error_code` 字段 �?视为违规
    - 后端响应�?`error_code` 字段 �?视为**必修 P0 缺陷**（前端无法分支）
  - **配置参数**：`coding_standards.error_code.reason_enum`�?0 �?reason 值列表）、`coding_standards.error_code.response_schema`（字段定义）、`coding_standards.error_code.require_in_http_exception`（默�?`true`）在 `config.yaml` 管理
  - **适用**：所有后�?4xx/5xx 响应（除 401/440/441 走认证拦截器外）
  - **不适用**：开发环�?`console.error`、本地输入校验、HTTP 5xx 网络层错�?
  - **历史教训**：多个前端组件用 `if (err.message.includes('expired'))` 判断 Cookie 过期 �?后端文案从「登录已过期」改为「会话已失效」后，所有页面判断失效，统一显示「未知错误」。修复：建立前后�?`error_code` 契约，前�?`switch` 分支

- 🆕v4.29【强制�?*B-REVIEW-156: 业务关键字常量集中管理（business keyword centralization�?*
  - 维度�?1 数据契约与时�?
  - 严重等级：warning
  - 规范引用：meta-rule #30 业务关键字常量集中管�?
  - **检查点**：业务关键字（已售、已删除、宝贝不存在等需正则匹配/includes 判断的字符串）必须集中到 `config.yaml#business_keywords` 或专用常量文件，业务代码中禁止硬编码关键字字符串
  - **判断信号**�?
    - `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售�?['\"]" src/xianyu_hunter/` �?视为硬编码（应从 config 读）
    - 业务代码 `grep "if.*['\"].*['\"].*in.*text" <file>` �?视为可能硬编�?
  - **配置参数**：`coding_standards.business_keyword.sold`（已售关键字列表）、`coding_standards.business_keyword.deleted`（已删除关键字列表）、`coding_standards.business_keyword.frontend_constants_file`（前端常量文件路径）、`coding_standards.business_keyword.consistency_test`（前后端一致性测试路径）�?`config.yaml` 管理
  - **适用**：商品状态识别（已售/已删/在售）、错误提示文案匹配、风控标签识别、敏感词过滤
  - **不适用**：日�?异常消息中的自由文本、配置文件中的连接信息、测试用例中�?mock 数据
  - **历史教训**：Cookie 自愈系统�?`sold` 关键字集合在 3 处独立维护，新增「宝贝走丢了」时只更新了 2 处，�?3 处漏更新导致「已售商品」被误判为「在售」继续抢单。修复：抽取�?`config.yaml#business_keywords.sold` 集中管理

---

### 31. 业务关键字常量集中管理与跨端契约对齐 🆕v4.31

> 本维度整�?v4.29 step 129-133 的后端侧审查要点，新�?5 �?B-REVIEW 检查点，对�?`xianyu-hunter-dev` v4.29.0 �?step 129-133。所有检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。前端对应规范为 `xianyu-frontend-code-review` v4.31.0 的维�?27（业务关键字常量集中管理与字段名大小写敏感）�?

- 🆕v4.31【强制�?*B-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION：业务关键字常量集中管理**
  - 维度�?1 业务关键字常量集中管理与跨端契约对齐
  - 严重等级：error
  - 规范引用：KEYWORD-CENTRAL-01 业务关键字常量集中管�?
  - **检查点**：外部平台文本特征（已售/已下�?区域/状态文案）必须集中到单一模块�?`*_TEXT_KEYWORDS` 常量，业务代码必须通过统一访问函数（如 `check_text_sold`）调用，**禁止**在各业务文件内散落中文字面量
  - **判断信号**�?
    - `grep "已售\|已下架\|卖掉�? src/xianyu_hunter/` 中文字面量散落多个文�?�?视为违规
    - `grep "in text" src/xianyu_hunter/` 出现内联关键字判断而非调用统一函数 �?视为可疑
    - 多个文件维护同一业务概念的关键字列表 �?视为违规
  - **配置参数**：`business_keyword_centralization.keyword_categories`（关键字分类清单，如 `["sold", "ordered", "region"]`）、`business_keyword_centralization.centralized_module`（集中模块路径，�?`collector_utils.py`）、`business_keyword_centralization.unified_function_pattern`（统一访问函数命名模式，如 `check_text_*`）、`business_keyword_centralization.forbidden_inline_patterns`（禁止的内联判断模式，如 `any\(kw in text for kw in`）在 `config.yaml` �?`business_keyword_centralization` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` step 129
  - **适用**：外部平台文本特征识别（已售/已下�?区域/状态文案）、第三方系统响应文案解析、任何需要全链路同步更新的关键字常量
  - **不适用**：框架内部固定文案（�?antd 默认 placeholder）、单次使用的字符串字面量（无复用需求）、协议固定值（�?HTTP method�?
  - **历史教训**：闲鱼前端将「已售」文案改为「卖掉了」，�?`SOLD_TEXT_KEYWORDS` 只在 `_detail.py` 部分文件中维护，`_parser.py` �?`buyer.py` 未同步更新，导致商品 1058031608014 已售但状态未采集。修复：抽取统一 `SOLD_TEXT_KEYWORDS` 常量�?`check_text_sold()` 函数�?`collector_utils.py`，三个文件统一调用

- 🆕v4.31【强制�?*B-REVIEW-EVENT-TYPE-EXACT-MATCH：事件类型过滤精确匹�?*
  - 维度�?1 业务关键字常量集中管理与跨端契约对齐
  - 严重等级：error
  - 规范引用：EVENT-MATCH-01 事件类型过滤精确匹配
  - **检查点**：业务查询事件类型时必须�?`==` 精确匹配�?*禁止**�?`startswith` / `endswith` / `in` 做前缀/后缀/子串过滤（统计聚合场景除外）；通知事件与业务事件必须使用不同的 type 前缀或命名空�?
  - **判断信号**�?
    - `grep "startswith\|endswith" src/xianyu_hunter/` 出现在事�?记录过滤逻辑�?�?视为可疑
    - 业务列表混入 `payload=None` 的空记录 �?必然违规
    - 事件 type 命名空间冲突（通知事件与业务事件同前缀，如 `eval.passed` 通知事件�?`eval.scored` 业务事件同前缀）→ 视为违规
  - **配置参数**：`event_type_exact_match.forbidden_prefix_patterns`（禁止的前缀过滤模式，如 `startswith\(['\"]\w+\.`）、`event_type_exact_match.required_match_pattern`（要求的精确匹配模式，如 `==` / `Set.has()` / `switch.*case`）、`event_type_exact_match.allowed_prefix_grouping_scenarios`（允许前缀分组场景白名单，�?`["statistics_aggregation", "log_filtering"]`）、`event_type_exact_match.event_type_categories`（事件类型分类清单，含业务事件与通知事件命名空间）在 `config.yaml` �?`event_type_exact_match` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` step 130
  - **适用**：业务事件查询（评估明细/订单列表/任务列表）、KPI 统计（按事件类型计数）、事件订阅（EventBus 订阅特定事件�?
  - **不适用**：全量事件导出（无需过滤）、日志搜索（模糊匹配是预期行为）、调试查询（临时性，非生产代码）
  - **历史教训**：`NotifierHub` 写入 `type='eval.passed'`、`payload=None` 的事件用�?KPI 统计，但 `api_evaluations.py` �?`startswith('eval.')` 过滤评估明细列表，误包含 227+ 条通知事件，用户看到�?13 条仅基于价格的评估记录」和大量空行。修复：将过滤条件改�?`== 'eval.scored'`，评估明细从 280 条减�?47 条有效记�?

- 🆕v4.31【强制�?*B-REVIEW-FIELD-NAME-CASE-SENSITIVE：前后端字段名大小写敏感检�?*
  - 维度�?1 业务关键字常量集中管理与跨端契约对齐
  - 严重等级：error
  - 规范引用：FIELD-CASE-01 前后端字段名大小写敏感检�?
  - **检查点**：Python 类私有属性命名（`_session` vs `_Session`）和 API 字段名（`total_for_type` vs `totalForType`）必须在赋值和引用处严格大小写一致，API 响应字段名必须前后端严格一致（含大小写、下划线、前后缀�?
  - **判断信号**�?
    - `grep "_[A-Z]" src/xianyu_hunter/` 出现大写开头的私有属�?�?视为可疑（Python 约定为小写）
    - 后端返回字段名与前端 types.ts 字段名不一致（含大小写差异）→ 视为违规
    - 前端�?`as any` / `as unknown as` 绕过字段名检�?�?视为违规
  - **配置参数**：`field_name_case_sensitive.backend_field_naming_style`（后端字段命名风格，默认 `snake_case`）、`field_name_case_sensitive.forbidden_bypass_patterns`（禁止的绕过模式，如 `as\s+any\b` / `as\s+unknown\s+as`）、`field_name_case_sensitive.known_case_sensitive_fields`（已知大小写敏感字段清单，含 `backend` �?`frontend_wrong` 对照）、`field_name_case_sensitive.bidirectional_match_required`（是否要求前后端双向 grep 匹配，默�?`true`）在 `config.yaml` �?`field_name_case_sensitive` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` step 131
  - **适用**：Python 类私有属性（`_xxx` 命名）、API 请求/响应字段名（前后端契约）、DB schema 字段名与 ORM model 字段名对齐、TypeScript interface �?Python Pydantic model 字段对齐
  - **不适用**：框架内置属性（�?`__init__`/`__str__`，由 Python 规范保证）、第三方库字段名（无法控制）
  - **历史教训**：`api_chatbot_config.py` line 343 使用 `self._Session()` 但类中定义的�?`self._session`（小�?s），运行时抛 `AttributeError: 'ChatbotRepository' object has no attribute '_Session'`；`api_task_links.py` 返回 `total` 字段，但前端 `ItemList.tsx` 期望 `total_for_type`，导致前端�? 条」显�?

- 🆕v4.31【强制�?*B-REVIEW-SERVICE-RESTART-VERIFICATION：服务重启验证清�?*
  - 维度�?1 业务关键字常量集中管理与跨端契约对齐
  - 严重等级：warning
  - 规范引用：RESTART-01 服务重启验证清单
  - **检查点**：Python 后端代码修改后必须重启服务（除非启用 `--reload`），重启后必须按清单验证服务状态（端口监听/健康检�?关键数据状�?启动日志无异常）
  - **判断信号**�?
    - 代码 review 中修改了 `.py` 文件但未提供重启命令 �?视为可疑
    - 用户反馈「修复无效」但代码已修�?�?必然未重启服�?
    - 重启后未验证端口监听 �?视为可疑
    - 重启后未查看启动日志确认�?`ImportError`/`OperationalError`/`AttributeError` �?视为可疑
  - **配置参数**：`post_restart.checklist`（重启验证清单，含端口监�?健康检�?数据状�?日志确认）、`post_restart.health_check_endpoints`（健康检查端点清单，�?`/api/about`/`/api/tasks`/`/api/scheduler/status`）、`post_restart.startup_log_keywords`（启动日志关键词，如 `Application startup complete`/`Scheduler started`）、`post_restart.frontend_build_required`（前端是否需要重新构建，默认 `true`）在 `config.yaml` �?`post_restart` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` step 132
  - **适用**：Python 后端代码修改后（任何 .py 文件）、前端代码修改后（需 `npm run build` + 浏览器强制刷新）、数据库迁移�?
  - **不适用**：开发模�?`--reload` 启用（自动热重载）、纯文档修改（无代码变更）、配置文件修改（部分配置支持热加载）
  - **历史教训**：修�?`api_anticrawl.py` 后未重启服务，用户反馈「会话管理仍未自动启动」，实际代码已修复但服务跑的是旧代码；重启后未验证端口监听，导致 uvicorn 启动失败但用户以为服务正常运�?

- 🆕v4.31【强制�?*B-REVIEW-WINDOWS-TERMINAL-ENCODING：Windows 终端编码�?Shell 语法兼容**
  - 维度�?1 业务关键字常量集中管理与跨端契约对齐
  - 严重等级：warning
  - 规范引用：ENCODING-SHELL-01 Windows 终端编码�?Shell 语法兼容
  - **检查点**：Windows PowerShell 脚本必须显式设置 UTF-8 编码，命令拼接必须用 `;` 而非 `&&`，含特殊字符的参数（�?`stash@{0}`）必须加引号，Python 脚本�?Windows 环境必须显式设置 stdout 编码
  - **判断信号**�?
    - `grep "cp936\|gbk" *.ps1` 出现编码硬编�?�?视为可疑
    - `grep "&&" *.ps1` PowerShell 脚本�?`&&` �?视为违规
    - `grep "stash@" *.ps1` 不加引号�?`stash@{N}` �?视为违规
    - 数据库存储中文为 `?` �?编码问题可疑
    - 日志文件中文乱码 �?编码问题可疑
  - **配置参数**：`cross_platform.encoding`（编码设置，默认 `UTF-8`）、`cross_platform.shell_quoting`（shell 参数引用规则，如 `stash@{N}` 必须加引号）、`cross_platform.path_separator`（路径分隔符处理，默�?`pathlib`/`os.path`）、`cross_platform.command_separator`（命令分隔符，PowerShell �?`;`，Linux �?`&&`）在 `config.yaml` �?`cross_platform` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` step 133
  - **适用**：Windows PowerShell 脚本调用 API（含中文 body）、Python 脚本�?Windows 环境输出中文到日志、git 操作（stash/branch 等含特殊字符的参数）、跨平台部署的脚本（Windows + Linux�?
  - **不适用**：Linux/Mac 环境�?shell 脚本（默�?UTF-8）、Docker 容器内脚本（容器内默�?UTF-8）、纯英文内容的脚本（无编码问题）
  - **历史教训**：外部脚本批量调�?`POST /api/chatbot/faq` �?PowerShell 默认 cp936 编码，中�?body 被转换为 `?`，导致数据库存储 3 条乱码记录（id=1/2/3）；`git stash apply stash@{0}` �?PowerShell 中报错「解析为哈希表」，修复：加引号 `'stash@{0}'`；`cd frontend && npm run build` 报错「`&&` 不是有效的语句分隔符」，修复：改�?`;`

---

### 32. 状态恢复与日志规范 🆕v4.30

> 本维度对�?`xianyu-hunter-dev` v4.31.0 meta-rules #31/#32，新�?2 �?B-REVIEW 检查点（B-REVIEW-157~158）。所有检查点强调配置驱动（参数在 `config.yaml` �?`resume_policy` / `log_merge` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。前端对应规范为 `xianyu-frontend-code-review` v4.35.0 �?F-REVIEW-116（状态恢复前置校验前端侧）；前端无降级链日志场景，不新增 LOG-MERGE 对应检查点�?

- 🆕v4.30【强制�?*B-REVIEW-157：RESUME-PRECHECK 状态恢复前置校�?*
  - 维度�?2 状态恢复与日志规范
  - 严重等级：error（P0，无效循环风险）
  - 规范引用：meta-rule #31 状态恢复前置校验（pause→resume 根因消除校验�?
  - **检查点**：具�?pause/resume 语义的组件（任务调度�?登录会话/连接�?断路器）�?resume 操作前必须调�?precheck 函数校验导致 pause �?root_cause 是否已消除，未消除时拒绝恢复并返回结构化响应
  - **检查项**�?
    1. 异常 pause 时必须记�?`root_cause`（含 `reason_code` + 失效层标�?+ 时间戳）持久化到任务/会话状态，而非仅记日志
    2. resume 操作前必须调�?precheck 函数校验 `root_cause` 对应的前置条件是否已恢复（如 Cookie �?valid、连接可达、配额充足）
    3. 校验失败时返回结构化拒绝 `{resume_blocked: true, reason_code, user_hint, retry_after}`，禁止静默失败或无条件放�?
    4. 异常 pause 后设置冷却期（`config.yaml#resume_policy.cooldown_seconds`），期间拒绝 resume，避�?恢复→失效→暂停"无效循环
    5. 冷却期时长、前置校验开关、`reason_code` �?precheck 函数映射表均�?config 读取，禁止硬编码
  - **判断信号**�?
    - `grep "def resume\|def start\|def unpause\|def activate" <file>` �?`precheck`/`_check_prerequisite` 调用 �?视为违规
    - `grep "pause\|paused\|should_pause"` �?`root_cause` 字段赋�?�?视为违规（无法校验根因消除）
    - resume 接口 `grep "return.*True\|return.*ok"` �?`if not precheck` 拒绝分支 �?视为违规（无条件放行�?
    - `grep "cooldown\|cool_down"` 时长为字面量数字而非 config 引用 �?视为硬编�?
  - **配置参数**：`resume_policy.cooldown_seconds`（冷却期时长，默�?300 秒）、`resume_policy.precheck_enabled`（前置校验开关，默认 true）、`resume_policy.reason_to_precheck_map`（reason_code �?precheck 函数映射表，�?`{"cookie_invalid": "_check_cookie_layers_valid", "session_expired": "_check_session_active", "connection_lost": "_check_pool_alive"}`）、`resume_policy.applicable_components`（适用组件清单，如 `["task_scheduler", "login_session", "connection_pool", "circuit_breaker"]`）在 `config.yaml` �?`resume_policy` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.31.0 meta-rules #31
  - **适用**：任务调度器 pause/resume（如搜索任务会话失效暂停）、登录会话失�?恢复（Cookie 层失效后重新登录）、连接池断连/重连、断路器开/闭、限流配额耗尽/恢复
  - **不适用**：用户主�?pause（非异常触发，无 root_cause）、一次性任务（�?resume 语义）、纯函数重试（无状态持久化）、开发调试手�?resume
  - **历史教训**：搜索任�?`t68bc149b` 因闲鱼会话失效（RGV587_ERROR）被自动暂停后，用户/系统�?30 分钟内连�?4 次恢复任务，�?Cookie 未重新登录刷新，每次恢复�?13~22 秒内再次触发会话失效检测并暂停，形�?恢复→失效→暂停"无效循环，浪费浏览器资源并产�?555 条冗�?WARNING。修复：resume 前校�?`cookie_rotator` �?identity/session �?`valid` 状态，失效时拒绝恢复并提示"请先重新登录闲鱼"；异�?pause 后设 5 分钟冷却期（config 可配），彻底消除无效循环

- 🆕v4.30【强制�?*B-REVIEW-158：LOG-MERGE 多阶段降级链日志合并**
  - 维度�?2 状态恢复与日志规范
  - 严重等级：warning（P1，可观测性噪音）
  - 规范引用：meta-rule #32 多阶段降级链日志合并
  - **检查点**：同一逻辑链的多个中间阶段（降�?重试/回退/多策略尝试）日志必须合并�?1 条结构化结果日志（WARNING/ERROR），中间步骤使用 `logger.debug()`，禁止每个中间步骤独立输�?WARNING
  - **检查项**�?
    1. 降级/重试链的中间步骤（如"尝试刷新 token""尝试 DOM 回退"）使�?`logger.debug()`，最终结果使�?`logger.warning()` �?`logger.error()`
    2. 最终结果日志必须含结构�?`extra` 字段：`{stages: [...], final_reason, keyword/context, attempts}`，其�?`stages` 为各中间步骤的简述数�?
    3. 同一逻辑链内 �? 个阶段则必须合并（`config.yaml#log_merge.min_stages_to_merge` 可配），单阶段无需合并
    4. 合并阈值、中间步�?DEBUG 开关、保留的中间步骤白名单均�?config 读取，禁止硬编码
  - **判断信号**�?
    - `grep -c "logger.warning" <file>` 同一函数�?�? 条且属于同一 try/降级�?�?视为违规（应合并�?1 条）
    - `grep "logger.warning.*尝试\|logger.warning.*刷新\|logger.warning.*回退\|logger.warning.*重试" <file>` 多条且无结构化合�?�?视为冗余告警
    - 降级链结果日�?`grep "logger.warning"` �?`extra=` 参数 �?视为不规范（无法聚合分析�?
    - 合并阈值硬编码为字面量数字 �?视为违规（应�?config 读）
  - **配置参数**：`log_merge.min_stages_to_merge`（合并阈值，默认 2，≥该值则必须合并）、`log_merge.intermediate_step_level`（中间步骤日志级别，默认 `debug`）、`log_merge.result_level`（结果日志级别，默认 `warning`）、`log_merge.required_extra_fields`（结果日志必须包含的 extra 字段，如 `["stages", "final_reason", "keyword", "attempts"]`）、`log_merge.whitelist_intermediate_warning`（保留为 WARNING 的中间步骤白名单，默认空）在 `config.yaml` �?`log_merge` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.31.0 meta-rules #32
  - **适用**：降级链（API→DOM→缓存）、重试链（指数退避多轮）、多策略回退（多 selector 候选）、浏览器自动化多策略尝试、批处理多阶段校�?
  - **不适用**：独立的一次性告警（不同业务流程）、用户操作触发的即时反馈、关键路径异常的 `logger.exception()`（需完整堆栈）、不同函�?模块的告�?
  - **历史教训**：搜�?API 会话失效时，`_search.py` 在同一次搜索失败中输出 5 �?WARNING（FAIL_SYS_ILLEGAL_ACCESS �?尝试强制刷新 _m_h5_tk �?刷新失败 �?尝试 DOM 回退 �?DOM 回退超时），单次搜索失效产生 5 条噪音日志，12 小时内累�?555 条冗�?WARNING（占�?WARNING 88%），淹没真正需要关注的告警。修复：中间步骤降为 DEBUG，最终合并为 1 条结构化 WARNING（含 `stages`/`final_reason`/`keyword`），告警量从 628 降至 ~80，可观测性显著提�?

---

### 33. 修复前全链路根因扫描协议 🆕v4.31

> 本维度对�?`xianyu-hunter-dev` v4.32.0 meta-rule #34，新�?1 �?B-REVIEW 检查点（B-REVIEW-160）。所有检查点强调配置驱动（参数在 `config.yaml` �?`root_cause_chain_check` 节点管理，不硬编码）与适用/不适用场景说明。前端对应规范为 `xianyu-frontend-code-review` v4.36.0 �?F-REVIEW-118�?

- 🆕v4.31【强制�?*B-REVIEW-160：ROOT-CAUSE-CHAIN-CHECK 修复前全链路根因扫描协议**
  - 维度�?3 修复前全链路根因扫描协议
  - 严重等级：error（P0，修复漏根因风险�?
  - 规范引用：meta-rule #34 修复前全链路根因扫描协议
  - **检查点**：修复非平凡 bug 前必须先�?�? 个根因覆盖用户层/接口�?数据�?配置�?历史层；PR 描述必须�?�? 根因列表"段；git diff 涉及 �? 个无关文件视为违反最小修改原则；新增逻辑�?unit test 视为 WARNING
  - **检查项**�?
    1. 修复前必须列�?�? 个候选根因，覆盖用户�?接口�?数据�?配置�?历史�?5 个维�?
    2. PR 描述必含"�? 根因列表"�?+ 验证工具 + 最小修改清�?+ 全链路反�?+ 防回归测�?
    3. git diff 涉及 �? 个无关文件视为违反最小修改原则（WARNING�?
    4. 新增逻辑�?unit test 视为 WARNING
    5. 链式检�?5 维度 menu_registry/router/page/api_wrapper/backend_endpoint �?B-REVIEW-159 5 层契约呼�?
  - **判断信号**�?
    - `git diff --name-only | wc -l` �?3 个无关文�?�?视为违规
    - PR 描述 `grep "根因列表\|root cause"` 缺失 �?视为违规
    - 新增函数 `grep "def test_"` 无对应测�?�?视为 WARNING
  - **配置参数**：`root_cause_chain_check.min_root_causes`（最小根因数，默�?3）、`root_cause_chain_check.coverage_layers`（必须覆盖的层，默认 `["user", "api", "data", "config", "history"]`）、`root_cause_chain_check.max_unrelated_files`（最大无关文件数，默�?3）、`root_cause_chain_check.require_unit_test`（新增逻辑是否必须�?unit test，默�?true）在 `config.yaml` �?`root_cause_chain_check` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.32.0 meta-rule #34
  - **适用**：非平凡 bug 修复（≥2 个根因可能）、跨层级问题（前�?后端+DB）、回�?bug（修复过但又复发）、生产事故复�?
  - **不适用**：typo/文案修改（单根因明确）、单测失败修复（根因在测试代码）、配置调整（无代码变更）、首次开发新功能（无 bug 历史�?
  - **历史教训**：通知中心菜单点击无反应问题，初次修复仅改前端 Route，未发现后端 endpoint 也不存在，导致修复后仍无法访问；�?�? 根因列表扫描后发�?5 层契约缺 3 层（router/page/api_wrapper/backend_endpoint），逐层补齐才彻底修�?

---

### 34. 前后端字段契约单一可信�?🆕v4.31

> 本维度对�?`xianyu-hunter-dev` v4.32.0 meta-rule #35，新�?1 �?B-REVIEW 检查点（B-REVIEW-161）。所有检查点强调配置驱动（参数在 `config.yaml` �?`contract_owner_marker` 节点管理，不硬编码）与适用/不适用场景说明。前端对应规范为 `xianyu-frontend-code-review` v4.36.0 �?F-REVIEW-119�?

- 🆕v4.31【强制�?*B-REVIEW-161：CONTRACT-OWNER-MARKER 前后端字段契约单一可信�?*
  - 维度�?4 前后端字段契约单一可信�?
  - 严重等级：error（P0，前后端字段漂移风险�?
  - 规范引用：meta-rule #35 前后端字段契约单一可信�?
  - **检查点**：后�?Pydantic/DB Row 字段 = 权威源；后端 `BaseModel` 字段必须显式标注 `@field_validator` / `Field(..., description=...)` 标明"权威�?角色；后端字段变更必须同步通知前端 + �?`contract_owner_marker` 节点更新 `affected_frontend_types_files` 列表；snake_case 严格透传禁止�?camelCase
  - **检查项**�?
    1. 后端 `BaseModel` 字段必须显式标注 `@field_validator` �?`Field(..., description=...)` 标明"权威�?角色
    2. 后端字段变更必须同步通知前端 + �?`contract_owner_marker` 节点更新 `affected_frontend_types_files` 列表
    3. snake_case 严格透传禁止�?camelCase（命名漂移检测：后端 `xxx_yyy` + 前端 `xxxYyy` = CRITICAL�?
    4. 前端 `types.ts` 字段必须与后�?`BaseModel` 字段一一对齐（含可�?必填/默认值）
    5. 后端字段废弃必须先标 `deprecated` 注释�? 个版本后再删�?
  - **判断信号**�?
    - `grep "class.*BaseModel" <file>` 后检查字段是否含 `Field(..., description=...)` �?缺失视为违规
    - 后端 `xxx_yyy` 字段 vs 前端 `xxxYyy` 字段 �?视为命名漂移（CRITICAL�?
    - `grep "camelCase\|to_camel\|camelize"` 在序列化路径 �?视为违规
  - **配置参数**：`contract_owner_marker.authority_source`（权威源标识，默�?`"backend"`）、`contract_owner_marker.required_marker_fields`（必须标注的字段，如 `["id", "user_id", "created_at", "updated_at"]`）、`contract_owner_marker.affected_frontend_types_files`（受影响前端 types 文件列表）、`contract_owner_marker.naming_drift_patterns`（命名漂移模式库，如 `["snake_case_to_camelCase", "snake_case_to_PascalCase"]`）、`contract_owner_marker.deprecation_grace_versions`（废弃字段保留版本数，默�?1）在 `config.yaml` �?`contract_owner_marker` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.32.0 meta-rule #35
  - **适用**：所有后�?`BaseModel`/DB Row 字段定义、前后端 API 契约接口、跨端字段映射、字段废弃流�?
  - **不适用**：内部数据结构（不向前端暴露）、临时调试字段、测�?mock 数据、纯前端 UI 状态字�?
  - **历史教训**：通知中心前后端字段不对齐，后�?`NotificationRow.read_at` 字段 vs 前端 `Notification.readAt` 字段，导致前端始终读 `undefined`，通知状态永远显�?未读"

---

### 35. 列表聚合与状态联�?🆕v4.34

> 本维度对�?`xianyu-hunter-dev` v4.34.0 meta-rules #38-42，新�?5 �?B-REVIEW 检查点（B-REVIEW-164~168）。同时整�?v4.33 规范治理（B-REVIEW-162/163，meta-rules #36-37）。所有检查点强调配置驱动（参数在 `config.yaml` �?`meta_rules_38_42` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。前端对应规范为 `xianyu-frontend-code-review` v4.38.0 �?F-REVIEW-122~126�?

- 🆕v4.33【强制�?*B-REVIEW-162：SEDIMENTATION-THRESHOLD 规范立项前置计数**
  - 维度�?5 编码规范防御性复�?
  - 严重等级：major（P1，过度规范化风险�?
  - 规范引用：meta-rule #36 规范沉淀门槛（防过度规范化）
  - **检查点**：新�?meta-rule/step/B-REVIEW 必须满足 �? 个相�?bug 门槛，单一 bug 立规范需�?experimental 标签 + 1 季度观察期，安全/数据丢失/付费受损豁免
  - **配置参数**：`meta_rules_governance.sedimentation_threshold`（默�?3）、`meta_rules_governance.sedimentation_time_window_months`（默�?6）、`meta_rules_governance.experimental_observation_quarters`（默�?1）、`meta_rules_governance.sedimentation_exemption_categories`（默�?`["security_vulnerability", "data_loss", "payment_damage"]`）在 `config.yaml` �?`meta_rules_governance` 节点管理
  - **适用**：所有新�?meta-rule/step/B-REVIEW 检查点
  - **不适用**：安全漏�?数据丢失/付费受损豁免类别（无需 �? 次即可立即立规范�?

- 🆕v4.33【建议�?*B-REVIEW-163：DEGRADATION-CLEANUP 规范退化清�?*
  - 维度�?5 编码规范防御性复�?
  - 严重等级：minor（P2，规范膨胀风险�?
  - 规范引用：meta-rule #37 规范退化机制（防规范膨胀�?
  - **检查点**：利用率 < 3 �?季度则标记待合并/待废弃，1 季度观察期后废弃并移�?version-history.md Deprecated 章节，安全类规范永不退�?
  - **配置参数**：`meta_rules_governance.degradation_threshold`（默�?3）、`meta_rules_governance.observation_period_quarters`（默�?1）、`meta_rules_governance.degradation_exemption_categories`（默�?`["security", "config_driven"]`）在 `config.yaml` �?`meta_rules_governance` 节点管理
  - **适用**：所有已立的 meta-rule/step/B-REVIEW 检查点
  - **不适用**：安全类规范（永不退化）、config_driven 类规范（依赖 config 存在�?

- 🆕v4.34【强制�?*B-REVIEW-164：GLOBAL-AGGREGATE-TASK-FILTER 全局聚合任务级过�?*
  - 维度�?9 API 设计规范 / 35 列表聚合与状态联�?
  - 严重等级：critical（P0，越界数据风险）
  - 规范引用：meta-rule #38 全局聚合任务级过�?
  - **检查点**：全局视图（无 task_id）列表查询必须按各任务个体配置范围过滤，禁止只用全局默认范围；必须实�?`_filter_by_per_task_range` 类似函数按各任务个体 price_range/market_ratio 过滤
  - **检查项**�?
    1. 全局视图（无 task_id）列表查询必须调�?`_filter_by_per_task_range` 按各任务个体配置范围过滤
    2. 禁止只用全局默认范围（如全局 min/max）过滤所有任务的数据
    3. 各任务的个体配置范围（price_range/market_ratio）必须从 task config 读取
    4. 过滤后数据不得超出任一任务的个体配置范�?
  - **判断信号**�?
    - `grep "task_id.*None" <file>` 但无 `_filter_by_per_task` 调用 �?视为违规
    - `grep "global_min\\|global_max" <file>` 在列表查询函�?�?视为违规
  - **反模�?*�?
    ```python
    def list_evaluations(task_id: str | None = None):
        # 全局视图只用全局默认范围，未按各任务个体配置过滤
        items = db.query(...).filter(Item.price >= global_min, Item.price <= global_max).all()
        return items
    ```
  - **正确模式**�?
    ```python
    def list_evaluations(task_id: str | None = None):
        items = db.query(...).all()
        if task_id is None:
            # 全局视图按各任务个体配置范围过滤
            items = _filter_by_per_task_range(items, task_configs)
        return items
    ```
  - **配置参数**：`meta_rules_38_42.global_aggregate_filter.enabled`（默�?true）、`meta_rules_38_42.global_aggregate_filter.severity`（默�?CRITICAL）、`meta_rules_38_42.global_aggregate_filter.required_filter_function`（默�?`"_filter_by_per_task_range"`）、`meta_rules_38_42.global_aggregate_filter.task_config_fields`（默�?`["price_range", "market_ratio"]`）在 `config.yaml` �?`meta_rules_38_42.global_aggregate_filter` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.34.0 meta-rule #38 step 184
  - **适用**：全局视图列表查询（无 task_id 参数）、跨任务聚合查询、Dashboard 全局统计
  - **不适用**：指�?task_id 的列表查询、单一任务详情页、无配置范围的全局统计
  - **历史教训**：`evaluations_list.py` 全局视图只用全局默认 price_range 过滤，导�?task 上限 800 的商品在"捡漏价格参�?中显�?¥2,988.00 越界数据

- 🆕v4.34【强制�?*B-REVIEW-165：LIST-CROSS-DOMAIN-INJECT 列表交叉数据批量注入**
  - 维度�? 性能 / 35 列表聚合与状态联�?
  - 严重等级：warning（P1，性能退化风险）
  - 规范引用：meta-rule #39 列表交叉数据批量注入
  - **检查点**：列表交叉其他数据源必须批量查询 + TTL 缓存，禁�?N+1 单条查询；批量查询函数签名必须接�?`list[str]` 参数返回 `dict[str, T]` 映射
  - **检查项**�?
    1. 列表交叉其他数据源（�?items 交叉 prices）必须用批量查询（`WHERE id IN (...)`�?
    2. 批量查询结果必须�?TTL 缓存（默�?5 分钟），缓存 key 含数据源标识
    3. 禁止在循环中单条查询（`for item in items: db.query(...).filter(id == item.id)`�?
    4. 批量查询函数签名必须接受 `list[str]` 参数返回 `dict[str, T]` 映射
  - **判断信号**�?
    - `grep "for.*in.*items:" <file>` 后跟 `db.query` 单条查询 �?视为违规
    - `grep "db.query.*filter.*==.*item\\." <file>` 在循环内 �?视为违规
  - **反模�?*�?
    ```python
    def list_items_with_prices(item_ids: list[str]):
        result = []
        for item_id in item_ids:
            price = db.query(Price).filter(Price.item_id == item_id).first()  # N+1 查询
            result.append({"item": item, "price": price})
        return result
    ```
  - **正确模式**�?
    ```python
    def list_items_with_prices(item_ids: list[str]):
        prices = _batch_load_prices(item_ids)  # 批量查询 + TTL 缓存
        return [{"item": item, "price": prices.get(item.id)} for item in items]
    ```
  - **配置参数**：`meta_rules_38_42.cross_domain_inject.enabled`（默�?true）、`meta_rules_38_42.cross_domain_inject.severity`（默�?WARNING）、`meta_rules_38_42.cross_domain_inject.cache_ttl_seconds`（默�?300）、`meta_rules_38_42.cross_domain_inject.batch_size_limit`（默�?500）、`meta_rules_38_42.cross_domain_inject.forbidden_loop_patterns`（默�?`["for.*in.*items:.*db.query"]`）在 `config.yaml` �?`meta_rules_38_42.cross_domain_inject` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.34.0 meta-rule #39 step 185
  - **适用**：列表交叉数据源（items × prices、tasks × configs、orders × users）、Dashboard 聚合查询、批量统�?
  - **不适用**：单条详情查询（无交叉）、实时性要求高的查询（缓存不一致）、小批量（≤3 个）查询
  - **历史教训**：`price_dashboard.py` 在循环中单条查询每个 item �?price�?00 �?item 触发 100 �?DB 查询，批量查�?+ TTL 缓存后降�?1 �?

- 🆕v4.34【强制�?*B-REVIEW-166：MULTI-FIELD-LINKED-SWITCH 多字段联动开关范�?*
  - 维度�?1 错误处理 / 14 配置管理 / 35 列表聚合与状态联�?
  - 严重等级：major（P1，逻辑错误风险�?
  - 规范引用：meta-rule #40 多字段联动开关范�?
  - **检查点**：联动字段必须声明「主开关→过滤器」优先级矩阵，主开关失效时子过滤器自动禁用；mode 是主开关，*_bargain_only 是过滤器
  - **检查项**�?
    1. 联动字段（如 mode + bargain_only）必须声明优先级矩阵注释
    2. 主开关（mode）失效时子过滤器�?_bargain_only）自动禁�?
    3. 子过滤器不得独立于主开关生效（�?mode=notify �?bargain_only 不得过滤�?
    4. 优先级矩阵必须从 config 读取，禁止硬编码
  - **判断信号**�?
    - `grep "mode.*notify\\|mode.*auto_buy" <file>` 但无优先级矩阵注�?�?视为违规
    - `grep "bargain_only" <file>` 但无 `if mode ==` 前置判断 �?视为违规
  - **反模�?*�?
    ```python
    # 无优先级矩阵，bargain_only �?mode=notify 时仍过滤
    if item.bargain_only and not _is_bargain(item):
        continue
    ```
  - **正确模式**�?
    ```python
    # 优先级矩阵：mode 是主开关，*_bargain_only 是过滤器
    # mode=auto_buy: bargain_only 生效；mode=semi_auto: bargain_only 生效；mode=notify: bargain_only 不生�?
    if mode in ("auto_buy", "semi_auto") and item.bargain_only and not _is_bargain(item):
        continue
    ```
  - **配置参数**：`meta_rules_38_42.linked_switch_priority.enabled`（默�?true）、`meta_rules_38_42.linked_switch_priority.severity`（默�?MAJOR）、`meta_rules_38_42.linked_switch_priority.main_switch_field`（默�?`"mode"`）、`meta_rules_38_42.linked_switch_priority.filter_suffix`（默�?`"_bargain_only"`）、`meta_rules_38_42.linked_switch_priority.priority_matrix`（默�?`{"auto_buy": "filter_active", "semi_auto": "filter_active", "notify": "filter_disabled"}`）在 `config.yaml` �?`meta_rules_38_42.linked_switch_priority` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.34.0 meta-rule #40 step 186
  - **适用**：联动字段场景（mode + bargain_only、enabled + threshold、auto + limit）、配置驱动的业务逻辑、多字段组合判断
  - **不适用**：独立字段（无联动关系）、单一开关（无子过滤器）、运行时动态字段（无固定优先级�?
  - **历史教训**：TaskEditor �?mode=notify �?bargain_only 仍过滤，导致通知模式下用户看不到符合条件的商�?

- 🆕v4.34【强制�?*B-REVIEW-167：RESUME-PRECHECK-STRUCTURED 状态恢复前置校验结构化响应**
  - 维度�?1 错误处理 / 9 异步与调度器 / 35 列表聚合与状态联�?
  - 严重等级：critical（P0，API 层处理困难风险）
  - 规范引用：meta-rule #41 状态恢复前置校验结构化响应
  - **检查点**：precheck 必须返回 5 字段结构�?dict `{resume_blocked, reason_code, user_hint, retry_after, task_registered}` 不抛异常，API 层直接透传；自定义 ResumeBlockedError 异常�?API 层转换为 400 响应
  - **检查项**�?
    1. precheck 函数必须返回 5 字段结构�?dict（不抛异常）
    2. 5 字段：`resume_blocked`（bool）、`reason_code`（str）、`user_hint`（str）、`retry_after`（int|None）、`task_registered`（bool�?
    3. precheck 函数体内禁止 `raise`（用 try/except 兜底返回结构�?dict�?
    4. API 层直接透传 precheck 结果，自定义 ResumeBlockedError 转换�?400 响应
  - **判断信号**�?
    - `grep "def precheck_" <file>` 函数体内�?`raise` �?视为违规
    - `grep "def precheck_" <file>` 返回值缺 5 字段任一 �?视为违规
    - `grep "raise ResumeBlockedError" <file>` 不在 API �?�?视为违规
  - **反模�?*�?
    ```python
    def precheck_resume(self, task_id: str) -> dict:
        if not self._is_root_cause_resolved(task_id):
            raise ResumeBlockedError("root cause not resolved")  # 抛异常，API 层难以处�?
        return {"resume_blocked": False}
    ```
  - **正确模式**�?
    ```python
    def precheck_resume(self, task_id: str) -> dict:
        try:
            if not self._is_root_cause_resolved(task_id):
                return {
                    "resume_blocked": True,
                    "reason_code": "root_cause_unresolved",
                    "user_hint": "请先修复根因后再恢复",
                    "retry_after": 30,
                    "task_registered": True,
                }
            return {"resume_blocked": False, "reason_code": "", "user_hint": "", "retry_after": None, "task_registered": True}
        except Exception:
            logger.exception("precheck_resume failed")
            return {"resume_blocked": True, "reason_code": "precheck_error", "user_hint": "校验失败", "retry_after": 60, "task_registered": True}
    ```
  - **配置参数**：`meta_rules_38_42.precheck_structured_fields.enabled`（默�?true）、`meta_rules_38_42.precheck_structured_fields.severity`（默�?CRITICAL）、`meta_rules_38_42.precheck_structured_fields.required_fields`（默�?`["resume_blocked", "reason_code", "user_hint", "retry_after", "task_registered"]`）、`meta_rules_38_42.precheck_structured_fields.forbid_raise`（默�?true）、`meta_rules_38_42.precheck_structured_fields.api_error_status`（默�?400）在 `config.yaml` �?`meta_rules_38_42.precheck_structured_fields` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.34.0 meta-rule #41 step 187
  - **适用**：pause/resume 语义的组件（scheduler/task/session）、状态恢复前置校验、API �?precheck endpoint
  - **不适用**：无 pause/resume 语义的组件、一次性校验（无状态恢复）、同步阻塞校验（�?API 透传需求）
  - **历史教训**：`scheduler.py` precheck_resume 抛异常，`api_tasks.py` 无法透传结构化响应，前端无法显示具体阻塞原因

- 🆕v4.34【强制�?*B-REVIEW-168：CONFIG-DRIVEN-THRESHOLD-FALLBACK 配置化阈值兜底范�?*
  - 维度�?4 配置管理 / 35 列表聚合与状态联�?
  - 严重等级：major（P1，配置缺失即崩溃风险�?
  - 规范引用：meta-rule #42 配置化阈值兜底范�?
  - **检查点**：从 config 读取的阈值必须有 try/except 兜底默认值，禁止配置缺失即崩溃；兜底默认值必须从 config �?fallback_defaults 节点读取
  - **检查项**�?
    1. �?config 读取的阈值（�?P10 分位数）必须�?try/except 包裹
    2. 配置缺失时必须回退到兜底默认值（�?P10 默认 0.10�?
    3. 兜底默认值必须从 config �?`fallback_defaults` 节点读取，禁止硬编码
    4. 兜底触发时必�?`logger.warning` 记录（不静默�?
  - **判断信号**�?
    - `grep "get_config\\(\\)\\.\\w+\\.\\w+" <file>` 但无 `try.*except` 包裹 �?视为违规
    - `grep "config\\.bargain_price\\.p10" <file>` 但无兜底 �?视为违规
  - **反模�?*�?
    ```python
    p10 = config.bargain_price.p10_percentile  # 配置缺失�?AttributeError 崩溃
    ```
  - **正确模式**�?
    ```python
    try:
        p10 = config.bargain_price.p10_percentile
    except (AttributeError, KeyError):
        p10 = fallback_defaults.get("p10_percentile", 0.10)
        logger.warning("config.bargain_price.p10_percentile 缺失，回退到默认�?{}", p10)
    ```
  - **配置参数**：`meta_rules_38_42.config_fallback_defaults.enabled`（默�?true）、`meta_rules_38_42.config_fallback_defaults.severity`（默�?MAJOR）、`meta_rules_38_42.config_fallback_defaults.fallback_defaults`（默�?`{"p10_percentile": 0.10, "market_ratio_threshold": 0.85, "price_range_tolerance": 0.05}`）、`meta_rules_38_42.config_fallback_defaults.require_warning_log`（默�?true）在 `config.yaml` �?`meta_rules_38_42.config_fallback_defaults` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.34.0 meta-rule #42 step 188
  - **适用**：从 config 读取的阈�?参数（P10 分位�?market_ratio/price_range）、配置驱动的业务逻辑、可选配置项
  - **不适用**：必需配置项（缺失应崩溃）、硬编码常量（非配置驱动）、启动时配置校验（一次性）
  - **历史教训**：`price_dashboard.py` 直接读取 `config.bargain_price.p10_percentile`，配置缺失时 AttributeError 导致 P10 计算崩溃

---

## 维度 36：跨层契约与测试同步（meta-rules #43-#47 落地�?

- 🆕v4.35【强制�?*B-REVIEW-173：EVENT-MULTI-EMIT-ALIGN 事件多发布点字段对齐**
  - 维度�?2 业务事件 / 36 跨层契约与测试同�?
  - 严重等级：critical（P0，事件消费方字段缺失导致业务流程断裂�?
  - 规范引用：meta-rule #43 事件多发布点字段对齐
  - **检查点**：后端业务事件在多个层（worker/service/route/SSE 推送器）有发布点时，每�?payload 字段集必须一致；同一事件类型所有发布点必须使用统一�?payload 构造函数，禁止散落字典字面�?
  - **检查项**�?
    1. 同一事件类型所有发布点必须使用统一 payload 构造函数（�?`build_event_payload`�?
    2. 必填字段（如 `task_mode`/`task_id`/`event_type`）在所有发布点必须存在
    3. 新增字段时必须同步更新所有发布点（含 SSE 推送器/worker 事件循环/route 钩子�?
    4. payload 构造函数必须有单元测试覆盖所有事件类型的字段完整�?
  - **判断信号**�?
    - `grep "EVAL_PASSED\|task\.started\|task\.completed" src/` 后逐处人工核对字段�?�?字段不一致视为违�?
    - `grep "payload = {" src/` 检查是否直接构造字典字面量而非调用统一函数 �?视为违规
  - **反模�?*�?
    ```python
    # 事件发布�?A（worker�?
    await event_bus.emit("EVAL_PASSED", {"task_id": tid, "score": s})
    # 事件发布�?B（route 钩子�?
    await event_bus.emit("EVAL_PASSED", {"task_id": tid, "score": s, "task_mode": mode})  # �?task_mode �?A
    ```
  - **正确模式**�?
    ```python
    # 统一构造函�?
    def build_eval_passed_payload(task_id: str, score: float, task_mode: str) -> dict:
        return {"task_id": task_id, "score": score, "task_mode": task_mode}
    # 所有发布点统一调用
    await event_bus.emit("EVAL_PASSED", build_eval_passed_payload(tid, s, mode))
    ```
  - **配置参数**：`meta_rules_43_47.event_multi_emit_alignment.enabled`（默�?true）、`meta_rules_43_47.event_multi_emit_alignment.severity`（默�?CRITICAL）、`meta_rules_43_47.event_multi_emit_alignment.emit_points`（默�?`["worker", "service", "route", "sse_pusher"]`）、`meta_rules_43_47.event_multi_emit_alignment.required_fields`（默�?`["task_id", "task_mode", "event_type"]`）、`meta_rules_43_47.event_multi_emit_alignment.event_types`（默�?`["EVAL_PASSED", "task.started", "task.completed"]`）在 `config.yaml` �?`meta_rules_43_47.event_multi_emit_alignment` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.35.0 meta-rule #43
  - **适用**：业务事件多层发布（worker/service/route/SSE 推送器）、跨进程事件传递、通知中心事件触发
  - **不适用**：单一发布点的内部事件、调试日志事件、单元测�?mock 事件
  - **历史教训**：SEMI_AUTO 模式�?EVAL_PASSED 事件三处发布点中 task_mode 字段不一致，导致通知模板渲染�?task_mode �?None，前端未渲染"确认下单"链接，用户无法触发确认流�?

- 🆕v4.35【强制�?*B-REVIEW-174：ROUTE-REGISTRY-BACKEND-SYNC 路由注册表与后端 endpoint 契约**
  - 维度�?9 API 契约 / 36 跨层契约与测试同�?
  - 严重等级：critical（P0，路由无后端支持时静�?fallback 到首页）
  - 规范引用：meta-rule #44 路由注册表与后端 endpoint 契约
  - **检查点**：前端路由注册表中的每条路由，后端必须提供对�?endpoint；新增前端路由必须同步在后端注册对应 API endpoint，且路由 fallback 不应静默重定向，应返�?404 显式提示
  - **检查项**�?
    1. 前端路由注册表中每条路由必须有后端对�?endpoint
    2. 路由 fallback 必须显式提示"路由未注�?而非静默重定向首�?
    3. 新增路由�?PR 必须同时修改前后端，git diff 仅含前端路由无后�?endpoint 视为违规
    4. 路由注册校验脚本退出码 0 才算通过
  - **判断信号**�?
    - `grep "path:" frontend/src/.../sheetRegistry` 后逐条与后�?endpoint 比对 �?缺失视为违规
    - 路由 fallback 配置�?`<Navigate to="/" replace />` 静默重定�?�?视为违规
  - **反模�?*�?
    ```typescript
    // 前端注册新路由但后端无对�?endpoint
    { path: "/confirm-buy", element: <ConfirmBuy /> }
    // 后端�?@router.get("/confirm-buy") endpoint
    // 路由 fallback 静默重定�?
    <Route path="*" element={<Navigate to="/" replace />} />
    ```
  - **正确模式**�?
    ```typescript
    // 前端路由注册
    { path: "/confirm-buy", element: <ConfirmBuy /> }
    // 后端同步提供 endpoint
    @router.get("/api/confirm-buy/{task_id}")
    async def confirm_buy(task_id: str, request: Request): ...
    // 路由 fallback 显式 404
    <Route path="*" element={<NotFound />} />
    ```
  - **配置参数**：`meta_rules_43_47.frontend_route_registration.enabled`（默�?true）、`meta_rules_43_47.frontend_route_registration.severity`（默�?CRITICAL）、`meta_rules_43_47.frontend_route_registration.route_list`（默认从 `menu_registry.yaml` 读取）、`meta_rules_43_47.frontend_route_registration.endpoint_mapping`（默�?`{"confirm-buy": "/api/confirm-buy/{task_id}"}`）、`meta_rules_43_47.frontend_route_registration.silent_redirect_forbidden`（默�?true）在 `config.yaml` �?`meta_rules_43_47.frontend_route_registration` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.35.0 meta-rule #44
  - **适用**：所有前端路由、新增前端页面、SPA 路由变更
  - **不适用**：纯前端 SPA 路由无后端数据（如静态帮助页）、纯客户端状态路�?
  - **历史教训**：新�?SEMI_AUTO 确认路由 `/confirm-buy` 时，前端 sheetRegistry 已注册但后端未提供对�?endpoint，导致路�?fallback `<Navigate to="/" replace />` 静默重定向到首页，用户点击确认链接无反应

- 🆕v4.35【强制�?*B-REVIEW-175：CALLBACK-URL-QUERY-CONSTRUCTION 回链 URL query string 构�?*
  - 维度�?2 业务事件 / 36 跨层契约与测试同�?
  - 严重等级：critical（P0，query string 缺失导致前端无法恢复上下文）
  - 规范引用：meta-rule #45 回链 URL query string 构�?
  - **检查点**：后端构造的回链 URL 必须包含前端所需的所�?query string 参数；前端解�?URL 时必须保留完�?query string，禁止使�?`pathname` 单独取值而丢�?search 部分
  - **检查项**�?
    1. 回链 URL 模板必须显式声明所需 query 参数清单
    2. 后端构�?URL 时必须使�?urlencode 而非 f-string 拼接
    3. 前端路由查找逻辑（如 `findSheetMeta`）必须剥�?query string 仅取 pathname
    4. 前端路由跳转逻辑（如 `useSheetSync`）必须保留完�?query string
  - **判断信号**�?
    - `grep "f\".*task_id\|f\".*item_id\" src/"` 检�?URL 拼接是否�?urlencode �?�?f-string 视为违规
    - `grep "useLocation\|useNavigate" frontend/src/` 后检�?pathname 是否剥离 query �?未剥离视为违�?
  - **反模�?*�?
    ```python
    # 后端�?f-string 拼接 URL 缺参�?
    callback_url = f"/confirm-buy?task_id={tid}"  # �?item_id 等参�?
    ```
    ```typescript
    // 前端�?pathname 单独取值丢�?query string
    const meta = findSheetMeta(location.pathname);  // 丢弃�??task_id=xxx
    navigate(location.pathname);  // 丢失 query string
    ```
  - **正确模式**�?
    ```python
    # 后端�?urlencode 构造完�?query string
    from urllib.parse import urlencode
    params = {"task_id": tid, "item_id": iid, "task_mode": mode}
    callback_url = f"/confirm-buy?{urlencode(params)}"
    ```
    ```typescript
    // 前端剥离 query 仅用于路由查找，跳转时保留完�?URL
    const meta = findSheetMeta(location.pathname);  // pathname 用于查找
    navigate(`${location.pathname}${location.search}`);  // search 保留
    ```
  - **配置参数**：`meta_rules_43_47.external_callback_query_retention.enabled`（默�?true）、`meta_rules_43_47.external_callback_query_retention.severity`（默�?CRITICAL）、`meta_rules_43_47.external_callback_query_retention.callback_routes`（默�?`["/confirm-buy", "/notifications/{id}"]`）、`meta_rules_43_47.external_callback_query_retention.required_params`（默�?`["task_id", "item_id", "task_mode"]`）、`meta_rules_43_47.external_callback_query_retention.urlencode_required`（默�?true）在 `config.yaml` �?`meta_rules_43_47.external_callback_query_retention` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.35.0 meta-rule #45
  - **适用**：通知/邮件中的回链 URL、SSE 推送中的跳转链接、消息卡片中的按钮链�?
  - **不适用**：纯内部 API 调用、后端服务间调用的内�?URL、静态资�?URL
  - **历史教训**：后端构造的确认链接 `/confirm-buy?task_id=xxx` 缺少 `task_mode` 参数，前�?`findSheetMeta` �?`location.pathname` 取值但 `useSheetSync` 跳转时丢�?query string，导致用户从通知点击确认链接后页面无法加载任务数�?

- 🆕v4.35【强制�?*B-REVIEW-176：TEST-SIGNATURE-SYNC 接口签名变更测试同步**
  - 维度�?4 测试规范 / 36 跨层契约与测试同�?
  - 严重等级：major（P1，测试与生产代码不一致导�?CI 通过但生产故障）
  - 规范引用：meta-rule #46 接口签名变更测试同步
  - **检查点**：后端接口签名变更后必须同步更新所有测试调用；mock 类型必须与实际返回类型匹配（AsyncMock vs MagicMock）；新增参数必须有测试覆�?
  - **检查项**�?
    1. 生产代码方法签名变更时同 PR 必须修改 tests/ 目录下相关测�?
    2. 测试�?mock 对象类型必须与实际返回类型匹配（async 函数�?AsyncMock，同步函数用 MagicMock�?
    3. 接口新增参数必须有测试覆盖默认值与边界�?
    4. 测试�?mock 字段集必须与生产代码字段集一�?
  - **判断信号**�?
    - `git diff` 生产代码方法签名变更但同 PR `tests/` 目录无修�?�?视为违规
    - `grep "AsyncMock\|MagicMock" tests/` 后核对与�?mock 函数 async/同步属性是否匹�?�?不匹配视为违�?
    - `grep "def test_" tests/` 后检�?mock 字段集是否覆盖生产代码新增字�?�?缺失视为违规
  - **反模�?*�?
    ```python
    # 生产代码 async 函数
    async def manual_takeover(task_id: str, request: Request): ...
    # 测试�?MagicMock（应 AsyncMock�?
    mock_takeover = MagicMock()
    # 测试�?request 参数（接口已新增�?
    result = await manual_takeover("tid")  # �?request 参数
    ```
  - **正确模式**�?
    ```python
    # 生产代码 async 函数
    async def manual_takeover(task_id: str, request: Request): ...
    # 测试�?AsyncMock
    mock_takeover = AsyncMock()
    # 测试同步更新参数
    mock_request = MagicMock()
    mock_request.state.user_id = "uid123"
    result = await manual_takeover("tid", mock_request)
    ```
  - **配置参数**：`meta_rules_43_47.test_synchronization.enabled`（默�?true）、`meta_rules_43_47.test_synchronization.severity`（默�?MAJOR）、`meta_rules_43_47.test_synchronization.signature_check_patterns`（默�?`["def .*\\(.*\\):", "async def .*\\(.*\\):"]`）、`meta_rules_43_47.test_synchronization.mock_type_mapping`（默�?`{"async": "AsyncMock", "sync": "MagicMock"}`）、`meta_rules_43_47.test_synchronization.require_test_diff`（默�?true）在 `config.yaml` �?`meta_rules_43_47.test_synchronization` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.35.0 meta-rule #46
  - **适用**：所有接口签名重构、async/同步属性变更、新�?移除参数、字段集变更
  - **不适用**：纯内部实现重构（不改变签名）、私有方法重构、注�?文档更新
  - **历史教训**：`manual_takeover` 接口新增 `request` 参数后测试未同步更新，导致测试调用缺参数报错；`mock_dedup.filter_new` �?AsyncMock 但生产代码改为同步函数，导致 await 同步返回值报�?

- 🆕v4.35【强制�?*B-REVIEW-177：EXTERNAL-DEP-ISOLATION 外部依赖隔离与测试可重复�?*
  - 维度�?4 测试规范 / 36 跨层契约与测试同�?
  - 严重等级：major（P1，外部依赖未隔离导致测试不稳定与误报�?
  - 规范引用：meta-rule #51 外部依赖隔离与测试可重复�?
  - **检查点**：测试中依赖 keyring/env/file/network 必须显式 patch；patch 必须返回确定性值（�?`return_value=None` 表示"无配�?）；禁止依赖外部资源真实状�?
  - **检查项**�?
    1. 测试中调�?`get_secret`/`os.environ[...]`/文件读取/网络请求的位置必须有显式 patch
    2. patch 必须返回确定性值（�?`return_value=None` 表示"无配�?场景�?
    3. keyring fallback 必须显式测试（mock keyring.get_password 返回 None 时降级到 env/file�?
    4. 测试不得依赖外部文件系统状态（�?`~/.config/xxx` 是否存在�?
  - **判断信号**�?
    - `grep "get_secret\|os\.environ\[" tests/` 但同函数�?`patch(..., return_value=None)` �?视为违规
    - `grep "keyring" tests/` 但无 `patch("keyring.get_password", return_value=None)` �?视为违规
    - `grep "open(" tests/` 但无 `mock_open` �?视为违规
  - **反模�?*�?
    ```python
    # 测试调用 get_secret 但无 patch（依赖真�?keyring/env 状态）
    def test_dingtalk_send_without_secret():
        # �?patch get_secret �?测试依赖真实环境变量
        result = send_dingtalk("msg")
        assert result is False  # 可能因环境变量存在而失�?
    ```
  - **正确模式**�?
    ```python
    # 测试显式 patch get_secret 返回 None
    @patch("xianyu_hunter.config.get_secret", return_value=None)
    def test_dingtalk_send_without_secret(mock_secret):
        result = send_dingtalk("msg")
        assert result is False  # 确定性：�?secret 时返�?False
    # keyring fallback 显式测试
    @patch("keyring.get_password", return_value=None)
    def test_keyring_fallback_to_env(mock_keyring):
        os.environ["XX_TOKEN"] = "from_env"
        result = get_token()
        assert result == "from_env"
    ```
  - **配置参数**：`meta_rules_43_47.external_dependency_isolation.enabled`（默�?true）、`meta_rules_43_47.external_dependency_isolation.severity`（默�?MAJOR）、`meta_rules_43_47.external_dependency_isolation.dependency_types`（默�?`["keyring", "env", "file", "network"]`）、`meta_rules_43_47.external_dependency_isolation.isolation_strategies`（默�?`{"keyring": "patch return_value=None", "env": "patch.dict os.environ", "file": "mock_open", "network": "responses_mock"}`）、`meta_rules_43_47.external_dependency_isolation.require_deterministic`（默�?true）在 `config.yaml` �?`meta_rules_43_47.external_dependency_isolation` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.35.0 meta-rule #47
  - **适用**：所有依赖外部资源的测试（keyring/env/file/network）、CI 环境、跨平台测试
  - **不适用**：纯函数测试（无外部依赖）、单元测�?mock 内部对象、集成测试显式需要真实资�?
  - **历史教训**：钉钉通知测试�?`get_secret` �?patch，CI 环境存在真实 webhook_url 导致测试发送真实请求；keyring fallback 未测试，本地 keyring 有缓存导�?CI 与本地测试结果不一�?

- 🆕v4.36【强制�?*B-REVIEW-178：SCHEDULER-RUNTIME-TOGGLE-SYMMETRY 调度器运行时开关对称�?*
  - 维度�? 异步与调度器 / 36 跨层契约与测试同�?
  - 严重等级：critical（P0，配置开关无效导致禁用后仍持续执行）
  - 规范引用：meta-rule #48 调度器运行时开关对称�?
  - **检查点**：调度器 `update_config(enabled=False)` 必须在同一个方法内完成"设标志位 + remove_job"两步操作；`update_config(enabled=True)` 必须调用 `add_job(...)` �?`resume_job(job_id)` 重新注册/恢复 job；job 函数入口必须 `if not self._enabled: return` 作为 double-check；调度器必须提供 `is_enabled() -> bool` 方法�?API 层查�?
  - **检查项**�?
    1. `update_config(enabled=False)` 必须调用 `scheduler.remove_job(job_id)`，禁止只设标志位
    2. `update_config(enabled=True)` 必须调用 `scheduler.add_job(...)` �?`resume_job(job_id)`
    3. job 函数入口必须�?`if not self._enabled: return` double-check
    4. 调度器必须提�?`is_enabled() -> bool` 公共方法
    5. `enabled` 字段必须�?`config.yaml` 读取，`update_config` 修改后必须同步写�?config
  - **判断信号**�?
    - `grep "update_config" src/` 后检�?`enabled=False` 分支是否�?`remove_job` �?缺失视为违规
    - `grep "_enabled" src/` 后检�?job 函数入口是否�?double-check �?缺失视为违规
    - `grep "is_enabled" src/` 无对应方法定�?�?视为违规
  - **反模�?*�?
    ```python
    # 只设标志位不移除 job，APScheduler 已注册的 job 仍按 trigger 触发
    def update_config(self, *, enabled: bool | None = None) -> None:
        if enabled is not None:
            self._enabled = enabled  # remove_job 缺失
    ```
  - **正确模式**�?
    ```python
    def update_config(self, *, enabled: bool | None = None) -> None:
        if enabled is not None:
            self._enabled = enabled
            if not enabled:
                try:
                    self._scheduler.remove_job(self._job_id)
                except Exception as e:
                    logger.warning("移除 job 失败: {}", e)
            else:
                self._scheduler.add_job(self._run_job, trigger=..., id=self._job_id)

    def _run_job(self):
        if not self._enabled:
            logger.warning("调度器已禁用�?job 仍触发，检�?update_config 实现")
            return
        # ... 业务逻辑

    def is_enabled(self) -> bool:
        return self._enabled
    ```
  - **配置参数**：`meta_rules_48_51.scheduler_runtime_toggle.enabled`（默�?true）、`meta_rules_48_51.scheduler_runtime_toggle.severity`（默�?CRITICAL）、`meta_rules_48_51.scheduler_runtime_toggle.require_remove_job`（默�?true）、`meta_rules_48_51.scheduler_runtime_toggle.require_entry_check`（默�?true）、`meta_rules_48_51.scheduler_runtime_toggle.require_is_enabled_method`（默�?true）、`meta_rules_48_51.scheduler_runtime_toggle.require_config_persist`（默�?true）在 `config.yaml` �?`meta_rules_48_51.scheduler_runtime_toggle` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #48
  - **适用**：所�?APScheduler 调度器（BackgroundScheduler/AsyncIOScheduler）；具有 `enabled` 配置开关的后台任务；运行时可动态启停的调度�?
  - **不适用**：一次性任务（�?`enabled` 字段）；启动时确定整个生命周期不启停的调度器；外部托管调度器（如 celery beat�?
  - **历史教训**：`BatchRefreshScheduler` 禁用后批量采集仍持续执行，用户反馈「关闭开关后任务还在跑」。排查发�?`update_config` 只设标志位未 remove_job，APScheduler 已注册的 job 仍按 trigger 触发

- 🆕v4.36【强制�?*B-REVIEW-179：TIME-PARAM-CONFIG-DRIVEN 时间参数配置�?*
  - 维度�?4 配置管理 / 36 跨层契约与测试同�?
  - 严重等级：major（P1，硬编码时间参数无法根据业务场景调整�?
  - 规范引用：meta-rule #49 时间参数配置�?
  - **检查点**：异常重试等待秒数、轮询间隔、超时秒数等时间参数必须�?`config.yaml` 读取，禁止硬编码字面量数字；配置节点必须提供合理的默认值与边界校验
  - **检查项**�?
    1. `grep "return 300\\|return 600\\|sleep(300)\\|sleep(600)" src/` 检查是否有硬编码时间字面量
    2. 时间参数必须�?`config.yaml` 的对应节点读取（�?`task_scheduler.exception_retry_wait_seconds`�?
    3. 配置节点必须提供默认值（�?`config.example.yaml` 中声明）
    4. 配置加载时必须有边界校验（min/max/non_negative�?
  - **判断信号**�?
    - `grep "\\b\\d{3,}\\b" src/xianyu_hunter/modules/scheduler.py` 后人工核对是否为时间参数字面�?�?是则视为违规
    - `grep "time\\.sleep\\|asyncio\\.sleep" src/` 后检查参数来源是否为 config 引用 �?字面量视为违�?
  - **反模�?*�?
    ```python
    # 异常重试等待硬编�?300 �?
    def _compute_next_wait_seconds(self, consecutive_errors: int) -> int:
        return 300  # 硬编码，无法根据业务场景调整
    ```
  - **正确模式**�?
    ```python
    def _compute_next_wait_seconds(self, consecutive_errors: int) -> int:
        # �?config 读取，提供默认值兜�?
        base_wait = getattr(self._config, 'exception_retry_wait_seconds', 300)
        max_wait = getattr(self._config, 'exception_retry_max_seconds', 1800)
        wait = min(base_wait * (2 ** min(consecutive_errors - 1, 5)), max_wait)
        return wait
    ```
  - **配置参数**：`meta_rules_48_51.time_param_config_driven.enabled`（默�?true）、`meta_rules_48_51.time_param_config_driven.severity`（默�?MAJOR）、`meta_rules_48_51.time_param_config_driven.param_patterns`（默�?`["exception_retry_wait", "polling_interval", "timeout_seconds", "cooldown_seconds"]`）、`meta_rules_48_51.time_param_config_driven.forbidden_literals`（默�?`[300, 600, 1800, 3600]`）、`meta_rules_48_51.time_param_config_driven.require_default_value`（默�?true）、`meta_rules_48_51.time_param_config_driven.require_boundary_check`（默�?true）在 `config.yaml` �?`meta_rules_48_51.time_param_config_driven` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #49
  - **适用**：所有时间参数（重试等待/轮询间隔/超时秒数/冷却期）；调度器配置；异步任务等待时�?
  - **不适用**：测试代码中的固定时间参数（�?`await asyncio.sleep(0.1)`）；性能优化中的微秒�?sleep（如 `asyncio.sleep(0)` 让出控制权）；日志输出间隔（如每 100 条日志输出一次）
  - **历史教训**：`scheduler.py` �?`_compute_next_wait_seconds` 异常重试等待硬编�?`return 300`，所有任务异常后必须�?5 分钟才能重试，无法根据业务场景调�?

- 🆕v4.36【强制�?*B-REVIEW-180：LIFECYCLE-RESOURCE-CLEANUP 长生命周期对象状态清�?*
  - 维度�? 异步与调度器 / 36 跨层契约与测试同�?
  - 严重等级：major（P1，状态字典无限增长导致内存泄漏）
  - 规范引用：meta-rule #50 长生命周期对象状态清�?
  - **检查点**：长生命周期对象（scheduler/container/registry/manager）的 `__init__` 中所�?`dict[str, ...]` 类型字段必须支持�?task_id 清理；DELETE API 删除 task 时必须调�?`drop_task_state(task_id)` 清理内存状�?
  - **检查项**�?
    1. 长生命周期对象的 `__init__` 中所�?`dict[str, ...]` 字段视为状态字典，必须支持�?task_id 清理
    2. 必须提供 `drop_task_state(self, task_id: str) -> None` 方法，内部遍历所有状态字�?`pop(task_id, None)`
    3. `DELETE /api/tasks/{task_id}` �?`DELETE /api/tasks/batch` 路由必须调用 `container.scheduler.drop_task_state(task_id)`
    4. `drop_task_state` 内部 `pop` 操作必须 `try/except Exception: logger.debug(...)` 容错，不阻断主流�?
  - **判断信号**�?
    - `grep "self\\._\\w+: dict\\[str," src/xianyu_hunter/modules/scheduler.py` 后检查是否有 `drop_task_state` 方法 �?缺失视为违规
    - `grep "delete_task\\|delete.*task" src/xianyu_hunter/web/routes/api_tasks.py` 后检查是否调�?`drop_task_state` �?缺失视为违规
  - **反模�?*�?
    ```python
    # 状态字典无清理方法，DELETE API 不调用清�?
    class TaskScheduler:
        def __init__(self):
            self._resume_cooldown: dict[str, float] = {}  # �?drop_task_state 方法
            self._last_failure_reason: dict[str, str] = {}

    # DELETE API 只删 DB 不清理内存状�?
    @router.delete("/{task_id}")
    async def delete_task(task_id: str):
        await task_store.delete(task_id)  # �?drop_task_state 调用
        return {"deleted": task_id}
    ```
  - **正确模式**�?
    ```python
    class TaskScheduler:
        def __init__(self):
            self._resume_cooldown: dict[str, float] = {}
            self._last_failure_reason: dict[str, str] = {}

        def drop_task_state(self, task_id: str) -> None:
            """清理指定 task 的所有状态字�?""
            try:
                self._resume_cooldown.pop(task_id, None)
                self._last_failure_reason.pop(task_id, None)
            except Exception as e:
                logger.debug("清理 task 状态失败（忽略�? {}", e)

    @router.delete("/{task_id}")
    async def delete_task(task_id: str):
        await task_store.delete(task_id)
        try:
            container.scheduler.drop_task_state(task_id)
        except Exception as e:
            logger.debug("清理 scheduler 任务状态失败（忽略�? {}", e)
        return {"deleted": task_id}
    ```
  - **配置参数**：`meta_rules_48_51.lifecycle_resource_cleanup.enabled`（默�?true）、`meta_rules_48_51.lifecycle_resource_cleanup.severity`（默�?MAJOR）、`meta_rules_48_51.lifecycle_resource_cleanup.state_dict_pattern`（默�?`"self\\._\\w+: dict\\[str,"`）、`meta_rules_48_51.lifecycle_resource_cleanup.require_drop_method`（默�?true）、`meta_rules_48_51.lifecycle_resource_cleanup.require_delete_api_call`（默�?true）、`meta_rules_48_51.lifecycle_resource_cleanup.cleanup_strategy`（默�?`lazy`）、`meta_rules_48_51.lifecycle_resource_cleanup.cleanup_triggers`（默�?`["delete_api", "scheduler_shutdown"]`）在 `config.yaml` �?`meta_rules_48_51.lifecycle_resource_cleanup` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #50
  - **适用**：长生命周期对象（scheduler/container/registry/manager/singleton service）；持有 `dict[str, ...]` 状态字段的组件；task 级或 session 级状态缓存；DELETE API 删除资源的场�?
  - **不适用**：短生命周期对象（请求级/函数级局部变量）；无状态服务（stateless）；只读缓存（never expire）；测试 fixture（测试结束自动清理）
  - **历史教训**：`scheduler.py` �?`_resume_cooldown` 字典�?task 异常 pause 后写入冷却时间戳，DELETE API 删除 task 时未清理，长期运行后字典无限增长，服务运�?7 天后内存�?200MB 涨到 1.5GB

- 🆕v4.36 experimental【强制�?*B-REVIEW-181：CRON-MIN-INTERVAL-CHECK 用户输入时间表达式校�?*
  - 维度�?4 配置管理 / 36 跨层契约与测试同�?
  - 严重等级：major（P1，cron 表达式无最小间隔校验触发反爬封禁）
  - 规范引用：meta-rule #51 用户输入时间表达式校验（experimental�? 季度观察期）
  - **检查点**：用户输入的 cron 表达式必须有最小执行间隔校验；解析失败�?cron 表达式必须返回结构化错误不抛异常；最小间隔阈值从 `config.yaml` 读取不硬编码
  - **检查项**�?
    1. 用户输入�?cron 表达式必须用 `apscheduler.triggers.cron.CronTrigger.from_crontab(cron_expr)` 解析
    2. 解析后必须计算最小执行间隔，低于阈值的拒绝并返回结构化错误 `{valid, reason_code, user_hint, min_interval_seconds}`
    3. 最小间隔阈值从 `config.yaml` �?`cron_min_interval_check.min_interval_seconds` 节点读取（默�?60 秒）
    4. 解析失败必须返回结构化错误不抛异�?
  - **判断信号**�?
    - `grep "schedule_cron\\|cron_expr" src/` 后检查是否有最小间隔校�?�?缺失视为违规
    - `grep "CronTrigger\\.from_crontab" src/` 后检查是否有 try/except 容错 �?缺失视为违规
  - **反模�?*�?
    ```python
    # 接受任意 cron 表达式，无最小间隔校�?
    def validate_cron(cron_expr: str) -> bool:
        try:
            CronTrigger.from_crontab(cron_expr)
            return True  # 接受 "* * * * *"（每分钟执行�?
        except Exception:
            return False
    ```
  - **正确模式**�?
    ```python
    from apscheduler.triggers.cron import CronTrigger
    from datetime import datetime, timedelta

    def validate_cron_with_min_interval(cron_expr: str, min_interval: int = 60) -> dict:
        """校验 cron 表达式并检查最小间�?""
        try:
            trigger = CronTrigger.from_crontab(cron_expr)
        except Exception as e:
            return {"valid": False, "reason_code": "PARSE_ERROR",
                    "user_hint": f"cron 表达式格式错�? {e}", "min_interval_seconds": None}
        # 计算连续两次触发的最小间�?
        now = datetime.now()
        next_runs = []
        current = now
        for _ in range(10):  # 采样 10 次取最小间�?
            current = trigger.get_next_fire_time(current, current)
            if current is None:
                break
            next_runs.append(current)
        if len(next_runs) >= 2:
            intervals = [(next_runs[i+1] - next_runs[i]).total_seconds() for i in range(len(next_runs)-1)]
            min_interval_actual = min(intervals)
            if min_interval_actual < min_interval:
                return {"valid": False, "reason_code": "INTERVAL_TOO_SHORT",
                        "user_hint": f"最小执行间�?{min_interval_actual}s 低于阈�?{min_interval}s",
                        "min_interval_seconds": min_interval_actual}
        return {"valid": True, "reason_code": None, "user_hint": None,
                "min_interval_seconds": None}
    ```
  - **配置参数**：`meta_rules_48_51.cron_min_interval_check.enabled`（默�?true）、`meta_rules_48_51.cron_min_interval_check.severity`（默�?MAJOR）、`meta_rules_48_51.cron_min_interval_check.min_interval_seconds`（默�?60）、`meta_rules_48_51.cron_min_interval_check.sample_count`（默�?10）、`meta_rules_48_51.cron_min_interval_check.require_structured_error`（默�?true）在 `config.yaml` �?`meta_rules_48_51.cron_min_interval_check` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #51（experimental�?
  - **适用**：所有接受用户输�?cron 表达式的场景（任务调�?定时采集/状态回查）；APScheduler CronTrigger 场景
  - **不适用**：系统内部固�?cron 表达式（非用户输入）；interval 触发器（已有 interval 参数）；一次性任务（无重复执行）
  - **历史教训**：task �?`schedule_cron` 字段接受任意 cron 表达式，用户配置 `* * * * *`（每分钟执行）导致批量采集每分钟触发一次，远低于反爬最小延迟（10 秒），触发闲鱼反爬封�?

- 🆕v4.38【强制�?*B-REVIEW-182：ASYNC-AWAIT-SYNC-CHECK async/await 同步性静态检�?*
  - 维度�? 异步与调度器
  - 严重等级：critical（P0，Python 3.14 兼容性风险）
  - 规范引用：meta-rule #57 async/await 同步性静态检�?
  - **检查点**：`async def` 方法体内若不�?`await` 表达式，必须改为同步 `def`；调用点同步移除 `await`
  - **检查项**�?
    1. 所�?`async def` 方法必须检查方法体内是否含 `await` 表达式，�?`await` 则改�?`def`
    2. 方法�?`async def` 改为 `def` 后，所有调用点必须同步移除 `await`
    3. 白名单豁免：`@abstractmethod` 纯接口定义、`__aenter__`/`__aexit__` 上下文管理器、async generator（含 `yield`）可保留 `async def` �?`await`
    4. 推荐�?AST 分析而非正则，准确识别方法体内是否含 `await` 节点
  - **判断信号**�?
    - `grep "async def" <file>` 后检查方法体内是否含 `await`
    - `grep "await self._finalize_run\|await self._simple_method" <file>` 但方法体全同�?�?违规
    - 方法�?async 改为 sync �?`grep "await <method_name>"` 仍有命中 �?调用点未同步
  - **反模�?*�?
    ```python
    # async def 方法体全同步，Python 3.14 优化后返�?None，await None 触发 TypeError
    async def _finalize_run(self, stats):
        self._stats = stats
        self._persist_to_db(stats)

    # 调用点仍�?await
    await self._finalize_run(stats)  # TypeError in Python 3.14
    ```
  - **正确模式**�?
    ```python
    # 改为同步 def
    def _finalize_run(self, stats):
        self._stats = stats
        self._persist_to_db(stats)

    # 调用点同步移�?await
    self._finalize_run(stats)
    ```
  - **配置参数**：`meta_rules_57_63.async_await_check.enabled`（默�?true）、`meta_rules_57_63.async_await_check.severity`（默�?CRITICAL）、`meta_rules_57_63.async_await_check.whitelist_decorators`（默�?`["@abstractmethod", "__aenter__", "__aexit__"]`）、`meta_rules_57_63.async_await_check.use_ast_analysis`（默�?true）在 `config.yaml` �?`meta_rules_57_63.async_await_check` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #57
  - **适用**：Python 3.11+ 异步代码；使�?asyncio �?FastAPI/uvicorn 项目；含 `async def` �?worker/scheduler/service �?
  - **不适用**：纯接口定义（`@abstractmethod`）；上下文管理器；async generator；测试代码中�?`async def test_*`
  - **历史教训**：`worker.py` �?`_finalize_run` 标记�?`async def` 但方法体全同步，Python 3.14 优化后返�?None，`await None` 触发 TypeError 导致调度器崩溃。同期发�?3 处类似问题（`_save_progress` / `_update_status` / `_notify_done`），均改为同�?

- 🆕v4.38【强制�?*B-REVIEW-183：RESOURCE-POOL-BENCHMARK 资源池配置性能基准**
  - 维度�?5 数据�?/ 16 性能
  - 严重等级：major（P1，NullPool 导致每次连接执行 PRAGMA 开销 ~100ms�?
  - 规范引用：meta-rule #58 资源池配置性能基准与决�?
  - **检查点**：资源池配置（`poolclass=NullPool`/`QueuePool`/`StaticPool`）必须有性能基准数据支持，docstring 记录选择理由与对比数�?
  - **检查项**�?
    1. 资源池选择必须有性能基准数据支持，记�?NullPool vs QueuePool"的连接建�?复用/销毁开销对比
    2. 资源池配置代码必须有 docstring 说明选择理由、对比数据、适用场景
    3. 系统层开销（连接建�?+ PRAGMA + init SQL�? 50ms 时禁止用 NullPool
    4. 测试环境可用 StaticPool 但需 docstring 标注"仅测试用"
  - **判断信号**�?
    - `grep "poolclass=" <file>` �?docstring 说明 �?WARNING
    - `grep "poolclass=NullPool" <file>` 但无性能基准 docstring �?违规
    - 慢查询日志中系统层开销 > 50ms 且使�?NullPool �?CRITICAL
  - **反模�?*�?
    ```python
    # �?docstring 说明，生产环境用 NullPool 每次连接执行 PRAGMA 开销 ~100ms
    engine = create_engine("sqlite:///data/xianyu.db", poolclass=NullPool)
    ```
  - **正确模式**�?
    ```python
    # QueuePool 复用连接，性能提升 10-50x；docstring 记录选择理由
    engine = create_engine(
        "sqlite:///data/xianyu.db",
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
    )
    # 性能基准：NullPool 每次新建连接执行 PRAGMA 开销 ~100ms�?
    # QueuePool 复用连接�?list_and_count_task_links �?231ms 降至 11.9ms�?9x 提升�?
    ```
  - **配置参数**：`meta_rules_57_63.resource_pool_benchmark.enabled`（默�?true）、`meta_rules_57_63.resource_pool_benchmark.overhead_threshold_ms`（默�?50）、`meta_rules_57_63.resource_pool_benchmark.forbidden_pool_types_in_prod`（默�?`["NullPool", "StaticPool"]`）在 `config.yaml` �?`meta_rules_57_63.resource_pool_benchmark` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #58
  - **适用**：所有资源池选择；含 PRAGMA/init/重试开销的资源初始化；数据库连接池、HTTP 连接池、浏览器实例�?
  - **不适用**：测试环境（�?StaticPool 保证隔离）；单次请求资源；内存数据结构；CLI 一次性脚�?
  - **历史教训**：`db_models.py` 使用 `NullPool` 导致 `list_and_count_task_links` 慢查�?231ms（其�?~100ms �?PRAGMA 开销）。改�?`QueuePool(pool_size=5, max_overflow=5, pool_pre_ping=True)` 后降�?11.9ms�?9x 提升�?

- 🆕v4.38【强制�?*B-REVIEW-184：HTTP-STATUS-CODE-MAPPING HTTP 状态码精细化映�?*
  - 维度�?3 错误处理 / 7 API 契约
  - 严重等级：major（P1，多原因汇聚同一状态码导致用户无法区分错误类型�?
  - 规范引用：meta-rule #59 HTTP 状态码精细化映射表
  - **检查点**：底层模块返回多原因�?None/错误时，必须建立 `reason_code �?status_code` 映射表；底层设置 `last_*_failure_reason`；上游按映射查找状态码
  - **检查项**�?
    1. 底层模块返回 None 时必须设�?`self.last_*_failure_reason`，记录具体原�?
    2. 上游必须建立 `_FAILURE_STATUS_MAP = {reason_code: status_code}` 映射�?
    3. 未知 reason 用默认状态码（如 410），但必�?`logger.warning` 记录未知 reason
    4. 前端按状态码提供本地化消息，禁止 `detail.includes(...)` substring 判断
  - **判断信号**�?
    - `grep "raise HTTPException(410\|raise HTTPException(502" <file>` 多原因汇聚同一�?�?WARNING
    - `grep "last_.*_failure_reason" <file>` �?`grep "is None" <file>` 配对检�?
    - `grep "_FAILURE_STATUS_MAP\|_STATUS_MAP" <file>` 无映射表 �?违规
  - **反模�?*�?
    ```python
    # 多原因汇聚同一状态码，用户无法区分错误类�?
    if detail is None:
        raise HTTPException(status_code=410, detail="商品详情页加载失败或已下�?)
    # 实际原因可能�?cookie 过期（应 403）、反爬（�?429）、网络超时（�?504�?
    ```
  - **正确模式**�?
    ```python
    # 底层设置具体失败原因
    class DetailParser:
        def parse(self, html):
            if not html:
                self.last_detail_failure_reason = "network_timeout"
                return None
            # ...

    # 上游建立映射�?
    _DETAIL_FAILURE_STATUS_MAP = {
        "home_title_redirect": 403,
        "login_redirect": 403,
        "verify_redirect": 441,
        "item_not_found": 410,
        "item_removed": 410,
        "anti_crawler": 429,
        "network_timeout": 504,
    }

    if detail is None:
        reason = parser.last_detail_failure_reason or "unknown"
        status = _DETAIL_FAILURE_STATUS_MAP.get(reason, 410)
        if reason not in _DETAIL_FAILURE_STATUS_MAP:
            logger.warning(f"未知 detail failure reason: {reason}")
        raise HTTPException(status_code=status, detail=f"detail failed: {reason}")
    ```
  - **配置参数**：`meta_rules_57_63.http_status_code_mapping.enabled`（默�?true）、`meta_rules_57_63.http_status_code_mapping.default_status_code`（默�?410）、`meta_rules_57_63.http_status_code_mapping.require_reason_field`（默�?true）、`meta_rules_57_63.http_status_code_mapping.mapping_table_example`（含 7 �?reason_code �?status_code 示例）在 `config.yaml` �?`meta_rules_57_63.http_status_code_mapping` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #59
  - **适用**：所�?HTTP 错误响应；多原因返回 None/错误的底层模块（�?detail() 返回 None �?10+ 原因�?
  - **不适用**：唯一原因的错误码（如 404 仅表示资源不存在）；内部异常不向用户暴露；健康检查端�?
  - **历史教训**：`collection_service.py` 将所�?`detail() is None` 映射�?410 Gone，用户看�?已下�?后误以为商品真的下架，实际重新登录后商品仍在。修复：建立映射�?+ 底层设置 failure_reason + 前端按状态码提供本地化消�?

- 🆕v4.38【强制�?*B-REVIEW-185：CSS-SELECTOR-FALLBACK CSS 选择器多级降�?*
  - 维度�?9 浏览器自动化
  - 严重等级：critical（P0，第三方网站改版即失效）
  - 规范引用：meta-rule #60 CSS 选择器多级降级策�?
  - **检查点**：依赖第三方网站 DOM 的选择器必须有 �? 级降级（业务语义 className �?HTML role 属�?�?文本内容前缀扫描）；dump 触发条件收窄到核心字段失�?
  - **检查项**�?
    1. 选择器必须按"业务语义 className �?HTML role 属�?�?文本内容前缀扫描"顺序尝试，每级失败自动降�?
    2. 调试 dump 仅在核心字段（如 `on_sale`）失败时触发，非核心字段（如 `sold`）失败不 dump
    3. 所�?selector 字符串在 `config.yaml` 管理，禁止硬编码
    4. �?selector 尝试的中间步�?DEBUG 化，最终失�?WARNING
  - **判断信号**�?
    - `grep "querySelectorAll\|querySelector" <file>` 选择器单一�?fallback �?CRITICAL
    - `grep "tabItem\|tab.*class.*tab" <file>` �?`try/except` �?`or []` fallback �?违规
    - `grep "dump.*html\|page.content" <file>` 触发条件含非核心字段 �?WARNING
  - **反模�?*�?
    ```python
    # 单一选择器无 fallback，改版后 on_sale=0 sold=0 误报
    tabs = page.querySelectorAll('[class*="tabItem"]')
    # dump 触发条件含非核心字段（sold），导致 12 小时累积 500+ dump 文件
    if on_sale == 0 or sold == 0:
        self._dump_html(page)
    ```
  - **正确模式**�?
    ```python
    # 三级降级：业�?className �?role 属�?�?文本前缀扫描
    tabs = (
        page.querySelectorAll('[class*="tabItem"]')
        or page.querySelectorAll('[class*="tab"][role="tab"]')
        or self._scan_text_prefix(page, prefix_texts=["在售", "已售"])
    )
    # dump 仅在核心字段 on_sale 失败时触�?
    if on_sale == 0:
        self._dump_html(page)
    ```
  - **配置参数**：`meta_rules_57_63.css_selector_fallback.enabled`（默�?true）、`meta_rules_57_63.css_selector_fallback.min_fallback_levels`（默�?3）、`meta_rules_57_63.css_selector_fallback.dump_trigger_fields`（默�?`["on_sale"]`）、`meta_rules_57_63.css_selector_fallback.dump_max_per_hour`（默�?10）在 `config.yaml` �?`meta_rules_57_63.css_selector_fallback` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #60
  - **适用**：第三方网站 DOM 解析（闲�?淘宝/天猫/京东）；依赖 className 的选择器；Playwright `page.querySelectorAll` 返回值解�?
  - **不适用**：自有代�?DOM；ID 选择器；`data-*` 属性选择器；后端 API JSON 解析；SSR 页面
  - **历史教训**：`_detail.py` �?`_parse_sale_counts_from_tabs` 仅依�?`tabItem` class 名，闲鱼页面 DOM 结构变化后失效。dump 触发条件 `on_sale==0 or sold==0` 导致 12 小时内累�?500+ dump 文件。修复：三级 fallback + 收紧 dump 触发条件�?`on_sale==0`

- 🆕v4.38【强制�?*B-REVIEW-186：EXCEPTION-LOG-SEMANTIC 异常日志语义保留**
  - 维度�?3 错误处理
  - 严重等级：critical（P0，丢�?traceback 导致问题定位耗时 30+ 分钟�?
  - 规范引用：meta-rule #61 异常日志语义保留规范
  - **检查点**：`except` 块内必须�?`logger.exception('描述')` 保留完整 traceback，禁�?`logger.warning(f'...{e}')` 丢失堆栈
  - **检查项**�?
    1. `except` 块内必须�?`logger.exception("描述")` 自动保留完整 traceback
    2. 禁止 `except` 块内 `logger.warning(f"操作失败: {e}")`（仅打印异常对象，丢失堆栈）
    3. �?except 块需记录异常信息时用 `logger.warning("描述", exc_info=True)`
    4. 多阶段降级链合并为单条结构化 WARNING（参�?meta-rule #32�?
  - **判断信号**�?
    - `grep "logger.warning.*f\".*{e}\"" <file>` �?`grep "logger.exception.*f\"" <file>` �?except 块内 �?违规
    - `grep "except.*as e:" <file>` 后跟 `logger.warning\|logger.error` 但无 `logger.exception` �?违规
  - **反模�?*�?
    ```python
    # except 块内�?logger.warning 丢失 traceback，定位耗时 30+ 分钟
    try:
        result = await self._fetch_detail(item_id)
    except Exception as e:
        logger.warning(f"获取详情失败: {e}")  # 仅打印异常对象，丢失堆栈
    ```
  - **正确模式**�?
    ```python
    # logger.exception 自动保留完整 traceback
    try:
        result = await self._fetch_detail(item_id)
    except Exception:
        logger.exception(f"获取详情失败, item_id={item_id}")
    ```
  - **配置参数**：`meta_rules_57_63.exception_log_semantic.enabled`（默�?true）、`meta_rules_57_63.exception_log_semantic.forbidden_patterns`（默�?`["logger.warning.*f\".*{e}\"", "logger.error.*f\".*{e}\""]`）、`meta_rules_57_63.exception_log_semantic.required_pattern`（默�?`"logger.exception"`）、`meta_rules_57_63.exception_log_semantic.critical_path_functions`（默�?`["_on_startup", "run_migrations", "_init_db", "_init_scheduler"]`）在 `config.yaml` �?`meta_rules_57_63.exception_log_semantic` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #61
  - **适用**：所有异常处理代码；关键路径（启�?迁移/初始化）；多阶段降级链路；后台任务异常处理；API 路由异常处理
  - **不适用**：纯性能日志；DEBUG 级别日志；非 except 块的 warning（用 exc_info=True）；测试代码
  - **历史教训**：关键路径用 `logger.warning(f"操作失败: {e}")` 丢失 traceback，排查问题只能看到异常消息但无法定位行号，定位耗时 30+ 分钟。修复后定位时间缩短�?5 分钟。同期发�?15+ 处类似问�?

- 🆕v4.38【强制�?*B-REVIEW-187：EXTERNAL-RESOURCE-LIFECYCLE 外部资源生命周期配对**
  - 维度�? 异步与调度器 / 19 浏览器自动化
  - 严重等级：critical（P0，并发采集时 page 被误关导�?TargetClosedError�?
  - 规范引用：meta-rule #62 外部资源生命周期配对管理
  - **检查点**：外部传入的资源（Page/Connection/Lock）必须配对调�?`register`/`unregister`，且�?`finally` �?`unregister` 避免泄漏
  - **检查项**�?
    1. 外部传入资源必须调用 `register_external_page(page)` 注册，使用完毕在 `finally` 块调�?`unregister_external_page(page)` 注销
    2. `unregister` 必须�?`finally` 块中调用，确保异常时也能注销
    3. 并发采集时，资源不被主流程误关（通过 register 标记"资源正在使用"�?
    4. `register` 时引用计�?+1，`unregister` �?-1，计数为 0 时才允许关闭资源
  - **判断信号**�?
    - `grep "reuse_page\|external_page\|register_external" <file>` 后检查是否配�?register/unregister
    - `grep "def.*page.*Page" <file>` 参数�?Page 但无 `register_external_page` �?违规
    - `grep "register_external_page" <file>` 但无 `finally.*unregister` �?配对缺失
  - **反模�?*�?
    ```python
    # 未注册外部传入的 page，主流程可能误关导致 TargetClosedError
    async def collect_items(self, page: Page, item_ids):
        for item_id in item_ids:
            await self._collect_one(page, item_id)
    # 主流�?_cleanup_idle_pages 检测到 page 空闲后关�?�?TargetClosedError
    ```
  - **正确模式**�?
    ```python
    # 入口 register + finally unregister + 引用计数管理
    async def collect_items(self, page: Page, item_ids):
        self._register_external_page(page)  # 引用计数 +1
        try:
            for item_id in item_ids:
                await self._collect_one(page, item_id)
        finally:
            self._unregister_external_page(page)  # 引用计数 -1，为 0 才允许关�?
    ```
  - **配置参数**：`meta_rules_57_63.external_resource_lifecycle.enabled`（默�?true）、`meta_rules_57_63.external_resource_lifecycle.resource_types`（默�?`["Page", "Connection", "Lock"]`）、`meta_rules_57_63.external_resource_lifecycle.require_finally_block`（默�?true）、`meta_rules_57_63.external_resource_lifecycle.use_reference_counting`（默�?true）在 `config.yaml` �?`meta_rules_57_63.external_resource_lifecycle` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #62
  - **适用**：外部资源传入（Page/Connection/Lock/SSE 连接）；并发采集场景；Playwright Page 共享；跨函数/跨模块资源传�?
  - **不适用**：内部创建的资源；单线程使用；一次性资源；`with` 语句管理的资�?
  - **历史教训**：`collection_service.py` 接收外部传入�?`page` 但未调用 `register_external_page`，并发采集时主流�?`_cleanup_idle_pages` 检测到 page 空闲后关闭，导致 `TargetClosedError`。修复：入口 register + finally unregister + 引用计数判断

- 🆕v4.38【强制�?*B-REVIEW-188：DB-WRITE-IDENTITY-TRACE 数据库写入身份追�?*
  - 维度�?5 数据�?/ 5 安全
  - 严重等级：major（P1，跨用户写入风险 + converter TypeError�?
  - 规范引用：meta-rule #63 数据库写入函数身份追溯与类型安全
  - **检查点**：数据库写入函数必须�?`user_id` 参数用于跨用户隔离；converter 函数处理 `re.Match` 对象必须显式调用 `m.group(1)` 再转型，禁用 `int(m)`
  - **检查项**�?
    1. 所有数据库写入函数（`upsert_*` / `insert_*` / `update_*` / `create_*`）必须含 `user_id: str` 参数
    2. 写入 SQL �?WHERE 子句必须�?`user_id` 条件，禁止跨用户写入
    3. 正则 converter 函数处理 `re.Match` 对象必须显式调用 `m.group(1)` 获取字符串再转型（`int(m.group(1))`），禁用 `int(m)`
    4. Pydantic 模型入口已校验的函数可豁�?user_id（但需注释标注"入口已校�?�?
  - **判断信号**�?
    - `grep "def upsert_\|def insert_\|def update_\|def create_" <file>` �?`user_id` 参数 �?WARNING
    - `grep "lambda m: int" <file>` �?`group(1)` �?CRITICAL
    - `grep "WHERE.*task_id" <file>` 但无 `AND user_id` �?WARNING
  - **反模�?*�?
    ```python
    # 反模�?1：缺 user_id 参数，跨用户写入风险
    def upsert_eval_event(event: EventRow):
        session.execute(text("INSERT INTO evaluations (task_id, score) VALUES (...)"))

    # 反模�?2：converter 函数直接�?re.Match 调用 int()，TypeError
    _SELLER_LABEL_PATTERNS = {
        "follower_count": (re.compile(r"关注(\d+)"), lambda m: int(m)),
    }
    # TypeError: int() argument must be a string, not 're.Match'
    ```
  - **正确模式**�?
    ```python
    # 正确模式 1：写入函数含 user_id 参数，WHERE 子句�?user_id 条件
    def upsert_eval_event(event: EventRow, user_id: str):
        session.execute(text(
            "INSERT INTO evaluations (task_id, user_id, score) VALUES (:task_id, :user_id, :score)"
        ), {"task_id": event.task_id, "user_id": user_id, "score": event.score})

    # 正确模式 2：converter 显式调用 m.group(1) 获取字符串再转型
    _SELLER_LABEL_PATTERNS = {
        "follower_count": (re.compile(r"关注(\d+)"), lambda m: int(m.group(1))),
    }
    ```
  - **配置参数**：`meta_rules_57_63.db_write_identity_trace.enabled`（默�?true）、`meta_rules_57_63.db_write_identity_trace.required_param_name`（默�?`"user_id"`）、`meta_rules_57_63.db_write_identity_trace.function_name_patterns`（默�?`["def upsert_", "def insert_", "def update_", "def create_"]`）、`meta_rules_57_63.db_write_identity_trace.forbidden_converter_patterns`（默�?`["lambda m: int(m)", "lambda m: float(m)"]`）在 `config.yaml` �?`meta_rules_57_63.db_write_identity_trace` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #63
  - **适用**：所有数据库写入函数；正�?converter 函数；跨用户系统；含 `re.findall` + converter 的解析逻辑
  - **不适用**：系统级写入（日志表/统计�?全局配置表）；单一调用点的函数；Pydantic 入口校验后的函数；纯查询函数
  - **历史教训**：`_SELLER_LABEL_PATTERNS` �?converter `lambda m: int(m)` �?`int() argument must be a string, not 're.Match'`。修复：改为 `lambda m: int(m.group(1))`。同期发�?`upsert_eval_event` �?`user_id` 参数导致跨用户写入风�?

- 🆕v4.40【强制�?*B-REVIEW-189：BUSINESS-STATUS-CODE-CONFLICT 业务异常状态码冲突检�?*
  - 维度�?3 错误处理 / 7 API 契约
  - 严重等级：critical（P0，业�?401 与认�?401 冲突导致前端误跳转登录页，破坏用户工作流�?
  - 规范引用：meta-rule #66 状态码分层所有权与冲突避�?
  - **�?B-REVIEW-184 的关�?*�?
    - B-REVIEW-184 关注「多原因 None �?状态码映射」（同层内多原因细分，对�?meta-rule #59�?
    - B-REVIEW-189 关注「同一状态码跨层语义冲突」（层间所有权划分，对�?meta-rule #66�?
    - 两者互补，不重�?
  - **检查点**：业务代码（CollectionError / HTTPException）禁止抛出认证层专属状态码；同一语义在不同业务模式必须使用相同状态码；路由透传需确保上游不抛认证层专属状态码
  - **检查项**�?
    1. 业务代码禁止抛出 `status_code_audit.forbidden_business_codes` 中定义的状态码�?01/403�?
    2. 认证层专属状态码（`reserved_for_middleware`）仅认证中间件可返回
    3. 同一语义（如 cookie_expired）在不同业务模式（detail-only/official-full）必须使�?`consistency_rules` 中定义的相同状态码
    4. 路由透传 CollectionError 时需通过单元测试覆盖确保上游不会抛出认证层专属状态码
  - **判断信号**�?
    - `grep "CollectionError(401" <file>` 命中 �?违反状态码所有权
    - `grep "raise HTTPException(status_code=401" <file>` 命中（非认证中间件）�?违反状态码所有权
    - 同一异常类在不同方法抛出不同状态码但语义相�?�?违反一致�?
  - **反模�?*�?
    ```python
    # 反模�?1：业务代码抛出认证层专属状态码 401
    raise CollectionError(401, "采集失败：闲鱼登录态失�?, item_id=item_id)
    # 前端 axios 拦截器把所�?401 当认证失效，跳转登录�?

    # 反模�?2：同一语义在不同模式使用不同状态码
    # _collect_detail_only
    raise CollectionError(401, "cookie 失效", item_id=item_id)
    # _collect_official_full
    raise CollectionError(440, "cookie 失效", item_id=item_id)

    # 反模�?3：路由无条件透传状态码，未校验是否属于认证�?
    except CollectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    ```
  - **正确模式**�?
    ```python
    # 正确模式 1：外部凭证失效使�?440 状态码
    raise CollectionError(440, "采集失败：闲鱼登录态失�?, item_id=item_id)

    # 正确模式 2：两种模式统一使用 440
    raise CollectionError(440, "cookie 失效", item_id=item_id)

    # 正确模式 3：通过单元测试覆盖 CollectionError 不抛�?401/403
    @pytest.mark.parametrize("status_code", [401, 403])
    def test_collection_error_not_use_auth_codes(status_code):
        with pytest.raises(AssertionError):
            CollectionError(status_code, "test")
    ```
  - **配置参数**：`status_code_audit.layers`�? 个层的所有权定义：auth/external_cred/validation/anti_crawler/not_found/server_error）、`status_code_audit.reserved_for_middleware`（默�?`[401]`）、`status_code_audit.forbidden_business_codes`（默�?`[401, 403]`）、`status_code_audit.consistency_rules`（一致性规则数组，applies_to 为数组可扩展）、`status_code_audit.detection_patterns`（grep 静态扫描模式：business_forbidden_in_raise / route_transparent_pass）在 `config.yaml` �?`status_code_audit` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.40.0 meta-rule #66
  - **适用**：所�?HTTP API 后端业务异常处理；多模式业务（如 detail-only/official-full 采集模式）共享同一异常类；FastAPI/Flask 等使�?HTTPException 的框架；带全局响应拦截器的前端应用后端配套
  - **不适用**：无认证的内部接口；纯参数校验（422 �?FastAPI 自动处理）；测试 mock（可自由返回任意状态码）；完全独立的服务（无状态码透传链路�?
  - **修复建议**：外部凭证失�?�?440；反爬限�?�?429；商品下�?页面不可�?�?410；浏览器异常 �?502
  - **历史教训**：`collection_service.py` 3 �?`CollectionError(401, ...)` 抛出认证层专属状态码，前�?axios 拦截器把所�?401 当作认证失效跳转登录页。修复：3 �?`CollectionError(401, ...)` �?`CollectionError(440, ...)`（与 official-full 模式一致），前端拦截器改为只对 `detail === 'Unauthorized'` 跳转登录�?

### B-REVIEW-226 ASYNC-BLOCKING-CALL-TIMEOUT async �������ó�ʱ����

- **������**��B-REVIEW-226 ASYNC-BLOCKING-CALL-TIMEOUT
- **�淶����**�����п������ù���� async API��Playwright `context.cookies()` / `bc.storage_state()` / `page.snapshot()` / `page.title()` / `page.url()` / `page.evaluate()`��httpx �����ӡ�aiohttp websocket�������� `asyncio.wait_for(coro, timeout=...)` ������ʱ����ʱֵ�����óɱ����ࣨlightweight_read / heavy_serialize / evaluate���� `config.yaml` �� `async_timeout_protection.timeout_by_category` ��ȡ����ֹӲ���롣
- **�ж��ź�**��`grep -nP "await\s+\w+\.(cookies|storage_state|snapshot|title|url|evaluate)\("` �������� `asyncio.wait_for` ���� �� Υ�档
- **���ò���**��`async_timeout_protection.enabled` / `async_timeout_protection.timeout_by_category.{lightweight_read,heavy_serialize,evaluate}` / `async_timeout_protection.fallback_strategy` / `async_timeout_protection.audit_grep_pattern`���� `config.yaml` �� `async_timeout_protection` �ڵ�����
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.48.0 meta-rule #80��
- **����**��Playwright async API ���ã�cookies/storage_state/snapshot/title/url/evaluate����httpx �����ӳص��ã�aiohttp websocket �����ӣ������� IPC ���������������δ��Ӧ����������Ӧ�����ù���� async ���á�
- **������**��Playwright �Դ� `timeout` �����ĵ��ã�`page.goto(timeout=...)` / `wait_for_load_state(timeout=...)`�����ڽ���ʱ����ͬ�� API ���ã�һ���Ե�����ʧ�ܼ���ֹ�ĳ�����������ڳ�ʼ�����ϲ����ܳ�ʱ������������ async �������� I/O �������գ���
- **��ʷ��ѵ**��`scripts/browser_login.py` ��¼�ɹ��� Cookie �����׶� `await context.cookies()` �� `await bc.storage_state()` δ�� `asyncio.wait_for`��Playwright IPC ����������̿���ʱ�����������ӽ�������ͣ�ͣ���� 90s �����п����� kill �ӽ��̣������ѵ�¼�ɹ��� Cookie ��ʧ���޸������� Playwright ���� API ����ͳһ�� `asyncio.wait_for(coro, timeout=config.async_timeout_protection.timeout_by_category.heavy_serialize)` ��������ʱ�󴥷� fallback��best_effort ���ؿ� cookies + �澯����

### B-REVIEW-227 SUBPROCESS-HEARTBEAT-STAGE-COORDINATION �ӽ���������׶γ�ʱЭͬ

- **������**��B-REVIEW-227 SUBPROCESS-HEARTBEAT-STAGE-COORDINATION
- **�淶����**��`subprocess.Popen` + status file �����ܹ��У�ÿ�׶α��붨����� status �ַ�����starting/opening/running/waiting/already_logged �ȣ�+ ������ʱ��ֵ���� `config.yaml` �� `subprocess_heartbeat.timeout_by_status` ��ȡ����ֹӲ���� 90s�����׶��������������ó�ʱ֮�ͱ��� `< ������ֵ * (1 - safety_margin)`�������˻��ڽ׶�δ���ʱ���п�����
- **�ж��ź�**��ͬ�ļ�ͬʱ���� `grep "subprocess.Popen"` + `grep "status_file"`���� status file д���߼����� �����ü��㣻��һ�����ÿ�׶� status �볬ʱ��ֵ�ĸ��������ԡ��ۼƳ�ʱ��������ֵ��������
- **���ò���**��`subprocess_heartbeat.enabled` / `subprocess_heartbeat.timeout_by_status.{starting,opening,running,waiting,already_logged}` / `subprocess_heartbeat.safety_margin`��Ĭ�� 0.3�����׶γ�ʱ֮�Ͳ�����������ֵ�� 70%��/ `subprocess_heartbeat.max_accumulated_timeout_warn`���� `config.yaml` �� `subprocess_heartbeat` �ڵ�����
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.48.0 meta-rule #81��
- **����**��`subprocess.Popen` + status file �����ܹ����� `scripts/browser_login.py` �������¼�ӽ��̣�����׶γ�ʱ�����񣨵�¼ �� ���� �� �ɼ����������ѯǰ�� status file �ж���ʱ�ĳ�����
- **������**��ͬ������-��Ӧģʽ��FastAPI ·��ֱ�� `await`���޶����ӽ��̣�����̨һ�����������������ƣ�����ǰ��״̬������޺����ѯ����ͬ����Э�̵��ȣ��� IPC ���գ���
- **��ʷ��ѵ**���������¼�ӽ��̽����嵥һ `running` status + ��һ 90s ��ֵ����ʵ�ʽ׶ΰ��� `starting`�������������� `opening`���򿪵�¼ҳ���� `running`���ȴ��û���¼���� `already_logged`������ Cookie�������� `already_logged` �׶ε��� `context.cookies()` + `storage_state()` �ۼ� IPC ��ʱ�ɴ� 60s��������������� GC ��ͣ�󳬹� 90s ������ֵ����������ӽ��̿����� kill����ʧ�ѵ�¼̬���޸���ÿ�׶ζ��� status + ������ֵ��`starting/opening/running/already_logged` �� 90s��`waiting` 30s�����׶������������ۼƳ�ʱ < 90 * (1 - 0.3) = 63s��

### B-REVIEW-228 CROSS-BLOCK-CONSISTENCY-CHECK ������һ���Լ��

- **������**��B-REVIEW-228 CROSS-BLOCK-CONSISTENCY-CHECK
- **�淶����**��ͬһ API���� `context.cookies()` / `storage_state()` / `page.goto()`���� �� `consistency_check.min_occurrences`��Ĭ�� 2��������ʱ��������ʩ����ʱ���� / �쳣���� / fallback ����ֵ������һ�£��Ը��ϸ���Ϊ׼������һ���� `asyncio.wait_for` ����һ���ޣ����ж��޳�ʱ������Υ�棬���벹�������ϸ�һ�£���
- **�ж��ź�**��ɨ�� `consistency_check.scan_paths` �г����ļ�����ͬһ API ������ �� `min_occurrences` �εĵ��õ���б�����ʩ�Աȣ���һ�¼�����Υ�档
- **���ò���**��`consistency_check.enabled` / `consistency_check.min_occurrences`��Ĭ�� 2��/ `consistency_check.scan_paths`��Ĭ�ϸ��� `scripts/browser_login.py` / `scripts/auth_helper.py` / `src/xianyu_hunter/infra/browser.py` / `src/xianyu_hunter/modules/worker.py` / `src/xianyu_hunter/modules/collector/_search.py`������ `config.yaml` �� `consistency_check` �ڵ�����
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.48.0 meta-rule #82��experimental����
- **����**��ͬһ API �ڶദ���õĳ�����������¼��ڶ����� `storage_state()`�������ô���Ƭ�Σ������¼��ʽ���� Cookie �����߼������ع������Ƿ�©�ģ����ֵ��õ��Ѽӱ�����ʣ��δ�ӣ���
- **������**���״�ʵ�ֵ�Ψһ���õ㣨�޶Աȶ��󣩣�������컯��ʵ�֣����� stub vs �������룬���Կ�ʡ�Գ�ʱ������ͬ��ܵ����Ʋ�����Playwright `page.goto()` vs httpx `client.get()`�����岻ͬ���ɱȣ���
- **��ʷ��ѵ**��`scripts/browser_login.py` �� `storage_state()` ���õ� A������¼���̣��� `asyncio.wait_for` ���������õ� B���ѵ�¼���ٵ���·�����ޱ��������� B ·��ż�� IPC ����ʱ�޳�ʱ���ף������� B-REVIEW-226 ���޸������⡣�޸���ɨ������ `storage_state()` ���õ㣬ͳһ���� `asyncio.wait_for` ���� A һ�¡��ü����� B-REVIEW-226 �ĺ��򲹳䣨226 ��ע�������Ƿ�ӳ�ʱ����228 ��ע����㱣���Ƿ�һ�¡�����

### B-REVIEW-229 MONKEYPATCH-FROM-IMPORT-COVERAGE monkeypatch ģ�鼶 from-import ����������

- **������**��B-REVIEW-229 MONKEYPATCH-FROM-IMPORT-COVERAGE
- **�淶����**�����Դ�����ʹ�� `monkeypatch.setattr` / `unittest.mock.patch` ʱ�����븲�Ǳ���������� `from X import Y` ��ģ�鼶���ã���ֹֻ patch Դģ��·���������� FastAPI ����ע�루`Depends`����д�Ա��� patch ɢ�㡣
- **�ж��ź�**��`grep -nP "monkeypatch\.setattr\(|patch\(['\"][^'\"]+\.\w+['\"]"` ���в��Դ��� �� ��鱻������Ƿ���ڶ�Ӧ�� `from X import Y`������ڵ�δ patch ����ģ������� �� Υ�档
- **���ò���**��`test_quality_protection.monkeypatch_coverage.enabled` / `test_quality_protection.monkeypatch_coverage.severity`��Ĭ�� CRITICAL��/ `test_quality_protection.monkeypatch_coverage.detection_patterns` / `test_quality_protection.monkeypatch_coverage.forbidden_partial_patch` / `test_quality_protection.monkeypatch_coverage.recommended_strategies`���� `config.yaml` �� `test_quality_protection.monkeypatch_coverage` �ڵ�����
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.49.1 step 236��
- **����**�����Դ���ʹ�� `monkeypatch.setattr` / `unittest.mock.patch` �ұ�����뺬ģ�鼶 `from-import` ���ã�async service ������ patch ���������ĳ�����
- **������**�����������ԣ����ⲿ�������룩��FastAPI Depends �ѷ�װ������������ fixture ��ͳһ����ĳ�����
- **��ʷ��ѵ**�����Դ��� `patch("xianyu_hunter.core.auth_helper.is_token_valid")` ֻ patch Դģ�飬��������� `from xianyu_hunter.core.auth_helper import is_token_valid` �Ѱ󶨱������ã�patch ����Ч������ͨ���������Ա�����޸���(1) ������ FastAPI ����ע����д��(2) ��һ patch ��������ģ������á�

### B-REVIEW-230 ASYNC-SYNC-TEST-CALL-MATCH ͬ��/�첽�������Ե���ƥ��

- **������**��B-REVIEW-230 ASYNC-SYNC-TEST-CALL-MATCH
- **�淶����**�����Ե� `await` ���ñ����뷽���� `async/sync` ����ƥ�䣻�����ⷽ�����ع�Ϊͬ��ʱ���Ա����Ƴ� `await`��mock ���ͱ����� `MagicMock` ����ͬ��ʵ�֣��� `AsyncMock` �����첽ʵ�֡�
- **�ж��ź�**���������б��� `TypeError: 'NoneType' object can't be awaited` / `TypeError: 'bool' object can't be awaited` / `coroutine '...' was never awaited` / `RuntimeWarning: coroutine '...' was never awaited` �� Υ�档
- **���ò���**��`test_quality_protection.async_sync_test_match.enabled` / `test_quality_protection.async_sync_test_match.severity`��Ĭ�� CRITICAL��/ `test_quality_protection.async_sync_test_match.error_signatures` / `test_quality_protection.async_sync_test_match.mock_type_alignment`���� sync_implementation=MagicMock��async_implementation=AsyncMock��refactoring_swap_required=true��/ `test_quality_protection.async_sync_test_match.detection_patterns`���� `config.yaml` �� `test_quality_protection.async_sync_test_match` �ڵ�����
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.49.1 step 237��
- **����**��FastAPI async �˵���ԣ�async service ���ԣ�async?sync �ع���Ļع���ԡ�
- **������**����ͬ��������ԣ��� await������ async ������ mock �Ѷ��롣
- **��ʷ��ѵ**�����ⷽ�� `_finalize_run` �� `async def` �ع�Ϊ `def` �������� `await self._finalize_run(...)`��Python 3.14 �Ż��󷵻� None��await None ���� `TypeError: object NoneType can't be used in 'await' expression`���޸����� `async def` ��Ϊͬ�� `def`�����õ�ͬ���Ƴ� `await`��mock ���ʹ� `AsyncMock` �л�Ϊ `MagicMock`��

### B-REVIEW-231 PROPERTY-RENAME-SERIALIZE-FIELD-SEP �������ع������л��ֶ�������

- **������**��B-REVIEW-231 PROPERTY-RENAME-SERIALIZE-FIELD-SEP
- **�淶����**���������������ع����շ�����Σ�ʱ���Ա���ͬ�������������Է��ʣ����л�������`to_dict` / `model_dump`�����뱣��Э���ֶ������� `appKey` / `userId` / `presetId`�����������������ع��ƻ�ǰ�����Լ��
- **�ж��ź�**���������б��� `AttributeError: ... has no attribute 'appKey'` / `AttributeError: ... has no attribute 'userId'` / `TypeError: ... unexpected keyword argument 'appKey'` �� Υ�档
- **���ò���**��`test_quality_protection.property_rename_serialize.enabled` / `test_quality_protection.property_rename_serialize.severity`��Ĭ�� CRITICAL��/ `test_quality_protection.property_rename_serialize.attribute_error_signatures` / `test_quality_protection.property_rename_serialize.type_error_signatures` / `test_quality_protection.property_rename_serialize.serialization_field_retention`���� require_protocol_field=true��mapping_example��/ `test_quality_protection.property_rename_serialize.test_sync_required` / `test_quality_protection.property_rename_serialize.detection_patterns`���� `config.yaml` �� `test_quality_protection.property_rename_serialize` �ڵ�����
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.49.1 step 238��
- **����**��dataclass / pydantic ģ���������ع����շ�����Σ����� `to_dict` / `model_dump` ���л�������ģ�ͣ�ǰ���Э���ֶ���Լ��������
- **������**�����ڲ����ݽṹ�������л����󣩣�ORM ���ࣨ������������һ�£���
- **��ʷ��ѵ**���� `appKey` �ع�Ϊ `app_key` ������� `obj.appKey` ���ʱ� `AttributeError`���� `to_dict` ��� `app_key` ����Э��Լ���� `appKey`��ǰ�˽���ʧ�ܡ��޸���(1) ���Ը������������� `obj.app_key`��(2) `to_dict` �� `{"appKey": self.app_key}` ����Э���ֶ�����

### B-REVIEW-232 FASTAPI-ENDPOINT-SIGNATURE-TEST-SYNC FastAPI �˵�ǩ���������ͬ��

- **������**��B-REVIEW-232 FASTAPI-ENDPOINT-SIGNATURE-TEST-SYNC
- **�淶����**��FastAPI �˵�ǩ������ `request: Request` / `user_id: str` ����ʱ���Ա��봫���Ӧ���������ε��ö��Ա���������ǩ�������� mock Request �Ƽ��� `SimpleNamespace(state=SimpleNamespace(user_id=mock_user_id))` ���죬�������� `starlette.Request` ����������
- **�ж��ź�**���������б��� `TypeError: <endpoint>() missing 1 required positional argument: 'request'` / `missing 1 required positional argument: 'user_id'` �� Υ�档
- **���ò���**��`test_quality_protection.fastapi_endpoint_test_sync.enabled` / `test_quality_protection.fastapi_endpoint_test_sync.severity`��Ĭ�� CRITICAL��/ `test_quality_protection.fastapi_endpoint_test_sync.error_signatures` / `test_quality_protection.fastapi_endpoint_test_sync.request_mock_template`���� use_simplenamespace=true��construct_pattern��mock_user_id_default="default"��mock_state_fields��/ `test_quality_protection.fastapi_endpoint_test_sync.signature_change_patterns`���� `config.yaml` �� `test_quality_protection.fastapi_endpoint_test_sync` �ڵ�����
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.49.1 step 239��
- **����**��FastAPI �˵�ǩ������������`request` / `user_id` / `session_id`����Ĳ���ͬ�������ε��ö������䡣
- **������**��������У���ع���Pydantic ģ���ֶα������������ͨ�� fixture ע�� request �ĳ�����
- **��ʷ��ѵ**���˵�ǩ�� `async def list_items(task_id: str)` ���� `request: Request` �����󣬲��� `await list_items(task_id="t1")` �� `TypeError: list_items() missing 1 required positional argument: 'request'`���޸������Թ��� `mock_request = SimpleNamespace(state=SimpleNamespace(user_id="default"))` ���� `await list_items(task_id="t1", request=mock_request)`��

### B-REVIEW-233 SOFT-DELETE-CATEGORY-ISOLATION ��ɾ�����ݷ������

- **������**��B-REVIEW-233 SOFT-DELETE-CATEGORY-ISOLATION
- **�淶����**������ͳ�Ʊ������� NULL ������¶����ݣ����롸δ���ࡹ����ͳ�ƣ�����ɾ����������ָ��ķ����ѱ���ɾ��������ͳ�ƣ�����ֹ�ϲ��жϵ����������ݻ�Ϊһ�ࡣ
- **�ж��ź�**��`grep -nP "if\s+not\s+\w+\s+or\s+\w+\s+not\s+in"` ���з���ͳ�ƴ��루�� `if not tid or tid not in task_map`���� Υ�档
- **���ò���**��`soft_delete_data_isolation.enabled` / `soft_delete_data_isolation.severity`��Ĭ�� HIGH��/ `soft_delete_data_isolation.detection_patterns` / `soft_delete_data_isolation.classification_rules`���� orphan_rule: `if tid is None` ����δ���ࡢdeleted_rule: `if tid not in task_map` ����ͳ�ƣ�/ `soft_delete_data_isolation.foreign_key_fields`���� `config.yaml` �� `soft_delete_data_isolation` �ڵ�����
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.49.1 step 240��
- **����**������ɾ������ķ���ͳ�ƣ��ۺϲ�ѯ��������ࣻ`list_and_count` ��ӿڵ� dist ͳ�ơ�
- **������**��Ӳɾ�������CASCADE��������������Ĵ����ݱ������Ӳ�Ϊ NULL ��ǿԼ�����
- **��ʷ��ѵ**������ͳ�ƴ��� `if not tid or tid not in task_map: uncategorized += 1` �� NULL ������¶����ݣ�����ɾ�������Ӧ��������Ϊһ�࣬���¡�δ���ࡹ������ߡ��޸������Ϊ `if tid is None: uncategorized += 1`������δ���ࣩ�� `if tid not in task_map: continue`��������ɾ������

### B-REVIEW-234 ES-RESILIENCE-PRECHECK ES ����Ԥ�죨ɨ��ǰ��飩

- **������**��B-REVIEW-234 ES-RESILIENCE-PRECHECK
- **�淶����**��SonarQube ɨ��ǰ������ Elasticsearch `read_only_allow_delete` �������������� CE ���洦�� FAILED ��ɨ�����ݲ����£�ɨ��ǰ��ѯ `/_cluster/health`����⵽���� `PUT /_all/_settings` ������
- **�ж��ź�**��ɨ��ű��� `sonar-scanner` / `ce_task` / `compute_engine` ��ȱ�� ES ������� �� Υ�棻CE ���洦�� FAILED ����־�� `read_only_allow_delete` �� Υ�档
- **���ò���**��`es_resilience_precheck.enabled` / `es_resilience_precheck.severity`��Ĭ�� HIGH��/ `es_resilience_precheck.es_endpoint`���� host=localhost��port=9200��protocol=http��health_check_path=/_cluster/health��request_timeout_sec=5��/ `es_resilience_precheck.read_only_indicator`���� field_name=read_only_allow_delete��locked_value=true��/ `es_resilience_precheck.unlock_action`���� method=PUT��path=/_all/_settings��body��on_failure=warn_and_continue��/ `es_resilience_precheck.pre_scan_steps` / `es_resilience_precheck.detection_patterns`���� `config.yaml` �� `es_resilience_precheck` �ڵ��������� `sonarqube-mcp` `core_config.json` `es_resilience` �ڵ㡣
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.49.1 + `sonarqube-mcp` `core_config.json` `es_resilience` �ڵ㡣
- **����**��SonarQube ɨ��ǰ�� ES Ԥ�죻CE ���洦�� FAILED �ĸ����Ų飻ɨ�����ݲ����³�����
- **������**���� ES ��������Ŀ���� SonarQube ɨ�裻ES �������������ά�㴦���
- **��ʷ��ѵ**��SonarQube ɨ��� CE ���洦�� FAILED��ɨ�����ݲ����£�����Ϊ ES ����ˮλ���� `read_only_allow_delete` ����CE д�� ES ʧ�ܡ��޸���ɨ��ǰ��ѯ `http://localhost:9200/_cluster/health`����⵽ `read_only_allow_delete: true` �� `PUT /_all/_settings` `{"index.blocks.read_only_allow_delete": null}` ������

### B-REVIEW-235 PYTEST-TIMEOUT-CONFIG ���Գ�ʱ����

- **������**��B-REVIEW-235 PYTEST-TIMEOUT-CONFIG
- **�淶����**��`pyproject.toml` �������� `pytest-timeout` ��������� `--timeout=<N>`�����ģ���Ա���֧�ַ������У��� `max_tests_per_batch` ��ֵ�����������ⵥ�⿨���������� CI ��ʱ�������
- **�ж��ź�**��`pyproject.toml` �� `[tool.pytest.ini_options]` ȱ�� `--timeout` ���� / `requirements-dev.txt` ȱ�� `pytest-timeout` ���� �� Υ�档
- **���ò���**��`test_quality_protection.pytest_timeout_config.enabled` / `test_quality_protection.pytest_timeout_config.severity`��Ĭ�� HIGH��/ `test_quality_protection.pytest_timeout_config.required_plugin`��pytest-timeout��/ `test_quality_protection.pytest_timeout_config.default_timeout_sec`��Ĭ�� 30��/ `test_quality_protection.pytest_timeout_config.required_addopts`���� `--timeout=30`��`--timeout-method=thread`��/ `test_quality_protection.pytest_timeout_config.batch_run`���� enabled=true��max_tests_per_batch=200��batch_command_template��/ `test_quality_protection.pytest_timeout_config.detection_patterns`���� `config.yaml` �� `test_quality_protection.pytest_timeout_config` �ڵ�����
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.49.1 step 38��
- **����**��`pyproject.toml` ���� pytest ����Ŀ��CI/CD ��ˮ�߲��ԣ����ģ�����׼���
- **������**������Ԫ���ԣ�<10 ������һ���Խű����ԣ���ʹ�� pytest ����Ŀ��
- **��ʷ��ѵ**��CI ��ˮ�ߵ������Կ����� timeout ���ã����� CI ��ʱ 1 Сʱ��������޸���`pip install pytest-timeout`��`pyproject.toml` ���� `addopts = "--timeout=30 --timeout-method=thread"`���������� 200 ��������������С�

### B-REVIEW-236 MULTI-USER-ID-PROPAGATION ���û����� user_id ͸��һ����

- **������**��B-REVIEW-236 MULTI-USER-ID-PROPAGATION
- **�淶����**��FastAPI �˵�� `request.state.user_id` ��ȡ�û���ݺ󣬱������������� service / repository / external_api ��������ȷ���� `user_id` ��������ֹ�˵��ȡ���������û����ݳ���ͨ��Ĭ��ֵ `"default"` ���������ݡ�
- **�ж��ź�**���˵�ǩ���� `request: Request` ������ `service.create_xxx(...)` / `service.update_xxx(...)` ����δ���� `user_id` �� Υ�档
- **���ò���**��`multi_user_id_propagation.enabled` / `multi_user_id_propagation.severity`��Ĭ�� CRITICAL��/ `multi_user_id_propagation.user_id_source`���� extraction_pattern=request.state.user_id��default_value="default"��single_user_compat=true��/ `multi_user_id_propagation.propagation_check_patterns` / `multi_user_id_propagation.forbidden_patterns` / `multi_user_id_propagation.required_propagation_layers`��route/service/repository/external_api������ `config.yaml` �� `multi_user_id_propagation` �ڵ�����
- **��Ӧ����淶**���μ� `xianyu-hunter-dev` v4.49.1 step 243��
- **����**�����û�ϵͳ���� user_id ����� service / repository��FastAPI �˵� + �м���ܹ���
- **������**�����û�ϵͳ���� user_id �����ϵͳ���������� `_log_*` / `_stats_*`��������ѯ��д��Ľӿڡ�
- **��ʷ��ѵ**���˵� `async def upsert_eval(request: Request, ...)` ͨ�� `user_id = request.state.user_id` ��ȡ��ݣ������� `service.upsert_eval_event(event)` ʱδ���� `user_id`�����¿��û�����д���λ���޸����������η������� `user_id: str` ������͸�������û����ݳ��� `user_id: str = "default"`��

---

## 维度 37：隧道 path_prefix / scheme-aware Cookie / SPA 部署对齐 / 禁止硬编码 base path（meta-rules #111-#114 落地）🆕v4.68

### B-REVIEW-TUNNEL-PATH-PREFIX 隧道仅转发 path_prefix 作用域

- **规范名称**：B-REVIEW-TUNNEL-PATH-PREFIX
- **规范内容**：Tailscale Funnel 通过 `--set-path {path_prefix}` 仅暴露 `/xianyu/*` 作用域，裸根 `/` 由 Tailscale 默认路由返回 `404 page not found`。`path_prefix` 必须来自 `yaml_config.TunnelConfig.path_prefix`（默认 `/xianyu/`），禁止在 `tunnel_providers.py` 写死；后端 `@app.get("/")` 的 SPA 直出必须返回 index.html 不重定向，避免 funnel 下重定向循环。
- **判断信号**：`tunnel_providers.py` 中 funnel 命令是否含硬编码 `/xianyu`；`@app.get("/")` 是否做了 302 重定向（funnel 下会循环）。
- **配置参数**：`tunnel.path_prefix`（默认 `/xianyu/`）—— 均在 `config.yaml` 的 `tunnel` 节点配置，无硬编码。
- **适用规范**：参见 `xianyu-hunter-dev` 规范 24
- **场景**：隧道/反向代理子路径部署；域名方式访问系统。
- **不适用**：直连 `127.0.0.1:8001` 开发模式（无 funnel 作用域限制）。
- **历史教训**：域名访问点账户切换跳 `https://…ts.net/`（隧道裸根）显示 `404 page not found`，根因是前端曾用 `location.replace('/')` 越出 `/xianyu` 作用域。

### B-REVIEW-SCHEME-AWARE-COOKIE 协议感知 Cookie（Secure 标志随请求协议）

- **规范名称**：B-REVIEW-SCHEME-AWARE-COOKIE
- **规范内容**：Cookie 为 HttpOnly，前端 JS 无法读写；后端 `RequestSchemeMiddleware` 必须按请求协议（http 直连 / https 隧道）设置 Cookie `Secure` 标志，避免 https 隧道下 Cookie 因 Secure 不匹配被丢弃导致"Cookie 异常"。
- **判断信号**：`app.py` 是否注册 `RequestSchemeMiddleware`；中间件是否根据 `request.url.scheme` 重写 Cookie `Secure`；前端是否存在假设可读写 HttpOnly Cookie 的逻辑（如 `storage.remove('xh_token')`）。
- **配置参数**：`cookie.scheme_aware.enabled`（默认 True）—— 在 `config.yaml` 的 `cookie` 节点配置。
- **适用规范**：参见 `xianyu-hunter-dev` 规范 27
- **场景**：IP 登录 → 域名访问切换、账户切换、隧道 https 访问。
- **不适用**：纯 API 服务无浏览器 Cookie 场景。
- **历史教训**：IP 方式登录初次系统右上角显示"Cookie 异常"；Cookie 有效性取决于 scheme-aware 中间件与 cookie-sync 重新注入，而非前端 remove。

### B-REVIEW-SPA-DEPLOY-ALIGN 部署产物与源码构建对齐

- **规范名称**：B-REVIEW-SPA-DEPLOY-ALIGN
- **规范内容**：exe 从磁盘 `get_app_dir()/static` 加载 SPA（非嵌入），`dist/xianyu-hunter/static/spa/` 必须与 `src/xianyu_hunter/web/static/spa/` 当前构建对齐。入口 chunk 引用的 `location.replace` 目标必须 `/xianyu/`（无裸根），否则运行实例加载旧前端。
- **判断信号**：`dist/index.html` 引用的入口 chunk 是否在 `dist/assets/` 真实存在；该 chunk 是否含 `location.replace('/')` 裸根（旧构建标志）；`src` 与 `dist` 的 `static/spa` 文件集是否对等（missing=0 / orphan=0）。
- **配置参数**：`deploy.spa_src` / `deploy.spa_dist` 路径节点（均在 `config.yaml` 的 `deploy` 节点）；删除静态产物以 `sw.js` precache 为白名单。
- **适用规范**：参见 `xianyu-hunter-dev` 规范 25-26
- **场景**：前端构建后部署、PyInstaller 从磁盘加载前端的发布流程。
- **不适用**：开发模式直接读 `src` 静态目录。
- **历史教训**：`dist` 副本停留在旧构建（`index-Bgdhz0KF.js` 含 `location.replace('/')`），导致域名访问账户切换仍跳 404。

### B-REVIEW-NO-HARDCODED-BASEPATH 禁止硬编码 base path / 重定向前缀

- **规范名称**：B-REVIEW-NO-HARDCODED-BASEPATH
- **规范内容**：所有重定向、URL 拼接、SPA 资源引用必须以配置化的 `path_prefix` / `BASE_URL` 为单一来源，禁止在代码写死 `/xianyu/` 字面量（改 base path 时需单点生效）。
- **判断信号**：`grep -rn "/xianyu/" src/ frontend/src/ | grep -v "config\|BASE_URL\|import.meta"` 命中即疑似硬编码。
- **配置参数**：`tunnel.path_prefix` / `spa.basename` —— 均在 `config.yaml` 配置。
- **适用规范**：参见 `xianyu-hunter-dev` 规范 23-24
- **场景**：任何涉及前端入口、重定向、资源前缀的代码。
- **不适用**：配置文件中声明 base path 的常量定义本身。

---

## 快速自检

执行 `pwsh .trae/skills/xianyu-backend-code-review/scripts/auto-scan.ps1` 自动检查以下阻塞项�?

1. Token 比较是否使用 `hmac.compare_digest()`（非 `==`�?
2. 是否存在硬编码凭据（password/secret/token/api_key�?
3. WebView2 子进程是否重定向�?`DEVNULL`
4. WebView2/Playwright 子进程是否使�?`CREATE_NO_WINDOW`（应�?`CREATE_NEW_CONSOLE`�?
5. `re`/`threading`/`logging` 是否在模块级导入
6. 是否存在�?`except:` + `pass`
7. 是否存在已弃用的 `datetime.utcnow()`（应�?`_utcnow = lambda: datetime.now(timezone.utc)`�?
8. SQLite 引擎是否使用 `StaticPool`（应�?`NullPool`�?
9. `local_embedding.py` 是否设置 `HF_ENDPOINT` 镜像
10. 是否存在 `e.printStackTrace()` 等价（`print(traceback.format_exc())` 替代日志�?
11. 是否存在 Pydantic 1.x �?`.dict()` / `.json()`（应�?`model_dump` / `model_dump_json`�?
12. `config/config.yaml` 是否明文暴露敏感凭据（如钉钉推�?Key�?
13. `.scannerwork/`、`__pycache__/`、`node_modules/`、`dist/` 等产物是否被 git track（应�?`git rm -r --cached` 清理�?
14. 异步方法调用是否遗漏 `await`（合并冲突时优先保留异步版本，禁止同步调用异步方法）
15. 🆕 **S7503**：是否存在无 `await` �?`async` 函数（应改同步函数）
16. 🆕 **S3776**：是否存在认知复杂度 > 15 的大函数（应拆分；可参�?`login_orchestrator.start_session` 拆分模式�?
17. 🆕 **S6767**：是否存在未使用的函数参�?属�?局部变量（应删除或�?`_` 前缀�?
18. 🆕 **S1192**：是否存在重复的字符串字面量 �?2 处（应提取为模块级常量）
19. 🆕 **S5843**：是否存在复杂度过高的正则（应拆分或改字符串方法�?
20. 🆕 `asyncio.CancelledError` 是否�?`suppress(...)` 包裹并向上传播（禁止 `except: pass`�?
21. 🆕 任务函数（`start_all` 等纯编排）是否保�?`async` 关键字而无 await（应改同步）
22. 🆕 `Evaluator` 构造是否接�?`thresholds/weights/keywords` 覆盖参数（会导致用户配置不生效）
23. 🆕 `ChatbotOrchestrator` 是否持有请求级状态（�?`session_id`）（应用 per-session Lock + 无状态设计）
24. 🆕 KB 索引是否仅白名单 `.md/.py/.jsonl/.txt`（应�?`EXCLUDE_DIRS` + `INCLUDE_EXTENSIONS`�?
25. 🆕 【强制】ORM `__table_args__` 中的 `Index(...)` �?`init_db()` 中的 `_migrate_create_index` 一致性（grep 双向比对�?
26. 🆕 【强制】`logger.xxx(...)` 调用中不包含 `%s`/`%d`/`%f` 占位符（grep 检�?printf 风格�?
27. 🆕 【强制】关键查询方法（`list_*`、`count_*`、`list_and_count_*`）包�?`time.monotonic()` 耗时埋点
28. 🆕 【强制】Repository 层查询方法不�?Python 层做全量加载 + 过滤 + 切片（检�?`SELECT *` �?`[r for r in rows if ...]` 模式�?
29. 🆕v4.0 【强制�?已完�?语义事件（EVAL_PASSED/NOTIFY_SENT）是否在业务逻辑完成后触发（禁止前置触发�?
30. 🆕v4.0 【强制】字段覆盖是否按语义分类（基本信�?数�?状�?标识），非一刀�?只填缺失"
31. 🆕v4.0 【强制】资源创建接口（session/start 等）是否幂等（返�?already_active 标志�?
32. 🆕v4.0 【强制】搜索接口参数命名是否统一（keyword/page/page_size），响应结构是否统一（items/total/page�?
33. 🆕v4.0 【强制】注释是否与代码逻辑一致（无误导性顺�?依赖约束说明�?
34. 🆕v4.0 【强制】动态资源映射是否映射表+推断函数分离，业务参数是否通过配置管理
35. 🆕v4.1 【强制�?*B-REVIEW-SESSION-SIGNAL**：含重试逻辑�?SSE/HTTP 接口，重试代码块结束后是否检查关键状态标志（�?`last_session_invalid`），状态仍异常是否推送明确错误事件并 return（禁�?重试失败但仍走成功流�?�?
36. 🆕v4.1 【强制�?*B-REVIEW-COOKIE-CHECK**：依赖多�?Cookie 的接口前置检查是否覆盖所有关�?token（身�?Cookie + 会话 token �?`_m_h5_tk`），清单是否�?`config.yaml` �?`cookie_check_lists` 节点管理（禁止只检查身�?Cookie 存在性）
37. 🆕v4.2 【强制�?*B-REVIEW-CROSS-FIELD**：dataclass/dict 中语义关联字段对（如 gpu_vendor+gpu_renderer、valid+written_count）是否在构造时校验一致�?
38. 🆕v4.2 【强制�?*B-REVIEW-NO-HARDCODED-PROPS**：Cookie/HTTP�?DB列属性是否根据数据语义动态设置（禁止批量硬编�?httpOnly:True/secure:True�?
39. 🆕v4.2 【强制�?*B-REVIEW-NO-CROSS-THREAD-ASYNC**：是否存�?`run_coroutine_threadsafe` + `future.result()` 组合（跨线程死锁风险，应改异步或 fire-and-forget�?
40. 🆕v4.2 【强制�?*B-REVIEW-TRY-FINALLY-INIT**：try/finally 块中 finally 引用的变量是否在 try 之前初始化为 None
41. 🆕v4.2 【强制�?*B-REVIEW-CROSS-COMPONENT-STATE**：多个组件对同一概念（会话有效�?登录状态）做判断时，状态变更是否双向同�?
42. 🆕v4.2 【强制�?*B-REVIEW-ERROR-HINT-ROUTABLE**：错误提示中引用�?API 端点/方法名是否实际存�?
43. 🆕v4.3 【强制�?*B-REVIEW-ENCRYPTION-DEGRADATION**：依赖外部进程的加密（如 v20 App-Bound）是否选择运行时接管（CDP/IPC）而非等待离线解密（检�?`CryptUnprotectData` 调用失败�?fallback 逻辑�?
44. 🆕v4.3 【强制�?*B-REVIEW-FILE-LOCK-BYPASS**：并发访问被�?SQLite 文件是否使用 `immutable=1` URI 模式（检�?`database is locked` 错误处理逻辑�?
45. 🆕v4.3 【强制�?*B-REVIEW-SCHEDULER-ISOLATION**：生命周期不同的后台任务是否使用独立 `BackgroundScheduler`（检�?`BackgroundScheduler()` 实例化是否在独立变量中）
46. 🆕v4.3 【强制�?*B-REVIEW-CONFIG-DRIVEN-TOGGLE**：高风险功能是否默认关闭 + 参数集中�?`Config` 类（检�?`enable_flag: bool = False` 模式 + `config.yaml` 暴露开关）
47. 🆕v4.3 【强制�?*B-REVIEW-FALLBACK-CHAIN**：多重方案是否按优先级降�?+ backoff 策略（检�?`max_failures`/`backoff_multiplier`/`max_interval` 是否在配置管理）
48. 🆕v4.3 【强制�?*B-REVIEW-CHROME-136-ADAPTATION**：`--remote-debugging-port` 是否配合 `--user-data-dir` 指向非标准目录（检测启动命令参数完整性）
49. 🆕v4.3 【强制�?*B-REVIEW-MULTI-PROFILE-DISCOVERY**：多 profile 发现是否优先读结构化元数�?fallback 到目录扫描（检�?`profile.info_cache` 读取逻辑 + 目录扫描 fallback�?
50. 🆕v4.3 【强制�?*B-REVIEW-WINDOWS-TEST-MOCK**：测试中 Windows 环境变量是否�?`tmp_path` 正确 mock（检�?`monkeypatch.setenv` + 路径结构与实现对齐）
51. 🆕v4.3 【强制�?*B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK**：使�?pytest 插件前是否验证项目已安装（检�?`pyproject.toml` �?`addopts` + `requirements-dev.txt` 声明�?
52. 🆕v4.4 【强制�?*B-REVIEW-ERROR-SEMANTICS**：错误码�?HTTP 状态码映射是否语义匹配（如 RGV587=token 过期不应映射�?401 登录失效，应映射�?408/503 稍后重试）（检�?`if "RGV587" in error` �?映射状态码的逻辑�?
53. 🆕v4.4 【强制�?*B-REVIEW-CONFIG-LINKAGE**：config.yaml 新增配置项是否从定义到最终消费点全链路可追踪（grep 字段名确认每层都有读取代码，禁止只注入到 TaskConfig 就认为生效）
54. 🆕v4.4 【强制�?*B-REVIEW-FAST-DEGRADATION**：含 `fast=True` 参数的方法，调用方是否在 fast 返回空结�?状态标志异常时自动�?`fast=False` 重试一次（检�?`fast=True` 调用点是否有降级重试逻辑�?
55. 🆕v4.4 【强制�?*B-REVIEW-NO-HARDCODED-THRESHOLD**：代码中是否存在 `MAX_XXX = N` 硬编码常量且 config.yaml 中已有对应配置项（如 `MAX_CONSECUTIVE_ERRORS` vs `fail_pause_threshold`），应改为读取配�?
56. 🆕v4.4 【强制�?*B-REVIEW-PARAM-PASS-THROUGH**：方法签名新增参数后是否 grep 所有调用点（含内部 `_private` 方法）确认参数传递（检�?`build_search_url` 新增参数�?`_call_search_api` 内部 URL 构建是否也传递）
57. 🆕v4.5 【强制�?*B-REVIEW-MULTI-WRITE-ENTRY**：核心状态（Cookie 层、登录态、连接池）有 �?2 个写入入口时是否有统一同步入口函数（grep `sync_xxx_from_<主数据源>` 模式 + 检�?`on_login_success` �?被定义未调用"回调�?
58. 🆕v4.5 【强制�?*B-REVIEW-INACTIVE-STATE-PRESERVE**：状态补救同步条件是否区�?从未初始�?�?主动失效"（检�?`not state.valid` 是否作为补救触发条件，应改为 `state.updated_at == 0.0`�?
59. 🆕v4.5 【强制�?*B-REVIEW-BROWSER-FALLBACK-SYNC**：状态查询端点（�?`/cookies/layers`）是否实现两步同步（先从主数据源补救 + 后从浏览器内存兜底并回写 JSON�?
60. 🆕v4.5 【强制�?*B-REVIEW-UPDATE-VS-UPSERT**：持久化层方法命名是否语义清晰（`update_*` 只更新已存在 vs `upsert_*` 更新+添加，检测是否有一个方法兼顾两种语义）；并发场景读-�?写是否在 `RLock` 内完�?
61. 🆕v4.5 【强制�?*B-REVIEW-POST-WRITE-HOOK**：写主数据源成功后是否显式调用同步钩子（检�?`if json_written: try: sync_xxx_from_json()` 模式；钩子失败是否仅记录日志不抛异常�?
62. 🆕v4.5 【强制�?*B-REVIEW-DEAD-CODE-CLEANUP**：是否存�?定义未调�?的函�?回调/事件订阅（`grep -rn "<func_name>" src/ tests/` 无结果时必须清理或恢复调用路径）
63. 🆕v4.6 【强制�?*B-REVIEW-FILTER-SCENARIO**：同一查询函数被多场景复用时是否参数化场景标志（如 `include_failed`），调用方是否显式传值（操作判断场景 False / 展示历史场景 True），是否新增回归测试覆盖两种场景（检�?`list_*`/`get_*`/`query_*` 函数内硬编码 `if status == 'failed': continue` 模式�?
64. 🆕v4.6 【强制�?*B-REVIEW-ASYNC-TIMEOUT**：`await` 外部资源（浏览器 `page.query_selector` / HTTP 请求 / 文件 IO）是否在调用层用 `asyncio.wait_for(coro, timeout=N)` 包装（禁止依赖被调用方内�?timeout 参数，如 `page.query_selector` �?timeout 参数会无限挂起），超时是否返�?504 状态码（参数在 `config.yaml` �?`async_timeout` 节点管理�?
65. 🆕v4.6 【强制�?*B-REVIEW-REUSE-PATTERN**：新增功能前是否 grep 项目内相似实现（�?`asyncio.wait_for` / `hmac.compare_digest` / `_escape_like` / `_utcnow`），是否复用既有 helper/工具函数/模式而非重新实现（检测新增函数与既有函数语义重复�?
66. 🆕v4.6 【强制�?*B-REVIEW-DATA-FLOW-TRACE**：用户反�?字段为空"时是否按 5 点逐层追踪（DB schema 字段存在 �?Repo 查询未过�?�?API 响应注入字段 �?前端 types 声明字段 �?render 取值正确），禁止仅查单层就下结论（检�?`list_orders_by_item_ids` 等查询是否在 Repo �?`if status == 'failed': continue` 一刀切过滤）
67. 🆕v4.9 【强制�?*B-REVIEW-STATE-MACHINE-WHITELIST**：业务对象有状态字段且会变化时（如 task.status / session.state / order.status）是否按 6 步流程设计：枚举穷举所有状态值、白名单显式列出允许的转换、终态（completed/failed/cancelled）不可复活、中间态（pending/running）有超时清理、deadline 不可无限重置、前后端枚举值统一（检�?`if status == 'X': status = 'Y'` 散落式转换，应改�?`TRANSITIONS: dict[str, set[str]]` 集中管理；参数在 `config.yaml` �?`state_machine` 节点管理�?
68. 🆕v4.9 【强制�?*B-REVIEW-RESOURCE-CLEANUP-HOOK**：可注册组件（BackgroundScheduler / EventBus 消费�?/ asyncio.Task / Playwright page / 浏览器实例）是否实现 `cleanup()` / `close()` / `shutdown()` 钩子并在 shutdown 事件中调用；`asyncio.create_task(...)` 返回�?Task 是否保留引用到实例属性防 GC（检�?`asyncio.create_task(...)` 未赋值的 fire-and-forget 模式 + `task.add_done_callback` 未取消模式）；取�?gather 模式是否正确（`await asyncio.gather(*tasks, return_exceptions=True)`）；try/finally 初始化模式是否完整（资源�?try 之前 `= None`，finally �?`if resource: await resource.close()`�?
69. 🆕v4.9 【强制�?*B-REVIEW-DUAL-LINK-CONSISTENCY**：同一业务目标（如"刷新会话" / "更新任务状�?）有 �?2 条链路（API 路由 + WebSocket 推�?+ 定时任务）时，共用前置条件（如校验登录�?锁竞�?参数合法性）是否提取为独立函数两链路调用同一函数（检�?`api_xxx.py` �?`scheduler_xxx.py` 中重复的校验代码块，应抽离为 `def _validate_xxx(...): ...` 共享调用）；是否 grep 验证两链路都调用了同一函数；是否新增测试覆盖两链路
70. 🆕v4.9 【强制�?*B-REVIEW-CONCURRENT-STATE-LOCK**：共享状态（会话有效�?/ 任务列表 / 连接�?/ Cookie 层）�?检�?+ 更新"是否在同一 `asyncio.Lock` / `threading.RLock` 内完成（检�?`if not self._active: self._start()` 错误模式，应改为 `async with self._lock: if not self._active: await self._start()`）；锁粒度是否最小化（不包裹 IO 密集操作）；锁内是否禁止 `await`（除非使�?`asyncio.Lock`）；dataclass 字段是否显式声明禁止 `getattr(self, 'xxx', default)` 兜底（应 `field1: str = ""` 显式声明默认值）；锁类型选择是否正确（`Lock` 不可重入 vs `RLock` 可重入）
71. 🆕v4.9 【强制�?*B-REVIEW-PYTHON-MODERN-ASYNCIO**：是否使�?`asyncio.create_task(coro)` 替代 `asyncio.get_event_loop().create_task(coro)`（Python 3.10+ 推荐做法，避免在无运行循环时�?DeprecationWarning）；是否避免 `getattr(obj, 'method', fallback)` 兜底（应直接调用 `obj.method()`，缺失方法应在类型层面解决）；模块级 import 是否完整（禁止函数内 `import asyncio` 的延迟导入）；`CancelledError` 是否向上传播（`except BaseException: ...` 应改�?`except Exception: ...` 或显�?`except asyncio.CancelledError: raise`）；类型注解是否用现代语法（`dict[str, str]` 替代 `Dict[str, str]`，`int | None` 替代 `Optional[int]`，需 Python 3.10+�?
72. 🆕v4.10 【强制�?*B-REVIEW-FILTER-VISIBILITY**：含过滤链路的查询接口（实时搜索/历史查询/列表过滤）是否输出完�?`filter_summary`（含 `raw`/各阶�?`*_skipped`/`final_total`/`filtered_out`）；`filtered_out` 项是否含 `link_type`/`link_key`/`display`/`filter_reason`/`filter_detail` 5 个字段；`max_filtered_out_items` 上限是否�?`config.yaml` �?`filter_summary` 节点读取（禁止硬编码 50）；过滤链每阶段（keyword/price/publish_days）是否记录跳过计数和详情（检�?`if not match: continue` 未记录到 `filter_summary` 模式�?
73. 🆕v4.10 【强制�?*B-REVIEW-PYTEST-MODULE-REIMPORT**：conftest.py patch 模块属性时是否遍历 `sys.modules` 找所有持目标属性的模块全部 patch（检�?`for name in ["xxx", "yyy"]: monkeypatch.setattr(...)` 硬编码模块名列表违规模式）；是否使用 `importlib.import_module` 替代 `__import__`（后者返回顶层包而非子模块）；patch 后是�?`assert hasattr(mod, TARGET_ATTR)` 验证生效；跨模块共享配置路径的测试是否用此模式（参数�?`config.yaml` �?`pytest_isolation` 节点管理�?
74. 🆕v4.10 【强制�?*B-REVIEW-LOGURU-PLACEHOLDER**：loguru 项目所�?`logger.xxx()` 调用是否使用 `{}` 占位符（检�?`grep -nE 'logger\.(debug|info|warning|error|critical).*%[sdrf]' src/` 命中违规）；混用 `%s`/`%d` 不抛异常但输出字面量极难发现；f-string 简单拼接可用但复杂格式推荐 `{}` 占位符；项目使用的日志库（loguru/logging/structlog）是否在 `config.yaml` �?`log_placeholder.logger_lib` 节点声明
75. 🆕v4.10 【强制�?*B-REVIEW-TEST-FIXTURE-ISOLATION**：conftest.py 是否�?`tmp_path` / `tmp_path_factory` 隔离生产路径（`data/cookies.json`/`*.db`）（检�?`open("data/cookies.json", "w")` 直接写生产路径违规模式）；fixture 数据是否带可识别特征（`test_fixture_` 前缀/`__test__` 后缀，便于污染后定位）；fixture 作用域是否正确（`scope="session"` 跨测试共�?/ `scope="function"` 单测试，禁止模块级全局变量持有测试数据）；数据污染应�?5 步流程是否在 `config.yaml` �?`test_isolation.pollution_recovery_steps` 节点管理
76. 🆕v4.11 【强制�?*B-REVIEW-CONFIG-VALIDATION**：数值型配置项是否有边界值校验（min/max/non_zero/range），加载时是否主动校验无效值用默认�?warning（检�?`interval = config.get(...)` 后直�?`interval / N` 算术运算未校�?interval>0 模式，参数在 `config.yaml` �?`config_validation` 节点管理�?
77. 🆕v4.11 【强制�?*B-REVIEW-MIGRATION-FAILURE-HANDLING**：`_migrate_*` 函数失败是否明确处理策略（关键迁�?raise RuntimeError 中断启动，非关键 warning+继续），是否�?`except: pass` 静默吞掉违规模式（检�?`_migrate_*` 函数中的 `except.*pass` 模式，参数在 `config.yaml` �?`migration_failure_strategy` 节点管理�?
78. 🆕v4.11 【强制�?*B-REVIEW-STATUS-CODE-SEMANTICS**：HTTP 状态码是否按语义精细化区分�?01 未登�?403 权限不足/440 Cookie 过期/441 Token 过期/504 网关超时），是否所有认证失败都映射�?401 导致前端无法区分（检�?`raise HTTPException(status_code=401, ".*过期")` 模式，参数在 `config.yaml` �?`status_code_semantics` 节点管理�?
79. 🆕v4.11 【强制�?*B-REVIEW-LLM-DEFENSIVE-PARSING**：LLM API 响应是否按三层级防御性解析（choices→message→content，每层用 .get()+isinstance+长度检查），是否含 `response["choices"][0]["message"]["content"]` 链式访问违规模式（参数在 `config.yaml` �?`llm_defensive_parsing` 节点管理�?
80. 🆕v4.11 【强制�?*B-REVIEW-SCHEDULER-DB-SYNC**：调度器内存状态变更（pause/resume/stop/error_pause）是否同�?DB（update_task_status），是否只在内存变更导致 API 返回与实际不一致（检�?`pause_event.clear()` 后未�?`update_task_status` 模式，参数在 `config.yaml` �?`scheduler_db_sync` 节点管理�?
81. 🆕v4.11 【强制�?*B-REVIEW-BACKGROUND-TASK-MONITOR**：后�?asyncio.Task 是否用轮询监控（task.done() 检查），是否含 `await stop_event.wait()` 静默等待导致任务异常退出无感知违规模式（参数在 `config.yaml` �?`background_task_monitor` 节点管理�?
82. 🆕v4.11 【强制�?*B-REVIEW-NUMERIC-EXTRACTION**：多数字文本是否�?`re.findall` �?`numbers[-1]`（实际成交价通常在最后），是否含 `re.search` 取第一个数字误取原价违规模式（参数�?`config.yaml` �?`numeric_extraction_strategy` 节点管理�?
83. 🆕v4.12 【强制�?*B-REVIEW-DOM-FALLBACK-CHAIN**：SPA 数据提取是否实现 DOM �?og:meta �?document.title 多层兜底（检�?`await page.locator(...).text_content()` 后直�?`return` 无兜底模式）；兜底层级顺序与选择器集合是否在 `config.yaml` �?`dom_fallback_chain` 节点管理（与 v4.3 B-REVIEW-FALLBACK-CHAIN �?多方案降�?语义不同，本节点专指 DOM 提取兜底�?
84. 🆕v4.12 【强制�?*B-REVIEW-FAILURE-DUMP**：关键选择器失败或数据提取异常时是否自�?dump `page.content()` �?`logs/<scenario>_<id>_<timestamp>.html`（检�?`except ElementNotFound: pass` �?`except TimeoutError: return None` �?dump 模式）；dump 是否�?`asyncio.create_task` fire-and-forget 不阻塞主流程；dump 文件名是否含场景标识+时间�?业务 ID；是否对敏感字段（cookie/token）脱敏；参数�?`config.yaml` �?`failure_dump` 节点管理
85. 🆕v4.12 【强制�?*B-REVIEW-TIMING-INSTRUMENTATION**：关键路径（`page.goto`/`wait_for_selector`/HTTP/DB 查询）是否用 `time.perf_counter()` 计时并按阈值告警（检�?`logger.info("开�?)/logger.info("结束")` 文本日志违规模式，应用结构化 timing）；超阈值是否升 `WARNING` 日志级别；阈值与场景白名单是否在 `config.yaml` �?`timing_instrumentation` 节点管理
86. 🆕v4.12 【强制�?*B-REVIEW-PRECHECK-AND-PARALLEL**：高开销操作（浏览器启动/网络采集）前是否前置校验 Cookie 凭证 `expires` 字段（检�?`async with async_playwright()` 后才校验 Cookie 的违规模式，应前置校验过期直接返�?440）；session cookie（`expires=-1`）是否跳过预校验；独�?IO 任务是否�?`asyncio.gather(*tasks, return_exceptions=True)` 并行（检�?`for task in tasks: await task` 串行违规模式）；`gather` 是否�?`return_exceptions=True` 隔离异常；身�?Cookie 白名单与并发上限是否�?`config.yaml` �?`precheck_parallel` 节点管理
87. 🆕v4.8 【强制�?*B-REVIEW-STATE-FLAG-PRECHECK**：状态标志设置后是否有前置检查（grep `self.*= True` 状态标�?�?检查操作入口是否有 `getattr(self, "flag", False)` 检查）；是否有重置机制（grep `flag = False`）（参数�?`config.yaml` �?`state_flag_precheck` 节点管理�?
88. 🆕v4.8 【强制�?*B-REVIEW-LOG-DOWNGRADE-STABILITY**：日志降级判断是否用模块级常量（检�?`logger.log(log_level` 动态级�?�?检查判断条件是否含魔法字符串，应提取为模块级常量并注释文案来源）（参数�?`config.yaml` �?`log_downgrade` 节点管理�?
89. 🆕v4.8 【强制�?*B-REVIEW-EDIT-VERIFY**：修复代码中引用的变�?函数是否真正存在于文件中（grep 标志性标识符确认�?false positive，无匹配则重新执�?Edit）；适用所有使�?Edit 工具的修改场�?
90. 🆕v4.13 【强制�?*B-REVIEW-STATS-EXCLUSIVE**：统计接口返回的分类计数是否互斥（`total = sum(各分类计�?`，如 `api_evaluations.py` �?dist 统计�?insufficient(score==null) �?auto/pass/fail(有评�? 互斥，`total = insufficient_count + auto + pass + fail`）；是否 grep 后端统计代码确认分类逻辑互斥；是否验�?total 等于各分类之和（禁止一个记录同时计入两个分类导致统计数量与实际不符）；非互斥分类（如标签统计，一个记录可属于多个分类）是否排除；适用场景：评分分布统计、状态分组统计、任何返回分类计数的 API；不适用场景：非互斥分类（如标签统计）；分类定义和互斥规则是否在 `config.yaml` �?`stats_exclusive` 节点管理
91. 🆕v4.15 【强制�?*B-REVIEW-CACHE-INVALIDATION**：任何持久化层（JSON 文件 / SQLite / 外部配置）变更后是否**显式调用**对应缓存对象�?`invalidate_cache()` 或等价方法（检测类�?`_cache`/`_cache_time`/`_cached_*` 字段但无 `invalidate_cache()` 方法的违规模式）；是否仅依赖 TTL 兜底（`time.time() - self._cache_time < 30` 模式违规，跨进程不一致）；跨进程变更（子进程写、主进程读）是否主动通知主进程失效缓存（检测子进程 `write_json()` 后只更新自己缓存未通知主进程的模式）；同步钩子失败是否�?`logger.warning` 不抛异常；适用场景：JSON 持久化层、跨进程 Cookie/状态同步、内存缓存与文件副本同步、登录态多进程写入；不适用场景：纯函数、纯计算缓存（LRU math）、无外部数据源同步的内部状态；参数�?`config.yaml` �?`cache_invalidation` 节点管理
92. 🆕v4.15 【强制�?*B-REVIEW-STATE-DETECTION-BOOTSTRAP**：任�?功能信号"字段（`last_session_invalid`/`is_healthy`/`is_connected` 等）默认�?`False` 是否被用�?功能正常"的判定条件（检�?`if not collector.last_session_invalid:` 误用初始 False 模式）；强制恢复/兜底逻辑是否仅依赖布尔字段未配合"已发生过检�?标记（`_last_m5tk_refresh > 0` / `use_count > 0` / `_has_run`）；强制恢复范围是否超出信号能证明有效的层（�?`m5tk_signal` 恢复 IDENTITY 层违规）；未识别的信号组合是否默认恢复所有层（应 `logger.warning` �?`set()`）；适用场景：跨进程/跨模块状态判定、Cookie 层状态自愈、容器健康检查、服务可用性兜底；不适用场景：纯客户�?UI 状态、单次函数返回值、无初始歧义的开关字段；参数�?`config.yaml` �?`state_detection_bootstrap` 节点管理
93. 🆕v4.15 【强制�?*B-REVIEW-MIGRATION-TRANSACTION**：SQLite `_migrate_*` 函数是否�?`engine.begin()` 单事务包裹整�?DDL 过程（检测多�?`conn.commit()` 拆分布骤违规模式）；迁移前是�?`DROP TABLE IF EXISTS {table}_old` 清理残留（避免上次失败导�?RENAME 阻塞）；`orm_table.create(...)` 是否传入 `conn` 而非 `engine`（确�?DDL 纳入事务）；数据复制是否用列名交集（防止列差异导�?INSERT 失败）；失败后是否从 `{table}_old` RENAME 恢复（异常路径完整性）；是否含 SQLite 不支持的 `ALTER TABLE ... MODIFY COLUMN` / `ALTER TABLE ... ALTER COLUMN` 违规模式（应改用表重建）；适用场景：SQLite 修改列约束、表重建、任何不可�?DDL；不适用场景：PostgreSQL/MySQL（有原生 DDL 事务）、新增列（直�?`ADD COLUMN`）、纯查询/插入操作；参数在 `config.yaml` �?`migration_transaction` 节点管理
102. 🆕v4.20 【强制�?*B-REVIEW-VERSION-SOURCE-SINGLE**：构建期元数据（版本�?构建时间/git_sha）是否有唯一源头文件（`__init__.py: __version__`�? 自动生成文件（`_build_info.py` �?`scripts/build_info.py` 维护）；多端点读取同一元数据是否封�?`_safe_xxx()` 三层 try/except 回退辅助函数（源�?�?生成文件 �?默认�?`'unknown'`）；`export_config`/`about`/`health` 等多端点响应中版本号字段是否调用辅助函数（检�?`grep -E '"version":\s*"[^"]+"' src/xianyu_hunter/web/routes/` 命中硬编码字符串的违规模式，应改�?`_safe_app_version()`）；是否使用 `"1.0"`/`"0.0.0"`/`"unknown version"` 等占位符（违规，应改�?`'unknown'`）；`grep "from xianyu_hunter import __version__" src/` 出现 �?2 处时是否封装辅助函数；端点命名含 "version" 但实际返回业务计数的（如 `/api/config/version` 返回 `len(backups)`）是否在 docstring 中明确语义，参数�?`config.yaml` �?`version_source_management` 节点管理（`single_source_file` / `auto_generated_file` / `safe_helper_function` / `fallback_default` / `forbidden_placeholders` / `forbidden_version_endpoints` / `helper_threshold`�?
103. 🆕v4.22 【强制�?*B-REVIEW-STARTUP-HOOK-COMPLETENESS**：所有依�?`container.browser`/`container.collector` 的组件是否在 `startup.py _on_startup` 中有对应 `start_xxx()` 启动钩子（检�?`grep container.browser/collector` 找所有依赖点逐个检查是否有对应启动调用）；启动钩子是否�?`if _should_start_scheduler()` 包裹；是否放在依赖的调度器之后；启动失败 try/except 兜底是否�?warning 不阻断主服务；参数在 `config.yaml` �?`startup_hook_completeness` 节点管理
104. 🆕v4.22 【强制�?*B-REVIEW-TASK-HISTORY-THREE-LAYER-PROTECTION**：写�?`running` 状态的代码路径是否有对�?`finalize` 调用更新为终态；是否覆盖正常结束/future.result超时/协程异常三条路径；错误消息累积是否设 FIFO 上限避免 JSON 字段无限膨胀；状态语义是否区�?`circuit_broken→failed` / `_stop_flag→cancelled` / 正常→completed；参数在 `config.yaml` �?`task_history_protection` 节点管理
105. 🆕v4.22 【强制�?*B-REVIEW-COUNTER-DB-MAX-INIT**：业务自�?ID（如 `task_id`/`batch_id`/`run_id`）是否在调度�?`__init__` 时从 DB `SELECT MAX(id)` 初始化（禁止依赖内存初始化，进程重启会重置）；查询失败是否回退�?0+warning 不阻断启动；`trigger_now` 时是�?+1 立即返回前端不等�?DB 写入；参数在 `config.yaml` �?`counter_db_max_init` 节点管理
106. 🆕v4.22 【强制�?*B-REVIEW-APSCHEDULER-INTERVAL-FIRST-RUN**：APScheduler interval 触发器是否设 `next_run_time=now+delay`（默认首次执行时间为 start+interval，启动后等完整间隔）；delay 建议 5-10 秒给初始化依赖就绪；日志是否输出间隔+首次执行时间；参数在 `config.yaml` �?`apscheduler_interval_first_run` 节点管理
107. 🆕v4.23 【强制�?*B-REVIEW-LLM-CAPABILITY-DISPATCH**：任�?LLM/多模�?function_call/json_mode 调用是否在构�?payload 前预检目标模型能力（检测直接构�?`messages=[{"type": "image_url", ...}]` 无能力预检的违规模式）；能力校验函数是否共享（`api_ai._is_vision_capable`，禁止散落内联判断）；关键字白名单是否配置化（`config.yaml` �?`llm_capability_keywords` 节点）；参数�?`config.yaml` �?`llm_capability_keywords` 节点管理
108. 🆕v4.23 【强制�?*B-REVIEW-SHARED-UTIL-CENTRALIZATION**：跨 �? 模块复用的判断逻辑/关键字白名单/常量是否抽取�?被依赖方"模块顶层的纯函数或模块级常量（检测跨 �? 文件出现相同关键�?正则/常量字面量必须触�?抽取共享"建议）；导入方是否只�?`from <source> import <shared>`；参数在 `config.yaml` �?`shared_util_rules` 节点管理
109. 🆕v4.23 【强制�?*B-REVIEW-SILENT-DOWNGRADE-PRECHECK**�?可选增�?能力（vision/function_call/json_mode）调用前是否预检（检测代码构�?payload 时未做能力预检的违规模式）；失败时是否降级为等价文本表达（�?prompt 追加"图片 URL + 描述"）而非抛错；预检失败日志级别是否 `logger.warning`（与 v4.9 B-REVIEW-LOG-DOWNGRADE-STABILITY 一致）；降�?prompt 模板是否集中管理（`config.yaml` �?`llm_downgrade` 节点）；是否区分"可选增�?�?核心能力"（核心能力缺失必须报错）；参数在 `config.yaml` �?`llm_downgrade` 节点管理
110. 🆕v4.25 【强制�?*B-REVIEW-MIGRATION-BLOCK-ISOLATION**：迁移函数（�?`run_migrations`）内含多个独立迁移块（C-01/C-02/C-03/C-04/C-05）时是否各自 try/except（检测外�?`try: ... except Exception as e: logger.warning(f"启动迁移钩子失败: {e}")` 包裹多个迁移块的违规模式）；强依赖场景（如表重建+数据回填）允许合并但必须在注释中说明合并原因；每个块�?except 是否�?`logger.warning` �?`logger.exception` 记录（禁�?`except: pass`）；块边界标识符是否�?`config.yaml` �?`migration_block_isolation.block_markers` 节点管理；参数在 `config.yaml` �?`migration_block_isolation` 节点管理（`function_patterns` / `block_markers` / `require_independent_try` / `allow_merge_when_dependent` / `violation_message`�?
111. 🆕v4.25 【强制�?*B-REVIEW-CRITICAL-PATH-NO-SWALLOW**：启动钩子（`_on_startup`�?迁移函数（`run_migrations`�?初始化函数（`_init_*`）等关键路径的外�?except 是否�?`logger.exception()` 输出完整 traceback（检�?`except Exception as e: logger.warning(f"...{e}")` 丢失堆栈的违规模式，检�?`except Exception as e: logger.warning("...: {}", e)` loguru 占位符也不保�?traceback 的违规模式，检�?`except: pass` 完全吞掉的违规模式）；关键路径函数清单是否在 `config.yaml` �?`critical_path_no_swallow.critical_functions` 节点管理；禁止日志模式是否在 `critical_path_no_swallow.forbidden_patterns` 节点管理；允许的简�?warning 场景（非关键路径）是否在 `critical_path_no_swallow.allowed_simple_warning` 节点管理；参数在 `config.yaml` �?`critical_path_no_swallow` 节点管理
112. 🆕v4.26 【强制�?*B-REVIEW-EXCLUDE-UNSET-CHECK**：PATCH/PUT 接口是否�?`model_dump(exclude_unset=True)` 区分未传/传null/传值三态（检�?`for k, v in data.items(): if v is not None: ...` 手动循环跳过 None 的违规模式，会丢�?�?null 表示清除覆盖"的语义）；是否覆盖字段传 null 表示清除覆盖应正常写�?None；参数在 `config.yaml` �?`api_update_semantics` 节点管理
113. 🆕v4.26 【强制�?*B-REVIEW-NOT-NULL-NONE-DEFENSE**：NOT NULL 字段�?null 时是否防御�?pop 而非直接写入 DB 触发 IntegrityError（检�?`model_dump(exclude_unset=True)` 后未�?NOT NULL 字段�?None 检查的违规模式）；覆盖字段�?null 表示清除覆盖应正常写�?None（与 B-REVIEW-EXCLUDE-UNSET-CHECK 联动）；参数�?`config.yaml` �?`api_update_semantics` 节点管理
114. 🆕v4.26 【强制�?*B-REVIEW-SHARED-SINGLETON-POLLUTION**：循环中创建任务级覆盖对象是否用局部变�?`worker_xxx`（检�?`container.config = new_config` 直接修改 container 单例的违规模式，会污染下一轮迭代）；任务级覆盖对象生命周期是否与循环迭代绑定（迭代结束后自动释放）；参数在 `config.yaml` �?`shared_singleton_protection` 节点管理
115. 🆕v4.27 【强制�?*B-REVIEW-FAILURE-REASON-PROPAGATION**：失败原因是否分三层传递（底层 `last_*_failure_reason` �?中层 status_code 映射 �?高层日志降级，检�?`if "expired" in detail` 字符串子串判断违规模式）；reason 值是否可枚举集中管理（`FAILURE_REASONS: tuple[str, ...]`，禁止散落字符串）；错误响应是否�?`error_code` 字段（前端按 error_code 分支而非按文案子串）；参数在 `config.yaml` �?`failure_reason_propagation` 节点管理
116. 🆕v4.27 【强制�?*B-REVIEW-DATA-COMPLETENESS-PRECHECK**：调用外部依赖前是否执行数据完整性预检（预检方法签名 `async def _check_xxx_completeness(self) -> str | None`，检�?`if len(cookies) < 10` 单阈值违规模式）；是否用双阈�?AND 判断（总数 + 关键项命中数）；调用后是否二次检查（防御外部依赖中途失效）；错误信息是否含具体缺失清单（禁止笼�?数据不完�?）；参数�?`config.yaml` �?`data_completeness_precheck` 节点管理
117. 🆕v4.27 【强制�?*B-REVIEW-MERGE-VS-OVERWRITE-WRITE**：持久化层写入策略是否匹配数据来源（部分集→合并�?`merge_*`，完整集→覆盖写 `save_*`/`export_*`，检测浏览器 Cookie 导入用覆盖写丢失旧数据的违规模式）；合并写方法签名是否为 `def merge_xxx(self, new_items: list[dict] | dict) -> bool`；合并后是否日志输出合并前后数量；覆盖写前是否预检新集完整；参数在 `config.yaml` �?`write_strategy_decision` 节点管理
118. 🆕v4.27 【强制�?*B-REVIEW-ERROR-MESSAGE-CONSTANT**：错误文�?日志降级 marker/用户提示信息是否提取为模块级常量（`_ERROR_MSG_*` / `_LOG_MARKER_*`，检�?`if "expired" in` / `if "unavailable" in` 字符串子串判断违规模式）；跨模块引用是否 `from <source> import _MSG_*`；错误响应是否含 `error_code` 字段；同一文案在代码中出现 �?2 处未提取为常量即违规（与 B-REVIEW-LOG-DOWNGRADE-STABILITY 联动）；参数�?`config.yaml` �?`error_message_centralization` 节点管理
119. 🆕v4.27 【强制�?*B-REVIEW-EDIT-VERIFY-DEPLOY-LOOP**：Edit 工具修改文件后是否立即用 Grep/Read 验证标志性标识符确实存在（检�?AI 助手修改后未 grep 验证的违规模式）；Python 修改后是否重启服务（检测用户反�?还是报错"�?Python 进程启动时间早于代码修改时间的违规模式）；重启后是否验证端口监听 + 数据状态；`git stash` 前是否先 `git commit` 保底；参数在 `config.yaml` �?`edit_verify_deploy_loop` 节点管理
120. 🆕v4.27 【强制�?*B-REVIEW-TEST-MOCK-SYNC**：修改前置条件（新增预检方法/配置�?方法参数）时是否同步更新测试 mock 数据（检测新�?`_check_*_completeness` 后原 mock 数据不完整导致测试失败的违规模式）；mock 数据是否覆盖完整字段集（�?22 �?cookie 而非 4 个）；mock 数据是否集中管理�?`conftest.py`；测试失败时是否优先检查前置条件变更（grep 最近修改的方法签名）；参数�?`config.yaml` �?`test_mock_synchronization` 节点管理
121. 🆕v4.28 【强制�?*B-REVIEW-MULTI-USER-RESOURCE-ISOLATION**：单用户系统升级到多用户时，全局单例资源是否�?`user_id` 维度隔离（检�?`cookies.json` 单例路径、`_cache: dict` 全局缓存变量、公共方法签名无 `user_id` 参数的违规模式）；文件路径是否加 `user_id` 维度（`cookies_{uid}.json`）；缓存是否分桶（`dict[str, tuple[dict, float]]`，按 user_id 取桶）；公共方法是否�?`user_id="default"` 默认参数；`user_id` 拼接文件路径前是否做白名单校验（正则 `^[A-Za-z0-9_-]{1,64}$` 防路径遍历）；SQLite 兜底是否判断 `user_id == default`�?*适用**：单用户→多用户升级、多租户、多账号管理�?*不适用**：纯内部工具、单租户 SaaS、用户数固定�?1；参数在 `config.yaml` �?`multi_user_resource_isolation` 节点管理（`user_id_pattern` / `default_user_id` / `isolation_dimensions` / `exclude_paths`�?
122. 🆕v4.28 【强制�?*B-REVIEW-AUTH-MULTI-PATH-VALIDATION**：多种认证方式（管理令牌 + 用户会话）时，中间件是否按优先级链式校验（检测中间件单一 token 校验、无 `user_id` 注入、异常静默降级的违规模式）；是否实现三路校验顺序（`WEB_TOKEN` 直�?�?`session_token` 查库 �?401）；token 比较是否�?`hmac.compare_digest` 防时序攻击（禁止 `==` 直接比较）；异常降级是否�?`logger.warning`（禁�?`logger.debug` 静默）；是否�?`user_id` 注入 `request.state` 供下游使用；日志是否禁止泄露 token 明文（必须脱敏）；公开路径白名单是否放行（白名单来�?`auth.public_prefixes` 配置）；**适用**：管理后�?用户前台混合认证、多角色系统�?*不适用**：单一认证方式、纯 API 网关、内部微服务；参数在 `config.yaml` �?`auth_multi_path_validation` 节点管理（`web_token_compare_func` / `session_verify_method` / `exception_log_level` / `public_prefixes_config` / `forbidden_log_levels`�?
123. 🆕v4.28 【强制�?*B-REVIEW-SESSION-TOKEN-SECURITY**：会�?token 的生成、存储、校验、撤销是否遵循安全最佳实践（检�?token 明文存库、用 `==` 比较、无滑动续期、撤销不清缓存的违规模式）；是否用 `secrets.token_urlsafe` 生成（禁�?`random.choices` / `uuid.uuid4` 截断）；是否�?`sha256` 存储哈希（禁止存明文）；校验是否�?`hmac.compare_digest`；是否实现滑动续期（距过期不�?`renewal_threshold_days` 天时延长 `ttl_days`）；撤销是否清缓�?+ 标记 `is_active=0`；缓存与撤销是否互斥（同一 `RLock` 内完成读-�?写）；是否实现会话固定防护（签发�?session 前失效旧 session）；**适用**：涉及用户会话的系统、需防时序攻击、需滑动续期�?*不适用**：无状�?JWT、一次�?token、内部服务通信；参数在 `config.yaml` �?`session_token_security` 节点管理（`token_generate_func` / `token_generate_length` / `token_hash_algo` / `compare_func` / `ttl_days` / `renewal_threshold_days` / `revoke_clear_cache` / `session_fixation_protection`�?
124. 🆕v4.28 【强制�?*B-REVIEW-SNAPSHOT-REALTIME-OVERWRITE**：历史快照与实时采集数据合并时是否按字段类型分档覆盖（检�?`_enrich_*` 函数所有字段都�?`if not existing: existing = new` 的违规模式，会丢失实时更新）；非空字段（`title` / `url` / `id` / `region` / `brand` / `seller_id` / `publish_time`）是否新值存在则覆写；数值字段（`price` / `count` / `view_cnt` / `want_cnt`）是否新�?> 0 才覆写（防止 0 误覆盖真实数据）；状态字段（`is_sold` / `is_deleted`）是否始终覆写（实时性最高）；标识字段（`seller_nick` / `nickname`）是否只填缺失（标识稳定不变）；每档覆盖策略是否有单元测试覆盖；覆盖策略是否有注释说明每档判断依据；**适用**：数据采集系统、缓存与源数据同步、历史快照与实时更新并存�?*不适用**：纯实时系统、纯审计系统、纯日志系统；参数在 `config.yaml` �?`snapshot_realtime_overwrite` 节点管理（`overwrite_strategy.non_empty_fields` / `overwrite_strategy.positive_numeric_fields` / `overwrite_strategy.state_fields` / `overwrite_strategy.identity_fields` / `require_unit_test`�?
125. 🆕v4.28 【强制�?*B-REVIEW-USER-IDENTITY-PRIORITY**：用户身份识别是否有明确优先级链且配置化管理（检测硬编码身份识别逻辑、无优先级链、无降级策略的违规模式）；是否实现优先级链（`unb` > `cookie2` 哈希 > `default`）；每级是否有正�?哈希校验（如 `unb` 匹配 `^\d{8,}$`、`cookie2` �?`sha256` 取前 16 位）；优先级链是否配置化（`config.yaml` �?`user_identity_priority.priority_chain`）；最终是否降级到 `default` 用户（禁止抛错阻断流程）；识别后是否调用 `identify_or_create` 确保库内有记录（避免后续查询空指针）�?*适用**：多用户系统、Cookie 认证、多账号管理�?*不适用**：无用户概念的工具、固定用户系统；参数�?`config.yaml` �?`user_identity_priority` 节点管理（`priority_chain[].source` / `priority_chain[].pattern` / `priority_chain[].hash` / `priority_chain[].length` / `require_identify_or_create`�?
126. ??v4.49.1 ��ǿ�ơ�**B-REVIEW-229 MONKEYPATCH-FROM-IMPORT-COVERAGE**�����Դ���ʹ�� monkeypatch.setattr / patch ʱ�Ƿ񸲸Ǳ���������� `from X import Y` ��ģ�鼶���ã����� patch ��ģ���©����ģ�鶥�� `from X import Y` ���á��������ģ�鶥�� `from X import Y` �� patch ·����һ�µ�Υ��ģʽ�����Ƿ�ɨ�豻��ģ������� `from X import Y` ��䲢���� patch��patch Ŀ���ǡ�����ģ������ԡ����ǡ�Դģ������ԡ���`patch("target_module.Y")` ���� `patch("source_module.Y")`�����Ƿ��� `monkeypatch.delattr` ��֤ import ����Ч��**����**������ʹ�� monkeypatch / unittest.mock.patch �Ĳ��Դ��룻**������**�����������ԣ���ģ�鼶 import����fixture ע��ʽ���ԣ������� `config.yaml` �� `test_quality_protection.monkeypatch_coverage` �ڵ�����`enabled` / `severity` / `detection_patterns` / `required_coverage_scope`����
127. ??v4.49.1 ��ǿ�ơ�**B-REVIEW-230 ASYNC-SYNC-TEST-CALL-MATCH**�������� await �����Ƿ��뷽���� async/sync ����ƥ�䣨���� sync ����ʹ�� await���� async ����©д await���� async ������ MagicMock ���� AsyncMock ��Υ��ģʽ����async �����Ƿ��� `AsyncMock` �� `AsyncMock(return_value=...)`��sync �����Ƿ��� `MagicMock`�������� `await xxx()` ��Ŀ���Ƿ������ `async def`���Ƿ��� `pytest.mark.asyncio` ��ע async ���ԣ�**����**������ async/sync �������ԣ�**������**����ͬ�����롢�� mock �Ķ˵��˲��ԣ������� `config.yaml` �� `test_quality_protection.async_sync_test_match` �ڵ�����`enabled` / `severity` / `mock_class_for_async` / `mock_class_for_sync` / `await_required_for_async`����
128. ??v4.49.1 ��ǿ�ơ�**B-REVIEW-231 PROPERTY-RENAME-SERIALIZE-FIELD-SEP**���������������ع����շ�����Σ�ʱ�����Ƿ�ͬ�����£������л�Э���ֶ����Ƿ���ԭֵ�������������������δͬ�����²��Զ��ԡ����л��ֶ�������������һ��ĵ���ǰ�����Լ���ѵ�Υ��ģʽ�����������������ع�ʱ�����л��ֶ�����`alias` / `serialization_key`���Ƿ񱣳ֲ��䣻���Զ����Ƿ�ͬ�����µ��������������л������JSON / dict�����ֶ����Ƿ���ǰ����Լһ�£��Ƿ��� `alias` װ������ `Field(alias=...)` ���������������л��ֶ�����**����**���������������ع�����������л�������**������**�����ڲ������ࡢ�����л������ DTO�������� `config.yaml` �� `test_quality_protection.property_rename_serialize` �ڵ�����`enabled` / `severity` / `require_alias_separation` / `serialization_field_name_stability`����
129. ??v4.49.1 ��ǿ�ơ�**B-REVIEW-232 FASTAPI-ENDPOINT-SIGNATURE-TEST-SYNC**��FastAPI �˵�ǩ������ `request: Request` / `user_id: str` �Ȳ���ʱ�������Ƿ����Ӧ���������˵�ǩ�������������þ�ǩ�����á�mock ȱ�� `request` / `user_id` ������Υ��ģʽ�����˵�ǩ�����������󣬲����� mock �ĵ����Ƿ�ͬ�����²����б���Ƿ��� `Mock(spec=endpoint)` ������ǩ����飻`request: Request` ע��ʱ�Ƿ��ڲ����й��� `Request` ������� `AsyncMock(spec=Request)`��`user_id` �Ƿ��� `request.state.user_id` ����ȷ��ȡ��**����**��FastAPI �˵�ǩ���������������ע�������**������**�����������ԡ���ǩ������������� `config.yaml` �� `test_quality_protection.fastapi_endpoint_test_sync` �ڵ�����`enabled` / `severity` / `detect_signature_drift` / `required_test_param_match`����
130. ??v4.49.1 ��ǿ�ơ�**B-REVIEW-233 SOFT-DELETE-CATEGORY-ISOLATION**������ͳ���Ƿ����� NULL ������¶�������δ���ࣩ����ɾ�����������ͳ�ƣ���������ͳ�ƽ� NULL ����ɾ��������������¹¶����ݱ�������������ɾ�����ݱ��������δ�����Υ��ģʽ�����Ƿ��� `CASE WHEN fk IS NULL THEN 'uncategorized' WHEN deleted_at IS NOT NULL THEN 'skip' ELSE category END` ���ࣻNULL ����Ƿ���롸δ���ࡹͰ����ɾ������Ƿ�����ͳ�ƣ��Ƿ��ڷ���ͳ�Ʋ�ѯ����ʽ�������������**����**��������ɾ�� + �������ͳ�ƵĲ�ѯ��**������**������ɾ���ı�����������Ĳ�ѯ�������� `config.yaml` �� `soft_delete_data_isolation` �ڵ�����`enabled` / `severity` / `classification_rules.orphan_rule` / `classification_rules.deleted_rule`����
131. ??v4.49.1 ��ǿ�ơ�**B-REVIEW-234 ES-RESILIENCE-PRECHECK**��SonarQube ɨ��ǰ�Ƿ��� ES `read_only_allow_delete` �������������ɨ��ǰδ�� ES ����Ԥ�졢ɨ���� ES �������� CE ����д��ʧ�ܵ�Υ��ģʽ����ɨ��ǰ�Ƿ���� `GET _cluster/settings` ��� `read_only_allow_delete`����⵽�����Ƿ���� `PUT _cluster/settings` �������Ƿ��¼������־�����ǰ��״̬���Ƿ�� ES ���ɴ��������������������Ԥ�쵫��¼ WARNING����**����**��SonarQube ȫ��ɨ�衢���� ES д�������������**������**�������� ES ��ɨ�衢ES �������������������� `config.yaml` �� `es_resilience_precheck` �ڵ�����`enabled` / `severity` / `es_endpoint.host` / `es_endpoint.port` / `read_only_indicator` / `unlock_action`����
132. ??v4.49.1 ��ǿ�ơ�**B-REVIEW-235 PYTEST-TIMEOUT-CONFIG**��`pyproject.toml` �Ƿ����� `pytest-timeout` ��ʱ�������ģ�����׼��޳�ʱ���������⿨������ CI ���峬ʱ��Υ��ģʽ�����Ƿ��� `pyproject.toml` �� `[tool.pytest.ini_options]` ���� `timeout = N`���Ƿ���������� `@pytest.mark.timeout(N)` ������ע�����ģ�����׼��Ƿ�������У����� �� `max_tests_per_batch`�����Ƿ�Ե������������г�ʱ���ף�**����**�����ģ�����׼�����100 �����ԣ���CI ��ˮ�߲��ԣ�**������**��С�Ͳ��Լ���<50 ���������ؿ��ٲ��ԣ������� `config.yaml` �� `test_quality_protection.pytest_timeout_config` �ڵ�����`enabled` / `severity` / `default_timeout_seconds` / `slow_test_marker` / `max_tests_per_batch`����
133. ??v4.49.1 ��ǿ�ơ�**B-REVIEW-236 MULTI-USER-ID-PROPAGATION**���˵��ȡ `request.state.user_id` ���Ƿ����������� service / repository / external_api ��������ȷ���ݣ����˵�ȡ�� `user_id` ��ֻ��ֲ�������δ�������� service ���¿��û�������Ⱦ��Υ��ģʽ�����Ƿ��� route �� service �� repository �� external_api ȫ��·͸�� `user_id`���Ƿ��� `user_id` ��Ϊ�������`cache[user_id][...]`�����Ƿ��� `user_id` ��Ϊ�ļ�·��ά�ȣ�`cookies_{user_id}.json`�����Ƿ��� `user_id` ��Ϊ DB ��ѯ����������`WHERE user_id = ?`����ȱʧ `user_id` ʱ�Ƿ񽵼��� `default` �û�����¼ WARNING��**����**�����û�ϵͳ�����⻧ϵͳ�����˺Ź����**������**�����û����ߡ��ڲ�΢����ͨ�ţ������� `config.yaml` �� `multi_user_id_propagation` �ڵ�����`enabled` / `severity` / `user_id_source` / `default_value` / `required_propagation_layers`����

---

## 审查流程�? 阶段流水线）

> v4.28.0 优化：从 5 阶段闭环精简�?4 阶段流水线，合并前置检查与上下文收集为"上下文加�?，新�?优先级分�?阶段（P0/P1/P2/P3 四级），结果呈现改为结构化报告模板�?

**按需加载 references 的触发条�?*：本技能含 12 �?`references/*.md` 主题文件，是 36 维度规则的细化展开。日常审查只需预加载头部索引表 + 关键章节�?*仅在以下场景**按需读取对应文件，避免一次性全量加载消耗过�?token�?

| 触发条件 | 加载文件 |
|----------|----------|
| 文件�?`repo_*.py` / `db_models.py` / `session.execute` / `poolclass=` | `references/sqlalchemy.md` + `references/architecture.md` |
| 文件�?`async def` / `await` / `asyncio.gather` / `BackgroundScheduler` | `references/async-and-concurrency.md` |
| 文件�?`hmac` / `keyring` / `secrets` / `auth` / `token` / `password` | `references/security.md` |
| 文件�?`time.perf_counter` / `N+1` / `cache` / `time complexity` | `references/performance.md` |
| 文件�?`try/except` / `raise` / `logger.` / `tenacity` | `references/consistency-and-state-checks.md` |
| 文件�?`read_csv` / `open(` / `encoding=` / `yaml.safe_load` / `json.loads` | `references/encoding-and-io.md` |
| 文件�?`dataclass` / `@dataclass` / 重复字符�?/ 注释与代�?| `references/maintainability.md` |
| 文件�?`yaml` / `config.yaml` / `get_config` / `_DRY_RUN` 字面�?| `references/yaml-and-config.md` |
| 文件�?`browser` / `playwright` / `Page` / `Context` | `references/browser-subprocess-patterns.md` |
| 文件�?`cache` / `TTL` / `invalidate_cache` / `_save_progress` | `references/cache-state-migration-patterns.md` |
| 文件含 `__all__` 变更 / 常量改函数 / `from xxx import` 改名 / `config.yaml` 新增配置块 / `_get_xxx()` 函数 / `| Select-Object -Last` / `Start-Process -RedirectStandardOutput` | `references/refactoring-safety-checks.md` |
| 触发 36 维度中的任一维度（需查具体判断信�?历史教训�?| `references/checkpoints-index.md`（按 ID 检索） |
| 完整速查问题-原因-方案 | `references/quick-troubleshooting.md` |
| 历史上某版本为何新增/废弃某项检查点 | `references/version-changelog.md` |
| 文件含 `ai_usage.py` / `embedding_service.py` / `UsageRecord` / `record_usage` / `check_budget` / `billable` / `_today_key` / `_date_key_of` / `input_tokens_override` / `cost_override` | `references/xianyu-walkthrough-cases.md` |
| 需要回顾「本次走查→修复→评审技能建设」的完整方法论复盘（四维度） | `references/review-process-retrospective.md` |

预加载建议：仅头部索引表（行 17-63�? `## 配置驱动` 章节 + `## 审查流程` 章节 + 当前审查文件的依赖对应文件�?

### 阶段 1：上下文加载

1. **加载配置**：读�?`config.yaml`（含 v4.28.0 新增�?`coding_standards` 节点，覆�?datetime/migration/null_defense/query_filter/enum_consistency/error_attribution/log_noise/circuit_breaker/state_sync/credential_stores/retry/param_chain/dataclass/startup/mock/cookie/parser/encoding/dry/contract/persist/race/keywords 23 个子节点�?
2. **确定评审范围**�?
   - **待提交变更模�?*：`git diff HEAD` + `git status` 提取改动�?`.py` 文件
   - **指定文件模式**：用户明确指定的文件列表
   - **片段评审模式**：用户粘贴的代码片段（无文件路径时仅输出建议�?
   - 应用 `scope.include_paths` / `scope.exclude_paths` 过滤，截�?`scope.max_files_per_run` 个文�?
3. **识别任务类型**：前�?/ 后端 / 全栈（本技能专注后端，前端�?`xianyu-frontend-code-review` 处理�?
4. **加载对应 coding-rules/ 主题文件**：根据评审范围加�?`references/` 下的架构/异步并发/SQLAlchemy/安全/性能/缓存状�?编码 IO/可维护�?YAML 配置等主题文�?
5. **收集文件上下�?*：对每个待评审文件，使用 Read 读取完整内容，使�?Grep 查找关键依赖（导入模�?项目内调�?DB 表引用），使�?Grep 查找相关测试文件评估测试覆盖，记�?`git log --oneline -5 -- <file>` 修改历史

**判断逻辑**：范围必须收紧——只评审用户提供的或明确引用的文件，不顺便审查旁边代码�?

### 阶段 2：分层扫�?

�?`checklist` 配置�?29 大类逐层扫描（见上文"审查规则"章节），每个维度引用对应 B-REVIEW checkpoints�?

1. **维度 1-6（架�?Pydantic/SQLAlchemy/SQLite�?*：引�?B-REVIEW-121~126（时区一致�?原生 SQL 类型防御/迁移步骤独立�?NOT NULL 字段防御/查询过滤条件精确�?状态值枚举一致性）
2. **维度 7-12（安�?性能/异步/事件总线/错误处理/日志�?*：引�?B-REVIEW-127~131（错误归因精细化/异常传播完整�?错误消息透传/重试策略配置�?已知场景日志降噪�?
3. **维度 13-19（代码质�?配置管理/智能客服/Git/Chrome 适配/跨字�?API 设计�?*：引�?B-REVIEW-138~146（参数传递链/业务关键词配置化/开关持久化/凭证多存储同�?属性调用一致�?API 契约一致�?命名语义清晰�?重复逻辑抽取/跨进程编码一致性）
4. **维度 9（异步与调度器）扩展**：引�?B-REVIEW-132~137（熔断器持久化对称�?状态切换原子�?多源失效判定一致�?缺失数据回退策略/多源状态同步标记机�?异步竞态防护）
5. **维度 20-29（测�?Composition Root/多用户隔�?LLM 能力派发/端到端失败原因链�?*：引�?B-REVIEW-147~150（dataclass 字段显式声明/启动钩子完整�?测试 Mock 类型匹配/Cookie 完整性管理）

**扫描方法**：对每个维度，使�?Grep 工具扫描代码库（pattern 字段），对比反模式示例识别问题，匹配到的违规项记录到报告�?*硬约束违规优先级最�?*，无�?severity 如何，必须在报告中突出显示�?

### 阶段 3：优先级分类

#### v4.60.0 专项检查步骤

6. **缓存守卫专项检查**：所有涉及缓存的代码变更，验证三原则（TTL配置化/空结果不缓存/缓存条件独立）。引用 B-REVIEW-275 CACHE-GUARD-3RULES，扫描 `TTL=` / `cache[` 等模式，确认 TTL 从 config 读取、空结果跳过缓存、缓存写入守卫独立于业务逻辑
7. **跨层影响范围评估**：修改后端字段时，自动评估前端 `types.ts` / `Config.tsx` 影响。引用 B-REVIEW-279 CROSS-LAYER-CLOSED-LOOP，检查 cookie_store / token_renewer / db_row / frontend_types 各层状态同步，确认 `sync_state_from_xxx()` 闭环
8. **状态机流转完整性检查**：涉及 scheduler/session 状态流转的代码，验证返回值语义+闭环。引用 B-REVIEW-277 STATE-MACHINE-RETURN，检查 `return True/False` 语义是否与调用方逻辑对齐，确认返回值文档化

#### v4.61.0 重构安全性专项检查

> 触发条件：`git diff` 含常量改函数 / `__all__` 变更 / `from xxx import` 改名 / `config.yaml` 新增配置块 / `_get_xxx()` 函数新增 / PowerShell 脚本中的 `| Select-Object -Last` 模式。配套文件 `references/refactoring-safety-checks.md`，所有阈值通过 `config.yaml#refactoring_safety` 节点管理。

9. **配置化重构 5 步法核对**：检测到"常量 → 函数"或"常量 → Config 字段"的变更时，强制核对 5 步法是否完整执行。引用 B-REVIEW-281 CONFIG-REFACTOR-5STEP，grep 旧常量名确认所有引用点已更新（含 import 语句、文档字符串、注释），`_get_xxx()` 函数内必须含异常回退到默认值。历史失败案例：`container.py:450` `self.config.buyer` 误用 self、`startup.py:161` import 未同步更新
10. **作用域契约校验**：对配置化重构后的调用点，核对函数签名与变量访问是否匹配。引用 B-REVIEW-282 SCOPE-CONTRACT-CHECK，模块级函数禁用 `self`/`cls`，静态方法禁用 `self`/`cls`，常量改函数后原 `self.config.xxx` 调用必须改为 `cfg = get_config(); cfg.xxx`
11. **跨文件引用同步校验**：检测到导出符号删除/改名时，必须确认有运行时验证步骤。引用 B-REVIEW-289 CROSS-FILE-REFERENCE-SYNC（与 B-REVIEW-283 IMPORT-NAME-CHECKLIST 配套），重构后必须启动服务或运行测试，捕获 `ImportError` / `NameError`（异常清单在 `config.yaml: refactoring_safety.cross_file_sync.catch_exceptions` 管理）
12. **配置访问统一入口检查**：扫描模块级硬编码业务参数常量（如 `_LIVE_CACHE_TTL = 60`）。引用 B-REVIEW-290 CONFIG-ACCESS-UNIFIED-ENTRY，业务参数（TTL/超时/阈值/间隔/重试次数/批次大小）必须从 `config.yaml` 通过 `get_config()` 读取，禁止模块级硬编码，`_get_xxx()` 函数必须有异常回退。历史失败案例：`_LIVE_CACHE_TTL` 重构为 `CacheConfig.live_search_ttl`
13. **PowerShell 长任务日志输出检查**：审查 `scripts/` 目录下 `.ps1` 文件，检测 `| Select-Object -Last` 等 sink cmdlet。引用 B-REVIEW-284 POWERSHELL-LONG-TASK-OUTPUT，执行时长 > `long_task_threshold_sec`（默认 30 秒，由 config 管理）的命令必须用 `> <file>` 重定向 + `Get-Content -Tail N <file>` 查看，禁止 sink cmdlet 缓冲整流导致内存爆涨。引用 B-REVIEW-285 RESOURCE-OVERLOAD-TOLERANCE，完整 pytest 超时（> `full_test_timeout_sec` 默认 300 秒）时降级为 Tier 2 直接 import 测试或 Tier 3 改动文件验证

按问题严重程度分�?4 级（替代�?severity_order × category_order 矩阵）：

- **P0 阻塞�?*：安全漏�?/ 数据丢失 / 崩溃 / 硬约束违规（必须修复才能合并�?
  - 示例：Token 比较�?`==`（B-REVIEW 硬约束）、SQLite �?`StaticPool`、`datetime.utcnow()` 弃用、敏感字段明文存�?
- **P1 严重**：逻辑错误 / 性能问题 / 状态不一�?/ 异常吞掉（应该修复）
  - 示例：B-REVIEW-121 时区一致性（TypeError 崩溃）、B-REVIEW-128 异常传播完整性（隐藏问题）、B-REVIEW-132 熔断器持久化对称性（状态丢失）
- **P2 改进**：代码质�?/ 可维护�?/ 配置�?/ 重复逻辑（建议修复）
  - 示例：B-REVIEW-130 重试策略配置化、B-REVIEW-139 业务关键词配置化、B-REVIEW-145 重复逻辑抽取
- **P3 微调**：风�?/ 注释 / 命名优化（可选修复）
  - 示例：B-REVIEW-144 命名语义清晰性、注释一致性、变量名优化

**分类规则**：硬约束违规统一�?P0；影响功能正确�?稳定性为 P1；影响可维护�?配置化为 P2；纯风格�?P3�?

### 阶段 4：结果呈�?

按结构化报告模板生成报告（见下文"输出模板"章节）。报告内容包括：
1. **审查概览**：审查范�?审查维度/问题统计（P0/P1/P2/P3 数量�?规范版本
2. **问题详情**：每个问题含编号/维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示�?优先�?
3. **与上次审查对�?*：🆕新�?/ ✅已修复 / ⚠️仍存�?
4. **好的实践**：正面反�?
5. **测试运行结果**（若 `verify.run_tests_after_review=true`�?
6. **审查结论与修复验证指�?*


#### v4.60.0 审查结果呈现优化

7. **按风险等级分组**：CRITICAL(安全/数据丢失) > WARNING(缓存/状态) > INFO(风格/优化)，同优先级内按风险等级排序
8. **防回归标记**：每个修复点标记对应测试模式（如 `test_cache_guard_ttl` / `test_field_strategy_coalesce` / `test_state_machine_return_semantics`），确保修复可验证
9. **跨层影响图**：显示变更的跨层传播路径（如 cookie_store → token_renewer → db_row → frontend_types），标识受影响的层级和字段

#### v4.61.0 重构安全性结果呈现

10. **重构安全性章节**：报告必须含独立的"重构安全性"章节（见 templates/report-template.md），包含 4 个子节：
    - **配置化重构核对**：列出 5 步法每步的执行状态（✅ 已执行 / ❌ 未执行 / ⚠️ 部分执行），引用旧常量名 → 新函数名映射表
    - **跨文件引用影响图**：显示导出符号变更的跨文件传播路径（如 `module_a.OLD_CONST` → `module_b._get_new_const()` → `module_c.import`），标识受影响的文件和行号
    - **运行时验证结果**：记录启动服务/运行测试的验证结果（通过/失败），捕获的 `ImportError` / `NameError` 异常清单
    - **硬编码业务参数清单**：列出扫描到的模块级硬编码业务参数常量（如 `_LIVE_CACHE_TTL = 60`），标注应迁移到的 Config 字段
11. **历史失败案例引用**：每个重构安全性违规必须引用对应的历史失败案例（container.py:450 / startup.py:161 / _LIVE_CACHE_TTL），说明"为什么这么做"的真实教训
12. **测试验证档位标记**：报告末尾标注本次审查使用的测试验证档位（Tier 1/2/3）及降级原因（若适用），引用 `config.yaml: refactoring_safety.test_verify_tiers` 配置
---

## 评审范围判断

- **待提交变更模�?*：`git diff HEAD --name-only` + 过滤 `.py` 文件
- **指定文件模式**：用户明确列出文件路�?
- **片段模式**：用户粘贴代码但无文件路径（仅输出建议，不输�?File:Line�?
- **范围必须收紧**：不顺便审查旁边代码，不主动扩展到未提及的文�?

## 误报识别判断

- 路径匹配 `scope.exclude_paths`：跳�?
- 测试文件中的规范类问题：降级处理
- 生成代码（含 `# @generated` 注释�?`__pycache__` 路径）：跳过
- 第三方库代码：跳�?
- 迁移文件（`_migrate_*` 函数）：幂等性已保证，不再要求事务包�?

## 修复建议判断

- 必须提供可操作的修复建议（含代码示例�?
- 建议必须解释"为什�?而非�?做什�?
- 若问题需要代码修改，在报告末尾询问用户是否应用修�?

## 失败恢复机制

1. **文件读取失败**：记录跳过原因，继续评审其他文件
2. **Grep 超时**：缩小搜索范围或跳过该检查项
3. **测试运行失败**：输出测试失败信息，不阻止报告生�?
4. **配置文件缺失**：使用内置默认配置并提示用户创建 `config.yaml`

---

## 审查判断标准

| 🟠阻塞(必须修复) | 🟠严重(强烈建议) | 🟡警告(建议) |
|-----------------|-----------------|-------------|
| 违反分层架构（跨层调用） | 服务调用缺必需字段 | 格式化不规范 |
| 缺失模块级导入（re/threading/logging�?| 未查看服务方法实�?| 变量命名不规�?|
| Token 比较未用 `hmac.compare_digest()` | 异常处理不完善（吞异�?丢堆栈） | 冗余代码 |
| 硬编码密�?密钥/钉钉推�?Key | 空指针风险（链式调用未判空） | 注释不清�?|
| SQL 字符串拼接（未用 `_escape_like`�?| N+1 查询/循环�?DB | 魔法数字未提取常�?|
| 凭据明文写入 `config.yaml` | 日志含敏感信�?| 函数过长 |
| 使用已弃�?`datetime.utcnow()` | async 代码中阻�?IO | 缺少类型注解 |
| SQLite 引擎�?`StaticPool`（应�?`NullPool`�?| `asyncio.Task` 未保留引�?| 缺少测试 |
| WebView2 �?`CREATE_NO_WINDOW` | `CancelledError` 被静默吞�?| 嵌套层级过深 |
| WebView2 重定向到 `DEVNULL` | `EventBus` 消费者未处理 `QueueEmpty` | 注释复述代码 |
| �?`except:` + `pass` | 未设�?`HF_ENDPOINT` 镜像 | DTO 未实�?Serializable（Pydantic 默认�?|
| Pydantic 1.x `.dict()` / `.json()` | `sentence-transformers` 跨版本未 fallback | 路由缺少 tags |
| `config/config.yaml` 明文暴露凭据 | `ChatbotOrchestrator` 持有请求级状�?| 缺少文档字符�?|
| GET 请求引发状态变�?| `_scan_and_chunk` 未排�?`web/static/` | 缺少 `__all__` |
| 响应返回 ORM 对象（非 DTO�?| `_overview()` 未用 CASE WHEN 合并 | 魔法字符�?|
| 必填字段缺失索引 | Web 进程未用 `with_browser=False` | - |
| `webview.start()` 未设 `private_mode=False` | `PriorityBrowserLock` 优先级缺�?| - |
| 循环依赖 A→B→C→A | `Container` 未深拷贝 chatbot 配置 | - |
| `local_embedding.py` 未设 HF 镜像 | Evaluator 接受覆盖参数 | - |
| 产物文件（`.scannerwork/` 等）�?git track | 异步方法调用遗漏 `await` | - |
| 🆕 �?`await` �?`async` 函数（S7503�?| 🆕 重复字符串字面量 �?2 处未提取为常量（S1192�?| - |
| 🆕 认知复杂�?> 15 未拆分（S3776�?| 🆕 复杂正则未拆分（S5843�?| - |
| 🆕 未使用的参数/属�?局部变量（S6767�?| 🆕 `Evaluator` 接受 `thresholds/weights/keywords` 覆盖参数 | - |
| 🆕 `asyncio.CancelledError` �?`except: pass` 静默吞掉 | 🆕 KB 索引未排�?`web/static/` 等前端构建产�?| - |
| 🆕v4.0 "已完�?事件在业务逻辑前触发（EVAL_PASSED 前置�?| 🆕v4.0 字段覆盖一刀�?只填缺失"（应按语义分类） | - |
| 🆕v4.0 资源创建接口非幂等（重复调用重复创建�?| 🆕v4.0 搜索接口参数/响应结构不统一 | - |
| 🆕v4.0 注释与代码逻辑不一致（误导性约束说明） | 🆕v4.0 动态资源映射表与推断函数混�?| - |
| 🆕v4.1 重试失败后未检查状态标志直接走成功流程（B-REVIEW-SESSION-SIGNAL�?| 🆕v4.1 Cookie 检查只覆盖身份 Cookie，忽略会�?token（B-REVIEW-COOKIE-CHECK�?| - |
| 🆕v4.1 错误粒度不区分（401/403/502/503/504 混用�?| - | - |
| 🆕v4.2 语义关联字段矛盾（如 gpu_vendor 配不匹配�?gpu_renderer�?| 🆕v4.2 跨组件对同一概念判断维度未同�?| - |
| 🆕v4.2 Cookie/HTTP属性硬编码（批�?httpOnly:True�?| 🆕v4.2 错误提示引用不存在的端点 | - |
| 🆕v4.2 run_coroutine_threadsafe + future.result() 死锁组合 | - | - |
| 🆕v4.2 try/finally 变量未初始化�?None | - | - |
| 🆕v4.3 v20 加密�?`CryptUnprotectData` 离线解密（应 CDP 接管）（B-REVIEW-ENCRYPTION-DEGRADATION�?| 🆕v4.3 �?profile 发现只读 Default（应�?`profile.info_cache`+fallback 扫描）（B-REVIEW-MULTI-PROFILE-DISCOVERY�?| - |
| 🆕v4.3 SQLite 文件锁报错未�?`immutable=1` URI 绕过（B-REVIEW-FILE-LOCK-BYPASS�?| 🆕v4.3 高风险功能默认启用（应默认关�?配置驱动）（B-REVIEW-CONFIG-DRIVEN-TOGGLE�?| - |
| 🆕v4.3 后台任务复用主调度器（应独立 BackgroundScheduler）（B-REVIEW-SCHEDULER-ISOLATION�?| 🆕v4.3 多方案失败无 backoff 策略（应配置驱动 max_failures/max_interval）（B-REVIEW-FALLBACK-CHAIN�?| - |
| 🆕v4.3 Chrome 136+ �?`--remote-debugging-port` �?`--user-data-dir` 非标准目录（B-REVIEW-CHROME-136-ADAPTATION�?| 🆕v4.3 测试 Windows 环境变量未用 `tmp_path` mock（路径结构与实现不一致）（B-REVIEW-WINDOWS-TEST-MOCK�?| - |
| 🆕v4.3 使用 pytest 插件未在 `pyproject.toml` 声明（运行时�?unrecognized arguments）（B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK�?| - | - |
| 🆕v4.4 错误码映射语义不匹配（如 RGV587=token 过期映射�?401 登录失效）（B-REVIEW-ERROR-SEMANTICS�?| - | - |
| 🆕v4.4 配置项注入到中间层但消费层未读取（配置无效化）（B-REVIEW-CONFIG-LINKAGE�?| - | - |
| - | 🆕v4.4 fast=True 失败后无降级重试（B-REVIEW-FAST-DEGRADATION�?| - |
| - | 🆕v4.4 硬编码阈值替代已有配置项（B-REVIEW-NO-HARDCODED-THRESHOLD�?| - |
| - | 🆕v4.4 方法签名新增参数后内部调用点遗漏传递（B-REVIEW-PARAM-PASS-THROUGH�?| - |
| 🆕v4.9 状态机无白名单转换规则，散落式 `if status=='X': status='Y'`（B-REVIEW-STATE-MACHINE-WHITELIST�?| 🆕v4.9 终态可复活 / 中间态无超时清理 / deadline 无限重置（B-REVIEW-STATE-MACHINE-WHITELIST�?| - |
| 🆕v4.9 可注册组件无 cleanup 钩子 / asyncio.Task 未保留引用被 GC（B-REVIEW-RESOURCE-CLEANUP-HOOK�?| 🆕v4.9 try/finally 资源未前置初始化�?None / gather 未用 return_exceptions（B-REVIEW-RESOURCE-CLEANUP-HOOK�?| - |
| - | 🆕v4.9 双链路共用前置条件重复实现，未抽离为共享函数（B-REVIEW-DUAL-LINK-CONSISTENCY�?| - |
| 🆕v4.9 共享状态检�?更新未在同一锁内（`if not active: start()` 错误模式）（B-REVIEW-CONCURRENT-STATE-LOCK�?| 🆕v4.9 dataclass 字段�?`getattr` 兜底 / 锁内 `await` / 锁粒度过大（B-REVIEW-CONCURRENT-STATE-LOCK�?| - |
| - | 🆕v4.9 �?`get_event_loop().create_task` 替代 `asyncio.create_task` / `except BaseException` �?CancelledError（B-REVIEW-PYTHON-MODERN-ASYNCIO�?| - |
| 🆕v4.8 状态标志设置后无前置检查（B-REVIEW-STATE-FLAG-PRECHECK�?| 🆕v4.8 日志降级判断用魔法字符串（B-REVIEW-LOG-DOWNGRADE-STABILITY�?| - |
| 🆕v4.8 状态标志无重置机制（等于永久禁用） | 🆕v4.8 修改后未验证生效（B-REVIEW-EDIT-VERIFY�?| - |
| 🆕v4.61 模块级函数误用 `self`/`cls`（B-REVIEW-282 SCOPE-CONTRACT-CHECK） | 🆕v4.61 PowerShell 长任务用 `\| Select-Object -Last` sink cmdlet（B-REVIEW-284） | - |
| 🆕v4.61 删除/重命名导出符号前未 grep 所有引用点（B-REVIEW-283 IMPORT-NAME-CHECKLIST） | 🆕v4.61 完整 pytest 超时无降级策略（B-REVIEW-285 RESOURCE-OVERLOAD-TOLERANCE） | - |
| 🆕v4.61 配置化重构后未执行运行时验证（B-REVIEW-289 CROSS-FILE-REFERENCE-SYNC） | 🆕v4.61 SonarQube 扫描单阶段失败终止整条链路（B-REVIEW-286） | - |
| 🆕v4.61 模块级硬编码业务参数常量 `_LIVE_CACHE_TTL = 60`（B-REVIEW-290 CONFIG-ACCESS-UNIFIED-ENTRY） | 🆕v4.61 SonarQube ES read-only 锁无自愈（B-REVIEW-287 RESILIENCE-RECOVERY） | - |
| 🆕v4.61 配置读取函数无异常回退到默认值（B-REVIEW-281 CONFIG-REFACTOR-5STEP） | 🆕v4.61 审查验证阶段未按三档策略选择测试粒度（B-REVIEW-288 TEST-VERIFY-TIERS） | - |

---

## 与现有工具的关系

- **xianyu-hunter-dev**：开发技能，本技能与之配合（开发完成后用本技能审查）
- **backend-code-review**（全局技能）：本技能参考其输出模板，但增加了闲鱼项目专属的硬约束和 24 维度检查清�?
- **xianyu-frontend-code-review**：前后端协同评审时配合使�?
- **xianyu-sonarqube-mcp**：SonarQube 修复后的二次人工评审使用本技�?
- **xianyu-logs-review**：运行时日志分析使用该技能，不使用本技�?
- **systematic-debugging**：纯调试场景使用该技能，不使用本技�?
- **skill-creator**：本技能由 skill-creator 创建

---

## 安全注意事项

1. **凭据**：报告中不包含任�?token、密码等敏感信息
2. **硬编码检�?*：硬约束规则 `no_hardcoded_credentials` 会扫描代码库
3. **凭据泄露建议**：若发现已泄露凭据（�?`config/config.yaml` 明文），建议立即吊销并提示操作步�?
4. **报告脱敏**：日�?报告中的 token、cookie 必须�?`***` 占位

---

## 示例用法

### 场景1：迭代发布前评审

用户�?对这次迭代的后端修改进行代码评审"

技能执行：
1. 读取 `config.yaml`
2. `git diff HEAD --name-only` 提取改动�?`.py` 文件
3. 逐文件读取并�?29 大类检�?
4. 硬约束合规性扫�?
5. 生成评审报告

### 场景2：指定文件评�?

用户�?评审 src/xianyu_hunter/web/routes/api_tasks.py"

技能执行：
1. 读取 `config.yaml`
2. 读取指定文件
3. 按检查清单评�?
4. 生成评审报告

### 场景3：仅评审安全问题

用户修改 `config.yaml`�?
```yaml
checklist:
  security: true
  architecture: false
  type_annotation: false
  pydantic: false
  sqlalchemy: false
  sqlite_optimization: false
  performance: false
  async_scheduler: false
  event_bus: false
  error_handling: false
  logging: false
  code_quality: false
  config_management: false
  process_management: false
  composition_root: false
  chatbot: false
  web_layer: false
  api_design: false
  testing: false
  naming: false
  layering: false
  project_specific: false
  git_ops: false
```

技能执行：只检查安全类问题�?

---

## 输出模板

当本技能被调用时，响应必须严格遵循以下模板之一�?

### Template A（有问题�?

```markdown
# Code Review Summary

Found <X> critical issues need to be fixed:

## 🔴 Critical (Must Fix)

### 1. <brief description of the issue>

FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<detailed explanation and references of the issue>

#### Suggested Fix

1. <brief description of suggested fix>
2. <code example> (optional, omit if not applicable)

---
... (repeat for each critical issue) ...

Found <Y> suggestions for improvement:

## 🟡 Suggestions (Should Consider)

### 1. <brief description of the suggestion>

FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<detailed explanation and references of the suggestion>

#### Suggested Fix

1. <brief description of suggested fix>
2. <code example> (optional, omit if not applicable)

---
... (repeat for each suggestion) ...

Found <Z> optional nits:

## 🟢 Nits (Optional)
### 1. <brief description of the nit>

FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<explanation and references of the optional nit>

#### Suggested Fix

- <minor suggestions>

---
... (repeat for each nits) ...

Found <W> config node missing issues (🆕v4.31):

## ⚙️ Config Node Missing (v4.31)

> 本分类专门记�?v4.31+ 配置驱动检查发现的配置节点缺失问题。当代码中引用了 v4.31+ 检查点�?`config.yaml` 中对应配置节点缺失或 `enabled: false` 时，记录在此分类。配置节点缺失会导致配置驱动检查无法生效，必须补充配置才能启用对应审查能力�?

### 1. <brief description of the missing config node>

Config Node: `<node_path>` (expected in `config.yaml`)
Related B-REVIEW: <B-REVIEW-XXX-XXX>
Current State: <missing | enabled: false | incomplete>

#### Explanation

<detailed explanation of why this config node is required and what B-REVIEW checkpoint it enables>

#### Suggested Fix

1. �?`config.yaml` �?`<node_path>` 节点下补充以下配置：
```yaml
<node_path>:
  enabled: true
  <parameter1>: <value1>
  <parameter2>: <value2>
```
2. 参�?`config.example.yaml` �?`<node_path>` 节点获取完整参数清单

---
... (repeat for each config node missing) ...

## �?What's Good

- <Positive feedback on good patterns>
```

- 若某分类无问题，省略该分类的整个 section
- 若问题数超过 10 个，概括�?"Found 10+ critical issues/suggestions/optional nits/config node missing" 并仅输出�?10 �?
- 不要压缩 section 之间的空行，保持可读�?
- 🆕v4.31 配置节点缺失分类�?CRITICAL 级别，必须修复才能启用对应审查能�?
- 若有任何问题需要代码修改，在结构化输出后追加简短的后续问题，询问用户是否应用修复。例如："是否需要我使用 Suggested Fix 来修复这些问题？"

### Template B（无问题�?

```markdown
## Code Review Summary
�?No issues found.
```

### Template C（v4.28.0 结构化报告，推荐�?

> v4.28.0 新增：结构化报告模板，含审查概览 + 问题详情，每个问题包含编�?维度/规范引用/代码位置/修复建议/配置节点/反模式示�?优先级。优先使用此模板�?

```markdown
## 代码审查报告

### 审查概览
- 审查范围：[文件列表]
- 审查维度：[命中的维度列表，�?6 SQLite 优化 / 9 异步与调度器 / 11 错误处理]
- 问题统计：P0=[n] P1=[n] P2=[n] P3=[n]
- 规范版本：xianyu-backend-code-review v4.28.0
- 配置版本：config.yaml coding_standards 节点 v4.28.0

### 问题详情

#### [P0] B-REVIEW-121 时区一致�?
- **规范引用**: DATETIME-TZ-01 时区一致性三步检查法
- **维度**: 6 SQLite 优化
- **代码位置**: repo_chatbot.py:478
- **问题描述**: `_utcnow()` 返回 aware，`row.created_at` �?naive，减法报�?`TypeError: can't subtract offset-naive and offset-aware datetimes`
- **修复建议**: 使用 `_utcnow().replace(tzinfo=None) - row.created_at` 统一�?naive（项目默认策略）
- **配置节点**: `coding_standards.datetime.default_timezone`（默�?`naive`�?
- **反模式示�?*:
  ```python
  diff = _utcnow() - row.created_at  # TypeError
  ```
- **正确模式**:
  ```python
  # �?正确：统一�?naive
  diff = _utcnow().replace(tzinfo=None) - row.created_at
  ```

---

#### [P1] B-REVIEW-127 错误归因精细�?
- **规范引用**: ATTRIB-01 错误归因精细�?
- **维度**: 11 错误处理
- **代码位置**: api_collection.py:234
- **问题描述**: 所有外部调用失败统一返回 502，前端无法区�?token 过期（需重新登录）与反爬（需等待重试�?
- **修复建议**: 根据 `failure_reason` 映射具体状态码�?01/429/503/502�?
- **配置节点**: `coding_standards.error_attribution.status_mapping`
- **反模式示�?*:
  ```python
  raise HTTPException(502)
  ```
- **正确模式**:
  ```python
  # �?正确：精细化映射
  status_map = {'token_expired': 401, 'anti_crawler': 429, 'page_unavailable': 503, 'other': 502}
  raise HTTPException(status_map.get(reason, 502))
  ```

---

... (repeat for each issue,�?P0 �?P1 �?P2 �?P3 顺序排列) ...

### 与上次审查对�?
- 🆕 新增：[新增问题列表]
- �?已修复：[已修复问题列表]
- ⚠️ 仍存在：[未修复问题列表]

### 好的实践
- <Positive feedback on good patterns>

### 审查结论
- 阻塞合并：[�?否]（P0 问题�?> 0 时阻塞）
- 修复优先级：先修�?P0，再 P1，P2/P3 可后续迭�?
- 修复验证：修复后重新执行本技能审查，确认 P0/P1 问题已解�?
```

**Template C 使用规则**�?
- v4.28.0 起优先使�?Template C（结构化报告�?
- 每个问题必须包含 8 个字段：编号/维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示�?
- 问题�?P0 �?P1 �?P2 �?P3 顺序排列
- 若某优先级无问题，省略该优先级的所有问�?
- 若问题数超过 10 个，在审查概览中标注 "10+ issues" 并仅输出�?10 �?
- 若有任何问题需要代码修改，在报告末尾询问用户是否应用修�?

---

## 重要提醒

1. 【强制】所有时间字段用 `_utcnow = lambda: datetime.now(timezone.utc)`，禁�?`datetime.utcnow()`
2. 【强制】SQLite 引擎�?`NullPool`，禁�?`StaticPool`
3. 【强制】Token 比较�?`hmac.compare_digest()`，禁�?`==`
4. 【强制】敏感字段写�?keyring，禁�?`config/config.yaml` 明文
5. 【强制】`local_embedding.py` 模块顶层�?`HF_ENDPOINT` 镜像
6. 【强制】提交前执行 `auto-scan.ps1`；完成后调用本技能走�?

---

## 快速问题定�?

完整的问�?原因-方案速查表（�?63 条）已迁移至 [references/quick-troubleshooting.md](references/quick-troubleshooting.md)。该表按问题类型分类（模块导�?数据�?SonarQube/日志/v4.0-v4.4 复盘/v4.8-v4.9 状态机�?Python 现代化）�?

---

## 附录A：硬约束来源

本技能的硬约束规则来源于�?
- `c:\Users\hspcadmin\.trae-cn\memory\projects\-d-code-otherProjects-17-xianyu\project_memory.md`
- `.trae/skills/xianyu-hunter-dev/references/project-rules.md`
- `.trae/skills/xianyu-backend-code-review/references/encoding-and-io.md` —�?字符编码�?I/O 边界审查要点（FAQ 乱码复盘提炼，ENC-01 ~ ENC-08�?
- `.trae/skills/xianyu-backend-code-review/references/consistency-and-state-checks.md` —�?多入口参数一致性、价格采集字段优先级、DOM 选择器排除、N+1 查询、json_extract vs LIKE、异常消息脱敏、计数器语义、状态检测关键词覆盖（实时搜�?价格不一�?商品删除复盘提炼�?3 �?B-REVIEW 检查点�?
- 历史代码评审记录（如 `config/config.yaml` 明文暴露钉钉凭据 Critical 安全事件�?

## 附录B：项目专属规�?

以下规范�?`config.yaml` �?`project_conventions` 节点维护�?

| 规范 | 说明 |
|------|------|
| `auth_whitelist` | 认证白名单端点（必须放行，不要求 token�?|
| `required_indexes` | 必须有索引的数据库字�?|
| `count_query_optimization` | COUNT 查询合并要求 |
| `webview2_config` | WebView2 配置要求 |
| `kb_index_whitelist` | 知识库索引白名单 |
| `kb_index_excludes` | 知识库索引排除路�?|
| `hf_endpoint` | HuggingFace 镜像 |
| `layering` | 分层依赖方向 |
| `immutable_dirs` | 不可移动目录 |
| `docker_stages` | Docker 三阶段构�?|
| `git_artifact_dirs` | 不应�?git track 的产物目录（�?`.scannerwork/`、`__pycache__/`�?|
| `git_conflict_strategy` | 合并冲突保留策略（如 `await` 异步版本优先�?|

## 附录C�?5 维度对照�?

| # | 维度 | 核心规则 |
|:--|:---|:---|
| 1 | 分层架构 | `web �?modules �?infra �?domain` 单向依赖 |
| 2 | 命名规范 | snake_case/PascalCase/*Row/*Config/_前缀 |
| 3 | 类型注解 | Python 3.10+ `X \| None`，全面注�?|
| 4 | Pydantic 2.x | `model_dump`、`Field` 约束、领域用 dataclass |
| 5 | SQLAlchemy 2.0 | `Mapped`、`_utcnow`、幂等迁移、`_escape_like` |
| 6 | SQLite 优化 | `NullPool`、WAL、busy_timeout、索引规约、🆕v4.3 文件锁绕过（SQLite immutable=1）、🆕v4.25 NOT NULL 字段 None 防御（B-REVIEW-111，区�?NOT NULL 字段防御�?pop 与覆盖字段写 None�?|
| 7 | 安全�?| `hmac.compare_digest`、keyring、SQL 注入防护、🆕v4.1 Cookie 检查全面性（身份 Cookie + 会话 token）、🆕v4.3 加密升级退化策略（v20 �?CDP 接管�?|
| 8 | 性能 | N+1 检测、`asyncio.to_thread`、缓�?|
| 9 | 异步与调度器 | `async def` 路由�? 类调度器、CancelledError、🆕v4.0 事件触发时机�?已完�?事件在业务逻辑完成后触发）、🆕v4.3 独立调度器隔离模式、🆕v4.25 共享单例污染防护（B-REVIEW-112，循环中任务级覆盖用 worker_xxx 局部变量） |
| 10 | 事件总线 | `asyncio.Queue`�?5 �?EventType、SSE lastEventId |
| 11 | 错误处理 | 三层兜底、保留堆栈、tenacity 重试、🆕v4.1 重试失败后状态信号传�?+ 错误粒度三类区分�?03/504/401/403/502）、🆕v4.3 降级链模式（多方�?backoff�?|
| 12 | 日志规约 | loguru �?sink、request_id 追踪、脱�?|
| 13 | 代码质量 | 模块级导入、SRP、嵌�?�?4、async/await 一致性、🆕v4.0 注释与代码一致�?|
| 14 | 配置管理 | pydantic-settings + keyring + .env 三层、🆕v4.3 配置驱动功能开关模式（高风险默认关闭） |
| 15 | 进程管理 | `CREATE_NEW_CONSOLE`、`private_mode=False`、🆕v4.3 Chrome 136+ 限制适配（remote-debugging-port + 非标�?user-data-dir�?|
| 16 | Composition Root | `Container` 单例、深拷贝 chatbot 配置、🆕v4.3 多配置文件发现模式（结构化元数据+fallback 扫描�?|
| 17 | 智能客服专项 | Orchestrator 无状态、KB 白名单、🆕v4.0 字段覆盖策略（按语义分类�?|
| 18 | Web 层规�?| `create_app` 工厂、LIFO 中间�?|
| 19 | API 设计 | HTTP 语义、分页、DTO 响应、🆕v4.0 幂等性设�?+ 搜索接口标准化、🆕v4.25 API 三态语义（B-REVIEW-110，PATCH/PUT �?model_dump(exclude_unset=True) 区分未传/传null/传值） |
| 20 | 测试建议 | null/空集�?边界�?并发/事务、🆕v4.3 Windows 测试环境 Mock + 第三方插件依赖预检 |
| 21 | 架构与分�?| 无循环依赖、领域纯净�?|
| 22 | 闲鱼项目规范 | Mixin 仓储、Typer CLI、Docker 三阶�?|
| 23 | Git 操作规范 | `index.lock` 检测、产�?untrack、cherry-pick 保留策略 |
| 24 | 跨字段一致性与硬编码属性禁�?| 字段一致性校验、Cookie/HTTP属性动态设置、跨线程异步禁用、try/finally初始化、跨组件状态同步、错误提示端点可操作�?|
| 25 | 错误提示语义 + 配置链路 + 快速模式降�?+ 硬编码阈值禁�?+ 参数透传完整�?| 🆕v4.4 错误码映射语义匹配、配置全链路追踪、fast 降级重试、阈值配置化、参数传递无遗漏 |
| 26 | 异步超时 + 数据流转 + 过滤场景 + 复用模式 | 🆕v4.6 异步操作整体超时保护（asyncio.wait_for）、字段为�?5 点追踪、过滤逻辑场景区分（include_failed 参数化）、复用既有模式原�?|
| 27 | 状态管理与日志治理 | 🆕v4.8 状态标志前置检查（B-REVIEW-STATE-FLAG-PRECHECK，检测异常状态后操作入口必须�?`getattr(self, "flag", False)` 前置检�?+ 重置机制）；日志级别动态降级（B-REVIEW-LOG-DOWNGRADE-STABILITY，判断字符串提取为模块级常量并注释文案来源）；修改后验证流程（B-REVIEW-EDIT-VERIFY，Edit 后用 Grep 验证标志性标识符）；参数分别�?`state_flag_precheck`/`log_downgrade` 节点管理 |
| 28 | LLM 端点能力派发与共享工具函�?| 🆕v4.23 能力驱动派发（B-REVIEW-LLM-CAPABILITY-DISPATCH，LLM/多模�?function_call 调用必须在构�?payload 前预检目标模型能力，失败时降级为等价文本表达）；共享工具函数（B-REVIEW-SHARED-UTIL-CENTRALIZATION，跨 �? 模块复用的判断逻辑/关键字白名单/常量必须抽取�?被依赖方"模块顶层的纯函数或模块级常量，禁止散落）；静默降级预检（B-REVIEW-SILENT-DOWNGRADE-PRECHECK�?可选增�?能力调用前必须预检，失败时降级为等价文本表达而非抛错，降�?prompt 模板集中管理）；参数分别�?`llm_capability_keywords`/`shared_util_rules`/`llm_downgrade` 节点管理 |
| 29 | 端到端失败原因链与数据完整性闭�?| 🆕v4.27 失败原因传递链（B-REVIEW-FAILURE-REASON-PROPAGATION，底�?`last_*_failure_reason` �?中层 status_code 映射 �?高层日志降级，禁止字符串子串判断，错误响应必须含 `error_code` 字段）；数据完整性预检（B-REVIEW-DATA-COMPLETENESS-PRECHECK，调用外部依赖前预检 + 调用后二次检查，双阈�?AND 判断，错误信息含具体缺失清单）；合并写入 vs 覆盖写入决策（B-REVIEW-MERGE-VS-OVERWRITE-WRITE，部分集→合并写 `merge_*`，完整集→覆盖写 `save_*`/`export_*`，覆盖写前必须预检新集完整）；文案常量集中管理（B-REVIEW-ERROR-MESSAGE-CONSTANT，错误文�?日志降级 marker 提取为模块级常量，跨模块引用必须 import，禁止字符串子串�?marker）；修改-验证-部署闭环（B-REVIEW-EDIT-VERIFY-DEPLOY-LOOP，Edit �?Grep 验证、Python 修改后重启服务、重启后验证端口+数据状态、git stash 前先 commit 保底）；测试 mock 同步（B-REVIEW-TEST-MOCK-SYNC，修改前置条件时同步更新 mock 数据，mock 数据覆盖完整字段集，集中管理�?conftest.py）；参数分别�?`failure_reason_propagation`/`data_completeness_precheck`/`write_strategy_decision`/`error_message_centralization`/`edit_verify_deploy_loop`/`test_mock_synchronization` 节点管理 |
| 30 | 业务关键字常量集中管理与跨端契约对齐 | 🆕v4.31 业务关键字常量集中管理（B-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION，外部平台文本特征集中到单一模块�?`*_TEXT_KEYWORDS` 常量，统一访问函数 `check_text_sold` 调用，禁止散落字面量）；事件类型过滤精确匹配（B-REVIEW-EVENT-TYPE-EXACT-MATCH，业务查询事件类型必须用 `==` 精确匹配，禁�?`startswith`/`endswith` 前缀过滤，通知事件与业务事件必须使用不同命名空间）；前后端字段名大小写敏感检查（B-REVIEW-FIELD-NAME-CASE-SENSITIVE，Python 类私有属�?`_session` vs `_Session` 严格大小写一致，API 响应字段名前后端严格一致含大小写下划线前后缀）；服务重启验证清单（B-REVIEW-SERVICE-RESTART-VERIFICATION，Python 后端代码修改后必须重启服务，重启后按清单验证端口监听/健康检�?数据状�?启动日志）；Windows 终端编码�?Shell 语法兼容（B-REVIEW-WINDOWS-TERMINAL-ENCODING，PowerShell 脚本显式设置 UTF-8 编码，命令拼接用 `;` 而非 `&&`，`stash@{0}` 加引号，Python 脚本设置 stdout 编码）；参数分别�?`business_keyword_centralization`/`event_type_exact_match`/`field_name_case_sensitive`/`post_restart`/`cross_platform` 节点管理 |
| 31 | 状态恢复与日志规范 | 🆕v4.30 状态恢复前置校验（B-REVIEW-157 RESUME-PRECHECK，具�?pause/resume 语义的组�?resume 前必�?precheck 校验 root_cause 消除，校验失败返回结构化拒绝 `{resume_blocked, reason_code, user_hint, retry_after}`，异�?pause 后设冷却期）；多阶段降级链日志合并（B-REVIEW-158 LOG-MERGE，同一逻辑链多阶段日志合并�?1 条结构化 WARNING，中间步�?DEBUG 化，结果�?`extra={stages, final_reason, keyword, attempts}`，禁止降级链每步独立 WARNING 淹没真实告警）；参数分别�?`resume_policy` / `log_merge` 节点管理 |
| 32 | 注册式资�?endpoint 契约 | 🆕v4.31 注册式资�?endpoint 契约（B-REVIEW-159 REGISTRATION-ENDPOINT-CHECK，meta-rule #33 后端落地——前端已�?`menu_registry`/`router`/`page`/`api_wrapper` 注册的资源，后端必须�?`src/xianyu_hunter/web/routes/api_<domain>.py` 提供对应 `@router.<method>` endpoint；缺一即视�?CRITICAL�? 层契约：L1 menu_registry / L2 router / L3 page / L4 api_wrapper / L5 backend_endpoint；自动化校验 `python scripts/check_registration.py` 退出码 0 才算通过）；参数�?`backend_registration_endpoint` 节点管理（含 precheck_layers 五层、required_field_mapping 跨层字段映射、fail_on_missing_layer CRITICAL、known_complete_resources 参考基线） |
| 33 | 修复前全链路根因扫描协议 | 🆕v4.31 修复前根因扫描协议（B-REVIEW-160 ROOT-CAUSE-CHAIN-CHECK，meta-rule #34 后端落地——修复非平凡 bug 前必须先�?�? 个根因覆盖用户层/接口�?数据�?配置�?历史层；PR 描述必含"�? 根因列表"�?+ 验证工具 + 最小修改清�?+ 全链路反�?+ 防回归测试；git diff 涉及 �? 个无关文件视为违反最小修改原则；新增逻辑�?unit test 视为 WARNING；链式检�?5 维度 menu_registry/router/page/api_wrapper/backend_endpoint �?B-REVIEW-159 5 层契约呼应）；参数在 `root_cause_chain_check` 节点管理 |
| 34 | 前后端字段契约单一可信�?| 🆕v4.31 前后端字段契约单一可信源（B-REVIEW-161 CONTRACT-OWNER-MARKER，meta-rule #35 后端落地——后�?Pydantic/DB Row 字段 = 权威源；后端 `BaseModel` 字段必须显式标注 `@field_validator` / `Field(..., description=...)` 标明"权威�?角色；后端字段变更必须同步通知前端 + �?`contract_owner_marker` 节点更新 `affected_frontend_types_files` 列表；snake_case 严格透传禁止�?camelCase；命名漂移检测：后端 `xxx_yyy` + 前端 `xxxYyy` = CRITICAL）；参数�?`contract_owner_marker` 节点管理（含 authority_source 唯一可信源、required_marker_fields 必填标注、affected_frontend_types_files 受影响前�?types、naming_drift_patterns 命名漂移模式库） |
| 35 | 编码规范防御性复�?| 🆕v4.33 规范沉淀门槛（B-REVIEW-162 SEDIMENTATION-THRESHOLD，meta-rule #36 落地——新�?meta-rule/step/B-REVIEW 必须满足 �? 个相�?bug 门槛，单一 bug 立规范需�?experimental 标签 + 1 季度观察期，安全/数据丢失/付费受损豁免）；规范退化机制（B-REVIEW-163 DEGRADATION-CLEANUP，meta-rule #37 落地——利用率 < 3 �?季度则标记待合并/待废弃，1 季度观察期后废弃并移�?version-history.md Deprecated 章节，安全类规范永不退化）；参数在 `meta_rules_governance` 节点管理（含 sedimentation_threshold 沉淀门槛、degradation_threshold 退化阈值、observation_period_quarters 观察期、sedimentation_exemption_categories 豁免类别、degradation_exemption_categories 安全类豁免）；🆕v4.34 全局聚合任务级过滤（B-REVIEW-164 GLOBAL-AGGREGATE-TASK-FILTER，meta-rule #38 落地——全局视图（无 task_id）列表查询必须按各任务个体配置范围过滤，禁止只用全局默认范围）；列表交叉数据批量注入（B-REVIEW-165 LIST-CROSS-DOMAIN-INJECT，meta-rule #39 落地——列表交叉其他数据源必须批量查询 + TTL 缓存，禁�?N+1 单条查询）；多字段联动开关范式（B-REVIEW-166 MULTI-FIELD-LINKED-SWITCH，meta-rule #40 落地——联动字段必须声明「主开关→过滤器」优先级矩阵，主开关失效时子过滤器自动禁用）；状态恢复前置校验结构化响应（B-REVIEW-167 RESUME-PRECHECK-STRUCTURED，meta-rule #41 落地——precheck 必须返回 5 字段结构�?dict 不抛异常，API 层直接透传）；配置化阈值兜底范式（B-REVIEW-168 CONFIG-DRIVEN-THRESHOLD-FALLBACK，meta-rule #42 落地——从 config 读取的阈值必须有 try/except 兜底默认值，禁止配置缺失即崩溃）；参数在 `meta_rules_38_42` 节点管理（含 global_aggregate_filter/cross_domain_inject/linked_switch_priority/precheck_structured_fields/config_fallback_defaults 5 个子节点�?|

### 36. 工程闭环元规范（meta-rules #52-#55 落地）🆕v4.34

> 基于 2026-07-07 修复的「价格过滤失�?/ SEMI_AUTO 模式退�?/ 外部 DOM 解析失败 / 测试 mock 错配�? 类问题复盘，使用 Sequential Thinking 4 维度复盘法，新增 4 �?B-REVIEW 检查点（B-REVIEW-177~180），自动化扫描从 168 �?172 项。所有新检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明。详细编码规范整合到 `xianyu-hunter-dev` v4.37.0 �?meta-rules #52-#55 �?step 189-192。前端对应规范为 `xianyu-frontend-code-review` v4.40.0 �?F-REVIEW-131~133�?56 过滤透明�?UI 仅前端适用）�?

- 🆕v4.34【强制�?*B-REVIEW-177：PARAM-CHAIN-EXEC 参数链闭环验�?*
  - 维度�?9 API 设计与契�?
  - 严重等级：critical（P0，过滤参数失效导致数据泄露）
  - 规范引用：meta-rule #52 参数链闭环验�?
  - **检查点**：过滤类参数（filter / constraint 语义）从 API 接收后必须存在对应的消费点（函数调用 / SQL WHERE / 条件分支），禁止"参数已接收但未被消费"
  - **检查项**�?
    1. API endpoint 函数签名声明参数后，函数体内必须存在该参数的消费逻辑
    2. 参数必须实际参与过滤条件构建（WHERE 子句 / 条件分支 / 函数调用参数�?
    3. 必须存在单元测试验证"传参 vs 不传�?结果集差�?
    4. 元数据参数白名单（page / page_size / limit / offset / sort / order / fields / select）在 config 管理
  - **判断信号**�?
    - `grep "<param_name>" <file>` 仅命中函数签名和 return 语句但未命中函数调用 �?视为可疑
    - API 接收 `market_ratio` 参数但未调用 `PriceStrategy.check(market_ratio=...)` �?违规
    - 单元测试�?`with_param` / `without_param` 对比用例 �?视为闭环验证缺失
  - **配置参数**：`param_chain_exec.enabled`（默�?true）、`param_chain_exec.metadata_whitelist`（默�?`["page", "page_size", "limit", "offset", "sort", "order", "order_by", "fields", "select"]`）、`param_chain_exec.filter_param_prefixes`（默�?`["filter_", "range_", "min_", "max_", "ratio_"]`）在 `config.yaml` �?`param_chain_exec` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #52 / step 189
  - **适用**：所有有过滤参数的列表查�?API（list_evaluations / list_items / search_* / list_orders）、PATCH/PUT 接口的可空字�?
  - **不适用**：GET 单个资源详情（无过滤）、DELETE 接口（参数仅定位资源）、仅作元数据返回的字段（total_count）、创建类 POST 接口
  - **历史教训**：`evaluations_list.py` 接收 `market_ratio=0.85` 参数但未调用 `PriceStrategy.check`，导致调整到 0.85 后仍能查出价格上�?800 的商品。修复：新增 `_resolve_market_ratio` / `_compute_eval_market_median` / `_filter_market_ratio` 三个辅助函数形成闭环�?

- 🆕v4.34【强制�?*B-REVIEW-178：MODE-VERTICAL-CHAIN 业务模式纵向链路一致�?*
  - 维度�?7 状态管理与日志治理
  - 严重等级：critical（P0，模式退化导致功能失效）
  - 规范引用：meta-rule #53 业务模式纵向链路一致�?
  - **检查点**：业务模式枚举（�?AUTO / SEMI_AUTO / MANUAL）必须在 6 个层纵向一致传递：决策�?�?事件�?�?通知�?�?路由�?�?接口�?�?状态机层，任一层缺失即模式退�?
  - **检查项**�?
    1. 决策层：`_should_buy()` 等决策函数必须根�?mode 返回不同决策
    2. 事件层：业务事件 payload 必含 mode 字段（如 `EVAL_PASSED` 事件�?`task_mode`�?
    3. 通知层：不同 mode 渲染不同模板（SEMI_AUTO 必含确认链接�?
    4. 路由层：前端为每�?mode 的后续动作提供对应路由（�?`/confirm-buy`�?
    5. 接口层：后端为每�?mode 的后续动作提�?endpoint
    6. 状态机层：必要时引入中间状态（�?`pending_confirm`）防越权
  - **判断信号**�?
    - `grep "task_mode\|mode.*AUTO\|mode.*MANUAL"` 在事�?payload / 通知模板 / 路由 / endpoint 中未命中 �?链路断裂
    - 决策函数返回值与 mode 无关 �?决策层未实现
    - 通知模板对所�?mode 渲染相同内容 �?通知层未实现
  - **配置参数**：`mode_vertical_chain.enabled`、`mode_vertical_chain.required_layers`（默�?`["decision", "event", "notification", "router", "endpoint", "state_machine"]`）、`mode_vertical_chain.mode_field_names`（默�?`["task_mode", "execution_mode", "notification_mode"]`）在 `config.yaml` �?`mode_vertical_chain` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #53 / step 190
  - **适用**：所有引�?mode 枚举且影响后续行为的业务（任务执行模式、采集模式、通知模式、订单确认模式）
  - **不适用**：纯展示�?mode 字段（仅日志记录不影响流转）、内部状态字段（不跨层传递）、单一布尔开关（无枚举语义，�?#40 MULTI-FIELD-LINKED-SWITCH�?
  - **历史教训**：SEMI_AUTO 模式退化为 CONFIRM/NOTIFY，因为：`_should_buy()` 返回 False / 通知模板缺确认链�?/ 事件 payload �?`task_mode` / �?`pending_confirm` 中间状�?/ 缺确认接口。修复：5 层全补齐 + 引入 `pending_confirm` 状态�?

- 🆕v4.34【强制�?*B-REVIEW-179：PARSER-FALLBACK-CHAIN 外部页面解析容错**
  - 维度�?3 浏览器自动化
  - 严重等级：warning（P1，外�?DOM 变化导致解析失败�?
  - 规范引用：meta-rule #54 外部页面解析容错
  - **检查点**：解析不受控的第三方页面 DOM 必须采用多级 fallback selector 策略，任一 selector 命中即返回，全部失败才触�?debug dump
  - **检查项**�?
    1. 三级 fallback：按"结构�?selector �?属�?selector �?文本扫描"顺序尝试
    2. debug dump 触发条件基于业务语义（如 `on_sale == 0`）而非实现细节（如 `sold == 0`�?
    3. selector 列表配置化，禁止硬编�?
    4. 降级链日志合并（�?B-REVIEW-158 LOG-MERGE 一致），中间步�?DEBUG �?
  - **判断信号**�?
    - `grep "querySelector\|querySelectorAll\|select\|css"` 在外部页面解析上下文，无 `try/except` �?`or []` fallback �?违规
    - `grep "tabItem\|tab.*role.*tab\|tab.*class"` selector 字符串硬编码 �?违规
    - debug dump 条件�?`sold == 0`（实现细节）而非 `on_sale == 0`（业务语义）�?违规
  - **配置参数**：`parser_fallback.enabled`、`parser_fallback.fallback_levels`（默�?3）、`parser_fallback.selectors`（默�?`["[class*='tabItem']", "[class*='tab'][role='tab']", "text_prefix_scan"]`）、`parser_fallback.debug_dump_trigger`（默�?`on_sale == 0`）在 `config.yaml` �?`parser_fallback` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #54 / step 191
  - **适用**：所有解析闲�?/ 淘宝 / 天猫 / 京东等第三方页面的代码（`_detail.py` / `_parse_*` 函数 / Playwright page.evaluate 返回值解析）
  - **不适用**：解析自己生成的内容（本�?HTML 模板）、解�?API 返回�?JSON（结构稳定）、解析固�?schema �?XML/YAML
  - **历史教训**：`_parse_sale_counts_from_tabs` 仅依�?`tabItem` class 名，闲鱼页面 DOM 结构变化导致 `on_sale=0` �?`sold=0`。修复：实现三级 fallback（`[class*='tabItem']` �?`[class*='tab'][role='tab']` �?文本前缀扫描 div/span/a），收紧 debug dump 触发条件�?`on_sale==0 or sold==0` 改为 `on_sale==0`�?

- 🆕v4.34【强制�?*B-REVIEW-180：MOCK-SYNC-BOUNDARY mock 同步与边界精确�?*
  - 维度�?0 测试建议
  - 严重等级：critical（P0，mock 类型错配导致测试失败或假阳性）
  - 规范引用：meta-rule #55 mock 同步与边界精确�?
  - **�?B-REVIEW-TEST-MOCK-SYNC（v4.27）的边界**：B-REVIEW-TEST-MOCK-SYNC 关注"修改前置条件时同步更新测�?mock"，本规范关注"mock 的类�?边界/字段/副作用精确�?
  - **检查点**：修改被测代码后必须同步 mock：mock 类型与被 mock 对象的同�?异步特性必须一致，patch 必须 patch 实际调用点而非定义�?
  - **检查项**�?
    1. 类型匹配：同步函数用 `MagicMock`，异步函数用 `AsyncMock`，禁止混�?
    2. patch 边界：patch 实际调用点（�?`worker.get_secret`）而非定义点（�?`secrets.get_secret`�?
    3. 字段完整性：mock 数据覆盖被测代码访问的所有字段，禁止部分 mock
    4. 副作用验证：测试必须断言"副作用未发生"（如未发起真实网络请�?/ 未写文件 / 未发邮件�?
  - **判断信号**�?
    - `grep "AsyncMock" <test_file>` 但被 mock 函数是同步函数（�?`async def`）→ 违规
    - `grep "MagicMock" <test_file>` 但被 mock 函数�?`async def` �?违规
    - `patch("module.function")` 但实际调用是 `from module import function; function()` �?patch 边界错误
  - **配置参数**：`mock_sync.enabled`、`mock_sync.type_mapping`（默�?`{"sync": "MagicMock", "async": "AsyncMock"}`）、`mock_sync.required_assertions`（默�?`["no_real_network_request", "no_file_write", "no_email_send"]`）在 `config.yaml` �?`mock_sync` 节点管理
  - **对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #55 / step 192
  - **适用**：所�?unit test / 集成测试中的 mock 替身
  - **不适用**：E2E 测试（应使用真实环境）、快照测试（snapshot test�?
  - **历史教训**：`test_dingtalk_notify_integration.py` �?`AsyncMock` �?`worker.py` �?`filter_new` 已改为同步实现，导致 `await` 在同步对象上失败。`test_notifier_new_channels.py` patch `get_secret` 位置错误导致 webhook_url/secret 实际不为空，测试发起真实钉钉请求。修复：AsyncMock �?MagicMock / patch get_secret 返回 None / test_manual_takeover_lock 构�?mock request �?user_id�?

---

## 37. �ⲿ���񼯳� ??v4.41

- �ȼ���critical��P0���ⲿ���񼯳�ʧ�ܵ��¹��ܲ����ã�
- ���ã�meta-rules #67-#71 / step 205-#210
- **B-REVIEW-190��CLI-PARAM-VERIFY CLI ���������֤**
  - ʹ���κ� CLI ���ߵ��²���ǰ��������ͨ�� --help ȷ�ϲ�������
  - ��ֹ����������ƣ��� cloudflared tunnel create ʹ�� --origincert ���� --cert
  - �ж��źţ�grep "\-\-cert" src/ ���е� CLI help ���� --cert ����
  - ��Ӧ����淶��step 205

- **B-REVIEW-191��CLI-OUTPUT-PARSE ����������ʽ����**
  - CLI ����������븲������������֪�����ʽ����
  - �ؼ��ֶεĽ��������������������ַ���
  - �ж��źţ�����ֻƥ��һ�������ʽ���� fallback
  - ��Ӧ����淶��step 206

- **B-REVIEW-192��SERVICE-PRECHECK �ⲿ����ǰ���������**
  - Provider ʵ�ֱ������ _check_prerequisites() ����
  - ����ȱʧʱ�׳������ָ�����쳣
  - �ж��źţ������ⲿ����ǰ�ް�װ/��¼/����ɴ��Լ��
  - ��Ӧ����淶��step 207

- **B-REVIEW-193��PROVIDER-PLUGIN ������ܹ��Ϲ�**
  - �����������������ͨ���������ʵ�֣�ע�ᵽ _PROVIDER_REGISTRY
  - Provider �л�ʱ������ stop ��ʵ��
  - �ж��źţ�grep "if.*provider" tunnel_service.py ���ִ���������֧
  - ��Ӧ����淶��step 208

- **B-REVIEW-194��NOTIFIEVENTBUS ֪ͨ���� EventBus ģʽ**
  - ����֪ͨ����ͨ�� NotifierHub ���ͣ���ֹ��ҵ�������ֱ�ӵ���֪ͨ����
  - ֪ͨ����ʹ���߳�+asyncio.run �Ž�ģʽ
  - �ж��źţ�ҵ���������ֱ�ӵ��õ�֪ͨ�����߼�
  - ��Ӧ����淶��step 209

- **���ò���**��external_service.cli_verify��external_service.precheck_required��external_service.provider_registry_enforced �� config.yaml �� external_service �ڵ����
- **����**�������漰�ⲿ CLI ���ߵ��á����������񼯳ɵĴ��루tunnel_providers.py��browser.py �ȣ�
- **������**�����ڲ�ҵ���߼������漰�ⲿ�����Ĵ���


## 38. Per-Preset Credential Management v4.42

- Severity: CRITICAL (P0, credential not following preset switch causes service call failures)
- Reference: meta-rules #70 / step 212
- **B-REVIEW-195: PRESET-APIKEY-SLOT-ISOLATION per-preset storage slot**
  - When credentials are tied to named presets/providers, each must have its own storage slot (keyring/key).
  - Switching presets must atomically: (a) save current credential to its slot, (b) load target preset credential from its slot, (c) update active config.
  - Signal: grep "if.*preset" reveals conditional credential logic without per-preset storage keys.
  - Corresponds to: src/xianyu_hunter/infra/secrets.py ai_preset_key_name(), src/xianyu_hunter/web/routes/api_ai.py AI_PRESET_BASE_URLS
  - Config param: credential_storage.per_preset_slots in config.yaml credential_storage node

- **B-REVIEW-196: MIGRATION-FIRST-TIME first-time migration**
  - When introducing per-item credential storage, existing global credentials must be migrated to the original preset slot during first switch.
  - Migration must happen atomically during the first switch, not at startup (to avoid breaking existing deployments).
  - Signal: new per-preset storage exists but no migration logic in save handler.
  - Corresponds to: save_ai_config() in api_ai.py migration block
  - Config param: credential_storage.migration_on_first_switch in config.yaml credential_storage node

- **B-REVIEW-197: EMPTY-OVERRIDES-LEGACY empty string overrides legacy**
  - When loading secrets from keyring, an empty string (key deleted/not configured) must override legacy fallback values (e.g., from .env).
  - _load_secrets_from_keyring must use "is not None" guard, not truthiness check, so empty string can override legacy values.
  - Signal: grep "if .*_key:" in _load_secrets_from_keyring reveals truthiness check instead of "is not None".
  - Corresponds to: config.py _load_secrets_from_keyring() None check fix
  - Config param: credential_storage.empty_overrides_legacy in config.yaml credential_storage node

- **B-REVIEW-198: MUTATION-RESPONSE-ECHO mutation response echo**
  - PUT/PATCH endpoints returning configuration must echo back the full updated state including derived/computed fields (preset_id, masked credentials).
  - Handler should call the corresponding GET handler to build the response, avoiding duplication.
  - Signal: mutation response only returns {ok: True, message: ...} without config data.
  - Corresponds to: save_ai_config() returning **get_ai_config() unpack
  - Config param: api.mutation_response_echo in config.yaml api node

- **B-REVIEW-202: PRESET-ID-LITERAL preset ID literal type**
  - Endpoint bodies accepting preset/provider identifiers must use Literal type for known values.
  - Signal: string parameter with known finite set uses str type annotation instead of Literal[...].
  - Corresponds to: AIConfigBody.preset_id Literal type definition
  - Config param: api.literal_preset_ids in config.yaml api node

- **Applicable**: All backend code handling per-preset/per-provider credentials (AI config, notification channels, proxy providers, tunnel configs)
- **Not applicable**: Forms without credential fields, one-time credential operations


## 39. Per-Preset Credential Frontend Contract v4.43

- Severity: CRITICAL (P0, frontend-backend contract mismatch for per-preset credential switching)
- Reference: meta-rules #71 / step 212 / step 213
- **B-REVIEW-200: MUTATION-ECHO-FULL mutation response includes full config state**
  - PUT /api/ai/config must return the full updated configuration including preset_id, masked api_key, and all derived fields.
  - Response should be built by calling the GET handler internally to avoid duplication.
  - Signal: grep "return.*{.*ok.*message" in save_ai_config without unpacking get_ai_config() result.
  - Config param: api.mutation_response_echo in config.yaml api node

- **B-REVIEW-201: PRESET-ID-LITERAL-TYPE preset_id uses Literal type annotation**
  - AIConfigBody.preset_id must use Literal["openai", "deepseek", ...] instead of plain str.
  - Signal: preset_id: str | None in a Pydantic model where preset values are a known finite set.
  - Config param: api.literal_preset_ids in config.yaml api node

- **B-REVIEW-202: FRONTEND-KEY-FIELD-CONTRACT frontend does not send raw api_key on preset switch**
  - The backend must accept PUT requests where api_key is absent during preset switching (relying on slot restoration).
  - When api_key is absent AND preset_id changes, backend must restore from the target preset's slot.
  - Signal: save handler ignores missing api_key during preset switch instead of treating it as an error.
  - Config param: credential_storage.frontend_contract in config.yaml credential_storage node

- **Applicable**: All backend endpoints involved in per-preset credential switching
- **Not applicable**: One-time credential operations without preset switching

## 40. Model Name Accuracy and Capability Check Backend Review v4.44

- Severity: CRITICAL (P0, backend model name mismatch causes API 400 errors)
- Reference: meta-rules #72 / step 214

- **B-REVIEW-203: MODEL-NAME-OFFICIAL-ACCURACY preset model matches vendor docs**
  - Backend default model names (config.py Settings.openai_model / openai_vision_model) must match vendor official API documentation character-for-character including case.
  - DeepSeek: deepseek-v4-flash (all lowercase), not DeepSeek-V4-Flash.
  - Signal: config.py default model name differs from official docs in case.
  - Config param: model_names.backend_defaults in config.yaml model_names node

- **B-REVIEW-204: CAPABILITY-CHECK-SHARED shared vision check function**
  - Model capability check functions (e.g., _is_vision_capable) must be shared across modules, not duplicated.
  - The shared function must use case-insensitive matching (.lower()) for keyword comparison.
  - Signal: _is_vision_capable or equivalent appears in multiple files without a shared import.
  - Config param: llm_capability_keywords.shared_function_required in config.yaml

- **B-REVIEW-205: MODEL-LITERAL-TYPE preset_id typed as Literal**
  - Request body fields accepting preset/vendor identifiers must use Literal type annotation with known values.
  - New presets must update both the Literal type definition and frontend PRESETS constant simultaneously.
  - Signal: preset_id: str used instead of preset_id: Literal["openai", "deepseek", ...].
  - Config param: api.literal_preset_ids in config.yaml


## 41. Config Persistence and Reflection Backend Review v4.44

- Severity: CRITICAL (P0, config values not persisted or incorrectly returned)
- Reference: meta-rules #73 / step 215

- **B-REVIEW-206: CONFIG-PERSIST-ENV-UPDATE non-secret fields written to .env on change**
  - PUT/PATCH config endpoints must persist non-secret fields (base_url, model, vision_model, embedding_*) to .env file.
  - Each field change must trigger an immediate .env upsert (existing key overwritten, new key appended).
  - Signal: config change only updates memory but not .env file.
  - Config param: config_persistence.env_persist_enabled (default True) in config.yaml

- **B-REVIEW-207: MASKED-KEY-RETURN api_key masked in GET but raw in PUT echo**
  - GET /api/ai/config must return api_key masked (****xxxx), PUT /api/ai/config response must echo full updated state.
  - The echo in PUT response must also mask api_key consistently with GET.
  - Signal: GET returns raw api_key, or PUT response does not include updated config state.
  - Config param: api.mutation_response_echo in config.yaml api node

- **B-REVIEW-208: KEY-RING-INDEPENDENT per-key storage isolation**
  - Each API Key (openai_api_key, embedding_api_key) must be stored independently in keyring with separate service/key pairs.
  - Switching one key must not affect the other. Clearing one key must not clear the other.
  - Signal: both keys stored under the same keyring key, or clearing one affects the other.
  - Config param: credential_storage.per_key_isolation (default True) in config.yaml

- **Applicable**: All backend config endpoints
- **Not applicable**: One-time operation endpoints

## 42. Multi-User Cookie Isolation Backend Review v4.45

- Severity: CRITICAL (P0, cookie isolation breaks real-time search after multi-user migration)
- Reference: meta-rules #72-#78 / steps 216-222

- **B-REVIEW-209: COOKIE-ISOLATION-USERID-PROPAGATION user_id propagated through cookie operations**
  - All CookieStore methods (_read_json, export_cookies, update_cookie_values, has_valid_cookies, invalidate_cache) must accept user_id parameter with default "default" for backward compatibility.
  - Real-time search entry points (_ensure_live_search_cookies, _check_live_cookies_safely, _load_pw_cookies_from_json) must accept user_id and receive it from request context.
  - Signal: grep "_ensure_live_search_cookies(container)$" reveals missing user_id; grep "store._read_json()" without user_id argument.
  - Config param: cookie_management.multi_user_isolation.user_id_propagation_required in config.yaml

- **B-REVIEW-210: LIVE-SEARCH-COOKIE-HEALTHCHECK user_id passed through SSE stream**
  - live_links endpoint must pass request.state.user_id through _live_event_stream to _check_live_cookies_safely to _ensure_live_search_cookies to _load_pw_cookies_from_json.
  - refresh_links endpoint must pass request.state.user_id to _ensure_live_search_cookies.
  - Signal: grep "_check_live_cookies_safely(container, task_id, inflight_event)$" reveals missing user_id.
  - Config param: cookie_management.multi_user_isolation.live_search_user_id_required in config.yaml

- **B-REVIEW-211: CACHE_INVALIDATION_BEFORE_READ invalidate cache before cross-process JSON reads**
  - All cookie JSON reads must call store.invalidate_cache(user_id) before store._read_json(user_id) to avoid stale cache from subprocess writes.
  - sync_cookie_layers_from_json must call store.invalidate_cache() (no user_id) before reading to clear all user caches.
  - Signal: grep "store._read_json" without preceding invalidate_cache call.
  - Config param: cookie_management.multi_user_isolation.cache_invalidation_required in config.yaml

- **B-REVIEW-212: COOKIE-INJECTION-VERIFY verify browser holds injected cookies**
  - After container.browser.add_cookies() returns True, must verify browser actually holds the injected identity cookies (unb, cookie2, sgcookie).
  - Verification must compare browser cookie values against injected values.
  - Signal: grep "add_cookies" followed by immediate return without verification.
  - Config param: cookie_management.multi_user_isolation.injection_verification_required in config.yaml

- **B-REVIEW-213: M5TK-REFRESH-ISOLATION _m_h5_tk refresh writes to correct user file**
  - _sync_response_cookies_to_context must accept user_id and pass it to update_cookie_values(updates, user_id=user_id).
  - _ensure_fresh_m5tk force refresh failure must log WARNING and skip retry, not hang.
  - Signal: grep "update_cookie_values(updates)$" reveals missing user_id.
  - Config param: cookie_management.multi_user_isolation.m5tk_user_isolation in config.yaml

- **B-REVIEW-214: COOKIE-LAYER-SYNC-INVALIDATE cross-process cookie writes must invalidate cache**
  - Browser login subprocess must call invalidate_cache(user_id) after writing cookies_{user_id}.json.
  - sync_cookie_layers_from_json must be called after cookie injection to sync layer states.
  - Signal: grep "sync_cookie_layers_from_json" without preceding invalidate_cache.
  - Config param: cookie_management.multi_user_isolation.layer_sync_after_inject in config.yaml

- **B-REVIEW-215: TEST-COOKIE-FILTER-BEFORE-INJECT filter test cookies before browser injection**
  - _load_pw_cookies_from_json must call is_test_cookie(name, value) for each cookie and skip test data before building Playwright cookie list.
  - Filtered test cookies must log WARNING with cookie name and first 8 chars of value.
  - Signal: grep "is_test_cookie" not found in _load_pw_cookies_from_json.
  - Config param: cookie_management.test_cookie_filter.enabled (default True) in config.yaml

- **B-REVIEW-216: USER-ID-VALIDATION-BEFORE-PATH user_id validated before file path construction**
  - All user_id values used in file paths must pass regex validation: ^[A-Za-z0-9_-]{1,64}$
  - Path construction must use Path(dir, filename) multi-parameter form, not string concatenation.
  - Signal: grep 'f"cookies_{' or Path(f"cookies_') reveals unsafe path construction.
  - Config param: cookie_management.multi_user_isolation.user_id_validation in config.yaml

- **B-REVIEW-217: BACKWARD-COMPAT-DEFAULT-user_id default value preserves single-user mode**
  - All cookie operations accepting user_id must default to "default" when not specified.
  - This ensures existing code without user_id awareness continues to work.
  - Signal: grep "user_id: str =" without default value in cookie operation signatures.
  - Config param: cookie_management.multi_user_isolation.backward_compat_default in config.yaml

- **Applicable**: All backend code handling cookie read/write/injection after multi-user migration
- **Not applicable**: Single-user mode deployments, one-time cookie import operations


## 37. Backend Logic Frontend Documentation Sync Review v4.49

- Severity: HIGH (P1, backend logic changes must be accompanied by frontend documentation)
- Reference: meta-rules #74-#75 / step 225

- **B-REVIEW-218: BACKEND-LOGIC-CHANGE-TRIGGERS-FRONTDOC backend logic changes must trigger frontend documentation update**
  - When evaluator logic changes (new scoring dimension, new threshold, new price range rule), the corresponding EvalRules page card must be updated within the same PR.
  - Signal: evaluator.py or price_strategy.py changes without corresponding EvalRules.tsx update.
  - Config param: eval.rules_visibility.sync_backend_changes (implicit, always True)

- **B-REVIEW-219: PRICE-RANGE-SCORING-CONFIGURABLE price range scoring thresholds must be configurable**
  - Price range scoring gradient values (edge penalty, center bonus, out-of-range penalty) must be read from task config, not hardcoded in evaluator.
  - Signal: evaluator.evaluate() contains magic numbers for price range penalties.
  - Config param: eval.price_range_scoring.gradient_steps in config.yaml

- **B-REVIEW-220: FALLBACK-COMPATIBLE-INTERFACE non-breaking changes to public methods**
  - When adding optional parameters (e.g., price_range to evaluator.evaluate()), the method signature must remain backward compatible with existing callers.
  - Signal: adding required parameter breaks existing call sites.
  - Config param: api.backward_compatibility.required (default True)

- **B-REVIEW-221: CONFLICT-RESOLUTION-HELPER-PRIORITY merge conflict resolution preserves main refactoring**
  - When resolving merge conflicts, main branch helper extraction patterns take priority over feature branch inline code.
  - Signal: feature branch inline code merged back into main, undoing helper extraction.
  - Config param: git.merge_conflict_resolution.helper_priority (default True)

- **Applicable**: All backend logic changes that affect evaluation, scoring, or filtering
- **Not applicable**: Pure infrastructure changes, config-only changes without logic modification


## 43. API Response Field UI Alignment Review v4.50.0

- Severity: HIGH (P1, interface contract alignment with frontend UI operation set)
- Reference: meta-rule #83 / step 236+237+238 / F-REVIEW-197 + F-REVIEW-198 (frontend side)

### B-REVIEW-237: API-RESPONSE-FIELD-UI-ALIGNMENT Interface response fields aligned with UI operation set

- **Specification**: List/detail interface return fields must be aligned with the frontend UI operation set. Over-fetching (returning fields not needed by the UI) and under-fetching (missing status fields needed by the UI for disabled/tiered judgment) are both prohibited.
- **Judgment signals**:
  - Response field count > `api_response_field_ui_alignment.max_fields_per_list_response` (default 20) �� suspected over-fetching
  - Response missing `required_status_fields_for_action_buttons` field for a button �� under-fetching
  - Frontend `grep "disabled=" <page>.tsx` but backend Response lacks corresponding field �� contract misalignment
  - Backend Response contains sensitive fields (password/token/cookie) that UI does not display �� must remove
- **Config node**: `config.yaml#api_response_field_ui_alignment`
  - `enabled`: enable (default true)
  - `max_fields_per_list_response`: max fields per list response (default 20)
  - `max_fields_per_detail_response`: max fields per detail response (default 40)
  - `required_status_fields_for_action_buttons`: required status fields for each action button (edit/toggle/stop/copy/delete/save_as_template)
  - `scan_paths`: scan paths (default `src/xianyu_hunter/web/routes/` and `src/xianyu_hunter/web/services/`)
- **Applicable**: List interfaces (/api/tasks, /api/orders, /api/items); detail interfaces; batch interfaces returning multiple resources; AntD Table columns render data source interfaces
- **Not applicable**: System-level interfaces (/api/healthz, /api/about); backend-only internal service methods; webhook/callback interfaces not involved in UI display; simple responses with �� 3 fields
- **Historical lesson**: TaskList.tsx operation column overflow Bug. Root cause: backend Response lacked template_savable field, frontend could not accurately determine whether "Save as Template" should be disabled, had to always display the button, contributing to operation column button count exceeding threshold. Fix: backend Response adds template_savable field; frontend uses this field for disabled judgment; "Save as Template" still displayed but moved to Dropdown due to low frequency
- **Corresponding specs**: `xianyu-hunter-dev` step 236 (action button tiered retention) + step 237 (multi-view mode consistency) + step 238 (UI horizontal overflow diagnosis and scroll fallback)
- **Frontend counterpart**: F-REVIEW-197 (action button tiered retention and scroll fallback) + F-REVIEW-198 (multi-view mode consistency)

---

## ��¼ A��2026-07-22 �������㣨���ڽ�һ�ֶԻ����̣�

> ��Դ��77 ������δ���������� 0 �֡��ٷ��ɼ�ʧ�ܡ�scoring ά�� bug 4 ����ʵ����

### A.1 ʹ�� domain enum ������ʽ import

**�������**��
```bash
grep -rn "RiskLevel\|OrderStatus\|EventType" src/xianyu_hunter/ --include="*.py" | grep -v "from xianyu_hunter"
```

**����׼**��
- �κ����� domain enum ֵ��`RiskLevel.EXTREME`��`OrderStatus.PENDING`�����ļ���import �б�������� enum
- ȱʧ import �ᱻ `try/except Exception` ��Ĭ�̵��������Ϊ�쳣�������Դ���
- ��鹤�ߣ�ɨ������ enum ���ã����� import ·��

**��ʵʧ��**��worker.py:339 ���� `RiskLevel.EXTREME` ��ֻ import `EvalResult`���������� eval.scored �¼�д��ʧ��

**�Զ������**��������� CI����
```python
import ast
forbidden = ['RiskLevel.', 'OrderStatus.', 'EventType.']
for f in glob.glob('src/xianyu_hunter/**/*.py', recursive=True):
    tree = ast.parse(open(f, encoding='utf-8').read())
    imports = {n.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.value.id in {'RiskLevel', 'OrderStatus', 'EventType'}:
            assert node.value.id in imports, f'{f}: ʹ�� {node.value.id} ��δ import'
```

### A.2 ��ֵ�������������Դ��ʵ��Χ�Ƶ�

**�������**��
```bash
grep -rn "credit_score_min\|register_days_min\|post_count_30d" src/xianyu_hunter/ config/
```

**����׼**��
- �κ�"ҵ����ֵ"�������븽��ע��˵������Դ��Χ
- ���÷���ֵ���� �� ����Դ���ޣ����������� 0-100������ֵ �� 100��
- ʱ����ֵ���� register_days�����뿼��ҵ��ʱ�䴰�ڣ�90 �� / 180 �� / 365 �죩
- ���ñ������ͬ����� `eval.yaml` / `eval.example.yaml` / `config.yaml` ����

**��ʵʧ��**��credit_score_min=600�����������÷ַ�Χ 0-100��94 �����ȫ��һƱ��� �� ȫ�� 0 ��

**����嵥**��
- [ ] ҵ���ĵ�/����Դ��ѯ����ʵ��Χ����
- [ ] ����ֵ�Ƿ��ڷ�Χ�ڣ�
- [ ] һƱ�������ֵ�Ƿ�����ϸ�

### A.3 �첽������Դ������ timeout/�Ŷӻ���

**�������**��
```bash
grep -rn "browser_lock\|asyncio.Lock\|with container\." src/xianyu_hunter/ --include="*.py"
```

**����׼**��
- ���� `asyncio.Lock` ������ `asyncio.wait_for(lock.acquire(), timeout=N)`
- ����������������ɼ���ʹ�� `external page` ���� shared page
- �û��� API���ٷ��ɼ�����������������ǰӦ����Ƿ��� scheduler ��������ռ��
- ʧ�ܴ�����Ϣ������ȷָ��"����������쳣/��Դռ��"

**��ʵʧ��**��scheduler ��������ռ�� browser_lock 30s ��ʱ���ٷ��ɼ� API �ȴ�����ʱ����"���Ժ�����"

**����**��
```python
try:
    async with asyncio.timeout(60):  # ���� 60s
        async with container.browser_lock:
            result = await _collect_official(...)
except TimeoutError:
    raise HTTPException(503, "ϵͳ��æ������ͣ�������������")
```

### A.4 �����¼�д������� upsert + Ψһ����

**�������**��
```bash
grep -rn "eval\.scored\|upsert_eval\|INSERT INTO events" src/xianyu_hunter/ --include="*.py"
```

**����׼**��
- `eval.scored` �¼������� `upsert_eval_event`��DELETE+INSERT ���ԣ�
- events ������� partial unique index `idx_eval_scored_unique ON (task_id, item_id) WHERE type = 'eval.scored'`
- �ظ�������ͬ task_id + item_id������������м�¼����ֹ INSERT ��������

**��ʵʧ��**���ظ�������ʱ�������� eval.scored �¼������·����ظ�����

### A.5 �޸�����/���������ͬ�������Զ���

**�������**��
```bash
grep -rn "credit_score_min\|600\|>= 500" tests/ --include="*.py"
```

**����׼**��
- ����Ӧ���ڷ�Χ��`50 <= x <= 100`�����Ǿ���ֵ��`x == 600`��
- �����޸ĺ������ȫ�����ԣ�ȷ���޶���ʧ��
- �޸�һ�� bug �󣬱��� grep �� bug ����ִ���ȷ�����в��Զ��Ѹ���

**��ʵʧ��**��credit_score 600��60 ��test_low_credit_veto �� `credit_score=500` ����������µ� 60 ��ֵ�²�����������ʧ��

**����**��
```python
def test_low_credit_veto():
    # �ñ߽�ֵ 50 ������60 ������ֵ��
    result = ev.evaluate(make_item(), make_seller(credit_score=50))
    assert result.score == 0

def test_thresholds_sensible():
    # �÷�Χ����
    assert 50 <= t.credit_score_min <= 100, "��ֵӦ���������÷�Χ 0-100 ��"
```

### A.6 ����������뼯�ɽ��ܷ֣��ܾ�Ӧ�� 0.85 ���ͷ��ȣ�

**�������**��
```bash
grep -rn "apply_ai_eval\|ai_reject\|ai_caution" src/xianyu_hunter/modules/evaluator.py
```

**����׼**��
- AI �����������ͨ�� `apply_ai_eval()` ���ɵ� `EvalResult.score`
- �ܾ��ࣨreject�����뽫 score ��Ϊ 0
- �����ࣨcaution������Ӧ�� 0.85 �ۿ�
- ���� 8+ ���� `+5` �ӷ֣�3- ���� `*0.7` �ͷ�
- ���ܽ���Ϊ metadata �洢������Ӱ�����շ���

**��ʵʧ��**��AI ����������洢Ϊ metadata ��δӰ�� score����������������ʵ�ʳ�ɫ����ƫ��

---

## ��¼ B���������ǿ��

### B.1 ���ʽ��飨������

```
1. ��̬��飨PR/����ύʱ��
   - �� grep �������
   - ��� A.1-A.6 ȫ��Ҫ��
   - ��� TypeScript ���루mypy/pyright��

2. ��Ԫ���ԣ��ϲ�ǰ��
   - �߽�ֵ���ԣ����/���/None/���ַ���/����Χ��
   - �쳣·�����ԣ���ʱ����������������

3. ���ɲ��ԣ��ϲ�ǰ��
   - ��ʵ DB ��֤
   - �˵��� API ����
   - ������������ٷ��ɼ���������ȡ��

4. ����һ���ԣ��ϲ�ǰ��
   - yaml/eval.yaml/eval.example.yaml ����һ��
   - �ĵ������һ��

5. �ع���飨����ǰ��
   - ȫ������ͨ��
   - ��ʵ����������
```

### B.2 ��鱨��ģ�壨������¼��

```markdown
## �����鱨�� - {�������}

### ������Blocker��
- [ ] A.1 domain enum δ import �� NameError ��Ĭ�̵�
- [ ] A.2 ��ֵ������Դ��Χ �� ȫ������
- [ ] A.3 �������� timeout �� API ��ʱ������

### �ؼ���Critical��
- [ ] A.4 �ظ��¼��� upsert �� ������Ⱦ
- [ ] A.5 ���Զ���δͬ�� �� �޸������ʧ��
- [ ] A.6 AI ����δ���ɽ��ܷ� �� ����ʧ��

### ����
- [ ] mypy ͨ��
- [ ] pytest ȫ��ͨ��
- [ ] ��ʵ DB ��֤ OK
- [ ] �˵��� API ���� OK
```

---

## ��¼ C���汾��ά��

- ���θ��£�2026-07-22
- �������ܣ�xianyu-hunter-dev����¼ A.2����xianyu-auto-testing
- ������Դ��`docs/00-�����/����-����淶�뼼���Ż�-2026-07-22.md`

---

> **v4.51.0 B-REVIEW-242 STEP-PROGRESS-LOG / B-REVIEW-243 TIMEOUT-ERROR-SEMANTICS / B-REVIEW-244 OVERWRITE-SET-SELECTION��meta-rule #85 ��أ�2026-07-22 ������ʱ+image_urls ��� Bug ���̣�**�����ڱ��ζԻ������������� Bug ���̡�����1��������ʱ��`buyer.py` `_do_buy` �޲��輶��־ + `TimeoutError` ��ͨ�÷�֧����2��image_urls ����գ�`api_evaluations.py` `image_urls` �� `_ALWAYS_OVERWRITE` �����б� `None` ���ǡ�ʹ�� Sequential Thinking 4 ά�ȸ��̷������ɹ�����/��ȷ������ʧ�ܵ�/�ɳ���Ĺ̶��������ж��߼�/�����벻���ó��������� 3 �� B-REVIEW ���㡣���м���ǿ������������������ `config.yaml` ��Ӧ�ڵ�������Ӳ����ҵ�������������/�����ó���˵����ȷ��ͨ���ԣ���
>
> **B-REVIEW-242 STEP-PROGRESS-LOG �ಽ��ؼ�·�����ȱ����־���**��ά�� 9/15������3 ����Ĺؼ�·��������/�ɼ�/��¼/Ǩ�ƣ���ÿ������ǰ���������־ `����X/N <��������> <�ؼ���ʶ>`����ʱ��ʧ��ʱ�ɴ���־���ٶ�λ������һ�����ж��źţ�`grep "async def _do_\|async def _collect_\|async def _login_" src/` �ҵ��ಽ�����̺��� �� ����Ƿ��в��輶�����־�����̺� ��3 �� `await` ���õ��� `����X/N` ��־ �� ��ΪΥ�棻��־�в������������ܲ�������� `����1` �� `/4`���� ��ΪΥ�棻��־�б�ŵ���ҵ���ʶ��`item_id`/`task_id`���� ��ΪΥ�档���ò����� `config.yaml` �� `step_progress_log` �ڵ�����`enabled`/`format`/`key_fields`/`min_steps_threshold`/`workflows`�������ã��ಽ��������Զ������̡��ಽ������Ǩ�����̡��ಽ���ʼ�����̣������ã������������ǹؼ�·���������㺯�������нṹ�������־�� cookie ������·���� B-REVIEW-231������ϸ����淶Ϊ `xianyu-hunter-dev` v4.52.0 step 247��
>
> **B-REVIEW-243 TIMEOUT-ERROR-SEMANTICS ��ʱ�쳣�û��Ѻ��������**��ά�� 9/15����`asyncio.wait_for` �����Ĵ���飬`except asyncio.TimeoutError` ������ `except Exception` ֮ǰ�������񣬴�����Ϣ����ʱ����+����ԭ��+���������Ҫ�أ���ֹ�ó�ʱ�쳣��ͨ�÷�֧��ʾ"δ֪�쳣"���ж��źţ�`grep "asyncio.wait_for" src/` �ҵ���ʱ���� �� ����Ƿ��� `except asyncio.TimeoutError` ר�ŷ�֧��`except asyncio.TimeoutError` �� `except Exception` ֮�� �� ���ɴ������룬��ΪΥ�棻��ʱ������Ϣ��"��ʱ"������/ԭ��/���� �� ��ΪΥ�棻��ʱ��־��ҵ���ʶ��`task_id`/`item_id`���� ��ΪΥ�棻��ʱ����Ӳ���루�� `timeout=90`�����Ǵ����ö�ȡ �� ��ΪΥ�档���ò����� `config.yaml` �� `timeout_error_semantics` �ڵ�����`buyer_do_buy_timeout_sec`/`collector_detail_timeout_sec`/`login_flow_timeout_sec`/`error_message_template`/`operation_names`/`possible_causes`/`suggested_actions`�������ã����������û����첽��ʱ����������/�ɼ�/��¼/�������������ã��ڲ���ʱ���ԣ���ֱ�������û����� B-REVIEW-50 �� 504 ״̬�룩���� tenacity ���Ի��ư����ĳ����������㺯������ϸ����淶Ϊ `xianyu-hunter-dev` v4.52.0 step 248��
>
> **B-REVIEW-244 OVERWRITE-SET-SELECTION �ֶθ��Ǽ���ѡ�����**��ά�� 6/17����`_ALWAYS_OVERWRITE` ����ֻ��"ÿ�βɼ��ض���ȡ��+��ֵ��׼ȷ"���ֶΣ�task_id/publish_time/view_cnt/want_cnt/region/seller_id�����ɼ����ܷ��� `None`/��ֵ����ֵ�м�ֵ���ֶΣ�image_urls/thumb_url/description�������� `_coalesce` �߼����ж��źţ�`grep "_ALWAYS_OVERWRITE\|_COALESCE" src/` �ҵ����϶��� �� ���ÿ���ֶε�ѡ�����ɣ��ֶ��� `_ALWAYS_OVERWRITE` �� + �ɼ����ܷ��� `None`/�� �� ��ΪΥ�棨Ӧ�� `_coalesce`�������϶�����ע��˵���ֶ�ѡ������ �� ��ΪΥ�棻�����ֶ��嵥Ӳ������Ǵ����ö�ȡ �� ��ΪΥ�棻�ɼ��������ֶα� `None` ���ǵ������ݶ�ʧ �� �����ֶι���������ò����� `config.yaml` �� `overwrite_set_selection` �ڵ�����`always_overwrite_fields`/`coalesce_fields`/`selection_criteria`/`require_comment`�������ã������� `_ALWAYS_OVERWRITE`/`_coalesce` ˫���Ե����ݺϲ��������ɼ�-�洢��·��������£������ã���һ���ǲ��ԣ��� `_coalesce` �߼����������־���豣��ȫ����ʷ������������������ϸ����淶Ϊ `xianyu-hunter-dev` v4.52.0 step 250��

---

## v4.55.0 B-REVIEW-245~249 �������淶��2026-07-22 �ڶ��ָ��̣�

> ��Ӧ xianyu-hunter-dev meta-rules #84-#87������ Sequential Thinking ��ά�ȸ��̳����
> ���ײ���ģʽ��xianyu-auto-testing ģʽ L��״̬�������ع飩/ ģʽ M�����������Լһ���ԣ���

### B-REVIEW-245 SCHEDULER-STATE-MACHINE-RECOVERY ������״̬���ָ�·����飨ά�� 9/15��

**��ӦԪ����**��#86��SCHEDULER-STATE-MACHINE-RECOVERY��
**�� B-REVIEW-157 RESUME-PRECHECK ������**��B-REVIEW-157 ��ע"resume ǰУ���������"��B-REVIEW-245 ��ע"pause/resume �¼������ loop �ջ�"

**���Ҫ��**��
1. `should_pause` ���� True ʱ����ѭ���Ƿ� `break` �˳���Ӧ `continue` �ض���������
2. `pause_event.set()` �Ƿ��ж�Ӧ�� `pause_event.wait()` ��ѭ���ڵȴ�
3. `pause_event.clear()` �Ƿ��� resume ǰ���ã�����ѭ�����������ת��
4. �ỰʧЧ��ͣʱ�Ƿ����� `consecutive_errors`����Ӧ�ڴ����ã�
5. `_run_loop` �����Ƿ��� `pause_event` ״̬

**�жϱ�׼**��
- `should_pause` ��֧�� `return True` ������ѭ�� `break` �� CRITICAL���������ÿ�����
- `pause_event.set()` �޶�Ӧ `wait()` �� CRITICAL��״̬�����ѣ�
- �ỰʧЧ��ͣʱ���� `consecutive_errors` �� WARNING���ָ������н�����

**�������**��
```powershell
Select-String -Path "src/xianyu_hunter/**/scheduler*.py" -Pattern "return True|pause_event|should_pause|consecutive_errors"
```

**���ó���**����̨�����������APScheduler/�Զ��� loop�����Ự�������¼̬ʧЧ����ͣ���ָ���
**�����ó���**��һ���Խű�����״̬ API�����̼����ƣ��źţ�

---

### B-REVIEW-246 COOKIE-TOKEN-SEPARATION ��� Cookie ��ǩ�� token ������飨ά�� 7/15��

**��ӦԪ����**��#84��COOKIE-TOKEN-STATE-SEPARATION���� 1-2 ��

**���Ҫ��**��
1. ��� Cookie ��ǩ�� token �Ƿ����������ֹ����"Cookie ��Ч�� token Ҳ��Ч"��
2. token ˢ��ʱ������� `_last_m5tk_refresh`�������߼��Ƿ��� Cookie ��ע���֧**�ⲿ**�����������ã�
3. ��������ʱ���ɵ����� token �Ƿ���ڵ�¼�����
4. ��洢���ʣ�������ڴ� + JSON + SQLite���� token ֵ�Ƿ�ͬ��

**�жϱ�׼**��
- token �����߼����� Cookie ��ע���֧�� �� CRITICAL��������ѳ� Cookie ʱ�����ã�
- ����"Cookie ��Ч�� token Ҳ��Ч" �� CRITICAL��token ���������������
- ���ں� token ֻ�����ڴ�δ��д JSON �� WARNING��JSON ����Զ�Ǿ�ֵ��

**�������**��
```powershell
Select-String -Path "src/xianyu_hunter/**/*.py" -Pattern "_last_m5tk_refresh|_m_h5_tk|token_refresh"
```

**���ó���**������̹��������ʵ����token ����� Cookie ����������֤��ϵ���� MTOP API��
**�����ó���**������������ɵ�¼�������� token ���ƵĴ� Cookie ��֤

---

### B-REVIEW-247 CONFIG-FIELD-FIVE-LAYER �����ֶ������·������飨ά�� 11/15��

**��ӦԪ����**��#86��CONFIG-FIELD-FULL-CHAIN-COVERAGE�������ֶ�ȫ��·���Ǽ�飩

**���Ҫ��**��
1. DB schema ���������ֶ�ʱ��`get_config` API �Ƿ񷵻ظ��ֶΣ��� 2 �㣩
2. `update_config` API �Ƿ�֧�ָ��ֶθ��£��� 3 �㣩
3. `update_config` �յ���ֵʱ�Ƿ�ɾ��������ָ�Ĭ�ϣ�����д����ַ���
4. DB schema Ĭ��ֵ�Ƿ�Ϊռλ���ַ�����`'??????????!'` / `'TODO'` / `'placeholder'`��
5. `get_config` ��ȡ�ֶ�ʱ�Ƿ���ֵ֤��Ч�ԣ���ֵ���˵�������Ĭ��ֵ��

**�жϱ�׼**��
- `get_config` �����ֶ��� < DB schema �ֶ��� �� CRITICAL���� 2 ��ȱʧ��
- `update_config` ��֧�ָ��ֶ� �� CRITICAL���� 3 ��ȱʧ��
- ��ֵд����ַ�������ɾ�� �� WARNING���ָ�Ĭ���������
- DB Ĭ��ֵΪռλ�� �� CRITICAL���û��������룩

**�������**��
```powershell
# �Ա� DB schema �ֶ��� get_config �����ֶ�
Select-String -Path "src/xianyu_hunter/**/*.py" -Pattern "ALTER TABLE.*ADD COLUMN|get_config|update_config"
# ���ռλ��
Select-String -Path "src/xianyu_hunter/**/*.py" -Pattern "placeholder|TODO|FIXME|\?\?\?\?"
```

**���ó���**���û��ɱ༭�����DB �־û������ñ��Ǩ�ƽű����������ֶ�
**�����ó���**�������ڳ������������������������ֻ������

---

### B-REVIEW-248 CROSS-LAYER-WRITEBACK-PROTECTION ���д�ر�����飨ά�� 6/17��

**��ӦԪ����**��#87��EMPTY-MEANS-RESET����ֵ=�ָ�Ĭ�����壩�� 4 �������д�ر��� + ��ֵ�������֣�
**�� B-REVIEW-244 OVERWRITE-SET-SELECTION ������**��B-REVIEW-244 ��ע"�ֶ�ѡ���ĸ�����"��B-REVIEW-248 ��ע"��ֵ����������д�ر���"

**���Ҫ��**��
1. `_ALWAYS_OVERWRITE` �����е��ֶ��Ƿ�"ÿ�βɼ��ض���ȡ��"���ɼ����ܷ��ؿյ��ֶ�Ӧ�� `_coalesce`��
2. �ⲿ API ���� `None`/`null` ʱ�Ƿ���վ���Ч���ݣ�Ӧ����"��ʽ��ֵ"��"δȡ��"��
3. �ֶ�ȱʧ��API δ���ظ��ֶΣ��Ƿ񱻵���"��ʽ��ֵ"�����Ӧ�� `_coalesce` �����ֵ��
4. �ɼ�ʧ��ʱ�Ƿ��� `None` ���Ǿ���Ч���ݣ�Ӧ�� `_coalesce` �����

**�жϱ�׼**��
- �ɼ����ܷ��ؿյ��ֶΣ��� `image_urls`/`brand`/`description`���� `_ALWAYS_OVERWRITE` �� �� CRITICAL���ɼ�ʧ��ʱ��վ����ݣ�
- �ֶ�ȱʧ������"��ʽ��ֵ"���� �� WARNING�������ֵ����ȫ��
- �ɼ�ʧ��ʱ `None` ���Ǿ���Ч���� �� CRITICAL�����ݶ�ʧ��

**�������**��
```powershell
Select-String -Path "src/xianyu_hunter/**/*.py" -Pattern "_ALWAYS_OVERWRITE|_coalesce|_NULL_SAFE"
```

**���ó���**���ɼ�-�洢��·���ⲿ API �� DB�����ٷ��ɼ�/�زɴ������ݸ���
**�����ó���**����һ���ǲ��ԣ��� `_coalesce` �߼�����������ڲ�����

---

### B-REVIEW-249 RENEWAL-LOOP-WRITEBACK ���ڱջ���д��飨ά�� 7/15��

**��ӦԪ����**��#84 �� 3 �㣨���ڱջ������ԣ�+ #85 �� 1-2 �㣨�ಽ��ɹ۲��ԣ�

**���Ҫ��**��
1. TokenRenewer ���ڻص�����ˢ�� token ���Ƿ��д CookieStore JSON/SQLite
2. ��дʧ���Ƿ�������ڣ�Ӧ����ϣ�token �����ڴ�ˢ�£�
3. ��дʧ���Ƿ����־����ֹ `except: pass` ��Ĭ��
4. loguru ��־ռλ���Ƿ��� `{}`����ֹ `%s` ��׼����
5. �ಽ��ؼ�·������3 ���裩�Ƿ��н��ȱ����־��`����X/N`��

**�жϱ�׼**��
- ���ں�ֻ�����ڴ�δ��д JSON �� CRITICAL��JSON ����Զ�Ǿ�ֵ��
- ��дʧ�� `except: pass` �� CRITICAL����Ĭ�쳣���Ų���������
- loguru ��־�� `%s` ռλ�� �� WARNING���������������ʵ��ֵ��
- �ಽ��·���޽��ȱ����־ �� WARNING����ʱ�޷���λ�����Ĳ���

**�������**��
```powershell
# ���ڻ�д���
Select-String -Path "src/xianyu_hunter/**/*.py" -Pattern "renew_callback|_default_renew|TokenRenewer"
# loguru ռλ�����
Select-String -Path "src/xianyu_hunter/**/*.py" -Pattern "logger\..*%s"
# ��Ĭ�쳣���
Select-String -Path "src/xianyu_hunter/**/*.py" -Pattern "except.*pass|except.*\.\.\."
```

**���ó���**����洢����ͬ����������ڴ� + JSON + SQLite�����ಽ��������Զ�������
**�����ó���**�����洢���ʵ� token ���ڣ�ʹ�ñ�׼�� logging ����Ŀ���� `%s`��

---

> **v4.55.0 B-REVIEW-245~249 ���淶�������**����Ӧ xianyu-hunter-dev v4.54.0 meta-rules #84-#87������ xianyu-auto-testing ģʽ L/M��config.yaml �Ѳ�ȫ B-REVIEW-247/248 ���ýڵ㣨config_field_coverage_backend����

---

## v4.56.0 B-REVIEW-250 �������淶

### B-REVIEW-250: LOGIN-SIDE-EFFECT-AUTOMATION ��¼��ڸ�����һ������飨ά�� 9/15��

**��Ӧ meta-rule**��#89 LOGIN-SIDE-EFFECT-AUTOMATION
**���׹淶**��xianyu-hunter-dev/assets/guides/coding-rules/concurrency.md step 253
**���ýڵ�**��config.yaml#login_side_effect

**����**����¼�ɹ�·�����Զ����� TokenRenewer �Ự���ڵȸ����ã�������ڣ�cookie ���롢�������¼�����Ƶ���ȣ�����©��������"��¼�ɹ����Ựδ���"���û��������⡣

**���Ҫ��**��
1. **���� helper ǿ�Ƶ���**�����е�¼�ɹ�·��������ù��� helper���� `trigger_session_start`������ֹ���������ʵ�ָ������߼�
2. **fire-and-forget ����**�������ñ����� `asyncio.ensure_future()` ���ȵ����¼�ѭ������ֹ `await` ������¼��Ӧ
3. **ʧ�ܰ�ȫԭ��**�����������ʧ�ܽ���¼ `logger.debug`�������쳣����Ӱ���¼�����̷���
4. **helper ģ�����**������ helper �����ڶ���ģ�飨�� `session_starter.py`������ֹ������·�ɴ������
5. **���ò���ע��**��������������ʧ����־���𡢶��������Ȳ�������� config.yaml ��ȡ����ֹӲ����
6. **��ڸ���������**��config.yaml#login_side_effect.entry_points �г���������ڱ���ʵ�ʵ��� helper

**�ж��źţ�grep ���**��
```bash
# �ź� 1����¼�ɹ���δ���� helper
grep -rn "login.*success\|login_success\|��¼�ɹ�" src/xianyu_hunter/web/routes/ | grep -v "trigger_session_start\|session_starter"

# �ź� 2��ֱ�� await �����ã�Υ�� fire-and-forget��
grep -rn "await.*start_session\|await.*token_renewer" src/xianyu_hunter/web/routes/

# �ź� 3��helper ������·��
grep -rn "async def trigger_session_start\|async def _start_side_effect" src/xianyu_hunter/web/routes/
```

**�������**��
```bash
# ͳ�Ƶ�¼����� vs helper ������
grep -c "trigger_session_start" src/xianyu_hunter/web/routes/*.py
grep -c "login.*success\|import.*cookie\|import.*token" src/xianyu_hunter/web/routes/*.py
```

**ͨ����׼**��
- ���� login_success ·�������� `trigger_session_start`
- �� `await.*start_session` ģʽ��Ӧ�� `ensure_future`��
- helper �����ڶ���ģ�飬���� routes/ Ŀ¼
- ʧ�ܴ����� `logger.debug`���� `raise` �� `logger.error`
- ������ config.yaml ��ȡ

**���ó���**��
- ��¼�ɹ���ĻỰ���ڡ�״̬ͬ��������Ԥ�ȵȷǹؼ�������
- ����ڣ�cookie ���롢�������¼�����Ƶ��룩ͳһ����

**�����ó���**��
- ��¼�����̵ĺ�������д�루�� cookie �־û����� ����ͬ�� await
- ������ʧ�ܻᵼ�����ݲ�һ�µĳ��� �� Ӧ��Ϊͬ������
- һ���Խű��� CLI ���� �� ���¼�ѭ���������� fire-and-forget

---

> **v4.56.0 B-REVIEW-250 ���淶�������**����Ӧ xianyu-hunter-dev v4.56.0 meta-rule #89������ xianyu-auto-testing ģʽ N��config.yaml �Ѳ�ȫ login_side_effect ���ýڵ㡣

## v4.57.0 B-REVIEW-251~253 �������淶

> ���ڵ����� Sequential Thinking ��ά�ȸ��̣����� meta-rules #90-#92���������淶 B-REVIEW-251~253 / F-REVIEW-206�����ײ���ģʽ O��

### B-REVIEW-251: FALLBACK-PRESERVE-KEY ���˹��챣���������飨ά�� 11/15��

**��Ӧ meta-rule**��#90 FALLBACK-PRESERVE-KEY
**���׹淶**��xianyu-hunter-dev/assets/guides/coding-rules/data-contract.md step 254
**���ýڵ�**��config.yaml#fallback_preserve_key

**����**��2026-07-22 price_range ע�� Bug ���̷��֣�`get_eval_payload_by_item` ���˹���α item dict ʱ��© `task_id`���������μ۸������ѯ�� `if task_id:` �����ж�������AI �������ȱ�ټ۸��������ݡ����˹����ʵ�屻�����߼������������������жϣ���©�������ᵼ�����ι��ܾ�ĬʧЧ��

**���Ҫ��**��
1. **������������**�����˹����ʵ�壨��α item dict��Ĭ����Ӧ���󣩱������ config.yaml#fallback_preserve_key.required_keys �г������й�������Ĭ�� task_id / user_id / seller_id��
2. **���˹���ʶ��**��ɨ�� try/except �� except ��֧���� dict��if/else �� fallback ��֧���� dict �Ȼ��˹���ģʽ
3. **ȱʧ��־**��������ȱʧʱ�����¼ WARNING ��־��log_level ���ã��������Ų������߼���������
4. **���������ж϶���**�����˹���Ĺ��������������������жϣ��� `if task_id:`�����룬ȷ������ʵ���ܲ��������߼�
5. **���ò���ע��**��required_keys��scan_globs��fallback_patterns �Ȳ�������� config.yaml ��ȡ����ֹӲ����

**�ж��źţ�grep ���**��
```bash
# �ź� 1�����˹���ʵ��ȱ�ٹ�����
grep -rn "fallback.*item\|pseudo.*item\|α.*item\|����.*����" src/xianyu_hunter/infra/repo_*.py src/xianyu_hunter/web/routes/api_*.py | grep -v "task_id\|user_id\|seller_id"

# �ź� 2�����˹��������ȱʧ������־
grep -rn "fallback.*item\|pseudo.*item" src/xianyu_hunter/ | grep -v "logger\.\(warning\|error\)\|logging\.\(warning\|error\)"
```

**ͨ����׼**��
- ���л��˹����ʵ����� required_keys �е����й�����
- ������ȱʧʱ��¼ WARNING ��־
- ���˹���Ĺ����������������ж϶���
- ������ config.yaml ��ȡ

**���ó���**��
- �¼�/������˹���αʵ��ʱ���� payload �������� item������α item dict��
- �ִ��� find_or_fallback ģʽ
- ·�ɲ㹹��Ĭ����Ӧʵ��

**�����ó���**��
- �����ݿ��ѯ������ʵ�壨���������ֶΣ�
- ǰ�˹����չʾ�ö��󣨲��������������жϣ�
- ���� fixtures����ȷ�����ض��ֶ�ȱʧ������

---

### B-REVIEW-252: TIME-WINDOW-FULL-FALLBACK ʱ�䴰�ڲ�ѯȫ��������飨ά�� 7/15��

**��Ӧ meta-rule**��#91 TIME-WINDOW-FULL-FALLBACK
**���׹淶**��xianyu-hunter-dev/assets/guides/coding-rules/data-query.md step 255
**���ýڵ�**��config.yaml#time_window_fallback

**����**��2026-07-22 �۸����� 30 �촰�������� Bug ���̷��֣����ݿ�����Ʒ����ʱ����磬����Ĭ�� 30 �촰�ڵ��²�ѯ���ؿգ�AI ������ȱ�ټ۸��������ݶ�������ʱ�䴰�ڲ�ѯ���ؿ�ʱ������ȫ�����˲��ԣ�����ᵼ�����ι��ܾ�ĬʧЧ��

**���Ҫ��**��
1. **ȫ�����˲���**������ʱ�䴰�ڵ�ͳ�Ʋ�ѯ��range_days / window_days / time_window ���������ؿ�ʱ��������˵�ȫ����ѯ��range_days=0��
2. **Դ�ֶα�ʶ**��ȫ�����˽��Ӧͨ�� source �ֶα�ʶ��Դ��source_value_windowed / source_value_full�����������θ�֪����������
3. **Ĭ�ϴ�������**��Ĭ��ʱ�䴰�ڣ�default_window_days������� config.yaml ��ȡ����ֹӲ����
4. **����������ȷ**�����˴�������������"���ڲ�ѯ���ؿ�"������"��ѯ������� N ��"��ģ������
5. **���ò���ע��**��default_window_days��fallback_to_full��source_field_name �Ȳ�������� config.yaml ��ȡ

**�ж��źţ�grep ���**��
```bash
# �ź� 1��ʱ�䴰�ڲ�ѯ��ȫ������
grep -rn "range_days\|window_days\|time_window" src/xianyu_hunter/infra/repo_*.py src/xianyu_hunter/web/routes/api_*.py | grep -v "fallback\|range_days.*=.*0\|full_query\|ȫ��"

# �ź� 2��ȫ�����˽���� source �ֶ�
grep -rn "range_days.*=.*0\|fallback.*full\|ȫ������" src/xianyu_hunter/ | grep -v "source\|data_source\|��Դ"
```

**ͨ����׼**��
- ����ʱ�䴰�ڲ�ѯ��ȫ�����˲���
- ȫ�����˽��ͨ�� source �ֶα�ʶ��Դ
- Ĭ�ϴ��ڴ� config.yaml ��ȡ
- ����������ȷ�����ڲ�ѯ���ؿգ�

**���ó���**��
- ����ʱ�䴰�ڵ�ͳ�Ʋ�ѯ���۸����䡢����ͳ�ơ��ȶ�������
- ���ݿ��ܼ����ڽ���ʱ��εĲ�ѯ
- AI ����ע����ʷ����ʱ

**�����ó���**��
- ʵʱ��Ҫ��ߵĲ�ѯ���統ǰ��桢ʵʱ�۸�
- ��ȷֻ����� N �����ݵĳ�������"��� 7 ��֪ͨ"��
- ������������ȫ����ѯ���ܲ��ɽ��ܵĳ�����Ӧ���÷�ҳ�򻺴棩

---

### B-REVIEW-253: POWERSHELL-EXPLICIT-SUFFIX PowerShell �ⲿ������ʽ��׺��飨ά�� 12/15��

**��Ӧ meta-rule**��#92 POWERSHELL-EXPLICIT-SUFFIX
**���׹淶**��xianyu-hunter-dev/assets/guides/coding-rules/shell-scripting.md step 256
**���ýڵ�**��config.yaml#powershell_explicit_suffix

**����**��2026-07-22 PowerShell curl ������ͻ Bug ���̷��֣�PowerShell �� `curl` �� `Invoke-WebRequest` �ı�������֧�� `-s`/`-w`/`-d` �� curl ԭ������������ HTTP �ӿڲ�������ʧ�ܡ����⣬PowerShell �� `-d "{\"key\":\"value\"}"` �� `-d '{"key":"value"}'` ��������ת��ʧ�ܣ����� JSON ����Ӧͨ���ļ����ݡ�

**���Ҫ��**��
1. **��ʽ .exe ��׺**��PowerShell �е��� curl/wget ���ⲿ����ʱ����ʹ�� `.exe` ��׺���� `curl.exe`������ֹʹ�ñ������� `curl`��
2. **��ͻ�����б�**��config.yaml#powershell_explicit_suffix.conflicting_aliases �г������д��ڱ�����ͻ�����Ĭ�� curl / wget / rmdir��
3. **JSON body �ļ�����**������ JSON ��������ͨ���ļ����ݣ�`-d "@file"`������ֹ���� JSON �ַ���
4. **���������**����������Ȳ����� command_max_length��Ĭ�� 200 �ַ���������Ӧ�����ļ����ݲ���
5. **���ò���ע��**��conflicting_aliases��required_suffix��json_body_via_file �Ȳ�������� config.yaml ��ȡ

**�ж��źţ�grep ���**��
```bash
# �ź� 1��PowerShell ��ʹ�� curl �������� curl.exe��
grep -rnP "(?<!\.exe)\bcurl\b" --include="*.ps1" .
grep -rnP "(?<!\.exe)\bwget\b" --include="*.ps1" .

# �ź� 2��PowerShell ������ JSON body
grep -rnP "-d\s+['\"]\{.*\}['\"]" --include="*.ps1" .
```

**ͨ����׼**��
- PowerShell �ű��������ⲿ����ʹ�� `.exe` ��׺
- ���� JSON ����ͨ���ļ�����
- ����Ȳ���������
- ������ config.yaml ��ȡ

**���ó���**��
- PowerShell �ű��е��� curl/wget ���ⲿ����
- �����ļ��е� Shell ����ʾ�������ƽ̨���ݣ�
- Windows �����µ� HTTP �ӿڲ���

**�����ó���**��
- Linux/macOS ������bash/zsh �� curl/wget ��ԭ�����
- Python �ű��е� subprocess ���ã�Python ���Լ��Ĳ��������
- PowerShell ԭ������� Get-Content��Invoke-RestMethod��

---

> **v4.57.0 B-REVIEW-251~253 ���淶�������**����Ӧ xianyu-hunter-dev v4.57.0 meta-rules #90-#92������ xianyu-auto-testing ģʽ O��config.yaml �Ѳ�ȫ fallback_preserve_key / time_window_fallback / powershell_explicit_suffix ���ýڵ㡣

---

## v4.60.0 B-REVIEW-267~268 �������淶��2026-07-22 �����ָ��̣�

> ���� xianyu-hunter-dev v4.60.0 meta-rule #101 ��أ���Ӧ"Cookie ״̬�쳣������״̬������ʾ Cookie ��Ч��"���⸴�̡����ýڵ㣺`config/tech-stack.json#hardConstraints.multiWritePathCheck`��

### B-REVIEW-267: MULTI-WRITE-PATH-STATE-CONSISTENCY ��д��·��״̬һ������飨ά�� 8/15��??v4.60

**��������**�������֤���������м��״̬���� CookieRotator._layer_states.valid���������¼/д��·������ͬһ״̬��״̬���ָ��߼������ڴ�״̬��Cookie ��֤�߼���������Ĳ�״̬
**���ýڵ�**��`config/tech-stack.json#hardConstraints.multiWritePathCheck`
- `intermediateStatePatterns`���м��״̬�ֶ�ģʽ�б��`_layer_states`��`.valid`��`.active`��`_state`��
- `writeEntryPatterns`��д�����ģʽ�б��`on_login_success`��`atomic_update`��`sync_state_from_cookies`��`_handle_login`��`_inject_cookie`��
- `validateActualDataPreferred`���Ƿ�������֤ʵ�����ݣ�true��
- `autoSyncEnabled`���Ƿ������Զ�ͬ����true��
- `syncMethodPattern`��ͬ����������ģʽ��`sync_state_from_*`��

**��鲽��**��
1. **ʶ���м��״̬����**��Grep ɨ���˴�������֤�������õ��м��״̬�ֶ�
2. **ö������д��·��**��Grep ɨ�����п��ܸ��¸�״̬��д����ڣ���¼�ɹ��ص���Cookie ע�롢Cookie ˢ�¡��ֶ����õȣ�
3. **��֤д��·��������**����ÿ��д����ڣ�����Ƿ������״̬��ʼ��/ͬ���߼�����1 ��д��·��δ���� �� P0 ȱ�ݣ����򣺶���д��·��δ��ʼ��״̬��������֤������ȡĬ�� False ֵ��
4. **����ʵ��������֤**����֤�����Ƿ�ֱ�Ӽ��ʵ�����ݣ��� Cookie ���ݡ�expires �ֶΡ�token �����ԣ����ǽ������м��״̬�������������Զ�ͬ�� �� P1 ȱ��
5. **�Զ�ͬ������**����֤�����ڷ���״̬��һ��ʱ�Ƿ��Զ�ͬ������ `sync_state_from_cookies`�������Զ�ͬ���������м��״̬ �� P1 ȱ��
6. **״̬��ʼ��ʱ��**�����״̬�Ƿ��ڷ������ʱ��ȷ��ʼ������ӳ־û��洢���أ������������ʱ״̬ΪĬ��ֵ

**Grep ����**��
```bash
# ʶ���м��״̬����
grep -rn "_layer_states\|\.valid\|\.active\|_state\[" src/ --include="*.py"
# ö��д�����
grep -rn "on_login_success\|atomic_update\|sync_state\|_handle_login\|_inject_cookie\|cookie_inject" src/ --include="*.py"
# ��֤д��·�������ԣ�д�����δ����״̬��ʼ����
grep -rn "def _handle_login\|def _inject_cookie\|def cookie_inject" src/ --include="*.py" | grep -v "on_login_success\|sync_state\|atomic_update"
# ������֤���������м��״̬
grep -rn "def.*check.*cookie\|def.*validate.*cookie\|def.*cookie_check" src/ --include="*.py"
```

**���ó���**��Cookie ״̬�����CookieRotator ��״̬������¼̬ͬ�������¼·�����������״̬��_cache/_cache_time �ֶΣ���������״̬�����˺��ֻ���״̬��account_rotator��
**�����ó���**��������״̬���޳־û����󣩡�������ʱ״̬��request_context�����޶�д��·���ĵ�Դ״̬
**�����й���Ĺ�ϵ**������ B-REVIEW-245��SCHEDULER-STATE-MACHINE-RECOVERY���� B-REVIEW-246��COOKIE-TOKEN-SEPARATION����ǰ�߹�ע������״̬���ָ����������ע��д��·����״̬һ����

---

### B-REVIEW-268: COOKIE-VALIDATE-ACTUAL-DATA Cookie ��֤Ӧ����ʵ��������飨ά�� 9/15��??v4.60

**��������**��Cookie ��Ч�Լ��ӿڣ��� `/api/anticrawl/check`����Cookie ����״̬չʾ��Cookie �ֻ��߼��е���Ч���жϡ�Token ���ں��״̬����
**���ýڵ�**��`config/tech-stack.json#hardConstraints.multiWritePathCheck`
- `validateActualDataPreferred`���Ƿ�������֤ʵ�����ݣ�true��ǿ��Ҫ��
- `autoSyncEnabled`���Ƿ������Զ�ͬ����true����֤���Զ�ͬ����״̬��

**��鲽��**��
1. **��֤����Դ**��Cookie ��֤��������ֱ�Ӽ�� Cookie ʵ�����ݣ��� `_m_h5_tk` token �����ԡ�`expires` ����ʱ�䡢identity Cookie �����ԣ������ǽ���ȡ CookieRotator._layer_states.valid �ڴ�״̬
2. **��֤ expires �ֶ�**��Cookie �洢ʱ���뱣�� `expires` �ֶΣ���֤ʱ���������ʱ�䡣��� Cookie �洢������ expires �ֶ� �� P0 ȱ��
3. **��֤�Զ�ͬ��**����֤�����ڼ��ʵ�����ݺ󣬱����Զ�ͬ����״̬������ `sync_state_from_cookies` �����Ʒ������������֤��ͬ�� �� P1 ȱ�ݣ�������֤������״̬��һ�£������߼���ȡ��״̬��
4. **��֤ token ������**��Cookie ��֤������ؼ� token���� `_m_h5_tk`��`_tb_token_`��`cookie2`��`sgcookie`���Ƿ���ڣ����ǽ���� identity Cookie
5. **��֤��־��¼**����֤��������¼ʵ������״̬���� token �Ƿ���ڡ�expires �Ƿ���ڣ������ǽ���¼"��Ч/��Ч"����ֵ������¼����ֵ �� P2 ȱ��
6. **��֤������ȫ**����֤�����ڶ��߳�/�첽�����±���ʹ��������״̬ͬ������

**Grep ����**��
```bash
# ���� Cookie ��֤����
grep -rn "def.*check.*cookie\|def.*validate.*cookie\|def.*cookie_check\|def.*cookie_health" src/ --include="*.py"
# ����Ƿ������м��״̬����ʵ������
grep -rn "_layer_states.*valid\|\.valid\b" src/ --include="*.py" | grep -i "check\|validate\|health"
# ��� expires �ֶ��Ƿ񱻱���
grep -rn "expires" src/xianyu_hunter/web/services/cookie_store.py
# ����Ƿ����Զ�ͬ��
grep -rn "sync_state_from_cookies\|sync_state" src/ --include="*.py"
```

**���ó���**��Cookie ��Ч�Լ��ӿڡ�Cookie ����״̬չʾ��Cookie �ֻ����߼���Token ���ں�״̬���¡����˺� Cookie ����
**�����ó���**���� Cookie ��״̬��֤���� API ������飩������־û�����ʱ Cookie����Ự�� CSRF token��
**�����й���Ĺ�ϵ**������ B-REVIEW-246��COOKIE-TOKEN-SEPARATION���� B-REVIEW-249��COOKIE-STATE-SYNC-REFRESH ǰ�˶�Ӧ����ǰ�߹�ע Cookie �� Token ����洢���������ע��֤�߼�Ӧ����ʵ������

---

> **v4.60.0 B-REVIEW-267~268 ���淶�������**����Ӧ xianyu-hunter-dev v4.60.0 meta-rule #101�������أ���config/tech-stack.json �Ѳ�ȫ `hardConstraints.multiWritePathCheck` ���ýڵ㡣ǰ�˶�Ӧ F-REVIEW-214��auto-testing ��Ӧģʽ T��


## v4.61.0 B-REVIEW-269~274 �������淶��2026-07-22 ����淶 ��2.15-��2.20 ��أ�

> ��Ӧ coding-standards.md ��2.15-��2.20 ���� 6 �ڱ���淶������"Ӳ�����Ų������û�"���̡����м���ǿ������������������ config.yaml ��Ӧ�ڵ�������Ӳ����ҵ�������������/�����ó���˵����ȷ��ͨ���ԣ������ײ���ģʽ��xianyu-auto-testing ģʽ P�����û��뻺����Իع飩��

### B-REVIEW-269: CACHE-STRATEGY ������ԺϹ���飨ά�� 7/15��

**��Ӧ����淶**����2.15 �������
**���ýڵ�**��config.yaml#cache

**����**������ TTL Ӳ���롢�ս���������ڸ�ʵʱ���ݻָ�������д��������ҵ���߼���ϣ����»�����Ч���ڷ��ع�ʱ���ݻ���б��

**���Ҫ��**������ʽ����

**��λ����**��
```bash
grep -rn "_cache\s*=\|CACHE_TTL\|cache_ttl\|_LIVE_CACHE_TTL" src/xianyu_hunter/ --include="*.py"
```

**�жϱ�׼��Υ���ж���**��
1. **TTL Ӳ����**������ TTL ʹ��ģ�鼶�������� `_LIVE_CACHE_TTL = 60`�����Ǵ� config.yaml ��ȡ �� CRITICAL
2. **�ս������**����ѯ���� 0 ����¼ʱ��д�뻺�棨`if items:` д DB �� `if filtered:` д�����������һ�£� �� CRITICAL
3. **�����������**������д������������ҵ���߼����� DB д����������ϣ�δ�����ж� �� WARNING
4. **TTL ��ͬԴ**���������м��ʱ��ȡ�� TTL ��д��ʱʹ�õ� TTL ��Դ��һ�� �� WARNING

**�޸�����**��
- �� TTL Ǩ�Ƶ� config.yaml �� cache �飨�� `cache.live_search_ttl`��
- �ս����0 records��������������д�룬���⻺����Ч���ڷ��ؿ��б��ڸ�ʵʱ���ݻָ�
- ����д�������������������ҵ���߼���`if filtered:` ����д�� vs `if items:` DB д�룩
- �������淶 ��2.15

**���ó���**��ʵʱ�������桢�б��ѯ���桢���ö�ȡ���桢Cookie ״̬����
**�����ó���**���� TTL �����û��桢����������ʱ�����������㺯��������棨������Դ������

---

### B-REVIEW-270: STATE-SYNC ״̬ͬ����������飨ά�� 9/15��

**��Ӧ����淶**����2.16 ״̬ͬ��
**���ýڵ�**��config.yaml#state_sync

**����**����㼶״̬У������δ��ʼ�����ڴ�㻺��״̬����¼�ɹ�/Token ˢ��/�ⲿ�����״̬���·��δ����ͬ��������������֤������ȡ����״̬��

**���Ҫ��**������ʽ����

**��λ����**��
```bash
grep -rn "checker\|is_valid\|_valid\b\|_layer_states\|\.valid\b" src/xianyu_hunter/ --include="*.py"
```

**�жϱ�׼��Υ���ж���**��
1. **�ڴ�״̬����**��У���߼�����δ��ʼ�����ڴ�״̬�ֶΣ��� `_layer_states.valid`������ʵ�ʴ洢���� �� CRITICAL
2. **ȱ��ͬ������**��״̬������ȱ����ʽ `sync_state_from_xxx()` ���� �� WARNING
3. **���·��δͬ��**������״̬���·������¼�ɹ�/Token ˢ��/�ⲿ���룩δ���� `sync_state_from_xxx()` ͬ������ �� CRITICAL
4. **��֤���ڻ���**����֤��������ȡ�����״̬����ʵ�����ݣ�Cookie �ļ�/DB ��¼�� �� CRITICAL

**�޸�����**��
- ��㼶״̬У��������ʵ�ʴ洢���ݣ�Cookie �ļ�/DB ��¼�����������ڴ�㻺��״̬
- ��� `sync_state_from_xxx()` ����������״̬���·���������
- �������淶 ��2.16

**���ó���**��Cookie ״̬�����CookieRotator ��״̬������¼̬ͬ�������¼·�����������״̬��_cache/_cache_time �ֶΣ���������״̬�����˺��ֻ���״̬
**�����ó���**��������״̬���޳־û����󣩡�������ʱ״̬��request_context�����޶�д��·���ĵ�Դ״̬

---

### B-REVIEW-271: PERF-OPTIMIZATION �����Ż��˲�����飨ά�� 8/15��

**��Ӧ����淶**����2.17 �����Ż�
**���ýڵ�**��config.yaml#performance

**����**�������¼�ѭ����ͬ�����á���Ƶ��ѯ�޻���㡢����δ���Ƶ� SQL��list+count δ�ϲ�����ʱ�ӿ�δ�� SSE������ API ��Ӧ������

**���Ҫ��**������ʽ����

**��λ����**��
```bash
grep -rn "requests\.get\|requests\.post\|time\.sleep\|\.all()\|\.execute()" src/xianyu_hunter/ --include="*.py"
```

**�жϱ�׼��Υ���ж���**��
1. **�����¼�ѭ��**���� async ������ʹ��ͬ�����ã�requests.get/time.sleep��δ�� run_in_executor �� CRITICAL
2. **��Ƶ��ѯ�޻���**����Ƶ��ѯ�ӿ�ȱ�ٻ���㣨dict+TTL�� �� WARNING
3. **����δ����**��Python ����ˣ�`[x for x in query.all() if ...]`������ SQL WHERE ���� �� WARNING
4. **list+count δ�ϲ�**����ҳ��ѯִ������ SQL��list + count�����Ǻϲ�Ϊһ�� CASE WHEN �ۺϲ�ѯ �� WARNING
5. **��ʱ�ӿ�δ�� SSE**����ʱ�ӿڣ���ʵʱ������ʹ����ѯ���� SSE ��ʽ��Ӧ �� WARNING
6. **ǰ���޻���**��ǰ���б�����δ�� useMemo ���浼���ظ����� �� WARNING
7. **�����ȼ���**��������ռ�ù�����δ�����ȼ�����priority lock���ö��������� �� WARNING

**�޸�����**��
- �����Ż��˲������첽����run_in_executor��+ ���棨dict+TTL��+ SQL ���ƣ�WHERE ���ˣ�+ �ϲ���ѯ��list+count��+ ǰ�˻��棨useMemo��+ ���ȼ�����priority lock��+ ��ʽ��Ӧ��SSE��+ ���� DB д��
- �������淶 ��2.17

**���ó���**��ʵʱ�����ӿڡ��б��ѯ�ӿڡ������ɼ����̡�Dashboard ͳ�Ʋ�ѯ����ʱ LLM ����
**�����ó���**������д�������������ƿ���ļ򵥲�ѯ��������������

---

### B-REVIEW-272: SCORING-SYSTEM ����ϵͳ�Ϲ���飨ά�� 10/15��

**��Ӧ����淶**����2.18 ����ϵͳ
**���ýڵ�**��config.yaml#scoring

**����**������ϵͳȱ�����������ּ����۷�ʹ�����Զ��� Sigmoid ���������徲̬���㡢AI �������δ���ɵ��ܷ֣�����������ʵ�ʳ�ɫ����ƫ�롣

**���Ҫ��**������ʽ����

**��λ����**��
```bash
grep -rn "evaluate\|score\|_eval\|sigmoid\|buffer\|quality" src/xianyu_hunter/ --include="*.py"
```

**�жϱ�׼��Υ���ж���**��
1. **�����������ּ�**������ϵͳȱ�����������ּ������/��/�� 3 ���� �� WARNING
2. **���Կ۷�**���۷�ʹ�����Թ�ʽ���� Sigmoid ���������±߽�ͻ�䣩 �� WARNING
3. **��̬����**������ֵ��̬������Ǹ������������ȶ�̬���� �� WARNING
4. **AI ����δ����**��AI �����������Ϊ metadata �洢���Ǽ��ɵ��ܷ� �� CRITICAL
5. **һƱ�������**��һƱ�������ֵ��������Դ��ʵ��Χ �� CRITICAL

**�޸�����**��
- ʵ�� 3 �����������ּ�����/��/�ͣ�
- �۷�ʹ�� Sigmoid ������ʽ������߽�ͻ�䣩
- ����ֵ�������������ȶ�̬����
- AI �����������ͨ�� apply_ai_eval() ���ɵ��ܷ�
- �������淶 ��2.18

**���ó���**����Ʒ�������֡�����������֡����յȼ��ж���AI �����������
**�����ó���**���������߼��ļ� CRUD����չʾ�����ݡ������������ּ��ĵ�һ����Դ

---

### B-REVIEW-273: EXT-DEP-FAULT-TOLERANCE �ⲿ�����ݴ���飨ά�� 12/15��

**��Ӧ����淶**����2.19 �ⲿ�����ݴ�
**���ýڵ�**��config.yaml#external_dep

**����**��token δԤˢ�µ��� API ǩ��ʧ�ܡ�DOM ѡ�����ޱ�ѡ���½���ʧ�ܡ��������������±��⡢��־��ʽ��ͳһ�����Ų����ѡ�

**���Ҫ��**������ʽ����

**��λ����**��
```bash
grep -rn "RGV587\|token\|query_selector\|retry\|_m_h5_tk\|Selector" src/xianyu_hunter/ --include="*.py"
```

**�жϱ�׼��Υ���ж���**��
1. **token ��Ԥˢ��**��token �����ǰδԤˢ�£����ڹ��ں�ˢ�£� �� CRITICAL
2. **DOM �ޱ�ѡ**��DOM ѡ����ֻ��һ��ѡ�����ޱ�ѡ��querySelector ���ˣ� �� WARNING
3. **����������**�������߼�δ�� asyncio.Semaphore ���Ʋ���/QPS �� WARNING
4. **��־��ʽ��ͳһ**��loguru ��־ʹ�� `%s` ռλ������ `{}` �� WARNING
5. **�쳣��Ĭ**���ⲿ���������쳣�� `except: pass` ��Ĭ�̵� �� CRITICAL

**�޸�����**��
- token Ԥˢ�£������ǰˢ�£�
- DOM �ݴ��querySelector ��������
- �������ԣ�asyncio.Semaphore ���� QPS��
- ��־ͳһʹ�� loguru �� `{}` ռλ��
- �������淶 ��2.19

**���ó���**��MTOP API ���ã�token ǩ������������Զ�����DOM ѡ��������������������ã�������������Cookie �����token ˢ�£�
**�����ó���**���ڲ�ͬ���������á������������һ���Բ����������㺯��

---

### B-REVIEW-274: MULTI-FORMAT-PARSE ���ʽ���������飨ά�� 11/15��

**��Ӧ����淶**����2.20 ���ʽ�������
**���ýڵ�**��config.yaml#input_parse

**����**������������赥һ��ʽ���ָ�㲻�ݴ���� `split('=')` ��ֵ���� `=` ʱ�ضϣ�����Ч��δ���˵��º����߼��쳣��

**���Ҫ��**������ʽ����

**��λ����**��
```bash
grep -rn "split\|parse\|clipboard\|paste\|import.*from" src/xianyu_hunter/ --include="*.py"
```

**�жϱ�׼��Υ���ж���**��
1. **δö�ٸ�ʽ**���������δö�����п��ܵ������ʽ�������赥һ��ʽ�� �� WARNING
2. **�ָ�㲻�ݴ�**���ָ�ʹ�� `split('=')` ���� `indexOf('=')` �ݴ��ֵ���� `=` ʱ���ضϣ� �� CRITICAL
3. **��Ч��δ����**�����������Ч��ռ�/��ֵ��δ����ֱ��ʹ�� �� WARNING
4. **��ʵʱ����**������ʧ��ʱ��ʵʱ�������û�����Ĭʧ�ܣ� �� WARNING

**�޸�����**��
- ö�����������ʽ����ʽö�٣�
- �ݴ�ָ`indexOf('=')` ȡ��һ�� `=` ��Ϊ�ָ�㣩
- ������Ч��ռ�/��ֵ���ˣ�
- ʵʱ����������ʧ��ʱ��ʾ�û���
- �������淶 ��2.20

**���ó���**��Cookie �������롢Token ճ�������������ļ����롢���������ݽ���
**�����ó���**���ṹ�����루JSON/YAML �ѽ���������һ��ʽ���루��֪��ʽ���������ڲ����ݴ���

---

> **v4.61.0 B-REVIEW-269~274 ���淶�������**����Ӧ coding-standards.md ��2.15-��2.20 ���� 6 �ڱ���淶��config.yaml �Ѳ�ȫ cache / state_sync / performance / scoring / external_dep / input_parse ���ýڵ㡣

---

## 44. 四维度复盘编码规范落地 Review v4.60.0

- Severity: HIGH (P1, 基于12个历史问题的四维度复盘，提炼缓存守卫/数据写入策略/状态机语义/跨层闭环等核心规范)
- Reference: meta-rules #102 / 四维度复盘 (缓存策略/数据完整性/状态管理/跨层一致性)

### B-REVIEW-275: CACHE-GUARD-3RULES 缓存守卫三原则（维度：缓存策略）

**配置节点**：config.yaml#cache_guard

**问题**：缓存TTL硬编码、空结果被缓存导致脏数据、缓存写入守卫与业务逻辑耦合导致缓存条件遗漏。

**关键要求**：三原则必须全部满足

**定位方式**：
```bash
grep -rn "TTL\|cache\[" src/xianyu_hunter/ --include="*.py"
```

**判断标准（违反判断）**：
1. **TTL硬编码**：缓存TTL使用字面量数字而非从config读取 → CRITICAL
2. **空结果缓存**：空列表/None结果直接写入缓存，后续请求读到脏数据 → WARNING
3. **缓存守卫耦合**：缓存写入条件与DB写入条件相同，而非独立判断 → WARNING

**修复方案**：
- (1) 配置化TTL：所有TTL从config读取，如 `config.cache.live_search_ttl`
- (2) 空结果不缓存：`if filtered: cache[key] = filtered`，空结果跳过缓存写入
- (3) 缓存条件独立：缓存写入守卫独立于业务逻辑，不依赖DB写入条件

**结果呈现**：📋 缓存守卫检查清单——违反原则[具体项]

**适用场景**：所有涉及缓存的代码（live_search缓存、token缓存、session缓存等）
**不适用场景**：无缓存的纯计算逻辑、一次性写入不读取的临时缓存

---

### B-REVIEW-276: FIELD-STRATEGY 数据写入策略字段级决策（维度：数据完整性）

**配置节点**：config.yaml#field_strategy

**问题**：_ALWAYS_OVERWRITE 和 _coalesce 使用不当，导致字段值被意外覆盖或应覆盖而未覆盖。

**关键要求**：每个字段必须有明确的写入策略和理由

**定位方式**：
```bash
grep -rn "_ALWAYS_OVERWRITE\|_coalesce" src/xianyu_hunter/ --include="*.py"
```

**判断标准（违反判断）**：
1. **不该覆盖的被覆盖**：image_urls/title 等应保留已有值的字段出现在 _ALWAYS_OVERWRITE 中 → CRITICAL
2. **该覆盖的未覆盖**：is_sold/status 等应始终以最新值为准的字段未在 _ALWAYS_OVERWRITE 中 → WARNING
3. **无策略文档**：字段加入 _ALWAYS_OVERWRITE 或 _coalesce 但无注释说明理由 → WARNING

**修复方案**：
- 将不应覆盖的字段从 _ALWAYS_OVERWRITE 移出，采用 _coalesce（仅填充空值）
- 确保 _ALWAYS_OVERWRITE 中的字段有明确注释说明为何必须覆盖
- 参照 config.yaml#field_strategy 中的 alwaysOverwriteFields / coalesceFields 配置

**结果呈现**：🔍 字段写入策略审查——[字段名]不应在_ALWAYS_OVERWRITE中

**适用场景**：upsert操作、数据同步写入、多源数据合并
**不适用场景**：单源单次写入、创建操作（非更新）

---

### B-REVIEW-277: STATE-MACHINE-RETURN 状态机返回值语义（维度：状态管理）

**配置节点**：config.yaml#state_machine_return

**问题**：scheduler/session状态流转中的return True/False语义模糊，调用方可能误解读导致流程中断或遗漏。

**关键要求**：返回值语义必须与调用方逻辑对齐

**定位方式**：
```bash
grep -rn "return True\|return False" src/xianyu_hunter/ --include="*.py" | grep -i "pause\|resume\|schedule\|session"
```

**判断标准（违反判断）**：
1. **返回值语义歧义**：return True在调用方被解释为break/continue/成功/失败等不同含义 → CRITICAL
2. **调用方误用**：调用方根据返回值做分支判断但语义与实现不一致 → WARNING
3. **缺少文档**：状态流转方法的返回值无文档说明其语义 → WARNING

**修复方案**：
- 明确return值语义文档：每个状态流转方法的返回值含义必须文档化
- 验证调用方使用方式：确保调用方对返回值的解读与实现一致
- 参照 config.yaml#state_machine_return.returnSemanticsDocument 配置

**结果呈现**：⚠️ 返回值语义歧义——return True在调用方被解释为break

**适用场景**：scheduler状态流转、session暂停/恢复、任务状态切换
**不适用场景**：无状态的操作方法、纯计算函数

---

### B-REVIEW-278: CALLBACK-INJECTION 回调注入默认值（维度：依赖注入）

**配置节点**：config.yaml#callback_injection

**问题**：回调函数初始化为None且未设置默认值，运行时调用None导致AttributeError。

**关键要求**：回调必须提供合理默认值+外部覆盖守卫

**定位方式**：
```bash
grep -rn "callback.*=.*None\|_callback\s*:" src/xianyu_hunter/ --include="*.py"
```

**判断标准（违反判断）**：
1. **回调为None**：回调参数默认为None且调用前无空值检查 → CRITICAL
2. **无默认实现**：缺少合理的默认回调实现（如safe_headless策略） → WARNING
3. **覆盖无守卫**：外部覆盖回调时无类型/签名校验 → WARNING

**修复方案**：
- 添加默认回调实现：`_default_callback` 提供safe_headless行为
- 添加覆盖守卫：外部覆盖时校验回调签名和类型
- 双路径测试：默认回调路径+自定义回调路径均需测试覆盖

**结果呈现**：🔧 回调未设置默认值——[callback名]可能为None导致运行时错误

**适用场景**：浏览器回调、事件回调、通知回调等依赖注入场景
**不适用场景**：必须由调用方提供的必需回调（非可选）

---

### B-REVIEW-279: CROSS-LAYER-CLOSED-LOOP 跨层闭环验证（维度：跨层一致性）

**配置节点**：config.yaml#cross_layer_closed_loop

**问题**：Cookie/Token/字段在A层写入但B层未同步读取，导致跨层状态不一致。

**关键要求**：修复后必须验证整条链路的写入→读取闭环

**定位方式**：
```bash
grep -rn "cookie_store\|token_renewer\|sync_state" src/xianyu_hunter/ --include="*.py"
```

**判断标准（违反判断）**：
1. **写入未同步**：某层写入字段但其他层未读取到最新值 → CRITICAL
2. **缺少同步方法**：跨层状态变更后无 sync_state_from_xxx() 同步方法 → WARNING
3. **同步时机不对**：同步方法存在但调用时机滞后，导致中间状态不一致 → WARNING

**修复方案**：
- 添加同步方法：`sync_state_from_xxx()` 在写入后立即同步
- 验证闭环：修复后必须验证整条链路的写入→读取闭环
- 参照 config.yaml#cross_layer_closed_loop.layersToCheck 和 syncMethodPattern 配置

**结果呈现**：🔗 跨层闭环验证——[字段]在[层A]写入但[层B]未同步

**适用场景**：Cookie跨层同步、Token跨层刷新、DB字段跨层写入
**不适用场景**：单层内的状态变更、无跨层依赖的纯内部状态

---

### B-REVIEW-280: WINDOWS-ENCODING Windows编码规范（维度：跨平台兼容）

**配置节点**：config.yaml#windows_encoding

**问题**：BAT/PS1脚本中包含中文字符，在GBK默认编码的Windows环境下导致乱码或执行失败。

**关键要求**：脚本中禁止中文或指定编码

**定位方式**：
```powershell
Get-ChildItem -Path "scripts/" -Filter "*.ps1","*.bat" -Recurse | Select-String -Pattern "[\u4e00-\u9fff]"
```

**判断标准（违反判断）**：
1. **BAT含中文**：.bat文件包含中文字符且未指定编码 → CRITICAL
2. **PS1含中文**：.ps1文件包含中文字符且未声明UTF-8 → WARNING
3. **Node路径未指定**：脚本中调用Node但未指定完整路径 → WARNING

**修复方案**：
- 中文字符替换为英文等效表述
- 指定UTF-8编码：BAT文件首行添加 `chcp 65001`，PS1文件添加 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`
- 指定Node完整路径：避免依赖PATH环境变量
- 参照 config.yaml#windows_encoding 配置

**结果呈现**：⚠️ Windows编码风险——[文件名]含中文字符可能导致GBK冲突

**适用场景**：所有BAT/PS1脚本、构建脚本、部署脚本
**不适用场景**：纯Python脚本（Python默认UTF-8）、JSON/YAML配置文件（编码已指定）

---

> **v4.60.0 B-REVIEW-275~280 四维度复盘编码规范落地**：基于12个历史问题复盘，新增缓存守卫三原则/数据写入策略字段级决策/状态机返回值语义/回调注入默认值/跨层闭环验证/Windows编码规范 6 项审查要点，config.yaml 已补全 cache_guard / field_strategy / state_machine_return / callback_injection / cross_layer_closed_loop / windows_encoding 配置节点。