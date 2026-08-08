# 11. 类型安全评审

- 【强制】前后端字段类型一致性（如 `is_sold?: boolean` 与后端 `bool(raw_sold)` 匹配）
- 【强制】可选链使用（`?.`）处理可能缺失的字段
- 【强制】联合类型和 `Exclude`/`Omit` 等高级类型的使用
- 【强制】避免 `any` 类型（必要时用 `unknown` + 类型守卫）
- 【强制】`as` 断言的合理性（是否有更安全的类型收窄方式）
- 【强制】TypeScript 严格模式合规（`strictNullChecks` 等）
- 🆕v4.0【强制】**IIFE 反模式禁止**：JSX 内禁止 `{(() => { ... })()}`，提取为组件顶部变量
  - ✅ `const apiKeyUrl = getApiKeyUrl(config.base_url)` 在 JSX: `{apiKeyUrl ? <Link/> : null}`
  - ❌ `{(() => { const url = getApiKeyUrl(config.base_url); return url ? <Link/> : null })()}`
- 🆕v4.0【强制】**动态资源映射分离**：映射表（`Record<string, string>`）与推断函数分离，不混合
  - 推断函数返回 `null` 表示无匹配，调用方条件渲染
  - 业务参数（URL、阈值）通过配置文件管理，不硬编码
- 🆕v4.4【强制】**F-REVIEW-CONFIG-DRIVEN-TOGGLE：配置驱动功能开关模式**
  - 高风险/高资源消耗的前端功能（如自动同步开关、CDP 调试触发按钮、批量操作）必须配置驱动，参数集中在 `constants.ts` 或 config 文件管理（不硬编码），默认关闭需用户显式启用
  - **判断信号**：功能需用户主动选择 + 可能耗资源（CPU/内存/网络）+ 多环境部署需求 + 涉及浏览器/系统资源调用
  - **修复模式**：`constants.ts` 定义 `FEATURE_TOGGLES` 映射 + 默认值 `false` → 组件通过 `useFeatureToggle(name)` Hook 读取 → 设置页提供 Switch 开关 + 资源消耗提示文案
  - **配置参数**：`enable_flag` 默认 `false`，详细参数（interval/threshold/port）集中在 `constants.ts` 的 `FEATURE_CONFIGS` 节点
  - **适用**：CDP 在线导入触发、Cookie 自动同步开关、向量库重建触发、批量导出等高风险/高资源消耗功能
  - **不适用**：核心功能（必须默认启用）、性能敏感场景（配置加载延迟不可接受）、简单展示组件
  - **历史教训**：`auto_sync` 默认关闭避免用户不知情下启用自动同步导致浏览器资源被占用；前端触发 CDP 导入的按钮应明确提示"需启动 Edge 调试模式"并默认 disabled，需用户先勾选"我已了解"再启用
- 🆕v4.5【强制】**F-REVIEW-ERROR-SEMANTICS：错误提示语义准确性**
  - 前端错误提示文案必须与后端错误根因语义匹配，**禁止**将特定错误（如 token 过期）显示为不相关的语义（如"登录已过期"）
  - **判断信号**：前端 catch 块中根据 HTTP 状态码或错误消息关键词显示提示文案时，文案语义必须与后端错误根因一致
  - **修复模式**：后端错误码根因分析 → 前端按语义分类显示提示（"稍后重试" vs "重新登录"）→ Alert 类型匹配严重性（warning 而非 error）→ 按钮紧迫性匹配操作出口
  - **通过示例**：
    ```typescript
    // RGV587 = mtop API 临时 token 过期，不是登录态失效
    if (detail.includes('令牌临时过期')) {
      setSessionExpired(true)  // 显示"稍后重试"提示，非"重新登录"
    }
    ```
  - **不通过示例**：
    ```typescript
    // RGV587 被映射为 401，前端显示"登录已过期"
    if (status === 401 || detail.includes('登录已过期')) {
      setSessionExpired(true)  // 误导用户重新登录
    }
    ```
  - **适用**：所有前端错误提示（Alert、message、notification）
  - **不适用**：开发环境调试信息
  - **历史教训**：后端将 RGV587（mtop API 临时 token 过期，TTL 1 小时）映射为 HTTP 401("闲鱼登录已过期")，前端捕获 401 后显示红色 Alert"Cookie 失效或会话过期"。但用户多查几次能成功——说明不是登录态失效。修复后改为橙色 warning"搜索令牌临时过期，请稍后重试"
