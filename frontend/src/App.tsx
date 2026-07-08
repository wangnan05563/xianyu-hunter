import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, type ReactNode } from 'react'
import { App as AntdApp, Spin } from 'antd'
import MainLayout from './components/layout/MainLayout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { lazyRetry, LazyErrorBoundary } from './utils/lazyRetry'
import ReloadPrompt from './components/ReloadPrompt'
import { useMobileDetect } from './mobile/hooks/useMobileDetect'
import MobileRoutes from './mobile/routes'

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
// 关于菜单：系统元信息 + 文档资源统一入口（独立路由，与 /help 同级）
const About = lazyRetry(() => import('./pages/About'))
// 智能客服模块：对话主页 + 配置页
const Chatbot = lazyRetry(() => import('./pages/Chatbot'))
const ChatbotConfig = lazyRetry(() => import('./pages/Chatbot/Config'))
// 菜单管理页：用户级菜单可见性/排序配置（MU5）
const MenuAdmin = lazyRetry(() => import('./pages/MenuAdmin'))
// 通知中心：系统通知的列表/标记已读/删除
const Notifications = lazyRetry(() => import('./pages/Notifications'))
// 半自动模式确认抢单页：外部通知点击链接后到达，复用 manual-takeover 接口
const ConfirmBuy = lazyRetry(() => import('./pages/ConfirmBuy'))

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
function LazyRoute({ children }: { readonly children: ReactNode }) {
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
  // 路径检测必须带 /app 前缀：SPA 挂载在 /app/ 下（BrowserRouter basename="/app"）
  // S7764：用 globalThis 替代 window
  // Navigate to="/m/" 必须带尾斜杠：父路由 <Route path="/m/*"> 的 splat 要求至少匹配 "/",
  // 不带尾斜杠的 /m 不会匹配 splat 路由，导致渲染 null（白屏）
  if (isMobile && !globalThis.location.pathname.startsWith('/app/m') && !globalThis.location.pathname.startsWith('/app/login')) {
    return <Navigate to="/m/" replace />
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
            {/* 菜单管理：用户级菜单可见性/排序配置（MU5） */}
            <Route path="menu-admin" element={<LazyRoute><MenuAdmin /></LazyRoute>} />
            {/* 通知中心：系统通知列表与已读管理 */}
            <Route path="notifications" element={<LazyRoute><Notifications /></LazyRoute>} />
            {/* 半自动模式确认抢单：通知链接回链到本页 */}
            <Route path="confirm-buy" element={<LazyRoute><ConfirmBuy /></LazyRoute>} />
            {/* 智能客服：对话主页 + 配置页（含知识库管理） */}
            <Route path="chatbot" element={<LazyRoute><Chatbot /></LazyRoute>} />
            <Route path="config/chatbot" element={<LazyRoute><ChatbotConfig /></LazyRoute>} />
            {/* 帮助文档、关于：与其他菜单一致，在 SheetWorkspace 内显示 */}
            <Route path="help" element={<LazyRoute><Help /></LazyRoute>} />
            <Route path="about" element={<LazyRoute><About /></LazyRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
          {/* 移动端路由组 */}
          <Route path="/m/*" element={<MobileRoutes />} />
        </Routes>
        {/* O-12-26 PWA 更新/离线就绪提示，放在 AntdApp 内以使用主题 notification */}
        <ReloadPrompt />
      </AntdApp>
    </ErrorBoundary>
  )
}
