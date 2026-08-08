# 维度 36：工程闭环元规范

> **编码规范引用**：coding-standards v1.3 §meta-rules #52-#55
> **配置节点**：config.yaml#engineering_closure

## 触发条件
- 新功能开发完成
- Bug 修复后
- 文档更新
- 测试用例增删
- 配置参数变更

## 检查规则

### 强制（P0 阻塞）
- **文档与代码同步**：接口/模型/配置变更必须同步更新对应文档（docstring、README、config.example.yaml）
- **测试覆盖闭环**：新增/修改功能必须有对应的单元测试；修复的 Bug 必须有回归测试
- **反馈循环机制**：上线后必须有监控/日志/告警机制确认功能正常，不能"上线即忘记"

### 推荐（P1 严重）
- 修复后添加调试日志验证修复生效（数据提取类修复尤其重要）
- 配置参数变更同步更新 `config.example.yaml`（新用户可参考）
- 新增 API 端点同步更新 auth_whitelist（如需要）
- 新增索引同步更新 `init_db()` 中的 `_migrate_create_index`
- 验收标准可验证：每个需求/修复有明确的可执行验收步骤

### 禁止
- 接口变更不更新文档（导致文档与实现脱节）
- 修复 Bug 后无回归测试（同 Bug 再次出现）
- 新功能上线无监控（线上异常无感知）
- config.yaml 新增配置项但 `config.example.yaml` 未同步

## Grep 扫描命令

```bash
# 文档同步检查
grep -rn "@router\.\(get\|post\|put\|delete\)" src/xianyu_hunter/ --include="*.py" | wc -l
# 与 docs/api.md 包含的端点数量对比

# 测试覆盖
grep -rn "def test_\|async def test_" tests/ --include="*.py"

# config.example.yaml 同步
diff <(grep -E "^[a-z_]+:" config/config.example.yaml | sort) <(grep -E "^[a-z_]+:" config/config.yaml | sort)

# init_db vs 运行时索引
grep -rn "Index(" src/xianyu_hunter/infra/ --include="*.py"
grep -rn "_migrate_create_index\|CREATE INDEX" src/xianyu_hunter/ --include="*.py"
```

## 判断标准
- 接口变更文档未更新 → P0 阻塞
- 新功能无单元测试 → P0 阻塞
- Bug 修复无回归测试 → P0 阻塞
- 新功能上线无监控 → P1 严重
- config.yaml 新增配置项但 example 未同步 → P1 严重
- 新增端点未更新 auth_whitelist → P1 严重
- 修复后无验证日志 → P1 严重

## 适用/不适用场景
- **适用**：所有代码变更的闭环检查；新功能交付；Bug 修复；配置变更
- **不适用**：临时脚本/一次性工具；纯探索性代码
