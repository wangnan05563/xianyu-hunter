# 3. React 组件规范 🆕v2.0

- 【强制】使用 `function` 关键字定义组件（**禁止**箭头函数）
- 【强制】Props 用 `type` 关键字定义（**禁止** `interface`，项目规范）
- 【强制】Hooks 调用顺序：所有 hooks 必须在条件/return 之前调用（避免 React Hooks 规则违规）
- 【强制】双层 ErrorBoundary 容错：`LazyErrorBoundary` + `Suspense`
- 【强制】路由切换用 `requestAnimationFrame` 重置滚动位置
- 【强制】**容器适配**：被嵌入到 SheetWorkspace/MainLayout 等固定高度容器的页面组件，用 `height: 100%` 适应父容器
- 【禁止】在嵌入场景使用 `minHeight: 100vh` 或 `height: 100vh`（溢出容器导致全屏问题）
- 【强制】flex 布局：Header 设 `flex: '0 0 auto'`，Content 设 `flex: 1` + `overflow: auto`
- 【推荐】独立路由页面（未进 MainLayout，如 `/login`）可用 `100vh`
- 🆕v4.0【强制】**多视图 state 提升**：Tab/Accordion/Collapse/Drawer 多视图共享同一数据源时，state 必须提升至最近共同父组件
- 🆕v4.0【强制】`destroyInactiveTabPane={false}` 保留 DOM（表单类避免输入焦点丢失）
- 🆕v4.0【强制】标题职责归容器（如 Tab label），子组件只保留功能说明文字，禁止标题重复
  - **判断信号**：两个子组件的 props 来自同一 config/state → 应提升
- 🆕v4.2【强制】**F-REVIEW-UI-STATE-INDEPENDENCE：UI 状态独立性原则**
  - 受控 UI 状态（`openKeys`/`expandedKeys`/`activeKey`/`Drawer open` 等）不应通过 `useEffect` 联动路由变化（`location.pathname`/`useNavigate`）
  - 路由变化只应更新**派生状态**：`selectedKeys`（高亮当前项）、breadcrumb（面包屑）、页面标题
  - **判断信号**：代码含 `useEffect(() => setOpenKeys(...), [autoOpenKeys])` 或 `useEffect(() => setExpandedKeys(...), [location.pathname])` → 视为违规
  - **修复模式**：`openKeys` 仅在首次挂载时按当前路由初始化（`useState(() => autoOpenKeys)`），之后完全由用户通过 `onOpenChange` 控制，移除 `useEffect` 联动
  - **适用**：Menu `openKeys`、Tree `expandedKeys`、Collapse `activeKey`、Tabs `activeKey`、Drawer `open` 等用户手动控制的 UI 状态
  - **不适用**：`selectedKeys`（应联动路由高亮）、breadcrumb（应联动路由）、页面标题（应联动路由）
  - **历史教训**：MainLayout 的 `openKeys` 通过 `useEffect` 联动 `autoOpenKeys`，sheet 切换触发 `navigate` → URL 变化 → `autoOpenKeys` 重算 → `setOpenKeys` 重置 → SubMenu 展开/折叠动画遮挡内容。第一次修复用"合并"策略仍会展开所有 SubMenu，最终改为完全移除 `useEffect` 联动才彻底解决

```typescript
// ✅ 推荐：function 关键字 + type Props
type MainLayoutProps = {
  children: React.ReactNode
}

function MainLayout({ children }: MainLayoutProps) {
  return (
    <ConfigProvider>
      <LayoutContent />
    </ConfigProvider>
  )
}
```

```typescript
// ✅ 推荐：双层 ErrorBoundary + Suspense
const LazyRoute = ({ children }) => (
  <LazyErrorBoundary>
    <Suspense fallback={<Spin />}>
      {children}
    </Suspense>
  </LazyErrorBoundary>
)
```

