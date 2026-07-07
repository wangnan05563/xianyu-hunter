import { useState } from 'react'
import { Tag, Input, Space } from 'antd'
import { PlusOutlined, CloseOutlined } from '@ant-design/icons'

interface TagEditorProps {
  readonly value: string[]
  readonly onChange: (value: string[]) => void
  readonly placeholder?: string
  readonly color?: string
}

/**
 * 标签编辑器：输入 + 回车添加 + 点击删除
 * 用于关键词、排除词等列表型配置
 */
export default function TagEditor({ value = [], onChange, placeholder = '输入后回车添加', color = 'blue' }: TagEditorProps) {
  const [input, setInput] = useState('')

  const add = () => {
    const v = input.trim()
    if (v && !value.includes(v)) {
      onChange([...value, v])
    }
    setInput('')
  }

  const remove = (tag: string) => {
    onChange(value.filter((t) => t !== tag))
  }

  return (
    <div>
      <Space size={[4, 8]} wrap>
        {value.map((tag) => (
          <Tag
            key={tag}
            color={color}
            closable
            closeIcon={<CloseOutlined />}
            onClose={(e) => {
              e.preventDefault()
              remove(tag)
            }}
            style={{ padding: '2px 8px' }}
          >
            {tag}
          </Tag>
        ))}
        <Input
          size="small"
          style={{ width: 160 }}
          value={input}
          placeholder={placeholder}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={add}
          suffix={<PlusOutlined onClick={add} style={{ cursor: 'pointer', color: '#999' }} />}
        />
      </Space>
    </div>
  )
}
