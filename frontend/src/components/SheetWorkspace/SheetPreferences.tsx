import { Drawer, Form, InputNumber, Switch, Button, Space, Typography, Divider } from 'antd'
import { useSheetStore } from '../../stores/sheetStore'

const { Text } = Typography

interface SheetPreferencesProps {
  open: boolean
  onClose: () => void
}

export function SheetPreferences({ open, onClose }: SheetPreferencesProps) {
  const preferences = useSheetStore((s) => s.preferences)
  const setPreferences = useSheetStore((s) => s.setPreferences)

  const handleReset = () => {
    setPreferences({
      maxSheets: 5,
      enableAnimation: true,
      minimizeInsteadOfClose: false,
      doubleClickCloseEnabled: false,
      doubleClickInterval: 350,
      thumbnailMode: false,
      thumbnailTooltipEnabled: true,
    })
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
          help="两次点击间隔 ≤ 此值视为双击；范围 200-800，推荐 300-500"
        >
          <InputNumber
            min={200}
            max={800}
            step={50}
            value={preferences.doubleClickInterval}
            onChange={(v) => v != null && setPreferences({ doubleClickInterval: v })}
            style={{ width: '100%' }}
            disabled={!preferences.doubleClickCloseEnabled}
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
          help="鼠标悬停在缩略图上时显示 sheet 名称、路径、创建时间等详细信息"
        >
          <Switch
            checked={preferences.thumbnailTooltipEnabled}
            onChange={(checked) => setPreferences({ thumbnailTooltipEnabled: checked })}
            disabled={!preferences.thumbnailMode}
          />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button onClick={onClose}>完成</Button>
            <Button onClick={handleReset}>恢复默认</Button>
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
