# 前端 UI

> 移动端检测、响应式断点、设备仿真、操作项分级、SPA 渲染容错、UI 视觉门控、React 状态选型、过滤结果透明化、URL 状态同步、SW 缓存版本同步。
>
> 涵盖规范: #56, #64, #65, #67, #68, #69, #83, #95, #103, #107, #116, #117, #118, #119
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #56 过滤结果透明化 UI
≥2 个过滤参数时必须透明化展示当前生效的过滤规则组合：Tooltip 说明 + filter_summary 三态（无数据/被过滤/全部）+ 参数语义化
- grep: `grep "filter.*range\|market.*ratio" <page>.tsx` 但无 `Tooltip` / `filter_summary` → 违规

### #64 URL↔状态同步失败回退
SheetWorkspace 中 openSheet 失败时 URL 已变但 activeId 未变，必须 navigate 回退
- grep: `grep "useSheetSync" frontend/src/hooks/` 但无 `useNavigate` → 缺 navigate

### #65 Service Worker 缓存版本同步
PWA 构建版本哈希必须与运行时检测版本一致，不一致时触发 skipWaiting 强制更新
- grep: `grep "navigator.serviceWorker.getRegistration" frontend/src/` 缺失 → 缺版本检测

### #67 移动端检测多重 fallback
iPadOS 13+ UA 伪装为 macOS，触摸检测需要 `ontouchend` + `maxTouchPoints` 双 fallback
- grep: `grep "ontouchend.*in.*document" frontend/src/` 无 `maxTouchPoints` → CRITICAL

### #68 响应式断点统一规范
路由跳转阈值可独立于 UI 响应式阈值，但差异必须显式声明；CSS 媒体查询与 UI Hook 对齐
- grep: `grep "767\|768\|600" frontend/src/` 多个不同值 → 断点分散

### #69 设备仿真模式验证清单
设备仿真必须验证 UA、maxTouchPoints、innerWidth 三者与目标设备一致
- grep: Playwright 设备仿真测试无 `evaluate` 验证 UA/maxTouchPoints → 不完整

### #83 UI 操作项分级保留与多视图一致性
操作按钮 >5 个时必须按频率分级（高频文字/中频图标/低频收入 Dropdown），表格与卡片视图操作集合必须一致
- grep: `grep "<Button" <page>.tsx` 计数 ≥6 且无 `<Dropdown` / `<Popover` → 违规

### #95 SPA 渲染容错体系
渲染容错三件套【强制】：全局 ErrorBoundary + lazyRetry + 路由级 ErrorBoundary；401 跳转必须防抖
- grep: `grep "BrowserRouter" frontend/src/App.tsx` 附近无 `<ErrorBoundary>` → 缺全局 ErrorBoundary

### #103 UI 视觉变更预确认门控
视觉风格变更 ≥10 个组件时，必须先预览再全量替换，记录回滚清单
- grep: `git diff` 涉及 ≥10 个图标/主题色/布局变更 → 必须预确认

### #107 React 状态选型判断矩阵
usePersistentState（跨刷新）> Zustand（跨组件）> useState（组件内）；禁止 useState 存持久化偏好
- grep: `grep "useState" <file>.tsx` 变量名含 `mode`/`theme`/`view` → 应改为 usePersistentState

### #116 源码受保护（清理脚本禁删/截断 tracked 源文件）
任何「清理/删除」脚本或命令执行前必须 `git status --short` 守卫，清理白名单只含 build 产物 / node_modules / .cache / 临时日志 / __pycache__；**绝对禁止**匹配 `src/`、`frontend/src/`、`*.css`、`*.ts(x)`、`*.py` 等 tracked 源码
- grep: `grep -rn "rm -rf\|Remove-Item\|del " scripts/ config/ --include="*.bat" --include="*.ps1"` 命中但无 `git status` 守卫 / 无白名单排除 `src/` → 违规

### #117 PWA 子路径导航回退绝对化
`base` 非 `/` 时 `navigateFallback` 必须绝对路径 `base + 'index.html'`（如 `/xianyu/index.html`）；workbox 必须 `cleanupOutdatedCaches: true`；`index.html` 必须有加载占位
- grep: `grep "navigateFallback" frontend/vite.config.ts` 值为 `'index.html'` 或相对路径 → 违规；`grep "cleanupOutdatedCaches" frontend/vite.config.ts` 缺失 → 违规

### #118 SPA 基路径三处对齐
`vite.config.ts base` ⇄ `main.tsx <BrowserRouter basename>` ⇄ 后端 `_serve_spa_request` 剥离前缀 三处一致；所有「自动打开浏览器」入口统一 `<base>`，禁止 `/` 或 `/app/`
- grep: `grep "basename" frontend/src/main.tsx` 与 `grep "base:" frontend/vite.config.ts` 不一致 → 违规；`grep "start.*http" scripts/` 含 `/app/` 或裸 `/` 入口 → 违规

### #119 前端设计令牌集中化
颜色/圆角/间距集中在 `:root` CSS 变量或主题 token，禁止组件/页面内硬编码十六进制色值；装饰色一律移除改用品牌灰阶，文本色满足 WCAG AA
- grep: `grep -rn "#[0-9a-fA-F]\{6\}" frontend/src/pages/**/*.tsx` 组件内联 style 含硬编码色值 → 违规（排除 token 定义文件与 svg fill 约定）
