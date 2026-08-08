# Testing 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「testing」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 10：测试编写【强制】

10. **测试编写【强制】**
    - **后端**: 在 `tests/` 新增 `test_<被测模块>.py`，遵循 `asyncio_mode = "auto"`，命名 `test_<scenario>` 或 `test_<issue>_fix`
    - **前端**: 在组件/hook 同级目录新增 `__tests__/<Component>.test.tsx`
    - **Cookie 隔离**: 后端测试自动应用 `isolate_cookie_json` fixture（conftest.py）
    - **E2E**: 涉及全链路验证，参考 `tests/test_e2e.py` 用 Fake 依赖注入 Container
    - **覆盖率目标**: 关键业务模块 80%+，无测试不合并


---

### step 37：Windows 测试环境 Mock 模式【强制】🆕v4.4

37. **Windows 测试环境 Mock 模式【强制】🆕v4.4**
    - 测试代码中 Windows 环境变量（`LOCALAPPDATA`/`APPDATA`/`USERPROFILE`）必须用 `tmp_path` 正确 mock，路径结构需与实现一致
    - **判断信号**：测试涉及 Windows 文件系统路径 + 使用环境变量 + 实现依赖 `Path(LOCALAPPDATA)` 等构造路径
    - **修复模式**：`monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))` → 测试 fixture 创建 `tmp_path / "Microsoft" / "Edge" / "User Data"` 完整路径结构 → 与实现路径完全对齐
    - **配置参数**：测试 fixture 路径模板、环境变量映射在 `tests/conftest.py` 管理
    - **适用**：Windows 文件系统路径测试、浏览器 profile 发现测试、配置文件加载测试
    - **不适用**：Linux/Mac 路径测试、不涉及环境变量的路径测试、纯函数测试
    - **历史教训**：测试代码创建 `tmp_path / "Edge" / "User Data"` 但实现用 `Path(LOCALAPPDATA) / "Microsoft" / "Edge" / "User Data"`，路径结构不一致导致测试失败；调整测试 fixture 路径结构对齐实现后通过


---

### step 38：第三方插件依赖预检模式【强制】🆕v4.4

38. **第三方插件依赖预检模式【强制】🆕v4.4**
    - 使用 pytest 插件（如 `pytest-timeout`）前必须验证项目已安装，避免运行时报错；插件依赖列表需在 `pyproject.toml` 显式声明
    - **判断信号**：使用 pytest 命令行参数（如 `--timeout`）+ 依赖第三方插件 + 未在 `pyproject.toml` 声明
    - **修复模式**：`pyproject.toml` `[tool.pytest.ini_options]` 显式声明 `addopts` + `requirements-dev.txt` 列出插件依赖 → 运行前用 `pytest --version` + 插件检查脚本验证
    - **配置参数**：插件依赖列表在 `pyproject.toml` 管理，预检脚本在 `scripts/check-deps.ps1`
    - **适用**：所有 pytest 插件依赖（`pytest-timeout`/`pytest-cov`/`pytest-asyncio`）、 tox/nox 多环境测试
    - **不适用**：pytest 内置功能（无需预检）、CI 环境固定镜像（依赖明确）
    - **历史教训**：使用 `pytest --timeout=60` 报错 `unrecognized arguments`，项目未安装 `pytest-timeout` 插件；移除 `--timeout` 标志后通过，但应预检插件依赖

### 第三阶段：验证与交付

---

### step 53：过滤逻辑场景区分【强制】🆕v4.7

53. **过滤逻辑场景区分【强制】🆕v4.7**
    - 同一查询函数被多个场景复用时，过滤逻辑必须**参数化场景标志**（如 `include_failed` / `include_deleted` / `scope`），调用方按使用场景传值，**禁止**一刀切过滤导致展示页看不到完整数据
    - **判断信号**：函数命名含 `list_*` / `get_*` / `query_*` 且 grep 多个调用点 → 检查过滤逻辑是否硬编码（如 `if status == 'failed': continue`）→ 必须改为参数化
    - **修复模式**：
      ```python
      def list_orders_by_item_ids(
          self, item_ids: list[str], include_failed: bool = False
      ) -> dict[str, dict]:
          """批量查询多个商品的最新订单状态

          include_failed 控制是否包含 failed 订单：
          - False（默认）：跳过 failed 订单，用于「是否允许重新抢单」判断
          - True：保留 failed 订单，用于评估明细展示完整订单历史
          """
          if not item_ids:
              return {}
          result: dict[str, dict] = {}
          with self.engine.connect() as conn:
              stmt = (
                  select(OrderRow)
                  .where(OrderRow.item_id.in_(item_ids))
                  .order_by(OrderRow.created_at.desc())
              )
              for row in conn.execute(stmt).all():
                  order = self._row_to_dict(row)
                  iid = order.get("item_id")
                  if not iid or iid in result:
                      continue
                  if not include_failed and order.get("status") == "failed":
                      continue
                  result[iid] = order
          return result
      ```
    - **关键约束**：
      - 场景标志必须**默认安全**（`include_failed=False` 默认跳过失败，避免影响现有逻辑）
      - 函数 docstring 必须说明**两种场景**的用途（操作判断 vs 展示历史）
      - 调用方必须**显式传值**（如 `include_failed=True`），不依赖默认值
      - 必须新增**回归测试**覆盖两种场景（参考 `test_list_orders_by_item_ids_failed_filter`）
    - **配置参数**：`scenario_flag_field`（默认 `include_failed`）、`status_whitelist`（默认 `['succeeded', 'pending']`）、`multi_scene_callsites`（多场景调用点列表）在 `config.yaml` 的 `filter_scenario` 节点管理
    - **适用**：同一查询被"操作判断"与"展示历史"两种场景复用，尤其是订单/任务/日志类查询
    - **不适用**：单一场景的查询（如报表统计只看成功）、有独立 Repo 方法的查询、权限过滤（应单独抽取）
    - **历史教训**：`list_orders_by_item_ids` 无条件 `if status == 'failed': continue`，导致评估明细页看不到失败订单记录，用户点击抢单失败后刷新页面看到 "—"，误以为没下过单而反复触发抢单。修复后增加 `include_failed` 参数，评估明细调用传 `True`


---

### step 66：pytest 模块重复 import 隔离规范【强制】🆕v4.11

