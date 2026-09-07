import { Modal, Spin, Row, Col, Statistic, Tag, Alert, Collapse, Empty } from 'antd'
import { TipButton } from '@/components/TipButton'
import type { AIConditionResult } from '../../../api'

interface AIEvalModalProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly open: boolean
  readonly loading: boolean
  readonly result: AIConditionResult | null
  readonly itemId: string
  readonly onCancel: () => void
}

// S3776 修复：原主组件 CC=28，将大块 JSX 拆分为独立子组件，主函数只剩骨架

// 评估结论 + 评分：拆分后主流程不再嵌套 ternary 判断颜色
function VerdictSection({ verdict, score }: {
  readonly verdict: string
  readonly score: number
}) {
  return (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col span={12}>
        <Statistic
          title="评估结论"
          value={verdict === 'recommend' ? '推荐' : '谨慎'}
          valueStyle={{ color: verdict === 'recommend' ? '#52c41a' : '#faad14' }}
        />
      </Col>
      <Col span={12}>
        <Statistic
          title="成色评分"
          value={`${score}/10`}
          valueStyle={{ color: score >= 7 ? '#52c41a' : '#faad14' }}
        />
      </Col>
    </Row>
  )
}

// 评估理由区块
function ReasonSection({ reason }: { readonly reason: string }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <strong>评估理由：</strong>
      <p style={{ marginTop: 4 }}>{reason}</p>
    </div>
  )
}

// 价格参考区块：sample_size > 0 走数据展示分支，否则走提示 Alert
function PriceRangeSection({ priceRange }: {
  readonly priceRange: AIConditionResult['price_range']
}) {
  if (priceRange && priceRange.sample_size > 0) {
    return (
      <div style={{
        marginBottom: 12, padding: 12, borderRadius: 6,
        background: 'rgba(82, 196, 26, 0.06)', border: '1px solid #d9f7be',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <strong style={{ color: '#389e0d' }}>同类物品价格参考</strong>
          <Tag color="green" style={{ fontSize: 11 }}>
            {priceRange.source_label || priceRange.source}
          </Tag>
        </div>
        <Row gutter={8}>
          <Col span={8}>
            <Statistic
              title="捡漏价格"
              value={priceRange.bargain_price == null ? '—' : `¥${priceRange.bargain_price}`}
              valueStyle={{ color: '#52c41a', fontSize: 18 }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="价格区间"
              value={priceRange.min_price != null && priceRange.max_price != null
                ? `¥${priceRange.min_price}~${priceRange.max_price}`
                : '—'}
              valueStyle={{ fontSize: 14 }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="中位数"
              value={priceRange.median_price == null ? '—' : `¥${priceRange.median_price}`}
              valueStyle={{ fontSize: 14 }}
            />
          </Col>
        </Row>
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
          样本数：{priceRange.sample_size}
          {priceRange.range_days ? ` · 近${priceRange.range_days}天` : ''}
          {' · 低于捡漏价格的商品可能为真捡漏，也需警惕假货风险'}
        </div>
      </div>
    )
  }
  return (
    <Alert
      type="info"
      showIcon
      style={{ marginBottom: 12 }}
      message="暂无同类物品价格参考"
      description={priceRange?.message || '当前商品无关联任务或暂无已售数据，建议先执行实时搜索采集更多商品以获取价格参考。'}
    />
  )
}

// 风险信号标签组：无信号时返回 null，主流程不嵌套 &&
function RiskSignalsSection({ signals }: { readonly signals?: string[] }) {
  if (!signals?.length) return null
  return (
    <div style={{ marginBottom: 12 }}>
      <strong>风险信号：</strong>
      <div style={{ marginTop: 4 }}>
        {signals.map((sig, i) => (
          <Tag key={`${sig}-${i}`} color="orange" style={{ marginBottom: 4 }}>{sig}</Tag>
        ))}
      </div>
    </div>
  )
}

// 详细分析折叠面板：无 detail 时不渲染
function DetailSection({ detail }: { readonly detail?: string }) {
  if (!detail) return null
  return (
    <Collapse
      items={[{ key: 'detail', label: '详细分析', children: <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{detail}</pre> }]}
      size="small"
    />
  )
}

// 来源 + 缓存标记
function SourceFooter({ source, cached }: {
  readonly source: string
  readonly cached?: boolean
}) {
  return (
    <div style={{ marginTop: 12, fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
      来源：{source === 'llm' ? 'AI 视觉分析' : '规则模拟'}
      {cached ? '（缓存）' : ''}
    </div>
  )
}

// 整合 result 渲染：把条件渲染集中到此组件，主 Modal 只剩骨架
function ResultContent({ result }: { readonly result: AIConditionResult }) {
  return (
    <div>
      <VerdictSection verdict={result.verdict} score={result.condition_score} />
      <ReasonSection reason={result.reason} />
      <PriceRangeSection priceRange={result.price_range} />
      <RiskSignalsSection signals={result.risk_signals} />
      <DetailSection detail={result.detail} />
      <SourceFooter source={result.source} cached={result.cached} />
    </div>
  )
}

export function AIEvalModal({ open, loading, result, itemId, onCancel }: AIEvalModalProps) {
  return (
    <Modal
      title={`AI 成色评估 - ${itemId}`}
      open={open}
      onCancel={onCancel}
      footer={<TipButton onClick={onCancel} tip="关闭 AI 评估弹窗">关闭</TipButton>}
      width={560}
    >
      <Spin spinning={loading}>
        {result ? (
          <ResultContent result={result} />
        ) : (
          !loading && <Empty description="点击评估按钮开始 AI 分析" />
        )}
      </Spin>
    </Modal>
  )
}
