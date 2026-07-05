import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, type ReactNode } from 'react'
import { App as AntdApp, Spin } from 'antd'
import MainLayout from './components/layout/MainLayout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { lazyRetry, LazyErrorBoundary } from './utils/lazyRetry'
import ReloadPrompt from './components/ReloadPrompt'
import { useMobileDetect } from './mobile/hooks/useMobileDetect'
// 移动端路由临时禁用：mobile/routes.tsx 引用的页面组件（Dashboard/Tasks/Orders/TabBar/OfflineBanner）尚未实现
// 待移动端模块开发完成后再启用 import MobileRoutes from './mobile/routes'

// 路由懒加载：按需加载页面组件，减小首屏 bundle 体积
// 使用 lazyRetry 包装：网络抖动或部署时 chunk 失效可自动重试，避免白屏
const Login = lazyRetry(() => import('./pages/Login'))
const Dashboard = lazyRetry(() => import('./pages/Dashboard'))
const TaskList = lazyRetry(() => import('./pages/Tasks/TaskList'))
const TaskEditor = lazyRetry(() => import('./pages/Tasks/TaskEditor'))
const TaskDetail = lazyRetry(() => import('./pages/Tasks/TaskDetail'))
const ItemList = lazyRetry(() => import('./pages/Items/ItemList'))
const Orders = lazyRetry(() => import('./pages/Orders/Orders'))
const Evaluations = lazyRetry(() => import('./pages/Evaluations/index'))
const Timeline = lazyRetry(() => import('./pages/Timeline'))
const Logs = lazyRetry(() => import('./pages/Logs/Logs'))
const ErrorLogs = lazyRetry(() => import('./pages/Logs/ErrorLogs'))
// 通知中心：业务通知列表（未读/已读/全部筛选、单条/全部已读、删除/清空已读）
const Notifications = lazyRetry(() => import('./pages/Notifications'))
const PriceStrategy = lazyRetry(() => import('./pages/Config/PriceStrategy'))
const EvalRules = lazyRetry(() => import('./pages/Config/EvalRules'))
const NotifierChannels = lazyRetry(() => import('./pages/Config/NotifierChannels'))
const VersionManager = lazyRetry(() => import('./pages/Config/VersionManager'))
const AIConfig = lazyRetry(() => import('./pages/Config/AIConfig'))
const Maintenance = lazyRetry(() => import('./pages/Maintenance/Cleanup'))
const DatabaseAdmin = lazyRetry(() => import('./pages/Maintenance/DatabaseAdmin'))
const VectorAdmin = lazyRetry(() => import('./pages/Maintenance/VectorAdmin'))
const BatchRefresh = lazyRetry(() => import('./pages/Maintenance/BatchRefresh'))
const SearchConfig = lazyRetry(() => import('./pages/Config/SearchConfig'))
const BuyerStrategy = lazyRetry(() => import('./pages/Config/BuyerStrategy'))
const Onboarding = lazyRetry(() => import('./pages/Onboarding'))
const AntiCrawl = lazyRetry(() => import('./pages/AntiCrawl'))
const Help = lazyRetry(() => import('./pages/Help'))
// 关于菜单：系统元信息 + 文档资源统一入口（嵌入 MainLayout 的 SheetWorkspace 内）
const About = lazyRetry(() => import('./pages/About'))
// 智能客服模块：对话主页 + 配置页
const Chatbot = lazyRetry(() => import('./pages/Chatbot'))
const ChatbotConfig = lazyRetry(() => import('./pages/Chatbot/Config'))
// 菜单管理页：用户级菜单可见性/排序配置（MU5）
const MenuAdmin = lazyRetry(() => import('./pages/MenuAdmin'))
// 数据导出页：独立路由，提供完整筛选条件（task_id/时间范围/状态/等级/limit）
const Export = lazyRetry(() => import('./pages/Export'))
// 价格行情：品类价格统计 + 横向对比 + 捡漏价格参考
const PriceDashboard = lazyRetry(() => import('./pages/PriceDashboard'))

// 全局 fallback 加载组件：懒加载页面未就绪时展示
function PageLoading() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 200 }}>
      <Spin size="large" />
    </div>
  )
}

// 统一包裹懒加载组件的 Suspense 边界
// 关键修复：在外层包一层 LazyErrorBoundary，捕获 chunk 加载失败错误，
// 避免 Suspense 无法捕获同步错误导致白屏
function LazyRoute({ children }: { children: ReactNode }) {
  return (
    <LazyErrorBoundary>
      <Suspense fallback={<PageLoading />}>{children}</Suspense>
    </LazyErrorBoundary>
  )
}

