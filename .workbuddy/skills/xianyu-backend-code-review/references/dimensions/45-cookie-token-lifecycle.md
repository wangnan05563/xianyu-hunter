# 维度 45：Cookie/会话令牌生命周期（预热首页 + 注入后 rehydrate）🆕v4.71.0 · B-REVIEW-338

> **编码规范引用**：xianyu-hunter-dev `references/coding-standards-2026-08-13.md` §12 / meta-rule #121 / #122
> **配置节点**：config.yaml#cookie_token_consistency（既有）+ config.yaml#cookie_warmup + config.yaml#cookie_rehydrate（新增）
> **测试关联**：xianyu-auto-testing 模式 C（Cookie 自愈）/ 模式 N（登录副作用）
> **复盘来源**：retrospective-2026-08-13-login-cookie.md（案例 H + 流程 P2 + 规范 #121/#122）

## 触发条件
- 登录/导出/cookie 注入前预热逻辑变更（`scripts/browser_login.py`）
- 向 Worker/无头浏览器注入 cookie 逻辑变更（`src/xianyu_hunter/web/routes/unified_login.py`）
- 涉及 `_m_h5_tk` / MTOP 会话令牌刷新、回写（`cookie_rotator.py` / `cookie_store.py`）

## 检查规则

### 强制（P0 阻塞）
- 登录/导出前预热必须访问 `config.yaml#cookie_warmup.homepage_url`（如 `https://www.goofish.com/`，平台首页），触发 MTOP `_m_h5_tk` 刷新；**禁止**仅访问子页（如 `/personal`，不触发刷新 → 导出过期令牌）。
- 向 Worker/浏览器注入 cookie 后必须 rehydrate（注入 ≠ 生效）：开新 page → 访问 `homepage_url` → 等 networkidle + `config.yaml#cookie_rehydrate.sleep_buffer_sec` → 读新鲜 `_m_h5_tk`/`_m_h5_tk_enc` → `update_cookie_values(updates, user_id=)` 回写 JSON。
- 令牌有效性判定用 `is_m5tk_expired(value)`（嵌入式时间戳），不依赖 cookie `expires` 字段（会话 cookie `expires=-1`）。

### 推荐（P1 严重）
- 预热后加 `wait_for_load_state("networkidle")` + 固定缓冲，确保令牌写入后再导出。
- rehydrate 步骤放在 `try/except` 内（非致命），单步失败不影响主流程。

### 推荐（P2 改进）
- 预热页/刷新页集中在配置（`cookie_warmup.homepage_url` / `cookie_rehydrate.homepage_url`），避免散落硬编码。

## Grep 扫描命令
```bash
# 检测预热页是否为首页（而非子页）
grep -n "goto(" scripts/browser_login.py

# 检测注入后是否有 rehydrate
grep -n "sync_cookie_layers_from_json\|_refresh_worker_m5tk\|update_cookie_values" src/xianyu_hunter/web/routes/unified_login.py

# 检测令牌过期判定
grep -n "is_m5tk_expired" src/xianyu_hunter/modules/cookie_rotator.py
```

## 判断标准
- 预热页是 `/personal` 等子页 → P0 阻塞（不触发 MTOP 刷新）
- 注入后无 rehydrate 步骤 → P0 阻塞（缺 `_m_h5_tk` 刷新）
- 令牌有效性依赖 `expires` 字段而非嵌入式时间戳 → P1 严重

## 适用场景
- 登录/导出/cookie 注入前需刷新 MTOP `_m_h5_tk` 的场景
- 向无头浏览器/Worker 注入 cookie 后需立即使用的场景
- 闲鱼/类 MTOP 会话令牌体系

## 不适用场景
- 非 MTOP/非会话令牌鉴权
- 注入后不立即发起需鉴权请求（可延后刷新）
- 原生 Playwright context 直接持有有效 cookie
