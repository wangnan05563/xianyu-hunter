# Frontend Ui 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「frontend ui」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 8：SonarQube 规则检查【强制，前端必做】

8. **SonarQube 规则检查【强制，前端必做】**
   - **S2004**：嵌套层级 ≤ 4，超限时提取模块级函数（典型：setState updater）
   - **S3358**：嵌套三元拆为变量
   - **S6757**：SFC 内不用 `this`，工厂函数替代 class
   - **S7784**：使用 `structuredClone` 替代 `JSON.parse(JSON.stringify())`
   - **S6848**：`clickableProps` 工厂函数配键盘事件
   - **S1128**：删除未使用 import
   - **S4325**：移除不必要类型断言
   - **S3776**：认知复杂度，拆 case 为模块级 handler
   - 🆕 **S7503**：不必要的 `async` 函数（无 await）——改同步
   - 🆕 **S6767**：未使用的 Props/State/参数 ——删除
   - 🆕 **S6819/S6844**：用 `<a>`/`<div>` 替代 `<button>` ——改 `<button type="button">` + 键盘事件
   - 🆕 **S7744**：不必要的类型转换 ——用类型守卫
   - 🆕 **S6582**：冗余可选链 ——移除 `?.`
   - 🆕 **S7735**：useEffect 依赖缺失 ——补全或用 ref 闭包
   - 🆕 **S6551**：`for...in` ——改 `Object.keys/values/entries`
   - 🆕 **S1874**：删除 API 未标 `@deprecated` ——加 JSDoc
   - 🆕 **S1192**：重复字符串字面量 ——提取为模块级常量
   - 🆕 **S1481/S2949**：FastAPI 装饰器误报 ——豁免规则
   - 🆕 **S5843**：复杂正则 ——拆分或 VERBOSE
   - **完整规则+修复模式+实战案例**：参见 [sonarqube-rules-guide.md](../sonarqube-rules-guide.md)


---

### step 12：容器适配原则【强制】

12. **容器适配原则【强制】**
    - 被嵌入到固定高度容器（如 SheetWorkspace、MainLayout）的页面组件，用 `height: 100%` 适应父容器
    - **禁止**在嵌入场景使用 `minHeight: 100vh` 或 `height: 100vh`，会溢出容器导致全屏显示
    - 独立路由页面（未进 MainLayout，如 `/login`、`/onboarding`）可用 `100vh`
    - flex 布局中 Header 用 `flex: '0 0 auto'`，Content 用 `flex: 1` + `overflow: auto`


---

### step 13：文件扩展名判断【强制】

13. **文件扩展名判断【强制】**
    - 含 JSX 语法的文件用 `.tsx`（如 `sheetRegistry.tsx` 含 `<DashboardOutlined />`）
    - 纯逻辑文件用 `.ts`（如 `sheetStore.ts`、`useIsMobile.ts`）
    - 测试文件扩展名跟随被测文件：组件测试用 `.test.tsx`，Hook/纯逻辑用 `.test.ts`
    - 创建文件前先判断内容是否含 JSX，避免 oxc 解析错误


---

### step 14：多视图切换与 state 提升【强制】🆕v4.0

14. **多视图切换与 state 提升【强制】🆕v4.0**
    - 多视图（Tab/Accordion/Collapse/Drawer）共享同一数据源时，state 必须提升至最近共同父组件
    - 容器组件用 `destroyInactiveTabPane={false}` 保留 DOM（表单类避免输入焦点丢失）
    - 标题职责归容器（如 Tab label），子组件只保留功能说明文字，禁止标题重复
    - **适用**：多视图共享数据源；**不适用**：各视图有独立数据源
    - **判断信号**：两个子组件的 props 来自同一 config/state → 应提升


---

### step 16：事件触发时机【强制】🆕v4.0

16. **事件触发时机【强制】🆕v4.0**
    - "已完成"语义事件（如 `EVAL_PASSED`、`NOTIFY_SENT`、`TASK_COMPLETED`）必须在业务逻辑**完成后**触发
    - "开始"语义事件（如 `TASK_STARTED`、`EVAL_STARTED`）在业务逻辑**开始前**触发
    - **禁止**：在业务逻辑前置条件变更时就触发完成事件（如 DingTalk 通知在 AI 评估前就触发 EVAL_PASSED）
    - **判断信号**：事件名含 PASSED/SENT/COMPLETED → 后置；含 STARTED/BEGIN → 前置


---

### step 20：注释与代码一致性【强制】🆕v4.0

20. **注释与代码一致性【强制】🆕v4.0**
    - 注释必须与代码逻辑**严格一致**，禁止误导性注释
    - 防御性说明需明确标注是"防御性"而非"必需"（如"顺序不影响结果，但保留防御性排列"）
    - 涉及顺序约束、依赖关系的注释需验证是否真实存在该约束
    - **历史教训**：注释称"必须在 X 之前判断避免误匹配"，但实际不存在误匹配风险，浪费维护者验证时间


---

### step 21：显式样式优于隐式间距【强制】🆕v4.0

21. **显式样式优于隐式间距【强制】🆕v4.0**
    - 图标+文字、按钮+文字等内联元素间距用显式 `style={{ marginRight: N }}` 或 `Space` 组件
    - **禁止**依赖 JSX 空格渲染间距（如 `<Icon /> 文字`），不同框架版本渲染不一致
    - **适用**：所有内联元素间距场景


---

### step 22：IIFE 反模式禁止【强制】🆕v4.0

22. **IIFE 反模式禁止【强制】🆕v4.0**
    - JSX 内禁止 IIFE（`{(() => { ... })()}`），提取为组件顶部的变量
    - JSX 中直接引用变量进行条件渲染（`{var ? <X/> : null}`）
    - **理由**：提升可读性、避免每次渲染重新创建函数、便于调试
    - **适用**：所有 JSX 中的条件渲染/计算逻辑；**不适用**：极简三元（`{a ? <X/> : null}` 可直接内联）


---

### step 24：UI 状态独立性原则【强制】🆕v4.2

24. **UI 状态独立性原则【强制】🆕v4.2**
    - **受控 UI 状态不应自动联动路由变化**：Menu `openKeys`、Tree `expandedKeys`、Collapse `activeKey`、Tabs `activeKey` 等用户手动控制的展开/折叠状态，必须独立于路由，仅在用户主动操作（点击 SubMenu 标题、折叠面板等）时变化
    - **路由变化只应更新派生状态**：`selectedKeys`（高亮当前项）、breadcrumb（面包屑）、页面标题等派生状态应联动路由，但**不应**改变用户手动控制的 UI 状态
    - **判断信号**：组件有 `useState` + `useEffect` 依赖 `location.pathname`/`useNavigate` → 检查是否过度联动（`openKeys`/`expandedKeys` 联动路由视为违规）
    - **修复模式**：`openKeys` 仅在首次挂载时按当前路由初始化（`useState(() => autoOpenKeys)`），之后完全由用户通过 `onOpenChange` 控制，**移除** `useEffect(() => setOpenKeys(autoOpenKeys), [autoOpenKeys])` 联动逻辑
    - **适用**：Menu `openKeys`、Tree `expandedKeys`、Collapse `activeKey`、Drawer `open` 等用户手动控制的 UI 状态
    - **不适用**：`selectedKeys`（应联动路由高亮当前项）、breadcrumb（应联动路由）、页面标题（应联动路由）
    - **历史教训**：MainLayout 的 `openKeys` 通过 `useEffect` 联动 `autoOpenKeys`，sheet 切换触发 `navigate` → URL 变化 → `autoOpenKeys` 重算 → `setOpenKeys` 重置 → SubMenu 展开/折叠动画遮挡内容。第一次修复用"合并"策略仍会展开新 SubMenu，最终改为完全移除 `useEffect` 联动才彻底解决


---

### step 25：跨字段一致性校验【强制】🆕v4.3

25. **跨字段一致性校验【强制】🆕v4.3**
    - 同一实体内多个语义相关联的字段必须在构造时校验一致性，禁止出现矛盾组合
    - **判断信号**：同一 dataclass/dict/type 中存在语义关联字段对（如 `gpu_vendor`+`gpu_renderer`、`valid`+`written_count`、`layer`+`cookies` 分层定义）
    - **修复模式**：在 `__post_init__` / 构造函数 / 工厂函数中校验关联字段一致性，不一致时抛 `ValueError`
    - **适用**：指纹/配置/状态数据结构、Cookie 分层定义、前后端 DTO 字段对齐
    - **不适用**：独立无关联字段、运行时动态拼装的临时对象
    - **历史教训**：`fingerprint.py` Profile 2 的 `gpu_vendor="Intel Inc."` 配 `gpu_renderer="AMD Radeon RX 6600"`，真实 Chrome 中应为 `Google Inc. (AMD)`，被 AWSC fireyejs 识破


---

### step 55：AntD 主题 token 动态覆盖模式【强制】🆕v4.8

55. **AntD 主题 token 动态覆盖模式【强制】🆕v4.8**
    - 项目支持暗色主题（`theme.darkAlgorithm`）时，任何在 `baseTheme.components.<Component>.<token>` 中**显式指定**的主题相关 token（token 名含 `Color` / `Bg` / `Border` / `Hover` / `Active` / `Focus` 后缀）必须根据 `isDark` 状态在能读取 `useTheme()` 的组件（通常是 `ThemedRoot`）内**动态覆盖**，**禁止**依赖 `darkAlgorithm` 自动重算或 `index.css` 中的 `--ant-*` CSS 变量
    - **判断信号**：项目使用 AntD 5.x + 配置 `algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm` + `baseTheme.components.<Component>.<token>` 显式指定了主题相关 token → 必须检查该 token 是否在 `ThemedRoot` 内根据 `isDark` 动态覆盖
    - **核心机制**（必须理解）：
      - antd v5 的 `darkAlgorithm` **仅重算未指定的 token**，显式指定的 token 会被原样继承 → 这是 `baseTheme` 中显式指定的亮色值在暗色主题下失效的根因
      - antd v5 的 `cssVar` 模式**默认未启用**，手动在 `index.css` 中写的 `--ant-*` CSS 变量不被组件引用，是死代码 → 不能依赖 CSS 变量覆盖 token，必须改 `ConfigProvider`
    - **修复模式**（在 `ThemedRoot` 内 spread `baseTheme` 后动态覆盖）：
      ```typescript
      function ThemedRoot() {
        const { isDark } = useTheme()
        return (
          <ConfigProvider
            theme={{
              ...baseTheme,
              algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
              components: {
                ...baseTheme.components,
                Table: {
                  ...baseTheme.components.Table,
                  // darkAlgorithm 不会重算显式指定的 token，故必须在此处动态覆盖
                  // 暗色用品牌色淡橙透明叠加，与卡片背景 #1f1f1f 形成明显对比且与亮色 #fff7f0 调性一致
                  rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : '#fff7f0',
                },
              },
            }}
          >
            <BrowserRouter basename="/xianyu">
              <App />
            </BrowserRouter>
          </ConfigProvider>
        )
      }
      ```
    - **暗色值选择原则**（与品牌色 `#FF6200` 保持视觉一致性）：
      - `Hover` / `Active` 状态色：优先用「品牌色 + 低透明度」叠加（如 `rgba(255, 98, 0, 0.08)`），避免硬编码纯色或过深色
      - 背景色（`Bg` 后缀）：用暗色阶梯色（如 `#1f1f1f` / `#141414`）
      - 文字色（`Color` 后缀）：用 `rgba(255, 255, 255, 0.88)` 或 `#e0e0e0`
      - 边框色（`Border` 后缀）：用 `rgba(255, 255, 255, 0.15)` 等半透明白
    - **注释要求**（注释必须解释「为什么」而非「做什么」）：
      1. 说明 `darkAlgorithm` 不会重算显式 token（避免后续维护者误以为会自动适配）
      2. 说明 WCAG 对比度计算（暗色文字与 hover 背景的对比度需满足 AA 级 ≥ 4.5:1）
      3. 说明品牌色一致性（暗色值与亮色值在视觉调性上保持一致，如都是淡橙调）
    - **配置参数**：`theme_token_whitelist`（主题相关 token 名称后缀白名单：`Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus`）、`dark_value_strategy`（暗色值生成策略：`hover_active=brand_overlay` / `background=dark_step` / `text=white_alpha`）、`brand_color`（默认 `#FF6200`）、`brand_overlay_alpha`（默认 `0.08`）、`wcag_level`（默认 `AA`）在 `config.yaml` 的 `antd_theme_override` 节点管理
    - **诊断流程**（出现「暗色主题下文字看不见/对比度低」类问题时执行）：
      1. `grep "components\\." main.tsx` 扫描所有显式指定的 token
      2. 逐个检查 token 名是否含主题相关后缀（`Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus`）
      3. 对每个主题相关 token，验证是否响应了 `isDark` 动态切换
      4. 若未响应 → 判定为违规，按修复模式动态覆盖
      5. 顺手 `grep "\\-\\-ant-" index.css` 检查是否有死代码 CSS 变量，确认后清理
    - **适用**：AntD 5.x 项目 + 多主题支持（`darkAlgorithm` / `defaultAlgorithm` 切换）+ `baseTheme.components.<Component>.<token>` 显式指定主题相关 token 的场景；WCAG 可访问性合规场景
    - **不适用**：未启用多主题的项目（仅默认亮色）；antd v4 及以下（主题机制不同）；启用了 antd v5 `cssVar: true` 的项目（CSS 变量会生效，可优先用 CSS 变量方案）；非 antd UI 库；与主题无关的 token（`borderRadius`/`fontSize`/`lineHeight` 等 `darkAlgorithm` 会自动适配）
    - **历史教训**：`baseTheme.components.Table.rowHoverBg` 显式指定为 `#fff7f0`（接近白色的淡橙），暗色主题下被原样继承，与暗色文字 `rgba(255, 255, 255, 0.88)≈#e0e0e0`（也接近白色）对比度近乎为零，hover 时文字几乎看不见。同时 `index.css` 中残留的 `--ant-table-row-hover-bg: #262626` 是死代码（未启用 cssVar 模式，不被组件引用）误导了初版诊断。修复后在 `ThemedRoot` 内根据 `isDark` 动态覆盖为 `rgba(255, 98, 0, 0.08)`


---

### step 65：过滤结果可见性规范【强制】🆕v4.11

