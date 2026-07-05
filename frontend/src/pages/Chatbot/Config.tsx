import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Tabs, Switch, InputNumber, Input, Button, Slider, Radio, Table, Modal,
  Card, Tag, message, Space, Typography, List,
} from 'antd'
import { PlusOutlined, DeleteOutlined, RollbackOutlined, HistoryOutlined } from '@ant-design/icons'
import { chatbotApi } from './api'
import { KBStatusCard } from './components/KBStatusCard'
import { VectorAdminPanel } from './components/VectorAdminPanel'
import type { ChatbotConfig, KBStatus, KBVersion, FAQ, AuditLog } from './types'

// 按点分路径更新嵌套字段（如 'rag.top_k'），返回新对象保持不可变
function setNestedField<T>(obj: T, path: string, value: unknown): T {
  const keys = path.split('.')
  if (keys.length === 1) {
    return { ...obj, [keys[0]]: value } as T
  }
  const [first, ...rest] = keys
  return {
    ...obj,
    [first]: setNestedField((obj as Record<string, unknown>)[first], rest.join('.'), value),
  } as T
}

// 从审计日志中过滤出重建/回滚记录，按时间倒序取前 5 条
// 后端 audit log 写入时 target 字段格式为 "{vid}|status:{status}|chunks:{n}" 或 "from:{vid}→to:{vid}|..."
function pickRebuildLogs(logs: AuditLog[]): AuditLog[] {
  return logs
    .filter(l => l.action === 'kb_rebuild' || l.action === 'kb_rollback')
    .slice(0, 5)
}

