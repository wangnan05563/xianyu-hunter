# 按钮 Tooltip 文案对照表

> 范围：`src/` 下所有使用共享组件 `<TipButton>`（默认导入 `TipButton`）的页面与组件。
> 统计：共 **363** 个 `TipButton` 用法，分布于 **63** 个源文件（不含组件定义文件本身 `components/TipButton.tsx`）。
> 列说明：**文件**（相对 `src/`）、**按钮（标签/图标）**、**Tooltip 文案**、**功能说明**（≤20 字，依据 onClick / 上下文 / 图标推断）。

## ⚠ 准确性提示（tip 不准确 / 泛化 / 缺失）

| 文件 | 问题 |
| --- | --- |
| `pages/Items/ItemList.tsx` | 一个 `disabled` 的 TipButton 仅作静态单位标签「秒」，tip 为「轮询间隔单位（秒）」，按钮无交互功能，语义不当（应改用纯文本）。 |
| `pages/Evaluations/hooks/useEvalColumns.tsx` | 状态筛选按钮的 `tip={title}`，tip 直接等于动态列标题（如「可抢单」），属于泛化提示，未描述按钮动作（切换筛选）。 |
| `pages/About/BrandCard.tsx` | 多个按钮 tip 来自 `TEXTS.*` 国际化常量（如更新提示、复制提示），静态扫描无法核对最终文案，需结合 i18n 资源确认是否准确。 |
| `pages/Config/SearchConfig.tsx` / `pages/Notifications/index.tsx` / `pages/Maintenance/BatchRefresh.tsx` | 部分按钮 tip 为运行时动态字符串（模板/变量 `filterTip` / `triggerTooltipText`），已按代码语义记录，实际文案随状态变化。 |

---

## src/components

### components/DiffPreviewModal.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| DiffPreviewModal.tsx | 取消 | 取消保存并关闭预览 | 关闭预览弹窗 |
| DiffPreviewModal.tsx | 确认保存 | 确认并保存配置变更 | 保存配置变更 |

### components/ExportButton.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| ExportButton.tsx | 导出 CSV（Download 图标） | 导出 {dataset} 为 CSV（Excel 友好） | 导出单一数据集 |

### components/ErrorBoundary.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| ErrorBoundary.tsx | 重试 | 重新渲染页面，尝试恢复正常 | 重置错误重渲染 |
| ErrorBoundary.tsx | 刷新页面 | 重新加载整个页面 | 刷新整页 |

### components/ReloadPrompt.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| ReloadPrompt.tsx | 稍后 | 稍后更新，关闭此提示 | 关闭更新通知 |
| ReloadPrompt.tsx | 立即刷新 | 立即应用新版本并刷新页面 | 应用 PWA 更新 |
| ReloadPrompt.tsx | 知道了 | 关闭此提示 | 关闭离线提示 |

### components/ParamCalculator/ParamCalculatorPanel.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| ParamCalculatorPanel.tsx | （Reload 图标，无文字） | 重新执行参数校验 | 重新校验参数 |

### components/layout/UserMenu.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| layout/UserMenu.tsx | （Reload 图标） | 刷新用户信息与健康状态 | 刷新用户/Cookie |
| layout/UserMenu.tsx | 换号（Swap 图标） | 切换到其他闲鱼账号 | 切换账号 |
| layout/UserMenu.tsx | 退出（Logout 图标） | 退出当前账号并清除登录态 | 退出登录 |

### components/layout/MainLayout.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| layout/MainLayout.tsx | （菜单折叠图标） | 展开或收起侧边栏 | 切换侧边栏 |
| layout/MainLayout.tsx | （MacCommand 图标） | 打开命令面板（Ctrl+K） | 打开命令面板 |
| layout/MainLayout.tsx | （状态圆点） | 调度器运行中 / 已停止 / 加载中… | 查看仪表盘 |
| layout/MainLayout.tsx | （Bell 图标） | 打开今日告警通知 | 打开告警抽屉 |
| layout/MainLayout.tsx | （Sun/Moon 图标） | 切换为亮/暗色主题 | 切换主题 |
| layout/MainLayout.tsx | （QuestionCircle 图标） | 打开帮助文档 | 打开帮助 |
| layout/MainLayout.tsx | （InfoCircle 图标） | 查看关于与版本信息 | 打开关于 |

### components/SheetWorkspace/SheetTabs.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| SheetWorkspace/SheetTabs.tsx | （缩略图关闭 Close 危险） | 关闭此 sheet | 关闭 sheet |
| SheetWorkspace/SheetTabs.tsx | （Minus 图标） | 最小化此 sheet | 最小化 sheet |
| SheetWorkspace/SheetTabs.tsx | （Close 危险图标） | 关闭此 sheet | 关闭 sheet |
| SheetWorkspace/SheetTabs.tsx | （Setting 图标） | 打开 Sheet 偏好设置（或 sheet 数量） | 打开偏好设置 |

### components/SheetWorkspace/SheetPreferences.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| SheetWorkspace/SheetPreferences.tsx | 清空回收栈 | 清空已淘汰 sheet 的回收记录 | 清空回收栈 |
| SheetWorkspace/SheetPreferences.tsx | 完成 | 关闭偏好设置面板 | 关闭面板 |
| SheetWorkspace/SheetPreferences.tsx | 恢复默认 | 恢复所有偏好为默认值 | 重置偏好 |

### components/SheetWorkspace/sheetNotifications.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| SheetWorkspace/sheetNotifications.tsx | 撤销 | 恢复被自动替换的 sheet | 恢复被替换 sheet |

---

## src/pages/Dashboard

### pages/Dashboard/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Dashboard/index.tsx | 创建任务 | 创建新的监控任务 | 新建任务 |
| Dashboard/index.tsx | 查看引导 | 查看新手引导说明 | 打开引导页 |

### pages/Dashboard/components/TrendModal.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Dashboard/components/TrendModal.tsx | 7 天 / 30 天 / 90 天 | 查看近 7 / 30 / 90 天趋势 | 切换趋势范围 |

### pages/Dashboard/components/PriceHistogramCard.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Dashboard/components/PriceHistogramCard.tsx | 查看商品 | 进入商品列表页面 | 进商品列表 |
| Dashboard/components/PriceHistogramCard.tsx | （Robot 图标） | 基于价格分布调用 AI 生成分析建议 | AI 价格分析 |
| Dashboard/components/PriceHistogramCard.tsx | 清除 | 清除当前 AI 分析结果 | 清除 AI 分析 |

