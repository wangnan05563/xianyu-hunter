import { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Button, Input, Tag, Space, Typography, Popconfirm,
  message, Statistic, Row, Col, Modal,
} from 'antd'
import {
  ReloadOutlined, CameraOutlined, RollbackOutlined, DeleteOutlined,
  WarningOutlined, FileSearchOutlined,
} from '@ant-design/icons'
import { vectorAdminApi } from '../../../api/vectorAdmin'
import type { VectorStatus, VectorSnapshot, VectorAuditLog } from '../../../api/vectorAdmin'

// 向量库维护面板：状态总览 + 快照管理 + 数据清理 + 审计日志
// 危险操作（恢复/删除快照/清空/按来源删除）通过 Popconfirm 二次确认，
// 后端要求 confirm_token=CONFIRM_DELETE，已封装在 vectorAdminApi 内部
export function VectorAdminPanel() {
  const [status, setStatus] = useState<VectorStatus | null>(null)
  const [snapshots, setSnapshots] = useState<VectorSnapshot[]>([])
  const [auditLogs, setAuditLogs] = useState<VectorAuditLog[]>([])
  const [loading, setLoading] = useState(false)

  // 创建快照 Modal
  const [snapshotModalOpen, setSnapshotModalOpen] = useState(false)
  const [snapshotLabel, setSnapshotLabel] = useState('')

  // 按来源删除 Modal
  const [cleanupSourceOpen, setCleanupSourceOpen] = useState(false)
  const [cleanupSourceFile, setCleanupSourceFile] = useState('')

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [st, snaps, logs] = await Promise.all([
        vectorAdminApi.getStatus(),
        vectorAdminApi.listSnapshots(),
        vectorAdminApi.getAuditLog(50),
      ])
      setStatus(st)
      setSnapshots(snaps.items)
      setAuditLogs(logs.items)
    } catch {
      message.error('加载向量库状态失败，请确认智能客服模块已启用')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const handleCreateSnapshot = async () => {
    try {
      const res = await vectorAdminApi.createSnapshot(snapshotLabel || undefined)
      message.success(`快照已创建：${res.snapshot_id}`)
      setSnapshotModalOpen(false)
      setSnapshotLabel('')
      loadAll()
    } catch {
      message.error('创建快照失败')
    }
  }

  const handleRestoreSnapshot = async (snapshotId: string) => {
    try {
      await vectorAdminApi.restoreSnapshot(snapshotId)
      message.success(`已从快照 ${snapshotId} 恢复`)
      loadAll()
    } catch {
      message.error('恢复失败')
    }
  }

  const handleDeleteSnapshot = async (snapshotId: string) => {
    try {
      await vectorAdminApi.deleteSnapshot(snapshotId)
      message.success(`快照 ${snapshotId} 已删除`)
      loadAll()
    } catch {
      message.error('删除快照失败')
    }
  }

  const handleCleanupAll = async () => {
    try {
      const res = await vectorAdminApi.cleanupAll()
      message.success(`已清空集合，删除 ${res.cleared} 条片段`)
      loadAll()
    } catch {
      message.error('清空集合失败')
    }
  }

  const handleCleanupBySource = async () => {
    if (!cleanupSourceFile.trim()) {
      message.warning('请输入来源文件路径')
      return
    }
    try {
      const res = await vectorAdminApi.cleanupBySource(cleanupSourceFile.trim())
      message.success(`已删除 ${res.deleted} 条片段`)
      setCleanupSourceOpen(false)
      setCleanupSourceFile('')
      loadAll()
    } catch {
      message.error('按来源删除失败')
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* 状态总览卡片 */}
      <Card
        title="向量库状态"
        extra={<Button icon={<ReloadOutlined />} onClick={loadAll} loading={loading}>刷新</Button>}
      >
        {status && (
          <Row gutter={[16, 16]}>
            <Col xs={12} sm={8} md={6}>
              <Statistic title="集合名" value={status.collection_name} valueStyle={{ fontSize: 14 }} />
            </Col>
            <Col xs={12} sm={8} md={6}>
              <Statistic title="片段数" value={status.chunk_count} />
            </Col>
            <Col xs={12} sm={8} md={6}>
              <Statistic title="数据大小" value={status.data_size_display} />
            </Col>
            <Col xs={12} sm={8} md={6}>
              <Statistic title="快照数" value={status.snapshot_count} />
            </Col>
            <Col xs={24} sm={8} md={12}>
              <Statistic title="持久化路径" value={status.persist_path} valueStyle={{ fontSize: 13, wordBreak: 'break-all' }} />
            </Col>
            <Col xs={24} sm={8} md={6}>
              <Statistic
                title="最近快照"
                value={status.last_snapshot_at || '无'}
                valueStyle={{ fontSize: 13 }}
              />
            </Col>
          </Row>
        )}
      </Card>

      {/* 快照管理 */}
      <Card title="快照管理">
        <Space style={{ marginBottom: 16 }}>
          <Button
            type="primary"
            icon={<CameraOutlined />}
            onClick={() => setSnapshotModalOpen(true)}
          >
            创建快照
          </Button>
        </Space>
        <Table
          size="small"
          rowKey="id"
          dataSource={snapshots}
          pagination={{ pageSize: 5 }}
          columns={[
            { title: '快照 ID', dataIndex: 'id', key: 'id', ellipsis: true },
            {
              title: '类型',
              dataIndex: 'is_manual',
              key: 'is_manual',
              render: (m: boolean) => <Tag color={m ? 'blue' : 'default'}>{m ? '手动' : '自动'}</Tag>,
            },
            { title: '大小', dataIndex: 'size_display', key: 'size_display' },
            { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
            {
              title: '操作',
              key: 'actions',
              render: (_: unknown, record: VectorSnapshot) => (
                <Space>
                  <Popconfirm
                    title="恢复快照"
                    description="当前集合数据将被覆盖，确认恢复？"
                    icon={<WarningOutlined style={{ color: '#ff4d4f' }} />}
                    onConfirm={() => handleRestoreSnapshot(record.id)}
                    okText="恢复"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button size="small" icon={<RollbackOutlined />}>恢复</Button>
                  </Popconfirm>
                  <Popconfirm
                    title="删除快照"
                    description="仅删除快照文件，不影响当前集合数据"
                    icon={<WarningOutlined style={{ color: '#ff4d4f' }} />}
                    onConfirm={() => handleDeleteSnapshot(record.id)}
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      {/* 数据清理 */}
      <Card title="数据清理" extra={<Typography.Text type="secondary">危险操作，需二次确认</Typography.Text>}>
        <Space>
          <Popconfirm
            title="清空集合"
            description="将删除所有片段，通常在全量重建前调用。确认清空？"
            icon={<WarningOutlined style={{ color: '#ff4d4f' }} />}
            onConfirm={handleCleanupAll}
            okText="清空"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button danger icon={<DeleteOutlined />}>清空集合</Button>
          </Popconfirm>
          <Button icon={<FileSearchOutlined />} onClick={() => setCleanupSourceOpen(true)}>
            按来源文件删除
          </Button>
        </Space>
      </Card>

      {/* 审计日志 */}
      <Card title="维护审计日志" extra={<Button icon={<ReloadOutlined />} onClick={loadAll}>刷新</Button>}>
        <Table
          size="small"
          rowKey="id"
          dataSource={auditLogs}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: '动作', dataIndex: 'action', key: 'action', render: (v: string) => <Tag>{v}</Tag> },
            { title: '目标', dataIndex: 'target', key: 'target', ellipsis: true },
            { title: '来源', dataIndex: 'source', key: 'source' },
            { title: '时间', dataIndex: 'created_at', key: 'created_at' },
          ]}
        />
      </Card>

      {/* 创建快照 Modal */}
      <Modal
        title="创建快照"
        open={snapshotModalOpen}
        onOk={handleCreateSnapshot}
        onCancel={() => { setSnapshotModalOpen(false); setSnapshotLabel('') }}
      >
        <Typography.Paragraph type="secondary">
          快照将复制当前集合数据到 <code>data/chromadb/snapshots/manual_{'{timestamp}'}[_{'{label}'}]</code>，可用于后续恢复。
        </Typography.Paragraph>
        <Input
          placeholder="备注（可选，会拼入快照目录名）"
          value={snapshotLabel}
          onChange={(e) => setSnapshotLabel(e.target.value)}
          maxLength={50}
        />
      </Modal>

      {/* 按来源删除 Modal */}
      <Modal
        title="按来源文件删除片段"
        open={cleanupSourceOpen}
        onOk={handleCleanupBySource}
        onCancel={() => { setCleanupSourceOpen(false); setCleanupSourceFile('') }}
      >
        <Typography.Paragraph type="secondary">
          删除指定来源文件对应的所有片段。用于文档过期或错误导入场景。
        </Typography.Paragraph>
        <Input
          placeholder="如：docs/chatbot-详细设计.md"
          value={cleanupSourceFile}
          onChange={(e) => setCleanupSourceFile(e.target.value)}
        />
      </Modal>
    </Space>
  )
}
