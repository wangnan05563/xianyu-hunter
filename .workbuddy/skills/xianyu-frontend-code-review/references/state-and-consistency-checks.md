# 前端状态管理与一致性审查（State & Consistency Checks）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)
> **重点**：前端状态判断 / API 契约对齐 / 错误反馈 / 交互体验 / 问题排查方法论
> **复盘来源**：基于实际解决的问题提炼（硬编码阈值、状态字段不一致、API 字段映射错误、credentials 缺失、错误无反馈、事件冒泡、自动聚焦、过滤可见性、修复后未验证）
> **配置节点**：所有参数在 `config.yaml` 的 `state_and_consistency_checks` 节点管理

---

## 维度 5: 状态管理与后端一致性

### F-REVIEW-NO-HARDCODED-THRESHOLD

- **检查点名称**：前端禁止硬编码业务阈值
- **所属维度**：维度 5 状态管理与后端一致性
- **问题描述**：前端用 `collectStats.failed >= 3` 硬编码阈值判断"已暂停"状态，且 `failed` 是累计数而非连续数，导致状态判断与后端实际状态不符
- **检查方法**：grep `>= \d+` / `<= \d+` / `> \d+` / `< \d+` 在 `.tsx/.ts` 文件中，确认非 UI 相关的数字阈值从后端获取
- **正面示例**：
  ```tsx
  // 从后端获取 is_paused 布尔值 + threshold 显示
  {collectStats.is_paused && (
    <Tag color="red">
      已暂停（连续失败达阈值 {collectStats.fail_pause_threshold} 次）
    </Tag>
  )}
  ```
- **反面示例**：
  ```tsx
  // 硬编码阈值 3，且用累计数 failed 而非连续数
  {collectStats.failed >= 3 && <Tag color="red">已暂停</Tag>}
  ```
- **适用场景**：任何前端判断业务状态（暂停 / 限制 / 阈值）的场景
- **不适用场景**：纯 UI 状态（如 pageSize=20、debounce=300ms）

---

### F-REVIEW-STATE-FROM-BACKEND

- **检查点名称**：前端状态判断必须使用后端返回的状态字段
- **所属维度**：维度 5 状态管理与后端一致性
- **问题描述**：前端自行计算"已暂停"状态（`failed >= 3`），而非使用后端返回的 `is_paused` 字段，导致前端判断与后端实际状态不一致
- **检查方法**：检查前端状态判断逻辑，确认使用后端返回的布尔状态字段而非前端计算
- **正面示例**：使用 `collectStats.is_paused`（后端返回）
  ```tsx
  {collectStats.is_paused && <Tag color="red">已暂停</Tag>}
  ```
- **反面示例**：前端计算 `collectStats.failed >= threshold`
  ```tsx
  {collectStats.failed >= 3 && <Tag color="red">已暂停</Tag>}
  ```
- **适用场景**：任何有后端对应状态的前端判断
- **不适用场景**：纯前端 UI 状态（如 modal visible）

---

### F-REVIEW-TYPE-ALIGNMENT

- **检查点名称**：前端类型定义与后端响应字段对齐
- **所属维度**：维度 5 状态管理与后端一致性
- **问题描述**：后端新增 `is_paused` / `fail_pause_threshold` 字段，前端类型定义未同步，导致 TypeScript 无法识别新字段或被 `as` 强制转换绕过检查
- **检查方法**：对比后端 API 响应字段与前端 TypeScript 类型定义
- **正面示例**：
  ```typescript
  interface CollectStats {
    is_paused: boolean            // 后端新增
    fail_pause_threshold: number  // 后端新增
    // ...其他字段
  }
  ```
- **反面示例**：前端类型缺少 `is_paused` / `fail_pause_threshold` 字段
  ```typescript
  interface CollectStats {
    failed: number
    success: number
    // 缺少 is_paused / fail_pause_threshold
  }
  ```
- **适用场景**：任何后端新增字段的前端同步
- **不适用场景**：前端独立的状态字段

---

## 维度 3: API 契约

### F-REVIEW-API-FIELD-MAPPING

