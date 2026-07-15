/**
 * localStorage 封装工具
 *
 * 为什么需要封装：
 * 1. 统一错误处理：隐私模式/存储已满等场景下 localStorage 操作会抛异常，
 *    各调用方重复 try-catch 容易遗漏
 * 2. 数据验证：读取时自动验证数据格式，脏数据返回默认值而非崩溃
 * 3. 回退机制：localStorage 不可用时回退到内存 Map，保证功能不中断
 * 4. 版本管理：存储格式含 __v 字段，未来格式变更时可平滑迁移
 */

/** 存储格式版本号，格式变更时递增 */
const STORAGE_VERSION = 1

/** 内存回退存储：localStorage 不可用时使用 */
const memoryStore = new Map<string, string>()

/** localStorage 是否可用（只检测一次，避免重复开销） */
let _available: boolean | null = null

function isAvailable(): boolean {
  if (_available !== null) return _available
  try {
    const testKey = '__xh_storage_test__'
    localStorage.setItem(testKey, '1')
    localStorage.removeItem(testKey)
    _available = true
  } catch {
    // 隐私模式、storage 被禁用、配额已满等
    _available = false
  }
  return _available
}

/**
 * 从存储中读取并验证数据
 *
 * @param key 存储键
 * @param defaultValue 默认值（读取失败或验证不通过时返回）
 * @param validator 可选的数据验证函数，返回 false 则视为无效数据
 */
export function get<T>(
  key: string,
  defaultValue: T,
  validator?: (value: unknown) => value is T,
): T {
  try {
    const raw = isAvailable()
      ? localStorage.getItem(key)
      : memoryStore.get(key) ?? null

    if (!raw) return defaultValue

    const parsed = JSON.parse(raw) as { __v?: number; data?: unknown }

    // 格式校验：必须是带 __v 的封装格式
    if (!parsed || typeof parsed.__v !== 'number' || !('data' in parsed)) {
      return defaultValue
    }

    const data = parsed.data

    // 验证器校验：调用方提供的数据格式验证
    if (validator && !validator(data)) {
      // 脏数据清除，避免下次再次解析失败
      remove(key)
      return defaultValue
    }

    return data as T
  } catch {
    // JSON 解析失败等异常，静默回退
    return defaultValue
  }
}

/**
 * 写入数据到存储
 *
 * @returns true 表示成功持久化，false 表示使用内存回退（非持久）
 */
export function set<T>(key: string, value: T): boolean {
  const wrapped = JSON.stringify({ __v: STORAGE_VERSION, data: value })
  try {
    if (isAvailable()) {
      localStorage.setItem(key, wrapped)
      return true
    }
    memoryStore.set(key, wrapped)
    return false
  } catch {
    // 存储已满或被禁用，回退到内存
    memoryStore.set(key, wrapped)
    return false
  }
}

/** 删除指定键 */
export function remove(key: string): void {
  try {
    if (isAvailable()) {
      localStorage.removeItem(key)
    }
    memoryStore.delete(key)
  } catch {
    memoryStore.delete(key)
  }
}

/** 存储是否可用（true 表示 localStorage 可用，数据会持久化） */
export const storage = {
  get,
  set,
  remove,
  isAvailable,
}

/**
 * 仅用于测试：重置可用性缓存和内存回退存储
 *
 * 为什么需要：_available 是模块级缓存（只检测一次），测试 mock localStorage 后
 * 必须重置缓存才能让 isAvailable 重新检测，否则测试间状态泄漏
 */
export function __resetForTesting(): void {
  _available = null
  memoryStore.clear()
}
