# 数据透传完整性测试

本文档描述模式 G（数据透传完整性测试模式）的详细操作步骤。

模式 G 用于验证跨层数据透传完整性（如 `user_id` 在多层调用链中正确传递至最底层数据库写入），覆盖透传链路签名检查、运行时追踪、多用户隔离三类场景。所有参数从 `config.yaml` 的 `data_propagation_integrity_test` 段读取，**禁止在文档中硬编码方法名、字段名、用户 ID、端点路径**。

对应 2026-07-18 卖家评估 Bug 复盘 Bug 2A（user_id 传递断裂）的回归测试需求。

## 1. 识别透传链路

### 1.1 读取链路配置

从 `data_propagation_integrity_test.propagation_chains` 读取所有透传链路。每条链路包含：

| 字段 | 含义 |
|------|------|
| `name` | 链路名称（人类可读） |
| `entry_method` | 入口方法（用户 API 调用入口，如 `ItemCollectionService.collect`） |
| `intermediate_methods` | 中间方法列表（透传链路上的层层调用，有序） |
| `sink_method` | 最底层方法（实际写入数据库或调用 repo 的方法） |
| `required_fields` | 必须从入口透传至 sink 的字段列表 |
| `test_user_id` | 测试用用户 ID（仅 user_id 类字段需要） |
| `trigger_endpoint` | 触发 API 端点 |
| `verify_endpoint` | 验证查询端点 |
| `exempt_fields` | 豁免字段列表（如 worker 后台任务允许 user_id 为 None） |

### 1.2 链路展开示例

以 `propagation_chains[0]`（官方采集评估事件写入链路）为例：

```
entry_method: ItemCollectionService.collect
  ↓
intermediate_methods[0]: _collect_official_full
  ↓
intermediate_methods[1]: _evaluate_and_notify
  ↓
intermediate_methods[2]: _save_eval_event
  ↓
sink_method: upsert_eval_event  (写入数据库)
```

`required_fields: [user_id]` 表示 `user_id` 必须从 `collect` 入口透传至 `upsert_eval_event` sink。

## 2. 静态签名检查

### 2.1 方法签名扫描

对每条链路中的每个方法（含 entry / intermediate / sink），扫描函数签名：

```powershell
# {key_files} ← data_propagation_integrity_test.key_files 拼接为绝对路径
# {method}    ← 当前链路当前方法名
Select-String -Path {key_files} -Pattern "def\s+{method}\s*\(" -Encoding UTF8 -Context 0,5 | ForEach-Object {
    "$($_.Path):$($_.LineNumber): $($_.Line)"
}
```

对每个匹配项，记录：
- 文件路径与行号
- 函数签名中的形参列表
- 是否包含 `required_fields` 中的字段（直接形参或 `**kwargs`）

### 2.2 字段传递检查

对链路中相邻的两个方法 A → B，检查 A 内部调用 B 时是否将 `required_fields` 中的字段作为关键字参数传递：

```powershell
# {file}    ← A 方法所在文件
# {methodB} ← B 方法名
# {field}   ← required_fields 中的字段
Select-String -Path {file} -Pattern "{methodB}\s*\(.*{field}\s*=" -Encoding UTF8 | ForEach-Object {
    "$($_.Path):$($_.LineNumber): $($_.Line)"
}
```

### 2.3 sink 方法使用检查

对 `sink_method`（最底层方法），检查是否将 `required_fields` 中的字段实际使用：
- 写入数据库（如 `EventRow(user_id=user_id)` 或 `INSERT INTO ... user_id`）
- 传递给其他方法（如 `repo.upsert(user_id=user_id)`）

```powershell
# {file}      ← sink_method 所在文件
# {sink}      ← sink_method 名称
# {field}     ← required_fields 中的字段
Select-String -Path {file} -Pattern "{sink}.*{field}|{field}.*{sink}" -Encoding UTF8 | ForEach-Object {
    "$($_.Path):$($_.LineNumber): $($_.Line)"
}
```

### 2.4 静态签名检查矩阵模板

