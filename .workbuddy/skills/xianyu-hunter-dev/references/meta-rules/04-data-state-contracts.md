# 数据状态与契约
> 包含元规范 #24 - #105

## 24. 跨组件/跨源状态同步（适用于多源/多链路场景）

> v4.29 扩展：原 #24 仅覆盖前端跨组件同步，现扩展为「前端跨组件 + 后端跨源」双场景，新增「后端内部双源同步」约束。

复杂前端应用（多组件共享同一份数据）+ 多 Tab / 多路由 + 配置变更实时生效的场景，以及后端内部存在多个数据源（YAML/keyring/EventRow/业务表/缓存）的场景必须满足：

### 24-A 前端跨组件同步

1. **单一可信源**：后端 `GET /api/xxx` 是前端唯一数据源，**禁止**前端 `usePersistentState` 重复持久化
2. **统一入口**：所有写入路径必须通过 `useXxxStore().setXxx(newData)` 集中入口，**禁止**各组件独立 `setState`
3. **统一 refetch**：API 调用后必须 `refetch()` 而非推断新状态（避免乐观更新与后端实际不一致）
4. **跨进程同步**：子进程状态变更必须 SSE 推送，**禁止**前端用 TTL 缓存兜底

### 24-B 后端内部跨源同步 🆕v4.29

后端内部存在多个数据源（YAML/keyring/EventRow/业务表/缓存/浏览器内存）时必须满足：

1. **源识别**：新增状态字段时必须识别归属类别并登记到 `config.yaml#state_sync.backend_internal_sources` 源对清单：
   | 源对 | 典型场景 | 同步方向 |
   |---|---|---|
   | YAML ↔ keyring | 凭据（DingTalk/ServerChan/Bark token） | YAML 启动时同步到 keyring |
   | EventRow ↔ 业务表 | KPI 统计（抢单成功率/推送失败率） | 业务表为可信源，EventRow 仅作聚合 |
   | 健康检查 ↔ Worker 实测 | Cookie 层状态 | Worker 实测优先，健康检查兜底 |
   | Cookie JSON ↔ 浏览器内存 | Cookie 层级管理 | 浏览器内存兜底回填 JSON |
   | 配置缓存 ↔ 原始配置 | AppConfig 单例 | 原始配置变更后必须 invalidate 缓存 |

2. **同步时机**：
   - **启动时同步**：`_on_startup` 中调用 `_sync_xxx()`（如 `_sync_yaml_credentials_to_keyring`）
   - **写入时同步**：业务表写入后同步写 EventRow（如 NotifierHub 推送后写 `type='notify'` 事件）
   - **失效时同步**：Worker 检测到失效（如 RGV587_ERROR）必须调用 `invalidate_layer` 同步到健康检查
   - **读取时兜底**：JSON 缺失时从浏览器内存兜底回填（如 `CookieStore.upsert_cookie_values`）

3. **同步方向约束**：
   - 业务表 → EventRow 单向（EventRow 不得反向写业务表）
   - 原始配置 → 配置缓存单向（缓存不得反向写原始配置）
   - 浏览器内存 → JSON 单向回填（JSON 不得反向写浏览器内存）
   - YAML → keyring 启动时单向（keyring 不得反向写 YAML）

4. **禁止**：
   - 多个源独立读写无同步机制（如 YAML 凭据写后 keyring 未同步，导致通知"凭据未找到"被静默跳过）
   - 健康检查与 Worker 实测使用不同判定标准（如健康检查看 cookie 存在，Worker 看 RGV587_ERROR）
   - EventRow 写入 `type='eval.passed'` 但业务表只查 `type='eval.scored'`，导致 KPI 统计 0

**关键约束**：
- 后端 `single_source_of_truth` 列表中的 API 返回值是前端唯一可信源
- `forbid_persistent_state_for` 列表中的字段禁止前端 `usePersistentState` 重复持久化
- 跨进程状态变更（`sse_push_required_for`）必须 SSE 推送，`ttl_grace_seconds: 0` 即禁止 TTL 兜底
- 后端 `backend_internal_sources` 列表中的源对必须有显式同步代码（启动/写入/失效/读取任一时机）

**判断信号**：
- 前端：`grep "usePersistentState" <file>` 但该字段在后端有 `GET /api/xxx` → 视为违规
- 前端：多个组件独立 `useEffect(() => fetch(...), [])` 拉取同一份数据 → 视为违规
- 前端：`setTimeout(refresh, 30000)` 作为跨进程状态同步方案 → 视为违规
- 后端：`grep "keyring" <file>` 与 `grep "yaml" <file>` 同一凭据出现两处但无 `_sync_` 函数 → 视为违规
- 后端：`grep "EventRow" <file>` 写入但业务表查询条件不匹配 → 视为违规
- 后端：健康检查函数与 Worker 函数对同一状态使用不同判定逻辑 → 视为违规
- 后端：`grep "json.load" <file>` 与 `grep "browser.cookies" <file>` 同一 cookie 出现两处但无回填代码 → 视为违规

**适用**：
- 前端：复杂前端应用（多组件共享同一份数据）/ 多 Tab / 多路由场景 / 配置变更实时生效
- 后端：YAML/keyring/EventRow/业务表/缓存/浏览器内存等多源场景

**不适用**：
- 前端：简单组件树（1-2 层 props drilling 即可）/ 服务端渲染场景 / 纯 UI 偏好（主题色、视图模式）→ 纯 UI 偏好应用 `usePersistentState`（参考 meta-rule #7）
- 后端：单一数据源（如纯 DB 查询无缓存）/ 一次性脚本 / 性能 hot path（同步开销不可接受）

**历史教训**：
- 前端：用户反馈"功能正常但状态显示失效"（30 秒才恢复），根因：子进程登录后只更新自己的内存缓存，主进程读时取到 TTL 内的旧"失效"状态，前端 `LayerStatusBadge` 仅依据 `valid: boolean` 显示（无"未检测"区分），三层叠加导致用户体感"明明能跑却一直报错"
- 后端：DingTalk 通知不发送，根因：YAML 中保存了 webhook 凭据但 `secrets.py` 的 KEY 常量名与 YAML 字段名不一致，启动时未调用 `_sync_yaml_credentials_to_keyring()`，keyring 中无凭据导致 DingTalk 渠道被静默跳过
- 后端：抢单成功率/推送失败率恒为 0%，根因：`business_kpi.py` 查询 `EventRow` 用 `type='paid'/'confirmed'`，但 NotifierHub 实际写入 `type='notify'`，且 NotifierHub 未写 EventRow；多源不一致导致 KPI 统计分母为 0
- 后端：健康检查显示 cookie 未过期但 Worker 报 RGV587_ERROR，根因：健康检查看 cookie 存在 + identity 层 validity，Worker 看 API 实际响应 RGV587_ERROR，两套判定标准未同步

