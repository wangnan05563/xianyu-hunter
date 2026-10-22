// frontend/src/pages/Evaluations/__tests__/evaluationsColumnConfig.test.tsx
// 评审 2.4-5：订单列 key=order_status 只写在表格列里、没登记进 COLUMN_DEFINITIONS。
// 后果一：列设置弹窗看不到它，无法显隐/拖拽；
// 后果二：applyConfig 的兜底会把未登记的列追加到末尾——包括 fixed-right 操作列之后。
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { useColumnConfig } from '../../../hooks/useColumnConfig'
import { storage } from '../../../utils/storage'
import { COLUMN_DEFINITIONS } from '../columnDefinitions'

const TABLE_KEYS = ['feedback', 'order_status', 'action']
const tableColumns = TABLE_KEYS.map((key) => ({ key }))
const keysOf = <T extends { key?: string }>(cols: T[]) => cols.map((c) => c.key)

function mount(storageKey: string) {
  return renderHook(() => useColumnConfig(storageKey, COLUMN_DEFINITIONS))
}

beforeEach(() => {
  localStorage.clear()
})

describe('评估明细列配置：订单列（评审 2.4-5）', () => {
  it('订单列已登记进配置表，操作列仍不参与配置', () => {
    const keys = COLUMN_DEFINITIONS.map((d) => d.key)
    expect(keys).toContain('order_status')
    expect(keys).not.toContain('action')
  })

  it('默认顺序下订单列位于操作列之前，不再被兜底甩到 fixed-right 之后', () => {
    const { result } = mount('t.evals.defs')
    expect(keysOf(result.current.applyConfig(tableColumns))).toEqual(['feedback', 'order_status', 'action'])
  })

  it('订单列可隐藏，隐藏后不再出现在表格列里', () => {
    const { result } = mount('t.evals.hide')
    act(() => result.current.toggleHidden('order_status'))
    expect(result.current.hidden.has('order_status')).toBe(true)
    expect(keysOf(result.current.applyConfig(tableColumns))).toEqual(['feedback', 'action'])
  })

  it('订单列可拖拽排序，顺序按用户配置生效', () => {
    const { result } = mount('t.evals.move')
    act(() => result.current.moveColumn('order_status', 'feedback'))
    expect(keysOf(result.current.applyConfig(tableColumns))).toEqual(['order_status', 'feedback', 'action'])
  })

  it('老用户已保存的列顺序里没有订单列时，新列追加在操作列之前', () => {
    storage.set('t.evals.legacy.order', ['feedback'])
    const { result } = mount('t.evals.legacy')
    expect(keysOf(result.current.applyConfig(tableColumns))).toEqual(['feedback', 'order_status', 'action'])
  })

  it('订单列文案/颜色取 constants/orderStatus，不再自带第三份 statusMap', () => {
    const src = readFileSync(resolve(__dirname, '../hooks/useEvalColumns.tsx'), 'utf8')
    expect(src).toContain('orderStatusLabel(status)')
    expect(src).toContain('orderStatusColor(status)')
    expect(src).not.toMatch(/pending_pay:\s*\{\s*color/)
  })
})
