# 17. 可访问性评审

- 【强制】交互元素（特别是图标按钮）必须有 `aria-label`
- 【强制】表单控件必须有 `label` 关联
- 【推荐】颜色对比度达标（WCAG AA）
- 【推荐】键盘导航支持（Tab 顺序、Enter/Space 触发）
- 【推荐】屏幕阅读器友好性（语义化标签、`role` 属性）
- 🆕v4.0【强制】**外部链接安全**：`target="_blank"` 必须加 `rel="noopener noreferrer"`（防 `window.opener` 钓鱼 + 不泄露 Referer）
