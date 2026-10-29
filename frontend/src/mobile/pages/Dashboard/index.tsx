import { Card, Spin, Tag } from 'antd'
import {
  FileSearchOutlined, DownloadOutlined, RobotOutlined, WarningOutlined,
  NotificationOutlined, DollarOutlined, DeleteOutlined, LineChartOutlined,
  SafetyCertificateOutlined, AimOutlined, SearchOutlined, ApiOutlined,
  HistoryOutlined, DatabaseOutlined, CloudDownloadOutlined, InfoCircleOutlined,
  ShoppingOutlined, AuditOutlined, FieldTimeOutlined, SecurityScanOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { statsApi } from '../../../api'
import type { TodayAlert, StatsOverview } from '../../../api/types'
import PullToRefresh from '../../components/PullToRefresh'
import FetchFailedHint from '../../../components/FetchFailedHint'

// 工具入口：P0/P1 页面快捷导航
// 后 4 条（商品/评估/时间线/反爬）在 routes.tsx 里一直有路由但没有任何入口，
// 属于「有页面没门」的死路由（FR-G-3）——补到这里才对得上「移动端可用」的口径
const TOOL_ENTRIES = [
  { key: 'logs', label: '实时日志', icon: <FileSearchOutlined />, path: '/m/logs/' },
  { key: 'market', label: '价格行情', icon: <LineChartOutlined />, path: '/m/market/' },
  { key: 'export', label: '数据导出', icon: <DownloadOutlined />, path: '/m/export/' },
  { key: 'error-logs', label: '错误日志', icon: <WarningOutlined />, path: '/m/error-logs/' },
  { key: 'notifier', label: '通知渠道', icon: <NotificationOutlined />, path: '/m/notifier-channels/' },
  { key: 'price', label: '价格策略', icon: <DollarOutlined />, path: '/m/price-strategy/' },
  { key: 'cleanup', label: '系统清理', icon: <DeleteOutlined />, path: '/m/cleanup/' },
  { key: 'chatbot-cfg', label: '客服配置', icon: <RobotOutlined />, path: '/m/chatbot-config/' },
  { key: 'items', label: '商品查询', icon: <ShoppingOutlined />, path: '/m/items/' },
  { key: 'evaluations', label: '评估记录', icon: <AuditOutlined />, path: '/m/evaluations/' },
  { key: 'timeline', label: '事件时间线', icon: <FieldTimeOutlined />, path: '/m/timeline/' },
  { key: 'anticrawl', label: '反爬状态', icon: <SecurityScanOutlined />, path: '/m/anticrawl/' },
] as const

// 配置入口：P2 高级配置页面
const CONFIG_ENTRIES = [
  { key: 'eval-rules', label: '评估规则', icon: <SafetyCertificateOutlined />, path: '/m/eval-rules/' },
  { key: 'buy-config', label: '抢单策略', icon: <AimOutlined />, path: '/m/buy-config/' },
  { key: 'search-config', label: '搜索参数', icon: <SearchOutlined />, path: '/m/search-config/' },
  { key: 'ai-config', label: 'AI 服务', icon: <ApiOutlined />, path: '/m/ai-config/' },
  { key: 'version', label: '配置版本', icon: <HistoryOutlined />, path: '/m/version-manager/' },
  { key: 'db-admin', label: '数据库', icon: <DatabaseOutlined />, path: '/m/db-admin/' },
  { key: 'batch-refresh', label: '批量采集', icon: <CloudDownloadOutlined />, path: '/m/batch-refresh/' },
  { key: 'about', label: '关于', icon: <InfoCircleOutlined />, path: '/m/about/' },
] as const

/** KPI 星级：5=达标、3=及格、1=偏低；数据不可用返回 0（不给「正常」的错觉） */
function star(v: number | undefined, isGood: (n: number) => boolean, isOk: (n: number) => boolean): number {
  if (v == null) return 0
  if (isGood(v)) return 5
  if (isOk(v)) return 3
  return 1
}

/** 通知失败星级：无数据 0 星；0 条失败 5 星；其余 1 星（用 if 收敛，避免嵌套三元） */
function notifyStar(v: number | undefined): number {
  if (v == null) return 0
  return v === 0 ? 5 : 1
}

// 移动端仪表盘：KPI 星级卡片 + 今日告警摘要 + 工具/配置入口
// KPI 口径（FR-G-1）：一律取 /api/stats 的真实字段，不再用 tasks.total 冒充商品数、
// 用 evaluation_count 冒充「评估通过」、用 orders.failed 冒充「通知失败」
export default function MobileDashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState<StatsOverview | null>(null)
  const [todayAlert, setTodayAlert] = useState<TodayAlert | null>(null)
  // 两个数据源各自记录失败：任一失败都不能把另一份数据抹掉，也不能显示成 0
  const [ovFailed, setOvFailed] = useState(false)
  const [alertFailed, setAlertFailed] = useState(false)

  const fetchData = useCallback(async () => {
    const [ovRes, alertRes] = await Promise.allSettled([
      statsApi.overview(),
      statsApi.today(),
    ])
    if (ovRes.status === 'fulfilled') {
      setOverview(ovRes.value)
      setOvFailed(false)
    } else {
      // 弱网/后端故障：保留上一次数据，但显式声明失败，卡片数字改显示 —
      setOvFailed(true)
      console.error('MobileDashboard overview failed:', ovRes.reason)
    }
    if (alertRes.status === 'fulfilled') {
      setTodayAlert(alertRes.value)
      setAlertFailed(false)
    } else {
      setAlertFailed(true)
      console.error('MobileDashboard today failed:', alertRes.reason)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    void fetchData()
  }, [fetchData])

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
  }

  const m = overview?.metrics
  // 数字可用性判定：请求失败 或 后端未下发 metrics 块时，一律显示 —
  const num = (v: number | undefined | null, showable: boolean) => (showable && v != null ? v : undefined)
  const itemsDiscovered = num(m?.items_discovered, !ovFailed)
  const evalPass = num(m?.eval_pass, !ovFailed)
  const orderSucceeded = num(overview?.orders.succeeded, !ovFailed)
  const notifyFailed = num(m?.notify_failed, !ovFailed)
  // 评估通过率：用同一份 metrics 现算，避免「通过数」与「总次数」分属两套口径
  const evalTotal = overview?.evaluation_count ?? 0
  const kpis: Array<{ label: string; value?: number; sub?: string; star: number }> = [
    {
      label: '发现商品',
      value: itemsDiscovered,
      sub: '累计入库商品数（与桌面 KPI 同源）',
      star: star(itemsDiscovered, (v) => v > 100, (v) => v > 20),
    },
    {
      label: '评估通过',
      value: evalPass,
      sub: evalPass != null && evalTotal > 0 ? `共 ${evalTotal} 条评估记录` : undefined,
      star: star(evalPass, (v) => v > 10, (v) => v > 0),
    },
    {
      label: '成功抢单',
      value: orderSucceeded,
      sub: ovFailed || !overview ? undefined : `失败 ${overview.orders.failed} 单`,
      star: star(orderSucceeded, (v) => v > 5, (v) => v > 0),
    },
    {
      label: '通知失败',
      value: notifyFailed,
      sub: notifyFailed === 0 ? '推送全部成功' : undefined,
      star: notifyStar(notifyFailed),
    },
  ]

  return (
    <PullToRefresh onRefresh={fetchData}>
      {/* KPI 星级卡片（单列） */}
      {ovFailed && (
        <FetchFailedHint source="统计接口（/api/stats）" onRetry={() => void fetchData()} />
      )}
      {kpis.map((kpi) => (
        <Card key={kpi.label} className="m-kpi-card" size="small">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 13, color: '#999' }}>
                {kpi.label}
                {kpi.value == null && ovFailed ? '（统计接口失败）' : ''}
              </div>
              <div
                style={{
                  fontSize: 28,
                  fontFamily: "'Cormorant Garamond', Georgia, serif",
                  fontWeight: 600,
                  color: '#E20613',
                  letterSpacing: '-0.5px',
                }}
              >
                {kpi.value ?? '—'}
              </div>
              {kpi.sub && <div style={{ fontSize: 11, color: '#bbb' }}>{kpi.sub}</div>}
            </div>
            {/* 星级评定：金色 ★ 表示达成等级；数据不可用时不给星（不给「正常」的错觉） */}
            <div style={{ color: '#C9A961', fontSize: 16 }}>
              {'★'.repeat(kpi.star)}
              <span style={{ color: '#d9d9d9' }}>{'★'.repeat(5 - kpi.star)}</span>
            </div>
          </div>
        </Card>
      ))}

      {/* 今日告警摘要 */}
      {(todayAlert || alertFailed) && (
        <Card title="今日告警" size="small" style={{ marginTop: 12 }}>
          {alertFailed ? (
            <FetchFailedHint source="今日告警" onRetry={() => void fetchData()} />
          ) : (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Tag color="red">失败 {todayAlert?.alerts.counts.failed}</Tag>
              <Tag color="orange">超时 {todayAlert?.alerts.counts.timeout}</Tag>
              <Tag color="purple">低分 {todayAlert?.alerts.counts.low_eval}</Tag>
            </div>
          )}
        </Card>
      )}

      {/* 工具入口：P0/P1 页面快捷导航（4 列网格） */}
      <Card title="工具" size="small" style={{ marginTop: 12 }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12,
          }}
        >
          {TOOL_ENTRIES.map((entry) => (
            <button
              key={entry.key}
              type="button"
              onClick={() => navigate(entry.path)}
              style={{
                background: 'none',
                border: 'none',
                padding: '8px 4px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 4,
                color: 'inherit',
                font: 'inherit',
              }}
            >
              <span style={{ fontSize: 22, color: '#E20613' }}>{entry.icon}</span>
              <span style={{ fontSize: 11 }}>{entry.label}</span>
            </button>
          ))}
        </div>
      </Card>

      {/* 配置入口：P2 高级配置页面（4 列网格） */}
      <Card title="配置与系统" size="small" style={{ marginTop: 12 }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12,
          }}
        >
          {CONFIG_ENTRIES.map((entry) => (
            <button
              key={entry.key}
              type="button"
              onClick={() => navigate(entry.path)}
              style={{
                background: 'none',
                border: 'none',
                padding: '8px 4px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 4,
                color: 'inherit',
                font: 'inherit',
              }}
            >
              <span style={{ fontSize: 22, color: '#E20613' }}>{entry.icon}</span>
              <span style={{ fontSize: 11 }}>{entry.label}</span>
            </button>
          ))}
        </div>
      </Card>
    </PullToRefresh>
  )
}
