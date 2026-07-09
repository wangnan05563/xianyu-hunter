import { useEffect, useState, useCallback } from 'react'
import { Card, Slider, InputNumber, Row, Col, Button, Space, message, Divider, Tag, Alert, Spin, Empty, Table, Switch, theme } from 'antd'
import {
  CloudDownloadOutlined,
  DollarCircleOutlined,
  RobotOutlined,
  SaveOutlined,
  ThunderboltOutlined,
  UndoOutlined,
} from '@ant-design/icons'
import ReactECharts from '../../components/charts/EChart'
import { useConfigStore } from '../../stores/configStore'
import { extractApiError } from '../../utils/apiError'
import type { DiffChange } from '../../stores/configStore'
import { evalApi } from '../../api'
import TagEditor from '../../components/editors/TagEditor'
import { useAutoRefresh } from '../../hooks/useAutoRefresh'
import { DiffPreviewModal } from '../../components/DiffPreviewModal'

// 热力图坐标数据：从 distData.buckets 二维数组计算 ECharts 所需 [x, y, value] 列表与轴标签
// 为什么提取：原实现包含 4 层嵌套（if + 3 个 for/forEach），留在组件内会让 EvalRules 复杂度超限
type HeatmapCompute = {
  data: Array<[number, number, number]>
  max: number
  xLabels: string[]
  yLabels: string[]
}
const computeHeatmapData = (distData: {
  buckets: Array<Array<{ count: number; pass: number; auto: number; fail: number }>>
  price_range: [number, number]
  total: number
} | null): HeatmapCompute => {
  const result: HeatmapCompute = { data: [], max: 1, xLabels: [], yLabels: [] }
  // 用可选链合并 null 判断更简洁（SonarQube S6582）
  if (!distData?.buckets?.length) return result

  const sBins = distData.buckets.length
  const pBins = distData.buckets[0]?.length || 5
  const [pMin, pMax] = distData.price_range || [0, 5000]
  const pStep = (pMax - pMin) / pBins
  const sStep = 100 / sBins

  // X 轴标签（价格区间）
  for (let i = 0; i < pBins; i++) {
    const lo = Math.round(pMin + i * pStep)
    const hi = Math.round(pMin + (i + 1) * pStep)
    result.xLabels.push(`¥${lo}~${hi}`)
  }
  // Y 轴标签（评分区间，从高到低）
  for (let i = 0; i < sBins; i++) {
    const hi = Math.round(100 - i * sStep)
    const lo = Math.round(100 - (i + 1) * sStep)
    result.yLabels.push(`${lo}-${hi}`)
  }
  // 构建 [x, y, value] 序列并跟踪最大值（用于 visualMap 范围）
  distData.buckets.forEach((row, si) => {
    row.forEach((bucket, pi) => {
      result.data.push([pi, si, bucket.count])
      if (bucket.count > result.max) result.max = bucket.count
    })
  })
  return result
}

// 构建热力图 ECharts 配置：tooltip/grid/visualMap/series
// 为什么提取：原实现是嵌套三元 + 多层对象字面量，组件内联让 EvalRules 函数复杂度上升
const buildHeatmapOption = (
  distData: { buckets: Array<Array<{ count: number; pass: number; auto: number; fail: number }>> } | null,
  heatmap: HeatmapCompute,
) => {
  // 用可选链合并 null 判断更简洁（SonarQube S6582）
  if (!distData?.buckets?.length) return null
  return {
    tooltip: {
      position: 'top',
      formatter: (p: { dataIndex: [number, number]; value: number }) => {
        const [pi, si] = p.dataIndex
        const bucket = distData.buckets[si]?.[pi]
        if (!bucket || bucket.count === 0) return '该区间暂无商品'
        return `${heatmap.xLabels[pi]} × ${heatmap.yLabels[si]}<br/>商品数：${bucket.count}<br/>可抢：${bucket.auto} / 通过：${bucket.pass} / 驳回：${bucket.fail}`
      },
    },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: heatmap.xLabels,
      name: '价格',
      splitArea: { show: true },
      axisLabel: { fontSize: 9, rotate: 30 },
    },
    yAxis: {
      type: 'category',
      data: heatmap.yLabels,
      name: '评分',
      splitArea: { show: true },
      axisLabel: { fontSize: 9 },
    },
    visualMap: {
      min: 0,
      max: heatmap.max,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: { color: ['#f5f5f5', '#bae7ff', '#69c0ff', '#1890ff'] },
      formatter: (v: number) => `${v}件`,
    },
    series: [
      {
        type: 'heatmap',
        data: heatmap.data,
        label: {
          show: true,
          formatter: (p: { value: number }) => p.value > 0 ? String(p.value) : '',
          fontSize: 9,
        },
      },
    ],
  }
}

