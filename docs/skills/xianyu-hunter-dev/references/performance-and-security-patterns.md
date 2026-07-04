# 性能与安全编码规范

> 本文档基于闲鱼猎人项目实际排查解决的问题提炼，列举数据库性能优化、安全性、状态管理语义正确性及问题排查方法论方面的编码规范。开发时必须严格遵守带【强制】标记的条文，【建议】条文应在合理场景下采纳。

---

## 一、数据库性能优化

### PS-001: 循环内数据库查询必须批量预查询 【强制】

**问题描述**

去重检查在循环内逐个查询 `get_recently_collected_item_ids([detail.id], ...)`，导致 N+1 查询。当 `new_items` 数量较多时，数据库往返次数线性增长，严重影响性能。

**规范条文**

循环内的数据库查询必须批量预查询，用 `set` 缓存结果，循环内只查缓存。批量查询应在循环外一次性完成。

**代码示例**

正面示例：

```python
# 循环前批量预查询
recent_collected_cache: set[str] | None = None
if eval_cfg and eval_cfg.auto_collect_official:
    all_item_ids = [item.id for item in new_items if item.id]
    if all_item_ids:
        recent_collected_cache = self.repo.get_recently_collected_item_ids(
            all_item_ids,
            eval_cfg.auto_collect_dedup_window_minutes,
        )

# 循环内优先用缓存
if recent_collected_cache is not None:
    recent_ids = recent_collected_cache
elif self.repo is not None:
    recent_ids = self.repo.get_recently_collected_item_ids([detail.id], window)
```

反面示例：

```python
# 循环内逐个查询（N+1）
for item in new_items:
    recent_ids = self.repo.get_recently_collected_item_ids([item.id], window)
```

**适用场景**

任何在循环内查询数据库的场景。

**不适用场景**

循环次数极少（<=3）的场景，此时批量预查询的代码复杂度收益不显著。

---

### PS-002: JSON 字段查询必须用 json_extract 替代 LIKE 【强制】

**问题描述**

stats 端点用 `payload.like('%"data_source"%')` 做全表扫描，无法利用索引，且容易匹配到非目标字段。

**规范条文**

SQLite/MySQL 的 JSON 字段查询必须用 `json_extract()` 函数替代 `LIKE`，避免全表扫描并提升语义准确性。

**代码示例**

正面示例：

```python
from sqlalchemy import func

success_count = conn.execute(
    select(func.count())
    .select_from(EventRow)
    .where(EventRow.type == "eval.scored")
    .where(func.json_extract(EventRow.payload, '$.data_source') == 'official')
).scalar() or 0
```

反面示例：

```python
# LIKE 全表扫描，无法用索引
success_count = conn.execute(
    select(EventRow)
    .where(EventRow.payload.like('%"data_source": "official"%'))
).count()
```

**适用场景**

SQLite/MySQL 的 JSON 字段查询。

**不适用场景**

非 JSON 字段的模糊查询；需要全文检索的场景应使用专门的全文索引方案。

---

## 二、安全性规范

### PS-003: 异常消息必须脱敏后存储 【强制】

**问题描述**

`str(e)[:500]` 可能包含 token/Cookie 等敏感信息，直接写入数据库后会泄露到 events 表和前端，造成安全风险。

**规范条文**

异常消息写入数据库/日志/前端前，必须用正则脱敏 token/Cookie 等敏感信息，并对结果做长度截断。

**代码示例**

正面示例：

```python
import re

_SENSITIVE_PATTERNS = [
    re.compile(r'(token=)[^&\s"\'<>]+', re.IGNORECASE),
    re.compile(r'((?:[Cc]ookie)\s*:\s*)[^\r\n]+'),
    re.compile(r'(_m_h5_tk=)[^;]+'),
    re.compile(r'(unb=)[^;]+'),
    re.compile(r'(cookie2=)[^;]+'),
    re.compile(r'(sgcookie=)[^;]+'),
]

def _sanitize_error(text: str, max_len: int = 500) -> str:
    """对异常消息脱敏后截断，避免 token/Cookie 泄露"""
    sanitized = text
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(r'\1***', sanitized)
    return sanitized[:max_len]

# 使用
error_msg = _sanitize_error(str(e))
```

反面示例：

```python
error_msg = str(e)[:500]  # 可能泄露 token/Cookie
```

**适用场景**

任何将异常消息存储或传输到外部的场景（写入数据库、记录日志、返回前端、上报监控等）。

**不适用场景**

仅在内存中处理的异常（不持久化/不传输）。

---

### PS-004: 敏感信息脱敏模式必须提取为模块级常量 【强制】

**问题描述**

在函数内定义脱敏正则会导致每次调用都重新编译，且难以复用和维护。

**规范条文**

脱敏正则模式必须提取为模块级常量（通常以 `_SENSITIVE_PATTERNS` 命名），禁止在函数内定义。模块级常量在模块加载时编译一次，便于复用与统一维护。

**适用场景**

任何有脱敏需求的场景。

**代码示例**

正面示例：

