# 7. API 调用规范 🆕v2.0

- 【强制】使用 axios 单例 + 拦截器（`frontend/src/api/client.ts`）
- 【强制】`baseURL: '/api'` + `withCredentials: true`（**硬约束**：所有请求携带 cookie 通过后端认证）
- 【强制】请求拦截器附加 `Authorization: Bearer <token>`
- 【强制】响应拦截器 401 防抖跳转（`isRedirecting` 标志位防重复跳转）
- 【强制】业务 API 模块导出 `<名>Api` 对象，**禁止**默认导出
- 【强制】API 统一出口 `frontend/src/api/index.ts`，新增 API 归入子模块
- 【强制】SSE 流式请求用 `fetch + ReadableStream`（axios 不支持流式）
- 【强制】SSE 请求必须包含 `credentials: 'include'`
- 【强制】错误抛 axios 兼容格式：`Object.assign(new Error(msg), { response: { status, data } })`

```typescript
// ✅ 推荐：业务 API 模块导出对象
export const taskApi = {
  list: () => client.get('/tasks'),
  get: (id: number) => client.get(`/tasks/${id}`),
  create: (data: TaskCreate) => client.post('/tasks', data),
  control: (id: number, action: string) => client.post(`/tasks/${id}/control`, { action }),
}

// ✅ 推荐：SSE 用 fetch + ReadableStream
live: async () => {
  const response = await fetch('/api/tasks/live', {
    credentials: 'include',  // 【硬约束】
  })
  const reader = response.body!.getReader()
  // ... 解析 SSE 事件
}
```

- 🆕v4.5【强制】**F-REVIEW-CONFIG-LINKAGE：配置全链路生效验证（前端侧）**
  - 前端配置项（如搜索间隔、防抖间隔、排序方式）从定义到消费必须全链路追踪，**禁止**只在配置页设置但不传递给后端 API
  - **判断信号**：前端配置页有某配置项，但对应的 API 请求参数中不包含该字段 → 配置无效
  - **检查方法**：从前端配置页表单 → 提交 API → 后端 config.yaml → 后端 Config 类 → 后端方法参数 → 最终 URL/SQL，确认每层都读取并传递
  - **适用**：所有前端可配置的参数（搜索参数、间隔、阈值），尤其是新增配置项后
  - **不适用**：前端纯 UI 配置（如主题色、页签数量）
  - **历史教训**：前端配置页显示"排序方式：默认综合"，用户可以设置排序方式，但后端 `build_search_url` 不支持 sort_type 参数，搜索 URL 中从不包含 `&sortType=...`。前端"搜索间隔"文案也混淆了"操作延迟"和"任务循环间隔"两个概念

- 🆕v4.7【强制】**F-REVIEW-FILTER-SCENARIO-FRONTEND：过滤逻辑场景区分（前端侧）**
  - 前端调用后端查询接口时，必须按使用场景显式传递场景标志（如 `include_failed` / `include_deleted`），**禁止**所有调用点使用默认值导致展示页看不到完整数据
  - **判断信号**：前端调用 `list_orders` / `list_tasks` 等查询接口时 → 检查是否传递 `include_failed` 参数 → 展示历史场景（评估明细页、历史记录页）必须传 `True` → 操作判断场景（抢单按钮、状态判断）传 `False` 或默认值
  - **修复模式**：识别接口的所有前端调用点 → 按场景分类（展示历史 vs 操作判断）→ 展示历史场景显式传 `include_failed: true` → 操作判断场景显式传 `include_failed: false` → 添加注释说明为何该场景需要/不需要失败数据
  - **配置参数**：`scenario_flag_field`（默认 `include_failed`）、`display_history_routes`（展示历史场景路由列表）、`operation_judge_routes`（操作判断场景路由列表）在 `config.yaml` 的 `filter_scenario_frontend` 节点管理
  - **关键约束**：
    - 展示历史场景**必须显式传 `True`**，不依赖后端默认值（后端默认安全为 `False`）
    - 前端调用点必须有注释说明为何该场景需要/不需要失败数据
    - 新增查询接口调用点时，必须评估属于哪种场景
  - **适用**：调用后端 `list_*` / `get_*` 查询接口的所有前端代码路径，尤其是订单/任务/日志类查询
  - **不适用**：纯前端筛选（如 Table 组件的 filter）、单一场景的查询（如报表统计只看成功）
  - **历史教训**：评估明细页调用 `list_orders_by_item_ids` 时未传 `include_failed`，后端默认跳过 failed 订单，导致用户点击抢单失败后刷新页面看到 "无"，误以为没下过单而反复触发抢单。修复后评估明细页显式传 `include_failed: true`