---

# 数据契约与时序元规范（25-30）🆕v4.30.0

> 以下 6 条元规范从 2026-06 至 2026-07 期间修复的批量任务断路器/启动钩子/日期时间/多源同步/错误传递/关键字管理 6 类问题中提炼，定义为「数据契约与时序」维度的通用判断逻辑。
>
> 命名空间与配置驱动：所有阈值（`fail_pause_threshold`/`critical_path_patterns`/`timezone_strategy`/`pending_marker_dir`/`error_code_enum`/`business_keyword_set`）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 28. 跨进程/跨组件状态同步六步法

> 与 #24 跨组件/跨源状态同步的区别：#24 聚焦「多源读写一致性」（如 YAML ↔ keyring），本条聚焦**写入端 + 同步调度器 + 读取端 + 启动检查**四方的全链路协作。

`config.yaml#state_sync.backend_internal_sources` 或 `frontend_pending_markers` 列表中的状态需要多源写入时（如 Cookie 多层管理、配置变更广播），必须满足六步：

1. **写端**：业务变更后写状态 + 写 `pending_marker`（如 `data/markers/cookie_refresh_<user_id>_<timestamp>.json`）
2. **同步端**：独立调度器（`cookie_sync_scheduler.py`）扫描 `pending_marker_dir` 执行同步
3. **读端**：仅读最新状态，不读 marker（marker 仅作同步信号）
4. **启动时**：`_on_startup` 检查 `pending_marker_dir` 中是否有未处理 marker，有则强制触发全量同步
5. **异常时**：保留 marker 不删除，下次重试（成功后才 `unlink`）
6. **配置**：同步开关、间隔、批次大小均通过 `config.yaml#state_sync` 节点管理

**关键约束**：
- `grep "pending_marker\|write_marker" <file>` 写端与 `grep "scan_marker\|process_marker" <file>` 同步端必须配对存在
- 启动函数匹配 `critical_path_patterns` → 必须含 `process_pending_markers()` 调用
- 失败重试最多 N 次（`max_retry_count`，默认 5）后告警，不无限重试

**判断信号**：
- `grep "write_marker" <file>` 但无 `scan_marker` 同步器 → 视为违规（marker 永远不会被消费）
- 启动函数无 `process_pending_markers` 但有 marker 写入端 → 视为违规（重启时积压 marker 丢失）
- `grep "os.unlink\|os.remove.*marker" <file>` 在 try 块内但无异常分支 → 视为违规（失败时 marker 丢失）

**适用**：Cookie 多层同步（JSON ↔ 浏览器内存 ↔ 业务表）、配置变更广播、跨 Tab 状态共享、用户偏好同步。
**不适用**：单写单读的临时状态、纯 UI 状态、性能 hot path（同步开销不可接受）、无跨进程边界的纯函数计算。

**历史教训**：Cookie 自愈系统（v4.32 优化）涉及 3 个写端（`auth_helper.py` / `browser_login.py` / 外部 API 调用）与 1 个同步器（`cookie_sync_scheduler.py`）。修复前：写端无 marker → 同步器无法被触发；写端有 marker 但启动时不检查 → 重启时积压 marker 永久丢失。修复：补全 6 步后，Cookie 自愈成功率从 65% 提升到 92%。

## 30. 业务关键字常量集中管理

> 与 F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION（frontend 维度 27）对应，本条覆盖后端 + 前端 + 配置 + 文档的**全栈关键字管理**。

业务关键字（已售、已删除、宝贝不存在、登录已过期、网络异常等需正则匹配/includes 判断的字符串）必须满足：

1. **集中位置**：
   - 后端：`config.yaml#business_keywords.<category>`（如 `sold` / `deleted` / `error_phrases`）
   - 前端：`frontend/src/constants/businessKeywords.ts`（如 `SOLD_KEYWORDS` / `DELETED_KEYWORDS` / `ERROR_PHRASES`）
2. **禁止散落**：业务代码中禁止硬编码关键字字符串（`if ('已售' in text）` → 应读 `config['business_keywords']['sold']`）
3. **配套版本号**：新增关键字需新增 `keyword_id`（如 `KW-SOLD-001`），用于追踪「哪条规则误判/漏判」
4. **配套测试**：每个关键字集合配单元测试（`test_business_keywords.py`）断言「新增商品文案 → 关键字集合应包含」
5. **同步约束**：前后端关键字集合**必须保持等价**（如后端 `sold` 含「卖掉了」，前端 `SOLD_KEYWORDS` 也必须含「卖掉了」），不一致 → 视为**契约不一致**

**关键约束**：
- `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售罄)['\"]" src/xianyu_hunter/` → 视为硬编码（应从 config 读）
- 业务代码 `grep "if.*['\"].*['\"].*in.*text\|if.*['\"].*['\"].*in.*msg" <file>` → 视为可能硬编码
- 前后端关键字集合不一致 → CI 校验失败（`tests/test_keyword_consistency.py`）

**判断信号**：
- 后端 `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售罄|该宝贝不存在|商品不存在)['\"]" <file>` → 视为违规
- 前端 `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售罄)['\"]" <file>` → 视为违规
- `config.yaml` 与 `frontend/src/constants/businessKeywords.ts` 关键字集合不一致 → 视为契约不一致

**适用**：商品状态识别（已售/已删/在售）、错误提示文案匹配、风控标签识别、敏感词过滤、用户行为分类。
**不适用**：日志/异常消息中的自由文本（仅展示用）、配置文件中的连接信息（用户名/密码）、测试用例中的 mock 数据（应使用 fixture）。

**历史教训**：Cookie 自愈系统的 `sold` 关键字集合在 `auth_helper.py`、`browser_login.py`、`cookie_sync_scheduler.py` 三处独立维护，新增「宝贝走丢了」时只更新了 2 处，第 3 处漏更新导致「已售商品」被误判为「在售」继续抢单。修复：抽取到 `config.yaml#business_keywords.sold` 集中管理，前后端同步，配套一致性测试，问题彻底消除。

## 35. 前后端字段契约单一可信源 🆕v4.32

> 与 B-REVIEW-161（backend 字段权威源标记）/ F-REVIEW-119（frontend 字段派生来源标注）对应。

前后端分离架构中，后端 Pydantic 模型 + DB Row 字段定义为权威源，前端 `types.ts` 必须显式标注派生来源，禁止无标注手工复制。

