// frontend/src/mobile/pages/AntiCrawl/index.tsx
import { Card, Tag, Spin, App, Button, Progress, Alert, Space, theme } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { anticrawlApi } from '../../../api'
import type { SessionStatus, HealthReport } from '../../../api/anticrawl'
import { extractApiError } from '../../../utils/apiError'
import PullToRefresh from '../../components/PullToRefresh'

// 秒数格式化为 "Xh Ym" / "Ym Zs"：避免引入 dayjs duration 增大 bundle
const formatDuration = (sec: number | null | undefined): string => {
  if (sec === null || sec === undefined || sec < 0) return '-'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export default function MobileAntiCrawl() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [session, setSession] = useState<SessionStatus | null>(null)
  const [health, setHealth] = useState<HealthReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  const fetchAll = useCallback(async () => {
    try {
      // 并发拉取会话状态与健康报告，减少串行延迟
      const [s, h] = await Promise.all([
        anticrawlApi.getSessionStatus(),
        anticrawlApi.checkHealth(),
      ])
      setSession(s)
      setHealth(h)
    } catch (e) {
      // 弱网保留已有数据
      message.error(extractApiError(e, '加载反爬状态失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

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
  let lightColor = themeToken.colorError // 默认红色：inactive
  let lightText = '未激活'
  if (session?.active) {
    lightColor = themeToken.colorSuccess
    lightText = '运行中'
  } else if (session?.token_expired) {
    lightColor = themeToken.colorWarning
    lightText = 'Token 失效'
  }

  // 健康分颜色档位：绿/橙/红，给用户直观等级感
  const healthScore = health?.score ?? session?.health_score ?? null
  const scoreColor = healthScore === null ? themeToken.colorTextDisabled : healthScore >= 80 ? themeToken.colorSuccess : healthScore >= 50 ? themeToken.colorWarning : themeToken.colorError

  return (
    <PullToRefresh onRefresh={fetchAll}>
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
          <div>运行时长：{formatDuration(session?.uptime_sec)}</div>
          <div>Token 寿命：{formatDuration(session?.token_age_sec)}</div>
        </Space>
      </Card>

      {/* 健康报告卡 */}
      <Card title="健康报告" size="small" style={{ marginBottom: 12 }}>
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
          <div style={{ fontSize: 13, color: themeToken.colorTextDisabled }}>暂无 Cookie 层数据</div>
        )}
      </Card>
    </PullToRefresh>
  )
}
