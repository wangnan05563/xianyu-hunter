"""KBManager：知识库管理器

职责：
- 文档扫描、分块、向量化、ChromaDB 写入
- 知识库版本管理（两阶段提交 + 快照恢复）
- 增量更新（doc_hash 对比）与回滚

设计要点（详见 docs/chatbot-详细设计.md §5.5）：
- 两阶段提交：阶段1导出快照，阶段2清空+写入+建版本记录，失败回滚
- 失败率 >10% 状态为 partial，>50% 状态为 failed 并回滚
- 失败构建不向上抛出（返回 failed 状态的 KBVersion）
- 旧快照保留 snapshot_max_keep 个，更老的清理
"""
from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import shutil
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from xianyu_hunter.infra.repo_chatbot import ChatbotRepository
from xianyu_hunter.infra.yaml_config import ChatbotKBConfig
from xianyu_hunter.modules.chatbot.embedding_service import EmbeddingService
from xianyu_hunter.modules.chatbot.security.patterns import SENSITIVE_PATTERNS
from xianyu_hunter.modules.chatbot.vector_store import VectorStore
from xianyu_hunter.paths import get_chromadb_path


@dataclass
class DocSnippet:
    """文档分片：扫描+分块后的原始片段（未向量化）"""
    content: str
    source_file: str          # 相对路径，如 "docs/chatbot-概要设计.md"
    section_path: str         # 如 "## 3. 模块设计 > ### 3.1 Orchestrator"
    line_start: int
    line_end: int
    doc_type: str             # requirement / design / manual / code
    truncated: bool = False   # 是否因超长被截断
    code_block: bool = False  # 是否为代码块
    redacted: bool = False    # 是否含敏感数据被标记


@dataclass
class KBVersion:
    """知识库版本记录"""
    version_id: str
    snapshot_path: str
    doc_hash: str
    build_type: str           # build / incremental / rollback
    status: str               # building / success / partial / failed / rolled_back
    chunk_count: int
    failed_chunk_count: int
    build_duration_sec: float | None
    error_message: str | None
    created_at: str           # ISO format


