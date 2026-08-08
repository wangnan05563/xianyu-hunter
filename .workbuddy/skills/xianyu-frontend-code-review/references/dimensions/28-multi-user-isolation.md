# 28. 多用户认证上下文隔离 🆕v4.32

基于 2026-07-05 完成的 MU2 Sprint（认证中间件改造 + CookieStore 扩展 user_id 维度）复盘（使用 Sequential Thinking 8 步复盘法——成功步骤/不确定性与失败/可抽象的固定流程与判断逻辑/适用场景与不适用场景），系统化梳理前端在多用户认证场景下的上下文隔离原则。本维度强调"前端按 user_id 隔离状态 + 认证 token 通过 httpOnly cookie 传递 + 401 降级路径明确分离"，确保多用户场景下不发生跨用户污染、认证失败有可操作的恢复路径。各项检查点对应 `xianyu-hunter-dev` 编码规范 step 134-137（多用户资源隔离 + 认证中间件多路校验 + 会话 token 安全管理 + 快照与实时数据覆盖决策）。
- 🆕v4.32【强制】**F-REVIEW-MULTI-USER-CONTEXT-ISOLATION：多用户上下文隔离**
  - 维度：28 多用户认证上下文隔离
  - 严重等级：error
  - **检查点**：前端是否存在按 user_id 维度隔离的状态/缓存/请求路径，避免跨用户数据污染
  - **判定标准**：**禁止**前端用全局单例 store/缓存承接多用户会话数据。前端从 `/api/auth/me` 获取当前 `user_id` 后，所有用户特定的 API 请求必须显式携带 `user_id` 上下文（通过请求参数、Header 或后端 session 注入），所有用户特定的 Zustand store 必须按 `user_id` 分桶存储（`Record<UserId, UserState>`），用户切换时必须清空旧用户的全局缓存并触发 `invalidate`
  - **检查范围**：前端所有持有用户特定状态的代码（Zustand store / React Context / localStorage 缓存 / Service Worker 缓存 / SWR/React Query 缓存键）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.32 将 CookieStore 改为 `cookies_{uid}.json` 分文件存储 + `_cache: dict[str, tuple[dict, float]]` 分桶缓存（step 134），前端必须同步按 `user_id` 隔离状态
    - 后端中间件三路校验通过后注入 `request.state.user_id`（step 135），前端从 `/api/auth/me` 拿到 `user_id` 后必须传递给所有用户相关 API
    - 多用户切换时未清空缓存会导致跨用户数据泄漏（A 用户的订单列表显示给 B 用户）
    - 前端"全局单例 store 承接多用户数据"是反模式，必须改为 `Record<UserId, UserState>` 分桶或切换时 `store.reset()`
  - **判断信号**（grep 检测）：
    - `grep -nE "user_id" frontend/src/stores/` 未命中 → 检查 Zustand store 是否考虑了 user_id 维度
    - `grep -nE "localStorage\.(get|set)Item\(['\"]user_" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否按 user_id 分键存储
    - `grep -nE "useUserStore|useAuthStore" frontend/src/` 命中 → 检查用户切换时是否调用 `reset()` 或 `invalidate`
    - 用户反馈"切换账号后看到上一个账号的数据" → 必查前端是否按 user_id 隔离状态
  - **修复模式**：
    ```typescript
    // ✅ 正确：Zustand store 按 user_id 分桶
    interface UserScopedState {
      [userId: string]: {
        orders: Order[]
        preferences: UserPreferences
      }
    }

    const useUserStore = create<UserScopedState>((set, get) => ({
      // 默认空对象
    }))

    // 切换用户时清空旧用户缓存
    function onUserSwitch(newUserId: string) {
      // 1. 清空全局 SWR/React Query 缓存
      queryClient.clear()
      // 2. 重置非用户特定 store
      useGlobalStore.getState().reset()
      // 3. 加载新用户数据
      loadUserData(newUserId)
    }

    // 禁止：全局单例 store 承接多用户数据（多用户切换时未清空，A 用户的订单残留显示给 B 用户）
    ```
  - **配置参数**：`multi_user_context_isolation` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `require_user_id_in_store`（默认 `true`，用户特定 store 必须按 user_id 分桶）
    - `require_invalidate_on_user_switch`（默认 `true`，用户切换时必须清空旧用户缓存）
    - `forbidden_global_singleton_patterns`（默认 `["create<.*>\\(\\)\\s*=>\\s*\\(\\{\\s*orders:"\\]`，禁止全局单例承接多用户数据的模式）
    - `user_id_source`（默认 `"/api/auth/me"`，前端获取当前 user_id 的端点）
    - `backend_isolation_source`（默认 `"xianyu-hunter-dev.multi_user_resource_isolation"`，后端资源隔离规范来源，确保前后端契约对齐）
  - **适用场景**：多用户系统（用户切换/多账号管理）、多租户 SaaS、需要按用户隔离缓存/状态/请求的场景
  - **不适用场景**：单用户系统（无用户切换需求）、纯内部工具（无登录态）、纯只读公共数据展示（无用户特定数据）
  - **历史教训**：MU2 Sprint 中后端 CookieStore 升级为按 `cookies_{uid}.json` 分文件存储，但前端 Zustand store 仍用全局单例承接订单/偏好数据，导致用户 A 切换到用户 B 时短暂显示 A 的订单列表（缓存未清空）。修复方式：前端引入 `onUserSwitch` 钩子，调用 `queryClient.clear()` + `useGlobalStore.getState().reset()` 后再加载新用户数据
  - **对应后端原则**：后端 CookieStore 按 user_id 分文件 + 分桶缓存 + 白名单校验 + SQLite 兜底隔离，详见 `xianyu-hunter-dev` step 134

- 🆕v4.32【强制】**F-REVIEW-AUTH-TOKEN-COOKIE-HANDLING：认证 token cookie 处理**
  - 维度：28 多用户认证上下文隔离
  - 严重等级：error
  - **检查点**：前端是否正确处理认证 token 的 cookie 传递、`credentials: 'include'` 配置、401 降级路径
  - **判定标准**：**禁止**前端将认证 token 存入 `localStorage`（应通过 httpOnly cookie 由后端写入）；**禁止**fetch/axios 请求遗漏 `credentials: 'include'`（或 axios 的 `withCredentials: true`）；**禁止**所有认证失败一律显示"请重新登录"，必须按后端状态码语义区分：401（未登录，跳登录页）/ 440（Cookie 过期，跳重新登录页）/ 441（Token 过期，调刷新接口）/ 403（权限不足，提示无权限）
  - **检查范围**：前端所有 API 请求代码（fetch/axios/SSE EventSource）、所有 401/403/440/441 错误处理分支、所有 token 存取代码
  - **核心机制**（审查时必须理解）：
    - 后端 v4.32 起中间件三路校验：管理令牌直通（hmac.compare_digest）→ 用户会话查库（verify_session）→ 401（step 135），前端必须配合 cookie 传递 token
    - 后端 `make_auth_response` 在登录成功后通过 `set-cookie` 写入 `xh_token` cookie（httpOnly + samesite=lax + max_age=86400*30），前端无法读取但会自动携带
    - 前端 fetch 必须显式 `credentials: 'include'` 才会携带 cookie；axios 必须设 `withCredentials: true`
    - 后端 SSE 事件需通过 htmx `<meta name="htmx-config">` 配置 `withCredentials` 或 EventSource 显式设 `withCredentials: true`
    - 状态码语义精细化（与 v4.27 F-REVIEW-ERROR-CODE-BRANCH 配合）：前端必须按 `error_code` 字段和 HTTP 状态码区分 401/440/441/403 不同降级路径
    - 拦截器层面精确化（与 v4.45 F-REVIEW-154 配合）：axios/fetch 全局响应拦截器跳转登录页必须基于 status + detail 双重校验（`status === 401 && detail === 'Unauthorized'`），禁止仅凭 status 跳转；业务 401（detail 为业务消息）由调用方 catch 处理；详见 config.yaml `interceptor_audit` 配置
  - **判断信号**（grep 检测）：
    - `grep -nE "fetch\\(" frontend/src/api/**/*.ts` 命中后检查是否包含 `credentials: 'include'`
    - `grep -nE "axios\\.create" frontend/src/api/**/*.ts` 命中后检查是否包含 `withCredentials: true`
    - `grep -nE "localStorage\\.(get|set)Item\\(['\"]xh_token" frontend/src/**/*.{ts,tsx}` 命中 → 违规（token 不应在 localStorage）
    - `grep -nE "EventSource\\(" frontend/src/**/*.{ts,tsx}` 命中后检查是否包含 `withCredentials: true`
    - `grep -nE "401.*登录|401.*login" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否区分 401/440/441/403
    - 用户反馈"频繁被踢出登录"/"刷新页面后丢失登录态" → 必查前端是否正确处理 cookie + credentials
  - **修复模式**：
    ```typescript
    // ✅ 正确：fetch 显式 credentials + 状态码分支
    async function fetchOrders() {
      const resp = await fetch('/api/orders', {
        credentials: 'include',  // 必须显式声明，否则不携带 cookie
      })
      if (resp.status === 401) {
        redirectTo('/login')  // 未登录，跳登录页
        return
      }
      if (resp.status === 440) {
        redirectTo('/relogin')  // Cookie 过期，跳重新登录页
        return
      }
      if (resp.status === 441) {
        await refreshToken()  // Token 过期，调刷新接口
        return fetchOrders()  // 重试
      }
      if (resp.status === 403) {
        message.error('权限不足')  // 已登录但无权限
        return
      }
      return resp.json()
    }

    // ✅ 正确：axios 全局配置 withCredentials
    const api = axios.create({
      baseURL: '/api',
      withCredentials: true,  // 全局配置，所有请求携带 cookie
    })

    // ✅ 正确：htmx meta 配置 credentials（初始化时机可靠）
    // <meta name="htmx-config" content='{"withCredentials": true}'>

    // 禁止：token 存 localStorage（XSS 可读取）

    // 禁止：所有认证失败一律跳登录页（未区分语义，用户反复被踢）
    ```
  - **配置参数**：`auth_token_cookie_handling` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `require_credentials_include`（默认 `true`，fetch 必须显式 `credentials: 'include'`）
    - `require_axios_with_credentials`（默认 `true`，axios 必须设 `withCredentials: true`）
    - `forbidden_token_storage`（默认 `["localStorage", "sessionStorage"]`，禁止存储 token 的位置）
    - `status_code_semantics`（默认 `{"401": "redirect_login", "440": "redirect_relogin", "441": "refresh_token", "403": "show_permission_error"}`，状态码到前端动作的映射）
    - `cookie_name`（默认 `"xh_token"`，后端写入的认证 cookie 名称）
    - `cookie_attributes`（默认 `{"httpOnly": true, "samesite": "lax", "max_age": 2592000}`，后端 cookie 属性契约）
    - `backend_auth_source`（默认 `"xianyu-hunter-dev.auth_multi_path_validation"`，后端认证中间件规范来源，确保前后端契约对齐）
  - **适用场景**：所有涉及认证的 API 请求、登录/会话管理、SSE 事件流认证、多角色权限控制
  - **不适用场景**：纯公共 API（无需认证）、第三方 OAuth 回调（按 OAuth 规范处理）、内部微服务间调用（无 cookie 概念）
  - **历史教训**：MU2 Sprint 中后端中间件实现三路校验（管理令牌 + 用户会话 + 401），但前端仍用旧逻辑：所有 401 一律跳登录页，导致用户会话过期（应跳重新登录页）和 Cookie 过期（应刷新 token）也被误判为"未登录"，用户频繁被踢出。同时部分 fetch 请求遗漏 `credentials: 'include'`，导致 cookie 不传递，后端 401 拒绝。修复方式：前端按 `error_code`/状态码分支处理，全局 axios 实例统一配置 `withCredentials: true`，htmx 通过 `<meta>` 配置 credentials
  - **对应后端原则**：后端中间件三路校验 + `make_auth_response` 写入 httpOnly cookie + 状态码语义精细化，详见 `xianyu-hunter-dev` step 135 + step 71（状态码语义精细化）

