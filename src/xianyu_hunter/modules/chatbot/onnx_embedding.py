"""OnnxEmbeddingBackend：基于 ONNX Runtime 的本地向量化后端

动机（安装包瘦身 P0）：
- 原 LocalEmbeddingBackend 用 sentence-transformers → 拉入 torch（~291MB）。
- bge-small-zh-v1.5 导成 ONNX 后，运行时只需 onnxruntime + tokenizers（Rust）+ numpy，
  彻底不依赖 torch / sentence-transformers / transformers，安装包可减 ~320MB。

与 LocalEmbeddingBackend 的差异：
- 权重来自导出产物（bge_small_zh.onnx + tokenizer.json），不是 HuggingFace 在线/缓存模型。
- 运行期优先加载 int8 量化版 bge_small_zh.int8.onnx（更小/更省内存），缺失则回退 fp32。
- 图内已完成 CLS pooling + L2 归一化，与 sentence-transformers 的
  modules.json / 1_Pooling 流水线一致 → 与旧 chromadb 向量同分布，无需重建知识库。

接口保持兼容：embed / embed_batch / dimensions 与 LocalEmbeddingBackend 一致，
调用方（EmbeddingService）零改动。

无 torch 保证：本模块在顶层不 import 任何 ML 框架；onnxruntime / tokenizers / numpy
均在 _ensure_loaded 内延迟导入。当 EMBEDDING_ENGINE != "onnx" 时本类根本不会被实例化。
"""
from __future__ import annotations

import os
import threading
from typing import Any

from loguru import logger

from xianyu_hunter.paths import get_app_dir

# ONNX 图输入/输出名（须与 scripts/export_embedding_onnx.py 导出时一致）
_ONNX_INPUT_IDS = "input_ids"
_ONNX_INPUT_MASK = "attention_mask"
_ONNX_OUTPUT = "embedding"
_ONNX_FP32 = "bge_small_zh.onnx"
_ONNX_INT8 = "bge_small_zh.int8.onnx"
_MAX_LEN = 512
_UNK_ID = 100  # [UNK]，用于检测分词器词表不完整（见导出脚本说明）


def _locate_artifact_dir(explicit: str | None) -> str:
    """定位 ONNX + tokenizer 工件目录，按优先级：

    1. 显式 EMBEDDING_ONNX_DIR / onnx_dir 参数
    2. 模块相对：<package>/resources/embedding（开发态，CWD 无关，最稳）
    3. 程序安装目录：get_app_dir()/resources/embedding（打包态，build-exe.ps1 复制）

    目录只需包含 fp32 或 int8 任一 ONNX 文件即可被认定（瘦身时可能只发 int8）。
    """
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    here = os.path.dirname(os.path.abspath(__file__))
    # modules/chatbot -> xianyu_hunter -> resources/embedding
    candidates.append(os.path.join(here, "..", "..", "resources", "embedding"))
    candidates.append(str(get_app_dir() / "resources" / "embedding"))
    for c in candidates:
        if os.path.isfile(os.path.join(c, _ONNX_FP32)) or os.path.isfile(os.path.join(c, _ONNX_INT8)):
            return os.path.abspath(c)
    # 未找到时返回第一个候选（让上层报更清晰的错误）
    return os.path.abspath(candidates[0])


def _resolve_model_path(artifact_dir: str, model_filename: str | None) -> str:
    """解析实际加载的 ONNX 文件名。

    - model_filename 显式指定（测试可固定 fp32）：直接用它。
    - 否则优先 int8（已量化，体积更小、内存更省）；int8 缺失则回退 fp32。
    """
    if model_filename:
        return os.path.join(artifact_dir, model_filename)
    int8 = os.path.join(artifact_dir, _ONNX_INT8)
    if os.path.isfile(int8):
        return int8
    return os.path.join(artifact_dir, _ONNX_FP32)


