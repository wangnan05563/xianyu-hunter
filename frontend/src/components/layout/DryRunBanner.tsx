// 全局「演练中」横幅（PRD FR-C3-1）：存在 dry_run 开启的运行任务时常驻提示，
// 防止用户误以为在真实抢单。挂载在 MainLayout 顶部，所有页面可见。
import { useEffect, useState } from 'react'
import { Alert } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { taskApi } from '../../api'
import { TASK_STATUS } from '../../constants/taskStatus'

// 轮询间隔 60s：横幅只做状态提示，不需要实时性；
// 后端演练触发与报告均已异步落库，此处仅读任务配置
const POLL_INTERVAL_MS = 60_000

// 横幅一行放得下的任务名上限，超出即折叠
const MAX_LISTED = 3

/**
 * 演练任务名折叠（评审 2.7 维度4）：
 * 真机出现过「演练测试、演练测试、……（12 次）」占满两行、把结论挤到末尾的情况，
 * 因此先按名去重，再在超过上限时折叠成「A、B、C 等 N 个任务」。
 */
export function summarizeDryRunTasks(names: string[]): string {
  const total = names.length
  const uniq = [...new Set(names)]
  const head = uniq.slice(0, MAX_LISTED).join('、')
  if (uniq.length > MAX_LISTED) return `${head} 等 ${total} 个任务`
  if (total > uniq.length) return `${head}（共 ${total} 个任务）`
  return head
}

/** 列表项里判定「演练中」所需的最小字段（Task 类型未声明 dry_run，此处按可选字段收窄） */
type DryRunListedTask = {
  readonly dry_run?: number | boolean
  readonly status: string
  readonly name: string
}

/**
 * 挑出「演练模式 + 正在运行」的任务名。
 * S2004：原来内联在 useEffect → then 回调里，叠加 filter/map 回调超过 4 层，提到模块级。
 */
function pickRunningDryRunNames(items: readonly DryRunListedTask[]): string[] {
  return items
    .filter((t) => t.dry_run && t.status === TASK_STATUS.RUNNING)
    .map((t) => t.name)
}

export default function DryRunBanner() {
  const [dryRunTaskNames, setDryRunTaskNames] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    const check = () => {
      taskApi.list({ limit: 200 })
        .then((res) => {
          if (cancelled) return
          setDryRunTaskNames(pickRunningDryRunNames(res.items))
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
      // 结论前置：先说「不会产生真实订单」，再列任务（评审 2.7 维度4）
      message={`演练模式运行中·不产生真实订单（走到订单确认页即中止）：${summarizeDryRunTasks(dryRunTaskNames)}`}
      banner
      style={{ borderRadius: 0, flex: '0 0 auto' }}
    />
  )
}
