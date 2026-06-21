import { useEffect, useState } from 'react'
import {
  Card,
  Switch,
  Button,
  Space,
  message,
  Row,
  Col,
  TimePicker,
  Checkbox,
  Divider,
  Tag,
} from 'antd'
import { SaveOutlined, UndoOutlined, BellOutlined } from '@ant-design/icons'
import { DndContext, closestCenter, DragEndEvent } from '@dnd-kit/core'
import { SortableContext, arrayMove, verticalListSortingStrategy } from '@dnd-kit/sortable'
import dayjs from 'dayjs'
import { useConfigStore } from '../../../stores/configStore'
import api from '../../../api/client'
import type { AppConfig } from '../../../api'
import { defaultChannels, eventTypes, severityColors, type ChannelDef } from './constants'
import ChannelCard from './components/ChannelCard'
import SortableChannelItem from './components/SortableChannelItem'
import QuietHoursTimeline from './components/QuietHoursTimeline'

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
    // 敏感字段直接更新到 config 根级（channelKey 当前未使用，保留以匹配子组件回调签名）
    void channelKey
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
                  <ChannelCard
                    channel={ch}
                    config={config}
                    testing={testingChannel === ch.key}
                    anyTesting={testingChannel !== null}
                    onToggle={toggleChannel}
                    onFieldChange={updateChannelField}
                    onTest={handleTest}
                  />
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
