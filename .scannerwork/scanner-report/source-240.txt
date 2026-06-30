import { Tag } from 'antd'
import { HolderOutlined } from '@ant-design/icons'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { ChannelDef } from '../constants'

interface SortableChannelItemProps {
  channel: ChannelDef
  index: number
}

export default function SortableChannelItem({ channel, index }: SortableChannelItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: channel.key,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={{
        ...style,
        display: 'flex',
        alignItems: 'center',
        padding: '8px 12px',
        marginBottom: 4,
        background: 'var(--xh-bg-spotlight)',
        border: '1px solid var(--xh-border-secondary)',
        borderRadius: 4,
      }}
    >
      <span {...attributes} {...listeners} className="drag-handle" style={{ marginRight: 8 }}>
        <HolderOutlined />
      </span>
      <Tag color="blue">{index}</Tag>
      <span style={{ fontSize: 18, marginRight: 8 }}>{channel.icon}</span>
      <span style={{ fontWeight: 500 }}>{channel.name}</span>
      <span style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', marginLeft: 8 }}>{channel.desc}</span>
      <Tag color={channel.enabled ? 'green' : 'default'} style={{ marginLeft: 'auto' }}>
        {channel.enabled ? '启用' : '禁用'}
      </Tag>
    </div>
  )
}
