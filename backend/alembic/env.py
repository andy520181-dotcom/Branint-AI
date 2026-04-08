"""
Alembic 迁移脚本执行环境。

NOTE: 该文件连接两个世界：
  - alembic (同步迁移框架) 
  - asyncpg (异步数据库驱动)
使用 run_sync 在事件循环中运行同步 alembic 操作。
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# 导入应用配置，获取数据库 URL
from app.config import settings

# 导入所有 Model 确保 Base.metadata 包含全部表定义
import app.model.session      # noqa: F401
import app.model.user         # noqa: F401
import app.model.agent_event  # noqa: F401

from app.db.database import Base

# Alembic Config 对象，提供对 alembic.ini 值的访问
config = context.config

# 解析 logging 配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# NOTE: target_metadata 指向我们的 ORM 元数据，支持 autogenerate 差异检测
target_metadata = Base.metadata


def _get_async_url() -> str:
    """从应用配置读取并转换为 asyncpg DSN。"""
    url = settings.database_url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """
    在 'offline' 模式下运行迁移（只生成 SQL，不实际连接数据库）。
    用途：生成可审查的迁移脚本，适合 DBA 审核后手动执行。
    """
    url = _get_async_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,        # 检测列类型变化
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """在已有连接上执行迁移（被 run_migrations_online 调用）。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    在 'online' 模式下运行迁移（实际连接数据库执行 DDL）。

    NOTE: 使用 NullPool 而非连接池，因为迁移是一次性批量操作，
          迁移完成后应立即释放连接，不需要复用。
    """
    url = _get_async_url()
    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
        connect_args={
            "ssl": False,
            "command_timeout": 120.0,   # 迁移可能含大量 DDL，给足时间
        },
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