65. **过滤结果可见性规范【强制】🆕v4.11**
    - 后端过滤链（keyword/price/publish_days/自定义过滤）必须输出完整的 `filter_summary` 结构，前端必须实现三态提示策略并提供"查看被过滤结果"入口，**禁止**只返回 final_total 不暴露过滤过程
    - **关键约束**：
      1. **filter_summary 完整结构**：必须包含 `raw`（原始结果数）/`formatted`（去重后）/各阶段 `*_skipped`（如 `keyword_skipped`/`price_skipped`/`publish_days_skipped`）/`final_total`/`final_items`/`final_sellers`/`filtered_out`（被过滤项详情列表）
      2. **filtered_out 项结构**：每项必须含 `link_type`/`link_key`/`display`/`filter_reason`/`filter_detail`，便于前端按原因分组展示
      3. **filtered_out 数量上限**：为避免响应过大，`filtered_out` 列表长度限制由 `config.yaml` 的 `filter_summary.max_filtered_out_items` 节点管理（默认 `50`），超出部分只计入计数不进入详情
      4. **前端三态提示策略**：
         - `success`（`raw > 0 && final_total > 0`）：`message.success("实时查询完成，获取 N 条")`
         - `warning`（`raw > 0 && final_total == 0`）：`message.warning`，文案必须列出各过滤原因计数（如"搜索到 32 条，但全部被过滤条件筛掉（关键词 5、价格 27），请调整任务过滤配置"）
         - `info`（`raw == 0`）：`message.info("实时查询完成，未找到匹配商品")`
      5. **"查看被过滤结果"入口**：当 `filtered_out` 非空时，前端必须提供按钮（如"查看被过滤的 N 条结果"）+ Modal 展示详情，Modal 内含 Alert（过滤链路统计）+ Table（商品标题/价格/过滤原因 Tag/详情）
      6. **TypeScript 类型显式声明**：API 返回类型必须显式声明 `filter_summary?: LiveFilterSummary`，**禁止**用 `as { filter_summary?: ... }` 强制类型转换绕过 TS 检查
    - **判断信号**：
      - 后端代码含 `if not match_keyword: continue` / `if price > max: continue` 等过滤逻辑 → 必须记录到 `filter_summary`
      - 前端实时搜索结果 `final_total == 0` 但无任何提示 → 视为违规
      - 前端代码含 `(res as { filter_summary?: ... })` 强制类型转换 → 视为违规
    - **修复模式**：
      ```python
      # ✅ 后端：filter_summary 初始化 + 三处过滤记录
      _filter_summary = {
          "raw": 0, "formatted": 0,
          "keyword_skipped": 0, "price_skipped": 0, "publish_days_skipped": 0,
          "final_total": 0, "final_items": 0, "final_sellers": 0,
          "filtered_out": [],  # 限制 50 条
      }
      # keyword 过滤
      if not _match_keyword(r, kw):
          _filter_summary["keyword_skipped"] += 1
          if len(_filter_summary["filtered_out"]) < max_filtered_out_items:
              _filter_summary["filtered_out"].append({
                  "link_type": r.get("link_type"), "link_key": r.get("link_key"),
                  "display": r.get("display"),
                  "filter_reason": "keyword", "filter_detail": f"未匹配关键词 {kw}",
              })
          continue
      ```
      ```typescript
      // ✅ 前端：三态提示 + 类型显式声明
      const fs = res.filter_summary  // 类型已在 live() 返回类型声明
      setLiveFilterSummary(fs || null)
      const itemCount = res.items?.length || 0
      if (itemCount > 0) {
        message.success(`实时查询完成，获取 ${itemCount} 条`)
      } else if (fs && fs.raw > 0) {
        const reasons: string[] = []
        if (fs.keyword_skipped) reasons.push(`关键词 ${fs.keyword_skipped}`)
        if (fs.price_skipped) reasons.push(`价格 ${fs.price_skipped}`)
        if (fs.publish_days_skipped) reasons.push(`发布时间 ${fs.publish_days_skipped}`)
        message.warning(`搜索到 ${fs.raw} 条，但全部被过滤条件筛掉（${reasons.join('、') || '未知原因'}），请调整任务过滤配置`)
      } else {
        message.info('实时查询完成，未找到匹配商品')
      }
      ```
    - **配置参数**：`filter_summary.max_filtered_out_items`（默认 `50`）、`filter_summary.three_state_thresholds`（三态判定阈值：`success_raw_min=1`/`success_final_min=1`/`warning_raw_min=1`/`warning_final_max=0`）、`filter_summary.filter_reason_labels`（过滤原因中文标签映射）在 `config.yaml` 的 `filter_summary` 节点管理
    - **适用**：所有含过滤链路的查询接口（实时搜索/历史查询/列表过滤）；前端展示后端过滤结果的场景
    - **不适用**：无过滤的纯 CRUD 接口；前端纯前端过滤（如 Table 自带筛选）；过滤结果不影响用户体验的场景（如后台日志查询）
    - **历史教训**：实时搜索接口 `final_total=0`（keyword 过滤 32 + price 过滤 27 = 0 最终）但前端只显示"实时查询完成"，用户无法判断是搜索无结果还是被过滤掉，反复调整搜索词无果。修复后添加 `filtered_out` 跟踪 + 三态提示 + "查看被过滤结果"Modal


---

### step 82：前端过滤与后端分类一致性验证【强制】🆕v4.14

82. **前端过滤与后端分类一致性验证【强制】🆕v4.14**
    - 实现前端过滤功能前，必须先查看后端统计分类逻辑，确认分类互斥性。前端过滤结果数量必须与后端统计卡片显示的数字一致，否则用户困惑。例如后端 dist 统计中 insufficient（score==null）与 auto/pass/fail（有评分）互斥，前端过滤必须遵循同样的互斥逻辑
    - **判断信号**：前端新增 filterStatus 过滤条件但未核对后端 insufficient_count/marginals/result 分类逻辑 → 必须先 grep 后端确认分类互斥性；前端过滤后各分类数量之和 ≠ 总数 → 必须对齐分类边界条件
    - **修复模式**：
      1. grep 后端代码确认分类逻辑：`grep -rn "insufficient_count\|marginals\|result\.auto\|result\.pass\|result\.fail" src/`
      2. 确认分类互斥性：`total = insufficient_count + auto + pass + fail`
      3. 前端过滤条件与后端对齐：`score == null → insufficient`，`score >= autoBuyScore → auto`，`passScore <= score < autoBuyScore → pass`，`score < passScore → fail`
      4. 验证：过滤后各分类数量之和等于总数
    - **配置参数**：`filter_backend_align.pass_score`（passScore 阈值，从 config 读取不硬编码）、`filter_backend_align.auto_buy_score`（autoBuyScore 阈值）、`filter_backend_align.category_mapping`（过滤分类映射表）在 `config.yaml` 的 `filter_backend_align` 节点管理
    - **适用**：统计卡片过滤、Tab 分类过滤、状态分组过滤
    - **不适用**：纯前端搜索过滤（无后端分类对应）、非互斥分类（一个记录可属于多个分类）
    - **历史教训**：前端 filterStatus 过滤条件未与后端 dist 统计分类对齐，导致过滤后数量与统计卡片数字不一致，用户困惑


---

### step 83：过滤+分页适配流程【强制】🆕v4.14

83. **过滤+分页适配流程【强制】🆕v4.14**
    - 添加 filterStatus 状态后，必须同步调整 pagination 的 total/current/pageSize 三参数。过滤后 filteredItems 可能少于 pageSize，若不调整分页参数会导致：(1) 分页器显示空页（total 仍是后端返回的全量总数）；(2) 当前页超出 filteredItems 范围显示空白；(3) 用户翻页触发不必要的后端 reload
    - **判断信号**：新增 filterStatus 后 pagination 的 total 仍用后端返回值 → 必须改为 filteredItems.length；过滤后 current 页未重置 → 必须强制为 1；pageSize 未调整导致分页截断 → 必须设为 filteredItems.length 或全量
    - **修复模式**：
      1. `total`: 过滤时用 `filteredItems.length` 而非后端返回的 `total`
      2. `current`: 过滤时强制为 1，不触发后端 reload
      3. `pageSize`: 过滤时设为 `filteredItems.length || 1`（全量显示，避免分页截断遗漏数据）
      4. `showTotal`: 过滤时显示「过滤后 N 条（共 M 条）」区分过滤前后
    - **配置参数**：`filter_pagination_adapt.total_strategy`（默认 `filtered_length`，过滤时 total 取值策略）、`filter_pagination_adapt.current_reset`（默认 `true`，过滤时是否重置到第 1 页）、`filter_pagination_adapt.page_size_strategy`（默认 `all_filtered`，过滤时 pageSize 取值策略）、`filter_pagination_adapt.empty_page_size_fallback`（默认 `1`，空数组 pageSize 兜底值）在 `config.yaml` 的 `filter_pagination_adapt` 节点管理
    - **适用**：前端过滤已加载的分页数据
    - **不适用**：后端分页过滤（filter 参数传给后端，total 自然对齐）
    - **历史教训**：新增 filterStatus 后未调整 pagination 参数，过滤后 current 页超出范围显示空白，用户翻页触发不必要的后端 reload


---

### step 84：空状态边界条件处理规范【强制】🆕v4.14

84. **空状态边界条件处理规范【强制】🆕v4.14**
    - 带过滤功能的列表，空状态判断必须用 filteredItems.length 而非原始 items.length，并区分两种情况。用 items.length 判断时，items 有数据但 filteredItems 过滤后为空，Table 会渲染空数组显示 antd 默认英文空状态，而非项目自定义的中文提示
    - **判断信号**：空状态判断用 `items.length === 0` 但页面有 filterStatus → 必须改为 `filteredItems.length === 0`；空状态文案单一 → 必须区分「无数据」与「过滤后无匹配」两种文案
    - **修复模式**：
      1. 空状态判断用 `filteredItems.length === 0`
      2. 区分两种文案：`items.length === 0 ? '暂无数据' : '当前过滤条件下无匹配记录'`
      3. 验证：过滤后无数据时显示正确文案，清除过滤后恢复列表
    - **配置参数**：`filter_empty_state.empty_text`（默认 `暂无数据`，无数据时文案）、`filter_empty_state.no_match_text`（默认 `当前过滤条件下无匹配记录`，过滤后无匹配时文案）在 `config.yaml` 的 `filter_empty_state` 节点管理
    - **适用**：所有带过滤功能的列表页（评估明细、商品列表、订单列表等）
    - **不适用**：无过滤功能的纯展示列表（直接用 items.length 即可）
    - **历史教训**：空状态判断用 items.length，items 有数据但 filteredItems 为空时 Table 显示 antd 默认英文空状态，而非项目自定义中文提示


---

### step 85：系统行为派生与用户配置正交原则【强制】🆕v4.14

85. **系统行为派生与用户配置正交原则【强制】🆕v4.14**
    - 系统行为（如折叠态列宽自适应）通过 useMemo 派生，不修改通用 hook 的用户配置。用户手动配置的列显隐/排序与系统行为的列宽调整是两个正交的关注点。若系统行为直接修改 useColumnConfig hook 的状态，会污染用户配置，导致折叠展开后用户配置丢失
    - **判断信号**：系统行为（如 panelCollapsed 变化）直接修改 useColumnConfig hook 状态 → 必须改为 useMemo 派生；列宽调整直接写入 hook 的 setColumns → 必须改为返回新数组
    - **修复模式**：
      1. 系统行为派生用 `useMemo` 包裹，依赖系统状态（如 panelCollapsed）
      2. 派生函数返回新数组，不修改原始 columns：`columns.map(col => ({ ...col, width: newWidth }))`
      3. 通用 hook（useColumnConfig）保持不变，系统行为在其外层派生
      4. 验证：折叠/展开后用户配置的列显隐/排序保持不变
    - **配置参数**：`derive_orthogonal.column_width_increment`（默认列宽增量）、`derive_orthogonal.remove_responsive_on_collapse`（默认 `true`，折叠时是否移除 responsive 属性）在 `config.yaml` 的 `derive_orthogonal` 节点管理
    - **适用**：布局变化导致的列宽/列显隐调整（折叠面板、窗口缩放等）
    - **不适用**：用户主动配置的列显隐/排序（直接写入 useColumnConfig）
    - **历史教训**：折叠面板时直接修改 useColumnConfig hook 状态调整列宽，导致用户配置的列显隐/排序被污染，展开后配置丢失


---

### step 95：长耗时异步请求 race condition 防护规范【强制】🆕v4.17

**背景**：Vision 推理 90s 期间用户切换商品，旧请求的 result/error/loading 污染新商品 UI 状态；原 onAIEval（60s）也存在同源问题。

**规范**：
1. 任何 > 3s 的异步请求（LLM Vision/批量采集/重型 DB 查询）必须用 `useRef` 跟踪最新请求 ID
2. 旧请求的 result/error/loading 三态在 setState 前必须校验 `ref.current === itemId`，不匹配则丢弃
3. finally 块同样校验，避免提前关闭新请求的 loading

**判断逻辑**：
- grep 前端 `client.post` / `client.get` 调用看是否有 `timeout` 参数 >= 3000
- 或调用方为 LLM/批量类（`aiApi.deepAnalyze` / `aiApi.evaluateCondition` / `evalApi.batchEvaluate`）
- 有则强制加 `useRef` 防护

**代码模板**：
```typescript
const itemIdRef = useRef('')
const onXxx = async (itemId: string) => {
  itemIdRef.current = itemId
  setLoading(true)
  setResult(null)
  try {
    const result = await api.fetch(itemId)
    if (itemIdRef.current !== itemId) return  // 丢弃过期结果
    setResult(result)
  } catch (err) {
    if (itemIdRef.current !== itemId) return  // 丢弃过期错误
    handleError(err)
  } finally {
    if (itemIdRef.current === itemId) {  // 仅最新请求结束 loading
      setLoading(false)
    }
  }
}
```

**配置参数**：`async_race_condition` 节点（enabled / threshold_ms / detect_patterns / abort_controller_preferred）

**适用场景**：timeout >= 3s 的异步请求 + 用户可触发多次切换商品/任务/对象的场景（Modal 内异步、列表行按钮异步）
**不适用场景**：同步请求（< 1s）；一次性请求（页面加载）；用户无法重复触发（如表单提交后禁用按钮）；请求顺序由用户显式控制（如分页加载）

