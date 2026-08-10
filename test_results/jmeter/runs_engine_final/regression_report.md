# 性能回归压测报告

> 生成时间：2026-08-09 09:49:25 ｜ 模式：python_replay

## 1. 总览

| 阶段 | 请求数 | 断言错误数 | 错误率 | 真实缺陷(按规则) | p50 | p95 | p99 |
|------|------:|----------:|------:|----------------:|----:|----:|----:|
| reads | 3669 | 0 | 0.0% | 0 (0.0%) | 66.85 | 626.43 | 1275.72 |
| writes | 5848 | 0 | 0.0% | 0 (0.0%) | 354.15 | 764.58 | 1093.95 |

## 2. 关键端点（修复前后，可选）

| 端点 | 方法 | 当前错误率 | 当前缺陷率 | p50 | p95 | p99 |
|------|------|-----------|-----------|----:|----:|----:|
| 订单详情(P0-1) | GET | 0.0% | 0.0% | 41.26 | 250.51 | 376.98 |
| 商品批量(P0-3) | GET | 0.0% | 0.0% | 38.88 | 208.43 | 253.25 |
| 偏好UPSERT(P0-2) | - | (计划中未找到) | - | - | - | - |
| 维护状态(P1-1) | GET | 0.0% | 0.0% | 59.45 | 234.84 | 419.23 |
| 向量库状态(P1-6) | GET | 0.0% | 0.0% | 28.89 | 116.15 | 177.71 |

## 3. 全端点错误率 / P95

