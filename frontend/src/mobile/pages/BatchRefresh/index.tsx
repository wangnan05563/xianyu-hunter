// frontend/src/mobile/pages/BatchRefresh/index.tsx
// 移动端批量采集：状态卡 + 控制按钮 + 配置编辑 + 历史列表
// 设计要点：保留 trigger/pause/resume/stop 四控制 + interval_minutes 热更新
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Tag, Spin, App, Button, Space, theme, InputNumber, Switch, Descriptions,
} from 'antd'
import {
  PlayCircleOutlined, PauseCircleOutlined, StopOutlined, ReloadOutlined, CloudDownloadOutlined,
} from '@ant-design/icons'
import { batchRefreshApi } from '../../../api'
import type { BatchRefreshStatus, BatchRefreshChangeLogEntry } from '../../../api/batchRefresh'
import { extractApiError } from '../../../utils/apiError'

const STATUS_COLORS: Record<string, string> = {
  idle: 'default',
  running: 'processing',
  paused: 'warning',
  stopped: 'error',
  error: 'error',
}

export default function MobileBatchRefresh() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [status, setStatus] = useState<BatchRefreshStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [actioning, setActioning] = useState(false)
  const [editingInterval, setEditingInterval] = useState<number>(60)
  const [editingEnabled, setEditingEnabled] = useState<boolean>(true)
  const [savingConfig, setSavingConfig] = useState(false)

  const load = useCallback(async (): Promise<void> => {
    try {
      const data = await batchRefreshApi.getStatus()
      setStatus(data)
      setEditingInterval(data.interval_minutes)
      setEditingEnabled(data.enabled)
    } catch (e) {
      message.error(extractApiError(e, '加载状态失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void load() }, [load])

  // 执行操作（trigger/pause/resume/stop）
  const doAction = async (
    action: 'trigger' | 'pause' | 'resume' | 'stop',
  ): Promise<void> => {
    setActioning(true)
    try {
      await batchRefreshApi[action]()
      message.success(`${action} 已发送`)
      await load()
    } catch (e) {
      message.error(extractApiError(e, `${action} 失败`), 3)
    } finally {
      setActioning(false)
    }
  }

  // 保存配置热更新
  const saveConfig = async (): Promise<void> => {
    setSavingConfig(true)
    try {
      await batchRefreshApi.patchConfig({
        interval_minutes: editingInterval,
        enabled: editingEnabled,
      })
      message.success('配置已更新')
      await load()
    } catch (e) {
      message.error(extractApiError(e, '保存失败'), 3)
    } finally {
      setSavingConfig(false)
    }
  }

  if (loading && !status) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  const currentStatus = status?.status ?? 'idle'
  const isRunning = currentStatus === 'running'
  const isPaused = currentStatus === 'paused'

  return (
    <div>
      {/* 状态卡 */}
      <Card size="small" style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary }}>当前状态</div>
            <Tag
              color={STATUS_COLORS[currentStatus] || 'default'}
              style={{ fontSize: 14, padding: '4px 12px', marginTop: 4 }}
            >
              {currentStatus.toUpperCase()}
            </Tag>
          </div>
          <Button type="text" icon={<ReloadOutlined />} onClick={() => void load()} />
        </div>
              {/* 上次执行结果 */}
        {status?.last_result && (
          <Descriptions column={1} size="small" style={{ marginTop: 8 }}>
            <Descriptions.Item label="上次执行">
              {status.last_run_at ? new Date(status.last_run_at).toLocaleString('zh-CN') : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="成功/失败/跳过">
              {status.last_result.success} / {status.last_result.failed} / {status.last_result.skipped}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      {/* 控制按钮 */}
      <Card size="small" style={{ marginBottom: 10 }} title="操作">
        <Space size={6} style={{ width: '100%' }}>
          {!isRunning && !isPaused && (
            <Button
              type="primary"
              icon={<CloudDownloadOutlined />}
              loading={actioning}
              onClick={() => void doAction('trigger')}
              style={{ flex: 1 }}
            >
              触发采集
            </Button>
          )}
          {isRunning && (
            <Button
              icon={<PauseCircleOutlined />}
              loading={actioning}
              onClick={() => void doAction('pause')}
              style={{ flex: 1 }}
            >
              暂停
            </Button>
          )}
          {isPaused && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={actioning}
              onClick={() => void doAction('resume')}
              style={{ flex: 1 }}
            >
              继续
            </Button>
          )}
          {(isRunning || isPaused) && (
            <Button
              danger
              icon={<StopOutlined />}
              loading={actioning}
              onClick={() => void doAction('stop')}
              style={{ flex: 1 }}
            >
              停止
            </Button>
          )}
        </Space>
      </Card>

      {/* 配置编辑 */}
      <Card size="small" style={{ marginBottom: 10 }} title="调度配置">
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13 }}>启用定时调度</span>
            <Switch
              checked={editingEnabled}
              onChange={setEditingEnabled}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              间隔（分钟）
            </div>
            <InputNumber
              value={editingInterval}
              onChange={(v) => v !== null && setEditingInterval(v)}
              min={1}
              max={1440}
              style={{ width: '100%' }}
              addonAfter="min" /* NOSONAR - addonAfter 在 antd 5.x 仍可用，暂不迁移 */
            />
          </div>
          <Button
            type="primary"
            block
            loading={savingConfig}
            onClick={saveConfig}
          >
            保存配置（热更新）
          </Button>
        </Space>
      </Card>

            {/* 变更日志 */}
      {status?.change_log && status.change_log.length > 0 && (
        <Card size="small" style={{ marginBottom: 12 }} title="最近变更">
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            {status.change_log.slice(0, 5).map((change: BatchRefreshChangeLogEntry) => (
              <div
                key={`${change.item_id}-${change.timestamp}`}
                style={{
                  padding: '4px 0',
                  borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
                  fontSize: 12,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Tag color="blue">{change.item_id.slice(0, 12)}</Tag>
                  <span style={{ color: themeToken.colorTextTertiary }}>
                    {new Date(change.timestamp).toLocaleString('zh-CN')}
                  </span>
                </div>
                <div style={{ marginTop: 2, color: themeToken.colorTextSecondary }}>
                  变更字段：{change.changed_fields.join(', ')}
                </div>
              </div>
            ))}
          </Space>
        </Card>
      )}
    </div>
  )
}
