import { useState, useEffect } from 'react'

// 移动端 UA 正则：覆盖 iPhone/Android/iPad/Windows Phone
// 注意：iPadOS 13+ UA 与桌面 macOS 一致，需额外检测 Macintosh + 触摸屏
const MOBILE_UA_PATTERN = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i

export function isMobileUA(userAgent: string): boolean {
  if (MOBILE_UA_PATTERN.test(userAgent)) return true
  // iPadOS 13+ 伪装为桌面 Mac，需检查是否支持触摸
  if (/Macintosh/i.test(userAgent) && typeof document !== 'undefined') {
    return 'ontouchend' in document
  }
  return false
}

export function useMobileDetect(): boolean {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    setIsMobile(isMobileUA(navigator.userAgent))
  }, [])

  return isMobile
}
