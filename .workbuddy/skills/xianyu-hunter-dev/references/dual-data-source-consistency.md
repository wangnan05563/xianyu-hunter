# 编码规范：双数据源一致性保障（Dual Data Source Consistency）

> **规范编号**：CSR-014
> **引入版本**：v4.69.0
> **关联复盘**：[retrospective-2026-07-26-r3.md](retrospective-2026-07-26-r3.md)
> **关联检查点**：B-REVIEW-332 / B-REVIEW-333 / B-REVIEW-334 / F-REVIEW-245
> **关联测试场景**：T005 / T006 / T007
> **状态**：experimental → 待生产验证后转 stable

---

## 1. 问题模式

当系统存在"持久化层 + 运行时层"双数据源时，若检查器（健康检查/状态查询）只读持久化层，而消费者（业务流程）读运行时层，会产生"检查器判定无效但功能正常"的矛盾现象。

### 典型案例

| 数据源 | 检查器 | 消费者 |
|--------|--------|--------|
| Cookie JSON 文件 | 健康检查 `cookie_checker` | - |
| 浏览器运行时内存 | - | 实时搜索 `_ensure_live_search_cookies` |

矛盾现象：健康检查显示 cookie 无效，但实时搜索仍能正常查询商品。

### 根因

1. 运行时层更新后未回写持久化层（回写失败被静默吞掉）
2. 回写只覆盖部分字段（如只回写 6 个关键 cookie，其他 cookie 仅在运行时层更新）
3. 持久化层有 TTL 缓存，落后于运行时层
4. 检查器与消费者判定标准不一致（检查范围、过期判断逻辑）

---

## 2. 保障流程

### 流程 14：双数据源一致性保障

```
1. 识别双数据源
   - 持久化层：JSON/DB/文件（如 data/cookies.json）
   - 运行时层：内存/缓存/浏览器上下文（如 container.browser._context）
   - 若两者会被不同消费者读取，进入本流程

2. 检查器兜底复核
   - 检查器以持久化层为主源判定
   - 主源判定无效时，必须回退运行时层兜底复核
   - 以运行时层为最终判定标准（因为它是实际消费者使用的数据源）

3. 同步机制
   - 运行时层更新后必须回写持久化层
   - 回写失败必须 warning 级别日志（可观测）
   - 回写范围应覆盖检查器依赖的关键字段

4. 检查器与消费者判定标准对齐
   - 检查器的检查范围必须与实际消费者依赖范围一致
   - 不应检查消费者不依赖的字段（避免误判）
   - 不应只检查消费者依赖字段的子集（避免漏判）

5. 检查器接口 async 兼容
   - 检查器接口支持 sync 和 async 两种实现
   - 调用方用 inspect.isawaitable(result) 兼容处理
   - 类型签名：Callable[[], bool | Awaitable[bool]]
```

### 流程 15：异常可观测性分级

| 异常类型 | 日志级别 | 理由 |
|---------|---------|------|
| 回写/同步失败 | warning | 影响数据一致性，需排查 |
| 配置缺失/解析失败 | warning | 影响功能可用性 |
| 查询失败（不影响主流程） | debug | 避免噪音，有 fallback 兜底 |
| 兜底路径触发 | info | 标记走了非主路径，便于统计 |
| 关键路径失败 | error | 需立即处理 |

**反模式**：所有 except 分支统一用 `debug` 静默吞掉——导致问题不可观测，排查困难。

### 流程 16：检查器接口异步兼容

```python
# 检查器接口类型签名
self._cookie_checker: Callable[[], bool | Awaitable[bool]] | None = None

# 调用方兼容处理
async def _check_cookies(self) -> bool:
    if not self._cookie_checker:
        return True
    try:
        result = self._cookie_checker()
        # 兼容 async 检查器：浏览器内存兜底等场景需要异步读取
        if inspect.isawaitable(result):
            result = await result
        return result
    except Exception as e:
        logger.error("Cookie 检查异常: %s", e)
        return False
```

---

## 3. 实现模式

### 模式 AH：检查器浏览器内存兜底