- **检查点名称**：前端 API 字段映射正确性
- **所属维度**：维度 3 API 契约
- **问题描述**：后端返回 `{items, total}` 对象，前端期望数组，导致 `map` / `length` 等数组操作失败或类型错误
- **检查方法**：对比前端 API 调用代码与后端端点响应结构
- **正面示例**：
  ```typescript
  // 前端使用 r.data.items（后端返回 {items, total}）
  const versions = r.data.items
  ```
- **反面示例**：
  ```typescript
  // 前端直接用 r.data（期望数组，但后端返回对象）
  const versions = r.data  // 类型错误
  ```
- **适用场景**：任何前端 API 调用
- **不适用场景**：无后端对应的纯前端数据

---

### F-REVIEW-CREDENTIALS-INCLUDE

- **检查点名称**：fetch 请求必须包含 credentials
- **所属维度**：维度 3 API 契约
- **问题描述**：前端 fetch 请求未包含 `credentials: 'include'`，导致认证 Cookie 不传递，请求被后端 401 拒绝
- **检查方法**：grep `fetch(` 确认所有请求包含 `credentials: 'include'`
- **正面示例**：
  ```typescript
  fetch(url, { credentials: 'include' })
  ```
- **反面示例**：
  ```typescript
  fetch(url)  // 不传递 Cookie
  ```
- **适用场景**：所有需要认证的 API 请求
- **不适用场景**：公开 API（无需认证）

---

## 维度 2: 错误处理

### F-REVIEW-ERROR-FEEDBACK

- **检查点名称**：错误状态必须有用户可见的反馈
- **所属维度**：维度 2 错误处理
- **问题描述**：消息发送失败后无重试机制，用户不知道发送失败，导致用户重复发送或误以为已发送
- **检查方法**：检查异步操作的错误处理，确认有 UI 反馈（Toast / 状态标记）
- **正面示例**：
  ```tsx
  // 消息状态指示器
  {message.status === 'failed' && (
    <RetryButton onClick={() => retrySend(message.id)} />
  )}
  ```
- **反面示例**：异步操作失败后静默处理，用户无感知
  ```typescript
  sendMessage(msg).catch(() => {})  // 静默吞错误
  ```
- **适用场景**：任何用户触发的异步操作
- **不适用场景**：后台自动重试的操作

---

### F-REVIEW-ASYNC-RETRY

- **检查点名称**：失败操作提供重试入口
- **所属维度**：维度 2 错误处理
- **问题描述**：消息发送失败后无法重试，用户必须重新输入完整内容，体验差
- **检查方法**：检查失败状态是否有重试按钮 / 方法
- **正面示例**：
  ```tsx
  {message.status === 'failed' && (
    <Button onClick={() => retrySend(message)}>重试</Button>
  )}
  ```
- **反面示例**：失败状态无任何重试入口，用户必须重新操作
- **适用场景**：任何可能失败的异步操作
- **不适用场景**：不可重试的操作（如已完成的订单）

---

## 维度 4: 交互体验

### F-REVIEW-EVENT-BUBBLING

- **检查点名称**：事件冒泡控制
- **所属维度**：维度 4 交互体验
- **问题描述**：Ant Design v5 Dropdown menu 的 onClick 在嵌套点击场景不触发，需用 Popconfirm 替代并 `stopPropagation`
- **检查方法**：检查 Dropdown / Popover 组件的嵌套点击事件，确认有 `stopPropagation`
- **正面示例**：
  ```tsx
  <Popconfirm onConfirm={(e) => { e?.stopPropagation(); handleDelete(); }}>
  ```
- **反面示例**：Dropdown onClick 在嵌套场景不触发
  ```tsx
  <Dropdown menu={{ items, onClick: handleDelete }}>  // 嵌套场景不触发
  ```
- **适用场景**：嵌套点击事件场景
- **不适用场景**：独立的点击事件

---

### F-REVIEW-AUTO-FOCUS

- **检查点名称**：切换会话时自动聚焦输入框
- **所属维度**：维度 4 交互体验
- **问题描述**：切换聊天会话后输入框未自动聚焦，用户需手动点击输入框才能开始输入
- **检查方法**：检查会话切换后的 useEffect，确认有 input.focus()
- **正面示例**：
  ```tsx
  const inputRef = useRef<InputRef>(null)
  useEffect(() => {
    inputRef.current?.focus()
  }, [sessionId])
  ```
