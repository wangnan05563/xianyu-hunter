// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// T02565（评审 2.2 任务管理）四条修复的源码契约，防止回归：
// 1) 关联面板列定义的 useMemo 依赖必须含 linkTaskId，否则闭包捕获首渲染的 handleRemoveLink（删除静默无响应）
// 2) 危险操作必须走二次确认，不再保留自研「行内装备确认 + 5s 自动撤销」状态机
// 3) 「全部启动」文案与 tooltip 必须限定在本页范围（后端只返回当前页 tasks）
// 4) 向导提供「直接创建」快捷通道 + Steps 可点选跳步
//
// 第 2 条在 T02651 收窄过一次：表格操作列收纳后，停止/删除挂在「更多」菜单项上，
// 那里挂不住 Popconfirm（弹层会随菜单一起销毁），改用 Modal.confirm。
// 卡片视图空间充裕，仍是 Popconfirm。所以这里的契约是「每个危险动作都有二次确认」，
// 而不是「确认一律用 Popconfirm」。

const stripComments = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

const list = stripComments(readFileSync(resolve(__dirname, '../TaskList.tsx'), 'utf-8'))
const editor = stripComments(readFileSync(resolve(__dirname, '../TaskEditor.tsx'), 'utf-8'))

describe('任务管理：关联删除闭包与确认模式（评审 2.2-1/2.2-3）', () => {
  it('linkColumns 依赖补 linkTaskId', () => {
    const block = list.match(/const linkColumns = useMemo\([\s\S]*?\], \[[^\]]*\]\)/)?.[0] ?? ''
    expect(block).toContain('linkTaskId')
  })

  it('行内装备确认状态机已删除，表格危险项走 Modal.confirm、卡片仍用 Popconfirm', () => {
    expect(list).not.toContain('armConfirm')
    expect(list).not.toContain('doArmConfirm')
    // 卡片视图：停止 + 删除仍是 Popconfirm（那里空间充裕，行内弹层没有抖动问题）
    expect(list.match(/<Popconfirm/g) ?? []).toHaveLength(2)
    // 表格视图收纳后：危险项挂在「更多」菜单上，确认走本文件统一的 Modal.confirm
    const rowMore = list.match(/const buildRowMoreItems[\s\S]*?\n  \}/)?.[0] ?? ''
    expect(rowMore).toContain('confirmRowDanger')
    expect(rowMore).toContain('danger: true')
    expect(rowMore).not.toContain('Popconfirm')
    expect(list).toMatch(/const confirmRowDanger[\s\S]*?Modal\.confirm\(\{/)
    // 表格列定义里不得再出现行内 Popconfirm，否则操作列回到 6 元素拥挤
    const actionCols = list.match(/const columns = \[[\s\S]*?\n  \]/)?.[0] ?? ''
    expect(actionCols).not.toContain('<Popconfirm')
  })
})

describe('任务管理：全部启动文案与向导快捷通道（评审 2.2-2/2.2-4/2.2-5）', () => {
  it('批量启动按钮不再承诺「所有任务」，文案限定本页', () => {
    expect(list).toContain('启动本页')
    expect(list).not.toMatch(/>\s*全部启动\s*</)
    expect(list).toMatch(/tip=\{`一键启动本页/)
  })

  it('Step1 提供直接创建，Steps 跳步走前置校验（T02653）', () => {
    expect(editor).toContain('直接创建')
    expect(editor).toMatch(/<Steps[\s\S]*?onChange=\{handleStepJump\}/)
    // 快捷通道不做逐步校验，直接走 handleSubmit(false)
    expect(editor).toContain('onClick={() => handleSubmit(false)}')
  })
})
