import { useEffect, useState } from 'react'
import {
  Card,
  InputNumber,
  Button,
  Space,
  message,
  Tag,
  Alert,
  Typography,
  Row,
  Col,
  Modal,
  Table,
} from 'antd'
import { SaveOutlined, UndoOutlined, BellOutlined, AimOutlined, ThunderboltOutlined, WarningOutlined } from '@ant-design/icons'
import { useConfigStore } from '../../stores/configStore'
import type { DiffChange } from '../../stores/configStore'
import { extractApiError } from '../../utils/apiError'

const { Text, Paragraph } = Typography

// 三种任务执行模式定义
const MODES = [
  {
    key: 'notify',
    icon: <BellOutlined />,
    label: 'notify',
    desc: '仅推送通知，不抢单（最安全）',
    color: '#1677ff' as const,
    bgColor: '#e6f4ff',
  },
  {
    key: 'confirm',
    icon: <AimOutlined />,
    label: 'confirm',
    desc: '推送后等待用户确认（推荐日常）',
    color: '#faad14' as const,
    bgColor: '#fffbe6',
  },
  {
    key: 'auto',
    icon: <ThunderboltOutlined />,
    label: 'auto',
    desc: '全自动抢单（仅在 auto_buy_score 足够高时使用）',
    color: '#FF6200' as const,
    bgColor: '#fff2e8',
  },
] as const

export default function BuyerStrategy() {
  const { config, load, save, hasChanges, reset, update, previewSave, confirmSave } = useConfigStore()
  const [loading, setLoading] = useState(false)
  // Diff 预览
  const [diffModalOpen, setDiffModalOpen] = useState(false)
  const [diffChanges, setDiffChanges] = useState<DiffChange[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    load()
  }, [load])

  if (!config) {
    return <div className="page-container">加载中...</div>
  }

  const { eval: evalConfig } = config

  // 数值防御：确保在 [0, 100] 范围内
  const clamp = (v: number | undefined | null): number => {
    if (v == null || isNaN(v)) return 0
    return Math.max(0, Math.min(100, v))
  }

  // 更新 auto_buy_score
  const updateAutoBuyScore = (v: number | null) => {
    update({
      eval: {
        ...evalConfig,
        auto_buy_score: clamp(v),
      },
    })
  }

  // 更新 pass_score
  const updatePassScore = (v: number | null) => {
    update({
      eval: {
        ...evalConfig,
        pass_score: clamp(v),
      },
    })
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      const changes = await previewSave()
      if (changes.length === 0) {
        message.info('配置未变更')
        return
      }
      setDiffChanges(changes)
      setDiffModalOpen(true)
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
    }
  }

  const handleConfirmSave = async () => {
    try {
      setSaving(true)
      await confirmSave()
      setDiffModalOpen(false)
      message.success('抢单策略已保存')
    } catch (e) {
      message.error(extractApiError(e), 5)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page-container">
      {/* 页面标题 + 操作栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h2 style={{ margin: 0, marginBottom: 4 }}>抢单策略</h2>
          <Text type="secondary">这些参数控制 auto 模式下的抢单行为。notify / confirm 模式不受影响。</Text>
        </div>
        <Space>
          <Button icon={<UndoOutlined />} onClick={reset} disabled={!hasChanges()}>
            重置
          </Button>
          <Button type="primary" style={{ backgroundColor: '#FF6200' }} icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
            保存
          </Button>
        </Space>
      </div>

      {/* 抢单分数配置 */}
      <Card title="分数阈值" style={{ marginBottom: 24 }}>
        <Row gutter={24}>
          <Col span={12}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}>
                <strong>自动抢单最低分数（auto_buy_score）</strong>
              </div>
              <InputNumber
                min={0}
                max={100}
                value={clamp(evalConfig.auto_buy_score)}
                onChange={updateAutoBuyScore}
                style={{ width: '100%' }}
                addonAfter="分"
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                ≥ 此分数才会自动拍下（在「评估权重」页面设置评分规则）
              </Paragraph>
            </div>
          </Col>

          <Col span={12}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}>
                <strong>通过分数（pass_score）</strong>
              </div>
              <InputNumber
                min={0}
                max={100}
                value={clamp(evalConfig.pass_score)}
                onChange={updatePassScore}
                style={{ width: '100%' }}
                addonAfter="分"
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                ≥ 此分数会推送给用户确认
              </Paragraph>
            </div>
          </Col>
        </Row>
      </Card>

      {/* 任务级模式说明 */}
      <Card title="任务级模式" style={{ marginBottom: 24 }}>
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          每个任务可独立设置执行模式（在「任务管理」中）：
        </Text>
        <Row gutter={[16, 16]}>
          {MODES.map((mode) => (
            <Col span={8} key={mode.key}>
              <Card
                size="small"
                style={{
                  borderColor: mode.color,
                  backgroundColor: mode.bgColor,
                  textAlign: 'center',
                }}
              >
                <Tag
                  icon={mode.icon}
                  color={mode.color}
                  style={{ fontSize: 14, padding: '4px 12px' }}
                >
                  {mode.label}
                </Tag>
                <p style={{ margin: '8px 0 0', color: 'var(--xh-text-secondary)', fontSize: 13 }}>{mode.desc}</p>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      {/* 安全护栏 */}
      <Card title="安全护栏" style={{ marginBottom: 24 }}>
        <ul style={{ paddingLeft: 20, lineHeight: 2.2, margin: 0 }}>
          <li><Text>auto_buy_score ≥ 80 才启用 auto 模式</Text></li>
          <li>
            <Text>单日抢单数量上限：在 </Text>
            <code style={{ background: 'var(--xh-bg-code)', padding: '2px 6px', borderRadius: 3 }}>buyer_config.py</code>
            <Text> 中配置（待 UI 化）</Text>
          </li>
          <li><Text>支付前暂停：默认开启（在 Dashboard 可手动接管）</Text></li>
        </ul>

        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          message={
            <span>
              <strong>谨慎使用 auto 模式</strong>：自动拍下会立即锁定你的资金，请确认已充分测试。
            </span>
          }
          style={{ marginTop: 16 }}
        />
      </Card>

      {/* Diff 预览 Modal */}
      <Modal
        title="配置变更预览"
        open={diffModalOpen}
        onCancel={() => setDiffModalOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setDiffModalOpen(false)}>
            取消
          </Button>,
          <Button key="confirm" type="primary" loading={saving} onClick={handleConfirmSave}>
            确认保存
          </Button>,
        ]}
        width={700}
      >
        <Table
          dataSource={diffChanges}
          rowKey="path"
          pagination={false}
          size="small"
          columns={[
            { title: '路径', dataIndex: 'path', key: 'path' },
            { title: '原值', dataIndex: 'old_value', key: 'old_value', render: (v) => v == null ? '-' : String(v) },
            { title: '新值', dataIndex: 'new_value', key: 'new_value', render: (v) => v == null ? '-' : String(v) },
            {
              title: '操作',
              dataIndex: 'op',
              key: 'op',
              render: (op: string) => (
                <Tag color={op === 'add' ? 'green' : op === 'delete' ? 'red' : 'orange'}>
                  {op === 'add' ? '新增' : op === 'delete' ? '删除' : '修改'}
                </Tag>
              ),
            },
          ]}
        />
      </Modal>
    </div>
  )
}
