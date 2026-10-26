// 快捷入口清单（T02640 / 评审 2.1-3）
// 裁决：保持现有顺序，前 6 项直接可见，其余收进「更多」下拉。
// 移出快捷卡不等于删功能——这些页面仍可从侧栏、命令面板与「更多」到达，
// 所以顺序按现有列表原样保留，等真正有点击埋点后再按频率重排。
export type QuickEntryIconType = 'task' | 'price' | 'eval' | 'notifier' | 'ai' | 'buyer'
  | 'search' | 'version' | 'cleanup' | 'dbAdmin' | 'antiCrawl'

export interface QuickEntry {
  readonly path: string
  readonly icon: QuickEntryIconType
  readonly title: string
  readonly desc: string
}

/** 直接铺在卡片上的入口数；其余进「更多」 */
export const QUICK_ENTRY_VISIBLE = 6

export const QUICK_ENTRIES: readonly QuickEntry[] = [
  { path: '/tasks/new', icon: 'task', title: '任务创建', desc: '向导式配置' },
  { path: '/config/price', icon: 'price', title: '价格策略', desc: '滑块 + 预览' },
  { path: '/config/eval', icon: 'eval', title: '评估规则', desc: '雷达图可视化' },
  { path: '/config/notifier', icon: 'notifier', title: '通知渠道', desc: '拖拽排序' },
  { path: '/config/ai', icon: 'ai', title: 'AI 服务', desc: '模型与深度分析' },
  { path: '/config/buyer', icon: 'buyer', title: '抢单策略', desc: '极速抢占配置' },
  { path: '/config/search', icon: 'search', title: '搜索参数', desc: '筛选与过滤' },
  { path: '/config/version', icon: 'version', title: '配置版本', desc: '版本回滚管理' },
  { path: '/maintenance', icon: 'cleanup', title: '系统清理', desc: '缓存与日志维护' },
  { path: '/maintenance/db', icon: 'dbAdmin', title: '数据库维护', desc: '业务表在线管理' },
  { path: '/anticrawl', icon: 'antiCrawl', title: '反爬登录管理', desc: '策略与会话监控' },
]

export function visibleQuickEntries(): readonly QuickEntry[] {
  return QUICK_ENTRIES.slice(0, QUICK_ENTRY_VISIBLE)
}

export function moreQuickEntries(): readonly QuickEntry[] {
  return QUICK_ENTRIES.slice(QUICK_ENTRY_VISIBLE)
}
