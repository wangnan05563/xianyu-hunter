// T02717：MobileLogin 曾实现但未挂路由，移动端 401/退出都落到桌面登录页。
// 这条用例从路由表本身发起渲染，证明 /m/login 真的渲染出移动端登录页；
// 若路由没挂，会命中 path="*" 的 Navigate，页面上一片空白。
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>()
  return {
    ...actual,
    authApi: {
      ...actual.authApi,
      getBrowserImportStatus: vi.fn(async () => ({
        edge: { exists: true, has_goofish_cookie: false },
        chrome: { exists: false, has_goofish_cookie: false },
      })),
    },
  }
})

import MobileRoutes from '../routes'

describe('移动端登录路由（T02717）', () => {
  it('/m/login 渲染 MobileLogin，而不是被兜底路由送回首页', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <MobileRoutes />
      </MemoryRouter>,
    )
    expect(await screen.findByText('浏览器导入')).toBeTruthy()
    expect(screen.getByText('手动 Cookie 注入')).toBeTruthy()
  })

  it('移动端退出登录回 /m/login，不再甩到桌面版', () => {
    const src = readFileSync(resolve(__dirname, '../components/AccountSwitcher.tsx'), 'utf-8')
    expect(src).toContain("globalThis.location.href = '/xianyu/m/login'")
    expect(src).not.toContain("globalThis.location.href = '/xianyu/login'")
  })
})
