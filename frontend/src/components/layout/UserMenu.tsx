import { useState, useCallback, useEffect } from 'react'
import { Avatar, Typography, Tag, Spin, Button, Tooltip, theme, Empty, message } from 'antd'
import { Popover } from 'antd'
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

const { Text } = Typography

interface UserMenuProps {
  userInfo: AuthMe
}

// 默认头像：闲鱼官方品牌色（橙）+ 闲字，作为无 avatar_url 时的兜底
// 为什么不使用第三方占位图：用户要求"官方提供的标准图片资源"，
// 后端 /api/auth/me 返回的 avatar_url 即闲鱼官方头像，无值时用品牌色兜底
const DEFAULT_AVATAR_BG = 'linear-gradient(135deg, #FF6200, #FF8C00)'

export default function UserMenu({ userInfo }: UserMenuProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { token: themeToken } = theme.useToken()

  const [open, setOpen] = useState(false)
  const [health, setHealth] = useState<CookieHealthReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)

  // 健康检查：每次调用都拉取最新状态
  // 为什么不做防抖：Popover 打开 + 刷新按钮均为用户主动操作，频率天然受控；
  // 防抖会导致「刷新」按钮短时间点击无效，与用户预期不符
  const fetchHealth = useCallback(async () => {
    setLoading(true)
    try {
      const data = await authApi.checkCookieHealth()
      setHealth(data)
    } catch {
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // Popover 打开时触发健康检查
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

  const displayName = userInfo.nick || userInfo.user_id || '未登录'
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
          {userInfo.user_id && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              ID: {userInfo.user_id}
            </Text>
          )}
        </div>
        <Tooltip title="刷新健康状态">
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => fetchHealth()}
          />
        </Tooltip>
      </div>

      {/* Cookie 健康状态 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <Spin size="small" />
          <div style={{ marginTop: 8, fontSize: 12, color: themeToken.colorTextSecondary }}>
            正在检查 Cookie 状态...
          </div>
        </div>
      ) : health ? (
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
      )}

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
  icon?: React.ReactNode
  label: string
  value: string
  valueColor?: string
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
