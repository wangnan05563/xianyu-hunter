/**
 * 导览步骤目标解析 —— 独立纯函数，供 GuideController 与单测共用
 *
 * 为什么单独成文件：解析逻辑不依赖 React/antd 运行时（只用 type import），
 * 抽出来可被 jsdom 单测直接覆盖，不必把整个 antd 依赖图拖进测试。
 */
import type { TourStepProps } from 'antd'

/**
 * 可作为高亮目标的最大尺寸（相对视口比例）
 *
 * 超过该比例的视为「整页容器」，不再做元素定位/高亮，改为居中展示。
 * 取 0.9 而非 1：留出边距，避免紧贴视口边缘的容器仍触发 scrollIntoView 抖动。
 */
export const MAX_TARGET_VIEWPORT_RATIO = 0.9

/**
 * 把步骤 selector 解析为 antd Tour 的 target
 *
 * 为什么返回**函数**而不是元素本身（T01713 根因修复）：
 * antd Tour 的 target 支持 `() => HTMLElement`，rc-tour 每次渲染/定位都会重新调用。
 * 若在 useMemo 中同步 `document.querySelector()` 拿到静态引用，SPA 内路由切换
 * （点侧边栏菜单）时会发生：
 *   1. pathname 变化 → GuideController 重渲染 → useMemo 重算，此刻 React 尚未提交、
 *      DOM 还是**旧页面**，于是抓到的是「即将卸载的旧 .page-container 节点」；
 *   2. React 提交后旧页面卸载，该节点脱离文档；
 *   3. rc-tour 对脱离文档的节点取 getBoundingClientRect() → 全 0，
 *      按 placement=bottom 算出 ≈(x:-34, y:18) —— 气泡跑到左上角且左边缘被截断。
 * 改为函数后，rc-tour 在每轮 useLayoutEffect（DOM 已更新）里实时查询，永远拿到当前页面节点。
 *
 * 两种降级为「居中」（返回 null）的情形：
 * 1. 查不到 / 已脱离文档 / 尚无布局（0 尺寸）——用 0 rect 会算出越界坐标；
 * 2. 整页容器（尺寸 ≥ 视口 90%）——rc-tour 对「未完整落入视口」的 target 会强制
 *    scrollIntoView({block:'center'})，对高于视口的容器会把页面滚到容器中心，
 *    气泡再按容器底边计算就被丢到视口外（实测仪表盘 2623px 容器 → 气泡 y=-12，顶部截断）；
 *    且高亮整页容器在视觉上等同整屏遮罩，无信息量。
 */
export function resolveTourTarget(selector?: string): TourStepProps['target'] {
  if (!selector) return undefined
  return (() => {
    const el = document.querySelector(selector)
    // S6582：!el || !el.isConnected 等价于 !el?.isConnected（el 为 null 时取反仍为 true）
    if (!el?.isConnected) return null
    const rect = el.getBoundingClientRect()
    // 尚无布局（0 尺寸）时按无目标处理，避免用 0 rect 算出越界坐标
    if (!rect.width || !rect.height) return null
    const vw = window.innerWidth || document.documentElement.clientWidth
    const vh = window.innerHeight || document.documentElement.clientHeight
    if (
      vh > 0 &&
      rect.height >= vh * MAX_TARGET_VIEWPORT_RATIO
    ) {
      return null
    }
    if (
      vw > 0 &&
      rect.width >= vw * MAX_TARGET_VIEWPORT_RATIO
    ) {
      return null
    }
    return el as HTMLElement
  }) as unknown as TourStepProps['target']
}