1. **单一可信源原则**：后端 Pydantic + DB Row = 权威源；前端 types.ts 必须显式标注派生来源（后端文件路径 + 行号 + Pydantic 字段 + 变更日期 + 约束）
2. **三种实现路径**：A 后端生成前端 types（datamodel-code-generator）/ B 手工对齐 + 注释标注（本项目当前选 B）/ C 共享 zod schema
3. **5 点追踪清单**：字段变更（新增/重命名/类型调整）必须 5 点全部更新：DB Row 定义 → Pydantic 模型 → 后端返回路径（_row_to_dict 白名单）→ 前端 types.ts → 前端消费点（api 方法 + pages 渲染）
4. **命名约定**：backend snake_case / frontend snake_case 严格透传（禁止转 camelCase）/ url_path kebab-case / class_name PascalCase
5. **配置驱动**：实现路径、注释模板字段、5 点追踪清单、命名约定、类型映射白名单均从 `config.yaml#contract_single_source` 读取

**关键约束**：
- 前端 types.ts 字段 `xxxYyy`（驼峰）但后端 Pydantic 字段 `xxx_yyy`（snake_case）→ 视为 CRITICAL（命名漂移）
- 后端新增字段但前端 types.ts 未同步 → 视为 CRITICAL（字段缺失）
- 前端 types.ts 缺 `派生来源` 注释 → 视为 WARNING（手工对齐但未标注）
- 前端 types.ts 字段标 `?` 但后端 Pydantic 标 `...` → 视为 WARNING（可选性漂移）
- 前端直接访问后端返回的 dict 用 `data['xxxYyy']`（驼峰）→ 视为 CRITICAL（违反 snake_case 透传）

**判断信号**：
- `grep "派生来源" frontend/src/api/types.ts` 缺失 → 手工对齐未标注
- 后端 Pydantic 字段 `xxx_yyy` + 前端 types.ts 字段 `xxxYyy` → 命名漂移
- 后端新增字段，前端 types.ts 未同步 → 字段缺失
- 前端 types.ts 字段标 `?` 但后端 Pydantic 标 `...` → 可选性漂移
- 前端直接访问后端返回的 dict 用 `data['xxxYyy']`（驼峰）→ 违反 snake_case 透传

**适用**：前后端分离架构中，任何跨网络边界传输的数据结构（HTTP body / query / path）。
**不适用**：纯前端单页（无后端）、SSR（后端直接渲染）、monorepo + 共享 types（已 typegen）、第三方 API（不可控，用适配层 + 注释"外部 API 字段名"）、性能 hot path（极致优化，用结构化 schema + 手工断言）。

**历史教训**：前端 `NotificationItem` 接口字段 `read_at` 拼成 `readAt`（驼峰）→ 后端返回 `read_at`（snake_case）→ 前端永远读到 `undefined` → "标记已读"按钮点击无效。根因：前端 types.ts 手工复制 Pydantic 字段时自己转成了驼峰。修复：建立 #35 单一可信源原则 + 5 点追踪清单 + types.ts 注释模板。5 类典型漂移：命名风格漂移 / 大小写漂移 / 类型漂移 / 可选性漂移 / 枚举值漂移。

> 📖 详细单一可信源原则、三种实现路径、5 点追踪清单、配置节点定义、典型反模式见 [contract-single-source.md](contract-single-source.md)。

## 38. 全局聚合任务级过滤（GLOBAL-AGGREGATE-TASK-FILTER）🆕v4.34

> 与 B-REVIEW-164（backend 列表聚合过滤维度）/ F-REVIEW-122（前端列表过滤透传）对应。

多任务共享的列表查询接口（无 `task_id` 参数的全局视图）必须按各任务的个体配置范围进行过滤，禁止只应用全局过滤而忽略任务级范围，导致越界数据被返回。

1. **全局视图与单任务视图区分**：列表查询接口必须区分「单任务视图」（显式 `task_id`）与「全局视图」（无 `task_id`），两者过滤逻辑不同
2. **全局视图任务级过滤**：全局视图必须遍历所有任务，对每条数据按其归属任务的个体配置（如价格范围）过滤，而非用全局默认范围过滤
3. **过滤函数抽取**：任务级过滤逻辑必须抽取为独立函数（如 `_filter_by_per_task_range`），便于复用与单测
4. **空范围处理**：任务无配置时使用全局默认范围兜底，禁止跳过过滤
5. **配置驱动**：过滤策略（per_task / global_only / hybrid）、默认范围兜底开关从 `config.yaml#global_aggregate_filter` 读取

**关键约束**：
- 全局视图缺任务级过滤分支 → 视为**必修 P0 缺陷**（数据越界）
- 任务级过滤逻辑硬编码在主循环（未抽取函数）→ 视为违规
- 任务无配置时跳过过滤（无兜底）→ 视为违规

**判断信号**：
- `grep "task_id.*None\|task_id.*is None" <file>` 但无 `_filter_by_per_task` / `_filter_by_task_range` 调用 → 视为违规
- `grep "def list_.*\(.*task_id.*\)" <file>` 缺全局视图分支 → 视为可疑
- 列表接口返回数据中存在超过任一任务配置上限的值 → 视为 P0

**适用**：多任务共享的列表查询接口（评估列表 / 仪表盘 / 商品列表 / 订单列表）、跨任务聚合视图、全局搜索。
**不适用**：单任务详情视图（task_id 显式传入，应用该任务范围）、统计聚合（无个体过滤需求）、管理后台超管视图（看全部数据）。

**历史教训**：用户反馈「最高价仍显示 ¥2,988.00」。根因：`evaluations_list.py` 在无 `task_id`（默认全局视图）时直接返回 `{min: None, max: None}` 不做任务级过滤，导致 task 价格上限 800 的商品也能查到 ¥2,988 的评估数据。修复：新增 `_filter_by_per_task_range` 函数，全局视图下按各任务个体价格范围过滤；`_load_sold_prices_from_links` 和 `_load_all_prices_from_items` 均调用此函数。

## 39. 列表交叉数据批量注入（LIST-CROSS-DOMAIN-INJECT）🆕v4.34

> 与 B-REVIEW-165（backend 列表 N+1 查询修复维度）/ F-REVIEW-123（前端列表数据合并展示）对应。

列表查询需要交叉注入其他数据源的数据（如评估列表注入捡漏价格、订单列表注入商品详情）时，必须采用批量查询 + TTL 缓存模式，禁止 N+1 单条查询导致接口性能退化。

1. **批量查询强制**：列表接口交叉其他数据源时必须用 `WHERE xxx IN (...)` 批量查询，禁止循环内单条查询
2. **TTL 缓存**：交叉数据查询结果必须按业务键（如 task_id / seller_id）缓存，TTL 从 `config.yaml#cross_domain_inject.cache_ttl_seconds` 读取
3. **单轮缓存**：单次 run_once / 单次请求内缓存，每轮重置（避免缓存陈旧）
4. **缺失降级**：交叉数据查询失败时降级为 `None` / 空对象，禁止阻断主列表返回
5. **配置驱动**：缓存开关、TTL、批量查询分块大小（避免 IN 子句过长）从 config 读取

