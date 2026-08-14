# 模式 AN：构建与运行时韧性回归测试

> 配置节点：`config.yaml#mode_an_build_runtime_resilience`
> 对应：`xianyu-hunter-dev` meta-rules #112~#115 + 复盘 `retrospective-2026-08-12`；审查 `xianyu-backend-code-review` B-REVIEW-291~295 / `xianyu-frontend-code-review` F-REVIEW-227~228。

### 触发关键词
- 安装包默认图标 / 构建产物图标 / SetupIconFile / 复用系统图标
- 打包 Python 损坏 / venv 继承死 stdlib / Could not find platform independent libraries
- 异步清理刷屏 / TargetClosedError / Future exception was never retrieved / unroute 超时
- 构建脚本编码 / .ps1 BOM / 脚本乱码

### 步骤 0：加载配置
读取 `config.yaml#mode_an_build_runtime_resilience` 段。**禁止硬编码**任何路径/超时/选择器/严重级。

### 步骤 1：构建产物资源显式化验证（#112 / B-REVIEW-291 / F-REVIEW-227）
1. `installer.iss` 必须含 `SetupIconFile`（`build_artifact_resource.installer_icon_path_default` 指定的品牌 ico）——缺失则安装包用默认图标。
2. 构建脚本内嵌 `installer.iss` 模板必须同步同一 `SetupIconFile`（删除重建不丢失）。
3. 应用 exe 图标由 `.spec` 的 `icon=` 指定。
4. 引用 `shell32.dll`/`imageres.dll` 系统图标 → WARNING（版权风险，须抽取成 `.ico`）。
- 参数：`build_artifact_resource.{installer_icon_path_default, forbid_system_icon_binding, recommend_size_px}`

### 步骤 2：构建运行时 Python 钉选验证（#113 / B-REVIEW-292）
1. 启动器（`scripts/构建打包.bat`）必须前置钉选已知完好运行时到 PATH（`build_runtime_python.pinned_python_path_default`）。
2. `.venv-build/pyvenv.cfg` 的 `home` 指向的 Python 必须健康：`Lib\os.py` 存在 + `python -m pip --version` 退出码 0（`health_check_commands`）。
3. `build-exe.ps1` 的 pip/ensurepip 调用须 `try/catch` 包裹（fail-soft 返回"重建"而非硬中止）。
- 参数：`build_runtime_python.{pinned_python_path_default, health_check_commands, require_fail_soft_pip}`

### 步骤 3：异步清理 shield + 取回回归（#114 / B-REVIEW-293）
1. 运行既有回归测试 `tests/test_unroute_search_api.py`（5 用例），验证：
   - 关闭态短接（page/context/browser 已关闭直接跳过 unroute）
   - `asyncio.shield` 保护内部 unroute task 不被 `wait_for` 超时取消（`SLOW_CANCELLED=False`）
   - `add_done_callback` 取回异常，抑制 "never retrieved"
2. 方法真实耗时 ≈ `async_cleanup_resilience.timeout_seconds_default`（2.5s），无 hang。
3. 若源码改动波及 `_unroute_search_api`，必须维持该测试覆盖（详见步骤 5 修复回归测试生成）。
- 参数：`async_cleanup_resilience.{timeout_seconds_default, require_shield, require_done_callback_retrieve}`

### 步骤 4：脚本编码 BOM/CRLF 验证（#112 反模式 / B-REVIEW-280 / B-REVIEW-295）
1. `scripts/*.ps1` 必须保持 UTF-8 BOM + CRLF（编辑后校验首 3 字节 `EF BB BF`）。
2. `scripts/*.bat` 建议纯 ASCII / 无 BOM / CRLF（消除 GBK 乱码脆弱性）。
3. 扫描用 `build_script_config_driven` 节点的 `audit_signals`（硬编码路径/超时/选择器）。
- 参数：`encoding_check.{ps1_require_bom, bat_prefer_ascii, forbidden_hardcoded}`（与 B-REVIEW 节点对齐）

### 步骤 5：修复回归测试生成（通用、配置驱动）
对任何已修复的 bug，按本步骤生成**最小 mock 驱动**的回归测试，避免依赖真实浏览器/服务：
1. 定位修复点所属 `meta-rule` / `B/F-REVIEW` 与对应配置节点。
2. 提取修复的"核心不变量"作为断言（如：shield 不取消内部 task、关闭态直接短路、钉选运行时健康）。
3. 构造最小 mock（如 `MagicMock` 模拟 Playwright `Page`，仅暴露 `is_closed`/`unroute`/`context`/`browser`），不启动真实浏览器。
4. 测试仅依赖模块级 logger（如 `_search.py` 的 `logger`），用 `SearchMixin.__new__()` 跳过 `__init__` 避免业务依赖。
5. 超时/路径/选择器全部从 `config.yaml` 读取，禁止硬编码。
6. 落盘到 `tests/`，命名 `test_<fix>.py`，并在本模式"修复回归测试索引"登记。

**反模式**：测试 cleanup 中 `await slow` 抛 `CancelledError`（BaseException 子类，不被 `except Exception` 捕获）误判失败——清理须区分 `CancelledError` 与业务异常。

### 修复回归测试索引（本模式维护）
| 修复 | 测试文件 | 核心断言 | 配置节点 |
|------|----------|----------|----------|
| 实时搜索 TargetClosedError | `tests/test_unroute_search_api.py` | shield 不取消内部 unroute / 关闭态短路 | `async_cleanup_resilience` |
| （待补充）安装包默认图标 | — | SetupIconFile 落地 | `build_artifact_resource` |
| （待补充）打包 Python 损坏 | — | launcher 钉选 + pip fail-soft | `build_runtime_python` |
