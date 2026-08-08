# 前端模式
> 包含元规范 #15 - #107

## 15. 前端三态反馈规范

所有用户主动触发的异步操作必须实现 **loading → success → error** 三态：

1. `message.loading` 返回 `hide` 函数，在 `then` 和 `catch` 分支都调用 `hide()`
2. 错误提示从 `err.response.data.detail` 提取后端返回的具体错误
3. loading 文案包含资源标识（如 ID 前 8 位）
4. 操作成功后触发数据刷新（`refresh()` / `refetch()`）
5. 禁止 `.catch(() => {})` 静默吞错误

## 29. 前端错误按 error_code 分支（禁止 substring 判断）

> 与 F-REVIEW-ERROR-CODE-BRANCH（frontend 维度 25）对应，本条是后端 + 前端协同的**契约级**元规范。

所有展示后端错误的 UI 组件 + 后端错误响应必须满足：

1. **后端错误响应统一结构**：`{ "error_code": "<reason>", "user_message": "<人类可读>", "detail": "<技术细节>" }`，其中 `error_code` 来自 `config.yaml#failure_reason_propagation.reason_enum` 枚举
2. **前端 switch 分支**：UI 组件用 `switch (err.error_code) { case 'token_expired': ...; case 'anti_crawler': ...; default: ... }` 匹配枚举
3. **禁止 substring 判断**：`if (msg.includes('expired'))` 类反模式禁止（文案变更即失效）
4. **常量集中管理**：前端在 `frontend/src/constants/errorCode.ts` 定义 `ErrorCode` 联合类型与展示文案映射，与后端 `reason_enum` 一一对应
5. **未知 error_code**：降级为通用错误 + `logger.warn` 记录 + 触发运营补登记

**关键约束**：
- 后端响应缺 `error_code` 字段 → 视为**必修 P0 缺陷**（前端无法分支）
- 前端 `if (err.message.includes(...))` → 视为违规（substring 反模式）
- 前端常量文件缺失 `ErrorCode` 类型与后端 `reason_enum` 对应 → 视为**契约不一致**

**判断信号**：
- 后端 `grep "raise HTTPException" <file>` 无 `error_code` 字段 → 视为违规
- 前端 `grep "if\\s*\\(.*\\.message\\.(includes|indexOf|search|match)" <file>` → 视为违规
- 前端 `grep "constants/errorCode\\|ErrorCode =" <file>` 缺对应枚举值 → 视为契约不一致

**适用**：所有展示后端错误的 UI 组件（错误提示/重试按钮/跳转登录）、所有后端 4xx/5xx 响应（除 401/440/441 走认证拦截器外）。
**不适用**：开发环境 `console.error`、本地输入校验（Zod/yup）、HTTP 5xx 网络层错误（统一 toast"网络异常"）。

**历史教训**：多个前端组件用 `if (err.message.includes('expired'))` 判断 Cookie 过期 → 后端文案从「登录已过期」改为「会话已失效」后，所有页面判断失效，统一显示「未知错误」。修复：建立前后端 `error_code` 契约，前端 `switch` 分支，后端响应携带标准化 `error_code` 字段。

## 40. 多字段联动开关范式（MULTI-FIELD-LINKED-SWITCH）🆕v4.34

> 与 B-REVIEW-166（backend 联动开关优先级矩阵）/ F-REVIEW-124（前端联动开关 UI 状态）对应。

多个业务字段叠加生效（如 `mode` 主开关 + `notify_bargain_only` / `auto_buy_bargain_only` 子过滤器）时，必须明确「主开关 → 过滤器」优先级矩阵，主开关失效时子过滤器自动禁用，禁止语义冲突的组合。

1. **优先级矩阵显式声明**：联动字段必须在文档/注释中显式声明「主开关 → 过滤器」优先级矩阵，列出所有合法组合
2. **主开关失效时子过滤器禁用**：主开关为 `notify`（仅通知）时 `auto_buy_*` 过滤器必须自动禁用 + UI 标识不可用
3. **PATCH 三态语义**：PATCH 接口必须用 `exclude_unset=True` 区分「未传 / 传 null / 传值」三态，禁止 0/false 被误判为未传
4. **bool→int 存储**：DB 存储 BOOLEAN 字段时统一用 INTEGER(0/1)，与同类开关字段（如 `use_cron`）保持一致
5. **配置驱动**：优先级矩阵、禁用规则、字段映射从 `config.yaml#linked_switch_priority` 读取

**关键约束**：
- 联动字段无优先级矩阵文档 → 视为 WARNING（语义模糊）
- 主开关 notify 模式但 `auto_buy_*` 未禁用 → 视为 P1（语义冲突）
- PATCH 接口未用 `exclude_unset=True` → 视为违规（三态丢失）
- bool 字段存储为 STRING('true'/'false') → 视为违规（应 INTEGER 0/1）

**判断信号**：
- `grep "mode.*notify\|mode.*auto_buy" <file>` 但无优先级矩阵注释 → 视为可疑
- `grep "exclude_unset.*True\|exclude_unset=True" <file>` PATCH 接口缺此参数 → 视为违规
- `grep "notify_bargain_only\|auto_buy_bargain_only" <file>` 缺 `disabled={.*mode.*===.*notify}` → 视为前端 UI 不规范
- `grep "BOOLEAN\|String.*true.*false" <file>` DB schema 中 bool 字段非 INTEGER → 视为违规

**适用**：多字段叠加生效的业务开关（mode + 子过滤器、enabled + 子配置、auto_* + 限制条件）。
**不适用**：独立开关（无联动）、纯前端 UI 开关（无后端逻辑）、单一布尔开关（无组合语义）。

**历史教训**：任务配置含 `mode` + `notify_bargain_only` + `auto_buy_bargain_only` 三个字段，无优先级矩阵。用户反馈「mode=notify 但 auto_buy_bargain_only=true 是否会触发自动下单」语义模糊。修复：明确优先级矩阵（mode 是主开关，*_bargain_only 是过滤器；mode=notify 时 auto_buy_bargain_only 自动禁用 + UI Tag 标识），PATCH 接口用 `exclude_unset=True` 三态语义，bool→int 存储与 `use_cron` 一致。

## 44. 前端路由三重注册同步（ROUTE-TRIPLE-REGISTRATION）🆕v4.35

> 与 B-REVIEW-174（backend 路由清单与前端注册对齐，v4.35 待落地）/ F-REVIEW-132（前端路由三重注册审查，v4.39 待落地）对应。

新增前端路由（含 SheetWorkspace 多页签应用）必须在「路由声明层 / 多页签注册层 / URL 同步 Hook 层」三处同步注册，禁止只注册一层导致「URL 变了内容不变」或「内容变了 URL 不变」的 UI 错乱。

