import { Card, Input, Button, Space, Row, Col, Tag, InputNumber, Typography, Alert } from 'antd'
import {
  EyeInvisibleOutlined,
  EyeOutlined,
  ApiOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import type { AIConfig as AIConfigData } from '../../../../api'
import { EMBEDDING_PRESETS } from '../constants'

const { Text } = Typography

// Embedding 连接测试结果，与 LLM TestResult 结构一致便于复用
export interface EmbeddingTestResult {
  success: boolean
  text: string
}

interface EmbeddingConfigFormProps {
  config: AIConfigData
  // 局部字段更新，避免子组件直接操作父级 setState
  onConfigChange: (patch: Partial<AIConfigData>) => void
  showApiKey: boolean
  onToggleShowApiKey: () => void
  onApplyPreset: (key: keyof typeof EMBEDDING_PRESETS) => void
  testing: boolean
  testResult: EmbeddingTestResult | null
  onTestConnection: () => void
}

export default function EmbeddingConfigForm({
  config,
  onConfigChange,
  showApiKey,
  onToggleShowApiKey,
  onApplyPreset,
  testing,
  testResult,
  onTestConnection,
}: EmbeddingConfigFormProps) {
  // 模式识别：
  // - local：base_url 留空 + model 有值 → 本地 Python 推理（sentence-transformers）
  // - inherit：base_url / model / dimensions 全部为空 → fallback 到 LLM 配置
  // - remote：base_url 有值 → OpenAI 兼容远程服务
  // 必须区分 local 和 inherit，否则用户选了"Python 本地"预设会被误判为 inherit
  const isLocalMode =
    !config.embedding_base_url && !!config.embedding_model
  const isInheritMode =
    !config.embedding_base_url && !config.embedding_model && !config.embedding_dimensions

  return (
    <>
      <h3 style={{ marginBottom: 8, marginTop: 32 }}>Embedding 向量服务配置</h3>
      <p style={{ color: 'var(--xh-text-tertiary)', marginBottom: 16 }}>
        为知识库（RAG）和 FAQ 语义匹配提供文本向量化能力。
        DeepSeek / 智谱等厂商不支持 /v1/embeddings，需独立配置（推荐 Python 本地，无外部依赖）。
      </p>

      {/* 本地模式提示 */}
      {isLocalMode && (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          message="当前使用 Python 本地推理"
          description={`模型 ${config.embedding_model} 将通过 sentence-transformers 在 Python 进程内运行，无需 Ollama 或外部 API。首次调用会下载约 95MB 模型权重。`}
        />
      )}

      {/* 复用模式提示：避免用户误以为配置丢失 */}
      {isInheritMode && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="当前复用 LLM 配置"
          description="所有 embedding 字段为空时，将自动使用上方的 LLM API Base URL / API Key 调用 /embeddings。仅当 LLM 厂商支持 embedding（如 OpenAI）时此模式可用。"
        />
      )}

      <Card style={{ marginBottom: 16, background: 'var(--xh-bg-spotlight)' }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* Embedding API Base URL */}
          <div>
            <label style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>
              Embedding API Base URL
            </label>
            <Input
              value={config.embedding_base_url ?? ''}
              onChange={(e) => onConfigChange({ embedding_base_url: e.target.value })}
              placeholder="留空 = Python 本地推理；Ollama: http://localhost:11434/v1"
              style={{ maxWidth: 600 }}
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              留空时启用 Python 本地推理（推荐，无需 Ollama）；填 URL 走 OpenAI 兼容协议
            </div>
          </div>

          {/* Embedding API Key（密码类型 + 显示/隐藏切换） */}
          <div>
            <label style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>
              Embedding API Key
            </label>
            <Input
              type={showApiKey ? 'text' : 'password'}
              value={config.embedding_api_key ?? ''}
              onChange={(e) => onConfigChange({ embedding_api_key: e.target.value })}
              placeholder="本地模式无需填写；远程 Ollama 填 ollama"
              style={{ maxWidth: 600 }}
              addonAfter={
                <Button
                  type="text"
                  size="small"
                  icon={showApiKey ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                  onClick={onToggleShowApiKey}
                >
                  {showApiKey ? '隐藏' : '显示'}
                </Button>
              }
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              本地模式无需鉴权；远程模式独立存储于 keyring，与 LLM API Key 解耦
            </div>
          </div>

          {/* Embedding 模型 + 维度（并排） */}
          <Row gutter={16}>
            <Col span={12}>
              <div>
                <label style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>
                  Embedding 模型
                </label>
                <Input
                  value={config.embedding_model ?? ''}
                  onChange={(e) => onConfigChange({ embedding_model: e.target.value })}
                  placeholder="本地: BAAI/bge-small-zh-v1.5 / 远程: nomic-embed-text"
                />
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
                  本地推荐: BAAI/bge-small-zh-v1.5 &nbsp; OpenAI: text-embedding-3-small
                </div>
              </div>
            </Col>
            <Col span={12}>
              <div>
                <label style={{ fontWeight: 500, marginBottom: 4, display: 'block' }}>
                  向量维度
                </label>
                <InputNumber
                  value={config.embedding_dimensions ?? 0}
                  onChange={(v) => onConfigChange({ embedding_dimensions: v ?? 0 })}
                  min={0}
                  max={3072}
                  style={{ width: '100%' }}
                  placeholder="0 表示由模型决定"
                />
                <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
                  bge-small-zh-v1.5 = 512 &nbsp; OpenAI text-embedding-3-small = 1536
                </div>
              </div>
            </Col>
          </Row>
        </Space>
      </Card>

      {/* 快捷预设按钮行 */}
      <h3 style={{ marginBottom: 8 }}>Embedding 快捷预设</h3>
      <p style={{ color: 'var(--xh-text-tertiary)', marginBottom: 16 }}>
        一键切换到常用 Embedding 服务商。推荐使用 Python 本地（无外部依赖，中文优化）。
      </p>
      <Space wrap style={{ marginBottom: 24 }}>
        {(
          Object.entries(EMBEDDING_PRESETS) as [
            keyof typeof EMBEDDING_PRESETS,
            (typeof EMBEDDING_PRESETS)[keyof typeof EMBEDDING_PRESETS],
          ][]
        ).map(([key, preset]) => (
          <Tag
            key={key}
            style={{ cursor: 'pointer', padding: '4px 12px', fontSize: 14 }}
            color={preset.color}
            onClick={() => onApplyPreset(key)}
          >
            {preset.label}
          </Tag>
        ))}
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
            {testing ? '测试中…（本地首次加载模型较慢）' : '🔗 测试 Embedding 连接'}
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
