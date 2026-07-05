# 多 Sheet 页工作区使用说明

## 概述

多 Sheet 页工作区是闲鱼猎人前端的通用页面容器，支持在同一会话内同时打开多个页面并以标签栏快速切换，所有菜单页面共用此工作区。

## 核心特性

- **多页面并行打开**：单个会话最多可同时打开 10 个页面（默认 5 个），便于数据对比与多任务切换
- **左侧纵向标签栏**：标签栏位于内容区左侧，纵向排列，支持图标 + 标题展示
- **Zustand 状态管理**：通过 `frontend/src/stores/sheetStore.ts` 集中管理 sheet 栈、激活项与偏好
- **URL 双向同步**：URL 变化自动同步到栈，栈切换自动更新 URL
- **会话持久化**：sheet 栈与偏好设置保存在 `localStorage`，刷新或重开浏览器后恢复
- **循环替换 + 回收栈**：达到上限时可自动淘汰最旧非激活 sheet，被淘汰项进入回收栈，5 秒内可撤销
- **缩略图模式**：sheet 数量较多时可切换为仅图标布局，节省横向空间
- **移动端自适应**：屏幕宽度 `< 768px` 时自动降级为单 sheet 模式

## 基本操作

| 序号 | 操作 | 触发方式 |
|------|------|----------|
| 1 | 打开页面（菜单点击） | 点击左侧菜单项 → 自动调用 `openSheetWithNotification` 新增 sheet |
| 2 | 打开页面（Command Palette） | `Ctrl+K` 打开命令面板 → 模糊搜索 → 选中命令 |
| 3 | 打开页面（g+X 快捷键） | 先按 `g`，500ms 内按第二个键（如 `g+t` 跳转任务管理） |
| 4 | 打开页面（URL 直接访问） | 浏览器地址栏输入路径或刷新 → `useSheetSync` 自动同步 |
| 5 | 切换 sheet | 点击左侧标签栏对应标签 → 激活该 sheet |
| 6 | 切换 sheet（浏览器前进/后退） | 浏览器导航 → `useSheetSync` 检测 URL 变化后激活对应 sheet |
| 7 | 关闭 sheet | 点击激活标签上的 × 按钮（受 `minimizeInsteadOfClose` 偏好影响） |
| 8 | 双击关闭 sheet | 在标签上快速双击（需在偏好中启用「双击关闭」） |
| 9 | 最小化 / 恢复 | 点击激活标签上的 − 按钮最小化；点击最小化标签的「恢复」恢复显示 |
| 10 | 重复打开同一路径 | 仅激活已有 sheet（不重复创建，若已最小化则同时恢复） |

> 关闭激活 sheet 后，自动激活相邻 sheet（优先右侧，无则左侧），无剩余 sheet 时跳转 `/`。

## 标签栏位置

**标签栏位于内容区左侧**（不是右侧），采用纵向布局：

- 标准模式：宽度 `80px`，每个标签纵向展示「图标 + 标题 + 操作按钮」
- 缩略图模式：宽度 `56px`，仅展示图标，鼠标悬停可查看详细信息
- 移动端：标签栏隐藏，单 sheet 全屏模式

布局结构参见 `frontend/src/components/SheetWorkspace/sheet.css` 中的 `.sheet-workspace`（flex row，标签栏在前、内容区在后）。

## 多 Sheet 状态管理

### Zustand store 核心

状态管理位于 `frontend/src/stores/sheetStore.ts`，使用 Zustand `create` 创建。核心状态字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `sheets` | `SheetItem[]` | 当前打开的 sheet 列表 |
| `activeId` | `string \| null` | 当前激活 sheet 的 id |
| `preferences` | `SheetPreferences` | 偏好设置 |
| `replacedHistory` | `ReplacedSheet[]` | 回收栈（被循环替换淘汰的 sheet 摘要） |
| `isMobile` | `boolean` | 是否移动端模式 |
| `hydrated` | `boolean` | 是否已从 localStorage 恢复 |
| `_navigator` | `fn \| null` | 注入的 navigate 函数（由 SheetWorkspace 注入） |

核心方法：`openSheet` / `closeSheet` / `activateSheet` / `minimizeSheet` / `restoreSheet` / `closeAll` / `restoreReplaced` / `clearReplacedHistory` / `setPreferences` / `hydrate` / `persist`。