1. **三重注册清单**：新增路由必须同步注册：
   - L1 路由声明层（如 `App.tsx` 的 `<Route>`）
   - L2 多页签注册层（如 `SheetWorkspace/sheetRegistry.tsx` 的 path → component 映射）
   - L3 URL 同步 Hook 层（如 `useSheetSync.ts` 的 location → sheet 同步逻辑）
2. **query string 保留**：路由携带 query string（如 `?task_id=xxx`）时，L3 Hook 必须 `location.pathname + location.search` 拼接，禁止只取 pathname 丢 query string
3. **路径匹配剥离**：L2 注册层的 `findSheetMeta` 函数必须先剥离 query string 与 hash 再匹配，避免 `?xxx` 干扰精确匹配
4. **配置驱动**：三重注册清单、query string 保留路由列表、路径匹配剥离规则从 `config.yaml#frontend_route_registration` 读取

**关键约束**：
- 新增路由只注册 L1（App.tsx）但未注册 L2（sheetRegistry）→ SheetWorkspace 显示"未打开任何页面"
- L3 Hook 只取 `location.pathname` 不取 `location.search` → query string 丢失，下游组件读不到参数
- L2 `findSheetMeta` 直接用原始 path 匹配（含 query string）→ 精确匹配失败
- 注册清单硬编码在代码中（如 `["/confirm-buy", "/tasks"]`）→ 视为违规（应从 config 读）

**判断信号**：
- `git diff` 显示新增 `<Route path="/<route_name>"` 但同 PR 内 `sheetRegistry` 无对应条目 → L2 同步缺失
- `grep "location.pathname" frontend/src/hooks/useSheetSync.ts` 但无 `location.search` → query string 丢失
- `grep "findSheetMeta" frontend/src/components/SheetWorkspace/` 函数体内无 `split('?')[0]` → 剥离缺失
- 新增路由后用户反馈"URL 变了内容不变"或"内容变了 URL 不变" → 三重同步失败

**适用**：SheetWorkspace 多页签应用中的新增路由；从外部链接（通知 / 邮件 / 二维码）回链进入应用的路由（依赖 query string 传参）；任何 path → component → URL 三层联动的路由系统。
**不适用**：独立路由（如 `/login` 不进入 SheetWorkspace）；纯 Hash 路由（query string 不在 pathname 中）；纯服务端渲染（无前端路由层）。

**历史教训**：新增 `/confirm-buy` 路由（SEMI_AUTO 通知回链）只在 `App.tsx` 注册，未同步到 `sheetRegistry`，导致用户点击通知后 URL 变为 `/confirm-buy` 但页面显示"未打开任何页面，请从左侧菜单选择"。修复：在 sheetRegistry 新增条目 + 修改 `findSheetMeta` 剥离 query string + 修改 `useSheetSync` 保留 query string，三重同步后页面正常渲染。

## 45. 外部回链 query string 保留（QUERY-STRING-RETAIN）🆕v4.35

> 与 B-REVIEW-175（backend 回链 URL 构造审查，v4.35 待落地）/ F-REVIEW-133（前端 query string 保留审查，v4.39 待落地）对应。

从外部链接（通知 / 邮件 / 二维码 / 公网 URL）回链进入应用的路由，必须完整保留 URL 中的 query string（如 `?task_id=xxx&item_id=yyy&error_code=zzz`），禁止 URL 同步 Hook 只取 pathname 丢失 query string，导致下游组件读不到业务参数。

1. **回链路由识别**：从 `config.yaml#external_callback_query_retention.callback_routes` 读取需要保留 query string 的路由列表
2. **URL 拼接规则**：URL 同步 Hook 在计算「当前路径」时必须 `location.pathname + location.search`，依赖数组必须包含 `location.search`
3. **路径匹配剥离**：路径查找函数（如 `findSheetMeta`）必须先 `path.split('?')[0].split('#')[0]` 剥离 query string 与 hash 再匹配
4. **下游消费契约**：回链页面组件必须能从 `useSearchParams` / `useLocation().search` 读取 query string 参数
5. **配置驱动**：回链路由列表、query string 字段名清单、剥离规则从 config 读取

**关键约束**：
- URL 同步 Hook 依赖数组缺 `location.search` → 视为违规（query string 变化不触发同步）
- 路径查找函数未剥离 query string 直接匹配 → 视为违规（带 `?xxx` 的 path 无法精确匹配）
- 回链路由列表硬编码在 Hook 中 → 视为违规（应从 config 读）
- 回链页面组件无法从 `useSearchParams` 读到 query string → 配置契约破裂

**判断信号**：
- `grep "location.pathname" frontend/src/hooks/` 但同函数无 `location.search` → query string 丢失
- `grep "findSheetMeta\|findRouteMeta" frontend/src/` 函数体内无 `split('?')` → 剥离缺失
- `grep "useEffect.*location.pathname" frontend/src/hooks/useSheetSync.ts` 依赖数组无 `location.search` → 依赖不全
- 用户反馈"从通知点击进入页面后参数丢失" → query string 未保留

**适用**：从外部通知 / 邮件 / 二维码 / 公网 URL 回链进入应用的路由（依赖 query string 传 task_id / item_id / error_code / token）；任何 URL 同步 Hook 处理带参数路由的场景。
**不适用**：纯内部导航（用户点击菜单，无 query string）；纯 `:param` 路径参数路由（参数在 pathname 中）；纯 Hash 路由（query string 不在 pathname 中）；纯服务端路由（无前端 Hook 层）。

**历史教训**：`/confirm-buy?task_id=xxx&item_id=yyy` 回链路由，`useSheetSync` 计算路径时只用 `location.pathname`，丢失 `?task_id=xxx`，导致 `ConfirmBuy` 组件读 `useSearchParams` 时 task_id 为 null，无法加载确认抢单数据。修复：path 改为 `location.pathname + location.search`，依赖数组加入 `location.search`，并建立 #45 强制保留规则。

## 56. 过滤结果透明化 UI（FILTER-RESULT-TRANSPARENCY-UI）🆕v4.37

> 与维度 7 API 契约（F-REVIEW-147）对应。

列表查询 UI 同时有 ≥2 个过滤参数（价格区间 + 市场比例 + 任务范围）时，必须透明化展示当前生效的过滤规则组合，否则用户无法理解"为何查不到数据"。

**与 #40 MULTI-FIELD-LINKED-SWITCH 的边界**：
- #40 关注"字段间联动 UI 禁用标识"（开关 disabled 状态）
- 本规范关注"过滤结果透明化展示"（数据被过滤的可见性）

1. **Tooltip 说明**：关键过滤参数提供 Tooltip 说明查询规则（如"价格区间 + 低于市场参考价参数取值"）
2. **filter_summary 三态**：空结果时区分"无数据"vs"被过滤排除"vs"全部数据"三种状态
3. **当前过滤组合展示**：UI 显式列出当前生效的过滤参数组合（如"当前过滤：价格 600-800 + 市场比例 ≤0.85"）
4. **参数语义化**：业务参数（如 `market_ratio` 0.85）应展示语义化文案（如"低于市场参考价 15%"）

