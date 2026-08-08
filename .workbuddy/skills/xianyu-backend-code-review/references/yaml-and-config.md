# YAML 与配置审查（YAML & Config）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **重点**：深度合并 / 加载顺序 / 校验 / 敏感字段

---

## 1. 配置加载架构

```
config/
├── config.yaml          # 主配置（用户运行时可改）
├── eval.yaml            # 评估规则基线
├── notifier.yaml        # 通知配置
├── browser.yaml         # 浏览器配置
├── config.example.yaml  # 主配置模板
└── eval.example.yaml    # 评估配置模板
```

**加载路径**：`src/xianyu_hunter/infra/yaml_config.py` 提供 `get_config()` 单例。

---

## 2. 核心规则

### 2.1 深度合并（CFG-01）

```python
# ❌ 浅合并 → 子配置整体覆盖主配置
data.update(load_yaml("config/config.yaml"))
data.update(load_yaml("config/eval.yaml"))  # 整体覆盖

# ✅ 深度合并
data = {}
for name in ("eval.yaml", "notifier.yaml", "browser.yaml"):
    _deep_merge_yaml(data, load_yaml(name))
_deep_merge_yaml(data, load_yaml("config/config.yaml"))  # 最后覆盖


def _deep_merge_yaml(target: dict, source: dict) -> None:
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge_yaml(target[k], v)
        else:
            target[k] = v
```

**为什么必须深度合并**：
- 浅合并让子配置顶层整体覆盖主配置
- 用户在主配置修改的子字段会丢失
- 案例：抢单策略 `auto_buy_score` 被 `eval.yaml` 默认值覆盖

### 2.2 加载顺序（CFG-02）

**子配置先，主配置后**：

```python
# ✅ 正确顺序
def _load_all() -> AppConfig:
    base = Path("config")
    data: dict[str, Any] = {}

    # 1) 子配置先加载（默认基线）
    for name in ("eval.yaml", "notifier.yaml", "browser.yaml"):
        section_data = load_yaml(base / name)
        if section_data:
            _deep_merge_yaml(data, section_data)

    # 2) 主配置最后加载（用户修改覆盖）
    main_data = load_yaml(base / "config.yaml")
    if main_data:
        _deep_merge_yaml(data, main_data)

    return AppConfig.model_validate(data)
```

**为什么主配置后加载**：
- 用户在 `config.yaml` 的修改应优先于默认基线
- 反过来则用户修改被基线覆盖（Bug 行为）

### 2.3 校验（CFG-03 / CFG-04）

```python
# ✅ 加载后校验
def _load_all() -> AppConfig:
    data = {}
    # ... 合并
    return AppConfig.model_validate(data)  # 校验失败抛 ValidationError
```

```python
# ✅ HTTP 端点捕获校验错误
@router.post("/api/config/save")
async def save_config(payload: dict, dry_run: bool = False):
    try:
        new = AppConfig.model_validate(merged)
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={"message": "配置校验失败，未保存", "errors": e.errors()}
        )
```

### 2.4 reload_config（CFG-05）

```python
# infra/yaml_config.py
@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return _load_all()

def reload_config() -> AppConfig:
    """强制重新加载配置，修改后必须调用。"""
    get_config.cache_clear()
    return _load_all()
```

```python
# web/routes/api_config.py
@router.post("/api/config/save")
async def save_config(payload: dict, dry_run: bool = False):
    # ... 校验和写盘
    if not dry_run:
        CONFIG_FILE.write_text(yaml.safe_dump(new, ...), encoding="utf-8")
        reload_config()  # ✅ 关键：刷新单例
    return {"ok": True, "diffs": [...]}
```

**为什么必须 reload**：
- `@lru_cache` 让 `get_config()` 返回同一对象
- 不 reload 的话，业务模块继续用旧值
- 抢单决策链每次都从 `get_config()` 读，**立即生效**依赖于 reload

---

## 3. 敏感字段保护（CFG-06 / SC-05）

### 3.1 REDACT_KEYS 列表

```python
# web/routes/api_config.py
_REDACT_KEYS = frozenset({
    "serverchan_key", "pushplus_token",
    "bark_key", "bark_server",
    "cookie", "cookies", "session_id"
})

def _redact(d: dict) -> dict:
    """递归脱敏敏感字段。"""
    for k in list(d.keys()):
        if k in _REDACT_KEYS and isinstance(d[k], str) and d[k]:
            d[k] = "***"
        elif isinstance(d[k], dict):
            _redact(d[k])
    return d

@router.get("/api/config")
async def get_config_endpoint():
    return _redact(get_config().model_dump())
```

### 3.2 凭据不写 YAML

```yaml
# config.yaml - 禁止包含凭据
notifier:
  serverchan_key: "sk-1234567890"  # ❌ 错误

# 正确：凭据走 .env
```

