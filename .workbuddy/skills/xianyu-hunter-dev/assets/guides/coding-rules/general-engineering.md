# General Engineering 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「general engineering」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 6：注释项检查【强制】

6. **注释项检查【强制】**
   - 模块级 docstring：说明职责 + 设计要点 + 引用设计文档（如 `docs/<模块>-详细设计.md §x.y`）
   - 类注释：说明类的职责、所属层、关键设计权衡
   - 方法注释：说明用途、关键参数含义、返回值说明
   - **注释应解释"为什么"而非"做什么"**（用户编程原则）
   - 历史教训用 `# C-01 修复 / # F-16 / # MU1` 等版本化标记便于追溯


---

### step 9：代码修改后的编译→部署→重启流程【强制】

9. **代码修改后的编译→部署→重启流程【强制】**
   - **后端**：Python 无需编译，但需要重启 uvicorn 进程使修改生效
     - 开发模式：`scripts/automation.ps1 -Action rebuild` 或直接重启 Web 进程
     - Docker 模式：`docker compose restart` 或 `docker compose up -d --build`
   - **前端**：`cd frontend; npm run build`（产物落到 `src/xianyu_hunter/web/static/spa`）
     - 开发模式：`cd frontend; npm run dev`（HMR，无需重启后端）
     - 生产模式：构建后重启后端使 SPA 静态资源更新
   - **数据库**：修改 `db_models.py` 后必须同步修改 `init_db()` 中的迁移逻辑，下次启动自动迁移


---

### step 11：状态管理一致性【强制】

11. **状态管理一致性【强制】**
    - 状态变更操作必须同步更新所有相关字段，避免"激活但未恢复""关闭但未清除引用"等不一致状态
    - 典型场景：`activateSheet` 激活最小化 sheet 时必须同时设 `minimized: false`，否则内容区显示空状态
    - 检查方法：每个状态变更函数，列出影响的所有字段，确认全部同步更新
    - 适用范围：Zustand store 的所有操作（open/close/activate/minimize/restore），后端状态机转换


---

### step 16：事件触发时机【强制】🆕v4.0 / v4.64.0 补充

16. **事件触发时机【强制】🆕v4.0 / v4.64.0 补充**
    - "已完成"语义事件（如 `EVAL_PASSED`、`NOTIFY_SENT`、`TASK_COMPLETED`）必须在业务逻辑**完成后**触发
    - "开始"语义事件（如 `TASK_STARTED`、`EVAL_STARTED`）在业务逻辑**开始前**触发
    - **禁止**：在业务逻辑前置条件变更时就触发完成事件（如 DingTalk 通知在 AI 评估前就触发 EVAL_PASSED）
    - **判断信号**：事件名含 PASSED/SENT/COMPLETED → 后置；含 STARTED/BEGIN → 前置
    - **🆕v4.64.0 补充：PASSED 事件的"业务最终步骤"锚点**：事件名含 PASSED 时，触发点必须锚定到**业务链路的最终步骤**之后，而非"前置条件达成"或"中间状态变更"。具体判断信号：
      - `EVAL_PASSED` 必须在 **AI 评估返回结果并写入 DB** 之后触发，禁止在"评估配置加载完成"或"任务状态变为 running"时触发
      - `NOTIFY_SENT` 必须在 **通知渠道（钉钉/企微/邮件）API 返回成功** 之后触发，禁止在"通知构造完成"时触发
      - `TASK_COMPLETED` 必须在 **任务结果持久化 + 关联资源清理** 之后触发，禁止在"任务循环退出"时触发
    - **🆕v4.64.0 历史教训（钉钉通知时机 Bug）**：自动采集功能中，`startup._call_official_collect` 包装器在 `worker.py` 内触发 `EVAL_PASSED` 事件，但原触发点位于"评估配置加载完成"之后、"AI 评估实际执行"之前，导致钉钉通知在 AI 评估前就发出。修复：将 `EVAL_PASSED` 触发点移至 `effective_eval_cfg()` 计算 + AI 评估 + DB 写入全部完成之后，并通过 `EventBus` 而非直接回调触发，确保事件时机与业务最终状态对齐。详见 `worker.py` 的 `auto_collect_*` 字段与 `_call_official_collect` 包装器。
    - **🆕v4.64.0 配置驱动**：事件触发时机阈值与事件名匹配规则在 `config/tech-stack.json#hardConstraints.eventTriggerTiming` 节点管理，包含 `passedEventAnchor`（业务最终步骤锚点）/ `passedEventNamePattern`（`.*_PASSED$`）/ `forbiddenTriggerPoints`（前置条件变更/中间状态变更）等参数，禁止在业务代码中硬编码事件触发条件。


---

### step 17：字段覆盖策略（数据合并）【强制】🆕v4.0

17. **字段覆盖策略（数据合并）【强制】🆕v4.0**
    - 数据采集合并（如爬虫数据覆盖历史快照）时，按字段语义分类覆盖策略，**不能一刀切**
    - 基本信息字段（title/url/region/brand/seller_id/publish_time）：新值非空则覆盖
    - 数值类字段（price/want_cnt/view_cnt）：新值 > 0 才覆盖（防止 0 覆盖有效值）
    - 状态类字段（is_sold）：始终覆盖（状态时效性最高）
    - 标识类字段（seller_nick）：只填缺失（稳定性高，无需频繁更新）
    - **适用**：数据采集合并、缓存更新；**不适用**：审计日志（需保留全量历史）


---

### step 18：幂等性设计【强制】🆕v4.0

18. **幂等性设计【强制】🆕v4.0**
    - 资源创建接口（如 `session/start`、`task/create`）必须幂等
    - 重复调用返回当前状态 + `already_active` 标志，不重复创建资源
    - 网络重试场景必须设计幂等键或状态检查
    - **适用**：资源创建接口、网络重试；**不适用**：纯查询接口（天然幂等）、计数器递增（需去重键）


---

### step 19：搜索接口标准化【强制】🆕v4.0 / v4.64.0 升级为模板方法模式

19. **搜索接口标准化【强制】🆕v4.0 / v4.64.0 升级为模板方法模式**
    - 实时搜索接口统一参数命名：`keyword`/`q`、`page`/`offset`、`page_size`/`limit`
    - 统一响应结构：`{ items, total, page, page_size }`
    - 统一防抖间隔（搜索场景默认 400ms，通过配置管理）
    - `requestId` 竞态保护：每次请求生成 requestId，丢弃过期响应
    - **适用**：实时搜索（用户输入 + 防抖 + 流式/分页）；**不适用**：主键精确查询、固定条件列表
    - **🆕v4.64.0 升级：SearchService 模板方法模式**：当项目内出现 ≥2 个搜索接口时，必须抽取为 `SearchService` 抽象基类（`src/xianyu_hunter/web/services/search_base.py`），禁止每个接口各写一套分页/计数/响应构造逻辑。模板方法编排规则：
      - **基类 `search()` 为唯一入口**，编排 5 步流程：`_build_query` → `_execute` → `_extract_facets` → `_paginate` → `_maybe_log_slow`，子类**禁止**重写 `search()`
      - **4 个钩子由子类实现**：`_build_query(params)` 构造查询条件 / `_execute(query, params)` 执行查询返回 `(rows, total)` / `_extract_facets(rows)` 提取分面（可返回空 dict）/ `_paginate(rows, params)` 分页
      - **默认内存分页**：基类 `_paginate` 用 `rows[offset:offset+limit]` 切片；子类若已在 SQL 层分页（更高效），**必须重写 `_paginate` 直接返回 rows**，避免全量加载后再切片
    - **🆕v4.64.0 SQL 层分页优化**：大数据集（预估 >500 行）搜索必须重写 `_paginate`，在 `_execute` 内用 `LIMIT/OFFSET` 或 `WHERE id > cursor` 下推到 SQL 层，禁止依赖基类内存分页。判断信号：`_execute` 返回 `rows` 长度等于 `total` → 视为可疑（未下推）
    - **🆕v4.64.0 慢查询埋点**：基类 `_maybe_log_slow` 提供双阈值埋点（`SLOW_THRESHOLD_MS=100` 记 info / `VERY_SLOW_THRESHOLD_MS=1000` 记 warning），子类无需重写。阈值通过 `config/tech-stack.json#hardConstraints.searchServiceTemplate.slowQueryThresholdMs` 管理，禁止在子类硬编码
    - **🆕v4.64.0 统一响应结构升级**：响应从 `{items, total, page, page_size}` 升级为 `{items, total, matched_facets, query_meta}`，其中 `matched_facets` 为分面直方图（可空 dict），`query_meta` 含 `elapsed_ms` 与 `cache_hit`（当前固定 False，预留缓存扩展）。前端 types.ts 必须同步声明新字段
    - **🆕v4.64.0 文件锚点**：基类实现见 `src/xianyu_hunter/web/services/search_base.py`；具体子类见 `src/xianyu_hunter/web/services/search_services.py`；前端搜索 Hook 见 `frontend/src/hooks/useSearch.ts` 与 `frontend/src/hooks/useSearchHistory.ts`
    - **🆕v4.64.0 配置驱动**：模板方法 4 钩子名称、慢查询阈值、响应字段、防抖间隔等参数在 `config/tech-stack.json#hardConstraints.searchServiceTemplate` 节点管理，禁止在业务代码中硬编码


---

### step 20：注释与代码一致性【强制】🆕v4.0

20. **注释与代码一致性【强制】🆕v4.0**
    - 注释必须与代码逻辑**严格一致**，禁止误导性注释
    - 防御性说明需明确标注是"防御性"而非"必需"（如"顺序不影响结果，但保留防御性排列"）
    - 涉及顺序约束、依赖关系的注释需验证是否真实存在该约束
    - **历史教训**：注释称"必须在 X 之前判断避免误匹配"，但实际不存在误匹配风险，浪费维护者验证时间


---

### step 22：IIFE 反模式禁止【强制】🆕v4.0

22. **IIFE 反模式禁止【强制】🆕v4.0**
    - JSX 内禁止 IIFE（`{(() => { ... })()}`），提取为组件顶部的变量
    - JSX 中直接引用变量进行条件渲染（`{var ? <X/> : null}`）
    - **理由**：提升可读性、避免每次渲染重新创建函数、便于调试
    - **适用**：所有 JSX 中的条件渲染/计算逻辑；**不适用**：极简三元（`{a ? <X/> : null}` 可直接内联）


---

### step 25：跨字段一致性校验【强制】🆕v4.3

25. **跨字段一致性校验【强制】🆕v4.3**
    - 同一实体内多个语义相关联的字段必须在构造时校验一致性，禁止出现矛盾组合
    - **判断信号**：同一 dataclass/dict/type 中存在语义关联字段对（如 `gpu_vendor`+`gpu_renderer`、`valid`+`written_count`、`layer`+`cookies` 分层定义）
    - **修复模式**：在 `__post_init__` / 构造函数 / 工厂函数中校验关联字段一致性，不一致时抛 `ValueError`
    - **适用**：指纹/配置/状态数据结构、Cookie 分层定义、前后端 DTO 字段对齐
    - **不适用**：独立无关联字段、运行时动态拼装的临时对象
    - **历史教训**：`fingerprint.py` Profile 2 的 `gpu_vendor="Intel Inc."` 配 `gpu_renderer="AMD Radeon RX 6600"`，真实 Chrome 中应为 `Google Inc. (AMD)`，被 AWSC fireyejs 识破


---

### step 27：死代码与资源生命周期【强制】🆕v4.3

27. **死代码与资源生命周期【强制】🆕v4.3**
    - 创建的长期存活对象（Proxy/Observer/Listener/Task）必须赋值给有生命周期的变量（实例属性/模块级变量），**禁止**赋值给局部变量后丢弃
    - `try/finally` 块中使用的变量必须在 `try` 之前初始化为 `None`，确保 `finally` 不会因未绑定而抛 `UnboundLocalError`
    - **判断信号**：`new Proxy()` / `new MutationObserver()` / `asyncio.create_task()` 的返回值赋值给局部变量；`try` 块内赋值的变量在 `finally` 中被引用
    - **修复模式**：监听器赋值给实例属性（`self._observer = new MutationObserver(...)`）；资源变量 `page = None` 前置初始化
    - **适用**：所有需要长期存活的监听器/观察者/后台任务；所有 try/finally 资源清理
    - **不适用**：一次性使用的临时对象、`with` 语句（自动管理生命周期）
    - **历史教训**：`awsc_spoof.py` 的 `var baxiaProxy = new Proxy(...)` 赋值给局部变量后从未使用，验证码触发事件永远不会被派发；`api_anticrawl.py` 的 `renew_callback` 中 `page` 变量未初始化，`new_page()` 抛异常时 `finally` 中 `page.close()` 报 `UnboundLocalError`


