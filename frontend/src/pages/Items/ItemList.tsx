import { useEffect, useState, useCallback, useMemo } from 'react'
import { Card, Table, Tag, Select, Button, Input, Space, Spin, Tooltip, message, Pagination, Empty, Segmented, Row, Col, Alert } from 'antd'
import { ReloadOutlined, SearchOutlined, DeleteOutlined, LinkOutlined, AppstoreOutlined, UnorderedListOutlined, LoginOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { AxiosError } from 'axios'
import { taskApi, taskLinkApi, type Task, type TaskLink, type FieldMap, type FieldMeta } from '../../api'
import LazyImage from '../../components/LazyImage'

type ViewMode = 'table' | 'card'

// 默认字段顺序：当后端未返回 field_map 时（如从 DB 加载的旧数据）使用此顺序
// 与后端 FIELD_METADATA 保持一致，确保无 field_map 时也能正常渲染
const DEFAULT_FIELD_ORDER: string[] = [
  'thumb_url', 'title', 'price', 'seller_nick', 'seller_credit',
  'region', 'want_cnt', 'publish_time', 'is_sold',
]

// 默认字段元数据：与后端 FIELD_METADATA 保持一致
// 当后端未返回 field_map 时使用此元数据渲染列
const DEFAULT_FIELD_META: FieldMap = {
  thumb_url: { label: '图片', type: 'image', width: 80 },
  title: { label: '标题', type: 'link' },
  price: { label: '价格', type: 'price', width: 100 },
  seller_nick: { label: '卖家', type: 'seller', width: 140 },
  seller_credit: { label: '信用', type: 'tag', color: 'green', width: 80 },
  region: { label: '地区', type: 'text', width: 100 },
  want_cnt: { label: '想要', type: 'number', width: 70 },
  publish_time: { label: '发布时间', type: 'datetime', width: 160 },
  is_sold: { label: '状态', type: 'status', width: 80 },
}

// 从 axios 错误中提取后端返回的具体错误信息
function errDetail(err: unknown): string {
  const axiosErr = err as AxiosError<{ detail: string }>
  return axiosErr?.response?.data?.detail || String(err)
}

export default function ItemList() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [selectedTask, setSelectedTask] = useState<string | null>(null)
  const [items, setItems] = useState<TaskLink[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [liveMode, setLiveMode] = useState(false)
  const [liveLoading, setLiveLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('card')
  const [regionFilter, setRegionFilter] = useState<string | undefined>(undefined)
  // 登录态/搜索令牌不可用标识：后端检测到身份 Cookie 缺失或 token 过期
  const [sessionExpired, setSessionExpired] = useState(false)
  // 字段元数据：后端返回的 field_map，描述每个字段的显示方式
  // 实时搜索时由后端返回，DB 加载时为 null（使用默认字段顺序）
  // 当接口字段变化时，前端根据此动态渲染列，无需修改代码
  const [fieldMap, setFieldMap] = useState<FieldMap | null>(null)

  // 加载任务列表
  useEffect(() => {
    taskApi.list({ limit: 200 }).then((res) => {
      setTasks(res.items || [])
      if (res.items.length > 0 && !selectedTask) {
        setSelectedTask(res.items[0].id)
      }
    }).catch(() => message.error('加载任务列表失败'))
  }, [])

  // 切换任务时退出实时模式并清空旧数据，避免不同任务结果混在一起
  useEffect(() => {
    setLiveMode(false)
    setItems([])
    setTotal(0)
    setPage(1)
    setFieldMap(null)  // 切换任务时清除字段元数据，避免上一个任务的列定义残留
  }, [selectedTask])

  // 加载商品列表
  // 修复：把 keyword/region 传给后端过滤，避免前端只过滤当前页导致跨页搜索失效
  const loadItems = useCallback(() => {
    if (!selectedTask) return
    setLoading(true)
    taskLinkApi.list(selectedTask, {
      type: 'item',
      limit: pageSize,
      offset: (page - 1) * pageSize,
      keyword: search || undefined,
      region: regionFilter || undefined,
    })
      .then((res) => {
        setItems(res.items || [])
        setTotal(res.total_for_type || 0)
      })
      .catch((err) => {
        message.error(errDetail(err) || '加载商品列表失败')
        setItems([])
        setTotal(0)
      })
      .finally(() => setLoading(false))
  }, [selectedTask, page, pageSize, search, regionFilter])

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
  }, [selectedTask, liveMode, loadItems])

  useEffect(() => {
    if (!liveMode) loadItems()
  }, [liveMode, loadItems])

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
        setLiveMode(true)  // 进入实时模式：隐藏分页、禁用删除/刷新
        // 保存后端返回的字段元数据，用于动态渲染列
        // 当接口字段变化时，前端根据此自动调整列头，无需修改代码
        setFieldMap(res.field_map || null)
        // 防御性过滤：只取 item 类型行。seller 行在另一张表/分页渲染，
        // 避免与 item 行共用同一表格列时出现字段错位
        const itemRows = (res.items || []).filter((r: TaskLink) => r.link_type === 'item' || !r.link_type)
        setItems(itemRows)
        setTotal(itemRows.length)
        const count = itemRows.length
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
  const handleDelete = (linkId: number) => {
    if (!selectedTask || !linkId) return
    taskLinkApi.remove(selectedTask, linkId).then(() => {
      message.success('已删除')
      loadItems()
    }).catch((err) => message.error(errDetail(err) || '删除失败'))
  }

  // 过滤已下推到后端（keyword/region 参数），前端直接使用 items
  // 地区选项从当前页数据提取（跨页场景需用户清空地区筛选后重新选择）
  const regionOptions = [...new Set(items.map((i) => i.display?.region).filter(Boolean))].sort()

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
          col.render = (d: TaskLink['display']) => (
            <Tooltip title={d?.url ? '点击打开原帖' : ''}>
              {d?.url ? (
                <a href={d.url} target="_blank" rel="noreferrer">{d?.title || '—'}</a>
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
          col.sorter = (a: TaskLink, b: TaskLink) => {
            const ta = a.display?.publish_time ? new Date(a.display.publish_time).getTime() : 0
            const tb = b.display?.publish_time ? new Date(b.display.publish_time).getTime() : 0
            return tb - ta  // 降序：最新在前
          }
          // 发布时间列只显示时间，不再回退渲染 seller_credit，
          // 避免"卖家"列与"发布时间"列错位显示同一字段
          col.render = (d: TaskLink['display']) => d?.publish_time ? new Date(d.publish_time).toLocaleString('zh-CN') : '—'
          break
        case 'status':
          col.render = (d: TaskLink['display']) => d?.is_sold ? <Tag color="red">已售</Tag> : <Tag color="green">在售</Tag>
          break
        default:
          continue
      }

      cols.push(col)
    }

    // 添加操作列（始终显示）
    cols.push({
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: TaskLink) => (
        <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.link_id)} size="small" disabled={!record.link_id || liveMode} />
      ),
    })

    return cols
  }, [fieldMap, liveMode])

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
            loading={loading || liveLoading}
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
          <Button type="link" icon={<LinkOutlined />} onClick={() => navigate('/tasks')}>
            管理任务
          </Button>
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
      </Card>

      <Card>
        <Spin spinning={loading || liveLoading}>
          {items.length === 0 ? (
            <Empty description={selectedTask ? '暂无商品数据，可尝试实时搜索' : '请先选择任务'} />
          ) : viewMode === 'table' ? (
            <>
              <Table
                columns={columns}
                dataSource={items}
                rowKey="link_id"
                pagination={false}
                size="middle"
                scroll={{ x: 1000 }}
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
          ) : (
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
                              {d?.region || '—'} · 想要 {d?.want_cnt ?? 0} · {d?.seller_nick || d?.seller_id || '—'}
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
                        bodyStyle={{ padding: 12 }}
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
                            <a key="link" href={d.url} target="_blank" rel="noreferrer" title="打开原帖">
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
                          <span>{d?.region || '—'}</span>
                          <span>想要 {d?.want_cnt ?? 0}</span>
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
          )}
        </Spin>
      </Card>
    </div>
  )
}
