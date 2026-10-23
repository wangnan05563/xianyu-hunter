// @vitest-environment node
// T02890 源码契约：门禁必须「接在对的对象上」，而不是只要出现过 disabled 就绿灯。
// 按按钮逐个切片断言：AI 相关入口被 aiOff 置灰；非 AI 的人工入口不受影响。
// 切片止于该元素自己的闭合，否则同名 props 会被邻居蒙过去（整份文件 toContain 同理）。
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it, expect } from 'vitest'

const FE = resolve(__dirname, '../..')
const read = (rel: string) => readFileSync(resolve(FE, rel), 'utf-8').replace(/\r\n/g, '\n')

const COLUMNS = read('src/pages/Evaluations/hooks/useEvalColumns.tsx')
const EVAL_PAGE = read('src/pages/Evaluations/index.tsx')
const TASKLIST = read('src/pages/Tasks/TaskList.tsx')
const EVAL_AI = read('src/pages/Evaluations/hooks/useEvalAI.ts')
const API_ERROR = read('src/utils/apiError.ts')
const BACKEND_GATE = read('../backend/xianyu_hunter/web/routes/api_ai.py')

/** 从 marker 起切到「这个元素自己的结尾」：独占一行的 /> 或 </TipButton>，先到为准 */
function elementSlice(src: string, marker: string): string {
  const start = src.indexOf(marker)
  expect(start, `未找到锚点：${marker}`).toBeGreaterThan(-1)
  const tail = src.slice(start)
  const ownClose = tail.search(/\n\s*\/>/)
  const tagEnd = tail.indexOf('</TipButton>')
  const ends = [ownClose, tagEnd].filter((i) => i > -1)
  expect(ends.length, `锚点没有闭合边界：${marker}`).toBeGreaterThan(0)
  return tail.slice(0, Math.min(...ends))
}

describe('评估列表 AI 列：只有 AI 按钮被开关置灰', () => {
  it('aiOff 取 useAIEnabled 的确定关闭态', () => {
    expect(COLUMNS).toContain("import { AI_GATE_OFF_TIP, useAIEnabled } from '../../../hooks/useAIEnabled'")
    expect(COLUMNS).toContain('const aiOff = useAIEnabled().enabled === false')
  })

  it('AI 成色评估按钮：置灰与提示都由 aiOff 驱动', () => {
    const slice = elementSlice(COLUMNS, "tip={aiOff ? AI_GATE_OFF_TIP : 'AI 成色评估'}")
    expect(slice).toContain('onClick={() => onAIEval(r.item_id)}')
    expect(slice).toContain('disabled={aiOff || (isDataInsufficient(r) && (r.payload.score ?? 0) < 60)}')
  })

  it('深度鉴伪按钮同样挂 aiOff（漏一个就是只灰一半）', () => {
    const slice = elementSlice(COLUMNS, "tip={aiOff ? AI_GATE_OFF_TIP : '深度鉴伪（盗图/损坏/一致性/模板）'}")
    expect(slice).toContain('onClick={() => onDeepAnalyze(r.item_id)}')
    expect(slice).toContain('disabled={aiOff || (isDataInsufficient(r) && (r.payload.score ?? 0) < 60)}')
  })

  it('aiOff 进入 useMemo 依赖，否则开关变化不重算列', () => {
    const deps = COLUMNS.slice(COLUMNS.indexOf('], ['), COLUMNS.indexOf('])', COLUMNS.indexOf('], [')))
    expect(deps).toContain('aiOff')
  })

  it('非 AI 的「收官方凭证」入口不得被开关连带置灰', () => {
    expect(elementSlice(COLUMNS, 'tip="访问闲鱼官方页面采集完整数据并重新评估"')).not.toContain('aiOff')
  })
})