const priceRangeGradientRules = [
  { range: '< 600', label: '低于任务下限', score: '-25 / -50', color: 'red' },
  { range: '600-640', label: '低价边缘', score: '-10', color: 'orange' },
  { range: '640-730', label: '推荐核心区', score: '不扣分', color: 'green' },
  { range: '730-760', label: '偏高观察区', score: '-5', color: 'gold' },
  { range: '760-800', label: '高价边缘', score: '-12', color: 'orange' },
  { range: '> 800', label: '高于任务上限', score: '-25 / -50', color: 'red' },
]

export default function EvalRules() {
  const { config, load, hasChanges, reset, update, previewSave, confirmSave, getFieldOriginal, revertField } = useConfigStore()
  const [distData, setDistData] = useState<{
    buckets: Array<Array<{ count: number; pass: number; auto: number; fail: number }>>
    price_range: [number, number]
    total: number
  } | null>(null)
  const [distLoading, setDistLoading] = useState(false)
  // Diff 预览
  const [diffModalOpen, setDiffModalOpen] = useState(false)
  const [diffChanges, setDiffChanges] = useState<DiffChange[]>([])
  const [saving, setSaving] = useState(false)

  // 自动官方采集统计：60s 自动刷新，仅在开关开启时加载
  // 为什么 60s：采集本身耗时 30s+，更短间隔无意义；更长间隔反馈滞后
  const [collectStats, setCollectStats] = useState<{
    total: number
    success: number
    failed: number
    success_rate: number
    is_paused: boolean
    fail_pause_threshold: number
    top_failures: Array<{ reason: string; count: number }>
  } | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)

  // 为什么用 config?.eval?.auto_collect_official 而不是 evalConfig?：
  // evalConfig 在下方 `if (!config) return` 之后才从 config 解构，hooks 必须在该 early return 之前调用，
  // 此处只能通过 config 可选链访问
  const loadCollectStats = useCallback((): Promise<void> => {
    if (!config?.eval?.auto_collect_official) {
      // 开关关闭时不加载，避免无意义请求
      setCollectStats(null)
      return Promise.resolve()
    }
    setStatsLoading(true)
    return evalApi
      .autoCollectStats(24)
      .then((res) => setCollectStats(res))
      .catch(() => {
        // 静默失败：统计接口失败不应弹 message 打断用户配置
      })
      .finally(() => setStatsLoading(false))
  }, [config?.eval?.auto_collect_official])

  const { lastRefreshAt: statsLastRefresh, nextRefreshAt: statsNextRefresh } = useAutoRefresh({
    enabled: !!config?.eval?.auto_collect_official,
    intervalSec: 60,
    paused: !config?.eval?.auto_collect_official,
    deps: [config?.eval?.auto_collect_official],
    refresh: loadCollectStats,
  })
  // 预格式化时间字符串，避免 JSX 内嵌套三元
  const statsLastRefreshStr = statsLastRefresh
    ? new Date(statsLastRefresh).toLocaleTimeString('zh-CN')
    : '-'
  const statsNextRefreshStr = statsNextRefresh
    ? new Date(statsNextRefresh).toLocaleTimeString('zh-CN')
    : null

  // 首次加载 + 开关切换时立即加载（useAutoRefresh 的 deps 已会触发，此处兜底保证首次进入也拉一次）
  useEffect(() => {
    loadCollectStats()
  }, [loadCollectStats])

  useEffect(() => {
    load()
    loadDist()
  }, [load])

  // 加载真实评估分布数据
  const loadDist = () => {
    setDistLoading(true)
    evalApi.distribution({ range_hours: 168, price_bin_count: 5, score_bin_count: 5 })
      .then((res) => setDistData(res))
      .catch(() => {})
      .finally(() => setDistLoading(false))
  }

  if (!config) {
    return <div className="page-container">加载中...</div>
  }

  const { eval: evalConfig } = config
  const weights = evalConfig.weights
  const thresholds = evalConfig.thresholds

  // 权重总和
  const weightsTotal = weights.professional + weights.credit + weights.dispute + weights.price

  // pass_score 不能大于 auto_buy_score
  const scoreOrderError = evalConfig.pass_score > evalConfig.auto_buy_score

  // 更新权重
  const updateWeight = (key: keyof typeof weights, value: number) => {
    update({
      eval: {
        ...evalConfig,
        weights: { ...weights, [key]: value },
      },
    })
  }

  // 更新阈值
  const updateThreshold = (key: keyof typeof thresholds, value: number) => {
    update({
      eval: {
        ...evalConfig,
        thresholds: { ...thresholds, [key]: value },
      },
    })
  }

  // 一键归一化（权重总和=100）
  const normalize = () => {
    if (weightsTotal === 0) return
    const factor = 100 / weightsTotal
    update({
      eval: {
        ...evalConfig,
        weights: {
          professional: Math.round(weights.professional * factor),
          credit: Math.round(weights.credit * factor),
          dispute: Math.round(weights.dispute * factor),
          price: Math.round(weights.price * factor),
        },
      },
    })
    message.success('已归一化为 100')
  }

  // 雷达图配置
  const radarOption = {
    tooltip: {},
    radar: {
      indicator: [
        { name: '职业度', max: 100 },
        { name: '信誉', max: 100 },
        { name: '纠纷', max: 100 },
        { name: '价格', max: 100 },
      ],
      shape: 'polygon',
      splitNumber: 5,
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: [weights.professional, weights.credit, weights.dispute, weights.price],
            name: '当前权重',
            areaStyle: { color: 'rgba(22, 119, 255, 0.3)' },
            lineStyle: { color: '#1677ff' },
          },
        ],
      },
    ],
  }

  // 评估分布热力图（使用真实分布数据）
  // 数据计算与 option 构造已提取为模块级纯函数，避免组件内多层嵌套循环
  const heatmap = computeHeatmapData(distData)
  const heatmapOption = buildHeatmapOption(distData, heatmap)

  // S3776 修复：将保存前的两个守卫校验提取为独立函数，主回调只剩 try/catch 流程
  const validateBeforeSave = (): string | null => {
    if (weightsTotal !== 100) return '权重总和必须为 100，请调整后保存'
    if (scoreOrderError) return '通过分数不能大于自动抢单分数'
    return null
  }

  const handleSave = async () => {
    const error = validateBeforeSave()
    if (error) {
      message.error(error)
      return
    }
    try {
      setSaving(true)
      const changes = await previewSave()
      if (changes.length === 0) {
        message.info('配置未变更')
        return
      }
      setDiffChanges(changes)
      setDiffModalOpen(true)
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
    }
  }

  const handleConfirmSave = async () => {
    try {
      setSaving(true)
      await confirmSave()
      setDiffModalOpen(false)
      message.success('评估规则已保存')
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <Space>
          <Button icon={<UndoOutlined />} onClick={reset} disabled={!hasChanges()}>
            重置
          </Button>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
            保存
          </Button>
        </Space>
      </div>

      {/* 权重总和提示 */}
      {weightsTotal !== 100 && (
        <Alert
          type="warning"
          message={`权重总和为 ${weightsTotal}，建议为 100（否则分数会被归一化）`}
          action={
            <Button size="small" onClick={normalize}>
              一键归一化
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={24}>
        {/* 左侧：权重雷达图 + 滑块 */}
        <Col span={12}>
          <Card title="4 维权重（雷达图 + 滑块联动）" style={{ marginBottom: 16 }}>
            <ReactECharts option={radarOption} style={{ height: 280 }} />

            <Divider />

            {/* 权重滑块 */}
            <WeightSlider
              label="职业度权重"
              value={weights.professional}
              onChange={(v) => updateWeight('professional', v)}
              help="在售商品 / 30天发布 / 描述中含职业关键词 → 扣分"
              revertPath="eval.weights.professional"
              originalValue={getFieldOriginal('eval.weights.professional')}
              onRevert={revertField}
            />
            <WeightSlider
              label="信誉权重"
              value={weights.credit}
              onChange={(v) => updateWeight('credit', v)}
              help="芝麻信用 / 实名认证 / 注册天数 → 加分"
              revertPath="eval.weights.credit"
              originalValue={getFieldOriginal('eval.weights.credit')}
              onRevert={revertField}
            />
            <WeightSlider
              label="纠纷权重"
              value={weights.dispute}
              onChange={(v) => updateWeight('dispute', v)}
              help="差评数 / 退款率 / 投诉 → 减分"
              revertPath="eval.weights.dispute"
              originalValue={getFieldOriginal('eval.weights.dispute')}
              onRevert={revertField}
            />
            <WeightSlider
              label="价格权重"
              value={weights.price}
              onChange={(v) => updateWeight('price', v)}
              help="商品价 / 市场价比例 → 加分"
              revertPath="eval.weights.price"
              originalValue={getFieldOriginal('eval.weights.price')}
              onRevert={revertField}
            />

            <Divider />
            <div style={{ textAlign: 'center' }}>
              <span
                className={`weight-total-indicator ${weightsTotal === 100 ? 'weight-total-ok' : 'weight-total-warn'}`}
              >
                权重总和：{weightsTotal}
                {weightsTotal === 100 ? ' ✓' : ' ⚠'}
              </span>
            </div>
          </Card>

          {/* 阈值配置 */}
          <Card title="阈值配置（一票否决标识）">
            <WeightSlider
              label="在售数阈值"
              value={thresholds.on_sale_count}
              onChange={(v) => updateThreshold('on_sale_count', v)}
              min={0}
              max={200}
              help="超过此值视为职业卖家"
            />
            <WeightSlider
              label="30 天发帖数阈值"
              value={thresholds.post_count_30d}
              onChange={(v) => updateThreshold('post_count_30d', v)}
              min={0}
              max={100}
              help="月发布超过此值视为职业"
            />
            <WeightSlider
              label="主营品类占比阈值"
              value={thresholds.top_category_ratio}
              onChange={(v) => updateThreshold('top_category_ratio', v)}
              min={0}
              max={1}
              step={0.05}
              help="单一类目占比超过此值视为职业"
              formatter={(v) => `${(v * 100).toFixed(0)}%`}
            />

            <Divider />

            {/* 一票否决项 */}
            <div style={{ marginBottom: 8 }}>
              <Tag color="red" icon={<ThunderboltOutlined />}>一票否决</Tag>
            </div>
            <WeightSlider
              label="信用分下限"
              value={thresholds.credit_score_min}
              onChange={(v) => updateThreshold('credit_score_min', v)}
              min={0}
              max={1000}
              help="低于此分一票否决（直接拒绝）"
            />
            <WeightSlider
              label="差评数上限"
              value={thresholds.bad_review_max}
              onChange={(v) => updateThreshold('bad_review_max', v)}
              min={0}
              max={20}
              help="超过此值一票否决"
            />
            <WeightSlider
              label="注册天数下限"
              value={thresholds.register_days_min}
              onChange={(v) => updateThreshold('register_days_min', v)}
              min={0}
              max={365}
              help="注册不满此天数加风险分"
            />
          </Card>
        </Col>

        {/* 右侧：通过阈值 + 分布预览 + 关键词 */}
        <Col span={12}>
          <div className="preview-panel">
            <Card title="通过阈值（双滑块）" style={{ marginBottom: 16 }}>
              {scoreOrderError && (
                <Alert
                  type="error"
                  message={`通过分数(${evalConfig.pass_score}) 不能大于自动抢单分数(${evalConfig.auto_buy_score})`}
                  style={{ marginBottom: 12 }}
                />
              )}
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8 }}>
                  <Space>
                    <strong>通过分数（pass_score）：</strong>
                    <Tag color="green">{evalConfig.pass_score}</Tag>
                    {evalConfig.pass_score !== getFieldOriginal('eval.pass_score') && (
                      <Button size="small" type="link" onClick={() => revertField('eval.pass_score')} style={{ padding: 0, fontSize: 12 }}>⏪</Button>
                    )}
                  </Space>
                  <span style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>≥ 此分数：通知用户</span>
                </div>
                <Slider
                  min={0}
                  max={100}
                  value={evalConfig.pass_score}
                  onChange={(v) =>
                    update({
                      eval: { ...evalConfig, pass_score: v },
                    })
                  }
                  marks={{ 0: '0', 60: '60', 80: '80', 100: '100' }}
                />
              </div>

              <div>
                <div style={{ marginBottom: 8 }}>
                  <Space>
                    <strong>自动抢单分数（auto_buy_score）：</strong>
                    <Tag color="orange">{evalConfig.auto_buy_score}</Tag>
                    {evalConfig.auto_buy_score !== getFieldOriginal('eval.auto_buy_score') && (
                      <Button size="small" type="link" onClick={() => revertField('eval.auto_buy_score')} style={{ padding: 0, fontSize: 12 }}>⏪</Button>
                    )}
                  </Space>
                  <span style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>≥ 此分数：全自动拍下</span>
                </div>
                <Slider
                  min={0}
                  max={100}
                  value={evalConfig.auto_buy_score}
                  onChange={(v) =>
                    update({
                      eval: { ...evalConfig, auto_buy_score: v },
                    })
                  }
                  marks={{ 0: '0', 60: '60', 80: '80', 100: '100' }}
                />
              </div>
            </Card>

            {/* AI 评估 + 自动官方采集配置 */}
            <Card
              title={
                <Space>
                  <RobotOutlined />
                  AI 评估与自动采集
                </Space>
              }
              style={{ marginBottom: 16 }}
            >
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Space>
                    <strong>AI 自动评估</strong>
                    <Tag color={evalConfig.ai_auto_eval ? 'green' : 'default'}>
                      {evalConfig.ai_auto_eval ? '已开启' : '已关闭'}
                    </Tag>
                  </Space>
                  <Switch
                    checked={evalConfig.ai_auto_eval}
                    onChange={(v) =>
                      update({ eval: { ...evalConfig, ai_auto_eval: v } })
                    }
                  />
                </div>
                <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>
                  开启后对通过规则评估的商品自动调用 AI 视觉评估（消耗 OpenAI token），AI 评估结果会实质性地影响总分和风险等级
                </div>
              </div>

              <Divider />

              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Space>
                    <strong>AI 深度分析</strong>
                    <Tag color={evalConfig.ai_auto_deep_analyze ? 'green' : 'default'}>
                      {evalConfig.ai_auto_deep_analyze ? '已开启' : '已关闭'}
                    </Tag>
                  </Space>
                  <Switch
                    checked={evalConfig.ai_auto_deep_analyze}
                    onChange={(v) =>
                      update({ eval: { ...evalConfig, ai_auto_deep_analyze: v } })
                    }
                  />
                </div>
                <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>
                  开启后对通过 AI 评估的商品自动进行深度分析（消耗更多 token），分析商品成色、真伪、性价比等维度
                </div>
              </div>

              <Divider />

              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Space>
                    <CloudDownloadOutlined />
                    <strong>自动官方采集</strong>
                    <Tag color={evalConfig.auto_collect_official ? 'green' : 'default'}>
                      {evalConfig.auto_collect_official ? '已开启' : '已关闭'}
                    </Tag>
                  </Space>
                  <Switch
                    checked={evalConfig.auto_collect_official}
                    onChange={(v) =>
                      update({ eval: { ...evalConfig, auto_collect_official: v } })
                    }
                  />
                </div>
                <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', marginBottom: 8 }}>
                  开启后对通过评估的商品自动调用官方采集，提取评价/留言等爬虫无法获取的数据做深度验证
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 13 }}>每轮最多采集</span>
                  <InputNumber
                    size="small"
                    min={1}
                    max={20}
                    value={evalConfig.auto_collect_max_per_run}
                    onChange={(v) =>
                      update({ eval: { ...evalConfig, auto_collect_max_per_run: v || 3 } })
                    }
                    style={{ width: 80 }}
                  />
                  <span style={{ fontSize: 13 }}>条（避免拖慢+反爬）</span>
                </div>
              </div>

              {/* 采集指标可视化：仅开关开启时展示，避免关闭后占用空间 */}
              {evalConfig.auto_collect_official && (
                <CollectStatsPanel
                  stats={collectStats}
                  loading={statsLoading}
                  lastRefreshStr={statsLastRefreshStr}
                  nextRefreshStr={statsNextRefreshStr}
                />
              )}

              <Divider style={{ margin: '12px 0' }} />

              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Space>
                    <ThunderboltOutlined />
                    <strong>AI 多轮优化建议</strong>
                    <Tag color={evalConfig.ai_multi_run_suggestion ? 'green' : 'default'}>
                      {evalConfig.ai_multi_run_suggestion ? '已开启' : '已关闭'}
                    </Tag>
                  </Space>
                  <Switch
                    checked={evalConfig.ai_multi_run_suggestion}
                    onChange={(v) =>
                      update({ eval: { ...evalConfig, ai_multi_run_suggestion: v } })
                    }
                  />
                </div>
                <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', marginBottom: 8 }}>
                  累积多轮运行数据后调用 AI 生成趋势洞察与优化建议，与单轮结论互补，提供更深层的策略调优方向
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 13 }}>每隔</span>
                  <InputNumber
                    size="small"
                    min={2}
                    max={20}
                    value={evalConfig.ai_suggestion_interval}
                    onChange={(v) =>
                      update({ eval: { ...evalConfig, ai_suggestion_interval: v || 5 } })
                    }
                    style={{ width: 80 }}
                  />
                  <span style={{ fontSize: 13 }}>轮生成一次（太小浪费 token，太大反馈滞后）</span>
                </div>
              </div>
            </Card>

            <Card
              title={
                <Space>
                  <DollarCircleOutlined />
                  任务价格区间梯度评分
                </Space>
              }
              style={{ marginBottom: 16 }}
            >
              <Alert
                type="info"
                showIcon={false}
                style={{ marginBottom: 12, fontSize: 12 }}
                message="价格维度会读取每个任务的 min_price / max_price；未配置任务区间时保持旧评分逻辑。"
              />
              <Table
                size="small"
                pagination={false}
                rowKey="range"
                dataSource={priceRangeGradientRules}
                columns={[
                  {
                    title: '以 600-800 元为例',
                    dataIndex: 'range',
                    key: 'range',
                    width: 120,
                    render: (v: string) => <Tag color="blue">{v}</Tag>,
                  },
                  {
                    title: '评分含义',
                    dataIndex: 'label',
                    key: 'label',
                  },
                  {
                    title: '价格分调整',
                    dataIndex: 'score',
                    key: 'score',
                    width: 110,
                    render: (v: string, row: { color: string }) => <Tag color={row.color}>{v}</Tag>,
                  },
                ]}
              />
              <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 8 }}>
                区间中段优先，靠近上下边缘轻扣分；超出区间会按偏离程度加重扣分，避免 1 元引流、配件价或明显偏高商品获得虚高评分。
              </div>
            </Card>

            <Card title="评估分布热力图（价格 × 评分）" style={{ marginBottom: 16 }}>
              <Spin spinning={distLoading}>
                {heatmapOption ? (
                  <>
                    <ReactECharts option={heatmapOption} style={{ height: 280 }} />
                    <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>
                      颜色越深表示该区间的商品数越多（近 7 天数据）。绿色区=通过，橙色区=自动抢单。
                    </div>
                  </>
                ) : (
                  <Empty description="暂无评估分布数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Spin>
            </Card>

            <Card title="职业关键词（标签编辑器 + 拖拽排序）">
              <TagEditor
                value={evalConfig.professional_keywords}
                onChange={(v) =>
                  update({
                    eval: { ...evalConfig, professional_keywords: v },
                  })
                }
                placeholder="输入职业关键词后回车，如：批发、代理"
                color="orange"
              />
              <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 8 }}>
                商品描述中包含这些关键词时，职业度评分会被扣减。
              </div>
            </Card>
          </div>
        </Col>
      </Row>

      <DiffPreviewModal
        open={diffModalOpen}
        diffChanges={diffChanges}
        loading={saving}
        onCancel={() => setDiffModalOpen(false)}
        onConfirm={handleConfirmSave}
      />
    </div>
  )
}

