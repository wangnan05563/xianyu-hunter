// frontend/src/mobile/pages/DatabaseAdmin/index.tsx
// 移动端数据库维护：表列表 + 行浏览（只读）+ 导出
// 关键简化：去掉桌面端 inline 编辑/批量删除/级联预览/审计日志，移动端仅浏览和导出
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Tag, Spin, App, Select, Button, Space, Empty, theme, Drawer,
} from 'antd'
import { ReloadOutlined, DownloadOutlined } from '@ant-design/icons'
import { dbAdminApi } from '../../../api/dbAdmin'
import type { DbTableInfo, DbRowListResponse } from '../../../api/types'
import { extractApiError } from '../../../utils/apiError'
import { notifyExportResult, triggerBlobDownload } from '../../../utils/exportFeedback'
import { useFailedSources } from '../../../hooks/useFailedSources'
import LoadFailedBar from '../../components/LoadFailedBar'

const PAGE_SIZE = 20

// 数据源（T02718）：表列表/表数据各自记账，失败时不能渲染成空下拉与「暂无数据」
type DatabaseAdminSource = 'tables' | 'rows'
const SOURCE_LABELS: Record<DatabaseAdminSource, string> = {
  tables: '数据表列表',
  rows: '表数据',
}

// 单元格值格式化：null/undefined → ''；对象/数组 → JSON 字符串；字符串原样返回；其他走 String()。
// 提取为独立函数避免 JSX 中嵌套三元（SonarQube S3358），并通过显式 if-链
// 让 SonarQube 识别 v 在 String() 处已排除对象分支，避免 [object Object] 警告（S6551）。
function formatCellValue(v: unknown): string {
  if (v == null) return ''
  if (typeof v === 'object') return JSON.stringify(v)
  if (typeof v === 'string') return v
  return String(v) // NOSONAR - 前置 typeof 已排除 object 分支，此处 v 只可能是 number/boolean/symbol
}

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
  const [exporting, setExporting] = useState<'csv' | 'json' | null>(null)
  const [detailRow, setDetailRow] = useState<Record<string, unknown> | null>(null)
  const { failed, mark } = useFailedSources<DatabaseAdminSource>()

  const loadTables = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const data = await dbAdminApi.listTables()
      setTables(data.tables)
      mark('tables', true)
    } catch (e) {
      mark('tables', false)
      message.error(extractApiError(e, '加载表列表失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message, mark])

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
      mark('rows', true)
    } catch (e) {
      mark('rows', false)
      message.error(extractApiError(e, '加载数据失败'), 3)
    } finally {
      setRowsLoading(false)
    }
  }, [selectedTable, page, search, message, mark])

  useEffect(() => { void loadTables() }, [loadTables])
  useEffect(() => { void loadRows() }, [loadRows])

  // 导出当前表（T02576 / 4.2-2：全表导出可能几十秒，必须有 loading 且按钮点名「全表」）
  const exportTable = async (format: 'csv' | 'json'): Promise<void> => {
    if (!selectedTable || exporting) return
    setExporting(format)
    try {
      const { blob, rows, filename } = await dbAdminApi.exportRows(selectedTable, format)
      triggerBlobDownload(blob, filename)
      notifyExportResult(message, { rows, filename }, `${selectedTable} 全表（${format.toUpperCase()}）`)
    } catch (e) {
      message.error(extractApiError(e, '导出失败'), 3)
    } finally {
      setExporting(null)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>

  // 全表行数与 /tables 同源（导出按钮的分母必须是全表，不是当前分页/筛选结果）
  const fullTableRows = tables.find((t) => t.name === selectedTable)?.rows
  // 行数标签：取不到时显示 —，不留一个转圈的「...」假装还在加载
  const rowsTagText = rows ? `${rows.total} 行` : (failed.rows ? '—' : '...')

  // 生成行 key：优先使用主键字段，避免直接使用数组索引作为 key（SonarQube S6479）
  // 数据库表通常有 id/_id/uuid 主键；若无则用行内容生成稳定 key，保证同表内唯一
  const rowKey = (row: Record<string, unknown>): string => {
    const idValue = row.id ?? row._id ?? row.uuid
    if (idValue == null) return JSON.stringify(row)
    // idValue 可能是对象（如 MongoDB ObjectId），先序列化对象分支
    if (typeof idValue === 'object') return JSON.stringify(idValue)
    // 此处 idValue 已排除 object 分支，String() 安全
    return String(idValue) // NOSONAR - 前置 typeof 已排除 object 分支
  }

  // 提取行数据区域的渲染逻辑为独立函数，避免 JSX 中嵌套三元（SonarQube S3358）
  const renderRowsContent = () => {
    if (rowsLoading) {
      return <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
    }
    if (!rows || rows.rows.length === 0) {
      if (failed.rows) return null
      // imageStyle 在 antd 5.x 仍可用且无替代 API，暂不迁移（SonarQube S1874）
      return <Empty description="暂无数据" imageStyle={{ height: 60 }} /> /* NOSONAR */
    }
    return (
      <div>
        {rows.rows.map((row: Record<string, unknown>) => (
          // 使用原生 <button> 替代 role="button" 的 div，确保跨设备可访问性（SonarQube S6819）
          // button 原生支持 Enter/Space 键触发 onClick，无需手写 onKeyDown（SonarQube S1082）
          <button
            key={rowKey(row)}
            type="button"
            style={{
              display: 'block',
              width: '100%',
              padding: '6px 0',
              marginBottom: 0,
              border: 'none',
              borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
              background: 'transparent',
              textAlign: 'left',
              cursor: 'pointer',
              font: 'inherit',
            }}
            onClick={() => setDetailRow(row)}
          >
            <div style={{ fontSize: 12, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {/* 展示前 3 个字段作为摘要 */}
              {Object.entries(row).slice(0, 3).map(([k, v]) => (
                <span key={k}>
                  <span style={{ color: themeToken.colorTextTertiary }}>{k}:</span>
                  {/* 使用 formatCellValue 统一处理 null/对象/字符串，避免嵌套三元（S3358/S6551/S6606） */}
                  <span>{formatCellValue(v).slice(0, 20)}</span>
                </span>
              ))}
            </div>
          </button>
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
    )
  }

  return (
    <div>
      {failed.tables && (
        <LoadFailedBar
          source={SOURCE_LABELS.tables}
          note="下拉为空不代表真的没有表"
          onRetry={() => void loadTables()}
        />
      )}
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
              <Button
                size="small"
                icon={<DownloadOutlined />}
                loading={exporting === 'csv'}
                disabled={!!exporting && exporting !== 'csv'}
                onClick={() => void exportTable('csv')}
                style={{ flex: 1 }}
              >
                导出全表 CSV{fullTableRows === undefined ? '' : `（${fullTableRows.toLocaleString()} 行）`}
              </Button>
              <Button
                size="small"
                icon={<DownloadOutlined />}
                loading={exporting === 'json'}
                disabled={!!exporting && exporting !== 'json'}
                onClick={() => void exportTable('json')}
                style={{ flex: 1 }}
              >
                导出全表 JSON
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
              {rowsTagText}
            </Tag>
          }
        >
          {failed.rows && (
            <LoadFailedBar
              source={SOURCE_LABELS.rows}
              note="下方行数、分页与列表都不代表真实数据"
              onRetry={() => void loadRows()}
            />
          )}
          {renderRowsContent()}
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
                  {/* 使用 formatCellValue 统一处理 null/对象/字符串，避免嵌套三元（S3358/S6551） */}
                  {formatCellValue(v)}
                </span>
              </div>
            ))}
          </div>
        )}
      </Drawer>
    </div>
  )
}
