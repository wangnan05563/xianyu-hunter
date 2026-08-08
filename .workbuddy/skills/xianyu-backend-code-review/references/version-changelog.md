## v4.69.0 (2026-07-26) - 双数据源一致性保障（experimental）

**类型**：experimental 版（Sequential Thinking 四维度复盘沉淀）
**触发来源**：2026-07-26 健康检查 cookie 显示无效但实时搜索正常，根因是双数据源不一致 + 检查器与消费者判定标准不对齐 + 异步检查器不兼容 + 回写异常静默吞掉。

**新增检查点**：
- B-REVIEW-332 双数据源兜底复核（DUAL-DATASOURCE-FALLBACK）
- B-REVIEW-333 检查器与消费者判定标准对齐（CHECKER-SCOPE-ALIGNMENT）
- B-REVIEW-334 异步检查器接口兼容（CHECKER-ASYNC-COMPATIBILITY）

**强化检查点**：
- B-REVIEW-152 关键路径异常保留完整 traceback → 补充异常可观测性分级（回写失败 warning / 查询失败 debug）

**配置驱动**：新增 `config.yaml: dual_data_source_consistency` 节点，包含 `enabled` / `fallbackToRuntime` / `syncBackOnUpdate` / `logLevelOnSyncFailure` / `checkerScopeAlignment` / `asyncCheckerCompatibility` 等子节点。

**关联规范**：[xianyu-hunter-dev/references/dual-data-source-consistency.md](../xianyu-hunter-dev/references/dual-data-source-consistency.md)
**关联复盘**：[xianyu-hunter-dev/references/retrospective-2026-07-26-r3.md](../xianyu-hunter-dev/references/retrospective-2026-07-26-r3.md)

**experimental 升正条件**：1 季度内（截至 2026-10-26）同类根因再发 ≥ 2 次

---

## v4.65.0 (2026-07-25) — 架构层依赖强化 + SQLAlchemy 写路径并发保护 + 搜索服务模板方法（第九轮复盘落地）

### 复盘背景

基于 2026-07-25 第九轮复盘（搜索接口标准化 + 事件触发时机 + 钉钉通知时机），将 `_skill_optim/architecture-rule.md`（4 条架构规则）+ `_skill_optim/sqlalchemy-rule.md`（4 条 SQLAlchemy 规则）+ 搜索服务模板方法模式（coding-standards v1.3 §2.27 + 规范 19 升级）三类高风险场景的审查要点沉淀为 11 个 B-REVIEW 检查点，分布在 3 个新维度：

| 失败案例 | 根因 | 对应检查点 |
|----------|------|------------|
| `EVAL_PASSED` 事件在 AI 评估前触发 | 事件触发时机错误，"已完成"语义事件前置触发 | 配套 `xianyu-hunter-dev` 规范 16 升级 |
| 4 个搜索接口重复实现分页/计数逻辑 | 缺少 SearchService 抽象基类 | B-REVIEW-324 SEARCH-SERVICE-TEMPLATE |
| 搜索接口无慢查询日志 | 缺少 `_maybe_log_slow` 钩子 | B-REVIEW-326 SEARCH-SLOW-QUERY-LOG |
| service 层绕过仓储直接查询 | 仓储抽象复用原则不明确 | B-REVIEW-319 REPOSITORY-ABSTRACTION-REUSE |
| 路由函数臃肿含业务逻辑 | 路由层业务剥离原则不明确 | B-REVIEW-318 BUSINESS-LOGIC-OUT-OF-CONTROLLER |
| 多写路径无并发保护 | 写路径并发保护选型缺失 | B-REVIEW-322 WRITE-PATH-CONCURRENCY-SAFEGUARD |

### 新增 B-REVIEW 检查点（11 项，3 个新维度）

#### 维度 38：架构层依赖强化（B-REVIEW-316~319，沉淀自 _skill_optim/architecture-rule.md）

- **B-REVIEW-316 LAYER-DEPENDENCY-DIRECTION**：层依赖方向铁律（error）。强化 references/architecture.md §2.2 规则表，新增 grep 检测信号。
- **B-REVIEW-317 LIBS-BUSINESS-AGNOSTIC**：公共工具库业务无关（error）。`infra/utils/` 等公共库禁止导入 `modules/web/services`，禁止依赖业务上下文。
- **B-REVIEW-318 BUSINESS-LOGIC-OUT-OF-CONTROLLER**：路由层业务逻辑剥离（error）。路由函数 ≤15 行，禁止 `session.execute/commit`，业务决策移到 service。
- **B-REVIEW-319 REPOSITORY-ABSTRACTION-REUSE**：仓储抽象复用（warning）。已存在仓储的表禁止 ad-hoc SQLAlchemy 查询，应扩展仓储。

#### 维度 39：SQLAlchemy 写路径并发保护（B-REVIEW-320~323，沉淀自 _skill_optim/sqlalchemy-rule.md）

- **B-REVIEW-320 SESSION-CONTEXT-MANAGER**：Session 上下文管理与显式事务控制（error）。`async with` + 显式 `commit/rollback`，事务内禁止网络 I/O。
- **B-REVIEW-321 TENANT-USERID-SCOPING**：多租户 user_id 隔离（error，通用版）。多用户表 `select/update/delete` 必须附加 `user_id` 条件，与 B-REVIEW-301/302 互补。
- **B-REVIEW-322 WRITE-PATH-CONCURRENCY-SAFEGUARD**：写路径并发保护选型（error）。乐观锁/Redis 分布式锁/SELECT FOR UPDATE 三选一，基于争用级别选型。
- **B-REVIEW-323 PREFER-ORM-EXPRESSION**：优先 SQLAlchemy 表达式（warning）。默认 ORM `select/update/delete`，原生 SQL 仅在明确技术约束下使用且必须参数化。

#### 维度 40：搜索服务模板方法模式（B-REVIEW-324~326，coding-standards v1.3 §2.27 + 规范 19 升级）

- **B-REVIEW-324 SEARCH-SERVICE-TEMPLATE**：搜索服务模板方法模式（error）。≥2 个搜索接口必须抽取 `SearchService` 基类，`search()` 为唯一入口编排 5 步流程。
- **B-REVIEW-325 SEARCH-HOOK-METHOD-CONTRACT**：搜索服务 4 钩子方法契约（error）。`_build_query`/`_execute`/`_extract_facets`/`_paginate` 签名与返回类型契约。
- **B-REVIEW-326 SEARCH-SLOW-QUERY-LOG**：搜索服务慢查询日志（warning）。`_maybe_log_slow` 在 `_execute` 后调用，阈值从 config 读取，日志含 `elapsed_ms`/`service_class`。

### 配套配置

- `config.yaml` 新增 3 个顶层节点：`architecture_layering` / `sqlalchemy_patterns` / `search_service_template`
- 所有参数（grep 模式、阈值、策略、表清单、钩子签名）通过 config.yaml 管理，无硬编码
- 与 `xianyu-hunter-dev/config/tech-stack.json#searchServiceTemplate` 对齐（基类文件、慢查询阈值）

### 跨技能联动

- 配套开发规范：`xianyu-hunter-dev` 规范 19（v4.64.0 升级为模板方法模式）+ 规范 16（事件触发时机，强化 PASSED 事件锚点）+ step 271/272（useSearch/useSearchHistory）
- 配套前端审查：`xianyu-frontend-code-review` F-REVIEW-236~240（useSearch/useSearchHistory 模式，待阶段 3 同步）
- 配套测试模式：`xianyu-auto-testing` 模式 AB/AC（搜索服务模板方法测试，待阶段 4 同步）
- 配套复盘报告：`xianyu-hunter-dev/references/retrospective-2026-07-25-r3.md` 第九轮复盘（I.1-I.7 结构）

### 详细描述

- 架构层依赖强化：详见 [references/architecture.md §13](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/architecture.md) v4.65.0 新增检查点速查
- SQLAlchemy 写路径并发保护：详见 [references/sqlalchemy.md §16](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/sqlalchemy.md) v4.65.0 新增检查点速查
- 搜索服务模板方法模式：详见 [SKILL.md §40](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/SKILL.md) 维度正文

### _skill_optim 规则文件沉淀清单

本次将 `_skill_optim/` 目录下 2 个规则文件全部沉淀为 B-REVIEW 检查点：

| 源文件 | 规则数 | 沉淀目标 | 状态 |
|---|---|---|---|
| `_skill_optim/architecture-rule.md` | 4 条 | B-REVIEW-316~319（维度 38） | 全部沉淀 ✅ |
| `_skill_optim/sqlalchemy-rule.md` | 4 条 | B-REVIEW-320~323（维度 39） | 全部沉淀 ✅ |

沉淀完成后，`_skill_optim/` 目录可作为归档保留（规则已全部转移到正式技能文件），后续不再作为活跃规则源。

---

## v4.64.0 (2026-07-25) — 资源创建幂等性与前端状态闭环（第八轮复盘落地）

### 复盘背景

基于 2026-07-25 第八轮复盘（反爬登录会话启动矛盾修复），将"资源创建接口幂等性"+"OperationResult 响应结构契约"+"前端状态刷新闭环"三类高风险场景的审查要点沉淀为 3 个 B-REVIEW 检查点。核心目标是"防止 UI 状态与后端响应不一致的矛盾现象"，所有审查要点来自反爬登录会话启动矛盾修复的真实失败案例：

| 失败案例 | 根因 | 对应检查点 |
|----------|------|------------|
| `/session/start` 会话已活跃时返回 `ok:False` 误报失败 | 资源创建接口缺幂等设计，用 `ok:False` 表达"已存在" | B-REVIEW-313 IDEMPOTENT-RESOURCE-CREATION |
| 后端响应字段不统一，缺少 `already_active`/`error_code` | 写操作响应缺统一 OperationResult 契约 | B-REVIEW-314 OPERATION-RESULT-CONTRACT |
| 后端新增 `already_active` 字段，前端 `OperationResult` 类型未同步声明 | 后端响应字段变更未驱动前端 types.ts 同步 | B-REVIEW-315 FRONTEND-STATE-REFRESH-CLOSED-LOOP |

### 新增 B-REVIEW 检查点

- **B-REVIEW-313 IDEMPOTENT-RESOURCE-CREATION**：资源创建接口幂等性强检查（critical，P0）。升级自维度 19 第 1842 行 🆕v4.0 幂等性设计描述性条目。
- **B-REVIEW-314 OPERATION-RESULT-CONTRACT**：OperationResult 响应结构契约（error）。必填 `ok`，可选 `already_active`/`already_exists`/`error_code`/`detail` 等。
- **B-REVIEW-315 FRONTEND-STATE-REFRESH-CLOSED-LOOP**：前端状态刷新闭环（后端侧，error）。后端响应字段变更必须同步前端 types.ts。

### 配套配置

- `config.yaml` 新增 3 个节点：`idempotent_resource_creation` / `operation_result_contract` / `frontend_state_refresh_closed_loop`
- 所有参数（路由模式、字段集、handler 模式、正则）通过 config.yaml 管理，无硬编码

### 跨技能联动

- 配套开发规范：`xianyu-hunter-dev` 规范 31（资源创建接口幂等性设计）+ 规范 32（前端 async handler 三分支完整性）
- 配套前端审查：`xianyu-frontend-code-review` F-REVIEW-233~235
- 配套测试模式：`xianyu-auto-testing` 模式 AA（幂等性与状态一致性回归测试）
- 配套复盘报告：`xianyu-hunter-dev/references/retrospective-2026-07-25-r2.md` 第八轮复盘（H.1-H.7 结构）

### 详细描述

详见 `references/idempotent-resource-creation-checks.md`。

---

## v4.61.0 (2026-07-23) — 重构安全性审查（复盘规范集后端落地）

### 复盘背景

基于新提炼的"复盘规范集"后端部分，将配置化重构、长任务执行、质量门禁、跨文件契约四类高风险场景的审查要点沉淀为 10 个 B-REVIEW 检查点。核心目标是"防止低级重构失误占用大量调试时间"，所有审查要点均来自真实失败案例：

