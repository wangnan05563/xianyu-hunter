import { Suspense, useMemo } from 'react'
import { Alert, Spin, Empty } from 'antd'
import { ErrorBoundary } from '../ErrorBoundary'
import { LazyErrorBoundary } from '../../utils/lazyRetry'
import { findSheetMeta } from './sheetRegistry'
import type { SheetItem } from '../../stores/sheetStore'
import { useConfigStore } from '../../stores/configStore'
import {
  collectChangedPaths,
  filterChangedPaths,
  scopeForPath,
} from '../../stores/configDirty'

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

function NotFoundSheet({ path }: { readonly path: string }) {
  return (
    <div style={{ padding: 48 }}>
      <Empty description={`未找到路径对应的页面：${path}`} />
    </div>
  )
}

/** 未保存黄条：只统计这一页自己那几段配置（T02572 项 3） */
function SheetDirtyBanner({ path }: { readonly path: string }) {
  const config = useConfigStore((s) => s.config)
  const original = useConfigStore((s) => s.original)
  const count = useMemo(() => {
    const scope = scopeForPath(path)
    if (!scope || !config || !original) return 0
    return filterChangedPaths(collectChangedPaths(config, original), scope).length
  }, [path, config, original])
  if (count === 0) return null
  return (
    <Alert
      type="warning"
      showIcon
      banner
      message={`本页有 ${count} 项改动尚未保存：切换标签页会保留草稿，关闭标签页会丢弃`}
      style={{ marginBottom: 8 }}
    />
  )
}

export function SheetContent({ sheet }: { readonly sheet?: SheetItem }) {
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
          {/* key 驱动重挂载：sheet 切换时触发淡入动画
              sheet-page-mount 让页面能参与内容区的 flex 高度分配（见 sheet.css） */}
          <div className="fade-in-up sheet-page-mount" key={sheet.id}>
            <SheetDirtyBanner path={sheet.path} />
            <Page />
          </div>
        </Suspense>
      </LazyErrorBoundary>
    </ErrorBoundary>
  )
}

export default SheetContent
