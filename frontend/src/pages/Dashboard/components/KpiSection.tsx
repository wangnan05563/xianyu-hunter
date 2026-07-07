import { Card, Col, Row, Statistic, Tag, Tooltip, theme } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  RiseOutlined,
  MinusOutlined,
} from '@ant-design/icons'
import type { ReactNode } from 'react'
import type { KpiCard } from '../../../api'
import { kpiStar, kpiStarTip, fmtKpiValue, deltaText } from '../utils'

interface KpiSectionProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly kpiCards: KpiCard[]
}

// S3776/S3358：提取趋势视觉计算到独立函数，降低 KpiSection map 回调的认知复杂度
// 为什么单独提取：原 map 回调内 trendPrefix 的 if + deltaTagColor 的嵌套三元贡献了约 8 复杂度，
// 提取后主回调 CC 从 16 降至 ~8，且嵌套三元被 if/else 替代
function computeKpiTrend(
  k: KpiCard,
  token: { colorError: string; colorSuccess: string },
): {
  trendPrefix: ReactNode
  deltaTagColor: string
  hasDelta: boolean
} {
  const delta = k.delta_pct
  const deltaUp = (delta ?? 0) >= 0
  const hasDelta = delta != null
  // 反向指标（失败率）方向取反：上升为坏，下降为好
  const isInverted = k.id === 'notify_failure_rate'
  const upColor = isInverted ? token.colorError : token.colorSuccess
  const downColor = isInverted ? token.colorSuccess : token.colorError
  let trendPrefix: ReactNode = <MinusOutlined style={{ color: 'var(--xh-text-tertiary)' }} />
  if (hasDelta) {
    trendPrefix = deltaUp
      ? <ArrowUpOutlined style={{ color: upColor }} />
      : <ArrowDownOutlined style={{ color: downColor }} />
  }
  // S3358：嵌套三元拆分为 if/else，避免 isInverted ? (deltaUp ? ... : ...) : (deltaUp ? ... : ...)
  // 反向指标上涨=坏（红），正向指标上涨=好（绿）
  let deltaTagColor: string
  if (isInverted) {
    deltaTagColor = deltaUp ? 'red' : 'green'
  } else {
    deltaTagColor = deltaUp ? 'green' : 'red'
  }
  return { trendPrefix, deltaTagColor, hasDelta }
}

export default function KpiSection({ kpiCards }: KpiSectionProps) {
  // 从 antd token 读取主题色，自动响应主题切换
  const { token } = theme.useToken()

  // 无 KPI 数据时不渲染整块卡片，避免空容器占用布局
  if (kpiCards.length === 0) return null

  return (
    <Card style={{ marginTop: 16 }} title={<span><RiseOutlined /> 业务 KPI（近 30 天）</span>}
      extra={<span style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>基于 {kpiCards[0]?.sample_size || 0} 条 · {kpiCards[0]?.range_days || 30} 天</span>}>
      <Row gutter={[16, 16]}>
        {kpiCards.map((k) => {
          const stars = kpiStar(k)
          const isInverted = k.id === 'notify_failure_rate'
          // KPI 满分高亮色：浅色主题用 #faad14，深色主题用 #FFD666 提亮
          const starColor = token.colorWarning
          const { trendPrefix, deltaTagColor, hasDelta } = computeKpiTrend(k, token)
          return (
            <Col xs={12} md={6} key={k.id}>
              <div style={{ borderLeft: stars === 5 ? `3px solid ${starColor}` : '3px solid transparent', paddingLeft: 8 }}>
                <Statistic
                  title={k.title}
                  value={isInverted ? k.value : fmtKpiValue(k)}
                  suffix={isInverted ? '%' : k.unit}
                  precision={k.is_pct && k.value !== 0 && k.value !== 100 ? 1 : 0}
                  valueStyle={stars === 5 ? { color: starColor } : undefined}
                  prefix={trendPrefix}
                />
                <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {hasDelta && (
                    <Tag color={deltaTagColor} style={{ fontSize: 11 }}>
                      {deltaText(k)}
                    </Tag>
                  )}
                  {/* 米其林 5 星评级 */}
                  <Tooltip title={kpiStarTip(k)}>
                    <span style={{ color: starColor, fontSize: 12, letterSpacing: 1 }}>
                      {'★'.repeat(stars)}{'☆'.repeat(5 - stars)}
                    </span>
                  </Tooltip>
                </div>
                <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', marginTop: 2 }}>{k.hint}</div>
              </div>
            </Col>
          )
        })}
      </Row>
    </Card>
  )
}
