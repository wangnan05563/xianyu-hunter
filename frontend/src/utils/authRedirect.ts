/**
 * 401 登录落点（T02717）：SPA 挂在 /xianyu/ 下，移动端路由在 /xianyu/m/。
 * 手机上登录/退出必须回移动端登录页，否则会被甩到桌面版。
 *
 * 只认 /xianyu/m 与 /xianyu/m/...，不能用 startsWith('/xianyu/m')——
 * 否则 /xianyu/market、/xianyu/mobile-* 这类桌面路径会被误判成移动端。
 */
const SPA_PREFIX = '/xianyu'

export function isMobileAppPath(pathname: string): boolean {
  return pathname === `${SPA_PREFIX}/m` || pathname.startsWith(`${SPA_PREFIX}/m/`)
}

/** 401 时应跳转的登录页（含 SPA 前缀，浏览器原生跳转不走 basename） */
export function authLoginPath(pathname: string): string {
  return isMobileAppPath(pathname) ? `${SPA_PREFIX}/m/login` : `${SPA_PREFIX}/login`
}

/** 当前是否已在登录页：两个登录页都算，避免 401 在登录页自身反复跳转 */
export function isAuthLoginPath(pathname: string): boolean {
  return pathname === `${SPA_PREFIX}/login` || pathname === `${SPA_PREFIX}/m/login`
}

/**
 * 移动端登录成功后的回跳地址：只接受同源的 /xianyu/m 路径。
 * 桌面路径会把手机用户带走，登录页自身会形成回环，外部 URL 则等于开放重定向——
 * 三类都退回移动端首页。
 */
export function mobileLoginRedirect(raw: string | null, origin: string): string {
  const fallback = `${SPA_PREFIX}/m/`
  if (!raw) return fallback
  try {
    const target = new URL(raw, origin)
    const sameOrigin = target.origin === origin
    if (sameOrigin && isMobileAppPath(target.pathname) && !isAuthLoginPath(target.pathname)) {
      return target.pathname + target.search
    }
  } catch {
    // 非法 URL（含 javascript: 等）：不猜，回首页
  }
  return fallback
}
