# 34. 规范治理（meta-rules #36-37 落地）🆕v4.37

> 本维度对应 `xianyu-hunter-dev` v4.33.0 meta-rules #36（规范沉淀门槛）与 #37（规范退化机制），与后端 `xianyu-backend-code-review` v4.33.0 维度 35 的 B-REVIEW-162/163 联动。前端侧新增 2 个 F-REVIEW 检查点（F-REVIEW-120/121），强调前端编码规范（F-REVIEW）的立项门槛与退化清理，防止过度规范化和规范膨胀。

#### F-REVIEW-120：SEDIMENTATION-THRESHOLD 规范立项前置计数（meta-rule #36 落地）

**规则**：新立前端编码规范（meta-rule / F-REVIEW / step）必须满足 ≥ `meta_rules_governance.sedimentation_threshold`（默认 3）个相似 bug 门槛，单一 bug 立规范需加 `experimental` 标签 + 1 季度观察期。

**关键约束**：
- 单一 bug 立规范（无 experimental 标签）→ 视为违规（规范膨胀风险）
- experimental 标签满 1 季度未升级为正式 → 视为废弃候选
- 例外豁免立规范但未标注豁免原因 → 视为不规范
- 计数阈值硬编码 → 视为违规（必须从 config 读取）

**判断信号**：
- `grep "🆕v4\\." SKILL.md` 新增维度标题但无对应的历史 bug 收集记录 → 视为违规
- `grep "experimental" SKILL.md` 标签满 1 季度未升级 → 废弃候选
- 新增 F-REVIEW 检查点但 `docs/standards/编码规范复盘.md` 中 < 3 个相关 bug 记录 → 视为违规

**配置参数**：`meta_rules_governance.sedimentation_threshold`（相关 bug 计数门槛，默认 3）、`meta_rules_governance.sedimentation_time_window_months`（计数时间窗口，默认 6 月）、`meta_rules_governance.experimental_observation_quarters`（experimental 观察期，默认 1 季度）、`meta_rules_governance.sedimentation_exemption_categories`（例外豁免类别：security_vulnerability / data_loss / payment_damage）在 `config.yaml` 的 `meta_rules_governance` 节点管理。

**对应编码规范**：详见 `xianyu-hunter-dev` v4.33.0 meta-rules #36 + 后端 `xianyu-backend-code-review` v4.33.0 B-REVIEW-162

**适用**：新增前端编码规范（F-REVIEW 检查点 / 维度 / step）的立项场景
**不适用**：安全漏洞类规范（XSS/CSRF/token 处理，立即立规范）、数据丢失类规范、付费受损类规范（这三类豁免 3 次门槛）

**历史教训**：v4.36.0 新增维度 31-33（F-REVIEW-117/118/119）时，仅基于"通知中心菜单点击无反馈"单一 bug 立规范，未满足 3 个相关 bug 门槛，且未标 experimental 标签。虽因属于"注册式资源三件套契约"类问题（影响用户可导航功能入口）可申请豁免，但未在规范中标注豁免原因，导致无法审计。修复：本维度（F-REVIEW-120）作为规范治理元规范，强制要求后续新增规范必须满足门槛或标注豁免原因。

#### F-REVIEW-121：DEGRADATION-CLEANUP 规范退化清理（meta-rule #37 落地）

**规则**：利用率 < `meta_rules_governance.degradation_threshold`（默认 3 次/季度）的 F-REVIEW 检查点必须标记"待合并"/"待废弃"，1 季度观察期后废弃并移入 `version-history.md` Deprecated 章节。

**关键约束**：
- 利用率 < 3 次/季度的 F-REVIEW 未标记待合并/待废弃 → 视为违规
- 标记"待废弃"满 1 季度未处理 → 视为违规（废弃流程卡住）
- 安全类规范被标记退化 → 视为违规（安全类永不退化）
- 退化阈值硬编码 → 视为违规（必须从 config 读取）

**判断信号**：
- `grep "待废弃|deprecated" SKILL.md` 标记满 1 季度未处理 → 废弃流程卡住
- F-REVIEW 检查点在最近 1 季度审查报告中 0 命中且未标记待废弃 → 视为违规
- 安全类 F-REVIEW（如 fetch_credentials_include / no_token_in_localstorage）被标记退化 → 视为违规

**配置参数**：`meta_rules_governance.degradation_threshold`（利用率退化阈值，默认 3 次/季度）、`meta_rules_governance.observation_period_quarters`（待废弃观察期，默认 1 季度）、`meta_rules_governance.degradation_exemption_categories`（永不退化类别：security / config_driven）在 `config.yaml` 的 `meta_rules_governance` 节点管理。

