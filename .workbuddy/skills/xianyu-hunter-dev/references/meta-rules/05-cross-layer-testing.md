# 跨层契约与测试

> 事件多发布点对齐、路由注册同步、query string 保留、测试同步责任、外部依赖隔离。
>
> 涵盖规范: #43, #44, #45, #46, #47
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #43 事件多发布点字段对齐
业务事件多发布点payload必须字段集一致。消费方按字段分支必须有fallback
- grep: `grep "<event_type>" src/` ≥2处但payload字段集不同 → 违规

### #44 前端路由三重注册同步
L1路由声明(App.tsx) → L2多页签注册(sheetRegistry) → L3 URL同步Hook(useSheetSync) 三处同步
- grep: git diff显示新增Route但同PR内sheetRegistry无对应条目 → L2缺失

### #45 外部回链 query string 保留
回链路由必须 location.pathname + location.search，依赖数组必须含 location.search
- grep: `grep "location.pathname" useSheetSync.ts` 无 `location.search` → query string丢失

### #46 测试同步责任原则
接口签名变更/async↔sync重构必须同步测试。测试mock必须与生产Pydantic 1:1对齐
- grep: git diff显示签名变更但tests/无对应修改 → 同步缺失

### #47 外部依赖隔离测试可重复性
测试中get_secret/os.environ/Path.read_text必须patch隔离，禁止依赖生产fallback
- grep: `grep "get_secret" tests/` 无 `patch` → 外部依赖未隔离
