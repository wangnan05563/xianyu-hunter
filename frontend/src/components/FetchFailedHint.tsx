import { Alert } from 'antd'
import { TipButton } from '@/components/TipButton'

interface FetchFailedHintProps {
  /** 数据源名称，用于「××加载失败」标题 */
  readonly source: string
  readonly onRetry?: () => void
  /** 覆盖默认说明：失败后果因区块而异（如「下面是内置默认值」） */
  readonly description?: string
}

/**
 * 数据源加载失败的内联错误态（T02586 假回执清零）。
 *
 * 为什么单独一个组件：Dashboard 原先把接口失败 catch 成 null/[]，各卡片于是渲染
 * 「暂无数据」或用 0 兜底 —— 后端故障被说成「一切正常但没有数据」。这个组件把两件事
 * 分开：取到 0 条是空态，没取到是错误态，且错误态自带重试入口。
 */
export default function FetchFailedHint({ source, onRetry, description }: FetchFailedHintProps) {
  return (
    <Alert
      type="error"
      showIcon
      message={`${source}加载失败`}
      description={description ?? '接口请求失败，本区块的数字与曲线不代表真实状态。'}
      action={
        onRetry ? (
          <TipButton size="small" onClick={onRetry} tip="重新请求该数据源">
            重试
          </TipButton>
        ) : undefined
      }
      style={{ margin: '8px 0' }}
    />
  )
}
