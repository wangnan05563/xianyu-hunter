# 维度 26：缓存 / Schema 演进

> **编码规范引用**：coding-standards v1.3 §缓存 TTL 配置化 / 空结果缓存 / 缓存写入守卫独立
> **配置节点**：config.yaml#cache / refactoring_safety
> **对应 references**：cache-state-migration-patterns.md

## 触发条件
- 缓存 TTL / key 设计变更
- DB Schema 变更（ALTER TABLE / migration / 新增列）
- 缓存写入/失效逻辑变更
- Alembic 迁移脚本

## 检查规则

### 强制（P0 阻塞）
- Schema 变更必须向后兼容：新增列必须有默认值；禁止删除生产环境已存在的列（先标记 deprecated，下一个大版本再删除）
- 缓存 key 必须版本化：格式 `{prefix}:{version}:{identifier}`，升级时变更 version 避免新旧缓存冲突
- 迁移脚本必须幂等：`IF NOT EXISTS` / `IF EXISTS` 包裹，重复执行不报错
- DB migration 失败处理策略：ALTER TABLE 失败后旧表不能丢失数据（RENAME 后新表创建失败时回滚 RENAME）

### 推荐（P1 严重）
- 缓存 TTL 从 `config.yaml` 读取，禁止模块级硬编码常量
- 空结果（0 条记录）必须缓存，避免反复触发底层查询
- 缓存写入守卫独立于上游业务逻辑（`if filtered:` cache write vs `if items:` DB write 各自独立）
- 持久化层变更后必须显式调用 `invalidate_cache()` 或等价方法

### 禁止
- 缓存 TTL 硬编码在代码中（如 `_LIVE_CACHE_TTL = 60`）
- Schema 变更直接删除列（破坏向后兼容）
- 迁移脚本非幂等（重复执行报错）

## Grep 扫描命令

```bash
# 硬编码 TTL
grep -rn "_TTL\s*=.*\d+\|TTL.*=.*\d+\|ttl\s*=.*\d+" src/xianyu_hunter/ --include="*.py" | grep -v "config\|get_config"

# 缓存 key 版本化
grep -rn "cache.*key\|CACHE_KEY\|_CACHE_.*=" src/xianyu_hunter/ --include="*.py"

# invalidate_cache
grep -rn "invalidate_cache\|cache.*clear\|cache.*reset" src/xianyu_hunter/ --include="*.py"

# migration 幂等性
grep -rn "IF NOT EXISTS\|IF EXISTS\|DROP TABLE\|DROP COLUMN\|ALTER TABLE" src/xianyu_hunter/ --include="*.py"

# 向后兼容：缺少默认值的新列
grep -rn "sa\.Column.*nullable=False" src/xianyu_hunter/ --include="*.py" | grep -v "default"
```

## 判断标准
- 缓存 TTL 硬编码 → P0 阻塞
- Schema 变更删除列 → P0 阻塞
- 迁移脚本非幂等 → P0 阻塞
- 空结果未缓存 → P1 严重
- 缓存写入守卫与业务逻辑耦合 → P1 严重
- 持久化层变更后未失效缓存 → P1 严重

## 适用/不适用场景
- **适用**：所有缓存相关代码；DB migration 脚本；Schema 变更涉及代码
- **不适用**：无缓存存储的应用；纯内存缓存无持久化