**关键约束**：
- 循环内单条查询（`for item in items: db.query(filter=item.id)`）→ 视为**必修 P0 缺陷**（N+1 查询）
- 缺失交叉数据时抛异常阻断主列表 → 视为违规（应降级为 None）
- 缓存 key 含时间戳或随机值（无复用性）→ 视为违规

**判断信号**：
- `grep "for.*in.*items:" <file>` 后跟 `db.query\|session.execute` 单条查询 → 视为 N+1 违规
- `grep "def list_.*\(.*\)" <file>` 缺 `IN \(.*\)` 批量查询 → 视为可疑
- 交叉数据查询无 `cache_ttl` / `_cache` / `lru_cache` → 视为不规范

**适用**：列表接口需要交叉其他数据源（评估列表 + 捡漏价格、订单列表 + 商品详情、商品列表 + 卖家信息、任务列表 + 最后执行状态）。
**不适用**：单条详情查询（无 N+1 风险）、TTL 不可接受的热路径（需实时数据）、列表数据量固定 ≤3 条（无性能问题）。

**历史教训**：评估列表显示「预估盈利」时，`_compute_sold_range` 在循环内对每个 task 单独查询已售价格，10 个任务触发 10 次 DB 查询，接口耗时从 200ms 升到 1.8s。修复：改为批量查询所有 task 的已售价格 + 5 分钟 TTL 缓存，接口耗时降到 250ms。

## 40. 多字段联动开关范式（MULTI-FIELD-LINKED-SWITCH）🆕v4.34

> 与 B-REVIEW-166（backend 联动开关优先级矩阵）/ F-REVIEW-124（前端联动开关 UI 状态）对应。

多个业务字段叠加生效（如 `mode` 主开关 + `notify_bargain_only` / `auto_buy_bargain_only` 子过滤器）时，必须明确「主开关 → 过滤器」优先级矩阵，主开关失效时子过滤器自动禁用，禁止语义冲突的组合。

1. **优先级矩阵显式声明**：联动字段必须在文档/注释中显式声明「主开关 → 过滤器」优先级矩阵，列出所有合法组合
2. **主开关失效时子过滤器禁用**：主开关为 `notify`（仅通知）时 `auto_buy_*` 过滤器必须自动禁用 + UI 标识不可用
3. **PATCH 三态语义**：PATCH 接口必须用 `exclude_unset=True` 区分「未传 / 传 null / 传值」三态，禁止 0/false 被误判为未传
4. **bool→int 存储**：DB 存储 BOOLEAN 字段时统一用 INTEGER(0/1)，与同类开关字段（如 `use_cron`）保持一致
5. **配置驱动**：优先级矩阵、禁用规则、字段映射从 `config.yaml#linked_switch_priority` 读取

**关键约束**：
- 联动字段无优先级矩阵文档 → 视为 WARNING（语义模糊）
- 主开关 notify 模式但 `auto_buy_*` 未禁用 → 视为 P1（语义冲突）
- PATCH 接口未用 `exclude_unset=True` → 视为违规（三态丢失）
- bool 字段存储为 STRING('true'/'false') → 视为违规（应 INTEGER 0/1）

**判断信号**：
- `grep "mode.*notify\|mode.*auto_buy" <file>` 但无优先级矩阵注释 → 视为可疑
- `grep "exclude_unset.*True\|exclude_unset=True" <file>` PATCH 接口缺此参数 → 视为违规
- `grep "notify_bargain_only\|auto_buy_bargain_only" <file>` 缺 `disabled={.*mode.*===.*notify}` → 视为前端 UI 不规范
- `grep "BOOLEAN\|String.*true.*false" <file>` DB schema 中 bool 字段非 INTEGER → 视为违规

**适用**：多字段叠加生效的业务开关（mode + 子过滤器、enabled + 子配置、auto_* + 限制条件）。
**不适用**：独立开关（无联动）、纯前端 UI 开关（无后端逻辑）、单一布尔开关（无组合语义）。

**历史教训**：任务配置含 `mode` + `notify_bargain_only` + `auto_buy_bargain_only` 三个字段，无优先级矩阵。用户反馈「mode=notify 但 auto_buy_bargain_only=true 是否会触发自动下单」语义模糊。修复：明确优先级矩阵（mode 是主开关，*_bargain_only 是过滤器；mode=notify 时 auto_buy_bargain_only 自动禁用 + UI Tag 标识），PATCH 接口用 `exclude_unset=True` 三态语义，bool→int 存储与 `use_cron` 一致。

## 42. 配置化阈值兜底范式（CONFIG-DRIVEN-THRESHOLD-FALLBACK）🆕v4.34

> 与 B-REVIEW-168（backend 配置兜底范式）/ F-REVIEW-126（前端配置缺失降级）对应。

从 `config.yaml` 读取的阈值/分位数/百分位必须有 `try/except` 兜底默认值，保证配置缺失、配置加载失败、配置类型错误时系统仍可运行，禁止"配置缺失即崩溃"。

1. **try/except 兜底强制**：所有从 config 读取的阈值必须用 `try/except` 包裹，失败时回退到代码内默认值
2. **默认值合理性**：默认值必须与配置模板（`config.example.yaml`）保持一致，禁止默认值与示例配置冲突
3. **失败降级日志**：兜底时必须 `logger.warning` 记录（不用 `logger.error`，避免污染告警），含字段名与回退值
4. **配置全链路验证**：新增配置项必须同步更新 `config.example.yaml` + Config 类字段 + 消费点 try/except
5. **配置驱动**：兜底开关、默认值表、降级日志级别从 `config.yaml#config_fallback_defaults` 读取

**关键约束**：
- 配置读取无 `try/except` 兜底 → 视为 P1（配置缺失即崩溃）
- 默认值与 `config.example.yaml` 不一致 → 视为违规
- 兜底时用 `logger.error` 触发告警 → 视为不规范（应 `logger.warning`）
- 新增配置项未更新 `config.example.yaml` → 视为违规（参考 meta-rule #16 全链路验证）

**判断信号**：
- `grep "get_config\(\)\.\w+\.\w+" <file>` 但无 `try.*except.*default` 包裹 → 视为可疑
- `grep "from.*yaml_config import get_config" <file>` 但同文件 `get_config()` 调用无 try/except → 视为违规
- `grep "logger\.error.*配置.*默认\|logger\.error.*fallback" <file>` → 视为不规范（应 warning）
- `config.example.yaml` 与 Config 类默认值 grep 不一致 → 视为违规