- **反面示例**：会话切换后无 focus 调用
- **适用场景**：聊天 / 搜索等需要频繁输入的场景
- **不适用场景**：只读页面

---

## 维度 6: 问题排查方法论

### F-REVIEW-FILTER-VISIBILITY-FRONTEND

- **检查点名称**：前端展示过滤结果可见性
- **所属维度**：维度 6 问题排查方法论
- **问题描述**：实时搜索结果被后端过滤后，前端未显示过滤原因，用户以为搜索无结果反复调整搜索词
- **检查方法**：检查搜索结果展示，确认有过滤原因说明
- **正面示例**：
  ```tsx
  {filterSummary.raw > 0 && filterSummary.final_total === 0 && (
    <Alert type="warning" message={`搜索到 ${filterSummary.raw} 条，全部被过滤条件筛掉`} />
  )}
  ```
- **反面示例**：搜索结果为空时只显示"无结果"，不显示过滤原因
- **适用场景**：任何有后端过滤的搜索结果展示
- **不适用场景**：无过滤的简单列表

---

### F-REVIEW-VERIFY-AFTER-FIX

- **检查点名称**：修复后必须验证前端效果
- **所属维度**：维度 6 问题排查方法论
- **问题描述**：修复后未强制刷新浏览器（Ctrl+Shift+R）导致旧缓存生效，误以为修复无效反复修改代码
- **检查方法**：确认前端修复后有验证步骤（强制刷新 / Playwright 截图）
- **正面示例**：
  ```bash
  # 修复后强制刷新浏览器
  # Ctrl+Shift+R (Windows/Linux) / Cmd+Shift+R (macOS)
  # 或用 Playwright 截图验证
  ```
- **反面示例**：修改代码后直接刷新（普通 F5 可能命中缓存）
- **适用场景**：任何前端代码修复
- **不适用场景**：纯类型定义修复

---

## 维度 7: UI 状态与操作按钮分离

### F-REVIEW-UI-STATE-ACTION-SEPARATION

- **检查点名称**：状态卡片操作按钮文案与状态文案分离
- **所属维度**：维度 7 UI 状态与操作按钮分离
- **问题描述**：Cookie 分层管理卡片在 `state.valid=true` 时显示红色"失效"操作按钮，用户误认为状态显示（报告"identity/session/tracking 一直显示失效"，实际三层 `valid=true`）。操作按钮文案与状态文案共用"失效"二字导致语义混淆。
- **检查方法**：grep 状态卡片组件（`Badge` / `Tag` / `Card`），检查同时含状态文本 + 操作按钮的场景，操作按钮文案是否加动词前缀（如"主动失效" / "手动标记失效"）+ 图标（如 `StopOutlined`）。
- **正面示例**：
```tsx
import { StopOutlined } from '@ant-design/icons'

// ✅ 状态文案与操作按钮文案分离
<Badge status={state.valid ? 'success' : 'default'} text={<Text strong>{layer}</Text>} />
<div>
  <Text type="secondary">
    {!state.valid ? '未初始化' : state.cookie_count > 0 ? `${state.cookie_count} 个 Cookie` : '已恢复（无 Cookie）'}
  </Text>
</div>
{state.valid && (
  <Button
    size="small"
    danger
    type="link"
    icon={<StopOutlined />}  // ✅ 图标强化操作语义
    onClick={() => handleInvalidateLayer(layer)}
  >
    主动失效  {/* ✅ 加"主动"前缀，与状态"失效"区分 */}
  </Button>
)}
```
- **反面示例**：
```tsx
// ❌ 操作按钮文案与状态文案共用"失效"
<Badge status={state.valid ? 'success' : 'default'} text={<Text>{layer}</Text>} />
{state.valid && (
  <Button danger type="link" onClick={() => handleInvalidateLayer(layer)}>
    失效  {/* ❌ 用户误认为这是状态显示 */}
  </Button>
)}
```
- **适用场景**：状态卡片同时显示状态 + 操作按钮的场景（Cookie 分层管理 / 任务状态卡片 / 连接状态卡片 / 服务健康卡片）
- **不适用场景**：纯展示卡片（无操作按钮）、纯操作卡片（无状态显示）、列表行内操作（操作列与状态列分离）