| 端点 | 方法 | path | 请求数 | 错误率 | 缺陷率 | P95(ms) |
|------|------|------|------:|------:|------:|------:|
| Cron示例 | GET | /api/cron/examples | 50 | 0.0% | 0.0% | 244.68 |
| DB表列表 | GET | /api/db-admin/tables | 50 | 0.0% | 0.0% | 465.01 |
| DB表结构 | GET | /api/db-admin/tables/${TABLE}/schema | 50 | 0.0% | 0.0% | 426.81 |
| DB表行 | GET | /api/db-admin/tables/${TABLE}/rows?limit=50 | 50 | 0.0% | 0.0% | 421.99 |
| Dashboard统计 | GET | /api/stats | 60 | 0.0% | 0.0% | 140.91 |
| Prompt列表 | GET | /api/prompts | 56 | 0.0% | 0.0% | 235.32 |
| 业务KPI | GET | /api/stats/business-kpi | 60 | 0.0% | 0.0% | 113.32 |
| 今日统计 | GET | /api/stats/today | 60 | 0.0% | 0.0% | 133.93 |
| 价格分类对比 | GET | /api/prices/category-comparison | 59 | 0.0% | 0.0% | 680.41 |
| 价格分类统计 | GET | /api/prices/category-stats | 59 | 0.0% | 0.0% | 546.15 |
| 价格直方图 | GET | /api/prices/histogram | 59 | 0.0% | 0.0% | 193.06 |
| 价格趋势 | GET | /api/stats/price-trend | 60 | 0.0% | 0.0% | 501.62 |
| 任务列表 | GET | /api/tasks | 59 | 0.0% | 0.0% | 225.03 |
| 任务详情 | GET | /api/tasks/${TASK_ID} | 59 | 0.0% | 0.0% | 359.44 |
| 任务运行记录 | GET | /api/tasks/${TASK_ID}/runs | 59 | 0.0% | 0.0% | 256.9 |
| 任务预检 | GET | /api/tasks/${TASK_ID}/precheck | 59 | 0.0% | 0.0% | 333.33 |
| 会话列表 | GET | /api/chatbot/sessions | 50 | 0.0% | 0.0% | 351.88 |
| 偏好 | GET | /api/preferences | 56 | 0.0% | 0.0% | 283.68 |
| 偏好UPSERT |  |  | 844 | 0.0% | 0.0% | 696.52 |
| 关于 | GET | /api/about | 56 | 0.0% | 0.0% | 163.18 |
| 创建会话 |  |  | 840 | 0.0% | 0.0% | 702.36 |
| 删除会话 |  |  | 836 | 100.0% | 0.0% | 604.03 |
| 卖家价格趋势 | GET | /api/stats/seller-price-trend | 60 | 0.0% | 0.0% | 207.94 |
| 参数计算器规则 | GET | /api/param-calculator/rules | 50 | 0.0% | 0.0% | 235.26 |
| 反爬健康 | GET | /api/anticrawl/health | 53 | 0.0% | 0.0% | 157.29 |
| 反爬指纹 | GET | /api/anticrawl/fingerprint | 53 | 0.0% | 0.0% | 141.16 |
| 反爬策略 | GET | /api/anticrawl/strategy | 53 | 0.0% | 0.0% | 1425.75 |
| 反爬频率统计 | GET | /api/anticrawl/freq/stats | 53 | 0.0% | 0.0% | 225.6 |
| 反馈统计 | GET | /api/evaluations/feedback/stats | 58 | 0.0% | 0.0% | 208.14 |
| 向量库状态 | GET | /api/vector-admin/status | 53 | 0.0% | 0.0% | 116.15 |
| 售出区间 | GET | /api/prices/sold-range | 59 | 0.0% | 0.0% | 667.67 |
| 商品批量 | GET | /api/items/batch | 59 | 0.0% | 0.0% | 208.43 |
| 商品摘要 | GET | /api/items/${ITEM_ID}/summary | 58 | 0.0% | 0.0% | 223.52 |
| 客服配置 | GET | /api/chatbot/config | 50 | 0.0% | 0.0% | 218.82 |
| 批量刷新历史 | GET | /api/batch-refresh/history | 50 | 0.0% | 0.0% | 446.18 |
| 批量刷新状态 | GET | /api/batch-refresh/status | 50 | 0.0% | 0.0% | 280.56 |
| 提交评估反馈 |  |  | 825 | 100.0% | 0.0% | 675.85 |
| 日志 | GET | /api/logs | 54 | 0.0% | 0.0% | 526.06 |
| 日志搜索 | GET | /api/logs/search | 53 | 0.0% | 0.0% | 1012.11 |
| 最新评估 | GET | /api/evaluations/latest/${ITEM_ID} | 58 | 0.0% | 0.0% | 223.33 |
| 未读计数 | GET | /api/notifications/unread_count | 54 | 0.0% | 0.0% | 323.65 |
| 检查更新 | GET | /api/about/check-update | 56 | 0.0% | 0.0% | 1703.48 |
| 模板 | GET | /api/templates | 56 | 0.0% | 0.0% | 243.24 |
| 清理缓存(dry_run) |  |  | 834 | 0.0% | 0.0% | 882.11 |
| 知识库版本 | GET | /api/kb/versions | 53 | 0.0% | 0.0% | 143.33 |
| 知识库状态 | GET | /api/kb/status | 53 | 0.0% | 0.0% | 164.0 |
| 砍价评估 | GET | /api/prices/bargain-eval | 59 | 0.0% | 0.0% | 370.64 |
| 维护状态 | GET | /api/maintenance/status | 50 | 0.0% | 0.0% | 234.84 |
| 自动采集统计 | GET | /api/evaluations/auto-collect-stats | 58 | 0.0% | 0.0% | 260.18 |
| 菜单 | GET | /api/menu | 56 | 0.0% | 0.0% | 162.64 |
| 订单列表 | GET | /api/orders | 59 | 0.0% | 0.0% | 243.8 |
| 订单详情 | GET | /api/orders/${ORDER_ID} | 59 | 0.0% | 0.0% | 250.51 |
| 评估分布 | GET | /api/evaluations/distribution | 58 | 0.0% | 0.0% | 176.83 |
| 评估列表 | GET | /api/evaluations | 58 | 0.0% | 0.0% | 174.81 |
| 评估卖家价格趋势 | GET | /api/evaluations/seller-price-trend | 58 | 0.0% | 0.0% | 215.2 |
| 评估漏斗 | GET | /api/stats/eval-funnel | 60 | 0.0% | 0.0% | 189.95 |
| 账号 | GET | /api/accounts | 53 | 0.0% | 0.0% | 328.94 |
| 账号统计 | GET | /api/accounts/stats | 53 | 0.0% | 0.0% | 369.71 |
| 趋势 | GET | /api/stats/trend | 60 | 0.0% | 0.0% | 117.92 |
| 近期反馈 | GET | /api/chatbot/feedback/recent | 50 | 0.0% | 0.0% | 224.95 |
| 通知全部已读 |  |  | 840 | 0.0% | 0.0% | 650.56 |
| 通知列表 | GET | /api/notifications | 55 | 0.0% | 0.0% | 304.14 |
| 配置 | GET | /api/config | 57 | 0.0% | 0.0% | 201.6 |
| 配置分享 | GET | /api/config/share | 56 | 0.0% | 0.0% | 291.33 |
| 配置原始 | GET | /api/config/raw | 56 | 0.0% | 0.0% | 517.61 |
| 配置备份 | GET | /api/config/backups | 56 | 0.0% | 0.0% | 634.62 |
| 配置导出 | GET | /api/config/export | 56 | 0.0% | 0.0% | 378.19 |
| 配置版本 | GET | /api/config/version | 56 | 0.0% | 0.0% | 432.97 |
| 配置预览 |  |  | 829 | 0.0% | 0.0% | 925.01 |
| 错误日志 | GET | /api/error-logs | 54 | 0.0% | 0.0% | 612.93 |
| 错误日志详情 | GET | /api/error-logs/${ERRORLOG_ID} | 54 | 0.0% | 0.0% | 451.23 |
| 阈值建议 | GET | /api/evaluations/threshold-suggestion | 58 | 0.0% | 0.0% | 238.19 |
| 隧道状态 | GET | /api/tunnel/status | 53 | 0.0% | 0.0% | 2887.09 |

