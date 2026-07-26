import { useState, useEffect } from 'react'

// 移动端 UA 正则：覆盖 iPhone/Android/iPad/Windows Phone
// 注意：iPadOS 13+ UA 与桌面 macOS 一致，需额外检测 Macintosh + 触摸屏
const MOBILE_UA_PATTERN = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i

// 视口宽度阈值（像素）：低于此值视为窄屏移动端
// 为什么需要宽度兜底：F12 设备模拟器 / 桌面窗口缩放 等场景下，
// UA 不含移动端关键字时（如 Edge 中文版简化为 "Linux; Android 10"），
// 仅靠 UA 识别会失效，导致桌面 SPA 在窄屏下被压成竖条
const MOBILE_VIEWPORT_MAX = 600

export function isMobileUA(userAgent: string): boolean {
  if (MOBILE_UA_PATTERN.test(userAgent)) return true
  // iPadOS 13+ 伪装为桌面 Mac，需检查是否支持触摸
  // ontouchend 在 Chrome DevTools / Playwright 设备仿真模式下可能未被正确设置，
  // 使用 navigator.maxTouchPoints > 0 作为更可靠的触摸能力 fallback
  if (/Macintosh/i.test(userAgent)) {
    if (typeof document !== 'undefined' && 'ontouchend' in document) return true
    if (typeof navigator !== 'undefined' && (navigator.maxTouchPoints || 0) > 0) return true
  }
  return false
}

// 综合判定：UA + 视口宽度
// 优先级：UA 最强（含 Mobile 关键字直接判为移动端），
// 视口宽度作为窄屏兜底
// 注意：不要加 pointer:coarse 触屏指针判定！
// 触屏笔记本 / 二合一设备 / Surface 触屏模式会触发 coarse，
// 但视口宽度通常 >= 1024（桌面分辨率），若同时判定为移动端会导致
// 桌面用户被强制跳到 /xianyu/m/ 路由（PC 端完全不可用）。
function detectMobile(): boolean {
  // 用 globalThis.* + 直接与 undefined 比较（避免 S7764/S7741 误报）
  if (globalThis.window === undefined || globalThis.navigator === undefined) return false
  const ua = globalThis.navigator.userAgent
  const width = globalThis.window.innerWidth
  const ontouchend = globalThis.document !== undefined && 'ontouchend' in globalThis.document
  // 设备仿真模式下 'ontouchend' 可能失效，maxTouchPoints 是更稳定的触摸信号
  // 仅在 Macintosh UA 分支生效，避免触屏笔记本（Surface 等）误判为移动端
  const maxTouchPoints = navigator.maxTouchPoints || 0
  const matchedByPattern = MOBILE_UA_PATTERN.test(ua)
  const matchedByMac = /Macintosh/i.test(ua) && (ontouchend || maxTouchPoints > 0)
  const result = matchedByPattern || matchedByMac || width <= MOBILE_VIEWPORT_MAX
  return result
}

export function useMobileDetect(): boolean {
  // 初始即用 detectMobile() 而非 false：避免 useEffect 异步更新导致
  // 首次 paint 走桌面路由、再 setState 重渲染的闪烁
  const [isMobile, setIsMobile] = useState<boolean>(detectMobile)

  useEffect(() => {
    const handler = () => setIsMobile(detectMobile())
    // 监听窗口尺寸变化（如 F12 切换设备模拟器），实时同步路由
    globalThis.window.addEventListener('resize', handler)
    return () => globalThis.window.removeEventListener('resize', handler)
  }, [])

  return isMobile
}
