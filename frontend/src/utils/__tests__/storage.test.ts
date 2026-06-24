import { describe, it, expect, beforeEach, vi } from 'vitest'
import { storage } from '../storage'

// Mock localStorage
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
  // 每次测试前重置 storage 模块的 _available 缓存
  // 通过让 localStorageMock 正常工作来确保 isAvailable 返回 true
  Object.defineProperty(globalThis, 'localStorage', {
    value: localStorageMock,
    writable: true,
    configurable: true,
  })
})

describe('storage.get', () => {
  it('读取已存储的数据', () => {
    storage.set('test.key', { name: '张三', age: 30 })
    const result = storage.get('test.key', null)
    expect(result).toEqual({ name: '张三', age: 30 })
  })

  it('键不存在时返回默认值', () => {
    const result = storage.get('not.exist', 'default')
    expect(result).toBe('default')
  })

  it('validator 验证通过时返回数据', () => {
    storage.set('test.num', 42)
    const result = storage.get('test.num', 0, (v): v is number => typeof v === 'number')
    expect(result).toBe(42)
  })

  it('validator 验证失败时返回默认值并清除脏数据', () => {
    storage.set('test.dirty', 'not-a-number')
    const result = storage.get('test.dirty', 0, (v): v is number => typeof v === 'number')
    expect(result).toBe(0)
    // 脏数据应被清除
    expect(localStorageMock.getItem('test.dirty')).toBeNull()
  })

  it('JSON 解析失败时返回默认值', () => {
    // 直接写入非法 JSON 到底层存储，绕过 storage.set 的封装
    store.set('test.broken', '{invalid json')
    const result = storage.get('test.broken', 'fallback')
    expect(result).toBe('fallback')
  })

  it('格式不匹配（无 __v 字段）时返回默认值', () => {
    // 直接写入未封装的数据，绕过 storage.set
    store.set('test.raw', JSON.stringify({ data: 'value' }))
    const result = storage.get('test.raw', 'default')
    expect(result).toBe('default')
  })
})

describe('storage.set', () => {
  it('正常写入数据', () => {
    const ok = storage.set('test.set', { value: 123 })
    expect(ok).toBe(true)
    expect(localStorageMock.setItem).toHaveBeenCalled()
  })

  it('存储格式包含版本号', () => {
    storage.set('test.fmt', 'hello')
    const raw = store.get('test.fmt')
    expect(raw).toBeDefined()
    const parsed = JSON.parse(raw!)
    expect(parsed).toHaveProperty('__v')
    expect(parsed).toHaveProperty('data', 'hello')
  })
})

describe('storage.remove', () => {
  it('删除已存在的键', () => {
    storage.set('test.rm', 'value')
    storage.remove('test.rm')
    expect(storage.get('test.rm', 'default')).toBe('default')
  })

  it('删除不存在的键不报错', () => {
    expect(() => storage.remove('not.exist')).not.toThrow()
  })
})

describe('storage.isAvailable', () => {
  it('localStorage 可用时返回 true', () => {
    expect(storage.isAvailable()).toBe(true)
  })

  it('localStorage 不可用时返回 false', () => {
    // 模拟 localStorage 抛异常（隐私模式）
    const brokenStorage = {
      getItem: () => { throw new Error('SecurityError') },
      setItem: () => { throw new Error('SecurityError') },
      removeItem: () => { throw new Error('SecurityError') },
      clear: () => {},
    }
    Object.defineProperty(globalThis, 'localStorage', {
      value: brokenStorage,
      writable: true,
      configurable: true,
    })
    expect(storage.isAvailable()).toBe(false)
  })
})

describe('storage 回退机制', () => {
  it('localStorage 不可用时回退到内存存储', () => {
    // 模拟 localStorage 不可用
    const brokenStorage = {
      getItem: () => { throw new Error('SecurityError') },
      setItem: () => { throw new Error('SecurityError') },
      removeItem: () => { throw new Error('SecurityError') },
      clear: () => {},
    }
    Object.defineProperty(globalThis, 'localStorage', {
      value: brokenStorage,
      writable: true,
      configurable: true,
    })

    // set 返回 false 表示未持久化（使用内存回退）
    const ok = storage.set('test.fallback', 'memory-value')
    expect(ok).toBe(false)

    // 仍可读取（从内存回退存储）
    const result = storage.get('test.fallback', 'default')
    expect(result).toBe('memory-value')
  })
})