- 🆕v4.33【强制】**F-REVIEW-EFFECT-MINIMIZE：useEffect 副作用最小化**
  - 维度：3 React 组件规范
  - 严重等级：HIGH
  - **规范引用**：EFFECT-01 useEffect 副作用最小化原则
  - **检查点**：useEffect 是否用于重置用户交互控制的状态、是否应合并而非替换、是否在依赖数组变化时触发不必要的副作用
  - **判定标准**：**禁止**在 useEffect 联动重置用户交互控制的状态（如 openKeys/expandedKeys/activeKey/open），此类状态应通过 useState 初始化 + 用户交互回调更新；**禁止**在 useEffect 替换本应合并的状态更新；useEffect 仅用于订阅/取消订阅、事件监听挂载/卸载、外部系统同步等真正的副作用场景
  - **检查范围**：所有 useEffect 调用，特别是依赖数组包含路由/location/props 和 setState 用户交互控制状态的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "useEffect\\(\\s*\\(\\s*\\)\\s*=>\\s*\\{[^}]*set(OpenKeys|ExpandedKeys|ActiveKey|Open)" frontend/src/**/*.{ts,tsx}` 命中 → 违规
    - useEffect 依赖数组包含 `location.pathname` / `url` 和 setState 用户控制状态 → 违规
    - 用户反馈"菜单动画闪烁"/"展开状态被重置" → 必查 useEffect 是否联动重置
  - **反模式**：
    ```typescript
    // 禁止：useEffect 联动重置用户控制的 openKeys，触发 SubMenu 动画遮挡
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：useState 初始化 + 用户交互控制，移除 useEffect 联动
    const [openKeys, setOpenKeys] = useState<string[]>(() => autoOpenKeys)
    // openKeys 完全由 onOpenChange 用户交互控制，不依赖路由变化
    ```
  - **配置参数**：`coding_standards.effect.disallow_reset_user_controlled_state`（默认 `true`，禁止 useEffect 重置用户控制状态）+ `coding_standards.effect.merge_strategy`（默认 `merge_not_replace`，状态更新应合并而非替换）
  - **适用场景**：所有受控 UI 状态（菜单展开/折叠/选中/Tab 激活）、用户交互后状态需要保留的场景
  - **不适用场景**：订阅外部 store（如 Zustand subscribe）、事件监听挂载/卸载、与外部系统（WebSocket/SSE）同步
  - **历史教训**：MainLayout 中 useEffect 联动重置 openKeys 导致 SubMenu 动画遮挡，用户操作时菜单闪烁。修复方式：完全移除 useEffect，openKeys 由 useState 初始化 + onOpenChange 用户控制
  - **对应后端原则**：无（纯前端 React 组件规范），规范源 xianyu-hunter-dev/references/coding-rules.md EFFECT-01

- 🆕v4.33【强制】**F-REVIEW-STATE-ATOMICITY：状态切换原子性**
  - 维度：3 React 组件规范
  - 严重等级：HIGH
  - **规范引用**：STATE-01 状态切换原子性原则（前端）
  - **检查点**：多字段状态切换是否同步更新，避免部分字段更新导致中间不一致状态
  - **判定标准**：涉及多字段状态切换（如 sheet.active/sheet.minimized/sheet.order 三字段联动）时，**禁止**分散更新单个字段导致中间不一致状态，**必须**封装 transition 方法同步更新所有字段，或使用单一状态枚举（如 sheet.status: 'active' | 'minimized' | 'closed'）替代多字段布尔值
  - **检查范围**：所有涉及多字段状态切换的代码（sheet/workspace/tab/panel 状态管理、对象状态机切换）
  - **判断信号**（grep 检测）：
    - `grep -nE "set\\w+\\(\\s*\\{[^}]*active:\\s*true" frontend/src/**/*.{ts,tsx}` 命中后检查是否同步更新 minimized/order 等关联字段
    - 多字段状态对象的部分更新（`setState({ active: true })` 而非 `setState({ active: true, minimized: false })`）→ 违规
    - 用户反馈"切换 Tab 时短暂出现两个激活状态" → 必查状态切换原子性
  - **反模式**：
    ```typescript
    // 禁止：只更新 active 忘了 minimized，导致 sheet 同时处于 active + minimized
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：封装 transition 方法，同步更新所有关联字段
    const activateSheet = (id: string) => {
      setSheets(prev => prev.map(s => {
        if (s.id === id) return { ...s, active: true, minimized: false }
        return { ...s, active: false }
      }))
    }
    // 或使用单一状态枚举替代多字段布尔值
    type SheetStatus = 'active' | 'minimized' | 'closed'
    ```
  - **配置参数**：无（纯代码模式检查，配置驱动通过 checklist.react_component 开关）
  - **适用场景**：多字段状态联动切换（sheet/tab/panel/workspace）、状态机转换、需要保持一致性的复合状态
  - **不适用场景**：独立单字段状态、无关联的并行状态更新、性能优化的批量更新（已有 React batching 保证）
  - **历史教训**：SheetWorkspace 中 `sheet.active = true` 时忘记同步 `sheet.minimized = false`，导致 sheet 同时显示为激活和最小化状态。修复方式：封装 `activateSheet` transition 方法同步更新所有关联字段
  - **对应后端原则**：无（纯前端状态管理），规范源 xianyu-hunter-dev/references/coding-rules.md STATE-01

- 🆕v4.33【强制】**F-REVIEW-SSE-CONN-MGMT：SSE 连接管理三要素**
  - 维度：15 SSE 重连
  - 严重等级：CRITICAL
  - **规范引用**：SSE-01 SSE 连接管理三要素
  - **检查点**：SSE 连接是否同时具备三要素——visibilitychange 监听（页面恢复可见时重建连接）、last_event_id 回放（断线重连时传递最后事件 ID）、最大重试限制（超限后降级轮询）
  - **判定标准**：**禁止**SSE 无限重连（必须配置 max_reconnect_attempts，超限后退化为轮询）；**必须**监听 visibilitychange 事件在页面恢复可见时重建连接；**必须**在重连时通过 `?last_event_id=` 参数传递最后事件 ID 启用服务端回放
  - **检查范围**：所有 EventSource / useEventSource 调用，SSE 重连逻辑，visibilitychange 事件监听
  - **判断信号**（grep 检测）：
    - `grep -nE "new EventSource\\(" frontend/src/**/*.{ts,tsx}` 命中后检查是否包含 visibilitychange 监听
    - `grep -nE "addEventListener\\('error'[\\s\\S]*setTimeout\\(connect" frontend/src/**/*.{ts,tsx}` 命中后检查是否有 MAX_RECONNECT 限制
    - `grep -nE "EventSource\\([^)]*\\)" frontend/src/**/*.{ts,tsx}` 命中后检查是否包含 `?last_event_id=` 参数
    - 用户反馈"SSE 频繁重连但不恢复" / "页面切回后事件丢失" → 必查三要素完整性
  - **反模式**：
    ```typescript
    // 禁止：SSE 无限重连，无最大重试限制，无 visibilitychange 监听
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：visibilitychange 监听 + last_event_id 回放 + 最大重试 10 次 + 降级轮询
    const MAX_RECONNECT = 10
    let reconnectCount = 0
    const connect = () => {
      const lastEventId = localStorage.getItem('xh_sse_last_event_id') || ''
      const es = new EventSource(`/api/events/stream?last_event_id=${lastEventId}`)
      es.addEventListener('open', () => { reconnectCount = 0 })
      es.addEventListener('error', () => {
        es.close()
        if (reconnectCount >= MAX_RECONNECT) {
          startPollingFallback()  // 降级轮询
          return
        }
        reconnectCount++
        setTimeout(connect, 3000 * reconnectCount)
      })
    }
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        reconnectCount = 0
        connect()
      }
    })
    ```
  - **配置参数**：`coding_standards.sse.max_reconnect_attempts`（默认 `10`，最大重连次数）+ `coding_standards.sse.polling_fallback_interval`（默认 `30`，降级轮询间隔秒数）+ `coding_standards.sse.visibility_reconnect`（默认 `true`，必须监听 visibilitychange）
  - **适用场景**：所有使用 SSE 的实时数据推送（事件流/通知流/状态变更推送）、长连接场景
  - **不适用场景**：WebSocket（有自己的重连机制）、短连接轮询、一次性事件订阅
  - **历史教训**：SSE 连接在网络抖动时无限重连导致服务器压力，且页面切到后台再切回时事件丢失。修复方式：增加最大重试 10 次限制 + visibilitychange 监听 + last_event_id 回放
  - **对应后端原则**：后端 SSE 端点必须支持 `?last_event_id=` 参数启用事件回放，规范源 xianyu-hunter-dev/references/coding-rules.md SSE-01

- 🆕v4.33【强制】**F-REVIEW-ASYNC-RACE-GUARD：异步竞态防护**
  - 维度：10 Hooks 设计模式
  - 严重等级：HIGH
  - **规范引用**：RACE-01 异步竞态防护
  - **检查点**：异步请求是否用 useRef 维护最新请求 ID，响应回来时对比 ID 决定是否更新状态
  - **判定标准**：**禁止**异步请求完成直接更新状态（无请求 ID 对比），**必须**用 useRef 维护最新请求 ID，响应回来时对比 ID，若不一致则丢弃响应（避免旧响应覆盖新响应）
  - **检查范围**：所有异步请求（fetch/axios）触发的状态更新，特别是搜索/筛选/分页等用户可快速连续触发的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "async\\s+function\\s+\\w+[\\s\\S]{0,500}set\\w+\\(.*\\)" frontend/src/**/*.{ts,tsx}` 命中后检查是否有 requestId 对比
    - `grep -nE "useRef\\(.*requestId" frontend/src/**/*.{ts,tsx}` 未命中 → 检查异步请求是否缺少竞态防护
    - 用户反馈"快速切换筛选条件后显示旧数据" / "搜索结果与关键词不匹配" → 必查异步竞态防护
  - **反模式**：
    ```typescript
    // 禁止：异步请求完成直接更新状态，无请求 ID 对比（旧响应可能覆盖新响应）
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：useRef 维护最新请求 ID，响应回来时对比
    const latestRequestId = useRef(0)
    const search = async (keyword: string) => {
      const requestId = ++latestRequestId.current
      const resp = await fetch(`/api/search?keyword=${keyword}`)
      const data = await resp.json()
      if (requestId !== latestRequestId.current) return  // 丢弃过期响应
      setResults(data)
    }
    ```
  - **配置参数**：`coding_standards.race.check_request_id`（默认 `true`，必须用 useRef 维护请求 ID 对比）
  - **适用场景**：用户可快速连续触发的异步请求（搜索/筛选/分页/排序）、并发请求可能返回顺序不一致的场景
  - **不适用场景**：单次提交（如保存/删除，无连续触发）、请求顺序天然保证的场景（如 await 链式调用）
  - **历史教训**：搜索框快速输入时，前一个请求的响应覆盖后一个请求的响应，导致显示与关键词不匹配的结果。修复方式：引入 useRef 维护最新请求 ID
  - **对应后端原则**：无（纯前端竞态防护），规范源 xianyu-hunter-dev/references/coding-rules.md RACE-01

