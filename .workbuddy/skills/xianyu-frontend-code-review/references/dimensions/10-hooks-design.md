# 10. Hooks 设计模式 🆕v2.0

- 【强制】常量提取到模块级（SonarQube S2004）：`MIN_INTERVAL`、`MAX_INTERVAL`、`DEFAULT_INTERVAL`、`MAX_RETRIES`、`RETRY_BASE_MS`、`DEBOUNCE_MS`、`BACKGROUND_SLOWDOWN`
- 【强制】`ref` 持有最新闭包（避免 setInterval 陷阱）：`refreshRef`、`enabledRef`、`pausedRef`、`intervalRef`、`scheduleNextRef`
- 【强制】页面不可见降频：×1（`BACKGROUND_SLOWDOWN`）
- 【强制】防抖：300/400/500ms（按场景）
- 【强制】`requestId` 竞态保护：每次请求生成 requestId，丢弃过期响应
- 🆕v4.0【强制】**搜索场景防抖间隔统一 400ms**（通过配置管理，非硬编码）
- 🆕v4.0【强制】**搜索响应结构统一**：`{ items, total, page, page_size }`，参数命名 `keyword/q, page/offset, page_size/limit`
- 【强制】`mountedRef` 防止卸载后 setState
- 【强制】`refreshingRef` 并发保护
- 【强制】`async/await` 与 `.then().catch()` 错误处理；禁止遗忘 `this` 上下文绑定
- 【强制】每个异步请求有错误处理分支
- 【强制】提交按钮异步期间设 `loading`/`disabled` 防重复提交
- 【强制】**测试环境准备**：antd 组件（Drawer/Grid/Skeleton）测试必须 mock `window.matchMedia`
- 【强制】vitest 测试命令必须加 `--no-isolate`（Node v24 + vitest 4.x worker 启动兼容性）
- 【强制】测试文件扩展名跟随被测文件：组件测试用 `.test.tsx`，Hook/纯逻辑用 `.test.ts`
- 【强制】全局事件监听（`visibilitychange`、`resize`、`scroll` 等）必须在 useEffect 中注册，并在 cleanup 中移除
- 【强制】`visibilitychange` 监听用于：页面不可见时暂停网络连接（SSE/WebSocket），恢复可见时自动重连
- 【推荐】useEffect 中同时管理 SSE 连接和 visibilitychange 监听，确保两者生命周期一致

- 🆕v4.7【强制】**F-REVIEW-ASYNC-FEEDBACK：异步操作用户反馈三态**
  - 前端异步操作（API 请求、文件上传、批量操作）必须实现 loading → success → error 三态用户反馈，**禁止** `.catch(() => {})` 静默吞错误
  - **判断信号**：`await fetch(...)` / `await axios(...)` / `useEffect` 中的异步操作 → 检查是否有 `message.loading` / `setLoading(true)` → 检查成功分支是否有 `message.success` → 检查 catch 分支是否有 `message.error` / `notification.error`
  - **修复模式**（三态反馈标准模式）：
    ```typescript
    // ✅ 标准三态反馈模式
    const hide = message.loading('正在采集评估明细...', 0)
    try {
      const result = await fetchEvaluationDetail(itemIds)
      hide()
      message.success(`采集完成，共 ${result.length} 条`)
      setData(result)
    } catch (err) {
      hide()
      message.error(err instanceof Error ? err.message : '采集失败，请稍后重试')
      // 错误状态必须显式设置，不能只靠 catch 不做任何事
      setError(err instanceof Error ? err.message : '未知错误')
    }
    ```
  - **禁止模式**：
    ```typescript
    // 禁止：静默吞错误

    // 禁止：只有 loading 没有 success/error 反馈
    ```
  - **配置参数**：`loading_duration`（loading 提示展示时长，默认 0 表示持续到手动关闭）、`success_auto_hide_ms`（成功提示自动关闭时长，默认 3000）、`error_auto_hide_ms`（错误提示自动关闭时长，默认 5000）、`feedback_components`（反馈组件映射，默认 `message`）在 `config.yaml` 的 `async_feedback` 节点管理
  - **关键约束**：
    - loading 提示必须在 await 之前触发，在 finally 或 success/error 分支中关闭
    - 错误信息必须面向用户友好（避免堆栈跟踪、错误码直接展示）
    - 批量操作必须显示进度（如"3/10 完成"）
    - 网络错误与业务错误区分显示（网络错误提示"网络异常"，业务错误显示后端返回的 detail）
  - **适用**：所有前端异步操作（API 请求、文件上传、批量操作、长时间计算）
  - **不适用**：后台同步任务（如 SSE 心跳、定时轮询）、纯展示组件的初始数据加载（可用 Skeleton 占位）
  - **历史教训**：评估明细采集按钮点击后无任何反馈，用户不知道是否在执行；采集失败后页面无变化，用户反复点击导致多次请求。修复后改为 `message.loading` → `message.success/error` 三态反馈

