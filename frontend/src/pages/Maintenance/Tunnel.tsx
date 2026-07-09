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
  message,
  Spin,
} from 'antd'
import {
  GlobalOutlined,
  PlayCircleOutlined,
  StopOutlined,
  LinkOutlined,
  CloudServerOutlined,
  SafetyCertificateOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'
import { tunnelApi, type TunnelStatus, type TunnelConfig, type TunnelDownloadError } from '../../api'

const { Text, Paragraph, Title } = Typography

const PROVIDER_LABELS: Record<string, string> = {
  cloudflare: 'Cloudflare Tunnel',
  cpolar: 'cpolar（国内推荐）',
}

const PROVIDER_DESC: Record<string, string> = {
  cloudflare: '免注册，自动分配 trycloudflare 域名。大陆访问可能不稳定。',
  cpolar: '国内服务器稳定，需注册账号获取 authtoken。访问 https://dashboard.cpolar.com/signup 注册',
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

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 300 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Title level={4}>
        <GlobalOutlined /> 内网穿透
      </Title>

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
              </Space>
              {status?.public_url ? (
                <Paragraph copyable={{ tooltips: ['复制', '已复制'] }} style={{ margin: 0 }}>
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
            <Text>1. 选择 Provider 并保存配置（cpolar 需填写 Authtoken）</Text>
            <Text>2. 点击"启动隧道"，系统自动下载二进制并建立公网连接</Text>
            <Text>3. 复制公网地址，在手机浏览器打开即可远程访问</Text>
            <Text>4. 隧道运行期间请勿关闭本程序</Text>
            <Text type="secondary">注意：免费版域名随机且会变化，重启隧道后需更新手机端地址</Text>
          </Space>
        }
      />
    </Space>
  )
}
