
# 36. 调度器运行时治理前端侧（meta-rules #48-51 落地）🆕v4.40

> 本维度对�?`xianyu-hunter-dev` v4.36.0 meta-rules #48（调度器运行时开关对称性）/ #49（时间参数配置化�? #50（长生命周期对象状态清理）/ #51（用户输入时间表达式校验，experimental），与后�?`xianyu-backend-code-review` v4.37.0 维度 36 �?B-REVIEW-178/179/180/181 联动。前端侧新增 4 �?F-REVIEW 检查点（F-REVIEW-136~139），聚焦于：调度器开关状态在前端的可见性与同步、前端轮询间隔的配置化、React Hook �?cleanup 机制、用户输�?cron 表达式的前端校验�?
#### F-REVIEW-136：SCHEDULER-STATUS-SYNC 调度器开关状态前端同步（meta-rule #48 前端侧）🆕v4.40

**检查点**：前端必须实时同步后端调度器的开关状态（enabled/disabled），用户切换开关后必须调用后端 API 持久化，前端状态必须以 `GET /api/scheduler/status` 返回值为唯一可信源，禁止前端独立维护 `enabled` 状态�?
**检查项**�?1. 调度器开�?UI 组件（Switch/Toggle）的 `checked` 状态必须从后端 `GET /api/scheduler/status` 响应读取，禁止前端独�?`useState` 维护
2. 用户切换开关后必须 `POST/PATCH /api/scheduler/config` 持久化到后端，前端状态更新必须在 API 成功响应�?3. API 失败时前端状态必须回滚到切换前值，并显示错误提�?4. 前端必须有定时轮询（�?`setInterval(fetchSchedulerStatus, 10000)`）同步后端状态，避免多端操作不一�?5. 轮询间隔�?`config.yaml` 读取不硬编码

**判断信号**�?- `grep "schedulerStatus\\|scheduler.*enabled" frontend/src/` 后检查状态来源是否为 API 响应 �?前端独立 `useState` 视为违规
- `grep "Switch.*onChange" frontend/src/` 后检�?onChange 是否调用 API �?缺失 API 调用视为违规
- `grep "setInterval.*scheduler" frontend/src/` 检查是否有定时轮询 �?缺失视为违规

**反模�?*�?```typescript
// 前端独立维护 enabled 状态，不调用后�?API
const [enabled, setEnabled] = useState(false);
<Switch checked={enabled} onChange={setEnabled} />  // �?API 调用
```

**正确模式**：`useSchedulerStatus()` 读取状�?�?`api.patch` 持久�?�?乐观更新 + 失败回滚 + `message.error` 提示

**配置参数**：`scheduler_runtime_governance_frontend.scheduler_status_sync.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_api_source`（是否强�?API 为唯一可信源，默认 true）、`require_polling`（是否强制定时轮询，默认 true）、`polling_interval_ms`（轮询间隔，默认 10000）、`require_rollback_on_failure`（是否强制失败回滚，默认 true）在 `config.yaml` �?`scheduler_runtime_governance_frontend.scheduler_status_sync` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #48 + 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-178

**适用**：所有调度器开�?UI（批量采�?Cookie 同步/状态回查）、配置页面中的功能开关组�?**不适用**：纯前端 UI 状态开关（如暗色模�?侧边栏折叠）、无后端持久化需求的临时开�?
**历史教训**：前端批量采集开�?`useState(false)` 独立维护，用户切换后未调用后�?API，刷新页面后状态丢失；且多端操作时前端显示与后端实际状态不一致，用户以为已禁用但后端仍持续执行�?
---

#### F-REVIEW-137：POLLING-INTERVAL-CONFIG 轮询间隔配置化（meta-rule #49 前端侧）🆕v4.40

**检查点**：前端所有定时轮询（`setInterval`/`setTimeout` 递归调用的轮询）的间隔时间必须从配置读取，禁止硬编码字面量数字；配置来源优先级：后端 API 响应 > 前端 config > 默认值�?
**检查项**�?1. `grep "setInterval\\|setTimeout" frontend/src/` 后检查间隔参数来�?�?字面量数字视为违�?2. 轮询间隔必须从配置读取（�?`import { pollingInterval } from '@/config'` 或后�?API 响应�?3. 配置必须提供默认值兜底（�?`pollingInterval ?? 10000`�?4. 页面不可见时（`document.hidden`）必须暂停或降频轮询，使�?`Page Visibility API`
5. 组件卸载时必�?`clearInterval` 清理定时�?
**判断信号**�?- `grep "setInterval\\([^,]*,\\s*\\d+\\)" frontend/src/` 匹配到字面量数字 �?视为违规
- `grep "document.hidden\\|visibilitychange" frontend/src/` 检查是否有页面可见性优�?�?缺失视为 WARNING

**反模�?*�?```typescript
// 硬编码轮询间�?10 �?useEffect(() => {
  const timer = setInterval(fetchData, 10000);  // 字面�?10000
  return () => clearInterval(timer);
}, []);
```

**正确模式**：`config.pollingInterval ?? 10000` 读取间隔 �?`setInterval` 轮询 �?`visibilitychange` 事件暂停/恢复 �?cleanup `clearInterval` + `removeEventListener`

**配置参数**：`scheduler_runtime_governance_frontend.polling_interval_config.enabled`（开关，默认 true）、`severity`（MAJOR）、`forbidden_literals_ms`（禁止的字面量毫秒数，默�?`[5000, 10000, 30000, 60000]`）、`require_default_fallback`（是否强制默认值兜底，默认 true）、`require_visibility_optimization`（是否强制页面可见性优化，默认 true）在 `config.yaml` �?`scheduler_runtime_governance_frontend.polling_interval_config` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #49 + 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-179

**适用**：所有前端定时轮询场景（数据刷新/状态同�?心跳检�?SSE 断线重连�?**不适用**：防�?节流场景（如搜索输入防抖 400ms，属�?UX 参数而非轮询间隔）、动画帧率（`requestAnimationFrame`）、一次性延迟执行（`setTimeout` 非递归�?
**历史教训**：前端状态页 `setInterval(fetchStatus, 10000)` 硬编�?10 秒轮询，用户切到后台标签页后仍持续请求，浪费带宽与服务器资源；且间隔无法根据网络环境调整（弱网环境应降频）�?
---

#### F-REVIEW-138：HOOK-CLEANUP-COMPLETENESS 长生命周�?Hook cleanup 完整性（meta-rule #50 前端侧）🆕v4.40

**检查点**：React Hook 中创建的所有副作用资源（定时器/事件监听�?WebSocket/SSE/订阅/AbortController）必须在 `useEffect` �?cleanup 函数中完整清理，禁止遗漏导致内存泄漏或僵尸更新�?
**检查项**�?1. `useEffect` 中创建的 `setInterval`/`setTimeout` 必须�?cleanup �?`clearInterval`/`clearTimeout`
2. `useEffect` 中添加的 `addEventListener` 必须�?cleanup �?`removeEventListener`
3. `useEffect` 中创建的 `WebSocket`/`EventSource`(SSE) 必须�?cleanup �?`close()`
4. `useEffect` 中创建的 `AbortController` 必须�?cleanup �?`abort()`
5. `useEffect` 中创建的 Zustand `subscribe` 必须�?cleanup 中调用返回的 `unsubscribe` 函数
6. 组件卸载后禁止更�?state（`isMounted` ref �?`AbortController` 防护�?
**判断信号**�?- `grep "useEffect" frontend/src/` 后逐个检查是否有 `return () => { ... }` cleanup �?缺失视为违规
- `grep "setInterval\\|addEventListener\\|new WebSocket\\|new EventSource" frontend/src/` 后检查对�?cleanup �?缺失视为违规
- `grep "subscribe(" frontend/src/` 后检查返回值是否在 cleanup 中调�?�?缺失视为违规

**反模�?*�?```typescript
// useEffect 创建定时器但�?cleanup
useEffect(() => {
  setInterval(fetchData, 10000);  // �?cleanup，组件卸载后仍执�?}, []);

// SSE 连接�?cleanup
useEffect(() => {
  const es = new EventSource('/api/events/stream');
  es.onmessage = (e) => setData(JSON.parse(e.data));
  // �?es.close() cleanup
}, []);

// Zustand subscribe �?unsubscribe
useEffect(() => {
  store.subscribe((state) => setLocalState(state.value));
  // �?unsubscribe cleanup
}, []);
```

**正确模式**：`useEffect` 中创�?`setInterval`/`EventSource`/`subscribe`/`AbortController` �?cleanup `return () => { clearInterval; es.close; unsubscribe; abortController.abort }`；卸载后防护�?`let isMounted = true` + `if (isMounted) setData`

**配置参数**：`scheduler_runtime_governance_frontend.hook_cleanup_completeness.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_cleanup_for`（必�?cleanup 的副作用类型列表，默�?`["setInterval", "setTimeout", "addEventListener", "WebSocket", "EventSource", "subscribe", "AbortController"]`）、`require_unmount_guard`（是否强制卸载后防护，默�?true）在 `config.yaml` �?`scheduler_runtime_governance_frontend.hook_cleanup_completeness` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #50 + 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-180

**适用**：所�?React Hook（`useEffect`/`useLayoutEffect`/自定�?Hook）；创建副作用资源的组件；SSE/WebSocket 实时数据消费组件；Zustand store 订阅组件
**不适用**：纯计算 Hook（无副作用）、只�?Hook（如 `useMemo`/`useCallback`）、SSR 场景（无 DOM 环境�?
**历史教训**：SSE 事件流组�?`useEffect` 中创�?`EventSource` 但无 cleanup，用户切换页面后 SSE 连接未关闭，持续接收事件并尝�?`setState`，导�?组件已卸载仍更新 state"�?React 警告与内存泄漏�?
---

#### F-REVIEW-139：CRON-EXPR-FRONTEND-VALIDATE cron 表达式前端校验（meta-rule #51 前端侧，experimental）🆕v4.40 experimental

**检查点**：前端接受用户输�?cron 表达式的表单组件必须在提交前进行前端校验，解析失败的 cron 表达式必须显示结构化错误提示，最小间隔阈值从配置读取�?
**检查项**�?1. 接受 cron 表达式输入的 `<Input>` / `<Input.TextArea>` 必须有前端校验（`onChange` �?`onBlur` 触发�?2. 校验函数必须使用 `cron-parser` 或等价库解析表达式，解析失败显示结构化错�?3. 校验通过后必须计算最小执行间隔，低于阈值的显示警告（不阻塞提交但提示用户）
4. 最小间隔阈值从 `config.yaml` 读取（默�?60 秒）
5. 表单提交时必须再次校验，禁止提交无效 cron 表达�?
**判断信号**�?- `grep "cron\\|schedule_cron" frontend/src/` 后检查是否有前端校验 �?缺失视为违规
- `grep "cron-parser\\|cronstrue" frontend/src/` 检查是否使用专业库解析 �?内联正则视为 WARNING

**反模�?*�?```typescript
// 接受任意输入，无前端校验
<Input
  value={cronExpr}
  onChange={(e) => setCronExpr(e.target.value)}
  placeholder="* * * * *"
/>
// 提交时直接发送到后端，无前端校验
const handleSubmit = () => {
  api.post('/api/tasks', { schedule_cron: cronExpr });  // 无校�?};
```

**正确模式**：`cron-parser` �?`parseExpression()` 解析 �?计算实际间隔 vs `config.cronMinIntervalSeconds ?? 60` �?`valid/error/warning` 三态返�?�?`Input.onChange` 实时校验 + `status` 属性联�?+ `Alert` 提示 �?`handleSubmit` 提交前再次校�?
**配置参数**：`scheduler_runtime_governance_frontend.cron_expr_frontend_validate.enabled`（开关，默认 true）、`severity`（MAJOR）、`min_interval_seconds`（最小间隔阈值，默认 60）、`require_parser_library`（是否强制使用专业库，默�?true）、`require_submit_revalidate`（是否强制提交时再次校验，默�?true）在 `config.yaml` �?`scheduler_runtime_governance_frontend.cron_expr_frontend_validate` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.36.0 meta-rule #51（experimental�? 后端 `xianyu-backend-code-review` v4.37.0 B-REVIEW-181

**适用**：所有接受用户输�?cron 表达式的表单（任务调度配�?定时采集配置/状态回查配置）
**不适用**：系统内部固�?cron 表达式（非用户输入）、interval 触发器配置（已有 interval 参数）、一次性任务（无重复执行）

**历史教训**：任务调度配置页面接受任�?cron 表达式输入，无前端校验，用户输入 `* * * * *`（每分钟执行）直接提交到后端，后端虽有校验但前端无即时反馈，用户体验差且增加无效请求�?
---

#### F-REVIEW-144：PARAM-CHAIN-EXEC-FRONTEND 参数链闭环验证（meta-rule #52 前端侧）🆕v4.42

**维度**�? API 契约
**严重等级**：critical（P0，过滤参数未消费导致数据泄漏�?
**检查点**：前端定义的 query 参数必须能在后端找到对应的消费逻辑，前端发送的过滤参数必须被后端实际消�?
**检查项**�?1. 前端 API 调用传递的过滤参数（如 market_ratio、price_range）必须对应后端的消费函数
2. 前端 types.ts 中声明的过滤参数字段必须与后�?API 签名一�?3. 前端单元测试应验�?传参 vs 不传�?的请�?URL 差异

**判断信号**�?- `grep "market_ratio\|price_range" frontend/src/api/` 但后端无对应消费逻辑 �?视为违规
- 前端 types.ts 声明过滤参数但后�?API 签名无对应参�?�?契约不一�?
**配置参数**：`param_chain_exec_frontend.metadata_whitelist`（默认同后端）在 `config.yaml` �?`param_chain_exec_frontend` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #52

**适用**：所有有过滤参数的列表查�?API 前端调用
**不适用**：GET 单个资源详情、DELETE 接口、创建类 POST 接口

**历史教训**：前端传�?`market_ratio=0.85` 参数但后�?`evaluations_list.py` 未调�?`PriceStrategy.check`，导致过滤未生效。修复：前后端同步闭�?
---

#### F-REVIEW-145：MODE-VERTICAL-CHAIN-FRONTEND 业务模式纵向链路一致性（meta-rule #53 前端侧）🆕v4.42

**维度**�? 业务逻辑
**严重等级**：critical（P0，模式退化导致业务逻辑失效�?
**检查点**：前端必须为每个 mode 枚举值提供对应路由、页面、组件，mode 字段名前后端严格一�?
**检查项**�?1. 前端枚举值必须与后端一致（�?AUTO/SEMI_AUTO/MANUAL�?2. 每个 mode 值在前端路由/页面/组件中都有引�?3. SEMI_AUTO 模式必须有确认路由（�?/confirm-buy�?4. mode 字段名严�?snake_case 透传，禁�?camelCase 转换

**判断信号**�?- `grep "SEMI_AUTO\|AUTO\|MANUAL" frontend/src/` 在路�?页面中未命中 �?链路断裂
- 前端 types.ts �?`taskMode` 而后端用 `task_mode` �?命名漂移

**配置参数**：`mode_vertical_chain_frontend.required_layers`（默�?`["router","page","component","api_wrapper"]`）、`mode_vertical_chain_frontend.mode_field_names`（默认同后端）在 `config.yaml` �?`mode_vertical_chain_frontend` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #53

**适用**：任务执行模式、通知模式、采集模式的前端实现
**不适用**：纯展示�?mode 字段、内部状态字段、单一布尔开�?
**历史教训**：SEMI_AUTO 模式退化为 CONFIRM/NOTIFY，前端无 /confirm-buy 路由，用户点击通知无反应。修复：新增 ConfirmBuy 页面+路由

---

#### F-REVIEW-146：MOCK-SYNC-BOUNDARY-FRONTEND mock 同步与边界精确性（meta-rule #55 前端侧）🆕v4.42

**维度**�?2 可测试�?**严重等级**：critical（P0，mock 错配导致测试假阳�?假阴性）

**检查点**：前�?vitest mock 类型必须与被 mock 对象的同�?异步特性匹配，mock 数据必须覆盖完整字段�?
**检查项**�?1. 同步函数�?`vi.fn()`，异步函数用 `vi.fn().mockResolvedValue()` �?`vi.mock()` 中用 async
2. mock 数据必须覆盖组件访问的所有字�?3. 测试必须断言副作用未发生（如未发起真�?API 请求�?
**判断信号**�?- `grep "vi.fn\(\)" frontend/src/__tests__/` 但被 mock 函数�?async �?违规
- mock 数据缺字段导致组件渲�?NPE �?不完�?
**配置参数**：`mock_sync_frontend.type_mapping`（默�?`{"sync":"vi.fn()","async":"vi.fn().mockResolvedValue()"}`）、`mock_sync_frontend.required_assertions`（默�?`["no_real_api_request","no_real_router_change"]`）在 `config.yaml` �?`mock_sync_frontend` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #55

**适用**：所�?vitest 单元测试、集成测试中�?mock
**不适用**：E2E 测试、快照测�?
**历史教训**：后�?AsyncMock 用在同步函数导致测试失败，前端类似问题用 vi.fn() mock 异步函数也会导致 await 失败

---

#### F-REVIEW-147：FILTER-RESULT-TRANSPARENCY-UI 过滤结果透明�?UI（meta-rule #56 前端侧）🆕v4.42

**维度**�? API 契约
**严重等级**：warning（P1，用户无法理�?为何查不到数�?�?
**检查点**：列表查�?UI 同时�?�? 个过滤参数时必须透明化展示当前生效的过滤规则组合

**检查项**�?1. 关键过滤参数提供 Tooltip 说明查询规则（用 QuestionCircleOutlined 图标�?2. 空结果时区分"无数�?vs"被过滤排�?vs"全部数据"三态（filter_summary�?3. UI 显式列出当前生效的过滤参数组�?4. 业务参数展示语义化文案（�?低于市场参考价 15%"而非"0.85"�?
**判断信号**�?- `grep "filter.*range\|market.*ratio\|min.*max" frontend/src/pages/` 在列�?UI 但无 `Tooltip`/`filter_summary` �?违规
- `grep "empty.*data\|no.*data"` 但无 `filtered_count`/`total_count` 区分 �?违规

**配置参数**：`filter_transparency_ui.min_filter_params`（默�?2）、`filter_transparency_ui.required_elements`（默�?`["tooltip","filter_summary"]`）、`filter_transparency_ui.filter_summary_states`（默�?`["no_data","filtered_empty","all_data"]`）在 `config.yaml` �?`filter_transparency_ui` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.37.0 meta-rules #56

**适用**：所有多参数列表查询 UI（评估明�?商品列表/订单列表/仪表盘过滤）
**不适用**：单一过滤参数、用户主动输入的查询条件、详情页

**历史教训**：用户调�?低于市场参考价"�?0.85 后，评估明细菜单仍能查出价格上限 800 的商品，�?UI 无任何提示当前生效的过滤规则。修复：在价格范�?label 处添�?QuestionCircleOutlined 图标+Tooltip 说明查询规则

---

#### F-REVIEW-148：ASYNC-AWAIT-SYNC-CHECK-FRONTEND async/await 同步性检查（meta-rule #57 前端侧）🆕v4.43

**维度**�?0 Hooks 设计模式
**严重等级**：critical（P0，useEffect 直接�?async 函数导致 React 警告 + 内存泄漏�?**规范引用**：meta-rule #57 async/await 同步性静态检查（前端侧）

**检查点**：React useEffect �?async 函数必须�?`.then()` �?IIFE 包裹，禁�?`async () => {}` 直接传给 useEffect

**检查项**�?1. useEffect 回调函数禁止�?async 函数（`useEffect(async () => {...})` 视为违规�?2. useEffect 内的 async 操作必须�?IIFE 包裹�?`.then()` 链式调用
3. 必须�?`cancelled` 标志防止组件卸载�?setState（内存泄漏防护）
4. 事件回调（onClick/onSubmit）中�?async 函数必须处理 rejection

**判断信号**�?- `grep "useEffect(async" frontend/src/` �?视为违规
- `grep "useEffect.*async.*=>" frontend/src/` �?视为违规

**反模�?*�?```typescript
// useEffect 直接�?async 函数
useEffect(async () => {
  const data = await fetchData();
  setData(data);
}, []);
// React 警告: "Effect callback cannot be async"
// cleanup 返回 Promise 导致取消逻辑失效
```

**正确模式**：`useEffect` 内用 `let cancelled = false` + IIFE `(async () => { await fetchData(); if (!cancelled) setData(data) })()` + cleanup `cancelled = true`

**配置参数**：`meta_rules_57_63_frontend.frontend_async_await_check.enabled`（默�?true）、`meta_rules_57_63_frontend.frontend_async_await_check.severity`（默�?CRITICAL）、`meta_rules_57_63_frontend.frontend_async_await_check.forbidden_patterns`（默�?`["useEffect(async", "useEffect.*async.*=>"]`）、`meta_rules_57_63_frontend.frontend_async_await_check.require_cancellation_flag`（默�?true）在 `config.yaml` �?`meta_rules_57_63_frontend.frontend_async_await_check` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #57

**适用**：React useEffect 副作用、事件回调（onClick/onSubmit 等）中的 async 函数
**不适用**：top-level await（模块顶层）、`await import()` 动态导入、async generator 函数

**历史教训**：useEffect 直接�?async 函数导致 React 警告 "Effect callback cannot be async"，且 cleanup 返回 Promise 导致取消逻辑失效，组件卸载后异步操作�?setState 引发内存泄漏

---

#### F-REVIEW-149：HTTP-ERROR-LOCALIZATION HTTP 错误本地化（meta-rule #59 前端侧）🆕v4.43

**维度**�? API 契约
**严重等级**：warning（P1，优先用后端英文 detail 对中文用户不友好�?**规范引用**：meta-rule #59 HTTP 状态码精细化映射表（前端侧�?
**检查点**：已知状态码优先用前端中�?`statusMessages[status]`，后�?detail 仅作 fallback

**检查项**�?1. 已知状态码优先用前端中文消息（`statusMessages[status]`�?2. 多状态码场景必须建立状态码 �?中文消息映射�?3. 未知状态码可回退到后�?detail，但必须标注 fallback 行为
4. 状态码映射表必须在 `api/<�?.ts` 顶层声明，禁止散落在组件�?
**判断信号**�?- `grep "detail ||" frontend/src/` �?视为违规（优先用 detail 而非 statusMessages�?- `grep "message.error.*detail" frontend/src/` �?视为违规

**反模�?*�?```typescript
catch (err) {
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;
  message.error(detail || statusMessages[status]);  // 优先用后端英�?detail
}
// 用户看到 "Failed to collect item: detail page unavailable or item removed"
// 中文用户无法理解
```

