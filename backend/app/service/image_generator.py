"""
品牌图片生成服务（基于 Gemini 3 Pro Image）

从美术指导 Agent 的文本输出中提取设计描述，
调用 gemini-3-pro-image-preview 生成品牌参考图。
"""
from __future__ import annotations

import base64
import logging
import os
import re

from app.storage.oss_service import upload_file

from google import genai

logger = logging.getLogger(__name__)

# NOTE: Gemini 内置的 fast/nano 级别图片模型
IMAGE_MODEL = "imagen-4.0-fast-generate-001"


def _get_client() -> genai.Client:
    """获取 Google GenAI 客户端（懒加载）"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY 环境变量未设置")
    return genai.Client(api_key=api_key)


async def generate_brand_images(
    image_type: str,
    midjourney_prompt: str,
    aspect_ratio: str,
) -> list[dict]:
    """
    根据美术指导 Agent 提供的高品质提示词生成品牌资产图像。
    返回：[{"type": "logo", "mime": "image/jpeg", "data_url": "https://oss..."}]
    """
    client = _get_client()
    results: list[dict] = []

    # 将 1:1, 16:9, 9:16, 4:3 传递给 config
    allowed_ratios = ["1:1", "16:9", "9:16", "4:3"]
    safe_ratio = aspect_ratio if aspect_ratio in allowed_ratios else "16:9"

    for attempt in range(2):
        try:
            logger.info("开始调用内置 Nano/Fast 图片生成模型 (%s 款)...", image_type)
            response = client.models.generate_images(
                model=IMAGE_MODEL,
                prompt=midjourney_prompt,
                config=dict(
                    number_of_images=1,
                    aspect_ratio=safe_ratio,
                    output_mime_type="image/jpeg",
                )
            )

            for img in response.generated_images:
                if img.image and img.image.image_bytes:
                    mime = "image/jpeg"
                    
                    oss_url = await upload_file(
                        content=img.image.image_bytes,
                        original_name=f"ai_generated_{image_type}.jpg",
                        content_type=mime,
                    )
                    
                    results.append({
                        "type": image_type,
                        "mime": mime,
                        "data_url": oss_url,
                    })
                    logger.info("Nano %s 图片生成成功并上传 OSS，大小: %d bytes", image_type, len(img.image.image_bytes))
            break  # 成功则跳出重试循环
        except Exception as e:
            import asyncio
            if attempt < 1:
                logger.warning("图片生成失败（第 %d 次），2s 后重试: %s", attempt + 1, e)
                await asyncio.sleep(2)
            else:
                logger.error("图片生成重试后仍失败: %s", e)

    return results
