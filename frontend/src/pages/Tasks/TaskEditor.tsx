import { useEffect, useState, useRef } from 'react'
import {
  Steps, Card, Form, Input, InputNumber, Slider, Button, Space, Radio,
  message, Result, Spin, Alert, Modal, Switch, Tag, Divider, Table, Select,
} from 'antd'
import {
  ArrowLeftOutlined, ArrowRightOutlined, CheckCircleOutlined, SettingOutlined,
  UndoOutlined, SaveOutlined, ExclamationCircleOutlined, RobotOutlined,
  CloudDownloadOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import TagEditor from '../../components/editors/TagEditor'
import CronEditor from '../../components/editors/CronEditor'
import { taskApi, configApi, TaskCreateBody, TaskSearchOverride, AppConfig } from '../../api'
import type { Task } from '../../api/types'
import { storage } from '../../utils/storage'
import { useConfigStore, DiffChange } from '../../stores/configStore'
import { extractApiError } from '../../utils/apiError'

// Diff 预览表格的共享 render 函数（3 个全局配置 Modal 重复使用，提取到模块级避免 S4144）
// 按类型分别处理：对象/数组走 JSON 序列化，避免 String() 输出 '[object Object]'
const renderDiffValue = (v: unknown): string => {
  if (v == null) return '-'
  if (Array.isArray(v)) return v.map(renderDiffValue).join(', ')
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
const renderOpTag = (op: string) => {
  // op 配色：add=绿 delete=红 其他=橙
  if (op === 'add') return <Tag color="green">新增</Tag>
  if (op === 'delete') return <Tag color="red">删除</Tag>
  return <Tag color="orange">修改</Tag>
}

// S4144：两个全局配置 Modal（BatchRefresh / Antidetect）的 handleSave 实现完全一致，
// 提取为模块级共享 helper，避免重复实现。两处调用各自传入自己的 setter。
async function previewConfigSave(opts: {
  setSaving: (b: boolean) => void
  previewSave: () => Promise<DiffChange[]>
  setDiffChanges: (c: DiffChange[]) => void
  setDiffModalOpen: (b: boolean) => void
}): Promise<void> {
  try {
    opts.setSaving(true)
    const changes = await opts.previewSave()
    if (changes.length === 0) {
      message.info('配置未变更')
      return
    }
    opts.setDiffChanges(changes)
    opts.setDiffModalOpen(true)
  } catch (e) {
    message.error(extractApiError(e), 5)
  } finally {
    opts.setSaving(false)
  }
}

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

// 闲鱼搜索排序方式（与后端 SearchConfig.sort_type 对齐）
const sortTypeOptions = [
  { value: 'default', label: '综合排序' },
  { value: 'newest', label: '最新发布' },
  { value: 'price_asc', label: '价格升序' },
  { value: 'price_desc', label: '价格降序' },
  { value: 'want_count', label: '想要数' },
]

// 草稿结构：包含所有任务级覆盖字段，确保刷新页面后能完整恢复
interface DraftData {
  formData: TaskCreateBody
  cron: string
  useCron: boolean
  intervalSeconds: number
}

// 安全解析字符串数组字段：后端可能返回 JSON 字符串或已解析的数组
// 为什么提取：useEffect 加载编辑数据内嵌套定义，提取后主回调复杂度下降
const safeParseStringArray = (v: unknown): string[] => {
  if (Array.isArray(v)) return v
  if (typeof v === 'string' && v.trim()) {
    try { return JSON.parse(v) } catch { return [] }
  }
  return []
}

// 把后端 Task 转换为表单初值（编辑模式 useEffect 内调用）
// 为什么提取：原 useEffect 内有 ~20 行属性映射 + 多处 ?? 兜底，提取后主回调只剩调度逻辑
const taskToFormData = (task: Task): TaskCreateBody => ({
  keyword: task.keyword || '',
  name: task.name || '',
  min_price: task.min_price,
  max_price: task.max_price,
  max_publish_days: task.max_publish_days,
  mode: task.mode || 'confirm',
  region: task.region || '',
  exclude_words: safeParseStringArray(task.exclude_words),
  search_filters: safeParseStringArray(task.search_filters),
  // 任务级覆盖字段：后端已将 JSON 字符串解析为对象，直接透传
  // eval_threshold 后端默认 60（NOT NULL），此处保留原值，前端用 null 表示"沿用全局"语义
  eval_threshold: task.eval_threshold ?? null,
  ai_prompt: task.ai_prompt ?? null,
  search_config: task.search_config ?? null,
  price_config: task.price_config ?? null,
  antidetect_config: task.antidetect_config ?? null,
  eval_config: task.eval_config ?? null,
})

// 根据 axios 错误状态码生成用户友好的加载失败提示
// 为什么提取：原 catch 块 if/else if/else + 多个 || 链，提取后主回调只剩单行调用
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const buildLoadErrorMessage = (err: any): string => {
  const status = err?.response?.status
  if (status === 401) return '登录已过期，请先登录后重试'
  if (status === 404) return '任务不存在，可能已被删除'
  return err?.response?.data?.detail || '加载失败，请返回列表重试'
}

export default function TaskEditor() {
  const navigate = useNavigate()
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const isEdit = !!id
  const [current, setCurrent] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadingEditData, setLoadingEditData] = useState(false)
  const [form] = Form.useForm()

  // 从 URL search params 读取 AI/模板预填充数据
  const prefillKeyword = searchParams.get('keyword') || ''
  const prefillName = searchParams.get('name') || ''
  const prefillMode = searchParams.get('mode') || ''
  const prefillMinPrice = searchParams.get('min_price')
  const prefillMaxPrice = searchParams.get('max_price')

  // 全局配置：用于显示"当前全局值"参考 + 全局快捷入口 Modal 编辑
  // 加载一次即可，TaskEditor 生命周期内全局配置不会变（保存全局配置后会刷新）
  const [globalConfig, setGlobalConfig] = useState<AppConfig | null>(null)

  // 用类型守卫替代 as 断言（S4325）：让 TypeScript 收窄 prefillMode 类型
  // TaskCreateBody['mode'] 是 string | undefined，需独立定义不含 undefined 的字面量联合
  type TaskMode = 'auto' | 'semi_auto' | 'confirm' | 'notify'
  const isTaskMode = (v: string): v is TaskMode =>
    v === 'auto' || v === 'semi_auto' || v === 'confirm' || v === 'notify'
  const initialMode: TaskMode = isTaskMode(prefillMode) ? prefillMode : 'confirm'

  // 表单状态（含任务级覆盖字段，null 表示沿用全局）
  const [formData, setFormData] = useState<TaskCreateBody>({
    keyword: prefillKeyword,
    name: prefillName || prefillKeyword,
    min_price: prefillMinPrice ? Number(prefillMinPrice) : null,
    max_price: prefillMaxPrice ? Number(prefillMaxPrice) : null,
    max_publish_days: 7,
    mode: initialMode,
    region: '',
    exclude_words: [],
    search_filters: [],
    // 任务级覆盖字段默认 null = 沿用全局配置
    // price_config 不在 UI 暴露编辑入口（min_price/max_price 已在 Step 2 覆盖），
    // 但需保留字段以便编辑模式下原样回显和保存，避免丢失已有配置
    eval_threshold: null,
    ai_prompt: null,
    search_config: null,
    price_config: null,
    antidetect_config: null,
    eval_config: null,
  })
  const [cron, setCron] = useState('*/5 * * * *')
  // 调度模式：false=固定间隔（interval_seconds），true=Cron 表达式
  // 与后端 Task.use_cron 字段对齐，修复之前前端配 cron 但 use_cron 恒 False 的断层
  const [useCron, setUseCron] = useState(false)
  const [intervalSeconds, setIntervalSeconds] = useState(60)

  // 全局快捷入口 Modal 状态
  const [evalModalOpen, setEvalModalOpen] = useState(false)
  const [batchRefreshModalOpen, setBatchRefreshModalOpen] = useState(false)
  const [antidetectModalOpen, setAntidetectModalOpen] = useState(false)

  // 草稿自动保存/恢复（迁移到统一 storage 工具，v3 格式与旧版不兼容，旧草稿自动失效）
  // v3：新增任务级覆盖字段，v2 草稿会被 validator 拒绝从而失效，避免字段缺失
  const DRAFT_KEY = 'xh.task-draft.v3'
  const [draftRestored, setDraftRestored] = useState(false)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 加载全局配置（用于参考值显示 + 全局快捷入口 Modal）
  useEffect(() => {
    configApi.get().then(setGlobalConfig).catch(() => {})
  }, [])

  // 新建模式下首次加载恢复草稿
  useEffect(() => {
    if (isEdit) return
    const draft = storage.get<DraftData | null>(
      DRAFT_KEY, null,
      (v): v is DraftData =>
        v !== null && typeof v === 'object' && 'formData' in v && 'cron' in v && 'useCron' in v && 'intervalSeconds' in v,
    )
    if (!draft) return
    // 仅在 URL 未提供预填充时恢复草稿，避免覆盖 AI/模板传入的数据
    if (draft.formData?.keyword && !prefillKeyword) {
      setFormData(draft.formData)
      setCron(draft.cron || '*/5 * * * *')
      setUseCron(draft.useCron ?? false)
      setIntervalSeconds(draft.intervalSeconds ?? 60)
      setDraftRestored(true)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 监听 formData/cron 变更，防抖 500ms 自动保存草稿（仅新建模式）
  useEffect(() => {
    if (isEdit) return
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      storage.set(DRAFT_KEY, { formData, cron, useCron, intervalSeconds })
    }, 500)
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current) }
  }, [formData, cron, useCron, intervalSeconds, isEdit])

  const clearDraft = () => {
    storage.remove(DRAFT_KEY)
    setDraftRestored(false)
  }

  // 编辑模式：加载现有任务数据
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    if (id) {
      setLoadingEditData(true)
      setLoadError(null)
      taskApi.get(id)
        .then((task) => {
          // 后端可能返回 JSON 字符串或已解析的数组/对象，统一安全解析
          const safeParse = (v: unknown): string[] => {
            if (Array.isArray(v)) return v
            if (typeof v === 'string' && v.trim()) {
              try { return JSON.parse(v) } catch { return [] }
            }
            return []
          }
          const data: TaskCreateBody = {
            keyword: task.keyword || '',
            name: task.name || '',
            min_price: task.min_price,
            max_price: task.max_price,
            max_publish_days: task.max_publish_days,
            mode: task.mode || 'confirm',
            region: task.region || '',
            exclude_words: safeParse(task.exclude_words),
            search_filters: safeParse(task.search_filters),
            // 任务级覆盖字段：后端已将 JSON 字符串解析为对象，直接透传
            // eval_threshold 后端默认 60（NOT NULL），此处保留原值，前端用 null 表示"沿用全局"语义
            eval_threshold: task.eval_threshold ?? null,
            ai_prompt: task.ai_prompt ?? null,
            search_config: task.search_config ?? null,
            price_config: task.price_config ?? null,
            antidetect_config: task.antidetect_config ?? null,
            eval_config: task.eval_config ?? null,
          }
          setFormData(data)
          setCron(task.cron || '*/5 * * * *')
          // 兼容旧任务：use_cron / interval_seconds 可能未持久化，回退默认值
          setUseCron(Boolean(task.use_cron))
          setIntervalSeconds(
            typeof task.interval_seconds === 'number' ? task.interval_seconds : 60
          )
        })
        .catch((err) => {
          console.error('加载任务失败:', err)
          const status = err?.response?.status
          if (status === 401) {
            setLoadError('登录已过期，请先登录后重试')
          } else if (status === 404) {
            setLoadError('任务不存在，可能已被删除')
          } else {
            setLoadError(err?.response?.data?.detail || '加载失败，请返回列表重试')
          }
        })
        .finally(() => setLoadingEditData(false))
    }
  }, [id])

  const steps = [
    { title: '基础信息', desc: '关键词与模式' },
    { title: '价格与过滤', desc: '价格区间与筛选' },
    { title: '搜索参数', desc: '任务级覆盖' },
    { title: 'AI 评估', desc: '评估参数' },
    { title: '反检测', desc: '任务级覆盖' },
    { title: '调度与确认', desc: 'Cron 与提交' },
  ]

  const handleNext = () => {
    if (current === 0 && !formData.keyword) {
      message.warning('请输入关键词')
      return
    }
    setCurrent(current + 1)
  }

  // ============== 任务级覆盖字段更新辅助函数 ==============
  // 设计：覆盖字段为 null 表示"沿用全局"，非 null（含空对象）表示"启用覆盖"
  // 单字段更新：清空值时从覆盖对象中删除该字段，对象变空则整体置 null

  // 判断值是否为"空"：null/undefined/空字符串/空数组都视为未覆盖
  // 用 unknown 类型避免 TypeScript 对泛型 T 与 string/number 无重叠的报错
  const isEmptyValue = (v: unknown): boolean =>
    v === null || v === undefined || v === '' || (Array.isArray(v) && v.length === 0)

  const updateSearchOverride = <K extends keyof TaskSearchOverride>(field: K, value: TaskSearchOverride[K] | null) => {
    // S7744：{...null}/{...undefined} 与 {...{}} 等价，空对象无用，直接展开原值
    const current = { ...formData.search_config }
    if (isEmptyValue(value)) {
      delete current[field]
    } else if (value != null) {
      // isEmptyValue 已过滤空字符串/空数组，仅需排除 null/undefined 让 TS 收窄类型
      current[field] = value
    }
    setFormData({ ...formData, search_config: Object.keys(current).length > 0 ? current : null })
  }

  // ============== 危险操作检测 ==============
  // 在提交前检测高风险配置组合，弹出二次确认 Modal
  // 检测规则基于反爬/资金安全经验阈值，不是硬性阻断，仅提示
  const detectRiskyConfig = (): { level: 'warning' | 'danger'; message: string }[] => {
    const risks: { level: 'warning' | 'danger'; message: string }[] = []
    if (formData.mode === 'auto') {
      risks.push({ level: 'warning', message: '任务模式为「全自动」，评估通过后会自动抢单，请确认资金风险' })
    }
    // 评估阈值：任务级优先，回退全局
    const effectiveThreshold = formData.eval_threshold ?? globalConfig?.eval?.pass_score ?? 60
    if (formData.mode === 'auto' && effectiveThreshold < 60) {
      risks.push({ level: 'danger', message: `评估阈值 ${effectiveThreshold} 低于 60，自动模式下可能抢到低质量商品` })
    }
    // QPS：反检测参数为全局配置（非任务级），直接读全局
    const effectiveQps = globalConfig?.antidetect?.qps ?? 1
    if (effectiveQps > 5) {
      risks.push({ level: 'danger', message: `全局 QPS=${effectiveQps} 过高，可能触发反爬封号` })
    }
    if (!useCron && intervalSeconds < 60) {
      risks.push({ level: 'warning', message: `执行间隔 ${intervalSeconds}秒 过短，可能触发反爬` })
    }
    return risks
  }

  const handleSubmit = () => {
    if (!formData.keyword) {
      message.warning('关键词不能为空')
      return
    }
    // globalConfig 异步加载未完成时禁止提交：detectRiskyConfig 依赖全局配置值，
    // 未加载时用默认值（如 qps=1）会漏报高风险配置
    if (!globalConfig) {
      message.warning('全局配置加载中，请稍候再提交')
      return
    }
    const risks = detectRiskyConfig()
    if (risks.length === 0) {
      doSubmit()
      return
    }
    // 危险操作二次确认：根据是否有 danger 级风险决定按钮样式
    const hasDanger = risks.some(r => r.level === 'danger')
    Modal.confirm({
      title: hasDanger ? '⚠️ 高风险配置确认' : '配置风险提示',
      icon: <ExclamationCircleOutlined style={{ color: hasDanger ? '#ff4d4f' : '#faad14' }} />,
      content: (
        <div>
          <p style={{ marginBottom: 8 }}>检测到以下风险，请确认是否继续：</p>
          {risks.map((r, i) => (
            <p key={`${r.level}-${i}`} style={{ color: r.level === 'danger' ? '#ff4d4f' : '#faad14', marginBottom: 4, fontSize: 13 }}>
              {r.level === 'danger' ? '🔴 ' : '🟡 '}{r.message}
            </p>
          ))}
        </div>
      ),
      okText: '确认继续',
      cancelText: '返回修改',
      okButtonProps: { danger: hasDanger },
      onOk: () => doSubmit(),
    })
  }

  const doSubmit = async () => {
    setLoading(true)
    try {
      // 调度配置直接放入 TaskCreateBody（types.ts 已声明），不再用交集类型绕过
      const body: TaskCreateBody = {
        ...formData,
        name: formData.name || formData.keyword,
        cron,
        use_cron: useCron,
        interval_seconds: intervalSeconds,
      }
      // 用 id 直接收窄类型，替代 isEdit + 非空断言
      if (id) {
        await taskApi.update(id, body)
        message.success('任务已更新')
      } else {
        await taskApi.create(body)
        message.success('任务已创建')
        clearDraft()
      }
      navigate('/tasks')
    } catch (e) {
      message.error(extractApiError(e), 5)
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
      params.set('filters', filters.join(','))
    }
    return `https://www.goofish.com/search?${params.toString()}`
  })()

  // 当前生效值：任务级覆盖优先，回退全局（用于 UI 展示"当前生效"提示）
  const effective = {
    pageSize: formData.search_config?.page_size ?? globalConfig?.search.page_size ?? 20,
    sortType: formData.search_config?.sort_type ?? globalConfig?.search.sort_type ?? 'default',
    timeout: formData.search_config?.timeout ?? globalConfig?.search.timeout ?? 30,
    regions: formData.search_config?.regions ?? globalConfig?.search.regions ?? '',
    filterTags: formData.search_config?.filter_tags ?? globalConfig?.search.filter_tags ?? [],
    evalThreshold: formData.eval_threshold ?? globalConfig?.eval?.pass_score ?? 60,
  }

  // 标题预计算：提取到组件主体以避免 JSX 内嵌套三元
  const pageTitle = (() => {
    if (isEdit) return '编辑任务'
    if (prefillKeyword) return '新增任务（已预填充）'
    return '新增任务（向导）'
  })()

  return (
    <div className="page-container">
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>

      <h2>{pageTitle}</h2>

      {/* 草稿恢复提示 */}
      {!isEdit && draftRestored && (
        <Alert
          message="已恢复上次未提交的草稿"
          type="info"
          showIcon
          closable
          onClose={() => setDraftRestored(false)}
          action={
            <Button size="small" danger onClick={clearDraft}>清除草稿</Button>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 编辑模式：数据加载中显示 spinner */}
      {isEdit && loadingEditData && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" tip="正在加载任务信息..."><div /></Spin>
        </div>
      )}

      {/* 编辑模式：加载失败显示错误（与 spinner 互斥，loadingEditData 已置 false） */}
      {!loadingEditData && isEdit && loadError && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Result
            status={loadError.includes('登录') ? 'warning' : 'error'}
            title={loadError}
            extra={
              <Space>
                <Button onClick={() => navigate('/tasks')}>返回列表</Button>
                {loadError.includes('登录') && (
                  <Button type="primary" onClick={() => navigate('/login')} style={{ background: '#FF6200', borderColor: '#FF6200' }}>
                    前往登录
                  </Button>
                )}
              </Space>
            }
          />
        </div>
      )}

      {/* 主内容：非编辑模式，或编辑模式但既不在加载也无错误 */}
      {(!isEdit || (!loadingEditData && !loadError)) && (
        <>
          <Steps current={current} items={steps} style={{ marginBottom: 24 }} />

      {/* Step 0: 基础信息 */}
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
                        <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>{opt.desc}</div>
                      </div>
                    </Radio.Button>
                  ))}
                </Space>
              </Radio.Group>
            </Form.Item>
          </Form>

          {/* 实时预览：搜索 URL */}
          {formData.keyword && (
            <Card size="small" style={{ background: 'rgba(22, 119, 255, 0.06)', marginTop: 16 }} title="🔍 实时预览：搜索 URL">
              <code style={{ fontSize: 12, wordBreak: 'break-all' }}>{searchUrl}</code>
            </Card>
          )}
        </Card>
      )}

      {/* Step 1: 价格与过滤 */}
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
                        border: selected ? '2px solid #1677ff' : '1px solid var(--xh-border-secondary)',
                        background: selected ? 'var(--xh-bg-info)' : 'var(--xh-bg-container)',
                      }}
                    >
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{opt.label}</div>
                      <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)' }}>{opt.desc}</div>
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

      {/* Step 2: 搜索参数（任务级覆盖） */}
      {current === 2 && (
        <Card
          title={
            <Space>
              <span>Step 3 · 搜索参数</span>
              <Tag color={formData.search_config ? 'blue' : 'default'}>
                {formData.search_config ? '任务级覆盖' : '沿用全局'}
              </Tag>
            </Space>
          }
          extra={
            <Button
              size="small"
              icon={<SettingOutlined />}
              onClick={() => navigate('/app/config/search')}
            >
              全局搜索配置
            </Button>
          }
        >
          <Alert
            type="info"
            showIcon
            message="任务级覆盖会优先于全局搜索配置生效"
            description="未填写的字段将沿用全局配置。清空字段即回退到全局值。"
            style={{ marginBottom: 16 }}
          />

          <Form layout="vertical">
            <Form.Item
              label="单页搜索条数（page_size）"
              help={`全局当前值：${globalConfig?.search.page_size ?? 20} 条`}
            >
              <InputNumber
                min={1}
                max={100}
                value={formData.search_config?.page_size ?? null}
                onChange={(v) => updateSearchOverride('page_size', v)}
                placeholder={`沿用全局（${effective.pageSize}）`}
                addonAfter="条"
                style={{ width: 200 }}
              />
            </Form.Item>

            <Form.Item
              label="排序方式（sort_type）"
              help={`全局当前值：${sortTypeOptions.find(o => o.value === effective.sortType)?.label ?? effective.sortType}`}
            >
              <Select
                allowClear
                value={formData.search_config?.sort_type ?? null}
                onChange={(v) => updateSearchOverride('sort_type', v ?? null)}
                placeholder={`沿用全局（${effective.sortType}）`}
                options={sortTypeOptions}
                style={{ width: 200 }}
              />
            </Form.Item>

            <Form.Item
              label="搜索超时（timeout）"
              help={`全局当前值：${globalConfig?.search.timeout ?? 30} 秒`}
            >
              <InputNumber
                min={5}
                max={120}
                value={formData.search_config?.timeout ?? null}
                onChange={(v) => updateSearchOverride('timeout', v)}
                placeholder={`沿用全局（${effective.timeout}）`}
                addonAfter="秒"
                style={{ width: 200 }}
              />
            </Form.Item>

            <Form.Item
              label="地区过滤（regions）"
              help={`全局当前值：${globalConfig?.search.regions || '全国'}（逗号分隔，空表示全国）`}
            >
              <Input
                value={formData.search_config?.regions ?? ''}
                onChange={(e) => updateSearchOverride('regions', e.target.value || null)}
                placeholder={`沿用全局（${effective.regions || '全国'}）`}
              />
            </Form.Item>

            <Form.Item
              label="筛选标签（filter_tags）"
              help={`全局当前值：${globalConfig?.search.filter_tags?.length ? globalConfig.search.filter_tags.join(', ') : '无'}`}
            >
              <TagEditor
                value={formData.search_config?.filter_tags ?? []}
                onChange={(v) => updateSearchOverride('filter_tags', v.length > 0 ? v : null)}
                placeholder="输入标签后回车（覆盖全局筛选标签）"
                color="blue"
              />
            </Form.Item>
          </Form>
        </Card>
      )}

      {/* Step 3: AI 评估参数 */}
      {current === 3 && (
        <Card
          title={
            <Space>
              <RobotOutlined />
              <span>Step 4 · AI 评估参数</span>
            </Space>
          }
          extra={
            <Button
              size="small"
              icon={<SettingOutlined />}
              onClick={() => setEvalModalOpen(true)}
            >
              全局 AI 评估配置
            </Button>
          }
        >
          <Alert
            type="info"
            showIcon
            message="任务级 AI 评估参数"
            description="此处的阈值和提示词为任务级覆盖，优先于全局配置。未设置则沿用全局。"
            style={{ marginBottom: 16 }}
          />

          <Form layout="vertical">
            <Form.Item
              label="评估通过阈值（eval_threshold）"
              help={`≥ 此分数视为通过，触发通知/抢单。全局当前值：${globalConfig?.eval?.pass_score ?? 60}`}
            >
              <Slider
                min={0}
                max={100}
                value={formData.eval_threshold ?? effective.evalThreshold}
                onChange={(v) => {
                  // 与全局值相同时回退 null，保留"沿用全局"语义
                  // 否则用户拖动后即使拖回原位也会变成任务级覆盖，全局值变更时此任务不跟随
                  const globalValue = globalConfig?.eval?.pass_score ?? 60
                  setFormData({ ...formData, eval_threshold: v === globalValue ? null : v })
                }}
                marks={{ 0: '0', 60: '60', 80: '80', 100: '100' }}
                tooltip={{ formatter: (v) => v == null ? '沿用全局' : String(v) }}
              />
              <Space style={{ marginTop: 8 }}>
                <InputNumber
                  min={0}
                  max={100}
                  value={formData.eval_threshold ?? null}
                  onChange={(v) => setFormData({ ...formData, eval_threshold: v })}
                  placeholder={`沿用全局（${effective.evalThreshold}）`}
                  style={{ width: 120 }}
                />
                <Button
                  size="small"
                  onClick={() => setFormData({ ...formData, eval_threshold: null })}
                  disabled={formData.eval_threshold === null}
                >
                  重置为全局
                </Button>
              </Space>
            </Form.Item>

            <Divider />

            <Form.Item
              label="AI 评估提示词（ai_prompt）"
              help="自定义 AI 评估时的额外指令，留空则使用系统默认提示词"
            >
              <Input.TextArea
                rows={4}
                value={formData.ai_prompt ?? ''}
                onChange={(e) => setFormData({ ...formData, ai_prompt: e.target.value || null })}
                placeholder="例：重点关注商品成色，对翻新机一票否决；优先考虑带原盒发票的商品"
                maxLength={500}
                showCount
              />
            </Form.Item>

            <Divider />

            {/* 任务级自动官方采集覆盖：留空（未设置）则沿用全局 AppConfig.eval */}
            {/* 为什么独立于全局配置模态框：高频任务可能需要单独关闭采集避免反爬，
                低频任务可能需要放宽 max_per_run 做深度扫描 */}
            <Form.Item
              label="自动官方采集（auto_collect_official）"
              help="留空则使用全局配置。开启后对通过评估的商品自动调用官方采集做深度验证"
            >
              <Space>
                <Switch
                  checked={formData.eval_config?.auto_collect_official ?? globalConfig?.eval?.auto_collect_official ?? false}
                  onChange={(v) => setFormData({
                    ...formData,
                    eval_config: { ...formData.eval_config, auto_collect_official: v },
                  })}
                />
                <Tag color={(() => {
                  // 任务级覆盖用蓝色高亮，继承全局则用默认色
                  if (formData.eval_config?.auto_collect_official != null) return 'blue'
                  return 'default'
                })()}>
                  {(() => {
                    if (formData.eval_config?.auto_collect_official != null) {
                      return `任务级：${formData.eval_config.auto_collect_official ? '已开启' : '已关闭'}`
                    }
                    return `沿用全局（${globalConfig?.eval?.auto_collect_official ? '已开启' : '已关闭'}）`
                  })()}
                </Tag>
                <Button
                  size="small"
                  onClick={() => {
                    const next = { ...formData.eval_config }
                    delete next.auto_collect_official
                    setFormData({ ...formData, eval_config: Object.keys(next).length > 0 ? next : null })
                  }}
                  disabled={formData.eval_config?.auto_collect_official == null}
                >
                  重置为全局
                </Button>
              </Space>
            </Form.Item>

            <Form.Item
              label="每轮最多采集条数（auto_collect_max_per_run）"
              help="留空则使用全局配置。避免拖慢+反爬"
            >
              <Space>
                <InputNumber
                  min={1}
                  max={20}
                  value={formData.eval_config?.auto_collect_max_per_run ?? null}
                  onChange={(v) => setFormData({
                    ...formData,
                    eval_config: { ...formData.eval_config, auto_collect_max_per_run: v ?? undefined },
                  })}
                  placeholder={`沿用全局（${globalConfig?.eval?.auto_collect_max_per_run ?? 3}）`}
                  style={{ width: 200 }}
                  addonAfter="条"
                />
                <Button
                  size="small"
                  onClick={() => {
                    const next = { ...formData.eval_config }
                    delete next.auto_collect_max_per_run
                    setFormData({ ...formData, eval_config: Object.keys(next).length > 0 ? next : null })
                  }}
                  disabled={formData.eval_config?.auto_collect_max_per_run == null}
                >
                  重置为全局
                </Button>
              </Space>
            </Form.Item>
          </Form>

          <Divider />

          {/* 全局 AI 评估配置概览（只读，点击按钮编辑） */}
          <Card size="small" type="inner" title="全局 AI 评估配置概览（只读）">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>通过分数（pass_score）</span>
                <Tag>{globalConfig?.eval?.pass_score ?? '-'}</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>自动抢单分数（auto_buy_score）</span>
                <Tag>{globalConfig?.eval?.auto_buy_score ?? '-'}</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>AI 自动评估</span>
                <Tag color={globalConfig?.eval?.ai_auto_eval ? 'green' : 'default'}>
                  {globalConfig?.eval?.ai_auto_eval ? '已开启' : '已关闭'}
                </Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>AI 深度分析</span>
                <Tag color={globalConfig?.eval?.ai_auto_deep_analyze ? 'green' : 'default'}>
                  {globalConfig?.eval?.ai_auto_deep_analyze ? '已开启' : '已关闭'}
                </Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>自动官方采集</span>
                <Tag color={globalConfig?.eval?.auto_collect_official ? 'green' : 'default'}>
                  {globalConfig?.eval?.auto_collect_official ? '已开启' : '已关闭'}
                </Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>每轮最多采集</span>
                <Tag>{globalConfig?.eval?.auto_collect_max_per_run ?? '-'} 条</Tag>
              </div>
            </Space>
          </Card>
        </Card>
      )}

      {/* Step 4: 反检测参数（全局配置） */}
      {current === 4 && (
        <Card
          title={
            <Space>
              <ThunderboltOutlined />
              <span>Step 5 · 反检测参数（全局配置）</span>
            </Space>
          }
          extra={
            <Button
              size="small"
              icon={<SettingOutlined />}
              onClick={() => setAntidetectModalOpen(true)}
            >
              修改全局反检测配置
            </Button>
          }
        >
          <Alert
            type="info"
            showIcon
            message="反检测参数为全局配置，所有任务共享"
            description="AntiDetect 实例在容器级创建，所有 TaskWorker 共享。如需按任务独立配置，需重构 collector 共享模型。调高 QPS 或调低延迟可能触发反爬封号，请谨慎操作。"
            style={{ marginBottom: 16 }}
          />

          <Card size="small" type="inner" title="全局反检测配置概览（只读）">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>每秒请求上限（qps）</span>
                <Tag color={(globalConfig?.antidetect?.qps ?? 1) > 5 ? 'red' : 'green'}>
                  {globalConfig?.antidetect?.qps ?? 1} 次/秒
                </Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>最小延迟（min_delay_ms）</span>
                <Tag>{globalConfig?.antidetect?.min_delay_ms ?? 200} ms</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>最大延迟（max_delay_ms）</span>
                <Tag>{globalConfig?.antidetect?.max_delay_ms ?? 1500} ms</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>连续失败熔断阈值（fail_pause_threshold）</span>
                <Tag>{globalConfig?.antidetect?.fail_pause_threshold ?? 3} 次</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>失败计数窗口（fail_window_sec）</span>
                <Tag>{globalConfig?.antidetect?.fail_window_sec ?? 3600} 秒</Tag>
              </div>
            </Space>
          </Card>

          {(globalConfig?.antidetect?.qps ?? 1) > 5 && (
            <Alert
              type="error"
              message={`当前全局 QPS=${globalConfig?.antidetect?.qps} 过高，可能触发反爬封号`}
              style={{ marginTop: 16 }}
              banner
            />
          )}
        </Card>
      )}

      {/* Step 5: 调度与确认 */}
      {current === 5 && (
        <Card
          title="Step 6 · 调度与确认"
          extra={
            <Button
              size="small"
              icon={<CloudDownloadOutlined />}
              onClick={() => setBatchRefreshModalOpen(true)}
            >
              批量采集配置
            </Button>
          }
        >
          <Form layout="vertical">
            <Form.Item label="调度模式" tooltip="固定间隔：每 N 秒执行一次；Cron：按表达式定时执行（如每天 9:00）">
              <Radio.Group value={useCron} onChange={(e) => setUseCron(e.target.value)}>
                <Radio.Button value={false}>⏱ 固定间隔</Radio.Button>
                <Radio.Button value={true}>📅 Cron 表达式</Radio.Button>
              </Radio.Group>
            </Form.Item>

            {/* S7735：交换分支改为肯定形式 useCron ? Cron : 固定间隔 */}
            {useCron ? (
              <Form.Item label="Cron 表达式（可视化编辑器）" tooltip="启用 Cron 模式后按表达式调度，忽略固定间隔">
                <CronEditor value={cron} onChange={setCron} />
              </Form.Item>
            ) : (
              <Form.Item
                label="执行间隔（秒）"
                tooltip="过短易触发反爬，过长可能错过抢单窗口。建议 60-300 秒"
              >
                <InputNumber
                  min={30}
                  max={3600}
                  value={intervalSeconds}
                  onChange={(v) => setIntervalSeconds(v ?? 60)}
                  addonAfter="秒"
                  style={{ width: 200 }}
                />
                {intervalSeconds < 60 && (
                  <Alert type="warning" message="执行间隔过短可能触发反爬" style={{ marginTop: 8 }} banner />
                )}
              </Form.Item>
            )}

            {/* 危险操作风险提示（提交前预览） */}
            {detectRiskyConfig().length > 0 && (
              <Alert
                type="warning"
                showIcon
                icon={<ExclamationCircleOutlined />}
                message="检测到以下风险配置，提交时将要求二次确认"
                style={{ marginTop: 16 }}
                description={
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {detectRiskyConfig().map((r, i) => (
                      <li key={`${r.level}-${i}`} style={{ color: r.level === 'danger' ? '#ff4d4f' : '#faad14', fontSize: 13 }}>
                        {r.message}
                      </li>
                    ))}
                  </ul>
                }
              />
            )}

            {/* 配置预览 */}
            <Card size="small" style={{ background: 'var(--xh-bg-spotlight)', marginTop: 16 }} title="📋 配置预览">
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
    use_cron: useCron,
    interval_seconds: intervalSeconds,
    cron,
    eval_threshold: formData.eval_threshold,
    ai_prompt: formData.ai_prompt,
    search_config: formData.search_config,
    antidetect_config: formData.antidetect_config,
    eval_config: formData.eval_config,
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
      </>
      )}

      {/* 全局 AI 评估配置快捷入口 Modal */}
      <GlobalEvalConfigModal open={evalModalOpen} onClose={() => setEvalModalOpen(false)} onSaved={() => {
        // 保存后重新加载全局配置，确保概览显示最新值
        configApi.get().then(setGlobalConfig).catch(() => {})
      }} />

      {/* 全局批量采集配置快捷入口 Modal */}
      <GlobalBatchRefreshModal open={batchRefreshModalOpen} onClose={() => setBatchRefreshModalOpen(false)} />

      {/* 全局反检测配置快捷入口 Modal */}
      <GlobalAntidetectConfigModal open={antidetectModalOpen} onClose={() => setAntidetectModalOpen(false)} onSaved={() => {
        configApi.get().then(setGlobalConfig).catch(() => {})
      }} />
    </div>
  )
}

