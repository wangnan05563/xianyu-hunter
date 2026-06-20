// 风险等级配置：合并自 Evaluations.tsx 的 RISK_COLOR 与 Timeline.tsx 的 RISK_LEVEL_CONFIG
// 同时包含 extreme（Evaluations 使用）与 critical（Timeline 使用）两种命名，以保持各组件显示效果不变
export const RISK_LEVEL_CONFIG: Record<string, { color: string; label: string }> = {
  low: { color: 'green', label: '低风险' },
  medium: { color: 'orange', label: '中风险' },
  high: { color: 'red', label: '高风险' },
  extreme: { color: 'red', label: '极高风险' },
  critical: { color: 'red', label: '极高风险' },
  unknown: { color: 'default', label: '数据不足' },
}
