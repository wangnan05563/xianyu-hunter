import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { Table, Button, Space, Tag, Modal, message, Input, Spin, Empty, Card, Select, Alert, Collapse, Tabs, Form, Tooltip, Segmented, Row, Col, Switch } from 'antd'
import { PlusOutlined, EditOutlined, PlayCircleOutlined, PauseCircleOutlined, ThunderboltOutlined, AppstoreOutlined, DeleteOutlined, CopyOutlined, StopOutlined, ClearOutlined, LinkOutlined, ReloadOutlined, EyeOutlined, MinusCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { taskApi, aiApi, templateApi, taskLinkApi, configApi, Task, TaskTemplate, AIParseTaskResult, TaskLink, LiveProgress, LiveFilterSummary } from '../../api'
import { STATUS_COLOR as statusColors } from '../../constants/statusColors'
import { usePersistentState } from '../../hooks/usePersistentState'
import { useAutoLiveSearch } from '../../hooks/useAutoLiveSearch'

// 让 Tag/span 等非原生交互元素获得键盘可访问性（S6848：onClick 需配合键盘事件）
// 用结构类型避免引入 React 命名空间依赖
const clickableProps = (cb: () => void) => ({
  role: 'button' as const,
  tabIndex: 0,
  onClick: cb,
  onKeyDown: (e: { key: string; preventDefault: () => void }) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      cb()
    }
  },
})

const statusLabels: Record<string, string> = {
  running: '运行中',
  paused: '已暂停',
  stopped: '已停止',
  deleted: '已删除',
}

const modeLabels: Record<string, string> = {
  auto: '全自动',
  semi_auto: '半自动',
  confirm: '需确认',
  notify: '仅通知',
}

// 模板市场分类
const tplCategories = ['全部', '相机', '游戏', '球鞋', '票务', '数码', '其他']

