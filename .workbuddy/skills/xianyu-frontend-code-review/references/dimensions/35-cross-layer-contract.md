# 35. 跨层契约与测试同步（meta-rules #43-47 落地）🆕v4.39

> 本维度对应 `xianyu-hunter-dev` v4.35.0 meta-rules #43-#47（事件多发布点字段对齐 / 路由三重注册同步 / query string 保留 / 测试同步责任 / 外部依赖隔离），与后端 `xianyu-backend-code-review` 的 B-REVIEW-169~173 联动。前端侧新增 5 个 F-REVIEW 检查点（F-REVIEW-131~135），基于 2026-07-07 SEMI_AUTO 模式通知未触发确认类问题复盘（EVAL_PASSED 事件三处发布点 task_mode 字段不对齐 / 前端 sheetRegistry 未注册新路由 + findSheetMeta 未剥离 query string / useSheetSync 丢失 query string），使用 Sequential Thinking 4 维度复盘法提炼，强调跨层契约对齐与测试同步，确保事件多发布点字段集一致 / 路由三处注册同步 / 外部回链 query string 保留 / 接口签名变更同步测试 / 外部依赖显式 mock。所有检查点强调配置驱动（参数在 `config.yaml` 的 `cross_layer_contract_test_sync` 节点管理，不硬编码）与适用 / 不适用场景说明。

#### F-REVIEW-131：EVENT-MULTI-EMIT-ALIGN 事件多发布点字段对齐（meta-rule #43 前端侧）🆕v4.39

**维度**：15 SSE 重连 / 19 跨组件状态同步

**【强制】**前端消费方按事件 payload 字段分支时（如 `payload.task_mode` / `event.task_mode`），必须确认所有事件发布点（成功路径 / 失败路径 / 超时路径 / 降级路径）发布的字段集一致；任一字段缺失必须显式 fallback，禁止默认 `undefined` 进入分支逻辑导致静默无反馈。

**关键约束**：
- 同一事件类型在多个发布点（成功 / 失败 / 超时 / 降级）字段集不一致 → 视为违规（CRITICAL）
- 消费方按某字段分支（如 `task_mode === 'SEMI_AUTO'`）但无 fallback / else 分支 → 视为违规（WARNING）
- 事件字段名在前后端 / 不同发布点拼写不一致（如 `task_mode` vs `taskMode`）→ 视为违规
- 字段添加至某发布点但未同步到其他发布点 → 视为违规

**判断信号**：
- `grep "payload\.\|event\." frontend/src/` 按字段分支但无 fallback / else 分支 → 视为违规
- `grep -r "emit.*task_mode\|emit.*taskMode" backend/` 多个 emit 点字段集不一致 → 视为违规
- 前端 `switch (payload.xxx)` 的 case 列表与后端 emit 字段集不匹配 → 视为违规

**反模式**：按字段分支但无 fallback，且未确认所有发布点字段一致

**正确模式**：`type EvalEvent = { task_mode: 'AUTO' | 'SEMI_AUTO' | 'MANUAL'; status: string }` 事件类型契约 → `switch (event.task_mode)` 分支处理 → `default` 分支 `console.warn` + 回退到 AUTO 流程

**配置参数**：`cross_layer_contract_test_sync.event_multi_emit_alignment.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_field_fallback`（是否强制字段缺失 fallback，默认 true）、`event_type_contract_required`（是否强制事件类型契约定义，默认 true）、`emit_point_consistency_check`（是否检查后端多发布点字段一致，默认 true）在 `config.yaml` 的 `cross_layer_contract_test_sync.event_multi_emit_alignment` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #43 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-173

**适用**：消费 SSE / WebSocket / postMessage / 自定义事件的前端组件
**不适用**：纯内部 state 变更（无跨层事件传递）、字段为可选且消费方不依赖分支的场景

**历史教训**：SEMI_AUTO 模式通知未触发确认弹窗。根因：EVAL_PASSED 事件存在三处发布点（成功路径 / 异常路径 / 超时路径），某发布点 `task_mode` 字段拼写不一致或缺失，前端按 `task_mode === 'SEMI_AUTO'` 分支但无 fallback，导致字段缺失时静默跳过确认流程，用户报告"通知未触发"。修复：统一三处发布点字段集，前端增加 default 分支兜底。

