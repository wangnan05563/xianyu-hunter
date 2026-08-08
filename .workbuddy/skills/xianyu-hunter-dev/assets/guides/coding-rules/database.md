# Database 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「database」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 32：文件锁绕过模式（SQLite immutable）【强制】🆕v4.4

32. **文件锁绕过模式（SQLite immutable）【强制】🆕v4.4**
    - 并发访问被锁文件时，使用 SQLite URI `immutable=1` 参数打开只读数据库，绕过 Windows 文件锁机制
    - **判断信号**：Windows 文件锁报错（`database is locked` / `unable to open database`）+ 只读访问需求 + SQLite 数据库
    - **修复模式**：构建 URI `file:./Cookies?immutable=1` → 用 `sqlite3.connect(uri=True)` 打开 → 仅执行 SELECT 查询
    - **配置参数**：`immutable_flag` 默认 `true`，`lock_timeout_ms` 在 `config/database.yaml` 管理
    - **适用**：浏览器 cookie 数据库并发访问、Windows 文件锁定机制、需要只读访问的共享资源
    - **不适用**：需要写入的场景、Linux 文件锁（建议用 `flock`）、原子写场景
    - **历史教训**：浏览器运行时持有 `Cookies` 数据库写锁，传统 `sqlite3.connect()` 打开失败，改用 `immutable=1` 后可并发读取


---

### step 70：DB 迁移失败处理【强制】🆕v4.12

70. **DB 迁移失败处理【强制】🆕v4.12**
    - `_migrate_*` 函数失败必须明确处理策略：关键迁移（schema 变更）失败 `raise RuntimeError` 中断启动；非关键迁移（索引补建/数据回填）失败 `logger.warning` + 继续启动，**禁止** `except: pass` 静默吞掉
    - **判断信号**：`_migrate_*` 函数含 `try/except` 块 → except 块必须明确记录日志或抛出，禁止 `pass`
    - **修复模式**：
      ```python
      # ✅ 关键迁移：失败必须中断
      def _migrate_add_column(conn, table: str, column: str, sql_type: str) -> None:
          try:
              conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
          except Exception as e:
              if "duplicate column" in str(e).lower():
                  return  # 幂等，已存在则跳过
              raise RuntimeError(f"关键迁移失败 {table}.{column}: {e}") from e

      # ✅ 非关键迁移：失败 warning + 继续
      def _migrate_create_index(conn, name: str, table: str, columns: list[str]) -> None:
          try:
              conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({', '.join(columns)})")
          except Exception as e:
              logger.warning("非关键索引迁移失败 {}：{}（不影响启动）", name, e)
      ```
    - **配置参数**：`migration_failure_strategy.critical_migrations`（关键迁移函数名列表，失败 raise）、`migration_failure_strategy.non_critical_migrations`（非关键迁移函数名列表，失败 warn）、`migration_failure_strategy.default_strategy`（默认 `warn`，可选 `raise`）在 `config.yaml` 的 `migration_failure_strategy` 节点管理
    - **适用**：所有 `_migrate_*` 函数（_migrate_add_column / _migrate_create_index / _migrate_make_column_nullable / _migrate_backfill_data）
    - **不适用**：迁移幂等性检查（已通过"duplicate column"等错误识别处理）；测试代码中的迁移
    - **历史教训**：`_migrate_create_index` 失败被 `except: pass` 吞掉，生产数据库索引长期缺失导致 Dashboard 查询慢 10 倍，但日志无任何记录


---

### step 93：SQLite DDL 修改列约束必须用表重建 + 事务安全【强制】🆕v4.16

