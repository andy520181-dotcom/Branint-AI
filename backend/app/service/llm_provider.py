"""
统一 LLM 调用入口（LiteLLM 封装）。

NOTE: 使用 tenacity 对所有 LLM 调用实施指数退避重试，
      以应对 DeepSeek / 其他 Provider 偶发的 Server Disconnected / 503 错误。
      流式调用由于 AsyncGenerator 无法直接被 tenacity 装饰，采用内部循环重试方案。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

import litellm
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.config import settings

logger = logging.getLogger(__name__)

# NOTE: 哪些异常值得重试——网络抖动、服务端临时故障
_RETRYABLE = (
    litellm.InternalServerError,
    litellm.ServiceUnavailableError,
    litellm.Timeout,
    litellm.APIConnectionError,
)

_RETRY_DECORATOR = retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def _get_temp(target_model: str) -> float:
    """Gemini 3 系列要求 temperature >= 1.0，否则会触发无限循环和推理性能下降"""
    return 1.0 if "gemini-3" in target_model else 0.7


async def call_llm_stream(
    messages: list[dict],
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    统一 LLM 流式调用入口，带指数退避重试。
    MVP 阶段默认使用 DeepSeek-V3。

    NOTE: AsyncGenerator 不能被 tenacity 直接装饰，
          改为在内部对 acompletion 调用重试，然后流式迭代结果。
    """
    target_model = model or settings.default_model
    logger.info("调用 LLM 模型: %s", target_model)
    temp = _get_temp(target_model)

    # NOTE: 先完整拿到 response 对象（此步可重试），再迭代 chunk
    for attempt in range(3):
        try:
            response = await litellm.acompletion(
                model=target_model,
                messages=messages,
                stream=True,
                temperature=temp,
                max_tokens=4096,
                timeout=25.0,  # 强制 25s 超时限制，防止 TCP 假死阻塞整个协程和 SSE 推流
            )
            async for chunk in response:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield token
            return  # 正常完成，退出

        except _RETRYABLE as e:
            if attempt < 2:
                wait = 2 ** attempt * 2  # 2s, 4s
                logger.warning(
                    "LLM 流式调用失败（第 %d 次），%ds 后重试: %s",
                    attempt + 1, wait, e,
                )
                await asyncio.sleep(wait)
            else:
                logger.error("LLM 流式调用重试 3 次后仍失败: %s", e)
                raise
        except litellm.APIError as e:
            logger.error("LLM API 调用失败（不可重试）: %s", e)
            raise


@_RETRY_DECORATOR
async def call_llm(
    messages: list[dict],
    model: str | None = None,
) -> str:
    """
    非流式调用（用于 Agent 间上下文传递时获取完整输出），带自动重试。
    """
    target_model = model or settings.default_model
    logger.info("调用 LLM 模型（非流式）: %s", target_model)
    temp = _get_temp(target_model)

    response = await litellm.acompletion(
        model=target_model,
        messages=messages,
        stream=False,
        temperature=temp,
        max_tokens=4096,
        timeout=45.0,  # 非流式调用给予更多等待时间，但仍必须防止永久死锁
    )
    return response.choices[0].message.content or ""


@_RETRY_DECORATOR
async def call_llm_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
    tool_choice: str | dict | None = None,
) -> tuple[str, list[dict] | None]:
    """
    非流式调用增强版：支持 Tool Calling，带自动重试。
    返回: (文本内容, tool_calls结果列表)
    """
    target_model = model or settings.default_model
    logger.info("调用 LLM 模型（Tools）: %s, 启用Tools", target_model)
    temp = _get_temp(target_model)

    kwargs: dict = {
        "model": target_model,
        "messages": messages,
        "stream": False,
        "temperature": temp,
        "max_tokens": 4096,
        "tools": tools,
        "timeout": 45.0,  # 工具调用同样配置超时防假死
    }
    if tool_choice:
        kwargs["tool_choice"] = tool_choice

    response = await litellm.acompletion(**kwargs)
    choice = response.choices[0]

    content = choice.message.content or ""
    tool_calls = None
    if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
        tool_calls = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in choice.message.tool_calls
        ]

    return content, tool_calls
