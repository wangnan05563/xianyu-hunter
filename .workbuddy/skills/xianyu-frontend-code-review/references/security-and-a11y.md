# 前端安全与可访问性审查（Security & A11y）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)

---

## 1. 安全（Security）

### 1.1 XSS 防护（SC-04）

```tsx
// ❌ 严重：直接渲染 HTML
<div dangerouslySetInnerHTML={{ __html: userInput }} />

// ✅ 用 React 默认转义
<div>{userInput}</div>
```

如果必须用 `dangerouslySetInnerHTML`，必须 sanitise：

```tsx
import DOMPurify from 'dompurify'

<div dangerouslySetInnerHTML={{
  __html: DOMPurify.sanitize(userInput)
}} />
```

### 1.2 敏感数据处理

```typescript
// ❌ 反例：cookie / token 写日志
console.log('token:', token)
console.log('user info:', user)

// ✅ 不打敏感信息
console.log('user logged in')
```

### 1.3 localStorage 存储（SC-02）

```typescript
// ⚠️ localStorage 容易被 XSS 读取
// 敏感信息（认证 token）优先用 httpOnly cookie
// 如必须用 localStorage，确保：
// 1. 不用存关键认证 token
// 2. 加 CSP 防止 XSS
// 3. 定期清理
```

### 1.4 URL 参数（SC-03）

```typescript
// ❌ 反例：敏感信息放 URL（被日志记录）
router.push(`/reset-password?token=${token}`)

// ✅ 敏感信息用 POST body 或 header
http.post('/reset-password', { token })
```

### 1.5 CSRF 防护

```typescript
// 后端：用 SameSite cookie + CSRF token
// 前端：所有写操作必须 POST/PUT/DELETE，不允许 GET

// 跨域请求带 credentials
http.post('/api/action', payload, {
  withCredentials: true
})
```

### 1.6 输入验证

```typescript
// 用户输入不直接信任，校验在前端 + 后端双重
const handleSubmit = (email: string) => {
  // 前端基础校验
  if (!/^[\w.-]+@[\w-]+\.\w+$/.test(email)) {
    message.error('邮箱格式错误')
    return
  }
  // 调用 API
  api.submit({ email })
}
```

### 1.7 第三方依赖安全

```bash
# 定期检查依赖漏洞
npm audit
npm audit fix

# 锁定版本
package-lock.json  # 必须提交
```

---

## 2. 可访问性（A11y）

### 2.1 语义化 HTML（SC-05）

```tsx
// ❌ 反例：用 div 模拟按钮
<div onClick={handleClick}>点击</div>

// ✅ 正例：语义化
<button onClick={handleClick}>点击</button>
```

### 2.2 表单标签

```tsx
// ❌ 反例：缺 label
<Input />

// ✅ 正例：关联 label
<Form.Item label="用户名" name="username">
  <Input />
</Form.Item>

// 或用 aria-label
<Input aria-label="搜索关键词" placeholder="搜索..." />
```

### 2.3 键盘导航

```tsx
// 所有可点击元素必须 keyboard 可达
// button / a 默认支持

// 自定义交互元素加 tabIndex
<div
  role="button"
  tabIndex={0}
  onClick={handleClick}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      handleClick()
    }
  }}
>
  点击
</div>
```

### 2.4 焦点管理

```tsx
import { useRef, useEffect } from 'react'

const Modal = ({ open, onClose, children }) => {
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (open) {
      // 打开时聚焦关闭按钮
      closeRef.current?.focus()
    }
  }, [open])

  return (
    <div role="dialog" aria-modal="true">
      {children}
      <button ref={closeRef} onClick={onClose}>关闭</button>
    </div>
  )
}
```

### 2.5 ARIA 属性

```tsx
// 错误状态
<Input
  status="error"
  aria-invalid="true"
  aria-describedby="username-error"
/>
<span id="username-error">用户名已存在</span>

// 加载状态
<div aria-busy={loading}>...</div>

// 隐藏装饰性元素
<Icon aria-hidden="true" />

// 实时区域
<div role="status" aria-live="polite">{message}</div>
```

### 2.6 颜色对比度（SC-08）

满足 WCAG AA：
- 正文：对比度 ≥ 4.5:1
- 大字体（18pt+）：对比度 ≥ 3:1

参考工具：
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- Chrome DevTools → Accessibility Tab

### 2.7 替代文本

```tsx
// 图片有 alt
<img src={item.image} alt={item.title} />

// 装饰图片 alt=""
<img src={decoration} alt="" role="presentation" />

// 复杂图有详细描述
<figure>
  <img src={chart} alt="销售趋势图" />
  <figcaption>2024 年 1-12 月销售数据</figcaption>
</figure>
```