66. **pytest 模块重复 import 隔离规范【强制】🆕v4.11**
    - pytest 在 `sys.modules` 中可能以 `test_xxx`（无包前缀）和 `tests.test_xxx`（带包前缀）两种名字持有同一测试文件的不同模块对象，conftest.py patch 模块属性时**禁止**硬编码模块名列表，必须遍历 `sys.modules` 找所有持目标属性的模块全部 patch
    - **关键约束**：
      1. **禁止硬编码模块名列表**：如 `for name in ["cookie_rotator", "api_tasks"]: patch(sys.modules[name])` —— 一旦新增模块需手动同步列表，极易遗漏
      2. **必须遍历 sys.modules**：用 `hasattr(mod, TARGET_ATTR)` 动态识别所有持目标属性的模块，全部 patch
      3. **禁止用 `__import__`**：`__import__("a.b")` 返回顶层包 `a` 而非子模块 `a.b`，必须用 `importlib.import_module` 正确返回子模块
      4. **patch 后验证**：patch 完成后必须 `assert hasattr(mod, TARGET_ATTR)` 验证 patch 生效
    - **判断信号**：
      - conftest.py 含 `for name in [...]: monkeypatch.setattr(sys.modules[name], ...)` 硬编码列表 → 视为违规
      - 测试用例 `import tests.test_xxx` 后修改模块属性，但被测代码 `from test_xxx import YYY` 读取的是另一份模块对象 → 典型症状
      - 代码含 `__import__("a.b")` 且后续操作期望得到子模块 → 视为违规
    - **修复模式**：
      ```python
      # ✅ 正确：遍历 sys.modules 找所有持目标属性的模块
      import sys
      TARGET_ATTR = "_COOKIE_JSON"

      def patch_all_modules_with_cookie(tmp_path):
          patched = []
          for mod in sys.modules.values():
              if mod is None:
                  continue
              if hasattr(mod, TARGET_ATTR):
                  # patch 到 tmp_path 隔离生产数据
                  setattr(mod, TARGET_ATTR, str(tmp_path / "cookies.json"))
                  patched.append(mod.__name__)
          assert patched, f"未找到持 {TARGET_ATTR} 属性的模块"
          return patched

      # ✅ 正确：importlib.import_module 替代 __import__
      import importlib
      mod = importlib.import_module("xianyu_hunter.modules.cookie_rotator")

      # ❌ 错误：硬编码模块名列表
      for name in ["cookie_rotator", "api_tasks", "auth_middleware"]:
          monkeypatch.setattr(sys.modules[name], "_COOKIE_JSON", ...)

      # ❌ 错误：__import__ 返回顶层包
      mod = __import__("xianyu_hunter.modules.cookie_rotator")  # 返回 xianyu_hunter 而非 cookie_rotator
      ```
    - **配置参数**：`pytest_isolation.target_attr_pattern`（默认 `_COOKIE_JSON`，支持正则）、`pytest_isolation.module_name_prefixes`（默认 `[]` 表示全扫，可选限制如 `["xianyu_hunter", "tests"]`）、`pytest_isolation.use_importlib`（默认 `true`，强制使用 `importlib.import_module`）在 `config.yaml` 的 `pytest_isolation` 节点管理
    - **适用**：pytest conftest.py 全局 fixture patch 模块属性；多模块共享同一配置文件路径的场景；任何需要 patch 跨模块共享状态的测试
    - **不适用**：单模块测试（直接 monkeypatch 即可）；非 pytest 测试框架；patch 对象属性（非模块属性）
    - **历史教训**：`conftest.py` 硬编码 `[cookie_rotator]` 列表 patch `_COOKIE_JSON`，但 pytest 以 `test_cookie_rotator` 和 `tests.test_cookie_rotator` 两种名字持有同一文件的两个模块对象，patch 只命中其中一个，导致生产 `data/cookies.json` 被测试数据污染。修复后改为遍历 `sys.modules` 找所有持 `_COOKIE_JSON` 属性的模块全部 patch


---

### step 68：测试 fixture 生产隔离与数据污染应急规范【强制】🆕v4.11

68. **测试 fixture 生产隔离与数据污染应急规范【强制】🆕v4.11**
    - conftest.py 必须 patch 生产路径（如 `data/cookies.json`、`*.db`）到 `tmp_path`，fixture 数据需带可识别特征（如 `test_fixture_` 前缀），数据污染应急必须按 5 步流程执行
    - **关键约束**：
      1. **生产路径 patch**：所有 fixture 必须用 `tmp_path` 隔离生产路径，**禁止**直接读写生产文件（如 `data/cookies.json`）
      2. **fixture 数据可识别特征**：测试数据必须带前缀/后缀（如 `test_fixture_user_`、`__test__cookie`），便于污染后定位
      3. **数据污染应急 5 步流程**：
         - **步骤 1 停止服务**：立即停止所有可能读写污染文件的服务（避免污染扩散）
         - **步骤 2 删除污染文件**：删除被测试数据污染的生产文件（如 `data/cookies.json`）
         - **步骤 3 修复 conftest**：修复 conftest.py 隔离逻辑（参考 step 66 遍历 sys.modules patch）
         - **步骤 4 重跑测试**：重跑全部测试验证修复有效（`pytest` 全绿）
         - **步骤 5 通知用户**：明确告知用户哪些文件被污染、已删除、需重新初始化
      4. **patch 验证**：fixture 加载后必须 `assert not os.path.exists(production_path)` 验证生产路径未被写入
      5. **fixture 作用域**：跨测试共享的 fixture 用 `scope="session"`，单测试用 `scope="function"`，**禁止**用模块级全局变量持有测试数据
    - **判断信号**：
      - conftest.py 含 `open("data/cookies.json", "w")` 直接写生产路径 → 视为违规
      - 测试数据无前缀/后缀特征（如 `user_id = "abc123"` 而非 `user_id = "test_fixture_abc123"`）→ 视为违规
      - 生产文件含测试数据（如 `data/cookies.json` 含 `test_fixture_` 前缀的 cookie）→ 典型污染症状
    - **修复模式**：
      ```python
      # ✅ 正确：tmp_path 隔离 + 可识别特征 + patch 验证
      @pytest.fixture(scope="session")
      def isolated_cookie_path(tmp_path_factory):
          cookie_path = tmp_path_factory.mktemp("data") / "cookies.json"
          # 写入带 test_fixture_ 前缀的测试数据
          cookie_path.write_text('{"token": "test_fixture_token_xxx"}')
          # patch 所有持 _COOKIE_JSON 属性的模块
          patched = []
          for mod in sys.modules.values():
              if mod is not None and hasattr(mod, "_COOKIE_JSON"):
                  setattr(mod, "_COOKIE_JSON", str(cookie_path))
                  patched.append(mod.__name__)
          assert patched, "未找到持 _COOKIE_JSON 属性的模块"
          return cookie_path

      # 数据污染应急流程（按 config.yaml 的 test_isolation.pollution_recovery_steps 执行）
      # 1. 停止服务：xianyu-automation-startserver stop
      # 2. 删除污染文件：rm data/cookies.json
      # 3. 修复 conftest：参考 step 66 遍历 sys.modules patch
      # 4. 重跑测试：pytest
      # 5. 通知用户：告知污染文件清单
      ```
    - **配置参数**：`test_isolation.production_path_patterns`（默认 `["data/cookies.json", "data/*.db", "data/*.json"]`）、`test_isolation.test_data_markers`（默认 `["test_fixture_", "__test__"]`）、`test_isolation.pollution_recovery_steps`（默认 5 步流程列表）、`test_isolation.fixture_scope_default`（默认 `function`）、`test_isolation.assert_no_production_write`（默认 `true`，加载 fixture 后断言生产路径未写入）在 `config.yaml` 的 `test_isolation` 节点管理
    - **适用**：所有 pytest fixture 涉及文件 IO 的场景；conftest.py 全局 fixture；CI/CD 测试环境
    - **不适用**：纯内存测试（无文件 IO）；mock 替代真实文件的测试；一次性脚本测试
    - **历史教训**：`conftest.py` 未隔离 `data/cookies.json`，测试用例直接写入生产文件，导致生产 cookie 被测试数据污染（含 `test_fixture_` 前缀的 token）。应急流程：停止服务 → 删除 `data/cookies.json` → 修复 conftest 遍历 sys.modules patch → 重跑 pytest 全绿 → 通知用户重新初始化 cookie


---

### step 128：测试 mock 同步规范（test mock synchronization）【强制】🆕v4.27

**背景**：修改接口前置条件（如新增 cookie 完整性预检）后，原测试未同步更新 mock，导致测试失败或测试通过但实际逻辑错误。

**问题**：`_collect_detail_only` 新增 `_check_detail_cookie_completeness` 预检后，原测试 `test_detail_only_collection_preserves_old_title_and_syncs_display` 未 mock `container.browser.get_cookies`，预检读不到 cookie 抛 401，测试失败。

**规范**：

1. **修改前置条件时同步更新测试 mock【强制】**：接口新增前置检查（如 cookie 完整性、token 有效性、配置加载）时，必须同步更新测试 mock 让前置检查通过：

   ```python
   # 修改前：原测试 mock
   container = MagicMock()
   container.collector.detail = AsyncMock(return_value=detail)

   # 修改后：新增 cookie 预检，需 mock browser.get_cookies
   container.browser.get_cookies = AsyncMock(return_value=[
       {"name": n, "value": "v"} for n in [
           "cookie2", "sgcookie", "unb", "_m_h5_tk",
           "cna", "tracknick", "_tb_token_", "t", "tfstk",
           "xlly_s", "_samesite_flag_", "KLNotice",
       ]
   ])
   ```

