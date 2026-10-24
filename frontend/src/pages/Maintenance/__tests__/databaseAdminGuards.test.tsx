// frontend/src/pages/Maintenance/__tests__/databaseAdminGuards.test.tsx
// T02576《数据库维护修复》的可执行断言（4.2-1/4.2-2/4.2-3/4.2-5 + PRD FR-H-1）
//
// 这些断言针对的是同一类缺陷：界面承诺了后端没做（或做得更多）的能力。
// 因此除了行为本身，还钉住"文案不许再退回假承诺"的源码级检查。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import {
  CascadeView,
  buildSubmitValues,
  cascadeScopeText,
  isDeleteConfirmBlocked,
  type CascadeState,
} from '../DatabaseAdmin'
import type { DbColumn } from '../../../api/types'

const COLS: DbColumn[] = [
  { name: 'id', type: 'TEXT', nullable: false, default: null, primary_key: true, label: '任务ID' },
  { name: 'name', type: 'TEXT', nullable: false, default: null, primary_key: false, label: '任务名称' },
  { name: 'keyword', type: 'TEXT', nullable: true, default: null, primary_key: false, label: '关键词' },
  { name: 'min_price', type: 'INTEGER', nullable: true, default: null, primary_key: false, label: '最低价格' },
]

describe('buildSubmitValues：编辑提交的真实口径（4.2-3 + FR-H-1）', () => {
  it('update 模式绝不提交主键，即使表单里带着它', () => {
    const out = buildSubmitValues(COLS, { id: 't9', name: '新名' }, new Set(), 'update')
    expect(out).not.toHaveProperty('id')
    expect(out).toEqual({ name: '新名' })
  })

  it('create 模式允许手工指定主键（后端支持新增时给 id）', () => {
    const out = buildSubmitValues(COLS, { id: 'new1', name: 'a' }, new Set(), 'create')
    expect(out).toEqual({ id: 'new1', name: 'a' })
  })

  it('勾选「置为 NULL」的可空列显式提交 null——这才是"清空"', () => {
    const out = buildSubmitValues(COLS, { keyword: '旧值', min_price: 100 }, new Set(['keyword']), 'update')
    expect(out).toEqual({ keyword: null, min_price: 100 })
  })

  it('未勾选时留空字段不提交（保持原值），不会把 NOT NULL 列写空', () => {
    const out = buildSubmitValues(COLS, { name: '', keyword: '' }, new Set(), 'update')
    expect(out).toEqual({})
  })

  it('主键勾了"置 NULL"也不生效：主键不可空、且 update 模式本就不提交', () => {
    const out = buildSubmitValues(COLS, { id: 't1', name: 'x' }, new Set(['id']), 'update')
    expect(out).not.toHaveProperty('id')
  })

  it('数字 0 与布尔 false 属于有效值，不被当成"空"丢弃', () => {
    const out = buildSubmitValues(COLS, { min_price: 0 }, new Set(), 'update')
    expect(out).toEqual({ min_price: 0 })
  })
})

describe('删除确认门禁（4.2-5）', () => {
  it('确认码不对就禁用', () => {
    expect(isDeleteConfirmBlocked('', { status: 'empty' })).toBe(true)
    expect(isDeleteConfirmBlocked('CONFIRM_DELETE', { status: 'empty' })).toBe(false)
  })

  it('级联预览加载中或失败时，即使确认码正确也必须禁用', () => {
    expect(isDeleteConfirmBlocked('CONFIRM_DELETE', { status: 'loading' })).toBe(true)
    expect(isDeleteConfirmBlocked('CONFIRM_DELETE', { status: 'error', detail: 'x' })).toBe(true)
  })
})

