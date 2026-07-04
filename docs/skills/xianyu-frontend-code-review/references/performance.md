# 前端性能审查（Performance）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)

---

## 1. 避免不必要重渲染

### 1.1 Selector 订阅（最常见问题）

```tsx
// ❌ 反例：订阅整个 store
const store = useConfigStore()
return <div>{store.config?.eval?.auto_buy_score}</div>

// ✅ 正例：selector 订阅
const autoBuyScore = useConfigStore(s => s.config?.eval?.auto_buy_score)
return <div>{autoBuyScore}</div>
```

### 1.2 React.memo 包装重组件

```tsx
// ❌ 重组件随父组件重渲染
const HeavyTable = ({ data }) => {
  return <Table dataSource={data} columns={columns} />
}

// ✅ memo 包装
const HeavyTable = React.memo(({ data }: { data: Item[] }) => {
  return <Table dataSource={data} columns={columns} }
})
```

### 1.3 useCallback 稳定回调

```tsx
// ❌ 每次渲染都创建新函数
return <ChildComponent onChange={(v) => setField(v)} />

// ✅ 稳定引用
const handleChange = useCallback((v: number) => setField(v), [])
return <ChildComponent onChange={handleChange} />
```

### 1.4 useMemo 缓存重计算

```tsx
// ❌ 每次渲染都重算
const sortedItems = items.sort((a, b) => b.score - a.score)

// ✅ memo 缓存
const sortedItems = useMemo(
  () => [...items].sort((a, b) => b.score - a.score),
  [items]
)
```

---

## 2. 列表性能

### 2.1 稳定 key（PF-02）

```tsx
// ❌ 用 index 作 key
{items.map((item, idx) => <Item key={idx} {...item} />)}

// ✅ 用业务 ID
{items.map((item) => <Item key={item.id} {...item} />)}
```

### 2.2 大列表虚拟滚动

```tsx
import { Virtual } from '@arco-design/web-react'  // 或 antd-virtual

<Table
  dataSource={items}  // 10000+ 条
  scroll={{ y: 600 }}
  pagination={false}
  components={{
    body: { row: VirtualRow }  // 虚拟滚动行
  }}
/>
```

### 2.3 表格列定义 useMemo

```tsx
// ❌ 每次渲染都重建
const columns = [
  { title: 'ID', dataIndex: 'id' },
  { title: '价格', dataIndex: 'price' },
  // ...
]

// ✅ 稳定引用
const columns = useMemo(() => [...], [])
```

---

## 3. 加载与懒加载

### 3.1 路由级代码分割

```tsx
import { lazy, Suspense } from 'react'

const BuyerStrategy = lazy(() => import('./pages/Config/BuyerStrategy'))

<Route
  path="/app/config/buyer"
  element={
    <Suspense fallback={<Spin />}>
      <BuyerStrategy />
    </Suspense>
  }
/>
```

### 3.2 图片懒加载

```tsx
<img src={item.image} loading="lazy" alt={item.title} />
```

### 3.3 组件级懒加载

```tsx
const DiffPreviewModal = lazy(() => import('./DiffPreviewModal'))

{showDiff && (
  <Suspense fallback={null}>
    <DiffPreviewModal {...props} />
  </Suspense>
)}
```

---

## 4. 频繁操作优化

### 4.1 Debounce 输入

```tsx
import { useDebouncedValue } from '@/hooks/useDebouncedValue'

const [searchInput, setSearchInput] = useState('')
const debouncedSearch = useDebouncedValue(searchInput, 300)

useEffect(() => {
  // 实际搜索
  api.search(debouncedSearch)
}, [debouncedSearch])
```

### 4.2 Throttle 滚动

```tsx
const handleScroll = useMemo(
  () => throttle((e: Event) => {
    // 滚动处理
  }, 100),
  []
)
```

### 4.3 防重复点击

```tsx
const [submitting, setSubmitting] = useState(false)

const handleSubmit = async () => {
  if (submitting) return  // 防止重复
  setSubmitting(true)
  try {
    await api.submit()
  } finally {
    setSubmitting(false)
  }
}
```

---

## 5. 内存泄漏

### 5.1 useEffect 清理

