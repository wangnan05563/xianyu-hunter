import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  isGuideDone,
  markGuideDone,
  resetGuideDone,
  resetAllGuides,
} from '../guideStorage'
import { storage, __resetForTesting } from '../../utils/storage'

// Mock localStorage（与 utils/__tests__/storage.test.ts 同模式）
const store = new Map<string, string>()
const localStorageMock = {
  getItem: vi.fn((key: string) => store.get(key) ?? null),
  setItem: vi.fn((key: string, value: string) => { store.set(key, value) }),
  removeItem: vi.fn((key: string) => { store.delete(key) }),
  clear: vi.fn(() => { store.clear() }),
}

beforeEach(() => {
  store.clear()
  vi.clearAllMocks()
  __resetForTesting()
  Object.defineProperty(globalThis, 'localStorage', {
    value: localStorageMock,
    writable: true,
    configurable: true,
  })
})

describe('guideStorage', () => {
  it('初始时引导未完成', () => {
    expect(isGuideDone('/tasks')).toBe(false)
  })

  it('markGuideDone 后 isGuideDone 返回 true', () => {
    markGuideDone('/tasks')
    expect(isGuideDone('/tasks')).toBe(true)
  })

  it('不同路由的引导状态相互隔离', () => {
    markGuideDone('/tasks')
    expect(isGuideDone('/tasks')).toBe(true)
    expect(isGuideDone('/orders')).toBe(false)
  })

  it('resetGuideDone 重置单个路由状态', () => {
    markGuideDone('/tasks')
    resetGuideDone('/tasks')
    expect(isGuideDone('/tasks')).toBe(false)
  })

  it('resetAllGuides 一次性重置多个路由', () => {
    markGuideDone('/tasks')
    markGuideDone('/orders')
    resetAllGuides(['/tasks', '/orders'])
    expect(isGuideDone('/tasks')).toBe(false)
    expect(isGuideDone('/orders')).toBe(false)
  })

  it('状态持久化到底层存储（含格式封装）', () => {
    markGuideDone('/tasks')
    // 底层键为 xh.guide.done./tasks，封装格式含 __v
    const raw = store.get('xh.guide.done./tasks')
    expect(raw).toBeDefined()
    const parsed = JSON.parse(raw!)
    expect(parsed.__v).toBeDefined()
    expect(parsed.data).toBe('1')
  })

  it('localStorage 中数据可通过 storage API 读取（跨层打通）', () => {
    markGuideDone('/config/price')
    // 用通用 storage 工具重新读取已验证写入格式
    expect(storage.get('xh.guide.done./config/price', '0')).toBe('1')
  })
})