---

### step 29：提示信息可操作性【强制】🆕v4.3

29. **提示信息可操作性【强制】🆕v4.3**
    - 面向用户的错误提示中引用的端点/方法/配置项/页面路径必须实际存在，提示应指向可操作的修复路径
    - **判断信号**：错误信息中包含 URL/方法名/配置项/路由路径引用
    - **修复模式**：提示中只引用已实现的端点；引用路由路径时确认前端路由已注册；提供具体的修复操作（如"请点击 X 按钮重新初始化"）
    - **适用**：所有面向用户的错误信息（API 响应、前端错误提示、日志中的用户指引）
    - **不适用**：内部调试日志（developer-facing）、堆栈跟踪
    - **历史教训**：`/api/anticrawl/health` 端点提示"请先调用 /api/anticrawl/health/configure"，但该端点从未实现，用户无法按提示操作


---

### step 41：快速模式降级重试【强制】🆕v4.5

41. **快速模式降级重试【强制】🆕v4.5**
    - `fast=True` 模式跳过恢复机制（token 刷新、RGV587 重试）时，调用方应在 fast 失败后自动以非 fast 模式重试一次
    - **判断信号**：方法签名含 `fast=True` 参数且 fast 模式跳过 `_ensure_fresh_*` / `*_retry` 逻辑 → 调用方必须检查 fast 返回结果的状态标志，失败时降级重试
    - **修复模式**：`fast=True` 返回空结果且状态标志（如 `last_session_invalid=True`）指示可恢复 → 自动以 `fast=False` 重试 → 重试成功则正常返回结果，失败才报错 → 重试超时应放宽以容纳 token 刷新 + 搜索
    - **配置参数**：降级重试超时（默认 45s，含 token 刷新 ~15s + 搜索 ~30s）在 `config.yaml` 的 `search` 节点管理
    - **适用**：所有 fast/quick 模式接口（跳过恢复机制的快速路径），尤其是实时搜索、快速预览
    - **不适用**：纯查询接口（无副作用）、实时性要求极高的接口（如心跳检测）、重试成本过高的操作
    - **历史教训**：实时搜索用 `fast=True` 完全跳过 `_ensure_fresh_m5tk()` 和 RGV587 重试，刚登录后第一次搜索碰巧 token 有效成功，后续连续请求时 token 过期全部失败。修复后 `live_links` 端点在 fast 搜索返回空结果且 `last_session_invalid=True` 时自动以 `fast=False` 重试一次


---

### step 43：参数透传链路完整性【强制】🆕v4.5

43. **参数透传链路完整性【强制】🆕v4.5**
    - 方法签名新增参数时，必须同步更新所有内部调用点传递该参数，**禁止**只在外层方法签名添加而内部调用点遗漏
    - **判断信号**：`git diff` 显示方法签名新增参数 → 必须 grep 方法名检查所有调用点（包括内部 `_private` 方法的调用）是否传递新参数
    - **检查方法**：从方法签名 → 内部调用 `_call_xxx(new_param=new_param)` → 内部调用 `build_url(new_param=new_param)` → 最终 URL 查询参数追加，逐层验证
    - **适用**：方法签名新增参数后的所有内部调用点，尤其是跨层参数传递（API → Module → Domain → URL Builder）
    - **不适用**：向后兼容的可选参数（有默认值且不影响现有行为）
    - **历史教训**：`search()` 方法新增 `sort_type`/`regions` 参数后，`_call_search_api()` 内部第 470 行 `build_search_url(keyword)` 未传 `sort_type`/`regions`，导致 RGV587 重试时 URL 中丢失排序和地区参数。`build_search_url` 本身也不支持这两个参数


---

### step 52：数据流转完整性 5 点追踪【强制】🆕v4.7

52. **数据流转完整性 5 点追踪【强制】🆕v4.7**
    - 用户反馈"某字段为空/显示异常"类问题时，必须按 **DB schema → Repo 查询过滤 → API 注入 → 前端 types → render 取值** 5 点逐层追踪根因，**禁止**只看前端代码或只查后端代码
    - **判断信号**：用户反馈"字段为空/数据丢失/显示异常" → 必须从 DB 原始数据开始逐层验证，每层都打印中间值
    - **追踪流程**：
      1. **DB schema**：用 `sqlite3` / DB 客户端查询原始数据，确认数据是否存在（如 `SELECT * FROM orders WHERE item_id = ?`）
      2. **Repo 查询过滤**：检查 Repo 层查询是否有 `WHERE`/`if status == 'failed': continue` 等过滤逻辑，确认数据是否被过滤
      3. **API 注入**：检查 API 路由层是否正确调用 Repo 并将数据注入响应（如 `order_map = container.repo.list_orders_by_item_ids(ids, include_failed=True)`）
      4. **前端 types**：检查 `frontend/src/api/types.ts` 中类型定义是否包含该字段（如 `order_status?: string`）
      5. **render 取值**：检查前端组件是否正确从响应中取值并渲染（如 `record.order?.status || '—'`）
    - **关键约束**：
      - 5 点必须**逐层验证**，不能跳过任何一层
      - 每层验证必须**打印中间值**（如 `print(order_map)` / `console.log(record.order)`），不能凭推断
      - 找到根因后必须**修复根因**而非绕过（如 Repo 过滤逻辑错误应修 Repo，而非 API 层重新查询）
      - 修复后必须**回归测试**覆盖该场景（如新增 `test_list_orders_by_item_ids_failed_filter`）
    - **配置参数**：`trace_nodes`（5 个节点的标识）、`required_fields`（必检字段列表）、`null_value_check`（是否检查 null 值）在 `config.yaml` 的 `data_flow_trace` 节点管理
    - **适用**：所有"字段为空/显示异常/数据丢失"类根因定位，尤其是涉及前后端多层的字段
    - **不适用**：UI 样式问题（如颜色/布局错误）、纯前端计算字段（如 `total = price * quantity`）、权限不足导致字段隐藏
    - **历史教训**：评估明细页"订单"列显示 "—"，根因是 `repo_orders.list_orders_by_item_ids` 无条件 `if status == 'failed': continue`，但 API 层评估明细调用未传 `include_failed=True`。数据库中实际有 3 条 failed 订单，但全部被 Repo 层过滤。修复后 API 返回 `order_status=failed`（之前为 `null`）


---

### step 54：复用既有模式原则【强制】🆕v4.7

54. **复用既有模式原则【强制】🆕v4.7**
    - 新增功能前必须先 `grep` 项目内相似实现，复用既有 helper / 工具函数 / 模式（如 `_utcnow` / `_escape_like` / `hmac.compare_digest` / `asyncio.wait_for` / `logger.warning`），**禁止**重复造轮子或实现已有模式的变体
    - **判断信号**：新增函数 + `grep` 发现已有相似命名/相似参数/相似功能的函数 → 必须复用而非重复实现；新增异步操作未复用 `asyncio.wait_for` 模式 → 视为违规
    - **修复模式**：
      1. **搜索阶段**：`grep -rn "<相似关键词>" src/ frontend/src/` 查找已有实现
      2. **评估阶段**：对比新增函数与已有函数的差异，判断是否可复用（参数差异 / 返回值差异 / 副作用差异）
      3. **复用阶段**：直接调用已有函数 / 抽取公共部分为 helper / 在已有函数上增加参数
      4. **文档阶段**：在新增函数 docstring 中说明"为什么不复用 X"（如适用）
    - **关键约束**：
      - 复用优先级：**项目内 helper > 标准库 > 第三方库 > 新实现**
      - 复用必须**保持一致性**：调用方式、参数命名、返回值格式与已有函数一致
      - 若已有函数不完全满足需求，应**扩展已有函数**而非新建（参考 step 53 参数化场景标志）
      - 必须复用的常见模式：`asyncio.wait_for`（异步超时）、`hmac.compare_digest`（凭据比较）、`_escape_like`（SQL LIKE 转义）、`_utcnow`（UTC 时间）、`logger.warning`（告警日志）
    - **配置参数**：`search_keywords`（必须搜索的关键词列表）、`similarity_threshold`（默认 0.7，相似度高于此值时强制复用）、`reuse_priority`（复用优先级顺序）在 `config.yaml` 的 `reuse_pattern` 节点管理
    - **适用**：所有新增功能 / 工具函数 / 帮助类 / 异步操作 / 安全相关代码
    - **不适用**：业务完全独立的全新功能、性能优化重写、技术债清理重构
    - **历史教训**：`refresh_item` 直接 `await collector.detail()` 而未复用 v4.4 的 fast 模式重试机制（`fast=False` 重试一次），也未加 `asyncio.wait_for` 整体超时（step 50 规范），导致浏览器异常时无限挂起。修复时复用 `asyncio.wait_for` 模式 + 504 状态码（与 v4.1 错误粒度三类区分一致）


---

### step 62：双链路一致性规范【强制】🆕v4.10

