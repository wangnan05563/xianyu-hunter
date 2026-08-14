# 安装包瘦身 — 架构与技术栈替换评估

- 评估时间: 2026-08-11
- 工作空间: `D:\code\otherProjects\17_xianyu`（xianyu-hunter v0.4.0）
- 性质: **只读/调研评估，未做任何改动**。聚焦"靠替换技术方案"实现瘦身。
- 安装包体积: `dist/` 2125 MB（含 InnoSetup 安装包 478 MB），其中 runtime 文件夹 `xianyu-hunter/` 约 1647 MB。

## 〇、核心结论（先说结论）

安装包肿的根因**不在前端**，而在 Python 的 ML/浏览器栈。前端 SPA 在 dist 中仅 ~13 MB，
换 UI 库/状态管理/构建工具对安装包几乎无影响（<5 MB）。**真正可替换、收益最大的三处**：

1. `sentence-transformers → torch`（**291 MB 单文件** + transformers/hf 系列）— embedding 后端，已有抽象。
2. `chromadb`（**60 MB** rust 绑定，并连带 onnxruntime 34 MB）— 向量库，单类可替换。
3. `playwright` 双 Chromium 构建（**完整 320 MB + headless 200 MB**）— 浏览器自动化，按部署模式二选一。

按"替换技术方案"路径，理论可释放 **约 570–690 MB**（torch 291 + chromadb 60 + 一套 Chromium 200~320），
且全部落在已隔离的 `modules/chatbot/` 与打包配置，**架构侵入面小**。

---

## 一、依赖与框架体积占比（dist/ 实测）

| 组件 | 体积 | 引入方 | 是否业务直接 import |
| --- | --- | --- | --- |
| `torch_cpu.dll` | 291 MB | sentence-transformers | 否（经 ST 间接） |
| 完整 Chromium 构建 | ~320 MB | playwright | 是（浏览器自动化核心） |
| 无头 Chromium 构建 | ~200 MB | playwright | 是（headless 模式） |
| `node.exe` (Playwright 驱动) | 87 MB | playwright | 是（驱动必需） |
| `model.safetensors` (bge-small) | 91 MB | 预置模型 | 是（embedding 权重） |
| `chromadb_rust_bindings.pyd` | 60 MB | chromadb | 否（经 chromadb 间接） |
| `onnxruntime` (dll+pyd) | ~34 MB | chromadb 传递依赖 | **否**（业务代码未直接用） |
| `xianyu-hunter.exe` + 应用代码 | ~76 MB | 主程序 | 是 |
| 其余（fastapi/uvicorn/sqlalchemy/numpy/scipy/grpc/cryptography/pyyaml + 81MB .py + 13MB js） | ~488 MB | 直接依赖 + 标准库 | 是 |
| **InnoSetup 安装包** | 478 MB | 构建产物 | —（dist 的压缩副本） |

> 体积集中度极高：**torch + 双 Chromium + chromadb + node ≈ 992 MB，占 runtime 的 60%**。

## 二、Python 后端 — 可替换模块（重点）

### 2.1 Embedding 后端：sentence-transformers → onnxruntime + 量化 ONNX 模型 【P0 · 高收益】
- **现状**：`modules/chatbot/local_embedding.py` 中 `LocalEmbeddingBackend` 调用
  `SentenceTransformer(model, device="cpu")`，模型 `bge-small-zh-v1.5`（91 MB）。
  这把整个 **torch（291 MB）+ transformers + huggingface_hub + tokenizers + hf_xet（合计 320 MB+）** 拉进包。
- **替换方案**：改用 **onnxruntime**（已因 chromadb 在包内，34 MB）加载 bge-small 的 **int8 量化 ONNX** 模型。
  社区已有 `bge-small-zh` 的 ONNX/quantized 版本，或直接用 `optimum` 导出。
- **架构影响**：仅改 `LocalEmbeddingBackend`（1 个类）的 `embed()` 实现，签名不变；
  `embedding_service.py` 与 `api_ai.py` 调用点无需动。`model.safetensors` 换成 `.onnx`（体积相近或更小，int8 后约减半）。
- **可行性 / 风险**：**高 / 低-中**。后端抽象已存在，onnxruntime 已在包内（零新增依赖）。
  风险在于 embedding 质量需回归（余弦相似度召回对齐），建议 A/B 对比 Top-K 一致性。
- **收益**：**−291 MB（torch）− transformers/hf 系列（数十 MB）**，净保留 onnxruntime 34 MB。
  **合计约 −320 MB**。

