# Per-Preset Credential Management 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「per-preset credential management」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 211：预设凭证独立槽位规范【强制】 🆕v4.42

**背景**：闲鱼猎人的 AI 服务配置支持多预设切换（OpenAI / DeepSeek / 智谱 / Moonshot / 通义千问 / 文心一言 / 豆包 / Agnes AI / Ollama），每个预设可能使用不同的 API Key。早期实现将所有预设共用同一个全局 API Key，切换预设时 Key 不跟随变化，导致目标服务的调用失败。

**问题**：凭证字段（API Key、Token 等）与预设绑定但未独立存储，切换预设时凭证丢失或不跟随。

**规范**：

1. 每个预设必须有独立的凭证存储槽位（storage slot），槽位名由 i_preset_key_name(preset_id) 等函数统一管理
2. 切换预设时的原子操作流程：
   - (a) 将当前预设的凭证保存到其槽位
   - (b) 从目标预设槽位加载凭证（存在则填充，不存在则为空）
   - (c) 更新 active config
3. 首次引入分槽存储时，必须将现有全局凭证迁移到原预设槽位（迁移发生在首次切换时，而非启动时）
4. 空字符串（凭证已删除）必须覆盖遗留值（如 .env 中的旧值），使用 is not None 守卫而非真值检查
5. 凭证存储/读取函数必须集中管理（如 secrets.py），禁止在路由层直接操作 keyring

**配置驱动**：参数在 config.yaml 的 credential_storage 节点管理，包含 per_preset_slots（预设槽位开关）、migration_on_first_switch（首次切换迁移）、empty_overrides_legacy（空串覆盖遗留值）。

**适用场景**：任何与预设/供应商绑定的凭证字段（AI API Key、通知渠道 Token、代理配置、隧道证书等）。

**不适用场景**：无凭证字段的纯展示表单、一次性凭证操作（如 OAuth 授权码交换）。

**判断信号**：
- grep "preset.*api_key\|api_key.*preset" src/ 发现预设与凭证关联但无独立槽位 → 违规
- grep "if .*_key:" 发现真值检查而非 is not None → 违规
- 路由层直接调用 keyring.set_password 而非通过 secrets 模块 → 违规

---

### step 212：配置变更响应回显规范【强制】 🆕v4.42

**背景**：前端 pplyPreset 调用 iApi.putConfig(patch) 后，后端返回 {ok: True, message: "...", ...config}。前端通过 setConfig((prev) => ({ ...prev, ...patch, ...saved })) 合并响应来保持 UI 与后端一致。但如果 mutation 响应只返回 {ok: true} 而不回显配置数据，前端需要额外发起 GET 请求才能同步状态。

**问题**：前端切换预设后，API Key 的返显值来自后端 PUT 响应中的脱敏值（****xxxx），但表单输入框需要的是实际值才能正确显示。脱敏值无法填充真实 Key 字段。

**规范**：

1. PUT/PATCH 配置端点必须回显完整更新后的状态（包括派生字段如 preset_id、脱敏凭证值）
2. 处理器应调用对应的 GET 处理器来构建响应，避免重复逻辑
3. 前端收到响应后应将 saved 数据合并到本地状态，确保 UI 与后端一致
4. 前端 pplyPreset 不应发送 pi_key 字段（因为预设切换时 Key 由后端从槽位恢复），但必须正确消费后端返回的脱敏值
5. 前端表单中的凭证输入框在预设切换后应保持空值（因为无法显示真实 Key），但 preset_id 和 ase_url 等字段必须正确更新

**配置驱动**：参数在 config.yaml 的 pi.mutation_response_echo 节点管理。

**适用场景**：所有配置类的 PUT/PATCH 端点。

**不适用场景**：纯操作型端点（如 /test-connection 只返回测试结果）。

**判断信号**：
- grep "return.*{ok.*message" src/ 发现 mutation 响应不含配置数据 → 违规
- 前端 PUT 后无 ...saved 合并逻辑 → 建议改进

---

### step 213：预设 ID 字面量类型规范【强制】 🆕v4.42

**背景**：AI 配置端点的 preset_id 参数有一组已知的有限值（openai / deepseek / zhipu / moonshot / qwen / ernie / doubao / agnes / ollama）。使用 str 类型允许任意字符串，无法在编译期捕获拼写错误。

**规范**：

1. 接受预设/供应商标识符的请求体必须使用 Literal 类型标注已知值
2. 新增预设时，必须同步更新 Literal 类型定义和前端 PRESETS 常量
3. 前后端预设 ID 必须严格一致，禁止动态映射

**配置驱动**：参数在 config.yaml 的 pi.literal_preset_ids 节点管理。

**适用场景**：所有接受预设/供应商标识符的 API 端点。

**不适用场景**：自由文本输入（如用户自定义标签）。

**判断信号**：
- grep "preset_id.*:.*str" src/ 发现使用 str 而非 Literal → 违规
- 前端 PRESETS 与后端 Literal 值不一致 → CRITICAL

---