```bash
# .env
SERVERCHAN_KEY=sk-1234567890
PUSHPLUS_TOKEN=...
```

```python
# 加载时从 .env 读取
from dotenv import load_dotenv
load_dotenv()

class NotifierConfig(BaseModel):
    serverchan_key: str = Field(default_factory=lambda: os.environ.get("SERVERCHAN_KEY", ""))
```

### 3.3 列表要完整

```python
# ✅ 完整 REDACT_KEYS（不漏字段）
_REDACT_KEYS = frozenset({
    "serverchan_key", "pushplus_token",
    "bark_key", "bark_server",
    "cookie", "cookies", "session_id",
    # 新增敏感字段必须同步加
    "wechat_webhook", "dingtalk_secret",  # 钉钉加签密钥
})
```

---

## 4. 模板同步（CFG-07）

### 4.1 新增字段流程

```
1. Pydantic AppConfig 加字段 + 默认值
2. *.example.yaml 加注释示例
3. 前端 api/types.ts 加类型
4. UI 控件接入
5. 测试覆盖
```

### 4.2 example.yaml 注释

```yaml
# config.example.yaml
server:
  port: 8000  # Web 服务端口
  host: "0.0.0.0"  # 监听地址

buyer:
  # 单日抢单数量上限（0 = 不限）
  max_orders_per_day: 10

  # 自动拍下前的暂停时间（秒），给用户接管机会
  pause_before_payment: 30
```

### 4.3 校验一致性

```python
# 部署脚本中验证 example 和实际配置结构一致
def test_example_yaml_matches_schema():
    example = yaml.safe_load(Path("config/config.example.yaml").read_text())
    schema = AppConfig.model_json_schema()
    example_keys = set(example.keys())
    schema_keys = set(schema["properties"].keys())
    missing = schema_keys - example_keys
    assert not missing, f"example.yaml 缺字段: {missing}"
```

---

## 5. YAML 解析陷阱（CFG-08）

### 5.1 时间字符串

```yaml
# ❌ 7:00 解析为整数 420
quiet_hours:
  start: 7:00
  end: 22:00

# ✅ 引号强制字符串
quiet_hours:
  start: "07:00"
  end: "22:00"
```

### 5.2 布尔歧义

```yaml
# ❌ "no" 在 YAML 1.1 解析为 false（1.2 改为 false）
feature:
  enabled: no

# ✅ 显式布尔
feature:
  enabled: true
```

### 5.3 数字 vs 字符串

```yaml
# ❌ 看起来像数字
version: 1.0  # 解析为字符串 1.0 还是数字 1.0？

# ✅ 显式
version: "1.0"
```

### 5.4 多行字符串

```yaml
# ✅ 用 | 保留换行 / > 折叠换行
description: |
  这是一段
  多行描述

description_folded: >
  这是折叠的
  描述
```

---

## 6. Pydantic 配置（CFG-09 / CFG-10）

### 6.1 extra 策略

```python
class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")  # ✅ 默认

    # 严格模式（拒绝未知字段）
    # model_config = ConfigDict(extra="forbid")
```

**为什么默认 ignore**：
- 向后兼容（旧 YAML 字段不报错）
- 阶段性收紧到 `forbid` 时要同步更新前端可能发送的多余字段

### 6.2 业务约束

```python
class EvalConfig(BaseModel):
    pass_score: int = Field(ge=0, le=100)
    auto_buy_score: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def check_pass_lt_auto_buy(self) -> "EvalConfig":
        if self.pass_score > self.auto_buy_score:
            raise ValueError(
                f"通过分数 pass_score({self.pass_score}) "
                f"不能大于 自动抢单分数 auto_buy_score({self.auto_buy_score})"
            )
        return self
```

### 6.3 字段默认值

```python
# ✅ 显式默认值（避免隐式 None）
class ServerConfig(BaseModel):
    port: int = 8000
    host: str = "0.0.0.0"
    workers: int = 1
```

---

## 7. 保存端点

### 7.1 深度合并（与加载一致）

```python
# web/routes/api_config.py
CONFIG_FILE = Path("config/config.yaml")

def _save_payload(payload: dict, dry_run: bool) -> dict:
    current = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    new = copy.deepcopy(current)

    # ✅ 与 _load_all 用相同的深度合并
    _deep_merge(new, payload)

    # 校验
    try:
        AppConfig.model_validate(new)
    except ValidationError as e:
        raise HTTPException(400, detail={"message": "配置校验失败", "errors": e.errors()})

    # 写盘
    if not dry_run:
        CONFIG_FILE.write_text(
            yaml.safe_dump(new, allow_unicode=True, sort_keys=False),
            encoding="utf-8"
        )
        reload_config()  # ✅ 关键

    return {"ok": True, "diffs": _diff(current, new)}
```

### 7.2 diff 计算

