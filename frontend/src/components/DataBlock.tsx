import type { ReactNode } from 'react'
import { Empty } from 'antd'
import FetchFailedHint from './FetchFailedHint'

interface DataBlockProps {
  /** 该数据源本次请求是否失败（来自 useFailedSources 的账） */
  readonly failed: boolean
  /** 数据源中文名，失败时渲染成「××加载失败」 */
  readonly source: string
  /** 真实条数；为 0 时渲染空态。失败时调用方不必关心该值 */
  readonly count?: number
  readonly emptyText: string
  readonly onRetry?: () => void
  readonly emptyImageSimple?: boolean
  readonly children: ReactNode
}

/**
 * 「错误态 / 空态 / 内容」三态二选一（T02700）。
 *
 * 为什么单独一个组件：各页原先写的是 `{list.length === 0 ? <Empty description="暂无××" /> : <Table/>}`，
 * 而 list 的兜底值是 `catch(() => [])` —— 接口失败与真的没数据走同一个分支。
 * 把三态收敛到一个组件后，调用方只需要把失败账与真实条数传进来，
 * 不可能再出现「失败也显示空态」。
 */
export default function DataBlock({
  failed, source, count, emptyText, onRetry, emptyImageSimple, children,
}: DataBlockProps) {
  if (failed) {
    return <FetchFailedHint source={source} onRetry={onRetry} />
  }
  if (count === 0) {
    return (
      <Empty
        description={emptyText}
        {...(emptyImageSimple ? { image: Empty.PRESENTED_IMAGE_SIMPLE } : {})}
      />
    )
  }
  return <>{children}</>
}
