import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ConfigProvider } from 'antd'
import { BrandCard } from '../BrandCard'
import type { UpdateState } from '../useUpdateChecker'
import { TEXTS } from '../i18n'

// ConfigProvider 包装：BrandCard 内部依赖 theme.useToken()
function renderCard(overrides: Partial<Parameters<typeof BrandCard>[0]> = {}) {
  const props: Parameters<typeof BrandCard>[0] = {
    version: '1.2.3',
    buildDate: '2026-06-28',
    gitSha: 'abc1234',
    state: { kind: 'idle' } as UpdateState,
    onCheck: vi.fn(),
    onCopy: vi.fn(),
    ...overrides,
  }
  const onCheck = props.onCheck
  const onCopy = props.onCopy
  const utils = render(
    <ConfigProvider>
      <BrandCard {...props} />
    </ConfigProvider>,
  )
  return { ...utils, onCheck, onCopy }
}

describe('BrandCard', () => {
  it('渲染版本号与构建日期', () => {
    renderCard({ version: '1.2.3', buildDate: '2026-06-28' })
    // 版本号展示
    expect(screen.getByText(`${TEXTS.versionLabel}: 1.2.3`)).toBeInTheDocument()
    // 构建日期展示
    expect(screen.getByText(`${TEXTS.releasedOn} 2026-06-28`)).toBeInTheDocument()
  })

  it('git_sha 为 unknown 时不展示 @sha', () => {
    renderCard({ gitSha: 'unknown' })
    // 不应出现 @unknown 这种误导性展示
    expect(screen.queryByText(/@unknown/)).not.toBeInTheDocument()
  })

  it('git_sha 有效时展示 @sha', () => {
    renderCard({ gitSha: 'abc1234' })
    expect(screen.getByText('@abc1234')).toBeInTheDocument()
  })

  it('idle 态：展示"检查更新"按钮，点击触发 onCheck', () => {
    const { onCheck } = renderCard({ state: { kind: 'idle' } })
    const btn = screen.getByRole('button', { name: new RegExp(TEXTS.updateIdle) })
    expect(btn).toBeInTheDocument()
    fireEvent.click(btn)
    expect(onCheck).toHaveBeenCalledTimes(1)
  })

  it('loading 态：展示"检查中…"文案', () => {
    renderCard({ state: { kind: 'loading' } })
    expect(screen.getByText(TEXTS.updateLoading)).toBeInTheDocument()
  })

  it('latest 态：展示"已是最新"文案', () => {
    renderCard({ state: { kind: 'latest' } })
    expect(screen.getByText(TEXTS.updateLatest)).toBeInTheDocument()
  })

  it('newer 态：展示"有新版本"并附带 latest 版本号', () => {
    renderCard({
      state: { kind: 'newer', url: 'https://example.com/v2.0.0', latest: '2.0.0' },
    })
    expect(screen.getByText(new RegExp(TEXTS.updateNewer))).toBeInTheDocument()
    expect(screen.getByText(/2\.0\.0/)).toBeInTheDocument()
  })

  it('error 态（network）：展示"网络异常"文案', () => {
    renderCard({ state: { kind: 'error', reason: 'network' } })
    expect(screen.getByText(new RegExp(TEXTS.updateErrorNetwork))).toBeInTheDocument()
  })

  it('error 态（server）：展示"服务异常"文案', () => {
    renderCard({ state: { kind: 'error', reason: 'server' } })
    expect(screen.getByText(new RegExp(TEXTS.updateErrorServer))).toBeInTheDocument()
  })

  it('点击复制按钮触发 onCopy', () => {
    const { onCopy } = renderCard()
    // aria-label 定位复制按钮
    const copyBtn = screen.getByLabelText(TEXTS.copyAriaLabel)
    fireEvent.click(copyBtn)
    expect(onCopy).toHaveBeenCalledTimes(1)
  })
})