| 失败案例 | 根因 | 对应检查点 |
|----------|------|------------|
| `container.py:450` `self.config.buyer` 应为 `cfg.buyer` | 模块级函数误用 self，5 步法步骤 5 未核对调用点作用域 | B-REVIEW-281 / 282 |
| `startup.py:161` `from xxx import TAKEOVER_TIMEOUT_MIN` 应为 `_get_takeover_timeout_min` | 常量改名后调用方未同步更新 import | B-REVIEW-281 / 283 / 289 |
| `_LIVE_CACHE_TTL = 60` 硬编码 | 业务参数散落模块级，调整需改代码 | B-REVIEW-290 |

### 新增检查点

| 检查点 ID | 名称 | 维度 | 核心规则 |
|-----------|------|------|----------|
| B-REVIEW-281 | CONFIG-REFACTOR-5STEP | 42. 重构安全性 | 配置化重构必须执行 5 步法（grep 引用点 → Config 字段 → YAML 块 → _get_xxx() 函数 → 强制核对） |
| B-REVIEW-282 | SCOPE-CONTRACT-CHECK | 42. 重构安全性 | 函数签名与变量访问必须匹配（模块级函数禁用 self/cls） |
| B-REVIEW-283 | IMPORT-NAME-CHECKLIST | 42. 重构安全性 | 导出符号删除/改名前必须 grep 所有 from-import 引用点 |
| B-REVIEW-284 | POWERSHELL-LONG-TASK-OUTPUT | 42. 重构安全性 | 长任务（>30 秒）禁用 sink cmdlet，改用文件重定向 |
| B-REVIEW-285 | RESOURCE-OVERLOAD-TOLERANCE | 42. 重构安全性 | 完整测试集超时降级为直接 import 测试或改动文件验证 |
| B-REVIEW-286 | SONARQUBE-PIPELINE-CLOSED-LOOP | 42. 重构安全性 | SonarQube 扫描 12 阶段闭环，每阶段有失败处理 |
| B-REVIEW-287 | RESILIENCE-RECOVERY | 42. 重构安全性 | ES read-only 自愈/CE 轮询/NOSONAR 校验/TRAE 旁路/锁清理 |
| B-REVIEW-288 | TEST-VERIFY-TIERS | 42. 重构安全性 | 测试验证三档（Tier 1 完整测试集 / Tier 2 直接 import / Tier 3 改动文件验证） |
| B-REVIEW-289 | CROSS-FILE-REFERENCE-SYNC | 42. 重构安全性 | 重构后必须启动服务/运行测试捕获 ImportError/NameError |
| B-REVIEW-290 | CONFIG-ACCESS-UNIFIED-ENTRY | 42. 重构安全性 | 业务参数必须从 config.yaml 读取，禁止模块级硬编码常量 |

### 配置节点

新增 `config.yaml#refactoring_safety` 节点，含 10 个子节点 + hard_constraints：

- `refactor_5step`：5 步法必需步骤与异常回退要求
- `scope_contract`：作用域契约规则（模块级函数/实例方法/类方法/静态方法）
- `import_name_change`：导入名称变更 checklist
- `long_task_output`：长任务阈值（30 秒）与禁用/推荐模式
- `resource_overload_tolerance`：CPU（90%）/内存（85%）阈值与降级策略
- `sonarqube_pipeline`：12 阶段闭环必需阶段列表
- `resilience_recovery`：5 类弹性恢复机制开关
- `test_verify_tiers`：三档阈值（Tier 1: 200 文件/300 秒，Tier 2: 50 文件）
- `cross_file_sync`：异常捕获清单（ImportError/NameError）
- `config_access_unified`：业务参数类型清单与历史失败案例

### 适用场景与不适用场景

| 检查点 | 适用场景 | 不适用场景 |
|--------|----------|------------|
| B-REVIEW-281~283 | 模块级硬编码常量改为 config.yaml 配置项 | 纯内部辅助常量（正则白名单）、测试 fixture |
| B-REVIEW-284~285 | 执行时长 > 30 秒的命令、CI 流水线 | 短命令（< 30 秒）、Linux/macOS 环境 |
| B-REVIEW-286~287 | 项目级 SonarQube 全量扫描、CI 质量门禁 | 单文件快速 lint、本地临时扫描 |
| B-REVIEW-288 | 审查流程验证阶段、CI 根据 PR 范围选择测试粒度 | 发布前最终验证（必须 Tier 1） |
| B-REVIEW-289~290 | 公共 API 重命名、配置化重构后核对 | 私有辅助函数改名、单文件内部重构 |

### 与现有检查点的关系

- B-REVIEW-281（5 步法）是流程级，B-REVIEW-NO-HARDCODED-THRESHOLD（阈值禁用）是结果级，B-REVIEW-CONFIG-LINKAGE（配置全链路生效）是应用级，三者互补
- B-REVIEW-284（PowerShell 长任务）与 B-REVIEW-WINDOWS-TERMINAL-ENCODING / B-REVIEW-POWERSHELL-EXPLICIT-SUFFIX 均针对 PowerShell 但维度不同
- B-REVIEW-286（SonarQube 闭环）的阶段 2（ES 预检）是 B-REVIEW-234 ES-RESILIENCE-PRECHECK 的细化
- B-REVIEW-288（测试三档）是流程级，B-REVIEW-235 PYTEST-TIMEOUT-CONFIG 是配置级
- B-REVIEW-289（跨文件同步）与 B-REVIEW-PARAM-PASS-THROUGH 均为"调用方同步"但粒度不同

### 关联文件变更

| 文件 | 变更类型 | 摘要 |
|------|----------|------|
| `references/refactoring-safety-checks.md` | 新增 | A/B/C/D 四类审查要点细化展开，含历史失败案例与配置节点速查 |
| `config.yaml` | 追加 | `refactoring_safety` 节点（10 子节点 + hard_constraints） |
| `references/checkpoints-index.md` | 追加 | B-REVIEW-281~290 索引条目 + v4.61.0 版本分组 + 统计数字 180→190 |
| `SKILL.md` | 更新 | 版本号 4.60.0→4.61.0 + 版本演进索引 + 配置驱动表 + 按需加载触发条件 + 阶段 3 专项检查步骤 9-13 + 阶段 4 结果呈现 10-12 + 审查判断标准表 5 条新条目 |
| `templates/report-template.md` | 追加 | v4.61.0 重构安全性审查报告模板（7 个子节） |

---

## v4.59.0 (2026-07-22) — SPA 白屏修复跨技能同步（后端无新增 B-REVIEW）

### 同步背景

2026-07-22 React SPA 间歇性白屏修复复盘，前端新增 6 个 F-REVIEW（214~219）和 xianyu-hunter-dev step 254-261 / meta-rule #95。本次为跨技能同步记录，后端无新增 B-REVIEW 检查点（白屏根因均为前端渲染容错缺失，不涉及后端代码变更）。

### 关联技能变更

| 技能 | 版本 | 变更摘要 |
|------|------|----------|
| xianyu-hunter-dev | v4.61.0 | 新增 step 254-261（frontend-ui.md 254-258 + testing.md 259-261）+ meta-rule #95 SPA-RENDER-RESILIENCE |
| xianyu-frontend-code-review | v4.59.0 | 新增 F-REVIEW-214~219（全局 ErrorBoundary / lazyRetry / 路由级 ErrorBoundary / API 防御性兜底 / Vitest 环境预检 / antd 中文按钮兼容）|
| xianyu-auto-testing | v1.9.0 | 新增模式 U（SPA 白屏回归测试）|
| xianyu-backend-code-review | v4.59.0 | **无新增 B-REVIEW**，仅同步记录 |

### 后端无需新增 B-REVIEW 的原因

白屏 5 类根因均为前端问题：
1. 缺少全局 ErrorBoundary — 前端 React 组件层
2. 懒加载 chunk 失效无重试 — 前端 Vite 构建层
3. 未保护的数据访问 — 前端 API 消费层（已由 F-REVIEW-217 覆盖）
4. 401 拦截器硬跳转中断渲染 — 前端 axios 拦截器层
5. 路由级错误无隔离 — 前端 React Router 层

后端 401 响应格式（`{"detail": "Unauthorized"}`）已在既有 B-REVIEW 中覆盖，无需新增。

### 配置节点

`config.yaml` 无变更。前端 `spa_white_screen_resilience` 节点由 xianyu-frontend-code-review 管理。

---

## v4.50.0 (2026-07-18) — 数据透传与职责分离规范

### 复盘背景

2026-07-18 卖家评估菜单修复三个同源 Bug，均为"信息传递断裂"问题：

| Bug | 断裂点 | 后果 |
|-----|--------|------|
| 评分 65 分 | worker 有 seller_profile 但未合并 detail 页字段 | 维度判定失败 → insufficient 模式 cap 65 |
| 商品消失 A | collection_service 三层调用未透传 user_id | 多用户隔离过滤隐藏事件 |
| 商品消失 B | enrich 用最新价格覆盖了过滤用的快照 | 旧 eval 事件被按新价格误判超范围 |

### 成功执行任务的完整步骤

1. **Phase 1 根因调查**：读取错误信息 → 复现路径分析 → 多组件证据收集（worker → collection_service → evaluator → repo_events → evaluations_list）→ 数据流追踪
2. **Phase 2 模式分析**：找到工作示例（collection_service._collect_official_full 已合并）→ 对比工作 vs 不工作 → 识别差异
3. **Phase 3 假设测试**：形成单一假设 → 6 个场景测试验证 _eval_snapshot_price 逻辑
4. **Phase 4 实施修复**：创建失败测试用例 → 实施单一修复（三处独立修复）→ 验证（py_compile + 模块导入 + 场景测试）

### 不确定性与失败点

| 不确定性/失败 | 应对策略 |
|--------------|----------|
| EventRow.user_id 列定义未确认 | 读取 db_models.py 确认 nullable + default="default" |
| seller_profile_fallback 是否已合并 detail 字段 | 读取 _detail.py 确认已合并（但 worker 未调用） |
| mypy 不可用 | 降级为 py_compile + 模块导入 + 场景测试 |

### 可抽象的固定流程与判断逻辑

1. **跨层数据透传完整性检查**：入口层接收的字段必须完整透传到最底层
2. **快照与最新值职责分离**：过滤用评估时快照，展示用最新值
3. **Fallback 路径数据合并完整性**：fallback 返回的数据必须合并所有可用来源
4. **多用户隔离字段一致性**：写入时必须显式传入 user_id，不依赖默认值

### 适用场景与不适用场景

| 流程 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 跨层透传 | 多层架构（domain→infra→modules→web） | 单层脚本 |
| 快照分离 | 采集-评估-展示链路 | 纯展示场景（无过滤） |
| fallback 完整性 | 有 fallback 机制的采集流程 | 稳定数据源（无 fallback） |
| 多用户隔离 | 多用户系统（user_id 隔离） | 单用户系统 |

### 新增检查点

| 检查点 ID | 名称 | 维度 | 核心规则 |
|-----------|------|------|----------|
| B-REVIEW-238 | DATA-PROPAGATION-INTEGRITY | 10 | 跨层调用链中的标识字段（user_id/task_id/request_id）必须完整透传到最底层 |
| B-REVIEW-239 | SNAPSHOT-VS-LATEST-SEPARATION | 10 | enrich 覆盖字段前必须保存快照，过滤函数优先用快照 |
| B-REVIEW-240 | FALLBACK-DATA-MERGE-COMPLETENESS | 10 | fallback 路径返回的数据必须合并所有可用来源，主源成功后也必须合并次源字段 |
| B-REVIEW-241 | MULTIUSER-ISOLATION-WRITE-CONSISTENCY | 10 | 数据库写入必须显式传入 user_id，不依赖默认值；DELETE 附加 user_id 过滤 |

### 配置节点

新增 `data_propagation` 配置节点，包含 4 个子节点对应 4 个检查点，所有参数通过 config.yaml 管理，技能本身不含硬编码。

### 关联文档

- 编码规范：[data-propagation.md](../../../xianyu-hunter-dev/assets/guides/coding-rules/data-propagation.md)
- 多用户隔离：[multi-user-auth.md](../../../xianyu-hunter-dev/assets/guides/coding-rules/multi-user-auth.md)
- Cookie 隔离：[multi-user-cookie-isolation.md](../../../xianyu-hunter-dev/assets/guides/coding-rules/multi-user-cookie-isolation.md)

---

## v4.46.0 (2026-07-17) - Cookie 自愈机制修复复盘（多级自愈/熔断重试协调/诊断日志/批量预检）

