import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Button, Space, Spin, Row, Col, Table, Empty, message, Tabs, List,
  Select, Popconfirm, Radio, Tooltip,
} from 'antd'
import {
  ArrowLeftOutlined, PlayCircleOutlined, PauseCircleOutlined, StopOutlined, ReloadOutlined,
  SearchOutlined, SyncOutlined, DeleteOutlined, PlusOutlined, EyeOutlined,
} from '@ant-design/icons'
import ReactECharts from '../../components/charts/EChart'
import { taskApi, taskDetailApi, taskLinkApi, evalApi, statsApi, type Task, type TaskRun, type TaskDep, type EvalItem, type TaskLink, type TrendSeries } from '../../api'
import { STATUS_COLOR } from '../../constants/statusColors'

// 过滤掉指定的上游依赖项（S2004 拆出避免函数嵌套过深）
// 为什么提取：handleRemoveDep → .then → setDeps(prev =>) → filter(d =>) 嵌套达 5 层
function filterOutDep(prev: TaskDep[], dependsOn: string): TaskDep[] {
  return prev.filter((d) => d.depends_on !== dependsOn)
}

// 评分色：≥70 绿 ≥50 橙 否则红
// 为什么提取：evalColumns 评分列内 IIFE 含 if/else if 链，提取后列定义更简洁
const evalScoreToColor = (s: number): string => {
  if (s >= 70) return '#52c41a'
  if (s >= 50) return '#faad14'
  return '#ff4d4f'
}

// 风险等级色：low=green high=red 其他=orange
// 为什么提取：evalColumns 风险列内 IIFE 含 if/else if 链，与评分色同理
const riskLevelToColor = (lvl: string): string => {
  if (lvl === 'low') return 'green'
  if (lvl === 'high') return 'red'
  return 'orange'
}

// 把 load 接口的 5 个返回值应用到对应 setter
// 为什么提取：load 函数 .then 回调内 5 个 setX 调用，每个含 || [] 默认值，
// 嵌套层级 1 让每个 || 翻倍计分，认知复杂度累计让 TaskDetail 主函数触发 S3776；
// 提取到模块级后，主函数复杂度由 ~12 降至 1（仅剩 if (!id) return）
type IdleGap = { from: string; to: string; duration_s: number }
function applyLoadResult(
  data: [unknown, unknown, unknown, unknown, unknown],
  setters: {
    setTask: (t: Task | null) => void
    setRuns: (r: TaskRun[]) => void
    setIdleGaps: (g: IdleGap[]) => void
    setDeps: (d: TaskDep[]) => void
    setDependents: (d: TaskDep[]) => void
    setEvals: (e: EvalItem[]) => void
    setLoading: (b: boolean) => void
  },
) {
  const [t, r, d, dep, ev] = data
  const rObj = r as { runs?: TaskRun[]; idle_gaps?: IdleGap[] } | null
  setters.setTask(t as Task)
  setters.setRuns(rObj?.runs || [])
  setters.setIdleGaps(rObj?.idle_gaps || [])
  setters.setDeps((d as TaskDep[]) || [])
  setters.setDependents((dep as TaskDep[]) || [])
  setters.setEvals((ev as { items?: EvalItem[] })?.items || [])
  setters.setLoading(false)
}

