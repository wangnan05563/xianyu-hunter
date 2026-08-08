# E. 浏览器自动化验证

> 对应决策节点：DT-07（useMobileDetect UA 不匹配）

## 检查项

### E1. browser_use subagent 验证场景

读取 `config.yaml` 的 `browser_automation` 段，按 `scenarios` 列表逐个调用 browser_use subagent：

```python
# 场景模板（每个场景一次 browser_use 调用）
Task(
    subagent_type="browser_use",
    description="<scenario.description>",
    query="""
    访问 <url_template>（替换 {host} {port} 为实际值）
    等待 2-3 秒
    报告：
    - 最终 URL
    - console errors
    - 是否触发 Navigate 跳转
    - 截图
    """
)
```

**三个验证场景**（来自 `config.yaml` 的 `browser_automation.scenarios`）：

1. **desktop_root**：桌面 UA 访问根路径（基准对照）
   - 期望最终 URL 匹配 `expected_final_url_pattern`
   - 期望状态码 `expected_status`

2. **desktop_app_m**：桌面 UA 直接访问移动端路径
   - 期望页面渲染
   - 期望 title 包含 `expected_title_contains`

3. **mobile_root**：移动端 UA 访问根路径（验证自动跳转）
   - 期望最终 URL 匹配 `expected_final_url_pattern`（应跳转到 `<spa.mobile_home_path>`）

### E2. browser_use 已知限制

读取 `config.yaml` 的 `browser_automation.known_limitations`：

- 无法切换 User-Agent
- 无法访问 DevTools Application 面板
- 无法执行 browser_evaluate 任意 JS
- 实际 navigator.userAgent 是 Electron 桌面环境

**意味着**：mobile_root 场景在 browser_use 下无法真正验证移动端跳转。

### E3. UA 切换失败的 fallback 策略

读取 `config.yaml` 的 `browser_automation.ua_fallback_strategy`：

**fallback 策略**：代码层面分析 + 用户实际设备验证

1. **代码层面分析**：
   - Read `useMobileDetect.ts` 确认正则覆盖用户手机 UA
   - 用代码逻辑推断在真实 iPhone/Android UA 下的判定结果

2. **用户实际设备验证**：
   - 加诊断浮层（见 `diagnostic-output.md`）
   - 让用户在手机上访问 `?<query_param_name>=<query_param_value>`
   - 报告诊断页面显示的内容

### E4. 收集 console errors 和 network 失败

每个 browser_use 调用后，要求 subagent 报告：
- console error 消息
- network 失败请求的 URL 和状态码
- 页面截图

**典型错误**：
- `net::ERR_ABORTED /api/auth/me`：未登录触发的 401，axios 拦截器跳转登录页
- `net::ERR_ABORTED /api/stats/today`：Dashboard 加载统计接口失败
- chunk 加载失败（如 `Failed to load resource: index-xxxx.js`）：PWA SW 缓存旧 chunk 的典型症状

## 命中后动作

- DT-07 命中：
  1. 进入阶段 F（诊断输出），加 visible 浮层
  2. 重新构建
  3. 让用户在手机上访问 `?<query_param_name>=<query_param_value>` 报告 UA
  4. 根据用户报告的 UA，扩展 `mobile_detect.ua_pattern` 或加 ontouchend 兜底

## 输出报告

1. 每个场景的最终 URL 和 console errors
2. browser_use 限制导致无法验证的场景
3. fallback 策略的执行结果
4. 命中的决策节点 ID
