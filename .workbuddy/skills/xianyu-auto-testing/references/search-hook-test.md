# 模式 AC：搜索 Hook 模式回归测试（useSearch / useSearchHistory）

> **版本**：v2.4.0（2026-07-25 第九轮复盘落地）
> **关联复盘**：`xianyu-hunter-dev/references/retrospective-2026-07-25-r3.md`（第九轮复盘）
> **关联规范**：`xianyu-hunter-dev` step 271/272（useSearch/useSearchHistory）+ coding-standards v1.3 §3.16-3.20
> **配套检查点**：
> - 前端：`xianyu-frontend-code-review` v4.65.0 F-REVIEW-236~240

---

## 测试目标

验证前端搜索 Hook 标准化机制（useSearch 400ms 防抖 + requestId 并发保护 + useSearchHistory localStorage 持久化 + LRU 去重 + 命名空间隔离），防止"搜索框抖动频繁发请求 / 搜索结果闪烁（旧响应覆盖新响应）/ 刷新后搜索历史丢失 / 历史重复条目"问题再次出现。

## 测试范围

| 层 | 文件 | 检查点 |
|---|---|---|
| 前端 Hook 层 | `frontend/src/hooks/useSearch.ts` | F-REVIEW-236 USE-SEARCH-DEBOUNCE-CONCURRENCY |
| 前端 Hook 层 | `frontend/src/hooks/useSearch.ts` | F-REVIEW-237 USE-SEARCH-ENABLED-CLEANUP |
| 前端 Hook 层 | `frontend/src/hooks/useSearchHistory.ts` | F-REVIEW-238 USE-SEARCH-HISTORY-PERSISTENCE |
| 前端 Hook 层 | `frontend/src/hooks/useSearchHistory.ts` | F-REVIEW-239 USE-SEARCH-HISTORY-NAMESPACE |
| 前端 Hook 层 | `frontend/src/hooks/useSearchHistory.ts` | F-REVIEW-240 USE-SEARCH-HISTORY-DECLARATION-ORDER |
| 前端接入层 | `frontend/src/pages/**/*.tsx` | F-REVIEW-236（裸 setTimeout/fetch 红旗） |
| 前端测试层 | `frontend/src/hooks/__tests__/useSearch.test.ts` | 单元测试覆盖 |
| 前端测试层 | `frontend/src/hooks/__tests__/useSearchHistory.test.ts` | 单元测试覆盖 |

---

## 测试用例矩阵

### AC-T01：useSearch 防抖与并发保护测试（F-REVIEW-236）

**场景**：用户在搜索框快速输入 5 次（100ms 间隔），验证只发起最后一次请求

**测试步骤**：
1. 渲染接入 useSearch 的组件
2. 模拟用户输入：100ms 间隔触发 5 次 onChange
3. 等待 500ms（超过防抖时间 400ms）
4. 验证 fetch 调用次数

**预期**：
- fetch 只被调用 1 次（最后一次输入的关键词）
- 无中间请求被发起

**测试代码示例**：
```typescript
import { renderHook, act } from '@testing-library/react';
import { useSearch } from '../useSearch';

test('useSearch 400ms 防抖：100ms 间隔触发 5 次只发起 1 次请求', async () => {
  const fetcher = jest.fn();
  const { result } = renderHook(() => useSearch({ fetcher, debounceMs: 400 }));

  // 100ms 间隔触发 5 次
  for (let i = 0; i < 5; i++) {
    act(() => {
      result.current.setKeyword(`keyword-${i}`);
    });
    await new Promise(r => setTimeout(r, 100));
  }

  // 等待 500ms（超过防抖时间）
  await new Promise(r => setTimeout(r, 500));

  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher).toHaveBeenCalledWith('keyword-4');
});
```

### AC-T02：useSearch requestId 并发保护测试（F-REVIEW-236）

**场景**：第一次搜索响应延迟 1s，第二次搜索响应立即返回，验证不会用旧响应覆盖新响应

