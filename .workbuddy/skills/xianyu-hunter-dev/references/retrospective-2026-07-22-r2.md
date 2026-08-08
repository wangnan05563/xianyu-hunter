# 附录 A（续）：第二轮复盘 — 状态机/认证/配置/跨层/超时五类失败模式

> 复盘时间：2026-07-22（第二轮，基于订单页面功能扩展、scheduler 卡死、智能客服乱码、FAIL_SYS_ILLEGAL_ACCESS、商品评估明细/图片未更新、抢单超时无日志等 7+ 问题）
> 复盘方法：Sequential Thinking 四维度复盘法（成功步骤 / 失败点 / 可抽象流程 / 适用场景）
> 配套元规则：#84-#88（见 meta-rules.md）
> 配套审查规范：F-REVIEW-200~204 / B-REVIEW-245~249
> 配套测试模式：xianyu-auto-testing 模式 L（状态机死锁回归）/ 模式 M（跨层数据契约一致性）

---

## A.6 模式 C：前后端契约同步修复（成功步骤）

**适用问题**：商品评估明细/图片未更新、品牌抓取错误、字段跨层不一致类问题

| 步骤 | 操作 | 验证方式 |
|---|---|---|
| 1. 识别跨层字段 | 找出前端消费、后端产出、DB 存储的三层字段（如 image_urls、brand、display） | grep 字段名跨层追溯 |
| 2. 判断覆盖策略 | 该字段属于 _ALWAYS_OVERWRITE（强制覆盖）/ _coalesce（旧值优先）/ _NULL_SAFE（空值不清空）哪个集合 | 读取后端覆盖策略常量 |
| 3. 前端状态重置 | React 组件复用场景，URL/props 变化时重置 errored/loaded/loading 等内部状态 | useEffect 监听依赖项 |
| 4. 后端写回保护 | 外部 API 返回空值时不清空旧有效数据，空值视为"本次未取到"而非"应清空" | _coalesce 逻辑单测 |
| 5. 跨层一致性验证 | 后端字段集合改动后，前端 types.ts 同步标注派生来源 | tsc 编译 + chunk 关键字验证 |

**关键判断逻辑**：
- 字段值 === None/null vs 字段未取到，语义不同
  - None/null：显式清空，应覆盖
  - 未取到（API 返回但字段缺失）：保留旧值
- React 组件复用时，URL/props 变化 → 内部状态（errored/loaded）必须重置

## A.7 模式 D：调度器状态机死锁修复（成功步骤）

**适用问题**：scheduler 任务永久卡死、pause/resume 失效、任务启动后不周期执行

| 步骤 | 操作 |
|---|---|
| 1. 状态机还原 | 画出 pause→resume→loop 的事件流（pause_event.set/clear/wait） |
| 2. 死锁点定位 | 找出"event 设置后无 waiter"或"waiter 永久阻塞"的分支 |
| 3. 闭环校验 | resume 路径必须能唤醒 wait；pause 路径必须让 loop 回到顶部阻塞 |
| 4. 返回值语义统一 | should_pause 时返回 False（继续循环）而非 True（break 出循环） |
| 5. 错误计数隔离 | 会话失效暂停时不重置 consecutive_errors，避免恢复后误判健康 |

**关键判断逻辑**：
- 暂停 ≠ 终止：暂停后 loop 必须保留 wait 能力，不能 break 出循环
- resume 前 pause_event 必须 clear，否则 loop 不阻塞会空转
- should_pause 返回值语义：True=应退出循环，False=应继续循环（不能混用）

## A.8 第二轮 6 个失败模式与修复（2026-07-22）