### 循环替换策略

开启 `circularReplaceEnabled` 偏好后，达到 `maxSheets` 上限时的处理：

1. 从「非激活 sheet」中按 `openedAt` 升序选出最旧的一项作为淘汰目标
2. 极端情况（所有 sheet 都激活，例如 `maxSheets=1`）退回全体选择
3. 淘汰旧 sheet，新建新 sheet，新 sheet 直接成为激活项
4. 被淘汰的 sheet 摘要进入回收栈

未开启循环替换时，超限返回 `{ ok: false, reason: 'limit' }`，由调用方处理（菜单点击会无响应，需要用户先关闭一个 sheet）。

### 回收栈机制

- 容量上限：`REPLACED_HISTORY_MAX = 5`（FIFO 截断）
- 仅存储轻量摘要（`id` / `path` / `title` / `replacedAt`），不存储 `icon` 等 ReactNode
- 不参与持久化：重启后回收栈清空（避免撤销按钮指向已失效的 sheet）
- 入口：偏好面板「回收栈」区域可查看历史并「清空回收栈」

### 撤销机制

**通过 Notification Toast 内的「撤销」按钮恢复**（**非快捷键**），流程：

1. 循环替换触发时，`openSheetWithNotification` 在右上角弹出 `notification.info`
2. Toast 内嵌「撤销」按钮，5 秒内有效
3. 点击「撤销」→ 调用 `restoreReplaced(id)` 从回收栈恢复被替换的 sheet
4. 5 秒未操作视为接受替换结果，Toast 自动关闭

恢复语义：用户主动撤销自己的动作不应被拒绝，因此 `restoreReplaced` 不检查 `maxSheets` 上限（可能临时超出，下次 `openSheet` 会再触发循环替换平衡）。

## 偏好设置

入口：左侧标签栏底部的 ⚙ 按钮（仅桌面端，移动端不显示标签栏）。

共 **8 项**可配置偏好：

| 配置项 | 字段 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| 最大 Sheet 数量 | `maxSheets` | 5 | 1-10 | 同时可打开的 sheet 上限，超出按循环替换策略处理 |
| 启用切换动画 | `enableAnimation` | 开启 | 开/关 | sheet 切换时的淡入动画 |
| 关闭按钮改为最小化 | `minimizeInsteadOfClose` | 关闭 | 开/关 | 开启后关闭按钮执行最小化而非真正关闭，保留页面状态 |
| 启用双击关闭 | `doubleClickCloseEnabled` | 关闭 | 开/关 | 在 sheet 标签上快速双击即可关闭（保守默认，避免误触） |
| 双击判定间隔 | `doubleClickInterval` | 350 | 200-800 | 两次点击间隔 ≤ 此值视为双击，单位毫秒 |
| 启用缩略图模式 | `thumbnailMode` | 关闭 | 开/关 | 标签栏仅显示图标，紧凑布局可容纳更多 sheet |
| 显示悬浮提示 | `thumbnailTooltipEnabled` | 开启 | 开/关 | 缩略图模式下鼠标悬停显示 sheet 详细信息（依赖缩略图模式开启） |
| 循环替换 | `circularReplaceEnabled` | 关闭 | 开/关 | 达到上限时自动淘汰最旧非激活 sheet，被淘汰项进入回收栈 |

配置即时生效，无需重启。偏好保存在浏览器本地 `localStorage` key `xh.sheets.preferences`，跨会话保留。偏好面板提供「恢复默认」按钮一键重置。

## 快捷键

| 快捷键 | 作用 | 备注 |
|--------|------|------|
| `Ctrl+K`（或 `⌘+K`） | 打开 Command Palette | 输入框聚焦时可直接模糊搜索命令 |
| `Escape` | 关闭 Command Palette | 仅在 Command Palette 打开时生效 |
| `g` 然后按 `d` | 跳转到仪表盘 `/` | g 前缀序列，500ms 内按第二键 |
| `g` 然后按 `t` | 跳转到任务管理 `/tasks` | 同上 |
| `g` 然后按 `o` | 跳转到抢单记录 `/orders` | 同上 |
| `g` 然后按 `e` | 跳转到卖家评估 `/evaluations` | 同上 |
| `g` 然后按 `i` | 跳转到事件时间线 `/timeline` | 同上 |
| `g` 然后按 `c` | 跳转到价格策略 `/config/price` | 同上 |
| `g` 然后按 `l` | 跳转到实时日志 `/logs` | 同上 |
| `g` 然后按 `a` | 跳转到关于 `/about` | 同上 |
| `g` 然后按 `m` | 跳转到智能客服 `/chatbot` | 同上 |

