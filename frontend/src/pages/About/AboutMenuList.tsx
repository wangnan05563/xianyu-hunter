import { Card, theme } from 'antd'
import { ExportOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { TEXTS } from './i18n'
import { API_BASE } from '../../utils/apiBase'

interface MenuItem {
  readonly key: string
  readonly label: string
  readonly href: string
  readonly external: boolean
}

// 8 个外部链接；按需求 §5.1 排序
const MENU_ITEMS: MenuItem[] = [
  { key: 'terms', label: TEXTS.menu.terms, href: 'https://example.com/terms', external: true },
  { key: 'privacy', label: TEXTS.menu.privacy, href: 'https://example.com/privacy', external: true },
  // licenses 触发 Modal，不走链接
  { key: 'licenses', label: TEXTS.menu.licenses, href: '#licenses', external: false },
  // help 为 SPA 内链（保留 /help 路由作回流入口）
  { key: 'help', label: TEXTS.menu.help, href: '/help', external: false },
  { key: 'api', label: TEXTS.menu.api, href: `${API_BASE}api/docs`, external: true },
  { key: 'contact', label: TEXTS.menu.contact, href: 'mailto:dev@example.com', external: true },
  { key: 'community', label: TEXTS.menu.community, href: 'https://example.com/community', external: true },
  { key: 'report', label: TEXTS.menu.report, href: 'https://example.com/issues/new', external: true },
]

// 发布版不得把占位域名交给用户：地址未就绪的条目不渲染，填入真实地址即自动出现
const PLACEHOLDER_HOST = 'example.com'
const VISIBLE_ITEMS = MENU_ITEMS.filter((item) => !item.href.includes(PLACEHOLDER_HOST))

interface AboutMenuListProps {
  readonly onOpenLicenses: () => void
}

export function AboutMenuList({ onOpenLicenses }: AboutMenuListProps) {
  const { token } = theme.useToken()

  const handleClick = (item: MenuItem, e: React.MouseEvent) => {
    if (item.key === 'licenses') {
      e.preventDefault()
      onOpenLicenses()
    }
  }

  const renderContent = (item: MenuItem, idx: number) => (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '14px 16px',
        cursor: 'pointer',
        borderBottom: idx < VISIBLE_ITEMS.length - 1 ? `1px solid ${token.colorBorderSecondary}` : 'none',
        transition: 'background-color 120ms cubic-bezier(0.2, 0, 0, 1)',
      }}
    >
      <span style={{ fontSize: 14, color: token.colorText }}>{item.label}</span>
      <ExportOutlined style={{ fontSize: 14, color: token.colorTextTertiary }} aria-hidden />
    </div>
  )

  return (
    <Card
      style={{
        background: token.colorBgContainer,
        border: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: 6,
        overflow: 'hidden',
      }}
      styles={{ body: { padding: 0 } }}
    >
      {VISIBLE_ITEMS.map((item, idx) => {
        // help 为 SPA 内链，用 Link 组件避免整页刷新
        const isInternal = !item.external && item.key === 'help'
        // S6819：移除内层 div 的 role="button"，交互由外层 a/Link 承担
        // hover/click 放在外层交互元素上，避免内层 div 触发 S6847
        const hoverHandlers = {
          onMouseEnter: (e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.backgroundColor = token.colorBgTextHover
          },
          onMouseLeave: (e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          },
        }
        if (isInternal) {
          return (
            <Link key={item.key} to={item.href} style={{ textDecoration: 'none', color: 'inherit' }} {...hoverHandlers}>
              {renderContent(item, idx)}
            </Link>
          )
        }
        return (
          <a
            key={item.key}
            href={item.href}
            target={item.external ? '_blank' : undefined}
            rel={item.external ? 'noopener noreferrer' : undefined}
            style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
            onClick={(e) => handleClick(item, e)}
            {...hoverHandlers}
          >
            {renderContent(item, idx)}
          </a>
        )
      })}
    </Card>
  )
}