| 链路 | 方法 | 形参含 user_id | 调用下一层传 user_id | sink 使用 user_id | 结果 |
|------|------|---------------|---------------------|-------------------|------|
| 官方采集 | collect | YES | YES | - | PASS |
| 官方采集 | _collect_official_full | YES | YES | - | PASS |
| 官方采集 | _evaluate_and_notify | YES | YES | - | PASS |
| 官方采集 | _save_eval_event | **NO** | - | - | **FAIL** |
| 官方采集 | upsert_eval_event | YES | - | YES（写入 EventRow） | PASS |

**FAIL 修复指引**：在 `_save_eval_event` 形参中追加 `user_id`，并在调用 `_save_eval_event` 处补充 `user_id=user_id` 关键字参数。

## 3. 运行时追踪验证

### 3.1 环境准备

1. 复用诊断模式 DT-01 ~ DT-03，确保 web 进程已运行、构建产物最新、HTTP 响应正常
2. **关键**：修改 `key_files` 中任一文件后必须重启 web 进程，否则新代码不生效
   - 重启命令：`web_process.start_command`（将 `{port}` 替换为 `web_process.port`）
3. 准备测试用户身份：
   - 使用 `test_user_id` 配置的值（如 `test_propagation_user`）
   - **必须非默认值 `"default"`**，否则无法检测默认值掩盖断裂的 Bug

### 3.2 触发官方采集

调用 `trigger_endpoint`（如 `/api/evaluations/official-collect`），以 `test_user_id` 用户身份发起请求：

```powershell
# {host}             ← web_process.host
# {port}             ← web_process.port
# {trigger_endpoint} ← propagation_chains[i].trigger_endpoint
# {test_user_id}     ← propagation_chains[i].test_user_id
# {token}            ← 从 auth.env_file_path 读取 auth.env_file_key 的值
curl.exe -X POST "http://{host}:{port}{trigger_endpoint}" `
    -H "Cookie: xh_token={token}" `
    -H "X-Test-User-Id: {test_user_id}"
```

> 注：实际请求头按 `auth` 配置构造。若项目通过其他方式注入 user_id（如 session 中间件），按项目实际机制构造。

### 3.3 数据库记录验证

直接查询数据库，验证写入的 `eval_events` 表记录的 `user_id` 字段是否等于 `test_user_id`：

```powershell
# {db_path}        ← 项目数据库路径（如 data/xianyu.db）
# {test_user_id}   ← propagation_chains[i].test_user_id
# {table}          ← eval_events 表名
.venv\Scripts\python.exe -c "
import sqlite3
conn = sqlite3.connect('{db_path}')
cur = conn.cursor()
cur.execute('SELECT user_id, item_id, created_at FROM {table} ORDER BY created_at DESC LIMIT 5')
for row in cur.fetchall():
    print(row)
conn.close()
"
```

**判定规则**：
- 最新一条记录的 `user_id` 字段值 == `test_user_id` → PASS
- 最新一条记录的 `user_id` 字段值 == `"default"` 或 None → **FAIL**（说明透传断裂，写入了默认值）

### 3.4 查询接口验证

调用 `verify_endpoint`（如 `/api/evaluations`），以 `test_user_id` 用户身份查询评估列表：

```powershell
# {host}           ← web_process.host
# {port}           ← web_process.port
# {verify_endpoint} ← propagation_chains[i].verify_endpoint
# {test_user_id}   ← propagation_chains[i].test_user_id
curl.exe "http://{host}:{port}{verify_endpoint}" `
    -H "Cookie: xh_token={token}" `
    -H "X-Test-User-Id: {test_user_id}"
```

**判定规则**：
- 响应中包含刚写入的评估记录 → PASS
- 响应中不包含刚写入的评估记录 → **FAIL**（说明查询接口未按 user_id 过滤，或写入的 user_id 错误）

## 4. 多用户隔离验证

### 4.1 准备两个测试用户

- 用户 A：`test_user_id`（如 `test_propagation_user`）
- 用户 B：另一个非默认用户 ID（如 `test_isolation_user`）

