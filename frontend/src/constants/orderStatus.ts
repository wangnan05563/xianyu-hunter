// 订单状态配置：合并自 Timeline.tsx 的 ORDER_STATUS_CONFIG 与 Orders.tsx 的 STATUS_COLOR
// 状态字面值与后端 domain/order.py OrderStatus 同源（T02585），新增状态先改枚举
// 注意：Orders.tsx 使用更详细的中文标签（如"已成功"），Timeline.tsx 使用简短标签（如"成功"），
// 因此 Orders.tsx 仍保留自己的 STATUS_TEXT，仅颜色从此处统一获取
export const ORDER_STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  succeeded: { color: 'green', label: '成功' },
  // 键集合与后端 domain/order.py OrderStatus 一一对应（T02585）：
  // 原先另有 paid/submitting/paying 三项，后端从未写入过这些字面值，属死配置
  pending_pay: { color: 'orange', label: '待支付' },
  failed: { color: 'red', label: '失败' },
  cancelled: { color: 'default', label: '已取消' },
  // 后端 api_orders.takeover_order 实际写入的状态是 takeover_pending（非 takeover）
  takeover_pending: { color: 'blue', label: '人工接管' },
  // 演练记录（PRD FR-C3-3）：orders.type=dry_run 的报告条目，红色徽标与真实记录区分
  dry_run: { color: 'red', label: '演练' },
}

/**
 * 订单状态字面值常量（T02693）。
 *
 * 为什么要再包一层：上面那张表带的是「颜色 + 文案」，判断状态时大家只能裸写
 * 'succeeded'，而裸写一旦拼成后端从未写入过的值（pending / paid / submitting）不会报错，
 * 只会让徽标、圆点配色和筛选静默失效——这正是 T02585 那批 bug 的形状。
 * 键集合与 ORDER_STATUS_CONFIG 严格对齐，由 constants/__tests__/orderStatusSingleSource.test.ts
 * 同时对照后端 domain/order.py 钉住。
 */
export const ORDER_STATUS = {
  SUCCEEDED: 'succeeded',
  PENDING_PAY: 'pending_pay',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
  TAKEOVER_PENDING: 'takeover_pending',
  DRY_RUN: 'dry_run',
} as const

export type OrderStatusValue = (typeof ORDER_STATUS)[keyof typeof ORDER_STATUS]

/**
 * 订单域的完整中文标签（T02716）。
 *
 * ORDER_STATUS_CONFIG.label 是时间轴用的两字短标签，列表/详情要显示「已成功」这类完整措辞。
 * 之前这套措辞在桌面订单页和移动端订单页各写了一份（移动端还漏了 cancelled），
 * 漏写的那个值会静默退化成英文末段。列表的可选项也从这里生成，
 * 保证「能选到的状态」和「能读到的标签」永远是同一份映射。
 */
export const ORDER_STATUS_LABELS: Record<OrderStatusValue, string> = {
  [ORDER_STATUS.PENDING_PAY]: '待支付',
  [ORDER_STATUS.SUCCEEDED]: '已成功',
  [ORDER_STATUS.FAILED]: '已失败',
  [ORDER_STATUS.CANCELLED]: '已取消',
  [ORDER_STATUS.TAKEOVER_PENDING]: '人工接管',
  [ORDER_STATUS.DRY_RUN]: '演练',
}

/**
 * 移动端订单页围绕用户决策的那几个状态（T02716）。
 * 列表的状态筛选与行内「改状态」下拉共用这一份：两处本来就是同一组决策
 * （待支付 / 支付完标记成功 / 放弃则取消），分成两份写就会一边加了另一边忘。
 */
export const ORDER_STATUS_USER_CHOICES: readonly OrderStatusValue[] = [
  ORDER_STATUS.PENDING_PAY,
  ORDER_STATUS.SUCCEEDED,
  ORDER_STATUS.CANCELLED,
]

/** 生成 Select / Segmented 的选项，避免各页面再手写一遍 value/label 对 */
export function orderStatusOptions(
  values: readonly OrderStatusValue[],
): { value: OrderStatusValue; label: string }[] {
  return values.map((value) => ({ value, label: ORDER_STATUS_LABELS[value] }))
}

/** 兜底显示原文：库里若出现枚举外的值，宁可露出英文也不要伪装成某个已知状态 */
export function orderStatusLabel(status: string): string {
  return ORDER_STATUS_LABELS[status as OrderStatusValue] || status
}

export function orderStatusColor(status: string): string {
  return ORDER_STATUS_CONFIG[status]?.color || 'default'
}