**关键约束**：
- UI 同时有 ≥2 个过滤参数但无 tooltip / filter_summary → 透明化不足
- 空结果统一显示"暂无数据"不区分原因 → 违规
- 过滤参数展示仅显示数值不显示语义 → 不友好

**判断信号**：
- `grep "filter.*range\|market.*ratio\|min.*max"` 在列表 UI 但无 `Tooltip` / `filter_summary` → 违规
- `grep "empty.*data\|no.*data"` 但无 `filtered_count` / `total_count` 区分 → 违规
- 参数展示仅 `value` 无 `label` / `description` → 不友好

**适用**：所有多参数列表查询 UI（评估明细 / 商品列表 / 订单列表 / 仪表盘过滤）
**不适用**：单一过滤参数（如仅搜索关键字）、用户主动输入的查询条件（用户已知）、详情页（无过滤）

**历史教训**：用户调整"低于市场参考价"到 0.85 后，评估明细菜单仍能查出价格上限 800 的商品，且 UI 无任何提示当前生效的过滤规则。用户误以为是价格范围 600-800 的问题，实际是 market_ratio 过滤未生效。修复：在价格范围 label 处添加 `QuestionCircleOutlined` 图标 + Tooltip 说明查询规则（价格区间 + 低于市场参考价参数取值）。

> 📖 详见 [frontend-ui.md](../assets/guides/coding-rules/frontend-ui.md) step 193。

---

# 异步与资源安全元规范（57-63）🆕v4.38.0

> 基于 2026-07-08 解决的「async/await 误用、NullPool 性能问题、HTTP 状态码语义模糊、CSS 选择器失效、异常日志丢失 traceback、并发安全 page closure、参数传递缺失、日志质量退化链」8 类问题，使用 Sequential Thinking 8 步复盘法（问题识别 → 根因分析 → 修复方案 → 验证 → 影响评估 → 规范候选 → 落地决策 → 内容设计），新增 7 条元规范（meta-rules #57-63），元规范总数从 56 → 63。
>
> 命名空间与配置驱动：所有阈值（`async_await_check` / `resource_pool_benchmark` / `http_status_code_mapping` / `css_selector_fallback` / `exception_log_semantic` / `external_resource_lifecycle` / `db_write_identity_trace`）均在 `config.yaml` 对应节点管理，禁止硬编码。
>
> 编号说明：step 198-204 / B-REVIEW-182-188 / F-REVIEW-148-151。

## 64. URL↔状态同步失败回退（URL-STATE-SYNC-FALLBACK）🆕v4.39 experimental

> 与 F-REVIEW-152（前端 URL↔状态同步失败回退审查）对应。后端无此场景，不新增 B-REVIEW。

SheetWorkspace 多页签应用中，URL 变化触发 `openSheet` 失败时（路径未注册 / 栈满），URL 已改变但 activeId 未变，导致 `useParams()` 返回错误值，业务逻辑误判。必须在 `openSheet` 失败时回退 URL 到当前 active sheet 的 path，保持 URL 与 active sheet 一致。

1. **失败时 URL 回退强制**：`useSheetSync` Hook 在 `openSheet` 失败时（`!result.ok`）必须调用 `navigate(activeSheet.path, { replace: true })` 回退 URL
2. **activeSheet 存在性检查**：回退前必须检查 `activeSheet` 是否存在（可能首次加载无 activeId），不存在则跳过回退
3. **replace 参数强制**：回退必须用 `{ replace: true }` 避免污染浏览器历史记录
4. **防循环检查保留**：回退后 `activeSheet.path === URL`，防循环检查（第 40 行）会跳过，不会死循环
5. **配置驱动**：回退开关、回退策略（replace / push）、允许回退的 reason 清单从 `config.yaml#url_state_sync_fallback` 读取

**关键约束**：
- `useSheetSync` Hook 缺 `navigate` 引入 → 视为 WARNING（无法回退）
- `openSheet` 失败时无 URL 回退逻辑 → 视为 CRITICAL（URL 漂移导致业务误判）
- 回退未用 `{ replace: true }` → 视为 WARNING（污染历史记录）
- 回退前未检查 `activeSheet` 存在性 → 视为 WARNING（空指针风险）

**判断信号**：
- `grep "useSheetSync" frontend/src/hooks/` 但无 `useNavigate` 引入 → 缺 navigate
- `grep "!result.ok" frontend/src/hooks/useSheetSync.ts` 但无 `navigate(activeSheet.path)` → 缺回退逻辑
- `grep "navigate\(.*\)" frontend/src/hooks/useSheetSync.ts` 但无 `replace: true` → 缺 replace 参数

**适用**：SheetWorkspace 多页签应用（URL ↔ sheet 栈双向同步）、URL 参数驱动的页面状态（如 `useParams().id` 判断编辑/新增模式）、外部链接回链场景（通知点击、邮件链接、二维码）。
**不适用**：纯静态路由（无状态同步）、无 URL 参数的页面（无 useParams 依赖）、独立路由（如 `/login` 不进入 SheetWorkspace）、传统 MPA（后端渲染无前端状态）。

**反模式**：
```typescript
// ❌ openSheet 失败时 URL 已改变但 activeId 不变，useParams 漂移
useEffect(() => {
  const path = location.pathname + location.search
  const activeSheet = sheets.find((s) => s.id === activeId)
  if (activeSheet?.path === path) return
  const result = openSheetWithNotification(path)
  // 缺失败时 URL 回退，导致 isEdit 误判
}, [location.pathname, location.search, sheets, activeId])
```

**正确模式**：
```typescript
// ✅ openSheet 失败时回退 URL 到 active sheet 的 path
import { useNavigate } from 'react-router-dom'

export function useSheetSync(): void {
  const location = useLocation()
  const navigate = useNavigate()
  const sheets = useSheetStore((s) => s.sheets)
  const activeId = useSheetStore((s) => s.activeId)

  useEffect(() => {
    const path = location.pathname + location.search
    const activeSheet = sheets.find((s) => s.id === activeId)
    if (activeSheet?.path === path) return
    const result = openSheetWithNotification(path)
    // openSheet 失败时回退 URL 到当前 active sheet 的 path
    if (!result.ok && activeSheet) {
      navigate(activeSheet.path, { replace: true })
    }
  }, [location.pathname, location.search, sheets, activeId, navigate])
}
```

**历史教训**：任务修改流程中点击 Step 3「全局搜索配置」按钮，`navigate('/app/config/search')` 多了 `/app` 前缀（basename），`findSheetMeta('/app/config/search')` 返回 undefined，触发 React Router `*` 重定向到 `/`。此时 URL 变为 `/`，但 activeId 仍指向 TaskEditor，`useParams().id` 返回 undefined，`isEdit` 误判为 false，提交时创建重复任务。修复：(1) Step 3 改为打开 Modal（避免 navigate）；(2) `useSheetSync` 在 `openSheet` 失败时回退 URL。

