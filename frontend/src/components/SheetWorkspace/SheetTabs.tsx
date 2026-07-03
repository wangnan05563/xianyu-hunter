import { Button, Tooltip, theme } from 'antd'
import { CloseOutlined, MinusOutlined, SettingOutlined } from '@ant-design/icons'
import type { SheetItem } from '../../stores/sheetStore'

interface SheetTabsProps {
  sheets: SheetItem[]
  activeId: string | null
  onActivate: (id: string) => void
  onClose: (id: string) => void
  onMinimize: (id: string) => void
  onOpenPreferences: () => void
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
}) {
  return (
    <div
      className={`sheet-tab${active ? ' sheet-tab-active' : ''}${sheet.minimized ? ' sheet-tab-minimized' : ''}`}
      onClick={onActivate}
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
      {/* 最小化时显示恢复提示 */}
      {sheet.minimized && (
        <Tooltip title="点击恢复">
          <span style={{ fontSize: 9, color: borderColor }}>恢复</span>
        </Tooltip>
      )}
    </div>
  )
}

export function SheetTabs({
  sheets,
  activeId,
  onActivate,
  onClose,
  onMinimize,
  onOpenPreferences,
}: SheetTabsProps) {
  const { token: themeToken } = theme.useToken()

  return (
    <div className="sheet-tabs" style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
      padding: 8,
      width: 80,
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
        />
      ))}
      {/* 底部偏好设置入口 */}
      <div style={{ marginTop: 'auto' }}>
        <Tooltip title="Sheet 偏好设置">
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
