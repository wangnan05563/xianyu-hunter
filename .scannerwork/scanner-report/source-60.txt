"""search_help 工具 — 基于向量检索搜索帮助文档

权限：read
超时：2s（默认，复用 RAGEngine.retrieve 的 embedding 调用）
LLM 工具：True（消耗 embedding 预算，ToolRegistry 会将其计入 LLM 工具预算）

调用模式：
- query（必填）：自然语言查询，返回 top_k 相关文档片段

实现复用 RAGEngine.retrieve，避免重复实现向量化 + 检索 + 阈值过滤逻辑。
返回的 chunks 转为 dict 列表供 LLM 在工具结果中引用。
"""
from __future__ import annotations

from typing import Any

from xianyu_hunter.modules.chatbot.tools.base import BaseTool, ToolResult


class SearchHelpTool(BaseTool):
    """搜索帮助文档工具

    通过 RAGEngine.retrieve 走完整的向量化 → ChromaDB 检索 → 阈值过滤流程，
    因复用 embedding 服务故 is_llm_tool=True（计入预算）。
    """

    name: str = "search_help"
    description: str = "搜索帮助文档，返回相关文档片段（基于 RAG 向量检索）"
    permissions: list[str] = ["read"]
    # 2s 默认超时：embedding 调用一般 <1s，预留 1s 余量
    timeout_sec: int = 2
    is_llm_tool: bool = True

    def __init__(self, rag_engine: Any) -> None:
        # 复用 RAGEngine 实例（container 单例），不重新构造 embedding/vector_store
        self._rag = rag_engine

    def get_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言查询，如 '如何配置 Cookie 自动同步'",
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    async def execute(self, query: str, **_: Any) -> ToolResult:
        if not query or not query.strip():
            return ToolResult(success=False, error="query 不能为空")

        chunks = await self._rag.retrieve(query)
        if not chunks:
            return ToolResult(
                success=True,
                data={"chunks": [], "count": 0, "message": "未找到相关文档"},
            )

        # 转 dict 列表便于 LLM 引用与序列化
        # 包含 index/source_file/section_path/line范围/content/similarity
        chunk_dicts = [
            {
                "index": i + 1,
                "source_file": c.source_file,
                "section_path": c.section_path,
                "line": f"L{c.line_start}-L{c.line_end}",
                "doc_type": c.doc_type,
                "similarity": round(c.similarity, 3),
                "content": c.content,
            }
            for i, c in enumerate(chunks)
        ]

        return ToolResult(
            success=True,
            data={"chunks": chunk_dicts, "count": len(chunk_dicts)},
        )
