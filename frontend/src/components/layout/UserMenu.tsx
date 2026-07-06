import { useState, useCallback, useEffect } from 'react'
import { Avatar, Typography, Tag, Spin, Button, Tooltip, theme, Empty, message, Popover } from 'antd'
import {
  SwapOutlined,
  LogoutOutlined,
  CheckCircleFilled,
  ExclamationCircleFilled,
  ClockCircleOutlined,
  SafetyCertificateOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { authApi } from '../../api'
import type { CookieHealthReport } from '../../api/auth'
import type { AuthMe } from '../../api/types'
import { useSheetStore } from '../../stores/sheetStore'
import { storage } from '../../utils/storage'

const { Text } = Typography

interface UserMenuProps {
  readonly userInfo: AuthMe
  // 刷新用户信息回调：父组件 MainLayout 提供，触发后端 nick 重抓 + 重新拉取 /me
  // 为什么需要：UserMenu 内部的"刷新"按钮原本只刷新 cookie health，
  // 现在同时触发 nick 重抓并更新顶部 displayName
  readonly onRefreshUserInfo?: () => Promise<AuthMe | null>
}

// 默认头像：闲鱼官方品牌色（橙）+ 闲字，作为无 avatar_url 时的兜底
// 为什么不使用第三方占位图：用户要求"官方提供的标准图片资源"，
// 后端 /api/auth/me 返回的 avatar_url 即闲鱼官方头像，无值时用品牌色兜底
const DEFAULT_AVATAR_BG = 'linear-gradient(135deg, #FF6200, #FF8C00)'

// 计算顶部显示名：local_username > nick > '未登录'
// 为什么提取：原代码内联嵌套三元，认知复杂度高；优先级规则集中一处便于维护
const computeDisplayName = (info: AuthMe): string => {
  // local_username 后端已合并 custom_alias > nickname > user_id，等值 user_id 时降级
  if (info.local_username && info.local_username !== info.user_id) return info.local_username
  if (info.nick && info.nick !== info.user_id) return info.nick
  return '未登录'
}

// S3776 修复：renderHealthDetail 原 CC=17，拆分为多个小组件 + 查表映射降低复杂度
// 每个子组件职责单一，主函数只剩组合逻辑

// 健康状态图标映射：is_valid → 图标组件
const HEALTH_STATUS_ICONS = {
  valid: CheckCircleFilled,
  invalid: ExclamationCircleFilled,
} as const

// 层级状态配置：label + 对应 health.layers 的 key
const LAYER_CONFIGS: ReadonlyArray<{
  readonly label: string
  readonly key: keyof CookieHealthReport['layers']
}> = [
  { label: '身份层', key: 'identity' },
  { label: '会话层', key: 'session' },
  { label: '追踪层', key: 'tracking' },
]

// 安全标记配置：label + 对应 health.security_flags 的 key + active 颜色
const SECURITY_FLAG_CONFIGS: ReadonlyArray<{
  readonly label: string
  readonly key: keyof CookieHealthReport['security_flags']
  readonly activeColor: string
}> = [
  { label: 'Secure', key: 'has_secure', activeColor: 'green' },
  { label: 'HttpOnly', key: 'has_httponly', activeColor: 'green' },
  { label: '会话级', key: 'is_session_cookie', activeColor: 'blue' },
]

// 健康状态头部：图标 + 文案 + 完整性标签
function HealthStatusHeader({
  health,
  themeToken,
}: {
  readonly health: CookieHealthReport
  readonly themeToken: ReturnType<typeof theme.useToken>['token']
}) {
  const StatusIcon = health.is_valid ? HEALTH_STATUS_ICONS.valid : HEALTH_STATUS_ICONS.invalid
  const iconColor = health.is_valid ? themeToken.colorSuccess : themeToken.colorError
  const statusText = health.is_valid ? 'Cookie 状态正常' : 'Cookie 异常'
  const tagColor = health.is_valid ? 'success' : 'error'
  const integrityText = health.integrity === 'complete' ? '完整' : '不完整'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
      <StatusIcon style={{ color: iconColor, fontSize: 16 }} />
      <Text strong style={{ fontSize: 13 }}>
        {statusText}
      </Text>
      <Tag color={tagColor} style={{ marginLeft: 'auto', fontSize: 11 }}>
        {integrityText}
      </Tag>
    </div>
  )
}

