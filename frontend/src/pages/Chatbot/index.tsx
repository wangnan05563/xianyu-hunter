import { useState, useEffect, useRef, useCallback } from 'react'
import { Layout, List, Button, Input, Typography, Tag, Popconfirm, Empty, Spin, Upload, message, Modal } from 'antd'
import {
  PlusOutlined,
  UserOutlined,
  DeleteOutlined,
  StopOutlined,
  MenuOutlined,
  PictureOutlined,
  CloseCircleFilled,
  SyncOutlined,
  StarOutlined,
  StarFilled,
  SearchOutlined,
  QuestionCircleOutlined,
  CustomerServiceOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import { useSSEChat } from './hooks/useSSEChat'
import { useSearch } from '../../hooks/useSearch'
import { useSearchHistory } from '../../hooks/useSearchHistory'
import { chatbotApi } from './api'
import { AssistantMessage } from './components/AssistantMessage'
import ChatbotOnboarding, {
  isOnboardingDismissed,
  resetOnboardingDismissed,
} from './components/ChatbotOnboarding'
import QuickReplyChips from './components/QuickReplyChips'
import HelpCenterModal from './components/HelpCenterModal'
import type { Session, Message, SSEEvent, ToolCall, FAQ } from './types'
import './chatbot.css'

const { Sider, Content } = Layout
const { TextArea } = Input

// S2004 修复：以下 updater 函数提取到模块级，避免组件内多层闭包嵌套超过 4 层。
// setState 的函数式更新若以箭头函数形式内联在深层回调里，会让嵌套层级随外层
// useEffect/事件处理器/onOk 等层层叠加而突破阈值。这里把它们抽为纯函数或
// 工厂函数（返回 updater），调用方传入参数即可获得一个无闭包依赖的 updater。

// 移除所有 status==='failed' 的消息（重试时清理旧的失败消息）
const filterOutFailedMessages = (prev: Message[]): Message[] =>
  prev.filter((m) => m.status !== 'failed')

// 标记指定 id 的消息为已撤回
const createRecalledMessageUpdater = (id: string) => (prev: Message[]): Message[] =>
  prev.map((m) => (m.id === id ? { ...m, is_recalled: 1 } : m))

// 标记指定会话为已转人工
const createEscalatedSessionUpdater = (sessionId: string) => (prev: Session[]): Session[] =>
  prev.map((s) => (s.id === sessionId ? { ...s, status: 'escalated' } : s))

// 标记指定临时 id 的消息为失败
const createFailedMessageUpdater = (tempId: string) => (prev: Message[]): Message[] =>
  prev.map((m) => (m.id === tempId ? { ...m, status: 'failed' } : m))

// 删除待发送图片列表中指定索引项
const createRemoveImageUpdater = (idx: number) => (prev: string[]): string[] =>
  prev.filter((_, i) => i !== idx)

// 重置流式响应的 ref + state（handleSend 启动时与 onComplete 兜底时共享）
// S2004 修复：抽到模块级避免在 onComplete 内联函数中重复写入逻辑、加深嵌套
const resetStreamingState = (refs: {
  streamingContentRef: { current: string }
  streamingSourcesRef: { current: Message['sources'] }
  streamingToolCallsRef: { current: Message['tool_calls'] }
  escalatedRef: { current: boolean }
  escalateReasonRef: { current: string }
  streamingFollowUpsRef: { current: string[] }
  userMsgSentRef: { current: boolean }
  setStreamingContent: (v: string) => void
  setStreamingSources: (v: Message['sources']) => void
  setStreamingToolCalls: (v: Message['tool_calls']) => void
}) => {
  refs.streamingContentRef.current = ''
  refs.streamingSourcesRef.current = []
  refs.streamingToolCallsRef.current = []
  refs.escalatedRef.current = false
  refs.escalateReasonRef.current = ''
  refs.streamingFollowUpsRef.current = []
  refs.userMsgSentRef.current = false
  refs.setStreamingContent('')
  refs.setStreamingSources([])
  refs.setStreamingToolCalls([])
}

// 处理 SSE 事件：模块级查表，避免 handleSSEEvent switch 内联多 case
// S2004/S3776 修复：每个 case 拆为独立模块级函数，switch 仅做派发，复杂度大幅降低
type StreamRefs = {
  streamingContentRef: { current: string }
  streamingSourcesRef: { current: Message['sources'] }
  streamingToolCallsRef: { current: Message['tool_calls'] }
  escalatedRef: { current: boolean }
  escalateReasonRef: { current: string }
  streamingFollowUpsRef: { current: string[] }
  userMsgSentRef: { current: boolean }
}
type StreamSetters = {
  setMessages: (updater: (prev: Message[]) => Message[]) => void
  setStreamingContent: (v: string) => void
  setStreamingSources: (v: Message['sources']) => void
  setStreamingToolCalls: (v: Message['tool_calls']) => void
}
type StreamContext = StreamRefs & StreamSetters

// 标记所有"发送中"的用户消息为已送达（首 token 兜底/完成兜底共用）
const markSendingUserMessagesAsSent = (prev: Message[]): Message[] =>
  prev.map((m) =>
    m.role === 'user' && m.status === 'sending' ? { ...m, status: 'sent' } : m,
  )

// SSE token 事件：累加流式内容；首 token 时把用户消息从 sending → sent
const handleSSEToken = (event: SSEEvent, ctx: StreamContext) => {
  ctx.streamingContentRef.current += (event.data.content as string || '')
  ctx.setStreamingContent(ctx.streamingContentRef.current)
  if (!ctx.userMsgSentRef.current) {
    ctx.userMsgSentRef.current = true
    ctx.setMessages(markSendingUserMessagesAsSent)
  }
}

// SSE sources 事件：替换引用源
const handleSSESources = (event: SSEEvent, ctx: StreamContext) => {
  ctx.streamingSourcesRef.current = event.data.sources as Message['sources']
  ctx.setStreamingSources(ctx.streamingSourcesRef.current)
}

// SSE tool_call 事件：追加到工具调用列表
const handleSSEToolCall = (event: SSEEvent, ctx: StreamContext) => {
  ctx.streamingToolCallsRef.current = [
    ...(ctx.streamingToolCallsRef.current || []),
    event.data as unknown as ToolCall,
  ]
  ctx.setStreamingToolCalls(ctx.streamingToolCallsRef.current)
}

// SSE error 事件：按 code 分支显示友好提示
const handleSSEError = (event: SSEEvent) => {
  const code = event.data.code as string
  const msg = event.data.message as string
  if (code === 'SECURITY_VIOLATION') {
    message.warning('检测到不安全输入，已拦截')
  } else if (code === 'OUT_OF_SCOPE') {
    message.warning(msg || '该问题超出客服范围')
  } else {
    message.error(msg || '生成失败')
  }
}

// SSE escalate 事件：转人工话术写入流式内容并标记 escalated
const handleSSEEscale = (event: SSEEvent, ctx: StreamContext) => {
  const escalateMsg = event.data.message as string
  const reason = event.data.reason as string
  if (escalateMsg) {
    ctx.streamingContentRef.current = escalateMsg
    ctx.setStreamingContent(escalateMsg)
  }
  ctx.escalatedRef.current = true
  ctx.escalateReasonRef.current = reason || ''
}

// SSE done 事件：保存 follow_ups 供 onComplete 读取
const handleSSEDone = (event: SSEEvent, ctx: StreamContext) => {
  ctx.streamingFollowUpsRef.current = (event.data.follow_ups as string[]) || []
}

// SSE 事件派发表：type → handler；新增事件只需在表内加一行
const SSE_EVENT_HANDLERS: Record<string, (event: SSEEvent, ctx: StreamContext) => void> = {
  token: handleSSEToken,
  sources: handleSSESources,
  tool_call: handleSSEToolCall,
  error: handleSSEError,
  escalate: handleSSEEscale,
  done: handleSSEDone,
}

// SSE onError 工厂：把临时消息标 failed 并 toast 错误
// S2004 修复：抽到模块级避免 sendMessage 回调内联加深嵌套
type SendErrorDeps = {
  setMessages: (updater: (prev: Message[]) => Message[]) => void
}
const createSendErrorHandler = (tempId: string, deps: SendErrorDeps) => (err: Error) => {
  deps.setMessages(createFailedMessageUpdater(tempId))
  message.error('对话失败: ' + err.message)
}

// SSE onComplete 工厂：固化 assistant 消息 + 重置流式状态 + 刷新会话列表
// S2004/S3776 修复：抽到模块级避免在 sendMessage 回调内联加深 handleSend 嵌套/复杂度
type SendCompleteDeps = {
  refs: StreamRefs
  setMessages: (updater: (prev: Message[]) => Message[]) => void
  setStreamingContent: (v: string) => void
  setStreamingSources: (v: Message['sources']) => void
  setStreamingToolCalls: (v: Message['tool_calls']) => void
  sessionId: string
  onAfterComplete: () => void
}
const createSendCompleteHandler = (deps: SendCompleteDeps) => () => {
  // 终止事件（done/error/escalate）触发后，确保用户消息从 sending → sent
  if (!deps.refs.userMsgSentRef.current) {
    deps.refs.userMsgSentRef.current = true
    deps.setMessages(markSendingUserMessagesAsSent)
  }
  // 读 ref.current 而非闭包 state（避免读到发送时刻的空快照）
  const content = deps.refs.streamingContentRef.current
  const sources = deps.refs.streamingSourcesRef.current
  const toolCalls = deps.refs.streamingToolCallsRef.current
  const escalated = deps.refs.escalatedRef.current
  const escalateReason = deps.refs.escalateReasonRef.current
  const followUps = deps.refs.streamingFollowUpsRef.current
  appendAssistantMessageIfAny(deps, content, sources, toolCalls, escalated, escalateReason, followUps)
  resetStreamingState({
    ...deps.refs,
    setStreamingContent: deps.setStreamingContent,
    setStreamingSources: deps.setStreamingSources,
    setStreamingToolCalls: deps.setStreamingToolCalls,
  })
  deps.onAfterComplete()
}

// 当有内容/来源/工具调用/转人工标记/推荐问题时，固化一条 assistant 消息
// S3776 修复：从 onComplete 内提取，消除巨型 if + 巨型对象字面量产生的认知复杂度
const appendAssistantMessageIfAny = (
  deps: SendCompleteDeps,
  content: string,
  sources: Message['sources'],
  toolCalls: Message['tool_calls'],
  escalated: boolean,
  escalateReason: string,
  followUps: string[],
) => {
  // escalate 事件无 content 时也要固化（转人工话术可能为空）；
  // follow_ups 也需纳入判断：主回答为空但生成了推荐问题时不能丢弃
  if (!content && !sources?.length && !toolCalls?.length && !escalated && followUps.length === 0) {
    return
  }
  const assistantMsg: Message = {
    id: `assistant-${Date.now()}`,
    session_id: deps.sessionId,
    role: 'assistant',
    content: content || '(空回复)',
    sources,
    tool_calls: toolCalls,
    escalated: escalated || undefined,
    escalate_reason: escalateReason || undefined,
    follow_ups: followUps.length > 0 ? followUps : undefined,
    created_at: new Date().toISOString(),
  }
  deps.setMessages((prev) => [...prev, assistantMsg])
}

// 转人工确认弹窗 onOk 实现：调用接口 + 更新 sessions/currentSession
// S2004 修复：从 handleEscalate 的内联 onOk 提取，避免组件内 4 层嵌套
type EscalateDeps = {
  setEscalating: (v: boolean) => void
  setSessions: (updater: (prev: Session[]) => Session[]) => void
  setCurrentSession: (updater: (prev: Session | null) => Session | null) => void
}
const confirmEscalate = async (targetSessionId: string, deps: EscalateDeps) => {
  deps.setEscalating(true)
  try {
    await chatbotApi.triggerEscalation(targetSessionId)
    deps.setSessions(createEscalatedSessionUpdater(targetSessionId))
    // 函数式更新：仅当用户仍停留在原会话时才更新当前会话状态
    deps.setCurrentSession((prev) =>
      prev?.id === targetSessionId ? { ...prev, status: 'escalated' } : prev,
    )
    message.success('已转接人工客服')
  } catch {
    message.error('转接失败，请稍后重试')
  } finally {
    deps.setEscalating(false)
  }
}

// 渲染消息气泡内的图片缩略图列表：每个图片用原生 button 包裹
// S6819/S6842 修复：img 加 role=button 是非交互元素加交互 role，改用 button 替代
// 为什么单独抽出来：让 MessageBubble 组件的 JSX 层级扁平，且 TypeScript 收窄
// imgs 参数为 string[] 后无需再依赖 msg.images 的可能为 null/undefined 的类型
const renderMessageImages = (imgs: string[], win: typeof globalThis) => (
  <div className="cb-msg-images">
    {imgs.map((img, idx) => (
      <button
        // S6479：图片 URL 作为稳定 key
        key={img}
        type="button"
        onClick={() => win.open(img, '_blank')}
        aria-label={`查看图片${idx + 1}`}
        // S6819/S6842：改用原生 button 替代 img+role=button，
        // 原生支持 Enter/Space 触发 click；重置外观以保留 cb-msg-image-thumb 视觉
        style={{ background: 'none', border: 'none', padding: 0, display: 'inline-flex', cursor: 'pointer' }}
      >
        <img
          src={img}
          alt={`图片${idx + 1}`}
          className="cb-msg-image-thumb"
        />
      </button>
    ))}
  </div>
)

// 极简商务头像：深色方块 + "AI" 字母，替代原机器人图标
function BotAvatar() {
  return (
    <div className="cb-avatar cb-avatar-bot" aria-label="AI 助手">
      AI
    </div>
  )
}

// 空状态插画：极简聊天气泡图标，替代原机器人插画
function EmptyIllustration() {
  return (
    <div className="cb-empty-illustration" aria-hidden="true">
      <MessageOutlined />
    </div>
  )
}

export default function ChatbotPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSession, setCurrentSession] = useState<Session | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [enableTools, setEnableTools] = useState(true)
  // 待发送的图片 base64 data URL 列表（最多 4 张，发送后清空）
  const [pendingImages, setPendingImages] = useState<string[]>([])

  // 图片转 base64 data URL（FileReader.readAsDataURL）
  const fileToDataUrl = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as string)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })

  // 添加图片：校验类型/大小/数量，通过后转 base64 加入 pendingImages
  // S3516 修复：原 setPendingImages 回调总返回 prev，等同无更新。
  // 改为遍历异步转 base64，每个就绪后用 functional update 追加，并在追加前
  // 用闭包计数避免重复警告（functional update 内不能放副作用）。
  // S2004 修复：循环体与 if 分支抽到模块级 addImageIfValid，降低 useCallback 内嵌套
  const MAX_IMAGES = 4
  const MAX_IMAGE_SIZE = 5 * 1024 * 1024 // 5MB
  const addImageFiles = useCallback(async (files: FileList | File[]) => {
    const arr = Array.from(files).filter((f) => f.type.startsWith('image/'))
    if (arr.length === 0) return
    // 用 ref-like 闭包变量跟踪是否已警告，避免重复提示
    const state: { warnedLimit: boolean } = { warnedLimit: false }
    for (const f of arr) {
      await addImageIfValid(f, state, setPendingImages)
    }
  }, [])

  // 单个图片处理：超过大小/数量限制时跳过或提示，并通过 setPendingImages updater 追加
  // S2004 修复：抽到模块级避免 for 内 5 层 if/try/setState 嵌套
  const addImageIfValid = async (
    f: File,
    state: { warnedLimit: boolean },
    setPendingImages: React.Dispatch<React.SetStateAction<string[]>>,
  ) => {
    if (f.size > MAX_IMAGE_SIZE) {
      message.warning(`${f.name} 超过 5MB，已跳过`)
      return
    }
    let url: string
    try {
      url = await fileToDataUrl(f)
    } catch {
      // 单个文件转 base64 失败时忽略，不影响其他文件
      return
    }
    let added = false
    setPendingImages((p) => {
      if (p.length >= MAX_IMAGES) return p
      added = true
      return [...p, url]
    })
    if (!added && !state.warnedLimit) {
      state.warnedLimit = true
      message.warning(`最多 ${MAX_IMAGES} 张图片`)
    }
  }

  // Upload beforeUpload：拦截不发请求，转 base64
  const handleUploadSelect = useCallback(
    (file: File) => {
      addImageFiles([file])
      return false // 阻止 antd Upload 自动上传
    },
    [addImageFiles],
  )

  // 粘贴图片：监听 paste 事件提取 image 类型项
  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      const items = e.clipboardData?.items
      if (!items) return
      const imageFiles: File[] = []
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          const f = item.getAsFile()
          if (f) imageFiles.push(f)
        }
      }
      if (imageFiles.length > 0) {
        e.preventDefault()
        addImageFiles(imageFiles)
      }
    },
    [addImageFiles],
  )

  // 拖拽图片：dragover/drop 事件
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      if (e.dataTransfer?.files?.length) {
        addImageFiles(e.dataTransfer.files)
      }
    },
    [addImageFiles],
  )
  const [loadingSessions, setLoadingSessions] = useState(false)
  const [loadingMessages, setLoadingMessages] = useState(false)
  // M2：会话搜索 + 收藏过滤
  const [searchKeyword, setSearchKeyword] = useState('')
  const [favoriteOnly, setFavoriteOnly] = useState(false)
  // M5：帮助中心弹窗 + 转人工加载
  const [helpOpen, setHelpOpen] = useState(false)
  const [escalating, setEscalating] = useState(false)
  // 移动端会话抽屉开关：桌面端 Sider 始终展开，移动端默认收起，点击切换按钮滑入
  const [siderOpen, setSiderOpen] = useState(false)
  // 流式响应中的临时消息内容（state 仅用于驱动渲染）
  const [streamingContent, setStreamingContent] = useState('')
  const [streamingSources, setStreamingSources] = useState<Message['sources']>([])
  const [streamingToolCalls, setStreamingToolCalls] = useState<Message['tool_calls']>([])

  // ref 镜像：onComplete 闭包陷阱修复（B-1）
  // 闭包捕获的 state 是发送时刻的快照，async 回调里始终读到旧值；
  // ref.current 可变，回调里能拿到最新值，从而正确固化 assistant 消息
  const streamingContentRef = useRef('')
  const streamingSourcesRef = useRef<Message['sources']>([])
  const streamingToolCallsRef = useRef<Message['tool_calls']>([])
  // H-3：转人工标记，onComplete 据此给 assistantMsg 打 escalated 标记
  const escalatedRef = useRef(false)
  const escalateReasonRef = useRef('')
  // 后续推荐问题 ref：done 事件携带，onComplete 读取后存入消息
  const streamingFollowUpsRef = useRef<string[]>([])
  // handleSend ref：后续问题点击事件监听需要调用最新版 handleSend，
  // 但 handleSend 每次渲染重建，空依赖 useEffect 会捕获旧版本
  const handleSendRef = useRef<(text?: string) => Promise<void>>(() => Promise.resolve())
  // M1 引导卡 FAQ 点击后暂存待发送内容（创建会话后 setInputValue）
  const pendingFaqRef = useRef<string | null>(null)
  // M3：用户消息已送达标记（首 token 到达时切到 sent，避免重复 setState）
  const userMsgSentRef = useRef(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const { isStreaming, sendMessage, cancel } = useSSEChat()

  // M1 引导卡关闭状态：localStorage 记忆 + 会话切换重置
  const [onboardingDismissed, setOnboardingDismissed] = useState<boolean>(
    () => isOnboardingDismissed(),
  )
  // 切换会话时重置引导卡关闭状态
  useEffect(() => {
    setOnboardingDismissed(false)
    resetOnboardingDismissed()
  }, [currentSession?.id])
  // 切换会话后自动聚焦输入框（M3）
  useEffect(() => {
    if (!isStreaming && inputRef.current) {
      inputRef.current.focus()
    }
  }, [currentSession?.id, isStreaming])

  // M3 快捷回复：从 FAQ 列表过滤 category='快捷' 的项
  const [quickReplies, setQuickReplies] = useState<FAQ[]>([])
  useEffect(() => {
    chatbotApi
      .listFAQ()
      .then((list) => {
        // 用 category 过滤：避免改 DB 迁移。约定 category 含"快捷"字样的 FAQ 作为快捷回复
        setQuickReplies(
          list
            .filter(
              (f) =>
                f.enabled &&
                (f.category === '快捷' ||
                  f.category === '快捷回复' ||
                  f.category === 'quick'),
            )
            .slice(0, 8),
        )
      })
      .catch(() => {
        // 静默失败：快捷回复非关键功能
      })
  }, [])

  // M3 重试：监听 MessageBubble 派发的 retry-send 事件
  // 触发时把原文本填回输入框 + 图片恢复 pendingImages，并移除原失败消息
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ text: string; images: string[] }>).detail
      if (!detail) return
      // 填回输入框 + 图片
      setInputValue(detail.text)
      setPendingImages(detail.images || [])
      // 移除状态为 failed 的同内容用户消息（避免重复）
      // S2004：updater 提取到模块级 filterOutFailedMessages
      setMessages(filterOutFailedMessages)
    }
    globalThis.addEventListener('chatbot:retry-send', handler)
    return () => globalThis.removeEventListener('chatbot:retry-send', handler)
  }, [])

  // M4 消息撤回：监听 MessageBubble 派发的 recall 事件
  useEffect(() => {
    // S3735 修复：原 `void (async () => {...})()` 用 void 调用 IIFE，改为直接用 async 函数。
    // addEventListener 接受 async handler（返回 Promise<void> 兼容 void 签名），
    // 内部 try/catch 包裹所有异步操作，不会产生未捕获 rejection
    const handleRecall = async (e: Event) => {
      const detail = (e as CustomEvent<{ id: string }>).detail
      if (!detail) return
      try {
        await chatbotApi.recallMessage(detail.id)
        // 乐观更新：立即把消息标记为已撤回
        // S2004：updater 由模块级工厂 createRecalledMessageUpdater 生成
        setMessages(createRecalledMessageUpdater(detail.id))
        message.success('已撤回')
      } catch {
        message.error('撤回失败，可能已超过 2 分钟时限')
      }
    }
    globalThis.addEventListener('chatbot:recall-message', handleRecall)
    return () => globalThis.removeEventListener('chatbot:recall-message', handleRecall)
  }, [])

  // M5：主动转人工——确认后调用 escalation/trigger
  // S2004 修复：onOk 内联 async 嵌套 4 层（setEscalating → try → await → setState/setSession），
  // 提取为模块级 confirmEscalate，降低 handleEscalate 嵌套深度
  const handleEscalate = () => {
    if (!currentSession) {
      message.warning('请先选择一个会话')
      return
    }
    // 捕获当前会话 ID，避免 onOk 闭包在用户切换会话后更新错误的会话
    const targetSessionId = currentSession.id
    Modal.confirm({
      title: '转接人工客服',
      content: '将转接至人工客服，当前会话状态会变更为"已转人工"。是否继续？',
      okText: '确认转接',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () =>
        confirmEscalate(targetSessionId, {
          setEscalating,
          setSessions,
          setCurrentSession,
        }),
    })
  }

  // 搜索历史：用户每次提交非空关键词时记录，供快速复用
  // 必须在 loadSessions 之前声明：loadSessions 依赖 addSessionHistory
  const { history: sessionHistory, add: addSessionHistory, clear: clearSessionHistory } = useSearchHistory({ namespace: 'chatbot' })

  // 加载会话列表（M2：支持关键词搜索 + 收藏过滤）
  const loadSessions = useCallback(async () => {
    setLoadingSessions(true)
    try {
      const { items } = await chatbotApi.listSessions(1, 50, searchKeyword || undefined, favoriteOnly)
      setSessions(items)
      // 默认选中第一个会话
      if (items.length > 0 && !currentSession) {
        setCurrentSession(items[0])
      }
      // 搜索成功且关键词非空时记录历史，供后续快速复用
      // 可选链替代 searchKeyword && searchKeyword.trim()：S6582
      if (searchKeyword?.trim()) {
        addSessionHistory(searchKeyword.trim())
      }
    } catch {
      message.error('加载会话列表失败')
    } finally {
      setLoadingSessions(false)
    }
  }, [currentSession, searchKeyword, favoriteOnly, addSessionHistory])

  // M2：搜索防抖——使用统一 useSearch hook（400ms），与 Alpine 模板对齐
  // 替代手写 setTimeout 防抖，获得并发保护 + 取消过时请求能力
  useSearch({
    search: () => loadSessions(),
    deps: [loadSessions],
  })

  // 切换会话时加载消息
  useEffect(() => {
    if (!currentSession) return
    const loadMessages = async () => {
      setLoadingMessages(true)
      try {
        const { items } = await chatbotApi.listMessages(currentSession.id, 50)
        setMessages(items)
      } catch {
        message.error('加载消息失败')
      } finally {
        setLoadingMessages(false)
      }
    }
    loadMessages()
  }, [currentSession])

  // 自动滚动到底部
  // 修复：scrollIntoView 会沿 DOM 祖先链向上找所有可滚动容器。
  // 当 .cb-messages 内容较少、未实际产生滚动条时，浏览器会跳过它继续向上找，
  // 最终滚动到外层 MainLayout.Content（overflow: auto），把整页（连同 Header）一起向下
  // 移动，导致顶部内容被截断、用户无法滚回顶部。
  // 改为显式定位到最近的消息容器 .cb-messages，调用其 scrollTo，避免影响外层滚动。
  // 同时增加"用户已接近底部"判断：仅在接近底部时自动滚动，
  // 用户主动上滑查看历史消息时不会被强制拉回底部。
  useEffect(() => {
    const endEl = messagesEndRef.current
    if (!endEl) return
    const scrollContainer = endEl.closest<HTMLDivElement>('.cb-messages')
    if (!scrollContainer) return
    // 距离底部 < 80px 视为"在底部"；首次加载（scrollTop === 0）也强制滚到底部
    const distanceToBottom =
      scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight
    if (distanceToBottom < 80) {
      // 首次加载用 auto 避免动画卡顿；后续用 smooth
      const isInitialLoad = scrollContainer.scrollTop === 0
      scrollContainer.scrollTo({
        top: scrollContainer.scrollHeight,
        behavior: isInitialLoad ? 'auto' : 'smooth',
      })
    }
  }, [messages, streamingContent])

  const handleCreateSession = async () => {
    try {
      const session = await chatbotApi.createSession()
      setSessions((prev) => [session, ...prev])
      setCurrentSession(session)
      setMessages([])
    } catch {
      message.error('创建会话失败')
    }
  }

  const handleDeleteSession = async (id: string) => {
    try {
      await chatbotApi.deleteSession(id)
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (currentSession?.id === id) {
        setCurrentSession(null)
        setMessages([])
      }
      message.success('已删除')
    } catch {
      message.error('删除失败')
    }
  }

  // M2：切换收藏状态（乐观更新，失败回滚）
  const handleToggleFavorite = async (id: string, currentFav: boolean) => {
    const prevSessions = sessions
    const newFav = !currentFav
    // 乐观更新：立即切换图标
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, is_favorite: newFav ? 1 : 0 } : s)),
    )
    try {
      await chatbotApi.toggleFavorite(id, newFav)
      // 重新加载列表以应用收藏置顶排序
      loadSessions()
    } catch {
      // 回滚
      setSessions(prevSessions)
      message.error('收藏失败')
    }
  }

  // SSE 事件处理：派发表查表，handler 在模块级；不在此处写 switch/case
  // S2004/S3776 修复：消除组件内 switch 的多层嵌套与认知复杂度
  const handleSSEEvent = useCallback(
    (event: SSEEvent) => {
      const handler = SSE_EVENT_HANDLERS[event.type]
      if (!handler) return
      handler(event, {
        streamingContentRef,
        streamingSourcesRef,
        streamingToolCallsRef,
        escalatedRef,
        escalateReasonRef,
        streamingFollowUpsRef,
        userMsgSentRef,
        setMessages,
        setStreamingContent,
        setStreamingSources,
        setStreamingToolCalls,
      })
    },
    [],
  )

  const handleSend = async (overrideText?: string) => {
    // overrideText 用于后续问题点击发送：绕过 inputValue 直接用指定文本
    const text = overrideText ?? inputValue
    if (!text.trim() || !currentSession || isStreaming) return
    // escalated 是终态：后端 should_escalate 会直接返回转人工，绕过 FAQ/RAG
    // 阻止发送并提示用户创建新会话，避免无意义的转人工回复
    if (currentSession.status === 'escalated') {
      message.warning('当前会话已转人工，请创建新会话继续咨询')
      return
    }

    // M4：图片直接存入 images 字段，气泡内渲染缩略图，不再追加 [图片×N] 文本
    const userMsg: Message = {
      id: `temp-${Date.now()}`,
      session_id: currentSession.id,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
      status: 'sending',  // M3：发送中
      images: pendingImages.length > 0 ? [...pendingImages] : undefined,
      retry_payload: { text: text, images: [...pendingImages] },
    }
    setMessages((prev) => [...prev, userMsg])
    const tempId = userMsg.id
    setInputValue('')
    setPendingImages([])
    // 重置 ref + state（ref 必须重置，否则下次对话会带上上次残留内容）
    resetStreamingState({
      streamingContentRef,
      streamingSourcesRef,
      streamingToolCallsRef,
      escalatedRef,
      escalateReasonRef,
      streamingFollowUpsRef,
      userMsgSentRef,
      setStreamingContent,
      setStreamingSources,
      setStreamingToolCalls,
    })

    await sendMessage({
      sessionId: currentSession.id,
      message: text,
      enableTools,
      images: pendingImages.length > 0 ? [...pendingImages] : [],
      onEvent: handleSSEEvent,
      // S2004 修复：onError/onComplete 提取到模块级工厂，消除 sendMessage 选项内的多层嵌套
      onError: createSendErrorHandler(tempId, { setMessages }),
      onComplete: createSendCompleteHandler({
        refs: {
          streamingContentRef,
          streamingSourcesRef,
          streamingToolCallsRef,
          escalatedRef,
          escalateReasonRef,
          streamingFollowUpsRef,
          userMsgSentRef,
        },
        setMessages,
        setStreamingContent,
        setStreamingSources,
        setStreamingToolCalls,
        sessionId: currentSession.id,
        // 刷新会话列表（更新最后活跃时间）
        onAfterComplete: () => { loadSessions() },
      }),
    })
  }

  // handleSend 每次渲染重建，follow-up-click 事件监听器（空依赖 useEffect）需通过 ref 调用最新版本
  handleSendRef.current = handleSend

  // 后续问题点击事件监听：点击推荐问题 Tag 后自动发送，绕过 inputValue 状态
  // 为什么用 ref + 空依赖：事件监听器只注册一次，避免每次渲染都 add/removeEventListener
  useEffect(() => {
    const handler = (e: Event) => {
      const question = (e as CustomEvent<string>).detail
      if (!question || typeof question !== 'string') return
      handleSendRef.current(question)
    }
    globalThis.addEventListener('chatbot:follow-up-click', handler)
    return () => globalThis.removeEventListener('chatbot:follow-up-click', handler)
  }, [])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Enter 发送，Shift+Enter 换行
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // S3776 修复：会话列表抽取为 SessionList 组件，主组件只剩调用
  const handleSelectSession = useCallback((session: Session) => {
    setCurrentSession(session)
    setSiderOpen(false)
  }, [])

  const sessionListBody = (
    <SessionList
      sessions={sessions}
      currentSessionId={currentSession?.id}
      loadingSessions={loadingSessions}
      searchKeyword={searchKeyword}
      favoriteOnly={favoriteOnly}
      onSelectSession={handleSelectSession}
      onToggleFavorite={handleToggleFavorite}
      onDeleteSession={handleDeleteSession}
    />
  )

  // S3776 修复：主内容区判断逻辑提取到函数，减少主组件内的分支
  // 无会话时的引导卡点击处理
  const handleOnboardingQuestionNoSession = useCallback(async (q: string) => {
    try {
      const session = await chatbotApi.createSession(q.slice(0, 30))
      setCurrentSession(session)
      pendingFaqRef.current = q
      setTimeout(() => {
        if (pendingFaqRef.current) {
          setInputValue(pendingFaqRef.current)
          pendingFaqRef.current = null
        }
      }, 0)
    } catch {
      message.error('创建会话失败')
    }
  }, [])

  const handleOnboardingDismiss = useCallback(() => {
    setOnboardingDismissed(true)
    try {
      localStorage.setItem('chatbot_onboarding_dismissed', '1')
    } catch {
      // localStorage 不可用时仅内存记忆
    }
  }, [])

  // 计算主内容区：用函数封装判断逻辑，主组件内只剩函数调用
  const mainContentBody = getMainContentBody({
    currentSession,
    onboardingDismissed,
    messages,
    loadingMessages,
    isStreaming,
    streamingContent,
    streamingSources,
    streamingToolCalls,
    messagesEndRef,
    onQuestionClickNoSession: handleOnboardingQuestionNoSession,
    onQuestionClickWithSession: setInputValue,
    onDismiss: handleOnboardingDismiss,
  })

  return (
    <Layout className="cb-root">
      <Sider
        width={260}
        theme="light"
        className={`cb-sider ${siderOpen ? 'cb-sider-open' : ''}`}
      >
        <div className="cb-sider-inner">
          <Button
            icon={<PlusOutlined />}
            block
            onClick={handleCreateSession}
            className="cb-new-btn"
          >
            新建会话
          </Button>
          {/* M2：搜索框 + 收藏过滤 */}
          <div className="cb-search-bar">
            <Input
              allowClear
              placeholder="搜索会话标题或内容"
              prefix={<SearchOutlined style={{ color: 'var(--cb-text-tertiary)' }} />}
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              className="cb-search-input"
            />
            <Button
              type={favoriteOnly ? 'primary' : 'text'}
              size="small"
              icon={favoriteOnly ? <StarFilled /> : <StarOutlined />}
              onClick={() => setFavoriteOnly((prev) => !prev)}
              className={`cb-fav-filter-btn ${favoriteOnly ? 'cb-fav-filter-active' : ''}`}
              title={favoriteOnly ? '显示全部会话' : '仅看收藏'}
            />
            </div>
            {/* 搜索历史小药丸：点击复用历史关键词，避免重复输入 */}
            {sessionHistory.length > 0 && (
              <div className="cb-search-history" style={{ padding: '4px 8px', display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
                {sessionHistory.map((kw) => (
                  <Tag
                    key={kw}
                    onClick={() => setSearchKeyword(kw)}
                    style={{ cursor: 'pointer', margin: 0, fontSize: 11 }}
                  >
                    {kw}
                  </Tag>
                ))}
                <Button type="link" size="small" onClick={clearSessionHistory} style={{ padding: 0, fontSize: 11 }}>
                  清空
                </Button>
              </div>
            )}
            {/* M5：帮助中心 + 立即转人工 */}
            <div className="cb-quick-actions">
              <Button
                block
                size="small"
                icon={<QuestionCircleOutlined />}
                onClick={() => setHelpOpen(true)}
                className="cb-action-btn"
              >
                帮助中心
              </Button>
              <Button
                block
                size="small"
                icon={<CustomerServiceOutlined />}
                onClick={handleEscalate}
                loading={escalating}
                className="cb-action-btn cb-action-btn-escalate"
              >
                立即转人工
              </Button>
            </div>
            {sessionListBody}
        </div>
      </Sider>

      {/* 移动端抽屉遮罩：仅 siderOpen 时渲染，桌面端 display:none 不显示 */}
      {siderOpen && (
        <button
          type="button"
          className="cb-sider-mask"
          // 原生 button 默认支持 Enter/Space 触发 click，无需 onKeyDown/role/tabIndex
          // 重置 border 与 padding 以保留 cb-sider-mask 的全屏遮罩样式
          style={{ border: 'none', padding: 0 }}
          onClick={() => setSiderOpen(false)}
          aria-label="关闭会话列表"
        />
      )}

      <Content className="cb-content">
        {/* 移动端顶部工具条：桌面端 display:none 不显示，仅 ≤768px 可见 */}
        <div className="cb-mobile-bar">
          <Button
            type="text"
            icon={<MenuOutlined />}
            onClick={() => setSiderOpen(true)}
            className="cb-mobile-toggle"
            aria-label="打开会话列表"
          />
          <span className="cb-mobile-bar-title">
            {currentSession ? (currentSession.title || '新会话') : '智能客服'}
          </span>
        </div>
        {/* S3358/S7735：主内容区已提取为 mainContentBody 变量（见 return 前 if-else） */}
        {mainContentBody}

        {/* S3776 修复：输入区抽取为 ChatInputArea 组件 */}
        {currentSession && (
          <ChatInputArea
            currentSession={currentSession}
            inputValue={inputValue}
            onInputChange={setInputValue}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            onDrop={handleDrop}
            isStreaming={isStreaming}
            quickReplies={quickReplies}
            onQuickReplySelect={setInputValue}
            pendingImages={pendingImages}
            onRemoveImage={(idx) => setPendingImages(createRemoveImageUpdater(idx))}
            onUploadSelect={handleUploadSelect}
            enableTools={enableTools}
            onToggleTools={setEnableTools}
            onSend={handleSend}
            onStop={cancel}
          />
        )}
      </Content>
      {/* M5 帮助中心弹窗 */}
      <HelpCenterModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </Layout>
  )
}

// S3776 修复：ChatbotPage 原 CC=21，拆分多个子组件 + 自定义 Hook 降低复杂度

// 会话状态标签映射：status → 样式类名 + 文案
const SESSION_STATUS_MAP: Record<Session['status'], { readonly className: string; readonly label: string }> = {
  active: { className: 'cb-tag-active', label: '活跃' },
  escalated: { className: 'cb-tag-ended', label: '已转人工' },
  ended: { className: 'cb-tag-ended', label: '已结束' },
}

// 会话列表项组件：单个会话的渲染
function SessionListItem({
  session,
  isActive,
  onSelect,
  onToggleFavorite,
  onDelete,
}: {
  readonly session: Session
  readonly isActive: boolean
  readonly onSelect: () => void
  readonly onToggleFavorite: (currentFav: boolean) => void
  readonly onDelete: () => void
}) {
  const statusInfo = SESSION_STATUS_MAP[session.status]
  return (
    <List.Item
      className={`cb-session-item ${isActive ? 'cb-session-item-active' : ''}`}
      onClick={onSelect}
      actions={[
        <button
          key="fav"
          type="button"
          className={`cb-fav-icon ${session.is_favorite ? 'cb-fav-icon-active' : ''}`}
          style={{ background: 'transparent', border: 'none', padding: 0 }}
          onClick={(e) => {
            e.stopPropagation()
            onToggleFavorite(!!session.is_favorite)
          }}
          aria-label={session.is_favorite ? '取消收藏' : '收藏'}
        >
          {session.is_favorite ? <StarFilled /> : <StarOutlined />}
        </button>,
        <Popconfirm
          key="delete"
          title="删除会话"
          description="删除后不可恢复，消息与反馈将一并清除"
          onConfirm={onDelete}
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <DeleteOutlined className="cb-delete-icon" onClick={(e) => e.stopPropagation()} />
        </Popconfirm>,
      ]}
    >
      <List.Item.Meta
        title={
          <Typography.Text ellipsis className="cb-session-title">
            {session.is_favorite ? '★ ' : ''}{session.title || '新会话'}
          </Typography.Text>
        }
        description={
          <span className="cb-session-meta">
            <Tag className={statusInfo.className}>
              {statusInfo.label}
            </Tag>
            <span className="cb-session-count">
              {session.message_count} 条
            </span>
          </span>
        }
      />
    </List.Item>
  )
}

// 会话列表组件
function SessionList({
  sessions,
  currentSessionId,
  loadingSessions,
  searchKeyword,
  favoriteOnly,
  onSelectSession,
  onToggleFavorite,
  onDeleteSession,
}: {
  readonly sessions: Session[]
  readonly currentSessionId?: string
  readonly loadingSessions: boolean
  readonly searchKeyword: string
  readonly favoriteOnly: boolean
  readonly onSelectSession: (session: Session) => void
  readonly onToggleFavorite: (id: string, currentFav: boolean) => void
  readonly onDeleteSession: (id: string) => void
}) {
  if (loadingSessions) {
    return <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
  }
  if (sessions.length === 0) {
    return <Empty description={searchKeyword || favoriteOnly ? '无匹配会话' : '暂无会话'} />
  }
  return (
    <div className="cb-session-list">
      <List
        dataSource={sessions}
        renderItem={(session) => (
          <SessionListItem
            key={session.id}
            session={session}
            isActive={currentSessionId === session.id}
            onSelect={() => onSelectSession(session)}
            onToggleFavorite={(currentFav) => onToggleFavorite(session.id, currentFav)}
            onDelete={() => onDeleteSession(session.id)}
          />
        )}
      />
    </div>
  )
}

// 消息列表组件
function MessageList({
  messages,
  currentSession,
  loadingMessages,
  isStreaming,
  streamingContent,
  streamingSources,
  streamingToolCalls,
  messagesEndRef,
}: {
  readonly messages: Message[]
  readonly currentSession: Session
  readonly loadingMessages: boolean
  readonly isStreaming: boolean
  readonly streamingContent: string
  readonly streamingSources: Message['sources']
  readonly streamingToolCalls: Message['tool_calls']
  readonly messagesEndRef: React.RefObject<HTMLDivElement>
}) {
  if (loadingMessages) {
    return (
      <div className="cb-messages">
        <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
      </div>
    )
  }
  return (
    <div className="cb-messages">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} sessionId={currentSession.id} />
      ))}
      {isStreaming && streamingContent && (
        <MessageBubble
          message={{
            id: 'streaming',
            session_id: currentSession.id,
            role: 'assistant',
            content: streamingContent,
            sources: streamingSources,
            tool_calls: streamingToolCalls,
            created_at: new Date().toISOString(),
          }}
          sessionId={currentSession.id}
        />
      )}
      {isStreaming && !streamingContent && (
        <div className="cb-thinking">
          <div className="cb-thinking-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <div style={{ marginTop: 8, fontSize: 13, color: 'var(--cb-text-tertiary)' }}>思考中...</div>
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  )
}

