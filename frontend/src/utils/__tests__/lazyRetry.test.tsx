import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { Suspense } from 'react'
import { lazyRetry, LazyErrorBoundary, isChunkLoadError } from '../lazyRetry'

describe('isChunkLoadError', () => {
  it('识别 Vite 动态导入失败错误', () => {
    const err = new Error('Failed to fetch dynamically imported module: /assets/foo.js')
    expect(isChunkLoadError(err)).toBe(true)
  })

  it('识别 Webpack ChunkLoadError', () => {
    const err = new Error('Loading chunk 42 failed.')
    expect(isChunkLoadError(err)).toBe(true)
  })

  it('非 chunk 加载错误返回 false', () => {
    const err = new Error('TypeError: Cannot read properties of undefined')
    expect(isChunkLoadError(err)).toBe(false)
  })

  it('非 Error 对象返回 false', () => {
    expect(isChunkLoadError('string error')).toBe(false)
    expect(isChunkLoadError(null)).toBe(false)
    expect(isChunkLoadError(undefined)).toBe(false)
  })
})

describe('lazyRetry', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('正常加载组件', async () => {
    const LazyComp = lazyRetry(() => Promise.resolve({
      default: () => <div data-testid="loaded">加载成功</div>,
    }))
    render(
      <Suspense fallback={<div>loading</div>}>
        <LazyComp />
      </Suspense>,
    )
    await waitFor(() => {
      expect(screen.getByTestId('loaded')).toBeInTheDocument()
    })
  })

  it('chunk 加载失败时自动重试', async () => {
    let attempts = 0
    const factory = () => {
      attempts++
      if (attempts < 2) {
        // 第一次失败，第二次成功
        return Promise.reject(new Error('Failed to fetch dynamically imported module: /assets/foo.js'))
      }
      return Promise.resolve({
        default: () => <div data-testid="loaded-after-retry">重试成功</div>,
      })
    }
    const LazyComp = lazyRetry(factory, { retries: 3 })
    render(
      <Suspense fallback={<div>loading</div>}>
        <LazyComp />
      </Suspense>,
    )
    await waitFor(() => {
      expect(screen.getByTestId('loaded-after-retry')).toBeInTheDocument()
    })
    expect(attempts).toBe(2)
  })

  it('非 chunk 错误不重试，直接抛出', async () => {
    let attempts = 0
    const factory = () => {
      attempts++
      return Promise.reject(new Error('SyntaxError: unexpected token'))
    }
    const LazyComp = lazyRetry(factory, { retries: 3 })
    render(
      <LazyErrorBoundary>
        <Suspense fallback={<div>loading</div>}>
          <LazyComp />
        </Suspense>
      </LazyErrorBoundary>,
    )
    // 等待错误边界捕获
    await waitFor(() => {
      expect(screen.getByText('页面加载失败，请重试。')).toBeInTheDocument()
    })
    // 非 chunk 错误不应重试
    expect(attempts).toBe(1)
  })
})

describe('LazyErrorBoundary', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('正常渲染子组件', () => {
    render(
      <LazyErrorBoundary>
        <div data-testid="child">正常</div>
      </LazyErrorBoundary>,
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })

  it('捕获错误后显示兜底界面', () => {
    function Bomb() {
      throw new Error('boom')
    }
    render(
      <LazyErrorBoundary>
        <Bomb />
      </LazyErrorBoundary>,
    )
    expect(screen.getByText('页面加载失败，请重试。')).toBeInTheDocument()
    expect(screen.getByText('刷新页面')).toBeInTheDocument()
  })

  it('resetKey 变化时重置错误状态', () => {
    function Bomb() {
      throw new Error('boom')
    }
    function Wrapper({ resetKey }: { resetKey: string }) {
      return (
        <LazyErrorBoundary resetKey={resetKey}>
          <Bomb />
        </LazyErrorBoundary>
      )
    }
    const { rerender } = render(<Wrapper resetKey="a" />)
    expect(screen.getByText('页面加载失败，请重试。')).toBeInTheDocument()

    rerender(<Wrapper resetKey="b" />)
    // resetKey 变化后尝试重置，但 Bomb 仍抛错，所以会再次显示错误界面
    expect(screen.getByText('页面加载失败，请重试。')).toBeInTheDocument()
  })
})
