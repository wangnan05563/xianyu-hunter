import { useEffect, useState } from 'react'

/**
 * 移动端断点检测 Hook
 *
 * 为什么用 matchMedia 而非 resize 事件：
 * 1. matchMedia 是声明式 API，浏览器内部优化，性能优于 resize+getBoundingClientRect
 * 2. 断点逻辑交给 CSS 媒体查询，与样式断点保持单一来源
 * 3. 767px 与 antd 默认 sm/md 断点对齐（< 768 为移动端）
 */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(max-width: 767px)').matches
  })

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 767px)')
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    // 现代浏览器用 addEventListener，避免已废弃的 addListener
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [])

  return isMobile
}
