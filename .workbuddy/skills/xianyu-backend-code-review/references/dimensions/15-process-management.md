# 维度 15：进程管理

> **编码规范引用**：coding-standards v1.3 hard constraints §WebView2
> **配置节点**：config.yaml#process_management
> **参考文档**：references/browser-subprocess-patterns.md

## 触发条件
- 新增/修改子进程启动代码时
- 使用 WebView2/Playwright 打开浏览器时
- 子进程 stdout/stderr 重定向时

## 检查规则

### 强制（P0 阻塞）
- WebView2 子进程必须使用 `CREATE_NEW_CONSOLE` 而非 `CREATE_NO_WINDOW`（防止 GUI 窗口闪退）
- WebView2 子进程不重定向 `stdout`/`stderr` 到 `DEVNULL`（保留调试输出）
- `webview.start()` 必须 `private_mode=False` + 唯一 `storage_path`（格式 `webview_data_{pid}_{timestamp}`）持久化 Cookie 并防冲突

### 推荐（P1 严重）
- Web 进程使用 `with_browser=False` 模式节省内存
- 子进程心跳与阶段超时协同：阶段允许累计超时 = 心跳阈值 × (1 - safety_margin)（B-REVIEW-227）
- 子进程异常不应静默：通过 status file 或日志报告
- Playwright `launch_persistent_context` 前清理 `SingletonLock` 锁文件
- 多个 Chromium 进程不能并发使用同一 `user_data_dir`

### 禁止
- `CREATE_NO_WINDOW` 用于 WebView2 子进程
- `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` 用于 WebView2
- 不传 `storage_path` 或使用默认共享路径的 `webview.start()`
- `launch_persistent_context` 前不清理 `SingletonLock`

## Grep 扫描命令
```bash
# 检测 WebView2 违规标志
grep -rn "CREATE_NO_WINDOW" src/xianyu_hunter/
grep -rn "CREATE_NEW_CONSOLE" src/xianyu_hunter/

# 检测 DEVNULL 重定向
grep -rn "DEVNULL" src/xianyu_hunter/

# 检测 webview.start 缺少 storage_path
grep -rn "webview\.start(" src/xianyu_hunter/ | grep -v "storage_path"

# 检测 SingletonLock 清理缺失
grep -rn "launch_persistent_context" src/xianyu_hunter/ -A 5 | grep -v "SingletonLock\|_cleanup"
```

## 判断标准
- CREATE_NO_WINDOW：P0 阻塞
- stdout/stderr → DEVNULL：P0 阻塞
- 缺少 storage_path：P0 阻塞
- 缺 SingletonLock 清理：P1 严重

## 适用场景
- `scripts/browser_login.py` 浏览器登录脚本
- `src/xianyu_hunter/infra/browser.py` 浏览器管理
- `src/xianyu_hunter/web/services/auth_manager.py` 认证管理
- 所有 `subprocess.Popen` 启动 Chromium/WebView2 的代码

## 不适用场景
- 非 WebView2 的普通子进程（如 `uvicorn` 启动）
- 前端 JS 代码
- Docker 容器中的无头浏览器启动
