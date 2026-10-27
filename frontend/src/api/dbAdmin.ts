import client from './client'
import { filenameFromHeaders, readExportError, rowsFromHeaders } from '../utils/exportFeedback'
import type {
  DbSchema,
  DbRowListResponse,
  DbTablesResponse,
  DbAuditLogResponse,
  CascadeRelation,
  CascadePreviewResponse,
} from './types'

// 数据库维护 API：业务表在线 CRUD（系统维护 → 数据库维护）
// 所有危险操作（删除/批量删除/导入）必须传 confirm_token=CONFIRM_DELETE
export const CONFIRM_TOKEN = 'CONFIRM_DELETE'

/** 数据库表导出结果：blob 交页面触发下载，行数/文件名来自响应头 */
export interface DbExportResult {
  blob: Blob
  /** 后端 X-Export-Rows 回带的真实行数；老后端未回带时为 null */
  rows: number | null
  filename: string
}

export const dbAdminApi = {
  // 列出表白名单及行数（侧边栏数据）
  listTables: () => client.get<DbTablesResponse>('/api/db-admin/tables').then((r) => r.data),

  // 取表结构（动态生成编辑表单用）
  getSchema: (table: string) =>
    client.get<DbSchema>(`/api/db-admin/tables/${table}/schema`).then((r) => r.data),

  // 分页查询（支持 search/order_by）
  listRows: (
    table: string,
    params: { limit?: number; offset?: number; order_by?: string; search?: string } = {},
  ) =>
    client
      .get<DbRowListResponse>(`/api/db-admin/tables/${table}/rows`, { params })
      .then((r) => r.data),

  // 新增一行
  createRow: (table: string, values: Record<string, unknown>) =>
    client.post<{ ok: boolean; table: string }>(`/api/db-admin/tables/${table}/rows`, { values }).then((r) => r.data),

  // 按主键更新
  updateRow: (table: string, pkValue: string | number, values: Record<string, unknown>) =>
    client
      .patch<{ ok: boolean; affected: number }>(`/api/db-admin/tables/${table}/rows/${encodeURIComponent(String(pkValue))}`, {
        values,
      })
      .then((r) => r.data),

  // 删除单行（query 传 confirm_token，返回含级联影响）
  deleteRow: (table: string, pkValue: string | number) =>
    client
      .delete<{ ok: boolean; affected: number; cascade: Record<string, number> }>(
        `/api/db-admin/tables/${table}/rows/${encodeURIComponent(String(pkValue))}`,
        { params: { confirm_token: CONFIRM_TOKEN } },
      )
      .then((r) => r.data),

  // 批量删除（返回含级联影响）
  batchDelete: (table: string, ids: Array<string | number>) =>
    client
      .post<{ ok: boolean; requested: number; affected: number; cascade: Record<string, number> }>(
        `/api/db-admin/tables/${table}/rows/batch-delete`,
        { ids, confirm_token: CONFIRM_TOKEN },
      )
      .then((r) => r.data),

  // 级联影响预览（删除前调用，返回各关联表将被影响的行数）
  cascadePreview: (table: string, ids: Array<string | number>) =>
    client
      .post<CascadePreviewResponse>(`/api/db-admin/tables/${table}/cascade-preview`, { ids })
      .then((r) => r.data),

  // 导出（返回 blob + 行数/文件名，浏览器侧触发下载）
  // 全表导出没有行数上限（events 等大表可达数万行），30s 默认超时会把「正在导出」
  // 变成「导出失败: timeout」——这里的超时与后端实测耗时对齐（T02576）。
  // 失败时抛可读错误（T02707：blob 错误体必须解析出 detail，不能只显示状态码）。
  exportRows: async (table: string, format: 'csv' | 'json'): Promise<DbExportResult> => {
    let res
    try {
      res = await client.get(`/api/db-admin/tables/${table}/export`, {
        params: { format },
        responseType: 'blob',
        timeout: 300000,
      })
    } catch (err) {
      throw await readExportError(err, `数据表 ${table}`)
    }
    return {
      blob: res.data as Blob,
      rows: rowsFromHeaders(res.headers),
      filename: filenameFromHeaders(res.headers, `${table}.${format}`),
    }
  },

  // 导入（二维数组 + 表头）
  // 单次最多 5000 行且逐行独立提交，耗时随行数线性增长，同样需要放宽超时。
  // mode 只有 insert：覆盖导入按 D-8 裁决关闭，后端对 replace 直接 400（T02749）。
  importRows: (
    table: string,
    rows: unknown[][],
    headers?: string[],
    mode: 'insert' = 'insert',
  ) =>
    client
      .post<{
        ok: boolean;
        total: number;
        inserted: number;
        skipped: number;
        /** 真实失败行数（errors 只是最多 20 条样例） */
        error_count: number;
        errors: string[];
      }>(
        `/api/db-admin/tables/${table}/import`,
        { rows, headers, mode, confirm_token: CONFIRM_TOKEN },
        { timeout: 300000 },
      )
      .then((r) => r.data),

  // 审计日志
  getAuditLog: (limit = 100) =>
    client.get<DbAuditLogResponse>('/api/db-admin/audit-log', { params: { limit } }).then((r) => r.data),
}

// 重新导出类型便于前端页面 import
// 用 `export type { ... } from` 转发可避免 isolatedModules 下
// 「declares locally, but it is not exported」误报（import 的类型无法被 re-export）
export type { DbColumn, DbTableInfo, CascadeRelation, CascadePreviewResponse } from './types'
