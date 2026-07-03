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

// 可爱卡通机器人头像 SVG：圆润造型 + 马卡龙配色，契合治愈系 UI
function BotAvatar() {
  return (
    <svg viewBox="0 0 40 40" width="22" height="22" fill="none">
      {/* 头部圆角矩形 */}
      <rect x="8" y="6" width="24" height="20" rx="8" fill="#fff" opacity="0.95" />
      {/* 天线 */}
      <circle cx="20" cy="4" r="2" fill="#fff" />
      <line x1="20" y1="6" x2="20" y2="4" stroke="#fff" strokeWidth="1.5" />
      {/* 左眼 */}
      <circle cx="15" cy="15" r="2.5" fill="#6ECDB4" />
      {/* 右眼 */}
      <circle cx="25" cy="15" r="2.5" fill="#6ECDB4" />
      {/* 腮红 */}
      <ellipse cx="12" cy="20" rx="2" ry="1.5" fill="#FFB3CC" opacity="0.7" />
      <ellipse cx="28" cy="20" rx="2" ry="1.5" fill="#FFB3CC" opacity="0.7" />
      {/* 嘴巴微笑 */}
      <path d="M17 20 Q20 22 23 20" stroke="#6ECDB4" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      {/* 身体小圆角 */}
      <rect x="12" y="26" width="16" height="8" rx="4" fill="#fff" opacity="0.8" />
    </svg>
  )
}

