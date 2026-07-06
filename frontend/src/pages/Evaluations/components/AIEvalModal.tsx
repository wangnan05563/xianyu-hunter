import { Modal, Spin, Row, Col, Statistic, Tag, Alert, Collapse, Empty, Button } from 'antd'
import type { AIConditionResult } from '../../../api'

interface AIEvalModalProps {
  open: boolean
  loading: boolean
  result: AIConditionResult | null
  itemId: string
  onCancel: () => void
}

export function AIEvalModal({ open, loading, result, itemId, onCancel }: AIEvalModalProps) {
  return (
    <Modal
      title={`AI 成色评估 - ${itemId}`}
      open={open}
      onCancel={onCancel}
      footer={<Button onClick={onCancel}>关闭</Button>}
      width={560}
    >
      <Spin spinning={loading}>
        {result ? (
          <div>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={12}>
                <Statistic
                  title="评估结论"
                  value={result.verdict === 'recommend' ? '推荐' : '谨慎'}
                  valueStyle={{ color: result.verdict === 'recommend' ? '#52c41a' : '#faad14' }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="成色评分"
                  value={`${result.condition_score}/10`}
                  valueStyle={{ color: result.condition_score >= 7 ? '#52c41a' : '#faad14' }}
                />
              </Col>
            </Row>
            <div style={{ marginBottom: 12 }}>
              <strong>评估理由：</strong>
              <p style={{ marginTop: 4 }}>{result.reason}</p>
            </div>
            {result.price_range && result.price_range.sample_size > 0 ? (
              <div style={{
                marginBottom: 12, padding: 12, borderRadius: 6,
                background: 'rgba(82, 196, 26, 0.06)', border: '1px solid #d9f7be',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <strong style={{ color: '#389e0d' }}>同类物品价格参考</strong>
                  <Tag color="green" style={{ fontSize: 11 }}>
                    {result.price_range.source_label || result.price_range.source}
                  </Tag>
                </div>
                <Row gutter={8}>
                  <Col span={8}>
                    <Statistic
                      title="捡漏价格"
                      value={result.price_range.bargain_price == null ? '—' : `¥${result.price_range.bargain_price}`}
                      valueStyle={{ color: '#52c41a', fontSize: 18 }}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="价格区间"
                      value={result.price_range.min_price != null && result.price_range.max_price != null
                        ? `¥${result.price_range.min_price}~${result.price_range.max_price}`
                        : '—'}
                      valueStyle={{ fontSize: 14 }}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="中位数"
                      value={result.price_range.median_price == null ? '—' : `¥${result.price_range.median_price}`}
                      valueStyle={{ fontSize: 14 }}
                    />
                  </Col>
                </Row>
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                  样本数：{result.price_range.sample_size}
                  {result.price_range.range_days ? ` · 近${result.price_range.range_days}天` : ''}
                  {' · 低于捡漏价格的商品可能为真捡漏，也需警惕假货风险'}
                </div>
              </div>
            ) : (
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
                message="暂无同类物品价格参考"
                description={result.price_range?.message || '当前商品无关联任务或暂无已售数据，建议先执行实时搜索采集更多商品以获取价格参考。'}
              />
            )}
            {result.risk_signals?.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <strong>风险信号：</strong>
                <div style={{ marginTop: 4 }}>
                  {result.risk_signals.map((sig, i) => (
                    <Tag key={`${sig}-${i}`} color="orange" style={{ marginBottom: 4 }}>{sig}</Tag>
                  ))}
                </div>
              </div>
            )}
            {result.detail && (
              <Collapse
                items={[{ key: 'detail', label: '详细分析', children: <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{result.detail}</pre> }]}
                size="small"
              />
            )}
            <div style={{ marginTop: 12, fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
              来源：{result.source === 'llm' ? 'AI 视觉分析' : '规则模拟'}
              {result.cached ? '（缓存）' : ''}
            </div>
          </div>
        ) : (
          !loading && <Empty description="点击评估按钮开始 AI 分析" />
        )}
      </Spin>
    </Modal>
  )
}