### pages/Dashboard/components/EventStreamSection.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Dashboard/components/EventStreamSection.tsx | 查看全部 | 跳转事件时间线查看全部事件 | 看全部事件 |
| Dashboard/components/EventStreamSection.tsx | 任务管理 | 进入任务管理页面 | 进任务管理 |
| Dashboard/components/EventStreamSection.tsx | 配置 | 进入 AI 配置页面 | 进 AI 配置 |
| Dashboard/components/EventStreamSection.tsx | 实时日志 | 进入实时日志页面 | 进实时日志 |
| Dashboard/components/EventStreamSection.tsx | 抢单记录 | 进入抢单记录页面 | 进抢单记录 |

### pages/Dashboard/components/AlertRadar.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Dashboard/components/AlertRadar.tsx | （Reload 图标） | 重新拉取最新预警数据 | 刷新预警 |

---

## src/pages/Chatbot

### pages/Chatbot/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Chatbot/index.tsx | 新建会话（Plus 图标） | 新建一个会话 | 新建会话 |
| Chatbot/index.tsx | （Star/StarFilled 图标） | 切换只显示收藏的会话 | 筛选收藏会话 |
| Chatbot/index.tsx | 清空 | 清空搜索历史 | 清搜索历史 |
| Chatbot/index.tsx | 打开帮助中心（QuestionCircle） | 打开帮助中心 | 打开帮助中心 |
| Chatbot/index.tsx | 转人工（CustomerService） | 转接至人工客服 | 转人工客服 |
| Chatbot/index.tsx | （Menu 图标） | 打开会话列表 | 打开会话列表 |
| Chatbot/index.tsx | （Picture 图标） | 上传图片（最多 4 张） | 上传图片 |
| Chatbot/index.tsx | 停止（Stop 图标） | 停止当前流式生成 | 停止生成 |
| Chatbot/index.tsx | 发送 | 发送消息（Enter） | 发送消息 |
| Chatbot/index.tsx | （Sync 图标） | 重新发送该消息 | 重发消息 |
| Chatbot/index.tsx | 撤回 | 撤回这条消息（2 分钟内） | 撤回消息 |

### pages/Chatbot/Config.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Chatbot/Config.tsx | （清空欢迎语） | 清空欢迎语，恢复默认文案 | 清欢迎语 |
| Chatbot/Config.tsx | 回滚（Rollback 图标） | 回滚知识库至该版本 | 回滚知识库 |
| Chatbot/Config.tsx | 新增 FAQ（Plus 图标） | 新增一条 FAQ | 新增 FAQ |
| Chatbot/Config.tsx | 编辑 | 编辑该条 FAQ | 编辑 FAQ |
| Chatbot/Config.tsx | 删除（Delete 图标） | 删除该条 FAQ | 删除 FAQ |
| Chatbot/Config.tsx | 刷新 | 刷新审计日志列表 | 刷新审计日志 |

### pages/Chatbot/components/VectorAdminPanel.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Chatbot/components/VectorAdminPanel.tsx | 刷新 | 刷新向量库状态、快照与审计日志 | 刷新向量库 |
| Chatbot/components/VectorAdminPanel.tsx | 创建快照（Camera 图标） | 为当前集合创建一份快照备份 | 建快照备份 |
| Chatbot/components/VectorAdminPanel.tsx | 恢复（Rollback 图标） | 用该快照覆盖当前集合数据 | 恢复快照 |
| Chatbot/components/VectorAdminPanel.tsx | 删除（Delete 图标） | 删除该快照文件，不影响当前集合 | 删快照文件 |
| Chatbot/components/VectorAdminPanel.tsx | 清空集合（Delete 危险） | 删除集合内全部片段（危险操作） | 清空集合 |
| Chatbot/components/VectorAdminPanel.tsx | 按来源文件删除（FileSearch） | 按来源文件删除其全部片段 | 按来源删除 |
| Chatbot/components/VectorAdminPanel.tsx | 刷新（审计日志） | 刷新向量库维护审计日志 | 刷新审计日志 |

### pages/Chatbot/components/AssistantMessage.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Chatbot/components/AssistantMessage.tsx | 复制会话记录（Copy 图标） | 复制当前会话记录到剪贴板 | 复制会话 |

### pages/Chatbot/components/KBStatusCard.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Chatbot/components/KBStatusCard.tsx | （Reload 图标） | 重建知识库索引（使用最新文档） | 重建索引 |

### pages/Chatbot/components/ChatbotOnboarding.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Chatbot/components/ChatbotOnboarding.tsx | （Close 图标） | 关闭引导卡片 | 关闭引导卡 |

---

## src/pages/Items

### pages/Items/ItemList.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Items/ItemList.tsx | （Delete 危险图标） | 删除此商品关联（不可恢复） | 删商品关联 |
| Items/ItemList.tsx | 重新登录（Login 图标） | 前往登录页刷新闲鱼 Cookie | 去登录页 |
| Items/ItemList.tsx | （Search 图标） | 调用闲鱼实时搜索并写入最新商品 | 实时搜索 |
| Items/ItemList.tsx | （Reload 图标） | 刷新当前任务的商品数据 | 刷新商品 |
| Items/ItemList.tsx | 秒（disabled） | 轮询间隔单位（秒） | ⚠ 静态单位标签 |
| Items/ItemList.tsx | 管理任务（Link 图标） | 前往任务管理页面 | 进任务管理 |
| Items/ItemList.tsx | 列配置（Setting 图标） | 拖拽调整列顺序或显示/隐藏字段 | 列配置 |
| Items/ItemList.tsx | 清空 | 清空搜索历史关键词 | 清搜索历史 |

---

## src/pages/About

### pages/About/BrandCard.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| About/BrandCard.tsx | （更新中，loading） | 正在检查更新 | 检查更新中 |
| About/BrandCard.tsx | （CheckCircle 图标，已最新） | 已是最新版本 | 已是最新 |
| About/BrandCard.tsx | （ArrowUp 图标，新版本） | 显示发布时间 / 有新版本可用 | 去下载更新 |
| About/BrandCard.tsx | （Warning 图标，失败） | 检查更新失败，点击重试 | 重试更新 |
| About/BrandCard.tsx | （Reload 图标） | 检查更新提示文案（i18n） | 检查更新 |
| About/BrandCard.tsx | （Copy 图标） | 复制提示文案（i18n） | 复制版本信息 |

