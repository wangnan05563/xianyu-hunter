# P0 embedding 后端替换可行性验证报告

- 日期：2026-08-12
- 目标：验证用 `onnxruntime` 替代 `sentence-transformers`(torch) 做本地 embedding 时，
  **质量是否等价** 与 **运行时能否彻底移除 torch**
- 结论：**可行，且质量逐位等价（cosine=1.0），torch 可完全移除**

---

## 1. 验证环境

| 项 | 值 |
|---|---|
| 模型 | `BAAI/bge-small-zh-v1.5`（512 维，~95MB，已缓存在本地 HF cache） |
| 当前后端 | `backend/xianyu_hunter/modules/chatbot/local_embedding.py::LocalEmbeddingBackend`（sentence-transformers，CPU） |
| 项目 venv 已装 | `sentence_transformers` / `transformers` / `torch` / `onnxruntime` / `numpy` |
| 验证新增安装 | `onnx`（仅用于导出，运行期不需要） |
| 模型流水线（来自 `modules.json` + `1_Pooling/config.json`） | `Transformer → Pooling(CLS token) → Normalize(L2)` |

> **关键发现**：bge 的 ST 流水线**不是** mean pooling，而是 **CLS-token pooling + L2 归一化**（末尾有 `2_Normalize` 模块）。第一版验证用 mean pooling 得到 cosine≈0.86，改用 CLS+L2 后立刻到 1.0。

---

## 2. 验证方法

### 2.1 ONNX 导出（构建期，torch 可用）
用 `torch.onnx.export`（legacy 导出器，`dynamo=False`，避免拉 `onnxscript`）把
`transformer + CLS pooling + L2 normalize` 导出为**单一 ONNX 图**：

```
输入: input_ids[int64, B, S], attention_mask[int64, B, S]
输出: embedding[float32, B, 512]   # 已含 L2 归一化
opset=14, dynamic_axes(B,S)
```

导出源码见 `_onnx_probe/run_probe.py`（验证产物，完成后已清理）。

### 2.2 质量对比（运行时，可无 torch）
- 参考：sentence-transformers `encode(normalize_embeddings=False)` —— 实际经模型内置 Normalize 模块已归一化
- 候选：ONNX + 分词器推理
- 指标：逐句余弦相似度 + 检索 top-1 一致性（8 条文档 + 3 条 query）

### 2.3 分词器（torch-free 运行期的关键坑）
裸 `tokenizers.Tokenizer.from_file(tokenizer.json)` 的词表**不完整**，`iPhone` 等
Latin token 会被当成 `[UNK]`(id 100)，导致混合文本余弦掉到 0.92。

**修复（构建期一次性）**：用完整 `vocab.txt`（21128 词）重建 `tokenizers.WordPiece`：
```python
from tokenizers import Tokenizer, models, pre_tokenizers, normalizers, processors
vocab = {w.strip(): i for i, w in enumerate(open("vocab.txt", encoding="utf-8"))}
tok = Tokenizer(models.WordPiece(vocab, unk_token="[UNK]"))
tok.normalizer = normalizers.BertNormalizer(lowercase=True, strip_accents=True)
tok.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
tok.post_processor = processors.TemplateProcessing(
    single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 101), ("[SEP]", 102)])
```

---

## 3. 验证结果

| 指标 | 结果 |
|---|---|
| ONNX 导出耗时 | 1.5s |
| ONNX 文件体积 | **90.5 MB**（≈ model.safetensors，无额外膨胀） |
| 逐句余弦(ST, ONNX) | **min=1.00000 / mean=1.00000** |
| 检索 top-1 一致性 | **3/3 完全一致** |
| 运行时是否加载 torch | **False**（仅 `onnxruntime` + `tokenizers` + `numpy`） |
| 现有 chromadb 向量兼容性 | **兼容**（ONNX 图含 L2 归一化，与旧向量同分布，无需重建知识库） |

> 注：推理耗时与 sentence-transformers 同量级（11 句 ~55ms），无性能退化。

---

## 4. 对 `LocalEmbeddingBackend` 的改造方案

**接口不变，仅换实现**——`embed` / `embed_batch` / `dimensions` 三个公开方法签名保持不变，
调用方（`EmbeddingService`）零改动。

```
构建期（CI / 打包机，torch 可用）:
  - torch.onnx.export 生成 bge_small_zh.onnx
  - 由 vocab.txt 生成 tokenizer 工件 (tokenizer.json / vocab.txt)
  -> 产物随包发布到 resources/embedding/

运行期（用户机器）:
  LocalEmbeddingBackend(onnx_path, tokenizer_path)
    load: onnxruntime.InferenceSession + tokenizers.Tokenizer
    embed(text): tokenize -> onnxruntime -> [已归一化向量]
```

