# 第九轮复盘：搜索接入扩展与事件时机修复（SearchService 模板方法 + useSearch/useSearchHistory Hook + 钉钉通知时机 + PowerShell 输出陷阱 + 测试路由一致性）

> 复盘时间：2026-07-25（第九轮，基于搜索接口标准化扩展接入、自动采集钉钉通知时机 Bug、FAQ 403 测试路由不一致、PowerShell 管道吞输出等 4 个独立修复过程的复盘）
> 复盘方法：Sequential Thinking 四维度复盘法（成功步骤 / 失败点 / 可抽象流程 / 适用场景）
> 配套编码规范：xianyu-hunter-dev step 16（v4.64.0 升级）/ step 19（v4.64.0 升级）/ step 133（v4.64.0 升级）/ step 271（新增）/ step 272（新增）
> 配套审查规范：B-REVIEW-324~326（搜索服务模板方法）/ F-REVIEW-236~240（useSearch/useSearchHistory Hook 模式）
> 配套配置节点：tech-stack.json#hardConstraints.eventTriggerTiming / searchServiceTemplate / searchHookDebounce / searchHistoryPersistence / powershellOutputTrap / testRouteConsistency

---

## I.1 成功执行任务的完整步骤

### I.1.1 搜索接口标准化与扩展接入

**适用问题**：项目内有 ≥2 个搜索接口（任务关联/错误日志/数据库维护/智能客服会话），各接口自行实现分页/计数/响应构造，导致逻辑重复、参数命名不一致、响应结构不统一。

| 步骤 | 操作 | 验证方式 |
|---|---|---|
| 1. 接口盘点 | grep 所有搜索接口，按 5 类分类（实时搜索/主键查询/固定条件列表/流式爬取/筛选器+查询按钮） | `grep "@bp\.\(post\|get\).*search" src/xianyu_hunter/web/routes/` |
| 2. 选基准 | 选最复杂的搜索接口作为基准（智能客服会话搜索，含分页+计数+分面） | 代码复杂度评估 |
| 3. 抽取基类 | 创建 `SearchService` 抽象基类（`search_base.py`），定义 `search()` 模板方法 + 4 个钩子 | 基类单元测试通过 |
| 4. 逐接口迁移 | 每个搜索接口迁移为 `SearchService` 子类，实现 4 个钩子 | 接口单元测试通过 |
| 5. 前端 Hook 抽取 | 创建 `useSearch`（防抖+并发保护）和 `useSearchHistory`（持久化+去重）Hook | Hook 单元测试通过 |
| 6. 前端页面接入 | 逐页面接入 `useSearch` + `useSearchHistory`，替换手动 `useEffect + setTimeout` | 页面功能验证 |
| 7. 联合验证 | 后端 SearchService + 前端 useSearch 端到端联调 | 4 个搜索页面全部正常 |

**关键判断逻辑**：
- 出现 ≥2 个搜索接口时必须抽取基类，避免逻辑重复
- 大数据集（>500 行）必须 SQL 层分页，禁止内存分页
- 防抖间隔必须统一（400ms，与 Alpine `@input.debounce.400ms` 对齐）
- `requestId` 并发保护必须覆盖所有实时搜索场景

### I.1.2 钉钉通知时机修复（EVAL_PASSED 事件）

**适用问题**：业务事件（如 `EVAL_PASSED`）在业务最终步骤之前触发，导致通知/副作用提前执行。

| 步骤 | 操作 | 验证方式 |
|---|---|---|
| 1. 现象诊断 | 用户反馈"AI 评估未完成就收到钉钉通知" | 通知截图 + 日志时间戳比对 |
| 2. 代码定位 | grep `EVAL_PASSED` 触发点 → 定位 `worker.py` 的 `_call_official_collect` 包装器 | `grep "EVAL_PASSED" src/` |
| 3. 根因分析 | 触发点位于"评估配置加载完成"之后，但"AI 评估实际执行"之前 | 静态阅读 + 时序图 |
| 4. 方案选择 | 将 `EVAL_PASSED` 触发点移至 AI 评估 + DB 写入全部完成之后，并通过 EventBus 触发 | 用户决策 |
| 5. 实施修复 | 修改 `worker.py` 的 `auto_collect_*` 字段 + `_call_official_collect` 包装器 | 代码编辑 |
| 6. 验证 | 触发自动采集流程，确认钉钉通知在 AI 评估完成后才发出 | 端到端测试 |

