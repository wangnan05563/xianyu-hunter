import { Layout, Menu, theme, Breadcrumb, Spin, Badge, Drawer, Collapse, List, Tag, Modal, Input, Alert, Button } from 'antd'
import { TipButton } from '@/components/TipButton'
import {
  BellOutlined,
  FileTextOutlined,
  HomeOutlined,
  InfoCircleOutlined,
  SearchOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  WarningOutlined,
  ClockCircleOutlined,
  StarOutlined,
  MacCommandOutlined,
  SunOutlined,
  MoonOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { useMemo, useState, useEffect, useCallback, useRef } from 'react'
import type React from 'react'
import type { MenuProps } from 'antd'
import { authApi, statsApi } from '../../api'
import type { TodayAlert, AuthMe } from '../../api/types'
import { useTheme } from '../../contexts/ThemeContext'
import UserMenu from './UserMenu'
import DryRunBanner from './DryRunBanner'
import { SheetWorkspace } from '../SheetWorkspace'
import { useSheetStore } from '../../stores/sheetStore'
import { openSheetWithNotification } from '../SheetWorkspace/sheetNotifications'
import { useMenuConfig, buildCommandItems } from '../../hooks/useMenuConfig'
import type { CommandItem } from '../../hooks/useMenuConfig'
import { useOpenKeysOnDeepLink } from '../../hooks/useOpenKeysOnDeepLink'
import FirstScreenSkeleton from './FirstScreenSkeleton'
import { buildBreadcrumbs } from './breadcrumb'
import { G_PREFIX_MAP, G_PREFIX_HINT, shortcutHintForPath } from './shortcuts'
import AccountSwitcher from './AccountSwitcher'
import { GuideController } from '../../guides/GuideController'

const { Header, Sider, Content } = Layout


// Command Palette 导航项不再硬编码：由 /api/menu 派生（buildCommandItems），见 T02556 / FR-B-4

// g+X 快捷键表与键位提示：单独成模块（shortcuts.ts），便于命令面板渲染提示与单测

export default function MainLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  // 主题状态来自全局 Context（与顶层 ConfigProvider、Login 页面共享）
  const { isDark, toggle } = useTheme()

  // 认证状态：SPA 静态文件不需要认证，但 API 调用需要 xh_token cookie
  // 首次加载时调用 /api/auth/me 触发后端设置认证 cookie
  const [authChecked, setAuthChecked] = useState(false)
  const [loggedIn, setLoggedIn] = useState(false)
  // 用户信息：供状态栏头像/昵称展示（来自 /api/auth/me）
  const [userInfo, setUserInfo] = useState<AuthMe>({ logged_in: false })
  // 侧边栏收缩状态
  // 窄屏（<=768px）下默认收起 Sider，避免桌面端布局在 F12 设备模拟器下被压成竖条
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    // 用 globalThis.window 而非裸 window 触发 S7764；直接与 undefined 比较（S7741），
    // SSR 构建期 globalThis.window 为 undefined，浏览器运行期必定有值
    if (globalThis.window === undefined) return false
    return globalThis.window.innerWidth <= 768
  })

  // 调度器运行状态（30秒轮询）
  const [schedulerRunning, setSchedulerRunning] = useState<boolean | null>(null)
  // 通知抽屉与今日告警
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [todayAlert, setTodayAlert] = useState<TodayAlert | null>(null)
  // 告警拉取错误：抽屉要区分「加载中 / 失败可重试 / 真的没告警」，失败不再永远转圈（T02560 / 2.5-12）
  const [alertError, setAlertError] = useState<string | null>(null)
  const alertCount = todayAlert
    ? todayAlert.alerts.counts.failed + todayAlert.alerts.counts.timeout + todayAlert.alerts.counts.low_eval
    : 0
  // 用 ref 持有轮询定时器，避免组件卸载后仍触发 setState
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Command Palette 状态
  const [cmdOpen, setCmdOpen] = useState(false)
  const [cmdSearch, setCmdSearch] = useState('')
  const [cmdActive, setCmdActive] = useState(0)
  // g 前缀快捷键：记录是否处于 g 等待第二键的状态
  const gPrefixRef = useRef(false)
  const gTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 动态菜单：从后端 /api/menu 拉取用户级菜单配置（MU5）
  // 模块级缓存 5min TTL，切换账号时由 AccountSwitcher 调用 invalidateMenuCache 失效
  const { menus, menuItems: dynamicMenuItems, loading: menuLoading, error: menuError, refresh: refreshMenus } = useMenuConfig()

  // 轮询调度器状态
  const fetchSchedulerStatus = useCallback(() => {
    statsApi.overview().then((data) => setSchedulerRunning(data.scheduler_running)).catch(() => setSchedulerRunning(null))
  }, [])

  // 拉取今日告警：失败时记录错误文案，供抽屉渲染「加载失败 + 重试」
  const fetchTodayAlert = useCallback(() => {
    statsApi.today()
      .then((data) => {
        setTodayAlert(data)
        setAlertError(null)
      })
      .catch((err: unknown) => setAlertError(err instanceof Error ? err.message : String(err)))
  }, [])

  useEffect(() => {
    // 未登录时不启动轮询，避免 401 请求
    if (!loggedIn) return
    fetchSchedulerStatus()
    fetchTodayAlert()
    pollRef.current = setInterval(() => {
      fetchSchedulerStatus()
      fetchTodayAlert()
    }, 30_000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [fetchSchedulerStatus, fetchTodayAlert, loggedIn])

  // 拉取用户信息：挂载时拉取一次；已登录但 nick/local_username 为空时轮询重试
  // 为什么需要重试：auth_helper 抓取 nick 异步进行，首次请求可能拿到 nick="" + logged_in=true
  //                 前端不重试就会一直显示"未登录"或 user_id，体验差
  const fetchUserInfo = useCallback(() => {
    return authApi.getMe().then((data) => {
      setLoggedIn(data.logged_in === true)
      setUserInfo(data)
      return data
    }).catch(() => {
      setLoggedIn(false)
      return null
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchUserInfo().finally(() => {
      if (cancelled) return
      setAuthChecked(true)
      // 认证完成后恢复上次会话的 sheet 栈
      useSheetStore.getState().hydrate()
    })

    // 已登录但 nick 抓取未完成时轮询：每 15s 拉一次，最多 8 次（共 2 分钟）
    // 为什么用 setTimeout 链而非 setInterval：每次拉取后基于最新 data 判断是否还需重试，
    // 拿到 nick 立即停止，避免无谓请求
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let retryCount = 0
    const MAX_RETRIES = 8
    const RETRY_INTERVAL = 15_000

    // S2004 修复：原 .then 内联回调嵌在 setTimeout 内，叠加 useEffect→scheduleRetry→setTimeout→.then→if
    // 共 5 层嵌套超阈值。提取为命名函数后，.then 仅传函数引用，if 脱离 setTimeout 调用链
    // 闭包引用 scheduleRetry 安全：onRetryData 调用时 scheduleRetry 已定义（延迟执行）
    const onRetryData = (data: AuthMe | null) => {
      if (!data) return
      // 终止条件：未登录 / 已拿到 nick / 已拿到 local_username（非 user_id 兜底）
      const hasRealName = !!data.nick
        || (!!data.local_username && data.local_username !== data.user_id)
      if (!data.logged_in || hasRealName) return
      scheduleRetry()
    }

    const scheduleRetry = () => {
      if (cancelled || retryCount >= MAX_RETRIES) return
      retryTimer = setTimeout(() => {
        retryCount += 1
        fetchUserInfo().then(onRetryData)
      }, RETRY_INTERVAL)
    }
    scheduleRetry()

    return () => {
      cancelled = true
      if (retryTimer) clearTimeout(retryTimer)
    }
  }, [fetchUserInfo])

  // 全局快捷键监听：Ctrl+K 打开 Command Palette，g+X 导航
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // 输入框内不触发快捷键，避免干扰正常输入
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target as HTMLElement).isContentEditable) return

      // Ctrl+K：打开 Command Palette
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setCmdOpen(true)
        setCmdSearch('')
        setCmdActive(0)
        return
      }

      // Escape：关闭 Command Palette
      if (e.key === 'Escape' && cmdOpen) {
        e.preventDefault()
        setCmdOpen(false)
        return
      }

      // g 前缀序列：先按 g，500ms 内再按第二个键
      if (e.key === 'g' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        gPrefixRef.current = true
        // 超时自动重置 g 前缀状态
        if (gTimerRef.current) clearTimeout(gTimerRef.current)
        gTimerRef.current = setTimeout(() => { gPrefixRef.current = false }, 500)
        return
      }

      // 处于 g 等待态时，第二个键触发导航
      if (gPrefixRef.current && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const target = G_PREFIX_MAP[e.key]
        if (target) {
          e.preventDefault()
          openSheetWithNotification(target)
        }
        gPrefixRef.current = false
        if (gTimerRef.current) clearTimeout(gTimerRef.current)
      }
    }
    globalThis.addEventListener('keydown', handler)
    return () => globalThis.removeEventListener('keydown', handler)
  }, [navigate, cmdOpen])

  // Command Palette 模糊搜索过滤（移到 LayoutContent 内部，因为依赖 ConfigProvider 上下文）

  // 所有 hooks 必须在条件性 return 之前调用，否则 React hooks 数量不一致会触发 Error #310
  // 动态菜单的叶子节点 key 列表：用于 selectedKey 匹配（高亮当前路由对应的菜单项）
  const allLeafKeys = dynamicMenuItems.flatMap((item) => {
    if ('type' in item) return [] // divider 无 key
    if ('children' in item && Array.isArray(item.children)) {
      return item.children.map((c) => c.key)
    }
    return item.key && item.key !== '/' ? [item.key] : []
  })
  // 优先精确匹配，其次取最长前缀匹配（避免 /maintenance/db 误匹配到 /maintenance）
  const matchedKey =
    allLeafKeys.find((k) => k === location.pathname) ||
    allLeafKeys
      .filter((k) => location.pathname.startsWith(k + '/') || location.pathname === k)
      .sort((a, b) => b.length - a.length)[0]
  const selectedKey = matchedKey || '/'

  // 根据当前路由计算应该自动展开的 SubMenu 分组
  // 依赖 dynamicMenuItems：菜单加载后重新计算，确保首次渲染时 openKeys 能正确初始化
  const autoOpenKeys = useMemo(() => {
    const keys: string[] = []
    for (const item of dynamicMenuItems) {
      if ('type' in item) continue // divider
      if ('children' in item && Array.isArray(item.children) && item.key) {
        if (item.children.some((c) => location.pathname.startsWith(c.key))) {
          keys.push(item.key)
        }
      }
    }
    return keys
  }, [location.pathname, dynamicMenuItems])

  // 受控 openKeys：首屏按当前路由展开所属分组，用户手动开合后不再被路由联动
  // 为什么不用 useEffect 全程联动 autoOpenKeys：sheet 切换/快捷键导航都会触发 URL 变化→
  // autoOpenKeys 重算，若联动更新 openKeys 会展开新分组 SubMenu，产生遮挡内容的动画
  // 用户期望：侧边栏 SubMenu 状态独立于路由，仅在用户主动点击时变化
  const { openKeys, setOpenKeys: handleOpenKeysChange } = useOpenKeysOnDeepLink(
    autoOpenKeys,
    dynamicMenuItems.length > 0,
  )

  // 命令面板导航项：与侧栏同源（/api/menu），不再维护第二张硬编码表
  const commandItems = useMemo(() => buildCommandItems(menus), [menus])

  // 面包屑：计算在 breadcrumb.ts 里（纯函数，可脱离 Router/antd 单测），此处只做渲染
  const crumbs = useMemo(
    () => buildBreadcrumbs(location.pathname, menus),
    [location.pathname, menus],
  )
  const breadcrumbItems = useMemo(
    () => crumbs.map((c, idx) => ({
      title: c.href ? (
        <Link to={c.href}>{idx === 0 ? <><HomeOutlined /> {c.label}</> : c.label}</Link>
      ) : (
        <span className={c.current ? 'current' : undefined}>{c.label}</span>
      ),
    })),
    [crumbs],
  )

  // 窗口尺寸变化时同步 Sider 收缩状态：F12 切换设备模拟器实时生效
  useEffect(() => {
    if (globalThis.window === undefined) return
    const handler = () => {
      if (globalThis.window.innerWidth <= 768) setCollapsed(true)
    }
    globalThis.window.addEventListener('resize', handler)
    return () => globalThis.window.removeEventListener('resize', handler)
  }, [])

  // 未登录：自动跳转到登录页（保存当前路径，登录后跳转回来）
  useEffect(() => {
    if (authChecked && !loggedIn) {
      const currentPath = location.pathname + location.search
      navigate(`/login?redirect=${encodeURIComponent(currentPath)}`, { replace: true })
    }
  }, [authChecked, loggedIn, navigate, location.pathname, location.search])

  // 认证检查中：显示加载
  if (!authChecked) {
    return <FirstScreenSkeleton stage="auth" />
  }

  // 未登录：显示骨架屏（useEffect 会自动跳转到登录页）
  if (!loggedIn) {
    return <FirstScreenSkeleton stage="login" />
  }

  // 菜单加载中：等待菜单数据就绪后再渲染 LayoutContent
  // 为什么需要等待：openKeys 初始化依赖 autoOpenKeys，而 autoOpenKeys 依赖 menuItems
  // 如果菜单未加载就渲染，openKeys 会初始化为空，SubMenu 不会自动展开
  if (menuLoading && dynamicMenuItems.length === 0) {
    return <FirstScreenSkeleton stage="menu" />
  }

  return (
    <LayoutContent
      isDark={isDark}
      onToggleTheme={toggle}
      collapsed={collapsed}
      setCollapsed={setCollapsed}
      location={location}
      navigate={navigate}
      schedulerRunning={schedulerRunning}
      todayAlert={todayAlert}
      alertCount={alertCount}
      cmdOpen={cmdOpen}
      setCmdOpen={setCmdOpen}
      cmdSearch={cmdSearch}
      setCmdSearch={setCmdSearch}
      cmdActive={cmdActive}
      setCmdActive={setCmdActive}
      breadcrumbItems={breadcrumbItems}
      selectedKey={selectedKey}
      openKeys={openKeys}
      setOpenKeys={handleOpenKeysChange}
      menuItems={dynamicMenuItems}
      commandItems={commandItems}
      menuError={menuError}
      onRetryMenu={refreshMenus}
      alertError={alertError}
      onRetryAlert={fetchTodayAlert}
      drawerOpen={drawerOpen}
      setDrawerOpen={setDrawerOpen}
      userInfo={userInfo}
      onRefreshUserInfo={fetchUserInfo}
    />
  )
}