93. **SQLite DDL 修改列约束必须用表重建 + 事务安全【强制】🆕v4.16**
    - SQLite 不支持 `ALTER COLUMN`，任何修改列约束的操作（NOT NULL→nullable、类型变更）必须通过 `_migrate_make_column_nullable` 模式（事务 + 残留清理 + 数据复制 + 异常恢复），禁止分散 commit 或裸 ALTER
    - 关键约束：
      1. **事务包裹**：整个表重建过程用 `engine.begin()` 包裹，任一步骤失败自动回滚
      2. **残留清理**：迁移前 `DROP TABLE IF EXISTS {table}_old`，避免上次失败残留导致 RENAME 阻塞
      3. **连接传参**：`orm_table.create(conn, checkfirst=True)` 传入连接而非 `engine`，确保 DDL 纳入事务
      4. **数据复制**：用列名交集（`{c.name for c in orm_table.columns} & {c[1] for c in PRAGMA table_info}`）复制数据，防止列差异导致 INSERT 失败
      5. **异常恢复**：失败后检查 `{table}` 是否存在，不存在则从 `{table}_old` RENAME 恢复
    - **判断信号**：`_migrate_*` 函数含多个 `conn.commit()` → 拆分为单一事务；`ALTER TABLE ... MODIFY COLUMN` / `ALTER TABLE ... ALTER COLUMN` → SQLite 不支持，需改用表重建；DDL 操作未传 `conn` 给 `orm_table.create` → 必须改为传 `conn`
    - **修复模式**：
      ```python
      with engine.begin() as conn:
          conn.execute(sa_text(f"DROP TABLE IF EXISTS {table}_old"))
          conn.execute(sa_text(f"ALTER TABLE {table} RENAME TO {table}_old"))
          orm_table.create(conn, checkfirst=True)
          old_cols = {c[1] for c in conn.execute(sa_text(f"PRAGMA table_info({table}_old)")).all()}
          common_cols = [c for c in orm_table.columns if c.name in old_cols]
          col_list = ", ".join(f'"{c.name}"' for c in common_cols)
          conn.execute(sa_text(f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM {table}_old"))
          conn.execute(sa_text(f"DROP TABLE {table}_old"))
      ```
    - **配置参数**：`migration_transaction.require_single_transaction`（默认 `true`）、`migration_transaction.cleanup_residual_table`（默认 `true`，自动 DROP `{table}_old`）、`migration_transaction.recover_from_old`（默认 `true`，失败后从 `{table}_old` 恢复）、`migration_transaction.exception_log_level`（默认 `error`）在 `config.yaml` 的 `migration_transaction` 节点管理
    - **适用**：SQLite 修改列约束、表重建、任何不可逆 DDL
    - **不适用**：PostgreSQL/MySQL（有原生 DDL 事务）、新增列（直接 `ADD COLUMN`）、纯查询/插入操作
    - **历史教训**：旧版 `_migrate_make_column_nullable` 用 3 个独立 commit 拆分布骤 1/2/3/4，步骤 2 或 3 失败时旧表已 RENAME 但新表未创建完成，tasks 表变空且 tasks_old 残留，下次启动时 RENAME 因目标已存在永久阻塞；新版改用 `engine.begin()` 单事务 + 残留清理 + 异常恢复，彻底解决该问题


---

### step 109：业务自增计数器 DB MAX 初始化规范【强制】🆕v4.20

**背景**：批量采集任务的 task_id 是业务字段（progress 表/历史表/日志均引用），调度器内存中维护自增计数器。如果进程重启，内存计数器从 0 开始，会与历史记录的 task_id 冲突。

**问题**：业务自增 ID 依赖内存初始化，进程重启后重置，导致新记录的 ID 与历史记录冲突。

**规范**：

1. 业务自增 ID（task_id/batch_id/run_id 等）不能依赖内存初始化（进程重启会重置）
2. 调度器 `__init__` 时必须从 DB `SELECT MAX(id)` 初始化计数器
3. 查询失败时回退到 0 + `logger.warning`，不阻断启动
4. `trigger_now()` 调用时 `+= 1` 后立即返回给前端，不等待 DB 写入
5. 为什么不用 DB 自增主键：业务自增 ID 需在调度器内存中维护以便 trigger_now 立即返回给前端，DB 自增主键要等 INSERT 后才知道值

**配置驱动**：参数在 `config.yaml` 的 `counter_db_max_init` 节点管理，包含 `counter_fields`（需要 DB MAX 初始化的字段列表）、`init_query_template`（初始化查询模板）、`fallback_value`（回退值默认 0）、`warning_on_failure`（失败时是否记录 warning）。

**适用场景**：业务自增 ID（task_id/batch_id/run_id）跨进程重启不能重置的场景。

**不适用场景**：DB 自增主键（autoincrement）；UUID/GUID；临时计数器（无需跨进程持久化）。


---

### step 116：数据库迁移块独立容错与关键路径异常可见性规范【强制】🆕v4.25

**背景**：用户报告 `sqlite3.OperationalError: no such column: notifications.read_at`，发生在 `add_notification` 的 UPSERT INSERT 语句中。ORM 模型 `NotificationRow` 已声明 `read_at` 字段，C-04 迁移逻辑（`ALTER TABLE notifications ADD COLUMN read_at`）也存在，但该列在实际数据库中缺失。

**根因**：`run_migrations()` 函数内多个迁移块（C-01~C-05）顺序执行，C-01 步骤的 `auto_migrate_task_links()` 抛异常后，C-02/C-03/C-04/C-05 全部被跳过；而外层 `_on_startup` 的 `try/except Exception as e: logger.warning(f"启动迁移钩子失败（忽略）: {e}")` 又吞掉了异常，仅留一条 warning 日志。最终数据库 schema 与 ORM 不一致，运行时 INSERT 才报 "no such column"。

**问题本质**：两个设计缺陷叠加——① 迁移块间无独立容错（前置失败阻断后续）；② 外层 try/except 吞掉关键路径异常（丢失完整堆栈，难以定位真正失败点）。