// 异常原因提示：仅在 is_valid=false 且有原因时显示
function IntegrityReasonHint({
  reason,
  themeToken,
}: {
  readonly reason?: string
  readonly themeToken: ReturnType<typeof theme.useToken>['token']
}) {
  if (!reason) return null
  return (
    <div style={{
      fontSize: 11, color: themeToken.colorTextSecondary,
      marginBottom: 10, padding: '6px 8px',
      background: themeToken.colorFillQuaternary,
      borderRadius: 4,
    }}>
      原因：{reason}
    </div>
  )
}

// Cookie 层级列表：遍历 LAYER_CONFIGS 渲染，避免重复 JSX
function HealthLayersList({
  health,
  themeToken,
}: {
  readonly health: CookieHealthReport
  readonly themeToken: ReturnType<typeof theme.useToken>['token']
}) {
  return (
    <>
      {LAYER_CONFIGS.map(({ label, key }) => {
        const isReady = health.layers[key]
        return (
          <DetailRow
            key={key}
            label={label}
            value={isReady ? '✓ 已就绪' : '✗ 缺失'}
            valueColor={isReady ? themeToken.colorSuccess : themeToken.colorError}
          />
        )
      })}
    </>
  )
}

// 安全标记组：遍历 SECURITY_FLAG_CONFIGS 渲染
function SecurityFlags({
  flags,
  themeToken,
}: {
  readonly flags: CookieHealthReport['security_flags']
  readonly themeToken: ReturnType<typeof theme.useToken>['token']
}) {
  return (
    <div style={{
      display: 'flex', gap: 6, flexWrap: 'wrap',
      marginTop: 4, paddingTop: 8, borderTop: `1px dashed ${themeToken.colorBorderSecondary}`,
    }}>
      {SECURITY_FLAG_CONFIGS.map(({ label, key, activeColor }) => {
        const active = flags[key]
        const text = key === 'is_session_cookie'
          ? (active ? label : '持久化')
          : (active ? `✓ ${label}` : `✗ ${label}`)
        return (
          <Tag
            key={key}
            color={active ? activeColor : 'default'}
            style={{ fontSize: 10, margin: 0 }}
          >
            {text}
          </Tag>
        )
      })}
    </div>
  )
}

// 健康详情主渲染函数：组合各子组件，主逻辑只剩拼装
// 复杂度降低原因：条件判断分散到各子组件，主函数无分支嵌套
const renderHealthDetail = (health: CookieHealthReport | null, themeToken: ReturnType<typeof theme.useToken>['token']) => {
  if (!health) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="无法获取 Cookie 状态"
        style={{ padding: '16px 0' }}
      />
    )
  }
  return (
    <>
      <HealthStatusHeader health={health} themeToken={themeToken} />
      <IntegrityReasonHint reason={!health.is_valid ? health.integrity_reason : undefined} themeToken={themeToken} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
        <DetailRow
          icon={<ClockCircleOutlined style={{ color: themeToken.colorPrimary }} />}
          label="有效期"
          value={health.expiry_human}
        />
        <DetailRow
          icon={<SafetyCertificateOutlined style={{ color: themeToken.colorPrimary }} />}
          label="Cookie 数"
          value={`${health.cookie_count} 个`}
        />
        <HealthLayersList health={health} themeToken={themeToken} />
        <SecurityFlags flags={health.security_flags} themeToken={themeToken} />
      </div>
    </>
  )
}