**对应编码规范**：详见 `xianyu-hunter-dev` v4.33.0 meta-rules #37 + 后端 `xianyu-backend-code-review` v4.33.0 B-REVIEW-163

**适用**：每季度对 F-REVIEW 检查点利用率统计与退化清理
**不适用**：安全类规范（XSS/CSRF/token 处理/认证白名单等永不退化）、配置驱动类规范（依赖 config 存在，config 存在则规范存在）

**历史教训**：v4.33.0 一次性新增 14 个 F-REVIEW（F-REVIEW-96~109），其中部分检查点（如 F-REVIEW-EMBEDDED-LAYOUT-HEIGHT）在后续季度审查中 0 命中，但未触发退化清理流程，导致规范堆积。修复：本维度（F-REVIEW-121）作为规范治理元规范，强制要求每季度统计利用率并清理低命中规范。

#### F-REVIEW-122：GLOBAL-AGGREGATE-TASK-FILTER 全局聚合任务级过滤（meta-rule #38 前端侧）🆕v4.38

**维度**：7 API 契约 / 11 数据展示

**规则**：前端聚合统计（如 Dashboard 价格区间分布、市场价比率分布）必须按当前任务的 `price_range`/`market_ratio` 配置过滤，禁止展示越界数据；前端展示聚合数据前必须确认后端已调用 `_filter_by_per_task_range` 过滤。

**关键约束**：
- 前端展示全局聚合数据但未确认后端按任务级配置过滤 → 视为违规（CRITICAL）
- 聚合数据中包含超出任务 `price_range` 的数据点 → 视为违规
- 聚合统计 UI 未标注"已按任务配置过滤" → 视为违规（WARNING）
- 前端自行实现过滤而非依赖后端 → 视为违规（应后端过滤，前端仅展示）

**判断信号**：
- `grep "aggregate\|stats\|distribution" frontend/src/` 后检查是否引用任务级配置过滤
- Dashboard 聚合组件未读取当前任务的 `price_range`/`market_ratio` → 视为违规
- 聚合数据响应中包含超出 `price_range` 的数据点 → 视为违规

**反模式**：前端展示全局聚合数据但未确认后端按任务级配置过滤

**正确模式**：`useEffect` 中 `fetch('/api/items/price-distribution?task_id=${taskId}')` 传入 task_id → 后端调用 `_filter_by_per_task_range` 按任务级 price_range/market_ratio 过滤

**配置参数**：`meta_rules_38_42_frontend.global_aggregate_filter.enabled`（开关，默认 true）、`severity`（CRITICAL）、`required_filter_function`（后端必须调用的过滤函数名，默认 `_filter_by_per_task_range`）、`task_config_fields`（任务级配置字段列表，默认 `["price_range", "market_ratio"]`）在 `config.yaml` 的 `meta_rules_38_42_frontend.global_aggregate_filter` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #38 + step 184

**适用**：所有全局聚合统计（Dashboard 价格分布、市场价比率分布、评估统计等）
**不适用**：单任务详情页的数据展示（已天然按 task_id 过滤）、用户级全局配置页面

**历史教训**：Dashboard 中"捡漏价格参考"聚合统计未按任务级 `price_range` 过滤，导致展示越界数据（如 price_range 配置为 0-100 元，但聚合分布中包含 200 元的数据点），用户误以为系统配置错误。修复：后端聚合 API 必须调用 `_filter_by_per_task_range` 按任务级配置过滤，前端传入 `task_id` 参数。

#### F-REVIEW-123：LIST-CROSS-DOMAIN-INJECT 列表交叉数据批量注入（meta-rule #39 前端侧）🆕v4.38

**维度**：7 API 契约 / 10 性能

**规则**：列表渲染交叉数据（如商品列表注入最新评估价/订单状态）必须用批量 API 一次性获取，禁止循环中逐项 fetch；前端必须支持批量响应的 `id → value` 映射结构。

**关键约束**：
- 列表中逐项 fetch 交叉数据（如 `items.map(item => fetch(`/api/eval/${item.id}`))`）→ 视为违规（CRITICAL）
- 批量 API 响应未用 `id → value` 映射结构 → 视为违规（WARNING）
- 前端未处理批量响应中缺失的 id → 视为违规（应加 fallback）
- 循环中调用 db query 的模式（`for item in items: db.query(...)`）→ 视为违规

