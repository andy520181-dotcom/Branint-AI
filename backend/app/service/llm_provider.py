from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import litellm

from app.config import settings

logger = logging.getLogger(__name__)

# NOTE: MVP 阶段只用 DeepSeek，但通过 LiteLLM 调用
# HACK: 未来 Phase 2 Pro 用户切换模型时只需改 model 参数，无需重构此函数
async def call_llm_stream(
    messages: list[dict],
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    统一 LLM 流式调用入口
    MVP 阶段默认使用 DeepSeek-V3，Phase 2 Pro 用户可传入不同模型名
    """
    target_model = model or settings.default_model
    logger.info("调用 LLM 模型: %s", target_model)

    # NOTE: Gemini 3 系列要求 temperature >= 1.0，否则会触发无限循环和推理性能下降
    temp = 1.0 if "gemini-3" in target_model else 0.7

    try:
        response = await litellm.acompletion(
            model=target_model,
            messages=messages,
            stream=True,
            temperature=temp,
            max_tokens=4096,
        )

        async for chunk in response:
            token = chunk.choices[0].delta.content or ""
            if token:
                yield token

    except litellm.APIError as e:
        logger.error("LLM API 调用失败: %s", e)
        raise


async def call_llm(
    messages: list[dict],
    model: str | None = None,
) -> str:
    """
    非流式调用（用于 Agent 间上下文传递时获取完整输出）
    """
    target_model = model or settings.default_model
    logger.info("调用 LLM 模型（非流式）: %s", target_model)

    # NOTE: Gemini 3 系列要求 temperature >= 1.0
    temp = 1.0 if "gemini-3" in target_model else 0.7

    response = await litellm.acompletion(
        model=target_model,
        messages=messages,
        stream=False,
        temperature=temp,
        max_tokens=4096,
    )
    return response.choices[0].message.content or ""
