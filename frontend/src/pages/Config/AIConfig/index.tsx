import { useEffect, useState } from 'react'
import { Card, Switch, Tag, message, Typography } from 'antd'
import { aiApi, type AIConfig as AIConfigData, type AIUsage } from '../../../api'
import { PRESETS } from './constants'
import ModelConfigForm, { type TestResult } from './components/ModelConfigForm'
import UsageStats from './components/UsageStats'
import BudgetSettings from './components/BudgetSettings'

const { Text } = Typography

export default function AIConfig() {
  // AI 配置状态
  const [config, setConfig] = useState<AIConfigData>({
    ai_enabled: true,
    base_url: '',
    api_key: '',
    model: '',
    vision_model: '',
  })

  // 用量数据状态
  const [usage, setUsage] = useState<AIUsage>({
    today: {
      total_calls: 0,
      total_tokens: 0,
      total_cost_usd: 0,
      total_cost_cny: 0,
      by_endpoint: {},
      by_model: {},
    },
    budget: {
      daily_token_limit: 500000,
      daily_cost_limit_usd: 5,
      rate_limit_per_min: 20,
      token_usage_pct: 0,
      cost_usage_pct: 0,
    },
    history: [],
  })

  // UI 状态
  const [showApiKey, setShowApiKey] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [saving, setSaving] = useState(false)

  // 初始化加载配置和用量数据
  useEffect(() => {
    Promise.all([
      aiApi.getConfig().catch(() => null),
      aiApi.getUsage().catch(() => null),
    ]).then(([configData, usageData]) => {
      if (configData) {
        setConfig({
          ai_enabled: configData.ai_enabled !== false,
          base_url: configData.base_url ?? '',
          api_key: configData.api_key ?? '',
          model: configData.model ?? '',
          vision_model: configData.vision_model ?? '',
        })
      }
      if (usageData) {
        setUsage(usageData)
      }
    })
  }, [])

  // 切换 AI 开关（关闭时需二次确认）
  const handleToggleAI = async (checked: boolean) => {
    // 关闭时二次确认，防止误操作导致所有 AI 功能降级
    if (!checked) {
      const confirmed = window.confirm(
        '确定要关闭 AI 功能吗？\n\n关闭后所有 AI 评估、解析、分析将降级到规则模式，不消耗任何 token。\n可随时重新开启。'
      )
      if (!confirmed) return
    }

    try {
      await aiApi.putConfig({ ai_enabled: checked })
      setConfig((prev) => ({ ...prev, ai_enabled: checked }))
      message.success(checked ? 'AI 功能已开启' : 'AI 功能已关闭')
    } catch {
      message.error('操作失败')
    }
  }

  // 统一更新 config 局部字段，避免子组件直接操作父级 setState
  const updateConfig = (patch: Partial<AIConfigData>) => {
    setConfig((prev) => ({ ...prev, ...patch }))
  }

  // 应用预设配置（仅修改 URL 和模型，API Key 需用户自行填写）
  const applyPreset = (presetKey: keyof typeof PRESETS) => {
    const preset = PRESETS[presetKey]
    if (!preset) return
    setConfig((prev) => ({
      ...prev,
      base_url: preset.base_url,
      model: preset.model,
      vision_model: preset.vision_model,
    }))
    message.success(`已切换到 ${preset.label} 预设`)
  }

  // 测试连接：先保存当前配置，再调用测试接口
  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      // 先保存当前配置，确保测试使用的是最新参数
      await aiApi.putConfig(config)
      const data = await aiApi.testConnection()
      if (data.ok) {
        setTestResult({ success: true, text: `连接成功 (${data.model || ''})` })
        // 测试成功后刷新用量数据
        const freshUsage = await aiApi.getUsage()
        if (freshUsage) setUsage(freshUsage)
      } else {
        setTestResult({ success: false, text: data.detail || '连接失败' })
      }
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : '网络错误'
      setTestResult({ success: false, text: `网络错误: ${errorMsg}` })
    } finally {
      setTesting(false)
    }
  }

  // 统一更新 budget 局部字段
  const updateBudget = (patch: Partial<AIUsage['budget']>) => {
    setUsage((prev) => ({ ...prev, budget: { ...prev.budget, ...patch } }))
  }

  // 保存预算设置
  const handleSaveBudget = async () => {
    setSaving(true)
    try {
      await aiApi.putBudget({
        daily_token_limit: usage.budget.daily_token_limit,
        daily_cost_limit_usd: usage.budget.daily_cost_limit_usd,
        rate_limit_per_min: usage.budget.rate_limit_per_min,
      })
      message.success('预算设置已保存')
      // 刷新用量数据以获取最新预算状态
      const freshUsage = await aiApi.getUsage()
      if (freshUsage) setUsage(freshUsage)
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page-container">
      {/* ====== 顶部：AI 功能总开关卡片 ====== */}
      <Card
        style={{
          marginBottom: 16,
          border: '2px solid #d9d9d9',
          background: '#fafafa',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
              AI 功能总开关
              <Tag color={config.ai_enabled ? 'success' : 'error'}>
                {config.ai_enabled ? '已开启' : '已关闭'}
              </Tag>
            </h3>
            <p style={{ marginTop: 4, color: '#999', margin: '4px 0 0' }}>
              关闭后所有 AI 功能将降级到规则模式，不消耗任何 token
            </p>
          </div>
          <Switch
            checked={config.ai_enabled}
            onChange={handleToggleAI}
            checkedChildren="ON"
            unCheckedChildren="OFF"
            style={{ minWidth: 80 }}
          />
        </div>
      </Card>

      {/* ====== 配置区域（带遮罩）====== */}
      <div style={{ position: 'relative', opacity: config.ai_enabled ? 1 : 0.5, pointerEvents: config.ai_enabled ? 'auto' : 'none' }}>
        {/* AI 关闭时的半透明遮罩提示 */}
        {!config.ai_enabled && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 10,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(0,0,0,0.06)',
              borderRadius: 8,
              pointerEvents: 'auto',
            }}
          >
            <Text strong style={{ fontSize: 18, color: '#999' }}>
              AI 功能已关闭，以下配置不可用
            </Text>
          </div>
        )}

        <ModelConfigForm
          config={config}
          onConfigChange={updateConfig}
          showApiKey={showApiKey}
          onToggleShowApiKey={() => setShowApiKey(!showApiKey)}
          onApplyPreset={applyPreset}
          testing={testing}
          testResult={testResult}
          onTestConnection={handleTestConnection}
        />
      </div>{/* end 遮罩容器 */}

      {/* ====== 用量仪表盘（始终可见）====== */}
      <UsageStats usage={usage} />

      {/* ====== 预算控制区 ====== */}
      <BudgetSettings
        budget={usage.budget}
        onBudgetChange={updateBudget}
        saving={saving}
        onSave={handleSaveBudget}
      />
    </div>
  )
}
