// 订单状态配置：合并自 Timeline.tsx 的 ORDER_STATUS_CONFIG 与 Orders.tsx 的 STATUS_COLOR
// takeover 来自 Orders.tsx，submitting/paying/cancelled 来自 Timeline.tsx
// 注意：Orders.tsx 使用更详细的中文标签（如"已成功"），Timeline.tsx 使用简短标签（如"成功"），
// 因此 Orders.tsx 仍保留自己的 STATUS_TEXT，仅颜色从此处统一获取
export const ORDER_STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  succeeded: { color: 'green', label: '成功' },
  // 与后端 OrderStatus.PENDING_PAY.value = "pending_pay" 对齐
  pending_pay: { color: 'orange', label: '待支付' },
  paid: { color: 'blue', label: '已支付' },
  submitting: { color: 'blue', label: '提交中' },
  paying: { color: 'blue', label: '支付中' },
  failed: { color: 'red', label: '失败' },
  cancelled: { color: 'default', label: '已取消' },
  // 后端 api_orders.takeover_order 实际写入的状态是 takeover_pending（非 takeover）
  takeover_pending: { color: 'blue', label: '人工接管' },
}
