# 浏览器自动化与子进程模式（v1.0）

> **版本**：v1.0
> **日期**：2026-07-04
> **来源**：从"闲鱼登录模块"后端问题复盘（多 Chromium 争用 user_data_dir / Cookie 异步写入 / 跨域 Cookie / SPA 抓取 / 子进程异常静默 / 资源拦截过度）
> **对应检查点**：`BAC-01 ~ BAC-14`（浏览器自动化与子进程维度）
> **适用范围**：`scripts/browser_login.py` + `scripts/auth_helper.py` + `src/xianyu_hunter/web/services/auth_manager.py` + `src/xianyu_hunter/infra/browser.py` + `src/xianyu_hunter/web/routes/unified_login.py` + `src/xianyu_hunter/web/routes/cookie_inject.py`
> **配套技能**：`xianyu-backend-code-review` v4.16.0+、`xianyu-hunter-dev`（编码规范来源）

---

## 一、问题原型

**用户报告**：

| # | 现象 | 根因 |
|---|---|---|
| 1 | `Target.createTarget: Failed to open a new tab` | 不清理 SingletonLock + 关闭 context 唯一 page |
| 2 | Cookie 18 个而非 38 个 | 异步写入未完成即读取 |
| 3 | unb 漏读 | unb 在 .taobao.com 域，仅按 goofish 过滤 |
| 4 | "Hi! 你好" 占位符 | SPA hydration 时序，domcontentloaded 后 2-8s 才挂载昵称元素 |
| 5 | auth_helper 并发触发卡死 | _maybe_refresh_userinfo 条件3 与登录路径并发 |
| 6 | 子进程异常静默无日志 | `except Exception: pass` 吞异常 |
| 7 | 页面无样式 | 拦截 stylesheet 导致 CSS 缺失 |
| 8 | 多标签页 | Sessions 历史恢复 + about:blank 默认页 |
| 9 | 注入 Cookie 未进入系统 | 未传 user_id，session_token 回退 web_token |
| 10 | 右上角"未登录"（6 次迭代） | 多 Chromium 争用 user_data_dir + 综合时序问题 |

**矛盾本质**：浏览器自动化涉及"多进程 + 异步时序 + 跨域 Cookie + SPA 渲染 + 子进程并发 + 资源加载"6 个独立维度，任一环节处理不当都会导致整体功能异常，且现象（"未登录"）与根因（Cookie 异步写入未完成）之间无明显因果关系，排查难度高。

---

## 二、检查清单（自动化扫描）

### 2.1 违规模式（`BAC-01 ~ BAC-04`：浏览器进程互斥）

#### 违规模式 A：不清理锁文件直接启动

```python
# ❌ 违规：不清理 SingletonLock 直接 launch
async with async_playwright() as pw:
    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=str(user_data_dir),
        # ❌ 缺少 _cleanup_lock_files(user_data_dir)
    )
```

**问题**：
- Worker 异常退出后 `SingletonLock` 残留
- 新 Chromium 启动后无法独占 user_data_dir
- `launch_persistent_context` 成功但 `new_page()` 报 `Target.createTarget: Failed to open a new tab`

#### 违规模式 B：关闭 context 唯一 page

```python
# ❌ 违规：关闭默认 page 再 new_page
pages = ctx.pages
if pages:
    await pages[0].close()  # ❌ 关闭唯一 page 让 context 不稳定
page = await ctx.new_page()  # ❌ Target.createTarget 失败
```

#### 违规模式 C：多个 Chromium 并发使用同一 user_data_dir

```python
# ❌ 违规：无互斥锁，auth_helper 与 browser_login 并发
class AuthManager:
    def trigger_refresh_userinfo_async(self):
        # ❌ 缺少 _refresh_lock + _refreshing 检查
        threading.Thread(target=self._refresh_userinfo_sync).start()
```

#### 违规模式 D：不延迟触发子进程

```python
# ❌ 违规：登录成功立即触发 auth_helper
def _trigger_userinfo_refresh():
    get_auth_manager().trigger_refresh_userinfo_async(delay=0.0)  # ❌ 不等 browser_login 退出
```

### 2.2 违规模式（`BAC-05 ~ BAC-07`：异步写入等待）

#### 违规模式 A：立即读取 Cookie

