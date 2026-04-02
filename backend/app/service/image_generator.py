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

from google import genai

logger = logging.getLogger(__name__)

# NOTE: 图片生成使用 Google GenAI SDK 直接调用，不走 LiteLLM
IMAGE_MODEL = "gemini-3-pro-image-preview"


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

    try:
        logger.info("开始生成品牌 Logo 概念图...")
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=[logo_prompt],
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                img_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                mime = part.inline_data.mime_type or "image/jpeg"
                results.append({
                    "type": "logo",
                    "mime": mime,
                    "data_url": f"data:{mime};base64,{img_b64}",
                })
                logger.info(
                    "Logo 图片生成成功，大小: %d bytes",
                    len(part.inline_data.data),
                )
            elif part.text is not None:
                logger.info("图片生成附带文本: %s", part.text[:100])

    except Exception as e:
        logger.error("图片生成失败: %s", e)

    return results