// 主内容区类型定义
type MainContentParams = {
  readonly currentSession: Session | null
  readonly onboardingDismissed: boolean
  readonly messages: Message[]
  readonly loadingMessages: boolean
  readonly isStreaming: boolean
  readonly streamingContent: string
  readonly streamingSources: Message['sources']
  readonly streamingToolCalls: Message['tool_calls']
  readonly messagesEndRef: React.RefObject<HTMLDivElement>
  readonly onQuestionClickNoSession: (q: string) => Promise<void>
  readonly onQuestionClickWithSession: (q: string) => void
  readonly onDismiss: () => void
}

// 主内容区渲染函数：从主组件抽出，降低主组件复杂度
function getMainContentBody(params: MainContentParams): React.ReactNode {
  const {
    currentSession,
    onboardingDismissed,
    messages,
    loadingMessages,
    isStreaming,
    streamingContent,
    streamingSources,
    streamingToolCalls,
    messagesEndRef,
    onQuestionClickNoSession,
    onQuestionClickWithSession,
    onDismiss,
  } = params

  if (!currentSession) {
    return (
      <ChatbotOnboarding
        onQuestionClick={onQuestionClickNoSession}
        onDismiss={onDismiss}
      />
    )
  }

  if (onboardingDismissed) {
    return (
      <div className="cb-empty">
        <EmptyIllustration />
        <span className="cb-empty-text">开始输入您的问题吧~</span>
      </div>
    )
  }

  if (messages.length === 0 && !loadingMessages) {
    return (
      <ChatbotOnboarding
        onQuestionClick={onQuestionClickWithSession}
        onDismiss={onDismiss}
      />
    )
  }

  return (
    <MessageList
      messages={messages}
      currentSession={currentSession}
      loadingMessages={loadingMessages}
      isStreaming={isStreaming}
      streamingContent={streamingContent}
      streamingSources={streamingSources}
      streamingToolCalls={streamingToolCalls}
      messagesEndRef={messagesEndRef}
    />
  )
}

