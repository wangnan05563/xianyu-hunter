import { useEffect, useState } from 'react'
import {
  Card,
  Switch,
  Input,
  Button,
  Space,
  message,
  Row,
  Col,
  Slider,
  TimePicker,
  Checkbox,
  Divider,
  Tag,
} from 'antd'
import {
  SaveOutlined,
  UndoOutlined,
  HolderOutlined,
  BellOutlined,
  SendOutlined,
} from '@ant-design/icons'
import { DndContext, closestCenter, DragEndEvent } from '@dnd-kit/core'
import { SortableContext, useSortable, arrayMove, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import dayjs from 'dayjs'
import { useConfigStore } from '../../stores/configStore'
import api from '../../api/client'
import type { AppConfig } from '../../api'

// 渠道定义
interface ChannelDef {
  key: string
  name: string
  icon: string
  desc: string
  enabled: boolean
  fields: { key: string; label: string; placeholder: string; secret?: boolean }[]
}

const defaultChannels: ChannelDef[] = [
  {
    key: 'serverchan',
    name: 'Server酱',
    icon: '💬',
    desc: '微信推送',
    enabled: true,
    fields: [{ key: 'serverchan_send_key', label: 'SendKey', placeholder: 'SCT123456...' }],
  },
  {
    key: 'pushplus',
    name: 'PushPlus',
    icon: '📱',
    desc: '微信推送（支持一对多）',
    enabled: true,
    fields: [{ key: 'pushplus_token', label: 'Token', placeholder: 'abc123...' }],
  },
  {
    key: 'bark',
    name: 'Bark',
    icon: '🍎',
    desc: 'iOS 推送',
    enabled: true,
    fields: [
      { key: 'bark_server', label: 'Server URL', placeholder: 'https://api.day.app' },
      { key: 'bark_key', label: 'Device Key', placeholder: 'bark device key', secret: true },
    ],
  },
  {
    key: 'telegram',
    name: 'Telegram',
    icon: '✈️',
    desc: '跨平台推送',
    enabled: false,
    fields: [
      { key: 'telegram_bot_token', label: 'Bot Token', placeholder: '123456:ABC-DEF...', secret: true },
      { key: 'telegram_chat_id', label: 'Chat ID', placeholder: '@channel 或 123456789' },
    ],
  },
  {
    key: 'wecom',
    name: '企业微信',
    icon: '🏢',
    desc: '企业群推送',
    enabled: false,
    fields: [{ key: 'wecom_webhook', label: 'Webhook URL', placeholder: 'https://qyapi.weixin.qq.com/...' }],
  },
  {
    key: 'dingtalk',
    name: '钉钉',
    icon: '📌',
    desc: '钉钉群推送',
    enabled: false,
    fields: [
      { key: 'dingtalk_webhook', label: 'Webhook URL', placeholder: 'https://oapi.dingtalk.com/...' },
      { key: 'dingtalk_secret', label: 'Secret', placeholder: 'SEC...', secret: true },
    ],
  },
  {
    key: 'webhook',
    name: '自定义 Webhook',
    icon: '🔗',
    desc: '自定义 HTTP 推送',
    enabled: false,
    fields: [{ key: 'webhook_url', label: 'URL', placeholder: 'https://your-server.com/hook' }],
  },
]

// 事件类型定义（12 种）
const eventTypes = [
  { key: 'TASK_STARTED', label: '任务启动', severity: 'info' },
  { key: 'TASK_STOPPED', label: '任务停止', severity: 'info' },
  { key: 'TASK_PAUSED', label: '任务暂停', severity: 'info' },
  { key: 'TASK_SEARCH_DONE', label: '搜索完成', severity: 'info' },
  { key: 'ITEM_FOUND', label: '发现新商品', severity: 'info' },
  { key: 'EVAL_PASSED', label: '评估通过', severity: 'important', defaultNotify: true },
  { key: 'EVAL_REJECTED', label: '评估拒绝', severity: 'info' },
  { key: 'BUY_SUCCEEDED', label: '抢单成功', severity: 'critical', defaultNotify: true },
  { key: 'BUY_FAILED', label: '抢单失败', severity: 'important' },
  { key: 'AUTH_EXPIRED', label: '登录态失效', severity: 'important' },
  { key: 'WAF_BLOCKED', label: 'WAF 拦截', severity: 'critical' },
  { key: 'SYSTEM_ERROR', label: '系统错误', severity: 'critical' },
]

const severityColors: Record<string, string> = {
  info: 'blue',
  important: 'orange',
  critical: 'red',
}

export default function NotifierChannels() {
  const { config, load, save, hasChanges, reset, update } = useConfigStore()
  const [channels, setChannels] = useState<ChannelDef[]>(defaultChannels)
  const [channelOrder, setChannelOrder] = useState<string[]>(defaultChannels.map((c) => c.key))
  const [subscribedEvents, setSubscribedEvents] = useState<string[]>(
    eventTypes.filter((e) => e.defaultNotify).map((e) => e.key),
  )
  const [loading, setLoading] = useState(false)
  const [testingChannel, setTestingChannel] = useState<string | null>(null)

  useEffect(() => {
    load()
  }, [load])

  // 从配置同步渠道开关状态 + 事件订阅状态
  useEffect(() => {
    if (!config) return
    const updated = channels.map((ch) => {
      const enabled =
        (ch.key === 'serverchan' && config.notifier.channels.serverchan) ||
        (ch.key === 'pushplus' && config.notifier.channels.pushplus) ||
        (ch.key === 'bark' && config.notifier.channels.bark) ||
        ch.enabled
      return { ...ch, enabled }
    })
    setChannels(updated)
    if (config.notifier.default_channels?.length) {
      setChannelOrder(config.notifier.default_channels)
    }
    // 从后端配置恢复事件订阅状态（持久化数据优先于默认值）
    if (config.notifier.subscribed_events?.length !== undefined) {
      setSubscribedEvents(config.notifier.subscribed_events)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config])

  const toggleChannel = (key: string, enabled: boolean) => {
    setChannels(channels.map((ch) => (ch.key === key ? { ...ch, enabled } : ch)))
    // 同步到配置
    if (config && ['serverchan', 'pushplus', 'bark'].includes(key)) {
      update({
        notifier: {
          ...config.notifier,
          channels: {
            ...config.notifier.channels,
            [key]: enabled,
          },
        },
      })
    }
  }

  const updateChannelField = (channelKey: string, fieldKey: string, value: string) => {
    if (!config) return
    // 敏感字段直接更新到 config 根级
    update({ [fieldKey]: value } as Partial<typeof config>)
  }

  // 拖拽排序
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (over && active.id !== over.id) {
      const oldIndex = channelOrder.indexOf(active.id as string)
      const newIndex = channelOrder.indexOf(over.id as string)
      const newOrder = arrayMove(channelOrder, oldIndex, newIndex)
      setChannelOrder(newOrder)
      // 同步到配置
      if (config) {
        update({
          notifier: { ...config.notifier, default_channels: newOrder },
        })
      }
    }
  }

  // 免打扰时段更新
  const updateQuietHours = (patch: Partial<AppConfig['notifier']['quiet_hours']>) => {
    if (!config) return
    update({
      notifier: {
        ...config.notifier,
        quiet_hours: { ...config.notifier.quiet_hours, ...patch },
      },
    })
  }

  const handleSave = async () => {
    try {
      setLoading(true)
      await save()
      message.success('通知配置已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async (channelKey: string) => {
    if (!config) return
    setTestingChannel(channelKey)
    try {
      // 收集该渠道当前填写的所有凭据字段
      const ch = channels.find((c) => c.key === channelKey)
      if (!ch) return
      const credentials: Record<string, string> = {}
      for (const field of ch.fields) {
        const val = (config as unknown as Record<string, unknown>)[field.key] as string
        if (val) credentials[field.key] = val
      }
      // 检查必填字段是否为空
      const emptyFields = ch.fields.filter((f) => !credentials[f.key])
      if (emptyFields.length > 0) {
        message.warning(`请先填写 ${emptyFields.map((f) => f.label).join('、')}`)
        setTestingChannel(null)
        return
      }

      const { data } = await api.post('/api/notifier/test', {
        channel: channelKey,
        credentials,
      })
      if (data.ok) {
        message.success(`✅ ${ch.name} 测试推送成功！请检查是否收到消息`)
      } else {
        message.error(`❌ 推送失败: ${data.error || '未知错误'}`)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '网络错误'
      message.error(`❌ 请求失败: ${msg}`)
    } finally {
      setTestingChannel(null)
    }
  }

  if (!config) {
    return <div className="page-container">加载中...</div>
  }

  const quietHours = config.notifier.quiet_hours

  // 按排序顺序获取渠道
  const orderedChannels = channelOrder
    .map((key) => channels.find((c) => c.key === key))
    .filter(Boolean) as ChannelDef[]

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>🔔 通知渠道可视化配置</h2>
        <Space>
          <Button icon={<UndoOutlined />} onClick={reset} disabled={!hasChanges()}>
            重置
          </Button>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={loading}>
            保存
          </Button>
        </Space>
      </div>

      <Row gutter={24}>
        {/* 左侧：渠道卡片墙 */}
        <Col span={14}>
          <Card title="渠道卡片墙（7 个渠道）" style={{ marginBottom: 16 }}>
            <Row gutter={[12, 12]}>
              {channels.map((ch) => (
                <Col span={12} key={ch.key}>
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
                          <div style={{ fontSize: 11, color: '#999' }}>{ch.desc}</div>
                        </div>
                      </Space>
                      <Switch checked={ch.enabled} onChange={(v) => toggleChannel(ch.key, v)} />
                    </div>

                    {ch.enabled && (
                      <div style={{ marginTop: 12 }}>
                        {ch.fields.map((field) => (
                          <div key={field.key} style={{ marginBottom: 8 }}>
                            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>{field.label}</div>
                            <Input.Password
                              placeholder={field.placeholder}
                              value={(config as unknown as Record<string, unknown>)[field.key] as string}
                              onChange={(e) => updateChannelField(ch.key, field.key, e.target.value)}
                              size="small"
                            />
                          </div>
                        ))}
                        <Button
                          size="small"
                          type="dashed"
                          icon={<SendOutlined />}
                          onClick={() => handleTest(ch.key)}
                          block
                          loading={testingChannel === ch.key}
                          disabled={testingChannel !== null && testingChannel !== ch.key}
                        >
                          {testingChannel === ch.key ? '发送中...' : '发送测试'}
                        </Button>
                      </div>
                    )}
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>

          {/* 通道顺序拖拽排序 */}
          <Card title="通道顺序（拖拽排序）" style={{ marginBottom: 16 }}>
            <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={channelOrder} strategy={verticalListSortingStrategy}>
                {orderedChannels.map((ch, index) => (
                  <SortableChannelItem key={ch.key} channel={ch} index={index + 1} />
                ))}
              </SortableContext>
            </DndContext>
            <div style={{ fontSize: 12, color: '#999', marginTop: 12 }}>
              按顺序尝试推送，失败则降级到下一个渠道。
            </div>
          </Card>
        </Col>

        {/* 右侧：免打扰时段 + 事件订阅 */}
        <Col span={10}>
          <div className="preview-panel">
            <Card title="免打扰时段" style={{ marginBottom: 16 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>启用免打扰</span>
                  <Switch
                    checked={quietHours.enabled}
                    onChange={(v) => updateQuietHours({ enabled: v })}
                  />
                </div>

                <div style={{ opacity: quietHours.enabled ? 1 : 0.5 }}>
                  <div style={{ marginBottom: 8 }}>静默时段（支持跨午夜）</div>
                  <Space>
                    <TimePicker
                      value={dayjs(quietHours.start, 'HH:mm')}
                      format="HH:mm"
                      onChange={(v) => updateQuietHours({ start: v?.format('HH:mm') || '23:00' })}
                    />
                    <span>→</span>
                    <TimePicker
                      value={dayjs(quietHours.end, 'HH:mm')}
                      format="HH:mm"
                      onChange={(v) => updateQuietHours({ end: v?.format('HH:mm') || '07:00' })}
                    />
                  </Space>

                  {/* 24 小时时间轴预览 */}
                  <div style={{ marginTop: 16 }}>
                    <QuietHoursTimeline start={quietHours.start} end={quietHours.end} />
                  </div>

                  <Divider />

                  <Checkbox
                    checked={quietHours.critical_only}
                    onChange={(e) => updateQuietHours({ critical_only: e.target.checked })}
                  >
                    仅 critical 级别可推送（其他事件落本地"待发摘要"）
                  </Checkbox>

                  <br />

                  <Checkbox
                    checked={quietHours.weekend_only}
                    onChange={(e) => updateQuietHours({ weekend_only: e.target.checked })}
                  >
                    仅周末启用（工作日保持全量推送）
                  </Checkbox>
                </div>
              </Space>
            </Card>

            <Card title="事件订阅规则（12 种事件）">
              <div style={{ marginBottom: 8, fontSize: 12, color: '#999' }}>
                勾选需要推送通知的事件类型：
              </div>
              <Checkbox.Group
                value={subscribedEvents}
                onChange={(values) => {
                  const newEvents = values as string[]
                  setSubscribedEvents(newEvents)
                  // 同步到配置（保存时会持久化到 YAML）
                  if (config) {
                    update({
                      notifier: {
                        ...config.notifier,
                        subscribed_events: newEvents,
                      },
                    })
                  }
                }}
                style={{ width: '100%' }}
              >
                <Row gutter={[8, 8]}>
                  {eventTypes.map((ev) => (
                    <Col span={24} key={ev.key}>
                      <Checkbox value={ev.key} style={{ width: '100%' }}>
                        <Space>
                          <Tag color={severityColors[ev.severity]} style={{ fontSize: 10 }}>
                            {ev.severity}
                          </Tag>
                          <span>{ev.label}</span>
                        </Space>
                      </Checkbox>
                    </Col>
                  ))}
                </Row>
              </Checkbox.Group>

              <Divider />

              <div style={{ fontSize: 12, color: '#999' }}>
                <BellOutlined /> 已订阅 {subscribedEvents.length} / {eventTypes.length} 种事件
              </div>
            </Card>
          </div>
        </Col>
      </Row>
    </div>
  )
}

// ============== 可拖拽渠道项 ==============
function SortableChannelItem({ channel, index }: { channel: ChannelDef; index: number }) {
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
        background: '#fafafa',
        border: '1px solid #d9d9d9',
        borderRadius: 4,
      }}
    >
      <span {...attributes} {...listeners} className="drag-handle" style={{ marginRight: 8 }}>
        <HolderOutlined />
      </span>
      <Tag color="blue">{index}</Tag>
      <span style={{ fontSize: 18, marginRight: 8 }}>{channel.icon}</span>
      <span style={{ fontWeight: 500 }}>{channel.name}</span>
      <span style={{ fontSize: 11, color: '#999', marginLeft: 8 }}>{channel.desc}</span>
      <Tag color={channel.enabled ? 'green' : 'default'} style={{ marginLeft: 'auto' }}>
        {channel.enabled ? '启用' : '禁用'}
      </Tag>
    </div>
  )
}

// ============== 免打扰时段时间轴预览 ==============
function QuietHoursTimeline({ start, end }: { start: string; end: string }) {
  const startHour = parseInt(start.split(':')[0])
  const endHour = parseInt(end.split(':')[0])
  const isCrossMidnight = startHour > endHour

  // 生成 24 小时间轴
  const hours = Array.from({ length: 24 }, (_, i) => i)
  const isQuiet = (hour: number) => {
    if (isCrossMidnight) {
      return hour >= startHour || hour < endHour
    }
    return hour >= startHour && hour < endHour
  }

  return (
    <div>
      <div style={{ display: 'flex', height: 24, borderRadius: 4, overflow: 'hidden' }}>
        {hours.map((h) => (
          <div
            key={h}
            style={{
              flex: 1,
              background: isQuiet(h) ? '#ff4d4f' : '#52c41a',
              opacity: isQuiet(h) ? 0.7 : 0.5,
            }}
            title={`${h}:00 - ${h + 1}:00 ${isQuiet(h) ? '（静默）' : '（推送）'}`}
          />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#999', marginTop: 4 }}>
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>24:00</span>
      </div>
      <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
        <span style={{ color: '#ff4d4f' }}>■</span> 静默时段 &nbsp;
        <span style={{ color: '#52c41a' }}>■</span> 推送时段
      </div>
    </div>
  )
}