**正确模式**：`COLLECT_ERROR_MESSAGES: Record<number, string>` 状态码→中文消息映射（503/403/440/441/410/502）→ catch �?`status` 查表优先展示中文 �?未知状�?fallback �?`detail || fallbackMessage`

**配置参数**：`meta_rules_57_63_frontend.frontend_http_error_localization.enabled`（默�?true）、`meta_rules_57_63_frontend.frontend_http_error_localization.severity`（默�?WARNING）、`meta_rules_57_63_frontend.frontend_http_error_localization.prefer_frontend_message`（默�?true）、`meta_rules_57_63_frontend.frontend_http_error_localization.status_messages_required`（默�?true）、`meta_rules_57_63_frontend.frontend_http_error_localization.fallback_to_detail`（默�?true）、`meta_rules_57_63_frontend.frontend_http_error_localization.localized_languages`（默�?`["zh-CN"]`）在 `config.yaml` �?`meta_rules_57_63_frontend.frontend_http_error_localization` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #59

**适用**：所�?HTTP 错误响应处理（catch 块中读取 `err.response.status` �?`err.response.data.detail`�?**不适用**：前端无对应状态码映射的未知错误、调试模式需展示原始 detail、纯技术内部错误不向用户展�?
**历史教训**：useEvalCollect.ts 优先用后�?detail 展示 "Failed to collect item 1053036882534: detail page unavailable or item removed"，对中文用户不友好，用户无法理解错误含义。修复：建立 COLLECT_ERROR_MESSAGES 状态码映射表，优先用中文消�?
---

#### F-REVIEW-150：ERROR-CHAIN-TRANSPARENT 错误链透明化（meta-rule #61 前端侧）🆕v4.43

**维度**�? API 契约 / 4 业务逻辑
**严重等级**：warning（P1，仅展示"采集失败"�?reason 用户无法判断�?**规范引用**：meta-rule #61 异常日志语义保留规范（前端侧�?
**检查点**：错误链路需透明展示 reason/failure_reason，用户可见错误必须含可操作建�?
**检查项**�?1. 错误消息必须�?reason 字段（来自后�?failure_reason�?2. 错误消息必须含可操作建议（如"请重新登录闲�?�?3. 错误必须标注 retryable 让用户知道是否可重试
4. 多阶段降级链必须合并展示最终生效路径（�?官方采集失败 �?降级到模拟采�?必须�?UI 体现�?
**判断信号**�?- `grep "message.error\|notification.error" frontend/src/` 后检查错误消息是否含 reason 与建�?- `grep "message.error\('采集失败'\)" frontend/src/` �?视为违规（无 reason�?
**反模�?*�?```typescript
message.error('采集失败');
// 用户无法判断�?cookie 过期还是反爬限制
// 需查看后端日志才能定位
```

**正确模式**：`message.error({ content: \`采集失败�?{reason}。建议：${actionHint}\`, duration: 8 })` 或结构化对象 `{ title, reason: failure_reason, suggestion: getSuggestionByReason(), retryable: isRetryable() }`

**配置参数**：`meta_rules_57_63_frontend.frontend_error_chain_transparent.enabled`（默�?true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.severity`（默�?WARNING）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.require_reason`（默�?true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.require_suggestion`（默�?true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.require_retryable_flag`（默�?true）、`meta_rules_57_63_frontend.frontend_error_chain_transparent.multi_stage_merge`（默�?true）在 `config.yaml` �?`meta_rules_57_63_frontend.frontend_error_chain_transparent` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #61

**适用**：所有错误展示组件（message.error / notification.error / Modal.error�?**不适用**：纯成功场景、loading 状态、开发调试日志（console.error�?
**历史教训**：前端仅展示"采集失败"�?reason，用户无法判断是 cookie 过期还是反爬限制，需查看后端日志才能定位。修复：错误消息�?reason + suggestion + retryable 三字�?
---

#### F-REVIEW-151：EXTERNAL-RESOURCE-CLEANUP-FRONTEND 外部资源清理（meta-rule #62 前端侧）🆕v4.43

**维度**�?0 Hooks 设计模式 / 6 Zustand 状态管�?**严重等级**：critical（P0，组件卸载后资源未释放导致内存泄漏与重复消息�?**规范引用**：meta-rule #62 外部资源生命周期配对管理（前端侧�?
**检查点**：useEffect 内创建的订阅/定时�?AbortController 必须�?cleanup 中释�?
**检查项**�?1. useEffect 内创建的 WebSocket 必须�?cleanup 中调�?`ws.close()`
2. useEffect 内创建的 EventSource 必须�?cleanup 中调�?`es.close()`
3. useEffect 内的 `setInterval`/`setTimeout` 必须�?cleanup 中调�?`clearInterval`/`clearTimeout`
4. useEffect 内的 `addEventListener` 必须�?cleanup 中调�?`removeEventListener`
5. useEffect 内的 AbortController 必须�?cleanup 中调�?`controller.abort()`
6. useEffect 必须返回 cleanup 函数（当创建了上述资源时�?
**判断信号**�?- `grep "useEffect" frontend/src/` 后检查是否返�?cleanup 函数
- `grep "setInterval\|setTimeout\|addEventListener\|new WebSocket\|new AbortController" frontend/src/` 检查是否在 cleanup 中释�?
**反模�?*�?```typescript
useEffect(() => {
  const ws = new WebSocket('ws://localhost:8080');
  ws.onmessage = (e) => setMessage(e.data);
  // 缺少 return () => ws.close();
}, []);
// 组件卸载�?WebSocket 仍保持连�?// 导致内存泄漏与重复消�?```

**正确模式**：`useEffect` 内创�?`AbortController` + `WebSocket` �?cleanup `return () => { controller.abort(); ws.close() }`

**配置参数**：`meta_rules_57_63_frontend.frontend_external_resource_cleanup.enabled`（默�?true）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.severity`（默�?CRITICAL）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.resource_types`（默�?`["WebSocket", "EventSource", "setInterval", "setTimeout", "addEventListener", "AbortController"]`）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.require_cleanup_return`（默�?true）、`meta_rules_57_63_frontend.frontend_external_resource_cleanup.pair_required`（默�?true）在 `config.yaml` �?`meta_rules_57_63_frontend.frontend_external_resource_cleanup` 节点管理

**对应编码规范**：详�?`xianyu-hunter-dev` v4.38.0 meta-rule #62

**适用**：所�?useEffect 副作用中创建的外部资源（WebSocket/EventSource/定时�?事件监听�?AbortController�?**不适用**：无副作用的纯渲染组件、React 组件卸载时自动清理的资源（如 useState 管理的状态）

**历史教训**：useEffect 创建 WebSocket 但无 cleanup，组件卸载后 WebSocket 仍保持连接，导致内存泄漏与重复消息（每次组件重新挂载都会新建连接�?
---

#### F-REVIEW-152 experimental：URL-STATE-SYNC-FALLBACK URL↔状态同步失败回退（meta-rule #64 前端侧）🆕v4.44 experimental

**维度**�? React 状态管�?/ 19 跨组件状态同�?**严重等级**：critical（P0，URL �?active sheet 不一致导�?useParams 返回错误值，业务逻辑误判�?**规范引用**：meta-rule #64 URL↔状态同步失败回退（experimental�?
**检查点**：SheetWorkspace 多页签应用中，URL 变化触发 openSheet 失败时，必须回退 URL 到当�?active sheet �?path

**检查项**�?1. useSheetSync Hook 监听 URL 变化时，�?openSheet 返回 false（路径未注册/栈满），必须调用 `navigate(activeSheet.path, { replace: true })` 回退 URL
2. 回退必须�?URL 变化事件处理中同步执行，不能延迟到下一帧（防止 useParams 读取到错误的 URL�?3. 回退动作必须记录日志（`logger.debug('URL sync failed, fallback to active sheet')`�?
**判断信号**�?- `grep "openSheet\|findSheetMeta" frontend/src/hooks/useSheetSync.ts` 后检查是否在 openSheet 失败时回退 URL
- `grep "navigate\|location.pathname" frontend/src/hooks/useSheetSync.ts` 检查是否有 fallback 逻辑

**反模�?*�?```typescript
useEffect(() => {
  const sheet = findSheetMeta(location.pathname);
  if (sheet) {
    openSheet(sheet.id);
  }
  // 缺少 else { navigate(activeSheet.path, { replace: true }) }
}, [location.pathname]);
// URL 已改变但 activeId 未变 �?useParams() 返回错误�?�?isEdit 误判�?false
```

**正确模式**：`useEffect` �?`findSheetMeta(pathname)` �?`openSheet(sheet.id)` 失败�?sheet 未找到时 `navigate(activeSheet.path, { replace: true })` 回退 + `logger.debug` 记录

**配置参数**：`url_state_sync_fallback` 节点（在 `config.yaml` 管理，不硬编码）�?- `enabled`（默�?`true`，开关本检查）
- `fallback_strategy`（默�?`replace`，回退策略：replace/push�?- `detection_patterns`（默�?`["navigate", "openSheet", "findSheetMeta"]`，需要检测的函数�?- `applicable_routes`（默�?`["/tasks", "/config/search"]`，适用路由白名单）

**对应编码规范**：详�?`xianyu-hunter-dev` v4.39.0 experimental meta-rule #64

**适用**：SheetWorkspace 多页签应用（useSheetSync Hook）；URL �?sheet 状态双向同步场�?**不适用**：单页应用（�?SheetWorkspace）；静态路由（无动�?sheet 注册�?
**历史教训**：任务修改流程中点击 Step 3「全局搜索配置」按钮，navigate('/app/config/search') 多了 /app 前缀（basename），findSheetMeta 返回 undefined，触�?React Router 重定向到 /。此�?URL 变为 /，但 activeId 仍指�?TaskEditor，useParams().id 返回 undefined，isEdit 误判�?false，提交时创建重复任务�?
**experimental 观察�?*：案例数<3 次，�?meta-rule #36 门槛规则�?experimental，观察期 2026-07-08 �?2026-10-08�? 季度）。观察期内若再出�?�? 个相�?bug 则升级为正式规范，否则废弃�?
---

#### F-REVIEW-153 experimental：SW-CACHE-VERSION-SYNC SW 缓存版本同步（meta-rule #65 前端侧）🆕v4.44 experimental

**维度**�?3 PWA 配置 / 10 Hooks 设计模式
**严重等级**：warning（P1，缓存旧版本导致功能异常，但用户可手动刷新解决）
**规范引用**：meta-rule #65 Service Worker 缓存版本同步（experimental�?
**检查点**：PWA 应用构建时生成的版本哈希必须与前端运行时检测的版本一致，版本不一致时触发 skipWaiting 强制更新

**检查项**�?1. vite-plugin-pwa 配置必须生成版本哈希（`strategies: 'generateSW'`，`manifest: { version: process.env.VITE_BUILD_VERSION }`�?2. 前端必须�?sw.js 注册时监�?`updatefound` 事件，新 SW 进入 waiting 状态时提示用户刷新
3. 用户确认刷新时调�?`registration.waiting.postMessage({ type: 'SKIP_WAITING' })` 触发 skipWaiting
4. 版本检测必须在应用启动时执行（main.tsx �?App.tsx），不能延迟到用户操作后

**判断信号**�?- `grep "vite-plugin-pwa" frontend/vite.config.ts` 检查是否配置版本生�?- `grep "updatefound\|SKIP_WAITING\|registration.waiting" frontend/src/` 检查是否有版本检测逻辑
- `grep "navigator.serviceWorker.register" frontend/src/` 检查是否有版本同步 Hook

**反模�?*�?```typescript
// vite.config.ts 缺少版本配置
VitePWA({
  strategies: 'generateSW',
  // 缺少 manifest.version
});

// main.tsx 注册 SW 但无版本检�?navigator.serviceWorker.register('/sw.js');
// 用户缓存旧版�?�?功能异常（如 PC 端重定向到移动端�?```

**正确模式**：`VitePWA({ strategies: 'generateSW', manifest: { version: process.env.VITE_BUILD_VERSION || Date.now() } })` + `useSWVersion()` Hook 监听 `registration.updatefound` �?`newWorker.statechange` �?`setNeedsRefresh(true)` + `skipWaiting()` 调用 `registration.waiting.postMessage({ type: 'SKIP_WAITING' })`

**配置参数**：`sw_cache_version_sync` 节点（在 `config.yaml` 管理，不硬编码）�?- `enabled`（默�?`true`，开关本检查）
- `version_detection`（默�?`updatefound`，版本检测方式：updatefound/manual�?- `skip_waiting_trigger`（默�?`postMessage`，触发方式：postMessage/reload�?- `hard_refresh_prompt`（默�?`true`，是否提示用户硬刷新�?
**对应编码规范**：详�?`xianyu-hunter-dev` v4.39.0 experimental meta-rule #65

**适用**：PWA 应用（vite-plugin-pwa）；Service Worker 缓存静态资源场�?**不适用**：非 PWA 应用（无 Service Worker）；�?SSR 应用（无客户端缓存）

**历史教训**：PC 端首次登录后重定向到 /app/m/（移动端），根因是浏览器缓存了旧�?sw.js，旧�?SPA �?useMobileDetect.ts �?pointer:coarse 触屏判断导致 PC 端误判为移动端�?
**experimental 观察�?*：案例数<3 次，�?meta-rule #36 门槛规则�?experimental，观察期 2026-07-08 �?2026-10-08�? 季度）。观察期内若再出�?�? 个相�?bug 则升级为正式规范，否则废弃�?
---

#### F-REVIEW-154：INTERCEPTOR-STATUS-CODE-DISCRIMINATION 全局拦截器状态码区分检查（meta-rule #66 前端侧）🆕v4.45

**维度**�? API 契约
**严重等级**：critical（P0，业�?401 被误判为认证失效导致用户被踢出登录页�?**规范引用**：meta-rule #66 全局拦截器状态码区分检�?
**关注�?*：axios/fetch 全局响应拦截器跳转登录页必须基于 status + detail 双重校验

**与已有规则的关系**�?- 已有 `auth_token_cookie_handling.forbidden_error_handling_patterns` 关注「业务代�?catch 块的错误处理模式�?- F-REVIEW-154 关注「axios/fetch 全局响应拦截器层面的精确化跳转条件�?- 两者互补，F-REVIEW-154 补齐了拦截器层面的检查缺�?
**检查规�?*�?1. 拦截器跳转登录页必须同时满足 `status === 401` + `detail === 'Unauthorized'`（或配置的其他认证中间件标识�?2. 禁止仅凭 `status === 401` 即跳转，未检�?`detail` 字段
3. 业务错误�?40/422/429/410）应由调用方 catch 后展�?detail，不应被全局拦截器拦截跳�?4. 拦截器处理后必须 `return Promise.reject(error)`，让调用�?catch 继续处理业务错误

**配置节点**：`config.yaml#interceptor_audit`

**配置结构**�?- `auth_redirect.conditions`：跳转条件数组（status + detail_equals + action），新增认证中间件标识时只需追加
- `auth_redirect.require_all_conditions`：true（必须同时满足所有条件）
- `auth_redirect.forbidden_interceptor_patterns`：禁止的拦截器模式（仅凭 status 跳转�?- `auth_redirect.recommended_pattern`：推荐的拦截器代码示�?- `business_error_handling`：业务错误处理数组（status + action�?- `require_reject_after_intercept`：true（拦截器必须 reject�?
**判断信号**�?- `grep -rn "status === 401" frontend/src/api/` 命中且无 `detail === 'Unauthorized'` 校验 �?拦截器过�?- `grep -rn "case 401:" frontend/src/api/` 命中�?switch 未检�?detail �?拦截器过�?- 拦截�?`if (status >= 400)` 即跳�?�?业务错误被全局拦截

**反模�?*�?```typescript
// 禁止：拦截器仅凭 status === 401 即跳转登录页，业�?401（闲�?cookie 过期）也会被误判为认证失效；应同时校�?detail === 'Unauthorized' 或使�?440 状态码区分
```

**正确模式**：拦截器 `status === 401 && detail === 'Unauthorized'` 双重校验 �?`localStorage.removeItem('xh_token')` + `globalThis.location.replace(import.meta.env.BASE_URL + 'login?redirect=...')`（排�?login �?+ `isRedirecting` 防重复跳转）�?业务 401 由调用方 catch

**配置参数**：`interceptor_audit` 节点（在 `config.yaml` 管理，不硬编码）�?- `auth_redirect.conditions`（默�?`[{status: 401, detail_equals: "Unauthorized", action: "redirect_to_login"}]`，跳转条件数组）
- `auth_redirect.require_all_conditions`（默�?`true`，必须同时满�?status �?detail 才跳转）
- `auth_redirect.forbidden_interceptor_patterns`（禁止的拦截器模式，仅凭 status 跳转�?- `auth_redirect.recommended_pattern`（推荐的拦截器代码示例）
- `business_error_handling`（业务错误处理数组：440/422/429/410 由调用方 catch�?- `require_reject_after_intercept`（默�?`true`，拦截器必须 reject�?
**对应编码规范**：详�?`xianyu-hunter-dev` v4.45.0 meta-rule #66

**适用场景**：axios/fetch 全局响应拦截器；�?Bearer/JWT 认证的前端应用；SPA 应用；与后端 FastAPI BearerAuthMiddleware 配套的前�?**不适用场景**：无认证应用；纯 SSR 应用；测�?mock

**修复建议**�?- 拦截器同时校�?status + detail
- 业务错误 reject 给调用方 catch
- 拦截器必�?return Promise.reject(error)

**复盘来源**：业�?401 与认�?401 状态码冲突 Bug（卖家评估页点击标题链接跳转登录页）

---

#### F-REVIEW-220：CACHE-CONSISTENCY-CHECK 缓存一致性审查（§2.15 缓存策略规范 前端侧）🆕v4.60

**维度**：10 Hooks 设计模式 / 7 API 契约
**严重等级**：major（P1，前端缓存 TTL 超过后端导致脏数据，依赖数组缺失导致闭包陈旧值）
**规范引用**：§2.15 缓存策略规范（前端侧落地）

**检查点**：前端 `useMemo`/`useCallback` 依赖数组必须完整，本地缓存 TTL 必须与后端 `cache.live_search_ttl` 协调（前端不应长于后端 TTL），缓存失效后必须自动重新请求

**定位方法**：`grep -rn "useMemo\|useCallback\|useCache\|cache" frontend/src/` 定位前端缓存使用点

**判断标准**：
1. `useMemo`/`useCallback` 依赖数组是否完整（遗漏依赖会导致闭包捕获陈旧值）
2. 前端本地缓存 TTL 是否与后端协调（后端 `cache.live_search_ttl=5s`，前端不应长于此后端 TTL）
3. 缓存失效后是否自动重新请求（避免用户看到过期数据）

**判断信号**：
- `grep -rn "useMemo\|useCallback" frontend/src/` 后检查第二参数依赖数组 → 缺失或为空数组（且函数体引用外部变量）视为违规
- 前端 TTL 字面量数字 > 5000（5s）→ 视为可疑（超过后端 `cache.live_search_ttl`）
- 缓存失效逻辑（如 `invalidateCache`/`cache.clear`）后无 `refetch`/`fetch` 调用 → 视为违规

**反模式**：
```typescript
// 1. 依赖数组缺失，过滤条件变更后展示旧数据
const value = useMemo(() => filter(items, filterKey), []);  // 缺 filterKey 依赖

// 2. 前端 TTL 超过后端 cache.live_search_ttl
const cache = useRef({ data: null, ts: 0 });
if (Date.now() - cache.current.ts < 30000) return cache.current.data;  // 30s > 后端 5s

// 3. 缓存失效不重新请求，用户看到过期数据
invalidateCache();  // 缺少 refetch() 调用
```

**正确模式**：
1. 依赖数组完整：`useMemo(() => filter(items, filterKey), [items, filterKey])`
2. 前端 TTL 不超过后端 `cache.live_search_ttl`：从配置读取 `const cacheTtl = config.cacheTtl ?? 5000`
3. 缓存失效后自动 refetch：`invalidateCache(); void refetch();`

**配置参数**：`cache_consistency_check` 节点（在 `config.yaml` 管理，不硬编码）：
- `enabled`（默认 `true`，开关本检查）
- `backend_ttl_ms`（默认 `5000`，与后端 `cache.live_search_ttl` 同步值）
- `frontend_ttl_max_ms`（默认 `5000`，前端 TTL 上限，超过则违规）
- `require_full_deps`（默认 `true`，强制 `useMemo`/`useCallback` 依赖完整）
- `require_refetch_on_invalidate`（默认 `true`，缓存失效后必须 refetch）

**修复建议**：前端缓存 TTL 不超过后端 `cache.live_search_ttl`，依赖数组必须完整，缓存失效后必须触发 refetch

**对应编码规范**：详见 `coding-standards.md` §2.15 缓存策略规范

**适用**：所有前端 `useMemo`/`useCallback`/`useCache`/`localStorage` 缓存场景；与后端 `cache.live_search_ttl` 协调的列表查询/搜索结果缓存
**不适用**：纯静态常量缓存（如 enum 映射表、配置常量）；用户偏好持久化（如 `usePersistentState`，与后端无关）；SSR 场景（无客户端缓存）

**历史教训**：前端搜索结果缓存 TTL 设为 30s，但后端 `cache.live_search_ttl=5s` 已更新数据，导致用户看到 25s 前的过期数据；且 `useMemo` 依赖数组为空，过滤条件变更后仍展示旧数据。修复：依赖数组补全 + 前端 TTL 对齐后端 + 失效后 refetch

---

#### F-REVIEW-221：MULTI-FORMAT-INPUT-PARSE 多格式输入解析审查（§2.20 多格式输入解析规范 前端侧）🆕v4.60

**维度**：4 TypeScript 严格规范 / 7 API 契约
**严重等级**：major（P1，输入解析覆盖不全导致部分格式数据丢失，split('=') 截断值中含 = 的数据）
**规范引用**：§2.20 多格式输入解析规范（前端侧落地）

**检查点**：粘贴板解析必须覆盖所有格式（标准头/换行分隔/Header 前缀/尾分号），必须有实时解析反馈（识别 N 项/填充 N 项/无效 N 项），分割点必须用 `indexOf('=')` 而非 `split('=')` 避免值中含 `=` 被截断

**定位方法**：`grep -rn "split\|parse\|clipboard\|paste\|onPaste" frontend/src/` 定位输入解析逻辑

