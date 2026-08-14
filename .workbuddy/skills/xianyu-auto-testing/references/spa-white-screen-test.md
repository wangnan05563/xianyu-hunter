# SPA 白屏回归测试参考文档

> 本文档为 xianyu-auto-testing 模式 U（SPA 白屏回归测试模式）的详细操作参考。
> 所有参数从 `config.yaml#mode_u_spa_white_screen_test` 读取，禁止硬编码。
> 对应 2026-07-22 间歇性白屏 Bug 复盘（meta-rule #95），覆盖 5 类根因：
> 1. 缺少全局 ErrorBoundary
> 2. 懒加载 chunk 失效无重试
> 3. 未保护的数据访问
> 4. 401 拦截器硬跳转
> 5. 路由级错误无隔离

---

## 1. 三件套完整性扫描

### 1.1 全局 ErrorBoundary 扫描

```powershell
# 从 config 读取扫描命令与必需文件
$scanCmd = $config.mode_u_spa_white_screen_test.error_boundary_check.scan_command
$requiredFiles = $config.mode_u_spa_white_screen_test.error_boundary_check.required_files
$minMatch = $config.mode_u_spa_white_screen_test.error_boundary_check.min_match_count

# 验证 App.tsx 中有 <ErrorBoundary> 包裹 Routes
Invoke-Expression $scanCmd

# 验证 ErrorBoundary 组件文件存在
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-Warning "FAIL: Missing required file: $file"
    }
}
```

**通过条件**：
- `App.tsx` 中 `<ErrorBoundary>` 出现次数 ≥ `min_match_count`（默认 1）
- `frontend/src/components/ErrorBoundary.tsx` 文件存在
- ErrorBoundary 包裹了 `<Routes>` 或路由根节点

**失败示例**：
- App.tsx 直接渲染 `<Routes>` 而未用 `<ErrorBoundary>` 包裹 → 子组件抛错导致整树白屏

### 1.2 lazyRetry 包装扫描

```powershell
# 扫描所有 lazy() 调用，识别未用 lazyRetry 包装的项
$scanCmd = $config.mode_u_spa_white_screen_test.lazy_retry_check.scan_command
Invoke-Expression $scanCmd

# 输出非空 → 存在未包装的 lazy()
```

**通过条件**：扫描结果为空（所有 `lazy()` 都被 `lazyRetry()` 包装）。

**失败示例**：
```tsx
// 错误：直接使用 lazy()，chunk 加载失败无重试
const Foo = lazy(() => import('./Foo'));

// 正确：用 lazyRetry 包装
const Foo = lazyRetry(() => import('./Foo'));
```

### 1.3 路由级 ErrorBoundary 扫描

```powershell
# 扫描 MainLayout.tsx 中的 resetKeys 声明
$scanCmd = $config.mode_u_spa_white_screen_test.route_error_boundary_check.scan_command
Invoke-Expression $scanCmd
```

**通过条件**：
- `MainLayout.tsx` 中存在 `<ErrorBoundary resetKeys={[location.pathname]}>` 包裹 `<Outlet>`
- resetKeys 使用基本类型（string/number）

**失败示例**：
```tsx
// 错误：resetKeys 传入对象引用，导致 ErrorBoundary 无法捕获重置
<ErrorBoundary resetKeys={[location]}>  // location 是对象
  <Outlet />
</ErrorBoundary>

// 正确：用 pathname 字符串
<ErrorBoundary resetKeys={[location.pathname]}>
  <Outlet />
</ErrorBoundary>
```

### 1.4 resetKeys 类型约束验证

读取 `MainLayout.tsx` 中 `<ErrorBoundary>` 的 `resetKeys` 属性，对每个数组元素验证类型：
- 允许的类型：`string`、`number`
- 禁止的类型：`object`、`array`（引用类型，引用变化无法被 React 浅比较识别）

**验证逻辑**：
```typescript
// 校验函数（仅用于说明逻辑，实际由静态扫描实现）
function validateResetKeys(resetKeys: unknown[]): boolean {
  return resetKeys.every(key => typeof key === 'string' || typeof key === 'number');
}
```

---

## 2. API 防御性访问扫描

### 2.1 数组字段直接访问扫描

```powershell
# 扫描所有 res.xxx. / data.xxx. 等数组字段直接访问
$scanCmd = $config.mode_u_spa_white_screen_test.api_array_defense_check.scan_command
Invoke-Expression $scanCmd

# 输出每行包含：文件路径 + 匹配的代码片段
```

