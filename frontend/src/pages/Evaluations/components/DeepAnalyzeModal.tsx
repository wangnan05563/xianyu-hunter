import { Modal, Spin, Descriptions, Alert, Tabs, Collapse, Empty, Tag, Row, Col, Statistic, Button } from 'antd'
import type { DeepAnalyzeResult, DeepCheckResult } from '../../../api'

interface DeepAnalyzeModalProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly open: boolean
  readonly loading: boolean
  readonly result: DeepAnalyzeResult | null
  readonly itemId: string
  readonly onCancel: () => void
}

function VerdictTag({ verdict }: { readonly verdict: 'recommend' | 'caution' | 'reject' }) {
  const tagColorMap = { recommend: 'success', caution: 'warning', reject: 'error' } as const
  const labelMap = { recommend: '推荐', caution: '谨慎', reject: '拒绝' } as const
  return <Tag color={tagColorMap[verdict]}>{labelMap[verdict]}</Tag>
}

function DeepCheckPanel({ title, check, signalLabel }: {
  readonly title: string
  readonly check: DeepCheckResult
  readonly signalLabel: string
}) {
  const riskColor = (() => {
    if (check.risk_level === 'low') return 'success'
    if (check.risk_level === 'medium') return 'warning'
    return 'error'
  })()
  const scoreColor = (() => {
    if (check.score >= 7) return '#52c41a'
    if (check.score >= 4) return '#faad14'
    return '#ff4d4f'
  })()
  const signals = check.signals ?? []
  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 12 }}>
        <Col span={12}>
          <Statistic
            title={`${title} 评分`}
            value={`${check.score}/10`}
            valueStyle={{ color: scoreColor, fontSize: 20 }}
          />
        </Col>
        <Col span={12} style={{ display: 'flex', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginBottom: 4 }}>风险等级</div>
            <Tag color={riskColor} style={{ fontSize: 14, padding: '2px 12px' }}>
              {(() => {
                if (check.risk_level === 'low') return '低'
                if (check.risk_level === 'medium') return '中'
                return '高'
              })()}
            </Tag>
          </div>
        </Col>
      </Row>
      {signals.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginBottom: 4 }}>{signalLabel}：</div>
          <div>
            {signals.map((s, i) => (
              <Tag key={`${s}-${i}`} color="orange" style={{ marginBottom: 4 }}>{s}</Tag>
            ))}
          </div>
        </div>
      )}
      <div style={{
        padding: 10, borderRadius: 6, background: 'var(--xh-bg-code)',
        fontSize: 13, color: 'var(--xh-text-secondary)', lineHeight: 1.6,
      }}>
        {check.detail || '无详细分析'}
      </div>
    </div>
  )
}

export function DeepAnalyzeModal({ open, loading, result, itemId, onCancel }: DeepAnalyzeModalProps) {
  return (
    <Modal
      title={`AI 深度鉴伪 - ${itemId}`}
      open={open}
      onCancel={onCancel}
      footer={<Button onClick={onCancel}>关闭</Button>}
      width={720}
    >
      <Spin spinning={loading} tip="多模态分析中，最多 90s...">
        {result ? (
          <div>
            <Descriptions
              size="small"
              column={3}
              bordered
              style={{ marginBottom: 12 }}
              items={[
                {
                  key: 'verdict',
                  label: '综合结论',
                  children: <VerdictTag verdict={result.overall_verdict} />,
                },
                {
                  key: 'score',
                  label: '综合评分',
                  children: (
                    <span style={{ fontWeight: 600 }}>
                      {result.overall_score}/10
                    </span>
                  ),
                },
                {
                  key: 'source',
                  label: '数据来源',
                  children: result.source === 'llm' ? 'AI Vision' : '规则模拟',
                },
              ]}
            />
            <Alert
              type={(() => {
                const verdict = result.overall_verdict
                if (verdict === 'recommend') return 'success'
                if (verdict === 'caution') return 'warning'
                return 'error'
              })()}
              showIcon
              message={result.summary}
              style={{ marginBottom: 12 }}
            />
            <Tabs
              items={[
                ...(result.stolen_image ? [{
                  key: 'stolen_image',
                  label: '盗图检测',
                  children: (
                    <DeepCheckPanel
                      title="盗图检测"
                      check={result.stolen_image}
                      signalLabel="风险信号"
                    />
                  ),
                }] : []),
                ...(result.damage ? [{
                  key: 'damage',
                  label: '物理损坏',
                  children: (
                    <DeepCheckPanel
                      title="物理损坏识别"
                      check={result.damage}
                      signalLabel="损坏类型"
                    />
                  ),
                }] : []),
                ...(result.consistency ? [{
                  key: 'consistency',
                  label: '一致性',
                  children: (
                    <DeepCheckPanel
                      title="描述与图片一致性"
                      check={result.consistency}
                      signalLabel="不一致项"
                    />
                  ),
                }] : []),
                ...(result.template ? [{
                  key: 'template',
                  label: '文案模板化',
                  children: (
                    <DeepCheckPanel
                      title="文案模板化检测"
                      check={result.template}
                      signalLabel="风险信号"
                    />
                  ),
                }] : []),
              ]}
            />
            {result.image_hashes && result.image_hashes.length > 0 && (
              <Collapse
                size="small"
                style={{ marginTop: 8 }}
                items={[{
                  key: 'hashes',
                  label: `图片哈希（${result.image_hashes.length}）`,
                  children: (
                    <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', margin: 0 }}>
                      {result.image_hashes.map(h => `${h.url}\n  → ${h.hash}`).join('\n')}
                    </pre>
                  ),
                }]}
              />
            )}
          </div>
        ) : (
          !loading && <Empty description="点击闪电按钮开始 AI 深度鉴伪" />
        )}
      </Spin>
    </Modal>
  )
}
