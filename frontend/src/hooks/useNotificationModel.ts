import { useCallback, useEffect, useRef, useState } from 'react'
import { notificationApi, statsApi } from '../api'
import type { TodayAlert } from '../api/types'

/**
 * 通知与告警的统一模型（T02561 / FR-B-1）
 *
 * 两套计数口径在此一次定死，铃铛 badge、告警抽屉、通知中心三处共用：
 * - 告警（alert）＝ 今日异常，来自 /api/stats/today 的 alerts.counts（failed + timeout + low_eval），
 *   不落库、无「已读」概念，每天自然归零；
 * - 未读（unread）＝ 持久化通知，来自 /api/notifications/unread_count 的 notifications 表（read_at IS NULL），
 *   只有标记已读/删除才会减少。
 * 二者不可相加成一个数字——那正是评审 2.9-1 指出的「用户无法判断到底有几条没看」的来源。
 */

export type BellBadge = {
  /** 铃铛上显示的数字；0 表示不显示 */
  count: number
  /** true＝这个数字是今日告警；false＝是未读通知。决定 badge 颜色与 tooltip 文案 */
  isAlert: boolean
}

/**
 * 铃铛单一数字的取值规则：告警优先，无告警时退为未读通知。
 * 为什么不做加法：两个口径相加会造出一个既非告警也非通知的第三种数，正是本单要消掉的问题。
 */
export function computeBellBadge(alertCount: number, unreadCount: number): BellBadge {
  if (alertCount > 0) return { count: alertCount, isAlert: true }
  return { count: unreadCount, isAlert: false }
}

export function bellBadgeTip(badge: BellBadge): string {
  if (badge.count === 0) return '打开通知抽屉（今日告警与未读通知）'
  return badge.isAlert
    ? `今日告警 ${badge.count} 条，点击查看`
    : `未读通知 ${badge.count} 条，点击查看`
}

/** 告警类 → 落地页：抽屉列表项按类跳转（N11） */
export const ALERT_JUMP_TARGETS = {
  failed: '/orders',
  timeout: '/orders',
  low_eval: '/evaluations',
} as const

export type AlertKind = keyof typeof ALERT_JUMP_TARGETS

export type NotificationModel = {
  readonly alerts: TodayAlert | null
  readonly alertCount: number
  readonly unreadCount: number
  readonly readCount: number
  readonly notifTotal: number
  readonly alertError: string | null
  readonly bell: BellBadge
  readonly refreshAlerts: () => void
  readonly refreshCounts: () => void
}

const POLL_MS = 30_000

/**
 * 计数失效广播：通知中心里标记已读/删除后调用，让 Header 铃铛立刻跟上。
 * 为什么不等 30s 轮询：FR-B-1 要求「badge 与已读联动」，等轮询会让用户以为已读没生效。
 * 为什么用广播而非全局 store：本 Hook 有两个独立实例（Header 与通知中心页），
 * 各自持有状态，广播是让它们同步的最小通道。
 */
const countListeners = new Set<() => void>()

export function invalidateNotificationCounts(): void {
  countListeners.forEach((fn) => fn())
}

export function useNotificationModel({ enabled }: { enabled: boolean }): NotificationModel {
  const [alerts, setAlerts] = useState<TodayAlert | null>(null)
  const [alertError, setAlertError] = useState<string | null>(null)
  const [unreadCount, setUnreadCount] = useState(0)
  const [readCount, setReadCount] = useState(0)
  const [notifTotal, setNotifTotal] = useState(0)
  const reqRef = useRef(0)

  const refreshAlerts = useCallback(() => {
    statsApi.today()
      .then((data) => {
        setAlerts(data)
        setAlertError(null)
      })
      .catch((err: unknown) => setAlertError(err instanceof Error ? err.message : String(err)))
  }, [])

  // 三个计数一次取回：后端 unread_count 返回的是全量口径，不受任何列表筛选影响（2.9-3）
  const refreshCounts = useCallback(() => {
    notificationApi.counts().then((c) => {
      setUnreadCount(c.unread)
      setReadCount(c.read)
      setNotifTotal(c.total)
    }).catch(() => { /* 计数加载失败不出声：抽屉与通知中心各自还有列表错误态 */ })
  }, [])

  useEffect(() => {
    if (!enabled) return
    const self = () => refreshCounts()
    countListeners.add(self)
    return () => { countListeners.delete(self) }
  }, [enabled, refreshCounts])

  useEffect(() => {
    if (!enabled) return
    // 每次启用都重新取号，避免上一轮登录态的响应覆盖新一轮状态
    reqRef.current += 1
    refreshAlerts()
    refreshCounts()
    const timer = setInterval(() => {
      refreshAlerts()
      refreshCounts()
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [enabled, refreshAlerts, refreshCounts])

  const alertCount = alerts
    ? alerts.alerts.counts.failed + alerts.alerts.counts.timeout + alerts.alerts.counts.low_eval
    : 0

  return {
    alerts,
    alertCount,
    unreadCount,
    readCount,
    notifTotal,
    alertError,
    bell: computeBellBadge(alertCount, unreadCount),
    refreshAlerts,
    refreshCounts,
  }
}
