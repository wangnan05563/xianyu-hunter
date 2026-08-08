# 编码规范索引（auto-generated）

> 本索引用于快速定位所有 step 编码规范的归档位置。
> 完整规范已按主题归档到 `assets/guides/coding-rules/` 目录下 20 个文件。
> 元规范（83 条通用规则）见 [meta-rules.md](../../../references/meta-rules.md)。

---

### 主题速查表（按主题加载）

| 主题文件 | 内容 | step 数 | step 范围 |
|---|---|---|---|
| [security.md](security.md) | 安全（token 校验/脱敏/SQL 注入/外部链接/数据库写入身份隔离） | 14 | 5-204 |
| [concurrency.md](concurrency.md) | 并发（asyncio/锁/超时/降级/async-await 静态检查/外部资源生命周期配对/批量启动容错/create_task 异常显式捕获/容器迭代快照） | 15 | 27-278 |
| [state-management.md](state-management.md) | 状态管理（一致性/同步/生命周期/状态恢复前置校验/长生命周期对象状态清理/状态机返回值语义校验） | 26 | 11-245 |
| [error-handling.md](error-handling.md) | 错误处理（粒度/重试/dump/原因传递/降级链日志合并/HTTP 状态码精细化/异常日志语义保留/超时异常用户友好语义） | 24 | 23-248 |
| [database.md](database.md) | 数据库（迁移/索引/SQLite/资源池基准/写入身份追溯） | 13 | 32-204 |
| [config-driven.md](config-driven.md) | 配置驱动（功能开关/全链路/阈值/字段契约/时间参数配置化/字段覆盖集合选择/缓存守卫） | 25 | 15-253 |
| [frontend-ui.md](frontend-ui.md) | 前端 UI（AntD/状态/三态/类型对齐/组件复用状态重置/SPA 渲染容错/UI预确认门控/React状态选型） | 41 | 8-260 |
| [testing.md](testing.md) | 测试（隔离/mock/fixture/Windows 编码/vitest 预检/tsconfig 排除） | 18 | 10-261 |
| [scheduler.md](scheduler.md) | 调度器（APScheduler/启动/状态可见/运行时开关对称性/cron 最小间隔校验/事件驱动启动解耦/主循环异常分层捕获） | 18 | 33-279 |
| [llm-ai.md](llm-ai.md) | LLM/AI（响应解析/能力派发/降级） | 4 | 72-114 |
| [browser-automation.md](browser-automation.md) | 浏览器自动化（Playwright/Cookie/子进程/CSS 选择器多级降级/外部资源活性真异步检测） | 18 | 36-276 |
| [multi-user-auth.md](multi-user-auth.md) | 多用户与认证安全（资源隔离/中间件/会话 token/覆盖决策） | 4 | 134-137 |
| [external-command-interaction.md](external-command-interaction.md) | 外部命令交互（长时交互式命令两阶段异步执行） | 6 | 223-228 |
| [external-service-integration.md](external-service-integration.md) | 外部服务集成 | 6 | 205-210 |
| [general-engineering.md](general-engineering.md) | 通用工程（注释/复用/现代化/死代码/事件过滤/重启验证/修复协议/字段契约/列表聚合/联动开关/precheck 结构化/配置兜底/多步骤进度编号日志/字段级写入策略/回调注入默认值） | 43 | 6-249 |
| [per-preset-credential.md](per-preset-credential.md) | 预设凭证管理 | 3 | 211-213 |
| [ai-service-config.md](ai-service-config.md) | AI 服务配置 | 2 | 214-215 |
| [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) | 多用户 Cookie 隔离（R1~R7） | 7 | 216-222 |
| [data-propagation.md](data-propagation.md) | 数据透传与职责分离（PROPAGATION/SNAPSHOT/FALLBACK-MERGE/MULTIUSER-CONSISTENCY） | 4 | 239-242 |
| [refactoring-checklist.md](refactoring-checklist.md) | 配置化重构 / 长任务执行 / 跨文件契约（5 步法/作用域契约/导入变更 checklist/PowerShell 长任务日志/资源过载容错/跨文件引用同步/配置访问统一入口/资源预检/弹性恢复配置化） | 9 | 262-270 |
| [encoding-integrity.md](encoding-integrity.md) | 源码文件编码完整性（中文→字面量? / GBK 误读乱码，与运行时 ENC 规范正交互补） | 1 | 280 |

---

### step 索引表（按 step 编号查找）

> 跨文件重复的 step 以 ` / ` 分隔多个主题文件；step 236~240 在 testing.md 与 frontend-ui.md/data-propagation.md 同时存在（编号冲突），两者均为有效规范。

