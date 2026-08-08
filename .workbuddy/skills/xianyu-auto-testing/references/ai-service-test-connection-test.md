# 模式 AD：AI 服务测试连接与预设切换回归测试

> 对应 B-REVIEW-327~329 + F-REVIEW-241~243（AI 服务菜单改造六项契约）
> 配置节点：`config.yaml#mode_ad_ai_service_test_connection_test`
> 配套编码规范：`xianyu-hunter-dev` coding-standards v1.3 §2.25（预设切换双步模式与归档加载契约）+ §2.26（敏感数据后端主导原则）

### 触发关键词
- 测试 AI 服务菜单 / 验证预设切换 / 测试 API Key 关联存储 / 测试 Embedding 模型状态
- 切换预设后 API Key 丢失 / 测试连接显示模型与配置不一致 / Embedding 模型下载状态不准 / "获取"按钮跳转错误页
- `AIConfig/constants.ts` 中 PRESETS/EMBEDDING_PRESETS 修改后
- `/api/ai/apply-preset`、`/api/ai/test-connection`、`/api/ai/test-embedding`、`/api/ai/embedding-model-status` 接口变更后

### 步骤 0：加载配置
读取 `config.yaml` 的 `mode_ad_ai_service_test_connection_test` 段。重点关注 `preset_definition_frontend_only`、`test_endpoint_status_echo`、`hf_cache_lightweight_check`、`status_display_central_map`、`external_link_security`、`preset_switch_archive_load` 子配置。禁止硬编码任何接口路径、字段名、正则、模型类名。

### 步骤 1：预设定义前后端分离验证（AD-01，对应 B-REVIEW-327）
1. **前端预设文件存在性验证**：验证 `frontend/src/pages/Config/AIConfig/constants.ts` 存在
2. **预设对象字段完整性验证**：PRESETS 对象每个预设必须包含 `base_url`/`model`/`vision_model`/`label`/`color`/`apiKeyUrl`
3. **后端硬编码预设扫描**：grep 后端代码，禁止出现 `PRESETS = {...}` / `preset_table = {...}` / `PRESET_LIST = [...]`
4. **apply-preset 接口签名验证**：`POST /api/ai/apply-preset` 必须接收 `from_preset` 与 `to_preset` 参数
5. **运行时验证**：用 Playwright 触发预设切换，验证后端不依赖硬编码列表
6. **违规标记**：发现后端硬编码预设或前端字段缺失 → P0 缺陷

### 步骤 2：测试接口状态回传契约验证（AD-02，对应 B-REVIEW-328）
1. **test-connection 状态字段验证**：`/api/ai/test-connection` 响应必须包含 `model` 字段
2. **状态字段运行时值验证**：返回的 `model` 必须是运行时实际使用的模型（从 LLM 响应获取），而非配置值
3. **test-embedding 状态字段验证**：`/api/ai/test-embedding` 响应必须包含 `model_status` 字段
4. **model_status 枚举值验证**：必须为 `downloaded`/`not_downloaded`/`checking`/`unknown` 之一
5. **失败响应状态字段验证**：即使测试失败，响应也必须包含状态字段（前端用于更新 UI）
6. **运行时验证**：用 curl/httpx 调用测试接口，断言响应包含必需字段
7. **违规标记**：发现测试接口无状态字段或值为配置值而非运行时值 → P0 缺陷

### 步骤 3：HF 缓存轻量检测验证（AD-03，对应 B-REVIEW-329）
1. **状态检测接口存在性验证**：`GET /api/ai/embedding-model-status` 必须存在
2. **检测方法验证**：状态检测必须仅检查目录存在性，禁止实例化模型
3. **禁止模型实例化验证**：grep 状态检测函数，禁止出现 `SentenceTransformer(` / `AutoModel.from_pretrained(` / `AutoTokenizer.from_pretrained(`
4. **缓存目录路径构造验证**：目录名必须符合 `models--{org}--{name}` 格式（斜杠转短横）
5. **snapshots 非空验证**：必须检查 `snapshots/` 子目录存在且非空，避免误判"目录存在但下载未完成"
6. **环境变量支持验证**：必须支持 `HF_HOME`/`HF_HUB_CACHE` 环境变量，并回退到默认缓存根目录
7. **运行时验证**：设置 `HF_HOME` 为临时目录，构造假缓存目录结构，验证状态检测返回正确
8. **违规标记**：发现检测函数实例化模型或未检查 snapshots 非空 → P0 缺陷