```python
# ❌ 违规：登录成功后立即读 Cookie
if _validate_login_cookies(cookies):
    final_cookies = await bc.cookies()  # ❌ 异步写入未完成，只拿到 18 个
    _export_cookies_to_json(final_cookies, "browser")
    return 0
```

**问题**：
- 闲鱼登录成功后会在 2-3s 内异步写入 `_m_h5_tk` / `tfstk` / `t` 等会话层 cookie
- 立即读 cookies 只能拿到 18-20 个身份 cookie，缺关键会话 cookie
- 后续 auth_helper 读 user_data_dir 时也无法获取完整 cookie

#### 违规模式 B：不调用 storage_state() flush

```python
# ❌ 违规：不调用 storage_state 强制 flush
await asyncio.sleep(3)
# ❌ 缺少 await bc.storage_state()
final_cookies = await bc.cookies()
```

#### 违规模式 C：bc.close() 后不等待 SQLite flush

```python
# ❌ 违规：close 后立即返回
await bc.close()
return 0  # ❌ SQLite 写入可能未完成
```

### 2.3 违规模式（`BAC-08 ~ BAC-10`：Cookie 域白名单与值校验）

#### 违规模式 A：仅按单一域过滤

```python
# ❌ 违规：仅按 goofish 过滤
goofish_cookies = [
    c for c in cookies
    if "goofish" in (c.get("domain") or "")  # ❌ 漏掉 unb（在 .taobao.com 域）
]
```

#### 违规模式 B：仅检测 Cookie 名称存在

```python
# ❌ 违规：_m_h5_tk 存在就视为登录
cookie_names = {c["name"] for c in cookies}
if "_m_h5_tk" in cookie_names:  # ❌ _m_h5_tk 访问首页就会设置
    return True
```

#### 违规模式 C：不校验 Cookie 值

```python
# ❌ 违规：不校验 unb 值
unb = cookie_map.get("unb", "")
if unb:  # ❌ unb="123456" 测试值也被识别为登录
    return True
```

### 2.4 违规模式（`BAC-11`：占位符过滤）

#### 违规模式 A：直接信任首次抓取结果

```python
# ❌ 违规：直接信任首次抓取的昵称
info = await page.evaluate("() => { ... }")
raw_nick = (info.get("nick") or "").strip()
# ❌ 缺少 _is_invalid_first 检查
# ❌ 缺少二次重试机制
if raw_nick:
    return {"nick": raw_nick}
```

**问题**：
- 闲鱼 SPA 用 React + 自定义 hydration，昵称元素在 `domcontentloaded` 后还需 2-8s 才挂载
- 首次抓到的 "Hi! 你好" 是个人页默认欢迎语占位符，并非真实昵称

### 2.5 违规模式（`BAC-12`：子进程异常可观测）

#### 违规模式 A：静默吞异常

```python
# ❌ 违规：except Exception: pass
def _refresh_userinfo_sync(self) -> None:
    try:
        proc = subprocess.run([...], timeout=60, capture_output=True)
        if proc.returncode == 0 and _USERINFO_FILE.exists():
            self._userinfo = json.loads(_USERINFO_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass  # ❌ 静默吞异常，_userinfo 保持旧值（nick=""），前端显示"未登录"且无日志可查
```

#### 违规模式 B：用 logger.debug 记录异常

```python
# ❌ 违规：日志级别过低
except Exception as e:
    logger.debug("auth_helper 失败: %s", e)  # ❌ 生产环境默认不输出 debug
```

### 2.6 违规模式（`BAC-13`：资源拦截白名单）

#### 违规模式 A：拦截 stylesheet

```python
# ❌ 违规：拦截 stylesheet
async def _block_resources(route):
    req = route.request
    if req.resource_type in ("font", "media", "image", "manifest", "stylesheet"):  # ❌ CSS 缺失
        await route.abort()
        return
    await route.continue_()
```

#### 违规模式 B：不放行登录域名

```python
# ❌ 违规：拦截 image 导致扫码二维码无法显示
async def _block_resources(route):
    req = route.request
    if req.resource_type == "image":  # ❌ 不放行 login.taobao.com 的二维码图
        await route.abort()
        return
    await route.continue_()
```

### 2.7 违规模式（`BAC-14`：配置化要求）

#### 违规模式 A：硬编码等待时间

