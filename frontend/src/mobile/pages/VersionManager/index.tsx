// frontend/src/mobile/pages/VersionManager/index.tsx
// 移动端配置版本：备份列表 + 回滚 + 导出/导入
// 关键简化：去掉桌面端 diff 预览，保留列表 + 回滚 + 导出
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Tag, Spin, App, Button, Space, Empty, theme, Popconfirm, Alert,
} from 'antd'
import { ReloadOutlined, RollbackOutlined, DownloadOutlined, UploadOutlined } from '@ant-design/icons'
import { configApi } from '../../../api/config'
import type { BackupItem } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'

const tsFmt = (iso: string): string => new Date(iso).toLocaleString('zh-CN')

export default function MobileVersionManager() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [backups, setBackups] = useState<BackupItem[]>([])
  const [version, setVersion] = useState<number>(0)
  const [loading, setLoading] = useState(true)
  const [rollingBack, setRollingBack] = useState(false)

  const load = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const [ver, bk] = await Promise.all([
        configApi.getVersion(),
        configApi.listBackups(),
      ])
      setVersion(ver.version)
      setBackups(bk.backups)
    } catch (e) {
      message.error(extractApiError(e, '加载失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void load() }, [load])

  // 回滚到最近的备份
  const rollback = async (): Promise<void> => {
    setRollingBack(true)
    try {
      await configApi.rollback()
      message.success('已回滚到上一个版本')
      void load()
    } catch (e) {
      message.error(extractApiError(e, '回滚失败'), 3)
    } finally {
      setRollingBack(false)
    }
  }

  // 恢复指定备份
  const restore = async (filename: string): Promise<void> => {
    try {
      await configApi.restoreBackup(filename)
      message.success(`已恢复 ${filename}`)
      void load()
    } catch (e) {
      message.error(extractApiError(e, '恢复失败'), 3)
    }
  }

  // 导出配置为 JSON 下载
  const exportConfig = async (): Promise<void> => {
    try {
      const data = await configApi.export()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `config-backup-${new Date().toISOString().slice(0, 10)}.json`
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      requestAnimationFrame(() => {
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      })
      message.success('已导出')
    } catch (e) {
      message.error(extractApiError(e, '导出失败'), 3)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <div>
      <Card size="small" style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary }}>当前版本</div>
            <div style={{ fontSize: 24, fontWeight: 600, color: '#E20613' }}>v{version}</div>
          </div>
          <Space direction="vertical" size={6}>
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={exportConfig}
            >
              导出
            </Button>
            <Popconfirm
              title="确认回滚？"
              description="将恢复到上一个配置版本，当前配置会被覆盖"
              okText="确认"
              okButtonProps={{ danger: true }}
              cancelText="取消"
              onConfirm={rollback}
            >
              <Button size="small" danger icon={<RollbackOutlined />} loading={rollingBack}>
                回滚
              </Button>
            </Popconfirm>
          </Space>
        </div>
      </Card>

      <Alert
        type="warning"
        showIcon
        message="回滚操作不可撤销"
        description="回滚后当前配置将被覆盖。建议先导出当前配置。"
        style={{ marginBottom: 12, fontSize: 12 }}
      />

      <Card
        size="small"
        title={`备份列表 (${backups.length})`}
        extra={
          <Button size="small" type="text" icon={<ReloadOutlined />} onClick={() => void load()}>
            刷新
          </Button>
        }
      >
        {backups.length === 0 ? (
          <Empty description="暂无备份" imageStyle={{ height: 60 }} />
        ) : (
          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            {backups.map((bk) => (
              <div
                key={bk.filename}
                style={{
                  padding: '8px 0',
                  borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Tag color="blue">v{bk.mtime}</Tag>
                  <span style={{ fontSize: 11, color: themeToken.colorTextTertiary }}>
                    {(bk.size / 1024).toFixed(1)} KB
                  </span>
                </div>
                <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
                  {tsFmt(bk.ts)}
                </div>
                <Button
                  size="small"
                  type="link"
                  onClick={() => void restore(bk.filename)}
                  style={{ padding: 0, fontSize: 12 }}
                >
                  恢复此版本
                </Button>
              </div>
            ))}
          </Space>
        )}
      </Card>
    </div>
  )
}
