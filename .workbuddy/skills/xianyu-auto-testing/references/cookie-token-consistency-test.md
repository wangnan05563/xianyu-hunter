# Cookie-Token 一致性测试

本文档描述模式 I（Cookie-Token 一致性测试模式）的详细操作步骤。

模式 I 用于验证身份 Cookie 与签名 token（`_m_h5_tk`）的状态分离与一致性保障，覆盖 Cookie 补注入、Token 重置独立性、续期闭环回写、日志占位符合规性、静默异常禁止五类场景。所有参数从 `config.yaml` 的 `cookie_token_consistency_test` 段读取，**禁止在文档中硬编码 Cookie 名称、域列表、方法名、正则模式**。

对应 2026-07-22 `FAIL_SYS_ILLEGAL_ACCESS` token 不匹配问题复盘的回归测试需求。根因：浏览器已有身份 Cookie 但 `_m_h5_tk` token 不匹配，Worker 浏览器启动时生成的匿名 token 残留内存导致 MTOP API 签名验证失败。

---

## 1. 场景 1：Cookie 补注入测试

### 1.1 读取补注入配置

从 `cookie_token_consistency_test.cookie_injection` 读取参数：

| 参数 | 含义 |
|------|------|
| `identity_cookies` | 身份 Cookie 列表（必须全部存在才认为身份 Cookie 完整） |
| `inject_domains` | 允许补注入的域（只注入这些域的 Cookie，防止跨域污染） |
| `test_cases` | 测试用例列表（I-01 ~ I-03） |

### 1.2 测试用例 I-01：缺所有身份 Cookie 时全量补注入

**前置条件**：浏览器 Cookie 为空（模拟刚启动的 Worker 浏览器实例）。

**操作步骤**：

1. 启动 Worker 浏览器实例，清空所有 Cookie
2. 触发实时搜索（调用 `api_task_links` 的搜索入口）
3. 检查日志中是否出现"补注入身份 Cookie"相关日志
4. 验证浏览器 Cookie 中是否包含 `identity_cookies` 中的所有 Cookie

**验证脚本**：

```powershell
# {db_path}            ← 项目数据库路径
# {identity_cookies}   ← cookie_injection.identity_cookies（从 config.yaml 读取）
.venv\Scripts\python.exe -c "
import sqlite3, json
conn = sqlite3.connect('{db_path}')
cur = conn.cursor()
cur.execute('SELECT cookies FROM cookie_store ORDER BY rowid DESC LIMIT 1')
row = cur.fetchone()
if row:
    cookies = json.loads(row[0])
    stored_names = {c['name'] for c in cookies}
    required = set({identity_cookies})
    missing = required - stored_names
    if missing:
        print('FAIL: missing identity cookies:', missing)
    else:
        print('PASS: all identity cookies present')
else:
    print('FAIL: no cookie store found')
conn.close()
"
```

### 1.3 测试用例 I-02：缺部分身份 Cookie 时增量补注入

**前置条件**：浏览器只有 `identity_cookies[0]`（如 `unb`），缺少其余。

**操作步骤**：

1. 启动 Worker 浏览器，只注入 `identity_cookies[0]`
2. 触发实时搜索
3. 验证浏览器补注入了缺失的 Cookie（而非全量重新注入）

### 1.4 测试用例 I-03：身份 Cookie 完整时不触发补注入

**前置条件**：浏览器已包含所有 `identity_cookies`。

**操作步骤**：

1. 启动 Worker 浏览器，注入所有 `identity_cookies`
2. 触发实时搜索
3. 验证日志中**不**出现"补注入身份 Cookie"相关日志
4. 验证浏览器 Cookie 未被重复覆盖

---

## 2. 场景 2：Token 重置独立性测试

### 2.1 读取 Token 重置配置

从 `cookie_token_consistency_test.token_reset_independence` 读取参数：

| 参数 | 含义 |
|------|------|
| `token_refresh_field` | token 刷新时间戳字段名（如 `_last_m5tk_refresh`） |
| `token_reset_value` | 重置值（强制刷新，通常为 `0.0`） |
| `test_cases` | 测试用例列表（I-04 ~ I-05） |

### 2.2 测试用例 I-04：补注入后必须重置 token

**核心验证点**：执行了 Cookie 补注入后，`token_refresh_field` 必须被重置为 `token_reset_value`。

**操作步骤**：

1. 构造 Cookie 缺失场景（触发 I-01 或 I-02 的补注入流程）
2. 在补注入代码执行后、实时搜索发起前，检查 `token_refresh_field` 的值
3. 验证其等于 `token_reset_value`（`0.0`）

**代码静态检查**：

扫描 `api_task_links.py`，验证补注入代码块后紧接 token 重置逻辑，且重置逻辑**不在**补注入的 `if` 块内部：

```powershell
# {token_refresh_field} ← token_reset_independence.token_refresh_field
# {file_path}           ← modules/api_task_links.py
Select-String -Path '{file_path}' -Pattern '{token_refresh_field}\s*=\s*0\.0'
```

**违规模式**（重置在 if 块内部，仅补注入时执行）：

