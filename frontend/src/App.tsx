import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy, type ReactNode } from 'react'
import { Spin } from 'antd'
import MainLayout from './components/layout/MainLayout'

// 路由懒加载：按需加载页面组件，减小首屏 bundle 体积
const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const TaskList = lazy(() => import('./pages/Tasks/TaskList'))
const TaskEditor = lazy(() => import('./pages/Tasks/TaskEditor'))
const TaskDetail = lazy(() => import('./pages/Tasks/TaskDetail'))
const ItemList = lazy(() => import('./pages/Items/ItemList'))
const Orders = lazy(() => import('./pages/Orders/Orders'))
const Evaluations = lazy(() => import('./pages/Evaluations/index'))
const Timeline = lazy(() => import('./pages/Timeline'))
const Logs = lazy(() => import('./pages/Logs/Logs'))
const PriceStrategy = lazy(() => import('./pages/Config/PriceStrategy'))
const EvalRules = lazy(() => import('./pages/Config/EvalRules'))
const NotifierChannels = lazy(() => import('./pages/Config/NotifierChannels'))
const VersionManager = lazy(() => import('./pages/Config/VersionManager'))
const AIConfig = lazy(() => import('./pages/Config/AIConfig'))
const Maintenance = lazy(() => import('./pages/Maintenance/Cleanup'))
const DatabaseAdmin = lazy(() => import('./pages/Maintenance/DatabaseAdmin'))
const SearchConfig = lazy(() => import('./pages/Config/SearchConfig'))
const BuyerStrategy = lazy(() => import('./pages/Config/BuyerStrategy'))
const Onboarding = lazy(() => import('./pages/Onboarding'))
const AntiCrawl = lazy(() => import('./pages/AntiCrawl'))

// 全局 fallback 加载组件：懒加载页面未就绪时展示
function PageLoading() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 200 }}>
      <Spin size="large" />
    </div>
  )
}

// 统一包裹懒加载组件的 Suspense 边界
function LazyRoute({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageLoading />}>{children}</Suspense>
}

export default function App() {
  return (
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
  )
}