注：`AbortController` 是更优解但需后端支持取消；`useRef` 方案是通用轻量解，无需后端配合。


---

### step 115：用户偏好类 UI 状态持久化强制复用 usePersistentState 规范【强制】🆕v4.24

**背景**：批量采集页面（`Maintenance/BatchRefresh.tsx`）的「自动刷新」开关使用 `useState(false)`，导致用户每次进入页面或刷新浏览器后开关状态丢失，需要反复手动开启。该开关属于用户偏好类 UI 状态（user preference），应跨会话保留。

**问题**：用户偏好类 UI 状态（自动刷新开关、视图模式、列显隐、折叠状态、最近使用列表等）直接使用 `useState` 存储，状态不跨会话保留；或各组件自行实现 `localStorage` 读写逻辑，逻辑重复且错误处理不一致。

**规范**：

1. **状态分类识别【强制】**：新增 React state 时必须先识别其归属类别：
   - **用户偏好类**（必须用 `usePersistentState`）：开关类（自动刷新、显示已售、折叠/展开）、视图模式（密度/列宽/列显隐）、主题偏好、最近使用列表、记住上次选中项
   - **业务数据类**（必须走后端 API）：任务列表、订单状态、配置项（`enabled`/`interval_minutes` 等已通过后端 PATCH /config 持久化的字段）
   - **会话状态类**（必须走 Zustand store）：登录态、当前选中项、跨页共享状态
   - **临时状态类**（必须用 `useState`）：loading、modal open、按钮 submitting、表单 dirty
   - **敏感数据类**（必须走 secure storage / httpOnly cookie）：token、密码、API key

2. **强制复用既有 hook【强制】**：用户偏好类 UI 状态必须使用项目既有 `frontend/src/hooks/usePersistentState.ts`，禁止：
   - 裸 `useState` 存储用户偏好（判别信号：刷新页面/路由切换后状态丢失即违规）
   - 各组件自行实现 `localStorage.getItem/setItem` 逻辑
   - 引入第三方持久化库（项目已有统一封装）

3. **key 命名规范【强制】**：localStorage key 必须遵循 `xh.<page>.<field>` 命名模式（与项目既有命名一致）：
   ```typescript
   // ✅ 正确：遵循 xh.<page>.<field> 命名
   const [autoRefresh, setAutoRefresh] = usePersistentState<boolean>(
     'xh.batchRefresh.autoRefresh',
     false,
     { validator: (v): v is boolean => typeof v === 'boolean' },
   )
   
   // ❌ 错误：无前缀/无命名规范
   const [autoRefresh, setAutoRefresh] = usePersistentState('autoRefresh', false)
   ```

4. **validator 必填【强制】**：必须传入 `validator` 选项防止 localStorage 脏数据（旧版本数据、用户手动修改、其他项目同名 key）导致 UI 异常：
   ```typescript
   // ✅ 正确：validator 防御脏数据
   usePersistentState<T>(key, defaultValue, {
     validator: (v): v is T => /* 类型与边界检查 */,
   })
   ```

5. **localStorage 不可用自动回退【强制】**：依赖 `usePersistentState` 内置的内存回退机制（隐私模式 / 存储已满 / 被禁用场景下功能不中断），禁止在业务代码中再 try-catch `localStorage` 调用。

6. **不重复持久化后端已持久化字段【强制】**：若字段已通过后端 API 持久化（如批量采集的 `enabled` / `interval_minutes` 已通过 `PATCH /api/batch-refresh/config` 持久化），前端不得再用 `usePersistentState` 重复持久化，否则会导致前后端不一致：
   - 前端从后端 `GET /status` 读取并填入 Form
   - 表单 dirty 标记保护用户编辑中的值不被轮询覆盖
   - 用户点击「保存」时 `PATCH /config` 提交到后端

**配置驱动**：用户偏好类关键词、检测模式、检查信号等参数在 `xianyu-frontend-code-review` 的 `config.yaml` 的 `ui_preference_persistence` 节点管理（详见 `xianyu-frontend-code-review` v4.24.0 的 `F-REVIEW-UI-PREFERENCE-PERSISTENCE`），不硬编码在技能中。

**适用场景**：
- 用户偏好类 UI 状态（自动刷新、视图模式、列显隐、折叠/展开、主题偏好、最近使用列表、记住上次选中项）
- 跨会话需要保留的 UI 偏好
- 用户重复进入页面希望延续上次设置的场景

**不适用场景**：
- 业务数据（任务列表、订单状态、配置项）—— 必须走后端 API
- 会话状态（登录态、当前选中项）—— 必须走 Zustand store
- 临时状态（loading、modal open、表单 submitting）—— 必须用 `useState`
- 敏感数据（token、密码、API key）—— 必须走 secure storage / httpOnly cookie
- 已通过后端持久化的字段（如 `enabled` / `interval_minutes`）—— 不重复持久化避免前后端不一致

**历史教训**：`Maintenance/BatchRefresh.tsx` 的 `autoRefresh` 开关使用 `useState(false)`，每次刷新页面开关重置为关闭，用户需要反复手动开启。修复方式：替换为 `usePersistentState<boolean>('xh.batchRefresh.autoRefresh', false, { validator: ... })`，复用项目既有 `hooks/usePersistentState.ts`（含防抖写入、数据验证、localStorage 不可用回退到内存 Map）。

**判断信号（review 触发条件）**：
- `grep "useState(false)$" frontend/src/pages/**/*.tsx` 命中用户偏好类变量名（含 `autoRefresh`/`viewMode`/`columnConfig`/`density`/`collapsed`/`expandedKeys`/`themePreference`/`recentItems` 等关键词）
- 用户反馈"刷新页面后开关/设置丢失"
- 用户反馈"每次进入页面都需要重新设置"


---

### step 121：前端错误处理规范【强制】🆕v4.26

**背景**：前端 API 调用的 catch 块必须用统一错误提取工具（`extractApiError`），显示具体错误信息（含状态码 + 详情）。

**问题**：前端 API 调用的 catch 块只显示 `message.error('保存失败')` 等无具体信息的错误提示，用户无法区分网络错误/验证错误/服务器错误，难以排查问题。

**规范**：

1. **统一错误提取【强制】**：API 调用的 catch 块必须用项目统一的 `extractApiError` 工具提取错误信息：
   ```typescript
   // ✅ 正确：用 extractApiError 显示具体错误信息，时长 5 秒
   catch (e) {
     message.error(extractApiError(e), 5);
   }

   // ❌ 错误：无具体信息的错误提示
   catch (e) {
     message.error('保存失败');
   }
   ```

2. **错误显示时长【强制】**：错误显示时长不少于 5 秒（配置驱动），保证用户有时间阅读。

3. **禁止无信息提示【强制】**：禁止 `message.error('保存失败')` / `message.error('操作失败')` 等无具体信息的错误提示。

**配置驱动**：错误显示时长、错误提取函数名、禁止的错误模式等参数在 `config.yaml` 的 `frontend_error_handling` 节点管理，包含 `error_display_duration_sec` / `required_error_extractor` / `forbidden_error_patterns` 等，不硬编码在技能中。

**适用场景**：
- 所有含 try/catch 的 API 调用
- 表单提交、配置保存、数据获取等可能失败的操作

**不适用场景**：
- 非 API 错误（如本地计算错误、表单验证错误）
- 已知预期错误（如取消操作）

**历史教训**：`TaskEditor.tsx` 的 `doSubmit` catch 块只显示 `message.error('保存失败')`，用户无法区分网络错误/验证错误/服务器错误，排查困难。修复：改用 `extractApiError(e)` + 5 秒显示时长。

**判断信号（review 触发条件）**：
- `grep "message.error('"` 不含 `extractApiError` 的 catch 块
- `grep "catch (e)"` 后跟 `message.error('xxx失败')` 等无信息提示


---

### step 122：默认值操作符规范【强制】🆕v4.26

**背景**：默认值场景统一用 `??`（nullish coalescing），只有需要同时过滤 `0`/`''`/`false` 时才用 `||`（logical or）。

**问题**：默认值场景混用 `||` 和 `??`，`||` 会将 `0`/`''`/`false` 也视为 falsy，可能导致意外行为（如 `v=0` 时被误判为 falsy 返回默认值）。

**规范**：

1. **默认值统一用 ??【强制】**：默认值场景必须用 `??`（nullish coalescing），只将 `null/undefined` 视为 falsy：
   ```typescript
   // ✅ 正确：v=0 时保留 0，v=null 时返回 1
   onChange={(v) => update({ qps: v ?? 1 })}

   // ❌ 错误：v=0 时会被误判为 falsy，返回 1
   onChange={(v) => update({ qps: v || 1 })}
   ```

2. **|| 仅用于过滤场景【强制】**：只有需要同时过滤 `0`/`''`/`false` 时才用 `||`（如空字符串转默认值、0 转默认值）：
   ```typescript
   // ✅ 正确：需要过滤空字符串时用 ||
   const name = inputName || 'default';
   ```

3. **风格一致性【强制】**：同一组件/模块内默认值操作符必须风格一致，禁止混用 `||` 和 `??` 导致语义不一致。

**配置驱动**：默认值操作符选择规则、例外场景清单、检测模式等参数在 `config.yaml` 的 `default_operator` 节点管理，包含 `preferred_operator` / `logical_or_exceptions` / `detection_patterns` 等，不硬编码在技能中。

**适用场景**：
- 所有提供默认值的表达式（InputNumber onChange、函数参数默认值、变量初始化）

**不适用场景**：
- 需要同时过滤 `0`/`''`/`false` 的场景（如空字符串转默认值、0 转默认值）
- 布尔逻辑判断（应用 `&&` / `||` 的本意）

**历史教训**：`GlobalAntidetectConfigModal` 中 `qps: v || 1`、`fail_pause_threshold: v || 3`、`fail_window_sec: v || 3600` 用 `||`，而 `min_delay_ms: v ?? 200`、`max_delay_ms: v ?? 1500` 用 `??`，风格不一致。虽然 InputNumber 的 min 约束保证 0 不会发生，但 `??` 语义更准确。修复：统一改为 `??`。

**判断信号（review 触发条件）**：
- `grep "|| "` 在 onChange/默认值场景中，检查是否有更准确的 `??` 替代
- 同一组件内混用 `||` 和 `??` 的默认值场景


---

### step 159：EFFECT-01 useEffect 副作用清理与依赖完整性规范【强制】🆕v4.29

**背景**：组件卸载后异步回调仍调用 `setState`，触发 `Can't perform a React state update on an unmounted component` 警告；useEffect 依赖数组遗漏导致闭包捕获旧值。

**问题**：useEffect 中发起异步请求/订阅事件/定时器时，未在 cleanup 函数中取消，组件卸载后回调仍执行 setState 导致内存泄漏与警告；依赖数组遗漏导致闭包捕获过期的 props/state。

**规范**：

1. **副作用必须清理【强制】**：useEffect 中发起的异步请求/定时器/事件订阅必须在 cleanup 中取消：
   ```typescript
   // ✅ 正确：用 AbortController 取消异步请求
   useEffect(() => {
     const controller = new AbortController();
     fetchData({ signal: controller.signal });
     return () => controller.abort();
   }, [deps]);

   // ❌ 错误：无 cleanup，卸载后 setState
   // useEffect(() => { fetchData().then(setData); }, [deps]);
   ```

2. **依赖数组完整性【强制】**：useEffect 依赖数组必须包含所有响应式依赖（props/state/derived），禁止遗漏导致闭包捕获旧值；如需排除某依赖，必须用 `useRef` 或注释说明原因。

3. **卸载守卫【强制】**：异步回调中调用 setState 前必须检测组件是否已卸载（用 `useRef` 标志位或 AbortController）：
   ```typescript
   const mountedRef = useRef(true);
   useEffect(() => {
     mountedRef.current = true;
     return () => { mountedRef.current = false; };
   }, []);
   // 异步回调中：if (mountedRef.current) setData(result);
   ```

**配置驱动**：`coding_standards.effect.cleanup_required`（`true`）、`dependency_check`（`exhaustive`）在 `config.yaml` 管理。

**适用场景**：
- useEffect 中发起异步请求/定时器/事件订阅
- 组件卸载后不应再更新状态
- 闭包捕获响应式依赖

**不适用场景**：
- 同步副作用（无异步回调，无需 cleanup）
- 仅在 mount 时执行一次的初始化（依赖数组为 []）

**历史教训**：组件卸载后异步 fetch 回调仍调用 setState，控制台持续警告；依赖数组遗漏 `filterValue`，列表显示旧过滤结果。

**判断信号（review 触发条件）**：
- `grep "useEffect" <tsx>` 无 return cleanup 函数
- `Can't perform a React state update on an unmounted component` 警告
- useEffect 依赖数组少于实际使用的响应式变量


---

### step 160：SSE-01 SSE 事件流生命周期管理规范【强制】🆕v4.29

**背景**：EventSource 连接未在组件卸载时关闭，导致连接泄漏；SSE 重连时未清理旧连接，多个 EventSource 并发推送导致重复渲染。

**问题**：EventSource 是长连接资源，未正确关闭即泄漏连接；重连逻辑未先关闭旧连接即新建，导致多个连接并发推送同一事件，UI 重复更新。

**规范**：

1. **EventSource 必须在 cleanup 中关闭【强制】**：
   ```typescript
   useEffect(() => {
     const es = new EventSource('/api/events/stream');
     es.onmessage = (e) => handleEvent(JSON.parse(e.data));
     return () => { es.close(); };  // 卸载时关闭
   }, []);
   ```

2. **重连前必须关闭旧连接【强制】**：重连逻辑必须先 `es.close()` 再新建 EventSource，禁止并发多个连接。

3. **SSE 事件去重【强制】**：事件处理必须用事件 ID 去重（`lastEventId`），防止重连后重复处理已处理事件。

**配置驱动**：`coding_standards.sse.reconnect_delay`（重连延迟）、`dedup_by_event_id`（`true`）在 `config.yaml` 管理。

**适用场景**：
- EventSource / SSE 事件流订阅
- 实时通知/状态推送
- WebSocket 长连接管理

**不适用场景**：
- 一次性 HTTP 请求（无长连接）
- 轮询场景（用 setInterval，非 SSE）

**历史教训**：通知中心组件卸载后 EventSource 未关闭，浏览器 Network 面板显示数十个 pending 连接；重连时未关闭旧连接，同一通知被处理多次。

