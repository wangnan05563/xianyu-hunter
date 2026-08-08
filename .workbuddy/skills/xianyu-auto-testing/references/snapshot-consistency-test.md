# 快照与最新值一致性测试

本文档描述模式 H（快照与最新值一致性测试模式）的详细操作步骤。

模式 H 用于验证评估事件中"快照值"（评估时入库的值，如 `_eval_snapshot_price`）与"最新值"（enrich 后的 items 表最新值，如 `item_price`）的职责分离是否正确，覆盖快照保存、过滤优先级、fallback 数据合并三类场景。所有参数从 `config.yaml` 的 `snapshot_consistency_test` 段读取，**禁止在文档中硬编码字段名、函数名、价格阈值**。

对应 2026-07-18 卖家评估 Bug 复盘 Bug 1（seller 字段未合并）与 Bug 2B（价格快照缺失）的回归测试需求。

## 1. 识别快照字段

### 1.1 读取快照字段配置

从 `snapshot_consistency_test.snapshot_fields` 读取所有快照字段。每个字段包含：

| 字段 | 含义 |
|------|------|
| `name` | 字段名称（人类可读） |
| `snapshot_field` | 快照字段名（评估事件 payload 中保存评估时的值，如 `_eval_snapshot_price`） |
| `latest_field` | 最新值字段名（items 表中的当前值，如 `item_price`） |
| `enrich_functions` | enrich 覆盖函数列表（可能用 latest_field 覆盖 snapshot_field） |
| `filter_functions` | 过滤函数列表（应优先用 snapshot_field 而非 latest_field） |

### 1.2 字段对应关系示例

以 `snapshot_fields[0]`（评估时价格）为例：

```
评估事件 payload:
  _eval_snapshot_price: 50  ← snapshot_field（评估时写入，不应被覆盖）

items 表:
  item_price: 150  ← latest_field（最新值，enrich 阶段可能读到）

enrich_functions:
  _apply_positive_fields  ← 可能用 item_price 覆盖 _eval_snapshot_price
  _enrich_eval_with_item

filter_functions:
  _filter_price_range      ← 应优先用 _eval_snapshot_price 判断
  _filter_market_ratio
```

## 2. 快照保存验证

### 2.1 触发评估事件写入

通过任意方式触发一次评估事件首次入库（如调用官方采集 API、worker 首次采集）：

```powershell
# {host}              ← web_process.host
# {port}              ← web_process.port
# {trigger_endpoint}  ← data_propagation_integrity_test.propagation_chains[0].trigger_endpoint
curl.exe -X POST "http://{host}:{port}{trigger_endpoint}" -H "Cookie: xh_token={token}"
```

### 2.2 触发官方采集（更新 items 表）

再次触发官方采集，使 items 表的 `item_price`（latest_field）更新为最新值。这一步用于构造"快照值与最新值不一致"的场景。

### 2.3 检查 payload 中是否包含 snapshot_field

直接查询数据库，检查评估事件的 payload 中是否包含 `snapshot_field`：

```powershell
# {db_path}        ← 项目数据库路径
# {snapshot_field} ← snapshot_fields[i].snapshot_field（如 _eval_snapshot_price）
.venv\Scripts\python.exe -c "
import sqlite3, json
conn = sqlite3.connect('{db_path}')
cur = conn.cursor()
cur.execute('SELECT payload FROM eval_events ORDER BY created_at DESC LIMIT 1')
row = cur.fetchone()
if row:
    payload = json.loads(row[0])
    if '{snapshot_field}' in payload:
        print('FOUND: {snapshot_field} =', payload['{snapshot_field}'])
    else:
        print('MISSING: {snapshot_field} not in payload')
conn.close()
"
```

**判定规则**：
- payload 中包含 `snapshot_field` → PASS
- payload 中不包含 `snapshot_field` → **FAIL**（说明评估时未保存快照）

### 2.4 检查 snapshot_field 值是否等于评估时写入的值

验证 `snapshot_field` 的值是否等于评估时写入的值（而非最新值）：

```powershell
# {snapshot_field} ← snapshot_fields[i].snapshot_field
# {latest_field}   ← snapshot_fields[i].latest_field
.venv\Scripts\python.exe -c "
import sqlite3, json
conn = sqlite3.connect('{db_path}')
cur = conn.cursor()
# 读取最新评估事件的 snapshot_field
cur.execute('SELECT payload FROM eval_events ORDER BY created_at DESC LIMIT 1')
event_payload = json.loads(cur.fetchone()[0])
snapshot_value = event_payload.get('{snapshot_field}')

# 读取 items 表的 latest_field
cur.execute('SELECT {latest_field} FROM items ORDER BY updated_at DESC LIMIT 1')
latest_value = cur.fetchone()[0]

print('snapshot_field value:', snapshot_value)
print('latest_field value:', latest_value)
if snapshot_value != latest_value:
    print('PASS: 快照值与最新值不一致，快照已正确保存')
else:
    print('FAIL: 快照值与最新值相同，可能被 enrich 覆盖')
conn.close()
"
```

