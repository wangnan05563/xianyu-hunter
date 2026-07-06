import { useState, useCallback } from 'react'
import { message } from 'antd'
import { aiApi, evalApi, orderApi, itemApi, type EvalItem } from '../../../api'

/**
 * 批量操作 Hook
 *
 * 为什么拆出：批量操作有独立的状态（selectedRowKeys, 各种 loading）
 * 和多个批量函数，集中管理便于理解和维护。
 */
export interface EvalBatchState {
  selectedRowKeys: React.Key[]
  setSelectedRowKeys: (keys: React.Key[]) => void
  batchAIEvaluating: boolean
  batchProgress: { done: number; total: number }
  onBatchAIEval: () => Promise<void>

  batchCollecting: boolean
  batchCollectProgress: { done: number; total: number }
  onBatchCollectOfficial: () => Promise<void>

  recomputing: boolean
  onRecompute: () => Promise<void>

  batchEvaluating: boolean
  onBatchEvaluateUnevaluated: () => Promise<void>

  manualTaking: Record<string, boolean>
  onManualTakeover: (r: EvalItem) => Promise<void>

  onTitleClick: (e: React.MouseEvent, r: EvalItem, url: string) => void
}

const MANUAL_TAKEOVER_ERROR_MESSAGES: Record<number, string> = {
  503: '抢单功能未启用：需要以 XH_WITH_SCHEDULER=1 模式启动服务',
  403: '闲鱼登录已过期，请先在「Cookie 注入」页面重新登录闲鱼',
  404: '商品不存在于数据库中',
  502: '抢单失败：未找到提交订单按钮，可能商品已下架或页面结构变化',
}
const MANUAL_TAKEOVER_TIMEOUT_MESSAGE = '抢单超时：浏览器自动化流程耗时过长，请检查网络后重试'
const MANUAL_TAKEOVER_FALLBACK_MESSAGE = '抢单失败，请稍后重试'

interface AxiosLikeError {
  response?: { status?: number; data?: { detail?: string } }
  code?: string
  message?: string
}

const isAxiosTimeout = (error: AxiosLikeError): boolean =>
  error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')

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
    message.error(detail || statusMessages[status])
  } else {
    message.error(detail || fallbackMessage)
  }
}

export function useEvalBatch(
  items: EvalItem[],
  taskId: string,
  load: () => void,
  loadDist: () => void,
): EvalBatchState {
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [batchAIEvaluating, setBatchAIEvaluating] = useState(false)
  const [batchProgress, setBatchProgress] = useState({ done: 0, total: 0 })

  const [batchCollecting, setBatchCollecting] = useState(false)
  const [batchCollectProgress, setBatchCollectProgress] = useState({ done: 0, total: 0 })

  const [recomputing, setRecomputing] = useState(false)
  const [batchEvaluating, setBatchEvaluating] = useState(false)

  const [manualTaking, setManualTaking] = useState<Record<string, boolean>>({})

  const onBatchAIEval = useCallback(async () => {
    const ids = items
      .filter(item => selectedRowKeys.includes(`${item.item_id}-${item.created_at}`))
      .map(item => item.item_id)
    if (ids.length === 0) return

    setBatchAIEvaluating(true)
    setBatchProgress({ done: 0, total: ids.length })

    let done = 0
    for (const id of ids) {
      try {
        await aiApi.evaluateCondition(id)
      } catch {
      }
      done++
      setBatchProgress({ done, total: ids.length })
    }

    setBatchAIEvaluating(false)
    setSelectedRowKeys([])
    message.success(`批量评估完成，共处理 ${ids.length} 项`)
    load()
  }, [items, selectedRowKeys, load])

  const onBatchCollectOfficial = useCallback(async () => {
    const ids = items
      .filter(item => selectedRowKeys.includes(`${item.item_id}-${item.created_at}`))
      .map(item => item.item_id)
    if (ids.length === 0) return

    setBatchCollecting(true)
    setBatchCollectProgress({ done: 0, total: ids.length })

    let done = 0
    let succeeded = 0
    let failed = 0
    for (const id of ids) {
      try {
        await evalApi.collectOfficial(id)
        succeeded++
      } catch {
        failed++
      }
      done++
      setBatchCollectProgress({ done, total: ids.length })
    }

    setBatchCollecting(false)
    setSelectedRowKeys([])
    message.success(`批量官方采集完成：成功 ${succeeded}，失败 ${failed}`)
    load()
  }, [items, selectedRowKeys, load])

  const onRecompute = useCallback(async () => {
    setRecomputing(true)
    try {
      const res = await evalApi.recompute(taskId || undefined)
      message.success(res.message)
      load()
      loadDist()
    } catch {
      message.error('重新评估失败')
    } finally {
      setRecomputing(false)
    }
  }, [taskId, load, loadDist])

  const onBatchEvaluateUnevaluated = useCallback(async () => {
    setBatchEvaluating(true)
    try {
      const res = await evalApi.batchEvaluateUnevaluated(taskId || undefined)
      message.success(res.message)
      load()
      loadDist()
    } catch {
      message.error('批量评估失败')
    } finally {
      setBatchEvaluating(false)
    }
  }, [taskId, load, loadDist])

  const onManualTakeover = useCallback(async (r: EvalItem) => {
    const itemId = r.item_id
    setManualTaking((prev) => ({ ...prev, [itemId]: true }))
    try {
      const result = await orderApi.manualTakeover(itemId, r.task_id)
      if (result.outcome === 'success') {
        message.success(result.message || '抢单成功')
      } else if (result.outcome === 'skipped_duplicate') {
        message.info(result.message || '商品已下过单，幂等跳过')
      }
      load()
    } catch (err: unknown) {
      showStatusError(
        err,
        MANUAL_TAKEOVER_ERROR_MESSAGES,
        MANUAL_TAKEOVER_TIMEOUT_MESSAGE,
        MANUAL_TAKEOVER_FALLBACK_MESSAGE,
      )
    } finally {
      setManualTaking((prev) => ({ ...prev, [itemId]: false }))
    }
  }, [load])

  const onTitleClick = useCallback((e: React.MouseEvent, r: EvalItem, url: string) => {
    e.preventDefault()
    const itemId = r.item_id
    if (itemId === '') return
    const hide = message.loading(`正在采集 ${itemId.slice(0, 8)}...`, 0)
    itemApi.refresh(itemId, r.task_id || undefined).then(() => {
      hide()
      message.success(`已更新商品信息：${itemId.slice(0, 8)}...`)
      load()
    }).catch((err: unknown) => {
      hide()
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail || `采集失败：${itemId.slice(0, 8)}...，请稍后重试`)
    })
    globalThis.open(url, '_blank', 'noopener,noreferrer')
  }, [load])

  return {
    selectedRowKeys,
    setSelectedRowKeys,
    batchAIEvaluating,
    batchProgress,
    onBatchAIEval,
    batchCollecting,
    batchCollectProgress,
    onBatchCollectOfficial,
    recomputing,
    onRecompute,
    batchEvaluating,
    onBatchEvaluateUnevaluated,
    manualTaking,
    onManualTakeover,
    onTitleClick,
  }
}