> 📖 详见 [state-management.md](../assets/guides/coding-rules/state-management.md) step 205（预沉淀）。

## 65. Service Worker 缓存版本同步（SW-CACHE-VERSION-SYNC）🆕v4.39 experimental

> 与 F-REVIEW-153（前端 SW 缓存版本同步审查）对应。后端无此场景，不新增 B-REVIEW。

PWA 应用使用 Service Worker 缓存静态资源，构建时生成的版本哈希（如 `sw.js` 中的 `precaching-manifest`）必须与前端运行时检测的版本一致。版本不一致时（如用户浏览器缓存旧 `sw.js`），必须触发 `skipWaiting()` 强制更新，避免旧版本页面功能异常。

1. **构建时版本哈希**：`vite-plugin-pwa` 构建时在 `sw.js` 中生成版本哈希（`self.__WB_MANIFEST` 中的文件哈希）
2. **运行时版本检测**：前端启动时（`main.tsx` 或 `App.tsx`）读取 `navigator.serviceWorker.controller` 的版本，与当前构建版本对比
3. **skipWaiting 强制更新**：版本不一致时调用 `registration.waiting?.postMessage({ type: 'SKIP_WAITING' })` 触发 `skipWaiting()`
4. **硬刷新提示**：`skipWaiting` 后显示「新版本已就绪，点击刷新加载」提示，用户确认后 `window.location.reload()`
5. **配置驱动**：版本检测开关、硬刷新提示文案、skipWaiting 触发策略从 `config.yaml#sw_cache_version_sync` 读取

**关键约束**：
- `sw.js` 缺版本哈希 → 视为 WARNING（无法检测版本差异）
- 前端启动时无版本检测逻辑 → 视为 WARNING（无法触发强制更新）
- 版本不一致时无 `skipWaiting` 触发 → 视为 CRITICAL（用户功能异常）
- 缺硬刷新提示直接 `reload()` → 视为 WARNING（用户体验突兀）

**判断信号**：
- `grep "self.__WB_MANIFEST\|precaching-manifest" frontend/dist/sw.js` 缺失 → 缺版本哈希
- `grep "navigator.serviceWorker.getRegistration" frontend/src/` 缺失 → 缺版本检测
- `grep "SKIP_WAITING\|skipWaiting" frontend/src/` 缺失 → 缺强制更新逻辑
- `grep "新版本.*刷新\|版本已更新" frontend/src/` 缺失 → 缺硬刷新提示

**适用**：PWA 应用（使用 Service Worker 缓存）、SPA 应用（单页应用前端构建）、依赖 Service Worker 缓存的离线应用、频繁迭代的前端项目（版本更新快）。
**不适用**：传统 MPA 应用（每次加载最新 HTML）、无 Service Worker 的应用、纯静态站点（无动态内容）、测试环境（版本检测关闭）。

**反模式**：
```typescript
// ❌ 无版本检测逻辑，用户浏览器缓存旧 sw.js 导致功能异常
// main.tsx 直接注册 SW，不检测版本
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js')
}
```

**正确模式**：
```typescript
// ✅ 构建时生成版本哈希 + 运行时版本检测 + skipWaiting 强制更新
// vite.config.ts
VitePWA({
  strategies: 'generateSW',
  manifest: { /* ... */ },
  workbox: {
    skipWaiting: true,
    clientsClaim: true,
  },
})

// main.tsx
async function checkSWUpdate() {
  if (!('serviceWorker' in navigator)) return
  const registration = await navigator.serviceWorker.getRegistration()
  if (registration?.waiting) {
    // 版本不一致，显示硬刷新提示
    const userConfirmed = confirm('新版本已就绪，点击刷新加载')
    if (userConfirmed) {
      registration.waiting.postMessage({ type: 'SKIP_WAITING' })
      window.location.reload()
    }
  }
}
checkSWUpdate()
```

**历史教训**：PC 端首次登录后重定向到 `/app/m/`（移动端），根因是浏览器缓存了旧版 `sw.js`，旧版 SPA 中 `useMobileDetect.ts` 用 `pointer:coarse` 触屏判断导致 PC 端误判为移动端。修复：(1) 修复 `useMobileDetect.ts` 移除 `pointer:coarse` 判断；(2) 构建新 SPA 生成新 `sw.js` 哈希；(3) 用户需硬刷新（Ctrl+Shift+R）清除 Service Worker 缓存。预防：添加版本检测 + `skipWaiting` 强制更新逻辑。

> 📖 详见 [frontend-ui.md](../assets/guides/coding-rules/frontend-ui.md) step 206（预沉淀）。

## 67. 移动端检测多重 fallback 强制要求（MOBILE-DETECT-MULTI-FALLBACK）🆕v4.41.0

> 与 F-REVIEW-155（前端移动端检测 Hook 审查）对应。本规则解决「设备仿真模式下单一触摸检测属性失效导致移动端路由不跳转」问题。

**问题背景**：iPadOS 13+ 设备 UA 伪装为桌面 macOS，移动端检测依赖 `'ontouchend' in document` 判断触摸能力，但 Chrome DevTools / Playwright 设备仿真模式下该属性可能未被正确设置，导致 Macintosh UA 分支检测失败，页面不跳转到移动端路由。

**核心原则**：
1. **多重 fallback**：移动端检测的触摸判断必须至少有 2 个独立检测属性（如 `ontouchend` + `maxTouchPoints`），任一为 true 即判为触摸设备
2. **仅限 Macintosh 分支**：fallback 仅在 Macintosh UA 分支生效，避免触屏笔记本（Surface 等）误判为移动端
3. **属性优先级**：`ontouchend` 优先（真实设备最可靠），`maxTouchPoints > 0` 作为 fallback（仿真模式下更稳定）
4. **禁止 pointer:coarse**：触屏笔记本/二合一设备会触发 coarse，但视口宽度通常 ≥1024，误判为移动端会导致桌面用户被强制跳到 /m/ 路由

**判断信号（grep / 静态检查）**：
- `grep "ontouchend.*in.*document" frontend/src/` 命中但同文件无 `maxTouchPoints` → 触摸检测缺少 fallback，视为 CRITICAL
- `grep "Macintosh.*ontouchend" frontend/src/` 但无 `maxTouchPoints` → iPadOS 13+ 检测不完整
- `grep "pointer.*coarse\|matchMedia.*pointer" frontend/src/mobile/` → 触屏笔记本误判风险

**配置驱动**：
- 触摸检测属性列表在 `config.yaml#mobile_detect.touch_detection_properties` 管理
- Macintosh UA 正则在 `config.yaml#mobile_detect.macintosh_pattern` 管理
- 视口阈值在 `config.yaml#mobile_detect.viewport_max_width` 管理

