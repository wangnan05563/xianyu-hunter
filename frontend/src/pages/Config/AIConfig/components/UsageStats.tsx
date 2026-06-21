import { Card, Row, Col, Statistic, Progress } from 'antd'
import type { AIUsage } from '../../../../api'
import { ENDPOINT_LABELS, formatTokens, getProgressColor } from '../constants'

interface UsageStatsProps {
  usage: AIUsage
}

export default function UsageStats({ usage }: UsageStatsProps) {
  return (
    <>
      <h3 style={{ marginBottom: 8 }}>用量仪表盘</h3>
      <p style={{ color: '#999', marginBottom: 16 }}>
        今日 AI 调用统计与费用估算（基于模型公开定价）
      </p>

      {/* 4 个 Statistic 卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card style={{ textAlign: 'center', background: '#fafafa' }}>
            <Statistic title="今日调用" value={usage.today.total_calls ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ textAlign: 'center', background: '#fafafa' }}>
            <Statistic title="今日 Token" value={formatTokens(usage.today.total_tokens ?? 0)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ textAlign: 'center', background: '#fafafa' }}>
            <Statistic
              title="今日费用 (USD)"
              value={`$${(usage.today.total_cost_usd ?? 0).toFixed(4)}`}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ textAlign: 'center', background: '#fafafa' }}>
            <Statistic
              title="今日费用 (CNY)"
              value={`¥${(usage.today.total_cost_cny ?? 0).toFixed(2)}`}
            />
          </Card>
        </Col>
      </Row>

      {/* 预算进度条 */}
      <Card style={{ marginBottom: 16, background: '#fafafa' }}>
        {/* Token 预算进度 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <strong>Token 预算</strong>
          <span style={{ color: '#999' }}>
            {formatTokens(usage.today.total_tokens ?? 0)} / {formatTokens(usage.budget.daily_token_limit ?? 0)}
          </span>
        </div>
        <Progress
          percent={Math.min(usage.budget.token_usage_pct ?? 0, 100)}
          strokeColor={getProgressColor(usage.budget.token_usage_pct ?? 0)}
          showInfo={false}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
          <span style={{ fontSize: 11, color: '#999' }}>{(usage.budget.token_usage_pct ?? 0).toFixed(1)}% 已用</span>
        </div>

        {/* 费用预算进度 */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: 16,
            marginBottom: 8,
          }}
        >
          <strong>费用预算</strong>
          <span style={{ color: '#999' }}>
            ${(usage.today.total_cost_usd ?? 0).toFixed(2)} / ${(usage.budget.daily_cost_limit_usd ?? 0).toFixed(2)}
          </span>
        </div>
        <Progress
          percent={Math.min(usage.budget.cost_usage_pct ?? 0, 100)}
          strokeColor={getProgressColor(usage.budget.cost_usage_pct ?? 0)}
          showInfo={false}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
          <span style={{ fontSize: 11, color: '#999' }}>{(usage.budget.cost_usage_pct ?? 0).toFixed(1)}% 已用</span>
        </div>
      </Card>

      {/* 调用分布列表 */}
      {Object.keys(usage.today.by_endpoint ?? {}).length > 0 && (
        <Card style={{ marginBottom: 16, background: '#fafafa' }} title="调用分布">
          {Object.entries(usage.today.by_endpoint ?? {}).map(([endpoint, count]) => (
            <div
              key={endpoint}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '4px 0',
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              <span>{ENDPOINT_LABELS[endpoint] || endpoint}</span>
              <span>{count} 次</span>
            </div>
          ))}
        </Card>
      )}

      {/* 近 7 天趋势列表 */}
      {(usage.history ?? []).length > 0 && (
        <Card style={{ marginBottom: 16, background: '#fafafa' }} title="近 7 天趋势">
          {(usage.history ?? []).map((day) => (
            <div
              key={day.date}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '4px 0',
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              <span>{day.date}</span>
              <span>
                {day.total_calls ?? 0} 次
                <span style={{ marginLeft: 8, color: '#999' }}>
                  {formatTokens((day.total_input_tokens ?? 0) + (day.total_output_tokens ?? 0))} tokens
                </span>
                <span style={{ marginLeft: 8, color: '#999' }}>¥{(day.total_cost_cny ?? 0).toFixed(2)}</span>
              </span>
            </div>
          ))}
        </Card>
      )}
    </>
  )
}