```python
def _diff(old: dict, new: dict, prefix: str = "") -> list[dict]:
    diffs = []
    all_keys = set(old.keys()) | set(new.keys())
    for k in all_keys:
        path = f"{prefix}.{k}" if prefix else k
        old_v = old.get(k)
        new_v = new.get(k)
        if isinstance(old_v, dict) and isinstance(new_v, dict):
            diffs.extend(_diff(old_v, new_v, path))
        elif old_v != new_v:
            op = "add" if old_v is None else "delete" if new_v is None else "modify"
            diffs.append({
                "path": path,
                "op": op,
                "old": str(old_v) if old_v is not None else None,
                "new": str(new_v) if new_v is not None else None,
            })
    return diffs
```

---

## 8. 测试用例

### 8.1 加载顺序

```python
def test_main_config_overrides_eval_yaml(tmp_path, monkeypatch):
    """主配置覆盖子配置。"""
    monkeypatch.chdir(tmp_path)
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()

    # eval.yaml 提供默认值
    (cfg_dir / "eval.yaml").write_text("""
eval:
  pass_score: 60
  auto_buy_score: 80
  weights: {professional: 30, credit: 30, dispute: 25, price: 15}
""", encoding="utf-8")

    # config.yaml 提供用户修改
    (cfg_dir / "config.yaml").write_text("""
eval:
  pass_score: 45
  auto_buy_score: 75
  ai_auto_eval: false
""", encoding="utf-8")

    cfg = get_config()
    assert cfg.eval.pass_score == 45  # config.yaml 覆盖
    assert cfg.eval.auto_buy_score == 75
    assert cfg.eval.weights.professional == 30  # eval.yaml 保留
    assert cfg.eval.ai_auto_eval is False  # config.yaml 独有
```

### 8.2 校验失败

```python
def test_pass_score_gt_auto_buy_should_fail():
    """pass_score > auto_buy_score 应校验失败。"""
    with pytest.raises(ValidationError) as exc:
        EvalConfig(pass_score=90, auto_buy_score=70)
    assert "pass_score" in str(exc.value)
```

### 8.3 敏感字段脱敏

```python
def test_redact_cookies():
    """敏感字段应脱敏。"""
    config = {
        "notifier": {"serverchan_key": "sk-secret"},
        "buyer": {"cookie": "session=xyz"}
    }
    redacted = _redact(config)
    assert redacted["notifier"]["serverchan_key"] == "***"
    assert redacted["buyer"]["cookie"] == "***"
```

---

## 9. 审查 checklist

| 类别 | 检查项 |
|---|---|
| 合并 | 深度合并（非 dict.update）？ |
| 顺序 | 子配置先，主配置后？ |
| 校验 | 加载后 `model_validate`？失败转 HTTPException？ |
| reload | 保存后 `reload_config()`？ |
| 敏感 | `_REDACT_KEYS` 完整？递归脱敏？ |
| 模板 | `*.example.yaml` 与 `*.yaml` 同步？ |
| 解析 | 时间字符串加引号？布尔显式？ |
| 约束 | 业务约束用 `@model_validator`？ |
| 测试 | 加载顺序？校验失败？脱敏？ |

---

## 10. 复盘：从对话中提炼

### 10.1 案例：抢单策略 Bug 完整链路

```
用户操作：修改 auto_buy_score = 75 → 保存
    ↓
前端：POST /api/config/save {payload, dry_run: true}
    ↓
后端 api_config.py：
  - 读 config.yaml 当前内容
  - 深度合并 payload（不是 dict.update）
  - 校验 AppConfig（pass_score <= auto_buy_score）
  - 返回 diffs
    ↓
前端显示 diff 预览
    ↓
用户确认 → POST /api/config/save {payload, dry_run: false}
    ↓
后端：写 config.yaml + reload_config()
    ↓
前端 GET /api/config → 新的 75
    ↓
刷新页面：BuyerStrategy 组件从 useConfigStore 拿值 → 显示 75
```

**关键修复点**：
1. `_load_all` 颠倒顺序 + 深度合并（`yaml_config.py`）
2. `_save_payload` 同样深度合并（`api_config.py`）
3. 保存后 `reload_config()` 失效 lru_cache

### 10.2 复盘经验

| 经验 | 说明 |
|---|---|
| **加载端 / 保存端必须用相同合并** | 否则保存成功但下次加载值不同 |
| **加注释解释 why** | 避免后人"优化"成浅合并回归 Bug |
| **写回归测试** | `test_main_config_overrides_eval_yaml` 防止再次出现 |
| **reload 是关键** | 缺了它所有实时生效的承诺都失效 |

---

## 11. 参考

- [Pydantic 文档](https://docs.pydantic.dev/)
- [PyYAML 文档](https://pyyaml.org/wiki/PyYAMLDocumentation)
- [项目 YAML 加载专题](../../xianyu-hunter-dev/references/yaml-config-patterns.md)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)
