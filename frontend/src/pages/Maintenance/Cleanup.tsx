import { useEffect, useState } from 'react'
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
} from '../../api'

const { Text } = Typography

// 表单状态类型
// CleanupBody 已从 API 层导入，此处无需重复定义

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
    } catch (error) {
      message.error('加载存储状态失败')
      console.error('加载状态失败', error)
    } finally {
      setLoading(false)
    }
  }

  // 执行缓存清理
  const handleCleanupCache = async () => {
    // 非预览模式需要用户确认，防止误操作导致数据丢失
    if (!cacheForm.dry_run && !globalThis.confirm('确认清理缓存？此操作不可撤销。')) {
      return
    }

    setCacheLoading(true)
    setCacheResult(null)
    try {
      const result = await maintenanceApi.cleanup('cache', {
        target: cacheForm.target,
        dry_run: cacheForm.dry_run,
      })
      setCacheResult(result)
      // 实际执行后刷新状态以反映最新存储情况
      if (!cacheForm.dry_run) {
        await loadStatus()
        message.success('缓存清理完成')
      }
    } catch (error) {
      setCacheResult({ errors: ['清理失败：' + String(error)] })
      message.error('缓存清理失败')
    } finally {
      setCacheLoading(false)
    }
  }

  // 执行数据库清理
  const handleCleanupDatabase = async () => {
    // 数据库操作风险较高，必须二次确认
    if (!dbForm.dry_run && !globalThis.confirm('确认清理数据库？建议先备份数据。此操作不可撤销。')) {
      return
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
      if (!dbForm.dry_run) {
        await loadStatus()
        message.success('数据库清理完成')
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
    if (!logForm.dry_run && !globalThis.confirm('确认清理日志文件？此操作不可撤销。')) {
      return
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
        message.info(count > 0 ? `预览完成：将处理 ${count} 项日志` : '预览完成：无需要清理的日志文件')
      } else {
        await loadStatus()
        message.success(count > 0 ? `日志清理完成，共处理 ${count} 项` : '没有需要清理的日志文件')
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

    return (
      <div style={{ marginTop: 12 }}>
        {result.cleaned?.length ? (
          <div style={{ color: '#52c41a', marginBottom: 8 }}>
            {result.count !== undefined && <div>完成 {result.count} 项</div>}
            {result.total_deleted !== undefined && <div>删除 {result.total_deleted} 条</div>}
            {result.total_freed_mb !== undefined && <div>释放 {result.total_freed_mb} MB</div>}
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
        <div>
          <h2 style={{ margin: 0 }}>系统维护</h2>
          <Text type="secondary" style={{ fontSize: 13 }}>
            缓存清理 · 数据库清理 · 日志清理
          </Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={loadStatus} loading={loading}>
          刷新状态
        </Button>
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
            <Statistic
              title="缓存"
              value={((status?.cache?.browser_data_mb ?? 0) + (status?.cache?.pycache_mb ?? 0)).toFixed(2)}
              suffix="MB"
              valueStyle={{ color: '#FF6200' }}
            />
            <div style={{ fontSize: 12, color: 'var(--xh-text-tertiary)', marginTop: 4 }}>
              浏览器 {status?.cache?.browser_data_mb ?? 0}MB · Py缓存 {status?.cache?.pycache_count ?? 0}个/{status?.cache?.pycache_mb ?? 0}MB
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
              清理浏览器数据目录和 Python 缓存文件
            </Text>

            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                清理范围
              </Text>
              <Select
                value={cacheForm.target}
                onChange={(value) => setCacheForm({ ...cacheForm, target: value })}
                style={{ width: '100%' }}
                options={[
                  { value: 'all', label: '全部缓存' },
                  { value: 'browser_data', label: '浏览器数据' },
                  { value: 'temp', label: '临时文件' },
                ]}
              />
            </div>

            <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Switch
                checked={cacheForm.dry_run}
                onChange={(checked) => setCacheForm({ ...cacheForm, dry_run: checked })}
              />
              <Text style={{ fontSize: 13 }}>仅预览（不实际执行）</Text>
              {!cacheForm.dry_run && <Tag color="red">将执行真实删除</Tag>}
            </div>

            <Button
              type="primary"
              icon={<DeleteOutlined />}
              block
              loading={cacheLoading}
              onClick={handleCleanupCache}
              style={{ backgroundColor: cacheForm.dry_run ? undefined : '#ff4d4f' }}
            >
              清理缓存
            </Button>

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

            <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Switch
                checked={dbForm.dry_run}
                onChange={(checked) => setDbForm({ ...dbForm, dry_run: checked })}
              />
              <Text style={{ fontSize: 13 }}>仅预览（不实际执行）</Text>
              {!dbForm.dry_run && <Tag color="red">将执行真实删除</Tag>}
            </div>

            <Button
              type="primary"
              icon={<DatabaseOutlined />}
              block
              loading={dbLoading}
              onClick={handleCleanupDatabase}
              style={{ backgroundColor: dbForm.dry_run ? undefined : '#ff4d4f' }}
            >
              清理数据库
            </Button>

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

            <Button
              type="primary"
              icon={<FileTextOutlined />}
              block
              loading={logLoading}
              onClick={handleCleanupLogs}
              style={{ backgroundColor: logForm.dry_run ? undefined : '#ff4d4f' }}
            >
              清理日志
            </Button>

            {renderResult(logResult)}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