class KBManager:
    """知识库管理器：单例，通过 container 注入

    构建互斥：build_lock 防止并发 build_all（API 触发 + 定时触发同时执行）
    """

    # 失败率阈值（业务规则，详见概要设计 §3.13.4）
    _PARTIAL_FAIL_RATE = 0.10  # >10% 状态记为 partial
    _FAILED_FAIL_RATE = 0.50   # >50% 状态记为 failed 并回滚

    # 孤儿 building 版本超时阈值：build_all 中途进程崩溃 / 异常被吞没时，
    # 状态可能卡在 building。超过此时间的 building 记录视为脏数据，
    # 新的构建会先清理它们再继续（避免前端一直显示「正在重建」导致按钮禁用）。
    # 默认 1 小时：正常全量重建 < 10 分钟，1 小时足够冗余又不至于误清运行中任务。
    _STALE_BUILDING_SEC = 3600

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        repo: ChatbotRepository,
        config: ChatbotKBConfig,
        project_root: str = ".",
    ) -> None:
        self._embedding = embedding_service
        self._vector_store = vector_store
        self._repo = repo
        self._config = config
        self._project_root = Path(project_root)
        # 构建互斥锁：build_all 与 incremental_update 共用，避免并发构建产生不一致快照
        self._build_lock = asyncio.Lock()
        # 构建进度状态：供 /kb/status 接口读取，前端轮询展示真实进度
        # 单值即可，因为 _build_lock 保证不会并发构建
        self._progress: dict = {"phase": "idle", "percent": 0, "message": ""}

    # ==================== 公开方法 ====================

    def get_progress(self) -> dict:
        """返回当前构建进度（供 /kb/status 接口转发给前端）"""
        return dict(self._progress)

    def _set_progress(self, phase: str, percent: int, message: str = "") -> None:
        """更新进度状态

        phase: idle/scanning/snapshotting/embedding/writing/finalizing/done/failed/rolling_back
        percent: 0-100
        message: 人类可读的阶段描述（前端直接展示）

        日志策略：phase 切换或 message 非空时打 INFO，便于运维事后分析构建流程。
        embedding 阶段细粒度进度由 embed_batch 内部节流打日志，避免这里重复刷屏。
        """
        prev_phase = self._progress.get("phase", "idle")
        self._progress = {
            "phase": phase,
            "percent": max(0, min(100, percent)),
            "message": message,
        }
        # 阶段切换 或 有描述消息 时打日志；embedding 阶段的细粒度进度
        # 由 _embed_batch_local 内部节流打日志（_PROGRESS_LOG_EVERY），这里只在
        # 进入/离开 embedding 阶段时打一次
        if phase != prev_phase or message:
            if phase == "embedding" and prev_phase == "embedding":
                # 内部进度变化，已被 _embed_batch_local 节流日志覆盖
                return
            logger.info(f"[KB进度] {phase} {percent}% {message}".rstrip())

    async def build_all(self) -> KBVersion:
        """全量构建：扫描所有 doc_paths → 分块 → 向量化 → 写入 ChromaDB → 创建版本记录

        两阶段提交：
        - 阶段1：导出当前 ChromaDB 快照到临时目录（用于回滚）
        - 阶段2：批量向量化 → 清空 ChromaDB → 写入新片段 → 更新版本状态
        - 任一阶段失败：调用 _rollback_build 恢复快照

        入口保护：先清理「陈旧 building 版本」（上次进程崩溃 / 异常被吞没遗留的脏数据），
        避免它们让 has_building_kb_version() 永远返回 true 导致前端按钮一直禁用。
        """
        # 先清理陈旧 building 版本，再争抢锁（避免锁内做 DB 写入扩大临界区）
        self._cleanup_stale_building_versions()

        async with self._build_lock:
            self._set_progress("scanning", 5, "扫描文档中...")
            snippets, fingerprints = self._scan_and_chunk_with_fingerprints()
            if not snippets:
                logger.warning("未扫描到任何文档片段，跳过构建")
                self._set_progress("failed", 100, "无文档片段可构建")
                return self._make_empty_failed_version("无文档片段可构建")

            self._set_progress("scanning", 15, f"已扫描到 {len(snippets)} 个片段")

            # 预估信息：参考上次成功构建的耗时，给用户心理预期
            # 避免 1 小时+ 的 embedding 阶段被误判为「卡死」而中途放弃
            last_ver = self._repo.get_current_kb_version()
            if last_ver and last_ver.get("build_duration_sec"):
                last_dur = last_ver["build_duration_sec"]
                last_chunks = last_ver.get("chunk_count", 0)
                # 用片段数比例外推：上次 10000 片段耗时 3600s → 本次 12000 片段预估 4320s
                if last_chunks > 0:
                    eta_sec = last_dur * len(snippets) / last_chunks
                    logger.info(
                        f"[KB预估] {len(snippets)} 片段，参考上次 {last_chunks} 片段/{last_dur:.0f}s，"
                        f"预估本次约 {eta_sec:.0f}s ({eta_sec/60:.0f}min)"
                    )
                else:
                    logger.info(
                        f"[KB预估] {len(snippets)} 片段，参考上次耗时 {last_dur:.0f}s"
                    )
            else:
                logger.info(
                    f"[KB预估] {len(snippets)} 片段，无历史参考耗时"
                )

            doc_hash = self._compute_doc_hash(snippets)
            version_id = uuid.uuid4().hex
            snapshot_path = self._make_snapshot_path(version_id)

            return await self._do_build(
                snippets=snippets,
                version_id=version_id,
                snapshot_path=snapshot_path,
                doc_hash=doc_hash,
                build_type="build",
                file_fingerprints=json.dumps(fingerprints),
                full_rebuild=True,
            )

    async def incremental_update(self) -> KBVersion | None:
        """增量更新：扫描文档 → 文件级指纹对比 → 只重建变更/新增文件，删除已移除文件

        - 文件级指纹（{source_file: content_md5}）无变化：返回 None（无需更新）
        - 有变化：只对变更/新增文件重新分块+embedding，删除已消失文件的旧片段，
          不清空集合（F8 根治：从"全量重建"降为"文件级增量"）
        - 旧版本无指纹（老库 / 回滚版本）时降级为全量重建，保证正确性
        """
        async with self._build_lock:
            self._set_progress("scanning", 5, "增量扫描文档中...")
            snippets, fingerprints = self._scan_and_chunk_with_fingerprints()
            if not snippets:
                logger.info("增量更新：未扫描到文档，跳过")
                self._set_progress("idle", 0, "")
                return None

            current_hash = self._compute_doc_hash(snippets)
            last_version = self._repo.get_current_kb_version()
            prev_fp = self._parse_fingerprints(last_version)
            if prev_fp is not None and prev_fp == fingerprints:
                logger.info("知识库文件指纹无变化，跳过增量更新")
                self._set_progress("idle", 0, "")
                return None

            if prev_fp is None:
                # 首次构建 / 老版本无指纹：降级为全量重建
                changed_snippets = snippets
                sources_to_replace: set[str] = set()
                full_rebuild = True
            else:
                removed_files = set(prev_fp) - set(fingerprints)
                changed_files = {
                    f for f in fingerprints if prev_fp.get(f) != fingerprints[f]
                }
                changed_snippets = [
                    s for s in snippets
                    if s.source_file in changed_files or s.source_file not in prev_fp
                ]
                sources_to_replace = changed_files | removed_files
                full_rebuild = not sources_to_replace
                if not changed_snippets and not removed_files:
                    # 指纹不同但分块结果无差异（如仅空白变化），无需重建
                    logger.info("知识库内容无片段级变化，跳过增量更新")
                    self._set_progress("idle", 0, "")
                    return None
                logger.info(
                    f"增量更新: 变更/新增文件 {len(changed_files)} 个，"
                    f"移除文件 {len(removed_files)} 个，"
                    f"待 embedding 片段 {len(changed_snippets)}/{len(snippets)}"
                )

            version_id = uuid.uuid4().hex
            snapshot_path = self._make_snapshot_path(version_id)

            return await self._do_build(
                snippets=changed_snippets,
                version_id=version_id,
                snapshot_path=snapshot_path,
                doc_hash=current_hash,
                build_type="incremental",
                file_fingerprints=json.dumps(fingerprints),
                sources_to_replace=sources_to_replace,
                full_rebuild=full_rebuild,
            )

    async def rollback(self, version_id: str) -> KBVersion:
        """从指定版本的快照恢复 ChromaDB

        - 创建 build_type="rollback" 的新版本记录
        - 旧版本状态更新为 "rolled_back"
        """
        self._set_progress("rolling_back", 5, f"回滚到版本 {version_id[:8]}")
        target = self._repo.get_kb_version(version_id)
        if not target:
            # 版本不存在时返回 failed 版本（不抛异常，符合"异常不向上抛出"约定）
            logger.warning(f"回滚失败：版本 {version_id} 不存在")
            self._set_progress("failed", 100, f"回滚失败：版本 {version_id} 不存在")
            return self._make_empty_failed_version(
                f"回滚失败：版本 {version_id} 不存在",
                build_type="rollback",
            )

        snapshot_path = target.get("snapshot_path", "")
        new_version_id = uuid.uuid4().hex
        new_snapshot_path = self._make_snapshot_path(new_version_id)
        doc_hash = target.get("doc_hash", "")
        start_ts = time.monotonic()

        # 先创建 building 状态的新版本记录
        self._set_progress("rolling_back", 20, "创建回滚版本记录")
        self._repo.create_kb_version(
            version_id=new_version_id,
            snapshot_path=new_snapshot_path,
            doc_hash=doc_hash,
            # 回滚后集合内容与目标版本一致，沿用其文件指纹以支持后续文件级增量
            file_fingerprints=target.get("file_fingerprints"),
            build_type="rollback",
        )
        self._repo.update_kb_version_status(
            version_id=new_version_id,
            status="building",
        )

        try:
            # 旧版本标记为 rolled_back（在恢复前更新，避免恢复失败时旧版本仍为 success）
            self._repo.update_kb_version_status(
                version_id=version_id,
                status="rolled_back",
            )

            self._set_progress("rolling_back", 40, "从快照恢复 ChromaDB")
            # 从快照恢复 ChromaDB
            await self._vector_store.restore_from_snapshot(snapshot_path)

            self._set_progress("rolling_back", 70, "导出新快照")
            # 恢复后立即导出新快照（保留可二次回滚的版本）
            await self._vector_store.export_snapshot(new_snapshot_path)

            chunk_count = await self._vector_store.count()
            duration = time.monotonic() - start_ts

            self._repo.update_kb_version_status(
                version_id=new_version_id,
                status="success",
                chunk_count=chunk_count,
                failed_chunk_count=0,
                build_duration_sec=duration,
                error_message=None,
            )

            self._cleanup_old_snapshots()
            self._set_progress(
                "done", 100,
                f"回滚完成: {chunk_count} 片段"
            )
            logger.info(
                f"回滚成功: target={version_id} new={new_version_id} "
                f"chunks={chunk_count} duration={duration:.2f}s"
            )
            return self._repo_to_version(self._repo.get_kb_version(new_version_id))
        except Exception as e:
            logger.exception("回滚失败")
            duration = time.monotonic() - start_ts
            self._repo.update_kb_version_status(
                version_id=new_version_id,
                status="failed",
                chunk_count=0,
                failed_chunk_count=0,
                build_duration_sec=duration,
                error_message=f"回滚失败: {type(e).__name__}: {e}",
            )
            self._set_progress("failed", 100, f"回滚失败: {e}")
            return self._repo_to_version(self._repo.get_kb_version(new_version_id))

    # ==================== 内部方法：构建核心 ====================

    async def _do_build(
        self,
        snippets: list[DocSnippet],
        version_id: str,
        snapshot_path: str,
        doc_hash: str,
        build_type: str,
        file_fingerprints: str | None = None,
        sources_to_replace: set[str] | None = None,
        full_rebuild: bool = True,
    ) -> KBVersion:
        """两阶段提交的核心实现

        阶段1：export_snapshot 到临时目录（保留回滚点）
        阶段2：embed_batch → clear_collection → upsert snippets → update version
        异常时调用 _rollback_build
        """
        start_ts = time.monotonic()

        # 先创建 building 状态的版本记录，便于外部观测构建状态
        self._set_progress("snapshotting", 20, "创建版本记录")
        self._repo.create_kb_version(
            version_id=version_id,
            snapshot_path=snapshot_path,
            doc_hash=doc_hash,
            file_fingerprints=file_fingerprints,
            build_type=build_type,
        )
        self._repo.update_kb_version_status(
            version_id=version_id,
            status="building",
        )

        # 阶段1：导出当前 ChromaDB 快照（用于失败回滚）
        # 先导出再清空，保证有可恢复的快照点
        self._set_progress("snapshotting", 30, "导出 ChromaDB 快照")
        await self._vector_store.export_snapshot(snapshot_path)

        # 阶段2：批量向量化 → 清空集合 → 写入新片段 → 更新版本状态
        # 用 try/finally 保证 _rollback_build 必定在异常路径被调用，
        # 避免版本状态卡在 building 永远不被改写（前端按钮一直灰显的根因之一）
        try:
            try:
                total_snippets = len(snippets)
                self._set_progress(
                    "embedding", 40,
                    f"向量化 {total_snippets} 个片段中..."
                )

                # 进度回调：把向量化子进度映射到 40% → 70% 区间
                # 写入阶段保留 70% 之后，避免进度条最后卡在中间值
                def _on_embed_progress(done: int, total: int) -> None:
                    if total <= 0:
                        return
                    # 40 + (done/total) * 30，向上取整避免前端看到「进度倒退」
                    percent = 40 + int(done * 30 / total)
                    self._set_progress(
                        "embedding", percent,
                        f"向量化中 {done}/{total}",
                    )

                embeddings, failed_indices = await self._embedding.embed_batch(
                    [s.content for s in snippets],
                    progress_cb=_on_embed_progress,
                )
                # embed_batch 返回 (成功向量紧凑列表, 失败索引列表)；空输入时返回 (None, [])
                if embeddings is None:
                    embeddings = []

                total = len(snippets)
                failed_count = len(failed_indices)
                fail_rate = failed_count / total if total > 0 else 0.0

                # 失败率 >50%：状态 failed，回滚（避免写入质量过低的知识库）
                if fail_rate > self._FAILED_FAIL_RATE:
                    logger.error(
                        f"Embedding 失败率 {fail_rate:.1%} > 50%，终止构建并回滚"
                    )
                    await self._rollback_build(
                        snapshot_path=snapshot_path,
                        version_id=version_id,
                        error=RuntimeError(
                            f"embedding 失败率 {fail_rate:.1%} 超过 50% 阈值"
                        ),
                    )
                    return self._repo_to_version(self._repo.get_kb_version(version_id))

                self._set_progress(
                    "writing", 70,
                    f"写入向量库（{total - failed_count}/{total} 片段）"
                )
                # 全量重建：清空集合后写入全部；
                # 增量合并：先删变更/移除文件的旧片段再 upsert 新片段，保留未变文件的向量
                if full_rebuild:
                    await self._vector_store.clear_collection()
                else:
                    for src in (sources_to_replace or set()):
                        await self._vector_store.delete_by_source(src)
                chunks_with_vectors: list[dict] = []
                failed_set = set(failed_indices)
                vec_idx = 0
                for i, snippet in enumerate(snippets):
                    if i in failed_set:
                        continue
                    if vec_idx >= len(embeddings):
                        # 防御性：embeddings 数量与预期不符时停止
                        break
                    chunks_with_vectors.append({
                        "id": f"{version_id}_{i}",
                        "content": snippet.content,
                        "source_file": snippet.source_file,
                        "section_path": snippet.section_path,
                        "line_start": snippet.line_start,
                        "line_end": snippet.line_end,
                        "doc_type": snippet.doc_type,
                        "embedding": embeddings[vec_idx],
                    })
                    vec_idx += 1

                upserted = await self._vector_store.upsert(chunks_with_vectors)
                # 增量合并后总片段数 = 集合实际数量（未变片段 + 新写片段）
                final_chunk_count = (
                    upserted
                    if full_rebuild
                    else await self._vector_store.count()
                )

                # 状态判定：>50% 已回滚；>10% partial；其他 success
                if fail_rate > self._PARTIAL_FAIL_RATE:
                    status = "partial"
                else:
                    status = "success"

                self._set_progress("finalizing", 90, "更新版本状态")
                duration = time.monotonic() - start_ts
                self._repo.update_kb_version_status(
                    version_id=version_id,
                    status=status,
                    chunk_count=final_chunk_count,
                    failed_chunk_count=failed_count,
                    build_duration_sec=duration,
                    error_message=None,
                )

                # 清理旧快照（保留 snapshot_max_keep 个）
                self._cleanup_old_snapshots()

                self._set_progress(
                    "done", 100,
                    f"构建完成: {final_chunk_count} 片段，状态 {status}"
                )
                logger.info(
                    f"知识库构建完成: version={version_id} type={build_type} "
                    f"status={status} chunks={final_chunk_count} failed={failed_count} "
                    f"duration={duration:.2f}s"
                )
                return self._repo_to_version(self._repo.get_kb_version(version_id))
            except Exception as e:
                logger.exception("阶段2（写入 ChromaDB）失败，开始回滚")
                await self._rollback_build(
                    snapshot_path=snapshot_path,
                    version_id=version_id,
                    error=e,
                )
                return self._repo_to_version(self._repo.get_kb_version(version_id))
        finally:
            # 兜底：无论成功失败，确保进度状态离开「活跃中间态」，
            # 避免进程崩溃后 _progress 残留 embedding/writing 等中间值
            current = self._progress.get("phase", "idle")
            if current in ("scanning", "snapshotting", "embedding", "writing", "finalizing"):
                logger.warning(
                    f"构建流程异常退出时进度仍为 {current}，强制归位为 idle"
                )
                self._set_progress("idle", 0, "")

    # ==================== 内部方法：扫描与分块 ====================

    # 扫描时排除的目录：这些目录下的文件对 RAG 知识库无价值
    # web/static: 前端构建产物（打包后的 .js/.css，单文件几百KB，会产生数千片段）
    # web/templates: HTML 模板（对问答无帮助）
    # __pycache__: Python 字节码缓存
    # node_modules / .git / dist / build: 依赖与构建产物
    _EXCLUDED_DIRS: frozenset[str] = frozenset({
        "web/static", "web/templates", "__pycache__",
        "node_modules", ".git", ".idea", ".vscode",
        "dist", "build", "target", ".cache",
    })

    # 仅索引这些后缀的文件（白名单机制）
    # 原因：.js/.css/.html/.svg/.json 等文件对 RAG 问答无价值，
    # 且打包后的前端文件体积大、被切成数千片段会拖慢向量化
    _ALLOWED_SUFFIXES: frozenset[str] = frozenset({
        ".md", ".py", ".jsonl", ".txt",
    })

    # S1192: 提取重复的 section_path 和 doc_type 字面量为常量
    _FILE_SECTION = "<file>"
    _HEADER_SECTION = "<header>"
    _DOC_TYPE_CODE = "code"
    _DOC_TYPE_MANUAL = "manual"

    def _is_excluded_path(self, fp: Path) -> bool:
        """判断文件是否落在 _EXCLUDED_DIRS 内（用 posix 路径匹配，兼容 Windows 反斜杠）"""
        try:
            rel = fp.relative_to(self._project_root).as_posix()
        except ValueError:
            rel = fp.as_posix()
        return any(
            rel.startswith(excluded + "/") or f"/{excluded}/" in f"/{rel}/"
            for excluded in self._EXCLUDED_DIRS
        )

    def _collect_files_from_path(self, root: Path) -> list[Path]:
        """从给定 root 收集要扫描的文件列表

        - root 是文件：直接返回 [root]
        - root 是目录：rglob 遍历，按 _EXCLUDED_DIRS 与 _ALLOWED_SUFFIXES 过滤
        """
        if root.is_file():
            return [root]
        files: list[Path] = []
        for fp in root.rglob("*"):
            if not fp.is_file():
                continue
            # 排除目录检查：用 posix 路径匹配，兼容 Windows 反斜杠
            if self._is_excluded_path(fp):
                continue
            # 后缀白名单：跳过 .js/.css/.html 等无文档价值的文件
            if fp.suffix.lower() not in self._ALLOWED_SUFFIXES:
                continue
            files.append(fp)
        return files

    def _chunk_file_by_suffix(self, file_path: Path, rel_path: str, content: str | None = None) -> list[DocSnippet]:
        """按后缀选择对应的分块器，返回该文件的片段列表

        content 可预传入（扫描时已读文件用于指纹，避免二次读盘）；为 None 时内部读取。
        """
        suffix = file_path.suffix.lower()
        if content is None:
            content = self._read_text(file_path)
        if suffix == ".md":
            return self._chunk_markdown(content, rel_path)
        if suffix == ".py":
            return self._chunk_python(content, rel_path)
        if suffix == ".jsonl":
            # JSONL 训练材料：每行一个独立训练样本，按行解析而非字符切分
            return self._chunk_jsonl(content, rel_path)
        # .txt 及其他白名单内但无专门分块器的文件
        if not content:
            return []
        return self._chunk_plain(content, rel_path)

    def _mark_sensitive_snippets(self, snippets: list[DocSnippet]) -> None:
        """原地标记含敏感数据的片段 redacted=True

        不脱敏是因为脱敏会破坏代码语义与文档可读性
        """
        for s in snippets:
            if self._has_sensitive_data(s.content):
                s.redacted = True

    def _scan_and_chunk(self) -> list[DocSnippet]:
        """兼容入口：仅返回片段列表（文件级指纹由 _scan_and_chunk_with_fingerprints 提供）"""
        snippets, _fingerprints = self._scan_and_chunk_with_fingerprints()
        return snippets

    def _scan_and_chunk_with_fingerprints(self) -> tuple[list[DocSnippet], dict[str, str]]:
        """扫描 config.doc_paths 下所有文件，返回 (snippets, {source_file: content_md5})

        - .md 文件：用 _chunk_markdown（按 H2 分割 + 代码块单独提取）
        - .py 文件：用 _chunk_python（AST 解析 docstring）
        - .jsonl 文件：用 _chunk_jsonl（每行一个独立训练样本）
        - .txt 文件：用 _chunk_plain（按 chunk_size 固定长度分块）
        - 其他文件类型跳过（前端构建产物等对 RAG 无价值）
        - 含敏感数据的片段标记 redacted=True 但保留

        source_file 统一为相对 project_root 的 posix 路径（与 upsert 的 metadata 一致）；
        content hash 为文件级指纹，供增量更新只重建变更文件（F8 根治）。
        """
        snippets: list[DocSnippet] = []
        fingerprints: dict[str, str] = {}
        for doc_path in self._config.doc_paths:
            root = self._project_root / doc_path
            if not root.exists():
                logger.warning(f"文档路径不存在: {doc_path}")
                continue

            # 既支持目录扫描也支持单文件
            files = self._collect_files_from_path(root)

            for file_path in files:
                # 统一用相对路径作为 source_file，便于按来源删除/审计
                try:
                    rel_path = file_path.relative_to(self._project_root).as_posix()
                except ValueError:
                    rel_path = file_path.as_posix()

                content = self._read_text(file_path)
                if not content:
                    continue
                fingerprints[rel_path] = hashlib.md5(content.encode("utf-8")).hexdigest()
                file_snippets = self._chunk_file_by_suffix(
                    file_path, rel_path, content=content
                )
                # 敏感数据扫描：标记 redacted=True 但保留片段
                self._mark_sensitive_snippets(file_snippets)
                snippets.extend(file_snippets)

        return snippets, fingerprints

    def _read_text(self, file_path: Path) -> str:
        """读取文件文本内容，失败时返回空字符串（避免单文件失败中断整个扫描）"""
        try:
            return file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            logger.debug(f"读取文件失败，跳过: {file_path}: {e}")
            return ""

    def _chunk_markdown(self, content: str, source_file: str) -> list[DocSnippet]:
        """Markdown 分块：按 ## H2 标题分割

        - 代码块（``` 或 ~~~）单独提取为 code_block 片段
        - 每个 H2 块内若超过 chunk_size，按 chunk_overlap 重叠切分并标记 truncated
        """
        if not content:
            return []

        lines = content.split("\n")
        snippets: list[DocSnippet] = []
        current_section: list[str] = []
        current_path = ""
        section_start_line = 1
        doc_type = self._classify_md_type(source_file)

        in_code_block = False
        code_block_start_line = 0

        for i, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            # 代码块边界检测（``` 或 ~~~）
            if stripped.startswith("```") or stripped.startswith("~~~"):
                # 代码块边界处理：进入/退出分别 flush 段落或生成代码片段
                # 提取为独立方法避免 if/else 双分支嵌套过深导致认知复杂度堆积
                if not in_code_block:
                    # 进入代码块前先保存当前段落（避免代码块与文本混在一个片段）
                    self._flush_md_section(
                        current_section, snippets, source_file, current_path,
                        section_start_line, i - 1, doc_type,
                    )
                    current_section = []
                    in_code_block = True
                    code_block_start_line = i
                else:
                    self._append_code_block_snippet(
                        snippets, lines, code_block_start_line, i,
                        source_file, current_path, doc_type,
                    )
                    in_code_block = False
                    section_start_line = i + 1
                continue

            # 仅在非代码块内识别 H2 标题（避免把代码里的注释当标题）
            if not in_code_block and line.startswith("## ") and not line.startswith("### "):
                # 保存前一段
                self._flush_md_section(
                    current_section, snippets, source_file, current_path,
                    section_start_line, i - 1, doc_type,
                )
                current_section = [line]
                current_path = line.lstrip("# ").strip()
                section_start_line = i
            else:
                current_section.append(line)

        # 最后一段
        self._flush_md_section(
            current_section, snippets, source_file, current_path,
            section_start_line, len(lines), doc_type,
        )

        return snippets

    def _flush_md_section(
        self,
        current_section: list[str],
        snippets: list[DocSnippet],
        source_file: str,
        current_path: str,
        line_start: int,
        line_end: int,
        doc_type: str,
    ) -> None:
        """把累积的段落写入 snippets 列表

        为什么提取为独立方法：同一段「段落→片段」flush 逻辑在代码块进入、H2 切换、
        文件末尾出现 3 次，内联会让主循环嵌套过深且容易行为漂移。
        """
        if not current_section:
            return
        section_content = "\n".join(current_section).strip()
        if not section_content:
            return
        snippets.extend(self._make_md_snippets(
            section_content, source_file,
            current_path or self._HEADER_SECTION,
            line_start, line_end, doc_type,
        ))

    def _append_code_block_snippet(
        self,
        snippets: list[DocSnippet],
        lines: list[str],
        code_block_start_line: int,
        code_block_end_line: int,
        source_file: str,
        current_path: str,
        doc_type: str,
    ) -> None:
        """代码块结束：生成单个 code_block 片段并追加

        为什么独立方法：代码块片段字段较多且需截断处理，内联会让代码块 else 分支嵌套过深。
        """
        code_lines = lines[code_block_start_line - 1: code_block_end_line]
        code_content = "\n".join(code_lines)
        snippets.append(DocSnippet(
            content=code_content[: self._config.chunk_size],
            source_file=source_file,
            section_path=f"{current_path} > <code_block>",
            line_start=code_block_start_line,
            line_end=code_block_end_line,
            doc_type=doc_type,
            truncated=len(code_content) > self._config.chunk_size,
            code_block=True,
        ))

    def _make_md_snippets(
        self,
        content: str,
        source_file: str,
        section_path: str,
        line_start: int,
        line_end: int,
        doc_type: str,
    ) -> list[DocSnippet]:
        """对单个 Markdown 段落做超长截断 + 重叠分块

        重叠分块的目的：保留段落边界的语义连续性，避免在 chunk 边界丢失上下文
        """
        chunk_size = self._config.chunk_size
        overlap = self._config.chunk_overlap

        if len(content) <= chunk_size:
            return [DocSnippet(
                content=content,
                source_file=source_file,
                section_path=section_path,
                line_start=line_start,
                line_end=line_end,
                doc_type=doc_type,
                truncated=False,
            )]

        # 超长：按 chunk_size 重叠切分（步长 = chunk_size - overlap）
        snippets: list[DocSnippet] = []
        step = max(1, chunk_size - overlap)
        pos = 0
        idx = 0
        while pos < len(content):
            chunk = content[pos: pos + chunk_size]
            snippets.append(DocSnippet(
                content=chunk,
                source_file=source_file,
                section_path=f"{section_path} (part {idx + 1})",
                line_start=line_start,
                line_end=line_end,
                doc_type=doc_type,
                truncated=True,
            ))
            pos += step
            idx += 1
        return snippets

    def _chunk_python(self, content: str, source_file: str) -> list[DocSnippet]:
        """Python 文件分块：用 AST 解析，提取函数/类的 docstring

        - SyntaxError 时回退到文件级 docstring（取前 chunk_size 字符）
        - 记录行号范围（node.lineno ~ node.end_lineno）
        - 跳过私有方法（_ 开头），不纳入知识库
        """
        if not content:
            return []

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            # AST 解析失败降级为文件粒度（保留可索引内容，不丢弃整个文件）
            logger.debug(f"AST 解析失败，降级文件粒度: {source_file}: {e}")
            return [self._make_file_level_python_snippet(content, source_file)]

        snippets: list[DocSnippet] = []
        self._extract_python_module_docstring(tree, source_file, snippets)
        self._extract_python_node_docstrings(tree, source_file, snippets)

        # 若 AST 未提取到任何片段（如纯赋值脚本），降级为文件粒度
        if not snippets:
            snippets.append(self._make_file_level_python_snippet(content, source_file))

        return snippets

    def _extract_python_module_docstring(
        self, tree: ast.Module, source_file: str, snippets: list[DocSnippet],
    ) -> None:
        """提取模块级 docstring（tree.body[0] 若是 Expr 且 value 是 Constant str）

        为什么独立方法：模块 docstring 判定含 3 层 isinstance 嵌套，
        内联会让 _chunk_python 顶层逻辑被类型守护占据，可读性下降。
        """
        if not tree.body:
            return
        first = tree.body[0]
        if not isinstance(first, ast.Expr) or not isinstance(first.value, ast.Constant):
            return
        doc = first.value.value
        if not isinstance(doc, str):
            return
        snippets.append(DocSnippet(
            content=doc,
            source_file=source_file,
            section_path="<module>",
            line_start=1,
            line_end=first.end_lineno or 1,
            doc_type="code",
        ))

    def _extract_python_node_docstrings(
        self, tree: ast.Module, source_file: str, snippets: list[DocSnippet],
    ) -> None:
        """遍历 AST 提取类/函数的 docstring（跳过私有方法 _ 开头）

        为什么独立方法：遍历 + isinstance + 私有过滤 + docstring 存在性检查
        多层条件叠加，提取后 _chunk_python 主流程仅保留编排。
        """
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                continue
            # 跳过私有方法（_ 开头），不纳入知识库
            if isinstance(node, ast.FunctionDef) and node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                continue
            # 构造可读的 section_path（ClassDef:func 或 FunctionDef:func）
            node_kind = node.__class__.__name__
            snippets.append(DocSnippet(
                content=f"{node.name}: {doc}",
                source_file=source_file,
                section_path=f"{node_kind}:{node.name}",
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                doc_type="code",
            ))

    def _make_file_level_python_snippet(
        self, content: str, source_file: str,
    ) -> DocSnippet:
        """构造文件粒度的 Python 片段（AST 解析失败或无片段时降级使用）"""
        lines = content.splitlines()
        return DocSnippet(
            content=content[: self._config.chunk_size],
            source_file=source_file,
            section_path=self._FILE_SECTION,
            line_start=1,
            line_end=len(lines) if lines else 1,
            doc_type="code",
            truncated=len(content) > self._config.chunk_size,
        )

    def _chunk_jsonl(self, content: str, source_file: str) -> list[DocSnippet]:
        """JSONL 分块：每行 JSON 解析为一个 DocSnippet

        用于训练材料导入（docs/05-智能客服/training-corpus/*.jsonl）：
        每行是一个独立训练样本（FAQ/领域知识/对话示例等），不应被字符切分。
        字段映射：
        - content → content（向量化文本）
        - section_path/category → section_path
        - doc_type → doc_type
        - metadata.code_block/redacted → 对应标记
        解析失败的行跳过（不中断整个文件扫描）
        """
        if not content:
            return []

        import json
        snippets: list[DocSnippet] = []
        for line_num, line in enumerate(content.splitlines(), 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                logger.debug(f"JSONL 解析失败，跳过 {source_file}:{line_num}: {e}")
                continue
            metadata = obj.get("metadata", {}) or {}
            snippets.append(DocSnippet(
                content=obj.get("content", ""),
                source_file=source_file,
                section_path=obj.get("section_path", "") or obj.get("category", ""),
                line_start=line_num,
                line_end=line_num,
                doc_type=obj.get("doc_type", "manual"),
                truncated=False,
                code_block=bool(metadata.get("code_block", False)),
                redacted=bool(metadata.get("redacted", False)),
            ))
        return snippets

    def _chunk_plain(self, content: str, source_file: str) -> list[DocSnippet]:
        """其他文件：按 chunk_size 固定长度分块（带 overlap）"""
        if not content:
            return []

        chunk_size = self._config.chunk_size
        overlap = self._config.chunk_overlap
        step = max(1, chunk_size - overlap)
        lines = content.splitlines()
        total_lines = len(lines) if lines else 1

        if len(content) <= chunk_size:
            return [DocSnippet(
                content=content,
                source_file=source_file,
                section_path=self._FILE_SECTION,
                line_start=1,
                line_end=total_lines,
                doc_type=self._DOC_TYPE_MANUAL,
            )]

        snippets: list[DocSnippet] = []
        pos = 0
        idx = 0
        while pos < len(content):
            chunk = content[pos: pos + chunk_size]
            snippets.append(DocSnippet(
                content=chunk,
                source_file=source_file,
                section_path=f"{self._FILE_SECTION} (part {idx + 1})",
                line_start=1,
                line_end=total_lines,
                doc_type=self._DOC_TYPE_MANUAL,
                truncated=True,
            ))
            pos += step
            idx += 1
        return snippets

    def _classify_md_type(self, source_file: str) -> str:
        """根据文件名特征判定 Markdown 文档类型

        - requirement：文件名含 requirement/需求
        - design：文件名含 design/概要/详细/设计
        - manual：其他
        """
        name = source_file.lower()
        if "requirement" in name or "需求" in source_file:
            return "requirement"
        if "design" in name or "概要" in source_file or "详细" in source_file or "设计" in source_file:
            return "design"
        return "manual"

    def _has_sensitive_data(self, text: str) -> bool:
        """用 SENSITIVE_PATTERNS 检测是否含敏感数据

        命中任一规则即视为含敏感数据（在 _scan_and_chunk 中标记 redacted=True）
        """
        return any(p.search(text) for _, p, _ in SENSITIVE_PATTERNS)

    # ==================== 内部方法：回滚与清理 ====================

    async def _rollback_build(
        self,
        snapshot_path: str,
        version_id: str,
        error: Exception,
    ) -> None:
        """从快照恢复 ChromaDB，更新版本状态为 failed

        - 仅当快照目录存在且非空时才尝试恢复
          （阶段1失败时 ChromaDB 未被修改，空快照恢复会清空数据，需跳过）
        - 恢复失败时仅记录日志（不向上抛出，符合"异常不向上抛出"约定）
        - 删除本次构建的临时快照目录
        """
        err_msg = f"{type(error).__name__}: {error}"
        snapshot_dir = Path(snapshot_path)
        # 仅当快照目录存在且非空时才尝试恢复
        # 避免阶段1失败时（快照不完整或为空）误用空快照清空未被修改的 ChromaDB
        should_restore = snapshot_dir.exists() and any(snapshot_dir.iterdir())

        if should_restore:
            try:
                await self._vector_store.restore_from_snapshot(snapshot_path)
                logger.info(f"已从快照恢复 ChromaDB: {snapshot_path}")
            except Exception as restore_err:
                # 恢复失败属于严重错误：ChromaDB 可能不一致
                # 仅记录日志，不向上抛出
                logger.exception(
                    f"快照恢复失败，ChromaDB 可能不一致: {restore_err}"
                )

        # 删除本次构建的临时快照（已恢复或已无意义）
        try:
            if snapshot_dir.exists():
                shutil.rmtree(snapshot_dir, ignore_errors=True)
        except Exception as cleanup_err:
            logger.debug(f"清理临时快照失败（可忽略）: {cleanup_err}")

        self._repo.update_kb_version_status(
            version_id=version_id,
            status="failed",
            chunk_count=0,
            failed_chunk_count=0,
            build_duration_sec=None,
            error_message=err_msg,
        )
        # 同步更新构建进度为失败状态，让前端能感知到错误原因
        self._set_progress("failed", 100, f"构建失败: {err_msg}")

    def _cleanup_old_snapshots(self) -> None:
        """保留最近 snapshot_max_keep 个快照，删除更老的快照目录和对应版本记录

        - 版本按 created_at DESC 排序（list_kb_versions 已排序）
        - 超出保留数的旧版本：删除磁盘快照目录 + 状态标记为 rolled_back
          （不物理删除版本记录，保留历史可追溯）
        """
        keep = self._config.snapshot_max_keep
        # 取较多版本以覆盖清理场景（默认 limit=20 可能不够）
        versions = self._repo.list_kb_versions(limit=100)
        if len(versions) <= keep:
            return

        # list_kb_versions 按 created_at DESC 返回，索引 [keep:] 为应清理的旧版本
        to_remove = versions[keep:]
        for v in to_remove:
            old_snapshot = v.get("snapshot_path", "")
            old_id = v.get("id", "")
            if old_snapshot and Path(old_snapshot).exists():
                try:
                    shutil.rmtree(old_snapshot, ignore_errors=True)
                except Exception as e:
                    logger.debug(f"删除旧快照失败（可忽略）: {old_snapshot}: {e}")
            # 状态标记为 rolled_back（保留版本记录用于审计追溯）
            if old_id:
                self._repo.update_kb_version_status(
                    version_id=old_id,
                    status="rolled_back",
                )

    def _cleanup_stale_building_versions(self) -> None:
        """清理「陈旧 building 版本」

        为什么需要：构建流程异常崩溃（进程被 kill / 异常被吞没等）时，
        版本记录会卡在 status=building 而永远不被改写，导致：
        1. 前端 has_building_kb_version() 持续返回 true
        2. 「重建」按钮一直灰显
        3. 用户无法重试

        实现：把超过 _STALE_BUILDING_SEC（默认 1 小时）且仍为 building 的版本
        批量标记为 failed（带 error_message 便于审计追溯）。

        调用时机：build_all 入口、_on_startup 启动钩子（双保险）。
        """
        try:
            cleaned = self._repo.mark_stale_building_kb_versions_failed(
                older_than_sec=self._STALE_BUILDING_SEC,
                error_message=(
                    f"陈旧 building 版本（>{self._STALE_BUILDING_SEC}s 未更新）"
                    "已被自动标记为 failed（进程异常崩溃残留）"
                ),
            )
            if cleaned > 0:
                logger.warning(
                    f"已清理 {cleaned} 个陈旧 building 版本（超过 {self._STALE_BUILDING_SEC}s 未更新）"
                )
        except Exception:
            # 清理失败不应阻塞主流程（最坏情况：按钮继续灰显，用户手动清理 DB）
            logger.exception("清理陈旧 building 版本失败（可忽略）")

    # ==================== 内部方法：辅助 ====================

    def _compute_doc_hash(self, snippets: list[DocSnippet]) -> str:
        """对所有片段内容计算 MD5 hash

        用于增量更新时检测内容是否真的变更（避免重复构建）
        同时纳入 source_file 与 section_path，确保结构变化也能感知
        """
        h = hashlib.md5()
        for s in snippets:
            h.update(s.source_file.encode("utf-8"))
            h.update(b"\x00")
            h.update(s.section_path.encode("utf-8"))
            h.update(b"\x00")
            h.update(s.content.encode("utf-8"))
            h.update(b"\x01")
        return h.hexdigest()

    @staticmethod
    def _parse_fingerprints(last_version: dict | None) -> dict[str, str] | None:
        """从版本记录解析文件级指纹 {source_file: content_md5}

        记录缺失或字段为空（老库 / 回滚产生的版本）返回 None，
        调用方据此降级为全量重建，保证正确性。
        """
        if not last_version:
            return None
        raw = last_version.get("file_fingerprints")
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except (TypeError, ValueError):
            return None

    def _make_snapshot_path(self, version_id: str) -> str:
        """生成快照路径：data/chromadb/snapshots/{version_id}/

        相对路径由 vector_store.export_snapshot / restore_from_snapshot 接受

        注意：此处返回相对路径字符串（与 vector_store 接口约定一致），
        实际写入由 vector_store 在 persist_path 下完成。
        persist_path 已通过 yaml_config.py 走 paths.get_chromadb_path()，
        打包后会指向 %APPDATA%/XianyuHunter/data/chromadb
        """
        return str(get_chromadb_path() / "snapshots" / version_id)

    def _make_empty_failed_version(
        self,
        error: str,
        build_type: str = "build",
    ) -> KBVersion:
        """无片段可构建/版本不存在时返回的 failed 版本

        写入一条 failed 版本记录便于调用方感知失败原因
        """
        version_id = uuid.uuid4().hex
        snapshot_path = self._make_snapshot_path(version_id)
        self._repo.create_kb_version(
            version_id=version_id,
            snapshot_path=snapshot_path,
            doc_hash="",
            build_type=build_type,
        )
        self._repo.update_kb_version_status(
            version_id=version_id,
            status="failed",
            chunk_count=0,
            failed_chunk_count=0,
            build_duration_sec=0.0,
            error_message=error,
        )
        return self._repo_to_version(self._repo.get_kb_version(version_id))

    def _repo_to_version(self, data: dict | None) -> KBVersion:
        """repo 返回的 dict → KBVersion dataclass"""
        if data is None:
            return KBVersion(
                version_id="",
                snapshot_path="",
                doc_hash="",
                build_type="build",
                status="failed",
                chunk_count=0,
                failed_chunk_count=0,
                build_duration_sec=None,
                error_message="版本记录不存在",
                created_at=_utcnow_iso(),
            )
        return KBVersion(
            version_id=str(data.get("id", "")),
            snapshot_path=str(data.get("snapshot_path", "")),
            doc_hash=str(data.get("doc_hash", "")),
            build_type=str(data.get("build_type", "build")),
            status=str(data.get("status", "failed")),
            chunk_count=int(data.get("chunk_count", 0)),
            failed_chunk_count=int(data.get("failed_chunk_count", 0)),
            build_duration_sec=data.get("build_duration_sec"),
            error_message=data.get("error_message"),
            created_at=str(data.get("created_at", "")),
        )


def _utcnow_iso() -> str:
    """统一生成 ISO 时间字符串（与 repo_chatbot._serialize_dt 保持一致）"""
    return datetime.now(timezone.utc).isoformat()