**扫描正则**：`\b(res|data|response)\.(items|tables|list|records|data|results)\.`

**失败示例**：
```tsx
// 错误：未兜底，res.items 为 undefined 时 .map 抛 TypeError 导致白屏
{res.items.map(item => <Row key={item.id} data={item} />)}

// 正确：用 || [] 兜底
{(res.items || []).map(item => <Row key={item.id} data={item} />)}
```

### 2.2 兜底验证

对每个匹配项，读取上下文 5 行，验证解构后是否用 `|| []` 兜底：

```powershell
# 对每个匹配位置检查上下文是否包含 || []
$matches = Invoke-Expression $scanCmd
foreach ($m in $matches) {
    $file = $m.Path
    $lineNum = $m.LineNumber
    $context = Get-Content $file | Select-Object -Skip ($lineNum - 3) -First 8
    if ($context -notmatch '\|\|\s*\[\]') {
        Write-Warning "FAIL: $file:$lineNum 缺少 || [] 兜底"
    }
}
```

### 2.3 可选链验证

扫描对象字段访问，验证是否用 `?.` 可选链：

```powershell
# 扫描 data.field.subField 模式（未用可选链）
Select-String -Path 'frontend/src/**/*.tsx' -Pattern '\b(data|item|record)\.\w+\.\w+' |
    Where-Object { $_.Line -notmatch '\?\.' }
```

**修复示例**：
```tsx
// 错误：data.user.name 在 user 为 null 时抛 TypeError
const userName = data.user.name;

// 正确：用可选链
const userName = data?.user?.name;
```

---

## 3. 401 拦截器防抖验证

### 3.1 防抖标记扫描

```powershell
# 扫描 401 拦截器代码
$scanCmd = $config.mode_u_spa_white_screen_test.http_401_debounce_check.scan_command
$debounceFlag = $config.mode_u_spa_white_screen_test.http_401_debounce_check.debounce_flag
Invoke-Expression $scanCmd | Select-String $debounceFlag
```

**通过条件**：401 拦截器代码中存在 `isRedirecting`（或配置的防抖标记变量）。

**失败示例**：
```typescript
// 错误：每次 401 都执行 window.location.href，并发请求触发多次跳转
if (error.response?.status === 401) {
  window.location.href = '/login';
}

// 正确：用防抖标记
let isRedirecting = false;
if (error.response?.status === 401) {
  if (isRedirecting) return;
  isRedirecting = true;
  window.location.replace('/login');
}
```

### 3.2 跳转方法验证

```powershell
$requiredMethod = $config.mode_u_spa_white_screen_test.http_401_debounce_check.required_redirect_method
$forbiddenMethod = $config.mode_u_spa_white_screen_test.http_401_debounce_check.forbidden_redirect_method

# 验证使用 window.location.replace 而非 window.location.href
Select-String -Path 'frontend/src/api/client.ts' -Pattern "window\.location\.$forbiddenMethod" |
    ForEach-Object { Write-Warning "FAIL: 使用了禁止的 $forbiddenMethod 跳转方法" }
```

**为什么用 replace 而非 href**：
- `href` 跳转后用户按"后退"按钮会回到失效页面，再次触发 401 跳转，陷入死循环
- `replace` 替换当前历史记录，避免后退回到失效页面

### 3.3 并发场景模拟（浏览器自动化）

通过 Playwright MCP 触发并发 401 请求，验证只跳转一次：

```javascript
// 通过 playwright_evaluate 注入并发请求
await page.evaluate(async () => {
  // 模拟 5 个并发请求同时返回 401
  const requests = Array.from({length: 5}, () =>
    fetch('/api/protected/resource', {headers: {'Authorization': 'invalid-token'}})
  );
  await Promise.all(requests);
});

// 验证：仅发生 1 次 navigation 事件
const navigationCount = await page.evaluate(() => {
  return window.__navigationCount || 0;  // 通过测试 hook 计数
});
// 通过条件：navigationCount === 1
```

**通过条件**：5 个并发 401 请求只触发 1 次跳转。

---

## 4. ErrorBoundary 单元测试

### 4.1 测试文件存在性验证

```powershell
$testFile = 'frontend/src/components/__tests__/ErrorBoundary.test.tsx'
if (-not (Test-Path $testFile)) {
    Write-Warning "FAIL: 测试文件缺失 - $testFile"
}
```

### 4.2 测试用例覆盖度验证

```powershell
$cmd = $config.mode_u_spa_white_screen_test.unit_test.error_boundary_test_command
Invoke-Expression $cmd
```

