/**
 * 侧栏收起状态的决策（纯函数，可脱离 React 单测）—— T02632 条目 1
 *
 * 原状：MainLayout 的 resize 监听只在 `isNarrowViewport()` 为真时 `setCollapsed(true)`，
 * 从窄窗拉回宽窗不会自动展开。实测把窗口 768 → 900px 后，侧栏仍停在 64px 收起态，
 * 用户得自己找到展开按钮再点一次——收起是系统替他做的，还原却要他做。
 *
 * 修法要点：只在「这次收起确实是窗口宽度造成的、且用户期间没有自己开合过」时才对称展开。
 * 用户手动开合代表显式意图，之后跨断点不再覆盖它（否则用户刚展开就被窗口尺寸变化顶掉）。
 */
export type SidebarCollapseState = {
  /** 侧栏当前是否收起 */
  collapsed: boolean
  /** 当前这次收起是不是「因为窗口窄」自动发生的 */
  autoCollapsed: boolean
}

/** 首屏状态：窗口本来就窄 → 默认收起，并记住这次收起是系统做的 */
export function initialCollapseState(narrowAtMount: boolean): SidebarCollapseState {
  return { collapsed: narrowAtMount, autoCollapsed: narrowAtMount }
}

/** 窗口尺寸变化：进入窄档自动收起；离开窄档只撤销自动收起的那一次 */
export function collapseOnResize(prev: SidebarCollapseState, narrow: boolean): SidebarCollapseState {
  if (narrow) {
    return prev.collapsed ? prev : { collapsed: true, autoCollapsed: true }
  }
  return prev.autoCollapsed ? { collapsed: false, autoCollapsed: false } : prev
}

/** 用户主动开合：显式意图优先，清掉自动收起标记 */
export function collapseByUser(prev: SidebarCollapseState, collapsed: boolean): SidebarCollapseState {
  return prev.collapsed === collapsed ? prev : { collapsed, autoCollapsed: false }
}