- 🆕v4.10【强制】**F-REVIEW-FILTER-VISIBILITY：过滤结果可见性（前端侧）**
  - 后端返回 `filter_summary` 时前端必须实现三态提示策略 + "查看被过滤结果"入口，**禁止**只显示"查询完成"不暴露过滤过程
  - **核心机制**（审查时必须理解）：
    - 后端过滤链（keyword/price/publish_days/自定义）会输出 `filter_summary` 含 `raw`/各阶段 `*_skipped`/`final_total`/`filtered_out` 详情
    - 前端若只看 `final_total` 不展示过滤过程，用户无法判断"无结果"是搜索无果还是被过滤掉，反复调整搜索词无果
    - TypeScript 类型必须显式声明 `filter_summary?: LiveFilterSummary`，**禁止**用 `as { filter_summary?: ... }` 强制类型转换绕过 TS 检查（会掩盖类型不匹配 bug）
  - **判断信号**：
    - 前端代码含 `(res as { filter_summary?: ... })` 强制类型转换 → 视为违规
    - 实时搜索/列表查询结果 `final_total == 0` 但前端只显示"查询完成"无任何过滤提示 → 视为违规
    - 后端返回 `filtered_out` 非空但前端无"查看被过滤结果"入口 → 视为违规
    - `grep "filter_summary" frontend/src/` 发现类型定义或消费逻辑缺失 → 视为违规
  - **修复模式**（三态提示 + 按钮入口 + Modal 详情）：
    ```typescript
    // ✅ API 类型显式声明
    export interface LiveFilterSummary {
      raw: number; formatted: number;
      keyword_skipped: number; price_skipped: number; publish_days_skipped: number;
      final_total: number; final_items: number; final_sellers: number;
      filtered_out: LiveFilteredItem[];
    }
    export interface LiveFilteredItem {
      link_type: string; link_key: string;
      display?: Partial<TaskLink['display']> & Record<string, any>;
      filter_reason: 'keyword' | 'price' | 'publish_days';
      filter_detail: string;
    }
    // live() 返回类型显式声明 filter_summary
    async function live(): Promise<{ items: TaskLink[]; filter_summary?: LiveFilterSummary; ... }>

    // ✅ 三态提示策略
    const fs = res.filter_summary  // 类型已在 live() 声明，无需 as 转换
    setLiveFilterSummary(fs || null)
    const itemCount = res.items?.length || 0
    if (itemCount > 0) {
      message.success(`实时查询完成，获取 ${itemCount} 条`)
    } else if (fs && fs.raw > 0) {
      // warning 必须列出各过滤原因计数
      const reasons: string[] = []
      if (fs.keyword_skipped) reasons.push(`关键词 ${fs.keyword_skipped}`)
      if (fs.price_skipped) reasons.push(`价格 ${fs.price_skipped}`)
      if (fs.publish_days_skipped) reasons.push(`发布时间 ${fs.publish_days_skipped}`)
      message.warning(`搜索到 ${fs.raw} 条，但全部被过滤条件筛掉（${reasons.join('、') || '未知原因'}），请调整任务过滤配置`)
    } else {
      message.info('实时查询完成，未找到匹配商品')
    }

    // ✅ "查看被过滤结果"按钮 + Modal（仅 filtered_out 非空时显示）
    {liveFilterSummary && liveFilterSummary.filtered_out.length > 0 && (
      <Button onClick={() => setFilteredModalOpen(true)}>
        查看被过滤的 {liveFilterSummary.filtered_out.length} 条结果
      </Button>
    )}
    <Modal open={filteredModalOpen} onCancel={() => setFilteredModalOpen(false)}>
      <Alert message={`过滤链路：原始 ${fs.raw} → 关键词 ${fs.keyword_skipped} → 价格 ${fs.price_skipped} → 发布时间 ${fs.publish_days_skipped} → 最终 ${fs.final_total}`} />
      <Table dataSource={fs.filtered_out} columns={[
        { title: '商品', dataIndex: 'display' },
        { title: '过滤原因', dataIndex: 'filter_reason', render: (v) => <Tag>{v}</Tag> },
        { title: '详情', dataIndex: 'filter_detail' },
      ]} />
    </Modal>
    ```
  - **三态判定阈值**（参数在 `config.yaml` 的 `filter_visibility` 节点管理）：
    - `success`：`raw >= success_raw_min`（默认 1）且 `final_total >= success_final_min`（默认 1）
    - `warning`：`raw >= warning_raw_min`（默认 1）且 `final_total <= warning_final_max`（默认 0）
    - `info`：`raw <= info_raw_max`（默认 0）
  - **配置参数**：`filter_visibility.three_state_thresholds`（三态判定阈值，如上）、`filter_visibility.modal_required_min_items`（默认 1，filtered_out 长度 ≥此值时必须提供 Modal 入口）、`filter_visibility.filter_reason_labels`（过滤原因中文标签映射，如 `{ keyword: "关键词", price: "价格", publish_days: "发布时间" }`）、`filter_visibility.forbid_as_cast`（默认 `true`，禁止 `as { filter_summary?: ... }` 强制类型转换）在 `config.yaml` 的 `filter_visibility` 节点管理
  - **诊断流程**（出现"实时搜索无结果但不知原因"类问题时执行）：
    1. `grep "filter_summary" frontend/src/` 扫描类型定义与消费逻辑
    2. 检查 API 返回类型是否显式声明 `filter_summary?` 字段
    3. 检查消费代码是否含 `as { filter_summary?: ... }` 强制转换（违规信号）
    4. 检查 `final_total == 0` 分支是否实现三态提示
    5. 检查 `filtered_out` 非空时是否提供"查看被过滤结果"按钮+Modal
  - **适用**：所有调用后端含过滤链路查询接口（实时搜索/历史查询/列表过滤）的前端代码；后端返回 `filter_summary` 结构的场景
  - **不适用**：无过滤的纯 CRUD 接口；前端纯前端过滤（如 Table 自带筛选）；过滤结果不影响用户体验的场景（如后台日志查询）
  - **历史教训**：实时搜索接口 `final_total=0`（keyword 过滤 32 + price 过滤 27 = 0 最终）但前端只显示"实时查询完成"，用户无法判断是搜索无结果还是被过滤掉，反复调整搜索词无果。且 `task.ts` 的 `live()` 返回类型未声明 `filter_summary`，前端用 `(res as { filter_summary?: LiveFilterSummary })` 强制转换绕过 TS 检查。修复后 `live()` 显式声明返回类型 + 三态提示 + "查看被过滤结果"Modal + api/index.ts re-export 新类型