---

## src/pages/Timeline

### pages/Timeline/components/TimelineItem.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Timeline/components/TimelineItem.tsx | （link，展开） | 展开或收起该事件的详细载荷 | 展开详情 |

### pages/Timeline/components/TimelineFilter.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Timeline/components/TimelineFilter.tsx | 刷新 | 重新加载时间线数据 | 刷新时间线 |
| Timeline/components/TimelineFilter.tsx | 同步订阅（Sync 图标） | 从通知配置同步订阅规则 | 同步订阅 |
| Timeline/components/TimelineFilter.tsx | 清除过滤 | 清除事件类型过滤 | 清过滤 |

---

## src/pages/ConfirmBuy

### pages/ConfirmBuy/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| ConfirmBuy/index.tsx | 返回首页 | 返回系统首页 | 回首页 |
| ConfirmBuy/index.tsx | 查看评估列表 | 前往评估明细列表 | 看评估列表 |
| ConfirmBuy/index.tsx | 返回首页 | 返回系统首页 | 回首页 |
| ConfirmBuy/index.tsx | 返回评估列表（ArrowLeft） | 返回评估明细列表 | 回评估列表 |
| ConfirmBuy/index.tsx | 确认抢单（Thunderbolt） | 创建待支付订单并提交抢单 | 提交抢单 |
| ConfirmBuy/index.tsx | 取消 | 放弃抢单并返回评估列表 | 放弃抢单 |

---

## src/pages/Help

### pages/Help/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Help/index.tsx | （Api 图标） | 在新标签页打开 API 文档 | 打开 API 文档 |

---

## src/pages/Config

### pages/Config/BuyerStrategy.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Config/BuyerStrategy.tsx | 重置（Undo 图标） | 放弃未保存的修改并重置 | 重置修改 |
| Config/BuyerStrategy.tsx | 保存（Save 图标） | 保存抢单策略配置 | 保存策略 |

### pages/Config/SearchConfig.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Config/SearchConfig.tsx | 重置（Undo 图标） | 放弃未保存的修改并重置 | 重置修改 |
| Config/SearchConfig.tsx | 保存配置（Save 图标） | 保存搜索参数配置 | 保存配置 |
| Config/SearchConfig.tsx | 筛选标签（动态 tag） | 点击切换筛选标签「{tag}」 | 切换筛选 |

### pages/Config/PriceStrategy.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Config/PriceStrategy.tsx | 重置（Revert 图标） | 放弃未保存的修改并重置 | 重置修改 |
| Config/PriceStrategy.tsx | 保存（Save 图标） | 保存价格策略配置 | 保存策略 |
| Config/PriceStrategy.tsx | 恢复最高价 | 恢复最高价原始值 | 恢复最高价 |
| Config/PriceStrategy.tsx | 恢复最低价 | 恢复最低价原始值 | 恢复最低价 |
| Config/PriceStrategy.tsx | 恢复市场价比例 | 恢复市场价比例原始值 | 恢复比例 |
| Config/PriceStrategy.tsx | 恢复 TopN | 恢复 TopN 原始值 | 恢复 TopN |
| Config/PriceStrategy.tsx | 重新生成预览（Experiment） | 重新生成策略命中预览数据 | 生成预览 |

### pages/Config/EvalRules.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Config/EvalRules.tsx | 重置（Undo 图标） | 放弃未保存的修改并重置 | 重置修改 |
| Config/EvalRules.tsx | 保存（Save 图标） | 保存评估规则配置 | 保存规则 |
| Config/EvalRules.tsx | 一键归一化 | 将权重总和自动归一化为 100 | 权重归一化 |
| Config/EvalRules.tsx | ⏪ | 恢复 pass_score 原始值 | 恢复阈值 |
| Config/EvalRules.tsx | ⏪ | 恢复 auto_buy_score 原始值 | 恢复阈值 |
| Config/EvalRules.tsx | ⏪ | 恢复该项权重原始值 | 恢复权重 |

### pages/Config/VersionManager.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Config/VersionManager.tsx | 刷新 | 重新加载版本与备份信息 | 刷新版本 |
| Config/VersionManager.tsx | 导出配置（Download） | 导出当前配置为 JSON 文件 | 导出配置 |
| Config/VersionManager.tsx | 分享配置（ShareAlt） | 生成脱敏配置用于分享 | 分享配置 |
| Config/VersionManager.tsx | 导入配置（Upload） | 从 JSON 文件导入配置 | 导入配置 |
| Config/VersionManager.tsx | 回滚（Rollback 危险） | 回滚到上一版本备份 | 回滚版本 |
| Config/VersionManager.tsx | 查看 | 查看该备份的详细信息 | 看备份详情 |
| Config/VersionManager.tsx | 恢复（Rollback 虚线） | 从该备份恢复配置 | 恢复备份 |
| Config/VersionManager.tsx | 关闭 | 关闭备份详情弹窗 | 关弹窗 |
| Config/VersionManager.tsx | 用当前备份覆盖现有配置 | 用当前备份覆盖现有配置 | 覆盖配置 |
| Config/VersionManager.tsx | 关闭 | 关闭分享配置弹窗 | 关弹窗 |
| Config/VersionManager.tsx | 复制到剪贴板（Copy） | 复制配置文本到剪贴板 | 复制配置 |

### pages/Config/AIConfig/components/ModelConfigForm.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Config/AIConfig/components/ModelConfigForm.tsx | （Eye/EyeInvisible 图标） | 切换显示或隐藏 API Key 明文 | 显隐密钥 |
| Config/AIConfig/components/ModelConfigForm.tsx | 获取 | 前往厂商 API Key 申请页 | 去申请密钥 |
| Config/AIConfig/components/ModelConfigForm.tsx | 保存配置 | 保存 LLM 配置 | 保存 LLM |
| Config/AIConfig/components/ModelConfigForm.tsx | （Api 图标） | 测试 LLM 连接是否可用 | 测试连接 |

### pages/Config/AIConfig/components/EmbeddingConfigForm.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Config/AIConfig/components/EmbeddingConfigForm.tsx | （Eye/EyeInvisible 图标） | 切换显示或隐藏 API Key 明文 | 显隐密钥 |
| Config/AIConfig/components/EmbeddingConfigForm.tsx | （Api 图标） | 测试 Embedding 连接是否可用 | 测试连接 |

