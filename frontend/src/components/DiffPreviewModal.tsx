import { type CSSProperties } from 'react'
import { Modal, Table, Button, Tag } from 'antd'
import type { DiffChange } from '../stores/configStore'
import { useConfigStore } from '../stores/configStore'
import { ParamCalculatorPanel } from './ParamCalculator'

// 单元格样式：长 JSON 字符串可换行（wordBreak 防单 token 撑爆列宽）
const codeStyle: CSSProperties = {
  display: 'block',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-all',
  fontSize: 12,
  fontFamily: 'var(--xh-font-mono, monospace)',
  color: 'var(--xh-text-secondary)',
  background: 'var(--xh-bg-code, #f5f5f5)',
  padding: '4px 6px',
  borderRadius: 3,
  maxHeight: 240,
  overflow: 'auto',
}

interface DiffPreviewModalProps {
  // 组件内部不应修改 props：加 readonly 防止意外赋值，符合 React 单向数据流
  readonly open: boolean
  readonly diffChanges: DiffChange[]
  readonly loading: boolean
  readonly onCancel: () => void
  readonly onConfirm: () => void
}

// 单元格值格式化：null/undefined → '-'；对象/数组 → JSON 缩进；字符串原样返回；其他走 String()。
// 提取为独立函数避免 JSX render 回调中出现嵌套三元（SonarQube S3358），并通过显式 if-链
// 让 SonarQube 识别 v 在 String() 处已排除对象分支，避免 [object Object] 警告（S6551）。
function formatCellValue(v: unknown): string {
  if (v == null) return '-'
  if (typeof v === 'object') return JSON.stringify(v, null, 2)
  if (typeof v === 'string') return v
  return String(v) // NOSONAR - 前置 typeof 已排除 object 分支，此处 v 只可能是 number/boolean/symbol
}

// 递归展平嵌套配置对象为扁平 dict
// 为什么这么做：后端 config_rules 用扁平字段名（如 empty_result_skip / batch_size）做查找，
// AppConfig 是嵌套结构（cache.empty_result_skip / batch_refresh.batch_size），
// 展平后字段名匹配后端期望，无需修改后端规则代码
// 字段名冲突容忍：AppConfig 的叶子字段名在段间唯一（如 batch_size 只在 batch_refresh 段），
// 万一冲突，后取值覆盖，对规则校验影响可控
function flattenConfig(obj: Record<string, unknown>, prefix = ''): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj)) {
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      // 嵌套对象递归展平，不带前缀（直接用叶子字段名）
      Object.assign(result, flattenConfig(value as Record<string, unknown>))
    } else {
      // 叶子字段：直接用 key 作为字段名，忽略 prefix
      // 这样后端 f.get('empty_result_skip') 能匹配 cache.empty_result_skip
      result[key] = value
    }
    // prefix 参数保留为预留扩展点，当前不使用（避免字段名带路径前缀）
    // 故意引用避免 TypeScript 未使用参数警告；SonarQube S3735 要求不使用 void 操作符
    if (prefix) { /* noop */ }
  }
  return result
}

/**
 * 配置变更预览弹窗（5 个配置页共享）
 *
 * 统一处理 Diff 预览的样式问题：
 * - 弹窗宽度 960 容纳 cookie_management 等长 JSON
 * - 表格 scroll.x 启用横向滚动，避免操作列被弹窗右边界遮挡
 * - 单元格用 <code> + whiteSpace: pre-wrap 展示对象/数组，保持可读性
 * - 路径列固定宽度，操作列固定 90px，剩余空间留给原值/新值列
 *
 * 集成参数计算器：弹窗打开时自动校验当前 configStore 中的待保存配置，
 * 在用户确认提交前展示分级建议。校验在 ParamCalculatorPanel 内部完成，
 * 通过 useConfigStore 获取当前 config，无需各配置页面单独传入。
 */
export function DiffPreviewModal({
  open,
  diffChanges,
  loading,
  onCancel,
  onConfirm,
}: DiffPreviewModalProps) {
  // 从 configStore 获取当前待保存的配置（用户修改后、未提交前的状态）
  // 为什么在这里取：所有配置页共享此组件，统一获取避免每个页面单独传入
  const config = useConfigStore((s) => s.config)

  // 展平嵌套配置为扁平 dict，传给参数计算器做规则校验
  // 为什么用 config 而非 diffChanges：config 是完整待保存状态，规则可基于完整配置做交叉校验
  const validationFields = config
    ? flattenConfig(config as unknown as Record<string, unknown>)
    : {}

  return (
    <Modal
      title="配置变更预览"
      open={open}
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button key="confirm" type="primary" loading={loading} onClick={onConfirm}>
          确认保存
        </Button>,
      ]}
      width={960}
      styles={{ body: { maxHeight: '60vh', overflow: 'auto' } }}
    >
      <Table
        dataSource={diffChanges}
        rowKey="path"
        pagination={false}
        size="small"
        scroll={{ x: 800 }}
        columns={[
          { title: '路径', dataIndex: 'path', key: 'path', width: 200, fixed: 'left' },
          {
            title: '原值',
            dataIndex: 'old_value',
            key: 'old_value',
            width: 280,
            render: (v: unknown) => {
              const text = formatCellValue(v)
              return (
                <code style={codeStyle}>
                  {text || '""'}
                </code>
              )
            },
          },
          {
            title: '新值',
            dataIndex: 'new_value',
            key: 'new_value',
            render: (v: unknown) => {
              const text = formatCellValue(v)
              return (
                <code style={codeStyle}>
                  {text || '""'}
                </code>
              )
            },
          },
          {
            title: '操作',
            dataIndex: 'op',
            key: 'op',
            width: 90,
            fixed: 'right',
            render: (op: string) => {
              // op → 颜色/文案映射，未知 op 走 default 分支
              const opColorMap: Record<string, string> = { add: 'green', delete: 'red' }
              const opLabelMap: Record<string, string> = { add: '新增', delete: '删除' }
              return (
                <Tag color={opColorMap[op] ?? 'orange'}>
                  {opLabelMap[op] ?? '修改'}
                </Tag>
              )
            },
          },
        ]}
      />

      {/* 参数计算器：提交前对当前待保存配置做规则校验
          仅在有变更时显示（diffChanges 非空表示用户已修改且准备保存）
          validateOnMount=true：弹窗打开即触发校验，无需用户额外操作 */}
      {open && diffChanges.length > 0 && Object.keys(validationFields).length > 0 && (
        <ParamCalculatorPanel
          scenario="config_update"
          fields={validationFields}
          validateOnMount
          bordered
        />
      )}
    </Modal>
  )
}
