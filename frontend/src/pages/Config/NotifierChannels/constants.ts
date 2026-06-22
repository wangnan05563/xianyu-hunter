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

// 事件类型定义（22 种）：与 Timeline EVENT_TYPE_OPTIONS / ENUM_TO_DOT 对齐
// severity 用于 UI 标签着色，defaultNotify 控制初始订阅
// key 必须与 ENUM_TO_DOT 中的键一一对应，否则时间线"同步订阅"会丢弃
export const eventTypes = [
  // 任务生命周期
  { key: 'TASK_STARTED', label: '任务启动', severity: 'info' },
  { key: 'TASK_STOPPED', label: '任务停止', severity: 'info' },
  { key: 'TASK_PAUSED', label: '任务暂停', severity: 'info' },
  { key: 'TASK_ERROR', label: '任务异常', severity: 'critical' },
  { key: 'TASK_SEARCH_DONE', label: '搜索完成', severity: 'info' },
  // 商品与评估
  { key: 'ITEM_DISCOVERED', label: '发现商品', severity: 'info' },
  { key: 'ITEM_FOUND', label: '发现商品（旧枚举）', severity: 'info' },
  { key: 'EVAL_PASSED', label: '评估通过', severity: 'important', defaultNotify: true },
  { key: 'EVAL_REJECTED', label: '评估拒绝', severity: 'info' },
  { key: 'EVAL_SCORED', label: '评估打分', severity: 'info' },
  // 购买
  { key: 'BUY_REQUESTED', label: '请求购买', severity: 'info' },
  { key: 'BUY_SUCCEEDED', label: '抢单成功', severity: 'critical', defaultNotify: true },
  { key: 'BUY_FAILED', label: '抢单失败', severity: 'important' },
  // 通知
  { key: 'NOTIFY_SENT', label: '通知已发送', severity: 'info' },
  // 安全
  { key: 'WAF_TRIGGERED', label: '风控触发', severity: 'critical' },
  { key: 'WAF_BLOCKED', label: '风控拦截', severity: 'critical' },
  // 认证
  { key: 'LOGIN_EXPIRED', label: '登录过期', severity: 'critical' },
  { key: 'AUTH_EXPIRED', label: '会话过期', severity: 'important' },
  // 系统
  { key: 'SYSTEM_ERROR', label: '系统错误', severity: 'critical' },
  // 维护（DB 实际存储的事件类型，无对应 EventType 枚举）
  { key: 'MAINTENANCE_DATABASE', label: '数据库维护', severity: 'info' },
  { key: 'MAINTENANCE_LOGS', label: '日志清理', severity: 'info' },
  { key: 'MAINTENANCE_CACHE', label: '缓存清理', severity: 'info' },
]

// 严重级别对应的标签颜色
export const severityColors: Record<string, string> = {
  info: 'blue',
  important: 'orange',
  critical: 'red',
}