**规范**：

1. **迁移块独立容错【强制】**：同一迁移函数内的多个独立迁移块（如 C-01 表重建 / C-02 ADD COLUMN / C-03 ADD COLUMN / C-04 ADD COLUMN / C-05 CREATE INDEX）必须各自独立 `try/except`，每个块失败时记 `logger.warning` + 块标识（如 `"C-04 notifications.read_at 迁移失败（忽略）: {e}"`），不阻断后续块：
   ```python
   # ✅ 正确：每个迁移块独立 try/except
   try:
       # C-04 迁移
       if insp.has_table("notifications"):
           notif_cols = {c["name"] for c in insp.get_columns("notifications")}
           if "read_at" not in notif_cols:
               with engine.begin() as conn:
                   conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN read_at DATETIME DEFAULT NULL")
   except Exception as e:
       logger.warning(f"C-04 notifications.read_at 迁移失败（忽略）: {e}")

   # C-05 迁移不受 C-04 失败影响
   try:
       # ...
   except Exception as e:
       logger.warning(f"C-05 ... 迁移失败（忽略）: {e}")
   ```

2. **强依赖时允许合并【强制】**：仅当迁移块间有强依赖（B 依赖 A 成功，如表重建后才能回填数据）时才允许合并到一个 `try` 块，并在 docstring 中注明依赖关系。

3. **外层禁止吞掉关键路径异常【强制】**：启动钩子（`_on_startup`）、迁移函数（`run_migrations`）、初始化函数（`init_db`/`init_container`）等关键路径的外层 `except` 必须用 `logger.exception()` 输出完整 traceback，禁止用 `logger.warning(f"...{e}")` 丢失堆栈：
   ```python
   # ❌ 错误：外层 warning 丢失堆栈，且内部无独立容错
   try:
       container = get_container()
       run_migrations(container)  # 内部任一迁移失败 → 全部跳过
   except Exception as e:
       logger.warning(f"启动迁移钩子失败（忽略）: {e}")  # 只有一行 message

   # ✅ 正确：外层 exception 保留堆栈（内部已有独立容错时，外层仅兜底）
   try:
       container = get_container()
       run_migrations(container)  # 内部各块独立 try/except
   except Exception:
       logger.exception("启动迁移钩子失败（不阻断主服务）")  # 完整 traceback
   ```

4. **数据库 schema 三方对比诊断法【强制】**：遇到 `no such column` / `no such table` / `column not found` 类错误时，必须执行三方对比诊断：
   - **① ORM 模型声明**（`db_models.py`）：确认字段是否在模型中声明
   - **② 迁移逻辑**（`run_migrations`）：确认是否有对应的 ALTER TABLE / CREATE TABLE 迁移
   - **③ 实际数据库 schema**（`PRAGMA table_info(<table>)`）：确认数据库实际列
   - 三方一致 → 报错为历史日志或连接错库；ORM有/迁移无 → 补迁移；迁移有/实际无 → 迁移未执行（检查启动日志中被吞掉的 warning）

**配置驱动**：迁移函数名列表、迁移块标识前缀、关键路径函数名、禁止的 except 模式等参数在 `xianyu-backend-code-review` 的 `config.yaml` 的 `migration_block_isolation` / `critical_path_no_swallow` 节点管理（详见 `xianyu-backend-code-review` v4.25.0 的 `B-REVIEW-MIGRATION-BLOCK-ISOLATION` / `B-REVIEW-CRITICAL-PATH-NO-SWALLOW`），不硬编码在技能中。

**适用场景**：
- 数据库增量迁移（ALTER TABLE / CREATE INDEX / 数据回填）多个独立步骤
- 启动初始化序列（日志 / DB / 调度器 / 浏览器等多个独立组件初始化）
- 配置加载多个独立配置项
- 任何 `no such column` / `no such table` 类错误的诊断

**不适用场景**：
- 有强依赖的迁移序列（表重建后才能回填数据）—— 应合并 try 并在失败时整体回滚
- 单一原子事务内的多个 SQL（应用事务的 ACID 保证，不应拆分 try）
- 非关键路径的 fire-and-forget 操作（如 dump 诊断文件，失败可静默）
- SQL 语法错误 / 权限错误 / 连接错误（非 schema 问题，三方对比不适用）

**历史教训**：`startup.py` 的 `run_migrations()` 函数内 C-01~C-05 五个迁移块顺序执行无独立 try/except，外层 `_on_startup` 的 `except Exception as e: logger.warning(f"启动迁移钩子失败（忽略）: {e}")` 吞掉异常。C-01 步骤的 `auto_migrate_task_links()` 因 `task_links` 表结构问题抛异常，导致 C-04（`notifications.read_at` 列添加）被跳过。数据库 schema 缺少 `read_at` 列，前端 `_persistErrorAsNotif` 调用 `POST /api/notifications` 时 INSERT 失败。修复方式：将 C-01~C-05 改为各自独立 try/except，前置失败不阻断后续迁移。