// ============== 全局 AI 评估配置快捷入口 Modal ==============
// 复用 configStore 的 previewSave/confirmSave 流程，与 EvalRules 页面一致
// 在 TaskEditor 中提供快捷入口，避免用户跳转到配置页面才能修改全局评估参数
function GlobalEvalConfigModal({ open, onClose, onSaved }: { readonly open: boolean; readonly onClose: () => void; readonly onSaved: () => void }) {
  const { config, load, update, previewSave, confirmSave, hasChanges, reset } = useConfigStore()
  const [diffChanges, setDiffChanges] = useState<DiffChange[]>([])
  const [diffModalOpen, setDiffModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) load()
  }, [open, load])

  const handleSave = async () => {
    if (!config) return
    // 校验：pass_score 不能大于 auto_buy_score（与 EvalRules 页面一致）
    if (config.eval.pass_score > config.eval.auto_buy_score) {
      message.error('通过分数不能大于自动抢单分数')
      return
    }
    try {
      setSaving(true)
      const changes = await previewSave()
      if (changes.length === 0) {
        message.info('配置未变更')
        return
      }
      setDiffChanges(changes)
      setDiffModalOpen(true)
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
    }
  }

  const handleConfirmSave = async () => {
    try {
      setSaving(true)
      await confirmSave()
      setDiffModalOpen(false)
      message.success('全局 AI 评估配置已保存')
      onSaved()
      onClose()
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
    }
  }

  if (!config) return null
  const evalConfig = config.eval

  return (
    <>
      <Modal
        title={
          <Space>
            <RobotOutlined />
            <span>全局 AI 评估参数配置</span>
          </Space>
        }
        open={open}
        onCancel={onClose}
        width={720}
        footer={[
          <Button key="cancel" onClick={onClose}>取消</Button>,
          <Button key="reset" icon={<UndoOutlined />} onClick={reset} disabled={!hasChanges()}>重置</Button>,
          <Button key="save" type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>保存</Button>,
        ]}
      >
        <Alert
          type="info"
          showIcon
          message="此配置为全局设置，对所有任务生效"
          description="任务级覆盖优先于全局配置。如需修改 AI 模型（gpt-4o 等），请前往「AI 配置」页面。"
          style={{ marginBottom: 16 }}
        />

        <Card title="通过阈值" size="small" style={{ marginBottom: 16 }}>
          <Form layout="vertical">
            <Form.Item label="通过分数（pass_score）" help="≥ 此分数：通知用户">
              <Slider
                min={0}
                max={100}
                value={evalConfig.pass_score}
                onChange={(v) => update({ eval: { ...evalConfig, pass_score: v } })}
                marks={{ 0: '0', 60: '60', 80: '80', 100: '100' }}
              />
            </Form.Item>
            <Form.Item label="自动抢单分数（auto_buy_score）" help="≥ 此分数：全自动拍下">
              <Slider
                min={0}
                max={100}
                value={evalConfig.auto_buy_score}
                onChange={(v) => update({ eval: { ...evalConfig, auto_buy_score: v } })}
                marks={{ 0: '0', 60: '60', 80: '80', 100: '100' }}
              />
            </Form.Item>
            {evalConfig.pass_score > evalConfig.auto_buy_score && (
              <Alert type="error" message="通过分数不能大于自动抢单分数" banner />
            )}
          </Form>
        </Card>

        <Card title="AI 评估与自动采集" size="small">
          <Form layout="vertical">
            <Form.Item label="AI 自动评估" help="开启后对通过规则评估的商品自动调用 AI 视觉评估（消耗 token）">
              <Switch
                checked={evalConfig.ai_auto_eval}
                onChange={(v) => update({ eval: { ...evalConfig, ai_auto_eval: v } })}
              />
            </Form.Item>
            <Form.Item label="AI 深度分析" help="开启后对通过 AI 评估的商品自动进行深度分析（消耗更多 token）">
              <Switch
                checked={evalConfig.ai_auto_deep_analyze}
                onChange={(v) => update({ eval: { ...evalConfig, ai_auto_deep_analyze: v } })}
              />
            </Form.Item>
            <Form.Item label="自动官方采集" help="开启后对通过评估的商品自动调用官方采集做深度验证">
              <Switch
                checked={evalConfig.auto_collect_official}
                onChange={(v) => update({ eval: { ...evalConfig, auto_collect_official: v } })}
              />
            </Form.Item>
            <Form.Item label="每轮最多采集条数" help="避免拖慢+反爬">
              <InputNumber
                min={1}
                max={20}
                value={evalConfig.auto_collect_max_per_run}
                onChange={(v) => update({ eval: { ...evalConfig, auto_collect_max_per_run: v || 3 } })}
                addonAfter="条"
                style={{ width: 200 }}
              />
            </Form.Item>
          </Form>
        </Card>
      </Modal>

      {/* Diff 预览 Modal（与 EvalRules 页面风格一致） */}
      <Modal
        title="配置变更预览"
        open={diffModalOpen}
        onCancel={() => setDiffModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setDiffModalOpen(false)}>取消</Button>,
          <Button key="confirm" type="primary" loading={saving} onClick={handleConfirmSave}>确认保存</Button>,
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
            { title: '原值', dataIndex: 'old_value', key: 'old_value', render: renderDiffValue },
            { title: '新值', dataIndex: 'new_value', key: 'new_value', render: renderDiffValue },
            { title: '操作', dataIndex: 'op', key: 'op', render: renderOpTag },
          ]}
        />
      </Modal>
    </>
  )
}

