# 浏览器 Cookie 导入功能完善设计

> 日期：2026-06-25
> 状态：设计阶段
> 关联模块：`web/routes/browser_import.py`、`modules/login_strategy.py`、`web/services/cookie_store.py`

## 1. 背景与目标

### 1.1 现状

项目已实现从系统浏览器导入 Cookie 的功能（策略 C：BROWSER\_IMPORT），位于 [browser\_import.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/browser_import.py)。支持三种加密格式解密：

* 明文 Cookie

* v10 前缀（Chrome v80+ AES-256-GCM）

* 无前缀（旧版 Chrome DPAPI）

### 1.2 待解决问题

| # | 问题                      | 影响                                                             |
| - | ----------------------- | -------------------------------------------------------------- |
| A | **v20 加密不支持**           | Chrome/Edge v127+ 默认启用 App-Bound Encryption，当前检测到 v20 即放弃，无法解密 |
| B | **仅支持 Default Profile** | 用户若用 `Profile 1`/`Profile 2` 登录闲鱼，找不到 Cookie                   |
| C | **零测试覆盖**               | 解密逻辑、文件锁规避等关键路径无回归保障                                           |
| G | **需手动触发**               | Cookie 过期后无法自动刷新，需用户手动点击导入                                     |

### 1.3 目标

1. v20 加密场景下能通过 CDP 协议获取明文 Cookie
2. 支持遍历浏览器所有 Profile，自动定位含闲鱼 Cookie 的 Profile
3. 关键路径测试覆盖率 ≥ 80%
4. 支持定时自动同步，Cookie 即将过期时自动触发导入

## 2. 技术方案

### 2.1 v20 加密方案：CDP 接管浏览器（方案 A）

**原理**：用户以 `--remote-debugging-port=9222` 启动 Edge，项目通过 CDP 协议的 `Network.getAllCookies` 直接获取明文 Cookie，完全绕过加密问题。

**关键约束**（Chrome 136+）：

* `--remote-debugging-port` 必须配合 `--user-data-dir` 指向非标准目录

* `--load-extension` 命令行参数已被移除（Chrome 137）

**方案选择理由**：

* 官方 API，稳定可靠，不依赖加密格式

* 项目已有 Playwright，可复用 `connect_over_cdp`

* 获取的是明文 Cookie，无需任何解密逻辑

* 不触碰系统安全（无需 COM 劫持或进程注入）

### 2.2 多 Profile 发现方案

**原理**：

1. 读取 `Local State` 的 `profile.info_cache` 获取所有 Profile 名称
2. 兜底：扫描 `User Data` 下匹配 `Default|Profile \d+` 的目录
3. 用 `immutable=1` 只读打开每个 Profile 的 Cookies DB，查询 `_m_h5_tk` 是否存在（不解密，只看 name）
4. 含闲鱼 Cookie 的 Profile 优先级排在前

### 2.3 定时同步方案

**原理**：复用项目已有的 `apscheduler`，在 Cookie 即将过期时自动触发导入流程。

**降级策略**：

1. 优先尝试离线导入（browser\_import.py，支持 v10/DPAPI/明文）
2. 离线失败（v20 或文件锁）则尝试 CDP 导入（需浏览器以调试端口运行）
3. 都失败则记录日志，等待下次重试
4. 连续 3 次失败后降低频率（间隔翻倍，上限 2 小时）

## 3. 架构设计

### 3.1 模块划分

```
src/xianyu_hunter/web/routes/browser_import.py       # 现有：离线解密导入（保留，增加 v20 检测委托）
src/xianyu_hunter/web/routes/browser_import_cdp.py   # 新增：CDP 在线导入
src/xianyu_hunter/web/services/browser_profile.py    # 新增：Profile 发现与遍历
src/xianyu_hunter/modules/cookie_sync_scheduler.py   # 新增：定时同步调度
tests/test_browser_import.py                         # 新增：离线导入单元测试
tests/test_browser_profile.py                         # 新增：Profile 发现测试
tests/test_cookie_sync_scheduler.py                   # 新增：调度测试
tests/test_browser_import_cdp.py                      # 新增：CDP 导入测试
scripts/start_edge_debug.ps1                          # 新增：一键启动调试 Edge
```

### 3.2 职责边界

