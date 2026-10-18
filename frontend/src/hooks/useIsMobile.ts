import { useEffect, useState } from 'react'
import { MOBILE_MEDIA_QUERY } from './breakpoints'

/**
 * 移动端断点检测 Hook
 *
 * 为什么用 matchMedia 而非 resize 事件：
 * 1. matchMedia 是声明式 API，浏览器内部优化，性能优于 resize+getBoundingClientRect
 * 2. 断点逻辑交给 CSS 媒体查询，与样式断点保持单一来源
 * 3. 阈值取自 breakpoints 的 NARROW_MAX_PX（< 768 为移动端），与 Sider 收起同一口径
 */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState<boolean>(() => {
    // S7741：globalThis 总是已声明，直接比较即可
    if (globalThis.window === undefined) return false
    return globalThis.matchMedia(MOBILE_MEDIA_QUERY).matches
  })

  useEffect(() => {
    const mql = globalThis.matchMedia(MOBILE_MEDIA_QUERY)
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    // 现代浏览器用 addEventListener，避免已废弃的 addListener
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [])

  return isMobile
}
