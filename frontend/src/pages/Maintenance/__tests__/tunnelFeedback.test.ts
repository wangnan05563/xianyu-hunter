// @vitest-environment jsdom
/**
 * T02590 / PRD 4.6（内网穿透语义与文案）纯函数契约测试
 *
 * 覆盖四条真实后果：
 * - 4.6-1：保存回执以 `POST /config` 后端文案为准，运行态保存不得再说「下次启动生效」
 * - 4.6-2：脏检测覆盖全部表单字段（旧实现只看 provider），authtoken 空串=不修改不算脏
 * - 4.6-4：向导置灰步骤必须给出「被什么卡住」；解锁后回到动作描述
 * - 4.6-5：停止确认可复述当前公网地址（地址会变是停止的真实后果）
 */
import { describe, expect, it } from 'vitest'
import {
  buildTunnelSaveCopy,
  tunnelDirtyFields,
  wizardLockedTips,
  buildTunnelStopCopy,
  type TunnelFormState,
} from '../Tunnel'
import type { TunnelConfig } from '../../../api/tunnel'

const baseConfig: TunnelConfig = {
  provider: 'cloudflare',
  local_port: 8800,
  cpolar_authtoken_masked: '',
  cpolar_authtoken_configured: false,
  binary_path: '',
  auto_start: false,
  tunnel_mode: 'quick',
  tunnel_name: '',
  tunnel_id: '',
  credentials_file: '',
  hostname: '',
  cert_file: '',
  cert_file_configured: false,
}

const cleanForm: TunnelFormState = {
  provider: 'cloudflare',
  local_port: 8800,
  cpolar_authtoken: '',
  binary_path: '',
  auto_start: false,
  tunnel_mode: 'quick',
}

describe('tunnelDirtyFields（4.6-2）', () => {
  it('表单与已保存配置一致时不脏', () => {
    expect(tunnelDirtyFields(baseConfig, cleanForm)).toEqual([])
  })

  it('config 尚未加载时不判定脏，避免用默认值谎报「有修改」', () => {
    expect(tunnelDirtyFields(null, { ...cleanForm, local_port: 1234 })).toEqual([])
  })

  it('只看 provider 远远不够：端口/模式/自启动/二进制路径任一变化都要报出来', () => {
    expect(tunnelDirtyFields(baseConfig, { ...cleanForm, local_port: 9000 })).toContain('本地端口')
    expect(tunnelDirtyFields(baseConfig, { ...cleanForm, tunnel_mode: 'named' })).toContain('隧道模式')
    expect(tunnelDirtyFields(baseConfig, { ...cleanForm, auto_start: true })).toContain('开机自启动')
    expect(tunnelDirtyFields(baseConfig, { ...cleanForm, binary_path: 'D:/x/cloudflared.exe' }))
      .toContain('二进制路径')
  })

  it('多字段同脏时全部列出，供黄条显示「有 N 项」', () => {
    const dirty = tunnelDirtyFields(baseConfig, { ...cleanForm, provider: 'tailscale', local_port: 9000 })
    expect(dirty).toEqual(['穿透服务', '本地端口'])
  })

  it('authtoken 空串＝不修改（后端约定），非空才算脏；纯空格不算填了', () => {
    expect(tunnelDirtyFields(baseConfig, { ...cleanForm, cpolar_authtoken: '' })).toEqual([])
    expect(tunnelDirtyFields(baseConfig, { ...cleanForm, cpolar_authtoken: '   ' })).toEqual([])
    expect(tunnelDirtyFields(baseConfig, { ...cleanForm, cpolar_authtoken: 'abc' })).toContain('Authtoken')
  })
})

describe('buildTunnelSaveCopy（4.6-1）', () => {
  it('后端回传运行态文案时逐字采用，并升级为 warning', () => {
    const r = buildTunnelSaveCopy(
      { message: '配置已保存；已按新配置重建隧道服务，当前隧道已断开、公网地址失效，需手动重新启动隧道', tunnel_was_running: true },
      false,
      false,
    )
    expect(r.level).toBe('warning')
    expect(r.text).toContain('当前隧道已断开')
    expect(r.text).not.toContain('下次启动')
  })

  it('后端回传空闲态文案时按 success 展示', () => {
    const r = buildTunnelSaveCopy(
      { message: '配置已保存，下次启动隧道时生效（当前无运行中的隧道）', tunnel_was_running: false },
      false,
      true,
    )
    expect(r.level).toBe('success')
    expect(r.text).toContain('下次启动隧道时生效')
  })

  it('后端未回传文案才走本地兜底，且兜底同样区分运行态', () => {
    expect(buildTunnelSaveCopy(null, false, true).level).toBe('warning')
    expect(buildTunnelSaveCopy(null, false, true).text).toContain('已断开')
    expect(buildTunnelSaveCopy(null, false, false).text).toContain('下次启动')
  })

  it('启动前自动同步（autoStart）保持即时文案，不谎称断线', () => {
    const r = buildTunnelSaveCopy({ message: '随便', tunnel_was_running: true }, true, true)
    expect(r).toEqual({ level: 'success', text: '配置已同步，正在启动隧道...' })
  })
})

describe('wizardLockedTips（4.6-4）', () => {
  it('未授权时②不可用并说明前置条件', () => {
    expect(wizardLockedTips(baseConfig).create).toContain('需先完成 ① 授权登录')
  })

  it('已授权但未建隧道时③不可用，②恢复为动作描述', () => {
    const c = wizardLockedTips({ ...baseConfig, cert_file: 'C:/cert.pem' })
    expect(c.create).toBe('创建命名隧道（或重新创建）')
    expect(c.dns).toContain('需先完成 ② 创建隧道')
  })

  it('三步齐备时两个提示都是动作描述，不再提「暂不可用」', () => {
    const c = wizardLockedTips({ ...baseConfig, cert_file: 'a', tunnel_id: 'b' })
    expect(c.dns).toBe('配置 DNS 路由（CNAME 记录）')
    expect(c.create).not.toContain('暂不可用')
  })
})

describe('buildTunnelStopCopy（4.6-5）', () => {
  it('有公网地址时确认可复述该地址，并说明重启会换地址', () => {
    const c = buildTunnelStopCopy('cloudflare', 'https://abc.trycloudflare.com')
    expect(c.scope).toContain('https://abc.trycloudflare.com')
    expect(c.count).toBe('正在运行的隧道 1 条（cloudflare）')
    expect(c.recovery).toContain('重新启动会拿到新的随机地址')
    expect(c.recovery).toContain('固定域名模式重启后地址不变')
  })

  it('地址没读到时不编造 URL，如实标注并说明需重新复制', () => {
    const c = buildTunnelStopCopy('tailscale', null)
    expect(c.scope).toContain('（未获取到）')
    expect(c.scope).not.toContain('http')
    expect(c.recovery).toContain('重新启动后需重新复制新的公网地址')
  })
})
