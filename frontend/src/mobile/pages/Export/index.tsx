// frontend/src/mobile/pages/Export/index.tsx
// 移动端数据导出：支持 4 个数据集（items/evaluations/orders/events）的快速下载
// 设计要点：下载走 axios blob + 隐藏 <a download>，HTTP 错误与 0 行结果都能反馈到 toast
import { useEffect, useState, useCallback } from 'react'
import { Card, Tag, Spin, App, Button, Radio, Space, DatePicker, theme, Alert } from 'antd'
import { DownloadOutlined, FileTextOutlined } from '@ant-design/icons'
import { exportApi, type ExportDataset, type ExportDatasetInfo, type ExportParams } from '../../../api/export'
import { taskApi } from '../../../api/task'
import type { Task } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'
import { notifyExportResult } from '../../../utils/exportFeedback'
import { useFailedSources } from '../../../hooks/useFailedSources'
import LoadFailedBar from '../../components/LoadFailedBar'

const { RangePicker } = DatePicker

// 本页的数据源（T02701 失败账与错误条一一对应）
type ExportSource = 'datasets' | 'tasks'
const SOURCE_LABELS: Record<ExportSource, string> = {
  datasets: '数据集定义',
  tasks: '任务列表',
}

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
  const [limit] = useState<number>(5000)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const { failed, settle } = useFailedSources<ExportSource>()

  const loadInit = useCallback(async (): Promise<void> => {
    setLoading(true)
    // 并发拉取数据集定义 + 任务列表，各自记账：
    // 任一路失败只挂自己的错误条，并把「取不到」和「服务端确实没给」分开
    const [dsRes, taskRes] = await Promise.allSettled([
      exportApi.listDatasets(),
      taskApi.list({ limit: 100 }),
    ])
    const ds = settle(dsRes, 'datasets')
    if (ds) setDatasets(ds.datasets)
    const taskList = settle(taskRes, 'tasks')
    if (taskList) setTasks(taskList.items)
    setLoading(false)
  }, [settle])

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

  // 触发下载：axios blob + 隐藏 <a download>（T02587 / FR-C-2）
  // 原实现把 URL 直接挂到 <a href> 上点击：HTTP 错误不可见、也拿不到行数，
  // 0 行同样弹「已开始下载」
  const handleDownload = async (): Promise<void> => {
    if (downloading) return
    setDownloading(true)
    try {
      const res = await exportApi.downloadFile(dataset, buildParams())
      notifyExportResult(message, res, dataset)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '下载失败', 3)
    } finally {
      setDownloading(false)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <div>
      {/* 数据集定义取不到时用的是本页内置的 4 个名字，必须明说，不能假装是服务端下发的 */}
      {failed.datasets && (
        <LoadFailedBar source={SOURCE_LABELS.datasets} note="以下选项是内置兜底列表，服务端真实列定义未知" onRetry={() => void loadInit()} />
      )}
      {failed.tasks && <LoadFailedBar source={SOURCE_LABELS.tasks} onRetry={() => void loadInit()} />}

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
        onClick={() => void handleDownload()}
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