**判断信号（review 触发条件）**：
- `grep -n "except Exception" src/xianyu_hunter/web/startup.py` 命中关键路径函数的外层统一 try/except
- `grep -n "logger.warning.*忽略" src/xianyu_hunter/web/startup.py` 命中吞掉异常的 warning
- 迁移函数体内多个 ALTER TABLE / CREATE INDEX 在同一 try 块内或无 try 包裹但外层有统一 try/except
- 运行时报 `no such column` / `no such table` 但 ORM 模型已声明对应字段


---

### step 138：DATETIME-TZ-01 时区一致性三步检查法【强制】🆕v4.29

**背景**：`repo_chatbot.py:478` 中 offset-naive 与 offset-aware datetime 混合做减法运算，触发 `TypeError: can't subtract offset-naive and offset-aware datetimes`。

**问题**：SQLAlchemy ORM 查询与 raw SQL 混用时，datetime 列的 tzinfo 一致性无统一管理；构造函数 `datetime.now()` 返回 naive，`datetime.now(timezone.utc)` 返回 aware，两者做比较/减法即抛异常。

**规范**：

1. **来源识别【强制】**：使用 datetime 前必须执行两步识别
   - 查 DB 模型定义确认列是否 timezone-aware（如 `DateTime(timezone=True)`）
   - 查 datetime 构造函数确认是否传入 `tzinfo` 参数

2. **对齐策略【强制】**：比较/减法运算前必须统一对齐为同一类型，推荐统一为 naive：
   ```python
   # ✅ 正确：aware → naive 对齐后再运算
   if value.tzinfo is not None:
       value = value.replace(tzinfo=None)
   delta = datetime.now() - value

   # ❌ 错误：aware 与 naive 直接相减
   # delta = datetime.now() - value  # 若 value 是 aware 则 TypeError
   ```

3. **能力检测【强制】**：对动态类型值（如 raw SQL 返回值）必须先检测再调用方法：
   ```python
   if isinstance(value, datetime):
       # 检测 tzinfo 后再决定是否调用 isoformat / 做减法
   ```

**配置驱动**：`coding_standards.datetime.default_timezone`（`naive` | `aware`，默认 `naive`）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- SQLAlchemy ORM 查询 + raw SQL 混用项目
- SQLite/MySQL 等不带时区的数据库
- 任何涉及 datetime 减法/比较的代码

**不适用场景**：
- 全链路统一 timezone-aware 且 DB 列均为 `DateTime(timezone=True)` 的项目
- 纯展示用 datetime 格式化（无运算）
- 时区转换业务（需保留 tzinfo）

**历史教训**：`repo_chatbot.py:478` 中 `datetime.now() - row.created_at` 因 `row.created_at` 来自 timezone-aware 列而抛 TypeError，导致聊天会话查询失败。

**判断信号（review 触发条件）**：
- `grep "datetime.now()" <file>` 与 `grep "timezone" <file>` 共存
- `TypeError: can't subtract offset-naive and offset-aware datetimes` 运行时错误


---

### step 139：DATETIME-TZ-02 原生 SQL 返回值防御【强制】🆕v4.29

**背景**：`api_db_admin.py:922` 中 SQLite 原生 SQL `text()` 查询返回 DateTime 列的字符串值，代码直接调用 `.isoformat()` 导致 `AttributeError: 'str' object has no attribute 'isoformat'`。

**问题**：SQLAlchemy `text()` 执行原生 SQL 时，DateTime 列可能返回字符串而非 datetime 对象（取决于驱动与连接配置），代码假设类型为 datetime 直接调用方法即抛异常。

**规范**：

1. **封装 datetime 强制转换工具函数【强制】**：使用 SQLAlchemy `text()` 执行原生 SQL 时，必须封装 `_coerce_datetime(value)` 工具函数处理返回值：
   ```python
   from datetime import datetime

   def _coerce_datetime(value) -> datetime | None:
       """将原生 SQL 返回值强制转换为 datetime，失败返回 None。

       为什么需要：SQLAlchemy text() 返回的 DateTime 列可能是字符串而非 datetime，
       直接调用 .isoformat() 会抛 AttributeError。
       """
       if value is None:
           return None
       if isinstance(value, datetime):
           return value
       if isinstance(value, str):
           try:
               return datetime.fromisoformat(value)
           except ValueError:
               return None
       return None
   ```

2. **所有原生 SQL 查询结果必须经过转换【强制】**：从原生 SQL 结果取 DateTime 列时必须调用 `_coerce_datetime()`，禁止直接使用原始值。

**配置驱动**：`coding_standards.datetime.raw_sql_coerce`（`true`/`false`，默认 `true`）在 `config.yaml` 管理。