// 内部子组件：在 ConfigProvider 内部消费 themeToken，确保暗色主题正确应用
interface LayoutContentProps {
  readonly isDark: boolean
  readonly onToggleTheme: () => void
  readonly collapsed: boolean
  readonly setCollapsed: React.Dispatch<React.SetStateAction<boolean>>
  readonly location: ReturnType<typeof useLocation>
  readonly navigate: ReturnType<typeof useNavigate>
  readonly schedulerRunning: boolean | null
  readonly todayAlert: TodayAlert | null
  readonly alertCount: number
  readonly cmdOpen: boolean
  readonly setCmdOpen: React.Dispatch<React.SetStateAction<boolean>>
  readonly cmdSearch: string
  readonly setCmdSearch: React.Dispatch<React.SetStateAction<string>>
  readonly cmdActive: number
  readonly setCmdActive: React.Dispatch<React.SetStateAction<number>>
  readonly breadcrumbItems: { title: React.ReactNode }[]
  readonly selectedKey: string
  readonly openKeys: string[]
  // 只接受「用户手动开合」的字符串数组入口：内部据此标记 touched，路由联动不再覆盖
  readonly setOpenKeys: (keys: string[]) => void
  readonly menuItems: NonNullable<MenuProps['items']>
  // 命令面板项：由 MainLayout 用 buildCommandItems(menus) 派生后传入（T02556 单源）
  readonly commandItems: CommandItem[]
  // 菜单与告警的失败态（T02560）：error 不再被丢弃，侧栏/抽屉内联展示并提供重试
  readonly menuError: Error | null
  readonly onRetryMenu: () => void
  readonly alertError: string | null
  readonly onRetryAlert: () => void
  readonly drawerOpen: boolean
  readonly setDrawerOpen: React.Dispatch<React.SetStateAction<boolean>>
  readonly userInfo: AuthMe
  // 刷新用户信息回调：从 MainLayout 传入，UserMenu 调用时触发后端 nick 重抓
  readonly onRefreshUserInfo?: () => Promise<AuthMe | null>
}

