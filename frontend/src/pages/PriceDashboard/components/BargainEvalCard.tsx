import type { ReactNode } from 'react'
import { Card, Spin, Empty, Space, InputNumber, Row, Col, Tag, Progress, Alert, Typography, theme } from 'antd'
import { TipButton } from '@/components/TipButton'
import { ReloadOutlined } from '@ant-design/icons'
import { BARGAIN_LEVEL_CONFIG } from '../constants'
import { formatPrice } from '../utils'
import type { BargainEval } from '../../../api/types'

const { Text } = Typography

interface BargainEvalCardProps {
  readonly soldTaskId: string | undefined
  readonly evalCurrentPrice: number | null
  readonly evalResult: BargainEval | null
  readonly evalLoading: boolean
  readonly onPriceChange: (v: number | null) => void
  readonly onEvaluate: () => void
  readonly onRefresh: () => void
}

// 价格评估卡片
// 为什么提取：该模块包含价格输入、评估结果展示（等级、得分、建议、分位数），
// 状态和渲染逻辑较为复杂，提取后主组件更简洁
export default function BargainEvalCard({
  soldTaskId,
  evalCurrentPrice,
  evalResult,
  evalLoading,
  onPriceChange,
  onEvaluate,
  onRefresh,
}: BargainEvalCardProps) {
  const { token } = theme.useToken()

  const levelConfig = BARGAIN_LEVEL_CONFIG[evalResult?.bargain_level || ''] || BARGAIN_LEVEL_CONFIG.unknown

  const getProgressStatus = (): 'success' | 'normal' | 'exception' => {
    if (!evalResult) return 'normal'
    if (evalResult.bargain_level === 'excellent' || evalResult.bargain_level === 'good') return 'success'
    if (evalResult.bargain_level === 'fair') return 'normal'
    return 'exception'
  }

  const getAlertType = (): 'success' | 'info' | 'warning' | 'error' => {
    if (!evalResult) return 'info'
    if (evalResult.bargain_level === 'excellent' || evalResult.bargain_level === 'good') return 'success'
    if (evalResult.bargain_level === 'fair') return 'info'
    if (evalResult.bargain_level === 'poor') return 'warning'
    return 'error'
  }

  const canEvaluate = soldTaskId && evalCurrentPrice != null && evalCurrentPrice > 0

  // S3358: 把嵌套三元（evalLoading ? ... : evalResult ? ... : ...）提取为独立 if/else 赋值
  let evalContent: ReactNode
  if (evalLoading) {
    evalContent = <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  } else if (evalResult) {
    evalContent = (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Row gutter={16} align="middle">
          <Col xs={24} sm={8}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text type="secondary">评估等级：</Text>
              <Tag color={levelConfig.color}>
                {levelConfig.label}
              </Tag>
            </div>
          </Col>
          <Col xs={24} sm={16}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text type="secondary">捡漏得分：</Text>
              <Progress
                percent={evalResult.bargain_score}
                size="small"
                status={getProgressStatus()}
                style={{ flex: 1, minWidth: 200, marginBottom: 0 }}
              />
            </div>
          </Col>
        </Row>
        <Alert
          type={getAlertType()}
          message={evalResult.suggestion}
        />
        {evalResult.sold_price_stats && (
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12, color: token.colorTextTertiary }}>
            <span>已售 P10：<b>{formatPrice(evalResult.sold_price_stats.p10)}</b></span>
            <span>P25：<b>{formatPrice(evalResult.sold_price_stats.p25)}</b></span>
            <span>中位数：<b>{formatPrice(evalResult.sold_price_stats.median)}</b></span>
            <span>P75：<b>{formatPrice(evalResult.sold_price_stats.p75)}</b></span>
            <span>P90：<b>{formatPrice(evalResult.sold_price_stats.p90)}</b></span>
            <span>样本数：<b>{evalResult.sold_price_stats.count}</b></span>
          </div>
        )}
      </div>
    )
  } else {
    evalContent = <Empty description={'输入价格并点击"评估"查看捡漏建议'} />
  }

  return (
    <Card
      title="价格评估"
      extra={
        <TipButton
          size="small"
          icon={<ReloadOutlined />}
          onClick={onRefresh}
          loading={evalLoading}
          disabled={!canEvaluate}
          tip="刷新评估结果与分位数数据"
        />
      }
    >
      {/* S7735: 反转否定条件 !soldTaskId 为肯定条件 soldTaskId */}
      {soldTaskId ? (
        <>
          <Space wrap style={{ marginBottom: 16 }}>
            <Text type="secondary">当前价格：</Text>
            <InputNumber
              value={evalCurrentPrice}
              onChange={onPriceChange}
              min={0}
              precision={2}
              prefix="¥"
              placeholder="输入待评估价格"
              style={{ width: 180 }}
            />
            <TipButton
              type="primary"
              size="small"
              onClick={onEvaluate}
              loading={evalLoading}
              disabled={evalCurrentPrice == null || evalCurrentPrice <= 0}
              tip="按当前价格评估捡漏等级与得分"
            >
              评估
            </TipButton>
            <Text type="secondary" style={{ fontSize: 12 }}>
              基于任务价格区间 + 已售商品分位数综合评估
            </Text>
          </Space>
          {evalContent}
        </>
      ) : (
        <Empty description={'请先在上方"捡漏价格参考"选择品类，再进行价格评估'} />
      )}
    </Card>
  )
}