**适用场景**：
- React SPA 移动端路由跳转检测（useMobileDetect / useIsMobile）
- iPadOS 13+ 设备兼容性
- Chrome DevTools / Playwright 设备仿真模式测试
- PWA 应用移动端适配

**不适用场景**：
- 纯 CSS 响应式布局（无 JS 检测逻辑）
- SSR 应用（路由由服务端控制）
- 非 Macintosh UA 设备（Android/iPhone 直接由 UA 正则匹配）

**复盘来源**：设备仿真模式下 iPad Pro 页面不跳转到移动端路由。根因：`'ontouchend' in document` 在仿真模式下为 false，且无 `maxTouchPoints` fallback。修复：在 `isMobileUA()` 和 `detectMobile()` 两个函数中增加 `navigator.maxTouchPoints > 0` 作为 fallback。

## 68. 响应式断点统一规范（RESPONSIVE-BREAKPOINT-UNIFY）🆕v4.41.0

> 与 F-REVIEW-156（前端响应式断点一致性检查）对应。本规则解决「多个移动端检测 Hook 和 CSS 媒体查询使用不同断点阈值，导致同一视口宽度下路由跳转与 UI 布局不一致」问题。

**问题背景**：项目中存在两套移动端检测 Hook（useMobileDetect 600px + useIsMobile 767px）和 CSS 媒体查询（768px），阈值不一致导致：
- 600-767px 区间：useMobileDetect 判为桌面（不跳转 /m/），但 useIsMobile 判为移动端（UI 响应式生效）
- 600px 以下：三者一致判为移动端
- 这种不一致在设备仿真模式下尤为明显

**核心原则**：
1. **路由跳转阈值独立于 UI 响应式阈值**：路由跳转（useMobileDetect）的视口阈值可以小于 UI 响应式（useIsMobile）阈值，因为路由跳转有更强副作用（强制导航到 /m/）
2. **阈值差异必须显式声明**：若两个 Hook 阈值不同，必须在代码注释和 config.yaml 中显式声明差异原因
3. **CSS 媒体查询与 UI Hook 对齐**：useIsMobile 的 matchMedia 断点必须与 CSS `@media` 断点一致（均为 767px/768px）
4. **阈值配置化**：所有断点阈值从 config.yaml 读取，禁止硬编码

**判断信号（grep / 静态检查）**：
- `grep "MOBILE_VIEWPORT_MAX\|viewport_max_width" frontend/src/` 与 `grep "767\|768" frontend/src/` 值不同 → 阈值不一致，需显式声明
- `grep "max-width.*767\|max-width.*768\|max-width.*600" frontend/src/` 多个不同值 → CSS 断点分散
- useMobileDetect 阈值与 useIsMobile 阈值差 > 100px → 可能导致行为不一致区间过大

**配置驱动**：
- 路由跳转阈值：`config.yaml#mobile_detect.viewport_max_width`（600px，有明确副作用说明）
- UI 响应式阈值：`config.yaml#mobile_detect.ui_responsive_max_width`（767px，与 antd 对齐）
- CSS 媒体查询断点：`config.yaml#mobile_detect.css_media_breakpoint`（768px，与 UI Hook +1 对齐）

**适用场景**：
- 多 Hook + 多 CSS 断点的 React SPA 项目
- 路由跳转与 UI 响应式需要不同阈值的场景
- Ant Design 等 UI 框架有固定断点的项目

**不适用场景**：
- 单一检测 Hook + 单一 CSS 断点（无一致性问题）
- 纯服务端渲染（无客户端路由跳转）
- 纯 CSS 响应式（无 JS 检测逻辑）

**复盘来源**：useMobileDetect（600px）控制路由跳转，useIsMobile（767px）控制桌面响应式，CSS @media（768px）控制样式适配。三者阈值不一致，在 600-767px 区间行为割裂。

## 69. 设备仿真模式验证清单（DEVICE-EMULATION-CHECKLIST）🆕v4.41.0

> 与 xianyu-auto-testing 技能的全面测试模式步骤 2 对应。本规则确保设备仿真测试的完整性和可靠性。

**问题背景**：Playwright MCP 的 `playwright_resize` 设备预设只调整视口尺寸和部分设备属性，但不修改 `navigator.userAgent` 和 `navigator.maxTouchPoints`，导致仿真测试无法覆盖真实设备行为，需要额外的验证策略。

**核心原则**：
1. **仿真三要素验证**：设备仿真测试必须验证 UA、maxTouchPoints、innerWidth 三者是否与目标设备一致
2. **UA 不一致时 fallback 验证**：若仿真工具无法修改 UA，必须通过 JS 属性覆盖模拟真实设备环境，验证 fallback 逻辑
3. **桌面端防误判必测**：每次修复移动端检测后，必须验证桌面端（≥1280px）不会被误判为移动端
4. **多设备覆盖**：至少覆盖窄屏手机（≤390px）、宽屏平板（≥834px）、桌面（≥1280px）三个典型场景

**判断信号（测试流程检查）**：
- 测试报告中无 `navigator.maxTouchPoints` 检查 → 设备仿真验证不完整
- 测试报告中无桌面端防误判结果 → 缺少必要验证
- 测试仅用 `playwright_resize` 而无 JS 属性覆盖验证 → UA 依赖的检测逻辑未真正测试
- 修复移动端检测后未重新构建部署 → 测试对象不是修复后代码

**配置驱动**：
- 设备预设列表：`config.yaml#browser_automation.playwright_mcp.device_presets`（多设备）
- JS 属性覆盖脚本模板：`config.yaml#browser_automation.playwright_mcp.ua_override_script_template`
- 防误判视口宽度：`config.yaml#browser_automation.playwright_mcp.desktop_viewport_width`

**适用场景**：
- Playwright / Puppeteer 设备仿真测试
- Chrome DevTools Device Mode 测试
- 需要验证 iPadOS 13+ 等 UA 伪装设备的场景

**不适用场景**：
- 真实设备测试（UA/maxTouchPoints 自然正确）
- 纯视觉回归测试（不涉及 JS 检测逻辑）
- 后端 API 测试（无浏览器环境）

**复盘来源**：Playwright `playwright_resize` iPad Pro 预设下 UA 仍为 Windows、maxTouchPoints=0，无法直接仿真 iPadOS 13+。需通过 `Object.defineProperty` 覆盖 navigator 属性来验证 maxTouchPoints fallback 修复。

## 83. UI 操作项分级保留与多视图一致性（UI-ACTION-TIER-RETAIN-AND-MULTI-VIEW-CONSISTENCY）🆕v4.49.0

> **experimental 标签**：本规则基于单一 UI Bug 复盘沉淀，需更多案例验证才能升级为正式规则。当前作为推荐性规范执行，季度复盘时评估升级条件。

