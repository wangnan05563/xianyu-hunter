# 代码治理与质量
> 包含元规范 #18 - #108

## 18. 跨前后端协同修复

跨端数据流问题必须前后端协同修复：

1. 检查前端调用 → 后端端点 → 数据源全链路
2. 禁止只改一边
3. 同步检查相关端点是否也有相同问题
4. 修复时同步清理死代码（只 set 不 read 的 state / 只 import 不调用的函数）

## 19. 死代码检测与清理

每次大版本（v4.x → v4.x+1）时主动检测：

1. `git log -p --all -S "<function_name>"` 查看历史变更
2. `grep -rn "<function_name>" src/ tests/` 确认无调用方
3. 在 PR/Commit 描述中标注"删除死代码 X"

**修复模式**：
- 找到调用方：恢复调用路径
- 改写为入口函数：将死代码改写为"统一同步入口"
- 直接删除：无任何依赖时

## 20. 失败诊断 dump 机制

关键选择器/数据提取失败时：

1. 自动 dump `page.content()` 到 `logs/<场景>_<id>_<timestamp>.html`
2. `logger.warning` 记录 dump 路径
3. dump 用 `try/except` 包裹不阻塞主流程
4. dump 是「事后取证」不是「在线恢复」
5. 禁止依赖 dump 结果做运行时决策
6. 禁止 dump 敏感数据（cookie/auth header）

---

# 工作流元规范（Workflow Meta-Rules，21-24）

> 以下 4 条元规范从「四维度复盘方法论」提炼，定义了 4 类高频工作流的通用判断逻辑。详细配置节点与适用/不适用场景见 [`docs/standards/四维度复盘方法论与历史教训集成.md`](../../../../docs/standards/四维度复盘方法论与历史教训集成.md)。
>
> 命名空间与配置驱动：所有参数（critical_path_patterns / failure_threshold / resource_holder_patterns / single_source_of_truth）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 33. 注册式资源三件套契约 🆕v4.32

> 与 B-REVIEW-159（backend 注册完整性）/ F-REVIEW-117（frontend 注册完整性）对应。

任何"用户可点击/可导航"的功能入口必须保证 5 层齐备：菜单注册 → 路由注册 → 页面文件 → API wrapper → 后端 endpoint。任一层缺失视为 CRITICAL 缺陷。

1. **5 层契约模型**：L1 `config/menu_registry.yaml`（path/component/label/i18n_key）+ L2 `frontend/src/App.tsx`（`<Route path>` + lazy import）+ L3 `frontend/src/pages/<域>/index.tsx`（export default 组件）+ L4 `frontend/src/api/<域>.ts`（导出 xxxApi 对象）+ L5 `src/xianyu_hunter/web/routes/api_<域>.py`（APIRouter + include_router）
2. **自动化校验**：`python scripts/check_registration.py` 必须在 CI + pre-commit hook 中执行，退出码非 0 即 CRITICAL
3. **结构化输出**：校验结果同时输出表格（开发者读）+ JSON（CI 解析）
4. **豁免机制**：实验性 feature 用 `exemption_list` 临时豁免，必填 `expires` 过期时间
5. **配置驱动**：5 层路径、校验命令、豁免清单均从 `config.yaml#frontend_registration_completeness` 读取，禁止硬编码

**关键约束**：
- 菜单注册了 path 但 App.tsx 无对应 `<Route>` → 视为 CRITICAL（L1 有 L2 无）
- App.tsx 有 `<Route>` 但 `pages/<域>/index.tsx` 不存在 → 视为 CRITICAL（L2 有 L3 无）
- 页面 import api 模块但 `api/<域>.ts` 不存在 → 视为 CRITICAL（L3 有 L4 无）
- api wrapper 调用 endpoint 但后端无 `@router.<method>` → 视为 CRITICAL（L4 有 L5 无）