### 2.2 向量库：chromadb → sqlite-vec（或 numpy 暴力检索） 【P0 · 高收益 · 低风险】
- **现状**：`modules/chatbot/vector_store.py` 中 `VectorStore` 类 `import chromadb`，
  带来 `chromadb_rust_bindings.pyd`（60 MB）并连带 onnxruntime（34 MB，见 2.1 后变为故意保留）。
- **替换方案**：
  - **首选 `sqlite-vec`**：SQLite 扩展（数 MB），与现有 `aiosqlite`/SQLAlchemy 栈天然契合，local-first，
    支持 cosine/L2 相似查询，无需新进程/新服务。
  - **备选 numpy 暴力余弦**：若向量规模小（个人知识库通常数千~数万条），`np.dot` + 归一化即可，
    零额外依赖。
- **架构影响**：仅改 `VectorStore` 类的 `add()/get()/query()`（约 1 个文件），对外接口不变。
  持久化从 chromadb 目录改为 SQLite 表/扩展。
- **可行性 / 风险**：**高 / 低**。向量规模小、局部使用，迁移成本低；需一次性数据迁移脚本（旧 chromadb 集合 → 新表）。
- **收益**：**−60 MB（chromadb rust 绑定）**；onnxruntime 不再"浪费"，转为 2.1 的轻量引擎。

> **2.1 + 2.2 组合拳**：移除 torch（291）+ chromadb（60），保留 onnxruntime（34）作为 embedding 引擎。
> 净释放 **约 350 MB**，且消除两个最重的 C 扩展依赖，构建也更快更稳（collect_submodules 范围缩小）。

### 2.3 浏览器自动化：playwright 双 Chromium → 单构建 【P1 · 条件性 · −200~320 MB】
- **现状**：dist 同时打包 `chromium-1223`（完整，GUI）与 `chromium_headless_shell-1223`（无头）。
  源码事实：默认 `headless=False`（`yaml_config.py:23`、`__main__.py:143` 需 GUI 桌面）→ 用完整 Chromium；
  `headless=True` → 用 headless-shell。**两套二选一**。
- **替换方案**：按目标部署的 `browser.headless` 取值，打包时只保留对应一套 Chromium。
  - 固定 `headless=True`：删完整 Chromium（**−320 MB**）。
  - 固定 `headless=False`（默认）：删 headless-shell（**−200 MB**）。
- **架构影响**：改 PyInstaller/playwright 打包（如 `PLAYWRIGHT_BROWSERS_PATH`、spec 资源复制步骤），
  须与部署配置严格一致；**不可两套都删**（否则浏览器起不来）。
- **可行性 / 风险**：**中 / 中**。playwright 本身难替代（闲鱼为 JS 渲染 + 强反爬，浏览器必不可少；
  selenium/undetected-chromedriver 仍需浏览器且更重）。`node.exe` 87 MB 是 playwright 驱动，**无法去除**。
- **收益**：**−200~320 MB**（取决于保留哪套）。

### 2.4 构建环境依赖卫生 【P2 · 低风险 · 间接收益】
- **现状**：`requirements.txt` 是 `pip freeze` 全量锁，含 **pyproject.toml 未声明的死依赖**：
  `bottle`、`pythonnet`/`clr_loader`、应仅 dev 的 `pytest`/`pytest-asyncio`/`rich` 等。
  源码核验：`import bottle`/`import clr`/`pythonnet` 在 `src/` 中**无任何调用**。
- **替换方案**：PyInstaller 构建环境应以 `pyproject.toml` 直接依赖为准（剔除 bottle/pythonnet 等），
  避免把死依赖装进 venv / 冻结进包。
- **架构影响**：仅构建流程；运行时无影响。
- **收益**：主要是 `.venv` 减负（~数十 MB），对 `dist` 影响有限（PyInstaller 按 import 图收集，死依赖通常不被打包，
  但干净的环境能避免误收集与构建不确定性）。

## 三、前端（React SPA）— 你点名的类别，但体积贡献极小

> 前端 SPA 在 dist 中仅 **~13 MB**（vite 构建产物）。下表评估你要求的"UI 库/工具库/状态管理/构建工具"，
> 但**诚实结论**：换它们对安装包几乎无感，优先级应远低于第二、三节。仅当同时追求"运行时更轻/更快"才值得做。

