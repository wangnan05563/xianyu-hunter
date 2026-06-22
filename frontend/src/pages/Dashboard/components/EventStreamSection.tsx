import { Card, Col, Row, List, Tag, Empty, Button, Badge, Descriptions, Input, Space, Spin } from 'antd'
import {
  SettingOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  ScheduleOutlined,
  ShoppingOutlined,
  ShoppingCartOutlined,
  AuditOutlined,
  HeartOutlined,
  UserOutlined,
  SwapOutlined,
  ThunderboltOutlined,
  LoginOutlined,
} from '@ant-design/icons'
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import type { RecentEvent, StatsOverview } from '../../../api'
import { authApi } from '../../../api'
import type { AuthMe } from '../../../api/types'
import { EVENT_COLOR } from '../../../constants/eventTypes'
import { evTypeLabel, evMsg } from '../utils'

interface EventStreamSectionProps {
  events: RecentEvent[]
  streamStatus: string
  overview: StatsOverview | null
  onNavigate: (path: string) => void
}

export default function EventStreamSection({ events, streamStatus, overview, onNavigate }: EventStreamSectionProps) {
  const navigate = useNavigate()

  // 登录账户状态
  const [auth, setAuth] = useState<AuthMe | null>(null)
  const [authLoading, setAuthLoading] = useState(true)

  // Token 快速更换状态
  const [tokenExpanded, setTokenExpanded] = useState(false)
  const [tokenValue, setTokenValue] = useState('')
  const [tokenUpdating, setTokenUpdating] = useState(false)
  const [tokenRefreshing, setTokenRefreshing] = useState(false)
  const [tokenResult, setTokenResult] = useState<{ text: string; error: boolean } | null>(null)

  // 加载登录态
  useEffect(() => {
    authApi.getMe().then(setAuth).catch(() => setAuth(null)).finally(() => setAuthLoading(false))
  }, [])

  // 快速刷新 _m_h5_tk（从浏览器读取）
  const handleQuickRefreshM5tk = useCallback(async () => {
    setTokenRefreshing(true)
    setTokenResult(null)
    try {
      const r = await fetch('/api/auth/cookie/fetch-keys?keys=_m_h5_tk', { credentials: 'include' })
      const data = await r.json()
      if (data.ok && data.cookies?._m_h5_tk) {
        setTokenValue(data.cookies._m_h5_tk)
        setTokenResult({ text: `已获取（来源: ${data.source}）`, error: false })
      } else {
        setTokenResult({ text: data.hint || '未找到', error: true })
      }
    } catch {
      setTokenResult({ text: '请求失败', error: true })
    } finally {
      setTokenRefreshing(false)
    }
  }, [])

  // 展开 Token 面板时自动拉取一次
  useEffect(() => {
    if (tokenExpanded) handleQuickRefreshM5tk()
  }, [tokenExpanded, handleQuickRefreshM5tk])

  // 注入单个 token
  const handleInjectToken = async () => {
    if (!tokenValue.trim()) return
    setTokenUpdating(true)
    setTokenResult(null)
    try {
      const result = await authApi.injectCookie(`_m_h5_tk=${tokenValue.trim()}`)
      if (result.ok) {
        setTokenResult({ text: 'Token 更新成功', error: false })
        // 刷新登录态
        authApi.getMe().then(setAuth).catch(() => {})
        setTimeout(() => setTokenExpanded(false), 1500)
      } else {
        setTokenResult({ text: result.error || '更新失败', error: true })
      }
    } catch {
      setTokenResult({ text: '请求失败', error: true })
    } finally {
      setTokenUpdating(false)
    }
  }

  // 截断显示的 token 值
  const displayToken = (val: string) => val.length > 20 ? val.slice(0, 20) + '…' : val

  return (
    <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
      <Col xs={24} lg={15}>
        <Card title={<span>事件流 <Badge count={events.length} style={{ marginLeft: 6, backgroundColor: '#1677ff' }} /></span>}
          extra={
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: streamStatus.includes('已连接') ? '#52c41a' : 'var(--xh-text-tertiary)' }}>{streamStatus}</span>
              <Button size="small" onClick={() => onNavigate('/timeline')}>查看全部</Button>
            </span>
          }>
          {events.length === 0 ? (
            <Empty description="暂无事件" />
          ) : (
            <List size="small" dataSource={events.slice(0, 50)}
              style={{ maxHeight: 360, overflow: 'auto' }}
              renderItem={(e) => (
                <List.Item style={{ padding: '4px 0' }}>
                  <List.Item.Meta
                    avatar={<Tag color={EVENT_COLOR[e.type] || 'default'} style={{ fontSize: 10 }}>{evTypeLabel(e.type)}</Tag>}
                    title={<span style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>{new Date(e.created_at).toLocaleString('zh-CN')}</span>}
                    description={<span style={{ fontSize: 12 }}>{evMsg(e)}</span>}
                  />
                </List.Item>
              )}
            />
          )}
        </Card>
      </Col>

      {/* 系统状态 */}
      <Col xs={24} lg={9}>
        <Card title={<span><SettingOutlined /> 系统状态</span>}
          extra={<span style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>{overview?.ts || ''}</span>}>

          {/* 登录账户 — 参考旧版 dashboard 设计 */}
          <div style={{
            background: 'var(--xh-bg-spotlight)', borderRadius: 6, padding: '10px 12px',
            marginBottom: 12, border: '1px solid var(--xh-border)',
          }}>
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginBottom: 6 }}>登录账户</div>
            {authLoading ? (
              <Spin size="small" />
            ) : auth?.logged_in ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <UserOutlined style={{ color: '#FF6200', fontSize: 18 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>
                      {auth.nick || (`用户 ${(auth.user_id || '').slice(0, 6)}`)}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', fontFamily: 'monospace' }}>
                      {(auth.user_id || '').slice(0, 12)}
                    </div>
                  </div>
                  {/* 换号 + Token 按钮 */}
                  <Space size={4}>
                    <Button size="small" onClick={() => navigate('/login')}>换号</Button>
                    {!tokenExpanded ? (
                      <Button
                        size="small"
                        icon={<ThunderboltOutlined />}
                        onClick={() => setTokenExpanded(true)}
                        style={{ fontSize: 10, color: '#e65100', borderColor: '#ffc107' }}
                      >
                        Token
                      </Button>
                    ) : (
                      <Button
                        size="small"
                        onClick={() => setTokenExpanded(false)}
                      >
                        收起
                      </Button>
                    )}
                  </Space>
                </div>

                {/* Token 快速更换面板（展开后内联显示） */}
                {tokenExpanded && (
                  <div style={{
                    marginTop: 8, padding: '8px 10px',
                    background: 'rgba(245, 124, 0, 0.08)', border: '1px solid rgba(245, 124, 0, 0.3)', borderRadius: 6,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: '#f57c00', fontSize: 11 }}>
                        <ThunderboltOutlined /> 更新 _m_h5_tk
                      </span>
                      <Space size={4}>
                        <Button size="small" type="link" loading={tokenRefreshing} onClick={handleQuickRefreshM5tk}
                          style={{ fontSize: 10, padding: '0 4px' }}>
                          从浏览器自动获取
                        </Button>
                      </Space>
                    </div>
                    <Space.Compact style={{ width: '100%' }}>
                      <Input
                        size="small"
                        placeholder="粘贴新的 _m_h5_tk 值"
                        value={tokenValue}
                        onChange={(e) => setTokenValue(e.target.value)}
                        style={{ fontFamily: 'monospace', fontSize: 11 }}
                        onPressEnter={handleInjectToken}
                      />
                      <Button
                        size="small"
                        type="primary"
                        loading={tokenUpdating}
                        onClick={handleInjectToken}
                        disabled={!tokenValue.trim()}
                        style={{ background: '#FF6200', borderColor: '#FF6200', fontSize: 11 }}
                      >
                        更新
                      </Button>
                    </Space.Compact>
                    {tokenResult && (
                      <div style={{ fontSize: 10, marginTop: 4, color: tokenResult.error ? '#ff4d4f' : '#52c41a' }}>
                        {tokenResult.text}
                      </div>
                    )}
                    {tokenValue && !tokenResult && (
                      <div style={{ fontSize: 10, color: 'var(--xh-text-tertiary)', marginTop: 2 }}>
                        当前值: {displayToken(tokenValue)}
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--xh-text-tertiary)' }}>未登录</span>
                <Button size="small" type="primary" icon={<LoginOutlined />} onClick={() => navigate('/login')}
                  style={{ background: '#FF6200', borderColor: '#FF6200' }}>
                  前往登录
                </Button>
              </div>
            )}
          </div>

          <Descriptions size="small" column={1} colon={false} labelStyle={{ width: 80, color: 'var(--xh-text-tertiary)' }} contentStyle={{ fontSize: 12 }}>
            <Descriptions.Item label={<><DatabaseOutlined /> 数据库</>}>
              {overview?.db_size || '—'}
            </Descriptions.Item>
            <Descriptions.Item label={<><ScheduleOutlined /> 调度器</>}>
              <Tag color={overview?.scheduler_running ? 'green' : 'default'}>{overview?.scheduler_running ? '运行中' : '未启动'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={<><CloudServerOutlined /> 浏览器</>}>
              <span style={{ fontSize: 10, fontFamily: 'monospace', wordBreak: 'break-all' }}>{overview?.browser_dir || '—'}</span>
            </Descriptions.Item>
            <Descriptions.Item label={<><ShoppingOutlined /> 任务</>}>
              {overview?.tasks?.total ?? 0}（{overview?.tasks?.running ?? 0} 运行中）
            </Descriptions.Item>
            <Descriptions.Item label={<><ShoppingCartOutlined /> 订单</>}>
              {overview?.orders?.total ?? 0}（{overview?.orders?.succeeded ?? 0} 成功 / {overview?.orders?.pending ?? 0} 待处理）
            </Descriptions.Item>
            <Descriptions.Item label={<><AuditOutlined /> 评估</>}>
              {overview?.evaluation_count ?? 0} 条记录
            </Descriptions.Item>
            <Descriptions.Item label={<><HeartOutlined /> 心跳</>}>
              {overview?.ts ? new Date(overview.ts).toLocaleString('zh-CN') : '—'}
            </Descriptions.Item>
          </Descriptions>
          <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Button size="small" onClick={() => onNavigate('/tasks')}>任务管理</Button>
            <Button size="small" onClick={() => onNavigate('/config/ai')}>配置</Button>
            <Button size="small" onClick={() => onNavigate('/logs')}>实时日志</Button>
            <Button size="small" onClick={() => onNavigate('/orders')}>抢单记录</Button>
          </div>
        </Card>
      </Col>
    </Row>
  )
}
