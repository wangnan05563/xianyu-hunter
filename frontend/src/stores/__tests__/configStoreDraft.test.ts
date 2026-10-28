import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../api', () => ({
  configApi: { get: vi.fn(), save: vi.fn() },
}))

import type { AppConfig } from '../../api'
import { configApi } from '../../api'
import { SCOPE_EVAL } from '../configDirty'
import { useConfigStore } from '../configStore'

const server = () =>
  ({
    eval: { pass_score: 60, thresholds: { on_sale_count: 3 } },
    search: { page_size: 20, regions: ['a'] },
  }) as unknown as AppConfig

describe('configStore.load 草稿保留（T02572）', () => {
  beforeEach(() => {
    useConfigStore.setState({ config: null, original: null, loading: false, error: null })
    vi.mocked(configApi.get).mockReset()
  })

  it('无 scope 的 load（TaskEditor 打开）不会抹掉配置页草稿', async () => {
    vi.mocked(configApi.get).mockResolvedValue(server())
    await useConfigStore.getState().load()
    const loaded = useConfigStore.getState().config as AppConfig
    useConfigStore.getState().update({ eval: { ...loaded.eval, pass_score: 70 } })

    await useConfigStore.getState().load()

    const { config, original } = useConfigStore.getState()
    expect((config as AppConfig).eval.pass_score).toBe(70)
    expect((original as AppConfig).eval.pass_score).toBe(60)
    expect(useConfigStore.getState().dirtyPathsInScope(SCOPE_EVAL)).toEqual(['eval.pass_score'])
  })

  it('服务端新值补进未改动字段，改动字段仍以草稿为准', async () => {
    vi.mocked(configApi.get).mockResolvedValue(server())
    await useConfigStore.getState().load()
    const loaded = useConfigStore.getState().config as AppConfig
    useConfigStore.getState().update({ eval: { ...loaded.eval, pass_score: 70 } })

    const changed = server()
    changed.eval.thresholds.on_sale_count = 5
    vi.mocked(configApi.get).mockResolvedValue(changed)
    await useConfigStore.getState().load()

    const config = useConfigStore.getState().config as AppConfig
    expect(config.eval.thresholds.on_sale_count).toBe(5)
    expect(config.eval.pass_score).toBe(70)
  })
})
