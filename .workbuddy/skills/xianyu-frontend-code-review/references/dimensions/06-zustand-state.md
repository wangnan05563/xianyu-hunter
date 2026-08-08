# 6. Zustand 状态管理 🆕v2.0

- 【强制】使用 Zustand 4.5（轻量状态管理）
- 【强制】`persist` 中间件 + `partialize` 只存必要字段（过滤 ReactNode 等不可序列化字段）
- 【强制】store 是纯逻辑层（不感知路由库）
- 【强制】`_navigator` 由组件通过 `useNavigate` 注入，不直接依赖 `react-router-dom`
- 【强制】防抖持久化（300ms）
- 【强制】`hydrate()` 恢复时丢弃失效 path
- 【推荐】`replacedHistory` 回收栈最多 5 个 FIFO
- 【强制】`openSheet()` 四分支决策：
  1. `activateExistingSheet`：已存在则激活
  2. `performCircularReplace`：达到 maxSheets 上限时循环替换
  3. `replaceMobileActiveSheet`：移动端替换当前活动
  4. `createNewSheet`：创建新页签
- 【强制】**状态变更操作一致性**：每个状态变更函数必须同步更新所有相关字段
  - `activateSheet` 激活最小化 sheet 时必须同时设 `minimized: false`
  - `closeSheet` 关闭激活项时必须同步切换 `activeId` 到相邻项
  - `minimizeSheet` 最小化激活项时必须同步切换 `activeId` 到下一个非最小化项
  - 检查方法：列出操作影响的所有字段，确认全部同步更新
- 🆕v4.6【强制】**F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND：多源状态同步统一入口（前端侧）**
  - 前端调用同一后端写入接口的不同代码路径时，状态更新必须统一通过单一 `updateState` / `refetchState` 函数而非各路径独立更新
  - **判断信号**：
    - 多个组件 / Hook 各自调用后端 GET 接口获取同一份状态（如 `/cookies/layers` / `/api/auth/me` / `/api/about`）
    - 各组件独立 setState 但缺少统一 refetch 入口
    - 一个组件更新状态后，其他依赖同一状态的组件不会自动刷新（需要手动刷新页面）
  - **修复模式**：
    - 抽取 `useXxxState()` Hook + 内部 `refetch()` 方法 + 写入路径统一调用 `refetch()`
    - 复杂场景用 Zustand 集中管理（`setXxxState(newData)`），写入路径统一 `setXxxState`
    - **禁止**每个组件独立 `useEffect(() => fetch(...), [])` 重复拉取
  - **关键约束**：写入路径调用 refetch 后，**禁止**再独立 setState 旧值（避免回退）；refetch 失败应保留旧状态并 `message.warning`
  - **配置参数**：`unified_state_hooks`（统一状态 Hook 列表）、`write_entry_paths`（需要触发 refetch 的写入路径）在 `config.yaml` 的 `state_sync_frontend` 节点管理
  - **适用**：后端有"主数据源"概念 + 多入口更新同一份状态 + 前端需要展示最新状态
  - **不适用**：纯客户端状态（localStorage 独占）、只读状态（一次性拉取）
  - **历史教训**：后端 `/cookies/layers` 端点修复统一同步入口后，前端若仍用 `useEffect` 在各组件独立调用 + 不统一 refetch，会出现"某些页面显示失效、另一些页面显示有效"的不一致现象。统一通过 `useCookieLayersStore` 集中管理 + 各写入路径 refetch 后彻底一致
