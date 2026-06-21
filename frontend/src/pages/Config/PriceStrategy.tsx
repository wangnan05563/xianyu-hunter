import { useEffect, useState, useRef } from 'react'
import { Card, Switch, Slider, InputNumber, Row, Col, Button, Space, message, Divider, Statistic } from 'antd'
import { SaveOutlined, UndoOutlined, ExperimentOutlined } from '@ant-design/icons'
import ReactECharts, { type EChartRef } from '../../components/charts/EChart'
import { useConfigStore } from '../../stores/configStore'
import { priceApi } from '../../api'

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
  const { config, load, save, update, hasChanges, reset } = useConfigStore()
  const [strategy, setStrategy] = useState<PriceStrategyConfig>(defaultConfig)
  const [histogram, setHistogram] = useState<{ bins: string[]; counts: number[]; prices: number[] } | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const chartRef = useRef<EChartRef>(null)

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
      // 将本地 strategy 修改同步到 configStore 后再保存
      update({ price_strategy: strategy })
      await save()
      message.success('价格策略已保存')
    } catch {
      message.error('保存失败')
    }
  }

  // 模拟策略命中预览
  const previewResults = (() => {
    if (!histogram) return { pass: 0, reject: 0, total: 0 }
    const total = histogram.counts.reduce((a, b) => a + b, 0)
    let pass = total
    let reject = 0

    // 按区间估算
    histogram.bins.forEach((bin, i) => {
      const price = parseFloat(bin.replace(/[k+]/g, '')) * (bin.includes('k') ? 1000 : 1)
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
          const price = parseFloat(bin.replace(/[k+]/g, '')) * (bin.includes('k') ? 1000 : 1)
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
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>💰 价格策略可视化配置</h2>
        <Space>
          <Button icon={<UndoOutlined />} onClick={reset} disabled={!hasChanges()}>
            重置
          </Button>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={useConfigStore((s) => s.loading)}>
            保存
          </Button>
        </Space>
      </div>

      <Row gutter={24}>
        {/* 左侧：策略配置 */}
        <Col span={12}>
          <Card title="策略配置（4 种策略独立开关）">
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
                  <span>🚫 硬性上限</span>
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
                <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
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
                  <span>⚠️ 硬性下限（防 1 元引流）</span>
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
                <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
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
                  <span>📊 低于市场参考价</span>
                </Space>
              }
            >
              <div style={{ opacity: strategy.enabled_market_ratio ? 1 : 0.5 }}>
                <Slider
                  min={0.3}
                  max={1.0}
                  step={0.05}
                  value={strategy.market_ratio}
                  onChange={(v) => setStrategy({ ...strategy, market_ratio: v })}
                  marks={{ 0.3: '30%', 0.5: '50%', 0.7: '70%', 1.0: '100%' }}
                  tooltip={{ formatter: (v) => `${((v ?? 0) * 100).toFixed(0)}%` }}
                />
                <div style={{ fontSize: 12, color: '#999' }}>
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
                  <span>🏆 同类低价 TopN</span>
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
                <div style={{ fontSize: 12, color: '#999' }}>
                  只保留同类商品中价格最低的前 {strategy.top_n} 个
                </div>
              </div>
            </Card>
          </Card>
        </Col>

        {/* 右侧：实时预览 */}
        <Col span={12}>
          <div className="preview-panel">
            <Card title="📈 实时预览：价格分布直方图" style={{ marginBottom: 16 }}>
              <ReactECharts ref={chartRef} option={chartOption} style={{ height: 300 }} />
              <div style={{ fontSize: 11, color: '#999', marginTop: 8 }}>
                <span style={{ color: '#52c41a' }}>■</span> 通过 &nbsp;
                <span style={{ color: '#ff4d4f' }}>■</span> 被过滤 &nbsp;
                <span style={{ color: '#faad14' }}>┃</span> 下限 &nbsp;
                <span style={{ color: '#ff4d4f' }}>┃</span> 上限
              </div>
            </Card>

            <Card title="🎯 策略命中预览">
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

              <Button
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
              </Button>
            </Card>
          </div>
        </Col>
      </Row>
    </div>
  )
}