**判定规则**：
- `snapshot_field` 值 == 评估时写入的值（不同于 latest_field） → PASS
- `snapshot_field` 值 == latest_field 值 → **FAIL**（说明 enrich 函数用 latest_field 覆盖了 snapshot_field）

### 2.5 快照字段一致性矩阵模板

| 快照字段 | payload 含 snapshot_field | snapshot_field 等于评估时值 | enrich 未覆盖 | 结果 |
|---------|--------------------------|----------------------------|--------------|------|
| _eval_snapshot_price | YES | YES | YES | PASS |
| _eval_snapshot_seller_credit | NO | - | - | **FAIL** |

## 3. 过滤优先级验证

### 3.1 读取测试场景

从 `snapshot_consistency_test.test_scenarios` 读取所有测试场景。每个场景包含：

| 字段 | 含义 |
|------|------|
| `name` | 场景名称 |
| `eval_price` | 评估时价格（snapshot_field 值，可为 null） |
| `latest_price` | 最新价格（latest_field 值） |
| `min_price` | 过滤范围下限 |
| `max_price` | 过滤范围上限 |
| `expected_filtered` | 预期是否被过滤（true 表示应过滤，false 表示不应过滤） |

### 3.2 构造测试数据

对每个测试场景，构造评估事件与 items 表数据：

```powershell
.venv\Scripts\python.exe -c "
import sqlite3, json
conn = sqlite3.connect('{db_path}')
cur = conn.cursor()

# 构造评估事件（snapshot_field 用 eval_price）
payload = {{'_eval_snapshot_price': {eval_price}}}
cur.execute('INSERT INTO eval_events (item_id, payload, user_id) VALUES (?, ?, ?)',
    ('test_item_001', json.dumps(payload), 'test_user'))

# 构造 items 表记录（latest_field 用 latest_price）
cur.execute('UPDATE items SET item_price = ? WHERE item_id = ?',
    ({latest_price}, 'test_item_001'))

conn.commit()
conn.close()
"
```

### 3.3 调用过滤函数

调用 `filter_functions` 中的过滤函数，验证是否按预期过滤：

```powershell
.venv\Scripts\python.exe -c "
import sqlite3, json
conn = sqlite3.connect('{db_path}')
cur = conn.cursor()

# 读取评估事件
cur.execute('SELECT payload FROM eval_events WHERE item_id = ?', ('test_item_001',))
event_payload = json.loads(cur.fetchone()[0])
snapshot_price = event_payload.get('_eval_snapshot_price')

# 读取 items 表 latest_field
cur.execute('SELECT item_price FROM items WHERE item_id = ?', ('test_item_001',))
latest_price = cur.fetchone()[0]

# 调用过滤函数（伪代码，实际需 import 项目代码）
# from xianyu_hunter.web.routes.evaluations_list import _filter_price_range
# filtered = _filter_price_range(snapshot_price or latest_price, min_price=10, max_price=100)

# 判定逻辑
if snapshot_price is not None:
    actual_filtered = not (10 <= snapshot_price <= 100)
else:
    actual_filtered = not (10 <= latest_price <= 100)

expected_filtered = {expected_filtered}
print('snapshot_price:', snapshot_price)
print('latest_price:', latest_price)
print('actual_filtered:', actual_filtered)
print('expected_filtered:', expected_filtered)
print('PASS' if actual_filtered == expected_filtered else 'FAIL')
conn.close()
"
```

### 3.4 过滤优先级验证清单

| 场景 | eval_price（snapshot） | latest_price | 范围 | 预期过滤 | 实际过滤 | 判定 |
|------|----------------------|--------------|------|---------|---------|------|
| 评估时在范围内，enrich 后超范围 | 50 | 150 | [10,100] | false | - | - |
| 评估时超范围，enrich 后在范围内 | 200 | 50 | [10,100] | true | - | - |
| 评估时无价格，enrich 后有价格 | null | 150 | [10,100] | false | - | - |

### 3.5 静态扫描验证过滤函数优先级

