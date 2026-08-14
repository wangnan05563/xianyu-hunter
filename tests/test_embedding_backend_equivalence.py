"""OnnxEmbeddingBackend 与参考后端（sentence-transformers / transformers）的等价性回归测试

目的：保证 ONNX Runtime 后端替换 sentence-transformers(torch) 后，向量化结果与生产
后端一致，知识库向量同分布、无需重建。

运行依赖：
- onnxruntime + tokenizers + numpy（ONNX 后端必需）
- 工件 src/xianyu_hunter/resources/embedding/
  - bge_small_zh.onnx（fp32，由 scripts/export_embedding_onnx.py 生成）
  - bge_small_zh.int8.onnx（int8 量化，由 scripts/quantize_embedding_onnx.py 生成）
  - tokenizer.json
  缺失则本测试整体 skip。

参考后端：
- sentence_transformers（与运行期 LocalEmbeddingBackend 完全一致，优先；自动探测）

判定阈值：
- fp32 ONNX vs ST：逐句余弦 > 0.999（单位向量，等价于点积）
- int8 ONNX vs fp32 ONNX：逐句余弦 > 0.99（量化有损但检索无感）

无 torch 保证：本测试 import onnx_embedding 后断言 torch 未被顶层拉入
（torch 仅在 ReferenceBackend / _ensure_loaded 内部延迟导入）。
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys

# 强制离线：参考后端只从本地缓存加载 bge-small-zh-v1.5，避免沙箱网络限制导致超时
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import numpy as np
import pytest

# 工件目录：与 scripts/export_embedding_onnx.py 默认输出一致
_EMBEDDING_ARTIFACT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "src", "xianyu_hunter", "resources", "embedding",
)
from xianyu_hunter.modules.chatbot.onnx_embedding import _ONNX_FP32, _ONNX_INT8
_ONNX_PATH = os.path.join(_EMBEDDING_ARTIFACT_DIR, _ONNX_FP32)
_INT8_PATH = os.path.join(_EMBEDDING_ARTIFACT_DIR, _ONNX_INT8)
_TOK_PATH = os.path.join(_EMBEDDING_ARTIFACT_DIR, "tokenizer.json")

# 混合语料（含 Latin 以验证 [UNK] 修复）：
# "iPhone" 在词表不全时会变 [UNK]，混合文本余弦掉到 ~0.92
_CORPUS = [
    "闲鱼上九成新的iPhone比官网便宜两百块",
    "周末去公园跑步，空气真好",
    "深度学习模型需要大量标注数据进行训练",
    "这台相机快门次数很少，配件齐全",
    "Python 是数据科学领域最流行的编程语言之一",
    "显卡价格最近回落了不少",
]
_QUERIES = [
    "二手 iPhone 多少钱",
    "怎么锻炼身体健康",
    "神经网络训练需要什么",
]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _st_importable() -> bool:
    """安全探测 sentence_transformers 是否可导入（不污染当前进程）

    本沙箱中 sentence_transformers 单独 import 偶发硬崩溃（rc=1 无输出），
    try/except 无法捕获。改用子进程探测，且先预热 torch/transformers（与导出脚本
    成功顺序一致，可规避该崩溃）；崩溃只杀子进程，不影响 pytest 主进程。
    设 XH_TEST_EMBED_REF=tf 可强制跳过 ST 探测。
    """
    if os.environ.get("XH_TEST_EMBED_REF") == "tf":
        return False
    try:
        r = subprocess.run(
            [sys.executable, "-c", "import torch, transformers; import sentence_transformers"],
            capture_output=True, timeout=120,
        )
        return r.returncode == 0
    except Exception:
        return False


def _load_reference_backend(model_name: str):
    """返回 (backend_callable, source)；backend_callable(texts)->list[np.ndarray]（已 L2 归一化）

    仅以 sentence_transformers 为参考后端——它与运行期 LocalEmbeddingBackend 完全一致，
    且 ONNX 工件即由 ST 的 base 模型导出，故 ONNX==ST 是构造上要保证的等价关系。

    注意：transformers.AutoTokenizer 对本模型词表不全（"iPhone"/"Python"→[UNK]），
    不能代表生产行为，故禁用其作为参考。若 ST 不可用，直接 skip 而非用 transformers 兜底。
    """
    if not _st_importable():
        pytest.skip(
            "sentence_transformers 不可用，无法作为等价参考"
            "（transformers 参考词表不全，已禁用；请在有 ST 的环境运行本测试）"
        )
    # 预热 torch/transformers 后再 import ST，规避本沙箱 ST 单独 import 崩溃
    import torch  # noqa: F401
    import transformers  # noqa: F401
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(model_name, device="cpu")
    def _st(texts):
        vecs = st.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [np.asarray(v, dtype=np.float64) for v in vecs]
    return _st, "sentence_transformers"


# 工件缺失则整体 skip（CI 无工件时保持绿灯）
# 只要有 fp32 或 int8 任一 ONNX + tokenizer 即可运行可用用例
pytestmark = pytest.mark.skipif(
    (not os.path.isfile(_ONNX_PATH) and not os.path.isfile(_INT8_PATH))
    or not os.path.isfile(_TOK_PATH),
    reason="缺少 ONNX embedding 工件（src/xianyu_hunter/resources/embedding/），"
           "请先运行 scripts/export_embedding_onnx.py 与 scripts/quantize_embedding_onnx.py",
)


@pytest.fixture(scope="module")
def onnx_backend():
    """fp32 ONNX 后端（固定文件名，避免被 int8 工件覆盖；对比 ST 用 0.999 阈值）"""
    from xianyu_hunter.modules.chatbot.onnx_embedding import OnnxEmbeddingBackend
    # 无 torch 顶层 import 保证：导入本模块后 torch 不应已被拉入
    assert "torch" not in sys.modules, "onnx_embedding 顶层不应 import torch"
    backend = OnnxEmbeddingBackend(
        onnx_dir=_EMBEDDING_ARTIFACT_DIR, model_filename=_ONNX_FP32
    )
    return backend


@pytest.fixture(scope="module")
def int8_backend():
    """int8 量化 ONNX 后端（固定文件名；对比 fp32 用 0.99 阈值）"""
    from xianyu_hunter.modules.chatbot.onnx_embedding import OnnxEmbeddingBackend
    if not os.path.isfile(_INT8_PATH):
        pytest.skip("缺少 int8 工件 bge_small_zh.int8.onnx，请先运行 quantize_embedding_onnx.py")
    backend = OnnxEmbeddingBackend(
        onnx_dir=_EMBEDDING_ARTIFACT_DIR, model_filename=_ONNX_INT8
    )
    return backend


@pytest.fixture(scope="module")
def fp32_backend():
    """与 int8 对比用的 fp32 基准（int8 测试需要两者都在场）"""
    from xianyu_hunter.modules.chatbot.onnx_embedding import OnnxEmbeddingBackend
    if not os.path.isfile(_ONNX_PATH):
        pytest.skip("缺少 fp32 工件 bge_small_zh.onnx，无法与 int8 对比")
    backend = OnnxEmbeddingBackend(
        onnx_dir=_EMBEDDING_ARTIFACT_DIR, model_filename=_ONNX_FP32
    )
    return backend


@pytest.fixture(scope="module")
def reference():
    backend_fn, source = _load_reference_backend("BAAI/bge-small-zh-v1.5")
    return backend_fn, source


def test_onnx_dimensions(onnx_backend):
    vecs = onnx_backend.embed_batch(_CORPUS[:1])
    assert len(vecs) == 1
    dim = onnx_backend.dimensions
    assert dim == len(vecs[0]) == 512, f"期望 512 维，实际 {dim}"


def test_tokenizer_full_vocab(onnx_backend):
    """验证分词器词表完整：'iPhone' 不应是 [UNK](id 100)"""
    from xianyu_hunter.modules.chatbot.onnx_embedding import _UNK_ID
    probe = onnx_backend._tokenizer.encode("iPhone 测试")
    assert _UNK_ID not in probe.ids, "ONNX tokenizer 词表不完整（iPhone 变 [UNK]）"


def test_per_sentence_cosine(onnx_backend, reference):
    """逐句余弦相似度 > 0.999（单位向量等价点积）"""
    ref_fn, source = reference
    onnx_vecs = [np.asarray(v, dtype=np.float64) for v in onnx_backend.embed_batch(_CORPUS)]
    ref_vecs = ref_fn(_CORPUS)
    assert len(onnx_vecs) == len(ref_vecs) == len(_CORPUS)
    min_cos = 1.0
    for i, (o, r) in enumerate(zip(onnx_vecs, ref_vecs)):
        c = _cosine(o, r)
        min_cos = min(min_cos, c)
        assert c > 0.999, f"句 {i} 余弦过低: {c:.6f}（参考后端={source}）"
    print(f"[equivalence] 最小逐句余弦={min_cos:.6f}（参考={source}）")


def test_top1_retrieval_consistency(onnx_backend, reference):
    """检索 top-1 索引在两种后端下一致"""
    ref_fn, source = reference
    corpus_onnx = [np.asarray(v, dtype=np.float64) for v in onnx_backend.embed_batch(_CORPUS)]
    corpus_ref = ref_fn(_CORPUS)
    q_onnx = [np.asarray(v, dtype=np.float64) for v in onnx_backend.embed_batch(_QUERIES)]
    q_ref = ref_fn(_QUERIES)
    for qi, (qo, qr) in enumerate(zip(q_onnx, q_ref)):
        top_onnx = int(np.argmax([_cosine(qo, c) for c in corpus_onnx]))
        top_ref = int(np.argmax([_cosine(qr, c) for c in corpus_ref]))
        assert top_onnx == top_ref, (
            f"查询 {qi} top-1 不一致：onnx={top_onnx}({_CORPUS[top_onnx]}) "
            f"ref={top_ref}({_CORPUS[top_ref]})（参考={source}）"
        )


def test_single_embed_matches_batch(onnx_backend):
    """单条 embed 与批量 embed 结果一致（接口兼容性）"""
    single = np.asarray(onnx_backend.embed(_CORPUS[0]), dtype=np.float64)
    batch = np.asarray(onnx_backend.embed_batch([_CORPUS[0]])[0], dtype=np.float64)
    assert _cosine(single, batch) > 0.9999


# ---------- int8 量化后端等价性（二次瘦身后运行期默认加载项） ----------

def test_int8_dimensions(int8_backend):
    vecs = int8_backend.embed_batch(_CORPUS[:1])
    dim = int8_backend.dimensions
    assert dim == len(vecs[0]) == 512, f"期望 512 维，实际 {dim}"


def test_int8_vs_fp32_cosine(int8_backend, fp32_backend):
    """int8 量化后端与 fp32 后端逐句余弦 > 0.99（量化有损但检索无感）"""
    i_vecs = [np.asarray(v, dtype=np.float64) for v in int8_backend.embed_batch(_CORPUS)]
    f_vecs = [np.asarray(v, dtype=np.float64) for v in fp32_backend.embed_batch(_CORPUS)]
    assert len(i_vecs) == len(f_vecs) == len(_CORPUS)
    min_cos = 1.0
    for i, (iv, fv) in enumerate(zip(i_vecs, f_vecs)):
        c = _cosine(iv, fv)
        min_cos = min(min_cos, c)
        assert c > 0.99, f"int8 vs fp32 句 {i} 余弦过低: {c:.6f}"
    print(f"[int8 equivalence] 最小逐句余弦(int8 vs fp32)={min_cos:.6f}")


def test_int8_top1_vs_fp32(int8_backend, fp32_backend):
    """int8 与 fp32 在检索 top-1 上一致（量化不影响最近邻排序）"""
    corpus_i = [np.asarray(v, dtype=np.float64) for v in int8_backend.embed_batch(_CORPUS)]
    corpus_f = [np.asarray(v, dtype=np.float64) for v in fp32_backend.embed_batch(_CORPUS)]
    q_i = [np.asarray(v, dtype=np.float64) for v in int8_backend.embed_batch(_QUERIES)]
    q_f = [np.asarray(v, dtype=np.float64) for v in fp32_backend.embed_batch(_QUERIES)]
    for qi, (qiv, qfv) in enumerate(zip(q_i, q_f)):
        top_i = int(np.argmax([_cosine(qiv, c) for c in corpus_i]))
        top_f = int(np.argmax([_cosine(qfv, c) for c in corpus_f]))
        assert top_i == top_f, (
            f"查询 {qi} int8/fp32 top-1 不一致：int8={top_i}({_CORPUS[top_i]}) "
            f"fp32={top_f}({_CORPUS[top_f]})"
        )


# ---------- 后端选择接线（EmbeddingService._build_local_backend） ----------

class _StubSettings:
    """避免 EmbeddingService 初始化触发 .env/keyring 副作用的占位配置"""
    embedding_base_url = ""
    embedding_engine = "st"
    embedding_api_key = ""
    openai_api_key = ""


def test_backend_selection_onnx_no_torch(monkeypatch):
    """embedding_engine='onnx' 时返回 OnnxEmbeddingBackend，且不新拉入 torch

    注意：torch 可能被同文件其他用例（ST 参考后端）先行导入，故只校验
    onnx 选择路径本身不会「新增」torch 到 sys.modules（torch 仅在 ST 路径需要）。
    模块级「import onnx_embedding 不拉 torch」由 test_onnx_dimensions 的 fixture 断言覆盖。
    """
    from xianyu_hunter.modules.chatbot.embedding_service import EmbeddingService
    from xianyu_hunter.modules.chatbot.onnx_embedding import OnnxEmbeddingBackend
    monkeypatch.setattr(
        "xianyu_hunter.modules.chatbot.embedding_service.get_settings",
        lambda: _StubSettings(),
    )
    svc = EmbeddingService(ai_usage=object(), model="x", dimensions=512)
    before = set(sys.modules)
    b = svc._build_local_backend("onnx")
    assert isinstance(b, OnnxEmbeddingBackend)
    # onnx 路径不得「新增」torch 顶层 import
    assert "torch" not in (set(sys.modules) - before)


def test_backend_selection_st(monkeypatch):
    """embedding_engine='st' 时返回 LocalEmbeddingBackend（sentence-transformers）"""
    if not _st_importable():
        pytest.skip("sentence_transformers 不可用，跳过 st 路径验证")
    import torch  # 预热，规避本沙箱 ST 单独 import 崩溃
    import transformers  # noqa: F401
    from xianyu_hunter.modules.chatbot.embedding_service import EmbeddingService
    from xianyu_hunter.modules.chatbot.local_embedding import LocalEmbeddingBackend
    monkeypatch.setattr(
        "xianyu_hunter.modules.chatbot.embedding_service.get_settings",
        lambda: _StubSettings(),
    )
    svc = EmbeddingService(ai_usage=object(), model="x", dimensions=512)
    b = svc._build_local_backend("st")
    assert isinstance(b, LocalEmbeddingBackend)