- 🆕v4.9【强制】**F-REVIEW-FREQ-STATS-POLLING：累计统计类 API 定时刷新**
  - 累计统计类 API（频率伪装统计 / 采样量 / 计数 / 令牌桶 / 健康评分 —— 内部状态持续累加的接口）必须在前端页面通过 `setInterval` **定时刷新**，**禁止**只依赖页面加载时拉一次。定时器间隔、清理策略、失败兜底必须在 `config.yaml` 的 `freq_stats_polling` 节点管理，不硬编码
  - **核心机制**（审查时必须理解）：
    - 业务模块（collector / buyer / notifier 等）持续调用后端核心模块（如 `FreqDisguise.record_request`）累加统计
    - 前端 `useEffect` 初始化时 `fetch` 一次，拿到的是某个时刻的快照
    - 用户停留在页面期间，后端统计持续累加，UI 永远停留在初始值（甚至永远是 0）
    - 表现：用户反馈"统计数据持续为 0 且无变化"，但后端 API 与业务调用方均正常
  - **判断信号**：
    - `grep "loadFreqStats\|loadStats\|fetchStats" <page>.tsx` 发现页面有加载函数
    - `grep "setInterval" <page>.tsx` **没有**对应的 `setInterval` 定时器
    - 累计统计类 API 名称含 `stats` / `metrics` / `count` / `health_score` / `token_bucket` 等关键词
    - 后端核心模块（如 `FreqDisguise` / `MetricsCollector` / `Sampler`）有 `_total_count` / `_history` 等内部状态
  - **修复模式**（在页面 useEffect 中加 `setInterval` + 清理）：
    ```typescript
    useEffect(() => {
      loadAll()
      // 频率伪装统计定时刷新：业务模块持续调用 apply_freq_delay/record_freq_request，
      // 前端需定时拉取才能反映最新请求节奏
      const freqInterval = setInterval(() => {
        loadFreqStats()
      }, POLL_INTERVALS.freqStats)  // 10000ms 来自 config.yaml
      return () => {
        clearInterval(freqInterval)  // 卸载时必须清理
      }
    }, [loadAll])
    ```
  - **关键约束**：
    - **必须清理定时器**：`useEffect` cleanup 中 `clearInterval`，避免组件卸载后定时器仍触发 `setState`（内存泄漏 + 警告）
    - **间隔配置化**：`10000` / `30000` 等间隔值必须来自 `config.yaml` 的 `freq_stats_polling.interval_ms` 或 `POLL_INTERVALS` 常量，禁止在组件内硬编码数字
    - **轮询失败静默**：累计统计轮询失败应 `console.error` 而非 `message.error`（避免用户被频繁弹窗骚扰）
    - **可独立刷新**：每个累计统计 API 可独立设置 `setInterval`，无需等待 `loadAll()`
  - **配置参数**：`enabled`（默认 `true`）、`interval_ms`（默认 `10000`）、`slow_interval_ms`（变化缓慢的统计如 Cookie 层，默认 `30000`）、`fail_silent`（轮询失败是否仅 console 不弹错，默认 `true`）、`applicable_pages`（适用页面列表如 `AntiCrawl` / `Dashboard`）、`exempt_apis`（豁免的 API 列表如已有 SSE 推送的接口）在 `config.yaml` 的 `freq_stats_polling` 节点管理
  - **诊断流程**（用户反馈"统计数据持续为 0 且无变化"时执行）：
    1. 定位页面对应的 `loadXxx` 函数 → 检查页面 useEffect 是否调用了 `loadAll()` 初始化
    2. `grep "setInterval" <page>.tsx` 检查是否有定时刷新
    3. 若无 → 判定为孤岛（前端未轮询）→ 按修复模式增加 `setInterval`
    4. 验证后端 API 端点是否被业务模块持续调用（`grep "apply_freq_delay\|record_request"` 后端）
    5. 三层验证：API 端点存在 → 业务模块调用 → 前端轮询 → 数据应开始累加
  - **适用**：
    - 反爬登录管理页面的频率伪装统计（业务模块持续调用 `apply_freq_delay` / `record_request`）
    - Dashboard 的实时统计（任务数 / 评估数 / 订单数等持续累加指标）
    - 健康检查页面的健康评分（持续变化）
    - 任何后端有"内部状态持续累加"特征的 API
  - **不适用**：
    - 纯客户端状态（localStorage 独占，无后端状态）
    - 只读快照类统计（后端一次性生成数据，无需轮询，如日报表）
    - Chart 库内置轮询（echarts / recharts 已有 setInterval 机制）
    - 已有 SSE 推送的实时数据流（避免与 SSE 重复）
  - **历史教训**：`AntiCrawl` 页面的 `loadFreqStats` 仅在 `useEffect` 初始化时调用一次，**没有 `setInterval` 定时刷新**。后端 `FreqDisguise.record_request` 被 collector/buyer 持续调用累加统计正确，但前端 UI 永远显示初始值（0）。用户反馈"频率伪装统计持续为 0 且无变化"持续数天。修复后在 `useEffect` 中加 `setInterval(loadFreqStats, 10000)` + cleanup `clearInterval`，数据立即开始正常累加