- 🆕v4.7【强制】**F-REVIEW-DATA-FLOW-TRACE-FRONTEND：字段为空 5 点追踪（前端侧）**
  - 前端"字段为空/显示异常"类问题必须配合后端按 5 点逐层追踪，前端侧负责验证 types 声明 + render 取值两点，**禁止**仅查前端单层就下结论"前端 bug"
  - **判断信号**：用户反馈"字段显示'--'/undefined" → 前端 grep 字段名在 `types.ts` 是否声明 → grep 在 `render` 是否正确取值 → 若前端正常则定位为后端问题（配合后端 B-REVIEW-DATA-FLOW-TRACE 追踪 DB/Repo/API 三点）
  - **修复模式**（前端侧 5 点追踪流程）：
    ```typescript
    // 1. types.ts 中字段声明
    interface Order {
      order_id: string          // ✅ 字段已声明
      status: string
      price: number | null      // ✅ 可空字段用 | null
    }
    // 2. render 中取值
    const order = orders.find(o => o.item_id === itemId)
    // 禁止：orders 为空数组时显示"--"
    // ✅ 正确：先检查 orders 是否加载完成
    {orders.length === 0 ? <Empty /> : <Table data={orders} />}
    // 禁止：order.status 被 Repo 层过滤掉（前端无法发现，需配合后端追踪）
    ```
  - **配置参数**：`trace_nodes_frontend`（前端负责的追踪节点：`frontend_types` + `render`）、`required_fields`（必查字段列表）、`null_value_patterns`（空值渲染模式，如 `field || '--'` / `field ?? '暂无'`）在 `config.yaml` 的 `data_flow_trace_frontend` 节点管理
  - **关键约束**：
    - 前端发现字段为空时，必须先确认前端 types + render 两点正常，再定位为后端问题
    - 可空字段必须用 `| null` 显式声明，禁止用 `any` 或省略类型
    - 渲染时必须区分"数据加载中"/"数据为空"/"字段缺失"三种状态
    - 前端 grep 字段名在 `types.ts` 和 `render` 都正常 → 必须反馈后端排查 DB/Repo/API 三点
  - **适用**：用户反馈"字段为空/显示异常/数据丢失"的所有场景
  - **不适用**：前端布局问题（非数据问题）、样式渲染问题、权限问题（用户看不到数据）
  - **历史教训**：评估明细页订单字段显示 "--"，前端排查 types 声明正常、render 取值正常，最终定位为后端 Repo 的 `list_orders_by_item_ids` 一刀切过滤 `if status == 'failed': continue`。前端侧已正常，根因在后端
- 🆕v4.12【强制】**F-REVIEW-XSS-ESCAPE：用户输入字段 HTML 转义**
  - 后端返回的用户输入字段（如 task.source、item.title、user.nickname）在展示时必须经过 HTML 转义，**禁止**直接渲染到 DOM（即使 JSX 默认转义，仍需双重保护防止 dangerouslySetInnerHTML 误用）
  - **核心机制**（审查时必须理解）：
    - React JSX 默认对 `{value}` 进行 HTML 转义，但以下场景不转义：`dangerouslySetInnerHTML`、`<a href={value}>`（javascript: 协议）、`<iframe src={value}>`、动态属性名
    - 后端字段可能包含 `<script>` / `<img onerror=>` / `javascript:` 等 XSS 载荷
    - 双重保护：escapeHtml 函数（转义 < > & " '）+ React JSX 默认转义，确保任意一层失效仍有保护
  - **判断信号**：
    - 后端返回字段直接渲染到 `dangerouslySetInnerHTML` → 视为违规
    - 后端返回字段直接渲染到 `<a href={value}>` 且未校验协议 → 视为违规
    - 后端返回字段为 source/title/nickname/name 等用户可编辑字段 → 必须经过 escapeHtml
    - 代码含 `dangerouslySetInnerHTML={{ __html: backendField }}` → CRITICAL 违规
  - **修复模式**：
    ```typescript
    // ✅ escapeHtml 函数 + SafeSourceTag 组件双重保护
    function escapeHtml(str: string): string {
      return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
    }

    function SafeSourceTag({ source }: { source: string }) {
      // 第一层保护：escapeHtml 转义特殊字符
      const safeSource = escapeHtml(source)
      // 第二层保护：JSX 默认转义（即使 escapeHtml 失效，JSX 仍会转义）
      return <Tag>{safeSource}</Tag>
    }

    // 禁止：后端字段直接渲染到 dangerouslySetInnerHTML

    // 禁止：后端字段直接渲染到 a href 未校验协议（item.url 可能是 javascript:alert(1)）
    // ✅ a href 必须校验协议
    function isSafeUrl(url: string): boolean {
      return /^https?:\/\//i.test(url)
    }
    {isSafeUrl(item.url) && <a href={item.url}>链接</a>}
    ```
  - **配置参数**：`xss_escape.required_for_fields`（必须转义的字段名列表，如 `["source", "title", "nickname", "description", "name"]`）、`xss_escape.forbidden_directives`（禁止的指令列表，如 `["dangerouslySetInnerHTML"]`）、`xss_escape.url_protocol_whitelist`（URL 协议白名单，如 `["http:", "https:"]`）、`xss_escape.double_protection`（默认 `true`，必须双重保护）在 `config.yaml` 的 `xss_escape` 节点管理
  - **适用**：所有后端返回字段的渲染；用户可编辑字段（source/title/nickname/description）；URL 字段（href/src）
  - **不适用**：纯前端硬编码字符串（如 'Hello World'）；数字/布尔类型字段（无 XSS 风险）；React 组件内部状态字段
  - **历史教训**：`TaskContentMenu` 直接渲染后端返回的 `task.source` 字段到 `<Tag>{source}</Tag>`，虽然 JSX 默认转义，但若用户切换到 `dangerouslySetInnerHTML` 渲染模式则会遭 XSS 攻击。修复后增加 `escapeHtml` 函数 + `SafeSourceTag` 组件双重保护
