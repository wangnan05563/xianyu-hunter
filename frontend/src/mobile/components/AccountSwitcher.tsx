// frontend/src/mobile/components/AccountSwitcher.tsx
import { useCallback, useState } from 'react'
import { Avatar, Dropdown, Spin, Tag, App } from 'antd'
import type { MenuProps } from 'antd'
import { LogoutOutlined } from '@ant-design/icons'
import { authApi } from '../../api'
import type { AccountInfo } from '../../api/auth'
import { extractApiError } from '../../utils/apiError'

type MenuItem = NonNullable<MenuProps['items']>[number]

// 状态 Tag 颜色：active=绿/expired=橙/disabled=灰
// 与桌面端 STATUS_TAG_COLOR 略有差异：移动端用 orange 替代 error 让视觉更柔和
const STATUS_TAG_COLOR: Record<AccountInfo['status'], string> = {
  active: 'green',
  expired: 'orange',
  disabled: 'default',
}

const STATUS_TAG_TEXT: Record<AccountInfo['status'], string> = {
  active: '正常',
  expired: '已过期',
  disabled: '已禁用',
}

// 显示名优先级：custom_alias > nickname > user_id 前 4 位
// 为什么用 user_id 前 4 位：纯数字 user_id 过长，移动端空间有限需截短
function getDisplayName(account: AccountInfo): string {
  if (account.custom_alias) return account.custom_alias
  if (account.nickname) return account.nickname
  return account.user_id.slice(0, 4)
}

// 触发器文案优先级：current > switching 空串 > 默认"账号"
// 拆出独立函数规避嵌套三元（SonarQube S3358），同时让优先级判定显式化
function getTriggerLabel(current: AccountInfo | undefined, switching: boolean): string {
  if (current) return getDisplayName(current)
  if (switching) return ''
  return '账号'
}

// 默认头像：闲鱼头像常因防盗链加载失败，回退到品牌色占位
const DEFAULT_AVATAR_BG = 'linear-gradient(135deg, #FF6200, #FF8C00)'

export default function MobileAccountSwitcher() {
  const { message } = App.useApp()
  const [accounts, setAccounts] = useState<AccountInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [open, setOpen] = useState(false)

  // 拉取账号列表：下拉打开时触发，避免无谓请求
  const fetchAccounts = useCallback(async () => {
    setLoading(true)
    try {
      const res = await authApi.getAccounts()
      setAccounts(Array.isArray(res) ? res : [])
    } catch (e) {
      // 静默失败：打开下拉时打扰用户不友好；仅打 warn 便于排查
      console.warn(extractApiError(e, '加载账号列表失败'))
    } finally {
      setLoading(false)
    }
    // deps 防御性声明：当前全部为稳定引用（模块导入 + useState setter），不会触发重建
    // 仍显式列出以符合 exhaustive-deps 规范，规避未来若 authApi/extractApiError 改为动态注入时的 stale closure 风险
  }, [authApi, setAccounts, setLoading, extractApiError])

  const handleOpenChange = useCallback((visible: boolean) => {
    setOpen(visible)
    if (visible && !switching) {
      void fetchAccounts()
    }
  }, [fetchAccounts, switching])

  // 切换账号：成功后整页刷新确保所有组件重新拉取新用户数据
  // 后端 verify_session 有 5 分钟缓存，不刷新会读到旧用户态
  const handleSwitch = useCallback(async (account: AccountInfo) => {
    if (account.is_current) {
      setOpen(false)
      return
    }
    setSwitching(true)
    try {
      await authApi.switchAccount(account.user_id)
      message.success(`已切换到 ${getDisplayName(account)}`)
      setOpen(false)
      // 整页刷新：刷新菜单和任务列表，确保新用户隔离的数据生效
      globalThis.location.reload()
    } catch (e) {
      message.error(extractApiError(e, '账号切换失败，请重试'), 3)
    } finally {
      setSwitching(false)
    }
  }, [message])

  // 退出登录：清空当前 session，跳登录页
  // 路径 /xianyu/login：SPA 挂在 /xianyu/ 下，浏览器完整 URL 跳转绕过路由
  const handleLogout = useCallback(async () => {
    setSwitching(true)
    try {
      await authApi.logoutAccount()
      setOpen(false)
      globalThis.location.href = '/xianyu/login'
    } catch (e) {
      message.error(extractApiError(e, '退出失败，请重试'), 3)
    } finally {
      setSwitching(false)
    }
  }, [message])

  // 当前账号：getAccounts 返回的 is_current 标记为准
  const current = accounts.find((a) => a.is_current)
  const others = accounts.filter((a) => !a.is_current)

  // 顶部当前账号信息项：disabled 防止点击触发任何菜单行为
  const headerItems: MenuItem[] = current ? [{
    key: 'current',
    disabled: true,
    label: (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', minWidth: 200 }}>
        {current.avatar_url ? (
          <Avatar size={32} src={current.avatar_url} />
        ) : (
          <Avatar size={32} style={{ background: DEFAULT_AVATAR_BG, fontSize: 13 }}>
            {getDisplayName(current).charAt(0)}
          </Avatar>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {getDisplayName(current)}
          </div>
          <div style={{ fontSize: 11, color: '#999', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {current.user_id}
          </div>
        </div>
      </div>
    ),
  }, { type: 'divider' }] : []

  // 账号列表项：点击切换
  const accountItems: MenuItem[] = others.map((account) => ({
    key: `account-${account.user_id}`,
    disabled: switching,
    onClick: () => { void handleSwitch(account) },
    label: (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
        {account.avatar_url ? (
          <Avatar size={28} src={account.avatar_url} />
        ) : (
          <Avatar size={28} style={{ background: DEFAULT_AVATAR_BG, fontSize: 12 }}>
            {getDisplayName(account).charAt(0)}
          </Avatar>
        )}
        <div style={{ flex: 1, minWidth: 0, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {getDisplayName(account)}
        </div>
        <Tag color={STATUS_TAG_COLOR[account.status]} style={{ margin: 0, fontSize: 10 }}>
          {STATUS_TAG_TEXT[account.status]}
        </Tag>
      </div>
    ),
  }))

  const menuItems: MenuItem[] = [
    ...headerItems,
    ...(loading ? [{
      key: 'loading',
      disabled: true,
      label: (
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <Spin size="small" />
        </div>
      ),
    }] : accountItems),
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      disabled: switching,
      danger: true,
      onClick: () => { void handleLogout() },
      label: '退出登录',
    },
  ]

  // 触发器：头像 + 显示名
  // 切换中显示 Spin 让用户知道操作在进行
  const triggerLabel = getTriggerLabel(current, switching)

  return (
    <Dropdown
      menu={{ items: menuItems }}
      trigger={['click']}
      open={open}
      onOpenChange={handleOpenChange}
      placement="bottomRight"
    >
      <button
        type="button"
        aria-label="账号切换"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '4px 8px',
          borderRadius: 16,
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          font: 'inherit',
          color: 'inherit',
        }}
      >
        {switching ? (
          <Spin size="small" />
        ) : (
          <>
            <Avatar size="small" src={current?.avatar_url} style={current?.avatar_url ? {} : { background: DEFAULT_AVATAR_BG }}>
              {triggerLabel.charAt(0)}
            </Avatar>
            <span style={{ fontSize: 13, maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {triggerLabel}
            </span>
          </>
        )}
      </button>
    </Dropdown>
  )
}
