# 维度 13：代码质量

> **编码规范引用**：coding-standards v1.3 §函数内冗余导入
> **配置节点**：config.yaml#code_quality
> **参考文档**：references/maintainability.md

## 触发条件
- 新增函数/方法时
- 代码中出现魔法数字时
- 发现重复代码块时
- SonarQube 扫描报出违规时

## 检查规则

### 强制（P0 阻塞）
- 函数内冗余导入必须移至模块级别（如 `import re`/`threading`/`logging`）
- 禁止魔法数字：阈值、timeout、限制值必须提取为语义常量
- DRY 原则：重复代码块（≥3 行、≥2 次出现）必须提取为函数

### 推荐（P1 严重）
- 函数长度控制在 ≤50 行（SonarQube S138）
- 参数个数控制在 ≤4 个，多了用 dataclass 封装
- 函数单一职责（SRP）：一个函数只做一件事
- 圈复杂度 ≤10：if/for/while 嵌套不超过 3 层
- 类内属性命名全类一致，跨模块引用必须与定义完全一致
- 文案常量提取到模块级（SonarQube S1192）：重复字符串字面量提取为常量

### 禁止
- 注释掉的代码块（应删除）
- 函数内重新导入已导入的模块
- 过长的单行代码（≥120 字符）
- 未使用的 import
- 从外部模块直接访问 `_` 前缀私有属性（B-REVIEW-PRIVATE-ATTR-ENCAPSULATION）

## Grep 扫描命令
```bash
# 检测函数内冗余导入
grep -rn "^def " src/xianyu_hunter/ -A 20 | grep "import "

# 检测魔法数字（非 0/1/-1 的裸数字）
grep -rn "\b[2-9]\d*\b" src/xianyu_hunter/ | grep -v "logger\|line\|assert\|#"

# 检测注释掉的代码
grep -rn "^#\s*(def |class |if |for |return |from |import )" src/xianyu_hunter/

# 检测跨模块私有属性访问
grep -rn "\b(repo|service|manager|client)\._\w+" src/xianyu_hunter/
```

## 判断标准
- 函数内冗余导入：P0 阻塞
- 魔法数字未提取：P0 阻塞
- 重复代码未 DRY：P0 阻塞
- 函数超过 50 行：P1 严重
- 跨模块访问私有属性：P1 严重

## 适用场景
- 所有 Python 文件
- 新增业务逻辑时
- 代码审查中质量检查

## 不适用场景
- 第三方库代码
- 自动生成的代码（如 protobuf）
- 一次性脚本（scripts/ 目录中明确标记）
