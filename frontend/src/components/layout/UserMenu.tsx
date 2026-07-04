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
      const [healthData, userData] = await Promise.all(tasks)
      if (healthData) setHealth(healthData)
      // userData 由父组件通过 props 更新，这里无需 setState
      void userData
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
      void fetchHealth()
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
  // 为什么 local_username 优先：它已包含用户自定义别名，比 nick 更具辨识度；
  // 当 local_username 等于 user_id 时降级到 '未登录'，避免顶部显示十六进制串
  const fallbackName = (userInfo.local_username && userInfo.local_username !== userInfo.user_id)
    ? userInfo.local_username
    : (userInfo.nick && userInfo.nick !== userInfo.user_id ? userInfo.nick : '')
  const displayName = fallbackName || '未登录'
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

  // 健康状态面板内容：将嵌套三元拆为两个变量，降低认知复杂度（S3358）
  // 先算 health 详情（含无数据时的 Empty 兜底），再用 loading 决定显示加载态还是详情
  const healthDetailContent = health ? (
    <>
      {/* 完整性状态 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        {health.is_valid ? (
          <CheckCircleFilled style={{ color: themeToken.colorSuccess, fontSize: 16 }} />
        ) : (
          <ExclamationCircleFilled style={{ color: themeToken.colorError, fontSize: 16 }} />
        )}
        <Text strong style={{ fontSize: 13 }}>
          {health.is_valid ? 'Cookie 状态正常' : 'Cookie 异常'}
        </Text>
        <Tag
          color={health.is_valid ? 'success' : 'error'}
          style={{ marginLeft: 'auto', fontSize: 11 }}
        >
          {health.integrity === 'complete' ? '完整' : '不完整'}
        </Tag>
      </div>
      {!health.is_valid && health.integrity_reason && (
        <div style={{
          fontSize: 11, color: themeToken.colorTextSecondary,
          marginBottom: 10, padding: '6px 8px',
          background: themeToken.colorFillQuaternary,
          borderRadius: 4,
        }}>
          原因：{health.integrity_reason}
        </div>
      )}

      {/* 详情列表 */}
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
        <DetailRow
          label="身份层"
          value={health.layers.identity ? '✓ 已就绪' : '✗ 缺失'}
          valueColor={health.layers.identity ? themeToken.colorSuccess : themeToken.colorError}
        />
        <DetailRow
          label="会话层"
          value={health.layers.session ? '✓ 已就绪' : '✗ 缺失'}
          valueColor={health.layers.session ? themeToken.colorSuccess : themeToken.colorError}
        />
        <DetailRow
          label="追踪层"
          value={health.layers.tracking ? '✓ 已就绪' : '✗ 缺失'}
          valueColor={health.layers.tracking ? themeToken.colorSuccess : themeToken.colorError}
        />
        {/* 安全标记 */}
        <div style={{
          display: 'flex', gap: 6, flexWrap: 'wrap',
          marginTop: 4, paddingTop: 8, borderTop: `1px dashed ${themeToken.colorBorderSecondary}`,
        }}>
          <Tag
            color={health.security_flags.has_secure ? 'green' : 'default'}
            style={{ fontSize: 10, margin: 0 }}
          >
            {health.security_flags.has_secure ? '✓ Secure' : '✗ Secure'}
          </Tag>
          <Tag
            color={health.security_flags.has_httponly ? 'green' : 'default'}
            style={{ fontSize: 10, margin: 0 }}
          >
            {health.security_flags.has_httponly ? '✓ HttpOnly' : '✗ HttpOnly'}
          </Tag>
          <Tag
            color={health.security_flags.is_session_cookie ? 'blue' : 'default'}
            style={{ fontSize: 10, margin: 0 }}
          >
            {health.security_flags.is_session_cookie ? '会话级' : '持久化'}
          </Tag>
        </div>
      </div>
    </>
  ) : (
    <Empty
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description="无法获取 Cookie 状态"
      style={{ padding: '16px 0' }}
    />
  )
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