### 4.2 隔离验证流程

1. **用户 A 触发采集**：以用户 A 身份调用 `trigger_endpoint`，写入一条评估记录
2. **用户 B 查询列表**：以用户 B 身份调用 `verify_endpoint`
3. **判定**：
   - 用户 B 的响应中**不应**包含用户 A 刚写入的评估记录（除非共享任务） → PASS
   - 用户 B 的响应中**包含**用户 A 的评估记录 → **FAIL**（数据泄漏）

### 4.3 多用户隔离验证清单

| 场景 | 用户 A 操作 | 用户 B 查询 | 预期结果 | 实际结果 | 判定 |
|------|------------|------------|---------|---------|------|
| A 触发采集，B 查询 | 调用 trigger_endpoint | 调用 verify_endpoint | B 看不到 A 的记录 | - | - |
| A、B 各自触发采集 | A 调用 trigger_endpoint | B 调用 trigger_endpoint | A、B 各自只看到自己的记录 | - | - |
| 共享任务场景 | A 创建任务，B 关联任务 | B 调用 verify_endpoint | B 能看到共享任务的记录 | - | - |

## 5. 失败案例分析：Bug 2A（user_id 传递断裂）

### 5.1 Bug 现象

2026-07-18 卖家评估 Bug 复盘中发现：
- 用户 A 通过官方采集 API 触发评估事件写入
- 数据库中确实写入了评估记录
- 但 `user_id` 字段值为 `"default"`（默认值），而非用户 A 的实际 user_id
- 导致用户 A 在评估列表查询时看不到自己的评估事件（被其他用户的查询过滤掉）

### 5.2 根因分析

调用链 `collect → _collect_official_full → _evaluate_and_notify → _save_eval_event → upsert_eval_event` 中：
- `collect` 接收 `user_id` 形参（来自 request.state.user_id）
- `_collect_official_full` 接收并传递 `user_id`
- `_evaluate_and_notify` 接收并传递 `user_id`
- **`_save_eval_event` 未接收 `user_id` 形参**（断裂点）
- `upsert_eval_event` 接收 `user_id`，但 `_save_eval_event` 调用时未传递，sink 内部使用默认值 `"default"`

### 5.3 Sequential Thinking 复盘

```
1. 观察：用户 A 触发采集后看不到自己的评估事件
2. 假设 1：评估事件未写入数据库 → 验证：SELECT * FROM eval_events WHERE item_id=xxx → 记录存在，假设 1 否定
3. 假设 2：查询接口过滤逻辑错误 → 验证：直接查数据库 user_id 字段 → user_id="default"，假设 2 否定
4. 假设 3：写入时 user_id 传递断裂 → 验证：grep _save_eval_event 签名 → 缺少 user_id 形参 → 假设 3 成立
5. 修复：在 _save_eval_event 形参中追加 user_id，调用处补充 user_id=user_id
6. 验证：触发采集 → 查询数据库 user_id 字段 == test_user_id → 修复确认
```

### 5.4 修复验证流程

1. **静态验证**：执行 §2 静态签名检查，所有链路所有方法的 `required_fields` 形参齐全
2. **运行时验证**：执行 §3 运行时追踪验证，数据库记录 `user_id` == `test_user_id`
3. **隔离验证**：执行 §4 多用户隔离验证，用户 B 看不到用户 A 的记录
4. **回归验证**：运行现有 pytest 测试套件，确认未引入新问题

## 6. 诊断输出

### 6.1 透传链路完整性矩阵

