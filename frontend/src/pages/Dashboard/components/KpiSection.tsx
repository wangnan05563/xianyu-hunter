import { Card, Col, Row, Statistic, Tag, Tooltip, theme } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  RiseOutlined,
  MinusOutlined,
} from '@ant-design/icons'
import type { KpiCard } from '../../../api'
import { kpiStar, kpiStarTip, fmtKpiValue, deltaText } from '../utils'

interface KpiSectionProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly kpiCards: KpiCard[]
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
          const delta = k.delta_pct
          const deltaUp = (delta ?? 0) >= 0
          const hasDelta = delta != null
          const stars = kpiStar(k)
          // 反向指标（失败率）方向取反：上升为坏，下降为好
          const isInverted = k.id === 'notify_failure_rate'
          // KPI 满分高亮色：浅色主题用 #faad14，深色主题用 #FFD666 提亮
          const starColor = token.colorWarning
          // 上升/下降箭头色：使用 token 中的语义色
          const upColor = isInverted ? token.colorError : token.colorSuccess
          const downColor = isInverted ? token.colorSuccess : token.colorError
          // S6478：把趋势箭头和 Tag 颜色计算从 JSX 内联 IIFE 提取到外部变量，
          // 避免 SonarQube 误判为「父组件内定义子组件」
          let trendPrefix = <MinusOutlined style={{ color: 'var(--xh-text-tertiary)' }} />
          if (hasDelta) {
            trendPrefix = deltaUp
              ? <ArrowUpOutlined style={{ color: upColor }} />
              : <ArrowDownOutlined style={{ color: downColor }} />
          }
          // 反向指标上涨=坏（红），正向指标上涨=好（绿）
          const deltaTagColor = isInverted
            ? (deltaUp ? 'red' : 'green')
            : (deltaUp ? 'green' : 'red')
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