**测试步骤**：
1. 触发第一次搜索（响应延迟 1s）
2. 100ms 后触发第二次搜索（响应立即返回）
3. 等待所有响应返回
4. 验证最终结果为第二次响应

**预期**：
- 最终结果为第二次搜索的响应
- 第一次搜索的响应被丢弃（requestId 不匹配）

**测试代码示例**：
```typescript
test('useSearch requestId 并发保护：慢响应不覆盖快响应', async () => {
  const slowFetcher = jest.fn().mockImplementation(
    () => new Promise(r => setTimeout(() => r('slow-result'), 1000))
  );
  const fastFetcher = jest.fn().mockResolvedValue('fast-result');

  const { result, rerender } = renderHook(
    ({ fetcher }) => useSearch({ fetcher, debounceMs: 0 }),
    { initialProps: { fetcher: slowFetcher } }
  );

  act(() => result.current.setKeyword('slow'));
  await new Promise(r => setTimeout(r, 50));

  rerender({ fetcher: fastFetcher });
  act(() => result.current.setKeyword('fast'));
  await new Promise(r => setTimeout(r, 1100));

  expect(result.current.result).toBe('fast-result');
});
```

### AC-T03：useSearch enabled 条件搜索测试（F-REVIEW-237）

**场景**：`enabled: false` 时不发请求；`enabled` 变为 `true` 时自动触发搜索

**测试步骤**：
1. 初始 `enabled: false`，触发搜索，验证无请求
2. 切换 `enabled: true`，验证自动触发搜索

**预期**：
- `enabled: false` 时 fetcher 不被调用
- `enabled` 变为 `true` 时 fetcher 被调用

### AC-T04：useSearch 卸载清理测试（F-REVIEW-237）

**场景**：组件卸载时必须 clearTimeout 并取消进行中请求

**测试步骤**：
1. 渲染 Hook，触发搜索（防抖中）
2. 立即卸载组件
3. 等待超过防抖时间
4. 验证 fetcher 未被调用

**预期**：
- 卸载后 fetcher 不被调用
- 无 "Can't perform a React state update on an unmounted component" 警告

**测试代码示例**：
```typescript
test('useSearch 卸载清理：卸载后不发起请求', async () => {
  const fetcher = jest.fn();
  const { result, unmount } = renderHook(() => useSearch({ fetcher, debounceMs: 400 }));

  act(() => result.current.setKeyword('test'));
  unmount();

  await new Promise(r => setTimeout(r, 500));
  expect(fetcher).not.toHaveBeenCalled();
});
```

### AC-T05：useSearchHistory localStorage 持久化测试（F-REVIEW-238）

**场景**：触发搜索 → 刷新页面 → 验证历史保留

**测试步骤**：
1. 渲染 Hook，调用 `add('item1')`、`add('item2')`
2. 读取 localStorage
3. 重新渲染 Hook（模拟刷新）
4. 验证历史保留

**预期**：
- localStorage 中存在 `xh_search_history.default` key
- 历史包含 `['item2', 'item1']`（LRU 顺序，最新在前）
- 重新渲染后历史保留

**测试代码示例**：
```typescript
test('useSearchHistory localStorage 持久化与 LRU 去重', () => {
  const { result } = renderHook(() => useSearchHistory({ namespace: 'items' }));

  act(() => result.current.add('item1'));
  act(() => result.current.add('item2'));
  act(() => result.current.add('item1')); // 重复，应移到首位

  expect(result.current.history).toEqual(['item1', 'item2']);

  // 验证 localStorage 持久化
  const stored = JSON.parse(localStorage.getItem('xh_search_history.items') || '[]');
  expect(stored).toEqual(['item1', 'item2']);
});
```

### AC-T06：useSearchHistory max_items 上限测试（F-REVIEW-238）

**场景**：添加 25 条历史（超过 max_items=20），验证最旧的被淘汰

**测试步骤**：
1. 渲染 Hook（max_items=20）
2. 添加 25 条历史
3. 验证历史数量为 20
4. 验证最旧的 5 条被淘汰