62. **双链路一致性规范【强制】🆕v4.10**
    - 同一业务目标有 ≥2 条执行链路时（如 Worker 调度链路 + Live 实时链路都到达「下单」），共用前置条件必须提取为独立函数，两条链路调用同一函数，**禁止**各自实现
    - **关键约束**：
      1. **共用前置条件提取**：价格过滤/分数校验/库存检查等前置条件提取为独立函数（如 `_build_price_strategy(task) -> PriceStrategy`）
      2. **两链路调用同一函数**：Worker 链路和 Live 链路必须调用同一函数，**禁止**各自实现相似逻辑
      3. **过滤范围明确**：前置条件过滤仅阻止「执行动作」（如抢单），不阻止「评估写库」（评估结果仍写入 DB 供后续分析）
      4. **grep 验证**：修改后必须 `grep` 验证两条链路确实调用同一函数，禁止遗漏
      5. **测试覆盖**：必须新增测试覆盖两条链路的前置条件一致性
    - **判断信号**：同一业务目标（如「下单」「采集」「通知」）有 ≥2 条执行链路 → 必须按此流程设计
    - **修复模式**：
      ```python
      # ✅ 提取共用前置条件为独立函数
      def _build_price_strategy(task: Task) -> PriceStrategy:
          """构建价格策略，Worker 和 Live 链路共用"""
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
    - **配置参数**：`dual_link.target_entities`（业务目标列表，如 `["buy", "collect", "notify"]`）、`dual_link.shared_predicate_patterns`（共用前置条件函数命名模式，如 `_build_*_strategy`）、`dual_link.verify_callers`（是否启用 grep 验证，默认 `true`）在 `config.yaml` 的 `dual_link_consistency` 节点管理
    - **适用**：同一业务目标有多个触发入口（如 Worker 调度 + Live 实时 + API 手动 + CLI 命令）
    - **不适用**：单一入口的业务（如只有 API 触发）；链路间业务逻辑本就不同（如 Worker 是异步批量，Live 是同步单条）——此时应抽取「共同部分」为函数，「差异部分」各自处理
    - **历史教训**：Worker 链路调用 `PriceStrategy.is_acceptable()` 做价格过滤，Live 链路只看分数达标不做价格过滤，导致两条链路行为不一致——Worker 链路过滤掉的高价商品在 Live 链路被下单。修复后提取 `_build_live_price_strategy` 共用函数，两链路调用同一函数


---

### step 64：Python 现代化规范【强制】🆕v4.10

64. **Python 现代化规范【强制】🆕v4.10**
    - Python 3.10+ 项目必须使用现代 asyncio API 与 dataclass 语法，**禁止**使用过时 API
    - **关键约束**：
      1. **asyncio.create_task 替代 get_event_loop**：`asyncio.create_task(coro)` 替代 `asyncio.get_event_loop().create_task(coro)`；在协程内获取事件循环用 `asyncio.get_running_loop()`（明确表示运行中循环），**禁止** `asyncio.get_event_loop()`（Python 3.10+ 已弃用，且在无运行循环时会创建新循环导致行为不可预期）
      2. **避免 getattr 兜底 dataclass 字段**：dataclass 字段必须显式声明默认值，**禁止**用 `getattr(obj, 'field', default)` 兜底未声明字段（掩盖字段未初始化 bug）；仅在处理「外部输入的动态属性」（如 JSON 解析结果）时才允许 getattr
      3. **模块级 import**：所有 import 必须在模块顶部，**禁止**函数内重复 import（除非解决循环依赖的延迟导入）
      4. **CancelledError 传播**：`asyncio.CancelledError` 必须用 `contextlib.suppress(asyncio.CancelledError)` 包裹 await 并向上传播，**禁止** `except: pass` 静默吞掉
      5. **类型注解现代语法**：`X | None` 替代 `Optional[X]`，`list[T]` 替代 `List[T]`，`dict[K, V]` 替代 `Dict[K, V]`
    - **判断信号**：Python 3.10+ 代码 + 使用 asyncio / dataclass → 必须按此规范
    - **修复模式**：
      ```python
      # ✅ 现代 asyncio API
      _scheduler_task = asyncio.create_task(_scheduler_loop())  # ✅
      # ❌ loop = asyncio.get_event_loop(); loop.create_task(...)  # 过时

      # ✅ dataclass 字段显式声明
      @dataclass
      class _WorkerHandle:
          consecutive_errors: int = 0  # ✅
      # ❌ h.consecutive_errors = getattr(h, 'consecutive_errors', 0) + 1  # 兜底反模式

      # ✅ CancelledError 传播
      from contextlib import suppress
      try:
          await task
      except asyncio.CancelledError:
          logger.info("任务被取消")
          raise  # 必须向上传播
      ```
    - **配置参数**：`modern_python.min_version`（默认 `"3.10"`）、`modern_python.deprecated_apis`（禁用 API 列表：`get_event_loop`/`utcnow`/`Optional`/`List`/`Dict`）、`modern_python.required_imports_at_module_level`（强制模块级导入的模块列表）在 `config.yaml` 的 `python_modern` 节点管理
    - **适用**：Python 3.10+ 项目；使用 asyncio 的代码；使用 dataclass 的领域模型
    - **不适用**：Python 3.9 及以下（部分语法不支持）；同步代码（无 asyncio）；非 dataclass 类
    - **历史教训**：`startup.py` 用 `asyncio.get_event_loop().create_task()` 创建后台任务（过时 API），且函数内重复 `import asyncio`；`_WorkerHandle` 用 `getattr` 兜底 `consecutive_errors` 字段。修复后改为 `asyncio.create_task()` + 模块级 import + 显式字段声明


---

### step 67：日志库占位符一致性规范【强制】🆕v4.11

67. **日志库占位符一致性规范【强制】🆕v4.11**
    - 项目选定单一日志库后（如 loguru），所有 `logger.xxx()` 调用必须使用该库的占位符语法，**禁止**混用其他日志库的占位符（如 loguru 用 `{}`，标准 logging 用 `%s`/`%d`）
    - **关键约束**：
      1. **loguru 占位符**：`logger.info("用户 {} 操作 {}", user, action)` 用 `{}`，**禁止** `logger.info("用户 %s 操作 %s", user, action)`（混用不抛异常但显示 `%s` 字面量，极难发现）
      2. **标准 logging 占位符**：`logging.info("用户 %s 操作 %s", user, action)` 用 `%s`/`%d`/`%r`/`%f`，**禁止** `logging.info("用户 {} 操作 {}", user, action)`
      3. **f-string 例外**：简单变量拼接可用 f-string（如 `logger.info(f"用户 {user} 操作")`），但复杂格式推荐用占位符（性能更好，延迟格式化）
      4. **诊断方法**：`grep -nE 'logger\\.(debug|info|warning|error|critical).*%[sdrf]' file.py` 在 logger 调用行附近即发现 loguru 项目混用 `%s` 的违规
    - **判断信号**：
      - 项目用 loguru（`from loguru import logger`）但代码含 `logger.xxx("...%s...", arg)` → 视为违规
      - 项目用标准 logging 但代码含 `logger.xxx("...{}...", arg)` → 视为违规
      - 日志输出含 `%s`/`%d` 字面量而非实际值 → 典型症状
    - **修复模式**：
      ```python
      # ✅ loguru：{} 占位符
      from loguru import logger
      logger.info("用户 {} 登录，耗时 {:.2f}s", user, elapsed)  # loguru 原生
      logger.warning("Cookie 刷新失败，原因：{}", reason)

      # ❌ 错误：loguru 项目混用 %s
      logger.info("用户 %s 登录", user)  # 输出"用户 %s 登录"字面量
      logger.warning("Cookie 刷新失败，原因：%s", reason)

      # ✅ 标准 logging：%s 占位符
      import logging
      logger = logging.getLogger(__name__)
      logger.info("用户 %s 登录", user)

      # ✅ f-string 例外（简单拼接可用）
      logger.info(f"用户 {user} 登录")
      ```
    - **配置参数**：`log_placeholder.logger_lib`（默认 `loguru`，可选 `logging`/`structlog`）、`log_placeholder.placeholder_pattern`（默认 `\\{\\}` 对 loguru，`%[sdrf]` 对 logging）、`log_placeholder.forbidden_pattern`（默认 `%[sdrf]` 对 loguru 项目）、`log_placeholder.logger_method_names`（默认 `["debug", "info", "warning", "error", "critical"]`）、`log_placeholder.allow_fstring`（默认 `true`，允许简单 f-string 拼接）在 `config.yaml` 的 `log_placeholder` 节点管理
    - **适用**：所有用 loguru/standard logging/structlog 的项目；混用多个日志库的项目（需统一到单一日志库）
    - **不适用**：未使用日志库的项目（如仅用 print）；自定义日志库（需在配置中声明占位符语法）
    - **历史教训**：`cookie_rotator.py` 第 197、245 行用 `logger.warning("...%s...", reason)`（loguru 项目混用 `%s`），loguru 不识别 `%s` 占位符但不抛异常，导致日志输出"Cookie 刷新失败，原因：%s"字面量。修复后改为 `logger.warning("...{}", reason)`


---

### step 75：文本数值提取模式【强制】🆕v4.12

75. **文本数值提取模式【强制】🆕v4.12**
    - 从可能含多个数字的文本中提取数值时，必须用 `re.findall` 取 `numbers[-1]`（最后一个数字），**禁止** `re.search` 取第一个数字，因实际成交价/当前值通常出现在最后（如"原价 1000 现价 500"应取 500）
    - **判断信号**：代码含 `re.search(r"\d+", text)` 或 `re.match(r"\d+", text)` 提取数值 → 必须评估文本是否可能含多数字，是则改为 `re.findall`
    - **修复模式**：
      ```python
      # ✅ 取最后一个数字（实际成交价）
      import re
      text = "原价 1000 现价 500"
      numbers = re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))
      if numbers:
          actual_price = float(numbers[-1])  # 500，正确

      # ❌ 错误：取第一个数字（误取原价）
      # m = re.search(r"\d+(?:\.\d+)?", text)
      # if m: actual_price = float(m.group())  # 1000，错误
      ```
    - **配置参数**：`numeric_extraction_strategy.default_strategy`（默认 `last`，可选 `first`/`max`/`min`）、`numeric_extraction_strategy.scenarios`（场景到策略的映射，如 `price_extraction → last`、`quantity_extraction → first`）、`numeric_extraction_strategy.regex_pattern`（默认 `r"\d+(?:\.\d+)?"`）在 `config.yaml` 的 `numeric_extraction_strategy` 节点管理
    - **适用**：从自由文本提取数值（价格/数量/评分/版本号）；多数字场景（"原价 X 现价 Y"、"最小 X 最大 Y"）
    - **不适用**：单一数字文本（如纯数字字符串 "123"）；结构化数据（JSON 字段直接取值）；有明确位置的文本（如"价格:X"用 `re.search(r"价格:\s*(\d+)", text)` 分组提取）
    - **历史教训**：`_extract_actual_price` 用 `re.search` 取第一个数字，订单页文本为"原价 1000 现价 500"时误取 1000，导致价格校验失败抢单被拒


---

### step 94：前后端字段契约对齐规范【强制】🆕v4.17

**背景**：前端 types.ts 声明 `damages`/`inconsistencies` 字段，但后端 `_normalize_deep_result` 显式归并到 `signals`，导致前端通过 `check[signalKey]` 动态取值永远拿到 undefined。

**规范**：
1. 后端对 LLM/外部响应做归一化（合并/重命名/转换字段）时，必须在前端 types.ts 对应字段声明中加注释 `// 后端已归一化，前端消费 X 字段`
2. types.ts 中保留旧字段名时必须标 optional 并加注释 `// 仅作兼容保留，后端不返回`
3. 前端禁止通过动态 key（如 `check[signalKey]`）取归一化字段，必须直接用归一化后的字段名（如 `check.signals`）

**判断逻辑**：
- grep 后端源码查看是否有 `_normalize` / `_unify` / `_merge` / `_flatten` 等归一化函数
- 有则同步检查前端 types.ts 声明是否与归一化结果对齐
- grep 前端 `as string[] | undefined` 等动态类型转换，确认是否在取归一化字段

**反例**：
```typescript
// ❌ 错误：signalKey 动态取值，后端归一化后 damages 永远 undefined
const signals = (check[signalKey] as string[] | undefined) ?? []
```

**正例**：
```typescript
// ✅ 正确：直接用归一化字段
const signals = check.signals ?? []
```

**配置参数**：`field_contract_align` 节点（enabled / require_doc_comment / detect_dynamic_key_access / fallback_to_legacy_field）

**适用场景**：后端有 `_normalize` / `_unify` / `_merge` / `_flatten` 等字段转换函数 + 前端通过动态 key 取值
**不适用场景**：后端直接返回原始响应无转换；前端类型声明与后端 pydantic 模型一一对应


---

### step 106：事件发布完整性规范【强制】🆕v4.19

**背景**：`EventType` 枚举中定义了 `EVAL_PASSED` 事件，`NotifierHub` 的 `DEFAULT_NOTIFY_EVENTS` 也包含 `EVAL_PASSED`，但 `worker.py` 评估通过后只写 events 表，**不发布** `EVAL_PASSED` 事件到 EventBus，订阅端永远收不到事件，通知永远不发送。这是"设计-实现断层"的典型——定义了事件类型但无发布点。

**规范**：

1. **`EventType` 枚举中定义的事件必须在业务逻辑中实际发布**
   - 定义事件类型后必须 grep 所有发布点（`event_bus.publish`）
   - 订阅集（如 `DEFAULT_NOTIFY_EVENTS`）中的事件必须有对应的发布点
   - 无发布点的事件类型视为"设计-实现断层"，必须在文档中标注"未实现"或删除

2. **业务状态变更后必须发布对应事件**
   - 评估通过 → 发布 `EVAL_PASSED`
   - 抢单成功 → 发布 `BUY_SUCCEEDED`
   - 抢单失败 → 发布 `BUY_FAILED`
   - 任务完成 → 发布 `TASK_COMPLETED`

3. **事件发布与数据库写入必须分离**
   - 数据库写入（events 表）是持久化记录
   - 事件发布（EventBus）是实时通知
   - 两者不能互相替代：写库不等于发布事件

4. **事件发布完整性必须用集成测试验证**
   - 测试用例：触发业务状态变更 → 验证 EventBus 收到对应事件
   - 测试必须覆盖所有 `DEFAULT_NOTIFY_EVENTS` 中的事件

5. **事件发布点必须配置驱动**
   - 业务状态到事件类型的映射在 `config.yaml` 的 `event_publish_mapping` 节点管理
   - 订阅集（如 `DEFAULT_NOTIFY_EVENTS`）在 `notifier.subscribed_events` 节点管理
   - **禁止**硬编码订阅集在代码中（应从 config 读取，便于动态调整）

**判断逻辑**：

- `grep "EventType\." src/xianyu_hunter/` 找到所有事件类型定义 → 每个事件必须有 `event_bus.publish(EventType.XXX)` 发布点
- `grep "DEFAULT_NOTIFY_EVENTS\|subscribed_events" src/xianyu_hunter/` 找到订阅集 → 每个订阅事件必须有发布点
- 业务状态变更代码（如 `if eval_passed:`）后无 `event_bus.publish()` → 视为违规
- 订阅集硬编码在代码中而非 config.yaml → 视为可疑

**反例**：

```python
# ❌ 错误：评估通过后只写库不发布事件
async def evaluate(self, task_id: str):
    score = await self._calculate_score(task_id)
    if score >= self.pass_score:
        # 写库但不发布事件
        await self.event_repo.create(
            task_id=task_id,
            event_type="eval_passed",
            payload={"score": score},
        )
        # 缺少：await self.event_bus.publish(EventType.EVAL_PASSED, {...})
```

**正例**：

```python
# ✅ 业务状态变更后同时写库和发布事件
async def evaluate(self, task_id: str):
    score = await self._calculate_score(task_id)
    if score >= self.pass_score:
        # 1. 写库（持久化记录）
        await self.event_repo.create(
            task_id=task_id,
            event_type="eval_passed",
            payload={"score": score},
        )
        # 2. 发布事件（实时通知）
        await self.event_bus.publish(EventType.EVAL_PASSED, {
            "task_id": task_id,
            "score": score,
        })
```

**配置参数**：`event_publish_mapping` 节点（business_state_to_event / require_publish_for_subscribed / require_integration_test）

**适用场景**：
- 所有 `EventType` 枚举中定义的事件
- 业务状态变更需通知订阅方的场景
- 事件驱动架构（EDA）的系统

