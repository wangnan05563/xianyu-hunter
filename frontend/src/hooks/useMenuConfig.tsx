import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import {
  DashboardOutlined,
  UnorderedListOutlined,
  ShoppingOutlined,
  ThunderboltOutlined,
  AuditOutlined,
  FieldTimeOutlined,
  FileTextOutlined,
  BugOutlined,
  DollarOutlined,
  SafetyCertificateOutlined,
  BellOutlined,
  HistoryOutlined,
  RobotOutlined,
  SearchOutlined,
  MessageOutlined,
  ClearOutlined,
  DatabaseOutlined,
  CloudDownloadOutlined,
  ExperimentOutlined,
  InfoCircleOutlined,
  SettingOutlined,
  AppstoreOutlined,
  ToolOutlined,
  StarOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  TagOutlined,
  ClusterOutlined,
  ReloadOutlined,
  DeleteOutlined,
  ShoppingCartOutlined,
  CommentOutlined,
  AimOutlined,
} from '@ant-design/icons'
// 合并 value 与 type 引入，避免 S3863 重复 import
import { menuApi, MENU_GROUP_LABELS, type MenuItem } from '../api/menu'

// 图标名 → Ant Design 图标组件映射
// 为什么集中维护：后端返回字符串图标名（如 'DashboardOutlined'），前端需映射到实际组件
// 缺失的图标会兜底到 AppstoreOutlined，避免渲染崩溃
// 为什么用 typeof AppstoreOutlined 而非 React.ComponentType：
// 补全 props 泛型让类型检查更严格（ForwardRefExoticComponent<Omit<AntdIconProps,'ref'> & RefAttributes>），
// 避免导入内部 AntdIconProps 类型，直接复用图标自身的具体类型签名
type IconComp = typeof AppstoreOutlined

const iconMap: Record<string, IconComp> = {
  DashboardOutlined,
  UnorderedListOutlined,
  ShoppingOutlined,
  ThunderboltOutlined,
  AuditOutlined,
  FieldTimeOutlined,
  FileTextOutlined,
  BugOutlined,
  DollarOutlined,
  SafetyCertificateOutlined,
  BellOutlined,
  HistoryOutlined,
  RobotOutlined,
  SearchOutlined,
  MessageOutlined,
  ClearOutlined,
  DatabaseOutlined,
  CloudDownloadOutlined,
  ExperimentOutlined,
  InfoCircleOutlined,
  SettingOutlined,
  AppstoreOutlined,
  ToolOutlined,
  StarOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  TagOutlined,
  ClusterOutlined,
  ReloadOutlined,
  DeleteOutlined,
  ShoppingCartOutlined,
  CommentOutlined,
  AimOutlined,
}

// 分组中文标签：用于 SubMenu 标题
// 后端 group 字段值与 menu_registry.yaml 对齐
// 共享常量从 menu.ts 导入，避免与 MenuAdmin 重复定义导致漂移

// Ant Design Menu items 类型：兼容 divider 与 SubMenu
// 叶子节点单独定义：SubMenu 的 children 永远是叶子（不嵌套 SubMenu），
// 这样 children 内访问 key 不需要额外类型守卫
type AntMenuLeaf = { key: string; icon?: ReactNode; label: string }
type AntMenuItem =
  | (AntMenuLeaf & { children?: AntMenuLeaf[] })
  | { type: 'divider' }

// 模块级缓存：跨组件实例共享，避免路由切换重复请求
// 为什么不用 React Context：菜单数据全局共享且不频繁变化，模块级缓存更简单
let menuCache: { menus: MenuItem[]; ts: number } | null = null
const CACHE_TTL_MS = 5 * 60 * 1000 // 5 分钟

/**
 * 失效菜单缓存：切换账号后调用，确保下次 useMenuConfig 拉取新用户菜单
 */
export function invalidateMenuCache(): void {
  menuCache = null
}

/**
 * 根据 MenuItem 列表构建 Ant Design Menu items
 *
 * 渲染策略：
 * 1. 按 group 字段分组（如 'data_view'/'config'），每组渲染为 SubMenu
 * 2. 无 group 字段的菜单项作为顶层项
 * 3. system 类别的菜单项放在最底部，用 divider 分隔
 * 4. 仅渲染 visible=true 的项
 * 5. 按 sort_order 升序排列
 */
