// frontend/src/mobile/pages/AntiCrawl/index.tsx
import { Card, Tag, Spin, App, Button, Progress, Alert, Space, theme } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { anticrawlApi } from '../../../api'
import type { SessionStatus, HealthReport } from '../../../api/anticrawl'
import { extractApiError } from '../../../utils/apiError'
import { formatDuration } from '../../../utils/timeFormat'
import { useFailedSources } from '../../../hooks/useFailedSources'
import LoadFailedBar from '../../components/LoadFailedBar'
import PullToRefresh from '../../components/PullToRefresh'

// 时长口径取自 utils/timeFormat（T02884）：这里原先自己有一份 formatDuration，
// 与共享实现只在单位字形上不同（1h 11m vs 1 小时 11 分），两份实现会在 60 秒边界上分叉。
// 窄屏用 compact 选项，而不是再养一个 helper。

// 提取到模块级：分支逻辑下沉以降低 MobileAntiCrawl 认知复杂度（S3776），并便于单独测试
const getSessionLight = (
  session: SessionStatus | null,
  themeToken: ReturnType<typeof theme.useToken>['token'],
): { color: string; text: string } => {
  // active 优先；其次 token_expired 用橙色提示 token 失效但会话未结束；默认红色 inactive
  if (session?.active) return { color: themeToken.colorSuccess, text: '运行中' }
  if (session?.token_expired) return { color: themeToken.colorWarning, text: 'Token 失效' }
  return { color: themeToken.colorError, text: '未激活' }
}

// 提取到模块级：用 if 替代嵌套三元，同时解决 S3358 可读性问题
const getScoreColor = (
  score: number | null,
  themeToken: ReturnType<typeof theme.useToken>['token'],
): string => {
  // 健康分颜色档位：绿/橙/红/灰，给用户直观等级感
  if (score === null) return themeToken.colorTextDisabled
  if (score >= 80) return themeToken.colorSuccess
  if (score >= 50) return themeToken.colorWarning
  return themeToken.colorError
}

// 数据源（T02718）：会话与健康分开记账，失败时不能渲染成「未激活 / 全红叉」
type AntiCrawlSource = 'session' | 'health'
const SOURCE_LABELS: Record<AntiCrawlSource, string> = {
  session: '会话状态',
  health: '健康报告',
}

