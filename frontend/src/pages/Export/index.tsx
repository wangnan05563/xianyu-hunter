import { useEffect, useMemo, useState } from 'react'
import { Card, Col, Row, Typography, Tag, Input, DatePicker, InputNumber, Button, Space, Spin, Empty, message, theme } from 'antd'
import { DownloadOutlined, DatabaseOutlined } from '@ant-design/icons'
import type { Dayjs } from 'dayjs'
import { exportApi, type ExportDataset, type ExportDatasetInfo, type ExportParams } from '../../api'

const { Paragraph, Text } = Typography
const { RangePicker } = DatePicker

// 数据集展示元数据：图标颜色 + 中文标题（description 由后端返回）
const DATASET_DISPLAY: Record<ExportDataset, { color: string; title: string }> = {
  items: { color: '#1677ff', title: '商品列表' },
  evaluations: { color: '#722ed1', title: '评估记录' },
  orders: { color: '#fa8c16', title: '订单记录' },
  events: { color: '#13c2c2', title: '事件日志' },
}

// 各数据集支持的筛选字段（控制表单显隐）
const DATASET_FILTERS: Record<ExportDataset, { task_id: boolean; time: boolean; status: boolean; level: boolean }> = {
  items: { task_id: true, time: true, status: false, level: false },
  evaluations: { task_id: true, time: true, status: false, level: false },
  orders: { task_id: true, time: true, status: true, level: false },
  events: { task_id: true, time: true, status: false, level: true },
}

interface FilterState {
  task_id: string
  range: [Dayjs, Dayjs] | null
  status: string
  level: string
  limit: number
}

const DEFAULT_FILTER: FilterState = {
  task_id: '',
  range: null,
  status: '',
  level: '',
  limit: 5000,
}

/**
 * 数据导出页面：将商品/评估/订单/事件数据导出为 CSV
 *
 * 为什么独立成页面而非仅嵌入 ExportButton：
 * 1. 嵌入式按钮只能按当前页上下文过滤（如 Items 页按 selectedTask）
 * 2. 独立页面支持用户自定义 task_id/时间范围/状态/等级/limit 等完整筛选条件
 * 3. 提供数据集列定义预览，便于用户确认导出字段
 */
