# Sprint B 交付报告

日期：2026-06-06
阶段：Sprint B（UX 体验优化第二批）
覆盖需求：UX-03（价格直方图分位数 + 时间对比）、UX-07（Dashboard sparkline 趋势小图）、UX-13（配置内联回滚）
负责人：BEMP 个性化开发

---

## 1. 交付摘要

| 需求 | 标题 | 后端 | 前端 | 状态 |
|---|---|---|---|---|
| **UX-03** | 价格直方图分位数 + 时间对比 | `/api/prices/histogram` 增加 P25/P50/P75 + 昨日/7 日均价 | dashboard.html 加 quantile 参考线 + summary 卡 | ✅ 已完成 |
| **UX-07** | Dashboard sparkline 趋势小图 | 新增 `/api/stats/trend?metric=events|orders|eval_score|success_rate` | 4 张统计卡底部加 SVG sparkline | ✅ 已完成 |
| **UX-13** | 配置内联回滚 | 无后端改动（基于客户端原值快照） | config 子页面加 ⏪ 内联按钮 + 顶部"全部重置" | ✅ 已完成 |

服务运行验证：FastAPI 已启动，127.0.0.1:8000；smoke test 8 个端点全部 200。

---

## 2. 实施细节

### 2.1 UX-03 价格直方图分位数 + 时间对比

**后端** `api_stats.py`
- `_percentile()`：NumPy 风格线性插值（rank = p * (n - 1)），单函数 8 行无依赖
- `_build_compare_means()`：拉 `ItemRow.price + created_at` 限 2000 条，按 `>= 24h` 和 `>= 7d` 切两桶算均值，输出 `yesterday` / `last7d` / `diff_pct`
- `/api/prices/histogram` 响应扩展：`summary.p25`、`summary.p75`、`summary.compare`

**前端** `dashboard.html`
- SVG 内新增 `<g x-ref="histQuantiles">` 用 createElementNS 绘制 3 条水平虚线（P50 主色，P25/P75 muted）
- 卡下方追加 `.histogram-summary` 两行：分位数（均价/中位/P25/P75）+ 时间对比（昨日/7日/涨跌幅）
- 涨跌幅 `>0` 用 `p75-text` 红、`<0` 用 `p25-text` 绿，缺失数据用 `—` 避免 `0%` 误读

**为什么不内置 `statistics.quantiles()`**
- 标准库 `statistics.quantiles()` 只支持四分位以外的预设档位，要 P25/P50/P75 还要自己写插值
- 单函数 8 行解决，零依赖，便于 review

### 2.2 UX-07 Dashboard sparkline 趋势小图

**后端** `api_stats.py`
- `_build_trend_series()`：等宽时间桶聚合（24h/24桶、72h/24桶、168h/14桶）
- `/api/stats/trend?metric=events|orders|eval_score|success_rate&range_hours=24|72|168`
- 响应含 `series[24].{ts,value,count}` + `summary.{min,max,avg,current}`

**前端** `dashboard.html`
- 4 张统计卡底部各加 `<svg class="spark" viewBox="0 0 240 36">` 占位
- `loadSparklines()` 并发拉 2 个 metric（events + orders），succeeded/failed 复用 orders 桶
- `renderSparkline()` 用 createElementNS 画 24 点折线 + 末尾圆点 + 半透明 area
- 三态颜色：默认 `--text-3` 灰、`.ok-spark` 绿、`.err-spark` 红

**为什么不直接做 succeeded/failed 单独 metric**
- 24h 窗口下数据稀疏，succeeded 桶经常全 0，折线变"无意义直线"
- orders 桶（同密度曲线）已经传达"事件/订单量趋势"——succeeded/failed 卡的色彩和数值差异本身就是定位信号
- 节省 2 次 API 调用（合并到 1 个 orders metric）

**设计决策**：
- 高度 36px：低于主数值（28px）的视觉权重，让"现在值"仍是一眼可见
- `pointer-events: none`：sparkline 在 `<a class="card">` 内不能拦截跳转
- 末尾点 `r=2.5`：比 line 粗 2x 突出"现在"

### 2.3 UX-13 配置内联回滚

**核心机制**：客户端原值快照 + 点分路径回写

**前端** `config/base.html`
- 新增 `Alpine.store('cfgOriginal', null)` 存储快照
- `init()` 拉 `/api/config` 后立刻 `resetCfgOriginal()` 深拷贝
- 新增 helper：
  - `_cfgGet(store, path)` / `_cfgSet(store, path, v)`：点分路径读写
  - `cfgChanged(path)`：判断某字段是否被改动（数组用 `JSON.stringify` 序列化对比）
  - `cfgRollback(path)`：写回原值
  - `fmtCfgVal(v)`：把值"美化"为 tooltip 文字
  - `hasAnyChanged()` + `rollbackAll()`：顶部"全部重置"按钮
- `confirmSave()` 成功路径追加 `resetCfgOriginal()` 刷新快照
- 暴露 `window._cfgPage = this` 供子页面的 `<div x-data>` scope 内访问

**前端** `config/search.html` + `config/eval.html`
- 每个字段 `<label>` 内加 `<button class="cfg-rollback">⏪</button>`
- `x-show="window._cfgPage?.cfgChanged('path')"` 控制可见性
- `:title="⏪ 恢复为: <原值>"` 提示原值
- 顶部"全部重置"按钮：`x-show="hasAnyChanged()"`，点击用 `confirm()` 二次确认