export default function UserMenu({ userInfo, onRefreshUserInfo }: UserMenuProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { token: themeToken } = theme.useToken()

  const [open, setOpen] = useState(false)
  const [health, setHealth] = useState<CookieHealthReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  // 用户信息刷新中状态：与 health 的 loading 分开管理，避免互相干扰
  const [refreshingUser, setRefreshingUser] = useState(false)

  // 健康检查 + 用户信息刷新：调用方决定是否同时刷新 userInfo
  // 为什么合并到一个函数：Popover 打开时只需 health（轻量，<300ms）；
  // 用户点"刷新"按钮时需要同时触发后端 nick 重抓并更新顶部 displayName
  const fetchHealth = useCallback(async (opts?: { withUserInfo?: boolean }) => {
    setLoading(true)
    if (opts?.withUserInfo) setRefreshingUser(true)
    try {
      // withUserInfo 时先触发后端 nick 重抓（异步），等 1.5s 再拉 /me 取最新结果
      // 为什么等 1.5s：auth_helper 子进程拉 nick 平均 1-2s，同步等待会卡 UI，
      // 用 setTimeout 让用户先看到 loading 状态，1.5s 后大概率能拿到最新 nick
      if (opts?.withUserInfo) {
        try { await authApi.refreshMe() } catch { /* ignore */ }
        await new Promise(resolve => setTimeout(resolve, 1500))
      }
      const tasks: [Promise<CookieHealthReport | null>, Promise<AuthMe | null>] = [
        authApi.checkCookieHealth().catch(() => null),
        opts?.withUserInfo && onRefreshUserInfo ? onRefreshUserInfo() : Promise.resolve(null),
      ]
      // userData 由父组件通过 props 更新，这里无需 setState，故不解构第二个返回值
      // S3735 修复：原 `void userData` 用 void 操作符抑制未使用警告，删除 void 改为不解构
      const [healthData] = await Promise.all(tasks)
      if (healthData) setHealth(healthData)
    } catch {
      setHealth(null)
    } finally {
      setLoading(false)
      setRefreshingUser(false)
    }
  }, [onRefreshUserInfo])

  // Popover 打开时触发健康检查（不刷新 userInfo，避免每次悬浮都触发 1.5s 延迟）
  const handleOpenChange = useCallback((visible: boolean) => {
    setOpen(visible)
    if (visible) {
      // S3735 修复：删除 void 操作符，fetchHealth 内部已 try/catch，.catch 兜底防 floating promise
      fetchHealth().catch(() => undefined)
    }
  }, [fetchHealth])

  // 换号：跳转到登录页（保留当前路径用于登录后跳回）
  // 为什么用 useLocation 而非 window.location：保持 SPA 路由一致性，
  // 避免在 BrowserRouter/HashRouter 切换时取到错误的路径格式
  const handleSwitchAccount = () => {
    setOpen(false)
    const currentPath = location.pathname + location.search
    navigate(`/login?redirect=${encodeURIComponent(currentPath)}`)
  }

  // 退出：调用 logout API，清除本地 token，跳转登录页
  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      await authApi.logout()
      localStorage.removeItem('xh_token')
      // 清空 sheet 栈与持久化状态，避免下一用户看到上一用户的 sheet
      useSheetStore.getState().closeAll()
      storage.remove('xh.sheets.state')
      message.success('已退出登录')
      setOpen(false)
      // replace 避免后退回到已退出登录的页面
      setTimeout(() => navigate('/login', { replace: true }), 300)
    } catch {
      message.error('退出失败，请重试')
    } finally {
      setLoggingOut(false)
    }
  }

  // 头像图片加载失败时回退到品牌色 + 昵称首字
  const [avatarError, setAvatarError] = useState(false)
  useEffect(() => {
    // avatar_url 变化时重置错误状态，允许重新加载
    setAvatarError(false)
  }, [userInfo.avatar_url])

  // 显示名优先级：local_username（custom_alias > nickname > user_id，后端算好）> nick > user_id > '未登录'
  // 提取为模块级 computeDisplayName，避免嵌套三元（S3358）
  const displayName = computeDisplayName(userInfo)
  const avatarUrl = userInfo.avatar_url && !avatarError ? userInfo.avatar_url : undefined
  const avatarContent = avatarUrl
    ? <Avatar size={32} src={avatarUrl} onError={() => { setAvatarError(true); return false }} />
    : (
      <Avatar
        size={32}
        style={{ background: DEFAULT_AVATAR_BG, fontSize: 14, fontWeight: 600 }}
      >
        {displayName.charAt(0)}
      </Avatar>
    )

  // 健康状态面板内容：详情渲染提取为模块级 renderHealthDetail，主组件只剩 loading 三元
  const healthDetailContent = renderHealthDetail(health, themeToken)
  const healthContent = loading ? (
    <div style={{ textAlign: 'center', padding: '24px 0' }}>
      <Spin size="small" />
      <div style={{ marginTop: 8, fontSize: 12, color: themeToken.colorTextSecondary }}>
        正在检查 Cookie 状态...
      </div>
    </div>
  ) : healthDetailContent

  // 悬浮面板内容
  const content = (
    <div style={{ width: 300, padding: '4px 0' }}>
      {/* 用户信息头部 */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 4px 12px', borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
        marginBottom: 12,
      }}>
        {avatarContent}
        <div style={{ flex: 1, minWidth: 0 }}>
          <Text strong style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {displayName}
          </Text>
          {/* 闲鱼昵称行：仅当 nick 与 displayName 不同时展示，让用户看到原始昵称 */}
          {userInfo.nick && userInfo.nick !== displayName && (
            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
              闲鱼昵称：{userInfo.nick}
            </Text>
          )}
          {/* 自定义别名行：用户在多用户管理页设置的标识 */}
          {userInfo.custom_alias && (
            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
              别名：{userInfo.custom_alias}
            </Text>
          )}
          {userInfo.user_id && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              ID: {userInfo.user_id}
            </Text>
          )}
        </div>
        <Tooltip title={refreshingUser ? '正在刷新用户信息和健康状态...' : '刷新用户信息与健康状态'}>
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            loading={loading}
            // 同时刷新 userInfo + cookie health：触发后端 nick 重抓并更新顶部 displayName
            onClick={() => fetchHealth({ withUserInfo: true })}
            aria-label="刷新用户信息与健康状态"
          />
        </Tooltip>
      </div>

      {/* Cookie 健康状态 */}
      {healthContent}

      {/* 操作按钮 */}
      <div style={{
        display: 'flex', gap: 8, marginTop: 12,
        paddingTop: 12, borderTop: `1px solid ${themeToken.colorBorderSecondary}`,
      }}>
        <Button
          block
          icon={<SwapOutlined />}
          onClick={handleSwitchAccount}
        >
          换号
        </Button>
        <Button
          block
          danger
          icon={<LogoutOutlined />}
          loading={loggingOut}
          onClick={handleLogout}
        >
          退出
        </Button>
      </div>
    </div>
  )

  return (
    <Popover
      content={content}
      trigger="hover"
      open={open}
      onOpenChange={handleOpenChange}
      placement="bottomRight"
      // 鼠标移入面板时保持显示，避免用户想点按钮时面板消失
      mouseEnterDelay={0.2}
      mouseLeaveDelay={0.3}
      // 主题适配：Popover 默认白底，暗色主题需显式覆盖
      overlayStyle={{ borderRadius: 8 }}
    >
      <div
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          // 为什么处理 Enter/Space：div 本身无交互语义，需手动支持键盘触发
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setOpen((prev) => !prev)
          }
        }}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '4px 10px', borderRadius: 20, cursor: 'pointer',
          background: themeToken.colorFillQuaternary,
          transition: 'background 0.2s ease',
        }}
        // 悬浮视觉反馈：背景加深
        onMouseEnter={(e) => {
          e.currentTarget.style.background = themeToken.colorFillTertiary
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = themeToken.colorFillQuaternary
        }}
        title="悬浮查看 Cookie 状态"
      >
        {avatarContent}
        <Text
          style={{
            fontSize: 13, fontWeight: 500, maxWidth: 100,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}
        >
          {displayName}
        </Text>
      </div>
    </Popover>
  )
}

// 详情行：图标 + 标签 + 值，紧凑布局
function DetailRow({
  icon,
  label,
  value,
  valueColor,
}: {
  readonly icon?: React.ReactNode
  readonly label: string
  readonly value: string
  readonly valueColor?: string
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
      {icon && <span style={{ fontSize: 13 }}>{icon}</span>}
      <Text type="secondary" style={{ fontSize: 12, minWidth: 56 }}>{label}</Text>
      <Text
        style={{
          fontSize: 12,
          marginLeft: 'auto',
          color: valueColor,
        }}
      >
        {value}
      </Text>
    </div>
  )
}
