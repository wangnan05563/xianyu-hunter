import { Layout, Menu, theme, Breadcrumb, Spin, Result, Button } from 'antd'
import {
  DashboardOutlined,
  UnorderedListOutlined,
  ShoppingOutlined,
  ThunderboltOutlined,
  AuditOutlined,
  FieldTimeOutlined,
  FileTextOutlined,
  DollarOutlined,
  SafetyCertificateOutlined,
  BellOutlined,
  HistoryOutlined,
  HomeOutlined,
  ToolOutlined,
  RobotOutlined,
  SearchOutlined,
  AimOutlined,
  LoginOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  AppstoreOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate, Link } from 'react-router-dom'
import { useMemo, useState, useEffect } from 'react'
import { authApi } from '../../api'

const { Header, Sider, Content } = Layout

// 菜单配置：一级分组使用 SubMenu 支持折叠展开
const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { type: 'divider' as const },
  {
    key: 'sub-data',
    icon: <AppstoreOutlined />,
    label: '数据查看',
    children: [
      { key: '/tasks', icon: <UnorderedListOutlined />, label: '任务管理' },
      { key: '/items', icon: <ShoppingOutlined />, label: '商品列表' },
      { key: '/orders', icon: <ThunderboltOutlined />, label: '抢单记录' },
      { key: '/evaluations', icon: <AuditOutlined />, label: '评估明细' },
      { key: '/timeline', icon: <FieldTimeOutlined />, label: '事件时间线' },
      { key: '/logs', icon: <FileTextOutlined />, label: '实时日志' },
    ],
  },
  { type: 'divider' as const },
  {
    key: 'sub-config',
    icon: <SettingOutlined />,
    label: '配置管理',
    children: [
      { key: '/config/price', icon: <DollarOutlined />, label: '价格策略' },
      { key: '/config/eval', icon: <SafetyCertificateOutlined />, label: '评估规则' },
      { key: '/config/buyer', icon: <AimOutlined />, label: '抢单策略' },
      { key: '/config/search', icon: <SearchOutlined />, label: '搜索参数' },
      { key: '/config/notifier', icon: <BellOutlined />, label: '通知渠道' },
      { key: '/config/ai', icon: <RobotOutlined />, label: 'AI 服务' },
      { key: '/config/version', icon: <HistoryOutlined />, label: '配置版本' },
    ],
  },
  { type: 'divider' as const },
  { key: '/maintenance', icon: <ToolOutlined />, label: '系统维护' },
]

// 路由 → 面包屑映射
const ROUTE_LABELS: Record<string, string> = {
  '/': '仪表盘',
  '/tasks': '任务管理',
  '/tasks/new': '新建任务',
  '/items': '商品列表',
  '/orders': '抢单记录',
  '/evaluations': '评估明细',
  '/timeline': '事件时间线',
  '/logs': '实时日志',
  '/config/price': '价格策略',
  '/config/eval': '评估规则',
  '/config/buyer': '抢单策略',
  '/config/search': '搜索参数',
  '/config/notifier': '通知渠道',
  '/config/ai': 'AI 服务',
  '/config/version': '配置版本',
  '/maintenance': '系统维护',
}