**预期**：
- 历史数量 = 20
- 历史前 20 条为最新添加的（item24~item4，去重后）

### AC-T07：useSearchHistory 命名空间隔离测试（F-REVIEW-239）

**场景**：在 `items` 命名空间搜索后，`sellers` 命名空间的历史不应包含该关键词

**测试步骤**：
1. 渲染 Hook（namespace='items'），添加 'item1'
2. 渲染 Hook（namespace='sellers'），添加 'seller1'
3. 验证两个命名空间的历史相互独立

**预期**：
- `items` 命名空间历史 = ['item1']
- `sellers` 命名空间历史 = ['seller1']
- localStorage 中存在两个独立的 key：`xh_search_history.items` 和 `xh_search_history.sellers`

**测试代码示例**：
```typescript
test('useSearchHistory 命名空间隔离', () => {
  const { result: itemsHook } = renderHook(() => useSearchHistory({ namespace: 'items' }));
  const { result: sellersHook } = renderHook(() => useSearchHistory({ namespace: 'sellers' }));

  act(() => itemsHook.current.add('item1'));
  act(() => sellersHook.current.add('seller1'));

  expect(itemsHook.current.history).toEqual(['item1']);
  expect(sellersHook.current.history).toEqual(['seller1']);

  // 验证 localStorage 独立 key
  expect(localStorage.getItem('xh_search_history.items')).toContain('item1');
  expect(localStorage.getItem('xh_search_history.sellers')).toContain('seller1');
});
```

### AC-T08：useSearchHistory storageKey useMemo 稳定性测试（F-REVIEW-240）

**场景**：storageKey 必须用 useMemo 固定，避免每次渲染生成新字符串

**测试步骤**：
1. 渲染 Hook
2. 触发重新渲染（如调用 add）
3. 验证 storageKey 引用稳定性

**预期**：
- 多次渲染后 storageKey 引用相同（`===`）
- add/clear/remove 的 useCallback 依赖稳定

**测试代码示例**：
```typescript
test('useSearchHistory storageKey useMemo 稳定性', () => {
  let storageKeyRefs: string[] = [];
  const { result, rerender } = renderHook(() => {
    const hook = useSearchHistory({ namespace: 'items' });
    storageKeyRefs.push(hook.storageKey);
    return hook;
  });

  act(() => result.current.add('item1'));
  rerender();
  act(() => result.current.add('item2'));

  // 验证 storageKey 引用稳定（同一字符串实例）
  const firstRef = storageKeyRefs[0];
  storageKeyRefs.forEach(ref => {
    expect(ref).toBe(firstRef);  // === 比较引用
  });
});
```

### AC-T09：useSearchHistory 声明顺序测试（F-REVIEW-240）

**场景**：若 `useSearchHistory` 与 `loadSessions` 等 useCallback 互相依赖，声明顺序必须满足"被依赖者先声明"

**测试步骤**：
1. 静态扫描接入页面（如 Chatbot/index.tsx）
2. 提取所有 useCallback / useState 声明顺序
3. 验证 useSearchHistory 在依赖它的 useCallback 之前声明

**预期**：
- useSearchHistory 在 loadSessions 之前声明
- 无循环依赖

**历史失败案例**：
- 文件：`frontend/src/pages/Chatbot/index.tsx`
- 问题：`addSessionHistory` 在 `loadSessions` 之后声明，但 `loadSessions` 的 useCallback 依赖了它
- 修复：将 `useSearchHistory` 声明移到 `loadSessions` 之前

### AC-T10：搜索接入页面裸 setTimeout/fetch 红旗扫描（F-REVIEW-236）

**场景**：搜索接入页面必须使用 useSearch，禁止裸 setTimeout/fetch

**测试步骤**：
1. grep 所有 `frontend/src/pages/**/*.tsx` 文件
2. 扫描裸 `setTimeout(.*search` 或 `setTimeout(.*fetch` 模式
3. 排除豁免页面（如 TaskDetail.tsx、Evaluations/index.tsx 等）

