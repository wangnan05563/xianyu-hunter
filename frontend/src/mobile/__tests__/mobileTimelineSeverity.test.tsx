// T02683 收尾：移动端时间线的严重度 Tag 原先只认 warn/err，
// events.level 归一为小写全词后整段判定失效（全部落回「事件」蓝色）。
// 这里用规范值 warning/error/info 各一条，钉住配色与文案。
import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { App } from 'antd'

const { listMock } = vi.hoisted(() => ({ listMock: vi.fn() }))

vi.mock('../../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api')>()
  return {
    ...actual,
    timelineApi: { ...actual.timelineApi, list: listMock },
  }
})

import MobileTimeline from '../pages/Timeline'

const ENTRIES = [
  {
    _kind: 'event',
    _ts: '2026-10-19T10:00:00',
    id: '1',
    type: 'eval.failed',
    level: 'warning',
    title: '价格偏离预警',
    payload: { message: '价格偏离详情' },
  },
  {
    _kind: 'event',
    _ts: '2026-10-19T10:00:01',
    id: '2',
    type: 'system.error',
    level: 'error',
    title: '数据库连接失败',
    payload: { message: '连接失败详情' },
  },
  {
    _kind: 'event',
    _ts: '2026-10-19T10:00:02',
    id: '3',
    type: 'task.started',
    level: 'info',
    title: '开始搜索',
    payload: { message: '搜索已启动' },
  },
]

function renderTimeline() {
  return render(
    <MemoryRouter initialEntries={['/m/timeline']}>
      <App>
        <MobileTimeline />
      </App>
    </MemoryRouter>,
  )
}

/** 取某条事件卡片内的严重度 Tag：只按文案找会放过「接错行」 */
function tagOf(title: string): HTMLElement {
  const card = screen.getByText(title).closest('.ant-card') as HTMLElement
  return within(card).getByText(/^(警告|错误|事件)$/)
}

describe('移动端时间线严重度（T02683）', () => {
  it('warning / error 走规范词着色，info 保持默认蓝色', async () => {
    listMock.mockResolvedValue({ items: ENTRIES })
    renderTimeline()

    await screen.findByText('价格偏离预警')
    expect(tagOf('价格偏离预警')).toHaveClass('ant-tag-orange')
    expect(tagOf('数据库连接失败')).toHaveClass('ant-tag-red')
    expect(tagOf('开始搜索')).toHaveClass('ant-tag-blue')
  })

  it('旧缩写不再被当成严重度（回退后这条会红）', async () => {
    listMock.mockResolvedValue({
      items: [{ ...ENTRIES[0], level: 'warn' }, { ...ENTRIES[1], level: 'err' }],
    })
    renderTimeline()

    await screen.findByText('价格偏离预警')
    expect(tagOf('价格偏离预警')).toHaveClass('ant-tag-blue')
    expect(tagOf('数据库连接失败')).toHaveClass('ant-tag-blue')
  })
})
