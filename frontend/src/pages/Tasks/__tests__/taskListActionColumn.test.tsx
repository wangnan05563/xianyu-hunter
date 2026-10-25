// T02651：任务列表表格「操作」列收纳 + 可跳转 Tag 的可点击暗示
// 工单现象：6 个元素（编辑/启动·暂停/停止/复制/更多/删除）常驻一列，叠 9 列数据后
// 窄屏要横向滚动才点到删除；采集周期 Tag 能点却没有任何链接暗示。
// 这里钉住三件事：
// 1) 常驻只剩高频动作（编辑 + 启动/暂停 + 更多），复制/停止/删除收进同一个下拉；
// 2) 收进菜单的危险项仍有二次确认，且确认文案带上任务名（菜单脱离了行上下文）；
// 3) 采集周期 Tag 带链接态样式与动作提示，点击真的跳到编辑页。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const apiMocks = vi.hoisted(() => ({
  list: vi.fn(),
  options: vi.fn(),
  count: vi.fn(),
  configGet: vi.fn(),
  aiConfig: vi.fn(),
  del: vi.fn(),
  stop: vi.fn(),
  start: vi.fn(),
}))

vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  const a = actual as Record<string, Record<string, unknown>>
  return {
    ...actual,
    taskApi: { ...a.taskApi, list: apiMocks.list, options: apiMocks.options, delete: apiMocks.del, stop: apiMocks.stop, start: apiMocks.start },
    taskLinkApi: { ...a.taskLinkApi, count: apiMocks.count },
    configApi: { ...a.configApi, get: apiMocks.configGet },
    aiApi: { ...a.aiApi, getConfig: apiMocks.aiConfig },
  }
})

import TaskList from '../TaskList'

const ROWS = [
  { id: 't1', name: '运行中的任务', keyword: 'iPhone', mode: 'keyword', status: 'running', interval_seconds: 60, created_at: '2026-01-01T00:00:00' },
  { id: 't2', name: '已停止的任务', keyword: 'Switch', mode: 'keyword', status: 'stopped', interval_seconds: 120, created_at: '2026-01-01T00:00:00' },
]

// 按钮可访问名带图标前缀，且 antd 会在两字中文按钮里插一个空格（「编 辑」），
// 因此按「去掉空白后的尾缀」匹配：既避开工具栏「启动本页」，也区别于菜单项「删除任务」。
const bySuffix = (suffix: string) => (name: string) => name.replace(/\s/g, '').endsWith(suffix)

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/tasks']}>
      <Routes>
        <Route path="/tasks" element={<TaskList />} />
        <Route path="*" element={<div>任务编辑页</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  Object.values(apiMocks).forEach((m) => m.mockReset())
  localStorage.clear()
  apiMocks.list.mockResolvedValue({ items: ROWS, total: ROWS.length })
  apiMocks.options.mockResolvedValue({ items: [], count: 0 })
  apiMocks.count.mockResolvedValue({ total: 0 })
  apiMocks.configGet.mockResolvedValue({ task_scheduler: { auto_search_enabled: false } })
  apiMocks.aiConfig.mockResolvedValue({ ai_enabled: true })
  apiMocks.del.mockResolvedValue({ ok: true })
  apiMocks.stop.mockResolvedValue({ ok: true })
  apiMocks.start.mockResolvedValue({ ok: true })
})

