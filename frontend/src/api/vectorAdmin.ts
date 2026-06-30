import client from './client'

// 向量数据库维护 API：ChromaDB 快照/清理/监控（系统维护 → 向量数据库维护）
// 危险操作（恢复/删除快照/清空/按来源删除）需 confirm_token=CONFIRM_DELETE
export const CONFIRM_TOKEN = 'CONFIRM_DELETE'

export interface VectorStatus {
  collection_name: string
  persist_path: string
  chunk_count: number
  data_size_bytes: number
  data_size_display: string
  snapshot_count: number
  last_snapshot_at: string | null
}

export interface VectorSnapshot {
  id: string
  size_bytes: number
  size_display: string
  created_at: string
  is_manual: boolean
}

export interface VectorAuditLog {
  id: number
  action: string
  target: string
  old_value_hash: string | null
  new_value_hash: string | null
  source: string
  created_at: string
}

export const vectorAdminApi = {
  // 状态总览
  getStatus: () =>
    client.get<VectorStatus>('/api/vector-admin/status').then((r) => r.data),

  // 快照列表
  listSnapshots: () =>
    client
      .get<{ items: VectorSnapshot[]; total: number }>('/api/vector-admin/snapshots')
      .then((r) => r.data),

  // 创建快照（label 可选，拼入目录名）
  createSnapshot: (label?: string) =>
    client
      .post<{ ok: boolean; snapshot_id: string }>('/api/vector-admin/snapshots', { label })
      .then((r) => r.data),

  // 从快照恢复（危险：覆盖当前集合）
  restoreSnapshot: (snapshotId: string) =>
    client
      .post<{ ok: boolean; restored_from: string }>(
        `/api/vector-admin/snapshots/${encodeURIComponent(snapshotId)}/restore`,
        { confirm_token: CONFIRM_TOKEN },
      )
      .then((r) => r.data),

  // 删除快照文件
  deleteSnapshot: (snapshotId: string) =>
    client
      .delete<{ ok: boolean; deleted: string }>(
        `/api/vector-admin/snapshots/${encodeURIComponent(snapshotId)}`,
        { params: { confirm_token: CONFIRM_TOKEN } },
      )
      .then((r) => r.data),

  // 清空集合
  cleanupAll: () =>
    client
      .post<{ ok: boolean; cleared: number }>('/api/vector-admin/cleanup/all', {
        confirm_token: CONFIRM_TOKEN,
      })
      .then((r) => r.data),

  // 按来源文件删除片段
  cleanupBySource: (sourceFile: string) =>
    client
      .post<{ ok: boolean; deleted: number }>('/api/vector-admin/cleanup/by-source', {
        source_file: sourceFile,
        confirm_token: CONFIRM_TOKEN,
      })
      .then((r) => r.data),

  // 审计日志
  getAuditLog: (limit = 100) =>
    client
      .get<{ items: VectorAuditLog[]; total: number }>('/api/vector-admin/audit-log', {
        params: { limit },
      })
      .then((r) => r.data),
}
