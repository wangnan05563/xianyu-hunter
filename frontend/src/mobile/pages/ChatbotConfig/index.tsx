// frontend/src/mobile/pages/ChatbotConfig/index.tsx
// 移动端智能客服配置（精简版）：仅展示欢迎语 + FAQ 列表预览 + 基础开关
// 设计要点：相比桌面端去掉 KB 版本管理 / VectorAdmin / 审计日志等运维型面板，
// 保留对客服实际效果影响最大的欢迎语和 FAQ，让运营人员可快速预览与编辑
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Tag, Spin, App, Switch, Button, Input, Modal, Space, List, Empty, theme,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { chatbotApi } from '../../../pages/Chatbot/api'
import type { ChatbotConfig, FAQ, WelcomeInfo } from '../../../pages/Chatbot/types'
import { extractApiError } from '../../../utils/apiError'

export default function MobileChatbotConfig() {
  const { message } = App.useApp()
  const { token: themeToken } = theme.useToken()
  const [config, setConfig] = useState<ChatbotConfig | null>(null)
  const [welcome, setWelcome] = useState<WelcomeInfo | null>(null)
  const [faqs, setFaqs] = useState<FAQ[]>([])
  const [loading, setLoading] = useState(true)
  const [editingFaq, setEditingFaq] = useState<FAQ | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState<FAQ>({ question: '', answer: '', category: '通用', enabled: true })

  const loadAll = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      // 错误隔离：任一失败不阻塞其他数据
      const [cfg, wel, faqList] = await Promise.all([
        chatbotApi.getConfig().catch(() => null),
        chatbotApi.getWelcome().catch(() => null),
        chatbotApi.listFAQ().catch(() => [] as FAQ[]),
      ])
      if (cfg) setConfig(cfg)
      if (wel) setWelcome(wel)
      setFaqs(faqList)
    } catch (e) {
      message.error(extractApiError(e, '加载配置失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void loadAll() }, [loadAll])

  // 切换启用开关：失败时回滚 + 重新拉取
  const toggleEnabled = async (v: boolean): Promise<void> => {
    if (!config) return
    const prev = config.enabled
    setConfig({ ...config, enabled: v })
    try {
      await chatbotApi.updateConfig('enabled', String(v))
      message.success(v ? '已启用客服' : '已停用客服')
    } catch (e) {
      message.error(extractApiError(e, '更新失败'), 3)
      setConfig({ ...config, enabled: prev })
    }
  }

  // 切换 FAQ 启用状态
  const toggleFaq = async (faq: FAQ, enabled: boolean): Promise<void> => {
    if (faq.id === undefined) return
    const updated = { ...faq, enabled }
    setFaqs((prev) => prev.map((f) => (f.id === faq.id ? updated : f)))
    try {
      await chatbotApi.upsertFAQ(updated)
    } catch (e) {
      message.error(extractApiError(e, '更新失败'), 3)
      setFaqs((prev) => prev.map((f) => (f.id === faq.id ? faq : f)))
    }
  }

  // 删除 FAQ
  const deleteFaq = (faq: FAQ): void => {
    if (faq.id === undefined) return
    Modal.confirm({
      title: '删除 FAQ',
      content: `确认删除「${faq.question}」？此操作不可撤销。`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await chatbotApi.deleteFAQ(faq.id!)
          message.success('已删除')
          setFaqs((prev) => prev.filter((f) => f.id !== faq.id))
        } catch (e) {
          message.error(extractApiError(e, '删除失败'), 3)
        }
      },
    })
  }

  // 打开编辑/新增 Modal
  const openModal = (faq: FAQ | null): void => {
    if (faq) {
      setForm(faq)
      setEditingFaq(faq)
    } else {
      setForm({ question: '', answer: '', category: '通用', enabled: true })
      setEditingFaq(null)
    }
    setModalOpen(true)
  }

  // 保存 FAQ
  const saveFaq = async (): Promise<void> => {
    if (!form.question.trim() || !form.answer.trim()) {
      message.warning('问题和答案不能为空')
      return
    }
    try {
      await chatbotApi.upsertFAQ(form)
      message.success('已保存')
      setModalOpen(false)
      const list = await chatbotApi.listFAQ()
      setFaqs(list)
    } catch (e) {
      message.error(extractApiError(e, '保存失败'), 3)
    }
  }

  if (loading || !config) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  return (
    <div>
      {/* 启用开关 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 600 }}>启用智能客服</div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary }}>
              关闭后用户将无法发起对话
            </div>
          </div>
          <Switch checked={config.enabled} onChange={toggleEnabled} />
        </div>
      </Card>

      {/* 欢迎语预览 */}
      <Card
        size="small"
        style={{ marginBottom: 12 }}
        title="欢迎语预览"
        extra={<Tag color="blue">仅展示</Tag>}
      >
        {welcome ? (
          <div style={{ fontSize: 14, padding: 12, background: themeToken.colorBgLayout, borderRadius: 6 }}>
            {welcome.message || '(未配置欢迎语)'}
          </div>
        ) : (
          <div style={{ fontSize: 13, color: themeToken.colorTextTertiary }}>加载中...</div>
        )}
      </Card>

      {/* FAQ 列表 */}
      <Card
        size="small"
        style={{ marginBottom: 12 }}
        title={`FAQ 列表 (${faqs.length})`}
        extra={
          <Button
            size="small"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => openModal(null)}
          >
            新增
          </Button>
        }
      >
        {faqs.length === 0 ? (
          <Empty description="暂无 FAQ" imageStyle={{ height: 60 }} />
        ) : (
          <List
            size="small"
            dataSource={faqs}
            renderItem={(faq) => (
              <List.Item
                key={faq.id}
                actions={[
                  <Button
                    key="edit"
                    size="small"
                    type="text"
                    icon={<EditOutlined />}
                    onClick={() => openModal(faq)}
                  />,
                  <Button
                    key="del"
                    size="small"
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => deleteFaq(faq)}
                  />,
                ]}
              >
                <List.Item.Meta
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 14 }}>{faq.question}</span>
                      <Tag color="default" style={{ fontSize: 10 }}>{faq.category}</Tag>
                    </div>
                  }
                  description={
                    <div style={{ fontSize: 12, color: themeToken.colorTextSecondary }}>
                      {faq.answer}
                    </div>
                  }
                />
                <Switch
                  size="small"
                  checked={faq.enabled}
                  onChange={(v) => void toggleFaq(faq, v)}
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* 编辑/新增 Modal */}
      <Modal
        title={editingFaq ? '编辑 FAQ' : '新增 FAQ'}
        open={modalOpen}
        onOk={saveFaq}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
        width="90%"
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>问题</div>
            <Input
              value={form.question}
              onChange={(e) => setForm({ ...form, question: e.target.value })}
              placeholder="用户可能问的问题"
              maxLength={200}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>答案</div>
            <Input.TextArea
              value={form.answer}
              onChange={(e) => setForm({ ...form, answer: e.target.value })}
              placeholder="标准回复内容"
              rows={4}
              maxLength={500}
            />
          </div>
          <div>
            <div style={{ fontSize: 12, color: themeToken.colorTextSecondary, marginBottom: 4 }}>分类</div>
            <Input
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              placeholder="如：通用 / 价格 / 订单"
              maxLength={20}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Switch
              checked={form.enabled}
              onChange={(v) => setForm({ ...form, enabled: v })}
            />
            <span style={{ fontSize: 13 }}>启用</span>
          </div>
        </Space>
      </Modal>
    </div>
  )
}