| step | 标题 | 主题文件 |
|---|---|---|
| 5 | 功能实现约束 | [security.md](security.md) |
| 6 | 注释项检查 | [general-engineering.md](general-engineering.md) |
| 7 | 安全调用检查 | [security.md](security.md) |
| 8 | SonarQube 规则检查 | [frontend-ui.md](frontend-ui.md) |
| 9 | 代码修改后的编译→部署→重启流程 | [general-engineering.md](general-engineering.md) |
| 10 | 测试编写 | [testing.md](testing.md) |
| 11 | 状态管理一致性 | [state-management.md](state-management.md) / [general-engineering.md](general-engineering.md) |
| 12 | 容器适配原则 | [frontend-ui.md](frontend-ui.md) |
| 13 | 文件扩展名判断 | [frontend-ui.md](frontend-ui.md) |
| 14 | 多视图切换与 state 提升 | [frontend-ui.md](frontend-ui.md) |
| 15 | 动态资源映射分离 | [config-driven.md](config-driven.md) |
| 16 | 事件触发时机 | [frontend-ui.md](frontend-ui.md) / [general-engineering.md](general-engineering.md) |
| 17 | 字段覆盖策略（数据合并） | [config-driven.md](config-driven.md) / [general-engineering.md](general-engineering.md) |
| 18 | 幂等性设计 | [config-driven.md](config-driven.md) / [general-engineering.md](general-engineering.md) |
| 19 | 搜索接口标准化 | [config-driven.md](config-driven.md) / [general-engineering.md](general-engineering.md) |
| 20 | 注释与代码一致性 | [frontend-ui.md](frontend-ui.md) / [general-engineering.md](general-engineering.md) |
| 21 | 显式样式优于隐式间距 | [frontend-ui.md](frontend-ui.md) |
| 22 | IIFE 反模式禁止 | [frontend-ui.md](frontend-ui.md) / [general-engineering.md](general-engineering.md) |
| 23 | 会话失效处理与错误粒度区分 | [error-handling.md](error-handling.md) |
| 24 | UI 状态独立性原则 | [state-management.md](state-management.md) / [frontend-ui.md](frontend-ui.md) |
| 25 | 跨字段一致性校验 | [frontend-ui.md](frontend-ui.md) / [general-engineering.md](general-engineering.md) |
| 26 | 硬编码属性禁用 | [security.md](security.md) |
| 27 | 死代码与资源生命周期 | [concurrency.md](concurrency.md) / [general-engineering.md](general-engineering.md) |
| 28 | 跨组件状态同步 | [state-management.md](state-management.md) |
| 29 | 提示信息可操作性 | [security.md](security.md) / [general-engineering.md](general-engineering.md) |
| 30 | 加密升级退化策略模式 | [security.md](security.md) |
| 31 | 多配置文件发现模式 | [security.md](security.md) |
| 32 | 文件锁绕过模式（SQLite immutable） | [security.md](security.md) / [database.md](database.md) |
| 33 | 独立调度器隔离模式 | [concurrency.md](concurrency.md) / [scheduler.md](scheduler.md) |
| 34 | 配置驱动功能开关模式 | [concurrency.md](concurrency.md) / [config-driven.md](config-driven.md) |
| 35 | 降级链模式 | [concurrency.md](concurrency.md) |
| 36 | Chrome 136+ 限制适配模式 | [browser-automation.md](browser-automation.md) |
| 37 | Windows 测试环境 Mock 模式 | [testing.md](testing.md) |
| 38 | 第三方插件依赖预检模式 | [testing.md](testing.md) |
| 39 | 错误提示语义准确性 | [error-handling.md](error-handling.md) |
| 40 | 配置全链路生效验证 | [config-driven.md](config-driven.md) |
| 41 | 快速模式降级重试 | [general-engineering.md](general-engineering.md) |
| 42 | 硬编码阈值禁用 | [config-driven.md](config-driven.md) |
| 43 | 参数透传链路完整性 | [general-engineering.md](general-engineering.md) |
| 44 | 多源状态同步统一入口 | [state-management.md](state-management.md) |
| 45 | 状态条件区分"从未初始化"与"主动失效" | [state-management.md](state-management.md) |
| 46 | 浏览器内存兜底同步模式 | [state-management.md](state-management.md) |
| 47 | Update vs Upsert 语义区分 | [state-management.md](state-management.md) |
| 48 | 写后钩子（Post-Write Hook）规范 | [state-management.md](state-management.md) |
| 49 | 死代码检测与清理 | [state-management.md](state-management.md) |
| 50 | 异步操作整体超时保护 | [concurrency.md](concurrency.md) |
| 51 | 异步操作用户反馈三态 | [error-handling.md](error-handling.md) |
| 52 | 数据流转完整性 5 点追踪 | [general-engineering.md](general-engineering.md) |
| 53 | 过滤逻辑场景区分 | [testing.md](testing.md) |
| 54 | 复用既有模式原则 | [general-engineering.md](general-engineering.md) |
| 55 | AntD 主题 token 动态覆盖模式 | [frontend-ui.md](frontend-ui.md) |
| 56 | 孤岛模块检测规范 | [scheduler.md](scheduler.md) |
| 57 | 时间敏感场景的延迟/统计分离规范 | [scheduler.md](scheduler.md) |
| 58 | Orchestrator 便捷方法封装规范 | [scheduler.md](scheduler.md) |
| 59 | 辅助功能异常日志级别规范 | [scheduler.md](scheduler.md) |
| 60 | 状态机设计规范 | [scheduler.md](scheduler.md) |
| 61 | 资源生命周期规范 | [concurrency.md](concurrency.md) |
| 62 | 双链路一致性规范 | [scheduler.md](scheduler.md) / [general-engineering.md](general-engineering.md) |
| 63 | 并发安全规范 | [concurrency.md](concurrency.md) |
| 64 | Python 现代化规范 | [general-engineering.md](general-engineering.md) |
| 65 | 过滤结果可见性规范 | [frontend-ui.md](frontend-ui.md) |
| 66 | pytest 模块重复 import 隔离规范 | [testing.md](testing.md) |
| 67 | 日志库占位符一致性规范 | [general-engineering.md](general-engineering.md) |
| 68 | 测试 fixture 生产隔离与数据污染应急规范 | [testing.md](testing.md) |
| 69 | 配置项边界值校验 | [config-driven.md](config-driven.md) |
| 70 | DB 迁移失败处理 | [database.md](database.md) |
| 71 | 状态码语义精细化 | [security.md](security.md) |
| 72 | LLM 响应防御性三层级解析 | [llm-ai.md](llm-ai.md) |
| 73 | 调度器状态与 DB 同步 | [scheduler.md](scheduler.md) |
| 74 | 后台任务健康监控 | [concurrency.md](concurrency.md) |
| 75 | 文本数值提取模式 | [general-engineering.md](general-engineering.md) |
| 76 | 前后端错误码契约与超时识别 | [error-handling.md](error-handling.md) |
| 77 | 前端可重试错误集与退避策略 | [error-handling.md](error-handling.md) |
| 78 | 多层兜底链模式 | [error-handling.md](error-handling.md) / [browser-automation.md](browser-automation.md) |
| 79 | 失败诊断 dump 机制 | [error-handling.md](error-handling.md) / [browser-automation.md](browser-automation.md) |
| 80 | 关键路径计时埋点 | [browser-automation.md](browser-automation.md) |
| 81 | 凭证前置校验与并行采集 | [browser-automation.md](browser-automation.md) |
| 82 | 前端过滤与后端分类一致性验证 | [frontend-ui.md](frontend-ui.md) |
| 83 | 过滤+分页适配流程 | [frontend-ui.md](frontend-ui.md) |
| 84 | 空状态边界条件处理规范 | [frontend-ui.md](frontend-ui.md) |
| 85 | 系统行为派生与用户配置正交原则 | [frontend-ui.md](frontend-ui.md) |
| 86 | 浏览器自动化资源拦截粒度规范 | [browser-automation.md](browser-automation.md) |
| 87 | Cookie 层依赖关系信号匹配规范 | [state-management.md](state-management.md) |
| 88 | DEBUG 代码清理规范 | [browser-automation.md](browser-automation.md) |
| 89 | 子进程创建标志规范 | [browser-automation.md](browser-automation.md) |
| 90 | 配置驱动原则强化 | [config-driven.md](config-driven.md) |
| 91 | 缓存失效传播规范 | [state-management.md](state-management.md) |
| 92 | 状态判定需区分"未检测"与"已检测未失效" | [state-management.md](state-management.md) |
| 93 | SQLite DDL 修改列约束必须用表重建 + 事务安全 | [database.md](database.md) |
| 94 | 前后端字段契约对齐规范 | [general-engineering.md](general-engineering.md) |
| 95 | 长耗时异步请求 race condition 防护规范 | [concurrency.md](concurrency.md) / [frontend-ui.md](frontend-ui.md) |
| 96 | 除零兜底禁止凑数规范 | [error-handling.md](error-handling.md) |
| 97 | 重复错误处理抽取规范 | [error-handling.md](error-handling.md) |
| 98 | 元数据单源管理与跨端显示对齐规范 | [config-driven.md](config-driven.md) |
| 99 | 选择器仓库同步与单一数据源规范 | [browser-automation.md](browser-automation.md) |
| 100 | 外部系统文本特征集中管理规范 | [browser-automation.md](browser-automation.md) |
| 101 | 关键调度器启动状态可见性规范 | [scheduler.md](scheduler.md) |
| 102 | Pydantic 模型字段完整性规范 | [security.md](security.md) / [config-driven.md](config-driven.md) |
| 103 | 凭据同步桥接规范（yaml→keyring） | [security.md](security.md) |
| 104 | 脱敏策略场景区分规范 | [security.md](security.md) |
| 105 | 第三方平台 API 兼容性规范 | [security.md](security.md) |
| 106 | 事件发布完整性规范 | [general-engineering.md](general-engineering.md) |
| 107 | 启动钩子完整性检查规范 | [state-management.md](state-management.md) / [scheduler.md](scheduler.md) |
| 108 | 任务历史持久化三层状态保护规范 | [state-management.md](state-management.md) / [scheduler.md](scheduler.md) |
| 109 | 业务自增计数器 DB MAX 初始化规范 | [database.md](database.md) / [scheduler.md](scheduler.md) |
| 110 | APScheduler interval 触发器首次执行控制规范 | [scheduler.md](scheduler.md) |
| 111 | CLI 默认参数友好性规范 | [scheduler.md](scheduler.md) |
| 112 | 能力驱动派发规范（capability-driven dispatch） | [llm-ai.md](llm-ai.md) |
| 113 | 共享工具函数规范（避免散落内联判断） | [llm-ai.md](llm-ai.md) |
| 114 | 静默降级预检规范（不支持能力 → 友好降级） | [llm-ai.md](llm-ai.md) |
| 115 | 用户偏好类 UI 状态持久化强制复用 usePersistentState 规范 | [frontend-ui.md](frontend-ui.md) |
| 116 | 数据库迁移块独立容错与关键路径异常可见性规范 | [database.md](database.md) |
| 117 | API 更新接口三态语义规范 | [config-driven.md](config-driven.md) |
| 118 | 字段全链路消费规范 | [config-driven.md](config-driven.md) |
| 119 | 共享单例局部变量规范 | [config-driven.md](config-driven.md) |
| 120 | 跨前后端类型对齐规范 | [config-driven.md](config-driven.md) |
| 121 | 前端错误处理规范 | [error-handling.md](error-handling.md) / [frontend-ui.md](frontend-ui.md) |
| 122 | 默认值操作符规范 | [frontend-ui.md](frontend-ui.md) |
| 123 | 失败原因传递链规范（reason propagation chain） | [error-handling.md](error-handling.md) |
| 124 | 数据完整性预检规范（pre-call completeness check） | [error-handling.md](error-handling.md) |
| 125 | 合并写入 vs 覆盖写入决策规范（merge vs overwrite write strategy） | [security.md](security.md) |
| 126 | 文案常量集中管理规范（error message constant centralization） | [error-handling.md](error-handling.md) |
| 127 | 修改-验证-部署闭环规范（edit-verify-deploy closed loop） | [error-handling.md](error-handling.md) |
| 128 | 测试 mock 同步规范（test mock synchronization） | [testing.md](testing.md) |
| 129 | 业务关键字常量集中管理规范 | [config-driven.md](config-driven.md) |
| 130 | 事件类型过滤精确匹配规范 | [general-engineering.md](general-engineering.md) |
| 131 | 前后端字段名大小写敏感检查规范 | [config-driven.md](config-driven.md) |
| 132 | 服务重启验证清单规范 | [general-engineering.md](general-engineering.md) |
| 133 | Windows 终端编码与 Shell 语法兼容规范 | [testing.md](testing.md) |
| 134 | 多用户资源隔离规范 | [multi-user-auth.md](multi-user-auth.md) |
| 135 | 认证中间件多路校验规范 | [multi-user-auth.md](multi-user-auth.md) |
| 136 | 会话 token 安全管理规范 | [multi-user-auth.md](multi-user-auth.md) |
| 137 | 快照与实时数据覆盖决策规范 | [multi-user-auth.md](multi-user-auth.md) |
| 138 | DATETIME-TZ-01 时区一致性三步检查法 | [database.md](database.md) |
| 139 | DATETIME-TZ-02 原生 SQL 返回值防御 | [database.md](database.md) |
| 140 | MIGRATE-01 迁移步骤独立性原则 | [database.md](database.md) |
| 141 | NULL-01 NOT NULL 字段防御原则 | [database.md](database.md) |
| 142 | QUERY-01 数据查询条件精确性原则 | [database.md](database.md) |
| 143 | ENUM-01 状态值枚举一致性原则 | [database.md](database.md) |
| 144 | ATTRIB-01 错误归因精细化原则 | [error-handling.md](error-handling.md) |
| 145 | EXCEPT-01 异常传播原则 | [error-handling.md](error-handling.md) |
| 146 | ERROR-01 错误消息透传原则 | [error-handling.md](error-handling.md) |
| 147 | RETRY-01 重试策略配置化原则 | [error-handling.md](error-handling.md) |
| 148 | LOG-NOISE-01 已知场景日志降噪原则 | [error-handling.md](error-handling.md) |
| 149 | CIRCUIT-01 熔断器持久化对称性原则 | [state-management.md](state-management.md) |
| 150 | STATE-01 状态切换原子性原则 | [state-management.md](state-management.md) |
| 151 | CONSISTENCY-01 多源失效判定一致性原则 | [state-management.md](state-management.md) |
| 152 | FALLBACK-01 缺失数据回退策略 | [state-management.md](state-management.md) |
| 153 | SYNC-01 多源状态同步标记机制 | [state-management.md](state-management.md) |
| 154 | RACE-01 异步竞态防护原则 | [state-management.md](state-management.md) |
| 155 | PARAM-CHAIN-01 参数传递链完整性原则 | [config-driven.md](config-driven.md) |
| 156 | KEYWORD-01 业务关键词集中管理原则 | [config-driven.md](config-driven.md) |
| 157 | PERSIST-01 用户可配置开关持久化原则 | [config-driven.md](config-driven.md) |
| 158 | CREDENTIAL-01 凭证多存储同步原则 | [config-driven.md](config-driven.md) |
| 159 | EFFECT-01 useEffect 副作用清理与依赖完整性规范 | [frontend-ui.md](frontend-ui.md) |
| 160 | SSE-01 SSE 事件流生命周期管理规范 | [frontend-ui.md](frontend-ui.md) |
| 161 | THEME-01 AntD 主题 token 单一数据源规范 | [frontend-ui.md](frontend-ui.md) |
| 162 | LAYOUT-01 布局响应式与最小宽度规范 | [frontend-ui.md](frontend-ui.md) |
| 163 | REGISTRY-01 注册表单一数据源规范 | [frontend-ui.md](frontend-ui.md) |
| 164 | FILTER-02 过滤条件与分页状态同步规范 | [frontend-ui.md](frontend-ui.md) |
| 165 | UI-SEMANTICS-01 UI 语义与行为一致性规范 | [frontend-ui.md](frontend-ui.md) |
| 166 | SOURCE-01 前端数据源单一可信源规范 | [frontend-ui.md](frontend-ui.md) |
| 167 | MOCK-01 测试 Mock 数据集中管理与字段完整性规范 | [testing.md](testing.md) |
| 168 | COOKIE-01 Cookie 完整保留与导入规范 | [browser-automation.md](browser-automation.md) |
| 169 | PARSER-01 解析器多层兜底规范 | [browser-automation.md](browser-automation.md) |
| 170 | KEYWORD-01 爬虫关键词集中管理规范 | [browser-automation.md](browser-automation.md) |
| 171 | NAMING-01 命名一致性与歧义消除规范 | [general-engineering.md](general-engineering.md) |
| 172 | CONTRACT-01 前后端契约对齐规范 | [general-engineering.md](general-engineering.md) |
| 173 | SEMANTICS-01 语义一致性规范 | [general-engineering.md](general-engineering.md) |
| 174 | FILTER-01 过滤逻辑精确匹配规范 | [general-engineering.md](general-engineering.md) |
| 175 | DRY-01 重复代码抽取规范 | [general-engineering.md](general-engineering.md) |
| 176 | ENCODING-01 编码一致性规范 | [general-engineering.md](general-engineering.md) |
| 177 | DATACLASS-01 数据类使用规范 | [general-engineering.md](general-engineering.md) |
| 178 | STARTUP-01 启动钩子完整性规范 | [general-engineering.md](general-engineering.md) |
| 179 | RESUME-01 状态恢复前置校验原则 | [state-management.md](state-management.md) |
| 180 | LOGMERGE-01 降级链日志合并原则 | [error-handling.md](error-handling.md) |
| 181 | REGISTRATION-01 注册式资源三件套契约原则 | [frontend-ui.md](frontend-ui.md) |
| 182 | ROOTCAUSE-01 修复前全链路根因扫描协议原则 | [general-engineering.md](general-engineering.md) |
| 183 | CONTRACT-SSO-01 前后端字段契约单一可信源原则 | [general-engineering.md](general-engineering.md) |
| 184 | GLOBAL-AGG-01 全局聚合任务级过滤原则 | [general-engineering.md](general-engineering.md) |
| 185 | CROSS-INJECT-01 列表交叉数据批量注入原则 | [general-engineering.md](general-engineering.md) |
| 186 | LINKED-SWITCH-01 多字段联动开关范式原则 | [general-engineering.md](general-engineering.md) |
| 187 | PRECHECK-STRUCT-01 状态恢复前置校验结构化响应原则 | [general-engineering.md](general-engineering.md) |
| 188 | CONFIG-FALLBACK-01 配置化阈值兜底范式原则 | [general-engineering.md](general-engineering.md) |
| 189 | PARAM-CHAIN-EXEC-01 参数链闭环验证规范 | [config-driven.md](config-driven.md) |
| 190 | MODE-VERTICAL-CHAIN-01 业务模式纵向链路一致性规范 | [state-management.md](state-management.md) |
| 191 | PARSER-FALLBACK-01 外部页面解析容错规范 | [browser-automation.md](browser-automation.md) |
| 192 | MOCK-SYNC-01 mock 同步与边界精确性规范 | [testing.md](testing.md) |
| 193 | FILTER-TRANS-01 过滤结果透明化 UI 规范 | [frontend-ui.md](frontend-ui.md) |
| 194 | SCHEDULER-RUNTIME-TOGGLE-SYMMETRY 调度器运行时开关对称性 | [scheduler.md](scheduler.md) |
| 195 | CRON-MIN-INTERVAL-CHECK 用户输入时间表达式校验 | [scheduler.md](scheduler.md) |
| 196 | TIME-PARAM-CONFIG-DRIVEN 时间参数配置化 | [config-driven.md](config-driven.md) |
| 197 | LIFECYCLE-RESOURCE-CLEANUP 长生命周期对象状态清理 | [state-management.md](state-management.md) |
| 198 | ASYNC-AWAIT-SYNC-CHECK async/await 同步性静态检查 | [concurrency.md](concurrency.md) |
| 199 | RESOURCE-POOL-BENCHMARK 资源池配置性能基准与决策 | [database.md](database.md) |
| 200 | HTTP-STATUS-CODE-MAPPING HTTP 状态码精细化映射表 | [error-handling.md](error-handling.md) |
| 201 | CSS-SELECTOR-FALLBACK CSS 选择器多级降级策略 | [browser-automation.md](browser-automation.md) |
| 202 | EXCEPTION-LOG-SEMANTIC 异常日志语义保留规范 | [error-handling.md](error-handling.md) |
| 203 | EXTERNAL-RESOURCE-LIFECYCLE 外部资源生命周期配对管理 | [concurrency.md](concurrency.md) |
| 204 | DB-WRITE-IDENTITY-TRACE 数据库写入函数身份追溯与类型安全 | [database.md](database.md) / [security.md](security.md) |
| 205 | CLI 命令参数验证 | [external-service-integration.md](external-service-integration.md) |
| 206 | CLI 输出解析多格式兼容 | [external-service-integration.md](external-service-integration.md) |
| 207 | 外部服务前置依赖检查 | [external-service-integration.md](external-service-integration.md) |
| 208 | Provider 插件化架构 | [external-service-integration.md](external-service-integration.md) |
| 209 | 通知集成使用 EventBus 模式 | [external-service-integration.md](external-service-integration.md) |
| 210 | Provider 前端 UI 状态管理 | [external-service-integration.md](external-service-integration.md) |
| 211 | 预设凭证独立槽位规范 | [per-preset-credential.md](per-preset-credential.md) |
| 212 | 配置变更响应回显规范 | [per-preset-credential.md](per-preset-credential.md) |
| 213 | 预设 ID 字面量类型规范 | [per-preset-credential.md](per-preset-credential.md) |
| 214 | Model Name Case-Sensitivity Standard | [ai-service-config.md](ai-service-config.md) |
| 215 | Config Input Persistence and Reflection Standard | [ai-service-config.md](ai-service-config.md) |
| 216 | 多用户 Cookie 隔离传播规范（R1） | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) |
| 217 | Cookie 注入浏览器状态验证规范（R4） | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) |
| 218 | _m_h5_tk 刷新用户隔离规范（R5） | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) |
| 219 | Cookie 层状态同步缓存清除规范（R3） | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) |
| 220 | 实时搜索 Cookie 健康检查 user_id 透传规范（R2） | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) |
| 221 | 测试 Cookie 注入前过滤规范（R6） | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) |
| 222 | user_id 文件路径安全构造规范（R7） | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) |
| 223 | 长时交互式命令识别与两阶段拆分 | [external-command-interaction.md](external-command-interaction.md) |
| 224 | 子进程非阻塞启动与后台 stdout 读取 | [external-command-interaction.md](external-command-interaction.md) |
| 225 | 完成标志多路径检测 | [external-command-interaction.md](external-command-interaction.md) |
| 226 | 跨请求状态管理与全局单例生命周期 | [external-command-interaction.md](external-command-interaction.md) |
| 227 | 子进程清理协议（terminate→wait→kill） | [external-command-interaction.md](external-command-interaction.md) |
| 228 | 前端轮询四态契约与资源清理 | [external-command-interaction.md](external-command-interaction.md) |
| 229 | 多级自愈模式规范（token 刷新→cookie 重注入→放弃） | [state-management.md](state-management.md) |
| 230 | 熔断标志与自动重试协调规范（重试前显式重置标志） | [state-management.md](state-management.md) |
| 231 | 诊断日志模式规范（关键路径结构化诊断日志） | [error-handling.md](error-handling.md) |
| 232 | 预检前置规范（批次级预检 + 登录后健康探测） | [general-engineering.md](general-engineering.md) |
| 233 | async 阻塞调用超时保护 | [browser-automation.md](browser-automation.md) |
| 234 | 子进程心跳与阶段超时协同 | [concurrency.md](concurrency.md) |
| 235 | 跨代码块一致性检查（experimental） | [browser-automation.md](browser-automation.md) |
| 236 | 操作项分级保留规范（meta-rule #83 落地）/ monkeypatch 模块级 from-import 绑定覆盖规范 | [frontend-ui.md](frontend-ui.md) / [testing.md](testing.md) |
| 237 | 多视图模式一致性规范（meta-rule #83 落地）/ 同步/异步方法测试调用匹配规范 | [frontend-ui.md](frontend-ui.md) / [testing.md](testing.md) |
| 238 | UI 水平空间溢出诊断与横向滚动容错规范（meta-rule #83 落地）/ 属性名重构与对外序列化字段名分离规范 | [frontend-ui.md](frontend-ui.md) / [testing.md](testing.md) |
| 239 | 跨层数据透传完整性规范（PROPAGATION-01）/ FastAPI 端点签名变更测试同步规范 | [data-propagation.md](data-propagation.md) / [testing.md](testing.md) |
| 240 | 快照与最新值职责分离规范（SNAPSHOT-01）/ 软删除数据分类隔离规范（NULL vs 不存在外键） | [data-propagation.md](data-propagation.md) / [testing.md](testing.md) |
| 241 | Fallback 路径数据合并完整性规范（FALLBACK-MERGE-01） | [data-propagation.md](data-propagation.md) |
| 242 | 多用户隔离字段一致性规范（MULTIUSER-CONSISTENCY-01） | [data-propagation.md](data-propagation.md) |
| 245 | 状态机返回值语义校验规范（STATE-MACHINE-RETURN-01） | [state-management.md](state-management.md) |
| 247 | 多步骤关键路径进度编号日志规范（STEP-PROGRESS-LOG-01） | [general-engineering.md](general-engineering.md) |
| 248 | 超时异常用户友好语义规范（TIMEOUT-ERROR-SEMANTICS-01） / 数据写入策略字段级决策规范（FIELD-STRATEGY-01） | [error-handling.md](error-handling.md) / [general-engineering.md](general-engineering.md) |
| 249 | React 组件复用状态同步重置规范（COMPONENT-REUSE-STATE-RESET-01） / 回调注入默认值模式规范（CALLBACK-INJECTION-01） | [frontend-ui.md](frontend-ui.md) / [general-engineering.md](general-engineering.md) |
| 250 | 字段覆盖集合选择标准规范（OVERWRITE-SET-SELECTION-01） | [config-driven.md](config-driven.md) |
| 253 | 缓存守卫三原则（CACHE-GUARD-3RULES） | [config-driven.md](config-driven.md) |
| 254 | 全局 ErrorBoundary 包裹规范（SPA-GLOBAL-ERROR-BOUNDARY-01） | [frontend-ui.md](frontend-ui.md) |
| 255 | 懒加载 chunk 失效重试规范（LAZY-CHUNK-RETRY-01） | [frontend-ui.md](frontend-ui.md) |
| 256 | 路由级 ErrorBoundary 隔离规范（ROUTE-ERROR-ISOLATION-01） | [frontend-ui.md](frontend-ui.md) |
| 257 | API 响应防御性兜底规范（API-DEFENSIVE-FALLBACK-01） | [frontend-ui.md](frontend-ui.md) |
| 258 | HTTP 401 拦截器防抖规范（HTTP-401-DEBOUNCE-01） | [frontend-ui.md](frontend-ui.md) |
| 259 | UI视觉变更预确认门控规范（UI-PREVIEW-GATE-01） / Vitest 环境预检规范（VITEST-ENV-PRECHECK-01） | [frontend-ui.md](frontend-ui.md) / [testing.md](testing.md) |
| 260 | React状态选型判断矩阵规范（STATE-SELECTION-01） / tsconfig 排除测试文件规范（TSCONFIG-EXCLUDE-TESTS-01） | [frontend-ui.md](frontend-ui.md) / [testing.md](testing.md) |
| 261 | antd v5 中文按钮自动空格兼容规范（ANTD-CN-BUTTON-SPACE-01） | [testing.md](testing.md) |
| 262 | 配置化重构 5 步法（CONFIG-REFACTOR-5STEP-01） | [refactoring-checklist.md](refactoring-checklist.md) |
| 263 | 作用域契约校验规范（SCOPE-CONTRACT-01） | [refactoring-checklist.md](refactoring-checklist.md) |
| 264 | 导入名称变更 checklist 规范（IMPORT-NAME-CHANGE-01） | [refactoring-checklist.md](refactoring-checklist.md) |
| 265 | PowerShell 长任务日志输出规范（POWERSHELL-LONG-TASK-LOG-01） | [refactoring-checklist.md](refactoring-checklist.md) |
| 266 | 系统资源过载容错规范（RESOURCE-OVERLOAD-FALLBACK-01） | [refactoring-checklist.md](refactoring-checklist.md) |
| 267 | 跨文件引用同步校验规范（CROSS-FILE-REF-SYNC-01） | [refactoring-checklist.md](refactoring-checklist.md) |
| 268 | 配置访问统一入口规范（CONFIG-ACCESS-UNIFIED-01） | [refactoring-checklist.md](refactoring-checklist.md) |
| 269 | 长任务执行资源预检规范（LONG-TASK-RESOURCE-PRECHECK-01） | [refactoring-checklist.md](refactoring-checklist.md) |
| 270 | 弹性恢复机制配置化规范（RESILIENCE-RECOVERY-CONFIG-01） | [refactoring-checklist.md](refactoring-checklist.md) |
| 271 | useSearch Hook 防抖与并发保护规范（USE-SEARCH-DEBOUNCE-01） | [frontend-ui.md](frontend-ui.md) |
| 272 | useSearchHistory 持久化与 Hooks 依赖顺序规范（USE-SEARCH-HISTORY-01） | [frontend-ui.md](frontend-ui.md) |
| 273 | 类型注解契约对齐规范（TYPE-ANNOTATION-CONTRACT-ALIGNMENT-01） | [type-annotation-contract.md](type-annotation-contract.md) |
| 274 | 事件驱动基础设施启动解耦规范（EVENT-BUS-STARTUP-DECOUPLING-01） | [scheduler.md](scheduler.md) |
| 275 | 批量启动容错隔离规范（BATCH-START-FAULT-ISOLATION-01） | [concurrency.md](concurrency.md) |
| 276 | 外部资源活性真异步检测规范（EXTERNAL-RESOURCE-ASYNC-LIVENESS-01） | [browser-automation.md](browser-automation.md) |
| 277 | create_task 异常显式捕获规范（CREATE-TASK-EXCEPTION-VISIBILITY-01） | [concurrency.md](concurrency.md) |
| 278 | 容器迭代快照规范（CONTAINER-ITERATION-SNAPSHOT-01） | [concurrency.md](concurrency.md) |
| 279 | 调度器主循环异常分层捕获规范（SCHEDULER-LOOP-LAYERED-EXCEPTION-01） | [scheduler.md](scheduler.md) |
| 280 | 源码文件编码完整性规范（SOURCE-FILE-ENCODING-INTEGRITY-01） | [encoding-integrity.md](encoding-integrity.md) |

