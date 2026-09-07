import { useState, useCallback, useRef } from 'react'
import { message } from 'antd'
import type { SSEEvent } from '../types'
import { API_BASE } from '../../../utils/apiBase'

interface UseSSEChatOptions {
  sessionId: string
  onEvent: (event: SSEEvent) => void
  onError: (error: Error) => void
  onComplete: () => void
}

interface SendMessageParams {
  message: string
  enableTools?: boolean
  images?: string[]
  // 模型覆盖：知识库问答界面下拉选择的模型，随请求上送，覆盖服务端默认模型
  model?: string
}

// 构造认证请求头：cookie 为主（withCredentials），Authorization header 为辅（兼容场景）
// 提取为模块级纯函数：原 sendMessage 内联三元 + spread 贡献认知复杂度（S3776）
const buildChatHeaders = (token: string | null): Record<string, string> => ({
  'Content-Type': 'application/json',
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
})

// 构造请求体：将 opts 字段映射为后端 API 字段
// 提取为模块级纯函数：原 sendMessage 内联对象字面量 + 2 个 ?? 运算贡献认知复杂度
const buildChatBody = (opts: UseSSEChatOptions & SendMessageParams) => ({
  session_id: opts.sessionId,
  message: opts.message,
  enable_tools: opts.enableTools ?? true,
  images: opts.images ?? [],
  // model 仅在用户显式选择时上送，留空则服务端用默认模型
  ...(opts.model ? { model: opts.model } : {}),
})

// 终止事件类型集合：done/error/escalate 触发 onComplete 后立即结束流
// 用 Set 查表替代 3 个 || 链，新增终止类型只需加一行（S3776）
const TERMINAL_EVENT_TYPES = new Set<SSEEvent['type']>(['done', 'error', 'escalate'])

// 用户主动取消（AbortController.abort）不算错误，需静默忽略
const isAbortError = (e: unknown): boolean =>
  e instanceof Error && e.name === 'AbortError'

// 错误归一化：将任意异常转为 Error 实例，便于上层统一处理
const normalizeError = (e: unknown): Error =>
  e instanceof Error ? e : new Error(String(e))

// 消费 SSE 流：解析每个事件并回调 onEvent，遇终止事件提前返回 true
// 提取为模块级函数：原 sendMessage 内 while+for+if 嵌套 4 层，SonarQube S3776 认知复杂度超限
// 返回值约定：true=遇到终止事件提前结束（调用方不应再回调 onComplete），false=流正常结束（调用方需补回调）
// 为什么用返回值而非内部直接调 onComplete：避免与 sendMessage 末尾的 onComplete 形成双重调用
async function consumeSSEStream(resp: Response, opts: UseSSEChatOptions): Promise<boolean> {
  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    // SSE 协议：双换行分隔独立事件
    const events = buffer.split('\n\n')
    // 最后一段可能不完整，保留到下次拼接
    buffer = events.pop() || ''

    for (const eventStr of events) {
      const event = parseSSEEvent(eventStr)
      if (event) {
        opts.onEvent(event)
        // done/error/escalate 为终止事件，结束本次流
        if (TERMINAL_EVENT_TYPES.has(event.type)) {
          return true
        }
      }
    }
  }
  return false
}

// SSE 聊天 Hook：用 fetch + ReadableStream 实现
// 为什么不用 EventSource：chat 是 POST 请求，EventSource 仅支持 GET
// 为什么不用 axios：axios 不支持 ReadableStream 流式读取
export function useSSEChat() {
  const [isStreaming, setIsStreaming] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (opts: UseSSEChatOptions & SendMessageParams) => {
      setIsStreaming(true)
      abortControllerRef.current = new AbortController()

      try {
        // 认证：cookie 为主（withCredentials），Authorization header 为辅（兼容）
        const token = localStorage.getItem('xh_token')
        const resp = await fetch(`${API_BASE}api/chatbot/chat`, {
          method: 'POST',
          credentials: 'include',
          headers: buildChatHeaders(token),
          body: JSON.stringify(buildChatBody(opts)),
          signal: abortControllerRef.current.signal,
        })

        if (!resp.ok) {
          // 401：清除失效 token 并跳转登录页
          // 硬约束：401 必须触发重定向，不能静默吞掉
          // 必须用 /xianyu/login：浏览器原生跳转不走 react-router，
          // 不会自动补 basename 前缀，直接用 /login 会被后端返回 404
          if (resp.status === 401) {
            localStorage.removeItem('xh_token')
            globalThis.location.href = '/xianyu/login'
            return
          }
          throw new Error(`HTTP ${resp.status}`)
        }

        // 消费 SSE 流：终止事件由 consumeSSEStream 提前返回，但仍需统一回调 onComplete
        // 为什么不在 consumeSSEStream 内部回调：避免与这里形成双重调用，让 onComplete 调用点单一可追踪
        await consumeSSEStream(resp, opts)
        opts.onComplete()
      } catch (e) {
        // 用户主动取消不算错误
        if (isAbortError(e)) return
        const err = normalizeError(e)
        opts.onError(err)
        message.error('对话失败: ' + err.message)
      } finally {
        setIsStreaming(false)
        abortControllerRef.current = null
      }
    },
    [],
  )

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort()
  }, [])

  return { isStreaming, sendMessage, cancel }
}

// 解析单个 SSE 事件字符串为结构化对象
// SSE 格式：event: xxx\ndata: {...}\n（可能有多行 data，需用 \n 拼接）
function parseSSEEvent(raw: string): SSEEvent | null {
  const lines = raw.split('\n')
  let type = ''
  // SSE 规范：多个 data: 行需用 \n 拼接为单个值
  // 用数组收集再 join，避免 += 拼接丢失换行符
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event: ')) {
      type = line.slice(7).trim()
    } else if (line.startsWith('data: ')) {
      dataLines.push(line.slice(6))
    }
  }
  if (!type) return null
  const data = dataLines.join('\n')
  try {
    return { type: type as SSEEvent['type'], data: JSON.parse(data) }
  } catch {
    // 非 JSON 数据（如纯文本 token），包装为 raw 字段
    return { type: type as SSEEvent['type'], data: { raw: data } }
  }
}
