import { useEffect, useState, useCallback, useMemo, useRef, type MouseEvent, type KeyboardEvent } from 'react'
import { Card, Table, Tag, Select, Button, Input, Space, Spin, Tooltip, message, Pagination, Empty, Segmented, Row, Col, Alert, Switch, InputNumber } from 'antd'
import { ReloadOutlined, SearchOutlined, DeleteOutlined, LinkOutlined, AppstoreOutlined, UnorderedListOutlined, LoginOutlined, ThunderboltOutlined, ClockCircleOutlined, LoadingOutlined, CheckCircleOutlined, SettingOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { AxiosError } from 'axios'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import relativeTime from 'dayjs/plugin/relativeTime'
import { taskApi, taskLinkApi, type Task, type TaskLink, type FieldMap } from '../../api'
import { itemApi } from '../../api/item'
import LazyImage from '../../components/LazyImage'
import { useAutoRefresh, DEFAULT_INTERVAL, MIN_INTERVAL, MAX_INTERVAL } from '../../hooks/useAutoRefresh'
import { usePersistentState } from '../../hooks/usePersistentState'
import { useColumnConfig, type ColumnConfig } from '../../hooks/useColumnConfig'
import { useSearch } from '../../hooks/useSearch'
import { useSearchHistory } from '../../hooks/useSearchHistory'
import ColumnSettingsModal from '../Evaluations/components/ColumnSettingsModal'
import { ExportButton } from '../../components/ExportButton'

// 相对时间插件：用于 updated_at 列渲染"3分钟前"等格式
// dayjs 默认不包含 fromNow()，需 extend 插件并切换中文 locale
dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

// 点击商品链接的采集逻辑已移入组件内 handleTitleClick，
// 以便访问 message 和 loadItems 实现采集后刷新列表

type ViewMode = 'table' | 'card'

// 商品状态筛选的取值集合
// 抽取为 type alias 以便在 useState/usePersistentState/参数声明处复用，避免联合字面量散落多处
type SoldFilter = 'all' | 'onsale' | 'sold'

// 默认字段顺序：当后端未返回 field_map 时（如从 DB 加载的旧数据）使用此顺序
// 与后端 FIELD_METADATA 保持一致，确保无 field_map 时也能正常渲染
// updated_at 为 DB 顶层字段（非 display 内），追加在末尾作为商品最近更新时间
const DEFAULT_FIELD_ORDER: string[] = [
  'thumb_url', 'title', 'brand', 'price', 'seller_nick', 'seller_credit',
  'region', 'want_cnt', 'view_cnt', 'publish_time', 'is_sold', 'updated_at',
]

// 默认字段元数据：与后端 FIELD_METADATA 保持一致
// 当后端未返回 field_map 时使用此元数据渲染列
const DEFAULT_FIELD_META: FieldMap = {
  thumb_url: { label: '图片', type: 'image', width: 80 },
  title: { label: '标题', type: 'link' },
  brand: { label: '品牌', type: 'text', width: 100 },
  price: { label: '价格', type: 'price', width: 100 },
  seller_nick: { label: '卖家', type: 'seller', width: 140 },
  seller_credit: { label: '信用', type: 'tag', color: 'green', width: 80 },
  region: { label: '地区', type: 'text', width: 100 },
  want_cnt: { label: '想要', type: 'number', width: 70 },
  view_cnt: { label: '浏览', type: 'number', width: 70 },
  publish_time: { label: '发布时间', type: 'datetime', width: 160 },
  is_sold: { label: '状态', type: 'status', width: 80 },
  updated_at: { label: '更新时间', type: 'datetime', width: 120 },
}

// 从 axios 错误中提取后端返回的具体错误信息
function errDetail(err: unknown): string {
  const axiosErr = err as AxiosError<{ detail: string }>
  return axiosErr?.response?.data?.detail || String(err)
}

// 数据变化检测：对比新旧数据的价格/状态/想要数签名，返回变化的 link_key 集合
// 既用于高亮展示，也用于判断是否需要显示"数据已更新"提示
function detectChanges(
  newItems: TaskLink[],
  prevMap: Map<string, string>,
): { changedKeys: Set<string>; newMap: Map<string, string> } {
  const changedKeys = new Set<string>()
  const newMap = new Map<string, string>()
  for (const item of newItems) {
    const key = item.link_key
    if (!key) continue  // 跳过无 link_key 的异常行
    const sig = `${item.display?.price ?? ''}|${item.display?.is_sold ?? ''}|${item.display?.want_cnt ?? ''}`
    newMap.set(key, sig)
    const prevSig = prevMap.get(key)
    if (prevSig !== undefined && prevSig !== sig) {
      changedKeys.add(key)
    }
  }
  return { changedKeys, newMap }
}

/** 检测数据变化并触发高亮 + 提示（loadItems 和自动刷新共用） */
function applyChangeHighlight(
  newItems: TaskLink[],
  prevItemsRef: React.MutableRefObject<Map<string, string>>,
  setHighlightRows: React.Dispatch<React.SetStateAction<Set<string>>>,
  setShowUpdateToast: React.Dispatch<React.SetStateAction<boolean>>,
) {
  const { changedKeys, newMap } = detectChanges(newItems, prevItemsRef.current)
  prevItemsRef.current = newMap
  if (changedKeys.size > 0) {
    setHighlightRows(changedKeys)
    setShowUpdateToast(true)
    setTimeout(() => setHighlightRows(new Set()), 3000)
    setTimeout(() => setShowUpdateToast(false), 2000)
  }
}

// 实时搜索结果客户端过滤：后端 live 端点不接受 keyword/region/brand/sold_filter 参数，
// 前端在拿到全量结果后按当前筛选条件过滤，确保两种模式下参数一致生效
function applyClientFilters(
  rows: TaskLink[],
  search: string,
  region: string | undefined,
  brand: string | undefined,
  sold: SoldFilter,
): TaskLink[] {
  let filtered = rows
  if (search) {
    const kwLower = search.toLowerCase()
    filtered = filtered.filter(r => (r.display?.title || '').toLowerCase().includes(kwLower))
  }
  if (region) {
    filtered = filtered.filter(r => r.display?.region === region)
  }
  if (brand) {
    filtered = filtered.filter(r => r.display?.brand === brand)
  }
  // 状态过滤：onsale 时未售（含 undefined 兜底为在售）显示，sold 时仅已售显示
  // 与卡片渲染 {d?.is_sold && <已售>} 的 truthy 判定保持一致
  if (sold === 'onsale') {
    filtered = filtered.filter(r => !r.display?.is_sold)
  } else if (sold === 'sold') {
    filtered = filtered.filter(r => !!r.display?.is_sold)
  }
  return filtered
}

export default function ItemList() {
  const navigate = useNavigate()
  // 搜索历史：商品标题关键词持久化到 localStorage，供快速复用
  const { history, add, clear } = useSearchHistory({ namespace: 'items' })
  const [tasks, setTasks] = useState<Task[]>([])
  // 持久化 selectedTask：页面刷新或实时搜索无结果后恢复上次选择的任务
  // 避免每次加载都跳回第一个任务，保持用户操作一致性
  const [selectedTask, setSelectedTask] = usePersistentState<string | null>('xh.items.selectedTask', null)
  const [items, setItems] = useState<TaskLink[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = usePersistentState<number>('xh.items.pageSize', 20, {
    validator: (v): v is number => typeof v === 'number' && v > 0 && Number.isFinite(v),
  })
  const [loading, setLoading] = useState(false)
  const [liveMode, setLiveMode] = useState(false)
  const [liveLoading, setLiveLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = usePersistentState<ViewMode>('xh.items.viewMode', 'card', {
    validator: (v): v is ViewMode => v === 'table' || v === 'card',
  })
  const [regionFilter, setRegionFilter] = usePersistentState<string | undefined>('xh.items.regionFilter', undefined)
  // 品牌筛选：与地区筛选对齐，持久化以保留用户偏好
  const [brandFilter, setBrandFilter] = usePersistentState<string | undefined>('xh.items.brandFilter', undefined)
  // 状态筛选：默认仅看在售商品，避免已售商品干扰捡漏决策；持久化保留用户偏好
  const [soldFilter, setSoldFilter] = usePersistentState<SoldFilter>('xh.items.soldFilter', 'onsale', {
    validator: (v): v is SoldFilter => v === 'all' || v === 'onsale' || v === 'sold',
  })
  // 登录态/搜索令牌不可用标识：后端检测到身份 Cookie 缺失或 token 过期
  const [sessionExpired, setSessionExpired] = useState(false)
  // 字段元数据：后端返回的 field_map，描述每个字段的显示方式
  // 实时搜索时由后端返回，DB 加载时为 null（使用默认字段顺序）
  // 当接口字段变化时，前端根据此动态渲染列，无需修改代码
  const [fieldMap, setFieldMap] = useState<FieldMap | null>(null)

  // ===== 实时更新（触发式刷新）相关状态 =====
  // 使用 usePersistentState 自动持久化，刷新页面后恢复上次设置
  const [autoRefreshEnabled, setAutoRefreshEnabled] = usePersistentState<boolean>(
    'xh.items.autoRefreshEnabled', false,
    { validator: (v): v is boolean => typeof v === 'boolean' },
  )
  const [refreshInterval, setRefreshInterval] = usePersistentState<number>(
    'xh.items.refreshInterval', DEFAULT_INTERVAL,
    {
      validator: (v): v is number =>
        typeof v === 'number' && Number.isFinite(v) && v >= MIN_INTERVAL && v <= MAX_INTERVAL,
    },
  )
  // 实时搜索模式下的轮询间隔（默认 15 秒，独立于 DB 模式的间隔）
  // 实时搜索耗时较长，间隔太短会导致请求堆积
  const [liveRefreshInterval, setLiveRefreshInterval] = usePersistentState<number>(
    'xh.items.liveRefreshInterval', 15,
    {
      validator: (v): v is number =>
        typeof v === 'number' && Number.isFinite(v) && v >= MIN_INTERVAL && v <= MAX_INTERVAL,
    },
  )
  // 数据变化高亮：记录哪些行发生了变化（link_key → 变化字段集合）
  const [highlightRows, setHighlightRows] = useState<Set<string>>(new Set())
  // 上一次的数据快照，用于对比检测变化
  const prevItemsRef = useRef<Map<string, string>>(new Map())
  // 实时搜索原始结果：保存未过滤的全量数据，供实时模式下 search/region 变化时重新过滤
  const liveItemsRef = useRef<TaskLink[]>([])
  // "数据已更新"淡入提示的显示控制
  const [showUpdateToast, setShowUpdateToast] = useState(false)

  // 加载任务列表
  // 依赖数组为 []：仅在挂载时加载一次，避免重复请求
  // 使用 selectedTaskRef 读取最新值，避免闭包捕获初始 null 导致覆盖已恢复的任务
  useEffect(() => {
    taskApi.list({ limit: 200 }).then((res) => {
      const items = res.items || []
      setTasks(items)
      // 仅在未选择任务时自动选中第一个（首次访问或持久化值为 null）
      if (items.length > 0 && !selectedTaskRef.current) {
        setSelectedTask(items[0].id)
      }
    }).catch(() => message.error('加载任务列表失败'))
  }, [])

  // 切换任务时退出实时模式并清空旧数据，避免不同任务结果混在一起
  useEffect(() => {
    setLiveMode(false)
    setItems([])
    setTotal(0)
    setPage(1)
    setFieldMap(null)
    prevItemsRef.current = new Map()  // 切换任务时重置变化检测快照，避免跨任务误判
    liveItemsRef.current = []  // 清空实时搜索原始结果，避免跨任务残留
  }, [selectedTask])

  // 加载商品列表
  // 修复：把 keyword/region/brand 传给后端过滤，避免前端只过滤当前页导致跨页搜索失效
  const loadItems = useCallback(() => {
    if (!selectedTask) return
    setLoading(true)
    taskLinkApi.list(selectedTask, {
      type: 'item',
      limit: pageSize,
      offset: (page - 1) * pageSize,
      keyword: search || undefined,
      region: regionFilter || undefined,
      brand: brandFilter || undefined,
      // 'all' 时不传给后端，等价于不过滤，减少参数传输
      sold_filter: soldFilter === 'all' ? undefined : soldFilter,
    })
      .then((res) => {
        const newItems = res.items || []
        setItems(newItems)
        setTotal(res.total_for_type || 0)
        applyChangeHighlight(newItems, prevItemsRef, setHighlightRows, setShowUpdateToast)
        // 搜索成功且关键词非空时记录历史，供后续快速复用
        if (search && search.trim()) {
          add(search.trim())
        }
      })
      .catch((err) => {
        message.error(errDetail(err) || '加载商品列表失败')
        setItems([])
        setTotal(0)
      })
      .finally(() => setLoading(false))
  }, [selectedTask, page, pageSize, search, regionFilter, brandFilter, soldFilter, add])

  // 触发式实时刷新：SSE 事件驱动为主，定时兜底轮询为辅
  // DB 模式和实时模式都支持轮询，通过 liveModeRef 选择不同的数据源
  // 筛选条件变化（page/search/region）由 loadItems 的 useEffect 负责加载，此处不重复
  const liveModeRef = useRef(liveMode)
  liveModeRef.current = liveMode
  const searchRef = useRef(search)
  searchRef.current = search
  const regionFilterRef = useRef(regionFilter)
  regionFilterRef.current = regionFilter
  const brandFilterRef = useRef(brandFilter)
  brandFilterRef.current = brandFilter
  const soldFilterRef = useRef(soldFilter)
  soldFilterRef.current = soldFilter

  // 静默实时搜索：轮询回调专用，不显示进度提示和错误消息
  // 错误抛出由 useAutoRefresh 的重试机制处理（最多3次，间隔递增）
  const silentLiveRefresh = useCallback(async () => {
    if (!selectedTask) return
    const res = await taskLinkApi.live(selectedTask)
    if (!res) return
    const itemRows = (res.items || []).filter(
      (r: TaskLink) => r.link_type === 'item' || !r.link_type,
    )
    liveItemsRef.current = itemRows
    const filteredRows = applyClientFilters(
      itemRows,
      searchRef.current,
      regionFilterRef.current,
      brandFilterRef.current,
      soldFilterRef.current,
    )
    setItems(filteredRows)
    setTotal(filteredRows.length)
    applyChangeHighlight(filteredRows, prevItemsRef, setHighlightRows, setShowUpdateToast)
  }, [selectedTask])

  // 点击标题超链接：异步触发后端采集（更新 brand/price/is_sold 等字段），
  // 同时打开闲鱼原帖。采集完成后刷新列表展示最新数据。
  // 参照评估明细页 onTitleClick 的交互模式：loading 提示 + 成功/失败反馈
  // 接受 MouseEvent | KeyboardEvent：anchor 同时绑定 onClick 和 onKeyDown（Enter/Space），
  // 键盘事件同样需要 preventDefault 阻止默认行为（如空格滚动页面）
  const handleTitleClick = (e: MouseEvent | KeyboardEvent, itemId: string | undefined, url: string | undefined) => {
    e.preventDefault()
    if (!itemId) {
      if (url) globalThis.open(url, '_blank', 'noopener,noreferrer')
      return
    }
    const shortId = itemId.slice(0, 8)
    const hide = message.loading(`正在采集 ${shortId}...`, 0)
    // 传入 task_id：items 表无记录时后端用其回填 task_links.display
    // 不传则 task_links.display 不会被同步，采集的字段更新无法反映到列表
    itemApi.refresh(itemId, selectedTask || undefined).then((res) => {
      hide()
      message.success(`已更新商品信息：${shortId}...`)
      if (liveModeRef.current) {
        // 实时模式：用采集结果直接更新 liveItemsRef，不重新搜索
        // 为什么不用 silentLiveRefresh：重新搜索会返回搜索 API 数据，
        // 覆盖详情页采集到的最新字段（价格/标题/品牌等），导致只有图片更新
        const idx = liveItemsRef.current.findIndex((r) => r.link_key === itemId)
        if (idx >= 0) {
          const item = liveItemsRef.current[idx]
          const d = { ...(item.display || {}) }
          // 用采集结果覆盖非空字段（与后端 set_if_present 策略一致）
          if (res.title) d.title = res.title
          if (res.price > 0) d.price = res.price
          if (res.brand) d.brand = res.brand
          if (res.seller_id) d.seller_id = res.seller_id
          if (res.region) d.region = res.region
          if (res.thumb_url) d.thumb_url = res.thumb_url
          if (res.image_urls && res.image_urls.length > 0) d.image_urls = res.image_urls
          if (res.want_cnt > 0) d.want_cnt = res.want_cnt
          if (res.view_cnt > 0) d.view_cnt = res.view_cnt
          if (res.seller_nick) d.seller_nick = res.seller_nick
          if (res.seller_credit != null) d.seller_credit = String(res.seller_credit)
          if (res.publish_time) d.publish_time = res.publish_time
          d.is_sold = res.is_sold
          liveItemsRef.current[idx] = { ...item, display: d }
          // 重新应用客户端筛选条件
          const filteredRows = applyClientFilters(
            liveItemsRef.current,
            searchRef.current,
            regionFilterRef.current,
            brandFilterRef.current,
            soldFilterRef.current,
          )
          setItems(filteredRows)
          setTotal(filteredRows.length)
        }
      } else {
        // DB 模式：从数据库加载（task_links.display 已被后端同步更新）
        loadItems()
      }
    }).catch((err: unknown) => {
      hide()
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail || `采集失败：${shortId}...，请稍后重试`)
    })
    if (url) {
      globalThis.open(url, '_blank', 'noopener,noreferrer')
    }
  }

  const { lastRefreshAt, refreshing, nextRefreshAt, triggerRefresh } = useAutoRefresh({
    enabled: autoRefreshEnabled,
    // 实时模式使用独立的轮询间隔（默认15秒），DB模式使用 refreshInterval
    intervalSec: liveMode ? liveRefreshInterval : refreshInterval,
    // 移除 liveMode 暂停：实时模式下也轮询，仅在没有任务或正在加载时暂停
    paused: !selectedTask || loading || liveLoading,
    deps: [selectedTask, page, pageSize, search, regionFilter, brandFilter, soldFilter, liveMode],
    refresh: async () => {
      if (!selectedTask) return
      if (liveModeRef.current) {
        // 实时模式：静默调用 live API（SSE 流），不显示进度提示
        await silentLiveRefresh()
      } else {
        // DB 模式：静默读取 DB 数据
        await taskLinkApi.list(selectedTask, {
          type: 'item',
          limit: pageSize,
          offset: (page - 1) * pageSize,
          keyword: search || undefined,
          region: regionFilter || undefined,
          brand: brandFilter || undefined,
          sold_filter: soldFilter === 'all' ? undefined : soldFilter,
        }).then((res) => {
          const newItems = res.items || []
          setItems(newItems)
          setTotal(res.total_for_type || 0)
          applyChangeHighlight(newItems, prevItemsRef, setHighlightRows, setShowUpdateToast)
        })
      }
    },
  })

  // 兜底轮询倒计时：显示距下次定时刷新的秒数
  // 只依赖 nextRefreshAt，不依赖 refreshing（避免刷新过程中倒计时闪烁）
  const [countdownSec, setCountdownSec] = useState<number | null>(null)
  useEffect(() => {
    if (!nextRefreshAt) {
      setCountdownSec(null)
      return
    }
    const calc = () => Math.max(0, Math.ceil((nextRefreshAt - Date.now()) / 1000))
    setCountdownSec(calc())
    const timer = setInterval(() => {
      const left = calc()
      setCountdownSec(left)
    }, 1000)
    return () => clearInterval(timer)
  }, [nextRefreshAt])

  // SSE 订阅：监听 task.search_done 事件，Worker 搜索完成时自动刷新商品列表
  // 仅订阅当前选中任务的事件，避免无关任务触发不必要的刷新
  // 断线 3 秒后自动重连，页面不可见时不建立连接（节省资源）
  const sseRef = useRef<EventSource | null>(null)
  const selectedTaskRef = useRef(selectedTask)
  selectedTaskRef.current = selectedTask
  const triggerRefreshRef = useRef(triggerRefresh)
  triggerRefreshRef.current = triggerRefresh
  useEffect(() => {
    if (!autoRefreshEnabled || liveMode || !selectedTask) return

    // P2: 重连次数上限，超限后放弃 SSE 退化为纯轮询
    // 为什么 10 次：3s 间隔 × 10 = 30s，覆盖短暂网络抖动；超限说明服务端不可用
    const MAX_RECONNECT = 10
    let reconnectAttempts = 0
    // P1: 记录最后收到的事件 ID，断线重连时传给后端触发回放
    // 浏览器原生 EventSource 自动重连会携带 Last-Event-ID header，
    // 但手动 close + new 重建不会，需显式传递
    let lastEventId = 0

    const connect = () => {
      if (sseRef.current) sseRef.current.close()
      if (document.visibilityState !== 'visible') return
      if (reconnectAttempts >= MAX_RECONNECT) return

      // P1: 传递 last_event_id 启用断线回放，后端会推送此 ID 之后的所有事件
      const url = lastEventId > 0
        ? `/api/events/stream?last_event_id=${lastEventId}`
        : '/api/events/stream'
      const es = new EventSource(url)
      sseRef.current = es
      es.addEventListener('app_event', (e: MessageEvent) => {
        try {
          // 浏览器自动维护 lastEventId（对应 SSE 帧的 id 字段）
          lastEventId = Number.parseInt(e.lastEventId) || lastEventId
          const ev = JSON.parse(e.data)
          // 只处理当前任务的搜索完成事件
          if (ev.type === 'task.search_done' && ev.task_id === selectedTaskRef.current) {
            triggerRefreshRef.current()
          }
        } catch { /* 忽略解析错误 */ }
      })
      es.addEventListener('error', () => {
        // lastEventId 已在 app_event 中更新，此处直接使用
        try { es.close() } catch { /* */ }
        sseRef.current = null
        reconnectAttempts++
        // P2: 未超限且页面可见时重连，否则放弃（退化为纯轮询）
        if (reconnectAttempts < MAX_RECONNECT && document.visibilityState === 'visible') {
          setTimeout(connect, 3000)
        }
      })
    }

    // P0: 页面恢复可见时重建 SSE 连接
    // 为什么需要：页面不可见时 selectedTask 变化会触发 useEffect 重执行，
    // connect() 检测不可见直接 return，恢复可见后无机制触发 connect()
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible' && sseRef.current === null) {
        reconnectAttempts = 0  // 恢复可见时重置计数，给新一轮重连机会
        connect()
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    connect()
    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange)
      if (sseRef.current) {
        sseRef.current.close()
        sseRef.current = null
      }
    }
  }, [autoRefreshEnabled, liveMode, selectedTask])

  // 刷新数据源：非 liveMode 时先调用 refresh 端点实时搜索并写入 DB，再加载 DB 数据
  // 这样确保"刷新"按钮获取的是最新商品，而非 DB 中的旧缓存
  const handleRefresh = useCallback(() => {
    if (!selectedTask) return
    if (liveMode) {
      loadLive()
      return
    }
    setLoading(true)
    const progressTimer = setTimeout(() => {
      message.loading({ content: '正在从闲鱼刷新数据...', key: 'refresh', duration: 0 })
    }, 2000)
    taskLinkApi.refresh(selectedTask)
      .then((res) => {
        clearTimeout(progressTimer)
        message.destroy('refresh')
        if (res.saved > 0) {
          message.success(`已刷新 ${res.saved} 条商品`)
        } else {
          message.info('未获取到新商品，可尝试更换关键词')
        }
        // 刷新后重新加载 DB 数据（page 重置到第 1 页，确保看到最新结果）
        // 修复：之前 setPage(1) + loadItems() 会用旧 page 闭包加载一次，导致双重请求
        // 改为：page 变化时由 useEffect 自动触发；page 未变时手动调用
        if (page !== 1) {
          setPage(1)  // useEffect 会自动触发 loadItems
        } else {
          loadItems()
        }
      })
      .catch((err) => {
        clearTimeout(progressTimer)
        message.destroy('refresh')
        const detail = errDetail(err)
        if (detail.includes('登录已过期') || detail.includes('重新登录')) {
          setSessionExpired(true)
        } else if (detail.includes('超时')) {
          message.error('刷新超时，请稍后重试')
        } else {
          message.error(detail || '刷新失败')
        }
      })
      .finally(() => setLoading(false))
  }, [selectedTask, liveMode, page, loadItems])

  // 搜索防抖：loadItems 依赖变化（selectedTask/page/search/region 等）时 400ms 防抖触发
  // enabled: !liveMode 实时模式下跳过 DB 加载（实时模式由 loadLive/silentLiveRefresh 负责数据）
  // 退出实时模式时 enabled 从 false→true，触发一次 DB 数据加载
  useSearch({
    search: async () => { loadItems() },
    deps: [loadItems],
    enabled: !liveMode,
  })

  // 实时模式下搜索条件变化时在客户端重新过滤（不重新请求闲鱼 API）
  // liveItemsRef 保存了实时搜索的原始全量结果，每次筛选条件变化时从中重新过滤
  useEffect(() => {
    if (!liveMode) return
    const filtered = applyClientFilters(liveItemsRef.current, search, regionFilter, brandFilter, soldFilter)
    setItems(filtered)
    setTotal(filtered.length)
  }, [liveMode, search, regionFilter, brandFilter, soldFilter])

  // 实时搜索
  const loadLive = () => {
    if (!selectedTask) return
    setLiveLoading(true)
    setSessionExpired(false)  // 重置上次的状态
    // 进度提示：2 秒后显示"正在搜索闲鱼..."，更快的反馈
    const progressTimer = setTimeout(() => {
      message.loading({ content: '正在搜索闲鱼，请稍候...', key: 'live-search', duration: 0 })
    }, 2000)
    taskLinkApi.live(selectedTask)
      .then((res) => {
        clearTimeout(progressTimer)
        message.destroy('live-search')
        // 防御：SSE 流未收到 done 事件时 res 为 null（如后端异常关闭连接）
        if (!res) {
          setLiveMode(false)
          message.info('未搜索到匹配商品，可尝试更换关键词')
          return
        }
        setLiveMode(true)  // 进入实时模式：隐藏分页、禁用删除/刷新
        // 保存后端返回的字段元数据，用于动态渲染列
        // 当接口字段变化时，前端根据此自动调整列头，无需修改代码
        setFieldMap(res.field_map || null)
        // 防御性过滤：只取 item 类型行。seller 行在另一张表/分页渲染，
        // 避免与 item 行共用同一表格列时出现字段错位
        const itemRows = (res.items || []).filter((r: TaskLink) => r.link_type === 'item' || !r.link_type)
        // 保存原始结果供实时模式下 search/region/brand 变化时重新过滤
        liveItemsRef.current = itemRows
        // 应用前端筛选条件（实时搜索结果在客户端过滤，确保与 DB 模式参数一致）
        const filteredRows = applyClientFilters(itemRows, search, regionFilter, brandFilter, soldFilter)
        setItems(filteredRows)
        setTotal(filteredRows.length)
        const count = filteredRows.length
        if (count > 0) {
          message.success(`实时搜索到 ${count} 个商品`)
        } else if (res.session_expired) {
          // 后端检测到搜索令牌过期（API 响应包含 RGV587/TOKEN_ILLEGAL 等标志）
          setSessionExpired(true)
        } else {
          message.info('未搜索到匹配商品，可尝试更换关键词')
        }
      })
      .catch((err) => {
        clearTimeout(progressTimer)
        message.destroy('live-search')
        const detail = errDetail(err)
        // 401 表示搜索令牌临时过期
        if (detail.includes('令牌临时过期') || detail.includes('重新登录')) {
          setSessionExpired(true)
        } else if (err?.code === 'ECONNABORTED' || detail.includes('timeout')) {
          message.error('搜索超时，闲鱼页面加载缓慢或会话已失效，请稍后重试')
        } else {
          message.error(detail || '实时搜索失败')
        }
      })
      .finally(() => setLiveLoading(false))
  }

  // 删除关联（仅 DB 数据可删除，实时搜索结果 link_id=0 无需删除）
  const handleDelete = useCallback((linkId: number) => {
    if (!selectedTask || !linkId) return
    taskLinkApi.remove(selectedTask, linkId).then(() => {
      message.success('已删除')
      loadItems()
    }).catch((err) => message.error(errDetail(err) || '删除失败'))
  }, [selectedTask, loadItems])

  // 过滤已下推到后端（keyword/region/brand 参数），前端直接使用 items
  // 地区/品牌选项：实时模式下从原始全量结果提取，避免筛选后选项减少；
  // DB 模式下从当前页 items 提取（跨页场景需用户清空筛选后重新选择）
  const regionOptions = [...new Set(
    (liveMode ? liveItemsRef.current : items)
      .map((i) => i.display?.region).filter(Boolean)
  )].sort((a, b) => String(a).localeCompare(String(b)))
  const brandOptions = [...new Set(
    (liveMode ? liveItemsRef.current : items)
      .map((i) => i.display?.brand).filter(Boolean)
  )].sort((a, b) => String(a).localeCompare(String(b)))

  // ===== 列配置（拖拽排序 + 显示/隐藏，持久化到 localStorage） =====
  // 复用评估明细页的 useColumnConfig + ColumnSettingsModal，保持交互一致性
  const [columnConfigOpen, setColumnConfigOpen] = useState(false)
  // 列定义基于字段元数据动态生成：fieldMap 变化时（实时搜索 vs DB 模式）自动合并新列
  const columnDefinitions = useMemo<ColumnConfig[]>(() => {
    const meta = fieldMap || DEFAULT_FIELD_META
    const order = fieldMap ? Object.keys(fieldMap) : DEFAULT_FIELD_ORDER
    return order.map((key) => ({
      key,
      label: meta[key]?.label || key,
      // 标题列锁定不可隐藏：核心展示字段，隐藏后无法识别商品
      locked: key === 'title',
    }))
  }, [fieldMap])
  const {
    order: columnOrder,
    hidden: hiddenColumns,
    toggleHidden: toggleColumnHidden,
    moveColumn: moveColumnOrder,
    reset: resetColumnConfig,
    applyConfig: applyColumnConfig,
  } = useColumnConfig('xh.items.columns', columnDefinitions)

  // 动态生成列定义：根据后端返回的 field_map 自动调整列头和渲染方式
  // 当接口字段变化时，前端根据 field_map 自动调整列，无需修改代码
  // 避免"列头显示卖家但实际展示信用信息"等错位问题
  const columns = useMemo(() => {
    // 确定字段顺序：优先使用 fieldMap 的顺序，否则使用默认顺序
    const order = fieldMap ? Object.keys(fieldMap) : DEFAULT_FIELD_ORDER
    // 确定字段元数据：优先使用 fieldMap，否则使用默认元数据
    const meta: FieldMap = fieldMap || DEFAULT_FIELD_META

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const cols: any[] = []
    for (const field of order) {
      const m = meta[field]
      if (!m) continue

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const col: any = {
        title: m.label,
        dataIndex: 'display',
        key: field,
        width: m.width,
      }

      switch (m.type) {
        case 'image':
          col.render = (d: TaskLink['display']) => d?.thumb_url ? <LazyImage src={d.thumb_url} referrerPolicy="no-referrer" width={60} height={60} style={{ borderRadius: 6 }} /> : '—'
          break
        case 'link':
          col.render = (d: TaskLink['display'], record: TaskLink) => (
            <Tooltip title={d?.url ? '点击采集更新商品信息并打开原帖' : ''}>
              {d?.url ? (
                <a
                  role="button"
                  tabIndex={0}
                  onClick={(e) => handleTitleClick(e, record.link_key ?? '', d.url)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleTitleClick(e, record.link_key ?? '', d.url) }}
                  style={{ cursor: 'pointer' }}
                >{d?.title || '—'}</a>
              ) : (
                d?.title || '—'
              )}
            </Tooltip>
          )
          break
        case 'price':
          col.sorter = (a: TaskLink, b: TaskLink) => (a.display?.price || 0) - (b.display?.price || 0)
          col.render = (d: TaskLink['display']) => <span style={{ color: '#ff4d4f', fontWeight: 600 }}>¥{d?.price?.toFixed(2) ?? '—'}</span>
          break
        case 'seller':
          col.render = (d: TaskLink['display']) => {
            const name = d?.seller_nick || d?.seller_id
            const credit = d?.seller_credit
            // 卖家昵称与信用度分开：昵称一行，信用度用紧凑 Tag
            // 避免信用度文本与昵称混在一起造成"成色当卖家"的视觉错位
            return (
              <div>
                <div style={{ lineHeight: '20px' }}>{name || '—'}</div>
                {credit && <Tag color="green" style={{ fontSize: 11, lineHeight: '16px', padding: '0 4px', margin: 0 }}>{credit}</Tag>}
              </div>
            )
          }
          break
        case 'tag':
          col.render = (d: TaskLink['display']) => d?.seller_credit ? <Tag color={m.color || 'green'} style={{ fontSize: 11, lineHeight: '16px', padding: '0 4px', margin: 0 }}>{d.seller_credit}</Tag> : '—'
          break
        case 'text':
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          col.render = (d: TaskLink['display']) => (d as any)?.[field] || '—'
          break
        case 'number':
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          col.render = (d: TaskLink['display']) => (d as any)?.[field] ?? '—'
          break
        case 'datetime':
          col.defaultSortOrder = 'descend' as const
          // updated_at 在 record 顶层（DB 字段，记录行最近更新时间），
          // publish_time 在 display 内（采集字段，商品发布时间）。
          // 通过 field 区分数据来源，避免 datetime 列统一硬编码 publish_time
          if (field === 'updated_at') {
            col.sorter = (a: TaskLink, b: TaskLink) => {
              const ta = a.updated_at ? new Date(a.updated_at).getTime() : 0
              const tb = b.updated_at ? new Date(b.updated_at).getTime() : 0
              return tb - ta  // 降序：最新在前
            }
            // 相对时间便于快速判断数据新鲜度，Tooltip 保留绝对时间便于精确核对
            col.render = (_d: TaskLink['display'], record: TaskLink) => {
              if (!record.updated_at) return '—'
              const t = dayjs(record.updated_at)
              return <Tooltip title={t.format('YYYY-MM-DD HH:mm:ss')}>{t.fromNow()}</Tooltip>
            }
          } else {
            col.sorter = (a: TaskLink, b: TaskLink) => {
              const ta = a.display?.publish_time ? new Date(a.display.publish_time).getTime() : 0
              const tb = b.display?.publish_time ? new Date(b.display.publish_time).getTime() : 0
              return tb - ta  // 降序：最新在前
            }
            // 发布时间列只显示时间，不再回退渲染 seller_credit，
            // 避免"卖家"列与"发布时间"列错位显示同一字段
            col.render = (d: TaskLink['display']) => d?.publish_time ? new Date(d.publish_time).toLocaleString('zh-CN') : '—'
          }
          break
        case 'status':
          col.render = (d: TaskLink['display']) => d?.is_sold ? <Tag color="red">已售</Tag> : <Tag color="green">在售</Tag>
          break
        default:
          continue
      }

      cols.push(col)
    }

    // 应用列配置：按用户拖拽顺序重排 + 跳过隐藏列
    // 操作列不参与配置，始终追加在最后
    const visibleCols = applyColumnConfig(cols)
    visibleCols.push({
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: TaskLink) => (
        <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.link_id)} size="small" disabled={!record.link_id || liveMode} />
      ),
    })

    return visibleCols
  }, [fieldMap, liveMode, handleDelete, applyColumnConfig])

  // 提取嵌套模板字符串为变量：避免在模板字符串内再嵌套模板字符串，提升可读性
  // 同时区分实时模式与 DB 模式下的轮询间隔展示文案
  const intervalLabel = liveMode ? `实时模式 ${liveRefreshInterval}秒` : `DB模式 ${refreshInterval}秒`

  return (
    <div className="page-container">
      {/* 登录态异常提示：醒目居中显示在搜索区域上方 */}
      {sessionExpired && (
        <Alert
          type="warning"
          showIcon
          banner
          message="闲鱼登录态不可用，实时搜索暂时不可用"
          description="当前浏览器缺少闲鱼搜索所需的登录 Cookie，或搜索临时令牌已过期。请重新登录闲鱼后再试。"
          action={
            <Button
              icon={<LoginOutlined />}
              onClick={() => navigate(`/?redirect=${encodeURIComponent('/items')}`)}
            >
              重新登录
            </Button>
          }
          style={{ marginBottom: 16, borderRadius: 8 }}
        />
      )}
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>选择任务：</span>
          <Select
            style={{ width: 300 }}
            placeholder="请选择任务"
            value={selectedTask || undefined}
            onChange={(v) => { setSelectedTask(v); setPage(1); setLiveMode(false) }}
            options={tasks.map((t) => ({ label: `${t.name}（${t.keyword}）`, value: t.id }))}
          />
          <Button
            type={liveMode ? 'primary' : 'default'}
            icon={<SearchOutlined />}
            loading={liveLoading}
            onClick={loadLive}
            disabled={!selectedTask}
          >
            实时搜索
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            loading={loading || liveLoading || refreshing}
            disabled={!selectedTask}
          >
            刷新
          </Button>
          <Input
            placeholder="搜索标题"
            prefix={<SearchOutlined />}
            style={{ width: 200 }}
            value={search}
            // 搜索条件变化时重置到第 1 页，避免看的是搜索结果的中间页
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            allowClear
          />
          <Select
            placeholder="筛选地区"
            style={{ width: 140 }}
            allowClear
            value={regionFilter}
            onChange={(v) => { setRegionFilter(v); setPage(1) }}
            options={regionOptions.map((r) => ({ label: r, value: r }))}
          />
          <Select
            placeholder="筛选品牌"
            style={{ width: 140 }}
            allowClear
            value={brandFilter}
            onChange={(v) => { setBrandFilter(v); setPage(1) }}
            options={brandOptions.map((b) => ({ label: b, value: b }))}
          />
          {/* 状态筛选：固定三档选项，与地区/品牌筛选并列排放 */}
          <Select
            placeholder="状态筛选"
            style={{ width: 100 }}
            value={soldFilter}
            onChange={(v) => { setSoldFilter(v); setPage(1) }}
            options={[
              { label: '全部', value: 'all' },
              { label: '在售', value: 'onsale' },
              { label: '已售', value: 'sold' },
            ]}
          />
          {/* 实时更新开关 + 轮询间隔配置
              DB 模式和实时模式各自有独立的间隔设置 */}
          <Tooltip title={`自动轮询（设置已保存：${autoRefreshEnabled ? '开' : '关'}）。${intervalLabel}轮询一次`}>
            <Space size={4}>
              <ThunderboltOutlined style={{ color: autoRefreshEnabled ? '#1677ff' : undefined }} />
              <Switch
                checked={autoRefreshEnabled}
                onChange={setAutoRefreshEnabled}
                size="small"
              />
            </Space>
          </Tooltip>
          {autoRefreshEnabled && (
            <Tooltip title={`${liveMode ? '实时搜索' : 'DB'}轮询间隔（${MIN_INTERVAL}-${MAX_INTERVAL}秒），设置已自动保存`}>
              <Space size={4}>
                <InputNumber
                  size="small"
                  min={MIN_INTERVAL}
                  max={MAX_INTERVAL}
                  value={liveMode ? liveRefreshInterval : refreshInterval}
                  onChange={(v) => {
                    const val = v || DEFAULT_INTERVAL
                    if (liveMode) setLiveRefreshInterval(val)
                    else setRefreshInterval(val)
                  }}
                  addonAfter="秒"
                  style={{ width: 90 }}
                />
              </Space>
            </Tooltip>
          )}
          {/* 上次刷新时间已移至商品列表 Card 顶部的醒目指示器中，避免工具栏信息冗余 */}
          <Button type="link" icon={<LinkOutlined />} onClick={() => navigate('/tasks')}>
            管理任务
          </Button>
          {/* 列配置：拖拽调整列顺序 + 显示/隐藏字段，配置持久化到 localStorage（仅表格模式生效） */}
          <Button
            icon={<SettingOutlined />}
            onClick={() => setColumnConfigOpen(true)}
            disabled={viewMode !== 'table'}
          >
            列配置
          </Button>
          {/* O-05-26 数据导出：按当前选中任务过滤导出商品 CSV */}
          <ExportButton dataset="items" params={{ task_id: selectedTask || undefined }} />
          <div style={{ marginLeft: 'auto' }}>
            <Segmented
              value={viewMode}
              onChange={(v) => setViewMode(v as ViewMode)}
              options={[
                { label: '', value: 'card', icon: <AppstoreOutlined /> },
                { label: '', value: 'table', icon: <UnorderedListOutlined /> },
              ]}
            />
          </div>
        </Space>
        {/* 搜索历史小药丸：点击复用历史关键词，避免重复输入 */}
        {history.length > 0 && (
          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
            {history.map((kw) => (
              <Tag
                key={kw}
                onClick={() => { setSearch(kw); setPage(1) }}
                style={{ cursor: 'pointer', margin: 0, fontSize: 11 }}
              >
                {kw}
              </Tag>
            ))}
            <Button type="link" size="small" onClick={clear} style={{ padding: 0, fontSize: 11 }}>
              清空
            </Button>
          </div>
        )}
      </Card>

      <Card style={{ position: 'relative' }}>
        {/* 实时更新指示器：自动刷新启用时始终显示
            DB 模式和实时模式都显示轮询状态和倒计时 */}
        {autoRefreshEnabled && selectedTask && (
          <div className={`xh-refresh-indicator ${refreshing ? 'xh-refresh-indicator--active' : ''}`}>
            {/* 顶部进度条：刷新中时显示 indeterminate 动画条 */}
            {refreshing && <div className="xh-refresh-progress-bar" />}
            <div className="xh-refresh-indicator__content">
              {(() => {
                // 刷新状态三态：刷新中 / 已就绪 / 等待中
                if (refreshing) {
                  return (
                    <>
                      <LoadingOutlined spin style={{ color: '#1677ff' }} />
                      <span className="xh-refresh-indicator__text" style={{ color: '#1677ff' }}>
                        {liveMode ? '正在实时搜索...' : '正在获取最新数据...'}
                      </span>
                    </>
                  )
                }
                if (lastRefreshAt) {
                  return (
                    <>
                      <CheckCircleOutlined style={{ color: '#52c41a' }} />
                      <span className="xh-refresh-indicator__text">
                        {liveMode ? '实时' : 'DB'}已更新于 {new Date(lastRefreshAt).toLocaleTimeString('zh-CN')}
                      </span>
                      {countdownSec !== null && countdownSec > 0 && (
                        <span className="xh-refresh-indicator__countdown">
                          · {countdownSec}s 后{liveMode ? '实时搜索' : '兜底刷新'}
                        </span>
                      )}
                    </>
                  )
                }
                return (
                  <>
                    <ClockCircleOutlined style={{ color: '#faad14' }} />
                    <span className="xh-refresh-indicator__text">
                      等待{liveMode ? '实时搜索' : '数据更新'}...
                    </span>
                  </>
                )
              })()}
            </div>
          </div>
        )}
        {/* "数据已更新"淡入提示：检测到数据变化时短暂显示 */}
        {showUpdateToast && (
          <div style={{
            position: 'absolute', top: 8, right: 16, zIndex: 10,
            background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6,
            padding: '4px 12px', fontSize: 12, color: '#52c41a',
            animation: 'xh-fade-in 0.3s ease',
          }}>
            数据已更新
          </div>
        )}
        <Spin spinning={loading || liveLoading}>
          {(() => {
            // 列表展示：空数据 / 表格 / 卡片
            if (items.length === 0) {
              return <Empty description={selectedTask ? '暂无商品数据，可尝试实时搜索' : '请先选择任务'} />
            }
            if (viewMode === 'table') {
              return (
                <>
                  <Table
                    columns={columns}
                    dataSource={items}
                    rowKey="link_id"
                pagination={false}
                size="middle"
                scroll={{ x: 1000 }}
                rowClassName={(record) => highlightRows.has(record.link_key) ? 'xh-row-highlight' : ''}
              />
              {!liveMode && (
                <div style={{ marginTop: 16, textAlign: 'right' }}>
                  <Pagination
                    current={page}
                    pageSize={pageSize}
                    total={total}
                    showSizeChanger
                    showTotal={(t) => `共 ${t} 条`}
                    pageSizeOptions={[20, 50, 100]}
                    onChange={(p, ps) => { setPage(p); setPageSize(ps) }}
                  />
                </div>
              )}
                </>
              )
            }
            return (
              <>
              {/* 卡片网格视图：大图 + 价格 + 标题 + 元信息 */}
              <Row gutter={[16, 16]}>
                {items.map((item) => {
                  const d = item.display
                  return (
                    <Col xs={12} sm={8} md={6} lg={4} xl={4} key={item.link_id}>
                      <Tooltip
                        title={
                          <div style={{ maxWidth: 300 }}>
                            <div style={{ fontWeight: 600, marginBottom: 4 }}>{d?.title || '—'}</div>
                            <div style={{ color: '#ff4d4f' }}>¥{d?.price?.toFixed(2) ?? '—'}</div>
                            <div style={{ color: 'var(--xh-text-tertiary)', fontSize: 12, marginTop: 4 }}>
                              {d?.brand ? `${d.brand} · ` : ''}{d?.region || '—'} · 想要 {d?.want_cnt ?? 0} · 浏览 {d?.view_cnt ?? 0} · {d?.seller_nick || d?.seller_id || '—'}
                              {d?.seller_credit && <span style={{ color: '#52c41a', marginLeft: 4 }}>[{d.seller_credit}]</span>}
                            </div>
                            {d?.publish_time && (
                              <div style={{ color: 'var(--xh-text-tertiary)', fontSize: 12 }}>
                                发布: {new Date(d.publish_time).toLocaleString('zh-CN')}
                              </div>
                            )}
                          </div>
                        }
                        placement="right"
                        mouseEnterDelay={0.3}
                      >
                      <Card
                        className="item-card"
                        size="small"
                        styles={{ body: { padding: 12 } }}
                        style={highlightRows.has(item.link_key) ? {
                          boxShadow: '0 0 0 2px #52c41a',
                          borderRadius: 8,
                          transition: 'box-shadow 0.3s ease',
                        } : undefined}
                        cover={
                          <div className="item-card-image">
                            {d?.thumb_url ? (
                              <LazyImage
                                src={d.thumb_url}
                                alt={d?.title || '商品图片'}
                                referrerPolicy="no-referrer"
                                style={{ width: '100%', height: '100%' }}
                              />
                            ) : (
                              <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--xh-text-quaternary)', fontSize: 24 }}>🖼️</div>
                            )}
                            {d?.is_sold && <span className="item-card-sold-badge">已售</span>}
                          </div>
                        }
                        actions={[
                          d?.url ? (
                            <a
                              key="link"
                              role="button"
                              tabIndex={0}
                              onClick={(e) => handleTitleClick(e, item.link_key ?? '', d.url)}
                              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleTitleClick(e, item.link_key ?? '', d.url) }}
                              title="采集更新并打开原帖"
                              style={{ cursor: 'pointer' }}
                            >
                              <LinkOutlined />
                            </a>
                          ) : <span key="nolink" style={{ color: '#d9d9d9' }}><LinkOutlined /></span>,
                          <DeleteOutlined key="delete" onClick={() => handleDelete(item.link_id)} style={{ color: item.link_id ? '#ff4d4f' : '#d9d9d9' }} />,
                        ]}
                      >
                        <div className="item-card-price">¥{d?.price?.toFixed(2) ?? '—'}</div>
                        <div className="item-card-title" title={d?.title}>
                          {d?.title || '—'}
                        </div>
                        <div className="item-card-meta">
                          {d?.brand && <span>{d.brand}</span>}
                          <span>{d?.region || '—'}</span>
                          <span>想要 {d?.want_cnt ?? 0}</span>
                          <span>浏览 {d?.view_cnt ?? 0}</span>
                        </div>
                      </Card>
                      </Tooltip>
                    </Col>
                  )
                })}
              </Row>
              {!liveMode && (
                <div style={{ marginTop: 16, textAlign: 'right' }}>
                  <Pagination
                    current={page}
                    pageSize={pageSize}
                    total={total}
                    showSizeChanger
                    showTotal={(t) => `共 ${t} 条`}
                    pageSizeOptions={[20, 50, 100]}
                    onChange={(p, ps) => { setPage(p); setPageSize(ps) }}
                  />
                </div>
              )}
              </>
            )
          })()}
        </Spin>
      </Card>

      {/* 列配置弹窗：拖拽调整列顺序 + 显示/隐藏字段 */}
      <ColumnSettingsModal
        open={columnConfigOpen}
        onClose={() => setColumnConfigOpen(false)}
        definitions={columnDefinitions}
        order={columnOrder}
        hidden={hiddenColumns}
        onToggleHidden={toggleColumnHidden}
        onMove={moveColumnOrder}
        onReset={resetColumnConfig}
      />
    </div>
  )
}
