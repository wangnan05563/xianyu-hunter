---
name: "xianyu-auto-testing"
description: "闲鱼猎人前端 SPA/PWA/移动端测试工作流。当用户报告白屏/路由不跳转/PWA缓存问题，或要求全面功能测试/Cookie自愈/Playwright超时/状态机/LLM治理等回归测试时触发。配置驱动，30+模式按需加载。"
version: "2.9.0"
---

# Xianyu Auto Testing

闲鱼猎人前端 SPA 路由、PWA 与移动端全面功能测试工作流。**所有模式的详细操作步骤已拆分到 `references/` 目录下的独立文件，按需读取。**

## 模式速查表

根据用户输入的关键词匹配模式，然后读取对应 references 文件执行。共享步骤（环境准备/浏览器初始化）见下文"共享步骤"章节。

| 模式 | 名称 | 触发关键词 | 配置节点 | references 文件 |
|------|------|-----------|----------|----------------|
| A | 诊断模式 | 白屏/路由不跳转/PWA/移动端地址跳不过去 | `decision_tree` | references/diagnostic-output.md |
| B | 全面测试 | 全面功能测试/遍历所有菜单/点击所有按钮/生成测试报告 | `test_execution + routes_discovery` | references/page-traversal.md |
| C | Cookie 自愈 | Cookie自愈/token刷新/重试机制/登录后立即失效 | `backend_cookie_healing` | references/backend-cookie-healing-test.md |
| D | Playwright 超时 | async阻塞调用超时/心跳协同/context.cookies()阻塞 | `async_timeout_test` | references/playwright-timeout-test.md |
| E | 大规模pytest | 运行全部测试/跑一下pytest/测试卡住/批量修复 | `test_execution (TR1~TR6)` | references/test-failure-classification.md |
| F | UI布局溢出 | 操作列溢出/Table横向溢出/多视图一致性 | `ui_layout_overflow_test` | references/ui-layout-overflow-test.md |
| G | 数据透传 | 跨层字段透传/多用户数据丢失/user_id传递 | `data_propagation_integrity_test` | references/data-propagation-test.md |
| H | 快照一致性 | 快照/过滤/fallback合并/刷新后商品消失 | `snapshot_consistency_test` | references/snapshot-consistency-test.md |
| I | Cookie-Token分离 | 非法请求/token不匹配/FAIL_SYS_ILLEGAL_ACCESS | `cookie_token_consistency_test` | references/cookie-token-consistency-test.md |
| J | 关键路径可观测性 | 多步骤日志/超时语义/组件状态重置/字段覆盖 | `critical_path_observability_test` | references/state-sync-testing.md |
| K | DB脏值诊断 | 乱码/问号/方块/garbled/mojibake | `mode_k_db_dirty_value_diagnosis_test` | references/db-dirty-value-test.md |
| L | 状态机死锁 | pause/resume闭环/should_pause返回值/任务永久卡死 | `mode_l_state_machine_deadlock_test` | references/state-machine-deadlock-test.md |
| M | 跨层数据契约 | 覆盖策略集合/组件复用状态重置/空值语义 | `mode_m_cross_layer_contract_test` | references/cross-layer-contract-test.md |
| N | 登录副作用 | 登录入口helper/fire-and-forget/失败安全 | `mode_n` | references/login-side-effect-test.md |
| O | 回退构造关联键 | 关联键注入/时间窗口回退/PowerShell外部命令 | `fallback_key_consistency_test` | references/fallback-key-consistency-test.md |
| P | 评估去重 | eval去重/部分唯一索引/upsert逻辑 | `mode_p_eval_dedup_test` | references/eval-dedup-test.md |
| Q | 构建产物 | 工具链版本/PATH优先级/构建产物完整性 | `mode_q_build_product_test` | references/build-product-test.md |
| R | 性能优化 | 缓存命中/SSE进度/性能回归 | `mode_r_performance_test` | references/performance-optimization-test.md |
| S | UI偏好持久化 | 主题/布局偏好/localStorage一致性 | `mode_s_ui_persistence_test` | references/ui-persistence-test.md |
| T | 多写入路径 | 多写入路径状态一致性/双写冲突 | `mode_t_multi_write_path_test` | references/multi-write-path-test.md |
| U | SPA白屏 | 白屏/ErrorBoundary/lazyRetry/路由级错误隔离 | `mode_u_spa_white_screen_test` | references/spa-white-screen-test.md |
| V | UI视觉回归 | 图标替换/主题修改/布局调整/视觉一致性 | `mode_v_visual_regression_test` | references/visual-regression-test.md |
| W | 缓存守卫 | TTL配置化/空结果缓存/缓存守卫独立性 | `mode_w_cache_guard_test` | references/cache-testing.md |
| X | 状态机完整性 | 状态枚举/转换验证/异常恢复/返回值语义 | `mode_x_state_machine_test` | references/state-machine-test.md |
| Y | 前端韧性 | Markdown代码块/SSE类型校验/定时器清理/a11y | `mode_y_frontend_resilience_test` | 读取 `xianyu-frontend-code-review/references/frontend-resilience-checks.md` |
| Z | LLM治理 | 附加调用预算/独立超时/响应解析/多调用一致性 | `mode_z_llm_governance_test` | 读取 `xianyu-backend-code-review/references/llm-governance-checks.md`（跨技能引用） |
| AA | 资源创建幂等 | 后端幂等/OperationResult契约/async handler三分支 | `mode_aa_idempotent_resource_creation_test` | references/idempotent-resource-creation-test.md |
| AB | 搜索服务模板 | SearchService抽象基类/钩子方法/慢查询日志 | `mode_ab_search_service_template_test` | references/search-service-template-test.md |
| AC | 搜索Hook | useSearch防抖/useSearchHistory持久化/并发保护 | `mode_ac_search_hook_test` | references/search-hook-test.md |
| AD | AI服务测试连接 | 预设切换/API Key关联/Embedding状态/外部链接安全 | `mode_ad_ai_service_test_connection_test` | references/ai-service-test-connection-test.md |
| AE | 类型注解契约 | 三方对齐/复杂返回结构/单元测试完整结构断言 | `type_annotation_contract_test` | references/type-annotation-contract-test.md |
| AF | 事件驱动启动解联 | EventBus启动/消费者循环/启动顺序/幂等防护 | `event_bus_startup_decoupling_test` | references/event-bus-startup-test.md |
| AJ | 健康检查端到端 | 双数据源一致性/health endpoint/check-update | `mode_aj_health_check_e2e_test` | references/health-check-e2e-test.md |
| AK | 源码编码完整性 | 源码中文变?/源码乱码/GBK误读/mojibake/编码损坏/问号 | `mode_ak_source_file_encoding_integrity` | references/source-file-encoding-integrity-test.md |
| AL | 子路径部署一致性 | 子路径/域名模式部署、API前缀、双挂载、PWA规则、导航链接前缀 | `subpath_deployment` | references/subpath-deployment-test.md |