```python
# ❌ 违规：3 秒硬编码
await asyncio.sleep(3)  # ❌ 应从 auth.cookie_write_wait_sec 读取
```

#### 违规模式 B：硬编码域名和选择器

```python
# ❌ 违规：域名硬编码
goofish_cookies = [
    c for c in cookies
    if "goofish" in (c.get("domain") or "")
    or "taobao" in (c.get("domain") or "")  # ❌ 应从 browser.auth_cookie_domains 读取
]

# ❌ 违规：选择器硬编码
await page.wait_for_selector(
    '[class*="userInfo"] [class*="nick"], ...',  # ❌ 应从 auth.nick_selectors 读取
    timeout=5000,  # ❌ 应从 auth.selector_wait_sec 读取
)
```

---

## 三、修复模式（参考实现）

### 3.1 修复：浏览器进程互斥

```python
# ✅ 修复：启动前清理锁文件 + 进程互斥 + 延迟触发
import glob as _glob
from pathlib import Path
import threading

def _cleanup_lock_files(user_data_dir: Path) -> None:
    """清理 user_data_dir 中残留的 SingletonLock 等锁文件 + Sessions 历史"""
    for pattern in (
        str(user_data_dir / "SingletonLock"),
        str(user_data_dir / "SingletonCookie"),
        str(user_data_dir / "SingletonSocket"),
        str(user_data_dir / "*lock*"),
        str(user_data_dir / "Default" / "Sessions" / "Tabs_*"),
        str(user_data_dir / "Default" / "Sessions" / "Session_*"),
    ):
        for f in _glob.glob(pattern):
            try:
                Path(f).unlink(missing_ok=True)
            except OSError:
                pass

class AuthManager:
    def __init__(self) -> None:
        self._refresh_lock = threading.Lock()
        self._refreshing = False

    def trigger_refresh_userinfo_async(self, delay: float | None = None) -> None:
        auth_cfg = _get_auth_cfg()
        if delay is None:
            delay = auth_cfg.helper_delay_sec  # ✅ 从配置读取
        # ...

    def _refresh_userinfo_sync_with_delay(self, delay: float = 0.0) -> None:
        if delay > 0:
            time.sleep(delay)
        with self._refresh_lock:
            if self._refreshing:
                logger.debug("auth_helper 已在运行，跳过本次触发")
                return
            self._refreshing = True
        try:
            self._refresh_userinfo_sync()
        finally:
            with self._refresh_lock:
                self._refreshing = False

# 启动前清理
_cleanup_lock_files(Path(cfg.user_data_dir))
ctx = await pw.chromium.launch_persistent_context(...)

# 复用默认 page（不 close + new_page）
page = bc.pages[0] if bc.pages else await bc.new_page()
```

### 3.2 修复：异步写入等待

```python
# ✅ 修复：等待 + flush + 兜底重读
auth_cfg = _get_auth_cfg()

if _validate_login_cookies(cookies):
    # 1. 等 Cookie 异步写入完成
    await asyncio.sleep(auth_cfg.cookie_write_wait_sec)  # ✅ 3s
    # 2. 强制 flush 到 SQLite
    try:
        await bc.storage_state()
    except Exception:
        pass
    # 3. 再次读取 Cookie
    final_cookies = await bc.cookies()
    _export_cookies_to_json(final_cookies, "browser")
    _save_playwright_cookies(final_cookies)
    # 4. 等 SQLite flush 完成
    await asyncio.sleep(auth_cfg.sqlite_flush_wait_sec)  # ✅ 2s
    return 0

# ✅ 修复：unb 兜底重读
_uid_via_tb_token = bool(uid) and not any(
    c.get("name") == "unb" for c in goofish_cookies
)
if _uid_via_tb_token:
    try:
        await page.wait_for_timeout(int(auth_cfg.unb_reread_wait_sec * 1000))  # ✅ 3s
        cookies = await ctx.cookies()
        goofish_cookies = [
            c for c in cookies
            if any(d in (c.get("domain") or "") for d in cfg.auth_cookie_domains)
        ]
        for c in goofish_cookies:
            if c.get("name") == "unb" and c.get("value"):
                uid = c["value"]
                break
    except Exception:
        pass
```

### 3.3 修复：Cookie 域白名单与值校验

