import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  ALERT_JUMP_TARGETS,
  bellBadgeTip,
  computeBellBadge,
} from '../../../hooks/useNotificationModel'

// 通知与告警模型统一守卫（T02561 / FR-B-1，合并 N11、N12、N19、2.9-1、2.9-2、2.9-3、2.9-7）
const LAYOUT_SOURCE = readFileSync(resolve(__dirname, '../MainLayout.tsx'), 'utf-8')
const PAGE_SOURCE = readFileSync(
  resolve(__dirname, '../../../pages/Notifications/index.tsx'),
  'utf-8',
)
const SHEET_NOTIFY_SOURCE = readFileSync(
  resolve(__dirname, '../../SheetWorkspace/sheetNotifications.tsx'),
  'utf-8',
)
const MENU_HOOK_SOURCE = readFileSync(
  resolve(__dirname, '../../../hooks/useMenuConfig.tsx'),
  'utf-8',
)
const API_SOURCE = readFileSync(resolve(__dirname, '../../../api/notifications.ts'), 'utf-8')
const HOOK_SOURCE = readFileSync(
  resolve(__dirname, '../../../hooks/useNotificationModel.ts'),
  'utf-8',
)
const REGISTRY_SOURCE = readFileSync(
  resolve(__dirname, '../../../../../config/menu_registry.yaml'),
  'utf-8',
)

describe('铃铛单一数字口径（2.9-1）', () => {
  it('有告警时数字是告警数，无告警时退为未读通知数', () => {
    expect(computeBellBadge(3, 5)).toEqual({ count: 3, isAlert: true })
    expect(computeBellBadge(0, 5)).toEqual({ count: 5, isAlert: false })
    expect(computeBellBadge(0, 0)).toEqual({ count: 0, isAlert: false })
  })

  it('两个口径永不相加——相加会造出第三种含义不明的数，正是本单要消掉的问题', () => {
    const badge = computeBellBadge(2, 7)
    expect(badge.count).not.toBe(9)
    expect(badge.count).toBe(2)
  })

  it('tooltip 文案与数字含义一致，用户能判断这个数字是什么', () => {
    expect(bellBadgeTip(computeBellBadge(2, 7))).toContain('今日告警 2 条')
    expect(bellBadgeTip(computeBellBadge(0, 7))).toContain('未读通知 7 条')
    expect(bellBadgeTip(computeBellBadge(0, 0))).toContain('通知抽屉')
  })
})

describe('抽屉列表项按类跳转（N11）', () => {
  it('失败/超时跳抢单记录，低分跳评估明细', () => {
    expect(ALERT_JUMP_TARGETS.failed).toBe('/orders')
    expect(ALERT_JUMP_TARGETS.timeout).toBe('/orders')
    expect(ALERT_JUMP_TARGETS.low_eval).toBe('/evaluations')
  })

  it('跳转目标都在菜单注册表里存在，不会点开一个不存在的 sheet', () => {
    for (const path of Object.values(ALERT_JUMP_TARGETS)) {
      expect(REGISTRY_SOURCE).toContain(`path: ${path}\n`)
    }
  })

  it('抽屉项走统一的 alertItem 渲染，且带键盘可达性', () => {
    expect(LAYOUT_SOURCE).toContain('alertItem')
    expect(LAYOUT_SOURCE).toContain('openSheetWithNotification(ALERT_JUMP_TARGETS[kind])')
    expect(LAYOUT_SOURCE).toContain('role="button"')
    // 三个面板都接上了跳转，不再只有其中一个能点
    for (const kind of ['failed', 'timeout', 'low_eval']) {
      expect(LAYOUT_SOURCE).toContain(`alertItem('${kind}'`)
    }
  })
})

describe('抽屉底部与通知中心入口（2.9-2）', () => {
  it('底部链接指向 /notifications，不再跳抢单记录', () => {
    expect(LAYOUT_SOURCE).toContain('<Link to="/notifications"')
    expect(LAYOUT_SOURCE).not.toContain('<Link to="/orders"')
    expect(LAYOUT_SOURCE).toContain('通知中心 →')
  })

  it('抽屉同时摆明两套计数：今日告警按天归零，未读通知来自通知中心', () => {
    expect(LAYOUT_SOURCE).toContain('今日告警（')
    expect(LAYOUT_SOURCE).toContain('未读通知 {notif.unreadCount} 条')
    expect(LAYOUT_SOURCE).toContain('notif.notifTotal')
  })

  it('侧栏通知中心图标与 Header 铃铛不再撞车', () => {
    const block = REGISTRY_SOURCE.slice(
      REGISTRY_SOURCE.indexOf('- key: notifications'),
      REGISTRY_SOURCE.indexOf('- key: price_dashboard'),
    )
    expect(block).toContain('icon: NotificationOutlined')
    expect(block).not.toContain('BellOutlined')
    expect(MENU_HOOK_SOURCE).toContain('NotificationOutlined')
  })
})

describe('通知中心计数口径（2.9-3、2.9-7）', () => {
  it('已读数取后端全量口径，不再用「列表 total − unread」现算', () => {
    expect(PAGE_SOURCE).toContain('.counts()')
    expect(PAGE_SOURCE).not.toContain('.unreadCount()')
    expect(PAGE_SOURCE).not.toContain('total - unreadCount')
    expect(API_SOURCE).toContain('NotificationCounts')
    expect(API_SOURCE).toContain('/api/notifications/unread_count')
  })

  it('标记已读成功后，未读筛选下该行从列表移除', () => {
    expect(PAGE_SOURCE).toContain("if (filter === 'unread')")
    expect(PAGE_SOURCE).toContain('setItems((prev) => prev.filter((it) => it.id !== item.id))')
  })
})

describe('替换通知不再遮挡 Header（N19）', () => {
  it('两条 sheet 通知都改为右下角', () => {
    expect(SHEET_NOTIFY_SOURCE).not.toContain("placement: 'topRight'")
    expect(SHEET_NOTIFY_SOURCE.match(/placement: 'bottomRight'/g)?.length).toBe(2)
  })
})

describe('计数只有一份来源（FR-B-1 单一事实源）', () => {
  it('MainLayout 不再自己拉 stats/today 与本地告警计数', () => {
    expect(LAYOUT_SOURCE).toContain('useNotificationModel({ enabled: loggedIn })')
    expect(LAYOUT_SOURCE).not.toContain('setTodayAlert')
    expect(LAYOUT_SOURCE).not.toContain('todayAlert.alerts.counts.failed +')
  })
})

describe('badge 与已读联动（不等 30s 轮询）', () => {
  it('Hook 暴露计数广播通道', () => {
    expect(HOOK_SOURCE).toContain('export function invalidateNotificationCounts')
    expect(HOOK_SOURCE).toContain('countListeners.add(self)')
    expect(HOOK_SOURCE).toContain('countListeners.delete(self)')
  })

  it('通知中心三处变更入口都会广播（单条已读、删除、重取计数）', () => {
    expect(PAGE_SOURCE).toContain('invalidateNotificationCounts')
    expect(PAGE_SOURCE.match(/invalidateNotificationCounts\(\)/g)?.length).toBe(3)
  })
})
