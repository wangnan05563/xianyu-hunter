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

/** 桌面窄窗上界：与 antd `breakpoint="lg"`（991.98px）同档，标签栏仍在但空间吃紧 */
export const NARROW_DESKTOP_MAX_PX = 992

/** 窄屏判定：与 CSS `max-width: 768px` 同口径（含 768 本身） */
export function isNarrowViewport(): boolean {
  return globalThis.window.innerWidth <= NARROW_MAX_PX
}

/**
 * 桌面窄窗判定：宽度 ∈ (NARROW_MAX_PX, NARROW_DESKTOP_MAX_PX]
 *
 * 为什么单独一档：≤768 由 `useIsMobile` 走移动端外壳（标签栏根本不渲染，
 * 「切缩略模式」无对象）；这一档是「桌面外壳 + 标签栏还在 + 横向空间吃紧」，
 * 缩略模式只在这里有意义（T02632 条目 2 的引导提示作用域）。
 */
export function isNarrowDesktopViewport(width: number = globalThis.window.innerWidth): boolean {
  return width > NARROW_MAX_PX && width <= NARROW_DESKTOP_MAX_PX
}

/** useIsMobile 用的是「严格小于 768」，即 max-width: 767px */
export const MOBILE_MEDIA_QUERY = `(max-width: ${NARROW_MAX_PX - 1}px)`
