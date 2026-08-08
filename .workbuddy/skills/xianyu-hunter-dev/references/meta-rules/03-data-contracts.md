# 数据契约与时序

> 前后端数据契约、datetime 时区策略、字段单一可信源、error_code 分支、业务关键字管理、跨层数据同步、状态机返回值等。
>
> 涵盖规范: #25, #26, #27, #28, #29, #30, #32, #33, #34, #35, #36, #37, #66, #71, #88, #90, #91, #105, #108, #109, #110
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #25 批量处理四要素
断路器+进度持久化+续传+日志对称。熔断分支必须调用 save_progress()，禁止break后无持久化
- grep: `grep "consecutive failure" <file>` 无 `save_progress()` → 违规

### #26 关键路径异常保留完整traceback
_on_startup/run_migrations/_init_* 外层except必须用 logger.exception()，禁止 warning(f"...{e}")
- grep: `grep "except Exception" <file>` 关键路径缺 `logger.exception()` → 违规

### #27 datetime 统一时区策略
存储UTC，算术前unify tzinfo，序列化ISO 8601。禁止datetime.now()无tzinfo
- grep: `grep "datetime.now()" <file>` 无 `tzinfo` → 违规

### #28 跨进程/跨组件状态同步六步法
写端→同步端→读端→启动检查→异常保留marker→配置驱动。写端和同步端必须配对
- grep: `grep "write_marker"` 但无 `scan_marker` 同步器 → 违规

### #29 前端错误按 error_code 分支
禁止substring判断。后端{error_code, user_message, detail}，前端switch(error_code)匹配
- grep: `grep "if.*\.message\.(includes|indexOf)" frontend/` → 违规

### #30 业务关键字常量集中管理
前后端关键字集合必须等价，配置到config.yaml和constants/businessKeywords.ts
- grep: `grep "['\"](已售|已删除|宝贝不存在)['\"]" src/` → 硬编码违规

### #32 多阶段降级链日志合并
降级链中间步骤DEBUG化，最终合并为1条结构化WARNING(含stages/final_reason)
- grep: 同函数≥3个logger.warning属同一降级链 → 违规

### #33 注册式资源三件套契约
L1菜单注册→L2路由注册→L3页面文件→L4 API wrapper→L5后端endpoint，五层缺一即CRITICAL

### #34 修复前全链路根因扫描协议
列≥3根因→排根因→修复→反查同类bug→防回归(unit test+文档)。禁止单点修复

### #35 前后端字段契约单一可信源
后端Pydantic+DB Row=权威源，前端 types.ts 必须标注派生来源，snake_case 透传禁止驼峰
- grep: 前端types.ts字段驼峰但后端Pydantic snake_case → 命名漂移

### #36 规范沉淀门槛
新立规范需≥3个相似bug。安全漏洞/数据丢失/付费受损可豁免。experimental标签预沉淀

### #37 规范退化机制
季度审查利用率<3则标记待合并/废弃。安全类规范永不退化

### #66 HTTP 状态码语义分层
401专属认证中间件，业务异常用440。前端拦截器必须基于detail精确匹配
- grep: `grep "CollectionError(401" src/` → 业务代码抛出认证层状态码

### #71 配置变更前后端契约
配置项变更必须前后端同步：接口路径→方法→参数→响应结构→字段类型→边界值

### #88 跨层数据契约同步流程
字段变更必须5点更新：DB Row→Pydantic→_row_to_dict白名单→types.ts→消费点

### #90 回退构造保留关联键
回退数据结构必须保留原始关联键(如item_id)，确保下游能重新关联

### #91 时间窗口查询全量回退
时间窗口查询失败时必须回退到全量查询，禁止返回空结果

### #105 数据写入策略字段级决策
数据写入策略必须在字段级决策(覆盖/追加/跳过/合并)，禁止全局统一策略

### #108 跨层闭环验证
git diff显示半边修改时必须调用全链路grep验证另一半，禁止只改一边

### #109 状态机返回值语义校验
状态机转换方法必须返回新状态对象，禁止返回True/False丢失失败原因

### #110 类型注解契约对齐 (experimental)
后端类型注解、Pydantic ResponseModel、前端 types.ts 三方必须对齐。权威源优先级：ResponseModel > types.ts > 函数注解
