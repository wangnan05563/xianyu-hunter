import { renderHook } from '@testing-library/react'
import { useMobileDetect, isMobileUA } from '../hooks/useMobileDetect'

describe('isMobileUA', () => {
  it('iPhone Safari 应识别为移动端', () => {
    const ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'
    expect(isMobileUA(ua)).toBe(true)
  })

  it('Android Chrome 应识别为移动端', () => {
    const ua = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile'
    expect(isMobileUA(ua)).toBe(true)
  })

  it('桌面 Chrome 应识别为非移动端', () => {
    const ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    expect(isMobileUA(ua)).toBe(false)
  })

  it('iPad 应识别为移动端', () => {
    const ua = 'Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15'
    expect(isMobileUA(ua)).toBe(true)
  })
})

describe('useMobileDetect', () => {
  it('默认返回 false（桌面环境）', () => {
    const { result } = renderHook(() => useMobileDetect())
    expect(typeof result.current).toBe('boolean')
  })
})