- 🆕v4.33【强制】**F-REVIEW-THEME-DYNAMIC-ADAPT：主题色动态适配**
  - 维度：5 AntD 5 主题规范
  - 严重等级：HIGH
  - **规范引用**：THEME-01 主题色动态适配
  - **检查点**：是否硬编码颜色值、是否根据 isDark 动态设置主题相关 token
  - **判定标准**：**禁止**硬编码颜色值（特别是主题相关 token 如 rowHoverBg/headerBg/headerColor），**必须**根据 isDark 动态设置；显式指定的主题 token 必须在 ThemedRoot 内按 isDark 覆盖（与 v4.8 F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE 配合）
  - **检查范围**：所有 components.<Component>.<token> 配置、内联样式中的颜色值、CSS 变量定义
  - **判断信号**（grep 检测）：
    - `grep -nE "components\\.[A-Z]\\w+\\.\\w*(?:Color|Bg|Border|Hover|Active|Focus)\\s*:\\s*['\"]#[0-9a-fA-F]+['\"]" frontend/src/**/*.{ts,tsx}` 命中 → 违规（硬编码颜色值）
    - `grep -nE "rowHoverBg|headerBg|headerColor" frontend/src/**/*.{ts,tsx}` 命中后检查是否根据 isDark 动态设置
    - 暗色模式下用户反馈"文字看不清"/"背景太亮" → 必查主题色动态适配
  - **反模式**：
    ```typescript
    // 禁止：硬编码 rowHoverBg，暗色模式不可读
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：根据 isDark 动态设置
    const themeConfig = {
      components: {
        Table: {
          rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : '#fff7f0'
        }
      }
    }
    ```
  - **配置参数**：`coding_standards.theme.disallow_hardcoded_colors`（默认 `true`，禁止硬编码主题色）+ `coding_standards.theme.colors.light`（浅色主题色映射）+ `coding_standards.theme.colors.dark`（暗色主题色映射）
  - **适用场景**：所有支持暗色主题的组件、显式指定的主题 token、内联样式中的颜色值
  - **不适用场景**：纯亮色主题应用（无暗色模式）、第三方组件内部样式（无法控制）、品牌固定色（如 logo 颜色）
  - **历史教训**：Table 组件硬编码 `rowHoverBg: '#fff7f0'`，暗色模式下用户无法看清 hover 行。修复方式：改为 `isDark ? 'rgba(255,98,0,0.08)' : '#fff7f0'`
  - **对应后端原则**：无（纯前端主题规范），规范源 xianyu-hunter-dev/references/coding-rules.md THEME-01

