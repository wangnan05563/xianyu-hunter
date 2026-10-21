/**
 * 仪表盘事件类型标签同源（T02842）
 *
 * 钉住的行为：events.type 的点分字面值必须渲染成中文标签，而不是 evTypeLabel 的英文末段兜底。
 * 回归点：Dashboard 侧原来另有两张表——下划线格式（buy_succeeded）和 21 个后端从未发出过的
 * 点分幽灵键（task.runner.* / collector.* / buyer.*），与 DB 实际 type 零交集，
 * 于是「搜索完成 / 商品评分」这类主力事件在仪表盘上一直显示成 search_done / scored，
 * 且颜色表也匹配不到、Tag 全灰。兜底本应是例外，当时却是常态。
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import EventStreamSection from '../components/EventStreamSection'
import { evTypeLabel } from '../utils'
import { eventTypeColor } from '../../../constants/eventTypes'
import type { RecentEvent } from '../../../api'

describe('evTypeLabel 读单一事实源（T02842）', () => {
  it('主力事件类型渲染中文，不再落英文末段', () => {
    // 两张库里 16314 + 377 行的主力类型，此前恰好是唯二真实存在却查不到的
    expect(evTypeLabel('task.search_done')).toBe('搜索完成')
    expect(evTypeLabel('eval.scored')).toBe('商品评分')
    expect(evTypeLabel('eval.passed')).toBe('通过筛选')
  })

  it('后端动态拼装的 db_admin.<action> 走家族规则', () => {
    expect(evTypeLabel('db_admin.delete')).toBe('数据表删除')
    expect(evTypeLabel('db_admin.import')).toBe('数据表导入')
    expect(evTypeLabel('db_admin.create_failed')).toBe('数据表新增失败')
  })

  it('真正未知的类型才用兜底，且空值不显示成空标签', () => {
    expect(evTypeLabel('somefuture.brand_new')).toBe('brand_new')
    expect(evTypeLabel('')).toBe('事件')
  })
})

describe('事件流卡片的类型 Tag（T02842）', () => {
  const events: RecentEvent[] = [
    { type: 'task.search_done', created_at: '2026-10-21T02:00:00Z', message: '搜索完成: 找到12/去重8/评估8/通过1' },
    { type: 'eval.scored', created_at: '2026-10-21T02:01:00Z', message: '评估得分 82' },
    { type: 'db_admin.delete', created_at: '2026-10-21T02:02:00Z', message: 'db_admin.delete events pk=7' },
  ]

  it('渲染中文标签，页面上找不到英文末段', () => {
    render(
      <MemoryRouter>
        <EventStreamSection
          events={events}
          streamStatus="已连接"
          overview={null}
          onNavigate={() => {}}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('搜索完成')).toBeTruthy()
    expect(screen.getByText('商品评分')).toBeTruthy()
    expect(screen.getByText('数据表删除')).toBeTruthy()
    expect(screen.queryByText('search_done')).toBeNull()
    expect(screen.queryByText('scored')).toBeNull()
  })

  it('已注册类型不再统一灰成 default', () => {
    expect(eventTypeColor('task.search_done')).toBe('blue')
    expect(eventTypeColor('db_admin.delete')).toBe('default') // 审计动作本就是中性色
    expect(eventTypeColor('never.emitted')).toBe('default')
  })
})
