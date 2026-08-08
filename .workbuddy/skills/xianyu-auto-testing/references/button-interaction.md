# 按钮交互测试

本文档描述全面测试模式步骤 4（按钮交互测试）的详细操作。

## 测试策略

根据 `config.yaml` 的 `test_execution.button_interaction.strategy`：

- **all**：全量点击所有可交互按钮
- **whitelist**：仅点击白名单中的按钮
- **blacklist**：跳过 `skip_button_texts` 中的按钮（推荐）

`skip_button_texts` 中的按钮通常是不可逆或有副作用的操作（如"删除"、"清空"、"回滚"）。

## TabBar 导航测试

### 1. 获取 TabBar 按钮数量

通过 `playwright_evaluate` 执行：

```javascript
(function(){
  var btns = document.querySelectorAll('{tabbar_button}');
  return btns.length;
})()
```

`{tabbar_button}` ← `routes_discovery.button_selectors.tabbar_button`

### 2. 逐个点击 Tab

对每个 Tab（从第 1 个到第 N 个），使用 CSS `:nth-child()` 选择器：

调用 `playwright_click`：
```
selector: "{tabbar_button}:nth-child({i})"
```

### 3. 验证跳转

点击后通过 `playwright_evaluate` 检查：

```javascript
(function(){
  return JSON.stringify({
    url: window.location.pathname,
    activeTab: document.querySelector('{tabbar_active} {tabbar_label}')?.textContent || 'none'
  });
})()
```

参数替换：
- `{tabbar_active}` ← `routes_discovery.button_selectors.tabbar_active`
- `{tabbar_label}` ← `routes_discovery.button_selectors.tabbar_label`

验证 `url` 是否跳转到预期路径，`activeTab` 是否为当前点击的 Tab 名称。

## Dashboard 入口按钮测试

### 1. 获取入口按钮列表

导航到 Dashboard 页面后，通过 `playwright_evaluate` 获取所有按钮文本：

```javascript
(function(){
  var btns = document.querySelectorAll('{content_button}');
  var result = [];
  btns.forEach(function(b){
    var text = b.textContent.trim().substring(0, 30);
    if (text) result.push(text);
  });
  return JSON.stringify(result);
})()
```

`{content_button}` ← `routes_discovery.button_selectors.content_button`

### 2. 逐个点击入口按钮

对每个按钮，通过 `playwright_evaluate` 执行点击（避免选择器特殊字符问题）：

```javascript
(function(){
  var btns = document.querySelectorAll('{content_button}');
  for (var i = 0; i < btns.length; i++) {
    if (btns[i].textContent.trim() === '{button_text}') {
      btns[i].click();
      return 'clicked';
    }
  }
  return 'not found';
})()
```

### 3. 验证跳转

点击后检查 `window.location.pathname` 是否跳转到预期页面。

## 页面功能按钮测试

### 1. 逐页识别按钮

导航到每个配置页面，通过 `playwright_evaluate` 获取按钮列表。

如果页面有异步加载，需等待后再获取按钮（使用轮询策略，见 `page-traversal.md`）。

### 2. 按策略过滤按钮

根据 `test_execution.button_interaction.strategy`：

- **blacklist**：跳过 `skip_button_texts` 中的按钮
- **whitelist**：仅点击白名单按钮
- **all**：全量点击

### 3. 点击按钮并验证

对每个按钮执行：

#### 点击

使用 `playwright_evaluate` 执行 JS 点击（见上方模板）。

#### 等待响应

通过 `playwright_evaluate` 等待 toast 出现：

```javascript
(function(){
  return new Promise(function(resolve){
    setTimeout(function(){
      var toast = document.querySelector('{toast_selector}');
      var loading = !!document.querySelector('{loading_selector}');
      resolve(JSON.stringify({
        toast: toast ? toast.textContent.trim().substring(0, 150) : 'none',
        loading: loading
      }));
    }, {toast_wait_ms});
  });
})()
```

参数替换：
- `{toast_selector}` ← `test_execution.button_interaction.toast_selector`
- `{loading_selector}` ← `test_execution.button_interaction.loading_selector`
- `{toast_wait_ms}` ← `test_execution.button_interaction.toast_wait_ms`

#### 检查 modal 弹窗

某些按钮可能弹出 modal 而非 toast：

```javascript
(function(){
  return new Promise(function(resolve){
    setTimeout(function(){
      var modal = document.querySelector('{modal_selector}');
      resolve(JSON.stringify({
        modal: modal ? modal.textContent.trim().substring(0, 150) : 'none'
      }));
    }, {toast_wait_ms});
  });
})()
```

`{modal_selector}` ← `test_execution.button_interaction.modal_selector`

#### 检查 URL 变化

```javascript
(function(){
  return window.location.pathname;
})()
```

#### 检查按钮状态变化

某些按钮点击后文本会变化（如"开启轮询"→"停止轮询"）：

```javascript
(function(){
  var btns = document.querySelectorAll('{content_button}');
  var result = [];
  btns.forEach(function(b){ result.push(b.textContent.trim().substring(0, 30)); });
  return JSON.stringify(result);
})()
```

### 4. 恢复按钮状态

如果按钮点击后产生了状态变化（如开启了轮询），需点击恢复按钮将状态恢复原状。

## 记录结果

每个按钮记录：

| # | 页面 | 按钮名称 | 状态 | Toast/Modal | URL 变化 | 备注 |
|---|------|---------|------|-------------|---------|------|
| 1 | TabBar | 仪表盘 Tab | PASS | - | /app/m/ | 跳转正常 |
| 2 | TabBar | 任务 Tab | PASS | - | /app/m/tasks/ | 跳转正常 |
| ... | ... | ... | ... | ... | ... | ... |

状态取值：PASS / FAIL / SKIP

## 注意事项

1. **副作用按钮谨慎点击**：`skip_button_texts` 中的按钮跳过，避免修改/删除数据
2. **异步页面等待**：部分页面按钮在异步加载完成后才出现，需先等待页面加载
3. **toast 消息可能消失很快**：如果 `toast_wait_ms` 后 toast 已消失，检查 console 是否有 error
4. **header 中的按钮**：使用 `routes_discovery.button_selectors.global_button` 选择器包含 header 中的按钮
5. **按钮点击后页面可能跳转**：点击后需检查 URL，如果跳转到新页面，后续按钮测试需在新页面执行
