import { useRef, useMemo } from 'react'
import { Button, Tooltip, theme } from 'antd'
import { CloseOutlined, MinusOutlined, SettingOutlined } from '@ant-design/icons'
import type { SheetItem } from '../../stores/sheetStore'
import type { SheetPreferences } from '../../stores/sheetStore'

interface SheetTabsProps {
  sheets: SheetItem[]
  activeId: string | null
  preferences: SheetPreferences
  onActivate: (id: string) => void
  onClose: (id: string) => void
  onMinimize: (id: string) => void
  onOpenPreferences: () => void
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

function TabItem({
  sheet,
  active,
  onActivate,
  onClose,
  onMinimize,
  activeBg,
  activeColor,
  textColor,
  borderColor,
  doubleClickCloseEnabled,
  doubleClickInterval,
  thumbnailMode,
  thumbnailTooltipEnabled,
}: {
  sheet: SheetItem
  active: boolean
  onActivate: () => void
  onClose: () => void
  onMinimize: () => void
  activeBg: string
  activeColor: string
  textColor: string
  borderColor: string
  doubleClickCloseEnabled: boolean
  doubleClickInterval: number
  thumbnailMode: boolean
  thumbnailTooltipEnabled: boolean
}) {
  // 上次点击时间戳：双击判定依据
  // 为什么用 useRef 而非 state：避免触发重渲染，仅作为内部计时器
  const lastClickRef = useRef<number>(0)

  const handleClick = () => {
    if (!doubleClickCloseEnabled) {
      onActivate()
      return
    }
    const now = Date.now()
    const last = lastClickRef.current
    // 重置时间戳，避免连续三连击触发两次关闭
    lastClickRef.current = now
    if (last > 0 && now - last <= doubleClickInterval) {
      // 命中双击：触发关闭并清空计时器
      lastClickRef.current = 0
      onClose()
      return
    }
    // 首次点击或间隔外：作为普通激活
    onActivate()
  }

  // 缩略图模式：仅图标 + Tooltip
  if (thumbnailMode) {
    const tabContent = (
      <div
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
          borderLeft: active ? `2px solid ${activeColor}` : '2px solid transparent',
          opacity: sheet.minimized ? 0.5 : 1,
          position: 'relative',
          transition: 'background 200ms, opacity 200ms',
        }}
      >
        <span style={{ fontSize: 18, lineHeight: 1 }}>{sheet.icon}</span>
        {sheet.minimized && (
          <span style={{ position: 'absolute', top: 2, right: 2, fontSize: 8, color: activeColor }}>●</span>
        )}
      </div>
    )

    if (!thumbnailTooltipEnabled) {
      return tabContent
    }

    const tooltipContent = (
      <div style={{ maxWidth: 240 }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{sheet.title}</div>
        <div style={{ fontSize: 12, opacity: 0.85 }}>
          <div>路径：{sheet.path}</div>
          <div>创建：{formatOpenedAt(sheet.openedAt)}</div>
          <div>状态：{sheet.minimized ? '已最小化' : (active ? '激活中' : '后台')}</div>
        </div>
      </div>
    )

    return (
      <Tooltip title={tooltipContent} placement="right" mouseEnterDelay={0.3}>
        {tabContent}
      </Tooltip>
    )
  }

  // 标准模式：图标 + 纵向标题 + 操作按钮
  return (
    <div
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
          <Tooltip title="最小化">
            <Button
              type="text"
              size="small"
              icon={<MinusOutlined style={{ fontSize: 10 }} />}
              onClick={(e) => { e.stopPropagation(); onMinimize() }}
              style={{ padding: '0 2px', height: 18 }}
            />
          </Tooltip>
          <Tooltip title="关闭">
            <Button
              type="text"
              size="small"
              danger
              icon={<CloseOutlined style={{ fontSize: 10 }} />}
              onClick={(e) => { e.stopPropagation(); onClose() }}
              style={{ padding: '0 2px', height: 18 }}
            />
          </Tooltip>
        </span>
      )}
      {/* 最小化时显示恢复提示：用 colorPrimary 确保可见性 */}
      {sheet.minimized && (
        <Tooltip title="点击恢复">
          <span style={{ fontSize: 9, color: activeColor, fontWeight: 500 }}>恢复</span>
        </Tooltip>
      )}
    </div>
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
        <Tooltip title={preferences.thumbnailMode ? summary : 'Sheet 偏好设置'}>
          <Button
            type="text"
            icon={<SettingOutlined />}
            onClick={onOpenPreferences}
            block
            style={{ marginTop: 8 }}
          />
        </Tooltip>
      </div>
    </div>
  )
}

export default SheetTabs
