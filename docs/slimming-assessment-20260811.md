# dist/ 与 .venv 瘦身评估

- 评估时间: 2026-08-11
- 工作空间: `D:\code\otherProjects\17_xianyu`
- 性质: **只读评估，未做任何删除/移动**。所有方案均标注风险与前置条件。

## 一、体积总览

| 目录 | 体积 | 角色 | 是否入 git |
| --- | --- | --- | --- |
| `dist/` | 2125 MB (2.07 GB) | PyInstaller 单文件夹交付物 + InnoSetup 安装包 | 否（.gitignore） |
| `.venv/` | 1084 MB (1.06 GB) | 开发/测试虚拟环境 | 否（.gitignore） |

两者均被 `.gitignore` 覆盖，**不影响仓库体积**；瘦身价值在于本地磁盘占用与分发体积。

## 二、dist/ 体积构成（Top 消费者）

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `XianyuHunter-Setup-v0.4.0.exe` | 478 MB | InnoSetup 安装包（含整个 `dist` 的压缩副本） |
| `_internal\torch\lib\torch_cpu.dll` | 291 MB | PyTorch CPU 推理后端 |
| `playwright_browsers\chromium-1223\chrome-win64\chrome.dll` | 270 MB | **完整 Chromium**（带 GUI） |
| `playwright_browsers\chromium_headless_shell-1223\...exe` | 192 MB | **无头 Chromium**（headless 用） |
| `models\bge-small-zh-v1.5\model.safetensors` | 91 MB | 向量化 embedding 模型 |
| `_internal\playwright\driver\node.exe` | 87 MB | Playwright Node 驱动 |
| `xianyu-hunter.exe` | 76 MB | 应用主程序 |
| `chromadb_rust_bindings.pyd` | 60 MB | Chroma 向量库绑定 |
| `onnxruntime` (dll+pyd) | ~34 MB | ONNX 推理（若未使用可剔除） |
| 其它 `.pyd`/`.dll`/`.py`（numpy/scipy/grpc/cryptography…） | 余量 | 依赖运行时 |

> 完整 Chromium 构建（含 dxcompiler/resources.pak/icudtl/libGLESv2 等）合计 ≈ 320 MB；headless-shell 构建合计 ≈ 200 MB。

## 三、.venv 体积构成（Top 消费者）

与 `dist/` **大量重叠**（torch_cpu.dll、node.exe、chromadb 等在 dist 与 venv 各一份——dist 是冻结副本，venv 是开发副本）。

| 类别 | 体积 | 是否运行时必需 |
| --- | --- | --- |
| `.dll` | 373 MB | 是（torch/numpy/scipy/onnxruntime 等） |
| `.py` (源码) | 269 MB | 是（包源码，正常） |
| `.pyd` | 198 MB | 是（编译扩展） |
| `.exe` | 97 MB | 是（python.exe + playwright node.exe） |
| `.lib` | 39.7 MB | **否**（torch.lib 28 MB 等为链接导入库，运行时不加载） |
| `.h` | 36.4 MB | **否**（头文件，编译期用） |
| `.pyc` | 20.5 MB | 否（字节码，可重建） |

## 四、瘦身方案（按风险/收益排序）

### 方案 A — 安装包移出 dist/ 【零风险 · 立即 · -478 MB】
`XianyuHunter-Setup-v0.4.0.exe` 是构建产物，runtime 只需 `dist/xianyu-hunter/` 文件夹。
把它放到 `releases/` 或独立构建输出目录即可，dist 立即减 478 MB。
**前置**：确认构建/分发流程不依赖它在 `dist/` 内（通常 InnoSetup 在 build 阶段生成，可改输出路径）。

### 方案 B — 按部署模式只保留一个 Chromium 构建 【中风险 · 条件 · -200~320 MB】
源码事实：默认 `headless=False`（`yaml_config.py:23`、`__main__.py:143` 需 GUI 桌面）→ 用**完整 Chromium**；`headless=True` → 用 **headless-shell**。
- 若部署固定 `headless=True`：可删完整 `chromium-1223`（≈320 MB）。
- 若部署固定 `headless=False`（默认）：可删 `chromium_headless_shell-1223`（≈200 MB）。
**前置**：必须与目标部署的 `browser.headless` 设置一致；需改 PyInstaller/playwright 打包（如 `PLAYWRIGHT_BROWSERS_PATH`、spec 中剔除对应目录）。**不可两套都删**。

### 方案 C — 剔除未使用的重依赖 【低风险 · -30~60 MB】
审计 `onnxruntime`(~34 MB) 等是否被实际 import；若为 PyInstaller 误打包，用 `--exclude-module` 去除；同理检查 `grpc`/各 `.pyd` 是否运行期必需。

### 方案 D — 模型量化 【质量权衡 · -40~50 MB】
`model.safetensors` 91 MB → int8 量化约减半。需回归验证 embedding 召回质量。

### 方案 E — PyTorch 轻量化替代 【高投入/高风险 · 数百 MB】
`torch_cpu.dll` 291 MB 是单文件最大项。若 embedding 可改用 onnxruntime + 量化 onnx 模型替代 sentence-transformers，可省数百 MB。属架构级改动，需充分验证。

### .venv 瘦身说明
`.venv` 为开发环境，实际瘦身应靠**重建**而非手工删：
- `pip install --no-cache-dir`；
- 拆分仅测试期使用的工具包；
- torch/playwright/chromadb 为核心依赖，体量无法回避。
- **不建议手工删除** `.lib`/`.h`/`.pyc`：它们不被运行时加载，但 `pip` 重装或某些构建会恢复/依赖，手工删易留隐患。真要减本地占用，直接重建一个 lean venv 更安全。

## 五、推荐执行顺序

1. **方案 A**（移出安装包）— 零风险、立竿见影，-478 MB。
2. **方案 B**（二选一 Chromium）— 条件性，-200~320 MB，需确认 headless 部署设置。
3. **方案 C/D**（剔冗余包 / 量化模型）— 评估级改动，-70~110 MB。
4. `.venv` 维持现状（gitignored），必要时重建 lean venv。

> 合计潜在可释放：约 **680 MB ~ 800 MB**（A+B），且均不影响运行时功能（前提：headless 设置匹配 + 安装包位置可接受）。

## 六、待用户确认后再执行项
- 安装包是否允许移出 `dist/`（构建流程依赖？）。
- 目标部署的 `browser.headless` 实际取值（决定删哪套 Chromium）。
- 是否接受模型量化/PyTorch 替代带来的质量与改动成本。
