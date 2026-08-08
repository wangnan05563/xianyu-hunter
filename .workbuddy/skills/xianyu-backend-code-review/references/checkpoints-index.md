# 检查点 ID 索引（references/checkpoints-index.md）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **用途**：按 B-REVIEW-* 检查点 ID 反查检查点名称、所属维度、配置节点、规范源（v4.x 引入版本）。本表是冷区域（按需查阅），日常审查无需预加载。
> **维护原则**：新增检查点时在本表追加一行（按 ID 升序），同时在 SKILL.md 维度正文中添加完整描述。
> **当前统计**：共 232 项检查点（B-REVIEW-NNN 编号 + B-REVIEW-NAME 命名两套体系并行），覆盖 47 个审查维度（v4.70.0 新增 B-REVIEW-337 源码文件编码完整性；v4.69.0 新增 B-REVIEW-332~334 双数据源一致性保障；v4.68.0 experimental 新增 B-REVIEW-331 事件驱动基础设施启动解耦；v4.67.0 experimental 新增 B-REVIEW-330 类型注解契约对齐；v4.65.0 新增维度 38/39/40 架构层依赖强化+SQLAlchemy 写路径并发保护+搜索服务模板方法，11 项 B-REVIEW-316~326；v4.64.0 新增维度 37 资源创建幂等性与前端状态闭环；v4.63.0 多用户安全审计 18 项已补发同步；v4.62.0 新增维度 45 LLM 多调用治理）。

---

## 完整索引表（按 ID 升序）