**判断信号**：
- `python scripts/check_registration.py` 退出码非 0 → 任意层缺失
- `grep -E "path: ['\"]/(notifications|orders|users)['\"]" config/menu_registry.yaml` 命中但 App.tsx 无对应 Route → L1 有 L2 无
- `Glob "frontend/src/pages/Notifications/index.tsx"` 失败但 App.tsx 有 `path="notifications"` 的 Route 引用 → L3 缺失
- `Glob "frontend/src/api/notifications.ts"` 失败但页面 import 该模块 → L4 缺失
- `grep -E "@router\.(get|post).*['\"\/]notifications" src/xianyu_hunter/web/routes/` 失败 → L5 缺失

**适用**：任何"用户可点击/可导航"的功能入口（菜单/侧边栏/按钮/Tab/Drawer/路由/Breadcrumb/通知订阅）。
**不适用**：纯静态页面、SSR（菜单由后端渲染）、单页 CLI、嵌入式设备、PWA 离线首页（单一 HTML 入口）、草稿/实验性 feature（用 exemption_list 豁免）。

**历史教训**：用户反馈"通知中心菜单点击无反应"。根因：`menu_registry.yaml` 注册了 `path=/notifications`，后端 `api_notifications.py` 完整实现接口，但前端 `App.tsx` 未注册路由、`pages/Notifications/` 不存在、`api/notifications.ts` 缺失。路由 fallback `<Route path="*" element={<Navigate to="/" replace />} />` 静默重定向回首页，用户体感"明明菜单点了几次，URL 都不变"。修复：新建 3 个前端文件 + App.tsx 注册路由。预防：加 #33 元规范 + `check_registration.py` 自动化脚本。

> 📖 详细 5 层契约模型、自动化校验脚本伪代码、配置节点定义见 [registration-completeness.md](registration-completeness.md)。

## 34. 修复前全链路根因扫描协议 🆕v4.32

> 与 B-REVIEW-160（backend 修复链路反查）/ F-REVIEW-118（frontend 根因最小数量）对应。

修复任何非平凡 bug（≥2 个文件参与 / 涉及状态变更 / 跨前后端 / 复盘过 ≥1 次）必须执行 5 步根因扫描协议，禁止"看到什么修什么"的单点修复。

1. **Step 1 列根因（≥3 个）**：必须列出至少 3 个独立根因，覆盖"用户层/接口层/数据层/配置层/历史层"5 维度，按"可能性 × 危害性"排序
2. **Step 2 排根因**：对每个根因用 1-2 个工具命令（Grep/Glob/Read/RunCommand）验证，记录"哪些被排除、哪些被确认"
3. **Step 3 修复**：只修改根因相关行（精确编辑原则），不顺手重构相邻代码，修复后立即 `git diff` 检查改动范围
4. **Step 4 反查**：修复后必须反查"同类 bug 的所有变体（横向同类）+ 用户操作路径其他拦截点（纵向全链）+ 配置/文档/部署中的体现（横向文档）"
5. **Step 5 防回归**：加 unit test + integration test + 更新 B/F-REVIEW 检查点 + 更新 `version-history.md` + 必要时更新 `project_memory.md` 硬约束

**关键约束**：
- PR 描述"修复"段不足 3 句 → 视为根因未充分展开（SUGGESTION）
- 修复后没有"反查同类 bug"段 → 视为 Step 4 缺失（SUGGESTION）
- `git diff` 涉及 ≥3 个无关文件 → 视为违反最小修改原则（WARNING）
- 新增逻辑但没加 unit test → 视为 Step 5 缺失（WARNING）
- 没有更新 `version-history.md` → 视为 Step 5 文档缺失（NIT）

**判断信号**：
- PR 描述 "修复" 段不足 3 句 → 根因未充分展开
- 修复后没有"反查同类 bug" 段 → Step 4 缺失
- `git diff` 涉及 ≥3 个无关文件 → 违反最小修改原则
- 新增逻辑但没加 unit test → Step 5 缺失
- 没有更新 `version-history.md` → Step 5 文档缺失

