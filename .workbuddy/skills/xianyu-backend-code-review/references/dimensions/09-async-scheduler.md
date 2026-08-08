# 维度 9：异步与调度器

> **编码规范引用**：coding-standards v1.3 §外部依赖容错
> **配置节点**：config.yaml#async_scheduler
> **参考文档**：references/async-and-concurrency.md

## 触发条件
- 新增异步函数或后台任务时
- 修改 scheduler 启动/关闭逻辑时
- 添加 QPS 限流或并发控制时

## 检查规则

### 强制（P0 阻塞）
- 异步函数命名使用 `_async` 后缀（如 `fetch_item_async`）
- 所有可能永久挂起的 async API 调用必须用 `asyncio.wait_for(coro, timeout=...)` 包裹（B-REVIEW-226）
- Scheduler 启动必须独立于业务任务条件（不嵌套在 `_scheduler_loop` 内部）
- Scheduler 优雅关闭顺序：先停 scheduler 再停 EventBus
- 调度器异常恢复：捕获 `ResumeBlockedError` 不中断整个循环

### 推荐（P1 严重）
- `asyncio.Semaphore` 控制 QPS，值从 `config.yaml` 读取
- `fire-and-forget` 任务用 `asyncio.ensure_future()` 不等待结果
- Token 预刷新机制（距过期前刷新，避免过期后才触发）
- 子进程心跳与阶段超时协同：阶段内累计超时 < 心跳阈值 × (1 - safety_margin)（B-REVIEW-227）
- 同一 API 的多处调用保护措施必须一致（B-REVIEW-228）

### 禁止
- async 函数中使用同步阻塞调用：`requests.get()`、`time.sleep()`、`open().read()`、`subprocess.run()`
- `threading.Lock` 在 async 上下文中使用（用 `asyncio.Lock`）
- `except Exception: pass` 吞调度器异常
- 串行 `for + await` 替代 `asyncio.gather()` 并发执行

## Grep 扫描命令
```bash
# 检测 async 中的同步阻塞
grep -rn "async def" src/xianyu_hunter/ -A 20 | grep -E "requests\.|time\.sleep|open\(|subprocess\."

# 检测缺少 asyncio.wait_for 的 Playwright API
grep -rnP "await\s+\w+\.(cookies|storage_state|snapshot|title|url|evaluate)\(" src/xianyu_hunter/

# 检测串行 await 模式
grep -rn "for.*in.*:\s*$" src/xianyu_hunter/ -A 1 | grep "await "

# 检测硬编码 QPS
grep -rn "Semaphore(\d+)" src/xianyu_hunter/
```

## 判断标准
- async 中同步阻塞：P0 阻塞
- 无 asyncio.wait_for 保护：P0 阻塞
- scheduler/EventBus 启动顺序错误：P0 阻塞
- 硬编码 Semaphore 值：P1 严重
- 串行可并发化：P1 严重

## 适用场景
- `modules/` 中所有异步业务逻辑
- `web/app.py` 中 lifespan 启动/关闭钩子
- `infra/` 中的 Playwright 异步 API 调用
- 后台 scheduler 相关代码

## 不适用场景
- 同步工具函数（不在 async 上下文中）
- Playwright 自带 timeout 参数的调用（`page.goto(timeout=...)`）
- 一次性调用且失败即终止的场景