**判断标准**：
1. 粘贴板解析是否覆盖所有格式（标准头/换行分隔/Header 前缀/尾分号）
2. 是否有实时解析反馈（识别 N 项/填充 N 项/无效 N 项）
3. 分割点是否用 `indexOf('=')` 而非 `split('=')` 避免值中含 `=` 被截断

**判断信号**：
- `grep -rn "split('=')" frontend/src/` 命中 → 视为违规（值含 `=` 会被截断，如 `password=a=b` 丢失 `=b`）
- 粘贴板解析逻辑仅处理单一格式（如只处理 `\n` 换行分隔）→ 视为违规
- `onPaste`/`onChange` 处理函数无识别/填充/无效计数反馈 → 视为 WARNING

**反模式**：
```typescript
// 1. 用 split('=') 导致值含 = 被截断
const [key, value] = line.split('=');  // "k=v=1" → value="v"，丢失 "=1"

// 2. 仅处理单一格式（只处理换行分隔）
const lines = text.split('\n');  // 未处理尾分号、Header 前缀等格式

// 3. 无实时反馈，用户不知道识别了多少项
onPaste={(e) => {
  const data = parse(e.clipboardData.getData('text'));
  setForm(data);  // 用户不知道识别/填充/无效各几项
}}
```

**正确模式**：
1. 用 `indexOf('=')` 容错分割：`const idx = line.indexOf('='); const key = line.slice(0, idx); const value = line.slice(idx + 1);`
2. 枚举所有格式：标准头（`key=value\n`）、换行分隔、Header 前缀（`Header: value`）、尾分号（`key=value;`）
3. 实时视觉反馈：`{识别 N 项，填充 N 项，无效 N 项}` + 高亮无效行

**配置参数**：`multi_format_input_parse` 节点（在 `config.yaml` 管理，不硬编码）：
- `enabled`（默认 `true`，开关本检查）
- `supported_formats`（默认 `["standard_header", "newline_delimited", "header_prefix", "trailing_semicolon"]`，必须覆盖的格式列表）
- `forbid_split_on_equals`（默认 `true`，禁止 `split('=')`，必须用 `indexOf('=')`）
- `require_realtime_feedback`（默认 `true`，强制识别/填充/无效计数反馈）

**修复建议**：枚举所有格式 + `indexOf('=')` 容错分割 + 实时视觉反馈，参考 §2.20

**对应编码规范**：详见 `coding-standards.md` §2.20 多格式输入解析规范

**适用**：所有接受粘贴板输入的表单（批量配置/批量导入/多行文本解析）；含 `key=value` 结构的输入场景
**不适用**：单行输入框（无粘贴板解析需求）；纯数字/日期输入；结构化 JSON 输入（用 `JSON.parse` 即可）；文件上传（非文本粘贴）

**历史教训**：批量配置粘贴板解析仅处理换行分隔，用户粘贴带尾分号的格式（`key=value;`）时全部识别失败；且 `split('=')` 截断了含 `=` 的值（如 `password=a=b`），导致配置丢失。修复：枚举 4 种格式 + `indexOf('=')` 分割 + 实时计数反馈

---

#### F-REVIEW-222：STREAMING-RESPONSE-HANDLER 流式响应处理审查（§2.17 性能优化范式 前端侧）🆕v4.60

**维度**：15 SSE 重连 / 10 Hooks 设计模式
**严重等级**：critical（P0，stage=error 未清理连接导致内存泄漏 + 状态卡死，stage=done 未关闭连接导致连接泄漏）
**规范引用**：§2.17 性能优化范式（前端侧落地）

**检查点**：必须正确处理 SSE stage 事件（checking_cache/searching/filtering/done/error），stage=error 时必须清理连接和状态，stage=done 时必须关闭 EventSource 连接，必须有超时兜底处理

**定位方法**：`grep -rn "EventSource\|SSE\|event-stream\|stage" frontend/src/` 定位 SSE 处理逻辑

**判断标准**：
1. 是否正确处理 SSE stage 事件（checking_cache/searching/filtering/done/error）
2. stage=error 时是否正确清理连接和状态
3. stage=done 时是否正确关闭 EventSource 连接
4. 是否有超时兜底处理（避免 SSE 卡住无响应）

**判断信号**：
- `grep -rn "EventSource\|event-stream" frontend/src/` 后检查 stage 事件处理 → 未覆盖 error/done 视为违规
- stage=error 处理分支未调用 `es.close()` 与状态重置 → 视为违规
- stage=done 处理分支未调用 `es.close()` → 视为违规（连接泄漏）
- SSE 处理逻辑无 `setTimeout`/`AbortController` 超时兜底 → 视为 WARNING

**反模式**：
```typescript
// 1. 未处理 stage=error，错误时状态卡死在 searching
es.addEventListener('stage', (e) => {
  const { stage } = JSON.parse(e.data);
  if (stage === 'searching') setSearching(true);
  if (stage === 'done') setSearching(false);
  // 缺少 error 处理 → 错误时状态卡死
});

// 2. stage=done 未关闭连接，每次搜索泄漏一个 EventSource
if (stage === 'done') {
  setData(result);
  // 缺少 es.close() → 连接泄漏
}

// 3. 无超时兜底，SSE 卡住时 UI 永远 loading
const es = new EventSource('/api/search/stream');
// 无 setTimeout 兜底
```

**正确模式**：
1. 按 stage 分发处理：`switch(stage) { case 'checking_cache': ...; case 'searching': ...; case 'filtering': ...; case 'done': ...; case 'error': ...; }`
2. stage=error 时清理：`es.close(); setState(STATE_ERROR); clearTimeout(timer);`
3. stage=done 时关闭连接：`es.close(); setState(STATE_DONE); clearTimeout(timer);`
4. 超时兜底：`const timer = setTimeout(() => { es.close(); setState(STATE_TIMEOUT); }, config.sseTimeoutMs ?? 30000);` 在 done/error/cleanup 中 `clearTimeout(timer)`

**配置参数**：`streaming_response_handler` 节点（在 `config.yaml` 管理，不硬编码）：
- `enabled`（默认 `true`，开关本检查）
- `required_stages`（默认 `["checking_cache", "searching", "filtering", "done", "error"]`，必须覆盖的 stage 列表）
- `require_close_on_done`（默认 `true`，stage=done 时必须 `es.close()`）
- `require_close_on_error`（默认 `true`，stage=error 时必须 `es.close()`）
- `require_cleanup_on_error`（默认 `true`，error 时必须重置状态）
- `require_timeout_fallback`（默认 `true`，必须有超时兜底）
- `default_timeout_ms`（默认 `30000`，超时阈值）

**修复建议**：按 stage 分发处理 + error 时清理 + done 时关闭连接，参考 §2.17

**对应编码规范**：详见 `coding-standards.md` §2.17 性能优化范式

**适用**：所有 `EventSource`/SSE 流式响应处理（搜索/采集/批量任务进度推送）；后端使用 stage 事件协议的实时通信
**不适用**：WebSocket（非 SSE 协议）；一次性 fetch 请求（非流式）；轮询场景（无 stage 事件）；纯 SSR 场景（无客户端 EventSource）

**历史教训**：搜索 SSE 流 stage=error 时未关闭 EventSource 连接，每次搜索失败都泄漏一个连接，长时间运行后浏览器连接数耗尽；且 UI 状态卡在 searching，用户以为还在搜索。修复：按 stage 分发 + error 时清理 + done 时关闭 + 30s 超时兜底

---

## 快速自检

执行 `pwsh .trae/skills/xianyu-frontend-code-review/scripts/auto-scan.ps1` 自动检查以下阻塞项�?
1. `fetch` 请求是否包含 `credentials: 'include'`
2. axios 是否设置 `withCredentials: true`
3. token 是否写入 `localStorage`（应优先 httpOnly cookie�?4. 是否使用 `dangerouslySetInnerHTML`
5. 是否使用 `any` 类型
6. 是否存在�?`.catch()` �?7. 图标按钮是否缺少 `aria-label`
8. `v-for`/`map` 是否使用 index 作为 key
9. 是否使用 `enum`（应用字符串字面量联合）
10. `ConfigProvider` 是否�?`BrowserRouter` 外层
11. 三处映射是否同步（路由、菜单、sheetRegistry�?12. 是否使用 `JSON.parse(JSON.stringify())` 深拷贝（应用 `structuredClone`，S7784�?13. 页面组件是否使用 `minHeight: 100vh`（嵌入场景应�?`height: 100%`�?14. 交互元素文字是否使用 `colorBorder`（应�?`colorPrimary`，确保对比度�?15. 🆕 **S6819/S6844**：是否存�?`<div onClick>` / `<a onClick>` �?href 的可点击元素（应�?`<button>` + 键盘事件�?16. 🆕 **S7503**：是否存在无 `await` �?`async` 函数（应改同步函数）
17. 🆕 **S6767**：函�?组件是否存在未使用的 Props、State、参�?18. 🆕 **S7744**：是否存�?`as unknown as T` 多重断言链（应用类型守卫�?19. 🆕 **S7735**：useEffect 依赖数组是否完整（结�?ESLint react-hooks/exhaustive-deps 提示�?20. 🆕 **S6582**：是否存�?`a?.b` �?a 已确认非空的冗余可选链
21. 🆕 **S1874**：被移除�?API 是否标注 `@deprecated` 而非直接删除
22. 🆕 **S6551**：是否使�?`for...in`（应�?`Object.keys/values/entries`�?23. 🆕 状态管理函数（`activateSheet`、`closeSheet` 等）是否同步更新所有相关字段（`minimized`/`activeId` 等）
24. 🆕 嵌入�?SheetWorkspace/MainLayout 的页面是否用 `height: 100%` 而非 `100vh`
25. 🆕 vitest 测试是否�?`--no-isolate` 参数（Node v24 兼容性）
26. 🆕 antd 组件测试是否 mock `window.matchMedia`（Drawer/Grid/Skeleton�?27. 【强制】EventSource 连接包含 lastEventId 记录（`e.lastEventId`）和重连�?`?last_event_id=` 参数传�?28. 【强制】SSE useEffect 包含 `visibilitychange` 监听器，且在 cleanup �?`removeEventListener`
29. 【强制】SSE error 重连�?`MAX_RECONNECT` 上限，超限后放弃 SSE 退化为轮询
30. 【强制】全局事件监听（`visibilitychange`/`resize`/`scroll`）在 useEffect cleanup 中移�?31. 🆕v4.0 【强制】Tab/Accordion/Collapse 多视图共享数据是�?state 提升至父组件 + `destroyInactiveTabPane={false}`
32. 🆕v4.0 【强制】JSX 内是否存�?IIFE（`{(() => { ... })()}`），应提取为变量
33. 🆕v4.0 【强制】`target="_blank"` 外部链接是否�?`rel="noopener noreferrer"`
34. 🆕v4.0 【强制】图�?文字间距是否用显�?`marginRight`（非 JSX 空格�?35. 🆕v4.0 【强制】注释是否与代码逻辑一致（无误导性顺�?依赖约束说明�?36. 🆕v4.0 【强制】动态资源映射是否映射表+推断函数分离（非混合），业务参数是否通过配置管理
37. 🆕v4.1 【强制】SSE 流消费回调是否显式处�?`stage='error'` 分支（禁止与 `stage='done'`+0 结果混为一谈）
38. 🆕v4.1 【强制】SSE 错误事件是否�?`status` 分类处理�?01/403 显示"前往登录"按钮�?03/504 稍后重试�?02 重启提示�?39. 🆕v4.2 **F-REVIEW-UI-STATE-INDEPENDENCE**（�?）：受控 UI 状态不应通过 useEffect 联动路由
40. 🆕v4.3 `new Proxy()` / `new MutationObserver()` 是否赋值给局部变量后丢弃（应赋值给实例属�?模块级变量）
41. 🆕v4.3 try/finally 块中 finally 引用的变量是否在 try 之前初始化为 null/undefined
42. 🆕v4.3 多个组件对同一概念（会话有效�?登录状态）做判断时，状态变更是否双向同�?43. 🆕v4.3 错误提示中引用的路由路径/API端点是否实际存在（前端路由已注册/后端已实现）
44. 🆕v4.4 **F-REVIEW-CONFIG-DRIVEN-TOGGLE**（�?1）：高风险功能必须配置驱动，默认关闭
45. 🆕v4.5 **F-REVIEW-ERROR-SEMANTICS**（�?1）：错误文案必须与后端根因语义匹�?46. 🆕v4.5 **F-REVIEW-CONFIG-LINKAGE**（�?）：配置项从表单到后端消费全链路可追�?47. 🆕v4.6 **F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND**（�?）：多写入入口统一 updateState
48. 🆕v4.7 **F-REVIEW-FILTER-SCENARIO-FRONTEND**（�?）：按场景显式传�?include_failed 等标�?49. 🆕v4.7 **F-REVIEW-ASYNC-FEEDBACK**（�?0）：异步操作 loading �?success �?error 三态反�?50. 🆕v4.7 **F-REVIEW-DATA-FLOW-TRACE-FRONTEND**（�?1）：字段为空�?5 点逐层追踪
51. 🆕v4.7 **F-REVIEW-REUSE-PATTERN-FRONTEND**（�?8）：新增功能�?grep 复用既有模式
52. 🆕v4.8 **F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE**（�?）：暗色主题 token 动态覆�?53. 🆕v4.9 **F-REVIEW-FREQ-STATS-POLLING**（�?0）：累计统计�?API 前端定时刷新
54. 🆕v4.10 **F-REVIEW-FILTER-VISIBILITY**（�?）：filter_summary 三态提示策�?55. 🆕v4.11 **F-REVIEW-STATE-ENUM-ALIGN**（�?）：前后端状态枚举值严格对�?56. 🆕v4.11 **F-REVIEW-STATE-MACHINE-UI**（�?）：状态机每个状态值有 UI 视觉标识
57. 🆕v4.11 **F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY**（�?）：多链路触发统一 refetch 入口
58. 🆕v4.13 **F-REVIEW-ERROR-CONTRACT-TIMEOUT**（�?）：模块�?statusMessages map + isAxiosTimeout()
59. 🆕v4.13 **F-REVIEW-RETRY-BACKOFF**（�?）：可重试错误按退避序列重�?65. 🆕v4.14 **F-REVIEW-FILTER-BACKEND-ALIGN**（�?）：前端过滤与后端分类逻辑对齐
66. 🆕v4.14 **F-REVIEW-FILTER-PAGINATION-ADAPT**（�?0）：filterStatus 后同步调�?pagination 三参�?67. 🆕v4.14 **F-REVIEW-FILTER-EMPTY-STATE**（�?）：空状态判断用 filteredItems.length
68. 🆕v4.15 **F-REVIEW-DEBUG-CODE-CLEANUP**（�?1）：临时 DEBUG 代码必须移除
69. 🆕v4.16 **F-REVIEW-STATE-FUNCTIONAL-ALIGN**（�?）：UI 状态与功能可用性一�?74. 🆕v4.20 **F-REVIEW-VERSION-SOURCE-ALIGN**（�?）：版本号源语义对齐 API
75. 🆕v4.21 **F-REVIEW-FIELD-NAME-ALIGN**（�?0）：字段名三层一致�?76. 🆕v4.21 **F-REVIEW-CONFIG-PERSIST-VERIFY**（�?0）：配置持久化端到端验证
77. 🆕v4.22 **F-REVIEW-PWA-CACHE-VERIFY**（�?3）：PWA 三层缓存验证
78. 🆕v4.23 **F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION**（�?1）：LLM 模型能力集中展示
79. 🆕v4.24 **F-REVIEW-UI-PREFERENCE-PERSISTENCE**（�?0）：用户偏好�?UI 状态用 usePersistentState
80. 🆕v4.25 **F-REVIEW-THREE-STATE-NULL-SEMANTICS**（�?）：PATCH/PUT 清除覆盖显式�?null
81. 🆕v4.25 **F-REVIEW-ERROR-HANDLING-CONSISTENCY**（�?0）：catch 块用 extractApiError
82. 🆕v4.25 **F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY**（�?）：默认值统一�??? 而非 ||
83. 🆕v4.27 **F-REVIEW-ERROR-CODE-BRANCH**（�?5）：�?error_code 字段分支决策
84. 🆕v4.27 **F-REVIEW-PRECHECK-API-DELEGATION**（�?5）：数据完整性预检委托后端
85. 🆕v4.27 **F-REVIEW-MOCK-FIELD-SET-SYNC**（�?5）：mock 数据覆盖完整字段�?86. 🆕v4.32 **F-REVIEW-MULTI-USER-CONTEXT-ISOLATION**（�?8）：多用户上下文�?user_id 隔离 + 切换时清空缓�?87. 🆕v4.32 **F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING**（�?8）：token �?httpOnly cookie + credentials:include + 401/440/441/403 状态码语义分支
88. 🆕v4.33 **F-REVIEW-EFFECT-MINIMIZE**（�?）：useEffect 禁止重置用户交互控制的状态（openKeys/expandedKeys/activeKey），应用 useState 初始�?89. 🆕v4.33 **F-REVIEW-STATE-ATOMICITY**（�?）：多字段状态切换必须同步更新（封装 transition 方法或单一状态枚举）
90. 🆕v4.33 **F-REVIEW-SSE-CONN-MGMT**（�?5）：SSE 连接管理三要素（visibilitychange 监听 + last_event_id 回放 + 最大重�?10 次降级轮询）
91. 🆕v4.33 **F-REVIEW-ASYNC-RACE-GUARD**（�?0）：异步请求�?useRef 维护最新请�?ID，响应回来时对比丢弃过期响应
92. 🆕v4.33 **F-REVIEW-THEME-DYNAMIC-ADAPT**（�?）：禁止硬编码主题色，必须根�?isDark 动态设置（rowHoverBg/headerBg 等）
93. 🆕v4.33 **F-REVIEW-EMBEDDED-LAYOUT-HEIGHT**（�?）：嵌入式布局�?height:100% + flex:1，禁�?minHeight:100vh
94. 🆕v4.33 **F-REVIEW-COMPONENT-REGISTRY**（�?）：ECharts/antd 组件必须 import + register，避免静默失�?95. 🆕v4.33 **F-REVIEW-FILTER-TRANSPARENCY**（�?）：数据被过滤时展示过滤原因和条数（Modal/Tooltip 展示 filter_summary�?96. 🆕v4.33 **F-REVIEW-DATA-SOURCE-VERIFY**（�?8）：显示数据必须来自正确数据源（系统版本�?/api/about 而非 /api/config/version�?97. 🆕v4.33 **F-REVIEW-STATS-RANGE-CALIBRATE**（�?6）：统计图表范围与业务范围匹配（task_id 过滤 + P5/P95 百分位校准）
98. 🆕v4.33 **F-REVIEW-UI-SEMANTICS-SPLIT**（�?）：按钮文案表达动作（主动失效），状态显示表达状态（已失效），禁止混�?99. 🆕v4.33 **F-REVIEW-PERSIST-BUSINESS-SWITCH**（�?0）：业务开关用 usePersistentState 持久化，禁止 useState 刷新丢失
100. 🆕v4.33 **F-REVIEW-ERROR-MESSAGE-PASS**（�?0）：catch 块用 extractApiError 提取后端具体错误，禁止无信息通用错误
101. 🆕v4.33 **F-REVIEW-API-CONTRACT-CONSISTENCY**（�?1）：TS interface 字段名与后端 response_model 完全一致（snake_case 对齐�?
> **F-REVIEW 检查点详细规则**：以�?50 �?F-REVIEW 检查点的核心机�?/ 判断信号 / 修复模式 / 适用场景 / 不适用场景 / 历史教训详见对应维度章节（�? 维度号）。配置参数在 `config.yaml` 的对应节点管理�?
---

## 审查流程�? 阶段流水线）🆕v4.33

> v4.33 将原 5 阶段闭环（Phase 0-4）优化为 4 阶段流水线，新增 `coding_standards` 节点加载�?`coding-rules/` 主题文件加载，强化优先级分类（P0/P1/P2/P3）与结构化报告呈现�?
### 阶段 1：上下文加载

1. **加载 config.yaml 配置**（含 `coding_standards` 节点，v4.33 新增�?   - 读取 `scope` / `priority` / `hard_constraints` / `checklist` / `coding_standards` 等节�?   - `coding_standards` 节点提供 14 �?F-REVIEW 检查点的阈值参数（effect/sse/theme/layout/registry/filter/ui_semantics/persist/race/error/contract/source 等）
2. **识别任务类型**（前�?后端/全栈�?   - 前端任务：加�?`frontend/src/` 下的 React/TypeScript/Ant Design 文件
   - 后端任务：转�?`xianyu-backend-code-review` 技�?   - 全栈任务：前后端协同审查，识别跨边界契约问题
3. **加载对应 `coding-rules/` 主题文件**（v4.33 新增规范源联动）
   - �?`xianyu-hunter-dev/references/coding-rules/` 加载与本次审查相关的主题文件（如 EFFECT-01/SSE-01/THEME-01 等）
   - 每个 F-REVIEW checkpoint 引用对应规范编号，审查时加载规范详情
4. **确定评审范围**�?   - **待提交变更模�?*：`git diff HEAD` + `git status` 提取改动�?`.tsx/.ts/.js` 文件
   - **指定文件模式**：用户明确指定的文件列表
   - **片段评审模式**：用户粘贴的代码片段（无文件路径时仅输出建议�?5. **应用 `scope.include_paths` / `scope.exclude_paths` 过滤**，截�?`scope.max_files_per_run` 个文�?6. **对每个待评审文件收集上下�?*�?   - 使用 Read 工具读取完整文件内容
   - 使用 Grep 工具查找关键依赖（导入的组件/Hook/工具函数、Ant Design 组件、API 接口�?   - 使用 Grep 查找相关测试文件（`__tests__/*.test.ts(x)`）评估测试覆�?   - 使用 Grep 查找相关类型定义（`types.ts`）评估类型一致�?   - 记录文件的最近修改历史（`git log --oneline -5 -- <file>`�?
**判断逻辑**：范围必须收紧——只评审用户提供的或明确引用的文件，不顺便审查旁边代码�?
### 阶段 2：分层扫�?
�?`checklist` 配置�?28 大类逐层扫描，每个维度引用对�?F-REVIEW checkpoints，对比反模式示例识别问题�?
**优先级排�?*：`severity_order` × `category_order`
- 类型安全（CRITICAL�? 业务逻辑（HIGH�? 性能（MEDIUM�? 规范（LOW�?- 硬约束违规优先级最高，无论 severity 如何

**子阶�?2.1：常规规则匹�?*

�?`checklist` 配置�?28 大类逐项检查（见上�?审查规则"章节），每个维度引用对应 F-REVIEW checkpoints�?
**子阶�?2.2：配置驱动检�?* 🆕v4.31