2. **mock 数据必须覆盖完整字段集【强制】**：mock 数据必须覆盖前置检查的所有关键字段（如 cookie 预检的 identity + session 双类 cookie），避免单类 mock 导致预检通过但实际逻辑错误。

3. **测试失败时优先检查前置条件变更【强制】**：测试失败时优先检查是否是前置条件变更导致（如新增预检、新增参数、新增依赖），而非测试逻辑本身错误。

4. **mock 数据集中管理【强制】**：测试 mock 数据集中的常量（如完整 cookie 集清单）应提取为测试模块级常量，避免散落多个测试函数：

   ```python
   # test_collection_service.py 模块级
   _COMPLETE_COOKIE_MOCK = [
       {"name": n, "value": "v"} for n in [
           "cookie2", "sgcookie", "unb", "_m_h5_tk",
           "cna", "tracknick", "_tb_token_", "t", "tfstk",
       ]
   ]

   # 测试函数复用
   container.browser.get_cookies = AsyncMock(return_value=_COMPLETE_COOKIE_MOCK)
   ```

**配置驱动**：mock 数据清单、前置条件检查项、测试失败排查步骤等参数在 `config.yaml` 的 `test_mock_synchronization` 节点管理，包含 `complete_mock_data` / `precheck_fields` / `failure_debug_steps` 等，不硬编码在技能中。

**适用场景**：
- 接口新增前置检查（cookie/token/config 完整性）
- 接口新增依赖（如新增 browser.get_cookies 调用）
- 接口签名变更（新增参数）
- mock 数据需覆盖多类字段的场景

**不适用场景**：
- 纯函数测试（无外部依赖）
- 已有完整 mock 的接口（无需新增）
- 一次性脚本测试（无长期维护需求）

**历史教训**：`_collect_detail_only` 新增 cookie 完整性预检后，原测试 `test_detail_only_collection_preserves_old_title_and_syncs_display` 未 mock `container.browser.get_cookies`，预检读不到 cookie 抛 401，测试失败。修复后添加 12 个 cookie 的 mock 数据（覆盖 identity + session 双类），测试通过。

**判断信号（review 触发条件）**：
- 接口新增前置检查但测试未更新 mock
- 测试失败原因是 `AttributeError: 'MagicMock' object has no attribute '<new_method>'`
- mock 数据只覆盖单类字段（如只有 identity cookie 无 session cookie）
- 测试 mock 数据散落多个函数而非集中常量


---

### step 133：Windows 终端编码与 Shell 语法兼容规范【强制】🆕v4.29

**背景**：项目部署在 Windows 环境，默认终端 PowerShell 存在编码（cp936/gbk）和 shell 语法（`&&` 不支持/`stash@{0}` 哈希表解析）差异，导致脚本调用 API 时中文乱码、git 操作失败、命令拼接报错。

**问题**：
1. PowerShell 默认编码 cp936/gbk，外部脚本批量调用 `POST /api/chatbot/faq` 时中文 body 被转换为 `?`，导致数据库存储乱码（如「你好」变成 `??`）
2. PowerShell 不支持 `&&` 语法（如 `cd dir && npm run build` 报错），需用 `;` 或分步执行
3. `git stash@{0}` 在 PowerShell 中被解析为哈希表语法，需加引号 `'stash@{0}'`
4. PowerShell 输出重定向默认编码与 Python `print` 中文编码不一致，导致日志文件乱码

**规范**：

1. **PowerShell 编码设置【强制】**：脚本启动时必须显式设置 UTF-8 编码，**禁止**依赖默认 cp936/gbk：
   ```powershell
   # ✅ 正确：脚本开头设置 UTF-8 编码
   [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   $OutputEncoding = [System.Text.Encoding]::UTF8
   chcp 65001 > $null  # 设置控制台代码页为 UTF-8

   # 调用 API 时显式设置 Content-Type 和 body 编码
   $body = @{ question = "你好"; answer = "世界" } | ConvertTo-Json -Depth 10
   $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/chatbot/faq" -Method Post -ContentType "application/json; charset=utf-8" -Body $bytes

   # ❌ 错误：依赖默认编码，中文变 ?
   # Invoke-RestMethod -Uri "..." -Method Post -Body ($body | ConvertTo-Json)  # 中文被 cp936 编码为 ?
   ```

2. **PowerShell 语法兼容【强制】**：命令拼接必须用 `;` 而非 `&&`，含特殊字符的参数必须加引号：
   ```powershell
   # ✅ 正确：用 ; 分隔命令
   cd frontend; npm run build

   # ✅ 正确：stash@{0} 加引号避免哈希表解析
   git stash apply 'stash@{0}'

   # ❌ 错误：用 && 分隔命令（PowerShell 不支持）
   # cd frontend && npm run build  # 报错：The token '&&' is not a valid statement separator

   # ❌ 错误：stash@{0} 不加引号
   # git stash apply stash@{0}  # 报错：解析为哈希表
   ```

3. **Python 脚本输出编码【强制】**：Python 脚本在 Windows 环境必须显式设置 stdout 编码：
   ```python
   # ✅ 正确：脚本开头设置 stdout 编码
   import sys
   sys.stdout.reconfigure(encoding='utf-8')  # Python 3.7+
   # 或用环境变量 PYTHONIOENCODING=utf-8

   # ❌ 错误：依赖默认编码，print 中文到日志文件乱码
   # print("处理完成")  # 日志文件可能是 cp936 编码
   ```

4. **跨平台脚本兼容【强制】**：脚本必须同时支持 Windows 和 Linux，用条件判断而非硬编码路径分隔符：
   ```python
   # ✅ 正确：用 pathlib 跨平台
   from pathlib import Path
   log_path = Path("logs") / "startup.log"

   # ✅ 正确：用 os.path 跨平台
   import os
   log_path = os.path.join("logs", "startup.log")

   # ❌ 错误：硬编码路径分隔符
   # log_path = "logs\\startup.log"  # Linux 不兼容
   ```

**配置驱动**：编码设置、shell 语法兼容规则、跨平台路径处理等参数在 `config.yaml` 的 `cross_platform` 节点管理，包含 `encoding` / `shell_quoting` / `path_separator` / `command_separator` 等，不硬编码在技能中。

**适用场景**：
- Windows PowerShell 脚本调用 API（含中文 body）
- Python 脚本在 Windows 环境输出中文到日志
- git 操作（stash/branch 等含特殊字符的参数）
- 跨平台部署的脚本（Windows + Linux）

**不适用场景**：
- Linux/Mac 环境的 shell 脚本（默认 UTF-8）
- Docker 容器内脚本（容器内默认 UTF-8）
- 纯英文内容的脚本（无编码问题）

**历史教训**：
- 外部脚本批量调用 `POST /api/chatbot/faq` 时 PowerShell 默认 cp936 编码，中文 body 被转换为 `?`，导致数据库存储 3 条乱码记录（id=1/2/3），需手动删除。修复：脚本显式设置 UTF-8 编码 + body 用字节数组传递
- `git stash apply stash@{0}` 在 PowerShell 中报错「解析为哈希表」，修复：加引号 `'stash@{0}'`
- `cd frontend && npm run build` 报错「`&&` 不是有效的语句分隔符」，修复：改用 `;`