#### F-REVIEW-132：ROUTE-TRIPLE-REGISTRATION 前端路由三重注册同步（meta-rule #44 前端侧）🆕v4.39

**维度**：8 路由与懒加载 / 14 三处映射同步

**【强制】**新增 SheetWorkspace 多页签路由必须在 L1（路由根组件 `<Route>`）、L2（路由注册表 sheetRegistry）、L3（URL 同步 Hook useSheetSync）三处同步注册；任一处缺失视为路由链路断裂，会导致 URL 与页签状态不同步。

**关键约束**：
- 新增 `<Route>` 但路由注册表无对应条目 → 视为违规（CRITICAL）
- 路由注册表注册新路由但 URL 同步 Hook 未处理该 path → 视为违规（URL 不联动）
- URL 同步 Hook 处理了 path 但路由根组件无对应 `<Route>` → 视为违规（404 fallback）
- 路由 path 在三处拼写不一致（如 `/evaluations` vs `/evaluation`）→ 视为违规

**判断信号**：
- `git diff` 新增 `<Route path="...">` 但同 PR 路由注册表无对应条目 → 视为违规
- `grep "sheetRegistry" frontend/src/` 路由表与 `grep "<Route" frontend/src/` 数量不一致 → 视为违规
- `grep "useSheetSync" frontend/src/hooks/` 处理的 path 列表与路由注册表不一致 → 视为违规

**反模式**：路由根组件新增 Route（如 /evaluations/auto）但路由注册表与 useSheetSync Hook 未同步更新

**正确模式**：L1 `<Route path="/evaluations/auto" element={<AutoEvalPage />} />` + L2 `sheetRegistry` 注册 `{ key, path, label }` + L3 `useSheetSync` 中 `sheetRegistry.find(s => s.path === location.pathname)` 三处同步

**配置参数**：`cross_layer_contract_test_sync.frontend_route_registration.enabled`（开关，默认 true）、`severity`（CRITICAL）、`registration_layers_required`（必须同步的层列表，默认 `["app_route", "sheet_registry", "use_sheet_sync"]`）、`path_consistency_check`（是否检查 path 拼写一致，默认 true）、`auto_validate_on_diff`（是否在 git diff 时自动校验，默认 true）在 `config.yaml` 的 `cross_layer_contract_test_sync.frontend_route_registration` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #44 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-174

**适用**：SheetWorkspace 多页签应用、依赖 URL 同步 sheet 状态的多页签场景
**不适用**：独立路由如 /login / /onboarding（无 sheet 同步需求）、纯内部导航（无 URL 变更）

**历史教训**：新增 SEMI_AUTO 评估路由，仅在路由根组件添加 `<Route>`，但路由注册表未注册对应条目、URL 同步 Hook 未处理该 path，导致用户从外部链接进入该路由时 sheet 页签状态与 URL 不同步。修复：新增路由必须三处同步，CI 自动校验 path 一致性。

#### F-REVIEW-133：QUERY-STRING-RETAIN 外部回链 query string 保留（meta-rule #45 前端侧）🆕v4.39

**维度**：8 路由与懒加载 / 19 跨组件状态同步

**【强制】**URL 同步 Hook 必须用 `location.pathname + location.search` 完整拼接作为路由标识；路由匹配函数（如 findSheetMeta）必须剥离 query string 后再与路由表 path 比对，禁止把含 query 的完整 URL 直接与路由表 path 比较。

**关键约束**：
- URL 同步 Hook 仅用 `location.pathname` 拼接 URL（丢失 query string）→ 视为违规（CRITICAL）
- 路由匹配函数直接用完整 URL（含 query）与路由表 path 比较 → 视为违规（永远匹配失败）
- 外部回链的 query string 在 sheet 切换后丢失 → 视为违规
- 用 `window.location.href` 替代 `location.pathname + location.search` → 视为违规（含 hash / origin 不可控）