### pages/Config/AIConfig/components/BudgetSettings.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Config/AIConfig/components/BudgetSettings.tsx | 保存预算设置 | 保存当前预算设置 | 保存预算 |

### pages/Config/NotifierChannels/components/ChannelCard.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Config/NotifierChannels/components/ChannelCard.tsx | （Send 图标） | 向该渠道发送测试推送消息 | 测试推送 |

### pages/Config/NotifierChannels/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Config/NotifierChannels/index.tsx | 重置（Undo 图标） | 放弃未保存的修改并重置 | 重置修改 |
| Config/NotifierChannels/index.tsx | 保存（Save 图标） | 保存通知渠道配置 | 保存渠道 |

---

## src/pages/Evaluations

### pages/Evaluations/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Evaluations/index.tsx | 计算建议阈值（Aim 图标） | 根据目标通过率计算建议评分阈值 | 算建议阈值 |
| Evaluations/index.tsx | 批量 AI 评估（Robot 图标） | 对选中商品批量执行 AI 成色评估 | 批量 AI 评估 |
| Evaluations/index.tsx | 批量官方采集（CloudDownload） | 对选中商品批量访问官方页面采集 | 批量采集 |
| Evaluations/index.tsx | 取消选择 | 取消已选中的商品 | 取消选择 |
| Evaluations/index.tsx | 查询（Search 图标） | 按当前筛选条件查询评估记录 | 查询记录 |
| Evaluations/index.tsx | 重置（Undo 图标） | 重置全部筛选条件 | 重置筛选 |
| Evaluations/index.tsx | 刷新（Reload 图标） | 重新加载评估列表数据 | 刷新列表 |
| Evaluations/index.tsx | 重新评估（Retweet 图标） | 重新计算所有商品评估分值 | 重算评估 |
| Evaluations/index.tsx | 批量评估未评估商品（Retweet） | 对尚未评估的商品批量评估 | 批量评估 |
| Evaluations/index.tsx | 列配置（Setting 图标） | 打开列显示与排序配置 | 列配置 |
| Evaluations/index.tsx | （折叠箭头图标） | 展开分析面板 / 收起分析面板 | 切换面板 |

### pages/Evaluations/hooks/useEvalColumns.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Evaluations/hooks/useEvalColumns.tsx | 状态筛选（动态图标） | {title}（动态列标题） | ⚠ 切换状态筛选 |
| Evaluations/hooks/useEvalColumns.tsx | （Robot 图标） | AI 成色评估 | AI 评估 |
| Evaluations/hooks/useEvalColumns.tsx | （Thunderbolt 图标） | 深度鉴伪（盗图/损坏/一致性/模板） | 深度鉴伪 |
| Evaluations/hooks/useEvalColumns.tsx | （CloudDownload 图标） | 访问闲鱼官方页面采集完整数据并重新评估 | 官方采集 |
| Evaluations/hooks/useEvalColumns.tsx | （Thunderbolt 图标，主） | 手动抢单（评分 ≥ 阈值） | 手动抢单 |

### pages/Evaluations/components/AIEvalModal.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Evaluations/components/AIEvalModal.tsx | 关闭 | 关闭 AI 评估弹窗 | 关闭弹窗 |

### pages/Evaluations/components/CollectResultModal.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Evaluations/components/CollectResultModal.tsx | 关闭 | 关闭官方采集结果弹窗 | 关闭弹窗 |

### pages/Evaluations/components/DeepAnalyzeModal.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Evaluations/components/DeepAnalyzeModal.tsx | 关闭 | 关闭 AI 深度鉴伪弹窗 | 关闭弹窗 |

### pages/Evaluations/components/ColumnSettingsModal.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Evaluations/components/ColumnSettingsModal.tsx | 恢复默认（Undo 图标） | 恢复列为默认顺序与显示状态 | 恢复列默认 |
| Evaluations/components/ColumnSettingsModal.tsx | 完成（主） | 保存列配置并关闭弹窗 | 保存列配置 |

### pages/Evaluations/components/TrendSparkline.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Evaluations/components/TrendSparkline.tsx | 加载卖家价格趋势（LineChart） | 加载该卖家的价格趋势数据 | 加载趋势 |

---

## src/pages/AntiCrawl

### pages/AntiCrawl/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| AntiCrawl/index.tsx | 刷新 | 刷新全部数据 | 刷新全部 |
| AntiCrawl/index.tsx | 初始化（PlayCircle 图标） | 初始化反爬协调器，启动登录策略 | 初始化协调器 |
| AntiCrawl/index.tsx | 更新 Cookie | 打开分层 Cookie 更新弹窗 | 开 Cookie 弹窗 |
| AntiCrawl/index.tsx | （Reload 图标） | 刷新 Cookie 层状态 | 刷 Cookie 层 |
| AntiCrawl/index.tsx | （Stop 危险图标） | 主动失效该 Cookie 层 | 失效 Cookie 层 |
| AntiCrawl/index.tsx | （Reload 图标） | 刷新频率伪装统计 | 刷频率统计 |
| AntiCrawl/index.tsx | （Download 图标） | 从浏览器导入 Cookie 覆盖文本框 | 导入 Cookie |
| AntiCrawl/index.tsx | 启动会话（PlayCircle 图标） | 启动会话管理并开始续期 | 启动会话 |
| AntiCrawl/index.tsx | 停止会话（Stop 危险） | 停止会话管理与后台续期 | 停止会话 |
| AntiCrawl/index.tsx | （Reload 图标） | 执行健康检查 | 健康检查 |

---

## src/pages/Tasks

