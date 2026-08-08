# 前端审查判断标准

> 本文件承接 SKILL.md 中"审查判断标准"章节的详细表格，按需加载。SKILL.md 仅保留分类规则速查。

## 三级判断标准

| 🟠阻塞(必须修复) | 🟠严重(强烈建议) | 🟡警告(建议) |
|-----------------|-----------------|-------------|
| `fetch` 请求未包含 `credentials: 'include'` | 未复用组件 | 缩进不规范 |
| axios 未设 `withCredentials: true` | UI 不一致 | 变量命名不规范 |
| token 写入 `localStorage` | 缺注释 | 冗余代码 |
| 使用 `dangerouslySetInnerHTML` | 验证规则不完善 | 注释不清 |
| 使用 `any` 类型 | 错误处理不完善 | 缺少类型注解 |
| `.catch()` 空实现 | 空指针风险（链式调用未判空） | 缺少测试 |
| `v-for`/`map` 使用 index 作为 key | `useEffect` 依赖数组不完善 | 缺少文档字符串 |
| `ConfigProvider` 在 `BrowserRouter` 内层 | `useMemo`/`useCallback` 缺失 | 嵌套层级过深 |
| 三处映射不同步（路由/菜单/sheetRegistry） | `requestId` 竞态保护缺失 | 注释复述代码 |
| `enum` 替代字符串字面量联合 | `mountedRef` 缺失（卸载后 setState） | 魔法数字未提取 |
| `JSON.parse(JSON.stringify())` 深拷贝 | `refreshingRef` 并发保护缺失 | 魔法字符串 |
| 使用 `interface`（应为 `type`） | `lazyRetry` 未包装 | 函数过长 |
| `main.tsx` 入口配置错误 | `SSE_LAST_EVENT_ID_KEY` 缺失 | 缺少 `__all__` |
| 函数嵌套 > 4 层（S2004） | PWA `runtimeCaching` 未排除 `/api/events/stream` | - |
| 认知复杂度 > 15（S3776） | 路由切换未重置滚动位置 | - |
| `vite.config.ts` `base` 错误 | `partialize` 未过滤 ReactNode | - |
| 构建产物未输出到 `web/static/spa` | store 感知路由库（未用 `_navigator` 注入） | - |
| 使用箭头函数定义组件 | `useEffect` 依赖数组缺失导致 stale closure | - |
| 嵌入页面用 `minHeight: 100vh`（应 `height: 100%`） | `activateSheet` 未同步恢复 `minimized` | - |
| 交互元素文字用 `colorBorder`（应 `colorPrimary`） | antd 组件测试未 mock `matchMedia` | - |
| 状态变更操作未同步更新所有相关字段 | vitest 命令缺少 `--no-isolate` | - |
| 🆕 `<div onClick>`/`<a onClick>` 无 href（S6819/S6844） | 🆕 `useEffect` 依赖缺失导致 stale closure（S7735） | - |
| 🆕 `await` 非 `async` 函数（S7503） | 🆕 冗余可选链 `a?.b` 当 a 已非空（S6582） | - |
| 🆕 未使用的 Props/State/参数（S6767） | 🆕 重复内联样式 `abstraction_thresholds.inline_style_repeat` 次以上 | - |
| 🆕v4.0 Tab 切换数据丢失（state 未提升） | 🆕v4.0 JSX IIFE 未提取为变量 | - |
| 🆕v4.0 外部链接缺 `rel="noopener noreferrer"` | 🆕v4.0 图标文字间距依赖 JSX 空格 | - |
| 🆕v4.0 注释与代码逻辑不一致（误导性约束说明） | 🆕v4.0 动态资源映射表与推断函数混用 | - |
| 🆕v4.1 SSE 流消费回调未处理 `stage='error'` 分支 | 🆕v4.1 SSE 错误事件未按 `status` 分类，401/403 应显示"前往登录"按钮 | - |
| 🆕v4.1 SSE 错误事件与"真的没货"（`stage='done'`+0 结果）混为一谈 | - | - |
| 🆕v4.2 受控 UI 状态（`openKeys`/`expandedKeys`）通过 `useEffect` 联动路由变化（产生非用户触发的展开/折叠动画） | - | - |
| 🆕v4.3 Proxy/Observer 赋值给局部变量后丢弃（死代码） | 🆕v4.3 跨组件对同一概念判断维度未同步 | - |
| 🆕v4.3 try/finally 变量未初始化为 null/undefined | 🆕v4.3 错误提示引用不存在的路由/端点 | - |
| 🆕v4.4 高风险前端功能默认启用（应默认关闭，配置驱动）（F-REVIEW-CONFIG-DRIVEN-TOGGLE） | 🆕v4.4 功能参数硬编码在组件内（应集中在 `constants.ts` `FEATURE_TOGGLES`/`FEATURE_CONFIGS` 节点管理） | - |
| 🆕v4.5 错误提示文案与后端错误根因语义不匹配（如 token 过期显示"登录已过期"）（F-REVIEW-ERROR-SEMANTICS） | 🆕v4.5 前端配置项未传递给后端 API（配置无效化）（F-REVIEW-CONFIG-LINKAGE） | - |
| 🆕v4.9 累计统计类 API（频率伪装统计/健康评分/计数器）仅在 useEffect 初始化时拉一次，缺少 setInterval 定时刷新（F-REVIEW-FREQ-STATS-POLLING） | 🆕v4.9 setInterval 间隔数字（30000/60000）硬编码在组件内（应来自 `config.yaml` `freq_stats_polling.interval_ms` `POLL_INTERVALS` 常量） | - |
| 🆕v4.10 后端返回 `filter_summary` 但前端只显示"查询完成"不暴露过滤过程（F-REVIEW-FILTER-VISIBILITY） | 🆕v4.10 API 返回类型用 `as { filter_summary?: ... }` 强制转换绕过 TS 检查（应显式声明 `filter_summary?` 字段） | - |
| 🆕v4.11 前后端状态枚举值不对齐（前端 `types.ts` 联合类型与后端 `Enum` 不一致）（F-REVIEW-STATE-ENUM-ALIGN） | 🆕v4.11 前端硬编码状态字符串（`status === 'running'`）而非引用 `types.ts` 联合类型 | - |
| 🆕v4.11 终态（`completed`/`failed`）仍显示 loading 动画或进行中文案（F-REVIEW-STATE-MACHINE-UI） | 🆕v4.11 中间态（`pending`/`running`）缺少 loading 反馈 / 操作按钮与后端状态机白名单不一致 | - |
| 🆕v4.11 多链路触发同一状态变更时各链路独立 `setState` 推断新状态（F-REVIEW-DUAL-LINK-CACHE-CONSISTENCY） | 🆕v4.11 SSE 推送状态变更后只更新当前组件 `setState` 未刷新全局缓存 / `refetch()` 失败清空缓存 | - |

## 分类规则

- **P0 阻塞**：硬约束违规（安全漏洞/数据丢失/崩溃/认证失效）
- **P1 严重**：逻辑错误/性能问题/状态不一致/异常吞掉/stale closure
- **P2 改进**：代码质量/可维护性/配置化/重复逻辑/类型注解缺失
- **P3 微调**：风格/注释/命名优化/魔法数字提取

## 严重等级映射

| Severity | 报告分类 | 修复时序 |
|---|---|---|
| CRITICAL | P0 阻塞性问题 | 必须修复后才能合并 |
| HIGH | P1 严重问题 | 强烈建议本次迭代修复 |
| MEDIUM | P2 改进问题 | 记录到 backlog，后续迭代修复 |
| LOW | P3 微调问题 | 风格/注释/命名优化 |
