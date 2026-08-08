# 元规范速查索引（Meta-Rules Index）

> 完整内容见 [../meta-rules.md](../meta-rules.md)。本索引提供按类别分组的一览表和快速定位。
> 元规范总计 111 条（#1-#111），其中 #1-#20 为通用规范，#21-#111 为专项工作流模板规范。

## 通用规范（#1-#20）

| # | 规则 | 关键词 | 概述 |
|---|------|--------|------|
| 1 | 配置驱动原则 | config-driven | 所有参数从 config.yaml 读取，禁止硬编码 |
| 2 | 适用/不适用场景说明 | scope | 每条规范必须说明适用和不适用场景 |
| 3 | 历史教训归档 | lesson-archive | 教训统一归档到 version-history.md，step 只保留引用 |
| 4 | 修复模式代码归档 | code-archive | 代码示例归档到 coding-rules/，step 只保留规则一行 |
| 5 | 判断信号优先 grep | grep-first | 所有判断信号必须可用 grep 验证 |
| 6 | 复用优先级 | reuse | 配置变量 > 内置默认值 > 封装工具 > 自定义实现 |
| 7 | 状态分类识别 | state-classify | 区分无状态/有状态/需同步三类 |
| 8 | 错误粒度区分 | error-granularity | 区分系统错误/业务错误/用户错误 |
| 9 | 日志级别规范 | log-level | DEBUG/INFO/WARNING/ERROR 级别选择标准 |
| 10 | 异步操作规范 | async | asyncio 正确使用模式与反模式 |
| 11 | 安全调用检查 | security | 外部输入校验、SQL 注入防护、时序攻击防护 |
| 12 | 状态机设计规范 | state-machine | 状态枚举、转换规则、恢复机制 |
| 13 | 测试隔离规范 | test-isolation | mock 隔离、数据库隔离、异步测试 |
| 14 | Python 现代化规范 | python-modern | 3.10+ 语法（X\|None、match-case、TypeAlias） |
| 15 | 前端三态反馈规范 | frontend-ui-states | loading/empty/error 三态处理 |
| 16 | 配置全链路生效验证 | config-verify | 配置变更后验证全链路生效 |
| 17 | 修改-验证-部署闭环 | modify-verify-deploy | 修改后必须验证 → 部署 → 再验证 |
| 18 | 跨前后端协同修复 | cross-stack-fix | 前端变更同步后端，后端变更同步前端 |
| 19 | 死代码检测与清理 | dead-code | grep 检测未使用变量/函数/导入 |
| 20 | 失败诊断 dump 机制 | failure-dump | 关键异常必须 dump 上下文用于诊断 |

## 数据与时序（#21-#35）

| # | 规则 | 关键词 | 概述 |
|---|------|--------|------|
| 21 | 错误处理决策树 | error-decision-tree | try/except/.catch 统一决策流程 |
| 22 | 批处理熔断模板 | batch-circuit-breaker | 长任务断点续传四要素 |
| 23 | 资源生命周期管理 | resource-lifecycle | 浏览器/订阅/连接生命周期六步法 |
| 24 | 跨组件/跨源状态同步 | cross-source-sync | 多源/多链路状态同步七步法 |
| 25 | 批量处理四要素 | batch-4-elements | 断路器+进度持久化+续传+日志对称 |
| 26 | 关键路径异常保留完整 traceback | traceback-preserve | 关键路径异常全保留，不清洗堆栈 |
| 27 | datetime 统一时区策略 | datetime-tz | naive↔aware 混用防护，优先 naive |
| 28 | 跨进程/跨组件状态同步六步法 | cross-process-sync | 同步六步：读→匹配→合并→写→校验→通知 |
| 29 | 前端错误按 error_code 分支 | error-code-branch | 禁止 substring 判断错误类型 |
| 30 | 业务关键字常量集中管理 | keyword-constants | 业务字符串提取为常量，跨端一致 |
| 31 | 状态恢复前置校验 | resume-precheck | pause→resume 根因消除与状态校验 |
| 32 | 多阶段降级链日志合并 | degrade-log-merge | 降级链日志合并为一条含阶段信息 |
| 33 | 注册式资源三件套契约 | registration-3-piece | 菜单+路由+页面注册一致性 |
| 34 | 修复前全链路根因扫描协议 | root-cause-scan | Bug 修复前 Grep 全链路影响 |
| 35 | 前后端字段契约单一可信源 | field-contract-source | 字段类型定义单一权威源 |

## 工程治理（#36-#55）