### pages/Tasks/TaskList.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Tasks/TaskList.tsx | （Eye 图标，表格） | 打开原帖 | 看原帖 |
| Tasks/TaskList.tsx | （MinusCircle 危险，表格） | 删除该关联 | 删关联 |
| Tasks/TaskList.tsx | 任务名（link，表格） | 打开该任务编辑页 | 编辑任务 |
| Tasks/TaskList.tsx | （Link 图标，关联数） | 查看该任务详情与关联数 | 看详情/关联 |
| Tasks/TaskList.tsx | 确认{arm.label}（危险） | 确认执行该危险操作 | 确认危险操作 |
| Tasks/TaskList.tsx | 取消 | 取消本次危险操作确认 | 取消确认 |
| Tasks/TaskList.tsx | 编辑（Edit 图标） | 编辑该任务 | 编辑任务 |
| Tasks/TaskList.tsx | 暂停（PauseCircle 图标） | 暂停该任务 | 暂停任务 |
| Tasks/TaskList.tsx | 启动（PlayCircle 图标） | 启动该任务 | 启动任务 |
| Tasks/TaskList.tsx | 停止（Stop 危险） | 停止该任务（需二次确认） | 停止任务 |
| Tasks/TaskList.tsx | 复制（Copy 图标） | 复制该任务为新任务 | 复制任务 |
| Tasks/TaskList.tsx | （More 图标） | 展开更多操作 | 更多操作 |
| Tasks/TaskList.tsx | 删除（Delete 危险） | 删除该任务（需二次确认） | 删除任务 |
| Tasks/TaskList.tsx | 智能建任务（Thunderbolt） | 用一句话 AI 智能创建任务 | AI 建任务 |
| Tasks/TaskList.tsx | 模板市场（Appstore 图标） | 打开任务模板市场 | 模板市场 |
| Tasks/TaskList.tsx | 新增任务（Plus 图标） | 新建一个任务 | 新建任务 |
| Tasks/TaskList.tsx | 一键启动全部（Thunderbolt） | 一键启动所有非运行中的任务 | 批量启动 |
| Tasks/TaskList.tsx | 批量暂停 | 批量暂停选中任务 | 批量暂停 |
| Tasks/TaskList.tsx | 批量恢复 | 批量恢复选中任务 | 批量恢复 |
| Tasks/TaskList.tsx | 批量停止（危险） | 批量停止选中任务 | 批量停止 |
| Tasks/TaskList.tsx | 批量删除（危险） | 批量删除选中任务 | 批量删除 |
| Tasks/TaskList.tsx | 清除选择 | 清除已选中的任务 | 清选择 |
| Tasks/TaskList.tsx | （Eye 图标，卡片） | 打开原帖 | 看原帖 |
| Tasks/TaskList.tsx | （MinusCircle 危险，卡片） | 删除该关联 | 删关联 |
| Tasks/TaskList.tsx | 任务名（link，卡片） | 打开该任务编辑页 | 编辑任务 |
| Tasks/TaskList.tsx | 确认{arm.label}（危险，卡片） | 确认执行该危险操作 | 确认危险操作 |
| Tasks/TaskList.tsx | 取消（卡片） | 取消本次危险操作确认 | 取消确认 |
| Tasks/TaskList.tsx | 编辑（Edit 图标，卡片） | 编辑该任务 | 编辑任务 |
| Tasks/TaskList.tsx | 暂停（PauseCircle，卡片） | 暂停该任务 | 暂停任务 |
| Tasks/TaskList.tsx | 启动（PlayCircle，卡片） | 启动该任务 | 启动任务 |
| Tasks/TaskList.tsx | 停止（Stop 危险，卡片） | 停止该任务（需二次确认） | 停止任务 |
| Tasks/TaskList.tsx | 复制（Copy 图标，卡片） | 复制该任务为新任务 | 复制任务 |
| Tasks/TaskList.tsx | （More 图标，卡片） | 展开更多操作 | 更多操作 |
| Tasks/TaskList.tsx | 删除（Delete 危险，卡片） | 删除该任务（需二次确认） | 删除任务 |
| Tasks/TaskList.tsx | 上一页 | 返回上一页 | 上一页 |
| Tasks/TaskList.tsx | 下一页 | 前往下一页 | 下一页 |
| Tasks/TaskList.tsx | （Reload 图标，关联弹窗） | 实时查询关联数据 | 实时查询 |
| Tasks/TaskList.tsx | 查看被过滤结果（link） | 查看被实时搜索过滤掉的结果 | 看过滤结果 |
| Tasks/TaskList.tsx | 手动添加一条关联（Plus） | 手动添加一条关联 | 加关联 |
| Tasks/TaskList.tsx | 取消（AI 弹窗） | 关闭智能建任务弹窗 | 关弹窗 |
| Tasks/TaskList.tsx | 用此结果继续 → | 用解析结果前往创建任务 | 继续建任务 |
| Tasks/TaskList.tsx | 开始解析（Thunderbolt） | 让 AI 解析需求并创建任务 | AI 解析 |
| Tasks/TaskList.tsx | （Delete 危险，模板市场） | 删除该私有模板 | 删模板 |

### pages/Tasks/TaskEditor.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Tasks/TaskEditor.tsx | 返回列表（ArrowLeft） | 返回任务列表 | 回列表 |
| Tasks/TaskEditor.tsx | 清除草稿（危险） | 清除本地草稿 | 清草稿 |
| Tasks/TaskEditor.tsx | 返回列表 | 返回任务列表 | 回列表 |
| Tasks/TaskEditor.tsx | 前往登录（主） | 前往登录页 | 去登录 |
| Tasks/TaskEditor.tsx | （Setting 图标） | 编辑全局搜索配置 | 编辑搜索配置 |
| Tasks/TaskEditor.tsx | （Setting 图标） | 编辑全局反检测配置 | 编辑反检测 |
| Tasks/TaskEditor.tsx | （CloudDownload 图标） | 编辑全局批量采集配置 | 编辑采集配置 |
| Tasks/TaskEditor.tsx | （ArrowLeft 图标） | 返回上一步 | 上一步 |
| Tasks/TaskEditor.tsx | 下一步（ArrowRight 主） | 进入下一步 | 下一步 |
| Tasks/TaskEditor.tsx | 创建任务 / 保存修改（CheckCircle 主） | 提交创建或保存任务 | 提交/保存 |
| Tasks/TaskEditor.tsx | （Setting 图标） | 编辑全局 AI 评估配置 | 编辑 AI 配置 |
| Tasks/TaskEditor.tsx | 重置评估阈值 | 重置评估阈值为全局值 | 重置阈值 |
| Tasks/TaskEditor.tsx | 重置自动采集 | 重置自动采集开关为全局值 | 重置采集 |
| Tasks/TaskEditor.tsx | 重置每轮采集条数 | 重置每轮采集条数为全局值 | 重置条数 |
| Tasks/TaskEditor.tsx | 取消（弹窗） | 关闭弹窗 | 关弹窗 |
| Tasks/TaskEditor.tsx | 重置（Undo 图标） | 重置为初始配置 | 重置配置 |
| Tasks/TaskEditor.tsx | 保存（Save 图标） | 保存配置 | 保存配置 |
| Tasks/TaskEditor.tsx | 取消（diff 弹窗） | 取消保存 | 取消保存 |
| Tasks/TaskEditor.tsx | 确认保存（主） | 确认保存并写入配置 | 确认保存 |
| Tasks/TaskEditor.tsx | 取消（弹窗） | 关闭弹窗 | 关弹窗 |
| Tasks/TaskEditor.tsx | 重置（Undo 图标） | 重置为初始配置 | 重置配置 |
| Tasks/TaskEditor.tsx | 保存（Save 图标） | 保存配置 | 保存配置 |
| Tasks/TaskEditor.tsx | 取消（diff 弹窗） | 取消保存 | 取消保存 |
| Tasks/TaskEditor.tsx | 确认保存（主） | 确认保存并写入配置 | 确认保存 |
| Tasks/TaskEditor.tsx | 取消（弹窗） | 关闭弹窗 | 关弹窗 |
| Tasks/TaskEditor.tsx | 重置（Undo 图标） | 重置为初始配置 | 重置配置 |
| Tasks/TaskEditor.tsx | 保存（Save 图标） | 保存配置 | 保存配置 |
| Tasks/TaskEditor.tsx | 取消（diff 弹窗） | 取消保存 | 取消保存 |
| Tasks/TaskEditor.tsx | 确认保存（主） | 确认保存并写入配置 | 确认保存 |
| Tasks/TaskEditor.tsx | 取消（弹窗） | 关闭弹窗 | 关弹窗 |
| Tasks/TaskEditor.tsx | 重置（Undo 图标） | 重置为初始配置 | 重置配置 |
| Tasks/TaskEditor.tsx | 保存（Save 图标） | 保存配置 | 保存配置 |
| Tasks/TaskEditor.tsx | 取消（diff 弹窗） | 取消保存 | 取消保存 |
| Tasks/TaskEditor.tsx | 确认保存（主） | 确认保存并写入配置 | 确认保存 |

