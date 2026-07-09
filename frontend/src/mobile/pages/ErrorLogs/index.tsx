// frontend/src/mobile/pages/ErrorLogs/index.tsx
// 移动端错误日志：按状态/级别/类型过滤 + 列表 + AI 上下文详情
// 关键简化：去掉桌面端批量操作/状态流转工作流，保留新单条查看 + AI 诊断入口
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Tag, Spin, App, Select, Button, Drawer, Space, Empty, theme, Alert, Modal,
} from 'antd'
import { ReloadOutlined, RobotOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { errorLogApi } from '../../../api/errorLogs'
import type { ErrorLog } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'

// 错误类型颜色档
const TYPE_COLORS: Record<string, string> = {
  HTTP_ERROR: 'red',
  RUNTIME_ERROR: 'volcano',
  VALIDATION_ERROR: 'orange',
  WAF_BLOCKED: 'magenta',
  AUTH_ERROR: 'purple',
  TIMEOUT: 'gold',
  UNKNOWN: 'default',
}

// 状态颜色档
const STATUS_COLORS: Record<ErrorLog['status'], string> = {
  new: 'red',
  resolved: 'green',
  ignored: 'default',
}

const LIST_LIMIT = 50

export default function MobileErrorLogs() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [items, setItems] = useState<ErrorLog[]>([])
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [statusFilter, setStatusFilter] = useState<ErrorLog['status'] | undefined>('new')
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<ErrorLog | null>(null)
  const [aiContextMd, setAiContextMd] = useState('')
  const [aiContextOpen, setAiContextOpen] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)

  const fetchList = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const data = await errorLogApi.list({
        status: statusFilter,
        error_type: typeFilter,
        limit: LIST_LIMIT,
      })
      setItems(data.items)
      setCounts(data.status_counts || {})
    } catch (e) {
      message.error(extractApiError(e, '加载错误日志失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, typeFilter, message])

  useEffect(() => { void fetchList() }, [fetchList])

  // 标记已处理
  const resolveOne = async (id: number): Promise<void> => {
    try {
      await errorLogApi.updateStatus(id, 'resolved')
      message.success('已标记为已处理')
      void fetchList()
      if (detail?.id === id) setDetail(null)
    } catch (e) {
      message.error(extractApiError(e, '操作失败'), 3)
    }
  }

  // 拉取 AI 上下文
  const openAiContext = async (id: number): Promise<void> => {
    setAiLoading(true)
    try {
      const md = await errorLogApi.getAiContext(id, 'markdown')
      setAiContextMd(md)
      setAiContextOpen(true)
    } catch (e) {
      message.error(extractApiError(e, '加载 AI 上下文失败'), 3)
    } finally {
      setAiLoading(false)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <div>
      {/* 状态计数横条：一目了然问题严重程度 */}
      <Space size={6} style={{ width: '100%', marginBottom: 8, flexWrap: 'wrap' }}>
        <Tag color="red">新 {counts.new ?? 0}</Tag>
        <Tag color="green">已处理 {counts.resolved ?? 0}</Tag>
        <Tag color="default">已忽略 {counts.ignored ?? 0}</Tag>
      </Space>

      {/* 过滤栏 */}
      <Space size={8} style={{ width: '100%', marginBottom: 12 }}>
        <Select
          placeholder="状态"
          allowClear
          style={{ flex: 1 }}
          value={statusFilter}
          onChange={(v: ErrorLog['status'] | undefined) => setStatusFilter(v)}
          options={[
            { value: 'new', label: '新' },
            { value: 'resolved', label: '已处理' },
            { value: 'ignored', label: '已忽略' },
          ]}
        />
        <Select
          placeholder="错误类型"
          allowClear
          style={{ flex: 1 }}
          value={typeFilter}
          onChange={(v) => setTypeFilter(v)}
          options={Object.keys(TYPE_COLORS).map((k) => ({ value: k, label: k }))}
        />
        <Button
          icon={<ReloadOutlined />}
          onClick={() => void fetchList()}
        />
      </Space>

      {items.length === 0 ? (
        <Empty description="暂无错误日志" />
      ) : (
        items.map((item) => (
          <Card
            key={item.id}
            size="small"
            style={{ marginBottom: 8, cursor: 'pointer' }}
            onClick={() => setDetail(item)}
          >
            <div style={{ display: 'flex', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
              <Tag color={STATUS_COLORS[item.status]}>{item.status}</Tag>
              <Tag color={TYPE_COLORS[item.error_type] || 'default'}>{item.error_type}</Tag>
              <span style={{ fontSize: 11, color: themeToken.colorTextTertiary, marginLeft: 'auto' }}>
                {new Date(item.created_at).toLocaleString('zh-CN')}
              </span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{item.error_message}</div>
            {item.request_path && (
              <div style={{ fontSize: 11, color: themeToken.colorTextSecondary, fontFamily: 'monospace' }}>
                {item.request_method} {item.request_path}
              </div>
            )}
          </Card>
        ))
      )}

      {/* 详情抽屉 */}
      <Drawer
        title="错误详情"
        placement="bottom"
        height="85%"
        open={detail !== null}
        onClose={() => setDetail(null)}
      >
        {detail && (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <div>
              <Tag color={STATUS_COLORS[detail.status]}>{detail.status}</Tag>
              <Tag color={TYPE_COLORS[detail.error_type] || 'default'}>{detail.error_type}</Tag>
            </div>
            <div>
              <strong>时间：</strong>
              {new Date(detail.created_at).toLocaleString('zh-CN')}
            </div>
            <div>
              <strong>错误：</strong>
              <div style={{ marginTop: 4, padding: 8, background: themeToken.colorBgLayout, borderRadius: 4, wordBreak: 'break-word', fontSize: 13 }}>
                {detail.error_message}
              </div>
            </div>
            {detail.request_path && (
              <div>
                <strong>请求：</strong>
                <div style={{ marginTop: 4, fontFamily: 'monospace', fontSize: 12 }}>
                  {detail.request_method} {detail.request_path}
                </div>
              </div>
            )}
            {detail.stack_trace && (
              <div>
                <strong>堆栈：</strong>
                <pre style={{ background: themeToken.colorBgLayout, padding: 8, borderRadius: 4, fontSize: 11, overflow: 'auto', maxHeight: 200 }}>
                  {detail.stack_trace}
                </pre>
              </div>
            )}
            <Space size={8} style={{ width: '100%' }}>
              <Button
                type="primary"
                icon={<RobotOutlined />}
                loading={aiLoading}
                onClick={() => void openAiContext(detail.id)}
                style={{ flex: 1 }}
              >
                AI 诊断
              </Button>
              {detail.status === 'new' && (
                <Button
                  icon={<CheckCircleOutlined />}
                  onClick={() => void resolveOne(detail.id)}
                  style={{ flex: 1 }}
                >
                  标记已处理
                </Button>
              )}
            </Space>
          </Space>
        )}
      </Drawer>

      {/* AI 上下文 Modal */}
      <Modal
        title="AI 诊断上下文"
        open={aiContextOpen}
        onCancel={() => setAiContextOpen(false)}
        footer={null}
        width="92%"
      >
        <Alert
          type="info"
          showIcon
          message="将以下上下文复制给 AI 助手可获得更精准的诊断"
          style={{ marginBottom: 8, fontSize: 12 }}
        />
        <pre style={{ background: themeToken.colorBgLayout, padding: 8, borderRadius: 4, fontSize: 11, overflow: 'auto', maxHeight: 400, whiteSpace: 'pre-wrap' }}>
          {aiContextMd}
        </pre>
      </Modal>
    </div>
  )
}
