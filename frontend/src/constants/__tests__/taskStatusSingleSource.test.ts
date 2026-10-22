import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  TASK_MODE,
  TASK_MODE_LABELS,
  TASK_STATUS,
  TASK_STATUS_CONFIG,
  taskModeOptions,
  taskStatusOptions,
} from '../taskStatus'
import {
  FOREIGN_VOCAB,
  codeLines,
  exists,
  listSrcFiles,
  scanStatusLiteralPositions,
  srcOf,
  vocabFor,
} from './statusLiteralScan'

// T02716：移动端任务页自己写了 STATUS_LABELS / MODE_LABELS（桌面任务列表再写一份，
// 且两边取值不一样——移动端把 notify 模式统一标成「确认」、把 stopped 任务标成「已暂停」）。
// 这类错不会报错，只是把状态说反，所以把「前端常量表 ↔ 后端枚举」钉死，
// 并对已收口文件禁止再出现裸的状态/模式字面串。写法沿用 T02693 的 orderStatusSingleSource。

const BACKEND_TASK_DOMAIN = resolve(
  __dirname,
  '../../../../backend/xianyu_hunter/domain/task.py',
)

/** T02716 已收口且**逐字禁裸串**的文件（全文件扫串，见下面那条规则的作用域说明） */
const BAN_FILES = [
  resolve(__dirname, '../../mobile/pages/Tasks/index.tsx'),
  resolve(__dirname, '../../mobile/pages/Tasks/TaskDetail.tsx'),
  resolve(__dirname, '../../pages/Tasks/TaskList.tsx'),
]

/**
 * 已收口的任务域文件：只允许通过 TASK_STATUS / TASK_MODE 常量引用取值。
 * T02850 把 Onboarding / 移动端编辑器 / TaskDetail / useAutoLiveSearch / DryRunBanner / Dashboard 加进来，
 * 但**不扩到逐字禁裸串**那一档：Dashboard 里 `es.addEventListener('error', …)` 的 `'error'`
 * 是 SSE 事件名，与 TaskStatus.ERROR 同词不同义；全文件扫串会把 DOM API 判成漂移，
 * 于是「守卫变红」的修法变成改注释或改名——比没有守卫更糟。
 * 这批文件由「状态/模式位置」扫描守护（把值写在比较/选项位置上才算裸写）。
 */
const CLEANED_FILES = [
  ...BAN_FILES,
  resolve(__dirname, '../../pages/Onboarding/index.tsx'),
  resolve(__dirname, '../../mobile/pages/TaskEditor/index.tsx'),
  resolve(__dirname, '../../pages/Tasks/TaskDetail.tsx'),
  resolve(__dirname, '../../hooks/useAutoLiveSearch.ts'),
  resolve(__dirname, '../../components/layout/DryRunBanner.tsx'),
  resolve(__dirname, '../../pages/Dashboard/index.tsx'),
]

/** 从后端枚举抽成员名 → 字面值（枚举体是缩进行，到第一条顶格行为止） */
function parseBackendEnum(className: string): Record<string, string> {
  const src = readFileSync(BACKEND_TASK_DOMAIN, 'utf-8')
  const start = src.indexOf(`class ${className}`)
  expect(start, `后端 domain/task.py 未找到 ${className} 定义`).toBeGreaterThanOrEqual(0)
  const after = src.slice(start)
  const body = after.slice(after.indexOf('\n') + 1)
  const slice = body.slice(0, body.search(/^\S.*$/m))
  const out: Record<string, string> = {}
  for (const m of slice.matchAll(/^\s{4}([A-Z_]+)\s*=\s*"([a-z_]+)"/gm)) {
    out[m[1]] = m[2]
  }
  expect(Object.keys(out).length, `${className} 解析结果为空，多半是枚举写法改了`).toBeGreaterThan(0)
  return out
}

