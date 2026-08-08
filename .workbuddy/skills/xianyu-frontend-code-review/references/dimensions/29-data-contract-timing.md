# 29. 数据契约与时序（meta-rules #25-30 落地）🆕v4.34

> 本维度整合 `xianyu-hunter-dev` v4.30.0 的 meta-rules #25-30 前端侧审查要点，新增 6 个 F-REVIEW 检查点（F-REVIEW-110~115）。所有检查点强调配置驱动（参数在 `config.yaml` 的 `data_contract_temporal` 节点管理，不硬编码）与适用/不适用场景说明。后端对应规范为 `xianyu-backend-code-review` v4.29.0 维度 31 的 B-REVIEW-151~156。

- 🆕v4.34【强制】**F-REVIEW-110: 批量断路器四要素 UI 反馈（batch circuit breaker UI feedback）**
  - 维度归属：29 数据契约与时序
  - 严重等级：error
  - 规范引用：meta-rule #25 批量处理四要素
  - **检查点**：批量操作 UI 必须区分「用户主动停止」「熔断可恢复」「异常失败」三态，**禁止**一律显示"操作已取消"或"操作失败"。熔断可恢复态必须展示 `success_count` / `pending_count` / `failure_reason` / `recover_action`（如"重试剩余 12 条"按钮），与后端 `batch_circuit_breaker` 日志文案（`paused/stopped/failed`）一一对应
  - **判断信号**：
    - `grep "message\\.(warning|error)\\(['\"](?:批次已停止|批次失败).*['\"]\\)" frontend/src/**/*.{ts,tsx}` → 视为**必修 P0 缺陷**（缺少可恢复性提示）
    - `grep "Modal\\.confirm.*停止" frontend/src/**/*.{ts,tsx}` 且 success_count / pending_count 不展示 → 视为缺恢复信息
  - **配置参数**：`data_contract_temporal.batch_circuit_breaker.failure_threshold`（默认 `3`，与后端 B-REVIEW-151 一致）、`required_state_display`（默认 `[running, paused, failed, completed]`）、`required_pause_info`（默认 `[success_count, pending_count, failure_reason, recover_action]`）在 `config.yaml` 管理
  - **适用**：所有用户可中止的批量操作（批量删除/批量导入/批量上报/批量刷新/批量重试）
  - **不适用**：单一 API 调用、≤3 条 item 的小批量操作、定时后台任务（无用户交互入口）
  - **历史教训**：`batch_refresh_scheduler.py` 熔断后剩余项被标记为 `skipped` 但前端仅显示"批次已停止"，用户无法判断是否可恢复，也无法看到"重试剩余 N 条"按钮，导致用户以为操作失败后只能重新发起全量

- 🆕v4.34【强制】**F-REVIEW-111: ErrorBoundary 完整 stack 上报（ErrorBoundary full stack report）**
  - 维度归属：29 数据契约与时序
  - 严重等级：error
  - 规范引用：meta-rule #26 关键路径异常保留完整 traceback
  - **检查点**：React 全局 `ErrorBoundary.componentDidCatch` 必须上报**完整 stack** 到监控服务（如 sentry / 自建 report 端点），**禁止**仅 `console.error` 打印或 `return null` 静默吞异常。后端关键路径用 `logger.exception()` 完整堆栈，前端全局错误兜底必须用同等的"全量上报"语义
  - **判断信号**：
    - `grep "componentDidCatch\\(error[\\s\\S]{0,200}(?:console\\.(log|error)|return\\s+null)" frontend/src/**/*.{ts,tsx}` → 视为**必修 P0 缺陷**（吞异常）
    - ErrorBoundary 仅有 `return <h1>出错了</h1>` 无 `Sentry.captureException(error)` → 视为违规
  - **配置参数**：`data_contract_temporal.error_boundary.require_full_stack_report`（默认 `true`）、`forbidden_patterns`（默认 `[console.error_only, return_null]`）、`report_service`（默认 `sentry`，可改为自建 report 端点）在 `config.yaml` 管理
  - **适用**：所有路由层 ErrorBoundary、所有 lazy 加载模块的兜底 ErrorBoundary、所有全局错误拦截
  - **不适用**：业务层 try/catch（业务层应处理具体错误后展示 UI，不应被 ErrorBoundary 兜底）、测试代码中的 mock ErrorBoundary
  - **历史教训**：MainLayout 顶层 ErrorBoundary 仅 `console.error` 打印，生产环境用户报"页面空白"无法定位根因（无 stack、无 userId、无路由信息）。修复：接入 sentry 并补充 `errorInfo.componentStack` 上报

