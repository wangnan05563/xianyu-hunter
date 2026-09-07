import { Drawer, Form, InputNumber, Switch, Space, Typography, Divider, Tag } from 'antd'
import { TipButton } from '@/components/TipButton'
import { SwapOutlined } from '@ant-design/icons'
import { useSheetStore, DEFAULT_PREFERENCES } from '../../stores/sheetStore'

const { Text } = Typography

interface SheetPreferencesProps {
  readonly open: boolean
  readonly onClose: () => void
}

export function SheetPreferences({ open, onClose }: SheetPreferencesProps) {
  const preferences = useSheetStore((s) => s.preferences)
  const setPreferences = useSheetStore((s) => s.setPreferences)
  const replacedHistory = useSheetStore((s) => s.replacedHistory)
  const clearReplacedHistory = useSheetStore((s) => s.clearReplacedHistory)

  // 复用 store 的默认值常量，避免两处定义导致默认值变更时不同步
  const handleReset = () => {
    setPreferences({ ...DEFAULT_PREFERENCES })
  }

  return (
    <Drawer
      title="Sheet 偏好设置"
      placement="right"
      open={open}
      onClose={onClose}
      width={360}
    >
      <Form layout="vertical">
        <Form.Item
          label="最大 Sheet 数量"
          help="同时可打开的 sheet 上限，范围 1-10"
        >
          <InputNumber
            min={1}
            max={10}
            step={1}
            value={preferences.maxSheets}
            onChange={(v) => v != null && setPreferences({ maxSheets: v })}
            style={{ width: '100%' }}
          />
        </Form.Item>

        <Form.Item
          label={
            <Space size={6}>
              <span>循环替换</span>
              {/*
                状态徽标：让用户在面板中一眼看到当前开关是否激活
                用 colorPrimary 与主题色统一，简洁不抢眼
              */}
              {preferences.circularReplaceEnabled ? (
                <Tag color="processing" icon={<SwapOutlined />}>已开启</Tag>
              ) : (
                <Tag>已关闭</Tag>
              )}
            </Space>
          }
          help={
            // 帮助文案分两段：开启/关闭行为差异 + 兜底机制，让用户清楚知道替换有恢复路径
            preferences.circularReplaceEnabled
              ? '达到上限时自动淘汰最早打开的非激活 sheet（保护当前查看页）。被替换的 sheet 进入回收栈，可通过 Toast 内的「撤销」按钮在 5 秒内恢复。'
              : '关闭时达到上限会拒绝打开新 sheet。开启后可无界打开新页面，老 sheet 自动回收。'
          }
        >
          <Switch
            checked={preferences.circularReplaceEnabled}
            onChange={(checked) => setPreferences({ circularReplaceEnabled: checked })}
            aria-label="循环替换开关"
          />
        </Form.Item>

        {replacedHistory.length > 0 && (
          <Form.Item
            label={
              <Space size={6}>
                <span>回收栈</span>
                <Tag color="default">{replacedHistory.length}/5</Tag>
              </Space>
            }
            help="最近被循环替换淘汰的 sheet 列表。Toast 中的「撤销」按钮可在 5 秒内恢复最新一项；此处可查看历史。"
          >
            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              {replacedHistory.slice(0, 5).map((r) => (
                <Text
                  key={r.id}
                  data-testid="replaced-sheet-item"
                  data-sheet-path={r.path}
                  type="secondary"
                  style={{ fontSize: 12 }}
                >
                  · {r.title} <Text type="secondary" style={{ fontSize: 11, opacity: 0.65 }}>({r.path})</Text>
                </Text>
              ))}
              <TipButton
                tip="清空已淘汰 sheet 的回收记录"
                size="small"
                type="link"
                onClick={clearReplacedHistory}
                style={{ padding: 0, alignSelf: 'flex-start' }}
              >
                清空回收栈
              </TipButton>
            </Space>
          </Form.Item>
        )}

        <Form.Item label="启用切换动画">
          <Switch
            checked={preferences.enableAnimation}
            onChange={(checked) => setPreferences({ enableAnimation: checked })}
          />
        </Form.Item>

        <Form.Item
          label="关闭按钮改为最小化"
          help="开启后，点击关闭按钮将最小化 sheet 而非真正关闭，保留页面状态"
        >
          <Switch
            checked={preferences.minimizeInsteadOfClose}
            onChange={(checked) => setPreferences({ minimizeInsteadOfClose: checked })}
          />
        </Form.Item>

        <Divider orientation="left" plain>双击关闭</Divider>

        <Form.Item
          label="启用双击关闭"
          help="开启后，在 sheet 标签上快速双击即可关闭（受间隔阈值约束，避免误触）"
        >
          <Switch
            checked={preferences.doubleClickCloseEnabled}
            onChange={(checked) => setPreferences({ doubleClickCloseEnabled: checked })}
            aria-label="双击关闭开关"
          />
        </Form.Item>

        <Form.Item
          label="双击判定间隔（毫秒）"
          help={preferences.doubleClickCloseEnabled ? '两次点击间隔 ≤ 此值视为双击；范围 200-800，推荐 300-500' : '需先启用「启用双击关闭」才能配置此间隔'}
        >
          <InputNumber
            min={200}
            max={800}
            step={50}
            value={preferences.doubleClickInterval}
            onChange={(v) => v != null && setPreferences({ doubleClickInterval: v })}
            style={{ width: '100%' }}
            disabled={!preferences.doubleClickCloseEnabled}
            aria-label="双击判定间隔"
          />
        </Form.Item>

        <Divider orientation="left" plain>缩略图模式</Divider>

        <Form.Item
          label="启用缩略图模式"
          help="开启后标签栏仅显示图标，紧凑布局可在有限空间容纳更多 sheet"
        >
          <Switch
            checked={preferences.thumbnailMode}
            onChange={(checked) => setPreferences({ thumbnailMode: checked })}
            aria-label="缩略图模式开关"
          />
        </Form.Item>

        <Form.Item
          label="显示悬浮提示"
          help={preferences.thumbnailMode ? '鼠标悬停在缩略图上时显示 sheet 名称、路径、创建时间等详细信息' : '需先启用「启用缩略图模式」才能配置悬浮提示'}
        >
          <Switch
            checked={preferences.thumbnailTooltipEnabled}
            onChange={(checked) => setPreferences({ thumbnailTooltipEnabled: checked })}
            disabled={!preferences.thumbnailMode}
            aria-label="显示悬浮提示开关"
          />
        </Form.Item>

        <Form.Item>
          <Space>
            <TipButton tip="关闭偏好设置面板" onClick={onClose}>完成</TipButton>
            <TipButton tip="恢复所有偏好为默认值" onClick={handleReset}>恢复默认</TipButton>
          </Space>
        </Form.Item>

        <Text type="secondary" style={{ fontSize: 12 }}>
          配置即时生效，无需重启。偏好保存在浏览器本地（localStorage key: xh.sheets.preferences）。
        </Text>
      </Form>
    </Drawer>
  )
}

export default SheetPreferences
