/**
 * 任务管理菜单组件
 *
 * 功能：
 * 1. 下拉选择任务，默认选中列表第一个任务
 * 2. 展示选中任务关联的闲鱼内容（商品/卖家）
 * 3. source 字段严格 HTML 转义，防止 XSS
 * 4. 一键启动所有任务（含确认、加载状态、反馈）
 *
 * 设计原则：复用现有 Ant Design Select 风格，不引入额外视觉元素
 */
import { useEffect, useState, useCallback, useMemo } from 'react'
import { Select, Table, Tag, Card, Space, Typography, Empty, Spin, Button, Modal, message, Tooltip } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { taskApi, taskLinkApi } from '../api/task'
import type { Task, TaskLink } from '../api/types'

const { Text, Link: AntLink } = Typography

// ========== HTML 转义工具 ==========
// 为什么需要手动转义：虽然 React JSX 默认转义字符串，
// 但 source 字段可能通过非 JSX 路径渲染（如 title 属性、Tooltip content），
// 统一转义确保所有展示路径都安全
function escapeHtml(str: string): string {
  if (!str) return ''
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
}

// source 字段安全渲染：先转义再映射为中文标签
// 为什么用函数而非直接 JSX：确保即使通过 Tooltip/title 属性也能安全展示
const SOURCE_LABELS: Record<string, string> = {
  auto: '自动',
  manual: '手动',
  live: '实时',
}
const SOURCE_COLORS: Record<string, string> = {
  auto: 'blue',
  manual: 'green',
  live: 'orange',
}

function SafeSourceTag({ source }: { source: string }) {
  // 双重防护：escapeHtml 转义 + React JSX 转义
  const escaped = escapeHtml(source)
  const label = SOURCE_LABELS[escaped] || escaped || '未知'
  const color = SOURCE_COLORS[escaped] || 'default'
  return <Tag color={color}>{label}</Tag>
}

// ========== 组件 Props ==========
interface TaskContentMenuProps {
  /** 可选：外部传入任务列表（如页面已加载），不传则内部加载 */
  tasks?: Task[]
  /** 可选：选中任务变化回调 */
  onTaskChange?: (taskId: string) => void
}

