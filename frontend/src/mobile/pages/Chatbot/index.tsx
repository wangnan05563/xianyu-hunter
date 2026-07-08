// frontend/src/mobile/pages/Chatbot/index.tsx
// 移动端智能客服对话页（精简版）：不显示会话列表，仅做基础对话
import { useState, useEffect, useRef, useCallback } from 'react'
import { Input, Button, Tag, Spin, App, theme } from 'antd'
import { SendOutlined, PlusOutlined, StopOutlined } from '@ant-design/icons'
import { chatbotApi } from '../../../pages/Chatbot/api'
import { useSSEChat } from '../../../pages/Chatbot/hooks/useSSEChat'
import type { Session, Message, SSEEvent } from '../../../pages/Chatbot/types'
import { extractApiError } from '../../../utils/apiError'

const { TextArea } = Input

// ============== 模块级 updater 函数（避免组件内多层闭包嵌套，S2004）==============

// 标记所有"发送中"的用户消息为已送达（首 token / 完成兜底共用）
const markSendingAsSent = (prev: Message[]): Message[] =>
  prev.map((m) => (m.role === 'user' && m.status === 'sending' ? { ...m, status: 'sent' } : m))

// 标记指定临时 id 的消息为失败（SSE onError 时调用）
const createFailedUpdater = (tempId: string) => (prev: Message[]): Message[] =>
  prev.map((m) => (m.id === tempId ? { ...m, status: 'failed' } : m))

// ============== 流式状态 ref / setter 类型 ==============

interface StreamRefs {
  contentRef: { current: string }
  errorRef: { current: string }
  followUpsRef: { current: string[] }
  userMsgSentRef: { current: boolean }
}

interface StreamSetters {
  setStreamingContent: (v: string) => void
  setStreamingError: (v: string) => void
}

interface SSEContext extends StreamRefs, StreamSetters {
  setMessages: (updater: (prev: Message[]) => Message[]) => void
}

// 重置流式状态（ref + state 同步重置，避免下次对话带上残留内容）
const resetStreamingState = (refs: StreamRefs, setters: StreamSetters): void => {
  refs.contentRef.current = ''
  refs.errorRef.current = ''
  refs.followUpsRef.current = []
  refs.userMsgSentRef.current = false
  setters.setStreamingContent('')
  setters.setStreamingError('')
}

// ============== SSE 事件处理（模块级查表，降低组件认知复杂度，S3776）==============

// token 事件：累加流式内容；首 token 时把用户消息从 sending → sent
const handleTokenEvent = (event: SSEEvent, ctx: SSEContext): void => {
  ctx.contentRef.current += (event.data.content as string) || ''
  ctx.setStreamingContent(ctx.contentRef.current)
  // 首 token 到达时把用户消息标记为已送达（避免重复 setState）
  if (!ctx.userMsgSentRef.current) {
    ctx.userMsgSentRef.current = true
    ctx.setMessages(markSendingAsSent)
  }
}

// error 事件：按 status 分类提示，渲染时以红色字显示
const handleErrorEvent = (event: SSEEvent, ctx: SSEContext): void => {
  const data = event.data as { message?: string; status?: number }
  const status = data.status
  const errMsg = data.message || '对话失败'
  // 401 由 useSSEChat 内部处理（跳转登录页），这里不重复处理
  // 429 限流：友好提示用户稍后重试
  if (status === 429) {
    ctx.errorRef.current = '请求过于频繁，请稍后重试'
    ctx.setStreamingError(ctx.errorRef.current)
    return
  }
  // 5xx 服务异常：提示服务端问题
  if (status && status >= 500) {
    ctx.errorRef.current = '服务暂时不可用，请稍后重试'
    ctx.setStreamingError(ctx.errorRef.current)
    return
  }
  // 其他错误：显示原始错误信息
  ctx.errorRef.current = errMsg
  ctx.setStreamingError(errMsg)
}

// done 事件：保存推荐问题到 ref，onComplete 读取后写入 assistant 消息
const handleDoneEvent = (event: SSEEvent, ctx: SSEContext): void => {
  ctx.followUpsRef.current = (event.data.follow_ups as string[]) || []
}

// SSE 事件派发表：type → handler；新增事件只需在表内加一行
const SSE_HANDLERS: Record<string, (event: SSEEvent, ctx: SSEContext) => void> = {
  token: handleTokenEvent,
  error: handleErrorEvent,
  done: handleDoneEvent,
}

// ============== onComplete 工厂：固化 assistant 消息 + 重置流式状态 ==============

interface CompleteDeps {
  refs: StreamRefs
  setters: StreamSetters
  setMessages: (updater: (prev: Message[]) => Message[]) => void
  sessionId: string
}

