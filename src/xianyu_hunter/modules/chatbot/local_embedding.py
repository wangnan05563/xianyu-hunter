"""LocalEmbeddingBackend：基于 sentence-transformers 的本地向量化后端

设计动机：
- Ollama 在 Windows 上需要 llama-server.exe 推理引擎，安装包不完整时无法工作
- sentence-transformers 直接在 Python 进程内推理，无需外部服务，部署简单
- bge-small-zh-v1.5（512 维，~95MB）中文优化，适合本项目 RAG 场景

懒加载策略：
- 模型在首次 embed 时加载（避免启动卡顿）
- 同一进程内复用实例（避免重复加载占用内存）

线程安全：
- sentence-transformers 内部模型推理本身线程安全（仅读权重）
- 但加载过程非线程安全，用 threading.Lock 保护 _load_model
"""
from __future__ import annotations

import os
import threading
from typing import Any

from loguru import logger

# 国内访问 huggingface.co 经常超时（WinError 10060），
# 默认走 hf-mirror.com 镜像；用户已设置 HF_ENDPOINT 时尊重其选择。
# 必须在 import sentence_transformers 之前执行：HF Hub 在请求时读取该变量，
# 模块加载阶段就会触发模型配置文件下载。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


class LocalEmbeddingBackend:
    """sentence-transformers 包装类，提供同步 embed 接口"""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: Any = None
        self._lock = threading.Lock()
        # 已加载的实际维度，首次 embed 后填充
        # 用途：ChromaDB collection 在首次 upsert 时推断维度，需与配置一致
        self._dim: int = 0

    @property
    def dimensions(self) -> int:
        """返回模型实际输出维度（首次 embed 后可用）"""
        return self._dim

    def _ensure_loaded(self) -> None:
        """懒加载模型（线程安全）

        首次调用时下载模型权重到 HuggingFace cache（~/.cache/huggingface/hub），
        后续启动直接从本地加载。
        """
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            logger.info(f"Loading local embedding model: {self._model_name}")
            # 延迟导入：避免未安装 torch 时整个模块 import 失败
            # 用户使用 HTTP backend 时无需安装 torch
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise RuntimeError(
                    "sentence-transformers 未安装，无法使用本地 embedding backend。"
                    "请运行: pip install torch --index-url https://download.pytorch.org/whl/cpu"
                    " && pip install sentence-transformers"
                ) from e
            # device='cpu' 显式指定：避免在无 CUDA 环境下自动探测失败
            self._model = SentenceTransformer(self._model_name, device="cpu")
            # sentence-transformers 5.x 重命名 get_sentence_embedding_dimension
            # → get_embedding_dimension，兼容新旧版本
            get_dim = getattr(
                self._model,
                "get_embedding_dimension",
                getattr(self._model, "get_sentence_embedding_dimension", None),
            )
            if get_dim is None:
                raise RuntimeError(
                    f"sentence-transformers 模型 {self._model_name} 不支持 "
                    "get_embedding_dimension/get_sentence_embedding_dimension，"
                    "请检查 sentence-transformers 版本"
                )
            self._dim = int(get_dim())
            logger.info(
                f"Local embedding model loaded: {self._model_name}, dim={self._dim}"
            )

    def embed(self, text: str) -> list[float]:
        """单条文本向量化（同步，由 EmbeddingService 通过 to_thread 调用）"""
        self._ensure_loaded()
        # normalize_to_fragment=False：保留原始向量，避免与 L2 距离计算不一致
        vec = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=False)
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量向量化（同步）

        sentence-transformers 内部已做 batch 优化，比循环单条快 10-50 倍。
        开启 show_progress_bar：让外层（to_thread 调用方）能在 stderr 看到 tqdm 进度条，
        便于运维直接观察 encode 速度，不再需要从日志反推。
        PyTorch CPU 多线程默认已启用（torch.set_num_threads = CPU 核数），
        无需额外配置；如需限制可在调用前 set torch.set_num_threads(N)。
        """
        self._ensure_loaded()
        vecs = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=False,
            batch_size=32,
            # tqdm 进度条写到 stderr，外层 asyncio.to_thread 调用方仍能正常观察
            # 不影响 logger 输出（loguru 也走 stderr，但独立 handler）
            show_progress_bar=len(texts) > 100,
        )
        return [v.tolist() for v in vecs]