export default function Export() {
  const { token } = theme.useToken()
  const [datasets, setDatasets] = useState<ExportDatasetInfo[]>([])
  const [loading, setLoading] = useState(true)
  // 每个数据集独立维护筛选条件，切换数据集时保留各自的输入
  const [filters, setFilters] = useState<Record<ExportDataset, FilterState>>({
    items: { ...DEFAULT_FILTER },
    evaluations: { ...DEFAULT_FILTER },
    orders: { ...DEFAULT_FILTER },
    events: { ...DEFAULT_FILTER },
  })

  useEffect(() => {
    exportApi.listDatasets()
      .then((res) => setDatasets(res.datasets || []))
      .catch(() => {
        // 拉取失败时用静态列定义兜底，保证页面可用
        setDatasets([
          { key: 'items', columns: ['id', 'task_id', 'title', 'price', 'publish_time', 'region', 'seller_id', 'want_cnt', 'view_cnt', 'first_seen', 'last_seen'], description: '商品列表' },
          { key: 'evaluations', columns: ['id', 'item_id', 'seller_id', 'score', 'risk_level', 'dimension_scores', 'reject_reasons', 'created_at'], description: '评估记录' },
          { key: 'orders', columns: ['id', 'task_id', 'item_id', 'seller_id', 'order_no', 'price', 'status', 'confirmed_at', 'paid_at', 'created_at'], description: '订单记录' },
          { key: 'events', columns: ['id', 'type', 'task_id', 'item_id', 'stage', 'level', 'message', 'created_at'], description: '事件日志' },
        ])
      })
      .finally(() => setLoading(false))
  }, [])

  const handleExport = (ds: ExportDataset) => {
    const f = filters[ds]
    const params: ExportParams = { limit: f.limit }
    if (f.task_id.trim()) params.task_id = f.task_id.trim()
    if (f.range?.length === 2) {
      params.start = f.range[0].format('YYYY-MM-DDTHH:mm:ss')
      params.end = f.range[1].format('YYYY-MM-DDTHH:mm:ss')
    }
    if (f.status.trim()) params.status = f.status.trim()
    if (f.level.trim()) params.level = f.level.trim()
    try {
      exportApi.download(ds, params)
      // download 是浏览器直跳，无法捕获响应回调，仅给"已触发"反馈
      message.success(`正在导出 ${DATASET_DISPLAY[ds].title}...`)
    } catch {
      message.error('导出失败，请稍后重试')
    }
  }

  const updateFilter = (ds: ExportDataset, patch: Partial<FilterState>) => {
    setFilters((prev) => ({ ...prev, [ds]: { ...prev[ds], ...patch } }))
  }

  // 数据集卡片渲染
  const cards = useMemo(() => {
    if (loading) return null
    if (datasets.length === 0) {
      return <Empty description="暂无可导出的数据集" />
    }
    return datasets.map((ds) => {
      const display = DATASET_DISPLAY[ds.key] || { color: '#1677ff', title: ds.key }
      const filterConfig = DATASET_FILTERS[ds.key]
      const f = filters[ds.key]
      return (
        <Col xs={24} lg={12} key={ds.key}>
          <Card
            title={
              <Space>
                <DatabaseOutlined style={{ color: display.color }} />
                <span>{display.title}</span>
                <Tag color={display.color}>{ds.key}</Tag>
              </Space>
            }
            styles={{ header: { background: token.colorFillAlter } }}
          >
            <Paragraph type="secondary" style={{ marginBottom: 12 }}>
              {ds.description}
            </Paragraph>

            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>列定义：</Text>
              <div style={{ marginTop: 4 }}>
                {ds.columns.map((col) => (
                  <Tag key={col} style={{ marginBottom: 4 }}>{col}</Tag>
                ))}
              </div>
            </div>

            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              {filterConfig.task_id && (
                <Input
                  allowClear
                  size="small"
                  placeholder="任务 ID 过滤（可选）"
                  value={f.task_id}
                  onChange={(e) => updateFilter(ds.key, { task_id: e.target.value })}
                />
              )}
              {filterConfig.time && (
                <RangePicker
                  size="small"
                  showTime
                  style={{ width: '100%' }}
                  value={f.range}
                  onChange={(range) => updateFilter(ds.key, { range: range as [Dayjs, Dayjs] | null })}
                />
              )}
              {filterConfig.status && (
                <Input
                  allowClear
                  size="small"
                  placeholder="订单状态过滤（如 succeeded/failed/pending）"
                  value={f.status}
                  onChange={(e) => updateFilter(ds.key, { status: e.target.value })}
                />
              )}
              {filterConfig.level && (
                <Input
                  allowClear
                  size="small"
                  placeholder="事件等级过滤（如 info/warning/error）"
                  value={f.level}
                  onChange={(e) => updateFilter(ds.key, { level: e.target.value })}
                />
              )}
              <Space size={8} style={{ width: '100%', justifyContent: 'space-between' }}>
                <Space size={4}>
                  <Text type="secondary" style={{ fontSize: 12 }}>行数上限：</Text>
                  <InputNumber
                    size="small"
                    min={1}
                    max={50000}
                    value={f.limit}
                    onChange={(v) => updateFilter(ds.key, { limit: v ?? 5000 })}
                    style={{ width: 100 }}
                  />
                </Space>
                <Button
                  type="primary"
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() => handleExport(ds.key)}
                >
                  导出 CSV
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>
      )
    })
  }, [datasets, loading, filters, token])

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 24 }}>
      <div style={{ marginBottom: 16 }}>
        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
          将商品、评估、订单、事件数据导出为 CSV（Excel/Numbers 友好，含 UTF-8 BOM）。支持按任务 ID、时间范围、状态、等级筛选。
        </Paragraph>
      </div>
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <Spin tip="加载数据集..." />
        </div>
      ) : (
        <Row gutter={[16, 16]}>
          {cards}
        </Row>
      )}
    </div>
  )
}