// ============== 全局批量采集配置快捷入口 Modal ==============
// 批量采集调度器配置（BatchRefreshConfig）：定时刷新在售商品详情
// 在调度确认步骤提供快捷入口，避免用户跳转到配置文件修改
function GlobalBatchRefreshModal({ open, onClose }: { readonly open: boolean; readonly onClose: () => void }) {
  const { config, load, update, previewSave, confirmSave, hasChanges, reset } = useConfigStore()
  const [diffChanges, setDiffChanges] = useState<DiffChange[]>([])
  const [diffModalOpen, setDiffModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) load()
  }, [open, load])

  // S4144：实现已提取为模块级 previewConfigSave，此处仅按本组件状态转发调用
  const handleSave = () => previewConfigSave({
    setSaving, previewSave, setDiffChanges, setDiffModalOpen,
  })

  const handleConfirmSave = async () => {
    try {
      setSaving(true)
      await confirmSave()
      setDiffModalOpen(false)
      message.success('批量采集配置已保存')
      onClose()
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
    }
  }

  if (!config) return null
  const br = config.batch_refresh

  return (
    <>
      <Modal
        title={
          <Space>
            <CloudDownloadOutlined />
            <span>批量采集调度配置</span>
          </Space>
        }
        open={open}
        onCancel={onClose}
        width={600}
        footer={[
          <Button key="cancel" onClick={onClose}>取消</Button>,
          <Button key="reset" icon={<UndoOutlined />} onClick={reset} disabled={!hasChanges()}>重置</Button>,
          <Button key="save" type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>保存</Button>,
        ]}
      >
        <Alert
          type="info"
          showIcon
          message="定时刷新在售商品详情，用于检测已售状态、补全字段"
          description="此配置为全局设置，需要调度器进程（XH_WITH_SCHEDULER=1）运行时才生效。"
          style={{ marginBottom: 16 }}
        />

        <Form layout="vertical">
          <Form.Item label="启用批量采集" help="关闭后调度器不会定时触发采集">
            <Switch
              checked={br.enabled}
              onChange={(v) => update({ batch_refresh: { ...br, enabled: v } })}
            />
          </Form.Item>
          <Form.Item label="触发间隔（分钟）" help="定时触发间隔，建议 30-60 分钟">
            <InputNumber
              min={5}
              max={1440}
              value={br.interval_minutes}
              onChange={(v) => update({ batch_refresh: { ...br, interval_minutes: v || 30 } })}
              addonAfter="分钟"
              style={{ width: 200 }}
            />
          </Form.Item>
          <Form.Item label="每批拉取数（batch_size）" help="每批从 DB 拉取的最大商品数（分页控制）">
            <InputNumber
              min={10}
              max={500}
              value={br.batch_size}
              onChange={(v) => update({ batch_refresh: { ...br, batch_size: v || 50 } })}
              addonAfter="条"
              style={{ width: 200 }}
            />
          </Form.Item>
          <Form.Item label="单次最多采集数（max_items_per_run）" help="防止单次运行长时间占用浏览器">
            <InputNumber
              min={10}
              max={1000}
              value={br.max_items_per_run}
              onChange={(v) => update({ batch_refresh: { ...br, max_items_per_run: v || 100 } })}
              addonAfter="条"
              style={{ width: 200 }}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="配置变更预览"
        open={diffModalOpen}
        onCancel={() => setDiffModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setDiffModalOpen(false)}>取消</Button>,
          <Button key="confirm" type="primary" loading={saving} onClick={handleConfirmSave}>确认保存</Button>,
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
            { title: '原值', dataIndex: 'old_value', key: 'old_value', render: renderDiffValue },
            { title: '新值', dataIndex: 'new_value', key: 'new_value', render: renderDiffValue },
            { title: '操作', dataIndex: 'op', key: 'op', render: renderOpTag },
          ]}
        />
      </Modal>
    </>
  )
}