| 模块                            | 职责                                  | 不做什么                            |
| ----------------------------- | ----------------------------------- | ------------------------------- |
| `browser_import.py`（现有）       | 离线解密导入（v10/DPAPI/明文）                | 不处理 v20，检测到 v20 时返回特定错误码委托给 CDP |
| `browser_import_cdp.py`（新）    | CDP 连接运行中的浏览器获取明文 Cookie            | 不做离线解密，不启动浏览器                   |
| `browser_profile.py`（新）       | 发现所有 Profile，找出含闲鱼 Cookie 的 Profile | 不做解密，只做检测                       |
| `cookie_sync_scheduler.py`（新） | 定时触发同步，管理重试与降级                      | 不做具体导入逻辑，委托给上述模块                |

### 3.3 数据流

```
[定时调度器] 或 [用户手动触发]
        ↓
   [策略选择]  ← 检测加密格式
      ├─ v10/明文/DPAPI → browser_import.py（离线解密，现有逻辑）
      │                       ↓
      │                 [browser_profile.py] 遍历所有 Profile
      │                       ↓
      └─ v20/检测失败   → browser_import_cdp.py（CDP 在线获取）
                              ↓
                    [cookie_store.export_cookies()] 写入 JSON + SQLite（现有）
                              ↓
                    [validate_imported_cookies()] 验证 Cookie 完整性
```

### 3.4 与现有系统的集成点

