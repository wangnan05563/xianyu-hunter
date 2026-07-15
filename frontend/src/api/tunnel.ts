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

// Tailscale Funnel 首次启用需要用户在浏览器完成授权
export interface TunnelTailscaleAuthError {
  detail: string
  error_type: 'tailscale_funnel_auth'
  auth_url: string
}

// Named Tunnel setup 向导各步骤的响应

// login 两阶段 API：POST start（非阻塞）+ GET poll
// cloudflared tunnel login 是交互式命令，会打开浏览器让用户授权。
// 前端先调 cloudflareLoginStart() 拿到授权 URL，再轮询 cloudflareLoginStatus() 等 cert.pem 生成。
export type CloudflareLoginStatus = 'waiting' | 'success' | 'failed' | 'idle'

export interface CloudflareLoginStartResult {
  status: CloudflareLoginStatus
  auth_url: string | null
  message: string
  output?: string
}

export interface CloudflareLoginStatusResult {
  status: CloudflareLoginStatus
  auth_url: string | null
  cert_file?: string
  message: string
  output?: string
  checked_paths?: string[]
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
  // login 两阶段：start 启动子进程拿授权 URL，status 轮询 cert.pem 是否生成
  cloudflareLoginStart: () =>
    client.post<CloudflareLoginStartResult>('/api/tunnel/cloudflare/login').then((r) => r.data),

  cloudflareLoginStatus: () =>
    client.get<CloudflareLoginStatusResult>('/api/tunnel/cloudflare/login/status').then((r) => r.data),

  cloudflareCreate: (body: { tunnel_name: string; cert_file?: string }) =>
    client.post<CloudflareCreateResult>('/api/tunnel/cloudflare/create', body).then((r) => r.data),

  cloudflareRouteDns: (body: { tunnel_name_or_id: string; hostname: string; cert_file?: string }) =>
    client.post<CloudflareRouteDnsResult>('/api/tunnel/cloudflare/route-dns', body).then((r) => r.data),
}
