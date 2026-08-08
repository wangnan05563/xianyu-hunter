# 页面遍历测试

本文档描述全面测试模式步骤 2（浏览器初始化）和步骤 3（页面遍历）的详细操作。

## 浏览器初始化

### 1. 设置设备预设

根据 `config.yaml` 的 `browser_automation.tool_type` 选择工具：

#### playwright_mcp 模式

调用 `playwright_resize`，参数从 `browser_automation.playwright_mcp` 读取：
- `width`: `<viewport_width>`
- `height`: `<viewport_height>`
- `mobile`: `<is_mobile>`
- `touch`: `<has_touch>`
- `deviceScaleFactor`: `<device_scale_factor>`

**已知限制**：`playwright_resize` 不会修改 `navigator.userAgent`。移动端跳转依赖视口兜底（宽度 ≤ `mobile_detect.viewport_max_width`）。

#### browser_use 模式

通过 Task subagent 启动浏览器，`subagent_type` 从 `browser_automation.subagent_type` 读取。

### 2. 导航到入口 URL

构造 URL：`http://{web_process.host}:{web_process.port}/`

调用 `playwright_navigate` 导航。

### 3. 设置认证

根据 `config.yaml` 的 `auth.type`：

#### cookie 模式

1. 从 `auth.env_file_path` 读取文件内容（路径相对 `project.root_dir`）
2. 解析出 `auth.env_file_key` 对应的值
3. 通过 `playwright_evaluate` 执行：

```javascript
(function(){
  document.cookie = '{cookie_name}={token}; path={cookie_path}; max-age={cookie_max_age}';
  return 'cookie set';
})()
```

参数替换：
- `{cookie_name}` ← `auth.cookie_name`
- `{token}` ← 从 .env 读取的值
- `{cookie_path}` ← `auth.cookie_path`
- `{cookie_max_age}` ← `auth.cookie_max_age`

#### header 模式

在 `playwright_navigate` 或 `playwright_get/post` 等请求中添加 header：
- header name: `auth.header_name`
- header value: `auth.header_prefix` + token

#### none 模式

跳过认证步骤。

### 4. 隐藏登录引导浮层

通过 `playwright_evaluate` 执行：

```javascript
(function(){
  var c = document.querySelector('{test_execution.login_overlay_selector}');
  if (c) c.style.display = 'none';
  return 'done';
})()
```

`{test_execution.login_overlay_selector}` 从 config 读取。

### 5. 验证移动端跳转

1. 导航到 `http://{host}:{port}/`
2. 等待 2-3 秒
3. 通过 `playwright_evaluate` 检查 `window.location.pathname`
4. 验证是否等于 `spa.mobile_home_path`

---

## 页面遍历

### 1. 获取页面路由列表

根据 `routes_discovery.source`：

#### manual 模式

从 `routes_discovery.manual_routes` 读取，每个条目包含：
- `path`：路由路径（如 `/m/tasks/`）
- `name`：页面名称（如"任务"）
- `expected_content`：预期内容关键词（如"任务"）

#### auto_from_file 模式

1. Read `routes_discovery.routes_file`（路径相对 `project.frontend_dir`）
2. 解析 `<Route path="...">` 中的路径
3. 拼接 `spa.mobile_route_prefix` 前缀

### 2. 逐页导航测试

对每个路由执行以下操作：

#### 导航

构造完整 URL：`http://{host}:{port}{spa.basename}{route.path}`

调用 `playwright_navigate` 导航。

#### 等待页面加载

根据 `test_execution.page_traversal.wait_strategy`：

**poll 模式**（推荐）：

通过 `playwright_evaluate` 轮询检查 DOM 内容长度：

```javascript
(function(){
  return new Promise(function(resolve){
    var retries = 0;
    var maxRetries = {poll_max_retries};
    var interval = {poll_interval_ms};
    function check() {
      var content = document.querySelector('{content_container_selector}');
      var len = content ? content.innerHTML.length : 0;
      if (len >= {content_min_length} || retries >= maxRetries) {
        resolve(JSON.stringify({contentLength: len, retries: retries}));
      } else {
        retries++;
        setTimeout(check, interval);
      }
    }
    check();
  });
})()
```

参数从 `test_execution.page_traversal` 和 `test_execution.content_container_selector` 读取。

**fixed_wait 模式**：

通过 `playwright_evaluate` 执行 `setTimeout` 等待固定时间。

#### 异步加载页面处理

对 `test_execution.page_traversal.async_load_pages` 中的页面：
- 增加 `poll_max_retries` 到 2 倍
- 或在导航后额外等待 2-3 秒再开始轮询

#### 检查项

每个页面检查以下内容：

1. **URL 验证**：`window.location.pathname` 是否等于预期路径
2. **Console 错误**：调用 `playwright_console_logs`，检查是否有 `[error]` 级别日志
3. **内容非空**：`content_container_selector` 的 innerHTML 长度 ≥ `content_min_length`
4. **预期内容关键词**：通过 `playwright_get_visible_text` 或 `playwright_evaluate` 检查页面文本是否包含 `route.expected_content`

#### 动态路由处理

根据 `test_execution.dynamic_routes.strategy`：

- **skip**：跳过路径中含 `:id` 的路由，记录为"跳过"
- **mock_id**：将 `:id` 替换为 `mock_ids` 中对应的值

### 3. 记录结果

每个页面记录：

| # | 路径 | 页面名称 | 状态 | 关键内容 | Console Errors | 备注 |
|---|------|---------|------|---------|----------------|------|
| 1 | /m/ | 仪表盘 | PASS | 统计卡片 | 无 | |
| 2 | /m/tasks/ | 任务 | PASS | 暂无任务 | 无 | |
| ... | ... | ... | ... | ... | ... | ... |

状态取值：PASS / FAIL / SKIP
