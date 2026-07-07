import { useState, useCallback } from 'react'
import { message } from 'antd'
import { evalApi, type EvalItem, type OfficialCollectResult } from '../../../api'

const RETRYABLE_STATUSES = new Set([410, 441, 502])
const RETRY_DELAYS: Record<string, number> = {
  '410': 1000,
  '441': 3000,
  '502': 1000,
  'timeout': 2000,
}

interface AxiosLikeError {
  response?: { status?: number; data?: { detail?: string } }
  code?: string
  message?: string
}

const isAxiosTimeout = (error: AxiosLikeError): boolean =>
  error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')

const COLLECT_OFFICIAL_ERROR_MESSAGES: Record<number, string> = {
  503: '官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动',
  403: '闲鱼登录已过期，请重新登录闲鱼',
  440: '闲鱼登录已过期，请重新登录闲鱼',
  441: '触发闲鱼反爬限制，请稍后重试或手动完成验证',
  410: '商品详情页加载失败或已下架，请稍后重试',
  502: '浏览器连接异常，请重启服务后重试',
}
const COLLECT_OFFICIAL_TIMEOUT_MESSAGE = '官方采集超时（详情页+卖家主页加载缓慢），请稍后重试或检查网络'
const COLLECT_OFFICIAL_FALLBACK_MESSAGE = '官方采集失败，请稍后重试'

async function collectOfficialWithRetry(itemId: string, taskId?: string): Promise<OfficialCollectResult> {
  const MAX_RETRIES = 1
  let lastErr: unknown
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await evalApi.collectOfficial(itemId, taskId)
    } catch (err: unknown) {
      lastErr = err
      if (attempt >= MAX_RETRIES) break
      const e = err as { response?: { status?: number }; code?: string; message?: string }
      const status = e?.response?.status
      const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(e?.message || '')
      const retryable = isTimeout || (status !== undefined && RETRYABLE_STATUSES.has(status))
      if (!retryable) break
      const delayKey = isTimeout ? 'timeout' : String(status)
      const delay = RETRY_DELAYS[delayKey] ?? 2000
      await new Promise(resolve => setTimeout(resolve, delay))
    }
  }
  throw lastErr
}

function showStatusError(
  err: unknown,
  statusMessages: Record<number, string>,
  timeoutMessage: string,
  fallbackMessage: string,
): void {
  const error = err as AxiosLikeError
  const status = error?.response?.status
  const detail = error?.response?.data?.detail
  if (isAxiosTimeout(error)) {
    message.error(timeoutMessage)
  } else if (status != null && statusMessages[status]) {
    // 已知状态码优先用前端中文消息，后端 detail 仅作为 fallback
    // 为什么不用 detail 优先：后端返回英文技术消息，对中文用户不友好
    message.error(statusMessages[status])
  } else {
    message.error(detail || fallbackMessage)
  }
}

export interface EvalCollectState {
  collecting: Record<string, boolean>
  collectResult: OfficialCollectResult | null
  collectModalOpen: boolean
  setCollectModalOpen: (v: boolean) => void
  onCollectOfficial: (r: EvalItem) => Promise<void>
}

export function useEvalCollect(
  load: () => void,
): EvalCollectState {
  const [collecting, setCollecting] = useState<Record<string, boolean>>({})
  const [collectResult, setCollectResult] = useState<OfficialCollectResult | null>(null)
  const [collectModalOpen, setCollectModalOpen] = useState(false)

  const onCollectOfficial = useCallback(async (r: EvalItem) => {
    const itemId = r.item_id
    setCollecting((prev) => ({ ...prev, [itemId]: true }))
    try {
      const result = await collectOfficialWithRetry(itemId, r.task_id)
      setCollectResult(result)
      setCollectModalOpen(true)
      message.success(`官方采集评估完成，评分：${result.evaluation.score ?? 'N/A'}`)
      load()
    } catch (err: unknown) {
      showStatusError(
        err,
        COLLECT_OFFICIAL_ERROR_MESSAGES,
        COLLECT_OFFICIAL_TIMEOUT_MESSAGE,
        COLLECT_OFFICIAL_FALLBACK_MESSAGE,
      )
    } finally {
      setCollecting((prev) => ({ ...prev, [itemId]: false }))
    }
  }, [load])

  return {
    collecting,
    collectResult,
    collectModalOpen,
    setCollectModalOpen,
    onCollectOfficial,
  }
}