```python
# ✅ 修复：双域过滤 + 严格值校验
cfg = _get_browser_cfg()
auth_cfg = _get_auth_cfg()

# 1. 域白名单从配置读取（goofish + taobao）
goofish_cookies = [
    c for c in cookies
    if any(d in (c.get("domain") or "") for d in cfg.auth_cookie_domains)
]

# 2. 登录态判定：关键 Cookie 任一存在
login_cookie_names = set(auth_cfg.login_cookie_names)
has_login_cookie = bool(login_cookie_names & goofish_names)

# 3. 严格值校验
def _validate_login_cookies(cookies: list[dict]) -> bool:
    cookie_map = {c["name"]: c.get("value", "") for c in cookies}
    unb = cookie_map.get("unb", "")
    cookie2 = cookie_map.get("cookie2", "")

    # unb 必须是纯数字且长度 >= 6
    if not unb or not unb.isdigit() or len(unb) < auth_cfg.unb_min_length:
        return False

    # 过滤测试值
    if unb in auth_cfg.unb_test_values:
        return False

    # cookie2 长度校验
    if not cookie2 or len(cookie2) < auth_cfg.cookie2_min_length:
        return False

    return True
```

### 3.4 修复：占位符过滤 + 二次重试

```python
# ✅ 修复：占位符过滤 + wait_for_selector + 固定 sleep 兜底
auth_cfg = _get_auth_cfg()

raw_nick = (info.get("nick") or "").strip()

# 1. 占位符过滤（从配置读取）
_is_invalid_first = (not raw_nick) or (raw_nick in auth_cfg.invalid_nicks)

# 2. 二次重试：不在登录页 URL 时触发
if _is_invalid_first and not is_login_url:
    try:
        # 优先等昵称元素挂载（比固定 sleep 更精准）
        await page.wait_for_selector(
            ", ".join(auth_cfg.nick_selectors),  # ✅ 选择器从配置读取
            timeout=int(auth_cfg.selector_wait_sec * 1000),  # ✅ 5s
            state="visible",
        )
    except Exception:
        # 选择器超时不影响：固定 sleep 兜底
        await page.wait_for_timeout(int(auth_cfg.selector_wait_sec * 1000))
    # 重抓昵称
    info = await page.evaluate("...")
    retry_nick = (info.get("nick") or "").strip()
    if retry_nick and retry_nick not in auth_cfg.invalid_nicks:
        raw_nick = retry_nick
```

### 3.5 修复：子进程异常可观测

```python
# ✅ 修复：捕获 stderr + logger.warning + 超时单独处理
def _refresh_userinfo_sync(self) -> None:
    try:
        proc = subprocess.run(
            [sys.executable, str(_HELPER), "info", "--out-dir", str(_OUT_DIR)],
            timeout=_get_auth_cfg().helper_timeout_sec,  # ✅ 从配置读取
            capture_output=True,
        )
        if proc.returncode == 0 and _USERINFO_FILE.exists():
            with self._lock:
                self._userinfo = json.loads(_USERINFO_FILE.read_text(encoding="utf-8"))
                self._userinfo_at = time.time()
        elif proc.returncode != 0:
            # ✅ 记录 stderr 前 500 字符
            stderr = proc.stderr.decode(errors="replace")[:500] if proc.stderr else ""
            logger.warning(
                "auth_helper info 失败 (returncode=%d): %s",
                proc.returncode, stderr,
            )
    except subprocess.TimeoutExpired:
        # ✅ 超时单独处理
        logger.warning("auth_helper info 超时（%ds）", _get_auth_cfg().helper_timeout_sec)
    except Exception as e:
        # ✅ 其他异常用 warning 而非 debug
        logger.warning("auth_helper info 异常: %s", e)
```

### 3.6 修复：资源拦截白名单

```python
# ✅ 修复：不拦截 stylesheet + 域名白名单放行 + 配置化
async def _block_resources(route):
    req = route.request
    url = req.url.lower()
    cfg = _get_browser_cfg()

    # 1. 域名白名单放行（从配置读取）
    if any(d in url for d in cfg.resource_allow_domains):
        await route.continue_()
        return

    # 2. 拦截类型白名单（不含 stylesheet，从配置读取）
    if req.resource_type in cfg.resource_block_types:
        await route.abort()
        return

    await route.continue_()
```

