import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, type ReactNode } from 'react'
import { Spin } from 'antd'
import MainLayout from './components/layout/MainLayout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { lazyRetry, LazyErrorBoundary } from './utils/lazyRetry'

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
const SearchConfig = lazyRetry(() => import('./pages/Config/SearchConfig'))
const BuyerStrategy = lazyRetry(() => import('./pages/Config/BuyerStrategy'))
const Onboarding = lazyRetry(() => import('./pages/Onboarding'))
const AntiCrawl = lazyRetry(() => import('./pages/AntiCrawl'))
const Help = lazyRetry(() => import('./pages/Help'))

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
  return (
    <ErrorBoundary>
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
          <Route path="config/price" element={<LazyRoute><PriceStrategy /></LazyRoute>} />
          <Route path="config/eval" element={<LazyRoute><EvalRules /></LazyRoute>} />
          <Route path="config/notifier" element={<LazyRoute><NotifierChannels /></LazyRoute>} />
          <Route path="config/version" element={<LazyRoute><VersionManager /></LazyRoute>} />
          <Route path="config/ai" element={<LazyRoute><AIConfig /></LazyRoute>} />
          <Route path="config/search" element={<LazyRoute><SearchConfig /></LazyRoute>} />
          <Route path="config/buyer" element={<LazyRoute><BuyerStrategy /></LazyRoute>} />
          <Route path="maintenance" element={<LazyRoute><Maintenance /></LazyRoute>} />
          <Route path="maintenance/db" element={<LazyRoute><DatabaseAdmin /></LazyRoute>} />
          <Route path="anticrawl" element={<LazyRoute><AntiCrawl /></LazyRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  )
}
