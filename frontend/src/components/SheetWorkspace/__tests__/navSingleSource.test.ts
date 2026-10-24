// @vitest-environment node
import { describe, it, expect, afterEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { setMenuLabelIndex } from '../../../api/menu'
import type { MenuItem } from '../../../api/menu'
import { sheetRegistry, findSheetMeta } from '../sheetRegistry'
import { buildCommandItems } from '../../../hooks/useMenuConfig'
import { MENU_GUIDES } from '../../../guides/menuGuides'

// 导航文案单一事实源守卫（T02556 / FR-B-4）
// 背景：同一个页面曾在侧栏、面包屑、命令面板、标签栏四处各有叫法
// （/items 商品中心 vs 商品列表、/evaluations 卖家评估 vs 评估明细、/chatbot 智能客服 vs 智能客服对话），
// 根因是四套并存的常量表。现在 /api/menu 是唯一权威源，本测试锁住两件事：
// 1) 兜底表（sheetRegistry title）与 registry label 不得漂移——菜单加载前的首帧也必须是同一个名字；
// 2) 已删除的重复文案表不得复活。
const REGISTRY_SOURCE = readFileSync(
  resolve(__dirname, '../../../../../config/menu_registry.yaml'),
  'utf-8',
)
const LAYOUT_SOURCE = readFileSync(resolve(__dirname, '../../layout/MainLayout.tsx'), 'utf-8')
const HELP_SOURCE = readFileSync(resolve(__dirname, '../../../pages/Help/index.tsx'), 'utf-8')
const PRICE_HISTOGRAM_SOURCE = readFileSync(
  resolve(__dirname, '../../../pages/Dashboard/components/PriceHistogramCard.tsx'),
  'utf-8',
)

function parseRegistryLabels(): Map<string, string> {
  const map = new Map<string, string>()
  for (const block of REGISTRY_SOURCE.split(/\n(?=\s*-\s*key:)/)) {
    const path = block.match(/\n\s+path:\s*(\S+)/)?.[1]
    const label = block.match(/\n\s+label:\s*(.+?)\s*$/m)?.[1]
    if (path && label) map.set(path, label)
  }
  return map
}

function menuItem(key: string, label: string, path: string): MenuItem {
  return {
    key,
    label,
    path,
    icon: 'AppstoreOutlined',
    sort_order: 0,
    visible: true,
    category: 'data_view',
  }
}

describe('导航文案单一事实源（T02556 / FR-B-4）', () => {
  afterEach(() => setMenuLabelIndex([]))

  it('menu_registry.yaml 的每个菜单页，sheetRegistry 兜底标题与 label 一致', () => {
    const labels = parseRegistryLabels()
    // registry 条目数骤降说明解析失效（YAML 结构被改动），先让守卫本身可信
    expect(labels.size).toBeGreaterThanOrEqual(29)
    const drifted: string[] = []
    for (const s of sheetRegistry) {
      const label = labels.get(s.path)
      if (label && label !== s.title) drifted.push(`${s.path}: registry=${label} sheet=${s.title}`)
    }
    expect(drifted).toEqual([])
  })

  it('标签栏标题跟随 /api/menu：菜单 label 与兜底标题不同时以菜单为准', () => {
    setMenuLabelIndex([menuItem('items', '商品台账', '/items')])
    expect(findSheetMeta('/items')?.title).toBe('商品台账')
  })

  it('菜单尚未到达时回退到 sheetRegistry 兜底标题', () => {
    setMenuLabelIndex([])
    expect(findSheetMeta('/items')?.title).toBe('商品中心')
  })

  it('非菜单子页面（/tasks/:id）不受菜单索引影响，仍用本地标题', () => {
    setMenuLabelIndex([menuItem('tasks', '任务管理', '/tasks')])
    expect(findSheetMeta('/tasks/123')?.title).toBe('任务详情')
  })

  it('MainLayout 不再维护 ROUTE_LABELS / COMMAND_ITEMS 重复文案表', () => {
    for (const dead of ['ROUTE_LABELS', 'COMMAND_ITEMS']) {
      expect(LAYOUT_SOURCE).not.toContain(dead)
    }
  })

  it('命令面板项由菜单派生，名称与侧栏一致', () => {
    const items = buildCommandItems([
      menuItem('items', '商品中心', '/items'),
      menuItem('orders', '抢单记录', '/orders'),
    ])
    expect(items.map((i) => [i.key, i.label])).toEqual([
      ['/items', '商品中心'],
      ['/orders', '抢单记录'],
    ])
    expect(items[0].icon).toBeTruthy()
  })

  it('用户隐藏的菜单项同样不出现在命令面板', () => {
    const hidden = menuItem('chatbot', '智能客服', '/chatbot')
    expect(buildCommandItems([{ ...hidden, visible: false }])).toEqual([])
  })

  // 评审 2.3-1：页面名在侧栏/标签栏/帮助/引导/仪表盘入口之间不得再分裂出「商品列表」
  describe('/items 命名单一事实源（T02657）', () => {
    const helpItemsBlock = HELP_SOURCE.slice(
      HELP_SOURCE.indexOf("id: 'items'"),
      HELP_SOURCE.indexOf("id: 'evaluations'"),
    )

    it('帮助文档的商品模块标题与菜单一致', () => {
      expect(helpItemsBlock).toContain("title: '商品中心'")
      expect(helpItemsBlock).not.toContain('商品列表')
    })

    it('全站引导里 /items 的标题与菜单一致', () => {
      const guide = MENU_GUIDES.find((g) => g.route === '/items')
      expect(guide?.steps[0]?.title).toBe('商品中心')
    })

    it('任务详情引导与帮助不再宣称内嵌「商品列表」页签', () => {
      const taskGuide = MENU_GUIDES.find((g) => g.route === '/tasks/:id')
      expect(taskGuide?.steps[0]?.description).not.toContain('商品列表')
      expect(helpItemsBlock).not.toContain('商品列表')
    })

    it('仪表盘价格直方图的入口提示使用商品中心', () => {
      expect(PRICE_HISTOGRAM_SOURCE).toContain("onNavigate('/items')")
      expect(PRICE_HISTOGRAM_SOURCE).not.toContain('商品列表')
    })
  })

  // 评审 2.4-4：本页评估对象是商品，「卖家评估」名不副实；全站统一为「评估明细」
  describe('/evaluations 命名单一事实源（T02665）', () => {
    const helpEvalBlock = HELP_SOURCE.slice(
      HELP_SOURCE.indexOf("id: 'evaluations'"),
      HELP_SOURCE.indexOf("id: 'orders'"),
    )

    it('侧栏/menu registry 使用「评估明细」', () => {
      expect(parseRegistryLabels().get('/evaluations')).toBe('评估明细')
    })

    it('帮助文档的评估模块标题与菜单一致', () => {
      expect(helpEvalBlock).toContain("title: '评估明细'")
      expect(helpEvalBlock).not.toContain("'卖家评估'")
    })

    it('全站引导里 /evaluations 的标题与菜单一致', () => {
      const guide = MENU_GUIDES.find((g) => g.route === '/evaluations')
      expect(guide?.steps[0]?.title).toBe('评估明细')
    })
  })
})