export default function MainLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { token: themeToken } = theme.useToken()

  // 认证状态：SPA 静态文件不需要认证，但 API 调用需要 xh_token cookie
  // 首次加载时调用 /api/auth/me 触发后端设置认证 cookie
  const [authChecked, setAuthChecked] = useState(false)
  const [loggedIn, setLoggedIn] = useState(false)
  // 侧边栏收缩状态
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    authApi.getMe().then((data) => {
      setLoggedIn(data.logged_in === true)
    }).catch(() => setLoggedIn(false))
      .finally(() => setAuthChecked(true))
  }, [])

  // 所有 hooks 必须在条件性 return 之前调用，否则 React hooks 数量不一致会触发 Error #310
  const allLeafKeys = menuItems.flatMap((item) => {
    if ('children' in item && Array.isArray(item.children)) {
      return item.children.map((c) => c.key)
    }
    return item.key && item.key !== '/' ? [item.key] : []
  })
  const matchedKey = allLeafKeys.find((k) => location.pathname.startsWith(k))
  const selectedKey = matchedKey || (location.pathname === '/' ? '/' : '/')

  // 根据当前路由自动展开对应的 SubMenu 分组
  const defaultOpenKeys = useMemo(() => {
    const keys: string[] = []
    for (const item of menuItems) {
      if ('children' in item && Array.isArray(item.children) && item.key) {
        if (item.children.some((c) => location.pathname.startsWith(c.key))) {
          keys.push(item.key)
        }
      }
    }
    return keys
  }, [location.pathname])

  const breadcrumbItems = useMemo(() => {
    const items = [{ title: <Link to="/"><HomeOutlined /> 首页</Link> }]
    const path = location.pathname
    if (path !== '/') {
      const label = ROUTE_LABELS[path]
        || ROUTE_LABELS[Object.keys(ROUTE_LABELS).find((k) => k !== '/' && path.startsWith(k)) || '']
      if (label) {
        items.push({ title: <span className="current">{label}</span> })
      }
    }
    return items
  }, [location.pathname])

  // 认证检查中：显示加载
  if (!authChecked) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="正在验证登录状态..." />
      </div>
    )
  }

  // 未登录：引导到新版登录页
  if (!loggedIn) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Result
          icon={<LoginOutlined style={{ color: '#FF6200' }} />}
          title="需要登录"
          subTitle="请先完成闲鱼账号认证，即可使用全部功能"
          extra={[
            <Button type="primary" key="login" onClick={() => navigate('/login')} style={{ background: '#FF6200' }}>
              前往登录
            </Button>,
            <Button key="retry" onClick={() => setAuthChecked(false)}>
              重试
            </Button>,
          ]}
        />
      </div>
    )
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        collapsedWidth={64}
        breakpoint="lg"
        trigger={null}
        style={{
          background: themeToken.colorBgContainer,
          boxShadow: '2px 0 8px rgba(0, 0, 0, 0.04)',
          position: 'sticky',
          top: 0,
          height: '100vh',
          overflow: 'auto',
        }}
      >
        {/* 品牌区：收缩时只显示 logo 圆标 */}
        <div className="brand-area" style={{ justifyContent: collapsed ? 'center' : undefined, padding: collapsed ? '16px 0' : undefined }}>
          <div className="brand-logo" style={{ fontSize: collapsed ? 24 : undefined }}>{collapsed ? '闲' : '闲'}</div>
          {!collapsed && (
            <div className="brand-text">
              <span className="brand-name">闲鱼猎人</span>
              <span className="brand-tagline">智能监控 · 自动抢单</span>
            </div>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          defaultOpenKeys={defaultOpenKeys}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          inlineCollapsed={collapsed}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: themeToken.colorBgContainer,
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0, 0, 0, 0.04)',
            position: 'sticky',
            top: 0,
            zIndex: 10,
            height: 56,
            lineHeight: '56px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* 侧边栏收缩/展开按钮 */}
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ fontSize: 16, width: 40, height: 40 }}
            />
            <Breadcrumb items={breadcrumbItems} className="app-breadcrumb" />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Button
              type="text"
              size="small"
              icon={<LoginOutlined />}
              onClick={() => navigate('/login')}
              style={{ fontSize: 12, color: themeToken.colorTextSecondary }}
            >
              登录管理
            </Button>
            <a
              href="/"
              style={{ fontSize: 12, color: themeToken.colorTextSecondary }}
              title="返回旧版控制台"
            >
              ← 返回旧版
            </a>
          </div>
        </Header>
        <Content style={{ overflow: 'auto', background: '#f5f7fa' }}>
          <div className="fade-in-up" key={location.pathname}>
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}
