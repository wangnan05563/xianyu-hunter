import { useState, useCallback, useEffect } from 'react'
import { Avatar, Typography, Tag, Spin, theme, Empty, message, Popover, Drawer } from 'antd'
import { TipButton } from '@/components/TipButton'
import {
  SwapOutlined,
  LogoutOutlined,
  CheckCircleFilled,
  ExclamationCircleFilled,
  ClockCircleOutlined,
  SafetyCertificateOutlined,
  ReloadOutlined,
  InfoCircleOutlined,
  ImportOutlined,
  ThunderboltOutlined,
  LoginOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { authApi } from '../../api'
import type { CookieHealthReport, UnifiedHealthReport, UnifiedHealthSource } from '../../api/auth'
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

// 计算顶部显示名：local_username > nick > 已登录兜底 > '未登录'
// 为什么提取：原代码内联嵌套三元，认知复杂度高；优先级规则集中一处便于维护
// 为什么用 logged_in 兜底：昵称抓取失败时（反爬/DOM 变化）名字字段全空，
// 旧逻辑直接显示"未登录"，与同面板的"Cookie 状态正常"自相矛盾
export const computeDisplayName = (info: AuthMe): string => {
  // local_username 后端已合并 custom_alias > nickname > user_id，等值 user_id 时降级
  if (info.local_username && info.local_username !== info.user_id) return info.local_username
  if (info.nick && info.nick !== info.user_id) return info.nick
  if (info.logged_in) return info.user_id || '已登录'
  if (info.detecting) return '检测中'
  return '未登录'
}

// S3776 修复：renderHealthDetail 原 CC=17，拆分为多个小组件 + 查表映射降低复杂度
// 每个子组件职责单一，主函数只剩组合逻辑

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
// 结论来源：统一健康端点 status（PRD FR-C1-5 面板展示统一结论），
// legacy CookieHealthReport 仅承载明细字段
const UNIFIED_STATUS_META = {
  healthy: { text: '登录态正常', color: 'success' as const },
  degraded: { text: '会话令牌待刷新', color: 'warning' as const },
  invalid: { text: '登录态失效', color: 'error' as const },
} as const

// reason.issue 友好文案映射：原始 issue 码对用户无意义
const ISSUE_LABELS: Record<string, string> = {
  expired: '已过期',
  missing: '缺失',
  mtop_token_stale: '会话令牌待刷新（访问闲鱼后自动恢复）',
  collector_session_invalid: '服务端会话已失效',
  no_cookie_data: '无 Cookie 档案',
}

const ACTION_META: Record<string, { label: string; icon: React.ReactNode; tip: string }> = {
  relogin: { label: '重新登录', icon: <LoginOutlined />, tip: '跳转登录页扫码重登录' },
  import_json: { label: '导入登录态', icon: <ImportOutlined />, tip: '从浏览器导出 Cookie JSON 导入' },
  restart_worker: { label: '重启服务', icon: <ThunderboltOutlined />, tip: '重启服务以重建 Worker 会话' },
}

// 统一结论头部：三态图标 + 文案 + 自动修复徽标
function UnifiedHealthHeader({
  unified,
  themeToken,
}: {
  readonly unified: UnifiedHealthReport
  readonly themeToken: ReturnType<typeof theme.useToken>['token']
}) {
  const meta = UNIFIED_STATUS_META[unified.status]
  const StatusIcon = unified.status === 'healthy' ? CheckCircleFilled : ExclamationCircleFilled
  const iconColor = unified.status === 'healthy'
    ? themeToken.colorSuccess
    : unified.status === 'degraded' ? themeToken.colorWarning : themeToken.colorError
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
      <StatusIcon style={{ color: iconColor, fontSize: 16 }} />
      <Text strong style={{ fontSize: 13 }}>{meta.text}</Text>
      {/* 自愈徽标：本轮检查触发了自动修复，让用户知道系统已自行恢复 */}
      {unified.self_healed && (
        <Tag color="processing" style={{ fontSize: 10, margin: 0 }}>已自动修复</Tag>
      )}
      <Tag color={meta.color} style={{ marginLeft: 'auto', fontSize: 11 }}>
        {unified.status === 'healthy' ? '健康' : unified.status === 'degraded' ? '降级' : '失效'}
      </Tag>
    </div>
  )
}

