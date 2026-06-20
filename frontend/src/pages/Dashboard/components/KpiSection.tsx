import { Card, Col, Row, Statistic, Tag, Tooltip } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  RiseOutlined,
  MinusOutlined,
} from '@ant-design/icons'
import type { KpiCard } from '../../../api'
import { kpiStar, kpiStarTip, fmtKpiValue, deltaText } from '../utils'

interface KpiSectionProps {
  kpiCards: KpiCard[]
}

export default function KpiSection({ kpiCards }: KpiSectionProps) {
  // 无 KPI 数据时不渲染整块卡片，避免空容器占用布局
  if (kpiCards.length === 0) return null

  return (
    <Card style={{ marginTop: 16 }} title={<span><RiseOutlined /> 业务 KPI（近 30 天）</span>}
      extra={<span style={{ fontSize: 11, color: '#8c8c8c' }}>基于 {kpiCards[0]?.sample_size || 0} 条 · {kpiCards[0]?.range_days || 30} 天</span>}>
      <Row gutter={[16, 16]}>
        {kpiCards.map((k) => {
          const delta = k.delta_pct
          const deltaUp = (delta ?? 0) >= 0
          const hasDelta = delta != null
          const stars = kpiStar(k)
          // 反向指标（失败率）方向取反：上升为坏，下降为好
          const isInverted = k.id === 'notify_failure_rate'
          return (
            <Col xs={12} md={6} key={k.id}>
              <div style={{ borderLeft: stars === 5 ? '3px solid #faad14' : '3px solid transparent', paddingLeft: 8 }}>
                <Statistic
                  title={k.title}
                  value={isInverted ? k.value : fmtKpiValue(k)}
                  suffix={isInverted ? '%' : k.unit}
                  precision={k.is_pct && k.value !== 0 && k.value !== 100 ? 1 : 0}
                  valueStyle={stars === 5 ? { color: '#faad14' } : undefined}
                  prefix={hasDelta ? (deltaUp ? <ArrowUpOutlined style={{ color: isInverted ? '#ff4d4f' : '#52c41a' }} /> : <ArrowDownOutlined style={{ color: isInverted ? '#52c41a' : '#ff4d4f' }} />) : <MinusOutlined style={{ color: '#8c8c8c' }} />}
                />
                <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {hasDelta && (
                    <Tag color={isInverted ? (deltaUp ? 'red' : 'green') : (deltaUp ? 'green' : 'red')} style={{ fontSize: 11 }}>
                      {deltaText(k)}
                    </Tag>
                  )}
                  {/* 米其林 5 星评级 */}
                  <Tooltip title={kpiStarTip(k)}>
                    <span style={{ color: '#faad14', fontSize: 12, letterSpacing: 1 }}>
                      {'★'.repeat(stars)}{'☆'.repeat(5 - stars)}
                    </span>
                  </Tooltip>
                </div>
                <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>{k.hint}</div>
              </div>
            </Col>
          )
        })}
      </Row>
    </Card>
  )
}
