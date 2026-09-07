import { useState } from 'react'
import { Card, Input, Space, Row, Col, Tag, Typography, Dropdown, Menu, Spin, message } from 'antd'
import { TipButton } from '@/components/TipButton'
import {
  EyeInvisibleOutlined,
  EyeOutlined,
  ApiOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'
import { aiApi, type AIModelInfo, type AIConfig as AIConfigData } from '../../../../api'
import { extractApiError } from '../../../../utils/apiError'
import { PRESETS, findPresetByBaseUrl } from '../constants'

const { Text } = Typography

// 测试连接结果类型，提升到组件外以便父组件复用
export interface TestResult {
  success: boolean
  text: string
}

interface ModelConfigFormProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly config: AIConfigData
  readonly onConfigChange: (patch: Partial<AIConfigData>) => void
  readonly showApiKey: boolean
  readonly onToggleShowApiKey: () => void
  readonly onApplyPreset: (key: keyof typeof PRESETS) => void
  readonly saving: boolean
  readonly onSaveConfig: () => void
  readonly testing: boolean
  readonly testResult: TestResult | null
  readonly onTestConnection: () => void
}

export default function ModelConfigForm({
  config,
  onConfigChange,
  showApiKey,
  onToggleShowApiKey,
  onApplyPreset,
  saving,
  onSaveConfig,
  testing,
  testResult,
  onTestConnection,
}: ModelConfigFormProps) {
  // 根据当前 base_url 反查预设，得到对应厂商的 API Key 申请页链接
  // 切换预设或手动改 base_url 都会重新派生，保证「获取」链接跟随当前配置
  const apiKeyUrl = findPresetByBaseUrl(config.base_url)?.apiKeyUrl

  // 拉取模型列表状态：文本/Vision 各自独立，避免互扰
  const [modelOptions, setModelOptions] = useState<AIModelInfo[]>([])
  const [visionOptions, setVisionOptions] = useState<AIModelInfo[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [loadingVisionModels, setLoadingVisionModels] = useState(false)
  // 下拉面板 open 受控：antd menu 不支持 loading 字段，改为 dropdownRender 自定义内容，
  // 需手动控制开关以在选中后收起（menu 原生写法会自动收起，这里需自行管理）
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const [visionDropdownOpen, setVisionDropdownOpen] = useState(false)

  // 拉取当前配置（可能未保存的 base_url / 新 Key）可用的模型列表
  // 脱敏 Key（**** 开头）不回传：后端会复用服务端已保存的 Key，避免用错误值请求；
  // 未脱敏的 Key 是用户刚输入的新值，回传用于临时连接预览（后端已支持该模式）
  const fetchModels = async (target: 'model' | 'vision_model') => {
    const rawKey = config.api_key ?? ''
    const apiKey = rawKey.startsWith('****') ? undefined : rawKey || undefined
    const setLoading = target === 'model' ? setLoadingModels : setLoadingVisionModels
    const setOptions = target === 'model' ? setModelOptions : setVisionOptions
    setLoading(true)
    try {
      const data = await aiApi.listModels({ base_url: config.base_url, api_key: apiKey })
      setOptions(data.ok ? data.models ?? [] : [])
    } catch (e) {
      message.error(extractApiError(e), 4)
    } finally {
      setLoading(false)
    }
  }

  // 生成「模型下拉」的面板 props：加载中显示 Spin，成功/失败显示模型列表；
  // 两个字段结构完全相同，仅数据源与回填字段不同，故抽成一个函数复用
  const renderModelDropdown = (target: 'model' | 'vision_model') => {
    const loading = target === 'model' ? loadingModels : loadingVisionModels
    const options = target === 'model' ? modelOptions : visionOptions
    const open = target === 'model' ? modelDropdownOpen : visionDropdownOpen
    const setOpen = target === 'model' ? setModelDropdownOpen : setVisionDropdownOpen
    return {
      open,
      onOpenChange: (next: boolean) => {
        setOpen(next)
        // 每次展开都重新拉取，保证拿到的是当前未保存配置下的最新模型列表
        if (next) void fetchModels(target)
      },
      dropdownRender: () =>
        loading ? (
          <div style={{ padding: 12, textAlign: 'center' }}>
            <Spin size="small" />
          </div>
        ) : (
          <Menu
            style={{
              border: '1px solid rgba(5, 5, 5, 0.06)',
              borderRadius: 8,
              boxShadow: '0 6px 16px 0 rgba(0,0,0,0.08), 0 3px 6px -4px rgba(0,0,0,0.12)',
            }}
            items={
              options.length
                ? options.map((m) => ({ key: m.id, label: m.id }))
                : [{ key: '__empty__', label: '未获取到模型，请检查 Base URL / API Key', disabled: true }]
            }
            onClick={({ key }) => {
              if (key !== '__empty__') onConfigChange({ [target]: key } as Partial<AIConfigData>)
              setOpen(false)
            }}
          />
        ),
    }
  }

  return (
    <>
      <p style={{ color: 'var(--xh-text-tertiary)', marginBottom: 16 }}>
        配置 AI 评估和自然语言解析所需的 LLM 服务。支持 OpenAI / DeepSeek / 智谱等 OpenAI 兼容接口。
      </p>

      <Card style={{ marginBottom: 16, background: 'var(--xh-bg-spotlight)' }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* API Base URL */}
          <div>
            {/* htmlFor + id 关联 label 与 input，满足可访问性（SonarQube S6853） */}
            <label htmlFor="ai-base-url" style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>API Base URL</label>
            <Input
              id="ai-base-url"
              value={config.base_url}
              onChange={(e) => onConfigChange({ base_url: e.target.value })}
              placeholder="https://api.openai.com/v1"
              style={{ maxWidth: 600 }}
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              OpenAI 兼容端点。DeepSeek: https://api.deepseek.com/v1 &nbsp;&nbsp; 智谱: https://open.bigmodel.cn/api/paas/v4
            </div>
          </div>

          {/* API Key（密码类型 + 显示/隐藏切换 + 厂商申请页「获取」链接） */}
          <div>
            <label htmlFor="ai-api-key" style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>API Key</label>
            {/* addonAfter 在 antd v5 已废弃，改用 Space.Compact 紧凑布局（SonarQube S1874） */}
            <Space.Compact style={{ maxWidth: 600 }}>
              <Input
                id="ai-api-key"
                type={showApiKey ? 'text' : 'password'}
                value={config.api_key}
                onChange={(e) => onConfigChange({ api_key: e.target.value })}
                placeholder="sk-..."
                style={{ flex: 1 }}
              />
              <TipButton
                tip="切换显示或隐藏 API Key 明文"
                type="default"
                icon={showApiKey ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                onClick={onToggleShowApiKey}
              >
                {showApiKey ? '隐藏' : '显示'}
              </TipButton>
              {apiKeyUrl && (
                <TipButton tip="前往厂商 API Key 申请页" type="default" href={apiKeyUrl} target="_blank" rel="noopener noreferrer">
                  获取
                </TipButton>
              )}
            </Space.Compact>
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              密钥通过系统密钥库（keyring）安全存储，不写入配置文件
            </div>
          </div>

          {/* 文本解析模型 + Vision 模型（并排） */}
          <Row gutter={16}>
            <Col span={12}>
              <div>
                <label htmlFor="ai-model-text" style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>文本解析模型</label>
                {/* 输入框 + 拉取模型下拉按钮：点击下拉时按当前 base_url/Key 拉取可用模型，选中即回填 */}
                <Space.Compact style={{ width: '100%' }}>
                  <Input
                    id="ai-model-text"
                    value={config.model}
                    onChange={(e) => onConfigChange({ model: e.target.value })}
                    placeholder="gpt-4o-mini"
                    style={{ flex: 1 }}
                  />
                  <Dropdown {...renderModelDropdown('model')}>
                    <TipButton tip="拉取当前配置可用的文本模型列表" icon={<UnorderedListOutlined />} />
                  </Dropdown>
                </Space.Compact>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
                  自然语言解析 + 任务字段提取
                </div>
              </div>
            </Col>
            <Col span={12}>
              <div>
                <label htmlFor="ai-model-vision" style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>Vision 模型</label>
                <Space.Compact style={{ width: '100%' }}>
                  <Input
                    id="ai-model-vision"
                    value={config.vision_model}
                    onChange={(e) => onConfigChange({ vision_model: e.target.value })}
                    placeholder="gpt-4o"
                    style={{ flex: 1 }}
                  />
                  <Dropdown {...renderModelDropdown('vision_model')}>
                    <TipButton tip="拉取当前配置可用的 Vision 模型列表" icon={<UnorderedListOutlined />} />
                  </Dropdown>
                </Space.Compact>
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
                  图片成色评估 + 深度多模态分析
                </div>
              </div>
            </Col>
          </Row>
        </Space>
      </Card>

      {/* 快捷预设按钮行 */}
      <h3 style={{ marginBottom: 8 }}>快捷预设</h3>
      <p style={{ color: 'var(--xh-text-tertiary)', marginBottom: 16 }}>
        一键切换到常用 AI 服务商，API Key 会按预设独立保存并随切换返显。
      </p>
      <Space wrap style={{ marginBottom: 24 }}>
        {(Object.entries(PRESETS) as [keyof typeof PRESETS, typeof PRESETS[keyof typeof PRESETS]][]).map(
          ([key, preset]) => (
            <Tag
              key={key}
              style={{ cursor: 'pointer', padding: '4px 12px', fontSize: 14 }}
              color={preset.color}
              onClick={() => onApplyPreset(key)}
            >
              {preset.label}
            </Tag>
          )
        )}
      </Space>

      {/* 连接测试按钮 + 结果展示 */}
      <div style={{ marginBottom: 24 }}>
        <Space align="center">
          <TipButton tip="保存 LLM 配置" type="primary" loading={saving} onClick={onSaveConfig} disabled={!config.ai_enabled}>
            保存配置
          </TipButton>
          <TipButton
            tip="测试 LLM 连接是否可用"
            icon={<ApiOutlined />}
            loading={testing}
            onClick={onTestConnection}
            disabled={!config.ai_enabled}
          >
            {testing ? '测试中…' : '🔗 测试连接'}
          </TipButton>
          {testResult && (
            <Text style={{ color: testResult.success ? '#52c41a' : '#ff4d4f' }}>
              {testResult.success ? <CheckCircleOutlined /> : <CloseCircleOutlined />} {testResult.text}
            </Text>
          )}
        </Space>
      </div>
    </>
  )
}
