import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { TipButton } from '@/components/TipButton'
import {
  Steps,
  Card,
  Input,
  InputNumber,
  Select,
  Result,
  message,
  Typography,
  Space,
  Alert,
} from 'antd'
import {
  CopyOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  RocketOutlined,
  LoginOutlined,
  PlusOutlined,
  BellOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons'
import { authApi, taskApi } from '../../api'
import type { TaskCreateBody } from '../../api/types'

const { Text, Paragraph } = Typography

export default function Onboarding() {
  const navigate = useNavigate()
  const [current, setCurrent] = useState(0)
  const [loginChecked, setLoginChecked] = useState(false)
  const [checking, setChecking] = useState(false)
  // Step 2 表单
  const [keyword, setKeyword] = useState('')
  const [minPrice, setMinPrice] = useState<number | null>(null)
  const [maxPrice, setMaxPrice] = useState<number | null>(null)
  const [mode, setMode] = useState<string>('notify')
  const [submitting, setSubmitting] = useState(false)

  // 复制 CLI 命令到剪贴板
  const copyCommand = (cmd: string) => {
    navigator.clipboard.writeText(cmd).then(
      () => message.success('已复制到剪贴板'),
      () => message.error('复制失败，请手动复制'),
    )
  }

  // 检查登录状态
  const checkLogin = async () => {
    setChecking(true)
    try {
      const data = await authApi.getMe()
      if (data.logged_in) {
        setLoginChecked(true)
        message.success('登录成功！')
      } else {
        message.warning('尚未登录，请先完成扫码')
      }
    } catch {
      message.error('检查登录状态失败')
    } finally {
      setChecking(false)
    }
  }

  // 提交创建任务
  const handleCreateTask = async () => {
    if (!keyword.trim()) {
      message.warning('请输入关键词')
      return
    }
    setSubmitting(true)
    try {
      const body: TaskCreateBody = {
        keyword: keyword.trim(),
        min_price: minPrice,
        max_price: maxPrice,
        mode,
      }
      await taskApi.create(body)
      message.success('任务创建成功！')
      setCurrent(2)
    } catch {
      message.error('创建任务失败')
    } finally {
      setSubmitting(false)
    }
  }

  // 步骤定义
  const steps = [
    {
      title: '扫码登录',
      icon: <LoginOutlined />,
      content: (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Alert type="info" message="在终端执行以下命令启动扫码登录" showIcon />
          <Card size="small" style={{ background: 'var(--xh-bg-code)', fontFamily: 'monospace' }}>
            <Space>
              <Text code>python -m xianyu_hunter qr-login</Text>
              <TipButton
                tip="复制扫码登录命令"
                size="small"
                icon={<CopyOutlined />}
                onClick={() => copyCommand('python -m xianyu_hunter qr-login')}
              >
                复制
              </TipButton>
            </Space>
          </Card>
          <div style={{ textAlign: 'center' }}>
            <TipButton
              tip="刷新并检测当前登录状态"
              type="primary"
              icon={<ReloadOutlined />}
              loading={checking}
              onClick={checkLogin}
            >
              刷新登录状态
            </TipButton>
            {loginChecked && (
              <Text type="success" style={{ marginLeft: 12 }}>
                <CheckCircleOutlined /> 已登录
              </Text>
            )}
          </div>
        </Space>
      ),
    },
    {
      title: '添加任务',
      icon: <PlusOutlined />,
      content: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text strong>关键词</Text>
            <Input
              placeholder="例如：iPhone 15 Pro"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <Text strong>价格范围</Text>
            <Space style={{ marginTop: 4 }}>
              <InputNumber
                placeholder="最低价"
                min={0}
                value={minPrice}
                onChange={(v) => setMinPrice(v)}
                style={{ width: 120 }}
              />
              <Text>—</Text>
              <InputNumber
                placeholder="最高价"
                min={0}
                value={maxPrice}
                onChange={(v) => setMaxPrice(v)}
                style={{ width: 120 }}
              />
            </Space>
          </div>
          <div>
            <Text strong>执行模式</Text>
            <Select
              value={mode}
              onChange={setMode}
              style={{ width: '100%', marginTop: 4 }}
              options={[
                { value: 'notify', label: '仅通知' },
                { value: 'confirm', label: '确认后执行' },
                { value: 'auto', label: '自动执行' },
              ]}
            />
          </div>
          <TipButton
            tip="创建监控任务"
            type="primary"
            icon={<RocketOutlined />}
            loading={submitting}
            onClick={handleCreateTask}
            block
          >
            创建任务
          </TipButton>
        </Space>
      ),
    },
    {
      title: '配置通知',
      icon: <BellOutlined />,
      content: (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Alert
            type="info"
            message="配置通知渠道后，系统会在商品匹配时及时推送消息"
            showIcon
          />
          <Paragraph>
            前往 <Link to="/config/notifier">通知渠道</Link> 页面配置钉钉、企业微信、邮件等通知方式。
          </Paragraph>
          <TipButton tip="进入下一步配置通知" type="primary" onClick={() => setCurrent(3)}>
            下一步
          </TipButton>
        </Space>
      ),
    },
    {
      title: '启动调度器',
      icon: <PlayCircleOutlined />,
      content: (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Alert type="info" message="在终端执行以下命令启动调度器" showIcon />
          <Card size="small" style={{ background: 'var(--xh-bg-code)', fontFamily: 'monospace' }}>
            <Space>
              <Text code>python -m xianyu_hunter worker</Text>
              <TipButton
                tip="复制启动调度器命令"
                size="small"
                icon={<CopyOutlined />}
                onClick={() => copyCommand('python -m xianyu_hunter worker')}
              >
                复制
              </TipButton>
            </Space>
          </Card>
          <TipButton tip="完成初始化设置" type="primary" onClick={() => setCurrent(4)} block>
            完成设置
          </TipButton>
        </Space>
      ),
    },
  ]

  // 完成庆祝态
  if (current >= steps.length) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: 'var(--xh-bg-layout)' }}>
        <Card style={{ maxWidth: 480, width: '100%', textAlign: 'center' }}>
          <Result
            icon={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
            title="设置完成！"
            subTitle="闲鱼猎人已就绪，开始你的智能监控之旅"
            extra={
              <TipButton tip="进入系统仪表盘" type="primary" size="large" onClick={() => navigate('/')}>
                进入仪表盘
              </TipButton>
            }
          />
        </Card>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: 'var(--xh-bg-layout)' }}>
      <Card style={{ maxWidth: 560, width: '100%' }}>
        <Steps current={current} items={steps.map((s) => ({ title: s.title, icon: s.icon }))} size="small" />
        <div style={{ marginTop: 32, minHeight: 200 }}>
          {steps[current].content}
        </div>
        <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
          <TipButton tip="返回上一步" disabled={current === 0} onClick={() => setCurrent(current - 1)}>
            上一步
          </TipButton>
          {/* Step 1 允许跳过（已登录或不想检查），Step 3 由内部按钮控制 */}
          {current !== 2 && (
          <TipButton tip="跳过本步骤" type="link" onClick={() => setCurrent(current + 1)}>
            跳过
          </TipButton>
          )}
        </div>
      </Card>
    </div>
  )
}
