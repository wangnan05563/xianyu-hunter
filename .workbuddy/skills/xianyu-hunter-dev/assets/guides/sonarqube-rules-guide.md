# SonarQube 规则速查与修复模式

> 本文档基于闲鱼猎人项目 SonarQube 修复实战（411 个问题修复至 523 个，按规则+严重级别分类）提炼而成，作为开发阶段的**预防手册**和 code review 阶段的**对照速查表**。所有规则均已落地为代码模板，配套实战案例可直接复用。

---

## 目录

- [一、规则总览（16+ 条）](#一规则总览16-条)
- [二、Python 规则详解](#二python-规则详解)
- [三、TypeScript 规则详解](#三typescript-规则详解)
- [四、复盘总结](#四复盘总结)
- [五、规则速查对照表](#五规则速查对照表)

---

## 一、规则总览（16+ 条）

| 规则 ID | 语言 | 类型 | 严重度 | 名称 | 文档 |
|--------|------|------|--------|------|------|
| **S3776** | Python/TS | 认知复杂度 | CRITICAL | 认知复杂度过高 | [§2.1](#21-s3776-认知复杂度) / [§3.1](#31-s3776-认知复杂度) |
| **S2004** | TS | 嵌套层级 | CRITICAL | 函数嵌套层级过深 | [§3.2](#32-s2004-嵌套层级) |
| **S3358** | TS | 三元复杂度 | MAJOR | 嵌套三元表达式 | [§3.3](#33-s3358-三元复杂度) |
| **S6757** | TS | 类设计 | MAJOR | SFC 内使用 `this` | [§3.4](#34-s6757-sfc-内-this) |
| **S7784** | TS | 深拷贝 | MAJOR | 用 `JSON.parse(JSON.stringify())` | [§3.5](#35-s7784-深拷贝) |
| **S6848** | TS | 可访问性 | MAJOR | 可点击元素缺键盘事件 | [§3.6](#36-s6848-键盘可访问性) |
| **S6819** | TS | 可访问性 | MAJOR | 用 anchor 替代 button | [§3.7](#37-s6819-anchor-替代-button) |
| **S6844** | TS | 可访问性 | MAJOR | 用 div 替代 button | [§3.8](#38-s6844-div-替代-button) |
| **S1128** | TS/Python | 死代码 | MINOR | 未使用的 import | [§3.9](#39-s1128-未使用-import) |
| **S4325** | TS | 类型断言 | MINOR | 不必要的类型断言 | [§3.10](#310-s4325-类型断言) |
| **S7503** | Python/TS | 异步规范 | MAJOR | 不必要的 `async` 函数 | [§2.2](#22-s7503-不必要的-async) |
| **S6767** | TS/Python | 死代码 | MAJOR | 未使用的参数/属性 | [§3.11](#311-s6767-未使用参数) / [§2.3](#23-s6767-未使用参数) |
| **S7744** | TS | 类型转换 | MAJOR | 不必要的类型转换 | [§3.12](#312-s7744-类型转换) |
| **S6582** | TS | 可选链 | MINOR | 冗余可选链 | [§3.13](#313-s6582-冗余可选链) |
| **S7735** | TS | Hooks | MAJOR | useEffect 缺少依赖 | [§3.14](#314-s7735-useeffect-依赖) |
| **S6551** | TS | 迭代 | MAJOR | `for...in` 遍历对象 | [§3.15](#315-s6551-for-in) |
| **S1874** | TS | 弃用标记 | MINOR | 缺少 `@deprecated` | [§3.16](#316-s1874-deprecated) |
| **S1192** | Python | 重复字符串 | MINOR | 重复字符串字面量 | [§2.4](#24-s1192-重复字符串) |
| **S1481** | Python | 死代码 | MINOR | 未使用 import（框架误报） | [§2.5](#25-s1481-未使用-import) |
| **S2949** | Python | 默认参数 | MAJOR | 可变默认参数（框架误报） | [§2.6](#26-s2949-可变默认参数) |
| **S3508** | Python | 死代码 | MINOR | 未使用局部变量 | [§2.7](#27-s3508-未使用局部变量) |
| **S5843** | Python | 正则 | MAJOR | 复杂正则 | [§2.8](#28-s5843-正则复杂度) |

---

## 二、Python 规则详解

### 2.1 S3776 认知复杂度

**阈值**：单函数认知复杂度 ≤ 15。

**根因**：函数承担过多职责，包含多个分支、嵌套循环、异常处理、回调函数等。

**修复模式**：
1. **早返回（early return）**：用 `if not condition: return` 替代嵌套 `if`
2. **提取模块级函数**：将内层逻辑提到模块级，函数内仅做编排
3. **拆分场景**：用 dispatch table（字典映射 handler）替代 if-elif 链
4. **提取谓词函数**：复杂条件（`a and b and not c`）拆为 `is_<scenario>()` 函数

**实战案例**：

```python
# ❌ 修复前：login_orchestrator.start_session 认知复杂度 > 20
async def start_session(self, ...):
    if not self._validate(...):
        raise ValueError(...)
    if self._is_running:
        ...
    async with self._browser_lock:
        ...
    try:
        await self._navigate(...)
    except TimeoutError:
        ...
    # ... 嵌套 6+ 层
```

```python
# ✅ 修复后：拆分为 7 个小方法
async def start_session(self, ...):
    """主流程：编排 7 步"""
    self._validate_session(...)
    if not self._acquire_browser():
        return False
    try:
        await self._navigate_login()
        await self._wait_for_qrcode()
        await self._poll_session_status()
        self._update_token_store()
        self._emit_started_event()
        return True
    except Exception:
        self._emit_failed_event()
        return False

def _validate_session(self, ...): ...
def _acquire_browser(self) -> bool: ...
async def _navigate_login(self): ...
async def _wait_for_qrcode(self): ...
async def _poll_session_status(self): ...
def _update_token_store(self): ...
def _emit_started_event(self): ...
def _emit_failed_event(self): ...
```

**复用模板**：
```python
def method_with_complex_logic(self, params):
    """主方法：纯编排，认知复杂度低"""
    self._validate_inputs(params)
    if not self._check_preconditions():
        return self._handle_precondition_failed()
    try:
        result = self._do_main_work(params)
        self._update_state(result)
        return self._build_success_response(result)
    except SpecificError as e:
        return self._handle_specific_error(e)
    except Exception as e:
        return self._handle_unexpected_error(e)
```

### 2.2 S7503 不必要的 `async`

**阈值**：`async def` 函数体内无 `await` 表达式。

**根因**：开发者误用 `async`（如为了统一接口），但函数实际只调用同步方法。

**修复模式**：
1. 移除 `async` 关键字，改为同步 `def`
2. 检查所有调用方：移除 `await`
3. 如果函数是回调/接口契约要求 `async`，需明确注释"接口要求，实际同步执行"

**实战案例**：

```python
# ❌ 修复前：scheduler.start_all 是 async 但无 await
async def start_all(self):
    self._scheduler.start()  # APScheduler.start() 是同步的
    self._register_jobs()     # 同步方法
    logger.info("调度器已启动")
```

```python
# ✅ 修复后：改为同步
def start_all(self):
    self._scheduler.start()
    self._register_jobs()
    logger.info("调度器已启动")
```

**判断标准**：
- 函数体内**完全没有** `await` → 改同步
- 函数体内有 `await` 但**全部**是同步方法 → 改同步
- 函数体内有 `await` 且调用了**真异步**方法（`asyncio.sleep`、`httpx`、其他 `async def`）→ 保留 `async`

### 2.3 S6767 未使用参数

**阈值**：方法签名中的参数从未在函数体内被使用。

**修复模式**：
1. **删除参数**：如果调用方都不传
2. **用 `_` 前缀**：明确"故意忽略"（如解构时）
3. **添加使用**：如果业务上需要，记录到日志或状态

**实战案例**：

```python
# ❌ 修复前：ThumbnailTab 定义了 onActivate 但从未使用
function ThumbnailTab({ sheet, onActivate }: ThumbnailTabProps) {
    return <div onClick={...}>{...}</div>  // onActivate 从未调用
}

# ✅ 修复后：删除未使用参数
function ThumbnailTab({ sheet }: ThumbnailTabProps) {
    return <div onClick={...}>{...}</div>
}
```

### 2.4 S1192 重复字符串

**阈值**：相同字符串字面量在文件中出现 ≥ 2 次。

**修复模式**：
1. **模块级常量**：`_TASK_NOT_FOUND = "任务不存在"`
2. **类级常量**：`class _Constants: TASK_NOT_FOUND = "..."`
3. **配置项**：动态文案（错误信息、用户提示）移到 `config.py` 或 i18n 文件

**实战案例**：

```python
# ❌ 修复前
def get_task(task_id: str) -> dict:
    task = repo.get_task(task_id)
    if not task:
        raise ValueError("任务不存在")
    return task

def pause_task(task_id: str) -> None:
    task = repo.get_task(task_id)
    if not task:
        raise ValueError("任务不存在")
    repo.update_task_status(task_id, "paused")

# ✅ 修复后
_TASK_NOT_FOUND = "任务不存在"

def get_task(task_id: str) -> dict:
    task = repo.get_task(task_id)
    if not task:
        raise ValueError(_TASK_NOT_FOUND)
    return task

def pause_task(task_id: str) -> None:
    task = repo.get_task(task_id)
    if not task:
        raise ValueError(_TASK_NOT_FOUND)
    repo.update_task_status(task_id, "paused")
```

### 2.5 S1481 未使用 import（框架误报）

**误报场景**：FastAPI 装饰器导入的符号在静态分析中显示为未使用。

**豁免规则**：
- `@app.get()`/`@router.post()` 注册的路由处理函数 → 豁免
- Pydantic 模型作为类型注解使用 → 豁免
- `Depends()`/`Auth` 依赖 → 豁免

**修复模式**：
- 确认豁免：在文件顶部加注释 `Xianyu 框架误报：FastAPI 装饰器模式，导入的符号在运行时通过反射调用`
- 不豁免：直接删除未使用 import

### 2.6 S2949 可变默认参数（框架误报）

**误报场景**：`Depends()`/`Body()`/`Query()`/`Path()` 作为默认值。

**修复模式**：
- `Depends(...)` 作为默认值 → 豁免（依赖注入器）
- `[]`/`{}`/`set()` 作为默认值 → 不豁免，改 `None` + 函数内初始化

```python
# ✅ 推荐
def get_items(items: list[str] = None) -> list[str]:
    if items is None:
        items = []
    return items

# ❌ 应修复
def get_items(items: list[str] = []) -> list[str]:  # 经典可变默认参数陷阱
    items.append("default")
    return items
```

### 2.7 S3508 未使用局部变量

**阈值**：局部变量赋值后从未被读取。

**修复模式**：
1. **删除赋值**：如果不需要变量
2. **用 `_` 前缀**：解构时跳过（`for _ in range(10)`）
3. **添加使用**：如果业务上需要但遗漏

### 2.8 S5843 正则复杂度

**阈值**：正则表达式嵌套/分支过多，可读性差。

**修复模式**：
1. **拆分多个简单正则**：每个正则匹配单一模式
2. **改用字符串方法**：能用 `str.startswith/endswith/contains` 就别用正则
3. **re.VERBOSE 模式**：复杂正则加注释

**实战案例**：

```python
# ❌ 修复前：单行 100+ 字符的正则
_URL_RE = re.compile(r"https?://[a-zA-Z0-9.-]+\.(?:com|cn|org|net|io|dev)(?:/[^\s]*)?\??[^\s]*")

# ✅ 修复后：拆分 + VERBOSE
_DOMAIN_RE = re.compile(r"[a-zA-Z0-9.-]+\.(?:com|cn|org|net|io|dev)")
_PATH_RE = re.compile(r"/[^\s?#]*")
_QUERY_RE = re.compile(r"\?[^\s#]*")

def extract_url_components(url: str) -> dict:
    domain_match = _DOMAIN_RE.search(url)
    path_match = _PATH_RE.search(url)
    query_match = _QUERY_RE.search(url)
    return {
        "domain": domain_match.group() if domain_match else None,
        "path": path_match.group() if path_match else None,
        "query": query_match.group() if query_match else None,
    }
```

---

## 三、TypeScript 规则详解

### 3.1 S3776 认知复杂度

**阈值**：单函数认知复杂度 ≤ 15。

**修复模式**：与 Python 相同（早返回、提取模块级、dispatch table、谓词函数）。

**实战案例**：

```typescript
// ❌ 修复前：Evaluations/index.tsx 内联 resolveAction 嵌套 4 层 + 复杂度 18
function getActionDisplay(item: EvalItem): ActionDisplay {
  if (item.payload?.is_sold) {
    return { text: '已售', type: 'sold' }
  } else if (item.payload?.order_status === 'ordered') {
    if (item.payload.is_sold) {
      return { text: '已下单已售', type: 'ordered-and-sold' }
    }
    return { text: '已下单', type: 'ordered' }
  } else if (item.canGrab) {
    return { text: '手动抢单', type: 'grab' }
  } else {
    return { text: '—', type: 'placeholder' }
  }
}

// ✅ 修复后：纯函数 + 常量分层
// 1. 常量
export const ACTION_PLACEHOLDER_TEXT: Record<ActionType, string> = {
  sold: '已售',
  ordered: '已下单',
  'ordered-and-sold': '已下单已售',
  grab: '手动抢单',
  placeholder: '—',
}

// 2. 纯函数（可单元测试）
export function resolveActionDisplay(item: EvalItem): ActionDisplay {
  if (item.payload?.is_sold && item.payload?.order_status === 'ordered') {
    return { type: 'ordered-and-sold' }
  }
  if (item.payload?.is_sold) return { type: 'sold' }
  if (item.payload?.order_status === 'ordered') return { type: 'ordered' }
  if (item.canGrab) return { type: 'grab' }
  return { type: 'placeholder' }
}

// 3. 组件
function ActionPlaceholder({ type }: { type: ActionType }) {
  return <Tag color={ACTION_COLOR[type]}>{ACTION_PLACEHOLDER_TEXT[type]}</Tag>
}
```

**配套单元测试**（19 个测试覆盖所有分支）：

```typescript
import { describe, it, expect } from 'vitest'
import { resolveActionDisplay } from '../utils'

describe('resolveActionDisplay', () => {
  it('已售商品：返回 sold', () => {
    expect(resolveActionDisplay({ payload: { is_sold: true } })).toEqual({ type: 'sold' })
  })
  it('已下单商品：返回 ordered', () => {
    expect(resolveActionDisplay({ payload: { order_status: 'ordered' } })).toEqual({ type: 'ordered' })
  })
  it('已下单+已售：返回 ordered-and-sold（优先级最高）', () => {
    expect(resolveActionDisplay({ payload: { is_sold: true, order_status: 'ordered' } }))
      .toEqual({ type: 'ordered-and-sold' })
  })
  it('可抢单商品：返回 grab', () => {
    expect(resolveActionDisplay({ canGrab: true })).toEqual({ type: 'grab' })
  })
  it('默认：返回 placeholder', () => {
    expect(resolveActionDisplay({})).toEqual({ type: 'placeholder' })
  })
})
```

### 3.2 S2004 嵌套层级

**阈值**：函数嵌套层级 ≤ 4。

**根因**：嵌套 `for`/`if`/回调函数超过 4 层。

**修复模式**：
1. **提取 setState updater** 为模块级函数（典型：React `useState` 的函数式更新）
2. **提取回调** 为工厂函数（典型：事件处理 `createXxxHandler(deps)`）
3. **早返回** 减少嵌套

**实战案例**：

```typescript
// ❌ 修复前：嵌套 5 层
function ChatInput() {
  function handleSend() {
    return function (event) {
      if (event.key === 'Enter') {
        if (!event.shiftKey) {
          setMessages(prev => {
            return [...prev, { role: 'user', content: input }]
          })
        }
      }
    }
  }
  return <Input onKeyDown={handleSend()} />
}

// ✅ 修复后：模块级 + 工厂函数
function createSendCompleteHandler(deps: { onSend: (msg: string) => void }) {
  return function handleSendComplete(event: KeyboardEvent) {
    if (event.key !== 'Enter' || event.shiftKey) return
    event.preventDefault()
    deps.onSend(/* ... */)
  }
}

function ChatInput() {
  const handleSendComplete = useMemo(
    () => createSendCompleteHandler({ onSend: sendMessage }),
    [sendMessage]
  )
  return <Input onKeyDown={handleSendComplete} />
}
```

### 3.3 S3358 三元复杂度

**阈值**：三元表达式嵌套不超过 2 层。

**修复模式**：
1. **拆分为 if-else**：超过 2 层时直接拆
2. **拆为变量**：先 `const a = cond ? x : y` 再用

```typescript
// ❌ 修复前：嵌套 3 层三元
const color = isDark ? (isActive ? '#FF6200' : '#FFA500') : (isActive ? '#0066CC' : '#999999')

// ✅ 修复后：拆为变量
const activeColor = isDark ? '#FF6200' : '#0066CC'
const inactiveColor = isDark ? '#FFA500' : '#999999'
const color = isActive ? activeColor : inactiveColor
```

### 3.4 S6757 SFC 内 `this`

**根因**：函数式组件（FC/SFC）内使用 `this`（典型错误：class 组件迁移到 FC 时残留）。

**修复模式**：
1. **工厂函数替代 class**：将 class 组件改写为 FC + hooks
2. **删除 `this.` 前缀**：用解构后的变量/参数替代

### 3.5 S7784 深拷贝

**阈值**：使用 `JSON.parse(JSON.stringify())` 进行深拷贝。

**修复模式**：使用 `structuredClone()`（原生 API，Node 17+/现代浏览器）。

```typescript
// ❌ 修复前
const cloned = JSON.parse(JSON.stringify(original))

// ✅ 修复后
const cloned = structuredClone(original)
```

**注意**：`structuredClone` 不支持函数、Symbol、DOM 节点，原生类型（`string`/`number`/`boolean`/`null`/`undefined`/`Date`/`RegExp`/`Array`/`Object`）都支持。

### 3.6 S6848 键盘可访问性

**阈值**：可点击元素（`onClick` 绑定的 `div`/`span`）必须配键盘事件。

**修复模式**：使用 `clickableProps` 工厂函数统一处理。

```typescript
// ✅ 推荐：工厂函数
export function clickableProps(onClick: () => void) {
  return {
    onClick,
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        onClick()
      }
    },
    tabIndex: 0,
    role: 'button',
  }
}

// 使用
<div {...clickableProps(handleClick)}>...</div>
```

### 3.7 S6819 anchor 替代 button

**阈值**：用 `<a>` 替代 `<button>`（无 `href` 时）。

**修复模式**：无 `href` 的可点击元素必须用 `<button type="button">`。

```tsx
// ❌ 修复前
<a onClick={handleClick}>点击</a>

// ✅ 修复后
<button type="button" onClick={handleClick}>点击</button>
```

### 3.8 S6844 div 替代 button

**阈值**：用 `<div role="button">` 替代 `<button>`。

**修复模式**：优先原生 `<button>`，配合 `clickableProps` 处理键盘事件。

```tsx
// ❌ 修复前
<div role="button" onClick={handleClick}>点击</div>

// ✅ 修复后
<button type="button" onClick={handleClick} onKeyDown={...}>点击</button>
```

### 3.9 S1128 未使用 import

**阈值**：导入但未使用的模块/符号。

**修复模式**：删除未使用 import。建议配置 ESLint `no-unused-vars` 自动检查。

### 3.10 S4325 类型断言

**阈值**：不必要的 `as` 断言（TypeScript 已能正确推导类型）。

**修复模式**：
1. **删除断言**：让 TS 自动推导
2. **类型守卫**：必要时用 `as unknown as T` 并附注释

```typescript
// ❌ 修复前
const value: string = 'foo' as string  // 多余的断言

// ✅ 修复后
const value = 'foo'  // TS 推导为 string
```

### 3.11 S6767 未使用参数

**修复模式**：同 Python（删除、`_` 前缀、添加使用）。

### 3.12 S7744 类型转换

**阈值**：`as unknown as T` 多重断言链路过深（≥ 2 层）。

**修复模式**：
1. **类型守卫**：用 `function isX(x: unknown): x is X` 收窄类型
2. **明确中间类型**：用 `as T1` 而非 `as unknown as T`

```typescript
// ❌ 修复前
const data = response as unknown as MyData  // 双重断言

// ✅ 修复后：类型守卫
function isMyData(x: unknown): x is MyData {
  return typeof x === 'object' && x !== null && 'id' in x
}
const data = isMyData(response) ? response : null
```

### 3.13 S6582 冗余可选链

**阈值**：可选链 `?.` 用在已知非空的值上。

**修复模式**：移除冗余 `?.`。

```typescript
// ❌ 修复前
const value = obj.a?.b.c  // obj.a 已非空

// ✅ 修复后
const value = obj.a.b.c
```

### 3.14 S7735 useEffect 依赖

**阈值**：useEffect 依赖数组缺失依赖项。

**修复模式**：
1. **补全依赖**：列出所有使用的外部变量
2. **ref 持有最新闭包**：避免循环依赖（典型：`useRef + useEffect` 模式）

```tsx
// ❌ 修复前：依赖缺失
useEffect(() => {
  console.log(count)  // 使用了 count 但未在依赖中
}, [])

// ✅ 修复后：补全依赖
useEffect(() => {
  console.log(count)
}, [count])
```

### 3.15 S6551 `for...in`

**阈值**：使用 `for...in` 遍历对象（应使用 `Object.keys/values/entries`）。

**修复模式**：

```typescript
// ❌ 修复前
for (const key in obj) {
  if (obj.hasOwnProperty(key)) {
    console.log(key, obj[key])
  }
}

// ✅ 修复后
for (const [key, value] of Object.entries(obj)) {
  console.log(key, value)
}
```

### 3.16 S1874 `@deprecated`

**阈值**：删除旧 API 时未标注 `@deprecated` 过渡期。

**修复模式**：删除前标注 `@deprecated` JSDoc，保留 1-2 个版本。

```typescript
/**
 * @deprecated Use `newFunction` instead. Will be removed in v2.0.0.
 */
export function oldFunction() {
  return newFunction()  // 委托给新函数
}
```

---

## 四、复盘总结

### 4.1 成功执行任务的完整步骤

**阶段一：扫描与分类**
1. 启动 SonarQube 服务（MCP 优先，降级到 sonar-scanner）
2. 验证 MCP 连接（`search_my_sonarqube_projects`）
3. 检查质量门禁状态（`get_project_quality_gate_status`）
4. 按严重级别分页拉取问题（`search_sonar_issues_in_projects`，ps=500）
5. 应用 filters 过滤（路径、规则、测试文件、生成代码）
6. 按 `severity_order × type_order` 排序
7. 按文件路径分组（同目录文件分到同组便于上下文复用）
8. 截取 `max_fix_per_run` 个最高优先级问题

**阶段二：并行修复**
1. 判断并行性（文件组数 > 1 且 `parallel_agents > 1`）
2. 启动 `scan.parallel_agents` 个子代理
3. 每个子代理分配 `scan.files_per_agent` 个文件
4. 子代理执行：读取 → 分析根因 → Edit 修复 → 记录报告
5. 同文件内多个 issue 串行处理（避免 Edit 冲突）

**阶段三：验证与报告**
1. 重新扫描对比 issue 数（修复前 vs 修复后）
2. 运行测试（`pytest tests/ ; npm --prefix frontend test`）
3. 硬约束合规性检查（`hard_constraints.rules`）
4. 生成报告（Markdown 格式到 `report.output_dir`）
5. 检查新问题（`fail_on_new_issues=true` 则阻止合并）

### 4.2 任务执行过程中的不确定性与失败点

**不确定性 1：MCP 工具不可用**
- 失败模式：MCP 工具无法连接 SonarQube 服务
- 应对：执行降级方案（`scripts/run-sonar-scanner.ps1`）
- 预防：启动前先 `verify-connection.ps1` 检查

**不确定性 2：MCP 工具参数限制**
- 失败模式：`analyze_code_snippet` 的 `scope` 参数只接受 `MAIN`/`TEST`（不能有空格）
- 失败模式：MCP 工具无法处理数组参数（如 `severities=["BLOCKER"]`）
- 应对：使用直接 REST API 调用（Python 脚本）

**不确定性 3：认证失败**
- 失败模式：401 错误（GLOBAL_ANALYSIS_TOKEN 无效）
- 应对：使用项目专属 token（如 `sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd`）
- 教训：从 `scripts/run_scan.bat` 中找正确 token

**不确定性 4：项目过滤不准确**
- 失败模式：`projectKeys=xianyu_hunter` 返回其他项目（fuzzy match）
- 应对：使用 `components=xianyu_hunter` 精确过滤

**不确定性 5：测试失败（与修复无关）**
- 失败模式：测试因 mock 数据过期失败
- 应对：检查测试是否依赖被修复代码的副作用，必要时更新 mock

**不确定性 6：修复引入新问题**
- 失败模式：拆分函数时漏掉一个调用方
- 应对：修复后必跑 `tsc --noEmit` + 单元测试 + 集成测试

### 4.3 可抽象的固定流程与判断逻辑

**固定流程 1：扫描 → 分类 → 修复 → 验证 闭环**
- 输入：项目名 + 严重级别
- 输出：修复报告
- 步骤：扫描 → filters 过滤 → 排序 → 分组 → 并行修复 → 重扫 → 报告

**固定流程 2：按规则 ID 选择修复策略**
- 规则 ID → 修复策略（`auto_fix` / `manual_review` / `skip`）
- 配置在 `scan_config.json -> fix_strategies`
- 新规则只需修改配置，无需改代码

**固定流程 3：按文件分组并行**
- 同一文件 → 串行（避免 Edit 冲突）
- 不同模块/目录 → 可并行
- 判断：`文件组数 > 1 且 parallel_agents > 1`

**固定流程 4：硬约束合规性检查**
- 遍历 `hard_constraints.rules`，每条用 Grep pattern 扫描
- 违规项写入报告
- `block_on_violation=true` 时阻止合并

**判断逻辑 1：修复优先级**
```
priority = severity_order × type_order
# 安全类（VULNERABILITY/SECURITY_HOTSPOT） > 功能类（BUG） > 规范类（CODE_SMELL）
# 硬约束违规优先级最高，无论 severity 如何
```

**判断逻辑 2：误报识别**
- 路径匹配 `ignore_paths` → 误报
- 规则 ID 在 `ignore_rules` → 误报
- 测试文件 + severity 在 `ignore_severity_in_tests` → 降级
- 生成代码（含 `// @generated`）→ 误报
- FastAPI 装饰器导入（S1481）→ 框架误报
- React Hook 依赖（S6488）→ 需结合上下文判断

**判断逻辑 3：修复闭环验证**
- 修复文件数 > 0 → 必须重新扫描
- 重扫发现新问题 → 必须处理（修复或回滚）
- 测试失败 → 必须修复测试或回滚代码

### 4.4 适用场景与不适用场景

**适用场景**：
- ✅ 迭代发布前的代码质量门禁检查
- ✅ 技术债清理运动（批量处理历史代码问题）
- ✅ 代码迁移/重构后的质量验证
- ✅ 多语言混合项目（Python+TypeScript）的代码质量闭环
- ✅ 新功能开发完成后的人工 review 前的预扫描

**不适用场景**：
- ❌ 小型脚本/原型项目（扫描成本大于收益）
- ❌ 未部署 SonarQube 服务的环境且无降级能力
- ❌ 紧急热修复（全量扫描太慢，应直接针对性修复）
- ❌ 高度依赖代码生成器的项目（生成代码噪声过高）
- ❌ 单文件 ≤ 100 行的临时脚本（规则触发概率低）

### 4.5 实战数据（2026-07-04 复盘）

| 指标 | 修复前 | 修复后 | 变化 |
|------|--------|--------|------|
| **BLOCKER** | 4 | 0 | -4 (100%) |
| **CRITICAL** | 143 | 141 | -2 |
| **MAJOR** | 335 | 167 | -168 |
| **MINOR** | 254 | 215 | -39 |
| **总问题** | 736 | 523 | -213 (-28.9%) |

**TOP 5 高频规则**：
1. **S3776（认知复杂度）**：约 80 个 → 拆分大函数（`login_orchestrator`、`cookie_store` 等）
2. **S2004（嵌套层级）**：约 30 个 → 提取模块级函数
3. **S6819/S6844（div/anchor 替代 button）**：约 25 个 → 改用 `<button>` + 键盘事件
4. **S7503（不必要 async）**：约 10 个 → 改同步（`scheduler.start_all`）
5. **S6767（未使用参数）**：约 15 个 → 删除（`ThumbnailTab.onActivate`）

---

## 五、规则速查对照表

| 规则 | 触发场景 | 严重度 | 修复模式 | 参考案例 |
|------|---------|--------|---------|---------|
| S3776 | 函数含 5+ 嵌套分支/循环 | CRITICAL | 拆分场景/提取模块级 | `login_orchestrator.start_session` |
| S2004 | 5+ 层函数嵌套 | CRITICAL | 提取 setState updater | `Chatbot/index.tsx` |
| S3358 | 3+ 层三元嵌套 | MAJOR | 拆为变量 | - |
| S6757 | SFC 内 `this.` | MAJOR | 工厂函数替代 class | - |
| S7784 | `JSON.parse(JSON.stringify())` | MAJOR | `structuredClone()` | - |
| S6848 | div onClick 无键盘 | MAJOR | `clickableProps` 工厂 | - |
| S6819 | `<a onClick>` 无 href | MAJOR | `<button type="button">` | - |
| S6844 | `<div role="button">` | MAJOR | `<button>` + 键盘 | `ItemList.tsx` |
| S1128 | 未使用 import | MINOR | 删除 | - |
| S4325 | 不必要 `as` | MINOR | 删除/类型守卫 | - |
| S7503 | `async` 无 `await` | MAJOR | 改同步 | `scheduler.start_all` |
| S6767 | 未使用参数 | MAJOR | 删除/`_` 前缀 | `ThumbnailTab.onActivate` |
| S7744 | `as unknown as T` | MAJOR | 类型守卫 | - |
| S6582 | 冗余可选链 | MINOR | 移除 `?.` | - |
| S7735 | useEffect 依赖缺失 | MAJOR | 补全/ref 闭包 | - |
| S6551 | `for...in` | MAJOR | `Object.entries` | - |
| S1874 | 删除 API 未标 `@deprecated` | MINOR | JSDoc `@deprecated` | - |
| S1192 | 重复字符串 ≥ 2 | MINOR | 提取常量 | `_TASK_NOT_FOUND` |
| S1481 | 未使用 import（误报） | MINOR | 豁免/删除 | FastAPI 装饰器 |
| S2949 | 可变默认参数（误报） | MAJOR | `None` + 函数内初始化 | - |
| S3508 | 未使用局部变量 | MINOR | 删除/`_` 前缀 | - |
| S5843 | 复杂正则 | MAJOR | 拆分/VERBOSE | `_URL_RE` 拆分 |

---

**使用指南**：
- **开发阶段**：参照修复模式（每节"实战案例"+"复用模板"）编写代码，预防问题产生
- **Review 阶段**：参照速查对照表（§五）快速定位规则对应的检查项
- **修复阶段**：参照 `xianyu-sonarqube-mcp` Skill 调用 MCP 工具批量修复
- **配置阶段**：所有规则阈值（认知复杂度 ≤ 15、嵌套 ≤ 4 等）可在 `config/scan_config.json` 中调整