**判断信号（review 触发条件）**：
- `grep "cp936\|gbk" <file>` 出现编码硬编码 → 视为可疑
- `grep "&&" <ps1_file>` PowerShell 脚本含 `&&` → 视为违规
- `grep "stash@" <ps1_file>` 不加引号的 stash@{N} → 视为违规
- 数据库存储中文为 `?` → 编码问题可疑
- 日志文件中文乱码 → 编码问题可疑

5. **🆕v4.64.0 PowerShell 管道吞输出陷阱【强制】**：pytest/长任务命令的输出**禁止**通过管道传递给 `Select-Object`/`Where-Object`/`More` 等 sink cmdlet，这些 cmdlet 会缓冲并丢弃部分输出（尤其是 stderr 与彩色 ANSI 转义序列），导致"命令成功但无输出"的假象。必须改用文件重定向再读取：
   ```powershell
   # ✅ 正确：重定向到文件再读取，输出完整保留
   pytest tests/test_chatbot_api_degraded.py > out.txt 2>&1
   Get-Content out.txt

   # ✅ 正确：长任务用 Start-Process 重定向
   Start-Process -FilePath pytest -ArgumentList "tests/" -RedirectStandardOutput "out.txt" -RedirectStandardError "err.txt" -NoNewWindow -Wait
   Get-Content -Tail 50 out.txt

   # ❌ 错误：管道吞输出（pytest 的 FAILED/ERROR 行被 Select-Object 缓冲丢弃）
   # pytest tests/ | Select-Object -Last 50  # 看不到失败详情

   # ❌ 错误：管道 + Where-Object 过滤（彩色 ANSI 转义被截断，正则匹配失败）
   # pytest tests/ | Where-Object { $_ -match "FAILED" }  # 漏报
   ```

6. **🆕v4.64.0 测试路由一致性【强制】**：测试代码中调用 `client.post/get/put/delete` 的路径与方法**必须**与实际路由装饰器（`@bp.route`/`@bp.post` 等）完全一致，禁止凭印象编写测试路径。常见陷阱：单复数混淆（`/faq` vs `/faqs`）、HTTP 方法混淆（路由无 PUT 但测试用 PUT）、前缀重复或缺失（`/api/chatbot/faq` vs `/chatbot/faq`）。
   ```python
   # ✅ 正确：测试路径与方法匹配路由定义
   # 路由：@bp.post("/faq")  → 前缀 /api/chatbot
   # 测试：
   response = client.post("/api/chatbot/faq", json=payload)

   # ❌ 错误：复数形式（路由是 /faq 单数，测试写成 /faqs）
   # response = client.post("/api/chatbot/faqs", json=payload)  # 404

   # ❌ 错误：方法不匹配（路由无 PUT，测试用 PUT）
   # response = client.put("/api/chatbot/faq", json=payload)  # 405 Method Not Allowed
   ```

   **验证方法**：测试编写前必须 `grep "@bp\.\(post\|put\|delete\|get\)" <route_file>` 列出所有路由装饰器，与测试 client 调用逐一比对。

   **🆕v4.64.0 历史教训（FAQ 403 Bug）**：`tests/test_chatbot_api_degraded.py` 中测试用 `client.put("/api/chatbot/faqs")`，但实际路由定义为 `@bp.post("/faq")`（单数 + POST upsert with id in body），导致测试 404/405。修复：测试路径改为 `/faq`，方法改为 POST，upsert 时 id 放在 body 而非 URL。修复后测试 153 passed / 0 failed。


---

### step 167：MOCK-01 测试 Mock 数据集中管理与字段完整性规范【强制】🆕v4.29

**背景**：测试 mock 数据散落在多个测试函数内部，修改前置条件（如 cookie 完整字段集）时需逐函数修改，漏改即导致测试通过但实际运行失败；mock 数据字段不完整，缺少关键字段（如 `domain`/`path`/`expires`）导致测试无法覆盖真实场景。

**问题**：mock 数据散落多处时，前置条件变更需逐处修改，漏改即测试与实际脱节；mock 字段不完整导致测试「绿但不可信」，掩盖真实 bug。

**规范**：

1. **mock 数据集中为模块级常量【强制】**：测试 mock 数据必须集中为测试模块级常量（`MOCK_COOKIE_FULL` / `MOCK_TASK_COMPLETE`），禁止散落在各测试函数内部：
   ```python
   # ✅ 正确：集中常量，复用 + 易维护
   MOCK_COOKIE_FULL = {
       "name": "_m_h5_tk", "value": "abc123", "domain": ".taobao.com",
       "path": "/", "expires": 1893456000, "secure": True, "httponly": False,
   }

   def test_cookie_layer_sync():
       result = sync_layer(MOCK_COOKIE_FULL)
       assert result.is_valid

   # ❌ 错误：散落函数内部，字段不完整
   # def test_cookie_layer_sync():
   #     cookie = {"name": "_m_h5_tk", "value": "abc123"}  # 缺 domain/path/expires
   #     result = sync_layer(cookie)
   ```

2. **mock 字段必须覆盖完整字段集【强制】**：mock 数据必须覆盖被测对象的完整字段集（参照 ORM 模型 / Pydantic model / TS interface），禁止用部分字段 mock 测全字段逻辑。

3. **前置条件变更必须同步更新 mock【强制】**：修改前置条件（如新增字段/变更字段类型/变更校验规则）时必须同步更新所有相关 mock 常量，并通过 grep 验证无遗漏。

4. **测试失败优先检查前置条件变更【强制】**：测试失败时必须优先检查前置条件是否变更（grep 最近的 schema/model 变更），而非优先怀疑测试本身逻辑错误。

**配置驱动**：`coding_standards.test_mock.centralize`（`true`）、`required_full_fields`（`true`）、`sync_on_precondition_change`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 单元测试 mock 数据（cookie/task/order 等）
- 集成测试 fixture 数据
- mock 数据需随前置条件变更而更新

**不适用场景**：
- 一次性测试数据（仅单个测试用，无需复用）
- 随机生成的测试数据（用 factory 模式）
- 第三方库的 mock（由库提供）

**历史教训**：cookie 同步测试的 mock 数据散落在 5 个测试函数中，新增 `domain`/`path`/`expires` 字段为必填后，仅更新了 2 个函数的 mock，其余 3 个测试通过但实际运行时因字段缺失失败。修复后提取 `MOCK_COOKIE_FULL` 常量，5 处复用。

**判断信号（review 触发条件）**：
- `grep "def test_" <test_file>` 函数内部含 mock 数据字面量
- mock 数据字段数 < ORM 模型字段数
- 测试通过但实际运行失败（mock 与实际脱节）
- 前置条件变更后未 grep 更新 mock


---

### step 192：mock 同步与边界精确性规范【强制，meta-rule #55 落地】🆕v4.37

