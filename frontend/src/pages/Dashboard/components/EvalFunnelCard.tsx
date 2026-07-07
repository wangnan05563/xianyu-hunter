import { useMemo } from 'react'
import { Card, Segmented, Empty, Spin, Statistic, Row, Col, Tooltip, theme } from 'antd'
import { AimOutlined, CheckCircleOutlined, ThunderboltOutlined, FallOutlined } from '@ant-design/icons'
import ReactECharts from '../../../components/charts/EChart'
import type { EvalFunnelData } from '../../../api'

interface EvalFunnelCardProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly data: EvalFunnelData | null
  readonly loading: boolean
  readonly rangeDays: number
  readonly onRangeChange: (days: number) => void
}

export default function EvalFunnelCard({ data, loading, rangeDays, onRangeChange }: EvalFunnelCardProps) {
  const { token } = theme.useToken()

  // ECharts 漏斗图配置
  // 用 sort='descending' 让数据大→小自上而下排列，符合漏斗视觉直觉
  const funnelOption = useMemo(() => {
    if (!data?.stages?.length) return null
    return {
      tooltip: {
        trigger: 'item',
        // formatter 同时展示绝对值、相对首阶段、相对上阶段，便于诊断流失
        formatter: (p: { name: string; value: number; data: { pctOfFirst: number; pctOfPrev: number } }) =>
          `${p.name}<br/>数量: <b>${p.value}</b><br/>占采集: ${p.data.pctOfFirst}%<br/>占上一阶段: ${p.data.pctOfPrev}%`,
        backgroundColor: token.colorBgElevated,
        borderColor: token.colorBorderSecondary,
        textStyle: { color: token.colorText },
      },
      series: [{
        type: 'funnel',
        sort: 'descending',
        gap: 2,
        // 颜色梯度：从采集到成功，色相由冷到暖，暗示转化进度
        color: [token.colorPrimary, token.colorInfo, token.colorSuccess, token.colorWarning, token.colorError],
        label: {
          show: true,
          position: 'inside',
          formatter: '{b}: {c}',
          color: '#fff',
          fontWeight: 600,
        },
        data: data.stages.map(s => ({
          name: s.label,
          value: s.count,
          // 自定义字段供 tooltip 使用
          pctOfFirst: s.pct_of_first,
          pctOfPrev: s.pct_of_prev,
        })),
      }],
    }
  }, [data, token])

  return (
    <Card
      title="评估漏斗与命中率"
      style={{ marginTop: 16 }}
      extra={
        <Segmented
          size="small"
          value={rangeDays}
          // S4325: 用 Number() 转换替代 as 断言，避免 SonarQube 报告冗余断言
          onChange={(v) => onRangeChange(Number(v))}
          options={[
            { label: '7天', value: 7 },
            { label: '30天', value: 30 },
            { label: '90天', value: 90 },
          ]}
        />
      }
    >
      <Spin spinning={loading}>
        {data && data.stages.length > 0 ? (
          <>
            {/* 漏斗图：占满宽度，高度固定避免阶段少时压扁 */}
            <div style={{ height: 320 }}>
              {funnelOption && <ReactECharts option={funnelOption} style={{ height: '100%', width: '100%' }} />}
            </div>

            {/* 4 个关键指标 */}
            <Row gutter={16} style={{ marginTop: 16 }}>
              <Col span={6}>
                <Tooltip title="评估通过数 / 已评估数。反映评估策略宽松度，过低可能漏掉好货，过高可能放过差货。">
                  <Statistic
                    title={<span><AimOutlined /> 命中率</span>}
                    value={data.metrics.hit_rate}
                    precision={1}
                    suffix="%"
                    valueStyle={{ color: token.colorInfo }}
                  />
                </Tooltip>
              </Col>
              <Col span={6}>
                <Tooltip title="抢单失败数 / 抢单触发数。反映评估+抢单策略的准确性，越低越好。">
                  <Statistic
                    title={<span><FallOutlined /> 误报率</span>}
                    value={data.metrics.false_positive_rate}
                    precision={1}
                    suffix="%"
                    valueStyle={{ color: data.metrics.false_positive_rate > 30 ? token.colorError : token.colorText }}
                  />
                </Tooltip>
              </Col>
              <Col span={6}>
                <Tooltip title="抢单成功数 / 抢单触发数。反映抢单执行能力，受库存、网络、风控影响。">
                  <Statistic
                    title={<span><ThunderboltOutlined /> 抢单成功率</span>}
                    value={data.metrics.conversion_rate}
                    precision={1}
                    suffix="%"
                    valueStyle={{ color: token.colorSuccess }}
                  />
                </Tooltip>
              </Col>
              <Col span={6}>
                <Tooltip title="抢单成功数 / 采集商品数。端到端转化能力，受采集质量、评估策略、抢单执行综合影响。">
                  <Statistic
                    title={<span><CheckCircleOutlined /> 端到端率</span>}
                    value={data.metrics.overall_rate}
                    precision={1}
                    suffix="%"
                    valueStyle={{ color: token.colorPrimary }}
                  />
                </Tooltip>
              </Col>
            </Row>
          </>
        ) : (
          <Empty description="暂无漏斗数据" />
        )}
      </Spin>
    </Card>
  )
}
