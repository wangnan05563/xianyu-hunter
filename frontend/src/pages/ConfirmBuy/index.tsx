import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Card, Result, Spin, Typography, Space, Tag, Alert, App } from 'antd'
import { ThunderboltOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import { TipButton } from '@/components/TipButton'
import { itemApi, orderApi } from '../../api'
import type { ItemSummary } from '../../api/types'

const { Title, Text, Paragraph } = Typography

// 闲鱼商品详情页 URL：与 utils 中 GOOFISH_ITEM_URL 保持一致
const GOOFISH_ITEM_URL = 'https://www.goofish.com/item?id='

export default function ConfirmBuy() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { message, modal } = App.useApp()

  const taskId = searchParams.get('task_id') || ''
  const itemId = searchParams.get('item_id') || ''

  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [item, setItem] = useState<ItemSummary | null>(null)
  const [errorMsg, setErrorMsg] = useState<string>('')

  // 加载商品摘要：itemApi.summary 复用现有 /api/items/{id}/summary 接口
  // 该接口返回 item_id/title/price/seller_id/seller_nick 等基础字段，
  // 足够展示抢单前的快照，无需重采详情页（避免浏览器自动化耗时）
  useEffect(() => {
    if (!itemId) {
      setErrorMsg('链接缺少 item_id 参数，无法确认抢单')
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const summary = await itemApi.summary(itemId)
        if (cancelled) return
        setItem(summary)
      } catch (e) {
        if (cancelled) return
        setErrorMsg(e instanceof Error ? e.message : '加载商品信息失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [itemId])

  // 确认抢单：调用 manual-takeover 接口，复用既有抢单流程
  // 该接口会校验 buyer 注入态、登录态、幂等性，返回抢单结果
  const handleConfirm = async () => {
    setSubmitting(true)
    try {
      const result = await orderApi.manualTakeover(itemId, taskId || undefined)
      if (result.outcome === 'success' && result.order) {
        message.success(`抢单成功：订单号 ${result.order.order_no}`)
        // 跳转到抢单记录页，让用户继续接管/支付流程
        navigate('/orders')
      } else if (result.outcome === 'skipped_duplicate') {
        // 幂等跳过：商品已下过单，引导用户到订单页查看
        modal.info({
          title: '商品已下过单',
          content: result.message || '该商品已存在订单，跳转查看订单详情',
          onOk: () => navigate('/orders'),
        })
      } else {
        message.error(result.message || '抢单失败')
      }
    } catch (e) {
      // 503 = buyer 未注入（XH_WITH_SCHEDULER=1 未启动）
      // 403 = 闲鱼登录过期
      // 409 = 商品已售出
      // 500 = 浏览器自动化流程异常
      const errMsg = e instanceof Error ? e.message : '抢单失败'
      setErrorMsg(errMsg)
      message.error(errMsg)
    } finally {
      setSubmitting(false)
    }
  }

  // 参数缺失：直接展示错误
  if (!itemId) {
    return (
      <Card>
        <Result
          status="warning"
          title="链接参数不完整"
          subTitle={errorMsg || '链接缺少 item_id 参数'}
          extra={
            <TipButton tip="返回系统首页" type="primary" onClick={() => navigate('/')}>
              返回首页
            </TipButton>
          }
        />
      </Card>
    )
  }

  // 加载中
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <Spin size="large" tip="加载商品信息..." />
      </div>
    )
  }

  // 商品不存在或加载失败
  if (!item) {
    return (
      <Card>
        <Result
          status="error"
          title="商品信息加载失败"
          subTitle={errorMsg || '商品可能已被删除或链接无效'}
          extra={
            <Space>
              <TipButton tip="前往评估明细列表" onClick={() => navigate('/evaluations')}>查看评估列表</TipButton>
              <TipButton tip="返回系统首页" type="primary" onClick={() => navigate('/')}>返回首页</TipButton>
            </Space>
          }
        />
      </Card>
    )
  }

  return (
    <Card>
      <Space style={{ marginBottom: 16 }}>
        <TipButton tip="返回评估明细列表" icon={<ArrowLeftOutlined />} onClick={() => navigate('/evaluations')}>
          返回评估列表
        </TipButton>
        <Tag color="orange">半自动模式</Tag>
      </Space>

      <Title level={4}>
        <ThunderboltOutlined /> 确认抢单
      </Title>
      <Paragraph type="secondary">
        该商品通过评估并触发了半自动模式通知。请核对商品信息后确认抢单。
      </Paragraph>

      {errorMsg && (
        <Alert
          type="error"
          message="抢单出错"
          description={errorMsg}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Card type="inner" title="商品快照">
        <Paragraph>
          <Text strong>商品 ID：</Text>
          <Text code>{item.item_id}</Text>
        </Paragraph>
        <Paragraph>
          <Text strong>标题：</Text>
          <a href={`${GOOFISH_ITEM_URL}${item.item_id}`} target="_blank" rel="noopener noreferrer">
            {item.title || '（无标题）'}
          </a>
        </Paragraph>
        <Paragraph>
          <Text strong>价格：</Text>
          <Text type="danger" strong>¥{item.price?.toFixed(2) ?? '—'}</Text>
        </Paragraph>
        {item.seller_nick && (
          <Paragraph>
            <Text strong>卖家：</Text>
            <Text>{item.seller_nick}</Text>
          </Paragraph>
        )}
        {taskId && (
          <Paragraph>
            <Text strong>任务 ID：</Text>
            <Text code>{taskId}</Text>
          </Paragraph>
        )}
      </Card>

      <Alert
        type="warning"
        message="抢单后将创建待支付订单，请尽快在闲鱼 App 内完成支付"
        showIcon
        style={{ margin: '16px 0' }}
      />

      <Space>
        <TipButton
          tip="创建待支付订单并提交抢单"
          type="primary"
          size="large"
          icon={<ThunderboltOutlined />}
          loading={submitting}
          onClick={handleConfirm}
        >
          确认抢单
        </TipButton>
        <TipButton tip="放弃抢单并返回评估列表" size="large" onClick={() => navigate('/evaluations')}>
          取消
        </TipButton>
      </Space>
    </Card>
  )
}