对每个 `filter_functions`，扫描源码验证其优先用 `snapshot_field` 而非 `latest_field`：

```powershell
# {file}          ← 过滤函数所在文件（如 web/routes/evaluations_list.py）
# {filter_func}   ← filter_functions[i]（如 _filter_price_range）
# {snapshot_field} ← snapshot_fields[i].snapshot_field
# {latest_field}   ← snapshot_fields[i].latest_field
Select-String -Path {file} -Pattern "def\s+{filter_func}" -Encoding UTF8 -Context 0,20 | ForEach-Object {
    "$($_.Path):$($_.LineNumber): $($_.Line)"
}
```

**判定规则**：过滤函数内部应优先读取 `snapshot_field`，仅在 `snapshot_field` 为 None 时 fallback 到 `latest_field`。

## 4. fallback 数据合并验证

### 4.1 读取 fallback 函数配置

从 `snapshot_consistency_test.fallback_functions` 读取所有 fallback 函数对。每个条目包含：

| 字段 | 含义 |
|------|------|
| `name` | 名称 |
| `primary_function` | 主源函数（如 `collector.seller_profile`） |
| `fallback_function` | fallback 函数（如 `seller_profile_fallback`） |
| `merge_on_primary_success` | 主源成功后是否也必须合并次源字段 |
| `merge_fields` | 需要合并的字段列表 |

### 4.2 触发 fallback 路径（主源失败）

构造主源失败场景（如清空 cookie_store 使主源 `seller_profile` 失败），触发 fallback：

```powershell
# {fallback_function} ← fallback_functions[i].fallback_function（如 seller_profile_fallback）
# {merge_fields}      ← fallback_functions[i].merge_fields（如 [nick, credit_score, register_days, sold_count]）
.venv\Scripts\python.exe -c "
# 1. 清空 cookie_store 触发主源失败
# 2. 调用 collector.seller_profile 触发 fallback
# 3. 检查 fallback 返回数据是否包含所有 merge_fields

# 伪代码
from xianyu_hunter.modules.collector import seller_profile_fallback
result = seller_profile_fallback(item_id='test_item_001')
required_fields = {merge_fields}
missing = [f for f in required_fields if not result.get(f)]
print('fallback result:', result)
print('missing fields:', missing)
print('PASS' if not missing else 'FAIL: 缺失字段 ' + str(missing))
"
```

**判定规则**：
- fallback 返回数据包含所有 `merge_fields` → PASS
- fallback 返回数据缺失 `merge_fields` 中任一字段 → **FAIL**

### 4.3 触发主源成功路径

恢复主源（如重新登录恢复 cookie_store），触发主源成功路径：

```powershell
.venv\Scripts\python.exe -c "
# 1. 恢复 cookie_store 使主源成功
# 2. 调用 collector.seller_profile 触发主源
# 3. 检查主源返回数据是否合并了次源字段（补全空字段）

# 伪代码
from xianyu_hunter.modules.collector import seller_profile
result = seller_profile(item_id='test_item_001')
required_fields = {merge_fields}
missing = [f for f in required_fields if not result.get(f)]
print('primary result:', result)
print('missing fields:', missing)
print('PASS' if not missing else 'FAIL: 主源成功后未合并次源字段 ' + str(missing))
"
```

**判定规则**（仅当 `merge_on_primary_success: true`）：
- 主源成功后返回数据包含所有 `merge_fields` → PASS
- 主源成功后返回数据缺失 `merge_fields` 中任一字段 → **FAIL**（主源应合并次源字段补全空字段）

### 4.4 fallback 合并完整性验证清单

| fallback 对 | 主源状态 | merge_fields 完整性 | 主源合并次源字段 | 结果 |
|------------|---------|---------------------|----------------|------|
| seller_profile → seller_profile_fallback | 主源失败 | - | - | - |
| seller_profile → seller_profile_fallback | 主源成功 | - | - | - |

## 5. 失败案例分析

### 5.1 Bug 1：seller 字段未合并

#### 现象

2026-07-18 卖家评估 Bug 复盘中发现：
- 评估事件写入时 seller 字段（如 nick、credit_score、register_days、sold_count）缺失
- 主源 `collector.seller_profile` 失败时调用 fallback `seller_profile_fallback`
- fallback 仅返回 fallback 源字段，未合并主源已有字段
- 导致主源成功后 enrich 阶段读到 fallback 返回值时丢失主源字段

#### 根因

`seller_profile_fallback` 实现仅返回 fallback 源数据，未合并主源已提供的字段。同时主源 `seller_profile` 成功后也未合并次源字段补全空字段。