### pages/Tasks/TaskDetail.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Tasks/TaskDetail.tsx | （Eye 图标） | 打开原帖 | 看原帖 |
| Tasks/TaskDetail.tsx | （Delete 危险图标） | 删除该关联 | 删关联 |
| Tasks/TaskDetail.tsx | 返回列表（ArrowLeft） | 返回任务列表 | 回列表 |
| Tasks/TaskDetail.tsx | 刷新（Reload 图标） | 重新加载任务详情 | 刷新详情 |
| Tasks/TaskDetail.tsx | 启动（PlayCircle 主） | 启动或重启该任务 | 启动任务 |
| Tasks/TaskDetail.tsx | 暂停（PauseCircle） | 暂停当前运行中的任务 | 暂停任务 |
| Tasks/TaskDetail.tsx | 停止（Stop 危险） | 停止当前任务 | 停止任务 |
| Tasks/TaskDetail.tsx | 编辑 | 编辑该任务配置 | 编辑任务 |
| Tasks/TaskDetail.tsx | 添加上游依赖（Plus link） | 加载可选任务以添加上游依赖 | 加依赖 |
| Tasks/TaskDetail.tsx | 添加选中（主） | 添加选中的上游依赖 | 确认加依赖 |
| Tasks/TaskDetail.tsx | 移除（link 危险） | 移除该上游依赖 | 移除依赖 |
| Tasks/TaskDetail.tsx | 实时查询（Search 图标） | 实时查询最新关联数据 | 实时查询 |
| Tasks/TaskDetail.tsx | 刷新数据源（Sync 图标） | 重新拉取并写入数据源 | 刷数据源 |

---

## src/pages/Notifications

### pages/Notifications/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Notifications/index.tsx | 标记全部已读（CheckSquare 主） | 将所有未读通知标记为已读 | 全部已读 |
| Notifications/index.tsx | 清空已读（Clear 危险） | 清空所有已读通知（不可恢复） | 清空已读 |
| Notifications/index.tsx | （Reload 图标） | 刷新通知列表与未读数 | 刷新通知 |
| Notifications/index.tsx | 筛选标签（动态 filterTip） | {filterTip}（动态） | 切换筛选 |
| Notifications/index.tsx | 标记已读（Check link） | 标记该通知为已读 | 标记已读 |
| Notifications/index.tsx | 删除（Delete link 危险） | 删除该通知（不可恢复） | 删通知 |

---

## src/pages/MenuAdmin

### pages/MenuAdmin/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| MenuAdmin/index.tsx | （ArrowLeft 图标） | 返回上一页 | 返回上页 |
| MenuAdmin/index.tsx | （Reload 图标） | 重新加载菜单配置 | 刷新菜单 |
| MenuAdmin/index.tsx | 重置为默认（Undo 图标） | 重置为默认菜单配置 | 重置菜单 |
| MenuAdmin/index.tsx | 保存（Save 主） | 保存菜单配置修改 | 保存菜单 |

---

## src/pages/Login

### pages/Login/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Login/index.tsx | 启动浏览器登录（Login 主） | 启动浏览器窗口并手动登录闲鱼 | 浏览器登录 |
| Login/index.tsx | 取消登录（Swap 图标） | 取消当前登录过程 | 取消登录 |
| Login/index.tsx | 重新登录（Reload 主） | 重新启动浏览器窗口登录 | 重新登录 |
| Login/index.tsx | （Global 图标） | 从系统浏览器读取 Cookie 并填充 | 读 Cookie |
| Login/index.tsx | 清空（Clear 图标） | 清空已填写的 Cookie 字段 | 清 Cookie |
| Login/index.tsx | 注入 Cookie（Key 主） | 注入 Cookie 完成登录 | 注入登录 |
| Login/index.tsx | 上传文件（Upload 图标） | 从文件导入 Cookie | 文件导入 |
| Login/index.tsx | 从 Edge 导入（Import 主） | 从 Edge 浏览器导入 Cookie | Edge 导入 |
| Login/index.tsx | 从 Chrome 导入（Import） | 从 Chrome 浏览器导入 Cookie | Chrome 导入 |
| Login/index.tsx | 打开闲鱼网页（Reload） | 在系统浏览器打开闲鱼登录页 | 开网页 |
| Login/index.tsx | 自动关闭 Edge 导入（Thunderbolt） | 自动关闭 Edge 后导入 Cookie | 自动 Edge 导入 |
| Login/index.tsx | 自动关闭 Chrome 导入（Thunderbolt） | 自动关闭 Chrome 后导入 Cookie | 自动 Chrome 导入 |
| Login/index.tsx | 刷新检测（Reload） | 重新检测浏览器状态 | 刷新检测 |
| Login/index.tsx | 查看教程（QuestionCircle link） | 查看获取 Cookie 的图文教程 | 看教程 |
| Login/index.tsx | 知道了 | 关闭教程弹窗 | 关弹窗 |

