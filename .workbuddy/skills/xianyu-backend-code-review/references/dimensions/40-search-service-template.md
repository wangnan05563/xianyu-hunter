# 维度 40：搜索服务模板方法

> **编码规范引用**：coding-standards v1.3 §2.27 + 规范 19
> **配置节点**：config.yaml#search_service_template

## 触发条件
- `SearchService` 抽象基类或子类实现
- 搜索流程代码（实时搜索/Worker 搜索/历史搜索）
- 搜索钩子方法（`pre_search` / `post_search` / `filter_items` / `sort_items` 等）

## 检查规则

### 强制（P0 阻塞）
- **`SearchService` 抽象基类 5 步流程必须完整**：`validate_input → pre_search → do_search → post_search → format_response`
- **4 个钩子方法契约**：子类必须实现 `_do_search()` 核心方法；`_pre_search()`、`_post_search()`、`_format_response()` 有默认实现，子类可覆盖但不得跳过调用
- **子类不得跳过模板方法步骤**：禁止子类重写 `search()` 方法中跳过 `validate_input` 或 `post_search` 等关键步骤
- 慢查询必须记录日志：搜索耗时超过阈值（如 3 秒）时记录 WARNING 日志含 `elapsed_ms` / `item_count` / `query_params`

### 推荐（P1 严重）
- 钩子方法命名遵循 `_pre_search` / `_do_search` / `_post_search` / `_format_response` 约定
- 模板方法用 `final` 装饰或文档注释标注"禁止覆盖"
- 搜索 timeout 从 `config.yaml` 读取，不硬编码
- 空结果缓存：搜索结果为空时必须缓存，避免反复搜索

### 禁止
- 子类完全重写 `search()` 跳过 5 步流程
- 慢查询无日志（排查困难）
- 钩子方法签名与基类不一致
- 搜索超时阈值硬编码

## Grep 扫描命令

```bash
# SearchService 基类定义
grep -rn "class\s+\w*Search\w*\|class\s+\w*search\w*" src/xianyu_hunter/ --include="*.py"

# 模板方法步骤
grep -rn "def search\|def _pre_search\|def _do_search\|def _post_search\|def _format_response" src/xianyu_hunter/ --include="*.py"

# 慢查询日志
grep -rn "elapsed\|耗时\|slow.*search\|timeout.*search" src/xianyu_hunter/ --include="*.py"

# 超时硬编码
grep -rn "timeout\s*=\s*\d+" src/xianyu_hunter/ --include="*.py" | grep -i search

# 5 步流程跳过检查
grep -rn "def search\(self" src/xianyu_hunter/ --include="*.py" -A 20
```

## 判断标准
- 缺少 5 步流程任一关键步骤 → P0 阻塞
- 子类跳过模板方法步骤 → P0 阻塞
- 慢查询无日志 → P1 严重
- 钩子方法签名不一致 → P1 严重
- 搜索超时硬编码 → P2 改进

## 适用/不适用场景
- **适用**：所有使用 SearchService 模板模式的搜索代码；实时搜索/Worker 搜索子类实现
- **不适用**：非搜索场景的模板方法模式；无需流程标准化的简单查询