- 🆕v4.11【强制】**F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY：前端缓存与后端状态机一致性**
  - 同一业务目标（如"刷新会话" / "更新任务状态"）有 ≥2 条链路（API 路由 + WebSocket 推送 + 定时任务 + 手动操作）触发同一状态变更时，前端必须通过**统一 refetch 入口**刷新缓存，**禁止**各链路独立 `setState` 导致缓存不一致
  - **核心机制**（审查时必须理解）：
    - 后端状态机有白名单转换规则（B-REVIEW-STATE-MACHINE-WHITELIST），前端缓存必须与后端状态机保持一致
    - 多链路触发同一状态变更时（如 API 调用 + SSE 推送 + 定时轮询），若各链路独立 `setState`，会出现"页面 A 显示新状态、页面 B 显示旧状态"的不一致
    - 前端缓存（Zustand store / useState / useRef）必须通过统一 `refetch()` 入口从后端拉取最新状态，而非各链路独立推演
  - **判断信号**：
    - 多个组件 / Hook 各自调用后端 GET 接口获取同一份状态 + 各自 `setState` → 视为违规
    - API 调用成功后前端 `setState(newStatus)` 但未触发其他依赖同一状态的组件刷新 → 视为违规
    - SSE 推送状态变更但前端只更新当前组件 `setState` 未刷新全局缓存 → 视为违规
    - 定时轮询拉取状态后前端 `setState` 与 API 调用路径的 `setState` 逻辑不一致 → 视为违规
  - **修复模式**（统一 refetch 入口 + 集中状态管理）：
    ```typescript
    // ✅ 抽取 useXxxState() Hook + 内部 refetch() + 多链路统一调用 refetch()
    function useTaskState() {
      const [task, setTask] = useState<Task | null>(null)
      const refetch = useCallback(async (taskId: number) => {
        const data = await taskApi.get(taskId)
        setTask(data)  // 统一 setState 入口
      }, [])
      return { task, refetch, setTask }
    }
    // API 调用路径
    const handleControl = async (action) => {
      await taskApi.control(taskId, action)
      await refetch(taskId)  // ✅ 统一 refetch
    }
    // SSE 推送路径
    useEffect(() => {
      const es = new EventSource(...)
      es.onmessage = (e) => {
        const data = JSON.parse(e.data)
        if (data.task_id === taskId) refetch(taskId)  // ✅ 统一 refetch，禁止独立 setState
      }
    }, [taskId, refetch])
    ```
  - **关键约束**：
    - 多链路触发同一状态变更时，**必须**调用统一 `refetch()` 从后端拉取最新状态，**禁止**各链路独立 `setState` 推断新状态
    - `refetch()` 失败应保留旧状态并 `message.warning`，**禁止**清空缓存
    - SSE 推送 + 定时轮询 + API 调用三链路必须共享同一 `refetch()` 入口
  - **配置参数**：`unified_refetch_hooks`（统一 refetch Hook 列表）、`multi_link_state_fields`（多链路状态字段列表，如 `['task.status', 'session.state']`）、`forbid_independent_setstate`（默认 `true`，多链路场景禁止独立 setState）在 `config.yaml` 的 `dual_link_cache_consistency` 节点管理
  - **适用**：同一业务目标有 ≥2 条链路触发状态变更的场景（API + SSE + 轮询）；后端有状态机白名单转换的场景
  - **不适用**：单链路状态变更（只有 API 调用，无 SSE/轮询）；纯前端 UI 状态（不依赖后端）；只读状态（无写入操作）
  - **历史教训**：任务详情页通过 API 调用 `taskApi.control(taskId, 'pause')` 后 `setTask({ ...task, status: 'paused' })` 独立推断状态，但任务列表页通过定时轮询拉取最新状态显示 `running`（后端实际状态已是 `paused`，但列表页缓存未刷新），导致"详情页显示已暂停、列表页显示运行中"的不一致。修复后两页统一通过 `useTaskState().refetch(taskId)` 刷新缓存

```typescript
// ✅ 推荐：persist + partialize
export const useSheetStore = create<SheetState>()(
  persist(
    (set, get) => ({
      sheets: [],
      openSheet: (path, title, icon) => { ... },
    }),
    {
      name: 'sheet-storage',
      partialize: (state) => ({ /* 只存必要字段，过滤 ReactNode */ }),
    }
  )
)
```
