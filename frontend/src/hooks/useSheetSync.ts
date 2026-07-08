import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
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
 *
 * openSheet 失败时 URL 回退：
 * navigate 改变了 URL 但 openSheet 可能因 not_found（路径未注册）或 limit（栈满）
 * 未创建/激活新 sheet。此时 URL 与 active sheet 的 path 不一致，
 * 依赖 useParams()/useSearchParams() 的组件会拿到错误的值。
 * 典型案例：TaskEditor 依赖 useParams().id 判断编辑/新增模式，
 * URL 漂移后 isEdit 误判为 false，提交时创建重复任务。
 * 回退后 activeSheet.path === URL，防循环检查会跳过，不会死循环。
 */
export function useSheetSync(): void {
  const location = useLocation()
  const navigate = useNavigate()
  const sheets = useSheetStore((s) => s.sheets)
  const activeId = useSheetStore((s) => s.activeId)

  useEffect(() => {
    // 保留 query string：confirm-buy 等外部通知回链页面依赖 ?task_id=xxx&item_id=yyy
    // 若只取 pathname，sheet 打开后 URL 丢失 query，组件读不到参数
    const path = location.pathname + location.search
    const activeSheet = sheets.find((s) => s.id === activeId)
    // 防循环：当前激活 sheet 的 path 已等于 URL 则不操作
    if (activeSheet?.path === path) return
    const result = openSheetWithNotification(path)
    // openSheet 失败时回退 URL 到当前 active sheet 的 path，保持 URL 与 active sheet 一致
    if (!result.ok && activeSheet) {
      navigate(activeSheet.path, { replace: true })
    }
  }, [location.pathname, location.search, sheets, activeId, navigate])
}