**不适用场景**：
- 内部状态变更（无需通知订阅方）
- 高频事件（如心跳检测，应直接调用而非事件发布）
- 一次性任务（如启动初始化）

**历史教训**：`EventType.EVAL_PASSED` 在枚举中定义，`DEFAULT_NOTIFY_EVENTS` 包含该事件，但 `worker.py` 评估通过后只写 events 表，不发布事件到 EventBus，订阅端永远收不到，自动抢单后通知永远不发送（用户反馈"自动抢单后未发送钉钉通知"）。修复后业务状态变更同时写库和发布事件


---

### step 130：事件类型过滤精确匹配规范【强制】🆕v4.29

**背景**：业务系统通常用 `type` 字段标记事件类别（如 `eval.scored`/`eval.passed`/`notify.sent`），代码中常用 `startswith('eval.')` 做前缀过滤，但同一前缀下可能有多个事件类型，前缀过滤会误包含不相关事件，导致统计偏差或列表混入无效记录。

**问题**：`NotifierHub` 推送时写入 `type='eval.passed'`、`payload=None` 的事件到 events 表（用于 KPI 统计），但 `api_evaluations.py` 的 `_collect_dist_eval_records` 和 `list_evaluations` 用 `event.type.startswith('eval.')` 过滤，误包含 `eval.passed` 通知事件，导致评估明细列表混入 227+ 条空记录（`payload=None`），用户看到「213 条仅基于价格的评估记录」和大量空行。

**规范**：

1. **事件类型过滤必须精确匹配【强制】**：业务查询事件类型时必须用 `==` 精确匹配，**禁止**用 `startswith` / `endswith` / `in` 做前缀/后缀/子串过滤，除非明确需要前缀分组（如统计所有 `eval.*` 事件）：
   ```python
   # ✅ 正确：精确匹配目标事件类型
   events = [e for e in all_events if e.type == 'eval.scored']

   # ❌ 错误：startswith 前缀过滤，误包含 eval.passed/eval.failed/eval.notified
   # events = [e for e in all_events if e.type.startswith('eval.')]
   ```

2. **通知事件与业务事件分离【强制】**：通知/审计类事件（如 `eval.passed` 仅用于 KPI 统计）必须与业务查询事件（如 `eval.scored` 用于评估明细）使用不同的 type 前缀或命名空间：
   ```python
   # ✅ 正确：通知事件用 notify.* 前缀，业务事件用 eval.* 前缀
   EventType.EVAL_SCORED = 'eval.scored'  # 业务事件：评估明细查询
   EventType.NOTIFY_SENT = 'notify.sent'  # 通知事件：KPI 统计

   # ❌ 错误：通知事件也用 eval.* 前缀，与业务事件混淆
   # EventType.EVAL_PASSED = 'eval.passed'  # 通知事件，但前缀与业务事件相同
   ```

3. **前缀分组仅限统计场景【强制】**：仅在统计聚合（如「所有 eval.* 事件总数」）场景允许 `startswith`，且必须注释说明包含的所有子类型：
   ```python
   # ✅ 正确：统计场景用 startswith 并注释包含的子类型
   # 包含 eval.scored / eval.passed / eval.failed 三类事件
   eval_total = sum(1 for e in events if e.type.startswith('eval.'))
   ```

**配置驱动**：事件类型过滤规则、精确匹配字段清单、前缀分组白名单等参数在 `config.yaml` 的 `event_filtering` 节点管理，包含 `strict_match_required` / `strict_match_fields` / `prefix_grouping_whitelist` / `event_namespace_separation` 等，不硬编码在技能中。

**适用场景**：
- 业务事件查询（评估明细/订单列表/任务列表）
- KPI 统计（按事件类型计数）
- 事件订阅（EventBus 订阅特定事件）

**不适用场景**：
- 全量事件导出（无需过滤）
- 日志搜索（模糊匹配是预期行为）
- 调试查询（临时性，非生产代码）

**历史教训**：`NotifierHub` 写入 `type='eval.passed'`、`payload=None` 的事件用于 KPI 统计，但 `api_evaluations.py` 用 `startswith('eval.')` 过滤评估明细列表，误包含 227+ 条通知事件，用户看到「213 条仅基于价格的评估记录」和大量空行。修复：将过滤条件改为 `== 'eval.scored'`，评估明细从 280 条减到 47 条有效记录。

**判断信号（review 触发条件）**：
- `grep "startswith" <file>` 出现在事件/记录过滤逻辑中 → 视为可疑
- `grep "endswith" <file>` 出现在事件/记录过滤逻辑中 → 视为可疑
- 业务列表混入 `payload=None` 的空记录 → 必然违规
- 事件 type 命名空间冲突（通知事件与业务事件同前缀）→ 视为违规


---

### step 132：服务重启验证清单规范【强制】🆕v4.29

**背景**：Python 后端代码修改后必须重启服务才能生效（除非启用 `--reload`），但开发者常误以为「修改即生效」，导致用户反馈「修复无效」实则服务未重启。此外，重启后缺少验证步骤，可能引入新问题未被发现。

**问题**：
1. 修改 `api_anticrawl.py` 后未重启服务，用户反馈「会话管理仍未自动启动」，实际代码已修复但服务跑的是旧代码
2. 重启后未验证端口监听，导致 uvicorn 启动失败但用户以为服务正常运行
3. 重启后未验证关键数据状态（如 cookie 层状态/任务调度器状态），导致新问题被延迟发现

**规范**：

1. **修改后必须重启【强制】**：Python 后端代码修改后必须重启服务，**禁止**认为「修改即生效」：
   ```bash
   # 重启命令（PowerShell）
   # 方式 1：停止旧进程 + 启动新进程
   Stop-Process -Name python -Force -ErrorAction SilentlyContinue
   python -m xianyu_hunter web --with-scheduler

   # 方式 2：用 scripts/automation.ps1
   .\scripts\automation.ps1 -Action rebuild
   ```

2. **重启后验证清单【强制】**：重启后必须按清单验证服务状态：
   ```bash
   # 1. 端口监听验证
   netstat -ano | findstr :8000  # 确认 uvicorn 在 8000 端口监听

   # 2. 健康检查
   curl http://127.0.0.1:8000/api/about  # 确认返回 200 + 版本信息

   # 3. 关键数据状态验证（按修改的模块选择性验证）
   curl http://127.0.0.1:8000/api/anticrawl/cookies/layers  # Cookie 层状态
   curl http://127.0.0.1:8000/api/tasks  # 任务列表
   curl http://127.0.0.1:8000/api/scheduler/status  # 调度器状态
   ```

3. **重启日志确认【强制】**：重启后必须查看启动日志，确认无 `ImportError`/`OperationalError`/`AttributeError`：
   ```bash
   # 查看启动日志
   Get-Content logs/startup.log -Tail 50
   # 关键确认点：
   # - "Application startup complete." 出现
   # - 无 "ImportError" / "ModuleNotFoundError"
   # - 无 "OperationalError" (DB 迁移问题)
   # - 无 "AttributeError" (类属性问题)
   # - 调度器启动日志 "Scheduler started" 出现
   # - 关钩子日志 "反爬会话管理已尝试自动启动" 出现（如修改了 startup.py）
   ```

4. **前端构建后必须刷新浏览器【强制】**：前端代码修改后必须 `npm run build` + 强制刷新浏览器（Ctrl+Shift+R 清除 PWA Service Worker 缓存）：
   ```bash
   # 前端构建
   cd frontend
   npm run build

   # 浏览器强制刷新（用户操作）
   # Ctrl+Shift+R 或 DevTools → Application → Service Workers → Unregister
   ```

**配置驱动**：重启验证清单、健康检查端点、关键日志关键词等参数在 `config.yaml` 的 `post_restart` 节点管理，包含 `checklist` / `health_check_endpoints` / `startup_log_keywords` / `frontend_build_required` 等，不硬编码在技能中。

**适用场景**：
- Python 后端代码修改后（任何 .py 文件）
- 前端代码修改后（需要 build + 浏览器刷新）
- 配置文件修改后（config.yaml/.env）
- 数据库迁移后

**不适用场景**：
- 启用 `--reload` 的开发环境（uvicorn 自动重载）
- 纯文档修改（无代码变更）
- 测试代码修改（无需重启生产服务）

**历史教训**：
- 修改 `api_anticrawl.py` 添加会话自动启动钩子后未重启服务，用户反馈「会话管理仍未自动启动」，实际代码已修复但服务跑的是旧代码。重启后日志显示「反爬会话管理已尝试自动启动」，问题解决
- 修改 `cookie_rotator.py` 后重启服务但未验证端口监听，uvicorn 因端口占用启动失败但用户以为服务正常，导致后续操作全部 502
- 修改前端 `AntiCrawl/index.tsx` 按钮文案后未强制刷新浏览器，PWA Service Worker 缓存导致用户看到的仍是旧文案

**判断信号（review 触发条件）**：
- 用户反馈「修复无效」但代码已修改 → 检查服务是否重启
- 用户反馈「前端无变化」但代码已 build → 检查浏览器是否强制刷新
- 重启后未执行健康检查 → 视为流程缺失
- 启动日志含 `ImportError`/`OperationalError` 但未停止服务排查 → 视为违规


---

### step 171：NAMING-01 命名一致性与歧义消除规范【强制】🆕v4.29

**背景**：Python 私有属性 `_session` 与 `_Session` 大小写不一致导致 `AttributeError`；变量名 `data` / `info` / `result` 语义模糊，无法表达具体业务含义；同一概念多处用不同命名（`task_id` / `taskId` / `id`）导致认知负担。

**问题**：命名不一致与语义模糊导致代码可读性差、IDE 自动补全误导、运行时 AttributeError；同一概念多处命名不同增加维护成本。

**规范**：

1. **命名大小写一致性【强制】**：变量/属性命名在赋值与引用处必须严格大小写一致，私有属性（`_` 开头）必须全小写（Python 惯例）：
   ```python
   # ✅ 正确：赋值和引用大小写一致
   self._session = self._build_session()
   def get(self): return self._session()

   # ❌ 错误：大小写不一致
   # self._session = ...
   # def get(self): return self._Session()  # AttributeError
   ```

2. **命名语义明确【强制】**：变量名必须表达具体业务含义，禁止用 `data` / `info` / `result` / `temp` 等无语义命名，必须用 `task_list` / `cookie_layer` / `refresh_result` 等业务命名。

3. **同一概念统一命名【强制】**：同一概念在全代码库必须用统一命名（含大小写/下划线/前后缀），如 `task_id` 统一用 snake_case，禁止 `taskId` / `TaskId` / `id` 混用。

**配置驱动**：`coding_standards.naming.case_sensitive`（`true`）、`forbid_vague_names`（`['data', 'info', 'result', 'temp']`）在 `config.yaml` 管理。

**适用场景**：
- Python 私有属性命名
- 变量/函数/类命名
- 跨模块共享概念的命名

**不适用场景**：
- 第三方库的命名（无法控制）
- 临时调试变量（如 `x` / `y` 用于测试）

**历史教训**：`api_chatbot_config.py:343` 引用 `self._Session()` 但定义的是 `self._session`，运行时 `AttributeError`；`api_task_links.py` 用 `total` 但前端期望 `total_for_type`，前端显示「0 条」。

**判断信号（review 触发条件）**：
- `grep "_[A-Z]" <file>` 出现大写开头的私有属性引用
- `grep "data\|info\|result" <file>` 出现无语义变量名
- 同一概念在多个文件用不同命名


---

### step 172：CONTRACT-01 前后端契约对齐规范【强制】🆕v4.29

**背景**：后端 API 返回 `total` 但前端 types.ts 期望 `total_for_type`；后端用 snake_case（`min_price`）但前端用 camelCase（`minPrice`），转换遗漏导致前端取不到数据。

**问题**：前后端字段名/类型/默认值不一致导致前端取不到数据或类型错误；契约文档缺失导致变更时无法同步。

**规范**：

1. **字段名严格对齐【强制】**：后端 API 响应字段名必须与前端 types.ts interface 严格一致（含大小写/下划线/前后缀），禁止后端 `total` 前端 `total_for_type`：
   ```python
   # ✅ 正确：后端字段名与前端 types.ts 一致
   return {"total_for_type": count, "items": [...]}  # 后端
   # interface Response { total_for_type: number; items: Item[]; }  # 前端

   # ❌ 错误：后端 total，前端 total_for_type
   # return {"total": count}  # 前端取不到 → 显示 0 条
   ```

2. **类型与默认值对齐【强制】**：后端字段类型（str/int/bool/null）必须与前端 TS 类型对齐；可选字段必须标注默认值（`field?: number` 对应后端 `Optional[int]`）。