**复盘方法**：Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景
**复盘范围**：最近 3 次会话的 Cookie 自愈机制修复过程
**问题归纳**：1 大类（A 自愈机制不完整，含 4 个子问题）

**修复的代码点**：
- `src/xianyu_hunter/modules/collection_service.py`：`_refresh_token_and_retry_detail` 两级自愈（token 刷新 → cookie 强制注入 → 放弃）+ `_log_cookie_diagnostics` 诊断日志 + `_force_reinject_cookies_from_store` 强制注入
- `src/xianyu_hunter/modules/batch_refresh_scheduler.py`：`_sync_cookie_before_batch` 批次级预检（注入后调用 ensure_official_cookies）
- `src/xianyu_hunter/web/routes/unified_login.py`：`_post_login_cookie_health_check` 登录后健康探测

**修复步骤**：
1. **根因定位**：
   - 单一恢复手段（仅 cookie 强制注入）错过 token 刷新更低成本的恢复机会
   - 重试前未重置熔断标志，重试入口立即返回 None 形成"假重试"
   - 自愈失败时无诊断日志，生产事故无法定位根因
   - 批量操作前未预检 cookie 有效性，整批失败浪费时间
   - 登录后未健康探测，登录成功但 cookie 未生效即开始业务调用
2. **最小修改**：
   - collection_service.py 实现 token 刷新 → cookie 强制注入两级自愈，每级重试前重置熔断标志，每级失败记录诊断日志
   - 新增 `_log_cookie_diagnostics` 函数记录关键状态变量（存在性/过期时间/值一致性）
   - batch_refresh_scheduler.py 新增 `_sync_cookie_before_batch` 批次级预检
   - unified_login.py 新增 `_post_login_cookie_health_check` 登录后健康探测
3. **验证策略**：自愈各级别失败时诊断日志输出关键状态变量；批量操作前预检失败仅告警不阻断

**4 维度复盘要点**：
1. **成功步骤**：分级自愈 + 熔断标志重置 + 诊断日志 + 批量预检 + 登录后健康探测
2. **不确定性与失败点**：
   - 重试前未重置熔断标志导致重试被短路（假重试）- 最隐蔽根因
   - 自愈失败时无诊断日志导致生产事故无法定位根因
   - 批量操作前未预检导致整批失败浪费时间
3. **可抽象的固定流程**：
   - 多级自愈四步法（识别恢复手段 → 按成本排序 → 每级重试前重置熔断 → 每级失败记录诊断）
   - 熔断与重试协调三步法（重试前重置 → 业务逻辑设置 → 静态扫描反模式）
   - 诊断日志三步法（关键变量配置化 → 状态摘要结构化 → 函数名模式统一）
   - 批量预检四步法（预检项配置化 → 健康探测 → 告警不阻断 → 阈值配置化）
4. **适用场景**：有多个独立恢复手段的系统 / 熔断与自动重试共存 / 失败原因多样 / 批量操作
**不适用场景**：单一恢复手段 / 无熔断机制 / 失败原因单一 / 单次操作

**新增审查要点**：B-REVIEW-MULTI-LEVEL-HEALING / B-REVIEW-CIRCUIT-BREAKER-RETRY / B-REVIEW-DIAGNOSTIC-LOGGING / B-REVIEW-PRE-CHECK-BATCH（4 项）
**配置参数**：cookie_self_healing.multi_level_healing / circuit_breaker_retry / diagnostic_logging / pre_check_batch
**历史教训**：重试前未重置熔断标志导致重试代码执行了但实际从未真正发起请求，日志看似重试成功但业务仍未恢复——"假重试"反模式。

---
## v4.43.0 (2026-07-13) - Per-Preset Credential Frontend Contract
**新增检查点**：B-REVIEW-200~202
- **B-REVIEW-200: MUTATION-ECHO-FULL**：PUT /api/ai/config 必须回显完整配置状态
- **B-REVIEW-201: PRESET-ID-LITERAL-TYPE**：AIConfigBody.preset_id 必须使用 Literal 类型
- **B-REVIEW-202: FRONTEND-KEY-FIELD-CONTRACT**：后端接受前端在预设切换时不发送 api_key

**维度**：39（Per-Preset Credential Frontend Contract）
**配置节点**：pi.mutation_response_echo / pi.literal_preset_ids / credential_storage.frontend_contract

---
# 版本演进详细复盘记录（Version Changelog）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **用途**：存放各版本的完整复盘详情（Sequential Thinking 复盘法、根因分析、检查点详情），SKILL.md 顶部仅保留索引表格，需要查阅历史决策与根因时再读取本文件。
> **维护原则**：新增版本复盘时按版本号倒序插入到本文件最上方，SKILL.md 顶部表格仅更新一行索引。

---

## v4.39.0 experimental 元规范同步（meta-rules #64-#65 前端侧）

基于 2026-07-08 解决的 2 类问题复盘（URL↔状态同步失败回退 / Service Worker 缓存版本同步），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，**后端无新增 B-REVIEW 检查点**（自动化扫描项保持 188 项不变）。原因：meta-rule #64（URL↔状态同步失败回退）和 #65（Service Worker 缓存版本同步）均为纯前端场景（SheetWorkspace 多页签应用 / PWA 应用），后端不直接处理前端 URL 状态同步或 Service Worker 缓存。仅在 backend 层面同步以下原则：(1) 后端 API 返回的 URL 相关字段（如重定向路径）必须与前端 basename 配置一致；(2) 后端若提供版本号 API（如 `/api/about`），必须确保版本号唯一可信源，避免前端缓存旧版本时版本检测不一致。本次复盘的详细编码规范整合到 `xianyu-hunter-dev` v4.39.0 的 experimental meta-rules #64/#65。前端对应规范为 `xianyu-frontend-code-review` v4.44.0 的 F-REVIEW-152/153（experimental）。

------

## v4.41.0（2026-07-13）快捷预设独立 API Key 管理复盘

**复盘方法**：Sequential Thinking 4 维度复盘法
**复盘范围**：2026-07-10 AI 服务快捷预设 API Key 未跟随变化 Bug
**问题归纳**：1 大类（A 凭据切换未隔离）

**修复步骤**：
1. **根因定位**：pi_ai.py 的 save_ai_config() 只更新全局 openai_api_key，切换预设时未保存/恢复对应预设的 Key
2. **最小修改**：
   - secrets.py 新增 AI_PRESET_KEY_PREFIX 和 i_preset_key_name() 函数，按预设 ID 生成独立密钥槽
   - pi_ai.py 新增 AI_PRESET_BASE_URLS 字典和 _preset_id_for_base_url() 反向查找函数
   - AIConfigBody 新增 preset_id: Literal[...] 字段，get_ai_config() 返回 preset_id
   - save_ai_config() 新增预设切换逻辑：首次切换时迁移全局 Key 到原预设槽，目标预设 Key 自动恢复
   - config.py _load_secrets_from_keyring() 将 if api_key: 改为 if api_key is not None:
   - 端点 PUT 响应改为返回 **get_ai_config() 完整配置字典
3. **验证策略**：
   - 3 条 pytest 用例全部通过（预设切换 Key 恢复、独立保存 Key、空值覆盖 .env）

**4 维度复盘要点**：
1. **成功步骤**：TDD Red-Green-Refactor 流程；keyring 系统密钥库存储预设 Key；PUT 响应回显完整配置
2. **不确定性与失败点**：
   - RED 阶段测试因 KeyError 失败（预设密钥槽不存在）- 符合预期
   - _load_secrets_from_keyring 原有 if api_key: 判断在 keyring 无值时不会覆盖 .env 遗留值 - 最隐蔽根因
3. **可抽象的固定流程**：凭据切换五步法（存储槽设计 -> 迁移逻辑 -> 切换原子性 -> 空值覆盖 -> 更新回显）
4. **适用场景**：所有涉及预设/供应商/配置组切换的凭据管理
**不适用场景**：无凭据字段的纯展示表单、一次性操作表单

**新增审查要点**：B-REVIEW-195/196/197/198/199
**配置参数**：credential_storage.per_preset_slots、credential_storage.migration_on_first_switch、credential_storage.empty_overrides_legacy、pi.mutation_response_echo、pi.literal_preset_ids
**历史教训**：if api_key: 隐式布尔判断掩盖空字符串语义，导致 keyring 无值时 .env 遗留 Key 重新激活。

---


## v4.38.0 异步同步性/资源池基准/HTTP状态码映射/CSS选择器降级/异常日志语义/外部资源生命周期/数据库写入身份追溯复盘（meta-rules #57-#63 后端落地）

基于 2026-07-08 解决的 7 类问题复盘（async/await 误用导致 Python 3.14 兼容性风险 / NullPool 性能问题导致慢查询 231ms / HTTP 状态码语义模糊导致用户误判商品下架 / CSS 选择器单一改版即失效 / 异常日志丢失 traceback 定位耗时 30+ 分钟 / 并发采集时 page 被误关导致 TargetClosedError / 数据库写入缺 user_id 导致跨用户数据风险 + converter 处理 re.Match 报 TypeError），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 7 项 B-REVIEW 检查点（B-REVIEW-182~188），自动化扫描从 181 项扩展到 188 项。

- **B-REVIEW-182 ASYNC-AWAIT-SYNC-CHECK**（meta-rule #57 后端落地——`async def` 方法体内若不含 `await` 表达式，必须改为同步 `def`；调用点同步移除 `await`，白名单豁免 `@abstractmethod`/`__aenter__`/`__aexit__`/async generator，参数在 `meta_rules_57_63.async_await_check` 节点管理）
- **B-REVIEW-183 RESOURCE-POOL-BENCHMARK**（meta-rule #58 后端落地——资源池配置必须有性能基准数据支持，docstring 记录选择理由与对比数据，系统层开销 > 50ms 时禁止用 NullPool，参数在 `meta_rules_57_63.resource_pool_benchmark` 节点管理）
- **B-REVIEW-184 HTTP-STATUS-CODE-MAPPING**（meta-rule #59 后端落地——底层模块返回多原因的 None/错误时，必须建立 `reason_code → status_code` 映射表，底层设置 `last_*_failure_reason`，上游按映射查找状态码，参数在 `meta_rules_57_63.http_status_code_mapping` 节点管理）
- **B-REVIEW-185 CSS-SELECTOR-FALLBACK**（meta-rule #60 后端落地——依赖第三方网站 DOM 的选择器必须有 ≥3 级降级（业务语义 className → HTML role 属性 → 文本内容前缀扫描），dump 触发条件收窄到核心字段失败，参数在 `meta_rules_57_63.css_selector_fallback` 节点管理）
- **B-REVIEW-186 EXCEPTION-LOG-SEMANTIC**（meta-rule #61 后端落地——`except` 块内必须用 `logger.exception('描述')` 保留完整 traceback，禁用 `logger.warning(f'...{e}')` 丢失堆栈，非 except 块用 `exc_info=True`，参数在 `meta_rules_57_63.exception_log_semantic` 节点管理）
- **B-REVIEW-187 EXTERNAL-RESOURCE-LIFECYCLE**（meta-rule #62 后端落地——外部传入的资源（Page/Connection/Lock）必须配对调用 `register`/`unregister`，且在 `finally` 块 `unregister` 避免泄漏，引用计数管理，参数在 `meta_rules_57_63.external_resource_lifecycle` 节点管理）
- **B-REVIEW-188 DB-WRITE-IDENTITY-TRACE**（meta-rule #63 后端落地——数据库写入函数必须含 `user_id` 参数用于跨用户隔离；converter 函数处理 `re.Match` 对象必须显式调用 `m.group(1)` 再转型，禁用 `int(m)`，参数在 `meta_rules_57_63.db_write_identity_trace` 节点管理）

所有检查点强调配置驱动（参数在 config.yaml 的 `meta_rules_57_63` 节点管理，不硬编码）与适用/不适用场景说明。详细编码规范整合到 xianyu-hunter-dev v4.38.0 meta-rules #57-#63。

---

## v4.37.0 调度器运行时治理复盘（meta-rules #48-#51 后端落地）

基于 2026-07-08 解决的 5 类调度器运行时治理问题复盘（BatchRefreshScheduler 运行时禁用无效 / CookieSyncScheduler 无法运行时禁用 / scheduler.py 异常重试等待硬编码 300s / _resume_cooldown 字典内存泄漏 / cron 模式无最小间隔校验），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 4 项 B-REVIEW 检查点（B-REVIEW-178~181），自动化扫描从 177 项扩展到 181 项。

