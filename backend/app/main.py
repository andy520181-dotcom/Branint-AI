import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, configure_litellm_keys
from app.api import sessions, auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 应用启动时注入 LiteLLM 所需的 API Keys
configure_litellm_keys()

app = FastAPI(
    title="Brandclaw AI 品牌咨询平台 API",
    description="多 Agent 协作的品牌战略生成平台",
    version="0.1.0",
)

# NOTE: MVP 阶段允许所有来源，生产环境需限制为前端域名
_allowed_origins = list({
    settings.frontend_url,
    "http://localhost:3000",
    "http://127.0.0.1:3000",   # 通过 127.0.0.1 访问时的 CORS origin
    "http://localhost:3001",
    "http://127.0.0.1:3001",
})
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(auth.router)


@app.get("/health")
async def health_check() -> dict:
    """健康检查接口"""
    return {"status": "ok", "model": settings.default_model}