3. **契约变更必须双向 grep【强制】**：字段变更时必须 grep 后端 `model_dump()` / dict 字面量 与前端 types.ts，确认无遗漏：
   ```bash
   grep -rn "field_name" src/xianyu_hunter/web/routes/
   grep -rn "field_name" frontend/src/api/types.ts
   ```

**配置驱动**：`coding_standards.contract.alignment_check`（`true`）、`snake_camel_mapping`（转换映射表）在 `config.yaml` 管理。

**适用场景**：
- API 响应字段（前后端契约）
- DB schema 字段名与 ORM model 字段名对齐
- TypeScript interface 与 Python Pydantic model 字段对齐

**不适用场景**：
- 框架内置字段（如 `__init__`）
- 第三方 API 的字段（无法控制）

**历史教训**：`api_task_links.py` 返回 `total` 但前端期望 `total_for_type`，前端显示「0 条」；`min_price` / `minPrice` 转换遗漏导致筛选条件失效。

**判断信号（review 触发条件）**：
- 后端响应字段名 vs 前端 types.ts 字段名不一致
- 前端显示「0 条」/「undefined」但后端日志显示有数据
- `AttributeError` / `KeyError` 由字段名不一致引发


---

### step 173：SEMANTICS-01 语义一致性规范【强制】🆕v4.29

**背景**：业务逻辑用 `paid` / `confirmed` 但 DB 存 `succeeded`，统计结果为 0%；事件类型用 `startswith('eval.')` 误包含 `eval.passed` 通知事件，评估明细混入空记录。

**问题**：业务逻辑中的状态值/事件类型语义与 DB 存储不一致导致查询/统计错误；模糊匹配（startswith/endswith）误包含不相关项导致数据污染。

**规范**：

1. **状态值与 DB 枚举一致【强制】**：业务逻辑中的状态值必须与 DB 存储的枚举值完全一致，禁止用同义词：
   ```python
   # ✅ 正确：与 DB 枚举一致
   if order.status == 'succeeded': success_count += 1

   # ❌ 错误：同义词不匹配
   # if order.status in ('paid', 'confirmed'):  # DB 实际存 'succeeded'
   ```

2. **事件类型精确匹配【强制】**：业务查询过滤单个事件类型必须用 `==` 精确匹配，禁止用 `startswith` / `endswith` 做前缀过滤（与 step 130 / step 142 一致）。

3. **状态值集中定义为 Enum【强制】**：状态值必须集中定义为模块级 Enum 类，禁止分散硬编码字符串。

**配置驱动**：`coding_standards.semantics.status_fields`（状态字段清单）、`require_enum`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 状态机/枚举字段（订单状态/任务状态/评估状态）
- 事件类型过滤
- 统计逻辑（按状态计数/聚合）

**不适用场景**：
- 自由文本字段（如备注/描述）
- 数值型状态（如 score）

**历史教训**：抢单成功率统计用 `status in ('paid', 'confirmed')` 但 DB 存 `succeeded`，统计结果 0%；评估明细用 `startswith('eval.')` 误包含 227+ 条 `eval.passed` 通知事件。

**判断信号（review 触发条件）**：
- `grep "status ==\|status in" <file>` 出现硬编码状态字符串
- `grep "startswith" <file>` 出现在查询过滤逻辑中
- 统计结果为 0% 但 DB 有数据


---

### step 174：FILTER-01 过滤逻辑精确匹配规范【强制】🆕v4.29

**背景**：评估明细查询用 `event.type.startswith('eval.')` 过于宽泛，引入 227+ 条 `eval.passed` 通知事件（`payload=None`），导致列表混入大量空记录。

**问题**：前缀/后缀/子串过滤（startswith/endswith/in）会误包含同一前缀下的不相关项，导致统计偏差或列表污染；与 step 130（事件类型过滤精确匹配）和 step 142（数据查询条件精确性）有重叠，本规范强调通用过滤逻辑的精确匹配原则。

**规范**：

1. **匹配单个值用 ==【强制】**：业务查询过滤单个值时必须用 `==` 精确匹配，禁止用 `startswith` / `endswith` / `in` 做前缀/后缀/子串过滤：
   ```python
   # ✅ 正确：精确匹配
   events = [e for e in all_events if e.type == 'eval.scored']

   # ❌ 错误：startswith 误包含 eval.passed
   # events = [e for e in all_events if e.type.startswith('eval.')]
   ```

2. **前缀分组必须列出所有变体【强制】**：若必须用 `startswith` 做前缀分组（如统计场景），必须列出所有匹配的前缀变体并注释包含的子类型。

3. **通知事件与业务事件分离【强制】**：通知/审计类事件（如 `eval.passed` 仅用于 KPI）必须与业务查询事件（如 `eval.scored` 用于明细）使用不同的 type 前缀。

**配置驱动**：`coding_standards.filter.precision_check`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 数据查询过滤（按类型/状态/分类查询）
- 事件类型过滤
- 统计聚合

**不适用场景**：
- 模糊搜索（如商品标题搜索）
- 正则匹配场景
- 全量导出（无需过滤）

**历史教训**：`api_evaluations.py` 用 `startswith('eval.')` 过滤评估明细，误包含 227+ 条 `eval.passed` 通知事件，评估明细从 280 条减到 47 条有效记录。

**判断信号（review 触发条件）**：
- `grep "startswith" <file>` 出现在查询过滤逻辑中
- `grep "endswith" <file>` 出现在查询过滤逻辑中
- 业务列表混入 `payload=None` 的空记录


---

### step 175：DRY-01 重复代码抽取规范【强制】🆕v4.29

**背景**：cookie 同步逻辑在 `cookie_sync_scheduler.py` / `auth_helper.py` / `browser_login.py` 三个文件重复实现，修改时需逐文件改，漏改导致行为不一致；重复代码约 37 行。

**问题**：同一逻辑在多处重复实现时，修改需逐文件同步，漏改导致行为不一致；重复代码增加维护成本与 bug 风险。

**规范**：

1. **跨模块复用逻辑必须抽取【强制】**：跨 ≥2 模块复用的逻辑（函数/常量/校验规则）必须抽取到被依赖方模块的顶层，消费方 import 复用：
   ```python
   # ✅ 正确：抽取到 cookie_utils.py
   # cookie_utils.py
   def write_pending_marker(layer: str, source: str) -> None:
       """写入 pending marker 文件，供 cookie_sync_scheduler 消费。"""
       marker = PENDING_DIR / f"{layer}_{source}.pending"
       marker.touch()

   # auth_helper.py / browser_login.py 统一复用
   from xianyu_hunter.modules.cookie_utils import write_pending_marker
   write_pending_marker("session", "auth_helper")

   # ❌ 错误：3 处重复实现
   # auth_helper.py: def _write_marker(...): ...
   # browser_login.py: def _write_pending(...): ...
   # cookie_sync_scheduler.py: def _check_marker(...): ...
   ```

2. **抽取前确认无副作用【强制】**：抽取共享逻辑前必须确认各消费点的行为一致（无细微差异），若存在差异必须用参数化而非复制粘贴。

3. **抽取后必须 grep 验证无残留【强制】**：抽取后必须 grep 旧实现的关键标志符，确认无残留重复代码。

**配置驱动**：`coding_standards.dry.min_reuse_count`（`2`）、`require_extraction`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 跨模块复用的逻辑（函数/常量/校验规则）
- 重复代码 ≥ 2 处
- 修改时需同步多处的逻辑

**不适用场景**：
- 单一消费点的逻辑（无需抽取）
- 细微差异较大的逻辑（用参数化而非强制抽取）
- 框架约定的重复（如多个 API 路由的相似结构）

**历史教训**：cookie 同步逻辑在 3 个文件重复实现（约 37 行），修改 pending marker 格式时仅更新了 2 个文件，第 3 个文件漏改导致同步失败。修复后抽取 `write_pending_marker` 到 `cookie_utils.py`，3 处复用，减少 37 行重复代码。

**判断信号（review 触发条件）**：
- 同一逻辑在 ≥2 文件重复出现
- 修改时需同步多处（grep 命中多处）
- 重复代码行数 ≥ 10 行


---

### step 176：ENCODING-01 编码一致性规范【强制】🆕v4.29

**背景**：PowerShell 默认编码 cp936/gbk，调用 API 时中文 body 被转换为 `?`，数据库存储乱码；Python 脚本输出中文到日志文件乱码；与 step 133（Windows 终端编码）有重叠，本规范强调全链路编码一致性。

**问题**：编码不一致导致中文乱码（存储/日志/网络传输）；编码问题难以排查（数据已写入乱码无法恢复）。

**规范**：

1. **脚本启动必须设置 UTF-8【强制】**：PowerShell / Python 脚本启动时必须显式设置 UTF-8 编码，禁止依赖默认 cp936/gbk：
   ```powershell
   # PowerShell
   [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   $OutputEncoding = [System.Text.Encoding]::UTF8
   chcp 65001 > $null
   ```
   ```python
   # Python
   import sys
   sys.stdout.reconfigure(encoding='utf-8')
   ```

2. **API 调用必须显式设置 Content-Type 与 body 编码【强制】**：调用 API 时必须显式设置 `Content-Type: application/json; charset=utf-8`，body 用 UTF-8 字节数组传递：
   ```powershell
   $body = @{ question = "你好" } | ConvertTo-Json -Depth 10
   $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
   Invoke-RestMethod -Uri "..." -Method Post -ContentType "application/json; charset=utf-8" -Body $bytes
   ```

3. **跨平台路径用 pathlib【强制】**：路径处理必须用 `pathlib.Path` 或 `os.path.join`，禁止硬编码路径分隔符。

**配置驱动**：`coding_standards.encoding.default`（`utf-8`）、`require_explicit_charset`（`true`）在 `config.yaml` 管理。

**适用场景**：
- Windows PowerShell 脚本调用 API（含中文 body）
- Python 脚本输出中文到日志
- 跨平台部署的脚本

**不适用场景**：
- Linux/Mac 环境（默认 UTF-8）
- Docker 容器内脚本（默认 UTF-8）
- 纯英文内容（无编码问题）

**历史教训**：外部脚本批量调用 `POST /api/chatbot/faq` 时 PowerShell 默认 cp936 编码，中文 body 被转换为 `?`，数据库存储 3 条乱码记录。

**判断信号（review 触发条件）**：
- 数据库存储中文为 `?`
- 日志文件中文乱码
- `grep "cp936\|gbk" <file>` 出现编码硬编码


---

### step 177：DATACLASS-01 数据类使用规范【强制】🆕v4.29

**背景**：领域模型用 dict 传递导致字段名拼写错误无法在编译期发现；Pydantic model 与 dataclass 混用导致校验规则不一致；dataclass 未用 `frozen=True` 导致运行时被意外修改。

**问题**：dict 传递数据无法在编译期发现字段名错误；Pydantic model 与 dataclass 选择无明确标准导致校验规则不一致；可变 dataclass 被意外修改导致难以追踪的 bug。

**规范**：

1. **领域模型用 frozen dataclass【强制】**：领域模型（无 IO 依赖的纯数据结构）必须用 `@dataclass(frozen=True)`，禁止用 dict 传递：
   ```python
   from dataclasses import dataclass

   @dataclass(frozen=True)
   class Task:
       task_id: str
       keyword: str
       status: str
   ```

2. **API 边界用 Pydantic model【强制】**：API 请求/响应模型必须用 Pydantic model（`BaseModel`），利用其运行时校验；内部领域模型用 dataclass。

3. **frozen=True 强制不可变【强制】**：领域模型 dataclass 必须用 `frozen=True`，防止运行时被意外修改：
   ```python
   # ✅ 正确：frozen 防止意外修改
   @dataclass(frozen=True)
   class CookieLayer:
       name: str
       is_valid: bool

   # ❌ 错误：可变 dataclass，运行时被修改
   # @dataclass
   # class CookieLayer:
   #     name: str
   #     is_valid: bool
   ```

**配置驱动**：`coding_standards.dataclass.domain_model_frozen`（`true`）、`api_boundary_pydantic`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 领域模型（无 IO 依赖的纯数据结构）
- API 请求/响应模型
- 跨模块传递的数据结构

**不适用场景**：
- 需要运行时修改的可变状态（用普通类）
- 简单配置项（用 dict 合理）
- ORM 模型（用 SQLAlchemy declarative）

**历史教训**：领域模型用 dict 传递，字段名 `task_id` 拼写为 `taskId` 未在编译期发现，运行时 KeyError；可变 dataclass 被意外修改 `task.status = 'completed'`，导致同一任务被重复处理。

**判断信号（review 触发条件）**：
- 领域模型用 dict 传递而非 dataclass
- dataclass 未用 `frozen=True`
- API 边界用 dataclass 而非 Pydantic model


