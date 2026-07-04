# antd 5 关键模式审查

> **来源**：从数据库维护模块开发中遇到的问题提炼
> **适用范围**：所有使用 antd 5 的前端页面
> **核心原则**：用框架提供的 API，不要绕过框架操作 DOM

---

## 一、Modal.confirm 动态状态管理

### 1.1 问题原型

用户在删除确认弹窗中输入确认词后，"确认删除"按钮仍然禁用。

**根因**：`okButtonProps: { disabled: true }` 让按钮永远禁用，而 `setTimeout + querySelector` 操作 DOM 在 antd 5 的 Modal.confirm 中不可靠（DOM 结构与普通 Modal 不同）。

### 1.2 审查规则

| 规则 | 说明 |
|---|---|
| ✅ 用 `modal.update()` | 动态更新 `okButtonProps.disabled` |
| ❌ 禁止 `querySelector` | antd 5 Modal.confirm DOM 结构不稳定 |
| ❌ 禁止 `setTimeout` | 竞态条件 + DOM 可能未渲染 |

### 1.3 正确模式

```typescript
let tokenValue = ''
const modal = Modal.confirm({
  okButtonProps: { danger: true, disabled: true },
  content: (
    <Input.Password onChange={(e) => {
      tokenValue = e.target.value
      modal.update((prev) => ({
        ...prev,
        okButtonProps: { danger: true, disabled: tokenValue !== CONFIRM_TOKEN },
      }))
    }} />
  ),
})
```

### 1.4 错误模式

```typescript
// ❌ DOM 操作（不可靠）
setTimeout(() => {
  const okBtn = document.querySelector('.ant-btn-primary')
  if (okBtn) okBtn.removeAttribute('disabled')
}, 100)

// ❌ 只更新变量，不触发按钮状态
onChange={(e) => { ref.value = e.target.value }}  // 按钮仍然 disabled
```

---

## 二、Menu onClick 路径守卫

### 2.1 问题原型

点击"系统维护"SubMenu 标题时触发 `navigate('sub-maintenance')`，跳转到非法 URL。

**根因**：antd 5 在某些版本中点击 SubMenu 标题会触发 `onClick`，传入的 `key` 是 SubMenu 的 key（如 `'sub-maintenance'`），不是路由路径。

### 2.2 审查规则

| 规则 | 说明 |
|---|---|
| ✅ onClick 校验路径 | `if (key.startsWith('/')) navigate(key)` |
| ❌ 禁止无校验 navigate | `onClick={({ key }) => navigate(key)}` |

### 2.3 正确模式

```typescript
<Menu
  onClick={({ key }) => {
    if (typeof key === 'string' && key.startsWith('/')) {
      navigate(key)
    }
  }}
/>
```

### 2.4 适用场景

- ✅ 所有包含 SubMenu 的 Menu 组件
- ✅ Menu items 中混合了路径 key 和非路径 key 的场景
- ❌ 纯展示型菜单（无导航功能）

---

## 三、表格列中文标注

### 3.1 审查规则

| 规则 | 说明 |
|---|---|
| 列标题必须有中文 | 用 `label.split('（')[0]` 显示中文简称 |
| Tooltip 显示完整标注 | hover 时展示包含类型特征/约束的完整标注 |
| PK 标记 | 主键列在标题中显示 `<Tag color="blue">PK</Tag>` |
| 类型标签 | 标题中显示列类型（如 `VARCHAR` / `INTEGER`） |

### 3.2 正确模式

```typescript
title: (
  <Tooltip title={col.label || `${col.type}${col.nullable ? '' : ' NOT NULL'}`}>
    <Space size={4}>
      <span>{col.label ? col.label.split('（')[0] : col.name}</span>
      {col.primary_key && <Tag color="blue">PK</Tag>}
    </Space>
  </Tooltip>
)
```

---

## 四、路由同步检查

### 4.1 问题原型

新增"数据库维护"菜单后，点击菜单跳转到 `/app`（首页）。

**根因**：`App.tsx` 路由表缺少 `maintenance/db` 路由，React Router 的 `<Route path="*">` 兜底跳转到首页。

### 4.2 审查清单

新增页面时必须同步检查：

| # | 检查项 | 文件 | 遗漏症状 |
|---|---|---|---|
| ① | 路由表添加 Route | `App.tsx` | 点击菜单跳到首页/404 |
| ② | 菜单项添加 | `MainLayout.tsx` | 菜单中看不到入口 |
| ③ | 页面组件创建 | `pages/` | 路由匹配但白屏 |
| ④ | 构建验证 | 终端 | TS 编译错误未发现 |

### 4.3 特别注意

- 子路由（如 `/maintenance/db`）必须在父路由（`/maintenance`）之后、`path="*"` 之前声明
- 否则会被 `path="*"` 兜底匹配，导致导航异常
- Menu 的 `selectedKey` 应使用最长前缀匹配，避免 `/maintenance/db` 被误匹配到 `/maintenance`

---

## 五、检查清单

审查前端代码时：

- [ ] Modal.confirm 动态状态用 `modal.update()`，未使用 DOM 操作
- [ ] Menu onClick 做了路径守卫（`startsWith('/')`）
- [ ] 表格列标题有中文标注 + Tooltip
- [ ] 新增页面的路由-菜单-组件三同步
- [ ] 子路由声明在 fallback 路由之前
- [ ] Menu selectedKey 用最长前缀匹配
