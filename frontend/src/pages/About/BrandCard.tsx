import { Card, Progress, theme } from 'antd'
import { TipButton } from '@/components/TipButton'
import {
  CopyOutlined,
  ReloadOutlined,
  CheckCircleFilled,
  ArrowUpOutlined,
  WarningFilled,
  DownloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import type { UpdateState, UpdateDownload } from './useUpdateChecker'
import { TEXTS } from './i18n'
import { formatShortDateTime } from '../../utils/timeFormat'

// 计算下载百分比（total 为 0 时显示不确定进度）
function downloadPercent(download: UpdateDownload): number {
  if (download.total <= 0) return 0
  return Math.min(100, Math.round((download.done / download.total) * 100))
}

interface BrandCardProps {
  readonly version: string
  readonly buildDate: string
  readonly gitSha: string
  readonly state: UpdateState
  readonly download: UpdateDownload
  readonly onCheck: () => void
  readonly onCopy: () => void
  readonly onUpdate: () => void
  readonly onInstall: () => void
}

// newer 态携带 latest/publishedAt，单独取出该分支类型供渲染函数使用
type NewerState = Extract<UpdateState, { kind: 'newer' }>

interface NewerStateProps {
  readonly state: NewerState
  readonly download: UpdateDownload
  readonly onUpdate: () => void
  readonly onInstall: () => void
}

// S3776：把 newer 态的三个子分支拆成独立函数，避免全部堆在 UpdateButton 的 switch 里
// 下载进行中/已完成：进度条 + 安装按钮，不可重复点击
function renderDownloadProgress({ download, onInstall }: NewerStateProps) {
  const installing = download.installing
  const done = download.status === 'done'
  const buttonText = done ? TEXTS.updateInstallConfirm : TEXTS.updateDownloadProgress
  const percent = done ? 100 : downloadPercent(download)
  const strokeColor = done ? '#52c41a' : undefined
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 120 }}>
        <Progress
          percent={percent}
          size="small"
          showInfo={done}
          strokeColor={strokeColor}
        />
      </div>
      <TipButton
        tip={buttonText}
        type={done ? 'primary' : 'default'}
        icon={done ? <ThunderboltOutlined /> : <DownloadOutlined />}
        loading={installing}
        disabled={!done}
        onClick={onInstall}
      >
        {buttonText}
      </TipButton>
    </div>
  )
}

// 下载出错：显示错误 + 重试下载按钮
function renderDownloadError({ download, onUpdate }: NewerStateProps) {
  const tipText = download.message || '下载失败，点击重试'
  return (
    <TipButton tip={tipText} danger icon={<WarningFilled />} onClick={onUpdate}>
      {download.message || '下载失败，重试'}
    </TipButton>
  )
}

// 空闲：展示「立即更新」主按钮
function renderIdleNewer({ state, onUpdate }: NewerStateProps) {
  let tip: string = TEXTS.updateNewer
  if (state.publishedAt) {
    tip = `${TEXTS.updatePublishedOn} ${formatShortDateTime(state.publishedAt, 'date')}`
  }
  return (
    <TipButton
      tip={tip}
      type="primary"
      icon={<ArrowUpOutlined />}
      onClick={onUpdate}
    >
      {TEXTS.updateInstallNow} ({state.latest})
    </TipButton>
  )
}

function renderNewerState(props: NewerStateProps) {
  const { download } = props
  if (download.status === 'downloading' || download.status === 'done') {
    return renderDownloadProgress(props)
  }
  if (download.status === 'error') {
    return renderDownloadError(props)
  }
  return renderIdleNewer(props)
}

// 五态更新按钮：根据状态机（idle/loading/latest/newer/error）渲染；
// newrer 态细分为「立即更新 / 下载进度 / 安装」三阶段
function UpdateButton({
  state, onCheck, download, onUpdate, onInstall,
}: {
  readonly state: UpdateState
  readonly onCheck: () => void
  readonly download: UpdateDownload
  readonly onUpdate: () => void
  readonly onInstall: () => void
}) {
  switch (state.kind) {
    case 'loading':
      // antd Button 的 loading prop 已自带 spinner，无需再叠加 LoadingOutlined
      return (
        <TipButton tip="正在检查更新" loading>
          {TEXTS.updateLoading}
        </TipButton>
      )
    case 'latest':
      return (
        <TipButton tip="已是最新版本" type="text" icon={<CheckCircleFilled style={{ color: '#52c41a' }} />}>
          {TEXTS.updateLatest}
        </TipButton>
      )
    case 'newer':
      return renderNewerState({ state, download, onUpdate, onInstall })
    case 'error':
      return (
        <TipButton
          tip="检查更新失败，点击重试"
          danger
          type="text"
          icon={<WarningFilled />}
          onClick={onCheck}
        >
          {state.reason === 'network' ? TEXTS.updateErrorNetwork : TEXTS.updateErrorServer} · {TEXTS.updateRetry}
        </TipButton>
      )
    case 'idle':
    default:
      // idle 态通过 Tooltip 告知用户「会自动检查」，避免用户误以为必须手动点击
      return (
        <TipButton tip={TEXTS.updateAutoCheckHint} type="primary" icon={<ReloadOutlined />} onClick={onCheck}>
          {TEXTS.updateIdle}
        </TipButton>
      )
  }
}

export function BrandCard({
  version, buildDate, gitSha, state, onCheck, onCopy, download, onUpdate, onInstall,
}: BrandCardProps) {
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
            <TipButton
              tip={TEXTS.copyHint}
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={onCopy}
              aria-label={TEXTS.copyAriaLabel}
            />
          </div>
          <div style={{ fontSize: 13, color: token.colorTextSecondary, marginTop: 4 }}>
            {TEXTS.releasedOn} {buildDate}
            {showSha && (
              <span style={{ marginLeft: 8, fontFamily: 'monospace' }}>@{gitSha}</span>
            )}
          </div>
        </div>
        <UpdateButton
          state={state}
          onCheck={onCheck}
          download={download}
          onUpdate={onUpdate}
          onInstall={onInstall}
        />
      </div>
    </Card>
  )
}