**关键判断逻辑**：
- 事件名含 PASSED/SENT/COMPLETED → 必须后置触发（业务最终步骤之后）
- 事件名含 STARTED/BEGIN → 前置触发（业务开始前）
- 通过 EventBus 解耦事件发布与业务逻辑，避免直接回调导致时机错乱

### I.1.3 FAQ 403 测试路由一致性修复

**适用问题**：测试代码中调用 `client.post/get/put/delete` 的路径与方法与实际路由定义不一致，导致测试 404/405。

| 步骤 | 操作 | 验证方式 |
|---|---|---|
| 1. 现象诊断 | 测试报告 `test_chatbot_api_degraded.py` 4 个测试失败，错误码 404/405 | pytest 输出 |
| 2. 路由比对 | grep 路由装饰器 `@bp.post("/faq")`（单数 + POST），与测试 `client.put("/faqs")`（复数 + PUT）比对 | `grep "@bp\.\(post\|put\|delete\|get\)" <route_file>` |
| 3. 根因分析 | 测试路径用复数 `/faqs` 但路由定义为单数 `/faq`；测试用 PUT 但路由无 PUT 方法 | 静态比对 |
| 4. 实施修复 | 测试路径改为 `/faq`，方法改为 POST，upsert 时 id 放在 body 而非 URL | 代码编辑 |
| 5. 验证 | 重新执行测试，153 passed / 0 failed | pytest 输出 |

**关键判断逻辑**：
- 测试编写前必须 grep 路由装饰器，与测试 client 调用逐一比对
- 常见陷阱：单复数混淆、HTTP 方法混淆、前缀重复或缺失、id 在 URL vs body

### I.1.4 PowerShell 管道吞输出陷阱

**适用问题**：pytest/长任务命令输出通过管道传递给 `Select-Object`/`Where-Object` 等 sink cmdlet 后，部分输出被缓冲丢弃，导致"命令成功但无输出"的假象。

| 步骤 | 操作 | 验证方式 |
|---|---|---|
| 1. 现象诊断 | pytest 执行后通过 `| Select-Object -Last 50` 查看输出，看不到 FAILED/ERROR 详情 | 输出截屏 |
| 2. 根因分析 | `Select-Object` 等 sink cmdlet 会缓冲并丢弃部分输出（尤其是 stderr 与彩色 ANSI 转义序列） | PowerShell 文档 |
| 3. 实施修复 | 改用文件重定向 `> out.txt 2>&1` 再 `Get-Content out.txt` | 命令验证 |
| 4. 验证 | 重新执行 pytest，确认 FAILED/ERROR 详情完整可见 | 输出对比 |

**关键判断逻辑**：
- 长任务输出禁止通过管道传递给 sink cmdlet
- 必须改用文件重定向再读取，确保输出完整保留

---

## I.2 6 个失败模式与修复（2026-07-25 第九轮）

### 后端 3 个失败模式

| 编号 | 失败模式 | 根因 | 修复 | 教训 | 沉淀检查点 |
|---|---|---|---|---|---|
| F41 | `EVAL_PASSED` 事件在 AI 评估前触发 | `worker.py` 的 `_call_official_collect` 包装器在"评估配置加载完成"之后触发 `EVAL_PASSED`，但"AI 评估实际执行"之前 | 将触发点移至 AI 评估 + DB 写入全部完成之后，通过 EventBus 触发 | PASSED 事件必须锚定到业务链路的最终步骤之后 | `xianyu-hunter-dev` 规范 16（事件触发时机） |
| F42 | 搜索接口逻辑重复 | 4 个搜索接口各自实现分页/计数/响应构造，参数命名与响应结构不一致 | 抽取 `SearchService` 抽象基类，子类实现 4 个钩子 | 出现 ≥2 个搜索接口时必须抽取基类 | B-REVIEW-324 SEARCH-SERVICE-TEMPLATE |
| F43 | 大数据集搜索用内存分页 | `_execute` 返回全量 rows 后用 `rows[offset:offset+limit]` 切片，未下推到 SQL 层 | 子类重写 `_paginate` 直接返回 rows，在 `_execute` 内用 `LIMIT/OFFSET` | 大数据集（>500 行）必须 SQL 层分页 | B-REVIEW-325 SEARCH-HOOK-METHOD-CONTRACT（`_paginate` 钩子契约） |