---

### step 178：STARTUP-01 启动钩子完整性规范【强制】🆕v4.29

**背景**：`startup.py` 的 `_on_startup` 外层 except 用 `logger.warning(f"...{e}")` 吞掉异常，丢失完整堆栈；启动钩子中的关键初始化（DB 迁移/调度器/浏览器）失败后服务继续运行但功能异常。

**问题**：启动钩子是关键路径，异常被吞掉后服务「半启动」状态（部分功能可用部分不可用），难以排查；外层 warning 丢失堆栈，无法定位真正失败点。

**规范**：

1. **关键路径外层必须用 logger.exception()【强制】**：启动钩子（`_on_startup`）/迁移函数（`run_migrations`）/初始化函数（`_init_*`）的外层 except 必须用 `logger.exception()` 输出完整 traceback：
   ```python
   # ✅ 正确：exception 保留完整堆栈
   try:
       container = get_container()
       run_migrations(container)
   except Exception:
       logger.exception("启动迁移钩子失败（不阻断主服务）")

   # ❌ 错误：warning 丢失堆栈
   # except Exception as e:
   #     logger.warning(f"启动迁移钩子失败（忽略）: {e}")
   ```

2. **关键初始化失败必须显式标记【强制】**：关键初始化（DB/调度器/浏览器）失败时必须设置 `init_failed = True` 标志，相关 API 检测标志后返回 503 而非异常。

3. **启动后必须验证关键组件【强制】**：启动后必须验证关键组件状态（DB 连接/调度器运行/端口监听），失败时输出 WARNING + 影响范围 + 修复命令。

**配置驱动**：`coding_standards.startup.critical_path_exception`（`true`）、`require_init_flag`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 启动钩子（`_on_startup` / `_on_shutdown`）
- 迁移函数（`run_migrations` / `init_db`）
- 初始化函数（`_init_container` / `_init_scheduler`）

**不适用场景**：
- 非关键路径的 fire-and-forget 操作（如 dump 诊断文件）
- 可重试的临时失败（用 tenacity 重试）

**历史教训**：`startup.py` 的 `_on_startup` 外层 except 用 `logger.warning(f"启动迁移钩子失败（忽略）: {e}")` 吞掉异常，C-01 迁移失败后 C-04（`notifications.read_at`）被跳过，数据库 schema 缺列，运行时 INSERT 失败。修复后改用 `logger.exception()` + 各迁移块独立 try/except。

**判断信号（review 触发条件）**：
- `grep "except Exception" src/xianyu_hunter/web/startup.py` 命中关键路径的外层统一 try/except
- `grep "logger.warning.*忽略" src/xianyu_hunter/web/startup.py` 命中吞掉异常的 warning
- 启动日志缺少完整 traceback
- 服务「半启动」状态（部分功能异常）


---

### step 182：修复前全链路根因扫描协议【强制，meta-rule #34 落地】

182. **修复前全链路根因扫描协议【强制，meta-rule #34 落地】**
   - **5 步 SOP**：
     - **Step 1 列根因（≥3 个）**：覆盖用户层/接口层/数据层/配置层/历史层 5 维度，列出 ≥3 个**独立的**根因
     - **Step 2 排根因**：用 Grep/Glob/Read/RunCommand 工具逐一验证每个根因
     - **Step 3 修复**：只修根因相关行（最小修改原则），不顺便重构
     - **Step 4 反查**：修复后用脚本/grep 验证"全链路是否还有类似缺口"
     - **Step 5 防回归**：加 unit test + integration test + 写一条 B/F-REVIEW 检查点
   - **配置驱动**：`config.yaml` 的 `root_cause_protocol` 节点管理（`min_root_causes: 3` / `required_chain_check_dimensions` / `required_regression_artifacts`）
   - **强制要求**：
     - PR 描述必须含 "≥3 根因列表" 段，否则视为 SUGGESTION
     - 修复后必须反查"全链路是否还有类似缺口"，否则视为 WARNING
     - `git diff` 涉及 ≥3 个无关文件 → 违反最小修改原则 → WARNING
     - 新增逻辑但没加 unit test → WARNING
   - **适用场景**：修复任何非平凡 bug（≥2 个文件参与 / 涉及状态变更 / 跨前后端 / 复盘过 ≥1 次）
   - **不适用**：纯样式 bug（颜色/间距/字号）、单行 typo、纯构建错误（依赖缺失/版本冲突）
   - **历史教训**：
     - 通知中心菜单点击无反应：根因是 L2/L3/L4 三层全缺，但朴素做法只补 L2 → 用户会再报"配置中心无反应"等类似问题
     - `repo_chatbot.py:478` datetime 混用 TypeError：修复未全仓扫描，2 周后又出现在 `api_orders.py:57`
   - **修复模板**（PR 描述）：
     ```markdown
     ## 根因列表（≥3）
     1. menu_registry 注册但 App.tsx 无路由（验证：grep 失败）
     2. 路由 fallback 静默重定向（验证：手动访问 /notifications 跳到 /）
     3. pages/Notifications 目录不存在（验证：Glob 失败）

     ## 排除的根因
     - 后端 API 缺失 → 已确认存在（grep api_notifications.py 命中）
     - 权限拦截 → 已确认 /notifications 在认证白名单

     ## 修复
     - L2: App.tsx 加 <Route path="notifications">
     - L3: 新建 pages/Notifications/index.tsx
     - L4: 新建 api/notifications.ts + 在 api/index.ts 导出

     ## 反查
     - 跑 check_registration.py：✅ 通过
     - grep 类似模式：grep "path: '/" menu_registry.yaml | xargs -I{} python check.py
     ```
   - **完整规范**：参见 [references/root-cause-protocol.md](../../../references/root-cause-protocol.md)

---

### step 183：前后端字段契约单一可信源【强制，meta-rule #35 落地】

183. **前后端字段契约单一可信源【强制，meta-rule #35 落地】**
   - **原则**：后端 Pydantic 模型 + DB Row 字段定义 = 权威源（Authoritative Source）；前端 `types.ts` 必须显式标注派生来源，禁止无标注手工复制
   - **3 种实现路径**：
     - 路径 A：后端生成前端 types（`datamodel-code-generator` / `openapi-typescript`）—— 强类型优先、大团队
     - 路径 B：手工对齐 + 注释标注 —— 快速迭代、小团队（本项目当前选 B）
     - 路径 C：共享 zod schema —— 前后端 TS/Node 栈
   - **5 点追踪清单**（字段变更时）：
     1. **DB Row 定义**：`db_models.py` 的 `Mapped[T]` 字段
     2. **Pydantic 模型**：`web/routes/api_*.py` 的 `BaseModel` 字段
     3. **后端返回路径**：`RepositoryBase._row_to_dict` 白名单 + 仓储 `_row_to_dto`
     4. **前端 types.ts**：`frontend/src/api/types.ts` 接口定义
     5. **前端消费点**：`frontend/src/api/<域>.ts` 方法 + `pages/<域>/` 渲染
   - **强制要求**：
     - 后端返回字段 `xxx_yyy`（snake_case）→ 前端 types.ts 必须是 `xxx_yyy`（**禁止转 camelCase**）
     - types.ts 缺 `派生来源` 注释 → WARNING
     - 后端 Pydantic 字段 `xxx_yyy` + 前端 types.ts 字段 `xxxYyy` → CRITICAL 命名漂移
     - 后端新增字段，前端 types.ts 未同步 → CRITICAL
   - **types.ts 注释模板**：
     ```typescript
     /**
      * 通知项
      *
      * 派生来源：src/xianyu_hunter/infra/db_models.py:NotificationRow
      *          + src/xianyu_hunter/web/routes/api_notifications.py:NotificationItem
      * Pydantic 字段：id / level / category / title / message / link /
      *                dedup_key / read_at / created_at
      * 变更日期：2026-07-06（初版）
      *
      * 约束：
      * - snake_case 严格保留，禁止转 camelCase
      * - 后端返回 ISO 8601 字符串，前端用 new Date() 解析
      * - read_at 为 null 表示未读，非空表示已读时间
      */
     export interface NotificationItem {
       id: number
       read_at: string | null  // ← snake_case，禁止 readAt
     }
     ```
   - **配置驱动**：`config.yaml` 的 `contract_single_source` 节点管理（`current_path: B` / `required_annotation_fields` / `five_point_trace` / `naming_convention` / `type_mapping`）
   - **判断信号**：
     - `grep "派生来源" frontend/src/api/types.ts` 缺失 → WARNING
     - 后端 Pydantic 字段 `xxx_yyy` + 前端 types.ts 字段 `xxxYyy` → CRITICAL
     - 后端 Pydantic 新增字段 + 前端 types.ts 未更新 → CRITICAL
     - 前端 `(data as Record<string, any>)['xxxYyy']` 动态 key 取值 → CRITICAL
   - **适用场景**：前后端分离架构中，任何跨网络边界传输的数据结构
   - **不适用**：纯前端单页、纯后端模板渲染、monorepo 共享 types（已有 typegen）、第三方 API（不可控）
   - **历史教训**：通知中心 `read_at` 字段手工复制时自己转成 `readAt`，前端永远读到 undefined，"标记已读"按钮点击无效
   - **完整规范**：参见 [references/contract-single-source.md](../../../references/contract-single-source.md)

---

### step 184：全局聚合任务级过滤【强制，meta-rule #38 落地】

184. **全局聚合任务级过滤【强制，meta-rule #38 落地】**
   - **原则**：多任务共享的列表查询接口（无 `task_id` 参数的全局视图）必须按各任务的个体配置范围过滤，禁止只用全局默认范围导致越界数据
   - **视图区分**：
     - **单任务视图**（`task_id` 显式传入）：应用该任务个体配置范围
     - **全局视图**（`task_id` 为 None）：遍历所有任务，对每条数据按其归属任务的个体配置过滤
   - **强制要求**：
     - 任务级过滤逻辑必须抽取为独立函数（如 `_filter_by_per_task_range`），便于复用与单测
     - 任务无配置时使用全局默认范围兜底，禁止跳过过滤
     - 过滤策略（per_task / global_only / hybrid）从 `config.yaml#global_aggregate_filter` 读取
   - **修复模式**：
     ```python
     # 修复前（违规）：全局视图不过滤
     def list_evaluations(task_id: str | None = None):
         if task_id is None:
             return {min: None, max: None}  # ❌ 不过滤
         return _load_by_task(task_id)

     # 修复后（合规）：全局视图按各任务范围过滤
     def list_evaluations(task_id: str | None = None):
         if task_id is None:
             return _filter_by_per_task_range(items)  # ✅ 抽取函数 + 任务级过滤
         return _load_by_task(task_id)

     def _filter_by_per_task_range(items: list) -> list:
         """按各任务个体价格范围过滤（全局视图专用）"""
         task_configs = _batch_load_task_configs()  # 批量加载，避免 N+1
         return [item for item in items
                 if _is_within_task_range(item, task_configs.get(item.task_id))]
     ```
   - **判断信号**：
     - `grep "task_id.*None\|task_id.*is None" <file>` 但无 `_filter_by_per_task` 调用 → 视为违规
     - `grep "def list_.*\(.*task_id.*\)" <file>` 缺全局视图分支 → 视为可疑
     - 列表接口返回数据中存在超过任一任务配置上限的值 → 视为 P0
   - **适用场景**：多任务共享的列表查询接口（评估列表 / 仪表盘 / 商品列表 / 订单列表）、跨任务聚合视图、全局搜索
   - **不适用场景**：单任务详情视图、统计聚合（无个体过滤需求）、管理后台超管视图
   - **历史教训**：用户反馈「最高价仍显示 ¥2,988.00」。根因：`evaluations_list.py` 在无 `task_id` 时直接返回 `{min: None, max: None}` 不做任务级过滤。修复：新增 `_filter_by_per_task_range` 函数。

---

### step 185：列表交叉数据批量注入【强制，meta-rule #39 落地】