- 🆕v4.11【强制】**F-REVIEW-STATE-MACHINE-UI：状态机 UI 视觉标识完整性**
  - 业务对象有状态字段（如 `task.status` / `session.state` / `order.status`）时，每个状态值必须有对应的 UI 视觉标识：颜色 Tag / 图标 / 文案 / 操作按钮。**禁止**终态显示"进行中"类动画，中间态必须有 loading 反馈
  - **核心机制**（审查时必须理解）：
    - 后端状态机有白名单转换规则（B-REVIEW-STATE-MACHINE-WHITELIST），前端 UI 必须为每个状态值提供明确的视觉标识
    - 终态（`completed` / `failed` / `cancelled`）禁止显示 loading 动画或"进行中"文案，应显示最终结果的静态标识（成功/失败/已取消）
    - 中间态（`pending` / `running` / `processing`）必须有 loading 反馈（Spin / 进度条 / 动画图标），让用户感知任务正在进行
    - 状态对应的操作按钮必须与状态机白名单转换一致（如 `running` 状态显示"暂停"按钮，`paused` 状态显示"恢复"按钮，`completed` 状态不显示任何操作按钮）
  - **判断信号**：
    - `grep "status" frontend/src/` 发现状态值但无对应 Tag/图标/文案映射 → 视为违规
    - 终态状态（`completed`/`failed`/`cancelled`）仍显示 loading 动画 → 视为违规
    - 中间态状态（`pending`/`running`）无 loading 反馈 → 视为违规
    - 操作按钮与状态机白名单不一致（如 `completed` 状态仍显示"暂停"按钮）→ 视为违规
    - 后端新增状态值但前端 UI 无对应视觉标识 → 视为违规
  - **修复模式**（状态→视觉标识映射表 + 操作按钮白名单）：
    ```typescript
    // ✅ 状态视觉标识映射表（集中管理）
    const TASK_STATUS_UI: Record<TaskStatus, { color: string; text: string; icon: ReactNode; loading: boolean }> = {
      pending: { color: 'default', text: '待开始', icon: <ClockCircleOutlined />, loading: false },
      running: { color: 'processing', text: '运行中', icon: <LoadingOutlined />, loading: true },
      paused: { color: 'warning', text: '已暂停', icon: <PauseCircleOutlined />, loading: false },
      completed: { color: 'success', text: '已完成', icon: <CheckCircleOutlined />, loading: false },
      failed: { color: 'error', text: '已失败', icon: <CloseCircleOutlined />, loading: false },
    }
    // ✅ 操作按钮白名单（与后端状态机 TRANSITIONS 一致）
    const TASK_ACTIONS: Partial<Record<TaskStatus, Action[]>> = {
      pending: [{ key: 'start', label: '开始' }],
      running: [{ key: 'pause', label: '暂停' }],
      paused: [{ key: 'resume', label: '恢复' }, { key: 'stop', label: '停止' }],
      // completed / failed 无操作按钮（终态不可复活）
    }
    // 消费端：
    const ui = TASK_STATUS_UI[task.status]
    <Tag color={ui.color} icon={ui.icon}>{ui.text}</Tag>
    {ui.loading && <Spin size="small" />}
    {TASK_ACTIONS[task.status]?.map(a => <Button key={a.key} onClick={() => handleAction(a.key)}>{a.label}</Button>)}
    ```
  - **配置参数**：`status_ui_mapping`（状态→视觉标识映射表，含 color/text/icon/loading 字段）、`terminal_states`（终态列表，默认 `['completed', 'failed', 'cancelled']`，禁止 loading 动画）、`intermediate_states`（中间态列表，默认 `['pending', 'running', 'processing']`，必须有 loading 反馈）、`action_whitelist`（状态→允许的操作按钮白名单，与后端 TRANSITIONS 一致）在 `config.yaml` 的 `state_machine_ui` 节点管理
  - **适用**：所有有状态字段的业务对象（任务/会话/订单/评估）；后端有状态机白名单转换的场景
  - **不适用**：纯前端 UI 状态（如 `loading` / `open` / `active`）；无状态机的 CRUD 实体；状态值不展示给用户的内部状态
  - **历史教训**：任务状态 `completed` 仍显示 loading 动画（因为前端 `TASK_STATUS_UI` 映射表未区分终态与中间态），用户以为任务还在运行反复刷新页面。且 `failed` 状态仍显示"暂停"按钮（操作按钮未与后端状态机白名单一致），用户点击后后端返回 400 错误。修复后映射表区分终态/中间态 + 操作按钮按白名单显示

