import { useEffect, useState } from 'react'
import { Card, Tag, Space, Button, Empty, Skeleton } from 'antd'
import {
  CloseOutlined,
  BookOutlined,
  ToolOutlined,
  CustomerServiceOutlined,
  PictureOutlined,
  ArrowRightOutlined,
  BulbOutlined,
} from '@ant-design/icons'
import { chatbotApi } from '../api'
import type { FAQ, WelcomeInfo } from '../types'

interface Props {
  onQuestionClick: (q: string) => void  // 点击 FAQ 立即发送
  onDismiss: () => void  // 关闭引导
}

// 热门功能卡片：硬编码 4 张，点击跳转（不消耗 API）
const HOT_FEATURES = [
  { key: 'kb', icon: <BookOutlined />, title: '知识库问答', desc: '从项目文档中检索答案' },
  { key: 'tools', icon: <ToolOutlined />, title: '工具调用', desc: '查询任务、评估、配置' },
  { key: 'human', icon: <CustomerServiceOutlined />, title: '人工转接', desc: '点踩两次或主动触发' },
  { key: 'vision', icon: <PictureOutlined />, title: '图片识别', desc: '上传图片让 AI 解析' },
] as const

// 使用提示：硬编码 3 条小贴士
const TIPS = [
  'Shift+Enter 换行，Enter 发送',
  '拖拽 / 粘贴 / 点击图片按钮上传图片',
  '点赞 / 点踩帮助我们改进回复质量',
]

const ONBOARDING_DISMISSED_KEY = 'chatbot_onboarding_dismissed'

// 读取 localStorage 关闭标记
export function isOnboardingDismissed(): boolean {
  try {
    return localStorage.getItem(ONBOARDING_DISMISSED_KEY) === '1'
  } catch {
    return false
  }
}

// 重置关闭标记（创建新会话时调用，让引导卡再次出现）
export function resetOnboardingDismissed(): void {
  try {
    localStorage.removeItem(ONBOARDING_DISMISSED_KEY)
  } catch {
    // localStorage 不可用时静默忽略
  }
}

// 欢迎语个性化策略：基于时间 / 历史会话数量
function personalizeWelcome(base: string, hasHistory: boolean): string {
  const hour = new Date().getHours()
  const isNight = hour >= 22 || hour < 7
  if (isNight) return '夜深了，有什么需要帮忙的吗？'
  if (hasHistory) return '欢迎回来！请继续提问或选择下方常见问题'
  return base
}

export default function ChatbotOnboarding({ onQuestionClick, onDismiss }: Props) {
  const [welcome, setWelcome] = useState<WelcomeInfo | null>(null)
  const [faqs, setFaqs] = useState<FAQ[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    Promise.allSettled([chatbotApi.getWelcome(), chatbotApi.listFAQ()])
      .then(([w, f]) => {
        if (!alive) return
        if (w.status === 'fulfilled') setWelcome(w.value)
        if (f.status === 'fulfilled') {
          // 只取 enabled=true 且 id 存在（避免空对象），按 sort_order 排序后取前 5
          setFaqs(
            f.value
              .filter((x) => x.enabled && x.id !== undefined)
              .slice(0, 5),
          )
        }
        setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  // 欢迎语：DB 配置 → 个性化策略兜底
  const greeting = welcome
    ? personalizeWelcome(welcome.message, false)
    : 'Hi，我是智能客服小蜜，请问有什么可以帮您？'

  return (
    <div className="cb-onboarding">
      {/* 头部欢迎语 + 关闭 */}
      <div className="cb-onboarding-header">
        <div className="cb-onboarding-greeting">{greeting}</div>
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          onClick={onDismiss}
          className="cb-onboarding-close"
        />
      </div>

      {/* 热门功能卡片 */}
      <div className="cb-onboarding-features">
        {HOT_FEATURES.map((f) => (
          <div key={f.key} className="cb-feature-card">
            <div className="cb-feature-icon">{f.icon}</div>
            <div className="cb-feature-title">{f.title}</div>
            <div className="cb-feature-desc">{f.desc}</div>
          </div>
        ))}
      </div>

      {/* 常见问题快捷入口 */}
      <div className="cb-onboarding-section">
        <div className="cb-onboarding-section-title">📌 常见问题</div>
        {loading ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : faqs.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无常见问题"
            style={{ margin: '12px 0' }}
          />
        ) : (
          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            {faqs.map((faq) => (
              <div
                key={faq.id}
                className="cb-faq-item"
                onClick={() => onQuestionClick(faq.question)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onQuestionClick(faq.question)
                }}
              >
                <span className="cb-faq-question">{faq.question}</span>
                <ArrowRightOutlined className="cb-faq-arrow" />
              </div>
            ))}
          </Space>
        )}
      </div>

      {/* 使用提示 */}
      <div className="cb-onboarding-tips">
        <BulbOutlined style={{ marginRight: 6, color: 'var(--cb-yellow-light, #FFE082)' }} />
        {TIPS.map((t, i) => (
          <Tag key={i} className="cb-tip-tag">{t}</Tag>
        ))}
      </div>
    </div>
  )
}
