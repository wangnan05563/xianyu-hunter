# 维度 22：闲鱼项目规范

> **编码规范引用**：coding-standards v1.3 §Hard Constraints（项目记忆）
> **配置节点**：config.yaml#hard_constraints / project_conventions

## 触发条件
- 任何后端 Python 文件变更
- auth 相关端点增删
- KBManager 或向量化相关代码变更
- Web 进程/浏览器启动配置变更

## 检查规则

### 强制（P0 阻塞）
- **auth_whitelist 端点完整性**：以下端点必须在认证白名单中：`/api/auth/cookie`、`/api/auth/me`、`/api/auth/import-from-browser`、`/import-from-browser/status`、`/api/events/stream`、`/api/notifications`、`/api/notifier/`、`/api/about`、`/api/about/check-update`
- **Web 进程**：必须使用 `with_browser=False` 模式以节省内存
- **hmac 比较**：Token 比较必须使用 `hmac.compare_digest()` 防止时序攻击
- **401 响应**：必须返回 JSON 格式 `{"detail": "Unauthorized"}`，非纯文本
- **敏感字段不记录**：token 长度等敏感字段不得写入日志，仅记录布尔匹配结果
- **Token 写入失败**：必须触发 `logging.warning()` 告警

### 推荐（P1 严重）
- **KBManager `_scan_and_chunk` 排除目录**：必须排除 `web/static/`、`web/templates/`、`__pycache__/`、`node_modules/`、`.git/`、`dist/`、`build/`；仅索引 `.md`/`.py`/`.jsonl`/`.txt` 文件
- **htmx credentials**：必须使用官方 `<meta>` 配置 credentials，确保初始化时序可靠
- **前端 fetch**：必须包含 `credentials: 'include'` 传认证信息
- **WebView2 配置**：子进程用 `CREATE_NEW_CONSOLE` 而非 `CREATE_NO_WINDOW`；不重定向 stdout/stderr 到 DEVNULL；`private_mode=False` + 唯一 `storage_path`（格式 `webview_data_{pid}_{timestamp}`）

### 禁止
- 缺失 import（如 `re`、`threading`、`logging`）导致运行时 NameError
- WebView2 使用 `CREATE_NO_WINDOW` 标志
- WebView2 重定向 stdout/stderr 到 DEVNULL

## Grep 扫描命令

```bash
# auth_whitelist 端点完整性
grep -rn "auth_whitelist\|AUTH_WHITELIST\|whitelist" src/xianyu_hunter/ --include="*.py"

# with_browser 模式
grep -rn "with_browser\s*=\s*True" src/xianyu_hunter/ --include="*.py"

# hmac.compare_digest
grep -rn "compare_digest\|== token\|token ==" src/xianyu_hunter/ --include="*.py"

# KBManager _scan_and_chunk 排除目录
grep -rn "_scan_and_chunk\|exclude.*dir" src/xianyu_hunter/ --include="*.py"
grep -rn "\.js\|\.css\|\.html" src/xianyu_hunter/ --include="*.py" | grep -i "scan\|chunk\|index"

# WebView2 子进程配置
grep -rn "CREATE_NO_WINDOW\|CREATE_NEW_CONSOLE\|DEVNULL" src/xianyu_hunter/ --include="*.py"

# 前端 credentials
grep -rn "credentials.*include" frontend/src/ --include="*.ts" --include="*.tsx"
```

## 判断标准
- auth_whitelist 缺少端点 → P0 阻塞
- `with_browser=True` → P0 阻塞
- 未使用 `hmac.compare_digest()` → P0 阻塞
- KBManager 未排除前端构建产物目录 → P1 严重
- WebView2 用 `CREATE_NO_WINDOW` → P1 严重
- 前端 fetch 缺少 `credentials: 'include'` → P1 严重

## 适用/不适用场景
- **适用**：所有后端代码审查；Auth/KBManager/WebView2 相关代码变更
- **不适用**：纯测试代码；非 WebView2 的 Playwright 浏览器管理（走 `browser-subprocess.md`）
