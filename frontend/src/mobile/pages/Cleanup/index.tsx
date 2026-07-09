// frontend/src/mobile/pages/Cleanup/index.tsx
// 移动端系统清理：缓存/数据库/日志三块卡片 + 预览开关 + 二次确认
// 设计要点：保留 dry_run 默认开 + Popconfirm 二次确认，保证移动端误触安全
import { useEffect, useState, useCallback, type ReactNode } from 'react'
import {
  Card, Tag, Spin, App, Select, InputNumber, Switch, Button, Space, Popconfirm, theme, Statistic, Row, Col,
} from 'antd'
import { DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import { maintenanceApi } from '../../../api/maintenance'
import type { StorageStatus, CleanupResult, CleanupBody } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'

// 清理 target 选项：与桌面端 Maintenance 保持一致
const CACHE_TARGETS = [
  { value: 'all', label: '全部缓存' },
  { value: 'browser_data', label: '浏览器数据' },
  { value: 'temp', label: '临时文件' },
]
const DB_TARGETS = [
  { value: 'all', label: '全部清理' },
  { value: 'old_events', label: '旧事件记录' },
  { value: 'old_items', label: '旧未关联商品' },
  { value: 'sold_items', label: '已售商品关联' },
  { value: 'vacuum', label: 'VACUUM 压缩' },
]
const LOG_TARGETS = [
  { value: 'old_logs', label: '按天数清理' },
  { value: 'large_logs', label: '大文件清理 (>10MB)' },
  { value: 'all', label: '全部清理' },
]

export default function MobileCleanup() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [status, setStatus] = useState<StorageStatus | null>(null)
  const [loading, setLoading] = useState(true)

  // 三个模块的独立表单 + 加载/结果状态（互不干扰）
  const [cacheForm, setCacheForm] = useState<CleanupBody>({ target: 'all', dry_run: true })
  const [cacheResult, setCacheResult] = useState<CleanupResult | null>(null)
  const [cacheLoading, setCacheLoading] = useState(false)

  const [dbForm, setDbForm] = useState<CleanupBody>({ target: 'old_events', days: 30, dry_run: true })
  const [dbResult, setDbResult] = useState<CleanupResult | null>(null)
  const [dbLoading, setDbLoading] = useState(false)

  const [logForm, setLogForm] = useState<CleanupBody>({ target: 'old_logs', days: 7, dry_run: true })
  const [logResult, setLogResult] = useState<CleanupResult | null>(null)
  const [logLoading, setLogLoading] = useState(false)

  const loadStatus = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const data = await maintenanceApi.getStorageStatus()
      setStatus(data)
    } catch (e) {
      message.error(extractApiError(e, '加载状态失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void loadStatus() }, [loadStatus])

  // 实际执行后刷新状态
  const cleanup = async (
    target: 'cache' | 'database' | 'logs',
    body: CleanupBody,
    setLoading_: (v: boolean) => void,
    setResult: (r: CleanupResult | null) => void,
  ): Promise<void> => {
    setLoading_(true)
    setResult(null)
    try {
      const result = await maintenanceApi.cleanup(target, body)
      setResult(result)
      if (!body.dry_run) await loadStatus()
      const count = result.cleaned?.length ?? 0
      if (body.dry_run) {
        message.info(count > 0 ? `预览：可处理 ${count} 项` : '预览：无内容可处理')
      } else {
        message.success(count > 0 ? `完成，共处理 ${count} 项` : '完成，无内容可处理')
      }
    } catch (e) {
      setResult({ errors: [`失败：${extractApiError(e, '')}`] })
      message.error(extractApiError(e, '清理失败'), 3)
    } finally {
      setLoading_(false)
    }
  }

  // 实际执行按钮（带 Popconfirm 二次确认）
  const renderExecuteButton = (
    target: 'cache' | 'database' | 'logs',
    form: CleanupBody,
    loading: boolean,
    setLoading_: (v: boolean) => void,
    setResult: (r: CleanupResult | null) => void,
  ): ReactNode => {
    if (form.dry_run) {
      return (
        <Button
          type="primary"
          block
          icon={<DeleteOutlined />}
          loading={loading}
          onClick={() => void cleanup(target, form, setLoading_, setResult)}
        >
          预览
        </Button>
      )
    }
    return (
      <Popconfirm
        title="确认执行？"
        description="此操作将真实删除数据，不可撤销"
        okText="确认执行"
        okButtonProps={{ danger: true }}
        cancelText="取消"
        onConfirm={() => void cleanup(target, form, setLoading_, setResult)}
      >
        <Button
          danger
          block
          icon={<DeleteOutlined />}
          loading={loading}
        >
          立即执行
        </Button>
      </Popconfirm>
    )
  }

  const renderResult = (r: CleanupResult | null): ReactNode => {
    if (!r) return null
    if (r.errors?.length) {
      return <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 8 }}>{r.errors.join('；')}</div>
    }
    if (r.cleaned?.length) {
      return (
        <div style={{ marginTop: 8, fontSize: 12, color: themeToken.colorTextSecondary }}>
          共 {r.count ?? r.cleaned.length} 项 · 释放 {r.total_freed_mb ?? 0} MB
        </div>
      )
    }
    return <div style={{ marginTop: 8, fontSize: 12, color: themeToken.colorTextTertiary }}>无可处理项</div>
  }

  if (loading && !status) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  return (
    <div>
      {/* 存储状态卡 */}
      <Card
        size="small"
        style={{ marginBottom: 12 }}
        title="存储状态"
        extra={
          <Button size="small" type="text" icon={<ReloadOutlined />} onClick={() => void loadStatus()}>
            刷新
          </Button>
        }
      >
        <Row gutter={8}>
          <Col span={8}>
            <Statistic
              title={<span style={{ fontSize: 11 }}>数据库</span>}
              value={status?.db?.db_size_mb ?? 0}
              suffix={<span style={{ fontSize: 10 }}>MB</span>}
              valueStyle={{ fontSize: 18, color: '#FF6200' }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title={<span style={{ fontSize: 11 }}>日志</span>}
              value={status?.logs?.total_size_mb ?? 0}
              suffix={<span style={{ fontSize: 10 }}>MB</span>}
              valueStyle={{ fontSize: 18, color: '#FF6200' }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title={<span style={{ fontSize: 11 }}>缓存</span>}
              value={((status?.cache?.browser_data_mb ?? 0) + (status?.cache?.pycache_mb ?? 0)).toFixed(1)}
              suffix={<span style={{ fontSize: 10 }}>MB</span>}
              valueStyle={{ fontSize: 18, color: '#FF6200' }}
            />
          </Col>
        </Row>
      </Card>

      {/* 缓存清理 */}
      <Card size="small" style={{ marginBottom: 10 }} title="缓存清理">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Select
            value={cacheForm.target}
            onChange={(v) => setCacheForm({ ...cacheForm, target: v })}
            options={CACHE_TARGETS}
            style={{ width: '100%' }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Switch
              checked={cacheForm.dry_run}
              onChange={(v) => setCacheForm({ ...cacheForm, dry_run: v })}
            />
            <span style={{ fontSize: 12 }}>仅预览</span>
            {!cacheForm.dry_run && <Tag color="red">将真实删除</Tag>}
          </div>
          {renderExecuteButton('cache', cacheForm, cacheLoading, setCacheLoading, setCacheResult)}
          {renderResult(cacheResult)}
        </Space>
      </Card>

      {/* 数据库清理 */}
      <Card size="small" style={{ marginBottom: 10 }} title="数据库清理">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Select
            value={dbForm.target}
            onChange={(v) => setDbForm({ ...dbForm, target: v })}
            options={DB_TARGETS}
            style={{ width: '100%' }}
          />
          {dbForm.target !== 'vacuum' && (
            <div>
              <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
                保留天数
              </div>
              <InputNumber
                value={dbForm.days}
                onChange={(v) => v !== null && setDbForm({ ...dbForm, days: v })}
                min={1}
                max={365}
                style={{ width: '100%' }}
                addonAfter="天"
              />
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Switch
              checked={dbForm.dry_run}
              onChange={(v) => setDbForm({ ...dbForm, dry_run: v })}
            />
            <span style={{ fontSize: 12 }}>仅预览</span>
            {!dbForm.dry_run && <Tag color="red">将真实删除</Tag>}
          </div>
          {renderExecuteButton('database', dbForm, dbLoading, setDbLoading, setDbResult)}
          {renderResult(dbResult)}
        </Space>
      </Card>

      {/* 日志清理 */}
      <Card size="small" style={{ marginBottom: 12 }} title="日志清理">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Select
            value={logForm.target}
            onChange={(v) => setLogForm({ ...logForm, target: v })}
            options={LOG_TARGETS}
            style={{ width: '100%' }}
          />
          {logForm.target !== 'large_logs' && (
            <div>
              <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
                保留天数
              </div>
              <InputNumber
                value={logForm.days}
                onChange={(v) => v !== null && setLogForm({ ...logForm, days: v })}
                min={1}
                max={365}
                style={{ width: '100%' }}
                addonAfter="天"
              />
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Switch
              checked={logForm.dry_run}
              onChange={(v) => setLogForm({ ...logForm, dry_run: v })}
            />
            <span style={{ fontSize: 12 }}>仅预览</span>
            {!logForm.dry_run && <Tag color="red">将真实删除</Tag>}
          </div>
          {renderExecuteButton('logs', logForm, logLoading, setLogLoading, setLogResult)}
          {renderResult(logResult)}
        </Space>
      </Card>
    </div>
  )
}