**判断信号**：
- `grep "location.pathname" frontend/src/hooks/` 命中但无 `location.search` 配对 → 视为违规
- `grep "findSheetMeta" frontend/src/` 内含 `pathname === path`（未先剥离 query）→ 视为违规
- `grep "window.location.href" frontend/src/hooks/` 命中 → 视为违规（应使用 location 对象拆分字段）

**反模式**：useSheetSync 仅取 location.pathname 丢失 ?task_id=xxx 等 query；findSheetMeta 直接用含 query 的 fullPath 与 sheetRegistry.path 比对导致永远匹配失败

**正确模式**：`useSheetSync` 中 `location.pathname + location.search` 完整保留 query → `findSheetMeta` 中 `fullPath.split('?')[0]` 剥离 query 后再与 `sheetRegistry.path` 比对

**配置参数**：`cross_layer_contract_test_sync.external_callback_query_retention.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_search_retention`（是否强制保留 location.search，默认 true）、`require_query_strip_in_match`（是否强制路由匹配前剥离 query，默认 true）、`forbidden_location_apis`（禁止使用的 location API 列表，默认 `["window.location.href"]`）在 `config.yaml` 的 `cross_layer_contract_test_sync.external_callback_query_retention` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #45 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-175

**适用**：从外部通知 / 邮件 / 二维码回链的路由（含 query string 携带业务参数）、SheetWorkspace URL 同步 Hook
**不适用**：纯内部导航（无 query string）、无需保留 query 的简单路由跳转

**历史教训**：用户从通知中心点击回链进入 `/evaluations/auto?task_id=xxx`，但 URL 同步 Hook 仅用 pathname 同步 sheet，query string 丢失；同时路由匹配函数用完整 URL（含 query）与路由表 path 比对，永远匹配失败导致 sheet 显示首页。修复：URL 同步 Hook 必须 `pathname + search` 拼接，路由匹配函数必须先 `split('?')[0]` 剥离 query 再匹配。

#### F-REVIEW-134：TEST-SYNC-RESPONSIBILITY 测试同步责任（meta-rule #46 前端侧）🆕v4.39

**维度**：可测试性 / 20 API 数据源一致性与类型契约对齐

**【强制】**前端 API 接口签名变更 / Hook 签名变更 / mock 字段集调整 / 异步同步逻辑重构必须在同 PR 同步更新对应 `__tests__/` 测试；测试覆盖率不允许因重构下降。

**关键约束**：
- API 签名变更（参数 / 返回类型 / 字段名）但同 PR `__tests__/` 无修改 → 视为违规（WARNING）
- Hook 签名变更但 Hook 测试未更新 → 视为违规
- mock 字段集调整但测试快照未更新 → 视为违规
- 异步同步逻辑重构（如 useEffect 改用 useSyncExternalStore）但测试用例未调整 → 视为违规

**判断信号**：
- `git diff` 生产代码 API 签名变更但同 PR `__tests__/` 无修改 → 视为违规
- `git diff` Hook 文件签名变更但同 PR Hook 测试文件无修改 → 视为违规
- `grep "vi.mock\|jest.mock" frontend/src/__tests__/` mock 字段集与生产代码字段集不一致 → 视为违规
- 测试覆盖率下降超过 5% → 视为违规

**反模式**：API 签名新增字段（如 task_mode）但测试 vi.mock 仍返回旧字段集，导致测试通过但生产代码按新字段分支失败

**正确模式**：`export type EvalItem = { id; status; task_mode: 'AUTO'|'SEMI_AUTO'|'MANUAL' }` 签名变更 → `vi.mock` 同步更新 mock 字段集含 `task_mode` → 新增 `test('SEMI_AUTO 模式触发确认弹窗')` 分支测试用例

**配置参数**：`cross_layer_contract_test_sync.test_synchronization.enabled`（开关，默认 true）、`severity`（WARNING）、`require_test_update_on_signature_change`（是否强制签名变更同步测试，默认 true）、`mock_field_set_sync_required`（是否强制 mock 字段集与生产代码同步，默认 true）、`coverage_drop_threshold_percent`（覆盖率下降阈值，默认 5）、`test_framework`（测试框架，默认 `vitest`）在 `config.yaml` 的 `cross_layer_contract_test_sync.test_synchronization` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #46 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-172

