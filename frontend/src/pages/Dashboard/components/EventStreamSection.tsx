import { Card, Col, Row, List, Tag, Empty, Badge, Descriptions, theme } from 'antd'
import {
  SettingOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  ScheduleOutlined,
  ShoppingOutlined,
  ShoppingCartOutlined,
  AuditOutlined,
  HeartOutlined,
} from '@ant-design/icons'
import type { RecentEvent, StatsOverview } from '../../../api'
import { EVENT_COLOR } from '../../../constants/eventTypes'
import { evTypeLabel, evMsg } from '../utils'
import { TipButton } from '@/components/TipButton'

interface EventStreamSectionProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly events: RecentEvent[]
  readonly streamStatus: string
  readonly overview: StatsOverview | null
  readonly onNavigate: (path: string) => void
}

export default function EventStreamSection({ events, streamStatus, overview, onNavigate }: EventStreamSectionProps) {
  // 从 antd token 读取主题色，自动响应主题切换
  const { token } = theme.useToken()

  return (
    <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
      <Col xs={24} lg={15}>
        <Card title={<span>事件流 <Badge count={events.length} style={{ marginLeft: 6, backgroundColor: token.colorInfo }} /></span>}
          extra={
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: streamStatus.includes('已连接') ? token.colorSuccess : 'var(--xh-text-tertiary)' }}>{streamStatus}</span>
              <TipButton size="small" onClick={() => onNavigate('/timeline')} tip="跳转事件时间线查看全部事件">查看全部</TipButton>
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
            <TipButton size="small" onClick={() => onNavigate('/tasks')} tip="进入任务管理页面">任务管理</TipButton>
            <TipButton size="small" onClick={() => onNavigate('/config/ai')} tip="进入 AI 配置页面">配置</TipButton>
            <TipButton size="small" onClick={() => onNavigate('/logs')} tip="进入实时日志页面">实时日志</TipButton>
            <TipButton size="small" onClick={() => onNavigate('/orders')} tip="进入抢单记录页面">抢单记录</TipButton>
          </div>
        </Card>
      </Col>
    </Row>
  )
}
