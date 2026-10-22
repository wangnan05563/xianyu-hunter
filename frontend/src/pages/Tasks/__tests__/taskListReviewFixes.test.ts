import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// T02565（评审 2.2 任务管理）四条修复的源码契约，防止回归：
// 1) 关联面板列定义的 useMemo 依赖必须含 linkTaskId，否则闭包捕获首渲染的 handleRemoveLink（删除静默无响应）
// 2) 危险操作确认统一为 Popconfirm，不再保留自研「行内装备确认 + 5s 自动撤销」状态机
// 3) 「全部启动」文案与 tooltip 必须限定在本页范围（后端只返回当前页 tasks）
// 4) 向导提供「直接创建」快捷通道 + Steps 可点选跳步

const stripComments = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

const list = stripComments(readFileSync(resolve(__dirname, '../TaskList.tsx'), 'utf-8'))
const editor = stripComments(readFileSync(resolve(__dirname, '../TaskEditor.tsx'), 'utf-8'))

describe('任务管理：关联删除闭包与确认模式（评审 2.2-1/2.2-3）', () => {
  it('linkColumns 依赖补 linkTaskId', () => {
    const block = list.match(/const linkColumns = useMemo\([\s\S]*?\], \[[^\]]*\]\)/)?.[0] ?? ''
    expect(block).toContain('linkTaskId')
  })

  it('行内装备确认状态机已删除，停止/删除走 Popconfirm', () => {
    expect(list).not.toContain('armConfirm')
    expect(list).not.toContain('doArmConfirm')
    expect(list).toContain('Popconfirm')
    expect(list.match(/<Popconfirm/g) ?? []).toHaveLength(4) // 表格 + 卡片 × 停止 + 删除
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