class OnnxEmbeddingBackend:
    """ONNX Runtime 包装类，提供同步 embed 接口（与 LocalEmbeddingBackend 同签名）

    与 sentence-transformers 的区别：模型权重来自本地 ONNX 文件，不联网、不依赖 torch。
    """

    def __init__(
        self,
        model_name: str | None = None,
        onnx_dir: str | None = None,
        model_filename: str | None = None,
    ) -> None:
        # model_name 保留仅为日志/兼容；实际加载来自 onnx_dir 工件
        self._model_name = model_name or "bge-small-zh-v1.5(onnx)"
        self._onnx_dir = _locate_artifact_dir(onnx_dir)
        # model_filename=None → 运行期优先 int8；测试可固定为 bge_small_zh.onnx
        self._model_path = _resolve_model_path(self._onnx_dir, model_filename)
        self._session: Any = None
        self._tokenizer: Any = None
        self._lock = threading.Lock()
        self._dim: int = 0

    @property
    def dimensions(self) -> int:
        """返回模型实际输出维度（首次 embed 后可用）"""
        return self._dim

    def _ensure_loaded(self) -> None:
        """懒加载 ONNX session + tokenizer（线程安全，与 LocalEmbeddingBackend 一致）

        延迟导入 onnxruntime / tokenizers / numpy，确保本模块在 torch 缺失环境也能 import。
        """
        if self._session is not None:
            return
        with self._lock:
            if self._session is not None:
                return
            import onnxruntime as ort
            from tokenizers import Tokenizer

            onnx_path = self._model_path
            tok_path = os.path.join(self._onnx_dir, "tokenizer.json")
            if not os.path.isfile(onnx_path):
                raise RuntimeError(
                    f"ONNX embedding 模型不存在: {onnx_path}。请先运行 "
                    "scripts/export_embedding_onnx.py 与 scripts/quantize_embedding_onnx.py 生成工件，"
                    "或确认 EMBEDDING_ONNX_DIR 指向正确目录。"
                )
            if not os.path.isfile(tok_path):
                raise RuntimeError(f"ONNX tokenizer 不存在: {tok_path}。请先运行导出脚本。")

            logger.info(f"Loading ONNX embedding model from: {onnx_path}")
            # CPUExecutionProvider：与 sentence-transformers CPU 推理一致
            self._session = ort.InferenceSession(
                onnx_path, providers=["CPUExecutionProvider"]
            )
            self._tokenizer = Tokenizer.from_file(tok_path)

            # 自检：用一条含 Latin 的文本验证分词器词表完整（"iphone" 应为 8210 而非 [UNK]=100）
            # 若词表不全，余弦会掉到 ~0.92，需重建 tokenizer（见导出脚本）。
            probe = self._tokenizer.encode("iPhone 测试")
            if _UNK_ID in probe.ids:
                logger.warning(
                    "ONNX tokenizer 词表疑似不完整（含 [UNK]），embedding 质量可能下降；"
                    "请用 scripts/export_embedding_onnx.py 重新导出 tokenizer.json。"
                )

            # 通过一次 dummy 推理确定输出维度（便宜，且避免硬编码维度）
            self._dim = len(self._run([""])[0])
            logger.info(f"ONNX embedding model loaded: dim={self._dim}")

    def _tokenize_batch(self, texts: list[str]) -> tuple[Any, Any]:
        """用 tokenizers 批量分词并 pad 到本批最长（与 sentence-transformers padding=True 一致）"""
        import numpy as np

        encs = self._tokenizer.encode_batch(texts)
        max_len = min(_MAX_LEN, max((len(e.ids) for e in encs), default=1))
        ids: list[list[int]] = []
        masks: list[list[int]] = []
        for e in encs:
            seq = e.ids[:max_len]
            pad = max_len - len(seq)
            ids.append(seq + [0] * pad)
            masks.append([1] * len(seq) + [0] * pad)
        return np.array(ids, dtype=np.int64), np.array(masks, dtype=np.int64)

    def _run(self, texts: list[str]) -> list[list[float]]:
        """批量推理：一次 ONNX 调用完成整批，效率高于逐条"""
        input_ids, attention_mask = self._tokenize_batch(texts)
        res = self._session.run(
            None,
            {_ONNX_INPUT_IDS: input_ids, _ONNX_INPUT_MASK: attention_mask},
        )[0]
        return [r.tolist() for r in res]

    def embed(self, text: str) -> list[float]:
        """单条文本向量化（同步，由 EmbeddingService 通过 to_thread 调用）"""
        self._ensure_loaded()
        return self._run([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量向量化（同步）。一次 ONNX 推理完成整批，效率高于逐条。"""
        self._ensure_loaded()
        return self._run(texts)
