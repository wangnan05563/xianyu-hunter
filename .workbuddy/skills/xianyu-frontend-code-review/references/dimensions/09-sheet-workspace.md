# 9. SheetWorkspace 多页签系统 🆕v2.0

- 【强制】多页签系统位于 `frontend/src/components/SheetWorkspace/`，按 4 文件组织
- 【强制】`SheetPreferences` 字段：
  - `maxSheets`: [1, 10]
  - `enableAnimation`: boolean
  - `minimizeInsteadOfClose`: boolean
  - `doubleClickCloseEnabled`: boolean
  - `doubleClickInterval`: [200, 800]
  - `thumbnailMode`: boolean
  - `circularReplaceEnabled`: boolean
- 【强制】`activateSheet` 激活最小化 sheet 时必须同时恢复（`minimized: false`），否则 SheetContent 显示空状态
- 【强制】最小化标识和"恢复"提示文字用 `colorPrimary`（`activeColor`），禁止用 `colorBorder`
- 【强制】页面组件嵌入 SheetContent 时用 `height: 100%`，禁止 `minHeight: 100vh`
