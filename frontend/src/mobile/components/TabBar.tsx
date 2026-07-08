import { useLocation, useNavigate } from 'react-router-dom'
import {
  DashboardOutlined,
  UnorderedListOutlined,
  ThunderboltOutlined,
  BellOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import { theme } from 'antd'

// 底部 5 Tab 导航：覆盖核心监控 + 关键操作
// key 必须带尾斜杠 /m/：父路由 <Route path="/m/*"> 的 splat 要求路径至少为 /m/，
// 用 /m（无尾斜杠）会不匹配 splat 导致渲染 null（白屏）
// 告警 Tab 合并时间线 + 通知中心，点击进入通知中心（高频入口）
// 客服 Tab 进入智能客服对话页
const TABS = [
  { key: '/m/', label: '仪表盘', icon: <DashboardOutlined /> },
  { key: '/m/tasks/', label: '任务', icon: <UnorderedListOutlined /> },
  { key: '/m/orders/', label: '抢单', icon: <ThunderboltOutlined /> },
  { key: '/m/notifications/', label: '告警', icon: <BellOutlined /> },
  { key: '/m/chatbot/', label: '客服', icon: <MessageOutlined /> },
]

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { token: themeToken } = theme.useToken()

  // 判断当前 Tab 是否激活：精确匹配或前缀匹配
  // /m 和 /m/ 都视为首页激活（Navigate 重定向 /m → /m/，但浏览器可能保持 /m）
  const isActive = (key: string) => {
    // 首页精确匹配 /m 或 /m/
    if (key === '/m/') return location.pathname === '/m' || location.pathname === '/m/'
    // 其他 Tab 前缀匹配：/m/tasks/ → /m/tasks 前缀
    // 去掉尾斜杠后前缀匹配，兼容 /m/tasks 和 /m/tasks/xxx
    const prefix = key.replace(/\/$/, '')
    return location.pathname === prefix || location.pathname.startsWith(prefix + '/')
  }

  return (
    <nav
      className="m-tabbar"
      style={{
        background: themeToken.colorBgContainer,
        borderTop: `1px solid ${themeToken.colorBorderSecondary}`,
      }}
    >
      {TABS.map((tab) => {
        const active = isActive(tab.key)
        return (
          <button
            key={tab.key}
            type="button"
            aria-current={active ? 'page' : undefined}
            className={`m-tab-item ${active ? 'active' : ''}`}
            onClick={() => navigate(tab.key)}
            style={{
              color: active ? themeToken.colorPrimary : themeToken.colorTextSecondary,
            }}
          >
            <span className="m-tab-icon">{tab.icon}</span>
            <span className="m-tab-label">{tab.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
