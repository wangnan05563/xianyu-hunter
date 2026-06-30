import client from './client'
import type { AppConfig, BackupItem } from './types'

// 配置 API：负责应用全局配置的读取、预览、保存及版本/备份管理
export const configApi = {
  get: () => client.get<AppConfig>('/api/config').then((r) => r.data),

  preview: (payload: Partial<AppConfig>) =>
    client.post('/api/config/preview', payload).then((r) => r.data),

  save: (payload: Partial<AppConfig>, dryRun = false) =>
    client.post('/api/config/save', { payload, dry_run: dryRun }).then((r) => r.data),

  // 配置版本管理
  getVersion: () =>
    client
      .get<{ version: number; latest_backup_ts: string | null; latest_backup_file: string | null }>(
        '/api/config/version',
      )
      .then((r) => r.data),

  listBackups: () =>
    client
      .get<{ backups: BackupItem[]; count: number; keep: number }>('/api/config/backups')
      .then((r) => r.data),

  rollback: () => client.post('/api/config/rollback').then((r) => r.data),

  restoreBackup: (filename: string) =>
    client.post(`/api/config/restore-backup?filename=${encodeURIComponent(filename)}`).then((r) => r.data),

  export: () => client.get('/api/config/export').then((r) => r.data),

  import: (config: Record<string, unknown>, confirm = false) =>
    client.post('/api/config/import', { schema: 'xianyu_hunter.config/v1', config, confirm }).then((r) => r.data),
}