- 🆕v4.33【强制】**F-REVIEW-EMBEDDED-LAYOUT-HEIGHT：嵌入式布局高度**
  - 维度：3 React 组件规范
  - 严重等级：HIGH
  - **规范引用**：LAYOUT-01 嵌入式布局高度
  - **检查点**：嵌入框架页面（如 iframe / Electron / 浏览器扩展弹窗）是否用 `height: 100%` + `flex: 1`，禁止 `minHeight: 100vh`
  - **判定标准**：**禁止**在嵌入式场景使用 `minHeight: '100vh'`（会撑满整个视口而非容器，导致全屏溢出）；**必须**使用 `height: '100%'` + `flex: 1` 适配父容器高度
  - **检查范围**：所有页面/布局组件的样式，特别是嵌入 iframe / Electron / 浏览器扩展弹窗的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "minHeight:\\s*['\"]100vh['\"]|minHeight:\\s*['\"]100vh['\"]" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否为嵌入式场景
    - `grep -nE "height:\\s*['\"]100%['\"]" frontend/src/**/*.{ts,tsx}` 未命中 → 检查嵌入式布局是否缺少 height:100%
    - 用户反馈"页面撑满整个浏览器窗口" / "iframe 内出现滚动条" → 必查嵌入式布局高度
  - **反模式**：
    ```typescript
    // 禁止：嵌入 iframe 使用 minHeight: '100vh'，撑满视口导致全屏
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：使用 height: '100%' + flex: 1 适配父容器
    const PageContainer = styled.div`
      height: '100%';
      flex: 1;
      overflow: auto;
    `
    ```
  - **配置参数**：`coding_standards.layout.disallow_minheight_100vh_in_embedded`（默认 `true`，嵌入式场景禁止 minHeight:100vh）
  - **适用场景**：嵌入 iframe / Electron / 浏览器扩展弹窗/桌面应用 webview 的页面布局
  - **不适用场景**：独立网页（非嵌入）、需要撑满视口的落地页/营销页、移动端 H5（视口适配）
  - **历史教训**：闲鱼猎人前端嵌入 iframe 时使用 `minHeight: '100vh'`，导致页面撑满整个浏览器窗口而非 iframe 容器，出现全屏溢出。修复方式：改为 `height: '100%'` + `flex: 1`
  - **对应后端原则**：无（纯前端布局规范），规范源 xianyu-hunter-dev/references/coding-rules.md LAYOUT-01