**判断信号（review 触发条件）**：
- `grep "new EventSource" <tsx>` 后无 `es.close()` 在 cleanup
- 浏览器 Network 面板多个 pending EventSource 连接
- 同一事件被处理多次（无去重）


---

### step 161：THEME-01 AntD 主题 token 单一数据源规范【强制】🆕v4.29

**背景**：AntD 主题 token（主色/圆角/间距）散落在多个 ConfigProvider 与组件 style 中，调整主题需修改多处，且多处覆盖导致最终 token 不确定。

**问题**：主题 token 散落多处时，全局主题调整需逐文件修改；嵌套 ConfigProvider 的 token 覆盖关系不明确，最终渲染 token 难以预测。

**规范**：

1. **主题 token 集中定义【强制】**：主题 token 必须集中到单一主题配置文件（如 `theme/index.ts`），禁止散落在组件 ConfigProvider 或 style 中：
   ```typescript
   // theme/index.ts
   export const themeConfig: ThemeConfig = {
     token: { colorPrimary: '#1677ff', borderRadius: 8 },
     components: { Button: { borderRadius: 8 } },
   };

   // App.tsx 唯一消费点
   <ConfigProvider theme={themeConfig}>...</ConfigProvider>
   ```

2. **禁止嵌套 ConfigProvider 覆盖 token【强制】**：禁止在子组件用 ConfigProvider 覆盖全局 token，如需局部主题必须从主题文件导出子主题。

3. **token 变更必须 grep 全局【强制】**：token 变更时必须 grep 确认无组件硬编码颜色/圆角值。

**配置驱动**：`coding_standards.theme.single_source`（`true`）、`forbid_nested_config_provider`（`true`）在 `config.yaml` 管理。

**适用场景**：
- AntD 主题配置（主色/圆角/间距/字体）
- 多页面统一主题
- 暗色/亮色主题切换

**不适用场景**：
- 一次性营销页面（独立主题，不复用全局 token）
- 第三方组件库的主题（无法控制）

**历史教训**：主色 `#1677ff` 在 3 个 ConfigProvider 与 5 个组件 style 中重复定义，调整主色需修改 8 处；嵌套 ConfigProvider 覆盖导致按钮圆角不一致。

**判断信号（review 触发条件）**：
- `grep "ConfigProvider" <tsx>` 出现多处 theme prop
- `grep "colorPrimary\|borderRadius" <tsx>` 散落在组件 style
- 同一 token 在多处硬编码不同值


---

### step 162：LAYOUT-01 布局响应式与最小宽度规范【强制】🆕v4.29

**背景**：表格/表单用固定宽度（如 `width: 1200px`），在窄屏下横向滚动错位；侧边栏折叠态未调整内容区宽度，导致内容被截断。

**问题**：固定宽度布局在不同屏幕尺寸下错位；响应式断点散落在多处导致不一致；侧边栏折叠态未同步调整内容区，内容溢出或截断。

**规范**：

1. **布局用响应式单位【强制】**：布局宽度必须用百分比 / fr / clamp() / AntD Grid，禁止固定像素宽度（除边框/分隔线）：
   ```typescript
   // ✅ 正确：响应式宽度
   <Col xs={24} md={12} lg={8}>...</Col>
   const width = 'clamp(320px, 80vw, 1200px)';

   // ❌ 错误：固定宽度
   // <div style={{ width: 1200 }}>...</div>
   ```

2. **断点集中管理【强制】**：响应式断点必须集中到主题配置或常量，禁止散落多处硬编码 media query。

3. **折叠态同步内容区【强制】**：侧边栏折叠/展开时必须同步调整内容区宽度（用 CSS variable 或 Grid 布局自动适配），禁止内容区固定宽度。

**配置驱动**：`coding_standards.layout.breakpoints`（断点清单）、`forbid_fixed_width`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 表格/表单/卡片布局
- 侧边栏 + 内容区布局
- 多屏幕尺寸适配（桌面/平板/移动）

**不适用场景**：
- 图标/按钮等固定尺寸组件（用固定像素合理）
- 打印布局（固定尺寸）

**历史教训**：任务列表表格用 `width: 1200px`，在 1366 屏幕下横向滚动错位；侧边栏折叠后内容区未收缩，表格右侧被截断。

**判断信号（review 触发条件）**- `grep "width: \d{4}" <tsx>` 出现固定大宽度
- `grep "@media" <tsx>` 断点散落多处
- 窄屏下横向滚动或内容截断


---

### step 163：REGISTRY-01 注册表单一数据源规范【强制】🆕v4.29

**背景**：`sheetRegistry.tsx`（path → component 映射）与 `MainLayout.tsx` 的 `menuItems` 不同步，新增页面时只改一处导致路由可达但菜单不显示，或菜单显示但路由 404。

**问题**：页面注册信息分散在多处（路由表/菜单项/sheet 注册表）时，新增/修改页面需同步多处，漏改即导致路由与菜单不一致。

**规范**：

1. **注册表单一数据源【强制】**：页面注册信息（path/title/icon/component/menuOrder）必须集中到单一注册表，路由表与菜单项从注册表派生：
   ```typescript
   // sheetRegistry.tsx 唯一数据源
   export const sheetRegistry = [
     { path: '/tasks', title: '任务', icon: <UnorderedListOutlined />, component: lazy(() => import('./Tasks')), menuOrder: 1 },
   ];

   // App.tsx 路由从注册表派生
   {sheetRegistry.map(s => <Route path={s.path} element={<s.component />} />)}

   // MainLayout.tsx 菜单从注册表派生
   const menuItems = sheetRegistry.map(s => ({ key: s.path, label: s.title, icon: s.icon }));
   ```

2. **新增页面只改注册表【强制】**：新增页面时只修改注册表，路由表与菜单自动派生，禁止分别修改。

3. **注册表变更必须 grep 验证【强制】**：注册表变更后必须 grep 确认路由与菜单无遗漏引用。

**配置驱动**：`coding_standards.registry.single_source`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 页面/路由/菜单注册
- Sheet/Tab 注册
- 权限项与菜单项映射

**不适用场景**：
- 动态路由（如 `/tasks/:id`，需独立定义）
- 临时页面（不在菜单显示）

**历史教训**：新增「评估明细」页面时只改了 `App.tsx` 路由，未改 `MainLayout.tsx` 菜单，用户反馈「找不到入口」；后续修复时只改菜单未改路由，点击菜单 404。

**判断信号（review 触发条件）**：
- `sheetRegistry` 与 `menuItems` 数量不一致
- 路由表与菜单项分别硬编码
- 用户反馈「菜单点击 404」或「找不到入口」


---

### step 164：FILTER-02 过滤条件与分页状态同步规范【强制】🆕v4.29

**背景**：列表页添加 `filterStatus` 过滤后未同步调整 `pagination.total`，分页仍用原始 `items.length`，导致过滤后页数错误、空页显示。

**问题**：过滤条件与分页状态是耦合关系，过滤变更后必须重置页码并更新 total，否则分页基于原始数据导致空页或页码越界。

**规范**：

1. **过滤变更必须重置页码【强制】**：`filterStatus` 变更时必须 `setPage(1)`，防止过滤后当前页越界：
   ```typescript
   const onFilterChange = (status) => {
     setFilterStatus(status);
     setPage(1);  // 重置到第一页
   };
   ```

2. **分页 total 必须用过滤后长度【强制】**：`pagination.total` 必须用 `filteredItems.length` 而非原始 `items.length`：
   ```typescript
   const filteredItems = useMemo(
     () => items.filter(i => i.status === filterStatus),
     [items, filterStatus]
   );
   const pagination = { total: filteredItems.length, current: page, pageSize: 20 };
   ```

3. **空状态区分【强制】**：必须区分「无数据」与「过滤后无匹配」两种文案，用 `filteredItems.length === 0` 判断而非 `items.length === 0`。

**配置驱动**：`coding_standards.filter.pagination_sync`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 列表页过滤 + 分页
- 搜索 + 分页
- Tab 切换 + 分页

**不适用场景**：
- 无分页的列表（仅过滤）
- 后端分页（total 由后端返回，无需前端同步）

**历史教训**：评估明细列表添加 `filterStatus` 后未重置页码，用户在第 5 页切换过滤，filteredItems 不足 5 页，显示空列表；total 仍用原始 280 条，分页器显示 14 页但实际只有 3 页有数据。

**判断信号（review 触发条件）**：
- `grep "filterStatus" <tsx>` 后无 `setPage(1)`
- `pagination.total` 用 `items.length` 而非 `filteredItems.length`
- 过滤后显示空列表但分页器有页码


---

### step 165：UI-SEMANTICS-01 UI 语义与行为一致性规范【强制】🆕v4.29

**背景**：按钮文案「立即采集」但实际行为是「加入队列」，用户点击后未见立即执行即认为按钮失效；「保存」按钮实际触发「保存并启动」，语义与行为不符导致误操作。

**问题**：UI 文案（按钮/菜单/提示）与实际行为不一致时，用户预期与系统行为错位，导致误操作或重复点击；错误提示文案与根因不符，误导排查方向。

**规范**：

1. **文案与行为语义一致【强制】**：按钮/菜单/操作的文案必须与实际行为语义一致，禁止「立即」对应「排队」、「保存」对应「保存并启动」：
   ```typescript
   // ✅ 正确：文案与行为一致
   <Button onClick={collectNow}>立即采集</Button>  // 同步执行
   <Button onClick={enqueue}>加入队列</Button>      // 异步排队

   // ❌ 错误：文案与行为不符
   // <Button onClick={enqueue}>立即采集</Button>  // 实际是排队，用户以为失效
   ```

2. **错误提示与根因一致【强制】**：错误提示文案必须与实际根因一致，禁止「网络错误」对应「权限不足」、「保存失败」对应「字段校验失败」。

3. **二次确认与破坏性操作匹配【强制】**：破坏性操作（删除/覆盖/停止）必须二次确认，且确认文案明确说明后果；非破坏性操作禁止二次确认（避免干扰）。

**配置驱动**：`coding_standards.ui_semantics.label_behavior_match`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 按钮/菜单/操作文案
- 错误提示文案
- 二次确认对话框

**不适用场景**：
- 内部工具（用户熟悉系统行为）
- 实验性功能（文案标注「实验性」即可）

**历史教训**：「立即采集」按钮实际是加入队列，用户点击后未见立即执行，重复点击导致队列堆积；「保存」按钮实际触发「保存并启动」，用户只想保存配置却意外启动了任务。

**判断信号（review 触发条件）**：
- 用户反馈「点击无效」但实际已入队
- 用户反馈「误操作」但文案未提示后果
- 错误提示文案与日志根因不符


---

### step 166：SOURCE-01 前端数据源单一可信源规范【强制】🆕v4.29

**背景**：同一数据（如任务列表）在 Zustand store 与组件本地 state 各获取一次，两端数据不一致；store 更新后本地 state 未同步，UI 显示旧数据。

**问题**：同一数据多处获取/存储时，一处更新未同步到其他源即导致数据不一致；TTL 兜底与主动 refetch 混用导致数据时效性不确定。

**规范**：

1. **单一可信源【强制】**：同一数据必须只有一个可信源（Zustand store 或组件本地 state，二选一），禁止多处分别获取：
   ```typescript
   // ✅ 正确：store 为唯一可信源，组件从 store 读
   const tasks = useTaskStore(s => s.tasks);

   // ❌ 错误：store 与本地 state 分别获取
   // const storeTasks = useTaskStore(s => s.tasks);
   // const [localTasks, setLocalTasks] = useState([]);
   // useEffect(() => { fetchTasks().then(setLocalTasks); }, []);
   ```

2. **统一 refetch 策略【强制】**：数据刷新必须统一通过 store action（`refetchTasks()`），禁止组件自行 fetch 后 setState。

3. **SSE 推送更新 store【强制】**：SSE 事件推送的数据更新必须写入 store，禁止组件直接订阅 SSE 更新本地 state。

**配置驱动**：`coding_standards.data_source.single_source`（`true`）、`forbid_ttl_fallback`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 列表数据（任务/订单/通知）
- 详情数据（同一详情多处展示）
- 跨组件共享数据

**不适用场景**：
- 组件内部临时状态（如编辑中的表单值）
- 派生数据（用 useMemo 从 store 派生）

**历史教训**：任务列表在 store 与 `Tasks/index.tsx` 本地 state 各获取一次，store 更新后本地 state 未同步，用户看到旧列表；TTL 兜底与 SSE 推送混用，数据时效性不确定。

**判断信号（review 触发条件）**：
- 同一数据在 store 与 useState 分别获取
- 组件自行 fetch 后 setState 而非调用 store action
- TTL 兜底与主动 refetch 混用

---

### step 181：注册式资源三件套契约【强制，meta-rule #33 落地】

181. **注册式资源三件套契约【强制，meta-rule #33 落地】**
   - **5 层契约**：任何用户可点击/可导航的功能入口，必须在 5 层都注册完整：
     - L1 菜单注册：`config/menu_registry.yaml` 含 `path` 字段
     - L2 路由注册：`frontend/src/App.tsx` 含 `<Route path="<path>">`
     - L3 页面文件：`frontend/src/pages/<域>/index.tsx` 存在
     - L4 API wrapper：`frontend/src/api/<域>.ts` 导出 `<域>Api`
     - L5 后端 endpoint：`src/xianyu_hunter/web/routes/api_<域>.py` 含 `@router.<method>`
   - **任一层缺失 = CRITICAL 阻断级**：
     - L1 缺：用户看不到入口（侧边栏无菜单）
     - L2 缺：用户看到菜单但点击无反应（route fallback 静默重定向）—— 本轮"通知中心菜单点击无反应"bug 根因
     - L3 缺：路由命中但页面空白/红屏
     - L4 缺：页面加载但所有请求报错
     - L5 缺：前端 404 一直报 "Network Error"
   - **配置驱动**：所有 5 层校验规则在 `config.yaml` 的 `frontend_registration_completeness` 节点管理（`required_layers` / `fail_on_missing_layer` / `exemption_list`）
   - **自动化校验**：CI + 提交前 hook 必跑 `python scripts/check_registration.py`，退出码 0 才算通过
   - **豁免清单**：草稿/实验性 feature 可临时跳过，但 `expires` 必填，到期未移除 = CRITICAL
   - **适用场景**：任何 SPA + 后端 API 架构，且有用户导航菜单的项目
   - **不适用**：纯静态页、SSR（菜单由后端渲染）、单页 CLI、嵌入式
   - **历史教训**：2026-07-06 通知中心菜单点击无反应——menu_registry 注册了 path=/notifications，但 App.tsx 无路由、pages/Notifications 目录不存在、api/notifications.ts 不存在
   - **修复模式**：
     ```bash
     # 1. 跑校验脚本
     python .trae/skills/xianyu-hunter-dev/scripts/check_registration.py
     # 2. 看到 "❌ /notifications: 缺层 L2/L3/L4" 提示
     # 3. 补全缺失层（参考模板 assets/templates/typescript/）
     # 4. 重跑脚本，退出码 0
     ```
   - **判断信号**：
     - `python scripts/check_registration.py` 退出码非 0 → 视为 CRITICAL
     - `grep "path: '/notifications'" config/menu_registry.yaml` 命中但 `grep 'path="notifications"' frontend/src/App.tsx` 失败 → L1 有 L2 无 → CRITICAL
     - `Glob "frontend/src/pages/Notifications/index.tsx"` 失败但 App.tsx 有 `path="notifications"` 的 Route 引用 → L3 缺失 → CRITICAL
   - **完整规范**：参见 [references/registration-completeness.md](../../../references/registration-completeness.md)