- 🆕v4.12【强制】**F-REVIEW-ASYNC-CONFIG-LOAD：异步配置加载与竞态保护**
  - 使用 `usePersistentState` 等 localStorage 持久化 hook 时，若初始值需从异步 API（如 `configApi.get()`）加载，必须实现双重检查防止竞态：第一次检查 localStorage 是否已有用户偏好，第二次检查在 API 返回后再次确认 localStorage 未被 usePersistentState 防抖写入抢先
  - **核心机制**（审查时必须理解）：
    - `usePersistentState` 同步初始化无法等待异步 API
    - 用户偏好优先级 > 全局配置默认值，不能直接覆盖已有用户偏好
    - 组件卸载后 API 返回仍调 setState 会触发 React 警告（Can't perform a React state update on an unmounted component）
  - **判断信号**：
    - 代码含 `configApi.get().then(cfg => setXxx(cfg.xxx))` 模式 → 必须有 cancelled 标志和双重检查
    - `useEffect` 依赖数组为 `[]` 但调用了异步 API + setState → 必须实现清理函数 `return () => { cancelled = true }`
    - 代码含 `if (localStorage.getItem(KEY) !== null) return` 短路 → 必须在 API then 回调中再次检查
  - **修复模式**：
    ```typescript
    // ✅ 双重检查 + cancelled 标志
    const [autoSearchEnabled, setAutoSearchEnabled] = usePersistentState<boolean>(
      'xh.tasks.autoSearchEnabled',
      false,
    )

    useEffect(() => {
      // 第一次检查：localStorage 已有值（用户偏好优先），不覆盖
      if (localStorage.getItem('xh.tasks.autoSearchEnabled') !== null) return
      let cancelled = false
      configApi.get()
        .then(cfg => {
          if (cancelled) return
          // 第二次检查：防止 usePersistentState 防抖写入抢先
          if (localStorage.getItem('xh.tasks.autoSearchEnabled') !== null) return
          setAutoSearchEnabled(cfg.task_scheduler?.auto_search_enabled ?? false)
        })
        .catch(() => { /* config 加载失败保持默认 false */ })
      return () => { cancelled = true }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
    ```
  - **配置参数**：`async_config_load.required_double_check`（默认 `true`，必须双重检查 localStorage）、`async_config_load.required_cancelled_flag`（默认 `true`，必须有 cancelled 标志）、`async_config_load.user_preference_priority`（默认 `true`，用户偏好优先于全局配置）、`async_config_load.fallback_default_value`（默认 `false`，config 加载失败时的兜底值）在 `config.yaml` 的 `async_config_load` 节点管理
  - **适用**：所有从异步 API 加载初始值的 usePersistentState/useState 场景；用户偏好与全局配置合并的场景
  - **不适用**：纯同步初始值（直接 useState(initialValue)）；非持久化的 useState；无异步 API 调用的场景
  - **历史教训**：`usePersistentState('xh.tasks.autoSearchEnabled', false)` 直接用 false 初始化，然后 useEffect 异步加载 configApi.get() 设置默认值，但用户已手动关闭开关（localStorage 为 false 值）时被 API 返回的 true 覆盖，导致用户偏好丢失

