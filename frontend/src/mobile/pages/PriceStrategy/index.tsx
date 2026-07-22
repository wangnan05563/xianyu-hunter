// frontend/src/mobile/pages/PriceStrategy/index.tsx
// 移动端价格策略配置：区间上限/下限/市场比/Top N 四个开关 + 数值
// 设计要点：相比桌面端去掉三段区间批量配置，保留核心单段区间 + 数值可视化
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Spin, App, Switch, InputNumber, Button, Space, Alert, theme, Tag,
} from 'antd'
import { SaveOutlined, ReloadOutlined } from '@ant-design/icons'
import { configApi } from '../../../api/config'
import { extractApiError } from '../../../utils/apiError'

// 价格策略单条配置项类型（与 AppConfig.price_strategy 对齐）
interface PriceStrategy {
  enabled_max: boolean
  max_price: number
  enabled_min: boolean
  min_price: number
  enabled_market_ratio: boolean
  market_ratio: number
  enabled_top_n: boolean
  top_n: number
}

export default function MobilePriceStrategy() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [form, setForm] = useState<PriceStrategy | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const cfg = await configApi.get()
      setForm(cfg.price_strategy)
    } catch (e) {
      message.error(extractApiError(e, '加载失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void load() }, [load])

  // 保存：完整替换 price_strategy 段
  const save = async (): Promise<void> => {
    if (!form) return
    setSaving(true)
    try {
      const cfg = await configApi.get()
      await configApi.save({ ...cfg, price_strategy: form })
      message.success('已保存')
    } catch (e) {
      message.error(extractApiError(e, '保存失败'), 3)
    } finally {
      setSaving(false)
    }
  }

  if (loading || !form) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  return (
    <div>
      <Alert
        type="info"
        showIcon
        message="价格策略对所有任务生效"
        description="当多个条件同时启用时，系统取交集。任务级覆盖请在任务编辑页设置。"
        style={{ marginBottom: 12, fontSize: 12 }}
      />

      {/* 上限 */}
      <Card size="small" style={{ marginBottom: 10 }} title="价格上限">
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13 }}>启用</span>
            <Switch
              checked={form.enabled_max}
              onChange={(v) => setForm({ ...form, enabled_max: v })}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              最高价格（元）
            </div>
            <InputNumber
              value={form.max_price}
              onChange={(v) => v !== null && setForm({ ...form, max_price: v })}
              min={0}
              max={1000000}
              step={10}
              disabled={!form.enabled_max}
              style={{ width: '100%' }}
              addonAfter="¥" /* NOSONAR - addonAfter 在 antd 5.x 仍可用，迁移到 InputNumber.Group 会破坏现有布局，暂不迁移 */
            />
          </div>
        </Space>
      </Card>

      {/* 下限 */}
      <Card size="small" style={{ marginBottom: 10 }} title="价格下限">
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13 }}>启用</span>
            <Switch
              checked={form.enabled_min}
              onChange={(v) => setForm({ ...form, enabled_min: v })}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              最低价格（元）
            </div>
            <InputNumber
              value={form.min_price}
              onChange={(v) => v !== null && setForm({ ...form, min_price: v })}
              min={0}
              max={1000000}
              step={10}
              disabled={!form.enabled_min}
              style={{ width: '100%' }}
              addonAfter="¥" /* NOSONAR - addonAfter 在 antd 5.x 仍可用，迁移到 InputNumber.Group 会破坏现有布局，暂不迁移 */
            />
          </div>
        </Space>
      </Card>

      {/* 市场价倍数 */}
      <Card size="small" style={{ marginBottom: 10 }} title="市场价倍数">
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13 }}>启用</span>
            <Switch
              checked={form.enabled_market_ratio}
              onChange={(v) => setForm({ ...form, enabled_market_ratio: v })}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              低于市场均价的比例（0~1）
            </div>
            <InputNumber
              value={form.market_ratio}
              onChange={(v) => v !== null && setForm({ ...form, market_ratio: v })}
              min={0}
              max={1}
              step={0.05}
              disabled={!form.enabled_market_ratio}
              style={{ width: '100%' }}
            />
            <div style={{ fontSize: 11, color: themeToken.colorTextTertiary, marginTop: 4 }}>
              例如 0.8 = 价格低于均价 80% 时通过
            </div>
          </div>
        </Space>
      </Card>

      {/* Top N */}
      <Card size="small" style={{ marginBottom: 12 }} title="同类 Top N">
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13 }}>启用</span>
            <Switch
              checked={form.enabled_top_n}
              onChange={(v) => setForm({ ...form, enabled_top_n: v })}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              仅取价格最低前 N 个
            </div>
            <InputNumber
              value={form.top_n}
              onChange={(v) => v !== null && setForm({ ...form, top_n: v })}
              min={1}
              max={100}
              step={1}
              disabled={!form.enabled_top_n}
              style={{ width: '100%' }}
            />
          </div>
        </Space>
      </Card>

      {/* 启停状态总览 */}
      <Card size="small" style={{ marginBottom: 12 }} title="当前生效">
        <Space size={4} wrap>
          <Tag color={form.enabled_max ? 'blue' : 'default'}>上限 {form.max_price}¥</Tag>
          <Tag color={form.enabled_min ? 'blue' : 'default'}>下限 {form.min_price}¥</Tag>
          <Tag color={form.enabled_market_ratio ? 'blue' : 'default'}>均价 ×{form.market_ratio}</Tag>
          <Tag color={form.enabled_top_n ? 'blue' : 'default'}>Top {form.top_n}</Tag>
        </Space>
      </Card>

      {/* 操作栏：固定底部 */}
      <Space size={8} style={{ width: '100%' }}>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => void load()}
          style={{ flex: 1 }}
        >
          重新加载
        </Button>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          loading={saving}
          onClick={save}
          style={{ flex: 2 }}
        >
          保存配置
        </Button>
      </Space>
    </div>
  )
}
