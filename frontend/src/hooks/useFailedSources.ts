import { useCallback, useState } from 'react'

/**
 * 数据源失败账（T02586 假回执清零 → T02701 抽成共用 hook）。
 *
 * 每个区块单独记一次成功/失败：失败时页面要显示错误态而不是「暂无数据 / 0 / 转圈」，
 * 成功时把该键从账上摘掉。取值时**只在新请求成功时覆盖旧数据**，
 * 所以弱网刷新失败不会把上一次的好数据冲成空列表。
 */
export function useFailedSources<K extends string>() {
  const [failed, setFailed] = useState<Partial<Record<K, boolean>>>({})

  const mark = useCallback((key: K, ok: boolean) => {
    setFailed(prev => {
      if (ok) {
        if (!prev[key]) return prev
        const next = { ...prev }
        delete next[key]
        return next
      }
      return prev[key] ? prev : { ...prev, [key]: true }
    })
  }, [])

  /** Promise.allSettled 单项记账： fulfilled → 返回值并销账；rejected → 记失败并返回 null */
  const settle = useCallback(<T,>(r: PromiseSettledResult<T>, key: K): T | null => {
    if (r.status === 'fulfilled') {
      mark(key, true)
      return r.value
    }
    mark(key, false)
    return null
  }, [mark])

  /** 单独一路请求（非 allSettled）的记账包装：成功返回数据，失败记上账并返回 null */
  const track = useCallback(async <T,>(key: K, p: Promise<T>): Promise<T | null> => {
    try {
      const v = await p
      mark(key, true)
      return v
    } catch {
      mark(key, false)
      return null
    }
  }, [mark])

  const isFailed = useCallback((key: K): boolean => !!failed[key], [failed])

  return { failed, mark, settle, track, isFailed }
}
