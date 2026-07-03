import { useState, useRef, useMemo, createContext, useContext } from 'react'
import { Typography, Tag, Tooltip, Progress, Collapse, Button, Modal, Input, Alert, Rate, Select, message } from 'antd'
import { CopyOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/atom-one-light.css'
import type { Message, Source } from '../types'
import { chatbotApi } from '../api'

interface Props {
  readonly message: Message
  readonly sessionId: string
  readonly onFeedbackDone?: () => void
}

// SourcesContext：把 msg.sources 透传给提取到模块顶层的 MarkdownLink，
// 避免 MarkdownLink 作为子组件定义在 AssistantMessage 内（SonarQube S6478）
const SourcesContext = createContext<Source[] | undefined>(undefined)

// 助手消息组件：渲染 Markdown 内容 + 引用来源 + 工具调用标记 + 1-5 星评分 + 转人工告警 + 后续问题推荐
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

  // 推荐问题点击：派发自定义事件，index.tsx 监听后自动发送
  const handleFollowUpClick = (question: string) => {
    // 使用 globalThis 而非 window：兼容 SSR / 非 browser 环境（SonarQube S7764）
    globalThis.dispatchEvent(new CustomEvent('chatbot:follow-up-click', { detail: question }))
  }

  // 把 [来源:N] 转成 Markdown 链接 [来源:N](#cite-N)，让 ReactMarkdown 解析为 <a> 标签
  // 然后在 components.a 中拦截 #cite- 开头的链接，渲染成带 Tooltip 的 Tag
  // 为什么用预处理而非自定义 text 渲染：react-markdown v9 不支持 components.text
  // 注意：必须跳过代码块和行内代码，否则代码内的 [来源:N] 字面量会被破坏
  const processedContent = useMemo(() => {
    if (!msg.sources || msg.sources.length === 0) return msg.content
    // replaceAll 显式表达"全局替换"语义，比 replace + g flag 更清晰（SonarQube S7781）
    const replaceCitations = (text: string) =>
      text.replaceAll(/\[来源:(\d+|\?)\]/g, (_m, num) => `[来源:${num}](#cite-${num})`)
    // 按代码块 ```...``` 和行内代码 `...` 切分，仅对非代码段做替换
    const parts: string[] = []
    let lastIndex = 0
    const codeRe = /```[\s\S]*?```|`[^`\n]+`/g
    let m: RegExpExecArray | null
    while ((m = codeRe.exec(msg.content)) !== null) {
      // 合并相邻 push 为单次调用，减少数组操作次数（SonarQube S7778）
      parts.push(replaceCitations(msg.content.slice(lastIndex, m.index)), m[0])
      lastIndex = m.index + m[0].length
    }
    parts.push(replaceCitations(msg.content.slice(lastIndex)))
    return parts.join('')
  }, [msg.content, msg.sources])

  // ReactMarkdown components：引用模块顶层组件，避免在组件内定义子组件（SonarQube S6478）
  // 依赖数组为空：MarkdownLink / MarkdownPre 均为顶层稳定引用，sources 通过 Context 透传
  const mdComponents = useMemo(() => ({
    a: MarkdownLink,
    pre: MarkdownPre,
  }), [])

  return (
    <div style={{ padding: '12px 0' }}>
      {/* 消息内容：ReactMarkdown 渲染，支持标题/列表/代码块/链接/加粗/斜体等 */}
      <div className="cb-md">
        {/* SourcesContext.Provider 把 msg.sources 注入给顶层 MarkdownLink */}
        <SourcesContext.Provider value={msg.sources}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight]}
            components={mdComponents}
          >
            {processedContent}
          </ReactMarkdown>
        </SourcesContext.Provider>
      </div>

      {/* 降级标记：RAG 降级为 FAQ 或转人工时显示 */}
      {msg.degraded && (
        <Tag color="orange" style={{ marginBottom: 8, marginTop: 8 }}>已降级</Tag>
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

      {/* 后续推荐问题：点击后自动发送，引导用户持续对话（参考豆包交互） */}
      {msg.follow_ups && msg.follow_ups.length > 0 && (
        <div className="cb-follow-ups">
          <div className="cb-follow-ups-label">您可能还想问：</div>
          <div className="cb-follow-ups-tags">
            {msg.follow_ups.map((q) => (
              <Tag
                // 基于内容生成稳定 key，避免数组索引在列表增删时错位（SonarQube S6479）
                key={q}
                className="cb-follow-up-tag"
                onClick={() => handleFollowUpClick(q)}
              >
                {q}
              </Tag>
            ))}
          </div>
        </div>
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

// Markdown 链接渲染：#cite- 开头的引用链接渲染为带 Tooltip 的 Tag，其他走原生 <a>
// 提取到模块顶层避免在 AssistantMessage 内定义子组件（SonarQube S6478/S6767）
function MarkdownLink({ href, children }: {
  readonly href?: string
  readonly children?: React.ReactNode
}) {
  // useContext 必须在条件判断之前无条件调用（React Hooks 规则）
  const sources = useContext(SourcesContext)
  // href 用可选链：避免对 undefined 调用 startsWith（SonarQube S6582）
  if (href?.startsWith('#cite-')) {
    const refNum = href.slice(6)
    const source = sources?.find((s) => s.index === Number.parseInt(refNum, 10))
    return (
      <Tooltip title={source ? `${source.file} · ${source.section}` : '来源未知'}>
        <Tag color="cyan" style={{ cursor: 'pointer', margin: '0 2px' }}>[来源:{refNum}]</Tag>
      </Tooltip>
    )
  }
  return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
}

// 代码块包装：添加语言标签 + 复制按钮，行号通过 CSS counter 实现
// 提取到模块顶层避免在 AssistantMessage 内定义子组件（SonarQube S6478）
function MarkdownPre({ children }: { readonly children?: React.ReactNode }) {
  const child = Array.isArray(children) ? children[0] : children
  if (child && typeof child === 'object' && 'props' in child) {
    const codeProps = (child as React.ReactElement<{ readonly className?: string; readonly children?: React.ReactNode }>).props
    return <CodeBlock className={codeProps.className}>{codeProps.children}</CodeBlock>
  }
  return <pre>{children}</pre>
}

// 代码块组件：语言标签 + 复制按钮 + 语法高亮（rehype-highlight 已处理）
// 行号通过 CSS counter 实现（见 chatbot.css .cb-md-code-wrap pre code）
function CodeBlock({ children, className }: { readonly children?: React.ReactNode; readonly className?: string }) {
  const [copied, setCopied] = useState(false)
  const codeRef = useRef<HTMLElement>(null)
  const lang = (className || '').replace('language-', '') || ''

  const handleCopy = async () => {
    // 从 DOM 取 textContent：rehype-highlight 处理后 children 是高亮 spans，不是纯文本
    const text = codeRef.current?.textContent || ''
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      message.error('复制失败')
    }
  }

  return (
    <div className="cb-md-code-wrap">
      <div className="cb-md-code-header">
        <span className="cb-md-code-lang">{lang || 'text'}</span>
        <button
          type="button"
          className="cb-md-copy-btn"
          onClick={handleCopy}
          aria-label="复制代码"
        >
          <CopyOutlined /> {copied ? '已复制' : '复制'}
        </button>
      </div>
      <pre>
        <code ref={codeRef} className={className}>{children}</code>
      </pre>
    </div>
  )
}
