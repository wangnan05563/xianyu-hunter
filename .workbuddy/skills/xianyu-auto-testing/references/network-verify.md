# B. 网络层验证

> 对应决策节点：DT-03（后端响应异常）

## 检查项

### B1. 后端响应链

读取 `config.yaml` 的 `web_process.host` 和 `web_process.port`，以及 `spa.*` 路径配置。

**重要陷阱**：PowerShell 中 `curl` 是 `Invoke-WebRequest` 的别名，`-s` 被解释为 `-SessionVariable`。**必须用 `curl.exe`** 显式调用真正的 curl。

```powershell
# 1. 根路径（期望 302 重定向到 SPA 路径）
curl.exe -s -o NUL -w "HTTP %{http_code} | redirect=%{redirect_url}`n" http://<host>:<port>/

# 2. SPA 首页（期望 200，HTML 内容）
curl.exe -s -o NUL -w "HTTP %{http_code} | size=%{size_download}`n" http://<host>:<port><desktop_home_path>

# 3. 移动端首页（期望 200，HTML 内容）
curl.exe -s -o NUL -w "HTTP %{http_code} | size=%{size_download}`n" http://<host>:<port><mobile_home_path>
```

### B2. 判断标准

读取 `config.yaml` 的 `build.expected_html_size_range` 和 `spa.*` 配置：

| 路径 | 期望状态码 | 期望内容 | 失败含义 |
|------|-----------|---------|---------|
| `/` | 302 | redirect_url 指向 `root_redirect_to` | 后端根路由未注册或异常 |
| `desktop_home_path` | 200 | HTML size 在 `expected_html_size_range` 内 | SPA catch-all 未生效 |
| `mobile_home_path` | 200 | HTML size 在 `expected_html_size_range` 内 | SPA catch-all 未生效 |

**HTML 大小判断**：
- `< expected_html_size_range.min`：通常是错误页或空响应
- `> expected_html_size_range.max`：可能注入了登录引导浮层（正常但需注意）
- 在范围内：正常

### B3. SPA index.html 内容检查

读取 `build_output_dir/index.html`，确认：
- `<script>` 标签引用的 JS 文件存在
- `<link rel="manifest">` 指向正确
- 没有引用已删除的旧 chunk（PWA SW 死锁的典型症状）

## 命中后动作

- DT-03 命中：检查后端 `<backend_key_files.app_py>` 的根路径 RedirectResponse 和 SPA catch-all 路由注册
- 具体路径见 `config.yaml` 的 `backend_key_files.app_py`

## 输出报告

1. 三个路径的响应码和内容大小
2. 是否符合期望
3. 命中的决策节点 ID
