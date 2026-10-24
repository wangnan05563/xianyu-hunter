/**
 * 首访自动弹出引导的「内容已渲染」门 —— 独立纯函数，供 GuideController 与单测共用
 *
 * 为什么不直接问「文档里有没有 .page-container」（T02631 根因）：
 * - MENU_GUIDES 的 29 条 route 里有 7 条页面根节点压根不带 `.page-container`
 *   （/anticrawl、/chatbot、/config/chatbot、/export、/maintenance/tunnel、/menu-admin、
 *   /price-dashboard），用「任意 page-container」当门，这 7 条首访永远不弹；
 * - SheetWorkspace 多标签下反向也不成立：后台 sheet 的旧 DOM 可能仍挂着同名节点，
 *   门被误判通过，而激活页其实还没渲染，Tour 弹在一堆已脱离文档的节点上。
 * 门只看**激活 sheet 的内容根**有没有子节点；页面没有 `.page-container` 是合法情形，
 * 步骤目标查不到时由 resolveTourTarget 降级为居中气泡。
 */

/** SheetWorkspace 的内容根（见 components/SheetWorkspace/index.tsx） */
export const SHEET_CONTENT_AREA_SELECTOR = '.sheet-content-area'

export function isPageRenderedForGuide(root: ParentNode = document): boolean {
  const area = root.querySelector(SHEET_CONTENT_AREA_SELECTOR)
  // 不在 SheetWorkspace 里（独立页/旧布局）时没有更细的容器可问，不额外设门
  if (!area) return true
  return area.childElementCount > 0
}
