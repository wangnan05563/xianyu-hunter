// 渠道定义：每个通知渠道的元信息 + 凭据字段配置
export interface ChannelDef {
  key: string
  name: string
  icon: string
  desc: string
  enabled: boolean
  fields: { key: string; label: string; placeholder: string; secret?: boolean }[]
}

// 默认渠道列表：开关状态会被后端配置覆盖，这里仅提供结构定义
export const defaultChannels: ChannelDef[] = [
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

// 事件类型定义（12 种）：severity 用于 UI 标签着色，defaultNotify 控制初始订阅
export const eventTypes = [
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

// 严重级别对应的标签颜色
export const severityColors: Record<string, string> = {
  info: 'blue',
  important: 'orange',
  critical: 'red',
}