#### Sequential Thinking 复盘

```
1. 观察：评估事件中 seller 字段（nick/credit_score/register_days/sold_count）缺失
2. 假设 1：评估时未调用 seller_profile → 验证：日志显示调用 → 假设 1 否定
3. 假设 2：seller_profile 主源失败未触发 fallback → 验证：日志显示 fallback 触发 → 假设 2 否定
4. 假设 3：fallback 返回数据字段不完整 → 验证：检查 fallback 实现 → 仅返回 fallback 源字段 → 假设 3 部分成立
5. 假设 4：主源成功后未合并次源字段 → 验证：检查主源实现 → 未合并次源字段补全空字段 → 假设 4 成立
6. 修复：fallback 合并所有可用来源；主源成功后也合并次源字段补全空字段
7. 验证：触发 fallback 路径 → merge_fields 完整 → 修复确认
```

### 5.2 Bug 2B：价格快照缺失

#### 现象

2026-07-18 卖家评估 Bug 复盘中发现：
- 评估事件 payload 中 `_eval_snapshot_price` 字段缺失
- 后续 enrich 阶段用 items 表 `item_price` 覆盖
- 过滤函数 `_filter_price_range` 用最新值过滤，导致评估时在范围内但 enrich 后超范围的记录被误删
- 用户报告"刷新后商品消失"

#### 根因

1. 评估事件写入时未保存 `_eval_snapshot_price` 快照字段
2. enrich 函数 `_apply_positive_fields` 用 `item_price` 覆盖了 payload 中的 `_eval_snapshot_price`
3. 过滤函数 `_filter_price_range` 未优先用 `_eval_snapshot_price`，而是用 `item_price`

#### Sequential Thinking 复盘

```
1. 观察：用户报告刷新后商品消失
2. 假设 1：商品被删除 → 验证：SELECT * FROM items WHERE item_id=xxx → 商品存在 → 假设 1 否定
3. 假设 2：过滤逻辑误删 → 验证：检查 _filter_price_range → 用 item_price（最新值）过滤 → 假设 2 成立
4. 假设 3：评估时价格与最新值不一致 → 验证：检查 payload._eval_snapshot_price → 字段缺失 → 假设 3 成立
5. 假设 4：enrich 覆盖了快照 → 验证：检查 _apply_positive_fields → 用 item_price 覆盖 _eval_snapshot_price → 假设 4 成立
6. 修复：
   a. 评估事件写入时保存 _eval_snapshot_price 快照
   b. enrich 函数不覆盖 _eval_snapshot_price（保护快照）
   c. 过滤函数优先用 _eval_snapshot_price，仅在 None 时 fallback 到 item_price
7. 验证：执行 §2 快照保存验证 + §3 过滤优先级验证 → 全部 PASS → 修复确认
```

## 6. 修复验证流程

### 6.1 静态验证

1. **快照字段保存扫描**：执行 §2.3 检查 payload 中是否包含 `snapshot_field`
2. **enrich 函数覆盖扫描**：扫描 `enrich_functions` 源码，验证未用 `latest_field` 覆盖 `snapshot_field`
3. **过滤函数优先级扫描**：执行 §3.5 扫描 `filter_functions`，验证优先用 `snapshot_field`

### 6.2 运行时验证

1. **快照保存验证**：执行 §2.4 检查 `snapshot_field` 值不等于 `latest_field` 值
2. **过滤优先级验证**：执行 §3.3 调用过滤函数，验证按 `snapshot_field` 过滤而非 `latest_field`

### 6.3 fallback 合并验证

1. **fallback 路径验证**：执行 §4.2 触发主源失败，验证 fallback 返回数据完整性
2. **主源合并验证**：执行 §4.3 触发主源成功，验证主源合并次源字段

### 6.4 回归验证

运行现有 pytest 测试套件，确认未引入新问题。重点关注：
- 评估事件写入相关测试
- 过滤函数相关测试
- fallback 函数相关测试

## 7. 诊断输出

### 7.1 快照字段一致性矩阵

```
## 快照字段一致性矩阵

| 快照字段 | payload 含 snapshot_field | snapshot_field 等于评估时值 | enrich 未覆盖 | 结果 |
|---------|--------------------------|----------------------------|--------------|------|
| _eval_snapshot_price | YES | YES | YES | PASS |
| _eval_snapshot_seller_credit | NO | - | - | FAIL |
```

### 7.2 过滤优先级验证结果