针对配置驱动�?F-REVIEW 检查点，必须在常规规则匹配后追�?配置驱动检�?子阶段，按以下顺序扫描：

1. **业务关键字硬编码扫描**（对�?F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION�?   - �?Grep 扫描 `frontend/src/**/*.{ts,tsx}` 是否存在 `const \w*_KEYWORDS?\s*=\s*\[` �?`\.includes\(['"](卖掉了|已售|已下�?` 模式
   - 命中后检查是否调�?`/api/config/text_features` 端点拉取后端配置；未调用 �?标记�?配置节点缺失"分类�?CRITICAL 问题
2. **事件类型前缀匹配扫描**（对�?F-REVIEW-EVENT-TYPE-EXACT-MATCH�?   - �?Grep 扫描 `frontend/src/**/*.{ts,tsx}` 是否存在 `\.startsWith\(['"]\w+\.` �?`\.indexOf\(['"]\w+\.\w` 模式
   - 命中后检查是否属于配置节�?`event_type_exact_match.allowed_prefix_grouping_scenarios` 允许的统�?日志场景；不属于 �?标记�?CRITICAL 问题
3. **字段名大小写敏感扫描**（对�?F-REVIEW-FIELD-NAME-CASE-SENSITIVE�?   - �?Grep 扫描 `frontend/src/api/**/*.ts` 是否存在驼峰字段名（后端应为 snake_case），以及 `frontend/src/**/*.{ts,tsx}` 是否存在 `as any` 类型断言绕过
   - 命中后检查前�?`api/types.ts` 字段名是否与后端 Pydantic 模型一一对应；不一�?�?标记�?CRITICAL 问题
4. 🆕v4.32 **多用户上下文隔离扫描**（对�?F-REVIEW-MULTI-USER-CONTEXT-ISOLATION�?   - �?Grep 扫描 `frontend/src/stores/` 是否存在未按 `user_id` 分桶的全局单例 store（如 `create<.*>\(\)\s*=>\s*\(\{\s*orders:` 模式�?   - 命中后检查用户切换路径是否调�?`queryClient.clear()` / `useGlobalStore.getState().reset()`；未调用 �?标记�?CRITICAL 问题（跨用户数据泄漏风险�?5. 🆕v4.32 **认证 token cookie 处理扫描**（对�?F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING�?   - �?Grep 扫描 `frontend/src/api/**/*.ts` �?`fetch(` 调用是否包含 `credentials: 'include'`，`axios.create` 是否包含 `withCredentials: true`
   - �?Grep 扫描 `frontend/src/**/*.{ts,tsx}` 是否存在 `localStorage.(get|set)Item(['"]xh_token` 模式（token 不应�?localStorage�?   - �?Grep 扫描 401 错误处理分支是否区分 401/440/441/403 状态码语义；未区分 �?标记�?CRITICAL 问题（用户频繁被踢出风险�?6. 🆕v4.33 **coding_standards 节点驱动扫描**（对�?F-REVIEW-96~109�?4 项新检查点�?   - �?`coding_standards` 节点配置的阈值参数扫描（effect/sse/theme/layout/registry/filter/ui_semantics/persist/race/error/contract/source�?   - 对比反模式示例识别问题，命中后引用对应规范编号（EFFECT-01/SSE-01/THEME-01 等）

**子阶�?2.3：硬约束合规性检�?*

遍历 `hard_constraints.rules`，对每条规则�?1. 使用 Grep 工具扫描代码库（pattern 字段�?2. 匹配到的违规项记录到报告
3. �?`hard_constraints.block_on_violation=true` 且发�?CRITICAL 违规，在报告中标�?阻止合并"

**判断逻辑**：硬约束违规优先级最高，无论 severity 如何，必须在报告中突出显示。本阶段识别的问题统一归入"配置节点缺失"分类（见 Template A），与常规规则匹配结果合并后进入阶段 3 优先级分类。

**子阶段 2.4：跨层影响范围评估** 🆕v4.60

修改前端 `types.ts` / 字段定义时，自动评估后端 Pydantic / DB 影响：
1. **前端字段变更检测**：Grep 扫描本次变更是否涉及 `frontend/src/api/types.ts` 中的字段定义修改
2. **后端影响映射**：若前端字段变更，对照 `contract_single_source` 配置检查后端 Pydantic 模型对应字段是否同步修改
3. **DB 影响评估**：若后端字段变更涉及 DB 列，标记为 CRITICAL（需数据库迁移）
4. **影响传播图生成**：生成本次变更的跨层传播路径图（types.ts → Pydantic → DB），写入报告的「跨层影响图」部分

**子阶段 2.5：缓存守卫专项检查** 🆕v4.60

所有涉及缓存的代码变更，验证三项守卫：
1. **空结果不缓存**：API 返回空数组/空对象时不应写入缓存，防止脏数据长期驻留
2. **TTL 非硬编码**：缓存过期时间必须从配置获取（如 `config_fallback_defaults` 节点），禁止硬编码魔法数字
3. **守卫独立性**：缓存守卫逻辑（写入前校验/TTL 过期清理/失效重取）应独立于业务逻辑，不与 UI 渲染耦合

**子阶段 2.6：UI变更门控检查** 🆕v4.60

前端视觉变更的预确认检查（对应 F-REVIEW-UI-PREVIEW-GATE）：
1. **变更行数统计**：统计本次变更中 icon/theme/color/layout 相关的替换行数
2. **门控阈值判断**：若变更行数 > `ui_preview_gate.changeLineThreshold`，标记为 WARNING 并要求预览确认
3. **豁免检测**：检查 commit message 是否匹配 `ui_preview_gate.exemptPatterns`（如 Bug修复/文案修正），匹配则跳过门控
4. **回滚清单生成**：门控未通过时，自动生成回滚清单（变更文件列表 + 变更前 git hash）

**子阶段 2.7：重构安全性检查** 🆕v4.61

基于复盘规范集 A/B/D 三类前端版本，审查重构过程的安全性（详见 [references/refactoring-safety-checks.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/refactoring-safety-checks.md)）。**为什么独立成节**：常规代码质量检查关注"代码写得对不对"，重构安全性检查关注"改的过程是否安全"——任何重命名、常量抽取、Hook 改造、构建命令变更都伴随着跨文件契约，必须配套同步验证。所有阈值参数在 `config.yaml#refactoring_safety_checks` 节点管理，不硬编码。

**触发条件**：本次变更为重构类操作（重命名 / 常量迁移 / Hook 改造 / 模块拆分 / 构建脚本变更）时自动触发；纯 Bug 修复或新增功能不触发。

按以下 7 项 F-REVIEW 检查点逐项扫描：

1. **常量配置化 5 步法**（对应 F-REVIEW-220 CONSTANT-CONFIG-DRIVEN）：
   - 检查常量重构是否遵循"grep 全量 → 新增常量 → 源文件改造 → 核对引用 → 文档同步"五步闭环
   - 判断信号：改动常量定义但未执行 grep 全量引用扫描 / 常量已迁移但源文件仍保留旧的内联字面量 / 注释仍引用旧常量名
   - 配置节点：`refactoring_safety_checks.constant_config_driven`

2. **React Hooks 作用域契约**（对应 F-REVIEW-221 REACT-HOOKS-SCOPE-CONTRACT）：
   - 检查 Hook 改造是否破坏组件作用域与模块作用域的边界
   - 判断信号：组件 useState/useRef 被改为模块级 `let` 变量 / Hook 被改为普通函数丢失 `use` 前缀 / 模块级常量被组件修改 / 组件 re-mount 后状态未恢复
   - 配置节点：`refactoring_safety_checks.react_hooks_scope_contract`

3. **导入名称变更 checklist**（对应 F-REVIEW-222 IMPORT-NAME-CHANGE-CHECKLIST）：
   - 检查重命名导出符号时是否按调用类型分类核对（Hook 调用保留 `()`、组件调用改为 JSX、函数调用加 `()`）
   - 判断信号：删除导出名前未 grep / Hook 改名为普通函数后调用方未加 `()` / 函数改名为组件后调用方未改为 JSX
   - 配置节点：`refactoring_safety_checks.import_name_change_checklist`

4. **长任务前端构建日志输出**（对应 F-REVIEW-223 LONG-TASK-BUILD-LOG-REDIRECT）：
   - 检查构建脚本是否使用 PowerShell sink cmdlet（如 `| Select-Object -Last N`）导致缓冲
   - 判断信号：脚本含 `| Select-Object` / `| Out-Host -Paging` / `| more` / 长任务未设置超时
   - 配置节点：`refactoring_safety_checks.long_task_build_log_redirect`

5. **系统资源过载容错**（对应 F-REVIEW-224 SYSTEM-RESOURCE-OVERLOAD-TOLERANCE）：
   - 检查全量 tsc 检查是否提供单文件 fallback / 是否监控 Node 进程内存
   - 判断信号：`tsc --noEmit` 超过 `system_resource_overload_tolerance.long_task_threshold_seconds` 仍无输出 / Node 内存超过 `node_memory_threshold_mb` / 无 fallback 策略
   - 配置节点：`refactoring_safety_checks.system_resource_overload_tolerance`

6. **跨文件引用同步校验**（对应 F-REVIEW-225 CROSS-FILE-CONTRACT-SYNC）：
   - 检查修改导出符号后是否运行 `tsc --noEmit` 验证（catch ImportError / NameError）
   - 判断信号：修改导出符号前未 grep / 重构后未运行 tsc / 未检查动态 `import()` 引用 / 修改函数签名但未同步调用方
   - 配置节点：`refactoring_safety_checks.cross_file_contract_sync`

7. **状态持久化统一入口**（对应 F-REVIEW-226 STATE-PERSISTENCE-UNIFIED-ENTRY）：
   - 检查业务参数（轮询间隔 / timeout / 阈值）是否从 config 读取 / localStorage key 是否有命名空间 / 状态读取是否有类型守卫
   - 判断信号：`setInterval(refresh, 10000)` 硬编码 / `localStorage.setItem('columns', ...)` 无命名空间 / `JSON.parse` 无类型守卫
   - 配置节点：`refactoring_safety_checks.state_persistence_unified_entry`

**判断逻辑**：本阶段识别的问题统一归入"重构安全性"分类，CRITICAL 问题（如 F-REVIEW-225 跨文件契约失败）必须阻塞合并。详细判定标准、反模式示例、修复模式见 [references/refactoring-safety-checks.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/refactoring-safety-checks.md)。

### 阶段 3：优先级分类 🆕v4.33

将阶�?2 识别的所有问题按 P0/P1/P2/P3 四级分类，决定修复优先级与是否阻塞合并�?
| 优先�?| 含义 | 阻塞合并 | 示例 |
|--------|------|----------|------|
| **P0 阻塞�?* | 安全漏洞/数据丢失/崩溃/认证绕过 | �?�?| token �?localStorage（F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING）、SSE 无限重连（F-REVIEW-SSE-CONN-MGMT�?|
| **P1 严重** | 逻辑错误/性能问题/数据不一�?| �?否（强烈建议修复�?| useEffect 重置用户状态（F-REVIEW-EFFECT-MINIMIZE）、异步竞态（F-REVIEW-ASYNC-RACE-GUARD）、API 契约不一致（F-REVIEW-API-CONTRACT-CONSISTENCY�?|
| **P2 改进** | 代码质量/可维护�?规范偏离 | �?�?| 主题色硬编码（F-REVIEW-THEME-DYNAMIC-ADAPT）、统计范围过大（F-REVIEW-STATS-RANGE-CALIBRATE）、错误消息无透传（F-REVIEW-ERROR-MESSAGE-PASS�?|
| **P3 微调** | 风格/注释/命名 | �?�?| 按钮与状态语义混用（F-REVIEW-UI-SEMANTICS-SPLIT）、组件注册集中性（F-REVIEW-COMPONENT-REGISTRY�?|

**判断逻辑**�?- P0 问题必须修复后才能合并，报告中标�?阻止合并"
- P1 问题强烈建议在本次迭代修复，报告中突出显�?- P2/P3 问题记录�?backlog，可在后续迭代修�?- 优先级映射到原有 severity：P0=CRITICAL、P1=HIGH、P2=MEDIUM、P3=LOW

### 阶段 4：结果呈�?
�?`report.format` 生成结构化报告（Markdown），严格遵循**输出模板**（见 `templates/report-template.md` 与下�?结构化报告模�?）�?
**报告结构**�?1. **审查概览**（审查范�?审查维度/问题统计 P0/P1/P2/P3/规范版本�?2. **问题详情**（按 P0→P3 优先级排序，每个问题含编�?维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示例）
3. **与上次审查对�?*（🆕新�?/ ✅已修复 / ⚠️仍存在）
4. **硬约束合规性检查结�?*
5. **好的实践**（正面反馈）
6. **测试运行结果**（若 `verify.run_tests_after_review=true`�?7. **审查结论与修复验证指�?*

**结构化报告模�?*（v4.33 新增，每个问题按以下格式呈现）：

```markdown
#### [P0] F-REVIEW-96 useEffect 副作用最小化
- **规范引用**: EFFECT-01 useEffect 副作用最小化原则
- **维度**: §3 React 组件规范
- **代码位置**: MainLayout.tsx:358-362
- **问题描述**: useEffect 联动重置 openKeys，触�?SubMenu 动画遮挡
- **修复建议**: 完全移除 useEffect，openKeys �?useState 初始�?+ 用户交互控制
- **配置节点**: coding_standards.effect.disallow_reset_user_controlled_state
- **反模式示�?*: useEffect(() => setOpenKeys(autoOpenKeys), [location.pathname])
```

**结果呈现优化** 🆕v4.60：

1. **按风险等级分组**：问题详情按风险等级分组呈现，优先级排序为：
   - CRITICAL（安全/数据丢失）> WARNING（缓存/状态）> INFO（风格/优化）
   - 每个风险等级对应不同的视觉标识：🔴 CRITICAL / 🟡 WARNING / 🔵 INFO

2. **防回归标记**：每个修复点标记对应的测试模式（xianyu-auto-testing 模式），确保修复可被自动测试覆盖：
   ```markdown
   - **防回归标记**: auto-testing 模式 V（UI一致性回归）/ 模式 W（状态持久化回归）/ 模式 X（渲染健壮性回归）
   ```

3. **跨层影响图**：显示变更的跨层传播路径，帮助审查者理解修改的完整影响范围：
   ```markdown
   ### 跨层影响图
   ```
   types.ts:Item.price_range ──→ Pydantic:ItemResponse.price_range ──→ DB:items.price_range
   types.ts:Item.market_ratio ──→ Pydantic:ItemResponse.market_ratio ──→ DB:items.market_ratio
   ```
   影响路径数：2  最大深度：3  涉及DB列：2
   ```

---

## 评审范围判断

- **待提交变更模�?*：`git diff HEAD --name-only` + 过滤 `.tsx/.ts/.js` 文件
- **指定文件模式**：用户明确列出文件路�?- **片段模式**：用户粘贴代码但无文件路径（仅输出建议，不输�?File:Line�?- **范围必须收紧**：不顺便审查旁边代码，不主动扩展到未提及的文�?
## 误报识别判断

- 路径匹配 `scope.exclude_paths`：跳�?- 测试文件中的规范类问题：降级处理
- 生成代码（含 `// @generated` 注释�?`__generated__` 路径）：跳过
- 第三方库代码（`node_modules`）：跳过
- 类型定义文件（`.d.ts`）中的规范类问题：降级处�?
## 修复建议判断

- 必须提供可操作的修复建议（含代码示例�?- 建议必须解释"为什�?而非�?做什�?
- 优先建议抽取纯函数、共享常量、共享组�?- 若问题需要代码修改，在报告末尾询问用户是否应用修�?
## 抽象建议判断（闲鱼项目特色）

- 重复的内联样式（`abstraction_thresholds.inline_style_repeat` 默认 3 处）：建议抽取共享组件或样式常量
- 重复的文案（`abstraction_thresholds.text_literal_repeat` 默认 2 处）：建议抽取共享文案常�?- 复杂的优先级/判定逻辑：建议抽取为纯函数并配套单元测试
- 跨组件共享的状态逻辑：建议抽取为自定�?Hook
- 函数行数超过 `function_max_lines`（默�?50）：建议拆分
- 组件行数超过 `component_max_lines`（默�?300）：建议拆分
- 嵌套深度超过 `max_nesting_depth`（默�?4）：建议重构（SonarQube S2004�?
## 失败恢复机制

1. **文件读取失败**：记录跳过原因，继续评审其他文件
2. **Grep 超时**：缩小搜索范围或跳过该检查项
3. **测试运行失败**：输出测试失败信息，不阻止报告生�?4. **配置文件缺失**：使用内置默认配置并提示用户创建 `config.yaml`
5. **TypeScript 编译错误**：记录但继续评审，不阻止报告生成

---

## 审查判断标准

| 🟠阻塞(必须修复) | 🟠严重(强烈建议) | 🟡警告(建议) |
|-----------------|-----------------|-------------|
| `fetch` 请求未包�?`credentials: 'include'` | 未复用组�?| 缩进不规�?|
| axios 未设 `withCredentials: true` | UI 不一�?| 变量命名不规�?|
| token 写入 `localStorage` | 缺注�?| 冗余代码 |
| 使用 `dangerouslySetInnerHTML` | 验证规则不完�?| 注释不清�?|
| 使用 `any` 类型 | 错误处理不完�?| 缺少类型注解 |
| �?`.catch()` �?| 空指针风险（链式调用未判空） | 缺少测试 |
| `v-for`/`map` 使用 index 作为 key | `useEffect` 依赖数组不完�?| 缺少文档字符�?|
| `ConfigProvider` �?`BrowserRouter` 内层 | `useMemo`/`useCallback` 缺失 | 嵌套层级过深 |
| 三处映射不同步（路由/菜单/sheetRegistry�?| `requestId` 竞态保护缺�?| 注释复述代码 |
| `enum` 替代字符串字面量联合 | `mountedRef` 缺失（卸载后 setState�?| 魔法数字未提�?|
| `JSON.parse(JSON.stringify())` 深拷�?| `refreshingRef` 并发保护缺失 | 魔法字符�?|
| 使用 `interface`（应�?`type`�?| `lazyRetry` 未包�?| 函数过长 |
| `main.tsx` 入口配置错误 | `SSE_LAST_EVENT_ID_KEY` 缺失 | 缺少 `__all__` |
| 函数嵌套 > 4 层（S2004�?| PWA `runtimeCaching` 未排�?`/api/events/stream` | - |
| 认知复杂�?> 15（S3776�?| 路由切换未重置滚动位�?| - |
| `vite.config.ts` `base` 错误 | `partialize` 未过�?ReactNode | - |
| 构建产物未输出到 `web/static/spa` | store 感知路由库（未用 `_navigator` 注入�?| - |
| 使用箭头函数定义组件 | `useEffect` 依赖数组缺失导致 stale closure | - |
| 嵌入页面�?`minHeight: 100vh`（应 `height: 100%`�?| `activateSheet` 未同步恢�?`minimized` | - |
| 交互元素文字�?`colorBorder`（应 `colorPrimary`�?| antd 组件测试�?mock `matchMedia` | - |
| 状态变更操作未同步更新所有相关字�?| vitest 命令缺少 `--no-isolate` | - |
| 🆕 `<div onClick>`/`<a onClick>` �?href（S6819/S6844�?| 🆕 `useEffect` 依赖缺失导致 stale closure（S7735�?| - |
| 🆕 �?`await` �?`async` 函数（S7503�?| 🆕 冗余可选链 `a?.b` �?a 已非空（S6582�?| - |
| 🆕 未使用的 Props/State/参数（S6767�?| 🆕 重复内联样式 `abstraction_thresholds.inline_style_repeat` 次以�?| - |
| 🆕v4.0 Tab 切换数据丢失（state 未提升） | 🆕v4.0 JSX �?IIFE 未提取为变量 | - |
| 🆕v4.0 外部链接�?`rel="noopener noreferrer"` | 🆕v4.0 图标文字间距依赖 JSX 空格 | - |
| 🆕v4.0 注释与代码逻辑不一致（误导性约束说明） | 🆕v4.0 动态资源映射表与推断函数混�?| - |
| 🆕v4.1 SSE 流消费回调未处理 `stage='error'` 分支 | 🆕v4.1 SSE 错误事件未按 `status` 分类�?01/403 应显�?前往登录"按钮�?| - |
| 🆕v4.1 SSE 错误事件�?真的没货"（`stage='done'`+0 结果）混为一�?| - | - |
| 🆕v4.2 受控 UI 状态（`openKeys`/`expandedKeys`）通过 `useEffect` 联动路由变化（产生非用户触发的展开/折叠动画�?| - | - |
| 🆕v4.3 Proxy/Observer 赋值给局部变量后丢弃（死代码�?| 🆕v4.3 跨组件对同一概念判断维度未同�?| - |
| 🆕v4.3 try/finally 变量未初始化�?null/undefined | 🆕v4.3 错误提示引用不存在的路由/端点 | - |
| 🆕v4.4 高风险前端功能默认启用（应默认关�?配置驱动）（F-REVIEW-CONFIG-DRIVEN-TOGGLE�?| 🆕v4.4 功能参数硬编码在组件内（应集中在 `constants.ts` �?`FEATURE_TOGGLES`/`FEATURE_CONFIGS` 节点管理�?| - |
| 🆕v4.5 错误提示文案与后端错误根因语义不匹配（如 token 过期显示"登录已过�?）（F-REVIEW-ERROR-SEMANTICS�?| 🆕v4.5 前端配置项未传递给后端 API（配置无效化）（F-REVIEW-CONFIG-LINKAGE�?| - |
| 🆕v4.9 累计统计�?API（频率伪装统�?/ 健康评分 / 计数器）仅在 useEffect 初始化时拉一次，缺少 setInterval 定时刷新（F-REVIEW-FREQ-STATS-POLLING�?| 🆕v4.9 setInterval 间隔数字�?0000/30000）硬编码在组件内（应来自 `config.yaml` �?`freq_stats_polling.interval_ms` �?`POLL_INTERVALS` 常量�?| - |
| 🆕v4.10 后端返回 `filter_summary` 但前端只显示"查询完成"不暴露过滤过程（F-REVIEW-FILTER-VISIBILITY�?| 🆕v4.10 API 返回类型�?`as { filter_summary?: ... }` 强制转换绕过 TS 检查（应显式声�?`filter_summary?` 字段�?| - |
| 🆕v4.11 前后端状态枚举值不对齐（前�?`types.ts` 联合类型与后�?`Enum` 不一致）（F-REVIEW-STATE-ENUM-ALIGN�?| 🆕v4.11 前端硬编码状态字符串（`status === 'running'`）而非引用 `types.ts` 联合类型 | - |
| 🆕v4.11 终态（`completed`/`failed`）仍显示 loading 动画�?进行�?文案（F-REVIEW-STATE-MACHINE-UI�?| 🆕v4.11 中间态（`pending`/`running`）缺�?loading 反馈 / 操作按钮与后端状态机白名单不一�?| - |
| 🆕v4.11 多链路触发同一状态变更时各链路独�?`setState` 推断新状态（F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY�?| 🆕v4.11 SSE 推送状态变更后只更新当前组�?`setState` 未刷新全局缓存 / `refetch()` 失败清空缓存 | - |
---