describe('批量 AI 评估：逐条打 /evaluate-condition，关开关时必须整批拦住', () => {
  it('批量按钮挂 aiOff，否则一批发 N 个 403 toast', () => {
    expect(EVAL_PAGE).toContain("import { AI_GATE_OFF_TIP, useAIEnabled } from '@/hooks/useAIEnabled'")
    const slice = elementSlice(EVAL_PAGE, 'onClick={onBatchAIEval}')
    expect(slice).toContain("tip={aiOff ? AI_GATE_OFF_TIP : '对选中商品批量执行 AI 成色评估'}")
    expect(slice).toContain('disabled={aiOff}')
  })

  it('同排的批量官方采集与取消选择不得被连带置灰', () => {
    expect(elementSlice(EVAL_PAGE, 'tip="对选中商品批量访问官方页面采集"')).not.toContain('aiOff')
    expect(elementSlice(EVAL_PAGE, 'tip="取消已选中的商品"')).not.toContain('aiOff')
  })

  it('useAIEnabled 必须早于 selectedCount 早退（否则条件调用 Hook）', () => {
    const hookAt = EVAL_PAGE.indexOf('const aiOff = useAIEnabled()')
    const earlyReturnAt = EVAL_PAGE.indexOf('if (selectedCount === 0) return null')
    expect(hookAt).toBeGreaterThan(-1)
    expect(earlyReturnAt).toBeGreaterThan(-1)
    expect(hookAt).toBeLessThan(earlyReturnAt)
  })
})

describe('任务列表：智能建任务入口在开关关闭时置灰', () => {
  it('入口按钮与弹窗内解析按钮都挂 aiOff，且提示指向开关', () => {
    expect(TASKLIST).toContain("import { AI_GATE_OFF_TIP, useAIEnabled } from '../../hooks/useAIEnabled'")
    expect(TASKLIST).toContain('const aiOff = useAIEnabled().enabled === false')
    expect(elementSlice(TASKLIST, "tip={aiOff ? AI_GATE_OFF_TIP : '用一句话 AI 智能创建任务'}")).toContain('disabled={aiOff}')
    expect(elementSlice(TASKLIST, "tip={aiOff ? AI_GATE_OFF_TIP : '让 AI 解析需求并创建任务'}")).toContain('disabled={aiOff}')
  })

  it('模板市场等非 AI 入口不受开关影响', () => {
    expect(elementSlice(TASKLIST, 'tip="打开任务模板市场"')).not.toContain('aiOff')
  })
})

describe('错误判定收敛到 apiError 单一入口', () => {
  it('判定只写在 apiError.ts，页面调 isAiDisabledError', () => {
    expect(API_ERROR).toContain('export function isAiDisabledError')
    expect(API_ERROR).toContain("export const AI_DISABLED_CODE = 'ai_disabled'")
    expect(EVAL_AI).toContain('if (isAiDisabledError(err))')
    expect(TASKLIST).toContain('if (isAiDisabledError(err))')
  })

  it('页面不得再按裸 403 断言「AI 未开启」', () => {
    expect(EVAL_AI).not.toContain('status === 403')
    expect(EVAL_AI).not.toContain('AI 功能未开启')
  })
})

describe('后端 403 带机器码且文案不变', () => {
  it('_check_ai_enabled 抛 CodedHTTPException(code=ai_disabled)', () => {
    expect(BACKEND_GATE).toContain('AI_DISABLED_CODE = "ai_disabled"')
    const start = BACKEND_GATE.indexOf('def _check_ai_enabled')
    // 窗口截到下一个顶层定义为止，避免把别处的 raise HTTPException 也算进本函数
    const body = BACKEND_GATE.slice(start)
    const end = body.search(/\n(?=def |class |# =|@router)/)
    const fn = body.slice(0, end > -1 ? end : 700)
    expect(fn).toContain('raise CodedHTTPException')
    expect(fn).toContain('code=AI_DISABLED_CODE')
    // 函数体内不得再出现裸 HTTPException（那样响应体没有 code，前端只能靠中文兜底）
    expect(fn).not.toContain('raise HTTPException')
  })

  it('detail 原文一字未改（前端逐字转述它）', () => {
    expect(BACKEND_GATE).toContain('detail="AI 功能已关闭，请在「AI 服务」配置页面开启"')
  })
})