// 采集统计类型：与主组件 useState 推断的类型保持一致
type CollectStats = {
  total: number
  success: number
  failed: number
  success_rate: number
  is_paused: boolean
  fail_pause_threshold: number
  top_failures: Array<{ reason: string; count: number }>
}

// S3776 修复：采集统计区块原嵌套 5+ 个条件渲染（三元+&&+嵌套三元），提取为独立组件
// 为什么独立 useToken：组件内 token 仅用于此区块的颜色，主组件不再需要持有 token
function CollectStatsPanel({
  stats,
  loading,
  lastRefreshStr,
  nextRefreshStr,
}: {
  readonly stats: CollectStats | null
  readonly loading: boolean
  readonly lastRefreshStr: string
  readonly nextRefreshStr: string | null
}) {
  const { token } = theme.useToken()
  // 提前计算成功率颜色，避免 JSX 中嵌套三元（SonarQube S3358）
  let rateColor: string = 'red'
  if (stats) {
    if (stats.success_rate >= 0.8) {
      rateColor = 'green'
    } else if (stats.success_rate >= 0.5) {
      rateColor = 'orange'
    }
  }
  return (
    <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--xh-bg-spotlight)', borderRadius: 6, fontSize: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: 'var(--xh-text-secondary)', fontWeight: 500 }}>
          最近 24 小时采集统计
        </span>
        <span style={{ fontSize: 11, color: 'var(--xh-text-quaternary)' }}>
          {loading ? '刷新中...' : `更新于 ${lastRefreshStr}`}
          {nextRefreshStr && ` · 下次 ${nextRefreshStr}`}
        </span>
      </div>
      {stats ? (
        <>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 8 }}>
            <span>
              共 <strong style={{ color: 'var(--xh-text-primary)' }}>{stats.total}</strong> 次
            </span>
            <span>
              成功 <strong style={{ color: token.colorSuccess }}>{stats.success}</strong> 次
            </span>
            <span>
              失败{' '}
              <strong style={{ color: stats.failed > 0 ? token.colorError : 'var(--xh-text-primary)' }}>
                {stats.failed}
              </strong>{' '}
              次
            </span>
            <span>
              成功率{' '}
              <Tag color={rateColor}>
                {(stats.success_rate * 100).toFixed(1)}%
              </Tag>
            </span>
          </div>
          {/* 退避暂停状态：后端根据最近一条失败事件的 consecutive_failures 判断 */}
          {/* 为什么用 is_paused 而非 failed >= 3：failed 是累计数，连续失败语义需看最近一次计数 */}
          {stats.is_paused && (
            <div style={{ marginBottom: 8 }}>
              <Tag color="red">
                已暂停（连续失败达阈值 {stats.fail_pause_threshold} 次）
              </Tag>
              <span style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', marginLeft: 8 }}>
                本轮剩余商品跳过采集，下轮自动重试
              </span>
            </div>
          )}
          {/* Top3 失败原因：仅在失败数 > 0 时展示，避免成功时占位 */}
          {stats.failed > 0 && stats.top_failures.length > 0 && (
            <div>
              <div style={{ color: 'var(--xh-text-tertiary)', marginBottom: 4 }}>主要失败原因：</div>
              <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--xh-text-secondary)' }}>
                {stats.top_failures.map((f) => (
                  <li key={`${f.reason}-${f.count}`} style={{ fontSize: 11 }}>
                    <span style={{ color: 'var(--xh-text-primary)' }}>{f.reason}</span>
                    <span style={{ color: 'var(--xh-text-quaternary)', marginLeft: 8 }}>×{f.count}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : (
        <span style={{ color: 'var(--xh-text-tertiary)' }}>
          {loading ? '加载中...' : '暂无数据'}
        </span>
      )}
    </div>
  )
}

// ============== 权重滑块组件 ==============
function WeightSlider({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  help,
  formatter,
  revertPath,
  originalValue,
  onRevert,
}: {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly label: string
  readonly value: number
  readonly onChange: (v: number) => void
  readonly min?: number
  readonly max?: number
  readonly step?: number
  readonly help?: string
  readonly formatter?: (v: number) => string
  readonly revertPath?: string
  readonly originalValue?: unknown
  readonly onRevert?: (path: string) => void
}) {
  // 仅当值与原始值不同时显示回滚按钮
  const showRevert = revertPath && originalValue !== undefined && value !== originalValue
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 500 }}>{label}</span>
        <Space size={4}>
          {showRevert && (
            <Button size="small" type="link" onClick={() => onRevert?.(revertPath)} style={{ padding: 0, fontSize: 12 }}>
              ⏪
            </Button>
          )}
          <InputNumber
            size="small"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(v) => onChange(v || 0)}
            style={{ width: 80 }}
            formatter={formatter ? (v) => formatter(v || 0) : undefined}
          />
        </Space>
      </div>
      <Slider
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={onChange}
        tooltip={{ formatter: formatter ? (v) => formatter(v || 0) : undefined }}
      />
      {help && <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>{help}</div>}
    </div>
  )
}
