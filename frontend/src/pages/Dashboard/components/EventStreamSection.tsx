import { Card, Col, Row, List, Tag, Empty, Button, Badge, Descriptions } from 'antd'
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

interface EventStreamSectionProps {
  events: RecentEvent[]
  streamStatus: string
  overview: StatsOverview | null
  onNavigate: (path: string) => void
}

export default function EventStreamSection({ events, streamStatus, overview, onNavigate }: EventStreamSectionProps) {
  return (
    <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
      <Col xs={24} lg={15}>
        <Card title={<span>事件流 <Badge count={events.length} style={{ marginLeft: 6, backgroundColor: '#1677ff' }} /></span>}
          extra={
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: streamStatus.includes('已连接') ? '#52c41a' : '#8c8c8c' }}>{streamStatus}</span>
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
                    title={<span style={{ fontSize: 11, color: '#8c8c8c' }}>{new Date(e.created_at).toLocaleString('zh-CN')}</span>}
                    description={<span style={{ fontSize: 12 }}>{evMsg(e)}</span>}
                  />
                </List.Item>
              )} />
          )}
        </Card>
      </Col>

      {/* 系统状态 */}
      <Col xs={24} lg={9}>
        <Card title={<span><SettingOutlined /> 系统状态</span>}
          extra={<span style={{ fontSize: 11, color: '#8c8c8c' }}>{overview?.ts || ''}</span>}>
          <Descriptions size="small" column={1} colon={false} labelStyle={{ width: 80, color: '#8c8c8c' }} contentStyle={{ fontSize: 12 }}>
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
