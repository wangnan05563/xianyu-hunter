import type { ReactNode } from 'react'
import { Card, Space, Select, Button, Tooltip, Spin, Empty, theme } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import ReactECharts from '../../../components/charts/EChart'
import type { EChartOption } from '../../../components/charts/EChart'
import { SORT_OPTIONS, RANGE_OPTIONS } from '../constants'
import { formatPrice } from '../utils'
import type { CategoryComparisonSortBy } from '../../../api'

interface CategoryComparisonChartProps {
  readonly loading: boolean
  readonly comparisonOption: EChartOption | null
  readonly overallMean: number
  readonly sortBy: CategoryComparisonSortBy
  readonly order: 'asc' | 'desc'
  readonly rangeDays: number
  readonly onSortByChange: (v: CategoryComparisonSortBy) => void
  readonly onOrderChange: (v: 'asc' | 'desc') => void
  readonly onRangeDaysChange: (v: number) => void
  readonly onRefresh: () => void
}

// 品类横向对比图表卡片
// 为什么提取：原组件中该模块约 70 行 JSX，包含筛选器、图表和图例说明，
// 提取后主组件更清晰，且该组件可独立维护和测试
export default function CategoryComparisonChart({
  loading,
  comparisonOption,
  overallMean,
  sortBy,
  order,
  rangeDays,
  onSortByChange,
  onOrderChange,
  onRangeDaysChange,
  onRefresh,
}: CategoryComparisonChartProps) {
  const { token } = theme.useToken()

  // S3358: 把嵌套三元（loading ? ... : comparisonOption ? ... : ...）提取为独立 if/else 赋值
  let chartContent: ReactNode
  if (loading) {
    chartContent = <div style={{ textAlign: 'center', padding: 60 }}><Spin /></div>
  } else if (comparisonOption) {
    chartContent = (
      <>
        <ReactECharts option={comparisonOption} style={{ height: 420 }} notMerge={true} lazyUpdate={true} />
        <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextTertiary }}>
          <span>全体均价：<b style={{ color: token.colorText }}>{formatPrice(overallMean)}</b></span>
          <span style={{ marginLeft: 16 }}>红色：高于均价 5% 以上</span>
          <span style={{ marginLeft: 12 }}>绿色：低于均价 5% 以上</span>
          <span style={{ marginLeft: 12 }}>蓝色：接近均价</span>
        </div>
      </>
    )
  } else {
    chartContent = <Empty description="暂无对比数据" />
  }

  return (
    <Card
      title="品类横向对比"
      extra={
        <Space wrap>
          <Select
            size="small" value={sortBy} style={{ width: 140 }}
            onChange={onSortByChange}
            options={SORT_OPTIONS}
          />
          <Select
            size="small" value={order} style={{ width: 90 }}
            onChange={onOrderChange}
            options={[{ value: 'desc', label: '降序' }, { value: 'asc', label: '升序' }]}
          />
          <Select
            size="small" value={rangeDays} style={{ width: 110 }}
            onChange={onRangeDaysChange}
            options={RANGE_OPTIONS}
          />
          <Tooltip title="刷新">
            <Button size="small" icon={<ReloadOutlined />} onClick={onRefresh} loading={loading} />
          </Tooltip>
        </Space>
      }
    >
      {chartContent}
    </Card>
  )
}