> 输入框、文本域、下拉框内不触发快捷键，避免干扰正常输入。撤销最近替换**仅通过 Notification 按钮触发**，无快捷键。

## 高级功能

### 循环替换

开启偏好「循环替换」后，达到 `maxSheets` 上限时不再阻止打开新 sheet，而是自动淘汰最早打开的非激活 sheet（保护当前激活页）。被淘汰的 sheet 进入回收栈，可通过 Toast 撤销。

未开启时：超限返回 `{ ok: false, reason: 'limit' }`，菜单点击无反应（需先关闭一个 sheet）。

### 回收栈

回收栈保存最近被循环替换淘汰的 sheet 摘要：

- 容量上限 5 条（FIFO 截断）
- 偏好面板「回收栈」区域可查看历史与清空
- 不持久化：刷新或重启浏览器后回收栈为空（避免撤销按钮指向已失效的 sheet）

### 撤销机制

循环替换触发后，右上角弹出 Notification Toast：

- 标题：「已自动替换 sheet」
- 描述：最旧非激活 sheet 标题
- 操作：内嵌「撤销」按钮，点击调用 `restoreReplaced` 恢复
- 时效：5 秒内有效，超时自动关闭
- 入口：`frontend/src/components/SheetWorkspace/sheetNotifications.tsx`

### 缩略图模式

开启偏好「启用缩略图模式」后：

- 标签栏宽度从 `80px` 收窄至 `56px`
- 仅显示图标，不显示标题
- 激活态保留微型关闭按钮（避免缩略图模式下无关闭途径）
- 最小化状态用 `●` 标识
- 配合「显示悬浮提示」可查看 sheet 名称、路径、创建时间、状态等详细信息

### 通知机制

循环替换触发时通过 antd `notification`（非 `message`）发出带操作按钮的提示：

- 位置：右上角 `topRight`
- 持续：5 秒自动关闭
- 内容：标题 + 被替换 sheet 名称 + 撤销按钮
- 设计原因：antd v5 `message` 不支持 `btn` 字段，无法嵌入撤销按钮

## 组件结构

### 组件树

```
SheetWorkspace (容器组件，无 props)
├── SheetTabs (左侧标签栏)
│   ├── TabItem (单个标签)
│   │   ├── StandardTab (标准模式：图标 + 纵向标题 + 操作按钮)
│   │   └── ThumbnailTab (缩略图模式：仅图标 + Tooltip)
│   └── 偏好设置入口按钮 (底部 ⚙)
├── SheetContent (内容区)
│   ├── ErrorBoundary (外层：捕获页面同步渲染错误)
│   ├── LazyErrorBoundary (内层：捕获 chunk 加载失败)
│   └── Suspense + 懒加载页面组件
└── SheetPreferences (偏好设置抽屉，placement=right)
```

### 文件职责

| 文件 | 职责 |
|------|------|
| `frontend/src/components/SheetWorkspace/index.tsx` | 容器组件，组装标签栏/内容区/偏好面板，注入 navigate 与移动端模式 |
| `frontend/src/components/SheetWorkspace/SheetTabs.tsx` | 左侧标签栏，含标准/缩略图两种 Tab 渲染模式与双击关闭判定 |
| `frontend/src/components/SheetWorkspace/SheetContent.tsx` | 内容区，含两层 ErrorBoundary 与 Suspense 懒加载 |
| `frontend/src/components/SheetWorkspace/SheetPreferences.tsx` | 偏好设置抽屉，含回收栈展示与清空 |
| `frontend/src/components/SheetWorkspace/sheetRegistry.tsx` | path → 页面组件 + 元数据映射表 |
| `frontend/src/components/SheetWorkspace/sheetNotifications.tsx` | `openSheetWithNotification` 包装函数，循环替换时发 Toast |
| `frontend/src/components/SheetWorkspace/sheet.css` | 布局样式与动画 |
| `frontend/src/stores/sheetStore.ts` | Zustand store，状态/操作/持久化/回收栈 |
| `frontend/src/hooks/useSheetSync.ts` | URL ↔ sheet 栈双向同步 Hook |
| `frontend/src/hooks/useIsMobile.ts` | 移动端断点检测（`max-width: 767px`） |

