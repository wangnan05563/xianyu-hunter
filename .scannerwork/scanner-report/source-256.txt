import { Modal, Checkbox, Button, Space, Tag, Tooltip, Empty } from 'antd'
import { HolderOutlined, UndoOutlined, LockOutlined, EyeInvisibleOutlined } from '@ant-design/icons'
import { DndContext, closestCenter, DragEndEvent } from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { ColumnConfig } from '../../../hooks/useColumnConfig'

interface ColumnSettingsModalProps {
  open: boolean
  onClose: () => void
  definitions: ColumnConfig[]
  order: string[]
  hidden: Set<string>
  onToggleHidden: (key: string) => void
  onMove: (activeKey: string, overKey: string) => void
  onReset: () => void
}

/** 可拖拽的列项：用 dnd-kit 的 useSortable 实现拖拽 */
function SortableColumnItem({
  config,
  isHidden,
  locked,
  onToggle,
}: {
  config: ColumnConfig
  isHidden: boolean
  locked: boolean
  onToggle: (key: string) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: config.key,
  })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    display: 'flex',
    alignItems: 'center',
    padding: '8px 12px',
    marginBottom: 4,
    background: 'var(--xh-bg-spotlight, #fafafa)',
    border: '1px solid var(--xh-border-secondary, #f0f0f0)',
    borderRadius: 4,
    cursor: 'default',
  }

  return (
    <div ref={setNodeRef} style={style}>
      {/* 拖拽手柄：仅此处响应拖拽，避免点击 checkbox 时触发拖拽 */}
      <span
        {...attributes}
        {...listeners}
        style={{ cursor: 'grab', marginRight: 8, color: 'var(--xh-text-tertiary, #999)' }}
      >
        <HolderOutlined />
      </span>
      <Checkbox
        checked={!isHidden}
        disabled={locked}
        onChange={() => onToggle(config.key)}
        style={{ marginRight: 8 }}
      />
      <span style={{ flex: 1, fontWeight: 500 }}>{config.label}</span>
      {locked && (
        <Tooltip title="核心列，不可隐藏">
          <LockOutlined style={{ color: '#faad14' }} />
        </Tooltip>
      )}
      {!locked && isHidden && (
        <Tag color="default" icon={<EyeInvisibleOutlined />}>已隐藏</Tag>
      )}
    </div>
  )
}

export default function ColumnSettingsModal({
  open,
  onClose,
  definitions,
  order,
  hidden,
  onToggleHidden,
  onMove,
  onReset,
}: ColumnSettingsModalProps) {
  // 按 order 顺序排列列定义
  const defMap = new Map(definitions.map((d) => [d.key, d]))
  const orderedConfigs = order
    .map((k) => defMap.get(k))
    .filter((d): d is ColumnConfig => Boolean(d))

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (over && active.id !== over.id) {
      onMove(String(active.id), String(over.id))
    }
  }

  return (
    <Modal
      title="列配置"
      open={open}
      onCancel={onClose}
      width={480}
      footer={
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Button icon={<UndoOutlined />} onClick={onReset}>
            恢复默认
          </Button>
          <Button type="primary" onClick={onClose}>
            完成
          </Button>
        </Space>
      }
    >
      <div style={{ marginBottom: 8, color: 'var(--xh-text-tertiary, #999)', fontSize: 12 }}>
        拖拽 <HolderOutlined /> 调整列顺序；勾选复选框控制列显示/隐藏
      </div>
      {orderedConfigs.length === 0 ? (
        <Empty description="无可配置列" />
      ) : (
        <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={order} strategy={verticalListSortingStrategy}>
            {orderedConfigs.map((config) => (
              <SortableColumnItem
                key={config.key}
                config={config}
                isHidden={hidden.has(config.key)}
                locked={!!config.locked}
                onToggle={onToggleHidden}
              />
            ))}
          </SortableContext>
        </DndContext>
      )}
    </Modal>
  )
}
