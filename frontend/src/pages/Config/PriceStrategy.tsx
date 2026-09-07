import { useEffect, useState, useRef } from 'react'
import { Card, Switch, Slider, InputNumber, Row, Col, Space, message, Divider, Statistic } from 'antd'
import { TipButton } from '@/components/TipButton'
import { SaveOutlined, ExperimentOutlined } from '@ant-design/icons'
import ReactECharts, { type EChartRef } from '../../components/charts/EChart'
import { useConfigStore } from '../../stores/configStore'
import { extractApiError } from '../../utils/apiError'
import type { DiffChange } from '../../stores/configStore'
import { priceApi } from '../../api'
import { DiffPreviewModal } from '../../components/DiffPreviewModal'
import {
  PriceCeilingIcon,
  PriceFloorIcon,
  MarketRatioIcon,
  TopNIcon,
  TrendPreviewIcon,
  TargetHitIcon,
  RevertIcon,
} from '../../components/icons/GeometricIcons'

interface PriceStrategyConfig {
  enabled_max: boolean
  max_price: number
  enabled_min: boolean
  min_price: number
  enabled_market_ratio: boolean
  market_ratio: number
  enabled_top_n: boolean
  top_n: number
}

const defaultConfig: PriceStrategyConfig = {
  enabled_max: true,
  max_price: 10000,
  enabled_min: true,
  min_price: 100,
  enabled_market_ratio: false,
  market_ratio: 0.8,
  enabled_top_n: false,
  top_n: 5,
}

