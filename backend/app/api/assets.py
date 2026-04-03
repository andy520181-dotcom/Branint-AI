"""
文件资产上传接口
支持将图片、PDF、文档等上传到服务器，返回资源 URL 供 LLM 会话引用
"""

import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/assets", tags=["assets"])
logger = logging.getLogger(__name__)

# NOTE: 上传文件存储在项目本地磁盘，MVP 阶段无需云存储
UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 允许上传的 MIME 类型白名单
ALLOWED_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/webp", "image/gif",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# 单文件最大 20MB
MAX_FILE_SIZE = 20 * 1024 * 1024


@router.post("/upload")
async def upload_asset(file: UploadFile = File(...)) -> JSONResponse:
    """
    上传品牌资产文件（图片、PDF、文档等）
    返回资源访问 URL，供前端预览及后续会话引用
    """
    # 校验文件类型
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件类型 {file.content_type}。支持：图片(PNG/JPEG/WebP)、PDF、Word文档、纯文本。"
        )

    # 读取内容并校验大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过 20MB 限制（当前：{len(content) // 1024 // 1024}MB）"
        )

    # NOTE: 用 UUID 前缀防止文件名碰撞，保留原始扩展名以便前端类型判断
    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix or ".bin"
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = UPLOAD_DIR / stored_name

    stored_path.write_bytes(content)
    logger.info("文件上传成功: %s -> %s (%d bytes)", original_name, stored_name, len(content))

    return JSONResponse({
        "url": f"/uploads/{stored_name}",
        "original_name": original_name,
        "content_type": file.content_type,
        "size": len(content),
    })
