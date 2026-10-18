import client from './client'

// 菜单分组类别：与后端 menu_registry.yaml group 字段对齐
// 为什么用字面量联合而非 enum：保持与后端 YAML 字符串一致，避免双重维护
// 为什么不用 | string：会让整个字面量联合失去类型检查意义，所有 typo 都被静默接受
// 已知 group 值来自 menu_registry.yaml，新增 group 需同步扩展此类型
export type MenuCategory =
  | 'overview'
  | 'data_view'
  | 'config'
  | 'maintenance'
  | 'other'
  | 'main'
  | 'system'

// 菜单文案单源索引（T02556 / FR-B-4）
// 为什么需要它：菜单名有四处在用（侧栏、面包屑、命令面板、标签栏），历史上各维护一张常量表，
// 结果同一个页面在四处叫法不同（/items 商品中心 vs 商品列表）。/api/menu 是唯一的权威源，
// 其余三处都应从这份索引取 label，不再各自硬编码。
// 由 useMenuConfig 在拉到菜单后写入；菜单尚未到达时索引为空，调用方回退到本地兜底标题
// （兜底标题由 navSingleSource 测试锁住与 registry 一致，因此回退不会出现第二种叫法）。
let labelByPath: Readonly<Record<string, string>> = {}

export function setMenuLabelIndex(menus: readonly MenuItem[]): void {
  const next: Record<string, string> = {}
  for (const m of menus) {
    if (m.path) next[m.path] = m.label
  }
  labelByPath = next
}

/** 取菜单权威标题：仅精确匹配菜单页，子页面（/tasks/:id）返回 undefined 由调用方兜底 */
export function menuLabelForPath(path: string): string | undefined {
  return labelByPath[path]
}

// 菜单分组中文标签：useMenuConfig 与 MenuAdmin 共享，避免重复定义导致漂移
// 后端 group 字段值与 menu_registry.yaml 对齐
export const MENU_GROUP_LABELS: Record<string, string> = {
  overview: '总览',
  data_view: '数据查看',
  config: '配置管理',
  maintenance: '系统维护',
  other: '其他',
  main: '主要功能',
  system: '系统',
}

// 菜单项结构：对应后端 GET /api/menu 返回的 MenuItem
// 字段命名与后端 snake_case 保持一致，避免前后端转换开销
// 项目规范：用 type 而非 interface 定义数据结构
export type MenuItem = {
  /** 菜单唯一标识，对应 registry 的 key（如 'tasks'/'dashboard'） */
  key: string
  /** 显示名称（已合并 custom_label，前端直接展示） */
  label: string
  /** Ant Design 图标组件名（如 'DashboardOutlined'），前端通过 iconMap 映射 */
  icon: string
  /** 路由路径（如 '/tasks'） */
  path: string
  /** 排序值，升序排列 */
  sort_order: number
  /** 是否可见 */
  visible: boolean
  /** 锁定项（后端强制可见，如菜单管理自身）：UI 需置灰可见性开关 */
  locked?: boolean
  /** 分组类别（对应 registry 的 group 字段） */
  category: MenuCategory
}

// PUT /api/menu 单项更新载荷：字段名与后端 api_menu.py MenuItemUpdate 逐字对齐
// 后端只接受 key/visible/sort_order；group/custom_label 需先扩后端模型（决策门 D-11），
// 未实现前不得出现在请求类型里，否则等于给用户一个写了也不生效的输入框
export type MenuItemUpdate = {
  key: string
  visible?: boolean
  sort_order?: number
}

// 菜单配置 API：管理用户级菜单配置（可见性/排序/别名）
// 与后端 api_menu.py 契约对齐：GET/PUT/POST /api/menu
export const menuApi = {
  // 获取当前用户菜单（已合并 registry 默认值 + 用户自定义）
  get: () =>
    client.get<{ menus: MenuItem[] }>('/api/menu').then((r) => r.data.menus),

  // 批量更新用户菜单配置（全量覆盖）：后端 MenuUpdateBody 的外层键是 menus
  update: (items: MenuItemUpdate[]) =>
    client.put<{ ok: boolean }>('/api/menu', { menus: items }).then((r) => r.data),

  // 重置为默认配置（删除 user_menu_configs 记录）
  reset: () =>
    client.post<{ ok: boolean }>('/api/menu/reset').then((r) => r.data),
}