### 步骤 4：UI 状态映射集中配置验证（AD-04，对应 F-REVIEW-241）
1. **STATUS_DISPLAY 集中定义验证**：含状态展示的组件必须用 `Record<Status, Display>` 类型集中定义状态映射
2. **必填字段完整性验证**：每个状态值必须包含 `text`/`color`/`icon` 三个字段
3. **穷举性验证**：STATUS_DISPLAY 必须穷举所有状态枚举值，禁止遗漏
4. **内联状态分支扫描**：grep JSX，禁止出现 `status === 'xxx' ? ... : ...` 内联分支
5. **状态字段名覆盖验证**：扫描 `modelStatus`/`status`/`downloadStatus`/`connectionStatus` 等候选字段名，确认均使用集中映射
6. **运行时验证**：用 Playwright 触发不同状态（下载中/已下载/未下载），验证 UI 显示正确
7. **违规标记**：发现内联状态分支或 Record 缺失字段 → P1 缺陷

### 步骤 5：外部链接安全属性验证（AD-05，对应 F-REVIEW-242）
1. **target=_blank 链接扫描**：扫描所有 `.tsx` 文件中 `target="_blank"` 的链接
2. **rel=noopener 验证**：每个 `target="_blank"` 链接必须包含 `rel="noopener noreferrer"`
3. **antd Button href 验证**：`<Button href="https://...">` 也必须包含 `rel` 属性
4. **同源链接豁免验证**：同源链接（如 `/api/...`）可豁免
5. **违规 grep 扫描**：扫描违规模式
6. **运行时验证**：用 Playwright 点击"获取"按钮，验证 `window.opener` 为 null
7. **违规标记**：发现 `target="_blank"` 无 `rel="noopener"` → P0 缺陷（安全漏洞）

### 步骤 6：预设切换归档-加载双步模式验证（AD-06，对应 F-REVIEW-243）
1. **applyPreset 双参数验证**：前端 `applyPreset` 函数必须同时传 `from_preset` 与 `to_preset`
2. **后端原子归档-加载验证**：后端 `apply-preset` 接口必须在同一事务中：① 归档 `from_preset` 当前 Key → ② 加载 `to_preset` 已存 Key
3. **脱敏 Key 返回验证**：后端必须返回 `api_key` 字段，值为脱敏格式（前3后3）
4. **前端使用脱敏值验证**：前端必须用后端返回的脱敏值更新 UI，禁止本地明文存储
5. **明文 Key 存储扫描**：grep 搜索，禁止 `localStorage.setItem(*.key)` / `sessionStorage.setItem(*.key)` 等明文存储
6. **活跃预设追踪验证**：前端必须维护 `activePresetKey` 状态，切换后立即更新
7. **运行时验证**：用 Playwright 触发 A→B 预设切换，验证 Key 归档/加载/脱敏值显示/刷新保持
8. **违规标记**：发现 applyPreset 单参数、明文 Key 存储、未返回脱敏值 → P0 缺陷

### 步骤 7：运行单元测试
1. **执行前端 vitest**：运行 `npx vitest run {vitest_args}` 执行预设切换相关前端单测
2. **执行后端 pytest**：运行 `pytest {pytest_args}` 执行后端预设切换单测
3. **测试用例覆盖验证**：检查 preset-switch 双参数契约、脱敏值回显、活跃预设追踪、明文 Key 存储禁令；apply-preset 接口原子归档-加载、脱敏值返回、状态回传
4. **失败定位**：若有用例失败，按 `key_files` 顺序读取对应源码定位根因

### 步骤 8：生成测试报告
输出 AI 服务测试连接与预设切换回归测试报告，包含：
1. **六项检查点状态**：AD-01~AD-06 静态扫描与运行时验证结果
2. **违规清单**：违规项的文件路径、行号、违规类型、严重等级（P0/P1）
3. **修复建议**：引用 coding-standards §2.25/§2.26 与对应的 B-REVIEW/F-REVIEW 详细描述
4. **单元测试状态**：前端 vitest / 后端 pytest 通过/失败统计、失败用例详情
5. **整体合规度**：六项检查点的合规百分比
6. **跨技能交叉验证**：与 `xianyu-backend-code-review` B-REVIEW-327~329 + `xianyu-frontend-code-review` F-REVIEW-241~243 的审查结果一致性
