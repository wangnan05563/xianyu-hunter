import { Card, Switch, Input, Button, Space } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import type { AppConfig } from '../../../../api'
import type { ChannelDef } from '../constants'

interface ChannelCardProps {
  channel: ChannelDef
  config: AppConfig
  // 当前卡片是否处于测试中
  testing: boolean
  // 是否有任意卡片处于测试中（用于禁用其他卡片的测试按钮）
  anyTesting: boolean
  onToggle: (key: string, enabled: boolean) => void
  onFieldChange: (channelKey: string, fieldKey: string, value: string) => void
  onTest: (channelKey: string) => void
}

export default function ChannelCard({
  channel: ch,
  config,
  testing,
  anyTesting,
  onToggle,
  onFieldChange,
  onTest,
}: ChannelCardProps) {
  return (
    <Card
      size="small"
      className={`channel-card ${!ch.enabled ? 'channel-card-disabled' : ''}`}
      style={{ border: ch.enabled ? '1px solid #1677ff' : '1px solid #d9d9d9' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <span style={{ fontSize: 20 }}>{ch.icon}</span>
          <div>
            <div style={{ fontWeight: 600 }}>{ch.name}</div>
            <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>{ch.desc}</div>
          </div>
        </Space>
        <Switch checked={ch.enabled} onChange={(v) => onToggle(ch.key, v)} />
      </div>

      {ch.enabled && (
        <div style={{ marginTop: 12 }}>
          {ch.fields.map((field) => (
            <div key={field.key} style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 12, color: 'var(--xh-text-secondary)', marginBottom: 4 }}>{field.label}</div>
              <Input.Password
                placeholder={field.placeholder}
                value={(config as unknown as Record<string, unknown>)[field.key] as string}
                onChange={(e) => onFieldChange(ch.key, field.key, e.target.value)}
                size="small"
              />
            </div>
          ))}
          <Button
            size="small"
            type="dashed"
            icon={<SendOutlined />}
            onClick={() => onTest(ch.key)}
            block
            loading={testing}
            disabled={anyTesting && !testing}
          >
            {testing ? '发送中...' : '发送测试'}
          </Button>
        </div>
      )}
    </Card>
  )
}