function LayoutContent({
  isDark, onToggleTheme, collapsed, setCollapsed, location, navigate,
  schedulerRunning, todayAlert, alertCount,
  cmdOpen, setCmdOpen, cmdSearch, setCmdSearch, cmdActive, setCmdActive,
  breadcrumbItems, selectedKey, openKeys, setOpenKeys, menuItems, commandItems,
  menuError, onRetryMenu, alertError, onRetryAlert,
  drawerOpen, setDrawerOpen, userInfo, onRefreshUserInfo,
}: LayoutContentProps) {
  // 必须在 ConfigProvider 内部调用，token 才会响应暗色算法
  const { token: themeToken } = theme.useToken()

  // Command Palette 模糊搜索过滤（数据源为 /api/menu 派生的 commandItems）
  const filteredCommands = useMemo(() => {
    if (!cmdSearch.trim()) return commandItems
    const kw = cmdSearch.toLowerCase()
    return commandItems.filter((item) => item.label.toLowerCase().includes(kw))
  }, [cmdSearch, commandItems])

  // 告警抽屉的三个空态文案同构，抽成函数避免同一段 JSX 重复（并消掉 `: <JSX>,` 形态）
  const emptyHint = (text: string) => <div style={{ color: themeToken.colorTextSecondary }}>{text}</div>

  // 路由切换时重置外层 Content 的滚动位置到顶部
  // 修复：默认情况下外层 Content 的 scrollTop 不会随路由变化重置，
  // 从其他页面跳转过来时新页面会显示在错误的滚动位置（如 /chatbot 顶部被截断）。
  // 用 rAF 确保在 Outlet 渲染完成、DOM 高度更新后再重置，避免时序问题。
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      const el = document.getElementById('main-content')
      if (el) el.scrollTo({ top: 0, behavior: 'auto' })
    })
    return () => cancelAnimationFrame(id)
  }, [location.pathname])

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        collapsedWidth={64}
        // 不设 breakpoint：避免窗口缩放触发 antd 自动折叠后，
        // 折叠态下 SubMenu 的 Popover 浮层溢出到 Content 区域上方。
        // 折叠状态完全由 Header 按钮显式控制。
        trigger={null}
        theme={isDark ? 'dark' : 'light'}
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
          <div className="brand-logo" style={{ fontSize: collapsed ? 24 : undefined }}>闲</div>
          {!collapsed && (
            <div className="brand-text">
              <span className="brand-name">闲鱼猎人</span>
              <span className="brand-tagline">智能监控 · 自动抢单</span>
            </div>
          )}
        </div>
        {/* 菜单加载失败：内联提示 + 重试，不再静默空白（T02560 / 2.5-10） */}
        {menuError !== null && menuItems.length === 0 && (
          <Alert
            type="error"
            showIcon
            style={{ margin: '8px 12px' }}
            message="菜单加载失败"
            description={
              <Button size="small" type="link" onClick={onRetryMenu} style={{ padding: 0 }}>
                重试
              </Button>
            }
          />
        )}
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          openKeys={openKeys}
          onOpenChange={setOpenKeys}
          items={menuItems}
          onClick={({ key }) => {
            // SubMenu 父项的 key 是 'sub-data'/'sub-config'/'sub-maintenance'，
            // 不以 / 开头，antd 在某些版本仍会触发 onClick。
            // 这里只对路径型 key 调 navigate，避免点击 SubMenu 标题时跳到非法 URL。
            if (typeof key === 'string' && key.startsWith('/')) {
              // 走 openSheet：sheet 栈管理 + URL 同步（store 内部 navigate）
              // 用带通知的包装函数：循环替换触发时发 Toast + 撤销按钮
              openSheetWithNotification(key)
            }
          }}
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
            <TipButton
              tip="展开或收起侧边栏"
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ fontSize: 16, width: 40, height: 40 }}
            />
            <Breadcrumb items={breadcrumbItems} className="app-breadcrumb" />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* Command Palette 触发按钮 */}
            <TipButton
              tip="打开命令面板（Ctrl+K）"
              type="text"
              shape="circle"
              size="small"
              icon={<MacCommandOutlined />}
              style={{ fontSize: 16, width: 28, height: 28 }}
              onClick={() => { setCmdOpen(true); setCmdSearch(''); setCmdActive(0) }}
            />
            {/* 调度器状态指示灯：绿色=运行中，红色=已停止 */}
            <TipButton
              tip={schedulerRunning === null ? '加载中…' : schedulerRunning ? '调度器运行中' : '调度器已停止'}
              type="text"
              shape="circle"
              size="small"
              style={{ width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              onClick={() => openSheetWithNotification('/')}
            >
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: (() => {
                    if (schedulerRunning === null) return '#d9d9d9'
                    if (schedulerRunning) return '#52c41a'
                    return '#ff4d4f'
                  })(),
                  display: 'inline-block',
                }}
              />
            </TipButton>

            {/* 通知铃铛：Badge 显示今日告警总数 */}
            <Badge count={alertCount} size="small" offset={[-2, 2]}>
              <TipButton
                tip="打开今日告警通知"
                type="text"
                shape="circle"
                size="small"
                icon={<BellOutlined />}
                style={{ fontSize: 16, width: 28, height: 28 }}
                onClick={() => setDrawerOpen(true)}
              />
            </Badge>

            {/* 主题切换按钮 */}
            <TipButton
              tip={isDark ? '切换为亮色主题' : '切换为暗色主题'}
              type="text"
              icon={isDark ? <SunOutlined /> : <MoonOutlined />}
              size="small"
              style={{ fontSize: 16, width: 28, height: 28 }}
              onClick={onToggleTheme}
            />

            {/* 帮助文档入口：在 SheetWorkspace 内打开 /help sheet，与其他菜单一致 */}
            <TipButton
              tip="打开帮助文档"
              type="text"
              shape="circle"
              size="small"
              icon={<QuestionCircleOutlined />}
              style={{ fontSize: 16, width: 28, height: 28 }}
              onClick={() => openSheetWithNotification('/help')}
            />

            {/* 关于入口：在 SheetWorkspace 内打开 /about sheet，展示版本/许可/文档资源 */}
            <TipButton
              tip="查看关于与版本信息"
              type="text"
              shape="circle"
              size="small"
              icon={<InfoCircleOutlined />}
              style={{ fontSize: 16, width: 28, height: 28 }}
              onClick={() => openSheetWithNotification('/about')}
            />

            {/* 账号切换器：多账号管理入口（MU7），切换后整页刷新确保数据隔离 */}
            <AccountSwitcher currentUserId={userInfo.user_id} />

            {/* 用户菜单：头像 + 昵称，悬浮显示 Cookie 健康面板（含换号/退出） */}
            <UserMenu userInfo={userInfo} onRefreshUserInfo={onRefreshUserInfo} />
          </div>
        </Header>
        <Content id="main-content" style={{ overflow: 'hidden', background: themeToken.colorBgLayout }}>
          {/* 全局「演练中」横幅（FR-C3-1）：存在 dry_run 运行任务时常驻提示，防误认为真实抢单 */}
          <DryRunBanner />
          {/* SheetWorkspace 接管内容区：sheet 标签栏 + 单激活 sheet 内容
              内部已含 ErrorBoundary + Suspense + 懒加载，无需外层包裹 */}
          <SheetWorkspace />
        </Content>
      </Layout>

      {/* 通知抽屉：展示今日告警分类列表 */}
      <Drawer
        title="今日告警"
        placement="right"
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        width={420}
        styles={{ body: { paddingTop: 12 } }}
      >
        {todayAlert ? (
          <>
            <Collapse
              defaultActiveKey={['failed', 'timeout', 'low_eval']}
              ghost
              items={[
                {
                  key: 'failed',
                  label: (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <WarningOutlined style={{ color: '#ff4d4f' }} />
                      失败订单
                      <Tag color="red">{todayAlert.alerts.counts.failed}</Tag>
                    </span>
                  ),
                  children: todayAlert.alerts.failed_orders.length > 0 ? (
                    <List
                      size="small"
                      dataSource={todayAlert.alerts.failed_orders}
                      renderItem={(o) => (
                        <List.Item>
                          <List.Item.Meta
                            title={<span>#{o.id} {o.title}</span>}
                            description={`¥${o.amount} · ${o.created_at}`}
                          />
                        </List.Item>
                      )}
                    />
                  ) : emptyHint('暂无失败订单'),
                },
                {
                  key: 'timeout',
                  label: (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <ClockCircleOutlined style={{ color: '#faad14' }} />
                      待支付超时
                      <Tag color="orange">{todayAlert.alerts.counts.timeout}</Tag>
                    </span>
                  ),
                  children: todayAlert.alerts.timeout_pending.length > 0 ? (
                    <List
                      size="small"
                      dataSource={todayAlert.alerts.timeout_pending}
                      renderItem={(o) => (
                        <List.Item>
                          <List.Item.Meta
                            title={<span>#{o.id} {o.title}</span>}
                            description={`¥${o.amount} · 超时 ${o.age_sec}s`}
                          />
                        </List.Item>
                      )}
                    />
                  ) : emptyHint('暂无超时订单'),
                },
                {
                  key: 'low_eval',
                  label: (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <StarOutlined style={{ color: '#722ed1' }} />
                      低分评估
                      <Tag color="purple">{todayAlert.alerts.counts.low_eval}</Tag>
                    </span>
                  ),
                  children: todayAlert.alerts.low_evaluations.length > 0 ? (
                    <List
                      size="small"
                      dataSource={todayAlert.alerts.low_evaluations}
                      renderItem={(e) => (
                        <List.Item>
                          <List.Item.Meta
                            title={<span>{e.message}</span>}
                            description={<span><Tag>{e.type}</Tag> 评分 {e.score} · {e.created_at}</span>}
                          />
                        </List.Item>
                      )}
                    />
                  ) : emptyHint('暂无低分评估'),
                },
              ]}
            />
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <Link to="/orders" onClick={() => setDrawerOpen(false)}>查看全部 →</Link>
            </div>
          </>
        ) : alertError !== null ? (
          // 拉取失败：给出错误态与重试，不再永远转圈（T02560 / 2.5-12）
          <Alert
            type="error"
            showIcon
            message="今日告警加载失败"
            description={alertError}
            action={<Button size="small" onClick={onRetryAlert}>重试</Button>}
          />
        ) : (
          <Spin />
        )}
      </Drawer>

      {/* Command Palette：Ctrl+K 打开，模糊搜索导航命令 */}
      <Modal
        open={cmdOpen}
        onCancel={() => setCmdOpen(false)}
        footer={null}
        closable={false}
        centered
        width={520}
        styles={{ body: { padding: 0 } }}
      >
        <div style={{ padding: '12px 16px 0' }}>
          <Input
            placeholder="搜索命令…"
            value={cmdSearch}
            onChange={(e) => { setCmdSearch(e.target.value); setCmdActive(0) }}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setCmdActive((prev) => Math.min(prev + 1, Math.max(0, filteredCommands.length - 1)))
              } else if (e.key === 'ArrowUp') {
                e.preventDefault()
                setCmdActive((prev) => Math.max(prev - 1, 0))
              } else if (e.key === 'Enter' && filteredCommands[cmdActive]) {
                openSheetWithNotification(filteredCommands[cmdActive].key)
                setCmdOpen(false)
              } else if (e.key === 'Escape') {
                setCmdOpen(false)
              }
            }}
            prefix={<SearchOutlined style={{ color: themeToken.colorTextQuaternary }} />}
            allowClear
            onClear={() => { setCmdSearch(''); setCmdActive(0) }}
          />
        </div>
        <div style={{ maxHeight: 320, overflowY: 'auto', padding: '8px 0' }}>
          {filteredCommands.length === 0 ? (
            <div style={{ textAlign: 'center', color: themeToken.colorTextSecondary, padding: 24 }}>无匹配命令</div>
          ) : (
            filteredCommands.map((item, idx) => {
              // N4：面板每行右侧展示 g+X 键位，快捷键从「只有帮助文档里才知道」变成使用时可见
              const hint = shortcutHintForPath(item.key)
              return (
              <button
                type="button"
                key={item.key}
                onClick={() => { openSheetWithNotification(item.key); setCmdOpen(false) }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 16px',
                  cursor: 'pointer',
                  background: idx === cmdActive ? themeToken.colorPrimaryBg : undefined,
                  borderRadius: 4,
                  margin: '0 8px',
                  border: 'none',
                  width: '100%',
                  textAlign: 'left',
                  font: 'inherit',
                }}
                onMouseEnter={() => setCmdActive(idx)}
              >
                <span style={{ fontSize: 16, color: themeToken.colorTextSecondary }}>{item.icon}</span>
                <span>{item.label}</span>
                <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                  {hint && (
                    <span style={{ fontSize: 12, fontFamily: 'monospace', color: themeToken.colorTextSecondary }}>
                      {hint}
                    </span>
                  )}
                  <span style={{ fontSize: 12, color: themeToken.colorTextQuaternary }}>{item.key}</span>
                </span>
              </button>
              )
            })
          )}
        </div>
        <div
          style={{
            borderTop: `1px solid ${themeToken.colorBorderSecondary}`,
            padding: '8px 16px',
            fontSize: 12,
            color: themeToken.colorTextSecondary,
          }}
        >
          {G_PREFIX_HINT}
        </div>
      </Modal>

      {/* 全站引导向导：常驻悬浮按钮 + 首访自动触发 */}
      <GuideController />
    </Layout>
  )
}
