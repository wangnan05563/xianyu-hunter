import { useEffect, useState } from 'react'
import { Steps, Card, Form, Input, InputNumber, Slider, Button, Space, Radio, message, Result } from 'antd'
import { ArrowLeftOutlined, ArrowRightOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import TagEditor from '../../components/editors/TagEditor'
import CronEditor from '../../components/editors/CronEditor'
import { taskApi, TaskCreateBody } from '../../api'

// 闲鱼筛选标签（与后端 XIANYU_FILTER_MAP 对齐）
const searchFilterOptions = [
  { value: 'personal_idle', label: '👤 个人闲置', desc: '非商家' },
  { value: 'verified', label: '✓ 实名认证', desc: '已认证' },
  { value: 'account_guarantee', label: '🛡️ 账号担保', desc: '平台担保' },
  { value: 'free_shipping', label: '📦 包邮', desc: '免运费' },
  { value: 'super_shop', label: '⭐ 超级卖家', desc: '优质卖家' },
  { value: 'brand_new', label: '🆕 全新', desc: '未使用' },
  { value: 'strict_select', label: '🏅 严选', desc: '平台严选' },
  { value: 'resale', label: '🔄 转卖', desc: '转卖商品' },
]

const modeOptions = [
  { value: 'auto', label: '🤖 全自动', desc: '评估通过后自动抢单' },
  { value: 'semi_auto', label: '⚡ 半自动', desc: '通知 + 自动抢单（需确认）' },
  { value: 'confirm', label: '✋ 需确认', desc: '通知 + 人工确认抢单' },
  { value: 'notify', label: '🔔 仅通知', desc: '只通知不抢单' },
]

export default function TaskEditor() {
  const navigate = useNavigate()
  const { id } = useParams()
  const isEdit = !!id
  const [current, setCurrent] = useState(0)
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

  // 表单状态
  const [formData, setFormData] = useState<TaskCreateBody>({
    keyword: '',
    name: '',
    min_price: null,
    max_price: null,
    max_publish_days: 7,
    mode: 'confirm',
    region: '',
    exclude_words: [],
    search_filters: [],
  })
  const [cron, setCron] = useState('*/5 * * * *')

  // 编辑模式：加载现有任务
  useEffect(() => {
    if (id) {
      taskApi.get(id).then((task) => {
        const data: TaskCreateBody = {
          keyword: task.keyword,
          name: task.name,
          min_price: task.min_price,
          max_price: task.max_price,
          max_publish_days: task.max_publish_days,
          mode: task.mode,
          region: task.region || '',
          exclude_words: task.exclude_words ? JSON.parse(task.exclude_words) : [],
          search_filters: task.search_filters ? JSON.parse(task.search_filters) : [],
        }
        setFormData(data)
        setCron(task.cron)
        form.setFieldsValue(data)
      })
    }
  }, [id, form])

  const steps = [
    { title: '基础信息', desc: '关键词与模式' },
    { title: '价格与过滤', desc: '价格区间与筛选' },
    { title: '调度与确认', desc: 'Cron 与提交' },
  ]

  const handleNext = () => {
    if (current === 0 && !formData.keyword) {
      message.warning('请输入关键词')
      return
    }
    setCurrent(current + 1)
  }

  const handleSubmit = async () => {
    if (!formData.keyword) {
      message.warning('关键词不能为空')
      return
    }
    setLoading(true)
    try {
      const body: TaskCreateBody = {
        ...formData,
        name: formData.name || formData.keyword,
      }
      if (isEdit) {
        await taskApi.update(id!, body)
        message.success('任务已更新')
      } else {
        await taskApi.create(body)
        message.success('任务已创建')
      }
      navigate('/tasks')
    } catch {
      message.error(isEdit ? '更新失败' : '创建失败')
    } finally {
      setLoading(false)
    }
  }

  // 实时预览：闲鱼搜索 URL
  const searchUrl = (() => {
    const params = new URLSearchParams()
    params.set('q', formData.keyword)
    const filters = formData.search_filters ?? []
    if (filters.length > 0) {
      // 简化预览：展示标签
      params.set('filters', filters.join(','))
    }
    return `https://www.goofish.com/search?${params.toString()}`
  })()

  return (
    <div className="page-container">
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>

      <h2>{isEdit ? '编辑任务' : '新增任务（向导）'}</h2>

      <Steps current={current} items={steps} style={{ marginBottom: 24 }} />

      {/* Step 1: 基础信息 */}
      {current === 0 && (
        <Card title="Step 1 · 基础信息">
          <Form layout="vertical" form={form}>
            <Form.Item label="关键词（必填）" required>
              <Input
                placeholder="例：索尼 A7M4 / iPhone 15 Pro 256G"
                value={formData.keyword}
                onChange={(e) => setFormData({ ...formData, keyword: e.target.value })}
                size="large"
              />
            </Form.Item>

            <Form.Item label="任务名称（可选，默认=关键词）">
              <Input
                placeholder="给任务起个易记的名字"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </Form.Item>

            <Form.Item label="任务模式（点击选择）" required>
              <Radio.Group
                value={formData.mode}
                onChange={(e) => setFormData({ ...formData, mode: e.target.value })}
              >
                <Space wrap>
                  {modeOptions.map((opt) => (
                    <Radio.Button
                      key={opt.value}
                      value={opt.value}
                      style={{ height: 'auto', padding: '8px 16px', lineHeight: 1.5 }}
                    >
                      <div>
                        <div style={{ fontWeight: 600 }}>{opt.label}</div>
                        <div style={{ fontSize: 11, color: '#999' }}>{opt.desc}</div>
                      </div>
                    </Radio.Button>
                  ))}
                </Space>
              </Radio.Group>
            </Form.Item>
          </Form>

          {/* 实时预览：搜索 URL */}
          {formData.keyword && (
            <Card size="small" style={{ background: '#f0f5ff', marginTop: 16 }} title="🔍 实时预览：搜索 URL">
              <code style={{ fontSize: 12, wordBreak: 'break-all' }}>{searchUrl}</code>
            </Card>
          )}
        </Card>
      )}

      {/* Step 2: 价格与过滤 */}
      {current === 1 && (
        <Card title="Step 2 · 价格与过滤">
          <Form layout="vertical">
            <Form.Item label="价格区间（双滑块）">
              <PriceRangeSlider
                min={formData.min_price ?? null}
                max={formData.max_price ?? null}
                onChange={(min, max) => setFormData({ ...formData, min_price: min, max_price: max })}
              />
            </Form.Item>

            <Form.Item label="最大发布天数（仅展示最近 N 天的商品）">
              <Slider
                min={1}
                max={30}
                value={formData.max_publish_days || 7}
                onChange={(v) => setFormData({ ...formData, max_publish_days: v })}
                marks={{ 1: '1天', 7: '7天', 14: '14天', 30: '30天' }}
              />
            </Form.Item>

            <Form.Item label="闲鱼筛选标签（点击多选）">
              <Space wrap>
                {searchFilterOptions.map((opt) => {
                  const selected = formData.search_filters?.includes(opt.value)
                  return (
                    <Card
                      key={opt.value}
                      size="small"
                      hoverable
                      onClick={() => {
                        const filters = formData.search_filters || []
                        setFormData({
                          ...formData,
                          search_filters: selected
                            ? filters.filter((f) => f !== opt.value)
                            : [...filters, opt.value],
                        })
                      }}
                      style={{
                        width: 140,
                        cursor: 'pointer',
                        border: selected ? '2px solid #1677ff' : '1px solid #d9d9d9',
                        background: selected ? '#e6f4ff' : '#fff',
                      }}
                    >
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{opt.label}</div>
                      <div style={{ fontSize: 11, color: '#999' }}>{opt.desc}</div>
                    </Card>
                  )
                })}
              </Space>
            </Form.Item>

            <Form.Item label="排除词（标签编辑器）">
              <TagEditor
                value={formData.exclude_words || []}
                onChange={(v) => setFormData({ ...formData, exclude_words: v })}
                placeholder="输入排除词后回车，如：二手、仿品"
                color="red"
              />
            </Form.Item>

            <Form.Item label="地域">
              <Input
                placeholder="例：北京 / 上海 / 广东"
                value={formData.region || ''}
                onChange={(e) => setFormData({ ...formData, region: e.target.value })}
              />
            </Form.Item>
          </Form>
        </Card>
      )}

      {/* Step 3: 调度与确认 */}
      {current === 2 && (
        <Card title="Step 3 · 调度与确认">
          <Form layout="vertical">
            <Form.Item label="Cron 表达式（可视化编辑器）">
              <CronEditor value={cron} onChange={setCron} />
            </Form.Item>

            {/* 配置预览 */}
            <Card size="small" style={{ background: '#fafafa', marginTop: 16 }} title="📋 配置预览">
              <pre style={{ fontSize: 12, margin: 0 }}>
{JSON.stringify(
  {
    keyword: formData.keyword,
    name: formData.name || formData.keyword,
    min_price: formData.min_price,
    max_price: formData.max_price,
    max_publish_days: formData.max_publish_days,
    mode: formData.mode,
    region: formData.region,
    exclude_words: formData.exclude_words,
    search_filters: formData.search_filters,
    cron,
  },
  null,
  2,
)}
              </pre>
            </Card>

            <Result
              icon={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              title="配置确认"
              subTitle="请检查以上配置，确认无误后提交"
              style={{ marginTop: 16 }}
            />
          </Form>
        </Card>
      )}

      {/* 步骤导航 */}
      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
        <Button
          disabled={current === 0}
          onClick={() => setCurrent(current - 1)}
          icon={<ArrowLeftOutlined />}
        >
          上一步
        </Button>
        <Space>
          {current < steps.length - 1 ? (
            <Button type="primary" onClick={handleNext} icon={<ArrowRightOutlined />}>
              下一步
            </Button>
          ) : (
            <Button type="primary" loading={loading} onClick={handleSubmit} icon={<CheckCircleOutlined />}>
              {isEdit ? '保存修改' : '创建任务'}
            </Button>
          )}
        </Space>
      </div>
    </div>
  )
}

// ============== 价格区间双滑块组件 ==============
function PriceRangeSlider({
  min,
  max,
  onChange,
}: {
  min: number | null
  max: number | null
  onChange: (min: number | null, max: number | null) => void
}) {
  const range: [number, number] = [min ?? 0, max ?? 100000]
  return (
    <div>
      <Slider
        range
        min={0}
        max={100000}
        step={100}
        value={range}
        onChange={(v) => onChange(v[0] === 0 ? null : v[0], v[1] === 100000 ? null : v[1])}
        marks={{
          0: '¥0',
          10000: '¥1万',
          50000: '¥5万',
          100000: '¥10万',
        }}
        tooltip={{ formatter: (v) => `¥${v}` }}
      />
      <Space>
        <InputNumber
          prefix="¥"
          placeholder="最低价"
          value={min}
          onChange={(v) => onChange(v, max)}
          style={{ width: 120 }}
        />
        <span>~</span>
        <InputNumber
          prefix="¥"
          placeholder="最高价"
          value={max}
          onChange={(v) => onChange(min, v)}
          style={{ width: 120 }}
        />
      </Space>
    </div>
  )
}
