import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useSheetStore } from '../stores/sheetStore'
import { openSheetWithNotification } from '../components/SheetWorkspace/sheetNotifications'

/**
 * URL ↔ sheet 栈双向同步 Hook
 *
 * 职责分工：
 * - URL→栈：本 Hook 监听 location.pathname 变化，调用 openSheet 同步到栈
 * - 栈→URL：由 store 内部 _navigator（注入的 navigate）完成
 *
 * 防循环关键：每次同步前比较"当前激活 sheet 的 path"与"URL path"，
 * 相同则跳过，避免 URL→栈→URL 死循环。
 *
 * 为什么用 openSheetWithNotification 而非 store.openSheet：
 * URL 变化（如菜单点击触发的 navigate）也可能触发循环替换，
 * 此时需发 Toast 通知 + 撤销按钮，与菜单点击走相同路径
 */
export function useSheetSync(): void {
  const location = useLocation()
  const sheets = useSheetStore((s) => s.sheets)
  const activeId = useSheetStore((s) => s.activeId)

  useEffect(() => {
    // 保留 query string：confirm-buy 等外部通知回链页面依赖 ?task_id=xxx&item_id=yyy
    // 若只取 pathname，sheet 打开后 URL 丢失 query，组件读不到参数
    const path = location.pathname + location.search
    const activeSheet = sheets.find((s) => s.id === activeId)
    // 防循环：当前激活 sheet 的 path 已等于 URL 则不操作
    if (activeSheet?.path === path) return
    openSheetWithNotification(path)
  }, [location.pathname, location.search, sheets, activeId])
}
