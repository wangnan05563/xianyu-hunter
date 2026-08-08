# 性能与缓存

> 性能优化量化验证、缓存 TTL 合理性、缓存守卫原则、数据写入策略、回调注入默认值。
>
> 涵盖规范: #93, #94, #104, #105, #106
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #93 性能优化量化验证
每个优化必须定义可量化指标（优化前/后值），并通过运行时测试验证，禁止主观描述
- grep: `grep "优化前\|优化后\|before\|after" docs/` 找不到量化指标 → 补充验证

### #94 缓存 TTL 合理性校验
TTL 必须 >= 被缓存操作平均耗时 × 期望命中倍数（默认 3）；注释须说明取值依据；TTL 从 config 读取
- grep: `grep "_TTL\s*=\s*\d" src/` 找到硬编码 TTL → 应改为 config 读取

### #104 缓存守卫三原则
TTL 配置化（禁止硬编码）、空结果不缓存（防掩盖实时数据）、守卫独立于业务逻辑
- grep: 模块级常量 `_XXX_CACHE_TTL = N` → 违反原则1

### #105 数据写入策略字段级决策
字段按语义分四类策略：alwaysOverwrite（状态类）/ coalesceIfTruthy（数值类）/ fillIfMissing（标识类）/ overwriteIfNotBlank（基本信息）
- grep: `grep "for k, v in new_data.items(): old\[k\] = v"` 无条件覆盖 → 必须字段级决策

### #106 回调注入默认值模式
可选回调必须提供默认空实现（`lambda *a, **kw: None`），禁止 `if callback: callback()`；回调依赖通过闭包注入
- grep: `grep "if on_success: on_success" src/` → 应改为 `on_success = on_success or noop`
