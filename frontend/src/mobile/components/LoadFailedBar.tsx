// frontend/src/mobile/components/LoadFailedBar.tsx
// 移动端窄屏用的单行失败条（T02701）。
// 桌面端用 FetchFailedHint（antd Alert 带 description），移动端放不下两行文案，
// 所以这里只保留「哪个数据源失败 + 这块数字不可信 + 重试」，样式与 Empty 空态明确区分：
// 取到 0 条是空态，没取到是错误态。
import { Button, theme } from 'antd'
import { ExclamationCircleFilled, ReloadOutlined } from '@ant-design/icons'

interface LoadFailedBarProps {
  /** 数据源中文名，渲染成「××加载失败」 */
  readonly source: string
  /** 可选补充说明，例如「保留上一次的数据」 */
  readonly note?: string
  readonly onRetry?: () => void
}

export default function LoadFailedBar({ source, note, onRetry }: LoadFailedBarProps) {
  const { token } = theme.useToken()
  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 10px',
        marginBottom: 8,
        borderRadius: 6,
        fontSize: 12,
        lineHeight: '18px',
        background: token.colorErrorBg,
        color: token.colorErrorText,
        border: `1px solid ${token.colorErrorBorder}`,
      }}
    >
      <ExclamationCircleFilled style={{ flex: 'none' }} />
      <span style={{ flex: 1 }}>
        {source}加载失败
        {note ? ` · ${note}` : ' · 本区块数字不代表真实状态'}
      </span>
      {onRetry && (
        <Button
          size="small"
          type="text"
          icon={<ReloadOutlined />}
          onClick={onRetry}
          style={{ color: token.colorErrorText, flex: 'none' }}
        >
          重试
        </Button>
      )}
    </div>
  )
}
