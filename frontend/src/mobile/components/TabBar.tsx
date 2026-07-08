import { useLocation, useNavigate } from 'react-router-dom'
import {
  DashboardOutlined,
  UnorderedListOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { theme } from 'antd'

// 底部 3 Tab 导航：仅保留已实现路由对应的 Tab
// 未实现的"客服"/"我的"页移除，避免点击被 catch-all 重定向回 /m 造成困惑
// key 必须带尾斜杠 /m/：父路由 <Route path="/m/*"> 的 splat 要求路径至少为 /m/，
// 用 /m（无尾斜杠）会不匹配 splat 导致渲染 null（白屏）
const TABS = [
  { key: '/m/', label: '仪表盘', icon: <DashboardOutlined /> },
  { key: '/m/tasks', label: '任务', icon: <UnorderedListOutlined /> },
  { key: '/m/orders', label: '抢单', icon: <ThunderboltOutlined /> },
]

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { token: themeToken } = theme.useToken()

  // 判断当前 Tab 是否激活：精确匹配或前缀匹配
  // /m 和 /m/ 都视为首页激活（Navigate 重定向 /m → /m/，但浏览器可能保持 /m）
  const isActive = (key: string) => {
    if (key === '/m/') return location.pathname === '/m' || location.pathname === '/m/'
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
              color: active ? '#E20613' : themeToken.colorTextSecondary,
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