export default function TaskContentMenu({ tasks: externalTasks, onTaskChange }: TaskContentMenuProps) {
  const [tasks, setTasks] = useState<Task[]>(externalTasks ?? [])
  const [selectedTaskId, setSelectedTaskId] = useState<string>('')
  const [links, setLinks] = useState<TaskLink[]>([])
  const [linkType, setLinkType] = useState<'item' | 'seller'>('item')
  const [loading, setLoading] = useState(false)
  const [linksLoading, setLinksLoading] = useState(false)
  const [startAllLoading, setStartAllLoading] = useState(false)

  // 加载任务列表
  const loadTasks = useCallback(async () => {
    if (externalTasks) return
    setLoading(true)
    try {
      const data = await taskApi.list({ limit: 200 })
      setTasks(data.items)
    } catch {
      // 静默失败：菜单不影响主页面功能
    } finally {
      setLoading(false)
    }
  }, [externalTasks])

  useEffect(() => {
    loadTasks()
  }, [loadTasks])

  // 默认选中第一个任务
  // 为什么用 useEffect 而非 useState 初始值：tasks 是异步加载的，
  // 初始为空数组，需要在加载完成后自动选中第一个
  useEffect(() => {
    if (!selectedTaskId && tasks.length > 0) {
      setSelectedTaskId(tasks[0].id)
    }
  }, [tasks, selectedTaskId])

  // 加载选中任务的关联内容
  const loadLinks = useCallback(async () => {
    if (!selectedTaskId) return
    setLinksLoading(true)
    try {
      const data = await taskLinkApi.list(selectedTaskId, {
        type: linkType,
        limit: 20,
      })
      setLinks(data.items)
    } catch {
      setLinks([])
    } finally {
      setLinksLoading(false)
    }
  }, [selectedTaskId, linkType])

  useEffect(() => {
    if (selectedTaskId) {
      loadLinks()
      onTaskChange?.(selectedTaskId)
    }
  }, [selectedTaskId, linkType, loadLinks, onTaskChange])

  // 一键启动所有任务
  // 为什么用 batchControl 而非逐个 control：减少网络请求，
  // 与 TaskList 批量操作保持一致；后端 batch-control 端点支持 restart 动作
  const handleStartAll = useCallback(() => {
    // 过滤出非 running 状态的任务，避免重复启动
    const toStart = tasks.filter((t) => t.status !== 'running')
    const skipped = tasks.length - toStart.length

    if (toStart.length === 0) {
      message.info(skipped > 0 ? `所有 ${skipped} 个任务已在运行中` : '暂无任务可启动')
      return
    }

    const taskNames = toStart.map((t) => t.name || t.keyword).slice(0, 5).join('、')
    const more = toStart.length > 5 ? ` 等 ${toStart.length} 个任务` : ''

    Modal.confirm({
      title: '确认启动所有任务？',
      content: `将启动 ${toStart.length} 个任务（${taskNames}${more}）` +
        (skipped > 0 ? `，跳过 ${skipped} 个已运行任务` : ''),
      okText: '启动',
      cancelText: '取消',
      onOk: async () => {
        setStartAllLoading(true)
        try {
          await taskApi.batchControl(toStart.map((t) => t.id), 'restart')
          message.success(`已启动 ${toStart.length} 个任务` + (skipped > 0 ? `，跳过 ${skipped} 个` : ''))
          // 刷新任务列表以同步状态
          await loadTasks()
        } catch (err: unknown) {
          // 部分失败时展示错误详情
          const detail = err instanceof Error ? err.message : String(err)
          message.error(`启动失败: ${detail.slice(0, 100)}`)
        } finally {
          setStartAllLoading(false)
        }
      },
    })
  }, [tasks, loadTasks])

  // 商品列定义
  const itemColumns: ColumnsType<TaskLink> = useMemo(() => [
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 80,
      render: (source: string) => <SafeSourceTag source={source} />,
    },
    {
      title: '商品信息',
      key: 'title',
      render: (_, record) => {
        const d = record.display
        const url = d.url || `https://www.goofish.com/item?id=${record.link_key}`
        return (
          <Space>
            {d.thumb_url && (
              <img
                src={d.thumb_url}
                alt=""
                style={{ width: 40, height: 40, borderRadius: 4, objectFit: 'cover' }}
              />
            )}
            <div>
              <AntLink href={url} target="_blank" rel="noopener noreferrer">
                {d.title || record.link_key}
              </AntLink>
              {d.region && <div><Text type="secondary" style={{ fontSize: 12 }}>{d.region}</Text></div>}
            </div>
          </Space>
        )
      },
    },
    {
      title: '价格',
      dataIndex: ['display', 'price'],
      key: 'price',
      width: 100,
      render: (price: number) => price ? `¥${price}` : '-',
    },
    {
      title: '卖家',
      key: 'seller',
      width: 120,
      render: (_, record) => record.display.seller_nick || '-',
    },
    {
      title: '状态',
      key: 'status',
      width: 80,
      render: (_, record) =>
        record.display.is_sold
          ? <Tag color="default">已售</Tag>
          : <Tag color="green">在售</Tag>,
    },
  ], [])

  // 卖家列定义
  const sellerColumns: ColumnsType<TaskLink> = useMemo(() => [
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 80,
      render: (source: string) => <SafeSourceTag source={source} />,
    },
    {
      title: '卖家',
      key: 'seller',
      render: (_, record) => record.display.seller_nick || record.link_key,
    },
    {
      title: '地区',
      key: 'region',
      width: 100,
      render: (_, record) => record.display.region || '-',
    },
  ], [])

  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* 任务下拉选择器 + 一键启动按钮 */}
        <Space>
          <Text strong>任务：</Text>
          <Select
            value={selectedTaskId || undefined}
            onChange={(v) => { setSelectedTaskId(v); setLinks([]) }}
            placeholder="选择任务"
            style={{ minWidth: 280 }}
            showSearch
            optionFilterProp="label"
            loading={loading}
            notFoundContent={loading ? <Spin size="small" /> : '暂无任务'}
            options={tasks.map((t) => ({
              value: t.id,
              label: `${t.name || t.keyword}（${t.keyword}）`,
            }))}
          />
          {/* 商品/卖家切换 */}
          <Select
            value={linkType}
            onChange={(v) => setLinkType(v)}
            style={{ width: 100 }}
            options={[
              { value: 'item', label: '商品' },
              { value: 'seller', label: '卖家' },
            ]}
          />
          {/* 一键启动所有任务 */}
          <Tooltip title="一键启动所有任务">
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={startAllLoading}
              onClick={handleStartAll}
              disabled={tasks.length === 0}
            >
              全部启动
            </Button>
          </Tooltip>
        </Space>

        {/* 关联内容列表 */}
        {selectedTaskId ? (
          <Table<TaskLink>
            dataSource={links}
            columns={linkType === 'item' ? itemColumns : sellerColumns}
            rowKey="link_id"
            size="small"
            loading={linksLoading}
            pagination={{ pageSize: 10, size: 'small' }}
            locale={{ emptyText: <Empty description="暂无关联内容" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          />
        ) : (
          <Empty description="请选择任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Space>
    </Card>
  )
}
