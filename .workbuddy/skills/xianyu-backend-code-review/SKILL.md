---
name: "xianyu-backend-code-review"
description: "闲鱼猎人后端代码（src/xianyu_hunter/ Python/FastAPI/SQLAlchemy .py）全面评审，覆盖分层架构/异步并发/数据库规约/安全/性能/错误处理/日志/配置/LLM治理等 40 维度。当用户要求审查/走查/评估后端 Python 代码时触发。纯前端 .tsx/.ts 改用 xianyu-frontend-code-review。"
version: "4.70.0"
updated: "2026-08-08"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# 闲鱼猎人后端代码审查

对 `src/xianyu_hunter/` 下 Python/FastAPI/SQLAlchemy 文件进行代码评审。**所有审查维度的详细规则、示例、反例已拆分到 `references/dimensions/` 目录，按需读取。**

## 版本演进索引

> 完整版本复盘详情见 [references/version-changelog.md](references/version-changelog.md)

| 版本 | 新增检查点 | 维度 |
|------|-----------|------|
| v4.70.0 | B-REVIEW-327~329 | 41 鉴权路径归一化 / 42 路由注册单一数据源 / 43 可选依赖完整性与降级契约 |
| v4.65.0 | B-REVIEW-316~326 | 38 架构层依赖强化 / 39 SQLAlchemy 写路径并发保护 / 40 搜索服务模板方法 |
| v4.64.0 | B-REVIEW-313~315 | 37 资源创建幂等性与前端状态闭环 |
| v4.63.0 | B-REVIEW-295~312 | 多用户安全审计 18 项 |
| v4.62.0 | B-REVIEW-291~294 | LLM 附加调用预算/超时/解析/一致性 |
| v4.61.0 | B-REVIEW-281~290 | 重构安全性审查 10 项 |
| v4.60.0 | B-REVIEW-275~280 | 缓存守卫三原则/状态机语义/跨层闭环 |
| v2.0~v4.59 | B-REVIEW-001~274 | 1-35 维度详见 references/version-changelog.md |

## 配置驱动

**所有评审规则、硬约束、项目规范通过 `config.yaml` 管理。** 首次使用从同目录 `config.example.yaml` 复制。

| 配置类 | 职责 |
|--------|------|
| `scope` | 评审范围（include_paths / exclude_paths / file_extensions） |
| `priority` | 优先级排序（severity_order / category_order） |
| `hard_constraints` | 硬约束规则（name / pattern / message / severity / auto_fix） |
| `checklist` | 评审检查清单 35+ 大类开关 |
| `project_conventions` | 项目专属规范（auth_whitelist / required_indexes / webview2_config 等） |
| `meta_rules_*` | meta-rules #25-51 落地配置节点 |
| `refactoring_safety` | 重构安全性配置（refactor_5step / scope_contract 等 10 子节点） |
| `report` / `verify` | 报告/验证配置 |

## 审查模式

| 模式 | 扫描范围 | 触发 |
|------|---------|------|
| 快速自检 | 仅阻塞级 | `pwsh scripts/auto-scan.ps1` |
| 增量审查 | `git diff --name-only` 变更文件 | 粘贴变更文件列表 |
| 指定文件审查 | 用户明确列出的文件 | 用户指定路径 |
| 片段评审 | 用户粘贴代码片段 | 无文件路径时仅输出建议 |
| 全量审查 | `src/xianyu_hunter/**/*.py` | 默认 |

---

## 审查维度索引

审查时根据命中维度读取对应的 `references/dimensions/` 文件，按需加载。

