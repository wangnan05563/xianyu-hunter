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
    download: { status: 'idle', total: 0, done: 0, message: '', installing: false },
    onCheck: vi.fn(),
    onCopy: vi.fn(),
    onUpdate: vi.fn(),
    onInstall: vi.fn(),
    ...overrides,
  }
  const onCheck = props.onCheck as ReturnType<typeof vi.fn>
  const onCopy = props.onCopy as ReturnType<typeof vi.fn>
  const onUpdate = props.onUpdate as ReturnType<typeof vi.fn>
  const onInstall = props.onInstall as ReturnType<typeof vi.fn>
  const utils = render(
    <ConfigProvider>
      <BrandCard {...props} />
    </ConfigProvider>,
  )
  return { ...utils, onCheck, onCopy, onUpdate, onInstall }
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

  it('newer 态：展示"立即更新"按钮并附带 latest 版本号，点击触发 onUpdate', () => {
    const { onUpdate } = renderCard({
      state: { kind: 'newer', url: 'https://example.com/v2.0.0', downloadUrl: 'https://github.com/x/releases/download/v2.0.0/setup.exe', latest: '2.0.0' },
    })
    // 立即更新按钮（TEXTS.updateInstallNow = '立即更新'）
    expect(screen.getByText(new RegExp(TEXTS.updateInstallNow))).toBeInTheDocument()
    expect(screen.getByText(/2\.0\.0/)).toBeInTheDocument()
    const btn = screen.getByRole('button', { name: new RegExp(TEXTS.updateInstallNow) })
    fireEvent.click(btn)
    expect(onUpdate).toHaveBeenCalledTimes(1)
  })

  it('newer 态 + 无 downloadUrl：仍展示"立即更新"，点击触发 onUpdate（由 hook 降级跳转 GitHub）', () => {
    const { onUpdate } = renderCard({
      state: { kind: 'newer', url: 'https://example.com/v2.0.0', downloadUrl: '', latest: '2.0.0' },
    })
    const btn = screen.getByRole('button', { name: new RegExp(TEXTS.updateInstallNow) })
    fireEvent.click(btn)
    expect(onUpdate).toHaveBeenCalledTimes(1)
  })

  it('下载中状态：展示进度条且安装按钮禁用', () => {
    renderCard({
      state: { kind: 'newer', url: '', downloadUrl: 'https://github.com/x/r.exe', latest: '2.0.0' },
      download: { status: 'downloading', total: 100, done: 40, message: '', installing: false },
    })
    expect(screen.getByText(TEXTS.updateDownloadProgress)).toBeInTheDocument()
    // 下载中时按钮文案为"下载中"，且 disabled（未下载完成不可触发安装）
    const installBtn = screen.getByRole('button', { name: new RegExp(TEXTS.updateDownloadProgress) })
    expect(installBtn).toBeDisabled()
  })

  it('下载完成状态：展示"安装更新"按钮，点击触发 onInstall', () => {
    const { onInstall } = renderCard({
      state: { kind: 'newer', url: '', downloadUrl: 'https://github.com/x/r.exe', latest: '2.0.0' },
      download: { status: 'done', total: 100, done: 100, message: '', installing: false },
    })
    const btn = screen.getByRole('button', { name: new RegExp(TEXTS.updateInstallConfirm) })
    expect(btn).toBeInTheDocument()
    fireEvent.click(btn)
    expect(onInstall).toHaveBeenCalledTimes(1)
  })

  it('下载失败状态：展示错误并可重试下载（触发 onUpdate）', () => {
    const { onUpdate } = renderCard({
      state: { kind: 'newer', url: '', downloadUrl: 'https://github.com/x/r.exe', latest: '2.0.0' },
      download: { status: 'error', total: 0, done: 0, message: '下载失败，请重试', installing: false },
    })
    expect(screen.getByText(/下载失败，请重试/)).toBeInTheDocument()
    const btn = screen.getByRole('button', { name: /下载失败/ })
    fireEvent.click(btn)
    expect(onUpdate).toHaveBeenCalledTimes(1)
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