// 空状态插画：机器人打招呼
function EmptyIllustration() {
  return (
    <svg viewBox="0 0 120 120" width="120" height="120" fill="none">
      {/* 背景圆 */}
      <circle cx="60" cy="60" r="50" fill="#FFD6E8" opacity="0.3" />
      <circle cx="60" cy="60" r="40" fill="#C8F1E2" opacity="0.35" />
      {/* 机器人头部 */}
      <rect x="35" y="30" width="50" height="42" rx="16" fill="#fff" />
      {/* 天线 */}
      <circle cx="60" cy="22" r="4" fill="#FF8FAB" />
      <line x1="60" y1="30" x2="60" y2="26" stroke="#FFB3CC" strokeWidth="2" />
      {/* 眼睛 */}
      <circle cx="48" cy="48" r="5" fill="#6ECDB4" />
      <circle cx="72" cy="48" r="5" fill="#6ECDB4" />
      <circle cx="48" cy="47" r="1.5" fill="#fff" />
      <circle cx="72" cy="47" r="1.5" fill="#fff" />
      {/* 腮红 */}
      <ellipse cx="42" cy="58" rx="4" ry="3" fill="#FFB3CC" opacity="0.6" />
      <ellipse cx="78" cy="58" rx="4" ry="3" fill="#FFB3CC" opacity="0.6" />
      {/* 微笑 */}
      <path d="M50 60 Q60 68 70 60" stroke="#6ECDB4" strokeWidth="2.5" strokeLinecap="round" fill="none" />
      {/* 身体 */}
      <rect x="42" y="72" width="36" height="20" rx="10" fill="#A8E6CF" opacity="0.8" />
      {/* 小手臂 */}
      <circle cx="35" cy="78" r="5" fill="#FFB3CC" opacity="0.7" />
      <circle cx="85" cy="78" r="5" fill="#FFB3CC" opacity="0.7" />
      {/* 装饰小星星 */}
      <text x="20" y="40" fontSize="14" fill="#FF8FAB" opacity="0.5">✦</text>
      <text x="95" y="75" fontSize="12" fill="#6ECDB4" opacity="0.5">✦</text>
      <text x="90" y="35" fontSize="10" fill="#FFB3CC" opacity="0.4">●</text>
    </svg>
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
  const addImageFiles = useCallback(async (files: FileList | File[]) => {
    const maxImages = 4
    const maxSize = 5 * 1024 * 1024 // 5MB
    const arr = Array.from(files).filter((f) => f.type.startsWith('image/'))
    if (arr.length === 0) return
    // 用 ref-like 闭包变量跟踪是否已警告，避免重复提示
    let warnedLimit = false
    for (const f of arr) {
      if (f.size > maxSize) {
        message.warning(`${f.name} 超过 5MB，已跳过`)
        continue
      }
      try {
        const url = await fileToDataUrl(f)
        let added = false
        setPendingImages((p) => {
          if (p.length >= maxImages) return p
          added = true
          return [...p, url]
        })
        if (!added && !warnedLimit) {
          warnedLimit = true
          message.warning(`最多 ${maxImages} 张图片`)
        }
      } catch {
        // 单个文件转 base64 失败时忽略，不影响其他文件
      }
    }
  }, [])

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
      setMessages((prev) => prev.filter((m) => m.status !== 'failed'))
    }
    globalThis.addEventListener('chatbot:retry-send', handler)
    return () => globalThis.removeEventListener('chatbot:retry-send', handler)
  }, [])

  // M4 消息撤回：监听 MessageBubble 派发的 recall 事件
  useEffect(() => {
    // handler 用同步包装：addEventListener 期望 (e: Event) => void，
    // 直接用 async 函数会返回 Promise，类型不匹配且未捕获的 rejection 无法处理
    const handler = (e: Event) => {
      void (async () => {
        const detail = (e as CustomEvent<{ id: string }>).detail
        if (!detail) return
        try {
          await chatbotApi.recallMessage(detail.id)
          // 乐观更新：立即把消息标记为已撤回
          setMessages((prev) =>
            prev.map((m) =>
              m.id === detail.id ? { ...m, is_recalled: 1 } : m,
            ),
          )
          message.success('已撤回')
        } catch {
          message.error('撤回失败，可能已超过 2 分钟时限')
        }
      })()
    }
    globalThis.addEventListener('chatbot:recall-message', handler)
    return () => globalThis.removeEventListener('chatbot:recall-message', handler)
  }, [])

  // M5：主动转人工——确认后调用 escalation/trigger
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
      onOk: async () => {
        setEscalating(true)
        try {
          await chatbotApi.triggerEscalation(targetSessionId)
          setSessions((prev) =>
            prev.map((s) =>
              s.id === targetSessionId ? { ...s, status: 'escalated' } : s,
            ),
          )
          // 函数式更新：仅当用户仍停留在原会话时才更新当前会话状态
          setCurrentSession((prev) =>
            prev?.id === targetSessionId ? { ...prev, status: 'escalated' } : prev,
          )
          message.success('已转接人工客服')
        } catch {
          message.error('转接失败，请稍后重试')
        } finally {
          setEscalating(false)
        }
      },
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

  // SSE 事件处理：根据事件类型更新流式消息
  // 同步写入 ref + state：ref 供 onComplete 读取最新值，state 触发渲染
  const handleSSEEvent = useCallback(
    (event: SSEEvent) => {
      switch (event.type) {
        case 'token':
          // 字段名 content：与后端 orchestrator.py L290 data={"content": token} 对齐
          streamingContentRef.current += (event.data.content as string || '')
          setStreamingContent(streamingContentRef.current)
          // M3：首 token 到达 → 用户消息已送达（sent）
          // 用 ref 标记"已发送"避免重复 setState
          if (!userMsgSentRef.current) {
            userMsgSentRef.current = true
            setMessages((prev) =>
              prev.map((m) =>
                m.role === 'user' && m.status === 'sending'
                  ? { ...m, status: 'sent' }
                  : m,
              ),
            )
          }
          break
        case 'sources':
          streamingSourcesRef.current = event.data.sources as Message['sources']
          setStreamingSources(streamingSourcesRef.current)
          break
        case 'tool_call':
          // tool_call 事件的 data 是单个工具调用结果，直接追加到列表
          // event.data 来自后端 TOOL_CALL 事件，结构对齐 ToolCall 接口
          streamingToolCallsRef.current = [
            ...(streamingToolCallsRef.current || []),
            event.data as unknown as ToolCall,
          ]
          setStreamingToolCalls(streamingToolCallsRef.current)
          break
        case 'error':
          // H-2：按 code 分支显示友好提示，而非统一"生成失败"
          // 后端 code 见 orchestrator.py：SECURITY_VIOLATION / OUT_OF_SCOPE / 其他
          {
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
          break
        case 'escalate':
          // H-3：转人工事件——将话术写入流式内容，标记 escalated
          // escalate 是终止事件，触发后 onComplete 会固化这条消息
          {
            const escalateMsg = event.data.message as string
            const reason = event.data.reason as string
            if (escalateMsg) {
              streamingContentRef.current = escalateMsg
              setStreamingContent(escalateMsg)
            }
            escalatedRef.current = true
            escalateReasonRef.current = reason || ''
          }
          break
        case 'done':
          // DONE 事件携带 follow_ups：存入 ref 供 onComplete 读取
          // done 是终止事件，useSSEChat 在 onEvent 后立即调 onComplete
          streamingFollowUpsRef.current = (event.data.follow_ups as string[]) || []
          break
      }
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
    const sentText = text
    const sentImages = pendingImages
    const tempId = userMsg.id
    setInputValue('')
    setPendingImages([])
    // 重置 ref + state（ref 必须重置，否则下次对话会带上上次残留内容）
    streamingContentRef.current = ''
    streamingSourcesRef.current = []
    streamingToolCallsRef.current = []
    escalatedRef.current = false
    escalateReasonRef.current = ''
    streamingFollowUpsRef.current = []
    userMsgSentRef.current = false
    setStreamingContent('')
    setStreamingSources([])
    setStreamingToolCalls([])

    await sendMessage({
      sessionId: currentSession.id,
      message: sentText,
      enableTools,
      images: sentImages,
      onEvent: handleSSEEvent,
      onError: (err) => {
        // M3：失败时把临时消息标 failed，UI 显示重试按钮
        setMessages((prev) =>
          prev.map((m) => (m.id === tempId ? { ...m, status: 'failed' } : m)),
        )
        message.error('对话失败: ' + err.message)
      },
      onComplete: () => {
        // 终止事件（done/error/escalate）触发后，确保用户消息从 sending → sent
        // escalate 事件不发 token，userMsgSentRef 不会被设置，需在此兜底
        if (!userMsgSentRef.current) {
          userMsgSentRef.current = true
          setMessages((prev) =>
            prev.map((m) =>
              m.role === 'user' && m.status === 'sending'
                ? { ...m, status: 'sent' }
                : m,
            ),
          )
        }
        // 读 ref.current 而非闭包 state（B-1 修复：避免读到发送时刻的空快照）
        const content = streamingContentRef.current
        const sources = streamingSourcesRef.current
        const toolCalls = streamingToolCallsRef.current
        const escalated = escalatedRef.current
        const escalateReason = escalateReasonRef.current
        const followUps = streamingFollowUpsRef.current
        // escalate 事件无 content 时也要固化（转人工话术可能为空）
        // follow_ups 也需纳入判断：主回答为空但生成了推荐问题时不能丢弃
        if (content || sources?.length || toolCalls?.length || escalated || followUps.length > 0) {
          const assistantMsg: Message = {
            id: `assistant-${Date.now()}`,
            session_id: currentSession.id,
            role: 'assistant',
            content: content || '(空回复)',
            sources: sources,
            tool_calls: toolCalls,
            escalated: escalated || undefined,
            escalate_reason: escalateReason || undefined,
            follow_ups: followUps.length > 0 ? followUps : undefined,
            created_at: new Date().toISOString(),
          }
          setMessages((prev) => [...prev, assistantMsg])
        }
        // 重置 ref + state
        streamingContentRef.current = ''
        streamingSourcesRef.current = []
        streamingToolCallsRef.current = []
        escalatedRef.current = false
        escalateReasonRef.current = ''
        streamingFollowUpsRef.current = []
        setStreamingContent('')
        setStreamingSources([])
        setStreamingToolCalls([])
        // 刷新会话列表（更新最后活跃时间）
        loadSessions()
      },
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

  // S3358：会话列表嵌套三元提取为变量，用 if-else 替代 loadingSessions ? <Spin> : sessions.length === 0 ? <Empty> : <List>
  const sessionListView = (
    <div className="cb-session-list">
      <List
        dataSource={sessions}
        renderItem={(session) => {
          // S3358：用映射表替代嵌套三元，避免 status === 'active' ? '活跃' : status === 'escalated' ? '已转人工' : '已结束'
          const statusClass = session.status === 'active' ? 'cb-tag-active' : 'cb-tag-ended'
          const statusLabels: Record<Session['status'], string> = {
            active: '活跃',
            escalated: '已转人工',
            ended: '已结束',
          }
          const statusLabel = statusLabels[session.status]
          return (
          <List.Item
            className={`cb-session-item ${currentSession?.id === session.id ? 'cb-session-item-active' : ''}`}
            onClick={() => {
              setCurrentSession(session)
              // 选中会话后自动关闭移动端抽屉，桌面端无副作用
              setSiderOpen(false)
            }}
            actions={[
              <span
                key="fav"
                className={`cb-fav-icon ${session.is_favorite ? 'cb-fav-icon-active' : ''}`}
                onClick={(e) => {
                  e.stopPropagation()
                  handleToggleFavorite(session.id, !!session.is_favorite)
                }}
                role="button"
                tabIndex={0}
                aria-label={session.is_favorite ? '取消收藏' : '收藏'}
                onKeyDown={(e) => {
                  // S6819：补全 Space 触发，使 role="button" 键盘交互符合 WAI-ARIA
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    e.stopPropagation()
                    handleToggleFavorite(session.id, !!session.is_favorite)
                  }
                }}
              >
                {session.is_favorite ? <StarFilled /> : <StarOutlined />}
              </span>,
              <Popconfirm
                key="delete"
                title="删除会话"
                description="删除后不可恢复，消息与反馈将一并清除"
                onConfirm={() => handleDeleteSession(session.id)}
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
                  <Tag className={statusClass}>
                    {statusLabel}
                  </Tag>
                  <span className="cb-session-count">
                    {session.message_count} 条
                  </span>
                </span>
              }
            />
          </List.Item>
          )
        }}
      />
    </div>
  )
  let sessionListBody: React.ReactNode
  if (loadingSessions) {
    sessionListBody = <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
  } else if (sessions.length === 0) {
    sessionListBody = <Empty description={searchKeyword || favoriteOnly ? '无匹配会话' : '暂无会话'} />
  } else {
    sessionListBody = sessionListView
  }

  // S3358/S7735：主内容区多层嵌套三元提取为变量，用 if-else 消除冗余条件与死代码
  // 原 L869 的 !onboardingDismissed 在 else 分支中冗余（else 已隐含 !onboardingDismissed）
  // 原 L882 的 messages.length === 0 && !loadingMessages 是死代码（被上一分支拦截），删除
  let mainContentBody: React.ReactNode
  if (!currentSession) {
    // 无会话：显示引导卡（M1）
    mainContentBody = (
      <ChatbotOnboarding
        onQuestionClick={async (q) => {
          // 先创建会话，再触发 handleSend
          try {
            const session = await chatbotApi.createSession(q.slice(0, 30))
            setCurrentSession(session)
            // 用 ref 暂存待发送内容，等 messages 加载完成后再发
            pendingFaqRef.current = q
            // 让父级进入 messages 渲染分支后再发送
            setTimeout(() => {
              if (pendingFaqRef.current) {
                setInputValue(pendingFaqRef.current)
                pendingFaqRef.current = null
              }
            }, 0)
          } catch {
            message.error('创建会话失败')
          }
        }}
        onDismiss={() => {
          setOnboardingDismissed(true)
          try {
            localStorage.setItem('chatbot_onboarding_dismissed', '1')
          } catch {
            // localStorage 不可用时仅内存记忆
          }
        }}
      />
    )
  } else if (onboardingDismissed) {
    // 已关闭引导卡：显示空状态
    mainContentBody = (
      <div className="cb-empty">
        <EmptyIllustration />
        <span className="cb-empty-text">开始输入您的问题吧~</span>
      </div>
    )
  } else if (messages.length === 0 && !loadingMessages) {
    // 新会话空消息：显示引导卡（M1）
    mainContentBody = (
      <ChatbotOnboarding
        onQuestionClick={(q) => setInputValue(q)}
        onDismiss={() => {
          setOnboardingDismissed(true)
          try {
            localStorage.setItem('chatbot_onboarding_dismissed', '1')
          } catch {
            // 静默忽略
          }
        }}
      />
    )
  } else {
    // 有消息或正在加载：显示消息列表
    mainContentBody = (
      <div className="cb-messages">
        {loadingMessages ? (
          <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} sessionId={currentSession.id} />
            ))}
            {/* 流式响应中的临时消息 */}
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
          </>
        )}
      </div>
    )
  }

  return (
    <Layout className="cb-root">
      <Sider
        width={280}
        theme="light"
        className={`cb-sider ${siderOpen ? 'cb-sider-open' : ''}`}
      >
        <div className="cb-sider-inner">
          <Button
            type="primary"
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
        <div
          className="cb-sider-mask"
          onClick={() => setSiderOpen(false)}
          // S1082/S6847/S6848：遮罩可点击须可被键盘操作，aria-hidden 与 onClick 冲突故移除
          role="button"
          tabIndex={0}
          aria-label="关闭会话列表"
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              setSiderOpen(false)
            }
          }}
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

        {/* 输入区：当前会话存在时显示，与消息区/引导卡互斥 */}
        {currentSession && (
          <div
            className="cb-input-area"
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
          >
            {/* M3 快捷回复：仅在非流式且有数据时显示 */}
            {!isStreaming && quickReplies.length > 0 && (
              <QuickReplyChips
                quickReplies={quickReplies}
                onSelect={(q) => setInputValue(q)}
              />
            )}
            {/* 图片预览缩略图 */}
            {pendingImages.length > 0 && (
              <div className="cb-image-preview-row">
                {pendingImages.map((img, idx) => (
                  // S6479：data URL 作为稳定 key，避免数组索引在增删时错位
                  <div key={img} className="cb-image-thumb">
                    <img src={img} alt={`图片${idx + 1}`} />
                    <CloseCircleFilled
                      className="cb-image-remove"
                      onClick={() =>
                        setPendingImages((prev) => prev.filter((_, i) => i !== idx))
                      }
                      // S1082/S6847/S6848：图标可点击需补全键盘可达性
                      role="button"
                      tabIndex={0}
                      aria-label={`删除图片${idx + 1}`}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          setPendingImages((prev) => prev.filter((_, i) => i !== idx))
                        }
                      }}
                    />
                  </div>
                ))}
              </div>
            )}
            <div className="cb-input-row">
              <Upload
                beforeUpload={handleUploadSelect}
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
                  ref={inputRef as React.Ref<any>}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onPaste={handlePaste}
                  placeholder={
                    currentSession?.status === 'escalated'
                      ? '当前会话已转人工，请创建新会话继续咨询'
                      : '输入消息，Enter 发送，Shift+Enter 换行，可粘贴/拖拽图片'
                  }
                  autoSize={{ minRows: 2, maxRows: 6 }}
                  className="cb-textarea"
                  maxLength={2000}
                  disabled={isStreaming || currentSession?.status === 'escalated'}
                />
                {isStreaming ? (
                  <Button icon={<StopOutlined />} onClick={cancel} className="cb-stop-btn">
                    停止
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    onClick={() => handleSend()}
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
                  onChange={(e) => setEnableTools(e.target.checked)}
                />
                {/* S6772：显式空格避免 JSX 折叠后 input 与文本无间隙 */}
                {' '}启用工具调用（查询任务/评估/配置等实时数据）
              </label>
            </div>
        )}
      </Content>
      {/* M5 帮助中心弹窗 */}
      <HelpCenterModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </Layout>
  )
}

// 消息气泡：区分用户/助手样式，马卡龙渐变气泡 + 圆润头像
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
            {/* 可选链替代 msg.images && msg.images.length：S6582 */}
            {msg.images?.length > 0 && (
              <div className="cb-msg-images">
                {msg.images.map((img, idx) => (
                  <img
                    // S6479：图片 URL 作为稳定 key
                    key={img}
                    src={img}
                    alt={`图片${idx + 1}`}
                    className="cb-msg-image-thumb"
                    onClick={() => window.open(img, '_blank')}
                    // S1082/S6847/S6848：图片可点击需补全键盘可达性
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        window.open(img, '_blank')
                      }
                    }}
                  />
                ))}
              </div>
            )}
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