**判断信号**：
- `grep "items.map.*fetch\|for.*of.*fetch" frontend/src/` 命中 → 视为违规
- `grep "\.map\(.*await" frontend/src/` 命中 → 视为违规（循环中 await）
- 列表组件中每个 item 单独发起 API 请求 → 视为违规

**反模式**：列表中逐项 fetch 交叉数据（N+1 查询）

**正确模式**：`fetch('/api/eval/batch', { method: 'POST', body: { ids: itemIds } })` 批量获取 → `evals` 为 `{ id: evalData }` 映射 → `items.map(item => ({ ...item, eval: evals[item.id] ?? null }))` 缺失加 fallback

**配置参数**：`meta_rules_38_42_frontend.cross_domain_inject.enabled`（开关，默认 true）、`severity`（WARNING）、`cache_ttl_seconds`（前端缓存 TTL，默认 300）、`batch_size_limit`（批量请求最大 id 数，默认 500）、`forbidden_loop_patterns`（禁止的循环模式列表）在 `config.yaml` 的 `meta_rules_38_42_frontend.cross_domain_inject` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #39 + step 185

**适用**：列表渲染交叉数据（商品列表注入评估价/订单状态、任务列表注入最新运行状态等）
**不适用**：单条详情页的数据获取、实时 SSE 推送的数据更新

**历史教训**：商品列表页每个商品单独 fetch 评估价，100 个商品触发 100 个 API 请求，页面加载时间从 200ms 膨胀到 5s+。修复：新增批量 API `/api/eval/batch`，前端一次性获取所有评估价并用 `id → value` 映射注入。

#### F-REVIEW-124：MULTI-FIELD-LINKED-SWITCH 多字段联动开关范式（meta-rule #40 前端侧）🆕v4.38

**维度**：3 React 组件 / 6 Zustand 状态管理

**规则**：多字段联动开关（如 mode + bargain_only）必须遵循"主开关决定副开关可见性"范式，副开关值在主开关关闭时必须清零而非保留；前端 UI 必须根据主开关状态动态显示/隐藏副开关。

**关键约束**：
- 副开关在主开关关闭时仍可操作 → 视为违规（MAJOR）
- 副开关值在主开关关闭时未清零（保留旧值）→ 视为违规（CRITICAL）
- 主开关切换时未触发副开关 UI 更新 → 视为违规
- 前端 UI 未根据主开关状态动态显示/隐藏副开关 → 视为违规

**判断信号**：
- `grep "mode.*bargain_only\|main_switch.*sub_switch" frontend/src/` 后检查联动逻辑
- 主开关切换时副开关值未清零 → 视为违规
- 副开关组件未根据主开关状态条件渲染 → 视为违规

**反模式**：副开关值在主开关关闭时未清零，且 UI 未联动

**正确模式**：`handleModeChange(newMode)` 切换主开关 → `newMode === 'notify'` 时 `setBargainOnly(false)` 副开关清零 → `{mode !== 'notify' && <Switch checked={bargainOnly} />}` 副开关条件渲染

**配置参数**：`meta_rules_38_42_frontend.linked_switch_priority.enabled`（开关，默认 true）、`severity`（MAJOR）、`main_switch_field`（主开关字段名，默认 `mode`）、`filter_suffix`（副开关后缀，默认 `_bargain_only`）、`priority_matrix`（主开关值 → 副开关可见性映射）在 `config.yaml` 的 `meta_rules_38_42_frontend.linked_switch_priority` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #40 + step 186

**适用**：所有多字段联动开关场景（mode + bargain_only、auto_buy + notify_only 等）
**不适用**：独立无依赖的开关字段、单向不可逆的开关（如删除确认）

**历史教训**：任务配置中 `mode` 切换为 `notify` 时，`bargain_only` 字段仍保留旧值 `true`，导致后端在 notify 模式下仍尝试 bargain 逻辑引发异常。修复：前端主开关切换时必须清零副开关值，且 UI 根据 `priority_matrix` 动态显示/隐藏副开关。

#### F-REVIEW-125：RESUME-PRECHECK-STRUCTURED 状态恢复前置校验结构化响应（meta-rule #41 前端侧）🆕v4.38

**维度**：7 API 契约 / 11 错误处理

**规则**：前端调用 resume/start 接口必须处理结构化 precheck 响应（`{resume_blocked, reason_code, user_hint, retry_after, task_registered}`），禁止假设接口直接成功；precheck 失败时必须展示 `user_hint` 和 `retry_after` 倒计时。