describe('任务状态/模式单一事实源（T02716）', () => {
  it('TASK_STATUS / TASK_MODE 的取值集合等于后端枚举', () => {
    // 只比字面值不比成员名：后端叫 NOTIFY_ONLY="notify"，前端常量用 TASK_MODE.NOTIFY 更顺口，
    // 会静默失效的是"值"而不是"名字"
    expect(Object.values(TASK_STATUS).sort()).toEqual(
      Object.values(parseBackendEnum('TaskStatus')).sort(),
    )
    expect(Object.values(TASK_MODE).sort()).toEqual(
      Object.values(parseBackendEnum('TaskMode')).sort(),
    )
  })

  it('标签表覆盖每个枚举值，不多不少', () => {
    expect(Object.keys(TASK_STATUS_CONFIG).sort()).toEqual(
      Object.values(parseBackendEnum('TaskStatus')).sort(),
    )
    expect(Object.keys(TASK_MODE_LABELS).sort()).toEqual(
      Object.values(parseBackendEnum('TaskMode')).sort(),
    )
  })

  it('每个状态都有中文标签与颜色（后端新增枚举值时这里必须一起补）', () => {
    for (const value of Object.values(TASK_STATUS)) {
      expect(TASK_STATUS_CONFIG[value].label, `${value} 缺中文标签`).toBeTruthy()
      expect(TASK_STATUS_CONFIG[value].color, `${value} 缺徽标颜色`).toBeTruthy()
    }
    for (const value of Object.values(TASK_MODE)) {
      expect(TASK_MODE_LABELS[value], `${value} 缺模式文案`).toBeTruthy()
    }
  })

  it('筛选项的 value/label 与标签表同源', () => {
    const options = taskStatusOptions([
      TASK_STATUS.RUNNING,
      TASK_STATUS.PAUSED,
      TASK_STATUS.STOPPED,
    ])
    expect(options.map((o) => o.value)).toEqual(['running', 'paused', 'stopped'])
    expect(options.map((o) => o.label)).toEqual(
      [TASK_STATUS.RUNNING, TASK_STATUS.PAUSED, TASK_STATUS.STOPPED].map(
        (v) => TASK_STATUS_CONFIG[v].label,
      ),
    )
  })

  it('notify 不再被标成「确认」（移动端那份 MODE_LABELS 只有两项，缺项全落到兜底文案）', () => {
    expect(TASK_MODE_LABELS[TASK_MODE.NOTIFY]).toBe('仅通知')
    expect(TASK_MODE_LABELS[TASK_MODE.CONFIRM]).toBe('需确认')
  })

  it('已收口文件里禁止裸写状态/模式字面串（防止再次漂移）', () => {
    const values = [...Object.values(TASK_STATUS), ...Object.values(TASK_MODE)]
    for (const path of BAN_FILES) {
      // 注释行不计（判据与全站扫描共用 codeLines）：解释行为的注释不是裸写
      const lines = codeLines(readFileSync(path, 'utf-8'))
      for (const value of values) {
        const offender = lines.find((line) => new RegExp(`['"\`]${value}['"\`]`).test(line))
        expect(offender, `${path} 裸写了 '${value}'，应改用 TASK_STATUS / TASK_MODE 常量`).toBeUndefined()
      }
    }
  })
})

