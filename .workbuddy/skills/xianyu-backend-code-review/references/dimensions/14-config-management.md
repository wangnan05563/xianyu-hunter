# 维度 14：配置管理

> **编码规范引用**：coding-standards v1.3 §配置驱动原则
> **配置节点**：config.yaml#（自身）
> **参考文档**：references/yaml-and-config.md

## 触发条件
- 新增可调整参数时（timeout/QPS/TTL/限制值）
- 修改配置文件（config.yaml/other YAML）时
- 发现硬编码常量时

## 检查规则

### 强制（P0 阻塞）
- 所有可变参数必须从 `config.yaml` 读取，禁止模块级硬编码常量（如 `_LIVE_CACHE_TTL = 60`）
- 配置加载使用深度合并（`_deep_merge_yaml`），非 `dict.update()` 浅合并
- 加载顺序：子配置（eval.yaml 等）先加载作基线 → config.yaml 最后加载作覆盖
- 保存配置后必须调用 `reload_config()` 失效 `@lru_cache` 单例

### 推荐（P1 严重）
- 配置缺失时有合理默认值（`Field(default=...)`）
- `extra="ignore"` 保证向后兼容（新增字段不报错）
- 业务约束用 `@model_validator(mode="after")` 校验（如 `pass_score <= auto_buy_score`）
- `*.example.yaml` 模板与配置 schema 同步更新
- 敏感凭据走环境变量/`.env` 而非 YAML

### 禁止
- 硬编码 TTL/QPS/Timeout/limit 等可调参数
- 浅合并（`data.update()`）导致用户修改被默认值覆盖
- 保存后缺少 `reload_config()`（业务模块继续用旧值）
- YAML 中布尔值使用 `"yes"/"no"/"on"/"off"`（显式用 `true/false`）
- YAML 中时间字符串不加引号（`7:00` 解析为整数 420）

## Grep 扫描命令
```bash
# 检测硬编码常量（如 TTL）
grep -rn "=\s*\d+\s*$\|_TTL\|_TIMEOUT\|_LIMIT" src/xianyu_hunter/ | grep -v "config\."

# 检测浅合并
grep -rn "\.update(" src/xianyu_hunter/ --include="*config*"

# 检测 reload_config 缺失（保存后无 reload）
grep -rn "CONFIG_FILE.write\|yaml.safe_dump" src/xianyu_hunter/ -A 5 | grep -v "reload_config"

# 检测 YAML 布尔歧义
grep -rn "yes$\|no$\|on$\|off$" config/
```

## 判断标准
- 硬编码可调参数：P0 阻塞
- 浅合并覆盖用户配置：P0 阻塞
- 保存后缺少 reload：P0 阻塞
- 缺少默认值：P1 严重
- example.yaml 不同步：P1 严重

## 适用场景
- `infra/yaml_config.py` 配置加载
- `web/routes/api_config.py` 配置保存
- 所有需要调整运行时参数的代码
- `config/*.yaml` 文件管理

## 不适用场景
- 纯代码常量（如正则表达式、算法常数）
- Python 枚举值
- Pydantic Field 定义的 `default_factory`（非硬编码）