| # | 规则 | 关键词 |
|---|------|--------|
| 36 | 规范沉淀门槛 | governance-threshold | 防过度规范化，≥3 次同类问题才沉淀 |
| 37 | 规范退化机制 | governance-deprecate | 防规范膨胀，定期审查移除无用规范 |
| 38 | 全局聚合任务级过滤 | global-agg-filter | 全局统计 + 任务级过滤双层架构 |
| 39 | 列表交叉数据批量注入 | list-cross-inject | 批量关联查询替代 N+1 |
| 40 | 多字段联动开关范式 | multi-field-switch | 多字段布尔联动的一致性保障 |
| 41 | 状态恢复前置校验结构化响应 | resume-structured | pause→resume 返回结构化校验结果 |
| 42 | 配置化阈值兜底范式 | threshold-fallback | 阈值配置缺失时的安全兜底策略 |
| 43 | 事件多发布点字段对齐 | event-emit-align | 同一事件多发布点字段一致性 |
| 44 | 前端路由三重注册同步 | route-triple-reg | 菜单注册/路由配置/权限注册三处同步 |
| 45 | 外部回链 query string 保留 | query-retain | 跨页跳转保留查询参数 |
| 46 | 测试同步责任原则 | test-sync | 功能变更者负责同步更新测试 |
| 47 | 外部依赖隔离测试可重复性 | ext-dep-isolation | 外部依赖测试必须可隔离重放 |
| 48 | 调度器运行时开关对称性 | scheduler-toggle | 启停开关必须对称：启动 A→B，关闭 B→A |
| 49 | 时间参数配置化 | time-config | 所有时间参数从 config 读取 |
| 50 | 长生命周期对象状态清理 | lifecycle-cleanup | 长时间运行对象的状态重置机制 |
| 51 | 用户输入时间表达式校验 | cron-validation | cron/时间表达式合法性校验 |
| 52 | 参数链闭环验证 | param-chain | 从参数传入到最终使用全链路验证 |
| 53 | 业务模式纵向链路一致性 | mode-vertical-chain | 同一业务模式前后端全链路一致 |
| 54 | 外部页面解析容错 | parser-fallback | 页面解析多级降级链 |
| 55 | mock 同步与边界精确性 | mock-sync | mock 数据必须与真实接口保持同步 |

## 前端 UI 与异步（#56-#69）

| # | 规则 | 关键词 |
|---|------|--------|
| 56 | 过滤结果透明化 UI | filter-transparency | 过滤后显示过滤条件摘要 |
| 57 | async/await 同步性静态检查 | async-sync-check | async 函数内部同步调用检测 |
| 58 | 资源池配置性能基准 | resource-pool-benchmark | 资源池大小基于基准测试配置 |
| 59 | HTTP 状态码精细化映射 | http-status-map | 状态码到业务错误的精确映射表 |
| 60 | CSS 选择器多级降级 | css-selector-fallback | 选择器从特定到通用多级回退 |
| 61 | 异常日志语义保留 | exception-log-semantic | 异常日志保留语义信息不丢失 |
| 62 | 外部资源生命周期配对 | ext-resource-pair | 创建/销毁必须配对管理 |
| 63 | 数据库写入函数身份追溯 | db-write-trace | 写入函数必须记录调用者身份 |
| 64 | URL↔状态同步失败回退 | url-state-fallback | URL 参数与 UI 状态双向同步失败回退 |
| 65 | Service Worker 缓存版本同步 | sw-cache-version | SW 缓存版本号与构建版本同步 |
| 66 | HTTP 状态码语义分层 | http-status-layer | 避免状态码语义冲突 |
| 67 | 移动端检测多重 fallback | mobile-detect-fallback | UA/屏幕尺寸/触摸支持三重检测 |
| 68 | 响应式断点统一规范 | responsive-breakpoint | 全局统一断点值 |
| 69 | 设备仿真模式验证清单 | device-emulation | 设备仿真测试必须验证的项 |

## Cookie 与多用户（#70-#78）

| # | 规则 | 关键词 |
|---|------|--------|
| 70 | 快捷预设独立 API Key | preset-apikey | 每预设独立 API Key 存储 |
| 71 | 配置变更前后端契约 | config-mutation-contract | 配置变更前端→后端契约必须同步 |
| 72 | 多用户 Cookie 隔离传播 | multi-user-cookie | user_id 在所有 Cookie 操作中传播 |
| 73 | Cookie 注入必须验证浏览器状态 | cookie-inject-verify | 注入后必须验证浏览器实际状态 |
| 74 | _m_h5_tk 刷新按用户隔离 | m5tk-refresh-isolation | token 刷新按 user_id 维度隔离 |
| 75 | Cookie 层状态同步清除缓存 | cookie-sync-invalidate | 状态同步后必须清除相关缓存 |
| 76 | 实时搜索 Cookie 健康检查传 user_id | live-search-healthcheck | 健康检查传递 user_id |
| 77 | Cookie 测试数据过滤在注入前 | cookie-test-filter | 测试数据在注入前过滤，不污染业务 |
| 78 | Cookie 文件路径 Path 多参数构造 | cookie-path-safe | 路径构造使用 Path 而非字符串拼接 |

