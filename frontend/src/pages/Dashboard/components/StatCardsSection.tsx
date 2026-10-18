import { Card, Col, Row, Statistic, Tooltip, theme } from 'antd'
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

  // 每张卡的曲线必须与卡面数字同口径：原先三张订单卡共用 sparklines.orders，
  // 同一条线挂三个指标下会误导趋势判断（评审 2.1-2）。tip 文案同时把口径写清，
  // 避免「运行中任务」卡的事件密度曲线被读成任务数趋势。
  const cards = [
    {
      key: 'tasks',
      icon: <ThunderboltOutlined className="stat-card-icon" style={{ color: token.colorPrimary }} />,
      title: '运行中任务',
      value: overview?.tasks?.running ?? 0,
      suffix: `/ ${overview?.tasks?.total ?? 0}`,
      color: token.colorPrimary,
      series: sparklines.events,
      tip: '曲线口径：近 24 小时事件密度（不是任务数趋势）',
      path: '/tasks',
    },
    {
      key: 'pending',
      icon: <ClockCircleOutlined className="stat-card-icon" style={{ color: token.colorWarning }} />,
      title: '待支付订单',
      value: overview?.orders?.pending ?? 0,
      color: token.colorWarning,
      series: sparklines.orders_pending,
      tip: '曲线口径：近 24 小时新建的待支付订单',
      path: '/orders',
    },
    {
      key: 'succeeded',
      icon: <CheckCircleOutlined className="stat-card-icon" style={{ color: token.colorSuccess }} />,
      title: '成功抢单',
      value: overview?.orders?.succeeded ?? 0,
      color: token.colorSuccess,
      series: sparklines.orders_succeeded,
      tip: '曲线口径：近 24 小时新建且最终成功的订单',
      path: '/orders',
    },
    {
      key: 'failed',
      icon: <CloseCircleOutlined className="stat-card-icon" style={{ color: token.colorError }} />,
      title: '抢单失败',
      value: overview?.orders?.failed ?? 0,
      color: token.colorError,
      series: sparklines.orders_failed,
      tip: '曲线口径：近 24 小时新建且失败的订单',
      path: '/orders',
    },
  ]

  return (
    <Row gutter={[16, 16]}>
      {cards.map(c => (
        <Col xs={12} sm={12} md={6} key={c.key}>
          <Card className="stat-card" hoverable onClick={() => onNavigate(c.path)}>
            {c.icon}
            <Statistic title={c.title} value={c.value} suffix={c.suffix} valueStyle={{ color: c.color }} />
            <div style={{ height: 40, marginTop: -8 }}>
              {/* Tooltip 包住整条曲线：口径只有 hover 才可见，避免卡片文字堆叠 */}
              <Tooltip title={c.tip}>
                <div style={{ height: 40 }}>
                  <ReactECharts option={sparklineOption(c.series, c.color)} style={{ height: 40 }} />
                </div>
              </Tooltip>
            </div>
          </Card>
        </Col>
      ))}
    </Row>
  )
}