192. **mock 同步与边界精确性规范【强制，meta-rule #55 落地】🆕v4.37**
    - 修改被测代码后必须同步更新 mock：mock 类型与被 mock 对象的同步/异步特性必须一致，patch 必须 patch **实际调用点**而非定义点，mock 数据必须覆盖完整字段集，测试必须断言"副作用未发生"
    - **与 step 128 测试 mock 同步规范的边界**：
      - step 128 关注"接口新增前置检查时同步更新 mock 数据"
      - 本规范关注"mock 类型/patch 路径/字段完整性/副作用断言"的精确性
    - **类型匹配矩阵**：
      | 被 mock 函数签名 | 正确 mock 类型 | 错误 mock 类型 | 症状 |
      |------------------|----------------|----------------|------|
      | `def f(): ...` | `MagicMock` | `AsyncMock` | `await` 在同步对象上失败 |
      | `async def f(): ...` | `AsyncMock` | `MagicMock` | `coroutine never awaited` |
      | `@property` | `PropertyMock` | `MagicMock` | 属性访问返回 mock 对象本身 |
    - **patch 边界**：必须 patch **实际调用点**（如 `worker.get_secret`）而非定义点（如 `secrets.get_secret`），因为 Python 的 `from x import f` 会在导入时绑定引用
      ```python
      # ❌ 错误：patch 定义点，但 worker.py 已 from secrets import get_secret
      patch("xianyu_hunter.modules.secrets.get_secret", return_value=None)

      # ✅ 正确：patch 实际调用点
      patch("xianyu_hunter.modules.worker.get_secret", return_value=None)
      ```
    - **字段完整性**：mock 数据必须覆盖被测代码访问的所有字段，禁止部分 mock，否则测试通过但运行时 NPE
    - **副作用断言**：测试必须断言"副作用未发生"
      ```python
      # ✅ 正确：断言未发起真实网络请求
      mock_post.assert_not_called()

      # ✅ 正确：断言未写文件
      assert not Path("data/cookies.json").exists()
      ```
    - **判断信号**：
      - `grep "AsyncMock" <test_file>` 但被 mock 函数是同步函数（无 `async def`）→ 违规
      - `grep "MagicMock" <test_file>` 但被 mock 函数是 `async def` → 违规
      - `patch("module.function")` 但实际调用是 `from module import function; function()` → patch 边界错误
      - mock 数据字段数 < 被测代码访问的字段数 → 不完整
      - 测试未断言副作用未发生（如未 `assert_not_called()`）→ 不完整
    - **修复模式**：
      ```python
      # ✅ 正确：类型匹配 + patch 调用点 + 完整字段 + 副作用断言
      def test_dingtalk_notify_skipped_when_secret_empty(monkeypatch):
          # worker.py 的 filter_new 是同步函数 → 用 MagicMock
          monkeypatch.setattr(worker, "filter_new", MagicMock(return_value=[]))
          # patch 调用点 worker.get_secret 而非定义点 secrets.get_secret
          monkeypatch.setattr(worker, "get_secret", lambda k: None)
          # mock 完整字段（覆盖 notifier 访问的所有字段）
          mock_notifier = MagicMock()
          mock_notifier.enabled = False
          mock_notifier.webhook_url = ""
          mock_notifier.secret = ""
          # 副作用断言：未发起真实钉钉请求
          mock_post = MagicMock()
          monkeypatch.setattr("xianyu_hunter.modules.notifier.requests.post", mock_post)

          result = run_notify_flow()

          assert result.skipped is True
          mock_post.assert_not_called()  # 副作用断言

      # ❌ 错误：AsyncMock 用于同步函数
      # monkeypatch.setattr(worker, "filter_new", AsyncMock(return_value=[]))  # 同步函数

      # ❌ 错误：patch 定义点
      # monkeypatch.setattr("xianyu_hunter.modules.secrets.get_secret", lambda k: None)
      ```
    - **配置参数**：`mock_sync.type_check`（默认 `true`，启用类型匹配检查）、`mock_sync.required_fields_check`（默认 `true`，启用字段完整性检查）、`mock_sync.side_effect_assert`（默认 `true`，强制副作用断言）、`mock_sync.patch_boundary_strict`（默认 `true`，patch 必须命中调用点）、`mock_sync.exemption_list`（豁免列表，如快照测试）在 `config.yaml` 的 `mock_sync` 节点管理
    - **适用**：所有 unit test / 集成测试中的 mock 替身
    - **不适用**：E2E 测试（应使用真实环境）、快照测试（snapshot test）
    - **历史教训**：`test_dingtalk_notify_integration.py` 用 `AsyncMock` 但 `worker.py` 的 `filter_new` 已改为同步实现，导致 `await` 在同步对象上失败。`test_notifier_new_channels.py` patch `get_secret` 位置错误导致 webhook_url/secret 实际不为空，测试发起真实钉钉请求。修复：AsyncMock 改 MagicMock 对齐同步实现 / patch get_secret 返回 None 确保真正为空 / test_manual_takeover_lock 构造 mock request 含 user_id


---

### step 236：monkeypatch 模块级 from-import 绑定覆盖规范【强制】🆕v4.49

236. **monkeypatch 模块级 from-import 绑定覆盖规范【强制】🆕v4.49**
    - 源码使用 `from X import Y` 时，Y 在模块加载时已绑定到当前模块命名空间，测试 monkeypatch 必须 patch **所有引用 Y 的模块级引用**，单独 patch 源模块 `X.Y` 不会影响已 from-import 的模块
    - **与 step 66/192 的边界**：
      - step 66 关注 pytest `sys.modules` 重复持有同一测试文件的不同模块对象（如 `test_xxx` vs `tests.test_xxx`）
      - step 192 关注 patch 必须命中实际调用点而非定义点
      - 本规范关注 `from X import Y` 模式下，**多个业务模块**各自持有一份 Y 的引用，需逐一 patch
    - **关键约束**：
      1. **检测 from-import 模式**：搜索源码 `grep "from xianyu_hunter.config import get_settings"`，列出所有命中模块
      2. **逐一 patch 所有引用模块**：每个 from-import 了 Y 的模块都需单独 `monkeypatch.setattr("target_module.Y", mock)`
      3. **patch 验证**：patch 后在测试函数内 `from target_module import Y; assert Y is mock` 验证生效
      4. **优先用依赖注入**：若源码支持 FastAPI `Depends()` 注入，优先用 `app.dependency_overrides` 替代 monkeypatch
    - **判断信号**：
      - 测试 monkeypatch 了 `xianyu_hunter.config.get_settings` 但被测代码 `from xianyu_hunter.config import get_settings` 后直接调用 → patch 不生效
      - 测试设置了 `openai_api_key=None` 但被测代码读到的仍是环境变量中的真实 key → 典型症状
      - `grep "from xianyu_hunter.config import" src/` 命中多个模块 → 需逐一 patch
    - **修复模式**：
      ```python
      # ❌ 错误：只 patch 源模块，from-import 的模块不受影响
      monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: test_settings)

      # ✅ 正确：patch 所有 from-import 了 get_settings 的模块
      monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: test_settings)
      monkeypatch.setattr("xianyu_hunter.web.app.get_settings", lambda: test_settings, raising=False)
      monkeypatch.setattr("xianyu_hunter.web.routes.api_ai_deep.get_settings", lambda: test_settings, raising=False)
      # ... 其他 from-import 了 get_settings 的模块

      # ✅ 更优：用 FastAPI 依赖注入替代 monkeypatch
      app.dependency_overrides[get_settings] = lambda: test_settings
      ```
    - **配置参数**：`monkeypatch_from_import.scan_pattern`（默认 `"from {config_module} import"`，正则扫描 from-import 命中模块）、`monkeypatch_from_import.auto_patch_all`（默认 `true`，自动 patch 所有命中模块）、`monkeypatch_from_import.prefer_di`（默认 `true`，优先用依赖注入）在 `config.yaml` 的 `monkeypatch_from_import` 节点管理
    - **适用**：Python 项目使用 `from X import Y` 模式引入全局单例（Settings/Config/Logger）；测试用 monkeypatch.setattr 替换全局单例
    - **不适用**：使用 `import X` 然后 `X.Y` 访问的模式（patch 源模块即可）；无全局单例的项目；纯函数测试
    - **历史教训**：`test_ai_deep.py` 的 fixture monkeypatch 了 `xianyu_hunter.config.get_settings` 和 `xianyu_hunter.web.app.get_settings`，但 `api_ai_deep.py` 通过 `from xianyu_hunter.config import get_settings` 在模块加载时已绑定引用，patch 不生效，导致 `openai_api_key` 读到环境变量真实值，`source` 返回 `"llm"` 而非 `"rule"`。修复后额外 patch `xianyu_hunter.web.routes.api_ai_deep.get_settings`


---

### step 237：同步/异步方法测试调用匹配规范【强制】🆕v4.49