- 🆕v4.13【强制】**F-REVIEW-ERROR-CONTRACT-TIMEOUT：前后端错误码契约与超时识别**
  - 前端调用后端含重试/异步逻辑的接口时，必须用模块级 `statusMessages: Record<number, string>` 映射表 + 独立 `isAxiosTimeout()` 函数双路识别错误，axios 超时无 `response.status` 必须用 `error.code === 'ECONNABORTED'` 和 `/timeout/i.test(error.message)` 识别，**禁止**所有错误走同一通用文案导致用户无法区分"网络超时"和"商品下架"
  - **核心机制**（审查时必须理解）：
    - axios 超时无 `response.status`（请求未到达后端或后端未响应），必须通过 `error.code` 和 `error.message` 识别
    - 后端按语义区分的状态码（401/403/410/440/441/502/503）必须在前端映射表中有对应文案
    - 超时识别优先于 status 映射（因超时无 status）
  - **判断信号**：
    - 前端 catch 块含 `err.response?.status` 但无超时识别逻辑 → 视为违规
    - 前端 `message.error('xxx 失败，请稍后重试')` 出现在多个 catch → 必须按状态码差异化文案
    - 模块内无独立 `isAxiosTimeout` 函数 → 视为违规
    - 错误消息映射表硬编码在 catch 块内 → 必须提取为模块级常量
  - **修复模式**：
    ```typescript
    // ✅ 模块级常量 + 模块级函数 + 统一错误提示
    const COLLECT_OFFICIAL_ERROR_MESSAGES: Record<number, string> = {
      503: '官方采集需要浏览器实例，请用 XH_WITH_SCHEDULER=1 模式启动',
      403: '闲鱼登录已过期，请重新登录闲鱼',
      440: '闲鱼登录已过期，请重新登录闲鱼',
      441: '触发闲鱼反爬限制，请稍后重试或手动完成验证',
      410: '商品详情页加载失败或已下架，请稍后重试',
      502: '浏览器连接异常，请重启服务后重试',
    }
    const COLLECT_OFFICIAL_TIMEOUT_MESSAGE = '官方采集超时（详情页+卖家主页加载缓慢），请稍后重试或检查网络'
    const COLLECT_OFFICIAL_FALLBACK_MESSAGE = '官方采集失败，请稍后重试'

    const isAxiosTimeout = (error: { code?: string; message?: string }): boolean =>
      error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')

    function showStatusError(err: unknown, statusMessages: Record<number, string>,
                             timeoutMessage: string, fallbackMessage: string): void {
      const error = err as { response?: { status?: number; data?: { detail?: string } }; code?: string; message?: string }
      if (isAxiosTimeout(error)) {
        message.error(timeoutMessage)  // 超时优先
      } else if (error?.response?.status != null && statusMessages[error.response.status]) {
        message.error(error?.response?.data?.detail || statusMessages[error.response.status])
      } else {
        message.error(error?.response?.data?.detail || fallbackMessage)
      }
    }

    // 禁止：所有错误走同一通用文案

    // 禁止：无超时识别（axios 超时无 response.status）
    ```
  - **配置参数**：`frontend_error_contract.timeout_codes`（默认 `['ECONNABORTED']`，axios 超时 code 列表）、`frontend_error_contract.timeout_patterns`（默认 `['/timeout/i']`，超时 message 正则模式列表）、`frontend_error_contract.status_message_map`（场景到消息映射，按业务接口分组，如 `collect_official: { 410: '...', 441: '...' }`）、`frontend_error_contract.timeout_priority`（默认 `true`，超时识别优先于 status 映射）在 `config.yaml` 的 `frontend_error_contract` 节点管理
  - **适用**：含重试逻辑的 SSE/HTTP 接口、依赖多个 Cookie 的接口、含状态机的业务接口、浏览器自动化接口
  - **不适用**：一次性请求无重试逻辑、纯 token 认证（JWT 无超时概念）、内部 API（无业务文案需求）
  - **历史教训**：用户反馈"官方采集失败，请稍后重试"，理论推断为 axios 30s 超时，实际日志显示采集只有 12s，根因是后端选择器失效返回 502，前端无超时识别导致无法区分"超时"和"502"