```
## 透传链路完整性矩阵

### 链路 1：官方采集评估事件写入链路

| 方法 | 形参含 user_id | 调用下一层传 user_id | sink 使用 user_id | 结果 |
|------|---------------|---------------------|-------------------|------|
| ItemCollectionService.collect | YES | YES | - | PASS |
| _collect_official_full | YES | YES | - | PASS |
| _evaluate_and_notify | YES | YES | - | PASS |
| _save_eval_event | YES | YES | - | PASS |
| upsert_eval_event | YES | - | YES（EventRow.user_id） | PASS |

链路完整性：5/5 PASS

### 链路 2：worker 首次采集评估事件写入链路

| 方法 | 形参含 task_id | 调用下一层传 task_id | sink 使用 task_id | 结果 |
|------|---------------|---------------------|-------------------|------|
| TaskWorker.run_once | YES | YES | - | PASS |
| _collect_detail_and_seller | YES | YES | - | PASS |
| _evaluate_item | YES | YES | - | PASS |
| _save_eval_event | YES | YES | - | PASS |
| upsert_eval_event | YES | - | YES（EventRow.task_id） | PASS |

链路完整性：5/5 PASS
（注：user_id 在 worker 链路中豁免，因 worker 是后台任务）
```

### 6.2 多用户隔离验证结果

```
## 多用户隔离验证结果

| 场景 | 用户 A 操作 | 用户 B 查询 | 预期结果 | 实际结果 | 判定 |
|------|------------|------------|---------|---------|------|
| A 触发采集，B 查询 | 调用 /api/evaluations/official-collect | 调用 /api/evaluations | B 看不到 A 的记录 | B 响应中无 A 的 item_id | PASS |
| A、B 各自触发采集 | A 调用 official-collect | B 调用 official-collect | A、B 各自只看到自己 | A 看到 A 的，B 看到 B 的 | PASS |

隔离验证：2/2 PASS
```

### 6.3 问题报告格式

```
## 发现的问题

### 问题 1
- 描述：_save_eval_event 形参缺少 user_id，导致 EventRow.user_id 写入默认值 "default"
- 关联 key_files：src/xianyu_hunter/modules/collection_service.py
- 复现步骤：
  1. 以 test_propagation_user 身份调用 /api/evaluations/official-collect
  2. 查询数据库 SELECT user_id FROM eval_events ORDER BY created_at DESC LIMIT 1
  3. 观察返回值为 "default" 而非 "test_propagation_user"
- 建议修复方向：在 _save_eval_event 形参中追加 user_id: str，调用处补充 user_id=user_id
- 关联 Bug：2026-07-18 卖家评估 Bug 复盘 Bug 2A
```

## 7. 已知陷阱

执行模式 G 时需特别注意以下陷阱（来自历史踩坑）：

1. **默认值 "default" 掩盖断裂**：`EventRow.user_id` 默认值为 `"default"`，即使透传断裂数据库记录依然存在，单测若不检查实际 user_id 值会漏报。**必须用非默认 test_user_id 验证**。

2. **worker 链路 user_id 豁免**：worker 是后台任务，user_id 可能为 None 是合理场景，不应误报为断裂。配置中通过 `exempt_fields` 声明豁免字段。

3. **服务未重启导致新代码未生效**：修改 `key_files` 中文件后，若仅重新构建前端而未重启 web 进程，后端 Python 代码不会重新加载。**必须重启 web 进程**。

4. **多用户隔离仅靠 user_id 不够**：评估列表查询接口未按 `user_id` 过滤时，用户 B 能查到用户 A 的评估记录。隔离验证需同时检查"用户 B 看不到用户 A 的记录"与"用户 A 能看到自己的记录"。

5. **共享任务的隔离例外**：若用户 A 与用户 B 共享同一任务（如 B 是 A 的协作成员），用户 B 应能看到该任务的评估记录。隔离验证需区分"私有记录"与"共享任务记录"。

6. **`**kwargs` 形参掩盖字段缺失**：方法签名用 `**kwargs` 接收任意字段时，静态签名检查可能误判为 PASS。需进一步检查方法内部是否从 `kwargs` 中取出 `user_id` 并传递给下一层。

7. **异步调用导致追踪困难**：若链路中存在 `await` 异步调用，运行时追踪需等待异步任务完成后再查询数据库，避免读到旧状态。建议在触发采集后等待 3-5 秒再查询。

8. **pytest mock 注入与真实透传不一致**：单测中用 mock 注入 user_id 的链路可能与真实调用链不一致。**单测 PASS 不等于透传完整**，必须配合运行时追踪验证。
