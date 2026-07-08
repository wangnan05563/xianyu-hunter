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
  open: boolean
  diffChanges: DiffChange[]
  loading: boolean
  onCancel: () => void
  onConfirm: () => void
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
              if (v == null) return '-'
              // 对象/数组用 JSON.stringify 缩进展示，避免单行 JSON 阅读困难
              const text = typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)
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
              if (v == null) return '-'
              const text = typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)
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
