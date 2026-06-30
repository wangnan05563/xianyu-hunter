import client from './client'

// About API 响应类型（与后端 api_about.py 契约对齐）
export interface AboutInfo {
  product: string
  version: string
  build_date: string
  git_sha: string
  python: string
  platform: string
}

export interface UpdateCheckResult {
  current: string
  latest: string
  has_update: boolean
  release_url: string
  checked_at: string
  // 标识数据来源：local=降级（GitHub 不可达），remote=实际查询 GitHub Releases API
  source: 'local' | 'remote'
  // 成功时携带的发布时间（ISO 8601，可能为空串）；失败时不存在
  published_at?: string
  // 失败时的诊断信息（仅 source='local' 时可能出现）
  error?: string
}

// 关于菜单 API：系统元信息 + 检查更新
export const aboutApi = {
  get: () => client.get<AboutInfo>('/api/about').then((r) => r.data),
  checkUpdate: () => client.get<UpdateCheckResult>('/api/about/check-update').then((r) => r.data),
}
