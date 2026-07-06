import { useState, useCallback } from 'react'
import { message } from 'antd'
import { evalApi, type EvalItem } from '../../../api'

/**
 * 评估反馈 Hook
 *
 * 为什么拆出：三档反馈（准确/部分准确/不准确）有独立的 loading 状态
 * 和提交逻辑，独立后主组件列定义中只需调用单一函数。
 */
export interface EvalFeedbackState {
  feedbackSubmitting: Record<string, boolean>
  onFeedback: (r: EvalItem, feedback: 'accurate' | 'inaccurate' | 'partial') => Promise<void>
}

export function useEvalFeedback(
  setItems: React.Dispatch<React.SetStateAction<EvalItem[]>>,
): EvalFeedbackState {
  const [feedbackSubmitting, setFeedbackSubmitting] = useState<Record<string, boolean>>({})

  const onFeedback = useCallback(async (r: EvalItem, feedback: 'accurate' | 'inaccurate' | 'partial') => {
    const itemId = r.item_id
    const taskId = r.task_id
    setFeedbackSubmitting((prev) => ({ ...prev, [itemId]: true }))
    try {
      await evalApi.submitFeedback(itemId, feedback, undefined, taskId)
      setItems((prev) =>
        prev.map((it) =>
          it.item_id === itemId && it.created_at === r.created_at
            ? { ...it, payload: { ...it.payload, feedback } }
            : it,
        ),
      )
      message.success('反馈已提交，感谢您的评价')
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        message.error('评估记录不存在，可能已被重新计算')
      } else {
        message.error('反馈提交失败')
      }
    } finally {
      setFeedbackSubmitting((prev) => ({ ...prev, [itemId]: false }))
    }
  }, [setItems])

  return {
    feedbackSubmitting,
    onFeedback,
  }
}
