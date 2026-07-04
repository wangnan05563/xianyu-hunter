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
```

---

## 参考

- 完整审查规则：[SKILL.md](../SKILL.md)
- 配套参考：[encoding-and-io.md](./encoding-and-io.md)