**关键约束**：
- 前端调用 resume/start 接口未处理 `resume_blocked: true` 情况 → 视为违规（CRITICAL）
- precheck 失败时仅展示通用错误而非 `user_hint` → 视为违规
- 未展示 `retry_after` 倒计时 → 视为违规（WARNING）
- 前端假设 resume 接口直接返回成功 → 视为违规

**判断信号**：
- `grep "resume\|start\|unpause" frontend/src/` 后检查是否处理结构化响应
- resume 接口响应处理中无 `resume_blocked` 字段判断 → 视为违规
- 错误展示中未引用 `user_hint` 或 `retry_after` → 视为违规

**反模式**：假设 resume 接口直接成功，未处理 precheck 结构化响应

**正确模式**：`fetch('/api/tasks/resume', { body: { task_id } })` → `res.resume_blocked` 为 true 时 `message.warning(res.user_hint)` + `setRetryCountdown(res.retry_after)` 倒计时 → 否则 `message.success('任务已恢复')`

**配置参数**：`meta_rules_38_42_frontend.precheck_structured_fields.enabled`（开关，默认 true）、`severity`（CRITICAL）、`required_fields`（结构化响应必须包含的字段列表，默认 `["resume_blocked", "reason_code", "user_hint", "retry_after", "task_registered"]`）、`forbid_raise`（是否禁止后端抛异常，默认 true）、`api_error_status`（precheck 失败时的 HTTP 状态码，默认 400）在 `config.yaml` 的 `meta_rules_38_42_frontend.precheck_structured_fields` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #41 + step 187

**适用**：所有 resume/start/unpause 接口的前端调用
**不适用**：首次创建任务（无 precheck 需求）、纯查询接口（无状态变更）

**历史教训**：前端调用 resume 接口时假设直接成功，但后端 precheck 检测到 cookie 过期返回 `resume_blocked: true`，前端仍展示"任务已恢复"导致用户困惑。修复：前端必须处理结构化 precheck 响应，precheck 失败时展示 `user_hint` 和 `retry_after` 倒计时。

#### F-REVIEW-126：CONFIG-DRIVEN-THRESHOLD-FALLBACK 配置化阈值兜底范式（meta-rule #42 前端侧）🆕v4.38

**维度**：1 配置驱动 / 11 错误处理

**规则**：前端使用的阈值参数（如 p10 百分位、market_ratio_threshold、price_range_tolerance）必须从后端配置 API 获取，禁止前端硬编码；配置 API 失败时必须用兜底默认值并 `console.warn`，禁止抛异常导致页面崩溃。

**关键约束**：
- 前端硬编码阈值参数（如 `const P10 = 0.10`）→ 视为违规（MAJOR）
- 配置 API 失败时抛异常导致页面崩溃 → 视为违规（CRITICAL）
- 配置 API 失败时未用兜底默认值 → 视为违规
- 配置 API 失败时未 `console.warn` 记录 → 视为违规（WARNING）

**判断信号**：
- `grep "const\s+P\d+\s*=\s*0\.\d+\|const\s+THRESHOLD\s*=" frontend/src/` 命中 → 视为违规
- 配置 API 调用无 try/catch 或 .catch() → 视为违规
- 配置 API 失败时无兜底默认值 → 视为违规

**反模式**：前端硬编码阈值，且配置 API 失败时抛异常

**正确模式**：`FALLBACK_DEFAULTS = { p10_percentile: 0.10, market_ratio_threshold: 0.85, price_range_tolerance: 0.05 }` 兜底 → `fetch('/api/config').then(r => r.json()).catch(err => { console.warn('配置 API 失败', err); return FALLBACK_DEFAULTS })`

**配置参数**：`meta_rules_38_42_frontend.config_fallback_defaults.enabled`（开关，默认 true）、`severity`（MAJOR）、`fallback_defaults`（兜底默认值映射，默认 `{p10_percentile: 0.10, market_ratio_threshold: 0.85, price_range_tolerance: 0.05}`）、`require_warning_log`（是否强制 console.warn，默认 true）在 `config.yaml` 的 `meta_rules_38_42_frontend.config_fallback_defaults` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.34.0 meta-rule #42 + step 188

**适用**：所有阈值参数（p10 百分位、market_ratio_threshold、price_range_tolerance 等）
**不适用**：纯 UI 展示参数（如颜色、字体大小）、无业务语义的常量

**历史教训**：前端硬编码 `P10_PERCENTILE = 0.10`，当后端配置调整为 `0.05` 时前端未同步，导致"捡漏价格参考"展示的"低于 P10"判定标准与后端不一致。修复：前端阈值参数必须从后端配置 API 获取，失败时用兜底默认值并 `console.warn`，禁止硬编码。
