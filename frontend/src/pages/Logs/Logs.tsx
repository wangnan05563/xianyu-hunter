import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { formatDateTime } from '../../utils/timeFormat'
import { useSearchParams } from 'react-router-dom'
import { Card, Space, Spin, Input, Select, Tag, Empty, message, Row, Col, Statistic, List } from 'antd'
import { ReloadOutlined, SearchOutlined, DownloadOutlined, PlayCircleOutlined, PauseCircleOutlined, StopOutlined, ClearOutlined } from '@ant-design/icons'
import { TipButton } from '@/components/TipButton'
import FetchFailedHint from '@/components/FetchFailedHint'
import { logApi, type LogEntry } from '../../api'
import { countLevels, levelColor, normalizeLevel } from '../../constants/logLevels'
import { API_BASE } from '../../utils/apiBase'
import { extractApiError } from '../../utils/apiError'

export default function Logs() {
  const [rawLogs, setRawLogs] = useState<Array<{ source: string; level: string; lines: string[] }>>([])
  const [searchResults, setSearchResults] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  // 失败态与空态分开：取到 0 条是「暂无日志」，没取到要说明原因并可重试（T02682）
  const [loadError, setLoadError] = useState<string | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  // 从 URL 恢复搜索条件
  const [query, setQuery] = useState(searchParams.get('query') || '')
  const [level, setLevel] = useState<string | undefined>(searchParams.get('level') || undefined)
  const [taskId, setTaskId] = useState<string | undefined>(searchParams.get('task_id') || undefined)
  // 实时流四态：未开启 / 连接中 / 已连接 / 已断开。
  // 断线不能退回「未开启」——那会让用户以为是自己关掉的，且已收到的日志看起来像停更了
  const [streamState, setStreamState] = useState<'idle' | 'connecting' | 'connected' | 'disconnected'>('idle')
  const streamActive = streamState !== 'idle'
  const [streamLogs, setStreamLogs] = useState<string[]>([])
  const [paused, setPaused] = useState(false)
  // 用 ref 跟踪暂停状态，避免 SSE 闭包中读到过时的 state
  const pausedRef = useRef(false)
  // 暂停期间暂存接收到的日志，恢复时一次性追加
  const pausedBufferRef = useRef<string[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)

  // 搜索条件变更时同步到 URL
  useEffect(() => {
    const params = new URLSearchParams()
    if (query) params.set('query', query)
    if (level) params.set('level', level)
    if (taskId) params.set('task_id', taskId)
    setSearchParams(params, { replace: true })
  }, [query, level, taskId, setSearchParams])

  const loadRaw = useCallback(() => {
    setLoading(true)
    logApi.list({ limit: 200, source: 'file' })
      .then((res) => { setRawLogs(res.items || []); setLoadError(null) })
      .catch((e) => {
        const msg = extractApiError(e, '加载日志失败')
        setLoadError(msg)
        message.error(msg)
      })
      .finally(() => setLoading(false))
  }, [])

  const search = useCallback(() => {
    setSearchLoading(true)
    logApi.search({ q: query, level, task_id: taskId, limit: 100 })
      .then((res) => {
        const items = res.items || []
        setSearchResults(items)
        setSearchError(null)
        message.success(`找到 ${items.length} 条匹配`)
      })
      .catch((e) => {
        const msg = extractApiError(e, '搜索失败')
        setSearchError(msg)
        message.error(msg)
      })
      .finally(() => setSearchLoading(false))
  }, [query, level, taskId])

  useEffect(() => { loadRaw() }, [loadRaw])

  // SSE 实时日志流
  // 后端 /api/events/stream 发的是 event: app_event 自定义类型,onmessage 不会触发,
  // 必须用 addEventListener('app_event', ...) 才能接收
  const startStream = () => {
    if (eventSourceRef.current) return
    const token = localStorage.getItem('xh_token') || ''
    const url = `${API_BASE}api/events/stream?token=${encodeURIComponent(token)}`
    const es = new EventSource(url)
    // 首帧/onopen 之前不算连上：此前弹「已开启」会在令牌失效或服务不可达时
    // 与随后的「连接断开」自相矛盾（T02681）
    const markConnected = () => {
      if (eventSourceRef.current !== es) return
      setStreamState((s) => (s === 'disconnected' ? s : 'connected'))
    }
    es.onopen = () => {
      if (eventSourceRef.current !== es) return
      setStreamState('connected')
      message.success('实时日志流已连接')
    }
    es.addEventListener('app_event', (ev) => {
      markConnected()
      try {
        const data = JSON.parse(ev.data) as LogEntry
        const line = data.message ? `[${data.level || 'info'}] ${data.message}` : ev.data
        if (pausedRef.current) {
          // 暂停时仅缓存，不追加到显示列表；超过500条丢弃最旧的
          pausedBufferRef.current.push(line)
          if (pausedBufferRef.current.length > 500) pausedBufferRef.current = pausedBufferRef.current.slice(-500)
        } else {
          setStreamLogs((prev) => [...prev.slice(-200), line])
        }
      } catch {
        if (pausedRef.current) {
          pausedBufferRef.current.push(ev.data)
          if (pausedBufferRef.current.length > 500) pausedBufferRef.current = pausedBufferRef.current.slice(-500)
        } else {
          setStreamLogs((prev) => [...prev.slice(-200), ev.data])
        }
      }
    })
    es.onerror = () => {
      if (eventSourceRef.current !== es) return
      // 断流：只关连接，不清 streamLogs / 暂停缓冲。保留下来的日志要明确标为「已断开」，
      // 用户可一键重连继续追加（T02680）
      es.close()
      eventSourceRef.current = null
      setStreamState('disconnected')
      message.warning('日志流连接断开，已保留断线前收到的日志')
    }
    eventSourceRef.current = es
    setStreamState('connecting')
  }

  const stopStream = () => {
    eventSourceRef.current?.close()
    eventSourceRef.current = null
    setStreamState('idle')
    setPaused(false)
    pausedRef.current = false
    pausedBufferRef.current = []
  }

  // 断线重连：EventSource 已被 close，直接重新建连；已收到的日志继续保留
  const reconnectStream = () => {
    if (eventSourceRef.current) return
    startStream()
  }

  // 暂停：停止追加到显示列表，但继续接收并缓存
  const togglePause = () => {
    if (paused) {
      // 恢复：先刷新缓冲区再解除暂停，避免新消息插入缓冲区消息之前
      const buffered = pausedBufferRef.current.slice(-200) // 限制最多200条
      pausedBufferRef.current = []
      if (buffered.length > 0) {
        setStreamLogs((prev) => [...prev.slice(-Math.max(0, 200 - buffered.length)), ...buffered])
      }
      pausedRef.current = false
      setPaused(false)
    } else {
      setPaused(true)
      pausedRef.current = true
    }
  }

  // 清空当前显示的实时流日志
  const clearStreamLogs = () => {
    setStreamLogs([])
    pausedBufferRef.current = []
  }

  useEffect(() => () => stopStream(), [])

  // 级别分布统计
  const levelDistribution = useMemo(() => countLevels(searchResults), [searchResults])

  // Top3 stage 标签
  const topStages = useMemo(() => {
    const stageCount: Record<string, number> = {}
    searchResults.forEach((item) => {
      if (item.stage) stageCount[item.stage] = (stageCount[item.stage] || 0) + 1
    })
    return Object.entries(stageCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
  }, [searchResults])

  // 合并原始日志行
  const allLines: Array<{ source: string; level: string; line: string }> = []
  rawLogs.forEach((g) => g.lines.forEach((l) => allLines.push({ source: g.source, level: g.level, line: l })))

  return (
    <div className="page-container">
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title="日志条数" value={allLines.length} /></Card></Col>
        <Col span={6}><Card><Statistic title="搜索结果" value={searchResults.length} /></Card></Col>
        <Col span={6}><Card><Statistic title="实时流" value={streamLogs.length} valueStyle={{ color: (() => {
          // 流式状态色：未启动灰；连接中蓝；断开红；运行绿（暂停不改变连接状态）
          if (streamState === 'idle') return 'var(--xh-text-tertiary)'
          if (streamState === 'connecting') return '#1677ff'
          if (streamState === 'disconnected') return '#ff4d4f'
          return paused ? '#faad14' : '#52c41a'
        })() }} /></Card></Col>
        <Col span={6}>
          <Card>
            <Space direction="vertical" style={{ width: '100%' }}>
              <TipButton
                tip={streamActive ? '停止并关闭实时日志流' : '开启实时日志流推送'}
                type="primary"
                danger={streamActive}
                icon={streamActive ? <StopOutlined /> : <PlayCircleOutlined />}
                onClick={streamActive ? stopStream : startStream}
                block
              >
                {streamState === 'idle' ? '开启实时流' : streamState === 'disconnected' ? '退出实时流' : '停止实时流'}
              </TipButton>
              {streamActive && (
                <Space style={{ width: '100%' }}>
                  <TipButton
                    tip={paused ? '恢复实时日志追加' : '暂停实时日志追加'}
                    size="small"
                    icon={paused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
                    onClick={togglePause}
                    style={{ flex: 1 }}
                  >
                    {paused ? '恢复' : '暂停'}
                  </TipButton>
                  <TipButton
                    tip="清空当前显示的实时流日志"
                    size="small"
                    icon={<ClearOutlined />}
                    onClick={clearStreamLogs}
                    danger
                    style={{ flex: 1 }}
                  >
                    清空
                  </TipButton>
                </Space>
              )}
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* 搜索面板 */}
        <Col span={12}>
          <Card title="结构化搜索">
            <Space style={{ marginBottom: 16 }} wrap>
              <Input
                placeholder="搜索关键词"
                prefix={<SearchOutlined />}
                style={{ width: 200 }}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onPressEnter={search}
                allowClear
              />
              <Select
                style={{ width: 120 }}
                allowClear
                placeholder="日志级别"
                value={level}
                onChange={(v) => setLevel(v)}
                options={[
                  { label: 'ERROR', value: 'err' },
                  { label: 'WARNING', value: 'warn' },
                  { label: 'INFO', value: 'info' },
                  { label: 'DEBUG', value: 'debug' },
                ]}
              />
              <Input
                placeholder="任务ID"
                style={{ width: 150 }}
                value={taskId}
                onChange={(e) => setTaskId(e.target.value)}
                allowClear
              />
              <TipButton tip="按关键词/级别/任务搜索日志" type="primary" icon={<SearchOutlined />} onClick={search} loading={searchLoading}>搜索</TipButton>
              {/* 导出 CSV 拼当前筛选参数，口径与所见一致；后端默认上限 1000 条，写进提示避免「导出全部」误解 */}
              <TipButton
                tip="按当前筛选条件（关键词/级别/任务ID）导出 CSV，最多 1000 条"
                icon={<DownloadOutlined />}
                href={logApi.exportUrl('csv', { q: query, level, task_id: taskId })}
                target="_blank"
              >
                导出CSV
              </TipButton>
              {/* format=log 走后端原始文件拼接，不吃筛选参数，文案只能声明「全部原始日志文件」 */}
              <TipButton tip="导出全部原始日志文件（run.stdout/stderr，不受筛选条件影响）" icon={<DownloadOutlined />} href={logApi.exportUrl('log')} target="_blank">导出LOG</TipButton>
            </Space>

            {searchError && (
              <FetchFailedHint
                source="搜索结果"
                description={`${searchError}${searchResults.length > 0 ? ' · 下方仍是上一次成功搜索的结果' : ' · 本次没有取到任何结果'}`}
                onRetry={search}
              />
            )}

            {/* 级别分布统计条 + Top stage 标签，仅在有搜索结果时显示 */}
            {searchResults.length > 0 && (
              <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>级别分布：</span>
                {Object.entries(levelDistribution).map(([lv, count]) => (
                  <Tag key={lv} color={levelColor(lv)}>{lv} {count}</Tag>
                ))}
                {topStages.length > 0 && (
                  <>
                    <span style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginLeft: 8 }}>Top标签：</span>
                    {topStages.map(([stage, count]) => (
                      <Tag key={stage}>{stage} ({count})</Tag>
                    ))}
                  </>
                )}
              </div>
            )}

            <Spin spinning={searchLoading}>
              {searchResults.length === 0 ? (
                // 失败时由上方 FetchFailedHint 说明原因，不能再显示「输入条件后搜索」
                searchError ? null : <Empty description="输入条件后搜索" />
              ) : (
                <List
                  size="small"
                  bordered
                  style={{ maxHeight: 500, overflow: 'auto' }}
                  dataSource={searchResults}
                  renderItem={(item) => (
                    <List.Item>
                      <div style={{ width: '100%' }}>
                        <Space size="small">
                          <Tag color={levelColor(item.level)}>{normalizeLevel(item.level)}</Tag>
                          <span style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>{formatDateTime(item.created_at)}</span>
                          {item.stage && <Tag>{item.stage}</Tag>}
                          {item.task_id && <Tag color="blue">{item.task_id.slice(0, 8)}</Tag>}
                        </Space>
                        <div style={{ marginTop: 4 }}>{item.message}</div>
                      </div>
                    </List.Item>
                  )}
                />
              )}
            </Spin>
          </Card>
        </Col>

        {/* 原始日志 / 实时流 */}
        <Col span={12}>
          <Card
            title={streamActive ? '实时日志流' : '原始日志'}
            extra={
              streamState === 'idle' ? (
                <TipButton tip="重新加载原始日志" icon={<ReloadOutlined />} onClick={loadRaw} loading={loading} size="small">刷新</TipButton>
              ) : (
                <Space size={8}>
                  {streamState === 'connecting' && <Tag color="processing">连接中</Tag>}
                  {streamState === 'connected' && <Tag color="success">已连接</Tag>}
                  {streamState === 'disconnected' && (
                    <>
                      <Tag color="error">连接已断开</Tag>
                      <TipButton size="small" onClick={reconnectStream} tip="重新建立实时日志流，已收到的日志会保留">
                        重新连接
                      </TipButton>
                    </>
                  )}
                </Space>
              )
            }
          >
            {/* 原始日志加载失败：不能再用「暂无日志」空态冒充（T02682） */}
            {loadError && !streamActive && (
              <FetchFailedHint
                source="日志"
                description={`${loadError}${allLines.length > 0 ? ' · 下方仍是上一次成功加载的内容' : ' · 本次一条日志都没取到'}`}
                onRetry={loadRaw}
              />
            )}
            <Spin spinning={loading}>
              <div style={{ maxHeight: 500, overflow: 'auto', fontFamily: 'Consolas, Monaco, monospace', fontSize: 12, background: 'var(--xh-bg-spotlight)', padding: 8 }}>
                {(() => {
                  // 实时流 / DB 静态日志的两种渲染路径
                  if (streamActive) {
                    if (streamLogs.length === 0) {
                      return (
                        <Empty
                          description={
                            streamState === 'connecting'
                              ? '正在连接日志流…'
                              : streamState === 'disconnected'
                                ? '连接已断开，断线前未收到日志'
                                : '等待日志推送...'
                          }
                        />
                      )
                    }
                    // 断线后保留已收到的日志但灰显：内容仍在、已不再更新
                    return (
                      <div data-testid="stream-logs" style={{ opacity: streamState === 'disconnected' ? 0.55 : 1 }}>
                        {streamLogs.map((l, i) => <div key={`${i}-${l}`} style={{ padding: '2px 0' }}>{l}</div>)}
                      </div>
                    )
                  }
                  if (allLines.length === 0) {
                    return loadError ? null : <Empty description="暂无日志" />
                  }
                  return allLines.slice(-200).map((l, i) => (
                    <div key={`${i}-${l.source}-${l.line}`} style={{ padding: '2px 0' }}>
                      <Tag color={levelColor(l.level)} style={{ fontSize: 10 }}>{l.level}</Tag>
                      <span style={{ color: 'var(--xh-text-tertiary)' }}>[{l.source}]</span> {l.line}
                    </div>
                  ))
                })()}
              </div>
            </Spin>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