**适用**：从 config 读取的阈值/分位数/百分位/重试次数/超时秒数/批次大小等可调参数。
**不适用**：强制必需配置（如数据库路径、认证密钥，缺失即不可启动，应在启动校验时 `raise` 而非兜底）、安全相关配置（如 token 比较方式，不可兜底）、协议固定值（不可配置）。

**历史教训**：`_compute_sold_range` 中 P10 分位数从配置读取 `bargain_percentile = get_config().bargain_price.percentile`，但用户 `config.yaml` 是旧版本无此字段，启动时未报错但调用时 `AttributeError: 'BargainPriceConfig' object has no attribute 'percentile'`，整个价格策略接口崩溃。修复：改为 `try: bargain_percentile = get_config().bargain_price.percentile; except Exception: bargain_percentile = 0.10` 兜底默认值，并 `logger.warning` 记录。后续推广为 #42 范式，所有配置读取必须有兜底。

> 📖 详细配置兜底范式、默认值表、降级日志模板见 [config-driven.md](../assets/guides/coding-rules/config-driven.md) step 188。

---

# 跨层契约与测试同步元规范（43-47）🆕v4.35.0

> 以下 5 条元规范从 2026-07-07 解决的「SEMI_AUTO 模式通知未触发确认 / EVAL_PASSED 事件三处发布点 task_mode 字段不对齐 / 前端 sheetRegistry 未注册新路由 + findSheetMeta 未剥离 query string / useSheetSync 丢失 query string / 历史测试 mock 类型不匹配 + keyring fallback + 接口签名变更未同步测试」5 类问题中提炼，定义为「跨层契约对齐与测试同步」维度的通用判断逻辑。
>
> 命名空间与配置驱动：所有参数（`event_multi_emit_alignment` / `frontend_route_registration` / `external_callback_query_retention` / `test_synchronization` / `external_dependency_isolation`）均在 `config.yaml` 对应节点管理，禁止硬编码。所有路径/模块名/字段名通过角色抽象描述（如「事件发布点」「路由注册表」「query string 字段名」），不硬编码具体文件名。

## 43. 事件多发布点字段对齐（EVENT-MULTI-EMIT-ALIGN）🆕v4.35

> 与 B-REVIEW-173（backend 事件多发布点字段对齐审查，v4.35 待落地）/ F-REVIEW-131（前端消费方分支对齐审查，v4.39 待落地）对应。

业务事件在多个层（worker / 服务 / 路由 / 通知模板）有发布点时，每处发布点必须保持事件 payload 字段集与字段语义一致，禁止某处补齐某字段而其他发布点遗漏，导致下游消费方按字段分支失败。

1. **多发布点识别**：grep 事件类型字符串（如 `EVAL_PASSED` / `task.started`），识别所有发布点（worker / service / route / template / SSE 推送器）
2. **字段对齐**：每处发布点的 payload 必须包含配置中声明的「必传字段集」（如 `task_mode` / `user_id` / `trace_id`），缺一视为违规
3. **重构同步**：当某处发布点新增字段时，必须 grep 所有发布点逐一同步
4. **下游消费对齐**：消费方按字段分支（如 `if payload.task_mode == SEMI_AUTO`）时，必须存在 fallback 分支（`else` / `default`），避免字段缺失时静默走默认路径
5. **配置驱动**：发布点清单、必传字段集、字段语义说明从 `config.yaml#event_multi_emit_alignment` 读取

**关键约束**：
- 业务事件有 ≥2 处发布点但 payload 字段集不一致 → 视为 **必修 P0 缺陷**（下游分支失效）
- 新增字段但未 grep 同步所有发布点 → 视为违规
- 消费方按字段分支但无 fallback → 视为违规（字段缺失时静默默认）
- 发布点清单硬编码在代码中（如 `["worker.py", "collection_service.py"]`）→ 视为违规（应从 config 读）

**判断信号**：
- `grep "<event_type>" src/` 命中 ≥2 处，每处上下文 `grep "<required_field>"` 不全命中 → 字段未对齐
- `grep "<event_type>.*emit\|publish.*<event_type>"` 多处但 `payload = {` 后字段数不同 → 字段集不一致
- 消费方 `if payload.<field> == X` 但无 `else` → fallback 缺失
- 新增字段后 git diff 显示发布点未同步更新 → 同步缺失

**适用**：业务事件在多层有发布点的场景（worker → service → route → 通知模板）；事件 payload 含分支决策字段（如 `task_mode` / `severity` / `source`）；事件需多消费方订阅（SSE 推送 + 通知中心 + Dashboard 刷新）。
**不适用**：单一发布点的内部事件（一处发布无需对齐）；纯调试日志事件（不产生下游副作用）；一次性脚本事件（无长期维护成本）。

**历史教训**：SEMI_AUTO 模式任务通过评估后，`worker.py` 的 `EVAL_PASSED` 发布点 payload 含 `task_mode` 字段，但 `collection_service.py` 与 `evaluations_common.py` 两处发布点未携带 `task_mode`，导致通知模板层无法按 `task_mode` 渲染"确认抢单"链接，SEMI_AUTO 退化为 NOTIFY_ONLY，从未触发确认动作。修复：grep 所有 EVAL_PASSED 发布点逐一补齐 `task_mode`，并建立 #43 强制对齐规则。

## 52. 参数链闭环验证（PARAM-CHAIN-EXEC）🆕v4.37

> 与维度 19 API 设计（B-REVIEW-177）/ 维度 7 API 契约（F-REVIEW-144）对应。

过滤类参数（filter / constraint 语义）从 API 接收后必须存在对应的消费点（函数调用 / SQL WHERE / 条件分支），禁止"参数已接收但未被消费"。

1. **接收点验证**：API endpoint 函数签名声明参数后，函数体内必须存在该参数的消费逻辑
2. **消费点验证**：参数必须实际参与过滤条件构建（WHERE 子句 / 条件分支 / 函数调用参数）
3. **结果集验证**：必须存在单元测试验证"传参 vs 不传参"结果集差异，否则视为过滤未生效
4. **元数据参数豁免**：分页参数（page / page_size / limit / offset）与排序参数（sort / order）属于标识/定位类参数，不在本规范范围

**关键约束**：
- 参数出现在函数签名 + return dict 中但未出现在过滤逻辑 → 视为"参数悬挂"违规
- 参数命名暗示过滤语义（含 `filter_` / `range_` / `min_` / `max_` / `ratio_` 前缀）必须闭环
- 元数据参数白名单在 `config.yaml` 管理，禁止硬编码

