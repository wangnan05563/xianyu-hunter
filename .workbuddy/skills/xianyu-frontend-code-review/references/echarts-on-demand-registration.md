# ECharts 按需注册完整性规范

> **复盘来源**：仪表盘"评估漏斗与命中率"图表不展示问题（2026-06-30）
> **根因**：`frontend/src/components/charts/EChart.tsx` 的 `echarts.use([...])` 遗漏 `FunnelChart`，而 `EvalFunnelCard.tsx` 使用 `type: 'funnel'`，导致 ECharts 静默渲染失败（canvas 不生成）
> **配套**：[xianyu-hunter-dev references/coding-standards.md §3.9](../../xianyu-hunter-dev/references/coding-standards.md)

---

## 1. 问题背景

### 1.1 ECharts 5 按需导入机制

ECharts 5 推荐按需导入以减小打包体积：

```ts
// 全量导入（不推荐，包体积大但无注册遗漏风险）
import * as echarts from 'echarts'

// 按需导入（推荐，但漏注册会静默失败）
import * as echarts from 'echarts/core'
import { BarChart, FunnelChart } from 'echarts/charts'
import { TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, FunnelChart, TooltipComponent, GridComponent, CanvasRenderer])
```

**关键特性**：未注册的 Chart 类型/Component 在使用时**不抛异常**，只在控制台输出 warn（如 `Component type not found: series.funnel`），canvas 节点不生成 → 静默失败。

### 1.2 本次故障现象

- 仪表盘"评估漏斗与命中率"卡片：漏斗图区域空白
- 同卡片内的 4 个 Statistic 指标（命中率/误报率/抢单成功率/端到端率）视觉上也不显示
- 浏览器控制台无显式报错（仅有 ECharts warn 容易被忽略）
- 后端 API `/api/stats/eval-funnel` 正常返回数据

### 1.3 误判风险

由于现象是"图表+指标都不展示"，容易误判为：
- ❌ 数据层问题（API 返回空）→ 陷入后端排查歧途
- ❌ 权限问题（用户无权查看）→ 排查 auth 中间件
- ❌ 渲染条件问题（`data.stages.length === 0`）→ 排查前端渲染逻辑

**正确排查方向**：静默失败 + 按需导入 → 优先排查按需注册完整性。

---

## 2. 检查点（ERC-*）

### ERC-01 使用点-注册点差集为空（Critical）

**规则**：所有 `type: 'xxx'` 使用点必须在 `echarts.use([...])` 有对应 Chart 类注册。

**审查方法**：

```
步骤 1：Grep 所有图表 type 使用点
  grep "type:\s*['\"]\(bar\|line\|funnel\|heatmap\|radar\|pie\|scatter\|gauge\|graph\|sankey\|tree\|treemap\|sunburst\|boxplot\|candlestick\|effectScatter\|lines\|map\|parallel\|pictorialBar\|themeRiver\|custom\)['\"]" frontend/src

步骤 2：读取 EChart.tsx 的 echarts.use([...]) 注册清单
  grep "echarts.use" frontend/src/components/charts/EChart.tsx

步骤 3：差集 = 使用点 type - 注册点 Chart 类
  type='funnel' 使用了 → 注册点是否有 FunnelChart？

步骤 4：差集非空 → 标记为 ERC-01 Critical
```

**type → Chart 类映射表**（ECharts 5 常用）：

| series.type | Chart 类 | 所在模块 |
|---|---|---|
| `bar` | `BarChart` | `echarts/charts` |
| `line` | `LineChart` | `echarts/charts` |
| `funnel` | `FunnelChart` | `echarts/charts` |
| `pie` | `PieChart` | `echarts/charts` |
| `scatter` | `ScatterChart` | `echarts/charts` |
| `heatmap` | `HeatmapChart` | `echarts/charts` |
| `radar` | `RadarChart` | `echarts/charts` |
| `graph` | `GraphChart` | `echarts/charts` |
| `tree` | `TreeChart` | `echarts/charts` |
| `treemap` | `TreemapChart` | `echarts/charts` |
| `sunburst` | `SunburstChart` | `echarts/charts` |
| `sankey` | `SankeyChart` | `echarts/charts` |
| `boxplot` | `BoxplotChart` | `echarts/charts` |
| `candlestick` | `CandlestickChart` | `echarts/charts` |
| `effectScatter` | `EffectScatterChart` | `echarts/charts` |
| `lines` | `LinesChart` | `echarts/charts` |
| `map` | `MapChart` | `echarts/charts` |
| `parallel` | `ParallelChart` | `echarts/charts` |
| `pictorialBar` | `PictorialBarChart` | `echarts/charts` |
| `themeRiver` | `ThemeRiverChart` | `echarts/charts` |
| `custom` | `CustomChart` | `echarts/charts` |
| `gauge` | `GaugeChart` | `echarts/charts` |

> **注意**：此映射表为参考，审查时以项目实际使用的 type 为准动态推导差集，不硬编码固定清单。

### ERC-02 集中注册（Critical）

**规则**：`echarts.use()` 只允许在 `components/charts/EChart.tsx` 调用一次，禁止各组件重复注册。