### 前端 2 个失败模式

| 编号 | 失败模式 | 根因 | 修复 | 教训 | 沉淀检查点 |
|---|---|---|---|---|---|
| F44 | `useSearchHistory` 的 `storageKey` 不稳定 | `storageKey` 直接用 `${prefix}${namespace}` 字符串拼接，每次渲染生成新字符串，导致 `useCallback` 依赖变化 | 用 `useMemo` 固定 `storageKey` | 字符串拼接的 key 必须用 `useMemo` 固定 | F-REVIEW-240 USE-SEARCH-HISTORY-DECLARATION-ORDER |
| F45 | `useSearchHistory` 声明顺序错误 | `useSearchHistory` 声明在 `loadSessions` 之后，`loadSessions` 的 `useCallback` 依赖了 `add`，导致 TDZ 错误 | 将 `useSearchHistory` 声明移到 `loadSessions` 之前 | Hook 必须声明在依赖它的 `useCallback` 之前 | F-REVIEW-240 USE-SEARCH-HISTORY-DECLARATION-ORDER |

### 测试 1 个失败模式

| 编号 | 失败模式 | 根因 | 修复 | 教训 | 沉淀检查点 |
|---|---|---|---|---|---|
| F46 | FAQ 测试路由不一致 | 测试用 `client.put("/api/chatbot/faqs")`，但路由定义为 `@bp.post("/faq")`（单数 + POST upsert） | 测试路径改为 `/faq`，方法改为 POST，id 放在 body | 测试编写前必须 grep 路由装饰器逐一比对 | `xianyu-auto-testing` 模式 AB 步骤 4（AB-04 测试路由一致性） |

---

## I.3 可沉淀的固定流程

| 流程 | 触发 | 步骤 | 验证 |
|---|---|---|---|
| SearchService 模板方法抽取范式 | 项目内出现 ≥2 个搜索接口 | ① 盘点所有搜索接口 ② 选最复杂的作为基准 ③ 创建 `SearchService` 基类（`search()` + 4 钩子） ④ 逐接口迁移为子类 ⑤ 大数据集重写 `_paginate` 为 SQL 层分页 ⑥ 前端抽取 `useSearch`/`useSearchHistory` Hook ⑦ 联合验证 | 4 个搜索页面端到端测试通过 |
| PASSED 事件时机校验范式 | 实现含 PASSED/SENT/COMPLETED 语义的事件触发 | ① 识别事件名是否含 PASSED/SENT/COMPLETED ② 定位业务链路的最终步骤（如 AI 评估 + DB 写入） ③ 确保触发点在最终步骤之后 ④ 优先通过 EventBus 触发，避免直接回调 ⑤ 端到端验证通知时机 | 通知在业务最终步骤完成后才发出 |
| useSearch Hook 抽取范式 | 多个搜索页面各自实现 `useEffect + setTimeout` 防抖 | ① 创建 `useSearch` Hook（防抖 + requestId 并发保护 + enabled 条件 + 卸载清理） ② 默认防抖 400ms 与 Alpine 对齐 ③ 用 `useRef` 持有最新闭包 ④ 逐页面接入替换手动防抖 ⑤ 验证快速输入不产生列表闪烁 | 快速输入测试无乱序覆盖 |
| useSearchHistory Hook 抽取范式 | 多个搜索页面各自实现 `localStorage` 读写 | ① 创建 `useSearchHistory` Hook（namespace 隔离 + 去重 + 容量限制 + 降级容错） ② 用 `useMemo` 固定 `storageKey` ③ 确保 Hook 声明在依赖它的 `useCallback` 之前 ④ 逐页面接入 ⑤ 验证跨页面历史不串扰 | 切换搜索页历史隔离测试通过 |
| 测试路由一致性校验范式 | 编写 FastAPI/Flask 路由测试 | ① 测试编写前 `grep "@bp\.\(post\|put\|delete\|get\)" <route_file>` 列出所有路由装饰器 ② 与测试 client 调用逐一比对路径（单复数）+ 方法（GET/POST/PUT/DELETE）+ 前缀 ③ upsert 时确认 id 在 body 还是 URL ④ 执行测试验证 | 测试 0 个 404/405 错误 |
| PowerShell 长任务输出查看范式 | 执行 pytest/npm build/Docker build 等长任务 | ① 禁止通过管道传递给 `Select-Object`/`Where-Object` 等 sink cmdlet ② 改用文件重定向 `> out.txt 2>&1` ③ 用 `Get-Content out.txt` 或 `Get-Content -Tail N out.txt` 查看 ④ 长任务用 `Start-Process -RedirectStandardOutput` | 输出完整保留，无丢失 |

