"""VectorStore：ChromaDB 适配器

职责：
- 封装 ChromaDB 的增删改查
- 快照导出/恢复（用于知识库版本管理）

设计要点（详见 docs/chatbot-详细设计.md §5.10）：
- 使用 ChromaDB 1.x API（PersistentClient），1.x 用 Rust 重写性能更优且提供 cp39-abi3 预编译 wheel
  （原 0.4.x 锁定因 chroma-hnswlib 需 C++ 编译、Python 3.14 无预编译 wheel 而放弃）
- 所有 ChromaDB 同步 API 用 asyncio.to_thread() 包装为异步，
  避免阻塞主事件循环（ChromaDB 内部 IO 较重）
- 异常在内部捕获并记录，不向上抛出（基础设施层容错）
- 关闭 telemetry，避免用户数据外泄
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

# 可选导入：chromadb 不是硬依赖（仅在构建/检索知识库时需要），
# 缺失时 __init__ 抛 ImportError 引导用户安装
try:
    import chromadb
except ImportError:
    chromadb = None  # type: ignore[assignment]


class VectorStore:
    """ChromaDB 适配器：单例，通过 container 注入"""

    def __init__(
        self,
        persist_path: str = "data/chromadb",
        collection_name: str = "xianyu_hunter_docs",
    ) -> None:
        if chromadb is None:
            # 明确告知安装命令，避免用户猜测版本兼容性
            raise ImportError(
                "chromadb 未安装，请运行: pip install chromadb>=1.0.0"
            )

        # 关闭 telemetry（避免用户数据外泄，符合需求 §10.3）
        # ChromaDB 1.x 改用 OpenTelemetry，未设置 CHROMA_OTEL_COLLECTION_ENDPOINT 时默认不发送数据
        # 此处仅作为兼容老版本 0.4.x 的兜底：0.4.x 需显式调用 disable_anonymized_telemetry()
        try:
            if hasattr(chromadb.telemetry, "disable_anonymized_telemetry"):
                chromadb.telemetry.disable_anonymized_telemetry()
        except Exception as e:
            # 失败不影响功能（1.x 默认已关闭 telemetry）
            logger.debug(f"关闭 ChromaDB telemetry 失败（可忽略）: {e}")

        self._persist_path = persist_path
        self._collection_name = collection_name
        # 持久化客户端：数据落盘到 persist_path，进程重启后数据不丢
        self._client = chromadb.PersistentClient(path=persist_path)
        # 集合固定使用 cosine 距离（与 OpenAI embedding 归一化向量匹配）
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # 暴露只读属性供运维 API（api_vector_admin）使用，避免外部直接访问私有字段
    @property
    def persist_path(self) -> str:
        return self._persist_path

    @property
    def collection_name(self) -> str:
        return self._collection_name

    async def search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        """向量检索

        返回 [{"content", "source_file", "section_path", "line_start",
                "line_end", "doc_type", "distance", "similarity"}]
        similarity = 1.0 - (distance / 2.0)（cosine distance 转 similarity）

        边界条件：
        - 集合为空：返回空列表
        - top_k > 集合大小：返回实际数量的结果
        """
        def _sync_query():
            return self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

        try:
            result = await asyncio.to_thread(_sync_query)
        except Exception as e:
            logger.exception(f"VectorStore 检索失败: {e}")
            return []

        if not result.get("ids") or not result["ids"][0]:
            return []

        chunks = []
        for i, _doc_id in enumerate(result["ids"][0]):
            distance = result["distances"][0][i]
            # cosine distance → similarity
            # ChromaDB cosine distance 范围 [0, 2]：0=完全相似，2=完全相反
            similarity = 1.0 - (distance / 2.0)
            metadata = result["metadatas"][0][i] or {}
            chunks.append({
                "content": result["documents"][0][i],
                "source_file": metadata.get("source_file", ""),
                "section_path": metadata.get("section_path", ""),
                "line_start": metadata.get("line_start", 0),
                "line_end": metadata.get("line_end", 0),
                "doc_type": metadata.get("doc_type", "manual"),
                "distance": distance,
                "similarity": similarity,
            })
        return chunks

    async def upsert(self, chunks: list[dict]) -> int:
        """批量插入/更新片段，返回成功数

        chunks 字段：
            [{"id", "content", "source_file", "section_path",
              "line_start", "line_end", "doc_type", "embedding"}]
        """
        if not chunks:
            return 0

        def _sync_upsert():
            # id 统一转字符串：ChromaDB 要求 id 为 str
            ids = [str(c["id"]) for c in chunks]
            embeddings = [c["embedding"] for c in chunks]
            documents = [c["content"] for c in chunks]
            metadatas = [
                {
                    "source_file": c.get("source_file", ""),
                    "section_path": c.get("section_path", ""),
                    "line_start": c.get("line_start", 0),
                    "line_end": c.get("line_end", 0),
                    "doc_type": c.get("doc_type", "manual"),
                }
                for c in chunks
            ]
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

        try:
            await asyncio.to_thread(_sync_upsert)
            return len(chunks)
        except Exception as e:
            logger.exception(f"VectorStore upsert 失败: {e}")
            return 0

    async def delete_by_source(self, source_file: str) -> int:
        """按来源文件删除，返回删除数

        ChromaDB delete 不返回删除数量，需先 get 拿到 ids 列表再 delete。
        """
        def _sync_get_ids():
            # where 过滤指定 source_file 的所有片段
            res = self._collection.get(where={"source_file": source_file})
            return res.get("ids", []) or []

        def _sync_delete():
            self._collection.delete(where={"source_file": source_file})

        try:
            ids = await asyncio.to_thread(_sync_get_ids)
            count = len(ids)
            if count == 0:
                return 0
            await asyncio.to_thread(_sync_delete)
            return count
        except Exception as e:
            logger.exception(f"VectorStore delete_by_source 失败: {e}")
            return 0

    async def clear_collection(self) -> None:
        """清空集合（全量重建前调用）

        实现方式：删除集合并重建，比逐条 delete 快得多。
        """
        def _sync_clear():
            self._client.delete_collection(self._collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        try:
            await asyncio.to_thread(_sync_clear)
        except Exception as e:
            logger.exception(f"VectorStore clear_collection 失败: {e}")

    async def export_snapshot(self, snapshot_path: str) -> None:
        """导出快照（复制 chromadb 持久化目录到 snapshot_path）

        ChromaDB 0.4.x 无原生快照 API，文件级复制是最简单可靠的方式。
        跳过 snapshots 子目录，避免递归复制快照目录本身。
        """
        def _sync_export():
            src = Path(self._persist_path)
            dst = Path(snapshot_path)
            dst.mkdir(parents=True, exist_ok=True)
            for item in src.iterdir():
                if item.name == "snapshots":
                    continue
                target = dst / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)

        try:
            await asyncio.to_thread(_sync_export)
        except Exception as e:
            logger.exception(f"VectorStore export_snapshot 失败: {e}")

    async def restore_from_snapshot(self, snapshot_path: str) -> None:
        """从快照恢复（先清空当前集合，再用快照覆盖）

        实现步骤：
        1. 清空 persist_path（保留 snapshots 目录，避免丢失其他版本快照）
        2. 复制快照内容到 persist_path
        3. 重建 collection 引用（旧的引用已失效）
        """
        def _sync_restore():
            src = Path(snapshot_path)
            if not src.exists():
                raise FileNotFoundError(f"快照不存在: {snapshot_path}")
            # 清空当前数据（保留 snapshots 目录）
            for item in Path(self._persist_path).iterdir():
                if item.name == "snapshots":
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            # 复制快照内容覆盖
            for item in src.iterdir():
                target = Path(self._persist_path) / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
            # 重建 collection 引用：旧 collection 对象绑定的数据已被替换
            self._collection = self._client.get_collection(self._collection_name)

        try:
            await asyncio.to_thread(_sync_restore)
        except Exception as e:
            logger.exception(f"VectorStore restore_from_snapshot 失败: {e}")

    async def count(self) -> int:
        """返回集合中片段数"""
        def _sync_count():
            return self._collection.count()

        try:
            return await asyncio.to_thread(_sync_count)
        except Exception as e:
            logger.exception(f"VectorStore count 失败: {e}")
            return 0
