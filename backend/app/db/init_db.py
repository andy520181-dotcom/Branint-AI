"""
数据库建表入口。

NOTE: 使用 checkfirst=True（即 CREATE TABLE IF NOT EXISTS 语义），
      应用每次启动时调用 init_db()，安全幂等，不会破坏已有数据。
"""

import logging

from app.db.database import Base, engine

# NOTE: 必须在 Base 之前导入所有 Model，否则 Base.metadata 中没有表定义
import app.model.session      # noqa: F401
import app.model.user         # noqa: F401
import app.model.agent_event  # noqa: F401

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """
    创建所有尚不存在的数据库表。
    在 FastAPI lifespan 启动事件中调用，确保应用启动时表已就绪。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表初始化完成（CREATE TABLE IF NOT EXISTS）")
