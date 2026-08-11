# 闲鱼猎人前端走查案例集（xianyu walkthrough cases）

> 本文件是 `xianyu-frontend-code-review` 技能的**按需加载**补充材料，沉淀自一次真实的端到端走查：
> 「LLM 用量指标页面（桌面端 `pages/Config/AIConfig` / 移动端 `mobile/pages/AIConfig`）内容一直不显示」→ 定位到移动端 `getUsage().catch(() => null)` 静默吞错。
> 它把既有的若干 `F-REVIEW-*` 检查点落到**具体组件形态**上，便于评审时快速对照。

## 何时加载本文件

- 审查文件命中：`mobile/pages/AIConfig`、`pages/Config/AIConfig`、`getUsage`、`usage` 初始化、`useEffect` 内异步请求、`catch(() =>` 这类失败处理。
- 或需要判断「同一数据接口在桌面端与移动端失败处理是否一致」时（跨端一致性）。
- 后端侧的同源案例（时区分桶 / billable 隔离 / 路径解析）见后端案例集 `references/xianyu-walkthrough-cases.md`。

---

## Case 1 — 跨端失败诊断一致性（cross-surface failure-diagnostic consistency）

**现象**：同一用量数据接口 `getUsage()`，桌面端早已写成 `getUsage().catch((e) => { console.warn('[AIConfig]...', e); return null })`，而移动端仍是裸 `.catch(() => null)`。结果：移动端加载失败时页面「内容一直不显示」，且控制台毫无痕迹，无法定位。

**正确形态**：同一数据接口在**所有消费端**必须共享同一失败诊断模式——至少一条 `console.warn`（带模块前缀）+ 安全的降级返回值。

```javascript
// 桌面端（既有，作为基准）
getUsage().catch((e) => {
  console.warn("[AIConfig] 用量数据加载失败，已隐藏卡片：", e);
  return null;
});
// 移动端（修复后，与桌面端对齐）
.getUsage().catch((e) => {
  console.warn("[MobileAIConfig] 用量数据加载失败，已隐藏卡片：", e);
  return null;
});
```

**评审要点**：
- 对齐 **F-REVIEW-ERROR-CODE-BRANCH / 错误处理一致性**：跨端（桌面 React / 移动 React-Native / 小程序）共享的 API 调用，失败分支的「是否日志化」必须一致，不允许一端静默。
- 凡出现 `.catch(() => null)` / `.catch(() => undefined)` 无日志，标记为问题，要求补 `console.warn` + 模块前缀。
- 泛化判断：把「同一接口名」在仓库里全局搜一遍，逐个核对失败分支形态是否统一。

---

## Case 2 — 异步初始化为 null + 优雅隐藏（async init-to-null + graceful hide）

**现象**：移动端 `usage` 初始值设为 `null`，加载失败时保持 `null`，UI 据此隐藏用量卡片。这种模式本身没问题，但**前提是失败被日志化**（见 Case 1）。若失败被静默吞掉，`null` 同时隐藏了「数据」和「失败原因」，排查时完全失明。

**正确形态**：
- `usage` 初始为 `null` 可接受，用于表示「尚未/未能加载」。
- 必须有显式分支处理 `null`：隐藏卡片或展示兜底文案，而不是让页面区域空白且无提示。
- 加载失败的成因必须写日志（否则 `null` 失去诊断意义）。

```javascript
const [usage, setUsage] = useState(null);
useEffect(() => {
  getUsage()
    .then(setUsage)
    .catch((e) => {
      console.warn("[MobileAIConfig] 用量加载失败，保持 null 并隐藏卡片：", e);
      setUsage(null);
    });
}, []);
// 渲染：usage === null 时渲染占位/隐藏，而非空白且无日志
```

**评审要点**：
- 异步状态初始为 `null`/`undefined` 是合理默认，但评审要确认：(a) 有加载态/错误态 UI；(b) 失败时留痕。
- 对齐 **F-REVIEW-STATE-INIT / 状态初始化规范**：禁止「初始 null + 无错误处理的渲染」组合导致空白屏。
- 泛化判断：搜 `useState(null)` 紧随异步请求的场景，逐个确认失败路径是否「既降级又留痕」。

---

## Case 3 — null 初始值 vs 默认值（null-init vs default-init 取舍）

**现象**：用量卡片在「无数据」与「加载失败」两种语义上都表现为「不显示」。若用默认值（空对象/零值）初始化，失败时会误显示「0 / 空」误导用户；若用 `null` 初始化并隐藏，则失败与「真的没数据」不可区分——必须靠日志区分。

**取舍原则**：
- 想要「失败时视觉上不干扰用户」→ 用 `null` 初始化 + 隐藏，但**必须用日志区分失败与无数据**（Case 1）。
- 想要「失败时也能展示结构化空态（如『暂无用量数据』）」→ 可用默认值初始化，但要保证默认值来自**显式约定**而非未加载的偶然 `null`。
- 关键：**不要让「未加载完成」的瞬时 `null` 被误当成「业务上的空」**永久展示。

**评审要点**：
- 对齐 **F-REVIEW-STATE-FUNCTIONAL-ALIGN / 状态语义对齐**：状态的每一个取值（null / 默认值 / 真实数据）都应有明确业务含义与对应 UI，不允许歧义。
- 泛化判断：状态初始值与「业务空态」是否重合；重合时是否有额外信号（日志/loading flag）消解歧义。

---

## 走查提炼的通用前端评审清单（可套用到同类页面）

1. **跨端一致性**：同一 API 在各端的失败分支（是否日志化、降级值）是否统一？（Case 1）
2. **失败可见性**：`.catch` / `try-catch` 是否留 `console.warn` + 模块前缀，而非裸吞？（Case 1 / F-REVIEW-ERROR）
3. **null 语义**：异步初始 `null` 是否有加载态/错误态 UI，失败时是否留痕？（Case 2）
4. **状态歧义**：状态初始值是否与「业务空态」重合而无额外信号消解？（Case 3）
5. **降级安全**：所有降级返回值是否被显式处理，不会造成空白屏或误导展示？（Case 2/3）

> 每条都可映射到既有 `F-REVIEW-*` 检查点与本技能维度章节；本案例集提供「真实组件形态 + 反模式 + 修复模板」，缩短从「看到组件」到「判定违规」的距离。
