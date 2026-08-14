# 维度 44：设计令牌集中化（禁硬编码色）🆕v4.71.0 · F-REVIEW-238

> **编码规范引用**：xianyu-hunter-dev `references/coding-standards.md` §3.16.4 / meta-rule #119
> **配置节点**：config.yaml#checklist.design_tokens_no_hardcode + config.yaml#design_tokens
> **测试关联**：xianyu-auto-testing 模式 V（UI 视觉回归）

## 触发条件
- 任何前端样式文件（`.css`/`.scss`/`styled`）或页面/组件内联 style 的新增或修改
- 涉及颜色、圆角、间距等视觉变量的变更
- 主题切换、品牌色、深浅色模式相关改动

## 检查规则

### 强制（P0 阻塞）
- 组件/页面内联 `style` **禁止**硬编码十六进制色值（如 `#FFB3CC`、`#6ECDB4`）。颜色必须从 `:root` CSS 变量 / 主题 token 引用（扫描路径见 config.yaml#design_tokens.scan_paths，例外见 config.yaml#design_tokens.hex_exclude_patterns）。
- 马卡龙等装饰色一律移除，改用品牌灰阶（背景 `#ffffff`、主文本 `#111111`、次要 `#777777`）。

### 推荐（P1 严重）
- 文本主色/次要色/边框/背景从 token 引用（如 config.yaml#design_tokens.text_primary_token=`--cb-text-primary`），满足 WCAG AA 对比度（正文 min_contrast_ratio=4.5）。
- 设计变量集中在单一 token 文件，避免散落多文件无单一源。

### 推荐（P2 改进）
- 圆角/间距/阴影等亦纳入 token，避免魔数散落。

## Grep 扫描命令
```bash
# 检测组件内联 style 中的硬编码十六进制色（排除 token 定义文件与 svg）
grep -rn "#[0-9a-fA-F]\{6\}" frontend/src/pages/ frontend/src/components/ \
  --include="*.tsx" --include="*.ts" \
  | grep -v "theme.ts" | grep -v "tokens.css" | grep -v "\.svg"

# 检测残留装饰色（马卡龙系）
grep -rniE "#(FFB3CC|FF8FAB|6ECDB4|A8E6CF|FFD6E8|E8D5F2)" frontend/src/ --include="*.css" --include="*.tsx"
```

## 判断标准
- 内联 style 含硬编码十六进制色 → P0 阻塞（排除 token 定义文件与 svg fill 约定）
- 文本色未从 token 引用、对比度不达标 → P1 严重
- 装饰色未移除、视觉风格与品牌灰阶不一致 → P1 严重

## 适用场景
- 任何前端样式文件（`.css`/`.scss`/`styled`）
- 含主题切换、品牌色、深浅色模式的项目

## 不适用场景
- 一次性内联调试样式（临时验证，不入库）
- 第三方组件库内部样式（不受本仓库 token 约束）
- SVG 图标内部 fill 的颜色约定（由图标规范单独管理）
