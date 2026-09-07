# -*- coding: utf-8 -*-
"""KBManager 文件级增量更新核心逻辑测试（F8 根治）

覆盖 4 个关键分支：
1. 无旧版本（首次）→ 全量重建（clear_collection + 全部 embedding）
2. 文件指纹无变化 → 跳过（返回 None）
3. 单文件内容变更 → 只重建该文件（删旧 + upsert 新，不清空）
4. 文件被删除 → 仅按 source 删除旧片段
"""
import asyncio
import json
import types

from xianyu_hunter.modules.chatbot.kb_manager import KBManager, DocSnippet


def _mk(source: str, content: str) -> DocSnippet:
    return DocSnippet(
        content=content, source_file=source, section_path="## t",
        line_start=1, line_end=2, doc_type="design",
    )


class FakeRepo:
    def __init__(self, versions=None):
        self.versions = list(versions or [])

    def get_current_kb_version(self):
        for v in reversed(self.versions):
            if v.get("status") == "success":
                return v
        return None

    def list_kb_versions(self, limit=100):
        return list(reversed(self.versions))

    def create_kb_version(self, version_id, snapshot_path, doc_hash, build_type,
                          file_fingerprints=None):
        v = {
            "id": version_id, "snapshot_path": snapshot_path, "doc_hash": doc_hash,
            "file_fingerprints": file_fingerprints, "chunk_count": 0,
            "failed_chunk_count": 0, "build_type": build_type, "status": "building",
            "build_duration_sec": None, "error_message": None, "is_current": False,
            "created_at": None,
        }
        self.versions.append(v)
        return v

    def update_kb_version_status(self, version_id, status, chunk_count=0,
                                 failed_chunk_count=0, build_duration_sec=None,
                                 error_message=None):
        for v in self.versions:
            if v["id"] == version_id:
                v.update(status=status, chunk_count=chunk_count,
                         failed_chunk_count=failed_chunk_count,
                         build_duration_sec=build_duration_sec,
                         error_message=error_message)
        return True

    def get_kb_version(self, version_id):
        for v in self.versions:
            if v["id"] == version_id:
                return v
        return None


class FakeEmbedding:
    def __init__(self):
        self.calls = []

    async def embed_batch(self, texts, progress_cb=None):
        self.calls.append(list(texts))
        return [[0.1] * 4 for _ in texts], []


class FakeVectorStore:
    def __init__(self):
        self.clear_count = 0
        self.deleted = []
        self.upserted_chunks = []

    async def export_snapshot(self, snapshot_path):
        pass

    async def clear_collection(self):
        self.clear_count += 1

    async def delete_by_source(self, source_file):
        self.deleted.append(source_file)
        return 1

    async def upsert(self, chunks):
        self.upserted_chunks.extend(chunks)
        return len(chunks)

    async def count(self):
        return 100


def _make_mgr(repo, vs, emb):
    cfg = types.SimpleNamespace(snapshot_max_keep=10)
    return KBManager(
        embedding_service=emb, vector_store=vs, repo=repo, config=cfg, project_root=".",
    )


def test_incremental_no_prior_version_full_rebuild():
    repo = FakeRepo()
    vs = FakeVectorStore()
    emb = FakeEmbedding()
    mgr = _make_mgr(repo, vs, emb)
    snippets = [_mk("docs/a.md", "A"), _mk("backend/x.py", "B")]
    fps = {"docs/a.md": "h1", "backend/x.py": "h2"}
    mgr._scan_and_chunk_with_fingerprints = lambda: (snippets, fps)

    asyncio.run(mgr.incremental_update())

    assert vs.clear_count == 1        # 无旧版本 → 全量清空重建
    assert len(emb.calls[0]) == 2     # 全部片段被 embedding
    assert vs.deleted == []           # 无需按 source 删除
    v = repo.versions[-1]
    assert v["build_type"] == "incremental"
    assert json.loads(v["file_fingerprints"]) == fps


def test_incremental_same_fingerprints_skip():
    prev = {
        "id": "prev", "status": "success", "doc_hash": "x",
        "file_fingerprints": json.dumps({"docs/a.md": "h1", "backend/x.py": "h2"}),
    }
    repo = FakeRepo([prev])
    vs = FakeVectorStore()
    emb = FakeEmbedding()
    mgr = _make_mgr(repo, vs, emb)
    snippets = [_mk("docs/a.md", "A"), _mk("backend/x.py", "B")]
    mgr._scan_and_chunk_with_fingerprints = lambda: (
        snippets, {"docs/a.md": "h1", "backend/x.py": "h2"})

    result = asyncio.run(mgr.incremental_update())

    assert result is None
    assert not emb.calls
    assert vs.clear_count == 0
    assert len(repo.versions) == 1    # 未产生新版本


def test_incremental_changed_file_only_rebuilds_changed():
    prev = {
        "id": "prev", "status": "success", "doc_hash": "x",
        "file_fingerprints": json.dumps({"docs/a.md": "h1", "backend/x.py": "h2"}),
    }
    repo = FakeRepo([prev])
    vs = FakeVectorStore()
    emb = FakeEmbedding()
    mgr = _make_mgr(repo, vs, emb)
    snippets = [_mk("docs/a.md", "A"), _mk("backend/x.py", "B2")]
    mgr._scan_and_chunk_with_fingerprints = lambda: (
        snippets, {"docs/a.md": "h1", "backend/x.py": "h2changed"})

    asyncio.run(mgr.incremental_update())

    assert vs.clear_count == 0                       # 不清空集合
    assert "backend/x.py" in vs.deleted              # 变更文件旧片段被删
    assert "docs/a.md" not in vs.deleted             # 未变文件不动
    assert [c["source_file"] for c in vs.upserted_chunks] == ["backend/x.py"]
    assert len(emb.calls[0]) == 1                    # 只 embedding 变更文件


def test_incremental_removed_file_deleted():
    prev = {
        "id": "prev", "status": "success", "doc_hash": "x",
        "file_fingerprints": json.dumps({"docs/a.md": "h1", "docs/old.md": "ho"}),
    }
    repo = FakeRepo([prev])
    vs = FakeVectorStore()
    emb = FakeEmbedding()
    mgr = _make_mgr(repo, vs, emb)
    snippets = [_mk("docs/a.md", "A")]
    mgr._scan_and_chunk_with_fingerprints = lambda: (snippets, {"docs/a.md": "h1"})

    asyncio.run(mgr.incremental_update())

    assert vs.clear_count == 0
    assert vs.deleted == ["docs/old.md"]             # 已移除文件的旧片段被删
    assert "docs/a.md" not in vs.deleted             # 未变文件不动