| # | 维度 | 触发条件 | 文件 |
|---|------|---------|------|
| 1 | 分层架构 | 路由/仓储/领域模型文件 | references/dimensions/01-layered-architecture.md |
| 2 | 命名规范 | 新增文件/类/函数/变量 | references/dimensions/02-naming-conventions.md |
| 3 | 类型注解 | Python .py 文件 | references/dimensions/03-type-annotations.md |
| 4 | Pydantic 2.x 模型 | Web 层请求/响应模型 | references/dimensions/04-pydantic-models.md |
| 5 | SQLAlchemy 2.0 规范 | DB 模型/仓储文件 | references/dimensions/05-sqlalchemy-standards.md |
| 6 | SQLite 优化与索引 | 仓储/init_db 文件 | references/dimensions/06-sqlite-index.md |
| 7 | 安全性评审 | 路由/认证/权限代码 | references/dimensions/07-security.md |
| 8 | 性能评审 | DB 查询/缓存/IO 操作 | references/dimensions/08-performance.md |
| 9 | 异步与调度器 | async/await/scheduler 文件 | references/dimensions/09-async-scheduler.md |
| 10 | 事件总线 | EventBus/消费者/发布者 | references/dimensions/10-event-bus.md |
| 11 | 错误处理 | try/except/error 文件 | references/dimensions/11-error-handling.md |
| 12 | 日志规约 | logger/logging 调用 | references/dimensions/12-logging-standards.md |
| 13 | 代码质量 | 所有 .py 文件 | references/dimensions/13-code-quality.md |
| 14 | 配置管理 | config/yaml 文件 | references/dimensions/14-config-management.md |
| 15 | 进程管理 | subprocess/进程启动 | references/dimensions/15-process-management.md |
| 16 | Composition Root | container.py | references/dimensions/16-composition-root.md |
| 17 | 智能客服专项 | chatbot/AI 调用 | references/dimensions/17-chatbot.md |
| 18 | Web 层规范 | web/routes/ 文件 | references/dimensions/18-web-layer.md |
| 19 | API 设计规范 | api_*.py 路由文件 | references/dimensions/19-api-design.md |
| 20 | 测试建议 | tests/ 目录文件 | references/dimensions/20-testing.md |
| 21 | 架构与分层 | 架构变更/new module | references/dimensions/21-architecture.md |
| 22 | 闲鱼项目规范 | 任何后端文件 | references/dimensions/22-project-specific.md |
| 23 | Git 操作规范 | .gitignore/submodule | references/dimensions/23-git-standards.md |
| 24 | 跨字段一致性 | 数据模型/仓储 | references/dimensions/24-cross-field-consistency.md |
| 25 | 状态管理与日志治理 | 状态流转/logging | references/dimensions/25-state-log-governance.md |
| 26 | 缓存/Schema 演进 | 缓存代码/migration | references/dimensions/26-cache-schema-evolution.md |
| 27 | 多路径数据源一致性 | 统计查询/聚合 | references/dimensions/27-data-source-consistency.md |
| 28 | LLM 端点能力派发 | LLM 调用/dispatcher | references/dimensions/28-llm-endpoint-dispatch.md |
| 29 | 失败原因链与闭环 | 错误追踪/root cause | references/dimensions/29-failure-chain-closure.md |
| 30 | 数据契约与时序 | 异步数据流/meta-rules #25-30 | references/dimensions/30-data-contract-timing.md |
| 31 | 业务关键字常量管理 | 业务常量/枚举 | references/dimensions/31-business-keywords.md |
| 32 | 状态恢复与日志 | 状态恢复/logging | references/dimensions/32-state-recovery.md |
| 33 | 修复前全链路扫描 | Bug 修复前 | references/dimensions/33-pre-fix-root-scan.md |
| 34 | 前后端字段契约 | 类型定义/Pydantic/DB | references/dimensions/34-field-contract.md |
| 35 | 列表聚合与状态联动 | 列表查询/状态联动 | references/dimensions/35-list-aggregation.md |
| 36 | 工程闭环元规范 | meta-rules #52-#55 | references/dimensions/36-engineering-closure.md |
| 37 | 资源创建幂等性 | 创建接口/状态闭环 | references/dimensions/37-idempotent-resource.md |
| 38 | 架构层依赖强化 | libs/路由/仓储 | references/dimensions/38-architecture-deps.md |
| 39 | SQLAlchemy 写路径并发保护 | Session/事务/多租户 | references/dimensions/39-sqlalchemy-write-concurrency.md |
| 40 | 搜索服务模板方法 | SearchService/钩子方法 | references/dimensions/40-search-service-template.md |
| 41 | 鉴权路径归一化 | 子路径部署、auth 中间件前缀归一化 | references/dimensions/41-auth-path-normalization.md |
| 42 | 路由注册单一数据源 | API_ROUTERS 表、双挂载一致性 | references/dimensions/42-route-registration-single-source.md |
| 43 | 可选依赖完整性与降级契约 | 可选模块降级、环境依赖完整性 | references/dimensions/43-optional-dependency-integrity.md |

额外评审要点（B-REVIEW-245~326，缓存守卫/状态机/多写入路径/编码规范/LLM 治理等）详见 [references/version-changelog.md](references/version-changelog.md) 的各版本复盘索引。

---

## 快速自检

**先执行此步骤进行快速自检：**

1. 硬约束扫描：`pwsh scripts/auto-scan.ps1`
2. 类型检查：`mypy src/xianyu_hunter/ --ignore-missing-imports`
3. 循环依赖：`pytest tests/ -k "import" --no-header -q`
4. 索引一致性：`grep -rn "Index(" src/xianyu_hunter/infra/` 与 `init_db()` 中 `_migrate_create_index` 双向对齐
5. 配置驱动：所有 TTL/阈值/路径从 `config.yaml` 读取，禁止模块级硬编码
6. datetime 时区：`grep -rn "\.now()\|utcnow" src/xianyu_hunter/ --include="*.py"` 全部 UTC + tzinfo 一致