237. **同步/异步方法测试调用匹配规范【强制】🆕v4.49**
    - 方法定义为 `async def` 时测试必须用 `await` 调用；方法定义为同步 `def` 时测试**禁止**用 `await` 调用；mock 替身的类型（AsyncMock/MagicMock）必须与被 mock 方法的同步/异步特性一致
    - **与 step 192 的边界**：step 192 关注 mock 类型匹配矩阵，本规范关注**测试调用方**的 await 匹配与生命周期不对称场景
    - **关键约束**：
      1. **await 匹配检测**：测试代码 `await obj.method()` 时，`method` 必须是 `async def`；`obj.method()`（无 await）时，`method` 应为同步 `def`
      2. **生命周期不对称**：同一类的 `start` 可能是同步、`stop` 可能是异步（如 TokenRenewer.start 同步、stop 异步），测试必须分别匹配
      3. **mock 类型匹配**：同步方法用 `MagicMock`，异步方法用 `AsyncMock`；同步方法用 `AsyncMock` 会产生 `coroutine never awaited` 警告
      4. **重构同步/异步时同步更新测试**：源码方法从同步改为异步（或反向）时，测试的 `await` 和 mock 类型必须同步更新
    - **判断信号**：
      - `TypeError: 'NoneType' object can't be awaited` → 测试 `await` 了同步方法（返回 None）
      - `TypeError: 'bool' object can't be awaited` → 测试 `await` 了同步方法（返回 bool）
      - `RuntimeWarning: coroutine never awaited` → 用 AsyncMock mock 了同步方法
      - `grep "await orch.start" tests/` 但源码 `def start(self):`（无 async）→ 违规
    - **修复模式**：
      ```python
      # ❌ 错误：await 同步方法
      await orch.start_session(...)  # start_session 是同步 def

      # ✅ 正确：同步方法直接调用
      orch.start_session(...)

      # ❌ 错误：AsyncMock 用于同步方法
      monkeypatch.setattr(renewer, "start", AsyncMock())  # start 是同步 def

      # ✅ 正确：同步方法用 MagicMock
      monkeypatch.setattr(renewer, "start", MagicMock())

      # ✅ 正确：异步方法用 AsyncMock + await
      monkeypatch.setattr(renewer, "stop", AsyncMock())
      await renewer.stop()
      ```
    - **配置参数**：`async_sync_match.check_await`（默认 `true`，检测 await 与方法定义是否匹配）、`async_sync_match.check_mock_type`（默认 `true`，检测 mock 类型与方法定义是否匹配）、`async_sync_match.lifecycle_asymmetric_patterns`（默认 `[{"class": "TokenRenewer", "sync": ["start"], "async": ["stop"]}]`，已知生命周期不对称的类清单）在 `config.yaml` 的 `async_sync_match` 节点管理
    - **适用**：Python asyncio 项目的单元测试；同一类含同步+异步混合方法的场景（如 TokenRenewer、LoginOrchestrator）；方法重构同步/异步特性时
    - **不适用**：纯同步项目（无 async）；纯异步项目（全 async）；无 mock 的测试
    - **历史教训**：`test_login_orchestrator.py` 对 `LoginOrchestrator.start_session`（同步）和 `start_session_default`（同步）使用 `await`，对 `TokenRenewer.start`（同步）使用 `AsyncMock`，导致 `TypeError: 'NoneType'/'bool' object can't be awaited` 和 `coroutine never awaited` 警告。修复后移除同步方法的 `await`，将 `TokenRenewer.start` 的 `AsyncMock` 改为 `MagicMock`


---

### step 238：属性名重构与对外序列化字段名分离规范【强制】🆕v4.49

238. **属性名重构与对外序列化字段名分离规范【强制】🆕v4.49**
    - 数据类属性名从驼峰（camelCase）改为蛇形（snake_case，PEP 8）时，测试必须同步更新属性引用；但对外序列化方法（`to_dict()`/`to_query_string()`/`to_json()`）仍须保留协议要求的字段名（如 MTOP 协议要求 `appKey`/`dataType`）
    - **关键约束**：
      1. **属性名遵循 PEP 8**：Python 数据类属性名用蛇形（`app_key`/`data_type`），不用驼峰
      2. **序列化字段名遵循协议**：对外暴露的序列化字段名（如 HTTP API、MTOP 协议）保留协议要求的命名（`appKey`/`dataType`）
      3. **重构时同步更新测试**：属性名变更后，测试中访问属性的代码（`obj.appKey` → `obj.app_key`）和构造对象的代码（`Cls(appKey=x)` → `Cls(app_key=x)`）必须同步更新
      4. **序列化测试不变**：序列化方法输出的字段名不变（仍为 `appKey`），所以序列化测试的断言（`result["appKey"]`）不需要改
    - **判断信号**：
      - `AttributeError: 'XxxParams' object has no attribute 'appKey'. Did you mean: 'app_key'?` → 测试用了旧属性名
      - `TypeError: XxxParams.__init__() got an unexpected keyword argument 'appKey'` → 测试构造对象用了旧参数名
      - `grep "appKey" tests/` 命中属性访问（`obj.appKey`）→ 违规；命中字典 key（`result["appKey"]`）→ 正常
    - **修复模式**：
      ```python
      # 源码数据类（PEP 8 蛇形属性名）
      @dataclass
      class MtopSignedParams:
          app_key: str      # 蛇形属性名
          data_type: str

          def to_dict(self) -> dict:
              return {"appKey": self.app_key, "dataType": self.data_type}  # 协议字段名

      # ❌ 错误：测试用旧驼峰属性名
      params = MtopSignedParams(appKey="abc", dataType="json")
      assert params.appKey == "abc"

      # ✅ 正确：测试用蛇形属性名
      params = MtopSignedParams(app_key="abc", data_type="json")
      assert params.app_key == "abc"
      # 序列化测试仍用协议字段名
      assert params.to_dict()["appKey"] == "abc"
      ```
    - **配置参数**：`attr_rename.pep8_attributes`（默认 `true`，属性名遵循 PEP 8 蛇形）、`attr_rename.protocol_fields_whitelist`（默认 `{"to_dict": ["appKey", "dataType"], "to_query_string": ["appKey", "dataType"]}`，序列化方法保留的协议字段名清单）、`attr_rename.sync_test_on_rename`（默认 `true`，属性名变更时强制同步测试）在 `config.yaml` 的 `attr_rename` 节点管理
    - **适用**：Python 数据类属性名从驼峰改蛇形（PEP 8 重构）；有对外协议要求保留特定字段名的序列化（HTTP API/MTOP/JSON-RPC）
    - **不适用**：无对外序列化的纯内部数据类；已遵循 PEP 8 的项目（无需重构）；TypeScript/JavaScript 项目（驼峰是惯例）
    - **历史教训**：`MtopSignedParams` 类属性名从 `appKey`/`dataType` 改为 `app_key`/`data_type`（PEP 8），但 `test_mtop_signer.py` 仍用 `params.appKey` 访问属性和 `MtopSignedParams(appKey=...)` 构造对象，导致 `AttributeError` 和 `TypeError`。修复后测试改用 `app_key`/`data_type`，但 `to_dict()`/`to_query_string()` 的输出仍为 `appKey`/`dataType`（MTOP 协议要求），序列化测试断言不变


---

### step 239：FastAPI 端点签名变更测试同步规范【强制】🆕v4.49

