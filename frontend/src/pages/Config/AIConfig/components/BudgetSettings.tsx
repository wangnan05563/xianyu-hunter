import { Card, Row, Col, InputNumber } from 'antd'
import { TipButton } from '@/components/TipButton'
import type { AIUsage } from '../../../../api'

interface BudgetSettingsProps {
  readonly budget: AIUsage['budget']
  // 局部字段更新，避免子组件直接操作父级 setState
  readonly onBudgetChange: (patch: Partial<AIUsage['budget']>) => void
  readonly saving: boolean
  readonly onSave: () => void
}

export default function BudgetSettings({ budget, onBudgetChange, saving, onSave }: BudgetSettingsProps) {
  return (
    <>
      <h3 style={{ marginBottom: 8 }}>预算控制</h3>
      <p style={{ color: 'var(--xh-text-tertiary)', marginBottom: 16 }}>
        超出预算后 AI 调用自动降级到规则模式，不影响系统正常使用。
      </p>

      <Card style={{ background: 'var(--xh-bg-spotlight)' }}>
        <Row gutter={16}>
          <Col span={8}>
            <div>
              {/* S6853：用 htmlFor 关联 label 与 input，保证屏幕阅读器可读 */}
              <label htmlFor="budget-daily-token" style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>每日 Token 上限</label>
              <InputNumber
                id="budget-daily-token"
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
              <label htmlFor="budget-daily-cost" style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>每日费用上限 (USD)</label>
              <InputNumber
                id="budget-daily-cost"
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
              <label htmlFor="budget-rate-limit" style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>每分钟调用上限</label>
              <InputNumber
                id="budget-rate-limit"
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
          <TipButton tip="保存当前预算设置" type="primary" loading={saving} onClick={onSave}>
            保存预算设置
          </TipButton>
        </div>
      </Card>
    </>
  )
}
