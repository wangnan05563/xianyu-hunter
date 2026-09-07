# 按钮 Tooltip 文案对照表（完整版）

> 自动抽取自 `frontend/src`（排除组件定义 `TipButton.tsx`）全部 `<TipButton>` 用法，共 **363** 处 / **2** 个分组。
> 用途：逐条核对悬浮提示文案是否准确对应按钮实际操作。
> 说明：「图标/自闭合按钮」指无文字子元素、仅图标的按钮，其提示文案在 `tip` 属性中。
> 说明：部分按钮的 `tip` 为**运行时动态表达式**（如 `tip={title}`、`tip={schedulerRunning ? …}`），静态抽取无法显示其文字，但运行时确有提示，**非缺口**；下方空白单元格即属此类。

## components（27）

| 文件 | 按钮（标签/图标） | Tooltip 文案 |
| --- | --- | --- |
| `components\DiffPreviewModal.tsx` | 取消 | 取消保存并关闭预览 |
| `components\DiffPreviewModal.tsx` | 确认保存 | 确认并保存配置变更 |
| `components\ErrorBoundary.tsx` | 重试 | 重新渲染页面，尝试恢复正常 |
| `components\ErrorBoundary.tsx` | 刷新页面 | 重新加载整个页面 |
| `components\ExportButton.tsx` | {label} | `导出 … 为 CSV（Excel 友好）` |
| `components\ReloadPrompt.tsx` | 稍后 | 稍后更新，关闭此提示 |
| `components\ReloadPrompt.tsx` | 立即刷新 | 立即应用新版本并刷新页面 |
| `components\ReloadPrompt.tsx` | 知道了 | 关闭此提示 |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） | 展开或收起侧边栏 |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） | 打开命令面板（Ctrl+K） |
| `components\layout\MainLayout.tsx` | { if (schedulerRunning === null) return '#d9d9d9' if (schedulerRunning) return '#52c41a' return '#ff4d4f' })(), display: 'inline-block', }} /> |  |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） | 打开今日告警通知 |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） |  |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） | 打开帮助文档 |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） | 查看关于与版本信息 |
| `components\layout\UserMenu.tsx` | （图标/自闭合按钮） |  |
| `components\layout\UserMenu.tsx` | 换号 | 切换到其他闲鱼账号 |
| `components\layout\UserMenu.tsx` | 退出 | 退出当前账号并清除登录态 |
| `components\ParamCalculator\ParamCalculatorPanel.tsx` | （图标/自闭合按钮） | 重新执行参数校验 |
| `components\SheetWorkspace\sheetNotifications.tsx` | 撤销 | 恢复被自动替换的 sheet |
| `components\SheetWorkspace\SheetPreferences.tsx` | 清空回收栈 | 清空已淘汰 sheet 的回收记录 |
| `components\SheetWorkspace\SheetPreferences.tsx` | 完成 | 关闭偏好设置面板 |
| `components\SheetWorkspace\SheetPreferences.tsx` | 恢复默认 | 恢复所有偏好为默认值 |
| `components\SheetWorkspace\SheetTabs.tsx` | （图标/自闭合按钮） | 关闭此 sheet |
| `components\SheetWorkspace\SheetTabs.tsx` | （图标/自闭合按钮） | 最小化此 sheet |
| `components\SheetWorkspace\SheetTabs.tsx` | （图标/自闭合按钮） | 关闭此 sheet |
| `components\SheetWorkspace\SheetTabs.tsx` | （图标/自闭合按钮） |  |

## pages（336）

