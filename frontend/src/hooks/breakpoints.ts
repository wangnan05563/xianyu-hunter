/**
 * 响应式断点的单一常量（T02562 / 2.7-5 断点统一）
 *
 * 背景：桌面外壳此前散着三套数字——Sider 收起 `innerWidth <= 768`、
 * 移动端判定 `max-width: 767px`、移动路由切换 600px，601–768px 成为
 * 「桌面外壳 + 收起侧栏 + 竖排标签栏」的死区。这里先把桌面侧统一到 768 一个常量。
 *
 * 尚未收进来的两处（口径不同，改动风险大，见 T02588 / FR-F-5）：
 * - `useMobileDetect` 的 600px 决定「走移动端路由还是桌面外壳」，与展示宽度不是同一件事；
 * - antd `breakpoint="lg"` 的实际阈值是 991.98px，且按**窗口宽**而非内容区宽判定，
 *   帮助页正文里嵌了侧栏时它并不等于 768。
 */
export const NARROW_MAX_PX = 768

/** 窄屏判定：与 CSS `max-width: 768px` 同口径（含 768 本身） */
export function isNarrowViewport(): boolean {
  return globalThis.window.innerWidth <= NARROW_MAX_PX
}

/** useIsMobile 用的是「严格小于 768」，即 max-width: 767px */
export const MOBILE_MEDIA_QUERY = `(max-width: ${NARROW_MAX_PX - 1}px)`