**6 类必需用例**：

#### 用例 1：正常渲染不触发错误界面
```tsx
test('正常渲染不触发错误界面', () => {
  render(
    <ErrorBoundary>
      <div>正常内容</div>
    </ErrorBoundary>
  );
  expect(screen.getByText('正常内容')).toBeInTheDocument();
  expect(screen.queryByText(/出错了/)).not.toBeInTheDocument();
});
```

#### 用例 2：子组件抛错显示错误界面
```tsx
test('子组件抛错显示错误界面', () => {
  const Bomb = () => { throw new Error('boom'); };
  // 抑制控制台错误日志干扰测试输出
  const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
  render(
    <ErrorBoundary>
      <Bomb />
    </ErrorBoundary>
  );
  expect(screen.getByText(/出错了|出错了/)).toBeInTheDocument();
  spy.mockRestore();
});
```

#### 用例 3：点击重试按钮清除错误状态
```tsx
test('点击重试按钮清除错误状态', () => {
  // 用 antd Button 渲染"重 试"或"重试"（兼容空格）
  const retryBtn = screen.getByRole('button', { name: /重\s*试/ });
  fireEvent.click(retryBtn);
  // 验证错误状态被清除
});
```

#### 用例 4：resetKeys 变化自动重置错误状态
```tsx
test('resetKeys 变化自动重置错误状态', () => {
  const { rerender } = render(
    <ErrorBoundary resetKeys={['/page1']}>
      <Bomb />
    </ErrorBoundary>
  );
  // 切换 resetKey
  rerender(
    <ErrorBoundary resetKeys={['/page2']}>
      <NormalChild />
    </ErrorBoundary>
  );
  // 验证错误界面消失，正常内容渲染
});
```

#### 用例 5：onError 回调被正确调用
```tsx
test('onError 回调被正确调用', () => {
  const onError = jest.fn();
  const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
  render(
    <ErrorBoundary onError={onError}>
      <Bomb />
    </ErrorBoundary>
  );
  expect(onError).toHaveBeenCalledWith(
    expect.any(Error),
    expect.objectContaining({ componentStack: expect.any(String) })
  );
  spy.mockRestore();
});
```

#### 用例 6：自定义 fallback 替代默认 UI
```tsx
test('自定义 fallback 替代默认 UI', () => {
  const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
  render(
    <ErrorBoundary fallback={<div>自定义错误页</div>}>
      <Bomb />
    </ErrorBoundary>
  );
  expect(screen.getByText('自定义错误页')).toBeInTheDocument();
  spy.mockRestore();
});
```

### 4.3 antd 中文按钮断言验证

验证测试用例中 antd Button 中文文案用 `getByRole('button', { name: /文\s*案/ })` 正则兼容空格：

**为什么需要正则兼容空格**：
- antd 5.x 默认在中文按钮文案的字符间插入 `&ZeroWidthSpace;`（U+200B）以优化中文排版
- 直接用 `getByText('重试')` 会失败，因实际渲染为 `重\u200B试`
- 用 `getByRole('button', { name: /重\s*试/ })` 通过正则 `\s*` 兼容空格

**禁止的匹配方式**：
```tsx
// 错误：直接用 getByText 匹配中文，遇 U+200B 失败
const btn = screen.getByText('重试');

// 正确：用 role + 正则
const btn = screen.getByRole('button', { name: /重\s*试/ });
```

---

## 5. lazyRetry 单元测试

### 5.1 测试文件存在性验证

```powershell
$testFile = 'frontend/src/utils/__tests__/lazyRetry.test.tsx'
if (-not (Test-Path $testFile)) {
    Write-Warning "FAIL: 测试文件缺失 - $testFile"
}
```

### 5.2 测试用例覆盖度验证

```powershell
$cmd = $config.mode_u_spa_white_screen_test.unit_test.lazy_retry_test_command
Invoke-Expression $cmd
```

**6 类必需用例**：

#### 用例 1：isChunkLoadError 识别各类 chunk 错误

```tsx
test('isChunkLoadError 识别 Vite/Webpack/CSS chunk 错误', () => {
  // Vite 风格
  const viteErr = new Error('Failed to fetch dynamically imported module: /Foo.tsx');
  expect(isChunkLoadError(viteErr)).toBe(true);

  // Webpack 风格
  const webpackErr = new Error('Loading chunk 42 failed.');
  expect(isChunkLoadError(webpackErr)).toBe(true);

  // CSS chunk 失败
  const cssErr = new Error('Loading CSS chunk 42 failed.');
  expect(isChunkLoadError(cssErr)).toBe(true);
});
```

