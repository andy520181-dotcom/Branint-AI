"""
SQLAlchemy 异步数据库引擎与 Session 工厂。

NOTE: 使用 asyncpg 驱动（postgresql+asyncpg://）实现非阻塞数据库访问，
      确保 FastAPI 异步路由在数据库 I/O 期间不阻塞事件循环。
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# NOTE: DATABASE_URL 中的 postgresql:// 需替换为 postgresql+asyncpg://
#       config.py 中原始值可能是 postgresql://，这里统一处理
def _build_async_url(url: str) -> str:
    """将同步 DSN 转换为 asyncpg DSN。"""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


_async_url = _build_async_url(settings.database_url)

# NOTE: pool_size=5 适合 MVP 阶段单机部署；生产可按实例规格调高
engine = create_async_engine(
    _async_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # 自动检测断开的连接，防止 idle 连接失效
    echo=False,          # 生产环境关闭 SQL 日志，调试时可改为 True
)

# NOTE: expire_on_commit=False 避免在 async 场景下 commit 后访问属性触发懒加载报错
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有 ORM Model 的基类。"""
    pass


async def get_db() -> AsyncSession:  # type: ignore[return]
    """
    FastAPI 依赖注入：提供一个可用的数据库 Session。
    使用 async with 确保请求结束后 Session 自动关闭。
    """
    async with AsyncSessionFactory() as session:
        yield session
