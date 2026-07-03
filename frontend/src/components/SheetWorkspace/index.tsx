import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SheetTabs } from './SheetTabs'
import { SheetContent } from './SheetContent'
import { SheetPreferences } from './SheetPreferences'
import { useSheetSync } from '../../hooks/useSheetSync'
import { useIsMobile } from '../../hooks/useIsMobile'
import { useSheetStore } from '../../stores/sheetStore'
import './sheet.css'

/**
 * SheetWorkspace 容器组件
 *
 * 职责：组装标签栏、内容区、偏好设置面板，注入 navigate 到 store，
 * 同步移动端模式，驱动 URL↔栈 双向同步。
 *
 * 为什么在此处注入 navigate 而非 store 内部直接 import：
 * store 是纯逻辑层，不应感知路由库；navigate 来自 Router 上下文，
 * 必须在组件树内获取，由容器注入实现关注点分离。
 */
export function SheetWorkspace() {
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const sheets = useSheetStore((s) => s.sheets)
  const activeId = useSheetStore((s) => s.activeId)
  const preferences = useSheetStore((s) => s.preferences)
  const activateSheet = useSheetStore((s) => s.activateSheet)
  const closeSheet = useSheetStore((s) => s.closeSheet)
  const minimizeSheet = useSheetStore((s) => s.minimizeSheet)
  const setMobileMode = useSheetStore((s) => s.setMobileMode)
  const setNavigator = useSheetStore((s) => s.setNavigator)

  const [prefOpen, setPrefOpen] = useState(false)

  // 注入 navigate 到 store（栈→URL 同步通道）
  // 为什么用 useEffect 而非渲染时调用：setNavigator 触发 set()，在渲染中调用会无限循环
  useEffect(() => {
    setNavigator(navigate)
  }, [navigate, setNavigator])

  // 同步移动端模式到 store：影响 openSheet 的单 sheet 替换逻辑
  useEffect(() => {
    setMobileMode(isMobile)
  }, [isMobile, setMobileMode])

  // URL→栈 同步：监听 location.pathname 变化调用 openSheet
  useSheetSync()

  const activeSheet = sheets.find((s) => s.id === activeId)

  // 关闭按钮行为：根据偏好选择最小化（保留状态）或真正关闭
  const handleClose = (id: string) => {
    if (preferences.minimizeInsteadOfClose) {
      minimizeSheet(id)
    } else {
      closeSheet(id)
    }
  }

  return (
    <div className={`sheet-workspace${preferences.enableAnimation ? '' : ' no-animation'}`}>
      {/* 移动端隐藏标签栏：单 sheet 全屏模式 */}
      {!isMobile && (
        <SheetTabs
          sheets={sheets}
          activeId={activeId}
          preferences={preferences}
          onActivate={activateSheet}
          onClose={handleClose}
          onMinimize={minimizeSheet}
          onOpenPreferences={() => setPrefOpen(true)}
        />
      )}
      <div className="sheet-content-area">
        <SheetContent sheet={activeSheet} />
      </div>
      <SheetPreferences open={prefOpen} onClose={() => setPrefOpen(false)} />
    </div>
  )
}

export default SheetWorkspace
