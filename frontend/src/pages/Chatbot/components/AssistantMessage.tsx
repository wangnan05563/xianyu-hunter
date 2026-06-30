import { useState } from 'react'
import { Typography, Tag, Tooltip, Progress, Collapse, Button, Modal, Input, Alert, message } from 'antd'
import { LikeOutlined, DislikeOutlined, CopyOutlined } from '@ant-design/icons'
import type { Message, Source } from '../types'
import { chatbotApi } from '../api'

interface Props {
  message: Message
  sessionId: string
  onFeedbackDone?: () => void
}

// 助手消息组件：渲染内容 + 引用来源 + 工具调用标记 + 反馈按钮 + 转人工告警
export function AssistantMessage({ message: msg, sessionId, onFeedbackDone }: Props) {
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false)
  const [feedbackRating, setFeedbackRating] = useState<'positive' | 'negative'>('positive')
  const [feedbackComment, setFeedbackComment] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const handleFeedback = (rating: 'positive' | 'negative') => {
    if (submitted) return
    setFeedbackRating(rating)
    setFeedbackModalOpen(true)
  }

  const submitFeedback = async () => {
    try {
      await chatbotApi.submitFeedback(msg.id, feedbackRating, feedbackComment, sessionId)
      setSubmitted(true)
      setFeedbackModalOpen(false)
      setFeedbackComment('')
      message.success('感谢您的反馈')
      onFeedbackDone?.()
    } catch {
      message.error('反馈提交失败')
    }
  }

  const copySession = async () => {
    try {
      const { content } = await chatbotApi.exportSession(sessionId)
      await navigator.clipboard.writeText(content)
      message.success('会话记录已复制到剪贴板')
    } catch {
      message.error('复制失败')
    }
  }

  return (
    <div style={{ padding: '12px 0' }}>
      {/* 消息内容：用 Typography 渲染，保留换行；手动处理 [来源:N] 引用 */}
      <Typography.Paragraph style={{ marginBottom: 8, whiteSpace: 'pre-wrap' }}>
        {renderContentWithCitations(msg.content, msg.sources)}
      </Typography.Paragraph>

      {/* 降级标记：RAG 降级为 FAQ 或转人工时显示 */}
      {msg.degraded && (
        <Tag color="orange" style={{ marginBottom: 8 }}>已降级</Tag>
      )}

      {/* 工具调用次数 */}
      {msg.tool_calls && msg.tool_calls.length > 0 && (
        <Tag color="blue" style={{ marginBottom: 8 }}>工具调用 {msg.tool_calls.length} 次</Tag>
      )}

      {/* 参考来源面板（可折叠） */}
      {msg.sources && msg.sources.length > 0 && (
        <Collapse ghost size="small" style={{ marginBottom: 8 }}>
          <Collapse.Panel header={`参考来源 (${msg.sources.length})`} key="sources">
            {msg.sources.map((src: Source) => (
              <div key={src.index} style={{ marginBottom: 8 }}>
                <Tag color="cyan">[{src.index}]</Tag>
                <Typography.Text type="secondary">{src.file}</Typography.Text>
                <Typography.Text style={{ marginLeft: 8 }}>{src.section}</Typography.Text>
                {src.line_start > 0 && (
                  <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                    L{src.line_start}-L{src.line_end}
                  </Typography.Text>
                )}
                <Tooltip title={`相似度: ${(src.similarity * 100).toFixed(1)}%`}>
                  <Progress
                    percent={Math.round(src.similarity * 100)}
                    size="small"
                    format={(p) => `${p}%`}
                    style={{ width: 80, marginLeft: 8, display: 'inline-flex' }}
                  />
                </Tooltip>
              </div>
            ))}
          </Collapse.Panel>
        </Collapse>
      )}

      {/* 转人工告警 */}
      {msg.escalated && (
        <Alert
          type="warning"
          message="已转人工客服"
          description={msg.escalate_reason || '请联系管理员处理'}
          action={
            <Button size="small" icon={<CopyOutlined />} onClick={copySession}>
              复制会话记录
            </Button>
          }
          style={{ marginBottom: 8 }}
        />
      )}

      {/* 反馈按钮 */}
      {!submitted && (
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            size="small"
            icon={<LikeOutlined />}
            onClick={() => handleFeedback('positive')}
          />
          <Button
            size="small"
            icon={<DislikeOutlined />}
            onClick={() => handleFeedback('negative')}
          />
        </div>
      )}

      {/* 反馈输入 Modal */}
      <Modal
        title="反馈"
        open={feedbackModalOpen}
        onOk={submitFeedback}
        onCancel={() => setFeedbackModalOpen(false)}
      >
        <Input.TextArea
          rows={3}
          placeholder="请描述您的反馈（可选）"
          value={feedbackComment}
          onChange={(e) => setFeedbackComment(e.target.value)}
        />
      </Modal>
    </div>
  )
}

// 渲染内容并处理 [来源:N] 引用标记
// 为什么不用 react-markdown：项目未安装该依赖，用简单文本渲染避免引入新包
// [来源:N] 渲染为带 Tooltip 的 Tag，点击可跳转到对应来源
function renderContentWithCitations(content: string, sources?: Source[]): React.ReactNode {
  if (!sources || sources.length === 0) {
    return content
  }

  const regex = /\[来源:(\d+|\?)\]/g
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  let key = 0

  while ((match = regex.exec(content)) !== null) {
    // 添加匹配前的普通文本
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index))
    }
    // 添加引用 Tag
    const refNum = match[1]
    const source = refNum !== '?' ? sources.find((s) => s.index === Number.parseInt(refNum, 10)) : undefined
    parts.push(
      <Tooltip
        key={`cite-${key++}`}
        title={source ? `${source.file} · ${source.section}` : '来源未知'}
      >
        <Tag color="cyan" style={{ cursor: 'pointer' }}>[来源:{refNum}]</Tag>
      </Tooltip>,
    )
    lastIndex = regex.lastIndex
  }
  // 添加剩余文本
  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex))
  }
  return <>{parts}</>
}
