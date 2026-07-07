import { Button, Badge, Tooltip } from 'antd'
import { BellOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { statsApi } from '../../api'

// 顶部状态栏：品牌 + 调度器状态灯 + 通知铃铛
export default function MobileHeader() {
  const navigate = useNavigate()
  const [schedulerRunning, setSchedulerRunning] = useState<boolean | null>(null)
  const [alertCount, setAlertCount] = useState(0)

  // 轮询调度器状态与告警数（30s）
  // 告警数 = 今日失败订单 + 超时待支付 + 低分评估，与 Dashboard 摘要一致
  useEffect(() => {
    const poll = async () => {
      try {
        const [overview, today] = await Promise.all([
          statsApi.overview(),
          statsApi.today(),
        ])
        setSchedulerRunning(overview.scheduler_running)
        const c = today.alerts.counts
        setAlertCount(c.failed + c.timeout + c.low_eval)
      } catch { /* 忽略，弱网下不打断用户 */ }
    }
    poll()
    const id = setInterval(poll, 30_000)
    return () => clearInterval(id)
  }, [])

  // 调度器状态文本：复用为 a11y 标签与 Tooltip 标题
  // S3358：拆分嵌套三元为独立变量
  let schedulerLabel = '已停止'
  if (schedulerRunning === null) schedulerLabel = '加载中'
  else if (schedulerRunning) schedulerLabel = '运行中'
  // S3358：状态点颜色拆分为独立变量
  let statusColor = '#ff4d4f'
  if (schedulerRunning === null) statusColor = '#d9d9d9'
  else if (schedulerRunning) statusColor = '#52c41a'
  // S4624：嵌套模板字面量提取为独立变量
  const alertSuffix = alertCount > 0 ? `，${alertCount} 条未读` : ''

  return (
    <header className="m-header">
      {/* 品牌区：改用 <button> 让键盘 / 屏幕阅读器可聚焦和操作 */}
      <button
        type="button"
        className="m-brand"
        onClick={() => navigate('/m')}
        aria-label="返回仪表盘"
      >
        <span className="m-brand-logo" aria-hidden="true">闲</span>
        <span className="m-brand-name">闲鱼猎人</span>
      </button>
      <div className="m-header-actions">
        {/* 调度器状态灯：用 <output> 替代 role="status"，原生 live region 语义 */}
        <Tooltip title={schedulerLabel}>
          <output
            className="m-status-dot"
            aria-live="polite"
            aria-label={`调度器状态：${schedulerLabel}`}
            style={{ background: statusColor }}
          />
        </Tooltip>
        {/* 通知铃铛 */}
        <Badge count={alertCount} size="small" offset={[-2, 2]}>
          <Button
            type="text"
            shape="circle"
            size="small"
            icon={<BellOutlined />}
            aria-label={`通知${alertSuffix}`}
          />
        </Badge>
      </div>
    </header>
  )
}
