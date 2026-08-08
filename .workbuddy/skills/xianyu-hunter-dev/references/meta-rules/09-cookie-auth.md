# Cookie 与认证安全

> Cookie 多用户隔离、注入验证、_m_h5_tk 刷新隔离、层级缓存同步、健康检查、测试数据过滤、路径安全构造、状态异常修复协议等。
>
> 涵盖规范: #72, #73, #74, #75, #76, #77, #78, #96, #97, #98, #99, #100, #101, #102
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #72 多用户 Cookie 隔离传播规范
注入cookie时必须按用户隔离，禁止混入其他用户的cookie

### #73 Cookie 注入必须验证浏览器状态
cookie注入后必须验证浏览器状态(页面加载成功/身份有效)，禁止注入后直接返回成功
- grep: `grep "inject_cookie\|add_cookies"` 无后续 `page.goto` 验证 → 违规

### #74 _m_h5_tk 刷新必须按用户隔离
_m_h5_tk刷新请求必须带对应用户的cookie，禁止全局统一刷新导致token错配

### #75 Cookie 层状态同步必须清除缓存
cookie层级状态变更时必须invalidate相关缓存，禁止缓存滞后导致状态不一致
- grep: `grep "invalidate\|invalidate_layer"` 缺缓存清除 → 违规

### #76 实时搜索 Cookie 健康检查必须传递 user_id
实时搜索的健康检查必须传递 user_id 参数，确保检查正确用户的cookie状态

### #77 Cookie 测试数据过滤必须在注入前执行
测试环境的cookie必须在注入前过滤掉测试数据，禁止测试cookie混入生产环境

### #78 Cookie 文件路径必须使用 Path 多参数构造
cookie文件路径必须用 `Path(base_dir) / user_id / "cookies.json"` 多参数构造，禁止字符串拼接

### #96 多写入路径状态一致性检查
多个写入路径写同一状态时必须保持一致性，禁止路径A写的状态被路径B忽略

### #97 UI 偏好持久化检查
UI偏好(主题/视图模式)变更后必须持久化，刷新后恢复。禁止刷新后重置为默认

### #98 storage 错误处理检查
localStorage/sessionStorage读写必须有try/catch错误处理，禁止假设永远成功

### #99 Cookie 状态异常与多写路径状态缺失预防
cookie异常和写入路径缺失必须同时预防。写端必须有marker+同步端必须扫描marker

### #100 页面刷新后 Cookie 有效但系统认为无效的修复协议
刷新后检查cookie实际有效性，禁止仅依赖内存缓存状态判断。grep `grep "sync_state_from_"` 缺调用 → 违规

### #101 Cookie 状态异常三合一修复
cookie状态异常+持久化+CDP模式三重问题联合修复协议

### #102 多写路径+UI偏好+storage错误三合一
多写路径状态检查+UI偏好持久化+storage错误处理联合检查
