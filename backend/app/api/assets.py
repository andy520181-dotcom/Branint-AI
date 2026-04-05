"""
文件资产上传接口。
上传至阿里云 OSS，返回公开访问 URL，供 LLM 会话引用及前端预览。

NOTE: 本地 /uploads 静态目录仅保留做降级兜底，正式上传全部走 OSS。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.storage.oss_service import ALLOWED_CONTENT_TYPES, MAX_FILE_SIZE, upload_file

router = APIRouter(prefix="/api/assets", tags=["assets"])
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_asset(file: UploadFile = File(...)) -> JSONResponse:
    """
    上传品牌资产文件（图片、PDF、文档等）到阿里云 OSS。
    返回 OSS 公开 URL，供前端预览及后续 Agent 会话引用。
    """
    # 校验文件类型
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件类型 {file.content_type}。支持：图片(PNG/JPEG/WebP/GIF)、PDF、Word文档、纯文本。",
        )

    # 读取内容并校验大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过 20MB 限制（当前：{len(content) // 1024 // 1024}MB）",
        )

    original_name = file.filename or "upload"

    try:
        url = await upload_file(content, original_name, file.content_type or "application/octet-stream")
    except Exception as e:
        logger.error("OSS 上传失败: %s, 错误: %s", original_name, e)
        raise HTTPException(status_code=500, detail=f"文件上传失败，请稍后重试")

    logger.info("文件上传完成: %s -> %s (%d bytes)", original_name, url, len(content))

    return JSONResponse({
        "url": url,
        "original_name": original_name,
        "content_type": file.content_type,
        "size": len(content),
    })