**问题背景**：任务管理页面（TaskList.tsx）操作列同时承载 6 个文字按钮（编辑/启停/停止/复制/另存为模板/删除），在窄屏或默认列宽下操作列总宽度约 580px，超出页面样式边界导致按钮被挤压换行、视觉错乱。根因是缺少"操作项分级保留"的硬性约束——所有按钮一律以文字按钮平铺，没有按使用频率分级（高频保留文字 / 中频图标 / 低频收入 Dropdown 等收起容器），也没有横向滚动 fallback 容错。同 Bug 同时暴露另一问题：表格视图与卡片视图对同一行操作按钮做了两套实现，修改时容易遗漏同步，造成多视图模式行为分裂。

**核心原则**：
1. 操作项分级保留范式：当单行/单卡操作按钮总数 > `uiLayout.actionButtonVisibleThreshold`（默认 5）时，必须按使用频率分级：
   - 高频（≥ `lowFrequencyThresholdPerMonth` 次/月）：保留为文字按钮
   - 中频（< 阈值但有快捷需求）：转为图标按钮 + Tooltip
   - 低频（< 阈值且无快捷需求）：收入收起容器（Dropdown/Popover/Drawer）
2. 收起容器选择策略由 `uiLayout.collapseContainerStrategy` 配置驱动（≤3 → Dropdown / 3-6 → Popover / >6 → Drawer），禁止在代码中硬编码选择逻辑
3. 多视图模式一致性：表格视图与卡片视图对同一资源的操作集合必须**完全一致**（按钮数量、文案、handler 行为、disabled 条件），禁止分叉实现
4. 横向溢出容错：所有 Table 必须显式声明 `scroll={{ x: <minWidth 或 'max-content'> }}`，作为分级保留失败时的最后兜底，避免按钮被挤压换行

**判断信号**：
- 单个 `<Space>` / `actions=` 内文字按钮 ≥ `actionButtonVisibleThreshold`（默认 5）→ 必须分级
- `grep "<Button" <page>.tsx` 计数 ≥ 6 且无 `<Dropdown` / `<Popover` / `<Drawer` → 违规
- 同一页面存在 `<Table` 与 `<Card` 两套视图，但只有一处修改了操作按钮 → 违反多视图一致性
- `grep "scroll=" <page>.tsx` 无匹配 → 缺少横向滚动 fallback

**配置驱动**：
- `uiLayout.enabled`：是否启用（默认 true）
- `uiLayout.actionButtonVisibleThreshold`：文字按钮可见阈值（默认 5）
- `uiLayout.lowFrequencyThresholdPerMonth`：低频判定阈值（默认 1）
- `uiLayout.collapseContainerStrategy`：收起容器选择策略（le3/3to6/gt6 三档）
- `uiLayout.scrollFallback`：横向滚动策略（默认 'max-content'）
- `uiLayout.multiViewSyncRequired`：多视图同步要求（默认 true）
- `uiLayout.multiViewSyncScanGlob`：扫描的文件 glob（默认 `frontend/src/pages/**/*.tsx`）
- `uiLayout.tableViewMatchers` / `uiLayout.cardViewMatchers`：识别表格视图/卡片视图的特征字符串
- 禁止在组件代码中硬编码阈值或容器选择逻辑

**适用场景**：
- 列表页操作列按钮过多导致水平空间溢出（任务管理、订单管理、商品管理）
- 同一资源在表格视图 + 卡片视图双视图呈现的场景
- AntD `<Table>` 的 columns render 中承载多个操作按钮的场景
- 移动端窄屏下的操作列收起需求（自适应缩窄到 < 阈值的一半时）

**不适用场景**：
- 单个详情页的固定操作栏（无横向溢出风险）
- 操作按钮总数 ≤ 阈值（无需分级）
- 仅有一种视图的页面（无多视图同步需求）
- 表单提交按钮组（主/次按钮天然分级，无需走此规则）

**与其他规则区别**：
- 与 #67（移动端检测多重 fallback）的区别：#67 关注设备类型识别；#83 关注操作按钮的分级保留
- 与 #68（响应式断点统一）的区别：#68 关注 CSS 断点与 Hook 阈值对齐；#83 关注操作列在溢出时的分级策略
- 与 step 162（LAYOUT-01 布局响应式与最小宽度规范）的配合：step 162 定义容器最小宽度；#83 定义操作列内部的分级保留
- 与 step 14（多视图切换与 state 提升）的配合：step 14 关注视图切换的 state 同步；#83 关注多视图下操作按钮集合的一致性

**复盘来源**：TaskList.tsx 操作列 6 个文字按钮溢出页面样式 Bug（2026-07-18 修复）。根因：操作列未按使用频率分级，"另存为模板"作为低频操作却占用一个文字按钮位置；同时 Table 缺少 `scroll` fallback。修复：将"另存为模板"收入 Dropdown 更多菜单（操作列从 6 个文字按钮减为 5 个 + 1 个图标按钮），Table 显式声明 `scroll={{ x: 'max-content' }}`，表格视图与卡片视图同步修改。

## 95. SPA 渲染容错体系（SPA-RENDER-RESILIENCE）🆕v4.61.0

> 与 F-REVIEW-217~221（前端 SPA 渲染容错审查）/ step 254~258（frontend-ui.md）/ step 259~261（testing.md）对应。
> 与 #83（UI 操作项分级保留与多视图一致性）的区别：#83 关注"UI 操作项与视图一致性"；#95 关注"SPA 渲染期异常的捕获、隔离与恢复"。
> 与 #85（关键路径可观测性与状态同步三要素）的区别：#85 关注"可观测性与状态重置"；#95 关注"渲染容错三件套（ErrorBoundary + lazyRetry + 路由隔离）+ 401 防抖"。

**问题背景**：本次对话中 React SPA 切换菜单时有 5-10% 概率白屏，刷新后恢复。经 Chrome DevTools 分析识别 5 类根因：① 缺少全局 ErrorBoundary，渲染异常冒泡到 React 顶层导致整页白屏；② 懒加载 chunk 失效（部署后旧 hash 404）无重试机制；③ 未保护的数据访问（`data.list[0].name` 未判空）；④ 401 拦截器硬跳转（`window.location.href`）在并发请求时多次跳转中断渲染；⑤ 路由级错误无隔离，单页错误使整个应用不可用。这是一个典型的 SPA 渲染容错体系缺失问题——缺少分层错误捕获、加载失败重试、数据访问防御、跳转防抖、错误隔离五道防线。

**核心原则**：
1. **渲染容错三件套【强制】**：全局 ErrorBoundary（兜底所有渲染异常）+ lazyRetry 包装（chunk 失效自动重试）+ 路由级 ErrorBoundary（隔离单路由错误），三者必须同时存在分层防御。
2. **resetKeys 仅限基本类型【强制】**：ErrorBoundary 的 `resetKeys` 只能放 `string`/`number`/`boolean`，禁止放对象/数组引用（引用每次渲染变化触发误重置）。
3. **数据访问防御性兜底【强制】**：组件渲染期访问 API 响应必须用可选链（`?.`）+ 空数组兜底（`?? []`），禁止假设响应结构一定完整。
4. **401 拦截器防抖【强制】**：401 跳转必须用模块级标志防抖 + `window.location.replace`（不留历史），禁止每个 401 都触发 `window.location.href` 跳转。
5. **测试环境预检【强制】**：运行 vitest 前必须预检安装状态，tsconfig 必须排除测试文件，antd v5 中文按钮断言必须兼容自动空格。

