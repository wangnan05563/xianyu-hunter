import { Modal, Row, Col, Card, Statistic, Tag, Image, Button, Space } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import type { OfficialCollectResult } from '../../../api'
import { translateDimension, translateRejectReason } from '../dimensionLabels'

interface CollectResultModalProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly open: boolean
  readonly result: OfficialCollectResult | null
  readonly onCancel: () => void
}

export function CollectResultModal({ open, result, onCancel }: CollectResultModalProps) {
  return (
    <Modal
      title={
        <Space>
          <GlobalOutlined style={{ color: '#1890ff' }} />
          <span>官方采集结果 - {result?.item_id}</span>
          <Tag color="blue">官方数据</Tag>
        </Space>
      }
      open={open}
      onCancel={onCancel}
      footer={<Button onClick={onCancel}>关闭</Button>}
      width={720}
    >
      {result && (
        <div>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="评估评分"
                  value={result.evaluation.score ?? 'N/A'}
                  valueStyle={{
                    color: (() => {
                      const score = result.evaluation.score
                      if (score == null) return '#999'
                      if (score >= 80) return '#52c41a'
                      if (score >= 60) return '#faad14'
                      return '#ff4d4f'
                    })(),
                    fontSize: 24,
                  }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="风险等级"
                  value={result.evaluation.risk_level}
                  valueStyle={{ fontSize: 16 }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="数据质量"
                  value={result.evaluation.data_quality}
                  valueStyle={{ fontSize: 16 }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="是否通过"
                  value={result.evaluation.is_passed ? '通过' : '未通过'}
                  valueStyle={{
                    color: result.evaluation.is_passed ? '#52c41a' : '#ff4d4f',
                    fontSize: 16,
                  }}
                />
              </Card>
            </Col>
          </Row>

          <Card title="商品信息" size="small" style={{ marginBottom: 12 }}>
            <Row gutter={[8, 8]}>
              <Col span={12}><strong>标题：</strong>{result.item.title || '—'}</Col>
              <Col span={6}><strong>价格：</strong><span style={{ color: '#f5222d', fontWeight: 600 }}>¥{result.item.price?.toFixed(2)}</span></Col>
              <Col span={6}><strong>地区：</strong>{result.item.region || '—'}</Col>
              <Col span={6}><strong>想要数：</strong>{result.item.want_cnt}</Col>
              <Col span={6}><strong>浏览数：</strong>{result.item.view_cnt}</Col>
              <Col span={24}>
                <strong>描述：</strong>
                <p style={{ marginTop: 4, maxHeight: 100, overflow: 'auto', color: 'var(--xh-text-secondary)' }}>
                  {result.item.description || '暂无描述'}
                </p>
              </Col>
              {result.item.image_urls.length > 0 && (
                <Col span={24}>
                  <strong>商品图片：</strong>
                  <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                    {result.item.image_urls.slice(0, 6).map((url, i) => (
                      <Image
                        key={`${url}-${i}`}
                        src={url}
                        referrerPolicy="no-referrer"
                        width={80}
                        height={80}
                        style={{ objectFit: 'cover', borderRadius: 4 }}
                        alt={`图片${i + 1}`}
                      />
                    ))}
                  </div>
                </Col>
              )}
            </Row>
          </Card>

          <Card title="卖家信息" size="small" style={{ marginBottom: 12 }}>
            <Row gutter={[8, 8]}>
              <Col span={8}><strong>昵称：</strong>{result.seller.nick || '—'}</Col>
              <Col span={8}><strong>信用分：</strong>{result.seller.credit_score ?? '—'}</Col>
              <Col span={8}><strong>注册天数：</strong>{result.seller.register_days}天</Col>
              <Col span={8}><strong>在售数：</strong>{result.seller.on_sale_count}</Col>
              <Col span={8}><strong>已售数：</strong>{result.seller.sold_count}</Col>
              <Col span={8}><strong>卖家ID：</strong>{result.seller.id || '—'}</Col>
            </Row>
          </Card>

          {result.reviews.length > 0 && (
            <Card title={`评价/留言 (${result.reviews.length})`} size="small" style={{ marginBottom: 12 }}>
              {result.reviews.map((review, i) => (
                <div key={`${review}-${i}`} style={{
                  padding: '6px 0', borderBottom: i < result.reviews.length - 1 ? '1px solid #f0f0f0' : 'none',
                  fontSize: 13,
                }}>
                  {review}
                </div>
              ))}
            </Card>
          )}

          <Card title="评估维度详情" size="small" style={{ marginBottom: 12 }}>
            <Row gutter={[8, 8]}>
              {Object.entries(result.evaluation.dimension_scores).map(([dim, score]) => (
                <Col key={dim} span={8}>
                  <Statistic
                    title={`${translateDimension(dim)} (${dim})`}
                    value={score}
                    valueStyle={{ fontSize: 16, color: (() => {
                      const num = Number(score)
                      if (num >= 70) return '#52c41a'
                      if (num >= 40) return '#faad14'
                      return '#ff4d4f'
                    })() }}
                  />
                </Col>
              ))}
            </Row>
            {result.evaluation.reject_reasons.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <strong>拒绝原因：</strong>
                {result.evaluation.reject_reasons.map((reason, i) => (
                  <Tag key={`${reason}-${i}`} color="orange" style={{ marginBottom: 4 }} title={reason}>
                    {translateRejectReason(reason)}
                  </Tag>
                ))}
              </div>
            )}
          </Card>

          <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', textAlign: 'center' }}>
            数据来源：闲鱼官方页面采集 · 采集时间：{new Date().toLocaleString('zh-CN', { hour12: false })}
          </div>
        </div>
      )}
    </Modal>
  )
}