export function buildMenuItems(menus: MenuItem[]): AntMenuItem[] {
  const visible = menus.filter((m) => m.visible)
  const main = visible.filter((m) => m.category !== 'system')
  const system = visible.filter((m) => m.category === 'system')

  // 主区域：按 category 字段分组（后端 category 即为分组键）
  const groups = new Map<string, MenuItem[]>()
  for (const m of main) {
    const g = m.category || 'main'
    if (!groups.has(g)) groups.set(g, [])
    groups.get(g)!.push(m)
  }

  // 按 group 内 sort_order 排序，group 间按首个元素的 sort_order 排序
  // S4043：先在独立语句中排序，再用于 map，避免原地 sort 副作用
  const sortedGroups = Array.from(groups.entries())
    .map(([g, items]) => {
      const sortedItems = [...items].sort((a, b) => a.sort_order - b.sort_order)
      return {
        group: g,
        items: sortedItems,
        minSort: Math.min(...items.map((i) => i.sort_order)),
      }
    })
    .sort((a, b) => a.minSort - b.minSort)

  const result: AntMenuItem[] = []
  for (const { group, items } of sortedGroups) {
    // 单项 group 直接作为顶层项，避免单层 SubMenu 包裹
    if (items.length === 1) {
      const item = items[0]
      result.push({
        key: item.path,
        icon: renderIcon(item.icon),
        label: item.label,
      })
    } else {
      // 多项 group 渲染为 SubMenu
      const groupKey = `sub-${group}`
      result.push({
        key: groupKey,
        icon: renderIcon(items[0].icon),
        label: MENU_GROUP_LABELS[group] || group,
        children: items.map((item) => ({
          key: item.path,
          icon: renderIcon(item.icon),
          label: item.label,
        })),
      })
    }
  }

  // 底部 system 类别菜单项
  if (system.length > 0) {
    result.push({ type: 'divider' })
    // S4043：sort 移到独立语句，避免原地 sort 在 for 中造成副作用
    const sortedSystem = [...system].sort((a, b) => a.sort_order - b.sort_order)
    for (const item of sortedSystem) {
      result.push({
        key: item.path,
        icon: renderIcon(item.icon),
        label: item.label,
      })
    }
  }

  return result
}

// 渲染图标：未知图标名兜底到 AppstoreOutlined
function renderIcon(iconName: string): ReactNode {
  const Icon = iconMap[iconName] || AppstoreOutlined
  return <Icon />
}

/**
 * 菜单配置 Hook：加载菜单 + 图标映射 + 缓存
 *
 * 设计要点：
 * 1. 模块级缓存 5 分钟 TTL，避免路由切换重复请求
 * 2. 切换账号后调用 invalidateMenuCache() 失效缓存
 * 3. 加载中显示 Spin（由消费方根据 loading 状态控制）
 * 4. 失败时保留旧缓存数据（如有），避免菜单瞬间消失
 */
export function useMenuConfig() {
  const [menus, setMenus] = useState<MenuItem[]>(menuCache?.menus ?? [])
  const [loading, setLoading] = useState<boolean>(!menuCache)
  const [error, setError] = useState<Error | null>(null)

  const fetchMenus = useCallback(async (force: boolean = false): Promise<void> => {
    // 缓存命中且未过期：直接使用，不发请求
    if (!force && menuCache && Date.now() - menuCache.ts < CACHE_TTL_MS) {
      setMenus(menuCache.menus)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await menuApi.get()
      menuCache = { menus: data, ts: Date.now() }
      setMenus(data)
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err))
      setError(e)
      // 失败时保留旧缓存数据（如有），避免菜单瞬间消失
      if (menuCache) setMenus(menuCache.menus)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchMenus()
  }, [fetchMenus])

  // 强制刷新：切换账号 / 菜单配置变更后调用
  const refresh = useCallback(() => {
    void fetchMenus(true)
  }, [fetchMenus])

  // 预构建 antd Menu items 格式
  const menuItems = buildMenuItems(menus)

  return { menus, menuItems, loading, error, refresh }
}
