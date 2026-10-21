// frontend/src/mobile/pages/Logs/index.tsx
// 移动端实时日志：用轮询代替桌面端 SSE（更稳，省去 EventSource token 携带复杂度）
// 关键简化：每 3s 拉一次最新日志，按级别/关键词过滤；点击行展开详情抽屉
import { useCallback, useEffect, useState, useRef } from 'react'
import {
  Card, Tag, Spin, App, Input, Select, Button, Drawer, Space, Empty, theme,
} from 'antd'
import { ReloadOutlined, SearchOutlined, DownloadOutlined, PauseCircleOutlined, PlayCircleOutlined, StopOutlined } from '@ant-design/icons'
import { logApi, type LogEntry } from '../../../api'
import { extractApiError } from '../../../utils/apiError'
import { levelColor, normalizeLevel } from '../../../constants/logLevels'
import { useFailedSources } from '../../../hooks/useFailedSources'
import LoadFailedBar from '../../components/LoadFailedBar'

// 两个独立数据源：列表本身（首屏/切过滤）与后台自动刷新（轮询/回到前台）
type LogsSource = 'logs' | 'poll'
const SOURCE_LABELS: Record<LogsSource, string> = { logs: '日志列表', poll: '自动刷新' }

// 轮询间隔：3s 比桌面端 5s 更紧凑，弥补没有 SSE 的实时性损失
const POLL_INTERVAL_MS = 3000
// 单次拉取上限：避免一次返回过多渲染卡顿
const FETCH_LIMIT = 100
// 详情抽屉时间戳格式
const tsFmt = (iso: string): string => new Date(iso).toLocaleString('zh-CN')

