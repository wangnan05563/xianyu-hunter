// 系统清理 → 缓存清理的范围选项（桌面端 pages/Maintenance/Cleanup.tsx 与
// 移动端 mobile/pages/Cleanup 共用，避免两端对「不适用」的措辞/置灰各写一套）
//
// T02739：打包版（PyInstaller）没有源码树，__pycache__ 扫描恒为 0——这一档必须
// 置灰并写明不适用，而不是留一个永远清不掉的按钮。是否适用由后端 status 接口
// 的 cache.pycache_applicable 回带（is_frozen() 判定），前端不自行猜测运行形态。

export interface CacheTargetOption {
  value: string
  label: string
  disabled?: boolean
}

/** 打包版选中 Python 编译缓存时的说明（不适用，非「已清空」） */
export const PYCACHE_NOT_APPLICABLE_HINT = '打包版无源码字节码缓存，此项不适用'

export function cacheTargetOptions(pycacheApplicable: boolean): CacheTargetOption[] {
  return [
    // 「全部」在打包版只剩浏览器数据，标签如实收窄，避免承诺清一份不存在的缓存
    { value: 'all', label: pycacheApplicable ? '全部缓存' : '全部缓存（浏览器数据）', disabled: false },
    { value: 'browser_data', label: '浏览器数据（含登录态）', disabled: false },
    {
      value: 'pycache',
      label: pycacheApplicable
        ? 'Python 编译缓存（__pycache__）'
        : 'Python 编译缓存（__pycache__）· 不适用',
      disabled: !pycacheApplicable,
    },
  ]
}