// T02850：后端增删一个 TaskStatus / TaskMode 取值时，各处的**期望行为**（写在下面，供下次改动对照）：
//   · 常量表与标签表 → 前两条断言直接红（值集合等于后端枚举、标签表不多不少），必须补 TASK_STATUS_CONFIG /
//     TASK_MODE_LABELS 与（如有筛选项）taskStatusOptions/taskModeOptions 的入参；
//   · 已收口文件（CLEANED_FILES）→ 不会因为新增值而红，因为它们引用常量而非字面值；
//   · 外来词表文件（FOREIGN_VOCAB）→ **不会**因为任务域新增取值而红，除非有人在那个文件里把新任务取值
//     写进状态/模式位置（那是真漂移，第 2 条规则会拦）；登记里写的值若已从文件消失，第 3 条会红，
//     提示把登记删掉，而不是留着当永久免检牌；
//   · Onboarding 向导 → 只有显式把新值加进 taskModeOptions([...]) 才会出现在下拉里，
//     默认仍是 TASK_MODE.NOTIFY（仅通知，不会默认开始抢单）。
describe('任务域字面值的全站扫描与外来词表登记（T02850）', () => {
  const TASK_VALUES: readonly string[] = [...Object.values(TASK_STATUS), ...Object.values(TASK_MODE)]

  it('Onboarding 向导的模式选项与默认值取自常量表（此前写死 3 项字面值）', () => {
    const options = taskModeOptions([TASK_MODE.NOTIFY, TASK_MODE.CONFIRM, TASK_MODE.AUTO])
    expect(options.map((o) => o.value)).toEqual(['notify', 'confirm', 'auto'])
    // 文案必须与 TASK_MODE_LABELS 同一份：向导原先写「确认后执行 / 自动执行」，
    // 任务列表同一模式显示「需确认 / 全自动」，用户会以为是两个不同档位
    expect(options.map((o) => o.label)).toEqual(
      [TASK_MODE.NOTIFY, TASK_MODE.CONFIRM, TASK_MODE.AUTO].map((v) => TASK_MODE_LABELS[v]),
    )
    const src = srcOf('pages/Onboarding/index.tsx')
    expect(src).toMatch(/taskModeOptions\(\[TASK_MODE\.NOTIFY, TASK_MODE\.CONFIRM, TASK_MODE\.AUTO\]\)/)
    expect(src).toMatch(/useState<TaskModeValue>\(TASK_MODE\.NOTIFY\)/)
  })

  it('全站把任务取值写在状态/模式位置上的，必须已被收口或已登记词表', () => {
    const cleanedRel = new Set(
      CLEANED_FILES.map((p) => p.slice(resolve(__dirname, '../..').length + 1).replace(/\\/g, '/')),
    )
    const unregistered = scanStatusLiteralPositions(TASK_VALUES).filter((h) => {
      if (cleanedRel.has(h.file)) return false
      return vocabFor(h.file)?.values.includes(h.value) !== true
    })
    expect(
      unregistered,
      `新出现的裸写（既不在 CLEANED_FILES 也不在外来词表登记里）：\n${unregistered
        .map((h) => `${h.file}:${h.line}: ${h.text}`).join('\n')}`,
    ).toEqual([])
  })

  it('外来词表登记本身不许烂掉：文件在、词还在、且不与收口清单重叠', () => {
    for (const v of FOREIGN_VOCAB) {
      expect(exists(v.file), `${v.file} 已不在仓库里，登记要删`).toBe(true)
      const src = srcOf(v.file)
      for (const value of v.values) {
        expect(src, `${v.file} 已不再出现 '${value}'，登记应删除（domain=${v.domain}）`).toContain(`'${value}'`)
      }
      expect(
        CLEANED_FILES.some((p) => p.replace(/\\/g, '/').endsWith(v.file)),
        `${v.file} 既登记为外来词表又列进 CLEANED_FILES，两条规则互相抵消`,
      ).toBe(false)
    }
  })

  it('向 /api/tasks 提交的 mode 字面值必须是 TaskMode 成员（后端未知 mode 直接 400）', () => {
    // 移动端编辑器曾写 `mode: 'keyword'`：不在 TASK_MODE 里，而后端 api_tasks.py 对未知 mode 抛 400，
    // 等于「移动端新建任务必失败」。裸串扫描按取值集合匹配，抓不到这种**根本不是成员**的值，
    // 所以这条按位置反查：提交任务的地方只许用常量。
    const modes: readonly string[] = Object.values(TASK_MODE)
    const offenders: string[] = []
    for (const rel of listSrcFiles()) {
      const src = srcOf(rel)
      if (!src.includes('taskApi.')) continue
      src.split(/\r?\n/).forEach((line, i) => {
        for (const m of line.matchAll(/\bmode\s*(?:===|!==|:)\s*'([a-z_]+)'/g)) {
          if (!modes.includes(m[1])) {
            offenders.push(`${rel}:${i + 1}: ${line.trim().slice(0, 80)}`)
          }
        }
      })
    }
    expect(offenders, `非法 mode 字面值：\n${offenders.join('\n')}`).toEqual([])
  })

  it('扫描范围覆盖移动端编辑器（否则上一条规则形同虚设）', () => {
    expect(listSrcFiles().filter((rel) => srcOf(rel).includes('taskApi.'))).toContain(
      'mobile/pages/TaskEditor/index.tsx',
    )
  })
})