## 与现有工具的关系

- **xianyu-hunter-dev**：开发技能，本技能与之配合（开发完成后用本技能审查）
- **frontend-code-review**（全局技能）：本技能参考其检查清单精神，但增加了闲鱼项目专属的硬约束�?19 维度检查清�?- **xianyu-backend-code-review**：前后端协同评审时配合使�?- **xianyu-sonarqube-mcp**：SonarQube 修复后的二次人工评审使用本技�?- **frontend-design**：UI 设计与样式调整使用该技能，不使用本技�?- **systematic-debugging**：纯调试场景使用该技能，不使用本技�?- **skill-creator**：本技能由 skill-creator 创建

---

## 安全注意事项

1. **凭据**：报告中不包含任�?token、密码等敏感信息
2. **XSS 风险**：检�?`dangerouslySetInnerHTML` 的使�?3. **敏感信息存储**：检�?token 是否避免写入 localStorage（优�?httpOnly cookie�?4. **认证一致�?*：检查所�?API 请求是否携带 credentials

---

## 示例用法

### 场景1：迭代发布前评审

用户�?对这次迭代的前端修改进行代码评审"

技能执行：
1. 读取 `config.yaml`
2. `git diff HEAD --name-only` 提取改动�?`.tsx/.ts/.js` 文件
3. 逐文件读取并�?23 大类检�?4. 硬约束合规性扫�?5. 生成评审报告

### 场景2：指定组件评�?
用户�?评审 frontend/src/pages/Evaluations/index.tsx"

技能执行：
1. 读取 `config.yaml`
2. 读取指定文件
3. 收集上下文（类型定义、测试文件、API 契约�?4. 按检查清单评�?5. 生成评审报告

### 场景3：仅评审类型安全和业务逻辑

用户修改 `config.yaml`�?```yaml
checklist:
  directory_structure: false
  naming: false
  react_component: false
  typescript_strict: false
  antd_theme: false
  zustand: false
  api_call: false
  routing_lazy: false
  sheet_workspace: false
  hooks_design: false
  type_safety: true
  sonarqube: false
  pwa: false
  three_mappings: false
  sse_reconnect: false
  business_logic: true
  performance: false
  accessibility: false
  testability: true
  auth: false
  project_specific: false
```

技能执行：只检查类型安全、业务逻辑和可测试性�?
### 场景4：评审新增的纯函数抽�?
用户�?评审我新抽取�?`resolveActionDisplay` 函数"

技能执行：
1. 读取函数定义文件（`utils.ts`�?2. 读取对应测试文件（`__tests__/resolveActionDisplay.test.ts`�?3. 重点检查：
   - 类型安全（返回值联合类型、参数类型）
   - 业务逻辑（优先级顺序、边界场景）
   - 可测试性（纯函数、测试覆盖度�?   - 注释质量（是否解�?为什�?�?4. 生成评审报告

---

## 结构化报告模�?🆕v4.33

> v4.33 新增结构化报告模板，强化"审查概览 + 问题详情"两段式呈现，每个问题含编�?维度/规范引用/代码位置/问题描述/修复建议/配置节点/反模式示�?8 要素。与下方 Template A/B 并存，按 `report.format` 选择�?
### 完整报告结构

```markdown
# 代码审查报告

## 审查概览
- **审查范围**: [文件列表，如 MainLayout.tsx / SheetWorkspace.tsx / api/types.ts]
- **审查维度**: [命中的维度列表，�?§3 React 组件规范 / §10 Hooks 设计模式 / §15 SSE 重连]
- **问题统计**: P0=[n] P1=[n] P2=[n] P3=[n]（总计 [n] 项）
- **规范版本**: xianyu-frontend-code-review v4.33.0
- **配置版本**: config.yaml（含 coding_standards 节点�?- **审查日期**: [YYYY-MM-DD]

## 问题详情

### 🔴 P0 阻塞性问题（必须修复后才能合并）

#### [P0] F-REVIEW-SSE-CONN-MGMT SSE 连接管理三要�?- **规范引用**: SSE-01 SSE 连接管理三要�?- **维度**: §15 SSE 重连
- **代码位置**: EventSourceProvider.tsx:45-62
- **问题描述**: SSE 连接无限重连，无最大重试限制，�?visibilitychange 监听，页面切回后事件丢失
- **修复建议**: 增加 MAX_RECONNECT=10 限制 + visibilitychange 监听 + last_event_id 回放 + 降级轮询
- **配置节点**: coding_standards.sse.max_reconnect_attempts / coding_standards.sse.visibility_reconnect
- **反模式示�?*:
  ```typescript
  es.addEventListener('error', () => {
    setTimeout(connect, 3000)  // 无限重连，无降级
  })
  ```

#### [P0] F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING 认证 token cookie 处理
- **规范引用**: AUTH-COOKIE-01（与 v4.32 F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING 配合�?- **维度**: §28 多用户认证上下文隔离
- **代码位置**: api/auth.ts:23
- **问题描述**: token 存入 localStorage，XSS 可读�?- **修复建议**: 改为 httpOnly cookie 由后端写入，fetch 显式 credentials: 'include'
- **配置节点**: auth_token_cookie_handling.forbidden_token_storage
- **反模式示�?*: `localStorage.setItem('xh_token', token)`

### 🟠 P1 严重问题（强烈建议本次迭代修复）

#### [P1] F-REVIEW-EFFECT-MINIMIZE useEffect 副作用最小化
- **规范引用**: EFFECT-01 useEffect 副作用最小化原则
- **维度**: §3 React 组件规范
- **代码位置**: MainLayout.tsx:358-362
- **问题描述**: useEffect 联动重置 openKeys，触�?SubMenu 动画遮挡
- **修复建议**: 完全移除 useEffect，openKeys �?useState 初始�?+ 用户交互控制
- **配置节点**: coding_standards.effect.disallow_reset_user_controlled_state
- **反模式示�?*: `useEffect(() => setOpenKeys(autoOpenKeys), [location.pathname])`

#### [P1] F-REVIEW-API-CONTRACT-CONSISTENCY API 契约一致�?- **规范引用**: CONTRACT-01 API 契约一致性（前端�?- **维度**: §11 类型安全评审
- **代码位置**: api/types.ts:128
- **问题描述**: 后端返回 total，前�?TS interface 期望 total_for_type，导致显�?0 �?- **修复建议**: TS interface 字段名与后端 response_model 完全一致（snake_case 对齐�?- **配置节点**: coding_standards.contract.check_ts_interface_match
- **反模式示�?*: `interface EvaluationResult { total_for_type: number }`

### 🟡 P2 改进问题（记录到 backlog，后续迭代修复）

#### [P2] F-REVIEW-THEME-DYNAMIC-ADAPT 主题色动态适配
- **规范引用**: THEME-01 主题色动态适配
- **维度**: §5 AntD 5 主题规范
- **代码位置**: theme.ts:34
- **问题描述**: 硬编�?rowHoverBg: '#fff7f0'，暗色模式不可读
- **修复建议**: 改为 isDark ? 'rgba(255,98,0,0.08)' : '#fff7f0'
- **配置节点**: coding_standards.theme.disallow_hardcoded_colors / coding_standards.theme.colors.light/dark
- **反模式示�?*: `rowHoverBg: '#fff7f0'`

### 🟢 P3 微调问题（风�?注释/命名�?
#### [P3] F-REVIEW-UI-SEMANTICS-SPLIT 按钮与状态语义分�?- **规范引用**: UI-SEMANTICS-01 按钮与状态语义分�?- **维度**: §3 React 组件规范
- **代码位置**: CookieList.tsx:156
- **问题描述**: 红色"失效"是按钮而非状态显示，用户误判
- **修复建议**: 按钮文案改为"主动失效"，状态用 Tag 显示"已失�?
- **配置节点**: coding_standards.ui_semantics.button_text_must_be_action
- **反模式示�?*: `<Button danger>失效</Button>`

### ⚙️ Config Node Missing（v4.31+ 独立分类�?
> Phase 2「配置驱动检查」识别的 3 类问题：业务关键字硬编码 / 事件类型前缀匹配 / 字段名大小写不一致。severity 默认 CRITICAL，可�?`config.yaml` �?`enabled` 字段开关�?*必须独立呈现**，不�?Critical/Suggestions/Nits 混合，便于用户快速定�?配置契约"类问题�?
#### [CRITICAL] F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION 业务关键字未集中管理
- **代码位置**: xxx.tsx:NN
- **问题描述**: [违反�?F-REVIEW 规则 + 缺失�?config 节点 + 前后端契约缺口]
- **修复建议**: [新增 config 节点 + 同步前端类型 + grep 双向验证]
- **配置节点**: business_keyword_centralization

## 与上次审查对�?- 🆕 新增: [n] �?- �?已修�? [n] �?- ⚠️ 仍存�? [n] �?
## 硬约束合规性检查结�?- 检查规则数: [n]
- 违规�? [n]
- 是否阻止合并: [�?否]

## 好的实践（正面反馈）
1. [正面反馈 1]
2. [正面反馈 2]

## 审查结论与修复验证指�?- **结论**: [通过 / 有条件通过 / 阻止合并]
- **修复优先�?*: P0 修复后重新审查，P1 建议本次迭代修复
- **验证方式**: 修复后运�?`npm --prefix frontend test ; npm --prefix frontend run typecheck`
```

**输出规则**�?- 若某分类无问题，省略该分类的整个 section
- 若问题数超过 10 个，概括�?"Found 10+ critical issues/suggestions/optional nits" 并仅输出�?10 �?- 不要压缩 section 之间的空行，保持可读�?- 「Config Node Missing」分类必须独立呈现，不与 Critical/Suggestions/Nits 混合
- 若有任何问题需要代码修改，在结构化输出后追加简短询问，例如�?是否需要我使用 Suggested Fix 来修复这些问题？"
- 无问题时输出简短结论：`## Code Review Summary\n�?No issues found.`

> 完整报告模板（含基本信息、severity/category 分布、四维度复盘、跨边界访问契约、配置变更点等扩展段落）�?[templates/report-template.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/templates/report-template.md)�?
---

## 重要提醒

1. 【强制】所�?`fetch`/axios 请求必须包含 `credentials: 'include'` / `withCredentials: true`
2. 【强制】`ConfigProvider` 必须�?`BrowserRouter` 外层，响�?`useTheme`
3. 【强制】新增页面必须同步三处映射（路由、菜单、sheetRegistry�?4. 【强制】禁�?`any` 类型、`dangerouslySetInnerHTML`、`enum`、`JSON.parse(JSON.stringify())`
5. 【强制】SSE 请求�?`fetch + ReadableStream`，lastEventId 持久化重�?6. 【强制】提交前执行 `auto-scan.ps1`；完成后调用本技能走�?
---

## 快速问题定�?
> 现象导向的问题定位对照表（现�?�?原因 �?方案�?0+ 项）已外部化�?[references/quick-troubleshooting.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/quick-troubleshooting.md)。当用户报告具体现象时，先查该表快速定位原因，再回到对应维度章节查阅详细规则�?
---

## 附录A：硬约束来源

本技能的硬约束规则来源于�?- `c:\Users\hspcadmin\.trae-cn\memory\projects\-d-code-otherProjects-17-xianyu\project_memory.md`
- `.trae/skills/xianyu-hunter-dev/references/project-rules.md`
- `.trae/skills/xianyu-hunter-dev/assets/guides/frontend-guide.md`
- `.trae/skills/xianyu-frontend-code-review/references/encoding-and-io.md` —�?字符编码�?I/O 边界审查要点（FAQ 乱码复盘提炼，ENC-01 ~ ENC-08�?- `.trae/skills/xianyu-frontend-code-review/references/state-and-consistency-checks.md` —�?前端硬编码阈值禁用、状态判断后端一致性、类型对齐、API 字段映射、credentials 传递、错误反馈与重试、事件冒泡控制（代码审查 P1 + 实时搜索复盘提炼�?0 �?F-REVIEW 检查点�?- 历史代码评审记录

## 附录B：项目专属规�?
以下规范�?`config.yaml` �?`project_conventions` 节点维护�?
| 规范 | 说明 |
|------|------|
| `ui_library` | UI 组件库（Ant Design�?|
| `visual_style` | 视觉风格偏好 |
| `auth_requirements` | 认证要求 |
| `test_framework` | 测试框架 |
| `types_location` | 类型定义位置 |
| `abstraction_patterns` | 推荐的抽象模�?|
| `routing` | 路由配置 |
| `pwa` | PWA 配置 |
| `sonarqube_rules` | SonarQube 8 条规�?|

## 附录C�?4 维度对照�?
| # | 维度 | 核心规则 |
|:--|:---|:---|
| 1 | 目录结构 | `frontend/src/<分类>/` 规范路径 |
| 2 | 命名规范 | PascalCase/camelCase/use<X>/<�?Store |
| 3 | React 组件规范 | function 关键�?+ type Props + 双层 ErrorBoundary + 🆕v4.2 F-REVIEW-UI-STATE-INDEPENDENCE（受�?UI 状态不联动路由�?|
| 4 | TypeScript 严格规范 | strict:true、type 优先、字符串字面量联合、🆕v4.25 F-REVIEW-DEFAULT-OPERATOR-CONSISTENCY（默认值统一�??? 而非 \|\|�?|
| 5 | AntD 5 主题 | ConfigProvider �?BrowserRouter 外层、品牌橙 |
| 6 | Zustand 状态管�?| persist + partialize、store 不感知路�?|
| 7 | API 调用规范 | axios + withCredentials、SSE �?fetch、🆕v4.25 F-REVIEW-THREE-STATE-NULL-SEMANTICS（PATCH/PUT 清除覆盖必须显式�?null�?|
| 8 | 路由与懒加载 | lazyRetry、双�?ErrorBoundary |
| 9 | SheetWorkspace 多页�?| 6 文件组织、四分支决策 |
| 10 | Hooks 设计模式 | 常量模块级、ref 持有最新闭包、requestId 竞态保护、🆕v4.24 F-REVIEW-UI-PREFERENCE-PERSISTENCE（用户偏好类 UI 状态强制复�?usePersistentState�?|
| 11 | 类型安全 | 前后端字段对齐、可选链、联合类型、🆕v4.4 配置驱动功能开关（F-REVIEW-CONFIG-DRIVEN-TOGGLE�?|
| 12 | SonarQube 合规 | 8 条规则：S2004/S3358/S6757/S7784/S6848/S1128/S4325/S3776 |
| 13 | PWA 配置 | base:'/xianyu/'、runtimeCaching 排除规则 |
| 14 | 三处映射同步 | App.tsx + MainLayout.tsx + sheetRegistry.tsx |
| 15 | SSE 重连 | lastEventId 持久化重连、🆕v4.1 F-REVIEW-SSE-ERROR-HANDLING（stage='error' �?status 分类处理 + "前往登录"跳转引导�?|
| 16 | 性能 | useMemo/useCallback、虚拟化、稳�?key |
| 17 | 可访问�?| aria-label、label 关联、键盘导�?|
| 18 | 闲鱼项目规范 | AntD 5.21、Vitest 4.1、纯函数+组件+常量分层 |
| 19 | 跨组件状态同步与死代码检�?| Proxy/Observer 赋值实例属性、try/finally 变量初始化、跨组件状态双向同步、错误提示路由可操作�?|
| 20 | 错误提示语义 + 配置链路（前端侧�?| 🆕v4.5 错误文案与根因匹配、前端配置全链路追踪、🆕v4.25 F-REVIEW-ERROR-HANDLING-CONSISTENCY（catch 块必须用 extractApiError�?|
| 21 | 异步反馈 + 数据流转 + 过滤场景 + 复用模式（前端侧�?| 🆕v4.7 异步操作三态反馈（loading→success→error）、字段为�?5 点追踪（前端 types+render）、过滤场景标志显式传递（include_failed）、复用既有前端模式（message.loading/lazyRetry/structuredClone�?|
| 22 | 累计统计�?API 定时刷新（前端侧�?| 🆕v4.9 累计统计�?API（频率伪装统�?/ 健康评分 / 计数器）必须在前�?useEffect 中通过 setInterval 定时刷新，禁止只依赖"页面加载时拉一�?；间隔、清理策略、失败兜底均�?`config.yaml` �?`freq_stats_polling` 节点管理，不硬编码（与后�?v4.8.0 `B-REVIEW-ISLAND-MODULE` 配合�?|
| 23 | 前后端错误码契约与超时识�?+ 前端可重试错误集与退避策�?| 🆕v4.13 模块�?`statusMessages` map + `isAxiosTimeout()` 函数（axios 超时�?`response.status` �?`error.code === 'ECONNABORTED'` �?`/timeout/i.test(error.message)` 识别）；可重试错误集�?10/441/502/超时）按 `retry_delays_ms` 退避序列重试，重试过程 `silent_on_retry`；非幂等写入接口禁用自动重试；参数在 `frontend_error_contract` + `frontend_retry_strategy` 节点管理（与后端 v4.12 `B-REVIEW-DOM-FALLBACK-CHAIN` / `B-REVIEW-TIMING-INSTRUMENTATION` / `B-REVIEW-PRECHECK-AND-PARALLEL` 联动�?|
| 24 | 模型能力元数据集中展示与降级状态可视化 | 🆕v4.23 前端展示 LLM 模型能力时必须集中展示（�?`/api/config` �?`/api/about` 统一获取，禁止每页独�?fetch/内联判断），用户上传图片/启用 tool 时前端必须根据能力位给出降级状态可视化（如 `Tag color="warning"` 显示"纯文本模型不支持图片分析，已降级为文字描�?），关键字列表仅在后�?`api_ai._VISION_CAPABLE_KEYWORDS` 一处维护，前端�?`isVisionCapable()` + `getCapabilityDisplay()` 共享函数�?`frontend/src/utils/modelCapability.ts`；参数在 `model_capability_centralization` 节点管理 |
| 25 | 端到端失败原因链前端侧同步原�?| 🆕v4.27 前端在端到端失败原因链中�?3 项同步原则：F-REVIEW-ERROR-CODE-BRANCH（错误展示按 `error_code` 字段分支，禁止按文案子串判断，与后端 `failure_reason_propagation.reason_enum` 一一对应）、F-REVIEW-PRECHECK-API-DELEGATION（数据完整性预检委托后端，禁止前端自行实现预检业务规则，调用后端预检端点 `/api/<resource>/precheck` 获取 `passed` 字段）、F-REVIEW-MOCK-FIELD-SET-SYNC（前�?mock 数据必须覆盖完整字段集与后端 Pydantic 模型一致，禁止�?`as` 类型断言绕过，集中管�?mock 基线文件 `frontend/src/test/mocks/`）；参数�?`failure_reason_chain_frontend` 节点管理（与后端 v4.27.0 维度 29 �?6 �?B-REVIEW 联动�?|
| 26 | 跨边界访问契约前端侧 | 🆕v4.30 后端跨边界契约不明确在前端的对应场景：F-REVIEW-DATETIME-RENDER-CONTRACT（后�?datetime 字段 must use `new Date(isoStr)` 显式解析，naive ISO 字符串追�?`Z` 后缀，禁止字符串方法解析）、F-REVIEW-PRIVATE-HOOK-ENCAPSULATION（跨组件访问私有 hooks/state 必须通过公共 API，禁�?`useXxxStore(s => s._xxx)` 直接访问私有字段，用 `useImperativeHandle` 显式声明可暴露方法）、F-REVIEW-NAMING-CONSISTENCY-FRONTEND（命名一致性验证：变量 camelCase / 组件 PascalCase / 常量 UPPER_SNAKE_CASE / 私有 _ 前缀，跨组件引用必须大小写匹配）；参数在 `cross_boundary_contract_frontend` 节点管理 |
| 27 | 业务关键字常量集中管理与字段名大小写敏感 | 🆕v4.31 前端业务关键字与字段契约层面�?3 项同步原则：F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION（前端业务关键字常量必须从后端配置端�?`/api/config/text_features` 拉取，禁止前端硬编码中文字面量，通过共享 helper `isItemSoldByText()` 调用后端配置）、F-REVIEW-EVENT-TYPE-EXACT-MATCH（前端按事件类型过滤必须 `===` 精确匹配�?`Set.has()`，禁�?`startsWith()`/`indexOf()` 前缀匹配，通知事件与业务事件分离处理）、F-REVIEW-FIELD-NAME-CASE-SENSITIVE（前端访问后端字段时大小写敏感，前端 `api/types.ts` 必须与后�?Pydantic 模型字段名一一对应，禁止用 `as any` 绕过类型检查）�? 项检查点对应 `xianyu-hunter-dev` step 129/130/131；参数在 `business_keyword_centralization` / `event_type_exact_match` / `field_name_case_sensitive` 节点管理（与后端 v4.31.0 维度 30 �?6 �?B-REVIEW 联动�?|
| 28 | 多用户认证上下文隔离 | 🆕v4.32 多用户场景前端隔离原则：F-REVIEW-MULTI-USER-CONTEXT-ISOLATION（前端按 `user_id` 隔离 Zustand store / 缓存 / 请求路径，禁止全局单例承接多用户数据；切换用户时必�?`queryClient.clear()` + `useGlobalStore.getState().reset()` 后再加载新用户数据）、F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING（认�?token 通过 httpOnly cookie 传递，fetch 必须 `credentials: 'include'` / axios 必须 `withCredentials: true`�?01/440/441/403 状态码语义精细化分支）；参数在 `multi_user_context_isolation` / `auth_token_cookie_handling` 节点管理（与 xianyu-hunter-dev step 134-137 + 后端 v4.32 维度 28 联动�?|
| 29 | 数据契约与时序（meta-rules #25-30 落地�?| 🆕v4.34 前端在数据契约与时序维度�?6 项落地检查点：F-REVIEW-110（批量断路器 UI 三态反馈，区分用户主动停止/熔断可恢�?异常失败，必须展�?success_count/pending_count/failure_reason/recover_action）、F-REVIEW-111（ErrorBoundary 完整 stack 上报，禁 console.error_only/return_null）、F-REVIEW-112（ISO datetime 统一解析与序列化，解析用 new Date().toLocaleString，发送用 toISOString）、F-REVIEW-113（跨进程状态同步六步法前端侧，�?setInterval 替代 SSE）、F-REVIEW-114（前端错误按 error_code 分支，禁 substring 判断）、F-REVIEW-115（业务关键字常量集中管理，禁内联字符串，�?@/constants/businessKeywords 导入，与后端一致性测试）�? 项检查点对应 xianyu-hunter-dev v4.30.0 meta-rules #25-30 + 后端 v4.29.0 维度 31 �?B-REVIEW-151~156；参数在 `data_contract_temporal` 节点管理 |
| 30 | 状态恢复前置校验前端侧（meta-rule #31 落地�?| 🆕v4.35 前端在状态恢复前置校验维度的 1 项落地检查点：F-REVIEW-116 RESUME-PRECHECK-FRONTEND（恢�?启动/继续按钮 onClick 必须先调用后�?precheck API 校验前置条件，禁前端自行实现预检；校验失败时展示 user_hint + retry_after 倒计�?+ 恢复动作按钮；与后端 B-REVIEW-157 配套）；1 项检查点对应 xianyu-hunter-dev v4.31.0 meta-rule #31 + 后端 v4.30.0 B-REVIEW-157；参数在 `resume_policy_precheck` 节点管理 |
| 31 | 注册式资源三件套契约前端侧（meta-rule #33 落地�?| 🆕v4.36 前端在注册式资源三件套契约维度的 1 项落地检查点：F-REVIEW-117 REGISTRATION-COMPLETENESS（菜�?路由/页面/API 模块/后端端点 5 层契约，任一层缺�?CRITICAL；自动化校验 `python scripts/check_registration.py` 退出码 0 才算通过）；1 项检查点对应 xianyu-hunter-dev v4.32.0 meta-rule #33 + 后端 B-REVIEW-159；参数在 `frontend_registration_completeness` 节点管理 |
| 32 | 修复前根因扫描协议前端侧（meta-rule #34 落地�?| 🆕v4.36 前端在修复前根因扫描协议维度�?1 项落地检查点：F-REVIEW-118 ROOT-CAUSE-MIN-COUNT（修复非平凡 bug 前必须先�?�? 个根因覆盖用户层/接口�?数据�?配置�?历史层；PR 描述必含"�? 根因列表"段；git diff 涉及 �? 个无关文件视为违反最小修改原则）�? 项检查点对应 xianyu-hunter-dev v4.32.0 meta-rule #34 + 后端 B-REVIEW-160；参数在 `root_cause_protocol` 节点管理 |
| 33 | 前后端字段契约单一可信源前端侧（meta-rule #35 落地�?| 🆕v4.36 前端在前后端字段契约单一可信源维度的 1 项落地检查点：F-REVIEW-119 CONTRACT-SINGLE-SOURCE（后�?Pydantic/DB Row 字段=权威源，前端 types.ts 必须显式标注"派生来源+Pydantic 字段+变更日期+约束"4 段注释；snake_case 严格透传禁止�?camelCase；命名漂�?CRITICAL）；1 项检查点对应 xianyu-hunter-dev v4.32.0 meta-rule #35 + 后端 B-REVIEW-161；参数在 `contract_single_source` 节点管理 |
| 34 | 规范治理（meta-rules #36-37 落地�?| 🆕v4.37 前端在规范治理维度的 2 项落地检查点：F-REVIEW-120 SEDIMENTATION-THRESHOLD（新立编码规范必须满�?�? 个相�?bug 门槛，单一 bug 立规范需�?experimental 标签 + 1 季度观察期，安全/数据丢失/付费受损豁免）、F-REVIEW-121 DEGRADATION-CLEANUP（利用率 < 3 �?季度�?F-REVIEW 必须标记待合�?待废弃，1 季度观察期后废弃并移�?version-history.md Deprecated 章节，安全类永不退化）�? 项检查点对应 xianyu-hunter-dev v4.33.0 meta-rules #36-37 + 后端 B-REVIEW-162/163；参数在 `meta_rules_governance` 节点管理 |


