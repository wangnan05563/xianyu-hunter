import { Card, Switch, Input, Space, Tag, Tooltip, Typography } from 'antd'
import { SendOutlined, StarFilled, LinkOutlined } from '@ant-design/icons'
import { TipButton } from '@/components/TipButton'
import type { AppConfig } from '../../../../api'
import type { ChannelDef } from '../constants'
import { pricingMeta } from '../constants'

interface ChannelCardProps {
  // 标记 readonly 以表达「父级传入后子组件不应修改」的契约（SonarQube S6759）
  readonly channel: ChannelDef
  readonly config: AppConfig
  // 当前卡片是否处于测试中
  readonly testing: boolean
  // 是否有任意卡片处于测试中（用于禁用其他卡片的测试按钮）
  readonly anyTesting: boolean
  readonly onToggle: (key: string, enabled: boolean) => void
  readonly onFieldChange: (channelKey: string, fieldKey: string, value: string) => void
  readonly onTest: (channelKey: string) => void
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
      // 反转条件避免否定式，提升可读性（SonarQube S7735）
      className={`channel-card ${ch.enabled ? '' : 'channel-card-disabled'}`}
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

      {ch.obtainUrl && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
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
          <TipButton
            tip="向该渠道发送测试推送消息"
            size="small"
            type="dashed"
            icon={<SendOutlined />}
            onClick={() => onTest(ch.key)}
            block
            loading={testing}
            disabled={anyTesting && !testing}
          >
            {testing ? '发送中...' : '发送测试'}
          </TipButton>
        </div>
      )}
    </Card>
  )
}
