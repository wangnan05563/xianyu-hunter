// frontend/src/mobile/pages/EvalRules/index.tsx
// 移动端评估规则：权重 + 阈值 + 通过/自动抢单分数 + AI 评估开关
// 关键简化：去掉桌面端的 diff 预览/阈值建议图表/重计算按钮，保留核心参数编辑
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Spin, App, Switch, InputNumber, Button, Space, Alert, theme, Tag, Divider,
} from 'antd'
import { SaveOutlined, ReloadOutlined } from '@ant-design/icons'
import { configApi } from '../../../api/config'
import type { AppConfig } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'

type EvalConfig = AppConfig['eval']

export default function MobileEvalRules() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [form, setForm] = useState<EvalConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const cfg = await configApi.get()
      setForm(cfg.eval)
    } catch (e) {
      message.error(extractApiError(e, '加载失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void load() }, [load])

  const save = async (): Promise<void> => {
    if (!form) return
    // pass_score 不能大于 auto_buy_score
    if (form.pass_score > form.auto_buy_score) {
      message.error(`通过分数(${form.pass_score}) 不能大于自动抢单分数(${form.auto_buy_score})`, 4)
      return
    }
    setSaving(true)
    try {
      const cfg = await configApi.get()
      await configApi.save({ ...cfg, eval: form })
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
        message="评估规则影响所有任务的评分计算"
        description="修改后需手动保存。保存后新评估将使用新规则，历史数据不受影响。"
        style={{ marginBottom: 12, fontSize: 12 }}
      />

      {/* 评分权重 */}
      <Card size="small" style={{ marginBottom: 10 }} title="评分权重">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {([
            ['professional', '专业度'],
            ['credit', '信用度'],
            ['dispute', '纠纷'],
            ['price', '价格'],
          ] as const).map(([key, label]) => (
            <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13 }}>{label}</span>
              <InputNumber
                value={form.weights[key]}
                onChange={(v) => v !== null && setForm({
                  ...form,
                  weights: { ...form.weights, [key]: v },
                })}
                min={0}
                max={10}
                step={0.5}
                style={{ width: 100 }}
              />
            </div>
          ))}
          <div style={{ fontSize: 11, color: themeToken.colorTextTertiary }}>
            权重总和建议在 10 左右
          </div>
        </Space>
      </Card>

      {/* 阈值 */}
      <Card size="small" style={{ marginBottom: 10 }} title="阈值">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {([
            ['on_sale_count', '在售商品数 ≥', 0, 10000],
            ['post_count_30d', '30 天发帖数 ≥', 0, 1000],
            ['top_category_ratio', '主营占比 ≥', 0, 1],
            ['credit_score_min', '信用分 ≥', 0, 1000],
            ['bad_review_max', '差评数 ≤', 0, 100],
            ['register_days_min', '注册天数 ≥', 0, 3650],
          ] as const).map(([key, label, min, max]) => (
            <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13 }}>{label}</span>
              <InputNumber
                value={form.thresholds[key]}
                onChange={(v) => v !== null && setForm({
                  ...form,
                  thresholds: { ...form.thresholds, [key]: v },
                })}
                min={min}
                max={max}
                step={key === 'top_category_ratio' ? 0.05 : 1}
                style={{ width: 100 }}
              />
            </div>
          ))}
        </Space>
      </Card>

      {/* 分数线 */}
      <Card size="small" style={{ marginBottom: 10 }} title="分数线">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              通过分数（pass_score）
            </div>
            <InputNumber
              value={form.pass_score}
              onChange={(v) => v !== null && setForm({ ...form, pass_score: v })}
              min={0}
              max={100}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              自动抢单分数（auto_buy_score）
            </div>
            <InputNumber
              value={form.auto_buy_score}
              onChange={(v) => v !== null && setForm({ ...form, auto_buy_score: v })}
              min={0}
              max={100}
              style={{ width: '100%' }}
            />
          </div>
          {form.pass_score > form.auto_buy_score && (
            <Alert type="error" message="通过分数不能大于自动抢单分数" style={{ fontSize: 12 }} />
          )}
        </Space>
      </Card>

      {/* AI 评估开关 */}
      <Card size="small" style={{ marginBottom: 10 }} title="AI 评估">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13 }}>AI 自动评估</span>
            <Switch
              checked={form.ai_auto_eval}
              onChange={(v) => setForm({ ...form, ai_auto_eval: v })}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13 }}>AI 深度分析</span>
            <Switch
              checked={form.ai_auto_deep_analyze}
              onChange={(v) => setForm({ ...form, ai_auto_deep_analyze: v })}
            />
          </div>
          <Divider style={{ margin: '4px 0' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13 }}>自动官方采集</span>
            <Switch
              checked={form.auto_collect_official}
              onChange={(v) => setForm({ ...form, auto_collect_official: v })}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              每轮最大采集数
            </div>
            <InputNumber
              value={form.auto_collect_max_per_run}
              onChange={(v) => v !== null && setForm({ ...form, auto_collect_max_per_run: v })}
              min={1}
              max={100}
              style={{ width: '100%' }}
            />
          </div>
        </Space>
      </Card>

      {/* 当前配置摘要 */}
      <Card size="small" style={{ marginBottom: 12 }} title="当前配置">
        <Space size={4} wrap>
          <Tag color="blue">通过 {form.pass_score}</Tag>
          <Tag color="orange">自动 {form.auto_buy_score}</Tag>
          <Tag color={form.ai_auto_eval ? 'green' : 'default'}>AI {form.ai_auto_eval ? '开' : '关'}</Tag>
          <Tag color={form.auto_collect_official ? 'green' : 'default'}>采集 {form.auto_collect_official ? '开' : '关'}</Tag>
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
