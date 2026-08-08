# YAML 配置加载踩坑模式（YAML Config Patterns）

> **来源**：从"抢单策略页面参数保存后刷新重置为默认值"Bug 修复中提炼
> **适用场景**：项目内任何涉及 `config/*.yaml` 加载、合并、持久化的修改

---

## 一、问题原型

**用户报告**：
> 修改"抢单策略"页面（`/app/config/buyer`）的 `auto_buy_score` 从 80 改为 75 → 点击保存 → 看到"保存成功" → 刷新页面 → 数值回到 80。

**根因**：
1. 加载顺序错误：`config.yaml` 先加载，`eval.yaml` 后加载用 `data.update()` 浅合并
2. `data.update(eval_yaml)` 让 eval.yaml 顶层**整体覆盖**了 config.yaml 中的 `eval` 块
3. 用户修改的 `auto_buy_score` 被丢弃

---

## 二、修复方案

### 2.1 颠倒加载顺序

```python
# ✅ 正确顺序：子配置先加载（默认基线），主配置后加载（用户修改覆盖）
def _load_all() -> AppConfig:
    base = Path("config")
    data: dict[str, Any] = {}

    # 1) 子配置作为默认基线
    for name in ("eval.yaml", "notifier.yaml", "browser.yaml"):
        section_data = load_yaml(base / name)
        if section_data:
            _deep_merge_yaml(data, section_data)

    # 2) 主配置最后加载（用户修改）
    main_data = load_yaml(base / "config.yaml")
    if main_data:
        _deep_merge_yaml(data, main_data)

    return AppConfig.model_validate(data)
```

### 2.2 改用深度合并

```python
def _deep_merge_yaml(target: dict, source: dict) -> None:
    """source 的细分字段覆盖 target 同名字段，不整体替换。"""
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge_yaml(target[k], v)
        else:
            target[k] = v
```

### 2.3 关键差异对比

| 场景 | 浅合并（Bug） | 深度合并（修复） |
|---|---|---|
| eval.yaml 覆盖 config.yaml 的 eval 子字段 | ❌ 整体被替换 | ✅ 细分字段被覆盖 |
| config.yaml 独有的 `ai_auto_eval` | ❌ 被 eval.yaml 整体替换时丢失 | ✅ 保留 |
| eval.yaml 独有的字段（如历史遗留） | ✅ 保留 | ✅ 保留 |

---

## 三、API 端点保存的合并逻辑

`api_config.py` 的保存路径必须用相同的深度合并逻辑：

```python
def _save_payload(payload: dict, dry_run: bool) -> dict:
    CONFIG_FILE = Path("config/config.yaml")
    current = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    new = copy.deepcopy(current)

    # 同样的深度合并（必须与 _load_all 一致）
    _deep_merge(new, payload)

    # 校验 + 写盘
    AppConfig.model_validate(new)
    if not dry_run:
        CONFIG_FILE.write_text(yaml.safe_dump(new, ...), encoding="utf-8")
        reload_config()

    return {"ok": True, "diffs": _diff(current, new)}
```

**关键**：保存端和加载端必须用**同一份合并逻辑**。否则可能出现"保存成功但下次加载值不一样"。

---

## 四、配置修改的标准流程

### 4.1 用户修改字段 → API 保存

```
前端 GET /api/config
  → 后端 get_config() → AppConfig.model_dump() → 序列化（_redact 处理敏感字段）
前端修改 auto_buy_score = 75
前端 POST /api/config/save {payload, dry_run: true}
  → 后端：深度合并 payload 到 config.yaml 当前内容
  → 校验 AppConfig（model_validator：pass_score <= auto_buy_score）
  → 返回 diffs
前端显示预览 → 用户确认 → POST /api/config/save {payload, dry_run: false}
  → 写 config.yaml + reload_config()
前端 GET /api/config
  → 新的 75 值返回
```

### 4.2 验证清单

- [ ] 修改字段后能保存（dry_run 返回 diff）
- [ ] 确认保存后实际写入 config.yaml
- [ ] reload_config() 后 get_config() 返回新值
- [ ] **前端刷新页面后**字段保持新值（不止 API 返回）
- [ ] 其他字段不受影响（深度合并的副作用）
- [ ] eval.yaml 默认值字段不被覆盖（除非用户在 config.yaml 也改了）

---

## 五、测试用例

```python
def test_main_config_overrides_eval_yaml(tmp_path, monkeypatch):
    """主配置的 eval 字段应优先于子配置 eval.yaml。"""
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

    # config.yaml 提供用户修改后的值
    (cfg_dir / "config.yaml").write_text("""
eval:
  pass_score: 45
  auto_buy_score: 75
  ai_auto_eval: false
""", encoding="utf-8")

    reload_config()
    cfg = get_config()

    # 关键断言：主配置覆盖子配置
    assert cfg.eval.pass_score == 45
    assert cfg.eval.auto_buy_score == 75
    # eval.yaml 独有字段保留（深度合并而非整体替换）
    assert cfg.eval.weights.professional == 30
    # config.yaml 独有字段保留
    assert cfg.eval.ai_auto_eval is False
```

---

## 六、易踩的二级坑

### 6.1 YAML 解析陷阱

```yaml
# ❌ 7:00 会被解析为整数 420（YAML 1.1 标准时间语法）
quiet_hours:
  end: 07:00

# ✅ 强制字符串
quiet_hours:
  end: "07:00"
```

### 6.2 Pydantic extra 字段

默认 Pydantic v2 **允许**未声明字段。如果 `AppConfig` 严格模式（`extra="forbid"`），保存时会拒绝未声明字段。

**建议**：
- 默认 `extra="ignore"`（向后兼容）
- 阶段性收紧为 `extra="forbid"` 时要同步更新前端可能发送的多余字段

### 6.3 校验失败时的错误传播

```python
# ❌ 异常被吞
try:
    AppConfig.model_validate(new)
except ValidationError:
    return {"ok": False}  # 错误细节丢失

# ✅ 返回结构化错误
try:
    AppConfig.model_validate(new)
except ValidationError as e:
    raise HTTPException(
        status_code=400,
        detail={"message": "配置校验失败，未保存", "errors": e.errors()}
    )
```

---

## 七、检查清单（自检）

修改配置加载/保存代码后：

- [ ] `_load_all` 的子配置顺序在主配置之前
- [ ] 使用 `_deep_merge_yaml` 而非 `data.update`
- [ ] 保存端也用深度合并
- [ ] 保存后调用 `reload_config()` 让单例刷新
- [ ] 校验失败返回 `detail.message` + `detail.errors`
- [ ] 写了回归测试 `test_main_config_overrides_eval_yaml`
- [ ] 手动验证：保存 → 刷新页面 → 值不变

---

## 八、相关文件

- `src/xianyu_hunter/infra/yaml_config.py` —— 加载 + 合并 + AppConfig
- `src/xianyu_hunter/web/routes/api_config.py` —— 保存端点
- `config/config.yaml` + `config/eval.yaml` —— 配置文件
- `tests/test_yaml_config.py` —— 单元测试
- `frontend/src/stores/configStore.ts` —— 前端保存逻辑
- `frontend/src/pages/Config/BuyerStrategy.tsx` —— 抢单策略 UI