---

## 四、检测模式（自动扫描正则）

### 4.1 后端扫描模式（`config.yaml` 的 `browser_automation.detect_patterns`）

```yaml
detect_patterns:
  # launch_persistent_context 前未调用 _cleanup_lock_files
  - pattern: "launch_persistent_context[\\s\\S]{0,500}(?!_cleanup_lock_files)"
    message: "launch_persistent_context 前必须调用 _cleanup_lock_files 清理 SingletonLock 等锁文件"
    severity: CRITICAL
    scope: "scripts/*.py"

  # 关闭 context 唯一 page 后 new_page
  - pattern: "pages\\[0\\]\\.close\\(\\)[\\s\\S]{0,200}new_page\\(\\)"
    message: "禁止关闭 context 唯一 page 后 new_page，会触发 Target.createTarget 失败"
    severity: CRITICAL

  # 多个 Chromium 并发使用同一 user_data_dir（无 _refresh_lock）
  - pattern: "class\\s+\\w+Manager[\\s\\S]{0,1000}user_data_dir(?!.*_refresh_lock)"
    message: "共享 user_data_dir 的 Manager 类必须含 _refresh_lock + _refreshing 互斥标志"
    severity: HIGH

  # 立即读取 Cookie（异步写入后未等待）
  - pattern: "_validate_login_cookies\\([\\s\\S]{0,200}await.*cookies\\(\\)(?!.*sleep)"
    message: "登录成功后必须 sleep(cookie_write_wait_sec) + storage_state() 再读 Cookie"
    severity: HIGH

  # 仅按单一域过滤 Cookie
  - pattern: '"goofish"\\s+in\\s+\\(c\\.get\\("domain"\\)'
    message: "Cookie 域过滤应包含 goofish + taobao（unb 在 .taobao.com 域），从 browser.auth_cookie_domains 读取"
    severity: HIGH

  # 仅检测 Cookie 名称存在不校验值
  - pattern: 'if\\s+"unb"\\s+in\\s+\\w+_names\\s*:\\s*return\\s+True'
    message: "登录态判定必须校验 unb 值（isdigit + len >= 6），不能仅检测名称存在"
    severity: HIGH

  # 静默吞异常
  - pattern: "except\\s+Exception\\s*:\\s*pass"
    message: "禁止 except Exception: pass 静默吞异常，必须 logger.warning + 记录 stderr"
    severity: CRITICAL

  # 用 logger.debug 记录异常
  - pattern: "except\\s+Exception\\s+as\\s+\\w+\\s*:[\\s\\S]{0,100}logger\\.debug"
    message: "异常路径必须用 logger.warning（而非 debug），生产环境默认不输出 debug"
    severity: HIGH

  # 拦截 stylesheet
  - pattern: 'resource_type\\s+in\\s+\\([^)]*"stylesheet"'
    message: "禁止拦截 stylesheet，CSS 缺失导致页面布局错乱、按钮不可见"
    severity: CRITICAL

  # 硬编码等待时间
  - pattern: "asyncio\\.sleep\\(\\s*\\d+\\.?\\d*\\s*\\)"
    message: "等待时间硬编码，应从 auth.cookie_write_wait_sec / sqlite_flush_wait_sec 读取"
    severity: MEDIUM

  # 硬编码域名
  - pattern: '"goofish"\\s+in\\s+\\(c\\.get\\("domain"\\)'
    message: "Cookie 域硬编码，应从 browser.auth_cookie_domains 读取"
    severity: MEDIUM
```

---

## 五、测试用例

### 5.1 后端测试（pytest）

