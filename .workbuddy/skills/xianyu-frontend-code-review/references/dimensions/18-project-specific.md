# 18. 闲鱼项目规范 🆕v2.0

- 【强制】UI 组件库：Ant Design 5.21
- 【强制】视觉风格（来自 user_profile.md）：干净明亮的扁平化设计语言，清新治愈的 macaron 配色，浅白/浅青为主，大圆角，轻透磨砂玻璃质感
- 【强制】API 出口统一：`frontend/src/api/index.ts` 用 `export *` 聚合
- 【强制】测试框架：Vitest 4.1 + @testing-library/react 16.3 + jsdom 29.1
- 【强制】测试文件位置：组件/hook 同级目录 `__tests__/<Component>.test.tsx`
- 【强制】构建命令：`npm run build`（`tsc -b && vite build`）
- 【强制】类型检查：`npx tsc -b`（构建前强制类型检查）
- 【强制】Dev 命令：`npm run dev`（HMR，端口 5173）
- 【强制】测试命令：`npx vitest run`
- 【推荐】抽象模式：纯函数 + 组件 + 常量分层（如 `resolveActionDisplay` + `ActionPlaceholder` + `ACTION_PLACEHOLDER_TEXT`）
- 🆕v4.0【强制】**显式样式优于隐式间距**：图标与文字、按钮与文字等内联元素间距用显式 `style={{ marginRight: N }}` 或 `Space` 组件，**禁止**依赖 JSX 空格渲染间距
- 🆕v4.0【强制】**注释与代码一致性**：注释必须与代码逻辑严格一致，禁止误导性注释；防御性说明需明确标注为"防御"而非"必需"
- 🆕v4.7【强制】**F-REVIEW-REUSE-PATTERN-FRONTEND：复用既有模式原则（前端侧）**
  - 新增前端功能前必须 grep 项目内相似实现，复用既有 Hook/工具函数/模式，**禁止**重新实现已有功能
  - **判断信号**：新增 Hook/组件/工具函数时 → grep 项目内是否已有相似实现 → 若有则复用或扩展 → 若无则评估是否可抽取为通用工具
  - **修复模式**（复用检查流程）：
    ```typescript
    // 新增"采集评估明细"功能前，先 grep 项目内相似实现
    // grep "message.loading" → 发现多处使用 message.loading + try/catch + message.success/error 模式
    // 复用既有模式：
    const hide = message.loading('正在采集...', 0)  // ✅ 复用 message.loading 模式
    try {
      // ...
    } catch (err) {
      hide()
      message.error(...)  // ✅ 复用 message.error 模式
    }
    // 新增页面路由前，先 grep "lazyRetry" → 复用既有懒加载模式
    const EvalDetail = lazy(() => lazyRetry(() => import('./pages/EvalDetail')))  // ✅ 复用 lazyRetry
    // 新增深拷贝需求前，先 grep "JSON.parse" → 发现应改用 structuredClone（SonarQube S7784）
    const cloned = structuredClone(data)  // ✅ 复用 structuredClone 模式
    ```
  - **配置参数**：`search_keywords`（搜索关键词列表，如 `message.loading` / `lazyRetry` / `structuredClone` / `useDebounce` / `useEventSource`）、`similarity_threshold`（相似度阈值，默认 0.7）、`reuse_priority`（复用优先级：项目内既有 Hook > 工具函数 > 模式 > 标准库 > 第三方库）在 `config.yaml` 的 `reuse_pattern_frontend` 节点管理
  - **关键约束**：
    - 新增 Hook 前必须 grep `use*.ts` 确认无相似实现
    - 新增工具函数前必须 grep `utils/` / `helpers/` 确认无相似实现
    - 强行复用导致耦合 > 重新实现的成本时，允许重新实现但需注释说明
    - 复用 Ant Design 组件时必须确认版本兼容性（项目用 AntD 5.21）
  - **适用**：新增前端功能（Hook/组件/工具函数/模式）前的预检查
  - **不适用**：首次实现的基础设施代码（无既有实现可复用）、业务逻辑差异较大的场景（强行复用会导致耦合）
  - **历史教训**：评估明细采集按钮未复用项目内既有的 `message.loading` + `try/catch` + `message.success/error` 三态反馈模式，导致无用户反馈。修复后复用既有模式实现三态反馈

