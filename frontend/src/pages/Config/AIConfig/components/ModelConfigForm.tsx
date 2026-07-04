import { Card, Input, Button, Space, Row, Col, Tag, Typography } from 'antd'
import {
  EyeInvisibleOutlined,
  EyeOutlined,
  ApiOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import type { AIConfig as AIConfigData } from '../../../../api'
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
  testing,
  testResult,
  onTestConnection,
}: ModelConfigFormProps) {
  // 根据当前 base_url 反查预设，得到对应厂商的 API Key 申请页链接
  // 切换预设或手动改 base_url 都会重新派生，保证「获取」链接跟随当前配置
  const apiKeyUrl = findPresetByBaseUrl(config.base_url)?.apiKeyUrl

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
            <Input
              id="ai-api-key"
              type={showApiKey ? 'text' : 'password'}
              value={config.api_key}
              onChange={(e) => onConfigChange({ api_key: e.target.value })}
              placeholder="sk-..."
              style={{ maxWidth: 600 }}
              addonAfter={
                <Space size="small">
                  <Button
                    type="text"
                    size="small"
                    icon={showApiKey ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                    onClick={onToggleShowApiKey}
                  >
                    {showApiKey ? '隐藏' : '显示'}
                  </Button>
                  {apiKeyUrl && (
                    <a href={apiKeyUrl} target="_blank" rel="noopener noreferrer">
                      获取
                    </a>
                  )}
                </Space>
              }
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              密钥通过系统密钥库（keyring）安全存储，不写入配置文件
            </div>
          </div>

          {/* 文本解析模型 + Vision 模型（并排） */}
          <Row gutter={16}>
            <Col span={12}>
              <div>
                <label htmlFor="ai-model-text" style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>文本解析模型</label>
                <Input
                  id="ai-model-text"
                  value={config.model}
                  onChange={(e) => onConfigChange({ model: e.target.value })}
                  placeholder="gpt-4o-mini"
                />
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
                  自然语言解析 + 任务字段提取
                </div>
              </div>
            </Col>
            <Col span={12}>
              <div>
                <label htmlFor="ai-model-vision" style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>Vision 模型</label>
                <Input
                  id="ai-model-vision"
                  value={config.vision_model}
                  onChange={(e) => onConfigChange({ vision_model: e.target.value })}
                  placeholder="gpt-4o"
                />
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
        一键切换到常用 AI 服务商（仅修改 URL 和模型名称，需自行配置 API Key）。
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
          <Button
            icon={<ApiOutlined />}
            loading={testing}
            onClick={onTestConnection}
            disabled={!config.ai_enabled}
          >
            {testing ? '测试中…' : '🔗 测试连接'}
          </Button>
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