- **B-REVIEW-178 SCHEDULER-RUNTIME-TOGGLE-SYMMETRY**（meta-rule #48 后端落地——调度器 `update_config(enabled=False)` 必须 remove_job + 入口 double-check + `is_enabled()` 方法 + 配置持久化，参数在 `meta_rules_48_51.scheduler_runtime_toggle` 节点管理）
- **B-REVIEW-179 TIME-PARAM-CONFIG-DRIVEN**（meta-rule #49 后端落地——异常重试等待/轮询间隔/超时秒数等时间参数必须从 config 读取，禁止硬编码字面量，参数在 `meta_rules_48_51.time_param_config_driven` 节点管理）
- **B-REVIEW-180 LIFECYCLE-RESOURCE-CLEANUP**（meta-rule #50 后端落地——长生命周期对象的状态字典必须提供 `drop_task_state(task_id)` 方法，DELETE API 必须调用清理，参数在 `meta_rules_48_51.lifecycle_resource_cleanup` 节点管理）
- **B-REVIEW-181 CRON-MIN-INTERVAL-CHECK**（meta-rule #51 后端落地 experimental——用户输入 cron 表达式必须有最小执行间隔校验，解析失败返回结构化错误不抛异常，参数在 `meta_rules_48_51.cron_min_interval_check` 节点管理）

所有检查点强调配置驱动（参数在 config.yaml 对应节点管理，不硬编码）与适用/不适用场景说明。详细编码规范整合到 xianyu-hunter-dev v4.36.0 meta-rules #48-#51 与 step 194-197。前端对应规范为 xianyu-frontend-code-review v4.40.0 的 F-REVIEW-136~139。同时修复 v4.35 B-REVIEW-173~177 的 meta-rule 引用编号错位（#47-#51 → #43-#47）与配置节点名（`meta_rules_47_51` → `meta_rules_43_47`）。

---

## v4.35.0 跨层契约与测试同步复盘（meta-rules #43-#47 后端落地）

基于 2026-07-07 解决的 5 类问题复盘（SEMI_AUTO 模式通知未触发确认 / EVAL_PASSED 事件三处发布点 task_mode 字段不对齐 / 前端路由注册与后端 endpoint 契约缺失 / 回链 URL query string 构造与消费不一致 / 历史测试 mock 类型不匹配 + keyring fallback + 接口签名变更未同步测试），使用 Sequential Thinking 4 维度复盘法，新增 1 项维度 36（跨层契约与测试同步）+ 5 项 B-REVIEW 检查点（B-REVIEW-173~177）。所有检查点强调配置驱动（参数在 config.yaml 对应节点管理，不硬编码）与适用/不适用场景说明。详细编码规范整合到 xianyu-hunter-dev v4.35.0 meta-rules #43-#47。前端对应规范为 xianyu-frontend-code-review v4.39.0 的 F-REVIEW-131~135。

---

## v4.34.0 列表聚合与状态联动复盘（meta-rules #38-42 后端落地）

基于本轮对话解决的 5 类问题复盘（全局聚合视图未按任务个体配置范围过滤导致越界数据 / 列表交叉数据源 N+1 单条查询性能退化 / 多字段联动开关无优先级矩阵导致主开关失效后子过滤器仍生效 / precheck 抛异常而非结构化响应导致 API 层难以处理 / 配置化阈值缺失兜底导致配置缺失即崩溃），使用 Sequential Thinking 8 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景/落地映射/配置节点设计/执行计划/验证，新增 5 项 B-REVIEW 检查点（B-REVIEW-164~168），自动化扫描从 163 项扩展到 168 项。

- **B-REVIEW-164 GLOBAL-AGGREGATE-TASK-FILTER**（meta-rule #38 后端落地——全局视图（无 task_id）列表查询必须按各任务个体配置范围过滤，禁止只用全局默认范围，参数在 `global_aggregate_filter` 节点管理）
- **B-REVIEW-165 LIST-CROSS-DOMAIN-INJECT**（meta-rule #39 后端落地——列表交叉其他数据源必须批量查询 + TTL 缓存，禁止 N+1 单条查询，参数在 `cross_domain_inject` 节点管理）
- **B-REVIEW-166 MULTI-FIELD-LINKED-SWITCH**（meta-rule #40 后端落地——联动字段必须声明「主开关→过滤器」优先级矩阵，主开关失效时子过滤器自动禁用，参数在 `linked_switch_priority` 节点管理）
- **B-REVIEW-167 RESUME-PRECHECK-STRUCTURED**（meta-rule #41 后端落地——precheck 必须返回 5 字段结构化 dict `{resume_blocked, reason_code, user_hint, retry_after, task_registered}` 不抛异常，API 层直接透传，参数在 `precheck_structured_fields` 节点管理）
- **B-REVIEW-168 CONFIG-DRIVEN-THRESHOLD-FALLBACK**（meta-rule #42 后端落地——从 config 读取的阈值必须有 try/except 兜底默认值，禁止配置缺失即崩溃，参数在 `config_fallback_defaults` 节点管理）

所有新检查点强调配置驱动（参数在 `config.yaml` 的 `meta_rules_38_42` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.34.0 的 meta-rules #38-42 与 step 184-188。前端对应规范为 `xianyu-frontend-code-review` v4.38.0 的 F-REVIEW-122~126。

---

## v4.31.0 注册式资源 endpoint 契约 + 修复前根因扫描协议 + 前后端字段契约单一可信源复盘（meta-rules #33-35 后端落地）

基于 2026-07-06 解决的"通知中心菜单点击无反应"问题复盘（`config/menu_registry.yaml` 已注册 `path=/notifications`，但 `frontend/src/App.tsx` 无对应 `<Route>`、`pages/Notifications/index.tsx` 不存在、`api/notifications.ts` 不存在，路由 fallback `<Route path="*" element={<Navigate to="/" replace />} />` 静默重定向到首页），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 3 项维度（32-34）+ 3 项 B-REVIEW 检查点（B-REVIEW-159~161），自动化扫描从 163 项扩展到 166 项。

- **B-REVIEW-159 REGISTRATION-ENDPOINT-CHECK 注册式资源 endpoint 契约**（meta-rule #33 后端落地——前端已在 `menu_registry`/`router`/`page`/`api_wrapper` 注册的资源，后端必须在 `src/xianyu_hunter/web/routes/api_<domain>.py` 提供对应 `@router.<method>` endpoint；缺一即视为 CRITICAL；自动化校验脚本 `python scripts/check_registration.py` 退出码 0 才算通过，参数在 `backend_registration_endpoint` 节点管理）
- **B-REVIEW-160 ROOT-CAUSE-CHAIN-CHECK 修复前全链路根因扫描协议**（meta-rule #34 后端落地——修复非平凡 bug 前必须先列 ≥3 个根因覆盖用户层/接口层/数据层/配置层/历史层；PR 描述必须含"≥3 根因列表"段；git diff 涉及 ≥3 个无关文件视为违反最小修改原则；新增逻辑无 unit test 视为 WARNING；参数在 `root_cause_chain_check` 节点管理）
- **B-REVIEW-161 CONTRACT-OWNER-MARKER 前后端字段契约单一可信源**（meta-rule #35 后端落地——后端 Pydantic/DB Row 字段 = 权威源；后端 `BaseModel` 字段必须显式标注 `@field_validator` / `Field(..., description=...)` 标明"权威源"角色；后端字段变更必须同步通知前端 + 在 `contract_owner_marker` 节点更新 `affected_frontend_types_files` 列表；snake_case 严格透传禁止转 camelCase；参数在 `contract_owner_marker` 节点管理）

所有新检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.32.0 的 meta-rules #33-35 与 step 181-183。前端对应规范为 `xianyu-frontend-code-review` v4.36.0 的 F-REVIEW-117/118/119。

---

## v4.31.0 业务关键字常量集中管理与跨端契约对齐复盘（后端侧）

基于本轮对话解决的 5 个问题复盘（业务关键字散落导致已售状态未采集、事件类型 startswith 过滤误包含通知事件、Python 私有属性大小写不一致 AttributeError、服务未重启导致修复无效、PowerShell 编码与 shell 语法兼容问题），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 1 项维度 30（业务关键字常量集中管理与跨端契约对齐）+ 5 项 B-REVIEW 检查点：

- **B-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION**（业务关键字常量集中管理——外部平台文本特征集中到单一模块的 `*_TEXT_KEYWORDS` 常量，统一访问函数 `check_text_sold` 调用，禁止散落字面量，配置参数在 `business_keyword_centralization` 节点管理）
- **B-REVIEW-EVENT-TYPE-EXACT-MATCH**（事件类型过滤精确匹配——业务查询事件类型必须用 `==` 精确匹配，禁止 `startswith`/`endswith` 前缀过滤，通知事件与业务事件必须使用不同命名空间，配置参数在 `event_type_exact_match` 节点管理）
- **B-REVIEW-FIELD-NAME-CASE-SENSITIVE**（前后端字段名大小写敏感检查——Python 类私有属性 `_session` vs `_Session` 严格大小写一致，API 响应字段名前后端严格一致含大小写下划线前后缀，配置参数在 `field_name_case_sensitive` 节点管理）
- **B-REVIEW-SERVICE-RESTART-VERIFICATION**（服务重启验证清单——Python 后端代码修改后必须重启服务，重启后按清单验证端口监听/健康检查/数据状态/启动日志，配置参数在 `post_restart` 节点管理）
- **B-REVIEW-WINDOWS-TERMINAL-ENCODING**（Windows 终端编码与 Shell 语法兼容——PowerShell 脚本显式设置 UTF-8 编码，命令拼接用 `;` 而非 `&&`，`stash@{0}` 加引号，Python 脚本设置 stdout 编码，配置参数在 `cross_platform` 节点管理）

审查流程新增「配置驱动检查」子阶段（3 步顺序扫描：读取配置节点清单 → 逐节点扫描代码 → 配置节点缺失检测）；Template A 新增「⚙️ Config Node Missing (v4.31)」分类（CRITICAL 级别，配置节点缺失会导致配置驱动检查无法生效）；所有新检查点强调配置驱动（参数在 `config.yaml` 的 `business_keyword_centralization` / `event_type_exact_match` / `field_name_case_sensitive` / `post_restart` / `cross_platform` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.29.0 的 step 129-133。前端对应规范为 `xianyu-frontend-code-review` v4.31.0 的维度 27（业务关键字常量集中管理与字段名大小写敏感）。

---

## v4.30.0 状态恢复前置校验 + 降级链日志合并复盘（meta-rules #31-32 后端落地）

基于日志排查报告发现的两类高频问题（异常 pause 后 resume 未校验根因消除形成"恢复→失效→暂停"无效循环、多阶段降级链每步独立 WARNING 淹没真实告警），使用 Sequential Thinking 4 维度复盘法，新增 1 项维度 32（状态恢复与日志规范）+ 2 项 B-REVIEW 检查点（B-REVIEW-157~158），自动化扫描从 161 项扩展到 163 项。

- **B-REVIEW-157 RESUME-PRECHECK 状态恢复前置校验**（meta-rule #31：具有 pause/resume 语义的组件 resume 前必须 precheck 校验 root_cause 消除，校验失败返回结构化拒绝 `{resume_blocked, reason_code, user_hint, retry_after}`，异常 pause 后设冷却期，参数在 `resume_policy` 节点管理）
- **B-REVIEW-158 LOG-MERGE 多阶段降级链日志合并**（meta-rule #32：同一逻辑链多阶段日志合并为 1 条结构化 WARNING，中间步骤 DEBUG 化，结果含 `extra={stages, final_reason, keyword, attempts}`，参数在 `log_merge` 节点管理）

所有新检查点强调配置驱动（参数在 `config.yaml` 的 `resume_policy` / `log_merge` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.31.0 的 meta-rules #31/#32。前端对应规范为 `xianyu-frontend-code-review` v4.35.0 的 F-REVIEW-116（状态恢复前置校验前端侧）；前端无降级链日志场景，不新增 LOG-MERGE 对应检查点。

---

## v4.29.0 数据契约与时序复盘（meta-rules #25-30 后端落地）

