import { useRef, useMemo } from 'react'
import type { MutableRefObject } from 'react'
import { Tooltip, theme, Badge } from 'antd'
import { TipButton } from '@/components/TipButton'
import { CloseOutlined, MinusOutlined, SettingOutlined, SwapOutlined } from '@ant-design/icons'
import type { SheetItem, SheetPreferences } from '../../stores/sheetStore'

interface SheetTabsProps {
  readonly sheets: SheetItem[]
  readonly activeId: string | null
  readonly preferences: SheetPreferences
  readonly onActivate: (id: string) => void
  readonly onClose: (id: string) => void
  readonly onMinimize: (id: string) => void
  readonly onOpenPreferences: () => void
}

/** 格式化时间戳为可读字符串 */
function formatOpenedAt(ts: number): string {
  try {
    const d = new Date(ts)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return '—'
  }
}

interface TabItemProps {
  readonly sheet: SheetItem
  readonly active: boolean
  readonly onActivate: () => void
  readonly onClose: () => void
  readonly onMinimize: () => void
  readonly activeBg: string
  readonly activeColor: string
  readonly textColor: string
  readonly borderColor: string
  readonly doubleClickCloseEnabled: boolean
  readonly doubleClickInterval: number
  readonly thumbnailMode: boolean
  readonly thumbnailTooltipEnabled: boolean
}

// S6767：子组件仅声明实际使用的 props，避免声明但未使用的 PropType
// ThumbnailTab 不需要 onActivate/onMinimize/borderColor/doubleClick*/thumbnailMode
type ThumbnailTabProps = Pick<TabItemProps, 'sheet' | 'active' | 'onClose' | 'activeBg' | 'activeColor' | 'textColor' | 'thumbnailTooltipEnabled'> & {
  readonly handleClick: (e?: React.MouseEvent<HTMLElement>) => void
}

// StandardTab 不需要 onActivate/doubleClick*/thumbnailMode/thumbnailTooltipEnabled
type StandardTabProps = Pick<TabItemProps, 'sheet' | 'active' | 'onClose' | 'onMinimize' | 'activeBg' | 'activeColor' | 'textColor' | 'borderColor'> & {
  readonly handleClick: (e?: React.MouseEvent<HTMLElement>) => void
}

function TabItem(props: TabItemProps) {
  // 上次点击时间戳：双击判定依据
  // 为什么用 useRef 而非 state：避免触发重渲染，仅作为内部计时器
  const lastClickRef = useRef<number>(0)

  // I1: 双击触发关闭后阻止事件冒泡，与关闭按钮的 stopPropagation 行为一致
  // 为什么返回布尔值：handleTabClick 需要告知调用方是否触发了关闭，以便决定是否 stopPropagation
  const handleClick = (e?: React.MouseEvent<HTMLElement>) => {
    if (handleTabClick(props, lastClickRef)) {
      e?.stopPropagation()
    }
  }

  if (props.thumbnailMode) {
    return <ThumbnailTab {...props} handleClick={handleClick} />
  }
  return <StandardTab {...props} handleClick={handleClick} />
}

/** 双击关闭判定与回放：避免在 TabItem 主体内嵌套复杂条件（S3776）
 *  返回 true 表示触发了关闭（调用方应阻止事件冒泡），false 表示仅激活
 */
function handleTabClick(
  props: TabItemProps,
  lastClickRef: MutableRefObject<number>,
): boolean {
  if (!props.doubleClickCloseEnabled) {
    props.onActivate()
    return false
  }
  const now = Date.now()
  const last = lastClickRef.current
  // 重置时间戳，避免连续三连击触发两次关闭
  lastClickRef.current = now
  if (last > 0 && now - last <= props.doubleClickInterval) {
    // 命中双击：触发关闭并清空计时器
    lastClickRef.current = 0
    props.onClose()
    return true
  }
  // 首次点击或间隔外：作为普通激活
  props.onActivate()
  return false
}

