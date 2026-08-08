# 维度 32：状态恢复与日志

> **编码规范引用**：coding-standards v1.3 §多层级状态校验必须基于实际存储内容
> **配置节点**：config.yaml#consistency_and_state_checks

## 触发条件
- Cookie/Token 状态恢复逻辑
- 登录/重登录/Token 刷新流程
- 浏览器状态导入导出
- 多层级状态同步（Cookie 文件 ↔ DB ↔ 内存缓存）

## 检查规则

### 强制（P0 阻塞）
- 多层级状态校验必须基于实际存储内容（Cookie 文件/DB 记录），不依赖内存层缓存状态
- 所有状态变更路径（登录成功/Token 刷新/外部导入）必须调用 `sync_state_from_xxx()` 同步方法
- 状态恢复失败必须记录详细日志（含失败原因、当前状态快照）

### 推荐（P1 严重）
- 状态同步方法命名遵循 `sync_state_from_{source}()` 模式（`sync_state_from_cookies` / `sync_state_from_db`）
- 状态同步方法写入主数据源后显式调用 `invalidate_cache()`
- Session Cookie 过期检测必须解析内嵌 timestamp（如 `_m_h5_tk` 的 `{token}_{ts_ms}` 格式），不止看 `expires` 字段
- 跨进程状态变更（如浏览器子进程更新 Cookie）必须主动通知主进程失效缓存

### 禁止
- 依赖内存缓存状态判断 Cookie/Token 有效性
- 状态同步方法只更新内存不持久化（`update_state_memory_only`）
- Session Cookie 过期仅判断 `expires` 字段而不解析内嵌 timestamp

## Grep 扫描命令

```bash
# sync_state_from 同步方法
grep -rn "sync_state_from\|sync.*state" src/xianyu_hunter/ --include="*.py"

# 内存缓存 vs 持久化
grep -rn "_cache\|_cached\|self\._.*_state" src/xianyu_hunter/ --include="*.py" | grep -v "invalidate\|sync\|refresh"

# Session Cookie timestamp 解析
grep -rn "rsplit.*_\|split.*_m_h5_tk\|_m_h5_tk.*timestamp" src/xianyu_hunter/ --include="*.py"

# invalidate_cache 调用
grep -rn "invalidate_cache\|cache.*invalidate" src/xianyu_hunter/ --include="*.py"
```

## 判断标准
- 依赖内存缓存判定状态 → P0 阻塞
- 状态变更路径缺少 `sync_state_from_xxx()` → P0 阻塞
- 状态恢复失败无日志 → P0 阻塞
- Cookie 过期仪仗 `expires` 字段不解析 timestamp → P1 严重
- 跨进程变更未通知失效缓存 → P1 严重

## 适用/不适用场景
- **适用**：登录/认证状态管理；Cookie 分层管理（identity/session/tracking）；多进程 Cookie 同步
- **不适用**：纯内存无持久化的简单状态（如动画状态）；无跨进程需求的单进程应用