// 流结束时把临时流式内容固化为正式 assistant 消息
// 为什么用 ref 而非闭包 state：async 回调里闭包捕获的是发送时刻快照，
// ref.current 可变能拿最新值，从而正确固化 assistant 消息
const createCompleteHandler = (deps: CompleteDeps) => (): void => {
  // 终止事件触发后，确保用户消息从 sending → sent
  if (!deps.refs.userMsgSentRef.current) {
    deps.refs.userMsgSentRef.current = true
    deps.setMessages(markSendingAsSent)
  }
  const content = deps.refs.contentRef.current
  const error = deps.refs.errorRef.current
  const followUps = deps.refs.followUpsRef.current
  // 有内容/错误/推荐问题时才固化（避免空回复污染消息列表）
  if (content || error || followUps.length > 0) {
    const assistantMsg: Message = {
      id: `assistant-${Date.now()}`,
      session_id: deps.sessionId,
      role: 'assistant',
      content: error ? `错误: ${error}` : content || '(空回复)',
      follow_ups: followUps.length > 0 ? followUps : undefined,
      created_at: new Date().toISOString(),
    }
    deps.setMessages((prev) => [...prev, assistantMsg])
  }
  resetStreamingState(deps.refs, deps.setters)
}

// ============== 主组件 ==============

