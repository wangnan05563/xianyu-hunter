# 12. SonarQube 合规 🆕v2.0 / v3.0 增强

- 【强制】**S2004**：函数嵌套层数 ≤4，超限提取模块级函数（典型：setState updater）
- 【强制】**S3358**：嵌套三元拆为变量（不超过 2 层）
- 【强制】**S6757**：SFC 内不用 `this`，工厂函数替代 class
- 【强制】**S7784**：使用 `structuredClone` 替代 `JSON.parse(JSON.stringify())`
- 【强制】**S6848**：`clickableProps` 工厂函数配键盘事件
- 【强制】**S1128**：删除未使用 import
- 【强制】**S4325**：移除不必要类型断言
- 【强制】**S3776**：认知复杂度 ≤15，拆 case 为模块级 handler
- 🆕【强制】**S7503**：不必要的 `async` 函数（无 await）——同步函数移除 `async` 关键字
- 🆕【强制】**S6767**：未使用的 Props/State/参数 ——立即删除，避免接口膨胀
- 🆕【强制】**S6819**：使用 `<a>` 替代 `<button>`（无 href 时）——改为 `<button type="button">`
- 🆕【强制】**S6844**：使用 `<div role="button">` 替代 `<button>` ——优先原生 `<button>` + 键盘事件
- 🆕【强制】**S7744**：不必要的类型转换（`as` 链路过深）——用类型守卫（`type guard`）收窄类型
- 🆕【强制】**S6582**：可选链冗余调用（`a?.b?.c` 而 a 已非空）——移除冗余 `?.`
- 🆕【强制】**S7735**：useEffect 缺少依赖项 ——补全依赖数组（用 `ref` 持有最新闭包避免循环）
- 🆕【强制】**S6551**：使用 `for...in` 遍历对象 ——改为 `Object.keys/values/entries`
- 🆕【强制】**S1874**：使用 `@deprecated` 标记替代直接删除的 API ——导出前标注 deprecated

**实战案例参考**：
- `SheetTabs.tsx` 拆分 `TabItem` 为 `ThumbnailTab` + `StandardTab` 修复 S3776 + S6767
- `Chatbot/index.tsx` 的 `createSendCompleteHandler` 工厂函数修复 S2004 + S6819
- `ItemList.tsx` `div+onClick` 改为 `<button>` 修复 S6844
- `Evaluations/index.tsx` 提取 `resolveActionDisplay` 修复 S3776
