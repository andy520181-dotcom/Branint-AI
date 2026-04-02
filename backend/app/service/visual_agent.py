from __future__ import annotations
from collections.abc import AsyncGenerator
from app.config import settings
from app.service.llm_provider import call_llm, call_llm_stream
from app.service.prompt_loader import load_agent_prompt


async def run_visual_agent(
    user_prompt: str,
    handoff_context: str,
) -> str:
    """
    美术指导 Agent（非流式）
    接收 market + strategy + content 的 handoff 交接摘要
    """
    user_content = f"品牌需求：\n{user_prompt}"
    if handoff_context:
        user_content += f"\n\n{handoff_context}"
    user_content += "\n\n请基于以上交接信息，制定完整的品牌视觉识别系统方案。"

    messages = [
        {"role": "system", "content": load_agent_prompt("visual")},
        {"role": "user", "content": user_content},
    ]
    # NOTE: 恢复文本推理与流式思考为全局默认模型 (DeepSeek)
    return await call_llm(messages, model=settings.default_model)


async def run_visual_agent_stream(
    user_prompt: str,
    handoff_context: str,
) -> AsyncGenerator[str, None]:
    """
    美术指导 Agent（流式）
    yield 每个 token，供 orchestrator 实时推送给前端
    """
    user_content = f"品牌需求：\n{user_prompt}"
    if handoff_context:
        user_content += f"\n\n{handoff_context}"
    user_content += "\n\n请基于以上交接信息，制定完整的品牌视觉识别系统方案。"

    messages = [
        {"role": "system", "content": load_agent_prompt("visual")},
        {"role": "user", "content": user_content},
    ]
    # NOTE: 恢复文本推理与流式思考为全局默认模型 (DeepSeek)
    async for chunk in call_llm_stream(messages, model=settings.default_model):
        yield chunk
