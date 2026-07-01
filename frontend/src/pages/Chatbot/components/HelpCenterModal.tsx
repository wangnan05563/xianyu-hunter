import { useState, useEffect } from 'react'
import { Modal, Collapse, Tag, Typography, Spin } from 'antd'
import {
  BookOutlined,
  QuestionCircleOutlined,
  KeyOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import { aboutApi } from '../../../api'

const { Text } = Typography

// 使用指南数据
const GUIDE_ITEMS = [
  { title: '智能问答', desc: '输入问题，AI 自动匹配知识库回答，支持多轮对话上下文' },
  { title: '图片识别', desc: '拖拽 / 粘贴 / 点击上传图片（最多 4 张），AI 可解析图片内容' },
  { title: '工具调用', desc: '启用工具后，AI 可查询任务状态、价格走势等实时数据' },
  { title: '消息撤回', desc: '发送后 2 分钟内可撤回用户消息，撤回后 AI 不再引用该内容' },
  { title: '会话收藏', desc: '点击星标收藏重要会话，收藏的会话自动置顶显示' },
  { title: '会话搜索', desc: '在侧边栏搜索框输入关键词，可搜索会话标题和消息内容' },
]

// 常见问题数据
const FAQ_ITEMS = [
  { q: '如何创建监控任务？', a: '在任务管理页面点击"新建任务"，填写关键词和筛选条件即可' },
  { q: '如何配置价格提醒？', a: '在任务详情页的"价格规则"中设置目标价格，触发后自动通知' },
  { q: '支持哪些平台？', a: '当前支持闲鱼平台商品监控，后续将扩展更多电商平台' },
  { q: '数据如何导出？', a: '在 Dashboard 页面点击"导出"按钮，支持 CSV 和 JSON 格式' },
  { q: 'AI 回答不准确？', a: '可点踩反馈，连续负反馈会自动转人工；也可在知识库管理中补充资料' },
  { q: '如何转人工？', a: '点击侧边栏"立即转人工"按钮，或连续点踩触发自动转接' },
]

// 快捷键说明
const SHORTCUTS = [
  { key: 'Enter', desc: '发送消息' },
  { key: 'Shift + Enter', desc: '输入框换行' },
  { key: 'Ctrl + Shift + R', desc: '强制刷新页面（清除缓存）' },
]

// 版本信息接口（与 AboutInfo 对齐）
interface VersionInfo {
  version: string
  build_date: string
  git_sha: string
}

export default function HelpCenterModal({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const [version, setVersion] = useState<VersionInfo | null>(null)
  const [loading, setLoading] = useState(false)

  // 弹窗打开时获取版本信息
  useEffect(() => {
    if (!open || version) return
    setLoading(true)
    aboutApi
      .get()
      .then((info) => {
        setVersion({
          version: info.version,
          build_date: info.build_date,
          git_sha: info.git_sha,
        })
      })
      .catch(() => {
        // 版本信息获取失败不阻塞弹窗
      })
      .finally(() => setLoading(false))
  }, [open, version])

  const collapseItems = [
    {
      key: 'guide',
      label: (
        <span><BookOutlined style={{ marginRight: 6 }} />使用指南</span>
      ),
      children: (
        <div className="cb-help-section">
          {GUIDE_ITEMS.map((item) => (
            <div key={item.title} className="cb-help-guide-item">
              <Text strong className="cb-help-guide-title">{item.title}</Text>
              <Text type="secondary" className="cb-help-guide-desc">{item.desc}</Text>
            </div>
          ))}
        </div>
      ),
    },
    {
      key: 'faq',
      label: (
        <span><QuestionCircleOutlined style={{ marginRight: 6 }} />常见问题</span>
      ),
      children: (
        <div className="cb-help-section">
          {FAQ_ITEMS.map((item) => (
            <div key={item.q} className="cb-help-faq-item">
              <Text strong className="cb-help-faq-q">Q: {item.q}</Text>
              <Text type="secondary" className="cb-help-faq-a">A: {item.a}</Text>
            </div>
          ))}
        </div>
      ),
    },
    {
      key: 'shortcuts',
      label: (
        <span><KeyOutlined style={{ marginRight: 6 }} />快捷键</span>
      ),
      children: (
        <div className="cb-help-section">
          {SHORTCUTS.map((s) => (
            <div key={s.key} className="cb-help-shortcut-item">
              <Tag className="cb-help-key-tag">{s.key}</Tag>
              <Text type="secondary">{s.desc}</Text>
            </div>
          ))}
        </div>
      ),
    },
    {
      key: 'version',
      label: (
        <span><InfoCircleOutlined style={{ marginRight: 6 }} />版本信息</span>
      ),
      children: (
        <div className="cb-help-section cb-help-version">
          {loading ? (
            <Spin size="small" />
          ) : version ? (
            <>
              <div className="cb-help-version-row">
                <Text type="secondary">版本</Text>
                <Text strong>{version.version}</Text>
              </div>
              <div className="cb-help-version-row">
                <Text type="secondary">构建日期</Text>
                <Text>{version.build_date}</Text>
              </div>
              <div className="cb-help-version-row">
                <Text type="secondary">Git</Text>
                <Text code>{version.git_sha}</Text>
              </div>
            </>
          ) : (
            <Text type="secondary">版本信息加载中…</Text>
          )}
        </div>
      ),
    },
  ]

  return (
    <Modal
      title="帮助中心"
      open={open}
      onCancel={onClose}
      footer={null}
      width={560}
      className="cb-help-modal"
    >
      <Collapse
        defaultActiveKey={['guide']}
        items={collapseItems}
        className="cb-help-collapse"
      />
    </Modal>
  )
}