- 🆕v4.13【强制】**F-REVIEW-RETRY-BACKOFF：前端可重试错误集与退避策略**
  - 前端调用后端接口必须区分「可重试错误」（410/441/502/timeout）与「需用户介入错误」（403/440/503），可重试错误用指数/固定退避重试 N 次（默认 N=1），重试时不弹消息避免打扰用户，**禁止**对所有错误一刀切重试导致需用户介入的错误被无意义重试
  - **核心机制**（审查时必须理解）：
    - 可重试错误：临时性故障（410 页面未加载/441 反爬触发/502 连接异常/timeout 超时）
    - 需用户介入错误：403 权限不足/440 Cookie 过期/503 服务未启动，重试无意义
    - 重试时不弹消息：避免偶发失败打扰用户，仅在最终失败时展示错误
    - 退避时间按错误类型差异化：441 反爬需 3s 冷却，410/502 快速重试 1s
  - **判断信号**：
    - 前端 catch 块直接 `throw` 或直接 `message.error` → 必须评估错误是否可重试
    - 前端 `retry_count` 或 `MAX_RETRIES` 硬编码数字 → 必须移到配置或模块级常量
    - 前端对所有错误都重试 → 必须区分可重试与不可重试
    - 前端重试时弹消息 → 应改为静默重试（仅在最终失败时展示）
  - **修复模式**：
    ```typescript
    // ✅ 可重试错误集 + 退避时间映射 + 重试不弹消息
    const RETRYABLE_STATUSES = new Set([410, 441, 502])
    const RETRY_DELAYS: Record<string, number> = {
      '410': 1000,   // 页面未加载，快速重试
      '441': 3000,   // 反爬触发，需 3s 冷却
      '502': 1000,   // 连接异常，快速重试
      'timeout': 2000,  // 超时 2s 后重试
    }

    async function collectOfficialWithRetry(itemId: string, taskId?: string): Promise<OfficialCollectResult> {
      const MAX_RETRIES = 1
      let lastErr: unknown
      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
          return await evalApi.collectOfficial(itemId, taskId)
        } catch (err: unknown) {
          lastErr = err
          if (attempt >= MAX_RETRIES) break
          const e = err as { response?: { status?: number }; code?: string; message?: string }
          const status = e?.response?.status
          const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(e?.message || '')
          const retryable = isTimeout || (status !== undefined && RETRYABLE_STATUSES.has(status))
          if (!retryable) break  // 不可重试错误直接抛出
          const delayKey = isTimeout ? 'timeout' : String(status)
          const delay = RETRY_DELAYS[delayKey] ?? 2000
          await new Promise(resolve => setTimeout(resolve, delay))
          // 重试时不弹消息，避免打扰用户（仅在最终失败时展示错误）
        }
      }
      throw lastErr
    }

    // 禁止：对所有错误一刀切重试
    // 禁止：重试时弹消息打扰用户
    ```
  - **配置参数**：`frontend_retry_strategy.retryable_statuses`（默认 `[410, 441, 502]`，可重试状态码列表）、`frontend_retry_strategy.retry_delays_ms`（默认 `{410: 1000, 441: 3000, 502: 1000, timeout: 2000}`，状态码到退避时间映射）、`frontend_retry_strategy.max_retries`（默认 `1`，最大重试次数）、`frontend_retry_strategy.non_retryable_statuses`（默认 `[403, 440, 503]`，需用户介入的错误列表）、`frontend_retry_strategy.silent_on_retry`（默认 `true`，重试时不弹消息）在 `config.yaml` 的 `frontend_retry_strategy` 节点管理
  - **适用**：网络请求（axios/fetch）、临时性错误（410/441/502/timeout）、浏览器自动化接口
  - **不适用**：需用户介入的错误（403 权限不足/440 Cookie 过期/503 服务未启动）、不可重试业务错误（404 资源不存在）、事务性操作（POST/PUT/DELETE 需幂等性保证）
  - **历史教训**：前端对所有错误直接 `message.error`，用户被偶发的 441 反爬/502 连接异常打扰，需用户手动重试；改为仅对可重试错误自动重试 1 次后，95% 的偶发失败用户无感知
- 🆕v4.14【强制】**F-REVIEW-FILTER-BACKEND-ALIGN：前端过滤与后端分类对齐**
  - 实现前端过滤功能前必须先 grep 后端 `insufficient_count`/`marginals`/`result` 确认分类互斥性，前端过滤条件必须与后端分类逻辑对齐，过滤后各分类数量之和等于总数，**禁止**前端自定义分类逻辑导致与后端统计不一致
  - **维度**：7 API 调用规范
  - **核心机制**（审查时必须理解）：
    - 后端分类是互斥的（每条记录只属于一个分类），前端过滤条件必须与后端分类逻辑 1:1 对齐
    - 过滤后各分类数量之和必须等于总数（互斥性验证），否则说明前端过滤逻辑有误
    - 阈值参数（autoBuyScore/passScore）必须从 config 读取，禁止硬编码
  - **判断信号**：
    - 前端有 filterStatus 状态但未 grep 后端分类逻辑 → 视为违规
    - 前端过滤后各分类数量之和 ≠ 总数 → 视为违规（分类不互斥或过滤逻辑错误）
    - 前端硬编码阈值数字（如 80/60）→ 必须移到配置
  - **示例**：评估明细统计卡片过滤，前端 filterStatus 过滤逻辑必须与后端 `api_evaluations.py` 的 `dist.marginals.result` 分类一致（`score==null→insufficient`，`score>=autoBuyScore→auto`，`passScore<=score<autoBuyScore→pass`，`score<passScore→fail`）
  - **适用**：统计卡片过滤、Tab 分类过滤、状态分组过滤
  - **不适用**：纯前端搜索过滤（无后端分类对应）、非互斥分类
  - **配置驱动**：阈值参数从 config 读取，分类映射表在 `config.yaml` 的 `filter_backend_align` 节点管理
  - **历史教训**：评估明细页统计卡片点击过滤后，前端 filterStatus 分类逻辑与后端 `dist.marginals.result` 不一致，导致过滤后数量与统计卡片显示数量不匹配
