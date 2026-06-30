import { useCallback, useMemo } from 'react'
import { usePersistentState } from './usePersistentState'

/**
 * 列配置 Hook —— 管理表格列的显示顺序与可见性，并持久化到 localStorage
 *
 * 为什么需要这个 Hook：
 * 1. 评估明细页字段多（17 列），不同用户关注点不同，需要个性化定制
 * 2. 列顺序与可见性属于 UI 偏好，应跨会话保留，避免每次重新配置
 * 3. 抽象为通用 Hook 后，商品列表等其他页面也可复用
 *
 * 数据结构：
 * - order: 列 key 数组，按显示顺序排列（包含所有列，含已隐藏的）
 * - hidden: 隐藏列的 key 集合（Set 序列化为数组存储）
 *
 * 不变量：
 * - order 必须包含所有列 key（新增列时通过 normalize 合并）
 * - hidden 中的 key 必须存在于 order 中
 * - 至少保留 1 列可见（toggleHidden 中保护）
 */
export interface ColumnConfig {
  /** 列的唯一标识，对应 ColumnDef.key */
  key: string
  /** 列标题（用于配置面板展示） */
  label: string
  /** 是否禁止隐藏（如标题、评分等核心列） */
  locked?: boolean
}

export function useColumnConfig(
  storageKey: string,
  definitions: ColumnConfig[],
) {
  // 默认顺序：按 definitions 给定顺序
  const defaultOrder = useMemo(() => definitions.map((d) => d.key), [definitions])

  // 列顺序：持久化存储。新列出现时合并到末尾，删除列时自动清理
  const [order, setOrder] = usePersistentState<string[]>(storageKey + '.order', defaultOrder, {
    validator: (v): v is string[] =>
      Array.isArray(v) && v.every((k) => typeof k === 'string'),
  })

  // 隐藏列集合：用数组持久化，使用时转 Set 加速查询
  const [hiddenArr, setHiddenArr] = usePersistentState<string[]>(storageKey + '.hidden', [], {
    validator: (v): v is string[] =>
      Array.isArray(v) && v.every((k) => typeof k === 'string'),
  })

  // 规范化 order：合并新增列、移除已删除列，保证 order 与 definitions 一致
  // 为什么用 useMemo 而非 useEffect：避免渲染中出现不一致状态，派生值即时计算
  const normalizedOrder = useMemo(() => {
    const defKeys = new Set(definitions.map((d) => d.key))
    const seen = new Set<string>()
    // 保留用户已配置的顺序，但仅包含当前定义中存在的 key
    const result: string[] = []
    for (const k of order) {
      if (defKeys.has(k) && !seen.has(k)) {
        result.push(k)
        seen.add(k)
      }
    }
    // 追加新增列（definitions 中存在但 order 中没有的）
    for (const d of definitions) {
      if (!seen.has(d.key)) {
        result.push(d.key)
        seen.add(d.key)
      }
    }
    return result
  }, [order, definitions])

  // 同步规范化后的 order 回 state（仅当发生变化时）
  // 为什么不在 render 中直接 setState：会导致无限渲染循环
  // 改为：在 useEffect 中同步，且仅在长度或内容不一致时更新
  // 实际上由于 useMemo 已经返回正确顺序，直接使用 normalizedOrder 即可，
  // 下次 setOrder 时会写入完整数据，无需额外同步

  const hidden = useMemo(() => new Set(hiddenArr), [hiddenArr])

  /** 切换某列的显示/隐藏（locked 列禁止隐藏） */
  const toggleHidden = useCallback((key: string) => {
    const def = definitions.find((d) => d.key === key)
    if (def?.locked) return  // 核心列禁止隐藏
    setHiddenArr((prev) => {
      const set = new Set(prev)
      // 保护：至少保留 1 列可见
      const visibleCount = normalizedOrder.filter((k) => !set.has(k)).length
      if (!set.has(key)) {
        // 即将隐藏：检查是否会清空所有可见列
        if (visibleCount <= 1) return prev  // 拒绝操作
        set.add(key)
      } else {
        set.delete(key)
      }
      return Array.from(set)
    })
  }, [definitions, normalizedOrder, setHiddenArr])

  /** 移动列顺序：把 active 移到 over 的位置 */
  const moveColumn = useCallback((activeKey: string, overKey: string) => {
    if (activeKey === overKey) return
    setOrder((prev) => {
      const oldIndex = prev.indexOf(activeKey)
      const newIndex = prev.indexOf(overKey)
      if (oldIndex === -1 || newIndex === -1) return prev
      const next = [...prev]
      const [moved] = next.splice(oldIndex, 1)
      next.splice(newIndex, 0, moved)
      return next
    })
  }, [setOrder])

  /** 重置为默认配置 */
  const reset = useCallback(() => {
    setOrder(defaultOrder)
    setHiddenArr([])
  }, [defaultOrder, setOrder, setHiddenArr])

  /** 根据当前配置筛选并重排列定义 */
  const applyConfig = useCallback(<T extends { key?: string }>(
    columns: T[],
  ): T[] => {
    // 构造 key -> column 的映射（用第一个出现的同 key 列）
    const colMap = new Map<string, T>()
    for (const c of columns) {
      const k = c.key
      if (k && !colMap.has(k)) colMap.set(k, c)
    }
    // 按 normalizedOrder 顺序输出，跳过隐藏列
    const result: T[] = []
    for (const k of normalizedOrder) {
      if (hidden.has(k)) continue
      const col = colMap.get(k)
      if (col) result.push(col)
    }
    // 追加未在 order 中但存在于 columns 的列（兜底，理论上不应发生）
    for (const c of columns) {
      const k = c.key
      if (!k || !normalizedOrder.includes(k)) result.push(c)
    }
    return result
  }, [normalizedOrder, hidden])

  /** 获取列的可配置元数据（按当前顺序） */
  const orderedDefinitions = useMemo(() => {
    const defMap = new Map(definitions.map((d) => [d.key, d]))
    return normalizedOrder
      .map((k) => defMap.get(k))
      .filter((d): d is ColumnConfig => Boolean(d))
  }, [normalizedOrder, definitions])

  return {
    order: normalizedOrder,
    hidden,
    toggleHidden,
    moveColumn,
    reset,
    applyConfig,
    orderedDefinitions,
  }
}
