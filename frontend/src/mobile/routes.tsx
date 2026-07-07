import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, type ReactNode } from 'react'
import { Spin } from 'antd'
import MobileLayout from './layout/MobileLayout'
import { lazyRetry, LazyErrorBoundary } from '../utils/lazyRetry'

// 移动端页面懒加载：按需加载，减小移动端首屏 bundle
const MobileDashboard = lazyRetry(() => import('./pages/Dashboard'))
const MobileTasks = lazyRetry(() => import('./pages/Tasks'))
const MobileTaskDetail = lazyRetry(() => import('./pages/Tasks/TaskDetail'))
const MobileOrders = lazyRetry(() => import('./pages/Orders'))
const MobileOrderDetail = lazyRetry(() => import('./pages/Orders/OrderDetail'))

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
      <Route path="/m" element={<MobileLayout />}>
        <Route index element={<MobileRoute><MobileDashboard /></MobileRoute>} />
        <Route path="tasks" element={<MobileRoute><MobileTasks /></MobileRoute>} />
        <Route path="tasks/:id" element={<MobileRoute><MobileTaskDetail /></MobileRoute>} />
        <Route path="orders" element={<MobileRoute><MobileOrders /></MobileRoute>} />
        <Route path="orders/:id" element={<MobileRoute><MobileOrderDetail /></MobileRoute>} />
        <Route path="*" element={<Navigate to="/m" replace />} />
      </Route>
    </Routes>
  )
}