---

## src/pages/PriceDashboard

### pages/PriceDashboard/components/BargainEvalCard.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| PriceDashboard/components/BargainEvalCard.tsx | （Reload 图标） | 刷新评估结果与分位数数据 | 刷新评估 |
| PriceDashboard/components/BargainEvalCard.tsx | 评估（主） | 按当前价格评估捡漏等级与得分 | 评估捡漏 |

### pages/PriceDashboard/components/SoldRangeCard.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| PriceDashboard/components/SoldRangeCard.tsx | （Reload 图标） | 刷新捡漏价格参考数据 | 刷新参考价 |

### pages/PriceDashboard/components/CategoryStatsTable.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| PriceDashboard/components/CategoryStatsTable.tsx | （Reload 图标） | 刷新品类统计明细数据 | 刷新统计 |

### pages/PriceDashboard/components/CategoryComparisonChart.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| PriceDashboard/components/CategoryComparisonChart.tsx | （Reload 图标） | 刷新品类对比图表数据 | 刷新图表 |

---

## src/pages/Logs

### pages/Logs/Logs.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Logs/Logs.tsx | （Play/Pause 主） | 开启实时日志流推送 / 停止并关闭流 | 启停日志流 |
| Logs/Logs.tsx | （Play/Pause 小） | 恢复实时日志追加 / 暂停实时日志追加 | 暂停/恢复 |
| Logs/Logs.tsx | （Clear 危险小） | 清空当前显示的实时流日志 | 清流日志 |
| Logs/Logs.tsx | 搜索（Search 主） | 按关键词/级别/任务搜索日志 | 搜索日志 |
| Logs/Logs.tsx | 导出CSV（Download） | 导出当前日志为 CSV 文件 | 导出 CSV |
| Logs/Logs.tsx | 导出LOG（Download） | 导出当前日志为 LOG 文件 | 导出 LOG |
| Logs/Logs.tsx | 刷新（Reload 小） | 重新加载原始日志 | 刷新原始日志 |

### pages/Logs/ErrorLogs.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Logs/ErrorLogs.tsx | 复制（Copy 图标） | 复制 AI 上下文到剪贴板 | 复制上下文 |
| Logs/ErrorLogs.tsx | 刷新（Reload 主） | 重新加载错误日志列表 | 刷新列表 |
| Logs/ErrorLogs.tsx | 批量清理（Delete 图标） | 清理 30 天前已解决/已忽略的日志 | 批量清理 |
| Logs/ErrorLogs.tsx | 搜索（Search 主） | 按状态与错误类型搜索日志 | 搜索日志 |
| Logs/ErrorLogs.tsx | 清空 | 清空搜索历史关键词 | 清搜索历史 |
| Logs/ErrorLogs.tsx | （Check 小） | 将选中项标记为已解决 | 标记已解决 |
| Logs/ErrorLogs.tsx | （Stop 小） | 将选中项标记为已忽略 | 标记已忽略 |
| Logs/ErrorLogs.tsx | （Delete 危险小） | 批量删除选中的错误日志 | 批量删除 |
| Logs/ErrorLogs.tsx | 取消选择（link） | 清除当前勾选 | 清选择 |
| Logs/ErrorLogs.tsx | （Delete 危险 text） | 删除该条错误日志 | 删日志 |

---

## src/pages/Orders

### pages/Orders/Orders.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Orders/Orders.tsx | 取消（接管弹窗） | 关闭接管弹窗 | 关弹窗 |
| Orders/Orders.tsx | 确认接管（Thunderbolt 主） | 开始接管此订单 | 接管订单 |
| Orders/Orders.tsx | 取消接管（Close 危险） | 取消接管并保留订单为待处理 | 取消接管 |
| Orders/Orders.tsx | 确认完成（Check 主） | 确认已在闲鱼完成支付 | 确认支付 |
| Orders/Orders.tsx | 关闭（完成提示） | 关闭完成提示 | 关提示 |
| Orders/Orders.tsx | （Thunderbolt link 小） | 接管此待处理订单 / 查看接管进度 | 接管/查看 |
| Orders/Orders.tsx | 删除（Delete link 危险） | 删除此订单（不可恢复） | 删订单 |
| Orders/Orders.tsx | 刷新（Reload 图标） | 重新加载订单列表 | 刷新列表 |
| Orders/Orders.tsx | 列配置（Setting 图标） | 自定义表格显示列与顺序 | 列配置 |

---

## src/pages/Export

### pages/Export/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Export/index.tsx | 导出 CSV（Download 主） | 导出 {标题} 为 CSV 文件 | 导出 CSV |

---

## src/pages/Onboarding

### pages/Onboarding/index.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Onboarding/index.tsx | 复制扫码登录命令（Copy 小） | 复制扫码登录命令 | 复制命令 |
| Onboarding/index.tsx | 刷新登录状态（Reload 主） | 刷新并检测当前登录状态 | 检测登录 |
| Onboarding/index.tsx | 创建监控任务（Rocket 主） | 创建监控任务 | 建任务 |
| Onboarding/index.tsx | 下一步 | 进入下一步配置通知 | 下一步 |
| Onboarding/index.tsx | 复制启动调度器命令（Copy 小） | 复制启动调度器命令 | 复制命令 |
| Onboarding/index.tsx | 完成设置（主） | 完成初始化设置 | 完成设置 |
| Onboarding/index.tsx | 进入仪表盘（主，大） | 进入系统仪表盘 | 进仪表盘 |
| Onboarding/index.tsx | 上一步 | 返回上一步 | 上一步 |
| Onboarding/index.tsx | 跳过 | 跳过本步骤 | 跳过步骤 |

---

## src/pages/Maintenance