### 2.8 跳过导航

```tsx
// 提供跳到主内容的链接（屏幕阅读器友好）
<a href="#main-content" className="skip-link">
  跳到主内容
</a>

<main id="main-content" tabIndex={-1}>
  ...
</main>
```

---

## 3. 安全审计 checklist

| 类别 | 检查项 |
|---|---|
| XSS | 无 `dangerouslySetInnerHTML` 直接渲染？如必须，sanitise？ |
| 敏感数据 | 不在 console.log 打印？localStorage 不存认证 token？ |
| URL | 敏感信息不放 URL 参数？ |
| CSRF | 写操作非 GET？带 credentials？ |
| 输入 | 用户输入前端校验？后端再校验？ |
| 依赖 | npm audit 无高危？ |
| HTTPS | 生产环境强制 HTTPS？ |
| CSP | 配置 Content-Security-Policy？ |

---

## 4. 可访问性 checklist

| 类别 | 检查项 |
|---|---|
| 语义化 | 用 button/a 不用 div 模拟？ |
| 标签 | 表单有关联 label？ |
| 键盘 | 交互元素 keyboard 可达？Enter/Space 处理？ |
| 焦点 | Modal 打开聚焦合理？Tab 顺序正确？ |
| ARIA | aria-label / role 正确？aria-live 用于动态消息？ |
| 对比度 | 文本对比度 ≥ 4.5:1？ |
| 替代文本 | 图片有 alt？装饰图 alt=""？ |
| 跳过导航 | 提供 skip link？ |

---

## 5. 常见反模式

| 反模式 | 风险 | 修复 |
|---|---|---|
| `dangerouslySetInnerHTML` 用户输入 | XSS | 不用，或 sanitise |
| 密码 / token 写 console | 泄露 | 删日志或脱敏 |
| localStorage 存认证 token | XSS 窃取 | httpOnly cookie |
| 敏感信息 URL 参数 | 泄露（日志 / Referer） | POST body |
| div 模拟按钮 | 键盘不可达 | 用 `<button>` |
| 缺 label | 表单不可用 | `<label>` / `aria-label` |
| 错误用纯色（无文本） | 色盲不友好 | 文本 + 图标 + 颜色 |
| 焦点陷阱缺失 | 键盘用户迷失 | Modal 内 Tab 循环 |
| 装饰图有 alt | 屏幕阅读器噪音 | `alt=""` |

---

## 6. 工具

| 工具 | 用途 |
|---|---|
| [axe DevTools](https://www.deque.com/axe/devtools/) | 自动 a11y 检查 |
| Chrome DevTools Lighthouse | A11y 评分 |
| [WAVE](https://wave.webaim.org/) | 网页 a11y 可视化 |
| `npm audit` | 依赖漏洞 |
| `eslint-plugin-jsx-a11y` | React a11y lint |
| [WebAIM Contrast](https://webaim.org/resources/contrastchecker/) | 颜色对比度 |

---

## 7. CI 集成

### 7.1 ESLint 规则

```json
// .eslintrc.json
{
  "plugins": ["jsx-a11y", "security"],
  "extends": [
    "plugin:jsx-a11y/recommended",
    "plugin:security/recommended"
  ],
  "rules": {
    "jsx-a11y/anchor-is-valid": "error",
    "jsx-a11y/click-events-have-key-events": "error",
    "jsx-a11y/no-static-element-interactions": "error",
    "security/detect-object-injection": "warn"
  }
}
```

### 7.2 自动化测试

```typescript
// jest-axe 检测 a11y
import { axe } from 'jest-axe'

test('BuyerStrategy 应该无 a11y 违规', async () => {
  const { container } = render(<BuyerStrategy />)
  const results = await axe(container)
  expect(results).toHaveNoViolations()
})
```

---

## 8. 复盘：从对话中提炼

本对话中**未涉及**安全 / 可访问性相关 Bug。但作为审查技能，需要保留相关检查项。

### 8.1 风险场景

| 场景 | 风险 | 预防 |
|---|---|---|
| 抢单策略配置修改 | 误操作导致自动拍下 | UI 二次确认 + 风险提示 |
| 任务批量启动 | 影响范围不可控 | 数量预览 + 二次确认 |
| Cookie 导入 | XSS / 注入 | 服务端 sanitise |
| 商品搜索结果展示 | 卖家输入可能含 HTML | React 默认转义 |

---

## 9. 参考

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [WCAG 2.1 指南](https://www.w3.org/WAI/WCAG21/quickref/)
- [MDN Web A11y](https://developer.mozilla.org/en-US/docs/Web/Accessibility)
- [React A11y](https://react.dev/learn/accessibility)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)