#### 用例 2：非 chunk 错误不识别

```tsx
test('非 chunk 错误不识别', () => {
  const typeErr = new TypeError('Cannot read properties of undefined');
  expect(isChunkLoadError(typeErr)).toBe(false);

  const syntaxErr = new SyntaxError('Unexpected token');
  expect(isChunkLoadError(syntaxErr)).toBe(false);
});
```

#### 用例 3：正常加载不触发重试

```tsx
test('正常加载不触发重试', async () => {
  const factory = jest.fn().mockResolvedValue({ default: () => <div>Foo</div> });
  const LazyFoo = lazyRetry(factory);

  await act(async () => {
    render(<Suspense fallback={<div>loading</div>}><LazyFoo /></Suspense>);
  });

  expect(factory).toHaveBeenCalledTimes(1);
  expect(screen.getByText('Foo')).toBeInTheDocument();
});
```

#### 用例 4：chunk 失败自动重试到上限

```tsx
test('chunk 失败自动重试到上限', async () => {
  const maxRetries = config.mode_u_spa_white_screen_test.lazy_retry_check.max_retries;
  const factory = jest.fn().mockRejectedValue(new Error('Failed to fetch dynamically imported module'));

  const LazyFoo = lazyRetry(factory);
  const spy = jest.spyOn(console, 'error').mockImplementation(() => {});

  await act(async () => {
    render(<Suspense fallback={<div>loading</div>}><LazyFoo /></Suspense>);
  });

  // factory 被调用 maxRetries + 1 次（首次 + maxRetries 次重试）
  expect(factory).toHaveBeenCalledTimes(maxRetries + 1);
  spy.mockRestore();
});
```

#### 用例 5：LazyErrorBoundary 兜底渲染

```tsx
test('LazyErrorBoundary 兜底渲染', async () => {
  const factory = jest.fn().mockRejectedValue(new Error('Failed to fetch dynamically imported module'));
  const LazyFoo = lazyRetry(factory, { fallback: <div>加载失败</div> });

  const spy = jest.spyOn(console, 'error').mockImplementation(() => {});

  await act(async () => {
    render(<Suspense fallback={<div>loading</div>}><LazyFoo /></Suspense>);
  });

  expect(screen.getByText('加载失败')).toBeInTheDocument();
  spy.mockRestore();
});
```

#### 用例 6：resetKey 变化触发重置

```tsx
test('resetKey 变化触发重置', async () => {
  const factory = jest.fn().mockRejectedValue(new Error('Failed to fetch dynamically imported module'));
  const LazyFoo = lazyRetry(factory);

  const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
  const { rerender } = render(<Suspense fallback={null}><LazyFoo resetKey="page1" /></Suspense>);

  // 重试计数达到上限后，切换 resetKey 应重置计数
  rerender(<Suspense fallback={null}><LazyFoo resetKey="page2" /></Suspender>);

  // 验证 sessionStorage 中重试计数被清零
  const stored = sessionStorage.getItem('__retry_Foo');
  expect(stored).toBeNull();
  spy.mockRestore();
});
```

### 5.3 sessionStorage 重试计数验证

**为什么用 sessionStorage 持久化**：
- React.lazy 的 factory 失败后，组件卸载时状态丢失
- 用 sessionStorage 持久化重试计数，跨重试周期保留进度
- 达到 maxRetries 后 reload 只执行一次（避免无限 reload）

**验证逻辑**：
```typescript
// 验证 sessionStorage 在达到 maxRetries 后被清理
const retryCount = parseInt(sessionStorage.getItem('__retry_Foo') || '0');
if (retryCount >= maxRetries) {
  // 停止重试，渲染 fallback
  sessionStorage.removeItem('__retry_Foo');
}
```

**验证标准**：
- 重试过程中 sessionStorage 计数从 0 递增到 maxRetries
- 达到 maxRetries 后停止重试，sessionStorage 被清理
- 重新挂载组件时计数从 0 开始

---

## 7. 子路径 navigateFallback 相对化导致移动端白屏（meta-rule #117 / F-REVIEW-237）

> 对应 2026-08-13 复盘（retrospective-2026-08-13）：非根路径部署（`base` 非 `/`，如 `/xianyu/`）下，`navigateFallback` 用相对 `'index.html'`，移动端切换设备模拟访问子路由 `/xianyu/m/` 时 SW 回退到错误入口 → 整页白板。
> 所有参数从 `config.yaml#pwa` 读取（navigate_fallback_absolute_path / require_cleanup_outdated_caches / loading_splash_selector），禁止硬编码。

