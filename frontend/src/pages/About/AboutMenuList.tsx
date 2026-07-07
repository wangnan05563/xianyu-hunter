import { Card, theme } from 'antd'
import { ExportOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { TEXTS } from './i18n'

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
  { key: 'api', label: TEXTS.menu.api, href: '/api/docs', external: true },
  { key: 'contact', label: TEXTS.menu.contact, href: 'mailto:dev@example.com', external: true },
  { key: 'community', label: TEXTS.menu.community, href: 'https://example.com/community', external: true },
  { key: 'report', label: TEXTS.menu.report, href: 'https://example.com/issues/new', external: true },
]

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
        borderBottom: idx < MENU_ITEMS.length - 1 ? `1px solid ${token.colorBorderSecondary}` : 'none',
        transition: 'background-color 120ms cubic-bezier(0.2, 0, 0, 1)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor = token.colorBgTextHover
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = 'transparent'
      }}
      onClick={(e) => handleClick(item, e)}
      // S6848/S1082：div 上有 click 处理，补充 role/tabIndex/onKeyDown 满足可访问性
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (item.key === 'licenses' && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          onOpenLicenses()
        }
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
      {MENU_ITEMS.map((item, idx) => {
        // help 为 SPA 内链，用 Link 组件避免整页刷新
        const isInternal = !item.external && item.key === 'help'
        if (isInternal) {
          return (
            <Link key={item.key} to={item.href} style={{ textDecoration: 'none', color: 'inherit' }}>
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
          >
            {renderContent(item, idx)}
          </a>
        )
      })}
    </Card>
  )
}
