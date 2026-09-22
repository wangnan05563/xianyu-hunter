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
  // 安装包直接下载地址（仅 has_update 且有安装包资产时非空）。
  // 为空时前端降级为「跳转 GitHub 手动下载」，不展示一键更新按钮
  download_url?: string
}

// 下载任务的进度状态（对应 /api/about/update/download 返回）
export interface UpdateDownloadState {
  ok: boolean
  // pending=未开始 / downloading=下载中 / done=完成 / error=失败
  status: 'pending' | 'downloading' | 'done' | 'error'
  latest: string
  // 总字节数（服务端未返回 content-length 时为 0）
  total: number
  // 已下载字节数
  bytes_downloaded: number
  // 失败信息（status=error 时非空）
  error?: string
  progress?: number
}

// 安装触发结果（对应 POST /api/about/update/install 返回）
export interface UpdateInstallResult {
  ok: boolean
  message?: string
  error?: string
  path?: string
}

// 关于菜单 API：系统元信息 + 检查更新 + 一键下载安装
export const aboutApi = {
  get: () => client.get<AboutInfo>('/api/about').then((r) => r.data),
  checkUpdate: () => client.get<UpdateCheckResult>('/api/about/check-update').then((r) => r.data),
  // 发起/查询安装包下载：downloadUrl 来自 check-update 的 download_url
  downloadUpdate: (downloadUrl: string, latest: string) =>
    client.get<UpdateDownloadState>('/api/about/update/download', {
      params: { download_url: downloadUrl, latest },
    }).then((r) => r.data),
  // 触发静默安装已下载的安装包
  installUpdate: (downloadUrl: string) =>
    client.post<UpdateInstallResult>('/api/about/update/install', { download_url: downloadUrl }).then((r) => r.data),
}