239. **FastAPI 端点签名变更测试同步规范【强制】🆕v4.49**
    - FastAPI 端点函数新增参数（如 `request: Request`、`user_id: str`）时，测试直接调用函数必须传入对应参数；下游调用新增关键字参数时，mock 断言必须适配新参数
    - **关键约束**：
      1. **端点签名变更检测**：对比端点函数签名与测试调用参数，检测缺失参数
      2. **mock Request 构造**：端点新增 `request: Request` 参数时，测试直接调用需构造 mock Request：`SimpleNamespace(state=SimpleNamespace(user_id="default"))`
      3. **下游调用断言适配**：端点新增 `user_id` 关键字参数传给下游时，mock 断言需从 `assert_called_once_with(container, saved)` 改为 `assert_called_once_with(container, saved, user_id="default")`
      4. **优先用 TestClient**：如果测试用 `TestClient(app).post("/path")` 通过 HTTP 调用，则无需手动构造 Request（FastAPI 自动注入）
    - **判断信号**：
      - `TypeError: xxx_order() missing 1 required positional argument: 'request'` → 端点新增了 request 参数但测试未传入
      - `TypeError: create_task() missing 1 required positional argument: 'request'` → 同上
      - `AssertionError: assert_called_once_with(container, saved)` 但实际调用含 `user_id="default"` → 断言未适配新参数
    - **修复模式**：
      ```python
      from types import SimpleNamespace

      def _make_request(user_id: str = "default"):
          """构造 mock Request 对象，用于直接调用端点函数"""
          return SimpleNamespace(state=SimpleNamespace(user_id=user_id))

      # ❌ 错误：端点新增 request 参数但测试未传入
      result = await takeover_order(order_id="o1", container=container)

      # ✅ 正确：传入 mock Request
      result = await takeover_order(order_id="o1", request=_make_request(), container=container)

      # ❌ 错误：断言未适配新增的 user_id 参数
      mock_trigger.assert_called_once_with(container, saved)

      # ✅ 正确：断言适配新增参数
      mock_trigger.assert_called_once_with(container, saved, user_id="default")
      ```
    - **配置参数**：`endpoint_signature.default_mock_user_id`（默认 `"default"`，mock Request 的 user_id 默认值）、`endpoint_signature.check_signature_sync`（默认 `true`，检测端点签名与测试调用是否同步）、`endpoint_signature.prefer_testclient`（默认 `true`，优先建议用 TestClient 通过 HTTP 调用）在 `config.yaml` 的 `endpoint_signature` 节点管理
    - **适用**：FastAPI 端点函数签名变更（新增 request/user_id 参数）；测试直接调用端点函数（非通过 TestClient）；多用户隔离架构（request.state.user_id）
    - **不适用**：通过 TestClient HTTP 调用的测试（FastAPI 自动注入参数）；非 FastAPI 项目；端点签名未变更的场景
    - **历史教训**：`takeover_order`/`update_order_status`/`create_task` 三个端点新增 `request: Request` 参数（用于多用户隔离 `getattr(request.state, "user_id", "default")`），但测试直接调用函数时未传入，导致 `TypeError: missing 1 required positional argument: 'request'`。同时 `update_order_status` 调用下游 `_trigger_dependent_tasks` 时新增了 `user_id=user_id` 关键字参数，但测试断言 `assert_called_once_with(container, saved)` 未适配。修复后测试构造 `SimpleNamespace(state=SimpleNamespace(user_id="default"))` 传入，断言改为 `assert_called_once_with(container, saved, user_id="default")`


---

### step 240：软删除数据分类隔离规范（NULL vs 不存在外键）【强制】🆕v4.49

240. **软删除数据分类隔离规范（NULL vs 不存在外键）【强制】🆕v4.49**
    - 分类统计/查询必须区分「外键为 NULL 的孤儿数据」与「外键指向已删除记录的数据」，前者归入"未分类"显示，后者直接跳过不显示
    - **关键约束**：
      1. **NULL 判定优先**：先判 `if tid is None` 归入"未分类"，再判 `if tid not in task_map` 跳过
      2. **禁止合并判断**：`if not tid or tid not in task_map` 会把"已删除任务的数据"误归入"未分类"，视为违规
      3. **同步两条路径**：range_days=0 和 range_days>0 两条查询路径的过滤逻辑必须一致
      4. **task_map 来源过滤**：`task_map` 必须已过滤 `status != 'deleted'`，确保已删除任务不在 map 中
    - **判断信号**：
      - `grep "if not tid or tid not in" src/` 命中合并判断 → 违规
      - 分类统计返回数 > 预期（含已删除任务的分类）→ 典型症状
      - "未分类"分类含 task_id 非 NULL 的数据 → 违规（未分类只应含 task_id=NULL 的孤儿）
    - **修复模式**：
      ```python
      # ❌ 错误：合并判断，已删除任务的数据被误归入"未分类"
      for item in items:
          tid = item.get("task_id")
          if not tid or tid not in task_map:
              orphan_items.append(item)  # 已删除任务的数据也进了这里
              continue
          classified[tid].append(item)

      # ✅ 正确：分开判断，NULL 归入未分类，不存在则跳过
      for item in items:
          tid = item.get("task_id")
          if tid is None:
              orphan_items.append(item)  # 真正的孤儿（task_id 为 NULL）
              continue
          if tid not in task_map:
              continue  # task_id 指向已删除任务，跳过不显示
          classified[tid].append(item)
      ```
    - **配置参数**：`soft_delete.orphan_label`（默认 `"未分类"`，孤儿数据的分类显示名）、`soft_delete.skip_missing_fk`（默认 `true`，外键指向已删除记录时跳过）、`soft_delete.task_map_filter`（默认 `"status != 'deleted'"`，task_map 的过滤条件）、`soft_delete.sync_query_paths`（默认 `true`，要求所有查询路径的过滤逻辑一致）在 `config.yaml` 的 `soft_delete_classification` 节点管理
    - **适用**：有软删除（status='deleted'）的业务；分类统计/Dashboard 场景；task_id 外键关联场景
    - **不适用**：硬删除（物理删除）的业务；无分类统计的需求；无外键关联的场景
    - **历史教训**：`price_dashboard.py` 的 `_classify_item_prices` 函数用 `if not tid or tid not in task_map` 合并判断，导致已删除任务的商品被误归入"未分类"分类，分类数从 2 变成 3。修复后拆分为 `if tid is None`（归入未分类）和 `if tid not in task_map`（跳过），并同步修复 `_filter_category_prices_by_range` 的 range_days>0 路径


---

### step 259：Vitest 环境预检规范（VITEST-ENV-PRECHECK-01，meta-rule #95 落地）【强制】🆕v4.61.0

**背景**：前端测试运行 `npx vitest` 时，若项目未安装 vitest，npx 会交互式提示"是否安装 vitest"，在非交互环境（CI/脚本调用）下永久卡死，导致整个测试流程挂起无输出。

**问题**：
1. `npx vitest` 在 vitest 未安装时触发交互式安装提示，非交互环境（CI/脚本）下永久卡死
2. 脚本调用 `npx vitest run` 无超时保护，卡死后无任何错误输出
3. 开发者误以为测试正在运行，长时间等待才发现是卡死

**规范**：

1. **运行前预检 vitest 安装【强制】**：运行 vitest 前必须预检 `node_modules/.bin/vitest` 是否存在或 `npm ls vitest` 是否有输出，未安装时直接报错退出而非交互式卡死：
   ```powershell
   # ✅ 正确：预检 vitest 是否安装
   if (-not (Test-Path "frontend/node_modules/.bin/vitest")) {
     Write-Error "vitest 未安装，请先执行 npm install"
     exit 1
   }
   npx vitest run

   # ❌ 错误：直接调用，未安装时交互式卡死
   npx vitest run  # 无输出永久挂起
   ```

2. **非交互环境强制 --yes 或直接调用本地 bin【强制】**：CI/脚本中必须用 `./node_modules/.bin/vitest` 直接调用或 `npx --yes vitest`，禁止裸 `npx vitest` 触发交互提示

3. **测试脚本超时保护【强制】**：封装测试运行的脚本必须设置超时（如 `Start-Process -Timeout 120`），避免卡死无限等待

