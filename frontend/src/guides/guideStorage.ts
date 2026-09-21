/**
 * 引导向导系统 —— 已完成状态存储层
 *
 * 为什么独立一个模块：引导完成状态涉及多个键（首次访问触发 + 手动完成），
 * 且需要与 MenuGuide 的 route 建立映射，集中管理避免散落。
 *
 * 存储键规范：xh.guide.done.<route>（值为 '1'）
 * 约定：仅当用户完成一次引导（走到最后一步并关闭）后才写入 done；
 * 中途跳过/主动关闭不视为完成，后续常驻按钮仍可唤起。
 */
import { get, set, remove } from '../utils/storage'

/** 已完成引导的键前缀：拼接 route（如 /tasks → 键 xh.guide.done./tasks） */
const DONE_PREFIX = 'xh.guide.done.'

/** 单条引导是否已标记完成 */
export function isGuideDone(route: string): boolean {
  return get<string>(DONE_PREFIX + route, '0') === '1'
}

/** 标记引导完成（首次触发后不再自动弹出，但常驻按钮仍可手动唤起） */
export function markGuideDone(route: string): void {
  set(DONE_PREFIX + route, '1')
}

/** 重置单个路由的引导完成标记（供调试/重新引导场景使用） */
export function resetGuideDone(route: string): void {
  remove(DONE_PREFIX + route)
}

/** 重置全部引导完成标记（供"重新开始引导"入口使用） */
export function resetAllGuides(routes: string[]): void {
  for (const r of routes) resetGuideDone(r)
}