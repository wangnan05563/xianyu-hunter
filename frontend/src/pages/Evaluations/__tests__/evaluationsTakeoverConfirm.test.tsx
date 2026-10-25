// frontend/src/pages/Evaluations/__tests__/evaluationsTakeoverConfirm.test.tsx
//
// T02671：评估页 fixed:'right' 操作列里的 Popconfirm 浮层持续重算位置
// （大表 + 横向滚动时确认框闪烁，Playwright 普通 click 报 element is not stable）。
// 修复是把确认换成 App 上下文的 modal.confirm——居中挂载、不跟触发点定位。
//
// 这里做真实渲染验证，因为「弹层锚在哪里」是本单的全部争点，源码扫描证明不了：
// 断言 ①确认前不下单（危险动作的语义没被换载体换掉）②对话框不是固定列单元格的后代
// （这才是抖动的根因）③列里不再出现 Popconfirm。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen, waitFor, within, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App, Table } from 'antd'
import { useEvalColumns } from '../hooks/useEvalColumns'
import type { EvalItem } from '../../../api'

// useEvalColumns 内部会经 useAIEnabled 拉 /api/ai/config；桩掉，避免 jsdom 发真实请求
vi.mock('../../../api', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return {
    ...actual,
    aiApi: { getConfig: vi.fn(() => Promise.resolve({ ai_enabled: true })) },
  }
})

const takeover = vi.fn(() => Promise.resolve())

// 一行「可抢单」的数据：评分高于阈值、无订单、未售 → 操作列渲染抢单按钮
const ROW: EvalItem = {
  item_id: '8800112233',
  task_id: 't093c1439',
  created_at: '2026-10-20T01:02:03+00:00',
  payload: {
    score: 88,
    risk_level: 'low',
    item_title: '联想笔记本内存 DDR4 3200 32G',
    item_price: 699,
    seller_nick: 'seller_a',
    order_status: null,
    is_sold: false,
  },
}

function Harness() {
  const columns = useEvalColumns({
    autoBuyScore: 70,
    passScore: 60,
    collecting: {},
    feedbackSubmitting: {},
    manualTaking: {},
    onAIEval: vi.fn(),
    onDeepAnalyze: vi.fn(),
    onCollectOfficial: vi.fn(),
    onFeedback: vi.fn(),
    onManualTakeover: takeover,
    onTitleClick: vi.fn(),
  })
  return (
    <Table
      columns={columns}
      dataSource={[ROW]}
      rowKey="item_id"
      scroll={{ x: 1800 }}
      pagination={false}
    />
  )
}

const wrap = () => render(<App><Harness /></App>)

/** 固定右列的**单元格**（不是同名的 th），以及其中的抢单按钮
 * （图标按钮无可访问名，只能按列定位——这正是本单的问题现场） */
const fixedActionCell = () => {
  const cell = document.querySelector('.ant-table-tbody td.ant-table-cell-fix-right')
  if (!cell) throw new Error('固定右列单元格不见了')
  return cell
}
const takeoverButton = () => {
  const btn = fixedActionCell().querySelector('button')
  if (!btn) throw new Error('固定列里没找到抢单按钮')
  return btn
}

afterEach(() => {
  cleanup()
  takeover.mockClear()
})

// 模态框会同时渲染 aria-hidden 的标题副本（.ant-modal-title 与 .ant-modal-confirm-title），
// 所以标题按选择器取，正文与按钮一律限定在对话框容器内，避免撞上 a11y 副本
const confirmTitle = () =>
  screen.findByText('确认手动抢单？', { selector: '.ant-modal-confirm-title' })

const confirmDialog = async () => {
  await confirmTitle()
  const box = document.querySelector('.ant-modal-confirm')
  if (!box) throw new Error('确认对话框不见了')
  return box as HTMLElement
}

describe('评估页抢单确认改走 modal（T02671）', () => {
  it('点抢单按钮只弹确认，确认之前绝不下单', async () => {
    wrap()
    await userEvent.click(takeoverButton())

    const box = await confirmDialog()
    expect(takeover).not.toHaveBeenCalled()
    // 四要素必须在：价格 / 评分 / 自动抢单阈值 / 会提交真实订单
    expect(within(box).getByText(/价格：¥699/)).toBeTruthy()
    expect(within(box).getByText(/评分：88（自动抢单阈值 70）/)).toBeTruthy()
    expect(within(box).getByText(/真实订单/)).toBeTruthy()
  }, 20_000)

  it('确认框不挂在表格子树内——这正是浮层抖动的根因', async () => {
    wrap()
    await userEvent.click(takeoverButton())

    const box = await confirmDialog()
    // 不变量是「不挂在任何表格单元格里」，不只是固定列那一格：
    // 挂在表头的 fix-right th 上，横向滚动时同样会被 Trigger 重算位置（探针 M3 实测）
    const table = document.querySelector('.ant-table-container')
    if (!table) throw new Error('没渲染出表格，断言无从谈起')
    expect(table.contains(box)).toBe(false)
    expect(fixedActionCell().contains(box)).toBe(false)
    expect(document.body.contains(box)).toBe(true)
    // 列内不再残留 Popconfirm 浮层
    expect(document.querySelector('.ant-popconfirm')).toBeNull()
  }, 20_000)

  it('点「取消」关闭确认且不下单', async () => {
    wrap()
    await userEvent.click(takeoverButton())
    const box = await confirmDialog()

    // antd 给两字按钮插了全角空格（「取 消」），所以名称按可带空格的形状匹配
    await userEvent.click(within(box).getByRole('button', { name: /^取\s?消$/ }))
    // jsdom 不跑完过渡（对话框一直停在 leave-active），所以断言「进入关闭流程」而非「已从 DOM 移除」
    await waitFor(() => expect(box.className).toContain('ant-zoom-leave'))
    expect(takeover).not.toHaveBeenCalled()
  }, 20_000)

  it('点「确认抢单」才下单，且带的是这一行', async () => {
    wrap()
    await userEvent.click(takeoverButton())
    const box = await confirmDialog()

    await userEvent.click(within(box).getByRole('button', { name: '确认抢单' }))
    await waitFor(() => expect(takeover).toHaveBeenCalledTimes(1))
    expect(takeover.mock.calls[0]?.[0]).toMatchObject({ item_id: '8800112233' })
  }, 20_000)

  it('确认按钮是危险样式（danger），与「提交真实订单」的后果相称', async () => {
    wrap()
    await userEvent.click(takeoverButton())
    const box = await confirmDialog()
    const ok = within(box).getByRole('button', { name: '确认抢单' })
    expect(ok.className).toContain('ant-btn-dangerous')
  }, 20_000)

  it('载体换掉后，源码里操作列不再引 Popconfirm', () => {
    const src = readFileSync(resolve(__dirname, '../hooks/useEvalColumns.tsx'), 'utf-8')
    expect(src).not.toContain('<Popconfirm')
    expect(src.match(/^import \{[^}]*\} from 'antd'/m)?.[0]).not.toContain('Popconfirm')
    expect(src).toContain('const { modal } = App.useApp()')
  })
})