---

## I.4 适用场景与不适用场景

### I.4.1 SearchService 模板方法模式

**适用**：
- 项目内出现 ≥2 个搜索接口
- 任务关联/错误日志/数据库维护/智能客服会话等列表搜索
- 需要分页 + 计数 + 分面直方图的搜索场景

**不适用**：
- 主键精确查询（无分页需求）
- 流式爬取（无请求-响应模型）
- 单接口场景（无需抽取基类）

### I.4.2 useSearch Hook

**适用**：
- 用户输入关键词的实时搜索
- 与 Alpine `@input.debounce.400ms` 模式对齐的搜索场景
- 弹窗/抽屉内的条件搜索（用 `enabled` 控制开关）

**不适用**：
- 筛选器 + 查询按钮模式（用户主动点击触发，无需防抖）
- 主键精确查询（无并发风险，直接 fetch）
- SSE/WebSocket 流式搜索（无请求-响应模型）

### I.4.3 useSearchHistory Hook

**适用**：
- 关键词搜索页面的历史记录持久化
- 跨会话需保留的用户搜索行为
- 多搜索页之间历史隔离

**不适用**：
- 枚举值筛选（如状态筛选/分类筛选，用户每次重新选择，无需历史）
- 敏感数据搜索（如密码/token 搜索，不应持久化到 localStorage）
- 一次性查询（如详情页 ID 查询，无需历史）

### I.4.4 PASSED 事件时机校验

**适用**：
- 所有含 PASSED/SENT/COMPLETED 语义的事件触发
- 钉钉/企微/邮件等通知集成
- AI 评估/任务完成等业务关键节点

**不适用**：
- STARTED/BEGIN 语义事件（业务开始前触发）
- 纯查询无副作用事件
- 调试用临时事件

### I.4.5 测试路由一致性校验

**适用**：
- FastAPI/Flask 路由测试编写
- 测试 404/405 错误排查
- API 重构后的测试同步检查

**不适用**：
- 无路由的纯函数测试
- 前端组件测试（无路由概念）
- 单元测试中 mock 掉的路由层

### I.4.6 PowerShell 长任务输出查看

**适用**：
- pytest 全量测试执行
- npm build / Docker 构建等长任务
- SonarQube 扫描输出查看
- 任何输出超过 50 行的命令

**不适用**：
- 短命令（< 10 行输出，管道无影响）
- 交互式命令（需实时输入）
- GUI 程序

---

## I.5 配套配置节点（配置驱动）

所有阈值/参数通过 `config/tech-stack.json#hardConstraints` 集中管理，禁止在业务代码中硬编码：

| 配置节点 | 用途 | step 引用 |
|---|---|---|
| `eventTriggerTiming` | PASSED 事件触发时机锚点配置 | step 16 |
| `searchServiceTemplate` | SearchService 模板方法模式配置（4 钩子/慢查询阈值/响应字段） | step 19 |
| `searchHookDebounce` | useSearch Hook 防抖与并发保护配置 | step 271 |
| `searchHistoryPersistence` | useSearchHistory 持久化配置（namespace/maxItems/降级策略） | step 272 |
| `powershellOutputTrap` | PowerShell 管道吞输出陷阱配置（禁用 cmdlet/重定向模式） | step 133 |
| `testRouteConsistency` | 测试路由一致性配置（路由装饰器模式/常见陷阱/验证方法） | step 133 |

---

## I.6 跨技能同步

本次复盘涉及的规范已同步到以下技能：

