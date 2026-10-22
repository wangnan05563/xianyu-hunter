/**
 * 抢单记录「演练单」筛选（T02673）
 *
 * 回归的缺陷：演练记录与真实记录混排，状态下拉没有「演练」入口。
 * 演练单不是订单状态：选项走独立的 type=dry_run 参数（status 白名单会拒绝
 * dry_run），URL 写 ?type=，与 ?status= 互斥（同一个下拉同时只表达一个维度）。
 */
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import type { OrderItem } from '../../../api/types'

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
  pending: 0, paid: 0, succeeded: 1, failed: 1, cancelled: 0, takeover: 0, total: 2,
}

function order(id: string, status: string, type: string): OrderItem {
  return {
    id, item_id: `i_${id}`, price: 99, status, type,
    created_at: '2026-10-21T00:00:00', confirmed_at: null,
  } as OrderItem
}

beforeAll(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
  Element.prototype.scrollIntoView = () => {}
})
afterAll(() => { vi.unstubAllGlobals() })

beforeEach(() => {
  localStorage.clear()
  listMock.mockReset()
  listMock.mockResolvedValue({
    items: [order('r1', 'succeeded', 'real'), order('d1', 'failed', 'dry_run')],
    count: 2, total: 2, stats: STATS, by_status: { succeeded: 1, failed: 1 },
  })
})

function renderAt(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Orders />
      <LocationProbe />
    </MemoryRouter>,
  )
}

// 与 ordersAlertDeepLink.test.tsx 同一套定位：antd Space 把每个子节点包进
// 独立的 .ant-space-item，标签的父节点里并没有下拉
function statusSelectRoot(): HTMLElement {
  let node: HTMLElement | null = screen.getByText('状态筛选：').parentElement
  while (node && !node.querySelector('.ant-select')) node = node.parentElement
  const root = node?.querySelector('.ant-select') as HTMLElement | null
  if (!root) throw new Error('未找到状态筛选下拉')
  return root
}

async function pickOption(label: string) {
  // 点击 .ant-select-selector 才会开下拉；选项在 body 门户里按类名找，
  // getByText(label) 会撞上表格行里的同名 Tag（如「已失败」）
  const selectEl = statusSelectRoot().querySelector('.ant-select-selector') as HTMLElement
  await userEvent.click(selectEl)
  const option = await waitFor(() => {
    const found = Array.from(document.querySelectorAll('.ant-select-item-option'))
      .filter((n) => n.textContent?.includes(label))
    if (!found.length) throw new Error(`下拉未出现「${label}」选项`)
    return found[0] as HTMLElement
  })
  await userEvent.click(option)
}

function lastCall(): Record<string, unknown> | undefined {
  return listMock.mock.calls.at(-1)?.[0] as Record<string, unknown> | undefined
}

describe('演练单筛选（T02673）', () => {
  it('选「演练单」：请求带 type=dry_run 且不带 status，URL 写 ?type=dry_run', async () => {
    renderAt('/orders')
    await waitFor(() => expect(listMock).toHaveBeenCalled())
    await pickOption('演练单')
    await waitFor(() => {
      const p = lastCall()
      expect(p).toMatchObject({ type: 'dry_run' })
      expect(p?.status).toBeUndefined()
    })
    expect(screen.getByTestId('location').textContent).toContain('type=dry_run')
    expect(screen.getByTestId('location').textContent).not.toContain('status=')
  })

  it('带 ?type=dry_run 落地：下拉显示「演练单」，请求带 type 参数', async () => {
    // 落地首查发生在 URL 同步 effect 之前，末次调用才是带筛选的那次
    renderAt('/orders?type=dry_run')
    await waitFor(() => {
      expect(lastCall()).toMatchObject({ type: 'dry_run' })
    })
    await waitFor(() => expect(document.querySelector('.ant-select-selection-item')?.getAttribute('title'))
      .toBe('演练单'))
  })

  it('从演练单切回普通状态：type 参数被清掉，status 正常回写', async () => {
    renderAt('/orders?type=dry_run')
    await waitFor(() => expect(lastCall()).toMatchObject({ type: 'dry_run' }))
    await pickOption('已失败')
    await waitFor(() => {
      const p = lastCall()
      expect(p).toMatchObject({ status: 'failed' })
      expect(p?.type).toBeUndefined()
    })
    expect(screen.getByTestId('location').textContent).toContain('status=failed')
    expect(screen.getByTestId('location').textContent).not.toContain('type=')
  })

  it('演练单视图下 allowClear 清空：两个参数都不再出现', async () => {
    renderAt('/orders?type=dry_run')
    await waitFor(() => expect(lastCall()).toMatchObject({ type: 'dry_run' }))
    const root = statusSelectRoot()
    await userEvent.hover(root)
    const clearIcon = root.querySelector('.ant-select-clear') as HTMLElement
    expect(clearIcon, 'allowClear 的清除按钮未出现').toBeTruthy()
    await userEvent.click(clearIcon)
    await waitFor(() => {
      const p = lastCall()
      expect(p?.status).toBeUndefined()
      expect(p?.type).toBeUndefined()
    })
  })
})
