import { useEffect, useState } from 'react'
import { aiApi } from '../api'

// 模块级缓存：AI 总开关是全局唯一状态，多个页面（任务列表 / 评估列表）各自拉一次
// /api/ai/config 既慢又会互相给出不同瞬间的读数，所以共享一份。
let cached: boolean | null = null
let inflight: Promise<void> | null = null
const subscribers = new Set<(v: boolean | null) => void>()

function publish(value: boolean | null): void {
  cached = value
  subscribers.forEach((fn) => fn(value))
}

function load(): Promise<void> {
  if (!inflight) {
    inflight = aiApi.getConfig()
      .then((cfg) => publish(cfg.ai_enabled !== false))
      // 读取失败保持 null（未知），不把它当成「已关闭」而把功能锁死
      .catch(() => publish(cached))
      .finally(() => { inflight = null })
  }
  return inflight
}

/** 配置页保存成功后调用，让入口的置灰状态跟着真实配置走 */
export function invalidateAIEnabled(next?: boolean): void {
  if (typeof next === 'boolean') {
    cached = next
    subscribers.forEach((fn) => fn(next))
    return
  }
  cached = null
  void load()
}

/**
 * AI 功能总开关当前是否开启。
 *
 * `enabled === false` 才代表确定关闭；`null` 是「还没读到/读失败」，此时不做任何提示。
 * 关闭不再意味着入口不可用：推理端点会退回规则解析（T02947 裁决 A），这里只用来改提示。
 * 仍在跑的旧打包版后端可能依旧返回 403，由 apiError.isAiDisabledError 兜住。
 */
export function useAIEnabled(): { enabled: boolean | null; refresh: () => void } {
  const [enabled, setEnabled] = useState<boolean | null>(cached)

  useEffect(() => {
    subscribers.add(setEnabled)
    setEnabled(cached)
    if (cached === null) void load()
    return () => { subscribers.delete(setEnabled) }
  }, [])

  return { enabled, refresh: () => void load() }
}

/** 入口提示：开关关闭时这些功能退回规则解析，仍然可点（T02947 裁决 A） */
export const AI_GATE_OFF_TIP = 'AI 已关闭：该功能退回规则解析，结果不是 AI 判断（可在「配置-AI 服务」开启）'
