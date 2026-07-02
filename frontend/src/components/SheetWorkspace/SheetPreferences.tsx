import { Drawer, Form, InputNumber, Switch, Button, Space, Typography } from 'antd'
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
    setPreferences({ maxSheets: 5, enableAnimation: true, minimizeInsteadOfClose: false })
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