**判断信号**：
- `grep "BrowserRouter" frontend/src/App.tsx` 附近无 `<ErrorBoundary>` 包裹 → 缺全局 ErrorBoundary
- `grep "React.lazy" frontend/src/` 命中裸用（未包 lazyRetry）→ 缺 chunk 重试
- `grep "<Route" frontend/src/` 附近无 `<ErrorBoundary>` 包裹 → 缺路由级隔离
- 组件含 `data.xxx.yyy` 链式访问无 `?.` → 缺防御性兜底
- `grep "location.href" frontend/src/api/` 命中 401 拦截器 → 缺防抖
- 用户反馈"切菜单偶发白屏，刷新后恢复" → 典型症状

**配置驱动**：
- `spa_render_resilience.globalErrorBoundary.enabled`：是否强制全局 ErrorBoundary（默认 true）
- `spa_render_resilience.globalErrorBoundary.resetKeyTypeWhitelist`：resetKeys 允许的类型（默认 `['string', 'number', 'boolean']`）
- `spa_render_resilience.lazyRetry.enabled`：是否强制 lazyRetry 包裹（默认 true）
- `spa_render_resilience.lazyRetry.maxRetries`：最大重试次数（默认 3）
- `spa_render_resilience.lazyRetry.chunkErrorPatterns`：chunk 失败错误模式列表
- `spa_render_resilience.routeErrorBoundary.enabled`：是否强制路由级 ErrorBoundary（默认 true）
- `spa_render_resilience.apiArrayDefense.enabled`：是否强制数组访问判空（默认 true）
- `spa_render_resilience.http401Debounce.enabled`：是否强制 401 防抖（默认 true）
- `spa_render_resilience.http401Debounce.redirectMethod`：跳转方法（默认 replace）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 所有 React SPA 项目（含路由 + 懒加载 + API 调用）
- CI/CD 频繁部署导致 chunk hash 变更的项目
- 含认证的 SPA（401 拦截器）
- 路由切换频繁的应用

**不适用场景**：
- SSR 应用（错误处理与跳转策略不同）
- 纯静态页面无路由无 API
- 无认证的公开 API（无 401 拦截器）

**与其他规则区别**：
- 与 #83（UI 操作项分级保留与多视图一致性）的区别：#83 关注"UI 操作项与视图一致性"；#95 关注"SPA 渲染期异常的捕获、隔离与恢复"
- 与 #85（关键路径可观测性与状态同步三要素）的区别：#85 关注"可观测性与状态重置"；#95 关注"渲染容错三件套 + 401 防抖"
- 与 step 249（React 组件复用状态同步重置）的区别：step 249 关注"组件复用时重置内部状态"；#95 关注"渲染异常的分层捕获与恢复"

**复盘来源**：2026-07-22 闲鱼猎人前端 React SPA 间歇性白屏修复。根因链：
1. 缺少全局 ErrorBoundary，渲染异常冒泡到 React 顶层导致整页白屏
2. 懒加载 chunk 失效（部署后旧 hash 404）无重试机制，直接白屏
3. 未保护的数据访问（`data.list[0].name` 未判空），后端返回非预期结构时抛异常
4. 401 拦截器用 `window.location.href` 跳转，并发请求多次跳转中断渲染
5. 路由级错误无隔离，单页错误使整个应用（含 Header/Sidebar）白屏

修复：
1. 添加全局 ErrorBoundary 包裹 `<BrowserRouter>`，resetKeys 用基本类型
2. 实现 `lazyRetry` 高阶函数包裹 `React.lazy`，sessionStorage 计数 + maxRetries
3. 路由级 ErrorBoundary 包裹 `<Outlet>`，resetKeys 绑定 `location.pathname`
4. API 响应防御性兜底：可选链 + 空数组兜底 + 前置判空
5. 401 防抖：模块级 `isRedirecting` 标志 + `window.location.replace`
6. 测试踩坑修复：vitest 预检、tsconfig 排除测试文件、antd 中文按钮空格兼容

对应 step 254~258（frontend-ui.md）+ step 259~261（testing.md）。

## 96. 多写入路径状态一致性检查（MULTI-WRITE-PATH-STATE-CHECK）🆕v4.60.0

**问题**：同一状态被多个写入路径（Zustand store 方法 + API 回调 + 定时器）修改时，写入顺序和条件不一致导致状态冲突。

**核心规则**：
1. 同一状态的所有写入路径必须经过单一调度函数，禁止各自直接修改状态
2. 多写入路径的优先级与互斥关系必须在配置中声明
3. 写入路径变更时必须同步更新所有调用方

**判断信号**：`grep` 发现同一 state 字段在 ≥2 处被 `setState` / `updateState` / `store.method` 修改 → 必须检查一致性

**配置参数**：`multi_write_path_check` 节点（enabled / stateFields / dedupMethod / priorityOrder）

**适用**：Zustand store 多方法操作同一字段、API 回调与定时器同时更新状态
**不适用**：单写入路径的状态、纯派生计算字段

**历史教训**：Cookie 状态被 `sync_state()` 和 `import_from_browser()` 两条路径分别修改，`sync_state` 写入 `valid=True` 但 `import_from_browser` 只写 `token` 未更新 `valid`，导致状态不一致。修复后提取 `_apply_cookie_update()` 单一调度函数。

## 97. UI 偏好持久化检查（UI-PREFERENCE-PERSISTENCE-CHECK）🆕v4.60.0

**问题**：用户 UI 偏好（主题色、CDP 模式开关、视图模式）用 `useState` 存储导致页面刷新后丢失。

**核心规则**：
1. 跨刷新需保留的偏好必须使用 `usePersistentState` / `localStorage`，禁止 `useState` 存储持久化偏好
2. 偏好关键词识别：`mode` / `theme` / `layout` / `view` / `collapsed` / `expanded` / `visible` / `enabled`
3. 禁止自行实现 localStorage 读写，必须复用项目 `usePersistentState` hook

**判断信号**：`useState` 的 key 名含偏好关键词 → 检查是否需要跨刷新持久化

**配置参数**：`ui_preference_persistence` 节点（enabled / preferenceKeywords / persistenceHookName / keyNamingPattern）

**适用**：用户手动切换的 UI 偏好（主题/模式/布局/展开状态）
**不适用**：临时交互状态（加载中/hover/焦点）、服务端数据同步状态

