"""
阿里云 OSS 对象存储服务封装。

NOTE: oss2 是同步 SDK，在 FastAPI 异步路由中使用 run_in_executor 包裹，
      避免阻塞事件循环。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from functools import partial
from pathlib import Path

import oss2

from app.config import settings

logger = logging.getLogger(__name__)

# NOTE: 模块级单例，避免每次上传都重建连接
_auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
_bucket = oss2.Bucket(_auth, f"https://{settings.oss_endpoint}", settings.oss_bucket_name)

# 允许上传的 MIME 类型白名单（与原 assets.py 保持一致）
ALLOWED_CONTENT_TYPES: set[str] = {
    "image/png", "image/jpeg", "image/webp", "image/gif",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# 单文件最大 20MB
MAX_FILE_SIZE = 20 * 1024 * 1024


def _build_object_key(original_name: str) -> str:
    """
    生成 OSS 对象路径：uploads/<uuid><ext>
    UUID 前缀防止文件名碰撞，按目录分组便于 OSS 管理。
    """
    suffix = Path(original_name).suffix or ".bin"
    return f"uploads/{uuid.uuid4().hex}{suffix}"


def _do_upload(object_key: str, content: bytes, content_type: str) -> str:
    """
    同步执行 OSS 上传（在线程池中调用，避免阻塞事件循环）。
    返回公开访问 URL。
    """
    headers = {"Content-Type": content_type}
    _bucket.put_object(object_key, content, headers=headers)
    public_url = f"{settings.oss_public_url.rstrip('/')}/{object_key}"
    logger.info("OSS 上传成功: %s -> %s", object_key, public_url)
    return public_url


async def upload_file(
    content: bytes,
    original_name: str,
    content_type: str,
) -> str:
    """
    异步上传文件到阿里云 OSS，返回公开访问 URL。

    NOTE: oss2 是同步阻塞 SDK，使用 run_in_executor 在线程池运行，
          保持 FastAPI 事件循环不被阻塞。
    """
    object_key = _build_object_key(original_name)
    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(
        None,
        partial(_do_upload, object_key, content, content_type),
    )
    return url
