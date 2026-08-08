# 16. 性能评审

- 【强制】复用 props（对象、数组、Map）使用 `useMemo` 保证引用稳定
- 【强制】回调函数使用 `useCallback` 避免子组件不必要渲染
- 【强制】`useEffect` 依赖数组完整性（避免遗漏依赖导致 stale closure）
- 【强制】列表渲染使用稳定的 `key`，**禁止**用 index
- 【强制】大列表虚拟化（`react-window`/`react-virtualized`）
- 【禁止】在 render 内创建新对象/数组
- 【强制】React Flow 数据使用 `useNodes`/`useEdges`（不手动拉取）
- 【强制】echarts 5.5 按需导入
- 【强制】网络重连（SSE/WebSocket/API 重试）必须有最大次数限制，超限后退化为降级方案（如轮询）
- 【强制】无限重连循环（`setTimeout(connect, N)` 无计数器）视为资源浪费风险