**适用场景**：
- SQLAlchemy `text()` 原生 SQL 查询
- 动态类型值处理（DB 返回值类型不确定）

**不适用场景**：
- ORM 查询（自动转换为 Python 类型）
- 确定类型的查询（如纯字符串列）

**历史教训**：`api_db_admin.py:922` 调用 `row.created_at.isoformat()` 但 `row.created_at` 实际是字符串，导致 DB 管理端点 500 错误。

**判断信号（review 触发条件）**：
- `grep "text(" <file>` 后跟 `.isoformat()` 或 `.timestamp()` 调用
- `AttributeError: 'str' object has no attribute 'isoformat'` 运行时错误


---

### step 140：MIGRATE-01 迁移步骤独立性原则【强制】🆕v4.29

**背景**：迁移步骤 C-04 被 C-01 异常吞掉（外层统一 try/except），导致后续迁移步骤全部跳过，`notifications.read_at` 列缺失，运行时报 `no such column`。

**问题**：多个独立迁移步骤共用一个外层 try/except 时，前置步骤抛异常会跳过所有后续步骤，且外层 except 仅记录一行 warning，丢失完整堆栈，难以定位真正失败点。

**规范**：

1. **独立步骤独立容错【强制】**：多个独立迁移步骤必须各自 try/except，禁止外层统一捕获吞掉异常：
   ```python
   # ✅ 正确：每个迁移步骤独立 try/except
   try:
       _migrate_step_c01(conn)
   except Exception as e:
       logger.warning(f"C-01 迁移失败（忽略）: {e}")

   try:
       _migrate_step_c02(conn)  # C-01 失败不影响 C-02
   except Exception as e:
       logger.warning(f"C-02 迁移失败（忽略）: {e}")

   # ❌ 错误：外层统一 try/except 吞掉异常
   # try:
   #     _migrate_step_c01(conn)
   #     _migrate_step_c02(conn)  # C-01 失败则 C-02 被跳过
   # except Exception as e:
   #     logger.warning(f"迁移失败: {e}")  # 丢失步骤标识
   ```

2. **强依赖场景允许合并【强制】**：强依赖场景（如表重建 + 数据回填）允许合并到一个 try 块，但注释中必须说明合并原因。

3. **迁移失败必须用 logger.exception()【强制】**：迁移失败必须用 `logger.exception()` 输出完整 traceback，禁止用 `logger.warning(f"...{e}")` 丢失堆栈。

**配置驱动**：`coding_standards.migration.independent_steps`（独立迁移步骤函数名列表）在 `config.yaml` 管理。

**适用场景**：
- 数据库迁移脚本
- 启动时迁移函数（`run_migrations` / `_on_startup`）

**不适用场景**：
- 单步迁移（无多步骤依赖）
- 强依赖迁移步骤（如表重建 + 数据回填，允许合并）

**历史教训**：`startup.py` 的 `run_migrations()` 中 C-01~C-05 五个迁移步骤共用外层 try/except，C-01 抛异常后 C-04（`notifications.read_at`）被跳过，数据库 schema 缺列，运行时 INSERT 失败。

**判断信号（review 触发条件）**：
- `grep "except Exception" <migrate_file>` 命中外层统一 try/except
- `grep "logger.warning.*忽略" <migrate_file>` 命中吞掉异常的 warning


---

### step 141：NULL-01 NOT NULL 字段防御原则【强制】🆕v4.29

**背景**：`interval_seconds` / `use_cron` 字段在 DB schema 中为 NOT NULL，但 API 层未做 null 防御，前端传 null 时触发 `NOT NULL constraint failure`。

**问题**：DB NOT NULL 字段在 API 层未做 null 防御，前端 PATCH/PUT 接口传 null 时直接写入 DB 触发 IntegrityError，错误信息暴露给用户且难以定位。

**规范**：

1. **API 层 null 防御【强制】**：DB NOT NULL 字段在 API 层必须做 null 防御，防御方式可选：
   - **Pydantic model_validator**：在模型层用 `@model_validator` 检查 None，返回 422
   - **API 层 if 判断**：在路由处理函数中 `if value is None: raise HTTPException(422, ...)`

   ```python
   # ✅ 正确：API 层 null 防御
   if updates.get("use_cron") is None and "use_cron" in updates:
       raise HTTPException(422, "use_cron 字段不允许为 null")

   # ❌ 错误：直接写入 DB 触发 IntegrityError
   # updates['use_cron'] = None → NOT NULL constraint failure
   ```

2. **NOT NULL 字段清单集中管理【强制】**：所有 NOT NULL 字段必须提取为模块级常量，便于审查与同步。

**配置驱动**：`coding_standards.null_defense.check_fields`（NOT NULL 字段清单）在 `config.yaml` 管理。

