import { useEffect, useState, useRef, useCallback } from 'react'
import {
  Card,
  Button,
  Space,
  Tag,
  Typography,
  Select,
  Input,
  InputNumber,
  Alert,
  Row,
  Col,
  Tooltip,
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
          <Button
            type={config.cert_file ? 'default' : 'primary'}
            icon={loginLoading || loginPolling ? <LoadingOutlined /> : undefined}
            loading={loginLoading}
            onClick={handleLogin}
            disabled={loginLoading || loginPolling}
          >
            {loginButtonText}
          </Button>
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
              <Button
                type={config.tunnel_id ? 'default' : 'primary'}
                icon={createLoading ? <LoadingOutlined /> : undefined}
                loading={createLoading}
                onClick={handleCreate}
                disabled={!config.cert_file || createLoading}
              >
                {config.tunnel_id ? '重新创建' : '创建隧道'}
              </Button>
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
              <Button
                type={config.hostname ? 'default' : 'primary'}
                icon={dnsLoading ? <LoadingOutlined /> : undefined}
                loading={dnsLoading}
                onClick={handleRouteDns}
                disabled={!config.tunnel_id || dnsLoading}
              >
                {config.hostname ? '重新配置' : '配置路由'}
              </Button>
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

export default function Tunnel() {
  const [status, setStatus] = useState<TunnelStatus | null>(null)
  const [config, setConfig] = useState<TunnelConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)

  // 配置表单（本地编辑态，保存后才生效）
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

  // 加载状态
  const loadStatus = useCallback(async () => {
    try {
      const data = await tunnelApi.getStatus()
      setStatus(data)
    } catch (error) {
      console.error('加载隧道状态失败', error)
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
    } catch (error) {
      // 401 表示未登录，配置端点需认证
      console.error('加载隧道配置失败', error)
    }
  }, [])

  // 初始加载
  useEffect(() => {
    (async () => {
      setLoading(true)
      await Promise.all([loadStatus(), loadConfig()])
      setLoading(false)
    })()
  }, [loadStatus, loadConfig])

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

  // 启动隧道
  const handleStart = async () => {
    // 表单中的 provider 与已保存不一致时，先同步配置再启动。
    // 否则后端读到的仍是旧 provider，启动的还是 Cloudflare。
    if (config && formProvider !== config.provider) {
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
  const handleStop = async () => {
    setStopping(true)
    try {
      const data = await tunnelApi.stop()
      setStatus(data)
      message.success('隧道已关闭')
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '停止失败')
    } finally {
      setStopping(false)
    }
  }

  // 保存配置
  // auto_start=true 时表示启动隧道前的自动同步，文案要即时反馈；
  // 手动点保存按钮时 next 启动才生效，文案应强调"下次启动生效"
  const handleSaveConfig = async (autoStart = false): Promise<boolean> => {
    setSavingConfig(true)
    try {
      await tunnelApi.saveConfig({
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
      message.success(autoStart ? '配置已同步，正在启动隧道...' : '配置已保存，下次启动隧道时生效')
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

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* 状态卡片 */}
      <Card>
        <Row align="middle" gutter={[16, 16]}>
          <Col flex="auto">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Space>
                <Tag color={isRunning ? 'green' : 'default'}>
                  {isRunning ? '● 运行中' : '○ 已停止'}
                </Tag>
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
                <Text type="secondary">隧道未启动，暂无公网地址</Text>
              )}
            </Space>
          </Col>
          <Col>
            <Space>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={starting}
                disabled={isRunning}
                onClick={handleStart}
              >
                启动隧道
              </Button>
              <Button
                danger
                icon={<StopOutlined />}
                loading={stopping}
                disabled={!isRunning}
                onClick={handleStop}
              >
                停止
              </Button>
              {status?.public_url && (
                <Tooltip title="在新窗口打开">
                  <Button
                    icon={<LinkOutlined />}
                    onClick={() => window.open(status.public_url!, '_blank')}
                  />
                </Tooltip>
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
                  <Button
                    key={url}
                    type="link"
                    size="small"
                    href={url}
                    target="_blank"
                    style={{ padding: 0 }}
                  >
                    {url.length > 60 ? url.slice(0, 60) + '...' : url}
                  </Button>
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
            <Button
              type="primary"
              icon={<LinkOutlined />}
              href={tailscaleAuthError.auth_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ marginTop: 8 }}
            >
              打开 Tailscale Funnel 授权页面
            </Button>
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

          <Button
            type="primary"
            loading={savingConfig}
            onClick={() => handleSaveConfig()}
          >
            保存配置
          </Button>
        </Space>
      </Card>

      {/* 使用说明 */}
      <Alert
        type="info"
        showIcon
        message="使用说明"
        description={
          <Space direction="vertical" size="small">
            <Text>1. 选择 Provider 和模式并保存配置</Text>
            <Text>2. 固定域名模式：按向导完成授权 → 创建隧道 → 配置 DNS 三步</Text>
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