```python
async def cookie_checker() -> bool:
    """检查器主逻辑：先读 JSON，无效时浏览器内存兜底"""
    # 1. 读持久化层（JSON）
    store = get_cookie_store()
    data = store._read_json()
    
    # 2. JSON 无效时，尝试从运行时层同步最新 token 回写 JSON
    if not _has_valid_token(data):
        refreshed = await _try_refresh_m5tk_from_browser(store)
        if refreshed:
            data = store._read_json()  # 重新读
    
    # 3. JSON 仍无效时，浏览器内存兜底复核
    if not _is_valid(data):
        return await _browser_cookies_fallback()
    
    # 4. JSON 有效时，正常判定
    return _validate_cookies(data)


async def _try_refresh_m5tk_from_browser(store) -> bool:
    """从浏览器内存读取最新 token 回写 JSON（被动同步，不触发主页导航）"""
    cookies = await container.browser.get_cookies()
    updates = {c["name"]: c["value"] for c in cookies 
               if c["name"] in {"_m_h5_tk", "_m_h5_tk_enc"} and c.get("value")}
    if not updates:
        return False
    return store.update_cookie_values(updates)


async def _browser_cookies_fallback() -> bool:
    """JSON 判定无效时的浏览器内存兜底复核，判定标准与消费者对齐"""
    cookies = await container.browser.get_cookies()
    # 判定标准与 _ensure_live_search_cookies 对齐
    has_token = any(c["name"] == "_m_h5_tk" and not is_m5tk_expired(c["value"]) for c in cookies)
    has_identity = bool(IDENTITY_COOKIES & {c["name"] for c in cookies})
    return has_token and has_identity
```

### 模式 AI：回写失败可观测

```python
# 反模式：静默吞掉
try:
    store.update_cookie_values(updates)
except Exception as e:
    logger.debug("回写失败: {}", e)  # 不可观测！

# 正确模式：warning 级别
try:
    store.update_cookie_values(updates)
except Exception as e:
    # 为什么 warning：回写失败会导致 JSON 中 token 陈旧，下次健康检查误判
    logger.warning("MTOP Set-Cookie 回写 JSON 失败: {}", e)
```

---

## 4. 适用场景

| 场景 | 适用流程 | 说明 |
|------|---------|------|
| Cookie JSON + 浏览器内存 | 流程 14 | 本案直接应用 |
| DB + Redis 缓存 | 流程 14 | 检查器读 DB，消费者读缓存，需缓存兜底 |
| 文件 + 内存映射 | 流程 14 | 检查器读文件，消费者读内存 |
| 所有 except 分支 | 流程 15 | 通用规范 |
| 检查器访问浏览器/HTTP/异步DB | 流程 16 | async 兼容 |

## 5. 不适用场景

| 场景 | 不适用流程 | 理由 |
|------|----------|------|
| 单一数据源 | 流程 14 | 无需兜底 |
| 检查器与消费者同源 | 流程 14 | 不存在不一致 |
| 强一致性要求 | 流程 14 | 应使用事务而非兜底 |
| 纯同步检查器 | 流程 16 | 无需 async 兼容复杂度 |

---

## 6. 验证清单

实现双数据源一致性保障时，需验证以下要点：

- [ ] 检查器读持久化层判定无效时，是否回退运行时层兜底复核？
- [ ] 运行时层更新后是否回写持久化层？
- [ ] 回写失败的 except 分支是否使用 warning 级别日志？
- [ ] 检查器的检查范围是否与实际消费者依赖范围一致？
- [ ] 检查器接口是否支持 async 实现（`inspect.isawaitable` 兼容）？
- [ ] 兜底复核的判定标准是否与消费者实际使用的判定标准对齐？
- [ ] 是否有端到端测试覆盖"JSON 无效 + 运行时层有效 → 检查器通过"场景？

---

## 7. 关联

- **复盘**：[retrospective-2026-07-26-r3.md](retrospective-2026-07-26-r3.md)
- **后端检查点**：B-REVIEW-332 / B-REVIEW-333 / B-REVIEW-334
- **前端检查点**：F-REVIEW-245
- **测试场景**：T005 / T006 / T007
- **既有相关**：
  - B-REVIEW-134 多源失效判定一致性（泛化版本，本案为具体应用）
  - B-REVIEW-135 缺失数据回退策略（泛化版本）
  - B-REVIEW-136 多源状态同步标记机制（泛化版本）
  - [cookie-state-recovery-patterns.md](cookie-state-recovery-patterns.md) Cookie 状态恢复模式
  - [data-consistency-patterns.md](data-consistency-patterns.md) 数据一致性模式