**适用场景**：
- DB NOT NULL 字段的 API 写入（POST/PATCH/PUT）
- 前端可编辑的 NOT NULL 字段

**不适用场景**：
- 允许 NULL 的字段（无需防御）
- DB 自增主键（由 DB 管理，不接受外部输入）

**历史教训**：`api_tasks.py` 的 `update_task` 未对 `use_cron` / `interval_seconds` 做 null 防御，前端清除覆盖时传 null 触发 `NOT NULL constraint failure`，错误信息暴露 SQL 细节。

**判断信号（review 触发条件）**：
- `grep "NOT NULL" <db_models_file>` 找出所有 NOT NULL 字段
- API 层 PATCH/PUT 接口未对 NOT NULL 字段做 null 检查


---

### step 142：QUERY-01 数据查询条件精确性原则【强制】🆕v4.29

**背景**：评估明细查询用 `event.type.startswith('eval.')` 过于宽泛，引入 227+ 条 `eval.passed` 通知事件（`payload=None`），导致评估明细列表混入大量空记录。应为 `== 'eval.scored'` 精确匹配。

**问题**：使用 `startswith` / `endswith` / `in` 做前缀/后缀/子串过滤时，同一前缀下可能有多个事件类型，前缀过滤会误包含不相关事件，导致统计偏差或列表混入无效记录。

**规范**：

1. **匹配单个值用 ==【强制】**：业务查询过滤单个值时必须用 `==` 精确匹配，禁止用 `startswith` / `endswith` / `in` 做前缀/后缀/子串过滤：
   ```python
   # ✅ 正确：精确匹配目标事件类型
   events = [e for e in all_events if e.type == 'eval.scored']

   # ❌ 错误：startswith 前缀过滤，误包含 eval.passed/eval.failed
   # events = [e for e in all_events if e.type.startswith('eval.')]
   ```

2. **使用 startswith 时必须列出所有匹配变体【强制】**：若必须用 `startswith` 做前缀分组（如统计场景），必须列出所有匹配的前缀变体，确认无噪声。

3. **通知事件与业务事件分离【强制】**：通知/审计类事件（如 `eval.passed` 仅用于 KPI）必须与业务查询事件（如 `eval.scored` 用于评估明细）使用不同的 type 前缀。

**配置驱动**：`coding_standards.query_filter.precision_check`（`true`/`false`，默认 `true`）在 `config.yaml` 管理。

**适用场景**：
- 数据查询过滤（按类型/状态/分类查询）
- 事件类型过滤
- 统计聚合（需前缀分组时必须注释包含的子类型）

**不适用场景**：
- 模糊搜索（如商品标题搜索）
- 正则匹配场景
- 全量导出（无需过滤）

**历史教训**：`api_evaluations.py` 用 `startswith('eval.')` 过滤评估明细，误包含 `eval.passed` 通知事件（227+ 条 `payload=None`），用户看到「213 条仅基于价格的评估记录」和大量空行。修复后改为 `== 'eval.scored'`，评估明细从 280 条减到 47 条有效记录。

**判断信号（review 触发条件）**：
- `grep "startswith" <file>` 出现在查询过滤逻辑中
- `grep "endswith" <file>` 出现在查询过滤逻辑中
- 业务列表混入 `payload=None` 的空记录


---

### step 143：ENUM-01 状态值枚举一致性原则【强制】🆕v4.29

**背景**：抢单成功率统计中，业务逻辑使用的状态值 `paid` / `confirmed` 与数据库存储的枚举值 `succeeded` 不匹配，导致统计结果为 0%。

**问题**：业务逻辑中使用的状态值字符串与数据库存储的枚举值不一致，导致查询条件不匹配、统计结果错误、UI 显示与实际状态脱节。

**规范**：

1. **状态值与 DB 枚举完全一致【强制】**：业务逻辑中使用的状态值必须与数据库存储的枚举值完全一致，禁止使用同义词/变体：
   ```python
   # ✅ 正确：与 DB 枚举值一致
   if order.status == 'succeeded':
       success_count += 1

   # ❌ 错误：使用同义词，与 DB 枚举不匹配
   # if order.status in ('paid', 'confirmed'):  # DB 实际存 'succeeded'
   #     success_count += 1
   ```

2. **状态值变更时同步更新所有引用【强制】**：状态值变更时，必须同步更新所有引用处（查询条件、统计逻辑、UI 显示），通过 grep 验证无遗漏。

3. **集中定义枚举常量【强制】**：状态值必须集中定义为模块级常量或 Enum 类，禁止分散硬编码字符串：
   ```python
   class OrderStatus(str, Enum):
       SUCCEEDED = 'succeeded'
       FAILED = 'failed'
       PENDING = 'pending'
   ```

**配置驱动**：`coding_standards.enum_consistency.status_fields`（状态字段清单）在 `config.yaml` 管理。