// 把 handleAddDep 内 Promise.all 的返回值应用到 setDeps/setDependents
// 为什么提取：原 .then 嵌套 .then 回调内含 2 个 || []，嵌套层级让复杂度翻倍；
// 提取后 handleAddDep 主流程仅剩单行调用
function applyDepsResult(
  data: [unknown, unknown],
  setters: {
    setDeps: (d: TaskDep[]) => void
    setDependents: (d: TaskDep[]) => void
  },
) {
  const [d, dep] = data
  setters.setDeps((d as TaskDep[]) || [])
  setters.setDependents((dep as TaskDep[]) || [])
}

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<Task | null>(null)
  const [runs, setRuns] = useState<TaskRun[]>([])
  const [idleGaps, setIdleGaps] = useState<Array<{ from: string; to: string; duration_s: number }>>([])
  const [deps, setDeps] = useState<TaskDep[]>([])
  const [dependents, setDependents] = useState<TaskDep[]>([])
  const [evals, setEvals] = useState<EvalItem[]>([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  // 商品链接 Tab 状态
  const [linkType, setLinkType] = useState<'item' | 'seller'>('item')
  const [links, setLinks] = useState<TaskLink[]>([])
  const [linkTotal, setLinkTotal] = useState(0)
  const [linkPage, setLinkPage] = useState(1)
  const [linkLoading, setLinkLoading] = useState(false)
  const [liveLoading, setLiveLoading] = useState(false)
  const [refreshLoading, setRefreshLoading] = useState(false)
  const linkPageSize = 20

  // 依赖关系管理状态
  const [allTasks, setAllTasks] = useState<Task[]>([])
  const [addDepTaskId, setAddDepTaskId] = useState<string | null>(null)
  const [addDepLoading, setAddDepLoading] = useState(false)

  // 趋势线状态
  const [trendRange, setTrendRange] = useState<24 | 72 | 168>(24)
  const [evalTrend, setEvalTrend] = useState<TrendSeries | null>(null)
  const [eventsTrend, setEventsTrend] = useState<TrendSeries | null>(null)
  const [trendLoading, setTrendLoading] = useState(false)

  const loadTrends = useCallback(() => {
    if (!id) return
    setTrendLoading(true)
    Promise.all([
      statsApi.trend({ metric: 'eval_score', task_id: id, range_hours: trendRange }).catch(() => null),
      statsApi.trend({ metric: 'events', task_id: id, range_hours: trendRange }).catch(() => null),
    ]).then(([ev, evs]) => {
      // Promise.all 已推断出 TrendSeries | null，as 断言冗余（SonarQube S4325）
      setEvalTrend(ev)
      setEventsTrend(evs)
    }).finally(() => setTrendLoading(false))
  }, [id, trendRange])

  useEffect(() => { loadTrends() }, [loadTrends])

  const load = () => {
    if (!id) return
    setLoading(true)
    Promise.all([
      taskApi.get(id).catch(() => null),
      taskDetailApi.runs(id, 168).catch(() => null),
      taskDetailApi.deps(id).catch(() => null),
      taskDetailApi.dependents(id).catch(() => null),
      evalApi.list({ task_id: id, limit: 50 }).catch(() => null),
    ]).then((data) => applyLoadResult(data, { setTask, setRuns, setIdleGaps, setDeps, setDependents, setEvals, setLoading }))
  }

  // 加载闲鱼内容关联
  const loadLinks = useCallback(() => {
    if (!id) return
    setLinkLoading(true)
    const offset = (linkPage - 1) * linkPageSize
    taskLinkApi.list(id, { type: linkType, limit: linkPageSize, offset })
      .then((res) => {
        setLinks(res.items)
        setLinkTotal(res.total_for_type)
      })
      .catch(() => message.error('加载链接失败'))
      .finally(() => setLinkLoading(false))
  }, [id, linkType, linkPage])

  useEffect(() => { load() }, [id])
  useEffect(() => { loadLinks() }, [loadLinks])

  // 切换类型时重置页码
  const handleLinkTypeChange = (type: 'item' | 'seller') => {
    setLinkType(type)
    setLinkPage(1)
  }

  // 删除关联链接
  const handleRemoveLink = (linkId: number) => {
    if (!id) return
    taskLinkApi.remove(id, linkId).then(() => {
      message.success('已删除')
      loadLinks()
    }).catch(() => message.error('删除失败'))
  }

  // 实时查询
  const handleLive = () => {
    if (!id) return
    setLiveLoading(true)
    taskLinkApi.live(id)
      .then(() => {
        message.success('实时查询完成')
        loadLinks()
      })
      .catch(() => message.error('实时查询失败'))
      .finally(() => setLiveLoading(false))
  }

  // 刷新数据源
  const handleRefresh = () => {
    if (!id) return
    setRefreshLoading(true)
    taskLinkApi.refresh(id)
      .then((res) => {
        message.success(`刷新完成：发现 ${res.found} 条，保存 ${res.saved} 条`)
        loadLinks()
      })
      .catch(() => message.error('刷新失败'))
      .finally(() => setRefreshLoading(false))
  }

  // 加载可选任务列表（添加依赖时用）
  const loadAllTasks = () => {
    taskApi.list({ limit: 200 })
      .then((res) => setAllTasks(res.items))
      .catch(() => message.error('加载任务列表失败'))
  }

  // 添加上游依赖
  const handleAddDep = () => {
    if (!id || !addDepTaskId) return
    setAddDepLoading(true)
    taskDetailApi.addDep(id, addDepTaskId)
      .then(() => {
        message.success('添加依赖成功')
        setAddDepTaskId(null)
        // 刷新依赖列表：默认值与 || [] 处理统一收敛到 applyDepsResult
        Promise.all([
          taskDetailApi.deps(id).catch(() => null),
          taskDetailApi.dependents(id).catch(() => null),
        ]).then((data) => applyDepsResult(data, { setDeps, setDependents }))
      })
      .catch(() => message.error('添加依赖失败'))
      .finally(() => setAddDepLoading(false))
  }

  // 移除上游依赖
  const handleRemoveDep = (dependsOn: string) => {
    if (!id) return
    taskDetailApi.removeDep(id, dependsOn)
      .then(() => {
        message.success('移除依赖成功')
        // 过滤逻辑提取为模块级 filterOutDep，避免嵌套过深（S2004）
        setDeps((prev) => filterOutDep(prev, dependsOn))
      })
      .catch(() => message.error('移除依赖失败'))
  }

  const handleControl = (action: 'pause' | 'resume' | 'stop' | 'restart') => {
    if (!id) return
    setActionLoading(true)
    taskApi.control(id, action).then(() => {
      message.success(`操作成功: ${action}`)
      setTimeout(load, 500)
    }).catch(() => message.error('操作失败')).finally(() => setActionLoading(false))
  }

  // 运行历史趋势图
  const runsOption = runs.length > 0 ? {
    tooltip: { trigger: 'axis' },
    legend: { data: ['事件数', '命中数', '错误数'] },
    xAxis: { type: 'category', data: runs.map((r) => new Date(r.start).toLocaleString('zh-CN').slice(5, 16)) },
    yAxis: { type: 'value' },
    series: [
      { name: '事件数', type: 'bar', data: runs.map((r) => r.event_count), itemStyle: { color: '#1890ff' } },
      { name: '命中数', type: 'bar', data: runs.map((r) => r.hit_count), itemStyle: { color: '#52c41a' } },
      { name: '错误数', type: 'line', data: runs.map((r) => r.err_count), itemStyle: { color: '#ff4d4f' } },
    ],
    grid: { left: 50, right: 20, bottom: 60, top: 40 },
  } : null

  const evalColumns = [
    { title: '商品ID', dataIndex: 'item_id', key: 'item_id', width: 150, ellipsis: true },
    { title: '标题', key: 'title', ellipsis: true, render: (_: unknown, r: EvalItem) => r.payload?.item_title || '—' },
    {
      title: '评分', key: 'score', width: 80,
      render: (_: unknown, r: EvalItem) => {
        const s = r.payload.score
        // 评分色计算提取为模块级 evalScoreToColor（避免 IIFE 嵌套 if/else if）
        const color = evalScoreToColor(s)
        return <span style={{ color, fontWeight: 600 }}>{s.toFixed(1)}</span>
      },
    },
    {
      title: '风险', key: 'risk', width: 80,
      render: (_: unknown, r: EvalItem) => {
        const lvl = r.payload.risk_level
        // 风险色计算提取为模块级 riskLevelToColor（避免 IIFE 嵌套 if/else if）
        const color = riskLevelToColor(lvl)
        return <Tag color={color}>{lvl}</Tag>
      },
    },
    {
      title: '时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (t: string) => new Date(t).toLocaleString('zh-CN'),
    },
  ]

  const runColumns = [
    { title: '开始', dataIndex: 'start', key: 'start', render: (t: string) => new Date(t).toLocaleString('zh-CN') },
    { title: '结束', dataIndex: 'end', key: 'end', render: (t: string | null) => t ? new Date(t).toLocaleString('zh-CN') : '运行中' },
    { title: '时长(秒)', dataIndex: 'duration_s', key: 'duration_s', width: 100 },
    { title: '事件', dataIndex: 'event_count', key: 'event_count', width: 80 },
    { title: '命中', dataIndex: 'hit_count', key: 'hit_count', width: 80, render: (v: number) => <Tag color="green">{v}</Tag> },
    { title: '错误', dataIndex: 'err_count', key: 'err_count', width: 80, render: (v: number) => v > 0 ? <Tag color="red">{v}</Tag> : v },
    { title: '警告', dataIndex: 'warn_count', key: 'warn_count', width: 80, render: (v: number) => v > 0 ? <Tag color="orange">{v}</Tag> : v },
  ]

  // 闲鱼内容关联表格列
  const linkColumns = [
    {
      title: '标题', key: 'title', ellipsis: true,
      render: (_: unknown, r: TaskLink) => r.display?.title || '—',
    },
    {
      title: '价格', key: 'price', width: 100,
      // 用肯定条件 typeof === 'number' 替代 != null，更直观（SonarQube S7735）
      render: (_: unknown, r: TaskLink) => typeof r.display?.price === 'number' ? `¥${r.display.price}` : '—',
    },
    {
      title: '卖家昵称', key: 'seller_nick', width: 120, ellipsis: true,
      render: (_: unknown, r: TaskLink) => r.display?.seller_nick || '—',
    },
    {
      title: '地区', key: 'region', width: 80,
      render: (_: unknown, r: TaskLink) => r.display?.region || '—',
    },
    {
      title: '发布时间', key: 'publish_time', width: 170,
      render: (_: unknown, r: TaskLink) => r.display?.publish_time ? new Date(r.display.publish_time).toLocaleString('zh-CN') : '—',
    },
    {
      title: '来源', key: 'source', width: 80,
      render: (_: unknown, r: TaskLink) => <Tag>{r.source}</Tag>,
    },
    {
      title: '操作', key: 'action', width: 120,
      render: (_: unknown, r: TaskLink) => (
        <Space size="small">
          {/* 打开原帖：与 TaskList「闲鱼内容关联」风格保持一致 */}
          {r.display?.url && (
            <Tooltip title="打开原帖">
              <Button
                size="small"
                type="link"
                icon={<EyeOutlined />}
                onClick={() => globalThis.open(r.display.url, '_blank')}
              />
            </Tooltip>
          )}
          <Popconfirm title="确认删除此关联？" onConfirm={() => handleRemoveLink(r.link_id)} okText="删除" cancelText="取消">
            <Tooltip title="删除关联">
              <Button type="link" danger size="small" icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  // 过滤掉当前任务和已有的上游依赖，避免重复添加
  const depIds = new Set(deps.map((d) => d.depends_on))
  const availableTasks = allTasks.filter((t) => t.id !== id && !depIds.has(t.id))

  return (
    <div className="page-container">
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>返回列表</Button>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
      </Space>

      <Spin spinning={loading}>
        {task ? (
          <>
            <Card title={`任务详情：${task.name}`} style={{ marginBottom: 16 }}>
              <Space style={{ marginBottom: 16 }}>
                <Button type="primary" icon={<PlayCircleOutlined />} loading={actionLoading} onClick={() => handleControl('restart')} disabled={task.status === 'running'}>启动</Button>
                <Button icon={<PauseCircleOutlined />} loading={actionLoading} onClick={() => handleControl('pause')} disabled={task.status !== 'running'}>暂停</Button>
                <Button danger icon={<StopOutlined />} loading={actionLoading} onClick={() => handleControl('stop')} disabled={task.status === 'stopped'}>停止</Button>
                <Button onClick={() => navigate(`/tasks/${task.id}/edit`)}>编辑</Button>
              </Space>

              <Descriptions bordered column={2} size="small">
                <Descriptions.Item label="任务ID">{task.id}</Descriptions.Item>
                <Descriptions.Item label="状态"><Tag color={STATUS_COLOR[task.status] || 'default'}>{task.status}</Tag></Descriptions.Item>
                <Descriptions.Item label="关键词">{task.keyword}</Descriptions.Item>
                <Descriptions.Item label="模式">{task.mode}</Descriptions.Item>
                <Descriptions.Item label="价格区间">{task.min_price ? `¥${task.min_price}` : '不限'} - {task.max_price ? `¥${task.max_price}` : '不限'}</Descriptions.Item>
                <Descriptions.Item label="地域">{task.region || '不限'}</Descriptions.Item>
                <Descriptions.Item label="Cron 表达式"><code>{task.cron}</code></Descriptions.Item>
                <Descriptions.Item label="最大发布天数">{task.max_publish_days || '不限'}</Descriptions.Item>
                <Descriptions.Item label="排除词">{task.exclude_words || '无'}</Descriptions.Item>
                <Descriptions.Item label="搜索过滤">{task.search_filters || '无'}</Descriptions.Item>
                <Descriptions.Item label="创建时间">{new Date(task.created_at).toLocaleString('zh-CN')}</Descriptions.Item>
                <Descriptions.Item label="更新时间">{new Date(task.updated_at).toLocaleString('zh-CN')}</Descriptions.Item>
              </Descriptions>
            </Card>

            {/* 趋势线卡片：评估分 + 事件密度双 sparkline */}
            <Card
              title="趋势概览"
              style={{ marginBottom: 16 }}
              extra={
                <Radio.Group
                  value={trendRange}
                  onChange={(e) => setTrendRange(e.target.value)}
                  size="small"
                  optionType="button"
                  buttonStyle="solid"
                  options={[
                    { value: 24, label: '24h' },
                    { value: 72, label: '3d' },
                    { value: 168, label: '7d' },
                  ]}
                />
              }
            >
              <Spin spinning={trendLoading}>
                <Row gutter={16}>
                  <Col span={12}>
                    <div style={{ textAlign: 'center', marginBottom: 4, color: 'var(--xh-text-secondary)', fontSize: 13 }}>评估分趋势</div>
                    {evalTrend && evalTrend.series.length > 0 ? (
                      <ReactECharts
                        option={{
                          tooltip: { trigger: 'axis' },
                          grid: { left: 40, right: 10, top: 10, bottom: 24 },
                          xAxis: { type: 'category', data: evalTrend.series.map((p) => new Date(p.ts).toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' })), show: true, axisLabel: { fontSize: 10 } },
                          yAxis: { type: 'value', min: (value: { min: number }) => Math.floor(value.min * 0.9), axisLabel: { fontSize: 10 } },
                          series: [{ type: 'line', data: evalTrend.series.map((p) => p.value), smooth: true, symbol: 'none', lineStyle: { width: 2, color: '#1890ff' }, areaStyle: { color: 'rgba(24,144,255,0.1)' } }],
                        }}
                        style={{ height: 120 }}
                      />
                    ) : (
                      <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Col>
                  <Col span={12}>
                    <div style={{ textAlign: 'center', marginBottom: 4, color: 'var(--xh-text-secondary)', fontSize: 13 }}>事件密度趋势</div>
                    {eventsTrend && eventsTrend.series.length > 0 ? (
                      <ReactECharts
                        option={{
                          tooltip: { trigger: 'axis' },
                          grid: { left: 40, right: 10, top: 10, bottom: 24 },
                          xAxis: { type: 'category', data: eventsTrend.series.map((p) => new Date(p.ts).toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' })), show: true, axisLabel: { fontSize: 10 } },
                          yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
                          series: [{ type: 'line', data: eventsTrend.series.map((p) => p.count), smooth: true, symbol: 'none', lineStyle: { width: 2, color: '#52c41a' }, areaStyle: { color: 'rgba(82,196,26,0.1)' } }],
                        }}
                        style={{ height: 120 }}
                      />
                    ) : (
                      <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Col>
                </Row>
              </Spin>
            </Card>

            <Tabs
              items={[
                {
                  key: 'runs',
                  label: `运行历史 (${runs.length})`,
                  children: (
                    <Card>
                      {runsOption && <ReactECharts option={runsOption} style={{ height: 280, marginBottom: 16 }} />}
                      {runs.length === 0 ? <Empty description="暂无运行记录" /> : (
                        <Table columns={runColumns} dataSource={runs} rowKey="start" size="small" pagination={{ pageSize: 10 }} />
                      )}
                      {idleGaps.length > 0 && (
                        <div style={{ marginTop: 16 }}>
                          <h4>空闲间隔（{idleGaps.length}）</h4>
                          {idleGaps.slice(0, 5).map((g) => (
                            <div key={`${g.from}-${g.to}`} style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                              {new Date(g.from).toLocaleString('zh-CN')} → {new Date(g.to).toLocaleString('zh-CN')}（{Math.floor(g.duration_s / 60)}分钟）
                            </div>
                          ))}
                        </div>
                      )}
                    </Card>
                  ),
                },
                {
                  key: 'evals',
                  label: `评估记录 (${evals.length})`,
                  children: (
                    <Card>
                      {evals.length === 0 ? <Empty description="暂无评估记录" /> : (
                        <Table columns={evalColumns} dataSource={evals} rowKey={(r) => `${r.item_id}-${r.created_at}`} size="small" pagination={{ pageSize: 10 }} />
                      )}
                    </Card>
                  ),
                },
                {
                  key: 'deps',
                  label: `依赖关系 (上游${deps.length}/下游${dependents.length})`,
                  children: (
                    <Row gutter={16}>
                      <Col span={12}>
                        <Card
                          title="上游依赖（本任务依赖的任务）"
                          size="small"
                          extra={
                            <Button
                              type="link"
                              size="small"
                              icon={<PlusOutlined />}
                              onClick={loadAllTasks}
                            >
                              添加依赖
                            </Button>
                          }
                        >
                          {/* 添加依赖的输入行 */}
                          {allTasks.length > 0 && (
                            <div style={{ marginBottom: 8, display: 'flex', gap: 8 }}>
                              <Select
                                placeholder="选择任务"
                                style={{ flex: 1 }}
                                value={addDepTaskId}
                                onChange={setAddDepTaskId}
                                showSearch
                                optionFilterProp="label"
                                options={availableTasks.map((t) => ({ value: t.id, label: `${t.name} (${t.keyword})` }))}
                              />
                              <Button
                                type="primary"
                                size="small"
                                loading={addDepLoading}
                                disabled={!addDepTaskId}
                                onClick={handleAddDep}
                              >
                                添加
                              </Button>
                            </div>
                          )}
                          {deps.length === 0 ? <Empty description="无上游依赖" /> : (
                            <List
                              size="small"
                              dataSource={deps}
                              renderItem={(d) => (
                                <List.Item
                                  extra={
                                    <Popconfirm title="确认移除此依赖？" onConfirm={() => handleRemoveDep(d.depends_on)} okText="移除" cancelText="取消">
                                      <Button type="link" danger size="small">移除</Button>
                                    </Popconfirm>
                                  }
                                >
                                  <Space>
                                    <Tag color="blue">{d.depends_on}</Tag>
                                    {d.depends_on_name || '—'}
                                  </Space>
                                </List.Item>
                              )}
                            />
                          )}
                        </Card>
                      </Col>
                      <Col span={12}>
                        <Card title="下游依赖（依赖本任务的任务）" size="small">
                          {dependents.length === 0 ? <Empty description="无下游依赖" /> : (
                            <List
                              size="small"
                              dataSource={dependents}
                              renderItem={(d) => (
                                <List.Item>
                                  <Space>
                                    <Tag color="green">{d.task_id}</Tag>
                                    {d.task_name || '—'}
                                  </Space>
                                </List.Item>
                              )}
                            />
                          )}
                        </Card>
                      </Col>
                    </Row>
                  ),
                },
                {
                  key: 'links',
                  label: '闲鱼内容关联',
                  children: (
                    <Card>
                      <Space style={{ marginBottom: 16 }} wrap>
                        {/* 商品/卖家类型切换 */}
                        <Select
                          value={linkType}
                          onChange={handleLinkTypeChange}
                          style={{ width: 120 }}
                          options={[
                            { value: 'item', label: '商品' },
                            { value: 'seller', label: '卖家' },
                          ]}
                        />
                        {/* 实时查询：长轮询拉取最新数据 */}
                        <Button
                          icon={<SearchOutlined />}
                          loading={liveLoading}
                          onClick={handleLive}
                        >
                          实时查询
                        </Button>
                        {/* 刷新数据源：触发后端重新搜索并写入 */}
                        <Button
                          icon={<SyncOutlined />}
                          loading={refreshLoading}
                          onClick={handleRefresh}
                        >
                          刷新数据源
                        </Button>
                      </Space>
                      <Table
                        columns={linkColumns}
                        dataSource={links}
                        rowKey="link_id"
                        size="small"
                        loading={linkLoading}
                        pagination={{
                          current: linkPage,
                          pageSize: linkPageSize,
                          total: linkTotal,
                          showSizeChanger: false,
                          showTotal: (total) => `共 ${total} 条`,
                          onChange: (page) => setLinkPage(page),
                        }}
                      />
                    </Card>
                  ),
                },
              ]}
            />
          </>
        ) : (
          <Empty description="任务不存在" />
        )}
      </Spin>
    </div>
  )
}