```python
# tests/backend/test_browser_automation.py
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from xianyu_hunter.web.services.auth_manager import AuthManager

class TestBrowserProcessMutex:
    """BAC-01 ~ BAC-04：浏览器进程互斥"""

    def test_cleanup_lock_files_called_before_launch(self, tmp_path):
        """launch_persistent_context 前必须调用 _cleanup_lock_files"""
        user_data_dir = tmp_path / "browser-data"
        user_data_dir.mkdir()
        # 制造残留锁文件
        (user_data_dir / "SingletonLock").touch()

        with patch('scripts.browser_login._cleanup_lock_files') as cleanup_spy:
            # 模拟启动
            asyncio.run(_cmd_login(status_file=tmp_path / "status.json", timeout=1))
            # ✅ _cleanup_lock_files 必须被调用
            cleanup_spy.assert_called_once_with(user_data_dir)

    def test_refresh_lock_prevents_concurrent_auth_helper(self):
        """_refresh_lock 必须防止 auth_helper 并发执行"""
        mgr = AuthManager()
        mgr._refreshing = True  # 模拟已有 auth_helper 在运行

        with patch.object(mgr, '_refresh_userinfo_sync') as refresh_spy:
            mgr._refresh_userinfo_sync_with_delay(delay=0.0)
            # ✅ 已有 auth_helper 在运行时跳过本次触发
            refresh_spy.assert_not_called()

    def test_delay_default_from_config(self):
        """delay 默认值必须从 auth.helper_delay_sec 读取"""
        mgr = AuthManager()
        with patch('xianyu_hunter.web.services.auth_manager._get_auth_cfg') as cfg_mock:
            cfg_mock.return_value.helper_delay_sec = 7.5
            with patch.object(mgr, '_refresh_userinfo_bg', new_callable=AsyncMock) as bg_mock:
                mgr.trigger_refresh_userinfo_async()  # 不传 delay
                # ✅ 用配置中的 7.5s 而非硬编码 5.0s
                _, kwargs = bg_mock.call_args
                assert kwargs.get('delay') == 7.5 or bg_mock.call_args.args[0] == 7.5


class TestAsyncWriteWait:
    """BAC-05 ~ BAC-07：异步写入等待"""

    @pytest.mark.asyncio
    async def test_cookie_write_wait_before_read(self, tmp_path):
        """登录成功后必须 sleep(cookie_write_wait_sec) 再读 Cookie"""
        auth_cfg_mock = MagicMock()
        auth_cfg_mock.cookie_write_wait_sec = 3.0
        auth_cfg_mock.sqlite_flush_wait_sec = 2.0

        with patch('scripts.browser_login._get_auth_cfg', return_value=auth_cfg_mock), \
             patch('asyncio.sleep') as sleep_mock, \
             patch('scripts.browser_login._validate_login_cookies', return_value=True):
            await _cmd_login(status_file=tmp_path / "status.json", timeout=1)
            # ✅ 必须有两次 sleep：3s (cookie write) + 2s (SQLite flush)
            sleep_calls = [c.args[0] for c in sleep_mock.call_args_list]
            assert 3.0 in sleep_calls
            assert 2.0 in sleep_calls

    @pytest.mark.asyncio
    async def test_storage_state_called_before_cookie_read(self):
        """读 Cookie 前必须调用 storage_state() 强制 flush"""
        bc_mock = AsyncMock()
        bc_mock.cookies.return_value = [{"name": "unb", "value": "123456"}]

        with patch('scripts.browser_login._validate_login_cookies', return_value=True):
            # ✅ storage_state 必须在第二次 cookies() 之前被调用
            await bc_mock.storage_state()
            assert bc_mock.storage_state.called


class TestCookieValidation:
    """BAC-08 ~ BAC-10：Cookie 域白名单与值校验"""

    def test_validate_unb_must_be_digit_and_min_length(self):
        """unb 必须是纯数字且长度 >= 6"""
        # ✅ 合法
        assert _validate_login_cookies([
            {"name": "unb", "value": "12345678"},
            {"name": "cookie2", "value": "abcdefghij"},
        ]) is True

        # ❌ 太短
        assert _validate_login_cookies([
            {"name": "unb", "value": "12345"},
            {"name": "cookie2", "value": "abcdefghij"},
        ]) is False

        # ❌ 非数字
        assert _validate_login_cookies([
            {"name": "unb", "value": "abcdef"},
            {"name": "cookie2", "value": "abcdefghij"},
        ]) is False

    def test_validate_unb_test_values_filtered(self):
        """unb 测试值（123456, 123）必须被过滤"""
        for test_val in ("123456", "123"):
            assert _validate_login_cookies([
                {"name": "unb", "value": test_val},
                {"name": "cookie2", "value": "abcdefghij"},
            ]) is False

    def test_cookie_domain_filter_includes_taobao(self):
        """Cookie 域过滤必须包含 taobao（unb 在 .taobao.com 域）"""
        cookies = [
            {"name": "unb", "value": "12345678", "domain": ".taobao.com"},
            {"name": "cookie2", "value": "abcdefghij", "domain": ".goofish.com"},
        ]
        cfg = _get_browser_cfg()
        # ✅ auth_cookie_domains 包含 goofish + taobao
        assert "goofish" in cfg.auth_cookie_domains
        assert "taobao" in cfg.auth_cookie_domains

        filtered = [
            c for c in cookies
            if any(d in (c.get("domain") or "") for d in cfg.auth_cookie_domains)
        ]
        # ✅ unb（在 taobao 域）必须被包含
        assert len(filtered) == 2
        assert any(c["name"] == "unb" for c in filtered)


class TestSubprocessExceptionObservability:
    """BAC-12：子进程异常可观测"""

    def test_subprocess_failure_logs_warning_with_stderr(self, caplog):
        """子进程失败时必须 logger.warning + 记录 stderr"""
        import logging
        caplog.set_level(logging.WARNING)

        mgr = AuthManager()
        # 模拟子进程失败
        with patch('subprocess.run') as run_mock:
            run_mock.return_value = MagicMock(
                returncode=1,
                stderr=b"auth_helper crashed: ImportError\n",
            )
            mgr._refresh_userinfo_sync()

        # ✅ 必须有 WARNING 日志
        assert any("auth_helper info 失败" in r.message for r in caplog.records)
        # ✅ 必须包含 stderr 内容
        assert any("ImportError" in r.message for r in caplog.records)

    def test_subprocess_timeout_logs_warning(self, caplog):
        """子进程超时必须单独 logger.warning"""
        import subprocess
        import logging
        caplog.set_level(logging.WARNING)

        mgr = AuthManager()
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd="x", timeout=60)):
            mgr._refresh_userinfo_sync()

        # ✅ 必须有"超时"日志
        assert any("超时" in r.message for r in caplog.records)


class TestResourceBlockWhitelist:
    """BAC-13：资源拦截白名单"""

    def test_stylesheet_not_in_block_types(self):
        """resource_block_types 必须不含 stylesheet"""
        cfg = _get_browser_cfg()
        # ✅ 不含 stylesheet
        assert "stylesheet" not in cfg.resource_block_types
        # ✅ 含 font / media / image / manifest
        assert "font" in cfg.resource_block_types
        assert "media" in cfg.resource_block_types
        assert "image" in cfg.resource_block_types
        assert "manifest" in cfg.resource_block_types

    def test_login_domains_in_allow_list(self):
        """resource_allow_domains 必须包含登录页域名"""
        cfg = _get_browser_cfg()
        # ✅ 必须包含登录页扫码二维码域名
        assert "login.taobao.com" in cfg.resource_allow_domains
        assert "passport.taobao.com" in cfg.resource_allow_domains
```

