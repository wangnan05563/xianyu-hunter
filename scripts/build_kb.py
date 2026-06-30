"""一次性脚本：执行知识库全量构建

用途：
- 首次部署或训练材料更新后，手动触发 KBManager.build_all()
- 验证 EmbeddingService + VectorStore + KBManager 全链路工作正常

运行：python scripts/build_kb.py
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# 确保项目根目录在 sys.path 中（脚本从 scripts/ 目录运行时）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main() -> int:
    # with_browser=False：Web 进程模式，跳过浏览器启动节省 ~100-200MB 内存
    # 详见 project_memory 中的硬约束
    from xianyu_hunter.container import build_default_container

    print("=" * 60)
    print("知识库全量构建")
    print("=" * 60)

    t0 = time.monotonic()
    container = build_default_container(with_browser=False)
    if container.chatbot is None:
        print("[FAIL] 智能客服子容器初始化失败，请检查依赖（chromadb/sentence-transformers）")
        return 1

    kb_manager = container.chatbot["kb_manager"]
    vector_store = container.chatbot["vector_store"]

    # 构建前统计
    before_count = await vector_store.count()
    print(f"构建前 ChromaDB 片段数: {before_count}")
    print("开始执行 build_all() ...")
    print("-" * 60)

    version = await kb_manager.build_all()
    print("-" * 60)
    print(f"version_id: {version.version_id}")
    print(f"build_type: {version.build_type}")
    print(f"status: {version.status}")
    print(f"chunk_count: {version.chunk_count}")
    print(f"failed_chunk_count: {version.failed_chunk_count}")
    print(f"build_duration_sec: {version.build_duration_sec}")
    if version.error_message:
        print(f"error_message: {version.error_message}")

    # 构建后统计
    after_count = await vector_store.count()
    print(f"构建后 ChromaDB 片段数: {after_count}")

    # 简单检索验证：用一个常见问题测试 RAG 检索
    print("-" * 60)
    print("检索验证（query='闲鱼猎人怎么创建任务'）...")
    embedding_service = container.chatbot["embedding_service"]
    qvec = await embedding_service.embed("闲鱼猎人怎么创建任务")
    if not qvec:
        print("[FAIL] query 向量化返回空")
        return 1
    results = await vector_store.search(qvec, top_k=3)
    print(f"top-{len(results)} 结果：")
    for i, r in enumerate(results, 1):
        print(f"  [{i}] similarity={r['similarity']:.4f}  source={r['source_file']}")
        snippet = r["content"][:120].replace("\n", " ")
        print(f"      content: {snippet}...")

    elapsed = time.monotonic() - t0
    print("=" * 60)
    print(f"总耗时: {elapsed:.2f}s")
    print("=" * 60)
    return 0 if version.status in ("success", "partial") else 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
