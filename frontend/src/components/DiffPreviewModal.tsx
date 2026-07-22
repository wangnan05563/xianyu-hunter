import { type CSSProperties } from 'react'
import { Modal, Table, Button, Tag } from 'antd'
import type { DiffChange } from '../stores/configStore'

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

/**
 * 配置变更预览弹窗（5 个配置页共享）
 *
 * 统一处理 Diff 预览的样式问题：
 * - 弹窗宽度 960 容纳 cookie_management 等长 JSON
 * - 表格 scroll.x 启用横向滚动，避免操作列被弹窗右边界遮挡
 * - 单元格用 <code> + whiteSpace: pre-wrap 展示对象/数组，保持可读性
 * - 路径列固定宽度，操作列固定 90px，剩余空间留给原值/新值列
 */
export function DiffPreviewModal({
  open,
  diffChanges,
  loading,
  onCancel,
  onConfirm,
}: DiffPreviewModalProps) {
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
    </Modal>
  )
}