**判断信号**：
- `grep "<param_name>" <file>` 仅命中函数签名和 return 语句但未命中函数调用 → 视为可疑
- API 接收 `market_ratio` 参数但未调用 `PriceStrategy.check(market_ratio=...)` → 违规
- 单元测试无 `with_param` / `without_param` 对比用例 → 视为闭环验证缺失

**适用**：所有有过滤参数的列表查询 API（list_evaluations / list_items / search_* / list_orders）、PATCH/PUT 接口的可空字段
**不适用**：GET 单个资源详情（无过滤）、DELETE 接口（参数仅定位资源）、仅作元数据返回的字段（total_count）、创建类 POST 接口

**历史教训**：`evaluations_list.py` 接收 `market_ratio=0.85` 参数但未调用 `PriceStrategy.check`，导致调整到 0.85 后仍能查出价格上限 800 的商品。修复：新增 `_resolve_market_ratio` / `_compute_eval_market_median` / `_filter_market_ratio` 三个辅助函数形成闭环。

> 📖 详见 [config-driven.md](../assets/guides/coding-rules/config-driven.md) step 189。

## 88. 跨层数据契约同步流程（CROSS-LAYER-CONTRACT-SYNC）🆕v4.55.0

> 与 B-REVIEW-248（backend 数据覆盖策略集合管理审查）/ F-REVIEW-200（前端 React 组件复用状态重置审查）/ xianyu-auto-testing 模式 M（跨层数据契约一致性测试）对应。
> 与 #85（关键路径可观测性与状态同步三要素）的关系：#85 的第 4 点定义了 `_ALWAYS_OVERWRITE` 集合选择标准；#88 定义了"发现字段跨层不一致时的修复流程"。

**问题背景**：用户反馈点击商品标题跳转至官方详细商品页面时，商品评估明细信息和商品图片未更新。根因是两个关联缺陷：(1) 前端 `ThumbCell` 组件在图片 URL 更新后未重置 `errored` 状态，导致加载失败的占位图残留——React 组件因 `rowKey` 不变被复用时，`useState` 状态不自动重置；(2) 后端在官方采集未获取到图片时，将 `items` 表的 `image_urls` 字段覆盖为 `None`，清空了旧数据——`image_urls` 误入 `_ALWAYS_OVERWRITE` 集合，应走 `_coalesce`。同类问题反复出现在 `brand`、`display`、`seller_credit` 等字段上，根因都是"修改字段覆盖策略时未走完整的跨层契约同步流程"。

**核心原则**：
1. **跨层契约同步五步流程**：发现字段跨层不一致时，必须按以下五步修复，缺步即遗留 Bug：
   - 步骤 1：识别跨层字段——找出前端消费、后端产出、DB 存储的三层字段
   - 步骤 2：判断覆盖策略——该字段属于 `_ALWAYS_OVERWRITE`（强制覆盖）/ `_coalesce`（旧值优先）/ `_NULL_SAFE`（空值不清空）哪个集合
   - 步骤 3：前端状态重置——React 组件复用场景，URL/props 变化时重置 `errored`/`loaded`/`loading` 等内部状态
   - 步骤 4：后端写回保护——外部 API 返回空值时不清空旧有效数据，空值视为"本次未取到"而非"应清空"
   - 步骤 5：跨层一致性验证——后端字段集合改动后，前端 `types.ts` 同步标注派生来源
2. **空值语义区分**：
   - `None`/`null`（显式空值）：API 返回了字段但值为空，语义是"应清空"，可覆盖
   - 字段缺失（API 未返回该字段）：语义是"本次未取到"，应走 `_coalesce` 保留旧值
   - **禁止**把"字段缺失"当作"显式空值"处理——采集可能因网络/权限/页面结构变化而未取到字段，这不代表字段值应为空
3. **React 组件复用状态重置**：组件因 `rowKey` 不变被 React 复用时，`useState` 状态不自动重置。内部状态依赖的 prop（如 `url`、`src`、`id`）变化时，必须用 `useEffect` 重置相关状态。**禁止**假设"props 变化时 React 会自动重置内部状态"——React 的复用机制是为了性能，不会重置 state。
4. **覆盖策略集合管理**：`_ALWAYS_OVERWRITE` 集合只放"每次采集必定获取到 + 新值更准确"的字段（如 `title`、`price`、`updated_at`）；采集可能返回空的字段（如 `image_urls`、`brand`、`description`）走 `_coalesce`。**禁止**把可能返回空的字段放入 `_ALWAYS_OVERWRITE`——采集失败时会用 `None` 覆盖旧有效数据。
5. **前后端契约同步**：后端 `ResponseModel` / DB Row 字段变更时，前端 `types.ts` 必须同步更新并标注派生来源（`// derived from backend ResponseModel.xxx`）。**禁止**后端字段变更但前端 `types.ts` 无响应。

**判断信号**：
- `grep "_ALWAYS_OVERWRITE" src/` 找到集合定义 → 检查每个字段是否"每次采集必定获取到"
- `grep "image_urls\|brand\|description" src/` 找到可能返回空的字段 → 检查是否在 `_ALWAYS_OVERWRITE` 中（应在 `_coalesce`）
- `grep "useState.*errored\|useState.*loaded\|useState.*loading" frontend/` 找到含内部状态的组件 → 检查是否在列表/展开行/Tab 面板中使用 + prop 变化时是否 `useEffect` 重置
- `grep "rowKey" frontend/` 找到列表组件 → 检查 `rowKey` 是否唯一（不唯一会导致复用）
- 后端 `ResponseModel` 新增字段但前端 `types.ts` 无对应 → 契约不同步

**配置驱动**：
- `cross_layer_contract_sync.enabled`：是否启用跨层契约同步检查（默认 true）
- `cross_layer_contract_sync.always_overwrite_set`：强制覆盖字段白名单（默认 `['title', 'price', 'updated_at', 'status']`）
- `cross_layer_contract_sync.coalesce_set`：coalesce 字段白名单（默认 `['image_urls', 'brand', 'description', 'seller_credit']`）
- `cross_layer_contract_sync.null_safe_set`：空值不清空字段白名单（默认 `[]`）
- `cross_layer_contract_sync.empty_value_semantics`：空值语义定义（默认 `{'none': 'explicit_clear', 'missing': 'keep_old'}`）
- `cross_layer_contract_sync.component_reuse_reset_fields`：组件复用需重置的状态字段（默认 `['errored', 'loaded', 'loading']`）
- `cross_layer_contract_sync.rowkey_uniqueness_required`：rowKey 唯一性要求（默认 true）
- `cross_layer_contract_sync.frontend_types_annotation_required`：前端 types.ts 派生来源标注要求（默认 true）
- `cross_layer_contract_sync.scan_globs`：扫描的文件 glob（默认 `['src/xianyu_hunter/web/routes/api_*.py', 'frontend/src/types.ts', 'frontend/src/pages/**/*.tsx']`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 前后端契约字段调整（新增/删除/重命名字段）
- DB 字段覆盖策略变更（`_ALWAYS_OVERWRITE` ↔ `_coalesce` 互转）
- React 组件在列表/展开行/Tab 面板中复用（`rowKey` 不变）
- 采集-存储链路（外部 API → DB → 前端展示）
- 官方采集/重采触发数据更新的场景

