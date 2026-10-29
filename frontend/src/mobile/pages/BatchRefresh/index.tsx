// frontend/src/mobile/pages/BatchRefresh/index.tsx
// 移动端批量采集：状态卡 + 控制按钮 + 配置编辑 + 历史列表
// 设计要点：保留 trigger/pause/resume/stop 四控制 + interval_minutes 热更新
import { useEffect, useState, useCallback } from 'react'
import { formatDateTime } from '../../../utils/timeFormat'
import {
  Card, Tag, Spin, App, Button, Space, theme, InputNumber, Switch, Descriptions,
} from 'antd'
import {
  PlayCircleOutlined, PauseCircleOutlined, StopOutlined, ReloadOutlined, CloudDownloadOutlined,
} from '@ant-design/icons'
import { batchRefreshApi } from '../../../api'
import type { BatchRefreshStatus, BatchRefreshChangeLogEntry, BatchRefreshTriggerPreview } from '../../../api/batchRefresh'
import { extractApiError } from '../../../utils/apiError'
import { confirmDanger } from '../../../components/DangerSummary'
import { useFailedSources } from '../../../hooks/useFailedSources'
import LoadFailedBar from '../../components/LoadFailedBar'

// 数据源（T02718）：状态取不到时不能显示 CURRENT=IDLE，
// 也要挡住「用默认值 60 分钟 / 启用」保存配置把真实配置覆盖掉
type BatchRefreshSource = 'status'
const SOURCE_LABELS: Record<BatchRefreshSource, string> = {
  status: '调度状态',
}

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
  const { failed, mark } = useFailedSources<BatchRefreshSource>()

  const load = useCallback(async (): Promise<void> => {
    try {
      const data = await batchRefreshApi.getStatus()
      setStatus(data)
      setEditingInterval(data.interval_minutes)
      setEditingEnabled(data.enabled)
      mark('status', true)
    } catch (e) {
      mark('status', false)
      message.error(extractApiError(e, '加载状态失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message, mark])

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

  // 触发前先取范围预估再四要素确认（T02771 / PRD 4.4-2）：
  // 移动端原来点一下就真跑一批，既看不到本批多大，也看不到是否接着断点续传。
  // 预估失败绝不降级成「0 个」直接放行——那等于把未知当无事发生。
  const triggerWithConfirm = async (): Promise<void> => {
    let preview: BatchRefreshTriggerPreview
    try {
      preview = await batchRefreshApi.triggerPreview()
    } catch (e) {
      message.error(extractApiError(e, '本批范围统计失败，请稍后重试'), 3)
      return
    }
    if (preview.pending === 0) {
      message.info('本批无待处理商品（当前没有在售商品），未触发采集', 3)
      return
    }
    // 先用 if 收敛「续跑 / 新批次」两套文案，避免确认框里出现嵌套三元
    let scope: string
    if (preview.resumed) {
      scope = `接着上次中断的批次跑剩下的 ${preview.pending} 个商品（原批次共 ${preview.resumed_total} 个，已处理 ${preview.resumed_processed} 个）`
    } else {
      const atLimitHint = preview.at_limit ? '（已达上限，本轮只跑这些）' : ''
      scope = `本批覆盖 ${preview.pending} 个在售商品，单次上限 ${preview.limit}${atLimitHint}`
    }
    const ok = await confirmDanger({
      title: preview.resumed ? '确认续跑未完成的批次？' : '确认触发批量采集？',
      action: '立即开始一轮批量采集，逐个访问商品详情页',
      scope,
      count: `${preview.pending} 个商品`,
      recovery: '触发后可在本页暂停或停止；停止时未处理的商品会持久化，下次触发从断点续传',
    })
    if (ok) await doAction('trigger')
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
      {failed.status && (
        <LoadFailedBar
          source={SOURCE_LABELS.status}
          note="当前状态未知，下方操作与保存配置已禁用，避免用默认值覆盖真实配置"
          onRetry={() => void load()}
        />
      )}
      {/* 状态卡 */}
      <Card size="small" style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary }}>当前状态</div>
            <Tag
              color={STATUS_COLORS[currentStatus] || 'default'}
              style={{ fontSize: 14, padding: '4px 12px', marginTop: 4 }}
            >
              {status ? currentStatus.toUpperCase() : '状态未知'}
            </Tag>
          </div>
          <Button type="text" icon={<ReloadOutlined />} onClick={() => void load()} />
        </div>
              {/* 上次执行结果 */}
        {status?.last_result && (
          <Descriptions column={1} size="small" style={{ marginTop: 8 }}>
            <Descriptions.Item label="上次执行">
              {status.last_run_at ? formatDateTime(status.last_run_at) : '-'}
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
              disabled={!status}
              loading={actioning}
              onClick={() => void triggerWithConfirm()}
              style={{ flex: 1 }}
            >
              触发采集
            </Button>
          )}
          {isRunning && (
            <Button
              icon={<PauseCircleOutlined />}
              disabled={!status}
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
              disabled={!status}
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
              disabled={!status}
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
            disabled={!status}
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
                    {formatDateTime(change.timestamp)}
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