- 🆕v4.16【强制】**F-REVIEW-ASYNC-RACE-CONDITION：长耗时异步请求 race condition 防护**
  - **判断信号**：`client.post` / `client.get` 调用含 `timeout >= 3000` 参数；或调用方为 LLM/批量类（`aiApi.deepAnalyze` / `aiApi.evaluateCondition` / `evalApi.batchEvaluate`）；用户可触发多次切换商品/任务/对象的 Modal 内异步或列表行按钮异步
  - **强制规则**：任何 >3s 的异步请求必须用 `useRef` 跟踪最新请求 ID；旧请求的 result/error/loading 三态在 setState 前必须校验 `ref.current === itemId`，不匹配则丢弃；finally 块同样校验，避免提前关闭新请求的 loading
  - **代码模板**：
    ```typescript
    const itemIdRef = useRef('')
    const onXxx = async (itemId: string) => {
      itemIdRef.current = itemId
      setLoading(true); setResult(null)
      try {
        const result = await api.fetch(itemId)
        if (itemIdRef.current !== itemId) return  // 丢弃过期结果
        setResult(result)
      } catch (err) {
        if (itemIdRef.current !== itemId) return  // 丢弃过期错误
        handleError(err)
      } finally {
        if (itemIdRef.current === itemId) setLoading(false)  // 仅最新请求结束 loading
      }
    }
    ```
  - **配置参数**：`async_race_condition` 节点（enabled / threshold_ms / detect_patterns / abort_controller_preferred）
  - **适用场景**：timeout >= 3s 的异步请求 + 用户可触发多次切换商品/任务/对象
  - **不适用场景**：同步请求（< 1s）；一次性请求（页面加载）；用户无法重复触发（如表单提交后禁用按钮）；请求顺序由用户显式控制（如分页加载）
  - 注：`AbortController` 是更优解但需后端支持取消；`useRef` 方案是通用轻量方案