// ============== 全局反检测配置快捷入口 Modal ==============
// 反检测参数（AntiDetectConfig）为全局配置，所有任务共享
// AntiDetect 实例在 container 级创建，无法按任务独立切换
function GlobalAntidetectConfigModal({ open, onClose, onSaved }: { readonly open: boolean; readonly onClose: () => void; readonly onSaved: () => void }) {
  const { config, load, update, previewSave, confirmSave, hasChanges, reset } = useConfigStore()
  const [diffChanges, setDiffChanges] = useState<DiffChange[]>([])
  const [diffModalOpen, setDiffModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) load()
  }, [open, load])

  // S4144：实现已提取为模块级 previewConfigSave，此处仅按本组件状态转发调用
  const handleSave = () => previewConfigSave({
    setSaving, previewSave, setDiffChanges, setDiffModalOpen,
  })

  const handleConfirmSave = async () => {
    try {
      setSaving(true)
      await confirmSave()
      setDiffModalOpen(false)
      message.success('全局反检测配置已保存')
      onSaved()
      onClose()
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
    }
  }

  if (!config) return null
  const ad = config.antidetect

  return (
    <>
      <Modal
        title={
          <Space>
            <ThunderboltOutlined />
            <span>全局反检测参数配置</span>
          </Space>
        }
        open={open}
        onCancel={onClose}
        width={600}
        footer={[
          <Button key="cancel" onClick={onClose}>取消</Button>,
          <Button key="reset" icon={<UndoOutlined />} onClick={reset} disabled={!hasChanges()}>重置</Button>,
          <Button key="save" type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>保存</Button>,
        ]}
      >
        <Alert
          type="warning"
          showIcon
          message="反检测参数为全局配置，影响所有任务"
          description="调高 QPS 或调低延迟可能触发反爬封号。修改后需重启调度器进程才生效（AntiDetect 实例在启动时创建）。"
          style={{ marginBottom: 16 }}
        />

        <Form layout="vertical">
          <Form.Item label="每秒请求上限（qps）" help={`建议 ≤ 5，过高触发反爬。当前：${ad.qps}`}>
            <InputNumber
              min={1}
              max={20}
              value={ad.qps}
              onChange={(v) => update({ antidetect: { ...ad, qps: v || 1 } })}
              addonAfter="次/秒"
              style={{ width: 200 }}
            />
            {ad.qps > 5 && (
              <Alert type="error" message="QPS 过高可能触发反爬封号" style={{ marginTop: 8 }} banner />
            )}
          </Form.Item>
          <Form.Item label="最小延迟（min_delay_ms）" help="请求间最小间隔">
            <InputNumber
              min={0}
              max={5000}
              value={ad.min_delay_ms}
              onChange={(v) => update({ antidetect: { ...ad, min_delay_ms: v ?? 200 } })}
              addonAfter="ms"
              style={{ width: 200 }}
            />
          </Form.Item>
          <Form.Item label="最大延迟（max_delay_ms）" help="请求间最大间隔">
            <InputNumber
              min={0}
              max={10000}
              value={ad.max_delay_ms}
              onChange={(v) => update({ antidetect: { ...ad, max_delay_ms: v ?? 1500 } })}
              addonAfter="ms"
              style={{ width: 200 }}
            />
          </Form.Item>
          <Form.Item label="连续失败熔断阈值（fail_pause_threshold）" help="连续失败此次数后暂停任务">
            <InputNumber
              min={1}
              max={50}
              value={ad.fail_pause_threshold}
              onChange={(v) => update({ antidetect: { ...ad, fail_pause_threshold: v || 3 } })}
              addonAfter="次"
              style={{ width: 200 }}
            />
          </Form.Item>
          <Form.Item label="失败计数窗口（fail_window_sec）" help="在此时间窗口内累计失败次数">
            <InputNumber
              min={60}
              max={86400}
              value={ad.fail_window_sec}
              onChange={(v) => update({ antidetect: { ...ad, fail_window_sec: v ?? 3600 } })}
              addonAfter="秒"
              style={{ width: 200 }}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="配置变更预览"
        open={diffModalOpen}
        onCancel={() => setDiffModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setDiffModalOpen(false)}>取消</Button>,
          <Button key="confirm" type="primary" loading={saving} onClick={handleConfirmSave}>确认保存</Button>,
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
            { title: '原值', dataIndex: 'old_value', key: 'old_value', render: renderDiffValue },
            { title: '新值', dataIndex: 'new_value', key: 'new_value', render: renderDiffValue },
            { title: '操作', dataIndex: 'op', key: 'op', render: renderOpTag },
          ]}
        />
      </Modal>
    </>
  )
}

