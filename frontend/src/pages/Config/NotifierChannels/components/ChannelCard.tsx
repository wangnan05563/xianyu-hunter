import { Card, Switch, Input, Button, Space, Tag, Tooltip, Typography } from 'antd'
import { SendOutlined, StarFilled, LinkOutlined } from '@ant-design/icons'
import type { AppConfig } from '../../../../api'
import type { ChannelDef } from '../constants'
import { pricingMeta } from '../constants'

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
  const meta = pricingMeta[ch.pricing]

  return (
    <Card
      size="small"
      className={`channel-card ${!ch.enabled ? 'channel-card-disabled' : ''}`}
      style={{ border: ch.enabled ? '1px solid #1677ff' : '1px solid #d9d9d9' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Space align="start">
          <span style={{ fontSize: 20, lineHeight: '24px' }}>{ch.icon}</span>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 600 }}>{ch.name}</span>
              <Tag color={meta.color} style={{ fontSize: 10, margin: 0, lineHeight: '18px' }}>
                {meta.label}
              </Tag>
              {ch.recommended && (
                <Tooltip title="免费且无每日限制的微信推送渠道，推荐优先使用">
                  <Tag color="gold" icon={<StarFilled />} style={{ fontSize: 10, margin: 0, lineHeight: '18px' }}>
                    推荐
                  </Tag>
                </Tooltip>
              )}
            </div>
            <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', marginTop: 2 }}>
              {ch.desc}
              {ch.limits && (
                <span style={{ marginLeft: 4, color: 'var(--xh-text-secondary)' }}>· {ch.limits}</span>
              )}
            </div>
          </div>
        </Space>
        <Switch checked={ch.enabled} onChange={(v) => onToggle(ch.key, v)} />
      </div>

      {ch.enabled && (
        <div style={{ marginTop: 12 }}>
          {ch.obtainUrl && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
              <Typography.Link
                href={ch.obtainUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 12 }}
              >
                获取 <LinkOutlined />
              </Typography.Link>
            </div>
          )}
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
