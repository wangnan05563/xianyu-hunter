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
  AimOutlined,
  SearchOutlined,
  BellOutlined,
  HistoryOutlined,
  RobotOutlined,
  MessageOutlined,
  ClearOutlined,
  DatabaseOutlined,
  CloudDownloadOutlined,
  ExperimentOutlined,
  InfoCircleOutlined,
  BlockOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { lazyRetry } from '../../utils/lazyRetry'

export interface SheetMeta {
  /** 稳定路径或带 :param 的模式（如 /tasks/:id） */
  path: string
  /** 标签栏标题 */
  title: string
  /** 标签栏图标 */
  icon: ReactNode
  /** 懒加载页面组件（复用 App.tsx 的 lazyRetry） */
  component: React.LazyExoticComponent<React.ComponentType<any>>
}

/**
 * sheet 页映射表：path → 页面组件 + 元数据
 *
 * 为什么独立维护而非从 App.tsx 提取：
 * 1. App.tsx 用 JSX <Route> 声明，无法直接反射为数据结构
 * 2. 此表同时承载 icon/title 元数据，供标签栏、偏好、恢复时重建使用
 * 3. 与 MainLayout 的 ROUTE_LABELS/COMMAND_ITEMS 元数据保持一致，未来可合并
 *
 * 维护约定：新增路由时需同步 App.tsx + 此表 + MainLayout 菜单
 */
export const sheetRegistry: SheetMeta[] = [
  { path: '/', title: '仪表盘', icon: <DashboardOutlined />, component: lazyRetry(() => import('../../pages/Dashboard')) },
  { path: '/tasks', title: '任务管理', icon: <UnorderedListOutlined />, component: lazyRetry(() => import('../../pages/Tasks/TaskList')) },
  { path: '/tasks/new', title: '新建任务', icon: <UnorderedListOutlined />, component: lazyRetry(() => import('../../pages/Tasks/TaskEditor')) },
  { path: '/tasks/:id', title: '任务详情', icon: <UnorderedListOutlined />, component: lazyRetry(() => import('../../pages/Tasks/TaskDetail')) },
  { path: '/tasks/:id/edit', title: '编辑任务', icon: <UnorderedListOutlined />, component: lazyRetry(() => import('../../pages/Tasks/TaskEditor')) },
  { path: '/items', title: '商品列表', icon: <ShoppingOutlined />, component: lazyRetry(() => import('../../pages/Items/ItemList')) },
  { path: '/orders', title: '抢单记录', icon: <ThunderboltOutlined />, component: lazyRetry(() => import('../../pages/Orders/Orders')) },
  { path: '/evaluations', title: '评估明细', icon: <AuditOutlined />, component: lazyRetry(() => import('../../pages/Evaluations/index')) },
  { path: '/timeline', title: '事件时间线', icon: <FieldTimeOutlined />, component: lazyRetry(() => import('../../pages/Timeline')) },
  { path: '/logs', title: '实时日志', icon: <FileTextOutlined />, component: lazyRetry(() => import('../../pages/Logs/Logs')) },
  { path: '/logs/errors', title: '错误日志', icon: <BugOutlined />, component: lazyRetry(() => import('../../pages/Logs/ErrorLogs')) },
  { path: '/config/price', title: '价格策略', icon: <DollarOutlined />, component: lazyRetry(() => import('../../pages/Config/PriceStrategy')) },
  { path: '/config/eval', title: '评估规则', icon: <SafetyCertificateOutlined />, component: lazyRetry(() => import('../../pages/Config/EvalRules')) },
  { path: '/config/notifier', title: '通知渠道', icon: <BellOutlined />, component: lazyRetry(() => import('../../pages/Config/NotifierChannels')) },
  { path: '/config/version', title: '配置版本', icon: <HistoryOutlined />, component: lazyRetry(() => import('../../pages/Config/VersionManager')) },
  { path: '/config/ai', title: 'AI 服务', icon: <RobotOutlined />, component: lazyRetry(() => import('../../pages/Config/AIConfig')) },
  { path: '/config/search', title: '搜索参数', icon: <SearchOutlined />, component: lazyRetry(() => import('../../pages/Config/SearchConfig')) },
  { path: '/config/buyer', title: '抢单策略', icon: <AimOutlined />, component: lazyRetry(() => import('../../pages/Config/BuyerStrategy')) },
  { path: '/config/chatbot', title: '客服配置', icon: <MessageOutlined />, component: lazyRetry(() => import('../../pages/Chatbot/Config')) },
  { path: '/maintenance', title: '系统清理', icon: <ClearOutlined />, component: lazyRetry(() => import('../../pages/Maintenance/Cleanup')) },
  { path: '/maintenance/db', title: '数据库维护', icon: <DatabaseOutlined />, component: lazyRetry(() => import('../../pages/Maintenance/DatabaseAdmin')) },
  { path: '/maintenance/vector', title: '向量数据库维护', icon: <DatabaseOutlined />, component: lazyRetry(() => import('../../pages/Maintenance/VectorAdmin')) },
  { path: '/batch-refresh', title: '批量采集', icon: <CloudDownloadOutlined />, component: lazyRetry(() => import('../../pages/Maintenance/BatchRefresh')) },
  { path: '/anticrawl', title: '反爬登录管理', icon: <ExperimentOutlined />, component: lazyRetry(() => import('../../pages/AntiCrawl')) },
  { path: '/price-dashboard', title: '价格行情', icon: <DollarOutlined />, component: lazyRetry(() => import('../../pages/PriceDashboard')) },
  { path: '/notifications', title: '通知中心', icon: <BellOutlined />, component: lazyRetry(() => import('../../pages/Notifications')) },
  { path: '/menu-admin', title: '菜单管理', icon: <SettingOutlined />, component: lazyRetry(() => import('../../pages/MenuAdmin')) },
  { path: '/chatbot', title: '智能客服对话', icon: <MessageOutlined />, component: lazyRetry(() => import('../../pages/Chatbot')) },
  { path: '/about', title: '关于', icon: <InfoCircleOutlined />, component: lazyRetry(() => import('../../pages/About')) },
  { path: '/export', title: '数据导出', icon: <CloudDownloadOutlined />, component: lazyRetry(() => import('../../pages/Export')) },
  { path: '/help', title: '帮助文档', icon: <BlockOutlined />, component: lazyRetry(() => import('../../pages/Help')) },
]

/**
 * 将 :param 模式路径转为正则，如 /tasks/:id → /^\/tasks\/[^/]+$/
 */
function pathToRegex(pattern: string): RegExp {
  // :param 匹配单个路径段（不含 /），避免 /tasks/123/edit 误匹配 /tasks/:id
  const re = pattern.replaceAll(/:[^/]+/g, '[^/]+')
  return new RegExp(`^${re}$`)
}

/**
 * 按 path 查找 sheet 元数据
 * 优先精确匹配，其次 :param 通配匹配
 */
export function findSheetMeta(path: string): SheetMeta | undefined {
  // 1. 精确匹配
  const exact = sheetRegistry.find((s) => s.path === path)
  if (exact) return exact
  // 2. :param 通配匹配
  return sheetRegistry.find((s) => s.path.includes(':') && pathToRegex(s.path).test(path))
}
