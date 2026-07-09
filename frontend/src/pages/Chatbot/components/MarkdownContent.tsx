/**
 * Markdown 渲染组件（桌面/移动端共享）
 *
 * 为什么独立组件：桌面端 AssistantMessage 与移动端 Chatbot 都需要 markdown
 * 渲染（标题/列表/代码块/表格/链接/加粗/斜体），原桌面端把 ReactMarkdown + 引用
 * 链接预处理内联在 AssistantMessage 中，移动端无法复用。提取后：
 * - 单一可信源：markdown 渲染样式/插件/链接转换规则集中维护
 * - 移动端精简版：不展示桌面端的评分/反馈/来源面板/转人工告警，但 markdown 渲染效果一致
 * - 解耦样式：包一层 .m-md（移动端）/ .cb-md（桌面端）className 即可切换上下文样式
 *
 * 关键修复：
 * - 截图中的 `?????`（9 个问号）实际是 LLM 输出的 markdown 表格分隔符 `---` 在
 *   pre-wrap 文本中逐字渲染后的视觉混淆，markdown 渲染后会自动解析为表格
 * - 移动端原本 `whiteSpace: pre-wrap` 直接拼接 content 导致 markdown 源码全部暴露
 */
import { useMemo, useState, useRef, createContext, useContext } from 'react'
import { Tag, Tooltip, message, theme } from 'antd'
import { CopyOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/atom-one-light.css'
import type { Source } from '../types'

// 引用来源上下文：MarkdownLink 通过 context 拿到 sources 用于渲染 Tooltip
// 提取到模块顶层避免 MarkdownLink 内部定义 context（SonarQube S6478）
const SourcesContext = createContext<ReadonlyArray<Source> | undefined>(undefined)

interface MarkdownContentProps {
  readonly content: string
  /** 引用来源：用于把 [来源:N] 渲染为带 Tooltip 的 Tag；为空时不做预处理 */
  readonly sources?: ReadonlyArray<Source>
  /** 外层包裹 className，移动端可传 'm-md' 复用移动端样式表 */
  readonly className?: string
}

// 把 [来源:N] 转成 Markdown 链接 [来源:N](#cite-N)，让 ReactMarkdown 解析为 <a> 标签
// 必须跳过代码块和行内代码，否则代码内的 [来源:N] 字面量会被破坏
function preprocessCitations(
  content: string,
  hasSources: boolean,
): string {
  if (!hasSources) return content
  // replaceAll 显式表达"全局替换"语义，比 replace + g flag 更清晰（SonarQube S7781）
  const replaceCitations = (text: string) =>
    text.replaceAll(/\[来源:(\d+|\?)\]/g, (_m, num) => `[来源:${num}](#cite-${num})`)
  const parts: string[] = []
  let lastIndex = 0
  const codeRe = /```[\s\S]*?```|`[^`\n]+`/g
  let m: RegExpExecArray | null
  while ((m = codeRe.exec(content)) !== null) {
    // 合并相邻 push 为单次调用，减少数组操作次数（SonarQube S7778）
    parts.push(replaceCitations(content.slice(lastIndex, m.index)), m[0])
    lastIndex = m.index + m[0].length
  }
  parts.push(replaceCitations(content.slice(lastIndex)))
  return parts.join('')
}

// Markdown 链接渲染：#cite- 开头的引用链接渲染为带 Tooltip 的 Tag，其他走原生 <a>
// 提取到模块顶层避免在 MarkdownContent 内定义子组件（SonarQube S6478/S6767）
function MarkdownLink({ href, children }: {
  readonly href?: string
  readonly children?: React.ReactNode
}) {
  // useContext 必须在条件判断之前无条件调用（React Hooks 规则）
  const sources = useContext(SourcesContext)
  // href 用可选链：避免对 undefined 调用 startsWith（SonarQube S6582）
  if (href?.startsWith('#cite-')) {
    const refNum = href.slice(6)
    const source = sources?.find((s) => s.index === Number.parseInt(refNum, 10))
    return (
      <Tooltip title={source ? `${source.file} · ${source.section}` : '来源未知'}>
        <Tag color="cyan" style={{ cursor: 'pointer', margin: '0 2px' }}>[来源:{refNum}]</Tag>
      </Tooltip>
    )
  }
  return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
}

// 代码块包装：添加语言标签 + 复制按钮
// 提取到模块顶层避免在 MarkdownContent 内定义子组件（SonarQube S6478）
function MarkdownPre({ children }: { readonly children?: React.ReactNode }) {
  const child = Array.isArray(children) ? children[0] : children
  if (child && typeof child === 'object' && 'props' in child) {
    const codeProps = (child as React.ReactElement<{ readonly className?: string; readonly children?: React.ReactNode }>).props
    return <CodeBlock className={codeProps.className}>{codeProps.children}</CodeBlock>
  }
  return <pre>{children}</pre>
}

// 代码块组件：语言标签 + 复制按钮 + 语法高亮（rehype-highlight 已处理）
function CodeBlock({ children, className }: { readonly children?: React.ReactNode; readonly className?: string }) {
  const [copied, setCopied] = useState(false)
  const codeRef = useRef<HTMLElement>(null)
  const lang = (className || '').replace('language-', '') || ''

  const handleCopy = async () => {
    // 从 DOM 取 textContent：rehype-highlight 处理后 children 是高亮 spans，不是纯文本
    const text = codeRef.current?.textContent || ''
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      message.error('复制失败')
    }
  }

  return (
    <div className="cb-md-code-wrap">
      <div className="cb-md-code-header">
        <span className="cb-md-code-lang">{lang || 'text'}</span>
        <button
          type="button"
          className="cb-md-copy-btn"
          onClick={handleCopy}
          aria-label="复制代码"
        >
          <CopyOutlined /> {copied ? '已复制' : '复制'}
        </button>
      </div>
      <pre>
        <code ref={codeRef} className={className}>{children}</code>
      </pre>
    </div>
  )
}

/**
 * MarkdownContent：纯渲染组件，不包含评分/反馈/来源面板等交互。
 * 桌面端 AssistantMessage 在此组件外层包评分/反馈/转人工告警，
 * 移动端 Chatbot 直接调用此组件渲染消息内容。
 */
export function MarkdownContent({ content, sources, className }: MarkdownContentProps) {
  // 引用链接预处理：sources 为空时不做替换（避免无意义正则）
  const processedContent = useMemo(
    () => preprocessCitations(content, !!(sources && sources.length > 0)),
    [content, sources],
  )
  // components 引用模块顶层组件，避免在组件内定义子组件（SonarQube S6478）
  // 依赖数组为空：MarkdownLink / MarkdownPre 均为顶层稳定引用
  const mdComponents = useMemo(() => ({
    a: MarkdownLink,
    pre: MarkdownPre,
  }), [])

  return (
    <div className={className ?? 'cb-md'}>
      <SourcesContext.Provider value={sources}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={mdComponents}
        >
          {processedContent}
        </ReactMarkdown>
      </SourcesContext.Provider>
    </div>
  )
}

// 工具函数：消费主题 token 包装（桌面/移动端可自定义气泡颜色）
// 为什么导出：移动端/桌面端在包裹 MarkdownContent 时需根据 user/assistant
// 角色切换气泡背景色，主题色通过 theme.useToken() 获取；这里仅避免
// 重复 import theme，保持组件对 antd 主题系统的解耦
export const _useMarkdownTheme = (): { readonly colorTextSecondary: string } => {
  const { token } = theme.useToken()
  return { colorTextSecondary: token.colorTextSecondary }
}