185. **列表交叉数据批量注入【强制，meta-rule #39 落地】**
   - **原则**：列表查询需要交叉注入其他数据源的数据时，必须采用批量查询 + TTL 缓存模式，禁止 N+1 单条查询
   - **批量查询模式**：
     - 用 `WHERE xxx IN (...)` 一次性查询所有需要的交叉数据
     - 分块大小（避免 IN 子句过长）从 `config.yaml#cross_domain_inject.batch_size` 读取，默认 100
   - **TTL 缓存模式**：
     - 缓存 key 为业务键（如 `task_id` / `seller_id`），禁止含时间戳或随机值
     - TTL 从 `config.yaml#cross_domain_inject.cache_ttl_seconds` 读取，默认 300 秒
     - 单轮 run_once / 单次请求内缓存，每轮重置
   - **缺失降级**：交叉数据查询失败时降级为 `None` / 空对象，禁止阻断主列表返回
   - **修复模式**：
     ```python
     # 修复前（违规）：N+1 查询
     def list_evaluations():
         items = load_items()
         for item in items:
             item.bargain_price = _compute_sold_range(item.task_id)  # ❌ N+1
         return items

     # 修复后（合规）：批量查询 + TTL 缓存
     from functools import lru_cache

     @lru_cache(maxsize=128)
     def _cached_sold_range(task_id: str) -> dict:
         return _compute_sold_range(task_id)

     def list_evaluations():
         items = load_items()
         task_ids = {item.task_id for item in items}
         # 批量查询，避免 N+1
         ranges = _batch_compute_sold_ranges(list(task_ids))
         for item in items:
             item.bargain_price = ranges.get(item.task_id)  # 缺失降级 None
         return items
     ```
   - **判断信号**：
     - `grep "for.*in.*items:" <file>` 后跟 `db.query\|session.execute` 单条查询 → 视为 N+1 违规
     - `grep "def list_.*\(.*\)" <file>` 缺 `IN \(.*\)` 批量查询 → 视为可疑
     - 交叉数据查询无 `cache_ttl` / `_cache` / `lru_cache` → 视为不规范
   - **适用场景**：列表接口需要交叉其他数据源（评估列表 + 捡漏价格、订单列表 + 商品详情、商品列表 + 卖家信息）
   - **不适用场景**：单条详情查询（无 N+1 风险）、TTL 不可接受的热路径、列表数据量固定 ≤3 条
   - **历史教训**：评估列表显示「预估盈利」时循环内对每个 task 单独查询已售价格，10 个任务触发 10 次 DB 查询，接口耗时从 200ms 升到 1.8s。修复：批量查询 + 5 分钟 TTL 缓存，耗时降到 250ms。

---

### step 186：多字段联动开关范式【强制，meta-rule #40 落地】

186. **多字段联动开关范式【强制，meta-rule #40 落地】**
   - **原则**：多个业务字段叠加生效时必须明确「主开关 → 过滤器」优先级矩阵，主开关失效时子过滤器自动禁用
   - **优先级矩阵模板**（必须在文档/注释中显式声明）：
     ```
     | mode (主开关) | notify_bargain_only (过滤器) | auto_buy_bargain_only (过滤器) |
     |---|---|---|
     | full_auto     | 可配置（开/关）              | 可配置（开/关）                |
     | semi_auto     | 可配置（开/关）              | 可配置（开/关）                |
     | notify        | 可配置（开/关）              | 强制禁用 + UI 标识不可用       |
     ```
   - **PATCH 三态语义**：
     - PATCH 接口必须用 `exclude_unset=True` 区分「未传 / 传 null / 传值」
     - 禁止 0/false 被误判为未传（导致字段无法清零）
   - **bool→int 存储**：DB 存储 BOOLEAN 字段统一用 INTEGER(0/1)，与同类开关字段（如 `use_cron`）一致
   - **前端 UI 联动**：
     ```tsx
     // 主开关 notify 模式时，auto_buy_bargain_only Switch 必须 disabled + Tag 标识
     <Switch
       checked={Boolean(formData.auto_buy_bargain_only)}
       onChange={(checked) => setFormData({ ...formData, auto_buy_bargain_only: checked })}
       disabled={formData.mode === 'notify'}  // ✅ 主开关失效时禁用
       checkedChildren="开"
       unCheckedChildren="关"
     />
     {formData.mode === 'notify' && (
       <Tag color="default" style={{ marginLeft: 8, fontSize: 11 }}>仅通知模式不可用</Tag>
     )}
     ```
   - **判断信号**：
     - `grep "mode.*notify\|mode.*auto_buy" <file>` 但无优先级矩阵注释 → 视为可疑
     - `grep "exclude_unset.*True\|exclude_unset=True" <file>` PATCH 接口缺此参数 → 视为违规
     - `grep "notify_bargain_only\|auto_buy_bargain_only" <file>` 缺 `disabled={.*mode.*===.*notify}` → 视为前端 UI 不规范
   - **适用场景**：多字段叠加生效的业务开关（mode + 子过滤器、enabled + 子配置、auto_* + 限制条件）
   - **不适用场景**：独立开关（无联动）、纯前端 UI 开关（无后端逻辑）、单一布尔开关（无组合语义）
   - **历史教训**：任务配置含 `mode` + `notify_bargain_only` + `auto_buy_bargain_only` 三个字段，无优先级矩阵。修复：明确优先级矩阵 + PATCH 三态语义 + bool→int 存储。

---

### step 187：状态恢复前置校验结构化响应【强制，meta-rule #41 落地】

187. **状态恢复前置校验结构化响应【强制，meta-rule #41 落地】**
   - **原则**：precheck 函数必须返回结构化 dict（不抛异常），含 5 个标准字段，便于 API 层统一转换与前端统一渲染
   - **5 字段结构化响应**：
     ```python
     def precheck_resume(self, task_id: str) -> dict[str, Any]:
         """恢复前置校验：返回结构化结果，不抛异常"""
         result: dict[str, Any] = {
             "resume_blocked": False,       # 是否阻断恢复
             "reason_code": "ok",           # 来自 reason_enum 枚举
             "user_hint": "",               # 人类可读提示（含恢复动作建议）
             "retry_after": None,           # 冷却期剩余秒数（null 表示无冷却期）
             "task_registered": task_id in self._workers,  # 任务是否注册到调度器
         }
         # 各校验分支用 result.update() 修改字段，禁止 raise
         if task_id not in self._workers:
             result["user_hint"] = "任务未注册到调度器，DB 状态将更新但需重启服务才生效"
             return result
         # ... 冷却期 / Cookie 校验等分支
         return result
     ```
   - **API 层直接透传**（禁止 try/except 包裹）：
     ```python
     @router.get("/{task_id}/precheck")
     def precheck_task_resume(task_id: str, request: Request, container: Container = Depends(get_container)) -> dict[str, Any]:
         _check_task_ownership(container, task_id, request)
         if container.collector is None:
             return {"resume_blocked": False, "reason_code": "ok", "user_hint": "纯 web 模式，无需校验", "retry_after": None, "task_registered": False}
         return container.scheduler.precheck_resume(task_id)  # ✅ 直接透传
     ```
   - **前端按 reason_code switch 分支**：
     ```tsx
     const showPrecheckBlocked = (result: TaskPrecheckResult) => {
       const isCookie = result.reason_code === 'cookie_invalid'
       Modal.warning({
         title: result.reason_code === 'cooldown' ? '⏳ 冷却期内' : '⚠️ 无法恢复',
         content: <div>{result.user_hint}</div>,
         okText: isCookie ? '前往登录' : '知道了',
         onOk: () => { if (isCookie) navigate('/login') },
       })
     }
     ```
   - **判断信号**：
     - `grep "def precheck_\|def _precheck" <file>` 函数体内含 `raise` → 视为违规
     - precheck 返回 dict 缺任一标准字段 → 视为违规
     - API 路由内含 `try.*precheck.*except` → 视为违规
     - `grep "result\.user_hint\.includes\|result\.user_hint\.indexOf" frontend/` → 视为违规（违反 #29）
   - **适用场景**：任何 precheck/resume 类接口（任务恢复 / 会话恢复 / 调度器恢复 / 连接池重连 / 断路器闭合）
   - **不适用场景**：单纯校验函数（无结构化响应需求，直接返回 bool）、同步阻塞式校验、纯前端校验
   - **历史教训**：`scheduler.precheck_resume` 最初设计为抛 `ResumeBlockedError` 异常，多种阻断原因需多个异常类（类爆炸）+ 前端无法用 `reason_code` 分支。修复：改为结构化 dict 返回 5 字段。

---

### step 188：配置化阈值兜底范式【强制，meta-rule #42 落地】

188. **配置化阈值兜底范式【强制，meta-rule #42 落地】**
   - **原则**：从 `config.yaml` 读取的阈值/分位数/百分位必须有 `try/except` 兜底默认值，保证配置缺失时系统仍可运行
   - **兜底模板**：
     ```python
     # 修复前（违规）：无兜底，配置缺失即崩溃
     def _compute_sold_range(prices: list[float]) -> dict:
         bargain_percentile = get_config().bargain_price.percentile  # ❌ AttributeError
         p10 = round(_percentile(sorted_p, bargain_percentile), 2)
         return {"min": min(prices), "max": max(prices), "p10": p10}

     # 修复后（合规）：try/except 兜底默认值
     def _compute_sold_range(prices: list[float]) -> dict:
         try:
             from xianyu_hunter.infra.yaml_config import get_config
             bargain_percentile = get_config().bargain_price.percentile
         except Exception:
             bargain_percentile = 0.10  # ✅ 与 config.example.yaml 默认值一致
             logger.warning("bargain_price.percentile 配置读取失败，回退默认值 0.10")
         p10 = round(_percentile(sorted_p, bargain_percentile), 2)
         return {"min": min(prices), "max": max(prices), "p10": p10}
     ```
   - **强制要求**：
     - 默认值必须与 `config.example.yaml` 保持一致（禁止默认值与示例配置冲突）
     - 兜底时必须 `logger.warning` 记录（不用 `logger.error`，避免污染告警）
     - 日志含字段名 + 回退值（如 `bargain_price.percentile 配置读取失败，回退默认值 0.10`）
     - 新增配置项必须同步更新 `config.example.yaml` + Config 类字段 + 消费点 try/except
   - **判断信号**：
     - `grep "get_config\(\)\.\w+\.\w+" <file>` 但无 `try.*except.*default` 包裹 → 视为可疑
     - `grep "from.*yaml_config import get_config" <file>` 但同文件 `get_config()` 调用无 try/except → 视为违规
     - `grep "logger\.error.*配置.*默认\|logger\.error.*fallback" <file>` → 视为不规范（应 warning）
     - `config.example.yaml` 与 Config 类默认值 grep 不一致 → 视为违规
   - **适用场景**：从 config 读取的阈值/分位数/百分位/重试次数/超时秒数/批次大小等可调参数
   - **不适用场景**：强制必需配置（如数据库路径、认证密钥，缺失即不可启动，应在启动校验时 `raise`）、安全相关配置（如 token 比较方式，不可兜底）、协议固定值（不可配置）
   - **历史教训**：`_compute_sold_range` 中 P10 分位数从配置读取，用户 `config.yaml` 是旧版本无此字段，调用时 `AttributeError`，整个价格策略接口崩溃。修复：try/except 兜底默认值 0.10 + `logger.warning` 记录。




---

### step 232：预检前置规范【强制】🆕v4.47

**背景**：3 次关联会话中，批次采集任务（一次处理数十个商品 ID）在执行中途才暴露 cookie 失效——前几个商品采集成功，第 N 个商品突然返回 `cookie_expired:_m_h5_tk`，导致部分成功部分失败。失败的 ID 需要重试，但重试时 cookie 仍未恢复，进入死循环。根因是缺乏批次级预检和登录后健康探测，问题延迟到任务执行中才暴露，已经消耗了部分资源。

**问题**：批次级任务（采集 / 同步 / 批量更新）缺乏前置预检，问题延迟到执行中暴露，导致部分成功部分失败的中间状态；登录后缺乏健康探测，刚登录成功的会话可能在第一个业务请求时就失效。

**规范**：

1. **批次级预检【强制】**：批次任务开始前必须预检 cookie / token / session / 连接等前置条件，**禁止**直接进入业务执行：
   - **预检内容**：cookie 是否存在、`_m_h5_tk` 是否过期（按 step 6.5 规范）、layer 状态是否有效、连接是否可达
   - **预检失败处理**：直接走自愈链路（按 step 229 多级自愈），**禁止**进入业务重试循环
   - **预检成功处理**：进入业务执行，执行中失败仍按业务重试逻辑处理

2. **登录后健康探测【强制】**：浏览器登录成功后，必须发起一次轻量健康探测（如调用 `mtop.taobao.idle.user.head` 或类似无副作用接口），确认会话实际可用后再标记登录成功：
   - **探测失败**：调用诊断日志（按 step 231），标记登录失败，**禁止**直接信任"登录窗口关闭"作为成功标志
   - **探测成功**：标记登录成功，触发批次级预检

3. **预检配置化【强制】**：预检内容清单、健康探测接口、预检失败处理策略，全部从 `config.yaml` 读取，**禁止**硬编码在代码中

**判断信号**：
- `grep "async def collect_batch\|async def process_batch\|async def sync_batch" src/` 找到批次函数 → 检查函数入口是否有预检步骤
- `grep "login_success\|on_login_complete" src/` 找到登录成功回调 → 检查是否调用健康探测
- 批次函数直接进入 `for item_id in items:` 循环，无前置预检 → 视为违规
- 登录回调只更新 cookie 不发起探测请求 → 视为违规

