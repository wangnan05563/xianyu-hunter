import { useCallback, useState } from 'react'
import { Avatar, Dropdown, Spin, Tag, Typography, message } from 'antd'
import type { MenuProps } from 'antd'
import {
  SwapOutlined,
  LogoutOutlined,
  UserAddOutlined,
  CheckCircleFilled,
  SettingOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../../api'
import type { AccountInfo } from '../../api/auth'
import { invalidateMenuCache } from '../../hooks/useMenuConfig'
import { invalidatePreferenceCache } from '../../hooks/usePreferences'
import { useSheetStore } from '../../stores/sheetStore'
import { storage } from '../../utils/storage'
import { extractApiError } from '../../utils/apiError'

const { Text } = Typography

type MenuItem = NonNullable<MenuProps['items']>[number]

// 默认头像背景：与 UserMenu 品牌色保持一致
const DEFAULT_AVATAR_BG = 'linear-gradient(135deg, #FF6200, #FF8C00)'

// Ant Design CSS 变量 fallback 颜色：仅在 --ant-* 变量未注入时生效（理论上不会触发）
// 为什么集中管理：避免散落多处导致颜色不一致，方便主题切换时统一调整
const FALLBACK = {
  textSecondary: '#999',
  borderSecondary: '#f0f0f0',
  success: '#52c41a',
  fillQuaternary: 'rgba(0,0,0,0.02)',
  fillTertiary: 'rgba(0,0,0,0.04)',
} as const

// 项目规范：用 type 而非 interface 定义组件 Props
type AccountSwitcherProps = {
  /** 当前账号 user_id（用于标记 is_current 与禁用切换到自身） */
  currentUserId?: string
  /** 切换账号成功后回调（父组件可触发菜单/任务刷新） */
  onSwitched?: (userId: string) => void
}

// 账号状态徽标颜色映射
const STATUS_TAG_COLOR: Record<string, string> = {
  active: 'success',
  expired: 'error',
  disabled: 'default',
}

const STATUS_TAG_TEXT: Record<string, string> = {
  active: '正常',
  expired: '已过期',
  disabled: '已禁用',
}

// 计算显示名：custom_alias > nickname > user_id
// 为什么提取：与 UserMenu 的 computeDisplayName 保持一致优先级
function getDisplayName(account: AccountInfo): string {
  if (account.custom_alias) return account.custom_alias
  if (account.nickname) return account.nickname
  return account.user_id
}

// S3776 修复：AccountSwitcher 原 CC=18，拆分为多个子组件 + 独立函数降低复杂度
// 账号菜单项组件：单个账号的渲染逻辑
function AccountMenuItem({
  account,
  isCurrent,
  isExpired,
  disabled,
  avatarError,
  onAvatarError,
  onClick,
}: {
  readonly account: AccountInfo
  readonly isCurrent: boolean
  readonly isExpired: boolean
  readonly disabled: boolean
  readonly avatarError: boolean
  readonly onAvatarError: () => boolean
  readonly onClick: () => void
}) {
  const displayName = getDisplayName(account)
  const avatarUrl = account.avatar_url && !avatarError ? account.avatar_url : undefined
  const showNickname = !!account.nickname && !!account.custom_alias && account.custom_alias !== account.nickname

  return (
    <div
      style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', minWidth: 220 }}
      onClick={onClick}
    >
      {avatarUrl ? (
        <Avatar size={28} src={avatarUrl} onError={onAvatarError} />
      ) : (
        <Avatar size={28} style={{ background: DEFAULT_AVATAR_BG, fontSize: 12 }}>
          {displayName.charAt(0)}
        </Avatar>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Text strong style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 }}>
            {displayName}
          </Text>
          {isCurrent && <CheckCircleFilled style={{ color: `var(--ant-color-success, ${FALLBACK.success})`, fontSize: 12 }} />}
        </div>
        {showNickname && (
          <Text type="secondary" style={{ fontSize: 11, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {account.nickname}
          </Text>
        )}
      </div>
      <Tag color={STATUS_TAG_COLOR[account.status] || 'default'} style={{ fontSize: 10, margin: 0 }}>
        {STATUS_TAG_TEXT[account.status] || account.status}
      </Tag>
    </div>
  )
}

// 构建账号列表菜单项：从主组件抽出，降低主函数复杂度
function buildAccountMenuItems(
  accounts: AccountInfo[],
  currentUserId: string | undefined,
  switching: boolean,
  avatarErrors: Record<string, boolean>,
  handleAvatarError: (userId: string) => boolean,
  handleSwitch: (userId: string) => void,
): MenuItem[] {
  return accounts.map((account) => {
    const isCurrent = account.is_current || account.user_id === currentUserId
    const isExpired = account.status !== 'active'
    return {
      key: `account-${account.user_id}`,
      disabled: switching || isExpired,
      onClick: () => { void handleSwitch(account.user_id) },
      label: (
        <AccountMenuItem
          account={account}
          isCurrent={isCurrent}
          isExpired={isExpired}
          disabled={switching || isExpired}
          avatarError={!!avatarErrors[account.user_id]}
          onAvatarError={() => handleAvatarError(account.user_id)}
          onClick={() => { if (!(switching || isExpired)) handleSwitch(account.user_id) }}
        />
      ),
    }
  })
}

// 下拉触发器按钮组件
function TriggerButton({
  current,
  displayName,
  avatarError,
  onAvatarError,
}: {
  readonly current: AccountInfo | undefined
  readonly displayName: string
  readonly avatarError: boolean
  readonly onAvatarError: () => boolean
}) {
  const avatarUrl = current?.avatar_url && !avatarError ? current.avatar_url : undefined
  return (
    <button
      type="button"
      aria-label="账号切换"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        borderRadius: 20,
        cursor: 'pointer',
        background: `var(--ant-color-fill-quaternary, ${FALLBACK.fillQuaternary})`,
        transition: 'background 0.2s ease',
        border: 'none',
        outline: 'none',
        font: 'inherit',
        color: 'inherit',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = `var(--ant-color-fill-tertiary, ${FALLBACK.fillTertiary})`
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = `var(--ant-color-fill-quaternary, ${FALLBACK.fillQuaternary})`
      }}
    >
      {avatarUrl ? (
        <Avatar size={28} src={avatarUrl} onError={onAvatarError} />
      ) : (
        <Avatar size={28} style={{ background: DEFAULT_AVATAR_BG, fontSize: 13, fontWeight: 600 }}>
          {displayName.charAt(0)}
        </Avatar>
      )}
      <SwapOutlined style={{ fontSize: 12, color: `var(--ant-color-text-secondary, ${FALLBACK.textSecondary})` }} />
    </button>
  )
}

export default function AccountSwitcher({ currentUserId, onSwitched }: AccountSwitcherProps) {
  const navigate = useNavigate()
  const [accounts, setAccounts] = useState<AccountInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [open, setOpen] = useState(false)
  // 头像加载失败状态：user_id → bool
  const [avatarErrors, setAvatarErrors] = useState<Record<string, boolean>>({})

  // 拉取账号列表
  const fetchAccounts = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      // 防御性：后端契约异常（如未返回 accounts 字段）时回退空数组，
      // 避免 setAccounts(undefined) 触发后续 .find() 崩溃
      const res = await authApi.getAccounts()
      const list = Array.isArray(res) ? res : []
      setAccounts(list)
    } catch (err) {
      // 失败时不弹错误消息，避免打开下拉时打扰用户
      const e = err instanceof Error ? err : new Error(String(err))
      console.warn('[AccountSwitcher] 拉取账号列表失败', e)
    } finally {
      setLoading(false)
    }
  }, [])

  // 下拉打开时拉取账号列表
  const handleOpenChange = useCallback((visible: boolean) => {
    setOpen(visible)
    if (visible && !switching) {
      void fetchAccounts()
    }
  }, [fetchAccounts, switching])

  // 切换账号：调用 API 后失效菜单/偏好缓存，刷新页面
  const handleSwitch = useCallback(async (userId: string) => {
    // 已是当前账号：直接关闭下拉
    if (userId === currentUserId) {
      setOpen(false)
      return
    }
    setSwitching(true)
    const hide = message.loading('正在切换账号…', 0)
    try {
      await authApi.switchAccount(userId)
      // 切换成功：失效所有用户级缓存
      invalidateMenuCache()
      invalidatePreferenceCache()
      // 清空 sheet 栈，避免看到上一用户的 sheet
      useSheetStore.getState().closeAll()
      storage.remove('xh.sheets.state')
      // 清除 localStorage 中的旧 token：后端 verify_session 有 5 分钟缓存，
      // 若不清除，整页刷新后 Bearer 头携带旧 token 会被缓存命中，
      // 导致中间件认证为旧用户而非新切换的用户
      storage.remove('xh_token')
      hide()
      message.success('账号切换成功')
      setOpen(false)
      // 通知父组件刷新菜单/任务
      onSwitched?.(userId)
      // 整页刷新：最可靠的重置方式，确保所有组件重新拉取新用户数据
      // 为什么用 replace：避免后退回到上一账号的页面
      globalThis.location.replace('/')
    } catch (err) {
      hide()
      message.error(extractApiError(err, '账号切换失败，请重试'))
    } finally {
      setSwitching(false)
    }
  }, [currentUserId, onSwitched])

  // 退出当前账号
  const handleLogout = useCallback(async () => {
    setSwitching(true)
    const hide = message.loading('正在退出当前账号…', 0)
    try {
      await authApi.logoutAccount()
      invalidateMenuCache()
      invalidatePreferenceCache()
      useSheetStore.getState().closeAll()
      storage.remove('xh.sheets.state')
      storage.remove('xh_token')
      hide()
      message.success('已退出当前账号')
      setOpen(false)
      // 跳转登录页
      setTimeout(() => navigate('/login', { replace: true }), 200)
    } catch (err) {
      hide()
      message.error(extractApiError(err, '退出失败，请重试'))
    } finally {
      setSwitching(false)
    }
  }, [navigate])

  // 添加新账号：跳转登录页
  const handleAddAccount = useCallback(() => {
    setOpen(false)
    // 不带 redirect：登录后用户主动选择是否切换
    navigate('/login?mode=add')
  }, [navigate])

  // 跳转菜单管理
  const handleMenuAdmin = useCallback(() => {
    setOpen(false)
    navigate('/menu-admin')
  }, [navigate])

  // 当前账号（用于头像显示）
  // 防御性：accounts 偶发为 undefined 时回退空数组，避免 .find() 崩溃
  const safeAccounts = Array.isArray(accounts) ? accounts : []
  const current = safeAccounts.find((a) => a.is_current) || safeAccounts.find((a) => a.user_id === currentUserId)
  const displayName = current ? getDisplayName(current) : '账号'
  const avatarUrl = current?.avatar_url && !avatarErrors[current.user_id] ? current.avatar_url : undefined

  // 头像加载失败时回退到品牌色
  const handleAvatarError = (userId: string) => {
    setAvatarErrors((prev) => ({ ...prev, [userId]: true }))
    return false
  }

  // S3776 修复：菜单项构建逻辑拆分到 buildMenuItems，主组件只剩调用
  // 菜单项头部
  const headerItem: MenuItem = {
    key: 'header',
    label: (
      <div style={{ padding: '4px 0', borderBottom: `1px solid var(--ant-color-border-secondary, ${FALLBACK.borderSecondary})`, marginBottom: 4 }}>
        <Text strong>账号切换</Text>
        <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
          共 {accounts.length} 个账号
        </Text>
      </div>
    ),
    disabled: true,
  }

  // 加载中菜单项
  const loadingItem: MenuItem = {
    key: 'loading',
    label: (
      <div style={{ textAlign: 'center', padding: '16px 0' }}>
        <Spin size="small" />
        <div style={{ marginTop: 8, fontSize: 12, color: `var(--ant-color-text-secondary, ${FALLBACK.textSecondary})` }}>加载账号列表…</div>
      </div>
    ),
    disabled: true,
  }

  // 底部操作项配置表：用查表替代逐个 push
  type ActionItemConfig = {
    readonly key: string
    readonly icon: React.ReactNode
    readonly label: string
    readonly onClick: () => void
    readonly danger?: boolean
    readonly dividerBefore?: boolean
  }
  const ACTION_ITEMS: ReadonlyArray<ActionItemConfig> = [
    { key: 'add-account', icon: <UserAddOutlined />, label: '添加新账号', onClick: handleAddAccount, dividerBefore: true },
    { key: 'menu-admin', icon: <SettingOutlined />, label: '菜单管理', onClick: handleMenuAdmin },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出当前账号', onClick: () => { void handleLogout() }, danger: true, dividerBefore: true },
  ]

  // 构建底部操作菜单项
  const actionItems: MenuItem[] = ACTION_ITEMS.flatMap((item) => {
    const result: MenuItem[] = []
    if (item.dividerBefore) result.push({ type: 'divider' })
    result.push({
      key: item.key,
      icon: item.icon,
      disabled: switching,
      onClick: item.onClick,
      danger: item.danger,
      label: item.label,
    })
    return result
  })

  // 账号列表项
  const accountItems: MenuItem[] = loading
    ? [loadingItem]
    : buildAccountMenuItems(accounts, currentUserId, switching, avatarErrors, handleAvatarError, handleSwitch)

  // 最终菜单项：头部 + 账号列表 + 操作项
  const menuItems: MenuItem[] = [headerItem, ...accountItems, ...actionItems]

  // 切换中状态：显示 Spin；否则用 TriggerButton 组件
  const triggerContent = switching ? (
    <Spin size="small" />
  ) : (
    <TriggerButton
      current={current}
      displayName={displayName}
      avatarError={current ? !!avatarErrors[current.user_id] : false}
      onAvatarError={() => { if (current) return handleAvatarError(current.user_id); return true }}
    />
  )

  return (
    <Dropdown
      menu={{ items: menuItems }}
      trigger={['click']}
      open={open}
      onOpenChange={handleOpenChange}
      placement="bottomRight"
    >
      {triggerContent}
    </Dropdown>
  )
}
