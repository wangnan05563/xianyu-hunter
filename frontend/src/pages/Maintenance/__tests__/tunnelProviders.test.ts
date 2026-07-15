import { describe, expect, it } from 'vitest'

import { TUNNEL_PROVIDERS } from '../tunnelProviders'


describe('TUNNEL_PROVIDERS', () => {
  it('includes Tailscale Funnel with fixed-domain prerequisites', () => {
    const tailscale = TUNNEL_PROVIDERS.tailscale

    expect(Object.keys(TUNNEL_PROVIDERS)).toEqual([
      'cloudflare',
      'cpolar',
      'tailscale',
    ])
    expect(tailscale.label).toBe('Tailscale Funnel（免费固定地址）')
    expect(tailscale.description).toContain('固定 ts.net 地址')
    expect(tailscale.description).toContain('预先安装并登录')
    expect(tailscale.installUrl).toBe('https://tailscale.com/download/windows')
  })
})
