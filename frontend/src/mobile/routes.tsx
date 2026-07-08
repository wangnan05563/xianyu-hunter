import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, type ReactNode } from 'react'
import { Spin } from 'antd'
import MobileLayout from './layout/MobileLayout'
import { lazyRetry, LazyErrorBoundary } from '../utils/lazyRetry'

// 移动端页面懒加载：按需加载，减小移动端首屏 bundle
const MobileDashboard = lazyRetry(() => import('./pages/Dashboard'))
const MobileTasks = lazyRetry(() => import('./pages/Tasks'))
const MobileTaskDetail = lazyRetry(() => import('./pages/Tasks/TaskDetail'))
const MobileTaskEditor = lazyRetry(() => import('./pages/TaskEditor'))
const MobileOrders = lazyRetry(() => import('./pages/Orders'))
const MobileOrderDetail = lazyRetry(() => import('./pages/Orders/OrderDetail'))
const MobileTimeline = lazyRetry(() => import('./pages/Timeline'))
const MobileNotifications = lazyRetry(() => import('./pages/Notifications'))
const MobileAntiCrawl = lazyRetry(() => import('./pages/AntiCrawl'))
const MobileItems = lazyRetry(() => import('./pages/Items'))
const MobileEvaluations = lazyRetry(() => import('./pages/Evaluations'))
const MobileChatbot = lazyRetry(() => import('./pages/Chatbot'))

function MobilePageLoading() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 200 }}>
      <Spin size="large" />
    </div>
  )
}

function MobileRoute({ children }: { readonly children: ReactNode }) {
  return (
    <LazyErrorBoundary>
      <Suspense fallback={<MobilePageLoading />}>{children}</Suspense>
    </LazyErrorBoundary>
  )
}

export default function MobileRoutes() {
  return (
    <Routes>
      {/* descendant Routes 看到的 pathname 是去掉父路由 /m 前缀后的剩余路径
          例如 URL /m/tasks → descendant pathname = "/tasks"
          所以根路由用 path="/" 匹配剩余路径，子路由用相对路径 tasks/orders 等 */}
      <Route path="/" element={<MobileLayout />}>
        <Route index element={<MobileRoute><MobileDashboard /></MobileRoute>} />
        {/* 任务管理：列表路由带尾斜杠，与 TabBar/MobileHeader 导航路径一致，避免 v7 严格匹配 404 */}
        <Route path="tasks/" element={<MobileRoute><MobileTasks /></MobileRoute>} />
        <Route path="tasks/new" element={<MobileRoute><MobileTaskEditor /></MobileRoute>} />
        <Route path="tasks/:id" element={<MobileRoute><MobileTaskDetail /></MobileRoute>} />
        <Route path="tasks/:id/edit" element={<MobileRoute><MobileTaskEditor /></MobileRoute>} />
        {/* 抢单记录 */}
        <Route path="orders/" element={<MobileRoute><MobileOrders /></MobileRoute>} />
        <Route path="orders/:id" element={<MobileRoute><MobileOrderDetail /></MobileRoute>} />
        {/* 告警与监控 */}
        <Route path="timeline/" element={<MobileRoute><MobileTimeline /></MobileRoute>} />
        <Route path="notifications/" element={<MobileRoute><MobileNotifications /></MobileRoute>} />
        <Route path="anticrawl/" element={<MobileRoute><MobileAntiCrawl /></MobileRoute>} />
        {/* 数据查询 */}
        <Route path="items/" element={<MobileRoute><MobileItems /></MobileRoute>} />
        <Route path="evaluations/" element={<MobileRoute><MobileEvaluations /></MobileRoute>} />
        {/* 智能客服 */}
        <Route path="chatbot/" element={<MobileRoute><MobileChatbot /></MobileRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
