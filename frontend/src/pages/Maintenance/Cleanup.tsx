import { useEffect, useRef, useState } from 'react'
import {
  Card,
  Select,
  InputNumber,
  Switch,
  Button,
  Row,
  Col,
  Statistic,
  Space,
  Alert,
  message,
  Tag,
  Typography,
} from 'antd'
import {
  ClearOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import {
  maintenanceApi,
  type StorageStatus,
  type CleanupResult,
  type CleanupBody,
  type CacheScan,
} from '../../api'
import { TipButton } from '@/components/TipButton'
import { confirmDanger } from '@/components/DangerSummary'
import { PYCACHE_NOT_APPLICABLE_HINT, cacheTargetOptions } from '@/utils/cacheTargets'

const { Text } = Typography

// 缓存清理各 target 的真实删除范围（与后端 api_maintenance.cleanup_cache 分支一一对应）
// FR-A-5（T02575）：browser_data 不再是 `webview_data_*`（全仓无写入方的幻影目录），
// 而是配置 browser.user_data_dir 指向的真实浏览器资料目录——闲鱼登录态就在这里
const CACHE_SCOPE: Record<string, string> = {
  all: 'Python 字节码缓存（__pycache__）+ 浏览器用户数据目录（含闲鱼登录态）',
  browser_data: '浏览器用户数据目录（含闲鱼登录 Cookie 与反爬指纹）',
  pycache: 'Python 字节码缓存（__pycache__）目录',
}

// 表单状态类型
// CleanupBody 已从 API 层导入，此处无需重复定义

interface CacheConfirmText {
  action: string
  scope: string
  count: string | null
  recovery: string
}

// S3776/S3358：缓存清理确认框文案抽成模块级纯函数，用 if 分支替代嵌套三元
function buildCacheConfirmText(
  body: CleanupBody,
  status: StorageStatus | null,
  pycacheApplicable: boolean,
): CacheConfirmText {
  const c = status?.cache
  const parts: string[] = []
  if (body.target !== 'browser_data' && pycacheApplicable) {
    parts.push(`__pycache__ 目录 ${c?.pycache_count ?? '未知'} 个（${c?.pycache_mb ?? '未知'} MB）`)
  }
  if (body.target !== 'pycache') {
    parts.push(
      `浏览器数据目录 ${c?.browser_data_files ?? '未知'} 个文件（${c?.browser_data_mb ?? '未知'} MB）`,
    )
  }
  // 打包版「全部缓存」真实删的只有浏览器数据，确认框不能还写着 __pycache__
  let scopeText = CACHE_SCOPE[body.target] ?? '所选缓存'
  if (!pycacheApplicable && body.target === 'all') {
    scopeText = '浏览器用户数据目录（含闲鱼登录态）'
  }
  // browser_data 分支现在真的会删登录态（FR-A-5）——后果必须写在确认框里
  const dropsLogin = body.target !== 'pycache'
  let scope = '只删 __pycache__ 字节码缓存；不包含数据库、日志，也不包含浏览器用户数据目录（登录态所在）'
  let recovery = '不可恢复；__pycache__ 会在下次运行时自动重建，只会让首次运行稍慢。'
  if (dropsLogin) {
    scope = `将删除浏览器用户数据目录 ${c?.browser_data_path ?? '（以统计接口回带路径为准）'}，`
      + '其中保存着闲鱼登录 Cookie 与反爬指纹；不包含 SQLite 数据库与日志文件'
    recovery = '不可恢复；删除后需重新扫码登录闲鱼。若浏览器正在占用该目录，'
      + '本次会跳过删除并明确报错，不会只删掉半个目录'
    if (c && !c.browser_data_exists) {
      recovery += '。当前未发现非空的浏览器数据目录，本次不会删除任何浏览器数据'
    }
  }
  return {
    action: `真实删除${scopeText}`,
    scope,
    count: status ? parts.join('；') : null,
    recovery,
  }
}

// S3358：日志清理确认框的 scope/count 文案独立成纯函数，避免三元里再套三元
function buildLogsConfirmText(
  target: string | undefined,
  days: number | undefined,
  lg: StorageStatus['logs'] | undefined,
): { action: string; scope: string; count: string | null } {
  const logAction: Record<string, string> = {
    old_logs: `删除修改时间早于 ${days} 天的日志文件`,
    large_logs: '删除体积超过 10MB 的日志文件',
    all: `删除「修改时间早于 ${days} 天」或「体积超过 10MB」的日志文件`,
  }
  let scope = '只删 logs/ 目录下的文本日志文件；不包含数据库里的事件记录与「错误日志」页的留存数据'
  if (target === 'large_logs' || target === 'all') {
    scope += '。注意：大文件分支不看修改时间，正在写入的当日日志只要超过 10MB 也会被删'
  }
  let count: string | null = null
  if (lg) {
    let oldestSuffix = ''
    if (lg.oldest) oldestSuffix = `（最早 ${lg.oldest}）`
    count = `当前日志 ${lg.file_count} 个文件共 ${lg.total_size_mb} MB${oldestSuffix}`
  }
  return { action: logAction[target ?? 'old_logs'] ?? '删除日志文件', scope, count }
}

export default function Maintenance() {
  // 存储状态数据
  const [status, setStatus] = useState<StorageStatus | null>(null)
  const [loading, setLoading] = useState(false)

  // 三个清理模块的独立状态，避免相互干扰
  const [cacheForm, setCacheForm] = useState<CleanupBody>({
    target: 'all',
    dry_run: true,
  })
  const [dbForm, setDbForm] = useState<CleanupBody>({
    target: 'all',
    days: 30,
    dry_run: true,
  })
  const [logForm, setLogForm] = useState<CleanupBody>({
    target: 'old_logs',
    days: 7,
    dry_run: true,
  })

  // 各模块的加载状态和结果
  const [cacheLoading, setCacheLoading] = useState(false)
  const [dbLoading, setDbLoading] = useState(false)
  const [logLoading, setLogLoading] = useState(false)

  const [cacheResult, setCacheResult] = useState<CleanupResult | null>(null)
  const [dbResult, setDbResult] = useState<CleanupResult | null>(null)
  const [logResult, setLogResult] = useState<CleanupResult | null>(null)

  // 浏览器数据目录的增量统计（T02738）：/status 先带回「统计中」，这里接手轮询续跑。
  // null 时退回 status 里的快照，两者以最新一次服务端结果为准。
  const [scan, setScan] = useState<CacheScan | null>(null)
  // 预览因统计未完成被挡回时记下请求体，扫完后自动补发一次同参数的预览
  const pendingPreviewRef = useRef<CleanupBody | null>(null)
  const activeScan = scan ?? status?.cache?.browser_data_scan ?? null
  const cacheScanning = activeScan?.state === 'scanning'

  // 页面加载时获取存储状态
  useEffect(() => {
    loadStatus()
  }, [])

  // 加载存储状态概览
  const loadStatus = async () => {
    try {
      setLoading(true)
      const data = await maintenanceApi.getStorageStatus()
      setStatus(data)
      // 概览已是服务端最新口径，本地轮询结果作废（否则旧的 scanning 会盖住新终值）
      setScan(null)
    } catch (error) {
      message.error('加载存储状态失败')
      console.error('加载状态失败', error)
    } finally {
      setLoading(false)
    }
  }

  // 打包版没有源码树，__pycache__ 恒为 0：置灰并标「不适用」（T02739）
  const pycacheApplicable = status?.cache?.pycache_applicable !== false

  // 执行缓存清理（override 供「统计完成后自动补发预览」使用）
  const handleCleanupCache = async (override?: CleanupBody) => {
    const body = override ?? { target: cacheForm.target, dry_run: cacheForm.dry_run }
    // 非预览模式必须走四要素确认（T02573）：原生 confirm 只能问「确认吗」，
    // 无法回答「删的是什么、有多少、能不能恢复」
    if (!body.dry_run) {
      // 统计未完成时「有多少」只能给半量，等于四要素失真（T02738）
      if (body.target !== 'pycache' && cacheScanning) {
        message.warning('浏览器数据仍在统计中，完成后才能给出准确的删除量，请稍候再执行')
        return
      }
      const confirmText = buildCacheConfirmText(body, status, pycacheApplicable)
      const ok = await confirmDanger({
        title: '确认清理缓存？',
        ...confirmText,
      })
      if (!ok) return
    }

    setCacheLoading(true)
    setCacheResult(null)
    try {
      const result = await maintenanceApi.cleanup('cache', body)
      setCacheResult(result)
      // 统计未完成：后端尚未评估出任何条目。记下请求体，扫完后自动补发同参数预览（T02738）
      if (result.pending) {
        pendingPreviewRef.current = body
        setScan(result.scan ?? null)
        message.info(
          `浏览器数据统计中（已遍历 ${result.scan?.scanned_entries ?? 0} 项），完成后自动展示预览结果`,
        )
        return
      }
      const count = result.cleaned?.length ?? 0
      // 预览也必须给反馈，否则用户无法判断"没反应"还是"没有可清理内容"（4.1-5）
      if (body.dry_run) {
        message.info(count > 0 ? `预览完成：将处理 ${count} 项缓存` : '预览完成：无需要清理的缓存')
        return
      }
      // 实际执行后刷新状态以反映最新存储情况（后端已同步让概览缓存失效，4.1-4）
      pendingPreviewRef.current = null
      setScan(null)
      await loadStatus()
      if (result.errors?.length) {
        message.error(`缓存清理未完成：${result.errors[0]}`)
      } else {
        message.success(count > 0 ? `缓存清理完成，共处理 ${count} 项` : '没有需要清理的缓存')
      }
    } catch (error) {
      setCacheResult({ errors: ['清理失败：' + String(error)] })
      message.error('缓存清理失败')
    } finally {
      setCacheLoading(false)
    }
  }

  // 统计未完成时轮询续跑：每次请求推进一小片，扫完刷新概览或自动补发预览（T02738）
  useEffect(() => {
    if (!cacheScanning) return
    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        const next = await maintenanceApi.getCacheScan()
        if (cancelled) return
        setScan(next)
        if (next.state === 'scanning') return
        const pendingBody = pendingPreviewRef.current
        pendingPreviewRef.current = null
        if (pendingBody) {
          await handleCleanupCache({ ...pendingBody, dry_run: true })
        } else {
          await loadStatus()
        }
      } catch {
        // 轮询偶发失败不弹错：进度仍在后端，用户再点预览即可接上
      }
    }, 1200)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [cacheScanning, scan])

  // 执行数据库清理
  const handleCleanupDatabase = async () => {
    // 数据库操作风险较高：确认框必须写清「按保留天数裁剪历史数据」这一真实语义与恢复成本
    if (!dbForm.dry_run) {
      const db = status?.db
      const d = dbForm.days
      // 各 target 的真实语义取自后端 cleanup_database 分支，vacuum 根本不删记录
      const dbAction: Record<string, string> = {
        all: `删除早于 ${d} 天的事件与未关联商品、清理已售商品关联，随后 VACUUM 压缩`,
        old_events: `删除早于 ${d} 天的事件记录`,
        old_items: `删除早于 ${d} 天且未关联任务的商品记录`,
        sold_items: '删除已售商品的关联记录（该分支不看天数）',
        vacuum: '执行 VACUUM 压缩数据库文件',
      }
      const ok = await confirmDanger({
        title: '确认清理数据库？',
        action: dbAction[dbForm.target ?? 'all'] ?? `清理数据库（${dbForm.target}）`,
        scope: dbForm.target === 'vacuum'
          ? '只重排数据库文件、回收空闲页；不删除任何业务记录，也不影响配置与浏览器登录态'
          : '裁剪数据库历史记录；不影响配置文件与浏览器登录态。确切条数请先用「仅预览」跑一次，预览结果即本次将处理的范围',
        count: db ? `当前库内 任务 ${db.tasks} / 商品 ${db.items} / 事件 ${db.events}（数据库 ${db.db_size_mb} MB）` : null,
        recovery: dbForm.target === 'vacuum'
          ? '压缩过程不可中断后回退，但记录不丢；数据库文件会变小，执行时间随库大小增长'
          : '不可直接撤销；可回到「数据库维护」用导出备份回滚，前提是本操作执行前已有可用备份',
      })
      if (!ok) return
    }

    setDbLoading(true)
    setDbResult(null)
    try {
      const result = await maintenanceApi.cleanup('database', {
        target: dbForm.target,
        days: dbForm.days,
        dry_run: dbForm.dry_run,
      })
      setDbResult(result)
      if (dbForm.dry_run) {
        const preview = result.total_deleted ?? 0
        message.info(
          preview > 0
            ? `预览完成：预计删除 ${preview} 条记录（未写库）`
            : '预览完成：当前保留天数内没有可删除的记录',
        )
        return
      }
      await loadStatus()
      if (result.errors?.length) {
        message.error(`数据库清理未完成：${result.errors[0]}`)
      } else {
        message.success(`数据库清理完成，共删除 ${result.total_deleted ?? 0} 条`)
      }
    } catch (error) {
      setDbResult({ errors: ['清理失败：' + String(error)] })
      message.error('数据库清理失败')
    } finally {
      setDbLoading(false)
    }
  }

  // 执行日志清理
  const handleCleanupLogs = async () => {
    if (!logForm.dry_run) {
      // 后端匹配条件是 (old_logs/all 且 mtime 超期) OR (large_logs/all 且 >10MB)——
      // 大文件分支不看时间，所以不能说「当日日志不会被删」
      const ok = await confirmDanger({
        title: '确认清理日志文件？',
        ...buildLogsConfirmText(logForm.target, logForm.days, status?.logs),
        recovery: '删除后历史日志无法找回；正在写入的当前日志文件若未被删除，只会因句柄占用继续追加',
      })
      if (!ok) return
    }

    setLogLoading(true)
    setLogResult(null)
    try {
      const result = await maintenanceApi.cleanup('logs', {
        target: logForm.target,
        days: logForm.days,
        dry_run: logForm.dry_run,
      })
      setLogResult(result)
      // 预览模式也必须给出明确反馈，否则用户无法判断是否有可清理内容
      // 优先判断 dry_run（预览）分支：默认开启预览，肯定条件更直观
      const count = result.cleaned?.length ?? 0
      if (logForm.dry_run) {
        message.info(
          count > 0
            ? `预览完成：将处理 ${count} 项日志，预计释放 ${result.total_freed_mb ?? 0} MB（未删除）`
            : '预览完成：无需要清理的日志文件',
        )
        return
      }
      await loadStatus()
      if (result.errors?.length) {
        message.error(`日志清理未完成：${result.errors[0]}`)
      } else {
        message.success(
          count > 0 ? `日志清理完成，共处理 ${count} 项，释放 ${result.total_freed_mb ?? 0} MB`
            : '没有需要清理的日志文件',
        )
      }
    } catch (error) {
      setLogResult({ errors: ['清理失败：' + String(error)] })
      message.error('日志清理失败')
    } finally {
      setLogLoading(false)
    }
  }

  // 渲染结果展示区域（成功信息和错误信息）
  const renderResult = (result: CleanupResult | null) => {
    if (!result) return null
    // dry_run 时后端回带的是「预计量」，必须用预览措辞 + 中性色渲染。
    // 旧实现按成功态渲染绿色「删除 0 条」——预览根本没写库，数字恒 0 却长得像执行结果（4.1-2）
    const preview = result.dry_run === true
    return (
      <div style={{ marginTop: 12 }}>
        {result.cleaned?.length ? (
          <div style={{ color: preview ? 'var(--xh-text-secondary)' : '#52c41a', marginBottom: 8 }}>
            <div>{preview ? '预览结果（未删除任何内容）' : '执行完成'}</div>
            {result.count !== undefined && (
              <div>{preview ? `将处理 ${result.count} 项` : `完成 ${result.count} 项`}</div>
            )}
            {result.total_deleted !== undefined && (
              <div>{preview ? `预计删除 ${result.total_deleted} 条` : `删除 ${result.total_deleted} 条`}</div>
            )}
            {result.total_freed_mb !== undefined && (
              <div>{preview ? `预计释放 ${result.total_freed_mb} MB` : `释放 ${result.total_freed_mb} MB`}</div>
            )}
            {result.cleaned.map((item) => (
              <Text key={item} type="secondary" style={{ fontSize: 12, display: 'block' }}>
                {item}
              </Text>
            ))}
          </div>
        ) : null}
        {result.errors?.length ? (
          <div style={{ color: '#ff4d4f' }}>
            {result.errors.map((err) => (
              <div key={err} style={{ fontSize: 12 }}>{err}</div>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="page-container">
      {/* 页面标题和刷新按钮 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 13 }}>
          缓存清理 · 数据库清理 · 日志清理
        </Text>
        <TipButton tip="刷新存储状态概览" icon={<ReloadOutlined />} onClick={loadStatus} loading={loading}>
          刷新状态
        </TipButton>
      </div>

      {/* 存储状态概览卡片 */}
      <Card style={{ marginBottom: 24 }}>
        <h3 style={{ marginBottom: 16, marginTop: 0 }}>存储状态</h3>
        <Row gutter={24}>
          {/* 数据库统计 */}
          <Col span={8}>
            <Statistic
              title="数据库"
              value={status?.db?.db_size_mb ?? 0}
              suffix="MB"
              valueStyle={{ color: '#FF6200' }}
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              {status?.db?.tasks ?? 0} 任务 · {status?.db?.items ?? 0} 商品 · {status?.db?.events ?? 0} 事件
            </div>
          </Col>

          {/* 日志文件统计 */}
          <Col span={8}>
            <Statistic
              title="日志文件"
              value={status?.logs?.total_size_mb ?? 0}
              suffix="MB"
              valueStyle={{ color: '#FF6200' }}
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              {status?.logs?.file_count ?? 0} 个文件{status?.logs?.oldest ? ` · 最早 ${status.logs.oldest}` : ''}
            </div>
          </Col>

          {/* 缓存统计 */}
          <Col span={8}>
            {cacheScanning ? (
              <Statistic
                title="缓存"
                value="统计中"
                valueStyle={{ color: '#FF6200' }}
              />
            ) : (
              <Statistic
                title="缓存"
                value={((status?.cache?.browser_data_mb ?? 0) + (status?.cache?.pycache_mb ?? 0)).toFixed(2)}
                suffix="MB"
                valueStyle={{ color: '#FF6200' }}
              />
            )}
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              {cacheScanning
                ? `浏览器数据统计中（已遍历 ${activeScan?.scanned_entries ?? 0} 项）`
                : `浏览器 ${status?.cache?.browser_data_mb ?? 0}MB/${status?.cache?.browser_data_files ?? 0} 个文件`}
              · 编译缓存 {pycacheApplicable
                ? `${status?.cache?.pycache_count ?? 0} 个目录/${status?.cache?.pycache_mb ?? 0}MB`
                : '不适用（打包版无源码字节码缓存）'}
            </div>
          </Col>
        </Row>
      </Card>

      {/* 三列清理卡片布局 */}
      <Row gutter={24}>
        {/* 缓存清理卡片 */}
        <Col span={8}>
          <Card
            title={
              <Space>
                <ClearOutlined style={{ color: '#FF6200' }} />
                <span>缓存清理</span>
              </Space>
            }
          >
            <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>
              {pycacheApplicable
                ? '清理 Python 字节码缓存与浏览器用户数据目录'
                : '清理浏览器用户数据目录'}
              {status?.cache?.browser_data_path ? `（${status.cache.browser_data_path}）` : ''}
              {pycacheApplicable
                ? '——后者保存闲鱼登录 Cookie，删除后需重新扫码登录'
                : '——其中保存闲鱼登录 Cookie，删除后需重新扫码登录'}
            </Text>

            {/* 大目录在后台分批统计（T02738）：先给进度，不把请求拖成空白等待 */}
            {cacheScanning && (
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
                message={`浏览器数据统计中：已遍历 ${activeScan?.scanned_entries ?? 0} 项`}
                description="统计在后台分批进行、秒级回传进度；完成后自动刷新，无需重复点击。统计完成前不能执行真实删除。"
              />
            )}

            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                清理范围
              </Text>
              {/* 4.1-3：旧标签「临时文件」名不副实——该分支实删 __pycache__，
                  且从不删任何临时文件；名与实在此对齐（选项表与移动端共用） */}
              <Select
                value={cacheForm.target}
                onChange={(value) => setCacheForm({ ...cacheForm, target: value })}
                style={{ width: '100%' }}
                options={cacheTargetOptions(pycacheApplicable)}
              />
              {!pycacheApplicable && (
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                  {PYCACHE_NOT_APPLICABLE_HINT}
                </Text>
              )}
            </div>

            <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Switch
                checked={cacheForm.dry_run}
                onChange={(checked) => setCacheForm({ ...cacheForm, dry_run: checked })}
              />
              <Text style={{ fontSize: 13 }}>仅预览（不实际执行）</Text>
              {!cacheForm.dry_run && <Tag color="red">将执行真实删除</Tag>}
            </div>

            <TipButton
              tip="清理所选范围的缓存（预览或真实执行）"
              type="primary"
              icon={<DeleteOutlined />}
              block
              loading={cacheLoading}
              onClick={() => { void handleCleanupCache() }}
              style={{ backgroundColor: cacheForm.dry_run ? undefined : '#ff4d4f' }}
            >
              清理缓存
            </TipButton>

            {renderResult(cacheResult)}
          </Card>
        </Col>

        {/* 数据库清理卡片 */}
        <Col span={8}>
          <Card
            title={
              <Space>
                <DatabaseOutlined style={{ color: '#FF6200' }} />
                <span>数据库清理</span>
              </Space>
            }
          >
            <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>
              清理冗余数据并压缩数据库
            </Text>

            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                清理范围
              </Text>
              <Select
                value={dbForm.target}
                onChange={(value) => setDbForm({ ...dbForm, target: value })}
                style={{ width: '100%' }}
                options={[
                  { value: 'all', label: '全部清理' },
                  { value: 'old_events', label: '旧事件记录' },
                  { value: 'old_items', label: '旧未关联商品' },
                  { value: 'sold_items', label: '已售商品关联' },
                  { value: 'vacuum', label: 'VACUUM 压缩' },
                ]}
              />
            </div>

            {/* 4.1-5：保留天数只对受 cutoff 约束的分支有意义；
                sold_items/vacuum 后端根本不读该参数，仍显示可编辑输入框＝假可配置 */}
            {(dbForm.target === 'all' || dbForm.target === 'old_events' || dbForm.target === 'old_items') && (
              <div style={{ marginBottom: 12 }}>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                  保留天数
                </Text>
                {/* addonAfter 已废弃，改用 Space.Compact 包装静态文本（antd v5） */}
                <Space.Compact style={{ width: '100%' }}>
                  <InputNumber
                    value={dbForm.days}
                    onChange={(value) => setDbForm({ ...dbForm, days: value ?? 30 })}
                    min={1}
                    max={365}
                    style={{ flex: 1 }}
                  />
                  <Button disabled>天</Button>
                </Space.Compact>
              </div>
            )}

            {/* VACUUM 是长耗时且阻塞写入的操作，不提前说明＝用户以为"卡住了"（4.1-5） */}
            {(dbForm.target === 'vacuum' || dbForm.target === 'all') && (
              <Alert
                type="warning"
                showIcon
                style={{ marginBottom: 12 }}
                message="VACUUM 期间数据库写入受阻"
                description="该操作会重排整个库文件，耗时随库体积增长；执行期间采集、抢单等写入可能等待或失败，建议在空闲时段进行。"
              />
            )}

            <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Switch
                checked={dbForm.dry_run}
                onChange={(checked) => setDbForm({ ...dbForm, dry_run: checked })}
              />
              <Text style={{ fontSize: 13 }}>仅预览（不实际执行）</Text>
              {!dbForm.dry_run && <Tag color="red">将执行真实删除</Tag>}
            </div>

            <TipButton
              tip="清理数据库冗余数据（预览或真实执行）"
              type="primary"
              icon={<DatabaseOutlined />}
              block
              loading={dbLoading}
              onClick={handleCleanupDatabase}
              style={{ backgroundColor: dbForm.dry_run ? undefined : '#ff4d4f' }}
            >
              清理数据库
            </TipButton>

            {renderResult(dbResult)}
          </Card>
        </Col>

        {/* 日志清理卡片 */}
        <Col span={8}>
          <Card
            title={
              <Space>
                <FileTextOutlined style={{ color: '#FF6200' }} />
                <span>日志清理</span>
              </Space>
            }
          >
            <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>
              清理旧日志文件释放磁盘空间
            </Text>

            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                清理规则
              </Text>
              <Select
                value={logForm.target}
                onChange={(value) => setLogForm({ ...logForm, target: value })}
                style={{ width: '100%' }}
                options={[
                  { value: 'old_logs', label: '按天数清理' },
                  { value: 'large_logs', label: '大文件清理 (>10MB)' },
                  { value: 'all', label: '全部清理' },
                ]}
              />
            </div>

            {/* 仅在选择按天数或全部清理时显示天数输入框 */}
            {(logForm.target === 'old_logs' || logForm.target === 'all') && (
              <div style={{ marginBottom: 12 }}>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                  保留天数
                </Text>
                {/* addonAfter 已废弃，改用 Space.Compact 包装静态文本（antd v5） */}
                <Space.Compact style={{ width: '100%' }}>
                  <InputNumber
                    value={logForm.days}
                    onChange={(value) => setLogForm({ ...logForm, days: value ?? 7 })}
                    min={1}
                    max={365}
                    style={{ flex: 1 }}
                  />
                  <Button disabled>天</Button>
                </Space.Compact>
              </div>
            )}

            <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Switch
                checked={logForm.dry_run}
                onChange={(checked) => setLogForm({ ...logForm, dry_run: checked })}
              />
              <Text style={{ fontSize: 13 }}>仅预览（不实际执行）</Text>
              {!logForm.dry_run && <Tag color="red">将执行真实删除</Tag>}
            </div>

            <TipButton
              tip="清理旧日志文件释放磁盘空间"
              type="primary"
              icon={<FileTextOutlined />}
              block
              loading={logLoading}
              onClick={handleCleanupLogs}
              style={{ backgroundColor: logForm.dry_run ? undefined : '#ff4d4f' }}
            >
              清理日志
            </TipButton>

            {renderResult(logResult)}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
