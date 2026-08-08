# 维度 3：类型注解

> **编码规范引用**：coding-standards v1.3 §MN-06
> **配置节点**：config.yaml#type_annotations

## 触发条件
- 新增函数/方法定义时
- 函数返回值类型不够明确时
- 使用 `Any` 类型时

## 检查规则

### 强制（P0 阻塞）
- 所有公开函数/方法必须标注参数类型和返回类型
- 使用 Python 3.10+ 语法：`X | None` 而非 `Optional[X]`
- 泛型容器必须标注元素类型：`list[str]` 而非 `list`，`dict[str, int]` 而非 `dict`
- `__init__` 方法必须标注（含 `self` 除外参数的完整标注）

### 推荐（P1 严重）
- 禁止滥用 `Any`，必要时用 `Unknown` + 类型守卫收窄
- 复杂类型使用 `TypeAlias`：`ItemList: TypeAlias = list[ItemDTO]`
- 回调类型使用 `Callable` 标注参数和返回值
- 使用 `TypedDict` 标注字典结构（非 Pydantic 场景）
- 可选参数使用 `str | None = None` 而非 `Optional[str] = None`

### 禁止
- 空类型注解：`def foo(x):`（公开函数禁止）
- `# type: ignore` 无注释说明原因
- 返回类型不一致（如 `-> Item | None | list[Item]`）

## Grep 扫描命令
```bash
# 检测缺少返回类型注解的公开函数
grep -rn "^def [^_].*):$" src/xianyu_hunter/ | grep -v "->" | grep -v "__init__"

# 检测旧式 Optional 用法
grep -rn "Optional\[" src/xianyu_hunter/

# 检测未标注的泛型容器
grep -rn ":\s*list\b" src/xianyu_hunter/ | grep -v "list\["
grep -rn ":\s*dict\b" src/xianyu_hunter/ | grep -v "dict\["

# 检测 Any 滥用（超过阈值）
grep -rn ": Any\b" src/xianyu_hunter/
```

## 判断标准
- 公开函数无返回类型注解：P0 阻塞
- 使用 `Optional[X]` 而非 `X | None`：P1 严重
- 泛型容器未标注元素类型：P1 严重
- Any 使用超过 5 处/文件：P1 严重

## 适用场景
- `src/xianyu_hunter/` 下所有 `.py` 文件
- 新增函数定义时
- mypy/pyright 类型检查配置

## 不适用场景
- 私有函数（`_` 前缀）可适度放宽
- 测试函数（`test_` 前缀，参数标注可省略）
- 与第三方无类型注解库的交互边界
