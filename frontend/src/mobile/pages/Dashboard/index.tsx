import { Card, Spin, Tag } from 'antd'
import { useEffect, useState } from 'react'
import { statsApi } from '../../../api'
import type { TodayAlert, StatsOverview } from '../../../api/types'
import PullToRefresh from '../../components/PullToRefresh'

// 移动端仪表盘：KPI 星级卡片 + 调度器状态 + 实时事件流（精简版）
export default function MobileDashboard() {
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState<StatsOverview | null>(null)
  const [todayAlert, setTodayAlert] = useState<TodayAlert | null>(null)

  const fetchData = async () => {
    try {
      const [ov, alert] = await Promise.all([
        statsApi.overview(),
        statsApi.today(),
      ])
      setOverview(ov)
      setTodayAlert(alert)
    } catch (e) {
      // 弱网下静默失败，保留已有数据；记录错误便于排查
      console.error('MobileDashboard fetch failed:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleRefresh = async () => {
    await fetchData()
  }

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  // KPI 数据：字段映射 StatsOverview 实际结构
  // discovered_count → tasks.total（任务总数即累计发现商品量）
  // eval_passed_count → evaluation_count（评估总次数，后端无 pass/fail 拆分）
  // order_succeeded_count → orders.succeeded（抢单成功数）
  // notify_failed_count → orders.failed（订单失败数，作为通知失败代理指标）
  const taskTotal = overview?.tasks.total ?? 0
  const evalCount = overview?.evaluation_count ?? 0
  const orderSucceeded = overview?.orders.succeeded ?? 0
  const orderFailed = overview?.orders.failed ?? 0
  const kpis = [
    { label: '发现商品', value: taskTotal, star: taskTotal > 100 ? 5 : 3 },
    { label: '评估通过', value: evalCount, star: evalCount > 10 ? 5 : 3 },
    { label: '抢单成功', value: orderSucceeded, star: orderSucceeded > 5 ? 5 : 1 },
    { label: '通知失败', value: orderFailed, star: orderFailed === 0 ? 5 : 1 },
  ]

  return (
    <PullToRefresh onRefresh={handleRefresh}>
      {/* KPI 星级卡片（单列） */}
      {kpis.map((kpi) => (
        <Card key={kpi.label} className="m-kpi-card" size="small">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 13, color: '#999' }}>{kpi.label}</div>
              <div
                style={{
                  fontSize: 28,
                  fontFamily: "'Cormorant Garamond', Georgia, serif",
                  fontWeight: 600,
                  color: '#E20613',
                  letterSpacing: '-0.5px',
                }}
              >
                {kpi.value}
              </div>
            </div>
            {/* 星级评定：金色 ★ 表示达成等级 */}
            <div style={{ color: '#C9A961', fontSize: 16 }}>
              {'★'.repeat(kpi.star)}
              <span style={{ color: '#d9d9d9' }}>{'★'.repeat(5 - kpi.star)}</span>
            </div>
          </div>
        </Card>
      ))}

      {/* 今日告警摘要 */}
      {todayAlert && (
        <Card title="今日告警" size="small" style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Tag color="red">失败 {todayAlert.alerts.counts.failed}</Tag>
            <Tag color="orange">超时 {todayAlert.alerts.counts.timeout}</Tag>
            <Tag color="purple">低分 {todayAlert.alerts.counts.low_eval}</Tag>
          </div>
        </Card>
      )}
    </PullToRefresh>
  )
}