/** 缩略图模式：仅图标 + Tooltip */
function ThumbnailTab({
  sheet,
  active,
  onClose,
  activeBg,
  activeColor,
  textColor,
  thumbnailTooltipEnabled,
  handleClick,
}: ThumbnailTabProps) {
  const tabContent = (
    <button
      type="button"
      className={`sheet-tab${active ? ' sheet-tab-active' : ''}${sheet.minimized ? ' sheet-tab-minimized' : ''}`}
      onClick={handleClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '8px 0',
        cursor: 'pointer',
        width: 40,
        height: 40,
        borderRadius: 6,
        background: active ? activeBg : 'transparent',
        color: active ? activeColor : textColor,
        border: 'none',
        borderLeft: active ? `2px solid ${activeColor}` : '2px solid transparent',
        opacity: sheet.minimized ? 0.5 : 1,
        position: 'relative',
        transition: 'background 200ms, opacity 200ms',
      }}
    >
      <span style={{ fontSize: 18, lineHeight: 1 }}>{sheet.icon}</span>
      {/* 缩略图模式激活态显示微型关闭按钮：
          双击关闭禁用时缩略图模式原本无任何关闭途径，属于可用性阻塞 */}
      {active && !sheet.minimized && (
        <TipButton
          tip="关闭此 sheet"
          type="text"
          size="small"
          danger
          data-testid="sheet-thumbnail-close"
          icon={<CloseOutlined style={{ fontSize: 8 }} />}
          onClick={(e) => { e.stopPropagation(); onClose() }}
          style={{
            position: 'absolute',
            top: -2,
            right: -2,
            padding: 0,
            width: 14,
            height: 14,
            minWidth: 14,
            borderRadius: '50%',
            background: '#fff',
            boxShadow: '0 0 0 1px currentColor',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        />
      )}
      {sheet.minimized && (
        <span style={{ position: 'absolute', top: 2, right: 2, fontSize: 8, color: activeColor }}>●</span>
      )}
    </button>
  )

  if (!thumbnailTooltipEnabled) {
    return tabContent
  }

  // 提取嵌套三元为独立变量：避免 JSX 内嵌套三元降低可读性（S3358）
  const activeText = active ? '激活中' : '后台'
  const statusText = sheet.minimized ? '已最小化' : activeText
  const tooltipContent = (
    <div style={{ maxWidth: 240 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{sheet.title}</div>
      <div style={{ fontSize: 12, opacity: 0.85 }}>
        <div>路径：{sheet.path}</div>
        <div>创建：{formatOpenedAt(sheet.openedAt)}</div>
        <div>状态：{statusText}</div>
      </div>
    </div>
  )

  return (
    <Tooltip title={tooltipContent} placement="right" mouseEnterDelay={0.3}>
      {tabContent}
    </Tooltip>
  )
}

/** 标准模式：图标 + 纵向标题 + 操作按钮 */
function StandardTab({
  sheet,
  active,
  onClose,
  onMinimize,
  activeBg,
  activeColor,
  textColor,
  borderColor,
  handleClick,
}: StandardTabProps) {
  return (
    <button
      type="button"
      className={`sheet-tab${active ? ' sheet-tab-active' : ''}${sheet.minimized ? ' sheet-tab-minimized' : ''}`}
      onClick={handleClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 4,
        padding: '10px 6px',
        cursor: 'pointer',
        width: 64,
        borderRadius: 6,
        background: active ? activeBg : 'transparent',
        color: active ? activeColor : textColor,
        border: 'none',
        borderLeft: active ? `2px solid ${activeColor}` : '2px solid transparent',
        opacity: sheet.minimized ? 0.5 : 1,
        position: 'relative',
        transition: 'background 200ms, opacity 200ms',
      }}
      title={sheet.title}
    >
      {/* 图标 */}
      <span style={{ fontSize: 18, lineHeight: 1 }}>{sheet.icon}</span>
      {/* 标题：纵向截断 */}
      <span style={{
        fontSize: 11,
        writingMode: 'vertical-rl',
        textOverflow: 'ellipsis',
        overflow: 'hidden',
        whiteSpace: 'nowrap',
        maxHeight: 80,
        letterSpacing: 1,
      }}>
        {sheet.title}
      </span>
      {/* 最小化标识 */}
      {sheet.minimized && (
        <span style={{ position: 'absolute', top: 2, right: 2, fontSize: 8, color: borderColor }}>●</span>
      )}
      {/* 操作按钮：激活态显示 */}
      {active && !sheet.minimized && (
        <span style={{ display: 'flex', gap: 2, marginTop: 2 }}>
          <TipButton
            tip="最小化此 sheet"
            type="text"
            size="small"
            icon={<MinusOutlined style={{ fontSize: 10 }} />}
            onClick={(e) => { e.stopPropagation(); onMinimize() }}
            style={{ padding: '0 2px', height: 18 }}
          />
          <TipButton
            tip="关闭此 sheet"
            type="text"
            size="small"
            danger
            icon={<CloseOutlined style={{ fontSize: 10 }} />}
            onClick={(e) => { e.stopPropagation(); onClose() }}
            style={{ padding: '0 2px', height: 18 }}
          />
        </span>
      )}
      {/* 最小化时显示恢复提示：用 colorPrimary 确保可见性 */}
      {sheet.minimized && (
        <Tooltip title="点击恢复">
          <span style={{ fontSize: 9, color: activeColor, fontWeight: 500 }}>恢复</span>
        </Tooltip>
      )}
    </button>
  )
}

export function SheetTabs({
  sheets,
  activeId,
  preferences,
  onActivate,
  onClose,
  onMinimize,
  onOpenPreferences,
}: SheetTabsProps) {
  const { token: themeToken } = theme.useToken()

  // 缩略图模式下整体宽度收窄
  const containerWidth = preferences.thumbnailMode ? 56 : 80

  // 缩略图模式时提示信息：当前打开数量
  const summary = useMemo(() => `共 ${sheets.length} 个 sheet`, [sheets.length])

  return (
    <div className="sheet-tabs" style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
      padding: 8,
      width: containerWidth,
      background: themeToken.colorBgContainer,
      borderLeft: `1px solid ${themeToken.colorBorderSecondary}`,
      overflowY: 'auto',
    }}>
      {/* 循环替换状态指示徽标：仅在开启时显示，让用户在使用过程中随时可识别状态 */}
      {preferences.circularReplaceEnabled && (
        <Tooltip title="循环替换已开启：达到上限时自动淘汰最旧非激活 sheet" placement="right">
          <div
            className="sheet-circular-indicator"
            data-testid="sheet-circular-indicator"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '6px 0',
              borderRadius: 6,
              background: themeToken.colorPrimaryBg,
              color: themeToken.colorPrimary,
              cursor: 'help',
            }}
          >
            <Badge dot color={themeToken.colorPrimary}>
              <SwapOutlined style={{ fontSize: 14 }} />
            </Badge>
          </div>
        </Tooltip>
      )}
      {sheets.map((s) => (
        <TabItem
          key={s.id}
          sheet={s}
          active={s.id === activeId}
          onActivate={() => onActivate(s.id)}
          onClose={() => onClose(s.id)}
          onMinimize={() => onMinimize(s.id)}
          activeBg={themeToken.colorPrimaryBg}
          activeColor={themeToken.colorPrimary}
          textColor={themeToken.colorText}
          borderColor={themeToken.colorBorder}
          doubleClickCloseEnabled={preferences.doubleClickCloseEnabled}
          doubleClickInterval={preferences.doubleClickInterval}
          thumbnailMode={preferences.thumbnailMode}
          thumbnailTooltipEnabled={preferences.thumbnailTooltipEnabled}
        />
      ))}
      {/* 底部偏好设置入口 */}
      <div style={{ marginTop: 'auto' }}>
        <TipButton
          tip={preferences.thumbnailMode ? summary : '打开 Sheet 偏好设置'}
          type="text"
          icon={<SettingOutlined />}
          onClick={onOpenPreferences}
          block
          style={{ marginTop: 8 }}
        />
      </div>
    </div>
  )
}

export default SheetTabs
