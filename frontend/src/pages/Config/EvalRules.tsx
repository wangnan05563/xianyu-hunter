import { useEffect, useState } from 'react'
import { Card, Slider, InputNumber, Row, Col, Button, Space, message, Divider, Tag, Alert, Spin, Empty, Modal, Table } from 'antd'
import { SaveOutlined, UndoOutlined, ThunderboltOutlined } from '@ant-design/icons'
import ReactECharts from '../../components/charts/EChart'
import { useConfigStore } from '../../stores/configStore'
import { extractApiError } from '../../utils/apiError'
import type { DiffChange } from '../../stores/configStore'
import { evalApi } from '../../api'
import TagEditor from '../../components/editors/TagEditor'

export default function EvalRules() {
  const { config, load, save, hasChanges, reset, update, previewSave, confirmSave, getFieldOriginal, revertField } = useConfigStore()
  const [loading, setLoading] = useState(false)
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
  const heatmapData: Array<[number, number, number]> = []
  let heatmapMax = 1
  const xLabels: string[] = []
  const yLabels: string[] = []

  if (distData && distData.buckets?.length) {
    const sBins = distData.buckets.length
    const pBins = distData.buckets[0]?.length || 5
    const [pMin, pMax] = distData.price_range || [0, 5000]
    const pStep = (pMax - pMin) / pBins
    const sStep = 100 / sBins

    // X轴标签（价格区间）
    for (let i = 0; i < pBins; i++) {
      const lo = Math.round(pMin + i * pStep)
      const hi = Math.round(pMin + (i + 1) * pStep)
      xLabels.push(`¥${lo}~${hi}`)
    }
    // Y轴标签（评分区间，从高到低）
    for (let i = 0; i < sBins; i++) {
      const hi = Math.round(100 - i * sStep)
      const lo = Math.round(100 - (i + 1) * sStep)
      yLabels.push(`${lo}-${hi}`)
    }

    // 构建热力图数据 [x, y, value]
    distData.buckets.forEach((row, si) => {
      row.forEach((bucket, pi) => {
        heatmapData.push([pi, si, bucket.count])
        if (bucket.count > heatmapMax) heatmapMax = bucket.count
      })
    })
  }

  const heatmapOption = distData && distData.buckets?.length ? {
    tooltip: {
      position: 'top',
      formatter: (p: { dataIndex: [number, number]; value: number }) => {
        const [pi, si] = p.dataIndex
        const bucket = distData.buckets[si]?.[pi]
        if (!bucket || bucket.count === 0) return '该区间暂无商品'
        return `${xLabels[pi]} × ${yLabels[si]}<br/>商品数：${bucket.count}<br/>可抢：${bucket.auto} / 通过：${bucket.pass} / 驳回：${bucket.fail}`
      },
    },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: xLabels,
      name: '价格',
      splitArea: { show: true },
      axisLabel: { fontSize: 9, rotate: 30 },
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      name: '评分',
      splitArea: { show: true },
      axisLabel: { fontSize: 9 },
    },
    visualMap: {
      min: 0,
      max: heatmapMax,
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
        data: heatmapData,
        label: {
          show: true,
          formatter: (p: { value: number }) => p.value > 0 ? String(p.value) : '',
          fontSize: 9,
        },
      },
    ],
  } : null

  const handleSave = async () => {
    if (weightsTotal !== 100) {
      message.error('权重总和必须为 100，请调整后保存')
      return
    }
    if (scoreOrderError) {
      message.error('通过分数不能大于自动抢单分数')
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
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>🛡️ 评估规则可视化配置</h2>
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

      {/* Diff 预览 Modal */}
      <Modal
        title="配置变更预览"
        open={diffModalOpen}
        onCancel={() => setDiffModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setDiffModalOpen(false)}>
            取消
          </Button>,
          <Button key="confirm" type="primary" loading={saving} onClick={handleConfirmSave}>
            确认保存
          </Button>,
        ]}
        width={700}
      >
        <Table
          dataSource={diffChanges}
          rowKey="path"
          pagination={false}
          size="small"
          columns={[
            { title: '路径', dataIndex: 'path', key: 'path' },
            { title: '原值', dataIndex: 'old_value', key: 'old_value', render: (v) => v == null ? '-' : String(v) },
            { title: '新值', dataIndex: 'new_value', key: 'new_value', render: (v) => v == null ? '-' : String(v) },
            {
              title: '操作',
              dataIndex: 'op',
              key: 'op',
              render: (op: string) => (
                <Tag color={op === 'add' ? 'green' : op === 'delete' ? 'red' : 'orange'}>
                  {op === 'add' ? '新增' : op === 'delete' ? '删除' : '修改'}
                </Tag>
              ),
            },
          ]}
        />
      </Modal>
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
  label: string
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
  help?: string
  formatter?: (v: number) => string
  revertPath?: string
  originalValue?: unknown
  onRevert?: (path: string) => void
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
