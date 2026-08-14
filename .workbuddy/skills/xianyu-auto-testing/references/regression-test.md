# 回归测试

本文档描述全面测试模式步骤 6（回归测试）的详细操作。

回归测试的目标是验证修复后的问题已解决，且未引入新问题。

## 1. 清除 Service Worker 缓存

### 为什么需要清除 SW 缓存

PWA `autoUpdate` 模式下，重新构建部署后：
- 新 SW 注册但旧 SW 仍在运行
- 旧 SW 缓存的旧 JS 文件仍在使用
- 首次刷新页面可能仍加载旧版本

### 清除操作

通过 `playwright_evaluate` 执行 `config.yaml` 中 `test_execution.sw_cleanup.unregister_script`：

该脚本执行以下操作：
1. 获取所有 Service Worker 注册
2. 逐个 unregister
3. 获取所有 Cache Storage keys
4. 逐个 delete caches
5. 返回清理结果（注销数量 + 清除缓存数量）

**预期输出**：`"unregistered N SW, cleared M caches"`

### 注意事项

- 清除 SW 缓存后，页面不会自动刷新，需手动导航
- 关闭并重新打开页面时 cookie 会丢失，需重新设置认证 cookie
- `playwright_console_logs` 返回的是整个会话的历史日志，不能用于判断当前页面是否产生新的日志

## 2. 重新加载页面

1. **设置认证 cookie**（见 `page-traversal.md` 的"设置认证"部分）
2. **导航到移动端首页**：`http://{host}:{port}{spa.mobile_home_path}`
3. **隐藏登录引导浮层**（见 `page-traversal.md` 的"隐藏登录引导浮层"部分）
4. **等待页面加载**（2-3 秒）

## 3. 验证修复效果

### 3.1 验证 JS 文件内容

使用 `test_execution.sw_cleanup.verify_script_template` 验证构建产物是否包含/不包含指定字符串。

模板中的占位符：
- `{js_path}`：JS 文件路径（如从页面 script 标签获取）
- `{search_string}`：要搜索的字符串

#### 获取当前加载的 JS 文件路径

```javascript
(function(){
  var scripts = document.querySelectorAll('script[src]');
  var srcs = [];
  scripts.forEach(function(s){ srcs.push(s.src); });
  return JSON.stringify(srcs.slice(-5));
})()
```

#### 验证 JS 文件内容

将 `verify_script_template` 中的 `{js_path}` 替换为实际路径，`{search_string}` 替换为要检查的字符串。

例如验证诊断日志已移除：
- `{js_path}` = `/xianyu/assets/index-XXXXX.js`
- `{search_string}` = `detectMobile`

预期结果：`"hasString": false`

### 3.2 Hook console.info 计数新调用

通过 `playwright_evaluate` 重写 `console.info`，计数特定前缀的调用：

```javascript
(function(){
  window.__detectCalls = 0;
  var origInfo = console.info;
  console.info = function(){
    var args = Array.from(arguments);
    if (args[0] === '{console_prefix}') {
      window.__detectCalls++;
    }
    origInfo.apply(console, args);
  };
  return 'console.info hooked';
})()
```

`{console_prefix}` ← `diagnostic.console_prefix`

然后导航到目标页面，等待几秒后检查计数：

```javascript
(function(){
  return new Promise(function(resolve){
    setTimeout(function(){
      resolve(JSON.stringify({ detectCalls: window.__detectCalls || 0 }));
    }, 3000);
  });
})()
```

预期结果：`detectCalls: 0`（诊断日志已移除）

### 3.3 检查 DOM 是否包含诊断浮层文本

导航到带诊断参数的 URL（如 `?debug=mobile`），检查页面是否包含诊断浮层文本：

```javascript
(function(){
  return new Promise(function(resolve){
    setTimeout(function(){
      var hasDiagnostic = document.body.textContent.includes('{diagnostic_title}');
      resolve(JSON.stringify({ hasDiagnostic: hasDiagnostic }));
    }, 3000);
  });
})()
```

`{diagnostic_title}` 从 `diagnostic.visible_fields` 中的标题文本读取。

预期结果：`hasDiagnostic: false`（诊断浮层已移除）

## 4. 验证未引入新问题

### 4.1 重跑关键页面导航

执行 TabBar 5 个 Tab 的导航测试（见 `button-interaction.md` 的"TabBar 导航测试"部分）：

1. 点击每个 Tab
2. 验证 URL 跳转正确
3. 验证 active 状态正确

### 4.2 检查 console 是否有新的 error

调用 `playwright_console_logs`，检查是否有 `[error]` 级别日志。

**注意**：由于 `console_logs` 返回历史日志，需通过日志内容判断是否为当前页面产生的新错误。可通过：
- 关闭页面后重新打开（但 cookie 会丢失）
- 或检查错误消息内容是否与修复前的错误不同

### 4.3 检查页面内容

导航到几个关键页面（如仪表盘、任务、抢单），检查：
- 页面内容正常渲染（innerHTML 长度 ≥ `content_min_length`）
- 预期内容关键词存在
- 无白屏

## 5. 记录回归测试结果

| 检查项 | 预期 | 实际 | 状态 |
|--------|------|------|------|
| SW 缓存清除 | unregistered N SW | unregistered 1 SW | PASS |
| JS 文件验证 | hasString: false | hasString: false | PASS |
| console.info 计数 | detectCalls: 0 | detectCalls: 0 | PASS |
| 诊断浮层验证 | hasDiagnostic: false | hasDiagnostic: false | PASS |
| TabBar 导航 | 5/5 通过 | 5/5 通过 | PASS |
| Console errors | 无新 error | 无新 error | PASS |
| 页面内容 | 正常渲染 | 正常渲染 | PASS |

全部通过则回归测试通过。
