# 维度 41：鉴权路径归一化（SPA 子路径部署） 🆕v4.70.0

> **编码规范引用**：xianyu-hunter-dev `references/deployment-runtime-standards.md` 规范 S1 §1.6
> **配置节点**：config.yaml#coding_standards.subpath_deployment
> **测试关联**：xianyu-auto-testing 模式 AL

## 触发条件
- 修改 `web/middleware/auth.py` 的公开白名单 / 401 判定逻辑
- 反向代理为"保留前缀（no-strip）"模式，请求带 `/xianyu` 命名空间前缀
- 新增需要在 `/xianyu/api/*` 与 `/api/*` 下都正确鉴权的端点

## 检查规则

### 强制（P0 阻塞）
- **禁止**把 `/xianyu/` 或 `/xianyu/api/` 整段塞进 `PUBLIC_PREFIXES` 白名单——这会让所有 `/xianyu/api/*` 免鉴权。
- 401 响应必须返回 JSON `{"detail": "Unauthorized"}`，非白名单且无 token 的 `/api/*`（及归一化后的 `/xianyu/api/*`）必须 401。

### 推荐（P1 严重）
- 中间件应在白名单/401 判断**之前**先归一化：`/xianyu/api/X` → `/api/X`，`/xianyu/login` → `/login`，使两套前缀共享同一套白名单与 401 语义。
- 归一化后的 `norm_path` 必须贯穿整个 `dispatch`（含 debug 日志），避免前半段用原始 path、后半段用 norm_path 的不一致。
- 非 `/api/` 前缀且非白名单的未知路径：明确"放行静态资源 / 401 API"的分流逻辑，不静默放行 API。

### 禁止
- `except: pass` 静默吞鉴权异常。
- 用字符串拼接硬编码前缀判断（应读 `config` 或常量）。

## Grep 扫描命令
```bash
# 检测白名单是否误加整段 /xianyu
grep -n "PUBLIC_PREFIXES\|/xianyu" src/xianyu_hunter/web/middleware/auth.py

# 检测是否做了前缀归一化（strip("/xianyu") 或类似）
grep -n "norm_path\|startswith(\"/xianyu\")\|\[7:\]" src/xianyu_hunter/web/middleware/auth.py
```

## 判断标准
- 白名单含 `/xianyu/` 整段 → P0 阻塞
- 未做前缀归一化导致 `/xianyu/api/*` 鉴权语义与 `/api/*` 不一致 → P1 严重
- 归一化后日志/判断仍混用原始 path → P1 严重

## 适用场景
- `web/middleware/auth.py`
- no-strip 反向代理下的所有 API 端点

## 不适用场景
- strip 模式代理（前缀已被代理剥离，后端只见 `/api/*`）：归一化步骤可省略，但白名单正确性仍适用
- 公开静态资源端点：走 SPA catch-all，不进 API 鉴权
