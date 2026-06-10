"""一次性脚本：将 PostgreSQL 中已有的 StudentMemory 记录迁移到 Chroma 向量库。

用法（在项目根目录下运行）：
    python scripts/migrate_embeddings.py
"""

import sys
from pathlib import Path

# 将项目根目录加入 sys.path，使 from app.xxx 导入生效
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import logging
import uuid

from sqlalchemy import select

from app.database import async_session_factory
from app.models.memory import StudentMemory
from app.services.embedding_service import get_model
from app.services.vector_store import add_memory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 50


async def migrate():
    # 预热模型
    logger.info("加载 embedding 模型...")
    get_model()

    async with async_session_factory() as db:
        # 查询所有记忆
        result = await db.execute(select(StudentMemory).order_by(StudentMemory.created_at.asc()))
        all_memories = list(result.scalars().all())

        total = len(all_memories)
        logger.info(f"共发现 {total} 条记忆需要迁移")

        success = 0
        for i, mem in enumerate(all_memories):
            try:
                created_at_str = mem.created_at.strftime("%Y-%m-%d") if mem.created_at else "unknown"
                add_memory(
                    memory_id=str(mem.id),
                    content=mem.content,
                    student_id=str(mem.student_id),
                    created_at=created_at_str,
                    importance=mem.importance or "medium",
                )
                success += 1
                if (i + 1) % BATCH_SIZE == 0:
                    logger.info(f"进度：{i + 1}/{total}")
            except Exception as e:
                logger.error(f"迁移失败 id={mem.id}: {e}")

        logger.info(f"迁移完成：成功 {success}/{total}")


if __name__ == "__main__":
    asyncio.run(migrate())