依赖变化：
- **移除**：`torch`(291MB) + `sentence-transformers` + `transformers`(重，且会拖入 torch)
- **保留**：`onnxruntime`（本就因 chromadb 依赖已在包内）、`tokenizers`（Rust，轻）、`numpy`
- **净收益**：≈ **290–320 MB**（见下）

---

## 5. 收益测算（安装包 / dist 维度）

| 依赖 | 体积 | 处置 |
|---|---|---|
| `torch_cpu.dll` 等 torch 产物 | ~291 MB | **移除** |
| `sentence-transformers` + `transformers` 纯 Python/资源 | ~30 MB | **移除** |
| `onnxruntime` | ~34 MB | 已在包内（chromadb 依赖），**不增不减** |
| `tokenizers`(Rust) | ~5 MB | 已随 transformers 存在，保留 |
| 新增 `bge_small_zh.onnx` | +90.5 MB | 替换原 `model.safetensors`(~95MB)，**净额≈0** |

**P0 净释放 ≈ 320 MB**（与架构评估报告 `arch-slimming-assessment-20260811.md` 一致）。

---

## 6. 风险与遗留

1. **量化可再减体积**：当前 ONNX 为 fp32(90.5MB)。若改为 `int8` 量化（ONNX Runtime 原生支持
   `quantize_dynamic`），体积可再降 ~40–50MB、推理更快；需回归验证中文召回无退化。
2. **回归测试必须做**：实现后跑现有 `tests/` 中 embedding / 检索相关用例，确认 top-k 排序与
   旧后端一致（本验证已证明单条 cosine=1.0，整库层面仍建议回归）。
3. **模型切换兼容**：若日后换用 `bge-large` / `bge-m3`，导出脚本需参数化（维度、是否多池化），
   但改造模式不变。
4. **构建期仍要 torch**：导出 ONNX 与生成分词器需在构建环境用 torch/transformers；这没问题，
   因为构建机本来就有完整依赖，只是**最终分发包**不再包含 torch。

---

## 7. 下一步建议

1. 落地 `OnnxEmbeddingBackend`（沿用 `LocalEmbeddingBackend` 的抽象，新增一个后端类，
   通过配置 `kb.embedding_backend` 切换，而非删除旧类，便于灰度）。
2. 在 `scripts/` 增加构建期导出脚本（生成 onnx + tokenizer 工件），接入 PyInstaller 打包流程。
3. 加一条 `pytest` 断言：用同一批文本分别经 ST 与 ONNX 后端，top-1 检索结果一致。
4. 可选：`quantize_dynamic` 量化 ONNX 做体积二次优化。

> 验证脚本与中间产物位于 `_onnx_probe/`（已清理，不进入仓库）。本报告的导出命令与分词器构建
> 片段即为实现蓝本。

---

## 8. 实现已落地（2026-08-12 续）

可行性验证通过后，已按 §7 建议完成落地实现，并经等价性回归测试验证。

### 8.1 新增 / 修改文件

| 文件 | 变更 | 说明 |
|---|---|---|
| `backend/xianyu_hunter/modules/chatbot/onnx_embedding.py` | 新增 | `OnnxEmbeddingBackend`：与 `LocalEmbeddingBackend` 同接口（`embed`/`embed_batch`/`dimensions`），无 torch 依赖（onnxruntime/tokenizers/numpy 均延迟导入）。 |
| `scripts/export_embedding_onnx.py` | 新增 | 构建期导出脚本：生成 `bge_small_zh.onnx`(90.5MB) + `tokenizer.json` + `meta.json`；优先 sentence-transformers，缺失时回退 transformers。 |
| `backend/xianyu_hunter/config.py` | 修改 | 新增 `embedding_engine: str = "st"`（"st"=sentence-transformers / "onnx"=ONNX Runtime）。 |
| `backend/xianyu_hunter/modules/chatbot/embedding_service.py` | 修改 | `_get_local_backend` 按 `embedding_engine` 选择后端；首选引擎不可用时回退另一引擎（构建/运行配置不匹配也不崩）。 |
| `xianyu-hunter.spec` | 修改 | 读取 `XH_EMBEDDING_ENGINE`：`onnx` 模式 exclude `torch`/`sentence_transformers`/`transformers`（保留 `tokenizers`），不收集 `sentence_transformers` 子模块。 |
| `scripts/build-exe.ps1` | 修改 | 新增 `-EmbeddingEngine` 参数（默认 `st`）；onnx 模式跳过 `sync-sentence-transformers` 与重模型下载，改为复制 `resources/embedding` 工件。 |
| `tests/test_embedding_backend_equivalence.py` | 新增 | 等价性回归：逐句余弦 > 0.999、top-1 一致、维度=512、分词器词表完整、后端选择接线。工件缺失时整体 skip。 |

