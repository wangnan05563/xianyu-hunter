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
  auto_start: boolean
  tunnel_mode: 'quick' | 'named'
  tunnel_name: string
  tunnel_id: string
  credentials_file: string
  hostname: string
  cert_file: string
  cert_file_configured: boolean
}

export interface TunnelConfigBody {
  provider: string
  local_port: number
  cpolar_authtoken: string
  binary_path: string
  auto_start: boolean
  tunnel_mode: 'quick' | 'named'
  tunnel_name: string
  tunnel_id: string
  credentials_file: string
  hostname: string
  cert_file: string
}

// 下载失败时后端返回的手动放置指引
export interface TunnelDownloadError {
  detail: string
  error_type: 'binary_download_failed'
  manual_path: string
  download_urls: string[]
}

// Named Tunnel setup 向导各步骤的响应
export interface CloudflareLoginResult {
  ok: boolean
  cert_file: string
  message: string
}

export interface CloudflareCreateResult {
  ok: boolean
  tunnel_id: string
  credentials_file: string
  tunnel_name: string
  message: string
}

export interface CloudflareRouteDnsResult {
  ok: boolean
  public_url: string
  message: string
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

  // Named Tunnel 配置向导
  cloudflareLogin: () =>
    client.post<CloudflareLoginResult>('/api/tunnel/cloudflare/login').then((r) => r.data),

  cloudflareCreate: (body: { tunnel_name: string; cert_file?: string }) =>
    client.post<CloudflareCreateResult>('/api/tunnel/cloudflare/create', body).then((r) => r.data),

  cloudflareRouteDns: (body: { tunnel_name_or_id: string; hostname: string; cert_file?: string }) =>
    client.post<CloudflareRouteDnsResult>('/api/tunnel/cloudflare/route-dns', body).then((r) => r.data),
}
