// frontend/src/mobile/pages/DatabaseAdmin/index.tsx
// 移动端数据库维护：表列表 + 行浏览（只读）+ 导出
// 关键简化：去掉桌面端 inline 编辑/批量删除/级联预览/审计日志，移动端仅浏览和导出
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Tag, Spin, App, Select, Button, Space, Empty, theme, Table, Drawer, Popconfirm,
} from 'antd'
import { ReloadOutlined, DownloadOutlined, EyeOutlined } from '@ant-design/icons'
import { dbAdminApi, CONFIRM_TOKEN } from '../../../api/dbAdmin'
import type { DbTableInfo, DbRowListResponse } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'

const PAGE_SIZE = 20

export default function MobileDatabaseAdmin() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [tables, setTables] = useState<DbTableInfo[]>([])
  const [selectedTable, setSelectedTable] = useState<string | undefined>(undefined)
  const [rows, setRows] = useState<DbRowListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [rowsLoading, setRowsLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [detailRow, setDetailRow] = useState<Record<string, unknown> | null>(null)

  const loadTables = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const data = await dbAdminApi.listTables()
      setTables(data.tables)
    } catch (e) {
      message.error(extractApiError(e, '加载表列表失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  const loadRows = useCallback(async (): Promise<void> => {
    if (!selectedTable) return
    setRowsLoading(true)
    try {
      const data = await dbAdminApi.listRows(selectedTable, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        search: search || undefined,
      })
      setRows(data)
    } catch (e) {
      message.error(extractApiError(e, '加载数据失败'), 3)
    } finally {
      setRowsLoading(false)
    }
  }, [selectedTable, page, search, message])

  useEffect(() => { void loadTables() }, [loadTables])
  useEffect(() => { void loadRows() }, [loadRows])

  // 导出当前表
  const exportTable = async (format: 'csv' | 'json'): Promise<void> => {
    if (!selectedTable) return
    try {
      const blob = await dbAdminApi.exportRows(selectedTable, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${selectedTable}.${format}`
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      requestAnimationFrame(() => {
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      })
      message.success('已导出')
    } catch (e) {
      message.error(extractApiError(e, '导出失败'), 3)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  return (
    <div>
      {/* 表选择 */}
      <Card size="small" style={{ marginBottom: 10 }} title="数据表">
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Select
            placeholder="选择表"
            value={selectedTable}
            onChange={(v) => { setSelectedTable(v); setPage(1); setSearch('') }}
            style={{ width: '100%' }}
            options={tables.map((t) => ({
              value: t.name,
              label: `${t.name} (${t.rows} 行)`,
            }))}
          />
          {selectedTable && (
            <Space size={6} style={{ width: '100%' }}>
              <Button size="small" icon={<DownloadOutlined />} onClick={() => void exportTable('csv')} style={{ flex: 1 }}>
                CSV
              </Button>
              <Button size="small" icon={<DownloadOutlined />} onClick={() => void exportTable('json')} style={{ flex: 1 }}>
                JSON
              </Button>
              <Button size="small" type="text" icon={<ReloadOutlined />} onClick={() => void loadRows()} />
            </Space>
          )}
        </Space>
      </Card>

      {/* 行数据 */}
      {selectedTable && (
        <Card
          size="small"
          title={`${selectedTable} 数据`}
          extra={
            <Tag color="blue">
              {rows ? `${rows.total} 行` : '...'}
            </Tag>
          }
        >
          {rowsLoading ? (
            <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
          ) : !rows || rows.rows.length === 0 ? (
            <Empty description="暂无数据" imageStyle={{ height: 60 }} />
          ) : (
            <div>
              {rows.rows.map((row: Record<string, unknown>, idx: number) => (
                <div
                  key={idx}
                  style={{
                    padding: '6px 0',
                    borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
                    cursor: 'pointer',
                  }}
                  onClick={() => setDetailRow(row)}
                >
                  <div style={{ fontSize: 12, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {/* 展示前 3 个字段作为摘要 */}
                    {Object.entries(row).slice(0, 3).map(([k, v]) => (
                      <span key={k}>
                        <span style={{ color: themeToken.colorTextTertiary }}>{k}:</span>
                        <span>{String(v ?? '').slice(0, 20)}</span>
                      </span>
                    ))}
                  </div>
                </div>
              ))}
              {/* 分页 */}
              <Space size={6} style={{ width: '100%', justifyContent: 'center', marginTop: 12 }}>
                <Button
                  size="small"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  上一页
                </Button>
                <Tag>{page} / {Math.ceil((rows?.total ?? 1) / PAGE_SIZE)}</Tag>
                <Button
                  size="small"
                  disabled={page * PAGE_SIZE >= (rows?.total ?? 0)}
                  onClick={() => setPage(page + 1)}
                >
                  下一页
                </Button>
              </Space>
            </div>
          )}
        </Card>
      )}

      {/* 行详情抽屉 */}
      <Drawer
        title="行详情"
        placement="bottom"
        height="70%"
        open={detailRow !== null}
        onClose={() => setDetailRow(null)}
      >
        {detailRow && (
          <div style={{ fontSize: 13 }}>
            {Object.entries(detailRow).map(([k, v]) => (
              <div
                key={k}
                style={{
                  display: 'flex',
                  gap: 8,
                  padding: '6px 0',
                  borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
                }}
              >
                <span style={{ minWidth: 100, color: themeToken.colorTextSecondary, fontSize: 12 }}>
                  {k}
                </span>
                <span style={{ flex: 1, wordBreak: 'break-word' }}>
                  {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '')}
                </span>
              </div>
            ))}
          </div>
        )}
      </Drawer>
    </div>
  )
}
