"""EmbeddingService：向量化服务，支持本地 backend 和 OpenAI 兼容远程 backend

职责：
- 单条/批量文本向量化
- 批量调用支持并发控制 + 重试 + 部分失败容忍
- 异常在内部捕获并记录，不向上抛出（基础设施层容错）

设计要点（详见 docs/chatbot-详细设计.md §5.9）：
- 并发用 asyncio.Semaphore 控制，避免触发 OpenAI 限流
- 每条文本独立重试 3 次（指数退避 0.5s/1s/2s）
- 部分失败：跳过失败片段，记录失败索引
- 失败率 >10% 时记 warning 但不终止（由调用方决定后续动作）
- 调用前 check_budget，调用后 record_usage（endpoint=chatbot_embedding）

后端选择（由 EMBEDDING_BASE_URL 决定）：
- 空或 "local"：本地 sentence-transformers（无需 Ollama/网络）
- 其他：OpenAI 兼容协议远程服务（Ollama/OpenAI/智谱等）

设计原因：DeepSeek 不支持 /v1/embeddings，Ollama 在 Windows 上又可能缺
llama-server.exe，本地 sentence-transformers 是最可靠的无外部依赖方案。
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

import httpx
from loguru import logger

from xianyu_hunter.config import get_settings


class EmbeddingService:
    """向量化服务：单例，通过 container 注入

    异常边界：
    - embed 失败返回空列表
    - embed_batch 部分失败返回 (成功向量列表, 失败索引列表)
    """

    def __init__(
        self,
        ai_usage: Any,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        concurrency: int = 5,
    ) -> None:
        self._ai_usage = ai_usage
        self._model = model
        self._dimensions = dimensions
        # 并发控制：避免触发 OpenAI API 限流（429）
        # 本地 backend 同样保留 semaphore：模型推理仍占用 CPU，避免任务堆积
        self._semaphore = asyncio.Semaphore(concurrency)
        # 最近一次批量调用的失败索引列表（保留供调试与监控查询）
        self._last_batch_failures: list[int] = []

        # Embedding 后端选择：
        # - EMBEDDING_BASE_URL 为空或 "local"：本地 sentence-transformers
        # - 其他：OpenAI 兼容协议远程服务
        settings = get_settings()
        base_url = settings.embedding_base_url.strip() if settings.embedding_base_url else ""

        self._is_local = not base_url or base_url.lower() == "local"
        # 本地 backend 实例：懒加载，首次 embed 时才加载模型权重
        # 避免启动时下载/加载阻塞服务就绪
        self._local_backend: Any = None
        self._http: httpx.AsyncClient | None = None

        if self._is_local:
            # 本地模式不需要 HTTP 客户端和 API Key
            self._api_key = ""
            self._embeddings_url = ""
            logger.info(
                f"EmbeddingService 启用本地 backend（model={model}），"
                f"模型将在首次调用时加载"
            )
        else:
            # 远程模式：embedding endpoint 独立于 LLM，优先读 settings.embedding_*，
            # 未配置时 fallback 到 openai_*（向后兼容旧部署）
            self._api_key = settings.embedding_api_key or settings.openai_api_key
            self._embeddings_url = base_url.rstrip("/") + "/embeddings"
            # 单条 embed 和批量 embed 共用一个 AsyncClient（连接池复用，减少握手开销）
            self._http = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=2.0),
            )

    def _get_local_backend(self) -> Any:
        """懒加载本地 embedding backend

        首次调用时实例化 LocalEmbeddingBackend 并加载模型（约 95MB for bge-small-zh-v1.5）。
        后续调用直接复用，避免重复加载。
        """
        if self._local_backend is None:
            # 延迟导入：避免未安装 torch 时整个模块 import 失败
            # 远程模式用户无需安装 torch
            from xianyu_hunter.modules.chatbot.local_embedding import LocalEmbeddingBackend
            self._local_backend = LocalEmbeddingBackend(self._model)
            # 触发模型加载（首次会下载权重到 HuggingFace cache）
            # 通过 to_thread 异步加载，避免阻塞事件循环
        return self._local_backend

    async def embed(self, text: str) -> list[float]:
        """单条文本向量化

        单次调用不走并发控制（semaphore），因为 RAGEngine.retrieve 每次只 embed 一个 query，
        semaphore 反而增加无谓的协程切换开销。
        """
        try:
            return await self._call_embedding(text)
        except Exception:
            # 基础设施层容错：不向上抛出，避免单次检索失败拖垮整个对话
            logger.exception("Embedding 单条调用失败")
            return []

    async def embed_batch(
        self,
        texts: list[str],
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> tuple[list[list[float]] | None, list[int]]:
        """批量向量化

        算法：
        1. 本地模式：调用 sentence-transformers 原生 batch 接口（一次 encode 多条文本）
           - 比循环单条快 10-50 倍（向量化 + GPU/CPU 内部并行）
           - 外层按 _LOCAL_BATCH_CHUNK 分批，每批完成后回调 progress_cb 反馈进度
             （避免数千片段一次性 encode 时前端进度条无变化被误判为卡死）
        2. 远程模式：并发控制 Semaphore(concurrency) + 每条独立重试 3 次
           - 指数退避 0.5s/1s/2s
           - 失败的文本记录索引，不阻塞其他文本
           - progress_cb 在所有任务 gather 完成后回调一次（远程 API 自身有速率限制，
             细粒度进度反馈意义有限且增加回调开销）
        3. 返回 (成功向量列表, 失败索引列表)

        边界条件：
        - 空列表：返回 (None, [])，由调用方判断
        - 部分失败（远程模式）：跳过失败片段，失败率 >10% 记 warning
        """
        if not texts:
            return None, []

        self._last_batch_failures = []

        if self._is_local:
            return await self._embed_batch_local(texts, progress_cb=progress_cb)

        # 远程模式：单条并发 + 重试
        # 用 dict 保存成功结果，按原始 idx 聚合，最后按顺序输出
        results: dict[int, list[float]] = {}

        async def embed_one(idx: int, text: str) -> None:
            async with self._semaphore:
                # 指数退避：0.5s / 1s / 2s（attempt=0/1/2）
                for attempt in range(3):
                    try:
                        vec = await self._call_embedding(text)
                        results[idx] = vec
                        return
                    except Exception as e:
                        if attempt == 2:
                            # 重试 3 次仍失败，记录索引并跳过该片段
                            logger.warning(
                                f"Embedding 片段 {idx} 失败（重试 3 次）: "
                                f"{type(e).__name__}: {e}"
                            )
                            self._last_batch_failures.append(idx)
                            return
                        await asyncio.sleep(0.5 * (2 ** attempt))

        tasks = [embed_one(i, t) for i, t in enumerate(texts)]
        await asyncio.gather(*tasks)

        # 按原顺序构造成功向量列表（保持与输入文本的对应关系）
        success_vectors = [results[i] for i in range(len(texts)) if i in results]
        failed_indices = sorted(self._last_batch_failures)

        # 失败率 >10% 记 warning 但不终止：由调用方决定是否中止构建
        fail_rate = len(failed_indices) / len(texts)
        if fail_rate > 0.1:
            logger.warning(
                f"Embedding 批量调用失败率 {fail_rate:.1%} "
                f"({len(failed_indices)}/{len(texts)})，超过 10% 阈值"
            )

        if progress_cb is not None:
            try:
                progress_cb(len(texts), len(texts))
            except Exception:
                logger.debug("embed_batch 进度回调异常，忽略", exc_info=True)

        return success_vectors, failed_indices

    # 本地模式外层分批大小：sentence-transformers 内部已 batch_size=32，
    # 外层分批仅用于阶段性进度反馈，不会影响推理性能。
    # 取 256 平衡「进度反馈频率」和「to_thread 切换开销」：
    # - 太小（如 64）会导致 10000+ 片段时 to_thread 切换 150+ 次开销显著
    # - 太大（如 1024）进度回调粒度过粗，前端长时间无变化
    _LOCAL_BATCH_CHUNK = 256

    # 本地模式单批 encode 超时阈值（秒）：
    # 用户在 CPU 上跑 10000+ 片段 bge-small 实测 ~1.5h，
    # 单批 256 片段正常耗时约 30-90s；超过 600s 必为异常（死锁 / OOM 换页 / 模型损坏）
    # 超时后抛 TimeoutError 让上层 _rollback_build 接管，避免无限卡死。
    _LOCAL_BATCH_TIMEOUT_SEC = 600

    # 进度日志节流阈值：每处理 N 个片段打一次 INFO 日志
    # 10000 片段 / 500 = 20 行日志，足够观察趋势又不刷屏
    _PROGRESS_LOG_EVERY = 500

    async def _embed_batch_local(
        self,
        texts: list[str],
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> tuple[list[list[float]], list[int]]:
        """本地模式批量向量化

        利用 sentence-transformers 原生 batch 接口。
        外层按 _LOCAL_BATCH_CHUNK 分批 encode，每批完成后回调 progress_cb，
        让前端能看到向量化进度，避免数千片段一次性 encode 时被误判为卡死。

        看门狗：单批 encode 超过 _LOCAL_BATCH_TIMEOUT_SEC 抛 TimeoutError，
        避免进程卡死时无限等待（让 _rollback_build 接管清理）。

        日志节流：每 _PROGRESS_LOG_EVERY 个片段打一次 INFO 日志，
        便于运维事后分析「跑到哪一步」「卡在哪个片段」。

        预算检查一次即可（不按条计费），失败时整批失败。
        """
        # 预算检查：本地模式不消耗 token，但仍检查总调用次数预算
        budget_ok, reason = self._ai_usage.check_budget()
        if not budget_ok:
            logger.warning(f"Embedding 预算超限，跳过批量向量化: {reason}")
            return [], list(range(len(texts)))

        backend = self._get_local_backend()
        total = len(texts)
        chunk = self._LOCAL_BATCH_CHUNK
        start_ts = asyncio.get_event_loop().time()
        last_log_done = 0
        try:
            all_vecs: list[list[float]] = []
            for start in range(0, total, chunk):
                batch = texts[start:start + chunk]
                # to_thread 包装：sentence-transformers 是同步库，避免阻塞事件循环
                # 看门狗：用 wait_for 包装 to_thread，单批超时则中止
                # （sentence-transformers 不支持 cancel，但 wait_for 超时后
                #  调用方会抛 TimeoutError，至少能跳到 except 让 _rollback 接管）
                vecs = await asyncio.wait_for(
                    asyncio.to_thread(backend.embed_batch, batch),
                    timeout=self._LOCAL_BATCH_TIMEOUT_SEC,
                )
                all_vecs.extend(vecs)
                done = min(start + chunk, total)
                last_log_done = self._log_batch_progress(
                    done, total, start_ts, last_log_done
                )
                self._safe_invoke_progress_cb(progress_cb, done, total)
            # 本地模式无远程 token 费用，但按批量文本总字符估算 token 量回填统计，
            # 让仪表盘能反映 embedding 负载；费用明确置 0（本地不花钱）。
            total_chars = sum(len(t) for t in texts)
            self._ai_usage.record_usage(
                endpoint="chatbot_embedding",
                model=self._model,
                input_tokens_override=max(1, int(total_chars / 1.5)),
                cost_override=0.0,
                billable=False,
            )
            return all_vecs, []
        except asyncio.TimeoutError:
            # 单批 encode 超时：模型可能死锁 / OOM 换页 / 损坏
            # 不静默重试，直接返回全部失败让 _rollback_build 接管
            elapsed = asyncio.get_event_loop().time() - start_ts
            logger.error(
                f"Embedding 单批 encode 超时 "
                f"(>{self._LOCAL_BATCH_TIMEOUT_SEC}s)，已处理 {len(all_vecs)}/{total}，"
                f"耗时 {elapsed:.0f}s，触发回滚"
            )
            return [], list(range(len(texts)))
        except Exception:
            logger.exception("本地 batch embedding 失败")
            return [], list(range(len(texts)))

    def _log_batch_progress(
        self,
        done: int,
        total: int,
        start_ts: float,
        last_log_done: int,
    ) -> int:
        """节流打日志：每 _PROGRESS_LOG_EVERY 个片段或最后一批时打 INFO

        返回新的 last_log_done（供下次调用对比），未到节流阈值时返回原值。
        提取为独立方法以降低 _embed_batch_local 的嵌套认知复杂度。
        """
        # 节流阈值未到且非最后一批：跳过日志
        if done - last_log_done < self._PROGRESS_LOG_EVERY and done != total:
            return last_log_done
        elapsed = asyncio.get_event_loop().time() - start_ts
        if elapsed > 0 and done > 0:
            rate = done / elapsed
            eta = (total - done) / rate if rate > 0 else 0
            logger.info(
                f"Embedding 进度: {done}/{total} "
                f"({done*100//total}%) {rate:.1f}/s ETA {eta:.0f}s"
            )
        else:
            logger.info(f"Embedding 进度: {done}/{total}")
        return done

    def _safe_invoke_progress_cb(
        self,
        progress_cb: Callable[[int, int], None] | None,
        done: int,
        total: int,
    ) -> None:
        """进度回调的安全包装：回调失败不影响构建主流程"""
        if progress_cb is None:
            return
        try:
            progress_cb(done, total)
        except Exception:
            # 进度回调失败不应影响构建主流程
            logger.debug("embed_batch 进度回调异常，忽略", exc_info=True)

    @property
    def last_batch_failure_count(self) -> int:
        """返回上次批量调用的失败数（供调用方快速判断是否需告警/中止）

        M-15 修复：原命名 last_batch_failures（复数）暗示返回列表，实际返回 int 数量。
        """
        return len(self._last_batch_failures)

    async def _call_embedding(self, text: str) -> list[float]:
        """统一入口：根据 backend 分发到本地或远程实现

        调用前 check_budget，调用后 record_usage（endpoint=chatbot_embedding）。
        异常向上抛出由调用方处理：embed 走 logger 兜底，embed_batch 走重试逻辑。
        """
        # 预算检查：避免超额调用导致费用失控
        budget_ok, reason = self._ai_usage.check_budget()
        if not budget_ok:
            raise RuntimeError(f"Embedding 预算超限: {reason}")

        if self._is_local:
            return await self._call_local(text)
        return await self._call_remote(text)

    def _estimate_local_tokens(self, text: str) -> int:
        """本地 embedding 不消耗远程 token/费用，但用字符数粗略估算 token 量，
        让「今日 Tokens / 近 7 天趋势」能反映 embedding 真实负载，
        避免本地大量 embedding 调用在仪表盘上完全不可见（看起来像漏记）。
        中文约 1.5 字符/token；按字符数 / 1.5 估算并取整，至少记 1。
        """
        return max(1, int(len(text) / 1.5))

    async def _call_local(self, text: str) -> list[float]:
        """本地 backend 调用：通过 to_thread 包装同步推理"""
        backend = self._get_local_backend()
        # to_thread：sentence-transformers 是同步库，避免阻塞事件循环
        vec = await asyncio.to_thread(backend.embed, text)
        # 本地模式无远程 token 费用，但用估算 token 量回填用量统计，
        # 让仪表盘能反映 embedding 负载；费用明确置 0（本地不花钱）。
        self._ai_usage.record_usage(
            endpoint="chatbot_embedding",
            model=self._model,
            input_tokens_override=self._estimate_local_tokens(text),
            cost_override=0.0,
            billable=False,
        )
        return vec

    async def _call_remote(self, text: str) -> list[float]:
        """远程 backend 调用：OpenAI 兼容 /v1/embeddings 协议"""
        payload: dict[str, Any] = {
            "model": self._model,
            "input": text,
        }
        # dimensions=0 表示由模型决定（Ollama nomic-embed-text 等本地模型不接受该参数）
        # 仅 OpenAI text-embedding-3-* 系列才需要显式指定 dimensions
        if self._dimensions > 0:
            payload["dimensions"] = self._dimensions
        assert self._http is not None  # 远程模式 __init__ 必定创建
        resp = await self._http.post(self._embeddings_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        # 记录用量（endpoint 命名 chatbot_embedding，便于按用途统计费用）
        self._ai_usage.record_usage(
            endpoint="chatbot_embedding",
            model=self._model,
            response_data=data,
        )
        return data["data"][0]["embedding"]
