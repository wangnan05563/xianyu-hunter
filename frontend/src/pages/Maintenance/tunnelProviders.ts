export interface TunnelProviderMetadata {
  label: string
  description: string
  installUrl?: string
}

export const TUNNEL_PROVIDERS: Record<string, TunnelProviderMetadata> = {
  cloudflare: {
    label: 'Cloudflare Tunnel',
    description: '免注册快速模式，或绑定自有域名获得固定地址。大陆访问可能不稳定。',
  },
  cpolar: {
    label: 'cpolar（国内推荐）',
    description: '国内服务器稳定，需注册账号获取 authtoken。',
  },
  tailscale: {
    label: 'Tailscale Funnel（免费固定地址）',
    description: '免费固定 ts.net 地址；需要在本机预先安装并登录 Tailscale。',
    installUrl: 'https://tailscale.com/download/windows',
  },
}

export const TUNNEL_PROVIDER_OPTIONS = Object.entries(TUNNEL_PROVIDERS).map(
  ([value, metadata]) => ({ value, label: metadata.label }),
)