export default function MobileAntiCrawl() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [session, setSession] = useState<SessionStatus | null>(null)
  const [health, setHealth] = useState<HealthReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const { failed, settle } = useFailedSources<AntiCrawlSource>()

  const fetchAll = useCallback(async () => {
    // 两路各自记账：任一路失败只挂自己的错误条，
    // 且不能把「取不到会话」显示成「未激活」、「取不到健康」显示成一排红叉
    const [sRes, hRes] = await Promise.allSettled([
      anticrawlApi.getSessionStatus(),
      anticrawlApi.checkHealth(),
    ])
    const s = settle(sRes, 'session')
    if (s) setSession(s)
    const h = settle(hRes, 'health')
    if (h) setHealth(h)
    setLoading(false)
  }, [settle])

  // 30s 定时轮询 + visibility 暂停：页面不可见时停止轮询，恢复时立即拉取并重启定时器
  useEffect(() => {
    let id: ReturnType<typeof setInterval> | null = null
    const start = () => {
      fetchAll()
      id = setInterval(fetchAll, 30_000)
    }
    const stop = () => {
      if (id) { clearInterval(id); id = null }
    }
    const onVisibility = () => {
      if (document.hidden) stop()
      else start()
    }
    start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [fetchAll])

  // 启停会话：完成后再拉一次最新状态，确保 UI 与后端一致
  const handleToggleSession = async (start: boolean) => {
    setActionLoading(true)
    try {
      if (start) {
        await anticrawlApi.startSession()
        message.success('会话已启动')
      } else {
        await anticrawlApi.stopSession()
        message.success('会话已停止')
      }
      await fetchAll()
    } catch (e) {
      message.error(extractApiError(e, start ? '启动失败' : '停止失败'), 3)
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  // 状态灯颜色：active 优先，其次 token_expired 用橙色提示 token 失效但会话未结束
  const { color: computedLightColor, text: computedLightText } = getSessionLight(session, themeToken)
  // 取不到会话时不能显示「未激活」——那是把未知当成了确定结论
  const sessionUnknown = failed.session && session === null
  const lightColor = sessionUnknown ? themeToken.colorTextDisabled : computedLightColor
  const lightText = sessionUnknown ? '状态未知' : computedLightText

  // 健康分颜色档位：绿/橙/红，给用户直观等级感
  const healthScore = health?.score ?? session?.health_score ?? null
  const scoreColor = getScoreColor(healthScore, themeToken)

  return (
    <PullToRefresh onRefresh={fetchAll}>
      {failed.session && (
        <LoadFailedBar
          source={SOURCE_LABELS.session}
          note="会话是否运行未知，下方内容不作数"
          onRetry={() => void fetchAll()}
        />
      )}
      {failed.health && (
        <LoadFailedBar
          source={SOURCE_LABELS.health}
          note="健康分与 Cookie/API 检查结果未知"
          onRetry={() => void fetchAll()}
        />
      )}
      {/* 会话状态卡 */}
      <Card
        title="会话状态"
        size="small"
        style={{ marginBottom: 12 }}
        extra={
          <Button
            size="small"
            loading={actionLoading}
            danger={session?.active === true}
            type={session?.active ? 'default' : 'primary'}
            onClick={() => handleToggleSession(!session?.active)}
          >
            {session?.active ? '停止会话' : '启动会话'}
          </Button>
        }
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: lightColor, display: 'inline-block' }} />
          <strong>{lightText}</strong>
        </div>
        <Space direction="vertical" size={4} style={{ fontSize: 13, color: '#666' }}>
          <div>策略：{session?.strategy || '-'}</div>
          <div>运行时长：{formatDuration(session?.uptime_sec, { compact: true })}</div>
          <div>Token 寿命：{formatDuration(session?.token_age_sec, { compact: true })}</div>
        </Space>
      </Card>

      {/* 健康报告卡 */}
      <Card title="健康报告" size="small" style={{ marginBottom: 12 }}>
        {failed.health && !health ? (
          // 取不到健康数据时不能把 null 当成三项检查全失败
          <div style={{ fontSize: 13, color: themeToken.colorTextDisabled }}>健康数据不可用</div>
        ) : (
          <>
            {healthScore !== null && (
              <div style={{ textAlign: 'center', marginBottom: 12 }}>
                <div style={{ fontSize: 36, fontWeight: 600, color: scoreColor, lineHeight: 1.2 }}>
                  {healthScore}
                </div>
                <Progress percent={healthScore} showInfo={false} strokeColor={scoreColor} />
              </div>
            )}
            <Space wrap size={8} style={{ marginBottom: 8 }}>
              <Tag color={health?.cookie_valid ? 'green' : 'red'}>
                Cookie {health?.cookie_valid ? '✓' : '✗'}
              </Tag>
              <Tag color={health?.api_reachable ? 'green' : 'red'}>
                API {health?.api_reachable ? '✓' : '✗'}
              </Tag>
              <Tag color={health?.page_accessible ? 'green' : 'red'}>
                页面 {health?.page_accessible ? '✓' : '✗'}
              </Tag>
              <Tag color="blue">WAF {health?.waf_status || '-'}</Tag>
            </Space>
          </>
        )}
        {/* needs_attention 时用 Alert 强提示，普通文本仅作建议展示 */}
        {health?.needs_attention && (
          <Alert
            type="warning"
            showIcon
            message={health.action || '需要关注'}
            style={{ marginTop: 8 }}
          />
        )}
        {!health?.needs_attention && health?.action && (
          <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>{health.action}</div>
        )}
      </Card>

      {/* Cookie 层状态卡 */}
      <Card title="Cookie 层状态" size="small">
        {session?.cookie_layers && Object.keys(session.cookie_layers).length > 0 ? (
          <Space wrap size={8}>
            {Object.entries(session.cookie_layers).map(([layer, valid]) => (
              <Tag key={layer} color={valid ? 'green' : 'red'}>
                {layer}: {valid ? '✓' : '✗'}
              </Tag>
            ))}
          </Space>
        ) : (
          <div style={{ fontSize: 13, color: themeToken.colorTextDisabled }}>
            {failed.session ? '会话数据不可用' : '暂无 Cookie 层数据'}
          </div>
        )}
      </Card>
    </PullToRefresh>
  )
}
