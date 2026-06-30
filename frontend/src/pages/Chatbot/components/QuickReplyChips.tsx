import { Tag, Space } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import type { FAQ } from '../types'

interface Props {
  quickReplies: FAQ[]
  onSelect: (question: string) => void  // 点击填充到输入框
}

// 输入区上方的快捷回复 Chip 列表
// 设计：横向滚动 + 马卡龙配色（与 --cb-pink-light 保持一致）
// 数据源：FAQ 中 category 含"快捷"字样的项（见 index.tsx 过滤逻辑）
export default function QuickReplyChips({ quickReplies, onSelect }: Props) {
  if (quickReplies.length === 0) return null
  return (
    <div className="cb-quick-replies">
      <ThunderboltOutlined className="cb-quick-replies-icon" />
      <Space size={6} wrap className="cb-quick-replies-tags">
        {quickReplies.map((faq) => (
          <Tag
            key={faq.id}
            className="cb-quick-reply-tag"
            onClick={() => onSelect(faq.question)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onSelect(faq.question)
            }}
          >
            {faq.question}
          </Tag>
        ))}
      </Space>
    </div>
  )
}
