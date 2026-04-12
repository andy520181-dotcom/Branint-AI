"""
FastAPI 应用入口。

NOTE: 使用 lifespan 替代 @app.on_event('startup')（FastAPI 0.93+ 推荐方式）。
      应用启动时自动执行 init_db()，确保数据库表就绪后再接受请求。
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings, configure_litellm_keys
from app.api import sessions, auth, assets
# NOTE: 必须在 create_all 之前导入所有 ORM 模型，否则 SQLAlchemy 不知道要建哪些表
from app.model import session as _session_model  # noqa: F401
from app.model import agent_event as _agent_event_model  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 应用启动时注入 LiteLLM 所需的 API Keys
configure_litellm_keys()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理：
    - 启动：完成配置加载等准备工作
    - 关闭：清理资源
    """
    # NOTE: 使用 NullPool 创建一次性独立引擎执行 create_all，
    # 避免与主连接池冲突导致 lifespan 启动时 asyncio.TimeoutError
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from app.db.database import Base, _async_url
    init_engine = create_async_engine(_async_url, poolclass=NullPool)
    try:
        async with init_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        logger.info("应用启动，数据库表已就绪，开始接受请求...")
    except Exception as e:
        logger.warning("数据库表初始化失败（将使用降级快照路径）: %s", e)
    finally:
        await init_engine.dispose()
    yield
    logger.info("应用关闭")


app = FastAPI(
    title="Branin AI 品牌咨询平台 API",
    description="多 Agent 协作的品牌战略生成平台",
    version="0.1.0",
    lifespan=lifespan,
)

_allowed_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(auth.router)
app.include_router(assets.router)

# NOTE: 暴露本地上传目录为公共静态目录，允许前端通过 /uploads/<filename> Preview 图片
_upload_dir = Path(__file__).parent.parent / "data" / "uploads"
_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_upload_dir)), name="uploads")


@app.get("/health")
async def health_check() -> dict:
    """健康检查接口"""
    return {"status": "ok", "model": settings.default_model}


@app.post("/api/admin/reload-prompts")
async def reload_prompts() -> dict:
    """
    热更新 Agent 规则文件
    修改 agents/*.md 后调用此接口即可立即生效，无需重启后端
    """
    from app.service.prompt_loader import reload_all
    reload_all()
    logger.info("Agent 规则文件已热更新")
    return {"status": "ok", "message": "Agent 规则文件缓存已清空，下次调用将加载最新规则"}
