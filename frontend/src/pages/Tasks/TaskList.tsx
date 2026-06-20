import { useEffect, useState } from 'react'
import { Table, Button, Space, Tag, Modal, message } from 'antd'
import { PlusOutlined, EditOutlined, PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { taskApi, Task } from '../../api'
import { STATUS_COLOR as statusColors } from '../../constants/statusColors'

const statusLabels: Record<string, string> = {
  running: '运行中',
  paused: '已暂停',
  stopped: '已停止',
  deleted: '已删除',
}

const modeLabels: Record<string, string> = {
  auto: '全自动',
  semi_auto: '半自动',
  confirm: '需确认',
  notify: '仅通知',
}

export default function TaskList() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('')

  const load = async () => {
    setLoading(true)
    try {
      const res = await taskApi.list({ status: statusFilter || undefined, limit: 20, offset: (page - 1) * 20 })
      setTasks(res.items || [])
      setTotal(res.total || 0)
    } catch {
      message.error('加载任务列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, statusFilter])

  const handleAction = async (id: string, action: 'start' | 'pause' | 'resume' | 'stop' | 'delete') => {
    try {
      if (action === 'delete') {
        Modal.confirm({
          title: '确认删除任务？',
          content: '删除后不可恢复，关联数据将一并清除。',
          okType: 'danger',
          onOk: async () => {
            await taskApi.delete(id)
            message.success('已删除')
            load()
          },
        })
        return
      }
      await taskApi[action](id)
      message.success('操作成功')
      load()
    } catch {
      message.error('操作失败')
    }
  }

  const columns = [
    {
      title: '任务名',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Task) => (
        <a onClick={() => navigate(`/tasks/${record.id}/edit`)}>{text}</a>
      ),
    },
    { title: '关键词', dataIndex: 'keyword', key: 'keyword' },
    {
      title: '价格区间',
      key: 'price',
      render: (_: unknown, record: Task) => {
        const min = record.min_price ?? '-'
        const max = record.max_price ?? '-'
        return `¥${min} ~ ¥${max}`
      },
    },
    {
      title: '模式',
      dataIndex: 'mode',
      key: 'mode',
      render: (mode: string) => <Tag>{modeLabels[mode] || mode}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={statusColors[status]}>{statusLabels[status] || status}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Task) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => navigate(`/tasks/${record.id}/edit`)}>
            编辑
          </Button>
          {record.status === 'running' ? (
            <Button size="small" icon={<PauseCircleOutlined />} onClick={() => handleAction(record.id, 'pause')}>
              暂停
            </Button>
          ) : (
            <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleAction(record.id, 'start')}>
              启动
            </Button>
          )}
          <Button size="small" danger onClick={() => handleAction(record.id, 'delete')}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>任务管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/tasks/new')}>
          新增任务（向导）
        </Button>
      </div>

      <Space style={{ marginBottom: 16 }}>
        <span>状态筛选：</span>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setPage(1)
          }}
          style={{ padding: '4px 8px' }}
        >
          <option value="">全部</option>
          <option value="running">运行中</option>
          <option value="paused">已暂停</option>
          <option value="stopped">已停止</option>
        </select>
      </Space>

      <Table
        columns={columns}
        dataSource={tasks}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: setPage,
          showTotal: (t) => `共 ${t} 条`,
        }}
      />
    </div>
  )
}