**适用**：修复任何非平凡 bug（≥2 个文件参与 / 涉及状态变更 / 跨前后端 / 复盘过 ≥1 次）。
**不适用**：纯样式 bug（颜色/间距/字号）、单行 typo（错别字/标点）、纯构建错误（依赖缺失/版本冲突）、安全漏洞补丁（时间敏感，先修后复盘，1 周内补复盘）、实验性 feature 试错。

**历史教训**：用户报告"通知中心菜单点击无反应"。朴素做法：直接去 App.tsx 加一行路由 → 完成。但用户还报告"配置中心"、"操作手册"、"实时日志"等 5 个菜单都"点击无反应"，单点修复只解决了 1/5。根因：6 类失败模式（相似 bug 重复 / 配置一致性盲区 / 跨语言契约模糊 / 熔断重试副作用 / 资源生命周期泄漏 / 空 except 吞异常）都源于"看到什么修什么"的单点修复思维。修复：建立 #34 5 步根因扫描协议，强制列 ≥3 根因 + 反查全链路。

> 📖 详细 5 步协议、6 类失败模式、配置节点定义见 [root-cause-protocol.md](root-cause-protocol.md)。

## 36. 规范沉淀门槛（防过度规范化）🆕v4.33

> 与 B-REVIEW-162（backend 规范立项前置计数）/ F-REVIEW-120（frontend 规范立项前置计数）对应。

新立编码规范（meta-rule / step / B-REVIEW / F-REVIEW）前必须满足"≥3 个相似 bug"门槛，避免单一 bug 立规范导致规范膨胀。安全漏洞/数据丢失/付费受损类 bug 可豁免，立即立规范。

1. **相似 bug 计数门槛**：同一根因（非表象）在不同文件/模块出现 ≥3 次才可立规范，阈值从 `config.yaml#meta_rules_governance.sedimentation_threshold` 读取
2. **计数维度**：根因相同（如"datetime 时区不一致"）而非表象相同（如"TypeError"）；文件/模块不同（非同文件重复）；时间窗口 ≤ 6 个月（避免跨年代久远的 bug 凑数）
3. **例外豁免**：安全漏洞（如 token 泄露）、数据丢失（如 DB 迁移失败）、付费受损（如订单金额错误）可立即立规范，无需 ≥3 次
4. **experimental 标签机制**：未达门槛但希望预沉淀的规范可标 `experimental` 标签，1 季度后未再出现相似 bug 则废弃；达标后升级为正式规范
5. **配置驱动**：相似 bug 计数阈值、时间窗口、例外豁免类别、experimental 观察期均从 config 读取，禁止硬编码

**关键约束**：
- 单一 bug 立规范（无 experimental 标签）→ 视为违规（规范膨胀风险）
- experimental 标签超 1 季度未升级为正式 → 视为废弃候选（应清理）
- 例外豁免立规范但未标注豁免原因 → 视为不规范（无法审计）
- 计数阈值硬编码在代码中 → 视为违规（应从 config 读）

**判断信号**：
- `grep "experimental" meta-rules.md` 标签超 1 季度未升级 → 废弃候选
- 新立 meta-rule 但无"历史教训"段（无相似 bug 支撑）→ 视为可疑
- 新立 B-REVIEW/F-REVIEW 但无对应"历史教训" → 视为可疑
- `grep "豁免原因" meta-rules.md` 例外规范缺豁免说明 → 视为不规范

**适用**：所有新立编码规范（meta-rule / step / B-REVIEW / F-REVIEW）的立项前置检查。
**不适用**：紧急安全修复（先修后立规范，1 周内补立项）、配置项新增（不立规范，只加 config 节点）、文档修正（非规范变更）。

**历史教训**：v4.10 期间某次单一 typo（变量名拼错）触发立规范，新增 1 条 B-REVIEW 检查点，但后续 6 个月未再出现相似 typo。该 B-REVIEW 在审查中 0 命中，占比规范总数 1.5%，拉低审查效率。修复：建立 #36 门槛规则，单一 bug 用 experimental 标签预沉淀，1 季度后未复现则废弃。

