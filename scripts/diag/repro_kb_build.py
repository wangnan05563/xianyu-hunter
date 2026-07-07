"""诊断脚本：主动跑一次 build_all，复现 13:51 失败场景

不走 HTTP，直接构造主容器 + chatbot 子容器，调用 KBManager.build_all。
所有异常完整打印 traceback（不像 api_kb._do_rebuild 那样吞掉）。
"""
import asyncio
import sys
import traceback
from pathlib import Path

# 项目根目录加进 sys.path
ROOT = Path(r"d:\code\otherProjects\17_xianyu")
sys.path.insert(0, str(ROOT / "src"))

from loguru import logger

# loguru 输出到 stderr（DEBUG 级别捕获所有 traceback）
logger.remove()
logger.add(sys.stderr, level="DEBUG", format="{time:HH:mm:ss.SSS} | {level:<7} | {message}")


async def main():
    logger.info("=== 开始诊断 build_all ===")

    # 走主容器：build_default_container 会创建 container.config / container.repo
    from xianyu_hunter.container import build_default_container
    container = build_default_container()
    if container.chatbot is None:
        logger.error("chatbot 子容器未启用")
        return 1

    cfg = container.config.chatbot
    logger.info(f"配置: chunk_size={cfg.kb.chunk_size} overlap={cfg.kb.chunk_overlap}")
    logger.info(f"doc_paths={cfg.kb.doc_paths}")
    logger.info(f"persist_path={cfg.kb.persist_path}")
    logger.info(f"embedding_model={cfg.kb.embedding_model} dim={cfg.kb.embedding_dimensions}")

    kb_manager = container.chatbot["kb_manager"]

    # 入口：清理陈旧 building（与生产路径一致）
    logger.info("调用 _cleanup_stale_building_versions()...")
    kb_manager._cleanup_stale_building_versions()

    # 关键：跑 build_all，不吞任何异常
    logger.info("开始 kb_manager.build_all() ...")
    try:
        version = await kb_manager.build_all()
        logger.info(
            f"build_all 完成: version_id={version.version_id[:8]} "
            f"status={version.status} chunks={version.chunk_count} "
            f"failed={version.failed_chunk_count}"
        )
    except Exception as e:
        logger.error(f"build_all 抛出未捕获异常: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
