import { useEffect, useState } from 'react'
import {
  Card,
  Timeline,
  Button,
  Space,
  message,
  Modal,
  Empty,
  Tag,
  Statistic,
  Row,
  Col,
  Upload,
  Input,
  Pagination,
} from 'antd'
import {
  HistoryOutlined,
  RollbackOutlined,
  DownloadOutlined,
  UploadOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  ShareAltOutlined,
  CopyOutlined,
} from '@ant-design/icons'
import { configApi, aboutApi, BackupItem, AboutInfo } from '../../api'

const PAGE_SIZE = 10

export default function VersionManager() {
  const [backups, setBackups] = useState<BackupItem[]>([])
  // 系统版本号来自 /api/about（_build_info.py 写入的 __version__），
  // 不再用 /api/config/version 的备份数计数——后者会因 BACKUP_KEEP=10 上限卡在 v10
  const [buildInfo, setBuildInfo] = useState<AboutInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedBackup, setSelectedBackup] = useState<BackupItem | null>(null)
  const [diffModalVisible, setDiffModalVisible] = useState(false)
  const [page, setPage] = useState(1)
  // 分享配置
  const [shareModalOpen, setShareModalOpen] = useState(false)
  const [shareText, setShareText] = useState('')
  const [shareLoading, setShareLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [backupRes, aboutRes] = await Promise.all([
        configApi.listBackups(),
        aboutApi.get(),
      ])
      setBackups(backupRes.backups || [])
      setBuildInfo(aboutRes)
    } catch {
      message.error('加载版本信息失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleRollback = () => {
    Modal.confirm({
      title: '确认一键回滚？',
      content: '将回滚到最近的备份版本。回滚前会自动备份当前配置（安全网）。',
      okText: '确认回滚',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await configApi.rollback()
          message.success('已回滚到上一版本')
          load()
        } catch {
          message.error('回滚失败')
        }
      },
    })
  }

  const handleRestore = (backup: BackupItem) => {
    Modal.confirm({
      title: `从备份恢复？`,
      content: `将从 ${backup.ts} 的备份恢复配置。`,
      okText: '确认恢复',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await configApi.restoreBackup(backup.filename)
          message.success(`已从 ${backup.ts} 恢复`)
          load()
        } catch {
          message.error('恢复失败')
        }
      },
    })
  }

  const handleExport = async () => {
    try {
      const data = await configApi.export()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `xianyu_hunter_config_${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      message.success('配置已导出')
    } catch {
      message.error('导出失败')
    }
  }

  // 需要脱敏的敏感字段列表
  const SENSITIVE_KEYS = ['serverchan_send_key', 'pushplus_token', 'bark_server', 'bark_key']

  const handleShare = async () => {
    setShareLoading(true)
    try {
      const data = await configApi.export()
      // 深拷贝后对敏感字段脱敏
      const sanitized = JSON.parse(JSON.stringify(data))
      for (const key of SENSITIVE_KEYS) {
        if (sanitized[key] != null && sanitized[key] !== '') {
          sanitized[key] = '***'
        }
      }
      setShareText(JSON.stringify(sanitized, null, 2))
      setShareModalOpen(true)
    } catch {
      message.error('获取配置失败')
    } finally {
      setShareLoading(false)
    }
  }

  const handleCopyShare = async () => {
    try {
      await navigator.clipboard.writeText(shareText)
      message.success('已复制到剪贴板')
    } catch {
      message.error('复制失败，请手动选择复制')
    }
  }

  // 内部处理函数：核心逻辑封装在此，仅返回 void
  // handleImport 作为 antd Upload 的 beforeUpload 钩子，统一返回 false 阻止自动上传
  // 这种"内部函数处理 + 外部包装返回 false"的结构避免所有 return 返回同一值（S3516）
  const processImport = async (file: File) => {
    const text = await file.text()
    const data = JSON.parse(text)
    if (data.schema !== 'xianyu_hunter.config/v1') {
      message.error('无效的配置文件格式')
      return
    }

    // 先预览
    const previewRes = await configApi.import(data.config, false)
    Modal.confirm({
        title: '导入配置确认',
        content: (
          <div>
            <p>将改动 <strong>{previewRes.diff_count}</strong> 处配置项：</p>
            <div style={{ maxHeight: 300, overflow: 'auto', background: 'var(--xh-bg-spotlight)', padding: 12, fontSize: 12 }}>
              {previewRes.diffs?.slice(0, 20).map((d: { path: string; op: string; old: string; new: string }, i: number) => (
                <div key={i} style={{ marginBottom: 4 }}>
                  <Tag color={(() => {
                    // op 配色：add=绿 remove=红 其他=橙
                    if (d.op === 'add') return 'green'
                    if (d.op === 'remove') return 'red'
                    return 'orange'
                  })()}>
                    {d.op}
                  </Tag>
                  <code>{d.path}</code>
                  {d.old && <span style={{ color: 'var(--xh-text-tertiary)' }}> {d.old} →</span>}
                  <span style={{ color: '#1677ff' }}> {d.new}</span>
                </div>
              ))}
              {previewRes.diff_count > 20 && <p>... 还有 {previewRes.diff_count - 20} 处改动</p>}
            </div>
          </div>
        ),
        okText: '确认导入',
        okType: 'danger',
        cancelText: '取消',
        width: 600,
        onOk: async () => {
          try {
            await configApi.import(data.config, true)
            message.success('配置已导入')
            load()
          } catch {
            message.error('导入失败')
          }
        },
      })
  }

  const handleImport = async (file: File) => {
    // beforeUpload 钩子：内部处理函数返回 void，钩子统一返回 false 阻止 antd 自动上传
    await processImport(file).catch(() => {
      message.error('文件解析失败')
    })
    return false
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    return `${(bytes / 1024).toFixed(1)} KB`
  }

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>
          <HistoryOutlined /> 配置版本管理
        </h2>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
            刷新
          </Button>
          <Button icon={<DownloadOutlined />} onClick={handleExport}>
            导出配置
          </Button>
          <Button icon={<ShareAltOutlined />} onClick={handleShare} loading={shareLoading}>
            分享配置
          </Button>
          <Upload beforeUpload={handleImport} accept=".json" showUploadList={false}>
            <Button icon={<UploadOutlined />}>导入配置</Button>
          </Upload>
        </Space>
      </div>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="系统版本"
              value={buildInfo ? `v${buildInfo.version}` : '--'}
            />
            {/* 构建日期与 git SHA 作为辅助信息，便于用户判断版本新鲜度 */}
            {buildInfo && (
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                构建：{buildInfo.build_date} · {buildInfo.git_sha.slice(0, 7)}
              </div>
            )}
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="备份总数" value={backups.length} suffix="个" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="最近备份"
              value={backups[0] ? new Date(backups[0].ts).toLocaleString('zh-CN') : '无'}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Button
              type="primary"
              danger
              icon={<RollbackOutlined />}
              onClick={handleRollback}
              disabled={backups.length === 0}
              block
            >
              一键回滚
            </Button>
          </Card>
        </Col>
      </Row>

      {/* 版本时间线 */}
      <Card title="版本时间线" loading={loading}>
        {backups.length === 0 ? (
          <Empty description="暂无备份（保存配置后会自动创建备份）" />
        ) : (
          <>
            <Timeline
              items={backups.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((backup, index) => {
                const globalIndex = (page - 1) * PAGE_SIZE + index
                return {
                  color: globalIndex === 0 ? 'green' : 'gray',
                  dot: globalIndex === 0 ? <CheckCircleOutlined style={{ fontSize: 16, color: '#52c41a' }} /> : undefined,
                  children: (
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '8px 0',
                      }}
                    >
                      <div>
                        <Space>
                          <Tag color={globalIndex === 0 ? 'green' : 'default'}>
                            {globalIndex === 0 ? '最新' : `v${backups.length - globalIndex}`}
                          </Tag>
                          <strong>{new Date(backup.ts).toLocaleString('zh-CN')}</strong>
                          <span style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>{formatSize(backup.size)}</span>
                        </Space>
                      </div>
                      <Space>
                        <Button
                          size="small"
                          onClick={() => {
                            setSelectedBackup(backup)
                            setDiffModalVisible(true)
                          }}
                        >
                          查看详情
                        </Button>
                        <Button
                          size="small"
                          type="dashed"
                          icon={<RollbackOutlined />}
                          onClick={() => handleRestore(backup)}
                        >
                          恢复
                        </Button>
                      </Space>
                    </div>
                  ),
                }
              })}
            />
            {backups.length > PAGE_SIZE && (
              <div style={{ textAlign: 'right', marginTop: 16 }}>
                <Pagination
                  current={page}
                  pageSize={PAGE_SIZE}
                  total={backups.length}
                  showTotal={(t) => `共 ${t} 个备份`}
                  onChange={(p) => setPage(p)}
                  size="small"
                />
              </div>
            )}
          </>
        )}
      </Card>

      {/* 备份详情 Modal */}
      <Modal
        title="备份详情"
        open={diffModalVisible}
        onCancel={() => setDiffModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDiffModalVisible(false)}>
            关闭
          </Button>,
          <Button
            key="restore"
            type="primary"
            danger
            icon={<RollbackOutlined />}
            onClick={() => {
              if (selectedBackup) {
                handleRestore(selectedBackup)
                setDiffModalVisible(false)
              }
            }}
          >
            从此备份恢复
          </Button>,
        ]}
        width={600}
      >
        {selectedBackup && (
          <div>
            <Row gutter={16}>
              <Col span={12}>
                <Statistic title="文件名" value={selectedBackup.filename} valueStyle={{ fontSize: 12 }} />
              </Col>
              <Col span={12}>
                <Statistic title="备份时间" value={new Date(selectedBackup.ts).toLocaleString('zh-CN')} />
              </Col>
            </Row>
            <Row gutter={16} style={{ marginTop: 16 }}>
              <Col span={12}>
                <Statistic title="文件大小" value={formatSize(selectedBackup.size)} />
              </Col>
              <Col span={12}>
                <Statistic title="时间戳" value={selectedBackup.ts_raw} valueStyle={{ fontSize: 12 }} />
              </Col>
            </Row>
          </div>
        )}
      </Modal>

      {/* 分享配置 Modal */}
      <Modal
        title="分享配置（已脱敏）"
        open={shareModalOpen}
        onCancel={() => setShareModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setShareModalOpen(false)}>
            关闭
          </Button>,
          <Button key="copy" type="primary" icon={<CopyOutlined />} onClick={handleCopyShare}>
            复制到剪贴板
          </Button>,
        ]}
        width={700}
      >
        <div style={{ marginBottom: 8, fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
          敏感字段（serverchan_send_key、pushplus_token、bark_server、bark_key）已替换为 ***
        </div>
        <Input.TextArea
          value={shareText}
          readOnly
          autoSize={{ minRows: 10, maxRows: 25 }}
          style={{ fontFamily: 'monospace', fontSize: 12 }}
        />
      </Modal>
    </div>
  )
}
