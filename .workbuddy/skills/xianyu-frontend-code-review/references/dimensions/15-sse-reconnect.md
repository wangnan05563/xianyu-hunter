# 15. SSE 重连 🆕v2.0

- 【强制】SSE lastEventId 持久化重连（`frontend/src/pages/Dashboard/index.tsx`）
- 【强制】`SSE_LAST_EVENT_ID_KEY = 'xh_sse_last_event_id'` 模块级常量
- 【强制】断线重连从 localStorage 读取 lastEventId 作为 `?last_event_id=` 参数
- 【强制】`handleSseAppEvent` 模块级函数（SonarQube S2004）
- 【强制】**SSE 断线重连三要素**（缺一不可）：
  1. **lastEventId 记录**：`app_event` 回调中 `e.lastEventId`（MessageEvent 属性，非 EventSource）保存到变量
  2. **重连传递 last_event_id**：URL 拼接 `?last_event_id=${lastEventId}`，启用后端回放断线期间事件
  3. **visibilitychange 监听**：页面恢复可见且 SSE 已断开时自动重建连接（解决页面不可见时 selectedTask 变化导致 SSE 永久断开的问题）
- 【强制】SSE error 重连必须有次数上限（`MAX_RECONNECT`，通过配置管理，默认 10），超限后放弃 SSE 退化为轮询
- 【强制】页面恢复可见时重置重连计数（`reconnectAttempts = 0`），给新一轮重连机会
- 【强制】`visibilitychange` 事件监听必须在 useEffect cleanup 中移除（`document.removeEventListener`），避免内存泄漏
- 【常见陷阱】`lastEventId` 是 `MessageEvent` 的属性（`e.lastEventId`），不是 `EventSource` 的属性（`es.lastEventId` 不存在）

- 🆕v4.1【强制】**F-REVIEW-SSE-ERROR-HANDLING：SSE 错误事件状态码分类处理**
  - SSE 流中收到 `stage='error'` 事件时，必须按 `status` 字段分类处理（状态码与文案映射在 `config.yaml` 的 `sse_error_status_mapping` 节点管理）：
    - `503/504`：稍后重试提示（如"网络繁忙，请稍后重试"），不阻塞 UI
    - `401/403`：需用户介入（如"登录已过期，请前往「反爬登录管理」重新登录"）+ 显式"前往登录"跳转按钮（用 `useNavigate` 跳转到 `/login` 或反爬登录页面）
    - `502`：需重启服务提示（如"浏览器连接断开，请重启服务"）
  - **禁止**：将 `stage='done'` + 0 条结果与 `stage='error'` 混为一谈（前者是"真的没货"，后者是"业务异常"）
  - **禁止**：吞掉 `stage='error'` 事件只展示通用错误（如只显示"预览失败"而无具体指引）
  - **判断信号**：组件消费 SSE 流（如 `useAutoLiveSearch.ts` 的 `live` 方法回调）→ 必须显式处理 `stage='error'` 分支
  - **通过示例**：
    ```typescript
    if (data.stage === 'error') {
      const status = data.status ?? 500
      if (status === 401 || status === 403) {
        setErrorMsg(data.detail ?? '登录已过期')
        setShowReLoginBtn(true)  // 显示"前往登录"按钮
      } else if (status === 502) {
        setErrorMsg(data.detail ?? '服务异常，请重启')
      } else {
        setErrorMsg(data.detail ?? '网络繁忙，请稍后重试')
      }
      return
    }
    ```
  - **不通过示例**：
    ```typescript
    if (data.stage === 'done') { /* 渲染结果 */ }
    // 未处理 stage='error'，导致 SSE 错误事件被忽略或走默认分支
    ```
