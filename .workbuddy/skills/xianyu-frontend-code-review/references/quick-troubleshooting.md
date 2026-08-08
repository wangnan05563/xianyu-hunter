# 快速问题定位（Quick Troubleshooting）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)
> **用途**：现象导向的问题定位对照表（现象 → 原因 → 方案），与 SKILL.md 中规则导向的 25 维度章节互补。当用户报告具体现象时，先查本表快速定位原因，再回到 SKILL.md 对应维度查阅详细规则。
> **维护原则**：新增问题复盘时追加到本表末尾，SKILL.md 中仅保留简短引用说明。

---

| 现象 | 原因 | 方案 |
|------|------|------|
| 401 跳转登录死循环 | axios 未设 `withCredentials: true` | `client.defaults.withCredentials = true` |
| 路由切换后白屏 | `lazyRetry` 未包装 chunk 失败重试 | 用 `lazy(() => lazyRetry(() => import(...)))` |
| 独立路由（如 `/login`）主题不切换 | `ConfigProvider` 在 `BrowserRouter` 内层 | 移到外层 |
| 页签切换状态丢失 | `partialize` 未过滤 ReactNode | 在 persist 中只存必要字段 |
| SSE 断线重连丢事件 | lastEventId 未持久化 | 用 `SSE_LAST_EVENT_ID_KEY` 存入 localStorage |
| 移动端页签无法替换 | `replaceMobileActiveSheet` 分支缺失 | 检查 `openSheet` 四分支决策 |
| 内存泄漏（卸载后 setState） | `mountedRef` 缺失 | 在 useEffect 中用 `mountedRef` 保护 setState |
| 竞态条件（旧响应覆盖新响应） | `requestId` 保护缺失 | 每次请求生成 requestId，丢弃过期响应 |
| 页面不可见时频繁请求 | 降频缺失 | 用 `BACKGROUND_SLOWDOWN = 3` 降频 |
| SonarQube S2004 报错 | 嵌套层级 > 4 | 提取模块级函数 |
| SonarQube S3776 报错 | 认知复杂度 > 15 | 拆 case 为模块级 handler |
| SonarQube S7784 报错 | 用 `JSON.parse(JSON.stringify())` | 改用 `structuredClone` |
| 类型断言警告（S4325） | 不必要的 `as` | 用类型守卫收窄类型 |
| store 持久化字段失效 | `partialize` 配置错误 | 检查 `partialize` 只存必要字段 |
| 路由懒加载失败 | `lazyRetry` 配置错误 | 检查 `MAX_RETRIES=3`、1s/2s/4s 指数退避 |
| 最小化 tab 点击无反应 | `activateSheet` 未恢复 `minimized` | 在 `activateSheet` 中同步设 `minimized: false` |
| 恢复按钮文字看不清 | 用 `colorBorder`（对比度低） | 改用 `colorPrimary`（`activeColor`） |
| 页面全屏溢出容器 | 用 `minHeight: 100vh` | 改用 `height: 100%` + flex 布局 |
| vitest 卡在 RUN 阶段 | Node v24 + vitest worker 兼容性 | 加 `--no-isolate` 参数 |
| antd Drawer 测试报错 | `window.matchMedia` 未 mock | beforeAll 中 mock `matchMedia` |
| 🆕 SonarQube S6819/S6844 报错 | `<div onClick>` / `<a onClick>` 无 href | 改用 `<button type="button">` + 键盘事件 |
| 🆕 SonarQube S7503 报错 | `async` 函数无 `await` | 改同步函数，或确认需要异步上下文 |
| 🆕 SonarQube S6767 报错 | 未使用的 Props/State/参数 | 删除未使用项，避免接口膨胀 |
| 🆕 SonarQube S7744 报错 | `as unknown as T` 多重断言 | 用类型守卫（`type guard`）收窄类型 |
| 🆕 SonarQube S6582 报错 | 冗余可选链 `a?.b` 中 a 已非空 | 移除冗余 `?.` |
| 🆕 SonarQube S7735 报错 | useEffect 依赖缺失 | 补全依赖数组（用 `ref` 持有最新闭包避免循环） |
| 🆕 SonarQube S6551 报错 | `for...in` 遍历对象 | 改用 `Object.keys/values/entries` |
| SSE 断线后页面恢复可见不重连 | 缺少 visibilitychange 监听 | 添加 `document.addEventListener('visibilitychange', ...)` 在恢复可见时调用 connect() |
| SSE 重连后丢事件 | 未传递 last_event_id | 重连 URL 拼接 `?last_event_id=${lastEventId}` 启用后端回放 |
| SSE error 无限重连 | 无重连次数上限 | 添加 `MAX_RECONNECT` 计数器，超限后退化为轮询 |
| TypeScript 编译报 `lastEventId does not exist on EventSource` | `lastEventId` 是 `MessageEvent` 属性非 `EventSource` | 在 `app_event` 回调中用 `e.lastEventId`，error 回调中用已记录的变量 |
| 🆕 SonarQube S1874 报错 | 直接删除旧 API | 标注 `@deprecated` 后再删（保留过渡期） |
| 🆕v4.0 Tab 切换后输入数据丢失 | state 未提升至父组件 | 将共享 state 提升至 Tabs 的父组件，子组件通过 props 接收 |
| 🆕v4.0 Tab 切换后输入框焦点丢失 | `destroyInactiveTabPane` 默认为 true | 设置 `destroyInactiveTabPane={false}` |
| 🆕v4.0 外部链接被 `window.opener` 钓鱼 | `target="_blank"` 缺 `rel` | 添加 `rel="noopener noreferrer"` |
| 🆕v4.0 图标文字间距不稳定 | 依赖 JSX 空格渲染 | 用 `style={{ marginRight: 6 }}` 或 `Space` 组件 |
| 🆕v4.0 注释误导维护者 | 注释称"必须 X 顺序"但实际不存在约束 | 验证约束真实性，改为"顺序不影响结果"或删除 |
| 🆕v4.1 SSE 错误被当作"无数据"处理 | 未区分 `stage='error'` 与 `stage='done'`+0 结果 | 显式处理 `stage='error'` 分支，错误事件不进入结果渲染流程 |
| 🆕v4.1 SSE 错误未引导用户操作 | 错误事件未按 `status` 分类（401/403 应跳转登录） | 按 `status` 分类：401/403 显示"前往登录"按钮、503/504 稍后重试、502 重启提示 |
| 🆕v4.1 SSE 错误只显示通用"预览失败" | 后端返回的 `detail` 字段未透传给用户 | 提取 `data.detail` 展示具体错误信息（如"登录已过期，请前往「反爬登录管理」重新登录"） |
| 🆕v4.2 sheet 切换/快捷键导航时侧边栏 SubMenu 展开/折叠动画遮挡内容 | `openKeys` 通过 `useEffect` 联动 `autoOpenKeys`（路由变化触发重置） | 移除 `useEffect` 联动，`openKeys` 仅首次挂载初始化（`useState(() => autoOpenKeys)`），之后由用户 `onOpenChange` 控制 |
| 🆕v4.3 验证码事件永远不触发 | `new Proxy()` 赋值给局部变量后丢弃 | 赋值给实例属性或模块级变量（如 `this._proxy = new Proxy(...)`） |
| 🆕v4.3 finally 块报 ReferenceError | try 内赋值的变量在 finally 中引用，但 try 抛异常 | 前置初始化 `let x = null;` finally 中 `if (x) x.close()` |
| 🆕v4.3 健康检查显示有效但任务暂停 | 健康检查器与 worker 对"会话有效性"判断维度不同 | 状态变更双向同步：worker 检测到失效时通知 health_checker，health_checker 查询时检查 worker 状态 |
| 🆕v4.3 用户按错误提示操作但端点不存在 | 错误提示引用了未实现的 API 端点 | 提示中只引用已实现的端点，或改为可操作的 UI 指引 |
| 🆕v4.4 用户不知情下浏览器资源被占用 | 前端触发高风险功能（CDP 导入/自动同步）默认启用 | `constants.ts` 定义 `FEATURE_TOGGLES` 默认 `false`，设置页提供 Switch 开关 + 资源消耗提示文案 |
| 🆕v4.4 功能参数硬编码难扩展 | 参数直接写在组件内（如 `interval=3000`） | 集中到 `constants.ts` 的 `FEATURE_CONFIGS` 节点管理，组件通过 `useFeatureToggle(name)` Hook 读取 |
| 🆕v4.5 用户看到"登录已过期"但多查几次能成功 | 后端 RGV587=token 过期映射为 401，前端按 401 显示"登录已过期" | 前端按错误根因区分：token 过期显示"令牌临时过期，请稍后重试"（warning），登录失效才显示"请重新登录"（error） |
| 🆕v4.5 前端配置页设置了排序方式但搜索结果无变化 | 前端配置未传递给后端 API 或后端配置链路断裂 | 从前端表单→API 请求→后端 config.yaml→Worker→search()→build_search_url() 全链路追踪 |
| 🆕v4.9 累计统计类 API（频率伪装统计 / 健康评分）持续为 0 且无变化 | 前端 useEffect 仅初始化时 fetch 一次，缺少 setInterval 定时刷新 | 在 useEffect 中加 `setInterval(loadStats, POLL_INTERVALS.freqStats)` + cleanup `clearInterval`；间隔必须来自 `config.yaml` |
| 🆕v4.9 setInterval 间隔数字（10000/30000）散落在多个组件 | 间隔值未集中管理 | 在 `constants.ts` 的 `POLL_INTERVALS` 节点或 `config.yaml` 的 `freq_stats_polling` 节点统一管理 |