### 8.2 构建 onnx 瘦身包

```powershell
# 1) 生成 ONNX + tokenizer 工件（需 torch，构建机已有完整依赖）
python scripts/export_embedding_onnx.py
#    -> backend/xianyu_hunter/resources/embedding/{bge_small_zh.onnx, tokenizer.json, meta.json}

# 2) 打包（排除 torch，约 -320MB）
powershell -File scripts/build-exe.ps1 -EmbeddingEngine onnx
```

运行期启用 onnx 后端：在 `.env` 设 `EMBEDDING_ENGINE=onnx`（默认 `st`，行为不变）。
**健壮性**：即使构建为 onnx 但配置仍为 `st`（或反），`EmbeddingService` 会在首选引擎不可用时
自动回退另一引擎，不会因配置/构建不匹配而崩溃。

### 8.3 分词器关键结论（修正 §2.3）

§2.3 提到「用 vocab.txt 重建」；实际实现用 `st.tokenizer.get_vocab()`（完整 21128 词，含
`iphone=8210`）重建 `tokenizers.WordPiece`，与生产 sentence-transformers 分词器**逐 token 一致**
（已用 6 条中英混合语料逐句比对：`ALL_MATCH_ST=True`）。

> **重要坑（验证中发现）**：`transformers.AutoTokenizer.from_pretrained(...)` 对本模型词表不全，
> 会把 `iPhone`/`Python` 等 Latin token 标成 `[UNK]`(id 100)，**不能**代表生产行为，因此等价性
> 测试的参考后端**只用 sentence-transformers**（与生产 `LocalEmbeddingBackend` 完全一致），
> 禁用 transformers 兜底。ONNX 图本身经「相同 token id」验证 cosine=1.000000，质量无折扣。

### 8.4 回归测试结果

`tests/test_embedding_backend_equivalence.py` 本地运行 **10 passed**：

| 用例 | 验证点 |
|---|---|
| `test_onnx_dimensions` | fp32 输出维度 = 512；`import onnx_embedding` 不拉 torch |
| `test_tokenizer_full_vocab` | `iPhone` 非 `[UNK]`（词表完整） |
| `test_per_sentence_cosine` | ST vs fp32 ONNX 逐句余弦 > 0.999（实测 = 1.0） |
| `test_top1_retrieval_consistency` | 检索 top-1 索引一致（3/3） |
| `test_single_embed_matches_batch` | 单条与批量 embed 一致 |
| `test_int8_dimensions` | int8 输出维度 = 512 |
| `test_int8_vs_fp32_cosine` | int8 vs fp32 逐句余弦 > 0.99（实测 min≈0.995，量化无感） |
| `test_int8_top1_vs_fp32` | int8 与 fp32 检索 top-1 一致 |
| `test_backend_selection_onnx_no_torch` | `embedding_engine=onnx` → `OnnxEmbeddingBackend`，不新拉 torch |
| `test_backend_selection_st` | `embedding_engine=st` → `LocalEmbeddingBackend` |

> fp32 用例固定加载 `bge_small_zh.onnx`（不被 int8 工件覆盖）；int8 用例固定加载
> `bge_small_zh.int8.onnx` 并与 fp32 对比，阈值放宽至 0.99（量化有损但检索无感）。

### 8.5 工件与提交说明

- `backend/xianyu_hunter/resources/embedding/` 的**生成物**已加入 `.gitignore`（不入库）：
  `*.onnx`（fp32 90.5MB / int8 ~55MB）、`tokenizer.json`、`meta.json` 被忽略；
  目录本身不忽略，由 `.gitkeep`（含用法说明）占位入库，clone 后结构可见但约 150MB 二进制不进仓库。
  工件由 `export_embedding_onnx.py`（fp32）与 `quantize_embedding_onnx.py`（int8）在开发/构建期生成；
  等价性测试在工件缺失时整体 skip，不影响 CI 绿。
- 默认（st）构建与运行行为**完全不变**；onnx 为可选的瘦身选项。

## 9. int8 量化二次瘦身（已落地）

