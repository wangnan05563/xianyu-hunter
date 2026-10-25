import { useEffect, useState } from 'react'
import { Badge, theme } from 'antd'
import { TipButton } from '@/components/TipButton'
import { CompressOutlined, CloseOutlined } from '@ant-design/icons'
import { isNarrowDesktopViewport } from '../../hooks/breakpoints'
import { storage } from '../../utils/storage'

/**
 * 桌面窄窗（宽度 ∈ (768, 992]）的一次性缩略模式引导 —— T02632 条目 2
 *
 * 工单原建议「视口 ≤768px 时自动把标签栏收起为缩略模式」在字面上做不了：
 * ≤768 由 useIsMobile 直接不渲染标签栏，切缩略是无对象的动作。这一档才是
 * 「桌面外壳 + 标签栏还在 + 横向空间吃紧」。
 *
 * 做法遵守工单口径：给引导，不静默改用户偏好（thumbnailMode 仍由用户在
 * Sheet 偏好里决定）。提示只出现一次，被点掉或关闭后写 localStorage 不再打扰。
 */
export const NARROW_HINT_DISMISS_KEY = 'xh.sheets.narrowThumbnailHintDismissed'

const HINT_TIP = '窗口偏窄，标签栏挤：可在偏好设置里启用「缩略图模式」，同屏放更多标签（不会改动你的其他设置）'

export interface NarrowSheetHintProps {
  readonly sheetCount: number
  readonly maxSheets: number
  readonly thumbnailMode: boolean
  readonly onOpenPreferences: () => void
}

/** 近满判定：达到上限前一个就开始挤（阈值跟着 maxSheets 走，不再散写魔法数） */
export function isNearSheetCap(sheetCount: number, maxSheets: number): boolean {
  return sheetCount >= Math.max(2, maxSheets - 1)
}

export function NarrowSheetHint({
  sheetCount,
  maxSheets,
  thumbnailMode,
  onOpenPreferences,
}: NarrowSheetHintProps) {
  const { token: themeToken } = theme.useToken()
  const [narrowDesktop, setNarrowDesktop] = useState<boolean>(() =>
    globalThis.window === undefined ? false : isNarrowDesktopViewport(),
  )
  const [dismissed, setDismissed] = useState<boolean>(() =>
    storage.get<boolean>(NARROW_HINT_DISMISS_KEY, false, (v): v is boolean => v === true),
  )

  useEffect(() => {
    if (globalThis.window === undefined) return
    const handler = () => setNarrowDesktop(isNarrowDesktopViewport())
    globalThis.window.addEventListener('resize', handler)
    return () => globalThis.window.removeEventListener('resize', handler)
  }, [])

  if (dismissed || thumbnailMode || !narrowDesktop || !isNearSheetCap(sheetCount, maxSheets)) {
    return null
  }

  const dismiss = () => {
    storage.set(NARROW_HINT_DISMISS_KEY, true)
    setDismissed(true)
  }

  return (
    <div
      className="sheet-narrow-hint"
      data-testid="sheet-narrow-thumbnail-hint"
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2, padding: '4px 0' }}
    >
      <TipButton
        tip={HINT_TIP}
        type="text"
        size="small"
        aria-label="缩略模式引导"
        onClick={() => {
          dismiss()
          onOpenPreferences()
        }}
        icon={
          <Badge dot color={themeToken.colorPrimary}>
            <CompressOutlined style={{ fontSize: 14 }} />
          </Badge>
        }
      />
      <TipButton
        tip="不再提示"
        type="text"
        size="small"
        aria-label="不再提示缩略模式"
        onClick={dismiss}
        icon={<CloseOutlined style={{ fontSize: 10, opacity: 0.55 }} />}
      />
    </div>
  )
}

export default NarrowSheetHint
