import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// T02567（评审 2.4 评估页高危操作确认与失败可见性）三条修复的源码契约：
// 1) 行内「手动抢单」直下真实订单 → 必须包在 Popconfirm 里，且文案带价格/评分/阈值
// 2) 「重新评估」静默全库重算 → 必须二次确认并显式说明重算范围
// 3) 批量 AI 评估逐条 catch {} 吞错后仍报成功 → 必须与采集批次同口径统计并提示失败数

const stripComments = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

const columns = stripComments(readFileSync(resolve(__dirname, '../hooks/useEvalColumns.tsx'), 'utf-8'))
const page = stripComments(readFileSync(resolve(__dirname, '../index.tsx'), 'utf-8'))
const batch = stripComments(readFileSync(resolve(__dirname, '../hooks/useEvalBatch.ts'), 'utf-8'))

describe('评估页：手动抢单二次确认（评审 2.4-1）', () => {
  it('抢单按钮包在 Popconfirm 内，动作只在 onConfirm 触发', () => {
    const takeover = columns.match(/<Popconfirm[\s\S]*?onManualTakeover\(r\)[\s\S]*?<\/Popconfirm>/)?.[0] ?? ''
    expect(takeover).toContain('确认手动抢单')
    expect(takeover).toContain('onConfirm={() => onManualTakeover(r)}')
    // 抢单按钮本身不能再挂 onClick，否则点一下即下单，确认框形同虚设
    expect(takeover).not.toContain('onClick={() => onManualTakeover(r)}')
  })

  it('确认文案暴露价格、评分与自动抢单阈值，并说明会提交真实订单', () => {
    const takeover = columns.match(/<Popconfirm[\s\S]*?onManualTakeover\(r\)[\s\S]*?<\/Popconfirm>/)?.[0] ?? ''
    expect(takeover).toContain('价格：')
    expect(takeover).toContain('评分：')
    expect(takeover).toContain('自动抢单阈值')
    expect(takeover).toContain('真实订单')
    expect(takeover).toMatch(/okButtonProps=\{\{ danger: true \}\}/)
  })

  it('Popconfirm 已从 antd 引入', () => {
    expect(columns.match(/^import \{[^}]*Popconfirm[^}]*\} from 'antd'/m)).not.toBeNull()
  })
})

describe('评估页：重新评估范围确认（评审 2.4-2）', () => {
  it('重新评估不再一键直触，改为 Popconfirm onConfirm', () => {
    const block = page.match(/<Popconfirm[\s\S]*?batch\.onRecompute[\s\S]*?<\/Popconfirm>/)?.[0] ?? ''
    expect(block).toContain('确认重新评估')
    expect(block).toContain('onConfirm={batch.onRecompute}')
    expect(block).toContain('确认重算')
    expect(block).toMatch(/okButtonProps=\{\{ danger: true \}\}/)
    expect(page).not.toContain('onClick={batch.onRecompute}')
  })

  it('范围文案区分已选任务与全部历史，并如实说明重算不吃当前筛选、不调用 AI', () => {
    expect(page).toContain('recomputeScope')
    expect(page).toMatch(/任务「\$\{selectedTaskName \|\| filters\.taskId\}」/)
    expect(page).toContain('当前账号全部历史评估记录')
    expect(page).toContain('重算不受上方时间窗与价格筛选限制')
    expect(page).toContain('不调用 AI')
  })

  it('Popconfirm 已从 antd 引入', () => {
    expect(page.match(/import \{[\s\S]*?Popconfirm[\s\S]*?\} from 'antd'/)?.[0]).toBeTruthy()
  })
})

describe('评估页：批量 AI 评估失败可见（评审 2.4-3）', () => {
  it('逐条统计成功/失败，不再空 catch 吞错', () => {
    const fn = batch.match(/const onBatchAIEval = useCallback\([\s\S]*?\}, \[[^\]]*\]\)/)?.[0] ?? ''
    expect(fn).toContain('let succeeded = 0')
    expect(fn).toContain('let failed = 0')
    expect(fn).toMatch(/catch \{\s*failed\+\+/)
    expect(fn).not.toMatch(/catch \{\s*\}/)
  })

  it('结束提示带成功/失败数量，与官方采集批次同口径', () => {
    const fn = batch.match(/const onBatchAIEval = useCallback\([\s\S]*?\}, \[[^\]]*\]\)/)?.[0] ?? ''
    expect(fn).toMatch(/if \(failed > 0\) \{[\s\S]*?message\.warning/)
    expect(fn).toContain('成功 ${succeeded}，失败 ${failed}')
    // 采集批次保持原口径，两者文案结构一致
    expect(fn).toContain('共 ${ids.length}')
    expect(batch).toContain('批量官方采集完成：成功 ${succeeded}，失败 ${failed}')
  })
})
