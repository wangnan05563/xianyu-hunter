import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ConfigProvider } from 'antd'
import { MemoryRouter } from 'react-router-dom'
import { AboutMenuList } from '../AboutMenuList'
import { TEXTS } from '../i18n'
import { API_BASE } from '@/utils/apiBase'

// MemoryRouter 包装：AboutMenuList 内部用 Link 渲染 help 项
function renderList(onOpenLicenses = vi.fn()) {
  render(
    <ConfigProvider>
      <MemoryRouter>
        <AboutMenuList onOpenLicenses={onOpenLicenses} />
      </MemoryRouter>
    </ConfigProvider>,
  )
  return { onOpenLicenses }
}

describe('AboutMenuList', () => {
  it('渲染全部 8 个菜单项', () => {
    renderList()
    // 按 i18n 文案逐项校验，确保 8 项都渲染
    expect(screen.getByText(TEXTS.menu.terms)).toBeInTheDocument()
    expect(screen.getByText(TEXTS.menu.privacy)).toBeInTheDocument()
    expect(screen.getByText(TEXTS.menu.licenses)).toBeInTheDocument()
    expect(screen.getByText(TEXTS.menu.help)).toBeInTheDocument()
    expect(screen.getByText(TEXTS.menu.api)).toBeInTheDocument()
    expect(screen.getByText(TEXTS.menu.contact)).toBeInTheDocument()
    expect(screen.getByText(TEXTS.menu.community)).toBeInTheDocument()
    expect(screen.getByText(TEXTS.menu.report)).toBeInTheDocument()
  })

  it('点击 licenses 项触发 onOpenLicenses 回调', () => {
    const { onOpenLicenses } = renderList()
    fireEvent.click(screen.getByText(TEXTS.menu.licenses))
    expect(onOpenLicenses).toHaveBeenCalledTimes(1)
  })

  it('外部链接项使用 target=_blank 与 rel=noopener', () => {
    renderList()
    // 用户协议为外部链接
    const termsLink = screen.getByText(TEXTS.menu.terms).closest('a')
    expect(termsLink).toHaveAttribute('target', '_blank')
    expect(termsLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('help 项为 SPA 内链（不打开新窗口）', () => {
    renderList()
    const helpLink = screen.getByText(TEXTS.menu.help).closest('a')
    // 内部链接不应有 target=_blank
    expect(helpLink).not.toHaveAttribute('target', '_blank')
    // href 应指向 /help
    expect(helpLink).toHaveAttribute('href', '/help')
  })

  it('api 项 href 指向 API_BASE + api/docs', () => {
    renderList()
    const apiLink = screen.getByText(TEXTS.menu.api).closest('a')
    // 部署子路径前缀（BASE_URL）：本地/测试为 /xianyu/，确保域名模式 /xianyu 下文档链接可达
    expect(apiLink).toHaveAttribute('href', `${API_BASE}api/docs`)
  })
})