- 🆕v4.33【强制】**F-REVIEW-COMPONENT-REGISTRY：组件注册完整性**
  - 维度：3 React 组件规范
  - 严重等级：HIGH
  - **规范引用**：REGISTRY-01 组件注册完整性
  - **检查点**：ECharts / antd 等需要 register 的组件是否 import + register，避免使用未注册组件导致静默失败
  - **判定标准**：**禁止**使用未注册的组件（如 ECharts 的 FunnelChart / LineChart / BarChart / PieChart 等）；**必须**在使用前 `import` + `use()` 注册所有用到的组件；组件注册应集中在入口文件（如 `echarts.setup.ts`）
  - **检查范围**：所有 ECharts 组件使用（`<FunnelChart />` / `<LineChart />` 等）、antd 按需加载配置、其他需要 register 的库
  - **判断信号**（grep 检测）：
    - `grep -nE "<(FunnelChart|LineChart|BarChart|PieChart|MapChart|HeatmapChart)" frontend/src/**/*.{ts,tsx}` 命中后检查对应 import + use 注册
    - `grep -nE "echarts\\.(register|use)\\(" frontend/src/**/*.{ts,tsx}` 命中后核对注册的组件列表是否覆盖所有使用
    - 用户反馈"图表不显示"/"组件渲染空白无报错" → 必查组件注册完整性
  - **反模式**：
    ```typescript
    // 禁止：使用 FunnelChart 但未注册，静默失败（图表不显示无报错）
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：import + register 所有用到的组件
    import * as echarts from 'echarts/core'
    import { FunnelChart } from 'echarts/charts'
    import { TooltipComponent, GridComponent } from 'echarts/components'
    import { CanvasRenderer } from 'echarts/renderers'

    echarts.use([FunnelChart, TooltipComponent, GridComponent, CanvasRenderer])
    ```
  - **配置参数**：`coding_standards.registry.check_components`（默认 `[FunnelChart, LineChart, BarChart, PieChart]`，需要检查注册的组件列表）
  - **适用场景**：所有使用 ECharts / antd / Mobx 等需要 register 的库的组件
  - **不适用场景**：使用全量引入（`import * as echarts from 'echarts'`，自动注册所有组件）、不涉及 register 的库
  - **历史教训**：使用 FunnelChart 但未注册，导致图表静默失败（无报错但不显示），用户反馈"图表空白"才定位到问题。修复方式：建立 `echarts.setup.ts` 集中注册所有用到的组件
  - **对应后端原则**：无（纯前端组件注册），规范源 xianyu-hunter-dev/references/coding-rules.md REGISTRY-01