基于 2026-07-05 解决的 6 类问题（batch_refresh_scheduler 断路器未保存进度/启动钩子 traceback 丢失/naive-aware 混用/跨进程状态同步缺 marker/前后端 error_code 契约缺失/业务关键字散落），使用 Sequential Thinking 4 维度复盘法，新增 6 项 B-REVIEW 检查点（B-REVIEW-151~156），自动化扫描从 155 项扩展到 161 项。

- **B-REVIEW-151 批量断路器四要素**（meta-rule #25：失败计数+进度持久化+续传入口+日志对称，参数在 `batch_circuit_breaker` 节点管理）
- **B-REVIEW-152 关键路径异常保留 traceback**（meta-rule #26：`_on_startup`/`run_migrations`/`_init_*` 外层 except 必 `logger.exception()`，参数在 `critical_path` 节点管理）
- **B-REVIEW-153 datetime 统一时区策略**（meta-rule #27：存储 UTC、算术前 unify tzinfo、序列化带 tzinfo，禁 `datetime.now()` 无 tzinfo 与 `utcnow()`，参数在 `datetime` 节点管理）
- **B-REVIEW-154 跨进程状态同步六步法**（meta-rule #28：写端+同步器+读端+启动检查+异常保留+配置驱动，参数在 `state_sync_marker` 节点管理）
- **B-REVIEW-155 前后端错误码契约**（meta-rule #29：HTTPException 必含 `error_code` 字段，参数在 `error_code` 节点管理）
- **B-REVIEW-156 业务关键字集中管理**（meta-rule #30：业务关键字禁散落代码，参数在 `business_keyword` 节点管理）

所有新检查点强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.30.0 的 meta-rules #25-30。前端对应规范为 `xianyu-frontend-code-review` v4.34.0 的 F-REVIEW-110~115。

---

## v4.28.0 全量复盘与审查要点同步（后端侧）

基于 2026-07-03 至 2026-07-05 全量问题复盘（使用 Sequential Thinking 18 步四维度复盘法——成功步骤/任务执行过程中的不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景/落地映射/配置节点设计/执行计划/验证/规范源联动），复盘范围覆盖 80+ topics，问题归纳为 7 大类（A 时区/B 命名/C 状态持久化/D Cookie 认证/E 前端交互/F 数据传递/G 鲁棒性），新增 30 项 B-REVIEW 检查点（B-REVIEW-121 ~ B-REVIEW-150）：

- 数据库维度 6 条（B-REVIEW-121~126，时区一致性/原生 SQL 类型防御/迁移步骤独立性/NOT NULL 字段防御/查询过滤条件精确性/状态值枚举一致性）
- 错误处理维度 5 条（B-REVIEW-127~131，错误归因精细化/异常传播完整性/错误消息透传/重试策略配置化/已知场景日志降噪）
- 状态管理维度 6 条（B-REVIEW-132~137，熔断器持久化对称性/状态切换原子性/多源失效判定一致性/缺失数据回退策略/多源状态同步标记机制/异步竞态防护）
- 配置管理维度 4 条（B-REVIEW-138~141，参数传递链完整性/业务关键词配置化/开关持久化/凭证多存储同步）
- 通用工程维度 5 条（B-REVIEW-142~146，属性调用一致性/API 契约一致性/命名语义清晰性/重复逻辑抽取/跨进程编码一致性）
- 数据类与启动维度 2 条（B-REVIEW-147~148，dataclass 字段显式声明/启动钩子完整性）
- 测试维度 1 条（B-REVIEW-149，测试 Mock 类型匹配）
- 浏览器自动化维度 1 条（B-REVIEW-150，Cookie 完整性管理）

自动化扫描从 125 项扩展到 155 项；**审查流程优化**：4 阶段流水线（上下文加载 → 分层扫描 → 优先级分类 → 结果呈现），替代原 5 阶段闭环；**结果呈现优化**：结构化报告模板（概览 + 问题详情，含规范引用/配置节点/反模式示例）；**配置化**：新增 `coding_standards` 节点（覆盖 datetime/migration/null_defense/query_filter/enum_consistency/error_attribution/log_noise/circuit_breaker/state_sync/credential_stores/retry/param_chain/dataclass/startup/mock/cookie/parser/encoding/dry/contract/persist/race/keywords 23 个子节点），所有参数通过 config.yaml 管理；**规范源联动**：每个 checkpoint 引用 xianyu-hunter-dev 中的规范编号（如 DATETIME-TZ-01/MIGRATE-01/NULL-01/QUERY-01/ENUM-01/ATTRIB-01/EXCEPT-01/ERROR-01/RETRY-01/LOG-NOISE-01/CIRCUIT-01/STATE-01/CONSISTENCY-01/FALLBACK-01/SYNC-01/RACE-01/PARAM-CHAIN-01/KEYWORD-01/PERSIST-01/CREDENTIAL-01/NAMING-01/CONTRACT-01/SEMANTICS-01/DRY-01/ENCODING-01/DATACLASS-01/STARTUP-01/MOCK-01/COOKIE-01），确保审查规则与编码规范单一可信源对齐。

---

## v4.28.0 多用户资源隔离/认证中间件多路校验/会话token安全/快照覆盖决策/用户身份优先级复盘（后端侧）

基于 MU1 多用户数据层 + MU2 认证中间件改造复盘（使用 Sequential Thinking 8 步复盘法——成功步骤/不确定性与失败点/可抽象流程/适用场景/落地映射/配置节点设计/执行计划/验证），新增维度 21（多用户隔离）+ 5 项 B-REVIEW 检查点：

- **B-REVIEW-MULTI-USER-RESOURCE-ISOLATION**（多用户资源隔离——全局单例资源必须按 user_id 隔离，文件路径 cookies_{uid}.json，缓存分桶 dict[str, tuple]，user_id 白名单校验防路径遍历，SQLite 兜底判断 default，配置参数在 multi_user_resource_isolation 节点管理）
- **B-REVIEW-AUTH-MULTI-PATH-VALIDATION**（认证中间件多路校验——WEB_TOKEN 直通→session_token 查库→401，hmac.compare_digest 防时序攻击，异常降级 warning 不 debug，user_id 注入 request.state，日志脱敏，配置参数在 auth_multi_path_validation 节点管理）
- **B-REVIEW-SESSION-TOKEN-SECURITY**（会话 token 安全——secrets.token_urlsafe 生成，sha256 存储，hmac.compare_digest 校验，滑动续期，撤销清缓存+标记失效，缓存与撤销互斥，会话固定防护，配置参数在 session_token_security 节点管理）
- **B-REVIEW-SNAPSHOT-REALTIME-OVERWRITE**（快照与实时数据覆盖决策——字段分四档：非空字段覆写/数值字段>0才覆写/状态字段始终覆写/标识字段只填缺失，每档有单元测试，配置参数在 snapshot_realtime_overwrite 节点管理）
- **B-REVIEW-USER-IDENTITY-PRIORITY**（用户身份识别优先级——unb>cookie2哈希>default 优先级链，每级有正则/哈希校验，配置化，最终降级 default，配置参数在 user_identity_priority 节点管理）

自动化扫描从 120 项扩展到 125 项；所有新检查点强调配置驱动（参数在 config.yaml 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.30.0 的 step 134-137。

---

## v4.27.0 端到端失败原因链与数据完整性闭环复盘（后端侧）

基于本轮对话解决的「Failed to collect item detail: page unavailable or login expired」根因复盘（代码被回退 + 服务未重启双重原因导致修复未生效，重新实施 4 个文件修复：错误语义优化 401/429/502/503 细粒度映射、merge_cookies 合并写入避免部分 cookie 覆盖完整集、cookie 完整性预检 22 个 cookie 双阈值 AND 判断、test mock 同步更新），使用 Sequential Thinking 4 维度复盘法——成功步骤/任务执行过程中的不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，新增 1 项维度 29（端到端失败原因链与数据完整性闭环）+ 6 项 B-REVIEW 检查点：

- **B-REVIEW-FAILURE-REASON-PROPAGATION**（失败原因传递链——底层设置 `last_*_failure_reason` → 中层映射 status_code → 文案与根因匹配 → reason 值可枚举集中管理，禁止用字符串子串做日志降级 marker，配置参数在 `failure_reason_propagation` 节点管理）
- **B-REVIEW-DATA-COMPLETENESS-PRECHECK**（数据完整性预检——预检方法签名 `async def _check_xxx_completeness(self) -> str | None`、双阈值 AND 判断（总数 + 关键项命中数）、调用前预检 + 调用后二次检查、错误信息含具体缺失清单，配置参数在 `data_completeness_precheck` 节点管理）
- **B-REVIEW-MERGE-VS-OVERWRITE-WRITE**（合并写入 vs 覆盖写入决策——写入策略决策矩阵（按数据来源选择策略）、合并写方法签名 `def merge_xxx(self, new_items: list[dict]) -> bool`、合并后日志输出、覆盖写必须先验证新集完整，配置参数在 `write_strategy_decision` 节点管理）
- **B-REVIEW-ERROR-MESSAGE-CONSTANT**（文案常量集中管理——文案常量集中定义、跨模块引用必须 import、禁止用字符串子串做 marker、错误响应增加 error_code 字段，配置参数在 `error_message_centralization` 节点管理）
- **B-REVIEW-EDIT-VERIFY-DEPLOY-LOOP**（修改-验证-部署闭环——修改后立即 grep 验证、全局 grep 旧文案、Python 修改后必须重启服务、重启后验证端口+数据状态、git stash 前先 commit 保底，配置参数在 `edit_verify_deploy_loop` 节点管理）
- **B-REVIEW-TEST-MOCK-SYNC**（测试 mock 同步——修改前置条件时同步更新测试 mock、mock 数据必须覆盖完整字段集、测试失败时优先检查前置条件变更、mock 数据集中管理，配置参数在 `test_mock_synchronization` 节点管理）

自动化扫描从 114 项扩展到 120 项；所有新检查点强调配置驱动（参数在 config.yaml 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.27.0 的 step 123-128。前端对应规范为 xianyu-frontend-code-review v4.27.0 的 F-REVIEW-FAILURE-REASON-UI-SYNC 等（前端侧同步原则）。

---

## v4.26.0 API三态语义/NOT NULL防御/共享单例污染复盘（后端侧）

基于本轮对话解决的「任务级配置覆盖功能开发 + 代码审查」复盘（使用 Sequential Thinking 8 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景/提炼编码规范/设计检查点/配置驱动方案/执行计划），新增 3 项 B-REVIEW 检查点：

- **B-REVIEW-EXCLUDE-UNSET-CHECK**（维度 19 状态管理与日志治理——PATCH/PUT 接口必须用 model_dump(exclude_unset=True) 区分未传/传null/传值三态，禁止手动循环跳过 None，配置参数在 api_update_semantics 节点管理）
- **B-REVIEW-NOT-NULL-NONE-DEFENSE**（维度 6 SQLite 优化——NOT NULL 字段传 null 时必须防御性 pop 而非直接写入 DB 触发 IntegrityError，覆盖字段传 null 表示清除覆盖应正常写入 None，配置参数在 api_update_semantics 节点管理）
- **B-REVIEW-SHARED-SINGLETON-POLLUTION**（维度 9 异步与调度器——循环中创建任务级覆盖对象必须用局部变量 worker_xxx，禁止直接修改 container 单例，配置参数在 shared_singleton_protection 节点管理）

自动化扫描从 111 项扩展到 114 项；所有新检查点强调配置驱动（参数在 config.yaml 的 api_update_semantics / shared_singleton_protection 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 xianyu-hunter-dev v4.26.0 的 step 117-122。前端对应规范为 xianyu-frontend-code-review v4.26.0 的 F-REVIEW-THREE-STATE-NULL-SEMANTICS（三态语义前端侧）。

---

## v4.25.0 数据库迁移块独立容错与关键路径异常可见性复盘

基于本轮对话解决的 `sqlite3.OperationalError: no such column: notifications.read_at` 问题复盘（使用 Sequential Thinking 6 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景/落地映射/配置节点设计），新增 2 项 B-REVIEW 检查点：