---

## 37. Provider �����ǰ��״̬���� ??v4.46

- ���صȼ���WARNING��P1��Provider UI ״̬��һ�µ����û������½���
- ���ã�meta-rules #71 / step 210
- **F-REVIEW-162��PROVIDER-UI-STATE ������Ⱦһ����**
  - ÿ�� Provider �����ñ���ֶα������ provider ����������Ⱦ
  - ��ͬ Provider ��ר��������� cpolar authtoken��Cloudflare cert_file��Tailscale ��װָ����������©
  - �ж��źţ�grep "formProvider.*===" frontend/src/ ȱ��ĳ�� provider ���͵�������֧
  - ��Ӧ����淶��step 210

- **F-REVIEW-163��WIZARD-STEPS ���������״̬��**
  - Named Tunnel �򵼱���ʹ�� Steps ����ֲ�������ÿ������ȷ�Ľ���/���/��������
  - ��״̬��currentStep�������� config.yaml �־û�״̬һ��
  - �ж��źţ��򵼲���״̬�������ļ��� cert_file/tunnel_id/hostname ��һ��
  - ��Ӧ����淶��step 210

- **F-REVIEW-164��ASYNC-LOADER-ISOLATION �첽����������**
  - ÿ���첽������login ��ѯ��create��route-dns�������ж����� loading ״̬
  - ��ֹ���� loading ״̬���²����以�����
  - �ж��źţ�loginLoading �� createLoading ����ͬһ�� loading ����
  - ��Ӧ����淶��step 210

- **F-REVIEW-165��POLL-TIMER-CLEANUP ��ѯ��ʱ������**
  - ��ѯ��ʱ����setInterval�����������ж��ʱͨ�� useEffect cleanup ����
  - ��ѯ�ص��б������������״̬����ֹж�غ� setState
  - �ж��źţ�setInterval ���ڵ� useEffect ���غ������� clearInterval
  - ��Ӧ����淶��step 210

- **F-REVIEW-166��ERROR-RESET ����״̬����**
  - �첽����ʧ�ܺ����������� loading �� polling ״̬
  - �û�����ʱ�������֮ǰ�Ĵ���״̬
  - �ж��źţ�catch ������ setLoginPolling(false) �� setCreateLoading(false)
  - ��Ӧ����淶��step 210

- **���ò���**��provider_ui.wizard_steps��provider_ui.poll_interval_ms��Ĭ�� 2500����provider_ui.async_timeout_ms��Ĭ�� 30000���� config.yaml �� provider_ui �ڵ����
- **����**������ Provider ��ص� UI �����Tunnel.tsx��tunnelProviders.ts��tunnel.ts API ģ�飩
- **������**���� Provider ��صı�����첽����

## 38. Per-Preset Credential Management v4.47

- Severity: CRITICAL (P0, credential not following preset switch causes service call failures)
- Reference: meta-rules #70 / step 211
- **F-REVIEW-167: PRESET-APIKEY-INDIVIDUAL per-preset storage slot**
  - When form fields store credentials associated with a specific preset/vendor (e.g., API Key, Token), each preset must have its own storage slot.
  - Switching presets must atomically: (a) save current credential to its slot, (b) restore credential from target preset slot, (c) update active config.
  - Signal: form still uses global credential after preset switch, or credential lost after switch.
  - Config param: credential_storage.per_preset_slots in config.yaml credential_storage node

- **F-REVIEW-168: CONFIG-SAVE-INDEPENDENCE independent save**
  - Form config fields (model name, endpoint URL, API Key, etc.) must have an independent save mechanism, cannot rely on secondary actions (e.g., "test connection") to persist.
  - Signal: only persistence entry after form modification is test/verify button, no independent save button or debounced auto-save.
  - Config param: config_save.independent_button_required in config.yaml config_save node

- **F-REVIEW-169: BACKEND-RETURN-ON-UPDATE update echo**
  - PUT/PATCH config endpoints must return full updated state (including derived fields like preset_id, masked API Key) after modification, frontend stays in sync without extra GET call.
  - Signal: mutation response only returns {ok: true}, frontend needs extra GET request to get updated state.
  - Config param: api.mutation_response_echo in config.yaml api node

- **Applicable**: All form configs involving preset/vendor switching (AI service config, notification channel config, proxy config, etc.)
- **Not applicable**: Pure display forms without credential fields, one-time operation forms


## 39. Per-Preset Credential Frontend Contract v4.44

- Severity: CRITICAL (P0, frontend preset switch does not properly sync with backend credential slots)
- Reference: meta-rules #71 / step 211 / step 212
- **F-REVIEW-170: PRESET-APPLY-NO-KEY-FORWARD applyPreset omits api_key field**
  - When pplyPreset switches presets, it must NOT send the current pi_key value in the PUT request body.
  - The api_key field should only be sent when the user explicitly types/changes it, not during preset switching.
  - Sending api_key during preset switch can overwrite the target preset's slot with the wrong key.
  - Signal: pplyPreset function includes pi_key: config.api_key in the patch object.
  - Config param: credential_storage.frontend_contract.accept_missing_api_key_on_preset_switch in config.yaml

- **F-REVIEW-171: MASKED-KEY-UI-HANDLING masked key display after preset switch**
  - After preset switch, the returned masked api_key (****xxxx) must NOT be written to the password input value.
  - The api_key input should remain empty after preset switch (user must re-enter if needed).
  - Other fields (base_url, model, vision_model, preset_id) should be updated from the response.
  - Signal: setConfig after preset switch includes pi_key: saved.api_key where saved.api_key is a masked value.
  - Config param: ui.masked_key_handling in config.yaml

- **F-REVIEW-172: EMBEDDING-PRESET-KEY-FOLLOW embedding preset also handles key independently**
  - Embedding preset switch must follow the same pattern: do NOT send embedding_api_key during preset switch.
  - The embedding API key slot restoration must also be backend-managed.
  - Signal: pplyEmbeddingPreset includes embedding_api_key in the patch.
  - Config param: credential_storage.embedding_independent_slots in config.yaml

- **Applicable**: All frontend forms involving preset/vendor credential switching
- **Not applicable**: Non-credential form fields, one-time credential operations
## 40. Model Name Case-Sensitivity Review v4.48

- Severity: CRITICAL (P0, model name case mismatch causes API 400 errors)
- Reference: meta-rules #72 / step 214

- **F-REVIEW-173: MODEL-NAME-CASE-ACCURACY preset model name matches official docs**
  - All preset model names in constants.ts (PRESETS / EMBEDDING_PRESETS) must match vendor official API documentation character-for-character including case.
  - DeepSeek: deepseek-v4-flash (all lowercase), not DeepSeek-V4-Flash or deepseek-v4-flash.
  - Baidu: ERNIE-Speed-8K (mixed case), not ernie-speed-8k.
  - Signal: preset model name differs from official docs in case.
  - Config param: model_names.case_sensitive_check in config.yaml model_names node

- **F-REVIEW-174: MODEL-NAME-SHARED-CHECK-LOWER case-insensitive capability check**
  - Model capability check functions (e.g., _is_vision_capable) must use .lower() for case-insensitive matching, since different vendors use different case strategies.
  - Signal: capability check uses exact string match without .lower().
  - Config param: llm_capability_keywords.case_insensitive (default True) in config.yaml

- **Applicable**: All preset model name definitions in frontend constants files
- **Not applicable**: User-custom-input model names (format validation only)


## 41. Config Persistence and Reflection Review v4.48

- Severity: CRITICAL (P0, config values lost after refresh or incorrectly masked)
- Reference: meta-rules #73 / step 215

- **F-REVIEW-175: CONFIG-PERSIST-ON-CHANGE no secondary-action-required save**
  - Every config input field must have an independent persistence entry point (debounced auto-save or dedicated save button), not dependent on secondary actions like "test connection".
  - Signal: the only persistence trigger for form changes is a test/verify button.
  - Config param: config_persistence.persist_on_change (default True) in config.yaml

- **F-REVIEW-176: CONFIG-REFLECT-ORIGINAL non-secret fields reflect raw values**
  - Backend GET endpoint must return original (non-masked) values for all non-secret config fields (base_url, model, vision_model, embedding_*).
  - Signal: GET response contains masked value for a non-secret field.
  - Config param: config_persistence.mask_non_secret_fields (default False) in config.yaml

- **F-REVIEW-177: MASKED-KEY-PUT-SKIP unchanged key detection on PUT**
  - Frontend PUT must detect masked key prefix (****) and omit api_key from the patch when user hasn't changed it.
  - Signal: PUT request body contains api_key starting with ****.
  - Config param: credential_storage.mask_key_prefix (default "****") in config.yaml

- **Applicable**: All config forms with persistent settings
- **Not applicable**: One-time operation forms
## 42. Multi-User Cookie Isolation Frontend Review v4.45

- Severity: CRITICAL (P0, frontend cookie state display breaks after multi-user migration)
- Reference: meta-rules #72-#78 / steps 216-222

- **F-REVIEW-178: COOKIE-USERID-CONTEXT user_id available in frontend cookie operations**
  - Frontend components that display or manipulate cookie state must receive user_id from the authentication context (request.state.user_id passed from backend).
  - Cookie layer status display (/cookies/layers) must show per-user state, not just default user.
  - Signal: cookie status component does not receive or display user_id.
  - Config param: cookie_management.multi_user_isolation.frontend_user_id_required in config.yaml

- **F-REVIEW-179: COOKIE-STATE-SYNC-REFRESH real-time cookie state reflects current user**
  - When user switches accounts or presets, cookie state display must refresh to show the new user's cookies_{user_id}.json state.
  - Auto-refresh polling must include user_id in the request to get correct per-user cookie status.
  - Signal: cookie state display does not refresh after user/preset switch.
  - Config param: cookie_management.multi_user_isolation.state_refresh_on_switch in config.yaml

- **F-REVIEW-180: LOGIN-SUCCESS-COOKIE-INJECT-VERIFY verify injection after login**
  - After successful login, frontend must verify that cookie injection succeeded by checking the response from the login endpoint.
  - The response should include injected cookie count and user_id.
  - Signal: login success handler does not verify injection result.
  - Config param: ui.login_injection_verification in config.yaml

- **F-REVIEW-181: MULTI-USER-COOKIE-DISPLAY per-user cookie count display**
  - Cookie status dashboard must show cookie count per user, not just total.
  - When multiple users exist, switching user view must reload the correct cookies_{user_id}.json state.
  - Signal: cookie count display aggregates across all users instead of per-user.
  - Config param: ui.cookie_display.per_user_mode in config.yaml

- **Applicable**: All frontend components displaying or manipulating cookie state after multi-user migration
- **Not applicable**: Non-cookie UI components, one-time login flows without state display


## 43. Backend Logic Visibility Sync Frontend Review v4.49

- Severity: HIGH (P1, backend logic changes must be reflected in frontend rule documentation)
- Reference: meta-rules #70-#71 / step 223

- **F-REVIEW-182: BACKEND-LOGIC-VISIBILITY-SYNC backend logic changes must have frontend documentation**
  - When backend evaluation logic changes (e.g., new price range scoring, new threshold rules), the EvalRules page must include a corresponding documentation card explaining the new rule.
  - Signal: backend adds new evaluation dimension but EvalRules.tsx has no card explaining it.
  - Config param: eval.rules_visibility.sync_backend_changes (implicit, always True)

- **F-REVIEW-183: RULE-DOCUMENTATION-USABLE-EXAMPLES rule cards must include concrete examples**
  - Rule documentation cards must include concrete numerical examples (e.g., 600-800 yuan gradient) to help users understand abstract rules.
  - Signal: rule card describes logic abstractly without any numerical example.
  - Config param: eval.rules_visibility.include_examples (default True)

- **F-REVIEW-184: RULE-CONFIG-SOURCE-ANNOTATION rule cards must annotate configuration source**
  - Rule documentation must clearly state whether the rule comes from task-level config (per-task min_price/max_price) or global config (AppConfig.eval).*
  - Signal: rule card does not indicate configuration source.
  - Config param: eval.rules_visibility.annotate_config_source (default True)

- **Applicable**: All pages that display evaluation rules, thresholds, or scoring logic
- **Not applicable**: Pages that only consume evaluation results without displaying rules

## 44. Static Build Artifact Awareness Frontend Review v4.49

- Severity: MEDIUM (P2, build artifact management prevents confusion)
- Reference: meta-rules #72-#73 / step 224

- **F-REVIEW-185: STATIC-BUILD-ARTIFACT-NOT-GIT tracked files must not include build artifacts**
  - Files in src/xianyu_hunter/web/static/spa/ must NOT be committed to Git. Only source files (frontend/src/) should be tracked.
  - Signal: git status shows modified files in web/static/spa/ that are staged for commit.
  - Config param: git.ignore_patterns includes src/xianyu_hunter/web/static/spa/

- **F-REVIEW-186: BUILD-VERIFICATION-BEFORE-SUBMIT frontend changes must pass tsc + vite build**
  - Any frontend source change must be verified with both npx tsc --noEmit AND npx vite build before considering the change complete.
  - Signal: frontend PR includes source changes but no build verification evidence.
  - Config param: build.verify_before_submit (default True)

- **F-REVIEW-187: PWA-CACHE-REFRESH-HINT user notified of PWA cache after frontend changes**
  - After making frontend page changes, developers must inform users to Ctrl+F5 or unregister Service Worker.
  - Signal: frontend page changes deployed but users report seeing old content.
  - Config param: pwa.refresh_hints.enabled (default True)

- **Applicable**: All frontend source changes
- **Not applicable**: Pure backend changes without frontend impact

## 45. ��ѯ״̬��ʱչʾ v4.51.0

**F-REVIEW-191: POLLING-TIMEOUT-DISPLAY ǰ����ѯ״̬��ʱչʾ**

- **�淶**��ǰ����ѯ���״̬ʱ����ͬһ״̬����������ֵ���� config ��ȡ��������չʾ��ʱ��ʾ���ṩ"����"����
- **�ж��ź�**��`grep "setInterval.*status|useEffect.*poll"` ���޳�ʱ��ʱ��
- **���ýڵ�**��`config.yaml#async_polling_pattern.timeout_display`
- **���ó���**��
  - �������¼״̬��ѯ��/browser-login/status��
  - Cookie ���������ѯ
  - ������ִ�н�����ѯ
  - �κ� setInterval + status ״̬��ģʽ
- **�����ó���**��
  - һ���� fetch ���󣨷���ѯ��
  - SSE/WebSocket ���ͣ�������������ͣ�����ǰ�˳�ʱ��
  - �û��ֶ�ˢ�³���
- **��ʷ��ѵ**���������¼ Cookie �����׶� IPC �������º������ͣ�ͣ�ǰ�����޵ȴ� 90s ��ű����Ӧ��ǰ�� 60s ʱ������ʾ
---

## ��¼ A��2026-07-22 �������㣨���ڽ�һ�ֶԻ����̣�

> ��Դ����������ʧ������ק/�����û���ά�ȱ��ػ� 3 ����ʵ�����ĸ���

### A.1 ����б�����ʽָ�� width �� ellipsis

**�������**��
```bash
grep -rn "title:.*'" frontend/src/pages/ --include="*.tsx" | grep -v "key:" | grep "dataIndex\|key:" | head -20
```

**����׼**��
- �ַ����У����⡢��������ע������� `ellipsis: true` ����ʽ `width`
- SCROLL_X ����������� width �ܺͶ� 50-60px ����
- ���������������м� width���������㱼 �� �����б�ѹ���� 0 ���

**��ʵʧ��**��������ϸ���� SCROLL_X=1610���̶����ܺ� 1590���������� width����ѹ�����ɼ�

### A.2 ����/���ػ����뱣��ԭ key ������

**�������**��
```bash
grep -rn "translate\|i18n\|labels\[" frontend/src/ --include="*.tsx" --include="*.ts" | head -20
```

**����׼**��
- Tag / Tooltip / Statistic ����ʹ�÷��뺯��ʱ�������� `title` ���Ա���ԭ key
- ���뺯��δƥ�䵽 key ʱ�����뷵��ԭ�ַ��������ף�����ֹ���ؿ�
- ������ļ����������`*.labels.ts`�������ں��� i18n ��չ

**����**��
```tsx
<Tag title={reason}>{translateRejectReason(reason)}</Tag>
<Statistic title={`${translateDimension(dim)} (${dim})`} value={score} />
```

### A.3 �û�������״̬�����߳־û� hook

**�������**��
```bash
grep -rn "localStorage\|sessionStorage\|usePersistentState" frontend/src/ --include="*.tsx" --include="*.ts"
```

**����׼**��
- �û�ƫ�ã���˳����������ҳ��С��ˢ�¼��������� `usePersistentState` hook
- localStorage key ����� namespace ǰ׺���� `xh.evals.columns.order`�������ҳ���ͻ
- �־û��� schema ����� `validator` ��������ֹ�ɰ汾���ݷ����л�����
- ���ٱ��� 1 �пɼ� / ���� 1 ��Ĭ�����ã����ױ�����

**����**��
```tsx
const [order, setOrder] = usePersistentState<string[]>('xh.evals.columns.order', DEFAULT_ORDER, {
  validator: (v): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string')
})
```

### A.4 ��ק/������������ͬ�� state����ֹ�첽�ӳ�

**�������**��
```bash
grep -rn "onDragEnd\|onSortEnd\|DndContext\|SortableContext" frontend/src/ --include="*.tsx"
```

**����׼**��
- `onDragEnd` �ص����� `setState(newOrder)` ͬ�����£����ܵ� onChange
- ������"δ�仯ʱ���� setState"�жϣ�React ǳ�Ƚϻ�ʧЧ��
- ��קǰ��Ҫ�������� re-render��key �仯�����ñ仯��
- �����У�locked: true������������ק�¼�����

**����**��
```tsx
// ���󣺽���¼��˳�򣬲����� state
const onDragEnd = (e) => console.log(e.active.id, e.over?.id)
```

### A.5 ����������֤���̣�ǰ�����У�

**�������**���޸������ִ�У���
```python
# �� Python �� minify �� chunk����֤�ؼ�����/������Ƭ��
import glob, os
files = glob.glob('src/xianyu_hunter/web/static/spa/assets/*.js')
for f in files:
    content = open(f, encoding='utf-8', errors='ignore').read()
    if 'translateDimension' in content or 'ְҵ���' in content:
        print(f'HIT: {os.path.basename(f)}')
```