---

### step 193：过滤结果透明化 UI 规范【强制，meta-rule #56 落地】🆕v4.37

193. **过滤结果透明化 UI 规范【强制，meta-rule #56 落地】🆕v4.37**
    - 列表查询 UI 同时有 ≥2 个过滤参数（价格区间 + 市场比例 + 任务范围）时，必须透明化展示当前生效的过滤规则组合，否则用户无法理解"为何查不到数据"
    - **与 step 65 过滤结果可见性规范的边界**：
      - step 65 关注"后端 filter_summary 结构 + 前端三态提示"
      - 本规范关注"前端透明化展示当前生效的过滤组合 + 参数语义化"
    - **与 step 82 前端过滤与后端分类一致性验证的边界**：
      - step 82 关注"过滤分类与后端统计对齐"
      - 本规范关注"过滤规则本身的可见性"
    - **四要素**：
      | 要素 | 说明 | 示例 |
      |------|------|------|
      | Tooltip 说明 | 关键过滤参数提供 Tooltip 说明查询规则 | 价格范围 label 旁加 `QuestionCircleOutlined` + Tooltip |
      | filter_summary 三态 | 空结果时区分"无数据"vs"被过滤排除"vs"全部数据" | `raw=0` → 无数据；`raw>0 && final=0` → 被过滤；`raw>0 && final>0` → 部分数据 |
      | 当前过滤组合展示 | UI 显式列出当前生效的过滤参数组合 | "当前过滤：价格 600-800 + 市场比例 ≤0.85" |
      | 参数语义化 | 业务参数展示语义化文案而非原始数值 | `market_ratio=0.85` → "低于市场参考价 15%" |
    - **判断信号**：
      - `grep "filter.*range\|market.*ratio\|min.*max"` 在列表 UI 但无 `Tooltip` / `filter_summary` → 违规
      - `grep "empty.*data\|no.*data"` 但无 `filtered_count` / `total_count` 区分 → 违规
      - 参数展示仅 `value` 无 `label` / `description` → 不友好
    - **修复模式**：
      ```tsx
      // ✅ 正确：Tooltip 说明 + 当前过滤组合展示 + 参数语义化
      function PriceRangeFilter({ value, onChange }) {
        return (
          <Form.Item
            label={
              <Space>
                <span>价格范围</span>
                <Tooltip title="价格区间 + 低于市场参考价参数取值（如设置 0.85 表示低于市场参考价 15%）">
                  <QuestionCircleOutlined />
                </Tooltip>
              </Space>
            }
          >
            <RangeSlider value={value} onChange={onChange} />
          </Form.Item>
        )
      }

      function FilterSummaryBar({ filterSummary, currentFilters }) {
        // 当前过滤组合展示
        const activeFilters = [
          currentFilters.priceRange && `价格 ${currentFilters.priceRange[0]}-${currentFilters.priceRange[1]}`,
          currentFilters.marketRatio && `低于市场参考价 ${Math.round((1 - currentFilters.marketRatio) * 100)}%`,
        ].filter(Boolean)

        if (activeFilters.length === 0) return null

        return (
          <Alert
            type="info"
            message={`当前过滤：${activeFilters.join(' + ')}`}
            description={filterSummary.raw > 0 && filterSummary.final_total === 0
              ? `搜索到 ${filterSummary.raw} 条，但全部被过滤条件筛掉，请调整过滤配置`
              : undefined}
          />
        )
      }

      // ❌ 错误：仅显示数值无语义
      // <span>{marketRatio}</span>  // 显示 0.85 而非 "低于市场参考价 15%"
      ```
    - **配置参数**：`filter_transparency.tooltip_required`（默认 `true`，强制关键过滤参数加 Tooltip）、`filter_transparency.three_state_required`（默认 `true`，强制 filter_summary 三态展示）、`filter_transparency.current_filter_bar`（默认 `true`，显示当前过滤组合 Alert）、`filter_transparency.semantic_label_map`（业务参数 → 语义化文案映射，如 `market_ratio: "低于市场参考价 {percent}%"`）、`filter_transparency.min_filter_count`（默认 `2`，≥2 个过滤参数才触发透明化）在 `config.yaml` 的 `filter_transparency` 节点管理
    - **适用**：所有多参数列表查询 UI（评估明细 / 商品列表 / 订单列表 / 仪表盘过滤）
    - **不适用**：单一过滤参数（如仅搜索关键字）、用户主动输入的查询条件（用户已知）、详情页（无过滤）
    - **历史教训**：用户调整"低于市场参考价"到 0.85 后，评估明细菜单仍能查出价格上限 800 的商品，且 UI 无任何提示当前生效的过滤规则。用户误以为是价格范围 600-800 的问题，实际是 market_ratio 过滤未生效。修复：在价格范围 label 处添加 `QuestionCircleOutlined` 图标 + Tooltip 说明查询规则（价格区间 + 低于市场参考价参数取值），并展示当前过滤组合 Alert


---

### step 236：操作项分级保留规范【强制，meta-rule #83 落地】🆕v4.49.0

236. **操作项分级保留规范【强制，meta-rule #83 落地】🆕v4.49.0**
    - 单行/单卡操作按钮总数 > `uiLayout.actionButtonVisibleThreshold`（默认 5）时，必须按使用频率分级保留：高频保留文字按钮 / 中频转图标 + Tooltip / 低频收入收起容器
    - **四要素**：
      | 要素 | 说明 | 示例 |
      |------|------|------|
      | 频率统计 | 每月平均使用次数从埋点或运营反馈获取，< `lowFrequencyThresholdPerMonth`（默认 1）判定低频 | "另存为模板" 月均 0.3 次 → 低频 |
      | 分级映射 | 高频 → 文字按钮；中频 → 图标 + Tooltip；低频 → 收入 Dropdown/Popover/Drawer | 编辑/启停/删除 → 文字；复制 → 图标；另存为模板 → Dropdown |
      | 容器选择 | 由 `uiLayout.collapseContainerStrategy` 配置驱动（≤3 → Dropdown / 3-6 → Popover / >6 → Drawer） | 收起 1 个低频按钮 → Dropdown |
      | 文案保留 | 收起容器内的按钮文案必须与原文字按钮完全一致，禁止改写 | "另存为模板" 收起后仍为 "另存为模板" |
    - **判断信号**：
      - `grep "<Button" <page>.tsx` 在单个 `<Space>` / `actions=` 内计数 > `actionButtonVisibleThreshold`（默认 5）→ 违规
      - `grep "<Button" <page>.tsx` 计数 ≥ 6 且无 `<Dropdown` / `<Popover` / `<Drawer` → 违规
      - 收起容器内的按钮文案与原文字按钮不一致 → 违规
    - **修复模式**：
      ```tsx
      // ✅ 正确：高频文字 + 中频图标 + 低频 Dropdown，操作列宽度从 580px 降到 380px
      <Space>
        <Button type="link" onClick={handleEdit}>编辑</Button>
        <Button type="link" onClick={handleToggle}>{running ? '暂停' : '启动'}</Button>
        <Button type="link" onClick={handleStop}>停止</Button>
        <Button type="link" icon={<CopyOutlined />} onClick={handleCopy}>
          <Tooltip title="复制" />
        </Button>
        <Button type="link" danger onClick={handleDelete}>删除</Button>
        <Dropdown menu={{ items: [{ key: 'save-as-template', label: '另存为模板', onClick: handleSaveAsTemplate }] }}>
          <Button type="link" icon={<MoreOutlined />} />
        </Dropdown>
      </Space>
      ```
    - **配置参数**：`uiLayout.actionButtonVisibleThreshold`（默认 5）、`uiLayout.lowFrequencyThresholdPerMonth`（默认 1）、`uiLayout.collapseContainerStrategy`（le3/3to6/gt6 三档）在 `config/tech-stack.json` 的 `hardConstraints.uiLayout` 节点管理
    - **适用**：列表页操作列（任务管理、订单管理、商品管理）、卡片视图操作区、详情页固定操作栏
    - **不适用**：操作按钮总数 ≤ 阈值、表单提交按钮组（主/次按钮天然分级）、详情页无溢出风险的固定操作栏
    - **历史教训**：TaskList.tsx 操作列 6 个文字按钮（编辑/启停/停止/复制/另存为模板/删除）在默认列宽下宽度约 580px 超出页面样式边界。修复：将"另存为模板"收入 Dropdown 更多菜单，操作列宽度降到约 380px
    - **审查 checkpoint**：F-REVIEW-197


---

### step 237：多视图模式一致性规范【强制，meta-rule #83 落地】🆕v4.49.0

