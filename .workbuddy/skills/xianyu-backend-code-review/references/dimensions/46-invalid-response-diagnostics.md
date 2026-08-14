# 维度 46：错误响应诊断契约（禁止 0/空误导）🆕v4.71.0 · B-REVIEW-339

> **编码规范引用**：xianyu-hunter-dev `references/coding-standards-2026-08-13.md` §13 / meta-rule #123
> **配置节点**：config.yaml#api_response_field_ui_alignment（既有）+ config.yaml#invalid_response_diagnostics（新增）
> **测试关联**：xianyu-auto-testing 模式 AJ（健康检查端到端）
> **复盘来源**：retrospective-2026-08-13-login-cookie.md（案例 H/P1 + 流程 P3 + 规范 #123）

## 触发条件
- 构造 invalid/错误/降级响应的代码变更（`cookie_status.py` / `api_anticrawl.py`）
- 前端健康态浮层、Cookie 状态展示的数据来源变更
- 任何对外暴露的状态/健康/诊断接口

## 检查规则

### 强制（P0 阻塞）
- invalid/错误响应必须携带**真实诊断字段**：
  - `cookie_count = len(cookies_list)`
  - `layers_status`（identity/session/tracking 各层命中状态）
  - `security_flags`（安全标记）
  - `key_cookies_found`（命中的关键 cookie 列表）
- **禁止**返回 0/空误导：不得把 invalid 响应的计数/层状态填空或 0，否则用户看到「0 个 cookie / 各层缺失」虚假结论。
- 前端健康态浮层、Cookie 状态展示必须消费真实字段，不得展示硬编码文案。

### 推荐（P1 严重）
- 诊断字段计算逻辑与正常路径一致（同一 `_compute_layers_status` / `_compute_security_flags` 辅助函数），避免 invalid 分支走不同的、缺字段的构造。

### 推荐（P2 改进）
- 诊断字段集中在配置（`config.yaml#invalid_response_diagnostics.required_fields`），新增状态类型时校验字段齐全。

## Grep 扫描命令
```bash
# 检测 invalid 响应是否填真实字段
grep -n "_make_invalid_status\|cookie_count=\|layers_status=" src/xianyu_hunter/web/services/cookie_status.py

# 检测前端是否消费真实字段而非硬编码文案
grep -n "0 个 cookie\|Cookie 异常" frontend/src/pages/**/CookieStatus*.tsx
```

## 判断标准
- invalid 响应 `cookie_count=0` 且 `layers_status` 为空 → P0 阻塞（误导）
- 前端展示硬编码「0 个 cookie」文案 → P0 阻塞
- invalid 分支字段少于正常分支 → P1 严重

## 适用场景
- 任何 invalid/错误/降级响应构造
- 前端健康态展示、Cookie 状态浮层

## 不适用场景
- 正常成功响应（按业务字段返回）
- 纯内部异常（不对外展示）
