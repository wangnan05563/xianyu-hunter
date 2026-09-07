import { useEffect, useState } from 'react'
import { Empty, Skeleton } from 'antd'
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
import { TipButton } from '@/components/TipButton'

interface Props {
  readonly onQuestionClick: (q: string) => void  // 点击 FAQ 立即发送
  readonly onDismiss: () => void  // 关闭引导
}

// 能力标签：图标 + 一句话，横向平铺，克制不喧宾夺主
const HOT_FEATURES = [
  { key: 'kb', icon: <BookOutlined />, title: '知识库问答' },
  { key: 'tools', icon: <ToolOutlined />, title: '工具调用' },
  { key: 'human', icon: <CustomerServiceOutlined />, title: '人工转接' },
  { key: 'vision', icon: <PictureOutlined />, title: '图片识别' },
] as const

// 使用提示：合并为一行，降低底部信息密度
const TIPS = 'Shift+Enter 换行 · 拖拽 / 粘贴 / 点击上传图片 · 点赞 / 点踩帮助我们改进'

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
  if (hasHistory) return '欢迎回来，有什么可以帮您的？'
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
          // 只取 enabled=true 且 id 存在（避免空对象），按 sort_order 排序后取前 6
          setFaqs(
            f.value
              .filter((x) => x.enabled && x.id !== undefined)
              .slice(0, 6),
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
    : '有什么可以帮您的？'

  // 常见问题区：提取为独立变量消除嵌套三元 (typescript:S3358)
  const faqSection = loading ? (
    <Skeleton active paragraph={{ rows: 2 }} title={false} />
  ) : faqs.length === 0 ? (
    <Empty
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description="暂无常见问题"
      style={{ margin: '24px 0', color: 'var(--cb-text-tertiary)' }}
    />
  ) : (
    <div className="cb-faq-grid">
      {faqs.map((faq) => (
        <button
          type="button"
          key={faq.id}
          className="cb-faq-card"
          onClick={() => onQuestionClick(faq.question)}
        >
          <span className="cb-faq-question">{faq.question}</span>
          <ArrowRightOutlined className="cb-faq-arrow" />
        </button>
      ))}
    </div>
  )
  return (
    <div className="cb-onboarding">
      <TipButton
        type="text"
        size="small"
        tip="关闭引导卡片"
        icon={<CloseOutlined />}
        onClick={onDismiss}
        className="cb-onboarding-close"
        aria-label="关闭引导"
      />

      <div className="cb-onboarding-center">
        <div className="cb-onboarding-hero">
          <h1 className="cb-onboarding-greeting">{greeting}</h1>
          <p className="cb-onboarding-subtitle">
            基于项目知识库与工具调用，为您提供准确答案
          </p>
        </div>

        {/* 能力标签 */}
        <div className="cb-onboarding-features">
          {HOT_FEATURES.map((f) => (
            <div key={f.key} className="cb-feature-card">
              <span className="cb-feature-icon">{f.icon}</span>
              <span className="cb-feature-title">{f.title}</span>
            </div>
          ))}
        </div>

        {/* 常见问题快捷入口 */}
        <div className="cb-onboarding-section">
          <div className="cb-onboarding-section-title">常见问题</div>
          {faqSection}
        </div>

        {/* 使用提示 */}
        <div className="cb-onboarding-tips">
          <BulbOutlined style={{ fontSize: 12 }} />
          <span>{TIPS}</span>
        </div>
      </div>
    </div>
  )
}