- 🆕v4.12【强制】**F-REVIEW-BATCH-OPERATION：批量操作完整流程**
  - 批量操作（一键启动/停止/删除所有任务等）必须实现完整流程：`Modal.confirm` 确认 + loading 状态 + success/error message 反馈 + 异常处理 + 状态刷新，**禁止**只调 API 不反馈或只反馈不刷新
  - **核心机制**（审查时必须理解）：
    - 批量操作影响多个资源，必须用户显式确认（Modal.confirm）防止误操作
    - 操作期间必须显示 loading 状态防止重复点击
    - 操作成功/失败必须明确反馈（message.success/error）
    - 部分失败时必须告知用户跳过数量和失败原因
    - 操作完成后必须刷新状态（loadTasks）确保 UI 与后端一致
  - **判断信号**：
    - 代码含 `taskApi.batchControl` / `Promise.all(ids.map(...))` 等批量调用 → 必须有完整流程
    - 代码含 `<Button onClick={() => taskApi.batchControl(...)}>` 无 Modal.confirm → 视为违规
    - 代码含批量 API 调用但无 loading 状态 → 视为违规
    - 代码含批量 API 调用但无 try/catch → 视为违规
  - **修复模式**：
    ```typescript
    const [startAllLoading, setStartAllLoading] = useState(false)

    const handleStartAll = useCallback(() => {
      // 过滤出需要启动的任务（跳过已运行）
      const toStart = tasks.filter((t) => t.status !== 'running')
      const skipped = tasks.length - toStart.length
      if (toStart.length === 0) {
        message.info(skipped > 0 ? `所有 ${skipped} 个任务已在运行中` : '暂无任务可启动')
        return
      }
      // 确认对话框
      const taskNames = toStart.map((t) => t.name || t.keyword).slice(0, 5).join('、')
      const more = toStart.length > 5 ? ` 等${toStart.length} 个任务` : ''
      Modal.confirm({
        title: '确认启动所有任务？',
        content: `将启动 ${toStart.length} 个任务（${taskNames}${more}）` +
          (skipped > 0 ? `，跳过 ${skipped} 个已运行任务` : ''),
        okText: '启动',
        cancelText: '取消',
        onOk: async () => {
          setStartAllLoading(true)
          try {
            await taskApi.batchControl(toStart.map((t) => t.id), 'restart')
            message.success(`已启动 ${toStart.length} 个任务` + (skipped > 0 ? `，跳过 ${skipped} 个` : ''))
            await loadTasks()  // 刷新状态
          } catch (err: unknown) {
            const detail = err instanceof Error ? err.message : String(err)
            message.error(`启动失败: ${detail.slice(0, 100)}`)
          } finally {
            setStartAllLoading(false)
          }
        },
      })
    }, [tasks, loadTasks])

    // 禁止：无确认 + 无 loading + 无反馈
    ```
  - **配置参数**：`batch_operation.required_steps`（默认 `["confirm", "loading", "feedback", "refresh"]`，必须的步骤）、`batch_operation.confirm_component`（默认 `Modal.confirm`）、`batch_operation.max_preview_items`（默认 `5`，确认框中预览的任务名数量上限）、`batch_operation.error_message_max_length`（默认 `100`，错误消息截断长度）在 `config.yaml` 的 `batch_operation` 节点管理
  - **适用**：所有批量操作（一键启动/停止/删除/导出所有任务）；影响多个资源的操作；不可逆操作（删除/归档）
  - **不适用**：单个资源操作（如启动单个任务）；纯查询操作（无副作用）；用户已通过其他方式确认的操作（如表单提交）
  - **历史教训**：`TaskContentMenu` 一键启动按钮直接调 `taskApi.batchControl` 无确认无 loading 无反馈，用户点击后无任何反应以为没生效重复点击，导致同一任务被启动多次

