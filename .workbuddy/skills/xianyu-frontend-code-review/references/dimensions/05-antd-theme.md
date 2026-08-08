# 5. AntD 5 主题规范 🆕v2.0

- 【强制】使用 Ant Design 5.21+ + `ConfigProvider` 主题
- 【强制】基础 token 包含 `colorPrimary: '#FF6200'`（闲鱼品牌橙）、`borderRadius: 8`
- 【强制】暗色主题用 `theme.darkAlgorithm`，亮色用 `theme.defaultAlgorithm`
- 【强制】`ConfigProvider` 必须在 `BrowserRouter` 外层（让独立路由如 `/login` 也能切换主题）
- 【强制】`theme.useToken()` 在 ConfigProvider 内部消费
- 【强制】组件级主题覆盖（如 `Table.rowHoverBg`）需响应 `isDark` 状态
- 【强制】**交互元素颜色对比度**：可点击的文字、图标、提示用 `colorPrimary`（即 `activeColor`），确保对比度
- 【禁止】交互元素文字用 `colorBorder`（对比度不足，浅色/深色主题下均难辨识）
- 【推荐】装饰性元素（边框、背景、分隔线）可用 `colorBorder`，交互元素不用
- 🆕v4.8【强制】**F-REVIEW-ANTD-THEME-TOKEN-OVERRIDE：AntD 主题 token 动态覆盖模式**
  - 项目支持暗色主题（`theme.darkAlgorithm`）时，`baseTheme.components.<Component>.<token>` 中**显式指定**的主题相关 token（token 名含 `Color` / `Bg` / `Border` / `Hover` / `Active` / `Focus` 后缀）必须根据 `isDark` 状态在能读到 `useTheme()` 的组件（通常是 `ThemedRoot`）内**动态覆盖**。**禁止**依赖 `darkAlgorithm` 自动重算或 `index.css` 中的 `--ant-*` CSS 变量
  - **核心机制**（审查时必须理解）：
    - antd v5 的 `darkAlgorithm` **仅重算未指定的 token**，显式指定的 token 会被原样继承 → 这是 `baseTheme` 中显式指定的亮色值在暗色主题下失效的根因
    - antd v5 的 `cssVar` 模式**默认未启用**，手动在 `index.css` 中写的 `--ant-*` CSS 变量不被组件引用，是死代码 → 不能依赖 CSS 变量覆盖 token，必须改 `ConfigProvider`
  - **判断信号**：
    - `grep "components\\." main.tsx` 发现 `baseTheme.components.<Component>.<token>: '<value>'` 显式指定了主题相关 token（token 名含 `Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus` 后缀）
    - 项目使用 `algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm`（支持暗色主题）
    - 该 token 在 `ThemedRoot` 中**未根据 `isDark` 动态覆盖**（直接 spread `baseTheme` 后未覆盖 `components.<Component>.<token>`）→ 视为违规
    - `index.css` 中存在 `--ant-*` CSS 变量定义（`grep "\\-\\-ant-" index.css`）→ 视为可疑死代码，需确认是否启用 `cssVar` 模式，未启用则清理
  - **修复模式**（在 `ThemedRoot` 的 spread `baseTheme` 后动态覆盖）：
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
          <BrowserRouter basename="/app">
            <App />
          </BrowserRouter>
        </ConfigProvider>
      )
    }
    ```
  - **暗色值选择原则**（与品牌色 `#FF6200` 保持视觉一致性，参数由 `config.yaml` 的 `antd_theme_override` 节点管理）：
    - `Hover` / `Active` 状态色：优先用「品牌色 + 低透明度」叠加（如 `rgba(255, 98, 0, 0.08)`），避免硬编码纯色或过深色
    - 背景色（`Bg` 后缀）：用暗色阶梯色（如 `#1f1f1f` / `#141414`）
    - 文字色（`Color` 后缀）：用 `rgba(255, 255, 255, 0.88)` 或 `#e0e0e0`
    - 边框色（`Border` 后缀）：用 `rgba(255, 255, 255, 0.15)` 等半透明色
  - **注释要求**（注释必须解释「为什么」而非「做什么」，参考用户编程原则）：
    1. 说明 `darkAlgorithm` 不会重算显式 token（避免后续维护者误以为会自动适配）
    2. 说明 WCAG 对比度计算（暗色文字与 hover 背景的对比度需满足 AA 级 ≥4.5:1）
    3. 说明品牌色一致性（暗色值与亮色值在视觉调性上保持一致，如都是淡橙调）
  - **配置参数**：`theme_token_whitelist`（主题相关 token 名称后缀白名单：`Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus`）、`dark_value_strategy`（暗色值生成策略：`hover_active=brand_overlay` / `background=dark_step` / `text=white_alpha`）、`brand_color`（默认 `#FF6200`）、`brand_overlay_alpha`（默认 `0.08`）、`wcag_level`（默认 `AA`）、`cssvar_enabled`（默认 `false`，用于判断 `--ant-*` 变量是否为死代码）在 `config.yaml` 的 `antd_theme_override` 节点管理
  - **诊断流程**（出现「暗色主题下文字看不见/对比度低」类问题时执行）：
    1. `grep "components\\." main.tsx` 扫描所有显式指定的 token
    2. 逐个检查 token 名是否含主题相关后缀（`Color`/`Bg`/`Border`/`Hover`/`Active`/`Focus`）
    3. 对每个主题相关 token，验证是否响应了 `isDark` 动态切换
    4. 若未响应 → 判定为违规，按修复模式动态覆盖
    5. 顺手 `grep "\\-\\-ant-" index.css` 检查是否有死代码 CSS 变量，确认后清理
  - **适用**：AntD 5.x 项目 + 多主题支持（`darkAlgorithm` / `defaultAlgorithm` 切换）；`baseTheme.components.<Component>.<token>` 显式指定主题相关 token 的场景；WCAG 可访问性合规场景
  - **不适用**：未启用多主题的项目（仅默认亮色）；antd v4 及以下（主题机制不同）；启用了 antd v5 `cssVar: true` 的项目（CSS 变量会生效，可优先用 CSS 变量方案）；非 antd UI 库；与主题无关的 token（`borderRadius`/`fontSize`/`lineHeight` 等 `darkAlgorithm` 会自动适配）
  - **历史教训**：`baseTheme.components.Table.rowHoverBg` 显式指定为 `#fff7f0`（接近白色的淡橙），暗色主题下被原样继承，与暗色文字 `rgba(255, 255, 255, 0.88)/#e0e0e0`（也接近白色）对比度近乎为零，hover 时文字几乎看不见。同时 `index.css` 中残留的 `--ant-table-row-hover-bg: #262626` 是死代码（未启用 cssVar 模式，不被组件引用）误导了初版诊断。修复后在 `ThemedRoot` 内根据 `isDark` 动态覆盖为 `rgba(255, 98, 0, 0.08)`

```typescript
// ✅ 推荐：ConfigProvider 在 BrowserRouter 外层
// 注意：baseTheme 中显式指定的主题相关 token（含 Color/Bg/Border/Hover/Active/Focus 后缀）
// 必须在 ThemedRoot 内根据 isDark 动态覆盖（darkAlgorithm 不会重算显式 token）
const baseTheme = {
  token: { colorPrimary: '#FF6200', borderRadius: 8 },
  components: {
    Table: { rowHoverBg: '#fff7f0' },  // 亮色值，暗色需在 ThemedRoot 动态覆盖
  },
}

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
            rowHoverBg: isDark ? 'rgba(255, 98, 0, 0.08)' : baseTheme.components.Table.rowHoverBg,
          },
        },
      }}
    >
      <BrowserRouter basename="/app">
        <App />
      </BrowserRouter>
    </ConfigProvider>
  )
}
```
