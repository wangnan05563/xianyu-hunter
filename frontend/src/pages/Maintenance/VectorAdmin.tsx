import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Drawer,
  Input,
  Modal,
  Row,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  message,
} from 'antd'
import {
  DatabaseOutlined,
  DeleteOutlined,
  ExclamationCircleOutlined,
  FileSearchOutlined,
  ReloadOutlined,
  RollbackOutlined,
  CameraOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import {
  vectorAdminApi,
  CONFIRM_TOKEN,
  type VectorStatus,
  type VectorSnapshot,
  type VectorAuditLog,
} from '../../api/vectorAdmin'

export default function VectorAdmin() {
  const [status, setStatus] = useState<VectorStatus | null>(null)
  const [snapshots, setSnapshots] = useState<VectorSnapshot[]>([])
  const [loading, setLoading] = useState(false)
  const [auditLogs, setAuditLogs] = useState<VectorAuditLog[]>([])
  const [auditDrawerOpen, setAuditDrawerOpen] = useState(false)
  // 创建快照弹窗
  const [createOpen, setCreateOpen] = useState(false)
  const [snapshotLabel, setSnapshotLabel] = useState('')
  // 按来源删除
  const [sourceFile, setSourceFile] = useState('')

  const loadAll = async () => {
    setLoading(true)
    try {
      const [s, snaps] = await Promise.all([
        vectorAdminApi.getStatus(),
        vectorAdminApi.listSnapshots(),
      ])
      setStatus(s)
      setSnapshots(snaps.items)
    } catch (e: any) {
      // 403 表示 chatbot 未启用，给用户明确提示
      const code = e?.response?.data?.detail?.code
      if (code === 'CHATBOT_DISABLED') {
        message.error('智能客服未启用，向量库不可用')
      } else {
        message.error(`加载失败: ${e?.response?.data?.detail || e?.message}`)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 创建快照
  const handleCreate = async () => {
    try {
      const result = await vectorAdminApi.createSnapshot(snapshotLabel || undefined)
      message.success(`快照已创建: ${result.snapshot_id}`)
      setCreateOpen(false)
      setSnapshotLabel('')
      loadAll()
    } catch (e: any) {
      message.error(`创建失败: ${e?.response?.data?.detail || e?.message}`)
    }
  }

  // 通用危险操作二次确认（输入 CONFIRM_TOKEN）
  const openDangerConfirm = (
    title: string,
    content: React.ReactNode,
    onOk: () => Promise<void>,
  ) => {
    let tokenValue = ''
    const modal = Modal.confirm({
      title,
      icon: <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />,
      content: (
        <div>
          {content}
          <p style={{ marginTop: 12 }}>请输入 <b>{CONFIRM_TOKEN}</b> 以确认（区分大小写）：</p>
          <Input.Password
            placeholder={CONFIRM_TOKEN}
            onChange={(e) => {
              tokenValue = e.target.value
              modal.update((prev) => ({
                ...prev,
                okButtonProps: { danger: true, disabled: tokenValue !== CONFIRM_TOKEN },
              }))
            }}
          />
        </div>
      ),
      okText: '确认',
      cancelText: '取消',
      okButtonProps: { danger: true, disabled: true },
      onOk: async () => {
        await onOk()
      },
    })
  }

  // 从快照恢复
  const handleRestore = (snapshot: VectorSnapshot) => {
    openDangerConfirm(
      `从快照恢复？`,
      <div>
        <p>将用快照 <b>{snapshot.id}</b> 的内容覆盖当前集合，当前数据将丢失。</p>
        <p>快照大小：{snapshot.size_display}　创建时间：{snapshot.created_at}</p>
      </div>,
      async () => {
        try {
          await vectorAdminApi.restoreSnapshot(snapshot.id)
          message.success('恢复成功')
          loadAll()
        } catch (e: any) {
          message.error(`恢复失败: ${e?.response?.data?.detail || e?.message}`)
        }
      },
    )
  }

  // 删除快照
  const handleDeleteSnapshot = (snapshot: VectorSnapshot) => {
    openDangerConfirm(
      `删除快照？`,
      <p>将删除快照 <b>{snapshot.id}</b>（{snapshot.size_display}），此操作不可恢复。</p>,
      async () => {
        try {
          await vectorAdminApi.deleteSnapshot(snapshot.id)
          message.success('已删除')
          loadAll()
        } catch (e: any) {
          message.error(`删除失败: ${e?.response?.data?.detail || e?.message}`)
        }
      },
    )
  }

  // 清空集合
  const handleCleanupAll = () => {
    openDangerConfirm(
      `清空向量集合？`,
      <p>将删除集合 <b>{status?.collection_name}</b> 中的所有片段（{status?.chunk_count} 条），
        操作不可恢复。建议先创建快照备份。</p>,
      async () => {
        try {
          const result = await vectorAdminApi.cleanupAll()
          message.success(`已清空 ${result.cleared} 条片段`)
          loadAll()
        } catch (e: any) {
          message.error(`清空失败: ${e?.response?.data?.detail || e?.message}`)
        }
      },
    )
  }

  // 按来源删除
  const handleCleanupBySource = () => {
    if (!sourceFile.trim()) {
      message.warning('请输入 source_file')
      return
    }
    openDangerConfirm(
      `按来源删除片段？`,
      <p>将删除 source_file=<b>{sourceFile.trim()}</b> 的所有片段，操作不可恢复。</p>,
      async () => {
        try {
          const result = await vectorAdminApi.cleanupBySource(sourceFile.trim())
          message.success(`已删除 ${result.deleted} 条片段`)
          setSourceFile('')
          loadAll()
        } catch (e: any) {
          message.error(`删除失败: ${e?.response?.data?.detail || e?.message}`)
        }
      },
    )
  }

  // 审计日志
  const loadAuditLogs = async () => {
    try {
      const data = await vectorAdminApi.getAuditLog(200)
      setAuditLogs(data.items)
      setAuditDrawerOpen(true)
    } catch (e: any) {
      message.error(`加载审计日志失败: ${e?.response?.data?.detail || e?.message}`)
    }
  }

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h2 style={{ margin: 0 }}>向量数据库维护</h2>
          <p style={{ margin: 0, color: 'var(--xh-text-tertiary)', fontSize: 13 }}>
            ChromaDB 运维 · 快照备份与恢复 · 数据清理 · 危险操作需输入 {CONFIRM_TOKEN}
          </p>
        </div>
        <Space>
          <Button icon={<FileTextOutlined />} onClick={loadAuditLogs}>审计日志</Button>
          <Button icon={<ReloadOutlined />} onClick={loadAll} loading={loading}>刷新</Button>
        </Space>
      </div>

      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="数据操作有风险"
        description="恢复和清空操作不可撤销，建议先创建快照备份。所有操作均记录审计日志。"
      />

      {/* 状态卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="片段数"
              value={status?.chunk_count ?? '-'}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="数据大小"
              value={status?.data_size_display ?? '-'}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="快照数"
              value={status?.snapshot_count ?? '-'}
              suffix={status?.last_snapshot_at ? `（最近 ${status.last_snapshot_at.slice(5, 16)}）` : ''}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="集合名"
              value={status?.collection_name ?? '-'}
            />
            <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              {status?.persist_path}
            </div>
          </Card>
        </Col>
      </Row>

      <Tabs
        items={[
          {
            key: 'snapshots',
            label: '备份与恢复',
            children: (
              <>
                <Space style={{ marginBottom: 12 }}>
                  <Button
                    type="primary"
                    icon={<CameraOutlined />}
                    onClick={() => setCreateOpen(true)}
                  >
                    创建快照
                  </Button>
                </Space>
                <Table
                  rowKey="id"
                  size="small"
                  dataSource={snapshots}
                  loading={loading}
                  pagination={{ pageSize: 15, showSizeChanger: false }}
                  columns={[
                    { title: '快照 ID', dataIndex: 'id', key: 'id', ellipsis: true },
                    {
                      title: '类型',
                      dataIndex: 'is_manual',
                      key: 'is_manual',
                      width: 80,
                      render: (v: boolean) => (
                        <Tag color={v ? 'orange' : 'blue'}>{v ? '手动' : '自动'}</Tag>
                      ),
                    },
                    { title: '大小', dataIndex: 'size_display', key: 'size_display', width: 100 },
                    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
                    {
                      title: '操作',
                      key: 'actions',
                      width: 160,
                      render: (_: unknown, record: VectorSnapshot) => (
                        <Space size="small">
                          <Button
                            size="small"
                            type="link"
                            icon={<RollbackOutlined />}
                            onClick={() => handleRestore(record)}
                          >
                            恢复
                          </Button>
                          <Button
                            size="small"
                            type="link"
                            danger
                            icon={<DeleteOutlined />}
                            onClick={() => handleDeleteSnapshot(record)}
                          >
                            删除
                          </Button>
                        </Space>
                      ),
                    },
                  ]}
                />
              </>
            ),
          },
          {
            key: 'cleanup',
            label: '数据清理',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Card title="清空集合" size="small">
                  <p style={{ color: 'var(--xh-text-tertiary)', marginBottom: 12 }}>
                    删除集合中的所有片段。通常在知识库全量重建前调用。
                  </p>
                  <Button danger icon={<DeleteOutlined />} onClick={handleCleanupAll}>
                    清空集合
                  </Button>
                </Card>
                <Card title="按来源文件删除" size="small">
                  <p style={{ color: 'var(--xh-text-tertiary)', marginBottom: 12 }}>
                    删除指定 source_file 对应的所有片段（文档过期/错误导入场景）。
                  </p>
                  <Space>
                    <Input
                      placeholder="输入 source_file"
                      prefix={<FileSearchOutlined />}
                      value={sourceFile}
                      onChange={(e) => setSourceFile(e.target.value)}
                      style={{ width: 360 }}
                    />
                    <Button danger icon={<DeleteOutlined />} onClick={handleCleanupBySource}>
                      删除
                    </Button>
                  </Space>
                </Card>
              </Space>
            ),
          },
        ]}
      />

      {/* 创建快照弹窗 */}
      <Modal
        title="创建快照"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); setSnapshotLabel('') }}
        onOk={handleCreate}
        okText="创建"
        cancelText="取消"
      >
        <p style={{ marginBottom: 8 }}>可选：为快照添加备注标签（拼入目录名）</p>
        <Input
          placeholder="例如：pre-rebuild"
          value={snapshotLabel}
          onChange={(e) => setSnapshotLabel(e.target.value)}
        />
      </Modal>

      {/* 审计日志抽屉 */}
      <Drawer
        title="向量库维护审计日志"
        open={auditDrawerOpen}
        onClose={() => setAuditDrawerOpen(false)}
        width={720}
      >
        <Table
          rowKey="id"
          size="small"
          dataSource={auditLogs}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
            {
              title: '操作',
              dataIndex: 'action',
              key: 'action',
              width: 200,
              render: (v: string) => <Tag color="blue">{v}</Tag>,
            },
            { title: '目标', dataIndex: 'target', key: 'target', ellipsis: true },
            { title: '来源', dataIndex: 'source', key: 'source', width: 80 },
          ]}
        />
      </Drawer>
    </div>
  )
}
