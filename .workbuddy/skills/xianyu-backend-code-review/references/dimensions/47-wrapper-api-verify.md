# 维度 47：第三方/包装器 API 核实🆕v4.71.0 · B-REVIEW-340

> **编码规范引用**：xianyu-hunter-dev `references/coding-standards-2026-08-13.md` §15 / meta-rule #126
> **配置节点**：（依赖 `browser` 包装器定义，无新增配置节点）
> **测试关联**：xianyu-auto-testing 模式 D（Playwright 超时）/ 模式 N（登录副作用）
> **复盘来源**：retrospective-2026-08-13-login-cookie.md（案例 H/P0-2 + 规范 #126）

## 触发条件
- 调用第三方 SDK / 项目自定义包装器方法（如 `container.browser`）
- 假设某方法「在原生库不存在」而判定为无效/空操作
- 新增对浏览器/外部资源的操作

## 检查规则

### 强制（P0 阻塞）
- 调用第三方/包装器方法前，必须核实其**真实类与方法签名**：
  - 如 `container.browser` 是项目自定义 `BrowserManager` 包装器（`src/xianyu_hunter/infra/browser.py`），非原生 Playwright `Browser`；其 `get_cookies()`/`new_page()`/`add_cookies()` 合法。
  - 原生 `Browser` 无 `get_cookies()`（需 `context.cookies()`），但包装器有 → 假设「方法不存在」会误判为空操作。
- 每个外部操作放 `try/except` 内，单步失败不影响主流程（非致命）。

### 推荐（P1 严重）
- 包装器公共方法在 `try/except` 内调用，失败记录 warning 而非中断。

### 推荐（P2 改进）
- 关键包装器 API 在 `references/browser-subprocess-patterns.md` 登记，审查时对照。

## Grep 扫描命令
```bash
# 确认包装器真实 API
grep -n "class BrowserManager\|def get_cookies\|def new_page\|def add_cookies" src/xianyu_hunter/infra/browser.py

# 检测调用点是否核实过类型
grep -n "container.browser\.\|browser.get_cookies\|browser.new_page" src/xianyu_hunter/web/routes/unified_login.py
```

## 判断标准
- 假设「方法不存在」前未查定义 → P0 阻塞（误判空操作）
- 外部操作不在 `try/except` 内 → P1 严重

## 适用场景
- 调用第三方 SDK / 项目自定义包装器（如 BrowserManager）
- 原生库 API 与包装器 API 不一致时

## 不适用场景
- 直接持有原生对象且文档明确
- 纯标准库调用