**历史教训**：AntiCrawl/index.tsx 的 CDP 模式开关用 `useState(false)`，刷新后状态重置为关闭，用户每次需重新开启。修复后改用 `usePersistentState('anticrawl-cdp-mode', false)`。

## 98. storage 错误处理检查（STORAGE-ERROR-HANDLING-CHECK）🆕v4.60.0

**问题**：localStorage/sessionStorage 在隐私模式、存储配额满、跨域 iframe 等场景下会抛异常，未做 try/catch 导致白屏。

**核心规则**：
1. 所有 `localStorage` / `sessionStorage` 读写必须 try/catch 包裹
2. 写入失败降级为内存存储 + `logger.warning` 告警
3. 读取失败返回默认值，不抛异常

**判断信号**：代码含 `localStorage.setItem` / `localStorage.getItem` / `sessionStorage` → 必须检查是否有 try/catch

**配置参数**：`storage_error_handling` 节点（enabled / fallbackToMemory / logLevel / quotaExceededRetries）

**适用**：所有 localStorage/sessionStorage 操作
**不适用**：Node.js 环境（无 localStorage）、Web Worker（无 localStorage）

**历史教训**：Safari 隐私模式下 `localStorage.setItem` 抛 QuotaExceededError，`usePersistentState` 未做 try/catch，导致页面白屏。

## 102. 多写路径状态检查+UI偏好持久化+storage错误处理三合一（MULTI-WRITE-PERSIST-STORAGE-TRIPLE）🆕v4.60.0

**问题**：多写路径状态冲突 + UI 偏好未持久化 + storage 错误未处理，三类问题本质相同：状态管理缺乏系统性设计。

**核心规则**：
1. 状态管理设计必须同时考虑：写入路径唯一性 + 持久化策略 + 错误容错
2. 新增状态时必须填写"状态管理三要素检查清单"（写入路径/持久化方式/错误处理）
3. 代码审查时按三要素逐项检查

**配置参数**：`state_management_triple` 节点（enabled / checkListItems / reviewEnforcement）

**适用**：所有新增 React 状态、Zustand store 状态
**不适用**：纯计算派生状态（无副作用）

**历史教训**：#97（UI偏好持久化）+ #98（storage错误处理）+ #99（Cookie状态异常）三问题根因相同：状态管理缺乏系统性。

## 103. UI 视觉变更预确认门控（UI-PREVIEW-GATE）🆕v4.62.0

**问题**：视觉风格全量替换（如图标、主题色、布局）后，用户审查认为不美观与整体不协调，需要回滚。

**核心规则**：
1. 视觉风格变更影响 ≥10 个组件时，必须先预览再全量替换（渐进式替换策略）
2. 替换前必须记录回滚清单（被替换的组件 + 原始实现）
3. 风格一致性评估：新视觉元素与整体主题（颜色/圆角/间距/粗细）是否协调
4. 用户确认后才执行全量替换

**判断信号**：`git diff` 涉及 ≥10 个图标的替换 / 主题色变更 / 布局结构重构 → 必须执行预确认门控

**配置参数**：`ui_preview_gate` 节点（enabled / changeLineThreshold / previewStrategy / triggerPatterns / exemptPatterns）

**适用**：视觉风格替换、图标变更、主题色调整、布局重构
**不适用**：Bug 修复的微小 UI 调整、文案修正、样式微调

**历史教训**：Geometric Essence 图标全量替换 21 个 Ant Design 图标后，用户认为不美观与整体主题不协调，要求完整回滚。根因：未先预览就全量替换，替换后与 Ant Design 设计语言不协调。

**对应 step**：step 259（frontend-ui.md）。

## 106. 回调注入默认值模式（CALLBACK-INJECTION-DEFAULT）🆕v4.62.0

**问题**：异步回调（如 `on_success`/`on_complete`）注入外部依赖时，调用方未传回调导致 `None` 调用报错，或回调内部依赖外部状态（如 `request_id`）但回调签名不包含该参数。

**核心规则**：
1. 可选回调参数必须提供默认空实现（`lambda *a, **kw: None`），禁止调用方手动 `if callback: callback()`
2. 回调内部依赖的外部状态必须通过闭包或参数注入，禁止回调内部直接读取全局变量
3. 回调注入的默认值必须与正常回调返回类型一致（如回调返回 dict，默认值返回空 dict）

**判断信号**：
- `if on_success: on_success(result)` → 违反规则1（应 `on_success = on_success or noop`）
- 回调内部引用 `request_id` / `task_id` 等外部变量但签名不包含 → 违反规则2
- 默认回调返回 `None` 但正常回调返回 dict → 违反规则3

**配置参数**：`callback_injection` 节点（enabled / defaultBehaviorStrategy / allowOverride / validateReturnType）

**适用**：所有异步回调（API 调用后回调、任务完成回调、事件处理器注册）
**不适用**：同步直接调用（无回调模式）、必须执行的回调（不应有默认空实现）

**历史教训**：`refresh_item` 的 `on_complete` 回调未传时为 `None`，调用 `on_complete(result)` 触发 `TypeError`。修复后 `on_complete = on_complete or (lambda r: None)`。

**对应 step**：step 249（general-engineering.md）。

## 107. React 状态选型判断矩阵（STATE-SELECTION-MATRIX）🆕v4.62.0

**问题**：React 状态管理选型不当导致：跨刷新持久化偏好用 `useState`（刷新丢失）、简单 UI 状态用全局 store（过度设计）、临时交互状态用 localStorage（性能浪费）。

**核心规则**：
1. **判断矩阵**（按优先级从高到低）：
   - 跨刷新需保留的偏好 → `usePersistentState`（key, defaultValue）
   - 跨组件共享的业务状态 → Zustand store
   - 仅组件内使用的 UI 状态 → `useState`
   - 表单临时输入 → `useState`（提交后清空）
2. **禁止**：`useState` 存储持久化偏好（key 含 `mode`/`theme`/`layout`/`view`/`collapsed`/`enabled`）
3. **禁止**：自行实现 `localStorage.getItem/setItem` 读写（必须复用 `usePersistentState`）

**判断信号**：
- `useState` 变量名含偏好关键词 → 检查是否应使用 `usePersistentState`
- `localStorage.getItem` 直接调用 → 违反规则3
- 组件内 `useState` 用于跨组件共享数据 → 应改用 Zustand

**配置参数**：`state_selection` 节点（enabled / preferenceKeywords / persistenceHookName / keyNamingPattern）

**适用**：React 组件状态管理选型、新增 useState/usePersistentState 前的判断
**不适用**：非 React 环境、服务端渲染（SSR 状态管理不同）

**历史教训**：AntiCrawl/index.tsx 的 CDP 模式开关用 `useState(false)`，刷新后状态重置。修复后改用 `usePersistentState('anticrawl-cdp-mode', false)`。

**对应 step**：step 260（frontend-ui.md）+ #97（UI偏好持久化检查）。