export default function ChatbotConfigPage() {
  const [config, setConfig] = useState<ChatbotConfig | null>(null)
  const [kbStatus, setKbStatus] = useState<KBStatus | null>(null)
  const [kbVersions, setKbVersions] = useState<KBVersion[]>([])
  const [faqs, setFaqs] = useState<FAQ[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(false)
  const [faqModalOpen, setFaqModalOpen] = useState(false)
  const [editingFaq, setEditingFaq] = useState<FAQ | null>(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    // 错误隔离：每个请求独立 catch，单个失败不影响其他状态
    // 否则 chatbot 模块未启用时 Promise.all 整体 reject，kbVersions 保持空，看起来"无重建记录"
    const safe = <T,>(p: Promise<T>, fallback: T): Promise<T> =>
      p.catch(() => fallback)

    try {
      const [cfg, status, versions, faqList, auditRes] = await Promise.all([
        chatbotApi.getConfig().catch(() => null),
        safe(chatbotApi.getKBStatus(), null),
        safe(chatbotApi.listKBVersions(), [] as KBVersion[]),
        safe(chatbotApi.listFAQ(), [] as FAQ[]),
        safe(chatbotApi.listAuditLogs(1, 50), { items: [] as AuditLog[], total: 0 }),
      ])
      if (!cfg) {
        message.error('智能客服模块未启用或加载失败')
      } else {
        setConfig(cfg)
      }
      if (status) setKbStatus(status)
      setKbVersions(versions)
      setFaqs(faqList)
      setAuditLogs(auditRes.items)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  // building 状态轮询：构建中每 2 秒拉取一次 status，构建完成时整体刷新
  // 不再使用单次 setTimeout，因为大型知识库构建可能 30s+，单次刷新无法感知中途进度
  useEffect(() => {
    if (!kbStatus?.building) return
    const timer = setInterval(async () => {
      try {
        const status = await chatbotApi.getKBStatus()
        setKbStatus(status)
        if (!status.building) {
          // 构建结束：停止轮询并整体刷新（拿到新版本列表和审计日志）
          loadAll()
        }
      } catch {
        // 静默失败，下次轮询继续
      }
    }, 2000)
    return () => clearInterval(timer)
  }, [kbStatus?.building, loadAll])

  // 按 key 防抖的 PUT 定时器（H-6/7/8 修复：Slider/Input 高频 onChange 避免洪水 PUT）
  const updateTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  const updateConfig = (key: string, value: string | number | boolean) => {
    // 即时更新本地状态，避免 Slider 拖动 / Input 输入时 UI 回弹到旧值
    setConfig(prev => prev ? setNestedField(prev, key, value) : prev)
    // 同 key 防抖 500ms：连续拖动 / 按键只发一次 PUT
    if (updateTimersRef.current[key]) {
      clearTimeout(updateTimersRef.current[key])
    }
    updateTimersRef.current[key] = setTimeout(async () => {
      try {
        await chatbotApi.updateConfig(key, String(value))
        message.success('配置已更新')
      } catch {
        message.error('更新失败')
        // 失败时重新加载以回滚本地状态
        const cfg = await chatbotApi.getConfig()
        setConfig(cfg)
      }
      delete updateTimersRef.current[key]
    }, 500)
  }

  // 组件卸载时清理防抖定时器，避免内存泄漏与卸载后状态更新
  useEffect(() => {
    return () => {
      Object.values(updateTimersRef.current).forEach(t => clearTimeout(t))
    }
  }, [])

  const handleRebuild = async (force: boolean) => {
    await chatbotApi.rebuildKB(force)
    // 立即拉取一次 status 触发 building=true，让轮询 useEffect 接管后续进度
    try {
      const status = await chatbotApi.getKBStatus()
      setKbStatus(status)
    } catch {
      // 静默：轮询 useEffect 会在 2s 后自动重试
    }
  }

  const handleRollback = async (versionId: string) => {
    Modal.confirm({
      title: '回滚知识库',
      content: '确定回滚到此版本？回滚期间对话功能短暂不可用。',
      onOk: async () => {
        try {
          await chatbotApi.rollbackKB(versionId)
          message.success('回滚成功')
          loadAll()
        } catch {
          message.error('回滚失败')
        }
      },
    })
  }

  const handleSaveFaq = async (faq: FAQ) => {
    try {
      await chatbotApi.upsertFAQ(faq)
      message.success('已保存')
      setFaqModalOpen(false)
      const list = await chatbotApi.listFAQ()
      setFaqs(list)
    } catch {
      message.error('保存失败')
    }
  }

  const handleDeleteFaq = async (id: number) => {
    try {
      await chatbotApi.deleteFAQ(id)
      message.success('已删除')
      const list = await chatbotApi.listFAQ()
      setFaqs(list)
    } catch {
      message.error('删除失败')
    }
  }

  const loadAuditLogs = async () => {
    try {
      const { items } = await chatbotApi.listAuditLogs(1, 50)
      setAuditLogs(items)
    } catch {
      message.error('加载审计日志失败')
    }
  }

  if (loading || !config) {
    return <Card loading={loading}>加载中...</Card>
  }

  const rebuildLogs = pickRebuildLogs(auditLogs)

  return (
    <Card title="智能客服配置">
      <Tabs
        items={[
          {
            key: 'basic',
            label: '基础配置',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <div>
                  <Typography.Text>启用智能客服</Typography.Text>
                  <Switch
                    checked={config.enabled}
                    onChange={(v) => updateConfig('enabled', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
                <div>
                  <Typography.Text>历史轮数（1-20）</Typography.Text>
                  <InputNumber
                    min={1} max={20}
                    value={config.max_history_turns}
                    onChange={(v) => v && updateConfig('max_history_turns', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
                <div>
                  <Typography.Text>会话超时（分钟，5-1440）</Typography.Text>
                  <InputNumber
                    min={5} max={1440}
                    value={config.session_timeout_min}
                    onChange={(v) => v && updateConfig('session_timeout_min', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
              </Space>
            ),
          },
          {
            key: 'rag',
            label: 'RAG 检索',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <div>
                  <Typography.Text>top_k（1-20）</Typography.Text>
                  <InputNumber
                    min={1} max={20}
                    value={config.rag.top_k}
                    onChange={(v) => v && updateConfig('rag.top_k', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
                <div>
                  <Typography.Text>相似度阈值（0-1，热更新）</Typography.Text>
                  <Slider
                    min={0} max={1} step={0.05}
                    value={config.rag.similarity_threshold}
                    onChange={(v) => updateConfig('rag.similarity_threshold', v)}
                    style={{ width: 300, marginLeft: 16, display: 'inline-flex' }}
                  />
                </div>
                <div>
                  <Typography.Text>context 最大字符（500-32000）</Typography.Text>
                  <InputNumber
                    min={500} max={32000}
                    value={config.rag.max_context_chars}
                    onChange={(v) => v && updateConfig('rag.max_context_chars', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
              </Space>
            ),
          },
          {
            key: 'agent',
            label: 'AGENT 工具',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <div>
                  <Typography.Text>启用工具</Typography.Text>
                  <Switch
                    checked={config.agent.enable_tools}
                    onChange={(v) => updateConfig('agent.enable_tools', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
                <div>
                  <Typography.Text>最大轮数（1-10）</Typography.Text>
                  <InputNumber
                    min={1} max={10}
                    value={config.agent.max_tool_rounds}
                    onChange={(v) => v && updateConfig('agent.max_tool_rounds', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
                <div>
                  <Typography.Text>触发模式</Typography.Text>
                  <Radio.Group
                    value={config.agent.tool_trigger_mode}
                    onChange={(e) => updateConfig('agent.tool_trigger_mode', e.target.value)}
                    style={{ marginLeft: 16 }}
                  >
                    <Radio value="function_calling">function_calling</Radio>
                    <Radio value="fallback">fallback</Radio>
                  </Radio.Group>
                </div>
              </Space>
            ),
          },
          {
            key: 'kb',
            label: '知识库管理',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                {kbStatus && <KBStatusCard status={kbStatus} onRebuild={handleRebuild} />}
                <Card
                  size="small"
                  title={
                    <Space>
                      <HistoryOutlined />
                      <span>最近重建记录</span>
                    </Space>
                  }
                >
                  {rebuildLogs.length === 0 ? (
                    <Typography.Text type="secondary">暂无重建记录</Typography.Text>
                  ) : (
                    <List
                      size="small"
                      dataSource={rebuildLogs}
                      renderItem={(log) => (
                        <List.Item>
                          <List.Item.Meta
                            avatar={
                              <Tag color={log.action === 'kb_rebuild' ? 'blue' : 'purple'}>
                                {log.action === 'kb_rebuild' ? '重建' : '回滚'}
                              </Tag>
                            }
                            title={
                              <Typography.Text style={{ fontSize: 12 }}>
                                {log.target}
                              </Typography.Text>
                            }
                            description={
                              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                                {log.created_at} · 来源：{log.source}
                              </Typography.Text>
                            }
                          />
                        </List.Item>
                      )}
                    />
                  )}
                </Card>
                <div>
                  <Typography.Text>定时自动更新</Typography.Text>
                  <Switch
                    checked={config.kb.auto_update_enabled}
                    onChange={(v) => updateConfig('kb.auto_update_enabled', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
                <div>
                  <Typography.Text>更新间隔（小时，1-168）</Typography.Text>
                  <InputNumber
                    min={1} max={168}
                    value={config.kb.update_interval_hours}
                    onChange={(v) => v && updateConfig('kb.update_interval_hours', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
                <Table
                  size="small"
                  rowKey="id"
                  dataSource={kbVersions}
                  pagination={{ pageSize: 5 }}
                  columns={[
                    { title: '版本', dataIndex: 'id', key: 'id', render: (v: string) => <Tag>{v.slice(0, 8)}</Tag> },
                    { title: '类型', dataIndex: 'build_type', key: 'build_type' },
                    { title: '片段数', dataIndex: 'chunk_count', key: 'chunk_count' },
                    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={s === 'success' ? 'green' : s === 'partial' ? 'orange' : 'red'}>{s}</Tag> },
                    { title: '时间', dataIndex: 'created_at', key: 'created_at' },
                    {
                      title: '操作', key: 'actions',
                      render: (_: unknown, record: KBVersion) => (
                        <Button
                          size="small"
                          icon={<RollbackOutlined />}
                          disabled={record.is_current}
                          onClick={() => handleRollback(record.id)}
                        >
                          回滚
                        </Button>
                      ),
                    },
                  ]}
                />
              </Space>
            ),
          },
          {
            key: 'faq',
            label: 'FAQ 管理',
            children: (
              <>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  style={{ marginBottom: 16 }}
                  onClick={() => { setEditingFaq(null); setFaqModalOpen(true) }}
                >
                  新增 FAQ
                </Button>
                <Table
                  size="small"
                  rowKey="id"
                  dataSource={faqs}
                  pagination={{ pageSize: 10 }}
                  columns={[
                    { title: '问题', dataIndex: 'question', key: 'question', ellipsis: true },
                    { title: '答案', dataIndex: 'answer', key: 'answer', ellipsis: true },
                    { title: '分类', dataIndex: 'category', key: 'category' },
                    { title: '启用', dataIndex: 'enabled', key: 'enabled', render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '是' : '否'}</Tag> },
                    {
                      title: '操作', key: 'actions',
                      render: (_: unknown, record: FAQ) => (
                        <Space>
                          <Button size="small" onClick={() => { setEditingFaq(record); setFaqModalOpen(true) }}>编辑</Button>
                          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => record.id && handleDeleteFaq(record.id)} />
                        </Space>
                      ),
                    },
                  ]}
                />
                <FaqEditModal
                  open={faqModalOpen}
                  faq={editingFaq}
                  onSave={handleSaveFaq}
                  onCancel={() => setFaqModalOpen(false)}
                />
              </>
            ),
          },
          {
            key: 'escalation',
            label: '转人工',
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <div>
                  <Typography.Text>点踩阈值（1-10，热更新）</Typography.Text>
                  <InputNumber
                    min={1} max={10}
                    value={config.escalation.feedback_threshold}
                    onChange={(v) => v && updateConfig('escalation.feedback_threshold', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
                <div>
                  <Typography.Text>统计窗口（分钟，5-1440，热更新）</Typography.Text>
                  <InputNumber
                    min={5} max={1440}
                    value={config.escalation.feedback_window_min}
                    onChange={(v) => v && updateConfig('escalation.feedback_window_min', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
                <div>
                  <Typography.Text>联系方式（热更新）</Typography.Text>
                  <Input
                    value={config.escalation.contact}
                    onChange={(e) => updateConfig('escalation.contact', e.target.value)}
                    placeholder="如：QQ群 123456"
                    style={{ marginLeft: 16, width: 300 }}
                  />
                </div>
                <div>
                  <Typography.Text>PII 脱敏</Typography.Text>
                  <Switch
                    checked={config.escalation.sanitize_pii}
                    onChange={(v) => updateConfig('escalation.sanitize_pii', v)}
                    style={{ marginLeft: 16 }}
                  />
                </div>
              </Space>
            ),
          },
          {
            key: 'vector-admin',
            label: '向量库维护',
            children: <VectorAdminPanel />,
          },
          {
            key: 'audit',
            label: '审计日志',
            children: (
              <>
                <Button style={{ marginBottom: 16 }} onClick={loadAuditLogs}>刷新</Button>
                <Table
                  size="small"
                  rowKey="id"
                  dataSource={auditLogs}
                  pagination={{ pageSize: 20 }}
                  columns={[
                    { title: '动作', dataIndex: 'action', key: 'action' },
                    { title: '目标', dataIndex: 'target', key: 'target', ellipsis: true },
                    { title: '来源', dataIndex: 'source', key: 'source' },
                    { title: '时间', dataIndex: 'created_at', key: 'created_at' },
                  ]}
                />
              </>
            ),
          },
        ]}
      />
    </Card>
  )
}

// FAQ 编辑弹窗
function FaqEditModal({
  open, faq, onSave, onCancel,
}: {
  open: boolean
  faq: FAQ | null
  onSave: (faq: FAQ) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState<FAQ>({
    question: '',
    answer: '',
    category: '通用',
    enabled: true,
  })

  useEffect(() => {
    if (faq) {
      setForm(faq)
    } else {
      setForm({ question: '', answer: '', category: '通用', enabled: true })
    }
  }, [faq, open])

  return (
    <Modal
      title={faq ? '编辑 FAQ' : '新增 FAQ'}
      open={open}
      onOk={() => onSave(form)}
      onCancel={onCancel}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Input
          placeholder="问题"
          value={form.question}
          onChange={(e) => setForm({ ...form, question: e.target.value })}
        />
        <Input.TextArea
          placeholder="答案"
          rows={4}
          value={form.answer}
          onChange={(e) => setForm({ ...form, answer: e.target.value })}
        />
        <Input
          placeholder="分类"
          value={form.category}
          onChange={(e) => setForm({ ...form, category: e.target.value })}
        />
        <div>
          <Typography.Text>启用</Typography.Text>
          <Switch
            checked={form.enabled}
            onChange={(v) => setForm({ ...form, enabled: v })}
            style={{ marginLeft: 16 }}
          />
        </div>
      </Space>
    </Modal>
  )
}