---

### F-REVIEW-SPECIAL-STATE-LABEL

- **检查点名称**：特殊状态显式标注
- **所属维度**：维度 7 UI 状态与操作按钮分离
- **问题描述**：后端 `force_restore_layers` 强制恢复层状态时，`cookie_count=0` 但 `valid=true`，前端显示"0 个 Cookie"误导用户以为有有效 cookie，实际是功能可用性信号强制恢复的。
- **检查方法**：检查状态文案三元嵌套，确认 `valid=true && count=0` 等特殊状态有显式文案标注（如"已恢复（无 Cookie）"），禁止显示"0 个 Cookie"。
- **正面示例**：
```tsx
// ✅ 特殊状态显式标注
<Text type="secondary">
  {!state.valid
    ? '未初始化'
    : state.cookie_count > 0
    ? `${state.cookie_count} 个 Cookie`
    : '已恢复（无 Cookie）'}  {/* ✅ force_restore 强制恢复的特殊语义 */}
</Text>
```
- **反面示例**：
```tsx
// ❌ 特殊状态显示"0 个 Cookie"误导用户
<Text type="secondary">
  {state.valid ? `${state.cookie_count} 个 Cookie` : '未初始化'}
  {/* count=0 时显示"0 个 Cookie"，用户以为有 0 个有效 cookie */}
</Text>
```
- **适用场景**：任何有 `valid=true && count=0` 等特殊状态组合的场景（force_restore / fallback / default 值）
- **不适用场景**：状态字段语义单一（如只有 valid/invalid 两态）

---

### F-REVIEW-STATUS-INDICATOR-SOURCE

- **检查点名称**：状态指示器同源于后端字段
- **所属维度**：维度 7 UI 状态与操作按钮分离
- **问题描述**：前端用 `count > 0 ? success : default` 自行计算 Badge status，覆盖后端 `valid` 字段判定，导致后端 `force_restore` 恢复 valid=true 后前端仍显示 default（失效）。
- **检查方法**：检查 `Badge status` / `Tag color` 是否直接来源于后端 `valid` 字段，禁止前端自行计算覆盖后端判定。
- **正面示例**：
```tsx
// ✅ Badge status 直接来源于后端 valid 字段
<Badge status={state.valid ? 'success' : 'default'} text={<Text>{layer}</Text>} />
```
- **反面示例**：
```tsx
// ❌ 前端自行计算 Badge status，覆盖后端 valid 判定
<Badge
  status={state.cookie_count > 0 ? 'success' : 'default'}  {/* ❌ count=0 时显示 default，覆盖 valid=true */}
  text={<Text>{layer}</Text>}
/>
```
- **适用场景**：任何状态指示器（Badge / Tag / Progress）来源于后端字段的场景
- **不适用场景**：前端独立计算的 UI 状态（如 loading / disabled）

---

### F-REVIEW-COOKIE-HEALTH-DISPLAY

- **检查点名称**：Cookie 健康状态显示一致性
- **所属维度**：维度 7 UI 状态与操作按钮分离
- **严重级别**：Warning
- **问题描述**：后端实现多级自愈（token 刷新 → cookie 强制注入 → 放弃）后，自愈成功时 Cookie 层状态应恢复为有效。前端若不轮询 `/cookies/layers` 获取最新状态，或轮询间隔过长，会导致后端自愈成功后前端仍显示"失效"（状态不一致）。此外，后端 `_post_login_cookie_health_check` 登录后健康探测结果若不在前端反馈，用户无法感知登录是否真正成功

- **检查方法**：
  1. 检查 Cookie 健康状态显示组件是否轮询 `/cookies/layers` 端点获取最新状态
  2. 确认轮询间隔来自配置（`config.yaml` 的 `freq_stats_polling.slow_interval_ms`），而非硬编码
  3. grep `valid` / `cookie_count` 确认前端显示的状态来源于后端返回的 `valid` 字段，而非前端缓存
  4. 确认后端自愈成功（`valid=true`）后前端在下一轮轮询周期内更新显示为"有效"
  5. 检查登录后是否有健康探测反馈（如 toast 提示"登录成功，Cookie 已验证"或"登录成功但部分 Cookie 缺失"）
  6. 确认前端不会在轮询请求失败时将状态强制设为"失效"（应保持上一次成功状态，仅标注 stale）