| 类别 | 现状 | 更轻替代 | 安装包收益 | 架构影响 / 可行性 |
| --- | --- | --- | --- | --- |
| **UI 库** | `antd` 5.21（React） | `shadcn/ui`(Radix+Tailwind) / `Mantine` / `Arco` | <3 MB（已 tree-shake） | 中：需重写组件，工作量大、收益小。**不建议仅为瘦身** |
| **状态管理** | `zustand` 4.5 | （已是最轻量，优于 Redux/MobX） | — | **保持**。无需替换 |
| **构建工具** | `vite` 5.4 | （已是最优，优于 webpack/CRA） | — | **保持**。无需替换 |
| **图表库** | `echarts` 5.5 | `uPlot` / `Chart.js`（若图表简单） | <2 MB | 低-中：仅当图表类型简单时值得 |
| **创意编码** | `p5` 2.3 | 移除（若非必需）或按需动态 import | <1 MB | 低：确认是否实际使用，未用则删 |
| **Markdown** | `react-markdown`+`highlight.js`+`rehype`+`remark` | `marked`+`Shiki`(或 Prism) | <1 MB | 低：聊天渲染，影响小 |
| **流程/图** | `react-flow-renderer` 10.3 | 自绘 SVG（若图简单） | <1 MB | 低-中：仅当 DAG 展示简单 |

**前端结论**：状态管理（zustand）与构建工具（vite）已是业界最轻选择，**保持不动**；
UI 库（antd）替换收益渺小却代价高昂，**不推荐仅为瘦身**；仅 `p5`（若未用）、`echarts→uPlot` 属"顺手可优化"项。

## 四、替换对架构的影响与可行性总评

| 序号 | 替换项 | 净释放 | 改动面 | 可行性 | 风险 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- |
| 2.1 | ST→onnxruntime(ONNX bge) | ~320 MB | 1 类（local_embedding） | 高 | 低-中（质量回归） | **P0** |
| 2.2 | chromadb→sqlite-vec | ~60 MB | 1 类（vector_store） | 高 | 低 | **P0** |
| 2.3 | playwright 单 Chromium | 200~320 MB | 打包配置 | 中 | 中（须配 headless） | **P1** |
| 2.4 | 构建环境去死依赖 | 数十 MB(.venv) | 构建流程 | 高 | 低 | **P2** |
| 3.x | 前端 UI/图表替换 | <5 MB | 大量组件 | 中 | 低 | **P3（不推荐仅为瘦身）** |

- **架构侵入面小**：2.1 与 2.2 都已被既有后端抽象（`LocalEmbeddingBackend` / `VectorStore`）隔离，
  替换是"换实现、不变接口"，对 `embedding_service.py` / `api_ai.py` / RAG 编排层无感。
- **依赖收敛正收益**：移除 torch + chromadb 后，onnxruntime 成为唯一重引擎，包体、构建时间、C 扩展冲突面同步下降。
- **不可替换项**：playwright（浏览器自动化核心，node.exe 不可去）、fastapi/uvicorn/sqlalchemy（业务骨架）、
  `model.safetensors`（embedding 权重，可量化但不可删）、`xianyu-hunter.exe`（主程序）。

## 五、优先级排序与建议执行顺序

1. **P0 — embedding 后端替换（2.1）**：最大单点收益（~320 MB），抽象已就绪，onnxruntime 已在包内。
   先导出/获取 bge-small 的 int8 ONNX 模型，改写 `LocalEmbeddingBackend.embed()`，做 Top-K 召回回归。
2. **P0 — 向量库替换（2.2）**：紧随其后（~60 MB），改 `VectorStore` 为 sqlite-vec，编写旧数据迁移脚本。
   两项完成后 torch + chromadb 彻底出局，**净 −350 MB**，且 onnxruntime"转正"。
3. **P1 — playwright 单 Chromium（2.3）**：确认目标部署 `browser.headless`，打包只留一套（−200~320 MB）。
4. **P2 — 构建环境去死依赖（2.4）**：以 pyproject 直接依赖构建，剔除 bottle/pythonnet/pytest 等。
5. **P3 — 前端**：保持 zustand/vite；仅清理未用的 `p5`、按需评估 `echarts→uPlot`；**不为瘦身替换 antd**。

> 若 P0+P1 全部落地，理论安装包 runtime 可从 ~1647 MB 降至 **约 1000~1100 MB**（−35%~40%），
> 加安装包移出 dist（上一轮方案 A，−478 MB）则整体交付物下降更显著。
