import { Tooltip } from 'antd'
import {
  RightOutlined,
  HeatMapOutlined,
  PieChartOutlined,
  BarChartOutlined,
  AimOutlined,
  CalculatorOutlined,
} from '@ant-design/icons'

interface CollapsibleRailProps {
  /** 点击展开面板（主按钮与任意图标均触发） */
  readonly onExpand: () => void
}

// 右侧分析面板折叠态的窄竖条
// 为什么独立组件：折叠态的布局与展开态完全不同（纵向图标条 vs 横向 Card 列），
// 抽离后 index.tsx 可按 panelCollapsed 条件渲染，互不干扰
const MODULES = [
  { key: 'heatmap', label: '评估分布热力图', Icon: HeatMapOutlined },
  { key: 'result', label: '结果分析', Icon: PieChartOutlined },
  { key: 'score', label: '分数分布', Icon: BarChartOutlined },
  { key: 'suggest', label: '阈值建议', Icon: AimOutlined },
  { key: 'calc', label: '阈值通过率计算器', Icon: CalculatorOutlined },
] as const

export default function CollapsibleRail({ onExpand }: CollapsibleRailProps) {
  return (
    <div
      style={{
        height: '100%',
        minHeight: 480,
        background: 'var(--xh-bg-code)',
        borderLeft: '1px solid var(--xh-border-secondary)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        paddingTop: 12,
        paddingBottom: 12,
      }}
    >
      {/* 主展开按钮：纵向排列图标+文字，明确示意可展开 */}
      <Tooltip title="展开分析面板">
        <button
          onClick={onExpand}
          style={{
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
            padding: '4px 0',
            color: 'var(--xh-text-secondary)',
          }}
        >
          <RightOutlined style={{ fontSize: 16 }} />
          <span style={{ fontSize: 11, writingMode: 'vertical-rl' }}>展开</span>
        </button>
      </Tooltip>

      {/* 分隔线 */}
      <div style={{ width: 20, height: 1, background: 'var(--xh-border-secondary)', margin: '12px 0' }} />

      {/* 模块图标纵列：点击任一即展开面板 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, alignItems: 'center' }}>
        {MODULES.map(({ key, label, Icon }) => (
          <Tooltip key={key} title={label}>
            <button
              onClick={onExpand}
              style={{
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                padding: 6,
                borderRadius: 4,
                color: 'var(--xh-text-tertiary)',
                transition: 'background 0.15s, color 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(24,144,255,0.08)'
                e.currentTarget.style.color = '#1890ff'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = 'var(--xh-text-tertiary)'
              }}
            >
              <Icon style={{ fontSize: 16 }} />
            </button>
          </Tooltip>
        ))}
      </div>
    </div>
  )
}
