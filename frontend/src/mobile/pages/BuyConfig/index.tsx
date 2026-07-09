// frontend/src/mobile/pages/BuyConfig/index.tsx
// 移动端抢单策略：auto_buy_score 阈值 + 抢单模式说明
// 设计要点：auto_buy_score 在全局 eval 配置中，buy_mode 是任务级参数
// 移动端仅展示和调整全局阈值，任务级 buy_mode 在任务编辑页设置
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Spin, App, Slider, Button, Space, Alert, theme, Tag, Descriptions,
} from 'antd'
import { SaveOutlined, ReloadOutlined } from '@ant-design/icons'
import { configApi } from '../../../api/config'
import { extractApiError } from '../../../utils/apiError'

type EvalConfig = Pick<import('../../../api/types').AppConfig['eval'], 'pass_score' | 'auto_buy_score'>

export default function MobileBuyConfig() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [form, setForm] = useState<EvalConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const cfg = await configApi.get()
      setForm({ pass_score: cfg.eval.pass_score, auto_buy_score: cfg.eval.auto_buy_score })
    } catch (e) {
      message.error(extractApiError(e, '加载失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void load() }, [load])

  const save = async (): Promise<void> => {
    if (!form) return
    if (form.pass_score > form.auto_buy_score) {
      message.error('通过分数不能大于自动抢单分数', 3)
      return
    }
    setSaving(true)
    try {
      const cfg = await configApi.get()
      await configApi.save({
        ...cfg,
        eval: { ...cfg.eval, auto_buy_score: form.auto_buy_score },
      })
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
        message="auto_buy_score 控制自动抢单的触发阈值"
        description="评估分数 ≥ auto_buy_score 时触发自动抢单。低于 pass_score 的商品不会通过评估。"
        style={{ marginBottom: 12, fontSize: 12 }}
      />

      <Card size="small" style={{ marginBottom: 12 }} title="自动抢单分数">
        <div style={{ textAlign: 'center', marginBottom: 12 }}>
          <span style={{ fontSize: 36, fontWeight: 600, color: '#E20613' }}>
            {form.auto_buy_score}
          </span>
          <span style={{ fontSize: 14, color: themeToken.colorTextSecondary }}> / 100</span>
        </div>
        <Slider
          value={form.auto_buy_score}
          onChange={(v) => setForm({ ...form, auto_buy_score: v })}
          min={0}
          max={100}
          marks={{
            0: '0',
            60: '60',
            80: { label: '80', style: { color: '#E20613' } },
            100: '100',
          }}
        />
        <div style={{ fontSize: 11, color: themeToken.colorTextTertiary, marginTop: 8 }}>
          建议设置在 80 以上，过低可能导致误抢
        </div>
      </Card>

      <Card size="small" style={{ marginBottom: 12 }} title="分数关系">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="通过分数">
            <Tag color="blue">{form.pass_score}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="自动抢单分数">
            <Tag color="orange">{form.auto_buy_score}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="区间">
            <Tag color={form.auto_buy_score - form.pass_score >= 10 ? 'green' : 'red'}>
              差值 {form.auto_buy_score - form.pass_score}
            </Tag>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card size="small" style={{ marginBottom: 12 }} title="抢单模式说明">
        <Space direction="vertical" size={8} style={{ fontSize: 13 }}>
          <div>
            <Tag color="green">auto</Tag>
            <span style={{ color: themeToken.colorTextSecondary }}>全自动（分数达标即抢单）</span>
          </div>
          <div>
            <Tag color="blue">notify</Tag>
            <span style={{ color: themeToken.colorTextSecondary }}>仅通知（需手动确认）</span>
          </div>
          <div>
            <Tag>manual</Tag>
            <span style={{ color: themeToken.colorTextSecondary }}>手动模式（仅采集不操作）</span>
          </div>
          <Alert
            type="warning"
            showIcon
            message="抢单模式为任务级参数"
            description="请在任务编辑页设置每个任务的抢单模式。"
            style={{ fontSize: 12, marginTop: 4 }}
          />
        </Space>
      </Card>

      <Space size={8} style={{ width: '100%' }}>
        <Button icon={<ReloadOutlined />} onClick={() => void load()} style={{ flex: 1 }}>
          重新加载
        </Button>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save} style={{ flex: 2 }}>
          保存配置
        </Button>
      </Space>
    </div>
  )
}
