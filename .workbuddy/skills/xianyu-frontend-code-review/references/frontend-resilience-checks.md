# 前端韧性检查点详细描述（references/frontend-resilience-checks.md）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)
> **用途**：F-REVIEW-227~232 六项前端韧性检查点的完整描述（问题/要求/定位/判断/修复/教训）。冷区域文件，日常审查无需预加载，仅在 SKILL.md 维度 40 索引命中时按需查阅。
> **维护原则**：新增/修改检查点时同步更新本文件 + SKILL.md 维度 40 索引 + checkpoints-index.md 索引行 + config.yaml 配置节点。
> **配套规范**：coding-standards v1.3 §3.10-3.15（2026-07-25 代码评审 10 问题复盘前端落地）

---

## F-REVIEW-227 MARKDOWN-PREPROCESS-CODEBLOCK-PROTECT Markdown 预处理代码块保护

- **检查点 ID**：F-REVIEW-227
- **严重等级**：CRITICAL（P0，代码块内容被替换破坏导致展示错误 + 用户无法复制正确代码）
- **配置节点**：`config.yaml#frontend_resilience.markdown_preprocess_codeblock_protect`
- **对应编码规范**：coding-standards v1.3 §3.10

### 问题描述
对 Markdown 字符串进行全局替换（如 `[来源:N]` → 脚注链接、`$xxx$` → 公式渲染）时，未先分割代码块（```...```）和行内代码（`` `...` ``），导致代码块内的内容也被替换，破坏代码语义。

### 关键要求
1. **替换前必须分割**：用正则将 Markdown 字符串按代码块/行内代码切分为段，仅对非代码段执行替换
2. **保留代码段原样**：代码段（含分隔符）直接拼接回结果，不参与任何字符替换
3. **替换函数与分割逻辑解耦**：替换函数（如 `replaceSources`）作为参数传入，分割器通用化

### 定位方式
```bash
# 搜索对 Markdown 字符串做 replace 的代码点
grep -rn "\.replace(.*content\|content\.replace\|processedContent" frontend/src/ --include="*.tsx" --include="*.ts"
```

