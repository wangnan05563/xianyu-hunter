# 多用户 Cookie 隔离编码规范

> 对应 meta-rules #72-#78 / B-REVIEW-209~217 / F-REVIEW-178~181。
> 本规范从 2026-07-06 实时搜索 FAIL_SYS_ILLEGAL_ACCESS 问题中提取，解决多用户 Cookie 隔离后 user_id 传播断裂导致的搜索 API 非法请求。

## 核心规则

### R1: CookieStore 所有方法必须接受 user_id 参数

`python
# 正确
def _read_json(self, user_id: str = "default") -> dict | None:
def export_cookies(self, cookies, method="unknown", user_id: str = "default"):
def update_cookie_values(self, updates, user_id: str = "default"):
def has_valid_cookies(self, user_id: str = "default"):
def invalidate_cache(self, user_id: str | None = None):
`

`python
# 错误 - 缺少 user_id 参数
def _read_json(self) -> dict | None:  # 硬编码默认用户
    data = self._cache.get("default")
`

**判断信号**: grep "def.*cookie.*self" src/ | grep -v "user_id"

### R2: 实时搜索入口必须透传 user_id

`python
# 正确 - 完整传播链
async def live_links(..., request: Request, ...):
    user_id = getattr(request.state, "user_id", "default")
    return StreamingResponse(
        _live_event_stream(..., user_id=user_id, ...),
    )

async def _live_event_stream(..., user_id: str | None, ...):
    cookie_error = await _check_live_cookies_safely(
        container, task_id, inflight_event, user_id=user_id
    )

async def _check_live_cookies_safely(..., user_id: str | None = None):
    await _ensure_live_search_cookies(container, user_id=user_id or "default")

async def _ensure_live_search_cookies(container, user_id: str = "default"):
    pw_cookies, _ = _load_pw_cookies_from_json(user_id)

def _load_pw_cookies_from_json(user_id: str = "default"):
    store.invalidate_cache(user_id)
    json_data = store._read_json(user_id)
`

`python
# 错误 - user_id 在传播链中丢失
async def _check_live_cookies_safely(container, task_id, inflight_event):
    await _ensure_live_search_cookies(container)  # 无 user_id
`

**判断信号**: grep "_ensure_live_search_cookies(container)$"

### R3: 跨进程写入后必须清除缓存

`python
# 浏览器登录子进程写入 JSON 后
store.invalidate_cache(user_id)  # 清除主进程缓存
sync_cookie_layers_from_json()   # 同步层状态
`

**判断信号**: grep "sync_cookie_layers_from_json" | grep -v "invalidate_cache"

### R4: Cookie 注入后必须验证浏览器状态

`python
success = await container.browser.add_cookies(pw_cookies)
if success:
    # 验证浏览器实际持有注入的 cookie
    browser_cookies = await container.browser.get_cookies()
    by_name = {c["name"]: c["value"] for c in browser_cookies}
    for name in _LIVE_SEARCH_IDENTITY_COOKIES:
        if name not in by_name:
            logger.warning("Cookie 注入后验证失败: 缺少 %s", name)
            success = False
`

**判断信号**: grep "add_cookies" | grep -v "get_cookies\|verify\|validate"

### R5: _m_h5_tk 回写必须指定 user_id

`python
# 正确
get_cookie_store().update_cookie_values(updates, user_id=current_user_id)

# 错误 - 写入默认用户
get_cookie_store().update_cookie_values(updates)
`

**判断信号**: grep "update_cookie_values(updates)$"

### R6: 测试 Cookie 必须在注入前过滤

`python
def _load_pw_cookies_from_json(user_id: str = "default"):
    store.invalidate_cache(user_id)
    json_data = store._read_json(user_id)
    if not json_data or not json_data.get("cookies"):
        return [], {}
    
    pw_cookies = []
    for c in json_data["cookies"]:
        name = str(c.get("name") or "")
        value = str(c.get("value") or "")
        if is_test_cookie(name, value):
            logger.warning("跳过测试 Cookie %s=%s...", name, value[:8])
            continue
        pw_cookies.append(_build_pw_cookie_item(name, value, c))
    return pw_cookies, {}
`

**判断信号**: grep "is_test_cookie" | wc -l 应该 >= 2（定义处 + 使用处）

### R7: user_id 用于文件路径前必须校验

`python
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

def _cookie_json_path(user_id: str = "default") -> Path:
    if not _USER_ID_RE.match(user_id):
        raise ValueError(f"invalid user_id: {user_id!r}")
    return Path(_COOKIE_JSON_DIR, f"cookies_{user_id}.json")
`

**判断信号**: grep 'f"cookies_{' src/ 应该配合 _USER_ID_RE.match

## 适用场景
- 多用户 Cookie 隔离后的所有后端代码路径
- 实时搜索、官方采集、自动购买等依赖 Cookie 的功能
- Cookie 层状态同步（/cookies/layers 端点）

## 不适用场景
- 单用户模式部署
- 一次性 Cookie 导入（无实时搜索需求）
- 仅读取 Cookie 用于状态展示（不注入浏览器）
