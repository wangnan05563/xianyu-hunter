# SonarQube 问题修复策略指南

## 概述
本文件描述各 SonarQube 规则的修复策略。所有修复必须保持代码功能不变。

## 通用原则
- 只修改必要的部分，不要顺便重构旁边的代码
- 注释解释"为什么"而不是"做什么"
- 修复后确保 TypeScript/Python 语法正确
- 不要添加不必要的错误处理或注释

## Python 规则

### S1481 (unused local variable)
- 场景：`except XxxError as e:` 中 `e` 未使用
- 修复：删除 `as e`，改为 `except XxxError:`
- 如果是其他未使用的局部变量，直接删除赋值

### S125 (commented out code)
- 修复：删除注释掉的代码行
- 保留有意义的注释（用 // 或 # 描述意图的，不是代码）

### S7503 (async without await)
- 场景：函数标记 `async` 但内部无 `await`
- 修复：移除 `async` 关键字
- 注意：如果函数是接口要求（如 FastAPI 路由），可能需要保留 async 并添加 `await asyncio.sleep(0)`

### S5713 (redundant Exception class)
- 场景：`except (Exception, ValueError):` 中 ValueError 是 Exception 子类
- 修复：移除冗余的子类，保留 `except Exception:`

### S1172 (unused function parameter)
- 修复：删除未使用的参数，或重命名为 `_paramname`
- 注意：如果是接口/回调签名要求，用 `_` 前缀

### S107 (too many parameters)
- 场景：函数参数 > 13
- 修复：将相关参数分组为对象参数（dataclass/TypedDict）
- 注意：这是较大重构，需谨慎

### S1066 (merge if statements)
- 场景：`if a: if b: ...` 可合并
- 修复：合并为 `if a and b:`

### S1871 (identical branches)
- 场景：if/else 两个分支实现相同
- 修复：合并分支

### S125 (commented code)
- 修复：删除注释掉的代码

### S3626 (redundant return)
- 修复：删除函数末尾多余的 `return None` 或 `return`

### S5850 (regex precedence)
- 修复：在正则表达式中添加括号明确优先级

### S5857 (reluctant quantifier)
- 修复：`.*?` 在字符类外替换为 `[^]]*` 等

### S3358 (nested ternary in Python)
- 修复：提取为独立变量或 if/else

### S7504 (unnecessary list())
- 场景：`list()` 作用于已是列表的对象
- 修复：移除 `list()` 调用

### S108 (logging only)
- 修复：按规则提示调整

### S5914 / S7483 / S116 / S3457
- 需查看具体代码和规则提示修复

## TypeScript/TSX 规则

### S6759 (mark props as read-only)
- 场景：函数组件 props 未标记为只读
- 修复：在 props 类型定义中添加 `readonly` 到每个属性
- 示例：
  ```tsx
  // 修复前
  function Foo(props: { name: string }) { ... }
  // 修复后
  function Foo(props: { readonly name: string }) { ... }
  ```
- 或用 `Readonly<>` 包装：`function Foo(props: Readonly<{ name: string }>)`
- 如果是 interface，加 `readonly` 到每个字段

### S1481 / S1854 (unused variable / useless assignment)
- 修复：删除未使用的变量
- 如果是 useCallback 包装器未被引用，直接删除

### S3358 (nested ternary)
- 场景：`a ? b : (c ? d : e)`
- 修复：提取为独立变量或在 JSX 外预计算
  ```tsx
  const label = c ? d : e
  return a ? b : label
  ```

### S7764 (prefer globalThis)
- 修复：`window` -> `globalThis`（如果访问 window 自身属性如 innerWidth）
- 或 `window.xxx` -> `globalThis.xxx`

### S6582 (prefer optional chain)
- 场景：`obj && obj.prop`
- 修复：`obj?.prop`

### S1128 (unused import)
- 修复：删除未使用的 import 语句

### S1874 (deprecated API)
- `destroyOnClose` -> `destroyOnHidden`（antd v5）
- `destroyInactiveTabPane` -> `destroyInactiveTabPane`（检查 antd 版本）
- 需查看具体 deprecated 提示

### S6819 (use button instead of role="button")
- 场景：`<div role="button" onClick={...}>`
- 修复：改为 `<button onClick={...}>` 或 `<button type="button" onClick={...}>`
- 注意：保留原有样式（可能需要 `style={{ border: 'none', background: 'none', padding: 0 }}`）

### S6853 (form label must be associated with control)
- 场景：`<label>foo</label>` 没有 `htmlFor`
- 修复：添加 `htmlFor` 关联 Input 的 `id`
- 或用 antd `<Form.Item label="foo">` 自动关联

### S6848 (non-native interactive elements)
- 场景：div/span 带 onClick 但无 role
- 修复：改用 `<button>` 或添加 `role="button"` + `tabIndex={0}` + `onKeyDown`

### S1082 (click handler needs keyboard listener)
- 修复：添加 `onKeyDown` 处理 Enter/Space

### S4624 (nested template literals)
- 场景：`` `${`inner`}` ``
- 修复：提取内层模板为变量

### S4325 (unnecessary assertion)
- 场景：`value as string` 但 value 已是 string 类型
- 修复：删除 `as string`

### S7748 (zero fraction)
- 场景：`1.0` 写成 `1`
- 修复：`1.0` -> `1`

### S7735 (negated condition)
- 场景：`if (!x) { A } else { B }`
- 修复：反转 `if (x) { B } else { A }`

### S6767 (PropType defined but never used)
- 修复：删除未使用的 PropType 定义

### S6479 (Array index in keys)
- 场景：`key={index}`
- 修复：用唯一字段 `key={item.id}` 或 `key={item.name + index}`

### S6478 (component definition inside parent)
- 修复：将内部组件提取到模块级

### S6551 (Object default stringification)
- 场景：`${obj}` 会输出 `[object Object]`
- 修复：`${JSON.stringify(obj)}` 或 `${obj.toString()}`

### S3863 (imported multiple times)
- 修复：合并重复的 import 语句

### S4043 (move sort to separate statement)
- 场景：`arr.sort()` 原地排序在表达式中使用
- 修复：`const sorted = [...arr].sort()` 或用 `arr.toSorted()`

### S2486 (empty catch)
- 修复：添加处理逻辑或 `console.error(e)` 或重新抛出

### S7781 (prefer replaceAll)
- 修复：`.replace()` -> `.replaceAll()`（全局替换场景）

### S7773 (prefer Number.parseInt)
- 修复：`parseInt(x)` -> `Number.parseInt(x)`

### S2681 / S1077 / S107 / S4323 / S6772 / S7770 / S6535 / S7747 / S6754 / S7718 / S7780 / S7784 / S6844 / S6660
- 需查看具体代码和规则提示修复

## 验证方法
- TypeScript：`npx tsc --noEmit -p frontend/tsconfig.json`
- Python：`python -m py_compile <file>`
