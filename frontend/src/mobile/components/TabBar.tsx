import { useLocation, useNavigate } from 'react-router-dom'
import {
  DashboardOutlined,
  UnorderedListOutlined,
  ThunderboltOutlined,
  MessageOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { theme } from 'antd'

// 底部 5 Tab 导航配置
const TABS = [
  { key: '/m', label: '仪表盘', icon: <DashboardOutlined /> },
  { key: '/m/tasks', label: '任务', icon: <UnorderedListOutlined /> },
  { key: '/m/orders', label: '抢单', icon: <ThunderboltOutlined /> },
  { key: '/m/chatbot', label: '客服', icon: <MessageOutlined /> },
  { key: '/m/profile', label: '我的', icon: <UserOutlined /> },
]

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { token: themeToken } = theme.useToken()

  // 判断当前 Tab 是否激活：精确匹配或前缀匹配
  const isActive = (key: string) => {
    if (key === '/m') return location.pathname === '/m'
    return location.pathname.startsWith(key)
  }

  return (
    <nav
      className="m-tabbar"
      style={{
        background: themeToken.colorBgContainer,
        borderTop: `1px solid ${themeToken.colorBorderSecondary}`,
      }}
    >
      {TABS.map((tab) => (
        <button
          key={tab.key}
          className={`m-tab-item ${isActive(tab.key) ? 'active' : ''}`}
          onClick={() => navigate(tab.key)}
          style={{
            color: isActive(tab.key) ? '#E20613' : themeToken.colorTextSecondary,
          }}
        >
          <span className="m-tab-icon">{tab.icon}</span>
          <span className="m-tab-label">{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}
