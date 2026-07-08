import { useState, useEffect } from 'react'

// 移动端 UA 正则：覆盖 iPhone/Android/iPad/Windows Phone
// 注意：iPadOS 13+ UA 与桌面 macOS 一致，需额外检测 Macintosh + 触摸屏
const MOBILE_UA_PATTERN = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i

// 视口宽度阈值（像素）：低于此值视为窄屏移动端
// 为什么需要宽度兜底：F12 设备模拟器 / 桌面窗口缩放 等场景下，
// UA 不含移动端关键字时（如 Edge 中文版简化为 "Linux; Android 10"），
// 仅靠 UA 识别会失效，导致桌面 SPA 在窄屏下被压成竖条
const MOBILE_VIEWPORT_MAX = 768

export function isMobileUA(userAgent: string): boolean {
  if (MOBILE_UA_PATTERN.test(userAgent)) return true
  // iPadOS 13+ 伪装为桌面 Mac，需检查是否支持触摸
  if (/Macintosh/i.test(userAgent) && typeof document !== 'undefined') {
    return 'ontouchend' in document
  }
  return false
}

// 综合判定：UA + 视口宽度 + 触屏指针类型
// 优先级：UA 最强（含 Mobile 关键字直接判为移动端），
// 视口宽度作为窄屏兜底，触屏指针作为辅助
function detectMobile(): boolean {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false
  if (isMobileUA(navigator.userAgent)) return true
  // 视口宽度兜底：F12 设备模拟器 / 窄屏浏览器自动识别
  if (window.innerWidth <= MOBILE_VIEWPORT_MAX) return true
  // 触屏指针：surface / iPad Pro 等设备的细分场景
  if (window.matchMedia && window.matchMedia('(pointer: coarse)').matches && window.innerWidth <= 1024) return true
  return false
}

export function useMobileDetect(): boolean {
  // 初始即用 detectMobile() 而非 false：避免 useEffect 异步更新导致
  // 首次 paint 走桌面路由、再 setState 重渲染的闪烁
  const [isMobile, setIsMobile] = useState<boolean>(detectMobile)

  useEffect(() => {
    const handler = () => setIsMobile(detectMobile())
    // 监听窗口尺寸变化（如 F12 切换设备模拟器），实时同步路由
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  return isMobile
}