237. **多视图模式一致性规范【强制，meta-rule #83 落地】🆕v4.49.0**
    - 同一资源在表格视图 + 卡片视图双视图呈现时，操作按钮集合必须**完全一致**（按钮数量、文案、handler 行为、disabled 条件），禁止分叉实现
    - **四要素**：
      | 要素 | 说明 | 示例 |
      |------|------|------|
      | 操作集合对齐 | 表格视图 `<Table>` 的 columns render 与卡片视图 `<Card actions>` 的按钮数量、文案、handler 必须完全一致 | 表格视图 5 个按钮 + 1 个 Dropdown，卡片视图必须同步 5 个按钮 + 1 个 Dropdown |
      | 共享 handler | 双视图的 handler 必须来自同一闭包或同一 useHandlers Hook，禁止各自定义同名函数 | `const handlers = useTaskActionHandlers(record); 表格视图和卡片视图都引用 handlers |
      | disabled 同步 | 按钮的 disabled 条件在双视图必须完全一致，禁止表格视图禁用但卡片视图可点击 | 任务状态为 running 时，表格与卡片的"编辑"按钮都必须 disabled |
      | 修改同步 | 修改任何视图的操作按钮时，必须同步修改另一视图，PR 描述中显式说明双视图同步 | PR 描述包含 "已同步表格视图 + 卡片视图" |
    - **判断信号**：
      - `grep "<Table" <page>.tsx` 与 `grep "<Card" <page>.tsx` 同时存在 → 必须做视图一致性检查
      - `git diff <page>.tsx` 仅修改了表格视图的操作列，但卡片视图 `<Card actions>` 未变 → 违规
      - 表格视图有 N 个操作按钮，卡片视图有 M ≠ N 个 → 违规
      - 双视图的 handler 函数名相同但定义在不同闭包 → 违规（应提取到 useHandlers Hook）
    - **修复模式**：
      ```tsx
      // ✅ 正确：提取 useTaskActionHandlers Hook，双视图共享同一 handler 集合
      function useTaskActionHandlers(record: Task) {
        return {
          edit: () => handleEdit(record),
          toggle: () => handleToggle(record),
          stop: () => handleStop(record),
          copy: () => handleCopy(record),
          delete: () => handleDelete(record),
          saveAsTemplate: () => handleSaveAsTemplate(record),
        }
      }

      // 表格视图 columns render
      const tableColumns = [{
        title: '操作',
        render: (_, record) => {
          const handlers = useTaskActionHandlers(record)
          return (
            <Space>
              <Button type="link" onClick={handlers.edit}>编辑</Button>
              {/* ... 其他按钮 */}
              <Dropdown menu={{ items: [{ key: 'save-as-template', label: '另存为模板', onClick: handlers.saveAsTemplate }] }}>
                <Button type="link" icon={<MoreOutlined />} />
              </Dropdown>
            </Space>
          )
        }
      }]

      // 卡片视图 actions（与表格视图完全一致）
      const cardActions = (record: Task) => {
        const handlers = useTaskActionHandlers(record)
        return [
          <Button type="link" onClick={handlers.edit}>编辑</Button>,
          {/* ... 其他按钮 */}
          <Dropdown menu={{ items: [{ key: 'save-as-template', label: '另存为模板', onClick: handlers.saveAsTemplate }] }}>
            <Button type="link" icon={<MoreOutlined />} />
          </Dropdown>,
        ]
      }
      ```
    - **配置参数**：`uiLayout.multiViewSyncRequired`（默认 true）、`uiLayout.multiViewSyncScanGlob`（默认 `frontend/src/pages/**/*.tsx`）、`uiLayout.tableViewMatchers`（默认 `["<Table", "columns=", "scroll="]`）、`uiLayout.cardViewMatchers`（默认 `["<Card", "actions=", "cover="]`）在 `config/tech-stack.json` 的 `hardConstraints.uiLayout` 节点管理
    - **适用**：同时存在表格视图 + 卡片视图的列表页（任务管理、订单管理）、同时存在列表视图 + 网格视图的页面、同时存在详细视图 + 简略视图的页面
    - **不适用**：仅有一种视图的页面、双视图但操作集合本身不同（如管理员视图 vs 普通用户视图，操作集合本就不同）
    - **历史教训**：TaskList.tsx 修复操作列溢出时，仅修改了表格视图，卡片视图的"另存为模板"按钮遗漏修改，导致双视图行为分裂。修复：同步修改卡片视图，将"另存为模板"收入 Dropdown 更多菜单
    - **审查 checkpoint**：F-REVIEW-198


---

### step 238：UI 水平空间溢出诊断与横向滚动容错规范【强制，meta-rule #83 落地】🆕v4.49.0

238. **UI 水平空间溢出诊断与横向滚动容错规范【强制，meta-rule #83 落地】🆕v4.49.0**
    - 所有 AntD `<Table>` 必须显式声明 `scroll={{ x: <minWidth 或 'max-content'> }}`，作为分级保留失败时的最后兜底，避免按钮被挤压换行
    - **四要素**：
      | 要素 | 说明 | 示例 |
      |------|------|------|
      | 溢出诊断 | 通过浏览器 DevTools 测量操作列实际宽度，对比页面可用宽度，差值 > 0 即溢出 | 操作列 580px vs 页面可用 480px → 溢出 100px |
      | 分级优先 | 优先走 step 236 操作项分级保留，将溢出降到 0；分级后仍有残留才走横向滚动 | 6 → 5 + 1 Dropdown 后宽度 380px < 480px → 无需横向滚动 |
      | 滚动兜底 | 分级后仍溢出时，必须显式声明 `scroll={{ x: 'max-content' }}` 或 `scroll={{ x: <minWidth> }}` | `<Table scroll={{ x: 'max-content' }} columns={columns} />` |
      | 视图同步 | 横向滚动配置在表格视图生效，卡片视图天然换行无需此配置，但需在 PR 描述中说明 | "表格视图已加 scroll fallback，卡片视图无需" |
    - **判断信号**：
      - `grep "scroll=" <page>.tsx` 无匹配 → 缺少横向滚动 fallback
      - 浏览器 DevTools 测量操作列宽度 > 页面可用宽度 → 溢出
      - 操作列按钮被挤压换行（高度不一致）→ 溢出
      - `grep "<Table" <page>.tsx` 但无 `columns` 的 `width` 属性 → 列宽未规划，易溢出
    - **修复模式**：
      ```tsx
      // ✅ 正确：先走分级保留（step 236），分级后仍溢出才加 scroll fallback
      <Table
        scroll={{ x: 'max-content' }}  // 兜底：分级后仍溢出时启用横向滚动
        columns={[
          { title: '任务名', dataIndex: 'name', width: 200 },
          { title: '状态', dataIndex: 'status', width: 100 },
          { title: '操作', render: (_, record) => <ActionButtons record={record} />, width: 380 },
        ]}
      />

      // ❌ 错误：仅靠 scroll 兜底，不做分级保留
      // <Table scroll={{ x: 'max-content' }} columns={[..., { title: '操作', render: () => <6 个文字按钮> }]} />
      ```
    - **配置参数**：`uiLayout.scrollFallback`（默认 'max-content'）在 `config/tech-stack.json` 的 `hardConstraints.uiLayout` 节点管理
    - **适用**：所有使用 AntD `<Table>` 的列表页、列数 ≥ 5 的表格、操作列承载多个按钮的表格
    - **不适用**：列数 ≤ 3 的简单表格（无溢出风险）、卡片视图（天然换行）、详情页（无表格）
    - **历史教训**：TaskList.tsx 表格未声明 `scroll` 属性，操作列 6 个文字按钮溢出时被挤压换行，视觉错乱。修复：将"另存为模板"收入 Dropdown（分级保留）后，仍显式声明 `scroll={{ x: 'max-content' }}` 作为兜底
    - **审查 checkpoint**：F-REVIEW-197


---


### step 249：COMPONENT-REUSE-STATE-RESET-01 React 组件复用状态同步重置规范【强制】🆕v4.52.0

**背景**：评估明细页 `ThumbCell` 组件接收 `url` prop 显示缩略图，图片加载失败时 `useState(false)` 的 `errored` 状态置为 `true` 显示占位图。官方采集更新图片 URL 后，因 `rowKey={`${r.item_id}-${r.created_at}`}` 不变，React 复用组件实例，`errored` 状态不自动重置，导致永远显示占位图。

**问题**：React 组件因 `rowKey` 不变被复用时，`useState` 内部状态不会自动重置。当 prop 变化（如 URL 更新）时，依赖该 prop 的内部状态（如 `errored`/`loading`/`selected`）仍保留旧值，导致 UI 不更新或显示错误状态。

**规范**：

1. **组件复用时内部状态必须随 prop 变化重置【强制】**：组件有 `useState` 内部状态 + 可能被 React 复用（`rowKey` 不变）+ 内部状态依赖某个 prop → 必须用 `useEffect` 监听 prop 变化重置内部状态：
   ```typescript
   // ✅ 正确：url 变化时重置 errored 状态
   function ThumbCell({ url, title }: { url?: string | null; title?: string | null }) {
     const [errored, setErrored] = useState(false)
     // url 变化时重置 errored：官方采集更新图片后需重新尝试加载，
     // 否则旧失败状态残留导致 React 复用实例时永远显示占位图
     useEffect(() => { setErrored(false) }, [url])
     if (!url || errored) {
       return <span>暂无图片</span>
     }
     return <img src={url} onError={() => setErrored(true)} alt={title ?? ''} />
   }
   ```

2. **判断组件是否会被复用【强制】**：以下场景组件会被 React 复用，必须检查内部状态重置：
   - 列表项组件（`<Table>` / `<List>` 的 `render` 函数内的组件）
   - 展开行组件（`expandedRowRender` 内的组件）
   - Tab 面板组件（`destroyInactiveTabPane={false}` 时）
   - `rowKey` 含静态字段（如 `created_at` 不变的字段）的列表

3. **需要重置的内部状态类型【强制】**：以下内部状态在依赖的 prop 变化时必须重置：
   - `errored` / `failed`（错误状态 → 重置为 `false`）
   - `loading`（加载状态 → 视场景重置）
   - `selected` / `active`（选中状态 → 视场景重置）
   - `expanded`（展开状态 → 视场景重置）
   - 任何从 prop 派生的缓存状态

4. **重置时机必须用 useEffect【强制】**：禁止在 render 阶段直接修改 state（`if (url !== prevUrl) setErrored(false)`），必须用 `useEffect`：
   ```typescript
   // ✅ 正确：useEffect 重置
   useEffect(() => { setErrored(false) }, [url])

   // ❌ 错误：render 阶段修改 state，导致无限重渲染
   if (url !== prevUrl) setErrored(false)  // React 警告：Cannot update during render
   ```

5. **重置逻辑配置化【推荐】**：需要重置的内部状态字段名、依赖的 prop 字段名，通过配置管理：
   ```yaml
   component_reuse_state_reset:
     enabled: true
     components:
       ThumbCell:
         reset_on_prop_change: { url: [errored] }
       OrderStatusTag:
         reset_on_prop_change: { orderId: [loading, cachedStatus] }
     reset_value_defaults: { errored: false, loading: false, selected: false }
   ```

**判断信号**：
- `grep "useState" frontend/src/` 找到含内部状态的组件 → 检查是否在列表/展开行/Tab 面板中使用
- 组件在 `<Table>` 的 `render` / `expandedRowRender` 中使用 + 有 `useState` → 必须检查 prop 变化时是否重置内部状态
- `rowKey` 含不变字段（如 `created_at`）+ 列表项组件有 `useState` → 组件会被复用，必须检查重置
- 组件有 `errored`/`loading`/`failed` 状态但无对应 `useEffect` 重置 → 视为违规
- 图片/数据更新后 UI 不刷新但数据已变 → 疑似状态残留，检查组件复用

**反模式**：
```typescript
// ❌ 无 useEffect 重置，url 变化后 errored 残留
function ThumbCell({ url, title }: { url?: string | null; title?: string | null }) {
  const [errored, setErrored] = useState(false)
  // 缺少：useEffect(() => { setErrored(false) }, [url])
  if (!url || errored) return <span>暂无图片</span>
  return <img src={url} onError={() => setErrored(true)} alt={title ?? ''} />
  // 官方采集更新 url 后，errored 仍为 true，永远显示"暂无图片"
}