| 技能 | 同步内容 | 版本 |
|---|---|---|
| xianyu-hunter-dev | step 16/19/133 升级 + step 271/272 新增 + 6 个 hardConstraints 节点 | v4.64.0 ✅ |
| xianyu-backend-code-review | B-REVIEW-324~326（搜索服务模板方法审查：模板方法模式/4 钩子方法契约/慢查询日志） + config.yaml 3 节点（`search_service_template`/`template_method_pattern`/`hook_method_contract`/`slow_query_log`） | v4.65.0 ✅ |
| xianyu-frontend-code-review | F-REVIEW-236~240（useSearch/useSearchHistory Hook 审查：防抖并发保护/enabled 条件搜索/持久化去重/命名空间隔离/声明顺序） + config.yaml `search_hook_patterns` 节点 | v4.65.0 ✅ |
| xianyu-auto-testing | 模式 AB（搜索服务模板方法回归测试，覆盖 B-REVIEW-324~326）+ 模式 AC（useSearch/useSearchHistory Hook 回归测试，覆盖 F-REVIEW-236~240） + config.yaml 2 节点 + references 2 文档 | v2.4.0 ✅ |

### 跨技能检查点闭环矩阵

| 检查点 ID | 名称 | 定义技能 | 测试模式 | 状态 |
|---|---|---|---|---|
| B-REVIEW-324 | SEARCH-SERVICE-TEMPLATE 模板方法模式 | xianyu-backend-code-review v4.65.0 | 模式 AB 步骤 1（AB-01） | ✅ |
| B-REVIEW-325 | SEARCH-HOOK-METHOD-CONTRACT 4 钩子方法契约 | xianyu-backend-code-review v4.65.0 | 模式 AB 步骤 2（AB-02） | ✅ |
| B-REVIEW-326 | SEARCH-SLOW-QUERY-LOG 慢查询日志 | xianyu-backend-code-review v4.65.0 | 模式 AB 步骤 3（AB-03） | ✅ |
| F-REVIEW-236 | USE-SEARCH-DEBOUNCE-CONCURRENCY 防抖与并发保护 | xianyu-frontend-code-review v4.65.0 | 模式 AC 步骤 1（AC-01） | ✅ |
| F-REVIEW-237 | USE-SEARCH-ENABLED-CLEANUP enabled 条件搜索与卸载清理 | xianyu-frontend-code-review v4.65.0 | 模式 AC 步骤 2（AC-02） | ✅ |
| F-REVIEW-238 | USE-SEARCH-HISTORY-PERSISTENCE localStorage 持久化与去重 | xianyu-frontend-code-review v4.65.0 | 模式 AC 步骤 3（AC-03） | ✅ |
| F-REVIEW-239 | USE-SEARCH-HISTORY-NAMESPACE 命名空间隔离 | xianyu-frontend-code-review v4.65.0 | 模式 AC 步骤 4（AC-04） | ✅ |
| F-REVIEW-240 | USE-SEARCH-HISTORY-DECLARATION-ORDER 声明顺序与依赖稳定性 | xianyu-frontend-code-review v4.65.0 | 模式 AC 步骤 5（AC-05） | ✅ |

---

## I.7 历史教训总结

1. **PASSED 事件时机**：钉钉通知在 AI 评估前触发，导致用户收到通知但实际评估未完成。教训：PASSED 事件必须锚定到业务链路的最终步骤之后
2. **搜索接口逻辑重复**：4 个搜索接口各自实现分页/计数，参数命名与响应结构不一致。教训：出现 ≥2 个搜索接口时必须抽取基类
3. **大数据集内存分页**：`_execute` 返回全量 rows 后切片，性能差。教训：大数据集（>500 行）必须 SQL 层分页
4. **storageKey 不稳定**：字符串拼接的 key 每次渲染生成新字符串，导致 useCallback 依赖变化。教训：字符串拼接的 key 必须用 `useMemo` 固定
5. **Hook 声明顺序**：`useSearchHistory` 声明在依赖它的 `useCallback` 之后，导致 TDZ 错误。教训：Hook 必须声明在依赖它的 `useCallback` 之前
6. **测试路由不一致**：测试用复数 `/faqs` 但路由定义为单数 `/faq`，测试用 PUT 但路由无 PUT。教训：测试编写前必须 grep 路由装饰器逐一比对
7. **PowerShell 管道吞输出**：pytest 输出通过 `Select-Object` 后部分丢失。教训：长任务输出必须用文件重定向再读取
