# 核心原则

> 编码规范的基础性通用原则（配置驱动、适用场景、历史教训归档等），所有其他规范服从这些元规则。
>
> 涵盖规范: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #1 配置驱动原则
所有参数必须在 `config.yaml` 管理，禁止硬编码。适用范围：数值/字符串枚举/列表映射表/命名规则。例外：语言框架常量、协议固定值、安全必需固定值。

### #2 适用/不适用场景说明
每条规范必须明确适用与不适用场景。新增规范时必须自问"在什么场景下不适用？"

### #3 历史教训归档
教训统一归档到 `version-history.md` 和 `cookie-state-recovery-patterns.md`。

### #4 修复模式代码归档
完整代码示例归档到 `coding-rules/<topic>.md`，step 内只保留核心规则+判断信号。

### #5 判断信号优先 grep
判断信号必须可用 `grep` 验证，禁止"语义判断"等模糊描述。

### #6 复用优先级
项目内 helper > 标准库 > 第三方库 > 新实现。禁止跨文件重复关键字/正则/常量。

### #7 状态分类识别
五类持久化策略：用户偏好(usePersistentState) | 业务数据(API+DB) | 会话(Zustand) | 临时(useState) | 敏感(httpOnly cookie)

### #8 错误粒度区分
状态码精细化：401 未登录 | 403 权限不足 | 440 Cookie过期 | 441 Token过期 | 429 反爬 | 502 浏览器异常 | 503 服务未启动 | 504 网关超时

### #9 日志级别规范
error(需人工介入) | warning(可恢复异常) | info(关键路径) | debug(调试) | exception(关键路径保留traceback)

### #10 异步操作规范
await 调用必须有超时保护(asyncio.wait_for) + CancelledError 传播 + Task引用保留

### #11 安全调用检查
空值判断/异常处理/敏感脱敏/权限校验/SQL注入防护/路径遍历/token比较(hmac.compare_digest)/外部链接(noopener)

### #12 状态机设计规范
枚举穷举/转换白名单/终态不可复活/中间态清理/前后端枚举统一

### #13 测试隔离规范
tmp_path隔离/测试数据可识别/patch验证/sys.modules遍历/importlib.import_module

### #14 Python 现代化规范
asyncio.create_task | get_running_loop | dataclass显式字段 | 模块级import | X|None替代Optional

### #15 前端三态反馈规范
loading→success→error 三态，message.loading hide函数，禁止.catch(()=>{})静默吞错

### #16 配置全链路生效验证
config.yaml→Config类→TaskConfig→Worker→最终消费点，全链路grep验证

### #17 修改-验证-部署闭环
Edit后grep验证 → 修改文案后全局grep → Python修改后重启 → 验证端口+数据

### #18 跨前后端协同修复
前端调用→后端端点→数据源全链路，禁止只改一边，同步清理死代码

### #19 死代码检测与清理
git log -S + grep确认无调用方，大版本时主动检测

### #20 失败诊断dump机制
自动dump page.content()到logs/，try/except包裹不阻塞主流程，禁止dump敏感数据
