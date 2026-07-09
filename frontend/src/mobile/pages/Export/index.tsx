// frontend/src/mobile/pages/Export/index.tsx
// 移动端数据导出：支持 4 个数据集（items/evaluations/orders/events）的快速下载
// 设计要点：点击即直跳 /api/export/{dataset} 浏览器原生处理 CSV 流式下载
import { useEffect, useState, useCallback } from 'react'
import { Card, Tag, Spin, App, Button, Radio, Space, DatePicker, theme, Alert } from 'antd'
import { DownloadOutlined, FileTextOutlined } from '@ant-design/icons'
import { exportApi, type ExportDataset, type ExportDatasetInfo, type ExportParams } from '../../../api/export'
import { taskApi } from '../../../api/task'
import type { Task } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'

const { RangePicker } = DatePicker

// 数据集描述：与后端 api_export 端点对齐
const DATASET_DESC: Record<ExportDataset, string> = {
  items: '商品快照（标题、价格、卖家、采集时间）',
  evaluations: '评估记录（分数、风险等级、AI 评语）',
  orders: '抢单记录（状态、价格、订单号）',
  events: '事件流（任务/系统/告警等全部类型）',
}

export default function MobileExport() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [datasets, setDatasets] = useState<ExportDatasetInfo[]>([])
  const [dataset, setDataset] = useState<ExportDataset>('items')
  const [tasks, setTasks] = useState<Task[]>([])
  const [taskId, setTaskId] = useState<string | undefined>(undefined)
  const [range, setRange] = useState<[string, string] | null>(null)
  const [limit, setLimit] = useState<number>(5000)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)

  const loadInit = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      // 并发拉取数据集定义 + 任务列表（供下拉）
      const [ds, taskRes] = await Promise.all([
        exportApi.listDatasets().catch(() => ({ datasets: [] as ExportDatasetInfo[] })),
        taskApi.list({ limit: 100 }).catch(() => ({ items: [] as Task[], total: 0 })),
      ])
      setDatasets(ds.datasets)
      setTasks(taskRes.items)
    } catch (e) {
      message.error(extractApiError(e, '加载失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void loadInit() }, [loadInit])

  // 组装参数：时间区间转 ISO
  const buildParams = (): ExportParams => {
    const p: ExportParams = { limit }
    if (taskId) p.task_id = taskId
    if (range) {
      p.start = range[0]
      p.end = range[1]
    }
    return p
  }

  // 触发下载：用 anchor + click 而非 location.href 直跳，避免移动端浏览器覆盖当前 SPA
  const handleDownload = (): void => {
    if (downloading) return
    setDownloading(true)
    try {
      const url = exportApi.buildUrl(dataset, buildParams())
      // 创建一个隐藏的 a 触发下载，保持 SPA 状态
      const a = document.createElement('a')
      a.href = url
      // 后端会从 URL 参数 file_name 推断；如未提供则后端使用默认命名
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      // 立即移除：download 是异步的，但点击已触发
      requestAnimationFrame(() => document.body.removeChild(a))
      message.success('已开始下载')
    } catch (e) {
      message.error(extractApiError(e, '下载失败'), 3)
    } finally {
      // 浏览器下载无回包，用定时器复位 downloading
      setTimeout(() => setDownloading(false), 1500)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <div>
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <div style={{ fontSize: 13, color: themeToken.colorTextSecondary }}>
            选择数据集和条件，点击下载即可获取 CSV 文件
          </div>
          <Radio.Group
            value={dataset}
            onChange={(e) => setDataset(e.target.value)}
            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, width: '100%' }}
          >
            {(datasets.length > 0 ? datasets : ['items', 'evaluations', 'orders', 'events'].map((k) => ({
              key: k as ExportDataset, columns: [], description: DATASET_DESC[k as ExportDataset],
            }))).map((d) => (
              <Radio.Button
                key={d.key}
                value={d.key}
                style={{ textAlign: 'center', height: 'auto', padding: '8px 4px', whiteSpace: 'normal' }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                  <FileTextOutlined />
                  <span style={{ fontSize: 12 }}>{d.key}</span>
                </div>
              </Radio.Button>
            ))}
          </Radio.Group>
        </Space>
      </Card>

      <Card size="small" style={{ marginBottom: 12 }} title="过滤条件">
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>任务范围（可选）</div>
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
                <option key={t.id} value={t.id}>{t.name}（{t.id.slice(0, 8)}）</option>
              ))}
            </select>
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>时间区间（可选）</div>
            <RangePicker
              showTime
              style={{ width: '100%' }}
              onChange={(_d, ds) => {
                // ds[0]/ds[1] 已是 ISO 字符串（dayjs toISOString）；空值数组转 null
                if (!ds[0] || !ds[1]) setRange(null)
                else setRange([ds[0], ds[1]])
              }}
            />
          </div>
          <Alert
            type="info"
            showIcon
            message={`最大导出 ${limit} 行`}
            description="超出限制时仅导出最近 N 条。复杂过滤请在桌面端完成。"
            style={{ fontSize: 12 }}
          />
        </Space>
      </Card>

      <Button
        type="primary"
        size="large"
        block
        icon={<DownloadOutlined />}
        loading={downloading}
        onClick={handleDownload}
      >
        下载 {dataset}.csv
      </Button>

      <Card size="small" style={{ marginTop: 12 }} title="数据集说明">
        <Space direction="vertical" size={6} style={{ fontSize: 13 }}>
          {(Object.keys(DATASET_DESC) as ExportDataset[]).map((k) => (
            <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Tag color={dataset === k ? 'blue' : 'default'}>{k}</Tag>
              <span style={{ color: themeToken.colorTextSecondary }}>{DATASET_DESC[k]}</span>
            </div>
          ))}
        </Space>
      </Card>
    </div>
  )
}