- **B-REVIEW-MIGRATION-BLOCK-ISOLATION**（维度 6 SQLite 优化——迁移函数内多个独立迁移块必须各自 try/except，禁止外层统一 try/except 吞掉异常导致后续块跳过；强依赖场景允许合并；块边界标识符（如 C-01/C-02 注释）在配置管理；配置参数在 `migration_block_isolation` 节点管理）
- **B-REVIEW-CRITICAL-PATH-NO-SWALLOW**（维度 11 错误处理——启动钩子/迁移/初始化等关键路径的外层 except 必须用 `logger.exception()` 输出完整 traceback，禁止 `logger.warning(f"...{e}")` 丢失堆栈；关键路径函数清单与禁止日志模式在配置管理；配置参数在 `critical_path_no_swallow` 节点管理）

自动化扫描从 109 项扩展到 111 项；同时补齐 v4.22/v4.23 遗漏未录入检查点清单的 7 项（#103-109）；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `migration_block_isolation` / `critical_path_no_swallow` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.25.0 的 step 116。前端本次为纯后端问题，参照 v4.7.0/v4.24.0 的"后端同步原则"模式，不新增 F-REVIEW 检查点，仅同步原则。

---

## v4.24.0 用户偏好类 UI 状态持久化复盘（后端侧同步原则）

基于本轮对话解决的「批量采集菜单相关参数开关应支持持久化」需求复盘（使用 Sequential Thinking 7 步复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景/落地映射/配置节点设计/执行计划细化），**不新增 B-REVIEW 检查点**（自动化扫描项保持 109 项不变）。原因：本次问题为纯前端 UI 状态持久化（用户偏好类 UI 状态使用 usePersistentState 而非 useState），后端不直接处理前端 UI 状态，业务场景过于狭窄。仅在 backend 层面同步以下原则：

1. 若后端提供用户偏好类 API（如 `/api/user/preferences`），所有偏好字段的存储格式、序列化策略、默认值、校验逻辑应在 `config.yaml` 管理，不硬编码
2. 后端持久化的字段（如批量采集的 `enabled` / `interval_minutes` 已通过 `PATCH /api/batch-refresh/config` 持久化）必须与前端保持单一可信源，前端不得再用 `usePersistentState` 重复持久化（避免前后端不一致），后端 `GET /status` 返回值必须是前端唯一可信源
3. 后端若涉及"用户偏好"语义的接口（如 `/api/user/preferences`、`/api/profile/settings`），必须遵循 B-REVIEW-CONFIG-DRIVEN-TOGGLE（v4.3.0）的配置驱动开关原则 + B-REVIEW-NO-HARDCODED-THRESHOLD（v4.4.0）的禁止硬编码阈值原则

本次复盘的详细编码规范整合到 `xianyu-hunter-dev` v4.24.0 的 step 115（仅前端规范），前端审查规则落地到 `xianyu-frontend-code-review` v4.24.0 的 F-REVIEW-UI-PREFERENCE-PERSISTENCE（第 77 项）。后端自动化扫描项保持 109 项不变。

---

## v4.23.0 能力驱动派发 / 共享工具函数 / 静默降级预检复盘（后端侧）

基于本轮对话解决的"LLM 深度分析因 vision 模型不支持 image_url 触发 400"问题复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景），新增 1 项维度 28（LLM 端点能力派发与共享工具函数）+ 3 项 B-REVIEW 检查点：

- **B-REVIEW-LLM-CAPABILITY-DISPATCH**（能力驱动派发——任何 LLM/多模态/function_call/json_mode 调用必须在构造 payload 前预检目标模型能力，能力校验函数必须共享（`api_ai._is_vision_capable`），关键字白名单配置化（`config.yaml` 的 `llm_capability_keywords` 节点），散落内联即违规）
- **B-REVIEW-SHARED-UTIL-CENTRALIZATION**（共享工具函数规范——跨 ≥2 模块复用的判断逻辑/关键字白名单/常量必须抽取为"被依赖方"模块顶层的纯函数或模块级常量，导入方只能 `from <source> import <shared>`，审查场景：跨 ≥2 文件出现相同关键字/正则/常量字面量必须触发"抽取共享"建议，配置参数在 `shared_util_rules` 节点管理）
- **B-REVIEW-SILENT-DOWNGRADE-PRECHECK**（静默降级预检——可选增强能力（vision/function_call/json_mode）调用前必须预检，失败时降级为等价文本表达（如 prompt 追加"图片 URL + 描述"）而非抛错，预检失败日志级别 `logger.warning`（与 v4.9 B-REVIEW-LOG-DOWNGRADE-STABILITY 一致），降级 prompt 模板集中管理（`config.yaml` 的 `llm_downgrade` 节点），区分"可选增强"与"核心能力"（核心能力缺失必须报错））

自动化扫描从 106 项扩展到 109 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `llm_capability_keywords` / `shared_util_rules` / `llm_downgrade` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.21.0 的 step 112-114。前端对应规范为 `xianyu-frontend-code-review` v4.23.0 的 `F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION`。

---

## v4.22.0 启动钩子完整性/任务历史三层保护/计数器DB MAX/interval首次执行复盘（后端侧）

基于本轮对话解决的 4 个问题（反爬会话管理未自动启动、批量采集历史残留running状态、task_id跨进程重启重置、interval触发器首次执行延迟30分钟）复盘（使用 Sequential Thinking 6 步复盘法——成功步骤/失败点/可抽象流程/适用场景/元规范提炼与落地映射），新增 4 项 B-REVIEW 检查点：

- **B-REVIEW-STARTUP-HOOK-COMPLETENESS**（维度 9 异步与调度器——所有依赖 container.browser/collector 的组件必须在 startup.py _on_startup 中有对应 start_xxx() 启动钩子，启动钩子必须用 if _should_start_scheduler() 包裹，放在依赖的调度器之后，启动失败 try/except 兜底仅 warning 不阻断主服务，验证方法 grep container.browser/collector 找所有依赖点逐个检查，配置参数在 startup_hook_completeness 节点管理）
- **B-REVIEW-TASK-HISTORY-THREE-LAYER-PROTECTION**（维度 9 异步与调度器——写入 running 状态的代码路径必须有对应 finalize 调用更新为终态，必须覆盖正常结束/future.result超时/协程异常三条路径，错误消息累积设FIFO上限避免JSON字段无限膨胀，状态语义区分 circuit_broken→failed / _stop_flag→cancelled / 正常→completed，配置参数在 task_history_protection 节点管理）
- **B-REVIEW-COUNTER-DB-MAX-INIT**（维度 6 SQLite 优化——业务自增ID如 task_id/batch_id/run_id 不能依赖内存初始化（进程重启会重置），调度器 __init__ 时必须从 DB SELECT MAX(id) 初始化，查询失败回退到0+warning不阻断启动，trigger_now 时 +1 立即返回前端不等待DB写入，配置参数在 counter_db_max_init 节点管理）
- **B-REVIEW-APSCHEDULER-INTERVAL-FIRST-RUN**（维度 9 异步与调度器——APScheduler interval 触发器默认首次执行时间为 start+interval（即启动后等完整间隔），需要启动后快速反馈的场景必须设 next_run_time=now+delay，delay 建议5-10秒给初始化依赖就绪，日志必须输出间隔+首次执行时间，配置参数在 apscheduler_interval_first_run 节点管理）

自动化扫描从 102 项扩展到 106 项；所有新检查点均强调配置驱动（参数在 config.yaml 的 startup_hook_completeness / task_history_protection / counter_db_max_init / apscheduler_interval_first_run 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 xianyu-hunter-dev v4.20.0 的 step 107-110。前端对应规范为 xianyu-frontend-code-review v4.22.0 的 F-REVIEW-PWA-CACHE-VERIFY（PWA 缓存验证）。

---

## v4.20.0 版本号源管理复盘（后端侧）

基于本轮解决的"版本管理菜单持续显示 V10"问题复盘（使用 Sequential Thinking 6 步复盘法——成功步骤/失败点/可抽象流程/适用场景），落地 v4.19.0 遗留待办，新增 1 项 B-REVIEW 检查点：

- **B-REVIEW-VERSION-SOURCE-SINGLE**（维度 14 配置管理——构建期元数据必须有唯一源头文件 `__init__.py: __version__`，构建期元数据由 `scripts/build_info.py` 自动生成 `_build_info.py`；多端点读取同一元数据必须封装 `_safe_xxx()` 三层 try/except 回退辅助函数（源头 → 生成文件 → 默认值 `'unknown'`）；export_config / about / health 等多端点响应中涉及版本号字段必须调用 `_safe_app_version()` 而非硬编码占位符 `"1.0"` / `"0.0.0"` / `"unknown version"`；端点命名相似不等于语义对齐，`/api/config/version` 名称含 "version" 但实际返回 `len(backups)`，应在端点命名或 docstring 中明确语义）

自动化扫描从 101 项扩展到 102 项；新检查点强调配置驱动（参数在 `config.yaml` 的 `version_source_management` 节点管理，包含 `single_source_file` / `auto_generated_file` / `safe_helper_function` / `fallback_default` / `forbidden_placeholders` / `forbidden_version_endpoints` 等，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.18.0 的 step 98。前端对应规范为 `xianyu-frontend-code-review` v4.20.0 的 `F-REVIEW-VERSION-SOURCE-ALIGN`。

---

## v4.19.0 DOM 选择器同步/外部文案集中管理/调度器启动可见性复盘

基于本次对话解决的 3 个核心问题复盘（使用 Sequential Thinking 12 步复盘法——成功步骤/失败点/可抽象流程/适用场景/元规范提炼/落地映射/配置节点设计），新增 3 项 B-REVIEW 检查点：

- **B-REVIEW-SELECTOR-REPOSITORY-SYNC**（维度 11 错误处理——同一 DOM 数据源的所有解析路径（主解析 `_find_cards` / 批量解析 `_BATCH_PARSE_SCRIPT` / 降级解析）必须引用同一选择器仓库，JS 脚本必须动态拼接选择器字符串（禁止内联 CSS 选择器），ID 提取必须有 3 层兜底（data-* 属性 → 内部任意 a[href] → /item/数字 路径），配置参数在 `selector_repository_sync` 节点管理）
- **B-REVIEW-EXTERNAL-TEXT-PATTERN-CENTRALIZE**（维度 13 代码质量——外部系统（闲鱼/淘宝/第三方 API）的文本特征（已售关键词/错误码/状态文案）必须提取为模块级常量（`tuple[str, ...]` 或 `frozenset[str]`），多处消费点必须复用同一纯函数（`check_xxx(text) -> bool`），禁止在消费点内联关键词列表，配置参数在 `external_text_pattern_centralize` 节点管理）
- **B-REVIEW-SCHEDULER-STARTUP-VISIBILITY**（维度 9 异步与调度器——关键后台调度器（影响业务正确性的，如批量采集/状态回查/数据同步）启动时输出 INFO + 间隔，未启动时输出 WARNING + 醒目提示 + 启动命令 + 影响范围，`--help` 必须说明启动参数影响范围，`/api/about` 端点必须返回调度器状态，配置参数在 `scheduler_startup_visibility` 节点管理）

自动化扫描从 98 项扩展到 101 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `selector_repository_sync` / `external_text_pattern_centralize` / `scheduler_startup_visibility` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.19.0 的 step 99-101。前端对应规范为 `xianyu-frontend-code-review` v4.19.0 的 `F-REVIEW-SCHEDULER-STATUS-DISPLAY`。遗留待办：v4.17.0/v4.18.0 的 VERSION-SOURCE 规范（B-REVIEW-VERSION-SOURCE-SINGLE）尚未在本 skill 落地，需后续补充。

---

## v4.16.0 字段归一化文档化 + 除零兜底禁止凑数复盘

基于本次对话解决的「前端接入 api_ai_deep 端点 + 后端贩子识别维度 3/4 实现」代码审查复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 2 项 B-REVIEW 检查点：

- **B-REVIEW-FIELD-NORMALIZE-DOC**（维度 18 跨字段一致性与硬编码属性禁用——后端对 LLM/外部响应做归一化（合并/重命名/转换字段）时必须在前端 types.ts 对应字段声明中加注释「后端已归一化，前端消费 X 字段」，types.ts 中保留旧字段名必须标 optional 并注释「仅作兼容保留，后端不返回」，前端禁止通过动态 key 取归一化字段必须直接用归一化后字段名，配置参数在 `field_normalize_doc` 节点管理）
- **B-REVIEW-DIVZERO-FALLBACK**（维度 13 代码质量——除零/空值兜底禁止用凑数小数 `x / 0.1` 伪装比值，比值/比率/百分比计算中 previous_count/baseline 可能为 0 时直接置为 0.0 或 float('inf')，写入 reason/log 展示给用户的数值无意义时用字符串 "N/A" 而非数字，配置参数在 `divzero_fallback` 节点管理）

