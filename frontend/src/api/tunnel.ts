import client from './client'

// 内网穿透 API：一键远程访问（系统维护 → 内网穿透）

export interface TunnelStatus {
  status: 'running' | 'stopped'
  public_url: string | null
  provider: string
}

export interface TunnelConfig {
  provider: string
  local_port: number
  cpolar_authtoken_masked: string
  cpolar_authtoken_configured: boolean
  binary_path: string
}

export interface TunnelConfigBody {
  provider: string
  local_port: number
  cpolar_authtoken: string
  binary_path: string
}

// 下载失败时后端返回的手动放置指引
export interface TunnelDownloadError {
  detail: string
  error_type: 'binary_download_failed'
  manual_path: string
  download_urls: string[]
}

export const tunnelApi = {
  getStatus: () =>
    client.get<TunnelStatus>('/api/tunnel/status').then((r) => r.data),

  start: () =>
    client.post<TunnelStatus>('/api/tunnel/start').then((r) => r.data),

  stop: () =>
    client.post<TunnelStatus>('/api/tunnel/stop').then((r) => r.data),

  getConfig: () =>
    client.get<TunnelConfig>('/api/tunnel/config').then((r) => r.data),

  saveConfig: (body: TunnelConfigBody) =>
    client.post<{ ok: boolean; message: string }>('/api/tunnel/config', body).then((r) => r.data),
}
