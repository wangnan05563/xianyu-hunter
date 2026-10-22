// 任务的排除词 / 搜索过滤以 JSON 字符串入库（如 ["抽奖","拼单"]），
// 直接渲染会让用户读原始 JSON。已知字符串数组按标签展示；
// 其他可解析 JSON 格式化后给复制入口；解析失败的原样显示，不静默吞成「无」。
import { Space, Tag, Typography } from 'antd'

type Parsed =
  | { kind: 'array'; items: string[] }
  | { kind: 'json'; text: string }
  | { kind: 'text'; text: string }
  | { kind: 'empty' }

function parse(raw: unknown): Parsed {
  if (Array.isArray(raw)) {
    return { kind: 'array', items: raw.map((v) => String(v)) }
  }
  if (typeof raw !== 'string' || !raw.trim()) return { kind: 'empty' }
  try {
    const value: unknown = JSON.parse(raw)
    if (Array.isArray(value)) {
      return { kind: 'array', items: value.map((v) => String(v)) }
    }
    return { kind: 'json', text: JSON.stringify(value, null, 2) }
  } catch {
    return { kind: 'text', text: raw }
  }
}

export default function JsonListField({ raw, emptyText = '无' }: { raw: unknown; emptyText?: string }) {
  const parsed = parse(raw)
  if (parsed.kind === 'empty' || (parsed.kind === 'array' && parsed.items.length === 0)) {
    return <>{emptyText}</>
  }
  if (parsed.kind === 'array') {
    return (
      <Space size={[4, 4]} wrap>
        {parsed.items.map((item, i) => (
          <Tag key={`${item}-${i}`}>{item}</Tag>
        ))}
      </Space>
    )
  }
  if (parsed.kind === 'json') {
    return (
      <Typography.Paragraph code copyable={{ text: parsed.text }} style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
        {parsed.text}
      </Typography.Paragraph>
    )
  }
  return <>{parsed.text}</>
}