## 37. 规范退化机制（防规范膨胀）🆕v4.33

> 与 B-REVIEW-163（backend 规范退化清理）/ F-REVIEW-121（frontend 规范退化清理）对应。

每季度统计各 step / B-REVIEW / F-REVIEW 在审查中的命中次数，利用率 < 3 次/季度则标记为"待合并"或"待废弃"，避免规范垃圾堆积拉低审查信噪比。安全类规范永不退化。

1. **利用率统计**：每季度末统计各 step / B-REVIEW / F-REVIEW 在审查报告中的命中次数，输出利用率排行榜
2. **退化阈值**：利用率 < `config.yaml#meta_rules_governance.degradation_threshold`（默认 3 次/季度）则标记为"待合并"或"待废弃"
3. **合并优先**：相似 step 优先合并（如 3 个 datetime 相关 step 合并为 1 个），废弃是最后手段
4. **废弃流程**：标记"待废弃" → 1 季度观察期（`config.yaml#meta_rules_governance.observation_period_quarters`，默认 1） → 确认无命中 → 废弃并移入 `version-history.md` 的 Deprecated 章节
5. **安全类豁免**：安全类规范（token 比较 / 加密 / 认证白名单等）永不退化，即使 0 命中也保留
6. **配置驱动**：退化阈值、观察期时长、安全类豁免清单均从 config 读取

**关键约束**：
- 利用率 < 阈值但未标记"待合并/待废弃" → 视为不规范（规范治理缺失）
- 废弃的 step/B-REVIEW 未移入 version-history.md 的 Deprecated 章节 → 视为不规范（历史记录缺失）
- 安全类规范被标记"待废弃" → 视为违规（安全规范永不退化）
- 退化阈值硬编码 → 视为违规（应从 config 读）

**判断信号**：
- `grep "待废弃" meta-rules.md` 标记超 1 季度未处理 → 废弃流程卡住
- `grep "Deprecated" version-history.md` 章节缺失 → 废弃记录不全
- 季度审查报告显示利用率 < 3 的规范未标记 → 退化机制未执行
- 安全类规范出现在"待废弃"列表 → 视为违规

**适用**：所有现有 step / B-REVIEW / F-REVIEW 的季度治理。
**不适用**：安全类规范（永不退化）、配置驱动类规范（依赖 config 存在，config 节点存在则规范保留）、meta-rule #1-35 的元规范（元规范是基础规则，不参与退化）。

**历史教训**：v4.0-v4.10 累积 30+ step，v4.20 季度审查发现其中 8 个 step 在 1 季度内 0 命中，占比 27%。这 8 个 step 拉低审查效率，且部分与后续新增 step 语义重叠。修复：建立 #37 退化机制，8 个 0 命中 step 中 5 个合并到相似 step、3 个移入 Deprecated 章节，规范总数从 30+ 精简到 22，审查信噪比提升 27%。

---

# 列表聚合与状态联动元规范（38-42）🆕v4.34.0

> 以下 5 条元规范从 2026-07 期间修复的「全局聚合列表过滤失效 / 列表交叉数据 N+1 查询 / 多字段联动开关语义模糊 / precheck 异常处理不规范 / 配置化阈值缺失兜底」5 类问题中提炼，定义为「列表聚合与状态联动」维度的通用判断逻辑。
>
> 命名空间与配置驱动：所有阈值（`global_aggregate_filter` / `cross_domain_inject` / `linked_switch_priority` / `precheck_structured_fields` / `config_fallback_defaults`）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 53. 业务模式纵向链路一致性（MODE-VERTICAL-CHAIN）🆕v4.37

> 与维度 19 状态管理（B-REVIEW-183，待落地）/ 维度 4 业务逻辑（F-REVIEW-141，待落地）对应。

