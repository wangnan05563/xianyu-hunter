import { useState, useEffect, useCallback } from 'react'
import { formatDateTime } from '../../../utils/timeFormat'
import {
  Card, Table, Input, Tag, Space, Typography,
  message, Statistic, Row, Col, Modal,
} from 'antd'
import {
  ReloadOutlined, CameraOutlined, RollbackOutlined, DeleteOutlined,
  FileSearchOutlined,
} from '@ant-design/icons'
import { vectorAdminApi } from '../../../api/vectorAdmin'
import type { VectorStatus, VectorSnapshot, VectorAuditLog } from '../../../api/vectorAdmin'
import { TipButton } from '@/components/TipButton'
import { confirmDanger, COUNT_UNKNOWN } from '@/components/DangerSummary'

// 向量库维护面板：状态总览 + 快照管理 + 数据清理 + 审计日志
// 危险操作（恢复/删除快照/清空/按来源删除）统一走 confirmDanger 四要素文案
// （T02577 D-9 裁决：只保留本面板一套入口，确认强度对齐 C 档），
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

  const handleRestoreSnapshot = async (snapshot: VectorSnapshot) => {
    const ok = await confirmDanger({
      title: `从快照 ${snapshot.id} 恢复？`,
      action: '用该快照的内容覆盖当前向量集合',
      scope: `集合 ${status?.collection_name ?? '（未知）'} 的全部片段；快照文件本身保留`,
      count: status?.chunk_count ?? null,
      recovery: `被覆盖后再写入的新片段无法找回；需要时可用同一快照 ${snapshot.id} 再次恢复`,
    })
    if (!ok) return
    try {
      await vectorAdminApi.restoreSnapshot(snapshot.id)
      message.success(`已从快照 ${snapshot.id} 恢复`)
      loadAll()
    } catch {
      message.error('恢复失败')
    }
  }

  const handleDeleteSnapshot = async (snapshot: VectorSnapshot) => {
    const ok = await confirmDanger({
      title: `删除快照 ${snapshot.id}？`,
      action: '删除该快照文件',
      scope: '仅删除快照文件，不影响当前集合数据',
      count: 1,
      recovery: '快照文件删除后不可恢复（当前集合数据不受影响）',
    })
    if (!ok) return
    try {
      await vectorAdminApi.deleteSnapshot(snapshot.id)
      message.success(`快照 ${snapshot.id} 已删除`)
      loadAll()
    } catch {
      message.error('删除快照失败')
    }
  }

  const handleCleanupAll = async () => {
    const ok = await confirmDanger({
      title: `清空集合 ${status?.collection_name ?? ''}？`,
      action: '删除集合内全部片段',
      scope: `集合 ${status?.collection_name ?? '（未知）'} 的全部向量片段；快照与原始文档不受影响`,
      count: status?.chunk_count ?? null,
      recovery: '不可恢复；建议先创建快照，之后可从快照恢复',
    })
    if (!ok) return
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
    const sourceFile = cleanupSourceFile.trim()
    const ok = await confirmDanger({
      title: '按来源文件删除片段？',
      action: `删除来源为 ${sourceFile} 的全部片段`,
      scope: `source_file=${sourceFile} 的片段；其他来源与原始文档不受影响`,
      count: COUNT_UNKNOWN,
      recovery: '不可恢复；需要时只能重新导入该来源文档',
    })
    if (!ok) return
    try {
      const res = await vectorAdminApi.cleanupBySource(sourceFile)
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
        extra={<TipButton tip="刷新向量库状态、快照与审计日志" icon={<ReloadOutlined />} onClick={loadAll} loading={loading}>刷新</TipButton>}
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
          <TipButton
            tip="为当前集合创建一份快照备份"
            type="primary"
            icon={<CameraOutlined />}
            onClick={() => setSnapshotModalOpen(true)}
          >
            创建快照
          </TipButton>
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
            { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (v: string) => formatDateTime(v) },
            {
              title: '操作',
              key: 'actions',
              render: (_: unknown, record: VectorSnapshot) => (
                <Space>
                  <TipButton
                    size="small"
                    tip="用该快照覆盖当前集合数据"
                    icon={<RollbackOutlined />}
                    onClick={() => handleRestoreSnapshot(record)}
                  >
                    恢复
                  </TipButton>
                  <TipButton
                    size="small"
                    tip="删除该快照文件，不影响当前集合"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleDeleteSnapshot(record)}
                  >
                    删除
                  </TipButton>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      {/* 数据清理 */}
      <Card title="数据清理" extra={<Typography.Text type="secondary">危险操作，需二次确认</Typography.Text>}>
        <Space>
          <TipButton tip="删除集合内全部片段（危险操作）" danger icon={<DeleteOutlined />} onClick={handleCleanupAll}>清空集合</TipButton>
          <TipButton tip="按来源文件删除其全部片段" icon={<FileSearchOutlined />} onClick={() => setCleanupSourceOpen(true)}>
            按来源文件删除
          </TipButton>
        </Space>
      </Card>

      {/* 审计日志 */}
      <Card title="维护审计日志" extra={<TipButton tip="刷新向量库维护审计日志" icon={<ReloadOutlined />} onClick={loadAll}>刷新</TipButton>}>
        <Table
          size="small"
          rowKey="id"
          dataSource={auditLogs}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: '动作', dataIndex: 'action', key: 'action', render: (v: string) => <Tag>{v}</Tag> },
            { title: '目标', dataIndex: 'target', key: 'target', ellipsis: true },
            { title: '来源', dataIndex: 'source', key: 'source' },
            { title: '时间', dataIndex: 'created_at', key: 'created_at', render: (v: string) => formatDateTime(v) },
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
