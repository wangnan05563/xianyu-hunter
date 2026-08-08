# 附录 A（续）：第三轮复盘 — 回退构造/时间窗口/PowerShell 环境/服务重启四类失败模式

> 复盘时间：2026-07-22（第三轮，基于 price_range 注入 Bug、30 天窗口无数据回退、PowerShell curl 别名冲突、端口冲突与服务未重启等 6+ 问题）
> 复盘方法：Sequential Thinking 四维度复盘法（成功步骤 / 失败点 / 可抽象流程 / 适用场景）
> 配套元规则：#90-#92（见 meta-rules.md）
> 配套审查规范：F-REVIEW-206 / B-REVIEW-251~253
> 配套测试模式：xianyu-auto-testing 模式 O（回退构造关联键一致性测试）

---

## A.12 模式 E：接口测试验证流程（成功步骤）

**适用问题**：后端接口开发完成后的端到端验证、AI 评估注入验证、价格区间数据注入验证

| 步骤 | 操作 | 验证方式 |
|---|---|---|
| 1. 端口冲突预检 | 检查目标端口是否被占用 | `Get-NetTCPConnection -LocalPort <port>` |
| 2. 杀旧进程 | 若端口被占用，按 PID 杀进程 | `Stop-Process -Id <pid> -Force` |
| 3. 启动服务 | 用最新代码启动后端服务 | `.venv\Scripts\python.exe -m xianyu_hunter web --port <port>` |
| 4. 服务健康检查 | curl 根路径验证 HTTP 200 | `curl.exe -s -o $null -w "%{http_code}" http://127.0.0.1:<port>/` |
| 5. 接口功能测试 | 用 curl.exe + JSON body 文件测试接口 | 将 JSON 写入临时文件，`-d "@<file>"` 传递 |
| 6. 返回结构验证 | 检查返回 JSON 包含预期字段 | 解析 JSON，断言字段存在且非空 |
| 7. 端到端验证 | 验证下游消费方（如 LLM）是否正确引用数据 | 检查 LLM detail 是否包含价格区间关键词 |

**关键判断逻辑**：
- 端口被占用 ≠ 服务正在运行：可能是旧进程残留，必须杀掉后重启
- 服务返回 404 ≠ 接口不存在：可能是旧服务未加载新代码
- PowerShell `curl` ≠ 真正的 curl：PowerShell 中 `curl` 是 `Invoke-WebRequest` 的别名

## A.13 第三轮 6 个失败模式与修复（2026-07-22）

| 编号 | 失败模式 | 根因 | 修复 | 教训 |
|---|---|---|---|---|
| F14 | AI 评估返回结果缺少 price_range 字段 | `get_eval_payload_by_item` 只查 payload 不查 task_id，回退构造的伪 item dict 无 task_id，价格区间查询被 `if task_id:` 跳过 | repo_events.py 同时查 task_id 并注入 payload；api_ai.py 从 payload 提取 task_id | 回退构造实体时必须保留下游依赖的关联键 |
| F15 | 价格区间 30 天窗口返回 empty | 数据库中商品数据时间较早，超过 30 天窗口 | api_ai.py 增加 30 天查询返回 empty 时用 range_days=0 重查 | 时间窗口查询必须有全量回退策略 |
| F16 | PowerShell curl 别名冲突 | PowerShell 的 `curl` 是 `Invoke-WebRequest` 别名，不支持 `-s`/`-w` 等参数 | 改用 `curl.exe` 调用真正的 curl | PowerShell 环境必须用 `.exe` 后缀调用外部命令 |
| F17 | PowerShell JSON body 传递失败 | `-d "{\"key\":\"value\"}"` 和 `-d '{"key":"value"}'` 都因引号转义失败 | 将 JSON 写入临时文件，用 `-d "@<file>"` 传递 | PowerShell 中复杂 JSON 参数应通过文件传递 |
| F18 | 端口 8000 被旧服务占用 | 旧进程未正确退出 | `Stop-Process -Id <pid> -Force` 杀旧进程后重启 | 启动服务前必须检查端口占用 |
| F19 | 接口返回 404 Not Found | 旧服务未重启，未加载新代码 | 杀掉旧进程后重新启动 | 修改后端代码后必须重启服务 |

## A.14 第三轮 4 个可沉淀的固定流程

| 流程 | 触发 | 步骤 | 验证 |
|---|---|---|---|
| 回退构造关联键保留 | 事件/缓存回退构造实体时 | 识别下游依赖键 → 查询时同时取关联键 → 注入回退实体 → 下游条件判断前校验键存在 | 单测覆盖回退路径 |
| 时间窗口全量回退 | 基于时间窗口的统计查询 | 窗口查询 → 返回 empty → 全量查询 → 合并结果 | 测试边界场景 |
| PowerShell 外部命令调用 | 在 PowerShell 中调用 curl/wget 等外部命令 | 识别别名冲突 → 用 `.exe` 后缀 → 复杂参数通过文件传递 | 命令执行成功且输出正确 |
| 服务重启验证 | 后端代码修改后 | 端口预检 → 杀旧进程 → 启动新服务 → 健康检查 → 接口验证 | 接口返回预期结果 |

## A.15 第三轮 4 项反模式（禁止清单）

1. **禁止**回退构造实体时遗漏下游依赖的关联键（如从 payload 回退构造 item 时遗漏 task_id）
2. **禁止**时间窗口查询返回空时直接返回空结果，必须有全量回退策略
3. **禁止**在 PowerShell 中用 `curl`（别名）而非 `curl.exe`（真正的 curl）调用 HTTP 接口
4. **禁止**修改后端代码后不重启服务就测试（旧服务未加载新代码会导致 404 或行为不一致）

## A.16 下游技能同步清单（第三轮）

| 文件 | 本次新增内容 |
|---|---|
| `.trae/skills/xianyu-frontend-code-review/SKILL.md` | 新增 F-REVIEW-206（回退构造关联键前端审查） |
| `.trae/skills/xianyu-backend-code-review/SKILL.md` | 新增 B-REVIEW-251~253（3 条审查规范） |
| `.trae/skills/xianyu-auto-testing/SKILL.md` | 新增模式 O（回退构造关联键一致性测试） |
| `.trae/skills/xianyu-hunter-dev/references/meta-rules.md` | 新增 #90-#92（3 条元规则） |