在 fp32 ONNX（§8）基础上，再用 `onnxruntime.quantization.quantize_dynamic` 对权重做 int8
动态量化，进一步减小运行期模型体积与内存占用。

### 9.1 量化脚本与工件

- 新增 `scripts/quantize_embedding_onnx.py`：对 `bge_small_zh.onnx` 做 `QInt8` 动态量化，
  仅量化权重 `MatMul`/`Gemm`（per_channel，`reduce_range=False`），输出 `bge_small_zh.int8.onnx`。
  幂等（`--force` 覆盖）；`--verify` 自检 int8 vs fp32 余弦。
- 运行期 `OnnxEmbeddingBackend` 优先加载 `bge_small_zh.int8.onnx`，缺失则回退 fp32
  （`model_filename` 参数可强制指定某文件，等价性测试借此固定 fp32 基准）。

### 9.2 实测收益与质量

| 工件 | 体积 | 说明 |
|---|---|---|
| `bge_small_zh.onnx`（fp32） | 90.5 MB | 与 ST 余弦 = 1.0 |
| `bge_small_zh.int8.onnx`（int8） | **54.6 MB** | 省 35.8 MB（39.6%） |
| int8 vs fp32 余弦 | min=0.9952 / mean=0.9957 | 量化有损但检索无感（top-1 一致） |

### 9.3 构建集成

`scripts/build-exe.ps1 -EmbeddingEngine onnx` 现流程：
0. **5.5.0 onnx 依赖自检（守卫）**：进 onnx 分支第一步先 `import onnx` 自检；
   若缺失（最常见于 `-SkipDeps` 模式跳过了 step 1 安装），立即报错并提示
   `pip install -r requirements-build.txt`，**提前失败**而非跑到 5.5.2 量化时才报含糊错。
1. step 1 已随 `pip install -e ".[build]"` 预装 onnx（构建期 extra，含 onnx）；
   fp32 缺失则运行 `export_embedding_onnx.py` 生成（需 torch，走 `.venv-build`）。
2. int8 缺失 → 直接运行 `quantize_embedding_onnx.py`（onnx 已在 step 1 预装，不再懒装）。
3. **仅复制 int8 onnx + tokenizer.json + meta.json 进 `dist`**（fp32 不进包，进一步瘦身）；
   运行期优先 int8。

### 9.4 关键坑（量化）

- `onnxruntime.quantization.quantize_dynamic` 在 1.x 已移除 `optimize_model` 参数（默认内部优化），
  调用时勿传该参数，否则 `TypeError`。
- 量化需要 `onnx` 包（PyInstaller 收集期不做量化，故不影响 dist 内运行）。`onnx` 在
  `pyproject.toml` 的 `[project.optional-dependencies].build` 声明；build-exe **step 1** 即
  `pip install -e ".[build]"` 预装 onnx（st / onnx 两种模式都会装，不再在 onnx 分支懒装）。
  `requirements-build.txt` 保留为独立安装方式（`pip install -r requirements-build.txt`），与 `.[build]` 等价。
- **`-SkipDeps` 模式不装 onnx**：该模式跳过 step 1 依赖安装，`.venv-build` 里可能根本没有 `onnx`，
  导致 5.5.1/5.5.2 失败。5.5.0 自检会在进入 onnx 分支时立即拦截并给出明确指引
  （去掉 `-SkipDeps` 重建，或手动 `pip install -r requirements-build.txt`）。
- 量化仅动权重，图内 CLS pooling + L2 归一化（`Div`/`ReduceL2`/`Sqrt`）保持 fp32，输出语义不变。
- 仅量化 `MatMul`/`Gemm` 即可获得 ~40% 体积下降；`Gather`（embedding 查表）体量小且量化易掉点，不量化。

### 9.5 用法

```powershell
# 开发/构建期生成 int8 工件（fp32 由 export 脚本先生成）
python scripts/export_embedding_onnx.py
python scripts/quantize_embedding_onnx.py --verify

# 打包（排除 torch，且只发 int8 模型，约 -320MB 后再省 ~36MB）
powershell -File scripts/build-exe.ps1 -EmbeddingEngine onnx
```

> 注：int8 量化是**可选的二次瘦身**。如某目标 CPU 对 int8 算子支持不佳导致异常，可在
> `build-exe.ps1` onnx 分支改为复制 fp32（运行期会自动优先 int8、回退 fp32），或设
> `OnnxEmbeddingBackend(model_filename="bge_small_zh.onnx")` 强制 fp32。
