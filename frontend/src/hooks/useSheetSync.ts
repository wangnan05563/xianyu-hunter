import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useSheetStore } from '../stores/sheetStore'

/**
 * URL ↔ sheet 栈双向同步 Hook
 *
 * 职责分工：
 * - URL→栈：本 Hook 监听 location.pathname 变化，调用 openSheet 同步到栈
 * - 栈→URL：由 store 内部 _navigator（注入的 navigate）完成
 *
 * 防循环关键：每次同步前比较"当前激活 sheet 的 path"与"URL path"，
 * 相同则跳过，避免 URL→栈→URL 死循环。
 */
export function useSheetSync(): void {
  const location = useLocation()
  const openSheet = useSheetStore((s) => s.openSheet)
  const sheets = useSheetStore((s) => s.sheets)
  const activeId = useSheetStore((s) => s.activeId)

  useEffect(() => {
    const path = location.pathname
    const activeSheet = sheets.find((s) => s.id === activeId)
    // 防循环：当前激活 sheet 的 path 已等于 URL 则不操作
    if (activeSheet?.path === path) return
    openSheet(path)
  }, [location.pathname, sheets, activeId, openSheet])
}