**����׼**��
- Vite minify �������ᱻѹ����translateDimension �� Ls���������� grep ��������֤
- ������ҵ��ؼ��ʣ����ı�ǩ��Ӣ�� token����֤
- ������������������Դ�ļ��޸�ʱ���� chunk mtime ֮ǰ

**��ʵʧ��**��dimensionLabels.ts ���ñ�����ɾ��������"�ɹ�"���������޷���

---

## ��¼ B���������ǿ��

### B.1 ����ʽ��飨������

```
1. ��̬��飨PR/����ύʱ��
   - �� grep �������
   - ��� TypeScript ���루tsc --noEmit��
   - ��� ESLint

2. ������飨�ϲ�ǰ��
   - npm run build �ɹ�
   - Python �ű���֤�ؼ� chunk ���´���
   - ������ֶ���֤���� 1 ����������

3. �ع���飨����ǰ��
   - ȫ������ͨ����vitest��
   - �˵��˹ؼ�·����Playwright��
```

### B.2 ��鱨��ģ�壨������¼��

```markdown
## ��鱨�� - {�������}

### ������Blocker��
- [ ] ����� width ȱʧ �� �б�ѹ�����ɼ�
- [ ] �����δ����ԭ key �� ���Բ��ɶ�λ

### �ؼ���Critical��
- [ ] �־û� key �� namespace �� ��ҳ���ͻ
- [ ] ��ק��δͬ�� state �� �û���������Ч

### ���飨Major��
- �������Ϊ�����ļ�
- ��ק�����м� `disabled` �Ӿ�����

### ����
- [ ] tsc --noEmit ͨ��
- [ ] npm run build �ɹ�
- [ ] Python ��֤ chunk ���´���
- [ ] ������ֶ���֤ OK
```

---

## ��¼ C���汾��ά��

- ���θ��£�2026-07-22
- �������ܣ�xianyu-hunter-dev����¼ A.5����xianyu-auto-testing
- ������Դ��`docs/00-�����/����-����淶�뼼���Ż�-2026-07-22.md`

---

> **v4.53.0 F-REVIEW-199 COMPONENT-REUSE-STATE-RESET �������״̬ͬ��������飨meta-rule #85 ��أ�2026-07-22 ThumbCell errored ״̬���� Bug ���̣�**�����ڱ��ζԻ������"�ٷ��ɼ�����ͼƬ URL ������ͼ����ʾռλͼ"���⸴�̣������� `ThumbCell` ����� `rowKey={`${r.item_id}-${r.created_at}`}` ���䱻 React ���ã�`useState(false)` �� `errored` ״̬���Զ����á�ʹ�� Sequential Thinking 4 ά�ȸ��̷������ɹ����裨ʶ�� rowKey ������Ų� useState ���á���� useEffect ���á�������֤��/��ȷ���ԣ��Ƿ����������ͬ�����⣩/�ɳ������̣������ useState + ������ + �ڲ�״̬���� prop �� ���� useEffect ���ã�/�����벻���ó��������� 1 �� F-REVIEW ���㡣**F-REVIEW-199 COMPONENT-REUSE-STATE-RESET**��ά�� 3/19����React ����� `rowKey` ���䱻����ʱ��`useState` �ڲ�״̬�����Զ����ã��ڲ�״̬��errored/loading/selected�������� prop �仯ʱ�������� `useEffect` ���á��ж��źţ�`grep "useState" frontend/src/` �ҵ����ڲ�״̬����� �� ����Ƿ��� `<Table>` render / `expandedRowRender` / Tab ��壨`destroyInactiveTabPane={false}`����ʹ�� �� ��� prop �仯ʱ�Ƿ��� `useEffect` �����ڲ�״̬��`rowKey` ����̬�ֶΣ��� `created_at`��+ �б�������� `useState` �� ����ᱻ���ã����������ã������ `errored`/`loading`/`failed` ״̬���޶�Ӧ `useEffect` ���� �� ��ΪΥ�档�޸�ģʽ��`useEffect(() => { setErrored(false) }, [url])`�����ò����� `config.yaml` �� `component_reuse_state_reset` �ڵ�����`enabled`/`components`/`reset_value_defaults`/`reuse_contexts`������Ӳ����ҵ����������ã��б��������չ���������Tab ��������`rowKey` ����̬�ֶε��б�������ã�ÿ�ζ�������ʵ���������key Ψһ�������ڲ�״̬�Ĵ�չʾ�����useEffect ����������������� F-REVIEW-159������ϸ����淶���ϵ� `xianyu-hunter-dev` v4.52.0 �� step 249����˶�Ӧ�ޣ���ǰ�˹淶����

---

## v4.55.0 F-REVIEW-200~204 �������淶��2026-07-22 �ڶ��ָ��̣�

> ��Ӧ xianyu-hunter-dev meta-rules #84-#88������ Sequential Thinking ��ά�ȸ��̳����
> ���ײ���ģʽ��xianyu-auto-testing ģʽ L��״̬�������ع飩/ ģʽ M�����������Լһ���ԣ���

### F-REVIEW-200 DERIVED-SOURCE-ANNOTATION ����ֶ�������Դ��ע��飨ά�� 11/15��

**��ӦԪ����**��#88 �� 5 �� / #35��ǰ����ֶ���Լ��һ����Դ��

**���Ҫ��**��
1. ��� `ResponseModel` / DB Row �ֶα��ʱ��ǰ�� `types.ts` �Ƿ�ͬ������
2. ǰ�� `types.ts` �п���ֶ��Ƿ��ע������Դ��`// derived from backend ResponseModel.xxx`��
3. ����ֶ�������/ɾ��ʱ��ǰ���Ƿ�ͬ���޸ģ�grep ����ֶ����� types.ts �еĲ����

**�жϱ�׼**��
- ��� `ResponseModel` �����ֶε�ǰ�� `types.ts` �޶�Ӧ �� CRITICAL����Լ��ͬ����
- ǰ�� `types.ts` �ֶ���������Դע���ҿ������ �� WARNING����׷����ȱʧ��
- ����ֶ�ɾ����ǰ�� types.ts �������� �� CRITICAL���������ͨ��������ʱ undefined��

**�������**��
```powershell
# ��ȡ��� ResponseModel �ֶ�
Select-String -Path "src/xianyu_hunter/web/routes/api_*.py" -Pattern "class.*ResponseModel" 
# �Ա�ǰ�� types.ts
Select-String -Path "frontend/src/types.ts" -Pattern "derived from"
```

**���ó���**����� ResponseModel/DB Row �ֶ�����/ɾ��/��������ǰ�����Լ�������
**�����ó���**����ǰ���ڲ����ͣ��޺����Դ���������������Ͷ���

---

### F-REVIEW-201 CONFIG-FIELD-UI-COVERAGE �����ֶ�ǰ�˱༭�ؼ�������飨ά�� 11/15��

**��ӦԪ����**��#87 �� 5 �㣨ǰ�� Config.tsx �༭�ؼ���

**���Ҫ��**��
1. DB schema ���û��ɱ༭�����ֶ��Ƿ��� `Config.tsx` ���ж�Ӧ�༭�ؼ�
2. �༭�ؼ������Ƿ����ֶ�����ƥ�䣨string��Input/textarea��bool��Switch��enum��Select��list��Transfer/Select multiple��
3. `types.ts` �������ֶ����Ͷ����Ƿ���ȫ

**�жϱ�׼**��
- DB schema ���ֶε� `Config.tsx` �ޱ༭�ؼ� �� CRITICAL���� 5 ��ȱʧ��
- �ֶ�����Ϊ text ��ʹ�� Input ���� textarea�����ı��������� WARNING
- `types.ts` ȱ���ֶ����Ͷ��� �� CRITICAL���� 4 ��ȱʧ��

**�������**��
```powershell
# �г� Config.tsx �еı���ؼ�
Select-String -Path "frontend/src/pages/Config.tsx" -Pattern "<(Input|TextArea|Switch|Select|Slider|InputNumber)"
# �Ա� types.ts �е������ֶ�
Select-String -Path "frontend/src/types.ts" -Pattern "Config"
```

**���ó���**�����������ֶκ��ǰ�˸�����飻����ҳ���ع������������֤
**�����ó���**��ֻ�����ã����û��ɱ༭������������/����������� DB �־û���

---

### F-REVIEW-202 CONFIG-RESTORE-DEFAULT �����ֶλָ�Ĭ�ϻ�����飨ά�� 11/15��

**��ӦԪ����**��#87 �� 3 �㣨�ָ�Ĭ�ϻ��ƣ�

**���Ҫ��**��
1. ÿ���û��ɱ༭�����ֶ��Ƿ���"�ָ�Ĭ��"��ڣ���ť/�˵�/ͼ�꣩
2. "�ָ�Ĭ��"�Ƿ���� `delete_config`��ɾ�� DB ��¼������д��Ĭ��ֵ�ַ���
3. "�ָ�Ĭ��"��ť��ֵ����Ĭ��ֵʱ�Ƿ� disabled��disabled-when-default��
4. �ָ�Ĭ�Ϻ� UI �Ƿ�ˢ��Ϊ������Ĭ��ֵ

**�жϱ�׼**��
- �����ֶ���"�ָ�Ĭ��"��� �� WARNING���ָ�Ĭ�ϻ���ȱʧ��
- "�ָ�Ĭ��"ͨ��д��Ĭ��ֵ�ַ���ʵ�� �� CRITICAL��Ĭ��ֵ�������ʱ��
- "�ָ�Ĭ��"��ťδʵ�� disabled-when-default �� NIT���û��������⣩

**�������**��
```powershell
Select-String -Path "frontend/src/pages/Config.tsx" -Pattern "delete|restore|�ָ�Ĭ��|reset"
```

**���ó���**���û��ɱ༭�����DB �־û������ñ�
**�����ó���**��ֻ�����ã���Ĭ��ֵ�����������

---

### F-REVIEW-203 TIMEOUT-STAGE-DISPLAY ��ʱ�׶��� UI ��ʾ��飨ά�� 13/15��

**��ӦԪ����**��#85 �� 2 �㣨��ʱ�쳣�û��Ѻ����壩

**���Ҫ��**��
1. �ಽ���첽����������/�ɼ�/��¼����ʱʱ��UI �Ƿ���ʾ����׶�������"�ύ������ʱ"������"δ֪�쳣"
2. ��ʱ������Ϣ�Ƿ������ʱ���� + ����ԭ�� + �������
3. ��ʱ toast/message �Ƿ�����"��ʱ"��"�ỰʧЧ"��������

**�жϱ�׼**��
- ��ʱ��ʾ"δ֪�쳣" �� CRITICAL���û��޷��ж��ǳ�ʱ���ǻỰʧЧ��
- ��ʱ��Ϣ�޳�ʱ���� �� WARNING���û��޷��ж��Ƿ������ʱ��
- ��ʱ��ỰʧЧʹ����ͬ�İ� �� WARNING�����������

**�������**��
```powershell
Select-String -Path "frontend/src/pages/**/*.tsx" -Pattern "δ֪�쳣|unknown error|timeout|��ʱ"
```

**���ó���**�������û����첽��ʱ����������/�ɼ�/��¼�����ಽ��ؼ�·��
**�����ó���**���ڲ���ʱ���ԣ���ֱ�������û�������������

---

### F-REVIEW-204 OVERWRITE-SET-FRONTEND-AWARENESS ���ǲ���ǰ�˸�֪��飨ά�� 11/15��

**��ӦԪ����**��#88 �� 4 �������ǲ��Լ��Ϲ������ ǰ�˲�

**���Ҫ��**��
1. ǰ���Ƿ�����˷��ص��ֶ���������ֵ������ `_coalesce` �����¿��ܱ����ֵ�ĳ�����
2. ǰ��չʾ"�ɼ�δȡ��"���ֶ�ʱ�Ƿ�����"������"��"δȡ��"������ʾ"����"���ǿհף�
3. ǰ���Ƿ��ڹٷ��ɼ�/�زɺ󴥷�����ˢ�£�����չʾ�������ݣ�

**�жϱ�׼**��
- ǰ�˼����ֶ���������ֵ������� `_coalesce` �� WARNING������չʾ��ֵ��ǰ�˲�֪�飩
- "δȡ��"�ֶ���ʾ�հ׶���"����" �� NIT���û��������⣩
- �ٷ��ɼ���δ��������ˢ�� �� WARNING��չʾ�������ݣ�

**�������**��
```powershell
# ���ǰ���Ƿ���"�ɼ���ˢ��"�߼�
Select-String -Path "frontend/src/pages/**/*.tsx" -Pattern "refresh|reload|fetch.*after|�ɼ�.*ˢ��"
```

**���ó���**���ɼ�-�洢-չʾ��·���ٷ��ɼ�/�زɴ������ݸ���
**�����ó���**����ǰ���ڲ�״̬���޲ɼ��߼���ҳ��

---

> **v4.55.0 F-REVIEW-200~204 ���淶�������**����Ӧ xianyu-hunter-dev v4.55.0 meta-rules #84-#88������ xianyu-auto-testing ģʽ L/M��

---

## v4.56.0 F-REVIEW-205 �������淶

### F-REVIEW-205: SIDE-EFFECT-FALLBACK-ALERT ǰ�˸����ö�����ʾ��飨ά�� 13/15��

**��Ӧ meta-rule**��#89 LOGIN-SIDE-EFFECT-AUTOMATION��ǰ����أ�
**���׹淶**��xianyu-hunter-dev/assets/guides/coding-rules/concurrency.md step 253
**���ýڵ�**��config.yaml#side_effect_fallback_alert

**����**����˵�¼�����ã���Ự���ڣ����� fire-and-forget ģʽ��ʧ��ʱ�� logger.debug��ǰ�����֪��˸�����״̬����ʧ��ʱ�ṩ������ʾ���ֶ�������ڣ������û�����Ϊ"��¼�ɹ������ܲ�����"��

**���Ҫ��**��
1. **������ʾ������**����˸�����ʧ��ʱ��ǰ�˱����ж�����ʾ��Alert/Message�������ܾ�Ĭ�޷���
2. **����������ȷ��**����������Ӧ��� `session.active === false` �� `session.status !== 'running'`�����Ƿ����Ĵ���״̬
3. **Alert ���͹淶**��������ʾ����ʹ�� `type="warning"`���� error�����¼�������ѳɹ������ṩ�ֶ��������
4. **�ֶ��������**��������ʾ�������"�ֶ�����Ự"��ť�����ӣ����ú�� `/api/session/start` �ӿ�
5. **״̬��ѯ����**����¼�ɹ���ǰ��Ӧ��ѯ `/api/session/status` ȷ�ϸ������Ƿ���Ч����ʱδ��Ч����ʾ������ʾ
6. **���ò���ע��**��������ʾ�İ�����ѯ������ʱ��ֵ�Ȳ�������� config.yaml ��ȡ

**�ж��źţ�grep ���**��
```bash
# �ź� 1����¼�ɹ�ҳ���޶�����ʾ
grep -rn "login.*success\|��¼�ɹ�" frontend/src/pages/AntiCrawl/ | grep -v "Alert\|Message\|notification"

# �ź� 2��������������ȷ
grep -rn "session.active\|session.status" frontend/src/pages/AntiCrawl/ | grep -v "=== false\|!== 'running'"

# �ź� 3��ȱ���ֶ��������
grep -rn "Alert.*type=\"warning\"" frontend/src/pages/AntiCrawl/ | grep -v "Button\|onClick.*start"
```

**�������**��
```bash
# ͳ�ƶ�����ʾ�����
grep -c "Alert.*warning" frontend/src/pages/AntiCrawl/*.tsx
# ͳ���ֶ������ť��
grep -c "�ֶ����\|manual.*start\|startSession" frontend/src/pages/AntiCrawl/*.tsx
```

**ͨ����׼**��
- ��¼�ɹ�ҳ����ڶ��� Alert ���
- ����������ȷ��� `session.active === false`
- Alert ����Ϊ warning�������ֶ������ť
- ״̬��ѯ����볬ʱ��ֵ�� config ��ȡ
- �İ��� config ��ȡ����Ӳ����

**���ó���**��
- ��¼�ɹ���������˸����õ�ҳ�棨�練����¼����ҳ��
- ������ʧ�ܲ�Ӱ�������ܵ�Ӱ������ĳ���

**�����ó���**��
- ��¼������ʧ�ܵĴ�����ʾ��Ӧ�� error ���ͣ�
- �޸����õĴ�չʾҳ��
- ������ʧ�ܻᵼ�����ݶ�ʧ�ĳ�����Ӧ�� error ���Ͳ���ֹ������

---

> **v4.56.0 F-REVIEW-205 ���淶�������**����Ӧ xianyu-hunter-dev v4.56.0 meta-rule #89��ǰ����أ������� xianyu-auto-testing ģʽ N��config.yaml �Ѳ�ȫ side_effect_fallback_alert ���ýڵ㡣

---

## v4.57.0 F-REVIEW-206 �������淶

### F-REVIEW-206: FALLBACK-PRESERVE-KEY-FRONTEND ���˹��������������飨ά�� 11/15��

**��Ӧ meta-rule**��#90 FALLBACK-PRESERVE-KEY��ǰ����أ�
**��Ӧ��˹���**��B-REVIEW-251
**���ýڵ�**��config.yaml#fallback_preserve_key_frontend
**���صȼ�**��error

**����/��ʷ��ѵ**��2026-07-22 price_range ע�� Bug ���̡�ǰ���ڻ��˹��� item ʵ��ʱ������¼� payload ���˹��죩����©�� task_id �ȹ��������������������ù��������߼���������������û�������ʧЧ��ʹ�� Sequential Thinking 4 ά�ȸ��̷������ɹ����裨ʶ����˹�����Ų��������©����ʽ��ȡ��������֤��/��ȷ���ԣ��Ƿ����������˹���ͬ�����⣩/�ɳ������̣�ǰ�˴Ӳ������ݹ���ʵ�� + �������������� �� ������ʽ��ȡ��������/�����벻���ó��������� 1 �� F-REVIEW ���㡣

**���Ĺ���**��ǰ�˴Ӻ�˻������ݣ����¼� payload ���˹����ʵ�壩�������ʱ�����뱣�����������Ĺ��������� task_id��user_id��item_id����

**���Ҫ��**��
1. **���˹��������������**��ǰ�˴Ӳ�������/�¼� payload ���˹���ʵ��ʱ��������ʽ��ȡ�������������������Ĺ��������� task_id��user_id��item_id��
2. **����������Ĭ�Ͽ�**���������ֶβ����� `undefined`/`null`/`''` ��ΪĬ��ֵ���ף������ payload/response ��ʽ��ȡ
3. **��������У��**���������Ѹ�ʵ����߼����簴 task_id ��ѯ���� user_id �ۺϣ��������õ��ǿչ�����
4. **���ò���ע��**���豣��Ĺ������嵥�� config.yaml ��ȡ����Ӳ����

**�ж��źţ�grep ���**��
```bash
# �ź� 1���ҵ����˹���
grep -rn "payload.get" frontend/src/

# �ź� 2�����˹�����©���������������ʱδ��ȡ task_id/user_id/item_id��
grep -rn "payload.get" frontend/src/ | grep -v "task_id\|user_id\|item_id"
```

**�������**��
```bash
# ͳ�ƻ��˹������
grep -rc "payload.get" frontend/src/
# �����˹����Ƿ񺬹�������ȡ
grep -rn "payload.get" frontend/src/ | grep -E "task_id|user_id|item_id"
```

**�޸�ģʽ**�����˹���ʱ�� payload/response ����ʽ��ȡ��������
```typescript
// ? Υ�棺���˹��� item ʱ��© task_id
const item = {
  id: payload.get('id'),
  price_range: payload.get('price_range'),
  // task_id ��© �� ���ΰ� task_id ����ʧЧ
}

// ? �Ϲ棺��ʽ��ȡ������
const item = {
  id: payload.get('id'),
  price_range: payload.get('price_range'),
  task_id: payload.get('task_id'),  // ��ʽ��ȡ���������ι���
  user_id: payload.get('user_id'),  // ��ʽ��ȡ
}
```

**���ò���**���� `config.yaml` �� `fallback_preserve_key` �ڵ�����`enabled`/`required_keys`/`entity_types`/`fallback_sources`������Ӳ����ҵ�������

**ͨ����׼**��
- ���˹����ʵ��������� `fallback_preserve_key.required_keys` �����Ĺ�����
- �������� payload/response ��ʽ��ȡ����Ĭ�Ͽ�ֵ
- �������嵥�� config.yaml ��ȡ����Ӳ����

**���ó���**��
- ǰ�˴Ӳ������ݹ���ʵ�� + ��������������
- �¼� payload ���˹���ʵ��
- SSE/WebSocket �¼����˹���

**�����ó���**��
- ֱ�Ӵ� API ��ȡ����ʵ�壨�޻��ˣ�
- ��ǰ�˹������ʱ�����޺�˹�����

---

> **v4.57.0 F-REVIEW-206 ���淶�������**����Ӧ xianyu-hunter-dev v4.57.0 meta-rule #90��ǰ����أ���config.yaml �Ѳ�ȫ fallback_preserve_key_frontend ���ýڵ㡣��˶�Ӧ B-REVIEW-251��

---

## v4.60.0 F-REVIEW-214~216 �������淶��2026-07-22 �����ָ��̣�

> ���� xianyu-hunter-dev v4.60.0 meta-rules #101-#102 ��أ���Ӧ"Cookie ״̬�쳣 + ҳ�����ó־û� + CDP ģʽ״̬��ʧ"�������⸴�̡����ýڵ㣺`config/tech-stack.json#hardConstraints.uiPersistence` �� `hardConstraints.multiWritePathCheck`��

### F-REVIEW-214: MULTI-WRITE-PATH-STATE-CHECK ��д��·��״̬��飨meta-rule #101 ǰ����أ�??v4.60

**��������**��ǰ����֤���������м��״̬���� CookieRotator._layer_states.valid����ǰ�����������˻�����м�״̬��ǰ���ж��д��·������ͬһ״̬ʱ
**���ýڵ�**��`config/tech-stack.json#hardConstraints.multiWritePathCheck`
- `intermediateStatePatterns`���м��״̬�ֶ�ģʽ�б��`_layer_states`��`.valid`��`.active`��`_cache_time`��
- `writeEntryPatterns`��д�����ģʽ�б��`on_login_success`��`atomic_update`��`sync_state`��
- `validateActualDataPreferred`���Ƿ�������֤ʵ�����ݣ�true��
- `autoSyncEnabled`���Ƿ������Զ�ͬ����true��

**��鲽��**��
1. **ʶ���м��״̬����**��Grep ɨ��ǰ�˴��������õ��м��״̬�ֶ�
2. **ö������д��·��**��Grep ɨ�����п��ܸ��¸�״̬��д�����
3. **��֤д��·��������**����ÿ��д����ڣ�����Ƿ������״̬��ʼ��/ͬ���߼�����1 ��д��·��δ���� �� P0 ȱ��
4. **����ʵ��������֤**����֤�����Ƿ�ֱ�Ӽ��ʵ�����ݣ��� Cookie ���ݡ�DB ��¼�����ǽ������м��״̬�������������Զ�ͬ�� �� P1 ȱ��
5. **�Զ�ͬ������**����֤��������״̬��һ��ʱ�Ƿ��Զ�ͬ�������Զ�ͬ���������м��״̬ �� P1 ȱ��

**Grep ����**��
```bash
# ʶ���м��״̬����
grep -rn "_layer_states\|\.valid\|\.active\|_cache_time" frontend/src/ --include="*.ts" --include="*.tsx"
# ö��д�����
grep -rn "on_login_success\|atomic_update\|sync_state\|set_layer_state" frontend/src/ --include="*.ts" --include="*.tsx"
# ��֤д��·�������ԣ�д�����δ����ͬ����
grep -rn "on_login_success\|atomic_update" frontend/src/ --include="*.ts" --include="*.tsx" | grep -v "sync_state\|init_state"
```

**���ó���**��Cookie ״̬�������¼̬ͬ���������״̬��������״̬�������û�������״̬
**�����ó���**����ǰ����ʱ״̬���� loading ��ǣ����޺�������ı��ؼ���״̬��һ������Ⱦ״̬
**�����й���Ĺ�ϵ**������ F-REVIEW-113�������״̬ͬ������ F-REVIEW-197�����û������Ĵ��ݣ���ǰ�߹�ע�����ͬ�����ƣ��������עд��·��������

---

### F-REVIEW-215: UI-PREFERENCE-PERSISTENCE-CHECK UIƫ�ó־û���飨meta-rule #102 ǰ����أ�??v4.60

**��������**������ҳ������ʱʹ�� `useState` �����û������õ� UI ƫ�ã����ҳ��С����ͼģʽ��ɸѡ����������״̬������ʽ�����������ҳ���Ƿ���δ�־û��� UI ƫ��
**���ýڵ�**��`config/tech-stack.json#hardConstraints.uiPersistence`
- `persistablePreferences`������־û���ƫ���б��pageSize/viewMode/filter/Enabled/Mode/sortBy/sortOrder��
- `nonPersistableStates`����Ӧ�־û���״̬�б��loading/error/modalVisible/dropdownOpen��
- `storageKeyPrefix`��localStorage key ǰ׺��`xh.`��
- `defaultDebounceMs`��Ĭ�Ϸ����ӳ٣�300ms��
- `draftDebounceMs`���ݸ�����ӳ٣�500ms��

**��鲽��**��
1. **ɨ�� useState ʹ��**��Grep ɨ������ҳ������е� `useState` ����
2. **ʶ���û�ƫ�ñ���**�����������Ƿ�ƥ�� `persistablePreferences` �б��е�ģʽ
3. **��֤�־û�**����ÿ��ƥ����û�ƫ�ñ���������Ƿ�ʹ�� `usePersistentState` ���� `useState`��ʹ�� `useState` �� P1 ȱ��
4. **��֤ storage key**����� `usePersistentState` �� key �Ƿ��� `storageKeyPrefix`��`xh.`����ͷ���Ƿ�Ψһ����������
5. **��֤��������**������Ƿ��ṩ `validator` ��������������֤����ֹ localStorage �����ݵ������ʹ���
6. **�ų��ǳ־û�״̬**����� `nonPersistableStates` �б��е�״̬�Ƿ������� `usePersistentState`

**Grep ����**��
```bash
# ɨ�� useState ��ʶ���û�ƫ�ñ���
grep -rn "useState" frontend/src/pages/ --include="*.tsx" | grep -iE "pageSize|viewMode|filter|Enabled|Mode|sortBy|sortOrder|useCdp|autoRefresh"
# ��֤�Ƿ�ʹ�� usePersistentState
grep -rn "usePersistentState" frontend/src/pages/ --include="*.tsx"
# ��֤ storage key ǰ׺
grep -rn "usePersistentState.*'" frontend/src/pages/ --include="*.tsx" | grep -v "'xh\."
```

**���ó���**�������û������õ� UI ƫ�ã���ҳ����ͼģʽ��ɸѡ�����򡢿��ء�����ѡ�񣩡�����ݸ��Զ����桢�򵼲������
**�����ó���**����ʱ UI ״̬��loading/error/modalVisible/dropdownOpen/hoveredRow�����ܿ�����ļ�ʱֵ�����������״̬
**�����й���Ĺ�ϵ**������ F-REVIEW-175��CONFIG-PERSIST-ON-CHANGE���� F-REVIEW-199��COMPONENT-REUSE-STATE-RESET����ǰ�߹�ע���ñ����ʱ���棬�������ע�û�ƫ�ÿ�Ự�־û�

---

### F-REVIEW-216: STORAGE-ERROR-HANDLING-CHECK storage �������飨meta-rule #102 ������??v4.60

**��������**��ʹ�� localStorage/sessionStorage �������ʵ���Զ���洢���߻� Hook�����洢��ش���Ĵ�����ͻ��˻���
**���ýڵ�**��`config/tech-stack.json#hardConstraints.uiPersistence`
- `storageVersionField`���洢��ʽ�汾�ֶ�����`__v`��
- `defaultDebounceMs`�������ӳ٣�������֤����д���Ƿ���ȷʵ��

**��鲽��**��
1. **��֤ try-catch ����**������ localStorage ��д������������� try-catch �У���ֹ `QuotaExceededError`��`SecurityError` �׳�δ�����쳣
2. **��֤���˻���**��localStorage ������ʱ����˽ģʽ/���ã��������ڴ���ˣ��� `Map`��������ֱ�ӱ���
3. **��֤���ݸ�ʽ**���洢��ʽ��������汾�ֶΣ�`__v`��������δ��Ǩ�ơ���ȡʱ������֤�汾���汾��ƥ��ʱ���˵�Ĭ��ֵ
4. **��֤����У��**����ȡ�����ͨ�� `validator` ����У���������ͣ���ֹ�洢�ľ����ݻ򱻴۸ĵ����ݵ������ʹ���
5. **��֤����д��**����Ƶ���µ�״̬����ʹ�÷���д�루Ĭ�� 300ms��������Ƶ��д�� localStorage Ӱ������
6. **��֤ isPersistent ��ʶ**��`usePersistentState` ���뷵�� `isPersistent` ��ʶ�������֪����ǰ�Ƿ������־û�

**Grep ����**��
```bash
# ��֤ try-catch ������δ������ localStorage ������
grep -rn "localStorage\.\(getItem\|setItem\|removeItem\)" frontend/src/ --include="*.ts" --include="*.tsx" | grep -v "try"
# ��֤���˻���
grep -rn "Map()\|new Map" frontend/src/utils/storage.ts
# ��֤�汾�ֶ�
grep -rn "__v" frontend/src/utils/storage.ts
# ��֤����д��
grep -rn "debounce\|setTimeout" frontend/src/hooks/usePersistentState.ts
```

**���ó���**������ʹ�� localStorage/sessionStorage �ĳ������Զ���洢���ߡ��־û� Hook��PWA ���߻���
**�����ó���**��Cookie �������ж����Ĵ�����淶����IndexedDB �������ж�����������ƣ����ڴ�״̬
**�����й���Ĺ�ϵ**������ F-REVIEW-138��HOOK-CLEANUP-COMPLETENESS���� F-REVIEW-165��POLL-TIMER-CLEANUP����ǰ�߹�ע Hook ��������������������ע�洢��Ĵ�����ͻ���

---

> **v4.60.0 F-REVIEW-UI-PREVIEW-GATE / STATE-SELECTION / DEFENSIVE-RENDER / COMPONENT-REUSE-RESET 规范已补全**：对应 xianyu-hunter-dev v4.60.0 12项历史问题复盘提炼，前端侧。config.yaml 已补全 `ui_preview_gate`、`state_selection`、`spa_render_resilience`、`component_reuse_state_reset` 配置节点。auto-testing 对应模式 V/W/X。

---

## v4.60.0 F-REVIEW-UI-PREVIEW-GATE / STATE-SELECTION / DEFENSIVE-RENDER / COMPONENT-REUSE-RESET（2026-07-23 12项历史问题复盘提炼）

### F-REVIEW-UI-PREVIEW-GATE: UI视觉变更预确认门控（维度 3/7）

**配置节点**：config.yaml#ui_preview_gate
**风险等级**：warning

**背景/历史教训**：基于历史问题复盘——icon/theme/color/layout 大面积替换时，未经过用户预览确认直接全量替换，导致UI一致性被破坏且难以回滚。使用 Sequential Thinking 4 维度复盘法提炼：成功步骤（识别出大面积替换属于高风险操作）/ 不确定性与失败（未设置预确认门控导致全量替换后无法回退）/ 可抽象的固定流程（单模块先行→用户确认→全量替换）/ 适用场景与不适用场景。

**检查要点**：
1. **大面积替换检测**：icon/theme/color/layout 的替换行数超过 `ui_preview_gate.changeLineThreshold`（默认10行）→ 要求预览确认
2. **替换策略**：先替换单模块→用户确认视觉一致性→全量替换，禁止直接全量替换
3. **回滚清单**：全量替换前必须记录回滚清单（变更文件列表+变更前内容），确保可回退
4. **豁免场景**：Bug修复、文案修正等非视觉变更不受门控约束（匹配 `ui_preview_gate.exemptPatterns`）

**判断信号（grep 命令）**：
```bash
# 信号 1：检测 icon 的大面积替换
git diff --stat | grep -E "import.*Icon" | wc -l

# 信号 2：检测 theme/color 大面积替换
git diff --stat | grep -E "colorPrimary|borderRadius|token\." | wc -l

# 信号 3：变更行数统计
git diff --shortstat
```

**修复模式**：单模块先行+用户确认+全量替换
```typescript
// ❌ 违规：直接全量替换所有 icon
- <OldIcon />
+ <NewIcon />
// 涉及 15+ 文件，超过 changeLineThreshold

// ✅ 合规：先替换单模块，用户确认后全量
// Step 1: 单模块替换（如 Dashboard 页面）
// Step 2: 用户预览确认
// Step 3: 全量替换 + 记录回滚清单
```

**结果呈现**：⚠️ UI变更门控未通过——需用户预览确认后再全量替换

**通过标准**：
- 大面积替换前已执行单模块先行策略
- 用户已确认视觉效果一致性
- 回滚清单已记录
- 豁免场景需在 commit message 中标注

**适用场景**：icon 全量替换、主题色调整、borderRadius 统一修改、布局结构大面积调整
**不适用场景**：Bug修复、文案修正、单文件小范围修改（变更行数 < changeLineThreshold）

---

### F-REVIEW-STATE-SELECTION: React状态管理选型正确性（维度 10/3）

**配置节点**：config.yaml#state_selection
**风险等级**：warning

**背景/历史教训**：基于历史问题复盘——页面刷新后用户偏好设置（如自动刷新、视图模式、列配置、密度、折叠状态等）丢失，因为使用了 useState 而非 usePersistentState。用户重新进入页面时所有个性化配置被重置为默认值，体验极差。使用 Sequential Thinking 4 维度复盘法提炼：成功步骤（识别出需持久化的状态应使用 usePersistentState）/ 不确定性与失败（开发者习惯性使用 useState 导致刷新丢失）/ 可抽象的固定流程（检查关键词→判断持久化需求→替换 Hook）/ 适用场景与不适用场景。

**检查要点**：
1. **useState 滥用检测**：扫描所有 useState 是否用于需跨刷新持久化的状态（匹配 `state_selection.preferenceKeywords` 列表）
2. **持久化 Hook 替换**：需持久化的状态应使用 `usePersistentState`（由 `state_selection.persistenceHookName` 配置），而非 `useState`
3. **key 命名规范**：usePersistentState 的 key 必须遵循 `xh.<page>.<field>` 命名模式（由 `state_selection.keyNamingPattern` 配置）
4. **validator 校验**：usePersistentState 必须提供 validator 函数，防止 localStorage 中被篡改的数据导致类型错误

**判断信号（grep 命令）**：
```bash
# 信号 1：检测 useState 用于偏好类状态
grep -rn "useState" frontend/src/pages/ --include="*.tsx" | grep -iE "autoRefresh|viewMode|columnConfig|density|collapsed|expandedKeys|themePreference|recentItems|useCdp"

# 信号 2：检测已使用 usePersistentState 的状态
grep -rn "usePersistentState" frontend/src/ --include="*.tsx"

# 信号 3：检测 key 命名不符合规范
grep -rn "usePersistentState" frontend/src/ --include="*.tsx" | grep -v "'xh\."
```

**修复模式**：useState→usePersistentState 替换
```typescript
// ❌ 违规：用 useState 存储需持久化的偏好
const [autoRefresh, setAutoRefresh] = useState(true)
const [viewMode, setViewMode] = useState('table')

// ✅ 合规：用 usePersistentState 持久化偏好，遵循 xh.<page>.<field> 命名 + validator
const [autoRefresh, setAutoRefresh] = usePersistentState('xh.tasks.autoRefresh', true, {
  validator: (v) => typeof v === 'boolean'
})
const [viewMode, setViewMode] = usePersistentState('xh.tasks.viewMode', 'table', {
  validator: (v) => ['table', 'card'].includes(v)
})
```

**结果呈现**：🔧 useState→usePersistentState 建议替换——刷新后状态丢失

**通过标准**：
- 所有 preferenceKeywords 列表中的状态均使用 usePersistentState
- key 命名遵循 `xh.<page>.<field>` 模式
- 每个 usePersistentState 均提供 validator 函数
- 非持久化状态（loading/error/modalVisible 等）仍使用 useState

**适用场景**：用户偏好设置（自动刷新、视图模式、列配置、密度、折叠状态、展开键、主题偏好、最近项、CDP模式）
**不适用场景**：临时 UI 状态（loading/error/modalVisible/dropdownOpen/hoveredRow）、组件内部非持久化计算状态

---

### F-REVIEW-DEFENSIVE-RENDER: SPA防御性渲染完整性（维度 7/10）

**配置节点**：config.yaml#spa_render_resilience
**风险等级**：error

**背景/历史教训**：基于历史问题复盘——SPA 白屏/崩溃问题频发，根因是缺乏防御性渲染机制：无 ErrorBoundary 导致组件异常时整页白屏；无 lazyRetry 导致 chunk 加载失败无法恢复；无防御性访问导致 API 数据为 null 时渲染崩溃；无 401 拦截防抖导致并发请求时多次跳转登录页。使用 Sequential Thinking 4 维度复盘法提炼：成功步骤（识别出 SPA 渲染层需要四件套防护）/ 不确定性与失败（四件套缺失导致用户体验断崖式下降）/ 可抽象的固定流程（逐一检查四件套→缺失则标记→修复补充）/ 适用场景与不适用场景。

**检查要点**：
1. **全局 ErrorBoundary**：SPA 入口（App.tsx）必须包含全局 ErrorBoundary 包裹，组件异常时展示降级 UI 而非白屏（`spa_render_resilience.requireGlobalErrorBoundary`）
2. **lazyRetry 包装**：所有 React.lazy 动态导入必须用 lazyRetry 包装，chunk 加载失败时自动重试（`spa_render_resilience.requireLazyRetry`）
3. **防御性访问**：API 返回数据的嵌套字段必须使用可选链 `?.` 访问，防止 null/undefined 导致渲染崩溃（`spa_render_resilience.requireDefensiveAccess`）
4. **401 拦截防抖**：全局 401 拦截器必须实现防抖，避免并发请求失败时多次重定向登录页（`spa_render_resilience.require401Debounce`）

**判断信号（grep 命令）**：
```bash
# 信号 1：检测全局 ErrorBoundary
grep -rn "ErrorBoundary" frontend/src/App.tsx

# 信号 2：检测 lazy 是否被 lazyRetry 包装
grep -rn "React.lazy\b" frontend/src/ --include="*.tsx" --include="*.ts" | grep -v "lazyRetry"

# 信号 3：检测 API 数据未使用可选链
grep -rn "data\.\(items\|list\|records\)" frontend/src/ --include="*.tsx" | grep -v "\?\."

# 信号 4：检测 401 拦截是否有防抖
grep -rn "401" frontend/src/api/client.ts | grep -v "debounce\|isRedirecting\|throttle"
```

**修复模式**：添加 ErrorBoundary + lazyRetry + 可选链 + 401 防抖
```typescript
// ❌ 违规：缺少全局 ErrorBoundary
function App() {
  return <Router><Routes>...</Routes></Router>
}

// ✅ 合规：全局 ErrorBoundary 包裹
function App() {
  return (
    <ErrorBoundary fallback={<Result status="error" title="页面异常" />}>
      <Router><Routes>...</Routes></Router>
    </ErrorBoundary>
  )
}

// ❌ 违规：React.lazy 无 lazyRetry
const Dashboard = React.lazy(() => import('./pages/Dashboard'))

// ✅ 合规：lazyRetry 包装
const Dashboard = React.lazy(() => lazyRetry(() => import('./pages/Dashboard'), 'Dashboard'))

// ❌ 违规：直接访问嵌套字段
const items = data.items.map(...)

// ✅ 合规：可选链 + 兜底
const items = data?.items ?? []

// ❌ 违规：401 拦截无防抖
if (status === 401) { navigate('/login') }

// ✅ 合规：401 防抖
if (status === 401 && !isRedirecting) {
  isRedirecting = true
  navigate('/login', { replace: true })
}
```

**结果呈现**：🛡️ 防御性渲染检查清单——缺少[具体项]

**通过标准**：
- App.tsx 包含全局 ErrorBoundary（`spa_render_resilience.checkItems` 第1项）
- 所有 React.lazy 使用 lazyRetry 包装（第2项）
- API 数据访问使用可选链 `?.`（第3项）
- 401 拦截器实现防抖机制（第4项）

**适用场景**：SPA 路由入口、动态加载页面、API 数据渲染、全局 HTTP 拦截器
**不适用场景**：SSR 应用（错误由服务端处理）、非 SPA 的传统多页应用

---

### F-REVIEW-COMPONENT-REUSE-RESET: 组件复用状态重置（维度 3/10）

**配置节点**：config.yaml#component_reuse_state_reset
**风险等级**：warning

**背景/历史教训**：基于历史问题复盘——列表项组件（如 ThumbCell）有内部 useState（如 errored/loading/selected），但在 Table render/expandedRowRender/Tab 面板中复用时，prop 变化但内部状态未重置，导致旧状态残留。例如 ThumbCell 的 errored 状态在切换 item 后仍保持 true，显示错误图标。使用 Sequential Thinking 4 维度复盘法提炼：成功步骤（识别出组件复用时内部状态需随 prop 变化重置）/ 不确定性与失败（开发者未考虑组件复用场景导致状态残留）/ 可抽象的固定流程（检测复用上下文+内部状态→添加 useEffect 重置）/ 适用场景与不适用场景。

**检查要点**：
1. **复用上下文检测**：组件在 Table render/expandedRowRender/Tab 面板中使用（匹配 `component_reuse_state_reset.reuseContexts` 列表）→需检查状态重置
2. **内部状态识别**：组件有 useState 但无 useEffect 监听 prop 变化重置内部状态→标记为问题
3. **重置默认值**：重置时使用 `resetValueDefaults` 配置的默认值（如 errored=false, loading=false, selected=false, expanded=false）
4. **rowKey 静态字段检测**：rowKey 包含静态字段时（如固定 ID），组件实例不会因 key 变化而重新挂载，更需显式重置

**判断信号（grep 命令）**：
```bash
# 信号 1：检测列表项组件中的 useState
grep -rn "useState" frontend/src/components/ --include="*.tsx" | grep -iE "errored|loading|selected|expanded"

# 信号 2：检测在 Table render 中复用的组件
grep -rn "render.*=\|expandedRowRender" frontend/src/pages/ --include="*.tsx"

# 信号 3：检测是否有 useEffect 重置
grep -rn "useEffect" frontend/src/components/ --include="*.tsx" | grep -iE "props\.\|itemId\|taskId"
```

**修复模式**：添加 useEffect 监听 prop 变化重置内部状态
```typescript
// ❌ 违规：ThumbCell 有 errored 状态但切换 item 时未重置
function ThumbCell({ item, src }: ThumbCellProps) {
  const [errored, setErrored] = useState(false)
  // 当 item 变化时，errored 仍为上一项的值
  return errored ? <ErrorIcon /> : <img src={src} onError={() => setErrored(true)} />
}

// ✅ 合规：添加 useEffect 监听 prop 变化重置内部状态
function ThumbCell({ item, src }: ThumbCellProps) {
  const [errored, setErrored] = useState(false)
  // item 变化时重置 errored 为默认值
  useEffect(() => {
    setErrored(false)
  }, [item?.id])
  return errored ? <ErrorIcon /> : <img src={src} onError={() => setErrored(true)} />
}
```

**结果呈现**：🔄 组件复用状态残留——[组件名]的[state名]未随[prop名]变化重置

**通过标准**：
- 列表项组件有 useState + 复用上下文 → 必须有 useEffect 重置
- 重置默认值从 `resetValueDefaults` 配置获取
- rowKey 含静态字段的 Table 更需显式重置检查

**适用场景**：Table render 列表项组件、expandedRowRender 展开行组件、Tab 面板组件、rowKey 含静态字段的列表
**不适用场景**：独立路由页面组件（每次挂载都是新实例）、组件的 prop 不变（无复用场景）

---

> **v4.60.0 F-REVIEW-UI-PREVIEW-GATE / STATE-SELECTION / DEFENSIVE-RENDER / COMPONENT-REUSE-RESET 规范已补全**：对应 xianyu-hunter-dev v4.60.0 12项历史问题复盘提炼，前端侧。config.yaml 已补全 `ui_preview_gate`、`state_selection`、`spa_render_resilience`、`component_reuse_state_reset` 配置节点。auto-testing 对应模式 V/W/X。

---

> **v4.60.0 F-REVIEW-214~216 ���淶�������**����Ӧ xianyu-hunter-dev v4.60.0 meta-rules #101-#102��ǰ����أ���config/tech-stack.json �Ѳ�ȫ `hardConstraints.uiPersistence` �� `hardConstraints.multiWritePathCheck` ���ýڵ㡣��˶�Ӧ B-REVIEW-267/268��auto-testing ��Ӧģʽ S/T��
