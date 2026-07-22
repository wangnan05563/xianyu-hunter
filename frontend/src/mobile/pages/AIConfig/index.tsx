// frontend/src/mobile/pages/AIConfig/index.tsx
// 移动端 AI 服务配置：LLM + Embedding 双路配置 + 连接测试
// 设计要点：aiApi.getConfig()/putConfig() 独立于 configApi，测试结果即时反馈
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Spin, App, Switch, Input, Button, Space, Alert, theme, Tag, Descriptions,
} from 'antd'
import { SaveOutlined, ReloadOutlined, ApiOutlined } from '@ant-design/icons'
import { aiApi } from '../../../api'
import type { AIConfig, AIUsage } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'

export default function MobileAIConfig() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [form, setForm] = useState<AIConfig | null>(null)
  const [usage, setUsage] = useState<AIUsage | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingLLM, setTestingLLM] = useState(false)
  const [testingEmb, setTestingEmb] = useState(false)

  const load = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const [cfg, use] = await Promise.all([
        aiApi.getConfig(),
        aiApi.getUsage().catch(() => null),
      ])
      setForm(cfg)
      if (use) setUsage(use)
    } catch (e) {
      message.error(extractApiError(e, '加载失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void load() }, [load])

  const save = async (): Promise<void> => {
    if (!form) return
    setSaving(true)
    try {
      await aiApi.putConfig(form)
      message.success('已保存')
    } catch (e) {
      message.error(extractApiError(e, '保存失败'), 3)
    } finally {
      setSaving(false)
    }
  }

  const testLLM = async (): Promise<void> => {
    setTestingLLM(true)
    try {
      const res = await aiApi.testConnection()
      if (res.ok) {
        // 将后缀提取为独立变量，避免嵌套模板字符串降低可读性
        const modelSuffix = res.model ? `（${res.model}）` : ''
        message.success(`连接成功${modelSuffix}`)
      } else {
        message.error(`连接失败：${res.detail || '未知错误'}`, 4)
      }
    } catch (e) {
      message.error(extractApiError(e, '测试失败'), 3)
    } finally {
      setTestingLLM(false)
    }
  }

  const testEmbedding = async (): Promise<void> => {
    setTestingEmb(true)
    try {
      const res = await aiApi.testEmbedding()
      if (res.ok) {
        // 将维度后缀提取为独立变量，避免嵌套模板字符串降低可读性
        const dimSuffix = res.dimensions ? `（维度 ${res.dimensions}）` : ''
        message.success(`Embedding 连接成功${dimSuffix}`)
      } else {
        message.error(`Embedding 失败：${res.detail || '未知错误'}`, 4)
      }
    } catch (e) {
      message.error(extractApiError(e, 'Embedding 测试失败'), 3)
    } finally {
      setTestingEmb(false)
    }
  }

  if (loading || !form) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  return (
    <div>
      {/* 用量统计 */}
      {usage && (
        <Card size="small" style={{ marginBottom: 10 }} title="今日用量">
          <Descriptions column={2} size="small">
            <Descriptions.Item label="调用次数">{usage.today.total_calls}</Descriptions.Item>
            <Descriptions.Item label="Token 数">{usage.today.total_tokens}</Descriptions.Item>
            <Descriptions.Item label="费用(¥)">{usage.today.total_cost_cny.toFixed(2)}</Descriptions.Item>
            <Descriptions.Item label="费用($)">${usage.today.total_cost_usd.toFixed(4)}</Descriptions.Item>
          </Descriptions>
          {usage.budget.daily_token_limit > 0 && (
            <div style={{ marginTop: 8 }}>
              <Tag color={usage.budget.token_usage_pct > 80 ? 'red' : 'green'}>
                Token {usage.budget.token_usage_pct}%
              </Tag>
              <Tag color={usage.budget.cost_usage_pct > 80 ? 'red' : 'green'}>
                费用 {usage.budget.cost_usage_pct}%
              </Tag>
            </div>
          )}
        </Card>
      )}

      {/* AI 总开关 */}
      <Card size="small" style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 600 }}>启用 AI 服务</div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary }}>
              关闭后所有 AI 评估功能停用
            </div>
          </div>
          <Switch
            checked={form.ai_enabled}
            onChange={(v) => setForm({ ...form, ai_enabled: v })}
          />
        </div>
      </Card>

      {/* LLM 配置 */}
      <Card size="small" style={{ marginBottom: 10 }} title="LLM 配置">
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              API Base URL
            </div>
            <Input
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              placeholder="https://api.openai.com/v1"
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              API Key
            </div>
            <Input.Password
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              placeholder="sk-..."
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              模型
            </div>
            <Input
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              placeholder="deepseek-chat / gpt-4o-mini"
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              Vision 模型（可选）
            </div>
            <Input
              value={form.vision_model}
              onChange={(e) => setForm({ ...form, vision_model: e.target.value })}
              placeholder="gpt-4o / deepseek-vision"
            />
          </div>
          <Button
            block
            icon={<ApiOutlined />}
            loading={testingLLM}
            onClick={testLLM}
          >
            测试 LLM 连接
          </Button>
        </Space>
      </Card>

      {/* Embedding 配置 */}
      <Card size="small" style={{ marginBottom: 12 }} title="Embedding 配置（可选）">
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            message="留空时自动 fallback 到 LLM 配置"
            style={{ fontSize: 12 }}
          />
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              Embedding Base URL
            </div>
            <Input
              value={form.embedding_base_url ?? ''}
              onChange={(e) => setForm({ ...form, embedding_base_url: e.target.value })}
              placeholder="同 LLM 或独立端点"
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              Embedding API Key
            </div>
            <Input.Password
              value={form.embedding_api_key ?? ''}
              onChange={(e) => setForm({ ...form, embedding_api_key: e.target.value })}
              placeholder="留空则使用 LLM Key"
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              Embedding 模型
            </div>
            <Input
              value={form.embedding_model ?? ''}
              onChange={(e) => setForm({ ...form, embedding_model: e.target.value })}
              placeholder="text-embedding-3-small / bge-small-zh"
            />
          </div>
          <Button
            block
            icon={<ApiOutlined />}
            loading={testingEmb}
            onClick={testEmbedding}
          >
            测试 Embedding 连接
          </Button>
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
