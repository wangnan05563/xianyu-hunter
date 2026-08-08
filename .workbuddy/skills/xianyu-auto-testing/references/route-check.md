# C. 路由配置核查

> 对应决策节点：DT-04（isMobile Navigate 条件被破坏）、DT-08（认证拦截优先于 isMobile）

## 检查项

### C1. App.tsx 的 isMobile 跳转逻辑

读取 `config.yaml` 的 `key_files.app_tsx`，检查以下要素：

1. **useMobileDetect Hook 调用**：`const isMobile = useMobileDetect()`
2. **Navigate 跳转条件**：
   ```tsx
   if (isMobile
     && !globalThis.location.pathname.startsWith('<basename><mobile_route_prefix>')  // 如 /app/m
     && !globalThis.location.pathname.startsWith('<basename><login_route>')) {       // 如 /app/login
     return <Navigate to="<mobile_route_prefix>" replace />                          // 如 /m/
   }
   ```
3. **Navigate to 路径**：必须带尾斜杠（如 `<mobile_route_prefix>`），父路由 `<Route path="<mobile_route_prefix>*">` 的 splat 要求至少匹配 `/`

**关键点**：
- `globalThis.location.pathname` 是浏览器原生路径，**包含 BrowserRouter basename**
- `Navigate to="<mobile_route_prefix>"` 是 react-router 路径，**不含 basename**
- basename 配置在 `key_files.main_tsx`：`<BrowserRouter basename="<basename>">`

### C2. routes.tsx 的 Route 注册

读取 `config.yaml` 的 `key_files.mobile_routes`，检查：
1. `<Route path="<mobile_route_prefix>*" element={<MobileRoutes />} />` 在 App.tsx 中注册
2. MobileRoutes 内部 `<Route path="/" element={<MobileLayout />}>` 父路由
3. 子路由注册（`<Route path="tasks/" .../>` 等）路径是否带尾斜杠

**为什么路径带尾斜杠**：react-router v7 严格匹配模式下，`tasks` 不匹配 `tasks/`，会导致 404。

### C3. MainLayout 的认证拦截

读取 `config.yaml` 的 `key_files.main_layout`，检查 useEffect 中的认证拦截：

```tsx
useEffect(() => {
  if (authChecked && !loggedIn) {
    const currentPath = location.pathname + location.search
    navigate(`<login_route>?redirect=${encodeURIComponent(currentPath)}`, { replace: true })
  }
}, [authChecked, loggedIn, navigate, location.pathname, location.search])
```

**判断**：
- 如果 isMobile=true，App.tsx 应该直接返回 `<Navigate to="<mobile_route_prefix>" />`，不会渲染 MainLayout
- 如果用户被跳到 `<basename><login_route>?redirect=...`，说明 MainLayout 渲染了，即 isMobile=false
- 这是 DT-08 命中的典型症状

### C4. useMobileDetect 检测逻辑

读取 `config.yaml` 的 `key_files.use_mobile_detect` 和 `mobile_detect` 段，检查：

1. **UA 正则**：`MOBILE_UA_PATTERN` 是否包含 `mobile_detect.ua_pattern` 中的所有关键字
2. **iPadOS 13+ 兜底**：
   ```ts
   if (/<macintosh_pattern>/i.test(userAgent) && typeof document !== 'undefined') {
     return '<touch_event_property>' in document
   }
   ```
3. **视口宽度兜底**：`window.innerWidth <= <viewport_max_width>`
4. **useState 初始化**：`useState<boolean>(detectMobile)` 而非 `useState(false)`，避免首次 paint 走桌面路由再 setState 重渲染闪烁

## 命中后动作

- DT-04 命中：恢复 App.tsx 的 Navigate 跳转条件
- DT-08 命中：调整 MainLayout useEffect 时序，或把 isMobile 检查放在更早的位置

## 输出报告

1. App.tsx Navigate 条件的实际代码片段
2. MainLayout 认证拦截的实际代码片段
3. useMobileDetect 的正则与兜底逻辑
4. 命中的决策节点 ID
