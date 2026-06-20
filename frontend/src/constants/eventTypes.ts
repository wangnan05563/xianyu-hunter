import { createElement, type ReactNode } from 'react'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  ShoppingOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'

// ===== Dashboard：RecentEvent.type 颜色与标签（下划线格式）=====
export const EVENT_COLOR: Record<string, string> = {
  buy_succeeded: 'green',
  eval_passed: 'blue',
  eval_scored: 'default',
  task_search_done: 'cyan',
  error: 'red',
  warn: 'orange',
}

export const EVENT_LABEL: Record<string, string> = {
  buy_succeeded: '抢单成功',
  eval_passed: '评估通过',
  eval_scored: '评估完成',
  task_search_done: '搜索完成',
  error: '错误',
  warn: '警告',
}

// ===== Dashboard：详细系统事件类型标签（点分格式，对应旧版 evTypeLabel）=====
export const EVENT_TYPE_LABEL: Record<string, string> = {
  'task.runner.started': '任务启动',
  'task.runner.stopped': '任务停止',
  'task.runner.finished': '任务完成',
  'task.runner.error': '任务异常',
  'collector.page_loaded': '页面加载',
  'collector.search_done': '搜索完成',
  'collector.item_found': '发现商品',
  'collector.rate_limited': '限流等待',
  'evaluator.item_scored': '商品评分',
  'evaluator.item_passed': '通过筛选',
  'evaluator.item_rejected': '已过滤',
  'buyer.order_placed': '下单成功',
  'buyer.order_failed': '下单失败',
  'buyer.payment_done': '支付完成',
  'buyer.timeout': '支付超时',
  'auth.login_success': '登录成功',
  'auth.login_failed': '登录失败',
  'auth.session_expired': '登录过期',
  'system.startup': '系统启动',
  'system.shutdown': '系统关闭',
  'system.error': '系统错误',
  'system.warning': '系统警告',
}

// ===== Timeline：事件类型过滤选项（与 domain/events.py EventType 对齐）=====
export const EVENT_TYPE_OPTIONS: { value: string; label: string; severity: string }[] = [
  { value: 'item.discovered', label: '发现商品', severity: 'info' },
  { value: 'eval.passed', label: '评估通过', severity: 'important' },
  { value: 'eval.rejected', label: '评估拒绝', severity: 'info' },
  { value: 'buy.requested', label: '请求购买', severity: 'info' },
  { value: 'buy.succeeded', label: '购买成功', severity: 'critical' },
  { value: 'buy.failed', label: '购买失败', severity: 'important' },
  { value: 'notify.sent', label: '通知已发送', severity: 'info' },
  { value: 'waf.triggered', label: '风控触发', severity: 'critical' },
  { value: 'login.expired', label: '登录过期', severity: 'critical' },
  { value: 'task.started', label: '任务启动', severity: 'info' },
  { value: 'task.paused', label: '任务暂停', severity: 'info' },
  { value: 'task.error', label: '任务异常', severity: 'critical' },
]

// ===== Timeline：大写枚举名 → 小写点分格式映射（用于同步通知订阅规则）=====
export const ENUM_TO_DOT: Record<string, string> = {
  ITEM_DISCOVERED: 'item.discovered',
  EVAL_PASSED: 'eval.passed',
  EVAL_REJECTED: 'eval.rejected',
  BUY_REQUESTED: 'buy.requested',
  BUY_SUCCEEDED: 'buy.succeeded',
  BUY_FAILED: 'buy.failed',
  NOTIFY_SENT: 'notify.sent',
  WAF_TRIGGERED: 'waf.triggered',
  LOGIN_EXPIRED: 'login.expired',
  TASK_STARTED: 'task.started',
  TASK_PAUSED: 'task.paused',
  TASK_ERROR: 'task.error',
}

// ===== Timeline：事件类型中文映射（含颜色与图标）=====
// 使用 createElement 而非 JSX，以保持 .ts 扩展名
export const EVENT_TYPE_LABELS: Record<string, { label: string; color: string; icon: ReactNode }> = {
  'task.search_done': { label: '搜索完成', color: 'blue', icon: createElement(InfoCircleOutlined) },
  'eval.scored': { label: '商品评分', color: 'cyan', icon: createElement(InfoCircleOutlined) },
  'eval.passed': { label: '通过筛选', color: 'green', icon: createElement(CheckCircleOutlined) },
  'eval.rejected': { label: '已过滤', color: 'default', icon: createElement(CloseCircleOutlined) },
  'order.created': { label: '创建订单', color: 'orange', icon: createElement(ShoppingOutlined) },
  'order.paid': { label: '支付成功', color: 'green', icon: createElement(CheckCircleOutlined) },
  'order.failed': { label: '订单失败', color: 'red', icon: createElement(CloseCircleOutlined) },
  dep_triggered: { label: '依赖激活', color: 'purple', icon: createElement(ThunderboltOutlined) },
  'maintenance.database': { label: '数据库维护', color: 'default', icon: createElement(InfoCircleOutlined) },
  'cleanup.database': { label: '数据库清理', color: 'default', icon: createElement(InfoCircleOutlined) },
}

// ===== Timeline：日志严重度配置（含颜色与图标）=====
export const SEVERITY_CONFIG: Record<string, { color: string; icon: ReactNode }> = {
  error: { color: 'red', icon: createElement(CloseCircleOutlined) },
  err: { color: 'red', icon: createElement(CloseCircleOutlined) },
  warning: { color: 'orange', icon: createElement(ExclamationCircleOutlined) },
  warn: { color: 'orange', icon: createElement(ExclamationCircleOutlined) },
  info: { color: 'blue', icon: createElement(InfoCircleOutlined) },
}