| 文件 | 按钮（标签/图标） | Tooltip 文案 |
| --- | --- | --- |
| `pages\About\BrandCard.tsx` | {TEXTS.updateLoading} | 正在检查更新 |
| `pages\About\BrandCard.tsx` | {TEXTS.updateLatest} | 已是最新版本 |
| `pages\About\BrandCard.tsx` | {TEXTS.updateNewer} ({state.latest}) |  |
| `pages\About\BrandCard.tsx` | {state.reason === 'network' ? TEXTS.updateErrorNetwork : TEXTS.updateErrorServer} · {TEXTS.updateRetry} | 检查更新失败，点击重试 |
| `pages\About\BrandCard.tsx` | {TEXTS.updateIdle} |  |
| `pages\About\BrandCard.tsx` | （图标/自闭合按钮） |  |
| `pages\AntiCrawl\index.tsx` | 刷新 | 刷新全部数据 |
| `pages\AntiCrawl\index.tsx` | 初始化协调器（{useCdp ? 'CDP' : 'Launch'} 模式） | 初始化反爬协调器，启动登录策略 |
| `pages\AntiCrawl\index.tsx` | 更新 Cookie | 打开分层 Cookie 更新弹窗 |
| `pages\AntiCrawl\index.tsx` | （图标/自闭合按钮） | 刷新 Cookie 层状态 |
| `pages\AntiCrawl\index.tsx` | 主动失效 | 主动失效该 Cookie 层 |
| `pages\AntiCrawl\index.tsx` | （图标/自闭合按钮） | 刷新频率伪装统计 |
| `pages\AntiCrawl\index.tsx` | 从浏览器导入（覆盖文本框） | 从浏览器导入 Cookie 覆盖文本框 |
| `pages\AntiCrawl\index.tsx` | 启动会话 | 启动会话管理并开始续期 |
| `pages\AntiCrawl\index.tsx` | 停止会话 | 停止会话管理与后台续期 |
| `pages\AntiCrawl\index.tsx` | 检查 | 执行健康检查 |
| `pages\Chatbot\Config.tsx` | 恢复默认 | 清空欢迎语，恢复默认文案 |
| `pages\Chatbot\Config.tsx` | 回滚 | 回滚知识库至该版本 |
| `pages\Chatbot\Config.tsx` | 新增 FAQ | 新增一条 FAQ |
| `pages\Chatbot\Config.tsx` | 编辑 | 编辑该条 FAQ |
| `pages\Chatbot\Config.tsx` | （图标/自闭合按钮） | 删除该条 FAQ |
| `pages\Chatbot\Config.tsx` | 刷新 | 刷新审计日志列表 |
| `pages\Chatbot\index.tsx` | 新建会话 | 新建一个会话 |
| `pages\Chatbot\index.tsx` | （图标/自闭合按钮） | 切换只显示收藏的会话 |
| `pages\Chatbot\index.tsx` | 清空 | 清空搜索历史 |
| `pages\Chatbot\index.tsx` | 帮助中心 | 打开帮助中心 |
| `pages\Chatbot\index.tsx` | 立即转人工 | 转接至人工客服 |
| `pages\Chatbot\index.tsx` | （图标/自闭合按钮） | 打开会话列表 |
| `pages\Chatbot\index.tsx` | （图标/自闭合按钮） | 上传图片（最多 4 张） |
| `pages\Chatbot\index.tsx` | 停止 | 停止当前流式生成 |
| `pages\Chatbot\index.tsx` | 发送 | 发送消息（Enter） |
| `pages\Chatbot\index.tsx` | 发送失败 · 重试 | 重新发送该消息 |
| `pages\Chatbot\index.tsx` | 撤回 | 撤回这条消息（2 分钟内） |
| `pages\Chatbot\components\AssistantMessage.tsx` | 复制会话记录 | 复制当前会话记录到剪贴板 |
| `pages\Chatbot\components\ChatbotOnboarding.tsx` | （图标/自闭合按钮） | 关闭引导卡片 |
| `pages\Chatbot\components\KBStatusCard.tsx` | 重建 | 重建知识库索引（使用最新文档） |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | 刷新 | 刷新向量库状态、快照与审计日志 |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | 创建快照 | 为当前集合创建一份快照备份 |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | 恢复 | 用该快照覆盖当前集合数据 |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | 删除 | 删除该快照文件，不影响当前集合 |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | 清空集合 | 删除集合内全部片段（危险操作） |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | 按来源文件删除 | 按来源文件删除其全部片段 |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | 刷新 | 刷新向量库维护审计日志 |
| `pages\Config\BuyerStrategy.tsx` | 重置 | 放弃未保存的修改并重置 |
| `pages\Config\BuyerStrategy.tsx` | 保存 | 保存抢单策略配置 |
| `pages\Config\EvalRules.tsx` | 重置 | 放弃未保存的修改并重置 |
| `pages\Config\EvalRules.tsx` | 保存 | 保存评估规则配置 |
| `pages\Config\EvalRules.tsx` | 一键归一化 | 将权重总和自动归一化为 100 |
| `pages\Config\EvalRules.tsx` | ⏪ | 恢复 pass_score 原始值 |
| `pages\Config\EvalRules.tsx` | ⏪ | 恢复 auto_buy_score 原始值 |
| `pages\Config\EvalRules.tsx` | ⏪ | 恢复该项权重原始值 |
| `pages\Config\PriceStrategy.tsx` | 重置 | 放弃未保存的修改并重置 |
| `pages\Config\PriceStrategy.tsx` | 保存 | 保存价格策略配置 |
| `pages\Config\PriceStrategy.tsx` | （图标按钮） | 恢复最高价原始值 |
| `pages\Config\PriceStrategy.tsx` | （图标按钮） | 恢复最低价原始值 |
| `pages\Config\PriceStrategy.tsx` | （图标按钮） | 恢复市场价比例原始值 |
| `pages\Config\PriceStrategy.tsx` | （图标按钮） | 恢复 TopN 原始值 |
| `pages\Config\PriceStrategy.tsx` | 刷新预览数据 | 重新生成策略命中预览数据 |
| `pages\Config\SearchConfig.tsx` | 重置 | 放弃未保存的修改并重置 |
| `pages\Config\SearchConfig.tsx` | 保存配置 | 保存搜索参数配置 |
| `pages\Config\SearchConfig.tsx` | {tag} | `点击切换筛选标签「…」` |
| `pages\Config\VersionManager.tsx` | 刷新 | 重新加载版本与备份信息 |
| `pages\Config\VersionManager.tsx` | 导出配置 | 导出当前配置为 JSON 文件 |
| `pages\Config\VersionManager.tsx` | 分享配置 | 生成脱敏配置用于分享 |
| `pages\Config\VersionManager.tsx` | 导入配置 | 从 JSON 文件导入配置 |
| `pages\Config\VersionManager.tsx` | 一键回滚 | 回滚到上一版本备份 |
| `pages\Config\VersionManager.tsx` | 查看详情 | 查看该备份的详细信息 |
| `pages\Config\VersionManager.tsx` | 恢复 | 从该备份恢复配置 |
| `pages\Config\VersionManager.tsx` | 关闭 | 关闭备份详情弹窗 |
| `pages\Config\VersionManager.tsx` | 从此备份恢复 | 用当前备份覆盖现有配置 |
| `pages\Config\VersionManager.tsx` | 关闭 | 关闭分享配置弹窗 |
| `pages\Config\VersionManager.tsx` | 复制到剪贴板 | 复制配置文本到剪贴板 |
| `pages\Config\AIConfig\components\BudgetSettings.tsx` | 保存预算设置 | 保存当前预算设置 |
| `pages\Config\AIConfig\components\EmbeddingConfigForm.tsx` | {showApiKey ? '隐藏' : '显示'} | 切换显示或隐藏 API Key 明文 |
| `pages\Config\AIConfig\components\EmbeddingConfigForm.tsx` | {testing ? '测试中…（本地首次加载模型较慢）' : '🔗 测试 Embedding 连接'} | 测试 Embedding 连接是否可用 |
| `pages\Config\AIConfig\components\ModelConfigForm.tsx` | {showApiKey ? '隐藏' : '显示'} | 切换显示或隐藏 API Key 明文 |
| `pages\Config\AIConfig\components\ModelConfigForm.tsx` | 获取 | 前往厂商 API Key 申请页 |
| `pages\Config\AIConfig\components\ModelConfigForm.tsx` | 保存配置 | 保存 LLM 配置 |
| `pages\Config\AIConfig\components\ModelConfigForm.tsx` | {testing ? '测试中…' : '🔗 测试连接'} | 测试 LLM 连接是否可用 |
| `pages\Config\NotifierChannels\index.tsx` | 重置 | 放弃未保存的修改并重置 |
| `pages\Config\NotifierChannels\index.tsx` | 保存 | 保存通知渠道配置 |
| `pages\Config\NotifierChannels\components\ChannelCard.tsx` | {testing ? '发送中...' : '发送测试'} | 向该渠道发送测试推送消息 |
| `pages\ConfirmBuy\index.tsx` | 返回首页 | 返回系统首页 |
| `pages\ConfirmBuy\index.tsx` | 查看评估列表 | 前往评估明细列表 |
| `pages\ConfirmBuy\index.tsx` | 返回首页 | 返回系统首页 |
| `pages\ConfirmBuy\index.tsx` | 返回评估列表 | 返回评估明细列表 |
| `pages\ConfirmBuy\index.tsx` | 确认抢单 | 创建待支付订单并提交抢单 |
| `pages\ConfirmBuy\index.tsx` | 取消 | 放弃抢单并返回评估列表 |
| `pages\Dashboard\index.tsx` | 创建任务 | 创建新的监控任务 |
| `pages\Dashboard\index.tsx` | 查看引导 | 查看新手引导说明 |
| `pages\Dashboard\components\AlertRadar.tsx` | （图标/自闭合按钮） | 重新拉取最新预警数据 |
| `pages\Dashboard\components\EventStreamSection.tsx` | 查看全部 | 跳转事件时间线查看全部事件 |
| `pages\Dashboard\components\EventStreamSection.tsx` | 任务管理 | 进入任务管理页面 |
| `pages\Dashboard\components\EventStreamSection.tsx` | 配置 | 进入 AI 配置页面 |
| `pages\Dashboard\components\EventStreamSection.tsx` | 实时日志 | 进入实时日志页面 |
| `pages\Dashboard\components\EventStreamSection.tsx` | 抢单记录 | 进入抢单记录页面 |
| `pages\Dashboard\components\PriceHistogramCard.tsx` | 查看商品 | 进入商品列表页面 |
| `pages\Dashboard\components\PriceHistogramCard.tsx` | AI 智能分析 | 基于价格分布调用 AI 生成分析建议 |
| `pages\Dashboard\components\PriceHistogramCard.tsx` | 清除 | 清除当前 AI 分析结果 |
| `pages\Dashboard\components\TrendModal.tsx` | {(() => { // 时间范围文案 if (h === 168) return '7 天' if (h === 720) return '30 天' return '90 天' })()} |  |
| `pages\Evaluations\index.tsx` | 计算建议阈值 | 根据目标通过率计算建议评分阈值 |
| `pages\Evaluations\index.tsx` | 批量 AI 评估 ({selectedCount} 项) | 对选中商品批量执行 AI 成色评估 |
| `pages\Evaluations\index.tsx` | 批量官方采集 ({selectedCount} 项) | 对选中商品批量访问官方页面采集 |
| `pages\Evaluations\index.tsx` | 取消选择 | 取消已选中的商品 |
| `pages\Evaluations\index.tsx` | 查询 | 按当前筛选条件查询评估记录 |
| `pages\Evaluations\index.tsx` | 重置 | 重置全部筛选条件 |
| `pages\Evaluations\index.tsx` | 刷新 | 重新加载评估列表数据 |
| `pages\Evaluations\index.tsx` | 重新评估 | 重新计算所有商品评估分值 |
| `pages\Evaluations\index.tsx` | 批量评估未评估商品 | 对尚未评估的商品批量评估 |
| `pages\Evaluations\index.tsx` | 列配置 | 打开列显示与排序配置 |
| `pages\Evaluations\index.tsx` | （图标/自闭合按钮） |  |
| `pages\Evaluations\components\AIEvalModal.tsx` | 关闭 | 关闭 AI 评估弹窗 |
| `pages\Evaluations\components\CollectResultModal.tsx` | 关闭 | 关闭官方采集结果弹窗 |
| `pages\Evaluations\components\ColumnSettingsModal.tsx` | 恢复默认 | 恢复列为默认顺序与显示状态 |
| `pages\Evaluations\components\ColumnSettingsModal.tsx` | 完成 | 保存列配置并关闭弹窗 |
| `pages\Evaluations\components\DeepAnalyzeModal.tsx` | 关闭 | 关闭 AI 深度鉴伪弹窗 |
| `pages\Evaluations\components\TrendSparkline.tsx` | 加载卖家价格趋势 | 加载该卖家的价格趋势数据 |
| `pages\Evaluations\hooks\useEvalColumns.tsx` | （图标/自闭合按钮） |  |
| `pages\Evaluations\hooks\useEvalColumns.tsx` | （图标/自闭合按钮） | AI 成色评估 |
| `pages\Evaluations\hooks\useEvalColumns.tsx` | （图标/自闭合按钮） | 深度鉴伪（盗图/损坏/一致性/模板） |
| `pages\Evaluations\hooks\useEvalColumns.tsx` | （图标/自闭合按钮） | 访问闲鱼官方页面采集完整数据并重新评估 |
| `pages\Evaluations\hooks\useEvalColumns.tsx` | （图标/自闭合按钮） | `手动抢单（评分 … ≥ …）` |
| `pages\Export\index.tsx` | 导出 CSV | `导出 … 为 CSV 文件` |
| `pages\Help\index.tsx` | API 文档 | 在新标签页打开 API 文档 |
| `pages\Items\ItemList.tsx` | （图标/自闭合按钮） | 删除此商品关联（不可恢复） |
| `pages\Items\ItemList.tsx` | 重新登录 | 前往登录页刷新闲鱼 Cookie |
| `pages\Items\ItemList.tsx` | 实时搜索 | 调用闲鱼实时搜索并写入最新商品 |
| `pages\Items\ItemList.tsx` | 刷新 | 刷新当前任务的商品数据 |
| `pages\Items\ItemList.tsx` | 秒 | 轮询间隔单位（秒） |
| `pages\Items\ItemList.tsx` | 管理任务 | 前往任务管理页面 |
| `pages\Items\ItemList.tsx` | 列配置 | 拖拽调整列顺序或显示/隐藏字段 |
| `pages\Items\ItemList.tsx` | 清空 | 清空搜索历史关键词 |
| `pages\Login\index.tsx` | 启动浏览器窗口登录 | 启动浏览器窗口并手动登录闲鱼 |
| `pages\Login\index.tsx` | 取消登录 | 取消当前登录过程 |
| `pages\Login\index.tsx` | 重新登录 | 重新启动浏览器窗口登录 |
| `pages\Login\index.tsx` | {autoFilling ? '读取中…' : '从浏览器自动获取'} | 从系统浏览器读取 Cookie 并填充 |
| `pages\Login\index.tsx` | 清空 | 清空已填写的 Cookie 字段 |
| `pages\Login\index.tsx` | 注入 Cookie 登录 | 注入 Cookie 完成登录 |
| `pages\Login\index.tsx` | 上传文件 | 从文件导入 Cookie |
| `pages\Login\index.tsx` | 从 Edge 导入 | 从 Edge 浏览器导入 Cookie |
| `pages\Login\index.tsx` | 从 Chrome 导入 | 从 Chrome 浏览器导入 Cookie |
| `pages\Login\index.tsx` | 打开闲鱼网页 | 在系统浏览器打开闲鱼登录页 |
| `pages\Login\index.tsx` | 自动关闭 Edge 并导入 | 自动关闭 Edge 后导入 Cookie |
| `pages\Login\index.tsx` | 自动关闭 Chrome 并导入 | 自动关闭 Chrome 后导入 Cookie |
| `pages\Login\index.tsx` | 刷新检测 | 重新检测浏览器状态 |
| `pages\Login\index.tsx` | 如何获取 Cookie？ | 查看获取 Cookie 的图文教程 |
| `pages\Login\index.tsx` | 知道了 | 关闭教程弹窗 |
| `pages\Logs\ErrorLogs.tsx` | 复制 | 复制 AI 上下文到剪贴板 |
| `pages\Logs\ErrorLogs.tsx` | 刷新 | 重新加载错误日志列表 |
| `pages\Logs\ErrorLogs.tsx` | 批量清理 | 清理 30 天前已解决/已忽略的日志 |
| `pages\Logs\ErrorLogs.tsx` | 搜索 | 按状态与错误类型搜索日志 |
| `pages\Logs\ErrorLogs.tsx` | 清空 | 清空搜索历史关键词 |
| `pages\Logs\ErrorLogs.tsx` | 标记已解决 | 将选中项标记为已解决 |
| `pages\Logs\ErrorLogs.tsx` | 标记已忽略 | 将选中项标记为已忽略 |
| `pages\Logs\ErrorLogs.tsx` | 批量删除 | 批量删除选中的错误日志 |
| `pages\Logs\ErrorLogs.tsx` | 取消选择 | 清除当前勾选 |
| `pages\Logs\ErrorLogs.tsx` | （图标/自闭合按钮） | 删除该条错误日志 |
| `pages\Logs\Logs.tsx` | {streaming ? '停止实时流' : '开启实时流'} |  |
| `pages\Logs\Logs.tsx` | {paused ? '恢复' : '暂停'} |  |
| `pages\Logs\Logs.tsx` | 清空 | 清空当前显示的实时流日志 |
| `pages\Logs\Logs.tsx` | 搜索 | 按关键词/级别/任务搜索日志 |
| `pages\Logs\Logs.tsx` | 导出CSV | 导出当前日志为 CSV 文件 |
| `pages\Logs\Logs.tsx` | 导出LOG | 导出当前日志为 LOG 文件 |
| `pages\Logs\Logs.tsx` | 刷新 | 重新加载原始日志 |
| `pages\Maintenance\BatchRefresh.tsx` | 刷新状态 | 刷新当前批次执行状态 |
| `pages\Maintenance\BatchRefresh.tsx` | 保存 | 保存并热更新配置 |
| `pages\Maintenance\BatchRefresh.tsx` | 立即触发批量采集 |  |
| `pages\Maintenance\BatchRefresh.tsx` | 暂停 | 暂停当前批次，采集完成后生效 |
| `pages\Maintenance\BatchRefresh.tsx` | 继续 | 从断点继续批量采集 |
| `pages\Maintenance\BatchRefresh.tsx` | 停止（持久化进度，可续传） | 停止批次并持久化进度 |
| `pages\Maintenance\BatchRefresh.tsx` | 详情 | 查看该条执行历史详情 |
| `pages\Maintenance\BatchRefresh.tsx` | 删除 | 删除该条历史记录，操作不可恢复 |
| `pages\Maintenance\BatchRefresh.tsx` | 查询 | 按筛选条件查询执行历史 |
| `pages\Maintenance\BatchRefresh.tsx` | 重置 | 重置所有筛选条件 |
| `pages\Maintenance\BatchRefresh.tsx` | 清理 30 天前 | 清理 30 天前的历史记录 |
| `pages\Maintenance\BatchRefresh.tsx` | 清空全部 | 清空全部历史记录，不可恢复 |
| `pages\Maintenance\BatchRefresh.tsx` | 刷新 | 重新加载执行历史列表 |
| `pages\Maintenance\Cleanup.tsx` | 刷新状态 | 刷新存储状态概览 |
| `pages\Maintenance\Cleanup.tsx` | 清理缓存 | 清理所选范围的缓存（预览或真实执行） |
| `pages\Maintenance\Cleanup.tsx` | 清理数据库 | 清理数据库冗余数据（预览或真实执行） |
| `pages\Maintenance\Cleanup.tsx` | 清理日志 | 清理旧日志文件释放磁盘空间 |
| `pages\Maintenance\DatabaseAdmin.tsx` | 审计日志 | 查看数据库维护审计日志 |
| `pages\Maintenance\DatabaseAdmin.tsx` | 刷新 | 刷新表列表与数据 |
| `pages\Maintenance\DatabaseAdmin.tsx` | 新增 | 新增一行记录 |
| `pages\Maintenance\DatabaseAdmin.tsx` | 批量删除 {selectedRowKeys.length > 0 && `(${selectedRowKeys.length})`} | 批量删除选中行（需确认） |
| `pages\Maintenance\DatabaseAdmin.tsx` | 导入 | 打开数据导入弹窗 |
| `pages\Maintenance\DatabaseAdmin.tsx` | 导出 CSV | 导出当前表数据为 CSV |
| `pages\Maintenance\DatabaseAdmin.tsx` | 导出 JSON | 导出当前表数据为 JSON |
| `pages\Maintenance\DatabaseAdmin.tsx` | 查看表结构 | 查看当前表字段结构 |
| `pages\Maintenance\DatabaseAdmin.tsx` | 查询 | 按关键词查询表数据 |
| `pages\Maintenance\DatabaseAdmin.tsx` | 清空 | 清空搜索历史关键词 |
| `pages\Maintenance\DatabaseAdmin.tsx` | 编辑 | 编辑该行记录 |
| `pages\Maintenance\DatabaseAdmin.tsx` | 删除 | 删除该行（需输入确认码） |
| `pages\Maintenance\DatabaseAdmin.tsx` | 选择 CSV 文件 | 选择本地 CSV 文件上传 |
| `pages\Maintenance\DatabaseAdmin.tsx` | 选择 JSON 文件 | 选择本地 JSON 文件上传 |
| `pages\Maintenance\Tunnel.tsx` | {loginButtonText} | 执行 Cloudflare 授权登录 |
| `pages\Maintenance\Tunnel.tsx` | {config.tunnel_id ? '重新创建' : '创建隧道'} | 创建命名隧道（或重新创建） |
| `pages\Maintenance\Tunnel.tsx` | {config.hostname ? '重新配置' : '配置路由'} | 配置 DNS 路由（CNAME 记录） |
| `pages\Maintenance\Tunnel.tsx` | 启动隧道 | 启动隧道建立公网连接 |
| `pages\Maintenance\Tunnel.tsx` | 停止 | 停止当前隧道 |
| `pages\Maintenance\Tunnel.tsx` | （图标/自闭合按钮） | 在新窗口打开公网地址 |
| `pages\Maintenance\Tunnel.tsx` | {url.length > 60 ? url.slice(0, 60) + '...' : url} | 下载 cloudflared 二进制文件 |
| `pages\Maintenance\Tunnel.tsx` | 打开 Tailscale Funnel 授权页面 | 打开 Tailscale Funnel 授权页面 |
| `pages\Maintenance\Tunnel.tsx` | 保存配置 | 保存隧道配置（下次启动生效） |
| `pages\Maintenance\VectorAdmin.tsx` | 审计日志 | 查看向量库审计日志 |
| `pages\Maintenance\VectorAdmin.tsx` | 刷新 | 重新加载向量库状态 |
| `pages\Maintenance\VectorAdmin.tsx` | 创建快照 | 创建向量库快照备份 |
| `pages\Maintenance\VectorAdmin.tsx` | 恢复 | 从快照恢复并覆盖当前集合 |
| `pages\Maintenance\VectorAdmin.tsx` | 删除 | 删除该快照（不可恢复） |
| `pages\Maintenance\VectorAdmin.tsx` | 清空集合 | 清空集合中全部片段 |
| `pages\Maintenance\VectorAdmin.tsx` | 删除 | 删除指定来源的所有片段 |
| `pages\MenuAdmin\index.tsx` | （图标/自闭合按钮） | 返回上一页 |
| `pages\MenuAdmin\index.tsx` | 刷新 | 重新加载菜单配置 |
| `pages\MenuAdmin\index.tsx` | 重置为默认 | 重置为默认菜单配置 |
| `pages\MenuAdmin\index.tsx` | 保存{hasDirty ? ` (${rows.filter((r) => r.dirty).length})` : ''} | 保存菜单配置修改 |
| `pages\Notifications\index.tsx` | 全部标记已读 | 将所有未读通知标记为已读 |
| `pages\Notifications\index.tsx` | 清空已读 | 清空所有已读通知（不可恢复） |
| `pages\Notifications\index.tsx` | （图标/自闭合按钮） | 刷新通知列表与未读数 |
| `pages\Notifications\index.tsx` | {label} |  |
| `pages\Notifications\index.tsx` | 标记已读 | 标记该通知为已读 |
| `pages\Notifications\index.tsx` | 删除 | 删除该通知（不可恢复） |
| `pages\Onboarding\index.tsx` | 复制 | 复制扫码登录命令 |
| `pages\Onboarding\index.tsx` | 刷新登录状态 | 刷新并检测当前登录状态 |
| `pages\Onboarding\index.tsx` | 创建任务 | 创建监控任务 |
| `pages\Onboarding\index.tsx` | 下一步 | 进入下一步配置通知 |
| `pages\Onboarding\index.tsx` | 复制 | 复制启动调度器命令 |
| `pages\Onboarding\index.tsx` | 完成设置 | 完成初始化设置 |
| `pages\Onboarding\index.tsx` | 进入仪表盘 | 进入系统仪表盘 |
| `pages\Onboarding\index.tsx` | 上一步 | 返回上一步 |
| `pages\Onboarding\index.tsx` | 跳过 | 跳过本步骤 |
| `pages\Orders\Orders.tsx` | 取消 | 关闭接管弹窗 |
| `pages\Orders\Orders.tsx` | 确认接管 | 开始接管此订单 |
| `pages\Orders\Orders.tsx` | 取消接管 | 取消接管并保留订单为待处理 |
| `pages\Orders\Orders.tsx` | 确认完成 | 确认已在闲鱼完成支付 |
| `pages\Orders\Orders.tsx` | 关闭 | 关闭完成提示 |
| `pages\Orders\Orders.tsx` | {r.status === 'pending' ? '接管' : '查看'} |  |
| `pages\Orders\Orders.tsx` | 删除 | 删除此订单（不可恢复） |
| `pages\Orders\Orders.tsx` | 刷新 | 重新加载订单列表 |
| `pages\Orders\Orders.tsx` | 列配置 | 自定义表格显示列与顺序 |
| `pages\PriceDashboard\components\BargainEvalCard.tsx` | （图标/自闭合按钮） | 刷新评估结果与分位数数据 |
| `pages\PriceDashboard\components\BargainEvalCard.tsx` | 评估 | 按当前价格评估捡漏等级与得分 |
| `pages\PriceDashboard\components\CategoryComparisonChart.tsx` | （图标/自闭合按钮） | 刷新品类对比图表数据 |
| `pages\PriceDashboard\components\CategoryStatsTable.tsx` | （图标/自闭合按钮） | 刷新品类统计明细数据 |
| `pages\PriceDashboard\components\SoldRangeCard.tsx` | （图标/自闭合按钮） | 刷新捡漏价格参考数据 |
| `pages\Tasks\TaskDetail.tsx` | （图标/自闭合按钮） | 打开原帖 |
| `pages\Tasks\TaskDetail.tsx` | （图标/自闭合按钮） | 删除该关联 |
| `pages\Tasks\TaskDetail.tsx` | 返回列表 | 返回任务列表 |
| `pages\Tasks\TaskDetail.tsx` | 刷新 | 重新加载任务详情 |
| `pages\Tasks\TaskDetail.tsx` | 启动 | 启动或重启该任务 |
| `pages\Tasks\TaskDetail.tsx` | 暂停 | 暂停当前运行中的任务 |
| `pages\Tasks\TaskDetail.tsx` | 停止 | 停止当前任务 |
| `pages\Tasks\TaskDetail.tsx` | 编辑 | 编辑该任务配置 |
| `pages\Tasks\TaskDetail.tsx` | 添加依赖 | 加载可选任务以添加上游依赖 |
| `pages\Tasks\TaskDetail.tsx` | 添加 | 添加选中的上游依赖 |
| `pages\Tasks\TaskDetail.tsx` | 移除 | 移除该上游依赖 |
| `pages\Tasks\TaskDetail.tsx` | 实时查询 | 实时查询最新关联数据 |
| `pages\Tasks\TaskDetail.tsx` | 刷新数据源 | 重新拉取并写入数据源 |
| `pages\Tasks\TaskEditor.tsx` | 返回列表 | 返回任务列表 |
| `pages\Tasks\TaskEditor.tsx` | 清除草稿 | 清除本地草稿 |
| `pages\Tasks\TaskEditor.tsx` | 返回列表 | 返回任务列表 |
| `pages\Tasks\TaskEditor.tsx` | 前往登录 | 前往登录页 |
| `pages\Tasks\TaskEditor.tsx` | 全局搜索配置 | 编辑全局搜索配置 |
| `pages\Tasks\TaskEditor.tsx` | 修改全局反检测配置 | 编辑全局反检测配置 |
| `pages\Tasks\TaskEditor.tsx` | 批量采集配置 | 编辑全局批量采集配置 |
| `pages\Tasks\TaskEditor.tsx` | 上一步 | 返回上一步 |
| `pages\Tasks\TaskEditor.tsx` | 下一步 | 进入下一步 |
| `pages\Tasks\TaskEditor.tsx` | {isEdit ? '保存修改' : '创建任务'} | 提交创建或保存任务 |
| `pages\Tasks\TaskEditor.tsx` | 全局 AI 评估配置 | 编辑全局 AI 评估配置 |
| `pages\Tasks\TaskEditor.tsx` | 重置为全局 | 重置评估阈值为全局值 |
| `pages\Tasks\TaskEditor.tsx` | 重置为全局 | 重置自动采集开关为全局值 |
| `pages\Tasks\TaskEditor.tsx` | 重置为全局 | 重置每轮采集条数为全局值 |
| `pages\Tasks\TaskEditor.tsx` | 取消 | 关闭弹窗 |
| `pages\Tasks\TaskEditor.tsx` | 重置 | 重置为初始配置 |
| `pages\Tasks\TaskEditor.tsx` | 保存 | 保存配置 |
| `pages\Tasks\TaskEditor.tsx` | 取消 | 取消保存 |
| `pages\Tasks\TaskEditor.tsx` | 确认保存 | 确认保存并写入配置 |
| `pages\Tasks\TaskEditor.tsx` | 取消 | 关闭弹窗 |
| `pages\Tasks\TaskEditor.tsx` | 重置 | 重置为初始配置 |
| `pages\Tasks\TaskEditor.tsx` | 保存 | 保存配置 |
| `pages\Tasks\TaskEditor.tsx` | 取消 | 取消保存 |
| `pages\Tasks\TaskEditor.tsx` | 确认保存 | 确认保存并写入配置 |
| `pages\Tasks\TaskEditor.tsx` | 取消 | 关闭弹窗 |
| `pages\Tasks\TaskEditor.tsx` | 重置 | 重置为初始配置 |
| `pages\Tasks\TaskEditor.tsx` | 保存 | 保存配置 |
| `pages\Tasks\TaskEditor.tsx` | 取消 | 取消保存 |
| `pages\Tasks\TaskEditor.tsx` | 确认保存 | 确认保存并写入配置 |
| `pages\Tasks\TaskEditor.tsx` | 取消 | 关闭弹窗 |
| `pages\Tasks\TaskEditor.tsx` | 重置 | 重置为初始配置 |
| `pages\Tasks\TaskEditor.tsx` | 保存 | 保存配置 |
| `pages\Tasks\TaskEditor.tsx` | 取消 | 取消保存 |
| `pages\Tasks\TaskEditor.tsx` | 确认保存 | 确认保存并写入配置 |
| `pages\Tasks\TaskList.tsx` | （图标/自闭合按钮） | 打开原帖 |
| `pages\Tasks\TaskList.tsx` | （图标/自闭合按钮） | 删除该关联 |
| `pages\Tasks\TaskList.tsx` | {text} | 打开该任务编辑页 |
| `pages\Tasks\TaskList.tsx` | {linkCounts[record.id] ?? '-'} | 查看该任务详情与关联数 |
| `pages\Tasks\TaskList.tsx` | 确认{arm.label} | 确认执行该危险操作 |
| `pages\Tasks\TaskList.tsx` | 取消 | 取消本次危险操作确认 |
| `pages\Tasks\TaskList.tsx` | 编辑 | 编辑该任务 |
| `pages\Tasks\TaskList.tsx` | 暂停 | 暂停该任务 |
| `pages\Tasks\TaskList.tsx` | 启动 | 启动该任务 |
| `pages\Tasks\TaskList.tsx` | 停止 | 停止该任务（需二次确认） |
| `pages\Tasks\TaskList.tsx` | 复制 | 复制该任务为新任务 |
| `pages\Tasks\TaskList.tsx` | （图标/自闭合按钮） | 展开更多操作 |
| `pages\Tasks\TaskList.tsx` | 删除 | 删除该任务（需二次确认） |
| `pages\Tasks\TaskList.tsx` | 智能建任务 | 用一句话 AI 智能创建任务 |
| `pages\Tasks\TaskList.tsx` | 模板市场 | 打开任务模板市场 |
| `pages\Tasks\TaskList.tsx` | 新增任务 | 新建一个任务 |
| `pages\Tasks\TaskList.tsx` | 全部启动 | 一键启动所有非运行中的任务 |
| `pages\Tasks\TaskList.tsx` | 暂停 | 批量暂停选中任务 |
| `pages\Tasks\TaskList.tsx` | 恢复 | 批量恢复选中任务 |
| `pages\Tasks\TaskList.tsx` | 停止 | 批量停止选中任务 |
| `pages\Tasks\TaskList.tsx` | 删除 | 批量删除选中任务 |
| `pages\Tasks\TaskList.tsx` | 清除选择 | 清除已选中的任务 |
| `pages\Tasks\TaskList.tsx` | 暂停 | 暂停该任务 |
| `pages\Tasks\TaskList.tsx` | 启动 | 启动该任务 |
| `pages\Tasks\TaskList.tsx` | {task.name \|\| task.keyword} | 打开该任务编辑页 |
| `pages\Tasks\TaskList.tsx` | 确认{arm.label} | 确认执行该危险操作 |
| `pages\Tasks\TaskList.tsx` | 取消 | 取消本次危险操作确认 |
| `pages\Tasks\TaskList.tsx` | 编辑 | 编辑该任务 |
| `pages\Tasks\TaskList.tsx` | 停止 | 停止该任务（需二次确认） |
| `pages\Tasks\TaskList.tsx` | 复制 | 复制该任务为新任务 |
| `pages\Tasks\TaskList.tsx` | （图标/自闭合按钮） | 展开更多操作 |
| `pages\Tasks\TaskList.tsx` | 删除 | 删除该任务（需二次确认） |
| `pages\Tasks\TaskList.tsx` | 上一页 | 返回上一页 |
| `pages\Tasks\TaskList.tsx` | 下一页 | 前往下一页 |
| `pages\Tasks\TaskList.tsx` | {searchingIds.has(linkTaskId) ? '自动搜索中...' : '实时查询'} | 实时查询关联数据 |
| `pages\Tasks\TaskList.tsx` | 查看被过滤的 {liveFilterSummary.filtered_out.length} 条结果 | 查看被实时搜索过滤掉的结果 |
| `pages\Tasks\TaskList.tsx` | 手动添加 | 手动添加一条关联 |
| `pages\Tasks\TaskList.tsx` | 取消 | 关闭智能建任务弹窗 |
| `pages\Tasks\TaskList.tsx` | 用此结果继续 → | 用解析结果前往创建任务 |
| `pages\Tasks\TaskList.tsx` | 开始解析 | 让 AI 解析需求并创建任务 |
| `pages\Tasks\TaskList.tsx` | （图标/自闭合按钮） | 删除该私有模板 |
| `pages\Timeline\components\TimelineFilter.tsx` | 刷新 | 重新加载时间线数据 |
| `pages\Timeline\components\TimelineFilter.tsx` | 同步订阅 | 从通知配置同步订阅规则 |
| `pages\Timeline\components\TimelineFilter.tsx` | 清除过滤 | 清除事件类型过滤 |
| `pages\Timeline\components\TimelineItem.tsx` | {isExpanded ? '收起详情' : '查看详情'} | 展开或收起该事件的详细载荷 |
