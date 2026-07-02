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
  Modal,
  Table,
  Tag,
  Switch,
  Alert,
} from 'antd'
import { SaveOutlined, UndoOutlined, SearchOutlined } from '@ant-design/icons'
import { useConfigStore } from '../../stores/configStore'
import { extractApiError } from '../../utils/apiError'
import type { DiffChange } from '../../stores/configStore'
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
  const { config, load, hasChanges, reset, update, previewSave, confirmSave } = useConfigStore()
  // Diff 预览
  const [diffModalOpen, setDiffModalOpen] = useState(false)
  const [diffChanges, setDiffChanges] = useState<DiffChange[]>([])
  const [saving, setSaving] = useState(false)

  // 本地状态：搜索配置字段（部分来自 antidetect，部分为搜索专用）
  const [searchInterval, setSearchInterval] = useState(3) // 搜索间隔（秒）
  const [pageSize, setPageSize] = useState(20) // 每页结果数
  const [sortType, setSortType] = useState('default') // 排序方式
  const [regions, setRegions] = useState('') // 地区过滤（逗号分隔）
  const [filterTags, setFilterTags] = useState<string[]>([]) // 筛选标签
  const [timeout, setTimeout] = useState(30) // 超时时间（秒）
  const [retryCount, setRetryCount] = useState(3) // 失败重试次数
  // 任务调度默认值（对应后端 TaskSchedulerConfig）
  const [defaultInterval, setDefaultInterval] = useState(60) // 新建任务默认采集周期（秒）
  const [autoSearchDefault, setAutoSearchDefault] = useState(false) // 任务列表自动搜索初始默认开关

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
      // 任务调度默认值初始化
      const ts = config.task_scheduler
      if (ts) {
        setDefaultInterval(ts.default_interval_seconds ?? 60)
        setAutoSearchDefault(ts.auto_search_enabled ?? false)
      }
    }
  }, [config])

  if (!config) {
    return <div className="page-container">加载中...</div>
  }

  // 保存配置：将搜索参数写回 AppConfig 的对应字段
  const handleSave = async () => {
    try {
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
        task_scheduler: {
          default_interval_seconds: defaultInterval,
          auto_search_enabled: autoSearchDefault,
          // 保留原有并发上限，本页面不暴露编辑入口（当前固定 1）
          auto_search_concurrency: config.task_scheduler?.auto_search_concurrency ?? 1,
        },
      })
      setSaving(true)
      const changes = await previewSave()
      if (changes.length === 0) {
        message.info('配置未变更')
        return
      }
      setDiffChanges(changes)
      setDiffModalOpen(true)
    } catch {
      message.error('预览失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  const handleConfirmSave = async () => {
    try {
      setSaving(true)
      await confirmSave()
      setDiffModalOpen(false)
      message.success('搜索参数配置已保存')
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
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
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
            保存配置
          </Button>
        </Space>
      </div>

      <Row gutter={24}>
        {/* 左列：基础搜索参数 */}
        <Col span={12}>
          <Card title="🔍 基础搜索参数" style={{ marginBottom: 16 }}>
            {/* 操作延迟（原"搜索间隔"，实际是单次操作间的人类行为模拟延迟，非任务循环间隔） */}
            <Form.Item label="操作延迟" extra="模拟人类操作的间隔时间（非任务循环间隔），避免被风控（建议 ≥2 秒）">
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
          <Card title="⚙️ 容错与重试" style={{ marginBottom: 16 }}>
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

          {/* 任务调度默认值：新建任务未指定时的兜底配置 */}
          <Card title="⏱ 任务调度默认值">
            <Alert
              type="info"
              showIcon
              message="新建任务未指定采集周期时使用此默认值"
              description="已存在的任务不受此配置影响，需在任务编辑器中单独修改。"
              style={{ marginBottom: 16 }}
            />
            <Form.Item
              label="默认采集周期"
              help="范围 30-3600 秒，过短易触发反爬，过长错过抢单窗口"
            >
              <InputNumber
                min={30}
                max={3600}
                step={10}
                value={defaultInterval}
                onChange={(v) => setDefaultInterval(v ?? 60)}
                addonAfter="秒"
                style={{ width: '100%' }}
              />
            </Form.Item>
            <Form.Item
              label="任务列表自动搜索默认开关"
              help="开启后，用户首次访问任务管理页时自动启用倒计时搜索（用户可在页面内手动关闭）"
            >
              <Switch
                checked={autoSearchDefault}
                onChange={setAutoSearchDefault}
                checkedChildren="开"
                unCheckedChildren="关"
              />
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
                      // 选中时由 type="primary" 提供橙底白字；未选中时用橙色描边+文字做主题暗示
                      borderColor: filterTags.includes(tag) ? undefined : '#FF6200',
                      color: filterTags.includes(tag) ? undefined : '#FF6200',
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
                <Text strong>操作延迟：</Text>
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

      {/* Diff 预览 Modal */}
      <Modal
        title="配置变更预览"
        open={diffModalOpen}
        onCancel={() => setDiffModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setDiffModalOpen(false)}>
            取消
          </Button>,
          <Button key="confirm" type="primary" loading={saving} onClick={handleConfirmSave}>
            确认保存
          </Button>,
        ]}
        width={700}
      >
        <Table
          dataSource={diffChanges}
          rowKey="path"
          pagination={false}
          size="small"
          columns={[
            { title: '路径', dataIndex: 'path', key: 'path' },
            { title: '原值', dataIndex: 'old_value', key: 'old_value', render: (v) => v == null ? '-' : String(v) },
            { title: '新值', dataIndex: 'new_value', key: 'new_value', render: (v) => v == null ? '-' : String(v) },
            {
              title: '操作',
              dataIndex: 'op',
              key: 'op',
              render: (op: string) => {
                // op → 颜色/文案映射，未知 op 走 default 分支
                const opColorMap: Record<string, string> = { add: 'green', delete: 'red' }
                const opLabelMap: Record<string, string> = { add: '新增', delete: '删除' }
                return (
                  <Tag color={opColorMap[op] ?? 'orange'}>
                    {opLabelMap[op] ?? '修改'}
                  </Tag>
                )
              },
            },
          ]}
        />
      </Modal>
    </div>
  )
}