- 🆕v4.14【强制】**F-REVIEW-FILTER-PAGINATION-ADAPT：前端过滤后分页参数适配**
  - 添加 filterStatus 状态后必须同步调整 pagination 的 total/current/pageSize 三参数，**禁止**过滤后仍用原 total/items 导致分页错乱或数据截断
  - **维度**：10 Hooks 设计模式
  - **核心机制**（审查时必须理解）：
    - `total=filteredItems.length`：分页总数基于过滤后的数据
    - `current=1`：切换过滤条件时重置到第一页，不触发后端 reload（前端过滤已加载数据）
    - `pageSize=filteredItems.length||1`：全量显示避免截断（过滤后数据量通常较少）
  - **判断信号**：
    - 前端有 filterStatus 但 pagination 仍用原 items.length → 视为违规
    - 切换 filterStatus 时 current 不重置 → 视为违规（可能指向不存在的页）
    - 过滤后 pageSize 仍用原值导致数据截断 → 视为违规
  - **示例**：`filterStatus !== 'all'` 时 `total=filteredItems.length`、`current=1`、`pageSize=filteredItems.length||1`
  - **适用**：前端过滤已加载的分页数据
  - **不适用**：后端分页过滤（filter 参数传给后端）
  - **配置驱动**：分页参数策略在 `config.yaml` 的 `filter_pagination_adapt` 节点管理
  - **历史教训**：评估明细页添加 filterStatus 后未调整 pagination 参数，导致过滤后分页错乱、数据被截断
- 🆕v4.14【强制】**F-REVIEW-FILTER-EMPTY-STATE：过滤空状态区分**
  - 空状态判断必须用 `filteredItems.length` 而非原始 `items.length`，区分「无数据」与「过滤后无匹配」两种文案，**禁止**用同一个空状态文案导致用户无法区分
  - **维度**：3 React 组件规范
  - **核心机制**（审查时必须理解）：
    - `items.length === 0`：数据源为空（后端无数据），应显示「暂无数据」
    - `filteredItems.length === 0` 且 `items.length > 0`：有数据但过滤后无匹配，应显示「当前过滤条件下无匹配记录」
    - 两种空状态文案必须不同，帮助用户判断是数据问题还是过滤问题
  - **判断信号**：
    - 前端用 `items.length === 0` 判断空状态但有 filterStatus → 视为违规
    - 过滤后无匹配数据显示「暂无数据」→ 视为违规（应显示「当前过滤条件下无匹配记录」）
    - 两种空状态用同一文案 → 视为违规
  - **示例**：`filteredItems.length === 0 ? (items.length === 0 ? '暂无数据' : '当前过滤条件下无匹配记录') : <Table>`
  - **适用**：所有带过滤功能的列表页
  - **不适用**：无过滤功能的纯展示列表
  - **配置驱动**：空状态文案在 `config.yaml` 的 `filter_empty_state` 节点管理
  - **历史教训**：评估明细页过滤后无匹配数据时显示「暂无数据」，用户误以为后端无数据，实际是过滤条件不匹配
- 🆕v4.15【强制】**F-REVIEW-DEBUG-CODE-CLEANUP：临时 DEBUG 代码清理**
  - 临时 DEBUG 代码在问题修复后必须移除，**禁止**留在生产代码中。DEBUG 代码包括：临时 import（如 `import * as _fs from 'fs'`）、临时环境变量检查（如 `process.env.DEBUG`）、临时日志文件写入（如 `_fs.writeFileSync('debug.log', ...)`）、临时 console.log（如 `console.log('DEBUG: ...')`）。问题修复后必须 grep 所有 DEBUG 代码并移除，避免污染生产环境
  - **判断信号**：代码含 `import * as _fs` / `process.env.DEBUG` / `writeFileSync('debug.log')` / `console.log('DEBUG')` / 异常密集的 console.log → 必须检查是否为临时 DEBUG 代码；问题修复后 grep 仍有 DEBUG 代码 → 必须移除
  - **修复模式**：
    ```typescript
    // 禁止：问题修复后仍保留 DEBUG 代码（临时 import / process.env.DEBUG / writeFileSync('debug.log') / console.log('DEBUG')）
    // ✅ 正确：问题修复后移除所有 DEBUG 代码
    // grep -rn "DEBUG\|debug\.log\|import \* as _fs\|process\.env\.DEBUG" frontend/src/
    // 确认无残留 DEBUG 代码
    ```
  - **配置参数**：`debug.enabled`（默认 `false`，生产环境禁用 DEBUG 代码）、`debug.cleanup_after_fix`（默认 `true`，问题修复后自动清理 DEBUG 代码）、`debug.whitelist`（长期监控指标白名单，如 `["performance_metrics", "health_check"]`）在 `config.yaml` 的 `debug` 节点管理
  - **适用**：临时调试代码、排查问题后的清理、开发环境调试
  - **不适用**：日志级别动态降级（需保留配置）、长期监控指标收集（需保留）、性能埋点（需保留）
  - **历史教训**：前端问题排查时添加 `import * as _fs` 和 `writeFileSync('debug.log', ...)` 写入调试信息，问题修复后未移除，导致生产环境产生 debug.log 文件污染

