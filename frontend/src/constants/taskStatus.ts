// 任务状态/模式常量：与后端 domain/task.py 的 TaskStatus / TaskMode 同源（T02716）
// 移动端列表与详情原先各写一份 STATUS_LABELS / MODE_LABELS，桌面任务页再写第三份；
// 拼错或漏写一个值不会报错，只会让徽标静默显示英文末段（例如 notify 模式在移动端被标成「确认」）。
// 键集合由 constants/__tests__/taskStatusSingleSource.test.ts 对照后端枚举钉住。

export const TASK_STATUS = {
  RUNNING: 'running',
  PAUSED: 'paused',
  STOPPED: 'stopped',
  ERROR: 'error',
  DELETED: 'deleted',
} as const

export type TaskStatusValue = (typeof TASK_STATUS)[keyof typeof TASK_STATUS]

export const TASK_MODE = {
  AUTO: 'auto',
  SEMI_AUTO: 'semi_auto',
  CONFIRM: 'confirm',
  // 后端成员名叫 NOTIFY_ONLY，字面值是 notify —— 对齐的是字面值，不是成员名
  NOTIFY: 'notify',
} as const

export type TaskModeValue = (typeof TASK_MODE)[keyof typeof TASK_MODE]

/** 合法模式取值（用于校验 AI/模板下发的 mode，非法值回落默认模式） */
export const TASK_MODE_VALUES: readonly TaskModeValue[] = Object.values(TASK_MODE)

export const isTaskMode = (value?: string | null): value is TaskModeValue =>
  !!value && (TASK_MODE_VALUES as readonly string[]).includes(value)

/**
 * 状态 → 颜色 + 中文标签。
 * 颜色沿用原 constants/statusColors.ts 的取值（error 为本次按后端枚举补齐）。
 */
export const TASK_STATUS_CONFIG: Record<TaskStatusValue, { color: string; label: string }> = {
  [TASK_STATUS.RUNNING]: { color: 'green', label: '运行中' },
  [TASK_STATUS.PAUSED]: { color: 'orange', label: '已暂停' },
  [TASK_STATUS.STOPPED]: { color: 'default', label: '已停止' },
  [TASK_STATUS.ERROR]: { color: 'red', label: '出错' },
  [TASK_STATUS.DELETED]: { color: 'red', label: '已删除' },
}

export const TASK_MODE_LABELS: Record<TaskModeValue, string> = {
  [TASK_MODE.AUTO]: '全自动',
  [TASK_MODE.SEMI_AUTO]: '半自动',
  [TASK_MODE.CONFIRM]: '需确认',
  [TASK_MODE.NOTIFY]: '仅通知',
}

/** 生成筛选项：可选状态与标签共用同一份映射，避免各页面再手写 value/label 对 */
export function taskStatusOptions(
  values: readonly TaskStatusValue[],
): { value: TaskStatusValue; label: string }[] {
  return values.map((value) => ({ value, label: TASK_STATUS_CONFIG[value].label }))
}

/** 未知值兜底显示原文，而不是猜一个中文标签——猜出来的标签会把「不可识别」伪装成「已识别」 */
export const taskStatusLabel = (status?: string | null) =>
  status ? TASK_STATUS_CONFIG[status as TaskStatusValue]?.label || status : '—'

export const taskStatusColor = (status?: string | null) =>
  status ? TASK_STATUS_CONFIG[status as TaskStatusValue]?.color : undefined

export const taskModeLabel = (mode?: string | null) =>
  mode ? TASK_MODE_LABELS[mode as TaskModeValue] || mode : '—'
