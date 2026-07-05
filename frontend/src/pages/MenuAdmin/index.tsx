import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Layout,
  Typography,
  Button,
  Space,
  Table,
  Switch,
  InputNumber,
  Card,
  Spin,
  message,
  Popconfirm,
  Tag,
  theme,
} from 'antd'
import {
  ArrowLeftOutlined,
  SettingOutlined,
  SaveOutlined,
  UndoOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { menuApi } from '../../api'
import type { MenuItem, MenuItemUpdate } from '../../api/menu'
import { MENU_GROUP_LABELS } from '../../api/menu'
import { extractApiError } from '../../utils/apiError'

const { Header, Content } = Layout
const { Title, Text } = Typography

// 表格行数据：扩展 MenuItem 含 key 用于 Table rowKey
// 项目规范：用 type 而非 interface 定义数据结构；扩展类型用交叉类型 & 而非 extends
type MenuRow = MenuItem & {
  // 行内编辑缓存：visible/sort_order 在表格内编辑，保存时统一提交
  editVisible: boolean
  editSortOrder: number
  // 是否被用户修改（用于高亮提示未保存）
  dirty: boolean
}

// 分组中文标签：从 menu.ts 共享常量导入，避免与 useMenuConfig 重复定义导致漂移

// 类别标签颜色：与 menu_registry.yaml 的 5 个分组对齐
const CATEGORY_TAG_COLOR: Record<string, string> = {
  overview: 'blue',
  data_view: 'cyan',
  config: 'purple',
  maintenance: 'orange',
  other: 'default',
}

export default function MenuAdmin() {
  const navigate = useNavigate()
  const { token } = theme.useToken()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  // 原始菜单数据（用于对比 dirty）
  const [original, setOriginal] = useState<MenuItem[]>([])
  // 编辑中数据
  const [rows, setRows] = useState<MenuRow[]>([])

  // 拉取菜单配置
  const loadMenus = useCallback(async (): Promise<void> => {
    setLoading(true)
    try {
      const data = await menuApi.get()
      setOriginal(data)
      setRows(
        data.map((m) => ({
          ...m,
          editVisible: m.visible,
          editSortOrder: m.sort_order,
          dirty: false,
        })),
      )
    } catch (err) {
      message.error(extractApiError(err, '加载菜单配置失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadMenus()
  }, [loadMenus])

  // 切换可见性
  const handleVisibleChange = useCallback((key: string, checked: boolean) => {
    setRows((prev) =>
      prev.map((r) =>
        r.key === key
          ? { ...r, editVisible: checked, dirty: r.editVisible !== r.visible || r.editSortOrder !== r.sort_order }
          : r,
      ),
    )
  }, [])

  // 调整排序值
  const handleSortOrderChange = useCallback((key: string, value: number | null) => {
    const v = typeof value === 'number' ? value : 0
    setRows((prev) =>
      prev.map((r) =>
        r.key === key
          ? { ...r, editSortOrder: v, dirty: r.editVisible !== r.visible || v !== r.sort_order }
          : r,
      ),
    )
  }, [])

  // 是否有未保存修改
  const hasDirty = useMemo(() => rows.some((r) => r.dirty), [rows])

  // 保存配置
  const handleSave = useCallback(async (): Promise<void> => {
    // 仅提交被修改的项
    const updates: MenuItemUpdate[] = rows
      .filter((r) => r.dirty)
      .map((r) => ({
        menu_key: r.key,
        visible: r.editVisible,
        sort_order: r.editSortOrder,
      }))

    if (updates.length === 0) {
      message.info('没有需要保存的修改')
      return
    }

    setSaving(true)
    const hide = message.loading('正在保存菜单配置…', 0)
    try {
      await menuApi.update(updates)
      // 保存成功后重新拉取，确保前端状态与后端一致
      await loadMenus()
      hide()
      message.success(`已保存 ${updates.length} 项修改`)
    } catch (err) {
      hide()
      message.error(extractApiError(err, '保存失败，请重试'))
    } finally {
      setSaving(false)
    }
  }, [rows, loadMenus])

  // 重置为默认配置
  const handleReset = useCallback(async (): Promise<void> => {
    setResetting(true)
    const hide = message.loading('正在重置为默认配置…', 0)
    try {
      await menuApi.reset()
      await loadMenus()
      hide()
      message.success('已重置为默认配置')
    } catch (err) {
      hide()
      message.error(extractApiError(err, '重置失败，请重试'))
    } finally {
      setResetting(false)
    }
  }, [loadMenus])

  // 表格列定义
  const columns = useMemo(
    () => [
      {
        title: '菜单项',
        dataIndex: 'label',
        key: 'label',
        render: (label: string, record: MenuRow) => (
          <Space>
            <Text strong>{label}</Text>
            {record.dirty && <Tag color="orange">未保存</Tag>}
          </Space>
        ),
      },
      {
        title: '标识',
        dataIndex: 'key',
        key: 'key',
        render: (key: string) => <Text type="secondary" code>{key}</Text>,
      },
      {
        title: '路径',
        dataIndex: 'path',
        key: 'path',
        render: (path: string) => <Text type="secondary" style={{ fontSize: 12 }}>{path}</Text>,
      },
      {
        title: '类别',
        dataIndex: 'category',
        key: 'category',
        render: (category: string) => (
          <Tag color={CATEGORY_TAG_COLOR[category] || 'default'}>
            {MENU_GROUP_LABELS[category] || category}
          </Tag>
        ),
      },
      {
        title: '可见',
        dataIndex: 'editVisible',
        key: 'visible',
        width: 80,
        render: (visible: boolean, record: MenuRow) => (
          <Switch
            checked={visible}
            onChange={(checked) => handleVisibleChange(record.key, checked)}
            disabled={saving || resetting}
          />
        ),
      },
      {
        title: '排序',
        dataIndex: 'editSortOrder',
        key: 'sort_order',
        width: 120,
        render: (order: number, record: MenuRow) => (
          <InputNumber
            value={order}
            min={0}
            max={9999}
            step={10}
            onChange={(v) => handleSortOrderChange(record.key, v)}
            disabled={saving || resetting}
            style={{ width: '100%' }}
          />
        ),
      },
    ],
    [handleVisibleChange, handleSortOrderChange, saving, resetting],
  )

  // 按 sort_order 排序展示
  const sortedRows = useMemo(
    () => [...rows].sort((a, b) => a.sort_order - b.sort_order),
    [rows],
  )

  return (
    <Layout style={{ height: '100%' }}>
      <Header
        style={{
          background: token.colorBgContainer,
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 1px 4px rgba(0, 0, 0, 0.04)',
          flex: '0 0 auto',
          height: 56,
        }}
      >
        <Space>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate(-1)}
          />
          <SettingOutlined style={{ fontSize: 18, color: token.colorPrimary }} />
          <Title level={4} style={{ margin: 0 }}>菜单管理</Title>
        </Space>
        <Space>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => void loadMenus()}
            disabled={loading || saving || resetting}
          >
            刷新
          </Button>
          <Popconfirm
            title="重置为默认配置"
            description="将清除所有自定义菜单配置，是否继续？"
            onConfirm={() => void handleReset()}
            disabled={loading || saving || resetting}
          >
            <Button icon={<UndoOutlined />} disabled={loading || saving || resetting}>
              重置为默认
            </Button>
          </Popconfirm>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={() => void handleSave()}
            disabled={!hasDirty || loading || saving || resetting}
            loading={saving}
          >
            保存{hasDirty ? ` (${rows.filter((r) => r.dirty).length})` : ''}
          </Button>
        </Space>
      </Header>
      <Content style={{ overflow: 'auto', padding: 16, background: token.colorBgLayout }}>
        <Card>
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary">
              调整菜单项的可见性与排序值（保存后立即生效，影响所有页面的侧边栏展示）。
            </Text>
          </div>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '48px 0' }}>
              <Spin size="large" />
              <div style={{ marginTop: 12, color: token.colorTextSecondary }}>加载菜单配置…</div>
            </div>
          ) : (
            <Table<MenuRow>
              rowKey="key"
              columns={columns}
              dataSource={sortedRows}
              pagination={false}
              size="middle"
              bordered
            />
          )}
        </Card>
      </Content>
    </Layout>
  )
}