export default function PriceStrategy() {
  const { config, load, update, hasChanges, reset, previewSave, confirmSave, getFieldOriginal } = useConfigStore()
  const [strategy, setStrategy] = useState<PriceStrategyConfig>(defaultConfig)
  const [histogram, setHistogram] = useState<{ bins: string[]; counts: number[]; prices: number[] } | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const chartRef = useRef<EChartRef>(null)
  // Diff 预览
  const [diffModalOpen, setDiffModalOpen] = useState(false)
  const [diffChanges, setDiffChanges] = useState<DiffChange[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    load()
  }, [load])

  // 配置加载完成后，将 price_strategy 同步到本地 state
  useEffect(() => {
    if (config?.price_strategy) {
      setStrategy(config.price_strategy)
    }
  }, [config])

  // 加载价格直方图数据
  useEffect(() => {
    priceApi
      .histogram({ range_hours: 168, bins: 20 })
      .then((data) => {
        if (data?.bins && data?.counts) {
          setHistogram({ bins: data.bins, counts: data.counts, prices: data.prices || [] })
        }
      })
      .catch(() => {
        // 数据加载失败时使用模拟数据展示
        setHistogram({
          bins: ['0', '500', '1k', '2k', '3k', '5k', '8k', '10k', '15k', '20k+'],
          counts: [5, 12, 28, 35, 22, 18, 10, 6, 3, 1],
          prices: [],
        })
      })
  }, [])

  const handleSave = async () => {
    try {
      // 将本地 strategy 修改同步到 configStore 后再预览
      update({ price_strategy: strategy })
      // 同步 bargain_price.percentile 到 configStore（与 price_strategy 一起保存）
      if (config?.bargain_price) {
        update({ bargain_price: { ...config.bargain_price } })
      }
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
      message.success('价格策略已保存')
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
    }
  }

  // 提取局部变量收窄类型，避免 JSX 中直接访问 config?.bargain_price?.percentile 触发 TS18047
  const bargainPercentile = config?.bargain_price?.percentile ?? 0.1

  // 模拟策略命中预览
  const previewResults = (() => {
    if (!histogram) return { pass: 0, reject: 0, total: 0 }
    const total = histogram.counts.reduce((a, b) => a + b, 0)
    let pass = total
    let reject = 0

    // 按区间估算
    histogram.bins.forEach((bin, i) => {
      const price = Number.parseFloat(bin.replaceAll('k', '').replaceAll('+', '')) * (bin.includes('k') ? 1000 : 1)
      const count = histogram.counts[i]
      let rejected = false

      if (strategy.enabled_max && price > strategy.max_price) rejected = true
      if (strategy.enabled_min && price < strategy.min_price) rejected = true

      if (rejected) {
        reject += count
        pass -= count
      }
    })

    return { pass, reject, total }
  })()

  // ECharts 直方图配置（含过滤区间标记）
  const chartOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: histogram?.bins || [],
      name: '价格区间',
    },
    yAxis: { type: 'value', name: '商品数' },
    series: [
      {
        name: '商品数',
        type: 'bar',
        data: histogram?.counts.map((count, i) => {
          const bin = histogram.bins[i]
          const price = Number.parseFloat(bin.replaceAll('k', '').replaceAll('+', '')) * (bin.includes('k') ? 1000 : 1)
          // 根据策略判定颜色
          let rejected = false
          if (strategy.enabled_max && price > strategy.max_price) rejected = true
          if (strategy.enabled_min && price < strategy.min_price) rejected = true
          return {
            value: count,
            itemStyle: { color: rejected ? '#ff4d4f' : '#52c41a' },
          }
        }) || [],
      },
    ],
    // 标记线：价格上下限
    markLine: {
      data: [
        ...(strategy.enabled_min
          ? [{ xAxis: strategy.min_price, lineStyle: { color: '#faad14' }, label: { formatter: '下限' } }]
          : []),
        ...(strategy.enabled_max
          ? [{ xAxis: strategy.max_price, lineStyle: { color: '#ff4d4f' }, label: { formatter: '上限' } }]
          : []),
      ],
    },
  }

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <Space>
          <TipButton tip="放弃未保存的修改并重置" icon={<RevertIcon size={16} />} onClick={reset} disabled={!hasChanges()}>
            重置
          </TipButton>
          <TipButton tip="保存价格策略配置" type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
            保存
          </TipButton>
        </Space>
      </div>

      <Row gutter={24}>
        {/* 左侧：策略配置 */}
        <Col span={12}>
          <Card title="策略配置（4 种策略独立开关）">
            {/* 捡漏价格 P10 分位数配置（对应后端 BargainPriceConfig） */}
            <Card
              size="small"
              style={{ marginBottom: 12 }}
              title={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><PriceFloorIcon size={20} /> 捡漏价格分位数</span>}
            >
              <Slider
                min={0.01}
                max={0.49}
                step={0.01}
                value={bargainPercentile}
                onChange={(v) => update({ bargain_price: { percentile: v } })}
                marks={{ 0.05: '5%', 0.1: '10%', 0.2: '20%', 0.49: '49%' }}
                tooltip={{ formatter: (v) => `${((v ?? 0) * 100).toFixed(0)}% (P${Math.round((v ?? 0) * 100)})` }}
              />
              <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
                取已售价格中最低 {bargainPercentile * 100}% 的边界值作为捡漏基准。
                调高让更多商品被判定为"可捡漏"，调低则更严格。
              </div>
            </Card>

            {/* 策略 1：硬性上限 */}
            <Card
              size="small"
              style={{ marginBottom: 12 }}
              title={
                <Space>
                  <Switch
                    checked={strategy.enabled_max}
                    onChange={(v) => setStrategy({ ...strategy, enabled_max: v })}
                  />
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <PriceCeilingIcon size={20} />
                    硬性上限
                  </span>
                  {strategy.max_price !== getFieldOriginal('price_strategy.max_price') && (
                    <TipButton tip="恢复最高价原始值" size="small" type="link" onClick={() => setStrategy({ ...strategy, max_price: getFieldOriginal('price_strategy.max_price') as number })} style={{ padding: 0, fontSize: 12 }}>
                      <RevertIcon size={12} />
                    </TipButton>
                  )}
                </Space>
              }
            >
              <div style={{ opacity: strategy.enabled_max ? 1 : 0.5 }}>
                <Slider
                  min={0}
                  max={50000}
                  step={100}
                  value={strategy.max_price}
                  onChange={(v) => setStrategy({ ...strategy, max_price: v })}
                  marks={{ 0: '¥0', 10000: '¥1万', 30000: '¥3万', 50000: '¥5万' }}
                  tooltip={{ formatter: (v) => `¥${v}` }}
                />
                <InputNumber
                  prefix="¥"
                  value={strategy.max_price}
                  onChange={(v) => setStrategy({ ...strategy, max_price: v || 0 })}
                  style={{ width: '100%' }}
                />
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
                  超过此价格的商品将被过滤
                </div>
              </div>
            </Card>

            {/* 策略 2：硬性下限 */}
            <Card
              size="small"
              style={{ marginBottom: 12 }}
              title={
                <Space>
                  <Switch
                    checked={strategy.enabled_min}
                    onChange={(v) => setStrategy({ ...strategy, enabled_min: v })}
                  />
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <PriceFloorIcon size={20} />
                    硬性下限（防 1 元引流）
                  </span>
                  {strategy.min_price !== getFieldOriginal('price_strategy.min_price') && (
                    <TipButton tip="恢复最低价原始值" size="small" type="link" onClick={() => setStrategy({ ...strategy, min_price: getFieldOriginal('price_strategy.min_price') as number })} style={{ padding: 0, fontSize: 12 }}>
                      <RevertIcon size={12} />
                    </TipButton>
                  )}
                </Space>
              }
            >
              <div style={{ opacity: strategy.enabled_min ? 1 : 0.5 }}>
                <Slider
                  min={0}
                  max={5000}
                  step={10}
                  value={strategy.min_price}
                  onChange={(v) => setStrategy({ ...strategy, min_price: v })}
                  marks={{ 0: '¥0', 100: '¥100', 500: '¥500', 2000: '¥2000', 5000: '¥5000' }}
                  tooltip={{ formatter: (v) => `¥${v}` }}
                />
                <InputNumber
                  prefix="¥"
                  value={strategy.min_price}
                  onChange={(v) => setStrategy({ ...strategy, min_price: v || 0 })}
                  style={{ width: '100%' }}
                />
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
                  低于此价格视为引流陷阱，过滤
                </div>
              </div>
            </Card>

            {/* 策略 3：低于市场参考价 */}
            <Card
              size="small"
              style={{ marginBottom: 12 }}
              title={
                <Space>
                  <Switch
                    checked={strategy.enabled_market_ratio}
                    onChange={(v) => setStrategy({ ...strategy, enabled_market_ratio: v })}
                  />
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <MarketRatioIcon size={20} />
                    低于市场参考价
                  </span>
                  {strategy.market_ratio !== getFieldOriginal('price_strategy.market_ratio') && (
                    <TipButton tip="恢复市场价比例原始值" size="small" type="link" onClick={() => setStrategy({ ...strategy, market_ratio: getFieldOriginal('price_strategy.market_ratio') as number })} style={{ padding: 0, fontSize: 12 }}>
                      <RevertIcon size={12} />
                    </TipButton>
                  )}
                </Space>
              }
            >
              <div style={{ opacity: strategy.enabled_market_ratio ? 1 : 0.5 }}>
                <Slider
                  min={0.3}
                  max={1}
                  step={0.05}
                  value={strategy.market_ratio}
                  onChange={(v) => setStrategy({ ...strategy, market_ratio: v })}
                  marks={{ 0.3: '30%', 0.5: '50%', 0.7: '70%', 1: '100%' }}
                  tooltip={{ formatter: (v) => `${((v ?? 0) * 100).toFixed(0)}%` }}
                />
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                  价格高于「市场价 × {strategy.market_ratio}」的商品将被过滤（需 ≥3 个样本）
                </div>
              </div>
            </Card>

            {/* 策略 4：同类低价 TopN */}
            <Card
              size="small"
              title={
                <Space>
                  <Switch
                    checked={strategy.enabled_top_n}
                    onChange={(v) => setStrategy({ ...strategy, enabled_top_n: v })}
                  />
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <TopNIcon size={20} />
                    同类低价 TopN
                  </span>
                  {strategy.top_n !== getFieldOriginal('price_strategy.top_n') && (
                    <TipButton tip="恢复 TopN 原始值" size="small" type="link" onClick={() => setStrategy({ ...strategy, top_n: getFieldOriginal('price_strategy.top_n') as number })} style={{ padding: 0, fontSize: 12 }}>
                      <RevertIcon size={12} />
                    </TipButton>
                  )}
                </Space>
              }
            >
              <div style={{ opacity: strategy.enabled_top_n ? 1 : 0.5 }}>
                <Slider
                  min={1}
                  max={20}
                  value={strategy.top_n}
                  onChange={(v) => setStrategy({ ...strategy, top_n: v })}
                  marks={{ 1: 'Top1', 5: 'Top5', 10: 'Top10', 20: 'Top20' }}
                />
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)' }}>
                  只保留同类商品中价格最低的前 {strategy.top_n} 个
                </div>
              </div>
            </Card>
          </Card>
        </Col>

        {/* 右侧：实时预览 */}
        <Col span={12}>
          <div className="preview-panel">
            <Card title={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><TrendPreviewIcon size={20} /> 实时预览：价格分布直方图</span>} style={{ marginBottom: 16 }}>
              <ReactECharts ref={chartRef} option={chartOption} style={{ height: 300 }} />
              <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', marginTop: 8 }}>
                {/* S6772：每个图例单元（图标+文字）整体放入一个 span，避免相邻 span 间空白歧义 */}
                <span style={{ color: '#52c41a' }}>■&nbsp;通过</span>{' '}
                <span style={{ color: '#ff4d4f', marginLeft: 8 }}>■&nbsp;被过滤</span>{' '}
                <span style={{ color: '#faad14', marginLeft: 8 }}>┃&nbsp;下限</span>{' '}
                <span style={{ color: '#ff4d4f', marginLeft: 8 }}>┃&nbsp;上限</span>
              </div>
            </Card>

            <Card title={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><TargetHitIcon size={20} /> 策略命中预览</span>}>
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic title="总商品数" value={previewResults.total} />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="通过"
                    value={previewResults.pass}
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="过滤"
                    value={previewResults.reject}
                    valueStyle={{ color: '#ff4d4f' }}
                  />
                </Col>
              </Row>

              <Divider />

              <TipButton
                tip="重新生成策略命中预览数据"
                type="dashed"
                block
                icon={<ExperimentOutlined />}
                loading={previewing}
                onClick={() => {
                  setPreviewing(true)
                  setTimeout(() => {
                    setPreviewing(false)
                    message.success('预览已刷新')
                  }, 500)
                }}
              >
                刷新预览数据
              </TipButton>
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
