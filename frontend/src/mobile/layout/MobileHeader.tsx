import { Button, Badge, Tooltip, theme } from 'antd'
import { ArrowLeftOutlined, BellOutlined } from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { statsApi } from '../../api'
import AccountSwitcher from '../components/AccountSwitcher'

// 五个 Tab 根路径：与 TabBar 的 key 一致
// 非 Tab 根路径（详情页 / 工具页 / 配置页）都需要返回出口 —— 这些页面此前
// 只能靠点品牌 Logo 回仪表盘，二级页普遍缺返回（FR-G-3 返回一致性）
const TAB_ROOTS = new Set(['/m', '/m/', '/m/tasks/', '/m/orders/', '/m/notifications/', '/m/chatbot/'])

function isTabRoot(pathname: string): boolean {
  const withSlash = pathname.endsWith('/') ? pathname : `${pathname}/`
  return TAB_ROOTS.has(pathname) || TAB_ROOTS.has(withSlash)
}

// 顶部状态栏：返回 + 品牌 + 调度器状态灯 + 通知铃铛 + 账号切换
export default function MobileHeader() {
  const navigate = useNavigate()
  const location = useLocation()
  const { token: themeToken } = theme.useToken()
  const [schedulerRunning, setSchedulerRunning] = useState<boolean | null>(null)
  const [alertCount, setAlertCount] = useState(0)
  // 轮询失败要显式声明：铃铛上保留上一次的数字却不说失败，等于告诉用户「没事」
  const [pollFailed, setPollFailed] = useState(false)

  // 非 Tab 根页显示返回按钮；无历史可退（深链接直达）时退回仪表盘，
  // 避免 navigate(-1) 把用户带出应用
  const showBack = !isTabRoot(location.pathname)
  const handleBack = () => {
    if (globalThis.history.length > 2) navigate(-1)
    else navigate('/m/')
  }

  // 轮询调度器状态与告警数（30s）
  // 告警数 = 今日失败订单 + 超时待支付 + 低分评估，与 Dashboard 摘要一致
  // 页面不可见时暂停轮询，恢复时立即拉取 + 重启定时器，省电省流量
  useEffect(() => {
    let id: ReturnType<typeof setInterval> | null = null
    const poll = async () => {
      try {
        const [overview, today] = await Promise.all([
          statsApi.overview(),
          statsApi.today(),
        ])
        setSchedulerRunning(overview.scheduler_running)
        const c = today.alerts.counts
        setAlertCount(c.failed + c.timeout + c.low_eval)
        setPollFailed(false)
      } catch {
        // 弱网下不打断用户（不弹 toast），但要把失败状态带进铃铛与状态灯
        setPollFailed(true)
      }
    }

    const start = () => {
      poll()
      id = setInterval(poll, 30_000)
    }
    const stop = () => {
      if (id) { clearInterval(id); id = null }
    }

    const onVisibility = () => {
      if (document.hidden) stop()
      else start()
    }

    start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  // 调度器状态文本：复用为 a11y 标签与 Tooltip 标题
  // S3358：拆分嵌套三元为独立变量
  let schedulerLabel = '已停止'
  if (schedulerRunning === null) schedulerLabel = pollFailed ? '未知（接口失败）' : '加载中'
  else if (schedulerRunning) schedulerLabel = '运行中'
  if (pollFailed && schedulerRunning !== null) schedulerLabel += '（接口失败，数字可能已过期）'
  // S3358：状态点颜色拆分为独立变量
  let statusColor = themeToken.colorError
  if (schedulerRunning === null || pollFailed) statusColor = themeToken.colorBorder
  else if (schedulerRunning) statusColor = themeToken.colorSuccess
  // S4624：嵌套模板字面量提取为独立变量
  const alertSuffix = alertCount > 0 ? `，${alertCount} 条未读` : ''
  const bellLabel = pollFailed
    ? '通知接口请求失败，铃铛数字不代表真实状态'
    : `通知${alertSuffix}`

  return (
    <header className="m-header">
      {/* 返回出口：非 Tab 根页面（详情/工具/配置）一律可见（FR-G-3） */}
      {showBack && (
        <Button
          type="text"
          shape="circle"
          size="small"
          icon={<ArrowLeftOutlined />}
          aria-label="返回上一页"
          onClick={handleBack}
          style={{ marginRight: 4 }}
        />
      )}
      {/* 品牌区：改用 <button> 让键盘 / 屏幕阅读器可聚焦和操作 */}
      <button
        type="button"
        className="m-brand"
        onClick={() => navigate('/m/')}
        aria-label="回到仪表盘"
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
        {/* 通知铃铛：接口失败时显示 ? 而不是上一次的数字（假回执消除） */}
        <Badge
          count={pollFailed && alertCount === 0 ? '?' : alertCount}
          size="small"
          offset={[-2, 2]}
          showZero={!pollFailed}
        >
          <Button
            type="text"
            shape="circle"
            size="small"
            icon={<BellOutlined />}
            aria-label={bellLabel}
            onClick={() => navigate('/m/notifications/')}
          />
        </Badge>
        {/* 账号切换：Dropdown 菜单，支持多账号切换 + 退出登录 */}
        <AccountSwitcher />
      </div>
    </header>
  )
}
