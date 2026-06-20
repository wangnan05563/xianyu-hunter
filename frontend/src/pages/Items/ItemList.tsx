import { useEffect, useState, useCallback } from 'react'
import { Card, Table, Tag, Select, Button, Input, Space, Spin, Image, Tooltip, message, Pagination, Empty, Segmented, Row, Col, Alert } from 'antd'
import { ReloadOutlined, SearchOutlined, DeleteOutlined, LinkOutlined, AppstoreOutlined, UnorderedListOutlined, LoginOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { AxiosError } from 'axios'
import { taskApi, taskLinkApi, type Task, type TaskLink } from '../../api'

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

  useEffect(() => {
    if (!liveMode) loadItems()
  }, [liveMode, loadItems])

  // 实时搜索
  const loadLive = () => {
    if (!selectedTask) return
    setLiveLoading(true)
    setSessionExpired(false)  // 重置上次的状态
    // 进度提示：3 秒后显示"正在搜索闲鱼..."
    const progressTimer = setTimeout(() => {
      message.loading({ content: '正在搜索闲鱼，请稍候...', key: 'live-search', duration: 0 })
    }, 3000)
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
      render: (d: TaskLink['display']) => d?.thumb_url ? <Image src={d.thumb_url} referrerPolicy="no-referrer" width={60} height={60} style={{ objectFit: 'cover', borderRadius: 6 }} /> : '—',
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
      render: (d: TaskLink['display']) => d?.seller_nick || d?.seller_id || '—',
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
      render: (d: TaskLink['display']) => d?.publish_time ? new Date(d.publish_time).toLocaleString('zh-CN') : '—',
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
          <Button icon={<ReloadOutlined />} onClick={loadItems} loading={loading} disabled={!selectedTask || liveMode}>
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
                      <Card
                        className="item-card"
                        size="small"
                        bodyStyle={{ padding: 12 }}
                        cover={
                          <div className="item-card-image">
                            {d?.thumb_url ? (
                              <Image
                                src={d.thumb_url}
                                alt={d?.title || '商品图片'}
                                referrerPolicy="no-referrer"
                                preview={{ src: d?.url || d?.thumb_url }}
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
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