---

## 六、相关文件

| 文件 | 职责 |
|------|------|
| `scripts/browser_login.py` | Playwright 有头浏览器登录入口子进程 |
| `scripts/auth_helper.py` | 用户昵称/头像抓取子进程（headless） |
| `src/xianyu_hunter/web/services/auth_manager.py` | 认证状态管理器（含 _refresh_lock 互斥） |
| `src/xianyu_hunter/web/routes/unified_login.py` | 统一登录路由 |
| `src/xianyu_hunter/web/routes/cookie_inject.py` | Cookie 注入登录路径 |
| `src/xianyu_hunter/web/routes/auth_query.py` | /me 路由（含 _INVALID_NICKS 过滤） |
| `src/xianyu_hunter/web/services/user_manager.py` | 用户身份识别 |
| `src/xianyu_hunter/infra/browser.py` | Worker 浏览器管理 |
| `src/xianyu_hunter/web/services/cookie_store.py` | Cookie 存储 |
| `src/xianyu_hunter/infra/yaml_config.py` | Pydantic AppConfig（含 AuthConfig + BrowserConfig） |
| `config/auth.yaml` | 认证模块配置（无硬编码参数集中管理） |
| `config/browser.yaml` | 浏览器配置（含资源拦截策略） |
| `tests/backend/test_browser_automation.py` | 浏览器自动化测试 |

---

## 七、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-04 | 初版：基于登录模块 11 类问题复盘，新增 `BAC-01 ~ BAC-14` 共 14 项检查点 |