业务模式枚举（如 AUTO / SEMI_AUTO / MANUAL）必须在 6 个层纵向一致传递：决策层 → 事件层 → 通知层 → 路由层 → 接口层 → 状态机层。任一层缺失即模式退化。

**与 #40 MULTI-FIELD-LINKED-SWITCH 的边界**：
- #40 关注"字段间横向联动"（主开关 + 子过滤器的优先级矩阵）
- 本规范关注"模式枚举纵向链路"（同一 mode 值在 6 层是否都引用）

1. **决策层**：`_should_buy()` 等决策函数必须根据 mode 返回不同决策
2. **事件层**：业务事件 payload 必含 mode 字段（如 `EVAL_PASSED` 事件含 `task_mode`）
3. **通知层**：不同 mode 渲染不同模板（SEMI_AUTO 必含确认链接）
4. **路由层**：前端为每个 mode 的后续动作提供对应路由（如 `/confirm-buy`）
5. **接口层**：后端为每个 mode 的后续动作提供 endpoint
6. **状态机层**：必要时引入中间状态（如 `pending_confirm`）防越权

**关键约束**：
- grep mode 枚举值，每个值必须在 6 个层都至少出现 1 次
- 中间状态必须显式声明，禁止用临时变量隐式表达
- mode 字段名在 6 层必须严格一致（snake_case 透传，禁止 camelCase 转换）

**判断信号**：
- `grep "task_mode\|mode.*AUTO\|mode.*MANUAL"` 在事件 payload / 通知模板 / 路由 / endpoint 中未命中 → 链路断裂
- 决策函数返回值与 mode 无关 → 决策层未实现
- 通知模板对所有 mode 渲染相同内容 → 通知层未实现

**适用**：所有引入 mode 枚举且影响后续行为的业务（任务执行模式、采集模式、通知模式、订单确认模式）
**不适用**：纯展示型 mode 字段（仅日志记录不影响流转）、内部状态字段（不跨层传递）、单一布尔开关（无枚举语义，归 #40）

**历史教训**：SEMI_AUTO 模式退化为 CONFIRM/NOTIFY，因为：`_should_buy()` 返回 False / 通知模板缺确认链接 / 事件 payload 缺 `task_mode` / 缺 `pending_confirm` 中间状态 / 缺确认接口。修复：5 层全补齐（决策/事件/通知/路由/接口）+ 引入 `pending_confirm` 状态。

> 📖 详见 [state-management.md](../assets/guides/coding-rules/state-management.md) step 190。

## 93. 性能优化量化验证（PERFORMANCE-QUANTITATIVE-VERIFICATION）🆕v4.59.0

> 与 B-REVIEW-262~267（backend 性能审查）/ F-REVIEW-211~213（frontend 性能审查）/ xianyu-auto-testing 模式 R（性能优化回归测试）对应。
> 与 #26（关键路径异常保留 traceback）的区别：#26 关注"异常日志完整性"；#93 关注"性能优化的量化验证"。

**问题背景**：本次对话中实施了 8 个性能优化方案（批量 upsert / run_in_executor / 60 秒缓存 / SQL 层过滤 / list+count 合并 / useMemo / 优先级锁 / SSE 流式响应），其中缓存 TTL 从 5 秒修正为 60 秒后，缓存命中响应时间从 4240ms 降至 1ms（4240 倍提升）。但如果缺乏量化验证，优化效果无法确认——"感觉变快了"不是有效的验证证据。

**核心原则**：
1. **每个性能优化方案必须定义可量化指标**：指标必须包含"优化前值"和"优化后值"（如响应时间 4240ms → 1ms、缓存命中率 0% → 99%），禁止用"感觉变快了"等主观描述。
2. **必须通过运行时测试验证**：静态代码分析不能作为性能优化的验证证据，必须通过运行时测试（curl/API 调用/浏览器 E2E）获取实际指标。
3. **验证证据必须包含在优化说明中**：优化说明必须包含测试方法、测试数据、优化前/后指标对比表格。
4. **缓存类优化必须验证缓存命中率**：缓存优化必须验证缓存命中场景（重复请求命中缓存）和缓存失效场景（TTL 过期后重新触发操作）。