- 🆕v4.34【强制】**F-REVIEW-112: ISO datetime 统一解析与序列化（ISO datetime parse & serialize）**
  - 维度归属：29 数据契约与时序
  - 严重等级：warning
  - 规范引用：meta-rule #27 datetime 统一时区策略
  - **检查点**：前端展示后端 ISO datetime 必须用 `new Date(isoStr).toLocaleString('zh-CN', { hour12: false })` 解析后转本地时区，**禁止**直接字符串拼接（`iso + ' 创建'`）或字符串方法（`iso.replace('T', ' ').slice(0, 19)`）；前端→后端传递时间必须用 `Date.toISOString()` 保留时区，**禁止** `toString()` / `toLocaleString()` 丢失时区信息
  - **判断信号**：
    - `grep "['\"]\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}['\"]\\s*\\+\\s*['\"]" frontend/src/**/*.{ts,tsx}` → 视为违规（直接拼接）
    - `grep "\\w+_(at|seen|time|active)\\.(replace|slice|substring|substr)\\(" frontend/src/**/*.{ts,tsx}` → 视为违规（字符串方法解析）
    - `grep "(time|date|at)\\s*:\\s*\\w+\\.toString\\(\\)" frontend/src/**/*.{ts,tsx}` → 视为违规（toString 丢时区）
  - **配置参数**：`data_contract_temporal.datetime.parse_iso_method`（默认 `new Date(isoStr)`）、`display_method`（默认 `toLocaleString('zh-CN', { hour12: false })`）、`send_to_backend_method`（默认 `Date.toISOString()`）、`forbidden_parse_methods`（默认 `[replace, slice, substring, substr]`）、`forbidden_send_methods`（默认 `[toString, toLocaleString]`）在 `config.yaml` 管理
  - **适用**：所有展示后端 `created_at` / `updated_at` / `expires_at` / `last_seen_at` 等 ISO 字符串、所有前端→后端的时间字段提交（搜索/筛选/创建）
  - **不适用**：纯展示用 dayjs/day.js 库已封装解析、纯日期不含时间（年月日）、固定文案中的时间字符串
  - **历史教训**：订单列表后端返回 `created_at: "2026-07-05T10:00:00+00:00"`，前端 `isoStr.slice(0, 10)` 取日期直接显示，时区错位（UTC 时间当作本地时间，跨时区用户全部差 8 小时显示）。修复：统一 `new Date(iso).toLocaleString('zh-CN', { timeZone, hour12: false })` 解析

- 🆕v4.34【强制】**F-REVIEW-113: 跨进程状态同步六步法（前端：SSE 推送 + 启动 refetch）**
  - 维度归属：29 数据契约与时序
  - 严重等级：warning
  - 规范引用：meta-rule #28 跨进程状态同步六步法
  - **检查点**：跨进程状态变更（如 Cookie 多层同步、批量进度、登录态变化）前端必须采用 **SSE 推送 + 启动 refetch** 模式，**禁止**用 `setInterval` 长间隔（≥5s）轮询替代 SSE 推送。SSE 推送失败时退化为短间隔（≤2s）轮询 + 启动时强制 refetch，与后端六步法配合
  - **判断信号**：
    - `grep "setInterval\\([^,]+,\\s*\\d{4,}\\)[\\s\\S]{0,300}//.*替代.*SSE|//.*替代.*SSE[\\s\\S]{0,300}setInterval" frontend/src/**/*.{ts,tsx}` → 视为违规（setInterval 替代 SSE）
    - SSE 错误处理无 `visibilitychange` 重建 / 无 `MAX_RECONNECT` 次数限制 → 与已有 F-REVIEW-SSE-ERROR-HANDLING 重复检查
  - **配置参数**：`data_contract_temporal.state_sync.prefer_sse`（默认 `true`）、`sse_substitute_setinterval`（默认 `forbidden`）、`max_setinterval_for_state_sync`（默认 `0`，表示禁止）、`marker_dir_for_frontend`（默认 `data/markers`）在 `config.yaml` 管理
  - **适用**：Cookie 状态变化推送、批量任务进度推送、登录态变化通知、配置变更广播
  - **不适用**：纯 UI 动画（与后端无关）、表单字段同步（父子组件 props）、单一 API 拉取后的本地轮询（≤1s 防抖）
  - **历史教训**：Cookie 状态变更后端写 marker，但前端用 `setInterval(refetch, 5000)` 轮询 → 5s 延迟 + 高频请求浪费。修复：后端通过 SSE `/api/events/stream` 主动推送 `cookie_status_changed` 事件，前端订阅后立即 refetch

