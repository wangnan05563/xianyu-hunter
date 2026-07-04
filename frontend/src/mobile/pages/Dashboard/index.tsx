import { Card, Spin, Tag } from 'antd'
import { useEffect, useState } from 'react'
import { statsApi } from '../../../api'
import type { TodayAlert } from '../../../api/types'
import PullToRefresh from '../../components/PullToRefresh'

// 移动端仪表盘：KPI 星级卡片 + 调度器状态 + 实时事件流（精简版）
export default function MobileDashboard() {
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState<any>(null)
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
      // 弱网下静默失败，保留已有数据
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

  // KPI 数据（从 overview 提取）
  const kpis = [
    { label: '发现商品', value: overview?.discovered_count ?? 0, star: overview?.discovered_count > 100 ? 5 : 3 },
    { label: '评估通过', value: overview?.eval_passed_count ?? 0, star: overview?.eval_pass_rate > 0.3 ? 5 : 3 },
    { label: '抢单成功', value: overview?.order_succeeded_count ?? 0, star: overview?.order_success_rate > 0.8 ? 5 : 1 },
    { label: '通知失败', value: overview?.notify_failed_count ?? 0, star: overview?.notify_failed_count === 0 ? 5 : 1 },
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