```python
# ❌ 错误：token 重置在 if injected 块内
if missing_cookies:
    inject_cookies(missing_cookies)
    self._last_m5tk_refresh = 0.0  # ← 仅补注入时重置，未补注入时不会重置
```

**正确模式**（重置独立于补注入）：

```python
# ✅ 正确：无论是否补注入都重置
if missing_cookies:
    inject_cookies(missing_cookies)
self._last_m5tk_refresh = 0.0  # ← 独立于补注入，始终执行
```

### 2.3 测试用例 I-05：未补注入时也必须重置 token

**核心验证点**：身份 Cookie 完整未触发补注入，`token_refresh_field` 仍必须被重置。

**操作步骤**：

1. 构造 Cookie 完整场景（I-03 条件）
2. 触发实时搜索
3. 验证 `token_refresh_field` 被重置为 `token_reset_value`（即使没有执行补注入）

---

## 3. 场景 3：续期闭环回写测试

### 3.1 读取续期闭环配置

从 `cookie_token_consistency_test.renewal_loop_writeback` 读取参数：

| 参数 | 含义 |
|------|------|
| `nav_url` | 续期导航 URL |
| `nav_timeout_ms` | 导航超时（毫秒） |
| `export_domains` | 回写域（提取这些域的 Cookie 回写） |
| `method_tag` | 回写方法标记（用于日志区分回写来源） |
| `writeback_failure_blocks_renewal` | 回写失败是否阻断续期 |

### 3.2 测试用例 I-06：续期后必须回写 CookieStore JSON

**核心验证点**：导航成功后必须调用 `browser.get_cookies(export_domains)` + `export_cookies(method=method_tag)` 回写 JSON 和 SQLite。

**操作步骤**：

1. 构造 token 过期场景（等待 `_m_h5_tk` TTL 到期，或手动清除 token）
2. 触发实时搜索，使 TokenRenewer 续期回调被触发
3. 检查 `login_orchestrator.py` 中续期回调是否包含 `get_cookies` + `export_cookies` 调用
4. 验证 CookieStore JSON 文件中 `method` 字段等于 `method_tag`（`"renew"`）

**代码静态检查**：

```powershell
# {file_path} ← modules/login_orchestrator.py
Select-String -Path '{file_path}' -Pattern 'export_cookies.*method.*renew'
```

### 3.3 测试用例 I-07：回写失败不阻断续期

**核心验证点**：回写失败时只记 `logger.warning`，不返回 `False` 阻断续期流程。

**操作步骤**：

1. Mock `export_cookies` 方法使其抛出异常
2. 触发续期流程
3. 验证续期仍返回成功（而非 `False`）
4. 验证日志中出现 `logger.warning` 级别的回写失败记录

**违规模式**（回写失败阻断续期）：

```python
# ❌ 错误：回写失败返回 False 阻断续期
try:
    cookies = browser.get_cookies(domains)
    export_cookies(cookies, method="renew")
except Exception:
    return False  # ← 阻断了续期流程
```

**正确模式**（回写失败不阻断）：

```python
# ✅ 正确：回写失败只记 warning，不阻断
try:
    cookies = browser.get_cookies(domains)
    export_cookies(cookies, method="renew")
except Exception:
    logger.warning("续期后回写 CookieStore 失败，不影响续期结果")  # ← 只记日志
```

---

## 4. 场景 4：日志占位符合规性测试

### 4.1 读取日志占位符配置

从 `cookie_token_consistency_test.loguru_placeholder` 读取参数：

| 参数 | 含义 |
|------|------|
| `logger_library` | 日志库名称（`loguru`） |
| `correct_placeholder` | 正确占位符（`{}`） |
| `forbidden_placeholders` | 禁止占位符列表（`%s`、`%d`、`%f`、`%r`） |
| `exceptions_use_brace_not_fstring` | 异常对象日志是否用 `{}` 而非 f-string |

### 4.2 测试用例 I-08：loguru 日志禁止使用 %s 占位符

**操作步骤**：

扫描所有 Python 文件中 `logger.xxx()` 调用，检查是否使用了 `forbidden_placeholders` 中的占位符。

```powershell
# {scan_pattern} ← loguru_placeholder.test_cases[I-08].scan_pattern
# {backend_dir}  ← 后端代码目录
Select-String -Path '{backend_dir}\*.py' -Pattern 'logger\.\w+\(.*%[sdrf].*\)' -Recurse
```

**违规示例**：

```python
# ❌ 错误：loguru 日志使用 %s 占位符（标准库 logging 风格）
logger.warning("Cookie 不完整: %s", missing_cookies)
```

**正确示例**：

```python
# ✅ 正确：loguru 日志使用 {} 占位符
logger.warning("Cookie 不完整: {}", missing_cookies)
```

### 4.3 测试用例 I-09：异常对象日志用大括号而非 f-string

**操作步骤**：

扫描所有 Python 文件中记录异常对象的 `logger.xxx()` 调用，检查是否使用了 f-string 嵌入异常对象。

**违规示例**：

```python
# ❌ 错误：用 f-string 嵌入异常对象
except Exception as e:
    logger.error(f"搜索失败: {e}")
```