---

### 版本演进索引（按版本号查找）

> 保留自 v4.42 起的版本演进记录；v4.42 之前的 step（5~210）归档在各主题文件中，不再单列版本。

| step | 标题 | 主题文件 | 级别 | 版本 |
|---|---|---|---|---|
| step 211 | 预设凭证独立槽位规范 | [per-preset-credential.md](per-preset-credential.md) | 强制 | v4.42 |
| step 212 | 配置变更响应回显规范 | [per-preset-credential.md](per-preset-credential.md) | 强制 | v4.42 |
| step 213 | 预设 ID 字面量类型规范 | [per-preset-credential.md](per-preset-credential.md) | 强制 | v4.42 |
| 214 | Model Name Case-Sensitivity Standard | [ai-service-config.md](ai-service-config.md) | CRITICAL | v4.43 |
| 215 | Config Input Persistence and Reflection Standard | [ai-service-config.md](ai-service-config.md) | CRITICAL | v4.43 |
| step 216 | 多用户 Cookie 隔离传播规范 | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) | 强制 | v4.45 |
| step 217 | Cookie 注入浏览器状态验证规范 | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) | 强制 | v4.45 |
| step 218 | _m_h5_tk 刷新用户隔离规范 | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) | 强制 | v4.45 |
| step 219 | Cookie 层状态同步缓存清除规范 | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) | 强制 | v4.45 |
| step 220 | 实时搜索 Cookie 健康检查 user_id 透传规范 | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) | 强制 | v4.45 |
| step 221 | 测试 Cookie 注入前过滤规范 | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) | 强制 | v4.45 |
| step 222 | user_id 文件路径安全构造规范 | [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md) | 强制 | v4.45 |
| step 223 | 长时交互式命令识别与两阶段拆分 | [external-command-interaction.md](external-command-interaction.md) | 强制 | v4.46 |
| step 224 | 子进程非阻塞启动与后台 stdout 读取 | [external-command-interaction.md](external-command-interaction.md) | 强制 | v4.46 |
| step 225 | 完成标志多路径检测 | [external-command-interaction.md](external-command-interaction.md) | 强制 | v4.46 |
| step 226 | 跨请求状态管理与全局单例生命周期 | [external-command-interaction.md](external-command-interaction.md) | 强制 | v4.46 |
| step 227 | 子进程清理协议（terminate→wait→kill） | [external-command-interaction.md](external-command-interaction.md) | 强制 | v4.46 |
| step 228 | 前端轮询四态契约与资源清理 | [external-command-interaction.md](external-command-interaction.md) | 强制 | v4.46 |
| step 229 | 多级自愈模式规范（token 刷新→cookie 重注入→放弃） | [state-management.md](state-management.md) | 强制 | v4.47 |
| step 230 | 熔断标志与自动重试协调规范（重试前显式重置标志） | [state-management.md](state-management.md) | 强制 | v4.47 |
| step 231 | 诊断日志模式规范（关键路径结构化诊断日志） | [error-handling.md](error-handling.md) | 强制 | v4.47 |
| step 232 | 预检前置规范（批次级预检 + 登录后健康探测） | [general-engineering.md](general-engineering.md) | 强制 | v4.47 |
| step 233 | async 阻塞调用超时保护 | [browser-automation.md](browser-automation.md) | 强制 | v4.48.0 |
| step 234 | 子进程心跳与阶段超时协同 | [concurrency.md](concurrency.md) | 强制 | v4.48.0 |
| step 235 | 跨代码块一致性检查（experimental） | [browser-automation.md](browser-automation.md) | 推荐 | v4.48.0 |
| step 236 | 操作项分级保留规范（meta-rule #83 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.49.0 |
| step 237 | 多视图模式一致性规范（meta-rule #83 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.49.0 |
| step 238 | UI 水平空间溢出诊断与横向滚动容错规范（meta-rule #83 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.49.0 |
| step 239 | 跨层数据透传完整性规范（PROPAGATION-01） | [data-propagation.md](data-propagation.md) | 强制 | v4.50.0 |
| step 240 | 快照与最新值职责分离规范（SNAPSHOT-01） | [data-propagation.md](data-propagation.md) | 强制 | v4.50.0 |
| step 241 | Fallback 路径数据合并完整性规范（FALLBACK-MERGE-01） | [data-propagation.md](data-propagation.md) | 强制 | v4.50.0 |
| step 242 | 多用户隔离字段一致性规范（MULTIUSER-CONSISTENCY-01） | [data-propagation.md](data-propagation.md) | 强制 | v4.50.0 |
| step 243 | Cookie-Token 一致性保障规范（COOKIE-TOKEN-CONSISTENCY-01，meta-rule #84 落地） | [state-management.md](state-management.md) | 强制 | v4.51.0 |
| step 244 | 续期闭环完整性规范（RENEWAL-LOOP-COMPLETENESS-01，meta-rule #84 落地） | [state-management.md](state-management.md) | 强制 | v4.51.0 |
| step 245 | 日志占位符格式规范（LOGURU-PLACEHOLDER-01，meta-rule #84 落地） | [error-handling.md](error-handling.md) | 强制 | v4.51.0 |
| step 246 | 静默异常禁止规范（SILENT-EXCEPTION-BAN-01，meta-rule #84 落地） | [error-handling.md](error-handling.md) | 强制 | v4.51.0 |
| step 247 | 多步骤关键路径进度编号日志规范（STEP-PROGRESS-LOG-01，meta-rule #85 落地） | [general-engineering.md](general-engineering.md) | 强制 | v4.52.0 |
| step 248 | 超时异常用户友好语义规范（TIMEOUT-ERROR-SEMANTICS-01，meta-rule #85 落地） | [error-handling.md](error-handling.md) | 强制 | v4.52.0 |
| step 249 | React 组件复用状态同步重置规范（COMPONENT-REUSE-STATE-RESET-01，meta-rule #85 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.52.0 |
| step 250 | 字段覆盖集合选择标准规范（OVERWRITE-SET-SELECTION-01，meta-rule #85 落地） | [config-driven.md](config-driven.md) | 强制 | v4.52.0 |
| step 253 | 登录成功路径副作用调度规范（LOGIN-SIDE-EFFECT-AUTOMATION-01，meta-rule #89 落地） | [concurrency.md](concurrency.md) | 强制 | v4.56.0 |
| step 254 | 全局 ErrorBoundary 包裹规范（SPA-GLOBAL-ERROR-BOUNDARY-01，meta-rule #95 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.61.0 |
| step 255 | 懒加载 chunk 失效重试规范（LAZY-CHUNK-RETRY-01，meta-rule #95 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.61.0 |
| step 256 | 路由级 ErrorBoundary 隔离规范（ROUTE-ERROR-ISOLATION-01，meta-rule #95 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.61.0 |
| step 257 | API 响应防御性兜底规范（API-DEFENSIVE-FALLBACK-01，meta-rule #95 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.61.0 |
| step 258 | HTTP 401 拦截器防抖规范（HTTP-401-DEBOUNCE-01，meta-rule #95 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.61.0 |
| step 259 | Vitest 环境预检规范（VITEST-ENV-PRECHECK-01，meta-rule #95 落地） | [testing.md](testing.md) | 强制 | v4.61.0 |
| step 260 | tsconfig 排除测试文件规范（TSCONFIG-EXCLUDE-TESTS-01，meta-rule #95 落地） | [testing.md](testing.md) | 强制 | v4.61.0 |
| step 261 | antd v5 中文按钮自动空格兼容规范（ANTD-CN-BUTTON-SPACE-01，meta-rule #95 落地） | [testing.md](testing.md) | 强制 | v4.61.0 |
| step 262 | 配置化重构 5 步法（CONFIG-REFACTOR-5STEP-01） | [refactoring-checklist.md](refactoring-checklist.md) | 强制 | v4.63.0 |
| step 263 | 作用域契约校验规范（SCOPE-CONTRACT-01） | [refactoring-checklist.md](refactoring-checklist.md) | 强制 | v4.63.0 |
| step 264 | 导入名称变更 checklist 规范（IMPORT-NAME-CHANGE-01） | [refactoring-checklist.md](refactoring-checklist.md) | 强制 | v4.63.0 |
| step 265 | PowerShell 长任务日志输出规范（POWERSHELL-LONG-TASK-LOG-01） | [refactoring-checklist.md](refactoring-checklist.md) | 强制 | v4.63.0 |
| step 266 | 系统资源过载容错规范（RESOURCE-OVERLOAD-FALLBACK-01） | [refactoring-checklist.md](refactoring-checklist.md) | 强制 | v4.63.0 |
| step 267 | 跨文件引用同步校验规范（CROSS-FILE-REF-SYNC-01） | [refactoring-checklist.md](refactoring-checklist.md) | 强制 | v4.63.0 |
| step 268 | 配置访问统一入口规范（CONFIG-ACCESS-UNIFIED-01） | [refactoring-checklist.md](refactoring-checklist.md) | 强制 | v4.63.0 |
| step 269 | 长任务执行资源预检规范（LONG-TASK-RESOURCE-PRECHECK-01） | [refactoring-checklist.md](refactoring-checklist.md) | 强制 | v4.63.0 |
| step 270 | 弹性恢复机制配置化规范（RESILIENCE-RECOVERY-CONFIG-01） | [refactoring-checklist.md](refactoring-checklist.md) | 强制 | v4.63.0 |
| step 253 | 缓存守卫三原则（CACHE-GUARD-3RULES，meta-rule #104 落地） | [config-driven.md](config-driven.md) | 强制 | v4.62.0 |
| step 248 | 数据写入策略字段级决策规范（FIELD-STRATEGY-01，meta-rule #105 落地） | [general-engineering.md](general-engineering.md) | 强制 | v4.62.0 |
| step 249 | 回调注入默认值模式规范（CALLBACK-INJECTION-01，meta-rule #106 落地） | [general-engineering.md](general-engineering.md) | 强制 | v4.62.0 |
| step 259 | UI视觉变更预确认门控规范（UI-PREVIEW-GATE-01，meta-rule #103 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.62.0 |
| step 260 | React状态选型判断矩阵规范（STATE-SELECTION-01，meta-rule #107 落地） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.62.0 |
| step 245 | 状态机返回值语义校验规范（STATE-MACHINE-RETURN-01，meta-rule #109 落地） | [state-management.md](state-management.md) | 强制 | v4.62.0 |
| step 271 | useSearch Hook 防抖与并发保护规范（USE-SEARCH-DEBOUNCE-01） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.64.0 |
| step 272 | useSearchHistory 持久化与 Hooks 依赖顺序规范（USE-SEARCH-HISTORY-01） | [frontend-ui.md](frontend-ui.md) | 强制 | v4.64.0 |
| step 273 | 类型注解契约对齐规范（TYPE-ANNOTATION-CONTRACT-ALIGNMENT-01，meta-rule #110 落地 experimental） | [type-annotation-contract.md](type-annotation-contract.md) | experimental | v4.67.0 |
| step 274 | 事件驱动基础设施启动解耦规范（EVENT-BUS-STARTUP-DECOUPLING-01，meta-rule #111 落地 experimental） | [scheduler.md](scheduler.md) | experimental | v4.68.0 |
| step 275 | 批量启动容错隔离规范（BATCH-START-FAULT-ISOLATION-01） | [concurrency.md](concurrency.md) | 强制 | v4.69.0 |
| step 276 | 外部资源活性真异步检测规范（EXTERNAL-RESOURCE-ASYNC-LIVENESS-01） | [browser-automation.md](browser-automation.md) | 强制 | v4.69.0 |
| step 277 | create_task 异常显式捕获规范（CREATE-TASK-EXCEPTION-VISIBILITY-01） | [concurrency.md](concurrency.md) | 强制 | v4.69.0 |
| step 278 | 容器迭代快照规范（CONTAINER-ITERATION-SNAPSHOT-01） | [concurrency.md](concurrency.md) | 强制 | v4.69.0 |
| step 279 | 调度器主循环异常分层捕获规范（SCHEDULER-LOOP-LAYERED-EXCEPTION-01） | [scheduler.md](scheduler.md) | 强制 | v4.69.0 |
| step 280 | 源码文件编码完整性规范（SOURCE-FILE-ENCODING-INTEGRITY-01） | [encoding-integrity.md](encoding-integrity.md) | 强制 | v4.70.0 |

### v4.64.0 升级记录（2026-07-25 第九轮复盘）

> 本次为已有 step 的内容升级，不新增 step 编号（除 step 271/272 外）。升级点已并入原 step 章节，此处仅做版本溯源。

| step | 升级内容 | 主题文件 | 版本 |
|---|---|---|---|
| 16 | 事件触发时机 — 追加 PASSED 事件"业务最终步骤"锚点 + 钉钉通知时机 Bug 教训 + 配置驱动节点 | [general-engineering.md](general-engineering.md) | v4.64.0 |
| 19 | 搜索接口标准化 — 升级为 SearchService 模板方法模式（4 钩子/SQL 分页/慢查询埋点/响应结构/文件锚点） | [general-engineering.md](general-engineering.md) / [config-driven.md](config-driven.md) | v4.64.0 |
| 133 | Windows 终端编码 — 追加 PowerShell 管道吞输出陷阱 + 测试路由一致性 + FAQ 403 Bug 教训 | [testing.md](testing.md) | v4.64.0 |
