import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import type React from 'react'
import { NarrowSheetHint, isNearSheetCap, NARROW_HINT_DISMISS_KEY } from '../NarrowSheetHint'

// T02632 条目 2：缩略模式仍靠用户手动开。桌面窄窗 + 标签接近上限时给一次性引导，
// 不静默改 thumbnailMode（工单明确要求「不要静默改用户偏好」）。

function setInnerWidth(width: number): void {
  Object.defineProperty(globalThis.window, 'innerWidth', { value: width, configurable: true })
}

const openPreferences = vi.fn()

const renderHint = (props: Partial<React.ComponentProps<typeof NarrowSheetHint>> = {}) =>
  render(
    <NarrowSheetHint
      sheetCount={4}
      maxSheets={5}
      thumbnailMode={false}
      onOpenPreferences={openPreferences}
      {...props}
    />,
  )

describe('缩略模式一次性引导（条目 2）', () => {
  beforeEach(() => {
    localStorage.clear()
    openPreferences.mockClear()
    setInnerWidth(900)
  })
  afterEach(() => {
    cleanup()
    localStorage.clear()
  })

  it('桌面窄窗 + 标签接近上限 + 未开缩略：出现引导', () => {
    renderHint()
    expect(screen.getByTestId('sheet-narrow-thumbnail-hint')).toBeInTheDocument()
  })

  it('宽窗不出现（768 以下也不出现，那一档标签栏根本不渲染）', () => {
    setInnerWidth(1440)
    renderHint()
    expect(screen.queryByTestId('sheet-narrow-thumbnail-hint')).toBeNull()
    cleanup()
    setInnerWidth(700)
    renderHint()
    expect(screen.queryByTestId('sheet-narrow-thumbnail-hint')).toBeNull()
  })

  it('用户已开缩略模式则不再提示', () => {
    renderHint({ thumbnailMode: true })
    expect(screen.queryByTestId('sheet-narrow-thumbnail-hint')).toBeNull()
  })

  it('点引导打开偏好设置，并落一次「已提示」标记（不写 thumbnailMode）', () => {
    renderHint()
    fireEvent.click(screen.getByLabelText('缩略模式引导'))
    expect(openPreferences).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId('sheet-narrow-thumbnail-hint')).toBeNull()
    expect(localStorage.getItem(NARROW_HINT_DISMISS_KEY)).toContain('true')
  })

  it('关掉提示后不再出现（重挂载也不出现）', () => {
    renderHint()
    fireEvent.click(screen.getByLabelText('不再提示缩略模式'))
    cleanup()
    renderHint()
    expect(screen.queryByTestId('sheet-narrow-thumbnail-hint')).toBeNull()
  })

  it('窗口从窄拉宽时提示自动隐藏，但不写「已提示」标记（下次窄回来仍可提醒）', () => {
    renderHint()
    setInnerWidth(1440)
    fireEvent(window, new Event('resize'))
    expect(screen.queryByTestId('sheet-narrow-thumbnail-hint')).toBeNull()
    expect(localStorage.getItem(NARROW_HINT_DISMISS_KEY)).toBeNull()
  })

  it('标签数没到近满阈值就不打扰', () => {
    renderHint({ sheetCount: 1 })
    expect(screen.queryByTestId('sheet-narrow-thumbnail-hint')).toBeNull()
  })

  it('近满阈值跟着 maxSheets 走', () => {
    expect(isNearSheetCap(4, 5)).toBe(true)
    expect(isNearSheetCap(3, 5)).toBe(false)
    expect(isNearSheetCap(1, 2)).toBe(false)
    expect(isNearSheetCap(2, 2)).toBe(true)
  })
})