- 🆕v4.20【强制】**F-REVIEW-VERSION-SOURCE-ALIGN：元数据源显示对齐规范**
  - 前端显示构建期元数据（版本号/构建时间/git_sha 等）必须调用**语义对齐**的 API 端点（如 `aboutApi.get()` 即 `/api/about`），**禁止**将返回 `len(backups)` / `count` / `size` / `length` 等业务计数端点当作版本号使用；新增元数据 API 调用必须通过 `Promise.all` 与既有 API 并行化避免瀑布请求；修复时必须同步清理只 `set` 不 `read` 的死代码 state
  - **核心机制**（审查时必须理解）：
    - 构建期元数据必须有唯一源头（Single Source of Truth），前端只是消费方，不能从同名但语义不同的端点推测
    - 端点命名相似不等于语义对齐：`/api/config/version` 名称含 "version" 但实际返回 `len(backups)`，受 `BACKUP_KEEP` 上限影响会卡在上限值
    - 显示元数据的组件（`<Statistic>` / `<Tag>` / `<Descriptions.Item>`）必须 grep `value=` 字段来源，确认来自语义对齐 API
    - 新增独立 API 调用必须 `Promise.all` 并行化（与既有 configApi 调用同时发起），避免串行瀑布请求导致加载时间翻倍
    - 修复 bug 时发现只 `set` 不 `read` 的 state（如 `const [, setXxx] = useState(0)`）必须同步清理，避免遗留死代码
  - **判断信号**：
    - `grep "getVersion\\(\\)" frontend/src/` 用于版本号显示 → 视为违规（应改用 `aboutApi.get()`）
    - `grep "Statistic.*title=.*version" frontend/src/` 的 `value=` 字段来自 `length` / `count` / `size` → 视为违规
    - `grep "Tag.*color=.*version" frontend/src/` 的 `children` 字段来自计数端点 → 视为违规
    - `grep "configApi\\.getVersion" frontend/src/` 同时 grep 不到 `aboutApi.get` → 视为违规
    - `const [, setXxx] = useState` 解构出 setter 但无 getter 使用 → 死代码信号
    - 新增 `aboutApi.get()` 调用未与既有 `configApi.getXxx()` `Promise.all` 并行 → 性能违规
  - **修复模式**：
    ```typescript
    // 禁止：getVersion() 实际返回 len(backups)，受 BACKUP_KEEP=10 上限永远卡在 10（永远显示 V10）
    // ✅ 正确：调用语义对齐的 /api/about 端点 + Promise.all 并行化
    const [buildInfo, setBuildInfo] = useState<BuildInfo | null>(null)
    const [backups, setBackups] = useState<BackupItem[]>([])

    useEffect(() => {
      // 并行化：aboutApi 提供版本号 + configApi 提供备份数（语义分离）
      Promise.all([aboutApi.get(), configApi.listBackups()])
        .then(([info, bks]) => {
          setBuildInfo(info)
          setBackups(bks)
        })
        .catch(err => message.error(`加载失败: ${err.message}`))
    }, [])

    return (
      <>
        <Statistic title="version" value={`v${buildInfo?.version ?? 'unknown'}`} />
        <Statistic title="backups" value={backups.length} />
      </>
    )

    // ✅ 死代码清理：发现 const [, setConfigVersion] = useState(0) 只 set 不 read → 删除
    ```
  - **配置参数**：`version_source_management` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `forbidden_version_endpoints`（默认 `["/api/config/version"]`，禁止当作版本号使用的端点列表）
    - `forbidden_placeholders`（默认 `["1.0", "0.0.0", "unknown version"]`，禁止作为版本号回退值的占位符）
    - `required_semantic_api`（默认 `"/api/about"`，版本号必须来自的语义对齐 API）
    - `parallel_fetch_required`（默认 `true`，新增元数据 API 调用必须 Promise.all 并行化）
    - `dead_code_cleanup_required`（默认 `true`，修复时必须同步清理只 set 不 read 的 state）
  - **适用**：构建期元数据（版本号/构建时间/git_sha/构建主机）的前端显示；多端点读取同一元数据的场景；前端"版本管理"/"关于"/"系统信息"页面
  - **不适用**：业务数据计数（如备份数/任务数/商品数）；临时调试变量；跨服务边界元数据（应通过专门 API 同步）；核心依赖版本（如 React/AntD 版本，由 package.json 管理）；Pydantic 模型字段（由后端类型系统管理）
  - **历史教训**：版本管理菜单持续显示"V10"。根因链路：前端 `VersionManager.tsx` 调用 `configApi.getVersion()` 拉取 `/api/config/version`，但该端点实际返回 `len(backups)`，受 `BACKUP_KEEP=10` 上限影响永远卡在 10；同时后端 `export_config` 中残留占位符 `"version": "1.0"`。修复：前端改用 `aboutApi.get()` 即 `/api/about` 拿真实 `__version__`，`Promise.all` 并行化避免瀑布；后端 `_safe_app_version()` 辅助函数替代占位符；同步清理 Dashboard 的 `const [, setConfigVersion] = useState(0)` 死代码

