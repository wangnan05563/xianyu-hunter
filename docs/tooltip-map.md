# 按钮 Tooltip 文案对照表（完整版）

> 自动抽取自 `frontend/src`（排除组件定义 `TipButton.tsx`）全部 `<TipButton>` 用法，共 **363** 处 / **2** 个分组。
> 用途：逐条核对悬浮提示文案是否准确对应按钮实际操作。
> 说明：「图标/自闭合按钮」指无文字子元素、仅图标的按钮，其提示文案在 `tip` 属性中。

## components（27）

| 文件 | 按钮（标签/图标） | Tooltip 文案 |
| --- | --- | --- |
| `components\DiffPreviewModal.tsx` | 取消 | "取消保存并关闭预览" |
| `components\DiffPreviewModal.tsx` | 确认保存 | "确认并保存配置变更" |
| `components\ErrorBoundary.tsx` | 重试 | "重新渲染页面，尝试恢复正常" |
| `components\ErrorBoundary.tsx` | globalThis.location.reload()}>刷新页面 | "重新加载整个页面" |
| `components\ExportButton.tsx` | } onClick={() => handleExport(dataset)} > {label} |  |
| `components\ReloadPrompt.tsx` | notification.destroy(key)}> 稍后 | "稍后更新，关闭此提示" |
| `components\ReloadPrompt.tsx` | { notification.destroy(key) if (updateSw) { void updateSw(true) // skipWaiting + 重载页面 } else { globalThis.location.reload() } }} > 立即刷新 | "立即应用新版本并刷新页面" |
| `components\ReloadPrompt.tsx` | notification.destroy(key)}> 知道了 | "关闭此提示" |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） | "展开或收起侧边栏" |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） | "打开命令面板（Ctrl+K）" |
| `components\layout\MainLayout.tsx` | openSheetWithNotification('/')} > { if (schedulerRunning === null) return '#d9d9d9' if (schedulerRunning) return '#52c41a' return '#ff4d4f' })(), display: 'inline-block', }} /> |  |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） | "打开今日告警通知" |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） |  |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） | "打开帮助文档" |
| `components\layout\MainLayout.tsx` | （图标/自闭合按钮） | "查看关于与版本信息" |
| `components\layout\UserMenu.tsx` | （图标/自闭合按钮） |  |
| `components\layout\UserMenu.tsx` | } onClick={handleSwitchAccount} > 换号 | "切换到其他闲鱼账号" |
| `components\layout\UserMenu.tsx` | } loading={loggingOut} onClick={handleLogout} > 退出 | "退出当前账号并清除登录态" |
| `components\ParamCalculator\ParamCalculatorPanel.tsx` | （图标/自闭合按钮） | "重新执行参数校验" |
| `components\SheetWorkspace\sheetNotifications.tsx` | { useSheetStore.getState().restoreReplaced(id) notification.destroy(key) }} > 撤销 | "恢复被自动替换的 sheet" |
| `components\SheetWorkspace\SheetPreferences.tsx` | 清空回收栈 | "清空已淘汰 sheet 的回收记录" |
| `components\SheetWorkspace\SheetPreferences.tsx` | 完成 | "关闭偏好设置面板" |
| `components\SheetWorkspace\SheetPreferences.tsx` | 恢复默认 | "恢复所有偏好为默认值" |
| `components\SheetWorkspace\SheetTabs.tsx` | （图标/自闭合按钮） | "关闭此 sheet" |
| `components\SheetWorkspace\SheetTabs.tsx` | （图标/自闭合按钮） | "最小化此 sheet" |
| `components\SheetWorkspace\SheetTabs.tsx` | （图标/自闭合按钮） | "关闭此 sheet" |
| `components\SheetWorkspace\SheetTabs.tsx` | （图标/自闭合按钮） |  |

## pages（336）

