// frontend/src/components/DangerSummary.tsx
// 危险操作确认文案的单一渲染口径：动作 + 影响范围 + 数量 + 恢复成本 四要素。
// 规范正文见 docs/standards/危险操作文案规范.md（T02573）。
import { Modal, Typography } from 'antd'
import { ExclamationCircleOutlined } from '@ant-design/icons'

const { Text } = Typography

export interface DangerCopy {
  /** 确认框标题，例如「确认清理缓存？」；缺省用通用标题 */
  readonly title?: string
  /** ① 动作：要做的是什么（动词 + 对象），不允许只写「此操作」 */
  readonly action: string
  /** ② 影响范围：波及哪些数据/资源，并明确「不包含」什么 */
  readonly scope: string
  /** ③ 数量：真实统计值；拿不到时传 null/''，会渲染成显式「未能预先统计」而不是省略 */
  readonly count?: string | number | null
  /** ④ 恢复成本：怎么撤销/回滚，或为什么不可恢复 */
  readonly recovery: string
}

/** 数量拿不到时的固定话术——宁可明说不知道，也不给出看起来完整的假数字 */
export const COUNT_UNKNOWN = '未能预先统计（以预览/执行结果为准）'

/** 四要素标签，测试与规范文档共用同一份 */
export const DANGER_FIELD_LABELS = ['动作', '影响范围', '数量', '恢复成本'] as const

/** 返回缺失的必填要素（数量允许「未知」占位，不算缺失） */
export function missingDangerFields(copy: DangerCopy): string[] {
  const missing: string[] = []
  if (!copy.action?.trim()) missing.push('动作')
  if (!copy.scope?.trim()) missing.push('影响范围')
  if (!copy.recovery?.trim()) missing.push('恢复成本')
  return missing
}

export default function DangerSummary(copy: DangerCopy) {
  const missing = missingDangerFields(copy)
  // 开发期把不合规文案暴露出来，避免新页面悄悄少写一个要素（规范第 4 条）
  if (missing.length > 0) {
    console.error(`[危险操作文案规范] 缺少要素：${missing.join('、')}`, copy)
  }
  const count = copy.count == null || copy.count === '' ? COUNT_UNKNOWN : String(copy.count)
  const rows: [string, string][] = [
    ['动作', copy.action],
    ['影响范围', copy.scope],
    ['数量', count],
    ['恢复成本', copy.recovery],
  ]
  return (
    <div style={{ marginTop: 4 }}>
      {rows.map(([label, value]) => (
        <div key={label} style={{ marginBottom: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>{label}：</Text>
          <Text style={{ fontSize: 13 }}>{value}</Text>
        </div>
      ))}
    </div>
  )
}

/** 用四要素文案替换原生 confirm；resolve(true) 表示用户确认执行 */
export function confirmDanger(copy: DangerCopy): Promise<boolean> {
  return new Promise((resolve) => {
    Modal.confirm({
      title: copy.title ?? '确认执行该操作？',
      icon: <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />,
      width: 560,
      content: <DangerSummary {...copy} />,
      okText: '确认执行',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    })
  })
}
