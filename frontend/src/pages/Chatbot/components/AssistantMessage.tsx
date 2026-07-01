import { useState } from 'react'
import { Typography, Tag, Tooltip, Progress, Collapse, Button, Modal, Input, Alert, Rate, Select, message } from 'antd'
import { CopyOutlined } from '@ant-design/icons'
import type { Message, Source } from '../types'
import { chatbotApi } from '../api'

interface Props {
  message: Message
  sessionId: string
  onFeedbackDone?: () => void
}

// 助手消息组件：渲染内容 + 引用来源 + 工具调用标记 + 1-5 星评分 + 转人工告警
export function AssistantMessage({ message: msg, sessionId, onFeedbackDone }: Props) {
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false)
  const [starRating, setStarRating] = useState(0)
  const [feedbackCategory, setFeedbackCategory] = useState<string | undefined>(undefined)
  const [feedbackComment, setFeedbackComment] = useState('')
  // M6：从消息已有反馈初始化已评价状态，刷新页面后回显
  const [submitted, setSubmitted] = useState(!!msg.feedback_rating && msg.feedback_rating > 0)
  const [submittedRating, setSubmittedRating] = useState(msg.feedback_rating ?? 0)

  // M6：星级决定 sentiment——4-5 星 positive，1-3 星 negative
  // 点击星级后自动打开反馈 Modal（低分时可填分类 + 文字，高分时只填文字）
  const handleRateChange = (value: number) => {
    if (submitted) return
    setStarRating(value)
    setFeedbackCategory(undefined)
    setFeedbackModalOpen(true)
  }

  const submitFeedback = async () => {
    if (starRating === 0) return
    // 4-5 星 → positive，1-3 星 → negative
    const sentiment = starRating >= 4 ? 'positive' : 'negative'
    try {
      await chatbotApi.submitFeedback(
        msg.id, sentiment, feedbackComment, sessionId,
        starRating, feedbackCategory,
      )
      setSubmitted(true)
      setSubmittedRating(starRating)
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

  // 反馈分类选项（仅低分 1-3 星时显示）
  const showCategorySelect = starRating > 0 && starRating <= 3

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

      {/* M6：1-5 星评分——已提交后只读 */}
      <div className="cb-feedback-rate">
        {submitted ? (
          <Rate disabled value={submittedRating} className="cb-rate-submitted" />
        ) : (
          // value 用 starRating 而非硬编码 0：让 Rate 显示与用户点击一致，
          // Modal 打开期间背后星数视觉连贯；取消时 starRating 已重置为 0 自然回空
          <Rate onChange={handleRateChange} value={starRating} className="cb-rate-input" />
        )}
        <span className="cb-rate-label">
          {submitted ? '已评价' : '点击评分'}
        </span>
      </div>

      {/* 反馈输入 Modal */}
      <Modal
        title="反馈"
        open={feedbackModalOpen}
        onOk={submitFeedback}
        onCancel={() => {
          setFeedbackModalOpen(false)
          setStarRating(0)
          setFeedbackCategory(undefined)
          setFeedbackComment('')
        }}
        okText="提交"
        cancelText="取消"
      >
        <div className="cb-feedback-modal-content">
          {/* 星级展示（只读，已在上一步选好） */}
          <div className="cb-feedback-modal-row">
            <Typography.Text>评分</Typography.Text>
            <Rate disabled value={starRating} />
          </div>
          {/* 低分时显示问题分类 */}
          {showCategorySelect && (
            <div className="cb-feedback-modal-row">
              <Typography.Text>问题类型</Typography.Text>
              <Select
                placeholder="选择问题类型"
                value={feedbackCategory}
                onChange={setFeedbackCategory}
                style={{ width: '100%' }}
                options={[
                  { value: 'irrelevant', label: '答非所问' },
                  { value: 'inaccurate', label: '信息有误' },
                  { value: 'other', label: '其他' },
                ]}
              />
            </div>
          )}
          {/* 文字反馈 */}
          <div className="cb-feedback-modal-row">
            <Typography.Text>补充说明</Typography.Text>
            <Input.TextArea
              rows={3}
              placeholder="请描述您的反馈（可选）"
              value={feedbackComment}
              onChange={(e) => setFeedbackComment(e.target.value)}
            />
          </div>
        </div>
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
