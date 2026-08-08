/**
 * Zustand Store 模板
 *
 * 复制后替换以下占位符：
 * - {Module}Store：Store 名（如 ItemsStore、OrdersStore）
 * - {ModuleItem}：类型名（如 Item、Order）
 *
 * 设计要点：
 * - Zustand 4.5+ 的 create 模式
 * - 状态与操作分离：state 字段 + actions 对象
 * - 通过 set 更新状态，避免直接修改
 * - 仅放全局共享状态，组件私有状态用 useState
 */

import { create } from 'zustand';
import type { {ModuleItem} } from '../api/{module}Api';

interface {Module}State {
  // ==================== 状态字段 ====================
  /** {Module} 列表 */
  items: {ModuleItem}[];
  /** 当前选中的 {ModuleItem} */
  selectedItem: {ModuleItem} | null;
  /** 加载状态 */
  loading: boolean;
  /** 错误信息 */
  error: string | null;
  /** 最后更新时间 */
  lastUpdated: number | null;
}

interface {Module}Actions {
  // ==================== 操作方法 ====================
  /** 设置列表 */
  setItems: (items: {ModuleItem}[]) => void;
  /** 添加单项（创建后调用） */
  addItem: (item: {ModuleItem}) => void;
  /** 更新单项（PATCH 后调用） */
  updateItem: (id: string, updates: Partial<{ModuleItem}>) => void;
  /** 删除单项 */
  removeItem: (id: string) => void;
  /** 选中 */
  selectItem: (item: {ModuleItem} | null) => void;
  /** 设置加载状态 */
  setLoading: (loading: boolean) => void;
  /** 设置错误信息 */
  setError: (error: string | null) => void;
  /** 重置为初始状态 */
  reset: () => void;
}

type {Module}Store = {Module}State & {Module}Actions;

const initialState: {Module}State = {
  items: [],
  selectedItem: null,
  loading: false,
  error: null,
  lastUpdated: null,
};

/**
 * {Module} 全局状态 Store
 *
 * 使用场景：
 * - 多个组件需要共享 {Module} 列表
 * - 跨组件需要访问选中状态
 * - 全局加载/错误状态
 *
 * 不适用场景：
 * - 仅单个组件使用的列表（用 useState 即可）
 * - 频繁更新的临时状态
 */
export const use{Module}Store = create<{Module}Store>((set) => ({
  ...initialState,

  // ==================== Actions ====================

  setItems: (items) =>
    set({
      items,
      lastUpdated: Date.now(),
      error: null,
    }),

  addItem: (item) =>
    set((state) => ({
      items: [item, ...state.items],
      lastUpdated: Date.now(),
    })),

  updateItem: (id, updates) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.id === id ? { ...item, ...updates } : item,
      ),
      selectedItem:
        state.selectedItem?.id === id
          ? { ...state.selectedItem, ...updates }
          : state.selectedItem,
      lastUpdated: Date.now(),
    })),

  removeItem: (id) =>
    set((state) => ({
      items: state.items.filter((item) => item.id !== id),
      selectedItem:
        state.selectedItem?.id === id ? null : state.selectedItem,
      lastUpdated: Date.now(),
    })),

  selectItem: (item) => set({ selectedItem: item }),

  setLoading: (loading) => set({ loading }),

  setError: (error) => set({ error }),

  reset: () => set(initialState),
}));

// ==================== 选择器 Hooks ====================

/**
 * 仅订阅 items 列表
 *
 * 为什么用选择器：避免组件因无关状态变化而重渲染
 */
export function use{Module}Items() {
  return use{Module}Store((state) => state.items);
}

/**
 * 仅订阅选中项
 */
export function useSelected{Module}Item() {
  return use{Module}Store((state) => state.selectedItem);
}

/**
 * 仅订阅加载状态
 */
export function use{Module}Loading() {
  return use{Module}Store((state) => state.loading);
}

/**
 * 仅订阅错误信息
 */
export function use{Module}Error() {
  return use{Module}Store((state) => state.error);
}
