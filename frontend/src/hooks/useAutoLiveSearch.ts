import { useCallback, useEffect, useRef, useState } from 'react'
import { taskLinkApi } from '../api'
import type { Task } from '../api/types'

interface UseAutoLiveSearchOptions {
  tasks: Task[]
  enabled: boolean
  onTaskSearchStart?: (taskId: string) => void
  // detail：透传后端 error.detail（如"系统正在执行后台搜索任务，请稍后重试"），
  // 让上层给出更精准的失败提示，避免笼统"自动搜索失败"
  onTaskSearchComplete?: (taskId: string, success: boolean, itemCount: number, detail?: string) => void
}

interface UseAutoLiveSearchReturn {
  remainMap: Record<string, number>
  searchingIds: Set<string>
  pauseAll: () => void
  resumeAll: () => void
}

// 每秒递减 remainMap：倒计时归零的任务入队搜索，搜索中的任务跳过递减
// 为什么提取到模块级：原 useEffect → setInterval → setRemainMap(prev =>) → forEach(taskId =>) 嵌套达 5 层，违反 S2004
function decrementRemainMap(
  prev: Record<string, number>,
  searchingIds: Set<string>,
  enqueue: (taskId: string) => void,
): Record<string, number> {
  const next = { ...prev }
  Object.keys(next).forEach((taskId) => {
    if (searchingIds.has(taskId)) return // 搜索中不递减
    const newVal = next[taskId] - 1
    if (newVal <= 0) {
      // 加入队列，倒计时显示 0
      enqueue(taskId)
      next[taskId] = 0
    } else {
      next[taskId] = newVal
    }
  })
  return next
}

/**
 * 任务列表自动实时搜索 Hook
 *
 * 设计要点（详见 docs/superpowers/specs/2026-07-02-task-auto-live-search-design.md）：
 * 1. 仅 status==='running' 任务参与倒计时
 * 2. 串行队列：同一时刻最多 1 个任务在搜索，避免浏览器锁竞争与反爬
 * 3. 页面不可见时暂停 tick（不累计也不重置剩余值，符合选项 B 决策）
 * 4. 不弹过滤 Modal，仅 toast 提示，避免无人值守弹窗堆积
 */
export function useAutoLiveSearch({
  tasks,
  enabled,
  onTaskSearchStart,
  onTaskSearchComplete,
}: UseAutoLiveSearchOptions): UseAutoLiveSearchReturn {
  const [remainMap, setRemainMap] = useState<Record<string, number>>({})
  const [searchingIds, setSearchingIds] = useState<Set<string>>(new Set())
  const queueRef = useRef<string[]>([])
  const processingRef = useRef<boolean>(false)
  const visibleRef = useRef<boolean>(!document.hidden)

  // 用 ref 持有最新引用，避免 setInterval 闭包陷阱
  // 为什么用 ref：setInterval 创建时持有 closure，后续 state 变化不会自动同步进去
  const searchingIdsRef = useRef<Set<string>>(new Set())
  const tasksRef = useRef<Task[]>(tasks)
  const enqueueSearchRef = useRef<(taskId: string) => void>(() => {})
  useEffect(() => {
    searchingIdsRef.current = searchingIds
  }, [searchingIds])
  useEffect(() => {
    tasksRef.current = tasks
  }, [tasks])

  // 初始化/更新倒计时：tasks 或 enabled 变化时重置
  // 使用 functional update 避免 remainMap 闭包陷阱
  useEffect(() => {
    setRemainMap((prev) => {
      if (!enabled) return {}
      const next: Record<string, number> = {}
      tasks.forEach((t) => {
        if (t.status === 'running') {
          // 仅初始化未在 remainMap 中的任务，避免覆盖进行中的倒计时
          // enabled=false→true 时 prev 为空，所有 running 任务都会重新初始化
          next[t.id] = prev[t.id] ?? (t.interval_seconds ?? 60)
        }
      })
      return next
    })
  }, [tasks, enabled])

  // visibilitychange 监听：仅更新 visibleRef，不重置 remainMap（选项 B 决策）
  useEffect(() => {
    const handler = () => {
      visibleRef.current = !document.hidden
    }
    document.addEventListener('visibilitychange', handler)
    return () => document.removeEventListener('visibilitychange', handler)
  }, [])

  // 串行处理队列
  const processQueue = useCallback(async () => {
    if (processingRef.current) return
    const taskId = queueRef.current.shift()
    if (!taskId) return
    processingRef.current = true
    setSearchingIds((prev) => new Set(prev).add(taskId))
    onTaskSearchStart?.(taskId)
    try {
      const res = await taskLinkApi.live(taskId)
      const itemCount = res?.items?.length ?? 0
      // 不展示过滤 Modal，仅 toast（避免自动搜索时弹窗干扰）
      onTaskSearchComplete?.(taskId, true, itemCount)
    } catch (err: unknown) {
      // 透传后端 detail：taskLinkApi.live 已按 axios 兼容格式抛出
      // 见 api/task.ts live() 中 throw new Error 附 response.data.detail
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      onTaskSearchComplete?.(taskId, false, 0, detail)
    } finally {
      setSearchingIds((prev) => {
        const next = new Set(prev)
        next.delete(taskId)
        return next
      })
      // 重置倒计时（用 ref 取最新 tasks，避免闭包陷阱）
      const task = tasksRef.current.find((t) => t.id === taskId)
      setRemainMap((prev) => ({
        ...prev,
        [taskId]: task?.interval_seconds ?? 60,
      }))
      processingRef.current = false
      // 处理下一个：用 setTimeout 让调用栈释放，避免长队列递归爆栈
      // 为什么不用 queueMicrotask：微任务仍在同一调用栈内执行，无法释放栈帧
      if (queueRef.current.length > 0) {
        setTimeout(() => processQueue(), 0)
      }
    }
  }, [onTaskSearchStart, onTaskSearchComplete])

  // 入队：使用 ref 包装，让 setInterval 能调用最新版
  const enqueueSearch = useCallback(
    (taskId: string) => {
      if (queueRef.current.includes(taskId)) return
      if (searchingIdsRef.current.has(taskId)) return
      queueRef.current.push(taskId)
      processQueue()
    },
    [processQueue],
  )
  useEffect(() => {
    enqueueSearchRef.current = enqueueSearch
  }, [enqueueSearch])

  // 每秒 tick（依赖仅 enabled，避免 searchingIds 变化重建 setInterval 导致 tick 抖动）
  useEffect(() => {
    if (!enabled) return
    const timer = setInterval(() => {
      // 页面不可见时暂停 tick（不累计，剩余值保持，符合选项 B）
      if (!visibleRef.current) return
      // 递减逻辑提取为模块级 decrementRemainMap，避免嵌套过深（S2004）
      setRemainMap((prev) => decrementRemainMap(prev, searchingIdsRef.current, enqueueSearchRef.current))
    }, 1000)
    return () => clearInterval(timer)
  }, [enabled])

  // pauseAll: 关闭开关时调用，清空队列与 remainMap
  // 为什么不清空 searchingIds：已发起的 SSE 不中断，完成后自然移除
  const pauseAll = useCallback(() => {
    queueRef.current = []
    setRemainMap({})
  }, [])

  // resumeAll: 开启开关时调用，重置所有 running 任务倒计时
  const resumeAll = useCallback(() => {
    const next: Record<string, number> = {}
    tasksRef.current.forEach((t) => {
      if (t.status === 'running') next[t.id] = t.interval_seconds ?? 60
    })
    setRemainMap(next)
  }, [])

  return { remainMap, searchingIds, pauseAll, resumeAll }
}
