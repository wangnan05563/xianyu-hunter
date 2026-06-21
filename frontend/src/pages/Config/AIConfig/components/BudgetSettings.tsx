import { Card, Button, Row, Col, InputNumber } from 'antd'
import type { AIUsage } from '../../../../api'

interface BudgetSettingsProps {
  budget: AIUsage['budget']
  // 局部字段更新，避免子组件直接操作父级 setState
  onBudgetChange: (patch: Partial<AIUsage['budget']>) => void
  saving: boolean
  onSave: () => void
}

export default function BudgetSettings({ budget, onBudgetChange, saving, onSave }: BudgetSettingsProps) {
  return (
    <>
      <h3 style={{ marginBottom: 8 }}>预算控制</h3>
      <p style={{ color: '#999', marginBottom: 16 }}>
        超出预算后 AI 调用自动降级到规则模式，不影响系统正常使用。
      </p>

      <Card style={{ background: '#fafafa' }}>
        <Row gutter={16}>
          <Col span={8}>
            <div>
              <label style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>每日 Token 上限</label>
              <InputNumber
                value={budget.daily_token_limit}
                onChange={(v) => onBudgetChange({ daily_token_limit: v ?? 500000 })}
                placeholder="500000"
                style={{ width: '100%' }}
                min={0}
              />
            </div>
          </Col>
          <Col span={8}>
            <div>
              <label style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>每日费用上限 (USD)</label>
              <InputNumber
                value={budget.daily_cost_limit_usd}
                onChange={(v) => onBudgetChange({ daily_cost_limit_usd: v ?? 5 })}
                placeholder="5.0"
                style={{ width: '100%' }}
                min={0}
                step={0.1}
              />
            </div>
          </Col>
          <Col span={8}>
            <div>
              <label style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>每分钟调用上限</label>
              <InputNumber
                value={budget.rate_limit_per_min}
                onChange={(v) => onBudgetChange({ rate_limit_per_min: v ?? 20 })}
                placeholder="20"
                style={{ width: '100%' }}
                min={0}
              />
            </div>
          </Col>
        </Row>
        <div style={{ marginTop: 16 }}>
          <Button type="primary" loading={saving} onClick={onSave}>
            保存预算设置
          </Button>
        </div>
      </Card>
    </>
  )
}
