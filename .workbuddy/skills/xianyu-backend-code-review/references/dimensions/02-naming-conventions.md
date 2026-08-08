# 维度 2：命名规范

> **编码规范引用**：coding-standards v1.3 §MN-04
> **配置节点**：config.yaml#naming_conventions

## 触发条件
- 新增类/函数/模块/变量时
- 代码审查中看到不一致的命名风格时
- 对已有代码做重命名重构时

## 检查规则

### 强制（P0 阻塞）
- 模块文件命名：`snake_case.py`，如 `repo_items.py`、`api_buyer.py`
- 类命名：`PascalCase`，如 `BuyerService`、`ItemRepository`
- 函数/方法命名：`snake_case()`，如 `get_by_id()`、`list_recent()`
- 常量命名：`UPPER_SNAKE_CASE`，如 `MAX_RETRY_COUNT`、`CONFIRM_TOKEN`
- 私有成员：`_` 前缀，如 `_load_all()`、`_redact_keys`
- 布尔值用 `is_`/`has_`/`can_` 前缀：`is_active`、`has_permission`

### 推荐（P1 严重）
- DB ORM 模型类用 `*ORM` 或 `*Row` 后缀：`ItemORM`、`UserRow`
- 配置类用 `*Config` 后缀：`AppConfig`、`EvalConfig`
- DTO 类用 `*DTO` 后缀：`ItemDTO`、`OrderDTO`
- 异常类用 `Error` 后缀：`ItemNotFoundError`、`ConfigError`
- 抽象基类用 `Base` 前缀：`BaseRepository`
- 文案常量提取到模块级常量（SonarQube S1192），禁止重复字面量
- 集合用复数命名：`items`、`users`
- 计数用 `_count` 后缀：`retry_count`、`error_count`

### 禁止
- 缩写命名（除非是公认缩写如 `id`、`url`），禁止 `eval` 替代 `evaluate`
- 魔法词命名：`data`、`info`、`item`（除非确实泛指）
- 拼音命名
- 单词拼写错误

## Grep 扫描命令
```bash
# 检测 PascalCase 类名违规（首字母大写）
grep -rn "^class [a-z]" src/xianyu_hunter/

# 检测 snake_case 函数违规（含大写字母）
grep -rn "^def [A-Z]" src/xianyu_hunter/

# 检测重复字符串字面量（SonarQube S1192）
grep -rn "[\"'][^\"']{10,}[\"']" src/xianyu_hunter/ | sort | uniq -c | sort -rn | head -20
```

## 判断标准
- 模块/类/函数命名不符合规范：P0 阻塞
- 缺少私有前缀：P0 阻塞
- 魔术词命名/拼音：P0 阻塞
- 缺少后缀约定（ORM/Config/DTO/Error）：P1 严重
- 重复字符串字面量未提取：P1 严重

## 适用场景
- 所有 Python 文件中的命名
- 新增文件和类时的命名选择
- 代码审查中命名一致性检查

## 不适用场景
- 第三方库的命名约定（遵循库自身规范）
- 测试文件名（pytest 约定 `test_*.py`）
- 配置键名（YAML 键使用项目特有约定）
