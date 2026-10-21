import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  TASK_MODE,
  TASK_MODE_LABELS,
  TASK_STATUS,
  TASK_STATUS_CONFIG,
  taskStatusOptions,
} from '../taskStatus'

// T02716：移动端任务页自己写了 STATUS_LABELS / MODE_LABELS（桌面任务列表再写一份，
// 且两边取值不一样——移动端把 notify 模式统一标成「确认」、把 stopped 任务标成「已暂停」）。
// 这类错不会报错，只是把状态说反，所以把「前端常量表 ↔ 后端枚举」钉死，
// 并对已收口文件禁止再出现裸的状态/模式字面串。写法沿用 T02693 的 orderStatusSingleSource。

const BACKEND_TASK_DOMAIN = resolve(
  __dirname,
  '../../../../backend/xianyu_hunter/domain/task.py',
)

/** 已收口的任务域文件：只允许通过 TASK_STATUS / TASK_MODE 常量引用取值 */
const CLEANED_FILES = [
  resolve(__dirname, '../../mobile/pages/Tasks/index.tsx'),
  resolve(__dirname, '../../mobile/pages/Tasks/TaskDetail.tsx'),
  resolve(__dirname, '../../pages/Tasks/TaskList.tsx'),
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

  it('已清理文件里禁止裸写状态/模式字面串（防止再次漂移）', () => {
    const values = [...Object.values(TASK_STATUS), ...Object.values(TASK_MODE)]
    for (const path of CLEANED_FILES) {
      const src = readFileSync(path, 'utf-8')
      for (const value of values) {
        expect(
          src,
          `${path} 裸写了 '${value}'，应改用 TASK_STATUS / TASK_MODE 常量`,
        ).not.toMatch(new RegExp(`['"\`]${value}['"\`]`))
      }
    }
  })
})