- **正面示例**：
  ```tsx
  // ✅ 轮询 /cookies/layers 获取最新状态，间隔来自配置
  useEffect(() => {
    const loadCookieLayers = () => {
      cookieApi.getLayers().then(data => {
        setCookieLayers(data)
      }).catch(() => {
        // 轮询失败仅 console.error，不弹 message.error（与 freq_stats_polling.fail_silent 一致）
        console.error('Cookie layers poll failed')
      })
    }
    loadCookieLayers()
    const timer = setInterval(loadCookieLayers, POLL_INTERVALS.cookieLayers)
    return () => clearInterval(timer)
  }, [])

  // ✅ 登录后健康探测反馈
  const handleLogin = async () => {
    try {
      const result = await authApi.login(credentials)
      if (result.health_check?.passed) {
        message.success('登录成功，Cookie 已验证', 3)
      } else {
        message.warning(`登录成功但${result.health_check?.reason || '部分 Cookie 缺失'}`, 5)
      }
      // 登录后立即刷新 Cookie 层状态（不等下一轮轮询）
      refetchCookieLayers()
    } catch (e) {
      message.error(extractApiError(e), 5)
    }
  }
  ```

- **反面示例**：
  ```tsx
  // ❌ 反例 1：不轮询，后端自愈成功后前端仍显示"失效"
  const cookieLayers = await cookieApi.getLayers()  // 仅页面加载时拉一次
  // 后端自愈成功后，前端不会更新显示

  // ❌ 反例 2：轮询间隔硬编码在组件内
  setInterval(loadCookieLayers, 60000)  // 硬编码 60 秒，应来自配置

  // ❌ 反例 3：轮询失败时强制设为"失效"
  catch (e) {
    setCookieLayers(prev => prev.map(l => ({ ...l, valid: false })))
    // 轮询失败不应强制设为失效，应保持上一次状态
  }

  // ❌ 反例 4：登录后无健康探测反馈
  const handleLogin = async () => {
    await authApi.login(credentials)
    message.success('登录成功')  // 未展示健康探测结果，用户不知道 Cookie 是否完整
  }
  ```

- **适用场景**：显示 Cookie 健康状态的前端组件（Cookie 分层管理卡片、登录页面、反爬登录管理、关于页面的 Cookie 状态展示）
- **不适用场景**：不显示 Cookie 状态的页面（如纯展示页面、无认证需求的公开页面）、纯后端内部逻辑（前端不感知）

---

## 配置参数

所有检查点的配置参数集中在 `config.yaml` 的 `state_and_consistency_checks` 节点管理：

