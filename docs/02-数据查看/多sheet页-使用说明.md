# 多 Sheet 页工作区使用说明

## 概述

系统采用多 sheet 页工作区模式，支持同时打开多个页面进行对比查看。每个 sheet 在右侧标签栏显示，点击标签切换激活页面。

## 基本操作

### 打开页面
- 点击左侧菜单项 → 自动在标签栏新增一个 sheet
- Command Palette（Ctrl+K）选择命令 → 自动新增 sheet
- g+X 快捷键导航 → 自动新增 sheet
- 同一页面重复打开 → 仅激活已有 sheet，不重复开

### 切换 sheet
- 点击右侧标签栏的对应标签 → 激活该 sheet
- 浏览器前进/后退 → 自动切换激活 sheet

### 关闭 sheet
- 点击激活 sheet 标签上的关闭按钮（×）
- 偏好「关闭按钮改为最小化」开启时，关闭按钮变为最小化（保留 sheet 状态）

### 最小化 / 恢复
- 点击激活 sheet 标签上的最小化按钮（−）
- 最小化后内容不渲染，释放资源
- 点击最小化标签的「恢复」恢复显示

## 偏好设置

入口：右侧标签栏底部的 ⚙ 按钮（桌面端）

| 配置项 | 默认值 | 取值范围 | 说明 |
|--------|--------|----------|------|
| 最大 Sheet 数量 | 5 | 1-10 | 同时可打开的 sheet 上限，超出时阻止并提示 |
| 启用切换动画 | 开启 | 开/关 | sheet 切换时的淡入动画 |
| 关闭按钮改为最小化 | 关闭 | 开/关 | 开启后关闭按钮执行最小化而非真正关闭 |

配置即时生效，无需重启。偏好保存在浏览器本地，跨会话保留。

## 移动端适配

屏幕宽度 < 768px 时自动降级为单 sheet 模式：
- 不显示标签栏
- 打开新页面时替换当前 sheet（不累计）
- 不受最大 sheet 数量限制
- 偏好设置入口在 Header 用户菜单内（未来扩展，当前仅桌面端）

## 状态恢复

刷新页面或重开浏览器后，自动恢复上次会话的 sheet 栈：
- 已打开的 sheet 列表
- 当前激活的 sheet
- 偏好设置

登出时会清空 sheet 栈，避免下一用户看到上一用户的页面。

## localStorage 键说明

| Key | 内容 | 清理方式 |
|-----|------|----------|
| `xh.sheets.state` | sheet 栈 + activeId | 登出自动清理；偏好面板「恢复默认」不清理此项 |
| `xh.sheets.preferences` | 偏好配置 | 偏好面板「恢复默认」重置；登出不清理 |

## 前端组件 API

### `<SheetWorkspace />`

无 props，自包含容器组件。消费 `useSheetStore` 与 `useSheetSync`。

### `useSheetStore`

```typescript
import { useSheetStore } from './stores/sheetStore'

// 读取状态
const { sheets, activeId, preferences } = useSheetStore()

// 操作
useSheetStore.getState().openSheet('/tasks')        // 打开/激活 sheet
useSheetStore.getState().closeSheet(id)              // 关闭 sheet
useSheetStore.getState().activateSheet(id)           // 激活 sheet
useSheetStore.getState().minimizeSheet(id)           // 最小化
useSheetStore.getState().restoreSheet(id)            // 恢复
useSheetStore.getState().closeAll()                  // 关闭全部
useSheetStore.getState().setPreferences({ maxSheets: 8 })  // 更新偏好
```

### `sheetRegistry`

```typescript
import { sheetRegistry, findSheetMeta } from './components/SheetWorkspace/sheetRegistry'

// 查找路径对应的 sheet 元数据
const meta = findSheetMeta('/tasks/123')
// { path: '/tasks/:id', title: '任务详情', icon: ..., component: ... }
```

## 使用示例

### 菜单点击打开 sheet

```typescript
// 菜单 onClick：直接调 openSheet，store 内部负责 navigate
useSheetStore.getState().openSheet(key)
```

### Command Palette 导航

```typescript
// 无需改动：navigate(key) → useSheetSync 监听 URL 变化 → 自动 openSheet
navigate(item.key)
```

## 常见问题

**Q: 为什么刷新后 URL 与激活 sheet 一致？**
A: `useSheetSync` Hook 实现了 URL↔栈双向同步。刷新时 `hydrate()` 恢复栈，`useSheetSync` 检测到 URL 与激活 sheet path 不一致时以 URL 为准。

**Q: 打开第 6 个 sheet 时提示已达上限怎么办？**
A: 关闭一个已打开的 sheet，或在偏好设置中调大「最大 Sheet 数量」（上限 10）。

**Q: 移动端为什么不能多开？**
A: 小屏幕多 sheet 拥挤影响体验，移动端默认单 sheet 替换模式。