## 审查流程（4 阶段流水线）

### 阶段 1：上下文加载

1. 加载 `config.yaml`（含 `coding_standards` 节点）
2. 识别任务类型——后端任务加载 `src/xianyu_hunter/` 文件
3. 加载对应 `coding-rules/` 主题文件（按需）
4. 确定评审范围：增量 (`git diff HEAD`) / 指定文件 / 片段 / 全量
5. 应用 `scope.include_paths` / `scope.exclude_paths` 过滤
6. 对每个文件：Read 完整内容 + Grep 关键依赖

### 阶段 2：分层扫描

按 `checklist` 配置的维度逐层扫描，分为 7 个子阶段：

**2.1 常规规则匹配**：按审查维度索引逐项检查，读取对应 `references/dimensions/` 文件

**2.2 配置驱动检查**：业务关键字硬编码 → 字段名大小写敏感 → 硬约束合规性 → 参数透传链路完整性

**2.3 硬约束合规性**：遍历 `hard_constraints.rules` Grep 扫描 → 标记违规

**2.4 跨层影响评估**：backend Pydantic/DB schema 变更 → 前端 types.ts 影响映射

**2.5 缓存守卫检查**：TTL 从 config 读取 / 空结果不可缓存 / 缓存写入守卫独立

**2.6 状态同步检查**：所有状态变更路径必须有 `sync_state_from_xxx()` 同步方法 / 基于实际存储内容校验

**2.7 重构安全性**：常量配置化 5 步法 / 作用域契约 / 导入名变更 checklist 等 10 项（详见 references/refactoring-safety-checks.md）

### 阶段 3：优先级分类

| 等级 | 判定标准 |
|------|---------|
| P0 阻塞 | 硬约束违规（安全漏洞/数据丢失/崩溃/认证失效/跨线程 sqlite 竞争） |
| P1 严重 | 逻辑错误/性能问题/状态不一致/异常吞掉/索引缺失/失败原因链断裂 |
| P2 改进 | 代码质量/可维护性/配置化/重复逻辑/类型注解缺失/硬编码常量 |
| P3 微调 | 风格/注释/命名优化/魔法数字提取 |

### 阶段 4：结果呈现

按 [templates/report-template.md](templates/report-template.md) 模板输出结构化报告。

---

## 评审范围判断

- 增量：`git diff HEAD --name-only` + 过滤 `.py`
- 指定文件：用户明确列出
- 片段：无文件路径仅输出建议
- **范围必须收紧**：不顺便审查旁边代码

## 失败恢复机制

1. 文件读取失败 → 记录跳过原因，继续
2. Grep 超时 → 缩小范围或跳过
3. 测试运行失败 → 输出错误，不阻止报告
4. 配置文件缺失 → 使用内置默认配置并提示创建 `config.yaml`
5. mypy 类型检查失败 → 记录但继续

## 审查判断标准

详细标准见 [references/judgment-criteria.md](references/judgment-criteria.md)。速查：
- P0 阻塞：硬约束违规
- P1 严重：逻辑/性能/一致性问题
- P2 改进：可维护性/配置化
- P3 微调：风格/注释/命名

## 安全注意事项

1. 报告中不含任何 token、密码等敏感信息
2. 检查 SQL 注入防护（LIKE 转义/表名校验/用户 ID 校验）
3. 检查 token 是否使用 `hmac.compare_digest()` 比较
4. 检查 `except: pass` 静默吞异常
5. 检查 Cookie/Token 跨层同步完整性

## 与现有工具的关系

- **xianyu-hunter-dev**：开发技能，开发完成后用本技能审查
- **xianyu-frontend-code-review**：前后端协同评审时配合使用
- **sonarqube-mcp**：SonarQube 修复后的二次审查
- **systematic-debugging**：纯调试场景使用，不使用本技能

---

## 版本历史

- **v4.69.0** (2026-07-31)：文档结构重构，SKILL.md 精简为维度索引 + 流程骨架，40 维度详情拆分到 references/dimensions/ 按需加载
- v4.65.0：架构层依赖强化/SQLAlchemy 写路径并发保护/搜索服务模板方法 (B-REVIEW-316~326)
- v4.64.0：资源创建幂等性与前端状态闭环 (B-REVIEW-313~315)
- v4.62.0：LLM 多调用治理 (B-REVIEW-291~294)
- v4.61.0：重构安全性审查 10 项 (B-REVIEW-281~290)