**正确示例**：

```python
# ✅ 正确：用 {} 占位符传参
except Exception as e:
    logger.error("搜索失败: {}", e)
```

---

## 5. 场景 5：静默异常禁止测试

### 5.1 读取静默异常配置

从 `cookie_token_consistency_test.silent_exception_ban` 读取参数：

| 参数 | 含义 |
|------|------|
| `critical_path_patterns` | 关键路径方法名模式列表 |
| `critical_path_min_level` | 关键路径最小日志级别（`exception`） |
| `auxiliary_path_min_level` | 辅助路径最小日志级别（`warning`） |
| `forbidden_patterns` | 禁止的异常处理模式（正则列表） |
| `exceptions_allowed_debug` | 允许 debug 级别的预期异常类型 |

### 5.2 测试用例 I-10：禁止 except: pass 静默异常

**操作步骤**：

扫描所有 Python 文件中的 `except` 块，检查是否存在完全静默的处理（`pass`、`...`、空块）。

```powershell
# {backend_dir} ← 后端代码目录
Select-String -Path '{backend_dir}\*.py' -Pattern 'except.*:\s*(pass|\.\.\.)' -Recurse
```

**违规示例**：

```python
# ❌ 错误：完全静默的异常处理
try:
    cookies = browser.get_cookies()
except Exception:
    pass  # ← 完全静默，排查时无法定位
```

**正确示例**：

```python
# ✅ 正确：至少记 warning 级别日志
try:
    cookies = browser.get_cookies()
except Exception as e:
    logger.warning("获取 Cookie 失败: {}", e)
```

### 5.3 测试用例 I-11：关键路径必须用 logger.exception

**操作步骤**：

扫描 `critical_path_patterns` 中列出的关键路径方法，验证其 `except` 块使用了 `logger.exception()`（输出完整 traceback）。

```powershell
# {critical_path_patterns} ← silent_exception_ban.critical_path_patterns（如 _on_startup, run_migrations 等）
# {backend_dir}            ← 后端代码目录
foreach ($pattern in {critical_path_patterns}) {
    $files = Select-String -Path '{backend_dir}\*.py' -Pattern "def\s+$pattern" -Recurse
    foreach ($file in $files) {
        # 检查该函数的 except 块是否用 logger.exception
        Write-Host "检查文件: $($file.Path) 行: $($file.LineNumber)"
    }
}
```

**违规示例**（关键路径用 `logger.warning(f'...')` 而非 `logger.exception()`）：

```python
# ❌ 错误：关键路径用 f-string warning，丢失 traceback
def _on_startup():
    try:
        run_migrations()
    except Exception as e:
        logger.warning(f"启动失败: {e}")  # ← 无 traceback，无法定位根因
```

**正确示例**（关键路径用 `logger.exception()`）：

```python
# ✅ 正确：关键路径用 logger.exception，保留完整 traceback
def _on_startup():
    try:
        run_migrations()
    except Exception:
        logger.exception("启动失败")  # ← 输出完整 traceback
```

---

## 6. 关联规范与审查点

| 关联类型 | 编号 | 描述 |
|----------|------|------|
| 元规范 | meta-rule #84 | Cookie-Token 状态分离与一致性保障 |
| 开发规范 step 243 | COOKIE-TOKEN-CONSISTENCY-01 | Cookie-Token 一致性保障规范 |
| 开发规范 step 244 | RENEWAL-LOOP-COMPLETENESS-01 | 续期闭环完整性规范 |
| 开发规范 step 245 | LOGURU-PLACEHOLDER-01 | 日志占位符格式规范 |
| 开发规范 step 246 | SILENT-EXCEPTION-BAN-01 | 静默异常禁止规范 |
| 后端审查 B-REVIEW-242 | COOKIE-TOKEN-CONSISTENCY | Cookie-Token 一致性审查 |
| 后端审查 B-REVIEW-243 | RENEWAL-LOOP-COMPLETENESS | 续期闭环完整性审查 |
| 后端审查 B-REVIEW-244 | LOGURU-PLACEHOLDER | 日志占位符格式审查 |
| 后端审查 B-REVIEW-245 | SILENT-EXCEPTION-BAN | 静默异常禁止审查 |
| 前端审查 F-REVIEW-199 | LIVE-SEARCH-ERROR-ALIGNMENT | 实时搜索错误消息对齐 |

---

## 7. 适用与不适用场景

### 7.1 适用场景

- Worker 浏览器多进程共享 Cookie 场景
- TokenRenewer 续期回调场景
- 依赖 `_m_h5_tk` 签名的 MTOP API 调用场景
- loguru 日志库的后端 Python 代码
- 关键启动/迁移/初始化路径的异常处理

### 7.2 不适用场景

- 纯前端 JavaScript/TypeScript 代码（日志占位符规范不适用）
- 使用标准库 `logging` 的项目（占位符规范为 `%s`，与 loguru 相反）
- 单进程无 Cookie 共享的简单爬虫
- 无续期机制的一次性 token 场景
- 预期异常且已用 `logger.debug` 记录的 `exceptions_allowed_debug` 中列出的异常类型
