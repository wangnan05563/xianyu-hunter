import { useEffect, useMemo, useState, useCallback } from 'react'
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Layout,
  Modal,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Upload,
  message,
} from 'antd'
import type { UploadProps } from 'antd'
import {
  DatabaseOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  TableOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import { dbAdminApi, type DbColumn, type DbTableInfo } from '../../api/dbAdmin'
import { useSearch } from '../../hooks/useSearch'
import { useSearchHistory } from '../../hooks/useSearchHistory'

// 与后端约定的危险操作确认 token
const CONFIRM_TOKEN = 'CONFIRM_DELETE'

const { Sider, Content } = Layout
const { TextArea } = Input

// 表名 → 中文显示名（侧边栏更易识别）
const TABLE_LABELS: Record<string, string> = {
  tasks: '任务',
  items: '商品',
  sellers: '卖家',
  evaluations: '评估记录',
  orders: '订单',
  events: '事件日志',
  task_links: '任务关联',
  task_deps: '任务依赖',
  notifications: '业务通知',
  accounts: '闲鱼账号',
  proxies: '代理池',
}

const PAGE_SIZE = 50

// 把任意值格式化为单元格文本（datetime/JSON 友好展示）
function formatCell(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  // 显式处理 string：避免后续 String() 误判对象为 [object Object]（S6551）
  if (typeof value === 'string') return value
  // 经过前面的 typeof 检查，value 必为基础类型（number/boolean/bigint/symbol），
  // 直接用 toString() 避免 String() 调用的 S6551 误报
  return (value as { toString: () => string }).toString()
}

// 表单初值转字符串：对象字段用 JSON.stringify 避免得到 [object Object]（S6551）
function toFormString(value: unknown): string {
  if (typeof value === 'object') return JSON.stringify(value)
  return (value as { toString: () => string }).toString()
}

// CSV 解析（简单实现，支持引号转义；生产环境建议用 papaparse）
// 提取到组件外避免每次渲染重建闭包（S7721）

// 处理引号字符：根据当前 inQuote 状态决定追加内容、状态切换、跳过下一字符数
// 为什么提取：parseCSV 主函数 if(inQuote) 内嵌套 if/else if 链让认知复杂度达 19（S3776）；
// 把引号处理独立后，主循环每个分支变为单层 else if，复杂度归零到 14 以下
function handleQuoteChar(
  inQuote: boolean,
  nextCh: string | undefined,
): { append: string; newInQuote: boolean; skip: number } {
  // 引号内遇到双引号：CSV 标准转义（"" 表示字面量 "），追加 " 并跳过下一 "
  if (inQuote && nextCh === '"') return { append: '"', newInQuote: true, skip: 1 }
  // 引号内遇到单 "：闭合引号
  if (inQuote) return { append: '', newInQuote: false, skip: 0 }
  // 引号外遇到 "：开启引号
  return { append: '', newInQuote: true, skip: 0 }
}

function parseCSV(text: string): string[][] {
  const rows: string[][] = []
  let cur: string[] = []
  let val = ''
  let inQuote = false
  // 去除 UTF-8 BOM：用 codePointAt 替代 charCodeAt 以正确处理 Unicode（S7758）
  if (text.codePointAt(0) === 0xfeff) text = text.slice(1)
  let i = 0
  while (i < text.length) {
    const ch = text[i]
    if (ch === '"') {
      const r = handleQuoteChar(inQuote, text[i + 1])
      val += r.append
      inQuote = r.newInQuote
      i += r.skip
    } else if (inQuote) {
      val += ch
    } else if (ch === ',') {
      cur.push(val); val = ''
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++
      cur.push(val); val = ''
      rows.push(cur); cur = []
    } else {
      val += ch
    }
    i++
  }
  if (val !== '' || cur.length > 0) { cur.push(val); rows.push(cur) }
  return rows.filter((r) => r.length > 1 || (r.length === 1 && r[0] !== ''))
}

// 构建级联影响预览 HTML：被 openDeleteConfirm 与 openBatchDeleteConfirm 共用
// 为什么提取：两个函数原本各自重复 try/catch + if(relations.length>0) + for + 三元 icon 链，
// 单函数复杂度 9+；提取后调用方仅剩单行 await，主函数复杂度降低 9
async function buildCascadeHtml(
  table: string | null,
  keys: Array<string | number>,
): Promise<string> {
  if (!table) return '<p style="color:#999">加载中...</p>'
  try {
    const preview = await dbAdminApi.cascadePreview(table, keys)
    if (preview.relations.length === 0) {
      return '<p style="color:#52c41a">✓ 无关联数据，可安全删除</p>'
    }
    const items = preview.relations
      .map((r) => `<li>${r.action === 'cascade' ? '🗑' : '✂'} ${r.description}</li>`)
      .join('')
    return `<p style="color:#faad14;margin-bottom:4px">⚠ 关联影响：共 ${preview.total_affected} 条关联数据将被处理</p><ul style="margin:0;padding-left:20px;font-size:12px;color:#666">${items}</ul>`
  } catch {
    return '<p style="color:#999">级联预览加载失败</p>'
  }
}

// 推断 antd 表单组件类型（动态表单渲染用）
function inferFormType(colType: string): 'text' | 'textarea' | 'number' | 'switch' | 'datetime' {
  const t = colType.toUpperCase()
  if (t.includes('INT') || t.includes('FLOAT') || t.includes('REAL') || t.includes('DOUBLE') || t.includes('NUMERIC')) {
    return 'number'
  }
  if (t.includes('BOOL')) return 'switch'
  if (t.includes('DATETIME') || t.includes('TIMESTAMP')) return 'datetime'
  if (t.includes('TEXT') || t.includes('JSON') || t.includes('CLOB')) return 'textarea'
  return 'text'
}

// 单元格编辑器：在 Modal 中根据列定义动态生成表单项
// props 标记 readonly 防止组件内部意外修改父级传入数据（S6759）
function ColumnFormFields({ columns, initial }: { readonly columns: DbColumn[]; readonly initial?: Record<string, unknown> }) {
  return (
    <>
      {columns.map((col) => {
        const formType = inferFormType(col.type)
        // 主键在 update 时禁用编辑，insert 时允许手工指定（兼容 String 主键）
        const isInitialNull = initial?.[col.name] === null || initial?.[col.name] === undefined
        const label = (
          <Tooltip title={col.label || undefined}>
            <Space size={4}>
              <span>{col.label ? col.label.split('（')[0] : col.name}</span>
              {col.primary_key && <Tag color="blue" style={{ marginLeft: 0 }}>PK</Tag>}
              <Text type="secondary" style={{ fontSize: 11 }}>{col.type}</Text>
            </Space>
          </Tooltip>
        )
        const initialValue = initial?.[col.name] ?? null
        if (formType === 'switch') {
          return (
            <Form.Item key={col.name} name={col.name} label={label} valuePropName="checked" initialValue={!!initialValue}>
              <Switch />
            </Form.Item>
          )
        }
        if (formType === 'number') {
          return (
            <Form.Item key={col.name} name={col.name} label={label} initialValue={isInitialNull ? null : Number(initialValue)}>
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
          )
        }
        if (formType === 'textarea') {
          return (
            <Form.Item key={col.name} name={col.name} label={label} initialValue={isInitialNull ? '' : toFormString(initialValue)}>
              <TextArea rows={3} placeholder="JSON 字符串" />
            </Form.Item>
          )
        }
        // text / datetime 统一用 Input，由后端解析
        return (
          <Form.Item key={col.name} name={col.name} label={label} initialValue={isInitialNull ? '' : toFormString(initialValue)}>
            <Input placeholder={col.nullable ? '可空' : ''} />
          </Form.Item>
        )
      })}
    </>
  )
}

export default function DatabaseAdmin() {
  // 搜索历史：文本搜索关键词持久化到 localStorage，供快速复用
  const { history, add, clear } = useSearchHistory({ namespace: 'db_admin' })
  // 侧边栏表数据
  const [tables, setTables] = useState<DbTableInfo[]>([])
  const [tablesLoading, setTablesLoading] = useState(false)
  // 当前选中表
  const [activeTable, setActiveTable] = useState<string | null>(null)
  // 当前表结构
  const [columns, setColumns] = useState<DbColumn[]>([])
  // 数据
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [orderBy, setOrderBy] = useState<string | undefined>(undefined)
  const [rowsLoading, setRowsLoading] = useState(false)
  // 多选
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  // 表结构详情抽屉
  const [schemaDrawerOpen, setSchemaDrawerOpen] = useState(false)
  // 审计日志抽屉
  const [auditDrawerOpen, setAuditDrawerOpen] = useState(false)
  // 编辑/新增弹窗
  const [editing, setEditing] = useState<{ mode: 'create' | 'update'; row?: Record<string, unknown> } | null>(null)
  // 导入弹窗
  const [importOpen, setImportOpen] = useState(false)
  // 审计日志内容
  const [auditLog, setAuditLog] = useState<{ items: Array<{ id: number; type: string; level: string; message: string; created_at: string }> }>({ items: [] })

  // 加载表列表
  const loadTables = async () => {
    setTablesLoading(true)
    try {
      const data = await dbAdminApi.listTables()
      const tables = data.tables || []
      setTables(tables)
      // 默认选中第一个表（防御性检查：避免 data.tables 为 undefined 抛错）
      if (!activeTable && tables.length > 0) {
        setActiveTable(tables[0].name)
      }
    } catch (e) {
      message.error('加载表列表失败')
      // 记录异常对象，便于排查时定位根因（S2486）
      console.warn('加载表列表失败:', e)
    } finally {
      setTablesLoading(false)
    }
  }

  useEffect(() => {
    loadTables()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 加载表结构
  const loadSchema = async (table: string) => {
    try {
      const data = await dbAdminApi.getSchema(table)
      setColumns(data.columns)
    } catch (e) {
      message.error('加载表结构失败')
      // 记录异常对象，便于排查时定位根因（S2486）
      console.warn('加载表结构失败:', e)
    }
  }

  // 加载行数据
  // 改为 useCallback：useSearch 需要把 loadRows 作为依赖，普通函数每次渲染重建会导致防抖失效
  const loadRows = useCallback(async () => {
    if (!activeTable) return
    setRowsLoading(true)
    setSelectedRowKeys([])
    try {
      const data = await dbAdminApi.listRows(activeTable, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        search: search || undefined,
        order_by: orderBy,
      })
      setRows(data.rows)
      setTotal(data.total)
      // 搜索成功且关键词非空时记录历史，供后续快速复用
      if (search?.trim()) {
        add(search.trim())
      }
    } catch (e: any) {
      message.error(`加载数据失败: ${e?.response?.data?.detail || e?.message}`)
    } finally {
      setRowsLoading(false)
    }
  }, [activeTable, page, search, orderBy, add])

  // 选中表变化时重置并加载（仅重置状态，数据加载由 useSearch 在依赖变化后防抖触发）
  useEffect(() => {
    if (activeTable) {
      loadSchema(activeTable)
      setPage(1)
      setSearch('')
      setOrderBy(undefined)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTable])

  // 搜索防抖：page/activeTable/search/orderBy 变化时 400ms 防抖触发
  // 替代手写 useEffect，统一搜索防抖逻辑
  const { doSearch } = useSearch({
    search: () => loadRows(),
    deps: [loadRows],
  })

  // 主键列（用于行标识与编辑时的禁用）
  const pkCol = useMemo(() => columns.find((c) => c.primary_key), [columns])

  // 动态列定义
  const tableColumns = useMemo(() => {
    return columns.map((col) => ({
      title: (
        <Tooltip title={col.label || `${col.type}${col.nullable ? '' : ' NOT NULL'}`}>
          <Space size={4}>
            <span>{col.label ? col.label.split('（')[0] : col.name}</span>
            {col.primary_key && <Tag color="blue" style={{ marginLeft: 0 }}>PK</Tag>}
          </Space>
        </Tooltip>
      ),
      dataIndex: col.name,
      key: col.name,
      ellipsis: true,
      width: col.name.length > 20 ? 200 : undefined,
      sorter: true,
      render: (v: unknown) => {
        if (v === null || v === undefined) return <Text type="secondary">NULL</Text>
        const text = formatCell(v)
        if (text.length > 80) {
          return <Tooltip title={text}><span>{text.slice(0, 80)}…</span></Tooltip>
        }
        return <span>{text}</span>
      },
    }))
  }, [columns])

  // 单行删除（带 CONFIRM 弹窗）
  const handleDelete = async (pkValue: unknown) => {
    if (!activeTable) return
    try {
      await dbAdminApi.deleteRow(activeTable, pkValue as string | number)
      message.success('已删除')
      loadRows()
      loadTables()
    } catch (e: any) {
      message.error(`删除失败: ${e?.response?.data?.detail || e?.message}`)
    }
  }

  // 批量删除
  const handleBatchDelete = async () => {
    if (!activeTable || selectedRowKeys.length === 0) return
    try {
      const result = await dbAdminApi.batchDelete(activeTable, selectedRowKeys.map(String))
      message.success(`已删除 ${result.affected}/${result.requested} 行`)
      setSelectedRowKeys([])
      loadRows()
      loadTables()
    } catch (e: any) {
      message.error(`批量删除失败: ${e?.response?.data?.detail || e?.message}`)
    }
  }

  // 弹窗：单行删除二次确认（含级联影响预览）
  const openDeleteConfirm = async (pkValue: unknown) => {
    let tokenValue = ''
    // 级联预览 HTML 构建提取为模块级 buildCascadeHtml（消除 try/catch + if/for 嵌套）
    const cascadeHtml = await buildCascadeHtml(activeTable, [pkValue as string | number])
    const modal = Modal.confirm({
      title: '确认删除该行？',
      icon: <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />,
      content: (
        <div>
          <p>主键：<code>{formatCell(pkValue)}</code></p>
          <div dangerouslySetInnerHTML={{ __html: cascadeHtml }} style={{ marginBottom: 12, padding: 8, background: '#fafafa', borderRadius: 6 }} />
          <p>请输入 <b>{CONFIRM_TOKEN}</b> 以确认（区分大小写）：</p>
          <Input.Password
            placeholder={CONFIRM_TOKEN}
            onChange={(e) => {
              tokenValue = e.target.value
              modal.update((prev) => ({
                ...prev,
                okButtonProps: { danger: true, disabled: tokenValue !== CONFIRM_TOKEN },
              }))
            }}
          />
        </div>
      ),
      okText: '确认删除',
      cancelText: '取消',
      okButtonProps: { danger: true, disabled: true },
      onOk: () => handleDelete(pkValue),
    })
  }

  // 弹窗：批量删除二次确认（含级联影响预览）
  const openBatchDeleteConfirm = async () => {
    let tokenValue = ''
    // 级联预览 HTML 构建复用 buildCascadeHtml（与 openDeleteConfirm 一致）
    const cascadeHtml = await buildCascadeHtml(activeTable, selectedRowKeys.map(String))
    const modal = Modal.confirm({
      title: `确认批量删除 ${selectedRowKeys.length} 行？`,
      icon: <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />,
      content: (
        <div>
          <p>将删除当前选中的 <b>{selectedRowKeys.length}</b> 行记录，操作不可恢复。</p>
          <div dangerouslySetInnerHTML={{ __html: cascadeHtml }} style={{ marginBottom: 12, padding: 8, background: '#fafafa', borderRadius: 6 }} />
          <p>请输入 <b>{CONFIRM_TOKEN}</b> 以确认（区分大小写）：</p>
          <Input.Password
            placeholder={CONFIRM_TOKEN}
            onChange={(e) => {
              tokenValue = e.target.value
              modal.update((prev) => ({
                ...prev,
                okButtonProps: { danger: true, disabled: tokenValue !== CONFIRM_TOKEN },
              }))
            }}
          />
        </div>
      ),
      okText: '确认删除',
      cancelText: '取消',
      okButtonProps: { danger: true, disabled: true },
      onOk: () => handleBatchDelete(),
    })
  }

  // 提交编辑/新增
  const [form] = Form.useForm()
  const handleSubmitEdit = async () => {
    if (!activeTable || !editing) return
    try {
      const values = await form.validateFields()
      // 去除空字符串，让后端走 nullable 语义
      const cleaned: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(values)) {
        if (v === '' || v === undefined) continue
        cleaned[k] = v
      }
      if (editing.mode === 'create') {
        await dbAdminApi.createRow(activeTable, cleaned)
        message.success('已新增')
      } else {
        const pkValue = editing.row?.[pkCol!.name] as string | number
        await dbAdminApi.updateRow(activeTable, pkValue, cleaned)
        message.success('已更新')
      }
      setEditing(null)
      loadRows()
      loadTables()
    } catch (e: any) {
      if (e?.errorFields) {
        message.error('表单校验失败')
      } else {
        message.error(`操作失败: ${e?.response?.data?.detail || e?.message}`)
      }
    }
  }

  // 导出（CSV/JSON）
  const handleExport = async (format: 'csv' | 'json') => {
    if (!activeTable) return
    try {
      const blob = await dbAdminApi.exportRows(activeTable, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${activeTable}_${new Date().toISOString().slice(0, 19).replaceAll(':', '').replaceAll('T', '')}.${format}`
      a.click()
      URL.revokeObjectURL(url)
      message.success('导出已开始')
    } catch (e: any) {
      message.error(`导出失败: ${e?.response?.data?.detail || e?.message}`)
    }
  }

  // 加载审计日志
  const loadAuditLog = async () => {
    try {
      const data = await dbAdminApi.getAuditLog(200)
      setAuditLog({ items: data.items })
    } catch (e) {
      message.error('加载审计日志失败')
      // 记录异常对象，便于排查时定位根因（S2486）
      console.warn('加载审计日志失败:', e)
    }
  }

  // 导入文件：核心解析与确认逻辑封装在内部函数中，
  // beforeUpload 钩子仅在调用后返回 false 阻止 antd 自动上传，
  // 这种"内部函数处理 + 外部包装返回 false"的结构避免所有 return 返回同一值（S3516）
  const processImportFile = async (file: { text: () => Promise<string>; name: string }) => {
    if (!activeTable) return
    const text = await file.text()
    const isJson = file.name.toLowerCase().endsWith('.json')
    let rows: unknown[][]
    let headers: string[] | undefined
    if (isJson) {
      const data = JSON.parse(text)
      if (!Array.isArray(data) || data.length === 0) {
        message.error('JSON 必须是非空数组')
        return
      }
      headers = Object.keys(data[0])
      rows = data.map((obj: any) => headers!.map((h) => obj[h]))
    } else {
      const all = parseCSV(text)
      if (all.length < 2) {
        message.error('CSV 至少需要表头 + 1 行数据')
        return
      }
      headers = all[0]
      rows = all.slice(1)
    }
    Modal.confirm({
        title: '确认导入',
        icon: <ExclamationCircleOutlined />,
        content: (
          <div>
            <p>将向表 <b>{activeTable}</b> 导入 <b>{rows.length}</b> 行</p>
            <p>请选择冲突处理：</p>
          </div>
        ),
        okText: '跳过冲突',
        cancelText: '取消',
        onOk: async () => {
          try {
            const result = await dbAdminApi.importRows(activeTable, rows, headers, 'insert')
            message.success(`导入完成：${result.inserted} 成功，${result.skipped} 跳过，${result.errors.length} 错误`)
            setImportOpen(false)
            loadRows()
            loadTables()
          } catch (e: any) {
            message.error(`导入失败: ${e?.response?.data?.detail || e?.message}`)
          }
        },
      })
  }

  const handleImportFile: UploadProps['beforeUpload'] = async (file) => {
    // 调用内部处理函数（内部返回 void），beforeUpload 钩子统一返回 false 阻止 antd 自动上传
    await processImportFile(file).catch((e: any) => {
      message.error(`文件解析失败: ${e?.message}`)
    })
    return false
  }

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <p style={{ margin: 0, color: 'var(--xh-text-tertiary)', fontSize: 13 }}>
          业务表在线 CRUD · 危险操作需要二次确认（输入 {CONFIRM_TOKEN}）· 所有写操作均记录审计日志
        </p>
        <Space>
          <Button icon={<FileTextOutlined />} onClick={() => { loadAuditLog(); setAuditDrawerOpen(true) }}>
            审计日志
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => { loadTables(); loadRows() }} loading={rowsLoading}>
            刷新
          </Button>
        </Space>
      </div>

      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="数据操作有风险"
        description={
          <span>
            建议操作前先在「导出」中下载备份。删除操作不可恢复，审计日志可在右上角查看。
          </span>
        }
      />

      <Layout style={{ background: 'transparent' }}>
        {/* 左侧表树 */}
        <Sider width={220} style={{ background: 'var(--xh-bg-container)', borderRadius: 8, marginRight: 16, overflow: 'auto' }}>
          <div style={{ padding: 12, fontWeight: 600, borderBottom: '1px solid var(--xh-border)' }}>
            <DatabaseOutlined /> 业务表
          </div>
          {tablesLoading && <div style={{ padding: 16 }}>加载中...</div>}
          {tables.map((t) => (
            // S6819：使用 <button> 替代 <div role="button">，原生 button 自带键盘可达性
            <button
              key={t.name}
              type="button"
              onClick={() => setActiveTable(t.name)}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                padding: '10px 16px',
                cursor: 'pointer',
                background: activeTable === t.name ? '#fff5e6' : 'transparent',
                borderLeft: activeTable === t.name ? '3px solid #FF6200' : '3px solid transparent',
                border: 'none',
                borderBottom: '1px solid var(--xh-border)',
                transition: 'all 0.2s',
                color: 'inherit',
                font: 'inherit',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: activeTable === t.name ? 600 : 400 }}>
                <TableOutlined style={{ marginRight: 6, color: '#FF6200' }} />
                {TABLE_LABELS[t.name] || t.name}
              </div>
              <div style={{ fontSize: 11, color: 'var(--xh-text-tertiary)', marginTop: 2, marginLeft: 22 }}>
                {t.name} · {t.rows.toLocaleString()} 行
              </div>
            </button>
          ))}
        </Sider>

        {/* 右侧主区域 */}
        <Content style={{ background: 'var(--xh-bg-container)', borderRadius: 8, padding: 16 }}>
          {activeTable ? (
            <>
              {/* 工具栏 */}
              <Space style={{ marginBottom: 12 }} wrap>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setEditing({ mode: 'create' }) }}>
                  新增
                </Button>
                <Button danger icon={<DeleteOutlined />} disabled={selectedRowKeys.length === 0} onClick={openBatchDeleteConfirm}>
                  批量删除 {selectedRowKeys.length > 0 && `(${selectedRowKeys.length})`}
                </Button>
                <Button icon={<UploadOutlined />} onClick={() => setImportOpen(true)}>
                  导入
                </Button>
                <Button icon={<DownloadOutlined />} onClick={() => handleExport('csv')}>
                  导出 CSV
                </Button>
                <Button icon={<DownloadOutlined />} onClick={() => handleExport('json')}>
                  导出 JSON
                </Button>
                <Button icon={<TableOutlined />} onClick={() => setSchemaDrawerOpen(true)}>
                  查看表结构
                </Button>
                <Input
                  placeholder="搜索文本列"
                  allowClear
                  prefix={<SearchOutlined />}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onPressEnter={() => { setPage(1); doSearch() }}
                  style={{ width: 200 }}
                />
                <Button onClick={() => { setPage(1); doSearch() }}>查询</Button>
              </Space>
              {/* 搜索历史小药丸：点击复用历史关键词，避免重复输入 */}
              {history.length > 0 && (
                <div style={{ marginBottom: 12, display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
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

              <Table
                rowKey={(r) => formatCell(r[pkCol?.name || 'id'])}
                columns={[
                  ...tableColumns,
                  {
                    title: '操作',
                    key: 'action',
                    width: 180,
                    fixed: 'right',
                    render: (_: unknown, record: Record<string, unknown>) => (
                      <Space size="small">
                        <Button
                          size="small"
                          type="link"
                          icon={<EditOutlined />}
                          onClick={() => {
                            form.resetFields()
                            form.setFieldsValue(record)
                            setEditing({ mode: 'update', row: record })
                          }}
                        >
                          编辑
                        </Button>
                        <Button size="small" type="link" danger icon={<DeleteOutlined />} onClick={() => openDeleteConfirm(record[pkCol!.name])}>删除</Button>
                      </Space>
                    ),
                  },
                ]}
                dataSource={rows}
                loading={rowsLoading}
                scroll={{ x: 'max-content' }}
                rowSelection={{
                  selectedRowKeys,
                  onChange: setSelectedRowKeys,
                  getCheckboxProps: () => ({}),
                }}
                pagination={{
                  current: page,
                  total,
                  pageSize: PAGE_SIZE,
                  showSizeChanger: false,
                  showTotal: (t) => `共 ${t.toLocaleString()} 行`,
                  onChange: setPage,
                }}
                onChange={(_pagination, _filters, sorter: any) => {
                  if (sorter?.field) {
                    setOrderBy(`${sorter.order === 'descend' ? '-' : ''}${sorter.field}`)
                  } else {
                    setOrderBy(undefined)
                  }
                }}
                size="small"
              />
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--xh-text-tertiary)' }}>请从左侧选择一张表</div>
          )}
        </Content>
      </Layout>

      {/* 编辑/新增弹窗 */}
      <Modal
        title={editing?.mode === 'create' ? `新增 → ${activeTable}` : `编辑 → ${activeTable}`}
        open={!!editing}
        onCancel={() => setEditing(null)}
        onOk={handleSubmitEdit}
        width={680}
        okText={editing?.mode === 'create' ? '新增' : '更新'}
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false}>
          <ColumnFormFields columns={columns} initial={editing?.row} />
        </Form>
      </Modal>

      {/* 导入弹窗 */}
      <Modal
        title="导入数据"
        open={importOpen}
        onCancel={() => setImportOpen(false)}
        footer={null}
      >
        <Tabs
          items={[
            {
              key: 'csv',
              label: 'CSV 格式',
              children: (
                <div>
                  <p>CSV 列顺序需与表头一致；首行为表头（列名），后续每行一条记录。</p>
                  <Upload accept=".csv" beforeUpload={handleImportFile} showUploadList={false}>
                    <Button icon={<UploadOutlined />}>选择 CSV 文件</Button>
                  </Upload>
                </div>
              ),
            },
            {
              key: 'json',
              label: 'JSON 格式',
              children: (
                <div>
                  <p>JSON 为对象数组，例如：<code>[&#123;"id":"1","name":"a"&#125;]</code></p>
                  <Upload accept=".json" beforeUpload={handleImportFile} showUploadList={false}>
                    <Button icon={<UploadOutlined />}>选择 JSON 文件</Button>
                  </Upload>
                </div>
              ),
            },
          ]}
        />
      </Modal>

      {/* 表结构抽屉 */}
      <Drawer
        title={`表结构 - ${activeTable}`}
        open={schemaDrawerOpen}
        onClose={() => setSchemaDrawerOpen(false)}
        width={860}
      >
        <Table
          rowKey="name"
          size="small"
          pagination={false}
          dataSource={columns}
          columns={[
            { title: '列名', dataIndex: 'name', key: 'name', width: 130 },
            { title: '中文标注', dataIndex: 'label', key: 'label', ellipsis: true },
            { title: '类型', dataIndex: 'type', key: 'type', width: 100 },
            {
              title: '主键',
              dataIndex: 'primary_key',
              key: 'primary_key',
              width: 50,
              render: (v: boolean) => v ? <Tag color="blue">PK</Tag> : '-',
            },
            {
              title: '可空',
              dataIndex: 'nullable',
              key: 'nullable',
              width: 50,
              render: (v: boolean) => v ? <Tag>YES</Tag> : <Tag color="red">NO</Tag>,
            },
            { title: '默认值', dataIndex: 'default', key: 'default', width: 100 },
          ]}
        />
      </Drawer>

      {/* 审计日志抽屉 */}
      <Drawer
        title="数据库维护审计日志"
        open={auditDrawerOpen}
        onClose={() => setAuditDrawerOpen(false)}
        width={720}
      >
        <Table
          rowKey="id"
          size="small"
          dataSource={auditLog.items}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
            {
              title: '操作',
              dataIndex: 'type',
              key: 'type',
              width: 160,
              render: (v: string) => <Tag color={v.includes('failed') ? 'red' : 'blue'}>{v}</Tag>,
            },
            {
              title: '级别',
              dataIndex: 'level',
              key: 'level',
              width: 60,
              render: (v: string) => {
                // err=红 warn=橙 其他=绿（info 等正常级别）
                const levelColorMap: Record<string, string> = { err: 'red', warn: 'orange' }
                return <Tag color={levelColorMap[v] ?? 'green'}>{v}</Tag>
              },
            },
            { title: '详情', dataIndex: 'message', key: 'message', ellipsis: true },
          ]}
        />
      </Drawer>
    </div>
  )
}

// 局部小工具：Text 别名（避免再 import Typography）
const Text = ({ type, style, children }: { readonly type?: 'secondary'; readonly style?: React.CSSProperties; readonly children: React.ReactNode }) => (
  <span style={{ color: type === 'secondary' ? '#999' : undefined, ...style }}>{children}</span>
)
