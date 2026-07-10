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
import { tunnelApi, type TunnelStatus, type TunnelConfig, type TunnelDownloadError } from '../../api'

const { Text, Paragraph } = Typography

const PROVIDER_LABELS: Record<string, string> = {
  cloudflare: 'Cloudflare Tunnel',
  cpolar: 'cpolar（国内推荐）',
}

const PROVIDER_DESC: Record<string, string> = {
  cloudflare: '免注册快速模式，或绑定域名固定地址。大陆访问可能不稳定。',
  cpolar: '国内服务器稳定，需注册账号获取 authtoken。访问 https://dashboard.cpolar.com/signup 注册',
}

// Named Tunnel 向导步骤定义
const WIZARD_STEPS = [
  { title: '授权登录', description: 'Cloudflare 账号授权' },
  { title: '创建隧道', description: '生成隧道凭证' },
  { title: '配置 DNS', description: '绑定固定域名' },
]

// Named Tunnel 配置向导组件
function NamedTunnelWizard({
  config,
  onConfigChanged,
}: {
  config: TunnelConfig
  onConfigChanged: () => void
}) {
  const [loginLoading, setLoginLoading] = useState(false)
  const [createName, setCreateName] = useState(config.tunnel_name || '')
  const [createLoading, setCreateLoading] = useState(false)
  const [dnsHostname, setDnsHostname] = useState(config.hostname || '')
  const [dnsLoading, setDnsLoading] = useState(false)

  // 根据已配置字段自动判断当前步骤
  const currentStep = !config.cert_file ? 0 : !config.tunnel_id ? 1 : !config.hostname ? 2 : 3

  const handleLogin = async () => {
    setLoginLoading(true)
    try {
      const result = await tunnelApi.cloudflareLogin()
      message.success(result.message)
      onConfigChanged()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '登录失败')
    } finally {
      setLoginLoading(false)
    }
  }

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
          <Button
            type={config.cert_file ? 'default' : 'primary'}
            icon={loginLoading ? <LoadingOutlined /> : undefined}
            loading={loginLoading}
            onClick={handleLogin}
            disabled={loginLoading}
          >
            {config.cert_file ? '重新授权' : '执行登录'}
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
    setStarting(true)
    setDownloadError(null)
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
  const handleSaveConfig = async () => {
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
      message.success('配置已保存，下次启动隧道时生效')
      await loadConfig()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '配置保存失败')
    } finally {
      setSavingConfig(false)
    }
  }

  const isRunning = status?.status === 'running'
  const isCloudflare = formProvider === 'cloudflare'

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 300 }}>
        <Spin size="large" />
      </div>
    )
  }

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
                {status?.provider && (
                  <Tag icon={<CloudServerOutlined />}>
                    {PROVIDER_LABELS[status.provider] || status.provider}
                  </Tag>
                )}
                {config?.tunnel_mode === 'named' && config?.hostname && (
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

      {/* 配置卡片 */}
      <Card title={<><SafetyCertificateOutlined /> Provider 配置</>}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text strong>穿透服务</Text>
            <Select
              value={formProvider}
              onChange={setFormProvider}
              style={{ width: '100%', marginTop: 4 }}
              options={Object.entries(PROVIDER_LABELS).map(([value, label]) => ({
                value,
                label,
              }))}
            />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
              {PROVIDER_DESC[formProvider]}
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
                placeholder="留空自动下载，或指定手动放置路径"
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
            onClick={handleSaveConfig}
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
            <Text>3. 点击"启动隧道"，系统自动下载二进制并建立公网连接</Text>
            <Text>4. 复制公网地址，在手机浏览器打开即可远程访问</Text>
            <Text>5. 隧道运行期间请勿关闭本程序</Text>
            {formTunnelMode === 'quick' && (
              <Text type="secondary">注意：快速模式域名随机且会变化，重启隧道后需更新手机端地址。如需固定地址，请切换到"固定域名模式"。</Text>
            )}
            {formTunnelMode === 'named' && (
              <Text type="secondary">固定域名模式：首次配置需 3 步向导，之后每次启动地址不变。</Text>
            )}
          </Space>
        }
      />
    </Space>
  )
}
