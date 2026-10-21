import { Card, Col, Row, List, Spin, Badge, Collapse, theme } from 'antd'
import { WarningOutlined, ReloadOutlined } from '@ant-design/icons'
import { TipButton } from '@/components/TipButton'
import { openSheetWithNotification } from '@/components/SheetWorkspace/sheetNotifications'
import FetchFailedHint from '@/components/FetchFailedHint'
import type { TodayAlert } from '../../../api'

interface AlertRadarProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly alertData: TodayAlert | null
  readonly alertOpen: boolean
  readonly onToggle: () => void
  readonly onReload: () => void
  readonly loadError?: boolean
}

export default function AlertRadar({ alertData, alertOpen, onToggle, onReload, loadError }: AlertRadarProps) {
  // 从 antd token 读取主题色，自动响应主题切换
  const { token } = theme.useToken()

  // 接口失败时不能用 ?? 0 写成「今日 0 单 / 0 事件」，也不能用绿点 Badge 表示「无异常」
  const alertCount = (alertData?.alerts?.counts?.failed ?? 0)
    + (alertData?.alerts?.counts?.timeout ?? 0)
    + (alertData?.alerts?.counts?.low_eval ?? 0)

  return (
    <Card style={{ marginTop: 16 }}
      title={
        // S6848/S1082：可点击区域用原生 button 替代 span+onClick，自带键盘可达性
        <button
          type="button"
          onClick={() => { onToggle(); if (!alertOpen) onReload() }}
          style={{ cursor: 'pointer', border: 'none', background: 'none', padding: 0, font: 'inherit', color: 'inherit', display: 'inline-flex', alignItems: 'center' }}
        >
          <WarningOutlined style={{ color: token.colorWarning, marginRight: 6 }} />
          异常雷达
          <Badge
            count={loadError ? '?' : alertCount}
            size="small"
            style={{ marginLeft: 8, backgroundColor: loadError ? token.colorTextTertiary : (alertData?.alerts?.counts?.failed ?? 0) > 0 ? token.colorError : token.colorWarning }}
          />
        </button>
      }
      extra={
        <span style={{ fontSize: 11, color: loadError ? token.colorError : 'var(--xh-text-tertiary)' }}>
          {loadError
            ? '预警接口失败，数字不代表今日真实状态'
            : `今日 ${alertData?.today?.orders ?? 0} 单 / ${alertData?.today?.events ?? 0} 事件`}
          <TipButton type="text" size="small" icon={<ReloadOutlined />} onClick={onReload} style={{ marginLeft: 4 }} tip="重新拉取最新预警数据" />
        </span>
      }>
      <Collapse activeKey={alertOpen ? ['alert'] : []} onChange={onToggle} bordered={false}
        items={[{
          key: 'alert', showArrow: false, style: { border: 'none' },
          label: null as unknown as string,
          children: alertData ? (
            <Row gutter={[16, 16]}>
              {/* 失败订单 */}
              <Col xs={24} md={8}>
                <Card size="small" title={<span><Badge status="error" /> 抢单失败 ({alertData.alerts.counts.failed})</span>}
                  style={{ borderLeft: `3px solid ${token.colorError}` }}>
                  {alertData.alerts.failed_orders.length === 0 ? (
                    <div style={{ color: token.colorSuccess, fontSize: 12 }}>无失败订单 ✓</div>
                  ) : (
                    <List size="small" dataSource={alertData.alerts.failed_orders.slice(0, 5)}
                      renderItem={o => (
                        <List.Item style={{ padding: '4px 0' }}>
                          {/* 原为裸 <a href="/orders?ref=...">：整页刷新丢 sheet 状态，且 basename=/xianyu 下 404（评审 2.1-4） */}
                          <TipButton type="link" size="small"
                            style={{ fontSize: 12, padding: 0, height: 'auto', color: token.colorError }}
                            onClick={() => openSheetWithNotification(`/orders?ref=${o.id}`)}
                            tip={`在「抢单记录」中定位订单 #${o.id}`}>
                            订单 #{o.id} 商品 {o.item_id} · ¥{o.price}
                          </TipButton>
                        </List.Item>
                      )} />
                  )}
                </Card>
              </Col>
              {/* 超时待支付 */}
              <Col xs={24} md={8}>
                <Card size="small" title={<span><Badge status="warning" /> 待支付超时 ({alertData.alerts.counts.timeout})</span>}
                  style={{ borderLeft: `3px solid ${token.colorWarning}` }}>
                  {alertData.alerts.timeout_pending.length === 0 ? (
                    <div style={{ color: token.colorSuccess, fontSize: 12 }}>无超时订单 ✓</div>
                  ) : (
                    <List size="small" dataSource={alertData.alerts.timeout_pending.slice(0, 5)}
                      renderItem={o => (
                        <List.Item style={{ padding: '4px 0' }}>
                          <TipButton type="link" size="small"
                            style={{ fontSize: 12, padding: 0, height: 'auto' }}
                            onClick={() => openSheetWithNotification(`/orders?ref=${o.id}`)}
                            tip={`在「抢单记录」中定位订单 #${o.id}`}>
                            订单 #{o.id} 商品 {o.item_id} · ¥{o.price} · {Math.floor((o.age_sec || 0) / 60)} 分钟前
                          </TipButton>
                        </List.Item>
                      )} />
                  )}
                </Card>
              </Col>
              {/* 评估低分 */}
              <Col xs={24} md={8}>
                <Card size="small" title={<span><Badge status="warning" /> 评估异常 score&lt;0.5 ({alertData.alerts.counts.low_eval})</span>}
                  style={{ borderLeft: `3px solid ${token.colorWarning}` }}>
                  {alertData.alerts.low_evaluations.length === 0 ? (
                    <div style={{ color: token.colorSuccess, fontSize: 12 }}>无低分评估 ✓</div>
                  ) : (
                    <List size="small" dataSource={alertData.alerts.low_evaluations.slice(0, 5)}
                      renderItem={e => (
                        <List.Item style={{ padding: '4px 0' }}>
                          <span style={{ fontSize: 12 }}>
                            {e.message || e.type} · score {e.score_value ?? '—'} · {(e.created_at || '').slice(5, 16)}
                          </span>
                        </List.Item>
                      )} />
                  )}
                </Card>
              </Col>
            </Row>
          ) : loadError ? (
            <FetchFailedHint source="异常雷达" onRetry={onReload} />
          ) : <Spin />,
        }]} />
    </Card>
  )
}
