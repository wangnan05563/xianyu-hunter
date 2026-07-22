// frontend/src/mobile/pages/SearchConfig/index.tsx
// 移动端搜索参数：page_size / sort_type / timeout / regions / filter_tags
// 设计要点：直接读写 AppConfig.search 段，filter_tags 用标签输入
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Spin, App, InputNumber, Select, Button, Space, Alert, theme, Tag, Input,
} from 'antd'
import { SaveOutlined, ReloadOutlined } from '@ant-design/icons'
import { configApi } from '../../../api/config'
import type { AppConfig } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'

type SearchConfig = AppConfig['search']

const SORT_OPTIONS = [
  { value: 'pub_time', label: '最新发布' },
  { value: 'price_asc', label: '价格升序' },
  { value: 'price_desc', label: '价格降序' },
  { value: 'want_cnt', label: '想要数' },
]

export default function MobileSearchConfig() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [form, setForm] = useState<SearchConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [tagInput, setTagInput] = useState('')

  const load = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const cfg = await configApi.get()
      setForm(cfg.search)
    } catch (e) {
      message.error(extractApiError(e, '加载失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void load() }, [load])

  const save = async (): Promise<void> => {
    if (!form) return
    setSaving(true)
    try {
      const cfg = await configApi.get()
      await configApi.save({ ...cfg, search: form })
      message.success('已保存')
    } catch (e) {
      message.error(extractApiError(e, '保存失败'), 3)
    } finally {
      setSaving(false)
    }
  }

  const addTag = (): void => {
    const tag = tagInput.trim()
    if (!tag || !form) return
    if (form.filter_tags.includes(tag)) {
      message.warning('标签已存在')
      return
    }
    setForm({ ...form, filter_tags: [...form.filter_tags, tag] })
    setTagInput('')
  }

  const removeTag = (tag: string): void => {
    if (!form) return
    setForm({ ...form, filter_tags: form.filter_tags.filter((t) => t !== tag) })
  }

  if (loading || !form) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  return (
    <div>
      <Alert
        type="info"
        showIcon
        message="搜索参数影响闲鱼商品搜索行为"
        description="任务级搜索参数可在任务编辑页覆盖。"
        style={{ marginBottom: 12, fontSize: 12 }}
      />

      <Card size="small" style={{ marginBottom: 10 }} title="基本参数">
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              每页条数（page_size）
            </div>
            <InputNumber
              value={form.page_size}
              onChange={(v) => v !== null && setForm({ ...form, page_size: v })}
              min={10}
              max={100}
              step={10}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              排序方式
            </div>
            <Select
              value={form.sort_type}
              onChange={(v) => setForm({ ...form, sort_type: v })}
              options={SORT_OPTIONS}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              超时时间（秒）
            </div>
            <InputNumber
              value={form.timeout}
              onChange={(v) => v !== null && setForm({ ...form, timeout: v })}
              min={5}
              max={120}
              step={5}
              style={{ width: '100%' }}
              addonAfter="s" /* NOSONAR - addonAfter 在 antd 5.x 仍可用，迁移到 InputNumber.Group 会破坏现有布局，暂不迁移 */
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>
              地区筛选
            </div>
            <Input
              value={form.regions}
              onChange={(e) => setForm({ ...form, regions: e.target.value })}
              placeholder="如：全国 / 北京 / 上海"
            />
          </div>
        </Space>
      </Card>

      <Card size="small" style={{ marginBottom: 12 }} title="过滤标签">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <Input
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              placeholder="输入标签后回车"
              onPressEnter={addTag}
              style={{ flex: 1 }}
            />
            <Button onClick={addTag}>添加</Button>
          </div>
          {form.filter_tags.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {form.filter_tags.map((tag) => (
                <Tag
                  key={tag}
                  closable
                  onClose={() => removeTag(tag)}
                  color="blue"
                >
                  {tag}
                </Tag>
              ))}
            </div>
          )}
        </Space>
      </Card>

      <Space size={8} style={{ width: '100%' }}>
        <Button icon={<ReloadOutlined />} onClick={() => void load()} style={{ flex: 1 }}>
          重新加载
        </Button>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save} style={{ flex: 2 }}>
          保存配置
        </Button>
      </Space>
    </div>
  )
}
