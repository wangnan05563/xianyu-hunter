// frontend/src/mobile/pages/Evaluations/index.tsx
import { Card, Select, Tag, Spin, Empty, Progress, App } from 'antd'
import { useEffect, useState, useCallback } from 'react'
import { evalApi } from '../../../api'
import type { EvalItem } from '../../../api/types'
import { RISK_LEVEL_CONFIG } from '../../../constants/riskLevels'
import { extractApiError } from '../../../utils/apiError'
import PullToRefresh from '../../components/PullToRefresh'

// 风险等级 Tag 颜色映射：low/medium/high 对应绿/橙/红
// 未知等级用默认灰色，避免异常数据导致颜色缺失
function getRiskColor(risk: string): string {
  return RISK_LEVEL_CONFIG[risk]?.color ?? 'default'
}

function getRiskLabel(risk: string): string {
  return RISK_LEVEL_CONFIG[risk]?.label ?? risk
}

// 时间本地化：后端返回 ISO 字符串，移动端按本地时区展示更直观
function formatLocalTime(raw?: string): string | null {
  if (!raw) return null
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString('zh-CN', { hour12: false })
}

// 状态筛选下拉项：与后端 result_category 取值严格对齐
// 全部 = undefined（不传该参数），其他值传给后端做精确过滤
type FilterCategory = 'auto' | 'pass' | 'fail' | 'insufficient' | undefined

// 类型守卫：收窄 FilterCategory 到后端接受的 4 种值，排除 'all' 和 undefined
// 定义在模块级避免每次渲染重建
const isResultCategory = (v: string): v is 'auto' | 'pass' | 'fail' | 'insufficient' =>
  ['auto', 'pass', 'fail', 'insufficient'].includes(v)

const FILTER_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'auto', label: '可抢' },
  { value: 'pass', label: '通过' },
  { value: 'fail', label: '驳回' },
  { value: 'insufficient', label: '数据不足' },
]

export default function MobileEvaluations() {
  const { message } = App.useApp()
  const [evals, setEvals] = useState<EvalItem[]>([])
  const [loading, setLoading] = useState(true)
  // 内部用 'all' 表示全部，请求时转换为 undefined
  const [filterValue, setFilterValue] = useState<string>('all')

  const fetchEvals = useCallback(async () => {
    // 'all' 不传给后端，让接口返回所有分类
    const resultCategory = isResultCategory(filterValue) ? filterValue : undefined
    try {
      const data = await evalApi.list({ limit: 50, result_category: resultCategory })
      setEvals(data.items)
    } catch (e) {
      // 弱网下保留已有数据，仅提示
      message.error(extractApiError(e, '加载评估列表失败'), 3)
    } finally {
      setLoading(false)
    }
  }, [filterValue, message])

  useEffect(() => { fetchEvals() }, [fetchEvals])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin />
      </div>
    )
  }

  return (
    <PullToRefresh onRefresh={fetchEvals}>
      <Select
        value={filterValue}
        style={{ width: '100%', marginBottom: 12 }}
        onChange={(v: string) => setFilterValue(v)}
        options={FILTER_OPTIONS}
      />
      {evals.length === 0 ? (
        <Empty description="暂无评估记录" />
      ) : (
        evals.map((item) => {
          const title = item.payload.item_title || item.item_id
          const price = item.payload.item_price
          const score = item.payload.score
          const risk = item.payload.risk_level
          const createdAt = formatLocalTime(item.created_at)
          const handleClick = () => message.info('请在桌面端查看详情')
          return (
            <Card
              key={`${item.item_id}-${item.created_at}`}
              className="m-eval-card"
              size="small"
              style={{ marginBottom: 12 }}
              onClick={handleClick}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  handleClick()
                }
              }}
            >
              <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                {/* 评分圆环：左固定宽，避免长标题挤压进度环 */}
                <div style={{ flexShrink: 0 }}>
                  <Progress
                    type="circle"
                    percent={score}
                    size={48}
                    format={(p) => `${p ?? 0}`}
                  />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontWeight: 600,
                    fontSize: 14,
                    marginBottom: 4,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                  }}>
                    {title}
                  </div>
                  {typeof price === 'number' && (
                    <div style={{ fontSize: 15, color: '#E20613', fontWeight: 600, marginBottom: 4 }}>
                      ¥{price}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 4 }}>
                    <Tag color={getRiskColor(risk)}>{getRiskLabel(risk)}</Tag>
                    {item.condition_label && <Tag color="blue">{item.condition_label}</Tag>}
                    {item.payload.is_sold && <Tag color="red">已售</Tag>}
                  </div>
                  {createdAt && (
                    <div style={{ fontSize: 12, color: '#999' }}>{createdAt}</div>
                  )}
                </div>
              </div>
            </Card>
          )
        })
      )}
    </PullToRefresh>
  )
}
