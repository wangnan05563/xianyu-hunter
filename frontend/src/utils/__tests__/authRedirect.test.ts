// T02717：401 登录落点按路径前缀分流。
// 移动端路由挂在 /xianyu/m/ 下，登录/退出必须留在移动端；
// 路径判断要精确到 /xianyu/m 与 /xianyu/m/...，不能把 /xianyu/market 误判成移动端。
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  authLoginPath,
  isAuthLoginPath,
  isMobileAppPath,
  mobileLoginRedirect,
} from '../authRedirect'

const ORIGIN = 'http://localhost:3000'

describe('401 登录落点（T02717）', () => {
  it('移动端路径回 /m/login', () => {
    for (const path of ['/xianyu/m', '/xianyu/m/', '/xianyu/m/orders/o1', '/xianyu/m/tasks/abc/edit']) {
      expect(isMobileAppPath(path), path).toBe(true)
      expect(authLoginPath(path), path).toBe('/xianyu/m/login')
    }
  })

  it('桌面路径回 /login，前缀相近的 /xianyu/market 不被误判', () => {
    for (const path of ['/xianyu/', '/xianyu/orders', '/xianyu/market', '/xianyu/mobile-config']) {
      expect(isMobileAppPath(path), path).toBe(false)
      expect(authLoginPath(path), path).toBe('/xianyu/login')
    }
  })

  it('两个登录页自身都算登录页，401 不会在登录页上二次跳转', () => {
    expect(isAuthLoginPath('/xianyu/login')).toBe(true)
    expect(isAuthLoginPath('/xianyu/m/login')).toBe(true)
    expect(isAuthLoginPath('/xianyu/m/orders')).toBe(false)
  })

  it('登录后回跳只接受同源移动端路径', () => {
    expect(mobileLoginRedirect('/xianyu/m/orders/o1?status=failed', ORIGIN))
      .toBe('/xianyu/m/orders/o1?status=failed')
    expect(mobileLoginRedirect('/xianyu/m', ORIGIN)).toBe('/xianyu/m')
    // 桌面路径 / 登录页自身 / 外站（即使路径伪装成移动端）/ 协议相对 / javascript: 一律回移动端首页。
    // 外站用例特意带 /xianyu/m 路径：只查路径不查 origin 的实现会把它放行成开放重定向。
    for (const raw of ['/xianyu/orders', '/xianyu/m/login', 'https://evil.example/x',
      'https://evil.example/xianyu/m/orders', '//evil.example/xianyu/m/orders',
      'javascript:alert(1)', '', null]) {
      expect(mobileLoginRedirect(raw, ORIGIN), String(raw)).toBe('/xianyu/m/')
    }
  })

  it('client.ts 的 401 目标由 authLoginPath 计算，不写死桌面登录页', () => {
    const src = readFileSync(resolve(__dirname, '../../api/client.ts'), 'utf-8')
    expect(src).toContain('authLoginPath(pathname)')
    expect(src).toContain('isAuthLoginPath(pathname)')
    expect(src).not.toContain('/xianyu/login?redirect=')
  })
})