**配置驱动**：`vitest_env_precheck.enabled`（默认 `true`，是否强制预检）、`vitest_env_precheck.localBinPath`（默认 `frontend/node_modules/.bin/vitest`，本地 bin 路径）、`vitest_env_precheck.scriptTimeoutSeconds`（默认 `120`，脚本超时秒数）、`vitest_env_precheck.nonInteractiveFlag`（默认 `--yes`，npx 非交互标志）在 `config.yaml` 的 `vitest_env_precheck` 节点管理，不硬编码在技能中。

**适用场景**：所有运行 vitest 的脚本/CI 流程；非交互环境的测试运行；Windows PowerShell 脚本调用 vitest

**不适用场景**：交互式终端手动运行（用户可选择安装）；已确认 vitest 安装的开发环境

**历史教训**：闲鱼猎人前端编写 ErrorBoundary 测试后运行 `npx vitest`，因项目未安装 vitest，npx 交互式提示是否安装，在脚本环境下永久卡死无输出。添加预检 `Test-Path "frontend/node_modules/.bin/vitest"` 后，未安装时直接报错退出，避免卡死。

**判断信号（review 触发条件）**：
- 脚本含 `npx vitest` 但无前置安装预检 → 视为违规
- CI 配置含 `npx vitest` 无 `--yes` 标志 → 视为违规
- 测试运行无超时保护 → 视为违规


---

### step 260：tsconfig 排除测试文件规范（TSCONFIG-EXCLUDE-TESTS-01，meta-rule #95 落地）【强制】🆕v4.61.0

**背景**：前端 `tsconfig.json` 未在 `exclude` 中排除测试文件（`**/*.test.tsx`、`**/*.test.ts`、`__tests__/**`），导致 `tsc --noEmit` 类型检查时把测试文件一并编译，测试文件中使用的 vitest 全局 API（`describe`/`it`/`expect`）和 jsdom 类型在编译上下文中未定义，报大量类型错误。

**问题**：
1. `tsconfig.json` 的 `exclude` 未列出测试文件 → `tsc --noEmit` 编译测试文件报 `Cannot find name 'describe'` 等错误
2. 测试文件引用 `@testing-library/react` 等测试依赖，但 `tsconfig.json` 的 `include` 范围含测试目录 → 类型检查失败
3. CI 的 `tsc` 步骤因测试文件报错而失败，阻断部署

**规范**：

1. **tsconfig.json 必须排除测试文件【强制】**：`tsconfig.json` 的 `exclude` 必须含测试文件 glob，确保 `tsc --noEmit` 只编译源码不编译测试：
   ```json
   {
     "compilerOptions": { ... },
     "include": ["src"],
     "exclude": [
       "src/**/*.test.tsx",
       "src/**/*.test.ts",
       "src/**/__tests__/**",
       "node_modules"
     ]
   }
   ```

2. **测试文件独立 tsconfig【推荐】**：测试文件的类型检查由 `vitest` 自带 ts-jest/esbuild 处理，不依赖主 tsconfig，可新增 `tsconfig.test.json` 继承主配置并补充 vitest 类型

3. **CI 类型检查与测试分离【强制】**：CI 中 `tsc --noEmit`（类型检查）与 `vitest run`（测试执行）必须分离，tsc 不含测试文件，vitest 独立运行

**配置驱动**：`tsconfig_exclude_tests.enabled`（默认 `true`，是否强制排除测试文件）、`tsconfig_exclude_tests.excludeGlobs`（默认 `["src/**/*.test.tsx", "src/**/*.test.ts", "src/**/__tests__/**"]`，排除 glob 列表）、`tsconfig_exclude_tests.ciSeparation`（默认 `true`，CI 中类型检查与测试分离）在 `config.yaml` 的 `tsconfig_exclude_tests` 节点管理，不硬编码在技能中。

**适用场景**：所有 TypeScript 前端项目含测试文件；CI 含 `tsc` 类型检查步骤；使用 vitest/jest 的项目

**不适用场景**：无测试文件的项目；测试文件与源码在不同顶级目录（如 `tests/` vs `src/`，include 已隔离）

**历史教训**：闲鱼猎人前端 `tsconfig.json` 的 `exclude` 未含 `src/**/*.test.tsx`，运行 `tsc --noEmit` 时编译 `ErrorBoundary.test.tsx` 和 `lazyRetry.test.tsx`，报 `Cannot find name 'describe'`/`Cannot find name 'expect'` 等错误。在 `exclude` 中添加测试文件 glob 后，tsc 只编译源码通过，vitest 独立运行测试通过。

**判断信号（review 触发条件）**：
- `tsconfig.json` 的 `exclude` 不含 `*.test.*` glob → 视为违规
- `tsc --noEmit` 报 `Cannot find name 'describe'`/`'it'`/`'expect'` → 典型症状（测试文件未排除）
- CI 的 tsc 步骤因测试文件报错失败 → 典型症状


---

### step 261：antd v5 中文按钮自动空格兼容规范（ANTD-CN-BUTTON-SPACE-01，meta-rule #95 落地）【强制】🆕v4.61.0

**背景**：antd v5 的 Button 组件在检测到中文文本时会自动在两个字之间插入空格（space-between 中文排版优化），导致测试断言 `expect(button).toHaveTextContent('确认删除')` 失败，实际文本为 `确 认 删 除`（含空格）。

**问题**：
1. antd v5 Button 中文文案自动加空格，测试 `toHaveTextContent` 精确匹配失败
2. 测试快照（snapshot）含不可见的空格变化，导致快照比对失败
3. 开发者误以为是业务逻辑 bug，实际是 antd 排版特性

**规范**：

1. **测试断言兼容中文空格【强制】**：测试 antd Button 中文文案时，必须用 `replace(/\s/g, '')` 去除空格后再断言，或用 `toHaveTextContent` 的正则匹配模式：
   ```tsx
   // ❌ 错误：精确匹配，antd 自动加空格导致失败
   expect(button).toHaveTextContent('确认删除')  // 实际: "确 认 删 除"

   // ✅ 正确：去除空格后断言
   expect(button.textContent?.replace(/\s/g, '')).toBe('确认删除')

   // ✅ 正确：正则匹配忽略空格
   expect(button).toHaveTextContent(/确.*认.*删.*除/)
   ```

2. **快照测试禁用自动空格【推荐】**：快照测试可在 Button 上设 `autoInsertSpace={false}` 关闭自动空格，或测试渲染时 mock antd 的 space-insertion 逻辑

3. **测试工具函数封装【强制】**：去除中文空格的逻辑应封装为测试工具函数（如 `stripCnSpace(text)`），禁止散落多个测试用例内联处理

**配置驱动**：`antd_cn_button_space.enabled`（默认 `true`，是否启用中文空格兼容检查）、`antd_cn_button_space.stripFunctionName`（默认 `stripCnSpace`，去空格工具函数名）、`antd_cn_button_space.snapshotDisableSpace`（默认 `true`，快照测试关闭自动空格）在 `config.yaml` 的 `antd_cn_button_space` 节点管理，不硬编码在技能中。

**适用场景**：antd v5 Button 中文文案测试；含中文按钮的快照测试；所有 antd v5 组件中文文案断言

**不适用场景**：英文文案按钮（无自动空格）；antd v4 及以下（无此特性）；非 antd 组件

**历史教训**：闲鱼猎人前端 ErrorBoundary 测试中断言刷新按钮文案 `expect(button).toHaveTextContent('刷新页面')`，因 antd v5 自动在中文间加空格，实际文本为 `刷 新 页 面`，断言失败。改为 `expect(button.textContent?.replace(/\s/g, '')).toBe('刷新页面')` 后通过。

**判断信号（review 触发条件）**：
- 测试含 `toHaveTextContent('中文文案')` 精确匹配 antd Button → 视为违规
- 测试失败信息含中文文案但实际值含空格 → 典型症状
- 快照测试因中文空格变化失败 → 典型症状


---

