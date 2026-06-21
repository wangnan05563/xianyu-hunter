import { useEffect, useState, useCallback, useRef } from 'react'
import { Card, Table, Tag, Select, Button, Input, Space, Spin, Image, Tooltip, message, Pagination, Empty, Segmented, Row, Col, Alert } from 'antd'
import { ReloadOutlined, SearchOutlined, DeleteOutlined, LinkOutlined, AppstoreOutlined, UnorderedListOutlined, LoginOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { AxiosError } from 'axios'
import { taskApi, taskLinkApi, type Task, type TaskLink } from '../../api'
import LazyImage from '../../components/LazyImage'

type ViewMode = 'table' | 'card'

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
  // Cookie 失效标识：实时搜索返回 0 结果且后端检测到会话过期
  const [sessionExpired, setSessionExpired] = useState(false)

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
  }, [selectedTask])

  // 加载商品列表
  const loadItems = useCallback(() => {
    if (!selectedTask) return
    setLoading(true)
    taskLinkApi.list(selectedTask, { type: 'item', limit: pageSize, offset: (page - 1) * pageSize })
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
  }, [selectedTask, page, pageSize])

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
          message.warning('未获取到新商品，可能是闲鱼会话失效或无匹配结果')
        }
        // 刷新后重新加载 DB 数据（page 重置到第 1 页，确保看到最新结果）
        setPage(1)
        loadItems()
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
        setItems(res.items || [])
        setTotal(res.items?.length || 0)
        const count = res.items?.length || 0
        if (count > 0) {
          message.success(`实时搜索到 ${count} 个商品`)
        } else if (res.session_expired) {
          // 后端检测到 Cookie 失效（API 响应被捕获但解析为空，或 RGV587_ERROR）
          setSessionExpired(true)
        } else {
          message.warning('未搜索到商品，可能是闲鱼会话失效或无匹配结果')
        }
      })
      .catch((err) => {
        clearTimeout(progressTimer)
        message.destroy('live-search')
        const detail = errDetail(err)
        // 401 表示闲鱼登录已过期
        if (detail.includes('登录已过期') || detail.includes('重新登录')) {
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
    }).catch(() => message.error('删除失败'))
  }

  // 过滤搜索 + 地区筛选
  const filteredItems = items.filter((i) => {
    const matchSearch = !search || i.display?.title?.toLowerCase().includes(search.toLowerCase())
    const matchRegion = !regionFilter || i.display?.region === regionFilter
    return matchSearch && matchRegion
  })

  // 从当前数据提取地区选项（去重）
  const regionOptions = [...new Set(items.map((i) => i.display?.region).filter(Boolean))].sort()

  const columns = [
    {
      title: '图片',
      dataIndex: 'display',
      key: 'thumb',
      width: 80,
      render: (d: TaskLink['display']) => d?.thumb_url ? <LazyImage src={d.thumb_url} referrerPolicy="no-referrer" width={60} height={60} style={{ borderRadius: 6 }} /> : '—',
    },
    {
      title: '标题',
      dataIndex: 'display',
      key: 'title',
      render: (d: TaskLink['display']) => (
        <Tooltip title={d?.url ? '点击打开原帖' : ''}>
          {d?.url ? (
            <a href={d.url} target="_blank" rel="noreferrer">{d?.title || '—'}</a>
          ) : (
            d?.title || '—'
          )}
        </Tooltip>
      ),
    },
    {
      title: '价格',
      dataIndex: 'display',
      key: 'price',
      width: 100,
      sorter: (a: TaskLink, b: TaskLink) => (a.display?.price || 0) - (b.display?.price || 0),
      render: (d: TaskLink['display']) => <span style={{ color: '#ff4d4f', fontWeight: 600 }}>¥{d?.price?.toFixed(2) ?? '—'}</span>,
    },
    {
      title: '卖家',
      dataIndex: 'display',
      key: 'seller',
      width: 140,
      render: (d: TaskLink['display']) => (
        <div>
          <div>{d?.seller_nick || d?.seller_id || '—'}</div>
          {d?.seller_credit && (
            <div style={{ fontSize: 11, color: '#52c41a' }}>信用 {d.seller_credit}</div>
          )}
        </div>
      ),
    },
    {
      title: '地区',
      dataIndex: 'display',
      key: 'region',
      width: 100,
      render: (d: TaskLink['display']) => d?.region || '—',
    },
    {
      title: '想要',
      dataIndex: 'display',
      key: 'want',
      width: 70,
      render: (d: TaskLink['display']) => d?.want_cnt ?? '—',
    },
    {
      title: '发布时间',
      dataIndex: 'display',
      key: 'publish',
      width: 160,
      defaultSortOrder: 'descend' as const,
      sorter: (a: TaskLink, b: TaskLink) => {
        const ta = a.display?.publish_time ? new Date(a.display.publish_time).getTime() : 0
        const tb = b.display?.publish_time ? new Date(b.display.publish_time).getTime() : 0
        return tb - ta  // 降序：最新在前
      },
      // 优先级：有发布时间显示时间；否则显示卖家信用度；都没有显示"—"
      render: (d: TaskLink['display']) => {
        if (d?.publish_time) return new Date(d.publish_time).toLocaleString('zh-CN')
        if (d?.seller_credit) return <span style={{ color: '#52c41a' }}>{d.seller_credit}</span>
        return '—'
      },
    },
    {
      title: '状态',
      dataIndex: 'display',
      key: 'status',
      width: 80,
      render: (d: TaskLink['display']) => d?.is_sold ? <Tag color="red">已售</Tag> : <Tag color="green">在售</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: TaskLink) => (
        <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.link_id)} size="small" disabled={!record.link_id || liveMode} />
      ),
    },
  ]

  return (
    <div className="page-container">
      {/* Cookie 失效提示：醒目居中显示在搜索区域上方 */}
      {sessionExpired && (
        <Alert
          type="error"
          showIcon
          banner
          message="闲鱼登录已过期，实时搜索无法获取商品"
          description="检测到闲鱼 Cookie 失效或会话过期。请重新登录后返回此页面，系统将自动恢复搜索功能。"
          action={
            <Button
              type="primary"
              icon={<LoginOutlined />}
              onClick={() => navigate(`/dashboard?redirect=${encodeURIComponent('/app/items')}`)}
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
            onChange={(e) => setSearch(e.target.value)}
            allowClear
          />
          <Select
            placeholder="筛选地区"
            style={{ width: 140 }}
            allowClear
            value={regionFilter}
            onChange={(v) => setRegionFilter(v)}
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
          {filteredItems.length === 0 ? (
            <Empty description={selectedTask ? '暂无商品数据，可尝试实时搜索' : '请先选择任务'} />
          ) : viewMode === 'table' ? (
            <>
              <Table
                columns={columns}
                dataSource={filteredItems}
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
                {filteredItems.map((item) => {
                  const d = item.display
                  return (
                    <Col xs={12} sm={8} md={6} lg={4} xl={4} key={item.link_id}>
                      <Tooltip
                        title={
                          <div style={{ maxWidth: 300 }}>
                            <div style={{ fontWeight: 600, marginBottom: 4 }}>{d?.title || '—'}</div>
                            <div style={{ color: '#ff4d4f' }}>¥{d?.price?.toFixed(2) ?? '—'}</div>
                            <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
                              {d?.region || '—'} · 想要 {d?.want_cnt ?? 0} · {d?.seller_nick || d?.seller_id || '—'}
                            </div>
                            {d?.publish_time && (
                              <div style={{ color: '#999', fontSize: 12 }}>
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
                              <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bfbfbf', fontSize: 24 }}>🖼️</div>
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
