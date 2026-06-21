import { useEffect, useState } from 'react'
import {
  Card,
  Form,
  InputNumber,
  Select,
  Input,
  Button,
  Space,
  message,
  Row,
  Col,
  Divider,
  Typography,
} from 'antd'
import { SaveOutlined, UndoOutlined, SearchOutlined } from '@ant-design/icons'
import { useConfigStore } from '../../stores/configStore'
import TagEditor from '../../components/editors/TagEditor'

const { Text } = Typography

// 搜索配置字段（对应后端 SearchConfig 模型）
interface SearchConfigFields {
  page_size: number
  sort_type: string
  timeout: number
  regions: string
  filter_tags: string[]
}

// 排序方式选项（闲鱼搜索支持）
const SORT_OPTIONS = [
  { label: '默认综合', value: 'default' },
  { label: '最新发布', value: 'newest' },
  { label: '价格最低', value: 'price_asc' },
  { label: '价格最高', value: 'price_desc' },
  { label: '想要最多', value: 'want_count' },
]

// 每页结果数量选项
const PAGE_SIZE_OPTIONS = [
  { label: '20 条/页', value: 20 },
  { label: '40 条/页', value: 40 },
  { label: '60 条/页', value: 60 },
  { label: '100 条/页', value: 100 },
]

/**
 * 搜索参数配置页面
 * 控制闲鱼搜索行为：间隔、排序、过滤、超时、重试等
 */
