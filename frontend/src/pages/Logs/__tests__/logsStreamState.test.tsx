/**
 * 实时日志流连接状态（T02680 / T02681）
 *
 * 三条回归：
 * 1. 点开实时流后、onopen 之前只能显示「连接中」，不得先弹「已开启」成功提示；
 * 2. 断流后进入「已断开」而不是退回「未开启」：已收到的日志保留并灰显，面板给「重新连接」；
 * 3. 断流不清暂停缓冲——暂停期间缓存的日志在重连/恢复后仍能取回。
 */
import { describe, it, expect, vi, beforeEach, beforeAll, afterAll } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { message } from 'antd'

const { listMock, searchMock } = vi.hoisted(() => ({ listMock: vi.fn(), searchMock: vi.fn() }))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const logApi = (actual as { logApi: Record<string, unknown> }).logApi
  return { ...actual, logApi: { ...logApi, list: listMock, search: searchMock } }
})

import Logs from '../Logs'

type AppEventHandler = (ev: { data: string }) => void

class FakeEventSource {
  static instances: FakeEventSource[] = []
  static get last() {
    return FakeEventSource.instances[FakeEventSource.instances.length - 1]
  }

  readonly url: string
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  private handlers: Record<string, AppEventHandler[]> = {}

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, cb: AppEventHandler) {
    ;(this.handlers[type] ||= []).push(cb)
  }

  close() {
    this.closed = true
  }

  emit(type: string, data: string) {
    ;(this.handlers[type] || []).forEach((cb) => cb({ data }))
  }
}

function renderLogs() {
  return render(
    <MemoryRouter initialEntries={['/logs']}>
      <Logs />
    </MemoryRouter>,
  )
}

async function openStream(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: /开启实时流/ }))
}

beforeAll(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterAll(() => {
  vi.unstubAllGlobals()
})

beforeEach(() => {
  FakeEventSource.instances = []
  listMock.mockReset().mockResolvedValue({
    items: [{ source: 'run.stdout.log', level: 'ERROR', lines: ['traceback ...'] }],
  })
  searchMock.mockReset().mockResolvedValue({ items: [], count: 0, total_estimate: 0, matched_levels: {}, matched_tags: {} })
})

describe('首帧前的连接中态（T02681）', () => {
  it('点开后先显示「连接中」，onopen 才弹成功并转「已连接」', async () => {
    const successSpy = vi.spyOn(message, 'success')
    successSpy.mockClear()
    const user = userEvent.setup()
    renderLogs()
    await openStream(user)

    expect(await screen.findByText('连接中')).toBeTruthy()
    expect(screen.getByText('正在连接日志流…')).toBeTruthy()
    expect(successSpy).not.toHaveBeenCalled()

    act(() => { FakeEventSource.last.onopen?.() })

    expect(await screen.findByText('已连接')).toBeTruthy()
    expect(successSpy).toHaveBeenCalledWith('实时日志流已连接')
    expect(screen.getByText('等待日志推送...')).toBeTruthy()
    successSpy.mockRestore()
  })

  it('首条 app_event 先到、onopen 后到也视为已连接', async () => {
    const user = userEvent.setup()
    renderLogs()
    await openStream(user)
    act(() => {
      FakeEventSource.last.emit('app_event', JSON.stringify({ level: 'info', message: '首帧日志' }))
    })
    expect(await screen.findByText('已连接')).toBeTruthy()
  })
})

describe('断流保留日志并可重连（T02680）', () => {
  it('断流后标「连接已断开」、日志灰显保留、给「重新连接」', async () => {
    const user = userEvent.setup()
    renderLogs()
    await openStream(user)
    act(() => { FakeEventSource.last.onopen?.() })
    act(() => {
      FakeEventSource.last.emit('app_event', JSON.stringify({ level: 'info', message: '断线前最后一条' }))
    })
    expect(await screen.findByText(/断线前最后一条/)).toBeTruthy()

    act(() => { FakeEventSource.last.onerror?.() })

    expect(await screen.findByText('连接已断开')).toBeTruthy()
    // 不再退回「未开启」：主开关变成「退出实时流」，原始日志面板不被顶回来
    expect(screen.getByRole('button', { name: /退出实时流/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /重新连接/ })).toBeTruthy()
    // 已收到的日志还在，但灰显标明不再更新
    const streamLogs = screen.getByTestId('stream-logs')
    expect(streamLogs.textContent).toContain('断线前最后一条')
    expect(streamLogs.style.opacity).toBe('0.55')
    expect(screen.queryByText('等待日志推送...')).toBeNull()
  })

  it('「重新连接」新建一条流，旧日志继续保留', async () => {
    const user = userEvent.setup()
    renderLogs()
    await openStream(user)
    act(() => { FakeEventSource.last.onopen?.() })
    act(() => {
      FakeEventSource.last.emit('app_event', JSON.stringify({ level: 'info', message: '第一次连接的日志' }))
    })
    act(() => { FakeEventSource.last.onerror?.() })
    const before = FakeEventSource.instances.length

    await user.click(await screen.findByRole('button', { name: /重新连接/ }))

    expect(FakeEventSource.instances.length).toBe(before + 1)
    expect(await screen.findByText('连接中')).toBeTruthy()
    expect(screen.getByTestId('stream-logs').textContent).toContain('第一次连接的日志')
  })

  it('断流不清暂停缓冲：恢复后暂停期间缓存的日志仍会出现', async () => {
    const user = userEvent.setup()
    renderLogs()
    await openStream(user)
    act(() => { FakeEventSource.last.onopen?.() })

    await user.click(screen.getByRole('button', { name: /暂停/ }))
    act(() => {
      FakeEventSource.last.emit('app_event', JSON.stringify({ level: 'info', message: '暂停期间到达' }))
    })
    expect(screen.queryByText(/暂停期间到达/)).toBeNull()

    act(() => { FakeEventSource.last.onerror?.() })
    expect(await screen.findByText('连接已断开')).toBeTruthy()
    // 暂停态未被 onerror 重置，缓冲也没有被清掉
    expect(screen.getByRole('button', { name: /恢复/ })).toBeTruthy()

    await user.click(screen.getByRole('button', { name: /恢复/ }))
    expect(await screen.findByText(/暂停期间到达/)).toBeTruthy()
  })
})
