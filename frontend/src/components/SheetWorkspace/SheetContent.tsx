import { Suspense } from 'react'
import { Spin, Empty } from 'antd'
import { ErrorBoundary } from '../ErrorBoundary'
import { LazyErrorBoundary } from '../../utils/lazyRetry'
import { findSheetMeta } from './sheetRegistry'
import type { SheetItem } from '../../stores/sheetStore'

/**
 * 单个 sheet 内容渲染区
 *
 * 为什么用两层 ErrorBoundary：
 * - 外层 ErrorBoundary（resetKeys=[path]）捕获页面同步渲染错误
 * - 内层 LazyErrorBoundary 专门捕获 chunk 加载失败（与 App.tsx LazyRoute 模式一致）
 */
function PageLoading() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 200 }}>
      <Spin size="large" />
    </div>
  )
}

function NotFoundSheet({ path }: { path: string }) {
  return (
    <div style={{ padding: 48 }}>
      <Empty description={`未找到路径对应的页面：${path}`} />
    </div>
  )
}

export function SheetContent({ sheet }: { sheet?: SheetItem }) {
  // 无 sheet 或激活 sheet 已最小化：显示空状态
  if (!sheet || sheet.minimized) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <Empty description="未打开任何页面，请从左侧菜单选择" />
      </div>
    )
  }

  const meta = findSheetMeta(sheet.path)
  if (!meta) return <NotFoundSheet path={sheet.path} />

  const Page = meta.component
  return (
    <ErrorBoundary resetKeys={[sheet.path]}>
      <LazyErrorBoundary resetKey={sheet.path}>
        <Suspense fallback={<PageLoading />}>
          {/* key 驱动重挂载：sheet 切换时触发淡入动画 */}
          <div className="fade-in-up" key={sheet.id}>
            <Page />
          </div>
        </Suspense>
      </LazyErrorBoundary>
    </ErrorBoundary>
  )
}

export default SheetContent
