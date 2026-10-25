import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * 固定右列里的删除确认不得再用 Popconfirm（T02975，T02671 同族收口）
 *
 * Popconfirm 底层是 @rc-component/trigger + findDOMNode：凭触发元素定位。
 * 触发点落在 `fixed: 'right'` 的 sticky 单元格里时，横向滚动会让它持续重算位置，
 * 确认框跟着闪，自动化里普通 click 直接 element is not stable。
 * 这两处与评估页是同一条因果链，只是没人报过——所以用契约钉住载体。
 */
const stripComments = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

const raw = (rel: string) => readFileSync(resolve(__dirname, rel), 'utf-8')

const ordersRaw = raw('../../Orders/Orders.tsx')
const batchRaw = raw('../BatchRefresh.tsx')
const ordersSrc = stripComments(ordersRaw)
const batchSrc = stripComments(batchRaw)

/**
 * 先在**带注释的原文**上切片（两端锚点里就含注释），再对切片去注释后断言——
 * 否则「去注释后的源码里找不到注释锚点」，切片恒空、断言恒绿/恒红都失真。
 */
function sliceRaw(src: string, start: string, end: string, label: string): string {
  const a = src.indexOf(start)
  const b = src.indexOf(end, a + start.length)
  if (a < 0 || b < 0) throw new Error(`${label} 定位失败：start=${a} end=${b}`)
  return stripComments(src.slice(a, b))
}

describe('Orders 删除确认（T02975）', () => {
  // 操作列 → 列配置应用处之间的那段就是操作列的渲染体
  const actionCol = () => sliceRaw(ordersRaw, "title: '操作', key: 'action'", '// 应用列配置', 'Orders 操作列')

  it('固定右列不再挂 Popconfirm，改用 App 的 modal.confirm', () => {
    const col = actionCol()
    expect(col).not.toContain('<Popconfirm')
    expect(col).not.toContain('onConfirm=')
    expect(col).toContain('modal.confirm(')
    expect(col).toContain('onOk: () => handleDelete(r.id)')
  })

  it('确认语义一字不减：标题、后果说明、按钮文案、危险样式', () => {
    const col = actionCol()
    expect(col).toContain("title: '确认删除此订单？'")
    expect(col).toContain("content: '删除后不可恢复'")
    expect(col).toContain("okText: '删除'")
    expect(col).toContain("cancelText: '取消'")
    expect(col).toMatch(/okButtonProps: \{ danger: true \}/)
  })

  it('modal 真的从 App 上下文取，且 Popconfirm 已从 antd 引入行移除', () => {
    expect(ordersSrc).toMatch(/const \{ modal \} = App\.useApp\(\)/)
    expect(ordersSrc.match(/^import \{[\s\S]*?\} from 'antd'/m)?.[0] ?? '').not.toContain('Popconfirm')
  })
})

describe('BatchRefresh 执行历史删除确认（T02975）', () => {
  // 历史表操作列：从 key: 'actions' 到该 useMemo 之后的排序处理段
  const historyCol = () => sliceRaw(batchRaw, "key: 'actions'", '// antd Table 排序变化', 'BatchRefresh 历史操作列')

  it('固定右列不再挂 Popconfirm，改用 App 的 modal.confirm', () => {
    const col = historyCol()
    expect(col).not.toContain('<Popconfirm')
    expect(col).toContain('modal.confirm(')
    expect(col).toContain('onOk: () => handleDelete(r.id)')
  })

  it('确认文案与原 Popconfirm 一致（标题/删除/取消）', () => {
    const col = historyCol()
    expect(col).toContain("title: '确认删除此条历史记录？'")
    expect(col).toContain("okText: '删除'")
    expect(col).toContain("cancelText: '取消'")
  })

  it('modal 进了 useMemo 依赖——漏了它会闭包持住旧 holder', () => {
    expect(batchSrc).toMatch(/const \{ modal \} = App\.useApp\(\)/)
    expect(historyCol()).toContain('], [modal])')
  })

  it('接错对象保护：不在固定列里的两处 Popconfirm（触发预估 / 清理预览）必须原样留着', () => {
    expect(batchSrc).toContain('renderCleanupPopconfirm')
    const remaining = batchSrc.split('<Popconfirm').length - 1
    expect(remaining).toBeGreaterThanOrEqual(2)
    expect(batchSrc.match(/^import \{[\s\S]*?\} from 'antd'/m)?.[0] ?? '').toContain('Popconfirm')
  })
})