// ❌ render 阶段修改 state
function ThumbCell({ url }: { url?: string }) {
  const [errored, setErrored] = useState(false)
  const prevUrl = useRef(url)
  if (url !== prevUrl.current) {  // render 阶段判断
    setErrored(false)  // render 阶段修改 state → 无限重渲染
    prevUrl.current = url
  }
  // ...
}
```

**配置参数**：`component_reuse_state_reset.enabled`（默认 `true`，是否启用检查）、`component_reuse_state_reset.components`（组件重置规则字典，key=组件名，value=`{ reset_on_prop_change: { prop名: [需重置的state名] } }`）、`component_reuse_state_reset.reset_value_defaults`（默认 `{ errored: false, loading: false, selected: false, expanded: false }`，重置默认值）、`component_reuse_state_reset.reuse_contexts`（默认 `['table_render', 'expanded_row_render', 'tab_panel_inactive', 'rowkey_contains_static_field']`，组件复用场景列表）在 `config.yaml` 的 `component_reuse_state_reset` 节点管理

**适用场景**：列表项组件（Table render）、展开行组件（expandedRowRender）、Tab 面板组件（destroyInactiveTabPane=false）、`rowKey` 含静态字段的列表、任何可能被 React 复用的组件

**不适用场景**：每次都创建新实例的组件（key 唯一）、无内部状态的纯展示组件、单例组件（页面级组件不会被复用）、useEffect 副作用清理场景（走 step 159）

**历史教训**：评估明细页 `ThumbCell` 组件接收 `url` prop 显示缩略图，图片加载失败时 `errored=true` 显示占位图。官方采集更新图片 URL 后，因 `rowKey={`${r.item_id}-${r.created_at}`}` 不变（`created_at` 是评估创建时间不更新），React 复用组件实例，`errored` 状态不自动重置，导致官方采集后图片仍显示占位图。添加 `useEffect(() => { setErrored(false) }, [url])` 后，URL 变化时重置错误状态，图片重新加载。与 step 159（useEffect 副作用清理）互补：step 159 聚焦"组件卸载时清理副作用"，本规则聚焦"组件复用时重置内部状态"。

---

### step 254：全局 ErrorBoundary 包裹规范（SPA-GLOBAL-ERROR-BOUNDARY-01，meta-rule #95 落地）【强制】🆕v4.61.0

254. **全局 ErrorBoundary 包裹规范（SPA-GLOBAL-ERROR-BOUNDARY-01，meta-rule #95 落地）【强制】🆕v4.61.0**
    - React SPA 根节点必须被全局 ErrorBoundary 包裹，捕获渲染期未处理异常并展示 fallback UI，**禁止**让异常冒泡到 React 顶层导致整页白屏
    - **关键约束**：
      1. **根节点包裹【强制】**：`App.tsx` 的 `<BrowserRouter>` 外层必须套 `<ErrorBoundary>`，确保所有路由树渲染异常被捕获
      2. **resetKeys 仅限基本类型【强制】**：`resetKeys` 数组只能放 `string`/`number`/`boolean`，**禁止**放对象/数组引用（引用每次渲染都变会触发误重置）
      3. **fallback UI 必须可操作【强制】**：fallback 必须含"刷新页面"按钮（`window.location.reload()`），**禁止**只展示静态错误文字让用户无法恢复
      4. **错误日志上报【强制】**：`componentDidCatch` 必须调用 `console.error` 记录错误堆栈，便于排查
    - **判断信号**：
      - `grep "BrowserRouter" frontend/src/App.tsx` 附近无 `<ErrorBoundary>` 包裹 → 视为违规
      - `resetKeys={[someObject]}` 或 `resetKeys={[someArray]}` 含引用类型 → 视为违规
      - ErrorBoundary fallback 仅含文字无操作按钮 → 视为违规
      - 用户反馈"切菜单偶发白屏，刷新后恢复" → 典型症状（渲染异常未捕获）
    - **反模式**：
      ```tsx
      // ❌ 错误：根节点无 ErrorBoundary，渲染异常直接白屏
      export default function App() {
        return (
          <BrowserRouter>
            <MainLayout />
          </BrowserRouter>
        )
      }

      // ❌ 错误：resetKeys 含引用类型，每次渲染触发误重置
      <ErrorBoundary resetKeys={[location.pathname, someObject]}>
        <Page />
      </ErrorBoundary>

      // ✅ 正确：根节点包裹 + resetKeys 基本类型 + 可操作 fallback
      <ErrorBoundary resetKeys={[location.pathname]}>
        <BrowserRouter>
          <MainLayout />
        </BrowserRouter>
      </ErrorBoundary>
      ```
    - **配置参数**：`spa_render_resilience.globalErrorBoundary.enabled`（默认 `true`，是否强制全局 ErrorBoundary）、`spa_render_resilience.globalErrorBoundary.resetKeyTypeWhitelist`（默认 `['string', 'number', 'boolean']`，resetKeys 允许的类型）、`spa_render_resilience.globalErrorBoundary.requireReloadButton`（默认 `true`，fallback 必须含刷新按钮）在 `config.yaml` 的 `spa_render_resilience` 节点管理
    - **适用场景**：所有 React SPA 项目；路由切换频繁的应用；含懒加载路由的应用
    - **不适用场景**：SSR 应用（需不同的错误处理策略）；纯静态页面无路由
    - **历史教训**：闲鱼猎人前端切换菜单时有 5-10% 概率白屏，刷新后恢复。根因是部分路由组件渲染期抛异常（如数据访问 `data[0].name` 未判空），异常冒泡到 React 顶层导致整页白屏。添加全局 ErrorBoundary 包裹 `<BrowserRouter>` 后，渲染异常被捕获展示 fallback UI，用户可点击刷新恢复

---

### step 255：懒加载 chunk 失效重试规范（LAZY-CHUNK-RETRY-01，meta-rule #95 落地）【强制】🆕v4.61.0

255. **懒加载 chunk 失效重试规范（LAZY-CHUNK-RETRY-01，meta-rule #95 落地）【强制】🆕v4.61.0**
    - 使用 `React.lazy()` 的路由组件必须用 `lazyRetry` 高阶函数包裹，在 ChunkLoadError 时自动重试加载（带 sessionStorage 持久化计数 + maxRetries 上限），**禁止**裸用 `React.lazy()` 导致部署后旧 chunk 404 永久白屏
    - **关键约束**：
      1. **lazyRetry 包裹【强制】**：所有 `React.lazy(() => import(...))` 必须替换为 `lazyRetry(() => import(...))`
      2. **sessionStorage 计数【强制】**：重试次数用 `sessionStorage` 持久化（key 含 chunk 标识），避免页面刷新后重置计数导致无限重试
      3. **maxRetries 上限【强制】**：默认 `maxRetries=3`，超过上限后停止重试交给 ErrorBoundary 兜底
      4. **错误模式识别【强制】**：必须识别 ChunkLoadError / Failed to fetch dynamically imported module 等加载失败错误模式，其他错误不重试
    - **判断信号**：
      - `grep "React.lazy" frontend/src/` 命中裸用（未包 lazyRetry）→ 视为违规
      - 部署后用户首次访问白屏，刷新后恢复 → 典型症状（旧 chunk hash 404）
      - `sessionStorage` 无 chunk 重试计数 key → 缺少持久化计数
    - **反模式**：
      ```tsx
      // ❌ 错误：裸用 React.lazy，chunk 加载失败无重试
      const ItemList = React.lazy(() => import('./pages/ItemList'))

      // ✅ 正确：lazyRetry 包裹 + sessionStorage 计数 + maxRetries
      const ItemList = lazyRetry(() => import('./pages/ItemList'), 'ItemList')

      // lazyRetry 实现要点
      function lazyRetry(importFn, name, maxRetries = 3) {
        return React.lazy(async () => {
          const key = `lazy-retry-${name}`
          const count = Number(sessionStorage.getItem(key) || '0')
          try {
            const mod = await importFn()
            sessionStorage.removeItem(key)
            return mod
          } catch (err) {
            if (count < maxRetries && isChunkLoadError(err)) {
              sessionStorage.setItem(key, String(count + 1))
              window.location.reload()
            }
            throw err
          }
        })
      }
      ```
    - **配置参数**：`spa_render_resilience.lazyRetry.enabled`（默认 `true`，是否强制 lazyRetry 包裹）、`spa_render_resilience.lazyRetry.maxRetries`（默认 `3`，最大重试次数）、`spa_render_resilience.lazyRetry.storageKeyPrefix`（默认 `lazy-retry-`，sessionStorage key 前缀）、`spa_render_resilience.lazyRetry.chunkErrorPatterns`（默认 `['ChunkLoadError', 'Failed to fetch dynamically imported module', 'Loading chunk']`，识别为 chunk 失败的错误模式列表）在 `config.yaml` 的 `spa_render_resilience` 节点管理
    - **适用场景**：所有使用 `React.lazy()` 的路由组件；CI/CD 频繁部署导致 chunk hash 变更的项目；PWA 应用
    - **不适用场景**：静态 import 的组件（无需懒加载）；SSR 应用
    - **历史教训**：闲鱼猎人前端部署新版本后，用户浏览器仍持有旧 index.html 引用旧 chunk hash，`React.lazy` 加载 404 chunk 抛 ChunkLoadError，因无重试机制直接白屏。添加 `lazyRetry` 包裹后，首次加载失败自动刷新重试，新 index.html 指向新 chunk hash，加载成功

---

### step 256：路由级 ErrorBoundary 隔离规范（ROUTE-ERROR-ISOLATION-01，meta-rule #95 落地）【强制】🆕v4.61.0

256. **路由级 ErrorBoundary 隔离规范（ROUTE-ERROR-ISOLATION-01，meta-rule #95 落地）【强制】🆕v4.61.0**
    - 每个路由级组件必须被独立 ErrorBoundary 包裹，确保单路由渲染错误被隔离不影响其他路由，**禁止**仅靠全局 ErrorBoundary 导致单页错误使整个应用不可用
    - **关键约束**：
      1. **路由级包裹【强制】**：`<Route element={<Page/>}>` 的 Page 组件外层必须套 `<ErrorBoundary>`（在 `MainLayout.tsx` 的 `<Outlet>` 外层或路由配置中包裹）
      2. **resetKeys 绑定路由参数【强制】**：路由级 ErrorBoundary 的 `resetKeys` 必须含 `location.pathname`，路由切换时自动重置错误状态
      3. **fallback 隔离【强制】**：路由级 fallback 只替换内容区，**禁止**覆盖全局布局（Header/Sidebar 保持可见）
      4. **与全局 ErrorBoundary 分层【强制】**：全局 ErrorBoundary 兜底未捕获异常，路由级 ErrorBoundary 捕获单路由异常，两者分层不冲突
    - **判断信号**：
      - `grep "<Route" frontend/src/` 附近无 `<ErrorBoundary>` 包裹 → 视为违规
      - 单个页面渲染错误导致整个布局白屏（Header/Sidebar 消失）→ 典型症状（缺路由级隔离）
      - 路由级 ErrorBoundary 的 `resetKeys` 不含 `location.pathname` → 切换路由不重置错误
    - **反模式**：
      ```tsx
      // ❌ 错误：路由无独立 ErrorBoundary，单页错误使整个应用白屏
      <Route path="/items" element={<ItemList />} />

      // ✅ 正确：路由级 ErrorBoundary 隔离 + resetKeys 绑定路由
      <Route path="/items" element={
        <ErrorBoundary resetKeys={[location.pathname]}>
          <ItemList />
        </ErrorBoundary>
      } />

      // ✅ 正确：在 MainLayout 的 Outlet 外层包裹（统一隔离所有子路由）
      <ErrorBoundary resetKeys={[location.pathname]}>
        <Outlet />
      </ErrorBoundary>
      ```
    - **配置参数**：`spa_render_resilience.routeErrorBoundary.enabled`（默认 `true`，是否强制路由级 ErrorBoundary）、`spa_render_resilience.routeErrorBoundary.resetKeySource`（默认 `location.pathname`，重置键来源）、`spa_render_resilience.routeErrorBoundary.preserveLayout`（默认 `true`，fallback 不覆盖全局布局）在 `config.yaml` 的 `spa_render_resilience` 节点管理
    - **适用场景**：多路由 SPA；路由组件含复杂数据访问；路由组件使用第三方库可能抛异常
    - **不适用场景**：单页应用（无路由）；纯静态展示页
    - **历史教训**：闲鱼猎人前端 DatabaseAdmin 页面因后端返回非预期数据结构导致渲染异常，因无路由级 ErrorBoundary，异常冒泡到全局 ErrorBoundary 使整个应用白屏（含 Header/Sidebar）。添加路由级 ErrorBoundary 包裹 `<Outlet>` 后，单页错误只影响内容区，用户可切换其他路由继续使用

---

### step 257：API 响应防御性兜底规范（API-DEFENSIVE-FALLBACK-01，meta-rule #95 落地）【强制】🆕v4.61.0

257. **API 响应防御性兜底规范（API-DEFENSIVE-FALLBACK-01，meta-rule #95 落地）【强制】🆕v4.61.0**
    - 组件渲染期访问 API 响应数据前必须做防御性判空与类型兜底，**禁止**假设响应结构一定完整（如 `data.list[0].name` 未判空），后端返回非预期结构时直接抛异常导致白屏
    - **关键约束**：
      1. **数组访问前判空【强制】**：`data.list` 访问 `data.list[0]` 前必须 `if (!data?.list?.length) return null`
      2. **对象属性访问用可选链【强制】**：`data?.user?.name` 替代 `data.user.name`，后端返回 null 时不抛异常
      3. **渲染前数据校验【强制】**：列表渲染前 `const list = data?.list ?? []`，确保始终是数组
      4. **异常边界与 ErrorBoundary 配合【强制】**：防御性兜底是第一道防线，ErrorBoundary 是兜底防线，两者必须同时存在
    - **判断信号**：
      - `grep "\.[0-9]\+\|\.list\[" frontend/src/` 命中未判空的数组索引访问 → 检查是否有前置判空
      - 组件含 `data.xxx.yyy` 链式访问无 `?.` → 视为违规
      - 后端返回 `{}` 或 `null` 时前端白屏 → 典型症状（未防御性兜底）
      - ErrorBoundary 捕获的异常堆栈含 `Cannot read properties of undefined (reading 'xxx')` → 典型症状
    - **反模式**：
      ```tsx
      // ❌ 错误：未判空访问数组与对象属性，后端返回非预期结构时白屏
      function ItemList({ data }: { data: ApiResponse }) {
        const firstItem = data.list[0]  // data.list 可能 undefined
        return <div>{firstItem.name}</div>  // firstItem 可能 undefined
      }

      // ✅ 正确：可选链 + 空数组兜底 + 前置判空
      function ItemList({ data }: { data?: ApiResponse }) {
        const list = data?.list ?? []
        if (!list.length) return <Empty />
        const firstItem = list[0]
        return <div>{firstItem?.name ?? '未命名'}</div>
      }
      ```
    - **配置参数**：`spa_render_resilience.apiArrayDefense.enabled`（默认 `true`，是否强制数组访问判空）、`spa_render_resilience.apiArrayDefense.requireOptionalChaining`（默认 `true`，链式访问必须用 `?.`）、`spa_render_resilience.apiArrayDefense.emptyListFallback`（默认 `true`，列表渲染前必须兜底空数组）在 `config.yaml` 的 `spa_render_resilience` 节点管理
    - **适用场景**：所有消费 API 响应的组件；列表渲染组件；含嵌套数据结构的组件
    - **不适用场景**：纯本地静态数据；TypeScript 严格类型保证非空且无运行时风险
    - **历史教训**：闲鱼猎人前端 `ItemList.tsx` 和 `DatabaseAdmin.tsx` 渲染期直接访问 `data.list[0].name`，后端在异常情况下返回 `{}` 导致 `data.list` 为 undefined，抛 `Cannot read properties of undefined` 导致白屏。添加可选链 + 空数组兜底后，后端返回非预期结构时展示空状态而非白屏

---

### step 258：HTTP 401 拦截器防抖规范（HTTP-401-DEBOUNCE-01，meta-rule #95 落地）【强制】🆕v4.61.0

258. **HTTP 401 拦截器防抖规范（HTTP-401-DEBOUNCE-01，meta-rule #95 落地）【强制】🆕v4.61.0**
    - axios/fetch 拦截器收到 401 响应时必须用模块级标志防抖，**禁止**每个 401 响应都触发 `window.location.href` 跳转，导致并发请求产生多次跳转中断渲染
    - **关键约束**：
      1. **模块级防抖标志【强制】**：用模块级 `let isRedirecting = false` 标志，首次 401 设为 `true` 并跳转，后续 401 直接 return 不重复跳转
      2. **location.replace 替代 href【强制】**：用 `window.location.replace(loginUrl)` 替代 `window.location.href = loginUrl`，replace 不留历史记录避免用户回退回失效页
      3. **防抖标志重置【强制】**：登录页加载时重置 `isRedirecting = false`，确保下次会话失效可再次跳转
      4. **并发请求不中断渲染【强制】**：401 拦截器只记录日志不抛异常中断当前渲染，跳转由 location.replace 异步触发
    - **判断信号**：
      - `grep "location.href" frontend/src/api/` 命中 401 拦截器 → 应改为 `location.replace`
      - `grep "isRedirecting" frontend/src/api/` 无命中 → 缺少防抖标志
      - 控制台出现多条 401 跳转日志或 "navigation interrupted" → 典型症状（未防抖）
      - 切菜单时偶发白屏且网络面板多条 401 → 典型症状（并发 401 跳转中断渲染）
    - **反模式**：
      ```typescript
      // ❌ 错误：每个 401 都触发跳转，并发请求产生多次跳转中断渲染
      instance.interceptors.response.use(
        (res) => res,
        (err) => {
          if (err.response?.status === 401) {
            window.location.href = '/login'  // 并发 5 个 401 → 5 次跳转
          }
          return Promise.reject(err)
        }
      )

      // ✅ 正确：模块级防抖 + replace 不留历史
      let isRedirecting = false
      instance.interceptors.response.use(
        (res) => res,
        (err) => {
          if (err.response?.status === 401 && !isRedirecting) {
            isRedirecting = true
            window.location.replace('/login')
          }
          return Promise.reject(err)
        }
      )
      ```
    - **配置参数**：`spa_render_resilience.http401Debounce.enabled`（默认 `true`，是否强制 401 防抖）、`spa_render_resilience.http401Debounce.redirectMethod`（默认 `replace`，跳转方法 replace/href）、`spa_render_resilience.http401Debounce.flagVariableName`（默认 `isRedirecting`，防抖标志变量名）在 `config.yaml` 的 `spa_render_resilience` 节点管理
    - **适用场景**：所有含认证的 SPA；axios/fetch 拦截器；并发请求场景
    - **不适用场景**：无认证的公开 API；SSR 应用（跳转方式不同）
    - **历史教训**：闲鱼猎人前端 `client.ts` 的 401 拦截器用 `window.location.href` 跳转，会话失效时多个并发请求各自触发 401 跳转，浏览器在渲染过程中被多次 navigation 中断导致白屏。改为模块级 `isRedirecting` 防抖 + `window.location.replace` 后，仅首次 401 触发跳转，渲染不被中断


---

### step 259：UI视觉变更预确认门控规范（UI-PREVIEW-GATE-01，meta-rule #103 落地）【强制】🆕v4.62.0

259. **UI视觉变更预确认门控规范（UI-PREVIEW-GATE-01，meta-rule #103 落地）【强制】🆕v4.62.0**
    - **背景**：Geometric Essence 图标全量替换 21 个 Ant Design 图标后，用户认为不美观与整体主题不协调，要求回滚。全量替换的回滚成本高，且无法预判用户审美偏好。
    - **规范**：
      1. 视觉风格变更（图标/主题色/布局/交互模式）须先预览再全量替换【强制】
      2. 渐进式替换策略：单模块先替换 → 用户确认 → 全量替换【强制】
      3. 回滚清单记录：变更前必须记录所有变更点（import/组件/样式/配置），便于一键回滚【强制】
      4. 预设组件替换自定义组件时，必须评估风格一致性（颜色/线条粗细/填充模式/圆角）【强制】
    - **判断信号**：
      - `grep "import.*Icon" <tsx>` 变更行数 > `ui_preview_gate.changeLineThreshold`（默认 10 行）
      - 图标/主题/布局的大面积替换
      - 自定义 SVG 图标替换预设图标库（AntD/MUI 等）
    - **配置参数**：`ui_preview_gate.enabled`（默认 `true`，是否启用预确认门控）、`ui_preview_gate.changeLineThreshold`（默认 `10`，触发预确认的变更行数阈值）、`ui_preview_gate.previewStrategy`（默认 `'single_module_first'`，预览策略：single_module_first / full_replace）在 `config.yaml` 的 `ui_preview_gate` 节点管理
    - **适用**：视觉风格替换、图标变更、主题色调整、布局重构、交互模式变更
    - **不适用**：Bug 修复导致的微小 UI 调整、文案修正、样式微调（间距/字号）、条件性渲染逻辑
    - **历史教训**：Geometric Essence 自定义 SVG 图标全量替换 21 个 Ant Design Outlined 图标，用户审查后认为不美观与整体主题不协调，要求回滚。回滚需修改 import/menuItems/COMMAND_ITEMS 三处，重新构建 22s，成本高。若先替换单模块预览确认，可避免无效全量替换


---

### step 260：React状态选型判断矩阵规范（STATE-SELECTION-01，meta-rule #107 落地）【强制】🆕v4.62.0

260. **React状态选型判断矩阵规范（STATE-SELECTION-01，meta-rule #107 落地）【强制】🆕v4.62.0**
    - **背景**：CDP 模式开关使用 `useState(false)` 导致刷新后状态重置，应使用 `usePersistentState`。状态管理选型错误导致用户体验退化。
    - **规范**：
      1. 新增 React state 时必须先识别归属类别【强制】：
         - 跨刷新持久化偏好 → `usePersistentState`（开关/视图模式/列显隐/折叠状态）
         - 仅组件生命周期内 → `useState`（loading/modal open/表单 dirty）
         - 跨组件共享 → Zustand store（登录态/当前选中项/跨页共享状态）
         - URL 同步 → `useSearchParams`（筛选条件/分页/排序）
      2. 禁止 `useState` 存储需跨刷新持久化的用户偏好【强制】
      3. 已有 `usePersistentState` 的项目禁止自行实现 localStorage 读写【强制】
    - **判断信号**：
      - `grep "useState(false)" <tsx>` 命中用户偏好类变量名
      - 用户反馈"刷新页面后开关/设置丢失"
      - `useState` 用于开关/视图模式/列配置等跨会话状态
    - **配置参数**：`state_selection.preferenceKeywords`（默认 `['autoRefresh', 'viewMode', 'columnConfig', 'density', 'collapsed', 'expandedKeys', 'themePreference', 'recentItems', 'useCdp']`，偏好类变量名关键词列表）、`state_selection.persistenceHookName`（默认 `'usePersistentState'`，持久化 Hook 名称）在 `config.yaml` 的 `state_selection` 节点管理
    - **适用**：新组件开发时的状态管理选型、`useState` 滥用审计
    - **不适用**：服务端渲染（RSC 无 `useState`）、非 React 项目
    - **历史教训**：`AntiCrawl/index.tsx` 的 CDP 模式开关使用 `useState(false)`，刷新页面后状态重置为关闭，用户需反复手动开启。修复：替换为 `usePersistentState('xh.anticrawl.useCdp', false, { validator })`


---

### step 271：useSearch Hook 防抖与并发保护规范【强制】🆕v4.64.0

271. **useSearch Hook 防抖与并发保护规范【强制】🆕v4.64.0**

    **背景**：项目内有多个搜索页面（智能客服会话/任务关联/错误日志/数据库维护），原本各自手动实现 `useEffect + setTimeout` 防抖，导致防抖间隔不一致（300ms/400ms/500ms 混用）、并发请求无保护（快速输入产生多个 in-flight 请求）、卸载后 setState 警告。v4.64.0 抽取统一 `useSearch` Hook（`frontend/src/hooks/useSearch.ts`），与 Alpine 模板 `@input.debounce.400ms` 对齐。

    **规范**：

    1. **统一防抖间隔【强制】**：所有实时搜索场景必须使用 `useSearch` Hook，默认防抖 400ms（与 Alpine `@input.debounce.400ms` 对齐），禁止各页面自行 `setTimeout`：
       ```typescript
       // ✅ 正确：统一 useSearch Hook
       const { isSearching } = useSearch({
         search: (deps) => loadSessions(deps[0] as string),
         deps: [keyword],
         debounceMs: 400,  // 可省略，默认 400
       })

       // ❌ 错误：各页面自行 setTimeout，防抖间隔不一致
       // useEffect(() => {
       //   const t = setTimeout(() => loadSessions(keyword), 300)  // 300ms 与其他页面不一致
       //   return () => clearTimeout(t)
       // }, [keyword])
       ```

    2. **requestId 并发保护【强制】**：每次发起请求递增 `requestIdRef.current`，响应回来时比对，过期响应被丢弃，避免快速输入时旧响应覆盖新响应：
       ```typescript
       // ✅ 正确：requestId 标记，旧响应被丢弃
       const currentId = ++requestIdRef.current
       setIsSearching(true)
       try {
         await searchRef.current(deps as unknown as T)
       } finally {
         if (currentId === requestIdRef.current) {  // 仅最新请求才清 loading
           setIsSearching(false)
         }
       }
       ```

    3. **enabled 条件搜索【强制】**：通过 `enabled` 参数控制是否触发搜索（如弹窗未打开时不搜索），`enabled=false` 时跳过所有请求：
       ```typescript
       const { isSearching } = useSearch({
         search: (deps) => searchItems(deps[0]),
         deps: [keyword],
         enabled: modalOpen,  // 弹窗关闭时不搜索
       })
       ```

    4. **卸载清理【强制】**：组件卸载时必须清理防抖计时器，避免卸载后 setState 警告：
       ```typescript
       useEffect(() => {
         return () => {
           if (debounceRef.current) clearTimeout(debounceRef.current)
         }
       }, [])
       ```

    5. **ref 持有最新闭包【强制】**：用 `useRef` 持有 `search` 与 `enabled` 的最新值，避免 `useCallback` 依赖变化导致防抖重置：
       ```typescript
       const searchRef = useRef(search)
       searchRef.current = search  // 每次渲染更新 ref
       ```

    **配置驱动**：防抖间隔、请求超时、默认 enabled 值等参数在 `config/tech-stack.json#hardConstraints.searchHookDebounce` 节点管理，包含 `defaultDebounceMs`（400）/ `requestIdFieldName`（`requestIdRef`）/ `enabledDefault`（true）/ `cleanupOnUnmount`（true）等，禁止在业务代码中硬编码。

    **适用场景**：
    - 用户输入关键词的实时搜索（智能客服会话/任务关联/错误日志/数据库维护）
    - 与 Alpine `@input.debounce.400ms` 模式对齐的搜索场景
    - 弹窗/抽屉内的条件搜索（用 `enabled` 控制开关）

    **不适用场景**：
    - 筛选器 + 查询按钮模式（用户主动点击触发，无需防抖）
    - 主键精确查询（无并发风险，直接 fetch）
    - SSE/WebSocket 流式搜索（无请求-响应模型）

    **历史教训**：
    - 智能客服会话搜索原本用 `useEffect + setTimeout(300)`，与任务关联搜索的 400ms 不一致，用户切换页面时防抖体验不一致。修复：统一为 `useSearch` Hook，默认 400ms
    - 快速输入"测试"时，前 3 个字符的请求并发发出，最后 "试" 字的响应先返回，"测试" 的响应后返回，导致列表显示"试"的结果而非"测试"。修复：requestId 并发保护，丢弃过期响应

    **判断信号（review 触发条件）**：
    - `grep "setTimeout.*load\|useEffect.*setTimeout" frontend/src/pages/` 命中搜索场景 → 视为违规
    - `grep "useState.*isSearching\|useState.*loading" frontend/src/` 但未使用 `useSearch` → 视为可疑
    - 用户反馈"快速输入时列表闪烁/显示错误结果" → 并发保护缺失
    - 用户反馈"卸载后控制台有 setState 警告" → 卸载清理缺失

    **关联审查点**：F-REVIEW-236（防抖间隔统一）/ F-REVIEW-237（requestId 并发保护）/ F-REVIEW-238（enabled 条件搜索与卸载清理）