**判断信号**：
- `grep "优化前\|优化后\|before\|after" docs/` 找不到量化指标 → 补充量化验证
- `grep "缓存命中\|cache hit\|cache_hit" src/` 找不到缓存命中日志 → 补充缓存命中验证
- 性能优化说明中只有代码变更说明，无运行时测试结果 → 补充运行时验证

**配置驱动**：
- `performance_verification.enabled`：是否启用量化验证检查（默认 true）
- `performance_verification.required_metrics`：必须包含的指标类型（默认 `['response_time', 'cache_hit_rate']`）
- `performance_verification.runtime_test_required`：是否必须运行时测试（默认 true）
- `performance_verification.cache_hit_threshold_ms`：缓存命中响应时间阈值（默认 10ms，超过则视为未命中）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 所有性能优化任务（响应时间优化、缓存优化、查询优化、并发优化）
- 性能优化代码审查（需验证优化说明中是否包含量化指标）
- 性能优化回归测试（需验证优化效果是否持续）

**不适用场景**：
- 功能开发任务（无需量化指标）
- UI 调整（主观体验为主，但交互响应时间仍需量化）
- 纯代码重构（无性能影响时无需量化）

**与其他规则区别**：
- 与 #26（关键路径异常保留 traceback）的区别：#26 关注"异常日志完整性"；#93 关注"性能优化的量化验证"
- 与 PS-022（性能优化必须有量化验证指标）的关系：PS-022 是本元规范在 performance-and-security-patterns.md 的落地条文

**复盘来源**：2026-07-22 闲鱼猎人实时查询性能优化。根因链：
1. 实施缓存优化时 TTL 设为 5 秒，小于操作耗时 15-20 秒
2. 缺乏量化验证，未发现缓存命中率几乎为零
3. E2E 测试时才发现缓存未命中（响应时间仍为 4240ms）
4. 修正为 60 秒后缓存命中响应时间降至 1ms（4240 倍提升）

修复：
1. TTL 从 5 秒修正为 60 秒
2. 补充缓存命中验证（首次请求触发搜索、60 秒内重复请求命中缓存）
3. 优化说明中包含量化指标对比表格

对应 step 269/270。

## 108. 跨层闭环验证（CROSS-LAYER-CLOSED-LOOP）🆕v4.62.0

**问题**：修改前端/types 后未同步修改后端/DB，或修改后端后未验证前端是否正确消费，导致"后端改了前端没改"或"前端调了后端没实现"的跨层不一致。

**核心规则**：
1. 跨层修改必须同步验证三层：前端 types → 后端 Pydantic → DB schema
2. 每层修改后必须 `grep` 验证其他层的对应代码是否同步更新
3. 修改产生的"半边修改"必须标记为 CRITICAL 级别问题

**判断信号**：
- `git diff` 只修改 `types.ts` 但未修改对应 `models.py` → 违反规则1
- `git diff` 只修改 `models.py` 但未修改对应 `types.ts` → 违反规则1
- 前端调用不存在的 API 端点 → 违反规则2

**配置参数**：`cross_layer_closed_loop` 节点（enabled / checkLayers / syncMethodPattern / grepVerification）

**适用**：前后端协同修改、API 接口变更、DB schema 变更
**不适用**：纯前端样式修改、纯后端内部逻辑重构、纯 DB 性能优化（不改 schema）

**历史教训**：评估详情页新增"反馈"列：后端 API 新增 `feedback_score` 字段，前端 `types.ts` 已更新但 `EvaluationDetail.tsx` 未读取该字段，导致列显示为空。根因：后端改了前端未完整消费。

**对应 step**：step 52（数据流转完整性5点追踪）+ B-REVIEW-279（跨层闭环验证）。
