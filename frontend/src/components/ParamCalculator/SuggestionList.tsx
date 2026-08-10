import { Alert, Tag, Space, Typography, Tooltip } from 'antd'
import {
  CheckCircleOutlined,
  InfoCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import type { Suggestion, Severity, RuleCategory } from '../../api'

// 参数计算器建议列表：按 severity 分组展示校验结果
//
// 设计：
// - 顶级 Alert 聚合"是否有阻断性问题"，明细列表展开具体建议
// - 无建议时显示 Empty 占位，避免空白界面
// - 每条建议显示 message + fix_hint + 关联字段 Tag

const { Text } = Typography

// severity -> Alert type / 图标 / 标题 / 颜色 映射
// 为什么不用 record：枚举顺序保持 ERROR > WARNING > INFO，便于按级别排序
const SEVERITY_META: Record<Severity, {
  alertType: 'error' | 'warning' | 'info'
  icon: React.ReactNode
  title: string
  color: string
}> = {
  error: {
    alertType: 'error',
    icon: <CloseCircleOutlined />,
    title: '阻断性问题',
    color: 'red',
  },
  warning: {
    alertType: 'warning',
    icon: <WarningOutlined />,
    title: '潜在风险',
    color: 'orange',
  },
  info: {
    alertType: 'info',
    icon: <InfoCircleOutlined />,
    title: '优化建议',
    color: 'blue',
  },
}

// 规则类别中文标签（用于 Tag 显示）
const CATEGORY_LABEL: Record<RuleCategory, string> = {
  accuracy: '准确性',
  stability: '稳定性',
  efficiency: '效率',
}

export interface SuggestionListProps {
  /** 建议列表（建议按 severity 降序传入，引擎已排序） */
  suggestions: Suggestion[]
  /** 是否正在校验中（用于显示 loading） */
  isValidating?: boolean
  /** 最近一次校验耗时（毫秒），用于性能监控展示 */
  elapsedMs?: number
  /** 是否折叠为单条 Alert（true）或展开明细列表（false） */
  compact?: boolean
  /** 空状态时的提示文案 */
  emptyText?: string
}

// 内部排序辅助：确保 ERROR 优先（防御性：调用方可能未排序）
const SEVERITY_ORDER: Record<Severity, number> = {
  error: 0,
  warning: 1,
  info: 2,
}

// severity 转 CSS 变量名：提取为独立函数避免嵌套三元（SonarQube S3358）
function severityBg(s: Severity): string {
  if (s === 'error') return 'danger'
  if (s === 'warning') return 'warning'
  return 'info'
}

export function SuggestionList({
  suggestions,
  isValidating = false,
  elapsedMs,
  compact = false,
  emptyText = '参数配置无异常',
}: Readonly<SuggestionListProps>) {
  // 校验中：显示加载提示
  if (isValidating) {
    return (
      <Alert
        type="info"
        showIcon
        message="正在校验参数..."
        style={{ borderRadius: 8 }}
      />
    )
  }

  // 无建议：显示通过状态
  if (suggestions.length === 0) {
    return (
      <Alert
        type="success"
        showIcon
        icon={<CheckCircleOutlined />}
        message={emptyText}
        description={
          elapsedMs != null && elapsedMs > 0
            ? <Text type="secondary" style={{ fontSize: 12 }}>校验耗时 {elapsedMs}ms</Text>
            : undefined
        }
        style={{ borderRadius: 8 }}
      />
    )
  }

  // 排序：ERROR 优先
  const sorted = [...suggestions].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  )

  // 最高级别用于顶级 Alert
  const topSeverity = sorted[0].severity
  const topMeta = SEVERITY_META[topSeverity]
  const errorCount = sorted.filter((s) => s.severity === 'error').length
  const warningCount = sorted.filter((s) => s.severity === 'warning').length
  const infoCount = sorted.filter((s) => s.severity === 'info').length

  // 顶级标题：分级计数
  const titleParts: string[] = []
  if (errorCount > 0) titleParts.push(`${errorCount} 项阻断`)
  if (warningCount > 0) titleParts.push(`${warningCount} 项警告`)
  if (infoCount > 0) titleParts.push(`${infoCount} 项建议`)
  const title = titleParts.join(' · ')

  // compact 模式：单条 Alert，描述列出全部建议
  if (compact) {
    return (
      <Alert
        type={topMeta.alertType}
        showIcon
        icon={topMeta.icon}
        message={title}
        description={
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            {sorted.map((s, i) => (
              <li key={`${s.code}-${i}`}>
                <Text>{s.message}</Text>
                {s.fix_hint && (
                  <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                    → {s.fix_hint}
                  </Text>
                )}
              </li>
            ))}
          </ul>
        }
        style={{ borderRadius: 8 }}
      />
    )
  }

  // 默认模式：顶级 Alert + 分级明细
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <Alert
        type={topMeta.alertType}
        showIcon
        icon={topMeta.icon}
        message={title}
        description={
          elapsedMs != null && elapsedMs > 0 ? (
            <Text type="secondary" style={{ fontSize: 12 }}>
              校验耗时 {elapsedMs}ms（响应预算 300ms）
            </Text>
          ) : undefined
        }
        style={{ borderRadius: 8 }}
      />

      {/* 明细列表 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {sorted.map((s, i) => {
          const meta = SEVERITY_META[s.severity]
          return (
            <div
              key={`${s.code}-${i}`}
              style={{
                padding: '8px 12px',
                background: `var(--xh-bg-${severityBg(s.severity)}, rgba(0,0,0,0.02))`,
                borderLeft: `3px solid var(--xh-${severityBg(s.severity)}-border, ${meta.color})`,
                borderRadius: 4,
              }}
            >
              <Space size={6} wrap>
                <Tag color={meta.color} style={{ margin: 0 }}>
                  {meta.icon} {meta.title}
                </Tag>
                <Tag color="default" style={{ margin: 0 }}>
                  {CATEGORY_LABEL[s.category]}
                </Tag>
                {/* 关联字段 Tooltip：便于用户定位到具体输入框 */}
                {s.affected_fields.length > 0 && (
                  <Tooltip title="关联字段">
                    <Space size={4}>
                      {s.affected_fields.map((f) => (
                        <Tag key={f} color="default" style={{ margin: 0, fontSize: 11 }}>
                          {f}
                        </Tag>
                      ))}
                    </Space>
                  </Tooltip>
                )}
              </Space>
              <div style={{ marginTop: 4 }}>
                <Text>{s.message}</Text>
              </div>
              {s.fix_hint && (
                <div style={{ marginTop: 2 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    修复建议：{s.fix_hint}
                  </Text>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default SuggestionList