**不适用场景**：
- 纯前端 UI 样式调整（无数据契约变更）
- 纯后端内部计算逻辑（无前端消费）
- 一次性数据迁移（无持续同步需求）
- 每次都创建新实例的组件（`key` 唯一，无复用问题）
- 单一覆盖策略（无 `_coalesce` 逻辑）

**与其他规则区别**：
- 与 #85（关键路径可观测性与状态同步三要素）的区别：#85 定义了 `_ALWAYS_OVERWRITE` 集合选择标准（聚焦"哪个集合"）；#88 定义了"发现不一致时的五步修复流程"（聚焦"怎么修"）
- 与 #35（前后端字段契约单一可信源）的区别：#35 关注"字段派生来源标注"（静态契约）；#88 关注"字段覆盖策略变更时的动态同步流程"
- 与 #87（配置字段五层链路覆盖）的区别：#87 关注"用户可编辑配置字段"的链路完整性；#88 关注"业务数据字段"的跨层覆盖策略一致性
- 与 step 249（React 组件复用状态重置）的关系：step 249 是 #88 第 3 步的具体实现
- 与 step 250（字段覆盖集合选择标准）的关系：step 250 是 #88 第 2 步的具体实现

**复盘来源**：2026-07-22 商品评估明细/图片未更新 Bug。根因链：
1. 前端 `ThumbCell` 组件因 `rowKey` 不变被 React 复用，图片 URL 更新后 `errored` 状态未重置 → 旧的占位图残留
2. 后端 `api_evaluations.py` 中 `image_urls` 在 `_ALWAYS_OVERWRITE` 集合，官方采集未获取到图片时 `None` 覆盖旧值 → 图片消失

修复：
1. 前端 `index.tsx` 添加 `useEffect(() => { setErrored(false) }, [url])` 重置 errored 状态
2. 后端将 `image_urls` 移出 `_ALWAYS_OVERWRITE`，走 `_coalesce` 保留旧值

对应 step 258/259/260。

## 90. 回退构造保留关联键（FALLBACK-PRESERVE-KEY）🆕v4.57.0

> 与 B-REVIEW-251（backend 回退构造关联键审查）/ F-REVIEW-206（前端回退构造关联键审查）/ xianyu-auto-testing 模式 O（回退构造关联键一致性测试）对应。
> 与 #88（跨层数据契约同步流程）的关系：#88 关注"字段覆盖策略"的跨层一致性；#90 关注"回退构造实体"时关联键的完整性——两者都可能因"遗漏字段"导致下游逻辑被跳过。

**问题背景**：AI 评估接口返回结果缺少 `price_range` 字段。根因是 `get_eval_payload_by_item` 方法只查询 `EventRow.payload` 不查询 `EventRow.task_id`，导致从 payload 回退构造的伪 item dict 无 `task_id` 字段。下游价格区间查询 `if task_id:` 条件判断因 `task_id` 为 None 被跳过，价格区间数据未注入 LLM prompt。同类问题反复出现在"从部分数据回退构造实体"的场景——回退构造的实体遗漏了下游依赖的关联键，导致下游条件判断被静默跳过。

**核心原则**：
1. **回退构造必须保留关联键**：从事件 payload / 缓存 / 部分数据回退构造实体时，必须同时查询并注入下游依赖的所有关联键（如 `task_id`、`user_id`、`seller_id`）。**禁止**只取 payload 内容而不取关联键——下游条件判断 `if task_id:` 会因关联键缺失而静默跳过逻辑。
2. **下游条件判断前校验键存在**：回退构造的实体传入下游时，下游应在条件判断前校验关联键是否存在，而非假设关联键一定有值。若关联键缺失，应记录 WARNING 日志而非静默跳过。
3. **回退路径必须可观测**：回退构造实体时必须记录日志（包含实体 ID、关联键值、回退来源），禁止静默回退。日志用于排查"为什么下游逻辑被跳过"。
4. **关联键清单管理**：每个回退构造点必须维护"下游依赖的关联键清单"，查询时必须同时取这些键。**禁止**在回退构造函数中只取业务字段而遗漏关联键。

**判断信号**：
- `grep "payload.get\|fallback" src/` 找到回退构造逻辑 → 检查是否遗漏 `task_id`/`user_id`/`seller_id` 等关联键
- `grep "if task_id:\|if user_id:\|if seller_id:" src/` 找到下游条件判断 → 检查上游回退构造是否注入了该键
- `grep "setdefault.*task_id\|setdefault.*user_id" src/` 找到关联键注入 → 确认回退构造路径有此逻辑
- 回退构造函数只查询 `payload` 字段而不查询关联键字段 → 视为违规

**配置驱动**：
- `fallback_preserve_key.enabled`：是否启用回退构造关联键检查（默认 true）
- `fallback_preserve_key.required_keys`：回退构造必须保留的关联键清单（默认 `['task_id', 'user_id', 'seller_id']`）
- `fallback_preserve_key.log_on_missing_key`：关联键缺失时是否记录 WARNING（默认 true）
- `fallback_preserve_key.scan_globs`：扫描的文件 glob（默认 `['src/xianyu_hunter/infra/repo_*.py', 'src/xianyu_hunter/web/routes/api_*.py']`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 事件 payload 回退构造实体（如从 eval 事件 payload 回退构造 item dict）
- 缓存回退构造实体（如从缓存部分数据回退构造完整对象）
- 数据库多表回退查询（如从事件表回退查询时需要同时取关联表的外键）
- 任何"从部分数据构造实体 + 下游依赖关联键"的场景

**不适用场景**：
- 直接从主表查询完整实体（无回退，字段齐全）
- 纯展示场景（无下游关联查询需求）
- 一次性脚本（无持续维护需求）

**与其他规则区别**：
- 与 #88（跨层数据契约同步流程）的区别：#88 关注"字段覆盖策略"跨层一致性；#90 关注"回退构造实体"时关联键完整性
- 与 #35（前后端字段契约单一可信源）的区别：#35 关注"字段派生来源标注"；#90 关注"回退构造时关联键不遗漏"
- 与 #87（配置字段五层链路覆盖）的区别：#87 关注"用户配置字段"链路完整性；#90 关注"业务数据回退构造"时关联键完整性

