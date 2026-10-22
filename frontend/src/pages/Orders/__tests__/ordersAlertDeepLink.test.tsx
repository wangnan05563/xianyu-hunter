/**
 * 抢单记录页读取告警深链（T02620）
 *
 * 回归的缺陷：抽屉/雷达的跳转只到「页面级」，落地后看不出是哪一条异常——
 * 因为本页历史上只读 ?ref=，不读 ?status=，抽屉带过来的筛选参数被静默忽略。
 * 这里用真实挂载（MemoryRouter + 初始 URL）断言「URL 参数 → 筛选状态 → 请求参数」这条链。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import type { OrderItem } from '../../../api/types'

// 把当前 location.search 打进 DOM，用于断言「筛选变更有没有回写 URL」
function LocationProbe() {
  const { search } = useLocation()
  return <span data-testid="location">{search}</span>
}

class FakeEventSource {
  constructor(public url: string) {}
  addEventListener() {}
  close() {}
}

const { listMock } = vi.hoisted(() => ({ listMock: vi.fn() }))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const orderApi = (actual as { orderApi: Record<string, unknown> }).orderApi
  return { ...actual, orderApi: { ...orderApi, list: listMock } }
})

import Orders from '../Orders'

const STATS = {
  pending: 0, paid: 0, succeeded: 0, failed: 1, cancelled: 0, takeover: 0, total: 1,
}

function order(id: string, status: string): OrderItem {
  return {
    id, item_id: `i_${id}`, price: 99, status,
    created_at: '2026-10-21T00:00:00', confirmed_at: null,
  }
}

beforeAll(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
  // jsdom 没实现 scrollIntoView：命中 ref 定位后本页会滚动该行，缺省实现会抛未捕获异常
  Element.prototype.scrollIntoView = () => {}
})
afterAll(() => { vi.unstubAllGlobals() })

beforeEach(() => {
  localStorage.clear()
  listMock.mockReset()
  listMock.mockResolvedValue({
    items: [order('o1', 'failed')], count: 1, total: 1, stats: STATS, by_status: { failed: 1 },
  })
})

function renderAt(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Orders />
    </MemoryRouter>,
  )
}

describe('?status= 驱动状态筛选', () => {
  it('带 ?status=failed&ref=o1 落地：请求带 status=failed，下拉显示「已失败」', async () => {
    renderAt('/orders?status=failed&ref=o1')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(listMock.mock.calls[0][0]).toMatchObject({ status: 'failed' })
    // 筛选控件必须可见地把「已按告警筛过」表达出来，否则用户仍以为看的是全量列表
    await waitFor(() => expect(document.querySelector('.ant-select-selection-item')?.getAttribute('title'))
      .toBe('已失败'))
  })

  it('超时告警的 pending_pay 同样被读取（后端超时口径）', async () => {
    renderAt('/orders?status=pending_pay&ref=o1')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(listMock.mock.calls[0][0]).toMatchObject({ status: 'pending_pay' })
  })

  it('脏 status 值降级为不筛选，不进入请求参数', async () => {
    renderAt('/orders?status=%3Cscript%3E')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(listMock.mock.calls[0][0].status).toBeUndefined()
  })

  it('无 ?status= 时保持原行为：不带筛选', async () => {
    renderAt('/orders')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    expect(listMock.mock.calls[0][0].status).toBeUndefined()
  })
})

// T02831：T02620 只做了「URL → 筛选」的读端。手动把下拉改成别的值之后 URL 不动，
// 于是页面上是「全部」、链接还是 failed，刷新就被重新打回「已失败」；
// 带 ?ref= 进来时更要紧——回写不能顺手把 ref 参数擦了，否则定位提示当场消失。
// 从「状态筛选：」这个标签往上找到包含下拉的那一层：antd Space 会把每个子节点
// 包进独立的 .ant-space-item，标签的父节点里并没有下拉；落地时若带着 ?status=failed，
// 占位符「全部状态」也不在 DOM 里，按占位符找会自己把自己绊倒
function statusSelectRoot(): HTMLElement {
  let node: HTMLElement | null = screen.getByText('状态筛选：').parentElement
  while (node && !node.querySelector('.ant-select')) node = node.parentElement
  const root = node?.querySelector('.ant-select') as HTMLElement | null
  if (!root) throw new Error('未找到状态筛选下拉')
  return root
}

describe('手动改状态筛选会回写 URL（T02831）', () => {
  function renderWithLocation(entry: string) {
    return render(
      <MemoryRouter initialEntries={[entry]}>
        <Orders />
        <LocationProbe />
      </MemoryRouter>,
    )
  }

  it('选「已成功」后 URL 跟上 status=succeeded，且 ref 参数保留', async () => {
    renderWithLocation('/orders?status=failed&ref=o1')
    // 等下拉把「已失败」渲染出来再操作：默认 mock 返回的是 failed 单，
    // 页面上没有「接管」按钮，用按钮等挂载会把两条用例拖成超时假失败
    await waitFor(() => expect(
      document.querySelector('.ant-select-selection-item')?.getAttribute('title'))
      .toBe('已失败'))

    const selectEl = statusSelectRoot().querySelector('.ant-select-selector') as HTMLElement
    await userEvent.click(selectEl)
    const option = await waitFor(() => {
      const found = Array.from(document.querySelectorAll('.ant-select-item-option'))
        .filter((n) => n.textContent?.includes('已成功'))
      if (!found.length) throw new Error('下拉未出现「已成功」选项')
      return found[0] as HTMLElement
    })
    await userEvent.click(option)

    const probe = screen.getByTestId('location')
    await waitFor(() => expect(probe.textContent).toContain('status=succeeded'))
    expect(probe.textContent).toContain('ref=o1')
    // 请求侧也必须跟着改，否则「URL 写了但列表还是旧的」是另一种假回执
    await waitFor(() => {
      const last = listMock.mock.calls.at(-1)?.[0] as Record<string, unknown> | undefined
      expect(last?.status).toBe('succeeded')
    })
  })

  it('点 allowClear 清空筛选时删除 status 键，不留下 status=undefined', async () => {
    renderWithLocation('/orders?status=failed&ref=o1')
    // 等下拉把「已失败」渲染出来再操作：默认 mock 返回的是 failed 单，
    // 页面上没有「接管」按钮，用按钮等挂载会把两条用例拖成超时假失败
    await waitFor(() => expect(
      document.querySelector('.ant-select-selection-item')?.getAttribute('title'))
      .toBe('已失败'))

    const selectRoot = statusSelectRoot()
    await userEvent.hover(selectRoot)
    const clear = selectRoot.querySelector('.ant-select-clear') as HTMLElement
    expect(clear, 'allowClear 的清除按钮未出现').toBeTruthy()
    await userEvent.click(clear)

    const probe = screen.getByTestId('location')
    await waitFor(() => expect(probe.textContent).not.toContain('status='))
    expect(probe.textContent).toContain('ref=o1')
  })
})