- 🆕v4.16【强制】**F-REVIEW-FIELD-CONTRACT-ALIGN：前后端字段契约对齐**
  - **判断信号**：后端有 `_normalize` / `_unify` / `_merge` / `_flatten` 等归一化函数 + 前端 types.ts 声明 damages/inconsistencies 等旧字段 + 前端通过 `check[signalKey]` 动态 key 取值
  - **强制规则**：后端归一化字段时前端 types.ts 必须注释 `// 后端已归一化，前端消费 X 字段`；保留旧字段名必须标 optional 并注释 `// 仅作兼容保留，后端不返回`；前端禁止通过动态 key 取归一化字段，必须直接用归一化后字段名（如 `check.signals`）
  - **反例**：`const signals = (check[signalKey] as string[] | undefined) ?? []`（后端归一化后 signalKey 永远 undefined）
  - **正例**：`const signals = check.signals ?? []`
  - **配置参数**：`field_contract_align` 节点（enabled / require_doc_comment / detect_dynamic_key_access / fallback_to_legacy_field）
  - **适用场景**：后端有归一化函数 + 前端通过动态 key 取值
  - **不适用场景**：后端直接返回原始响应无转换；前端类型声明与后端 pydantic 模型一一对应

- 🆕v4.16【强制】**F-REVIEW-ERROR-HANDLER-EXTRACT：重复错误处理抽取**
  - **判断信号**：grep `status === 403` / `status === 404` 在同文件内出现 >= 2 处；多个 async 函数调用同一后端端点的错误处理 if-else 完全重复
  - **强制规则**：两处以上相同 if-else 状态码分支必须抽取工具函数 `handleXxxError(err, fallbackMsg, closeModal)`；抽取后原调用处仅保留 `handleXxxError(err, '失败文案', () => setModalOpen(false))` 一行
  - **反例**：onAIEval 和 onDeepAnalyze 各自包含 403/404/422 三段 if-else 完全重复
  - **正例**：抽取 `handleAiError(err, fallbackMsg, closeModal)` 工具函数，两处调用各减少 13 行
  - **配置参数**：`error_handler_extract` 节点（enabled / min_duplicate_count / detect_patterns / unified_signature）
  - **适用场景**：多个 async 函数调用同一后端端点；多个函数处理同一类外部 API 错误
  - **不适用场景**：仅一处调用的错误处理；错误处理逻辑有差异（如不同端点状态码集合不同）
- 🆕v4.21【强制】**F-REVIEW-FIELD-NAME-ALIGN：字段名三层一致性规范**
  - 凭据字段名在四层（前端 `types.ts` / 后端 Pydantic 模型 / keyring KEY 常量 / yaml 字段）必须 1:1 对齐；当第三方库构造函数参数名与本项目字段名不一致时，必须在 API 边界层做字段名映射（`_FIELD_NAME_MAP` 映射表 + `_map_credentials_to_notifier_params()` 转换函数），**禁止** API 端点直接 `**body.credentials` 解包透传
  - **核心机制**（审查时必须理解）：
    - Pydantic v2 + keyring + yaml 三层持久化链路中，字段名不一致会导致同步写错位置和 `model_dump()` 丢弃字段
    - 第三方 Notifier 构造函数参数名（如 `webhook_url`/`send_key`/`token`）通常与项目字段名（如 `dingtalk_webhook`/`serverchan_send_key`/`pushplus_token`）不一致
    - API 端点直接 `**body.credentials` 解包传给 Notifier 构造函数，未识别字段会被 `**kwargs` 吞入，触发 `TypeError`
    - 边界层映射函数必须集中在模块顶部声明，禁止散落在多个函数中
  - **判断信号**：
    - 前端 `types.ts` 凭据字段名 ≠ 后端 Pydantic 字段名 → 视为违规
    - 后端 Pydantic 字段名 ≠ keyring KEY 常量 → 视为违规
    - keyring KEY 常量 ≠ yaml 字段 → 视为违规
    - API 端点直接 `**body.credentials` 解包传给 Notifier 构造函数 → 必查字段名映射
    - Notifier 构造函数参数名与前端字段名不一致（如 `dingtalk_webhook` vs `webhook_url`）→ 必须在边界层做字段名映射
  - **修复模式**：
    ```typescript
    // ✅ 前端 types.ts 字段名与后端 Pydantic 字段名 1:1 对齐
    interface NotifierCredentials {
      serverchan_send_key: string
      pushplus_token: string
      bark_server: string
      bark_key: string
      telegram_bot_token: string
      telegram_chat_id: string
      wecom_webhook: string
      dingtalk_webhook: string
      dingtalk_secret: string
      webhook_url: string
    }
    ```

    ```python
    # ✅ 后端边界层字段名映射（集中在模块顶部声明）
    _FIELD_NAME_MAP: dict[str, str] = {
        "serverchan_send_key": "send_key",
        "pushplus_token": "token",
        "bark_server": "server",
        "bark_key": "key",
        "telegram_bot_token": "bot_token",
        "telegram_chat_id": "chat_id",
        "wecom_webhook": "webhook_url",
        "dingtalk_webhook": "webhook_url",
        "dingtalk_secret": "secret",
    }

    def _map_credentials_to_notifier_params(credentials: dict[str, str]) -> dict[str, str]:
        """将前端字段名转换为 Notifier 构造函数参数名"""
        mapped: dict[str, str] = {}
        for key, value in credentials.items():
            mapped[_FIELD_NAME_MAP.get(key, key)] = value
        return mapped

    # 禁止：直接 **body.credentials 解包（TypeError: unexpected keyword argument）
    ```
  - **配置参数**：`field_name_mapping.layers`（必须对齐的层级列表，如 `["frontend_types", "pydantic_model", "keyring_key", "yaml_field"]`）、`field_name_mapping.boundary_map`（边界层字段名映射表，如 `{"serverchan_send_key": "send_key", ...}`）、`field_name_mapping.require_align_check`（默认 `true`，CI 中自动检查字段名对齐）在 `config.yaml` 的 `field_name_mapping` 节点管理
  - **适用场景**：凭据字段（webhook/token/secret 类）；前后端持久化链路字段；多层级字段名一致性要求
  - **不适用场景**：第三方 API 返回字段的归一化（参考 F-REVIEW-FIELD-CONTRACT-ALIGN）；前端内部状态字段（无后端对应）；后端计算字段（无前端写入）
  - **历史教训**：前端字段名 `dingtalk_webhook` 与 Notifier 构造函数参数名 `webhook_url` 不一致，`/api/notifier/test` 直接 `**body.credentials` 解包导致 `TypeError: BaseNotifier.__init__() got an unexpected keyword argument 'dingtalk_webhook'`。修复后添加 `_FIELD_NAME_MAP` 边界层映射