**复盘来源**：2026-07-22 AI 评估 price_range 注入 Bug。根因链：
1. `repo_events.py` 的 `get_eval_payload_by_item` 只查 `EventRow.payload` 不查 `EventRow.task_id`
2. `api_ai.py` 回退构造伪 item dict 时 `task_id` 为 None
3. 价格区间查询 `if task_id:` 条件判断因 `task_id` 为 None 被跳过
4. AI 评估结果缺少 `price_range` 字段

修复：
1. `repo_events.py` 同时查询 `EventRow.payload` 和 `EventRow.task_id`，将 `task_id` 注入 payload dict
2. `api_ai.py` 回退构造伪 item 时从 payload 提取 `task_id`

对应 step 261/262/263。

## 91. 时间窗口查询全量回退（TIME-WINDOW-FULL-FALLBACK）🆕v4.57.0

> 与 B-REVIEW-252（backend 时间窗口全量回退审查）对应。
> 与 #90（回退构造保留关联键）的关系：#90 确保"关联键不缺失"；#91 确保"时间窗口无数据时有回退"——两者都防止下游逻辑被静默跳过。

**问题背景**：AI 评估接口查询同类物品已售价格区间时，`range_days=30` 返回 `source: "empty"`，但 `range_days=0`（全量）有 58 条数据。根因是数据库中商品数据时间较早，超过 30 天窗口。价格区间数据缺失导致 LLM 无法引用价格参考。同类问题反复出现在"基于时间窗口的统计查询"场景——窗口内无数据时直接返回空结果，而非回退到全量查询。

**核心原则**：
1. **时间窗口查询必须有全量回退**：基于时间窗口的统计查询（如价格区间、销量统计、热度排名），当窗口内无数据时必须自动回退到全量查询（`range_days=0`）。**禁止**窗口无数据时直接返回空结果——统计数据缺失会导致下游决策无参考。
2. **回退必须可观测**：窗口回退时必须记录日志（包含窗口参数、窗口内数据量、回退后数据量），禁止静默回退。日志用于排查"为什么数据量突然变少"。
3. **回退结果必须标注 source**：回退查询的结果必须标注数据来源（`source` 字段），区分"窗口内有数据"和"回退到全量"。下游消费方根据 `source` 判断数据时效性。
4. **窗口参数配置驱动**：时间窗口参数（如 `range_days`）必须在配置文件管理，**禁止**硬编码在代码中。

**判断信号**：
- `grep "range_days" src/` 找到时间窗口查询 → 检查窗口无数据时是否有全量回退
- `grep "source.*empty\|source.*full" src/` 找到 source 标注 → 确认回退时 source 有变化
- `grep "range_days.*30\|range_days.*7\|range_days.*90" src/` 找到硬编码窗口 → 应从配置读取
- 时间窗口查询返回 empty 但无回退逻辑 → 视为违规

**配置驱动**：
- `time_window_fallback.enabled`：是否启用时间窗口全量回退检查（默认 true）
- `time_window_fallback.default_window_days`：默认时间窗口天数（默认 30）
- `time_window_fallback.fallback_to_full`：窗口无数据时是否回退到全量（默认 true）
- `time_window_fallback.log_on_fallback`：回退时是否记录日志（默认 true）
- `time_window_fallback.source_field_name`：结果来源标注字段名（默认 `'source'`）
- `time_window_fallback.scan_globs`：扫描的文件 glob（默认 `['src/xianyu_hunter/web/routes/api_*.py', 'src/xianyu_hunter/web/routes/price_dashboard.py']`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 价格区间统计查询（如已售商品价格区间）
- 销量统计查询（如近 N 天销量排名）
- 热度排名查询（如近 N 天搜索热度）
- 任何"基于时间窗口的聚合统计 + 数据可能超出窗口"的场景

**不适用场景**：
- 实时性要求高的查询（如当前库存、实时价格——回退到全量会引入过期数据）
- 窗口语义即为"只看这个时间段"的查询（如"近 7 天新增商品"——回退到全量会改变语义）
- 增量同步查询（如"自上次同步以来的变更"——回退会重复处理）

**与其他规则区别**：
- 与 #90（回退构造保留关联键）的区别：#90 确保"关联键不缺失"（实体构造层面）；#91 确保"时间窗口无数据时有回退"（查询策略层面）
- 与 #22（批处理熔断断模式）的区别：#22 关注"批处理失败时保存进度"；#91 关注"时间窗口查询无数据时回退到全量"

**复盘来源**：2026-07-22 价格区间 30 天窗口返回 empty Bug。根因链：
1. `api_ai.py` 查询价格区间时用 `range_days=30`
2. 数据库中商品数据时间较早，超过 30 天窗口
3. 查询返回 `source: "empty"`，无回退逻辑
4. AI 评估结果缺少价格区间参考

修复：
1. `api_ai.py` 增加 30 天查询返回 empty 时用 `range_days=0` 重查
2. 日志记录回退行为和结果

对应 step 264/265。

## 105. 数据写入策略字段级决策（FIELD-STRATEGY）🆕v4.62.0

**问题**：数据合并时"一刀切"覆盖策略导致：数值类字段被 0 覆盖、标识类字段频繁变化、状态类字段更新不及时。

**核心规则**：
1. 数据合并按字段语义分类采用不同策略，禁止一刀切
2. **alwaysOverwrite**：状态类字段（`is_sold`/`status`/`valid`）——时效性最高，始终覆盖
3. **coalesceIfTruthy**：数值类字段（`price`/`count`/`score`）——新值 > 0 才覆盖，防止 0 覆盖有效值
4. **fillIfMissing**：标识类字段（`seller_nick`/`brand`/`category`）——只填缺失，稳定性高
5. **overwriteIfNotBlank**：基本信息字段（`title`/`url`/`region`）——新值非空则覆盖

**判断信号**：数据合并/更新代码中 `for k, v in new_data.items(): old[k] = v` 无条件覆盖 → 必须按字段语义分类

**配置参数**：`field_strategy` 节点（alwaysOverwriteFields / coalesceIfTruthyFields / fillIfMissingFields / overwriteIfNotBlankFields）

**适用**：数据采集合并、爬虫数据覆盖历史快照、缓存更新
**不适用**：审计日志（需保留全量历史）、纯创建场景（无旧值）

**历史教训**：商品刷新时 `price=0`（平台返回缺失值）覆盖了历史有效价格，导致低价商品被误判。修复后 price 字段改为 `coalesceIfTruthy` 策略。

**对应 step**：step 248（general-engineering.md）+ step 17（数据合并字段覆盖策略）。
