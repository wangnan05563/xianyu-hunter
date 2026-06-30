import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ConfigProvider } from 'antd'
import { OpenSourceLicenses } from '../OpenSourceLicenses'
import { TEXTS } from '../i18n'

// jsdom 未实现 matchMedia，antd Modal 内部的 ResponsiveObserver 依赖它
// 这里在文件级别补一个最小可用 mock，避免 TypeError 中断渲染
beforeAll(() => {
  if (!window.matchMedia) {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  }
})

function renderModal(open = true) {
  const onClose = vi.fn()
  render(
    <ConfigProvider>
      <OpenSourceLicenses open={open} onClose={onClose} />
    </ConfigProvider>,
  )
  return { onClose }
}

describe('OpenSourceLicenses', () => {
  it('open=false 时不渲染 Modal 内容', () => {
    renderModal(false)
    expect(screen.queryByText(TEXTS.licensesTitle)).not.toBeInTheDocument()
  })

  it('open=true 时渲染标题和搜索框', () => {
    renderModal(true)
    expect(screen.getByText(TEXTS.licensesTitle)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(TEXTS.licensesSearchPlaceholder)).toBeInTheDocument()
  })

  it('默认展示全部依赖（前端 + 后端）', () => {
    renderModal(true)
    // 抽样验证前端依赖 react 存在（多个依赖名含 react 子串，用 getAllByText）
    expect(screen.getAllByText(/react/i).length).toBeGreaterThan(0)
    // 抽样验证后端依赖 fastapi 存在
    expect(screen.getByText(/fastapi/i)).toBeInTheDocument()
  })

  it('搜索关键字过滤依赖列表', () => {
    renderModal(true)
    const input = screen.getByPlaceholderText(TEXTS.licensesSearchPlaceholder)

    fireEvent.change(input, { target: { value: 'axios' } })

    // axios 应该出现
    expect(screen.getByText(/axios/i)).toBeInTheDocument()
    // fastapi 应该被过滤掉
    expect(screen.queryByText(/fastapi/i)).not.toBeInTheDocument()
  })

  it('按许可证类型搜索', () => {
    renderModal(true)
    const input = screen.getByPlaceholderText(TEXTS.licensesSearchPlaceholder)

    // 搜索 BSD-3-Clause：应返回 uvicorn、httpx、Jinja2、starlette、websockets
    fireEvent.change(input, { target: { value: 'BSD-3-Clause' } })

    expect(screen.getByText(/uvicorn/i)).toBeInTheDocument()
    // MIT 许可的 react 不应出现
    expect(screen.queryByText(/^react$/i)).not.toBeInTheDocument()
  })

  it('搜索无结果时展示空状态文案', () => {
    renderModal(true)
    const input = screen.getByPlaceholderText(TEXTS.licensesSearchPlaceholder)

    fireEvent.change(input, { target: { value: '不存在的依赖名xyz123' } })

    expect(screen.getByText(TEXTS.emptySearch)).toBeInTheDocument()
  })

  it('清空搜索后恢复全部列表', () => {
    renderModal(true)
    const input = screen.getByPlaceholderText(TEXTS.licensesSearchPlaceholder) as HTMLInputElement

    // 先过滤
    fireEvent.change(input, { target: { value: 'axios' } })
    expect(screen.queryByText(/fastapi/i)).not.toBeInTheDocument()

    // 清空
    fireEvent.change(input, { target: { value: '' } })
    expect(screen.getByText(/fastapi/i)).toBeInTheDocument()
  })
})