### pages/Maintenance/BatchRefresh.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Maintenance/BatchRefresh.tsx | 刷新状态（Reload 图标） | 刷新当前批次执行状态 | 刷状态 |
| Maintenance/BatchRefresh.tsx | 保存配置（Save 小） | 保存并热更新配置 | 保存配置 |
| Maintenance/BatchRefresh.tsx | 触发（PlayCircle 主） | {triggerTooltipText}（动态） | 触发采集 |
| Maintenance/BatchRefresh.tsx | 暂停（PauseCircle） | 暂停当前批次，采集完成后生效 | 暂停批次 |
| Maintenance/BatchRefresh.tsx | 继续（PlayCircle 主） | 从断点继续批量采集 | 续采 |
| Maintenance/BatchRefresh.tsx | 停止（Stop 危险） | 停止批次并持久化进度 | 停止批次 |
| Maintenance/BatchRefresh.tsx | 查看详情（Eye link） | 查看该条执行历史详情 | 看详情 |
| Maintenance/BatchRefresh.tsx | 删除（Delete link 危险） | 删除该条历史记录，操作不可恢复 | 删历史 |
| Maintenance/BatchRefresh.tsx | 查询（Search 主） | 按筛选条件查询执行历史 | 查询历史 |
| Maintenance/BatchRefresh.tsx | 重置 | 重置所有筛选条件 | 重置筛选 |
| Maintenance/BatchRefresh.tsx | 清理 30 天前（Delete） | 清理 30 天前的历史记录 | 清旧记录 |
| Maintenance/BatchRefresh.tsx | 清空全部（Delete 危险） | 清空全部历史记录，不可恢复 | 清空历史 |
| Maintenance/BatchRefresh.tsx | 刷新（Reload 图标） | 重新加载执行历史列表 | 刷历史 |

### pages/Maintenance/Cleanup.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Maintenance/Cleanup.tsx | 刷新状态（Reload 图标） | 刷新存储状态概览 | 刷状态 |
| Maintenance/Cleanup.tsx | 清理缓存（Delete 主） | 清理所选范围的缓存（预览或真实执行） | 清缓存 |
| Maintenance/Cleanup.tsx | 清理数据库（Database 主） | 清理数据库冗余数据（预览或真实执行） | 清数据库 |
| Maintenance/Cleanup.tsx | 清理日志（FileText 主） | 清理旧日志文件释放磁盘空间 | 清日志 |

### pages/Maintenance/DatabaseAdmin.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Maintenance/DatabaseAdmin.tsx | 审计日志（FileText 图标） | 查看数据库维护审计日志 | 看审计 |
| Maintenance/DatabaseAdmin.tsx | 刷新（Reload 图标） | 刷新表列表与数据 | 刷表数据 |
| Maintenance/DatabaseAdmin.tsx | 新增（Plus 主） | 新增一行记录 | 新增行 |
| Maintenance/DatabaseAdmin.tsx | 批量删除（Delete 危险） | 批量删除选中行（需确认） | 批量删行 |
| Maintenance/DatabaseAdmin.tsx | 导入（Upload 图标） | 打开数据导入弹窗 | 打开导入 |
| Maintenance/DatabaseAdmin.tsx | 导出 CSV（Download） | 导出当前表数据为 CSV | 导出 CSV |
| Maintenance/DatabaseAdmin.tsx | 导出 JSON（Download） | 导出当前表数据为 JSON | 导出 JSON |
| Maintenance/DatabaseAdmin.tsx | 查看表结构（Table 图标） | 查看当前表字段结构 | 看结构 |
| Maintenance/DatabaseAdmin.tsx | 查询 | 按关键词查询表数据 | 查询数据 |
| Maintenance/DatabaseAdmin.tsx | 清空 | 清空搜索历史关键词 | 清搜索历史 |
| Maintenance/DatabaseAdmin.tsx | 编辑（Edit link 小） | 编辑该行记录 | 编辑行 |
| Maintenance/DatabaseAdmin.tsx | 删除（Delete link 危险） | 删除该行（需输入确认码） | 删行 |
| Maintenance/DatabaseAdmin.tsx | 选择 CSV 文件（Upload） | 选择本地 CSV 文件上传 | 选 CSV |
| Maintenance/DatabaseAdmin.tsx | 选择 JSON 文件（Upload） | 选择本地 JSON 文件上传 | 选 JSON |

### pages/Maintenance/Tunnel.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Maintenance/Tunnel.tsx | 授权登录 | 执行 Cloudflare 授权登录 | CF 授权 |
| Maintenance/Tunnel.tsx | 创建隧道 | 创建命名隧道（或重新创建） | 建隧道 |
| Maintenance/Tunnel.tsx | 配置 DNS 路由 | 配置 DNS 路由（CNAME 记录） | 配 DNS |
| Maintenance/Tunnel.tsx | 启动隧道（PlayCircle 主） | 启动隧道建立公网连接 | 启动隧道 |
| Maintenance/Tunnel.tsx | 停止隧道（Stop 危险） | 停止当前隧道 | 停止隧道 |
| Maintenance/Tunnel.tsx | （Link 图标） | 在新窗口打开公网地址 | 打开公网 |
| Maintenance/Tunnel.tsx | 下载（link 小） | 下载 cloudflared 二进制文件 | 下载二进制 |
| Maintenance/Tunnel.tsx | 授权（Link 主） | 打开 Tailscale Funnel 授权页面 | TS 授权 |
| Maintenance/Tunnel.tsx | 保存配置（主） | 保存隧道配置（下次启动生效） | 保存配置 |

### pages/Maintenance/VectorAdmin.tsx
| 文件 | 按钮（标签/图标） | Tooltip 文案 | 功能说明 |
| --- | --- | --- | --- |
| Maintenance/VectorAdmin.tsx | 审计日志（FileText） | 查看向量库审计日志 | 看审计 |
| Maintenance/VectorAdmin.tsx | 刷新（Reload 图标） | 重新加载向量库状态 | 刷状态 |
| Maintenance/VectorAdmin.tsx | 创建快照（Camera 主） | 创建向量库快照备份 | 建快照 |
| Maintenance/VectorAdmin.tsx | 恢复（Rollback link 小） | 从快照恢复并覆盖当前集合 | 恢复快照 |
| Maintenance/VectorAdmin.tsx | 删除（Delete link 危险） | 删除该快照（不可恢复） | 删快照 |
| Maintenance/VectorAdmin.tsx | 清空集合（Delete 危险） | 清空集合中全部片段 | 清集合 |
| Maintenance/VectorAdmin.tsx | 删除（Delete 危险） | 删除指定来源的所有片段 | 按来源删 |
