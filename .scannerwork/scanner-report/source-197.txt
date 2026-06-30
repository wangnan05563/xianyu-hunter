import { useEffect, useState } from 'react'
import { Input, Space, Tag, Typography } from 'antd'
import { cronApi } from '../../api'

const { Text } = Typography

interface CronEditorProps {
  value: string
  onChange: (value: string) => void
}

const presets = [
  { label: '每分钟', value: '*/1 * * * *' },
  { label: '每 5 分钟', value: '*/5 * * * *' },
  { label: '每 10 分钟', value: '*/10 * * * *' },
  { label: '每 30 分钟', value: '*/30 * * * *' },
  { label: '每小时', value: '0 * * * *' },
  { label: '每天 0 点', value: '0 0 * * *' },
  { label: '每天 8 点', value: '0 8 * * *' },
  { label: '工作日 9 点', value: '0 9 * * 1-5' },
]

/**
 * Cron 可视化编辑器：预设选择 + 自定义输入 + 下次触发预览
 */
export default function CronEditor({ value, onChange }: CronEditorProps) {
  const [nextRuns, setNextRuns] = useState<string[]>([])
  const [error, setError] = useState<string>('')

  useEffect(() => {
    if (!value) return
    let cancelled = false
    cronApi
      .validate(value)
      .then((res) => {
        if (cancelled) return
        if (res.valid) {
          setNextRuns(res.next_runs || [])
          setError('')
        } else {
          setNextRuns([])
          setError(res.error || '表达式无效')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('校验失败')
        }
      })
    return () => {
      cancelled = true
    }
  }, [value])

  return (
    <div>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space wrap>
          <span style={{ fontSize: 12, color: '#999' }}>预设：</span>
          {presets.map((p) => (
            <Tag
              key={p.value}
              style={{ cursor: 'pointer' }}
              color={value === p.value ? 'blue' : 'default'}
              onClick={() => onChange(p.value)}
            >
              {p.label}
            </Tag>
          ))}
        </Space>

        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="5 字段 cron 表达式：分 时 日 月 周"
          style={{ fontFamily: 'monospace' }}
        />

        {error && <Text type="danger" style={{ fontSize: 12 }}>⚠ {error}</Text>}

        {nextRuns.length > 0 && (
          <div style={{ background: '#f6ffed', padding: 12, borderRadius: 6, border: '1px solid #b7eb8f' }}>
            <Text strong style={{ fontSize: 12, color: '#52c41a' }}>✓ 表达式有效，未来 5 次触发：</Text>
            <ol style={{ margin: '8px 0 0 20px', fontSize: 12, color: '#52c41a' }}>
              {nextRuns.map((t, i) => (
                <li key={i}>{new Date(t).toLocaleString('zh-CN')}</li>
              ))}
            </ol>
          </div>
        )}
      </Space>
    </div>
  )
}