自动化扫描从 96 项扩展到 98 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `field_normalize_doc` / `divzero_fallback` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.17.0 的 step 94-97。前端对应规范为 `xianyu-frontend-code-review` v4.16.0 的 `F-REVIEW-FIELD-CONTRACT-ALIGN` / `F-REVIEW-ERROR-HANDLER-EXTRACT`。

---

## v4.15.0 Cookie 层状态管理 + 代码变更逻辑审查复盘（后端侧）

基于本轮解决的"功能正常但状态显示失效"问题（用户反馈：实时查询、官方采集等功能均能正常运行，但 identity、session、tracking 状态持续显示失效）+ 代码变更逻辑审查（发现 2 个 Critical / 3 个 Suggestion / 2 个 Nit）复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 3 项 B-REVIEW 检查点：

- **B-REVIEW-CACHE-INVALIDATION**（维度 14 配置管理——任何持久化层（JSON/SQLite/外部配置）变更后必须**显式调用**对应缓存对象的 `invalidate_cache()` 或等价方法，TTL 兜底不替代主动失效，跨进程变更必须主动通知主进程，配置参数在 `cache_invalidation` 节点管理）
- **B-REVIEW-STATE-DETECTION-BOOTSTRAP**（维度 9 异步与调度器——任何"功能信号"字段不能仅用布尔初始值代表"未检测"，必须配合"已发生过检测"标记（时间戳/计数器/标志位），强制恢复需白名单（信号只能恢复其能证明有效的层范围），配置参数在 `state_detection_bootstrap` 节点管理）
- **B-REVIEW-MIGRATION-TRANSACTION**（维度 6 SQLite 优化——SQLite 不支持 ALTER COLUMN，修改列约束必须用 `engine.begin()` 单事务 + 残留清理 + 数据复制 + 异常恢复模式，禁止分散 commit 或裸 ALTER，配置参数在 `migration_transaction` 节点管理）

自动化扫描从 93 项扩展到 96 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `cache_invalidation` / `state_detection_bootstrap` / `migration_transaction` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.16.0 的 step 91-93。前端对应规范为 `xianyu-frontend-code-review` v4.16.0 的 `F-REVIEW-STATE-FUNCTIONAL-ALIGN`。

---

## v4.14.0 登录流程性能优化/Cookie层同步测试修复/代码变更逻辑审查复盘（后端侧）

基于本次会话解决的 4 个问题（登录流程性能优化、Cookie层同步测试修复、代码变更逻辑审查）复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 3 项 B-REVIEW 检查点：

- **B-REVIEW-ROUTE-BLOCK-TYPES**（维度 9 异步与调度器——浏览器自动化资源拦截必须考虑业务关键资源，禁止盲目拦截 image/font/media，拦截前必须检查页面是否依赖图片渲染关键内容如二维码图片，配置参数在 `browser.route_block_types` 节点管理）
- **B-REVIEW-SIGNAL-LAYER-MAPPING**（维度 10 事件总线——层恢复信号必须与层范围匹配，SESSION层信号不能恢复IDENTITY层，信号只能恢复其所属层及以下层，配置参数在 `cookie_layers.signal_layer_mapping` 节点管理）
- **B-REVIEW-DEBUG-CODE-CLEANUP**（维度 13 代码质量——临时DEBUG代码在问题修复后必须移除，禁止留在生产代码中，配置参数在 `debug` 节点管理）

自动化扫描从 90 项扩展到 93 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的对应节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.15.0 的 step 86-88。前端对应规范为 `xianyu-frontend-code-review` v4.15.0 的 `F-REVIEW-DEBUG-CODE-CLEANUP`。

---

## v4.13.0 统计分类互斥性复盘（后端侧）

基于本轮对话解决的「评估明细页面优化」工作复盘（使用 Sequential Thinking 5 步系统分析——成功步骤/失败点/可抽象流程/适用场景/落地映射），新增 1 项 B-REVIEW 检查点：

- **B-REVIEW-STATS-EXCLUSIVE**（维度 19 API 设计规范——统计接口返回的分类计数必须互斥，total = sum(各分类计数)，insufficient(score==null) 与 score-based 分类(auto/pass/fail) 互斥，禁止一个记录同时计入两个分类导致统计数量与实际不符）

自动化扫描从 89 项扩展到 90 项；新检查点强调配置驱动（参数在 `config.yaml` 的 `stats_exclusive` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.14.0 的 step 82。前端对应规范为 `xianyu-frontend-code-review` v4.14.0 的 `F-REVIEW-FILTER-BACKEND-ALIGN`。

---

## v4.12.0 官方采集失败复盘（后端侧）

基于本轮对话解决的「官方采集失败」P0-P3 优化工作复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 4 项 B-REVIEW 检查点：

- **B-REVIEW-DOM-FALLBACK-CHAIN**（维度 11 错误处理——SPA 数据提取必须 DOM → og:meta → document.title 多层兜底，与 v4.3 B-REVIEW-FALLBACK-CHAIN 多方案降级语义不同，本节点专指 DOM 提取兜底，禁止单一选择器失败即整体失败）
- **B-REVIEW-FAILURE-DUMP**（维度 11 错误处理——关键选择器失败必须 dump `page.content()` 到 `logs/<scenario>_<id>_<timestamp>.html` 用于事后取证，dump 用 `asyncio.create_task` fire-and-forget 不阻塞主流程，敏感字段需脱敏）
- **B-REVIEW-TIMING-INSTRUMENTATION**（维度 8 性能——关键路径 `page.goto`/`wait_for_selector`/HTTP/DB 必须用 `time.perf_counter()` 计时并按阈值告警，禁止仅用 `logger.info("开始")/logger.info("结束")` 文本日志难以聚合分析）
- **B-REVIEW-PRECHECK-AND-PARALLEL**（维度 9 异步与调度器——高开销操作前必须前置校验 Cookie 凭证 `expires` 字段，session cookie `expires=-1` 跳过预校验，persistent cookie 过期直接返回 440 不启动浏览器；独立 IO 任务必须用 `asyncio.gather(*tasks, return_exceptions=True)` 并行执行，禁止 `for task in tasks: await task` 串行）

自动化扫描从 82 项扩展到 86 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `dom_fallback_chain` / `failure_dump` / `timing_instrumentation` / `precheck_parallel` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.13.0 的 step 76-81。前端对应规范为 `xianyu-frontend-code-review` v4.13.0 的 `F-REVIEW-ERROR-CONTRACT-TIMEOUT` / `F-REVIEW-RETRY-BACKOFF`。

---

## v4.11.0 配置校验/迁移失败处理/状态码语义/LLM 防御解析/调度器 DB 同步/后台任务监控/数值提取复盘

基于本轮对话解决的 7 类问题复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 7 项 B-REVIEW 检查点：

- **B-REVIEW-CONFIG-VALIDATION**（维度 14 配置管理——数值型配置项必须有边界值校验 min/max/non_zero/range，加载时主动校验无效值用默认值+warning，禁止直接用于算术运算导致 ZeroDivisionError）
- **B-REVIEW-MIGRATION-FAILURE-HANDLING**（维度 6 SQLite 优化——`_migrate_*` 函数失败必须明确策略，关键迁移 raise RuntimeError 中断启动，非关键 warning+继续，禁止 `except: pass` 静默吞掉）
- **B-REVIEW-STATUS-CODE-SEMANTICS**（维度 7 安全性——HTTP 状态码按语义精细化区分 401 未登录/403 权限不足/440 Cookie 过期/441 Token 过期/504 网关超时，禁止所有认证失败都映射为 401）
- **B-REVIEW-LLM-DEFENSIVE-PARSING**（维度 11 错误处理——LLM API 响应必须三层级防御性解析 choices→message→content，每层用 .get()+isinstance+长度检查，禁止链式访问导致 KeyError/IndexError）
- **B-REVIEW-SCHEDULER-DB-SYNC**（维度 9 异步与调度器——调度器内存状态变更必须同步 DB（update_task_status），禁止只在内存变更导致 API 返回与实际不一致）
- **B-REVIEW-BACKGROUND-TASK-MONITOR**（维度 9 异步与调度器——后台 asyncio.Task 必须用轮询监控 task.done()，禁止 asyncio.Event().wait() 静默等待导致任务异常退出无感知）
- **B-REVIEW-NUMERIC-EXTRACTION**（维度 13 代码质量——多数字文本必须用 re.findall 取 numbers[-1]，禁止 re.search 取第一个数字误取原价）

自动化扫描从 75 项扩展到 82 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `config_validation` / `migration_failure_strategy` / `status_code_semantics` / `llm_defensive_parsing` / `scheduler_db_sync` / `background_task_monitor` / `numeric_extraction_strategy` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.12.0 的 step 69-75。前端对应规范为 `xianyu-frontend-code-review` v4.12.0 的 `F-REVIEW-INPUT-NUMBER-BOUNDS` / `F-REVIEW-XSS-ESCAPE`。

---

## v4.10.0 过滤结果可见性/pytest 模块重复 import 隔离/日志库占位符一致性/测试 fixture 生产隔离复盘

基于本轮对话解决的 4 类问题复盘（使用 Sequential Thinking 8 步系统分析——成功步骤/失败点/可抽象流程/适用场景/落地映射），新增 4 项 B-REVIEW 检查点：

- **B-REVIEW-FILTER-VISIBILITY**（维度 19 API 设计规范——含过滤链路的查询接口必须输出完整 `filter_summary` 含 raw/各阶段 skipped/final_total/filtered_out，filtered_out 项含 link_type/link_key/display/filter_reason/filter_detail 5 字段，max_filtered_out_items 上限从 config 读取禁止硬编码 50）
- **B-REVIEW-PYTEST-MODULE-REIMPORT**（维度 20 测试建议——conftest.py patch 模块属性时必须遍历 sys.modules 找所有持目标属性的模块全部 patch，禁止硬编码模块名列表，禁止用 `__import__` 必须用 `importlib.import_module`）
- **B-REVIEW-LOGURU-PLACEHOLDER**（维度 12 日志规约——loguru 项目所有 logger.xxx() 必须用 `{}` 占位符，grep `%[sdrf]` 在 logger 调用行附近即发现违规，混用不抛异常但显示 %s 字面量极难发现）
- **B-REVIEW-TEST-FIXTURE-ISOLATION**（维度 20 测试建议——conftest.py 必须 patch 生产路径到 tmp_path，fixture 数据需带可识别特征如 `test_fixture_` 前缀，数据污染应急 5 步流程停止服务→删除污染文件→修复 conftest→重跑测试→通知用户）

自动化扫描从 71 项扩展到 75 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `filter_summary` / `pytest_isolation` / `log_placeholder` / `test_isolation` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.11.0 的 step 65-68。前端对应规范为 `xianyu-frontend-code-review` v4.10.0 的 `F-REVIEW-FILTER-VISIBILITY`。

---

## v4.9.0 双链路一致性/状态机/资源生命周期/并发安全/Python 现代化复盘

基于本次对话解决的 5 类问题复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 5 项 B-REVIEW 检查点：

- **B-REVIEW-STATE-MACHINE-WHITELIST**（维度 11 状态机白名单转换——业务对象有状态字段且会变化时必须按枚举穷举/白名单转换/终态不可复活/中间态超时清理/deadline 不可无限重置/前后端枚举值统一 6 步流程设计）
- **B-REVIEW-RESOURCE-CLEANUP-HOOK**（维度 9 资源生命周期——可注册组件必须实现 cleanup() 钩子，asyncio.Task 引用保留防 GC，取消+gather 模式，try/finally 初始化）
- **B-REVIEW-DUAL-LINK-CONSISTENCY**（维度 18 双链路一致性——同一业务目标有 ≥2 条链路时共用前置条件必须提取为独立函数两链路调用同一函数，grep 验证+测试覆盖）
- **B-REVIEW-CONCURRENT-STATE-LOCK**（维度 9 并发安全——共享状态检查+更新必须在同一锁内，dataclass 字段显式声明禁止 getattr 兜底）
- **B-REVIEW-PYTHON-MODERN-ASYNCIO**（维度 9 Python 现代化——asyncio.create_task 替代 get_event_loop，模块级 import，CancelledError 传播）

