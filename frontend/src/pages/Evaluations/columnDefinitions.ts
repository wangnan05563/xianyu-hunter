import type { ColumnConfig } from '../../hooks/useColumnConfig'

// 列的「可配置清单」：列设置弹窗、默认顺序、显隐都以此为准。
// 只登记表格里真实存在的 key；fixed-right 操作列不参与配置，因此不在表内。
export const COLUMN_DEFINITIONS: ColumnConfig[] = [
  { key: 'task_id', label: '任务ID' },
  { key: 'thumb', label: '图片' },
  { key: 'title', label: '标题', locked: true },
  { key: 'price', label: '价格' },
  { key: 'estimated_profit', label: '预估盈利' },
  { key: 'seller', label: '卖家' },
  { key: 'region', label: '地区' },
  { key: 'brand', label: '品牌' },
  { key: 'want', label: '想要' },
  { key: 'view', label: '浏览' },
  { key: 'publish', label: '发布时间' },
  { key: 'is_sold', label: '状态' },
  { key: 'condition', label: '成色' },
  { key: 'condition_tags', label: '成色标签' },
  { key: 'score', label: '评分', locked: true },
  { key: 'risk', label: '风险' },
  { key: 'ai', label: 'AI' },
  { key: 'collect', label: '官方采集' },
  { key: 'feedback', label: '反馈' },
  // 订单列此前只存在于表格定义、没登记进配置表：列设置弹窗管不到它，
  // 还会被 applyConfig 的兜底逻辑甩到 fixed-right 操作列之后（评审 2.4-5）
  { key: 'order_status', label: '订单' },
]