**预期**：
- 非豁免页面无裸 setTimeout/fetch 红旗
- 豁免页面有明确说明（如纯手动搜索按钮）

**测试代码示例**：
```typescript
import { glob } from 'glob';
import * as fs from 'fs';

test('搜索接入页面无裸 setTimeout/fetch 红旗', () => {
  const exemptPages = [
    'frontend/src/pages/TaskDetail.tsx',
    'frontend/src/pages/Evaluations/index.tsx',
    'frontend/src/pages/BatchRefresh.tsx',
    'frontend/src/pages/Logs/Logs.tsx',
    'frontend/src/pages/Chatbot/index.tsx',
  ];

  const files = glob.sync('frontend/src/pages/**/*.tsx')
    .filter(f => !exemptPages.includes(f));

  const redFlags = [
    /setTimeout\([^)]*search/i,
    /setTimeout\([^)]*fetch/i,
    /setTimeout\([^)]*query/i,
  ];

  files.forEach(file => {
    const content = fs.readFileSync(file, 'utf-8');
    redFlags.forEach(pattern => {
      expect(content).not.toMatch(pattern);
    });
  });
});
```

---

## 静态扫描清单

| 扫描项 | grep 模式 | 严重等级 |
|---|---|---|
| useSearch 无防抖 | `useSearch` 实现缺 `setTimeout`/`clearTimeout` | P0 |
| useSearch 无 requestId 保护 | `useSearch` 实现缺 `requestIdRef` | P0 |
| 搜索接入页面裸 setTimeout | `setTimeout\([^)]*search` | P0 |
| 搜索接入页面裸 fetch | `setTimeout\([^)]*fetch` | P0 |
| useSearchHistory 无 localStorage | `useSearchHistory` 实现缺 `localStorage.setItem` | P0 |
| useSearchHistory 无去重 | `useSearchHistory` add 未检查重复 | P0 |
| storageKey 未用 useMemo | `useSearchHistory` 实现缺 `useMemo.*storageKey` | P1 |
| 声明顺序错误 | `useSearchHistory` 在依赖它的 useCallback 之后 | P1 |

---

## 运行时验证清单

| 验证项 | 方法 | 严重等级 |
|---|---|---|
| 400ms 防抖触发 | 100ms 间隔触发 5 次，验证只发起 1 次请求 | P0 |
| requestId 并发保护 | 慢响应不覆盖快响应 | P0 |
| 卸载清理 | 卸载后 fetcher 不被调用 | P0 |
| localStorage 持久化 | 刷新后历史保留 | P0 |
| LRU 去重 | 重复关键词移到首位 | P0 |
| max_items 上限 | 超过上限淘汰最旧 | P0 |
| 命名空间隔离 | 跨命名空间无污染 | P1 |
| storageKey 稳定性 | 多次渲染引用相同 | P1 |

---

## 适用场景与不适用场景

| 流程 | 适用场景 | 不适用场景 |
|---|---|---|
| useSearch 防抖 | 前端搜索框输入场景 | 服务端搜索（无前端防抖） |
| useSearch enabled | 条件搜索（如选择分类后才搜索） | 全局搜索（永不卸载） |
| useSearchHistory 持久化 | 搜索框历史下拉 | 无痕模式（localStorage 不可用） |
| useSearchHistory 命名空间 | 多页面独立历史 | 单页面搜索 |
| storageKey useMemo | Hook 接入页面 | 类组件（不使用 Hook） |

---

## 跨技能联动

- **配套审查**：`xianyu-frontend-code-review` v4.65.0 F-REVIEW-236~240
- **配套编码规范**：`xianyu-hunter-dev` step 271/272（useSearch/useSearchHistory）+ coding-standards v1.3 §3.16-3.20
- **配套后端测试**：`xianyu-auto-testing` 模式 AB（SearchService 模板方法测试）
- **配套复盘**：`xianyu-hunter-dev/references/retrospective-2026-07-25-r3.md`（第九轮复盘）
