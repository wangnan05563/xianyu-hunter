# 维度 30：数据契约与时序

> **编码规范引用**：coding-standards v1.3 §跨边界访问契约 / datetime 时区统一
> **配置节点**：config.yaml#meta_rules_25_30

## 触发条件
- datetime 操作（相减/比较/序列化）
- 跨边界数据传输（DB ↔ 模块 ↔ API 响应 ↔ 前端）
- 异步数据流中的时序保证
- Pydantic 模型序列化/反序列化

## 检查规则

### 强制（P0 阻塞）
- **datetime 相减/比较前统一时区状态**：所有 datetime 操作前必须确认两边都是 naive 或都是 aware，项目约定优先 naive（`_utcnow().replace(tzinfo=None)`）
- **数据契约跨越层时保持一致性**：DB 层（SQLAlchemy）、业务层（Pydantic）、API 层（JSON）字段定义三端对齐

### 推荐（P1 严重）
- 跨进程传递 datetime 使用 ISO 8601 序列化（`datetime.isoformat()`）
- Pydantic 模型 `model_config = dict(use_enum_values=True)` 或在序列化时显式处理枚举值
- 多格式输入解析：格式枚举 + 容错分割 + 无效过滤 + 实时反馈
- 异步操作时序依赖必须用 `await` / `asyncio.gather` 显式保证，不依赖竞态假设

### 禁止
- datetime 混合使用 naive 和 aware 进行算术/比较操作
- 跨进程传递 datetime 对象直接 pickle（进程重启后不兼容）
- config.yaml 值与代码映射表键名不匹配

## Grep 扫描命令

```bash
# datetime 时区状态
grep -rn "\.now()\|utcnow\|datetime\." src/xianyu_hunter/ --include="*.py" | grep -v "tzinfo\|replace.*tz"

# naive/aware 混合操作
grep -rn "timedelta\|- datetime\|\.total_seconds" src/xianyu_hunter/ --include="*.py" -B 2 | grep -v "tzinfo=None"

# ISO 8601 序列化
grep -rn "\.isoformat()\|datetime\.fromisoformat\|\.strftime" src/xianyu_hunter/ --include="*.py"

# Pydantic 序列化配置
grep -rn "model_config\|model_validate\|model_dump" src/xianyu_hunter/ --include="*.py"
```

## 判断标准
- datetime 混合 naive/aware 操作 → P0 阻塞
- 跨层字段定义不对齐（后端字段名 vs 前端 types.ts）→ P0 阻塞
- 跨进程 datetime 未用 ISO 8601 → P1 严重
- Pydantic 枚举值序列化未处理 → P1 严重

## 适用/不适用场景
- **适用**：所有 datetime 操作代码；跨边界数据传递；异步数据流
- **不适用**：纯内存内部运算不对外暴露的 datetime；测试代码中 mock 的 datetime