---

### step 272：useSearchHistory 持久化与 Hooks 依赖顺序规范【强制】🆕v4.64.0

272. **useSearchHistory 持久化与 Hooks 依赖顺序规范【强制】🆕v4.64.0**

    **背景**：搜索历史原本各页面自行 `localStorage` 读写，导致 key 命名混乱（`search_history`/`xh_history`/`chatbot_hist`）、无去重（同一关键词重复出现）、无容量限制（localStorage 无限增长）。v4.64.0 抽取统一 `useSearchHistory` Hook（`frontend/src/hooks/useSearchHistory.ts`），并修复了 `storageKey` 不稳定导致的 `useCallback` 依赖问题。

    **规范**：

    1. **统一命名空间隔离【强制】**：不同搜索页的历史必须通过 `namespace` 参数隔离，key 格式为 `xh_search_history_{namespace}`，禁止各页面自行命名：
       ```typescript
       // ✅ 正确：命名空间隔离
       const { history, add, clear } = useSearchHistory({ namespace: 'chatbot' })
       // localStorage key: xh_search_history_chatbot

       const { history, add, clear } = useSearchHistory({ namespace: 'items' })
       // localStorage key: xh_search_history_items

       // ❌ 错误：各页面自行命名，key 混乱
       // localStorage.setItem('search_history', ...)  // 命名不一致
       ```

    2. **useMemo 固定 storageKey【强制】**：`storageKey` 必须用 `useMemo` 固定，避免每次渲染生成新字符串导致 `useCallback` 依赖变化，进而触发使用此 Hook 的组件（如 Chatbot `loadSessions`）无意义重渲染：
       ```typescript
       // ✅ 正确：useMemo 固定 key
       const storageKey = useMemo(() => `${STORAGE_KEY_PREFIX}${namespace}`, [namespace])

       // ❌ 错误：每次渲染生成新字符串，useCallback 依赖变化
       // const storageKey = `${STORAGE_KEY_PREFIX}${namespace}`  // 不稳定
       ```

    3. **去重 + 最近优先 + 容量限制【强制】**：添加历史时必须去重（同一关键词只保留最近一次）、最近优先（新搜索插入头部）、容量限制（默认 20 条，超出时淘汰尾部）：
       ```typescript
       const add = useCallback((keyword: string) => {
         setHistory(prev => {
           const filtered = prev.filter(kw => kw !== keyword)  // 去重
           return [keyword, ...filtered].slice(0, maxItems)     // 最近优先 + 容量限制
         })
       }, [maxItems])
       ```

    4. **Hooks 声明顺序规范【强制】**：当 `useSearchHistory` 的 `add`/`clear`/`remove` 被另一个 `useCallback`（如 `loadSessions`）依赖时，`useSearchHistory` 必须声明在 `loadSessions` **之前**，否则 `loadSessions` 的 `useCallback` 依赖会引用未声明的变量（TDZ 错误）：
       ```typescript
       // ✅ 正确：useSearchHistory 在 loadSessions 之前声明
       const { history, add, clear } = useSearchHistory({ namespace: 'chatbot' })

       const loadSessions = useCallback(async (keyword?: string) => {
         if (keyword) add(keyword)  // add 已声明
         // ...
       }, [add])  // 依赖 add

       // ❌ 错误：useSearchHistory 在 loadSessions 之后声明（TDZ 错误）
       // const loadSessions = useCallback(async (keyword?: string) => {
       //   if (keyword) add(keyword)  // add 未声明（TDZ）
       // }, [add])
       // const { history, add, clear } = useSearchHistory({ namespace: 'chatbot' })
       ```

    5. **localStorage 降级容错【强制】**：`localStorage` 读取必须 try/catch，不可用或数据损坏时静默降级为空数组，禁止抛出异常阻塞渲染：
       ```typescript
       useEffect(() => {
         try {
           const raw = localStorage.getItem(storageKey)
           if (raw) {
             const parsed = JSON.parse(raw)
             if (Array.isArray(parsed)) setHistory(parsed.slice(0, maxItems))
           }
         } catch {
           // localStorage 不可用或数据损坏时静默降级
         }
       }, [storageKey, maxItems])
       ```

    **配置驱动**：命名空间列表、最大保留条数、key 前缀、降级策略等参数在 `config/tech-stack.json#hardConstraints.searchHistoryPersistence` 节点管理，包含 `storageKeyPrefix`（`xh_search_history_`）/ `defaultMaxItems`（20）/ `deduplicationStrategy`（`filter_then_unshift`）/ `fallbackStrategy`（`silent_empty`）/ `namespaceList`（`['chatbot', 'items', 'logs', 'db_maintenance']`）等，禁止在业务代码中硬编码。

    **适用场景**：
    - 关键词搜索页面的历史记录持久化（智能客服会话/任务关联/错误日志/数据库维护）
    - 跨会话需保留的用户搜索行为
    - 多搜索页之间历史隔离

    **不适用场景**：
    - 枚举值筛选（如状态筛选/分类筛选，用户每次重新选择，无需历史）
    - 敏感数据搜索（如密码/token 搜索，不应持久化到 localStorage）
    - 一次性查询（如详情页 ID 查询，无需历史）

    **历史教训**：
    - `useSearchHistory` 的 `storageKey` 原本直接用 `${prefix}${namespace}` 字符串拼接，每次渲染生成新字符串，导致 `add`/`clear`/`remove` 的 `useCallback` 依赖变化，进而触发 Chatbot 组件的 `loadSessions` 无意义重渲染。修复：用 `useMemo` 固定 `storageKey`
    - `useSearchHistory` 原本声明在 `loadSessions` 之后，`loadSessions` 的 `useCallback` 依赖了 `add`，导致 TDZ（Temporal Dead Zone）错误。修复：将 `useSearchHistory` 声明移到 `loadSessions` 之前
    - 智能客服会话搜索历史原本用 `localStorage.setItem('search_history', ...)`，与任务关联搜索的 `xh_history` 命名不一致，切换页面时历史串扰。修复：统一为 `useSearchHistory` Hook + namespace 隔离

    **判断信号（review 触发条件）**：
    - `grep "localStorage.setItem.*history\|localStorage.getItem.*history" frontend/src/` 命中 → 视为违规（未使用 `useSearchHistory`）
    - `grep "useState.*history" frontend/src/` 但未使用 `useSearchHistory` → 视为可疑
    - `grep "const storageKey = " frontend/src/hooks/` 未使用 `useMemo` → 视为违规
    - 用户反馈"切换搜索页时历史记录串扰" → namespace 隔离缺失
    - 用户反馈"刷新后历史记录消失" → localStorage 持久化缺失

    **关联审查点**：F-REVIEW-239（useSearchHistory 持久化模式）/ F-REVIEW-240（React Hooks 依赖顺序规范）