export default function MobileChatbot() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [currentSession, setCurrentSession] = useState<Session | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [welcomeMessage, setWelcomeMessage] = useState('')

  // 流式响应状态（state 仅用于驱动渲染）
  const [streamingContent, setStreamingContent] = useState('')
  const [streamingError, setStreamingError] = useState('')

  // ref 镜像：onComplete 闭包陷阱修复
  // 闭包捕获的 state 是发送时刻快照，async 回调里始终读到旧值；
  // ref.current 可变，回调里能拿到最新值
  const contentRef = useRef('')
  const errorRef = useRef('')
  const followUpsRef = useRef<string[]>([])
  const userMsgSentRef = useRef(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { isStreaming, sendMessage, cancel } = useSSEChat()

  // ============== 初始化：恢复最近会话或创建新会话 + 加载欢迎语 ==============
  // cancelled 标志防止卸载后 setState（F-REVIEW-ASYNC-RACE-GUARD）
  useEffect(() => {
    let cancelled = false
    const init = async (): Promise<void> => {
      try {
        // 欢迎语失败不阻断主流程，仅 UI 缺失
        const welcome = await chatbotApi.getWelcome().catch(() => null)
        if (cancelled) return
        if (welcome) setWelcomeMessage(welcome.message)

        // 取最近 1 条会话作为当前会话，避免每次进入都新建
        const { items } = await chatbotApi.listSessions(1, 1)
        if (cancelled) return
        if (items.length > 0) {
          setCurrentSession(items[0])
          const { items: msgs } = await chatbotApi.listMessages(items[0].id, 50)
          if (cancelled) return
          setMessages(msgs)
        } else {
          // 无历史会话则创建新会话
          const session = await chatbotApi.createSession()
          if (cancelled) return
          setCurrentSession(session)
        }
      } catch (e) {
        if (!cancelled) message.error(extractApiError(e, '初始化失败，请刷新重试'), 3)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void init()
    return () => { cancelled = true }
  }, [message])

  // ============== 自动滚动到底部 ==============
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, streamingContent, streamingError])

  // ============== SSE 事件派发 ==============
  // useState 的 setter 是稳定引用，空依赖安全
  const handleSSEEvent = useCallback((event: SSEEvent) => {
    const handler = SSE_HANDLERS[event.type]
    if (!handler) return
    handler(event, {
      contentRef,
      errorRef,
      followUpsRef,
      userMsgSentRef,
      setStreamingContent,
      setStreamingError,
      setMessages,
    })
  }, [])

  // ============== 发送消息 ==============
  const handleSend = async (overrideText?: string): Promise<void> => {
    // overrideText 用于推荐问题点击发送：绕过 inputValue 直接用指定文本
    const text = overrideText ?? inputValue
    if (!text.trim() || !currentSession || isStreaming) return

    const userMsg: Message = {
      id: `temp-${Date.now()}`,
      session_id: currentSession.id,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
      status: 'sending',
    }
    setMessages((prev) => [...prev, userMsg])
    const tempId = userMsg.id
    setInputValue('')

    const refs: StreamRefs = { contentRef, errorRef, followUpsRef, userMsgSentRef }
    const setters: StreamSetters = { setStreamingContent, setStreamingError }
    resetStreamingState(refs, setters)

    await sendMessage({
      sessionId: currentSession.id,
      message: text,
      enableTools: true,
      onEvent: handleSSEEvent,
      // useSSEChat 内部已用 antd message 提示错误，这里仅标记失败消息，不重复提示
      onError: () => {
        setMessages(createFailedUpdater(tempId))
      },
      onComplete: createCompleteHandler({
        refs,
        setters,
        setMessages,
        sessionId: currentSession.id,
      }),
    })
  }

  // ============== 新建会话 ==============
  const handleNewSession = async (): Promise<void> => {
    try {
      const session = await chatbotApi.createSession()
      setCurrentSession(session)
      setMessages([])
    } catch (e) {
      message.error(extractApiError(e, '创建会话失败'), 3)
    }
  }

  // ============== 推荐问题点击：自动发送 ==============
  const handleFollowUpClick = (question: string): void => {
    if (isStreaming) return
    void handleSend(question)
  }

  // ============== Enter 发送，Shift+Enter 换行 ==============
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin />
      </div>
    )
  }

  // ============== 渲染消息气泡 ==============
  const renderMessage = (msg: Message): React.ReactNode => {
    if (msg.role === 'system') {
      return (
        <div
          key={msg.id}
          style={{ textAlign: 'center', color: '#999', fontSize: 12, margin: '4px 0' }}
        >
          {msg.content}
        </div>
      )
    }
    const isUser = msg.role === 'user'
    return (
      <div
        key={msg.id}
        style={{
          display: 'flex',
          justifyContent: isUser ? 'flex-end' : 'flex-start',
          marginBottom: 12,
        }}
      >
        <div
          style={{
            borderRadius: 12,
            padding: '8px 12px',
            maxWidth: '80%',
            backgroundColor: isUser ? themeToken.colorPrimary : themeToken.colorBgContainer,
            color: isUser ? 'white' : 'rgba(0,0,0,0.85)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {msg.content}
          {/* 推荐问题：可点击的小标签，点击后自动发送 */}
          {!isUser && msg.follow_ups && msg.follow_ups.length > 0 && (
            <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {msg.follow_ups.map((q) => (
                <Tag
                  key={q}
                  onClick={() => handleFollowUpClick(q)}
                  style={{ cursor: 'pointer', margin: 0 }}
                >
                  {q}
                </Tag>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // ============== 渲染流式响应气泡 ==============
  const renderStreaming = (): React.ReactNode => {
    if (!isStreaming) return null
    const content = streamingContent || (streamingError ? `错误: ${streamingError}` : '')
    // 无内容时显示思考中占位，让用户知道正在等待响应
    if (!content) {
      return (
        <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 12 }}>
          <div
            style={{
              borderRadius: 12,
              padding: '8px 12px',
              backgroundColor: '#f5f5f5',
              color: '#999',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Spin size="small" />
            <span>思考中...</span>
          </div>
        </div>
      )
    }
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 12 }}>
        <div
          style={{
            borderRadius: 12,
            padding: '8px 12px',
            maxWidth: '80%',
            backgroundColor: '#f5f5f5',
            color: streamingError ? '#ff4d4f' : 'rgba(0,0,0,0.85)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {content}
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* 顶部：当前会话标题 + 新会话按钮 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 12px',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <span
          style={{
            fontWeight: 600,
            fontSize: 14,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
            marginRight: 8,
          }}
        >
          {currentSession?.title || '智能客服'}
        </span>
        <Button size="small" icon={<PlusOutlined />} onClick={() => void handleNewSession()}>
          新会话
        </Button>
      </div>

      {/* 消息列表（可滚动区域） */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {/* 欢迎语：仅 UI 展示，不入库 */}
        {welcomeMessage && (
          <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 12 }}>
            <div
              style={{
                borderRadius: 12,
                padding: '8px 12px',
                maxWidth: '80%',
                backgroundColor: '#f5f5f5',
                color: 'rgba(0,0,0,0.85)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {welcomeMessage}
            </div>
          </div>
        )}
        {messages.map(renderMessage)}
        {renderStreaming()}
        <div ref={messagesEndRef} />
      </div>

      {/* 底部输入区（固定） */}
      <div
        style={{
          padding: 12,
          borderTop: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'flex-end',
          gap: 8,
        }}
      >
        <TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息，Enter 发送，Shift+Enter 换行"
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={isStreaming}
          style={{ flex: 1 }}
        />
        {isStreaming ? (
          <Button
            danger
            shape="circle"
            icon={<StopOutlined />}
            onClick={cancel}
            aria-label="停止生成"
          />
        ) : (
          <Button
            type="primary"
            shape="circle"
            icon={<SendOutlined />}
            onClick={() => void handleSend()}
            disabled={!inputValue.trim()}
            aria-label="发送消息"
          />
        )}
      </div>
    </div>
  )
}
