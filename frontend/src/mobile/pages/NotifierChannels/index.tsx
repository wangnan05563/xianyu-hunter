// frontend/src/mobile/pages/NotifierChannels/index.tsx
// 移动端通知渠道配置：精简版（仅启停开关 + 关键凭据编辑 + 顺序展示）
// 设计要点：去掉桌面端的拖拽排序/分类定价/限额展示，保留核心"启停 + 填凭据 + 测试"
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Tag, Spin, App, Switch, Button, Input, Space, Modal, Empty, theme, message as antdMessage,
} from 'antd'
import { EditOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { configApi } from '../../../api/config'
import { defaultChannels, type ChannelDef } from '../../../pages/Config/NotifierChannels/constants'
import { extractApiError } from '../../../utils/apiError'

export default function MobileNotifierChannels() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [channels, setChannels] = useState<ChannelDef[]>(defaultChannels)
  const [config, setConfig] = useState<Record<string, string> | null>(null)
  const [enabledMap, setEnabledMap] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<ChannelDef | null>(null)
  const [formValues, setFormValues] = useState<Record<string, string>>({})
  const [testing, setTesting] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // 加载配置：分别拉取结构化 + 凭据字段
  const loadAll = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const cfg = await configApi.get()
      // 启停状态来自 notifier.channels
      const enabled: Record<string, boolean> = {}
      defaultChannels.forEach((ch) => {
        enabled[ch.key] = (cfg.notifier.channels as Record<string, boolean>)[ch.key] ?? ch.enabled
      })
      setEnabledMap(enabled)
      setChannels(defaultChannels.map((ch) => ({ ...ch, enabled: enabled[ch.key] })))
      // 凭据字段：直接读 cfg 的顶层字段
      const creds: Record<string, string> = {}
      cfg.notifier.channels // 确保 notifier 段存在
      creds.serverchan_send_key = cfg.serverchan_send_key
      creds.pushplus_token = cfg.pushplus_token
      creds.bark_server = cfg.bark_server
      creds.bark_key = cfg.bark_key
      creds.telegram_bot_token = cfg.telegram_bot_token
      creds.telegram_chat_id = cfg.telegram_chat_id
      creds.wecom_webhook = cfg.wecom_webhook
      creds.dingtalk_webhook = cfg.dingtalk_webhook
      creds.dingtalk_secret = cfg.dingtalk_secret
      creds.webhook_url = cfg.webhook_url
      setConfig(creds)
    } catch (e) {
      message.error(extractApiError(e, '加载失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void loadAll() }, [loadAll])

  // 切换启停：本地立即更新 + 调用 configApi.save
  const toggleChannel = async (ch: ChannelDef, v: boolean): Promise<void> => {
    const prev = enabledMap[ch.key] ?? false
    setEnabledMap((m) => ({ ...m, [ch.key]: v }))
    setChannels((arr) => arr.map((c) => (c.key === ch.key ? { ...c, enabled: v } : c)))
    try {
      const cfg = await configApi.get()
      const payload = {
        notifier: {
          ...cfg.notifier,
          channels: { ...cfg.notifier.channels, [ch.key]: v },
        },
      }
      await configApi.save(payload)
      message.success(v ? '已启用' : '已停用')
    } catch (e) {
      message.error(extractApiError(e, '更新失败'), 3)
      // 回滚
      setEnabledMap((m) => ({ ...m, [ch.key]: prev }))
      setChannels((arr) => arr.map((c) => (c.key === ch.key ? { ...c, enabled: prev } : c)))
    }
  }

  // 打开凭据编辑
  const openEdit = (ch: ChannelDef): void => {
    const initial: Record<string, string> = {}
    ch.fields.forEach((f) => {
      initial[f.key] = config?.[f.key] ?? ''
    })
    setFormValues(initial)
    setEditing(ch)
  }

  // 保存凭据
  const saveCreds = async (): Promise<void> => {
    if (!editing) return
    setSaving(true)
    try {
      const cfg = await configApi.get()
      // 只更新当前渠道的凭据字段
      await configApi.save({ ...cfg, ...formValues })
      message.success('已保存')
      setEditing(null)
      void loadAll()
    } catch (e) {
      message.error(extractApiError(e, '保存失败'), 3)
    } finally {
      setSaving(false)
    }
  }

  // 测试通知（直连后端 /api/notifier/test）
  const testChannel = async (ch: ChannelDef): Promise<void> => {
    if (!enabledMap[ch.key]) {
      message.warning('请先启用渠道')
      return
    }
    setTesting(ch.key)
    try {
      const { default: client } = await import('../../../api/client')
      await client.post('/api/notifier/test', { channel: ch.key })
      message.success('测试通知已发送，请查收')
    } catch (e) {
      message.error(extractApiError(e, '测试失败'), 3)
    } finally {
      setTesting(null)
    }
  }

  if (loading || !config) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  return (
    <div>
      <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 8 }}>
        启用渠道并填写凭据，点击测试可验证配置
      </div>

      {channels.length === 0 ? (
        <Empty description="暂无可配置渠道" />
      ) : (
        channels.map((ch) => {
          const isEnabled = enabledMap[ch.key] ?? false
          return (
            <Card
              key={ch.key}
              size="small"
              style={{ marginBottom: 8, opacity: isEnabled ? 1 : 0.65 }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 24 }}>{ch.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <strong style={{ fontSize: 14 }}>{ch.name}</strong>
                    {ch.recommended && <Tag color="gold" style={{ fontSize: 10 }}>推荐</Tag>}
                  </div>
                  <div style={{ fontSize: 11, color: themeToken.colorTextSecondary }}>{ch.desc}</div>
                </div>
                <Switch
                  size="small"
                  checked={isEnabled}
                  onChange={(v) => void toggleChannel(ch, v)}
                />
              </div>
              <Space size={6} style={{ width: '100%', marginTop: 8 }}>
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => openEdit(ch)}
                  style={{ flex: 1 }}
                >
                  凭据
                </Button>
                <Button
                  size="small"
                  type="primary"
                  icon={<CheckCircleOutlined />}
                  loading={testing === ch.key}
                  disabled={!isEnabled}
                  onClick={() => void testChannel(ch)}
                  style={{ flex: 1 }}
                >
                  测试
                </Button>
              </Space>
            </Card>
          )
        })
      )}

      {/* 凭据编辑 Modal */}
      <Modal
        title={editing ? `${editing.name} 凭据` : ''}
        open={editing !== null}
        onOk={saveCreds}
        onCancel={() => setEditing(null)}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        width="92%"
      >
        {editing && (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {editing.obtainUrl && (
              <div style={{ fontSize: 12, color: themeToken.colorTextSecondary }}>
                获取凭据：
                <a href={editing.obtainUrl} target="_blank" rel="noopener noreferrer">
                  {editing.obtainUrl}
                </a>
              </div>
            )}
            {editing.fields.map((f) => (
              <div key={f.key}>
                <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
                  {f.label}
                </div>
                {f.secret ? (
                  <Input.Password
                    value={formValues[f.key] ?? ''}
                    onChange={(e) => setFormValues({ ...formValues, [f.key]: e.target.value })}
                    placeholder={f.placeholder}
                  />
                ) : (
                  <Input
                    value={formValues[f.key] ?? ''}
                    onChange={(e) => setFormValues({ ...formValues, [f.key]: e.target.value })}
                    placeholder={f.placeholder}
                  />
                )}
              </div>
            ))}
          </Space>
        )}
      </Modal>
    </div>
  )
}