**适用场景**：
- 状态机/枚举字段（订单状态/任务状态/评估状态）
- 查询条件（按状态过滤）
- 统计逻辑（按状态计数/聚合）
- UI 显示（状态标签/颜色映射）

**不适用场景**：
- 自由文本字段（如备注/描述）
- 用户输入的标签
- 数值型状态（如 score）

**历史教训**：抢单成功率统计用 `status in ('paid', 'confirmed')` 但 DB 实际存储 `succeeded`，导致统计结果为 0%。修复后改为 `status == 'succeeded'`，统计正确显示 95% 成功率。

**判断信号（review 触发条件）**：
- `grep "status ==\|status in" <file>` 出现硬编码状态字符串
- 同一状态在多个文件用不同字符串表示
- 统计结果为 0% 但 DB 有数据


---

### step 199：RESOURCE-POOL-BENCHMARK 资源池配置性能基准与决策【强制】🆕v4.38

**背景**：本轮对话修复的 8 类问题之一——SQLAlchemy `NullPool` 在高并发场景下因每次请求创建新连接导致性能下降 3 倍，但配置选择缺乏性能基准数据支持，docstring 未记录选择理由。

**问题**：数据库/HTTP/浏览器资源池配置（`poolclass`、`pool_size`、`max_overflow`）的选择往往凭经验或默认值，缺乏性能基准数据对比。当业务规模变化（如从单用户 10 QPS 到多用户 100 QPS）时，原配置可能不再适用，但因无基准数据无法判断是否需要调整。

**规范**：

1. **资源池配置必须有 docstring 记录选择理由【强制】**：所有 `poolclass=` / `pool_size=` / `max_overflow=` 配置必须有 docstring 说明：
   - 选择该配置的理由（如"SQLite 单文件场景用 NullPool 避免连接复用冲突"）
   - 性能基准数据（如"基准测试：NullPool 50 QPS vs QueuePool 150 QPS，但 QueuePool 在 SQLite WAL 模式下有锁冲突"）
   - 适用规模与不适用规模（如"适用于 ≤100 QPS 单用户场景，多用户高并发需切换 QueuePool"）

2. **性能基准数据必须可复现【强制】**：docstring 中引用的性能基准必须有可复现的测试脚本（位于 `tests/benchmarks/`），脚本包含：
   - 测试环境（Python 版本、DB 版本、并发数）
   - 测试场景（QPS 从 10 → 100 → 500）
   - 结果数据（平均延迟、P99 延迟、错误率）

3. **慢查询日志监控【强制】**：资源池配置变更后必须开启慢查询日志（阈值默认 50ms），持续监控 7 天，若系统开销 > 50ms 则触发配置 review：
   ```python
   # ✅ 正确：配置变更后开启慢查询日志
   engine = create_engine(
       url,
       poolclass=NullPool,
       echo=False,
       connect_args={"timeout": 30},
   )
   # docstring: NullPool 选择理由 - SQLite 单文件场景避免连接复用冲突
   # 基准测试: tests/benchmarks/test_db_pool.py (NullPool 50 QPS vs QueuePool 150 QPS)
   # 适用规模: ≤100 QPS 单用户；多用户高并发需切换 QueuePool + PostgreSQL
   ```

4. **配置参数从 config.yaml 读取【强制】**：`poolclass` / `pool_size` / `max_overflow` / `pool_timeout` 必须从 `config.yaml` 的 `database.pool` 节点读取，禁止硬编码。

**配置驱动**：`resource_pool_benchmark` 节点管理基准要求，包含 `require_docstring`（默认 `true`）、`require_benchmark_script`（默认 `true`）、`benchmark_script_dir`（默认 `"tests/benchmarks/"`）、`slow_query_threshold_ms`（默认 `50`）、`monitor_days_after_change`（默认 `7`）、`system_overhead_alert_ms`（默认 `50`）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- SQLAlchemy 数据库连接池配置（NullPool / QueuePool / StaticPool）
- HTTP 客户端连接池（httpx.AsyncClient / aiohttp.ClientSession）
- Playwright 浏览器实例池（单实例 vs 多实例）
- 任何资源池配置决策

**不适用场景**：
- 开发环境的临时配置（可放宽 docstring 要求）
- 单次脚本（无长期运行需求）
- 内存数据库（如 SQLite :memory:，无连接池概念）

**历史教训**：项目早期所有场景默认用 `NullPool`，多用户场景下每次 API 请求创建新 DB 连接，P99 延迟从 50ms 涨到 200ms，但无基准数据无法定位是连接池问题。增加基准测试后发现 `QueuePool` 在多用户场景下性能提升 3 倍，但 SQLite WAL 模式下有锁冲突，最终方案是单用户用 NullPool、多用户切换 PostgreSQL + QueuePool。docstring 记录该决策后，后续 review 可快速判断是否需要调整。