| 编号 | 失败模式 | 根因 | 修复 | 教训 |
|---|---|---|---|---|
| F8 | scheduler 任务永久卡死 | `_run_loop` 会话失效时 `return True` 导致主循环 break，resume 时 `pause_event.set()` 无 loop 在 wait | should_pause 返回 False，loop 顶部检查 pause_event 状态 | 状态机恢复路径必须有 waiter 在 wait |
| F9 | 智能客服欢迎语乱码 '??????????!' | DB `chatbot_config.welcome_message` 被写入占位符字符串 | get_config 返回该字段 + 前端 textarea + 清 DB 脏值 + "恢复默认"按钮 | 配置字段必须 5 层链路全覆盖 |
| F10 | FAIL_SYS_ILLEGAL_ACCESS 非法请求 | Worker 浏览器启动时生成匿名 `_m_h5_tk` token 残留内存，与身份 Cookie 不匹配 | 每次实时搜索强制刷新 token；TokenRenewer 续期回写 CookieStore | 身份 Cookie 与签名 token 必须分离管理 |
| F11 | 商品评估明细/图片未更新 | (a) ThumbCell URL 更新后未重置 errored；(b) 后端 image_urls 被覆盖为 None | (a) useEffect 重置 errored；(b) image_urls 移出 _ALWAYS_OVERWRITE | React 组件复用必须重置内部状态；后端覆盖策略需区分空值与未取到 |
| F12 | 抢单超时无日志/显示"未知异常" | `asyncio.wait_for` 超时 except 块未结构化记录阶段信息 | 超时 except 块输出阶段名+耗时；UI 显示具体阶段 | 多步骤关键路径每阶段需独立 status + 超时阈值 + 结构化日志 |
| F13 | 任务管理所有任务启动后不周期搜索 | scheduler `_run_loop` 会话失效时 return True 导致 break | should_pause 返回 False，loop 顶部检查 pause_event | 会话失效是暂停而非终止，loop 必须保留 wait 能力 |

## A.9 第二轮 5 个可沉淀的固定流程

| 流程 | 触发 | 步骤 | 验证 |
|---|---|---|---|
| 跨层数据一致性修复 | 前后端契约字段调整 | 5 层齐全 → 覆盖策略分类 → 前端状态重置 → 后端写回保护 → 跨层一致性验证 | tsc + chunk 关键字 |
| 状态机恢复路径校验 | scheduler/任务循环/会话管理改动 | 状态机还原 → 死锁点定位 → 闭环校验 → 返回值语义统一 → 错误计数隔离 | 单测模拟 pause/resume |
| 身份认证与签名分离 | 浏览器自动化/第三方 API 签名改动 | 身份 Cookie 与签名 token 分离存储 → token 刷新时间戳无条件重置 → 续期闭环回写 → 日志占位符校验 | 集成测试日志序列 |
| 配置字段全链路覆盖 | 用户可编辑配置项改动 | DB schema → get_config → update_config → types.ts → Config.tsx → 恢复默认按钮 | 5 层链路检查脚本 |
| 超时与可观测性配对 | 多步骤关键路径改动 | 每阶段独立 status → 独立超时阈值 → 结构化超时日志 → UI 显示阶段名 | 关键路径可观测性测试 |

## A.10 第二轮 6 项反模式（禁止清单）

1. **禁止** scheduler/任务循环的 should_pause 返回 True 导致主循环 break（会话失效是暂停不是终止）
2. **禁止** 后端把外部 API 返回的空值（None/null）当作"应清空旧值"处理（应区分"空值"与"未取到"）
3. **禁止** React 组件复用时不在 useEffect 中重置 errored/loaded/loading 等内部状态
4. **禁止** 配置字段只改 DB schema 而不补全 get_config/update_config/types.ts/Config.tsx 五层链路
5. **禁止** 身份 Cookie 与签名 token 混合存储，token 刷新时间戳有条件重置
6. **禁止** asyncio.wait_for 超时 except 块只输出 "未知异常" 而不记录阶段名和耗时

## A.11 下游技能同步清单（第二轮）

| 文件 | 本次新增内容 |
|---|---|
| `.trae/skills/xianyu-frontend-code-review/SKILL.md` | 新增 F-REVIEW-200~204（5 条审查规范） |
| `.trae/skills/xianyu-backend-code-review/SKILL.md` | 新增 B-REVIEW-245~249（5 条审查规范） |
| `.trae/skills/xianyu-auto-testing/SKILL.md` | 新增模式 L（状态机死锁回归）/ 模式 M（跨层数据契约一致性） |
| `.trae/skills/xianyu-hunter-dev/references/meta-rules.md` | 新增 #84-#88（5 条元规则） |