- 🆕v4.19【强制】**F-REVIEW-SCHEDULER-STATUS-DISPLAY：调度器状态展示规范**
  - 前端"关于"页面必须展示关键调度器启动状态，调用 `/api/about` 端点获取 `schedulers: [{name, enabled, interval_minutes, last_run_at}]` 数组并渲染为状态卡片，未启动的调度器必须显示红色"未启动"标签 + 启动命令提示，启动的调度器显示绿色"运行中"标签 + 间隔 + 最近运行时间，调度器状态变更必须通过 SSE 实时推送或定时轮询刷新
  - **核心机制**（审查时必须理解）：
    - 后端关键调度器（如 `BatchRefreshScheduler`）影响业务正确性，但用户无法从终端日志感知启动状态
    - 前端"关于"页面是用户感知系统运行状态的唯一入口，必须展示调度器状态
    - 未启动调度器必须用红色标签醒目标识 + 显示启动命令（如 `python -m xianyu_hunter web --with-scheduler`）
    - 启动的调度器显示绿色"运行中"标签 + 间隔（如"每 30 分钟"）+ 最近运行时间
    - 调度器状态可能随启动参数/环境变量变化，必须通过 SSE 推送或定时轮询（间隔在 config.yaml 管理）刷新
  - **判断信号**：
    - `grep "schedulers" frontend/src/` 未发现消费 `/api/about` 返回的 `schedulers` 字段 → 视为违规
    - "关于"页面只有版本号/构建时间，无调度器状态展示 → 视为违规
    - 调度器状态用单一布尔值显示（无"未启动"vs"运行中"区分）→ 视为可疑
    - 未启动调度器无启动命令提示 → 视为可疑
    - 调度器状态无定时刷新（仅页面加载时拉一次）→ 视为可疑
  - **修复模式**：
    ```typescript
    // ✅ types.ts 声明调度器状态类型
    interface SchedulerStatus {
      name: string
      enabled: boolean
      interval_minutes: number
      last_run_at: string | null  // ISO 时间字符串，null 表示从未运行
    }

    // ✅ About 页面渲染调度器状态卡片
    function SchedulerStatusCard({ scheduler }: { scheduler: SchedulerStatus }) {
      return (
        <Card size="small" title={scheduler.name}>
          <Space>
            <Tag color={scheduler.enabled ? 'success' : 'error'}>
              {scheduler.enabled ? '运行中' : '未启动'}
            </Tag>
            <Text type="secondary">每 {scheduler.interval_minutes} 分钟</Text>
            {scheduler.last_run_at && (
              <Text type="secondary">
                最近运行：{new Date(scheduler.last_run_at).toLocaleString()}
              </Text>
            )}
          </Space>
          {!scheduler.enabled && (
            <Alert
              type="warning"
              showIcon
              message="该调度器未启动，相关功能将不生效"
              description={
                <Text code>python -m xianyu_hunter web --with-scheduler</Text>
              }
            />
          )}
        </Card>
      )
    }

    // ✅ 定时轮询刷新（间隔从 config 读取）
    const POLL_INTERVAL = 30000  // 30s，应从 config.yaml 读取
    useEffect(() => {
      const timer = setInterval(() => aboutApi.get().then(setAboutInfo), POLL_INTERVAL)
      return () => clearInterval(timer)
    }, [])

    // 禁止：未展示调度器状态，用户无法感知启动情况
    ```
  - **配置参数**：`scheduler_status_display.enabled`（默认 `true`）、`scheduler_status_display.require_about_endpoint_consumption`（默认 `true`，前端必须消费 `/api/about` 的 `schedulers` 字段）、`scheduler_status_display.require_disabled_hint`（默认 `true`，未启动调度器必须显示启动命令提示）、`scheduler_status_display.require_realtime_refresh`（默认 `true`，必须通过 SSE 或定时轮询刷新）、`scheduler_status_display.refresh_interval_ms`（默认 `30000`，轮询间隔毫秒）、`scheduler_status_display.status_color_mapping`（默认 `{enabled: 'success', disabled: 'error'}`）、`scheduler_status_display.startup_command_hint`（默认 `'python -m xianyu_hunter web --with-scheduler'`，未启动时显示的启动命令）在 `config.yaml` 的 `scheduler_status_display` 节点管理
  - **适用**：前端"关于"页面/系统信息页面；展示后端调度器运行状态；用户需要感知后台任务运行情况的场景
  - **不适用**：纯前端调度器（如 `setInterval` 无后端对应）；调试用页面（非用户面向）；无调度器的简单应用
  - **历史教训**：用户启动 web 服务时未加 `--with-scheduler` 参数，`BatchRefreshScheduler` 永远不运行，但前端"关于"页面只显示版本号，用户无法感知调度器未启动。导致商品 1058031608014 实际已售但数据库 `is_sold=0` 长期不刷新，用户看到已售商品仍被推荐。修复后前端"关于"页面展示调度器状态卡片，未启动时显示红色标签 + 启动命令提示