export default function MobileLogs() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [polling, setPolling] = useState(false)
  const [pollingPaused, setPollingPaused] = useState(false)
  const [query, setQuery] = useState('')
  const [level, setLevel] = useState<string | undefined>(undefined)
  const [detail, setDetail] = useState<LogEntry | null>(null)
  // ref 镜像：避免闭包陷阱（暂停按钮在回调里读到旧 pollingPaused）
  const pausedRef = useRef(false)
  pausedRef.current = pollingPaused
  const { failed, mark } = useFailedSources<LogsSource>()

  // 拉取并搜索
  const fetchLogs = useCallback(async (): Promise<LogEntry[]> => {
    const res = await logApi.search({ q: query || undefined, level, limit: FETCH_LIMIT })
    return res.items || []
  }, [query, level])

  // 首次加载 / 过滤条件变化时拉一次
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchLogs()
      .then((items) => {
        if (cancelled) return
        setEntries(items)
        mark('logs', true)
      })
      .catch((e) => {
        if (cancelled) return
        mark('logs', false)
        message.error(extractApiError(e, '加载日志失败'), 3)
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [fetchLogs, message, mark])

  // 后台刷新（轮询 / 回到前台 / 失败条重试）：失败时保留旧数据，
  // 但旧数据不等于最新数据，必须记账把「自动刷新失败」说出来（T02701）
  const refreshInBackground = useCallback(async (): Promise<void> => {
    try {
      const items = await fetchLogs()
      setEntries(items)
      mark('poll', true)
    } catch {
      mark('poll', false)
    }
  }, [fetchLogs, mark])

  // 轮询：仅在 polling=true 且未暂停时每 3s 拉一次
  useEffect(() => {
    if (!polling || pollingPaused) return
    // 轮询开启/恢复：上一轮的「自动刷新失败」不再适用，先销账
    mark('poll', true)
    const id = setInterval(() => {
      // 暂停期间不更新 UI，避免视觉跳动
      if (pausedRef.current) return
      void refreshInBackground()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [polling, pollingPaused, refreshInBackground, mark])

  // visibility 切换：隐藏时停止轮询，恢复时立即拉一次
  useEffect(() => {
    if (!polling) return
    const onVis = () => {
      if (!document.hidden) void refreshInBackground()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [polling, refreshInBackground])

  // 手动重试：清空失败账并重新拉列表
  const reload = useCallback((): void => {
    setLoading(true)
    fetchLogs()
      .then((items) => {
        setEntries(items)
        mark('logs', true)
        mark('poll', true)
      })
      .catch((e) => {
        mark('logs', false)
        message.error(extractApiError(e, '加载失败'), 3)
      })
      .finally(() => setLoading(false))
  }, [fetchLogs, mark, message])

  const togglePolling = (): void => {
    setPolling((v) => !v)
    setPollingPaused(false)
  }

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  return (
    <div>
      {/* 过滤栏 + 轮询控制 */}
      <Space direction="vertical" size={8} style={{ width: '100%', marginBottom: 12 }}>
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="搜索关键词"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Space size={8} style={{ width: '100%' }}>
          <Select
            placeholder="日志级别"
            allowClear
            style={{ flex: 1 }}
            value={level}
            onChange={(v) => setLevel(v)}
            options={[
              { value: 'err', label: 'ERROR' },
              { value: 'warn', label: 'WARN' },
              { value: 'info', label: 'INFO' },
              { value: 'debug', label: 'DEBUG' },
            ]}
          />
          <Button
            size="middle"
            icon={<ReloadOutlined />}
            onClick={reload}
          >
            刷新
          </Button>
        </Space>
        {/* 轮询开关：移动端只暴露必要控制，避免布局过密 */}
        <Space size={8} style={{ width: '100%' }}>
          <Button
            type={polling ? 'default' : 'primary'}
            size="small"
            icon={polling ? <StopOutlined /> : <PlayCircleOutlined />}
            onClick={togglePolling}
            style={{ flex: 1 }}
          >
            {polling ? '停止轮询' : '开启轮询'}
          </Button>
          {polling && (
            <Button
              size="small"
              icon={pollingPaused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
              onClick={() => setPollingPaused((v) => !v)}
              style={{ flex: 1 }}
            >
              {pollingPaused ? '继续刷新' : '暂停刷新'}
            </Button>
          )}
          <Button
            size="small"
            icon={<DownloadOutlined />}
            href={logApi.exportUrl('csv', { q: query, level })}
            target="_blank"
          >
            CSV
          </Button>
        </Space>
      </Space>

      {/* 列表数据源失败：不能再用「暂无日志」空态冒充（T02701） */}
      {failed.logs && (
        <LoadFailedBar
          source={SOURCE_LABELS.logs}
          note={entries.length > 0 ? '下面是上一次成功拉取的结果' : '本次一条都没取到'}
          onRetry={reload}
        />
      )}
      {/* 后台刷新失败：列表还在，但不代表最新状态 */}
      {!failed.logs && failed.poll && polling && (
        <LoadFailedBar
          source={SOURCE_LABELS.poll}
          note="列表停留在上一次成功拉取的结果，可能已过期"
          onRetry={() => void refreshInBackground()}
        />
      )}

      {entries.length === 0 ? (
        failed.logs ? null : <Empty description="暂无日志" />
      ) : (
        entries.map((item, idx) => {
          // level 归一化后取色与展示：表内存小写缩写（err/warn/info/debug），
          // 直接大写会得到 ERR/WARN，落在颜色表键外 → Tag 恒灰
          const lvKey = normalizeLevel(item.level || 'info')
          const color = levelColor(item.level)
          return (
            <Card
              key={`${item.id ?? idx}-${item.created_at}`}
              size="small"
              style={{ marginBottom: 8, cursor: 'pointer' }}
              onClick={() => setDetail(item)}
            >
              <div style={{ display: 'flex', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
                <Tag color={color}>{lvKey}</Tag>
                {item.stage && <Tag>{item.stage}</Tag>}
                {item.task_id && <Tag color="blue">{item.task_id.slice(0, 8)}</Tag>}
                <span style={{ fontSize: 11, color: themeToken.colorTextTertiary, marginLeft: 'auto' }}>
                  {tsFmt(item.created_at)}
                </span>
              </div>
              {/* 单行省略避免卡片过高；详情在 Drawer 中查看 */}
              <div style={{ fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {item.message}
              </div>
            </Card>
          )
        })
      )}

      {/* 详情抽屉：完整堆叠字段 + payload */}
      <Drawer
        title="日志详情"
        placement="bottom"
        height="80%"
        open={detail !== null}
        onClose={() => setDetail(null)}
      >
        {detail && (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <div>
              <strong>级别：</strong>
              <Tag color={levelColor(detail.level)}>{normalizeLevel(detail.level || 'info')}</Tag>
            </div>
            <div><strong>时间：</strong>{tsFmt(detail.created_at)}</div>
            {detail.stage && <div><strong>阶段：</strong><Tag>{detail.stage}</Tag></div>}
            {detail.task_id && <div><strong>任务：</strong><Tag color="blue">{detail.task_id}</Tag></div>}
            <div>
              <strong>消息：</strong>
              <div style={{ marginTop: 4, padding: 8, background: themeToken.colorBgLayout, borderRadius: 4, wordBreak: 'break-word' }}>
                {detail.message}
              </div>
            </div>
            {detail.payload && Object.keys(detail.payload).length > 0 && (
              <div>
                <strong>Payload：</strong>
                <pre style={{ background: themeToken.colorBgLayout, padding: 8, borderRadius: 4, fontSize: 12, overflow: 'auto', maxHeight: 300 }}>
                  {JSON.stringify(detail.payload, null, 2)}
                </pre>
              </div>
            )}
          </Space>
        )}
      </Drawer>
    </div>
  )
}
