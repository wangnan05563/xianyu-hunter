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
import DangerSummary, { type DangerCopy } from '@/components/DangerSummary'
import { PYCACHE_NOT_APPLICABLE_HINT, cacheTargetOptions } from '@/utils/cacheTargets'

// 各清理模块的真实动作（T02573：确认框按「动作/影响范围/数量/恢复成本」四要素写）
const TARGET_ACTION: Record<'cache' | 'database' | 'logs', string> = {
  cache: '清理缓存',
  database: '清理数据库历史数据',
  logs: '清理日志文件',
}

function mobileDangerCopy(
  target: 'cache' | 'database' | 'logs',
  form: CleanupBody,
  status: StorageStatus | null,
): DangerCopy {
  const days = form.days
  if (target === 'cache') {
    const c = status?.cache
    // FR-A-5（T02575）：browser_data 现在删的是真实浏览器资料目录，后果是掉登录态
    const dropsLogin = form.target !== 'pycache'
    // T02739：打包版没有源码树，确认框不能还承诺清掉一份不存在的 __pycache__
    const pycacheApplicable = c?.pycache_applicable !== false
    return {
      action: `删除${form.target === 'pycache' ? ' __pycache__ 字节码缓存'
        : form.target === 'browser_data' ? ' 浏览器用户数据目录（含闲鱼登录 Cookie 与反爬指纹）'
          : pycacheApplicable ? ' __pycache__ 与浏览器用户数据目录'
            : ' 浏览器用户数据目录（含闲鱼登录 Cookie 与反爬指纹）'}`,
      scope: dropsLogin
        ? `将删除 ${c?.browser_data_path ?? '浏览器用户数据目录'}；不包含数据库与日志文件`
        : '只删 __pycache__ 字节码缓存；不包含数据库、日志与浏览器用户数据目录（登录态所在）',
      count: c
        ? (pycacheApplicable ? `__pycache__ 目录 ${c.pycache_count} 个（${c.pycache_mb} MB）；` : '')
          + `浏览器数据 ${c.browser_data_files} 个文件（${c.browser_data_mb} MB）`
        : null,
      recovery: dropsLogin
        ? '不可恢复；删除后需重新扫码登录闲鱼。浏览器正在占用该目录时会跳过删除并报错'
        : '不可恢复；字节码会在下次运行自动重建，首次运行稍慢',
    }
  }
  if (target === 'database') {
    const db = status?.db
    const d = days
    const action: Record<string, string> = {
      all: `删除早于 ${d} 天的事件与未关联商品、清理已售商品关联，随后 VACUUM 压缩`,
      old_events: `删除早于 ${d} 天的事件记录`,
      old_items: `删除早于 ${d} 天且未关联任务的商品记录`,
      sold_items: '删除已售商品的关联记录（该分支不看天数）',
      vacuum: '执行 VACUUM 压缩数据库文件',
    }
    const isVacuum = form.target === 'vacuum'
    return {
      action: action[form.target] ?? '清理数据库历史数据',
      scope: isVacuum
        ? '只重排数据库文件、回收空闲页；不删除任何业务记录'
        : '裁剪数据库历史记录；不影响配置与浏览器登录态。确切条数请先用「预览」确认',
      count: db ? `当前库内 任务 ${db.tasks} / 商品 ${db.items} / 事件 ${db.events}` : null,
      recovery: isVacuum
        ? '记录不会丢，但压缩过程无法中途恢复原文件；执行时间随库大小增长'
        : '不可恢复；只能在「数据库维护」用导出备份回滚，前提是先有备份',
    }
  }
  const lg = status?.logs
  const bigFile = form.target === 'large_logs' || form.target === 'all'
  return {
    action: form.target === 'large_logs' ? '删除体积超过 10MB 的日志文件'
      : form.target === 'all' ? `删除「早于 ${days} 天」或「超过 10MB」的日志文件`
        : `删除修改时间早于 ${days ?? '—'} 天的日志文件`,
    scope: '只删 logs/ 下的历史文本日志；不包含数据库事件记录'
      + (bigFile ? '。注意：大文件分支不看修改时间，当日日志只要超过 10MB 也会被删' : ''),
    count: lg ? `当前日志 ${lg.file_count} 个共 ${lg.total_size_mb} MB` : null,
    recovery: '删除后历史日志找不回，只能依赖数据库事件与「错误日志」页的留存数据',
  }
}

// 缓存清理选项由 utils/cacheTargets 统一生成（与桌面端同一份措辞 + 同一套「不适用」置灰）
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

  // T02739：打包版没有源码树，__pycache__ 恒为 0 → 置灰并标「不适用」
  const pycacheApplicable = status?.cache?.pycache_applicable !== false

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
        title={`确认${TARGET_ACTION[target]}？`}
        description={<DangerSummary {...mobileDangerCopy(target, form, status)} />}
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
      // 预览态回带的是"预计量"，措辞必须与执行态区分（4.1-2）
      const preview = r.dry_run === true
      return (
        <div style={{ marginTop: 8, fontSize: 12, color: themeToken.colorTextSecondary }}>
          {preview ? '预览（未删除）：' : ''}共 {r.count ?? r.cleaned.length} 项
          {r.total_deleted !== undefined && ` · ${preview ? '预计删除' : '删除'} ${r.total_deleted} 条`}
          {r.total_freed_mb !== undefined && ` · ${preview ? '预计释放' : '释放'} ${r.total_freed_mb} MB`}
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
            options={cacheTargetOptions(pycacheApplicable)}
            style={{ width: '100%' }}
          />
          {!pycacheApplicable && (
            <span style={{ fontSize: 11, color: themeToken.colorTextTertiary }}>
              {PYCACHE_NOT_APPLICABLE_HINT}
            </span>
          )}
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
          {/* 4.1-5：sold_items 与 vacuum 两个分支后端都不读 days，显示可编辑输入框＝假可配置 */}
          {dbForm.target !== 'vacuum' && dbForm.target !== 'sold_items' && (
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
                addonAfter="天" /* NOSONAR - addonAfter 在 antd 5.x 仍可用，迁移到 InputNumber.Group 会破坏现有布局，暂不迁移 */
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
                addonAfter="天" /* NOSONAR - addonAfter 在 antd 5.x 仍可用，迁移到 InputNumber.Group 会破坏现有布局，暂不迁移 */
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