| ID | 名称 | 引入版本 | 维度 | 配置节点 |
|----|------|----------|------|----------|
| B-REVIEW-110 | EXCLUDE-UNSET-CHECK：API 更新接口 exclude_unset 检查 | - | 12. API 设计 | config.yaml: coding_standards |
| B-REVIEW-111 | NOT-NULL-NONE-DEFENSE：NOT NULL 字段 None 防御检查 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-112 | SHARED-SINGLETON-POLLUTION：共享单例污染检查 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-121 | 时区一致性检查 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-122 | 原生 SQL 返回值类型防御 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-123 | 迁移步骤独立性 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-124 | NOT NULL 字段防御 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-125 | 查询过滤条件精确性 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-126 | 状态值枚举一致性 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-127 | 错误归因精细化 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-128 | 异常传播完整性 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-129 | 错误消息透传 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-130 | 重试策略配置化 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-131 | 已知场景日志降噪 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-132 | 熔断器持久化对称性 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-133 | 状态切换原子性 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-134 | 多源失效判定一致性 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-135 | 缺失数据回退策略 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-136 | 多源状态同步标记机制 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-CHROME-136-ADAPTATION | Chrome 136+ 限制适配模式 | - | 1-2. 架构/命名 | config.yaml: coding_standards |
| B-REVIEW-137 | 异步竞态防护 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-138 | 参数传递链完整性 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-139 | 业务关键词配置化 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-140 | 开关持久化 | - | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: coding_standards |
| B-REVIEW-141 | 凭证多存储同步 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-142 | 属性调用一致性 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-143 | API 契约一致性 | - | 12. API 设计 | config.yaml: coding_standards |
| B-REVIEW-144 | 命名语义清晰性 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-145 | 重复逻辑抽取 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-146 | 跨进程编码一致性 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-147 | dataclass 字段显式声明 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-148 | 启动钩子完整性 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-149 | 测试 Mock 类型匹配 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-150 | Cookie 完整性管理 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-151 | 批量断路器四要素 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-152 | 关键路径异常保留完整 traceback | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-153 | datetime 统一时区策略 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-154 | 跨进程状态同步六步法 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-155 | 前后端错误码契约 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-156 | 业务关键字常量集中管理 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-157 | RESUME-PRECHECK 状态恢复前置校验 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-158 | LOG-MERGE 多阶段降级链日志合并 | - | 17. 日志规范 | config.yaml: coding_standards |
| B-REVIEW-160 | ROOT-CAUSE-CHAIN-CHECK 修复前全链路根因扫描协议 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-161 | CONTRACT-OWNER-MARKER 前后端字段契约单一可信源 | - | 30. 契约 | config.yaml: coding_standards |
| B-REVIEW-162 | SEDIMENTATION-THRESHOLD 规范立项前置计数 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-163 | DEGRADATION-CLEANUP 规范退化清理 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-164 | GLOBAL-AGGREGATE-TASK-FILTER 全局聚合任务级过滤 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-165 | LIST-CROSS-DOMAIN-INJECT 列表交叉数据批量注入 | - | 10. 业务建模 | config.yaml: coding_standards |
| B-REVIEW-166 | MULTI-FIELD-LINKED-SWITCH 多字段联动开关范式 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-167 | RESUME-PRECHECK-STRUCTURED 状态恢复前置校验结构化响应 | - | 20-27. 国际化/Web/缓存/迁移/认证/集成 | config.yaml: coding_standards |
| B-REVIEW-168 | CONFIG-DRIVEN-THRESHOLD-FALLBACK 配置化阈值兜底范式 | - | 6. 配置驱动 | config.yaml: coding_standards |
| B-REVIEW-173 | EVENT-MULTI-EMIT-ALIGN 事件多发布点字段对齐 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-174 | ROUTE-REGISTRY-BACKEND-SYNC 路由注册表与后端 endpoint 契约 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-175 | CALLBACK-URL-QUERY-CONSTRUCTION 回链 URL query string 构造 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-176 | TEST-SIGNATURE-SYNC 接口签名变更测试同步 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-177 | PARAM-CHAIN-EXEC 参数链闭环验证 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-178 | MODE-VERTICAL-CHAIN 业务模式纵向链路一致性 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-179 | PARSER-FALLBACK-CHAIN 外部页面解析容错 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-180 | MOCK-SYNC-BOUNDARY mock 同步与边界精确性 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-181 | CRON-MIN-INTERVAL-CHECK 用户输入时间表达式校验 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-182 | ASYNC-AWAIT-SYNC-CHECK async/await 同步性静态检查 | - | 3. 异步并发 | config.yaml: coding_standards |
| B-REVIEW-183 | RESOURCE-POOL-BENCHMARK 资源池配置性能基准 | - | 9. 资源管理 | config.yaml: coding_standards |
| B-REVIEW-184 | HTTP-STATUS-CODE-MAPPING HTTP 状态码精细化映射 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-185 | CSS-SELECTOR-FALLBACK CSS 选择器多级降级 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-186 | EXCEPTION-LOG-SEMANTIC 异常日志语义保留 | - | 17. 日志规范 | config.yaml: coding_standards |
| B-REVIEW-187 | EXTERNAL-RESOURCE-LIFECYCLE 外部资源生命周期配对 | - | 9. 资源管理 | config.yaml: coding_standards |
| B-REVIEW-188 | DB-WRITE-IDENTITY-TRACE 数据库写入身份追溯 | - | 11. 数据库/ORM | config.yaml: coding_standards |
| B-REVIEW-189 | BUSINESS-STATUS-CODE-CONFLICT 业务异常状态码冲突检查 | - | 28-36. 工程闭环/现代化 | config.yaml: coding_standards |
| B-REVIEW-226 | ASYNC-BLOCKING-CALL-TIMEOUT async 阻塞调用超时保护 | v4.48.0 | 35. 工程闭环/现代化 | config.yaml: async_timeout_protection |
| B-REVIEW-227 | SUBPROCESS-HEARTBEAT-STAGE-COORDINATION 子进程心跳与阶段超时协同 | v4.48.0 | 35. 工程闭环/现代化 | config.yaml: subprocess_heartbeat |
| B-REVIEW-228 | CROSS-BLOCK-CONSISTENCY-CHECK 跨代码块一致性检查 | v4.48.0 | 35. 工程闭环/现代化 | config.yaml: consistency_check |
| B-REVIEW-229 | MONKEYPATCH-FROM-IMPORT-COVERAGE monkeypatch 模块级 from-import 覆盖完整性 | v4.49.1 | 37. 测试质量与同步性 | config.yaml: test_quality_protection.monkeypatch_coverage |
| B-REVIEW-230 | ASYNC-SYNC-TEST-CALL-MATCH 同步/异步方法测试调用匹配 | v4.49.1 | 37. 测试质量与同步性 | config.yaml: test_quality_protection.async_sync_test_match |
| B-REVIEW-231 | PROPERTY-RENAME-SERIALIZE-FIELD-SEP 属性名重构与序列化字段名分离 | v4.49.1 | 37. 测试质量与同步性 | config.yaml: test_quality_protection.property_rename_serialize |
| B-REVIEW-232 | FASTAPI-ENDPOINT-SIGNATURE-TEST-SYNC FastAPI 端点签名变更测试同步 | v4.49.1 | 37. 测试质量与同步性 | config.yaml: test_quality_protection.fastapi_endpoint_test_sync |
| B-REVIEW-233 | SOFT-DELETE-CATEGORY-ISOLATION 软删除数据分类隔离 | v4.49.1 | 37. 测试质量与同步性 | config.yaml: soft_delete_data_isolation |
| B-REVIEW-234 | ES-RESILIENCE-PRECHECK ES 弹性预检（扫描前检查） | v4.49.1 | 37. 测试质量与同步性 | config.yaml: es_resilience_precheck |
| B-REVIEW-235 | PYTEST-TIMEOUT-CONFIG 测试超时配置 | v4.49.1 | 37. 测试质量与同步性 | config.yaml: test_quality_protection.pytest_timeout_config |
| B-REVIEW-236 | MULTI-USER-ID-PROPAGATION 多用户隔离 user_id 透传一致性 | v4.49.1 | 37. 测试质量与同步性 | config.yaml: multi_user_id_propagation |
| B-REVIEW-237 | API-RESPONSE-FIELD-UI-ALIGNMENT 接口返回字段与 UI 操作集合对齐（meta-rule #83 后端侧） | v4.50.0 | 38. 接口契约与前端 UI 对齐 | config.yaml: api_response_field_ui_alignment |
| B-REVIEW-238 | PROPAGATION-INTEGRITY 跨层数据透传完整性（meta-rule #83 落地） | v4.50.0 | 39. 数据透传与职责分离 | config.yaml: data_propagation.propagation_integrity |
| B-REVIEW-239 | SNAPSHOT-LATEST-SEPARATION 快照与最新值职责分离 | v4.50.0 | 39. 数据透传与职责分离 | config.yaml: data_propagation.snapshot_latest_separation |
| B-REVIEW-240 | FALLBACK-DATA-MERGE Fallback 路径数据合并完整性 | v4.50.0 | 39. 数据透传与职责分离 | config.yaml: data_propagation.fallback_data_merge |
| B-REVIEW-241 | MULTIUSER-WRITE-CONSISTENCY 多用户隔离写入一致性 | v4.50.0 | 39. 数据透传与职责分离 | config.yaml: data_propagation.multiuser_write_consistency |
| B-REVIEW-242 | COOKIE-TOKEN-CONSISTENCY Cookie-Token 一致性审查（meta-rule #84 落地，token 重置独立于 Cookie 补注入） | v4.51.0 | 40. Cookie-Token 一致性 | config.yaml: cookie_token_consistency.consistency_check |
| B-REVIEW-243 | RENEWAL-LOOP-COMPLETENESS 续期闭环完整性审查（续期后必须回写 CookieStore JSON + SQLite） | v4.51.0 | 40. Cookie-Token 一致性 | config.yaml: cookie_token_consistency.renewal_loop |
| B-REVIEW-244 | LOGURU-PLACEHOLDER 日志占位符格式审查（loguru 用 {} 禁止 %s） | v4.51.0 | 41. 日志规范 | config.yaml: cookie_token_consistency.loguru_placeholder |
| B-REVIEW-245 | SILENT-EXCEPTION-BAN 静默异常禁止审查（禁止 except: pass，关键路径必须 logger.exception） | v4.51.0 | 41. 日志规范 | config.yaml: cookie_token_consistency.silent_exception_ban |
| B-REVIEW-281 | CONFIG-REFACTOR-5STEP 配置化重构 5 步法（grep 引用点 → Config 字段 → YAML 块 → _get_xxx() 函数 → 强制核对） | v4.61.0 | 42. 重构安全性 | config.yaml: refactoring_safety.refactor_5step |
| B-REVIEW-282 | SCOPE-CONTRACT-CHECK 作用域契约校验（模块级函数禁用 self/cls，静态方法禁用 self/cls） | v4.61.0 | 42. 重构安全性 | config.yaml: refactoring_safety.scope_contract |
| B-REVIEW-283 | IMPORT-NAME-CHECKLIST 导入名称变更 checklist（删除/改名前必须 grep 所有 from-import 引用点） | v4.61.0 | 42. 重构安全性 | config.yaml: refactoring_safety.import_name_change |
| B-REVIEW-284 | POWERSHELL-LONG-TASK-OUTPUT PowerShell 长任务日志输出（禁用 sink cmdlet，改用文件重定向） | v4.61.0 | 42. 重构安全性 | config.yaml: refactoring_safety.long_task_output |
| B-REVIEW-285 | RESOURCE-OVERLOAD-TOLERANCE 系统资源过载容错（CPU/内存阈值预检 + 超时降级策略） | v4.61.0 | 42. 重构安全性 | config.yaml: refactoring_safety.resource_overload_tolerance |
| B-REVIEW-286 | SONARQUBE-PIPELINE-CLOSED-LOOP SonarQube 15 阶段闭环（每阶段有失败处理，不能 exit 1 终止链路） | v4.61.0 | 42. 重构安全性 | config.yaml: refactoring_safety.sonarqube_pipeline |
| B-REVIEW-287 | RESILIENCE-RECOVERY 弹性恢复机制（ES read-only 自愈/CE 轮询/NOSONAR 校验/TRAE 旁路/锁清理） | v4.61.0 | 42. 重构安全性 | config.yaml: refactoring_safety.resilience_recovery |
| B-REVIEW-288 | TEST-VERIFY-TIERS 测试验证三档（Tier 1 完整测试集 / Tier 2 直接 import / Tier 3 改动文件验证） | v4.61.0 | 42. 重构安全性 | config.yaml: refactoring_safety.test_verify_tiers |
| B-REVIEW-289 | CROSS-FILE-REFERENCE-SYNC 跨文件引用同步校验（重构后必须启动服务/运行测试捕获 ImportError/NameError） | v4.61.0 | 42. 重构安全性 | config.yaml: refactoring_safety.cross_file_sync |
| B-REVIEW-290 | CONFIG-ACCESS-UNIFIED-ENTRY 配置访问统一入口（业务参数必须从 config.yaml 读取，禁止模块级硬编码常量） | v4.61.0 | 42. 重构安全性 | config.yaml: refactoring_safety.config_access_unified |
| B-REVIEW-291 | LLM-AUX-CALL-BUDGET 附加调用预算与用量闭环（附加 LLM 调用前必须 check_budget，调用后必须 _record_llm_usage，共享主调用 BudgetContext） | v4.62.0 | 45. LLM 多调用治理 | config.yaml: llm_call_governance.aux_call_budget |
| B-REVIEW-292 | LLM-AUX-CALL-TIMEOUT 附加调用独立超时（asyncio.wait_for 设置独立超时 < 主调用超时，超时降级返回空） | v4.62.0 | 45. LLM 多调用治理 | config.yaml: llm_call_governance.aux_call_timeout |
| B-REVIEW-293 | LLM-RESPONSE-STRUCTURED-PARSE 响应结构化解析（禁止 re 提取 JSON，必须 json.loads + 类型校验 + 代码块剥离） | v4.62.0 | 45. LLM 多调用治理 | config.yaml: llm_call_governance.response_parse |
| B-REVIEW-294 | LLM-MULTI-CALL-CONSISTENCY 多调用一致性（异常处理/日志格式/降级策略与主调用一致，附加异常不冒泡） | v4.62.0 | 45. LLM 多调用治理 | config.yaml: llm_call_governance.multi_call_consistency |
| B-REVIEW-295 | SESSION-CACHE-INVALIDATION-ON-ISSUE 签发新 token 时清除旧 token 缓存（issue_session 撤销旧 session 时同步清除 _verify_cache，否则旧 token 在 TTL 内仍命中绕过会话固定防护） | v4.63.0 | 19. 安全 / 20. 多用户隔离 | config.yaml: mu_audit_2026_07.session_cache_invalidation |
| B-REVIEW-296 | STATUS-CHANGE-CACHE-CLEAR 状态变更时清除缓存（与 B-REVIEW-295 配合，覆盖 disabled 状态清缓存；active 恢复不需清缓存） | v4.63.0 | 19. 安全 / 20. 多用户隔离 | config.yaml: mu_audit_2026_07.status_change_cache |
| B-REVIEW-297 | TMP-FILE-UNIQUE-NAME 并发写入时 tmp 文件名必须唯一（pattern 含 pid+thread_id，禁止固定 .tmp 后缀，避免并发 _write_json 竞争） | v4.63.0 | 4. 异步并发 / 19. 安全 | config.yaml: mu_audit_2026_07.tmp_file_naming |
| B-REVIEW-298 | CACHE-READ-DOUBLE-CHECK 读文件后重新检查缓存（_read_json 读完文件后写缓存前重新检查，避免两段式锁导致旧数据覆盖新缓存） | v4.63.0 | 4. 异步并发 / 19. 安全 | config.yaml: mu_audit_2026_07.cache_read_double_check |
| B-REVIEW-299 | LOCK-OUTSIDE-IO 持锁调用 IO 操作阻塞其他操作（merge_cookies 的 _sync_to_sqlite 应移到 with self._lock 之外，锁内只允许 cache/json 读写） | v4.63.0 | 4. 异步并发 | config.yaml: mu_audit_2026_07.lock_outside_io |
| B-REVIEW-300 | LOG-NO-SENSITIVE-VALUE 日志不应记录敏感信息（Cookie value/token/session_token/密码禁明文，只记录 len 或 hash 前 8 位） | v4.63.0 | 8. 错误处理 / 9. 日志规范 | config.yaml: mu_audit_2026_07.log_sensitive_value |
| B-REVIEW-301 | IDOR-TRIPLE-DEFENSE 越权防护三道防线（路由层 _check_task_ownership + ORM user_id 过滤 + Repo 层 user_id 参数，三道必须同时存在） | v4.63.0 | 19. 安全 / 20. 多用户隔离 | config.yaml: mu_audit_2026_07.idor_triple_defense |
| B-REVIEW-302 | SEARCH-USERID-PROPAGATION 搜索服务必须传递 user_id（SearchParams 必含 user_id；_execute 调 repo.search 必传；路由层从 request.state.user_id 注入） | v4.63.0 | 20. 多用户隔离 | config.yaml: mu_audit_2026_07.search_userid_propagation |
| B-REVIEW-303 | BATCH-UPSERT-USERID-FIELD 批量插入必须包含 user_id（sqlite_insert().values() 显式包含 user_id，on_conflict 不更新 user_id 避免归属权覆盖） | v4.63.0 | 20. 多用户隔离 / 5. 数据库规约 | config.yaml: mu_audit_2026_07.batch_upsert_userid |
| B-REVIEW-304 | INSERT-OR-REPLACE-SEMANTICS SQLite REPLACE 语义陷阱（INSERT OR REPLACE 在 UNIQUE 冲突时先删除整行再插入丢失未指定字段，应改用 ON CONFLICT DO UPDATE） | v4.63.0 | 5. 数据库规约 | config.yaml: mu_audit_2026_07.insert_or_replace_semantics |
| B-REVIEW-305 | DELETE-ENDPOINT-COMPLETENESS API 契约要求 DELETE 端点（契约定义了 GET/PUT/DELETE 时 DELETE 必须实现，支持按 key/path 参数删除单个资源） | v4.63.0 | 19. 安全 / 1. 分层架构 | config.yaml: mu_audit_2026_07.delete_endpoint_completeness |
| B-REVIEW-306 | BODY-SIZE-LIMIT-DOS API body 必须有大小限制（dict max_keys=100 / value max_value_size=64KB / list max_length=100，超限返回 400） | v4.63.0 | 19. 安全 | config.yaml: mu_audit_2026_07.body_size_limit |
| B-REVIEW-307 | YAML-TYPE-VALIDATION 加载 YAML 时校验字段类型（禁止 list(data.get(...)) 强转字符串，必须 isinstance 校验后再赋值，失败返回空列表） | v4.63.0 | 7. 配置管理 | config.yaml: mu_audit_2026_07.yaml_type_validation |
| B-REVIEW-308 | ENGINE-PROPERTY-ENCAPSULATION 不应直接访问 _engine（禁止外部模块访问 user_manager._engine，应通过 UserManager.engine 只读 property 暴露） | v4.63.0 | 1. 分层架构 / 6. 性能 | config.yaml: mu_audit_2026_07.engine_encapsulation |
| B-REVIEW-309 | DATETIME-FORMAT-CONSISTENCY datetime 格式一致性（raw SQL 和 ORM default 必须用相同格式，禁止 raw SQL 用 isoformat 字符串而 ORM 用 datetime 对象） | v4.63.0 | 5. 数据库规约 / 7. 配置管理 | config.yaml: mu_audit_2026_07.datetime_format_consistency |
| B-REVIEW-310 | EXCEPTION-FLAG-RESET 异常时重置标志（try 块设置的标志如 multi_user_finalized=True 在 except 中必须重置，否则永久降级无法自愈） | v4.63.0 | 8. 错误处理 | config.yaml: mu_audit_2026_07.exception_flag_reset |
| B-REVIEW-311 | CACHE-FAILURE-LOGGING 缓存失效失败应记录日志（缓存失效 try/except 禁止静默 pass，必须记录 warning 含 user_id 和异常信息） | v4.63.0 | 8. 错误处理 / 9. 日志规范 | config.yaml: mu_audit_2026_07.cache_failure_logging |
| B-REVIEW-312 | USERID-DEFAULT-UNIFICATION user_id 默认值统一（所有 getattr(request.state, "user_id", ...) 兜底值必须统一为 "default"，禁止混用 None） | v4.63.0 | 20. 多用户隔离 | config.yaml: mu_audit_2026_07.userid_default_unification |
| B-REVIEW-313 | IDEMPOTENT-RESOURCE-CREATION 资源创建接口幂等性强检查（已存在时返回 ok:True + already_active，禁止 ok:False） | v4.64.0 | 37. 资源创建幂等性与前端状态闭环 | config.yaml: idempotent_resource_creation |
| B-REVIEW-314 | OPERATION-RESULT-CONTRACT OperationResult 响应结构契约（必填 ok，可选 already_active/error_code/detail 等） | v4.64.0 | 37. 资源创建幂等性与前端状态闭环 | config.yaml: operation_result_contract |
| B-REVIEW-315 | FRONTEND-STATE-REFRESH-CLOSED-LOOP 前端状态刷新闭环（后端响应字段变更必须同步前端 types.ts） | v4.64.0 | 37. 资源创建幂等性与前端状态闭环 | config.yaml: frontend_state_refresh_closed_loop |
| B-REVIEW-330 | TYPE-ANNOTATION-CONTRACT-ALIGNMENT 类型注解契约对齐（后端函数返回类型注解 ↔ Pydantic ResponseModel ↔ 前端 types.ts 三方对齐；返回复杂结构 list[dict]/list[TypedDict]/嵌套 BaseModel/dict[str, Any] 时强制；权威源优先级：Pydantic ResponseModel > 前端 types.ts > 后端函数注解；无 ResponseModel 时以前端 types.ts 反向校验；单元测试禁止仅断言长度，必须断言 isinstance+字段存在性+字段类型+至少一个字段值） | v4.67.0 experimental | 12. API 设计 / 30. 契约 | config.yaml: type_annotation_contract |
| B-REVIEW-331 | EVENT-BUS-STARTUP-DECOUPLING 事件驱动基础设施启动解耦（EventBus/MessageQueue 消费者循环必须与业务任务存在性解耦；消费者循环独立启动函数 + 先于业务调度器启动 + 后于业务调度器停止 + 幂等防护 + 异常隔离 + 运行时入口补启动；禁止消费者循环嵌套在业务调度器函数内部受业务条件阻断） | v4.68.0 experimental | 3. 异步并发 / 19. 调度器 | config.yaml: event_bus_startup_decoupling |
| B-REVIEW-332 | DUAL-DATASOURCE-FALLBACK：双数据源兜底复核 | v4.69.0 | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: dual_data_source_consistency |
| B-REVIEW-333 | CHECKER-SCOPE-ALIGNMENT：检查器与消费者判定标准对齐 | v4.69.0 | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: dual_data_source_consistency |
| B-REVIEW-334 | CHECKER-ASYNC-COMPATIBILITY：异步检查器接口兼容 | v4.69.0 | 14-19. 安全/性能/状态/日志/并发/测试 | config.yaml: dual_data_source_consistency |
| B-REVIEW-337 | SOURCE-FILE-ENCODING-INTEGRITY：源码文件编码完整性（后端源码本体中文→字面量? / GBK 误读乱码，与运行时 ENC 规范正交互补） | v4.70.0 | 28. 编码规范 | config.yaml: coding_standards.source_file_encoding_integrity |
| B-REVIEW-APSCHEDULER-INTERVAL-FIRST-RUN | APScheduler interval 触发器首次执行控制规范 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-ASYNC-TIMEOUT | 异步操作整体超时保护 | - | 3. 异步并发 | config.yaml: coding_standards.datetime |
| B-REVIEW-AUTH-MULTI-PATH-VALIDATION | 多种认证方式（管理令牌 + 用户会话）时，中间件是否按优先级链式校验（检测中间件单一 token 校验、无 `user_id` 注入、异常静默降级的违规模式）；... | - | 24. 认证授权 | config.yaml: coding_standards |
| B-REVIEW-BACKGROUND-TASK-MONITOR | 后台任务健康监控 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-BROWSER-FALLBACK-SYNC | 浏览器内存兜底同步模式 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION | 业务关键字常量集中管理 | - | 通用 | config.yaml: coding_standards.keywords |
| B-REVIEW-CACHE-INVALIDATION | 缓存失效传播完整性 | - | 22. 缓存 | config.yaml: coding_standards |
| B-REVIEW-CIRCUIT-BREAKER-RETRY | CIRCUIT-BREAKER-RETRY 熔断标志与重试协调检查（重试前必须重置熔断标志，否则重试被短路形成假重试；重试失败时熔断标志必须由业务逻辑而非手动设置） | v4.46.0 | 15. 自愈与可靠性 | config.yaml: cookie_self_healing.circuit_breaker_retry |
| B-REVIEW-CONCURRENT-CHECK-ACT | 并发 check-then-act 原子化 | - | 通用 | config.yaml: coding_standards.race |
| B-REVIEW-CONCURRENT-STATE-LOCK | 并发共享状态锁保护 | - | 16. 状态管理 | config.yaml: coding_standards.state_sync / circuit_breaker |
| B-REVIEW-CONFIG-DRIVEN-TOGGLE | 配置驱动功能开关模式 | - | 6. 配置驱动 | config.yaml: coding_standards |
| B-REVIEW-CONFIG-LINKAGE | 配置全链路生效验证 | - | 6. 配置驱动 | config.yaml: coding_standards |
| B-REVIEW-CONFIG-VALIDATION | 配置项边界值校验 | - | 6. 配置驱动 | config.yaml: coding_standards |
| B-REVIEW-COOKIE-CHECK | Cookie 检查全面性 | - | 通用 | config.yaml: coding_standards.cookie / parser |
| B-REVIEW-COUNTER-DB-MAX-INIT | 业务自增计数器 DB MAX 初始化规范 | - | 11. 数据库/ORM | config.yaml: coding_standards |
| B-REVIEW-CREDENTIAL-SYNC-BRIDGE | 凭据同步桥接规范（yaml→keyring） | - | 通用 | config.yaml: coding_standards.credential_stores |
| B-REVIEW-CRITICAL-PATH-NO-SWALLOW | 关键路径异常可见性 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-CROSS-COMPONENT-STATE | 跨组件状态同步 | - | 16. 状态管理 | config.yaml: coding_standards.state_sync / circuit_breaker |
| B-REVIEW-CROSS-FIELD | 跨字段一致性校验 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-DATA-COMPLETENESS-PRECHECK | 数据完整性预检（pre-call completeness check） | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-DATA-FLOW-TRACE | 字段为空 5 点追踪 | - | 通用 | config.yaml: coding_standards.race |
| B-REVIEW-DEAD-CODE-CLEANUP | 死代码检测与清理 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-DEBUG-CODE-CLEANUP | 临时 DEBUG 代码清理 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-DIAGNOSTIC-LOGGING | DIAGNOSTIC-LOGGING 诊断日志完整性检查（自愈均失败时必须记录关键状态变量：存在性/过期时间/值一致性；日志含状态摘要；诊断变量列表配置化） | v4.46.0 | 15. 自愈与可靠性 | config.yaml: cookie_self_healing.diagnostic_logging |
| B-REVIEW-DIVZERO-FALLBACK | 除零兜底禁止凑数 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-DOM-FALLBACK-CHAIN | DOM 多层兜底链模式 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-DUAL-LINK-CONSISTENCY | 双链路前置条件一致性 | - | 26. 双链路一致性 | config.yaml: coding_standards |
| B-REVIEW-EDIT-VERIFY | 修改生效验证（针对 AI 辅助开发） | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-EDIT-VERIFY-DEPLOY-LOOP | 修改-验证-部署闭环（edit-verify-deploy closed loop） | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-ENCRYPTION-DEGRADATION | 加密升级退化策略模式 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-ERROR-HINT-ROUTABLE | 错误提示端点可操作性 | - | 13. 错误处理 | config.yaml: coding_standards.error_attribution |
| B-REVIEW-ERROR-MESSAGE-CONSTANT | 错误文案/日志降级 marker/用户提示信息是否提取为模块级常量（`_ERROR_MSG_ | - | 13. 错误处理 | config.yaml: coding_standards.error_attribution |
| B-REVIEW-ERROR-SEMANTICS | 错误提示语义准确性 | - | 13. 错误处理 | config.yaml: coding_standards.error_attribution |
| B-REVIEW-EVENT-TYPE-EXACT-MATCH | 事件类型过滤精确匹配 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-EXCLUDE-UNSET-CHECK | PATCH/PUT 接口是否用 `model_dump(exclude_unset=True)` 区分未传/传null/传值三态（检测 `for k, v in... | - | 通用 | config.yaml: coding_standards.param_chain |
| B-REVIEW-EXTERNAL-TEXT-PATTERN-CENTRALIZE | 外部系统文本特征集中管理 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-FAILURE-DUMP | 失败诊断 dump 机制 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-FAILURE-REASON-PROPAGATION | 失败原因是否分三层传递（底层 `last_ | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-FALLBACK-CHAIN | 降级链模式 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-FAST-DEGRADATION | 快速模式降级重试 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-FIELD-NAME-CASE-SENSITIVE | 前后端字段名大小写敏感检查 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-FIELD-NORMALIZE-DOC | 字段归一化文档化 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-FILE-LOCK-BYPASS | 文件锁绕过模式（SQLite immutable） | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-FILTER-SCENARIO | 过滤逻辑场景区分 | - | 通用 | config.yaml: coding_standards.query_filter |
| B-REVIEW-FILTER-VISIBILITY | 过滤结果可见性（后端侧） | - | 通用 | config.yaml: coding_standards.query_filter |
| B-REVIEW-INACTIVE-STATE-PRESERVE | 状态条件区分"从未初始化"与"主动失效" | - | 16. 状态管理 | config.yaml: coding_standards.state_sync / circuit_breaker |
| B-REVIEW-LLM-CAPABILITY-DISPATCH | 能力驱动派发（capability-driven dispatch） | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-LLM-DEFENSIVE-PARSING | LLM 响应防御性三层级解析 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-LOG-DOWNGRADE-STABILITY | 日志降级判断稳定性 | - | 17. 日志规范 | config.yaml: coding_standards.log_noise |
| B-REVIEW-LOGURU-PLACEHOLDER | 日志库占位符一致性 | - | 17. 日志规范 | config.yaml: coding_standards.log_noise |
| B-REVIEW-MERGE-VS-OVERWRITE-WRITE | 持久化层写入策略是否匹配数据来源（部分集→合并写 `merge_ | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-MIGRATION-BLOCK-ISOLATION | 迁移块独立容错 | - | 23. 迁移 | config.yaml: coding_standards.migration |
| B-REVIEW-MIGRATION-FAILURE-HANDLING | DB 迁移失败处理 | - | 11. 数据库/ORM | config.yaml: coding_standards.migration |
| B-REVIEW-MIGRATION-TRANSACTION | SQLite `_migrate_ | - | 23. 迁移 | config.yaml: coding_standards.migration |
| B-REVIEW-MULTI-LEVEL-HEALING | MULTI-LEVEL-HEALING 多级自愈完整性检查（多个独立恢复手段时必须分级自愈：低成本→中成本→放弃；每级重试前重置熔断标志；每级失败记录诊断日志；自愈级别配置化） | v4.46.0 | 15. 自愈与可靠性 | config.yaml: cookie_self_healing.multi_level_healing |
| B-REVIEW-MULTI-PATH-DATA-SOURCE | 同 API 多查询数据源一致性 | - | 12. API 设计 | config.yaml: coding_standards |
| B-REVIEW-MULTI-PROFILE-DISCOVERY | 多配置文件发现模式 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-MULTI-USER-RESOURCE-ISOLATION | 单用户系统升级到多用户时，全局单例资源是否按 `user_id` 维度隔离（检测 `cookies.json` 单例路径、`_cache: dict` 全局缓存... | - | 9. 资源管理 | config.yaml: coding_standards |
| B-REVIEW-MULTI-WRITE-ENTRY | 多源状态同步统一入口 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-NO-CROSS-THREAD-ASYNC | 跨线程异步调用禁用 | - | 3. 异步并发 | config.yaml: coding_standards |
| B-REVIEW-NO-HARDCODED-PROPS | 硬编码属性禁用 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-NO-HARDCODED-THRESHOLD | 硬编码阈值禁用 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-NOT-NULL-NONE-DEFENSE | NOT NULL 字段传 null 时是否防御性 pop 而非直接写入 DB 触发 IntegrityError（检测 `model_dump(exclude_... | - | 11. 数据库/ORM | config.yaml: coding_standards.null_defense |
| B-REVIEW-NUMERIC-EXTRACTION | 文本数值提取模式 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-PARAM-PASS-THROUGH | 参数透传链路完整性 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK | 第三方插件依赖预检模式 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-POST-WRITE-HOOK | 写后钩子（Post-Write Hook）规范 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-PRE-CHECK-BATCH | PRE-CHECK-BATCH 批量操作预检检查（批量操作前预检关键依赖；关键操作后健康探测；预检失败仅告警不阻断；预检参数配置化） | v4.46.0 | 15. 自愈与可靠性 | config.yaml: cookie_self_healing.pre_check_batch |
| B-REVIEW-PRECHECK-AND-PARALLEL | 凭证前置校验与并行采集 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-PYDANTIC-FIELD-DECLARE | Pydantic 模型字段完整性规范 | - | 通用 | config.yaml: coding_standards.param_chain |
| B-REVIEW-PYTEST-MODULE-REIMPORT | pytest 模块重复 import 隔离 | - | 5. 导入与依赖 | config.yaml: coding_standards |
| B-REVIEW-PYTHON-MODERN-ASYNCIO | Python 现代化 asyncio 用法 | - | 3. 异步并发 | config.yaml: coding_standards |
| B-REVIEW-REDACT-SCENARIO | 脱敏策略场景区分规范 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-RESOURCE-CLEANUP-HOOK | 资源生命周期 cleanup 钩子完整性 | - | 9. 资源管理 | config.yaml: coding_standards |
| B-REVIEW-REUSE-PATTERN | 复用既有模式原则 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-ROUTE-BLOCK-TYPES | 浏览器自动化资源拦截粒度 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-SCHEDULER-DB-SYNC | 调度器状态与 DB 同步 | - | 11. 数据库/ORM | config.yaml: coding_standards |
| B-REVIEW-SCHEDULER-ISOLATION | 独立调度器隔离模式 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-SCHEDULER-STARTUP-VISIBILITY | 关键调度器启动状态可见性 | - | 通用 | config.yaml: coding_standards.startup / mock |
| B-REVIEW-SELECTOR-REPOSITORY-SYNC | 选择器仓库同步与单一数据源 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-SERVICE-RESTART-VERIFICATION | 服务重启验证清单 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-SESSION-SIGNAL | 重试失败后状态信号必须传递 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-SESSION-TOKEN-SECURITY | 会话 token 的生成、存储、校验、撤销是否遵循安全最佳实践（检测 token 明文存库、用 `==` 比较、无滑动续期、撤销不清缓存的违规模式）；是否用 `... | - | 14. 安全 | config.yaml: coding_standards |
| B-REVIEW-SHARED-SINGLETON-POLLUTION | 循环中创建任务级覆盖对象是否用局部变量 `worker_xxx`（检测 `container.config = new_config` 直接修改 contain... | - | 6. 配置驱动 | config.yaml: coding_standards |
| B-REVIEW-SHARED-UTIL-CENTRALIZATION | 共享工具函数规范（避免散落内联判断） | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-SIGNAL-LAYER-MAPPING | 层依赖关系信号匹配 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-SILENT-DOWNGRADE-PRECHECK | 静默降级预检（不支持能力 → 友好降级） | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-SNAPSHOT-REALTIME-OVERWRITE | 历史快照与实时采集数据合并时是否按字段类型分档覆盖（检测 `_enrich_ | - | 通用 | config.yaml: coding_standards.datetime |
| B-REVIEW-STARTUP-HOOK-COMPLETENESS | 启动钩子完整性检查规范 | - | 通用 | config.yaml: coding_standards.startup / mock |
| B-REVIEW-STATE-DETECTION-BOOTSTRAP | 状态判定需区分"未检测"与"已检测未失效" | - | 16. 状态管理 | config.yaml: coding_standards.state_sync / circuit_breaker |
| B-REVIEW-STATE-FLAG-PRECHECK | 状态标志前置检查完整性 | - | 16. 状态管理 | config.yaml: coding_standards.state_sync / circuit_breaker |
| B-REVIEW-STATE-MACHINE-WHITELIST | 状态机白名单转换 | - | 16. 状态管理 | config.yaml: coding_standards.state_sync / circuit_breaker |
| B-REVIEW-STATISTICAL-INPUT-BOUNDARY | 统计聚合输入边界校准 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-STATS-EXCLUSIVE | 统计接口返回的分类计数是否互斥（`total = sum(各分类计数)`，如 `api_evaluations.py` 的 dist 统计中 insuffici... | - | 12. API 设计 | config.yaml: coding_standards |
| B-REVIEW-STATUS-CODE-SEMANTICS | 状态码语义精细化 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-TASK-HISTORY-THREE-LAYER-PROTECTION | 任务历史持久化三层状态保护规范 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-TEST-FIXTURE-ISOLATION | 测试 fixture 生产隔离与数据污染应急 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-TEST-MOCK-SYNC | 测试 mock 同步（test mock synchronization） | - | 通用 | config.yaml: coding_standards.startup / mock |
| B-REVIEW-TIMING-INSTRUMENTATION | 关键路径计时埋点 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-TRY-FINALLY-INIT | try/finally 变量初始化 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-UPDATE-VS-UPSERT | Update vs Upsert 语义区分 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-USER-IDENTITY-PRIORITY | 用户身份识别是否有明确优先级链且配置化管理（检测硬编码身份识别逻辑、无优先级链、无降级策略的违规模式）；是否实现优先级链（`unb` > `cookie2` 哈... | - | 通用 | config.yaml: user_identity_priority.priority_chain |
| B-REVIEW-VERSION-SOURCE-SINGLE | 元数据源单源管理规范 | - | 通用 | config.yaml: coding_standards |
| B-REVIEW-WINDOWS-TERMINAL-ENCODING | Windows 终端编码与 Shell 语法兼容 | - | 28. 编码规范 | config.yaml: coding_standards.encoding |
| B-REVIEW-WINDOWS-TEST-MOCK | Windows 测试环境 Mock 模式 | - | 通用 | config.yaml: coding_standards.startup / mock |

---

## 按版本分组（参考 `references/version-changelog.md`）

| 版本 | 范围 | 数量 | 引入来源 |
|------|------|------|----------|
| v4.68.0 experimental | B-REVIEW-331 | 1 | 第十一轮复盘：事件驱动基础设施启动解耦（meta-rule #111 + step 274 落地 experimental），覆盖 EventBus 启动耦合导致钉钉通知失效 Bug 修复经验 |
| v4.67.0 experimental | B-REVIEW-330 | 1 | 第十轮复盘：类型注解契约对齐（meta-rule #110 + step 273 落地 experimental），覆盖图片哈希 undefined Bug 修复经验 |
| v4.65.0 | B-REVIEW-316~326 | 11 | 第九轮复盘：架构层依赖强化（沉淀自 _skill_optim/architecture-rule.md）+ SQLAlchemy 写路径并发保护（沉淀自 _skill_optim/sqlalchemy-rule.md）+ 搜索服务模板方法模式（coding-standards v1.3 §2.27 + 规范 19 升级） |
| v4.63.0 | B-REVIEW-295~312 | 18 | 多用户安全与并发审计（2026-07-25 MU1-MU6 全量走查复盘，config.yaml#mu_audit_2026_07） |
| v4.61.0 | B-REVIEW-281~290 | 10 | 复盘规范集后端落地（配置化重构 5 步法/作用域契约/导入名称 checklist/PowerShell 长任务/资源过载容错/SonarQube 闭环/弹性恢复/测试三档/跨文件同步/配置统一入口） |
| v4.51.0 | B-REVIEW-242~245 | 4 | meta-rule #84 Cookie-Token 状态分离与一致性保障（Cookie-Token 一致性/续期闭环完整性/日志占位符/静默异常禁止） |
| v4.50.0 | B-REVIEW-237~241 | 5 | meta-rule #83 后端侧：接口返回字段与 UI 操作集合对齐 + 数据透传与职责分离（PROPAGATION/SNAPSHOT/FALLBACK/MULTIUSER） |
| v4.49.1 | B-REVIEW-229~236 | 8 | 测试质量与同步性（monkeypatch 覆盖/async-sync 调用匹配/属性重构与序列化分离/端点签名同步/软删除隔离/ES 弹性预检/pytest 超时/多用户 user_id 透传） |
| v4.46.0 | B-REVIEW-MULTI-LEVEL-HEALING / B-REVIEW-CIRCUIT-BREAKER-RETRY / B-REVIEW-DIAGNOSTIC-LOGGING / B-REVIEW-PRE-CHECK-BATCH | 4 | Cookie 自愈机制修复（多级自愈/熔断重试协调/诊断日志/批量预检） |
| v4.40.0 | B-REVIEW-189 | 1 | meta-rule #66 业务异常状态码冲突 |
| v4.38.0 | B-REVIEW-182~188 | 7 | meta-rules #57-#63 异步/资源池/HTTP/CSS/异常日志/外部资源/DB身份 |
| v4.37.0 | B-REVIEW-178~181 | 4 | meta-rules #48-#51 调度器运行时治理 |
| v4.35.0 | B-REVIEW-173~177 | 5 | meta-rules #43-#47 跨层契约与测试同步 |
| v4.34.0 | B-REVIEW-164~168 | 5 | meta-rules #38-42 列表聚合与状态联动 |
| v4.33.0 | B-REVIEW-162~163 | 2 | meta-rule #36 规范沉淀门槛 |
| v4.31.0 | B-REVIEW-159~161 | 3 | meta-rules #33-35 注册式 endpoint/根因扫描/字段契约 |
| v4.30.0 | B-REVIEW-157~158 | 2 | meta-rules #31-32 状态恢复前置校验/降级链日志合并 |
| v4.29.0 | B-REVIEW-151~156 | 6 | meta-rules #25-30 数据契约与时序 |
| v4.28.0 | B-REVIEW-121~150 | 30 | 全量复盘 80+ topics，4 阶段流水线 |
| v4.27.0 | B-REVIEW-NAME（6 项）| 6 | meta-rule #24 工程闭环元规范 |
| v4.25.0 | B-REVIEW-110~112 | 3 | EXCLUDE-UNSET/NOT-NULL/SHARED-SINGLETON |
| v4.23.0 | B-REVIEW-NAME（4 项）| 4 | LLM 能力派发/共享工具/静默降级/失败原因 |
| v4.22.0 | B-REVIEW-NAME（4 项）| 4 | 启动钩子/任务历史/计数器/APScheduler |
| v4.21.0 | B-REVIEW-NAME（3 项）| 3 | Pydantic 字段/凭据同步/脱敏场景 |
| v4.20.0 | 1 项 | 1 | 版本源管理 |
| v4.19.0 | B-REVIEW-NAME（3 项）| 3 | 调度器启动/选择器同步/外部文本 |
| v4.16.0 | B-REVIEW-NAME（2 项）| 2 | 字段归一化/除零兜底 |
| v4.14.0 | B-REVIEW-NAME（3 项）| 3 | 资源拦截/信号层/DEBUG 清理 |
| v4.13.0 | 1 项 | 1 | 统计分类互斥性 |
| v4.12.0 | B-REVIEW-NAME（4 项）| 4 | DOM 兜底链/失败 dump/计时埋点/前置校验 |
| v4.11.0 | B-REVIEW-NAME（5 项）| 5 | 状态码语义/调度器同步/后台任务监控/数值提取/配置校验 |
| v4.10.0 | B-REVIEW-NAME（3 项）| 3 | 日志占位符/过滤可见性/pytest 隔离 |
| v4.9.0 | B-REVIEW-NAME（4 项）| 4 | 资源清理/并发锁/状态机白名单/现代化 asyncio |
| v4.8.0 | B-REVIEW-NAME（3 项）| 3 | 状态标志/日志降级/修改验证 |
| v4.6.0 | B-REVIEW-NAME（3 项）| 3 | 异步超时/复用模式/字段追踪 |
| v4.5.0 | B-REVIEW-NAME（4 项）| 4 | Update/Upsert/多源同步/失效状态/浏览器兜底/死代码 |
| v4.4.0 | B-REVIEW-NAME（4 项）| 4 | 错误语义/无硬编码阈值/参数透传/快速降级/配置联动 |
| v4.3.0 | B-REVIEW-NAME（8 项）| 8 | 文件锁/加密退化/调度器隔离/降级链/Chrome 136/多 profile/Windows Mock/插件依赖 |
| v4.1.0 | B-REVIEW-NAME（2 项）| 2 | Cookie 检查/Session 信号 |
| v4.0.0 及之前 | 历史沉淀 | 数十项 | 分层架构/异步/数据库/错误处理/日志/性能/安全等基础规范 |

总计：约 207 项 B-REVIEW 检查点（v4.0.0 至今逐步沉淀）。

---

## 命名规则

- **B-REVIEW-NNN**（数字 ID）：v4.25.0 起编号体系，主要用于 v4.28+ 的全量复盘新增项（B-REVIEW-110~189）
- **B-REVIEW-NAME**（语义命名）：v4.0-v4.27 的命名体系（如 B-REVIEW-COOKIE-CHECK），描述性强但不便检索
- **混用现状**：两套体系并行使用，ID 段优先用于跨版本引用与 changelog 追踪，NAME 段保留历史阅读习惯
- **新增建议**：v4.40+ 统一用数字 ID，按当前最大号 +1 递增（如新增则用 B-REVIEW-291）