```python
# 模块级常量，模块加载时编译一次
_SENSITIVE_PATTERNS = [
    re.compile(r'(token=)[^&\s"\'<>]+', re.IGNORECASE),
    re.compile(r'((?:[Cc]ookie)\s*:\s*)[^\r\n]+'),
]

def _sanitize_error(text: str) -> str:
    sanitized = text
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(r'\1***', sanitized)
    return sanitized
```

反面示例：

```python
def _sanitize_error(text: str) -> str:
    # 每次调用都重新编译，且难以复用
    patterns = [
        re.compile(r'(token=)[^&\s"\'<>]+', re.IGNORECASE),
        re.compile(r'((?:[Cc]ookie)\s*:\s*)[^\r\n]+'),
    ]
    for pattern in patterns:
        text = pattern.sub(r'\1***', text)
    return text
```

---

## 三、状态管理语义正确性

### PS-005: 计数器语义必须与变量名一致 【强制】

**问题描述**

`_consecutive_collect_failures` 仅在失败时自增、成功时不清零，导致实际语义变成"累计失败"而非"连续失败"，最终在累计失败次数达到阈值时错误触发暂停。

**规范条文**

计数器的语义必须与变量名一致——"连续失败计数器"必须在成功时清零，否则应改名为"累计失败计数器"（如 `_total_failures`）。命名与行为任何一方变更时，必须同步另一方。

**代码示例**

正面示例：

```python
# 成功时清零连续失败计数器
await self.official_collect_fn(detail.id, self.task.id)
stats.official_collected += 1
self._consecutive_collect_failures = 0  # 连续失败语义：成功时重置
```

反面示例：

```python
# 成功时不清零，导致"累计失败"触发暂停
await self.official_collect_fn(detail.id, self.task.id)
stats.official_collected += 1
# 缺少 self._consecutive_collect_failures = 0
```

**适用场景**

任何有状态计数器的场景。

**不适用场景**

确实需要累计统计的场景（此时变量名应改为 `_total_failures` 等表达累计语义的名称）。

---

### PS-006: 前端阈值必须从后端配置获取 【强制】

**问题描述**

前端用 `collectStats.failed >= 3` 硬编码阈值判断"已暂停"，且 `failed` 是累计数而非连续数，与后端实际暂停逻辑（基于连续失败）不一致，导致前端显示与后端状态脱节。

**规范条文**

阈值/限制值必须从后端配置获取，不得在前端硬编码。前端状态判断应使用后端返回的 `is_paused` 布尔值，而非自行根据计数器推断。

**代码示例**

正面示例：

```tsx
// 后端返回 is_paused + fail_pause_threshold
{collectStats.is_paused && (
  <Tag color="red">
    已暂停（连续失败达阈值 {collectStats.fail_pause_threshold} 次）
  </Tag>
)}
```

反面示例：

```tsx
// 硬编码阈值，且用累计数而非连续数
{collectStats.failed >= 3 && <Tag color="red">已暂停</Tag>}
```

**适用场景**

任何前端判断业务状态的场景。

**不适用场景**

纯 UI 状态（如 loading/visible/折叠展开）的判断。

---

### PS-007: 新一轮处理必须重置上一轮状态 【强制】

**问题描述**

`_consecutive_collect_failures` 未在新一轮 `run_once` 开始时重置，导致上一轮的失败延续到本轮，使新一轮在尚未发生任何失败时就接近或达到暂停阈值。

**规范条文**

跨商品/跨轮次累积的状态计数器，必须在新一轮处理开始时重置，保证每轮的状态起点是干净的。

**代码示例**

正面示例：

```python
async def run_once(self) -> RunResult:
    stats = RunStats()
    # 新一轮重置上一轮的连续失败计数
    self._consecutive_collect_failures = 0
```

反面示例：

```python
async def run_once(self) -> RunResult:
    stats = RunStats()
    # 未重置 _consecutive_collect_failures，上一轮失败会延续到本轮
```

**适用场景**

任何跨轮次累积的状态（连续失败计数、重试计数、阶段状态等）。

**不适用场景**

需要跨轮次保留的历史数据（如总采集数、运行日志等）。

---

## 四、问题排查方法论

### PS-008: 问题排查的标准化流程 【建议】

**规范条文**

运行时问题排查必须遵循以下标准化流程，避免遗漏关键环节：

1. 明确问题现象（复现条件、预期 vs 实际）
2. 追踪调用链（前端→后端→外部 API）
3. 对比参数传递（多入口差异）
4. 定位代码缺陷（静态分析）
5. 查看日志确认运行时状态
6. 提出解决方案
7. 应用修复并语法校验
8. 添加调试日志/测试用例验证
9. 用户验证

**适用场景**

任何运行时问题的排查。

**不适用场景**

纯代码风格/命名问题（直接静态分析即可，无需走完整流程）。

---

### PS-009: 修复后必须验证假设 【强制】

**问题描述**

价格问题首次修复后用户反馈"问题依然存在"，说明仅凭代码静态分析无法确认修复有效——实际运行时的数据流可能与预期不同。

**规范条文**

修复后必须用实际数据（日志/测试用例）验证修复效果，不能仅凭代码分析就认定修复成功。验证证据应包含在修复说明中。

**适用场景**

任何涉及数据提取/转换/过滤的修复。

**不适用场景**

纯逻辑修复且有测试覆盖的场景（测试通过即可作为验证证据）。
