import { useEffect, useState, useCallback } from 'react'
import {
  Card, Table, Tag, Button, Space, Spin, Input, Select, Slider, Row, Col, message,
  Empty, DatePicker, Modal, Collapse, Statistic, Image, Tooltip, Alert,
} from 'antd'
import {
  ReloadOutlined, AimOutlined, RobotOutlined, LinkOutlined,
  SearchOutlined, UndoOutlined, RetweetOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { evalApi, aiApi, taskApi, type EvalItem, type AIConditionResult, type Task } from '../../api'
import { RISK_LEVEL_CONFIG } from '../../constants/riskLevels'
import { isDataInsufficient, getInsufficientReason, type DistResponse, type SellerTrendData } from './utils'
import EvalHeatmap from './components/EvalHeatmap'
import ResultBarChart from './components/ResultBarChart'
import PriceHistogram from './components/PriceHistogram'
import TrendSparkline from './components/TrendSparkline'

const { RangePicker } = DatePicker

export default function Evaluations() {
  // === 列表数据 ===
  const [items, setItems] = useState<EvalItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // === 查询条件 ===
  const [itemId, setItemId] = useState<string>('')
  const [taskId, setTaskId] = useState<string>('')
  const [tasks, setTasks] = useState<Task[]>([])
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100])
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)

  // === 分页 ===
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // === 分布图 ===
  const [dist, setDist] = useState<DistResponse | null>(null)
  const [distRange, setDistRange] = useState(168)
  const [distLoading, setDistLoading] = useState(false)

  // 从分布数据中获取当前生效阈值（后端返回），回退到默认 60/80
  const passScore = dist?.thresholds?.pass_score ?? 60
  const autoBuyScore = dist?.thresholds?.auto_buy_score ?? 80

  // === 阈值建议 ===
  const [thresholdTarget, setThresholdTarget] = useState(70)
  const [suggestion, setSuggestion] = useState<{ suggested_threshold: number; current_pass_rate: number } | null>(null)

  // === AI 评估 ===
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResult, setAiResult] = useState<AIConditionResult | null>(null)
  const [aiItemId, setAiItemId] = useState('')

  // === 卖家趋势（展开行） ===
  const [trendCache, setTrendCache] = useState<Record<string, SellerTrendData>>({})
  const [trendLoading, setTrendLoading] = useState('')

  // === 重新评估 ===
  const [recomputing, setRecomputing] = useState(false)

  // 用当前配置重新计算历史评估
  const onRecompute = async () => {
    setRecomputing(true)
    try {
      const res = await evalApi.recompute(taskId || undefined)
      message.success(res.message)
      // 重新加载数据
      load()
      loadDist()
    } catch {
      message.error('重新评估失败')
    } finally {
      setRecomputing(false)
    }
  }

  // 加载评估列表
  const load = useCallback(() => {
    setLoading(true)
    const params: Record<string, unknown> = {
      page_num: page,
      page_size: pageSize,
      limit: pageSize * 4,
    }
    if (itemId) params.item_id = itemId
    if (taskId) params.task_id = taskId
    if (scoreRange[0] > 0) params.min_score = scoreRange[0]
    if (scoreRange[1] < 100) params.max_score = scoreRange[1]
    if (dateRange && dateRange[0]) params.start_time = dateRange[0].format('YYYY-MM-DD')
    if (dateRange && dateRange[1]) params.end_time = dateRange[1].format('YYYY-MM-DD')

    evalApi.list(params)
      .then((res) => {
        setItems(res.items || [])
        setTotal(res.total || res.count || 0)
      })
      .catch(() => message.error('加载评估列表失败'))
      .finally(() => setLoading(false))
  }, [page, pageSize, itemId, taskId, scoreRange, dateRange])

  // 加载分布数据
  const loadDist = useCallback(() => {
    setDistLoading(true)
    evalApi.distribution({ range_hours: distRange, price_bin_count: 10, score_bin_count: 10 })
      .then((res) => setDist(res as DistResponse))
      .catch(() => {})
      .finally(() => setDistLoading(false))
  }, [distRange])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadDist() }, [loadDist])
  // 加载任务列表（供下拉选择器使用）
  useEffect(() => {
    taskApi.list({ limit: 200 }).then((res) => {
      setTasks(res.items || [])
    }).catch(() => {})
  }, [])

  // 查询/重置
  const onSearch = () => { setPage(1); load() }
  const onReset = () => {
    setItemId(''); setTaskId(''); setScoreRange([0, 100]); setDateRange(null); setPage(1)
  }

  // 阈值建议
  const fetchSuggestion = () => {
    evalApi.thresholdSuggestion(thresholdTarget / 100)
      .then((res) => { setSuggestion(res); message.success(`建议阈值: ${res.suggested_threshold}`) })
      .catch(() => message.error('获取阈值建议失败'))
  }

  // AI 成色评估
  const onAIEval = async (itemId: string) => {
    if (!itemId) {
      message.error('商品 ID 为空，无法评估')
      return
    }
    setAiItemId(itemId)
    setAiModalOpen(true)
    setAiLoading(true)
    setAiResult(null)
    try {
      const result = await aiApi.evaluateCondition(itemId)
      setAiResult(result)
    } catch (err: unknown) {
      const error = err as { response?: { status?: number; data?: { detail?: string } } }
      const status = error?.response?.status
      const detail = error?.response?.data?.detail
      if (status === 403) {
        message.error('AI 功能未开启，请在配置页面开启')
      } else if (status === 404) {
        message.error('商品不存在于数据库中')
      } else if (status === 422) {
        message.error('请求参数错误：商品 ID 为空')
      } else {
        message.error(detail || 'AI 评估失败，请检查 AI 配置')
      }
      setAiModalOpen(false)
    } finally {
      setAiLoading(false)
    }
  }

  // 卖家价格趋势
  const [trendError, setTrendError] = useState<Record<string, string>>({})
  const loadSellerTrend = async (itemId: string) => {
    if (trendCache[itemId]) return
    setTrendLoading(itemId)
    setTrendError((prev) => ({ ...prev, [itemId]: '' }))
    try {
      const data: SellerTrendData = await evalApi.sellerTrend(itemId)
      setTrendCache((prev) => ({ ...prev, [itemId]: data }))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      // 404: 商品未入库或无卖家信息
      if (msg.includes('404') || msg.includes('未找到')) {
        setTrendError((prev) => ({ ...prev, [itemId]: '该商品未入库，无法查询卖家趋势' }))
      } else {
        setTrendError((prev) => ({ ...prev, [itemId]: '加载失败：' + msg.slice(0, 50) }))
      }
    } finally {
      setTrendLoading('')
    }
  }

  // === 表格列定义（与商品列表页对齐） ===
  const columns = [
    {
      title: '任务ID', dataIndex: 'task_id', key: 'task_id', width: 120,
      ellipsis: true,
      render: (v: string) => <Tooltip title={v}>{v?.slice(0, 10)}...</Tooltip>,
    },
    {
      title: '图片', key: 'thumb', width: 70,
      render: (_: unknown, r: EvalItem) => {
        const url = r.payload?.thumb_url as string | undefined
        return url ? (
          <Image src={url} referrerPolicy="no-referrer" width={50} height={50}
            style={{ objectFit: 'cover', borderRadius: 6 }} preview={false} />
        ) : '—'
      },
    },
    {
      title: '标题', key: 'title', ellipsis: true,
      render: (_: unknown, r: EvalItem) => {
        const title = r.payload?.item_title || '—'
        const url = `https://www.goofish.com/item?id=${r.item_id}`
        return <a href={url} target="_blank" rel="noopener noreferrer">{title} <LinkOutlined /></a>
      },
    },
    {
      title: '价格', key: 'price', width: 90,
      sorter: (a: EvalItem, b: EvalItem) =>
        (a.payload?.item_price ?? 0) - (b.payload?.item_price ?? 0),
      render: (_: unknown, r: EvalItem) => r.payload?.item_price != null
        ? <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{Number(r.payload.item_price).toFixed(2)}</span>
        : '—',
    },
    {
      // 卖家列：参考闲鱼商品详情页风格，昵称+信用度合并显示
      title: '卖家', key: 'seller', width: 160, ellipsis: true,
      render: (_: unknown, r: EvalItem) => {
        const nick = r.payload?.seller_nick as string | undefined
        const id = r.payload?.seller_id as string | undefined
        const credit = r.payload?.seller_credit as string | undefined
        // 真实昵称优先级：清洗后的 seller_nick > seller_id（截短）> '—'
        const displayName = nick && nick.trim() ? nick : (id ? `用户 ${id.slice(0, 8)}` : '—')
        return (
          <div>
            <div>{displayName}</div>
            {credit && <div style={{ fontSize: 11, color: '#52c41a' }}>信用 {credit}</div>}
          </div>
        )
      },
    },
    {
      // 地区列：清洗后从脏数据恢复的 region，缺则 '—'
      title: '地区', key: 'region', width: 80,
      render: (_: unknown, r: EvalItem) => (r.payload?.region as string) || '—',
    },
    {
      // 想要数
      title: '想要', key: 'want', width: 60,
      render: (_: unknown, r: EvalItem) => (r.payload?.want_cnt as number) ?? '—',
    },
    {
      // 发布时间列：优先级 = 完整时间戳 > 历史数据中的发布时间短语 > '—'
      // 兜底显示"一周内发布"等从 seller_nick 脏数据中恢复的原文
      title: '发布时间', key: 'publish', width: 150,
      render: (_: unknown, r: EvalItem) => {
        const t = r.payload?.publish_time as string | undefined
        if (t) return new Date(t).toLocaleString('zh-CN')
        const text = r.payload?.publish_time_text as string | undefined
        if (text) return <span style={{ color: '#faad14' }}>{text}</span>
        return '—'
      },
    },
    {
      title: '成色', key: 'condition', width: 110,
      filters: [
        { text: '全新', value: '全新' },
        { text: '近全新', value: '近全新' },
        { text: '正常使用', value: '正常使用' },
        { text: '明显使用', value: '明显使用' },
        { text: '有故障/维修', value: '有故障/维修' },
        { text: '未注明', value: '未注明' },
        { text: '未知', value: '未知' },
      ],
      onFilter: (val: unknown, r: EvalItem) => (r as { condition_label?: string }).condition_label === val,
      render: (_: unknown, r: EvalItem & { condition_label?: string; condition_score?: number; is_branded_new?: boolean; has_repair?: boolean }) => {
        const label = r.condition_label || '未知'
        const score = r.condition_score || 0
        // 颜色：全新=绿、近全新=蓝、正常使用=灰、明显使用=橙、故障=红
        const colorMap: Record<string, string> = {
          '全新': 'green',
          '近全新': 'cyan',
          '正常使用': 'default',
          '明显使用': 'orange',
          '有故障/维修': 'red',
          '未注明': 'default',
          '未知': 'default',
        }
        return (
          <div>
            <Tag color={colorMap[label] || 'default'}>{label}</Tag>
            {score !== 0 && (
              <span style={{ fontSize: 11, marginLeft: 4, color: score > 0 ? '#52c41a' : '#ff4d4f' }}>
                {score > 0 ? `+${score}` : score}分
              </span>
            )}
          </div>
        )
      },
    },
    {
      title: '成色标签', key: 'condition_tags', width: 150,
      render: (_: unknown, r: EvalItem & { condition_tags?: Array<{ category: string; label: string }> }) => {
        const tags = r.condition_tags || []
        if (tags.length === 0) return '—'
        // 显示具体命中的关键词（限制最多 3 个，避免列表过长）
        return (
          <span style={{ fontSize: 11 }}>
            {tags.slice(0, 3).map((t, i) => (
              <Tag key={i} style={{ marginBottom: 2 }} color="blue">{t.label}</Tag>
            ))}
            {tags.length > 3 && <span style={{ color: '#999' }}>+{tags.length - 3}</span>}
          </span>
        )
      },
    },
    {
      title: '评分', key: 'score', width: 80,
      sorter: (a: EvalItem, b: EvalItem) => (a.payload.score ?? 0) - (b.payload.score ?? 0),
      render: (_: unknown, r: EvalItem) => {
        if (isDataInsufficient(r)) {
          // 方案C改进：显示具体原因而非笼统的"数据不足"
          return <Tag color="default">{getInsufficientReason(r)}</Tag>
        }
        const s = r.payload.score
        const color = s >= autoBuyScore ? '#52c41a' : s >= passScore ? '#faad14' : '#ff4d4f'
        return <span style={{ color, fontWeight: 600, fontSize: 15 }}>{s.toFixed(1)}</span>
      },
    },
    {
      title: '风险', key: 'risk', width: 70,
      render: (_: unknown, r: EvalItem) => {
        const level = r.payload?.risk_level || 'unknown'
        const cfg = RISK_LEVEL_CONFIG[level] || RISK_LEVEL_CONFIG.unknown
        return <Tag color={cfg.color}>{cfg.label}</Tag>
      },
    },
    {
      title: 'AI', key: 'ai', width: 70,
      render: (_: unknown, r: EvalItem) => (
        <Button
          size="small"
          icon={<RobotOutlined />}
          onClick={() => onAIEval(r.item_id)}
          disabled={isDataInsufficient(r) && (r.payload.score ?? 0) < 60}
        />
      ),
    },
  ]

  // 展开行：卖家价格趋势（委托给 TrendSparkline 组件）
  const expandedRowRender = (r: EvalItem) => (
    <TrendSparkline
      trend={trendCache[r.item_id]}
      loading={trendLoading === r.item_id}
      error={trendError[r.item_id]}
      onLoad={() => loadSellerTrend(r.item_id)}
    />
  )

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: 16 }}>评估明细</h2>

      {/* 查询条件 */}
      <Card style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <span>商品ID：</span>
          <Input
            placeholder="模糊匹配" allowClear style={{ width: 160 }}
            value={itemId} onChange={(e) => setItemId(e.target.value)}
            onPressEnter={onSearch}
          />
          <span>任务ID：</span>
          <Select
            placeholder="选择任务" allowClear showSearch
            style={{ width: 260 }}
            value={taskId || undefined}
            onChange={(v) => { setTaskId(v || ''); setPage(1); }}
            onClear={() => setTaskId('')}
            filterOption={(input, option) =>
              (option?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
            }
            options={tasks.map((t) => ({
              label: `${t.name}（${t.keyword}）`,
              value: t.id,
            }))}
            notFoundContent="暂无任务"
          />
          <span>评分范围：</span>
          <Slider
            range style={{ width: 200 }}
            value={scoreRange}
            onChange={(v) => setScoreRange(v as [number, number])}
          />
          <span>时间范围：</span>
          <RangePicker
            value={dateRange as [dayjs.Dayjs, dayjs.Dayjs] | null}
            onChange={(v) => setDateRange(v as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={onSearch}>查询</Button>
          <Button icon={<UndoOutlined />} onClick={onReset}>重置</Button>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
          <Button icon={<RetweetOutlined />} onClick={onRecompute} loading={recomputing}>重新评估</Button>
        </Space>
      </Card>

      {/* 方案C改进：数据不足时显示引导提示 */}
      {dist && dist.insufficient_count > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={`有 ${dist.insufficient_count} 条评估记录因卖家信息缺失仅基于价格评估`}
          description="建议在 Dashboard 页面重新登录闲鱼后，点击上方「重新评估」按钮获取完整评估结果。"
        />
      )}

      {/* 统计卡片 */}
      {dist && (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col span={4}>
            <Card size="small"><Statistic title="评估总数" value={dist.total} /></Card>
          </Col>
          <Col span={4}>
            <Card size="small"><Statistic title={`可抢(≥${autoBuyScore})`} value={dist.marginals.result.auto} valueStyle={{ color: '#52c41a' }} /></Card>
          </Col>
          <Col span={4}>
            <Card size="small"><Statistic title={`通过(${passScore}-${autoBuyScore - 1})`} value={dist.marginals.result.pass} valueStyle={{ color: '#1890ff' }} /></Card>
          </Col>
          <Col span={4}>
            <Card size="small"><Statistic title={`驳回(<${passScore})`} value={dist.marginals.result.fail} valueStyle={{ color: '#ff4d4f' }} /></Card>
          </Col>
          <Col span={4}>
            <Card size="small"><Statistic title="数据不足" value={dist.insufficient_count} valueStyle={{ color: '#999' }} /></Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="价格区间" value={dist.price_range[0] > 0 ? `¥${dist.price_range[0]}~${dist.price_range[1]}` : '—'} />
            </Card>
          </Col>
        </Row>
      )}

      <Row gutter={16}>
        {/* 左侧：列表 */}
        <Col span={16}>
          <Card>
            <Spin spinning={loading}>
              {items.length === 0 ? (
                <Empty description="暂无评估数据" />
              ) : (
                <Table
                  columns={columns}
                  dataSource={items}
                  rowKey={(r) => `${r.item_id}-${r.created_at}`}
                  size="middle"
                  scroll={{ x: 1200 }}
                  expandable={{
                    expandedRowRender,
                    rowExpandable: () => true,
                  }}
                  pagination={{
                    current: page,
                    pageSize,
                    total,
                    showSizeChanger: true,
                    showQuickJumper: true,
                    pageSizeOptions: ['10', '20', '50', '100'],
                    onChange: (p, ps) => { setPage(p); setPageSize(ps) },
                    showTotal: (t) => `共 ${t} 条`,
                  }}
                />
              )}
            </Spin>
          </Card>
        </Col>

        {/* 右侧：图表 */}
        <Col span={8}>
          <EvalHeatmap
            dist={dist}
            distRange={distRange}
            distLoading={distLoading}
            onRangeChange={setDistRange}
          />

          <ResultBarChart dist={dist} passScore={passScore} autoBuyScore={autoBuyScore} />

          <PriceHistogram dist={dist} />

          {/* 阈值建议 */}
          <Card title="阈值建议">
            <div style={{ marginBottom: 8 }}>目标通过率：{thresholdTarget}%</div>
            <Slider value={thresholdTarget} onChange={(v) => setThresholdTarget(v)} min={10} max={90} step={5} />
            <Button type="primary" icon={<AimOutlined />} onClick={fetchSuggestion} style={{ marginTop: 8 }} block>
              计算建议阈值
            </Button>
            {suggestion && (
              <div style={{ marginTop: 16, padding: 12, background: '#f6ffed', borderRadius: 4 }}>
                <div>建议阈值：<b style={{ color: '#52c41a' }}>{suggestion.suggested_threshold}</b></div>
                <div style={{ fontSize: 12, color: '#999' }}>当前通过率：{(suggestion.current_pass_rate * 100).toFixed(1)}%</div>
                <div style={{ fontSize: 12, color: '#999' }}>样本数：{dist?.total ?? '—'}</div>
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* AI 评估结果弹窗 */}
      <Modal
        title={`AI 成色评估 - ${aiItemId}`}
        open={aiModalOpen}
        onCancel={() => setAiModalOpen(false)}
        footer={<Button onClick={() => setAiModalOpen(false)}>关闭</Button>}
        width={560}
      >
        <Spin spinning={aiLoading}>
          {aiResult ? (
            <div>
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={12}>
                  <Statistic
                    title="评估结论"
                    value={aiResult.verdict === 'recommend' ? '推荐' : '谨慎'}
                    valueStyle={{ color: aiResult.verdict === 'recommend' ? '#52c41a' : '#faad14' }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="成色评分"
                    value={`${aiResult.condition_score}/10`}
                    valueStyle={{ color: aiResult.condition_score >= 7 ? '#52c41a' : '#faad14' }}
                  />
                </Col>
              </Row>
              <div style={{ marginBottom: 12 }}>
                <strong>评估理由：</strong>
                <p style={{ marginTop: 4 }}>{aiResult.reason}</p>
              </div>
              {aiResult.risk_signals?.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <strong>风险信号：</strong>
                  <div style={{ marginTop: 4 }}>
                    {aiResult.risk_signals.map((sig, i) => (
                      <Tag key={i} color="orange" style={{ marginBottom: 4 }}>{sig}</Tag>
                    ))}
                  </div>
                </div>
              )}
              {aiResult.detail && (
                <Collapse
                  items={[{ key: 'detail', label: '详细分析', children: <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{aiResult.detail}</pre> }]}
                  size="small"
                />
              )}
              <div style={{ marginTop: 12, fontSize: 12, color: '#999' }}>
                来源：{aiResult.source === 'llm' ? 'AI 视觉分析' : '规则模拟'}
                {aiResult.cached ? '（缓存）' : ''}
              </div>
            </div>
          ) : (
            !aiLoading && <Empty description="点击评估按钮开始 AI 分析" />
          )}
        </Spin>
      </Modal>
    </div>
  )
}
