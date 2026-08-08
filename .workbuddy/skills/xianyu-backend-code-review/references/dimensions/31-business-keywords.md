# 维度 31：业务关键字常量管理

> **编码规范引用**：coding-standards v1.3 §状态关键词覆盖完整 / 模块级常量
> **配置节点**：config.yaml#consistency_and_state_checks.status_keyword_constant

## 触发条件
- 业务文案/状态关键词增删改
- 状态检测函数（`is_sold` / `is_offline` / `is_blocked` 等）
- 前端/后端共享的枚举值或常量
- 错误码/反爬识别关键词

## 检查规则

### 强制（P0 阻塞）
- 业务文案/状态关键词必须提取为模块级常量（`tuple` / `frozenset`），禁止函数内定义或内联
- 多处消费点必须 import 同一常量复用，禁止各自维护
- 跨端（前后端）契约对齐：后端定义的业务关键字枚举值，前端必须同步消费

### 推荐（P1 严重）
- 关键词列表覆盖所有平台文案变体（如 `is_sold` 含"已售/已售出/已售完/已售罄/宝贝已售/卖掉了/已下架/宝贝不存在/已删除"等）
- 关键词常量命名遵循 `UPPER_SNAKE_CASE`，注释说明来源和覆盖范围
- 错误码/反爬识别关键词统一集中在 `anti_crawl_constants.py` 或等价文件中

### 禁止
- 硬编码业务字符串（如直接 `if "已售" in text`）
- 关键词列表在函数内定义
- 前后端各自维护不一致的关键词集合

## Grep 扫描命令

```bash
# 硬编码业务字符串
grep -rn "\"已售\"\|'已售'\|'卖掉了'\|'已下架'\|'宝贝不存在'" src/xianyu_hunter/ --include="*.py"

# 模块级关键词常量
grep -rn "_KEYWORDS\|_TEXTS\|_PATTERNS\|_LIST\s*=\s*(" src/xianyu_hunter/ --include="*.py"

# 跨端关键词对齐
grep -rn "已售\|卖掉了\|已下架" frontend/src/ --include="*.ts" --include="*.tsx"
grep -rn "SOLD\|OFFLINE\|BLOCKED" src/xianyu_hunter/ --include="*.py"
```

## 判断标准
- 业务字符串硬编码 → P0 阻塞
- 关键词列表函数内定义 → P0 阻塞
- 多处消费各自维护关键词 → P1 严重
- 关键词未覆盖完整变体 → P1 严重
- 前后端关键词集合不一致 → P1 严重

## 适用/不适用场景
- **适用**：状态检测（已售/下架/风控）；错误码识别；反爬判断；平台文案匹配
- **不适用**：仅单次使用的简单判断；非业务语义的技术常量（如正则表达式）