- 🆕v4.24【强制】**F-REVIEW-UI-PREFERENCE-PERSISTENCE：用户偏好类 UI 状态持久化强制复用 usePersistentState**
  - 用户偏好类 UI 状态（自动刷新开关、视图模式、列显隐、折叠/展开状态、主题偏好、最近使用列表、记住上次选中项等）必须使用项目既有 `frontend/src/hooks/usePersistentState.ts` 持久化，**禁止**用 `useState` 存储（判别信号：刷新页面/路由切换后状态丢失即违规）、**禁止**各组件自行实现 `localStorage.getItem/setItem` 逻辑、**禁止**引入第三方持久化库
  - **核心机制**（审查时必须理解）：
    - 项目已有统一封装的 `usePersistentState` hook（位于 `frontend/src/hooks/usePersistentState.ts`），内置防抖写入、数据验证、localStorage 不可用回退到内存 Map
    - 业务方未使用既有 hook 而裸 `useState` 会导致用户偏好类状态在页面刷新/路由切换后丢失
    - 各组件自行实现 localStorage 读写会导致错误处理不一致、key 命名混乱、无防抖、无内存回退
    - 已通过后端 API 持久化的字段（如批量采集的 `enabled` / `interval_minutes`）不得再用 `usePersistentState` 重复持久化，否则前后端不一致
  - **判断信号**（grep 检测）：
    - `grep -E "const\s+\[\s*(autoRefresh|viewMode|columnConfig|density|collapsed|expandedKeys|themePreference|recentItems|rememberLast)\s*,\s*\w+\]\s*=\s*useState" frontend/src/pages/**/*.tsx` 命中 → 违规
    - `grep "localStorage.getItem\|localStorage.setItem" frontend/src/pages/**/*.tsx` 命中 → 检查是否应改用 `usePersistentState`
    - 用户反馈"刷新页面后开关/设置丢失"、"每次进入页面都需要重新设置" → 必查
  - **修复模式**（用 usePersistentState 替换 useState）：
    ```typescript
    // ✅ 正确：使用 usePersistentState + key 命名规范 + validator
    import { usePersistentState } from '../../hooks/usePersistentState'
    
    const [autoRefresh, setAutoRefresh] = usePersistentState<boolean>(
      'xh.batchRefresh.autoRefresh',  // key 遵循 xh.<page>.<field> 命名
      false,
      { validator: (v): v is boolean => typeof v === 'boolean' },  // validator 必填防脏数据
    )
    
    // 禁止：裸 useState，刷新页面后状态丢失
    // 禁止：自行实现 localStorage 读写
    ```
  - **状态分类识别**（新增 state 时必须先识别归属类别）：
    | 类别 | 持久化方式 | 示例 |
    |---|---|---|
    | 用户偏好类 | `usePersistentState` | 自动刷新、视图模式、列显隐、折叠/展开、主题偏好、最近使用列表 |
    | 业务数据类 | 后端 API | 任务列表、订单状态、配置项（已通过后端持久化） |
    | 会话状态类 | Zustand store | 登录态、当前选中项、跨页共享状态 |
    | 临时状态类 | `useState` | loading、modal open、按钮 submitting、表单 dirty |
    | 敏感数据类 | secure storage / httpOnly cookie | token、密码、API key |
  - **配置参数**：`ui_preference_persistence` 节点（enabled / preference_keywords / required_hook / prefer_state_storage_patterns / skip_scenarios / require_validator / require_key_naming / require_memory_fallback / detection_signals）
  - **关键约束**：
    - localStorage key 必须遵循 `xh.<page>.<field>` 命名模式
    - validator 必填，防止 localStorage 脏数据（旧版本数据/用户手动修改/其他项目同名 key）导致 UI 异常
    - 不重复持久化后端已通过 PATCH /config 持久化的字段（避免前后端不一致）
    - localStorage 不可用（隐私模式/存储已满/被禁用）时依赖 hook 内置的内存回退机制，业务代码不额外 try-catch
  - **适用**：用户偏好类 UI 状态（开关类、视图模式、列显隐、折叠/展开、主题偏好、最近使用列表、记住上次选中项）；跨会话需要保留的 UI 偏好
  - **不适用**：业务数据（必须走后端 API）；会话状态（必须用 Zustand store）；临时状态如 loading/modal open（必须用 useState）；敏感数据（必须走 secure storage）；已通过后端持久化的字段（不重复持久化）
  - **历史教训**：`Maintenance/BatchRefresh.tsx` 的「自动刷新」开关使用 `useState(false)`，每次刷新页面或重新进入页面开关重置为关闭，用户需要反复手动开启。修复方式：替换为 `usePersistentState<boolean>('xh.batchRefresh.autoRefresh', false, { validator: ... })`，复用项目既有 `hooks/usePersistentState.ts`（含防抖写入、数据验证、localStorage 不可用回退到内存 Map）。本次同时验证「启用批量采集」与「触发间隔」字段已通过后端 `PATCH /api/batch-refresh/config` 持久化，无需重复持久化
  - **对应后端原则**：若后端提供用户偏好 API（如 `/api/user/preferences`），同样必须复用同一持久化策略与配置驱动，不硬编码（详见 `xianyu-backend-code-review` v4.24.0 复盘记录同步原则）