describe('操作列收纳：只留高频动作常驻', () => {
  it('编辑 + 启动/暂停常驻，复制/停止/删除不再各占一个按钮', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('运行中的任务')).toBeInTheDocument())

    expect(screen.getAllByRole('button', { name: bySuffix('编辑') })).toHaveLength(2)
    expect(screen.getByRole('button', { name: bySuffix('暂停') })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: bySuffix('启动') })).toBeInTheDocument()
    expect(screen.getAllByLabelText('更多操作')).toHaveLength(2)

    // 收纳后这些动作只能出现在下拉菜单里，不应再以行内按钮常驻
    expect(screen.queryByRole('button', { name: bySuffix('复制') })).toBeNull()
    expect(screen.queryByRole('button', { name: bySuffix('停止') })).toBeNull()
    expect(screen.queryByRole('button', { name: bySuffix('删除') })).toBeNull()
  })

  it('操作列钉右：本表列合计宽于可视区，不固定就要横向滚到视口外才点得到删除', async () => {
    const { container } = renderPage()
    await waitFor(() => expect(screen.getByText('运行中的任务')).toBeInTheDocument())

    // 真机实测（T02651）：1440 档可用宽度 1112px、11 列合计 1524px，
    // 未 fixed 时操作整列落在 x=1621（视口之外）。jsdom 量不到坐标，
    // 因此钉的是 antd 由列配置直接产出的 fix-right 类名——它与 scroll.x 同时生效才算钉住。
    const fixedHead = container.querySelector('th.ant-table-cell-fix-right')
    expect(fixedHead?.textContent).toContain('操作')
    // 表头 1 个 + 每行 1 个钉右单元格（去掉 fixed 后这里只剩普通 th，计数会掉到 0）
    expect(container.querySelectorAll('.ant-table-cell-fix-right').length).toBe(3)
  })

  it('「更多」菜单按状态给出危险项：运行中可停止，已停止只有删除', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('运行中的任务')).toBeInTheDocument())

    fireEvent.click(screen.getAllByLabelText('更多操作')[0])
    expect(await screen.findByText('停止任务')).toBeInTheDocument()
    expect(screen.getByText('删除任务')).toBeInTheDocument()
    expect(screen.getByText('复制为新任务')).toBeInTheDocument()
    expect(screen.getByText('另存为模板')).toBeInTheDocument()
  })

  it('菜单里的删除仍有二次确认，且确认文案带任务名', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('已停止的任务')).toBeInTheDocument())

    // 第二行（已停止）：只需删掉该任务，没有停止项
    fireEvent.click(screen.getAllByLabelText('更多操作')[1])
    await screen.findByText('删除任务')
    expect(screen.queryByText('停止任务')).toBeNull()
    fireEvent.click(screen.getByText('删除任务'))

    // antd 会把确认标题同时渲染到 aria 关联节点上，因此用 getAllByText 而不是 getByText
    await waitFor(() => expect(screen.getAllByText('确认删除该任务？').length).toBeGreaterThan(0))
    // 菜单脱离了行上下文，确认框必须能核对对象
    await waitFor(() => expect(screen.getAllByText(/已停止的任务——删除后不可恢复/).length).toBeGreaterThan(0))

    fireEvent.click(screen.getByRole('button', { name: bySuffix('删除') }))
    await waitFor(() => expect(apiMocks.del).toHaveBeenCalledWith('t2'))
  })
})

describe('采集周期 Tag 的可点击暗示', () => {
  it('带链接态 class 与动作提示，点击跳到该任务编辑页', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('运行中的任务')).toBeInTheDocument())

    const tag = screen.getByText('⏱ 60秒')
    expect(tag.className).toContain('xh-clickable-tag')
    expect(tag.getAttribute('role')).toBe('button')
    // 提示文案要说清「点了会怎样」，而不是只重复周期值（工单第 2 条）
    fireEvent.mouseOver(tag)
    await waitFor(() => expect(screen.getAllByText('点击编辑采集周期').length).toBeGreaterThan(0))

    fireEvent.click(tag)
    await waitFor(() => expect(screen.getByText('任务编辑页')).toBeInTheDocument())
  })

  it('样式表真的给出 hover/focus 的链接色与下划线（光有 cursor 不算暗示）', () => {
    const css = readFileSync(resolve(__dirname, '../../../index.css'), 'utf-8')
    const base = css.match(/\.xh-clickable-tag\s*\{[^}]*\}/)?.[0] ?? ''
    const hover = css.match(/\.xh-clickable-tag:hover[^{]*\{[^}]*\}/)?.[0] ?? ''
    expect(base).toContain('cursor: pointer')
    expect(base).toMatch(/color:\s*#1677ff/)
    expect(hover).toContain('text-decoration: underline')
  })

  it('cron 任务的 Tag 提示里同时保留 cron 表达式与可点击说明', async () => {
    apiMocks.list.mockResolvedValue({
      items: [{ ...ROWS[0], use_cron: true, cron: '*/10 * * * *' }],
      total: 1,
    })
    renderPage()
    const tag = await screen.findByText(/📅 \*\/10 \* \* \* \*/)
    fireEvent.mouseOver(tag)
    await waitFor(() => expect(
      screen.getAllByText((content) => content.includes('点击编辑采集周期 · cron:')).length,
    ).toBeGreaterThan(0))
  })
})