1. **登录策略选择器** [login\_strategy.py#L31-L37](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/login_strategy.py#L31-L37)：在 `BROWSER_IMPORT` 策略内部增加 v20 检测分支
2. **CookieStore** [cookie\_store.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/services/cookie_store.py)：复用 `export_cookies()` 写入，不改动
3. **APScheduler**：项目已用 `apscheduler>=3.10`，复用现有调度器
4. **配置**：在 `config.yaml` 的 `browser` 节点下新增 `auto_sync` 配置项

## 4. 模块详细设计

### 4.1 browser\_profile.py - Profile 发现

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class BrowserProfile:
    """浏览器单个 Profile 的元信息"""
    name: str           # "Default" / "Profile 1" / "Profile 2"
    user_data_dir: Path # User Data 根目录
    cookies_db: Path    # .../Default|Profile N/Network/Cookies
    local_state: Path   # .../Local State（AES 密钥）
    has_xianyu_cookie: bool  # 是否含 _m_h5_tk 等闲鱼 Cookie

def discover_profiles(browser: str) -> list[BrowserProfile]:
    """遍历 User Data 下所有 Profile 目录
    
    优先级排序：
    1. 含闲鱼 Cookie 的 Profile 排在前
    2. 同等条件下 Default 排在前
    3. 其余按 Profile N 数字升序
    """
```

**实现要点**：

* 读取 `Local State` 的 `profile.info_cache` 获取所有 Profile 名称

* 兜底：扫描 `User Data` 下匹配 `Default|Profile \d+` 的目录

* 检测闲鱼 Cookie：用 `immutable=1` 只读打开，查询 `_m_h5_tk` 是否存在（不解密，只看 name）

### 4.2 browser\_import\_cdp.py - CDP 在线导入

```python
@router.post("/import-from-browser/cdp")
def import_via_cdp(port: int = 9222) -> JSONResponse:
    """通过 CDP 协议从运行中的浏览器获取明文 Cookie
    
    前置条件：浏览器以 --remote-debugging-port=9222 启动
    """
    # 1. 检测 CDP 端点是否可达（http://localhost:9222/json/version）
    # 2. 用 Playwright connect_over_cdp 连接
    # 3. 遍历所有 context，获取所有 Cookie
    # 4. 过滤闲鱼域名 Cookie（goofish/taobao/alipay）
    # 5. 调用 cookie_store.export_cookies() 写入
```

**实现要点**：

* 用 `httpx` 先探测 `http://localhost:{port}/json/version`，避免 Playwright 连接超时

* `playwright.sync_api.sync_playwright().chromium.connect_over_cdp(f"http://localhost:{port}")`

* 遍历 `browser.contexts`，对每个 `context.cookies()` 获取明文 Cookie

* 过滤域名：`any(d in cookie['domain'] for d in ('goofish', 'taobao', 'alipay'))`

### 4.3 cookie\_sync\_scheduler.py - 定时同步

```python
class CookieSyncScheduler:
    def __init__(self, cookie_store, config):
        self.interval_minutes = config.auto_sync_interval  # 默认 30
        self.scheduler = AsyncIOScheduler()
    
    async def _sync_job(self):
        """定时任务：检查并同步 Cookie"""
        # 1. 检查当前 Cookie 是否即将过期（< 10 分钟）
        # 2. 若即将过期，触发导入流程
        # 3. 优先尝试离线导入（browser_import）
        # 4. 失败则尝试 CDP 导入（需浏览器以调试端口运行）
        # 5. 都失败则记录日志，等待下次重试
```

**实现要点**：

* 复用项目已有的 `apscheduler`，在 [startup.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/startup.py) 中注册

* 配置项：`browser.auto_sync: bool`、`browser.auto_sync_interval: int`（分钟）

* 失败重试：连续 3 次失败后降低频率（间隔翻倍），避免频繁打扰

* 不自动关闭浏览器（避免打断用户工作）

### 4.4 一键启动脚本

```powershell
# scripts/start_edge_debug.ps1
# 以调试端口启动 Edge，使用独立的 user-data-dir（Chrome 136+ 要求）
$debugProfile = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Debug"
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
    --remote-debugging-port=9222 `
    --user-data-dir="$debugProfile" `
    --remote-allow-origins=* `
    "https://www.goofish.com/"
```

**说明**：使用独立 `Debug` 目录避免与用户日常浏览器冲突，首次需登录闲鱼，之后 Cookie 会持久化。

## 5. 错误处理

### 5.1 错误场景与处理

| 场景                          | 处理方式                             | 用户可见反馈                         |
| --------------------------- | -------------------------------- | ------------------------------ |
| **CDP 端口未启动**               | 检测 `localhost:9222` 不可达          | 提示运行 `start_edge_debug.ps1` 脚本 |
| **CDP 连接被拒**                | Chrome 136+ 未带 `--user-data-dir` | 提示需使用非标准 user-data-dir         |
| **浏览器未登录闲鱼**                | CDP 获取到 Cookie 但无 `_m_h5_tk`     | 提示先在浏览器中登录闲鱼                   |
| **Profile 无闲鱼 Cookie**      | 遍历所有 Profile 都未找到                | 列出已扫描的 Profile，提示登录            |
| **文件锁定且 auto\_close=False** | 降级到 CDP 方案                       | 提示两种选择：关闭浏览器或用 CDP             |
| **定时同步连续失败**                | 降低频率（间隔翻倍，上限 2 小时）               | 日志记录，前端状态显示"同步异常"              |
| **解密异常（v10/v20 混合）**        | 跳过失败的，继续解密其他                     | 返回部分成功 + 错误列表                  |

### 5.2 数据验证机制

```python
# 导入后验证 Cookie 有效性（复用现有 cookie_rotator 的分层逻辑）
# IDENTITY_COOKIES / SESSION_COOKIES 常量从 cookie_rotator.py 导入
def validate_imported_cookies(cookies: list[dict]) -> dict:
    """验证导入的 Cookie 是否满足闲鱼登录要求
    
    identity 层（必须）：unb, cookie2, sgcookie, lg2
    session 层（必须）：_m_h5_tk, _m_h5_tk_enc
    tracking 层（可选）：cna, tfstk 等
    """
    cookie_names = {c['name'] for c in cookies}
    identity_ok = IDENTITY_COOKIES.issubset(cookie_names)
    session_ok = SESSION_COOKIES.issubset(cookie_names)
    return {
        "valid": identity_ok and session_ok,
        "missing_identity": IDENTITY_COOKIES - {c['name'] for c in cookies},
        "missing_session": SESSION_COOKIES - {c['name'] for c in cookies},
    }
```

## 6. 安全措施

| 风险                 | 措施                                 |
| ------------------ | ---------------------------------- |
| **CDP 端口暴露**       | 仅监听 `127.0.0.1`，启动脚本绑定 `localhost` |
| **明文 Cookie 在内存**  | 导入完成后立即清理临时变量，不记录到日志               |
| **调试 Profile 持久化** | 脚本注释提示用户可手动删除 `Debug` 目录           |
| **定时同步打扰**         | 默认关闭，需用户在配置中显式启用 `auto_sync: true` |
| **Web API 未授权访问**  | CDP 端点纳入现有 Bearer Token 中间件保护      |

## 7. 测试设计

### 7.1 单元测试

**`tests/test_browser_import.py`**：

| 测试用例                                 | 覆盖点                       |
| ------------------------------------ | ------------------------- |
| `test_decrypt_dpapi_success`         | DPAPI 解密成功路径              |
| `test_decrypt_aes_gcm_v10`           | v10 AES-256-GCM 解密        |
| `test_decrypt_aes_gcm_v20_detected`  | v20 检测并返回 None（不崩溃）       |
| `test_decrypt_plaintext`             | 明文 Cookie 直接返回            |
| `test_copy_file_with_share_locked`   | 文件锁规避（mock robocopy）      |
| `test_copy_file_with_share_fallback` | robocopy 失败回退 CreateFileW |

**`tests/test_browser_profile.py`**：

| 测试用例                                  | 覆盖点                   |
| ------------------------------------- | --------------------- |
| `test_discover_profiles_default_only` | 只有 Default 目录         |
| `test_discover_profiles_multiple`     | Default + Profile 1/2 |
| `test_discover_profiles_priority`     | 含闲鱼 Cookie 的排在前       |
| `test_discover_profiles_no_xianyu`    | 无闲鱼 Cookie 的 Profile  |

**`tests/test_cookie_sync_scheduler.py`**：

| 测试用例                               | 覆盖点             |
| ---------------------------------- | --------------- |
| `test_sync_job_cookies_valid`      | Cookie 有效时不触发同步 |
| `test_sync_job_cookies_expiring`   | 即将过期时触发同步       |
| `test_sync_job_offline_success`    | 离线导入成功          |
| `test_sync_job_fallback_to_cdp`    | 离线失败降级到 CDP     |
| `test_sync_job_all_failed_backoff` | 全部失败时退避         |

**`tests/test_browser_import_cdp.py`**：

| 测试用例                          | 覆盖点               |
| ----------------------------- | ----------------- |
| `test_cdp_port_not_reachable` | CDP 端口未启动         |
| `test_cdp_connect_success`    | CDP 连接成功获取 Cookie |
| `test_cdp_no_xianyu_cookie`   | 浏览器未登录闲鱼          |
| `test_cdp_filter_domains`     | 域名过滤逻辑            |

### 7.2 集成测试

**`tests/test_browser_import_integration.py`**：

| 测试用例                        | 覆盖点                        |
| --------------------------- | -------------------------- |
| `test_import_v10_e2e`       | v10 加密端到端导入（mock SQLite）   |
| `test_import_cdp_e2e`       | CDP 导入端到端（mock Playwright） |
| `test_import_multi_profile` | 多 Profile 场景               |

### 7.3 测试策略

* 所有外部依赖（SQLite 文件、Playwright、robocopy）通过 `monkeypatch` mock

* 测试不依赖真实浏览器运行

* 测试不写入真实的 `browser-data` 目录，使用 `tmp_path` fixture

## 8. 配置变更

在 `config/config.yaml` 的 `browser` 节点下新增：

```yaml
browser:
  user_data_dir: "./browser-data"
  # 新增：定时自动同步配置
  auto_sync: false                    # 默认关闭，需显式启用
  auto_sync_interval: 30              # 同步间隔（分钟）
  auto_sync_expiry_threshold: 10      # Cookie 剩余有效期阈值（分钟），低于此值触发同步
  cdp_port: 9222                      # CDP 调试端口
```

## 9. 不在本次范围内

以下内容明确不在本次实现范围：

* **跨平台支持**（macOS/Linux）：当前仅支持 Windows，未来可扩展

* **IElevator COM 解密**：方案 B 未被选择，不实现本地 v20 解密

* **浏览器扩展**：不开发浏览器扩展

* **AES 密钥缓存**：每次读取 Local State 的开销可接受，不做缓存

* **内存安全增强**：本地工具场景，不额外加密内存中的 Cookie

## 10. 验收标准

1. **v20 加密支持**：在 Edge v127+ 环境下，通过 CDP 方式能成功获取闲鱼 Cookie
2. **多 Profile 支持**：用户在 `Profile 1` 登录闲鱼时，能自动发现并导入
3. **测试覆盖**：新增模块测试覆盖率 ≥ 80%，所有测试通过
4. **定时同步**：启用 `auto_sync: true` 后，Cookie 过期前 10 分钟自动触发同步
5. **错误处理**：所有错误场景有明确的用户可见反馈
6. **不破坏现有功能**：现有的 v10/DPAPI/明文解密导入流程不受影响

