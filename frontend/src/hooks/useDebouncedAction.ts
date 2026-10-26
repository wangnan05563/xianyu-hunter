import { useCallback, useEffect, useRef } from 'react'

/** 筛选改完之后等多久自动查询；与工单裁定的 300ms 一致 */
export const FILTER_AUTO_DELAY_MS = 300

/**
 * 「改完就查」的防抖通道（T02669）。
 *
 * 为什么只给非文本控件用：文本框逐字符触发会把中文输入法的候选过程变成一串请求，
 * 所以商品ID 这类输入仍走回车/失焦，由调用方决定何时 flush。
 * flush 是给「查询」按钮留的立即执行口径：取消尚未到点的自动查询，马上查一次。
 */
export function useDebouncedAction(
  action: () => void,
  delayMs: number = FILTER_AUTO_DELAY_MS,
) {
  const actionRef = useRef(action)
  actionRef.current = action
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const cancel = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current)
      timer.current = null
    }
  }, [])

  useEffect(() => cancel, [cancel])

  const schedule = useCallback(() => {
    cancel()
    timer.current = setTimeout(() => {
      timer.current = null
      actionRef.current()
    }, delayMs)
  }, [cancel, delayMs])

  const flush = useCallback(() => {
    cancel()
    actionRef.current()
  }, [cancel])

  return { schedule, flush, cancel }
}
