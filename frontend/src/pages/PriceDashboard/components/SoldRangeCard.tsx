import type { ReactNode } from 'react'
import { Card, Space, Select, Button, Tooltip, Spin, Empty, Statistic, Row, Col, Tag, Alert, Typography, theme } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { RANGE_OPTIONS } from '../constants'
import type { Task } from '../../../api/types'

const { Text } = Typography

interface SoldRangeData {
  min_price: number | null
  max_price: number | null
  median_price: number | null
  bargain_price: number | null
  p10?: number | null
  p25?: number | null
  p75?: number | null
  p90?: number | null
  sample_size: number
  filtered_count?: number
  source: string
  source_label?: string
  message?: string
  task_price_range?: { min_price: number | null; max_price: number | null }
}

interface SoldRangeCardProps {
  readonly loading: boolean
  readonly soldRange: SoldRangeData | null
  readonly soldTaskId: string | undefined
  readonly soldRangeDays: number
  readonly tasks: Task[]
  readonly onTaskChange: (v: string | undefined) => void
  readonly onRangeDaysChange: (v: number) => void
  readonly onRefresh: () => void
}

// 捡漏价格参考卡片
// 为什么提取：该模块包含统计卡片、元信息展示和过滤提示，约 80 行 JSX，
// 逻辑独立，提取后可降低主组件复杂度，且便于单独维护
export default function SoldRangeCard({
  loading,
  soldRange,
  soldTaskId,
  soldRangeDays,
  tasks,
  onTaskChange,
  onRangeDaysChange,
  onRefresh,
}: SoldRangeCardProps) {
  const { token } = theme.useToken()

  const hasTaskPriceRange = soldRange?.task_price_range
    && (soldRange.task_price_range.min_price != null || soldRange.task_price_range.max_price != null)

  // S4624: 把嵌套模板字面量的内层提取为独立变量，避免模板嵌套
  const filterNote = soldRange?.filtered_count ? `，本次共过滤 ${soldRange.filtered_count} 个` : ''

  // S3358: 把嵌套三元（loading ? ... : soldRange && sample_size > 0 ? ... : ...）提取为独立 if/else 赋值
  let bodyContent: ReactNode
  if (loading) {
    bodyContent = <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  } else if (soldRange && soldRange.sample_size > 0) {
    bodyContent = (
      <>
        <Row gutter={16}>
          <Col xs={12} sm={6}>
            <Statistic
              title="捡漏价格"
              value={soldRange.bargain_price ?? 0}
              precision={2}
              prefix="¥"
              valueStyle={{ color: token.colorSuccess }}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>低于此价可捡漏</Text>
          </Col>
          <Col xs={12} sm={6}>
            <Statistic title="最低价" value={soldRange.min_price ?? 0} precision={2} prefix="¥" />
          </Col>
          <Col xs={12} sm={6}>
            <Statistic title="中位数" value={soldRange.median_price ?? 0} precision={2} prefix="¥" />
          </Col>
          <Col xs={12} sm={6}>
            <Statistic title="最高价" value={soldRange.max_price ?? 0} precision={2} prefix="¥" />
          </Col>
        </Row>
        <div style={{ marginTop: 12, display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12 }}>
          <span><Text type="secondary">样本数：</Text><Tag color="blue">{soldRange.sample_size}</Tag></span>
          {soldRange.source_label && (
            <span><Text type="secondary">数据来源：</Text><Tag color="purple">{soldRange.source_label}</Tag></span>
          )}
          {hasTaskPriceRange && (
            <span>
              <Text type="secondary">任务价格区间：</Text>
              <Tag color="cyan">
                {/* S7735: 反转否定条件 != null 为肯定条件 == null，交换分支 */}
                {soldRange.task_price_range!.min_price == null ? '—' : `¥${soldRange.task_price_range!.min_price}`}
                {' ~ '}
                {soldRange.task_price_range!.max_price == null ? '—' : `¥${soldRange.task_price_range!.max_price}`}
              </Tag>
            </span>
          )}
          {soldRange.filtered_count != null && soldRange.filtered_count > 0 && (
            <span>
              <Tooltip title="被任务价格区间过滤掉的异常样本数（1 元引流、配件、超范围高价）">
                <Tag color="orange">已过滤 {soldRange.filtered_count} 个</Tag>
              </Tooltip>
            </span>
          )}
        </div>
        {hasTaskPriceRange && (
          <Alert
            type="info"
            showIcon={false}
            style={{ marginTop: 8, fontSize: 12 }}
            message={`已按任务价格区间过滤异常样本（1 元引流、配件、超范围高价）${filterNote}，统计更贴近任务实际监控目标。`}
          />
        )}
      </>
    )
  } else {
    bodyContent = <Empty description={soldRange?.message || '暂无已售价格数据，建议先执行实时搜索采集更多商品'} />
  }

  return (
    <Card
      title="捡漏价格参考"
      extra={
        <Space wrap>
          <Select
            size="small" value={soldTaskId} style={{ width: 200 }}
            placeholder="选择品类"
            allowClear
            onChange={onTaskChange}
            options={tasks.map((t) => ({ value: t.id, label: (t.name || t.keyword || t.id).slice(0, 30) }))}
          />
          <Select
            size="small" value={soldRangeDays} style={{ width: 110 }}
            onChange={onRangeDaysChange}
            options={RANGE_OPTIONS.filter((o) => o.value !== 0)}
          />
          <Tooltip title="刷新">
            <Button size="small" icon={<ReloadOutlined />} onClick={onRefresh} loading={loading} />
          </Tooltip>
        </Space>
      }
    >
      {bodyContent}
    </Card>
  )
}
