"""Web 路由聚合

路由文件按功能逻辑分组（物理文件保持平铺，避免跨文件导入重构风险）：

== 任务管理 API ==
  api_tasks.py          — 任务 CRUD + 批量控制
  api_task_deps.py      — F-16 任务依赖关系
  api_task_links.py     — 闲鱼内容关联（实时搜索/跨任务搜索）

== 认证 API（api_auth.py 聚合以下子模块）==
  api_auth.py           — 认证聚合路由
  auth_query.py         — 用户信息/会话验证
  unified_login.py      — 统一登录入口
  browser_login.py      — Playwright 浏览器登录
  cookie_inject.py      — 手动 Cookie 注入
  browser_import.py     — 从系统浏览器导入 Cookie
  auth_helpers.py       — 认证公共工具函数

== 统计 API（api_stats.py 聚合以下子模块）==
  api_stats.py          — 统计聚合路由
  stats_overview.py     — 总览统计（4 卡）
  stats_today.py        — 今日异常雷达
  timeline.py           — 统一时间线
  sse_stream.py         — SSE 事件流
  price_histogram.py    — 价格直方图
  trend.py              — 多指标趋势
  business_kpi.py       — F-OB1 业务 KPI
  seller_trend.py       — F-12 卖家价格趋势

== 其他 API ==
  api_config.py         — 配置管理（5 Tab + 版本回滚）
  api_logs.py           — 日志搜索/标签/导出/SSE
  api_orders.py         — 抢单记录/人工接管
  api_evaluations.py    — 评估明细/分布/阈值建议
  api_items.py          — 商品批量查询
  api_ai.py             — F-01 AI 建任务 + F-06 Vision 成色评估
  api_notifier.py       — P3-F-10 免打扰配置
  api_notifications.py  — 业务通知中心
  api_templates.py      — F-11 模板市场
  api_export.py         — P1-5 数据导出（CSV）
  api_prompts.py        — P1-8 Prompt 在线编辑器
  api_cron.py           — P1-7 Cron 表达式校验
  price_dashboard.py    — P1-6 价格行情看板增强（品类统计/横向对比）
  api_ai_deep.py        — P1-4 AI 深度多模态分析增强（盗图/损坏/一致性/贩子识别）
  api_accounts_proxies.py — P1-2 多账号轮换 + 代理池
"""