- 🆕v4.34【强制】**F-REVIEW-114: 前端错误按 error_code 分支（error_code switch branch）**
  - 维度归属：29 数据契约与时序
  - 严重等级：error
  - 规范引用：meta-rule #29 前端错误按 error_code 分支
  - **检查点**：前端错误展示必须用 `switch (err.error_code)` 按后端 `reason_enum` 分支，**禁止**按文案子串判断（`if (err.message.includes('expired'))`）。`reason_enum` 与后端 `error_code_contract.reason_enum` 一一对应。前端常量集中在 `frontend/src/constants/errorCode.ts`
  - **判断信号**：
    - `grep "if\\s*\\(\\s*\\w+\\.(message|detail|msg)\\.(includes|indexOf|search|match)\\(['\"](?:expired|unavailable|rate limited|page unavailable|login expired|session invalid)" frontend/src/**/*.{ts,tsx}` → 视为**必修 P0 缺陷**（substring 判断）
    - 前端 import `errorCode` 常量缺失 → 视为违规（应从 `frontend/src/constants/errorCode.ts` 导入）
  - **配置参数**：`data_contract_temporal.error_code_branch.reason_enum_source`（默认 `xianyu-backend-code-review.error_code.reason_enum`，与后端单一可信源）、`recognized_error_codes`（默认 10 个 reason 值）、`forbidden_substring_patterns`（默认 `[expired, unavailable, rate_limited, login_expired, session_invalid]`）、`required_pattern`（默认 `switch\\s*\\(\\s*\\w+\\.error_code\\s*\\)`）、`frontend_constants_file`（默认 `frontend/src/constants/errorCode.ts`）在 `config.yaml` 管理
  - **适用**：所有 API 错误处理分支、所有 toast/notification 文案、所有 4xx/5xx 错误展示
  - **不适用**：本地表单校验（无后端响应）、开发环境 console.error 调试日志、第三方 SDK 错误（按 SDK 文档处理）
  - **历史教训**：前端 8 个组件用 `if (err.message.includes('expired'))` 判断 Cookie 过期 → 后端文案从「登录已过期」改为「会话已失效」后所有页面判断失效，统一显示「未知错误」。修复：建立前后端 `error_code` 契约，前端 `switch (err.error_code)` 分支

- 🆕v4.34【强制】**F-REVIEW-115: 业务关键字常量集中管理（business keyword centralization）**
  - 维度归属：29 数据契约与时序
  - 严重等级：warning
  - 规范引用：meta-rule #30 业务关键字常量集中管理
  - **检查点**：前端业务关键字（已售/已删除/宝贝不存在/卖掉了/已售罄等需正则匹配/includes 判断的字符串）**禁止**内联到组件（如 `if (text.includes('已售'))`），**必须**从 `frontend/src/constants/businessKeywords.ts` 导入，**必须**与后端 `config.yaml#business_keywords` 等价（通过 `tests/test_keyword_consistency.py` 验证）
  - **判断信号**：
    - `grep "['\"](?:已售|已删除|宝贝不存在|卖掉了|已售罄)['\"]" frontend/src/**/*.{ts,tsx}` → 视为违规（硬编码）
    - 业务代码 `if (text.includes('xxx'))` 且 xxx 不在 `businessKeywords.ts` → 视为违规
  - **配置参数**：`data_contract_temporal.business_keyword.constants_file`（默认 `frontend/src/constants/businessKeywords.ts`）、`backend_source`（默认 `xianyu-backend-code-review.business_keyword`，单一可信源）、`consistency_test`（默认 `tests/test_keyword_consistency.py`）、`categories`（默认 `[sold, deleted, loginExpired, antiCrawler]`）在 `config.yaml` 管理
  - **适用**：商品状态识别（已售/已删/在售）、错误提示文案匹配、风控标签识别、敏感词过滤
  - **不适用**：纯前端 UI 文案常量、一次性调试字符串
  - **历史教训**：前端商品列表判断已售用 `'已售'`，但后端配置中为 `'已售出'`，导致前端漏判已售出商品，展示为在售

---

