import { MENU_GROUP_LABELS, menuGroupByKey } from '../../api/menu'
import type { MenuItem } from '../../api/menu'
import { findSheetMeta } from '../SheetWorkspace/sheetRegistry'

// 面包屑的一级结构（不含 JSX）：渲染层把 href 转 <Link>、current 转末级高亮，
// 计算逻辑单独成函数便于脱离 antd/Router 上下文做单元测试
export type Crumb = {
  readonly label: string
  readonly href?: string
  readonly current?: boolean
}

/**
 * 按「当前路径 + 菜单事实源」计算面包屑
 *
 * 首页 > 分组 > 页面；详情页（/tasks/123）多一级，父级菜单项作为可点链接回所属列表。
 * 名称取自 GET /api/menu 的 label/category，不再维护第二份路径→中文名表，
 * 否则同一页面会在侧栏与面包屑各处叫法不一致（E01/N1 的根因）。
 */
export function buildBreadcrumbs(pathname: string, menus: MenuItem[]): Crumb[] {
  const root: Crumb = { label: '首页', href: '/' }
  if (pathname === '/') return [{ ...root, current: true }]

  // 最长前缀匹配：/tasks/123 归到菜单项 /tasks，/logs/errors 归到自身
  const hit = menus
    .filter((m) => m.path !== '/' && (pathname === m.path || pathname.startsWith(`${m.path}/`)))
    .sort((a, b) => b.path.length - a.path.length)[0]

  if (!hit) {
    // 菜单里没有这条路径（独立页/参数页）：显式给出页面名，而不是面包屑只剩「首页」
    return [root, { label: findSheetMeta(pathname)?.title ?? '独立页面', current: true }]
  }

  const out: Crumb[] = [root]
  // 分组名优先取 registry 的 groups.label（与侧栏 SubMenu 同源），兜底用内置中文表
  const groupLabel = menuGroupByKey(hit.category)?.label ?? MENU_GROUP_LABELS[hit.category]
  if (groupLabel) out.push({ label: groupLabel })

  if (pathname === hit.path) {
    return [...out, { label: hit.label, current: true }]
  }
  out.push({ label: hit.label, href: hit.path })
  const tail = findSheetMeta(pathname)
  // S7750：tsconfig lib 为 ES2021（无 findLast / at），改为按下标取最后一段，语义与 filter(...).pop() 一致
  const segments = pathname.split('/').filter(Boolean)
  const lastSegment = segments.length > 0 ? segments[segments.length - 1] : pathname
  const tailLabel = tail?.title ?? lastSegment
  return [...out, { label: tailLabel, current: true }]
}