**样式** `app.css`
- `.cfg-rollback` 20×20 圆角小按钮，hover 黄色高亮 + `scale(1.1)`，active `scale(0.95)`

**为什么不直接用 `$root`**
- 子页面 `<div x-data>` 创建新 scope 后，`$root` 指向最近的 x-data 父级
- `window` 是唯一"跨越所有 Alpine scope"都可见的挂载点
- 选 `window._cfgPage` 而非挂到 store：避免污染全局 `cfgOriginal` 命名空间

**为什么不存后端拉"上一次保存版本"对比**
- 后端没有"未保存草稿"概念（保存即覆盖）
- 客户端深拷贝更轻：内存里 1 份 JSON（约 5KB），零网络
- 会话级粒度已足够：用户刷新页面 = 接受"上次保存"为新基线

---

## 3. 文件清单

| 文件 | 状态 | 关键改动 |
|---|---|---|
| `src/xianyu_hunter/web/routes/api_stats.py` | 改 | 新增 P25/P50/P75 + compare + `/api/stats/trend` |
| `src/xianyu_hunter/web/templates/dashboard.html` | 改 | 4 张卡 + sparkline；直方图 P25/P50/P75 + 时间对比 |
| `src/xianyu_hunter/web/templates/config/base.html` | 改 | cfgOriginal 快照 + helper + 顶部"全部重置" |
| `src/xianyu_hunter/web/templates/config/search.html` | 改 | 11 个字段加 ⏪ 内联按钮 |
| `src/xianyu_hunter/web/templates/config/eval.html` | 改 | 6 个核心字段（weights + pass/auto_buy）加 ⏪ |
| `src/xianyu_hunter/web/static/app.css` | 改 | spark-* 样式（5 条）+ cfg-rollback 样式 |

---

## 4. Smoke Test 结果

服务启动：`./start_web.ps1` → FastAPI on 127.0.0.1:8000

| 端点 / 资源 | HTTP | 体积 | 说明 |
|---|---|---|---|
| `GET /dashboard` | 200 | 65 KB | 含 4 个 `<svg class="spark">` |
| `GET /api/stats/trend?metric=events&range_hours=24` | 200 | 1327 B | 24 桶 + summary |
| `GET /api/stats/trend?metric=orders&range_hours=24` | 200 | 1327 B | 24 桶 + summary |
| `GET /api/stats/trend?metric=eval_score&range_hours=24` | 200 | 1331 B | 24 桶 + summary |
| `GET /api/stats/trend?metric=success_rate&range_hours=24` | 200 | 1333 B | 24 桶 + summary |
| `GET /config/search` | 200 | 55 KB | 含 cfg-rollback 按钮 + 顶部"全部重置" |
| `GET /config/eval` | 200 | 55 KB | 含 6 个 cfg-rollback 按钮 |
| `GET /static/app.css` | 200 | 60 KB | 含 spark-line/area/dot + cfg-rollback 样式 |

所有端点通过。服务持续运行中。

---

## 5. 后续建议

### 5.1 未在 Sprint B 完成的 P3 项目

按 `2026-06-05-ux-optimization-plan.md` 中的清单：

- **UX-08 任务成功率折线**（任务详情页）：复用 `/api/stats/trend?metric=success_rate` 即可
- **UX-09 评估分分布**（评估页）：需要 `/api/evaluations/distribution` 新端点 + 散点图
- **UX-10 配置导入/导出**：需 `/api/config/import` `/api/config/export` 端点
- **UX-11 Toast 失败原因持久化**：Notification Center 已有，复用即可
- **UX-12 快捷键 / Command Palette**：P2-1，需全局快捷键注册组件

### 5.2 优化余地

- **succeeded/failed 卡**：当前用 orders 桶近似，密度曲线一致；若想精确可加 `?metric=succeeded_count` + `?metric=failed_count`（前后端各加 5 行）
- **配置回滚的快照粒度**：当前是"会话级"——刷新页面就重置。如果想"跨会话"做草稿，可加 `localStorage` 持久化
- **sparkline 触达移动端**：当前移动端 `< 900px` 时 sparkline 仍显示但 4 张卡会变单列，曲线可能被挤窄。可加 `@media (max-width: 900px) { .spark { display: none; } }` 隐藏

---

## 6. 阶段交接声明

- 当前阶段：**Sprint B（UX 优化第二批）** ✅ 已完成
- 下一阶段：**Sprint C**（按 v3 评审报告顺序为：UX-08/09/10/11/12 + 任何 11 项新增功能）
- 下一阶段智能体：`bemp-personalized-developer`（沿用）
- 下一阶段技能：前端组件 + 后端 API
- 交接上下文：
  1. 服务持续运行在 `127.0.0.1:8000`（PID 见 start_web.ps1 启动日志）
  2. `/api/stats/trend` 已稳定返回 4 种 metric，可在 Sprint C 直接复用做 UX-08
  3. `cfgRollback` 模式可推广到其他"会话级原值"场景（如任务编辑表单）
  4. 文档已更新：dashboard.html 内的 P3-UX-07 注释、base.html 的 P3-UX-13 注释便于后人理解