**判断信号（review 触发条件）**：
- `grep "poolclass=" <file>` 无 docstring 说明选择理由
- `grep "poolclass=" <file>` 无基准测试脚本引用
- 慢查询日志中系统开销 > 50ms
- `poolclass=` / `pool_size=` 硬编码而非从 config 读取


---

### step 204：DB-WRITE-IDENTITY-TRACE 数据库写入函数身份追溯与类型安全【强制】🆕v4.38

**背景**：本轮对话修复的 8 类问题之一——`ItemsMixin.get_item()` 缺少 `user_id` 参数，多个路由调用点传入 `user_id` 触发 `TypeError: got an unexpected keyword argument 'user_id'`，且写入函数无身份隔离导致跨用户数据泄露风险。

**问题**：数据库写入/查询函数未显式接收 `user_id` 参数，造成两种危害：① 调用点传 `user_id` 触发 TypeError（参数签名不匹配）；② 写入时无 user_id 过滤，多用户场景下可能查询/修改其他用户的数据（安全隐患）。

**规范**：

1. **写入/查询函数必须显式接收 user_id【强制】**：所有涉及用户数据的 DB 写入/查询函数（Repository / Service 层）必须显式接收 `user_id: str` 参数，并在 WHERE 子句中过滤：
   ```python
   # ✅ 正确：显式接收 user_id + WHERE 过滤
   def get_item(self, item_id: str, user_id: str | None = None) -> ItemRow | None:
       stmt = select(ItemRow).where(ItemRow.item_id == item_id)
       if user_id is not None:
           stmt = stmt.where(ItemRow.user_id == user_id)
       return session.execute(stmt).scalar_one_or_none()
   ```

2. **向后兼容的 Optional user_id【强制】**：为保持向后兼容，`user_id` 参数默认值设为 `None`（`user_id: str | None = None`），当 `user_id is None` 时跳过 user_id 过滤（适用于系统级查询如 admin 接口）。

3. **调用点必须传 user_id【强制】**：所有从请求上下文获取 user_id 的调用点（API 路由 / Service 层）必须将 user_id 传递给 Repository 层，禁止调用时不传 user_id 导致跨用户查询：
   ```python
   # ✅ 正确：路由层从 request 获取 user_id 并传递
   @router.get("/items/{item_id}/summary")
   async def get_item_summary(item_id: str, request: Request):
       user_id = request.state.user_id
       return await container.items.get_item_summary(item_id, user_id=user_id)
   ```

4. **类型注解必须完整【强制】**：函数签名必须包含完整类型注解（`user_id: str | None = None`），禁止用 `user_id=None` 无类型注解，便于静态类型检查器（mypy / pyright）检测调用点遗漏。

5. **参数传递链路完整性【强制】**：user_id 从中间件 → 路由 → Service → Repository 必须完整传递，禁止任一环节丢失。与 meta-rule #52「参数链闭环验证」互补：#52 管"参数已接收但未被消费"，本规范管"参数传递链路完整不丢失"。

**配置驱动**：`db_write_identity_trace` 节点管理身份追溯规则，包含 `required_user_id_param`（默认 `true`）、`user_id_param_type`（默认 `"str | None = None"`）、`where_filter_required`（默认 `true`）、`call_site_must_pass_user_id`（默认 `true`）、`type_annotation_required`（默认 `true`）、`exempt_functions`（豁免函数列表，如系统级 admin 查询）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- 多用户系统的所有 DB 写入/查询函数（Repository / Service 层）
- 涉及 user_id 隔离的表（items / orders / evaluations / tasks 等）
- 从中间件到 Repository 的完整调用链路

**不适用场景**：
- 系统级查询（admin 接口、健康检查、统计聚合，无 user_id 隔离需求）
- 单用户系统（无 user_id 概念）
- 只读公共数据（如商品类目字典，所有用户共享）

**历史教训**：`ItemsMixin.get_item()` 缺少 `user_id` 参数，但 5 个路由调用点（`api_items.py:37` / `api_items.py:75` / `api_orders.py:305` / `api_orders.py:379` / `evaluations_seller_trend.py:156`）都传了 `user_id=user_id`，触发 `TypeError: get_item() got an unexpected keyword argument 'user_id'`，导致 GET /api/items/test-item-001/summary 接口 500 错误。修复后 `get_item` 显式接收 `user_id: str | None = None` 并在 WHERE 过滤，向后兼容未传 user_id 的调用点。

**判断信号（review 触发条件）**：
- `grep "def get_.*\(self" <file>` 命中但参数列表无 `user_id`
- `grep "user_id=user_id" <file>` 命中但被调用函数无 `user_id` 参数
- `TypeError: got an unexpected keyword argument 'user_id'` 运行时错误
- DB 查询无 `WHERE user_id ==` 过滤但表有 user_id 字段


---

