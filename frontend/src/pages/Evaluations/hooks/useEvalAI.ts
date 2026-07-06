import { useState, useRef, useCallback } from 'react'
import { message } from 'antd'
import { aiApi, type AIConditionResult, type DeepAnalyzeResult } from '../../../api'

/**
 * AI 评估 Hook
 *
 * 为什么拆出：AI 评估和深度分析各有 4-5 个 state + 复杂的异步逻辑，
 * 包括 race condition 防护（用 ref 跟踪最新请求）。
 * 独立后主组件只需要处理 Modal 的开关和展示。
 */
export interface EvalAIState {
  aiModalOpen: boolean
  aiLoading: boolean
  aiResult: AIConditionResult | null
  aiItemId: string
  setAiModalOpen: (v: boolean) => void
  onAIEval: (itemId: string) => Promise<void>

  deepModalOpen: boolean
  deepLoading: boolean
  deepResult: DeepAnalyzeResult | null
  deepItemId: string
  setDeepModalOpen: (v: boolean) => void
  onDeepAnalyze: (itemId: string) => Promise<void>
}

export function useEvalAI(): EvalAIState {
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResult, setAiResult] = useState<AIConditionResult | null>(null)
  const [aiItemId, setAiItemId] = useState('')
  const aiItemIdRef = useRef('')

  const [deepModalOpen, setDeepModalOpen] = useState(false)
  const [deepLoading, setDeepLoading] = useState(false)
  const [deepResult, setDeepResult] = useState<DeepAnalyzeResult | null>(null)
  const [deepItemId, setDeepItemId] = useState('')
  const deepItemIdRef = useRef('')

  const handleAiError = (err: unknown, fallbackMsg: string, closeModal: () => void) => {
    const error = err as { response?: { status?: number; data?: { detail?: string } } }
    const status = error?.response?.status
    const detail = error?.response?.data?.detail
    if (status === 403) {
      message.error('AI 功能未开启，请在配置页面开启')
    } else if (status === 404) {
      message.error('商品不存在于数据库中')
    } else if (status === 422) {
      message.error('请求参数错误：商品 ID 为空')
    } else {
      message.error(detail || fallbackMsg)
    }
    closeModal()
  }

  const onAIEval = useCallback(async (itemId: string) => {
    if (itemId === '') {
      message.error('商品 ID 为空，无法评估')
      return
    }
    aiItemIdRef.current = itemId
    setAiItemId(itemId)
    setAiModalOpen(true)
    setAiLoading(true)
    setAiResult(null)
    try {
      const result = await aiApi.evaluateCondition(itemId)
      if (aiItemIdRef.current !== itemId) return
      setAiResult(result)
    } catch (err: unknown) {
      if (aiItemIdRef.current !== itemId) return
      handleAiError(err, 'AI 评估失败，请检查 AI 配置', () => setAiModalOpen(false))
    } finally {
      if (aiItemIdRef.current === itemId) {
        setAiLoading(false)
      }
    }
  }, [])

  const onDeepAnalyze = useCallback(async (itemId: string) => {
    if (itemId === '') {
      message.error('商品 ID 为空，无法分析')
      return
    }
    deepItemIdRef.current = itemId
    setDeepItemId(itemId)
    setDeepModalOpen(true)
    setDeepLoading(true)
    setDeepResult(null)
    try {
      const result = await aiApi.deepAnalyze(itemId)
      if (deepItemIdRef.current !== itemId) return
      setDeepResult(result)
    } catch (err: unknown) {
      if (deepItemIdRef.current !== itemId) return
      handleAiError(err, '深度分析失败，请稍后重试', () => setDeepModalOpen(false))
    } finally {
      if (deepItemIdRef.current === itemId) {
        setDeepLoading(false)
      }
    }
  }, [])

  return {
    aiModalOpen,
    aiLoading,
    aiResult,
    aiItemId,
    setAiModalOpen,
    onAIEval,

    deepModalOpen,
    deepLoading,
    deepResult,
    deepItemId,
    setDeepModalOpen,
    onDeepAnalyze,
  }
}
