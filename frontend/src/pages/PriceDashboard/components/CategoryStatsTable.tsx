import { useMemo } from 'react'
import { Card, Space, Button, Tooltip, Table, Alert, Tag, Typography, Empty, theme } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { formatPrice } from '../utils'
import type { CategoryStat } from '../../../api'

const { Text } = Typography

interface CategoryStatsTableProps {
  readonly loading: boolean
  readonly stats: CategoryStat[]
  readonly statsTotal: number
  readonly onRefresh: () => void
}

// 品类统计明细表格卡片
// 为什么提取：表格列定义和卡片包装约 50 行，列定义复杂且独立，
// 提取后可单独维护列配置，降低主组件复杂度
export default function CategoryStatsTable({
  loading,
  stats,
  statsTotal,
  onRefresh,
}: CategoryStatsTableProps) {
  const { token } = theme.useToken()

  const statsColumns = useMemo(() => [
    {
      title: '品类',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (name: string, record: CategoryStat) => (
        <span>{name || record.keyword || '未分类'}</span>
      ),
    },
    {
      title: '任务价格区间',
      dataIndex: 'task_price_range',
      key: 'task_price_range',
      width: 150,
      render: (tr: CategoryStat['task_price_range']) => {
        if (!tr || (tr.min_price == null && tr.max_price == null)) {
          return <Text type="secondary">未配置</Text>
        }
        return (
          <Tag color="cyan">
            {tr.min_price == null ? '—' : `¥${tr.min_price}`}
            {' ~ '}
            {tr.max_price == null ? '—' : `¥${tr.max_price}`}
          </Tag>
        )
      },
    },
    { title: '样本数', dataIndex: 'count', key: 'count', width: 80, sorter: (a: CategoryStat, b: CategoryStat) => a.count - b.count, render: (v: number) => <Tag color="blue">{v}</Tag> },
    { title: '最低价', dataIndex: 'min', key: 'min', width: 90, sorter: (a: CategoryStat, b: CategoryStat) => a.min - b.min, render: (v: number) => formatPrice(v) },
    { title: '最高价', dataIndex: 'max', key: 'max', width: 90, sorter: (a: CategoryStat, b: CategoryStat) => a.max - b.max, render: (v: number) => formatPrice(v) },
    { title: '均价', dataIndex: 'mean', key: 'mean', width: 90, sorter: (a: CategoryStat, b: CategoryStat) => a.mean - b.mean, render: (v: number) => formatPrice(v) },
    { title: '中位数', dataIndex: 'median', key: 'median', width: 90, sorter: (a: CategoryStat, b: CategoryStat) => a.median - b.median, render: (v: number) => formatPrice(v) },
    { title: 'P25', dataIndex: 'p25', key: 'p25', width: 80, render: (v: number) => formatPrice(v) },
    { title: 'P75', dataIndex: 'p75', key: 'p75', width: 80, render: (v: number) => formatPrice(v) },
    { title: 'P10', dataIndex: 'p10', key: 'p10', width: 80, render: (v: number) => formatPrice(v) },
    { title: 'P90', dataIndex: 'p90', key: 'p90', width: 80, render: (v: number) => formatPrice(v) },
  ], [])

  return (
    <Card
      title="品类统计明细"
      extra={
        <Space>
          <span style={{ fontSize: 12, color: token.colorTextTertiary }}>
            共 {statsTotal} 件商品 · {stats.length} 个品类
          </span>
          <Tooltip title="刷新">
            <Button size="small" icon={<ReloadOutlined />} onClick={onRefresh} loading={loading} />
          </Tooltip>
        </Space>
      }
    >
      <Alert
        type="info"
        showIcon={false}
        style={{ marginBottom: 12, fontSize: 12 }}
        message="已按各任务配置的价格区间过滤超范围样本（1 元引流、配件、超范围高价），最高价/最低价均不会超出任务配置的上限/下限。"
      />
      <Table<CategoryStat>
        rowKey={(r) => r.task_id || '__orphan__'}
        columns={statsColumns}
        dataSource={stats}
        loading={loading}
        size="small"
        pagination={{ pageSize: 10, showSizeChanger: false, showTotal: (t) => `共 ${t} 个品类` }}
        scroll={{ x: 960 }}
        locale={{ emptyText: <Empty description="暂无统计数据" /> }}
      />
    </Card>
  )
}