```yaml
state_and_consistency_checks:
  enabled: true
  # 维度 5: 状态管理与后端一致性
  no_hardcoded_threshold:
    enabled: true
    forbidden_patterns:
      - ">= \\d+"
      - "<= \\d+"
      - "> \\d+"
      - "< \\d+"
    whitelist_ui_fields:
      - pageSize
      - debounce
      - maxRetries
  state_from_backend:
    enabled: true
    require_backend_status_field: true
  type_alignment:
    enabled: true
    require_sync_check: true
  # 维度 3: API 契约
  api_field_mapping:
    enabled: true
    require_response_type_check: true
  credentials_include:
    enabled: true
    require_credentials_include: true
    require_with_credentials: true
  # 维度 2: 错误处理
  error_feedback:
    enabled: true
    require_ui_feedback: true
    forbidden_silent_catch: true
  async_retry:
    enabled: true
    require_retry_entry: true
  # 维度 4: 交互体验
  event_bubbling:
    enabled: true
    require_stop_propagation: true
  auto_focus:
    enabled: true
    applicable_pages:
      - Chatbot
      - Search
  # 维度 6: 问题排查方法论
  filter_visibility_frontend:
    enabled: true
    require_filter_reason_display: true
  verify_after_fix:
    enabled: true
    require_hard_refresh: true
    require_screenshot_verify: false
  # 维度 7: UI 状态与操作按钮分离
  ui_state_action_separation:
    enabled: true
    require_action_verb_prefix: true  # 操作按钮文案加动词前缀
    require_action_icon: true  # 操作按钮用图标强化语义
    forbidden_shared_words: ["失效", "删除", "重置"]  # 状态与操作共用易混淆动词
  special_state_label:
    enabled: true
    require_explicit_label: true  # valid=true && count=0 等特殊状态显式标注
    forbidden_misleading_text: ["0 个 Cookie", "0 条记录"]
  status_indicator_source:
    enabled: true
    require_backend_field_source: true  # Badge status 同源于后端 valid 字段
    forbid_frontend_calculation: true  # 禁止前端自行计算覆盖后端判定
  # 维度 7: Cookie 健康状态显示一致性（v4.50.0 新增）
  cookie_health_display:
    enabled: true
    require_polling: true  # 必须轮询 /cookies/layers 获取最新状态
    polling_interval_source: "config"  # 轮询间隔必须来自配置，禁止硬编码
    require_health_check_feedback: true  # 登录后健康探测结果必须有 UI 反馈
    forbid_force_invalid_on_poll_failure: true  # 轮询失败时禁止强制设为"失效"
    backend_healing_endpoints: ["/api/cookies/layers"]  # 后端自愈状态查询端点
```

---

## 参考

- 完整审查规则：[SKILL.md](../SKILL.md)
- 配套参考：[encoding-and-io.md](./encoding-and-io.md)

---

## F-REVIEW-245 健康状态展示与后端实际状态一致性（v4.68.0 新增）

**规范源**：[dual-data-source-consistency.md](../../../xianyu-hunter-dev/references/dual-data-source-consistency.md) 流程 14
**配置节点**：`config.yaml: health_display_consistency`

### 审查要点

前端展示的健康状态（cookie_valid / score / action）**必须**与用户实际体验一致。当后端健康检查因双数据源不一致导致判定无效，但实际功能（实时搜索/采集/抢单）仍可用时，前端应：
1. 不应只展示"cookie 无效"导致用户误以为功能不可用
2. 应展示"健康检查异常但功能可用"的中间态，或提示用户"功能实际可用，建议刷新 cookie"
3. 健康状态展示应与功能入口的实际可用性联动验证

### 判定规则

- **严重**：前端展示"cookie 无效"且禁用功能入口，但功能实际可用（误导用户）
- **警告**：前端展示"cookie 无效"但未禁用功能入口，用户困惑但功能可用
- **警告**：健康状态未与功能实际可用性联动验证（无法发现双数据源不一致）

### 审查维度

1. **状态展示准确性**：cookie_valid=false 时是否真的意味着功能不可用？
2. **功能入口禁用策略**：cookie_valid=false 时是否禁用了实际可用的功能入口？
3. **用户提示文案**：是否区分"cookie 真失效"与"健康检查异常但功能可用"？
4. **状态刷新机制**：用户重新登录后，健康状态是否能立即反映（而非等下次定时检查）？

### 典型案例

反爬登录管理页面展示"cookie 无效"（cookie_valid: false），但用户切换到任务详情做实时搜索仍能正常查询 → 前端应展示"健康检查异常，但实时搜索仍可用，建议刷新 cookie"而非简单的"cookie 无效"。

### 实现建议

```typescript
// 健康状态展示组件应根据 action 字段细化提示
const healthMessage = useMemo(() => {
  if (!healthReport) return null;
  if (healthReport.cookie_valid) return 'Cookie 状态正常';
  // cookie_valid=false 时，区分"真失效"与"检查异常"
  if (healthReport.action === 'relogin') return 'Cookie 已失效，请重新登录';
  if (healthReport.action === 'renew_token') return 'Token 过期，正在续期...';
  return '健康检查异常，但功能可能仍可用，建议刷新 Cookie';
}, [healthReport]);
```

### 关联

- **后端对应检查点**：B-REVIEW-332 双数据源兜底复核
- **测试场景**：T005 健康检查端到端测试
- **规范源**：[dual-data-source-consistency.md](../../../xianyu-hunter-dev/references/dual-data-source-consistency.md)
