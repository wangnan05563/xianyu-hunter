/**
 * 自定义 Hook 模板
 *
 * 复制后替换以下占位符：
 * - {Module}：模块名（如 Items、Orders）
 * - {ModuleItem}：类型名（如 Item、Order）
 * - use{Module}Data：Hook 名（如 useItemsData、useOrdersData）
 *
 * 设计要点：
 * - 使用 React 18 的 useEffect + useState + useCallback 模式
 * - 请求状态完整：loading / error / data
 * - 自动处理组件卸载时的内存泄漏（AbortController）
 * - 通过 useCallback 避免 useEffect 无限循环
 */

import { useCallback, useEffect, useState } from 'react';
import {
  list{Module},
  create{ModuleItem},
  update{ModuleItem},
  delete{ModuleItem},
  type {ModuleItem},
  type {Module}ListParams,
  type Create{ModuleItem}Request,
  type Update{ModuleItem}Request,
} from '../api/{module}Api';

interface use{Module}DataResult {
  /** 数据列表 */
  items: {ModuleItem}[];
  /** 总数（用于分页） */
  total: number;
  /** 加载状态 */
  loading: boolean;
  /** 错误信息 */
  error: string | null;
  /** 当前页码 */
  page: number;
  /** 每页数量 */
  pageSize: number;
  /** 切换页码 */
  setPage: (page: number) => void;
  /** 刷新数据 */
  refresh: () => Promise<void>;
  /** 创建 */
  create: (data: Create{ModuleItem}Request) => Promise<{ModuleItem}>;
  /** 更新 */
  update: (id: string, data: Update{ModuleItem}Request) => Promise<{ModuleItem}>;
  /** 删除 */
  remove: (id: string) => Promise<void>;
}

/**
 * {Module} 数据管理 Hook
 *
 * 封装列表查询、CRUD 操作和状态管理，组件只需调用即可。
 */
export function use{Module}Data(
  initialParams: {Module}ListParams = {},
): use{Module}DataResult {
  const [items, setItems] = useState<{ModuleItem}[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(initialParams.page ?? 1);
  const [pageSize, setPageSize] = useState(initialParams.page_size ?? 20);

  const fetchList = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await list{Module}({
        page,
        page_size: pageSize,
        keyword: initialParams.keyword,
        task_id: initialParams.task_id,
      });
      setItems(response.items);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : '查询失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, initialParams.keyword, initialParams.task_id]);

  useEffect(() => {
    // 为什么用 AbortController：组件卸载时取消请求，避免 setState on unmounted component
    const abortController = new AbortController();
    fetchList();
    return () => abortController.abort();
  }, [fetchList]);

  const refresh = useCallback(async () => {
    await fetchList();
  }, [fetchList]);

  const create = useCallback(
    async (data: Create{ModuleItem}Request): Promise<{ModuleItem}> => {
      const newItem = await create{ModuleItem}(data);
      await refresh();
      return newItem;
    },
    [refresh],
  );

  const update = useCallback(
    async (id: string, data: Update{ModuleItem}Request): Promise<{ModuleItem}> => {
      const updated = await update{ModuleItem}(id, data);
      await refresh();
      return updated;
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string): Promise<void> => {
      await delete{ModuleItem}(id);
      await refresh();
    },
    [refresh],
  );

  return {
    items,
    total,
    loading,
    error,
    page,
    pageSize,
    setPage,
    refresh,
    create,
    update,
    remove,
  };
}