### 数据流

```
用户操作（菜单/快捷键/URL）
        ↓
openSheetWithNotification (sheetNotifications.tsx)
        ↓
useSheetStore.openSheet (sheetStore.ts)
        ↓
   ┌────┴────┐
   │ 已存在？│ → 激活现有 sheet（必要时恢复最小化）
   └────┬────┘
        ↓ 否
   ┌────┴────┐
   │ 桌面端？│
   └────┬────┘
        ↓ 是
   ┌────────────┐
   │ 达上限？    │ → 是 → circularReplaceEnabled?
   └────┬───────┘          ↓ 是              ↓ 否
        ↓ 否          循环替换 + 回收栈    返回 { ok: false, reason: 'limit' }
   创建新 sheet
        ↓
   navigate (注入的 _navigator) → URL 更新
        ↓
   useSheetSync 检测 URL 变化 → 防循环判断 → 必要时再调 openSheet
```

## 常见问题 FAQ

**Q1：为什么刷新后 URL 与激活 sheet 一致？**
A：`useSheetSync` Hook 实现了 URL↔栈双向同步。刷新时 `hydrate()` 恢复栈，`useSheetSync` 检测到 URL 与激活 sheet path 不一致时以 URL 为准。

**Q2：打开第 6 个 sheet 时无反应怎么办？**
A：默认 `maxSheets=5` 且未开启循环替换。两种方案：
1. 关闭一个已打开的 sheet 后再尝试
2. 在偏好设置中开启「循环替换」（自动淘汰最旧非激活 sheet）或调大「最大 Sheet 数量」（上限 10）

**Q3：移动端为什么不能多开？**
A：屏幕宽度 `< 768px` 时自动降级为单 sheet 模式：不显示标签栏，打开新页面时替换当前 sheet（不累计），不受 `maxSheets` 限制。

**Q4：撤销按钮为什么 5 秒后消失？**
A：循环替换属于「需要稍长时间决策」的操作，5 秒足够用户读完标题并决定是否撤销。超时视为接受替换结果。重启后回收栈清空，无法跨会话撤销。

**Q5：重启浏览器后回收栈为什么是空的？**
A：回收栈依赖 `replacedAt` 时间戳计算 5 秒撤销窗口，重启后时间戳已过期，恢复无意义且可能导致撤销按钮指向已失效的 sheet。回收栈仅在当前会话内有效。

**Q6：偏好设置修改后未生效？**
A：偏好即时生效，无需重启。若未生效请检查浏览器 `localStorage` 中 `xh.sheets.preferences` 是否被外部覆盖。偏好面板「恢复默认」可一键重置。

**Q7：双击关闭为什么默认关闭？**
A：保守默认值，避免误触关闭未保存数据。如需启用，在偏好设置中开启「启用双击关闭」，可配合「双击判定间隔」（200-800ms）调整灵敏度。

**Q8：登出后会保留 sheet 栈吗？**
A：不会。登出时清空 sheet 栈，避免下一用户看到上一用户的页面。偏好设置不清理（跨会话保留用户习惯）。

## localStorage 键说明

| Key | 内容 | 持久化范围 | 清理方式 |
|-----|------|-----------|----------|
| `xh.sheets.state` | sheet 栈（id/path/minimized/openedAt）+ activeId | 当前会话 + 跨会话恢复 | 登出自动清理；偏好面板「恢复默认」不清理此项 |
| `xh.sheets.preferences` | 偏好配置（8 项） | 跨会话保留 | 偏好面板「恢复默认」重置；登出不清理 |

> `icon` 与 `title` 不持久化：运行时从 `sheetRegistry` 重建，避免 ReactNode 序列化问题。`replacedHistory` 不持久化（理由见 FAQ Q5）。

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v2.0 | 2026-07-05 | 修正标签栏位置（左侧非右侧）；补全 8 项偏好设置；补全 10 项基本操作；新增循环替换、回收栈、撤销机制、缩略图模式、通知机制章节；新增组件结构与数据流；扩充 FAQ 至 8 项 |
| v1.0 | 早期 | 初版使用说明 |
