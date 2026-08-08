/**
 * API 模块模板
 *
 * 复制后替换以下占位符：
 * - {Module}：模块名（如 items、orders）
 * - {ModuleItem}：类型名（如 Item、Order）
 *
 * 设计要点：
 * - 所有请求必须包含 credentials: 'include' 以传递认证 Cookie
 * - 统一错误处理：HTTP 非 2xx 抛出 Error，由调用方处理
 * - 类型严格：请求/响应均有 TypeScript 类型定义
 */

// ==================== 类型定义 ====================

export interface {ModuleItem} {
  id: string;
  name: string;
  status: 'active' | 'inactive' | 'deleted';
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
}

export interface {Module}ListResponse {
  items: {ModuleItem}[];
  total: number;
  page: number;
  page_size: number;
}

export interface Create{ModuleItem}Request {
  name: string;
  metadata?: Record<string, unknown>;
}

export interface Update{ModuleItem}Request {
  name?: string;
  status?: 'active' | 'inactive' | 'deleted';
  metadata?: Record<string, unknown>;
}

export interface {Module}ListParams {
  page?: number;
  page_size?: number;
  keyword?: string;
  task_id?: string;
}

// ==================== API 函数 ====================

const API_BASE = '/api/{module}';

/**
 * 通用的 fetch 封装
 *
 * 为什么单独封装：
 * - 统一 credentials: 'include' 配置
 * - 统一错误处理逻辑
 * - 便于后续扩展拦截器（如 401 自动跳转登录）
 */
async function request<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    credentials: 'include', // 【强制】必须包含，传递认证 Cookie
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
    } catch {
      // JSON 解析失败，使用默认错误消息
    }
    throw new Error(errorMessage);
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/**
 * 分页查询 {Module} 列表
 */
export async function list{Module}(
  params: {Module}ListParams = {},
): Promise<{Module}ListResponse> {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set('page', String(params.page));
  if (params.page_size) searchParams.set('page_size', String(params.page_size));
  if (params.keyword) searchParams.set('keyword', params.keyword);
  if (params.task_id) searchParams.set('task_id', params.task_id);

  const query = searchParams.toString();
  return request<{Module}ListResponse>(`${API_BASE}${query ? `?${query}` : ''}`);
}

/**
 * 查询单个 {ModuleItem}
 */
export async function get{ModuleItem}(id: string): Promise<{ModuleItem}> {
  return request<{ModuleItem}>(`${API_BASE}/${id}`);
}

/**
 * 创建 {ModuleItem}
 */
export async function create{ModuleItem}(
  data: Create{ModuleItem}Request,
): Promise<{ModuleItem}> {
  return request<{ModuleItem}>(API_BASE, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * 更新 {ModuleItem}（部分更新）
 */
export async function update{ModuleItem}(
  id: string,
  data: Update{ModuleItem}Request,
): Promise<{ModuleItem}> {
  return request<{ModuleItem}>(`${API_BASE}/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * 删除 {ModuleItem}
 */
export async function delete{ModuleItem}(id: string): Promise<void> {
  await request<void>(`${API_BASE}/${id}`, {
    method: 'DELETE',
  });
}
