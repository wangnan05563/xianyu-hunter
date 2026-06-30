import { Card, Button, Tooltip, theme } from 'antd'
import {
  CopyOutlined,
  ReloadOutlined,
  CheckCircleFilled,
  ArrowUpOutlined,
  WarningFilled,
} from '@ant-design/icons'
import type { UpdateState } from './useUpdateChecker'
import { TEXTS } from './i18n'

// 格式化 ISO 发布时间为本地可读日期（YYYY-MM-DD）
// 失败时回退原值，避免 UI 因后端格式异常而崩溃
function formatPublishDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

interface BrandCardProps {
  version: string
  buildDate: string
  gitSha: string
  state: UpdateState
  onCheck: () => void
  onCopy: () => void
}

// 五态按钮渲染：根据状态机（idle/loading/latest/newer/error）分别呈现
function UpdateButton({ state, onCheck }: { state: UpdateState; onCheck: () => void }) {
  switch (state.kind) {
    case 'loading':
      // antd Button 的 loading prop 已自带 spinner，无需再叠加 LoadingOutlined
      return (
        <Button loading>
          {TEXTS.updateLoading}
        </Button>
      )
    case 'latest':
      return (
        <Button type="text" icon={<CheckCircleFilled style={{ color: '#52c41a' }} />}>
          {TEXTS.updateLatest}
        </Button>
      )
    case 'newer':
      // 新版本可用：按钮跳转到 GitHub release 页面；title 展示发布时间（若有）
      // 为什么用 title 而非内联文本：避免按钮宽度溢出，发布时间作为补充信息悬浮展示
      return (
        <Tooltip
          title={
            state.publishedAt
              ? `${TEXTS.updatePublishedOn} ${formatPublishDate(state.publishedAt)}`
              : TEXTS.updateNewer
          }
        >
          <Button
            type="primary"
            icon={<ArrowUpOutlined />}
            onClick={() => globalThis.open(state.url, '_blank', 'noopener,noreferrer')}
          >
            {TEXTS.updateNewer} ({state.latest})
          </Button>
        </Tooltip>
      )
    case 'error':
      return (
        <Button
          danger
          type="text"
          icon={<WarningFilled />}
          onClick={onCheck}
        >
          {state.reason === 'network' ? TEXTS.updateErrorNetwork : TEXTS.updateErrorServer} · {TEXTS.updateRetry}
        </Button>
      )
    case 'idle':
    default:
      // idle 态通过 Tooltip 告知用户「会自动检查」，避免用户误以为必须手动点击
      return (
        <Tooltip title={TEXTS.updateAutoCheckHint}>
          <Button type="primary" icon={<ReloadOutlined />} onClick={onCheck}>
            {TEXTS.updateIdle}
          </Button>
        </Tooltip>
      )
  }
}

export function BrandCard({ version, buildDate, gitSha, state, onCheck, onCopy }: BrandCardProps) {
  const { token } = theme.useToken()
  // git_sha 为 unknown 时不显示（避免误导用户）
  const showSha = gitSha && gitSha !== 'unknown'

  return (
    <Card
      style={{
        background: token.colorBgContainer,
        border: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: 6,
        marginBottom: 24,
      }}
      styles={{ body: { padding: 20 } }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        {/* Logo：与 Swagger UI 顶栏品牌块完全一致（品牌识别统一） */}
        <div
          aria-hidden
          style={{
            width: 48,
            height: 48,
            borderRadius: 6,
            background: 'linear-gradient(135deg, #FF6200, #FF8533)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: 22,
            fontWeight: 700,
            boxShadow: '0 2px 8px rgba(255, 98, 0, 0.25)',
            flexShrink: 0,
          }}
        >
          闲
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 18, fontWeight: 600, color: token.colorText }}>
              {TEXTS.versionLabel}: {version}
            </span>
            <Tooltip title={TEXTS.copyHint}>
              <Button
                type="text"
                size="small"
                icon={<CopyOutlined />}
                onClick={onCopy}
                aria-label={TEXTS.copyAriaLabel}
              />
            </Tooltip>
          </div>
          <div style={{ fontSize: 13, color: token.colorTextSecondary, marginTop: 4 }}>
            {TEXTS.releasedOn} {buildDate}
            {showSha && (
              <span style={{ marginLeft: 8, fontFamily: 'monospace' }}>@{gitSha}</span>
            )}
          </div>
        </div>
        <UpdateButton state={state} onCheck={onCheck} />
      </div>
    </Card>
  )
}