export default function TaskList() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = usePersistentState<number>('xh.tasks.pageSize', 20, {
    validator: (v): v is number => typeof v === 'number' && v > 0 && Number.isFinite(v),
  })
  const [statusFilter, setStatusFilter] = useState<string>('')

  // ---- 智能建任务状态 ----
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [aiInput, setAiInput] = useState('')
  const [aiParsing, setAiParsing] = useState(false)
  const [aiResult, setAiResult] = useState<AIParseTaskResult | null>(null)
  const [aiError, setAiError] = useState('')

  // ---- 模板市场状态 ----
  const [tplModalOpen, setTplModalOpen] = useState(false)
  const [tplItems, setTplItems] = useState<TaskTemplate[]>([])
  const [tplCategory, setTplCategory] = useState('全部')
  const [tplSearch, setTplSearch] = useState('')
  const [tplLoading, setTplLoading] = useState(false)

  // ---- 批量操作状态 ----
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])

  // ---- 视图模式：桌面默认表格，移动默认卡片 ----
  // 为什么用 usePersistentState：用户切换视图模式后刷新应保持，但首次访问需根据屏幕宽度决定默认值
  const [viewMode, setViewMode] = usePersistentState<'table' | 'card'>(
    'xh.tasks.viewMode',
    globalThis.innerWidth < 768 ? 'card' : 'table',
    { validator: (v): v is 'table' | 'card' => v === 'table' || v === 'card' },
  )

  // ---- 行内二次确认状态机 ----
  // 结构：{ taskId: { action, label, hint, armed_at } }
  const [armConfirm, setArmConfirm] = useState<Record<string, { action: string; label: string; hint: string; armed_at: number }>>({})
  const armTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  /** 装备确认：点击危险按钮后切换为"确认/取消" */
  const doArmConfirm = (taskId: string, action: string, label: string, hint: string) => {
    // 清除旧的定时器
    if (armTimers.current[taskId]) clearTimeout(armTimers.current[taskId])
    setArmConfirm((prev) => ({ ...prev, [taskId]: { action, label, hint, armed_at: Date.now() } }))
    // 5秒未确认自动撤销
    armTimers.current[taskId] = setTimeout(() => {
      setArmConfirm((prev) => {
        const next = { ...prev }
        delete next[taskId]
        return next
      })
      delete armTimers.current[taskId]
    }, 5000)
  }

  /** 取消确认：恢复原按钮 */
  const cancelArmConfirm = (taskId: string) => {
    if (armTimers.current[taskId]) {
      clearTimeout(armTimers.current[taskId])
      delete armTimers.current[taskId]
    }
    setArmConfirm((prev) => {
      const next = { ...prev }
      delete next[taskId]
      return next
    })
  }

  /** 确认执行危险操作 */
  const executeArmConfirm = async (taskId: string) => {
    const arm = armConfirm[taskId]
    if (!arm) return
    // 清除定时器
    if (armTimers.current[taskId]) {
      clearTimeout(armTimers.current[taskId])
      delete armTimers.current[taskId]
    }
    // 先清除确认状态，防止重复点击
    setArmConfirm((prev) => {
      const next = { ...prev }
      delete next[taskId]
      return next
    })
    try {
      await taskApi[arm.action as 'stop' | 'delete'](taskId)
      message.success('操作成功')
      load()
    } catch {
      message.error('操作失败')
    }
  }

  // ---- 关联数状态 ----
  const [linkCounts, setLinkCounts] = useState<Record<string, number>>({})

  // ---- 闲鱼内容关联面板状态 ----
  const [linkPanelOpen, setLinkPanelOpen] = useState(false)
  const [linkTaskId, setLinkTaskId] = useState<string>('')
  const [linkSearch, setLinkSearch] = useState('')
  const [linkType, setLinkType] = useState<string>('item')
  const [linkItems, setLinkItems] = useState<TaskLink[]>([])
  const [linkTotal, setLinkTotal] = useState(0)
  const [linkPage, setLinkPage] = useState(1)
  const [linkPageSize] = useState(10)
  const [linkLoading, setLinkLoading] = useState(false)
  const [liveLoading, setLiveLoading] = useState(false)
  const [liveItems, setLiveItems] = useState<TaskLink[]>([])
  // SSE 进度阶段：用于实时显示搜索当前步骤
  const [liveStage, setLiveStage] = useState<string>('')
  // 实时搜索过滤汇总：done 阶段由后端返回，用于在 final_total=0 时展示过滤原因
  const [liveFilterSummary, setLiveFilterSummary] = useState<LiveFilterSummary | null>(null)
  // "显示被过滤结果" Modal 开关
  const [filteredModalOpen, setFilteredModalOpen] = useState(false)
  // 手动添加 Modal
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [addForm] = Form.useForm()
  const [addLoading, setAddLoading] = useState(false)
  // 一键启动所有任务（迁移自原仪表盘 TaskContentMenu）
  const [startAllLoading, setStartAllLoading] = useState(false)

  // 自动搜索开关：localStorage 持久化，首次访问从全局配置读取默认值
  // 为什么异步加载 config 后才设置：usePersistentState 同步初始化无法等待 config
  const [autoSearchEnabled, setAutoSearchEnabled] = usePersistentState<boolean>(
    'xh.tasks.autoSearchEnabled',
    false,
  )

  useEffect(() => {
    // localStorage 已有值：用户偏好优先，不覆盖
    if (localStorage.getItem('xh.tasks.autoSearchEnabled') !== null) return
    let cancelled = false
    configApi.get()
      .then(cfg => {
        if (cancelled) return
        // 双重检查：防止 usePersistentState 防抖写入抢先
        if (localStorage.getItem('xh.tasks.autoSearchEnabled') !== null) return
        setAutoSearchEnabled(cfg.task_scheduler?.auto_search_enabled ?? false)
      })
      .catch(() => { /* config 加载失败保持默认 false */ })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 自动实时搜索 Hook：串行队列 + 可见性暂停 + 1s tick
  // pauseAll 用于用户主动关闭开关时清空待搜索队列，避免队列中任务继续执行
  const { remainMap, searchingIds, pauseAll } = useAutoLiveSearch({
    tasks,
    enabled: autoSearchEnabled,
    onTaskSearchComplete: (taskId, success, itemCount) => {
      const taskName = tasks.find(t => t.id === taskId)?.name ?? taskId
      if (!success) {
        message.warning(`任务「${taskName}」自动搜索失败`)
      } else if (itemCount > 0) {
        message.success(`任务「${taskName}」自动搜索完成，新增 ${itemCount} 条`)
      }
    },
  })

  const load = async () => {
    setLoading(true)
    try {
      const res = await taskApi.list({ status: statusFilter || undefined, limit: pageSize, offset: (page - 1) * pageSize })
      setTasks(res.items || [])
      setTotal(res.total || 0)
      // 加载每个任务的关联数
      const counts: Record<string, number> = {}
      await Promise.all(
        (res.items || []).map(async (t) => {
          try {
            const c = await taskLinkApi.count(t.id)
            counts[t.id] = c.total
          } catch {
            counts[t.id] = 0
          }
        }),
      )
      setLinkCounts(counts)
    } catch {
      message.error('加载任务列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, statusFilter])

  // ============== 智能建任务 ==============

  const openAiParse = () => {
    setAiInput('')
    setAiResult(null)
    setAiError('')
    setAiParsing(false)
    setAiModalOpen(true)
  }

  const doAiParse = async () => {
    if (!aiInput.trim()) {
      message.warning('请输入需求描述')
      return
    }
    setAiParsing(true)
    setAiError('')
    setAiResult(null)
    try {
      const result = await aiApi.parseTask(aiInput.trim())
      if (!result.keyword) {
        setAiError('AI 未能提取出关键词，请尝试更具体的描述')
        return
      }
      setAiResult(result)
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response?.status
      if (status === 400 || status === 422) {
        setAiError('AI 服务未配置或请求格式错误，请先在配置页设置 AI 服务')
      } else {
        setAiError('AI 解析失败，请稍后重试或检查网络连接')
      }
    } finally {
      setAiParsing(false)
    }
  }

  // 将 AI 解析结果填入 TaskEditor，通过 URL search params 传递
  const applyAiResult = () => {
    if (!aiResult) return
    const validModes = ['notify', 'confirm', 'auto', 'semi_auto']
    const mode = validModes.includes(aiResult.mode) ? aiResult.mode : 'notify'
    const params = new URLSearchParams({
      keyword: aiResult.keyword,
      name: aiResult.name || aiResult.keyword,
      mode,
    })
    if (aiResult.min_price != null) params.set('min_price', String(aiResult.min_price))
    if (aiResult.max_price != null) params.set('max_price', String(aiResult.max_price))
    setAiModalOpen(false)
    navigate(`/tasks/new?${params.toString()}`)
  }

  // ============== 模板市场 ==============

  const loadTemplates = async () => {
    setTplLoading(true)
    try {
      const res = await templateApi.list(tplCategory)
      setTplItems(res.items || [])
    } catch {
      message.error('加载模板失败')
    } finally {
      setTplLoading(false)
    }
  }

  const openTemplateMarket = () => {
    setTplCategory('全部')
    setTplSearch('')
    setTplModalOpen(true)
    // loadTemplates 由下方 useEffect 在 tplCategory 变化时自动触发，无需手动调用
  }

  useEffect(() => {
    if (tplModalOpen) loadTemplates()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tplCategory, tplModalOpen])

  const filteredTplItems = tplItems.filter((t) => {
    if (!tplSearch) return true
    const q = tplSearch.toLowerCase()
    return (t.name?.toLowerCase().includes(q) || t.keyword?.toLowerCase().includes(q))
  })

  const applyTemplate = (tpl: TaskTemplate) => {
    const validModes = ['notify', 'confirm', 'auto', 'semi_auto']
    const mode = validModes.includes(tpl.mode) ? tpl.mode : 'notify'
    const params = new URLSearchParams({
      keyword: tpl.keyword,
      name: tpl.name,
      mode,
    })
    if (tpl.min_price != null) params.set('min_price', String(tpl.min_price))
    if (tpl.max_price != null) params.set('max_price', String(tpl.max_price))
    setTplModalOpen(false)
    navigate(`/tasks/new?${params.toString()}`)
  }

  const deleteTemplate = async (id: string) => {
    try {
      await templateApi.delete(id)
      message.success('模板已删除')
      loadTemplates()
    } catch {
      message.error('删除失败')
    }
  }

  // ============== 任务操作 ==============

  const handleAction = async (id: string, action: 'start' | 'pause' | 'resume' | 'stop' | 'delete') => {
    try {
      // 停止和删除由行内二次确认机制处理，此处不再弹 Modal
      await taskApi[action](id)
      message.success('操作成功')
      load()
    } catch {
      message.error('操作失败')
    }
  }

  // 复制任务：跳转到新建页，携带原任务参数
  const cloneTask = (task: Task) => {
    const params = new URLSearchParams({
      keyword: task.keyword + ' 副本',
      name: (task.name || task.keyword) + ' 副本',
      mode: task.mode,
    })
    if (task.min_price != null) params.set('min_price', String(task.min_price))
    if (task.max_price != null) params.set('max_price', String(task.max_price))
    navigate(`/tasks/new?${params.toString()}`)
  }

  // 另存为模板
  const saveAsTemplate = async (task: Task) => {
    try {
      await templateApi.create({
        name: task.name || task.keyword,
        keyword: task.keyword,
        min_price: task.min_price,
        max_price: task.max_price,
        mode: task.mode,
        icon: '📋',
        category: '其他',
      })
      message.success('已保存为私有模板')
    } catch {
      message.error('保存模板失败')
    }
  }

  // ============== 沉默状态计算 ==============

  const getSilenceTag = (task: Task) => {
    // created_at 和 updated_at 相同时视为从未更新
    if (!task.updated_at || task.updated_at === task.created_at) {
      return <Tag color="default">无活动</Tag>
    }
    const daysSinceUpdate = (Date.now() - new Date(task.updated_at).getTime()) / (1000 * 60 * 60 * 24)
    if (daysSinceUpdate > 30) return <Tag color="red">沉默30d+</Tag>
    if (daysSinceUpdate > 7) return <Tag color="orange">沉默7d+</Tag>
    return <Tag color="green">活跃</Tag>
  }

  // ============== 批量操作 ==============

  const handleBatchAction = (action: 'pause' | 'resume' | 'stop' | 'delete') => {
    const ids = selectedRowKeys.map(String)
    if (ids.length === 0) return

    // 删除和停止需要二次确认
    if (action === 'delete' || action === 'stop') {
      const label = action === 'delete' ? '删除' : '停止'
      Modal.confirm({
        title: `确认批量${label}？`,
        content: `将${label} ${ids.length} 个任务，此操作不可撤销。`,
        okType: 'danger',
        onOk: async () => {
          try {
            await taskApi.batchControl(ids, action)
            message.success(`已批量${label} ${ids.length} 个任务`)
            setSelectedRowKeys([])
            load()
          } catch {
            message.error(`批量${label}失败`)
          }
        },
      })
      return
    }

    // 暂停/恢复直接执行
    taskApi.batchControl(ids, action).then(() => {
      message.success(`批量操作成功`)
      setSelectedRowKeys([])
      load()
    }).catch(() => {
      message.error('批量操作失败')
    })
  }

  // ============== 闲鱼内容关联面板 ==============

  // 加载关联列表
  const loadLinks = useCallback(() => {
    if (!linkTaskId) return
    setLinkLoading(true)
    const offset = (linkPage - 1) * linkPageSize
    taskLinkApi.list(linkTaskId, { type: linkType, limit: linkPageSize, offset })
      .then((res) => {
        setLinkItems(res.items)
        setLinkTotal(res.total_for_type)
      })
      .catch(() => message.error('加载关联列表失败'))
      .finally(() => setLinkLoading(false))
  }, [linkTaskId, linkType, linkPage, linkPageSize])

  useEffect(() => { loadLinks() }, [loadLinks])

  // 跨任务搜索过滤（useMemo 避免每次渲染重新计算）
  const filteredLinkItems = useMemo(() => linkItems.filter((item) => {
    if (!linkSearch) return true
    const q = linkSearch.toLowerCase()
    return (
      item.link_key.toLowerCase().includes(q) ||
      (item.display.title || '').toLowerCase().includes(q)
    )
  }), [linkItems, linkSearch])

  // 实时查询（SSE 流式接收进度）
  const handleLive = () => {
    if (!linkTaskId) {
      message.warning('请先选择任务')
      return
    }
    setLiveLoading(true)
    setLiveItems([])
    setLiveFilterSummary(null)
    setLiveStage('正在检查缓存...')
    // SSE 进度阶段中文映射
    const stageLabels: Record<string, string> = {
      checking_cache: '正在检查缓存...',
      checking_cookies: '正在检查登录状态...',
      acquiring_lock: '正在获取浏览器锁...',
      searching: '正在搜索闲鱼...',
      refreshing_token: '正在刷新搜索令牌...',
      searching_retry: '正在重试搜索...',
      filtering: '正在过滤结果...',
      writing_db: '正在写入数据库...',
    }
    taskLinkApi.live(linkTaskId, (data: LiveProgress) => {
      if (data.stage && stageLabels[data.stage]) {
        setLiveStage(stageLabels[data.stage])
      }
    })
      .then((res) => {
        setLiveItems(res.items || [])
        setLiveStage('')
        // 保存过滤汇总，供"显示被过滤结果"按钮使用
        const fs = res.filter_summary
        setLiveFilterSummary(fs || null)
        const itemCount = res.items?.length || 0
        if (itemCount > 0) {
          message.success(`实时查询完成，获取 ${itemCount} 条`)
        } else if (fs && fs.raw > 0) {
          // 搜索有结果但全被过滤掉：提示用户调整过滤条件，而非显示"获取 0 条"
          // 为什么区分：raw=0 表示闲鱼本身搜不到，raw>0 final_total=0 表示被任务过滤条件筛掉
          const reasons: string[] = []
          if (fs.keyword_skipped) reasons.push(`关键词 ${fs.keyword_skipped}`)
          if (fs.price_skipped) reasons.push(`价格 ${fs.price_skipped}`)
          if (fs.publish_days_skipped) reasons.push(`发布时间 ${fs.publish_days_skipped}`)
          message.warning(
            `搜索到 ${fs.raw} 条，但全部被过滤条件筛掉（${reasons.join('、') || '未知原因'}），请调整任务过滤配置`,
          )
        } else {
          message.info('实时查询完成，未找到匹配商品')
        }
      })
      .catch(() => {
        setLiveStage('')
        message.error('实时查询失败')
      })
      .finally(() => setLiveLoading(false))
  }

  // 删除关联
  const handleRemoveLink = (linkId: number) => {
    if (!linkTaskId) return
    taskLinkApi.remove(linkTaskId, linkId).then(() => {
      message.success('已删除')
      loadLinks()
    }).catch(() => message.error('删除失败'))
  }

  // 手动添加关联
  const handleAddLink = async () => {
    try {
      const values = await addForm.validateFields()
      if (!linkTaskId) {
        message.warning('请先选择任务')
        return
      }
      setAddLoading(true)
      await taskLinkApi.create(linkTaskId, {
        link_type: values.link_type,
        link_key: values.link_key,
        note: values.note || undefined,
      })
      message.success('添加成功')
      setAddModalOpen(false)
      addForm.resetFields()
      loadLinks()
    } catch (err: unknown) {
      // validateFields 失败时 err 是表单错误对象，不需要 message 提示
      if (err && typeof err === 'object' && 'errorFields' in err) return
      message.error('添加失败')
    } finally {
      setAddLoading(false)
    }
  }

  // 一键启动所有任务（迁移自原仪表盘 TaskContentMenu.handleStartAll）
  // 为什么用 batchControl 而非逐个 control：减少网络请求，与现有批量操作一致
  const handleStartAll = useCallback(() => {
    const toStart = tasks.filter((t) => t.status !== 'running')
    const skipped = tasks.length - toStart.length

    if (toStart.length === 0) {
      message.info(skipped > 0 ? `所有 ${skipped} 个任务已在运行中` : '暂无任务可启动')
      return
    }

    const taskNames = toStart.map((t) => t.name || t.keyword).slice(0, 5).join('、')
    const more = toStart.length > 5 ? ` 等 ${toStart.length} 个任务` : ''

    Modal.confirm({
      title: '确认启动所有任务？',
      content: `将启动 ${toStart.length} 个任务（${taskNames}${more}）` +
        (skipped > 0 ? `，跳过 ${skipped} 个已运行任务` : ''),
      okText: '启动',
      cancelText: '取消',
      onOk: async () => {
        setStartAllLoading(true)
        try {
          await taskApi.batchControl(toStart.map((t) => t.id), 'restart')
          message.success(`已启动 ${toStart.length} 个任务` + (skipped > 0 ? `，跳过 ${skipped} 个` : ''))
          // 刷新任务列表以同步状态
          await load()
        } catch (err: unknown) {
          const detail = err instanceof Error ? err.message : String(err)
          message.error(`启动失败: ${detail.slice(0, 100)}`)
        } finally {
          setStartAllLoading(false)
        }
      },
    })
  }, [tasks])

  // 合并 DB 数据与实时数据用于展示（useMemo 避免每次渲染重新合并数组）
  const mergedLinkData = useMemo(() => [
    ...liveItems.map((item) => ({ ...item, _isLive: true })),
    ...filteredLinkItems.map((item) => ({ ...item, _isLive: false })),
  ], [liveItems, filteredLinkItems])

  // 关联列表列定义（useMemo 保持稳定引用，避免 Table 不必要的重渲染）
  const linkColumns = useMemo(() => [
    {
      title: '标题',
      dataIndex: ['display', 'title'],
      key: 'title',
      ellipsis: true,
      render: (text: string, record: TaskLink & { _isLive?: boolean }) => (
        <Space>
          {record._isLive && <Tag color="blue">实时</Tag>}
          <span>{text || '-'}</span>
        </Space>
      ),
    },
    {
      title: '价格',
      dataIndex: ['display', 'price'],
      key: 'price',
      width: 90,
      render: (v: number) => v != null ? `¥${v}` : '-',
    },
    {
      title: '卖家昵称',
      dataIndex: ['display', 'seller_nick'],
      key: 'seller_nick',
      width: 100,
      render: (v: string) => v || '-',
    },
    {
      title: '地区',
      dataIndex: ['display', 'region'],
      key: 'region',
      width: 80,
      render: (v: string) => v || '-',
    },
    {
      title: '发布时间',
      dataIndex: ['display', 'publish_time'],
      key: 'publish_time',
      width: 120,
      render: (v: string) => v || '-',
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 80,
      render: (v: string) => v || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: TaskLink & { _isLive?: boolean }) => (
        <Space size="small">
          {record.display?.url && (
            <Tooltip title="打开原帖">
              <Button
                size="small"
                type="link"
                icon={<EyeOutlined />}
                onClick={() => globalThis.open(record.display.url, '_blank')}
              />
            </Tooltip>
          )}
          {!record._isLive && record.link_id > 0 && (
            <Tooltip title="删除关联">
              <Button
                size="small"
                type="link"
                danger
                icon={<MinusCircleOutlined />}
                onClick={() => handleRemoveLink(record.link_id)}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ], [])

  const columns = [
    {
      title: '任务名',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Task) => (
        <Button type="link" onClick={() => navigate(`/tasks/${record.id}/edit`)} style={{ padding: 0 }}>{text}</Button>
      ),
    },
    { title: '关键词', dataIndex: 'keyword', key: 'keyword' },
    {
      title: '价格区间',
      key: 'price',
      render: (_: unknown, record: Task) => {
        const min = record.min_price ?? '不限'
        const max = record.max_price ?? '不限'
        return `¥${min} ~ ¥${max}`
      },
    },
    {
      title: '模式',
      dataIndex: 'mode',
      key: 'mode',
      render: (mode: string) => <Tag>{modeLabels[mode] || mode}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={statusColors[status]}>{statusLabels[status] || status}</Tag>,
    },
    {
      title: '采集周期',
      key: 'interval',
      width: 110,
      // 只读列：点击跳转 TaskEditor 修改，避免在列表行内直接编辑造成误操作
      render: (_: unknown, record: Task) => {
        // use_cron=true 显示 cron 表达式，否则显示秒数
        if (record.use_cron) {
          return (
            <Tooltip title={record.cron}>
              <Tag style={{ cursor: 'pointer' }} {...clickableProps(() => navigate(`/tasks/${record.id}/edit`))}>
                📅 {record.cron}
              </Tag>
            </Tooltip>
          )
        }
        return (
          <Tag
            style={{ cursor: 'pointer' }}
            {...clickableProps(() => navigate(`/tasks/${record.id}/edit`))}
          >
            ⏱ {record.interval_seconds ?? 60}秒
          </Tag>
        )
      },
    },
    {
      title: '下次搜索',
      key: 'next_search',
      width: 90,
      // 仅 running 任务参与倒计时；非 running 显示占位符
      render: (_: unknown, record: Task) => {
        if (record.status !== 'running') return <span style={{ color: 'var(--xh-text-tertiary)' }}>—</span>
        const remain = remainMap[record.id]
        if (remain == null) return <span style={{ color: 'var(--xh-text-tertiary)' }}>—</span>
        if (searchingIds.has(record.id)) {
          return <Tag color="processing">搜索中</Tag>
        }
        // 剩余 <10s 用警示色提示用户即将触发搜索
        return <span style={{ color: remain < 10 ? '#faad14' : 'var(--xh-text-secondary)' }}>{remain}s</span>
      },
    },
    {
      title: '沉默',
      key: 'silence',
      width: 100,
      render: (_: unknown, record: Task) => getSilenceTag(record),
    },
    {
      title: '关联',
      key: 'links',
      width: 80,
      render: (_: unknown, record: Task) => (
        <Button type="link" onClick={() => navigate(`/tasks/${record.id}`)} style={{ padding: 0 }}>
          <LinkOutlined /> {linkCounts[record.id] ?? '-'}
        </Button>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Task) => {
        const arm = armConfirm[record.id]
        // 该行已进入确认状态，显示"确认"和"取消"
        if (arm) {
          return (
            <Space size="small">
              <Button size="small" type="primary" danger onClick={() => executeArmConfirm(record.id)}>
                确认{arm.label}
              </Button>
              <Button size="small" onClick={() => cancelArmConfirm(record.id)}>
                取消
              </Button>
            </Space>
          )
        }
        // 正常状态：显示所有操作按钮
        return (
          <Space size="small">
            <Button size="small" icon={<EditOutlined />} onClick={() => navigate(`/tasks/${record.id}/edit`)}>
              编辑
            </Button>
            {record.status === 'running' ? (
              <Button size="small" icon={<PauseCircleOutlined />} onClick={() => handleAction(record.id, 'pause')}>
                暂停
              </Button>
            ) : (
              <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleAction(record.id, 'start')}>
                启动
              </Button>
            )}
            {/* 运行中或已暂停时显示停止按钮（危险操作，需行内确认） */}
            {(record.status === 'running' || record.status === 'paused') && (
              <Button size="small" danger icon={<StopOutlined />} onClick={() => doArmConfirm(record.id, 'stop', '停止', '停止后任务将不再运行')}>
                停止
              </Button>
            )}
            <Button size="small" icon={<CopyOutlined />} onClick={() => cloneTask(record)}>
              复制
            </Button>
            <Button size="small" onClick={() => saveAsTemplate(record)}>
              另存为模板
            </Button>
            <Button size="small" danger icon={<DeleteOutlined />} onClick={() => doArmConfirm(record.id, 'delete', '删除', '删除后不可恢复')}>
              删除
            </Button>
          </Space>
        )
      },
    },
  ]

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>任务管理</h2>
        <Space>
          <Button icon={<ThunderboltOutlined />} onClick={openAiParse}>
            智能建任务
          </Button>
          <Button icon={<AppstoreOutlined />} onClick={openTemplateMarket}>
            模板市场
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/tasks/new')}>
            新增任务
          </Button>
        </Space>
      </div>

      <Space style={{ marginBottom: 16 }}>
        {/* 全部启动：放在状态筛选前作为视觉焦点，使用品牌色渐变提升可发现性 */}
        <Tooltip title="一键启动所有非运行中的任务">
          <Button
            type="primary"
            className="xh-btn-brand"
            icon={<ThunderboltOutlined />}
            loading={startAllLoading}
            onClick={handleStartAll}
            disabled={tasks.length === 0}
          >
            全部启动
          </Button>
        </Tooltip>
        <Tooltip title="开启后，运行中的任务按各自采集周期自动触发实时搜索（串行队列，页面不可见时暂停）">
          <Space size={4}>
            <Switch
              checked={autoSearchEnabled}
              // aria-label 提升无障碍可访问性，读屏软件可正确朗读开关用途
              aria-label="自动实时搜索开关"
              // 关闭时调用 pauseAll 清空待搜索队列，避免队列中任务继续执行
              onChange={(v) => {
                setAutoSearchEnabled(v)
                if (!v) pauseAll()
              }}
              checkedChildren="自动"
              unCheckedChildren="手动"
            />
          </Space>
        </Tooltip>
        <span>状态筛选：</span>
        <Select
          value={statusFilter || undefined}
          onChange={(v) => { setStatusFilter(v || ''); setPage(1) }}
          style={{ width: 120 }}
          allowClear
          placeholder="全部"
          options={[
            { value: 'running', label: '运行中' },
            { value: 'paused', label: '已暂停' },
            { value: 'stopped', label: '已停止' },
          ]}
        />
        <Segmented
          value={viewMode}
          onChange={(v) => setViewMode(v as 'table' | 'card')}
          options={[
            { label: '表格', value: 'table' },
            { label: '卡片', value: 'card' },
          ]}
        />
      </Space>

      {/* 批量操作工具条 */}
      {selectedRowKeys.length > 0 && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={
            <Space>
              <span>已选 {selectedRowKeys.length} 项</span>
              <Button size="small" icon={<PauseCircleOutlined />} onClick={() => handleBatchAction('pause')}>暂停</Button>
              <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleBatchAction('resume')}>恢复</Button>
              <Button size="small" icon={<StopOutlined />} danger onClick={() => handleBatchAction('stop')}>停止</Button>
              <Button size="small" icon={<DeleteOutlined />} danger onClick={() => handleBatchAction('delete')}>删除</Button>
              <Button size="small" icon={<ClearOutlined />} onClick={() => setSelectedRowKeys([])}>清除选择</Button>
            </Space>
          }
        />
      )}

      {viewMode === 'table' ? (
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          loading={loading}
          rowSelection={{
            selectedRowKeys,
            onChange: setSelectedRowKeys,
          }}
          pagination={{
            current: page,
            total,
            pageSize,
            onChange: (p, ps) => {
              // 切换 pageSize 时重置到第1页
              if (ps !== pageSize) {
                setPageSize(ps)
                setPage(1)
              } else {
                setPage(p)
              }
            },
            showSizeChanger: true,
            pageSizeOptions: [20, 50, 100],
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      ) : (
        /* 卡片视图 */
        <Spin spinning={loading}>
          <Row gutter={[16, 16]}>
            {tasks.map((task) => {
              const arm = armConfirm[task.id]
              // 状态条颜色
              const statusColor = statusColors[task.status] || '#d9d9d9'
              // 提取到变量避免 JSX 内嵌套三元（S3358）
              const isRunning = task.status === 'running'
              const showStopBtn = isRunning || task.status === 'paused'
              const startPauseBtn = isRunning ? (
                <Button size="small" icon={<PauseCircleOutlined />} onClick={() => handleAction(task.id, 'pause')}>暂停</Button>
              ) : (
                <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleAction(task.id, 'start')}>启动</Button>
              )
              return (
                <Col key={task.id} xs={24} sm={12} md={8} lg={8}>
                  <Card
                    size="small"
                    style={{ borderTop: `3px solid ${statusColor}` }}
                    styles={{ body: { padding: '12px 16px' } }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 14 }}>
                      <Button type="link" onClick={() => navigate(`/tasks/${task.id}/edit`)} style={{ padding: 0, fontWeight: 600 }}>{task.name || task.keyword}</Button>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--xh-text-secondary)', marginBottom: 8 }}>
                      关键词：{task.keyword}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--xh-text-secondary)', marginBottom: 8 }}>
                      价格：¥{task.min_price ?? '不限'} ~ ¥{task.max_price ?? '不限'}
                    </div>
                    <Space size={4} wrap style={{ marginBottom: 8 }}>
                      <Tag>{modeLabels[task.mode] || task.mode}</Tag>
                      <Tag color={statusColors[task.status]}>{statusLabels[task.status] || task.status}</Tag>
                    </Space>
                    <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 8, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {arm ? (
                        <>
                          <Button size="small" type="primary" danger onClick={() => executeArmConfirm(task.id)}>
                            确认{arm.label}
                          </Button>
                          <Button size="small" onClick={() => cancelArmConfirm(task.id)}>取消</Button>
                        </>
                      ) : (
                        <>
                          <Button size="small" icon={<EditOutlined />} onClick={() => navigate(`/tasks/${task.id}/edit`)}>编辑</Button>
                          {startPauseBtn}
                          {showStopBtn && (
                            <Button size="small" danger icon={<StopOutlined />} onClick={() => doArmConfirm(task.id, 'stop', '停止', '停止后任务将不再运行')}>停止</Button>
                          )}
                          <Button size="small" icon={<CopyOutlined />} onClick={() => cloneTask(task)}>复制</Button>
                          <Button size="small" onClick={() => saveAsTemplate(task)}>另存为模板</Button>
                          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => doArmConfirm(task.id, 'delete', '删除', '删除后不可恢复')}>删除</Button>
                        </>
                      )}
                    </div>
                  </Card>
                </Col>
              )
            })}
          </Row>
          {tasks.length > 0 && (
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <Space>
                <Button disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</Button>
                <span>{page} / {Math.max(1, Math.ceil(total / pageSize))}</span>
                <Button disabled={page >= Math.ceil(total / pageSize)} onClick={() => setPage(page + 1)}>下一页</Button>
              </Space>
            </div>
          )}
        </Spin>
      )}

      {/* ===== 闲鱼内容关联面板 ===== */}
      <Collapse
        style={{ marginTop: 16 }}
        activeKey={linkPanelOpen ? ['link-panel'] : []}
        onChange={(keys) => setLinkPanelOpen(keys.includes('link-panel'))}
        items={[
          {
            key: 'link-panel',
            label: '🔗 闲鱼内容关联',
            children: (
              <>
                {/* 面板头部：任务选择 + 搜索 + 实时查询 */}
                <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Select
                    value={linkTaskId || undefined}
                    onChange={(v) => { setLinkTaskId(v); setLinkPage(1); setLiveItems([]) }}
                    placeholder="选择任务"
                    style={{ minWidth: 200 }}
                    showSearch
                    optionFilterProp="label"
                    options={tasks.map((t) => ({ value: t.id, label: t.name || t.keyword }))}
                  />
                  <Input.Search
                    placeholder="按 key 或标题搜索"
                    value={linkSearch}
                    onChange={(e) => setLinkSearch(e.target.value)}
                    style={{ width: 220 }}
                    allowClear
                  />
                  <Button
                    icon={<ReloadOutlined />}
                    loading={liveLoading}
                    onClick={handleLive}
                    disabled={!linkTaskId || searchingIds.has(linkTaskId)}
                  >
                    {searchingIds.has(linkTaskId) ? '自动搜索中...' : '实时查询'}
                  </Button>
                  {liveLoading && liveStage && (
                    <span style={{ color: '#1677ff', fontSize: 13 }}>
                      <Spin size="small" style={{ marginRight: 6 }} />
                      {liveStage}
                    </span>
                  )}
                  {/* 被过滤结果入口：仅当存在 filtered_out 时显示，避免无谓按钮 */}
                  {liveFilterSummary && liveFilterSummary.filtered_out?.length > 0 && (
                    <Button
                      size="small"
                      type="link"
                      onClick={() => setFilteredModalOpen(true)}
                    >
                      查看被过滤的 {liveFilterSummary.filtered_out.length} 条结果
                    </Button>
                  )}
                  <Button
                    icon={<PlusOutlined />}
                    onClick={() => setAddModalOpen(true)}
                    disabled={!linkTaskId}
                  >
                    手动添加
                  </Button>
                </div>

                {/* Tab 切换：商品 / 卖家 */}
                <Tabs
                  activeKey={linkType}
                  onChange={(key) => { setLinkType(key); setLinkPage(1); setLiveItems([]) }}
                  items={[
                    { key: 'item', label: '商品' },
                    { key: 'seller', label: '卖家' },
                  ]}
                />

                {/* 关联列表 */}
                <Table
                  columns={linkColumns}
                  dataSource={mergedLinkData}
                  rowKey={(record) => `${record._isLive ? 'live-' : ''}${record.link_id}-${record.link_key}`}
                  loading={linkLoading || liveLoading}
                  size="small"
                  pagination={{
                    current: linkPage,
                    total: linkTotal + liveItems.length,
                    pageSize: linkPageSize,
                    onChange: setLinkPage,
                    showTotal: (t) => `共 ${t} 条`,
                  }}
                />
              </>
            ),
          },
        ]}
      />

      {/* ===== 手动添加关联 Modal ===== */}
      <Modal
        title="手动添加关联"
        open={addModalOpen}
        onCancel={() => { setAddModalOpen(false); addForm.resetFields() }}
        onOk={handleAddLink}
        confirmLoading={addLoading}
        destroyOnHidden
      >
        <Form form={addForm} layout="vertical" initialValues={{ link_type: 'item' }}>
          <Form.Item name="link_type" label="类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select options={[{ value: 'item', label: '商品 ID' }, { value: 'seller', label: '卖家 ID' }]} />
          </Form.Item>
          <Form.Item name="link_key" label="Key" rules={[{ required: true, message: '请输入 Key' }]}>
            <Input placeholder="输入商品 ID 或卖家 ID" />
          </Form.Item>
          <Form.Item name="note" label="备注">
            <Input.TextArea rows={2} placeholder="可选备注" />
          </Form.Item>
        </Form>
      </Modal>

      {/* ===== 实时搜索被过滤结果 Modal ===== */}
      {/* 为什么单独 Modal：让用户看到被过滤掉的商品详情，判断是否需要调整任务的过滤条件 */}
      <Modal
        title="被过滤的结果"
        open={filteredModalOpen}
        onCancel={() => setFilteredModalOpen(false)}
        footer={null}
        width={900}
        destroyOnHidden
      >
        {liveFilterSummary && (
          <>
            {/* 过滤统计概览：raw → keyword/price/publish_days → final_total 链路 */}
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message={`原始 ${liveFilterSummary.raw} 条 → 关键词过滤 ${liveFilterSummary.keyword_skipped}、价格过滤 ${liveFilterSummary.price_skipped}、发布时间过滤 ${liveFilterSummary.publish_days_skipped} → 最终保留 ${liveFilterSummary.final_total} 条`}
            />
            <Table
              size="small"
              rowKey={(r, idx) => `${r.link_type}-${r.link_key}-${idx}`}
              dataSource={liveFilterSummary.filtered_out}
              pagination={{ pageSize: 10 }}
              columns={[
                {
                  title: '标题',
                  dataIndex: ['display', 'title'],
                  key: 'title',
                  ellipsis: true,
                  render: (v: string) => v || '-',
                },
                {
                  title: '价格',
                  dataIndex: ['display', 'price'],
                  key: 'price',
                  width: 90,
                  render: (v: number) => v != null ? `¥${v}` : '-',
                },
                {
                  title: '过滤原因',
                  dataIndex: 'filter_reason',
                  key: 'filter_reason',
                  width: 110,
                  render: (reason: string) => {
                    const colorMap: Record<string, string> = {
                      keyword: 'orange',
                      price: 'red',
                      publish_days: 'volcano',
                    }
                    const labelMap: Record<string, string> = {
                      keyword: '关键词',
                      price: '价格',
                      publish_days: '发布时间',
                    }
                    return <Tag color={colorMap[reason] || 'default'}>{labelMap[reason] || reason}</Tag>
                  },
                },
                {
                  title: '详情',
                  dataIndex: 'filter_detail',
                  key: 'filter_detail',
                  ellipsis: true,
                },
              ]}
            />
          </>
        )}
      </Modal>

      {/* ===== 智能建任务 Modal ===== */}
      <Modal
        title="✨ 智能建任务"
        open={aiModalOpen}
        onCancel={() => { if (!aiParsing) setAiModalOpen(false) }}
        footer={null}
        width={560}
        destroyOnHidden
      >
        <p style={{ color: 'var(--xh-text-secondary)', marginBottom: 16 }}>
          用一句话描述你的需求，AI 会帮你自动解析为关键词、价格区间、执行模式等
        </p>

        <Input.TextArea
          rows={3}
          placeholder="例：我想买 95 新索尼 A7M4 套机，预算 1.2w 以内，上海本地优先"
          value={aiInput}
          onChange={(e) => setAiInput(e.target.value)}
          disabled={aiParsing}
        />

        {/* 解析进度 */}
        {aiParsing && (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <Spin />
            <p style={{ marginTop: 8, color: 'var(--xh-text-tertiary)' }}>AI 正在解析你的需求...</p>
          </div>
        )}

        {/* 错误提示 */}
        {aiError && (
          <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(255, 77, 79, 0.08)', borderRadius: 6, color: '#ff4d4f', border: '1px solid rgba(255, 77, 79, 0.3)' }}>
            {aiError}
          </div>
        )}

        {/* 解析结果预览 */}
        {aiResult && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>✓ 解析结果（可继续微调）</div>
            <Card size="small" style={{ background: 'rgba(82, 196, 26, 0.08)', border: '1px solid rgba(82, 196, 26, 0.3)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: '6px 12px', fontSize: 13 }}>
                {aiResult.keyword && (<><span style={{ color: 'var(--xh-text-tertiary)' }}>关键词：</span><span style={{ fontWeight: 600 }}>{aiResult.keyword}</span></>)}
                {aiResult.name && (<><span style={{ color: 'var(--xh-text-tertiary)' }}>任务名：</span><span>{aiResult.name}</span></>)}
                {(aiResult.min_price != null || aiResult.max_price != null) && (
                  <><span style={{ color: 'var(--xh-text-tertiary)' }}>价格区间：</span><span>¥{aiResult.min_price ?? '不限'} ~ ¥{aiResult.max_price ?? '不限'}</span></>
                )}
                {aiResult.mode && (<><span style={{ color: 'var(--xh-text-tertiary)' }}>执行模式：</span><span>{modeLabels[aiResult.mode] || aiResult.mode}</span></>)}
              </div>
              {aiResult.reason && (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--xh-text-tertiary)', borderTop: '1px dashed var(--xh-border-secondary)', paddingTop: 6 }}>
                  💡 {String(aiResult.reason)}
                </div>
              )}
            </Card>
          </div>
        )}

        {/* 底部按钮 */}
        <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button onClick={() => setAiModalOpen(false)}>取消</Button>
          {!aiResult ? (
            <Button type="primary" loading={aiParsing} onClick={doAiParse} icon={<ThunderboltOutlined />}>
              开始解析
            </Button>
          ) : (
            <Button type="primary" onClick={applyAiResult}>
              用此结果继续 →
            </Button>
          )}
        </div>
      </Modal>

      {/* ===== 模板市场 Modal ===== */}
      <Modal
        title="📦 模板市场"
        open={tplModalOpen}
        onCancel={() => setTplModalOpen(false)}
        footer={null}
        width={680}
        destroyOnHidden
      >
        <p style={{ color: 'var(--xh-text-secondary)', marginBottom: 12 }}>
          选择模板一键创建任务，或从现有任务"另存为模板"
        </p>

        {/* 分类标签 + 搜索 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
          <Space wrap>
            {tplCategories.map((cat) => (
              <Tag
                key={cat}
                style={{ cursor: 'pointer', padding: '2px 10px' }}
                color={tplCategory === cat ? 'blue' : 'default'}
                {...clickableProps(() => setTplCategory(cat))}
              >
                {cat}
              </Tag>
            ))}
          </Space>
          <Input
            placeholder="搜索模板名称/关键词"
            value={tplSearch}
            onChange={(e) => setTplSearch(e.target.value)}
            style={{ width: 180 }}
            allowClear
            size="small"
          />
        </div>

        {/* 模板卡片网格 */}
        {(() => {
          // 模板列表三态：加载中 / 空 / 列表
          if (tplLoading) {
            return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
          }
          if (filteredTplItems.length === 0) {
            return <Empty description="暂无模板" />
          }
          return (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
            {filteredTplItems.map((tpl) => (
              <Card
                key={tpl.id}
                hoverable
                size="small"
                onClick={() => applyTemplate(tpl)}
                style={{ cursor: 'pointer', position: 'relative' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <span style={{ fontSize: 18 }}>{tpl.icon || '📋'}</span>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{tpl.name}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-secondary)', marginBottom: 4 }}>关键词：{tpl.keyword}</div>
                <div style={{ fontSize: 12, color: 'var(--xh-text-secondary)', marginBottom: 4 }}>
                  价格：¥{tpl.min_price ?? '不限'} ~ ¥{tpl.max_price ?? '不限'}
                </div>
                <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                  <Tag color={tpl.is_preset ? 'blue' : 'orange'} style={{ fontSize: 11 }}>
                    {tpl.is_preset ? '📋 预置' : '🔒 私有'}
                  </Tag>
                  {tpl.category && <Tag style={{ fontSize: 11 }}>🏷 {tpl.category}</Tag>}
                  <Tag style={{ fontSize: 11 }}>{modeLabels[tpl.mode] || tpl.mode}</Tag>
                </div>
                {/* 私有模板显示删除按钮 */}
                {!tpl.is_preset && (
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    style={{ position: 'absolute', top: 4, right: 4 }}
                    onClick={(e) => { e.stopPropagation(); deleteTemplate(tpl.id) }}
                  />
                )}
              </Card>
            ))}
          </div>
          )
        })()}
      </Modal>
    </div>
  )
}