**适用**：前端 API 层重构、Hook 签名变更、异步同步逻辑（useEffect / useSyncExternalStore）重构、mock 字段集调整
**不适用**：纯样式调整（CSS / Tailwind class）、注释 / 文档修改、纯类型导入调整（无运行时影响）

**历史教训**：API 新增 `task_mode` 字段后未同步更新测试 mock，测试用例仍用旧字段集（无 task_mode）通过 CI，但生产环境按 task_mode 分支时字段缺失导致 SEMI_AUTO 确认弹窗未触发。修复：API 签名变更必须在同 PR 同步测试和 mock 字段集，CI 校验覆盖率下降不超过阈值。

#### F-REVIEW-135：EXTERNAL-DEP-ISOLATION 外部依赖隔离测试可重复性（meta-rule #47 前端侧）🆕v4.39

**维度**：可测试性

**【强制】**前端测试中依赖 `fetch` / `localStorage` / `sessionStorage` / `window` / `import.meta.env` 等外部依赖必须显式 `vi.mock` / `vi.spyOn` / `vi.stubGlobal` / `vi.stubEnv` 隔离，禁止依赖生产 fallback 或运行时真实环境。

**关键约束**：
- 测试中调用 `fetch` 但无 `vi.spyOn(global, 'fetch')` → 视为违规（CRITICAL）
- 测试中读取 `localStorage` 但无 mock → 视为违规（CRITICAL）
- 测试依赖 `import.meta.env.VITE_XXX` 但无 `vi.stubEnv` → 视为违规（WARNING）
- 测试依赖 `window.location` 真实值 → 视为违规

**判断信号**：
- `grep "fetch\|localStorage\|sessionStorage" frontend/src/__tests__/` 命中但同文件无 `vi.mock\|vi.spyOn\|vi.stubGlobal` → 视为违规
- `grep "import.meta.env" frontend/src/__tests__/` 命中但无 `vi.stubEnv` → 视为违规
- `grep "window.location" frontend/src/__tests__/` 命中但无 mock → 视为违规
- 测试在 CI 与本地结果不一致（依赖真实环境）→ 视为违规

**反模式**：测试直接调用真实 fetch / localStorage 而无 vi.spyOn / vi.stubGlobal mock，导致 CI 无网络环境下失败、本地有缓存通过

**正确模式**：`vi.spyOn(global, 'fetch').mockResolvedValue(...)` mock fetch + `vi.stubGlobal('localStorage', { getItem, setItem, removeItem })` mock localStorage + `vi.stubEnv('VITE_API_BASE', '/api/v1')` mock env → 测试结束 `vi.restoreAllMocks()`

**配置参数**：`cross_layer_contract_test_sync.external_dependency_isolation.enabled`（开关，默认 true）、`severity`（CRITICAL）、`require_mock_for_external_deps`（是否强制外部依赖 mock，默认 true）、`external_deps_to_mock`（需 mock 的依赖列表，默认 `["fetch", "localStorage", "sessionStorage", "window", "import.meta.env"]`）、`forbid_real_env_in_test`（是否禁止测试依赖真实环境，默认 true）、`auto_restore_mocks`（是否自动 restoreAllMocks，默认 true）在 `config.yaml` 的 `cross_layer_contract_test_sync.external_dependency_isolation` 节点管理

**对应编码规范**：详见 `xianyu-hunter-dev` v4.35.0 meta-rule #47 + 后端 `xianyu-backend-code-review` v4.35.0 B-REVIEW-177

**适用**：所有前端测试（单元测试 / 集成测试 / Hook 测试 / 组件测试）
**不适用**：纯函数测试（无外部依赖）、TypeScript 类型测试（`tsd`）、常量与枚举测试

**历史教训**：异步同步 Hook 测试依赖真实 `fetch` 和 `localStorage`，本地有缓存与网络通过，CI 无网络环境下失败；同时测试 mock 未设置 `task_mode` 字段，导致 mock 与生产代码字段集不一致。修复：所有外部依赖必须显式 `vi.spyOn` / `vi.stubGlobal` / `vi.stubEnv` mock，确保测试可重复性。
