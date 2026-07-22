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
} from 'antd'
import { SaveOutlined, UndoOutlined, BellOutlined, AimOutlined, ThunderboltOutlined, WarningOutlined } from '@ant-design/icons'
import { useConfigStore } from '../../stores/configStore'
import type { DiffChange } from '../../stores/configStore'
import { extractApiError } from '../../utils/apiError'
import { DiffPreviewModal } from '../../components/DiffPreviewModal'

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
  const { config, load, hasChanges, reset, update, previewSave, confirmSave } = useConfigStore()
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
    // Number.isNaN 比 isNaN 更严格：不会对非数字类型做隐式转换（SonarQube S7773）
    if (v == null || Number.isNaN(v)) return 0
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
        <Text type="secondary">这些参数控制 auto 模式下的抢单行为。notify / confirm 模式不受影响。</Text>
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
              {/* addonAfter 在 antd v5 已废弃，改用 Space.Compact 紧凑布局（SonarQube S1874） */}
              <Space.Compact style={{ width: '100%' }}>
                <InputNumber
                  min={0}
                  max={100}
                  value={clamp(evalConfig.auto_buy_score)}
                  onChange={updateAutoBuyScore}
                  style={{ flex: 1 }}
                />
                <span style={{ display: 'inline-flex', alignItems: 'center', padding: '0 12px', background: 'var(--xh-bg-spotlight)', border: '1px solid var(--xh-border)', borderLeft: 'none' }}>分</span>
              </Space.Compact>
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
              <Space.Compact style={{ width: '100%' }}>
                <InputNumber
                  min={0}
                  max={100}
                  value={clamp(evalConfig.pass_score)}
                  onChange={updatePassScore}
                  style={{ flex: 1 }}
                />
                <span style={{ display: 'inline-flex', alignItems: 'center', padding: '0 12px', background: 'var(--xh-bg-spotlight)', border: '1px solid var(--xh-border)', borderLeft: 'none' }}>分</span>
              </Space.Compact>
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                ≥ 此分数会推送给用户确认
              </Paragraph>
            </div>
          </Col>
        </Row>
      </Card>

      {/* 抢单运行时参数（替代 buyer_config.py 硬编码） */}
      <Card title="抢单运行时参数" style={{ marginBottom: 24 }}>
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 16 }}>
          控制自动抢单流程的细节参数。修改后保存即可生效，无需重启服务。
        </Paragraph>
        <Row gutter={24}>
          <Col span={8}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}><strong>点击重试次数</strong></div>
              <InputNumber
                min={0}
                max={10}
                value={config.buyer.click_retry_times}
                onChange={(v) => update({ buyer: { ...config.buyer, click_retry_times: v ?? 0 } })}
                style={{ width: '100%' }}
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                点击"立即购买"按钮失败时的重试次数
              </Paragraph>
            </div>
          </Col>
          <Col span={8}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}><strong>点击重试间隔（秒）</strong></div>
              <InputNumber
                min={0}
                max={10}
                step={0.1}
                value={config.buyer.click_retry_interval}
                onChange={(v) => update({ buyer: { ...config.buyer, click_retry_interval: v ?? 0 } })}
                style={{ width: '100%' }}
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                两次点击之间的退避秒数
              </Paragraph>
            </div>
          </Col>
          <Col span={8}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}><strong>确认按钮超时（秒）</strong></div>
              <InputNumber
                min={1}
                max={60}
                value={config.buyer.confirm_button_timeout}
                onChange={(v) => update({ buyer: { ...config.buyer, confirm_button_timeout: v ?? 10 } })}
                style={{ width: '100%' }}
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                等待"提交订单"按钮出现的超时
              </Paragraph>
            </div>
          </Col>
          <Col span={8}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}><strong>价格容差</strong></div>
              <InputNumber
                min={0}
                max={1}
                step={0.01}
                value={config.buyer.price_tolerance}
                onChange={(v) => update({ buyer: { ...config.buyer, price_tolerance: v ?? 0 } })}
                style={{ width: '100%' }}
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                拍下价格相对预期价格的允许偏差（0.05=5%）
              </Paragraph>
            </div>
          </Col>
          <Col span={8}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}><strong>两次落单最小间隔（秒）</strong></div>
              <InputNumber
                min={0}
                max={3600}
                value={config.buyer.min_interval_between_orders}
                onChange={(v) => update({ buyer: { ...config.buyer, min_interval_between_orders: v ?? 0 } })}
                style={{ width: '100%' }}
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                防手抖：两次落单间的最小间隔，0=不限制
              </Paragraph>
            </div>
          </Col>
          <Col span={8}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}><strong>人工接管超时（分钟）</strong></div>
              <InputNumber
                min={1}
                max={120}
                value={config.buyer.takeover_timeout_min}
                onChange={(v) => update({ buyer: { ...config.buyer, takeover_timeout_min: v ?? 30 } })}
                style={{ width: '100%' }}
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                与闲鱼订单关闭时间对齐，超时未接管则订单流转到下一状态
              </Paragraph>
            </div>
          </Col>
        </Row>
      </Card>

      {/* 账号轮换调度参数（替代 account_rotator.py 硬编码） */}
      <Card title="账号轮换调度" style={{ marginBottom: 24 }}>
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 16 }}>
          多账号轮换调度器的冷却与失败阈值。触发风控后账号进入冷却，连续失败超阈值则自动禁用。
          修改后保存即生效（已创建的调度器实例会在下次启动时读取新值）。
        </Paragraph>
        <Row gutter={24}>
          <Col span={12}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}><strong>冷却时间（秒）</strong></div>
              <InputNumber
                min={60}
                max={86400}
                value={config.account_rotator.cooldown_sec}
                onChange={(v) => update({ account_rotator: { ...config.account_rotator, cooldown_sec: v ?? 1800 } })}
                style={{ width: '100%' }}
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                触发风控后的冷却秒数（默认 1800=30 分钟），冷却结束后自动恢复
              </Paragraph>
            </div>
          </Col>
          <Col span={12}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}><strong>连续失败阈值</strong></div>
              <InputNumber
                min={1}
                max={50}
                value={config.account_rotator.fail_threshold}
                onChange={(v) => update({ account_rotator: { ...config.account_rotator, fail_threshold: v ?? 5 } })}
                style={{ width: '100%' }}
              />
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                连续失败次数超过此值自动禁用账号（默认 5），需人工介入恢复
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

      <DiffPreviewModal
        open={diffModalOpen}
        diffChanges={diffChanges}
        loading={saving}
        onCancel={() => setDiffModalOpen(false)}
        onConfirm={handleConfirmSave}
      />
    </div>
  )
}