- 🆕v4.16【强制】**F-REVIEW-STATE-FUNCTIONAL-ALIGN：状态显示与功能可用性一致**
  - 前端 UI 显示的功能/会话/服务状态（如 Cookie 层状态：`identity` / `session` / `tracking` 是否失效；服务可用性：SSE 连接、API 健康度、采集器运行状态）必须与功能实际可用性保持一致；**禁止**仅依据后端返回的"初始值"或"短期缓存"判定 UI 状态显示为"失效/异常"
  - **核心机制**（审查时必须理解）：
    - 后端"功能信号"字段（如 `last_session_invalid` / `is_healthy` / `is_connected`）的初始值（默认 `False`）表示"未检测"，**不能**被解读为"功能正常"
    - 后端"功能信号"必须配合"已发生过检测"标记（首次成功时间戳 `_last_check_at > 0`、计数器 `use_count > 0`、首次成功标记 `_has_run`）才具备"已检测"语义
    - 前端 UI 状态显示"有效/正常"前必须先确认"已发生过真实调用且成功"，**禁止**仅看后端初始 `False` 就误判为"正常"或显示绿色有效标识
    - 跨进程/跨模块场景下，子进程已检测成功的状态变更必须通过 SSE / 状态广播实时同步到前端，**禁止**前端用 30s TTL 缓存兜底（子进程状态变更后 30 秒内前端仍显示旧状态）
  - **判断信号**：
    - `grep "state === 'valid'\\|state === 'normal'\\|state === 'healthy'" frontend/src/` 出现不配合"已检测"标记的硬编码布尔判定 → 视为违规
    - `grep "sessionInvalid\\|isInvalid\\|isExpired" frontend/src/` 仅依据后端单次返回值更新 UI 状态（无首次成功时间戳、计数器辅助）→ 视为违规
    - UI 状态显示组件（如 `<StatusTag>` / `<LayerStatusBadge>`）的 props 来自未校验的布尔字段（如 `valid` 默认 `false`）→ 视为可疑
    - 跨进程状态同步依赖 `setInterval` 轮询（30s/60s TTL）而未使用 SSE 推送 → 视为可疑（同步不及时）
  - **修复模式**：
    ```typescript
    // ✅ 后端 types.ts 显式区分"未检测" / "已检测有效" / "已检测无效"
    // 与后端 xianyu-backend-code-review v4.15.0 的 B-REVIEW-STATE-DETECTION-BOOTSTRAP 对齐
    export type LayerStatus =
      | 'unknown'      // 初始未检测（前端必须显示灰色/未检测，不显示"失效"）
      | 'valid'        // 已检测且有效
      | 'invalid'      // 已检测且失效
      | 'stale'        // 已检测但超时（last_check_threshold_seconds）

    // ✅ 接收后端"已检测"标记
    interface LayerState {
      status: LayerStatus
      lastCheckedAt: number    // 0 = 未检测
      useCount: number         // 0 = 未检测
      lastError?: string
    }

    // ✅ UI 渲染：仅在 lastCheckedAt > 0 时才显示"已检测"状态
    function LayerStatusBadge({ state }: { state: LayerState }) {
      if (state.lastCheckedAt === 0 && state.useCount === 0) {
        return <Tag color="default">未检测</Tag>   // 必须明确区分"未检测"与"已失效"
      }
      if (state.status === 'valid') {
        return <Tag color="success">有效</Tag>
      }
      if (state.status === 'invalid') {
        return <Tag color="error">失效</Tag>
      }
      if (state.status === 'stale') {
        return <Tag color="warning">检测超时</Tag>
      }
      return <Tag color="default">未知</Tag>
    }

    // 禁止：仅依据布尔 initial=false 判定"有效"（刚启动时 valid=false 被解读为"失效"，但实际语义是"未检测"）
    ```
  - **配置参数**：
    - `state_functional_align.required_check_marker`：默认 `true`，必须有"已检测"标记（`lastCheckedAt > 0` / `useCount > 0` / `hasRun` 至少一个）
    - `state_functional_align.unknown_status_display`：默认 `'未检测'`，未检测状态的 UI 文案
    - `state_functional_align.sse_push_required`：默认 `true`，跨进程状态变更必须 SSE 推送（禁止 TTL 兜底）
    - `state_functional_align.ttl_grace_seconds`：默认 `0`，跨进程同步的 TTL 兜底秒数，0 即不依赖 TTL
    - `state_functional_align.stale_threshold_seconds`：默认 `3600`，已检测状态超过该秒数视为 `stale`（检测超时）
    - `state_functional_align.status_field_mapping`：状态字段到判定逻辑的映射（如 `cookie_layer → {required: ['lastCheckedAt', 'useCount'], initialValue: 'unknown'}`）
    - `state_functional_align.status_color_mapping`：状态值到 UI 颜色/文案的映射（如 `{valid: 'success', invalid: 'error', unknown: 'default', stale: 'warning'}`）
    在 `config.yaml` 的 `state_functional_align` 节点管理
  - **适用**：所有功能/会话/服务状态显示（Cookie 层有效性 / SSE 连接状态 / API 健康度 / 采集器运行状态 / 第三方服务可达性 / 任务调度器状态）；跨进程/跨模块状态同步（子进程→主进程→前端）；状态自愈（容器健康检查、服务可用性兜底）
  - **不适用**：纯前端 UI 状态（如 `loading` / `open` / `active` 开关）；单次函数返回值（无状态延续语义）；无初始歧义的纯布尔开关（如 `enableNotification: boolean`）；后端已用布尔 `True/False` 明确表达"有效/失效"且前端仅做展示映射的场景
  - **历史教训**：用户反馈实时查询、官方采集均能正常运行，但反爬登录管理页的 `identity` / `session` / `tracking` 状态持续显示为失效（红 X 标签），根因：后端 `CookieStore` 用 30s TTL 兜底缓存子进程状态，浏览器子进程登录后只更新子进程自己的内存缓存，主进程读时仍取到 TTL 内的"失效"状态（30 秒后才自动恢复），同时前端 `LayerStatusBadge` 仅依赖 `valid: boolean` 显示（无"未检测"区分），导致用户看到"功能可用但状态持续失效"长达 30 秒，体感"明明能跑却一直报红"。修复后三层：①后端 `sync_cookie_layers_from_json()` 显式调用 `invalidate_cache()`（B-REVIEW-CACHE-INVALIDATION）②后端 `collector.last_session_invalid=False` 仅在 `_last_m5tk_refresh > 0` 时才恢复所有层（B-REVIEW-STATE-DETECTION-BOOTSTRAP）③前端 `LayerStatusBadge` 区分 `unknown` / `valid` / `invalid` / `stale` 四态，无"已检测"标记时显示灰色"未检测"而非"失效"
