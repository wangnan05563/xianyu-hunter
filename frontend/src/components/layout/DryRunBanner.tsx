// 全局「演练中」横幅（PRD FR-C3-1）：存在 dry_run 开启的运行任务时常驻提示，
// 防止用户误以为在真实抢单。挂载在 MainLayout 顶部，所有页面可见。
import { useEffect, useState } from 'react'
import { Alert } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { taskApi } from '../../api'

// 轮询间隔 60s：横幅只做状态提示，不需要实时性；
// 后端演练触发与报告均已异步落库，此处仅读任务配置
const POLL_INTERVAL_MS = 60_000

export default function DryRunBanner() {
  const [dryRunTaskNames, setDryRunTaskNames] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    const check = () => {
      taskApi.list({ limit: 200 })
        .then((res) => {
          if (cancelled) return
          const names = res.items
            .filter((t) => (t as { dry_run?: number | boolean }).dry_run
              && t.status === 'running')
            .map((t) => t.name)
          setDryRunTaskNames(names)
        })
        .catch(() => { /* 拉取失败保持现状，不打扰用户 */ })
    }
    check()
    const timer = setInterval(check, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  if (dryRunTaskNames.length === 0) return null
  return (
    <Alert
      type="warning"
      showIcon
      icon={<ThunderboltOutlined />}
      message={`演练模式运行中：${dryRunTaskNames.join('、')}——抢单链路走到订单确认页即中止，不会产生真实订单`}
      banner
      style={{ borderRadius: 0 }}
    />
  )
}
