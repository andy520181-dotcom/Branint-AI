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


def _extract_logo_prompt(visual_output: str) -> str:
    """
    从美术指导 Agent 的输出中提取 Logo 设计方向，
    构建适合图片生成模型的英文 Prompt。
    """
    # 尝试从 handoff 或正文中提取关键信息
    style_keywords = []
    color_hex = []

    # 提取 HEX 色值
    hex_matches = re.findall(r"#[0-9A-Fa-f]{6}", visual_output)
    if hex_matches:
        color_hex = hex_matches[:3]  # 最多取前 3 个

    # 提取风格关键词
    style_match = re.search(r"(?:风格|调性|关键词)[：:]\s*(.+)", visual_output)
    if style_match:
        style_keywords.append(style_match.group(1).strip()[:50])

    # 构建 prompt
    prompt_parts = [
        "Design a professional brand logo.",
        "Clean, minimal, flat design style.",
        "White background, suitable for brand identity.",
    ]
    if color_hex:
        prompt_parts.append(f"Use these brand colors: {', '.join(color_hex)}.")
    if style_keywords:
        prompt_parts.append(f"Visual style: {', '.join(style_keywords)}.")

    return " ".join(prompt_parts)


async def generate_brand_images(
    visual_output: str,
    user_prompt: str,
) -> list[dict]:
    """
    根据美术指导 Agent 的输出生成品牌参考图。

    返回：[{"type": "logo", "mime": "image/jpeg", "data_url": "data:image/jpeg;base64,..."}]
    """
    client = _get_client()
    results: list[dict] = []

    # NOTE: 生成 Logo 概念图
    logo_prompt = (
        f"Based on this brand brief: {user_prompt[:200]}. "
        f"{_extract_logo_prompt(visual_output)} "
        "Create a professional, premium brand logo design. "
        "Minimal, modern, clean flat design. White background."
    )

    for attempt in range(2):
        try:
            logger.info("开始调用内置 Nano/Fast 图片生成模型 (Banner 款)...")
            # 使用专用的 generate_images 接口，支持指定长宽比 (Banner 常规比例 16:9)
            response = client.models.generate_images(
                model=IMAGE_MODEL,
                prompt=logo_prompt,
                config=dict(
                    number_of_images=1,
                    aspect_ratio="16:9",  # Banner 比例
                    output_mime_type="image/jpeg",
                )
            )

            for img in response.generated_images:
                if img.image and img.image.image_bytes:
                    mime = "image/jpeg"
                    logger.info("Nano Banner 图片生成成功，准备上传 OSS (大小: %d bytes)", len(img.image.image_bytes))
                    
                    # 彻底丢弃 base64 通过流强推前端的内存杀手做法，转为直接上传至阿里云 OSS
                    oss_url = await upload_file(
                        content=img.image.image_bytes,
                        original_name="ai_generated_banner.jpg",
                        content_type=mime,
                    )
                    
                    results.append({
                        "type": "banner",
                        "mime": mime,
                        "data_url": oss_url,
                    })
                    logger.info("Nano Banner 图片生成成功，大小: %d bytes", len(img.image.image_bytes))
            break  # 成功则跳出重试循环
        except Exception as e:
            import asyncio
            if attempt < 1:
                logger.warning("图片生成失败（第 %d 次），2s 后重试: %s", attempt + 1, e)
                await asyncio.sleep(2)
            else:
                logger.error("图片生成重试后仍失败: %s", e)

    return results