- 🆕v4.21【强制】**F-REVIEW-CONFIG-PERSIST-VERIFY：配置持久化端到端验证规范**
  - 持久化链路必须端到端验证（前端写入 → API 接收 → Pydantic 序列化 → yaml 存储 → keyring 同步（如适用）→ GET 回显），每层必须打印中间值确认传递；修复后必须新增端到端测试覆盖该场景（前端写入 → 刷新页面 → 验证回显）；开关状态字段必须默认安全（如 `enabled: bool = False` 默认关闭，避免意外启用）
  - **核心机制**（审查时必须理解）：
    - 持久化链路任一层断裂都会导致"填写后刷新页面变空"问题
    - Pydantic v2 `extra='ignore'` 会丢弃未声明字段（参考 B-REVIEW-PYDANTIC-FIELD-DECLARE）
    - 前端 `types.ts` 字段缺失会导致 API 响应字段无法被前端消费
    - 开关状态默认值若为 `true`，新增功能默认启用可能造成意外影响
  - **判断信号**：
    - 前端表单填写后刷新页面输入框变空 → 必查持久化链路（types.ts → API → Pydantic → yaml → 回显）
    - 前端开关状态切换后刷新页面还原为初始值 → 必查开关字段是否在 Pydantic 模型中声明
    - API 响应缺失前端写入的字段 → 必查 Pydantic `model_dump()` 是否丢弃未声明字段
    - 前端调用 `PUT /api/config` 成功后 `GET /api/config` 返回旧值 → 必查后端是否实际写入 yaml
  - **修复模式**：
    ```typescript
    // ✅ 前端：写入后立即 GET 验证回显
    const onSave = async (credentials: NotifierCredentials) => {
      await fetch('/api/config', {
        method: 'PUT',
        credentials: 'include',
        body: JSON.stringify(credentials),
      })
      // 端到端验证：立即 GET 确认回显
      const resp = await fetch('/api/config', { credentials: 'include' })
      const data = await resp.json()
      if (data.dingtalk_webhook !== credentials.dingtalk_webhook) {
        message.error('配置未持久化，请检查后端')
      }
    }
    ```
  - **配置参数**：`config_persist_verify.layers`（必须验证的层级列表，如 `["frontend_write", "api_receive", "pydantic_serialize", "yaml_store", "get_response"]`）、`config_persist_verify.require_e2e_test`（默认 `true`，必须新增端到端测试）、`config_persist_verify.default_safe_value`（默认 `false`，开关字段默认安全值）在 `config.yaml` 的 `config_persist_verify` 节点管理
  - **适用场景**：所有用户可编辑的配置项（凭据、开关、阈值）；前端表单到后端持久化的链路；刷新页面后状态需保持的场景
  - **不适用场景**：纯前端状态（如 UI 折叠状态）；运行时计算字段（无需持久化）；调试用临时字段
  - **历史教训**：通知渠道菜单填写凭据后刷新页面输入框清空。根因：`AppConfig` Pydantic 模型未声明凭据字段，`extra='ignore'` 导致 `model_dump()` 丢弃，`GET /api/config` 不返回凭据。修复后端到端验证每一层传递
