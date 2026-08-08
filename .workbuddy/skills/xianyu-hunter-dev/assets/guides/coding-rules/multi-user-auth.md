# 多用户与认证安全 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「多用户资源隔离 + 认证中间件 + 会话 token 安全」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 134：多用户资源隔离规范【强制】🆕v4.30

134. **多用户资源隔离规范【强制】🆕v4.30**
    - 单用户系统升级到多用户时，所有按全局单例管理的资源（文件/缓存/数据库表）必须按 `user_id` 维度隔离
    - **判断信号**：存在全局单例路径（如 `cookies.json`）、全局缓存变量（如 `_cache: dict`）、无 `user_id` 参数的公共方法
    - **修复模式**：
      1. 文件路径加 user_id 维度：`cookies.json` → `cookies_{uid}.json`，用 `_cookie_json_path(user_id)` 函数生成
      2. 缓存从单值改为分桶：`_cache: dict[str, tuple[dict, float]]`（按 user_id → (data, timestamp)）
      3. 所有公共方法加 `user_id: str = "default"` 参数（向后兼容）
      4. user_id 拼接到文件路径必须白名单校验：`_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")`
      5. SQLite 兜底逻辑需判断 `user_id == "default"`（避免多用户通过全局表误判）
    - **适用场景**：单用户→多用户升级、多租户场景、多账号管理
    - **不适用场景**：纯内部工具（无用户概念）、单租户 SaaS、用户数固定为 1 的脚本
    - **配置参数**：`config.yaml` 的 `multi_user_resource_isolation` 节点管理（user_id_pattern / default_user_id / isolation_dimensions / exclude_paths）

---

### step 135：认证中间件多路校验规范【强制】🆕v4.30

135. **认证中间件多路校验规范【强制】🆕v4.30**
    - 同时存在多种认证方式（管理令牌 + 用户会话）时，中间件必须按优先级链式校验，校验通过后注入 `request.state.user_id`
    - **判断信号**：中间件只有单一 token 校验、无 user_id 注入、异常静默降级（debug 日志）
    - **修复模式**：
      1. 公开路径白名单放行（PUBLIC_PREFIXES）
      2. 提取 token：Authorization header > xh_token cookie
      3. 路径 1（管理令牌直通）：`hmac.compare_digest(req_token, web_token)` → `request.state.user_id = "default"`
      4. 路径 2（用户会话查库）：`get_user_manager().verify_session(req_token)` → `request.state.user_id = user_id`
      5. 路径 3（校验失败）：`/api/` 返回 `401 {"detail": "Unauthorized"}`，非 `/api/` 放行
      6. 异常降级必须 `logger.warning`（禁止 `logger.debug` 静默吞掉系统级故障）
      7. 日志禁止泄露 token 明文（只记录 bool 匹配结果）
    - **适用场景**：管理后台+用户前台混合认证、向后兼容旧 token、多角色系统
    - **不适用场景**：单一认证方式、纯 API 网关（无认证层）、内部微服务间调用
    - **配置参数**：`config.yaml` 的 `auth_multi_path_validation` 节点管理（web_token_compare_func / session_verify_method / exception_log_level / public_prefixes_config）

---

### step 136：会话 token 安全管理规范【强制】🆕v4.30

136. **会话 token 安全管理规范【强制】🆕v4.30**
    - 用户会话 token 的生成、存储、校验、撤销必须遵循安全最佳实践，防止时序攻击、会话固定、撤销窗口
    - **判断信号**：token 明文存库、用 `==` 比较 token、无滑动续期、撤销不清缓存
    - **修复模式**：
      1. 生成：`secrets.token_urlsafe(48)` 生成 64 字符随机串
      2. 存储：库内只存 `sha256(token)`，不存明文（`token_hash = hashlib.sha256(token.encode()).hexdigest()`）
      3. 校验：`hmac.compare_digest(token_hash, stored_hash)` 防时序攻击
      4. 滑动续期：距过期不足 N 天时延长到 TTL 天（`if (expires - now) < timedelta(days=N): new_expires = now + timedelta(days=TTL)`）
      5. 撤销：`UPDATE user_sessions SET is_active=0` + 清除缓存中该用户所有条目
      6. 缓存与撤销互斥：`verify_session` 和 `revoke_session` 必须在同一 `RLock` 内完成，消除"查库后缓存被撤销"窗口
      7. 会话固定防护：签发新 session 前标记旧 session 为 `is_active=0`
    - **适用场景**：所有涉及用户会话的系统、需防时序攻击的场景、需滑动续期的场景
    - **不适用场景**：无状态 JWT（签名校验无需查库）、一次性 token（无需续期）、内部服务间通信
    - **配置参数**：`config.yaml` 的 `session_token_security` 节点管理（token_generate_func / token_hash_algo / compare_func / ttl_days / renewal_threshold_days / revoke_clear_cache）

---

### step 137：快照与实时数据覆盖决策规范【强制】🆕v4.30

137. **快照与实时数据覆盖决策规范【强制】🆕v4.30**
    - 历史快照数据与实时采集数据合并时，不能一律"只填缺失"，必须按字段类型分档覆盖
    - **判断信号**：`_enrich_*` 函数中所有字段都用 `if not existing: existing = new`、数值字段历史值不被新值覆盖
    - **修复模式**：字段分四档覆盖策略
      1. **非空字段**（title/url/id/region/brand/seller_id/publish_time）：新值存在则覆写（`if new: existing = new`）
      2. **数值字段**（price/count/view_cnt/want_cnt）：新值 > 0 才覆写（`if new > 0: existing = new`）
      3. **状态字段**（is_sold/is_deleted）：始终覆写（`existing = new`）
      4. **标识字段**（seller_nick/nickname）：只填缺失（`if not existing: existing = new`）
    - 每档覆盖策略必须有单元测试覆盖
    - 覆盖策略必须有注释说明"为什么这个字段用这个档位"
    - **适用场景**：数据采集系统、缓存与源数据同步、历史快照与实时更新并存
    - **不适用场景**：纯实时系统（无快照）、纯审计系统（不可修改）、纯日志系统（只追加）
    - **配置参数**：`config.yaml` 的 `snapshot_realtime_overwrite` 节点管理（overwrite_strategy / non_empty_fields / positive_numeric_fields / state_fields / identity_fields）
