// 任务状态颜色映射（running/paused/stopped/deleted）
// 原先在 TaskDetail.tsx 与 TaskList.tsx 中各自重复定义，统一抽取到此处
export const STATUS_COLOR: Record<string, string> = {
  running: 'green',
  paused: 'orange',
  stopped: 'default',
  deleted: 'red',
}