**反模式**：
```tsx
// ❌ 各组件自己注册（重复 + 维护困难）
// EvalFunnelCard.tsx
import * as echarts from 'echarts/core'
import { FunnelChart } from 'echarts/charts'
echarts.use([FunnelChart])

// PriceHistogramCard.tsx
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
echarts.use([BarChart])
```

**正确模式**：
```tsx
// ✅ 集中在 EChart.tsx 注册一次
// components/charts/EChart.tsx
import * as echarts from 'echarts/core'
import { BarChart, LineChart, FunnelChart, ... } from 'echarts/charts'
echarts.use([BarChart, LineChart, FunnelChart, ...])

// 业务组件只 import EChart 组件
// EvalFunnelCard.tsx
import EChart from '@/components/charts/EChart'
```

### ERC-03 修改后验证链（Critical）

**规则**：改 `EChart.tsx` 后必须跑完整验证链。

| 步骤 | 命令 / 动作 | 期望结果 |
|---|---|---|
| 1. 类型检查 | `cd frontend && npx tsc --noEmit` | 无报错 |
| 2. 构建 | `cd frontend && npm run build` | 成功，echarts-vendor chunk 体积合理变化（新增 Chart 类约 +200~300KB） |
| 3. 控制台 | 浏览器 devtools console（强刷 `Ctrl+Shift+R`） | 无 `Component type not found` warn |
| 4. DOM 验证 | `evaluate_script` 检测目标卡片内 `canvas` 节点 | canvas 存在且 width/height > 0 |
| 5. 数据验证 | `evaluate_script` 检测 `.ant-statistic-content-value` | 指标数值正常显示 |

**DOM 验证脚本示例**：
```js
() => {
  const cards = document.querySelectorAll('.ant-card')
  for (const c of cards) {
    const title = c.querySelector('.ant-card-head-title')
    if (title && title.textContent.includes('评估漏斗')) {
      return {
        canvasCount: c.querySelectorAll('canvas').length,
        canvasSize: Array.from(c.querySelectorAll('canvas')).map(cv => `${cv.width}x${cv.height}`),
        statValues: Array.from(c.querySelectorAll('.ant-statistic-content-value')).map(v => v.textContent.trim()),
      }
    }
  }
}
```

### ERC-04 静默失败排查优先级（Suggestion）

**规则**：图表/组件不渲染且无显式报错时，优先排查按需注册完整性。

**排查决策树**：

```
图表不渲染？
├── 有显式报错（TypeError/ReferenceError）→ 看错误信息直接修复
└── 无报错（静默失败）
    ├── 是否使用按需导入（echarts/core + echarts.use）？
    │   ├── 是 → 优先跑 ERC-01 差集法（注册遗漏最高概率）
    │   └── 否（全量导入）→ 跳过注册检查
    ├── 注册完整 → 检查渲染条件（data 是否为空 / stages.length === 0）
    ├── 数据正常 → 检查容器尺寸（height=0 导致不渲染）
    └── 尺寸正常 → 检查 CSS（display:none / z-index 覆盖）
```

---

## 3. 适用场景与不适用场景

### 适用场景

- ✅ ECharts 按需导入（`echarts/core` + `echarts.use`）架构
- ✅ 任何采用按需注册（tree-shakable）的第三方库（如 ant-design-vue 的 `app.use()`、ag-grid 的 `ModuleRegistry.registerModule`）
- ✅ 现象为"静默失败"——组件不渲染但不抛异常
- ✅ 新增图表/组件类型后首次集成
- ✅ SPA 重新构建后图表消失（构建配置变化导致注册丢失）

### 不适用场景

- ❌ 全量导入（`import * as echarts from 'echarts'`）——不存在注册遗漏问题
- ❌ 显式报错（TypeError/ReferenceError）——直接看错误信息追溯
- ❌ 数据层问题（API 返回空、字段不匹配）——走 SD-* / STQ-* 统计查询验证
- ❌ 样式/布局问题（canvas 渲染了但不可见）——走 CSS 审查
- ❌ 浏览器兼容性问题（特定浏览器不渲染）——走兼容性测试

---

## 4. 预防机制

### 4.1 CI 自动化检查（建议）

在 `frontend/package.json` 的 `scripts` 中加入检查脚本，对比使用点与注册点：

```bash
# 示例：pre-commit 钩子检查 ECharts 注册完整性
node scripts/check-echarts-registration.js
```

检查逻辑：Grep `type: 'xxx'` 使用点 → 与 `EChart.tsx` 的 `echarts.use` 注册清单对比 → 差集非空则报错。

### 4.2 Code Review 检查项

修改涉及以下文件时，必须检查 ERC-01~04：
- `components/charts/EChart.tsx`
- 任何使用 `<EChart>` 组件的页面
- 新增图表类型（series.type）

### 4.3 文档同步

新增图表类型时，在 [xianyu-hunter-dev references/coding-standards.md §3.9](../../xianyu-hunter-dev/references/coding-standards.md) 的"使用点清单"中同步记录。

---

## 5. 参考

- [ECharts 5 按需引入文档](https://echarts.apache.org/handbook/zh/basics/import)
- [xianyu-hunter-dev coding-standards.md §3.9](../../xianyu-hunter-dev/references/coding-standards.md) —— 图表组件按需注册规范
- 本次修复 PR：`EChart.tsx` 新增 `FunnelChart` 注册 + SPA 重新构建