- 🆕v4.22【强制】**F-REVIEW-PWA-CACHE-VERIFY：PWA 缓存验证规范**
  - 维度归属：13 PWA 配置
  - 检查项：前端功能不可见时必须从源码→构建产物→sw.js 预缓存清单三层验证
  - 强制要求：
    1. `vite-plugin-pwa` 的 `registerType: 'prompt'` 模式检测到新版本仅弹通知不自动刷新，必须实现 `ReloadPrompt` 组件提示用户刷新
    2. 或改为 `registerType: 'autoUpdate'` 自动激活新版本（无需用户确认）
    3. 部署后必须验证 `sw.js` 预缓存清单包含新 chunk 文件名（如 `BatchRefresh-xxx.js`）
    4. 构建产物必须包含新功能标识（如中文文案「执行历史」），用 `Select-String` 或 `grep` 验证
    5. 构建时间必须晚于源码修改时间，确保构建是最新的
    6. 用户反馈「看不到新功能」时，排查顺序：源码 → 构建产物 → sw.js 预缓存清单 → Service Worker 缓存 → 浏览器缓存
  - 配置节点：`pwa_cache_verify`（verify_layers / register_type / prompt_fallback_required / reload_prompt_component / build_time_check）
  - 适用场景：PWA 项目（vite-plugin-pwa/Workbox）部署后用户反馈「看不到新功能」
  - 不适用场景：无 PWA 的传统部署；htmx 服务端渲染；CSR 无 Service Worker
  - 实战案例：批量采集执行历史 Tab 已在源码和构建产物中正确实现，但用户看不到，原因是 PWA Service Worker 缓存了旧版本 JS 资源，registerType: 'prompt' 模式只弹通知不自动刷新，用户需手动 Ctrl+Shift+R 硬刷新

