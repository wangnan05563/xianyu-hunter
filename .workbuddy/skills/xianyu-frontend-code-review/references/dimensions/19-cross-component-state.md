# 19. 跨组件状态同步与死代码检查 🆕v4.3

- 【强制】**F-REVIEW-DEAD-CODE：长期存活对象禁止赋值给局部变量**：`new Proxy()` / `new MutationObserver()` / `new IntersectionObserver()` 等需要长期存活的监听器/观察者，必须赋值给实例属性（`this._observer`）或模块级变量，禁止赋值给局部变量后丢弃
  - **判断信号**：`var xxx = new Proxy(...)` / `const xxx = new MutationObserver(...)` 且 xxx 是局部变量且未被返回/导出
  - **修复模式**：赋值给实例属性或模块级变量，确保引用保留
  - **历史教训**：`awsc_spoof.py` 的 `var baxiaProxy = new Proxy(window.__baxia__, {...})` 赋值给局部变量后从未使用，验证码触发事件永远不会被派发

- 【强制】**F-REVIEW-TRY-FINALLY-INIT：try/finally 变量初始化**：`try/finally` 块中 `finally` 引用的变量必须在 `try` 之前初始化为 `null`/`undefined`，确保 `try` 内赋值前抛异常时 `finally` 不会抛 `ReferenceError`
  - **判断信号**：`try { const page = await create() } finally { page.close() }` 且 page 在 try 内声明
  - **修复模式**：`let page = null; try { page = await create() } finally { if (page) await page.close() }`

- 【强制】**F-REVIEW-CROSS-COMPONENT-STATE：跨组件状态同步**：多个组件/模块对同一概念（如"会话有效性"/"登录状态"）做判断时，状态变更必须双向同步——状态变更方通知其他组件、查询方额外检查其他组件的最新状态
  - **判断信号**：两个以上组件各自独立判断"会话有效性"/"登录状态"等同一概念（如健康检查器检查 Cookie 存在性 + worker 检查 API 响应 RGV587_ERROR）
  - **修复模式**：前端 store 状态变更时通过事件/回调通知其他组件；查询方在判断时额外检查其他来源的状态标记
  - **不适用**：单组件内部状态、无跨组件依赖的独立判断

- 【强制】**F-REVIEW-ERROR-HINT-ROUTABLE：错误提示路由可操作性**：面向用户的错误提示中引用的路由路径必须在前端路由表中已注册，引用的 API 端点必须在后端已实现
  - **判断信号**：错误信息中包含 `/api/xxx` 或 `/page-path` 引用
  - **修复模式**：提示中只引用已注册的路由和已实现的端点；提供具体的可操作修复指引（如"请点击「反爬登录管理」重新初始化"而非"请调用 /api/xxx/configure"）