- 🆕v4.33【强制】**F-REVIEW-FILTER-TRANSPARENCY：过滤透明性**
  - 维度：7 API 调用规范
  - 严重等级：MEDIUM
  - **规范引用**：FILTER-02 过滤透明性
  - **检查点**：数据被过滤时是否展示过滤原因和条数，避免用户误以为数据丢失
  - **判定标准**：**禁止**仅显示"获取 N 条"而隐藏过滤过程（实际搜到 M 条被过滤剩 N 条）；**必须**展示过滤原因和条数（如"搜到 59 条，按规则过滤后显示 12 条"），通过 Modal / Tooltip / Alert 展示 `filter_summary`
  - **检查范围**：所有调用后端过滤接口的列表页/搜索页/统计页，特别是显示条数的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "获取\\s*\\d+\\s*条|共\\s*\\d+\\s*条" frontend/src/**/*.{ts,tsx}` 命中后检查是否展示 filter_summary
    - `grep -nE "filter_summary" frontend/src/api/types.ts` 命中后检查前端是否消费该字段
    - 用户反馈"显示获取 0 条但实际有数据" → 必查过滤透明性
  - **反模式**：
    ```typescript
    // 禁止：显示"获取0条"但实际搜到 59 条被过滤，用户误以为数据丢失
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：后端返回 filter_summary，前端用 Modal/Tooltip 展示
    const resp = await fetch('/api/items/search?keyword=xxx')
    const data = await resp.json()
    message.success(`显示 ${data.items.length} 条`)
    if (data.filter_summary) {
      Modal.info({
        title: '过滤结果说明',
        content: `搜到 ${data.filter_summary.total_matched} 条，按规则过滤后显示 ${data.items.length} 条。过滤原因：${data.filter_summary.reason}`
      })
    }
    ```
  - **配置参数**：`coding_standards.filter.summary_enabled`（默认 `true`，必须展示过滤摘要）
  - **适用场景**：所有调用后端过滤接口的列表页/搜索页/统计页、用户可能误解数据完整性的场景
  - **不适用场景**：纯前端过滤（无后端 filter_summary）、无需展示过滤过程的内部统计、数据导出场景
  - **历史教训**：搜索接口显示"获取 0 条"但实际后端搜到 59 条被过滤规则过滤，用户误以为数据丢失。修复方式：后端返回 `filter_summary` 字段，前端用 Modal 展示过滤原因和条数
  - **对应后端原则**：后端必须返回 `filter_summary` 字段（`total_matched` / `total_filtered` / `reason`），规范源 xianyu-hunter-dev/references/coding-rules.md FILTER-02

- 🆕v4.33【强制】**F-REVIEW-DATA-SOURCE-VERIFY：数据源正确性验证**
  - 维度：18 闲鱼项目规范
  - 严重等级：HIGH
  - **规范引用**：SOURCE-01 数据源正确性验证
  - **检查点**：显示数据是否来自正确数据源，避免误用配置备份文件数等错误数据源
  - **判定标准**：**禁止**误用数据源（如版本管理显示配置备份文件数 V10 而非系统版本），**必须**从语义对齐的 API 获取数据（如系统版本从 `/api/about` 获取，而非 `/api/config/version` 返回的 `len(backups)`）
  - **检查范围**：所有显示版本/计数/统计数据的组件，特别是从多个 API 获取类似字段的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "version\\s*[:=]" frontend/src/**/*.{ts,tsx}` 命中后检查数据源是否为 `/api/about`
    - `grep -nE "/api/config/version" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否误用（该接口返回 len(backups)）
    - 用户反馈"版本号显示为 V10 而非实际版本" → 必查数据源正确性
  - **反模式**：
    ```typescript
    // 禁止：版本管理显示 V10（配置备份文件数而非系统版本）
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：从 /api/about 获取系统版本
    const resp = await fetch('/api/about')
    const data = await resp.json()
    setVersion(data.version)  // 系统版本号
    ```
  - **配置参数**：`coding_standards.source.verify_data_source`（默认 `true`，必须验证数据源语义正确性）
  - **适用场景**：所有显示版本/计数/统计数据的场景、从多个 API 获取类似字段的场景、数据源语义可能混淆的场景
  - **不适用场景**：单一明确数据源、内部计数（无歧义）、测试 mock 数据
  - **历史教训**：版本管理页显示 V10，用户以为是系统版本，实际是配置备份文件数。修复方式：从 `/api/about` 获取系统版本，废弃 `/api/config/version` 误用
  - **对应后端原则**：后端 `/api/about` 必须返回系统版本字段，规范源 xianyu-hunter-dev/references/coding-rules.md SOURCE-01（与 v4.20 F-REVIEW-VERSION-SOURCE-ALIGN 配合）

- 🆕v4.33【强制】**F-REVIEW-STATS-RANGE-CALIBRATE：统计范围校准**
  - 维度：16 性能评审
  - 严重等级：MEDIUM
  - **规范引用**：RANGE-01 统计范围校准（前端）
  - **检查点**：统计图表范围是否与业务范围匹配，避免统计范围过大导致图表不可读或误导
  - **判定标准**：**禁止**统计图表范围过大与业务范围不匹配（如价格直方图统计 0-10000 但任务定价范围仅 0-500），**必须**按业务范围过滤（task_id 过滤）+ 百分位校准（P5/P95）确保图表聚焦业务实际范围
  - **检查范围**：所有统计图表（直方图/折线图/散点图），特别是显示价格/数量/频率等业务指标的图表
  - **判断信号**（grep 检测）：
    - `grep -nE "type:\\s*['\"](histogram|line|scatter)" frontend/src/**/*.{ts,tsx}` 命中后检查统计范围是否与业务范围匹配
    - `grep -nE "min:\\s*\\d+.*max:\\s*\\d+" frontend/src/**/*.{ts,tsx}` 命中后检查 min/max 是否经过业务校准
    - 用户反馈"图表大部分是空白"/"数据集中在角落" → 必查统计范围校准
  - **反模式**：
    ```typescript
    // 禁止：价格直方图统计范围 0-10000，与任务定价范围 0-500 不匹配
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：task_id 过滤 + P5/P95 百分位校准
    const taskPrices = prices.filter(p => p.task_id === currentTaskId)
    const sorted = [...taskPrices].sort((a, b) => a.price - b.price)
    const p5 = sorted[Math.floor(sorted.length * 0.05)].price
    const p95 = sorted[Math.floor(sorted.length * 0.95)].price
    const option = {
      xAxis: { min: p5, max: p95 },  // 聚焦业务实际范围
      series: [{ type: 'histogram', data: taskPrices }]
    }
    ```
  - **配置参数**：无（纯业务逻辑校准，配置驱动通过 checklist.performance 开关）
  - **适用场景**：所有统计图表（直方图/折线图/散点图）、显示业务指标的图表、数据范围可能过大误导决策的场景
  - **不适用场景**：全量数据展示（无范围限制需求）、固定范围仪表盘、实时监控图表（范围动态）
  - **历史教训**：价格直方图统计范围 0-10000，但任务定价范围仅 0-500，导致图表大部分空白，用户无法看清分布。修复方式：task_id 过滤 + P5/P95 百分位校准聚焦业务范围
  - **对应后端原则**：无（纯前端图表校准），规范源 xianyu-hunter-dev/references/coding-rules.md RANGE-01

- 🆕v4.33【强制】**F-REVIEW-UI-SEMANTICS-SPLIT：按钮与状态语义分离**
  - 维度：3 React 组件规范
  - 严重等级：MEDIUM
  - **规范引用**：UI-SEMANTICS-01 按钮与状态语义分离
  - **检查点**：按钮文案是否表达动作（动词）、状态显示是否表达状态（名词/形容词），避免用户误解
  - **判定标准**：**禁止**按钮文案与状态显示混用（如红色"失效"既是按钮文案又是状态显示，用户无法判断是点击失效还是已失效），**必须**按钮文案表达动作（如"主动失效"/"批量失效"），状态显示表达状态（如"有效"/"已失效"）
  - **检查范围**：所有按钮文案、状态标签/徽章、操作列按钮
  - **判断信号**（grep 检测）：
    - `grep -nE "<Button[^>]*>[^<]*(失效|有效|启用|禁用)" frontend/src/**/*.{ts,tsx}` 命中后检查文案是动作还是状态
    - `grep -nE "<Tag[^>]*>[^<]*(失效|有效|启用|禁用)" frontend/src/**/*.{ts,tsx}` 命中后检查是否与按钮文案混用
    - 用户反馈"误点了失效按钮以为是状态显示" → 必查按钮与状态语义分离
  - **反模式**：
    ```typescript
    // 禁止：红色"失效"是按钮而非状态显示，用户误判
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：按钮文案表达动作（主动失效），状态显示表达状态（有效/已失效）
    <Space>
      {record.status === 'active'
        ? <Button danger onClick={handleDisable}>主动失效</Button>
        : <Tag color="default">已失效</Tag>}
    </Space>
    ```
  - **配置参数**：`coding_standards.ui_semantics.button_text_must_be_action`（默认 `true`，按钮文案必须是动作）+ `coding_standards.ui_semantics.status_display_must_be_state`（默认 `true`，状态显示必须是状态）
  - **适用场景**：所有按钮文案、状态标签/徽章、操作列按钮、状态切换控件
  - **不适用场景**：图标按钮（无文案）、纯导航按钮（如"返回"）、确认对话框按钮（如"确定"/"取消"）
  - **历史教训**：列表操作列红色"失效"按钮被用户误以为是状态标签，导致误点击。修复方式：按钮文案改为"主动失效"，状态用 Tag 显示"已失效"
  - **对应后端原则**：无（纯前端 UI 语义），规范源 xianyu-hunter-dev/references/coding-rules.md UI-SEMANTICS-01

- 🆕v4.33【强制】**F-REVIEW-PERSIST-BUSINESS-SWITCH：用户可配置开关持久化**
  - 维度：10 Hooks 设计模式
  - 严重等级：HIGH
  - **规范引用**：PERSIST-01 用户可配置开关持久化
  - **检查点**：业务开关（如自动刷新/批量启用/调试模式）是否用 `usePersistentState` 持久化，避免刷新丢失
  - **判定标准**：**禁止**业务开关用 `useState`（刷新后丢失用户配置），**必须**用 `usePersistentState`（localStorage 持久化）；持久化 key 必须遵循 `xh.<page>.<field>` 命名模式（与 v4.24 F-REVIEW-UI-PREFERENCE-PERSISTENCE 配合）
  - **检查范围**：所有业务开关（自动刷新/批量启用/调试模式/高级筛选/暗色模式等用户可配置的布尔/枚举状态）
  - **判断信号**（grep 检测）：
    - `grep -nE "const\\s+\\[\\s*(autoRefresh|batchEnabled|debugMode|advancedFilter|darkMode)\\s*,\\s*\\w+\\]\\s*=\\s*useState" frontend/src/**/*.{ts,tsx}` 命中 → 违规
    - `grep -nE "usePersistentState\\(\\s*['\"]xh\\." frontend/src/**/*.{ts,tsx}` 未命中 → 检查业务开关是否缺少持久化
    - 用户反馈"刷新后开关重置为默认值" → 必查业务开关持久化
  - **反模式**：
    ```typescript
    // 禁止：业务开关用 useState，刷新丢失
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：业务开关用 usePersistentState（localStorage 持久化）
    const [autoRefresh, setAutoRefresh] = usePersistentState<boolean>(
      'xh.dashboard.autoRefresh',
      false,
      { validator: (v) => typeof v === 'boolean' }
    )
    ```
  - **配置参数**：`coding_standards.persist.business_switch_must_persist`（默认 `true`，业务开关必须持久化）+ `coding_standards.persist.storage_key_prefix`（默认 `xh.`，持久化 key 前缀）
  - **适用场景**：所有业务开关（自动刷新/批量启用/调试模式/高级筛选/暗色模式等用户可配置状态）
  - **不适用场景**：临时状态（如 loading/visible）、会话状态（如 currentStep）、敏感数据（如 token）、后端已持久化的字段（应从后端获取）
  - **历史教训**：批量刷新的自动刷新开关用 useState，用户刷新页面后开关重置为 false，导致用户需要重新开启。修复方式：改用 usePersistentState 持久化到 localStorage
  - **对应后端原则**：无（纯前端持久化），规范源 xianyu-hunter-dev/references/coding-rules.md PERSIST-01

- 🆕v4.33【强制】**F-REVIEW-ERROR-MESSAGE-PASS：错误消息透传**
  - 维度：20 API 数据源一致性与类型契约对齐
  - 严重等级：MEDIUM
  - **规范引用**：ERROR-01 错误消息透传（前端）
  - **检查点**：catch 块是否用 `extractApiError` 提取后端具体错误，避免显示无信息的通用错误
  - **判定标准**：**禁止**catch 块显示无信息的通用错误（如 `message.error('预览失败')`），**必须**用 `extractApiError` 提取后端具体错误（如 `message.error(extractApiError(err, '预览失败'))`），让用户看到后端根因
  - **检查范围**：所有 API 调用的 catch 块，特别是显示错误提示的场景
  - **判断信号**（grep 检测）：
    - `grep -nE "catch\\s*\\([^)]*\\)\\s*\\{[^}]*message\\.error\\(['\"][^'\"]*失败['\"]" frontend/src/**/*.{ts,tsx}` 命中 → 违规（无具体错误）
    - `grep -nE "extractApiError" frontend/src/**/*.{ts,tsx}` 未命中 → 检查 catch 块是否缺少错误透传
    - 用户反馈"只显示保存失败，不知道具体原因" → 必查错误消息透传
  - **反模式**：
    ```typescript
    // 禁止：catch 块显示无具体错误的通用提示
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：用 extractApiError 提取后端具体错误
    try {
      await previewFile(id)
    } catch (err) {
      message.error(extractApiError(err, '预览失败'))
      // 显示如："预览失败：文件不存在"或"预览失败：权限不足"
    }
    ```
  - **配置参数**：`coding_standards.error.require_extract_api_error`（默认 `true`，catch 块必须用 extractApiError）
  - **适用场景**：所有 API 调用的 catch 块、显示错误提示的场景、用户需要知道错误根因的操作
  - **不适用场景**：纯前端错误（如表单校验）、网络层错误（无后端响应）、测试 mock
  - **历史教训**：文件预览失败时只显示"预览失败"，用户不知道是文件不存在还是权限不足，无法定位问题。修复方式：用 `extractApiError` 提取后端具体错误透传给用户
  - **对应后端原则**：后端必须返回结构化错误响应（`error_code` + `message` 字段）（与 v4.27 F-REVIEW-ERROR-CODE-BRANCH 配合），规范源 xianyu-hunter-dev/references/coding-rules.md ERROR-01

- 🆕v4.33【强制】**F-REVIEW-API-CONTRACT-CONSISTENCY：API 契约一致性**
  - 维度：11 类型安全评审
  - 严重等级：HIGH
  - **规范引用**：CONTRACT-01 API 契约一致性（前端）
  - **检查点**：TS interface 字段名是否与后端 response_model 一致，避免大小写/命名风格不一致导致数据显示为 0/undefined
  - **判定标准**：**禁止**TS interface 字段名与后端 response_model 不一致（如后端返回 `total`，前端期望 `total_for_type`），**必须**TS interface 字段名与后端 response_model 完全一致（snake_case 对齐 snake_case）；可选字段用 `field?: T`，可空字段用 `field: T | null`
  - **检查范围**：所有 `frontend/src/api/types.ts` 中的 interface/type 定义，与后端 Pydantic model 的字段名对比
  - **判断信号**（grep 检测）：
    - `grep -nE "interface\\s+\\w+[\\s\\S]{0,500}?\\s+\\w+:\\s" frontend/src/api/types.ts` 命中后与后端 model 对比字段名
    - `grep -nE "as\\s+any\\b|as\\s+unknown\\s+as" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否绕过类型检查掩盖契约不一致
    - 用户反馈"显示 0 条"/"字段显示 undefined" → 必查 API 契约一致性
  - **反模式**：
    ```typescript
    // 禁止：后端返回 total，前端期望 total_for_type，导致显示 0 条
    ```
  - **修复模式**：
    ```typescript
    // ✅ 正确：TS interface 字段名与后端 response_model 完全一致
    interface EvaluationResult {
      total: number  // 与后端 Pydantic model 字段名一致
      total_for_type?: number  // 可选字段用 ?，可空字段用 | null
    }
    ```
  - **配置参数**：`coding_standards.contract.check_ts_interface_match`（默认 `true`，必须检查 TS interface 与后端 model 一致性）
  - **适用场景**：所有 API 响应类型定义、前后端字段契约对齐、类型安全检查
  - **不适用场景**：纯前端内部类型（无后端对应）、第三方 API 类型（按第三方文档）、归一化层类型（前后端字段映射）
  - **历史教训**：评估明细页后端返回 `total`，前端 TS interface 期望 `total_for_type`，导致显示 0 条。修复方式：TS interface 字段名与后端 response_model 完全一致
  - **对应后端原则**：后端 Pydantic model 字段名必须稳定，新增字段需同步前端 types.ts（与 v4.16 F-REVIEW-TYPE-CONTRACT-ALIGN 配合），规范源 xianyu-hunter-dev/references/coding-rules.md CONTRACT-01