describe('CascadeView：预览结果不再走 innerHTML', () => {
  it('失败态给出原因 + 重试入口，而不是只留一行灰字', () => {
    const onRetry = vi.fn()
    render(<CascadeView state={{ status: 'error', detail: '500 服务器开小差' }} onRetry={onRetry} />)
    expect(screen.getByText('级联影响预览失败，删除已禁用')).toBeTruthy()
    expect(screen.getByText('500 服务器开小差')).toBeTruthy()
    fireEvent.click(screen.getByText('重试预览'))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('关联影响按文本渲染；后端字段里的 HTML 不会被当标记执行（T02727 同族）', () => {
    const evil = '<img src=x onerror=alert(1)>'
    const state: CascadeState = {
      status: 'relations',
      total: 7,
      relations: [
        { table: 'items', fk: 'task_id', action: 'cascade', count: 5, description: `商品 ${evil} 5 条` },
        { table: 'events', fk: 'task_id', action: 'set_null', count: 2, description: '事件 2 条' },
      ],
    }
    const { container } = render(<CascadeView state={state} onRetry={() => {}} />)
    expect(screen.getByText('关联影响：共 7 条关联数据将被处理')).toBeTruthy()
    expect(container.querySelector('img')).toBeNull()
    expect(container.innerHTML).toContain('&lt;img')
    expect(screen.getByText(/连同删除：商品/)).toBeTruthy()
    expect(screen.getByText(/仅解除关联：事件/)).toBeTruthy()
  })

  it('无关联数据时给出明确安全结论；加载中不假装完成', () => {
    render(<CascadeView state={{ status: 'empty' }} onRetry={() => {}} />)
    expect(screen.getByText('无关联数据，可安全删除')).toBeTruthy()
    render(<CascadeView state={{ status: 'loading' }} onRetry={() => {}} />)
    expect(screen.getByText('级联影响预览加载中…')).toBeTruthy()
  })
})

describe('删除确认四要素（T02725）', () => {
  it('影响范围写清行数、级联条数与处理方式', () => {
    expect(cascadeScopeText('tasks', 3, { status: 'empty' })).toBe('表 tasks 的 3 行记录，无级联子记录')
    const scope = cascadeScopeText('tasks', 2, {
      status: 'relations',
      total: 7,
      relations: [
        { table: 'items', fk: 'task_id', action: 'cascade', count: 5, description: '商品 5 条' },
        { table: 'events', fk: 'task_id', action: 'cascade', count: 1, description: '事件 1 条' },
        { table: 'logs', fk: 'task_id', action: 'set_null', count: 1, description: '日志 1 条' },
      ],
    })
    expect(scope).toContain('表 tasks 的 2 行记录')
    expect(scope).toContain('7 条关联数据')
    expect(scope).toContain('2 类表连同删除')
    expect(scope).toContain('1 类表仅解除关联')
  })

  it('级联统计中/失败时明说范围未知，不假装已经算清', () => {
    expect(cascadeScopeText('tasks', 1, { status: 'loading' })).toContain('统计完成前无法确认')
    expect(cascadeScopeText('tasks', 1, { status: 'error', detail: 'x' })).toContain('删除已禁用')
  })
})

describe('源码级名实一致（防止退回假承诺）', () => {
  // 注释里允许保留一次历史说明（解释当初为什么错），所以断言只针对代码本体：
  // 剥掉块注释与整行注释后再比，口径与 tests/test_maintenance_cleanup.py 的
  // test_no_webview_data_left_in_cleanup_sources 一致（T02575 同族教训）。
  const stripComments = (src: string): string => {
    const noBlock = src.replace(/\/\*[\s\S]*?\*\//g, '')
    return noBlock.split('\n').filter((line) => !line.trim().startsWith('//')).join('\n')
  }
  const page = stripComments(readFileSync(resolve(__dirname, '../DatabaseAdmin.tsx'), 'utf-8'))

  it('不再出现"请选择冲突处理"这种没有第二个选项的选择', () => {
    expect(page).not.toContain('请选择冲突处理')
    expect(page).toContain('冲突处理只有一种：跳过')
  })

  it('删除确认不再把预览拼成 HTML（整类 sink，而不只是 dangerouslySetInnerHTML）', () => {
    // T02727：级联预览的表名/列名来自 SQLite，可从本页直接编辑，属于存储型 XSS 面。
    // 挡住 JSX 的 dangerouslySetInnerHTML 还不够：改写成 ref.innerHTML = / insertAdjacentHTML
    // 同样会把后端文本当标记执行，所以按「HTML sink 类别」逐一禁。
    for (const sink of ['dangerouslySetInnerHTML', '__html:', '.innerHTML', 'insertAdjacentHTML', 'document.write']) {
      expect(page, `DatabaseAdmin.tsx 代码里出现了 HTML sink：${sink}`).not.toContain(sink)
    }
  })

  it('导出按钮点名全表，且带 loading', () => {
    expect(page).toContain('导出全表 CSV')
    expect(page).toContain('loading={exporting === \'csv\'}')
    expect(page).toContain('导出的是 {activeTable} 的全部')
  })

  it('编辑弹窗说明"留空=不改 / 勾选=清空 / 主键不可改"', () => {
    expect(page).toContain('置为 NULL（清空此字段）')
    expect(page).toContain('主键不可修改')
    expect(page).toContain('留空的字段保持原值不变')
  })

  it('审计日志抽屉有 loading，不再先开后填', () => {
    expect(page).toContain('loading={auditLoading}')
  })

  it('单行/批量删除共用 DangerSummary 四要素，批量数量取真实选中数（T02725）', () => {
    expect(page).toContain('<DangerSummary')
    expect(page).toMatch(/count=\{opts\.rowCount\}/)
    expect(page).toMatch(/rowCount: selectedRowKeys\.length/)
    expect(page).toContain('批量删除表 ${activeTable} 中选中的 ${selectedRowKeys.length} 行记录')
    // 旧确认框只有一句「将从表 X 删除…操作不可恢复」，缺动作/影响范围
    expect(page).not.toContain('将从表 ${activeTable} 删除')
  })

  it('移动端导出同样点名全表并给 loading（T02576 桌面/移动同口径）', () => {
    const mobile = readFileSync(resolve(__dirname, '../../../mobile/pages/DatabaseAdmin/index.tsx'), 'utf-8')
    expect(mobile).toContain('导出全表 CSV')
    expect(mobile).toContain("loading={exporting === 'csv'}")
    expect(mobile).toContain('fullTableRows')
  })
})