// 原因列表：逐条展示哪个 Cookie / 哪个档案 / 什么问题（去重避免同源同因重复刷屏）
function UnifiedReasonsList({
  unified,
  themeToken,
}: {
  readonly unified: UnifiedHealthReport
  readonly themeToken: ReturnType<typeof theme.useToken>['token']
}) {
  const seen = new Set<string>()
  const rows = unified.reasons.filter((r) => {
    const key = `${r.source}|${r.cookie}|${r.issue}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
  if (rows.length === 0) return null
  return (
    <div style={{
      fontSize: 11, color: themeToken.colorTextSecondary,
      marginBottom: 10, padding: '6px 8px',
      background: themeToken.colorFillQuaternary,
      borderRadius: 4,
    }}>
      {rows.map((r, i) => (
        <div key={i}>
          {r.cookie ? `${r.cookie} ` : ''}
          {ISSUE_LABELS[r.issue] ?? r.issue}
          {r.source !== 'none' && r.source !== 'collector' ? `（${r.source}）` : ''}
        </div>
      ))}
    </div>
  )
}

// 修复引导按钮（FR-C1-4）：invalid 时后端返回可执行动作，前端一键触发
function HealthActionsRow({
  unified,
  themeToken,
  onAction,
}: {
  readonly unified: UnifiedHealthReport
  readonly themeToken: ReturnType<typeof theme.useToken>['token']
  readonly onAction: (action: string) => void
}) {
  if (unified.status !== 'invalid' || unified.actions.length === 0) return null
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
      {unified.actions.map((action) => {
        const meta = ACTION_META[action]
        if (!meta) return null
        return (
          <TipButton
            key={action}
            tip={meta.tip}
            size="small"
            block
            icon={meta.icon}
            onClick={() => onAction(action)}
          >
            {meta.label}
          </TipButton>
        )
      })}
    </div>
  )
}

// 诊断详情抽屉：逐源展示档案评估明细（PRD FR-C1-5 诊断详情）
function DiagnosisDrawer({
  open,
  unified,
  onClose,
  themeToken,
}: {
  readonly open: boolean
  readonly unified: UnifiedHealthReport | null
  readonly onClose: () => void
  readonly themeToken: ReturnType<typeof theme.useToken>['token']
}) {
  return (
    <Drawer
      title="登录态诊断详情"
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
      styles={{ body: { padding: '12px 16px' } }}
    >
      {!unified || unified.sources.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无档案数据" />
      ) : (
        <>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
            结论依据（最新鲜数据源）：{unified.freshest_source ?? '无'}
          </Text>
          {unified.sources.map((s) => (
            <SourceCard key={s.source} src={s} themeToken={themeToken} />
          ))}
        </>
      )}
    </Drawer>
  )
}

// 单个数据源评估卡片
function SourceCard({
  src,
  themeToken,
}: {
  readonly src: UnifiedHealthSource
  readonly themeToken: ReturnType<typeof theme.useToken>['token']
}) {
  return (
    <div style={{
      background: themeToken.colorFillQuaternary,
      borderRadius: 8, padding: '8px 12px', marginBottom: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <Text strong style={{ fontSize: 12 }}>{src.source}</Text>
        <Tag color={src.fresh ? 'success' : 'default'} style={{ fontSize: 10, margin: 0 }}>
          {src.fresh ? '有效' : '不可用'}
        </Tag>
        <Text type="secondary" style={{ fontSize: 10, marginLeft: 'auto' }}>
          {src.cookie_count} 个 Cookie
        </Text>
      </div>
      <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
        来源方式：{src.method}
      </Text>
      {src.identity_valid.length > 0 && (
        <Text style={{ fontSize: 11, display: 'block', color: themeToken.colorSuccess }}>
          ✓ 有效：{src.identity_valid.join('、')}
        </Text>
      )}
      {src.identity_expired.length > 0 && (
        <Text style={{ fontSize: 11, display: 'block', color: themeToken.colorError }}>
          ✗ 已过期：{src.identity_expired.join('、')}
        </Text>
      )}
      {src.identity_missing.length > 0 && (
        <Text style={{ fontSize: 11, display: 'block', color: themeToken.colorWarning }}>
          ✗ 缺失：{src.identity_missing.join('、')}
        </Text>
      )}
      <Text type="secondary" style={{ fontSize: 11 }}>
        会话令牌：{src.has_valid_m5tk ? '✓ 有效' : '✗ 无效'}
      </Text>
    </div>
  )
}

// 昵称未同步提示：auth_helper 抓取失败时给出明确原因，替代过去的静默空昵称
// 为什么需要：打包版 Worker 常驻浏览器独占 browser-data，auth_helper 启动即失败，
// 前端过去只看到裸账号 ID，用户无法判断是"未登录"还是"抓取失败"
function NickSyncHint({
  userInfo,
  themeToken,
}: {
  readonly userInfo: AuthMe
  readonly themeToken: ReturnType<typeof theme.useToken>['token']
}) {
  // 已有真实昵称（浏览器抓取成功）时不提示
  const hasRealNick = Boolean(userInfo.nick)
  if (userInfo.nick_sync_state !== 'failed' || hasRealNick) return null
  return (
    <div style={{
      fontSize: 11, color: themeToken.colorWarning,
      marginTop: 4, padding: '4px 6px',
      background: themeToken.colorFillQuaternary,
      borderRadius: 4,
      display: 'flex', alignItems: 'center', gap: 4,
    }}>
      <ExclamationCircleFilled style={{ fontSize: 11 }} />
      <span>昵称未同步（浏览器抓取失败），当前显示账号名</span>
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
        // S3358：嵌套三元拆分为 if/else，避免认知复杂度过高
        let text: string
        if (key === 'is_session_cookie') {
          text = active ? label : '持久化'
        } else {
          text = active ? `✓ ${label}` : `✗ ${label}`
        }
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

// 健康详情主渲染函数：结论区消费统一端点，明细区保留 legacy 字段
// 复杂度降低原因：条件判断分散到各子组件，主函数无分支嵌套
const renderHealthDetail = (
  unified: UnifiedHealthReport | null,
  legacy: CookieHealthReport | null,
  themeToken: ReturnType<typeof theme.useToken>['token'],
  onAction: (action: string) => void,
  onOpenDiagnosis: () => void,
) => {
  if (!unified) {
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
      <UnifiedHealthHeader unified={unified} themeToken={themeToken} />
      <UnifiedReasonsList unified={unified} themeToken={themeToken} />
      <HealthActionsRow unified={unified} themeToken={themeToken} onAction={onAction} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
        <DetailRow
          icon={<ClockCircleOutlined style={{ color: themeToken.colorPrimary }} />}
          label="有效期"
          value={unified.expiry_human || legacy?.expiry_human || '未知'}
        />
        <DetailRow
          icon={<SafetyCertificateOutlined style={{ color: themeToken.colorPrimary }} />}
          label="Cookie 数"
          value={`${legacy?.cookie_count ?? unified.sources.reduce((n, s) => n + s.cookie_count, 0)} 个`}
        />
        {legacy && <HealthLayersList health={legacy} themeToken={themeToken} />}
        {legacy && <SecurityFlags flags={legacy.security_flags} themeToken={themeToken} />}
      </div>
      {/* 诊断详情入口：抽屉逐源展示档案评估明细 */}
      <TipButton
        tip="查看各数据源逐项诊断明细"
        type="text"
        size="small"
        block
        icon={<InfoCircleOutlined />}
        onClick={onOpenDiagnosis}
      >
        诊断详情
      </TipButton>
    </>
  )
}

export default function UserMenu({ userInfo, onRefreshUserInfo }: UserMenuProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { token: themeToken } = theme.useToken()

  const [open, setOpen] = useState(false)
  const [health, setHealth] = useState<CookieHealthReport | null>(null)
  // 统一健康结论（PRD FR-C1-5）：面板展示的唯一结论来源
  const [unified, setUnified] = useState<UnifiedHealthReport | null>(null)
  const [diagnosisOpen, setDiagnosisOpen] = useState(false)
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
      // 并行拉统一结论 + legacy 明细：结论来自统一端点（禁止各自下结论），
      // legacy 仅承载分层/安全标记等明细字段；任一失败置 null 由渲染层兜底
      const tasks: [Promise<UnifiedHealthReport | null>, Promise<CookieHealthReport | null>, Promise<AuthMe | null>] = [
        authApi.getUnifiedHealth().catch(() => null),
        authApi.checkCookieHealth().catch(() => null),
        opts?.withUserInfo && onRefreshUserInfo ? onRefreshUserInfo() : Promise.resolve(null),
      ]
      // userData 由父组件通过 props 更新，这里无需 setState，故不解构第二个返回值
      // S3735 修复：原 `void userData` 用 void 操作符抑制未使用警告，删除 void 改为不解构
      const [unifiedData, legacyData] = await Promise.all(tasks)
      setUnified(unifiedData)
      if (legacyData) setHealth(legacyData)
    } catch {
      setUnified(null)
      setHealth(null)
    } finally {
      setLoading(false)
      setRefreshingUser(false)
    }
  }, [onRefreshUserInfo])

  // FR-C1-4 修复引导：一键触发后端返回的可执行动作
  const handleHealthAction = useCallback((action: string) => {
    if (action === 'restart_worker') {
      // 服务重启属于用户手动操作：给出明确指引而非伪装成前端可完成
      message.info('请在系统托盘或终端重启服务，重启后 Worker 将加载最新登录态')
      return
    }
    // relogin / import_json：都跳登录页（登录页含扫码与导入通道，T01779 落地导入 Tab）
    setOpen(false)
    const currentPath = location.pathname + location.search
    navigate(`/login?redirect=${encodeURIComponent(currentPath)}`)
  }, [navigate, location])

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
  const healthDetailContent = renderHealthDetail(
    unified, health, themeToken, handleHealthAction, () => setDiagnosisOpen(true),
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
          {/* 闲鱼昵称行：仅当 nick 与 displayName 不同时展示，让用户看到原始昵称
              nick 来自浏览器抓取的真实昵称，Cookie 账号名兜底不会落到这里，
              因此兜底名永远不会被标成「闲鱼昵称」 */}
          {userInfo.nick && userInfo.nick !== displayName && (
            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
              闲鱼昵称：{userInfo.nick}
            </Text>
          )}
          {/* 账号名行：昵称抓取失败时用 Cookie tracknick 兜底，显式标注为「账号名」
              而非「闲鱼昵称」，避免误导用户以为这是闲鱼展示昵称 */}
          {userInfo.display_name_source === 'cookie_account' && (
            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
              账号名：{displayName}
            </Text>
          )}
          {/* 昵称未同步提示 */}
          <NickSyncHint userInfo={userInfo} themeToken={themeToken} />
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
        <TipButton
          tip={refreshingUser ? '正在刷新用户信息和健康状态...' : '刷新用户信息与健康状态'}
          type="text"
          size="small"
          icon={<ReloadOutlined />}
          loading={loading}
          // 同时刷新 userInfo + cookie health：触发后端 nick 重抓并更新顶部 displayName
          onClick={() => fetchHealth({ withUserInfo: true })}
          aria-label="刷新用户信息与健康状态"
        />
      </div>

      {/* Cookie 健康状态 */}
      {healthContent}

      {/* 操作按钮 */}
      <div style={{
        display: 'flex', gap: 8, marginTop: 12,
        paddingTop: 12, borderTop: `1px solid ${themeToken.colorBorderSecondary}`,
      }}>
        <TipButton
          tip="切换到其他闲鱼账号"
          block
          icon={<SwapOutlined />}
          onClick={handleSwitchAccount}
        >
          换号
        </TipButton>
        <TipButton
          tip="退出当前账号并清除登录态"
          block
          danger
          icon={<LogoutOutlined />}
          loading={loggingOut}
          onClick={handleLogout}
        >
          退出
        </TipButton>
      </div>
    </div>
  )

  return (
    <>
      <Popover
        content={content}
        trigger="hover"
        open={open}
        onOpenChange={handleOpenChange}
        placement="bottomRight"
        // 鼠标移入面板时保持显示，避免用户想点按钮时面板消失
        mouseEnterDelay={0.2}
        mouseLeaveDelay={0.3}
        // S1874：overlayStyle 已弃用，改用 styles.root
        styles={{ root: { borderRadius: 8 } }}
      >
      {/* S6819：原生 button 替代 div[role="button"]，键盘 Enter/Space 由浏览器原生触发 onClick */}
      <button
        type="button"
        aria-label="悬浮查看 Cookie 状态"
        onClick={() => setOpen((prev) => !prev)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '4px 10px', borderRadius: 20, cursor: 'pointer',
          background: themeToken.colorFillQuaternary,
          transition: 'background 0.2s ease',
          // 按钮重置：消除浏览器默认样式，保持与原 div 视觉一致
          border: 'none',
          outline: 'none',
          font: 'inherit',
          color: 'inherit',
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
      </button>
      </Popover>
      {/* 诊断详情抽屉：挂在 Popover 外层，避免随悬浮面板关闭而销毁 */}
      <DiagnosisDrawer
        open={diagnosisOpen}
        unified={unified}
        onClose={() => setDiagnosisOpen(false)}
        themeToken={themeToken}
      />
    </>
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
