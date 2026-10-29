import { useEffect, useState, useRef, useCallback } from 'react'
import {
  Card,
  Space,
  Tag,
  Typography,
  Select,
  Input,
  InputNumber,
  Alert,
  Row,
  Col,
  Switch,
  Radio,
  Steps,
  message,
  Spin,
} from 'antd'
import {
  PlayCircleOutlined,
  StopOutlined,
  LinkOutlined,
  CloudServerOutlined,
  SafetyCertificateOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { tunnelApi, type TunnelStatus, type TunnelConfig, type TunnelDownloadError, type TunnelTailscaleAuthError } from '../../api'
import { TUNNEL_PROVIDERS, TUNNEL_PROVIDER_OPTIONS } from './tunnelProviders'
import { TipButton } from '@/components/TipButton'
import { confirmDanger } from '@/components/DangerSummary'

const { Text, Paragraph } = Typography

// Named Tunnel 向导步骤定义
const WIZARD_STEPS = [
  { title: '授权登录', description: 'Cloudflare 账号授权' },
  { title: '创建隧道', description: '生成隧道凭证' },
  { title: '配置 DNS', description: '绑定固定域名' },
]

// 处理 cloudflared 登录轮询结果。提取为模块级函数以降低 NamedTunnelWizard 认知复杂度
async function pollCloudflareLogin(callbacks: {
  onStop: () => void
  onConfigChanged: () => void
  onAuthUrl: (url: string) => void
}) {
  try {
    const result = await tunnelApi.cloudflareLoginStatus()
    if (result.status === 'success') {
      callbacks.onStop()
      message.success(result.message || '授权成功')
      callbacks.onConfigChanged()
    } else if (result.status === 'failed') {
      callbacks.onStop()
      message.error(result.message || '登录失败')
      if (result.output) {
        console.error('cloudflared login 输出:', result.output)
      }
      if (result.checked_paths?.length) {
        console.error('已检查的 cert.pem 路径:', result.checked_paths)
      }
    } else if (result.status === 'idle') {
      // provider 被重置（服务重启等），停止轮询
      callbacks.onStop()
      message.warning('登录会话已失效，请重新点击执行登录')
    } else if (result.auth_url) {
      // waiting：更新授权 URL（start 时可能未拿到，轮询时才拿到）
      callbacks.onAuthUrl(result.auth_url)
    }
  } catch (error: any) {
    callbacks.onStop()
    message.error(error?.response?.data?.detail || '轮询登录状态失败')
  }
}

// 根据已配置字段自动判断当前步骤。提取为模块级函数避免嵌套三元（S3358）与否定条件（S7735），并降低组件复杂度（S3776）
function getCurrentStep(config: TunnelConfig): number {
  if (config.cert_file) {
    if (config.tunnel_id) {
      if (config.hostname) return 3
      return 2
    }
    return 1
  }
  return 0
}

// ============ T02590 / PRD 4.6：表单脏检测与后端驱动文案（纯函数，便于单测） ============

export interface TunnelFormState {
  provider: string
  local_port: number
  cpolar_authtoken: string
  binary_path: string
  auto_start: boolean
  tunnel_mode: 'quick' | 'named'
}

// 与 handleSaveConfig 提交字段一一对应；向导落库的字段（tunnel_name/tunnel_id/hostname 等）
// 不在此列，因为它们在向导里即时保存、表单不承载编辑入口。
export const TUNNEL_FORM_FIELD_LABELS: Record<keyof TunnelFormState, string> = {
  provider: '穿透服务',
  local_port: '本地端口',
  cpolar_authtoken: 'Authtoken',
  binary_path: '二进制路径',
  auto_start: '开机自启动',
  tunnel_mode: '隧道模式',
}

/**
 * 列出「表单值与已保存配置不一致」的字段（4.6-2）。
 *
 * 旧实现只在 provider 变化时才先保存配置，其余字段（端口/模式/自启动/二进制路径）改了
 * 直接点「启动隧道」，启动用的仍是旧配置——用户以为在跑刚设置的东西，实际跑的是上一次的。
 * authtoken 只在非空时算脏（后端约定：空串=不修改）。
 */
export function tunnelDirtyFields(config: TunnelConfig | null, form: TunnelFormState): string[] {
  if (config == null) return []
  const dirty: string[] = []
  if (form.provider !== config.provider) dirty.push(TUNNEL_FORM_FIELD_LABELS.provider)
  if (form.local_port !== config.local_port) dirty.push(TUNNEL_FORM_FIELD_LABELS.local_port)
  if (form.binary_path !== config.binary_path) dirty.push(TUNNEL_FORM_FIELD_LABELS.binary_path)
  if (form.auto_start !== config.auto_start) dirty.push(TUNNEL_FORM_FIELD_LABELS.auto_start)
  if (form.tunnel_mode !== config.tunnel_mode) dirty.push(TUNNEL_FORM_FIELD_LABELS.tunnel_mode)
  if (form.cpolar_authtoken.trim() !== '') dirty.push(TUNNEL_FORM_FIELD_LABELS.cpolar_authtoken)
  return dirty
}

/**
 * 保存回执文案（4.6-1 后端侧）：以 `POST /config` 返回的 message 为准，
 * 前端不再自行判断「保存是否断当前隧道」。回退分支只在后端未回传时启用，
 * 且回退文案同样区分运行态，不写「下次启动生效」这种运行态假话。
 */
export function buildTunnelSaveCopy(
  result: { message?: string; tunnel_was_running?: boolean } | null | undefined,
  autoStart: boolean,
  wasRunning: boolean,
): { level: 'success' | 'warning'; text: string } {
  if (autoStart) {
    return { level: 'success', text: '配置已同步，正在启动隧道...' }
  }
  if (result?.message) {
    return { level: result.tunnel_was_running ? 'warning' : 'success', text: result.message }
  }
  const running = result?.tunnel_was_running ?? wasRunning
  return running
    ? { level: 'warning', text: '配置已保存；当前隧道已断开，公网地址失效，需要手动重新启动隧道' }
    : { level: 'success', text: '配置已保存，下次启动隧道时生效（当前无运行中的隧道）' }
}

/**
 * 向导步骤 ②③ 被禁用时的原因说明（4.6-4）。
 * 旧实现只有 `opacity:0.5`，鼠标点上去既不解释为什么不能点，也不说要点哪儿才能解锁。
 */
export function wizardLockedTips(config: TunnelConfig): { create: string; dns: string } {
  return {
    create: config.cert_file
      ? '创建命名隧道（或重新创建）'
      : '暂不可用：需先完成 ① 授权登录（拿到 cert.pem 后才能创建隧道）',
    dns: config.tunnel_id
      ? '配置 DNS 路由（CNAME 记录）'
      : '暂不可用：需先完成 ② 创建隧道（拿到 tunnel_id 后才能绑定域名）',
  }
}

/** 停止隧道的确认四要素文案（4.6-5：停止是破坏性操作，且地址会变） */
export function buildTunnelStopCopy(provider: string, publicUrl: string | null) {
  return {
    title: '停止当前隧道？',
    action: '停掉正在运行的隧道进程',
    scope: `公网地址 ${publicUrl || '（未获取到）'}，本地端口转发到已保存的 local_port`,
    count: '正在运行的隧道 1 条（' + provider + '）',
    recovery: publicUrl
      ? '隧道停止后该地址立即无法访问；重新启动会拿到新的随机地址（快速模式），已分享出去的链接需要重新提供。固定域名模式重启后地址不变。'
      : '重新启动后需重新复制新的公网地址。',
  }
}

// 执行 Cloudflare 登录流程。提取为模块级函数降低 NamedTunnelWizard 认知复杂度（S3776），
// 通过 callbacks 注入状态 setter，避免直接依赖组件闭包
async function doCloudflareLogin(handlers: {
  onStartLoading: () => void
  onResetAuthUrl: () => void
  onStopPoll: () => void
  onSetAuthUrl: (url: string) => void
  onStartPoll: () => void
  onEndLoading: () => void
}) {
  handlers.onStartLoading()
  handlers.onResetAuthUrl()
  handlers.onStopPoll()
  try {
    const result = await tunnelApi.cloudflareLoginStart()
    if (result.status === 'failed') {
      message.error(result.message || '登录启动失败')
      if (result.output) {
        console.error('cloudflared login 输出:', result.output)
      }
      return
    }
    // waiting：显示授权 URL，开始轮询
    if (result.auth_url) {
      handlers.onSetAuthUrl(result.auth_url)
    }
    handlers.onStartPoll()
  } catch (error: any) {
    message.error(error?.response?.data?.detail || '登录启动失败')
  } finally {
    handlers.onEndLoading()
  }
}

// Named Tunnel 配置向导组件
function NamedTunnelWizard({
  config,
  onConfigChanged,
}: {
  // readonly 修饰符满足 S6759：组件 props 在运行时不应变更
  readonly config: TunnelConfig
  readonly onConfigChanged: () => void
}) {
  const [loginLoading, setLoginLoading] = useState(false)
  const [loginAuthUrl, setLoginAuthUrl] = useState<string | null>(null)
  const [loginPolling, setLoginPolling] = useState(false)
  const [createName, setCreateName] = useState(config.tunnel_name || '')
  const [createLoading, setCreateLoading] = useState(false)
  const [dnsHostname, setDnsHostname] = useState(config.hostname || '')
  const [dnsLoading, setDnsLoading] = useState(false)

  const loginPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 根据已配置字段自动判断当前步骤（提取为模块级函数 getCurrentStep）
  const currentStep = getCurrentStep(config)

  const stopLoginPoll = useCallback(() => {
    if (loginPollRef.current) {
      clearInterval(loginPollRef.current)
      loginPollRef.current = null
    }
    setLoginPolling(false)
  }, [])

  // 组件卸载时清理轮询，防止内存泄漏和卸载后 setState
  useEffect(() => {
    return () => stopLoginPoll()
  }, [stopLoginPoll])

  // 提取为 useCallback：原 startLoginPoll 内嵌 setInterval -> pollCloudflareLogin -> onAuthUrl lambda 共 5 层触发 S2004
  // 独立后 startLoginPoll 内只剩 setInterval -> pollCloudflareLogin 共 4 层，符合阈值
  const handleAuthUrl = useCallback((url: string) => {
    setLoginAuthUrl((prev) => prev ?? url)
  }, [])

  const startLoginPoll = useCallback(() => {
    stopLoginPoll()
    setLoginPolling(true)
    loginPollRef.current = setInterval(() => pollCloudflareLogin({
      onStop: stopLoginPoll,
      onConfigChanged,
      onAuthUrl: handleAuthUrl,
    }), 2500)
  }, [stopLoginPoll, onConfigChanged, handleAuthUrl])

  const handleLogin = () => doCloudflareLogin({
    onStartLoading: () => setLoginLoading(true),
    onResetAuthUrl: () => setLoginAuthUrl(null),
    onStopPoll: stopLoginPoll,
    onSetAuthUrl: setLoginAuthUrl,
    onStartPoll: startLoginPoll,
    onEndLoading: () => setLoginLoading(false),
  })

  const handleCreate = async () => {
    if (!createName.trim()) {
      message.warning('请输入隧道名称')
      return
    }
    setCreateLoading(true)
    try {
      const result = await tunnelApi.cloudflareCreate({ tunnel_name: createName.trim() })
      message.success(result.message)
      onConfigChanged()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '创建隧道失败')
    } finally {
      setCreateLoading(false)
    }
  }

  const handleRouteDns = async () => {
    if (!dnsHostname.trim()) {
      message.warning('请输入固定域名')
      return
    }
    setDnsLoading(true)
    try {
      const result = await tunnelApi.cloudflareRouteDns({
        tunnel_name_or_id: config.tunnel_name || config.tunnel_id,
        hostname: dnsHostname.trim(),
      })
      message.success(result.message)
      onConfigChanged()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || 'DNS 路由配置失败')
    } finally {
      setDnsLoading(false)
    }
  }

  // 登录按钮文案：优先显示轮询状态，其次按是否已配置区分
  let loginButtonText = '执行登录'
  if (loginPolling) {
    loginButtonText = '等待授权中...'
  } else if (config.cert_file) {
    loginButtonText = '重新授权'
  }

  // 4.6-4：置灰步骤必须说清「被什么卡住」，而不是只降透明度
  const lockedTips = wizardLockedTips(config)

  return (
    <Card
      title={
        <Space>
          <SafetyCertificateOutlined />
          <Text>固定域名配置向导</Text>
          {currentStep === 3 && (
            <Tag color="success" icon={<CheckCircleOutlined />}>已配置</Tag>
          )}
        </Space>
      }
      size="small"
      style={{ marginTop: 8 }}
    >
      {/* 4.6-4：本页同时存在两套持久化模型，口径写在最显眼处而不是留给用户猜 */}
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 12 }}
        message="向导的每一步点了就直接写入配置，无需再点下方「保存配置」"
        description={
          <Text type="secondary" style={{ fontSize: 12 }}>
            上方「Provider 配置」表单是草稿态——改完必须点「保存配置」才落库；
            本向导（授权 / 创建隧道 / 配置 DNS）是即时生效态——每完成一步立即持久化，
            与表单的保存按钮互不相干。混用时的常见误解是「向导做完了还要点保存」，实际不需要。
          </Text>
        }
      />
      <Steps
        current={currentStep}
        size="small"
        items={WIZARD_STEPS}
        style={{ marginBottom: 16 }}
      />

      {/* 步骤 1：授权登录 */}
      <div style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space>
            <Text strong>① 授权登录</Text>
            {config.cert_file && <Tag color="success" icon={<CheckCircleOutlined />}>已完成</Tag>}
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            点击下方按钮，浏览器将打开 Cloudflare 授权页面。授权后自动生成 cert.pem 证书文件。
          </Text>
          {config.cert_file && (
            <Text code copyable style={{ fontSize: 12 }}>{config.cert_file}</Text>
          )}
          {/* 轮询中：显示等待提示和授权链接（浏览器未自动打开时可手动点击） */}
          {loginPolling && (
            <Alert
              type="info"
              showIcon
              icon={<LoadingOutlined />}
              message="等待 Cloudflare 授权..."
              description={
                <Space direction="vertical" size="small">
                  <Text>请在浏览器中完成 Cloudflare 账号授权，完成后此页面将自动检测到。</Text>
                  {loginAuthUrl && (
                    <Space>
                      <Text type="secondary">浏览器未打开？</Text>
                      <a href={loginAuthUrl} target="_blank" rel="noopener noreferrer">
                        手动打开授权链接
                      </a>
                    </Space>
                  )}
                </Space>
              }
            />
          )}
          <TipButton
            tip="执行 Cloudflare 授权登录"
            type={config.cert_file ? 'default' : 'primary'}
            icon={loginLoading || loginPolling ? <LoadingOutlined /> : undefined}
            loading={loginLoading}
            onClick={handleLogin}
            disabled={loginLoading || loginPolling}
          >
            {loginButtonText}
          </TipButton>
        </Space>
      </div>

      {/* 步骤 2：创建隧道 */}
      <div style={{ marginBottom: 16, opacity: config.cert_file ? 1 : 0.5 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space>
            <Text strong>② 创建隧道</Text>
            {config.tunnel_id && <Tag color="success" icon={<CheckCircleOutlined />}>已完成</Tag>}
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            输入隧道名称（如 xianyu-hunter），系统将创建命名隧道并生成凭证文件。
          </Text>
          <Row gutter={8}>
            <Col flex="auto">
              <Input
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="隧道名称（英文 + 连字符）"
                disabled={!config.cert_file || createLoading}
              />
            </Col>
            <Col>
              <TipButton
                tip={lockedTips.create}
                type={config.tunnel_id ? 'default' : 'primary'}
                icon={createLoading ? <LoadingOutlined /> : undefined}
                loading={createLoading}
                onClick={handleCreate}
                disabled={!config.cert_file || createLoading}
              >
                {config.tunnel_id ? '重新创建' : '创建隧道'}
              </TipButton>
            </Col>
          </Row>
          {config.tunnel_id && (
            <Space direction="vertical" size={0} style={{ width: '100%' }}>
              <Text code copyable style={{ fontSize: 12 }}>ID: {config.tunnel_id}</Text>
              <Text code copyable style={{ fontSize: 12 }}>{config.credentials_file}</Text>
            </Space>
          )}
        </Space>
      </div>

      {/* 步骤 3：配置 DNS */}
      <div style={{ opacity: config.tunnel_id ? 1 : 0.5 }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space>
            <Text strong>③ 配置 DNS</Text>
            {config.hostname && <Tag color="success" icon={<CheckCircleOutlined />}>已完成</Tag>}
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            输入已托管在 Cloudflare 的域名子域（如 app.example.com），系统将自动创建 CNAME 记录。
          </Text>
          <Row gutter={8}>
            <Col flex="auto">
              <Input
                value={dnsHostname}
                onChange={(e) => setDnsHostname(e.target.value)}
                placeholder="固定域名（如 app.example.com）"
                disabled={!config.tunnel_id || dnsLoading}
              />
            </Col>
            <Col>
              <TipButton
                tip={lockedTips.dns}
                type={config.hostname ? 'default' : 'primary'}
                icon={dnsLoading ? <LoadingOutlined /> : undefined}
                loading={dnsLoading}
                onClick={handleRouteDns}
                disabled={!config.tunnel_id || dnsLoading}
              >
                {config.hostname ? '重新配置' : '配置路由'}
              </TipButton>
            </Col>
          </Row>
          {config.hostname && (
            <Text type="success" strong>
              固定地址：https://{config.hostname}
            </Text>
          )}
        </Space>
      </div>
    </Card>
  )
}

// S3776：保存按钮提示抽成模块级函数，主组件不再保留 if/else-if 分支
function resolveSaveButtonTip(config: TunnelConfig | null, isRunning: boolean): string {
  if (config == null) return '配置未加载成功，暂时无法保存（请先点上方「重试」）'
  if (isRunning) return '保存隧道配置（当前隧道会立即断开，需重新启动）'
  return '保存隧道配置（下次启动生效）'
}

export default function Tunnel() {
  const [status, setStatus] = useState<TunnelStatus | null>(null)
  const [config, setConfig] = useState<TunnelConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)

  // 配置表单（本地草稿态：点「保存配置」或「启动隧道」时才落库；固定域名向导是即时落库）
  const [formProvider, setFormProvider] = useState('cloudflare')
  const [formAuthtoken, setFormAuthtoken] = useState('')
  const [formPort, setFormPort] = useState(0)
  const [formBinaryPath, setFormBinaryPath] = useState('')
  const [formAutoStart, setFormAutoStart] = useState(false)
  const [formTunnelMode, setFormTunnelMode] = useState<'quick' | 'named'>('quick')

  // 下载失败指引
  const [downloadError, setDownloadError] = useState<TunnelDownloadError | null>(null)
  // Tailscale Funnel 首次授权失败指引
  const [tailscaleAuthError, setTailscaleAuthError] = useState<TunnelTailscaleAuthError | null>(null)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 4.6-3：加载失败必须可见。旧实现只 console.error，配置加载失败（如 401）时
  // 表单回落到默认 cloudflare、向导整块消失，页面却照常显示「○ 已停止」——
  // 用户读到的是「隧道是停的」，真相是「我根本没读到你现在的状态」。
  const [loadErrors, setLoadErrors] = useState<{ status: string | null; config: string | null }>({
    status: null,
    config: null,
  })

  const describeError = (error: any, fallback: string) => {
    const data = error?.response?.data
    const detail = typeof data === 'string' ? data : data?.detail
    if (error?.response?.status === 401) return '未登录或登录已过期（401），请重新登录后重试'
    return detail || fallback
  }

  // 加载状态
  const loadStatus = useCallback(async () => {
    try {
      const data = await tunnelApi.getStatus()
      setStatus(data)
      setLoadErrors((prev) => ({ ...prev, status: null }))
    } catch (error) {
      console.error('加载隧道状态失败', error)
      setLoadErrors((prev) => ({ ...prev, status: describeError(error, '隧道状态加载失败') }))
    }
  }, [])

  // 加载配置
  const loadConfig = useCallback(async () => {
    try {
      const data = await tunnelApi.getConfig()
      setConfig(data)
      setFormProvider(data.provider)
      setFormPort(data.local_port)
      setFormBinaryPath(data.binary_path)
      setFormAutoStart(data.auto_start)
      setFormTunnelMode(data.tunnel_mode)
      // authtoken 不回显明文，已配置时显示占位
      setFormAuthtoken('')
      setLoadErrors((prev) => ({ ...prev, config: null }))
    } catch (error) {
      // 401 表示未登录，配置端点需认证
      console.error('加载隧道配置失败', error)
      setLoadErrors((prev) => ({ ...prev, config: describeError(error, '隧道配置加载失败') }))
    }
  }, [])

  const reloadAll = useCallback(async () => {
    setLoading(true)
    await Promise.all([loadStatus(), loadConfig()])
    setLoading(false)
  }, [loadStatus, loadConfig])

  // 初始加载
  useEffect(() => {
    void reloadAll()
  }, [reloadAll])

  // 运行中时轮询状态（检测进程退出、URL 变化）
  useEffect(() => {
    if (status?.status === 'running') {
      pollRef.current = setInterval(loadStatus, 3000)
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [status?.status, loadStatus])

  // 4.6-2：表单是否脏（任一字段与已保存配置不一致）
  const dirtyFields = tunnelDirtyFields(config, {
    provider: formProvider,
    local_port: formPort,
    cpolar_authtoken: formAuthtoken,
    binary_path: formBinaryPath,
    auto_start: formAutoStart,
    tunnel_mode: formTunnelMode,
  })

  // 启动隧道
  const handleStart = async () => {
    // 4.6-2：任一字段脏都先落库再启动。
    // 旧实现只在 provider 变化时同步配置，端口/隧道模式/自启动改了直接点启动，
    // 跑起来的仍是上一次保存的配置——「我改的没生效」且界面上没有任何提示。
    if (config && dirtyFields.length > 0) {
      const ok = await handleSaveConfig(true)
      if (!ok) return
    }
    setStarting(true)
    setDownloadError(null)
    setTailscaleAuthError(null)
    try {
      const data = await tunnelApi.start()
      setStatus(data)
      message.success('隧道已启动')
    } catch (error: any) {
      // 检查是否为下载失败错误
      const errData = error?.response?.data
      if (errData?.error_type === 'binary_download_failed') {
        setDownloadError(errData)
        message.error('二进制下载失败，请按提示手动放置')
      } else if (errData?.error_type === 'tailscale_funnel_auth') {
        // Tailscale 首次启用 Funnel 需用户在浏览器完成授权
        setTailscaleAuthError(errData)
        message.error('需要在 Tailscale 管理后台完成授权')
      } else {
        message.error(errData?.detail || '隧道启动失败')
      }
    } finally {
      setStarting(false)
    }
  }

  // 停止隧道
  // 4.6-5：停止是破坏性操作且地址会变（快速模式下重启即换 URL），
  // 旧实现一键直接断，用户是在「试一下」的心态下把现网连接掐掉的。
  const handleStop = async () => {
    // 运行中的 provider 以后端 status 为准，表单值只是草稿
    const copy = buildTunnelStopCopy(status?.provider || formProvider, status?.public_url ?? null)
    const confirmed = await confirmDanger({
      title: copy.title,
      action: copy.action,
      scope: copy.scope,
      count: copy.count,
      recovery: copy.recovery,
    })
    if (!confirmed) return
    setStopping(true)
    try {
      const data = await tunnelApi.stop()
      setStatus(data)
      message.success('隧道已关闭，公网地址已失效')
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '停止失败')
    } finally {
      setStopping(false)
    }
  }

  // 保存配置
  // 生效语义由后端回执驱动（T02590 / 4.6-1）：后端在保存时会重建隧道服务，
  // 运行态保存等于当场断线——这句话只能由知道真相的一侧说，前端不再自行猜测。
  const handleSaveConfig = async (autoStart = false): Promise<boolean> => {
    setSavingConfig(true)
    try {
      const result = await tunnelApi.saveConfig({
        provider: formProvider,
        local_port: formPort,
        // 空串表示不修改已有 authtoken
        cpolar_authtoken: formAuthtoken,
        binary_path: formBinaryPath,
        auto_start: formAutoStart,
        // 保留已有 named tunnel 配置（向导直接持久化，此处只传表单中的模式）
        tunnel_mode: formTunnelMode,
        tunnel_name: config?.tunnel_name || '',
        tunnel_id: config?.tunnel_id || '',
        credentials_file: config?.credentials_file || '',
        hostname: config?.hostname || '',
        cert_file: config?.cert_file || '',
      })
      const wasRunning = status?.status === 'running'
      const copy = buildTunnelSaveCopy(result, autoStart, wasRunning)
      if (copy.level === 'warning') {
        message.warning(copy.text)
      } else {
        message.success(copy.text)
      }
      await loadConfig()
      return true
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '配置保存失败')
      return false
    } finally {
      setSavingConfig(false)
    }
  }

  const isRunning = status?.status === 'running'
  const isCloudflare = formProvider === 'cloudflare'
  const isTailscale = formProvider === 'tailscale'

  // 运行中保存＝立刻断线，必须先讲清后果再落刀（T02573 / 危险操作文案规范 B 档）
  const handleSaveClick = async () => {
    if (isRunning) {
      const ok = await confirmDanger({
        title: '隧道正在运行，确认保存配置？',
        action: '用当前表单值覆盖隧道配置',
        scope: '后端会以新配置重建隧道服务：现有隧道进程被停掉，公网地址立即失效，且不会自动按新配置重连',
        count: `正在运行的隧道 1 条（${formProvider}，本地端口 ${formPort}）`,
        recovery: '需手动点「启动隧道」重新拉起；未配置固定 named tunnel 时，重启后的公网地址会与当前地址不同，'
          + '已分享出去的链接需要重新提供',
      })
      if (!ok) return
    }
    await handleSaveConfig()
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 300 }}>
        <Spin size="large" />
      </div>
    )
  }

  // 顶部状态卡片的标签跟随当前表单选择（formProvider），让用户切换 provider 时立即看到变化。
  // 已保存/运行态的差异由后端 status 字段在保存或启动后覆盖。
  const displayProvider = status?.provider && status.status === 'running' ? status.provider : formProvider
  const isCloudflareDisplay = displayProvider === 'cloudflare'

  // 保存按钮提示：配置没读到时不能假装能保存（点了会拿默认值覆盖真实配置）
  const saveButtonTip = resolveSaveButtonTip(config, isRunning)

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* 4.6-3：加载失败如实渲染并可重试，而不是让页面继续显示一个编出来的「已停止」 */}
      {(loadErrors.status || loadErrors.config) && (
        <Alert
          type="error"
          showIcon
          message="隧道信息未能加载"
          description={
            <Space direction="vertical" size={4}>
              {loadErrors.status && <Text>状态：{loadErrors.status}</Text>}
              {loadErrors.config && (
                <Text>配置：{loadErrors.config}（配置缺失时表单回落默认值、固定域名向导不会显示）</Text>
              )}
              <Text type="secondary" style={{ fontSize: 12 }}>
                恢复前请勿依据本页展示判断隧道真实状态；点击「重试」或重新登录后再看。
              </Text>
            </Space>
          }
          action={
            <TipButton tip="重新加载隧道状态与配置" size="small" onClick={() => void reloadAll()}>
              重试
            </TipButton>
          }
        />
      )}

      {/* 状态卡片 */}
      <Card>
        <Row align="middle" gutter={[16, 16]}>
          <Col flex="auto">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Space>
                {loadErrors.status ? (
                  <Tag color="orange">状态未知（读取失败）</Tag>
                ) : (
                  <Tag color={isRunning ? 'green' : 'default'}>
                    {isRunning ? '● 运行中' : '○ 已停止'}
                  </Tag>
                )}
                <Tag icon={<CloudServerOutlined />}>
                  {TUNNEL_PROVIDERS[displayProvider]?.label || displayProvider}
                </Tag>
                {isCloudflareDisplay && config?.tunnel_mode === 'named' && config?.hostname && (
                  <Tag color="blue">固定域名</Tag>
                )}
              </Space>
              {status?.public_url ? (
                <Paragraph
                  copyable={{
                    text: status.public_url,
                    tooltips: ['复制', '已复制'],
                  }}
                  style={{ margin: 0 }}
                >
                  <Text type="success" strong>{status.public_url}</Text>
                </Paragraph>
              ) : (
                <Text type="secondary">
                  {loadErrors.status ? '状态读取失败，暂无法确认公网地址' : '隧道未启动，暂无公网地址'}
                </Text>
              )}
            </Space>
          </Col>
          <Col>
            <Space>
              <TipButton
                tip="启动隧道建立公网连接"
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={starting}
                disabled={isRunning}
                onClick={handleStart}
              >
                启动隧道
              </TipButton>
              <TipButton
                tip="停止当前隧道"
                danger
                icon={<StopOutlined />}
                loading={stopping}
                disabled={!isRunning}
                onClick={handleStop}
              >
                停止
              </TipButton>
              {status?.public_url && (
                <TipButton
                  tip="在新窗口打开公网地址"
                  aria-label="打开公网地址"
                  icon={<LinkOutlined />}
                  onClick={() => window.open(status.public_url!, '_blank')}
                />
              )}
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 下载失败指引 */}
      {downloadError && (
        <Alert
          type="error"
          showIcon
          icon={<ExclamationCircleOutlined />}
          message="二进制下载失败"
          description={
            <Space direction="vertical" size="small">
              <Text>{downloadError.detail}</Text>
              <Text strong>请手动下载并放置到以下路径：</Text>
              <Text code copyable>{downloadError.manual_path}</Text>
              <Space wrap>
                {downloadError.download_urls.map((url) => (
                  <TipButton
                    key={url}
                    tip="下载 cloudflared 二进制文件"
                    type="link"
                    size="small"
                    href={url}
                    target="_blank"
                    style={{ padding: 0 }}
                  >
                    {url.length > 60 ? url.slice(0, 60) + '...' : url}
                  </TipButton>
                ))}
              </Space>
              <Text type="secondary">放置后重新点击"启动隧道"即可</Text>
            </Space>
          }
        />
      )}

      {/* Tailscale Funnel 授权指引（类似固定域名向导的体验） */}
      {tailscaleAuthError && (
        <Card
          size="small"
          style={{ marginTop: 8, borderColor: '#faad14', borderWidth: 1 }}
          title={
            <Space>
              <SafetyCertificateOutlined style={{ color: '#faad14' }} />
              <Text>Tailscale Funnel 首次授权向导</Text>
            </Space>
          }
        >
          <Steps
            size="small"
            current={0}
            style={{ marginBottom: 16 }}
            items={[
              { title: '打开授权页', description: '浏览器访问授权链接' },
              { title: '启用 Funnel', description: '在 Tailscale 后台开启' },
              { title: '重新启动', description: '回到本页点击启动' },
            ]}
          />
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Tailscale Funnel 是将本地服务暴露到公网的功能，首次使用需要在 Tailscale 管理后台完成一次性授权。
            </Text>
            <Text strong>操作步骤：</Text>
            <Text>① 点击下方按钮，浏览器将打开 Tailscale 授权页面（含当前节点标识）</Text>
            <Text>② 在页面中确认并启用 Funnel 功能（可能需要登录 Tailscale 账号）</Text>
            <Text>③ 授权完成后，回到本页面重新点击"启动隧道"</Text>
            <TipButton
              tip="打开 Tailscale Funnel 授权页面"
              type="primary"
              icon={<LinkOutlined />}
              href={tailscaleAuthError.auth_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ marginTop: 8 }}
            >
              打开 Tailscale Funnel 授权页面
            </TipButton>
            <Text type="secondary" style={{ fontSize: 12 }} copyable>
              授权链接：{tailscaleAuthError.auth_url}
            </Text>
          </Space>
        </Card>
      )}

      {/* 配置卡片 */}
      <Card title={<><SafetyCertificateOutlined /> Provider 配置</>}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text strong>穿透服务</Text>
            <Select
              value={formProvider}
              onChange={setFormProvider}
              style={{ width: '100%', marginTop: 4 }}
              options={TUNNEL_PROVIDER_OPTIONS}
            />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
              {TUNNEL_PROVIDERS[formProvider]?.description}
            </Text>
          </div>

          {/* Cloudflare 模式选择 */}
          {isCloudflare && (
            <div>
              <Text strong>隧道模式</Text>
              <Radio.Group
                value={formTunnelMode}
                onChange={(e) => setFormTunnelMode(e.target.value)}
                style={{ marginTop: 4, display: 'block' }}
              >
                <Radio value="quick">快速模式（临时域名，每次重启变化）</Radio>
                <Radio value="named">固定域名模式（需 Cloudflare 账号 + 托管域名）</Radio>
              </Radio.Group>
            </div>
          )}

          {/* Named Tunnel 配置向导 */}
          {isCloudflare && formTunnelMode === 'named' && config && (
            <NamedTunnelWizard
              config={config}
              onConfigChanged={loadConfig}
            />
          )}

          {isTailscale && (
            <Alert
              type="info"
              showIcon
              message="使用免费的固定 ts.net 地址"
              description={
                <Space direction="vertical" size={4}>
                  <Text>
                    启动前请先安装 Tailscale、登录账号，并保持后台服务运行。
                    首次启用 Funnel 时可能会打开浏览器请求授权。
                  </Text>
                  <a
                    href={TUNNEL_PROVIDERS.tailscale.installUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    下载 Tailscale for Windows
                  </a>
                </Space>
              }
            />
          )}

          {formProvider === 'cpolar' && (
            <div>
              <Text strong>cpolar Authtoken</Text>
              {config?.cpolar_authtoken_configured && (
                <Tag color="blue" style={{ marginLeft: 8 }}>已配置（{config.cpolar_authtoken_masked}）</Tag>
              )}
              <Input.Password
                value={formAuthtoken}
                onChange={(e) => setFormAuthtoken(e.target.value)}
                placeholder={config?.cpolar_authtoken_configured ? '已配置，留空表示不修改' : '请输入 cpolar authtoken'}
                style={{ marginTop: 4 }}
              />
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                访问{' '}
                <a href="https://dashboard.cpolar.com/signup" target="_blank" rel="noopener noreferrer">
                  cpolar 控制台
                </a>{' '}
                注册并获取 Authtoken
              </Text>
            </div>
          )}

          <Row gutter={16}>
            <Col span={12}>
              <Text strong>本地端口</Text>
              <InputNumber
                value={formPort}
                onChange={(v) => setFormPort(v || 0)}
                min={0}
                max={65535}
                style={{ width: '100%', marginTop: 4 }}
                placeholder="0 表示从 server.port 继承"
              />
            </Col>
            <Col span={12}>
              <Text strong>二进制路径（可选）</Text>
              <Input
                value={formBinaryPath}
                onChange={(e) => setFormBinaryPath(e.target.value)}
                placeholder={isTailscale
                  ? '留空自动检测系统安装，或指定 tailscale.exe 路径'
                  : '留空自动下载，或指定手动放置路径'}
                style={{ marginTop: 4 }}
              />
            </Col>
          </Row>

          <Row align="middle" gutter={16}>
            <Col>
              <Space>
                <Switch
                  checked={formAutoStart}
                  onChange={setFormAutoStart}
                />
                <Text>开机自启动</Text>
              </Space>
            </Col>
            <Col>
              <Text type="secondary" style={{ fontSize: 12 }}>
                开启后，后端服务启动时自动在后台线程启动隧道
              </Text>
            </Col>
          </Row>

          {/* 4.6-2：表单脏了要显式说，不能让「改了没生效」静默发生 */}
          {config && dirtyFields.length > 0 && (
            <Alert
              type="warning"
              showIcon
              message={`有 ${dirtyFields.length} 项未保存的修改：${dirtyFields.join('、')}`}
              description={
                <Text type="secondary" style={{ fontSize: 12 }}>
                  当前运行中的隧道用的仍是已保存的配置。点「保存配置」立即落库；
                  点「启动隧道」会先自动保存这些修改再启动。
                </Text>
              }
            />
          )}

          <TipButton
            tip={saveButtonTip}
            type="primary"
            danger={isRunning}
            loading={savingConfig}
            disabled={config == null}
            onClick={() => void handleSaveClick()}
          >
            保存配置
          </TipButton>
        </Space>
      </Card>

      {/* 使用说明 */}
      <Alert
        type="info"
        showIcon
        message="使用说明"
        description={
          <Space direction="vertical" size="small">
            <Text>1. 选择 Provider 和模式并保存配置（表单改动需点「保存配置」才落库；点「启动隧道」会自动先保存）</Text>
            <Text>2. 固定域名模式：按向导完成授权 → 创建隧道 → 配置 DNS 三步，向导每一步即时保存，无需再点「保存配置」</Text>
            <Text>3. 点击"启动隧道"，系统将检测或准备 Provider CLI 并建立公网连接</Text>
            <Text>4. 复制公网地址，在手机浏览器打开即可远程访问</Text>
            <Text>5. 隧道运行期间请勿关闭本程序</Text>
            {isCloudflare && formTunnelMode === 'quick' && (
              <Text type="secondary">注意：快速模式域名随机且会变化，重启隧道后需更新手机端地址。如需固定地址，请切换到"固定域名模式"。</Text>
            )}
            {isCloudflare && formTunnelMode === 'named' && (
              <Text type="secondary">固定域名模式：首次配置需 3 步向导，之后每次启动地址不变。</Text>
            )}
            {isTailscale && (
              <Text type="secondary">Tailscale Funnel：首次授权后获得固定 ts.net 地址，无需购买域名。</Text>
            )}
          </Space>
        }
      />
    </Space>
  )
}