// 输入区组件
function ChatInputArea({
  currentSession,
  inputValue,
  onInputChange,
  onKeyDown,
  onPaste,
  onDrop,
  isStreaming,
  quickReplies,
  onQuickReplySelect,
  pendingImages,
  onRemoveImage,
  onUploadSelect,
  enableTools,
  onToggleTools,
  onSend,
  onStop,
}: {
  readonly currentSession: Session
  readonly inputValue: string
  readonly onInputChange: (value: string) => void
  readonly onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void
  readonly onPaste: (e: React.ClipboardEvent) => void
  readonly onDrop: (e: React.DragEvent) => void
  readonly isStreaming: boolean
  readonly quickReplies: FAQ[]
  readonly onQuickReplySelect: (q: string) => void
  readonly pendingImages: string[]
  readonly onRemoveImage: (idx: number) => void
  readonly onUploadSelect: (file: File) => boolean
  readonly enableTools: boolean
  readonly onToggleTools: (checked: boolean) => void
  readonly onSend: () => void
  readonly onStop: () => void
}) {
  const isEscalated = currentSession.status === 'escalated'
  const placeholder = isEscalated
    ? '当前会话已转人工，请创建新会话继续咨询'
    : '输入消息，Enter 发送，Shift+Enter 换行，可粘贴/拖拽图片'

  return (
    <div /* NOSONAR - 拖放容器非交互元素 */
      className="cb-input-area"
      onDrop={onDrop}
      onDragOver={(e) => e.preventDefault()}
      // S6845/S6847：移除 tabIndex/onKeyDown/role，拖放事件保留在 div 上
      // 键盘上传由内部 Upload 按钮承担，无需让容器本身可聚焦
      aria-label="消息输入区，可拖拽图片到此处上传"
    >
      {!isStreaming && quickReplies.length > 0 && (
        <QuickReplyChips
          quickReplies={quickReplies}
          onSelect={onQuickReplySelect}
        />
      )}
      {pendingImages.length > 0 && (
        <div className="cb-image-preview-row">
          {pendingImages.map((img, idx) => (
            <div key={img} className="cb-image-thumb">
              <img src={img} alt={`图片${idx + 1}`} />
              <button
                type="button"
                className="cb-image-remove"
                onClick={() => onRemoveImage(idx)}
                aria-label={`删除图片${idx + 1}`}
              >
                <CloseCircleFilled />
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="cb-input-row">
        <Upload
          beforeUpload={onUploadSelect}
          showUploadList={false}
          accept="image/*"
          disabled={isStreaming || pendingImages.length >= 4}
        >
          <Button
            type="text"
            icon={<PictureOutlined />}
            disabled={isStreaming || pendingImages.length >= 4}
            className="cb-upload-btn"
            title={pendingImages.length >= 4 ? '最多 4 张' : '上传图片'}
          />
        </Upload>
        <TextArea
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          placeholder={placeholder}
          autoSize={{ minRows: 2, maxRows: 6 }}
          className="cb-textarea"
          maxLength={2000}
          disabled={isStreaming || isEscalated}
        />
        {isStreaming ? (
          <Button icon={<StopOutlined />} onClick={onStop} className="cb-stop-btn">
            停止
          </Button>
        ) : (
          <Button
            onClick={onSend}
            disabled={!inputValue.trim()}
            className="cb-send-btn"
          >
            发送
          </Button>
        )}
      </div>
      <label className="cb-tools-label">
        <input
          type="checkbox"
          checked={enableTools}
          onChange={(e) => onToggleTools(e.target.checked)}
        />
        {' '}启用工具调用（查询任务/评估/配置等实时数据）
      </label>
    </div>
  )
}

// 消息气泡：区分用户/助手样式，极简商务深浅气泡 + 方正头像
function MessageBubble({ message: msg, sessionId }: { readonly message: Message; readonly sessionId: string }) {
  const isUser = msg.role === 'user'
  // M3 重试：失败时点击重发（仅用户消息 + 有 retry_payload）
  const handleRetry = () => {
    if (!msg.retry_payload) return
    // 用自定义事件通知 handleSend 重新执行（避免在 MessageBubble 里复制 sendMessage 逻辑）
    globalThis.dispatchEvent(
      new CustomEvent('chatbot:retry-send', {
        detail: msg.retry_payload,
      }),
    )
  }
  // M4 撤回：派发事件由父组件处理 API 调用 + state 更新
  const handleRecall = () => {
    globalThis.dispatchEvent(
      new CustomEvent('chatbot:recall-message', { detail: { id: msg.id } }),
    )
  }
  // M4 撤回按钮可见条件：用户消息 + 已保存到 DB（非 temp-）+ 2 分钟内 + 未撤回
  const canRecall =
    isUser &&
    !msg.id.startsWith('temp-') &&
    !msg.is_recalled &&
    Date.now() - new Date(msg.created_at).getTime() < 120000
  // M4 已撤回：渲染灰色占位
  if (msg.is_recalled) {
    return (
      <div className={`cb-msg-row ${isUser ? 'cb-msg-row-user' : ''}`}>
        <div className={`cb-avatar ${isUser ? 'cb-avatar-user' : 'cb-avatar-bot'}`}>
          {isUser ? <UserOutlined /> : <BotAvatar />}
        </div>
        <div className="cb-bubble cb-bubble-recalled">
          <span className="cb-recalled-text">消息已撤回</span>
        </div>
      </div>
    )
  }
  return (
    <div className={`cb-msg-row ${isUser ? 'cb-msg-row-user' : ''}`}>
      <div className={`cb-avatar ${isUser ? 'cb-avatar-user' : 'cb-avatar-bot'}`}>
        {isUser ? <UserOutlined /> : <BotAvatar />}
      </div>
      <div className={`cb-bubble ${isUser ? 'cb-bubble-user' : 'cb-bubble-bot'}`}>
        {isUser ? (
          <>
            {/* M4 图文混排：先渲染图片缩略图，再渲染文本 */}
            {/* msg.images?.length 让 TypeScript 收窄失败（属性别名收窄限制），
                改用 alias 变量：外层 if 已确保非空，imgs 自动收窄为 string[] */}
            {msg.images && msg.images.length > 0 && renderMessageImages(msg.images, globalThis)}
            <Typography.Paragraph className="cb-bubble-text">
              {msg.content}
            </Typography.Paragraph>
            {/* M3 状态 + M4 撤回按钮 */}
            <div className="cb-msg-status">
              {msg.status === 'sending' && (
                <span className="cb-msg-status-sending">
                  <Spin size="small" />{' '}发送中...
                </span>
              )}
              {msg.status === 'sent' && (
                <span className="cb-msg-status-sent">已送达 ✓</span>
              )}
              {msg.status === 'failed' && (
                <Button
                  size="small"
                  type="link"
                  danger
                  icon={<SyncOutlined />}
                  onClick={handleRetry}
                  className="cb-msg-retry-btn"
                >
                  发送失败 · 重试
                </Button>
              )}
              {/* M4：已送达消息显示撤回按钮（2 分钟内） */}
              {canRecall && !msg.status && (
                <Button
                  size="small"
                  type="link"
                  onClick={handleRecall}
                  className="cb-msg-recall-btn"
                >
                  撤回
                </Button>
              )}
            </div>
          </>
        ) : (
          <AssistantMessage message={msg} sessionId={sessionId} />
        )}
      </div>
    </div>
  )
}
