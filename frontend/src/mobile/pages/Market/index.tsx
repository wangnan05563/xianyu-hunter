// frontend/src/mobile/pages/Market/index.tsx
// 移动端价格行情：分类统计列表 + 简化的概览卡片
// 设计要点：相比桌面端去掉多维度对比表/AI 分析入口，保留核心"已售价格区间"和"分类均价"
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Tag, Spin, App, Select, Space, Button, Empty, theme, Statistic, Row, Col, Alert,
} from 'antd'
import { ReloadOutlined, DollarOutlined } from '@ant-design/icons'
import { priceApi } from '../../../api/price'
import { taskApi } from '../../../api/task'
import type { Task, SoldPriceRange } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'

// 范围选项（天）
const RANGE_OPTIONS = [
  { value: 7, label: '近 7 天' },
  { value: 30, label: '近 30 天' },
  { value: 90, label: '近 90 天' },
]

export default function MobileMarket() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [tasks, setTasks] = useState<Task[]>([])
  const [taskId, setTaskId] = useState<string | undefined>(undefined)
  const [rangeDays, setRangeDays] = useState<number>(30)
  const [soldRange, setSoldRange] = useState<SoldPriceRange | null>(null)
  const [categories, setCategories] = useState<Array<{ name: string; keyword: string; count: number; mean: number; median: number; min: number; max: number; p10: number }>>([])
  const [loading, setLoading] = useState(true)

  const loadTasks = useCallback(async (): Promise<void> => {
    try {
      const res = await taskApi.list({ limit: 100 })
      setTasks(res.items)
    } catch (e) {
      message.error(extractApiError(e, '加载任务失败'), 3)
    }
  }, [message])

  const loadStats = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      // 并发拉取已售区间 + 分类统计
      const [sold, stats] = await Promise.all([
        priceApi.soldRange({ task_id: taskId, range_days: rangeDays }).catch(() => null),
        priceApi.categoryStats({ task_id: taskId, range_hours: rangeDays * 24 }).catch(() => ({ categories: [], total_count: 0 })),
      ])
      setSoldRange(sold)
      // 仅保留前 5 个分类避免移动端长列表
      setCategories(
        stats.categories.slice(0, 5).map((c) => ({
          name: c.name,
          keyword: c.keyword,
          count: c.count,
          mean: c.mean,
          median: c.median,
          min: c.min,
          max: c.max,
          p10: c.p10,
        })),
      )
    } catch (e) {
      message.error(extractApiError(e, '加载行情失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [taskId, rangeDays, message])

  useEffect(() => { void loadTasks() }, [loadTasks])
  useEffect(() => { void loadStats() }, [loadStats])

  if (loading && !soldRange) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  return (
    <div>
      {/* 任务 + 范围过滤 */}
      <Space direction="vertical" size={8} style={{ width: '100%', marginBottom: 12 }}>
        <select
          value={taskId ?? ''}
          onChange={(e) => setTaskId(e.target.value || undefined)}
          style={{
            width: '100%', height: 32, padding: '0 8px', borderRadius: 4,
            border: `1px solid ${themeToken.colorBorder}`, background: themeToken.colorBgContainer,
            fontSize: 14,
          }}
        >
          <option value="">全部任务</option>
          {tasks.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
        <Space size={8} style={{ width: '100%' }}>
          <Select
            value={rangeDays}
            onChange={(v) => setRangeDays(v)}
            options={RANGE_OPTIONS}
            style={{ flex: 1 }}
          />
          <Button icon={<ReloadOutlined />} onClick={() => void loadStats()}>
            刷新
          </Button>
        </Space>
      </Space>

      {/* 已售价格概览 */}
      <Card size="small" style={{ marginBottom: 12 }} title="已售价格区间">
        {soldRange && soldRange.sample_size > 0 ? (
          <>
            <Row gutter={8} style={{ marginBottom: 8 }}>
              <Col span={12}>
                <Statistic
                  title={<span style={{ fontSize: 11 }}>最低价</span>}
                  value={soldRange.min_price ?? 0}
                  prefix="¥"
                  valueStyle={{ fontSize: 18, color: '#52c41a' }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title={<span style={{ fontSize: 11 }}>最高价</span>}
                  value={soldRange.max_price ?? 0}
                  prefix="¥"
                  valueStyle={{ fontSize: 18, color: '#ff4d4f' }}
                />
              </Col>
            </Row>
            <Row gutter={8} style={{ marginBottom: 8 }}>
              <Col span={12}>
                <Statistic
                  title={<span style={{ fontSize: 11 }}>中位数</span>}
                  value={soldRange.median_price ?? 0}
                  prefix="¥"
                  valueStyle={{ fontSize: 16 }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title={<span style={{ fontSize: 11 }}>捡漏参考（P10）</span>}
                  value={soldRange.p10 ?? 0}
                  prefix="¥"
                  valueStyle={{ fontSize: 16, color: '#1677ff' }}
                />
              </Col>
            </Row>
            <Alert
              type="info"
              showIcon
              message={`样本 ${soldRange.sample_size} 条${soldRange.filtered_count ? `（已过滤 ${soldRange.filtered_count} 个超范围样本）` : ''}`}
              style={{ fontSize: 11 }}
            />
          </>
        ) : (
          <Empty description="暂无可用样本" imageStyle={{ height: 60 }} />
        )}
      </Card>

      {/* 分类均价列表 */}
      <Card
        size="small"
        title="分类均价（Top 5）"
        extra={
          <Tag color="blue" icon={<DollarOutlined />}>
            {categories.length} 类
          </Tag>
        }
      >
        {categories.length === 0 ? (
          <Empty description="暂无数据" imageStyle={{ height: 60 }} />
        ) : (
          categories.map((c) => (
            <div
              key={c.name}
              style={{
                padding: '8px 0',
                borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 500 }}>{c.name}</span>
                <Tag>{c.count} 条</Tag>
              </div>
              <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
                关键词：{c.keyword}
              </div>
              <Space size={4} wrap>
                <Tag color="green">均价 ¥{c.mean.toFixed(0)}</Tag>
                <Tag color="blue">中位 ¥{c.median.toFixed(0)}</Tag>
                <Tag color="orange">P10 ¥{c.p10.toFixed(0)}</Tag>
              </Space>
              <div style={{ fontSize: 11, color: themeToken.colorTextTertiary, marginTop: 4 }}>
                范围：¥{c.min.toFixed(0)} - ¥{c.max.toFixed(0)}
              </div>
            </div>
          ))
        )}
      </Card>
    </div>
  )
}