export default function SearchConfig() {
  const { config, load, save, hasChanges, reset, update } = useConfigStore()
  const [loading, setLoading] = useState(false)

  // 本地状态：搜索配置字段（部分来自 antidetect，部分为搜索专用）
  const [searchInterval, setSearchInterval] = useState(3) // 搜索间隔（秒）
  const [pageSize, setPageSize] = useState(20) // 每页结果数
  const [sortType, setSortType] = useState('default') // 排序方式
  const [regions, setRegions] = useState('') // 地区过滤（逗号分隔）
  const [filterTags, setFilterTags] = useState<string[]>([]) // 筛选标签
  const [timeout, setTimeout] = useState(30) // 超时时间（秒）
  const [retryCount, setRetryCount] = useState(3) // 失败重试次数

  useEffect(() => {
    load()
  }, [load])

  // 从已加载的配置中初始化本地状态
  useEffect(() => {
    if (config) {
      // 将 antidetect 的毫秒延迟转换为秒（用户更直观）
      const delaySec = Math.round((config.antidetect.min_delay_ms || 3000) / 1000)
      setSearchInterval(delaySec)
      // 重试次数从 fail_pause_threshold 推断（或使用默认值）
      setRetryCount(config.antidetect.fail_pause_threshold || 3)
      // 从 search 配置块加载搜索专用参数
      const sc = (config as { search?: SearchConfigFields }).search
      if (sc) {
        setPageSize(sc.page_size ?? 20)
        setSortType(sc.sort_type ?? 'default')
        setTimeout(sc.timeout ?? 30)
        setRegions(sc.regions ?? '')
        setFilterTags(sc.filter_tags ?? [])
      }
    }
  }, [config])

  if (!config) {
    return <div className="page-container">加载中...</div>
  }

  // 保存配置：将搜索参数写回 AppConfig 的对应字段
  const handleSave = async () => {
    try {
      setLoading(true)
      // 构建更新 payload：
      // 1. antidetect: 搜索间隔和重试次数（通用反检测参数）
      // 2. search: 搜索专用参数（page_size/sort_type/timeout/regions/filter_tags）
      update({
        antidetect: {
          ...config.antidetect,
          min_delay_ms: searchInterval * 1000,
          max_delay_ms: searchInterval * 1500, // 最大延迟 = 1.5x 最小延迟
          qps: Math.round(60 / searchInterval), // 根据 QPS 反推
          fail_pause_threshold: retryCount,
        },
        search: {
          page_size: pageSize,
          sort_type: sortType,
          timeout: timeout,
          regions: regions,
          filter_tags: filterTags,
        } as SearchConfigFields,
      })
      // 等待 store 更新
      await save()
      message.success('搜索参数配置已保存')
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-container">
      {/* 页面标题 + 操作按钮 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0, color: '#FF6200' }}>
          <SearchOutlined style={{ marginRight: 8 }} />
          搜索参数配置
        </h2>
        <Space>
          <Button icon={<UndoOutlined />} onClick={reset} disabled={!hasChanges()}>
            重置
          </Button>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={loading}>
            保存配置
          </Button>
        </Space>
      </div>

      <Row gutter={24}>
        {/* 左列：基础搜索参数 */}
        <Col span={12}>
          <Card title="🔍 基础搜索参数" style={{ marginBottom: 16 }}>
            {/* 搜索间隔 */}
            <Form.Item label="搜索间隔" extra="两次搜索之间的等待时间，避免被风控（建议 ≥2 秒）">
              <InputNumber
                min={1}
                max={30}
                step={1}
                value={searchInterval}
                onChange={(v) => setSearchInterval(v || 3)}
                addonAfter="秒"
                style={{ width: '100%' }}
              />
            </Form.Item>

            {/* 每页结果数量 */}
            <Form.Item label="每页结果数量" extra="单次请求返回的商品条目数">
              <Select
                value={pageSize}
                onChange={setPageSize}
                options={PAGE_SIZE_OPTIONS}
                style={{ width: '100%' }}
              />
            </Form.Item>

            {/* 排序方式 */}
            <Form.Item label="排序方式" extra="搜索结果的默认排序规则">
              <Select
                value={sortType}
                onChange={setSortType}
                options={SORT_OPTIONS}
                style={{ width: '100%' }}
              />
            </Form.Item>

            {/* 搜索超时 */}
            <Form.Item label="搜索超时" extra="单次搜索请求的最大等待时间">
              <InputNumber
                min={10}
                max={120}
                step={5}
                value={timeout}
                onChange={(v) => setTimeout(v || 30)}
                addonAfter="秒"
                style={{ width: '100%' }}
              />
            </Form.Item>
          </Card>

          {/* 容错与重试 */}
          <Card title="⚙️ 容错与重试">
            {/* 失败重试次数 */}
            <Form.Item
              label="失败重试次数"
              extra={`连续失败 ${retryCount} 次后将暂停任务（防触发风控）`}
            >
              <InputNumber
                min={0}
                max={10}
                step={1}
                value={retryCount}
                onChange={(v) => setRetryCount(v || 0)}
                style={{ width: '100%' }}
              />
            </Form.Item>

            {/* 当前 QPS 提示（只读） */}
            <Form.Item label="等效 QPS" extra="根据搜索间隔自动计算的理论值">
              <Text code>{Math.round(60 / searchInterval)} 次/分钟</Text>
            </Form.Item>
          </Card>
        </Col>

        {/* 右列：过滤与标签 */}
        <Col span={12}>
          <Card title="📍 地区与过滤" style={{ marginBottom: 16 }}>
            {/* 地区过滤 */}
            <Form.Item
              label="地区过滤"
              extra='限制搜索结果的发货地区，多个地区用英文逗号分隔（如 "北京,上海,广州"）'
            >
              <Input
                value={regions}
                onChange={(e) => setRegions(e.target.value)}
                placeholder="例：北京,上海,广州"
                allowClear
              />
            </Form.Item>

            <Divider plain>筛选标签</Divider>

            {/* 筛选标签 - TagEditor 组件 */}
            <Form.Item
              label="筛选标签"
              extra="仅显示带有以下标签的商品（如包邮、信用极好等同款筛选条件）"
            >
              <TagEditor
                value={filterTags}
                onChange={setFilterTags}
                placeholder="输入筛选标签后回车"
                color="orange"
              />
            </Form.Item>

            {/* 预设快捷标签 */}
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>常用预设：</Text>
              <Space size={[4, 8]} wrap style={{ marginLeft: 8 }}>
                {['包邮', '信用极好', '同款', '全新', '可小刀'].map((tag) => (
                  <Button
                    key={tag}
                    size="small"
                    type={filterTags.includes(tag) ? 'primary' : 'default'}
                    onClick={() => {
                      if (filterTags.includes(tag)) {
                        setFilterTags(filterTags.filter((t) => t !== tag))
                      } else {
                        setFilterTags([...filterTags, tag])
                      }
                    }}
                    style={{
                      fontSize: 12,
                      borderColor: filterTags.includes(tag) ? '#FF6200' : undefined,
                      color: filterTags.includes(tag) ? '#FF6200' : undefined,
                    }}
                  >
                    {tag}
                  </Button>
                ))}
              </Space>
            </div>
          </Card>

          {/* 配置摘要 */}
          <Card title="📋 当前配置摘要">
            <div style={{ fontSize: 13, lineHeight: 2 }}>
              <div>
                <Text strong>搜索间隔：</Text>
                <Text>{searchInterval}s（最大 {Math.round(searchInterval * 1.5)}s）</Text>
              </div>
              <div>
                <Text strong>每页数量：</Text>
                <Text>{pageSize} 条</Text>
              </div>
              <div>
                <Text strong>排序方式：</Text>
                <Text>{SORT_OPTIONS.find((o) => o.value === sortType)?.label}</Text>
              </div>
              <div>
                <Text strong>超时设置：</Text>
                <Text>{timeout}s</Text>
              </div>
              <div>
                <Text strong>重试策略：</Text>
                <Text>失败 {retryCount} 次后暂停</Text>
              </div>
              <div>
                <Text strong>地区过滤：</Text>
                <Text>{regions || '未设置（全国）'}</Text>
              </div>
              <div>
                <Text strong>筛选标签：</Text>
                <Text>{filterTags.length > 0 ? filterTags.join('、') : '未设置'}</Text>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