## 外部命令与超时（#79-#83）

| # | 规则 | 关键词 |
|---|------|--------|
| 79 | 长时交互式外部命令两阶段异步 | long-cmd-2phase | 启动→交互→结果分离 |
| 80 | async 阻塞调用超时保护 | async-timeout | 所有阻塞调用必须 asyncio.wait_for |
| 81 | 子进程心跳与阶段超时协同 | subprocess-heartbeat | 心跳 + 阶段超时双重保护 |
| 82 | 跨代码块一致性检查 | cross-block-check | 同一数据不同代码块取值一致性 |
| 83 | UI 操作项分级保留多视图一致性 | ui-action-tier | 操作项按优先级分级保留 |

## Cookie/Token/状态（#84-#92）

| # | 规则 | 关键词 |
|---|------|--------|
| 84 | Cookie-Token 状态分离 | cookie-token-separate | 身份 Cookie 与签名 Token 分离管理 |
| 85 | 关键路径可观测性 | critical-path-observability | 多步骤编号日志+超时友好语义 |
| 86 | 调度器状态机恢复路径校验 | scheduler-state-recovery | pause/resume 闭环与返回值检查 |
| 87 | 配置字段五层链路覆盖 | config-field-coverage | DB/get_config/update_config/types.ts/Config.tsx |
| 88 | 跨层数据契约同步 | cross-layer-contract | 空值语义区分 + React 组件复用状态重置 |
| 89 | 登录副作用自动化 | login-side-effect | fire-and-forget 调度，失败安全 |
| 90 | 回退构造保留关联键 | fallback-preserve-key | 回退构造时必须注入下游依赖键 |
| 91 | 时间窗口查询全量回退 | time-window-fallback | 窗口无数据时自动全量回退 |
| 92 | PowerShell 外部命令显式后缀 | powershell-suffix | curl→curl.exe，wget→wget.exe |

## 性能与缓存（#93-#94）

| # | 规则 | 关键词 |
|---|------|--------|
| 93 | 性能优化量化验证 | perf-quantify | 优化前后必须量化对比 |
| 94 | 缓存 TTL 合理性校验 | cache-ttl-check | TTL 设置必须基于业务需求和时间分布 |

## SPA 与 UI 存储（#95-#98）

| # | 规则 | 关键词 |
|---|------|--------|
| 95 | SPA 渲染容错体系 | spa-render-resilience | ErrorBoundary/lazyRetry/路由级隔离 |
| 96 | 多写入路径状态一致性 | multi-write-consistency | 多写入路径最终状态一致 |
| 97 | UI 偏好持久化检查 | ui-preference-persist | localStorage 键名命名空间隔离 |
| 98 | storage 错误处理检查 | storage-error-handle | 隐私模式/Safari 无痕写入失败处理 |

## Cookie 状态异常（#99-#102）

| # | 规则 | 关键词 |
|---|------|--------|
| 99 | Cookie 状态异常多写预防 | cookie-state-anomaly | 多写入路径下状态异常检测 |
| 100 | 页面刷新 Cookie 有效但系统无效修复 | cookie-refresh-mismatch | 页面刷新后状态不一致的检查与修复 |
| 101 | Cookie 状态持久化三重修复 | cookie-triple-fix | 异常+持久+CDP 三重修复 |
| 102 | 多写路径+UI持久化+storage 三合一 | multi-write-persist-triple | 三项检查合并执行 |

## 架构质量（#103-#111）

| # | 规则 | 关键词 |
|---|------|--------|
| 103 | UI 视觉变更预确认门控 | ui-preview-gate | UI 变更前截图预确认 |
| 104 | 缓存守卫三原则 | cache-guard | TTL配置化+空结果不缓存+守卫独立 |
| 105 | 数据写入策略字段级决策 | field-strategy | _ALWAYS_OVERWRITE vs _coalesce 决策 |
| 106 | 回调注入默认值模式 | callback-injection | 回调默认安全实现+覆盖守卫 |
| 107 | React 状态选型判断矩阵 | state-selection | useState/useReducer/Zustand/Context 选型 |
| 108 | 跨层闭环验证 | cross-layer-closed-loop | 写入→读取全链路闭环校验 |
| 109 | 状态机返回值语义校验 | state-machine-return | return True/False 语义与调用方对齐 |
| 110 | 类型注解契约对齐 | type-annotation-contract | 三方类型定义一致性检查 |
| 111 | 事件驱动基础设施启动解耦 | event-bus-startup | EventBus 启动独立于业务任务 |