```tsx
useEffect(() => {
  const timer = setInterval(() => {
    // 定时任务
  }, 1000)

  return () => clearInterval(timer)  // 清理
}, [])
```

### 5.2 取消请求

```tsx
useEffect(() => {
  const controller = new AbortController()

  fetch('/api/items', { signal: controller.signal })
    .then(r => r.json())
    .then(setItems)
    .catch(e => {
      if (e.name !== 'AbortError') console.error(e)
    })

  return () => controller.abort()  // 取消
}, [])
```

### 5.3 事件监听清理

```tsx
useEffect(() => {
  const handler = (e: KeyboardEvent) => { /* ... */ }
  window.addEventListener('keydown', handler)
  return () => window.removeEventListener('keydown', handler)
}, [])
```

---

## 6. Bundle Size 优化

### 6.1 按需引入 Ant Design

```tsx
// ✅ Vite 自动 tree-shake
import { Button, Form } from 'antd'

// ❌ 引入全量
import Antd from 'antd'
```

### 6.2 第三方库替换

- `moment` → `dayjs`（更小）
- `lodash` → `lodash-es`（按需 import）
- `chart.js` → 按需 import 组件

### 6.3 Bundle 分析

```bash
cd frontend && npm run build -- --analyze
```

查看 `dist/stats.html` 找到体积大户。

---

## 7. 网络性能

### 7.1 请求合并

```tsx
// ❌ 循环单请求
for (const id of ids) {
  await api.getItem(id)
}

// ✅ 批量接口
await api.getItems(ids)  // 后端支持批量
```

### 7.2 数据缓存

```tsx
import { useQuery } from '@tanstack/react-query'

const { data, isLoading } = useQuery({
  queryKey: ['config'],
  queryFn: () => configApi.get(),
  staleTime: 5 * 60 * 1000  // 5 分钟内不重新请求
})
```

### 7.3 取消重复请求

```tsx
const lastRequest = useRef<AbortController>()

const fetchData = async () => {
  lastRequest.current?.abort()  // 取消上一次
  lastRequest.current = new AbortController()
  const data = await fetch('/api/x', { signal: lastRequest.current.signal })
}
```

---

## 8. 渲染性能

### 8.1 避免内联对象 / 数组

```tsx
// ❌ 每次渲染新对象
<Component style={{ margin: 10 }} items={[1, 2, 3]} />

// ✅ 提取
const STYLE = { margin: 10 }
const ITEMS = [1, 2, 3]

<Component style={STYLE} items={ITEMS} />
```

### 8.2 条件渲染拆分

```tsx
// ❌ 父组件重渲染导致子组件全重渲染
return (
  <div>
    <HeavyA />
    {showB && <HeavyB />}
    <HeavyC />
  </div>
)

// ✅ 拆分子组件，各自 memo
const HeavyA = memo(...)
const HeavyB = memo(...)
```

### 8.3 列表项用 memo

```tsx
const Item = memo(({ data, onClick }: ItemProps) => {
  return <div onClick={() => onClick(data.id)}>{data.name}</div>
})
```

---

## 9. 性能审查 checklist

| 类别 | 检查项 |
|---|---|
| 重渲染 | Zustand selector 订阅？React.memo 包装？useCallback 稳定回调？ |
| 列表 | 稳定 key？大列表虚拟滚动？ |
| 加载 | 路由 lazy？图片 lazy？大组件 lazy？ |
| 频繁操作 | Debounce / Throttle？防重复点击？ |
| 内存 | useEffect 清理？取消请求？事件监听清理？ |
| Bundle | 按需 import？替换大体积库？ |
| 网络 | 批量请求？数据缓存？取消重复？ |
| 渲染 | 内联对象？条件渲染拆分？列表 memo？ |

---

## 10. 性能工具

| 工具 | 用途 |
|---|---|
| React DevTools Profiler | 找出重渲染组件 |
| Chrome Performance Tab | 录制运行时性能 |
| Lighthouse | 综合性能评分 |
| `why-did-you-render` | 开发环境检测不必要重渲染 |
| Bundle Analyzer | 分析 bundle 体积 |

---

## 11. 参考

- [React 性能优化](https://react.dev/learn/render-and-commit)
- [Web Vitals](https://web.dev/vitals/)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)