**修复模式**：
```python
# ✅ 批次前预检 + 登录后健康探测
async def collect_batch(self, item_ids: list[str], ...):
    # 批次级预检（关键步骤，不能省略）
    precheck_ok = await self._precheck_session()
    if not precheck_ok:
        # 预检失败走自愈链路，不进入业务重试
        await self._refresh_token_and_retry_detail(item_ids[0], ...)
        return  # 自愈后由调用方决定是否重新发起批次

    # 预检通过，进入业务执行
    for item_id in item_ids:
        await self.detail(item_id)

async def _on_login_complete(self, ...):
    # 登录后健康探测（关键步骤，不能省略）
    health_ok = await self._probe_session_health()
    if not health_ok:
        self._log_cookie_diagnostics(
            "post_login_health_check_failed",
            {"cookie_count": len(self.cookie_store.as_dict())},
        )
        return False  # 标记登录失败

    # 探测成功，标记登录成功
    self._log_cookie_diagnostics(
        "post_login_health_check_passed",
        {"cookie_count": len(self.cookie_store.as_dict())},
    )
    return True

# ❌ 反模式：批次直接进入循环，无预检
async def collect_batch(self, item_ids: list[str], ...):
    for item_id in item_ids:  # 第 N 个商品可能因 cookie 失效而失败
        await self.detail(item_id)

# ❌ 反模式：登录成功只更新 cookie，无健康探测
async def _on_login_complete(self, ...):
    self.cookie_store.update_from_browser(self.browser)
    return True  # 第一个业务请求可能立即返回 cookie_expired
```

**配置参数**：`precheck_frontloading.enabled`（默认 `true`，是否启用预检前置）、`precheck_frontloading.batch_precheck`（默认 `true`，是否启用批次级预检）、`precheck_frontloading.batch_precheck_items`（默认 `['cookie_exists', 'm5tk_not_expired', 'layer_states_valid', 'connection_reachable']`，预检项清单）、`precheck_frontloading.batch_precheck_fail_strategy`（默认 `self_heal`，预检失败策略，可选 `self_heal` / `abort` / `retry`）、`precheck_frontloading.post_login_health_check`（默认 `true`，是否启用登录后健康探测）、`precheck_frontloading.health_check_endpoint`（默认 `mtop.taobao.idle.user.head`，健康探测接口）、`precheck_frontloading.health_check_timeout_sec`（默认 `5`，探测超时秒数）、`precheck_frontloading.diagnostic_log_function`（默认 `_log_cookie_diagnostics`，诊断日志函数名）在 `config.yaml` 的 `precheck_frontloading` 节点管理

**适用场景**：批次采集任务（一次处理多个 ID）、批次同步任务、登录后立即执行业务、任何"前置条件失效会导致部分成功部分失败"的场景

**不适用场景**：单次操作（无批次概念）、纯本地计算（无 cookie / token / session 依赖）、幂等重试场景（即使部分失败可重试）、UI 渲染（无前置条件检查需求）

**历史教训**：批次采集任务一次处理数十个商品 ID，前几个成功，第 N 个返回 `cookie_expired:_m_h5_tk`，失败的 ID 进入重试队列，但重试时 cookie 仍未恢复，死循环持续数小时。引入批次级预检（cookie + m5tk + layer + connection 四项检查）后，问题在批次开始前暴露，自愈链路优先于业务重试触发。引入登录后健康探测后，"刚登录成功就失效"问题从执行中暴露提前到登录回调中暴露。详细复盘参见 [cookie-state-recovery-patterns.md](../../../references/cookie-state-recovery-patterns.md) v3 流程 J。

### step 247：STEP-PROGRESS-LOG-01 多步骤关键路径进度编号日志规范【强制】🆕v4.52.0

**背景**：抢单流程（`buyer.py` `_do_buy`）含4个关键步骤（导航详情页→点击立即购买→等待订单确认页→提交订单→提取订单号），原代码无步骤级日志，超时后只能看到"落单超时"，无法定位卡在哪一步，需二次复现才能拿到上下文。

**问题**：多步骤关键路径（抢单/采集/登录/迁移）无步骤级进度日志，超时或失败时无法从日志快速定位卡在哪一步，排查耗时成倍增加。

**规范**：

1. **多步骤流程必须编号日志【强制】**：≥3 步骤的关键路径在每个步骤前必须打编号日志，格式 `步骤X/N <步骤描述> <关键标识>`：
   ```python
   # ✅ 正确：编号日志，超时时可从日志定位卡在哪一步
   logger.info(f"[Buyer] 步骤1/4 导航详情页 item={item_id}")
   await self._navigate(item_id)
   logger.info(f"[Buyer] 步骤2/4 点击立即购买 item={item_id}")
   await self._click_buy_now()
   logger.info(f"[Buyer] 步骤2.5/4 等待订单确认页 item={item_id}")
   await self._wait_for_order_page()
   logger.info(f"[Buyer] 步骤3/4 点击提交订单 item={item_id}")
   await self._click_submit_order()
   logger.info(f"[Buyer] 步骤4/4 提取订单号 item={item_id}")
   order_no = await self._extract_order_no()
   ```

2. **编号格式必须含总步数【强制】**：用 `步骤X/N` 格式（X=当前步，N=总步数），禁止仅 `步骤X`，总步数让排查者知道流程还有多远。

3. **每步必须含关键标识【强制】**：每步日志必须含业务标识（`item_id`/`task_id`/`order_no`），便于 grep 定位特定任务的执行轨迹。

4. **子步骤用小数编号【强制】**：主步骤内的辅助等待/校验用小数（如 `步骤2.5/4`），不占用主步骤编号，保持主流程编号连续。

5. **编号日志配置化【强制】**：步骤描述模板、关键标识字段名、是否启用编号日志，全部从 `config.yaml` 读取，禁止硬编码：
   ```yaml
   step_progress_log:
     enabled: true
     format: "步骤{step}/{total} {description} {key_field}={key_value}"
     key_fields: ["item_id", "task_id", "order_no"]
     workflows:
       buyer_do_buy:
         steps: ["导航详情页", "点击立即购买", "等待订单确认页", "点击提交订单", "提取订单号"]
       official_collect:
         steps: ["访问详情页", "提取商品数据", "访问卖家主页", "提取卖家数据", "重新评估", "写入事件"]
   ```

**判断信号**：
- `grep "async def _do_\|async def _collect_\|async def _login_" src/` 找到多步骤流程函数 → 检查是否有步骤级编号日志
- 流程含 ≥3 个 `await` 调用但无 `步骤X/N` 日志 → 视为违规
- 日志有步骤描述但无总步数（如仅 `步骤1` 无 `/4`）→ 视为违规
- 日志有编号但无业务标识（`item_id`/`task_id`）→ 视为违规

**反模式**：
```python
# ❌ 无步骤级日志，超时后无法定位
async def _do_buy(self, item_id):
    await self._navigate(item_id)
    await self._click_buy_now()
    await self._wait_for_order_page()
    await self._click_submit_order()
    order_no = await self._extract_order_no()
    # 超时后日志只有"落单超时"，不知道卡在哪一步

# ❌ 有日志但无总步数和业务标识
logger.info("步骤1")  # 不知道总共几步，不知道是哪个商品
```

**配置参数**：`step_progress_log.enabled`（默认 `true`，是否启用编号日志）、`step_progress_log.format`（默认 `"步骤{step}/{total} {description} {key_field}={key_value}"`，日志格式模板）、`step_progress_log.key_fields`（默认 `["item_id", "task_id", "order_no"]`，关键标识字段名）、`step_progress_log.min_steps_threshold`（默认 `3`，触发编号日志的最小步骤数）、`step_progress_log.workflows`（工作流步骤定义字典）在 `config.yaml` 的 `step_progress_log` 节点管理

**适用场景**：多步骤浏览器自动化流程（抢单/采集/登录）、多步骤数据迁移流程、多步骤初始化流程、任何 ≥3 步骤的关键路径

**不适用场景**：单步操作（无步骤概念）、非关键路径（调试日志即可）、纯计算函数（无 IO 等待）、已有结构化诊断日志的 cookie 自愈链路（走 step 231）

**历史教训**：`buyer.py` `_do_buy` 含5个关键步骤但无步骤级日志，90秒超时后日志仅"落单超时 task=xxx item=yyy"，无法判断是导航卡住还是提交订单卡住。添加 `步骤1/4`~`步骤4/4` 编号日志后，超时场景可从日志直接定位卡在"步骤2.5/4 等待订单确认页"，排查时间从数小时降至分钟级。与 step 231（诊断日志模式）互补：step 231 聚焦"自愈链路的结构化上下文"，本规则聚焦"多步骤流程的进度编号定位"。


---

### step 248：数据写入策略字段级决策规范（FIELD-STRATEGY-01，meta-rule #105 落地）【强制】🆕v4.62.0

**背景**：后端 `_ALWAYS_OVERWRITE` 覆盖策略将 `image_urls` 字段覆盖为 None，清空了旧数据。不同字段有不同的业务语义，应按字段粒度选择覆盖策略。

**规范**：

1. **数据合并时按字段语义分类写入策略【强制】**：
   - 覆盖型（`_ALWAYS_OVERWRITE`）：状态类字段（is_sold/status）、时效性字段（updated_at）
   - 合并型（`_coalesce`）：新值非空才覆盖，保留旧值（image_urls/title/seller_nick）
   - 保留型：新值为 None 时保留旧值，新值非空时覆盖

2. **新增字段到 `_ALWAYS_OVERWRITE` 集合时必须文档化决策理由【强制】**

3. **禁止一刀切全量覆盖【强制】**——每个字段必须有明确的写入策略

**判断信号**：
- `grep "_ALWAYS_OVERWRITE" <py>` 新增字段但无注释说明理由 → 检查
- 数据合并后部分字段意外清空 → 疑似覆盖策略不当
- `grep "None" <py>` 在 enrich/合并逻辑中将字段设为 None → 检查是否应保留旧值

**配置参数**：`field_strategy.alwaysOverwriteFields`（默认 `['is_sold', 'status', 'updated_at']`，覆盖型字段列表）、`field_strategy.coalesceFields`（默认 `['image_urls', 'title', 'seller_nick']`，合并型字段列表）在 `config.yaml` 的 `field_strategy` 节点管理

**适用**：enrich/合并/覆盖逻辑、多源数据汇聚、批量更新操作

**不适用**：全新创建（无旧数据）、硬删除（无需合并）、单源独占写入

**历史教训**：官方采集未获取到图片时，后端将 items 表的 `image_urls` 字段覆盖为 None（因 `image_urls` 在 `_ALWAYS_OVERWRITE` 集合中），清空了旧数据。修复：将 `image_urls` 移出 `_ALWAYS_OVERWRITE`，采用 `_coalesce` 逻辑保留旧值


---

### step 249：回调注入默认值模式规范（CALLBACK-INJECTION-01，meta-rule #106 落地）【强制】🆕v4.62.0

**背景**：`login_orchestrator.py` 的 `_auto_relogin_callback` 未初始化，导致 3 次连续续期失败。回调函数未设置默认值时，调用方需处理 None/未设置状态。

**规范**：

1. **回调函数必须提供合理默认值【强制】**——在初始化时注入默认行为

2. **默认行为应是安全的、无副作用的【强制】**——如默认 callback 使用 headless cookie_inject 而非 None

3. **提供外部覆盖守卫【强制】**——允许外部设置自定义 callback，但有 guard 防止覆盖为 None

4. **测试默认和覆盖两种路径【强制】**

**判断信号**：
- `grep "callback.*None" <py>` 回调变量初始化为 None → 检查是否有默认值注入
- 调用回调前无 None 检查 → 潜在 AttributeError
- 回调未设置导致运行时错误 → 典型症状

**配置参数**：`callback_injection.defaultBehaviorStrategy`（默认 `'safe_headless'`，默认行为策略）、`callback_injection.allowOverride`（默认 `true`，是否允许外部覆盖）在 `config.yaml` 的 `callback_injection` 节点管理

**适用**：回调函数未设置、依赖注入点、策略模式、插件架构

**不适用**：同步简单逻辑（无回调）、确定性算法（无策略选择）、核心业务逻辑（不应有默认 fallback）

**历史教训**：`login_orchestrator.py` 的 `_auto_relogin_callback` 未初始化，后端报错"自动重登录回调未配置"。修复：添加 `_default_relogin_callback` 使用 `cookie_inject(headless)`，在 `start_session_default` 中注入，提供 guard 允许外部覆盖

---