- 🆕v4.23【强制】**F-REVIEW-MODEL-CAPABILITY-CENTRALIZATION：模型能力元数据集中展示与降级状态可视化**
  - 前端展示 LLM 模型能力（vision_capable / function_call / json_mode）时必须**集中展示**（从后端 `/api/config` 或 `/api/about` 统一获取，禁止在每个展示页独立 fetch / 内联判断）；用户上传图片 / 启用 tool 时前端必须根据能力位给出**降级状态可视化**（如 `Tag color="warning"` 显示"纯文本模型不支持图片分析，已降级为文字描述"），禁止静默丢弃用户的可选输入
  - **核心机制**（审查时必须理解）：
    - 后端 `api_ai._is_vision_capable()` 共享函数 + `api_ai_deep.py` 调用是后端服务端的"能力-需求"匹配
    - 前端展示层是"用户-能力"对齐：用户能直观看到当前模型支持什么能力 + 不支持时降级行为
    - 后端 LLM 调用前预检 + 前端展示能力位 + 降级状态可视化 = 端到端能力驱动派遣
    - 关键字白名单仅在后端 `api_ai._VISION_CAPABLE_KEYWORDS` 一处维护，前端展示用 `settings.openai_vision_model` + 单一 `isVisionCapable()` 共享函数
  - **判断信号**：
    - 前端 `useState` / `useEffect` 内独立 fetch `/api/config` 获取 vision_model + 内联关键字白名单判断（`if (model.includes('vision'))`）→ 视为违规（应统一 fetch + 共享函数）
    - 前端调用图片上传 / function call 时未做能力位预检 + 降级提示 → 视为违规
    - 关键字列表（`['vision', 'gpt-4o', ...]`）出现在前端 `.tsx`/`.ts` 文件中（应仅在后端 `api_ai.py`）→ 视为违规
    - ≥ 2 个前端组件出现相同的 vision_capable 判断逻辑 → 视为违规（应抽到 `frontend/src/utils/modelCapability.ts` 共享）
  - **修复模式**：
    ```typescript
    // ✅ 共享工具函数 + 集中获取 + 降级可视化
    // frontend/src/utils/modelCapability.ts
    const VISION_KEYWORDS = ['vision', 'gpt-4o', 'gpt-4-vision', 'qvq', 'qwen-vl', 'glm-4v', 'claude-3', 'opus', 'sonnet', 'haiku'] as const;
    export function isVisionCapable(modelName: string | null | undefined): boolean {
      if (!modelName) return false;
      return VISION_KEYWORDS.some(kw => modelName.toLowerCase().includes(kw));
    }
    export function getCapabilityDisplay(modelName: string | null | undefined): { vision: boolean; warning?: string } {
      if (!modelName) return { vision: false, warning: '未配置模型' };
      const vision = isVisionCapable(modelName);
      return { vision, warning: vision ? undefined : '当前模型为纯文本模型，已自动降级为文字描述' };
    }

    // AI 配置页（集中展示）
    import { getCapabilityDisplay } from '@/utils/modelCapability';
    const { vision, warning } = getCapabilityDisplay(settings.openai_vision_model);
    return <div>
      <Tag color={vision ? 'success' : 'warning'}>{vision ? '支持 Vision' : '不支持 Vision'}</Tag>
      {warning && <Alert type="warning" message={warning} />}
    </div>;

    // 图片上传组件（消费端）
    const { vision } = getCapabilityDisplay(settings.openai_vision_model);
    const handleUpload = (file: File) => {
      if (!vision) {
        message.warning('当前模型不支持图片分析，将使用文字描述');
        return uploadAsText(file);
      }
      return uploadAsImage(file);
    };
    ```
    ```typescript
    // 禁止：跨组件内联关键字 + 独立 fetch（AIConfigPage / ImageUploader 各自 fetch + 内联关键字判断，散落修改风险）
    ```
  - **配置参数**：`model_capability_centralization.shared_util_path`（默认 `frontend/src/utils/modelCapability.ts`）、`model_capability_centralization.capability_source`（默认 `/api/config` + `/api/about`）、`model_capability_centralization.require_centralized_fetch`（默认 `true`，禁止每页独立 fetch）、`model_capability_centralization.require_downgrade_visualization`（默认 `true`，降级状态必须可视化）、`model_capability_centralization.tag_color_mapping`（默认 `{supported: 'success', unsupported: 'warning'}`）、`model_capability_centralization.alert_message`（默认 `当前模型不支持{capability}，已自动降级为{fallback}`）在 `config.yaml` 的 `model_capability_centralization` 节点管理
  - **适用场景**：前端展示 LLM 模型能力（AI 配置页/设置页/模型选择器）；用户上传图片/启用 tool/选择 json_mode 的交互组件；监控页展示当前模型能力与降级状态；多页面共享同一能力位信息
  - **不适用场景**：纯后端内部能力判断（无前端展示）；单页面单次性能力判断（不必抽取共享函数）；后端 SDK 已封装能力判断（如 langchain `with_structured_output`）
  - **历史教训**：深度分析无脑拼接 `image_url` content block 到后端 400 和 WARNING 噪音；前端用户上传图片时未做能力预检，图片被静默丢弃；修复时后端加 `_is_vision_capable()` 共享函数 + 前端加 `getCapabilityDisplay()` 共享函数 + 集中展示能力 + 上传时降级提示