## 共享步骤

以下步骤为多个模式共用，已拆分为独立文件：

| 步骤 | 说明 | references 文件 |
|------|------|----------------|
| 环境准备 | 检查 web 进程/构建产物/HTTP 响应 | references/env-check.md |
| 网络验证 | 验证 HTTP 可达性与响应码 | references/network-verify.md |
| 路由核查 | 检查 SPA 路由配置与 BaseName | references/route-check.md |
| PWA 核查 | 检查 Service Worker 与缓存策略 | references/pwa-check.md |
| 浏览器初始化 | 设置设备预设/导航入口/认证 Cookie | references/browser-verify.md |
| 清缓存指导 | 用户侧缓存清理步骤 | references/cache-cleanup-guide.md |
| 按钮交互 | 按钮遍历/点击/状态验证 | references/button-interaction.md |
| 回归测试 | 修复后回归验证 | references/regression-test.md |
| 响应式测试 | 多设备/UA 检测/断点适配 | references/responsive-test.md |
| 测试报告 | 报告格式与输出模板 | references/test-report.md |
| 三档机制 | 测试档位选择/资源容错/降级 | references/tiered-test-verification.md |

## 不适用场景

- 后端 API 接口测试（应改用 API 测试智能体）
- SSR 应用（Next.js / Nuxt.js）路由机制不同
- 非 SPA 多页应用
- 非 PWA 应用（无 service worker）
- 非 React 项目（Vue / Angular）
- 性能压测 / 安全测试 / 跨浏览器兼容性测试
- 纯后端单元测试（应改用 pytest 直接执行）
- 数据库 schema 迁移测试（应改用专门的迁移测试）
- 纯视觉设计评审（非代码变更）
- 非缓存类性能测试
- 无状态流转的纯 CRUD

## 关键设计原则

1. **配置驱动**：所有可参数化项集中在 `config.yaml`，SKILL.md 和 references 只引用变量。修改项目路径/端口/正则/命令时只需改 config.yaml。
2. **决策树分发**：诊断模式使用决策树（DT-01 ~ DT-11）按顺序检查，命中即停。
3. **references 子文档**：每个阶段的详细操作步骤在 `references/` 子文档中，按需 Read。
4. **memory 优先**：排查前先查项目 memory，历史诊断能直接指向根因，避免重复排查。
5. **模式独立**：所有模式互相独立，不需要按顺序执行。每种模式有自己的触发条件和配置段。
6. **关键文件监控**：每种模式定义了 `key_files` 列表，当这些文件被修改后自动触发对应模式的回归验证。
7. **关联规范可追溯**：每种模式在 config.yaml 中声明了对应的 meta_rule / 代码审查标准，确保测试与编码规范保持一致。
8. **测试验证三档机制**：所有涉及测试验证的模式在执行测试前必须按此机制选择验证档位（Tier 1/2/3），根据系统资源降级。

