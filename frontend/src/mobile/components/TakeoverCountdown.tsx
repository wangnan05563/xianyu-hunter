// frontend/src/mobile/components/TakeoverCountdown.tsx
// 人工接管倒计时（FR-G-2）
//
// 为什么要这个组件：移动端订单页原先只把 takeover_pending 渲染成一个静态「人工接管」标签，
// 用户看不到还剩多少时间，而闲鱼待付款订单会在 30 分钟后自动关闭 —— 没有倒计时等于没有提示。
// 后端其实已经下发 deadline/剩余秒（GET /api/orders 对 takeover_pending 附加；
// GET /api/orders/{id} 本次补齐，T02588），前端只是没用。
//
// 时刻基准：优先用 remaining_sec 换算绝对时刻（Date.now() + remaining），
// 这样不依赖后端 ISO 串有没有时区标记；只有 remaining_sec 缺失时才退回解析 deadline，
// 并按后端语义把无时区标记的串当 UTC 处理（后端 _utcnow().replace(tzinfo=None)）。
import { useEffect, useMemo, useState } from 'react'
import { Tag } from 'antd'

interface TakeoverCountdownProps {
  readonly deadline?: string | null
  readonly remainingSec?: number | null
}

/** 把后端 deadline 串解析为毫秒时刻；无时区标记按 UTC（与后端 naive UTC 写入一致） */
function parseDeadline(s: string): number | null {
  const hasTz = s.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(s)
  const t = Date.parse(hasTz ? s : `${s}Z`)
  return Number.isNaN(t) ? null : t
}

function formatRemain(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}

export default function TakeoverCountdown({ deadline, remainingSec }: TakeoverCountdownProps) {
  const target = useMemo(() => {
    if (remainingSec != null) return Date.now() + remainingSec * 1000
    if (deadline) return parseDeadline(deadline)
    return null
  }, [deadline, remainingSec])

  const [remain, setRemain] = useState<number | null>(
    target == null ? null : Math.max(0, Math.round((target - Date.now()) / 1000)),
  )

  useEffect(() => {
    if (target == null) {
      setRemain(null)
      return undefined
    }
    const tick = () => setRemain(Math.max(0, Math.round((target - Date.now()) / 1000)))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [target])

  if (target == null || remain == null) {
    // 后端没给倒计时依据时如实说明，绝不显示「剩 0 秒」——那会被读成「已经超时」
    return <Tag>接管截止未知</Tag>
  }
  if (remain <= 0) return <Tag color="red">接管已超时</Tag>
  // 5 分钟内转橙色再转红色：与桌面「接管截止」列同一意图（临近要看得见）
  const color = remain <= 300 ? 'red' : 'blue'
  return <Tag color={color}>剩 {formatRemain(remain)}</Tag>
}
