import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { App as AntdApp, ConfigProvider } from 'antd'
import type { ReactNode } from 'react'
import { useUpdateChecker } from '../useUpdateChecker'
import { aboutApi } from '../../../api'

// Mock aboutApi：每个 case 单独设置实现
vi.mock('../../../api', () => ({
  aboutApi: {
    get: vi.fn(),
    checkUpdate: vi.fn(),
  },
}))

// AntdApp + ConfigProvider 包装：useUpdateChecker 内部依赖 App.useApp() 取 message
function wrapper({ children }: { children: ReactNode }) {
  return (
    <ConfigProvider>
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useUpdateChecker', () => {
  it('初始状态为 idle', () => {
    const { result } = renderHook(() => useUpdateChecker('1.0.0'), { wrapper })
    expect(result.current.state).toEqual({ kind: 'idle' })
  })

  it('检查更新：无新版本时进入 latest 态，3s 后自动回 idle', async () => {
    vi.mocked(aboutApi.checkUpdate).mockResolvedValue({
      current: '1.0.0',
      latest: '1.0.0',
      has_update: false,
      release_url: '',
      checked_at: '',
      source: 'local',
    })

    const { result } = renderHook(() => useUpdateChecker('1.0.0'), { wrapper })

    await act(async () => {
      await result.current.run()
    })

    expect(result.current.state).toEqual({ kind: 'latest' })

    // 3s 后应自动回到 idle
    act(() => {
      vi.advanceTimersByTime(3000)
    })

    expect(result.current.state).toEqual({ kind: 'idle' })
  })

  it('检查更新：有新版本时进入 newer 态并携带 url 和 latest', async () => {
    vi.mocked(aboutApi.checkUpdate).mockResolvedValue({
      current: '1.0.0',
      latest: '2.0.0',
      has_update: true,
      release_url: 'https://example.com/release/v2.0.0',
      checked_at: '',
      source: 'remote',
    })

    const { result } = renderHook(() => useUpdateChecker('1.0.0'), { wrapper })

    await act(async () => {
      await result.current.run()
    })

    expect(result.current.state).toEqual({
      kind: 'newer',
      url: 'https://example.com/release/v2.0.0',
      latest: '2.0.0',
      publishedAt: undefined,
    })
  })

  it('检查更新：newer 态携带 publishedAt 字段（来自 GitHub Releases）', async () => {
    vi.mocked(aboutApi.checkUpdate).mockResolvedValue({
      current: '1.0.0',
      latest: '2.0.0',
      has_update: true,
      release_url: 'https://github.com/wangnan05563/xianyu-hunter/releases/tag/v2.0.0',
      checked_at: '',
      source: 'remote',
      published_at: '2026-06-15T00:00:00Z',
    })

    const { result } = renderHook(() => useUpdateChecker('1.0.0'), { wrapper })

    await act(async () => {
      await result.current.run()
    })

    expect(result.current.state).toEqual({
      kind: 'newer',
      url: 'https://github.com/wangnan05563/xianyu-hunter/releases/tag/v2.0.0',
      latest: '2.0.0',
      publishedAt: '2026-06-15T00:00:00Z',
    })
  })

  it('检查更新：网络错误（无 response）归类为 network reason', async () => {
    // 模拟 axios 网络错误：没有 response 字段
    const networkErr = Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' })
    vi.mocked(aboutApi.checkUpdate).mockRejectedValue(networkErr)

    const { result } = renderHook(() => useUpdateChecker('1.0.0'), { wrapper })

    await act(async () => {
      await result.current.run()
    })

    expect(result.current.state).toEqual({ kind: 'error', reason: 'network' })
  })

  it('检查更新：服务端错误（有 response）归类为 server reason', async () => {
    // 模拟服务端 5xx 错误：带 response 字段
    const serverErr = Object.assign(new Error('Server Error'), {
      response: { status: 500 },
    })
    vi.mocked(aboutApi.checkUpdate).mockRejectedValue(serverErr)

    const { result } = renderHook(() => useUpdateChecker('1.0.0'), { wrapper })

    await act(async () => {
      await result.current.run()
    })

    expect(result.current.state).toEqual({ kind: 'error', reason: 'server' })
  })

  it('copy：剪贴板成功时调用 message.success', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })

    const { result } = renderHook(() => useUpdateChecker('1.2.3'), { wrapper })

    await act(async () => {
      await result.current.copy()
    })

    expect(writeText).toHaveBeenCalledWith('1.2.3')
  })

  it('copy：剪贴板拒绝时不抛错（降级提示）', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })

    const { result } = renderHook(() => useUpdateChecker('1.2.3'), { wrapper })

    // 不应抛出
    await expect(act(async () => {
      await result.current.copy()
    })).resolves.toBeUndefined()
  })

  it('H1: 进入 latest 态后卸载组件应清理 idle 定时器（不触发卸载后 setState）', async () => {
    vi.mocked(aboutApi.checkUpdate).mockResolvedValue({
      current: '1.0.0',
      latest: '1.0.0',
      has_update: false,
      release_url: '',
      checked_at: '',
      source: 'local',
    })

    // spy setTimeout / clearTimeout 以观测清理行为
    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout')
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')

    const { result, unmount } = renderHook(() => useUpdateChecker('1.0.0'), { wrapper })

    // 挂载时已注册若干 setTimeout（5s 自动检查 + 60 分钟 interval），
    // 清空 spy 调用记录，仅观测 run() 触发的 idle timer
    setTimeoutSpy.mockClear()
    clearTimeoutSpy.mockClear()

    await act(async () => {
      await result.current.run()
    })

    expect(result.current.state).toEqual({ kind: 'latest' })

    // 进入 latest 态后应注册一个 3s 的 idle 定时器
    // 注意：run() 内部不会再触发其它 setTimeout，所以最后一个就是 idle timer
    expect(setTimeoutSpy).toHaveBeenCalled()
    const idleTimer = setTimeoutSpy.mock.results.at(-1)?.value as ReturnType<typeof setTimeout> | undefined
    expect(idleTimer).toBeTruthy()

    // 卸载组件：useEffect 清理函数应调用 clearTimeout 清掉 idle 定时器
    unmount()

    expect(clearTimeoutSpy).toHaveBeenCalledWith(idleTimer)

    // 推进 3s 定时器：因已被清理，不应有任何 setState 副作用
    act(() => {
      vi.advanceTimersByTime(3000)
    })

    // 卸载后 result.current 仍保持卸载前的 latest 态（未回退到 idle 即说明 timer 没生效）
    expect(result.current.state).toEqual({ kind: 'latest' })

    setTimeoutSpy.mockRestore()
    clearTimeoutSpy.mockRestore()
  })

  it('自动检查：挂载后 5s 自动触发一次检查', async () => {
    vi.mocked(aboutApi.checkUpdate).mockResolvedValue({
      current: '1.0.0',
      latest: '1.0.0',
      has_update: false,
      release_url: '',
      checked_at: '',
      source: 'local',
    })

    renderHook(() => useUpdateChecker('1.0.0'), { wrapper })

    // 挂载后立即检查：未发起请求（5s 延迟未到）
    expect(aboutApi.checkUpdate).not.toHaveBeenCalled()

    // 推进 5s：应自动触发首次检查
    await act(async () => {
      vi.advanceTimersByTime(5000)
      // 让微任务（Promise 解析）落地
      await vi.mocked(aboutApi.checkUpdate).mock.results[0]?.value
    })

    expect(aboutApi.checkUpdate).toHaveBeenCalledTimes(1)
  })

  it('自动检查：60 分钟后再次触发检查', async () => {
    vi.mocked(aboutApi.checkUpdate).mockResolvedValue({
      current: '1.0.0',
      latest: '1.0.0',
      has_update: false,
      release_url: '',
      checked_at: '',
      source: 'local',
    })

    renderHook(() => useUpdateChecker('1.0.0'), { wrapper })

    // 推进 5s：首次自动检查
    await act(async () => {
      vi.advanceTimersByTime(5000)
      await vi.mocked(aboutApi.checkUpdate).mock.results[0]?.value
    })
    expect(aboutApi.checkUpdate).toHaveBeenCalledTimes(1)

    // 推进 60 分钟：第二次自动检查
    await act(async () => {
      vi.advanceTimersByTime(60 * 60 * 1000)
      await vi.mocked(aboutApi.checkUpdate).mock.results[1]?.value
    })
    expect(aboutApi.checkUpdate).toHaveBeenCalledTimes(2)
  })

  it('卸载时清理挂载延迟 timer 和自动检查 interval（不触发后续检查）', async () => {
    vi.mocked(aboutApi.checkUpdate).mockResolvedValue({
      current: '1.0.0',
      latest: '1.0.0',
      has_update: false,
      release_url: '',
      checked_at: '',
      source: 'local',
    })

    const { unmount } = renderHook(() => useUpdateChecker('1.0.0'), { wrapper })

    // 卸载前未发起检查
    expect(aboutApi.checkUpdate).not.toHaveBeenCalled()

    unmount()

    // 推进 5s + 60 分钟：因 timer 已清理，不应有任何检查
    await act(async () => {
      vi.advanceTimersByTime(5000 + 60 * 60 * 1000)
    })

    expect(aboutApi.checkUpdate).not.toHaveBeenCalled()
  })

  it('并发抑制：检查进行中再次调用 run 应被跳过', async () => {
    // 用一个可控的 Promise 模拟未完成的请求
    let resolveCheck!: (v: unknown) => void
    vi.mocked(aboutApi.checkUpdate).mockImplementation(() => {
      return new Promise((resolve) => {
        resolveCheck = resolve
      }) as Promise<any>
    })

    const { result } = renderHook(() => useUpdateChecker('1.0.0'), { wrapper })

    // 第一次调用：进入 loading，请求未完成
    let firstCall: Promise<void>
    act(() => {
      firstCall = result.current.run()
    })
    expect(result.current.state).toEqual({ kind: 'loading' })

    // 第二次调用：因 isCheckingRef=true，应被跳过
    await act(async () => {
      await result.current.run()
    })
    // 仍只有 1 次请求
    expect(aboutApi.checkUpdate).toHaveBeenCalledTimes(1)

    // 完成第一次请求
    await act(async () => {
      resolveCheck({
        current: '1.0.0', latest: '1.0.0', has_update: false,
        release_url: '', checked_at: '', source: 'local',
      })
      await firstCall!
    })

    expect(result.current.state).toEqual({ kind: 'latest' })
  })
})