- 🆕v4.25【强制】**F-REVIEW-THREE-STATE-NULL-SEMANTICS：API 更新接口三态语义检查**
  - 维度归属：API 调用规范
  - 严重等级：warning
  - **检查点**：PATCH/PUT 请求是否正确处理 null 语义
  - **判定标准**：前端发送更新请求时，**清除覆盖字段必须显式传 null（不能省略字段）**，更新字段必须传具体值。**禁止**用"省略字段"代替"传 null"——后端 `exclude_unset=True` 会把省略字段视为"未提交"（保持原值），而 `null` 才是"显式清除覆盖"的语义
  - **检查范围**：所有 `taskApi.update` / `configApi.update` 等 PATCH/PUT 调用
  - **核心机制**（审查时必须理解）：
    - 后端 Pydantic + `exclude_unset=True` 模式下，请求体省略字段 = "未提交" = 保持原值；显式传 `null` = "显式清除覆盖"
    - 前端 `FormData`/payload 构造时，已勾选"恢复默认"/"清除覆盖"的字段必须显式赋 `null`，不能依赖字段省略
    - 后端配合使用 `Optional[T] = None` 但区分"未传"（保持原值）与"null"（清除），需用 `model_dump(exclude_unset=True)` 而非 `exclude_none=True`
  - **判断信号**（grep 检测）：
    - `grep -nE "delete formData\[" frontend/src/pages/**/*.tsx` 命中 → 检查是否应改为 `formData[x] = null`
    - `grep -nE "if \(value\) \{ formData\[" frontend/src/pages/**/*.tsx` 命中 → 检查 else 分支是否应 `formData[x] = null`
    - 用户反馈"清除覆盖不生效，覆盖值仍存在" → 必查前端是否省略字段而非传 null
  - **修复模式**：
    ```typescript
    // ✅ 正确：清除覆盖字段显式传 null
    const payload: Partial<TaskConfig> = { search_config: null }  // 显式 null 清除覆盖
    await taskApi.update(taskId, payload)

    // 禁止：省略字段，后端 exclude_unset=True 视为"未提交"，覆盖不会被清除

    // 禁止：用 undefined 也会被 exclude_unset 过滤掉
    ```
  - **配置参数**：`api_update_semantics` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `three_state_fields`（默认 `["search_config", "filter_config", "score_override", "notify_config"]`，必须显式传 null 才能清除覆盖的字段列表）
    - `clear_override_fields`（默认 `["search_config"]`，"清除覆盖"语义的字段列表）
    - `detection_signals`（默认 `["delete formData[", "omit field in PATCH", "undefined in PATCH payload"]`，触发检查的代码模式）
    - `forbidden_omit_fields`（默认同 `three_state_fields`，禁止在 PATCH 中省略的字段列表）
  - **适用场景**：所有 PATCH/PUT 接口的可选字段（任务级配置覆盖、用户偏好覆盖、商品级配置覆盖、批量配置覆盖）
  - **不适用场景**：POST 创建接口（所有字段都显式传，不存在"省略 = 保持原值"语义）；GET 查询接口（无写入语义）；DELETE 接口（无字段语义）
  - **历史教训**：任务级配置覆盖功能开发时，前端 FormData 的"清除 search_config 覆盖"操作通过 `delete formData.search_config` 实现，导致后端 `exclude_unset=True` 把该字段视为"未提交"，覆盖未被清除，用户反馈"清除不生效"。修复方式：改为 `formData.search_config = null` 显式传 null，后端识别 null 后调用 `clear_override()` 清除覆盖
  - **对应后端原则**：后端 PATCH/PUT 接口必须用 `model_dump(exclude_unset=True)` 区分"未提交"与"显式 null"，禁止用 `exclude_none=True`（会吞掉 null 语义），详见 `xianyu-backend-code-review` v4.26.0 的 `B-REVIEW-EXCLUDE-UNSET-CHECK` / `B-REVIEW-NOT-NULL-NONE-DEFENSE`