| 文件 | 按钮（标签/图标） | Tooltip 文案 |
| --- | --- | --- |
| `pages\About\BrandCard.tsx` | {TEXTS.updateLoading} | "正在检查更新" |
| `pages\About\BrandCard.tsx` | }> {TEXTS.updateLatest} | "已是最新版本" |
| `pages\About\BrandCard.tsx` | } onClick={() => globalThis.open(state.url, '_blank', 'noopener,noreferrer')} > {TEXTS.updateNewer} ({state.latest}) |  |
| `pages\About\BrandCard.tsx` | } onClick={onCheck} > {state.reason === 'network' ? TEXTS.updateErrorNetwork : TEXTS.updateErrorServer} · {TEXTS.updateRetry} | "检查更新失败，点击重试" |
| `pages\About\BrandCard.tsx` | } onClick={onCheck}> {TEXTS.updateIdle} |  |
| `pages\About\BrandCard.tsx` | （图标/自闭合按钮） |  |
| `pages\AntiCrawl\index.tsx` | } onClick={loadAll} loading={loadingStrategy}> 刷新 | "刷新全部数据" |
| `pages\AntiCrawl\index.tsx` | } onClick={handleInitialize} loading={loadingInit} block > 初始化协调器（{useCdp ? 'CDP' : 'Launch'} 模式） | "初始化反爬协调器，启动登录策略" |
| `pages\AntiCrawl\index.tsx` | 更新 Cookie | "打开分层 Cookie 更新弹窗" |
| `pages\AntiCrawl\index.tsx` | （图标/自闭合按钮） | "刷新 Cookie 层状态" |
| `pages\AntiCrawl\index.tsx` | } onClick={() => handleInvalidateLayer(layer)} style={{ padding: '4px 0', fontSize: 12 }} > 主动失效 | "主动失效该 Cookie 层" |
| `pages\AntiCrawl\index.tsx` | （图标/自闭合按钮） | "刷新频率伪装统计" |
| `pages\AntiCrawl\index.tsx` | } loading={loadingImport} onClick={handleImportFromBrowser} style={{ flex: 1 }} > 从浏览器导入（覆盖文本框） | "从浏览器导入 Cookie 覆盖文本框" |
| `pages\AntiCrawl\index.tsx` | } onClick={onStart} loading={loadingSession} disabled={session?.active} > 启动会话 | "启动会话管理并开始续期" |
| `pages\AntiCrawl\index.tsx` | } onClick={onStop} loading={loadingSession} disabled={!session?.active} > 停止会话 | "停止会话管理与后台续期" |
| `pages\AntiCrawl\index.tsx` | } onClick={onCheck} loading={loadingHealth} size="small" > 检查 | "执行健康检查" |
| `pages\Chatbot\Config.tsx` | updateConfig('welcome_message', '')} style={{ paddingLeft: 0, marginTop: 4 }} > 恢复默认 | "清空欢迎语，恢复默认文案" |
| `pages\Chatbot\Config.tsx` | } disabled={record.is_current} onClick={() => handleRollback(record.id)} > 回滚 | "回滚知识库至该版本" |
| `pages\Chatbot\Config.tsx` | } style={{ marginBottom: 16 }} onClick={() => { setEditingFaq(null); setFaqModalOpen(true) }} > 新增 FAQ | "新增一条 FAQ" |
| `pages\Chatbot\Config.tsx` | { setEditingFaq(record); setFaqModalOpen(true) }}>编辑 | "编辑该条 FAQ" |
| `pages\Chatbot\Config.tsx` | （图标/自闭合按钮） | "删除该条 FAQ" |
| `pages\Chatbot\Config.tsx` | 刷新 | "刷新审计日志列表" |
| `pages\Chatbot\index.tsx` | } block onClick={handleCreateSession} className="cb-new-btn" > 新建会话 | "新建一个会话" |
| `pages\Chatbot\index.tsx` | （图标/自闭合按钮） | "切换只显示收藏的会话" |
| `pages\Chatbot\index.tsx` | 清空 | "清空搜索历史" |
| `pages\Chatbot\index.tsx` | } onClick={() => setHelpOpen(true)} className="cb-action-btn" > 帮助中心 | "打开帮助中心" |
| `pages\Chatbot\index.tsx` | } onClick={handleEscalate} loading={escalating} className="cb-action-btn cb-action-btn-escalate" > 立即转人工 | "转接至人工客服" |
| `pages\Chatbot\index.tsx` | （图标/自闭合按钮） | "打开会话列表" |
| `pages\Chatbot\index.tsx` | （图标/自闭合按钮） | "上传图片（最多 4 张）" |
| `pages\Chatbot\index.tsx` | } onClick={onStop} className="cb-stop-btn"> 停止 | "停止当前流式生成" |
| `pages\Chatbot\index.tsx` | 发送 | "发送消息（Enter）" |
| `pages\Chatbot\index.tsx` | } onClick={handleRetry} className="cb-msg-retry-btn" > 发送失败 · 重试 | "重新发送该消息" |
| `pages\Chatbot\index.tsx` | 撤回 | "撤回这条消息（2 分钟内）" |
| `pages\Chatbot\components\AssistantMessage.tsx` | } onClick={copySession}> 复制会话记录 | "复制当前会话记录到剪贴板" |
| `pages\Chatbot\components\ChatbotOnboarding.tsx` | （图标/自闭合按钮） | "关闭引导卡片" |
| `pages\Chatbot\components\KBStatusCard.tsx` | } onClick={handleRebuild} loading={isBuilding} disabled={isBuilding} > 重建 | "重建知识库索引（使用最新文档）" |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | } onClick={loadAll} loading={loading}>刷新 | "刷新向量库状态、快照与审计日志" |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | } onClick={() => setSnapshotModalOpen(true)} > 创建快照 | "为当前集合创建一份快照备份" |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | }>恢复 | "用该快照覆盖当前集合数据" |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | }>删除 | "删除该快照文件，不影响当前集合" |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | }>清空集合 | "删除集合内全部片段（危险操作）" |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | } onClick={() => setCleanupSourceOpen(true)}> 按来源文件删除 | "按来源文件删除其全部片段" |
| `pages\Chatbot\components\VectorAdminPanel.tsx` | } onClick={loadAll}>刷新 | "刷新向量库维护审计日志" |
| `pages\Config\BuyerStrategy.tsx` | } onClick={reset} disabled={!hasChanges()}> 重置 | "放弃未保存的修改并重置" |
| `pages\Config\BuyerStrategy.tsx` | } onClick={handleSave} loading={saving}> 保存 | "保存抢单策略配置" |
| `pages\Config\EvalRules.tsx` | } onClick={reset} disabled={!hasChanges()}> 重置 | "放弃未保存的修改并重置" |
| `pages\Config\EvalRules.tsx` | } onClick={handleSave} loading={saving}> 保存 | "保存评估规则配置" |
| `pages\Config\EvalRules.tsx` | 一键归一化 | "将权重总和自动归一化为 100" |
| `pages\Config\EvalRules.tsx` | revertField('eval.pass_score')} style={{ padding: 0, fontSize: 12 }}>⏪ | "恢复 pass_score 原始值" |
| `pages\Config\EvalRules.tsx` | revertField('eval.auto_buy_score')} style={{ padding: 0, fontSize: 12 }}>⏪ | "恢复 auto_buy_score 原始值" |
| `pages\Config\EvalRules.tsx` | onRevert?.(revertPath)} style={{ padding: 0, fontSize: 12 }}> ⏪ | "恢复该项权重原始值" |
| `pages\Config\PriceStrategy.tsx` | } onClick={reset} disabled={!hasChanges()}> 重置 | "放弃未保存的修改并重置" |
| `pages\Config\PriceStrategy.tsx` | } onClick={handleSave} loading={saving}> 保存 | "保存价格策略配置" |
| `pages\Config\PriceStrategy.tsx` | setStrategy({ ...strategy, max_price: getFieldOriginal('price_strategy.max_price') as number })} style={{ padding: 0, fontSize: 12 }}> | "恢复最高价原始值" |
| `pages\Config\PriceStrategy.tsx` | setStrategy({ ...strategy, min_price: getFieldOriginal('price_strategy.min_price') as number })} style={{ padding: 0, fontSize: 12 }}> | "恢复最低价原始值" |
| `pages\Config\PriceStrategy.tsx` | setStrategy({ ...strategy, market_ratio: getFieldOriginal('price_strategy.market_ratio') as number })} style={{ padding: 0, fontSize: 12 }}> | "恢复市场价比例原始值" |
| `pages\Config\PriceStrategy.tsx` | setStrategy({ ...strategy, top_n: getFieldOriginal('price_strategy.top_n') as number })} style={{ padding: 0, fontSize: 12 }}> | "恢复 TopN 原始值" |
| `pages\Config\PriceStrategy.tsx` | } loading={previewing} onClick={() => { setPreviewing(true) setTimeout(() => { setPreviewing(false) message.success('预览已刷新') }, 500) }} > 刷新预览数据 | "重新生成策略命中预览数据" |
| `pages\Config\SearchConfig.tsx` | } onClick={reset} disabled={!hasChanges()}> 重置 | "放弃未保存的修改并重置" |
| `pages\Config\SearchConfig.tsx` | } onClick={handleSave} loading={saving}> 保存配置 | "保存搜索参数配置" |
| `pages\Config\SearchConfig.tsx` | { if (filterTags.includes(tag)) { setFilterTags(filterTags.filter((t) => t !== tag)) } else { setFilterTags([...filterTags, tag]) } }} style={{ fontSize: 12, // 选中时由 type="primary" 提供橙底白字；未选中时用橙色描边+文字做主题暗示 borderColor: filterTags.includes(tag) ? undefined : '#FF6200', color: filterTags.includes(tag) ? undefined : '#FF6200', }} > {tag} |  |
| `pages\Config\VersionManager.tsx` | } onClick={load} loading={loading}> 刷新 | "重新加载版本与备份信息" |
| `pages\Config\VersionManager.tsx` | } onClick={handleExport}> 导出配置 | "导出当前配置为 JSON 文件" |
| `pages\Config\VersionManager.tsx` | } onClick={handleShare} loading={shareLoading}> 分享配置 | "生成脱敏配置用于分享" |
| `pages\Config\VersionManager.tsx` | }>导入配置 | "从 JSON 文件导入配置" |
| `pages\Config\VersionManager.tsx` | } onClick={handleRollback} disabled={backups.length === 0} block > 一键回滚 | "回滚到上一版本备份" |
| `pages\Config\VersionManager.tsx` | { setSelectedBackup(backup) setDiffModalVisible(true) }} > 查看详情 | "查看该备份的详细信息" |
| `pages\Config\VersionManager.tsx` | } onClick={() => handleRestore(backup)} > 恢复 | "从该备份恢复配置" |
| `pages\Config\VersionManager.tsx` | setDiffModalVisible(false)}> 关闭 | "关闭备份详情弹窗" |
| `pages\Config\VersionManager.tsx` | } onClick={() => { if (selectedBackup) { handleRestore(selectedBackup) setDiffModalVisible(false) } }} > 从此备份恢复 | "用当前备份覆盖现有配置" |
| `pages\Config\VersionManager.tsx` | setShareModalOpen(false)}> 关闭 | "关闭分享配置弹窗" |
| `pages\Config\VersionManager.tsx` | } onClick={handleCopyShare}> 复制到剪贴板 | "复制配置文本到剪贴板" |
| `pages\Config\AIConfig\components\BudgetSettings.tsx` | 保存预算设置 | "保存当前预算设置" |
| `pages\Config\AIConfig\components\EmbeddingConfigForm.tsx` | : } onClick={onToggleShowApiKey} > {showApiKey ? '隐藏' : '显示'} | "切换显示或隐藏 API Key 明文" |
| `pages\Config\AIConfig\components\EmbeddingConfigForm.tsx` | } loading={testing} onClick={onTestConnection} disabled={!config.ai_enabled} > {testing ? '测试中…（本地首次加载模型较慢）' : '🔗 测试 Embedding 连接'} | "测试 Embedding 连接是否可用" |
| `pages\Config\AIConfig\components\ModelConfigForm.tsx` | : } onClick={onToggleShowApiKey} > {showApiKey ? '隐藏' : '显示'} | "切换显示或隐藏 API Key 明文" |
| `pages\Config\AIConfig\components\ModelConfigForm.tsx` | 获取 | "前往厂商 API Key 申请页" |
| `pages\Config\AIConfig\components\ModelConfigForm.tsx` | 保存配置 | "保存 LLM 配置" |
| `pages\Config\AIConfig\components\ModelConfigForm.tsx` | } loading={testing} onClick={onTestConnection} disabled={!config.ai_enabled} > {testing ? '测试中…' : '🔗 测试连接'} | "测试 LLM 连接是否可用" |
| `pages\Config\NotifierChannels\index.tsx` | } onClick={reset} disabled={!hasChanges()}> 重置 | "放弃未保存的修改并重置" |
| `pages\Config\NotifierChannels\index.tsx` | } onClick={handleSave} loading={loading}> 保存 | "保存通知渠道配置" |
| `pages\Config\NotifierChannels\components\ChannelCard.tsx` | } onClick={() => onTest(ch.key)} block loading={testing} disabled={anyTesting && !testing} > {testing ? '发送中...' : '发送测试'} | "向该渠道发送测试推送消息" |
| `pages\ConfirmBuy\index.tsx` | navigate('/')}> 返回首页 | "返回系统首页" |
| `pages\ConfirmBuy\index.tsx` | navigate('/evaluations')}>查看评估列表 | "前往评估明细列表" |
| `pages\ConfirmBuy\index.tsx` | navigate('/')}>返回首页 | "返回系统首页" |
| `pages\ConfirmBuy\index.tsx` | } onClick={() => navigate('/evaluations')}> 返回评估列表 | "返回评估明细列表" |
| `pages\ConfirmBuy\index.tsx` | } loading={submitting} onClick={handleConfirm} > 确认抢单 | "创建待支付订单并提交抢单" |
| `pages\ConfirmBuy\index.tsx` | navigate('/evaluations')}> 取消 | "放弃抢单并返回评估列表" |
| `pages\Dashboard\index.tsx` | navigate('/tasks/new')} tip="创建新的监控任务"> 创建任务 |  |
| `pages\Dashboard\index.tsx` | navigate('/onboarding')} tip="查看新手引导说明"> 查看引导 |  |
| `pages\Dashboard\components\AlertRadar.tsx` | （图标/自闭合按钮） | "重新拉取最新预警数据" |
| `pages\Dashboard\components\EventStreamSection.tsx` | onNavigate('/timeline')} tip="跳转事件时间线查看全部事件">查看全部 |  |
| `pages\Dashboard\components\EventStreamSection.tsx` | onNavigate('/tasks')} tip="进入任务管理页面">任务管理 |  |
| `pages\Dashboard\components\EventStreamSection.tsx` | onNavigate('/config/ai')} tip="进入 AI 配置页面">配置 |  |
| `pages\Dashboard\components\EventStreamSection.tsx` | onNavigate('/logs')} tip="进入实时日志页面">实时日志 |  |
| `pages\Dashboard\components\EventStreamSection.tsx` | onNavigate('/orders')} tip="进入抢单记录页面">抢单记录 |  |
| `pages\Dashboard\components\PriceHistogramCard.tsx` | onNavigate('/items')} tip="进入商品列表页面">查看商品 |  |
| `pages\Dashboard\components\PriceHistogramCard.tsx` | } loading={aiLoading} onClick={onAiAnalyze} size="small" tip="基于价格分布调用 AI 生成分析建议" > AI 智能分析 |  |
| `pages\Dashboard\components\PriceHistogramCard.tsx` | 清除 | "清除当前 AI 分析结果" |
| `pages\Dashboard\components\TrendModal.tsx` | onRangeChange(h)} tip={h === 168 ? '查看近 7 天趋势' : h === 720 ? '查看近 30 天趋势' : '查看近 90 天趋势'}> {(() => { // 时间范围文案 if (h === 168) return '7 天' if (h === 720) return '30 天' return '90 天' })()} |  |
| `pages\Evaluations\index.tsx` | } onClick={fetchSuggestion} style={{ marginTop: 8 }} block tip="根据目标通过率计算建议评分阈值"> 计算建议阈值 |  |
| `pages\Evaluations\index.tsx` | } loading={batchAIEvaluating} onClick={onBatchAIEval} tip="对选中商品批量执行 AI 成色评估"> 批量 AI 评估 ({selectedCount} 项) |  |
| `pages\Evaluations\index.tsx` | } loading={batchCollecting} onClick={onBatchCollectOfficial} tip="对选中商品批量访问官方页面采集"> 批量官方采集 ({selectedCount} 项) |  |
| `pages\Evaluations\index.tsx` | 取消选择 | "取消已选中的商品" |
| `pages\Evaluations\index.tsx` | } onClick={onSearch} tip="按当前筛选条件查询评估记录">查询 |  |
| `pages\Evaluations\index.tsx` | } onClick={onReset} tip="重置全部筛选条件">重置 |  |
| `pages\Evaluations\index.tsx` | } onClick={list.load} loading={list.loading} tip="重新加载评估列表数据">刷新 |  |
| `pages\Evaluations\index.tsx` | } onClick={batch.onRecompute} loading={batch.recomputing} tip="重新计算所有商品评估分值">重新评估 |  |
| `pages\Evaluations\index.tsx` | } onClick={batch.onBatchEvaluateUnevaluated} loading={batch.batchEvaluating} tip="对尚未评估的商品批量评估">批量评估未评估商品 |  |
| `pages\Evaluations\index.tsx` | } onClick={() => setColumnConfigOpen(true)} tip="打开列显示与排序配置">列配置 |  |
| `pages\Evaluations\index.tsx` | （图标/自闭合按钮） |  |
| `pages\Evaluations\components\AIEvalModal.tsx` | 关闭 | "关闭 AI 评估弹窗" |
| `pages\Evaluations\components\CollectResultModal.tsx` | 关闭 | "关闭官方采集结果弹窗" |
| `pages\Evaluations\components\ColumnSettingsModal.tsx` | } onClick={onReset} tip="恢复列为默认顺序与显示状态"> 恢复默认 |  |
| `pages\Evaluations\components\ColumnSettingsModal.tsx` | 完成 | "保存列配置并关闭弹窗" |
| `pages\Evaluations\components\DeepAnalyzeModal.tsx` | 关闭 | "关闭 AI 深度鉴伪弹窗" |
| `pages\Evaluations\components\TrendSparkline.tsx` | } onClick={onLoad} tip="加载该卖家的价格趋势数据"> 加载卖家价格趋势 |  |
| `pages\Evaluations\hooks\useEvalColumns.tsx` | （图标/自闭合按钮） |  |
| `pages\Evaluations\hooks\useEvalColumns.tsx` | （图标/自闭合按钮） | "AI 成色评估" |
| `pages\Evaluations\hooks\useEvalColumns.tsx` | （图标/自闭合按钮） | "深度鉴伪（盗图/损坏/一致性/模板）" |
| `pages\Evaluations\hooks\useEvalColumns.tsx` | （图标/自闭合按钮） | "访问闲鱼官方页面采集完整数据并重新评估" |
| `pages\Evaluations\hooks\useEvalColumns.tsx` | （图标/自闭合按钮） |  |
| `pages\Export\index.tsx` | } onClick={() => handleExport(ds.key)} > 导出 CSV |  |
| `pages\Help\index.tsx` | } onClick={() => globalThis.open(`${API_BASE}api/docs`, '_blank')} > API 文档 | "在新标签页打开 API 文档" |
| `pages\Items\ItemList.tsx` | （图标/自闭合按钮） | "删除此商品关联（不可恢复）" |
| `pages\Items\ItemList.tsx` | } onClick={() => navigate(`/?redirect=${encodeURIComponent('/items')}`)} > 重新登录 | "前往登录页刷新闲鱼 Cookie" |
| `pages\Items\ItemList.tsx` | } loading={liveLoading} onClick={loadLive} disabled={!selectedTask} > 实时搜索 | "调用闲鱼实时搜索并写入最新商品" |
| `pages\Items\ItemList.tsx` | } onClick={handleRefresh} loading={loading \|\| liveLoading \|\| refreshing} disabled={!selectedTask} > 刷新 | "刷新当前任务的商品数据" |
| `pages\Items\ItemList.tsx` | 秒 | "轮询间隔单位（秒）" |
| `pages\Items\ItemList.tsx` | } onClick={() => navigate('/tasks')}> 管理任务 | "前往任务管理页面" |
| `pages\Items\ItemList.tsx` | } onClick={() => setColumnConfigOpen(true)} disabled={viewMode !== 'table'} > 列配置 | "拖拽调整列顺序或显示/隐藏字段" |
| `pages\Items\ItemList.tsx` | 清空 | "清空搜索历史关键词" |
| `pages\Login\index.tsx` | } onClick={onStart} loading={startingBrowser} style={{ background: '#FF6200', borderColor: '#FF6200', width: 'fit-content' }} > 启动浏览器窗口登录 | "启动浏览器窗口并手动登录闲鱼" |
| `pages\Login\index.tsx` | } onClick={onCancel}> 取消登录 | "取消当前登录过程" |
| `pages\Login\index.tsx` | } onClick={onStart} loading={startingBrowser} style={{ background: '#FF6200', borderColor: '#FF6200' }}> 重新登录 | "重新启动浏览器窗口登录" |
| `pages\Login\index.tsx` | } loading={autoFilling} onClick={onAutoFill} > {autoFilling ? '读取中…' : '从浏览器自动获取'} | "从系统浏览器读取 Cookie 并填充" |
| `pages\Login\index.tsx` | } onClick={onClear}> 清空 | "清空已填写的 Cookie 字段" |
| `pages\Login\index.tsx` | } loading={injecting} onClick={onInject} disabled={!hasAnyCookie} style={{ background: '#FF6200', borderColor: '#FF6200' }} > 注入 Cookie 登录 | "注入 Cookie 完成登录" |
| `pages\Login\index.tsx` | } size="small" loading={injecting}> 上传文件 | "从文件导入 Cookie" |
| `pages\Login\index.tsx` | } loading={importing} onClick={() => onImport('edge')} disabled={!browserStatus?.edge?.exists} style={{ background: '#FF6200', borderColor: '#FF6200' }} > 从 Edge 导入 | "从 Edge 浏览器导入 Cookie" |
| `pages\Login\index.tsx` | } loading={importing} onClick={() => onImport('chrome')} disabled={!browserStatus?.chrome?.exists} > 从 Chrome 导入 | "从 Chrome 浏览器导入 Cookie" |
| `pages\Login\index.tsx` | } onClick={onOpenBrowser}> 打开闲鱼网页 | "在系统浏览器打开闲鱼登录页" |
| `pages\Login\index.tsx` | } loading={importing} onClick={() => onImport('edge', true)} disabled={!browserStatus?.edge?.exists} danger > 自动关闭 Edge 并导入 | "自动关闭 Edge 后导入 Cookie" |
| `pages\Login\index.tsx` | } loading={importing} onClick={() => onImport('chrome', true)} disabled={!browserStatus?.chrome?.exists} danger > 自动关闭 Chrome 并导入 | "自动关闭 Chrome 后导入 Cookie" |
| `pages\Login\index.tsx` | } onClick={onRefreshStatus}> 刷新检测 | "重新检测浏览器状态" |
| `pages\Login\index.tsx` | } onClick={() => setTutorialVisible(true)} style={{ color: themeToken.colorTextSecondary }} > 如何获取 Cookie？ | "查看获取 Cookie 的图文教程" |
| `pages\Login\index.tsx` | setTutorialVisible(false)}>知道了 | "关闭教程弹窗" |
| `pages\Logs\ErrorLogs.tsx` | } onClick={handleCopyAi}> 复制 | "复制 AI 上下文到剪贴板" |
| `pages\Logs\ErrorLogs.tsx` | } onClick={loadList} loading={loading} block> 刷新 | "重新加载错误日志列表" |
| `pages\Logs\ErrorLogs.tsx` | } block> 批量清理 | "清理 30 天前已解决/已忽略的日志" |
| `pages\Logs\ErrorLogs.tsx` | } onClick={() => doSearch()}> 搜索 | "按状态与错误类型搜索日志" |
| `pages\Logs\ErrorLogs.tsx` | 清空 | "清空搜索历史关键词" |
| `pages\Logs\ErrorLogs.tsx` | } loading={batchLoading} onClick={() => handleBatchAction('resolved', '已标记为已解决')} > 标记已解决 | "将选中项标记为已解决" |
| `pages\Logs\ErrorLogs.tsx` | } loading={batchLoading} onClick={() => handleBatchAction('ignored', '已标记为已忽略')} > 标记已忽略 | "将选中项标记为已忽略" |
| `pages\Logs\ErrorLogs.tsx` | } loading={batchLoading} > 批量删除 | "批量删除选中的错误日志" |
| `pages\Logs\ErrorLogs.tsx` | 取消选择 | "清除当前勾选" |
| `pages\Logs\ErrorLogs.tsx` | （图标/自闭合按钮） | "删除该条错误日志" |
| `pages\Logs\Logs.tsx` | : } onClick={streaming ? stopStream : startStream} block > {streaming ? '停止实时流' : '开启实时流'} |  |
| `pages\Logs\Logs.tsx` | : } onClick={togglePause} style={{ flex: 1 }} > {paused ? '恢复' : '暂停'} |  |
| `pages\Logs\Logs.tsx` | } onClick={clearStreamLogs} danger style={{ flex: 1 }} > 清空 | "清空当前显示的实时流日志" |
| `pages\Logs\Logs.tsx` | } onClick={search} loading={searchLoading}>搜索 | "按关键词/级别/任务搜索日志" |
| `pages\Logs\Logs.tsx` | } href={logApi.exportUrl('csv')} target="_blank">导出CSV | "导出当前日志为 CSV 文件" |
| `pages\Logs\Logs.tsx` | } href={logApi.exportUrl('log')} target="_blank">导出LOG | "导出当前日志为 LOG 文件" |
| `pages\Logs\Logs.tsx` | } onClick={loadRaw} loading={loading} size="small">刷新 | "重新加载原始日志" |
| `pages\Maintenance\BatchRefresh.tsx` | } onClick={() => loadStatus()} loading={loading}> 刷新状态 | "刷新当前批次执行状态" |
| `pages\Maintenance\BatchRefresh.tsx` | } loading={saving} disabled={unavailable} onClick={handleSaveConfig} > 保存 | "保存并热更新配置" |
| `pages\Maintenance\BatchRefresh.tsx` | } loading={triggering} disabled={unavailable \|\| inProgress} onClick={handleTrigger} block style={{ marginBottom: 12 }} > 立即触发批量采集 |  |
| `pages\Maintenance\BatchRefresh.tsx` | } loading={controlling === 'pause'} disabled={!running} onClick={handlePause} > 暂停 | "暂停当前批次，采集完成后生效" |
| `pages\Maintenance\BatchRefresh.tsx` | } loading={controlling === 'resume'} disabled={!paused} onClick={handleResume} > 继续 | "从断点继续批量采集" |
| `pages\Maintenance\BatchRefresh.tsx` | } loading={controlling === 'stop'} disabled={!inProgress} onClick={handleStop} > 停止（持久化进度，可续传） | "停止批次并持久化进度" |
| `pages\Maintenance\BatchRefresh.tsx` | } onClick={() => handleViewDetail(r)} > 详情 | "查看该条执行历史详情" |
| `pages\Maintenance\BatchRefresh.tsx` | }> 删除 | "删除该条历史记录，操作不可恢复" |
| `pages\Maintenance\BatchRefresh.tsx` | } onClick={handleSearch}> 查询 | "按筛选条件查询执行历史" |
| `pages\Maintenance\BatchRefresh.tsx` | 重置 | "重置所有筛选条件" |
| `pages\Maintenance\BatchRefresh.tsx` | }>清理 30 天前 | "清理 30 天前的历史记录" |
| `pages\Maintenance\BatchRefresh.tsx` | }>清空全部 | "清空全部历史记录，不可恢复" |
| `pages\Maintenance\BatchRefresh.tsx` | } onClick={loadList} loading={loading}> 刷新 | "重新加载执行历史列表" |
| `pages\Maintenance\Cleanup.tsx` | } onClick={loadStatus} loading={loading}> 刷新状态 | "刷新存储状态概览" |
| `pages\Maintenance\Cleanup.tsx` | } block loading={cacheLoading} onClick={handleCleanupCache} style={{ backgroundColor: cacheForm.dry_run ? undefined : '#ff4d4f' }} > 清理缓存 | "清理所选范围的缓存（预览或真实执行）" |
| `pages\Maintenance\Cleanup.tsx` | } block loading={dbLoading} onClick={handleCleanupDatabase} style={{ backgroundColor: dbForm.dry_run ? undefined : '#ff4d4f' }} > 清理数据库 | "清理数据库冗余数据（预览或真实执行）" |
| `pages\Maintenance\Cleanup.tsx` | } block loading={logLoading} onClick={handleCleanupLogs} style={{ backgroundColor: logForm.dry_run ? undefined : '#ff4d4f' }} > 清理日志 | "清理旧日志文件释放磁盘空间" |
| `pages\Maintenance\DatabaseAdmin.tsx` | } onClick={() => { loadAuditLog(); setAuditDrawerOpen(true) }}> 审计日志 | "查看数据库维护审计日志" |
| `pages\Maintenance\DatabaseAdmin.tsx` | } onClick={() => { loadTables(); loadRows() }} loading={rowsLoading}> 刷新 | "刷新表列表与数据" |
| `pages\Maintenance\DatabaseAdmin.tsx` | } onClick={() => { form.resetFields(); setEditing({ mode: 'create' }) }}> 新增 | "新增一行记录" |
| `pages\Maintenance\DatabaseAdmin.tsx` | } disabled={selectedRowKeys.length === 0} onClick={openBatchDeleteConfirm}> 批量删除 {selectedRowKeys.length > 0 && `(${selectedRowKeys.length})`} | "批量删除选中行（需确认）" |
| `pages\Maintenance\DatabaseAdmin.tsx` | } onClick={() => setImportOpen(true)}> 导入 | "打开数据导入弹窗" |
| `pages\Maintenance\DatabaseAdmin.tsx` | } onClick={() => handleExport('csv')}> 导出 CSV | "导出当前表数据为 CSV" |
| `pages\Maintenance\DatabaseAdmin.tsx` | } onClick={() => handleExport('json')}> 导出 JSON | "导出当前表数据为 JSON" |
| `pages\Maintenance\DatabaseAdmin.tsx` | } onClick={() => setSchemaDrawerOpen(true)}> 查看表结构 | "查看当前表字段结构" |
| `pages\Maintenance\DatabaseAdmin.tsx` | { setPage(1); doSearch() }}>查询 | "按关键词查询表数据" |
| `pages\Maintenance\DatabaseAdmin.tsx` | 清空 | "清空搜索历史关键词" |
| `pages\Maintenance\DatabaseAdmin.tsx` | } onClick={() => { form.resetFields() form.setFieldsValue(record) setEditing({ mode: 'update', row: record }) }} > 编辑 | "编辑该行记录" |
| `pages\Maintenance\DatabaseAdmin.tsx` | } tip="删除该行（需输入确认码）" onClick={() => openDeleteConfirm(record[pkCol!.name])}>删除 |  |
| `pages\Maintenance\DatabaseAdmin.tsx` | }>选择 CSV 文件 | "选择本地 CSV 文件上传" |
| `pages\Maintenance\DatabaseAdmin.tsx` | }>选择 JSON 文件 | "选择本地 JSON 文件上传" |
| `pages\Maintenance\Tunnel.tsx` | : undefined} loading={loginLoading} onClick={handleLogin} disabled={loginLoading \|\| loginPolling} > {loginButtonText} | "执行 Cloudflare 授权登录" |
| `pages\Maintenance\Tunnel.tsx` | : undefined} loading={createLoading} onClick={handleCreate} disabled={!config.cert_file \|\| createLoading} > {config.tunnel_id ? '重新创建' : '创建隧道'} | "创建命名隧道（或重新创建）" |
| `pages\Maintenance\Tunnel.tsx` | : undefined} loading={dnsLoading} onClick={handleRouteDns} disabled={!config.tunnel_id \|\| dnsLoading} > {config.hostname ? '重新配置' : '配置路由'} | "配置 DNS 路由（CNAME 记录）" |
| `pages\Maintenance\Tunnel.tsx` | } loading={starting} disabled={isRunning} onClick={handleStart} > 启动隧道 | "启动隧道建立公网连接" |
| `pages\Maintenance\Tunnel.tsx` | } loading={stopping} disabled={!isRunning} onClick={handleStop} > 停止 | "停止当前隧道" |
| `pages\Maintenance\Tunnel.tsx` | （图标/自闭合按钮） | "在新窗口打开公网地址" |
| `pages\Maintenance\Tunnel.tsx` | {url.length > 60 ? url.slice(0, 60) + '...' : url} | "下载 cloudflared 二进制文件" |
| `pages\Maintenance\Tunnel.tsx` | } href={tailscaleAuthError.auth_url} target="_blank" rel="noopener noreferrer" style={{ marginTop: 8 }} > 打开 Tailscale Funnel 授权页面 | "打开 Tailscale Funnel 授权页面" |
| `pages\Maintenance\Tunnel.tsx` | handleSaveConfig()} > 保存配置 | "保存隧道配置（下次启动生效）" |
| `pages\Maintenance\VectorAdmin.tsx` | } onClick={loadAuditLogs}>审计日志 | "查看向量库审计日志" |
| `pages\Maintenance\VectorAdmin.tsx` | } onClick={loadAll} loading={loading}>刷新 | "重新加载向量库状态" |
| `pages\Maintenance\VectorAdmin.tsx` | } onClick={() => setCreateOpen(true)} > 创建快照 | "创建向量库快照备份" |
| `pages\Maintenance\VectorAdmin.tsx` | } onClick={() => handleRestore(record)} > 恢复 | "从快照恢复并覆盖当前集合" |
| `pages\Maintenance\VectorAdmin.tsx` | } onClick={() => handleDeleteSnapshot(record)} > 删除 | "删除该快照（不可恢复）" |
| `pages\Maintenance\VectorAdmin.tsx` | } onClick={handleCleanupAll}> 清空集合 | "清空集合中全部片段" |
| `pages\Maintenance\VectorAdmin.tsx` | } onClick={handleCleanupBySource}> 删除 | "删除指定来源的所有片段" |
| `pages\MenuAdmin\index.tsx` | （图标/自闭合按钮） | "返回上一页" |
| `pages\MenuAdmin\index.tsx` | } onClick={() => void loadMenus()} disabled={loading \|\| saving \|\| resetting} > 刷新 | "重新加载菜单配置" |
| `pages\MenuAdmin\index.tsx` | } disabled={loading \|\| saving \|\| resetting}> 重置为默认 | "重置为默认菜单配置" |
| `pages\MenuAdmin\index.tsx` | } onClick={() => void handleSave()} disabled={!hasDirty \|\| loading \|\| saving \|\| resetting} loading={saving} > 保存{hasDirty ? ` (${rows.filter((r) => r.dirty).length})` : ''} | "保存菜单配置修改" |
| `pages\Notifications\index.tsx` | } onClick={handleMarkAllRead} loading={actionLoading} disabled={unreadCount === 0} block > 全部标记已读 | "将所有未读通知标记为已读" |
| `pages\Notifications\index.tsx` | } danger disabled={readCount === 0} block> 清空已读 | "清空所有已读通知（不可恢复）" |
| `pages\Notifications\index.tsx` | （图标/自闭合按钮） | "刷新通知列表与未读数" |
| `pages\Notifications\index.tsx` | setFilter(s)} > {label} |  |
| `pages\Notifications\index.tsx` | } onClick={() => handleMarkRead(item)} > 标记已读 | "标记该通知为已读" |
| `pages\Notifications\index.tsx` | }> 删除 | "删除该通知（不可恢复）" |
| `pages\Onboarding\index.tsx` | } onClick={() => copyCommand('python -m xianyu_hunter qr-login')} > 复制 | "复制扫码登录命令" |
| `pages\Onboarding\index.tsx` | } loading={checking} onClick={checkLogin} > 刷新登录状态 | "刷新并检测当前登录状态" |
| `pages\Onboarding\index.tsx` | } loading={submitting} onClick={handleCreateTask} block > 创建任务 | "创建监控任务" |
| `pages\Onboarding\index.tsx` | setCurrent(3)}> 下一步 | "进入下一步配置通知" |
| `pages\Onboarding\index.tsx` | } onClick={() => copyCommand('python -m xianyu_hunter worker')} > 复制 | "复制启动调度器命令" |
| `pages\Onboarding\index.tsx` | setCurrent(4)} block> 完成设置 | "完成初始化设置" |
| `pages\Onboarding\index.tsx` | navigate('/')}> 进入仪表盘 | "进入系统仪表盘" |
| `pages\Onboarding\index.tsx` | setCurrent(current - 1)}> 上一步 | "返回上一步" |
| `pages\Onboarding\index.tsx` | setCurrent(current + 1)}> 跳过 | "跳过本步骤" |
| `pages\Orders\Orders.tsx` | 取消 | "关闭接管弹窗" |
| `pages\Orders\Orders.tsx` | } loading={loading} onClick={handleTakeover}> 确认接管 | "开始接管此订单" |
| `pages\Orders\Orders.tsx` | } loading={loading} onClick={handleCancel}> 取消接管 | "取消接管并保留订单为待处理" |
| `pages\Orders\Orders.tsx` | } loading={loading} onClick={handleConfirm}> 确认完成 | "确认已在闲鱼完成支付" |
| `pages\Orders\Orders.tsx` | 关闭 | "关闭完成提示" |
| `pages\Orders\Orders.tsx` | } size="small" onClick={() => openTakeoverModal(r)} > {r.status === 'pending' ? '接管' : '查看'} |  |
| `pages\Orders\Orders.tsx` | } size="small"> 删除 | "删除此订单（不可恢复）" |
| `pages\Orders\Orders.tsx` | } onClick={load} loading={loading}>刷新 | "重新加载订单列表" |
| `pages\Orders\Orders.tsx` | } onClick={() => setColumnConfigOpen(true)}>列配置 | "自定义表格显示列与顺序" |
| `pages\PriceDashboard\components\BargainEvalCard.tsx` | （图标/自闭合按钮） | "刷新评估结果与分位数数据" |
| `pages\PriceDashboard\components\BargainEvalCard.tsx` | 评估 | "按当前价格评估捡漏等级与得分" |
| `pages\PriceDashboard\components\CategoryComparisonChart.tsx` | （图标/自闭合按钮） | "刷新品类对比图表数据" |
| `pages\PriceDashboard\components\CategoryStatsTable.tsx` | （图标/自闭合按钮） | "刷新品类统计明细数据" |
| `pages\PriceDashboard\components\SoldRangeCard.tsx` | （图标/自闭合按钮） | "刷新捡漏价格参考数据" |
| `pages\Tasks\TaskDetail.tsx` | （图标/自闭合按钮） | "打开原帖" |
| `pages\Tasks\TaskDetail.tsx` | （图标/自闭合按钮） | "删除该关联" |
| `pages\Tasks\TaskDetail.tsx` | } onClick={() => navigate('/tasks')}>返回列表 | "返回任务列表" |
| `pages\Tasks\TaskDetail.tsx` | } onClick={load} loading={loading}>刷新 | "重新加载任务详情" |
| `pages\Tasks\TaskDetail.tsx` | } loading={actionLoading} onClick={() => handleControl('restart')} disabled={task.status === 'running'}>启动 | "启动或重启该任务" |
| `pages\Tasks\TaskDetail.tsx` | } loading={actionLoading} onClick={() => handleControl('pause')} disabled={task.status !== 'running'}>暂停 | "暂停当前运行中的任务" |
| `pages\Tasks\TaskDetail.tsx` | } loading={actionLoading} onClick={() => handleControl('stop')} disabled={task.status === 'stopped'}>停止 | "停止当前任务" |
| `pages\Tasks\TaskDetail.tsx` | navigate(`/tasks/${task.id}/edit`)}>编辑 | "编辑该任务配置" |
| `pages\Tasks\TaskDetail.tsx` | } onClick={loadAllTasks} > 添加依赖 | "加载可选任务以添加上游依赖" |
| `pages\Tasks\TaskDetail.tsx` | 添加 | "添加选中的上游依赖" |
| `pages\Tasks\TaskDetail.tsx` | 移除 | "移除该上游依赖" |
| `pages\Tasks\TaskDetail.tsx` | } loading={liveLoading} onClick={handleLive} > 实时查询 | "实时查询最新关联数据" |
| `pages\Tasks\TaskDetail.tsx` | } loading={refreshLoading} onClick={handleRefresh} > 刷新数据源 | "重新拉取并写入数据源" |
| `pages\Tasks\TaskEditor.tsx` | } onClick={() => navigate('/tasks')} style={{ marginBottom: 16 }}> 返回列表 | "返回任务列表" |
| `pages\Tasks\TaskEditor.tsx` | 清除草稿 | "清除本地草稿" |
| `pages\Tasks\TaskEditor.tsx` | navigate('/tasks')}>返回列表 | "返回任务列表" |
| `pages\Tasks\TaskEditor.tsx` | navigate('/login')} style={{ background: '#FF6200', borderColor: '#FF6200' }}> 前往登录 | "前往登录页" |
| `pages\Tasks\TaskEditor.tsx` | } onClick={() => setSearchConfigModalOpen(true)} > 全局搜索配置 | "编辑全局搜索配置" |
| `pages\Tasks\TaskEditor.tsx` | } onClick={() => setAntidetectModalOpen(true)} > 修改全局反检测配置 | "编辑全局反检测配置" |
| `pages\Tasks\TaskEditor.tsx` | } onClick={() => setBatchRefreshModalOpen(true)} > 批量采集配置 | "编辑全局批量采集配置" |
| `pages\Tasks\TaskEditor.tsx` | setCurrent(current - 1)} icon={ } > 上一步 | "返回上一步" |
| `pages\Tasks\TaskEditor.tsx` | }> 下一步 | "进入下一步" |
| `pages\Tasks\TaskEditor.tsx` | }> {isEdit ? '保存修改' : '创建任务'} | "提交创建或保存任务" |
| `pages\Tasks\TaskEditor.tsx` | } onClick={onOpenGlobalConfig} > 全局 AI 评估配置 | "编辑全局 AI 评估配置" |
| `pages\Tasks\TaskEditor.tsx` | setFormData({ ...formData, eval_threshold: null })} disabled={formData.eval_threshold === null} > 重置为全局 | "重置评估阈值为全局值" |
| `pages\Tasks\TaskEditor.tsx` | { const next = { ...formData.eval_config } delete next.auto_collect_official setFormData({ ...formData, eval_config: Object.keys(next).length > 0 ? next : null }) }} disabled={formData.eval_config?.auto_collect_official == null} > 重置为全局 | "重置自动采集开关为全局值" |
| `pages\Tasks\TaskEditor.tsx` | { const next = { ...formData.eval_config } delete next.auto_collect_max_per_run setFormData({ ...formData, eval_config: Object.keys(next).length > 0 ? next : null }) }} disabled={formData.eval_config?.auto_collect_max_per_run == null} > 重置为全局 | "重置每轮采集条数为全局值" |
| `pages\Tasks\TaskEditor.tsx` | 取消 | "关闭弹窗" |
| `pages\Tasks\TaskEditor.tsx` | } onClick={reset} disabled={!hasChanges()}>重置 | "重置为初始配置" |
| `pages\Tasks\TaskEditor.tsx` | } loading={saving} onClick={handleSave}>保存 | "保存配置" |
| `pages\Tasks\TaskEditor.tsx` | setDiffModalOpen(false)}>取消 | "取消保存" |
| `pages\Tasks\TaskEditor.tsx` | 确认保存 | "确认保存并写入配置" |
| `pages\Tasks\TaskEditor.tsx` | 取消 | "关闭弹窗" |
| `pages\Tasks\TaskEditor.tsx` | } onClick={reset} disabled={!hasChanges()}>重置 | "重置为初始配置" |
| `pages\Tasks\TaskEditor.tsx` | } loading={saving} onClick={handleSave}>保存 | "保存配置" |
| `pages\Tasks\TaskEditor.tsx` | setDiffModalOpen(false)}>取消 | "取消保存" |
| `pages\Tasks\TaskEditor.tsx` | 确认保存 | "确认保存并写入配置" |
| `pages\Tasks\TaskEditor.tsx` | 取消 | "关闭弹窗" |
| `pages\Tasks\TaskEditor.tsx` | } onClick={reset} disabled={!hasChanges()}>重置 | "重置为初始配置" |
| `pages\Tasks\TaskEditor.tsx` | } loading={saving} onClick={() => previewConfigSave({ setSaving, previewSave, setDiffChanges, setDiffModalOpen })}>保存 | "保存配置" |
| `pages\Tasks\TaskEditor.tsx` | setDiffModalOpen(false)}>取消 | "取消保存" |
| `pages\Tasks\TaskEditor.tsx` | 确认保存 | "确认保存并写入配置" |
| `pages\Tasks\TaskEditor.tsx` | 取消 | "关闭弹窗" |
| `pages\Tasks\TaskEditor.tsx` | } onClick={reset} disabled={!hasChanges()}>重置 | "重置为初始配置" |
| `pages\Tasks\TaskEditor.tsx` | } loading={saving} onClick={handleSave}>保存 | "保存配置" |
| `pages\Tasks\TaskEditor.tsx` | setDiffModalOpen(false)}>取消 | "取消保存" |
| `pages\Tasks\TaskEditor.tsx` | 确认保存 | "确认保存并写入配置" |
| `pages\Tasks\TaskList.tsx` | （图标/自闭合按钮） | "打开原帖" |
| `pages\Tasks\TaskList.tsx` | （图标/自闭合按钮） | "删除该关联" |
| `pages\Tasks\TaskList.tsx` | navigate(`/tasks/${record.id}/edit`)} style={{ padding: 0 }}>{text} | "打开该任务编辑页" |
| `pages\Tasks\TaskList.tsx` | navigate(`/tasks/${record.id}`)} style={{ padding: 0 }}> {linkCounts[record.id] ?? '-'} | "查看该任务详情与关联数" |
| `pages\Tasks\TaskList.tsx` | executeArmConfirm(record.id)}> 确认{arm.label} | "确认执行该危险操作" |
| `pages\Tasks\TaskList.tsx` | cancelArmConfirm(record.id)}> 取消 | "取消本次危险操作确认" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => navigate(`/tasks/${record.id}/edit`)}> 编辑 | "编辑该任务" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => handleAction(record.id, 'pause')}> 暂停 | "暂停该任务" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => handleAction(record.id, 'start')}> 启动 | "启动该任务" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => doArmConfirm(record.id, 'stop', '停止', '停止后任务将不再运行')}> 停止 | "停止该任务（需二次确认）" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => cloneTask(record)}> 复制 | "复制该任务为新任务" |
| `pages\Tasks\TaskList.tsx` | （图标/自闭合按钮） | "展开更多操作" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => doArmConfirm(record.id, 'delete', '删除', '删除后不可恢复')}> 删除 | "删除该任务（需二次确认）" |
| `pages\Tasks\TaskList.tsx` | } onClick={openAiParse}> 智能建任务 | "用一句话 AI 智能创建任务" |
| `pages\Tasks\TaskList.tsx` | } onClick={openTemplateMarket}> 模板市场 | "打开任务模板市场" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => navigate('/tasks/new')}> 新增任务 | "新建一个任务" |
| `pages\Tasks\TaskList.tsx` | } loading={startAllLoading} onClick={handleStartAll} disabled={tasks.length === 0} > 全部启动 | "一键启动所有非运行中的任务" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => handleBatchAction('pause')}>暂停 | "批量暂停选中任务" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => handleBatchAction('resume')}>恢复 | "批量恢复选中任务" |
| `pages\Tasks\TaskList.tsx` | } danger onClick={() => handleBatchAction('stop')}>停止 | "批量停止选中任务" |
| `pages\Tasks\TaskList.tsx` | } danger onClick={() => handleBatchAction('delete')}>删除 | "批量删除选中任务" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => setSelectedRowKeys([])}>清除选择 | "清除已选中的任务" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => handleAction(task.id, 'pause')}>暂停 | "暂停该任务" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => handleAction(task.id, 'start')}>启动 | "启动该任务" |
| `pages\Tasks\TaskList.tsx` | navigate(`/tasks/${task.id}/edit`)} style={{ padding: 0, fontWeight: 600 }}>{task.name \|\| task.keyword} | "打开该任务编辑页" |
| `pages\Tasks\TaskList.tsx` | executeArmConfirm(task.id)}> 确认{arm.label} | "确认执行该危险操作" |
| `pages\Tasks\TaskList.tsx` | cancelArmConfirm(task.id)}>取消 | "取消本次危险操作确认" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => navigate(`/tasks/${task.id}/edit`)}>编辑 | "编辑该任务" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => doArmConfirm(task.id, 'stop', '停止', '停止后任务将不再运行')}>停止 | "停止该任务（需二次确认）" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => cloneTask(task)}>复制 | "复制该任务为新任务" |
| `pages\Tasks\TaskList.tsx` | （图标/自闭合按钮） | "展开更多操作" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => doArmConfirm(task.id, 'delete', '删除', '删除后不可恢复')}>删除 | "删除该任务（需二次确认）" |
| `pages\Tasks\TaskList.tsx` | setPage(page - 1)}>上一页 | "返回上一页" |
| `pages\Tasks\TaskList.tsx` | = Math.ceil(total / pageSize)} onClick={() => setPage(page + 1)}>下一页 | "前往下一页" |
| `pages\Tasks\TaskList.tsx` | } loading={liveLoading} onClick={handleLive} disabled={!linkTaskId \|\| searchingIds.has(linkTaskId)} > {searchingIds.has(linkTaskId) ? '自动搜索中...' : '实时查询'} | "实时查询关联数据" |
| `pages\Tasks\TaskList.tsx` | setFilteredModalOpen(true)} > 查看被过滤的 {liveFilterSummary.filtered_out.length} 条结果 | "查看被实时搜索过滤掉的结果" |
| `pages\Tasks\TaskList.tsx` | } onClick={() => setAddModalOpen(true)} disabled={!linkTaskId} > 手动添加 | "手动添加一条关联" |
| `pages\Tasks\TaskList.tsx` | setAiModalOpen(false)}>取消 | "关闭智能建任务弹窗" |
| `pages\Tasks\TaskList.tsx` | 用此结果继续 → | "用解析结果前往创建任务" |
| `pages\Tasks\TaskList.tsx` | }> 开始解析 | "让 AI 解析需求并创建任务" |
| `pages\Tasks\TaskList.tsx` | （图标/自闭合按钮） | "删除该私有模板" |
| `pages\Timeline\components\TimelineFilter.tsx` | } onClick={onReload} loading={loading}>刷新 | "重新加载时间线数据" |
| `pages\Timeline\components\TimelineFilter.tsx` | } onClick={onSyncFromNotifier}> 同步订阅 | "从通知配置同步订阅规则" |
| `pages\Timeline\components\TimelineFilter.tsx` | onEventTypeFilterChange([])}> 清除过滤 | "清除事件类型过滤" |
| `pages\Timeline\components\TimelineItem.tsx` | onToggleExpand(idx)} > {isExpanded ? '收起详情' : '查看详情'} | "展开或收起该事件的详细载荷" |