### 7.1 根因识别
- `vite.config.ts` 的 `base` 非 `/` 但 `navigateFallback` 为相对 `'index.html'`（或 SW 构建后 `createHandlerBoundToURL` 指向相对路径）。
- 移动端 UA 切换设备模拟时，子路由 `/xianyu/m/` 的导航请求被 SW 拦截回退，相对路径在子路径下解析错误 → 返回 200 但入口 chunk 错乱 → 白板。
- 旧 SW 在 `prompt` 模式 / 无 `cleanupOutdatedCaches` 时缓存旧 chunk，永久卡白屏。

### 7.2 验证步骤
1. 读 `pwa.navigate_fallback_absolute_path`，确认 `vite.config.ts` 的 `navigateFallback` 与 sw.js 的 `createHandlerBoundToURL` 均为该绝对路径。
2. 确认 `cleanupOutdatedCaches: true`（`pwa.require_cleanup_outdated_caches`）。
3. 确认 `index.html` 含 `loading_splash_selector` 加载占位（JS 挂载后替换）。
4. 浏览器自动化：桌面 UA 访问 `/xianyu/` 正常 → 切移动端 UA / 设备模拟访问 `/xianyu/m/` → 应正常渲染（非白板）。

```powershell
# base 非根 + 相对回退（命中即 P0）
Select-String -Path "frontend/vite.config.ts" -Pattern 'base:\s*[''"]/xianyu'
Select-String -Path "frontend/vite.config.ts" -Pattern "navigateFallback:\s*['\"]index\.html['\"]"
# sw.js 绝对化回退（正则子串提取，规避精确引号比对误判）
Select-String -Path "<build_output_dir>/sw.js" -Pattern "createHandlerBoundToURL\(['\"]<navigate_fallback_absolute_path 去引号>['\"]\)"
```

### 7.3 修复与缓解
- `navigateFallback` 改为绝对路径 `navigate_fallback_absolute_path`；`cleanupOutdatedCaches: true`；`registerType: autoUpdate`。
- `index.html` 加 `loading_splash_selector` 加载占位，避免纯白白屏。
- 部署对齐后清 PWA Service Worker 缓存 / 硬刷新一次（旧 SW 短暂下发旧入口 chunk）。

**通过条件**：`base` 非 `/` 时 navigateFallback 绝对化 + cleanupOutdatedCaches 开启 + 加载占位存在 + 移动端子路由访问非白板。

---

## 6. 测试报告模板

```markdown
## SPA 白屏回归测试报告（模式 U）

### 测试环境
- 测试时间: {timestamp}
- 测试范围: 渲染容错体系完整性回归
- 配置节点: mode_u_spa_white_screen_test

### 测试结果

| 步骤 | 检查项 | 状态 | 备注 |
|------|--------|------|------|
| U-01 | 全局 ErrorBoundary | PASS/FAIL | App.tsx 包裹 <ErrorBoundary> |
| U-01 | lazyRetry 包装 | PASS/FAIL | 所有 lazy() 被 lazyRetry() 包装 |
| U-01 | 路由级 ErrorBoundary | PASS/FAIL | MainLayout 包裹 <Outlet> |
| U-01 | resetKeys 类型约束 | PASS/FAIL | 全部为 string/number |
| U-02 | 数组字段兜底 | PASS/FAIL | {coverage}% 用 || [] 兜底 |
| U-02 | 可选链使用 | PASS/FAIL | {coverage}% 用 ?. 可选链 |
| U-03 | 401 防抖标记 | PASS/FAIL | isRedirecting 存在 |
| U-03 | 跳转方法 | PASS/FAIL | 用 window.location.replace |
| U-03 | 并发场景 | PASS/FAIL | 5 并发仅 1 次跳转 |
| U-04 | ErrorBoundary 测试 | PASS/FAIL | 6/6 用例通过 |
| U-05 | lazyRetry 测试 | PASS/FAIL | 6/6 用例通过 |
| U-07 | 子路径 navigateFallback 绝对化 | PASS/FAIL | base 非 / 时绝对回退 + cleanupOutdatedCaches + 加载占位 |

### 发现的问题
{问题描述} | 关联文件: {key_file} | 关联编号: {step/F-REVIEW} | 建议修复: {方案}

### 结论
{all_pass | has_failures} - {summary}
```