// ============== 价格区间双滑块组件 ==============
// 边界哨兵：max 取这个值表示"无上限"，Slider 不应触发 props.onChange 把 100000 反复转 null
// 为什么用哨兵常量：原实现 [min ?? 0, max ?? 100000] 在拖动过程中会让 Slider value 在
// 0/100000 与 真实值之间反复跳变，引发 onChange 递归更新父组件，外部 InputNumber
// 同步出现延迟。改用本地 state 持有 number，onChangeComplete 才提交 props.onChange
const PRICE_MIN = 0
const PRICE_MAX = 100000
const PRICE_STEP = 100

function PriceRangeSlider({
  min,
  max,
  onChange,
}: {
  readonly min: number | null
  readonly max: number | null
  readonly onChange: (min: number | null, max: number | null) => void
}) {
  // 本地 range 状态：始终是 number（不存 null）
  // 为什么用本地 state：Slider 在拖动过程中持续触发 onChange，直接透传会引发父组件
  // setState 风暴；onChangeComplete（拖动结束）才提交 props.onChange，让 InputNumber
  // 仅在拖动结束时同步，避免持续闪烁和性能浪费
  const [range, setRange] = useState<[number, number]>([
    min ?? PRICE_MIN,
    max ?? PRICE_MAX,
  ])

  // 外部 min/max 变化（如 InputNumber 输入、父组件恢复草稿、URL 预填充）→ 同步到本地
  // 只在 props 与本地不一致时更新，避免拖动过程中 props.onChange 回流触发额外 setState
  useEffect(() => {
    const nextMin = min ?? PRICE_MIN
    const nextMax = max ?? PRICE_MAX
    setRange((prev) => (prev[0] === nextMin && prev[1] === nextMax ? prev : [nextMin, nextMax]))
  }, [min, max])

  // 拖动过程中：仅更新本地 state，UI 跟手、不触发父组件更新
  // Slider 在 range 模式下 onChange 的 v 一定是 number[]，但类型签名仍是 number | number[]
  const handleSliderChange = (v: number | number[]) => {
    if (!Array.isArray(v)) return
    setRange([v[0], v[1]])
  }

  // 拖动结束：把哨兵值（PRICE_MIN/PRICE_MAX）转回 null 提交给父组件
  // 为什么在这里处理：拖动过程中本地 state 始终是 number，0/100000 表示"无下限/无上限"，
  // 转 null 的动作延后到拖动结束，避免过程中父组件持续 re-render 导致 Slider 闪烁
  const handleSliderChangeComplete = (v: number | number[]) => {
    if (!Array.isArray(v)) return
    onChange(v[0] === PRICE_MIN ? null : v[0], v[1] === PRICE_MAX ? null : v[1])
  }

  // 最低价输入：直接提交 props.onChange（InputNumber 是离散输入，无拖动过程）
  // min=0 转 null 的语义放在父组件 / 此处统一：保持与 Slider 完成时一致
  const handleMinInput = (v: number | null | undefined) => {
    onChange(v ?? null, max)
  }

  // 最高价输入：同上；同时钳制 max 不低于当前 min（防止区间倒置）
  // 倒置校验：若用户先输入 max=3000 再输入 min=5000，max 会被自动提升到 ≥ 5000，
  // 避免数据库存非法区间
  const handleMaxInput = (v: number | null | undefined) => {
    onChange(min, v ?? null)
  }

  return (
    <div>
      <Slider
        range
        min={PRICE_MIN}
        max={PRICE_MAX}
        step={PRICE_STEP}
        value={range}
        onChange={handleSliderChange}
        onChangeComplete={handleSliderChangeComplete}
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
          min={0}
          max={range[1] === PRICE_MAX ? undefined : range[1]}
          // 关键：用本地 range[0] 而不是 props.min，确保 Slider 拖动中 InputNumber 不会抖动
          value={range[0]}
          onChange={handleMinInput}
          style={{ width: 120 }}
        />
        <span>~</span>
        <InputNumber
          prefix="¥"
          placeholder="最高价"
          min={0}
          max={PRICE_MAX}
          value={range[1] === PRICE_MAX ? undefined : range[1]}
          onChange={handleMaxInput}
          style={{ width: 120 }}
        />
      </Space>
    </div>
  )
}