## 测试验证三档机制

> 跨模式通用机制，详细信息见 `references/tiered-test-verification.md`
> 配置节点：`config.yaml#tiered_test_verification` + `config.yaml#long_task_logging` + `config.yaml#system_resource_monitoring`

| 档位 | 名称 | 适用改动类型 | 验证内容 |
|------|------|-------------|----------|
| Tier 1 | 完整测试集 | refactor（重构） | `pytest tests/ + tsc --noEmit` 全量验证 |
| Tier 2 | 直接 import 测试 | bugfix（Bug 修复） | 改动文件的核心功能 import 验证 |
| Tier 3 | 改动文件 5/5 验证 | feature（新增功能） | 改动文件的语法+导入链路验证 |

| 降级触发条件 | 阈值 | 降级到 |
|--------------|------|--------|
| 高 CPU | > `cpu.threshold_percent`（默认 90%）持续 `duration_sec`（默认 30 秒） | Tier 2 |
| 高 IO 延迟 | > `disk_io.threshold_latency_sec`（默认 5 秒） | Tier 2 |
| 可用内存不足 | < `memory.threshold_available_mb`（默认 512 MB） | Tier 2 |
| Tier 2 失败 | 任一文件 import 失败 | Tier 3 |

**长任务日志输出规范（B1）**：
- 禁用：`| Select-Object -Last N` / `Tee-Object` / `| More`（sink cmdlet）
- 首选：`Start-Process -RedirectStandardOutput`（绕过管道缓冲）
- 次选：`Out-File -Encoding utf8`（避免 CLIXML）

## 修复点测试覆盖检查清单

每个 Bug 修复或功能新增后，必须按此清单验证测试覆盖度。

| 检查项 | 说明 | 验证方法 |
|--------|------|---------|
| 改动点有对应测试 | 每个代码改动点必须有对应测试用例 | 对照 diff 逐行检查测试覆盖 |
| 正常路径覆盖 | 正常输入下的预期行为有测试 | 构造正常输入断言预期输出 |
| 边界值覆盖 | 边界条件（空列表/0条/最大值/阈值附近）有测试 | 构造边界值断言不抛异常 |
| 异常路径覆盖 | 异常输入（无效数据/配置缺失/超时）有测试 | 构造异常输入断言优雅降级 |
| 向后兼容 | 改动不破坏现有功能 | 运行全量测试无回归 |
| 常量变更有生效验证 | 修改配置常量（如 TTL）后验证实际生效 | 读取配置断言值与预期一致 |
| 新增守卫有边界测试 | 新增 if 守卫测试 true/false 两分支 | 构造满足/不满足条件的输入 |

## 配置加载

**所有参数从 `config.yaml` 读取，禁止在流程中硬编码任何路径、端口、选择器、超时秒数、正则、命令。**

读取 `config.yaml` 时重点关注以下配置段（按需）：
- `web_process`：端口、进程名检查
- `build`：构建命令、产物路径
- `spa`：子路径部署配置（`basename` 路由前缀、`api_prefix` API 前缀、移动端路径）——**模式 AL 必须读取，禁止硬编码 `/xianyu/`**
- `browser_automation`：浏览器工具类型、设备预设
- `test_execution`：测试执行参数
- `routes_discovery`：页面路由列表、按钮选择器
- `memory_search`：memory 搜索配置
- `decision_tree`：DT-01 ~ DT-11 决策节点
- `callback_for_llm`：工具调用审批策略（必读，确保工具调用能执行）

## 失败处理

- **环境检查失败**：按各模式的决策树 `fix` 字段执行修复后重试
- **测试失败**：按模式 E（`references/test-failure-classification.md`）分类 → 并行修复 → 验证
- **浏览器不可用**：检查 `web_process` 进程状态，必要时重启服务
- **构建产物不存在**：重新执行 `build.command`
- **PWA SW 死锁**：按 `references/pwa-check.md` 清缓存指导操作

## 版本历史

- **v2.9.0** (2026-08-08)：新增模式 AL（子路径部署一致性验证），`config.yaml` 新增 `spa.basename`/`spa.api_prefix` 配置节点，强化"禁止硬编码前缀、全部参数走配置"的泛化约束
- **v2.8.0** (2026-07-31)：文档结构重构，SKILL.md 精简为模式速查表 + 设计原则 + 共享步骤索引，详细内容全部拆分到 references/ 按需加载
- **v2.7.0**：新增模式 AD/AE/AF/AJ
- **v2.3.0**：新增模式 AA：资源创建幂等性与状态闭环回归测试
- **v2.2.0**：新增模式 Y/Z：前端韧性回归测试 + LLM 治理回归测试
- **v2.1.0**：新增测试验证三档机制（B1/B2/C3/D1/D2 复盘规范），新增 references/tiered-test-verification.md
- **v2.0.0**：新增模式 V/W/X：UI视觉回归测试、缓存守卫验证测试、状态机完整性测试
