import { useEffect, useState, useCallback } from 'react'
import {
  Card,
  Button,
  Row,
  Col,
  Space,
  message,
  Tag,
  Typography,
  Statistic,
  Progress,
  Descriptions,
  Badge,
  Switch,
  Modal,
  Input,
  Divider,
  Alert,
} from 'antd'
import {
  ReloadOutlined,
  PlayCircleOutlined,
  StopOutlined,
  SafetyCertificateOutlined,
  IdcardOutlined,
  ThunderboltOutlined,
  KeyOutlined,
  HeartOutlined,
  ExperimentOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'
import { anticrawlApi } from '../../api'
import { usePersistentState } from '../../hooks/usePersistentState'
import type {
  StrategyEvaluation,
  SessionStatus,
  FingerprintInfo,
  FreqStats,
  CookieLayersResult,
  HealthReport,
  OperationResult,
} from '../../api'

const { Text, Paragraph } = Typography

// 策略中文标签映射
const STRATEGY_LABELS: Record<string, string> = {
  cdp_connect: 'CDP 连接系统浏览器',
  reuse_userdata: '复用 browser-data Cookie',
  browser_import: '从系统浏览器导入',
  qr_scan: '扫码登录',
  cookie_inject: '手动 Cookie 注入',
}

// 健康动作中文映射
const ACTION_LABELS: Record<string, string> = {
  none: '无需操作',
  renew_token: '续期 Token',
  relogin: '重新登录',
  pause: '暂停 + 通知',
}

// WAF 状态颜色映射
const WAF_COLORS: Record<string, string> = {
  clear: 'green',
  warning: 'orange',
  blocked: 'red',
}

const WAF_LABELS: Record<string, string> = {
  clear: '正常',
  warning: '警告',
  blocked: '已熔断',
}

export default function AntiCrawl() {
  // 数据状态
  const [strategy, setStrategy] = useState<StrategyEvaluation | null>(null)
  const [session, setSession] = useState<SessionStatus | null>(null)
  const [fingerprint, setFingerprint] = useState<FingerprintInfo | null>(null)
  const [freqStats, setFreqStats] = useState<FreqStats | null>(null)
  const [cookieLayers, setCookieLayers] = useState<CookieLayersResult | null>(null)
  const [health, setHealth] = useState<HealthReport | null>(null)

  // 加载状态
  const [loadingStrategy, setLoadingStrategy] = useState(false)
  const [loadingInit, setLoadingInit] = useState(false)
  const [loadingSession, setLoadingSession] = useState(false)
  const [loadingHealth, setLoadingHealth] = useState(false)
  const [loadingLayers, setLoadingLayers] = useState(false)

  // CDP 模式开关（持久化：刷新后保持上次设置）
  const [useCdp, setUseCdp] = usePersistentState<boolean>('xh.anticrawl.useCdp', false, {
    validator: (v): v is boolean => typeof v === 'boolean',
  })

  // Cookie 更新弹窗
  const [cookieModalOpen, setCookieModalOpen] = useState(false)
  const [cookieInput, setCookieInput] = useState('')
  const [loadingUpdate, setLoadingUpdate] = useState(false)

  // ============== 数据加载 ==============

  const loadAll = useCallback(async () => {
    await Promise.all([
      loadStrategy(),
      loadSession(),
      loadFingerprint(),
      loadFreqStats(),
      loadCookieLayers(),
    ])
  }, [])

  useEffect(() => {
    loadAll()
    // 会话活跃时每 10 秒刷新状态
    const interval = setInterval(() => {
      loadSession()
    }, 10000)
    return () => clearInterval(interval)
  }, [loadAll])

  const loadStrategy = async () => {
    try {
      setLoadingStrategy(true)
      const data = await anticrawlApi.getStrategy()
      setStrategy(data)
    } catch (error) {
      console.error('加载策略失败', error)
    } finally {
      setLoadingStrategy(false)
    }
  }

  const loadSession = async () => {
    try {
      const data = await anticrawlApi.getSessionStatus()
      setSession(data)
    } catch (error) {
      console.error('加载会话状态失败', error)
    }
  }

  const loadFingerprint = async () => {
    try {
      const data = await anticrawlApi.getFingerprint()
      setFingerprint(data)
    } catch (error) {
      console.error('加载指纹信息失败', error)
    }
  }

  const loadFreqStats = async () => {
    try {
      const data = await anticrawlApi.getFreqStats()
      setFreqStats(data)
    } catch (error) {
      console.error('加载频率统计失败', error)
    }
  }

  const loadCookieLayers = async () => {
    try {
      setLoadingLayers(true)
      const data = await anticrawlApi.getCookieLayers()
      setCookieLayers(data)
    } catch (error) {
      console.error('加载 Cookie 层状态失败', error)
    } finally {
      setLoadingLayers(false)
    }
  }

  // ============== 操作处理 ==============

  const handleInitialize = async () => {
    try {
      setLoadingInit(true)
      const result = await anticrawlApi.initialize(useCdp)
      if (result.ok) {
        message.success(result.message || `协调器已初始化（${result.mode} 模式）`)
        await loadAll()
      } else {
        message.error(result.error || '初始化失败')
      }
    } catch (error) {
      message.error('初始化失败')
      console.error(error)
    } finally {
      setLoadingInit(false)
    }
  }

  const handleStartSession = async () => {
    try {
      setLoadingSession(true)
      const result = await anticrawlApi.startSession()
      if (result.ok) {
        message.success('会话管理已启动')
        await loadSession()
      } else {
        message.error('启动会话失败')
      }
    } catch (error) {
      message.error('启动会话失败')
      console.error(error)
    } finally {
      setLoadingSession(false)
    }
  }

  const handleStopSession = async () => {
    try {
      setLoadingSession(true)
      const result = await anticrawlApi.stopSession()
      if (result.ok) {
        message.success('会话管理已停止')
        await loadSession()
      } else {
        message.error(result.error || '停止会话失败')
      }
    } catch (error) {
      message.error('停止会话失败')
      console.error(error)
    } finally {
      setLoadingSession(false)
    }
  }

  const handleHealthCheck = async () => {
    try {
      setLoadingHealth(true)
      let result = await anticrawlApi.checkHealth()
      // 未配置检查器时自动初始化后重试
      if (!result.ok && result.error?.includes('initialize')) {
        const initResult = await anticrawlApi.initialize(useCdp)
        if (initResult.ok) {
          await loadAll()
          result = await anticrawlApi.checkHealth()
        }
      }
      setHealth(result)
      if (result.ok) {
        if (result.is_healthy) {
          message.success(`健康检查通过（score=${result.score}）`)
        } else {
          message.warning(`健康检查发现问题（score=${result.score}，建议：${ACTION_LABELS[result.action] || result.action}）`)
        }
      } else {
        message.warning(result.error || '未配置健康检查器')
      }
    } catch (error) {
      message.error('健康检查失败')
      console.error(error)
    } finally {
      setLoadingHealth(false)
    }
  }

  const handleInvalidateLayer = (layer: string) => {
    Modal.confirm({
      title: `确认失效 ${layer} 层？`,
      icon: <ExclamationCircleOutlined />,
      content: layer === 'identity' ? 'identity 层失效会级联导致 session 层失效' : undefined,
      onOk: async () => {
        try {
          const result = await anticrawlApi.invalidateLayer(layer)
          if (result.ok) {
            message.success(result.message || `层 ${layer} 已失效`)
            await loadCookieLayers()
          } else {
            message.error(result.error || '操作失败')
          }
        } catch (error) {
          message.error('操作失败')
          console.error(error)
        }
      },
    })
  }

  const handleUpdateCookies = async () => {
    if (!cookieInput.trim()) {
      message.warning('请输入 Cookie')
      return
    }

    // 解析 cookie 字符串为对象
    const cookies: Record<string, string> = {}
    for (const part of cookieInput.split(/[;\n]/)) {
      const trimmed = part.trim()
      if (!trimmed || !trimmed.includes('=')) continue
      const [name, ...valueParts] = trimmed.split('=')
      const value = valueParts.join('=')
      if (name && value) {
        cookies[name.trim()] = value.trim()
      }
    }

    if (Object.keys(cookies).length === 0) {
      message.warning('未能解析出有效的 Cookie')
      return
    }

    try {
      setLoadingUpdate(true)
      const result = await anticrawlApi.updateCookies(cookies)
      if (result.ok) {
        message.success(result.message || `已更新 ${result.written} 个 Cookie`)
        setCookieModalOpen(false)
        setCookieInput('')
        await loadCookieLayers()
      } else {
        message.error(result.error || '更新失败')
      }
    } catch (error) {
      message.error('更新 Cookie 失败')
      console.error(error)
    } finally {
      setLoadingUpdate(false)
    }
  }

  // ============== 渲染 ==============

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <ExperimentOutlined style={{ marginRight: 8 }} />
          反爬登录管理
        </Typography.Title>
        <Button icon={<ReloadOutlined />} onClick={loadAll} loading={loadingStrategy}>
          刷新
        </Button>
      </Space>

      <Row gutter={[16, 16]}>
        {/* ============== 策略评估 ============== */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <ThunderboltOutlined />
                登录策略评估
              </Space>
            }
            extra={
              <Space>
                <Text type="secondary">CDP 模式</Text>
                <Switch checked={useCdp} onChange={setUseCdp} size="small" />
              </Space>
            }
          >
            {strategy && (
              <>
                <Alert
                  type="info"
                  showIcon
                  message={`推荐策略：${STRATEGY_LABELS[strategy.recommended] || strategy.recommended}`}
                  description={strategy.reason}
                  style={{ marginBottom: 16 }}
                />
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="可用策略">
                    <Space wrap>
                      {strategy.available_strategies.map((s) => (
                        <Tag key={s} color={s === strategy.recommended ? 'orange' : 'default'}>
                          {STRATEGY_LABELS[s] || s}
                        </Tag>
                      ))}
                    </Space>
                  </Descriptions.Item>
                </Descriptions>
              </>
            )}
            <Divider style={{ margin: '12px 0' }} />
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleInitialize}
              loading={loadingInit}
              block
            >
              初始化协调器（{useCdp ? 'CDP' : 'Launch'} 模式）
            </Button>
          </Card>
        </Col>

        {/* ============== 会话管理 ============== */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <SafetyCertificateOutlined />
                会话管理
                {session?.active && (
                  <Badge status="processing" text="运行中" />
                )}
              </Space>
            }
          >
            {session && (
              <Row gutter={[16, 16]}>
                <Col span={8}>
                  <Statistic
                    title="会话状态"
                    value={session.active ? '活跃' : '未启动'}
                    valueStyle={{ color: session.active ? '#52c41a' : '#8c8c8c' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="运行时间"
                    value={session.active ? `${Math.floor(session.uptime_sec)}s` : '-'}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="Token 年龄"
                    value={session.token_age_sec != null ? `${Math.floor(session.token_age_sec)}s` : '-'}
                    valueStyle={{
                      color: session.token_expired ? '#ff4d4f' : '#52c41a',
                    }}
                  />
                </Col>
              </Row>
            )}
            <Divider style={{ margin: '12px 0' }} />
            <Space>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleStartSession}
                loading={loadingSession}
                disabled={session?.active}
              >
                启动会话
              </Button>
              <Button
                danger
                icon={<StopOutlined />}
                onClick={handleStopSession}
                loading={loadingSession}
                disabled={!session?.active}
              >
                停止会话
              </Button>
            </Space>
          </Card>
        </Col>

        {/* ============== 健康检查 ============== */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <HeartOutlined />
                健康检查
              </Space>
            }
            extra={
              <Button
                icon={<ReloadOutlined />}
                onClick={handleHealthCheck}
                loading={loadingHealth}
                size="small"
              >
                检查
              </Button>
            }
          >
            {health && health.ok ? (
              <>
                <Progress
                  percent={health.score}
                  status={
                    health.score >= 80 ? 'success' : health.score >= 60 ? 'normal' : 'exception'
                  }
                  format={(percent) => `${percent}分`}
                  style={{ marginBottom: 16 }}
                />
                <Row gutter={[16, 8]}>
                  <Col span={6}>
                    <Statistic
                      title="Cookie"
                      value={health.cookie_valid ? '有效' : '无效'}
                      valueStyle={{ color: health.cookie_valid ? '#52c41a' : '#ff4d4f', fontSize: 14 }}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="API"
                      value={health.api_reachable ? '可达' : '不可达'}
                      valueStyle={{ color: health.api_reachable ? '#52c41a' : '#ff4d4f', fontSize: 14 }}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="页面"
                      value={health.page_accessible ? '可访问' : '不可访问'}
                      valueStyle={{ color: health.page_accessible ? '#52c41a' : '#ff4d4f', fontSize: 14 }}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="WAF"
                      value={WAF_LABELS[health.waf_status] || health.waf_status}
                      valueStyle={{ fontSize: 14 }}
                    />
                  </Col>
                </Row>
                {health.action !== 'none' && (
                  <Alert
                    type={health.needs_attention ? 'error' : 'warning'}
                    showIcon
                    message={`建议操作：${ACTION_LABELS[health.action] || health.action}`}
                    style={{ marginTop: 12 }}
                  />
                )}
              </>
            ) : (
              <Text type="secondary">
                {health?.error || '点击「检查」按钮执行健康检查'}
              </Text>
            )}
          </Card>
        </Col>

        {/* ============== Cookie 分层管理 ============== */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <KeyOutlined />
                Cookie 分层管理
              </Space>
            }
            extra={
              <Space>
                <Button
                  size="small"
                  onClick={() => setCookieModalOpen(true)}
                >
                  更新 Cookie
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  size="small"
                  onClick={loadCookieLayers}
                  loading={loadingLayers}
                />
              </Space>
            }
          >
            {cookieLayers && (
              <Row gutter={[16, 16]}>
                {Object.entries(cookieLayers.layers).map(([layer, state]) => (
                  <Col span={8} key={layer}>
                    <Card size="small" style={{ textAlign: 'center' }}>
                      <Badge
                        status={state.valid ? 'success' : 'default'}
                        text={
                          <Text strong style={{ fontSize: 14 }}>
                            {layer}
                          </Text>
                        }
                      />
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {state.valid ? `${state.cookie_count} 个 Cookie` : '未初始化'}
                        </Text>
                      </div>
                      {state.valid && (
                        <Button
                          size="small"
                          danger
                          type="link"
                          onClick={() => handleInvalidateLayer(layer)}
                          style={{ padding: '4px 0', fontSize: 12 }}
                        >
                          失效
                        </Button>
                      )}
                    </Card>
                  </Col>
                ))}
              </Row>
            )}
            <Alert
              type="info"
              showIcon
              message="分层说明"
              description={
                <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12 }}>
                  <li><b>identity</b>：身份层（unb/cookie2/sgcookie），最稳定</li>
                  <li><b>session</b>：会话层（_m_h5_tk），依赖 identity</li>
                  <li><b>tracking</b>：追踪层（cna/tfstk），每次请求可能变化</li>
                </ul>
              }
              style={{ marginTop: 12 }}
            />
          </Card>
        </Col>

        {/* ============== 指纹信息 ============== */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <IdcardOutlined />
                指纹信息
              </Space>
            }
          >
            {fingerprint && fingerprint.profile ? (
              <Descriptions column={2} size="small" bordered>
                <Descriptions.Item label="Profile" span={2}>
                  <Tag color="orange">{fingerprint.profile.name}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="UA" span={2}>
                  <Text style={{ fontSize: 12 }} copyable>
                    {fingerprint.profile.ua}
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="平台">
                  {fingerprint.profile.platform}
                </Descriptions.Item>
                <Descriptions.Item label="厂商">
                  {fingerprint.profile.vendor}
                </Descriptions.Item>
                <Descriptions.Item label="CPU 核心">
                  {fingerprint.profile.hardware_concurrency}
                </Descriptions.Item>
                <Descriptions.Item label="内存">
                  {fingerprint.profile.device_memory} GB
                </Descriptions.Item>
                <Descriptions.Item label="GPU" span={2}>
                  {fingerprint.profile.gpu_vendor} / {fingerprint.profile.gpu_renderer}
                </Descriptions.Item>
                <Descriptions.Item label="屏幕">
                  {fingerprint.profile.screen_width} × {fingerprint.profile.screen_height}
                </Descriptions.Item>
                <Descriptions.Item label="色深">
                  {fingerprint.profile.color_depth} bit
                </Descriptions.Item>
                <Descriptions.Item label="Stealth 脚本" span={2}>
                  {fingerprint.stealth_scripts_count} 个（指纹 + AWSC 伪装）
                </Descriptions.Item>
              </Descriptions>
            ) : (
              <Alert
                type="info"
                showIcon
                message="CDP 模式或未初始化"
                description="CDP 模式使用真实浏览器，无需指纹注入。点击上方「初始化协调器」生成 launch 模式指纹。"
              />
            )}
          </Card>
        </Col>

        {/* ============== 频率伪装统计 ============== */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <ThunderboltOutlined />
                频率伪装统计
              </Space>
            }
            extra={
              <Button
                icon={<ReloadOutlined />}
                size="small"
                onClick={loadFreqStats}
              />
            }
          >
            {freqStats && (
              <Row gutter={[16, 16]}>
                <Col span={8}>
                  <Statistic
                    title="总请求数"
                    value={freqStats.total_requests}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="噪声请求"
                    value={freqStats.noise_requests}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="噪声占比"
                    value={(freqStats.noise_ratio * 100).toFixed(2)}
                    suffix="%"
                    precision={2}
                  />
                </Col>
                {freqStats.mean_interval != null && (
                  <>
                    <Col span={8}>
                      <Statistic
                        title="平均间隔"
                        value={freqStats.mean_interval.toFixed(2)}
                        suffix="s"
                        precision={2}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="中位间隔"
                        value={freqStats.median_interval?.toFixed(2)}
                        suffix="s"
                        precision={2}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="标准差"
                        value={freqStats.std_interval?.toFixed(2)}
                        suffix="s"
                        precision={2}
                      />
                    </Col>
                  </>
                )}
              </Row>
            )}
            <Alert
              type="info"
              showIcon
              message="频率伪装策略"
              description="使用对数正态分布模拟人类请求间隔的右偏特征（mean > median），并插入噪声请求打乱请求规律。"
              style={{ marginTop: 12 }}
            />
          </Card>
        </Col>
      </Row>

      {/* ============== Cookie 更新弹窗 ============== */}
      <Modal
        title="分层更新 Cookie"
        open={cookieModalOpen}
        onOk={handleUpdateCookies}
        onCancel={() => {
          setCookieModalOpen(false)
          setCookieInput('')
        }}
        confirmLoading={loadingUpdate}
        okText="更新"
        cancelText="取消"
        width={600}
      >
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          输入 Cookie 字符串（格式：<code>name=value; name2=value2</code>），
          系统会自动分类到 identity / session / tracking 三层并原子更新。
        </Paragraph>
        <Input.TextArea
          value={cookieInput}
          onChange={(e) => setCookieInput(e.target.value)}
          placeholder="_m_h5_tk=token_123; _m_h5_tk_enc=enc_123; unb=123456; cookie2=abc; sgcookie=sg; ..."
          rows={6}
          style={{ fontFamily: 'monospace', fontSize: 12 }}
        />
      </Modal>
    </div>
  )
}