### 判断标准
- ❌ 违规：`content.replace(/\[来源:(\d+)\]/g, ...)` 直接对原始 Markdown 字符串替换
- ✅ 合规：先 `content.split(/(```[\s\S]*?```|`[^`]+`)/)` 分割，对偶数索引段（非代码）执行替换

### 修复方案
```typescript
// ✅ 正确：分割代码块，仅对非代码段替换
function preprocessMarkdown(content: string, replaceFn: (s: string) => string): string {
  // 按代码块和行内代码分割，捕获组保留分隔符
  const segments = content.split(/(```[\s\S]*?```|`[^`]+`)/);
  return segments
    .map((seg, idx) => (idx % 2 === 0 ? replaceFn(seg) : seg))
    .join('');
}

const processedContent = preprocessMarkdown(content, (s) =>
  s.replace(/\[来源:(\d+)\]/g, (_, n) => `<sup class="cite">${n}</sup>`)
);
```

### 历史教训
AssistantMessage 组件中 `[来源:N]` 替换未做代码块保护，导致代码块内出现的 `[来源:1]` 文本被错误替换为脚注 HTML，破坏代码展示。

### 适用场景
- 对 Markdown 字符串做任何字符替换（脚注/公式/链接/emoji）
- 自定义 Markdown 预处理流水线
- 富文本渲染前的内容清洗

### 不适用场景
- 仅渲染 Markdown 不做替换（react-markdown 等库内部已处理）
- 对纯文本（非 Markdown）的替换

---

## F-REVIEW-228 REACT-RENDER-SIDEFFECT-BAN React 组件 render 阶段副作用禁令

- **检查点 ID**：F-REVIEW-228
- **严重等级**：CRITICAL（P0，render 阶段写 ref 导致 StrictMode 双调用下状态不一致 + 难以复现的 Bug）
- **配置节点**：`config.yaml#frontend_resilience.react_render_sideffect_ban`
- **对应编码规范**：coding-standards v1.3 §3.11

### 问题描述
React 函数组件主体（render 阶段）直接写入 `ref.current`、修改外部变量、调用订阅 API。StrictMode 下 render 会执行两次，副作用被重复触发导致状态污染。

### 关键要求
1. **render 阶段禁止副作用**：函数组件主体内禁止 `ref.current = ...`、修改外部变量、订阅事件
2. **副作用必须放在 useEffect**：ref 写入、事件订阅、定时器启动必须在 `useEffect` 内
3. **事件回调中可写 ref**：onClick/onChange 等事件处理函数中写 ref 是合法的（不在 render 阶段）
4. **derived state 用 useMemo**：从 props/state 派生的值用 `useMemo`，不要在 render 中写 ref 缓存

### 定位方式
```bash
# 搜索函数组件主体内的 ref.current 赋值
grep -rn "\.current\s*=" frontend/src/ --include="*.tsx" --include="*.ts" | grep -v "useEffect\|useLayoutEffect\|=>"
```

### 判断标准
- ❌ 违规：`function Comp() { handleSendRef.current = handleSend; return <.../> }`（render 阶段写 ref）
- ✅ 合规：`useEffect(() => { handleSendRef.current = handleSend; }, [handleSend]);`
- ✅ 合规：`const handleClick = () => { ref.current = newValue; }`（事件回调中写 ref）

### 修复方案
```typescript
// ❌ 错误：render 阶段写 ref
function ChatPage() {
  const handleSendRef = useRef<() => void>(() => {});
  handleSendRef.current = handleSend; // 违规：render 阶段副作用
  return <Child onAction={() => handleSendRef.current()} />;
}

// ✅ 正确：在 useEffect 中写 ref
function ChatPage() {
  const handleSendRef = useRef<() => void>(() => {});
  useEffect(() => {
    handleSendRef.current = handleSend;
  }, [handleSend]);
  return <Child onAction={() => handleSendRef.current()} />;
}
```

### 历史教训
Chatbot/index.tsx 中 `handleSendRef.current = handleSend` 写在函数组件主体内，StrictMode 下重复执行导致 ref 指向旧闭包。修复：移到 `useEffect` 中。

### 适用场景
- 所有 React 函数组件
- 自定义 Hook 的主体（同样禁止副作用）
- 使用 ref 的场景

### 不适用场景
- 类组件的 constructor（语义不同）
- 事件处理函数内部（不在 render 阶段）
- useEffect/useLayoutEffect 内部（本就是副作用位置）

---

## F-REVIEW-229 SSE-EVENT-RUNTIME-TYPE-VALIDATION SSE 事件运行时类型校验

- **检查点 ID**：F-REVIEW-229
- **严重等级**：CRITICAL（P0，未校验的 SSE 数据导致运行时崩溃 + 类型断言掩盖 schema 漂移）
- **配置节点**：`config.yaml#frontend_resilience.sse_event_runtime_type_validation`
- **对应编码规范**：coding-standards v1.3 §3.12

### 问题描述
SSE 事件数据用 `as` 强制断言为特定类型（如 `data.follow_ups as string[]`），未做运行时类型校验。后端 schema 漂移时前端无法感知，运行时访问不存在的字段导致崩溃。

### 关键要求
1. **禁止 `as` 强制断言 SSE 数据**：SSE event data 必须用 zod schema 或 type guard 校验
2. **校验失败时降级**：类型不匹配时记录 WARNING 并使用 fallback 值，不抛错中断流
3. **schema 与后端契约对齐**：zod schema 字段必须与后端 Pydantic 模型一一对应
4. **可选字段用 `.optional()`**：后端可能不返回的字段必须标记为可选

### 定位方式
```bash
# 搜索 SSE 事件处理中的 as 断言
grep -rn "JSON\.parse.*as\s\|event\.data.*as\s\|\.follow_ups.*as\s" frontend/src/ --include="*.tsx" --include="*.ts"
```

### 判断标准
- ❌ 违规：`const followUps = (data.follow_ups ?? []) as string[]`（无运行时校验）
- ✅ 合规：`const parsed = FollowUpsSchema.safeParse(data.follow_ups); const followUps = parsed.success ? parsed.data : []`

### 修复方案
```typescript
import { z } from 'zod';

// schema 与后端 Pydantic 模型对齐
const FollowUpsSchema = z.object({
  follow_ups: z.array(z.string()).optional().default([]),
});

// SSE 事件处理
const handleSSEEvent = (event: MessageEvent) => {
  const raw = JSON.parse(event.data);
  const parsed = FollowUpsSchema.safeParse(raw);
  if (!parsed.success) {
    console.warn('SSE follow_ups schema mismatch', parsed.error);
    return { followUps: [] };
  }
  return { followUps: parsed.data.follow_ups };
};
```

### 历史教训
Chatbot SSE DONE 事件中 `data.follow_ups as string[]` 强制断言，后端返回 `null` 时前端崩溃。修复：用 zod schema 校验。

### 适用场景
- 所有 SSE 事件数据处理
- WebSocket 消息处理
- 任何从外部源（API/PostMessage/Storage）读取的不可信数据

### 不适用场景
- 内部纯函数间传递的数据（类型系统已保证）
- 测试代码中的 mock 数据

---

## F-REVIEW-230 TIMER-CLEANUP-RACE-GUARD 定时器清理与竞态防护

- **检查点 ID**：F-REVIEW-230
- **严重等级**：HIGH（P1，未清理的定时器导致内存泄漏 + 旧回调覆盖新状态）
- **配置节点**：`config.yaml#frontend_resilience.timer_cleanup_race_guard`
- **对应编码规范**：coding-standards v1.3 §3.13

### 问题描述
`setTimeout`/`setInterval` 未在组件卸载时清理；多次触发同一操作时未清除旧定时器，导致旧回调在新状态后执行，覆盖正确状态。

### 关键要求
1. **卸载时必须清理**：`setTimeout`/`setInterval` 必须在 `useEffect` cleanup 函数中 `clearTimeout`/`clearInterval`
2. **重设前清除旧定时器**：用 `useRef` 存储定时器 ID，新触发前 `clearTimeout(ref.current)`
3. **依赖项变更时清理**：`useEffect` 依赖数组变更时先执行 cleanup 清理旧定时器
4. **避免在 render 中创建定时器**：定时器必须在 `useEffect` 或事件回调中创建

### 定位方式
```bash
# 搜索 setTimeout/setInterval 未配合 clearTimeout/clearInterval
grep -rn "setTimeout\|setInterval" frontend/src/ --include="*.tsx" --include="*.ts"
```

### 判断标准
- ❌ 违规：`const timer = setTimeout(...); ` 无对应 `clearTimeout` 在 cleanup 中
- ❌ 违规：连续点击触发多次 setTimeout，旧定时器未清除
- ✅ 合规：`useEffect(() => { const t = setTimeout(...); return () => clearTimeout(t); }, [dep]);`
- ✅ 合规：用 `useRef` 存储定时器 ID，新触发前先 `clearTimeout(ref.current)`

### 修复方案
```typescript
// ✅ 正确：useRef 存储定时器 ID，重设前清除
function CodeBlock({ code }: { code: string }) {
  const copyTimerRef = useRef<number | null>(null);

  const handleCopy = () => {
    if (copyTimerRef.current) {
      clearTimeout(copyTimerRef.current); // 清除旧定时器
    }
    navigator.clipboard.writeText(code);
    setCopied(true);
    copyTimerRef.current = window.setTimeout(() => {
      setCopied(false);
      copyTimerRef.current = null;
    }, 2000);
  };

  // 卸载时清理
  useEffect(() => {
    return () => {
      if (copyTimerRef.current) {
        clearTimeout(copyTimerRef.current);
      }
    };
  }, []);
}
```

### 历史教训
CodeBlock 组件中"复制成功"提示的 setTimeout 未清理，用户快速连续复制时旧定时器在新提示后触发，导致提示提前消失。修复：用 `useRef` 记录定时器 ID，重设前清除。

### 适用场景
- 所有使用 setTimeout/setInterval 的组件
- 防抖/节流实现
- 动画/过渡定时器
- 轮询场景

### 不适用场景
- 一次性 Promise（如 `await new Promise(setTimeout)` 配合 `Promise.race` 取消）
- Web Worker 中的定时器（独立线程，不影响 React 组件）

---

## F-REVIEW-231 INTERACTIVE-ELEMENT-A11Y 交互元素可访问性

- **检查点 ID**：F-REVIEW-231
- **严重等级**：MEDIUM（P2，键盘用户无法操作 + 屏幕阅读器忽略交互功能）
- **配置节点**：`config.yaml#frontend_resilience.interactive_element_a11y`
- **对应编码规范**：coding-standards v1.3 §3.14

### 问题描述
非原生交互元素（`<div>`/`<span>` 加 onClick）未添加 `tabIndex`、`role` 和 `onKeyDown` 事件处理，键盘用户无法 Tab 聚焦，屏幕阅读器不识别为可交互。

### 关键要求
1. **非原生交互元素三件套**：`<div onClick>` 必须同时添加 `tabIndex={0}`、`role="button"`、`onKeyDown` 处理 Enter/Space
2. **优先用语义化原生元素**：能用 `<button>`/`<a>` 就不用 `<div onClick>`
3. **焦点可见性**：`tabIndex > 0` 的元素必须有 `:focus-visible` 样式
4. **键盘事件处理完整**：Enter 和 Space 都必须触发点击行为

### 定位方式
```bash
# 搜索非原生交互元素
grep -rn "<div.*onClick\|<span.*onClick\|<li.*onClick" frontend/src/ --include="*.tsx" | grep -v "role=\|tabIndex"
```

### 判断标准
- ❌ 违规：`<div onClick={handleClick}>点击</div>`（无 tabIndex/role/onKeyDown）
- ✅ 合规：`<button onClick={handleClick}>点击</button>`（原生元素，自动支持键盘）
- ✅ 合规：`<div role="button" tabIndex={0} onClick={handleClick} onKeyDown={onEnterOrSpace(handleClick)}>点击</div>`

### 修复方案
```typescript
// ✅ 优先：用原生 <button>
<button onClick={handleClick} className="tag">推荐问题</button>

// ✅ 必须用 div 时：三件套齐全
<div
  role="button"
  tabIndex={0}
  onClick={handleClick}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  }}
>
  推荐问题
</div>

// 抽象为工具函数
const onEnterOrSpace = (fn: () => void) => (e: React.KeyboardEvent) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    fn();
  }
};
```

### 历史教训
Chatbot 推荐问题 Tag 用 `<div onClick>` 实现，键盘用户无法 Tab 聚焦。修复：添加 `tabIndex={0}`、`role="button"`、`onKeyDown`，支持 Enter/Space 触发。

### 适用场景
- 所有非原生交互元素（div/span/li 加 onClick）
- 自定义可点击组件
- 拖拽交互（需补充 aria 属性）

### 不适用场景
- 原生 `<button>`/`<a>`/`<input>` 等语义化元素（已内置可访问性）
- 纯展示元素（无交互行为）

---

## F-REVIEW-232 SSE-ONCOMPLETE-DATA-INTEGRITY 流式响应 onComplete 数据完整性

- **检查点 ID**：F-REVIEW-232
- **严重等级**：HIGH（P1，附加产出丢失导致用户看不到推荐问题/标题/摘要）
- **配置节点**：`config.yaml#frontend_resilience.sse_oncomplete_data_integrity`
- **对应编码规范**：coding-standards v1.3 §3.15

### 问题描述
SSE 流式响应的 `onComplete` 回调中，持久化条件仅检查主回答非空（`content.length > 0`），忽略附加产出（follow_ups/标题/标签）。当主回答为空但有附加产出时，消息未持久化，附加数据丢失。

### 关键要求
1. **持久化判断基于"任一产出非空"**：`content || followUps.length > 0 || title || tags.length > 0`
2. **附加产出与主回答独立判断**：不要用 `content && followUps` 这种 AND 逻辑
3. **onComplete 必须接收所有产出**：SSE DONE 事件的全部字段都应传递给 onComplete
4. **空状态显式标注**：所有产出都为空时记录 WARNING，但仍创建空消息记录（便于调试）

### 定位方式
```bash
# 搜索 onComplete 回调中的持久化条件
grep -rn "onComplete\|content\.length\|assistantMsg" frontend/src/ --include="*.tsx" --include="*.ts"
```

### 判断标准
- ❌ 违规：`if (content.length > 0) { createMessage({ content, followUps }); }`（主回答为空时不持久化）
- ✅ 合规：`if (content.length > 0 || followUps.length > 0) { createMessage({ content, followUps }); }`

### 修复方案
```typescript
// ✅ 正确：任一产出非空即持久化
const handleComplete = (data: { content: string; followUps: string[]; title?: string }) => {
  const hasAnyOutput =
    data.content.length > 0 ||
    data.followUps.length > 0 ||
    (data.title?.length ?? 0) > 0;

  if (hasAnyOutput) {
    createAssistantMessage({
      content: data.content,
      followUps: data.followUps,
      title: data.title,
    });
  } else {
    console.warn('SSE 完成但所有产出为空', data);
  }
};
```

### 历史教训
Chatbot onComplete 中 `if (content.length > 0)` 判断，当 LLM 返回空回答但有推荐问题时，消息未持久化，用户看不到推荐问题。修复：将 `followUps.length > 0` 加入判断条件。

### 适用场景
- SSE 流式响应的完成回调
- WebSocket 消息聚合的完成回调
- 任何多产出字段的持久化判断

### 不适用场景
- 单一字段的持久化（无需考虑多产出）
- 临时缓存（不涉及持久化）

---

## 配置节点速查

| 检查点 | 配置节点 | severity | 关键参数 |
|---|---|---|---|
| F-REVIEW-227 | `frontend_resilience.markdown_preprocess_codeblock_protect` | CRITICAL | `forbid_direct_replace_on_markdown` / `require_codeblock_split` |
| F-REVIEW-228 | `frontend_resilience.react_render_sideffect_ban` | CRITICAL | `forbid_ref_write_in_render` / `require_use_effect_for_ref` |
| F-REVIEW-229 | `frontend_resilience.sse_event_runtime_type_validation` | CRITICAL | `forbid_as_assertion` / `require_zod_schema` / `require_safe_parse` |
| F-REVIEW-230 | `frontend_resilience.timer_cleanup_race_guard` | HIGH | `require_cleanup_on_unmount` / `require_clear_before_reset` |
| F-REVIEW-231 | `frontend_resilience.interactive_element_a11y` | MEDIUM | `require_tabindex_role_keydown` / `prefer_native_button` |
| F-REVIEW-232 | `frontend_resilience.sse_oncomplete_data_integrity` | HIGH | `require_any_output_check` / `forbid_main_only_check` |
