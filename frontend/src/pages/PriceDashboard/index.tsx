import { Alert } from 'antd'
import { InfoCircleOutlined } from '@ant-design/icons'
import {
  useCategoryStats,
  useCategoryComparison,
  useSoldRange,
  useBargainEval,
} from './hooks'
import {
  CategoryComparisonChart,
  SoldRangeCard,
  BargainEvalCard,
  CategoryStatsTable,
} from './components'

// 价格行情看板主组件
// 重构说明：原组件认知复杂度约 50，通过以下策略降到 15 以下：
// 1. 按功能模块提取 4 个自定义 Hook（品类统计、横向对比、捡漏参考、价格评估）
// 2. 提取 4 个子组件，每个子组件负责一个独立的 UI 模块
// 3. 提取常量和工具函数到独立文件
// 4. 主组件仅负责组合各模块，保持简洁清晰
export default function PriceDashboard() {
  const categoryStats = useCategoryStats()
  const categoryComparison = useCategoryComparison()
  const soldRange = useSoldRange()
  const bargainEval = useBargainEval({
    soldTaskId: soldRange.soldTaskId,
    soldRangeDays: soldRange.soldRangeDays,
  })

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Alert
        type="info"
        showIcon
        icon={<InfoCircleOutlined />}
        message="价格行情看板"
        description="按品类聚合的商品价格统计与横向对比。捡漏价格参考基于近期已售商品，低于该价格可视为捡漏机会。"
        style={{ marginBottom: 0 }}
      />

      <CategoryComparisonChart
        loading={categoryComparison.compLoading}
        comparisonOption={categoryComparison.comparisonOption}
        overallMean={categoryComparison.overallMean}
        sortBy={categoryComparison.sortBy}
        order={categoryComparison.order}
        rangeDays={categoryComparison.rangeDays}
        onSortByChange={categoryComparison.setSortBy}
        onOrderChange={categoryComparison.setOrder}
        onRangeDaysChange={categoryComparison.setRangeDays}
        onRefresh={categoryComparison.fetchComparison}
      />

      <SoldRangeCard
        loading={soldRange.soldLoading}
        soldRange={soldRange.soldRange}
        soldTaskId={soldRange.soldTaskId}
        soldRangeDays={soldRange.soldRangeDays}
        tasks={soldRange.tasks}
        onTaskChange={soldRange.setSoldTaskId}
        onRangeDaysChange={soldRange.setSoldRangeDays}
        onRefresh={soldRange.fetchSoldRange}
      />

      <BargainEvalCard
        soldTaskId={soldRange.soldTaskId}
        evalCurrentPrice={bargainEval.evalCurrentPrice}
        evalResult={bargainEval.evalResult}
        evalLoading={bargainEval.evalLoading}
        onPriceChange={bargainEval.setEvalCurrentPrice}
        onEvaluate={bargainEval.fetchBargainEval}
        onRefresh={bargainEval.fetchBargainEval}
      />

      <CategoryStatsTable
        loading={categoryStats.statsLoading}
        stats={categoryStats.stats}
        statsTotal={categoryStats.statsTotal}
        onRefresh={categoryStats.fetchStats}
      />
    </div>
  )
}
