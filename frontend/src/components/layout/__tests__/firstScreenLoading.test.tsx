import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen } from '@testing-library/react'
import FirstScreenSkeleton, { FIRST_SCREEN_STAGE_LABELS } from '../FirstScreenSkeleton'

// 首屏加载与失败态守卫（T02560 / 2.5-10、2.5-12）
const LAYOUT_SOURCE = readFileSync(resolve(__dirname, '../MainLayout.tsx'), 'utf-8')

describe('首屏骨架屏（T02560）', () => {
  it('三个阶段各自给出对应文案，且都是同一个骨架结构', () => {
    expect(Object.keys(FIRST_SCREEN_STAGE_LABELS).sort()).toEqual(['auth', 'login', 'menu'])
    const { unmount } = render(<FirstScreenSkeleton stage="menu" />)
    expect(screen.getByText('正在加载菜单…')).toBeTruthy()
    expect(document.querySelectorAll('.ant-skeleton').length).toBeGreaterThanOrEqual(3)
    unmount()
    render(<FirstScreenSkeleton stage="auth" />)
    expect(screen.getByText('正在验证登录状态…')).toBeTruthy()
  })

  it('骨架屏声明为 status 区域，读屏能播报等待状态', () => {
    render(<FirstScreenSkeleton stage="login" />)
    expect(document.querySelector('[role="status"]')).toBeTruthy()
    expect(screen.getByText('正在跳转登录页…')).toBeTruthy()
  })

  it('MainLayout 不再用三段全屏大 Spin 串行占位', () => {
    expect(LAYOUT_SOURCE).toContain('FirstScreenSkeleton')
    expect(LAYOUT_SOURCE).not.toContain('<Spin size="large"')
    for (const tip of ['正在验证登录状态...', '正在跳转到登录页...', '正在加载菜单...']) {
      expect(LAYOUT_SOURCE).not.toContain(tip)
    }
  })

  it('菜单失败与告警失败都有内联重试入口，不再静默丢弃 error', () => {
    expect(LAYOUT_SOURCE).toContain('菜单加载失败')
    expect(LAYOUT_SOURCE).toContain('今日告警加载失败')
    expect(LAYOUT_SOURCE).toContain('onRetryMenu')
    // 告警重试入口自 T02561 起随计数口径一起收进 useNotificationModel（notif.refreshAlerts）
    expect(LAYOUT_SOURCE).toContain('notif.refreshAlerts')
    // 曾经的形态：statsApi.today() 的 catch 是空的
    expect(LAYOUT_SOURCE).not.toContain('statsApi.today().then(setTodayAlert).catch(() => {})')
  })
})
