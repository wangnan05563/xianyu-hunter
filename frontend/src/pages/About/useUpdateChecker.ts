import { useState, useCallback, useRef, useEffect } from 'react'
import { App } from 'antd'
import { aboutApi } from '../../api'
import { TEXTS } from './i18n'

/**
 * 检查更新状态机：
 * idle → loading → (latest | newer | error)
 * latest 3s 后自动回 idle（让用户看到"已是最新"反馈后恢复初始态）
 * newer / error 为终态，不自动回 idle（让用户充分阅读提示）
 */
export type UpdateState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'latest' }
  | { kind: 'newer'; url: string; latest: string; publishedAt?: string }
  | { kind: 'error'; reason: 'network' | 'server' }

const IDLE_TIMEOUT_MS = 3000
// 自动检查间隔：60 分钟
// 为什么选 60 分钟：GitHub 未认证 API 限速 60/小时/IP，60 分钟轮询刚好用满配额；
// 后端还有 5 分钟缓存兜底，即使前端轮询更频繁也不会击穿限速。
const AUTO_CHECK_INTERVAL_MS = 60 * 60 * 1000
// 挂载后延迟自动检查：5 秒
// 为什么延迟而非立即：避免阻塞首屏渲染；用户进入 About 页主要是查看版本信息，
// 5 秒后自动检查既不突兀又能及时反馈。
const AUTO_CHECK_DELAY_MS = 5000

// axios 错误简易判定：网络中断通常无 response 或 code 为 ERR_NETWORK
function isNetworkError(e: unknown): boolean {
  if (typeof e === 'object' && e !== null) {
    const err = e as { response?: unknown; code?: string }
    return !err.response || err.code === 'ERR_NETWORK'
  }
  return false
}

export function useUpdateChecker(current: string) {
  const [state, setState] = useState<UpdateState>({ kind: 'idle' })
  const { message } = App.useApp()
  // 持有 latest→idle 自动重置的 timer 句柄：组件卸载或重复触发 run 时需清理，
  // 否则卸载后 setState 仍会触发 React "Can't perform a React state update on an unmounted component" 警告
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // 自动检查间隔 timer 句柄（setInterval 返回值类型与 setTimeout 在浏览器中相同，但语义不同）
  const autoCheckTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // 挂载延迟检查 timer 句柄
  const mountDelayTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // 防止自动检查与手动检查并发：自动检查发起前检查此标志
  const isCheckingRef = useRef(false)

  // 内部检查实现：自动/手动共用，避免重复代码
  const performCheck = useCallback(async () => {
    if (isCheckingRef.current) {
      // 已有检查在进行中，跳过（防止自动+手动并发）
      return
    }
    isCheckingRef.current = true
    setState({ kind: 'loading' })
    try {
      const res = await aboutApi.checkUpdate()
      if (res.has_update) {
        setState({
          kind: 'newer',
          url: res.release_url,
          latest: res.latest,
          publishedAt: res.published_at,
        })
      } else {
        setState({ kind: 'latest' })
        // 清理上一次未触发的定时器（用户快速连续点击检查更新时，避免堆叠多个 timer）
        if (idleTimerRef.current) {
          clearTimeout(idleTimerRef.current)
        }
        // 3s 后自动回 idle，让按钮恢复可点击的初始态
        idleTimerRef.current = setTimeout(() => {
          idleTimerRef.current = null
          setState((prev) => (prev.kind === 'latest' ? { kind: 'idle' } : prev))
        }, IDLE_TIMEOUT_MS)
      }
    } catch (e) {
      setState({ kind: 'error', reason: isNetworkError(e) ? 'network' : 'server' })
    } finally {
      isCheckingRef.current = false
    }
  }, [])

  // 手动检查：用户点击「检查更新」按钮时调用
  const run = useCallback(async () => {
    await performCheck()
  }, [performCheck])

  // 挂载时延迟 5s 自动检查一次 + 启动 60 分钟定期检查
  // 为什么不在 useEffect deps 里放 current：current 变化时不应重置自动检查周期，
  // 否则用户在 About 页修改版本号会触发频繁检查
  useEffect(() => {
    // 5s 后发起首次自动检查
    mountDelayTimerRef.current = setTimeout(() => {
      performCheck()
    }, AUTO_CHECK_DELAY_MS)

    // 启动 60 分钟定期检查
    autoCheckTimerRef.current = setInterval(() => {
      performCheck()
    }, AUTO_CHECK_INTERVAL_MS)

    return () => {
      // 卸载时清理所有 timer，避免内存泄漏与对已卸载组件调用 setState
      if (mountDelayTimerRef.current) {
        clearTimeout(mountDelayTimerRef.current)
        mountDelayTimerRef.current = null
      }
      if (autoCheckTimerRef.current) {
        clearInterval(autoCheckTimerRef.current)
        autoCheckTimerRef.current = null
      }
      if (idleTimerRef.current) {
        clearTimeout(idleTimerRef.current)
        idleTimerRef.current = null
      }
    }
  }, [performCheck])

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(current)
      message.success(TEXTS.copied)
    } catch {
      // 剪贴板权限被拒时降级：仅 toast 提示
      message.warning(TEXTS.copyFailed)
    }
  }, [current, message])

  return { state, run, copy }
}
