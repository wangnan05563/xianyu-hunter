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
  const schedulerLabel = schedulerRunning === null ? '加载中' : schedulerRunning ? '运行中' : '已停止'

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
        {/* 调度器状态灯：补 role + aria-label 让屏幕阅读器感知状态变化 */}
        <Tooltip title={schedulerLabel}>
          <span
            className="m-status-dot"
            role="status"
            aria-live="polite"
            aria-label={`调度器状态：${schedulerLabel}`}
            style={{
              background: schedulerRunning === null ? '#d9d9d9' : schedulerRunning ? '#52c41a' : '#ff4d4f',
            }}
          />
        </Tooltip>
        {/* 通知铃铛 */}
        <Badge count={alertCount} size="small" offset={[-2, 2]}>
          <Button
            type="text"
            shape="circle"
            size="small"
            icon={<BellOutlined />}
            aria-label={`通知${alertCount > 0 ? `，${alertCount} 条未读` : ''}`}
          />
        </Badge>
      </div>
    </header>
  )
}
