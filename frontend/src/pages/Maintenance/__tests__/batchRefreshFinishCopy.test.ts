/**
 * 批量采集收尾反馈与清理预览的纯函数契约（T02578 / PRD 5.4-4.4-1/4.4-3/4.4-4/4.4-5）
 *
 * 覆盖四条容易被「假收尾/假数字」绕过的判据：
 * - 首帧不得判定为收尾（否则一进页面就弹一次「批量采集完成」）
 * - 后端无统计时必须如实说「未回传统计」，不能凑一个 0/0/0 的成功文案
 * - 清理条数文案只能来自预览态，统计中/失败/0 条三种状态不得写成可确认的既成事实
 * - 禁用态按钮的 tooltip 不能再写动作描述（「暂停当前批次」挂在空闲按钮上就是假选择）
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  batchRunJustFinished,
  buildBatchFinishCopy,
  cleanupPreviewDescription,
  controlButtonTips,
} from '../BatchRefresh'

type RunResult = Parameters<typeof buildBatchFinishCopy>[0]

const IDLE: NonNullable<RunResult> = { success: 0, failed: 0, skipped: 0, stopped: false }

describe('batchRunJustFinished（4.4-1 收尾判定）', () => {
  it('首帧不判定为收尾', () => {
    // 页面刚加载时 prev 未知，若按「非运行态即收尾」会凭空弹一次完成通知
    expect(batchRunJustFinished(null, 'idle')).toBe(false)
    expect(batchRunJustFinished(undefined, 'idle')).toBe(false)
  })

  it('running/paused/stopping → idle 才算收尾', () => {
    expect(batchRunJustFinished('running', 'idle')).toBe(true)
    expect(batchRunJustFinished('paused', 'idle')).toBe(true)
    expect(batchRunJustFinished('stopping', 'idle')).toBe(true)
  })

  it('仍在进行中或本来就空闲都不算收尾', () => {
    expect(batchRunJustFinished('running', 'running')).toBe(false)
    expect(batchRunJustFinished('running', 'paused')).toBe(false)
    expect(batchRunJustFinished('idle', 'idle')).toBe(false)
  })
})

describe('buildBatchFinishCopy（4.4-1 收尾文案）', () => {
  it('有失败时降级为 warning 并带真实计数', () => {
    const copy = buildBatchFinishCopy({ ...IDLE, success: 12, failed: 3, skipped: 1 }, '2026-10-20T06:00:00+00:00')
    expect(copy.level).toBe('warning')
    expect(copy.message).toContain('成功 12')
    expect(copy.message).toContain('失败 3')
    expect(copy.message).toContain('跳过 1')
  })

  it('被手动停止时说明可续传', () => {
    const copy = buildBatchFinishCopy({ ...IDLE, stopped: true }, '2026-10-20T06:00:00+00:00')
    expect(copy.description).toContain('手动停止')
    expect(copy.description).toContain('断点续传')
  })

  it('无统计时如实说明后端未回传，不编造计数', () => {
    const copy = buildBatchFinishCopy(null, null)
    expect(copy.description).toContain('未回传统计')
    expect(copy.message + copy.description).not.toMatch(/成功 \d+/)
    // 时间也未回传时必须写「时间未回传」，不能显示空占位假装知道
    expect(copy.description).toContain('时间未回传')
  })
})

describe('cleanupPreviewDescription（4.4-3 分母同源）', () => {
  it('统计中不得出现具体条数', () => {
    expect(cleanupPreviewDescription(undefined, 30)).toContain('正在统计')
    expect(cleanupPreviewDescription({ status: 'loading' }, 0)).not.toMatch(/\d+ 条/)
  })

  it('统计失败时禁用口径说明并要求重试', () => {
    expect(cleanupPreviewDescription({ status: 'error' }, 30)).toContain('无法确认本次删除范围')
  })

  it('0 条时文案点明是 0 条（配合确认按钮禁用）', () => {
    expect(cleanupPreviewDescription({ status: 'ready', matched: 0 }, 0)).toContain('0 条')
    expect(cleanupPreviewDescription({ status: 'ready', matched: 0 }, 30)).toContain('0 条')
  })

  it('days=0 说清是整表清空且不分用户，days>0 带上天数', () => {
    expect(cleanupPreviewDescription({ status: 'ready', matched: 7 }, 0)).toContain('全部 7 条')
    expect(cleanupPreviewDescription({ status: 'ready', matched: 7 }, 0)).toContain('不区分用户')
    const d30 = cleanupPreviewDescription({ status: 'ready', matched: 7 }, 30)
    expect(d30).toContain('30 天前')
    expect(d30).toContain('7 条')
    expect(d30).toContain('不可恢复')
  })
})

describe('controlButtonTips（4.4-5 禁用态不写动作描述）', () => {
  it('空闲时三个按钮都说明为什么不可用', () => {
    const tips = controlButtonTips({ running: false, paused: false, stopping: false })
    expect(tips.pause).toContain('无可暂停批次')
    expect(tips.resume).toContain('已暂停')
    expect(tips.stop).toContain('没有正在运行的批次')
  })

  it('运行中：暂停可点、继续/停止说明当前不需要', () => {
    const tips = controlButtonTips({ running: true, paused: false, stopping: false })
    expect(tips.pause).toContain('当前商品采集完成后生效')
    expect(tips.resume).toContain('无需继续')
    expect(tips.stop).toContain('持久化未处理商品')
  })

  it('暂停中：继续变为可操作描述', () => {
    const tips = controlButtonTips({ running: false, paused: true, stopping: false })
    expect(tips.resume).toContain('从断点继续')
    // 暂停态下「暂停」按钮的提示不能写「当前空闲」——那不是它的真实状态
    expect(tips.pause).toContain('已处于「已暂停」')
    expect(tips.pause).not.toContain('当前空闲')
  })

  it('停止中：不再提示「暂停」', () => {
    const tips = controlButtonTips({ running: false, paused: false, stopping: true })
    expect(tips.pause).toContain('无需再暂停')
  })
})

describe('源码级契约（4.4-4 口径名实对齐）', () => {
  // 去注释后再断言：旧注释里写着「总执行次数」，不去注释会出现「注释自证」的假通过
  const stripComments = (s: string) =>
    s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/[^\n]*/g, '$1')

  const src = stripComments(
    readFileSync(join(process.cwd(), 'src/pages/Maintenance/BatchRefresh.tsx'), 'utf-8'),
  )

  it('卡片标题不再出现「总执行次数」这类与筛选条件不符的口径', () => {
    expect(src).not.toContain('总执行次数')
    expect(src).toContain('执行记录总数')
    expect(src).toContain('当前筛选结果数')
    expect(src).toContain('全表累计')
  })

  it('清理确认框确实接了预览（不是继续用筛选 total 冒充删除条数）', () => {
    expect(src).toContain('cleanupHistoryPreview')
    expect(src).toContain('cleanupPreviewDescription')
    expect(src).toContain('disabled: !canConfirm')
  })

  it('控制按钮 tooltip 全部改为状态派生，不再有硬编码动作描述', () => {
    expect(src).not.toContain('tip="停止批次并持久化进度"')
    expect(src).toContain('tips.stop')
  })
})
