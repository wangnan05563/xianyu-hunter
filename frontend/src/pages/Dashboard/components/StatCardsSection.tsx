import { Card, Col, Row, Statistic, theme } from 'antd'
import {
  ThunderboltOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import ReactECharts from '../../../components/charts/EChart'
import type { StatsOverview, TrendSeries } from '../../../api'

interface StatCardsSectionProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly overview: StatsOverview | null
  readonly sparklines: Record<string, TrendSeries | null>
  readonly onNavigate: (path: string) => void
}

// Sparkline 小图配置（无坐标轴，纯折线 + 渐变填充）
// 内联在此组件内，因仅本组件使用，避免污染全局
function sparklineOption(series: TrendSeries | null, color: string) {
  if (!series?.series?.length) return {}
  const data = series.series.map(s => s.value)
  return {
    grid: { top: 0, right: 0, bottom: 0, left: 0 },
    xAxis: { type: 'category', show: false, data: series.series.map(() => '') },
    yAxis: { type: 'value', show: false, min: Math.min(...data) * 0.9 },
    series: [{
      type: 'line', data, smooth: true, symbol: 'none',
      lineStyle: { color, width: 1.5 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [{ offset: 0, color: color + '40' }, { offset: 1, color: color + '05' }] } },
    }],
  }
}

export default function StatCardsSection({ overview, sparklines, onNavigate }: StatCardsSectionProps) {
  // 从 antd token 读取主题色，自动响应浅色/暗色主题切换
  const { token } = theme.useToken()

  return (
    <Row gutter={[16, 16]}>
      <Col xs={12} sm={12} md={6}>
        <Card className="stat-card" hoverable onClick={() => onNavigate('/tasks')}>
          <ThunderboltOutlined className="stat-card-icon" style={{ color: token.colorPrimary }} />
          <Statistic
            title="运行中任务"
            value={overview?.tasks?.running ?? 0}
            suffix={`/ ${overview?.tasks?.total ?? 0}`}
            valueStyle={{ color: token.colorPrimary }}
          />
          <div style={{ height: 40, marginTop: -8 }}>
            <ReactECharts option={sparklineOption(sparklines.tasks, token.colorPrimary)} style={{ height: 40 }} />
          </div>
        </Card>
      </Col>
      <Col xs={12} sm={12} md={6}>
        <Card className="stat-card" hoverable onClick={() => onNavigate('/orders')}>
          <ClockCircleOutlined className="stat-card-icon" style={{ color: token.colorWarning }} />
          <Statistic
            title="待支付订单"
            value={overview?.orders?.pending ?? 0}
            valueStyle={{ color: token.colorWarning }}
          />
          <div style={{ height: 40, marginTop: -8 }}>
            <ReactECharts option={sparklineOption(sparklines.orders, token.colorWarning)} style={{ height: 40 }} />
          </div>
        </Card>
      </Col>
      <Col xs={12} sm={12} md={6}>
        <Card className="stat-card" hoverable onClick={() => onNavigate('/orders')}>
          <CheckCircleOutlined className="stat-card-icon" style={{ color: token.colorSuccess }} />
          <Statistic
            title="成功抢单"
            value={overview?.orders?.succeeded ?? 0}
            valueStyle={{ color: token.colorSuccess }}
          />
          <div style={{ height: 40, marginTop: -8 }}>
            <ReactECharts option={sparklineOption(sparklines.orders, token.colorSuccess)} style={{ height: 40 }} />
          </div>
        </Card>
      </Col>
      <Col xs={12} sm={12} md={6}>
        <Card className="stat-card" hoverable onClick={() => onNavigate('/orders')}>
          <CloseCircleOutlined className="stat-card-icon" style={{ color: token.colorError }} />
          <Statistic
            title="抢单失败"
            value={overview?.orders?.failed ?? 0}
            valueStyle={{ color: token.colorError }}
          />
          <div style={{ height: 40, marginTop: -8 }}>
            <ReactECharts option={sparklineOption(sparklines.orders, token.colorError)} style={{ height: 40 }} />
          </div>
        </Card>
      </Col>
    </Row>
  )
}
