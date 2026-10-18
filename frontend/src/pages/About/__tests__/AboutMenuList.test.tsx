import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ConfigProvider } from 'antd'
import { MemoryRouter } from 'react-router-dom'
import { AboutMenuList } from '../AboutMenuList'
import { TEXTS } from '../i18n'
import { API_BASE } from '@/utils/apiBase'

// MemoryRouter 包装：AboutMenuList 内部用 Link 渲染 help 项
function renderList(onOpenLicenses = vi.fn()) {
  const result = render(
    <ConfigProvider>
      <MemoryRouter>
        <AboutMenuList onOpenLicenses={onOpenLicenses} />
      </MemoryRouter>
    </ConfigProvider>,
  )
  return { ...result, onOpenLicenses }
}

describe('AboutMenuList', () => {
  it('渲染已就绪的 3 个菜单项，占位外链不渲染', () => {
    const { container } = renderList()
    expect(screen.getByText(TEXTS.menu.licenses)).toBeInTheDocument()
    expect(screen.getByText(TEXTS.menu.help)).toBeInTheDocument()
    expect(screen.getByText(TEXTS.menu.api)).toBeInTheDocument()
    // 地址未就绪（example.com 占位）的条目不得出现在发布版
    expect(screen.queryByText(TEXTS.menu.terms)).not.toBeInTheDocument()
    expect(screen.queryByText(TEXTS.menu.privacy)).not.toBeInTheDocument()
    expect(screen.queryByText(TEXTS.menu.contact)).not.toBeInTheDocument()
    expect(screen.queryByText(TEXTS.menu.community)).not.toBeInTheDocument()
    expect(screen.queryByText(TEXTS.menu.report)).not.toBeInTheDocument()
    expect(container.innerHTML).not.toContain('example.com')
  })

  it('点击 licenses 项触发 onOpenLicenses 回调', () => {
    const { onOpenLicenses } = renderList()
    fireEvent.click(screen.getByText(TEXTS.menu.licenses))
    expect(onOpenLicenses).toHaveBeenCalledTimes(1)
  })

  it('外部链接项使用 target=_blank 与 rel=noopener', () => {
    renderList()
    const apiLink = screen.getByText(TEXTS.menu.api).closest('a')
    expect(apiLink).toHaveAttribute('target', '_blank')
    expect(apiLink).toHaveAttribute('rel', 'noopener noreferrer')
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
