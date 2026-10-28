import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../api', () => ({
  configApi: { get: vi.fn(), save: vi.fn() },
}))

import type { AppConfig } from '../../api'
import { configApi } from '../../api'
import { SCOPE_EVAL, SCOPE_SEARCH } from '../configDirty'
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
    vi.mocked(configApi.save).mockReset()
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

describe('configStore 按页段提交（T02571）', () => {
  beforeEach(() => {
    useConfigStore.setState({ config: null, original: null, loading: false, error: null })
    vi.mocked(configApi.get).mockReset()
    vi.mocked(configApi.save).mockReset()
  })

  const dirtyBoth = async () => {
    vi.mocked(configApi.get).mockResolvedValue(server())
    await useConfigStore.getState().load()
    const loaded = useConfigStore.getState().config as AppConfig
    useConfigStore.getState().update({
      eval: { ...loaded.eval, pass_score: 70 },
      search: { ...loaded.search, page_size: 50 },
    })
  }

  it('带 scope 的保存只提交本页段，别页草稿不落盘', async () => {
    await dirtyBoth()
    vi.mocked(configApi.save).mockResolvedValue({ diffs: [] })

    await useConfigStore.getState().confirmSave(SCOPE_EVAL)

    const payload = vi.mocked(configApi.save).mock.calls[0][0] as Record<string, unknown>
    expect(Object.keys(payload)).toEqual(['eval'])
  })

  it('本页段没改动就不发请求', async () => {
    vi.mocked(configApi.get).mockResolvedValue(server())
    await useConfigStore.getState().load()

    await useConfigStore.getState().confirmSave(SCOPE_SEARCH)
    expect(vi.mocked(configApi.save)).not.toHaveBeenCalled()

    expect(await useConfigStore.getState().previewSave(SCOPE_SEARCH)).toEqual([])
    expect(vi.mocked(configApi.save)).not.toHaveBeenCalled()
  })

  it('保存后本页段变干净，别页仍算脏', async () => {
    await dirtyBoth()
    vi.mocked(configApi.save).mockResolvedValue({ diffs: [] })

    await useConfigStore.getState().confirmSave(SCOPE_EVAL)

    expect(useConfigStore.getState().dirtyPathsInScope(SCOPE_EVAL)).toEqual([])
    expect(useConfigStore.getState().dirtyPathsInScope(SCOPE_SEARCH)).toEqual(['search.page_size'])
  })

  it('带 scope 的重置只清本页草稿', async () => {
    await dirtyBoth()

    useConfigStore.getState().reset(SCOPE_EVAL)

    const config = useConfigStore.getState().config as AppConfig
    expect(config.eval.pass_score).toBe(60)
    expect(config.search.page_size).toBe(50)
  })

  it('不传 scope 保持整份提交（TaskEditor 等全局入口）', async () => {
    await dirtyBoth()
    vi.mocked(configApi.save).mockResolvedValue({ diffs: [] })

    await useConfigStore.getState().confirmSave()

    const payload = vi.mocked(configApi.save).mock.calls[0][0] as Record<string, unknown>
    expect(Object.keys(payload).sort()).toEqual(['eval', 'search'])
    expect(useConfigStore.getState().dirtyPathsInScope(SCOPE_EVAL)).toEqual([])
    expect(useConfigStore.getState().dirtyPathsInScope(SCOPE_SEARCH)).toEqual([])
  })
})