自动化扫描从 69 项扩展到 74 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `state_machine` / `resource_lifecycle` / `dual_link_consistency` / `concurrency_safety` / `python_modern` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.10.0 的 step 60-64。

---

## v4.8.0 状态管理与日志治理复盘

基于"日志分析优化 + 代码评审复盘"（使用 Sequential Thinking 4 维度分析——成功步骤/失败点/可抽象流程/适用场景），新增 3 项 B-REVIEW 检查点：

- **B-REVIEW-STATE-FLAG-PRECHECK**（维度 9 状态标志前置检查完整性——检测到异常状态后后续操作入口必须有前置检查）
- **B-REVIEW-LOG-DOWNGRADE-STABILITY**（维度 12 日志降级判断稳定性——判断字符串提取为模块级常量）
- **B-REVIEW-EDIT-VERIFY**（维度 13 修改生效验证——Edit 后用 Grep 验证）

自动化扫描从 86 项扩展到 89 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `state_flag_precheck` / `log_downgrade` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。

---

## v4.8.0 频率伪装统计孤岛复盘

基于"反爬登录管理菜单的频率伪装统计持续为 0 且无变化"问题复盘（使用 Sequential Thinking 4 维度复盘法——成功步骤 / 失败点 / 可抽象流程 / 适用场景），新增 3 项 B-REVIEW 检查点：

- **B-REVIEW-ISLAND-MODULE**（维度 13 孤岛模块检测——统计/计数器/采样类模块必须有业务调用方，否则视为孤岛，修复模式 grep 检测调用方 + Orchestrator 入口封装 + 业务模块集成 + 前端定时刷新）
- **B-REVIEW-TIME-SENSITIVE-SPLIT**（维度 11 时间敏感场景的延迟/统计分离——业务操作存在延迟容忍度差异时核心模块必须提供"延迟+统计"与"仅统计"两种入口，fast 模式仅跳过 sleep 保持统计连续）
- **B-REVIEW-AUX-LOG-LEVEL**（维度 12 辅助功能异常日志级别——辅助功能失败必须用 `logger.warning` 记录，禁止 `logger.debug`（默认不输出）和 `logger.error`（过度严重））

自动化扫描从 66 项扩展到 69 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `freq_disguise_stats` / `freq_disguise_time_sensitive` / `log_level_strategy` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。详细编码规范整合到 `xianyu-hunter-dev` v4.9.0 的 step 56-59。

---

## v4.7.0 AntD 主题 token 动态覆盖复盘（后端同步原则）

基于前端"暗色主题下 Table hover 高亮色与文字色一致导致不可见"问题复盘（使用 Sequential Thinking 5 步系统分析——成功步骤 / 失败点 / 可抽象流程 / 适用场景 / 落地映射），**未新增 B-REVIEW 检查点**。原因：后端不直接处理 antd 主题 token，业务场景过于狭窄。仅在后端层面同步以下原则：

1. 后端若提供"主题配置 API"（如 `/api/config/theme` 返回主题相关 token），所有 token 默认值应在 `config.yaml` 管理，不硬编码
2. API 返回的 token 字段需与前端 `ConfigProvider` 中的 token 名保持一致（文档同步）
3. 新增 token 字段时需提供默认值，避免前端取不到值（向后兼容）

本次复盘的详细编码规范整合到 `xianyu-hunter-dev` v4.8 的 step 55，前端审查规则落地到 `xianyu-frontend-code-review` v4.8.0 的 F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE（第 52 项）。后端自动化扫描项保持 66 项不变。

---

## v4.6.0 异步超时 / 数据流转 / 过滤场景 / 复用模式复盘

基于"评估明细标题采集超时 + 订单字段为空根因定位 + 一刀切过滤导致展示缺失"三个问题复盘（使用 Sequential Thinking 5 步系统分析——成功步骤 / 失败点 / 可抽象流程 / 适用场景 / 落地映射），新增 4 项 B-REVIEW 检查点：

- **B-REVIEW-ASYNC-TIMEOUT**（维度 9 异步操作整体超时保护——`await` 外部资源必须在调用层用 `asyncio.wait_for(coro, timeout=N)` 包装，超时返回 504 状态码，禁止依赖被调用方内部 timeout 参数）
- **B-REVIEW-DATA-FLOW-TRACE**（维度 18 字段为空 5 点追踪——"字段为空"类问题必须按 DB schema → Repo 查询过滤 → API 注入 → 前端 types → render 取值 5 点逐层追踪）
- **B-REVIEW-FILTER-SCENARIO**（维度 6 过滤逻辑场景区分——同一查询被多场景复用时必须参数化场景标志 `include_failed`，操作判断与展示历史场景区分）
- **B-REVIEW-REUSE-PATTERN**（维度 13 复用既有模式——新增功能前必须 grep 项目内相似实现，复用既有 helper/工具函数/模式 `asyncio.wait_for` / `hmac.compare_digest` / `_escape_like` / `_utcnow`）

自动化扫描从 62 项扩展到 66 项；所有新检查点均强调配置驱动（参数在 `config.yaml` 的 `async_timeout` / `data_flow_trace` / `filter_scenario` / `reuse_pattern` 节点管理，不硬编码）与适用/不适用场景说明（确保通用性）。

---

## v4.5.0 Cookie 分层管理架构修复复盘

基于"5 个登录路径不更新 CookieRotator 层状态 + cookie_checker 覆盖手动失效 + MTOP Set-Cookie 不回写 JSON + update_cookie_values 并发非原子"问题复盘（使用 4 维度复盘法——成功步骤/失败点/可抽象流程/适用场景），新增 6 项 B-REVIEW 检查点：

- **B-REVIEW-MULTI-WRITE-ENTRY**（维度 10 状态同步统一入口——多入口写入同一份状态时必须有显式同步函数，禁止依赖未触发回调）
- **B-REVIEW-INACTIVE-STATE-PRESERVE**（维度 10 状态条件区分——用 `updated_at == 0.0` 区分"从未初始化"与"主动失效"，避免补救逻辑覆盖手动失效）
- **B-REVIEW-BROWSER-FALLBACK-SYNC**（维度 10 浏览器内存兜底——`/cookies/layers` 等状态查询端点两步同步，先从 JSON 补救仍有层未恢复时从浏览器内存兜底并回写）
- **B-REVIEW-UPDATE-VS-UPSERT**（维度 6 持久化语义区分——`update_*` 只更新已存在、`upsert_*` 更新+添加，concurrent 场景必须在 RLock 内完成读-改-写）
- **B-REVIEW-POST-WRITE-HOOK**（维度 14 写后钩子——写主数据源后必须显式调用同步钩子，失败仅记录日志不抛异常）
- **B-REVIEW-DEAD-CODE-CLEANUP**（维度 13 死代码清理——大版本时主动 grep "定义未调用"的函数/回调并清理）

自动化扫描从 56 项扩展到 62 项。

---

## v4.4.0 搜索参数链路 + 错误语义 + 硬编码阈值复盘

基于"实时搜索错误提示语义偏差 + fast 模式跳过恢复机制 + 搜索参数配置不生效"三个问题复盘（使用 Sequential Thinking 4 维度分析），新增 5 项 B-REVIEW 检查点：

- **B-REVIEW-ERROR-SEMANTICS**（维度 7 错误提示语义准确性——RGV587=token 过期不应映射为 401 登录失效）
- **B-REVIEW-CONFIG-LINKAGE**（维度 14 配置全链路生效验证——config.yaml→Config→TaskConfig→Worker→方法参数→URL 构建逐层追踪）
- **B-REVIEW-FAST-DEGRADATION**（维度 11 快速模式降级重试——fast=True 跳过恢复机制时调用方应自动以非 fast 模式重试一次）
- **B-REVIEW-NO-HARDCODED-THRESHOLD**（维度 9 硬编码阈值禁用——MAX_CONSECUTIVE_ERRORS=10 改为读取 fail_pause_threshold 配置）
- **B-REVIEW-PARAM-PASS-THROUGH**（维度 5 参数透传链路完整性——方法签名新增参数后必须 grep 所有调用点确认传递）

自动化扫描从 51 项扩展到 56 项。

---

## v4.3.0 浏览器 Cookie 导入增强复盘

基于"浏览器 Cookie 导入增强（v20 加密 + 多 Profile + 自动同步）"复盘（使用 Sequential Thinking 4 维度分析），新增 9 项 B-REVIEW 检查点：

- **B-REVIEW-ENCRYPTION-DEGRADATION**（维度 7 加密升级退化策略）
- **B-REVIEW-MULTI-PROFILE-DISCOVERY**（维度 16 多配置文件发现）
- **B-REVIEW-FILE-LOCK-BYPASS**（维度 6 SQLite immutable 文件锁绕过）
- **B-REVIEW-SCHEDULER-ISOLATION**（维度 9 独立调度器隔离）
- **B-REVIEW-CONFIG-DRIVEN-TOGGLE**（维度 14 配置驱动功能开关）
- **B-REVIEW-FALLBACK-CHAIN**（维度 11 降级链模式）
- **B-REVIEW-CHROME-136-ADAPTATION**（维度 15 Chrome 136+ 限制适配）
- **B-REVIEW-WINDOWS-TEST-MOCK**（维度 20 Windows 测试环境 Mock）
- **B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK**（维度 20 第三方插件依赖预检）

自动化扫描从 42 项扩展到 51 项；所有新检查点均强调配置驱动（参数在 config/*.yaml 管理，不硬编码）与适用/不适用场景说明（确保通用性）。

---

## v4.2.0 反爬模块代码审查复盘

基于反爬模块全面评估复盘，新增维度 24（跨字段一致性与硬编码属性禁用），补充检查项：dataclass 相关字段一致性校验、Cookie/HTTP 属性硬编码、`run_coroutine_threadsafe`+`future.result()` 跨线程死锁组合、try/finally 变量未初始化、跨组件状态双向同步、错误提示端点可操作性验证，自动化扫描从 36 项扩展到 42 项。

---

## v4.1.0 会话失效处理复盘

基于"实时搜索会话失效未推送明确错误提示"问题复盘，新增维度 11（重试失败后状态信号传递）+ 维度 7（Cookie 检查全面性）补充检查项，自动化扫描从 34 项扩展到 36 项；新增错误粒度三类区分（503/504 稍后重试、401/403 需用户介入、502 需重启服务）、对照证据定位法（用户反馈业务查不到时首要排查步骤）。

---

## v4.0.0 事件时机/字段覆盖/幂等性/搜索标准化复盘

基于 DingTalk 通知事件时机修复 + 评估详情字段覆盖策略 + 反爬登录幂等性 + 实时搜索标准化 + 代码评审通用规范复盘，新增维度 9（事件触发时机）、维度 13（注释一致性）、维度 17（字段覆盖策略）、维度 19（幂等性设计 + 搜索接口标准化）补充检查项，自动化扫描从 24 项扩展到 34 项。

---

## v3.0.0 SonarQube 规则增强

基于 SonarQube 修复实战复盘，扩展维度 9（异步与调度器）新增 S7503 规则检查、维度 13（代码质量）新增 S3776（认知复杂度）、S6767（未使用参数）、S1192（重复字符串）、S5843（正则复杂度）规则，补充实战案例（`login_orchestrator.start_session` 7 步拆分模式、`scheduler.start_all` 同步化），自动化扫描从 14 项扩展到 24 项；新增 Evaluator 构造检查（禁止接受覆盖参数）、KB 白名单检查、`CancelledError` 传播检查。

---

## v2.1.0 新增维度 23（Git 操作规范）

基于多分支合并实战复盘，新增 `.git/index.lock` 残留检测、产物文件 untrack、cherry-pick 冲突保留策略、async/await 一致性等检查项，自动化扫描从 12 项扩展到 14 项。

---

## v2.0.0 知识点整合

整合 `xianyu-hunter-dev` 技能的 `backend-guide.md`、`database-guide.md`、`chatbot-guide.md` 与 `project-rules.md` 硬约束，新增维度 1（分层架构）、4（Pydantic 2.x）、5（SQLAlchemy 2.0）、6（SQLite 优化）、9（异步与调度器）、10（事件总线）、16（Composition Root）、17（智能客服专项），扩展安全/性能/日志维度，自动化扫描 14 项。
