import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Button, Space, Spin, Row, Col, Table, Empty, message, Statistic, Tabs, List,
} from 'antd'
import {
  ArrowLeftOutlined, PlayCircleOutlined, PauseCircleOutlined, StopOutlined, ReloadOutlined,
} from '@ant-design/icons'
import ReactECharts from '../../components/charts/EChart'
import { taskApi, taskDetailApi, evalApi, type Task, type TaskRun, type TaskDep, type EvalItem } from '../../api'
import { STATUS_COLOR } from '../../constants/statusColors'

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

  const load = () => {
    if (!id) return
    setLoading(true)
    Promise.all([
      taskApi.get(id).catch(() => null),
      taskDetailApi.runs(id, 168).catch(() => ({ runs: [], idle_gaps: [] })),
      taskDetailApi.deps(id).catch(() => []),
      taskDetailApi.dependents(id).catch(() => []),
      evalApi.list({ task_id: id, limit: 50 }).catch(() => ({ items: [] })),
    ]).then(([t, r, d, dep, ev]) => {
      setTask(t as Task)
      setRuns((r as { runs: TaskRun[]; idle_gaps: Array<{ from: string; to: string; duration_s: number }> })?.runs || [])
      setIdleGaps((r as { idle_gaps: Array<{ from: string; to: string; duration_s: number }> })?.idle_gaps || [])
      setDeps((d as TaskDep[]) || [])
      setDependents((dep as TaskDep[]) || [])
      setEvals((ev as { items: EvalItem[] })?.items || [])
      setLoading(false)
    })
  }

  useEffect(() => { load() }, [id])

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
        const color = s >= 70 ? '#52c41a' : s >= 50 ? '#faad14' : '#ff4d4f'
        return <span style={{ color, fontWeight: 600 }}>{s.toFixed(1)}</span>
      },
    },
    {
      title: '风险', key: 'risk', width: 80,
      render: (_: unknown, r: EvalItem) => <Tag color={r.payload.risk_level === 'low' ? 'green' : r.payload.risk_level === 'high' ? 'red' : 'orange'}>{r.payload.risk_level}</Tag>,
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
                          {idleGaps.slice(0, 5).map((g, i) => (
                            <div key={i} style={{ fontSize: 12, color: '#999' }}>
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
                        <Card title="上游依赖（本任务依赖的任务）" size="small">
                          {deps.length === 0 ? <Empty description="无上游依赖" /> : (
                            <List
                              size="small"
                              dataSource={deps}
                              renderItem={(d) => (
                                <List.Item>
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