export default function App() {
  const isMobile = useMobileDetect()

  // 移动端 UA 自动跳转到 /m/* 路由
  // 桌面端访问 /m/* 重定向到桌面路由
  // 移动端模块未实现时跳过自动跳转，避免重定向到不存在的 /m 路由
  if (isMobile && !window.location.pathname.startsWith('/login')) {
    // 待移动端模块完成后恢复: return <Navigate to="/m" replace />
  }

  return (
    <ErrorBoundary>
      {/* AntdApp 提供 App.useApp() 上下文，让 ReloadPrompt 能用主题化的 notification */}
      <AntdApp>
        <Routes>
          {/* 登录页独立路由，不嵌套在 MainLayout 中 */}
          <Route path="/login" element={<LazyRoute><Login /></LazyRoute>} />
          {/* 引导页独立路由，不嵌套在 MainLayout 中 */}
          <Route path="/onboarding" element={<LazyRoute><Onboarding /></LazyRoute>} />
          {/* 帮助文档独立路由，不嵌套在 MainLayout 中（含自有顶部导航） */}
          <Route path="/help" element={<LazyRoute><Help /></LazyRoute>} />
          <Route path="/" element={<MainLayout />}>
            <Route index element={<LazyRoute><Dashboard /></LazyRoute>} />
            <Route path="tasks" element={<LazyRoute><TaskList /></LazyRoute>} />
            <Route path="tasks/new" element={<LazyRoute><TaskEditor /></LazyRoute>} />
            <Route path="tasks/:id/edit" element={<LazyRoute><TaskEditor /></LazyRoute>} />
            <Route path="tasks/:id" element={<LazyRoute><TaskDetail /></LazyRoute>} />
            <Route path="items" element={<LazyRoute><ItemList /></LazyRoute>} />
            <Route path="orders" element={<LazyRoute><Orders /></LazyRoute>} />
            <Route path="evaluations" element={<LazyRoute><Evaluations /></LazyRoute>} />
            <Route path="timeline" element={<LazyRoute><Timeline /></LazyRoute>} />
            <Route path="logs" element={<LazyRoute><Logs /></LazyRoute>} />
            <Route path="logs/errors" element={<LazyRoute><ErrorLogs /></LazyRoute>} />
            <Route path="notifications" element={<LazyRoute><Notifications /></LazyRoute>} />
            <Route path="config/price" element={<LazyRoute><PriceStrategy /></LazyRoute>} />
            <Route path="config/eval" element={<LazyRoute><EvalRules /></LazyRoute>} />
            <Route path="config/notifier" element={<LazyRoute><NotifierChannels /></LazyRoute>} />
            <Route path="config/version" element={<LazyRoute><VersionManager /></LazyRoute>} />
            <Route path="config/ai" element={<LazyRoute><AIConfig /></LazyRoute>} />
            <Route path="config/search" element={<LazyRoute><SearchConfig /></LazyRoute>} />
            <Route path="config/buyer" element={<LazyRoute><BuyerStrategy /></LazyRoute>} />
            <Route path="maintenance" element={<LazyRoute><Maintenance /></LazyRoute>} />
            <Route path="maintenance/db" element={<LazyRoute><DatabaseAdmin /></LazyRoute>} />
            <Route path="maintenance/vector" element={<LazyRoute><VectorAdmin /></LazyRoute>} />
            <Route path="batch-refresh" element={<LazyRoute><BatchRefresh /></LazyRoute>} />
            <Route path="anticrawl" element={<LazyRoute><AntiCrawl /></LazyRoute>} />
            {/* 价格行情：品类价格统计 + 横向对比 + 捡漏价格参考 */}
            <Route path="price-dashboard" element={<LazyRoute><PriceDashboard /></LazyRoute>} />
            {/* 菜单管理：用户级菜单可见性/排序配置（MU5） */}
            <Route path="menu-admin" element={<LazyRoute><MenuAdmin /></LazyRoute>} />
            {/* 智能客服：对话主页 + 配置页（含知识库管理） */}
            <Route path="chatbot" element={<LazyRoute><Chatbot /></LazyRoute>} />
            <Route path="config/chatbot" element={<LazyRoute><ChatbotConfig /></LazyRoute>} />
            {/* 数据导出：独立页面提供完整筛选条件 */}
            <Route path="export" element={<LazyRoute><Export /></LazyRoute>} />
            {/* 关于菜单：嵌入 MainLayout 的 SheetWorkspace 内展示版本/许可/文档资源（非全屏） */}
            <Route path="about" element={<LazyRoute><About /></LazyRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
          {/* 移动端路由组临时禁用：mobile 模块页面组件未实现，待完成后恢复 */}
          {/* <Route path="/m/*" element={<MobileRoutes />} /> */}
        </Routes>
        {/* O-12-26 PWA 更新/离线就绪提示，放在 AntdApp 内以使用主题 notification */}
        <ReloadPrompt />
      </AntdApp>
    </ErrorBoundary>
  )
}