```
## 过滤优先级验证结果

| 场景 | eval_price（snapshot） | latest_price | 范围 | 预期过滤 | 实际过滤 | 判定 |
|------|----------------------|--------------|------|---------|---------|------|
| 评估时在范围内，enrich 后超范围 | 50 | 150 | [10,100] | false | false | PASS |
| 评估时超范围，enrich 后在范围内 | 200 | 50 | [10,100] | true | true | PASS |
| 评估时无价格，enrich 后有价格 | null | 150 | [10,100] | false | false | PASS |

过滤优先级：3/3 PASS
```

### 7.3 fallback 合并完整性结果

```
## fallback 合并完整性结果

### seller_profile 降级

| 主源状态 | merge_fields 完整性 | 主源合并次源字段 | 结果 |
|---------|---------------------|----------------|------|
| 主源失败 | nick=YES, credit_score=YES, register_days=YES, sold_count=YES | - | PASS |
| 主源成功 | nick=YES, credit_score=YES, register_days=YES, sold_count=YES | YES（合并次源补全空字段） | PASS |

fallback 合并：2/2 PASS
```

### 7.4 问题报告格式

```
## 发现的问题

### 问题 1
- 描述：评估事件 payload 中 _eval_snapshot_price 字段缺失，导致过滤函数用 item_price 误删评估时在范围内的记录
- 关联 key_files：src/xianyu_hunter/web/routes/evaluations_list.py
- 复现步骤：
  1. 触发官方采集写入评估事件（item_price=50）
  2. 触发官方采集更新 items 表（item_price=150）
  3. 调用 /api/evaluations 查询评估列表
  4. 观察评估记录被过滤（因 _filter_price_range 用 item_price=150 超出 [10,100] 范围）
- 建议修复方向：
  a. 评估事件写入时保存 _eval_snapshot_price 快照
  b. _apply_positive_fields 不覆盖 _eval_snapshot_price
  c. _filter_price_range 优先用 _eval_snapshot_price
- 关联 Bug：2026-07-18 卖家评估 Bug 复盘 Bug 2B
```

## 8. 已知陷阱

执行模式 H 时需特别注意以下陷阱（来自历史踩坑）：

1. **enrich 函数静默覆盖快照**：`_apply_positive_fields` 等 enrich 函数若用 `dict.update()` 或直接赋值方式覆盖 `snapshot_field`，代码层面难以察觉。**必须运行时验证 payload 中 snapshot_field 值与 latest_field 值不一致**。

2. **过滤函数 fallback 顺序错误**：过滤函数应优先用 `snapshot_field`，仅在 None 时 fallback 到 `latest_field`。若顺序颠倒（先读 latest_field），即使 snapshot_field 存在也会用最新值过滤。

3. **null 快照值的边界处理**：评估时无价格（snapshot_field 为 null）时，过滤函数应 fallback 到 `latest_field`，避免误删有效记录。`test_scenarios[2]`（评估时无价格）专门覆盖此场景。

4. **fallback 函数未合并主源字段**：`seller_profile_fallback` 仅返回 fallback 源字段时，主源已提供的字段会被覆盖丢失。fallback 实现应先复制主源数据，再用 fallback 源字段补全空字段。

5. **主源成功后未合并次源字段**：主源 `seller_profile` 成功后，若未合并次源字段补全空字段，主源未提供的字段（如 register_days）会缺失。`merge_on_primary_success: true` 配置强制要求主源成功后也合并次源。

6. **快照字段命名混淆**：`_eval_snapshot_price`（快照）与 `item_price`（最新值）字段名不同，但若开发时误用 `item_price` 作为快照字段名，会导致 enrich 覆盖后无法区分。命名约定：快照字段以下划线前缀 `_eval_snapshot_` 开头，明确语义。

7. **test_scenarios 数据未清理**：构造测试数据后未清理，会影响后续测试。建议在测试结束后删除 `item_id='test_item_001'` 的评估事件与 items 记录。

8. **数据库时间戳精度**：评估事件与 items 表的 `created_at` / `updated_at` 时间戳精度可能不够（如秒级），多次触发采集后时间戳相同难以区分先后。建议用 `ORDER BY rowid DESC` 取最新记录。

9. **过滤函数副作用**：过滤函数除了过滤外可能还有其他副作用（如修改 payload）。验证时需检查副作用是否符合预期，避免引入新问题。

10. **enrich 函数顺序依赖**：`enrich_functions` 列表中函数按顺序执行，前一个函数的输出是后一个函数的输入。若前一个函数覆盖了 snapshot_field，后一个函数读到的已是覆盖后的值。需按列表顺序逐一验证。
